"""The valuations: one snapshot per company per refresh, never replaced.

``result`` holds the whole ``ValuationResult`` as ``result_to_json`` writes it. The other columns
copy the fields the screen sorts and filters on: the value, the levels and the price as ``repr``
text, so each float reads back exactly, price ÷ value as a REAL (the double itself, also exact),
the designation's word, ``flags`` as a JSON list of the flag codes, and the policy version,
method version and settings hash the result cites. The ``stance5`` and ``stance3`` columns of
method 0.5 are no longer written: a new row leaves them NULL. The screen reads the snapshot with
the greatest id per symbol, the snapshots its agents' records rest on in one read
(``snapshot_rows``), and the Settings page the versions most of the screen's cite. A review reads
the snapshot that assembled a snapshot's figures (``assembling_snapshot``) to know which splits
they had seen (spec 2026-11-14 7). The report
page's price chart and the export's table twin of it read a company's band over time from the
copied columns alone (``band_points``), never parsing a result.
"""

import json
import sqlite3
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from fairband.config import utcnow
from fairband.engine.types import Levels, ValuationResult, result_from_json, result_to_json
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


def assembling_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> SnapshotRow | None:
    """The snapshot that assembled the figures snapshot ``snapshot_id`` carries: itself when a full
    or scoped refresh or a revalue wrote it, else, for a price refresh's, the company's latest
    earlier snapshot one of those wrote (a price refresh reprices a snapshot's figures and
    assembles none); ``None`` when there is no such snapshot, or no snapshot ``snapshot_id``."""
    row = conn.execute(
        "SELECT s.* FROM snapshots s JOIN refreshes r ON r.id = s.refresh_id"
        " WHERE s.symbol = (SELECT symbol FROM snapshots WHERE id = ?) AND s.id <= ?"
        " AND r.kind IN ('full', 'scoped', 'revalue') ORDER BY s.id DESC LIMIT 1",
        (snapshot_id, snapshot_id),
    ).fetchone()
    return None if row is None else _snapshot(row)


def snapshot_rows(conn: sqlite3.Connection, ids: Collection[int]) -> dict[int, SnapshotRow]:
    """The snapshots of ``ids`` that exist, by id, in one read; none for no id, with no read."""
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT * FROM snapshots WHERE id IN (SELECT value FROM json_each(?))",
        (json.dumps(sorted(ids)),),
    )
    return {r["id"]: _snapshot(r) for r in rows}


def refresh_snapshots(conn: sqlite3.Connection, refresh_id: int) -> list[SnapshotRow]:
    """The snapshots refresh ``refresh_id`` wrote, ordered by symbol."""
    rows = conn.execute(
        "SELECT * FROM snapshots WHERE refresh_id = ? ORDER BY symbol, id", (refresh_id,)
    )
    return [_snapshot(r) for r in rows]


@dataclass(frozen=True)
class BandPoint:
    """A snapshot's price and its levels on the day it was priced; no levels on a refusal."""

    snapshot_id: int
    day: date
    price: float | None
    levels: Levels | None


def band_points(conn: sqlite3.Connection, symbol: str) -> list[BandPoint]:
    """The company's snapshots that carry a price date, oldest day first, the newest snapshot of
    each day (the greatest id); none before the first (spec 2026-11-06 Tier 2, 18.4)."""
    rows = conn.execute(
        "SELECT id, price_date, price, buy_level, fair_low, fair_high, trim_level FROM snapshots"
        " WHERE id IN (SELECT MAX(id) FROM snapshots WHERE symbol = ? AND price_date IS NOT NULL"
        " GROUP BY price_date) ORDER BY price_date",
        (symbol,),
    )
    return [_band_point(r) for r in rows]


def _band_point(row: sqlite3.Row) -> BandPoint:
    buy, low, high, trim = (
        load_float(row[name]) for name in ("buy_level", "fair_low", "fair_high", "trim_level")
    )
    levels = None
    if buy is not None and low is not None and high is not None and trim is not None:
        levels = Levels(buy=buy, fair_low=low, fair_high=high, trim=trim)
    day = date.fromisoformat(row["price_date"])  # the query reads only rows with one
    return BandPoint(row["id"], day, load_float(row["price"]), levels)


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
