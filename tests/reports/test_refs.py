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
from fairband.engine.secondary import Part, secondary_value
from fairband.policy import Policy
from fairband.policy.tax import load_tax_table
from fairband.refresh.inputs_statements import statements_for
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
from fairband.store.research import add_finding
from fairband.store.reviews import insert_review
from fairband.store.secondary import insert_derivation, insert_secondary
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
    for ref, (value, unit) in expected.items():
        assert _resolve(conn, ref, policy) == Resolved(value, unit, None, sid), ref
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
    valuation = secondary_value([part], 200.0, 100.0, 100.0, 150.0, "Wide", policy)
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
                assert found == Resolved(cell.value, cell.unit, cell.period, None), ref
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
        190.0, "per-share", "2025-11-03", None
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
    assert _resolve(conn, "policy:z_safe", policy) == Resolved(policy.z_safe, "count", None, None)
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
