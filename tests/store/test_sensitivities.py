"""The sensitivity readings (spec 2026-11-06 Tier 2, 13.8): each read back exactly, a number or a
word on either axis, a null cell kept, and the pair in force stored both or neither, counted
from 1."""

import sqlite3
from datetime import UTC, datetime

from fairband.engine.sensitivity import SensitivityGrid
from fairband.store.ledger import OWNER, Writer
from fairband.store.sensitivities import SensitivityRow, insert_sensitivity, sensitivity_row

NOW = datetime(2026, 11, 7, 9, 30, tzinfo=UTC)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")


def test_a_sensitivity_reads_back_exactly(conn: sqlite3.Connection) -> None:
    cells = ((133.36653551867192, None), (0.1 + 0.2, 12.0))
    grid = SensitivityGrid((0.05, 0.08), ("Narrow", "Wide"), cells, (1, 2))
    found = insert_sensitivity(
        conn,
        "AAPL",
        7,
        3,
        "growth.belief",
        "moat.class",
        grid,
        "fairband-policy-v9",
        "abc123",
        AGENT,
        NOW,
    )
    assert sensitivity_row(conn, found) == SensitivityRow(
        id=found,
        symbol="AAPL",
        snapshot_id=7,
        review_id=3,
        created_at=NOW,
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        row_tag="growth.belief",
        col_tag="moat.class",
        row_values=(0.05, 0.08),
        col_values=("Narrow", "Wide"),
        cells=cells,
        current=(1, 2),
        policy_version="fairband-policy-v9",
        settings_hash="abc123",
    )
    assert sensitivity_row(conn, found + 1) is None


def test_no_pair_in_force_stores_neither_index(conn: sqlite3.Connection) -> None:
    grid = SensitivityGrid((0.05,), (0.10, 0.20), ((10.0, 12.5),), None)
    found = insert_sensitivity(
        conn, "AAPL", 7, None, "growth.belief", "return.runway", grid, "v", "h", OWNER, NOW
    )
    row = sensitivity_row(conn, found)
    assert row is not None
    assert (row.current, row.review_id, row.principal, row.actor) == (None, None, "owner", None)
    stored = conn.execute(
        "SELECT current_row, current_col FROM sensitivities WHERE id = ?", (found,)
    ).fetchone()
    assert tuple(stored) == (None, None)
