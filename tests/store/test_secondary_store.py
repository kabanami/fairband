"""The secondary valuations and the derivations (spec 2026-11-06 Tier 2, 11 and 13.4): each read
back exactly, the parts with their present values, newest first."""

import sqlite3
from datetime import UTC, datetime, timedelta

from fairband.engine.secondary import SECONDARY_METHOD, Part, secondary_value
from fairband.policy import load_policy
from fairband.store.ledger import OWNER, Writer
from fairband.store.reviews import latest_secondary_value
from fairband.store.secondary import (
    DerivationRow,
    SecondaryRow,
    derivation_row,
    insert_derivation,
    insert_secondary,
    latest_secondary,
    secondaries_for,
)

NOW = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
FILING = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None, "figure": "debt"}
PATH = (100.0, 105.0, 110.25, 115.7625, 121.550625)
PARTS = (Part("the business", PATH, 0.03, None), Part("a unit", (20.0,) * 5, 0.0, "a royalty"))
POLICY = load_policy()


def _insert(
    conn: sqlite3.Connection,
    parts: tuple[Part, ...] = PARTS,
    debt: float = 200.0,
    writer: Writer = AGENT,
    at: datetime = NOW,
) -> int:
    valuation = secondary_value(parts, debt, 100.0, 100.0, 15.0, "Wide", POLICY)
    return insert_secondary(
        conn,
        "AAPL",
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
    v = secondary_value(PARTS, 200.0, 100.0, 100.0, 15.0, "Wide", POLICY)
    assert v.levels is not None
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
    )
    assert latest_secondary_value(conn, "AAPL") == v.value_per_share  # the review log's reader
    assert latest_secondary(conn, "MSFT") is None and secondaries_for(conn, "MSFT") == []


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
