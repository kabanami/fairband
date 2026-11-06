"""The ledger: one row for every write the owner, an agent or the system makes (spec 2026-11-06
Tier 2, section 7).

A row names its writer: the principal, and for an agent the model identifier it runs as (the
actor) and its client's name and version. It names the kind of write (``note``, ``finding``,
``override``, ``work-item``, ``claim`` and the others of spec 7), the company when there is one,
the record it points to by table and id (neither for a write that stored no record, as a rejected
report stores none), what the write rested on (the company's snapshot and, when there is one, the
work item), and one line of summary. Rows are appended, never changed, and read newest first.
``record`` joins the caller's transaction when it holds one, so a record and its ledger row
commit together or not at all.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction

Principal = Literal["owner", "agent", "system"]


@dataclass(frozen=True)
class Writer:
    """Who makes a write: the principal, and an agent's model identifier and client."""

    principal: Principal
    actor: str | None
    client: str | None


OWNER = Writer("owner", None, None)
SYSTEM = Writer("system", None, None)


@dataclass(frozen=True)
class LedgerRow:
    id: int
    at: datetime
    principal: Principal
    actor: str | None
    client: str | None
    kind: str
    symbol: str | None
    ref_table: str | None
    ref_id: int | None
    snapshot_id: int | None
    work_item_id: int | None
    summary: str


def record(
    conn: sqlite3.Connection,
    writer: Writer,
    at: datetime,
    kind: str,
    symbol: str | None,
    ref_table: str | None,
    ref_id: int | None,
    *,
    snapshot_id: int | None = None,
    work_item_id: int | None = None,
    summary: str,
) -> int:
    """Append the write to the ledger; return the row's id. The reference names its table and
    its id together, or neither."""
    if (ref_table is None) != (ref_id is None):
        raise ValueError("a ledger reference names its table and its id together")
    row = (
        dump_stamp(at),
        writer.principal,
        writer.actor,
        writer.client,
        kind,
        symbol,
        ref_table,
        ref_id,
        snapshot_id,
        work_item_id,
        summary,
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO ledger (at, principal, actor, client, kind, symbol, ref_table, ref_id,"
            " snapshot_id, work_item_id, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    return inserted_id(cursor)


def entries(
    conn: sqlite3.Connection, symbol: str | None = None, limit: int = 100
) -> list[LedgerRow]:
    """The newest ``limit`` rows, newest first: the company's when ``symbol`` names one, else
    every row."""
    if symbol is None:
        rows = conn.execute("SELECT * FROM ledger ORDER BY id DESC LIMIT ?", (limit,))
    else:
        rows = conn.execute(
            "SELECT * FROM ledger WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol, limit)
        )
    return [_row(r) for r in rows]


def _row(row: sqlite3.Row) -> LedgerRow:
    return LedgerRow(
        id=row["id"],
        at=load_stamp(row["at"]),
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        kind=row["kind"],
        symbol=row["symbol"],
        ref_table=row["ref_table"],
        ref_id=row["ref_id"],
        snapshot_id=row["snapshot_id"],
        work_item_id=row["work_item_id"],
        summary=row["summary"],
    )
