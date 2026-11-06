"""The valuations: one snapshot per company per refresh, never replaced.

``result`` holds the whole ``ValuationResult`` as ``result_to_json`` writes it. The other columns
copy the fields the screen sorts and filters on: the value, the levels and the price as ``repr``
text, so each float reads back exactly, price ÷ value as a REAL (the double itself, also exact),
the designation's word, ``flags`` as a JSON list of the flag codes, and the policy version,
method version and settings hash the result cites. The ``stance5`` and ``stance3`` columns of
method 0.5 are no longer written: a new row leaves them NULL. The screen reads the snapshot with
the greatest id per symbol, and the Settings page the versions most of the screen's cite.
"""

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from fairband.config import utcnow
from fairband.engine.types import ValuationResult, result_from_json, result_to_json
from fairband.store._codec import (
    dump_date,
    dump_float,
    dump_stamp,
    inserted_id,
    load_date,
    load_float,
    load_stamp,
)
from fairband.store.db import transaction


@dataclass(frozen=True)
class SnapshotRow:
    id: int
    symbol: str
    refresh_id: int
    deciles_refresh_id: int | None
    created_at: datetime
    phase: str | None
    route: str | None
    value: float | None
    buy_level: float | None
    fair_low: float | None
    fair_high: float | None
    trim_level: float | None
    price: float | None
    price_to_value: float | None
    designation: str | None
    price_date: date | None
    data_date: date
    valid_until: date
    flags: tuple[str, ...]
    refusal: str | None
    policy_version: str
    method_version: str
    settings_hash: str
    result: ValuationResult


def insert_snapshot(
    conn: sqlite3.Connection,
    result: ValuationResult,
    refresh_id: int,
    *,
    clock: Callable[[], datetime] = utcnow,
) -> int:
    """Append the result as refresh ``refresh_id``'s snapshot of its company; return its id.

    A result ``result_to_json`` refuses (a NaN or infinity) raises ``ValueError`` before any write.
    """
    levels = result.levels
    row = (
        result.symbol,
        refresh_id,
        result.deciles_refresh_id,
        dump_stamp(clock()),
        result.phase.phase,
        result.route,
        dump_float(result.value),
        dump_float(None if levels is None else levels.buy),
        dump_float(None if levels is None else levels.fair_low),
        dump_float(None if levels is None else levels.fair_high),
        dump_float(None if levels is None else levels.trim),
        dump_float(result.price),
        result.price_to_value,
        result.designation,
        dump_date(result.price_date),
        dump_date(result.data_date),
        dump_date(result.valid_until),
        json.dumps([f.code for f in result.flags]),
        result.refusal,
        result.policy_version,
        result.method_version,
        result.settings_hash,
        result_to_json(result),
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO snapshots (symbol, refresh_id, deciles_refresh_id, created_at, phase,"
            " route, value, buy_level, fair_low, fair_high, trim_level, price, price_to_value,"
            " designation, price_date, data_date, valid_until, flags, refusal, policy_version,"
            " method_version, settings_hash, result)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    return inserted_id(cursor)


def latest_snapshots(conn: sqlite3.Connection) -> list[SnapshotRow]:
    """The newest snapshot of every company, ordered by symbol."""
    rows = conn.execute(
        "SELECT * FROM snapshots WHERE id IN (SELECT MAX(id) FROM snapshots GROUP BY symbol)"
        " ORDER BY symbol"
    )
    return [_snapshot(r) for r in rows]


def latest_versions(
    conn: sqlite3.Connection, symbols: Sequence[str] | None = None
) -> tuple[str, str] | None:
    """The policy version and settings hash that most of the newest snapshots cite, one per
    company of ``symbols`` (every company with a snapshot when ``None``); on a tie, the pair of
    the newest snapshot. ``None`` when none of them has a snapshot."""
    among = "" if symbols is None else " AND symbol IN (SELECT value FROM json_each(?))"
    params = () if symbols is None else (json.dumps(list(symbols)),)
    row = conn.execute(
        "SELECT policy_version, settings_hash FROM snapshots"
        f" WHERE id IN (SELECT MAX(id) FROM snapshots GROUP BY symbol){among}"
        " GROUP BY policy_version, settings_hash ORDER BY COUNT(*) DESC, MAX(id) DESC LIMIT 1",
        params,
    ).fetchone()
    return None if row is None else (row["policy_version"], row["settings_hash"])


def latest_snapshot(conn: sqlite3.Connection, symbol: str) -> SnapshotRow | None:
    """The company's newest snapshot, if it has one."""
    row = conn.execute(
        "SELECT * FROM snapshots WHERE symbol = ? ORDER BY id DESC LIMIT 1", (symbol,)
    ).fetchone()
    return None if row is None else _snapshot(row)


def snapshot_row(conn: sqlite3.Connection, snapshot_id: int) -> SnapshotRow | None:
    """The snapshot ``snapshot_id``, if there is one."""
    row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    return None if row is None else _snapshot(row)


def refresh_snapshots(conn: sqlite3.Connection, refresh_id: int) -> list[SnapshotRow]:
    """The snapshots refresh ``refresh_id`` wrote, ordered by symbol."""
    rows = conn.execute(
        "SELECT * FROM snapshots WHERE refresh_id = ? ORDER BY symbol, id", (refresh_id,)
    )
    return [_snapshot(r) for r in rows]


def _snapshot(row: sqlite3.Row) -> SnapshotRow:
    return SnapshotRow(
        id=row["id"],
        symbol=row["symbol"],
        refresh_id=row["refresh_id"],
        deciles_refresh_id=row["deciles_refresh_id"],
        created_at=load_stamp(row["created_at"]),
        phase=row["phase"],
        route=row["route"],
        value=load_float(row["value"]),
        buy_level=load_float(row["buy_level"]),
        fair_low=load_float(row["fair_low"]),
        fair_high=load_float(row["fair_high"]),
        trim_level=load_float(row["trim_level"]),
        price=load_float(row["price"]),
        price_to_value=row["price_to_value"],
        designation=row["designation"],
        price_date=load_date(row["price_date"]),
        data_date=load_date(row["data_date"]),
        valid_until=load_date(row["valid_until"]),
        flags=tuple(json.loads(row["flags"])),
        refusal=row["refusal"],
        policy_version=row["policy_version"],
        method_version=row["method_version"],
        settings_hash=row["settings_hash"],
        result=result_from_json(row["result"]),
    )
