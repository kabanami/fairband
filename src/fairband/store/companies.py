"""The universe: one row per admitted or excluded listing per refresh that built the universe.

A full refresh writes the whole universe under its own ``refresh_id``; the latest universe is the
rows of the greatest ``refresh_id`` present. ``market_cap`` is decimal text.
"""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from fairband.store._codec import dump_decimal, dump_stamp, load_decimal, load_stamp
from fairband.store.db import transaction


@dataclass(frozen=True)
class CompanyRow:
    symbol: str
    refresh_id: int
    name: str | None
    exchange: str | None
    sector: str | None
    industry: str | None
    country: str | None
    currency: str | None
    is_adr: bool
    cap_band: str | None
    market_cap: Decimal | None
    eligible: bool
    exclusion_reason: str | None
    observed_at: datetime


def insert_companies(conn: sqlite3.Connection, rows: Sequence[CompanyRow]) -> None:
    """Append the rows in one transaction."""
    stored = [
        (
            r.symbol,
            r.refresh_id,
            r.name,
            r.exchange,
            r.sector,
            r.industry,
            r.country,
            r.currency,
            r.is_adr,
            r.cap_band,
            dump_decimal(r.market_cap),
            r.eligible,
            r.exclusion_reason,
            dump_stamp(r.observed_at),
        )
        for r in rows
    ]
    with transaction(conn):
        conn.executemany(
            "INSERT INTO companies (symbol, refresh_id, name, exchange, sector, industry, country,"
            " currency, is_adr, cap_band, market_cap, eligible, exclusion_reason, observed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            stored,
        )


def latest_companies(conn: sqlite3.Connection, eligible_only: bool = True) -> list[CompanyRow]:
    """The latest universe, ordered by symbol; only the admitted listings unless told otherwise."""
    rows = conn.execute(
        "SELECT * FROM companies WHERE refresh_id = (SELECT MAX(refresh_id) FROM companies)"
        " ORDER BY symbol"
    )
    companies = [_company(r) for r in rows]
    return [c for c in companies if c.eligible or not eligible_only]


def latest_company(conn: sqlite3.Connection, symbol: str) -> CompanyRow | None:
    """The symbol's row from the newest refresh that listed it."""
    row = conn.execute(
        "SELECT * FROM companies WHERE symbol = ? ORDER BY refresh_id DESC LIMIT 1", (symbol,)
    ).fetchone()
    return None if row is None else _company(row)


def _company(row: sqlite3.Row) -> CompanyRow:
    return CompanyRow(
        symbol=row["symbol"],
        refresh_id=row["refresh_id"],
        name=row["name"],
        exchange=row["exchange"],
        sector=row["sector"],
        industry=row["industry"],
        country=row["country"],
        currency=row["currency"],
        is_adr=bool(row["is_adr"]),
        cap_band=row["cap_band"],
        market_cap=load_decimal(row["market_cap"]),
        eligible=bool(row["eligible"]),
        exclusion_reason=row["exclusion_reason"],
        observed_at=load_stamp(row["observed_at"]),
    )
