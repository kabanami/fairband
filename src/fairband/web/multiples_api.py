"""The multiples history read (spec 2026-11-06 Tier 2, 13.7 and 16; ``method.md`` 16.7).

``GET /api/companies/{symbol}/multiples-history`` answers ``{symbol, pe, peNote, peForward}``, the
two P/E series of ``fairband.reports.multiples``, each ``{points, stats, since, responseId,
note}``: the points oldest first as ``{day, value, ref}``, the statistics ``avg10y``,
``median10y``, ``high10y`` and ``low10y`` as ``{value, unit, ref}`` with the unit ``multiple``,
``since`` the series' first day on file (ISO text, ``null`` with none), and the refs
``multiple:<symbol>/<series>/<date>`` and ``/<stat>`` (``avg_10y`` and its siblings).

- ``pe``, the trailing P/E: the series Fairband builds from FMP's closes and quarterly EPS, and
  the pair's closes for a company in another currency (spec 2026-11-19 6.3), the P/E history's
  three answers through the pass-through (``SERIES_KIND``), each reused inside ``reuse_hours``,
  else fetched and stored; ``responseId`` is the closes' stored response's. A fetched answer the
  series cannot be read from (one that is not a list) is stored as unusable, and the next read
  fetches it again: the read serves the series of the newest usable stored answers, whatever
  their age, with ``peNote`` "the series could not be read", so the read and the refs agree; with
  none stored, the fetched closes with no points and that ``note``, ``peNote`` ``null``. When the
  fetch cannot be had, the read serves the series of the newest usable stored answers, whatever
  their age, the series the ``multiple:`` refs resolve against, and ``peNote`` says why: "no FMP
  key" on a server with no pass-through, the busy sentence, or the vendor's failure, scrubbed.
  ``pe`` is ``null`` only when none is stored; ``peNote`` is ``null`` when the fetch answered a
  series.
- ``peForward``, the forward P/E: the multiples log's, ``responseId`` and ``note`` ``null``.

The read may call FMP, so a request carries ``X-Fairband-Request: 1`` as a write does, else 403
before anything else is read (``app``, D11). A symbol that is not one is a 400. The route is a
sync one, as the pass-through route is: the fetch runs on FastAPI's thread pool, under the
pass-through's slots and its wait.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from typing import Any

from fastapi import FastAPI, HTTPException

from fairband.policy.settings import exchange_symbol
from fairband.refresh.passthrough import SERIES_KIND, Passthrough, PassthroughBusy
from fairband.reports.multiples import (
    STATS,
    Series,
    forward_series,
    stored_trailing,
    trailing_series,
)
from fairband.reports.refs import multiple_ref
from fairband.store.currency import reporting_currency
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
        pe, pe_note = _trailing(passthrough, conn_factory, symbol)
        with closing(conn_factory()) as conn:
            forward = forward_series(multiples_log_for(conn, symbol))
        return {
            "symbol": symbol,
            "pe": pe,
            "peNote": pe_note,
            "peForward": _series_json(symbol, "pe_forward", forward, None, None),
        }


def _trailing(
    passthrough: Passthrough | None, conn_factory: Callable[[], sqlite3.Connection], symbol: str
) -> tuple[dict[str, Any] | None, str | None]:
    """The trailing series as the read answers it, and why the fetch could not be had or read,
    if so."""
    unread: int | None = None  # the fetched closes, when the series cannot be read from the fetch
    if passthrough is None:
        reason = NO_FMP_KEY
    else:
        try:
            parts = passthrough.fetch(SERIES_KIND, symbol, {})
        except (PassthroughBusy, VendorError) as exc:
            reason = str(exc)
        else:
            with closing(conn_factory()) as conn:
                currency = reporting_currency(conn, symbol)
            payloads = {part: fetched.payload for part, fetched in parts.items()}
            series, closes_id = trailing_series(payloads, currency), parts["closes"].row.id
            if series is not None:
                return _trailing_json(symbol, closes_id, series), None
            reason, unread = UNREADABLE, closes_id
    with closing(conn_factory()) as conn:
        stored = stored_trailing(conn, symbol)
    if stored is not None:
        return _trailing_json(symbol, *stored), reason
    if unread is not None:
        return _trailing_json(symbol, unread, None), None
    return None, reason


def _trailing_json(symbol: str, response_id: int, series: Series | None) -> dict[str, Any]:
    if series is None:
        return _series_json(symbol, "pe", _NO_SERIES, response_id, UNREADABLE)
    return _series_json(symbol, "pe", series, response_id, None)


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
