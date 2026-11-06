"""The agent's vendor pass-throughs (spec 2026-11-06 Tier 2, 15.3): four FMP endpoints the engine
does not read, fetched on request with the server's key and stored, so a report can cite a field of
one as ``response:<id>/<json pointer>``.

The kinds and the endpoints they are stored under (provider ``fmp``):

- ``transcript``: ``transcript``, the earnings call of the fiscal ``year`` and ``quarter`` (1 to 4),
  both required;
- ``news``: ``news``, the newest ``limit`` stories (``NEWS_LIMIT`` when left out);
- ``segments``: two calls, ``segments-product`` and ``segments-geographic``, the revenue by product
  and by region, answered as the parts ``product`` and ``geographic``;
- ``insider-trades``: ``insider-trades``, the newest insider trades.

For each call, as ``fetch_company`` does: the newest HTTP 200 response to the same call (endpoint,
symbol and the call's logical params, ``symbol`` among them) stored without an error is reused when
it was observed less than ``reuse_hours`` before the clock; else the vendor is called, outside any
transaction, and the response is stored with its body scrubbed of ``secrets``. The answer's payload
is the stored text parsed, so it carries no key either. A body that is not JSON is stored with the
error ``unusable payload: ...`` and raises a ``VendorError``; a ``VendorError`` is stored as a
response row with its message and status and no payload, then raised, its message scrubbed. Neither
is reused.

The calls go through the FMP client the server builds on the limiter its refresh runs share, so the
pass-throughs keep the refresh's pace.
"""

import json
import sqlite3
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
from typing import Any

from fairband.policy import Policy
from fairband.refresh.fetch import unusable
from fairband.store.vendor import (
    ResponseRow,
    latest_response,
    record_response,
    response_payload,
    response_row,
)
from fairband.vendors.fmp import Fmp
from fairband.vendors.http import VendorError, VendorResponse
from fairband.vendors.scrub import scrub

KINDS = ("transcript", "news", "segments", "insider-trades")
NEWS_LIMIT = 20
_KIND_LIST = ", ".join(KINDS[:-1]) + f" or {KINDS[-1]}"
_PROVIDER = "fmp"


@dataclass(frozen=True)
class Fetched:
    """One stored response: its row, its payload parsed and whether it was reused."""

    row: ResponseRow
    payload: Any
    reused: bool


@dataclass(frozen=True)
class _Call:
    part: str
    endpoint: str
    params: dict[str, str]  # the logical params, the reuse key
    send: Callable[[], VendorResponse]


class Passthrough:
    """Fetches the four kinds through ``fmp``; ``policy.refresh.reuse_hours`` is the reuse window,
    ``clock`` judges it, and ``secrets`` are scrubbed from every stored text and every answer."""

    def __init__(
        self,
        fmp: Fmp,
        conn_factory: Callable[[], sqlite3.Connection],
        policy: Policy,
        clock: Callable[[], datetime],
        secrets: tuple[str, ...],
    ) -> None:
        self._fmp = fmp
        self._conn_factory = conn_factory
        self._window = timedelta(hours=policy.refresh.reuse_hours)
        self._clock = clock
        self._secrets = secrets

    def close(self) -> None:
        """Close the FMP client."""
        self._fmp.close()

    def fetch(self, kind: str, symbol: str, params: Mapping[str, str]) -> dict[str, Fetched]:
        """The stored responses that answer ``kind`` for ``symbol`` (the store's exchange form), by
        part: ``product`` and ``geographic`` for ``segments``, else the one part named ``kind``.
        Raises ``ValueError`` on an unknown kind or a missing or bad parameter, before any call,
        and ``VendorError`` when a call fails."""
        calls = self._calls(kind, symbol, params)
        with closing(self._conn_factory()) as conn:
            return {call.part: self._fetch(conn, call, symbol) for call in calls}

    def _fetch(self, conn: sqlite3.Connection, call: _Call, symbol: str) -> Fetched:
        latest = latest_response(conn, _PROVIDER, call.endpoint, symbol, call.params)
        if latest is not None and self._clock() - latest.observed_at < self._window:
            text = response_payload(conn, latest.id)
            if text is not None:
                return Fetched(latest, json.loads(text), reused=True)
        try:
            response = call.send()
        except VendorError as exc:
            message = scrub(str(exc), self._secrets)
            self._record(conn, call, symbol, exc.status, None, message, self._clock())
            raise VendorError(message, exc.status, exc.retryable) from None
        payload = scrub(response.text, self._secrets)
        if response.json is None:
            error = unusable(payload)
            self._record(conn, call, symbol, response.status, payload, error, response.observed_at)
            message = f"GET {response.url} -> {response.status} with a body that is not JSON"
            raise VendorError(message, response.status, retryable=False)
        response_id = self._record(
            conn, call, symbol, response.status, payload, None, response.observed_at
        )
        row = response_row(conn, response_id)
        assert row is not None
        return Fetched(row, json.loads(payload), reused=False)

    def _record(
        self,
        conn: sqlite3.Connection,
        call: _Call,
        symbol: str,
        status: int | None,
        payload: str | None,
        error: str | None,
        observed_at: datetime,
    ) -> int:
        return record_response(
            conn, _PROVIDER, call.endpoint, call.params, symbol, status, payload, error, observed_at
        )

    def _calls(self, kind: str, symbol: str, params: Mapping[str, str]) -> list[_Call]:
        fmp = self._fmp
        match kind:
            case "transcript":
                year, quarter = _whole(params, "year"), _whole(params, "quarter")
                if year is None or quarter is None:
                    raise ValueError("a transcript needs year and quarter")
                if not 1 <= quarter <= 4:
                    raise ValueError("quarter must be 1 to 4")
                logical = {"symbol": symbol, "year": str(year), "quarter": str(quarter)}
                send = partial(fmp.transcript, symbol, year, quarter)
                return [_Call(kind, "transcript", logical, send)]
            case "news":
                limit = _whole(params, "limit")
                limit = NEWS_LIMIT if limit is None else limit
                if limit < 1:
                    raise ValueError("limit must be at least 1")
                logical = {"symbol": symbol, "limit": str(limit)}
                return [_Call(kind, "news", logical, partial(fmp.news, symbol, limit))]
            case "segments":
                product = partial(fmp.segments_product, symbol)
                geographic = partial(fmp.segments_geographic, symbol)
                return [
                    _Call("product", "segments-product", {"symbol": symbol}, product),
                    _Call("geographic", "segments-geographic", {"symbol": symbol}, geographic),
                ]
            case "insider-trades":
                send = partial(fmp.insider_trades, symbol)
                return [_Call(kind, "insider-trades", {"symbol": symbol}, send)]
        raise ValueError(unknown_kind(kind))


def unknown_kind(kind: str) -> str:
    """The sentence that refuses a kind outside ``KINDS``."""
    return f"unknown vendor kind: {kind} ({_KIND_LIST})"


def _whole(params: Mapping[str, str], name: str) -> int | None:
    """The parameter ``name`` as a whole number, ``None`` when it is left out."""
    text = params.get(name)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"{name} must be a whole number, not {text!r}") from None
