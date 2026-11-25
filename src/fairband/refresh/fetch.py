"""Fetch one company: thirty-one FMP calls (spec 6.5, the peers of growth routes spec 5.5, the
splits of spec 2026-11-09 10.1, the quarterly balance sheet of spec 2026-11-13 12.1, and the
company page's sixteen: the ten of spec 2026-11-16 10.1, the Financials tab's four of spec
2026-11-17 8.1 and the Investor relations tab's two of spec 2026-11-18 8.1), each reused while
fresh and stored whole, then a thirty-second, the newest earnings call's transcript, where the
store holds no copy of it with words. Every call is FMP's (spec 2026-11-19 8.10): the answers of
the provider ``gf`` a fetch stored before stay in the store, unread.

The counts are those of a key on FMP's Ultimate plan. The fetch asks no endpoint the plan of its
adapter does not serve (``Fmp.plan``, ``fairband.plans``): on Premium neither the list of earnings
calls, ``transcript-dates``, nor the newest call's transcript, so thirty calls, and no refusal of
FMP's is stored. An endpoint left out is neither called, reused nor failed; what the store holds
of it from another plan's time stays, unread by the fetch.

``fetch_company`` refuses to run inside a transaction: vendor calls run outside write transactions.
It takes the endpoints in a fixed order. For each one it:

1. reuses the newest HTTP 200 response without an error to the same call (provider, endpoint,
   symbol and params) when it was observed less than the policy's ``reuse_hours`` before ``now``,
   unless ``force``: no call, no write (spec 6.2, D13). A scoped refresh forces every call,
   whatever the window, so on a split's day it reads the splits FMP lists from that day (spec
   2026-11-09 10.3); a full refresh does not, so it continues after a cancel (``run``);
2. else calls the vendor, outside any transaction;
3. then stores the response, its body scrubbed of ``secrets``, together with the facts and
   observations normalized from it in one transaction, so a response never stands without its rows.

A 200 whose payload gives no rows (FMP answers an unknown symbol with an empty list, and some
failures with an error object) is stored with the error ``"unusable payload: <the first 80
characters, scrubbed, whitespace collapsed>"`` and counts as failed; a row with an error is never
reused. The price history stores no rows: its closes stay in the stored payload, read back with
``response_payload`` and ``price_closes``, and it is usable when it holds a close.
Nor do the peers: their symbols stay in the stored payload, read back with ``peer_symbols``, and
the payload is usable when it names a peer or is exactly the empty list (a company with no peers
has none, and that answer is reused like any other); a list of objects without a ``symbol``, or
anything but a list, is unusable. The peers are not required. The splits are stored as observations
(dataset ``split``, ``split_observations``); any list is usable, the empty list among them (a
company with no split has none, reused like any other answer), and anything but a list is
unusable. The splits are not required either: without them the company is valued on what it has.
The company page's sixteen (``PAGE_ENDPOINTS``), fetched after the fifteen the engine reads, store
no rows: the page reads their stored payloads. Each is usable when it is a list, the empty list
among them (a company with no dividend, no analyst, no news, no segments, no earnings call or no
filing has none, reused like any other answer), and unusable otherwise (FMP's ``{"Error Message":
...}``). None of the sixteen is required. ``news``, the two segment answers,
``segments-product`` and ``segments-geographic``, the list of earnings calls,
``transcript-dates``, and the filings, ``sec-filings``, are stored under the pass-through's
endpoints and params (``page_params``), so the fetch's copy and a pass-through's (the news' at the
same limit, the filings' of the same window) reuse each other; the pass-through refuses a news, a
segments, a list of calls or a filings answer that is not a list as this module does, so neither
reuses FMP's error body. The filings' window is the 365 days to the fetch's day
(``filings_window``), the window the agents' filing list asks by default on that day.

The newest call's transcript (``TRANSCRIPT``) is asked last, after the listed calls, and read
from the store only then: where the newest usable stored list of calls names a call
(``page_investor.newest_call``) and the store holds no usable copy of that call's transcript
with words (``page_investor.has_words``), under the ``transcript`` pass-through's params
(``symbol``, ``year``, ``quarter``). It has no reuse window: a copy with words is never asked
again, by a forced fetch either (a call's words do not change once the vendor holds them), and a
call the vendor holds no words for yet (an empty list, or a row with a blank content) is asked
again at every fetch. Otherwise it is a page call: stored whole with no rows, usable when it is a
list, not required, and a 429 on it stops the fetch.

A ``VendorError`` is stored as a response row with the error, its HTTP status if one came back and
no payload, in a transaction of its own, and the fetch goes on with the next endpoint, except after
an HTTP 429, on any call, a page call among them: the fetch stops there and reports
``rate_limited``; stopping the refresh is the runner's job.

The stored ``params`` are the call's logical parameters (``symbol``, ``period``, ``limit``, the
filings' ``from`` and ``to``, a transcript's ``year`` and ``quarter``), never the key, and the
same call stores the same dict, so they are the reuse key. The price history's start date (five
years before ``now``) is left out, so its key does not change at midnight and the 24-hour rule
alone decides its reuse. The filings' window stays in their key, as in the pass-through's: a fetch
on the next day asks the next day's window.

The refresh's ``rates`` stage stores each currency's pair history here too (``rates.fetch_rates``,
spec 2026-11-10 7.1): endpoint ``fx-history``, the pair (``USDSEK``) as the symbol, stored whole
with no rows like the price history, usable when it holds a close (``fx_closes``), its start date
left out of the key in the same way.
"""

import json
import logging
import sqlite3
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from functools import partial
from http import HTTPStatus
from itertools import chain
from typing import Any, Literal

from fairband.policy import Policy
from fairband.store.db import transaction
from fairband.store.facts import FactRow, insert_facts
from fairband.store.observations import ObservationRow, insert_observations
from fairband.store.vendor import (
    latest_response,
    record_response,
    response_payload,
    usable_responses,
)
from fairband.vendors.fmp import (
    ANNUAL_ESTIMATE_LIMIT,
    FILINGS_LIMIT,
    QUARTER_ESTIMATE_LIMIT,
    Fmp,
    Period,
    StatementKind,
)
from fairband.vendors.http import VendorError, VendorResponse
from fairband.vendors.normalize_fmp import (
    as_reported_balance_facts,
    earnings_observations,
    estimate_observations,
    fx_closes,
    peer_symbols,
    price_closes,
    profile_observations,
    quote_observations,
    split_observations,
    statement_facts,
)
from fairband.vendors.page_investor import has_words, newest_call
from fairband.vendors.scrub import scrub

logger = logging.getLogger("fairband.refresh")

type Provider = Literal["fmp"]  # the store's name of the one vendor a fetch calls

# The depths of spec 6.5.
STATEMENT_YEARS = 11  # ten years for the ROIC aggregate plus the opening balance
STATEMENT_QUARTERS = 8
PRICE_YEARS = 5
EARNINGS_ROWS = 12
# The company page's depths (spec 2026-11-16 10.1).
GROWTH_YEARS = 1  # the newest fiscal year's growth
DIVIDEND_ROWS = 4
NEWS_STORIES = 60

FILINGS_WINDOW_DAYS = 365  # the filings' window: the agents' filing list's default (filings_api)

# The company page's calls (spec 2026-11-16 10.1, the Financials tab's four of spec 2026-11-17 8.1,
# then the Investor relations tab's two of spec 2026-11-18 8.1), the endpoints as stored, in fetch
# order after the fifteen the engine reads. None is required, and none gives a fact or an
# observation: the page reads their stored payloads.
PAGE_ENDPOINTS: tuple[str, ...] = (
    "ratios-ttm",
    "key-metrics-ttm",
    "financial-growth",
    "financial-scores",
    "price-change",
    "price-target",
    "grades",
    "dividends",
    "shares-float",
    "news",
    "ratios-annual",
    "key-metrics-annual",
    "segments-product",
    "segments-geographic",
    "transcript-dates",
    "sec-filings",
)
_PAGE_LIMITS = {"financial-growth": GROWTH_YEARS, "dividends": DIVIDEND_ROWS, "news": NEWS_STORIES}
# The page endpoints by fiscal year, over the statements' years.
_PAGE_BY_YEAR = frozenset({"ratios-annual", "key-metrics-annual"})
_FILINGS = "sec-filings"  # the page endpoint whose params hold the window of the fetch's day
_CALL_DATES = "transcript-dates"  # the list of earnings calls that names the newest call
# The newest call's transcript (spec 2026-11-18 8.1), the endpoint as stored: asked after the listed
# calls where the store holds no copy of it with words, stored whole as a page answer is.
TRANSCRIPT = "transcript"

# Without these the company cannot be valued; their failure sets ``FetchOutcome.error``. The
# quarterly consensus is not among them: FMP answers ``[]`` for a company without quarterly
# coverage (a foreign filer that reports twice a year, say), and the routes that read it, Mature
# Growth and the revenue-growth route, refuse an incomplete NTM consensus themselves.
REQUIRED = frozenset({"income-annual", "balance-annual", "cashflow-annual", "quote"})
# The six statements; each endpoint is named as the dataset its facts are stored under. The
# quarterly balance sheet is not required: a company without one reads its annual sheet.
STATEMENT_ENDPOINTS = frozenset(
    {
        "income-annual",
        "balance-annual",
        "cashflow-annual",
        "income-quarter",
        "cashflow-quarter",
        "balance-quarter",
    }
)
_DETAIL_CHARS = 80  # of an unusable payload, kept as its error
_PENDING = 0  # the response id normalized rows carry until their response is recorded

type _Rows = tuple[list[FactRow], list[ObservationRow]]


@dataclass(frozen=True)
class FetchOutcome:
    """What one fetch did. ``calls`` counts the endpoints called, a failed call among them;
    ``reused`` the endpoints served from the store; ``failed`` names, in fetch order, the endpoints
    that failed or gave an unusable payload; ``error`` is ``"data fetch failed:
    <endpoints>"`` naming the required endpoints among them, or ``None`` when every required
    endpoint has its data. ``rate_limited`` is true when an endpoint answered HTTP 429: the
    endpoints after it are skipped (neither called, reused nor failed), so ``failed`` and
    ``error`` cover only the endpoints up to it. The newest call's transcript counts only where
    it is asked: where the store holds a copy of it with words, or no list names a call, it is
    neither called, reused nor failed."""

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
    send: Callable[[], VendorResponse]
    reuses: bool = True  # False: no reuse window, the call is made whenever it is listed


def fetch_company(
    conn: sqlite3.Connection,
    fmp: Fmp,
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
    window = timedelta(hours=policy.refresh.reuse_hours)
    calls = reused = 0
    failed: list[str] = []
    rate_limited = False
    # ``chain`` is lazy: the newest call's transcript is read from the store only once the listed
    # calls are stored or reused, and never after a 429 has stopped the fetch.
    listed = _calls(fmp, symbol, now.date())
    for call in chain(listed, _newest_transcript(conn, fmp, symbol)):
        latest = latest_response(conn, call.provider, call.endpoint, symbol, call.params)
        if call.reuses and not force and latest is not None and now - latest.observed_at < window:
            reused += 1
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


def page_params(endpoint: str, symbol: str, today: date | None = None) -> dict[str, str]:
    """The logical params the fetch stores for a page endpoint of ``PAGE_ENDPOINTS``: the symbol;
    the depth as ``limit`` for ``financial-growth`` (``GROWTH_YEARS``), ``dividends``
    (``DIVIDEND_ROWS``) and ``news`` (``NEWS_STORIES``); ``period`` ``annual`` with
    ``STATEMENT_YEARS`` as ``limit`` for ``ratios-annual`` and ``key-metrics-annual``; and for
    ``sec-filings`` the window of ``filings_window(today)`` as ``from`` and ``to`` with
    ``FILINGS_LIMIT`` as ``limit``. ``news``'s are the pass-through's at the same limit, the two
    segment endpoints' and ``transcript-dates``' the pass-through's (the symbol alone), and
    ``sec-filings``' the ``filings`` pass-through's for that window, so each reuses the other's
    copy. Raises ``ValueError`` for any other endpoint, and for ``sec-filings`` without
    ``today``: its params are the day's."""
    if endpoint not in PAGE_ENDPOINTS:
        raise ValueError(f"not a page endpoint: {endpoint}")
    if endpoint == _FILINGS:
        if today is None:
            raise ValueError(f"{_FILINGS} needs the day its window ends on")
        start, end = filings_window(today)
        return {
            "symbol": symbol,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "limit": str(FILINGS_LIMIT),
        }
    if endpoint in _PAGE_BY_YEAR:
        return {"symbol": symbol, "period": "annual", "limit": str(STATEMENT_YEARS)}
    limit = _PAGE_LIMITS.get(endpoint)
    return {"symbol": symbol} if limit is None else {"symbol": symbol, "limit": str(limit)}


def filings_window(today: date) -> tuple[date, date]:
    """The filings' window of a fetch on ``today``: ``FILINGS_WINDOW_DAYS`` before it, to it, the
    window the agents' filing list asks by default on that day (``filings_api``)."""
    return today - timedelta(days=FILINGS_WINDOW_DAYS), today


def _calls(fmp: Fmp, symbol: str, today: date) -> list[_Call]:
    """The calls for ``symbol`` in fetch order: the fifteen the engine reads, then the company
    page's sixteen, in the order of ``PAGE_ENDPOINTS`` with the params of ``page_params``; less
    the endpoints the adapter's plan does not serve (``fairband.plans``)."""
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

    page_sends: dict[str, Callable[[], VendorResponse]] = {
        "ratios-ttm": partial(fmp.ratios_ttm, symbol),
        "key-metrics-ttm": partial(fmp.key_metrics_ttm, symbol),
        "financial-growth": partial(fmp.financial_growth, symbol, GROWTH_YEARS),
        "financial-scores": partial(fmp.financial_scores, symbol),
        "price-change": partial(fmp.price_change, symbol),
        "price-target": partial(fmp.price_target, symbol),
        "grades": partial(fmp.grades, symbol),
        "dividends": partial(fmp.dividends, symbol, DIVIDEND_ROWS),
        "shares-float": partial(fmp.shares_float, symbol),
        "news": partial(fmp.news, symbol, NEWS_STORIES),
        "ratios-annual": partial(fmp.ratios, symbol, STATEMENT_YEARS),
        "key-metrics-annual": partial(fmp.key_metrics, symbol, STATEMENT_YEARS),
        "segments-product": partial(fmp.segments_product, symbol),
        "segments-geographic": partial(fmp.segments_geographic, symbol),
        _CALL_DATES: partial(fmp.transcript_dates, symbol),
        _FILINGS: partial(fmp.filings, symbol, *filings_window(today)),
    }
    as_reported = {"period": "annual", "limit": str(STATEMENT_YEARS)}
    calls = [
        statement("income", "annual", STATEMENT_YEARS),
        statement("balance", "annual", STATEMENT_YEARS),
        statement("cashflow", "annual", STATEMENT_YEARS),
        statement("income", "quarter", STATEMENT_QUARTERS),
        statement("cashflow", "quarter", STATEMENT_QUARTERS),
        statement("balance", "quarter", STATEMENT_QUARTERS),
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
        on_fmp("splits", {}, partial(fmp.splits, symbol)),
        *(
            _Call("fmp", endpoint, page_params(endpoint, symbol, today), page_sends[endpoint])
            for endpoint in PAGE_ENDPOINTS
        ),
    ]
    return [call for call in calls if fmp.plan.serves(call.endpoint)]


def _newest_transcript(conn: sqlite3.Connection, fmp: Fmp, symbol: str) -> Iterator[_Call]:
    """The call for the transcript of the newest earnings call (spec 2026-11-18 8.1), read from the
    store when the fetch reaches it, after the listed calls: where the newest usable stored
    ``transcript-dates`` answer names a call (``newest_call``) and no usable stored ``transcript``
    answer of its fiscal year and quarter, under the pass-through's params, holds words
    (``has_words``). With no reuse window: a call the vendor holds no words for yet is asked again
    at every fetch, and a call the store holds words for is never asked again. None otherwise,
    and none on a plan that serves no transcript (``fairband.plans``), whatever list the store
    holds. It reads every stored answer as data and raises on none."""
    if not fmp.plan.serves(TRANSCRIPT):
        return
    listed = latest_response(conn, "fmp", _CALL_DATES, symbol, page_params(_CALL_DATES, symbol))
    newest = None if listed is None else newest_call(_parsed(conn, listed.id))
    if newest is None:
        return
    year, quarter = newest
    params = {"symbol": symbol, "year": str(year), "quarter": str(quarter)}
    copies = usable_responses(conn, "fmp", TRANSCRIPT, symbol)
    if any(row.params == params and has_words(_parsed(conn, row.id)) for row in copies):
        return
    send = partial(fmp.transcript, symbol, year, quarter)
    yield _Call("fmp", TRANSCRIPT, params, send, reuses=False)


def _parsed(conn: sqlite3.Connection, response_id: int) -> Any:
    """A stored response's payload parsed; ``None`` without one, or when it does not parse."""
    text = response_payload(conn, response_id)
    try:
        return None if text is None else json.loads(text)
    except ValueError:
        return None


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
    the response; ``None`` when it gives none. The price history, a pair's history, the peers, the
    page endpoints and the newest call's transcript give no rows; the two histories' payloads are
    usable when they hold a close, the peers' when it names a peer or is exactly ``[]``, a page
    endpoint's and the transcript's when it is a list. The splits' payload is usable when it is a
    list, even one that gives no rows."""
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
        case "fx-history":
            return ([], []) if fx_closes(payload) else None
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
        case "splits":
            return ([], split_observations(payload, *source)) if isinstance(payload, list) else None
        case _ if endpoint in PAGE_ENDPOINTS or endpoint == TRANSCRIPT:
            return ([], []) if isinstance(payload, list) else None
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
