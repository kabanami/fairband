"""The company page's four reads (the company page's design, 7.2, 7.4, 10.3, 10.4 and 10.5, the
Financials tab's design, 7.9 and 8.3, and the Research tab's design, 8.1), each from the store
alone: none calls a vendor, so each is a plain GET that needs no request header.

Each answers ``quote``, the head's figures on every tab (``page_fmp.head_quote``: ``{price,
change, changePercent, day}``, each ``null`` without a quote's row).

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
  secondary valuation it names (``research_page.report_call``, on the policy's designation edges);
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

Rules for the overview, the estimates and the financials:

- An answer is the company's newest HTTP 200 FMP answer with no error to its endpoint under the
  params the fetch stores it with, whatever its age (``store.vendor.latest_response``), parsed.
  An endpoint with none, or whose payload does not parse, has no answer, and its reader gives its
  figures ``null`` and its lists empty.
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
  ``segments-geographic``).
- ``dataDate`` (7.4) is the day of the oldest observation among the answers the read drew, as ISO
  text, the news left out, since its stories carry their own days; ``null`` when it drew none. The
  financials' data date counts its ten answers alone, not the quote's row it answers for the head
  (the Financials tab's design, 8.3).
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
with no stored profile a 404, "no page data for <symbol>"; on the overview and the research read,
a stored setting the policy refuses a 409 (``settings_api.effective``). A company needs no
snapshot, but for the research read, which answers the same 404 for a company with none and needs
no stored profile.
"""

import json
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
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
from fairband.store.currency import reporting_currency
from fairband.store.ledger import entry_count
from fairband.store.observations import observations_for
from fairband.store.overrides import overrides_for
from fairband.store.reports import ReportRow, report_row, reports_for
from fairband.store.research import kill_criteria_for, news_items_for
from fairband.store.reviews import review_row, reviews_for
from fairband.store.secondary import secondaries_for, secondary_row
from fairband.store.snapshots import latest_snapshot, snapshot_row
from fairband.store.vendor import latest_response, response_payload
from fairband.vendors import page_financials as financials
from fairband.vendors import page_fmp
from fairband.vendors.fmp import ANNUAL_ESTIMATE_LIMIT, StatementKind
from fairband.web.agents_api import criterion_json, record_json
from fairband.web.reports_api import checked_symbol, report_json, report_list
from fairband.web.research_api import bridge_lines, research_records
from fairband.web.research_page import of_report, report_call
from fairband.web.reviews_api import review_json, secondary_json
from fairband.web.settings_api import effective

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


@dataclass(frozen=True)
class _Answer:
    """A stored answer, parsed, and the time it was observed."""

    payload: Any
    observed_at: datetime


def add_company_page_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    clock: Callable[[], datetime],
) -> None:
    """Register the company page's four reads; ``policy`` is the file's, which the user's settings
    overlay, ``tax`` the table a report's references read the statements with, and ``clock`` gives
    the time the news is judged stale at and the day the next earnings date and the last dividend
    payment are judged on."""

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
                "reviews": [
                    review_json(r, with_result=False) | {"bridge": bridge_lines(r, overrides)}
                    for r in reviews_for(conn, symbol)
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
        "call": report_call(snapshot, review, secondary, policy.designation_edges),
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
