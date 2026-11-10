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
from support import engine_companies
from synthetic import QUARTERS, M, add_company, bodies, estimates_quarter
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
from fairband.refresh.inputs_statements import TrailingPeriod, statements_for
from fairband.store.observations import insert_observations, observations_for

TODAY = date(2026, 11, 1)
DECILES = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)
# Spec 13.4: a split of 2 dated between a quarter ending 30 Sep and a price of 30 Oct.
SPLIT = SplitRow(date(2026, 10, 15), 2.0, 1.0)
END, PRICE_DATE = date(2026, 9, 30), date(2026, 10, 30)
# The four trailing quarters to END, oldest first.
ENDS = (date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), END)
# A split between the second and the third trailing quarter.
WITHIN = SplitRow(date(2026, 4, 15), 2.0, 1.0)
# The DATA inputs the statement side marks when it scales.
STATEMENT_KEYS = {"shares_diluted", "eps_ttm", "street_ttm_eps"}

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


def _trailing(eps: float | None, end: date = END, quarters: int = 4) -> TrailingFigures:
    yearly = quarters == 1
    return TrailingFigures(
        end, quarters, yearly, None, None, None, eps, None, None, None, None, None, None
    )


def _figures(
    count: float = 1000.0,
    eps: float = 4.0,
    street: float = 4.2,
    counts: tuple[float | None, ...] | None = None,
) -> SplitFigures:
    """Four trailing quarters, each a quarter of ``eps`` and of ``street``, on ``counts`` (each
    ``count`` unless given); the diluted count is ``count``."""
    each = (count,) * 4 if counts is None else counts
    return SplitFigures(
        shares_diluted=count,
        trailing=_trailing(eps),
        periods=tuple(TrailingPeriod(end, eps / 4, n) for end, n in zip(ENDS, each, strict=True)),
        street_actuals=tuple((end, street / 4) for end in ENDS),
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
    end: date = END,
) -> SplitOutcome:
    return apply_splits(
        figures,
        splits,
        statement_end=end,
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
    actuals $4.20 read $2.10; each is noted and an estimate under split-scaled, keyed by the
    engine's DATA input that holds it."""
    out = _apply(_figures())
    f = out.figures
    assert f.trailing is not None
    assert (f.shares_diluted, f.trailing.eps_diluted) == (2000.0, 2.0)
    assert f.street_ttm_eps == pytest.approx(2.1)
    assert out.notes == {
        "shares_diluted": "×2 for the 2-for-1 split of 15 Oct 2026",
        "eps_ttm": "÷2 for the 2-for-1 split of 15 Oct 2026",
        "street_ttm_eps": "÷2 for the 2-for-1 split of 15 Oct 2026",
    }
    assert out.estimate_methods == dict.fromkeys(STATEMENT_KEYS, "split-scaled")
    assert out.flag is not None
    assert (out.flag.code, out.flag.word) == ("split-pending", "Split pending")
    assert out.flag.sentence == (
        "A 2-for-1 split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The diluted count (×2), the trailing EPS and the street actuals (÷2 on the quarters to "
        "30 Sep 2026) are read on the post-split basis. The closes and the quote are FMP's, "
        "already on it."
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
    # no DATA input holds the annual consensus EPS: the sentence names it, no note does
    assert set(out.notes) == set(out.estimate_methods) == STATEMENT_KEYS
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
    assert set(out.notes) == STATEMENT_KEYS  # two quarters make no NTM window: no ntm_eps
    assert (
        "The consensus EPS for fiscal 2026 to 2028 and for the quarters to 31 Mar 2027 is read "
        "÷2." in _sentence(out)
    )


def test_the_ntm_eps_is_marked_only_when_an_ntm_quarter_scaled() -> None:
    """The NTM quarters are the first four ending after the statement end (``ntm_quarters``). A
    fifth quarter that scales leaves the NTM EPS as found, so it is unmarked though the sentence
    names the quarter; when the four scale, the NTM EPS carries the note, its span theirs."""
    ends = (date(2026, 12, 31), date(2027, 3, 31), date(2027, 6, 30), date(2027, 9, 30))
    fifth = _quarter(date(2027, 12, 31), 1.2, 1200.0)  # implies 1,000: pre-split
    restated = tuple(_quarter(end, 0.5, 1000.0) for end in ends)  # imply 2,000: post-split
    out = _apply(replace(_figures(), quarter_estimates=(*restated, fifth)))
    assert [q.eps for q in out.figures.quarter_estimates] == [0.5, 0.5, 0.5, 0.5, 0.6]
    assert "ntm_eps" not in out.notes and "ntm_eps" not in out.estimate_methods
    assert "The consensus EPS for the quarter to 31 Dec 2027 is read ÷2." in _sentence(out)
    found = tuple(_quarter(end, 1.0, 1000.0) for end in ends)  # imply 1,000: pre-split
    out = _apply(replace(_figures(), quarter_estimates=(*found, fifth)))
    assert out.notes["ntm_eps"] == (
        "the consensus quarters to 30 Sep 2027 ÷2 for the 2-for-1 split of 15 Oct 2026"
    )
    assert out.estimate_methods["ntm_eps"] == "split-scaled"


def test_a_reported_row_is_left_alone_and_unnamed() -> None:
    """Only the rows ending after the statement end (30 Sep 2026) are tested: a quarter ending
    30 Jun 2026 implying the pre-split count stands, and one ending on the statement end without
    a net-income mean goes unnamed, while the quarter ending 31 Dec 2026 scales."""
    quarters = (
        _quarter(date(2026, 6, 30), 4.2, 4200.0),
        _quarter(END, 4.4, None),
        _quarter(date(2026, 12, 31), 1.0, 1000.0),
    )
    out = _apply(replace(_figures(), quarter_estimates=quarters))
    assert [q.eps for q in out.figures.quarter_estimates] == [4.2, 4.4, 0.5]
    sentence = _sentence(out)
    assert "The consensus EPS for the quarter to 31 Dec 2026 is read ÷2." in sentence
    assert "net-income mean" not in sentence and "Jun 2026" not in sentence


def test_the_sentence_agrees_in_number_and_names_the_quarters_left() -> None:
    """One quarter scaled reads "the quarter to"; quarters without a net-income mean are named by
    period end."""
    quarters = (
        _quarter(date(2026, 12, 31), 1.0, 1000.0),
        _quarter(date(2027, 3, 31), 1.1, None),
        _quarter(date(2027, 6, 30), 1.2, None),
    )
    out = _apply(replace(_figures(), quarter_estimates=quarters))
    assert "The consensus EPS for the quarter to 31 Dec 2026 is read ÷2." in _sentence(out)
    assert (
        "The consensus EPS for the quarters ending 31 Mar 2027 and 30 Jun 2027 has no net-income "
        "mean and is read as stored." in _sentence(out)
    )


def test_a_count_matching_neither_basis_is_read_as_stored() -> None:
    """A count of 1,000 against a quote count of 5,000: neither 1,000 nor 1,100 lies within 15%.
    An 11-for-10 split takes "An"."""
    small = SplitRow(date(2026, 10, 15), 11.0, 10.0)
    out = _apply(_figures(), splits=(small,), market_cap=5000.0 * 50)
    assert out.figures == _figures() and out.notes == {} and out.estimate_methods == {}
    assert _sentence(out) == (
        "An 11-for-10 split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The diluted count matches neither basis of the quote's count, so the statements are "
        "read as stored. The closes and the quote are FMP's, already on it."
    )


def test_without_a_diluted_count_the_statements_and_the_consensus_are_read_as_stored() -> None:
    """No count D: no test of the statements, and no P or S for the consensus, so a row implying
    the pre-split count stands and a row without a mean goes unnamed."""
    rows = (_annual(2026, 4.2, 4200.0), _annual(2027, 4.4, None))
    figures = replace(_figures(), shares_diluted=None, annual_estimates=rows)
    out = _apply(figures)
    assert out.figures == figures and out.notes == {} and out.estimate_methods == {}
    assert _sentence(out) == (
        "A 2-for-1 split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "No diluted count is on file, so the statements and the consensus are read as stored. "
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
    assert (
        "The diluted count lies within the tolerance of the quote's count on both bases, so the "
        "statements are read as stored." in _sentence(out)
    )


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
    # the figure observed before the split is noted under its DATA input; the later one is not
    assert out.notes["gf_eps_ttm"] == "÷2 for the 2-for-1 split of 15 Oct 2026"
    assert out.estimate_methods["gf_eps_ttm"] == "split-scaled"
    assert set(out.notes) == set(out.estimate_methods) == {*STATEMENT_KEYS, "gf_eps_ttm"}
    assert "GuruFocus's EPS observed 10 Oct 2026 is read ÷2." in _sentence(out)
    assert "GuruFocus's EPS observed 20 Oct 2026" not in _sentence(out)


def test_a_reverse_split_multiplies_the_per_share_figures() -> None:
    reverse = SplitRow(date(2026, 10, 15), 1.0, 10.0)
    figures = _figures(count=1000.0, eps=4.0, street=4.2)
    out = _apply(figures, splits=(reverse,), market_cap=100.0 * 50)
    f = out.figures
    assert f.trailing is not None
    assert (f.shares_diluted, f.trailing.eps_diluted) == (100.0, 40.0)
    assert f.street_ttm_eps == pytest.approx(42.0)
    assert _sentence(out).startswith(
        "A 1-for-10 reverse split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The diluted count (×0.1), the trailing EPS and the street actuals (÷0.1 on the quarters "
        "to 30 Sep 2026)"
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


def _acme_split(store: Store, **payloads: Any) -> sqlite3.Connection:
    """ACME split 2-for-1 on 2026-10-15, its quote at $25 on 208 m shares."""
    split = {"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1}
    return store(**bodies(), splits=[split], quote=_quote(25.0, 208 * M), **payloads)


def test_build_inputs_reads_a_pending_split(store: Store) -> None:
    """ACME split 2-for-1 on 2026-10-15, after its newest quarter (30 Sep 2026) and before its
    quote (30 Oct 2026); the quote shows 208 m shares against 104 m stored, so the statements
    are pre-split and scale; the fixture's consensus rows imply 100 m, within 15% of 104 m,
    and scale; the GuruFocus figures, observed at the fetch (1 Nov 2026), stand. The fixture's
    three consensus quarters make no NTM window, so the NTM EPS is unmarked."""
    inputs = build(_acme_split(store))
    assert inputs.shares_diluted == pytest.approx(208 * M)
    assert inputs.trailing is not None
    # the four trailing quarters, 101 m to 104 m shares, each × 2 within 15% of 208 m: all halve
    assert inputs.trailing.eps_diluted == pytest.approx(0.95)  # 1.90 halved
    assert inputs.street_ttm_eps == pytest.approx(1.05)  # 2.10 halved
    assert inputs.notes["eps_ttm"] == "÷2 for the 2-for-1 split of 15 Oct 2026"
    # each implies 100 m, within 15% of 104 m
    assert [a.eps for a in inputs.annual_estimates] == pytest.approx([1.0, 1.1, 1.2])
    assert [q.eps for q in inputs.quarter_estimates] == pytest.approx([0.26, 0.27, 0.28])
    assert inputs.gf_eps_ttm == 6.11
    assert inputs.input_flags[-1].code == "split-pending"  # after the statements' flags
    marked = {name for name, method in inputs.estimate_methods.items() if method == "split-scaled"}
    assert marked == STATEMENT_KEYS
    assert inputs.notes["shares_diluted"] == "×2 for the 2-for-1 split of 15 Oct 2026"
    assert inputs.notes["street_ttm_eps"] == "÷2 for the 2-for-1 split of 15 Oct 2026"
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
    """The DATA inputs that hold a scaled figure read as estimates under ``split-scaled`` with the
    split note: the count, the trailing EPS, the street EPS and, since the NTM quarters scaled,
    the NTM EPS. Four consensus quarters (each implying 100 m) give a full NTM window, so the row
    is valued. The GuruFocus figures, observed after the split, read as observed."""
    conn = _acme_split(store, **{"estimates-quarter": estimates_quarter()})
    result = value_company(build(conn), DECILES, load_policy(), TODAY)
    assert result.refusal is None
    assert "split-pending" in [f.code for f in result.flags]
    tagged = {i.name: i for i in result.inputs}
    split = "the 2-for-1 split of 15 Oct 2026"
    for name, note in (
        ("shares_diluted", f"×2 for {split}"),
        ("eps_ttm", f"÷2 for {split}"),
        ("street_ttm_eps", f"÷2 for {split}"),
        ("ntm_eps", f"the consensus quarters to 30 Sep 2027 ÷2 for {split}"),
    ):
        found = tagged[name]
        assert (found.kind, found.estimate_method, found.note) == (
            "estimate",
            "split-scaled",
            note,
        ), name
    for name in ("gf_eps_ttm", "gf_eps_without_nri"):
        assert (tagged[name].kind, tagged[name].estimate_method) == ("observed", None), name
    assert tagged["statements"].estimate_method is None  # the count of fiscal years, unscaled


def test_assembly_reads_the_trailing_periods(store: Store) -> None:
    """The four trailing quarters, oldest first, each with its own EPS and count; on the
    fiscal-year fallback, the one year with its own."""
    stated = statements_for(store(**bodies()), "ACME", "US", load_tax_table(), TODAY)
    assert [(p.end, p.shares_diluted) for p in stated.trailing_periods] == [
        (end, (100 + i) * M) for i, end in enumerate(QUARTERS) if i > 0
    ]
    eps = [p.eps_diluted for p in stated.trailing_periods]
    assert eps == pytest.approx([0.46, 0.47, 0.48, 0.49])
    assert stated.shares_diluted == 104 * M  # the newest quarter's


def test_assembly_reads_the_fiscal_year_on_the_fallback(store: Store, clock: Clock) -> None:
    gap = (QUARTERS[0], QUARTERS[1], QUARTERS[3], QUARTERS[4])  # not consecutive
    conn = store(**bodies(quarters=gap))
    stated = statements_for(conn, "ACME", "US", load_tax_table(), TODAY)
    (year,) = stated.trailing_periods
    assert (year.end, year.shares_diluted) == (date(2025, 12, 31), 100 * M)
    assert year.eps_diluted == pytest.approx(1.5 + 0.15 * 11)
    assert stated.shares_diluted == 104 * M  # the newest quarter's still (4.2)


def test_a_split_within_the_trailing_quarters_scales_the_older_ones() -> None:
    """(a) A split between the second and the third trailing quarter: the older two read 1,000
    shares, the newer two and the quote 2,000. The newest quarter postdates the split, so the
    count stands; the older two read pre-split against it and halve, the newer stand."""
    figures = _figures(count=2000.0, counts=(1000.0, 1000.0, 2000.0, 2000.0))
    out = _apply(figures, splits=(WITHIN,))
    f = out.figures
    assert f.shares_diluted == 2000.0
    assert [p.eps_diluted for p in f.periods] == [0.5, 0.5, 1.0, 1.0]
    assert f.trailing is not None and f.trailing.eps_diluted == 3.0
    assert [eps for _, eps in f.street_actuals] == pytest.approx([0.525, 0.525, 1.05, 1.05])
    assert f.street_ttm_eps == pytest.approx(3.15)
    split = "the 2-for-1 split of 15 Apr 2026"
    assert out.notes == {
        "eps_ttm": f"÷2 on 2 of 4 quarters for {split}",
        "street_ttm_eps": f"÷2 on 2 of 4 quarters for {split}",
    }
    assert out.estimate_methods == dict.fromkeys(("eps_ttm", "street_ttm_eps"), "split-scaled")
    assert _sentence(out) == (
        "A 2-for-1 split of 15 Apr 2026 falls after the quarter ending 31 Mar 2026. "
        "The trailing EPS and the street actuals (÷2 on the quarters ending 31 Dec 2025 to "
        "31 Mar 2026) are read on the post-split basis. The closes and the quote are FMP's, "
        "already on it."
    )


def test_a_split_within_the_trailing_quarters_leaves_restated_quarters_alone() -> None:
    """FMP restated the older two: every quarter reads 2,000, nothing scales, the note still
    fires while a trailing quarter predates the split, and the consensus, which follows the newest
    statement, is not tested."""
    rows = (_annual(2027, 4.2, 4200.0),)
    figures = replace(_figures(count=2000.0, eps=2.0, street=2.1), annual_estimates=rows)
    out = _apply(figures, splits=(WITHIN,))
    assert out.figures == figures and out.notes == {}
    assert _sentence(out) == (
        "A 2-for-1 split of 15 Apr 2026 falls after the quarter ending 31 Mar 2026. "
        "FMP's statements and street actuals already read on the post-split basis. The closes and "
        "the quote are FMP's, already on it."
    )


def test_a_split_after_every_trailing_quarter_scales_all_four_through_the_periods() -> None:
    """(b) Four quarters on 1,000 shares, a split after the newest, the quote at 2,000: each
    quarter halves and the count doubles (the rule before the periods, now through them)."""
    out = _apply(_figures())
    assert [p.eps_diluted for p in out.figures.periods] == [0.5] * 4
    assert [eps for _, eps in out.figures.street_actuals] == pytest.approx([0.525] * 4)
    assert out.figures.shares_diluted == 2000.0
    assert "(÷2 on the quarters to 30 Sep 2026)" in _sentence(out)


def test_restated_newest_and_pre_split_older_quarters_scale_the_older_alone() -> None:
    """META's 10-K case: a split after the newest quarter, which FMP read post-split (2,000, the
    quote's count), the older three still on 1,000: the count stands and the three halve."""
    figures = _figures(count=2000.0, counts=(1000.0, 1000.0, 1000.0, 2000.0))
    out = _apply(figures)
    assert out.figures.shares_diluted == 2000.0
    assert [p.eps_diluted for p in out.figures.periods] == [0.5, 0.5, 0.5, 1.0]
    assert out.notes["eps_ttm"] == "÷2 on 3 of 4 quarters for the 2-for-1 split of 15 Oct 2026"
    assert "shares_diluted" not in out.notes
    assert _sentence(out).startswith(
        "A 2-for-1 split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The trailing EPS and the street actuals (÷2 on the quarters ending 31 Dec 2025 to "
        "30 Jun 2026) are read on the post-split basis."
    )


def _year(count: float, eps: float = 4.0) -> SplitFigures:
    """The fiscal-year fallback: one year ending 31 Dec 2025 on ``count`` shares; no street
    actuals."""
    end = date(2025, 12, 31)
    return replace(
        _figures(count=count, eps=eps),
        trailing=_trailing(eps, end, quarters=1),
        periods=(TrailingPeriod(end, eps, count),),
        street_actuals=(),
    )


def test_the_fiscal_year_fallback_is_read_on_the_years_own_count() -> None:
    """(c) One fiscal year on 1,000 shares, a split after its end: against a quote of 2,000 the
    year's EPS halves and the count doubles; against 1,000 both stand, post-split."""
    end = date(2025, 12, 31)
    out = _apply(_year(1000.0), end=end)
    assert out.figures.shares_diluted == 2000.0
    assert out.figures.trailing is not None and out.figures.trailing.eps_diluted == 2.0
    assert out.figures.periods[0].eps_diluted == 2.0
    assert out.figures.street_ttm_eps is None
    assert _sentence(out).startswith(
        "A 2-for-1 split of 15 Oct 2026 falls after the newest statement (31 Dec 2025). "
        "The diluted count (×2) and the trailing EPS (÷2 on the fiscal year) are read on the "
        "post-split basis."
    )
    stands = _apply(_year(1000.0), market_cap=1000.0 * 50, end=end)
    assert stands.figures == _year(1000.0)
    assert "FMP's statements and street actuals already read on the post-split basis." in (
        _sentence(stands)
    )


def test_the_fallback_year_is_judged_by_its_own_count_not_the_newest_quarters() -> None:
    """The diluted count is the newest quarter's (4.2), here 2,000 from a quarter after the
    split; the year itself reads 1,000. The count stands against the quote's 2,000 and the year,
    by its own count, halves."""
    figures = replace(_year(1000.0), shares_diluted=2000.0)
    out = _apply(figures, end=date(2025, 12, 31))
    assert out.figures.shares_diluted == 2000.0
    assert out.figures.trailing is not None and out.figures.trailing.eps_diluted == 2.0
    assert "shares_diluted" not in out.notes
    assert "The trailing EPS (÷2 on the fiscal year) is read on the post-split basis." in (
        _sentence(out)
    )


def test_a_quarter_without_a_count_is_named_and_read_as_stored() -> None:
    """(d) The quarter ending 31 Mar 2026 has no count: its EPS and actual stand, the other three
    halve."""
    out = _apply(_figures(counts=(1000.0, None, 1000.0, 1000.0)))
    assert [p.eps_diluted for p in out.figures.periods] == [0.5, 1.0, 0.5, 0.5]
    assert out.figures.trailing is not None and out.figures.trailing.eps_diluted == 2.5
    assert out.notes["eps_ttm"] == "÷2 on 3 of 4 quarters for the 2-for-1 split of 15 Oct 2026"
    sentence = _sentence(out)
    assert (
        "The diluted count (×2), the trailing EPS and the street actuals (÷2 on the quarters "
        "ending 31 Dec 2025, 30 Jun 2026 and 30 Sep 2026) are read on the post-split basis."
        in sentence
    )
    assert "The quarter ending 31 Mar 2026 has no share count and is read as stored." in sentence


def test_splits_on_either_side_of_a_quarter_scale_each_period_by_its_own_ratio() -> None:
    """A 2-for-1 within the trailing quarters and a 3-for-2 after them: the older two quarters
    (1,000 shares) read ÷3, the newer two (2,000) ÷1.5, the count ×1.5 against the quote's 3,000."""
    after = SplitRow(date(2026, 10, 15), 3.0, 2.0)
    figures = _figures(count=2000.0, counts=(1000.0, 1000.0, 2000.0, 2000.0))
    out = _apply(figures, splits=(WITHIN, after), market_cap=3000.0 * 50)
    assert out.figures.shares_diluted == 3000.0
    assert [p.eps_diluted for p in out.figures.periods] == pytest.approx([1 / 3] * 2 + [2 / 3] * 2)
    assert out.notes["eps_ttm"] == (
        "÷3 on 2 of 4 quarters and ÷1.5 on 2 of 4 quarters for the 2-for-1 split of 15 Apr 2026 "
        "and the 3-for-2 split of 15 Oct 2026"
    )
    assert out.notes["shares_diluted"] == "×1.5 for the 3-for-2 split of 15 Oct 2026"
    assert _sentence(out).startswith(
        "A 2-for-1 split of 15 Apr 2026 and a 3-for-2 split of 15 Oct 2026 fall after the quarter "
        "ending 31 Mar 2026. The diluted count (×1.5), the trailing EPS and the street actuals (÷3 "
        "on the quarters ending 31 Dec 2025 to 31 Mar 2026 and ÷1.5 on the quarters ending "
        "30 Jun 2026 to 30 Sep 2026) are read on the post-split basis."
    )


def test_pre_split_quarters_without_a_trailing_sum_scale_nothing_and_say_so() -> None:
    figures = _figures(count=2000.0, counts=(1000.0, 1000.0, 2000.0, 2000.0))
    *older, newest = figures.periods
    figures = replace(
        figures,
        trailing=_trailing(None),
        periods=(*older, replace(newest, eps_diluted=None)),
        street_actuals=(),
    )
    out = _apply(figures, splits=(WITHIN,))
    assert out.figures.trailing == _trailing(None) and out.notes == {}
    assert "No trailing EPS or street actuals are on file to scale." in _sentence(out)


def test_a_fiscal_year_without_a_count_is_read_as_stored() -> None:
    end = date(2025, 12, 31)
    figures = replace(_year(1000.0), periods=(TrailingPeriod(end, 4.0, None),))
    out = _apply(figures, end=end)
    assert out.figures.shares_diluted == 2000.0
    assert out.figures.trailing is not None and out.figures.trailing.eps_diluted == 4.0
    assert (
        "The diluted count (×2) is read on the post-split basis. The fiscal year has no share "
        "count and is read as stored." in _sentence(out)
    )


def _split_inputs(inputs: CompanyInputs) -> CompanyInputs:
    """``inputs`` after a 2-for-1 split on 15 Oct 2026 that FMP has restated nowhere but the
    quote and the closes: the price halved, the market cap kept (so the quote reads twice the
    count), every stored count and per-share figure on the old basis and the rule applied."""
    assert inputs.trailing is not None and inputs.shares_diluted is not None
    t, count = inputs.trailing, inputs.shares_diluted
    assert t.eps_diluted is not None
    street = inputs.street_ttm_eps
    figures = SplitFigures(
        shares_diluted=count,
        trailing=t,
        periods=tuple(TrailingPeriod(end, t.eps_diluted / 4, count) for end in ENDS),
        street_actuals=() if street is None else tuple((end, street / 4) for end in ENDS),
        gf_eps_ttm=inputs.gf_eps_ttm,
        gf_eps_ttm_as_of=date(2026, 10, 10),
        gf_eps_without_nri=inputs.gf_eps_without_nri,
        gf_eps_without_nri_as_of=date(2026, 10, 10),
        quarter_estimates=inputs.quarter_estimates,
        annual_estimates=inputs.annual_estimates,
    )
    assert inputs.price is not None and inputs.market_cap is not None
    out = apply_splits(
        figures,
        (SPLIT,),
        statement_end=t.period_end,
        price_date=inputs.price_date,
        quote_market_cap=inputs.market_cap,
        quote_price=inputs.price / 2,
        tolerance=0.15,
    )
    f = out.figures
    assert f.shares_diluted == 2 * count  # the rule read the stored count pre-split
    return replace(
        inputs,
        price=inputs.price / 2,
        shares_diluted=f.shares_diluted,
        trailing=f.trailing,
        street_ttm_eps=f.street_ttm_eps,
        gf_eps_ttm=f.gf_eps_ttm,
        gf_eps_without_nri=f.gf_eps_without_nri,
        quarter_estimates=f.quarter_estimates,
        annual_estimates=f.annual_estimates,
        closes=tuple((day, close / 2) for day, close in inputs.closes),
        input_flags=(*inputs.input_flags, *(() if out.flag is None else (out.flag,))),
    )


@pytest.mark.parametrize(
    ("company", "route"),
    [
        (engine_companies.mature_growth_inputs, "mature-growth"),
        (engine_companies.mature_stable_inputs, "mature-stable"),
    ],
    ids=["mature-growth", "mature-stable"],
)
def test_a_split_leaves_the_price_to_value_unchanged(
    company: Callable[[], CompanyInputs], route: str
) -> None:
    """(f) The company unsplit, and split 2-for-1 with every stored figure on the old basis: the
    rule puts each on the new one, so the price ÷ value is the same. The consensus quarters carry
    a net-income mean, so the rule can test them."""
    base = company()
    assert base.shares_diluted is not None
    quarters = tuple(
        replace(q, net_income=q.eps * base.shares_diluted)
        for q in base.quarter_estimates
        if q.eps is not None
    )
    unsplit = replace(base, quarter_estimates=quarters)
    split = _split_inputs(unsplit)
    deciles, policy = engine_companies.universe_deciles(), load_policy()
    before = value_company(unsplit, deciles, policy, TODAY)
    after = value_company(split, deciles, policy, TODAY)
    assert (before.route, after.route) == (route, route)
    assert before.price_to_value is not None and after.price_to_value is not None
    assert after.price_to_value == pytest.approx(before.price_to_value, abs=1e-9)
    assert before.value is not None and after.value is not None
    assert after.value == pytest.approx(before.value / 2, rel=1e-9)
