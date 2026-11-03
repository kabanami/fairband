"""Fetch one company: thirteen FMP calls and two GuruFocus calls (spec 6.5, and the peers of growth
routes spec 5.5), each reused while fresh and stored whole.

``fetch_company`` refuses to run inside a transaction: vendor calls run outside write transactions.
It takes the endpoints in a fixed order. For each one it:

1. reuses the newest HTTP 200 response without an error to the same call (provider, endpoint,
   symbol and params) when it was observed less than ``reuse_hours`` (FMP) or ``gf_reuse_days``
   (GuruFocus) before ``now``, unless ``force``: no call, no write (spec 6.2, D13);
2. else calls the vendor, outside any transaction;
3. then stores the response, its body scrubbed of ``secrets``, together with the facts and
   observations normalized from it in one transaction, so a response never stands without its rows.

A 200 whose payload gives no rows (GuruFocus answers some failures with HTTP 200 and an error body;
FMP answers an unknown symbol with an empty list) is stored with the error ``"unusable payload:
<the first 80 characters, scrubbed, whitespace collapsed>"`` and counts as failed; a row with an
error is never reused. The price history stores no rows: its closes stay in the stored payload,
read back with ``response_payload`` and ``price_closes``, and it is usable when it holds a close.
Nor do the peers: their symbols stay in the stored payload, read back with ``peer_symbols``, and
the payload is usable when it names a peer or is exactly the empty list (a company with no peers
has none, and that answer is reused like any other); a list of objects without a ``symbol``, or
anything but a list, is unusable. The peers are not required.

A ``VendorError`` is stored as a response row with the error, its HTTP status if one came back and
no payload, in a transaction of its own, and the fetch goes on with the next endpoint, except after
an HTTP 429: the fetch stops there and reports ``rate_limited``; stopping the refresh is the
runner's job. Without a GuruFocus client, the two GuruFocus endpoints fail with "no GuruFocus key"
(logged) and store nothing, unless the store holds fresh responses, which are reused.

The stored ``params`` are the call's logical parameters (``symbol``, ``period``, ``limit``), never
the key, and the same call stores the same dict, so they are the reuse key. The price history's
start date (five years before ``now``) is left out, so its key does not change at midnight and the
24-hour rule alone decides its reuse.
"""

import logging
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from functools import partial
from http import HTTPStatus
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
    peer_symbols,
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

# Without these the company cannot be valued; their failure sets ``FetchOutcome.error``. The
# quarterly consensus is not among them: FMP answers ``[]`` for a company without quarterly
# coverage (a foreign filer that reports twice a year, say), and the routes that read it, Mature
# Growth and the revenue-growth route, refuse an incomplete NTM consensus themselves.
REQUIRED = frozenset({"income-annual", "balance-annual", "cashflow-annual", "quote"})
# The five statements; each endpoint is named as the dataset its facts are stored under.
STATEMENT_ENDPOINTS = frozenset(
    {"income-annual", "balance-annual", "cashflow-annual", "income-quarter", "cashflow-quarter"}
)
NO_GF_KEY = "no GuruFocus key"
_GF_ENDPOINTS = frozenset({"summary", "keyratios"})
_DETAIL_CHARS = 80  # of an unusable payload, kept as its error
_PENDING = 0  # the response id normalized rows carry until their response is recorded

type _Rows = tuple[list[FactRow], list[ObservationRow]]


@dataclass(frozen=True)
class FetchOutcome:
    """What one fetch did. ``calls`` counts the endpoints called, a failed call among them;
    ``reused`` the endpoints served from the store; ``failed`` names, in fetch order, the endpoints
    that failed, gave an unusable payload or had no client; ``error`` is ``"data fetch failed:
    <endpoints>"`` naming the required endpoints among them, or ``None`` when every required
    endpoint has its data. ``rate_limited`` is true when an endpoint answered HTTP 429: the
    endpoints after it are skipped (neither called, reused nor failed), so ``failed`` and
    ``error`` cover only the endpoints up to it."""

    symbol: str
    calls: int
    reused: int
    failed: tuple[str, ...]
    error: str | None
    rate_limited: bool = False


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
    is the client's. ``secrets`` are the vendor keys, scrubbed from every stored text. Raises
    ``ValueError`` when ``conn`` is in a transaction.
    """
    if conn.in_transaction:
        raise ValueError("fetch_company must not run inside a transaction")
    windows: dict[Provider, timedelta] = {
        "fmp": timedelta(hours=policy.refresh.reuse_hours),
        "gf": timedelta(days=policy.refresh.gf_reuse_days),
    }
    calls = reused = 0
    failed: list[str] = []
    rate_limited = False
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
            if exc.status == HTTPStatus.TOO_MANY_REQUESTS:
                rate_limited = True
                break
            continue
        unusable_error = _store(conn, call, symbol, response, now, secrets)
        if unusable_error is not None:
            _log_failure(symbol, call, unusable_error)
            failed.append(call.endpoint)
    required = [endpoint for endpoint in failed if endpoint in REQUIRED]
    error = f"data fetch failed: {', '.join(required)}" if required else None
    return FetchOutcome(symbol, calls, reused, tuple(failed), error, rate_limited)


def provider_of(endpoint: str) -> Provider:
    """The provider of an endpoint name this module stores (``FetchOutcome.failed``): the two
    GuruFocus endpoints are its bare route names, ``summary`` and ``keyratios``; every other
    endpoint is FMP's."""
    return "gf" if endpoint in _GF_ENDPOINTS else "fmp"


def _calls(fmp: Fmp, gf: GuruFocus | None, symbol: str, today: date) -> list[_Call]:
    """The calls for ``symbol``, thirteen FMP and two GuruFocus, in fetch order."""
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
        assert endpoint in _GF_ENDPOINTS, f"provider_of must name {endpoint} GuruFocus's"
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
        on_fmp("price-history", {}, partial(fmp.price_history, symbol, start)),
        estimates("annual", ANNUAL_ESTIMATE_LIMIT),
        estimates("quarter", QUARTER_ESTIMATE_LIMIT),
        on_fmp(
            "earnings", {"limit": str(EARNINGS_ROWS)}, partial(fmp.earnings, symbol, EARNINGS_ROWS)
        ),
        on_fmp("peers", {}, partial(fmp.peers, symbol)),
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
) -> str | None:
    """Store the response and its normalized rows in one transaction. Returns the error stored
    with an unusable payload, else ``None``."""
    observed = response.observed_at
    payload = scrub(response.text, secrets)
    rows = _rows(call.endpoint, response.json, symbol, observed, now)
    error = None if rows is not None else unusable(payload)
    with transaction(conn):
        response_id = record_response(
            conn,
            call.provider,
            call.endpoint,
            call.params,
            symbol,
            response.status,
            payload,
            error,
            observed,
        )
        if rows is not None:
            facts, observations = rows
            insert_facts(conn, [replace(f, response_id=response_id) for f in facts])
            insert_observations(conn, [replace(o, response_id=response_id) for o in observations])
    return error


def unusable(payload: str) -> str:
    """The error stored with a payload that gives no rows: ``unusable payload: <the first 80
    characters, whitespace collapsed>``. Pass the payload scrubbed: a key cut short would no
    longer be scrubbed."""
    return f"unusable payload: {' '.join(payload.split())[:_DETAIL_CHARS]}"


def _rows(
    endpoint: str, payload: Any, symbol: str, observed: datetime, now: datetime
) -> _Rows | None:
    """The facts and observations one endpoint's parsed payload gives, citing ``_PENDING`` for
    the response; ``None`` when it gives none. The price history and the peers give no rows; the
    one's payload is usable when it holds a close, the other's when it names a peer or is exactly
    ``[]``."""
    source = (symbol, _PENDING, observed, now)
    facts: list[FactRow] = []
    observations: list[ObservationRow] = []
    match endpoint:
        case _ if endpoint in STATEMENT_ENDPOINTS:
            facts = statement_facts(payload, symbol, endpoint, _PENDING, observed, now)
        case "balance-asreported-annual":
            facts = as_reported_balance_facts(payload, *source)
        case "profile":
            observations = profile_observations(payload, *source)
        case "quote":
            observations = quote_observations(payload, *source)
        case "price-history":
            return ([], []) if price_closes(payload) else None
        case "estimates-annual":
            observations = estimate_observations(payload, symbol, "annual", _PENDING, observed, now)
        case "estimates-quarter":
            observations = estimate_observations(
                payload, symbol, "quarter", _PENDING, observed, now
            )
        case "earnings":
            observations = earnings_observations(payload, *source, today=now.date())
        case "peers":
            return ([], []) if peer_symbols(payload, symbol) or payload == [] else None
        case "summary":
            observations = summary_observations(payload, *source)
        case "keyratios":
            observations = keyratios_observations(payload, *source)
        case _:
            raise ValueError(f"no normalizer for endpoint {endpoint}")
    return (facts, observations) if facts or observations else None


def _log_failure(symbol: str, call: _Call, reason: str) -> None:
    logger.warning("%s %s %s failed: %s", symbol, call.provider, call.endpoint, reason)


def _years_before(day: date, years: int) -> date:
    """The same day ``years`` earlier; 29 February becomes the 28th."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)
