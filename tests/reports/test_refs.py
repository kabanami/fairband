"""The references a report cites (spec 2026-11-06 Tier 2, 13.2), each form resolved on the
``snapshots`` fixture of ``conftest.py``: AAPL (the Mature Growth golden renamed, a price of $150)
with ACME's synthetic statements, consensus, closes and ACME as its mature peer; AAL, refused."""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest
from refresh.synthetic import NOW, bodies
from support.engine_companies import (
    decline_inputs,
    fx_inputs,
    mature_growth_inputs,
    on_quarter_sheet,
    universe_deciles,
    with_minority,
)
from support.payloads import store_payloads
from support.web import TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import review_company
from fairband.engine.route import reprice, value_company
from fairband.engine.secondary import Drivers, Part, secondary_value
from fairband.engine.sensitivity import SensitivityGrid
from fairband.policy import Policy
from fairband.policy.tax import load_tax_table
from fairband.refresh.inputs_statements import statements_for, stored_quarters
from fairband.reports.check import WRONG_UNIT, check_sections
from fairband.reports.filing_report import row_ref, served
from fairband.reports.refs import (
    Resolved,
    Resolver,
    resolve,
    rests_on,
    same_snapshot,
    unit_of,
)
from fairband.reports.tables import financial_tables
from fairband.store.guidance import insert_guidance
from fairband.store.ledger import Writer
from fairband.store.multiples import log_multiples
from fairband.store.research import add_finding
from fairband.store.reviews import insert_review
from fairband.store.secondary import insert_derivation, insert_secondary
from fairband.store.sensitivities import insert_sensitivity
from fairband.store.snapshots import insert_snapshot, snapshot_row
from fairband.store.vendor import record_response

M = 1_000_000
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")


def _resolve(conn: sqlite3.Connection, ref: str, policy: Policy) -> Resolved | None:
    return resolve(conn, "AAPL", ref, policy)


def test_snapshot_refs(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    sid = snapshots["AAPL"]
    stored = snapshot_row(conn, sid)
    assert stored is not None
    result, levels = stored.result, stored.result.levels
    assert result.value is not None and levels is not None
    s = f"snapshot:{sid}"
    expected = {
        f"{s}/value": (result.value, "per-share"),
        f"{s}/price": (150.0, "per-share"),
        f"{s}/price_to_value": (result.price_to_value, "multiple"),
        f"{s}/levels/buy": (levels.buy, "per-share"),
        f"{s}/levels/trim": (levels.trim, "per-share"),
        f"{s}/inputs/price": (150.0, "per-share"),
        f"{s}/inputs/revenue_ttm": (22_800 * M, "currency"),
        f"{s}/inputs/eps_ttm": (5.3, "per-share"),
        f"{s}/inputs/aggregate_roic": (result.intermediates["roic"]["aggregate"], "percent"),
        f"{s}/inputs/shares_diluted": (1_000 * M, "count"),
        f"{s}/inputs/moat_class": ("Wide", None),  # a word input: the word leading its note
        f"{s}/inputs/runway_years": (20.0, "years"),
        f"{s}/inputs/moat_score": (8.0, "score"),
        f"{s}/intermediates/belief/rate": (0.063, None),
        f"{s}/intermediates/growth_rates/0": (result.intermediates["growth_rates"][0], None),
        f"{s}/phase/phase": ("Mature Growth", None),
        f"{s}/phase/growth_3y": (result.phase.growth_3y, "percent"),
        f"{s}/phase/years_used": (11.0, "count"),
    }
    prices = {f"{s}/price", f"{s}/inputs/price"}  # a share price, written to cents
    for ref, (value, unit) in expected.items():
        resolved = Resolved(value, unit, None, sid, price=ref in prices)
        assert _resolve(conn, ref, policy) == resolved, ref
    assert _resolve(conn, f"{s}/inputs/dividends_ttm", policy) == Resolved(
        -1_000 * M, "currency", None, sid, outflow=True
    )
    for ref in (
        f"snapshot:{snapshots['AAL']}/value",  # another company's
        "snapshot:999/value",
        f"{s}/levels/nope",
        f"{s}/inputs/no_such_input",
        f"{s}/intermediates/roic",  # a table, not a figure
        f"{s}/intermediates/no/such/path",
        f"{s}/phase/checks",
        f"{s}/value/extra",
        "snapshot:x/value",
        f"{s}",
        "nosuchform:1/value",
        "no colon",
    ):
        assert _resolve(conn, ref, policy) is None, ref


@pytest.mark.parametrize("record", ["99999999999999999999", "²"])
@pytest.mark.parametrize(
    "form",
    [
        "snapshot:{}/value",
        "review:{}/value",
        "secondary:{}/value",
        "sensitivity:{}/0/0",
        "finding:{}",
        "guidance:{}/midpoint",
        "derived:{}",
        "response:{}/0/content",
        "filing:{}/S/1/0",
    ],
)
def test_an_id_no_row_can_have_names_nothing(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int], form: str, record: str
) -> None:
    """A made-up id past SQLite's integers, or a digit that is not an ASCII one, names no record:
    the ref resolves to nothing, as an unknown id does, and nothing is raised, so a report that
    cites it is refused for an unresolved reference and the server does not fail."""
    ref = form.format(record)
    resolver = Resolver(conn, "AAPL", policy)
    assert resolver.resolve(ref) is None
    assert resolver.describe(ref) == ref
    assert rests_on(conn, ref) is None


def test_a_digit_that_is_not_ascii_is_no_index(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """``str.isdigit`` takes "²" for a digit and ``int`` does not: a bridge line or a list item
    numbered so is absent, on a record that exists."""
    review_id = _review_id(conn, policy, snapshots["AAPL"])
    assert _resolve(conn, f"review:{review_id}/bridge/1/delta", policy) is not None
    assert _resolve(conn, f"review:{review_id}/bridge/²/delta", policy) is None
    stored = record_response(
        conn, "fmp", "news", {"symbol": "AAPL"}, "AAPL", 200, '[{"shares": 5}]', None, NOW
    )
    assert _resolve(conn, f"response:{stored}/0/shares", policy) == Resolved(5.0, None, None, None)
    assert _resolve(conn, f"response:{stored}/²/shares", policy) is None


def test_a_refused_snapshot_resolves_to_no_value(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    aal = snapshots["AAL"]
    assert resolve(conn, "AAL", f"snapshot:{aal}/value", policy) == Resolved(
        None, "per-share", None, aal
    )


def _review_id(conn: sqlite3.Connection, policy: Policy, snapshot_id: int) -> int:
    """AAPL's review under a belief of 8%, stored on ``snapshot_id``."""
    inputs = replace(mature_growth_inputs(), symbol="AAPL")
    deciles = universe_deciles()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    belief = Override(7, "growth.belief", 0.08, "agent", "claude-opus-5-5", NOW, "guidance raised")
    review = review_company(inputs, deciles, policy, TODAY, [belief], mechanical)
    return insert_review(conn, review, "AAPL", snapshot_id, None, clock=lambda: NOW)


def test_review_refs(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    review_id = _review_id(conn, policy, snapshots["AAPL"])
    mechanical = snapshot_row(conn, snapshots["AAPL"])
    assert mechanical is not None and mechanical.value is not None
    r = f"review:{review_id}"
    value = _resolve(conn, f"{r}/value", policy)
    assert value is not None and isinstance(value.value, float)
    assert (value.unit, value.period, value.snapshot_id) == ("per-share", None, snapshots["AAPL"])
    delta = _resolve(conn, f"{r}/bridge/1/delta", policy)
    assert delta is not None and delta.unit == "per-share"
    assert delta.value == pytest.approx(value.value - mechanical.value, abs=1e-9)
    old = _resolve(conn, f"{r}/bridge/1/old", policy)
    assert old == Resolved(0.063, "percent", None, snapshots["AAPL"])
    assert _resolve(conn, f"{r}/bridge/1/new", policy) == Resolved(
        0.08, "percent", None, snapshots["AAPL"]
    )
    buy = _resolve(conn, f"{r}/levels/buy", policy)
    assert buy is not None and buy.unit == "per-share" and buy.value != mechanical.buy_level
    # the review's intermediates, by their path as a snapshot's are: the overridden belief, and
    # the growth the price needs under the review (a belief override moves the value, not it)
    belief = _resolve(conn, f"{r}/intermediates/belief/rate", policy)
    assert belief == Resolved(0.08, None, None, snapshots["AAPL"])
    growth = _resolve(conn, f"{r}/intermediates/implied_growth", policy)
    assert growth is not None and isinstance(growth.value, float) and growth.unit is None
    assert growth.value == pytest.approx(mechanical.result.intermediates["implied_growth"])
    for ref in (
        f"{r}/bridge/0/delta",
        f"{r}/bridge/2/delta",
        f"{r}/bridge/1/tag",
        f"{r}/intermediates",
        f"{r}/intermediates/no_such",
        f"{r}/intermediates/belief",  # a table, not a figure
        "review:99/value",
    ):
        assert _resolve(conn, ref, policy) is None, ref


def test_a_company_in_another_currency_resolves_its_rate_and_names_it(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-10 7.2 and 7.4 on FXCO, the company in SEK at 8.0 a dollar, here an ADR of five
    ordinary shares: an input in SEK resolves to the read's unit as one in USD does (a total
    ``currency``, a figure a share ``per-share``), so a bridge line of an override in SEK does too;
    the rate is a figure with no unit, the ADR ratio a multiple, the differential a percent; and
    the references list names the rate, its date, the currency, the differential and the value in
    the currency in words."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    inputs = replace(fx_inputs(), is_adr=True, adr_ratio=5.0)
    mechanical = value_company(inputs, universe_deciles(), policy, TODAY)
    sid = insert_snapshot(conn, mechanical, aapl.refresh_id, clock=lambda: NOW)
    outside = Override(9, "value.outside", 40.0, "agent", "claude-opus-5-5", NOW, "a stake")
    review = review_company(inputs, universe_deciles(), policy, TODAY, [outside], mechanical)
    review_id = insert_review(conn, review, "FXCO", sid, None, clock=lambda: NOW)
    resolver = Resolver(conn, "FXCO", policy)
    s = f"snapshot:{sid}"
    for ref, value, unit in (
        (f"{s}/inputs/fx_rate", 8.0, None),
        (f"{s}/inputs/adr_ratio", 5.0, "multiple"),
        (f"{s}/inputs/inflation_differential", 0.02, "percent"),
        (f"{s}/inputs/market_cap", 40_000e6, "currency"),
        (f"{s}/inputs/eps_ttm", 42.4, "per-share"),
        (f"{s}/intermediates/fx_rate", 8.0, None),
        (f"review:{review_id}/bridge/1/new", 40.0, "per-share"),
    ):
        found = resolver.resolve(ref)
        assert found is not None, ref
        assert (found.value, found.unit) == (pytest.approx(value), unit), ref
    assert resolver.resolve(f"{s}/intermediates/currency") == Resolved("SEK", None, None, sid)
    priced = "priced 31 Oct 2026"
    for path, words in (
        ("intermediates/value_in_currency", "the value a share in the reporting currency"),
        (
            "intermediates/fx_rate",
            "the exchange rate, units of the reporting currency per US dollar",
        ),
        ("inputs/fx_rate", "the exchange rate, units of the reporting currency per US dollar"),
        ("intermediates/fx_date", "the exchange rate's date"),
        ("intermediates/currency", "the reporting currency"),
        (
            "intermediates/inflation_differential",
            "the inflation differential against the US dollar",
        ),
        ("inputs/inflation_differential", "the inflation differential against the US dollar"),
        ("inputs/adr_ratio", "the ADR ratio, ordinary shares per ADS"),
    ):
        assert resolver.describe(f"{s}/{path}") == f"snapshot {sid}, {words}, {priced}", path
    assert resolver.describe(f"review:{review_id}/intermediates/fx_rate") == (
        f"review {review_id}, the exchange rate, units of the reporting currency per US dollar"
    )


def test_the_ten_year_median_margins_resolve_and_read_in_words(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-13 11: the playbook's cycle formula cites the ten-year median net margin as
    `snapshot:<id>/intermediates/margin_history/net/median`. AAPL's series with net income at
    three quarters of each year's operating income: the operating median is 23.25% and the net
    median 17.4375%, each over 10 years. The references list names each in words. On the fixture's
    own snapshot, whose series has no net income, the net margin is absent and its ref resolves
    to nothing, raising nothing."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    base = replace(mature_growth_inputs(), symbol="AAPL")
    assert all(fy.operating_income is not None for fy in base.series)
    series = tuple(
        replace(fy, net_income=0.75 * (fy.operating_income or 0.0)) for fy in base.series
    )
    mechanical = value_company(replace(base, series=series), universe_deciles(), policy, TODAY)
    sid = insert_snapshot(conn, mechanical, aapl.refresh_id, clock=lambda: NOW)
    resolver = Resolver(conn, "AAPL", policy)
    s = f"snapshot:{sid}/intermediates/margin_history"
    priced = "priced 30 Oct 2026"
    for path, value, words in (
        ("net/median", 0.174375, "the ten-year median net margin"),
        ("operating/median", 0.2325, "the ten-year median operating margin"),
        ("net/years", 10.0, "the fiscal years behind the ten-year median net margin"),
        ("operating/years", 10.0, "the fiscal years behind the ten-year median operating margin"),
    ):
        found = resolver.resolve(f"{s}/{path}")
        assert found is not None, path
        assert (found.value, found.snapshot_id) == (pytest.approx(value), sid), path
        assert resolver.describe(f"{s}/{path}") == f"snapshot {sid}, {words}, {priced}", path
    bare = f"snapshot:{snapshots['AAPL']}/intermediates/margin_history"
    assert resolver.resolve(f"{bare}/operating/median") is not None
    assert resolver.resolve(f"{bare}/net/median") is None
    assert resolver.resolve(f"{bare}/net/years") is None
    assert resolver.resolve(bare) is None  # a record, not a figure


def test_the_newest_sheet_and_the_floor_s_lines_resolve_and_read_in_words(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-13 12.2: the Decline row reads its floor from the newest balance sheet, here
    the quarter of 30 Sep 2026 with current assets of $900 m and liabilities of $500 m, and
    records the sheet's period beside debt and cash. The references list names each in words."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    dc = on_quarter_sheet(replace(decline_inputs(), symbol="AAPL"), 900e6, 500e6)
    mechanical = value_company(dc, universe_deciles(), policy, TODAY)
    assert mechanical.route == "decline"
    sid = insert_snapshot(conn, mechanical, aapl.refresh_id, clock=lambda: NOW)
    resolver = Resolver(conn, "AAPL", policy)
    priced = "priced 30 Oct 2026"
    for path, value, words in (
        (
            "inputs/floor_current_assets",
            900e6,
            "the total current assets the liquidation floor reads",
        ),
        (
            "inputs/floor_total_liabilities",
            500e6,
            "the total liabilities the liquidation floor reads",
        ),
        (
            "intermediates/balance_sheet/label",
            "fiscal 2026 Q3",
            "the period of the newest balance sheet",
        ),
        (
            "intermediates/balance_sheet/period_end",
            "2026-09-30",
            "the period end of the newest balance sheet",
        ),
    ):
        ref = f"snapshot:{sid}/{path}"
        found = resolver.resolve(ref)
        assert found is not None and (found.value, found.snapshot_id) == (value, sid), path
        assert resolver.describe(ref) == f"snapshot {sid}, {words}, {priced}", path
    assert resolver.describe(f"snapshot:{sid}/intermediates/balance_sheet/quarterly") == (
        f"snapshot {sid}, whether the newest balance sheet is a quarter's, {priced}"
    )
    # the fiscal year's lines Z″ and F read keep their own words
    assert resolver.describe(f"snapshot:{sid}/inputs/total_liabilities") == (
        f"snapshot {sid}, the total liabilities, {priced}"
    )


def test_the_minority_interest_resolves_and_reads_in_words(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-13 13: a Decline row whose newest balance sheet holds a minority interest of
    $50 m cites the line as an input and carries the figure the route subtracts; the references
    list names each in words."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    dc = with_minority(replace(decline_inputs(), symbol="AAPL"), 50e6)
    mechanical = value_company(dc, universe_deciles(), policy, TODAY)
    assert mechanical.route == "decline"
    sid = insert_snapshot(conn, mechanical, aapl.refresh_id, clock=lambda: NOW)
    resolver = Resolver(conn, "AAPL", policy)
    for path, words in (
        ("inputs/minority_interest", "the minority interest on the newest balance sheet"),
        ("intermediates/minority_interest", "the minority interest the route subtracts"),
    ):
        ref = f"snapshot:{sid}/{path}"
        found = resolver.resolve(ref)
        assert found is not None and (found.value, found.snapshot_id) == (50e6, sid), path
        assert resolver.describe(ref) == f"snapshot {sid}, {words}, priced 30 Oct 2026", path


def test_the_anchor_s_source_resolves_and_reads_in_words(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-13 9a: the playbook has an agent read where year 1 came from at
    `snapshot:<id>/intermediates/anchor/source`. The Mature Growth golden with fiscal 2027's Q2
    on 3 analysts and the quarter that completes fiscal 2027 on file at 1.60: fiscal 2027's
    quarters sum to 6.10 against its annual 6.00 on 12 analysts, so year 1 is the periods' 5.90
    corrected by 3/4 of −0.10. The references list names the source, the periods' sum and each
    figure of the correction in words."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    base = replace(mature_growth_inputs(), symbol="AAPL")
    q = base.quarter_estimates
    fifth = replace(q[3], period_end=date(2027, 12, 31), fiscal_period="Q4", eps=1.60)
    thin = replace(base, quarter_estimates=(*q[:2], replace(q[2], analysts=3), *q[3:], fifth))
    mechanical = value_company(thin, universe_deciles(), policy, TODAY)
    sid = insert_snapshot(conn, mechanical, aapl.refresh_id, clock=lambda: NOW)
    resolver = Resolver(conn, "AAPL", policy)
    s = f"snapshot:{sid}/intermediates/anchor"
    last = "the last fiscal year the NTM window reaches"
    for path, value, words in (
        (
            "source",
            "annual",
            "whether the NTM EPS is the periods' sum or corrected by the annual consensus",
        ),
        ("periods_sum", pytest.approx(5.90), "the sum of the NTM window's EPS means"),
        ("annual/fiscal_year", 2027.0, last),
        ("annual/eps", 6.00, f"the annual EPS mean of {last}"),
        (
            "annual/analysts",
            12.0,
            "the EPS analysts of the annual consensus that corrects the NTM EPS",
        ),
        (
            "annual/year_sum",
            pytest.approx(6.10),
            f"the sum of the EPS means of the periods of {last}",
        ),
        (
            "annual/share",
            0.75,
            "the NTM window's share of the periods of the last fiscal year it reaches",
        ),
        (
            "annual/correction",
            pytest.approx(-0.075),
            "the correction of the NTM EPS by the annual consensus",
        ),
    ):
        found = resolver.resolve(f"{s}/{path}")
        assert found is not None and (found.value, found.snapshot_id) == (value, sid), path
        assert resolver.describe(f"{s}/{path}") == f"snapshot {sid}, {words}, priced 30 Oct 2026"
    assert resolver.resolve(f"{s}/annual") is None  # a record, not a figure


def _secondary_id(conn: sqlite3.Connection, policy: Policy, snapshot_id: int) -> int:
    """Spec 20.1's one-part path, debt 200, cash 100, 100 shares."""
    part = Part("the business", (100.0, 105.0, 110.25, 115.7625, 121.550625), 0.03, None)
    valuation = secondary_value(
        parts=[part], debt=200.0, cash=100.0, shares=100.0, price=150.0, moat="Wide", policy=policy
    )
    return insert_secondary(
        conn,
        "AAPL",
        snapshot_id,
        [part],
        valuation,
        "the services segment",
        [{"kind": "filing", "ref": "10-K", "note": None}],
        "agent",
        "agent",
        policy.version,
        policy.settings_hash,
        None,
        AGENT,
        NOW,
    )


def test_secondary_refs(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    s = f"secondary:{_secondary_id(conn, policy, sid)}"
    expected = {
        f"{s}/value": (16.8242, "per-share"),
        f"{s}/firm_value": (1782.4206, "currency"),
        f"{s}/equity": (1682.4206, "currency"),
        f"{s}/debt": (200.0, "currency"),
        f"{s}/shares": (100.0, "count"),
        f"{s}/parts/1/pv/1": (91.7431, "currency"),
        f"{s}/parts/1/pv/5": (78.9996, "currency"),
        f"{s}/parts/1/fcff/2": (105.0, "currency"),
        f"{s}/parts/1/terminal_pv": (1356.1592, "currency"),
        f"{s}/parts/1/terminal_growth": (0.03, "percent"),
    }
    for ref, (value, unit) in expected.items():
        found = _resolve(conn, ref, policy)
        assert found is not None, ref
        assert (found.value, found.unit, found.snapshot_id) == (
            pytest.approx(value, abs=1e-4),
            unit,
            sid,
        ), ref
    for ref in (f"{s}/parts/2/pv/1", f"{s}/parts/1/pv/6", f"{s}/parts/1/pv/0", f"{s}/nope"):
        assert _resolve(conn, ref, policy) is None, ref


def _drivers_secondary_id(conn: sqlite3.Connection, policy: Policy, snapshot_id: int) -> int:
    """Spec 20.4's drivers: a trailing revenue of 1,000, the terminal return 12%, debt 200, cash
    100, 50 shares."""
    drivers = Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02)
    valuation = secondary_value(
        drivers=drivers,
        revenue_0=1000.0,
        roic_t=0.12,
        debt=200.0,
        cash=100.0,
        shares=50.0,
        price=150.0,
        moat="Wide",
        policy=policy,
    )
    return insert_secondary(
        conn,
        "AAPL",
        snapshot_id,
        (),
        valuation,
        "the cycle turns",
        [{"kind": "filing", "ref": "10-K", "note": None}],
        "agent",
        "agent",
        policy.version,
        policy.settings_hash,
        None,
        AGENT,
        NOW,
        revenue_0=1000.0,
        roic_t=0.12,
    )


def test_the_secondary_projection_and_grid_refs_resolve(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    s = f"secondary:{_drivers_secondary_id(conn, policy, sid)}"
    expected = {
        f"{s}/value": (39.888938, "per-share"),
        f"{s}/years/1/revenue": (1100.0, "currency"),
        f"{s}/years/2/ebit": (237.6, "currency"),
        f"{s}/years/3/nopat": (187.11, "currency"),
        f"{s}/years/1/reinvestment": (50.0, "currency"),
        f"{s}/years/2/fcff": (134.2, "currency"),
        f"{s}/years/3/pv": (121.549402, "currency"),
        f"{s}/drivers/years": (3.0, "count"),
        f"{s}/drivers/tax_rate": (0.25, "percent"),
        f"{s}/drivers/terminal_growth": (0.02, "percent"),
        f"{s}/drivers/sales_to_capital": (2.0, "multiple"),
        f"{s}/drivers/revenue_growth/2": (0.08, "percent"),
        f"{s}/drivers/operating_margin/3": (0.20, "percent"),
        f"{s}/grid/2/2": (39.888938, "per-share"),  # the centre, the value
        f"{s}/grid/1/1": (44.220636, "per-share"),  # g 1%, r 8%
        f"{s}/terminal_fcff": (159.0435, "currency"),
        f"{s}/terminal": (2272.05, "currency"),
        f"{s}/terminal_pv": (1754.439476, "currency"),
    }
    for ref, (value, unit) in expected.items():
        found = _resolve(conn, ref, policy)
        assert found is not None, ref
        assert (found.value, found.unit, found.snapshot_id) == (
            pytest.approx(value, abs=1e-4),
            unit,
            sid,
        ), ref
    unresolved = (
        "years/9/fcff",  # a three-year record
        "years/0/fcff",
        "years/1/nope",
        "years/1",
        "drivers/revenue_growth",  # a list, not a figure
        "drivers/revenue_growth/4",
        "drivers/tax_rate/1",
        "drivers/nope",
        "grid/4/1",
        "grid/1/0",
        "grid/1",
        "parts/1/pv/1",
    )
    for path in unresolved:
        assert _resolve(conn, f"{s}/{path}", policy) is None, path
    on_parts = f"secondary:{_secondary_id(conn, policy, sid)}"
    for path in ("years/1/fcff", "drivers/years", "drivers/tax_rate", "terminal_fcff", "terminal"):
        assert _resolve(conn, f"{on_parts}/{path}", policy) is None, path
    centre = _resolve(conn, f"{on_parts}/grid/2/2", policy)  # a parts record carries a grid
    assert centre is not None and centre.value == pytest.approx(16.8242, abs=1e-4)
    cites = [
        {"cite": "$0.25", "ref": f"{s}/drivers/tax_rate"},
        {"cite": "25.0%", "ref": f"{s}/drivers/tax_rate"},
    ]
    [finding] = check_sections(
        conn, "AAPL", sid, [{"heading": "Valuation", "parts": cites}], policy
    )
    assert (finding.where, finding.what) == ("section 1, part 1: $0.25", WRONG_UNIT)


def test_sensitivity_refs(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """A cell by its row and its column, each counted from 1; a refused cell holds no value. An
    axis value by its row or its column, in its input's unit, a word axis's word."""
    sid = snapshots["AAPL"]
    grid = SensitivityGrid((0.05, 0.08), (0.10, 0.20, 0.30), ((120.5, None, 140.0),) * 2, None)
    found = insert_sensitivity(
        conn, "AAPL", sid, None, "growth.belief", "return.runway", grid, "v", "h", AGENT, NOW
    )
    theirs = insert_sensitivity(
        conn, "AAL", snapshots["AAL"], None, "phase", "moat.class", grid, "v", "h", AGENT, NOW
    )
    moats = SensitivityGrid((0.05,), ("Wide", "Narrow"), ((120.0, 110.0),), None)
    words = insert_sensitivity(
        conn, "AAPL", sid, None, "growth.belief", "moat.class", moats, "v", "h", AGENT, NOW
    )
    s = f"sensitivity:{found}"
    assert _resolve(conn, f"{s}/1/1", policy) == Resolved(120.5, "per-share", None, sid)
    assert _resolve(conn, f"{s}/2/3", policy) == Resolved(140.0, "per-share", None, sid)
    assert _resolve(conn, f"{s}/1/2", policy) == Resolved(None, "per-share", None, sid)
    assert _resolve(conn, f"{s}/rows/1", policy) == Resolved(0.05, "percent", None, sid)
    assert _resolve(conn, f"{s}/rows/2", policy) == Resolved(0.08, "percent", None, sid)
    assert _resolve(conn, f"{s}/cols/3", policy) == Resolved(0.30, "percent", None, sid)
    assert _resolve(conn, f"sensitivity:{words}/cols/2", policy) == Resolved(
        "Narrow", None, None, sid
    )
    for ref in (
        f"{s}/0/1",
        f"{s}/3/1",
        f"{s}/1/4",
        f"{s}/1",
        f"{s}/1/1/1",
        f"{s}/x/1",
        f"{s}/rows/0",
        f"{s}/rows/3",
        f"{s}/cols/4",
        f"{s}/cols/x",
        f"{s}/rows",
        f"{s}/rows/1/1",
        f"{s}/axes/1",
        f"sensitivity:{theirs}/1/1",  # another company's
        f"sensitivity:{theirs}/rows/1",
        "sensitivity:999/1/1",
        "sensitivity:x/1/1",
    ):
        assert _resolve(conn, ref, policy) is None, ref
    assert rests_on(conn, f"{s}/1/1") == sid
    assert rests_on(conn, f"sensitivity:{theirs}/1/1") == snapshots["AAL"]
    assert rests_on(conn, "sensitivity:999/1/1") is None


def test_fact_refs(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    assert _resolve(conn, "fact:AAPL/revenue/2025", policy) == Resolved(
        2100 * M, "currency", "2025", None
    )
    assert _resolve(conn, "fact:aapl/revenue/2024", policy) == Resolved(
        2000 * M, "currency", "2024", None
    )
    eps = _resolve(conn, "fact:AAPL/eps_diluted/2025", policy)
    assert eps is not None and (eps.unit, eps.period) == ("per-share", "2025")
    assert eps.value == pytest.approx(3.15)
    assert _resolve(conn, "fact:AAPL/total_assets/2025", policy) == Resolved(
        1610 * M, "currency", "2025", None
    )
    for line, outflow in (("capex", True), ("dividends", True), ("cfi", False), ("cff", False)):
        found = _resolve(conn, f"fact:AAPL/{line}/2025", policy)
        assert found is not None and found.outflow is outflow, line
    capex_ttm = _resolve(conn, "fact:AAPL/capex/ttm", policy)
    assert capex_ttm is not None and capex_ttm.outflow
    shares = _resolve(conn, "fact:AAPL/shares_diluted/2025", policy)
    assert shares == Resolved(100 * M, "count", "2025", None)
    # the trailing figures: the last four quarters, as statements_for reads them
    trailing = statements_for(conn, "AAPL", "US", load_tax_table(), date.min).trailing
    assert trailing is not None and trailing.revenue is not None
    assert _resolve(conn, "fact:AAPL/revenue/ttm", policy) == Resolved(
        trailing.revenue, "currency", "ttm", None
    )
    for ref in (
        "fact:AAPL/revenue/2031",
        "fact:AAPL/goodwill/2025",
        "fact:AAPL/revenue",
        "fact:AAPL/total_assets/ttm",  # not a trailing figure
        "fact:AAPL/cadence/ttm",  # it places the trailing figures, as their period end does
        "fact:ACME/revenue/2025",  # another company's
        "fact:not a symbol/revenue/2025",
    ):
        assert _resolve(conn, ref, policy) is None, ref


def test_a_quarter_s_fact_resolves(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-11, 7.2: ``fact:<symbol>/<line>/<YYYY>-Q<n>`` reads a stored quarter's line as
    the quarters read serves it (ACME's synthetic quarters, the newest ending 2026-09-30 with
    revenue of $340 m), the line's unit, the label its period, an outflow line marked as the
    trailing one is."""
    resolver = Resolver(conn, "AAPL", policy)  # the quarters read once for every ref
    assert resolver.resolve("fact:AAPL/revenue/2026-Q3") == Resolved(
        340 * M, "currency", "2026-Q3", None
    )
    assert resolver.resolve("fact:aapl/revenue/2025-Q3") == Resolved(
        300 * M, "currency", "2025-Q3", None
    )
    eps = resolver.resolve("fact:AAPL/eps_diluted/2026-Q3")
    assert eps is not None and (eps.unit, eps.period) == ("per-share", "2026-Q3")
    assert eps.value == pytest.approx(0.49)
    for line, outflow in (("capex", True), ("buybacks", True), ("cfo", False)):
        found = resolver.resolve(f"fact:AAPL/{line}/2026-Q3")
        assert found is not None and found.outflow is outflow, line
    assert resolver.resolve("fact:AAPL/capex/2026-Q3") == Resolved(
        -24 * M, "currency", "2026-Q3", None, outflow=True
    )
    # the interest expense by its size; a line the quarter lacks holds no figure
    interest = resolver.resolve("fact:AAPL/interest_expense/2026-Q3")
    assert interest == Resolved(4 * M, "currency", "2026-Q3", None)
    assert resolver.resolve("fact:AAPL/sbc/2026-Q1") == Resolved(None, "currency", "2026-Q1", None)
    for quarter in stored_quarters(conn, "AAPL").periods:
        found = resolver.resolve(f"fact:AAPL/net_income/{quarter.period}")
        assert found is not None and found.value == quarter.net_income, quarter.period
    assert resolver.describe("fact:AAPL/revenue/2026-Q3") == (
        "the revenue line of Q3 of fiscal 2026 on file"
    )


def test_a_quarter_not_on_file_is_unresolved(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Review Focus 5: a label not on file, a line that is not a quarter's, a label not written
    ``<YYYY>-Q<n>`` and another company's quarter name nothing; nor does a quarter left out for its
    currency (CADQ's two oldest quarters, in CAD beside annual statements in USD)."""
    resolver = Resolver(conn, "AAPL", policy)
    for ref in (
        "fact:AAPL/revenue/1999-Q1",  # not on file
        "fact:AAPL/total_assets/2026-Q3",  # a balance sheet line, no quarter's
        "fact:AAPL/shares_diluted/2026-Q3",
        "fact:AAPL/period_end/2026-Q3",  # it places the quarter's figures
        "fact:AAPL/fiscal_period/2026-Q3",
        "fact:AAPL/revenue/2026Q3",  # the label has its dash
        "fact:AAPL/revenue/2026-q3",
        "fact:AAPL/revenue/2026-Q3/x",
        "fact:ACME/revenue/2026-Q3",  # another company's
    ):
        assert resolver.resolve(ref) is None, ref
    payloads = {e: p for e, p in bodies().items() if e != "earnings"}
    for row in payloads["income-quarter"][:2]:
        row["reportedCurrency"] = "CAD"
    store_payloads(conn, "CADQ", payloads, NOW)
    other = Resolver(conn, "CADQ", policy)
    assert other.resolve("fact:CADQ/revenue/2025-Q3") is None
    assert other.resolve("fact:CADQ/revenue/2025-Q4") is None
    assert other.resolve("fact:CADQ/revenue/2026-Q1") == Resolved(
        320 * M, "currency", "2026-Q1", None
    )


def test_any_stored_period_label_resolves(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The final review's C.5: a stored period's label that is not of the quarter's form (a
    half-year FMP stores as ``H1``) resolves as the quarters read serves it, the label its period;
    a label not on file, and a year as digits alone not on file, name nothing."""
    payloads = {e: p for e, p in bodies(cadence="half-yearly").items() if e != "earnings"}
    newest = max(payloads["income-quarter"], key=lambda row: row["date"])
    newest["period"] = "H1"
    store_payloads(conn, "HALFQ", payloads, NOW)
    labels = [h.period for h in stored_quarters(conn, "HALFQ").periods]
    assert labels[-1] == "2026-H1"
    resolver = Resolver(conn, "HALFQ", policy)
    assert resolver.resolve("fact:HALFQ/revenue/2026-H1") == Resolved(
        330 * M, "currency", "2026-H1", None
    )
    assert resolver.describe("fact:HALFQ/revenue/2026-H1") == "the revenue line of 2026-H1 on file"
    for ref in ("fact:HALFQ/revenue/2026-H2", "fact:HALFQ/revenue/2031", "fact:HALFQ/revenue/H1"):
        assert resolver.resolve(ref) is None, ref


def test_table_refs(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    tables = financial_tables(conn, "AAPL", policy)
    resolver = Resolver(conn, "AAPL", policy)  # the tables computed once for every cell
    for table in tables:
        for row in table.rows:
            for cell in row.cells:
                ref = f"table:AAPL/{table.name}/{row.name}/{cell.period}"
                found = resolver.resolve(ref)
                outflow = row.name in ("capital_spending", "dividends", "buybacks")
                expected = Resolved(cell.value, cell.unit, cell.period, None, outflow=outflow)
                assert found == expected, ref
    growth = _resolve(conn, "table:AAPL/growth/revenue_growth/2025", policy)
    assert growth is not None and growth.value == pytest.approx(0.05)
    assert _resolve(conn, "table:AAPL/growth/revenue_growth/2019", policy) is None
    assert _resolve(conn, "table:AAPL/growth/nope/2025", policy) is None


def test_estimate_close_and_peer_refs(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    assert _resolve(conn, "estimate:AAPL/2026/eps", policy) == Resolved(
        3.3, "per-share", "2026", None
    )
    assert _resolve(conn, "estimate:AAPL/2027/revenue", policy) == Resolved(
        2420 * M, "currency", "2027", None
    )
    assert _resolve(conn, "estimate:AAPL/2026/analysts_eps", policy) == Resolved(
        9.0, "count", "2026", None
    )
    assert _resolve(conn, "close:AAPL/2025-11-03", policy) == Resolved(
        190.0, "per-share", "2025-11-03", None, price=True
    )
    margin = _resolve(conn, "peer:AAPL/ACME/margin", policy)
    assert margin is not None and margin.unit == "percent"
    assert margin.value == pytest.approx(0.2)  # ACME's ten-year operating margin
    market_cap = _resolve(conn, "peer:AAPL/ACME/market_cap", policy)
    assert market_cap == Resolved(4_000 * M, "currency", None, None)
    for ref in (
        "estimate:AAPL/2030/eps",
        "estimate:AAPL/2026/fiscal_year",
        "estimate:AAPL/2026/nope",
        "close:AAPL/2026-01-01",
        "peer:AAPL/AAL/margin",
        "peer:AAPL/ACME/nope",
    ):
        assert _resolve(conn, ref, policy) is None, ref


def test_an_estimate_ref_reads_the_newest_answer(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """FMP moved AAPL's fiscal 2027 a day, to 2027-12-30, in a newer answer with fewer analysts
    than the stored one's 8: the ref of fiscal 2027 resolves the newer figure, and fiscal 2026,
    which the newer answer leaves out, resolves nothing."""
    moved = [{"symbol": "AAPL", "date": "2027-12-30", "epsAvg": 3.5, "numAnalystsEps": 6}]
    store_payloads(conn, "AAPL", {"estimates-annual": moved}, NOW)
    assert _resolve(conn, "estimate:AAPL/2027/eps", policy) == Resolved(
        3.5, "per-share", "2027", None
    )
    assert _resolve(conn, "estimate:AAPL/2027/analysts_eps", policy) == Resolved(
        6.0, "count", "2027", None
    )
    assert _resolve(conn, "estimate:AAPL/2026/eps", policy) is None


def test_finding_and_derived_refs(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    source = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None}
    services = add_finding(
        conn,
        "AAPL",
        date(2025, 9, 27),
        "services grew",
        source,
        AGENT,
        NOW,
        value=0.112,
        unit="percent",
        period="2025",
    )
    bare = add_finding(conn, "AAPL", date(2025, 9, 27), "no figure", source, AGENT, NOW)
    theirs = add_finding(
        conn, "AAL", date(2025, 9, 27), "x", source, AGENT, NOW, value=1.0, unit="count"
    )
    assert _resolve(conn, f"finding:{services}", policy) == Resolved(0.112, "percent", "2025", None)
    assert _resolve(conn, f"finding:{bare}", policy) == Resolved(None, None, None, None)
    assert _resolve(conn, f"finding:{theirs}", policy) is None

    sid = snapshots["AAPL"]
    a, b = f"snapshot:{sid}/value", "fact:AAPL/revenue/2025"
    derived = insert_derivation(conn, "AAPL", "ratio", b, a, None, 3.5, "multiple", AGENT, NOW)
    on_facts = insert_derivation(
        conn, "AAPL", "growth", b, "fact:AAPL/revenue/2024", None, 0.05, "percent", AGENT, NOW
    )
    assert _resolve(conn, f"derived:{derived}", policy) == Resolved(3.5, "multiple", None, sid)
    assert _resolve(conn, f"derived:{on_facts}", policy) == Resolved(0.05, "percent", None, None)
    assert _resolve(conn, "derived:999", policy) is None
    assert rests_on(conn, f"derived:{derived}") == sid


def test_guidance_refs(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    """A guidance record's figures in the metric's unit, its step a percent, each of the record's
    period; another company's record names nothing, and a step not computed holds no figure."""

    def guided(
        symbol: str, metric: str, period: str, low: float, high: float, base: float | None = None
    ) -> int:
        said, source = "We guide.", "response:12/0/content"
        return insert_guidance(
            conn, symbol, metric, period, low, high, "gaap", TODAY, said, source, AGENT, NOW, base
        )

    revenue = guided("AAPL", "revenue", "2026", 100 * M, 110 * M, 100 * M)
    eps = guided("AAPL", "eps", "2026Q3", 1.5, 1.6)
    margin = guided("AAPL", "operating_margin", "2026", 0.30, 0.32)
    theirs = guided("AAL", "capex", "2026", 10 * M, 12 * M)
    g = f"guidance:{revenue}"
    assert _resolve(conn, f"{g}/low", policy) == Resolved(100 * M, "currency", "2026", None)
    assert _resolve(conn, f"{g}/high", policy) == Resolved(110 * M, "currency", "2026", None)
    midpoint = _resolve(conn, f"{g}/midpoint", policy)
    assert midpoint is not None and midpoint.value == pytest.approx(105 * M)
    step = _resolve(conn, f"{g}/step", policy)
    assert step is not None and step.value == pytest.approx(0.05)
    assert (step.unit, step.period, step.snapshot_id) == ("percent", "2026", None)
    on_eps = f"guidance:{eps}"
    assert _resolve(conn, f"{on_eps}/low", policy) == Resolved(1.5, "per-share", "2026Q3", None)
    assert _resolve(conn, f"{on_eps}/step", policy) == Resolved(None, "percent", "2026Q3", None)
    found = _resolve(conn, f"guidance:{margin}/midpoint", policy)
    assert found is not None and found.unit == "percent"
    for ref in (
        f"guidance:{theirs}/low",
        f"{g}/text",
        f"{g}",
        "guidance:999/low",
        "guidance:x/low",
    ):
        assert _resolve(conn, ref, policy) is None, ref
    assert rests_on(conn, f"{g}/low") is None  # a company fact, as a finding is
    cites = [
        {"cite": "$0.05", "ref": f"{g}/step"},
        {"cite": "5.0%", "ref": f"{g}/step"},
        {"cite": "$105,000,000", "ref": f"{g}/midpoint"},
    ]
    sid = snapshots["AAPL"]
    [finding] = check_sections(
        conn, "AAPL", sid, [{"heading": "Valuation", "parts": cites}], policy
    )
    assert (finding.where, finding.what) == ("section 1, part 1: $0.05", WRONG_UNIT)


def test_a_net_income_guidance_ref_reads_a_total(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-14 9: a net income record's figures are totals in the reporting currency, its
    step a percent: $1.1 bn to $1.3 bn over a 2026 actual of $1.0 bn, a midpoint of $1.2 bn and a
    step of 20%; the references list names it in words, and a report cites it as any total."""
    said, source = "We guide net income.", "response:12/0/content"
    low, high, base = 1.1e9, 1.3e9, 1e9
    record = insert_guidance(
        conn, "AAPL", "net_income", "2027", low, high, "gaap", TODAY, said, source, AGENT, NOW, base
    )
    g = f"guidance:{record}"
    assert _resolve(conn, f"{g}/low", policy) == Resolved(1.1e9, "currency", "2027", None)
    midpoint = _resolve(conn, f"{g}/midpoint", policy)
    assert midpoint is not None and midpoint.value == pytest.approx(1.2e9)
    assert (midpoint.unit, midpoint.period) == ("currency", "2027")
    step = _resolve(conn, f"{g}/step", policy)
    assert step is not None and step.value == pytest.approx(0.2) and step.unit == "percent"
    words = Resolver(conn, "AAPL", policy).describe(f"{g}/midpoint")
    assert words == f"guidance record {record}: net income for fiscal 2027, the midpoint"
    cites = [
        {"cite": "$1,200,000,000", "ref": f"{g}/midpoint"},
        {"cite": "20.0%", "ref": f"{g}/step"},
    ]
    sections = [{"heading": "Valuation", "parts": cites}]
    assert check_sections(conn, "AAPL", snapshots["AAPL"], sections, policy) == []


def test_response_refs(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    payload = [{"symbol": "AAPL", "revenue": 391.0, "segment/name": "Services", "list": [1, 2]}]
    at = datetime(2026, 11, 1, tzinfo=UTC)
    response = record_response(
        conn, "fmp", "segments", {"symbol": "AAPL"}, "AAPL", 200, json.dumps(payload), None, at
    )
    other = record_response(
        conn, "fmp", "segments", {"symbol": "AAL"}, "AAL", 200, json.dumps(payload), None, at
    )
    assert _resolve(conn, f"response:{response}/0/revenue", policy) == Resolved(
        391.0, None, None, None
    )
    assert _resolve(conn, f"response:{response}/0/segment~1name", policy) == Resolved(
        "Services", None, None, None
    )
    for ref in (
        f"response:{response}/0/list",
        f"response:{response}/1/revenue",
        f"response:{response}",
        f"response:{other}/0/revenue",
        "response:999/0/revenue",
    ):
        assert _resolve(conn, ref, policy) is None, ref


def test_a_filing_ref_resolves_whatever_the_sheet_s_name_holds(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Review Focus 1 (spec 2026-11-11, 5.5 and 5.6): a cell of a stored filing report by its
    sheet's served name, its row and its column. The sheet's stored key holds a no-break space, a
    run of spaces, a slash, a tilde, an apostrophe, a comma, a percent sign, a question mark, a
    hash and an accent. A string cell resolves as it is served, the text the agent read, so a cite
    of a word fits it; a null cell holds no value."""
    key = "Rev\xa0by  Product/Region ~ O'Neil, 5% net? #1 é"
    raw_label = "Additional leases, primarily for warehouses,\xa0that have  not yet commenced"
    label = "Additional leases, primarily for warehouses, that have not yet commenced"
    title = {"Rev by Product (Detail) $ in Millions": ["3 Months Ended", "Lease term", ""]}
    report = {
        "symbol": "AAPL",
        "period": "Q1",
        "year": "2027",
        key: [title, {raw_label: [12.5, "1  year ", None]}],
    }
    params = {"symbol": "AAPL", "year": "2027", "period": "Q1"}
    at = datetime(2026, 11, 11, 9, 30, tzinfo=UTC)
    stored = record_response(
        conn, "fmp", "filing-report", params, "AAPL", 200, json.dumps(report), None, at
    )
    segments = record_response(
        conn, "fmp", "segments", {"symbol": "AAPL"}, "AAPL", 200, json.dumps(report), None, at
    )
    row = row_ref(stored, served(key), 1)
    assert row == f"filing:{stored}/Rev by Product~1Region ~0 O'Neil, 5% net? #1 é/1"
    assert _resolve(conn, f"{row}/0", policy) == Resolved(12.5, None, None, None)
    # stored "1  year ": the word as served
    assert _resolve(conn, f"{row}/1", policy) == Resolved("1 year", None, None, None)
    assert _resolve(conn, f"{row}/2", policy) == Resolved(None, None, None, None)
    assert resolve(conn, "AAL", f"{row}/0", policy) is None  # another company's resolver
    for ref in (
        f"{row_ref(segments, served(key), 1)}/0",  # a response of another endpoint
        f"{row_ref(stored, 'Nope', 1)}/0",  # a sheet that is not there
        f"{row_ref(stored, key, 1)}/0",  # the stored key, not the served name
        f"{row_ref(stored, served(key), 9)}/0",  # row 9
        f"{row}/9",  # col 9
        row,  # three parts
        f"{row}/0/0",  # five parts
        f"filing:{stored}/{served(key)}/1/0",  # the slash not escaped: five parts
        "filing:999/LEASES/1/0",
    ):
        assert _resolve(conn, ref, policy) is None, ref
    resolver = Resolver(conn, "AAPL", policy)
    # the final review's B.4: the column by its index and, where the sheet names it, its words
    cited = f"FMP filing report of fiscal 2027 Q1, {served(key)}: {label}"
    assert resolver.describe(f"{row}/0") == (
        f"{cited}, column 0 (3 Months Ended), observed 11 Nov 2026"
    )
    assert resolver.describe(f"{row}/2") == f"{cited}, column 2, observed 11 Nov 2026"
    assert resolver.describe(f"{row}/9") == f"{row}/9"  # a ref that names nothing is its own


def test_multiple_refs_resolve(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """A point of either P/E series by its date, with the date as its period, and a statistic of
    the ten years to the newest day by its name, each a multiple; the trailing series is the newest
    stored ``pettm`` response's, the forward one the log's."""
    rows = [
        ["2016-10-29", 30.0, 30.0, 30.0, 30.0],  # a day before the ten years
        ["2016-10-30", 20.0, 20.0, 20.0, 20.0],
        ["2021-06-30", "At Loss", 0, 0, 0],
        ["2026-10-29", 23.0, 23.0, 23.0, 23.0],
        ["2026-10-30", 24.0, 24.0, 24.0, 24.0],
    ]
    at = datetime(2026, 11, 1, tzinfo=UTC)
    older = [["2026-10-30", 99.0, 99.0, 99.0, 99.0]]
    for payload, observed in ((older, at.replace(day=1, month=10)), (rows, at)):
        record_response(
            conn,
            "gf",
            "pettm",
            {"symbol": "AAPL"},
            "AAPL",
            200,
            json.dumps(payload),
            None,
            observed,
        )
    unread = '{"error": "Stock not found"}'  # newer, stored unusable: never read
    record_response(
        conn,
        "gf",
        "pettm",
        {"symbol": "AAPL"},
        "AAPL",
        200,
        unread,
        f"unusable payload: {unread}",
        at.replace(day=2),
    )
    for day, pe_forward in (("2026-10-29", 21.5), ("2026-10-30", None), ("2026-10-31", 22.5)):
        log_multiples(
            conn, "AAPL", date.fromisoformat(day), 150.0, None, None, pe_forward, 1, 1, at
        )
    expected = {
        "multiple:AAPL/pe/2026-10-30": Resolved(24.0, "multiple", "2026-10-30", None),
        "multiple:AAPL/pe/2016-10-30": Resolved(20.0, "multiple", "2016-10-30", None),
        "multiple:AAPL/pe/avg_10y": Resolved(67 / 3, "multiple", None, None),
        "multiple:AAPL/pe/median_10y": Resolved(23.0, "multiple", None, None),
        "multiple:AAPL/pe/high_10y": Resolved(24.0, "multiple", None, None),
        "multiple:AAPL/pe/low_10y": Resolved(20.0, "multiple", None, None),
        "multiple:aapl/pe_forward/2026-10-31": Resolved(22.5, "multiple", "2026-10-31", None),
        "multiple:AAPL/pe_forward/avg_10y": Resolved(22.0, "multiple", None, None),
        "multiple:AAPL/pe_forward/low_10y": Resolved(21.5, "multiple", None, None),
    }
    for ref, resolved in expected.items():
        assert _resolve(conn, ref, policy) == resolved, ref
    for ref in (
        "multiple:AAPL/pe/2026-10-31",  # no row that day
        "multiple:AAPL/pe/2021-06-30",  # a loss
        "multiple:AAPL/pe/2016-10-29",  # before the ten years
        "multiple:AAPL/pe_forward/2026-10-30",  # no forward P/E that day
        "multiple:AAPL/pe/mean_10y",
        "multiple:AAPL/ps/avg_10y",
        "multiple:AAPL/pe",
        "multiple:AAPL/pe/avg_10y/1",
        "multiple:AAL/pe/avg_10y",  # another company's
    ):
        assert _resolve(conn, ref, policy) is None, ref
    # AAL has no stored series: its trailing refs name nothing, its forward statistics no figure.
    assert resolve(conn, "AAL", "multiple:AAL/pe/avg_10y", policy) is None
    assert resolve(conn, "AAL", "multiple:AAL/pe_forward/avg_10y", policy) == Resolved(
        None, "multiple", None, None
    )
    cites = [
        {"cite": "$22.33", "ref": "multiple:AAPL/pe/avg_10y"},
        {"cite": "22.33x", "ref": "multiple:AAPL/pe/avg_10y"},
        {"cite": "24.00", "ref": "multiple:AAPL/pe/2026-10-30", "period": "2026-10-30"},
    ]
    [finding] = check_sections(
        conn, "AAPL", snapshots["AAPL"], [{"heading": "Price", "parts": cites}], policy
    )
    assert (finding.where, finding.what) == ("section 1, part 1: $22.33", WRONG_UNIT)


def test_policy_refs(conn: sqlite3.Connection, policy: Policy) -> None:
    assert _resolve(conn, "policy:required_return", policy) == Resolved(
        policy.required_return, "percent", None, None
    )
    assert _resolve(conn, "policy:runway_years.Wide", policy) == Resolved(
        float(policy.runway_years["Wide"]), "years", None, None
    )
    assert _resolve(conn, "policy:fair_band.1", policy) == Resolved(
        policy.fair_band[1], "multiple", None, None
    )
    assert _resolve(conn, "policy:z_safe", policy) == Resolved(policy.z_safe, "score", None, None)
    for ref in ("policy:fair_band", "policy:no_such_value", "policy:runway_years.Huge"):
        assert _resolve(conn, ref, policy) is None, ref


def test_same_snapshot_on_a_reprice_and_a_revalue(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    cited = snapshot_row(conn, snapshots["AAPL"])
    assert cited is not None and cited.value is not None
    refresh_id = cited.refresh_id
    repriced = reprice(cited.result, 160.0, date(2026, 11, 2), policy)
    reprice_id = insert_snapshot(conn, repriced, refresh_id, clock=lambda: NOW)
    assert same_snapshot(conn, cited.id, reprice_id)
    assert same_snapshot(conn, cited.id, cited.id)
    assert not same_snapshot(conn, reprice_id, cited.id)  # the later is not the cited's reprice
    revalued = replace(repriced, value=cited.value + 1.0)
    revalue_id = insert_snapshot(conn, revalued, refresh_id, clock=lambda: NOW)
    assert not same_snapshot(conn, cited.id, revalue_id)
    later_data = replace(repriced, data_date=date(2026, 11, 2))
    assert not same_snapshot(
        conn, cited.id, insert_snapshot(conn, later_data, refresh_id, clock=lambda: NOW)
    )
    assert not same_snapshot(conn, snapshots["AAL"], cited.id)  # another company's
    assert not same_snapshot(conn, 999, cited.id)


@pytest.mark.parametrize(
    ("engine", "unit"),
    [
        ("USD", "currency"),
        ("EUR", "currency"),
        ("USD a share", "per-share"),
        ("ratio", "percent"),
        ("multiple", "multiple"),
        ("shares", "count"),
        ("fiscal years", "count"),
        ("years", "years"),
        ("score", "score"),
        ("class", None),
        ("date", None),
        (None, None),
    ],
)
def test_engine_units_map_onto_the_reads_units(engine: str | None, unit: str | None) -> None:
    assert unit_of(engine) == unit


def test_rests_on(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    review_id = _review_id(conn, policy, snapshots["AAPL"])
    assert rests_on(conn, f"snapshot:{snapshots['AAL']}/value") == snapshots["AAL"]
    assert rests_on(conn, f"review:{review_id}/value") == snapshots["AAPL"]
    assert rests_on(conn, "snapshot:999/value") is None
    assert rests_on(conn, "fact:AAPL/revenue/2025") is None


@pytest.fixture
def described(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> dict[str, Any]:
    """The ids of AAPL's records a ref of each form names, and the policy's version."""
    sid = snapshots["AAPL"]
    source = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None}
    grid = SensitivityGrid((0.05, 0.08), (0.10, 0.20), ((120.5, 130.0), (140.0, 150.0)), None)
    revenue = "fact:AAPL/revenue/2025"
    payload = json.dumps([{"symbol": "AAPL", "revenue": 391.0}])
    observed = datetime(2026, 11, 1, 14, 0, tzinfo=UTC)
    return {
        "snapshot": sid,
        "review": _review_id(conn, policy, sid),
        "parts": _secondary_id(conn, policy, sid),
        "drivers": _drivers_secondary_id(conn, policy, sid),
        "sensitivity": insert_sensitivity(
            conn, "AAPL", sid, None, "growth.belief", "return.runway", grid, "v", "h", AGENT, NOW
        ),
        "finding": add_finding(conn, "AAPL", date(2025, 9, 27), "services", source, AGENT, NOW),
        "guidance": insert_guidance(
            conn,
            "AAPL",
            "eps",
            "2027",
            6.25,
            6.75,
            "gaap",
            date(2026, 10, 28),
            "We guide.",
            "response:3/0/content",
            AGENT,
            NOW,
            None,
        ),
        "ratio": insert_derivation(
            conn, "AAPL", "ratio", revenue, f"snapshot:{sid}/value", None, 3.5, None, AGENT, NOW
        ),
        "cagr": insert_derivation(
            conn, "AAPL", "cagr", revenue, "fact:AAPL/revenue/2021", 4, 0.05, "percent", AGENT, NOW
        ),
        "response": record_response(
            conn, "fmp", "segments", {"symbol": "AAPL"}, "AAPL", 200, payload, None, observed
        ),
        "version": policy.version,
        # another company's records, which name nothing for AAPL
        "aal": snapshots["AAL"],
        "their_sensitivity": insert_sensitivity(
            conn, "AAL", snapshots["AAL"], None, "phase", "moat.class", grid, "v", "h", AGENT, NOW
        ),
        "their_finding": add_finding(conn, "AAL", date(2025, 9, 27), "x", source, AGENT, NOW),
    }


@pytest.mark.parametrize(
    ("ref", "source"),
    [
        ("snapshot:{snapshot}/price", "snapshot {snapshot}, the price, priced 30 Oct 2026"),
        ("snapshot:{snapshot}/value", "snapshot {snapshot}, the value a share, priced 30 Oct 2026"),
        (
            "snapshot:{snapshot}/price_to_value",
            "snapshot {snapshot}, price ÷ value, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/levels/fair_low",
            "snapshot {snapshot}, the fair band's low, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/inputs/aggregate_roic",
            "snapshot {snapshot}, the ten-year aggregate ROIC, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/inputs/revenue_ttm",  # an input by its name in words
            "snapshot {snapshot}, the revenue TTM, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/intermediates/belief/rate",
            "snapshot {snapshot}, the belief, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/intermediates/multiples/pe_clean",
            "snapshot {snapshot}, the clean P/E, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/intermediates/growth_rates/0",  # an intermediate by its path
            "snapshot {snapshot}, the growth rates 0, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/intermediates/charge/hold_years",
            "snapshot {snapshot}, the years the runway return holds, priced 30 Oct 2026",
        ),
        # the revenue steps the charge read, the consensus's as found and where each came from
        # (spec 2026-11-14 6.3), by the year's step, counted as the bridge labels count them
        (
            "snapshot:{snapshot}/intermediates/charge/revenue_steps/0",
            "snapshot {snapshot}, the revenue step 2 the charge reads, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/intermediates/charge/revenue_steps_found/1",
            "snapshot {snapshot}, the consensus revenue step 3 as found, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/intermediates/charge/revenue_step_source/1",
            (
                "snapshot {snapshot}, the source of the revenue step 3 the charge reads, priced 30 "
                "Oct 2026"
            ),
        ),
        (
            "review:{review}/intermediates/charge/revenue_steps/1",
            "review {review}, the revenue step 3 the charge reads",
        ),
        (
            "snapshot:{snapshot}/intermediates/runway_return/one_year",
            "snapshot {snapshot}, the newest year's marginal return, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/intermediates/runway_return/constant_margin",
            (
                "snapshot {snapshot}, the five-year marginal return at a constant margin, priced "
                "30 Oct 2026"
            ),
        ),
        (
            "snapshot:{snapshot}/intermediates/runway_return/without_goodwill/measure",
            (
                "snapshot {snapshot}, the return on capital without goodwill and intangibles, priced "
                "30 Oct 2026"
            ),
        ),
        ("snapshot:{snapshot}/phase/phase", "snapshot {snapshot}, the phase, priced 30 Oct 2026"),
        (
            "snapshot:{snapshot}/phase/growth_3y",
            "snapshot {snapshot}, the three-year revenue growth, priced 30 Oct 2026",
        ),
        (
            "snapshot:{snapshot}/phase/growth_decile",  # a classifier field by its name
            "snapshot {snapshot}, the classifier's growth decile, priced 30 Oct 2026",
        ),
        ("review:{review}/value", "review {review}, the value a share"),
        ("review:{review}/levels/buy", "review {review}, the buy level"),
        (
            "review:{review}/bridge/1/delta",
            "review {review}, bridge line 1 (belief), the change in the value a share",
        ),
        ("review:{review}/bridge/1/old", "review {review}, bridge line 1 (belief), the old figure"),
        ("review:{review}/bridge/1/new", "review {review}, bridge line 1 (belief), the new figure"),
        ("review:{review}/intermediates/belief/rate", "review {review}, the belief"),
        (
            "review:{review}/intermediates/implied_growth",
            "review {review}, the growth the price needs",
        ),
        (
            "review:{review}/intermediates/growth_rates/0",  # an intermediate by its path
            "review {review}, the growth rates 0",
        ),
        (
            "review:{review}/intermediates/outside_value_per_share",  # written under the override
            "review {review}, the value outside the business",
        ),
        ("secondary:{parts}/value", "secondary valuation {parts}, the value a share"),
        ("secondary:{parts}/firm_value", "secondary valuation {parts}, the firm value"),
        ("secondary:{parts}/levels/trim", "secondary valuation {parts}, the trim level"),
        ("secondary:{parts}/grid/1/2", "secondary valuation {parts}, the grid, row 1 column 2"),
        (
            "secondary:{parts}/parts/1/pv/3",
            "secondary valuation {parts}, part 1, year 3 present value",
        ),
        ("secondary:{parts}/parts/1/fcff/2", "secondary valuation {parts}, part 1, year 2 FCFF"),
        ("secondary:{parts}/parts/1/value", "secondary valuation {parts}, part 1, its value"),
        (
            "secondary:{parts}/parts/1/terminal_growth",
            "secondary valuation {parts}, part 1, the terminal growth",
        ),
        ("secondary:{drivers}/years/3/fcff", "secondary valuation {drivers}, year 3 FCFF"),
        ("secondary:{drivers}/years/1/revenue", "secondary valuation {drivers}, year 1 revenue"),
        (
            "secondary:{drivers}/terminal_pv",
            "secondary valuation {drivers}, the terminal's present value",
        ),
        ("secondary:{drivers}/drivers/tax_rate", "secondary valuation {drivers}, the tax rate"),
        (
            "secondary:{drivers}/drivers/revenue_growth/2",
            "secondary valuation {drivers}, the revenue growth of year 2",
        ),
        ("sensitivity:{sensitivity}/1/2", "sensitivity {sensitivity}, row 1 column 2"),
        ("sensitivity:{sensitivity}/rows/1", "sensitivity {sensitivity}, the belief of row 1"),
        (
            "sensitivity:{sensitivity}/cols/2",
            "sensitivity {sensitivity}, the runway return of column 2",
        ),
        ("fact:AAPL/revenue/2025", "the revenue line of fiscal 2025 on file"),
        ("fact:AAPL/capex/ttm", "the capital spending line of the trailing twelve months on file"),
        ("fact:AAPL/eps_diluted/2024", "the diluted EPS line of fiscal 2024 on file"),
        ("fact:AAPL/eps_diluted/2026-Q3", "the diluted EPS line of Q3 of fiscal 2026 on file"),
        ("table:AAPL/growth/revenue_growth/2025", "the growth table, revenue growth, fiscal 2025"),
        (
            "table:AAPL/cash_flow/fcf_to_net_income/2025",
            "the cash flow table, FCF to net income, fiscal 2025",
        ),
        ("table:AAPL/quality/altman_z/2025", "the quality table, Altman's Z″, fiscal 2025"),
        (
            "table:AAPL/returns/aggregate_roic_ten_year/2025",
            "the returns table, ten-year aggregate ROIC, fiscal 2025",
        ),
        ("estimate:AAPL/2026/eps", "the consensus for fiscal 2026, EPS"),
        ("estimate:AAPL/2026-Q4/analysts_eps", "the consensus for Q4 of fiscal 2026, analysts EPS"),
        ("close:AAPL/2025-11-03", "the close of 3 Nov 2025"),
        ("multiple:AAPL/pe/2026-10-30", "the trailing P/E, 30 Oct 2026"),
        ("multiple:AAPL/pe_forward/avg_10y", "the forward P/E, the ten-year average"),
        ("multiple:AAPL/pe/low_10y", "the trailing P/E, the ten-year low"),
        ("peer:AAPL/ACME/margin", "ACME, margin"),
        ("peer:AAPL/ACME/sales_to_capital", "ACME, sales to capital"),
        ("finding:{finding}", "finding {finding}: 10-K 2025, p. 41"),
        (
            "guidance:{guidance}/midpoint",
            "guidance record {guidance}: EPS for fiscal 2027, the midpoint",
        ),
        ("guidance:{guidance}/low", "guidance record {guidance}: EPS for fiscal 2027, the low"),
        ("guidance:{guidance}/step", "guidance record {guidance}: EPS for fiscal 2027, the step"),
        (
            "derived:{ratio}",
            "derivation {ratio}: the ratio of fact:AAPL/revenue/2025 and snapshot:{snapshot}/value",
        ),
        (
            "derived:{cagr}",
            (
                "derivation {cagr}: the cagr of fact:AAPL/revenue/2025 and fact:AAPL/revenue/2021"
                " over 4 years"
            ),
        ),
        ("response:{response}/0/revenue", "FMP segments, observed 1 Nov 2026"),
        ("policy:required_return", "policy required_return, {version}"),
        (" snapshot:{snapshot}/price ", "snapshot {snapshot}, the price, priced 30 Oct 2026"),
        # a ref that names nothing is its own description
        ("nosuchform:1/value", "nosuchform:1/value"),
        ("finding:999", "finding:999"),
        ("sensitivity:999/1/2", "sensitivity:999/1/2"),
        ("sensitivity:{sensitivity}/3/1", "sensitivity:{sensitivity}/3/1"),  # no third row
        ("sensitivity:{sensitivity}/cols/3", "sensitivity:{sensitivity}/cols/3"),  # two columns
        ("secondary:999/value", "secondary:999/value"),
        ("secondary:{parts}/years/1/fcff", "secondary:{parts}/years/1/fcff"),  # the drivers form's
        ("secondary:{drivers}/years/4/fcff", "secondary:{drivers}/years/4/fcff"),  # three years
        ("sensitivity:{their_sensitivity}/1/1", "sensitivity:{their_sensitivity}/1/1"),
        ("finding:{their_finding}", "finding:{their_finding}"),
        ("snapshot:{aal}/price", "snapshot:{aal}/price"),
    ],
)
def test_describe(
    conn: sqlite3.Connection, policy: Policy, described: dict[str, Any], ref: str, source: str
) -> None:
    """Each form's source in words, one sentence for the references list: a date or a name where
    one serves, the record's id where nothing else names it."""
    resolver = Resolver(conn, "AAPL", policy)
    assert resolver.describe(ref.format(**described)) == source.format(**described)
