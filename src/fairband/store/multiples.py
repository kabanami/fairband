"""The multiples log (spec 2026-11-06 Tier 2, 13.7; ``method.md`` 16.7): the forward P/E's history,
which no vendor on file keeps, so Fairband keeps its own.

A row a company a day, the day the price is of: the price and the reported, clean and forward P/E
of the engine's intermediates at it, ``NULL`` where the result has none, with the snapshot and the
refresh that wrote it and the time. The refresh writes one in the transaction of every snapshot it
values or reprices that carries a price and its date (``log_snapshot``); a result with no price
writes none, nor does a symbol's failure, whose refusal carries a stored quote the log already
holds. The newest write of a day replaces the row's price, snapshot, refresh and time, and each
multiple it carries; a multiple it lacks keeps the figure the row holds, so a refusal never blanks
a valued day. ``multiples_log_for`` reads a company's rows oldest first and ``since`` the day its
log began.

Each write is one transaction; it joins the caller's when there is one, so the snapshot's row and
its log row commit together.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from fairband.engine.types import ValuationResult
from fairband.store._codec import dump_date, dump_float, dump_stamp, load_date, load_float
from fairband.store.db import transaction


@dataclass(frozen=True)
class MultiplesRow:
    day: date
    price: float
    pe_reported: float | None
    pe_clean: float | None
    pe_forward: float | None
    snapshot_id: int | None


def log_multiples(
    conn: sqlite3.Connection,
    symbol: str,
    day: date,
    price: float,
    pe_reported: float | None,
    pe_clean: float | None,
    pe_forward: float | None,
    snapshot_id: int | None,
    refresh_id: int | None,
    at: datetime,
) -> None:
    """Log the company's multiples of ``day``, over a row of that day: a multiple given replaces
    the row's, one not given keeps it."""
    row = (
        symbol,
        dump_date(day),
        dump_float(price),
        dump_float(pe_reported),
        dump_float(pe_clean),
        dump_float(pe_forward),
        snapshot_id,
        refresh_id,
        dump_stamp(at),
    )
    with transaction(conn):
        conn.execute(
            "INSERT INTO multiples_log (symbol, day, price, pe_reported, pe_clean, pe_forward,"
            " snapshot_id, refresh_id, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT (symbol, day) DO UPDATE SET price = excluded.price,"
            " pe_reported = COALESCE(excluded.pe_reported, pe_reported),"
            " pe_clean = COALESCE(excluded.pe_clean, pe_clean),"
            " pe_forward = COALESCE(excluded.pe_forward, pe_forward),"
            " snapshot_id = excluded.snapshot_id, refresh_id = excluded.refresh_id,"
            " created_at = excluded.created_at",
            row,
        )


def log_snapshot(
    conn: sqlite3.Connection,
    result: ValuationResult,
    snapshot_id: int,
    refresh_id: int,
    at: datetime,
) -> None:
    """Log the multiples of snapshot ``snapshot_id``'s result as of its price date: its
    intermediates' ``multiples``, each ``None`` where the result has none (a refusal has none).
    Nothing for a result without a price or a price date."""
    if result.price is None or result.price_date is None:
        return
    found: Any = result.intermediates.get("multiples")
    multiples: dict[str, float | None] = found if isinstance(found, dict) else {}
    log_multiples(
        conn,
        result.symbol,
        result.price_date,
        result.price,
        multiples.get("pe_reported"),
        multiples.get("pe_clean"),
        multiples.get("pe_forward"),
        snapshot_id,
        refresh_id,
        at,
    )


def multiples_log_for(conn: sqlite3.Connection, symbol: str) -> list[MultiplesRow]:
    """The company's rows, oldest first."""
    rows = conn.execute(
        "SELECT day, price, pe_reported, pe_clean, pe_forward, snapshot_id FROM multiples_log"
        " WHERE symbol = ? ORDER BY day",
        (symbol,),
    )
    return [
        MultiplesRow(
            day=load_date(row["day"]),
            price=float(row["price"]),
            pe_reported=load_float(row["pe_reported"]),
            pe_clean=load_float(row["pe_clean"]),
            pe_forward=load_float(row["pe_forward"]),
            snapshot_id=row["snapshot_id"],
        )
        for row in rows
    ]


def since(conn: sqlite3.Connection, symbol: str) -> date | None:
    """The day the company's log began, ``None`` before its first row."""
    row = conn.execute("SELECT MIN(day) FROM multiples_log WHERE symbol = ?", (symbol,)).fetchone()
    return None if row[0] is None else load_date(row[0])
