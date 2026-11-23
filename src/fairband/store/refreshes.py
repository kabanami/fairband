"""The refresh record, its per-company progress and the universe deciles each full refresh saves.

``refreshes`` holds one row per run; its status is ``running`` until ``finish_refresh`` sets
``done``, ``failed`` or ``cancelled``, or ``mark_interrupted`` finds it after a stop and sets
``interrupted``. One refresh runs at a time: ``create_refresh`` raises ``RefreshRunning`` while a
row is ``running``. Each row records the policy version, the method version and the settings hash
the run reads. ``refresh_items`` holds each company's latest status within a refresh, and
``deciles`` the decile edges as JSON lists of floats. Apart from the user's settings and
watchlists and the moat table, these are the only rows the store updates.
"""

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from fairband.engine.classifier import Deciles
from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction

type Finished = Literal["done", "failed", "interrupted", "cancelled"]


class RefreshRunning(Exception):
    """A refresh is already running; ``refresh_id`` names it."""

    def __init__(self, refresh_id: int) -> None:
        super().__init__(f"refresh {refresh_id} is running")
        self.refresh_id = refresh_id


@dataclass(frozen=True)
class RefreshRow:
    id: int
    kind: str
    symbols: tuple[str, ...] | None
    status: str
    stage: str | None
    started_at: datetime
    finished_at: datetime | None
    policy_version: str
    method_version: str
    settings_hash: str
    calibration: dict[str, Any] | None
    message: str | None


@dataclass(frozen=True)
class ItemRow:
    refresh_id: int
    symbol: str
    status: str
    error: str | None
    updated_at: datetime


def create_refresh(
    conn: sqlite3.Connection,
    kind: str,
    symbols: Sequence[str] | None,
    policy_version: str,
    method_version: str,
    started_at: datetime,
    settings_hash: str,
) -> int:
    """Start a ``running`` refresh and return its id. Called outside a transaction, it takes the
    write lock before the check, so two connections cannot both start one."""
    stored_symbols = None if symbols is None else json.dumps(list(symbols))
    with transaction(conn, immediate=True):
        running = conn.execute(
            "SELECT id FROM refreshes WHERE status = 'running' ORDER BY id LIMIT 1"
        ).fetchone()
        if running is not None:
            raise RefreshRunning(int(running["id"]))
        cursor = conn.execute(
            "INSERT INTO refreshes (kind, symbols, status, started_at, policy_version,"
            " method_version, settings_hash) VALUES (?, ?, 'running', ?, ?, ?, ?)",
            (
                kind,
                stored_symbols,
                dump_stamp(started_at),
                policy_version,
                method_version,
                settings_hash,
            ),
        )
    return inserted_id(cursor)


def set_stage(conn: sqlite3.Connection, refresh_id: int, stage: str) -> None:
    with transaction(conn):
        cursor = conn.execute("UPDATE refreshes SET stage = ? WHERE id = ?", (stage, refresh_id))
        _require_one(cursor, refresh_id)


def finish_refresh(
    conn: sqlite3.Connection,
    refresh_id: int,
    status: Finished,
    finished_at: datetime,
    message: str | None = None,
    calibration: dict[str, Any] | None = None,
) -> None:
    """Close the refresh with its status, finish time, message and calibration counts."""
    stored_calibration = (
        None if calibration is None else json.dumps(calibration, sort_keys=True, allow_nan=False)
    )
    with transaction(conn):
        cursor = conn.execute(
            "UPDATE refreshes SET status = ?, finished_at = ?, message = ?, calibration = ?"
            " WHERE id = ?",
            (status, dump_stamp(finished_at), message, stored_calibration, refresh_id),
        )
        _require_one(cursor, refresh_id)


def upsert_item(
    conn: sqlite3.Connection,
    refresh_id: int,
    symbol: str,
    status: str,
    error: str | None,
    updated_at: datetime,
) -> None:
    """Record the company's status within the refresh, replacing its earlier status."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO refresh_items (refresh_id, symbol, status, error, updated_at)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT (refresh_id, symbol) DO UPDATE"
            " SET status = excluded.status, error = excluded.error,"
            " updated_at = excluded.updated_at",
            (refresh_id, symbol, status, error, dump_stamp(updated_at)),
        )


def items(conn: sqlite3.Connection, refresh_id: int) -> list[ItemRow]:
    """The refresh's companies, ordered by symbol."""
    rows = conn.execute(
        "SELECT * FROM refresh_items WHERE refresh_id = ? ORDER BY symbol", (refresh_id,)
    )
    return [
        ItemRow(
            refresh_id=r["refresh_id"],
            symbol=r["symbol"],
            status=r["status"],
            error=r["error"],
            updated_at=load_stamp(r["updated_at"]),
        )
        for r in rows
    ]


def current_refresh(conn: sqlite3.Connection) -> RefreshRow | None:
    """The ``running`` refresh, if any."""
    row = conn.execute(
        "SELECT * FROM refreshes WHERE status = 'running' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return None if row is None else _refresh(row)


def latest_refresh(conn: sqlite3.Connection) -> RefreshRow | None:
    """The refresh with the greatest id, whatever its status."""
    row = conn.execute("SELECT * FROM refreshes ORDER BY id DESC LIMIT 1").fetchone()
    return None if row is None else _refresh(row)


def recent_refreshes(conn: sqlite3.Connection, limit: int = 20) -> list[RefreshRow]:
    """The ``limit`` refreshes with the greatest ids, the newest first, whatever their status:
    the page reads them to follow a run that ended between two of its reads (spec 2026-11-23
    refresh experience, 4.3)."""
    rows = conn.execute("SELECT * FROM refreshes ORDER BY id DESC LIMIT ?", (limit,))
    return [_refresh(row) for row in rows]


def latest_shown_refresh(conn: sqlite3.Connection) -> RefreshRow | None:
    """The refresh the page's status line describes: the one with the greatest id, passing over
    a revalue that names its companies and finished ``done``. A moat write records such a revalue
    of one company (spec 2026-11-19 8.6), and the line stays about the last run of the whole
    screen (the founder, 2026-11-22). A named revalue that did not end ``done`` is not passed
    over, since the line says how a run ended."""
    row = conn.execute(
        "SELECT * FROM refreshes"
        " WHERE NOT (kind = 'revalue' AND symbols IS NOT NULL AND status = 'done')"
        " ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return None if row is None else _refresh(row)


def latest_full_refresh(conn: sqlite3.Connection) -> RefreshRow | None:
    """The full refresh with the greatest id among those that finished ``done``."""
    row = conn.execute(
        "SELECT * FROM refreshes WHERE kind = 'full' AND status = 'done' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return None if row is None else _refresh(row)


def mark_interrupted(conn: sqlite3.Connection, at: datetime) -> int:
    """Set every ``running`` refresh to ``interrupted``, finished ``at``; return how many."""
    with transaction(conn):
        cursor = conn.execute(
            "UPDATE refreshes SET status = 'interrupted', finished_at = ? WHERE status = 'running'",
            (dump_stamp(at),),
        )
    return cursor.rowcount


def save_deciles(conn: sqlite3.Connection, refresh_id: int, deciles: Deciles, at: datetime) -> None:
    """Store the deciles under ``refresh_id`` (the object's own ``refresh_id`` is not read)."""
    with transaction(conn):
        conn.execute(
            "INSERT INTO deciles (refresh_id, growth_edges, margin_slope_edges, n_growth,"
            " n_margin, computed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                refresh_id,
                json.dumps(list(deciles.growth_edges), allow_nan=False),
                json.dumps(list(deciles.margin_slope_edges), allow_nan=False),
                deciles.n_growth,
                deciles.n_margin,
                dump_stamp(at),
            ),
        )


def latest_deciles(conn: sqlite3.Connection) -> Deciles | None:
    """The deciles of the greatest refresh id, citing that refresh."""
    row = conn.execute("SELECT * FROM deciles ORDER BY refresh_id DESC LIMIT 1").fetchone()
    if row is None:
        return None
    return Deciles(
        growth_edges=tuple(float(x) for x in json.loads(row["growth_edges"])),
        margin_slope_edges=tuple(float(x) for x in json.loads(row["margin_slope_edges"])),
        n_growth=row["n_growth"],
        n_margin=row["n_margin"],
        refresh_id=row["refresh_id"],
    )


def _require_one(cursor: sqlite3.Cursor, refresh_id: int) -> None:
    if cursor.rowcount != 1:
        raise ValueError(f"no refresh {refresh_id}")


def _refresh(row: sqlite3.Row) -> RefreshRow:
    symbols, calibration = row["symbols"], row["calibration"]
    return RefreshRow(
        id=row["id"],
        kind=row["kind"],
        symbols=None if symbols is None else tuple(json.loads(symbols)),
        status=row["status"],
        stage=row["stage"],
        started_at=load_stamp(row["started_at"]),
        finished_at=load_stamp(row["finished_at"]),
        policy_version=row["policy_version"],
        method_version=row["method_version"],
        settings_hash=row["settings_hash"],
        calibration=None if calibration is None else json.loads(calibration),
        message=row["message"],
    )
