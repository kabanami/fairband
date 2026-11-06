"""The ledger: one row for every write, under the writer that made it (spec 2026-11-06 Tier 2,
section 7)."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fairband.store.db import transaction
from fairband.store.ledger import OWNER, SYSTEM, LedgerRow, Writer, entries, record

NOW = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)


def test_record_and_entries(conn: sqlite3.Connection) -> None:
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    first = record(conn, writer, NOW, "note", "AAPL", "notes", 1, summary="a note")
    second = record(
        conn,
        SYSTEM,
        NOW + timedelta(minutes=1),
        "work-item",
        "MSFT",
        "work_items",
        1,
        summary="expiry",
    )
    rows = entries(conn)
    assert [r.id for r in rows] == [second, first]
    assert rows[1].actor == "claude-opus-5-5" and rows[1].client == "claude-code/2.1"
    assert [r.symbol for r in entries(conn, "AAPL")] == ["AAPL"]
    assert len(entries(conn, limit=1)) == 1


def test_a_row_reads_back_whole(conn: sqlite3.Connection) -> None:
    """Every field round trips: the time as an aware timestamp, the snapshot and work item the
    write rested on, a row with no company."""
    rested = record(
        conn,
        OWNER,
        NOW,
        "request",
        "AAPL",
        "work_items",
        4,
        snapshot_id=12,
        work_item_id=4,
        summary="valuation review requested",
    )
    bare = record(conn, SYSTEM, NOW, "derivation", None, "derivations", 9, summary="ratio")
    newest, oldest = entries(conn)
    assert oldest == LedgerRow(
        id=rested,
        at=NOW,
        principal="owner",
        actor=None,
        client=None,
        kind="request",
        symbol="AAPL",
        ref_table="work_items",
        ref_id=4,
        snapshot_id=12,
        work_item_id=4,
        summary="valuation review requested",
    )
    assert (newest.id, newest.principal, newest.symbol, newest.snapshot_id) == (
        bare,
        "system",
        None,
        None,
    )


def test_a_row_joins_the_callers_transaction(conn: sqlite3.Connection) -> None:
    """A record and its ledger row commit together, or neither does."""
    with pytest.raises(RuntimeError), transaction(conn):
        record(conn, OWNER, NOW, "note", "AAPL", "notes", 1, summary="a note")
        raise RuntimeError("the record's write failed")
    assert entries(conn) == []


def test_a_row_may_point_at_no_record(conn: sqlite3.Connection) -> None:
    """A rejected report stores nothing but its ledger row, which has no record to name (spec
    2026-11-06 Tier 2, 13.1)."""
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    record(conn, writer, NOW, "report", "AAPL", None, None, summary="rejected: 2 findings")
    [row] = entries(conn, "AAPL")
    assert (row.kind, row.ref_table, row.ref_id, row.summary) == (
        "report",
        None,
        None,
        "rejected: 2 findings",
    )


@pytest.mark.parametrize(("ref_table", "ref_id"), [("reports", None), (None, 3)])
def test_a_half_reference_is_refused(
    conn: sqlite3.Connection, ref_table: str | None, ref_id: int | None
) -> None:
    with pytest.raises(
        ValueError, match="^a ledger reference names its table and its id together$"
    ):
        record(conn, OWNER, NOW, "report", "AAPL", ref_table, ref_id, summary="half")
    assert entries(conn) == []
