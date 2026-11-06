"""The reviews and their log (spec 2026-11-06 Tier 2, 10.4 to 10.6; ``method.md`` 14.5 to 14.7).

A review is the engine's result under a company's applied overrides, stored on the snapshot it
follows as a snapshot is stored: ``result`` as ``result_to_json`` writes it, the value, the levels
and the mechanical value as ``repr`` text so each float reads back exactly, price ÷ value as a
REAL, the designation's word and the refusal; beside them the bridge's lines and the ids of the
overrides inside as JSON, the refresh that wrote it (``None`` for an override's or a drop's own
recompute), ``fairband-review/1``, and the policy version, method version, settings hash and
deciles refresh it ran under. A review is never replaced: each snapshot a company's reviews follow
gets one of its own.

The company's current review (``latest_review``, ``latest_reviews``) is its newest while an
override is applied: a drop of the last one clears it, as a period-tied override dropped at a
refresh with none left does, and no review is written in its place.

The log keeps one row for each review written (10.6): the time, the company, the refresh, the
snapshot and the review; the mechanical phase and value; the reviewed phase and value (no value on
a refusal); the latest secondary value; the price; the mechanical designation; and the latest
report's stance. ``latest_secondary_value`` and ``latest_stance`` read the two figures from the
``secondary_valuations`` and ``reports`` tables, ``None`` while a company has none.
"""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from fairband.config import utcnow
from fairband.engine.review import REVIEW_METHOD, Review
from fairband.engine.types import ValuationResult, result_from_json, result_to_json
from fairband.store._codec import dump_float, dump_stamp, inserted_id, load_float, load_stamp
from fairband.store.db import transaction

# A company's reviews count while it holds an applied override.
_CURRENT = "symbol IN (SELECT symbol FROM overrides WHERE state = 'applied')"


@dataclass(frozen=True)
class ReviewRow:
    id: int
    symbol: str
    snapshot_id: int
    refresh_id: int | None
    created_at: datetime
    value: float | None
    buy_level: float | None
    fair_low: float | None
    fair_high: float | None
    trim_level: float | None
    price_to_value: float | None
    designation: str | None
    refusal: str | None
    mechanical_value: float | None
    bridge: tuple[dict[str, Any], ...]
    override_ids: tuple[int, ...]
    policy_version: str
    method_version: str
    review_method: str
    settings_hash: str
    deciles_refresh_id: int | None
    result: ValuationResult


@dataclass(frozen=True)
class LogRow:
    id: int
    at: datetime
    symbol: str
    refresh_id: int | None
    snapshot_id: int
    review_id: int
    mechanical_phase: str | None
    mechanical_value: float | None
    reviewed_phase: str | None
    reviewed_value: float | None
    secondary_value: float | None
    price: float | None
    designation: str | None
    stance: str | None


def insert_review(
    conn: sqlite3.Connection,
    review: Review,
    symbol: str,
    snapshot_id: int,
    refresh_id: int | None,
    *,
    clock: Callable[[], datetime] = utcnow,
) -> int:
    """Append the review on snapshot ``snapshot_id``, written by refresh ``refresh_id`` (``None``
    outside a refresh); return its id. A result ``result_to_json`` refuses raises ``ValueError``
    before any write."""
    result, levels = review.result, review.result.levels
    row = (
        symbol,
        snapshot_id,
        refresh_id,
        dump_stamp(clock()),
        dump_float(result.value),
        dump_float(None if levels is None else levels.buy),
        dump_float(None if levels is None else levels.fair_low),
        dump_float(None if levels is None else levels.fair_high),
        dump_float(None if levels is None else levels.trim),
        result.price_to_value,
        result.designation,
        result.refusal,
        dump_float(review.mechanical_value),
        json.dumps([asdict(line) for line in review.bridge], allow_nan=False),
        json.dumps(list(review.override_ids)),
        result.policy_version,
        result.method_version,
        REVIEW_METHOD,
        result.settings_hash,
        result.deciles_refresh_id,
        result_to_json(result),
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO reviews (symbol, snapshot_id, refresh_id, created_at, value, buy_level,"
            " fair_low, fair_high, trim_level, price_to_value, designation, refusal,"
            " mechanical_value, bridge, override_ids, policy_version, method_version,"
            " review_method, settings_hash, deciles_refresh_id, result)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    return inserted_id(cursor)


def latest_review(conn: sqlite3.Connection, symbol: str) -> ReviewRow | None:
    """The company's current review (module docstring), if it has one."""
    row = conn.execute(
        f"SELECT * FROM reviews WHERE symbol = ? AND {_CURRENT} ORDER BY id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    return None if row is None else _review(row)


def reviews_for(conn: sqlite3.Connection, symbol: str) -> list[ReviewRow]:
    """Every review of the company, newest first."""
    rows = conn.execute("SELECT * FROM reviews WHERE symbol = ? ORDER BY id DESC", (symbol,))
    return [_review(r) for r in rows]


def latest_reviews(conn: sqlite3.Connection) -> dict[str, ReviewRow]:
    """The current review of every company that has one, by symbol."""
    rows = conn.execute(
        "SELECT * FROM reviews WHERE id IN (SELECT MAX(id) FROM reviews GROUP BY symbol)"
        f" AND {_CURRENT} ORDER BY symbol"
    )
    return {r["symbol"]: _review(r) for r in rows}


def log_review(
    conn: sqlite3.Connection,
    at: datetime,
    symbol: str,
    refresh_id: int | None,
    snapshot_id: int,
    review_id: int,
    mechanical_phase: str | None,
    mechanical_value: float | None,
    reviewed_phase: str | None,
    reviewed_value: float | None,
    secondary_value: float | None,
    price: float | None,
    designation: str | None,
    stance: str | None,
) -> int:
    """Append the review's log row; return its id."""
    row = (
        dump_stamp(at),
        symbol,
        refresh_id,
        snapshot_id,
        review_id,
        mechanical_phase,
        dump_float(mechanical_value),
        reviewed_phase,
        dump_float(reviewed_value),
        dump_float(secondary_value),
        dump_float(price),
        designation,
        stance,
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO review_log (at, symbol, refresh_id, snapshot_id, review_id,"
            " mechanical_phase, mechanical_value, reviewed_phase, reviewed_value,"
            " secondary_value, price, designation, stance)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    return inserted_id(cursor)


def review_log(conn: sqlite3.Connection, symbol: str | None = None) -> list[LogRow]:
    """The log's rows, newest first: the company's when ``symbol`` names one, else every row."""
    if symbol is None:
        rows = conn.execute("SELECT * FROM review_log ORDER BY id DESC")
    else:
        rows = conn.execute("SELECT * FROM review_log WHERE symbol = ? ORDER BY id DESC", (symbol,))
    return [_log(r) for r in rows]


def latest_secondary_value(conn: sqlite3.Connection, symbol: str) -> float | None:
    """The value a share of the company's newest secondary valuation; ``None`` without one."""
    row = conn.execute(
        "SELECT value_per_share FROM secondary_valuations WHERE symbol = ?"
        " ORDER BY id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    return None if row is None else load_float(row["value_per_share"])


def latest_stance(conn: sqlite3.Connection, symbol: str) -> str | None:
    """The stance of the company's newest report; ``None`` without one."""
    row = conn.execute(
        "SELECT stance FROM reports WHERE symbol = ? ORDER BY id DESC LIMIT 1", (symbol,)
    ).fetchone()
    return None if row is None else str(row["stance"])


def _review(row: sqlite3.Row) -> ReviewRow:
    return ReviewRow(
        id=row["id"],
        symbol=row["symbol"],
        snapshot_id=row["snapshot_id"],
        refresh_id=row["refresh_id"],
        created_at=load_stamp(row["created_at"]),
        value=load_float(row["value"]),
        buy_level=load_float(row["buy_level"]),
        fair_low=load_float(row["fair_low"]),
        fair_high=load_float(row["fair_high"]),
        trim_level=load_float(row["trim_level"]),
        price_to_value=row["price_to_value"],
        designation=row["designation"],
        refusal=row["refusal"],
        mechanical_value=load_float(row["mechanical_value"]),
        bridge=tuple(json.loads(row["bridge"])),
        override_ids=tuple(json.loads(row["override_ids"])),
        policy_version=row["policy_version"],
        method_version=row["method_version"],
        review_method=row["review_method"],
        settings_hash=row["settings_hash"],
        deciles_refresh_id=row["deciles_refresh_id"],
        result=result_from_json(row["result"]),
    )


def _log(row: sqlite3.Row) -> LogRow:
    return LogRow(
        id=row["id"],
        at=load_stamp(row["at"]),
        symbol=row["symbol"],
        refresh_id=row["refresh_id"],
        snapshot_id=row["snapshot_id"],
        review_id=row["review_id"],
        mechanical_phase=row["mechanical_phase"],
        mechanical_value=load_float(row["mechanical_value"]),
        reviewed_phase=row["reviewed_phase"],
        reviewed_value=load_float(row["reviewed_value"]),
        secondary_value=load_float(row["secondary_value"]),
        price=load_float(row["price"]),
        designation=row["designation"],
        stance=row["stance"],
    )
