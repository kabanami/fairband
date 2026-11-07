"""The sensitivity readings of the route (spec 2026-11-06 Tier 2, 13.8; ``method.md`` 14.8).

A reading is stored as of the snapshot it was made on, and never changed: the company, the
snapshot, the current review it ran under (none without an applied override), the two inputs'
tags, their values as JSON (a number or a word each, so either reads back exactly), the cells as
JSON (a row of values a share for each row value, ``null`` where the engine valued none, each
float written as its ``repr``), the pair in force as two columns counted from 1, both or neither,
the policy version and the settings hash it ran under, and the writer and the time.
``sensitivity_row`` reads one by its id.

Each write is one transaction; it joins the caller's when there is one, so the caller's ledger row
commits with it.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from fairband.engine.sensitivity import SensitivityGrid
from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

type Value = float | str


@dataclass(frozen=True)
class SensitivityRow:
    id: int
    symbol: str
    snapshot_id: int
    review_id: int | None
    created_at: datetime
    principal: Principal
    actor: str | None
    client: str | None
    row_tag: str
    col_tag: str
    row_values: tuple[Value, ...]
    col_values: tuple[Value, ...]
    cells: tuple[tuple[float | None, ...], ...]
    current: tuple[int, int] | None
    policy_version: str
    settings_hash: str


def insert_sensitivity(
    conn: sqlite3.Connection,
    symbol: str,
    snapshot_id: int,
    review_id: int | None,
    row_tag: str,
    col_tag: str,
    grid: SensitivityGrid,
    policy_version: str,
    settings_hash: str,
    writer: Writer,
    at: datetime,
) -> int:
    """Store ``grid`` of ``row_tag`` by ``col_tag`` on snapshot ``snapshot_id``; return its id."""
    current_row, current_col = (None, None) if grid.current is None else grid.current
    row = (
        symbol,
        snapshot_id,
        review_id,
        dump_stamp(at),
        writer.principal,
        writer.actor,
        writer.client,
        row_tag,
        col_tag,
        json.dumps(grid.rows, allow_nan=False),
        json.dumps(grid.cols, allow_nan=False),
        json.dumps(grid.cells, allow_nan=False),
        current_row,
        current_col,
        policy_version,
        settings_hash,
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO sensitivities (symbol, snapshot_id, review_id, created_at, principal,"
            " actor, client, row_tag, col_tag, row_values, col_values, cells, current_row,"
            " current_col, policy_version, settings_hash)"
            f" VALUES ({', '.join('?' * len(row))})",
            row,
        )
    return inserted_id(cursor)


def sensitivity_row(conn: sqlite3.Connection, sensitivity_id: int) -> SensitivityRow | None:
    """The reading ``sensitivity_id``, if there is one."""
    row = conn.execute("SELECT * FROM sensitivities WHERE id = ?", (sensitivity_id,)).fetchone()
    if row is None:
        return None
    current_row, current_col = row["current_row"], row["current_col"]
    return SensitivityRow(
        id=row["id"],
        symbol=row["symbol"],
        snapshot_id=row["snapshot_id"],
        review_id=row["review_id"],
        created_at=load_stamp(row["created_at"]),
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        row_tag=row["row_tag"],
        col_tag=row["col_tag"],
        row_values=tuple(json.loads(row["row_values"])),
        col_values=tuple(json.loads(row["col_values"])),
        cells=tuple(tuple(cells) for cells in json.loads(row["cells"])),
        current=None if current_row is None else (current_row, current_col),
        policy_version=row["policy_version"],
        settings_hash=row["settings_hash"],
    )
