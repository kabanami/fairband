"""The references a report cites (spec 2026-11-06 Tier 2, 13.2), each form resolved on the
``snapshots`` fixture of ``conftest.py``: AAPL (the Mature Growth golden renamed, a price of $150)
with ACME's synthetic statements, consensus, closes and ACME as its mature peer; AAL, refused."""

import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from refresh.synthetic import NOW
from support.engine_companies import mature_growth_inputs, universe_deciles
from support.web import TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import review_company
from fairband.engine.route import reprice, value_company
from fairband.engine.secondary import Drivers, Part, secondary_value
from fairband.engine.sensitivity import SensitivityGrid
from fairband.policy import Policy
from fairband.policy.tax import load_tax_table
from fairband.refresh.inputs_statements import statements_for
from fairband.reports.check import WRONG_UNIT, check_sections
from fairband.reports.refs import (
    Resolved,
    Resolver,
    resolve,
    rests_on,
    same_snapshot,
    unit_of,
)
from fairband.reports.tables import financial_tables
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
    for ref in (
        f"{r}/bridge/0/delta",
        f"{r}/bridge/2/delta",
        f"{r}/bridge/1/tag",
        "review:99/value",
    ):
        assert _resolve(conn, ref, policy) is None, ref


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
    """A cell by its row and its column, each counted from 1; a refused cell holds no value."""
    sid = snapshots["AAPL"]
    grid = SensitivityGrid((0.05, 0.08), (0.10, 0.20, 0.30), ((120.5, None, 140.0),) * 2, None)
    found = insert_sensitivity(
        conn, "AAPL", sid, None, "growth.belief", "return.runway", grid, "v", "h", AGENT, NOW
    )
    theirs = insert_sensitivity(
        conn, "AAL", snapshots["AAL"], None, "phase", "moat.class", grid, "v", "h", AGENT, NOW
    )
    s = f"sensitivity:{found}"
    assert _resolve(conn, f"{s}/1/1", policy) == Resolved(120.5, "per-share", None, sid)
    assert _resolve(conn, f"{s}/2/3", policy) == Resolved(140.0, "per-share", None, sid)
    assert _resolve(conn, f"{s}/1/2", policy) == Resolved(None, "per-share", None, sid)
    for ref in (
        f"{s}/0/1",
        f"{s}/3/1",
        f"{s}/1/4",
        f"{s}/1",
        f"{s}/1/1/1",
        f"{s}/x/1",
        f"sensitivity:{theirs}/1/1",  # another company's
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
        "fact:ACME/revenue/2025",  # another company's
        "fact:not a symbol/revenue/2025",
    ):
        assert _resolve(conn, ref, policy) is None, ref


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
