"""The reviews and their log (spec 2026-11-06 Tier 2, 10.4 to 10.6; ``method.md`` 14.5 to 14.7).

A review is the engine's result under a company's applied overrides, stored on the snapshot it
follows as a snapshot is stored: ``result`` as ``result_to_json`` writes it, the value, the levels
and the mechanical value as ``repr`` text so each float reads back exactly, price ÷ value as a
REAL, the designation's word and the refusal; beside them the bridge's lines and the ids of the
overrides inside as JSON, the refresh that wrote it (``None`` for an override's or a drop's own
recompute), the review method, and the policy version, method version, settings hash and
deciles refresh it ran under. A review is never replaced: each snapshot a company's reviews follow
gets one of its own.

A review has a kind (spec 2026-11-23 held reviewed value, 5.1 to 5.4). A ``made`` review is
written by a deliberate act: an override's write or drop, a moat class's write, or Review again.
A ``held`` review is a made one that a refresh carried onto a newer snapshot; ``made_id`` names
the made review. A ``reading`` is what the review gives on a newer snapshot, computed by a
refresh; ``made_id`` names the made review it reads again. ``ReviewRow.held_id`` is the made
review's id on each of the three.

The table ``held_reviews`` has one row for a company that holds a review (``HeldRow``): its made
review and when it was made, and the facts a refresh stores for its state (5.3): the first time a
valuing refresh read it again, the newer period's end, the overrides the system dropped (each
``{id, tag, reason, at}``), the newest good reading's value or its refusal with its time, and the
day a refresh first found a reason. ``insert_review`` names a made review as the held one in the
same transaction (``hold_review``), its state empty; ``clear_held`` removes the row, and
``set_held_state`` writes the facts.

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
from datetime import date, datetime
from typing import Any, Literal

from fairband.config import utcnow
from fairband.engine.review import REVIEW_METHOD, Review
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

# A company's reviews count while it holds an applied override.
_CURRENT = "symbol IN (SELECT symbol FROM overrides WHERE state = 'applied')"

ReviewKind = Literal["made", "held", "reading"]


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
    kind: ReviewKind = "made"
    made_id: int | None = None

    @property
    def held_id(self) -> int:
        """The made review this row is, copies or reads again: ``made_id``, else its own id."""
        return self.id if self.made_id is None else self.made_id


@dataclass(frozen=True)
class HeldRow:
    """The review a company holds, and the facts of its state (module docstring)."""

    symbol: str
    review_id: int
    made_at: datetime
    read_again_at: datetime | None
    newer_period: date | None
    dropped: tuple[dict[str, Any], ...]
    reading_value: float | None
    reading_refusal: str | None
    reading_at: datetime | None
    early_at: date | None


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
    kind: str | None = None


def insert_review(
    conn: sqlite3.Connection,
    review: Review,
    symbol: str,
    snapshot_id: int,
    refresh_id: int | None,
    *,
    kind: ReviewKind = "made",
    made_id: int | None = None,
    clock: Callable[[], datetime] = utcnow,
) -> int:
    """Append the review on snapshot ``snapshot_id``, written by refresh ``refresh_id`` (``None``
    outside a refresh); return its id. A ``made`` review becomes the one the company holds, in the
    same transaction (``hold_review``); a ``held`` copy and a ``reading`` name their made review
    in ``made_id`` and leave the held one as it is. A result ``result_to_json`` refuses raises
    ``ValueError`` before any write."""
    result, levels = review.result, review.result.levels
    at = clock()
    row = (
        symbol,
        snapshot_id,
        refresh_id,
        dump_stamp(at),
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
        kind,
        None if kind == "made" else made_id,
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO reviews (symbol, snapshot_id, refresh_id, created_at, value, buy_level,"
            " fair_low, fair_high, trim_level, price_to_value, designation, refusal,"
            " mechanical_value, bridge, override_ids, policy_version, method_version,"
            " review_method, settings_hash, deciles_refresh_id, result, kind, made_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
        review_id = inserted_id(cursor)
        if kind == "made":
            hold_review(conn, symbol, review_id, at)
    return review_id


def hold_review(conn: sqlite3.Connection, symbol: str, review_id: int, at: datetime) -> None:
    """Name the made review ``review_id`` as the one ``symbol`` holds, made ``at``, with an empty
    state: the facts stored for the review it held before are gone with it."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO held_reviews (symbol, review_id, made_at) VALUES (?, ?, ?)"
            " ON CONFLICT (symbol) DO UPDATE SET review_id = excluded.review_id,"
            " made_at = excluded.made_at, read_again_at = NULL, newer_period = NULL,"
            " dropped = '[]', reading_value = NULL, reading_refusal = NULL, reading_at = NULL,"
            " early_at = NULL",
            (symbol, review_id, dump_stamp(at)),
        )


def clear_held(conn: sqlite3.Connection, symbol: str) -> None:
    """The company holds no review from here on; one that holds none stays so. Its reviews stay
    on file."""
    with transaction(conn):
        conn.execute("DELETE FROM held_reviews WHERE symbol = ?", (symbol,))


def held_row(conn: sqlite3.Connection, symbol: str) -> HeldRow | None:
    """The review the company holds with the facts of its state, if it holds one."""
    row = conn.execute("SELECT * FROM held_reviews WHERE symbol = ?", (symbol,)).fetchone()
    return None if row is None else _held(row)


def held_rows(conn: sqlite3.Connection) -> dict[str, HeldRow]:
    """The held review of every company that holds one, by symbol."""
    rows = conn.execute("SELECT * FROM held_reviews ORDER BY symbol")
    return {r["symbol"]: _held(r) for r in rows}


def set_held_state(conn: sqlite3.Connection, state: HeldRow) -> None:
    """Write the facts of ``state`` on its company's row, when the company still holds the review
    ``state`` names: a review made since keeps its own, empty state."""
    with transaction(conn):
        conn.execute(
            "UPDATE held_reviews SET read_again_at = ?, newer_period = ?, dropped = ?,"
            " reading_value = ?, reading_refusal = ?, reading_at = ?, early_at = ?"
            " WHERE symbol = ? AND review_id = ?",
            (
                dump_stamp(state.read_again_at),
                dump_date(state.newer_period),
                json.dumps(list(state.dropped), allow_nan=False),
                dump_float(state.reading_value),
                state.reading_refusal,
                dump_stamp(state.reading_at),
                dump_date(state.early_at),
                state.symbol,
                state.review_id,
            ),
        )


def latest_review(conn: sqlite3.Connection, symbol: str) -> ReviewRow | None:
    """The company's current review (module docstring), if it has one."""
    row = conn.execute(
        f"SELECT * FROM reviews WHERE symbol = ? AND {_CURRENT} ORDER BY id DESC LIMIT 1",
        (symbol,),
    ).fetchone()
    return None if row is None else _review(row)


def review_row(conn: sqlite3.Connection, review_id: int) -> ReviewRow | None:
    """The review ``review_id``, current or not, if there is one."""
    row = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,)).fetchone()
    return None if row is None else _review(row)


def latest_review_on(conn: sqlite3.Connection, snapshot_id: int) -> ReviewRow | None:
    """The newest review written on the snapshot ``snapshot_id``, current or not, if any."""
    row = conn.execute(
        "SELECT * FROM reviews WHERE snapshot_id = ? ORDER BY id DESC LIMIT 1", (snapshot_id,)
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
    kind: ReviewKind | None = None,
) -> int:
    """Append the review's log row, with the review's ``kind``; return its id."""
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
        kind,
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO review_log (at, symbol, refresh_id, snapshot_id, review_id,"
            " mechanical_phase, mechanical_value, reviewed_phase, reviewed_value,"
            " secondary_value, price, designation, stance, kind)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        kind=row["kind"],
        made_id=row["made_id"],
    )


def _held(row: sqlite3.Row) -> HeldRow:
    return HeldRow(
        symbol=row["symbol"],
        review_id=row["review_id"],
        made_at=load_stamp(row["made_at"]),
        read_again_at=load_stamp(row["read_again_at"]),
        newer_period=load_date(row["newer_period"]),
        dropped=tuple(json.loads(row["dropped"])),
        reading_value=load_float(row["reading_value"]),
        reading_refusal=row["reading_refusal"],
        reading_at=load_stamp(row["reading_at"]),
        early_at=load_date(row["early_at"]),
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
        kind=row["kind"],
    )
