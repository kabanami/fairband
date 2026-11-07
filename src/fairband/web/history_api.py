"""The band's history read (spec 2026-11-06 Tier 2, 18.4; ``method.md`` 16.6).

``GET /api/companies/{symbol}/band-history`` answers ``{symbol, points}``, the band the report
page's price chart draws behind the closes: a point a snapshot that carries a price date, oldest
day first, the newest snapshot of each day (``store.snapshots.band_points``), each ``{day, price,
fairLow, fairHigh, buyLevel, trimLevel, snapshotId}`` with ``day`` the snapshot's price date (ISO
text) and the four levels the snapshot's, ``null`` on a refusal, whose point carries its price
alone. A company before its first snapshot has no point; a symbol the store holds neither a
universe row nor a snapshot for is a 404, "no company <symbol>", and one that is not a symbol a
400.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from typing import Any

from fastapi import FastAPI, HTTPException

from fairband.policy.settings import exchange_symbol
from fairband.store.companies import latest_company
from fairband.store.snapshots import BandPoint, band_points


def add_history_routes(app: FastAPI, conn_factory: Callable[[], sqlite3.Connection]) -> None:
    """Register the band's history read."""

    @app.get("/api/companies/{symbol}/band-history")
    def band_history(symbol: str) -> dict[str, Any]:
        try:
            symbol = exchange_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        with closing(conn_factory()) as conn:
            points = band_points(conn, symbol)
            if not points and latest_company(conn, symbol) is None:
                raise HTTPException(404, f"no company {symbol}")
        return {"symbol": symbol, "points": [_point(p) for p in points]}


def _point(point: BandPoint) -> dict[str, Any]:
    levels = point.levels
    return {
        "day": point.day.isoformat(),
        "price": point.price,
        "fairLow": None if levels is None else levels.fair_low,
        "fairHigh": None if levels is None else levels.fair_high,
        "buyLevel": None if levels is None else levels.buy,
        "trimLevel": None if levels is None else levels.trim,
        "snapshotId": point.snapshot_id,
    }
