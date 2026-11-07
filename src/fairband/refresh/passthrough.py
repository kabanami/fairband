"""The agent's vendor pass-throughs (spec 2026-11-06 Tier 2, 15.3): vendor endpoints the engine
does not read, fetched on request with the server's keys and stored, so a report can cite a field
of one as ``response:<id>/<json pointer>``.

The kinds and the endpoints they are stored under, provider ``fmp`` but the last:

- ``transcript``: ``transcript``, the earnings call of the fiscal ``year`` and ``quarter`` (1 to 4),
  both required;
- ``news``: ``news``, the newest ``limit`` stories, 1 to ``NEWS_LIMIT_MAX`` (``NEWS_LIMIT`` when
  left out);
- ``segments``: two calls, ``segments-product`` and ``segments-geographic``, the revenue by product
  and by region, answered as the parts ``product`` and ``geographic``;
- ``insider-trades``: ``insider-trades``, the newest insider trades, a page of
  ``INSIDER_TRADES_LIMIT``, which the reuse key holds;
- ``dcf``: two calls, ``dcf`` and ``dcf-levered``, FMP's discounted cash flow value and its levered
  one, answered as the parts ``dcf`` and ``levered``: a cross-check a report may cite, never a
  value Fairband computes;
- ``pe-history``: ``pettm`` under provider ``gf`` (the refresh's name for GuruFocus), GuruFocus's
  daily trailing P/E series (13.7), reused inside ``PE_HISTORY_REUSE_HOURS`` (seven days) whatever
  ``reuse_hours`` is. It needs the GuruFocus client: without one it raises ``PassthroughNoKey``
  (``NO_GF_KEY``, a 503 on the route) before any call or reuse. GuruFocus answers some failures
  with HTTP 200 and a JSON body, so a payload with no dated row (``normalize_gf.pe_ttm_rows``) is
  unusable: stored with the error ``unusable payload: ...``, answered as fetched, never reused.

For each call, as ``fetch_company`` does: the newest HTTP 200 response to the same call (provider,
endpoint, symbol and the call's logical params, ``symbol`` among them) stored without an error is
reused when it was observed less than its reuse window before the clock (``reuse_hours`` but for
``pe-history``); else the vendor is called, outside any transaction, and the response is stored
with its body scrubbed of ``secrets``. The answer's payload is the stored text parsed, so it
carries no key either. A body that is not JSON is stored with the error ``unusable payload: ...``
and raises a ``VendorError``; a ``VendorError`` is stored as a response row with its message and
status and no payload, then raised, its message scrubbed (the GuruFocus token travels in the URL
path, which the message names). None of the three is reused.

The FMP calls go through the FMP client the server builds on the limiter its refresh runs share,
so the pass-throughs keep the refresh's pace; the GuruFocus client is not paced, as the refresh's
is not. They run on the request threads, the pool every sync route of the app shares. What is
bounded: at most ``PASSTHROUGH_SLOTS`` (four) vendor calls of either vendor are in flight at once;
a call that finds every slot taken waits for one at most ``PASSTHROUGH_WAIT_S`` (ten seconds),
holding its request's thread meanwhile, then raises ``PassthroughBusy`` (``BUSY``, a 503 on the
route), nothing called or stored, and the agent tries again. A reuse takes no slot.
"""

import json
import sqlite3
import threading
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
from fairband.vendors import gurufocus as gurufocus_api
from fairband.vendors.fmp import INSIDER_TRADES_LIMIT, Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorError, VendorResponse
from fairband.vendors.normalize_gf import pe_ttm_rows
from fairband.vendors.scrub import scrub

KINDS = ("transcript", "news", "segments", "insider-trades", "dcf", "pe-history")
NEWS_LIMIT = 20
NEWS_LIMIT_MAX = 100
PE_HISTORY_REUSE_HOURS = 168  # a daily series: seven days of reuse, whatever reuse_hours is
PASSTHROUGH_SLOTS = 4  # vendor calls in flight at once
PASSTHROUGH_WAIT_S = 10.0  # the longest a call waits for a slot
BUSY = "the pass-throughs are busy: four calls are in flight, try again"
NO_GF_KEY = "no GuruFocus key: the pe-history pass-through is off"
FMP = "fmp"  # FMP's name in the store
_KIND_LIST = ", ".join(KINDS[:-1]) + f" or {KINDS[-1]}"


class PassthroughBusy(Exception):
    """No slot freed within ``PASSTHROUGH_WAIT_S``: the message is ``BUSY``."""


class PassthroughNoKey(Exception):
    """The kind's vendor has no client, the server no key for it: the message is ``NO_GF_KEY``."""


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
    provider: str = FMP
    reuse: timedelta | None = None  # the reuse window; ``reuse_hours`` when ``None``
    usable: Callable[[Any], bool] | None = None  # whether a JSON payload reads; any does if None


class Passthrough:
    """Fetches the kinds through ``fmp`` and, for ``pe-history``, ``gurufocus`` (``None`` without
    a GuruFocus key); ``policy.refresh.reuse_hours`` is the reuse window, ``clock`` judges it, and
    ``secrets`` are scrubbed from every stored text and every answer."""

    def __init__(
        self,
        fmp: Fmp,
        conn_factory: Callable[[], sqlite3.Connection],
        policy: Policy,
        clock: Callable[[], datetime],
        secrets: tuple[str, ...],
        gurufocus: GuruFocus | None = None,
    ) -> None:
        self._fmp = fmp
        self._gurufocus = gurufocus
        self._conn_factory = conn_factory
        self._window = timedelta(hours=policy.refresh.reuse_hours)
        self._clock = clock
        self._secrets = secrets
        self._slots = threading.BoundedSemaphore(PASSTHROUGH_SLOTS)

    def close(self) -> None:
        """Close the vendor clients."""
        self._fmp.close()
        if self._gurufocus is not None:
            self._gurufocus.close()

    def fetch(self, kind: str, symbol: str, params: Mapping[str, str]) -> dict[str, Fetched]:
        """The stored responses that answer ``kind`` for ``symbol`` (the store's exchange form), by
        part: ``product`` and ``geographic`` for ``segments``, ``dcf`` and ``levered`` for
        ``dcf``, else the one part named ``kind``. Raises ``ValueError`` on an unknown kind or a
        missing or bad parameter and ``PassthroughNoKey`` on a kind whose vendor has no client,
        each before any call, ``PassthroughBusy`` when no slot frees in time, and ``VendorError``
        when a call fails."""
        calls = self._calls(kind, symbol, params)
        with closing(self._conn_factory()) as conn:
            return {call.part: self._fetch(conn, call, symbol) for call in calls}

    def _fetch(self, conn: sqlite3.Connection, call: _Call, symbol: str) -> Fetched:
        latest = latest_response(conn, call.provider, call.endpoint, symbol, call.params)
        window = self._window if call.reuse is None else call.reuse
        if latest is not None and self._clock() - latest.observed_at < window:
            text = response_payload(conn, latest.id)
            if text is not None:
                return Fetched(latest, json.loads(text), reused=True)
        try:
            response = self._send(call)
        except VendorError as exc:
            message = scrub(str(exc), self._secrets)
            self._record(conn, call, symbol, exc.status, None, message, self._clock())
            raise VendorError(message, exc.status, exc.retryable) from None
        payload = scrub(response.text, self._secrets)
        if response.json is None:
            not_json = unusable(payload)
            self._record(
                conn, call, symbol, response.status, payload, not_json, response.observed_at
            )
            message = f"GET {response.url} -> {response.status} with a body that is not JSON"
            raise VendorError(message, response.status, retryable=False)
        parsed = json.loads(payload)
        # A payload the kind cannot read is stored with its error, so it is never reused.
        error = None if call.usable is None or call.usable(parsed) else unusable(payload)
        response_id = self._record(
            conn, call, symbol, response.status, payload, error, response.observed_at
        )
        row = response_row(conn, response_id)
        assert row is not None
        return Fetched(row, parsed, reused=False)

    def _send(self, call: _Call) -> VendorResponse:
        """The vendor call in a slot, the wait for one bounded: a reuse never takes a slot."""
        if not self._slots.acquire(timeout=PASSTHROUGH_WAIT_S):
            raise PassthroughBusy(BUSY)
        try:
            return call.send()
        finally:
            self._slots.release()

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
            conn,
            call.provider,
            call.endpoint,
            call.params,
            symbol,
            status,
            payload,
            error,
            observed_at,
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
                if not 1 <= limit <= NEWS_LIMIT_MAX:
                    raise ValueError(f"limit is 1 to {NEWS_LIMIT_MAX}")
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
                # The page size is in the reuse key, so a changed one never reuses older rows.
                logical = {"symbol": symbol, "limit": str(INSIDER_TRADES_LIMIT)}
                send = partial(fmp.insider_trades, symbol)
                return [_Call(kind, "insider-trades", logical, send)]
            case "dcf":
                return [
                    _Call("dcf", "dcf", {"symbol": symbol}, partial(fmp.dcf, symbol)),
                    _Call(
                        "levered",
                        "dcf-levered",
                        {"symbol": symbol},
                        partial(fmp.dcf_levered, symbol),
                    ),
                ]
            case "pe-history":
                if self._gurufocus is None:
                    raise PassthroughNoKey(NO_GF_KEY)
                return [
                    _Call(
                        kind,
                        gurufocus_api.PE_TTM,
                        {"symbol": symbol},
                        partial(self._gurufocus.pe_ttm, symbol),
                        provider=gurufocus_api.PROVIDER,
                        reuse=timedelta(hours=PE_HISTORY_REUSE_HOURS),
                        usable=_reads_as_series,
                    )
                ]
        raise ValueError(unknown_kind(kind))


def _reads_as_series(payload: Any) -> bool:
    """Whether a ``pe-history`` payload holds the series' dated rows: GuruFocus answers some
    failures with HTTP 200 and a JSON body (``{"error": ...}``)."""
    return pe_ttm_rows(payload) is not None


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
