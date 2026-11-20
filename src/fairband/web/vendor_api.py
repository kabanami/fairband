"""The vendor pass-through route (spec 2026-11-06 Tier 2, 15.3 and 16).

``GET /api/vendor/{kind}/{symbol}?year=&quarter=&limit=`` answers ``{responseId, observedAt,
reused, payload}``: the stored vendor response to the call, reused when it was observed within its
reuse window, else fetched and stored (``fairband.refresh.passthrough``), its payload scrubbed of
the keys; a report cites a field of it as ``response:<responseId>/<json pointer>``. The kinds are
``transcript`` (``year`` and ``quarter`` required), ``news`` (``limit``, 1 to 100, 20 when left
out), ``segments``, ``insider-trades`` (``limit``, 1 to 100, answers the first of the stored
page's trades, every one when left out, with ``tradeCount``, the trades the page holds; a trade
keeps its place, so a ``response:`` ref names it at any limit), ``transcript-dates`` (the fiscal
year, the quarter and the date of every call on file) and ``dcf``, all from FMP; ``segments`` and
``dcf`` are two responses each, answered as ``{responses: {product: {...}, geographic: {...}}}``
and ``{responses: {dcf: {...}, levered: {...}}}``. Each part of ``segments`` adds ``newestYear``,
the largest ``fiscalYear`` among its payload's rows that hold an integer there (a JSON ``2025.0``
is no integer), null where none does or the payload is not a list (spec 2026-11-15 11): FMP's
revenue by region can end years before its revenue by product. The P/E history's answers are no
kind of this route (spec 2026-11-19 6.3): the multiples history read serves the series built from
them.

The route may call a vendor, so a request carries ``X-Fairband-Request: 1`` as a write does,
else 403 before anything else is read (``app``, D11). An unknown kind, a symbol that is not one or
a missing or bad parameter is a 400 with its sentence; without a pass-through (the server has no
FMP key) a 503, "no FMP key"; when no slot frees within ten seconds a 503, "the pass-throughs are
busy: four calls are in flight, try again"; a failed vendor call a 502 with the vendor's sentence,
scrubbed.

The route is a sync one: FastAPI runs it on its thread pool, where a vendor call waits at most ten
seconds for one of the pass-through's four slots, then, an FMP call, for its slot in the limiter
the refresh worker's runs share.
"""

from typing import Any

from fastapi import FastAPI, HTTPException

from fairband.policy.settings import exchange_symbol
from fairband.refresh.passthrough import KINDS, Fetched, Passthrough, PassthroughBusy, unknown_kind
from fairband.vendors.http import VendorError

NO_FMP_KEY = "no FMP key"


def add_vendor_routes(app: FastAPI, passthrough: Passthrough | None) -> None:
    """Register the vendor pass-through route."""

    @app.get("/api/vendor/{kind}/{symbol}")
    def vendor(
        kind: str,
        symbol: str,
        year: int | None = None,
        quarter: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        if kind not in KINDS:
            raise HTTPException(400, unknown_kind(kind))
        if passthrough is None:
            raise HTTPException(503, NO_FMP_KEY)
        given = {"year": year, "quarter": quarter, "limit": limit}
        params = {name: str(value) for name, value in given.items() if value is not None}
        try:
            parts = passthrough.fetch(kind, exchange_symbol(symbol), params)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except PassthroughBusy as exc:
            raise HTTPException(503, str(exc)) from None
        except VendorError as exc:
            raise HTTPException(502, str(exc)) from None
        if kind == "segments":  # two calls, each its part with the newest year of its split
            return {"responses": {part: _split(fetched) for part, fetched in parts.items()}}
        if len(parts) > 1:  # dcf: two calls, each its part
            return {"responses": {part: _answer(fetched) for part, fetched in parts.items()}}
        if kind == "insider-trades":
            return _trades(parts[kind], limit)
        return _answer(parts[kind])


def _answer(fetched: Fetched) -> dict[str, Any]:
    return {
        "responseId": fetched.row.id,
        "observedAt": fetched.row.observed_at.isoformat(),
        "reused": fetched.reused,
        "payload": fetched.payload,
    }


def _split(fetched: Fetched) -> dict[str, Any]:
    """A revenue split's answer, with ``newestYear``: the largest ``fiscalYear`` among the
    payload's rows that hold an integer there (a JSON ``2025.0`` is no integer), null where none
    does or the payload is not a list. FMP's split by region can end years before its split by
    product (QCOM's ended at fiscal 2023), and the payload names no newest year."""
    rows = fetched.payload if isinstance(fetched.payload, list) else []
    years = [row.get("fiscalYear") for row in rows if isinstance(row, dict)]
    whole = [year for year in years if isinstance(year, int) and not isinstance(year, bool)]
    return _answer(fetched) | {"newestYear": max(whole, default=None)}


def _trades(fetched: Fetched, limit: int | None) -> dict[str, Any]:
    """The insider trades' answer: the first ``limit`` trades of the stored page, every one
    without a limit, and ``tradeCount``, the trades the stored page holds. A cut keeps each
    trade's place, so ``response:<id>/<n>/...`` names the same trade whatever the limit."""
    answer, page = _answer(fetched), fetched.payload
    if not isinstance(page, list):
        return answer
    return answer | {"payload": page if limit is None else page[:limit], "tradeCount": len(page)}
