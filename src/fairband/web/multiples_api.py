"""The multiples history read (spec 2026-11-06 Tier 2, 13.7 and 16; ``method.md`` 16.7).

``GET /api/companies/{symbol}/multiples-history`` answers ``{symbol, pe, peNote, peForward}``, the
two P/E series of ``fairband.reports.multiples``, each ``{points, stats, since, responseId,
note}``: the points oldest first as ``{day, value, ref}``, the statistics ``avg10y``,
``median10y``, ``high10y`` and ``low10y`` as ``{value, unit, ref}`` with the unit ``multiple``,
``since`` the series' first day on file (ISO text, ``null`` with none), and the refs
``multiple:<symbol>/<series>/<date>`` and ``/<stat>`` (``avg_10y`` and its siblings).

- ``pe``, the trailing P/E: the ``pe-history`` pass-through's answer (``responseId`` the stored
  response's), the stored response when one is inside its seven days, else fetched and stored. A
  payload the series cannot be read from has no points and the ``note`` "the series could not be
  read". When it cannot be had, ``pe`` is ``null`` and ``peNote`` says why: "no GuruFocus key: the
  pe-history pass-through is off", "no FMP key" on a server with no pass-through, the busy
  sentence, or the vendor's failure, scrubbed. ``peNote`` is ``null`` otherwise.
- ``peForward``, the forward P/E: the multiples log's, ``responseId`` and ``note`` ``null``.

A symbol that is not one is a 400. The route is a sync one, as the pass-through route is: the
fetch runs on FastAPI's thread pool, under the pass-through's slots and its wait.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from typing import Any

from fastapi import FastAPI, HTTPException

from fairband.policy.settings import exchange_symbol
from fairband.refresh.passthrough import Passthrough, PassthroughBusy, PassthroughNoKey
from fairband.reports.multiples import STATS, Series, forward_series, trailing_series
from fairband.reports.refs import multiple_ref
from fairband.store.multiples import multiples_log_for
from fairband.vendors.http import VendorError
from fairband.web.vendor_api import NO_FMP_KEY

UNREADABLE = "the series could not be read"
_NO_SERIES = Series((), dict.fromkeys(STATS), None)


def add_multiples_routes(
    app: FastAPI, conn_factory: Callable[[], sqlite3.Connection], passthrough: Passthrough | None
) -> None:
    """Register the multiples history read; ``passthrough`` fetches the trailing series."""

    @app.get("/api/companies/{symbol}/multiples-history")
    def multiples_history(symbol: str) -> dict[str, Any]:
        try:
            symbol = exchange_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        pe, pe_note = _trailing(passthrough, symbol)
        with closing(conn_factory()) as conn:
            forward = forward_series(multiples_log_for(conn, symbol))
        return {
            "symbol": symbol,
            "pe": pe,
            "peNote": pe_note,
            "peForward": _series_json(symbol, "pe_forward", forward, None, None),
        }


def _trailing(
    passthrough: Passthrough | None, symbol: str
) -> tuple[dict[str, Any] | None, str | None]:
    """The trailing series as the read answers it and ``None``, or ``None`` and why."""
    if passthrough is None:
        return None, NO_FMP_KEY
    try:
        fetched = passthrough.fetch("pe-history", symbol, {})["pe-history"]
    except (PassthroughNoKey, PassthroughBusy, VendorError) as exc:
        return None, str(exc)
    series = trailing_series(fetched.payload)
    if series is None:
        return _series_json(symbol, "pe", _NO_SERIES, fetched.row.id, UNREADABLE), None
    return _series_json(symbol, "pe", series, fetched.row.id, None), None


def _series_json(
    symbol: str, name: str, series: Series, response_id: int | None, note: str | None
) -> dict[str, Any]:
    return {
        "points": [
            {
                "day": day.isoformat(),
                "value": value,
                "ref": multiple_ref(symbol, name, day.isoformat()),
            }
            for day, value in series.points
        ],
        "stats": {
            stat.replace("_", ""): {
                "value": series.stats[stat],
                "unit": "multiple",
                "ref": multiple_ref(symbol, name, stat),
            }
            for stat in STATS
        },
        "since": None if series.since is None else series.since.isoformat(),
        "responseId": response_id,
        "note": note,
    }
