"""The agent's vendor pass-throughs (spec 2026-11-06 Tier 2, 15.3): vendor endpoints the engine
does not read, fetched on request with the server's keys and stored, so a report can cite a field
of one as ``response:<id>/<json pointer>``.

The kinds and the endpoints they are stored under, every one FMP's (provider ``fmp``):

- ``transcript``: ``transcript``, the earnings call of the fiscal ``year`` and ``quarter`` (1 to 4),
  both required; the company page's Investor relations tab reads a call's through this kind
  where the store holds no copy of it with words (``web.company_api``), so an agent's call and
  the tab's reuse each other's copy inside the window; no refresh asks one (B-252);
- ``news``: ``news``, the newest ``limit`` stories, 1 to ``NEWS_LIMIT_MAX`` (``NEWS_LIMIT`` when
  left out); the refresh stores each company's news under the same key at 60
  (``fetch.NEWS_STORIES``, ``fetch.page_params``), so a call at 60 and the refresh reuse each
  other's copy;
- ``segments``: two calls, ``segments-product`` and ``segments-geographic``, the revenue by product
  and by region, answered as the parts ``product`` and ``geographic``; the refresh stores each
  company's two under the same keys, the symbol alone (``fetch.page_params``, spec 2026-11-17
  8.1), so a call and the refresh reuse each other's copy;
- ``insider-trades``: ``insider-trades``, the newest insider trades, a page of
  ``INSIDER_TRADES_LIMIT``, which the reuse key holds; a ``limit`` (1 to that size) is checked
  here and cuts the route's answer, never the call or the stored page;
- ``transcript-dates``: ``transcript-dates``, the fiscal year, the quarter and the date of every
  earnings call on file, newest first, so the agent asks ``transcript`` for a call that exists;
  the Investor relations tab reads a company's through this kind as a reader opens it
  (``web.company_api``), under the same key, the symbol alone, so a call and the tab reuse each
  other's copy; no refresh asks one (B-252);
- ``dcf``: two calls, ``dcf`` and ``dcf-levered``, FMP's discounted cash flow value and its levered
  one, answered as the parts ``dcf`` and ``levered``: a cross-check a report may cite, never a
  value Fairband computes.

The trailing P/E history, ``SERIES_KIND`` (spec 2026-11-19 6.3; ``method.md`` 16.7), is fetched
and stored as the kinds are, but it is no kind of the generic route: the multiples history read
alone asks it, and builds the series from its answers (``reports.multiples.trailing_series``).
Its calls are built with the connection open, since the pair needs the company's reporting
currency (``store.currency.reporting_currency``); ``series_answers`` names what each is stored
under, the key the stored series is read back by:

- ``closes``: ``pe-closes``, the daily closes (``historical-price-eod/full``) from ``PE_YEARS``
  (ten) years before the clock's day;
- ``quarters``: ``pe-quarters``, the newest ``PE_QUARTERS_LIMIT`` (44) quarterly income
  statements;
- ``rates``, a company in another currency only: ``pe-rates``, the pair's closes
  (``historical-price-eod/light`` on ``USD<code>``, ``rates.pair_of``) from ``PE_RATE_YEARS``
  (eleven) years before the clock's day, since each period's EPS is read at its end's rate and
  the first day's trailing year reaches a year behind the closes, under the pair as the symbol,
  as the rates stage stores ``fx-history``; a code that names no pair has no call.

The endpoint names are the series' own: one stored as ``price-history`` would become the newest
copy of the five-year closes for every reader, the engine among them; one as ``income-quarter``
would become facts at the next refresh, since the statement backfill reads every response of
that endpoint whatever its params; one as ``fx-history`` would replace the three-year rates. No
fact and no observation is written from them. The closes' and the pair's start dates are left
out of their keys, ``years`` in their place, as the price history's is, so a key does not change
at midnight. Each answer is reused for ``reuse_hours``, usable when it is a list, the empty list
among them: a company listed last month has a series with no point, stored and reused like any
other.

The filing kinds, ``FILING_KINDS`` (spec 2026-11-11 filings access, 4), from FMP, are fetched and
stored as the others are, but they are not kinds of the generic route, whose answer is the whole
payload: ``KINDS`` stays that route's list, and ``unknown_kind`` names it alone.

- ``filings``: ``sec-filings``, every filing from ``from`` to ``to``, ISO dates, both required and
  ``from`` on or before ``to`` (else ``BAD_WINDOW``), a page of ``FILINGS_LIMIT`` rows, which the
  reuse key holds; the Investor relations tab reads a company's of the 365 days to the day
  through this kind as a reader opens its Filings view (``web.company_api``), so a call for that
  window, the filing list's default on that day, and the tab reuse each other's copy; no refresh
  asks one (B-252);
- ``filing-reports``: ``filing-report-dates``, the fiscal year and the period of every filing
  report on file, newest first;
- ``filing-report``: ``filing-report``, the 10-Q or the 10-K of the fiscal ``year`` and ``period``
  (``FILING_PERIODS``: ``FY``, ``Q1`` to ``Q4``), both required (``NEEDS_PERIOD``, ``BAD_PERIOD``),
  reused whatever its age, with no window (spec 2026-11-15 10): a filing does not change once
  filed, and a ``filing:`` ref names its stored copy by the response id, so a second copy would
  only split the cites of one filing over two ids. Nothing is deleted.

A ``news``, a ``segments`` part, a ``transcript-dates``, a ``filings``, a ``filing-reports`` or a
P/E history payload is usable when it is a list, a ``filing-report`` one when
``filing_report_usable``: FMP answers a period it does not hold, an unknown symbol, or some
failures with HTTP 200 and ``{"Error Message": ...}``. An unusable one is stored with the error
``unusable payload: ...``, answered as fetched, never reused; so neither the pass-through nor the
refresh reuses a ``news`` or a ``segments`` error body.

For each call, as ``fetch_company`` does: the newest HTTP 200 response to the same call (provider,
endpoint, symbol and the call's logical params, ``symbol`` among them) stored without an error is
reused when it was observed less than ``reuse_hours`` before the clock, or, a ``filing-report``,
whatever its age; else the vendor is called, outside any transaction, and the response is stored
with its body scrubbed of ``secrets`` (a key inside a link FMP answers among them). The answer's
payload is the stored text parsed, so it carries no key either. A body that is not JSON is stored
with the error ``unusable payload: ...`` and raises a ``VendorError``; a ``VendorError`` is stored
as a response row with its message and status and no payload, then raised, its message scrubbed.
None of the three is reused. A kind of several calls makes them in order and raises at the first
that fails: the answers stored before it stand.

The calls go through the FMP client the server builds on the limiter its refresh runs share, so
the pass-throughs keep the refresh's pace. They run on the request threads, the pool every sync
route of the app shares. What is bounded: at most ``PASSTHROUGH_SLOTS`` (four) vendor calls are in
flight at once; a call that finds every slot taken waits for one at most ``PASSTHROUGH_WAIT_S``
(ten seconds), holding its request's thread meanwhile, then raises ``PassthroughBusy`` (``BUSY``,
a 503 on the route), nothing called or stored, and the agent tries again. A reuse takes no slot.

The client is on the plan its key states (``Fmp.plan``, ``fairband.plans``). A kind with an
endpoint that plan does not serve is refused, ``NotServed``, after its parameters are checked and
before the store is read: on Premium ``transcript`` and ``transcript-dates``, "FMP's Premium plan
does not serve earnings calls" (``NOT_SERVED``). Nothing is called and nothing stored, and a
copy the store holds from another plan's time is not answered here, so a kind answers one way on
a plan; the company page's own reads still show what the store holds
(``fairband.web.company_api``).
"""

import json
import sqlite3
import threading
from collections.abc import Callable, Mapping
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import partial
from typing import Any

from fairband.plans import Plan
from fairband.policy import Policy
from fairband.refresh.fetch import _years_before, unusable
from fairband.refresh.rates import pair_of
from fairband.store.currency import reporting_currency
from fairband.store.vendor import (
    ResponseRow,
    latest_response,
    record_response,
    response_payload,
    response_row,
)
from fairband.vendors.fmp import FILINGS_LIMIT, INSIDER_TRADES_LIMIT, Fmp
from fairband.vendors.http import VendorError, VendorResponse
from fairband.vendors.scrub import scrub

KINDS = (
    "transcript",
    "news",
    "segments",
    "insider-trades",
    "transcript-dates",
    "dcf",
)
FILING_KINDS = ("filings", "filing-reports", "filing-report")  # not the generic route's
SERIES_KIND = "pe-history"  # the trailing P/E history's answers; not the generic route's
PE_CLOSES = "pe-closes"  # the endpoints the history's answers are stored under
PE_QUARTERS = "pe-quarters"
PE_RATES = "pe-rates"
PE_YEARS = 10  # the years of closes
PE_RATE_YEARS = 11  # the years of the pair's closes: the first day's trailing year reaches back
PE_QUARTERS_LIMIT = 44  # the quarterly income statements: eleven years
FILING_PERIODS = ("FY", "Q1", "Q2", "Q3", "Q4")
BAD_PERIOD = "period is FY or Q1 to Q4"
NEEDS_PERIOD = "a filing report needs year and period"
BAD_WINDOW = "from and to are ISO dates, from on or before to"
NEWS_LIMIT = 20
NEWS_LIMIT_MAX = 100
PASSTHROUGH_SLOTS = 4  # vendor calls in flight at once
PASSTHROUGH_WAIT_S = 10.0  # the longest a call waits for a slot
BUSY = "the pass-throughs are busy: four calls are in flight, try again"
NOT_SERVED = "FMP's {plan} plan does not serve {what}"
# What an endpoint a plan does not serve gives, in the sentence's words (``fairband.plans``).
_UNSERVED = {"transcript": "earnings calls", "transcript-dates": "earnings calls"}
FMP = "fmp"  # FMP's name in the store
_USD = "USD"
_KIND_LIST = ", ".join(KINDS[:-1]) + f" or {KINDS[-1]}"


class PassthroughBusy(Exception):
    """No slot freed within ``PASSTHROUGH_WAIT_S``: the message is ``BUSY``."""


class NotServed(Exception):
    """The plan of the pass-through's client serves no call of the kind asked: the message is
    ``NOT_SERVED`` with the plan and what it does not serve."""


@dataclass(frozen=True)
class Fetched:
    """One stored response: its row, its payload parsed and whether it was reused."""

    row: ResponseRow
    payload: Any
    reused: bool


@dataclass(frozen=True)
class SeriesAnswer:
    """What one of the P/E history's answers is stored under: its endpoint, the symbol (the
    company's, the pair's for the rates) and its logical params, the reuse key."""

    endpoint: str
    symbol: str
    params: dict[str, str]


def series_answers(symbol: str, currency: str) -> dict[str, SeriesAnswer]:
    """The P/E history's answers for ``symbol`` (the store's exchange form) reporting in
    ``currency``, by part: ``closes`` and ``quarters``, and ``rates`` for a currency other than
    USD that names a pair (``rates.pair_of``); the closes' key holds ``PE_YEARS``, the pair's
    ``PE_RATE_YEARS``."""
    years = str(PE_YEARS)
    quarters = {"symbol": symbol, "period": "quarter", "limit": str(PE_QUARTERS_LIMIT)}
    answers = {
        "closes": SeriesAnswer(PE_CLOSES, symbol, {"symbol": symbol, "years": years}),
        "quarters": SeriesAnswer(PE_QUARTERS, symbol, quarters),
    }
    if currency != _USD:
        try:
            pair = pair_of(currency)
        except ValueError:  # a code that names no pair: no rate to read
            return answers
        rate_years = {"symbol": pair, "years": str(PE_RATE_YEARS)}
        answers["rates"] = SeriesAnswer(PE_RATES, pair, rate_years)
    return answers


@dataclass(frozen=True)
class _Call:
    part: str
    endpoint: str
    params: dict[str, str]  # the logical params, the reuse key
    send: Callable[[], VendorResponse]
    ages: bool = True  # False: no window, a usable copy is reused whatever its age
    usable: Callable[[Any], bool] | None = None  # whether a JSON payload reads; any does if None
    symbol: str | None = None  # the symbol it is stored under; the company's when None


class Passthrough:
    """Fetches the kinds through ``fmp``; ``policy.refresh.reuse_hours`` is the reuse window,
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
        self._slots = threading.BoundedSemaphore(PASSTHROUGH_SLOTS)

    def close(self) -> None:
        """Close the vendor client."""
        self._fmp.close()

    @property
    def plan(self) -> Plan:
        """The plan the vendor client's key is on (``fairband.plans``)."""
        return self._fmp.plan

    def fetch(self, kind: str, symbol: str, params: Mapping[str, str]) -> dict[str, Fetched]:
        """The stored responses that answer ``kind`` for ``symbol`` (the store's exchange form), by
        part: ``product`` and ``geographic`` for ``segments``, ``dcf`` and ``levered`` for
        ``dcf``, ``closes``, ``quarters`` and, in another currency, ``rates`` for
        ``SERIES_KIND``, else the one part named ``kind``. Raises ``ValueError`` on an unknown kind
        or a missing or bad parameter, before any call, then ``NotServed`` where the client's plan
        does not serve one of the kind's endpoints, before the store is read and with no call,
        ``PassthroughBusy`` when no slot frees in time, and ``VendorError`` when a call fails."""
        with closing(self._conn_factory()) as conn:
            calls = self._calls(conn, kind, symbol, params)
            plan = self._fmp.plan
            for call in calls:
                if not plan.serves(call.endpoint):
                    what = _UNSERVED.get(call.endpoint, f"its {kind} data")
                    raise NotServed(NOT_SERVED.format(plan=plan.label, what=what))
            return {call.part: self._fetch(conn, call, symbol) for call in calls}

    def _fetch(self, conn: sqlite3.Connection, call: _Call, company: str) -> Fetched:
        symbol = company if call.symbol is None else call.symbol
        latest = latest_response(conn, FMP, call.endpoint, symbol, call.params)
        if latest is not None and (
            not call.ages or self._clock() - latest.observed_at < self._window
        ):
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
            conn, FMP, call.endpoint, call.params, symbol, status, payload, error, observed_at
        )

    def _calls(
        self, conn: sqlite3.Connection, kind: str, symbol: str, params: Mapping[str, str]
    ) -> list[_Call]:
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
                send = partial(fmp.news, symbol, limit)
                return [_Call(kind, "news", logical, send, usable=_is_list)]
            case "segments":
                product = partial(fmp.segments_product, symbol)
                geographic = partial(fmp.segments_geographic, symbol)
                logical = {"symbol": symbol}
                return [
                    _Call("product", "segments-product", logical, product, usable=_is_list),
                    _Call(
                        "geographic", "segments-geographic", logical, geographic, usable=_is_list
                    ),
                ]
            case "insider-trades":
                # ``limit`` cuts the answer, not the call (``vendor_api``): the page is fetched and
                # stored whole.
                limit = _whole(params, "limit")
                if limit is not None and not 1 <= limit <= INSIDER_TRADES_LIMIT:
                    raise ValueError(f"limit is 1 to {INSIDER_TRADES_LIMIT}")
                # The page size is in the reuse key, so a changed one never reuses older rows.
                logical = {"symbol": symbol, "limit": str(INSIDER_TRADES_LIMIT)}
                send = partial(fmp.insider_trades, symbol)
                return [_Call(kind, "insider-trades", logical, send)]
            case "transcript-dates":
                send = partial(fmp.transcript_dates, symbol)
                logical = {"symbol": symbol}
                return [_Call(kind, "transcript-dates", logical, send, usable=_is_list)]
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
            case "pe-history":  # SERIES_KIND: a bare name in a case would capture, not compare
                return self._series_calls(symbol, reporting_currency(conn, symbol))
            case "filings":
                start, end = _window(params)
                # The page size is in the reuse key, as insider-trades' is.
                logical = {
                    "symbol": symbol,
                    "from": start.isoformat(),
                    "to": end.isoformat(),
                    "limit": str(FILINGS_LIMIT),
                }
                send = partial(fmp.filings, symbol, start, end)
                return [_Call(kind, "sec-filings", logical, send, usable=_is_list)]
            case "filing-reports":
                send = partial(fmp.filing_report_dates, symbol)
                logical = {"symbol": symbol}
                return [_Call(kind, "filing-report-dates", logical, send, usable=_is_list)]
            case "filing-report":
                year, period = _whole(params, "year"), params.get("period")
                if year is None or period is None:
                    raise ValueError(NEEDS_PERIOD)
                if period not in FILING_PERIODS:
                    raise ValueError(BAD_PERIOD)
                logical = {"symbol": symbol, "year": str(year), "period": period}
                return [
                    _Call(
                        kind,
                        "filing-report",
                        logical,
                        partial(fmp.filing_report, symbol, year, period),
                        ages=False,  # a filing does not change once filed
                        usable=filing_report_usable,
                    )
                ]
        raise ValueError(unknown_kind(kind))

    def _series_calls(self, symbol: str, currency: str) -> list[_Call]:
        """The P/E history's calls for ``symbol`` reporting in ``currency``, in order: the closes
        from ``PE_YEARS`` before the clock's day, the quarters and, in another currency, the
        pair's closes from ``PE_RATE_YEARS`` before it, each stored under its ``series_answers``
        key."""
        fmp, today = self._fmp, self._clock().date()
        answers = series_answers(symbol, currency)
        sends = {
            "closes": partial(fmp.price_history, symbol, _years_before(today, PE_YEARS)),
            "quarters": partial(fmp.statement, symbol, "income", "quarter", PE_QUARTERS_LIMIT),
        }
        if "rates" in answers:
            start = _years_before(today, PE_RATE_YEARS)
            sends["rates"] = partial(fmp.fx_history, answers["rates"].symbol, start)
        return [
            _Call(part, a.endpoint, a.params, sends[part], usable=_is_list, symbol=a.symbol)
            for part, a in answers.items()
        ]


def filing_report_usable(payload: Any) -> bool:
    """Whether a ``filing-report`` payload is a report: an object without the key ``Error
    Message`` that holds a sheet, a key whose value is a list. FMP answers a period it does not
    hold, or an unknown symbol, with HTTP 200 and ``{"Error Message": ...}``."""
    return (
        isinstance(payload, dict)
        and "Error Message" not in payload
        and any(isinstance(value, list) for value in payload.values())
    )


def _is_list(payload: Any) -> bool:
    """Whether a ``news``, a ``segments`` part, a ``transcript-dates``, a ``filings``, a
    ``filing-reports`` or a P/E history payload reads: a list."""
    return isinstance(payload, list)


def _window(params: Mapping[str, str]) -> tuple[date, date]:
    """The filing list's ``from`` and ``to``: ISO dates, both required, ``from`` on or before
    ``to``, else ``BAD_WINDOW``."""
    try:
        start, end = date.fromisoformat(params["from"]), date.fromisoformat(params["to"])
    except (KeyError, ValueError):
        raise ValueError(BAD_WINDOW) from None
    if start > end:
        raise ValueError(BAD_WINDOW)
    return start, end


def unknown_kind(kind: str) -> str:
    """The sentence that refuses a kind outside ``KINDS``; it names ``KINDS`` alone, the generic
    route's list, and ``fetch`` raises it for a kind in none of that list, ``FILING_KINDS`` and
    ``SERIES_KIND``."""
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
