"""The vendor pass-through route (spec 2026-11-06 Tier 2, 15.3 and 16).

``GET /api/vendor/{kind}/{symbol}?year=&quarter=&limit=`` answers ``{responseId, observedAt,
reused, payload}``: the stored FMP response to the call, reused when it was observed within
``reuse_hours``, else fetched and stored (``fairband.refresh.passthrough``), its payload scrubbed of
the keys; a report cites a field of it as ``response:<responseId>/<json pointer>``. The kinds are
``transcript`` (``year`` and ``quarter`` required), ``news`` (``limit``, 1 to 100, 20 when left
out), ``segments`` and ``insider-trades``; ``segments`` is two responses, answered as
``{responses: {product: {...}, geographic: {...}}}``.

An unknown kind, a symbol that is not one or a missing or bad parameter is a 400 with its
sentence; without a pass-through (the server has no FMP key) a 503, "no FMP key"; a failed vendor
call a 502 with the vendor's sentence, scrubbed.

The route is a sync one: FastAPI runs it on its thread pool, where a vendor call waits for one of
the pass-through's four slots, then for its slot in the limiter the refresh worker's runs share.
"""

from typing import Any

from fastapi import FastAPI, HTTPException

from fairband.policy.settings import exchange_symbol
from fairband.refresh.passthrough import KINDS, Fetched, Passthrough, unknown_kind
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
        except VendorError as exc:
            raise HTTPException(502, str(exc)) from None
        if kind == "segments":
            return {"responses": {part: _answer(fetched) for part, fetched in parts.items()}}
        return _answer(parts[kind])


def _answer(fetched: Fetched) -> dict[str, Any]:
    return {
        "responseId": fetched.row.id,
        "observedAt": fetched.row.observed_at.isoformat(),
        "reused": fetched.reused,
        "payload": fetched.payload,
    }
