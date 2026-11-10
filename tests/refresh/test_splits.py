"""The splits on file and the basis rule (spec 2026-11-09 section 10): ``splits_for`` and
``build_inputs`` over a temporary database that ``fetch_company`` fills, ``apply_splits`` on its
own.

The router answers each endpoint a test sets with its payload, and every other endpoint with its
ACME fixture.
"""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from synthetic import M, add_company, bodies
from vendor_double import FIXTURES, Clients, Clock, Router

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.classifier import Deciles
from fairband.engine.route import CompanyInputs, value_company
from fairband.policy import Policy, load_policy
from fairband.policy.tax import load_tax_table
from fairband.refresh.fetch import fetch_company
from fairband.refresh.inputs import build_inputs
from fairband.refresh.inputs_splits import (
    SplitFigures,
    SplitOutcome,
    SplitRow,
    apply_splits,
    pending_splits,
    splits_for,
)
from fairband.store.observations import insert_observations, observations_for

TODAY = date(2026, 11, 1)
DECILES = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)
# Spec 13.4: a split of 2 dated between a quarter ending 30 Sep and a price of 30 Oct.
SPLIT = SplitRow(date(2026, 10, 15), 2.0, 1.0)
END, PRICE_DATE = date(2026, 9, 30), date(2026, 10, 30)

type Store = Callable[..., sqlite3.Connection]


@pytest.fixture
def store(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> Store:
    """Fetches ACME with the given payloads in place of its fixtures, then lists the company."""

    def fill(company: bool = True, **payloads: Any) -> sqlite3.Connection:
        router.bodies.update(
            {endpoint: json.dumps(body).encode() for endpoint, body in payloads.items()}
        )
        fetch_company(conn, clients.fmp, clients.gf, "ACME", policy, clock(), clients.secrets)
        if company:
            add_company(conn)
        return conn

    return fill


def test_splits_for_reads_the_rows_oldest_first(store: Store) -> None:
    conn = store(
        **bodies(),
        splits=[
            {"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1},
            {"symbol": "ACME", "date": "2019-05-20", "numerator": 3, "denominator": 2},
            {"symbol": "ACME", "date": "2010-01-04", "numerator": 1, "denominator": 10},
        ],
    )
    rows = splits_for(conn, "ACME")
    assert [(r.date, r.numerator, r.denominator) for r in rows] == [
        (date(2010, 1, 4), 1.0, 10.0),
        (date(2019, 5, 20), 3.0, 2.0),
        (date(2026, 10, 15), 2.0, 1.0),
    ]
    assert [r.ratio for r in rows] == [0.1, 1.5, 2.0]
    assert [r.word for r in rows] == ["1-for-10 reverse split", "3-for-2 split", "2-for-1 split"]


def test_a_split_word_prints_at_most_two_decimals() -> None:
    """A whole number prints as an integer, any other to two decimals with trailing zeros
    dropped."""
    day = date(2025, 1, 2)
    assert SplitRow(day, 1.0526, 1).word == "1.05-for-1 split"
    assert SplitRow(day, 1.1, 1).word == "1.1-for-1 split"
    assert SplitRow(day, 4, 3.0).word == "4-for-3 split"
    assert SplitRow(day, 1, 1.3333).word == "1-for-1.33 reverse split"


def test_splits_for_without_rows(store: Store) -> None:
    assert splits_for(store(**bodies(), splits=[]), "ACME") == ()


def test_splits_for_skips_a_half_split_and_a_zero_denominator(store: Store) -> None:
    """The normalizer stores neither; a store that holds one still reads no split from it."""
    conn = store(**bodies(), splits=[{"date": "2019-05-20", "numerator": 2, "denominator": 1}])
    denominator, numerator = observations_for(conn, "ACME", "split")
    insert_observations(
        conn,
        [
            replace(numerator, period=date(2021, 1, 4)),
            replace(numerator, period=date(2022, 1, 3)),
            replace(denominator, period=date(2022, 1, 3), value=Decimal(0)),
        ],
    )
    assert splits_for(conn, "ACME") == (SplitRow(date(2019, 5, 20), 2.0, 1.0),)


def test_splits_for_reads_the_latest_response_alone(store: Store, clock: Clock) -> None:
    """FMP's list at the newest fetch is the whole truth: a split it no longer lists, withdrawn
    or re-dated, is not read, though its observations stay on file."""
    kept = {"symbol": "ACME", "date": "2019-05-20", "numerator": 3, "denominator": 2}
    withdrawn = {"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1}
    conn = store(**bodies(), splits=[withdrawn, kept])
    assert [r.date for r in splits_for(conn, "ACME")] == [date(2019, 5, 20), date(2026, 10, 15)]
    clock.now += timedelta(days=2)  # past the reuse window: the splits are fetched again
    store(company=False, splits=[kept])
    assert splits_for(conn, "ACME") == (SplitRow(date(2019, 5, 20), 3.0, 2.0),)


def test_splits_for_without_a_usable_response(store: Store, router: Router) -> None:
    router.fail.add("splits")
    assert splits_for(store(**bodies()), "ACME") == ()


def build(conn: sqlite3.Connection) -> CompanyInputs:
    return build_inputs(conn, "ACME", load_policy(), load_tax_table(), TODAY)


def _trailing(eps: float) -> TrailingFigures:
    return TrailingFigures(END, 4, False, None, None, None, eps, None, None, None, None, None, None)


def _figures(count: float = 1000.0, eps: float = 4.0, street: float = 4.2) -> SplitFigures:
    return SplitFigures(
        shares_diluted=count,
        trailing=_trailing(eps),
        street_ttm_eps=street,
        gf_eps_ttm=None,
        gf_eps_ttm_as_of=None,
        gf_eps_without_nri=None,
        gf_eps_without_nri_as_of=None,
        quarter_estimates=(),
        annual_estimates=(),
    )


def _annual(year: int, eps: float, net_income: float | None) -> AnnualEstimate:
    return AnnualEstimate(year, date(year, 12, 31), eps, None, net_income, None, None)


def _quarter(end: date, eps: float, net_income: float | None) -> QuarterEstimate:
    return QuarterEstimate(end, end.year, "Q1", eps, None, net_income, None)


def _apply(
    figures: SplitFigures,
    splits: tuple[SplitRow, ...] = (SPLIT,),
    market_cap: float | None = 2000.0 * 50,
    price: float | None = 50.0,
) -> SplitOutcome:
    return apply_splits(
        figures,
        splits,
        statement_end=END,
        price_date=PRICE_DATE,
        quote_market_cap=market_cap,
        quote_price=price,
        tolerance=0.15,
    )


def _sentence(out: SplitOutcome) -> str:
    assert out.flag is not None
    return out.flag.sentence


def test_pending_splits_window() -> None:
    """A split after the newest statement and at or before the price date is pending; one on
    the price date is; one the day after is not; one on the statement end is not."""
    assert pending_splits([SPLIT], END, PRICE_DATE) == (SPLIT,)
    on_price = SplitRow(PRICE_DATE, 2, 1)
    assert pending_splits([on_price], END, PRICE_DATE) == (on_price,)
    assert pending_splits([SplitRow(date(2026, 10, 31), 2, 1)], END, PRICE_DATE) == ()
    assert pending_splits([SplitRow(END, 2, 1)], END, PRICE_DATE) == ()
    assert pending_splits([SPLIT], None, PRICE_DATE) == ()
    assert pending_splits([SPLIT], END, None) == ()


def test_the_statements_are_scaled_when_the_quote_shows_them_pre_split() -> None:
    """Spec 13.4: a count of 1,000 reads 2,000; the trailing EPS of $4 reads $2; the street
    actuals $4.20 read $2.10; each is noted and an estimate under split-scaled."""
    out = _apply(_figures())
    f = out.figures
    assert f.trailing is not None
    assert (f.shares_diluted, f.trailing.eps_diluted, f.street_ttm_eps) == (2000.0, 2.0, 2.1)
    assert set(out.notes) >= {"shares_diluted", "statements", "street_ttm_eps"}
    assert out.estimate_methods == {
        "shares_diluted": "split-scaled",
        "statements": "split-scaled",
        "street_ttm_eps": "split-scaled",
    }
    assert out.notes["shares_diluted"] == "×2 for the 2-for-1 split of 15 Oct 2026"
    assert out.flag is not None
    assert (out.flag.code, out.flag.word) == ("split-pending", "Split pending")
    assert out.flag.sentence == (
        "A 2-for-1 split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The diluted count (×2), the trailing EPS and the street actuals (÷2) are read on the "
        "post-split basis. The closes and the quote are FMP's, already on it."
    )


def test_the_statements_are_left_alone_when_fmp_has_restated_them() -> None:
    """The vendor finding of 2026-11-10: a count of 2,000 against a quote count of 2,000 is
    post-split; nothing is scaled and the sentence says so; the flag still fires."""
    out = _apply(_figures(count=2000.0, eps=2.0, street=2.1))
    assert out.figures == _figures(count=2000.0, eps=2.0, street=2.1)
    assert out.notes == {} and out.estimate_methods == {}
    assert "FMP's statements and street actuals already read on the post-split basis." in (
        _sentence(out)
    )


def test_without_the_quotes_count_the_statements_are_read_as_stored() -> None:
    out = _apply(_figures(), market_cap=None)
    assert out.figures.shares_diluted == 1000.0
    assert "The quote gives no share count, so the statements are read as stored." in (
        _sentence(out)
    )
    assert _apply(_figures(), price=0.0).figures.shares_diluted == 1000.0


def test_the_consensus_is_scaled_by_its_implied_count() -> None:
    """Spec 13.4: $4.20 on a net-income mean of 4,200 implies 1,000, the pre-split count, so it
    reads $2.10; $2.10 implying 2,000 is left alone; a row without a mean is left alone and
    named."""
    rows = (_annual(2026, 4.2, 4200.0), _annual(2027, 2.1, 4200.0), _annual(2028, 4.4, None))
    out = _apply(replace(_figures(), annual_estimates=rows))
    assert [a.eps for a in out.figures.annual_estimates] == [2.1, 2.1, 4.4]
    assert out.notes["estimates_annual"] == "EPS ÷ 2 for fiscal 2026"
    assert out.estimate_methods["estimates_annual"] == "split-scaled"
    assert "estimates_quarter" not in out.notes
    sentence = _sentence(out)
    assert "The consensus EPS for fiscal 2026 is read ÷2." in sentence
    assert "The consensus EPS for fiscal 2028 has no net-income mean and is read as stored." in (
        sentence
    )


def test_the_consensus_test_reads_the_post_split_count_when_the_statements_were_restated() -> None:
    """With the count already 2,000 (restated), a row implying 1,000 is pre-split and scales;
    one implying 2,000 stands."""
    rows = (_annual(2026, 4.2, 4200.0), _annual(2027, 2.1, 4200.0))
    out = _apply(replace(_figures(count=2000.0, eps=2.0, street=2.1), annual_estimates=rows))
    assert [a.eps for a in out.figures.annual_estimates] == [2.1, 2.1]


def test_quarterly_rows_scale_too_and_the_spans_read_first_to_last() -> None:
    annual = tuple(_annual(year, 4.0, 4000.0) for year in (2026, 2027, 2028))
    quarters = (
        _quarter(date(2026, 12, 31), 1.0, 1000.0),
        _quarter(date(2027, 3, 31), 1.1, 1100.0),
    )
    out = _apply(replace(_figures(), annual_estimates=annual, quarter_estimates=quarters))
    assert [a.eps for a in out.figures.annual_estimates] == [2.0, 2.0, 2.0]
    assert [q.eps for q in out.figures.quarter_estimates] == [0.5, 0.55]
    assert out.notes["estimates_annual"] == "EPS ÷ 2 for fiscal 2026 to 2028"
    assert out.notes["estimates_quarter"] == "EPS ÷ 2 for the quarters to 31 Mar 2027"
    assert out.estimate_methods["estimates_quarter"] == "split-scaled"
    assert (
        "The consensus EPS for fiscal 2026 to 2028 and for the quarters to 31 Mar 2027 is read "
        "÷2." in _sentence(out)
    )


def test_the_sentence_agrees_in_number_and_names_the_quarters_left() -> None:
    """One quarter scaled reads "the quarter to"; quarters without a net-income mean are named by
    period end; an 11-for-10 split takes "An"; a count within the tolerance of neither basis
    leaves the statements as stored with no statement sentence."""
    quarters = (
        _quarter(date(2026, 12, 31), 1.0, 1000.0),
        _quarter(date(2027, 3, 31), 1.1, None),
        _quarter(date(2027, 6, 30), 1.2, None),
    )
    out = _apply(replace(_figures(), quarter_estimates=quarters))
    assert out.notes["estimates_quarter"] == "EPS ÷ 2 for the quarter to 31 Dec 2026"
    assert (
        "The consensus EPS for the quarters ending 31 Mar 2027 and 30 Jun 2027 has no net-income "
        "mean and is read as stored." in _sentence(out)
    )
    small = SplitRow(date(2026, 10, 15), 11.0, 10.0)
    neither = _apply(_figures(), splits=(small,), market_cap=5000.0 * 50)
    assert neither.figures == _figures() and neither.notes == {}
    assert _sentence(neither) == (
        "An 11-for-10 split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The closes and the quote are FMP's, already on it."
    )


def test_a_row_within_both_counts_is_left_alone() -> None:
    """An 11-for-10 split: 1,000 and 1,100 lie within 15% of each other, so the implied count
    cannot tell the bases apart and the row stands."""
    small = SplitRow(date(2026, 10, 15), 11.0, 10.0)
    rows = (_annual(2026, 4.2, 4200.0),)
    figures = replace(_figures(count=1000.0), annual_estimates=rows)
    out = _apply(figures, splits=(small,), market_cap=1100.0 * 50)
    assert out.figures.annual_estimates[0].eps == 4.2
    # the count itself: 1,000 × 1.1 = 1,100 is within 15% of Q, but so is 1,000: left alone
    assert out.figures.shares_diluted == 1000.0


def test_gurufocus_figures_scale_by_observation_date() -> None:
    before, after = date(2026, 10, 10), date(2026, 10, 20)
    figures = replace(
        _figures(),
        gf_eps_ttm=6.0,
        gf_eps_ttm_as_of=before,
        gf_eps_without_nri=5.8,
        gf_eps_without_nri_as_of=after,
    )
    out = _apply(figures)
    assert (out.figures.gf_eps_ttm, out.figures.gf_eps_without_nri) == (3.0, 5.8)
    assert out.notes["gf_eps_ttm"] and "gf_eps_without_nri" not in out.notes
    assert out.estimate_methods["gf_eps_ttm"] == "split-scaled"
    assert "GuruFocus's EPS observed 10 Oct 2026 is read ÷2." in _sentence(out)


def test_a_reverse_split_multiplies_the_per_share_figures() -> None:
    reverse = SplitRow(date(2026, 10, 15), 1.0, 10.0)
    figures = _figures(count=1000.0, eps=4.0, street=4.2)
    out = _apply(figures, splits=(reverse,), market_cap=100.0 * 50)
    f = out.figures
    assert f.trailing is not None
    assert (f.shares_diluted, f.trailing.eps_diluted, f.street_ttm_eps) == (100.0, 40.0, 42.0)
    assert _sentence(out).startswith(
        "A 1-for-10 reverse split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The diluted count (×0.1), the trailing EPS and the street actuals (÷0.1)"
    )


def test_two_pending_splits_compound() -> None:
    two = (SPLIT, SplitRow(date(2026, 10, 20), 3.0, 2.0))
    out = _apply(_figures(), splits=two, market_cap=3000.0 * 50)
    assert out.figures.trailing is not None
    assert out.figures.shares_diluted == 3000.0
    assert out.figures.trailing.eps_diluted == pytest.approx(4 / 3)
    assert _sentence(out).startswith(
        "A 2-for-1 split of 15 Oct 2026 and a 3-for-2 split of 20 Oct 2026 fall after the newest "
        "statement (30 Sep 2026). The diluted count (×3),"
    )


def test_no_pending_split_changes_nothing() -> None:
    old = SplitRow(date(2019, 5, 20), 2.0, 1.0)
    out = _apply(_figures(), splits=(old,))
    assert out == SplitOutcome(_figures(), None, {}, {})
    assert _apply(_figures(), splits=()) == SplitOutcome(_figures(), None, {}, {})


def _quote(price: float, count: float) -> list[dict[str, Any]]:
    """The ACME quote fixture at ``price`` and a market cap of ``price × count``, its timestamp
    (30 Oct 2026) kept."""
    (row,) = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text())
    return [{**row, "price": price, "marketCap": price * count}]


def _acme_split(store: Store) -> sqlite3.Connection:
    """ACME split 2-for-1 on 2026-10-15, its quote at $25 on 208 m shares."""
    split = {"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1}
    return store(**bodies(), splits=[split], quote=_quote(25.0, 208 * M))


def test_build_inputs_reads_a_pending_split(store: Store) -> None:
    """ACME split 2-for-1 on 2026-10-15, after its newest quarter (30 Sep 2026) and before its
    quote (30 Oct 2026); the quote shows 208 m shares against 104 m stored, so the statements
    are pre-split and scale; the fixture's consensus rows imply 100 m, within 15% of 104 m,
    and scale; the GuruFocus figures, observed at the fetch (1 Nov 2026), stand."""
    inputs = build(_acme_split(store))
    assert inputs.shares_diluted == pytest.approx(208 * M)
    assert inputs.trailing is not None
    assert inputs.trailing.eps_diluted == pytest.approx(0.95)  # 1.90 halved
    assert inputs.street_ttm_eps == pytest.approx(1.05)  # 2.10 halved
    # each implies 100 m, within 15% of 104 m
    assert [a.eps for a in inputs.annual_estimates] == pytest.approx([1.0, 1.1, 1.2])
    assert [q.eps for q in inputs.quarter_estimates] == pytest.approx([0.26, 0.27, 0.28])
    assert inputs.gf_eps_ttm == 6.11
    assert inputs.input_flags[-1].code == "split-pending"  # after the statements' flags
    assert inputs.estimate_methods["shares_diluted"] == "split-scaled"
    assert inputs.notes["shares_diluted"] == "×2 for the 2-for-1 split of 15 Oct 2026"
    assert inputs.market_cap == pytest.approx(25.0 * 208 * M) and inputs.price == 25.0


@pytest.mark.parametrize("failed", [False, True], ids=["old-split", "failed-call"])
def test_build_inputs_without_a_pending_split_is_unchanged(
    store: Store, router: Router, failed: bool
) -> None:
    """The fixture's 2019 split predates every statement: nothing moves and no flag fires; the
    same when the splits call failed (no rows)."""
    if failed:
        router.fail.add("splits")
    inputs = build(store(**bodies()))
    assert "split-pending" not in [f.code for f in inputs.input_flags]
    assert "shares_diluted" not in inputs.notes
    assert "split-scaled" not in inputs.estimate_methods.values()
    assert inputs.shares_diluted == 104 * M
    assert inputs.trailing is not None and inputs.trailing.eps_diluted == pytest.approx(1.90)
    assert inputs.street_ttm_eps == pytest.approx(2.10)
    assert [a.eps for a in inputs.annual_estimates] == pytest.approx([2.0, 2.2, 2.4])


def test_the_flag_reaches_the_snapshot(store: Store) -> None:
    result = value_company(build(_acme_split(store)), DECILES, load_policy(), TODAY)
    assert "split-pending" in [f.code for f in result.flags]
    [shares] = [i for i in result.inputs if i.name == "shares_diluted"]
    assert shares.note == "×2 for the 2-for-1 split of 15 Oct 2026"
    assert (shares.kind, shares.estimate_method) == ("estimate", "split-scaled")
