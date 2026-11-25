"""The company page's reads (the company page's design, 7.2, 7.4, 10.3, 10.4 and 10.5, the
Financials tab's design, 7.9 and 8.3, the Research tab's design, 8.1, and the Investor relations
tab's design, 7.5, 7.6 and 8.2). Each tab's own read is from the store alone: none calls a vendor,
so each is a plain GET that needs no request header. The Investor relations tab's three later
reads, of the list of earnings calls, of an earnings call and of a year of filings, answer from
the store where it holds a copy that does not change, and else through the pass-throughs
(``fairband.refresh.passthrough``); each may call a vendor, so each carries
``X-Fairband-Request: 1``, else 403 before anything else is read (``app``, D11). No refresh
stores the tab's lists or a call's words (B-252; the founder, 2026-11-18 and 2026-11-25: a reader
opens a few companies, and a refresh paid for all of them): the tab's read draws what the store
holds at once and names each list that is stale, and the page then asks the later reads, which
keep what they fetch. This is an exception, by that ruling, to the founder's ruling of
2026-11-16 that a page opens from the store alone.

Each tab's read answers ``quote``, the head's figures on every tab (``page_fmp.head_quote``:
``{price, change, changePercent, day}``, each ``null`` without a quote's row).

- ``GET /api/companies/{symbol}/page/overview`` answers ``{symbol, dataDate, quote, company,
  statistics, trading, priceChange, prices, news}``: the Company block (``page_fmp.company``),
  the Key statistics (``page_fmp.statistics``), the Trading group (``page_fmp.trading``), the
  price changes (``page_fmp.price_change``), the prices (``page_fmp.prices``), and ``news``,
  ``{stories, observedAt, stale, limit}``: the stored stories (``page_fmp.stories``), the time
  their answer was observed, ``null`` without one, whether a refresh would fetch them again, and
  ``limit``, the depth the refresh stores them at (``fetch.NEWS_STORIES``), at which the page
  asks the pass-through for newer ones.
- ``GET /api/companies/{symbol}/page/estimates`` answers ``{symbol, dataDate, quote, earnings,
  consensus, target, ratings}``: the Earnings block (``page_fmp.earnings``), the Consensus
  estimates (``page_fmp.consensus``), the price target (``page_fmp.target``) and the ratings
  (``page_fmp.ratings``).
- ``GET /api/companies/{symbol}/page/financials`` answers ``{symbol, dataDate, quote, currency,
  cadence, statements, segments, ratios}``: the tab's currency and the company's reporting
  cadence, ``quarterly`` or ``half-yearly``; ``statements``, the income statement, the balance
  sheet and the cash flow statement (``income``, ``balance``, ``cashflow``), each ``{annual,
  quarter}`` (``page_financials.statement``); ``segments``, the revenue by product and by region
  (``{product, region}``, ``page_financials.segments``); and ``ratios``, the ratios and the key
  metrics by fiscal year (``page_financials.ratios``). Each is a table, ``{columns, rows}``.
- ``GET /api/companies/{symbol}/page/research?report=<id>`` answers ``{symbol, dataDate, quote,
  reports, report, call, ofReport, records}``, ``dataDate`` ``null`` since the report's call
  carries its own days: ``reports``, the company's revisions newest first as the list read answers
  them (``reports_api.report_list``); ``report``, the revision ``report`` names, else the latest,
  whole as the report read answers it (``reports_api.report_json``), on the effective policy;
  ``call``, its value card's figures from the snapshot it rests on and the review and the
  secondary valuation it names (``research_page.report_call``, on that record's stored levels);
  ``ofReport``, ``{killCriteria, newsItems}``, the records its cards draw
  (``research_page.of_report``), each as the research read serves it; the three ``null`` for a
  company with no report. ``records`` is the research read's eight lists
  (``research_api.research_records``), with ``reviews``, the company's reviews as the reviews read
  serves them, without their results, each bridge line as the company detail serves it, with its
  input's label, its unit in the review's reporting currency and its override's reason and writer
  (``research_api.bridge_lines``), ``secondaryValuations``, its secondary valuations as their
  read serves them, each newest first, and ``ledgerCount``, the count of its ledger rows, which
  ``ledger`` cuts at the newest twenty. A report of another company is a 404, "report <id> is
  <its symbol>'s, not <symbol>'s"; an id that names none a 404, "no report <id>".
- ``GET /api/companies/{symbol}/page/investor-relations`` answers ``{symbol, dataDate, quote,
  nextEarnings, calls, callsDay, callsStale, callsServed, filings, filingsStale}``:
  ``nextEarnings``, the day of the next earnings date of the earnings
  (``page_fmp.next_earnings``), else ``null``; ``calls``, every call of the newest usable stored
  list of calls (``transcript-dates``), whatever its age, newest first, each with its quarter's
  four figures from the earnings row that is the call's (``page_investor.calls``), empty without
  a list; ``callsDay``, the day that list was observed, ``null`` without one; ``callsServed``,
  false where the plan of the server's key serves no list of calls (``fairband.plans``: Premium),
  so the page can say why a company has none and asks for none, and true on a plan that serves
  it and on a server with no FMP key, where nothing says the plan; a list the store holds from
  another plan's time is still answered in ``calls``; ``filings``, ``{from, to, rows, truncated,
  observedDay}`` of the tab's filing list: of the usable stored filing lists (``sec-filings``)
  of a whole window, their params exactly those of the 365 days to their ``to`` at
  ``FILINGS_LIMIT`` rows (``_window_params``), that end on or before the clock's day and on or
  before the day the list was observed, the one that ends latest, the newest among those that
  end on one day. So the list the tab's filings read fetched for the clock's day, an agent's
  default list of its day, or a refresh's of before B-252, each of the 365 days to its day and
  observed that day, and never an agent's list of an older window, of a narrower or a wider one
  asked the same day, or of one asked before its last day, which lacks what was filed after it;
  a list whose ``to`` is no ISO date is never the tab's either. It answers its window's first
  and last days, its rows newest first (``page_investor.filing_rows``), ``truncated``, true
  where it holds the vendor's limit of ``FILINGS_LIMIT`` rows, so the window's oldest filings
  are missing, and the day it was observed; ``null`` without one. ``callsStale`` and
  ``filingsStale`` are each true without its list, or where the list was observed at or before
  the clock's time less the effective policy's reuse window (``refresh.reuse_hours``), as
  ``news.stale`` is; the filing list also where its window ended before the day it was observed,
  an agent's list of a past window, which never held the days since. The page draws the stored
  list at once and asks the list's own read below
  for a newer one, the filing list's only as the reader opens the Filings view. Its ``dataDate``
  counts the quote's row and the earnings, which both views draw, as the estimates read counts
  its own, and neither list: each carries its own day, since the page may hold a newer one than
  this read answered, and the page works out each view's caption (the Investor relations tab's
  design, 7.6).
- ``GET /api/companies/{symbol}/page/investor-relations/calls`` answers ``{symbol, calls,
  callsDay}``, the tab's read's two fields of the list of calls, from the ``transcript-dates``
  pass-through's list: reused inside its window, else fetched and kept, the empty list of a
  company with no call among them. The calls' figures are the stored earnings rows', which stay
  a refresh's (the Estimates tab reads them). A list the pass-through stored as unusable (FMP's
  error object) is a 502, ``NO_CALLS``.
- ``GET /api/companies/{symbol}/page/investor-relations/call?year=&quarter=`` answers ``{symbol,
  fiscalYear, quarter, date, turns, questionsAt, observedDay}``, the call of the fiscal ``year``
  and ``quarter`` (``page_investor.transcript``) and the day its copy was fetched: the newest
  usable stored ``transcript`` answer of that call that holds words (``page_investor.has_words``),
  whatever its age, since a call's words do not change once the vendor holds them; else the
  ``transcript`` pass-through's, reused inside its window, an answer with no words among them
  (``turns`` empty), or fetched past it. An answer of the pass-through that is no list (FMP's
  error object, which the pass-through stores as an answer) is a 502, ``NO_TRANSCRIPT``.
- ``GET /api/companies/{symbol}/page/investor-relations/filings?to=`` answers ``{from, to, rows,
  truncated, observedDay}`` of the filing list of the 365 days to the ISO date ``to``
  (``_window``), on or before the clock's day, as the tab's read answers its filing list; ``to``
  left out is the clock's day, the tab's first window, which the page asks so, since the day is
  the server's to say. The newest usable stored list of exactly that window, whatever its age,
  where it was observed after ``to``, since a past year's list observed once the year was over
  does not change; else, a list observed on ``to`` or before it, none, or ``to`` the clock's
  day, the ``filings`` pass-through's, reused inside its window or fetched. A list the
  pass-through stored as unusable (FMP's error object) is a 502, ``filings_api.NO_LIST``.

Rules for the overview, the estimates, the financials and the Investor relations tab's read:

- An answer is the company's newest HTTP 200 FMP answer with no error to its endpoint under the
  params the fetch stores it with, whatever its age (``store.vendor.latest_response``), parsed;
  the filing list is the one above. An endpoint with none, or whose payload does not parse, has no
  answer, and its reader gives its figures ``null`` and its lists empty.
- The quote's row (10.4) is the symbol's row (``page_fmp.quote_row``) in the payload of the
  response that the company's newest ``quote`` observation cites: a fetch's quote, or a price
  refresh's batch, which is stored under no symbol.
- The overview draws the profile, the quote's row, the price history, the earnings (for the next
  date), the six answers of the Key statistics (``ratios-ttm``, ``key-metrics-ttm``,
  ``financial-growth``, ``financial-scores``, ``dividends``, ``shares-float``), the price changes
  and the news; the estimates the quote's row, the earnings, the annual consensus, the price
  target and the grades; the financials the quote's row and ten answers: the six statements
  (``income-annual``, ``income-quarter``, ``balance-annual``, ``balance-quarter``,
  ``cashflow-annual``, ``cashflow-quarter``), the ratios and the key metrics by fiscal year
  (``ratios-annual``, ``key-metrics-annual``) and the two segment answers (``segments-product``,
  ``segments-geographic``); the Investor relations tab's the quote's row, the earnings, the list
  of calls and the filing list.
- ``dataDate`` (7.4) is the day of the oldest observation among the answers the read drew, as ISO
  text, the news left out, since its stories carry their own days; ``null`` when it drew none. The
  financials' data date counts its ten answers alone, not the quote's row it answers for the head
  (the Financials tab's design, 8.3); the Investor relations tab's counts the quote's row and
  the earnings, and neither of its lists (above).
- ``news.stale`` (10.5) is true without a stored answer, or when it was observed at or before the
  clock's time less the effective policy's reuse window (``refresh.reuse_hours``).
- The consensus keeps the rows dated after the newest fiscal year's period end on file
  (``series_for``, the years the report tables' estimate columns follow) and the week a 52/53-week
  year's end drifts by (``inputs_statements.YEAR_END_DRIFT``): a row dated within that week is the
  year already reported. Every row is kept where no year is on file. A money figure in the
  reporting currency carries the company's (``store.currency.reporting_currency``), USD where it
  has no snapshot. The next earnings date and the last dividend payment are judged on the clock's
  day.
- The financials' currency (the Financials tab's design, 7.9 and 8.3) is the ``reportedCurrency``
  of the newest row of the annual income statement (``page_financials.reported_currency``), else
  the company's (``store.currency.reporting_currency``); every reader is handed it, for a column
  whose row names none. The cadence is ``half-yearly`` where the period ends of the quarterly
  income statement say so (``inputs_statements.cadence_of``, on each end once, oldest first, as
  the engine takes one end a date), and the three quarterly tables are then read by half-year;
  else ``quarterly``, a company whose cadence the rule cannot tell among them. The ratios and the
  two segment tables keep the newest ``fetch.STATEMENT_YEARS`` fiscal years, the statements'
  depth; a statement's table holds every dated row of its answer.

A symbol that is not one is a 400 with its sentence (``reports_api.checked_symbol``); a company
with no stored profile a 404, "no page data for <symbol>"; on the overview, the research read and
the Investor relations tab's read, which read the effective policy, a stored setting the policy
refuses a 409 (``settings_api.effective``). A company needs no
snapshot, but for the research read, which answers the same 404 for a company with none and needs
no stored profile.

The Investor relations tab's three later reads refuse, in the order they are judged, after the
403: a ``year`` or a ``quarter`` that is no whole number or left out, the framework's 400
(``year: ...``, ``app``); a symbol that is not one; a ``quarter`` outside 1 to 4,
``BAD_QUARTER``; a ``to`` that is no ISO date, or whose 365 days would start before the
calendar's first day, ``BAD_TO``; a ``to`` after the clock's day, ``FUTURE_TO``, a window that has
not ended, which the page never asks; each a 400, then the 404 of a company with no stored
profile.
Only then, and only where the store cannot answer, the pass-through's failures as the pass-through
route answers them: without a pass-through (the server has no FMP key) a 503, "no FMP key"; the
list of calls or a call's transcript on a plan that serves none (``fairband.plans``) a 402 with
the plan's sentence, "FMP's Premium plan does not serve earnings calls"; every
slot taken a 503 with its ``BUSY``; a failed vendor call a 502 with the vendor's sentence,
scrubbed; an answer that is no list, FMP's error object, a 502 with the read's own sentence
(``NO_CALLS``, ``NO_TRANSCRIPT``, ``filings_api.NO_LIST``). So a request refused before the store
is read calls no vendor and stores nothing. No answer of the tab's four reads carries a ref or a
response id: no report cites them. The three reads are sync ones, as the pass-through route is:
FastAPI runs them on its thread pool, where a vendor call waits at most ten seconds for one of
the pass-through's slots.
"""

import json
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import FastAPI, HTTPException

from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.fetch import (
    EARNINGS_ROWS,
    NEWS_STORIES,
    PAGE_ENDPOINTS,
    STATEMENT_QUARTERS,
    STATEMENT_YEARS,
    page_params,
)
from fairband.refresh.inputs_statements import YEAR_END_DRIFT, cadence_of, series_for
from fairband.refresh.passthrough import NotServed, Passthrough, PassthroughBusy
from fairband.store.currency import reporting_currency
from fairband.store.ledger import entry_count
from fairband.store.observations import observations_for
from fairband.store.overrides import overrides_for
from fairband.store.reports import ReportRow, report_row, reports_for
from fairband.store.research import kill_criteria_for, news_items_for
from fairband.store.reviews import review_row, reviews_for
from fairband.store.secondary import secondaries_for, secondary_row
from fairband.store.snapshots import latest_snapshot, snapshot_row
from fairband.store.vendor import (
    ResponseRow,
    latest_response,
    response_payload,
    usable_responses,
)
from fairband.vendors import page_financials as financials
from fairband.vendors import page_fmp
from fairband.vendors import page_investor as investor
from fairband.vendors.fmp import ANNUAL_ESTIMATE_LIMIT, FILINGS_LIMIT, StatementKind
from fairband.vendors.http import VendorError
from fairband.web.agents_api import criterion_json, record_json
from fairband.web.filings_api import NO_LIST, WINDOW_DAYS
from fairband.web.reports_api import checked_symbol, report_json, report_list
from fairband.web.research_api import bridge_lines, research_records
from fairband.web.research_page import of_report, report_call
from fairband.web.reviews_api import review_json, secondary_json
from fairband.web.settings_api import effective
from fairband.web.vendor_api import NO_FMP_KEY

# The page answers of the Key statistics (the design's 8.3).
_STATISTICS = (
    "ratios-ttm",
    "key-metrics-ttm",
    "financial-growth",
    "financial-scores",
    "dividends",
    "shares-float",
)
# The ten answers of the Financials tab (the Financials tab's design, 8.3): the six statements,
# the ratios and the key metrics by fiscal year, and the two segment answers.
_FINANCIALS = (
    "income-annual",
    "income-quarter",
    "balance-annual",
    "balance-quarter",
    "cashflow-annual",
    "cashflow-quarter",
    "ratios-annual",
    "key-metrics-annual",
    "segments-product",
    "segments-geographic",
)
_STATEMENT_KINDS: tuple[StatementKind, ...] = ("income", "balance", "cashflow")
# The params beside the symbol that the fetch stores the engine's answers the page reads under
# (``fetch._calls``); the page's own are ``fetch.page_params``.
_ENGINE_PARAMS: dict[str, dict[str, str]] = {
    "profile": {},
    "price-history": {},
    "earnings": {"limit": str(EARNINGS_ROWS)},
    "estimates-annual": {"period": "annual", "limit": str(ANNUAL_ESTIMATE_LIMIT)},
    "income-annual": {"period": "annual", "limit": str(STATEMENT_YEARS)},
    "balance-annual": {"period": "annual", "limit": str(STATEMENT_YEARS)},
    "cashflow-annual": {"period": "annual", "limit": str(STATEMENT_YEARS)},
    "income-quarter": {"period": "quarter", "limit": str(STATEMENT_QUARTERS)},
    "balance-quarter": {"period": "quarter", "limit": str(STATEMENT_QUARTERS)},
    "cashflow-quarter": {"period": "quarter", "limit": str(STATEMENT_QUARTERS)},
}
# The Investor relations tab's answers as stored, each under its pass-through's endpoint and params
# (``refresh.passthrough``; B-252: no fetch stores them): the list of calls under the symbol
# alone, each filing list under its window (``_window_params``) and each call's transcript under
# its fiscal year and quarter.
_CALL_DATES = "transcript-dates"
_FILINGS = "sec-filings"
_TRANSCRIPT = "transcript"
BAD_QUARTER = "quarter must be 1 to 4"  # the transcript pass-through's sentence
BAD_TO = "to must be an ISO date from 0002-01-01 on"  # its 365 days start in the calendar
FUTURE_TO = "to must be today or earlier"
NO_TRANSCRIPT = "FMP answered no transcript for {symbol}"  # as ``filings_api.NO_LIST``
NO_CALLS = "FMP answered no list of earnings calls for {symbol}"  # as that one too


@dataclass(frozen=True)
class _Answer:
    """A stored answer, parsed, and the time it was observed."""

    payload: Any
    observed_at: datetime


@dataclass(frozen=True)
class _Copy:
    """A stored response the Investor relations tab draws: its row, which holds its params and
    the time it was observed, and its payload parsed."""

    row: ResponseRow
    payload: Any


def add_company_page_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    clock: Callable[[], datetime],
    passthrough: Passthrough | None,
) -> None:
    """Register the company page's reads; ``policy`` is the file's, which the user's settings
    overlay, ``tax`` the table a report's references read the statements with, and ``clock`` gives
    the time the news and the Investor relations tab's two lists are judged stale at, the day
    the next earnings date and the last dividend payment are judged on, and the day a filing
    window ending before it is a past one. ``passthrough`` fetches what the store cannot answer
    on the Investor relations tab's three later reads, which answer 503 without one."""

    @app.get("/api/companies/{symbol}/page/overview")
    def page_overview(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        now = clock()
        today = now.date()
        with closing(conn_factory()) as conn:
            profile = _profile(conn, symbol)
            window = timedelta(hours=effective(conn, policy).refresh.reuse_hours)
            quote = _quote(conn, symbol)
            history = _stored(conn, "price-history", symbol)
            earnings = _stored(conn, "earnings", symbol)
            statistics = {endpoint: _stored(conn, endpoint, symbol) for endpoint in _STATISTICS}
            change = _stored(conn, "price-change", symbol)
            news = _stored(conn, "news", symbol)
            reporting = reporting_currency(conn, symbol)
        drawn = [profile, quote, history, earnings, change, *statistics.values()]
        row = _payload(quote)
        upcoming = page_fmp.next_earnings(_payload(earnings), today)
        answers = {endpoint: _payload(found) for endpoint, found in statistics.items()}
        return {
            "symbol": symbol,
            "dataDate": _data_date(drawn),
            "quote": page_fmp.head_quote(row),
            "company": page_fmp.company(profile.payload),
            "statistics": page_fmp.statistics(answers, profile.payload, row, reporting, today),
            "trading": page_fmp.trading(
                row, profile.payload, None if upcoming is None else upcoming["day"]
            ),
            "priceChange": page_fmp.price_change(_payload(change)),
            "prices": page_fmp.prices(_payload(history), row),
            "news": {
                "stories": page_fmp.stories(_payload(news)),
                "observedAt": None if news is None else news.observed_at.isoformat(),
                "stale": news is None or news.observed_at <= now - window,
                "limit": NEWS_STORIES,
            },
        }

    @app.get("/api/companies/{symbol}/page/estimates")
    def page_estimates(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        today = clock().date()
        with closing(conn_factory()) as conn:
            _profile(conn, symbol)
            quote = _quote(conn, symbol)
            earnings = _stored(conn, "earnings", symbol)
            consensus = _stored(conn, "estimates-annual", symbol)
            target = _stored(conn, "price-target", symbol)
            grades = _stored(conn, "grades", symbol)
            years = series_for(conn, symbol)
            reporting = reporting_currency(conn, symbol)
        after = years[-1].period_end + YEAR_END_DRIFT if years else None
        return {
            "symbol": symbol,
            "dataDate": _data_date([quote, earnings, consensus, target, grades]),
            "quote": page_fmp.head_quote(_payload(quote)),
            "earnings": page_fmp.earnings(_payload(earnings), today),
            "consensus": page_fmp.consensus(_payload(consensus), after, reporting),
            "target": page_fmp.target(_payload(target)),
            "ratings": page_fmp.ratings(_payload(grades)),
        }

    @app.get("/api/companies/{symbol}/page/financials")
    def page_financials(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            _profile(conn, symbol)
            quote = _quote(conn, symbol)
            drawn = {endpoint: _stored(conn, endpoint, symbol) for endpoint in _FINANCIALS}
            reporting = reporting_currency(conn, symbol)
        answers = {endpoint: _payload(found) for endpoint, found in drawn.items()}
        named = financials.reported_currency(answers["income-annual"])
        currency = reporting if named is None else named
        ends = list(dict.fromkeys(financials.period_ends(answers["income-quarter"])))
        half_yearly = cadence_of(ends) == "half-yearly"
        return {
            "symbol": symbol,
            "dataDate": _data_date(drawn.values()),
            "quote": page_fmp.head_quote(_payload(quote)),
            "currency": currency,
            "cadence": "half-yearly" if half_yearly else "quarterly",
            "statements": {
                kind: {
                    "annual": financials.statement(answers[f"{kind}-annual"], kind, currency),
                    "quarter": financials.statement(
                        answers[f"{kind}-quarter"],
                        kind,
                        currency,
                        quarterly=True,
                        half_yearly=half_yearly,
                    ),
                }
                for kind in _STATEMENT_KINDS
            },
            "segments": {
                "product": financials.segments(
                    answers["segments-product"], currency, STATEMENT_YEARS
                ),
                "region": financials.segments(
                    answers["segments-geographic"], currency, STATEMENT_YEARS
                ),
            },
            "ratios": financials.ratios(
                answers["ratios-annual"], answers["key-metrics-annual"], currency, STATEMENT_YEARS
            ),
        }

    @app.get("/api/companies/{symbol}/page/research")
    def page_research(symbol: str, report: int | None = None) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            if latest_snapshot(conn, symbol) is None:
                raise HTTPException(404, f"no page data for {symbol}")
            current = effective(conn, policy)
            revisions = reports_for(conn, symbol)
            shown = _shown(conn, symbol, revisions, report)
            quote = _quote(conn, symbol)
            overrides = {o.id: o for o in overrides_for(conn, symbol)}
            records = {
                **research_records(conn, symbol),
                # the made reviews and the copies a refresh carried; a reading shows nowhere on
                # the page but the opened detail of a value expired early (spec 2026-11-23 held
                # reviewed value, 5.7)
                "reviews": [
                    review_json(r, with_result=False) | {"bridge": bridge_lines(r, overrides)}
                    for r in reviews_for(conn, symbol)
                    if r.kind != "reading"
                ],
                "secondaryValuations": [secondary_json(s) for s in secondaries_for(conn, symbol)],
                "ledgerCount": entry_count(conn, symbol),
            }
            if shown is None:
                parts: dict[str, Any] = {"report": None, "call": None, "ofReport": None}
            else:
                parts = _report_parts(conn, shown, current, tax)
        return {
            "symbol": symbol,
            "dataDate": None,
            "quote": page_fmp.head_quote(_payload(quote)),
            "reports": report_list(revisions),
            **parts,
            "records": records,
        }

    @app.get("/api/companies/{symbol}/page/investor-relations")
    def page_investor_relations(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        now = clock()
        today = now.date()
        with closing(conn_factory()) as conn:
            _profile(conn, symbol)
            reuse = timedelta(hours=effective(conn, policy).refresh.reuse_hours)
            quote = _quote(conn, symbol)
            earnings = _stored(conn, "earnings", symbol)
            dates = _stored(conn, _CALL_DATES, symbol)
            window = _latest_window(conn, symbol, today)
        upcoming = page_fmp.next_earnings(_payload(earnings), today)
        return {
            "symbol": symbol,
            "dataDate": _data_date([quote, earnings]),  # each list carries its own day (7.6)
            "quote": page_fmp.head_quote(_payload(quote)),
            "nextEarnings": None if upcoming is None else upcoming["day"],
            "calls": investor.calls(_payload(dates), _payload(earnings)),
            "callsDay": None if dates is None else dates.observed_at.date().isoformat(),
            "callsStale": dates is None or dates.observed_at <= now - reuse,
            "callsServed": passthrough is None or passthrough.plan.serves(_CALL_DATES),
            "filings": None if window is None else _filing_list(window),
            "filingsStale": window is None or _stale_window(window.row, now - reuse),
        }

    @app.get("/api/companies/{symbol}/page/investor-relations/calls")
    def page_investor_calls(symbol: str) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        with closing(conn_factory()) as conn:
            _profile(conn, symbol)
            earnings = _stored(conn, "earnings", symbol)
        copy = _asked(passthrough, _CALL_DATES, symbol, {})  # the kind is the endpoint's name
        if copy.row.error is not None:  # FMP's error object, stored with its error
            raise HTTPException(502, NO_CALLS.format(symbol=symbol))
        return {
            "symbol": symbol,
            "calls": investor.calls(copy.payload, _payload(earnings)),
            "callsDay": copy.row.observed_at.date().isoformat(),
        }

    @app.get("/api/companies/{symbol}/page/investor-relations/call")
    def page_investor_call(symbol: str, year: int, quarter: int) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        if not 1 <= quarter <= 4:
            raise HTTPException(400, BAD_QUARTER)
        asked = {"year": str(year), "quarter": str(quarter)}
        with closing(conn_factory()) as conn:
            _profile(conn, symbol)
            copy = _with_words(conn, symbol, {"symbol": symbol, **asked})
        if copy is None:  # the store holds no words for the call: the pass-through's window holds
            copy = _asked(passthrough, "transcript", symbol, asked)
            if not isinstance(copy.payload, list):  # FMP's error object, stored as an answer
                raise HTTPException(502, NO_TRANSCRIPT.format(symbol=symbol))
        return {
            "symbol": symbol,
            "fiscalYear": year,
            "quarter": quarter,
            **investor.transcript(copy.payload),
            "observedDay": copy.row.observed_at.date().isoformat(),
        }

    @app.get("/api/companies/{symbol}/page/investor-relations/filings")
    def page_investor_filings(symbol: str, to: str | None = None) -> dict[str, Any]:
        symbol = checked_symbol(symbol)
        today = clock().date()
        start, end = _window(today) if to is None else _window_to(to)
        if end > today:  # a window that has not ended: the page never asks one
            raise HTTPException(400, FUTURE_TO)
        past = end < today
        with closing(conn_factory()) as conn:
            _profile(conn, symbol)
            copy = _stored_window(conn, symbol, end) if past else None
        if copy is None:  # today's window, or a past one not on file: the pass-through's holds
            window = {"from": start.isoformat(), "to": end.isoformat()}
            copy = _asked(passthrough, "filings", symbol, window)
            if copy.row.error is not None:  # FMP's error object, stored with its error
                raise HTTPException(502, NO_LIST.format(symbol=symbol))
        return _filing_list(copy)


def _latest_window(conn: sqlite3.Connection, symbol: str, today: date) -> _Copy | None:
    """The tab's filing list (the Investor relations tab's design, 8.2): of the company's usable
    stored filing lists of a whole window (``_whole_window``) that ends on or before ``today`` and
    on or before the day it was observed, the one that ends latest, the newest among those that
    end on one day; so the list the tab's filings read fetched for its day, an agent's default
    list of its day or a refresh's of before B-252, each of the 365 days to its day and observed
    that day, and never a list of a window that ends before that one's, of a narrower or a wider
    one asked the same day, or of one asked before its last day, which lacks what was filed
    after it. ``None`` without one, or when its payload does not parse."""
    whole = [
        (end, row)
        for row in usable_responses(conn, "fmp", _FILINGS, symbol)
        if (end := _whole_window(row, symbol)) is not None
        and end <= today
        and end <= row.observed_at.date()
    ]
    if not whole:
        return None
    _, latest = max(whole, key=lambda pair: (pair[0], pair[1].id))
    payload = _parsed(response_payload(conn, latest.id))
    return None if payload is None else _Copy(latest, payload)


def _whole_window(row: ResponseRow, symbol: str) -> date | None:
    """The day a stored filing list's window ends, where its params are exactly those of the 365
    days to that day at ``FILINGS_LIMIT`` rows (``_window_params``), the shape the tab's filings
    read, the agents' default list and a refresh of before B-252 store; ``None`` for any other
    window, and for a ``to`` that is no ISO date or whose 365 days fall outside the calendar."""
    try:
        end = date.fromisoformat(row.params["to"])
        return end if row.params == _window_params(symbol, end) else None
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _stale_window(row: ResponseRow, fresh_from: datetime) -> bool:
    """Whether the tab's filing list ``row`` (``_latest_window``) is stale: observed at or before
    ``fresh_from``, the clock's time less the reuse window, or a list of a window that ended
    before the day it was observed, which never held the days since: an agent's list of a past
    window, asked an hour ago, is no list of today's filings."""
    ended = date.fromisoformat(row.params["to"])  # an ISO date: ``_whole_window`` read it
    return row.observed_at <= fresh_from or ended < row.observed_at.date()


def _stored_window(conn: sqlite3.Connection, symbol: str, end: date) -> _Copy | None:
    """The newest usable stored filing list of the 365 days to ``end``, under the params the
    ``filings`` pass-through stores it with (``_window_params``), whatever its age, where it was
    observed after ``end``, the window's last day: a list observed on that day or before it, as
    the tab's first window is, lacks what was filed after it. ``None`` without one, or when its
    payload does not parse."""
    found = latest_response(conn, "fmp", _FILINGS, symbol, _window_params(symbol, end))
    if found is None or found.observed_at.date() <= end:
        return None
    payload = _parsed(response_payload(conn, found.id))
    return None if payload is None else _Copy(found, payload)


def _with_words(conn: sqlite3.Connection, symbol: str, params: dict[str, str]) -> _Copy | None:
    """The newest usable stored ``transcript`` answer under ``params`` that holds words
    (``page_investor.has_words``), whatever its age; ``None`` without one. A newer copy with no
    words hides no older one with them."""
    for row in usable_responses(conn, "fmp", _TRANSCRIPT, symbol):
        if row.params == params:
            payload = _parsed(response_payload(conn, row.id))
            if investor.has_words(payload):
                return _Copy(row, payload)
    return None


def _asked(
    passthrough: Passthrough | None, kind: str, symbol: str, params: dict[str, str]
) -> _Copy:
    """The pass-through's one stored response to ``kind`` for ``symbol``, the store's form: reused
    inside its window, else fetched and stored. Its failures as the pass-through route answers
    them: without a pass-through (the server has no FMP key) a 503, ``NO_FMP_KEY``; a parameter it
    refuses a 400; a kind the plan of the server's key does not serve a 402 with the plan's
    sentence; every slot taken a 503; a failed call a 502 with the vendor's sentence, which
    the pass-through has scrubbed."""
    if passthrough is None:
        raise HTTPException(503, NO_FMP_KEY)
    try:
        fetched = passthrough.fetch(kind, symbol, params)[kind]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except NotServed as exc:
        raise HTTPException(402, str(exc)) from None
    except PassthroughBusy as exc:
        raise HTTPException(503, str(exc)) from None
    except VendorError as exc:
        raise HTTPException(502, str(exc)) from None
    return _Copy(fetched.row, fetched.payload)


def _window_to(text: str) -> tuple[date, date]:
    """The first and last days of the filing window of the 365 days to the ISO date ``text``
    (``_window``); a 400, ``BAD_TO``, when it is no date or when the window would
    start before the calendar's first day."""
    try:
        return _window(date.fromisoformat(text))
    except (ValueError, OverflowError):
        raise HTTPException(400, BAD_TO) from None


def _window(end: date) -> tuple[date, date]:
    """The first and last days of the tab's filing window that ends on ``end``: the
    ``WINDOW_DAYS`` before it, to it, the window the agents' filing list asks by default on that
    day (``filings_api``)."""
    return end - timedelta(days=WINDOW_DAYS), end


def _window_params(symbol: str, end: date) -> dict[str, str]:
    """The params the ``filings`` pass-through stores ``symbol``'s filing list of the window to
    ``end`` under (``_window``), at ``FILINGS_LIMIT`` rows: the reuse key the tab's reads find a
    list by."""
    start, end = _window(end)
    return {
        "symbol": symbol,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "limit": str(FILINGS_LIMIT),
    }


def _filing_list(copy: _Copy) -> dict[str, Any]:
    """A stored filing list as the tab's reads answer it: its window's first and last days, its
    rows newest first (``page_investor.filing_rows``), ``truncated``, true where it holds the
    vendor's limit of ``FILINGS_LIMIT`` rows, so the window's oldest filings are missing, and
    ``observedDay``, the day it was observed, which the Filings view's data date counts (the
    Investor relations tab's design, 7.6)."""
    payload = copy.payload
    return {
        "from": copy.row.params.get("from"),
        "to": copy.row.params.get("to"),
        "rows": investor.filing_rows(payload),
        "truncated": isinstance(payload, list) and len(payload) >= FILINGS_LIMIT,
        "observedDay": copy.row.observed_at.date().isoformat(),
    }


def _shown(
    conn: sqlite3.Connection, symbol: str, revisions: Sequence[ReportRow], report_id: int | None
) -> ReportRow | None:
    """The revision the research read shows: the one ``report_id`` names, else the latest of
    ``revisions``, the company's newest first; ``None`` for a company with none. A 404 for an id
    that names no report or another company's."""
    if report_id is None:
        return revisions[0] if revisions else None
    found = report_row(conn, report_id)
    if found is None:
        raise HTTPException(404, f"no report {report_id}")
    if found.symbol != symbol:
        raise HTTPException(404, f"report {report_id} is {found.symbol}'s, not {symbol}'s")
    return found


def _report_parts(
    conn: sqlite3.Connection, report: ReportRow, policy: Policy, tax: TaxTable
) -> dict[str, Any]:
    """``report`` whole, its call and the records its cards draw (the module docstring), on the
    effective ``policy``."""
    snapshot = snapshot_row(conn, report.snapshot_id)
    assert snapshot is not None  # a report is stored on its company's snapshot
    review = None if report.review_id is None else review_row(conn, report.review_id)
    secondary = None if report.secondary_id is None else secondary_row(conn, report.secondary_id)
    symbol = report.symbol
    criteria, news = of_report(
        report, kill_criteria_for(conn, symbol), news_items_for(conn, symbol)
    )
    reporting = reporting_currency(conn, symbol)
    return {
        "report": report_json(conn, report, policy, tax),
        "call": report_call(snapshot, review, secondary),
        "ofReport": {
            "killCriteria": [criterion_json(k, reporting) for k in criteria],
            "newsItems": [record_json(n) for n in news],
        },
    }


def _profile(conn: sqlite3.Connection, symbol: str) -> _Answer:
    """The company's stored profile; a 404 without one."""
    found = _stored(conn, "profile", symbol)
    if found is None:
        raise HTTPException(404, f"no page data for {symbol}")
    return found


def _stored(conn: sqlite3.Connection, endpoint: str, symbol: str) -> _Answer | None:
    """The company's newest usable answer to ``endpoint`` under the fetch's params; ``None``
    without one, or when its payload does not parse."""
    if endpoint in PAGE_ENDPOINTS:
        params = page_params(endpoint, symbol)
    elif endpoint == _CALL_DATES:
        params = {"symbol": symbol}  # the ``transcript-dates`` pass-through's
    else:
        params = {"symbol": symbol, **_ENGINE_PARAMS[endpoint]}
    response = latest_response(conn, "fmp", endpoint, symbol, params)
    if response is None:
        return None
    payload = _parsed(response_payload(conn, response.id))
    return None if payload is None else _Answer(payload, response.observed_at)


def _quote(conn: sqlite3.Connection, symbol: str) -> _Answer | None:
    """The quote's row (the module docstring), observed when its response was; ``None`` without
    a ``quote`` observation, or where the response it cites holds no row for the symbol."""
    cited = max(observations_for(conn, symbol, "quote"), key=lambda r: r.response_id, default=None)
    if cited is None:
        return None
    row = page_fmp.quote_row(_parsed(response_payload(conn, cited.response_id)), symbol)
    return None if row is None else _Answer(row, cited.observed_at)


def _parsed(text: str | None) -> Any:
    """A stored payload parsed; ``None`` without one, or when it does not parse."""
    try:
        return None if text is None else json.loads(text)
    except ValueError:
        return None


def _payload(answer: _Answer | None) -> Any:
    return None if answer is None else answer.payload


def _data_date(answers: Iterable[_Answer | None]) -> str | None:
    """The day of the oldest observation among ``answers``, as ISO text; ``None`` without one."""
    days = [answer.observed_at.date() for answer in answers if answer is not None]
    return min(days).isoformat() if days else None
