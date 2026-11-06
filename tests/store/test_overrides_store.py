"""The overrides (spec 2026-11-06 Tier 2, 10.1 to 10.3): each stored with the rule's answer, a number
or a word read back exactly, and dropped with its reason."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fairband.engine.overrides import Override
from fairband.store.ledger import Writer
from fairband.store.overrides import (
    OverrideRow,
    applied_overrides,
    as_override,
    drop_override,
    insert_override,
    override_row,
    overrides_for,
    set_review,
)

NOW = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
TRANSCRIPT = {"kind": "transcript", "ref": "Q3 call", "note": "guidance raised"}


def _belief(conn: sqlite3.Connection, symbol: str = "AAPL", new: float = 0.08) -> int:
    return insert_override(
        conn,
        symbol,
        "growth.belief",
        0.1234567890123,
        new,
        "ratio",
        "guidance raised",
        [TRANSCRIPT],
        "lasting",
        None,
        None,
        7,
        AGENT,
        NOW,
        "applied",
        "",
    )


def test_an_override_reads_back_exactly(conn: sqlite3.Connection) -> None:
    belief = _belief(conn)
    cash = insert_override(
        conn,
        "AAPL",
        "balance.cash",
        None,
        250e6,
        "USD",
        "the vendor dropped the line",
        [{"kind": "filing", "ref": "10-K 2025, p. 41", "note": None}],
        "period-tied",
        "FY2025",
        None,
        7,
        AGENT,
        LATER,
        "applied",
        "",
    )
    moat = insert_override(
        conn,
        "AAPL",
        "moat.class",
        "Wide",
        "Narrow",
        "class",
        "the patents lapse",
        [],
        "lasting",
        None,
        None,
        7,
        AGENT,
        LATER,
        "refused-evidence",
        "an override needs evidence",
    )
    assert not conn.in_transaction
    assert override_row(conn, belief) == OverrideRow(
        id=belief,
        symbol="AAPL",
        tag="growth.belief",
        old=0.1234567890123,
        new=0.08,
        unit="ratio",
        reason="guidance raised",
        evidence=(TRANSCRIPT,),
        lifetime="lasting",
        period=None,
        corrected_value=None,
        snapshot_id=7,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        at=NOW,
        state="applied",
        message="",
        review_id=None,
        drop_reason=None,
        dropped_at=None,
    )
    found = override_row(conn, cash)
    assert found is not None
    assert (found.old, found.new, found.lifetime, found.period) == (
        None,
        250e6,
        "period-tied",
        "FY2025",
    )
    words = override_row(conn, moat)
    assert words is not None
    assert (words.old, words.new, words.state, words.message) == (
        "Wide",
        "Narrow",
        "refused-evidence",
        "an override needs evidence",
    )
    assert override_row(conn, 99) is None


def test_a_period_tied_override_keeps_the_value_it_corrected(conn: sqlite3.Connection) -> None:
    for corrected in (100.0, "Wide", None):
        override_id = insert_override(
            conn,
            "AXLE",
            "balance.cash",
            corrected,
            120.0,
            "USD",
            "r",
            [TRANSCRIPT],
            "period-tied",
            "FY2025",
            corrected,
            3,
            AGENT,
            NOW,
            "applied",
            "",
        )
        found = override_row(conn, override_id)
        assert found is not None and found.corrected_value == corrected


def test_applied_overrides_after_a_drop(conn: sqlite3.Connection) -> None:
    first, other, second = _belief(conn), _belief(conn, "MSFT"), _belief(conn, new=0.09)
    assert [o.id for o in applied_overrides(conn, "AAPL")] == [first, second]
    drop_override(conn, first, "replaced by override 3", LATER)
    assert not conn.in_transaction
    assert [o.id for o in applied_overrides(conn, "AAPL")] == [second]
    dropped = override_row(conn, first)
    assert dropped is not None
    assert (dropped.state, dropped.drop_reason, dropped.dropped_at) == (
        "dropped",
        "replaced by override 3",
        LATER,
    )
    assert [o.id for o in overrides_for(conn, "AAPL")] == [second, first]  # newest first
    assert [o.id for o in overrides_for(conn, "MSFT")] == [other]


def test_only_an_applied_override_drops(conn: sqlite3.Connection) -> None:
    first = _belief(conn)
    drop_override(conn, first, "wrong", LATER)
    with pytest.raises(ValueError, match="override 1 is dropped, not applied"):
        drop_override(conn, first, "again", LATER)
    with pytest.raises(KeyError):
        drop_override(conn, 99, "none", LATER)


def test_set_review_and_the_engine_record(conn: sqlite3.Connection) -> None:
    belief = _belief(conn)
    set_review(conn, belief, 12)
    found = override_row(conn, belief)
    assert found is not None and found.review_id == 12
    assert as_override(found) == Override(
        belief, "growth.belief", 0.08, "agent", "claude-opus-5-5", NOW, "guidance raised"
    )
    with pytest.raises(KeyError):
        set_review(conn, 99, 12)
