"""Fetch one company: the fourteen calls of spec 6.5, each reused while fresh and stored whole.

``fetch_company`` takes the endpoints in a fixed order. For each one it:

1. reuses the newest HTTP 200 response to the same call (provider, endpoint, symbol and params)
   when it was observed less than ``reuse_hours`` (FMP) or ``gf_reuse_days`` (GuruFocus) before
   ``now``, unless ``force``: no call, no write (spec 6.2, D13);
2. else calls the vendor, outside any transaction;
3. then stores the response, its body scrubbed of ``secrets``, together with the facts and
   observations normalized from it in one transaction, so a response never stands without its rows.

A ``VendorError`` is stored as a response row with the error, its HTTP status if one came back and
no payload, in a transaction of its own, and the fetch goes on with the next endpoint. Without a
GuruFocus client, the two GuruFocus endpoints fail with "no GuruFocus key" (logged) and store
nothing, unless the store holds fresh responses, which are reused. An HTTP 429 is a
``VendorError`` like any other here; stopping the refresh is the runner's job.

The stored ``params`` are the call's logical parameters (``symbol``, ``period``, ``limit``,
``from``), never the key, and the same call stores the same dict, so they are the reuse key. The
price history is stored as ``price-close`` observations: ``period`` and ``as_of`` the close date,
field ``close``, unit ``currency``. Call ``fetch_company`` outside any transaction.
"""

import logging
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
from typing import Any, Literal

from fairband.policy import Policy
from fairband.store.db import transaction
from fairband.store.facts import FactRow, insert_facts
from fairband.store.observations import ObservationRow, insert_observations
from fairband.store.vendor import latest_response, record_response
from fairband.vendors.fmp import (
    ANNUAL_ESTIMATE_LIMIT,
    QUARTER_ESTIMATE_LIMIT,
    Fmp,
    Period,
    StatementKind,
)
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorError, VendorResponse
from fairband.vendors.normalize_fmp import (
    as_reported_balance_facts,
    earnings_observations,
    estimate_observations,
    price_closes,
    profile_observations,
    quote_observations,
    statement_facts,
)
from fairband.vendors.normalize_gf import keyratios_observations, summary_observations
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.refresh")

type Provider = Literal["fmp", "gf"]

# The depths of spec 6.5.
STATEMENT_YEARS = 11  # ten years for the ROIC aggregate plus the opening balance
STATEMENT_QUARTERS = 8
PRICE_YEARS = 5
EARNINGS_ROWS = 12

# Without these the company cannot be valued; their failure sets ``FetchOutcome.error``.
REQUIRED = frozenset(
    {"income-annual", "balance-annual", "cashflow-annual", "quote", "estimates-quarter"}
)
NO_GF_KEY = "no GuruFocus key"
_STATEMENT_ENDPOINTS = frozenset(
    {"income-annual", "balance-annual", "cashflow-annual", "income-quarter", "cashflow-quarter"}
)

type _Rows = tuple[list[FactRow], list[ObservationRow]]


@dataclass(frozen=True)
class FetchOutcome:
    """What one fetch did. ``calls`` counts the endpoints called, a failed call among them;
    ``reused`` the endpoints served from the store; ``failed`` names, in fetch order, the endpoints
    that failed or had no client; ``error`` is ``"data fetch failed: <endpoints>"`` naming the
    required endpoints among them, or ``None`` when every required endpoint has its data."""

    symbol: str
    calls: int
    reused: int
    failed: tuple[str, ...]
    error: str | None


@dataclass(frozen=True)
class _Call:
    provider: Provider
    endpoint: str
    params: Mapping[str, str]
    send: Callable[[], VendorResponse] | None  # None: no client for the provider


def fetch_company(
    conn: sqlite3.Connection,
    fmp: Fmp,
    gf: GuruFocus | None,
    symbol: str,
    policy: Policy,
    now: datetime,
    secrets: Sequence[str],
    force: bool = False,
) -> FetchOutcome:
    """Fetch ``symbol``'s endpoints that are not fresh in the store, and store what comes back.

    ``now`` judges freshness and is every stored row's ``entered_at``; a response's ``observed_at``
    is the client's. ``secrets`` are the vendor keys, scrubbed from every stored text.
    """
    windows: dict[Provider, timedelta] = {
        "fmp": timedelta(hours=policy.refresh.reuse_hours),
        "gf": timedelta(days=policy.refresh.gf_reuse_days),
    }
    calls = reused = 0
    failed: list[str] = []
    for call in _calls(fmp, gf, symbol, now.date()):
        latest = latest_response(conn, call.provider, call.endpoint, symbol, call.params)
        if not force and latest is not None and now - latest.observed_at < windows[call.provider]:
            reused += 1
            continue
        if call.send is None:
            _log_failure(symbol, call, NO_GF_KEY)
            failed.append(call.endpoint)
            continue
        calls += 1
        try:
            response = call.send()
        except VendorError as exc:
            message = scrub(str(exc), secrets)
            record_response(
                conn,
                call.provider,
                call.endpoint,
                call.params,
                symbol,
                exc.status,
                None,
                message,
                now,
            )
            _log_failure(symbol, call, message)
            failed.append(call.endpoint)
            continue
        _store(conn, call, symbol, response, now, secrets)
    required = [endpoint for endpoint in failed if endpoint in REQUIRED]
    error = f"data fetch failed: {', '.join(required)}" if required else None
    return FetchOutcome(symbol, calls, reused, tuple(failed), error)


def _calls(fmp: Fmp, gf: GuruFocus | None, symbol: str, today: date) -> list[_Call]:
    """The fourteen calls for ``symbol``, in fetch order."""
    start = _years_before(today, PRICE_YEARS)

    def on_fmp(
        endpoint: str, params: Mapping[str, str], send: Callable[[], VendorResponse]
    ) -> _Call:
        return _Call("fmp", endpoint, {"symbol": symbol, **params}, send)

    def statement(kind: StatementKind, period: Period, limit: int) -> _Call:
        params = {"period": period, "limit": str(limit)}
        return on_fmp(
            f"{kind}-{period}", params, partial(fmp.statement, symbol, kind, period, limit)
        )

    def estimates(period: Period, limit: int) -> _Call:
        params = {"period": period, "limit": str(limit)}
        return on_fmp(f"estimates-{period}", params, partial(fmp.estimates, symbol, period, limit))

    def on_gf(endpoint: str, send: Callable[[GuruFocus, str], VendorResponse]) -> _Call:
        bound = None if gf is None else partial(send, gf, symbol)
        return _Call("gf", endpoint, {"symbol": symbol}, bound)

    as_reported = {"period": "annual", "limit": str(STATEMENT_YEARS)}
    return [
        statement("income", "annual", STATEMENT_YEARS),
        statement("balance", "annual", STATEMENT_YEARS),
        statement("cashflow", "annual", STATEMENT_YEARS),
        statement("income", "quarter", STATEMENT_QUARTERS),
        statement("cashflow", "quarter", STATEMENT_QUARTERS),
        on_fmp(
            "balance-asreported-annual",
            as_reported,
            partial(fmp.balance_as_reported, symbol, STATEMENT_YEARS),
        ),
        on_fmp("profile", {}, partial(fmp.profile, symbol)),
        on_fmp("quote", {}, partial(fmp.quote, [symbol])),
        on_fmp(
            "price-history", {"from": start.isoformat()}, partial(fmp.price_history, symbol, start)
        ),
        estimates("annual", ANNUAL_ESTIMATE_LIMIT),
        estimates("quarter", QUARTER_ESTIMATE_LIMIT),
        on_fmp(
            "earnings", {"limit": str(EARNINGS_ROWS)}, partial(fmp.earnings, symbol, EARNINGS_ROWS)
        ),
        on_gf("summary", GuruFocus.summary),
        on_gf("keyratios", GuruFocus.keyratios),
    ]


def _store(
    conn: sqlite3.Connection,
    call: _Call,
    symbol: str,
    response: VendorResponse,
    now: datetime,
    secrets: Sequence[str],
) -> None:
    """The response and its normalized rows, in one transaction."""
    observed = response.observed_at
    payload = scrub(response.text, secrets)
    with transaction(conn):
        response_id = record_response(
            conn,
            call.provider,
            call.endpoint,
            call.params,
            symbol,
            response.status,
            payload,
            None,
            observed,
        )
        facts, observations = _rows(
            call.endpoint, response.json, symbol, response_id, observed, now
        )
        insert_facts(conn, facts)
        insert_observations(conn, observations)


def _rows(
    endpoint: str, payload: Any, symbol: str, response_id: int, observed: datetime, now: datetime
) -> _Rows:
    """The facts and observations normalized from one endpoint's parsed payload."""
    if endpoint in _STATEMENT_ENDPOINTS:  # the endpoint names the statement dataset
        return statement_facts(payload, symbol, endpoint, response_id, observed, now), []
    source = (symbol, response_id, observed, now)
    match endpoint:
        case "balance-asreported-annual":
            return as_reported_balance_facts(payload, *source), []
        case "profile":
            return [], profile_observations(payload, *source)
        case "quote":
            return [], quote_observations(payload, *source)
        case "price-history":
            return [], _close_observations(payload, *source)
        case "estimates-annual":
            return [], estimate_observations(payload, symbol, "annual", response_id, observed, now)
        case "estimates-quarter":
            return [], estimate_observations(payload, symbol, "quarter", response_id, observed, now)
        case "earnings":
            return [], earnings_observations(payload, *source, today=now.date())
        case "summary":
            return [], summary_observations(payload, *source)
        case "keyratios":
            return [], keyratios_observations(payload, *source)
    raise ValueError(f"no normalizer for endpoint {endpoint}")


def _close_observations(
    payload: Any, symbol: str, response_id: int, observed: datetime, entered: datetime
) -> list[ObservationRow]:
    """One ``price-close`` observation per daily close."""
    return [
        ObservationRow(
            symbol=symbol,
            dataset="price-close",
            period=when,
            field="close",
            value=Decimal(str(close)),
            unit="currency",
            as_of=when,
            observed_at=observed,
            entered_at=entered,
            response_id=response_id,
        )
        for when, close in price_closes(payload)
    ]


def _log_failure(symbol: str, call: _Call, reason: str) -> None:
    logger.warning("%s %s %s failed: %s", symbol, call.provider, call.endpoint, reason)


def _years_before(day: date, years: int) -> date:
    """The same day ``years`` earlier; 29 February becomes the 28th."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)
