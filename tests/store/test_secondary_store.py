"""The secondary valuations and the derivations (spec 2026-11-06 Tier 2, 11 and 13.4): each read
back exactly, the parts with their present values or the drivers with their projection, the grid
and the rate, newest first; and why a company can have none on a snapshot (spec 2026-11-10 7.6)."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from support.engine_companies import mature_growth_inputs, universe_deciles, young_growth_inputs
from support.web import TODAY, _company

from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import value_company
from fairband.engine.secondary import SECONDARY_METHOD, Drivers, Part, secondary_value
from fairband.engine.types import ValuationResult
from fairband.policy import load_policy
from fairband.refresh.rates import NO_RATE
from fairband.store.companies import insert_companies
from fairband.store.ledger import OWNER, Writer
from fairband.store.reviews import ReviewRow, insert_review, latest_secondary_value, review_row
from fairband.store.secondary import (
    DerivationRow,
    SecondaryRow,
    cannot_fix,
    derivation_row,
    insert_derivation,
    insert_secondary,
    latest_secondaries,
    latest_secondary,
    no_secondary,
    secondaries_for,
)
from fairband.store.snapshots import SnapshotRow, insert_snapshot, snapshot_row

NOW = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
FILING = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None, "figure": "debt"}
PATH = (100.0, 105.0, 110.25, 115.7625, 121.550625)
PARTS = (Part("the business", PATH, 0.03, None), Part("a unit", (20.0,) * 5, 0.0, "a royalty"))
# Spec 20.4's drivers, from a trailing revenue of 1,000 at a terminal return of 12%.
DRIVERS = Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02)
POLICY = load_policy()
# The refusals an agent cannot fix (spec 2026-11-10 7.6), as the engine words them: no diluted
# share count, the currency's four of 7.5 and the listed-share basis's, as method 1.6 words it and
# with the ratio a snapshot valued before 1.6 may carry (spec 2026-11-19 6.2).
ABOVE_BOUND = "ARS: expected inflation 12.1% above the 10% bound"
BASIS = "share basis unclear: the newest period's count 259.5 m against the quote's 194.9 m"
BASIS_BEFORE_1_6 = (
    "share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the ADR"
    " ratio 10)"
)
CANNOT_FIX = (
    "no diluted share count",
    "reporting currency unknown",
    NO_RATE.format(code="SEK"),
    "no inflation projection for XYZ",
    ABOVE_BOUND,
    BASIS,
    BASIS_BEFORE_1_6,
)
# The refusal the engine gave a foreign filer before method 1.1, which an old snapshot carries.
FOREIGN_FILER = "foreign filer: currency and share-unit handling not built yet"


def _insert(
    conn: sqlite3.Connection,
    parts: tuple[Part, ...] = PARTS,
    debt: float = 200.0,
    writer: Writer = AGENT,
    at: datetime = NOW,
    symbol: str = "AAPL",
) -> int:
    valuation = secondary_value(
        parts=parts, debt=debt, cash=100.0, shares=100.0, price=15.0, moat="Wide", policy=POLICY
    )
    return insert_secondary(
        conn,
        symbol,
        7,
        parts,
        valuation,
        "the segments diverge",
        [FILING],
        "agent",
        "statements",
        POLICY.version,
        "{}",
        3,
        writer,
        at,
    )


def test_a_secondary_valuation_reads_back_exactly(conn: sqlite3.Connection) -> None:
    secondary_id = _insert(conn)
    assert not conn.in_transaction
    v = secondary_value(
        parts=PARTS, debt=200.0, cash=100.0, shares=100.0, price=15.0, moat="Wide", policy=POLICY
    )
    assert v.levels is not None and v.grid is not None
    found = latest_secondary(conn, "AAPL")
    assert found == SecondaryRow(
        id=secondary_id,
        symbol="AAPL",
        snapshot_id=7,
        created_at=NOW,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        parts=(
            {
                "name": "the business",
                "fcff": list(PATH),
                "terminal_growth": 0.03,
                "note": None,
                "pv": list(v.parts[0].pv),
                "terminal": v.parts[0].terminal,
                "terminal_pv": v.parts[0].terminal_pv,
                "value": v.parts[0].value,
            },
            {
                "name": "a unit",
                "fcff": [20.0] * 5,
                "terminal_growth": 0.0,
                "note": "a royalty",
                "pv": list(v.parts[1].pv),
                "terminal": v.parts[1].terminal,
                "terminal_pv": v.parts[1].terminal_pv,
                "value": v.parts[1].value,
            },
        ),
        firm_value=v.firm_value,
        debt=200.0,
        cash=100.0,
        shares=100.0,
        equity=v.equity,
        value_per_share=v.value_per_share,
        buy_level=v.levels.buy,
        fair_low=v.levels.fair_low,
        fair_high=v.levels.fair_high,
        trim_level=v.levels.trim,
        price_to_value=v.price_to_value,
        designation=v.designation,
        reason="the segments diverge",
        evidence=(FILING,),
        debt_source="agent",
        cash_source="statements",
        policy_version=POLICY.version,
        settings_hash="{}",
        deciles_refresh_id=3,
        secondary_method=SECONDARY_METHOD,
        form="parts",
        drivers=None,
        projection=None,
        grid={
            "rows": list(v.grid.rows),
            "cols": list(v.grid.cols),
            "cells": [list(row) for row in v.grid.cells],
        },
        fx_rate=1.0,  # a USD row's
    )
    assert latest_secondary_value(conn, "AAPL") == v.value_per_share  # the review log's reader
    assert latest_secondary(conn, "MSFT") is None and secondaries_for(conn, "MSFT") == []


def test_a_drivers_valuation_reads_back_exactly(conn: sqlite3.Connection) -> None:
    v = secondary_value(
        drivers=DRIVERS,
        revenue_0=1000.0,
        roic_t=0.12,
        debt=200.0,
        cash=100.0,
        shares=50.0,
        price=30.0,
        moat="Wide",
        policy=POLICY,
    )
    assert v.projection is not None and v.grid is not None
    secondary_id = insert_secondary(
        conn,
        "AAPL",
        7,
        (),
        v,
        "the cycle turns",
        [FILING],
        "agent",
        "agent",
        POLICY.version,
        "{}",
        3,
        AGENT,
        NOW,
        revenue_0=1000.0,
        roic_t=0.12,
    )
    found = latest_secondary(conn, "AAPL")
    assert found is not None and found.id == secondary_id
    assert (found.form, found.parts, found.value_per_share) == ("drivers", (), v.value_per_share)
    assert found.value_per_share == pytest.approx(39.888938, abs=1e-4)
    assert found.drivers == {
        "years": 3,
        "revenue_growth": [0.10, 0.08, 0.05],
        "operating_margin": [0.20, 0.20, 0.20],
        "tax_rate": 0.25,
        "sales_to_capital": 2.0,
        "terminal_growth": 0.02,
    }
    assert found.projection == {
        "trailing_revenue": 1000.0,
        "terminal_return": 0.12,
        "years": [
            {
                "t": y.t,
                "revenue": y.revenue,
                "ebit": y.ebit,
                "nopat": y.nopat,
                "reinvestment": y.reinvestment,
                "fcff": y.fcff,
                "pv": y.pv,
            }
            for y in v.projection.years
        ],
        "terminal_fcff": v.projection.terminal_fcff,
        "terminal": v.projection.terminal,
        "terminal_pv": v.projection.terminal_pv,
    }
    assert found.grid == {
        "rows": list(v.grid.rows),
        "cols": list(v.grid.cols),
        "cells": [list(row) for row in v.grid.cells],
    }
    assert found.secondary_method == SECONDARY_METHOD


def test_the_record_carries_the_snapshot_s_rate(conn: sqlite3.Connection) -> None:
    """A secondary valuation in another currency stores its snapshot's rate, units of the currency
    per USD, read back exactly (spec 2026-11-10 7.6); one stored without a rate, a USD row's,
    holds 1.0."""
    v = secondary_value(
        parts=PARTS, debt=200.0, cash=100.0, shares=100.0, price=15.0, moat="Wide", policy=POLICY
    )
    rated = insert_secondary(
        conn,
        "FXCO",
        7,
        PARTS,
        v,
        "the segments diverge",
        [FILING],
        "agent",
        "statements",
        POLICY.version,
        "{}",
        3,
        AGENT,
        NOW,
        fx_rate=8.123456789,
    )
    found = latest_secondary(conn, "FXCO")
    assert found is not None and (found.id, found.fx_rate) == (rated, 8.123456789)
    _insert(conn)
    usd = latest_secondary(conn, "AAPL")
    assert usd is not None and usd.fx_rate == 1.0


def test_a_valuation_with_no_grid_stores_none(conn: sqlite3.Connection) -> None:
    """A rate a point below r at or below the highest growth leaves no grid (method 15.5)."""
    low_r = replace(POLICY, required_return=0.035)
    v = secondary_value(
        parts=PARTS, debt=200.0, cash=100.0, shares=100.0, price=15.0, moat="Wide", policy=low_r
    )
    assert v.grid is None
    insert_secondary(
        conn,
        "AAPL",
        7,
        PARTS,
        v,
        "the segments diverge",
        [FILING],
        "agent",
        "statements",
        POLICY.version,
        "{}",
        3,
        AGENT,
        NOW,
    )
    found = latest_secondary(conn, "AAPL")
    assert found is not None and (found.form, found.grid) == ("parts", None)


def test_a_negative_value_is_stored_with_no_levels(conn: sqlite3.Connection) -> None:
    loss = (Part("a loss", (-50.0,) * 3, 0.0, None),)
    _insert(conn, loss, debt=1000.0)
    found = latest_secondary(conn, "AAPL")
    assert found is not None and found.value_per_share < 0
    levels = (found.buy_level, found.fair_low, found.fair_high, found.trim_level)
    assert levels == (None,) * 4 and (found.price_to_value, found.designation) == (None, None)


def test_secondaries_newest_first(conn: sqlite3.Connection) -> None:
    first = _insert(conn)
    second = _insert(conn, writer=OWNER, at=LATER)
    assert [s.id for s in secondaries_for(conn, "AAPL")] == [second, first]
    latest = latest_secondary(conn, "AAPL")
    assert latest is not None and (latest.id, latest.principal, latest.actor) == (
        second,
        "owner",
        None,
    )


def test_latest_secondaries_newest_per_symbol(conn: sqlite3.Connection) -> None:
    """The screen's one read (spec 18.1): every company's newest, by symbol."""
    assert latest_secondaries(conn) == {}
    _insert(conn)
    newest = _insert(conn, at=LATER)
    other = _insert(conn, symbol="MSFT")
    found = latest_secondaries(conn)
    assert list(found) == ["AAPL", "MSFT"]
    assert (found["AAPL"].id, found["MSFT"].id) == (newest, other)
    assert found["AAPL"] == latest_secondary(conn, "AAPL")


@pytest.mark.parametrize("refusal", [*CANNOT_FIX, FOREIGN_FILER])
def test_cannot_fix_names_the_refusals_an_agent_cannot_fix(refusal: str) -> None:
    """No diluted share count, the currency refusals of spec 2026-11-10 7.5 and the basis's, each
    as the engine words it; and the foreign-filer refusal an old snapshot on file carries."""
    assert cannot_fix(refusal)


@pytest.mark.parametrize(
    "refusal",
    [
        None,
        "no trailing revenue",
        "value not positive under the reinvestment charge",
        "no target margin: 2 mature peers",
        "incomplete NTM consensus",
        "Start-up: no value by design",
        "foreign filer",  # the word alone is no refusal the engine gives
    ],
)
def test_cannot_fix_leaves_every_other_refusal_to_the_fallback(refusal: str | None) -> None:
    assert not cannot_fix(refusal)


def test_no_secondary_names_the_valued_route_first(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    """Why a company can have no secondary valuation on a snapshot, in the order the secondary
    route refuses (method 15.4, plan 3): the route values it (ADRX, an ADR the route values),
    before a refusal an agent cannot fix; then the review values it (AAL refused for its target
    margin, valued by a margin override), before such a refusal too; then that refusal in its own
    words (spec 2026-11-10 7.6), an old snapshot's foreign-filer refusal among them, or no diluted
    share count. None on a refused snapshot that can have one, nor where its review refused: an
    ADR in USD the route refuses takes the fallback, the ADR flag being no ground."""
    refresh_id = new_refresh()
    adr = replace(_company("ADRX", refresh_id, "An ADR", Decimal(100_000_000_000)), is_adr=True)
    insert_companies(conn, [adr])

    def stored(result: ValuationResult) -> SnapshotRow:
        found = snapshot_row(conn, insert_snapshot(conn, result, refresh_id, clock=lambda: NOW))
        assert found is not None
        return found

    def valued(**changes: object) -> ValuationResult:
        inputs = replace(mature_growth_inputs(), **changes)
        return value_company(inputs, universe_deciles(), POLICY, TODAY)

    adr_valued = valued(symbol="ADRX")
    assert adr_valued.value is not None
    assert no_secondary(stored(adr_valued), None) == "the route values the company"
    adr_refused = valued(symbol="ADRX", refusal="a test refusal")
    assert no_secondary(stored(adr_refused), None) is None
    above_bound = valued(symbol="ARSX", currency="ARS", refusal=ABOVE_BOUND)
    assert no_secondary(stored(above_bound), None) == ABOVE_BOUND
    old = valued(symbol="FRGN", currency="EUR", refusal=FOREIGN_FILER)
    assert no_secondary(stored(old), None) == FOREIGN_FILER
    no_shares = valued(symbol="NOSH", shares_diluted=None)
    assert no_secondary(stored(no_shares), None) == "no diluted share count"
    young = replace(young_growth_inputs(), symbol="AAL", peers=())
    refused = value_company(young, universe_deciles(), POLICY, TODAY)
    assert refused.value is None and refused.refusal is not None
    on_refused = stored(refused)
    assert no_secondary(on_refused, None) is None
    # the review: valued, an override having routed the refused row; refused, as the row is
    target = Override(1, "margin.target", 0.2, "agent", AGENT.actor, NOW, "the peers by hand")
    routed = review_company(young, universe_deciles(), POLICY, TODAY, [target], refused)
    assert routed.result.value is not None
    valued_review = _review(conn, routed, on_refused.id)
    still_refused = Review(
        replace(refused, refusal="the reviewed margin is refused"), None, (), (1,)
    )
    refused_review = _review(conn, still_refused, on_refused.id)
    assert no_secondary(on_refused, valued_review) == "the review values the company"
    assert no_secondary(on_refused, refused_review) is None
    # the route's reason first, and the review's before a refusal an agent cannot fix
    assert no_secondary(stored(adr_valued), valued_review) == "the route values the company"
    assert no_secondary(stored(above_bound), valued_review) == "the review values the company"


def _review(conn: sqlite3.Connection, review: Review, snapshot_id: int) -> ReviewRow:
    """``review`` stored on snapshot ``snapshot_id``, read back."""
    found = review_row(
        conn, insert_review(conn, review, "AAL", snapshot_id, None, clock=lambda: NOW)
    )
    assert found is not None
    return found


def test_a_derivation_reads_back_exactly(conn: sqlite3.Connection) -> None:
    cagr = insert_derivation(
        conn,
        "AAPL",
        "cagr",
        "fact:AAPL/revenue/2025",
        "fact:AAPL/revenue/2022",
        3,
        0.1 / 3,
        "percent",
        AGENT,
        NOW,
    )
    by_zero = insert_derivation(
        conn,
        "AAPL",
        "ratio",
        "snapshot:7/price",
        "snapshot:7/value",
        None,
        None,
        None,
        OWNER,
        LATER,
    )
    assert not conn.in_transaction
    assert derivation_row(conn, cagr) == DerivationRow(
        id=cagr,
        symbol="AAPL",
        operation="cagr",
        a="fact:AAPL/revenue/2025",
        b="fact:AAPL/revenue/2022",
        years=3,
        value=0.1 / 3,
        unit="percent",
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        at=NOW,
    )
    found = derivation_row(conn, by_zero)
    assert found is not None and (found.value, found.unit, found.years) == (None, None, None)
    assert (found.principal, found.at) == ("owner", LATER)
    assert derivation_row(conn, by_zero + 1) is None
