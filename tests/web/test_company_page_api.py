"""Three of the company page's reads, the overview, the estimates and the financials (the company
page's design, 7.4, 10.3, 10.4 and 10.5, and the Financials tab's design, 7.9 and 8.3; the
Research tab's read is ``test_research_page_api.py``'s, the Investor relations tab's three
``test_investor_page_api.py``'s), and the two fields the company's detail gains (7.2 and 11.1), on
the database of ``conftest.py``: AAPL valued on the Mature Growth route, AAL refused for its target
margin, HGCO valued on the revenue growth route.

The page's company is ``page_payloads``' LFOX, which has no snapshot unless a test values one. Its
FMP answers are stored as the refresh stores them: each under the fetch's params, a quote with its
observations. The expected figures are the readers' (``vendors.page_fmp`` and
``vendors.page_financials``) on the same payloads, whose own tests read each field: these tests
check what each read hands each reader. The financials answer is ``page_answers``', the one the
page's node tests draw."""

import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from refresh.vendor_double import FMP_KEY, Router
from support import page_answers as answers
from support import page_payloads as pages
from support.engine_companies import (
    fx_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.payloads import store_payloads
from support.vendor import Vendor, passthrough_client
from support.web import HEADER, NOW, TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import review_company
from fairband.engine.route import value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.refresh.fetch import (
    EARNINGS_ROWS,
    PAGE_ENDPOINTS,
    STATEMENT_QUARTERS,
    STATEMENT_YEARS,
    fetch_company,
    page_params,
)
from fairband.refresh.inputs_statements import YEAR_END_DRIFT
from fairband.refresh.passthrough import Passthrough
from fairband.store.db import connect
from fairband.store.ledger import Writer
from fairband.store.moat import set_moat
from fairband.store.observations import insert_observations
from fairband.store.overrides import insert_override
from fairband.store.reviews import insert_review
from fairband.store.settings import write_settings
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.store.vendor import record_response
from fairband.vendors import fmp as fmp_api
from fairband.vendors import page_financials, page_fmp
from fairband.vendors.fmp import ANNUAL_ESTIMATE_LIMIT, Fmp
from fairband.vendors.http import VendorHttp
from fairband.vendors.normalize_fmp import quote_observations

SYMBOL = pages.SYMBOL
AT = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)  # 90 minutes before the clock's NOW
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
OVERVIEW = f"/api/companies/{SYMBOL}/page/overview"
ESTIMATES = f"/api/companies/{SYMBOL}/page/estimates"
FINANCIALS = f"/api/companies/{SYMBOL}/page/financials"
# The answers of the Key statistics, which the overview draws (the company page's design, 8.3).
STATISTICS = (
    "ratios-ttm",
    "key-metrics-ttm",
    "financial-growth",
    "financial-scores",
    "dividends",
    "shares-float",
)
# The ten answers the financials read draws (the Financials tab's design, 8.3).
FINANCIAL_ANSWERS: dict[str, Any] = {
    "income-annual": pages.INCOME_ANNUAL,
    "income-quarter": pages.INCOME_QUARTER,
    "balance-annual": pages.BALANCE_ANNUAL,
    "balance-quarter": pages.BALANCE_QUARTER,
    "cashflow-annual": pages.CASHFLOW_ANNUAL,
    "cashflow-quarter": pages.CASHFLOW_QUARTER,
    "ratios-annual": pages.RATIOS_ANNUAL,
    "key-metrics-annual": pages.KEY_METRICS_ANNUAL,
    "segments-product": pages.SEGMENTS_PRODUCT,
    "segments-geographic": pages.SEGMENTS_GEOGRAPHIC,
}
# Every answer the three reads draw, but the quote, which a test stores with its observations.
ANSWERS: dict[str, Any] = {
    "profile": pages.PROFILE,
    "price-history": pages.HISTORY,
    "earnings": pages.EARNINGS,
    "estimates-annual": pages.ESTIMATES,
    "ratios-ttm": pages.RATIOS,
    "key-metrics-ttm": pages.KEY_METRICS,
    "financial-growth": pages.GROWTH,
    "financial-scores": pages.SCORES,
    "price-change": pages.PRICE_CHANGE,
    "price-target": pages.TARGET,
    "grades": pages.GRADES,
    "dividends": pages.DIVIDENDS,
    "shares-float": pages.FLOAT,
    "news": pages.NEWS,
    **FINANCIAL_ANSWERS,
}
EMPTY = {"columns": [], "rows": []}  # a table whose answer the store lacks
# LFOX's fiscal years on file, so the consensus starts after fiscal 2025.
INCOME = [
    {"symbol": SYMBOL, "date": f"{year}-12-31", "fiscalYear": str(year), "period": "FY"}
    | {"reportedCurrency": "SEK", "revenue": revenue}
    for year, revenue in ((2025, 3.27e12), (2024, 2.44e12))
]


def _params(endpoint: str, symbol: str) -> dict[str, str]:
    """The params the fetch stores ``endpoint``'s answer under (``fetch._calls``)."""
    if endpoint in PAGE_ENDPOINTS:
        return page_params(endpoint, symbol)
    years = {"period": "annual", "limit": str(STATEMENT_YEARS)}
    quarters = {"period": "quarter", "limit": str(STATEMENT_QUARTERS)}
    extra = {
        "profile": {},
        "price-history": {},
        "earnings": {"limit": str(EARNINGS_ROWS)},
        "estimates-annual": {"period": "annual", "limit": str(ANNUAL_ESTIMATE_LIMIT)},
        **{f"{kind}-annual": years for kind in ("income", "balance", "cashflow")},
        **{f"{kind}-quarter": quarters for kind in ("income", "balance", "cashflow")},
    }[endpoint]
    return {"symbol": symbol, **extra}


def _store(
    db_path: Path,
    endpoint: str,
    payload: Any,
    at: datetime,
    symbol: str = SYMBOL,
    *,
    status: int = 200,
    error: str | None = None,
) -> None:
    """``payload`` stored as the fetch stores ``symbol``'s answer to ``endpoint``, observed
    ``at``."""
    with closing(connect(db_path)) as conn:
        params = _params(endpoint, symbol)
        text = None if payload is None else json.dumps(payload)
        record_response(conn, "fmp", endpoint, params, symbol, status, text, error, at)


def _quote(db_path: Path, payload: Any, at: datetime, symbols: Sequence[str]) -> None:
    """A quote of ``symbols`` stored with each one's observations: one symbol's as the fetch
    stores it, several as a price refresh stores a batch, under no symbol."""
    if len(symbols) == 1:
        endpoint, params, symbol = "quote", {"symbol": symbols[0]}, symbols[0]
    else:
        endpoint, params, symbol = "batch-quote", {"symbols": ",".join(symbols)}, None
    with closing(connect(db_path)) as conn:
        found = record_response(
            conn, "fmp", endpoint, params, symbol, 200, json.dumps(payload), None, at
        )
        rows = [row for s in symbols for row in quote_observations(payload, s, found, at, at)]
        insert_observations(conn, rows)


def _store_all(db_path: Path, policy: Policy) -> None:
    """Every answer of LFOX at ``AT``, its quote, its two fiscal years, and a snapshot in SEK, its
    reporting currency (FXCO's result, spec 2026-11-10 11.2)."""
    for endpoint, payload in ANSWERS.items():
        _store(db_path, endpoint, payload, AT)
    _quote(db_path, pages.QUOTE, AT, [SYMBOL])
    in_sek = value_company(replace(fx_inputs(), symbol=SYMBOL), universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        store_payloads(conn, SYMBOL, {"income-annual": INCOME}, AT)
        insert_snapshot(conn, in_sek, 1)


def _get(client: TestClient, path: str) -> Any:
    r = client.get(path)
    assert r.status_code == 200, r.text
    return r.json()


def _tables(financials: Mapping[str, Any]) -> list[Any]:
    """The financials answer's nine tables: each statement's by fiscal year and by quarter, the
    revenue by product and by region, and the ratios."""
    statements = financials["statements"]
    return [
        *(
            statements[kind][period]
            for kind in ("income", "balance", "cashflow")
            for period in ("annual", "quarter")
        ),
        financials["segments"]["product"],
        financials["segments"]["region"],
        financials["ratios"],
    ]


def test_the_overview_whole(client: TestClient, db_path: Path, policy: Policy) -> None:
    _store_all(db_path, policy)
    today = NOW.date()
    quote = pages.QUOTE[0]
    statistics = {endpoint: ANSWERS[endpoint] for endpoint in STATISTICS}
    body = _get(client, OVERVIEW)
    assert body == {
        "symbol": SYMBOL,
        "dataDate": "2026-11-01",
        "quote": page_fmp.head_quote(quote),
        "company": page_fmp.company(pages.PROFILE),
        "statistics": page_fmp.statistics(statistics, pages.PROFILE, quote, "SEK", today),
        "trading": page_fmp.trading(quote, pages.PROFILE, "2027-01-14"),
        "priceChange": page_fmp.price_change(pages.PRICE_CHANGE),
        "prices": page_fmp.prices(pages.HISTORY, quote),
        "news": {
            "stories": page_fmp.stories(pages.NEWS),
            "observedAt": AT.isoformat(),
            "stale": False,
            "limit": 60,
        },
    }
    # The design's 14.2: the enterprise value in the reporting currency, the market cap in US
    # dollars; the next earnings date the earlier of two future rows, past one without an actual.
    size = body["statistics"]["size"]
    assert size["enterpriseValue"] == {"value": 12480000000000, "currency": "SEK"}
    assert size["marketCap"] == {"value": 412600000000, "currency": "USD"}
    assert body["trading"]["nextEarnings"] == "2027-01-14"
    # The head's figures, which each of the page's reads carries (the design's 7.2).
    assert body["quote"] == {
        "price": 182.4,
        "change": 2.15,
        "changePercent": 1.1928,
        "day": "2026-11-16",
    }
    # The quote's day (16 Nov) is later than the history's newest (13 Nov): it closes the prices.
    assert body["prices"][-2:] == [
        ["2026-11-13", 180.25, 7650200],
        ["2026-11-16", 182.4, 8123400],
    ]


def test_the_estimates_whole(client: TestClient, db_path: Path, policy: Policy) -> None:
    _store_all(db_path, policy)
    body = _get(client, ESTIMATES)
    assert body == {
        "symbol": SYMBOL,
        "dataDate": "2026-11-01",
        "quote": _get(client, OVERVIEW)["quote"],
        "earnings": page_fmp.earnings(pages.EARNINGS, NOW.date()),
        "consensus": page_fmp.consensus(pages.ESTIMATES, date(2025, 12, 31), "SEK"),
        "target": page_fmp.target(pages.TARGET),
        "ratings": page_fmp.ratings(pages.GRADES),
    }
    # The consensus starts after the newest fiscal year on file, in the reporting currency.
    assert [row["fiscalYear"] for row in body["consensus"]] == [2026, 2027, 2028, 2029]
    assert body["consensus"][0]["eps"] == {"value": 61.2, "currency": "SEK"}
    assert body["target"]["consensus"] == {"value": 205.6, "currency": "USD"}
    assert body["quote"]["price"] == 182.4


def test_the_financials_whole(client: TestClient, db_path: Path, policy: Policy) -> None:
    """The ten answers stored as the fetch stores them, and a snapshot in Swedish kronor: the
    tab's currency is the newest annual income row's, New Taiwan dollars, and every reader is
    handed it, so the segments' columns, whose rows name none, read it; the quarters end a quarter
    apart. The answer is the one the page's node tests draw, but its data date, the day the
    answers were stored."""
    _store_all(db_path, policy)
    body = _get(client, FINANCIALS)
    assert body == answers.FINANCIALS | {"dataDate": "2026-11-01"}
    assert (body["currency"], body["cadence"]) == ("TWD", "quarterly")
    assert body["quote"] == _get(client, OVERVIEW)["quote"]
    tables = _tables(body)
    assert [table for table in tables if not table["columns"] or not table["rows"]] == []
    assert len(tables) == 9
    income = body["statements"]["income"]
    assert [column["label"] for column in income["annual"]["columns"]] == ["2023", "2024", "2025"]
    assert [column["label"] for column in income["quarter"]["columns"]] == [
        "Q4 2025",
        "Q1 2026",
        "Q2 2026",
    ]
    region = body["segments"]["region"]
    assert {column["currency"] for column in region["columns"]} == {"TWD"}
    assert [row["key"] for row in region["rows"]] == ["Asia", "North America", "Europe"]


def test_the_financials_of_a_company_with_a_profile_and_nothing_else(
    client: TestClient, db_path: Path
) -> None:
    """Review Focus 2: no statement, no ratio and no segment on file. The read answers with every
    table empty, no data date (it does not draw the profile), the company's currency, USD with no
    snapshot, and the cadence quarterly."""
    _store(db_path, "profile", pages.PROFILE, AT)
    body = _get(client, FINANCIALS)
    assert body == answers.profile_only_financials()
    assert _tables(body) == [EMPTY] * 9
    assert (body["dataDate"], body["currency"], body["cadence"]) == (None, "USD", "quarterly")


def test_the_financials_read_an_answer_of_the_wrong_shape_as_an_empty_table(
    client: TestClient, db_path: Path
) -> None:
    """Review Focus 1: FMP's error object, which the segments pass-through stored as an answer
    before it checked one, and statements that are no list: the read answers, those tables empty,
    the currency the company's and the cadence quarterly."""
    _store(db_path, "profile", pages.PROFILE, AT)
    error = {"Error Message": "Limit Reach"}
    _store(db_path, "segments-product", error, AT)
    _store(db_path, "income-annual", error, AT)
    _store(db_path, "income-quarter", "not a list", AT)
    _store(db_path, "segments-geographic", pages.SEGMENTS_GEOGRAPHIC, AT)
    body = _get(client, FINANCIALS)
    assert body["segments"]["product"] == EMPTY
    assert body["statements"]["income"] == {"annual": EMPTY, "quarter": EMPTY}
    assert (body["currency"], body["cadence"]) == ("USD", "quarterly")
    region = page_financials.segments(pages.SEGMENTS_GEOGRAPHIC, "USD", STATEMENT_YEARS)
    assert body["segments"]["region"] == region


@pytest.mark.parametrize("older", FINANCIAL_ANSWERS)
def test_the_financials_data_date_is_the_oldest_of_its_ten_answers(
    client: TestClient, db_path: Path, older: str
) -> None:
    """The oldest day among the ten answers the tab draws (the Financials tab's design, 8.3), each
    in turn stored a day before the rest. The profile's day, the quote's and another tab's
    answer's, older still, do not count."""

    def on(day: int) -> datetime:
        return datetime(2026, 10, day, 12, 0, tzinfo=UTC)

    _store(db_path, "profile", pages.PROFILE, on(20))
    _quote(db_path, pages.QUOTE, on(21), [SYMBOL])
    _store(db_path, "ratios-ttm", pages.RATIOS, on(22))
    for endpoint, payload in FINANCIAL_ANSWERS.items():
        _store(db_path, endpoint, payload, on(29 if endpoint == older else 30))
    body = _get(client, FINANCIALS)
    assert (body["dataDate"], body["quote"]["price"]) == ("2026-10-29", 182.4)


def test_the_ratios_and_the_segments_keep_the_statements_years(
    client: TestClient, db_path: Path
) -> None:
    """The Financials tab's design, 8.1 and 8.3: of answers that hold twelve fiscal years, the
    ratios and each segment table keep the newest eleven, the statements' depth."""
    assert STATEMENT_YEARS == 11
    _store(db_path, "profile", pages.PROFILE, AT)
    years = range(2014, 2026)
    ratios = [pages.RATIOS_ANNUAL[0] | {"date": f"{y}-12-31", "fiscalYear": str(y)} for y in years]
    _store(db_path, "ratios-annual", ratios, AT)
    for endpoint in ("segments-product", "segments-geographic"):
        first = FINANCIAL_ANSWERS[endpoint][0]
        segments = [first | {"date": f"{y}-12-31", "fiscalYear": y} for y in years]
        _store(db_path, endpoint, segments, AT)
    body = _get(client, FINANCIALS)
    newest = [str(year) for year in range(2015, 2026)]
    for table in (body["ratios"], *body["segments"].values()):
        assert [column["label"] for column in table["columns"]] == newest


def test_a_half_year_reporter_s_cadence_and_labels(client: TestClient, db_path: Path) -> None:
    """The Financials tab's design, 7.9: quarterly income rows that end half a year apart, which
    FMP names Q4 and Q2, are a half-year reporter's. The three quarterly tables label them H2 and
    H1; the annual tables keep their years."""
    _store(db_path, "profile", pages.PROFILE, AT)
    _store(db_path, "income-annual", pages.INCOME_ANNUAL, AT)
    halves = ("2025-12-31", "2026-06-30")
    for kind in ("income", "balance", "cashflow"):
        rows = [row for row in FINANCIAL_ANSWERS[f"{kind}-quarter"] if row["date"] in halves]
        assert [row["period"] for row in rows] == ["Q2", "Q4"]
        _store(db_path, f"{kind}-quarter", rows, AT)
    body = _get(client, FINANCIALS)
    assert body["cadence"] == "half-yearly"
    for kind in ("income", "balance", "cashflow"):
        columns = body["statements"][kind]["quarter"]["columns"]
        assert [column["label"] for column in columns] == ["H2 2025", "H1 2026"]
    columns = body["statements"]["income"]["annual"]["columns"]
    assert [column["label"] for column in columns] == ["2023", "2024", "2025"]


def test_the_cadence_reads_each_period_end_once(client: TestClient, db_path: Path) -> None:
    """The engine takes one end a date (``inputs_statements.cadence_of``): quarterly income rows
    that end half a year apart, the newest stored twice, are a half-year reporter's, as the engine
    reads them, and not a company whose cadence the rule cannot tell. The quarterly income
    statement is the only quarterly answer stored, so the cadence is read from it."""
    _store(db_path, "profile", pages.PROFILE, AT)
    halves = ("2025-12-31", "2026-06-30")
    rows = [row for row in FINANCIAL_ANSWERS["income-quarter"] if row["date"] in halves]
    newest = max(rows, key=lambda row: row["date"])
    _store(db_path, "income-quarter", [newest, *rows], AT)
    body = _get(client, FINANCIALS)
    assert body["cadence"] == "half-yearly"


def test_the_currency_is_the_newest_annual_income_row_s(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """The Financials tab's design, 7.9 and 8.3: the tab's currency is the newest annual income
    row's, whatever the company's snapshot says (Swedish kronor here); a column whose row names
    another currency keeps its own, and the segments' columns, whose rows name none, read the
    tab's. Where the newest row names none, the tab's currency is the company's."""
    _store_all(db_path, policy)
    newest, older = pages.INCOME_ANNUAL[:2]
    income = [newest | {"reportedCurrency": "USD"}, older | {"reportedCurrency": "EUR"}]
    _store(db_path, "income-annual", income, AT + timedelta(minutes=1))
    body = _get(client, FINANCIALS)
    assert body["currency"] == "USD"
    columns = body["statements"]["income"]["annual"]["columns"]
    assert [(column["label"], column["currency"]) for column in columns] == [
        ("2024", "EUR"),
        ("2025", "USD"),
    ]
    assert {column["currency"] for column in body["segments"]["product"]["columns"]} == {"USD"}
    unnamed = [newest | {"reportedCurrency": None}, older | {"reportedCurrency": "EUR"}]
    _store(db_path, "income-annual", unnamed, AT + timedelta(minutes=2))
    body = _get(client, FINANCIALS)
    assert body["currency"] == "SEK"
    columns = body["statements"]["income"]["annual"]["columns"]
    assert [column["currency"] for column in columns] == ["EUR", "SEK"]
    assert {column["currency"] for column in body["segments"]["product"]["columns"]} == {"SEK"}


def test_an_estimate_dated_within_the_drift_of_the_newest_year_is_that_year(
    client: TestClient, db_path: Path
) -> None:
    """A 52/53-week fiscal year ends up to six days either side of its month and day: FMP may date
    the reported year's estimate a few days after the statement's period end. That row is the
    reported year, not a consensus year; the next year's, a year later, is."""
    _store(db_path, "profile", pages.PROFILE, AT)
    income = [
        {"symbol": SYMBOL, "date": day, "fiscalYear": year, "period": "FY", "revenue": 3.0e12}
        for day, year in (("2025-12-27", "2025"), ("2024-12-28", "2024"))
    ]
    reported, upcoming = (
        pages.ESTIMATES[-1] | {"date": "2025-12-31"},
        pages.ESTIMATES[-2] | {"date": "2026-12-31"},
    )
    _store(db_path, "estimates-annual", [upcoming, reported], AT)
    with closing(connect(db_path)) as conn:
        store_payloads(conn, SYMBOL, {"income-annual": income}, AT)
    consensus = _get(client, ESTIMATES)["consensus"]
    assert consensus == page_fmp.consensus([upcoming], None, "USD")
    assert [row["fiscalYear"] for row in consensus] == [2026]


@pytest.mark.parametrize(("dated", "drawn"), [("2026-01-03", False), ("2026-01-04", True)])
def test_the_consensus_cut_s_exact_boundary(
    client: TestClient, db_path: Path, dated: str, drawn: bool
) -> None:
    """The cut is the newest fiscal year's end, 27 Dec 2025, plus the drift of seven days: a row
    dated on its last day, 3 Jan 2026, is the reported year and is not drawn; one dated a day
    later is drawn."""
    assert timedelta(days=7) == YEAR_END_DRIFT
    _store(db_path, "profile", pages.PROFILE, AT)
    income = [
        {"symbol": SYMBOL, "date": day, "fiscalYear": year, "period": "FY", "revenue": 3.0e12}
        for day, year in (("2025-12-27", "2025"), ("2024-12-28", "2024"))
    ]
    row = pages.ESTIMATES[-1] | {"date": dated}
    _store(db_path, "estimates-annual", [row], AT)
    with closing(connect(db_path)) as conn:
        store_payloads(conn, SYMBOL, {"income-annual": income}, AT)
    consensus = _get(client, ESTIMATES)["consensus"]
    assert consensus == (page_fmp.consensus([row], None, "USD") if drawn else [])


def test_a_close_too_large_for_a_float_is_left_out_of_the_read(
    client: TestClient, db_path: Path
) -> None:
    """Review Focus 1: a stored close beyond a float's range, as text or as a JSON integer, is
    left out of the prices as a row with no close is, so the read answers and its JSON holds no
    infinity."""
    _store(db_path, "profile", pages.PROFILE, AT)
    huge = [
        pages.HISTORY[0] | {"close": "1e400"},
        pages.HISTORY[1] | {"close": 10**400},
        *pages.HISTORY[2:],
    ]
    _store(db_path, "price-history", huge, AT)
    prices = _get(client, OVERVIEW)["prices"]
    assert prices == page_fmp.prices(pages.HISTORY[2:], None)
    assert len(prices) == len(pages.HISTORY) - 2


def test_a_company_with_a_profile_and_nothing_else(client: TestClient, db_path: Path) -> None:
    """Review Focus 2: a company fetched before the page's calls, or whose page calls all failed,
    opens with every figure ``None``, no price and no story."""
    _store(db_path, "profile", pages.PROFILE, AT)
    overview = _get(client, OVERVIEW)
    assert overview["dataDate"] == "2026-11-01"
    assert overview["company"] == page_fmp.company(pages.PROFILE)
    assert overview["statistics"] == page_fmp.statistics({}, pages.PROFILE, None, "USD", NOW.date())
    assert overview["statistics"]["size"]["marketCap"] is None
    assert overview["trading"] == page_fmp.trading(None, pages.PROFILE, None)
    assert overview["trading"]["open"] is None
    no_quote = {"price": None, "change": None, "changePercent": None, "day": None}
    assert overview["quote"] == no_quote
    assert set(overview["priceChange"].values()) == {None}
    assert overview["prices"] == []
    assert overview["news"] == {"stories": [], "observedAt": None, "stale": True, "limit": 60}
    estimates = _get(client, ESTIMATES)
    assert estimates == {
        "symbol": SYMBOL,
        "dataDate": None,  # the estimates tab draws no profile
        "quote": no_quote,
        "earnings": {"next": None, "rows": []},
        "consensus": [],
        "target": {"consensus": None, "median": None, "low": None, "high": None},
        "ratings": page_fmp.ratings(None),
    }
    assert set(estimates["ratings"].values()) == {None}


def test_a_bad_symbol_is_a_400_and_no_profile_a_404(client: TestClient) -> None:
    for tab in ("overview", "estimates", "financials"):
        r = client.get(f"/api/companies/a b/page/{tab}")
        assert (r.status_code, r.json()) == (400, {"detail": "'a b' is not a symbol"})
        # AAPL has a snapshot and no stored profile: the page reads need the profile alone
        r = client.get(f"/api/companies/aapl/page/{tab}")
        assert (r.status_code, r.json()) == (404, {"detail": "no page data for AAPL"})
        r = client.get(f"/api/companies/ZZZZ/page/{tab}")
        assert (r.status_code, r.json()) == (404, {"detail": "no page data for ZZZZ"})


def test_the_data_date_is_the_oldest_answer_s_day(client: TestClient, db_path: Path) -> None:
    """The oldest day among the answers the tab draws, the news left out (the design's 7.4): the
    overview draws no price target and no grades, and the estimates no profile; both draw the
    quote, the head's."""

    def on(day: int) -> datetime:
        return datetime(2026, 10, day, 12, 0, tzinfo=UTC)

    for endpoint, day in (
        ("profile", 31),
        ("price-history", 30),
        ("earnings", 29),
        ("ratios-ttm", 28),
        ("estimates-annual", 30),
        ("price-target", 25),
        ("news", 20),
    ):
        _store(db_path, endpoint, ANSWERS[endpoint], on(day))
    _quote(db_path, pages.QUOTE, on(31), [SYMBOL])
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-28"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-25"
    _store(db_path, "dividends", pages.DIVIDENDS, on(27))  # a drawn answer, older again
    _store(db_path, "grades", pages.GRADES, on(24))
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-27"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-24"
    # The quote read is the one the newest observation cites, the last stored, whatever its day.
    _quote(db_path, pages.QUOTE, on(26), [SYMBOL])
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-26"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-24"
    _quote(db_path, pages.QUOTE, on(22), [SYMBOL])
    assert _get(client, OVERVIEW)["dataDate"] == "2026-10-22"
    assert _get(client, ESTIMATES)["dataDate"] == "2026-10-22"


def test_the_news_is_stale_on_the_far_side_of_the_window(
    client_with_clock: Callable[[datetime], TestClient], db_path: Path, policy: Policy
) -> None:
    """Stale when observed at or before the clock less the effective policy's reuse window."""
    _store(db_path, "profile", pages.PROFILE, AT)
    _store(db_path, "news", pages.NEWS, AT)
    window = timedelta(hours=policy.refresh.reuse_hours)

    def news(now: datetime) -> Mapping[str, Any]:
        found: Mapping[str, Any] = _get(client_with_clock(now), OVERVIEW)["news"]
        assert (found["observedAt"], found["stories"]) == (
            AT.isoformat(),
            page_fmp.stories(pages.NEWS),
        )
        return found

    assert news(AT + window - timedelta(seconds=1))["stale"] is False
    assert news(AT + window)["stale"] is True
    with closing(connect(db_path)) as conn:
        write_settings(conn, {"refresh.reuse_hours": 1}, None, NOW, policy)
    assert news(AT + timedelta(minutes=59))["stale"] is False
    assert news(AT + timedelta(hours=1))["stale"] is True


def test_the_newest_answer_wins_and_an_errored_one_is_passed_over(
    client: TestClient, db_path: Path
) -> None:
    _store(db_path, "profile", pages.PROFILE, AT)
    older = [pages.RATIOS[0] | {"grossProfitMarginTTM": 0.5}]
    newer = [pages.RATIOS[0] | {"grossProfitMarginTTM": 0.6}]
    _store(db_path, "ratios-ttm", older, datetime(2026, 10, 29, tzinfo=UTC))
    _store(db_path, "ratios-ttm", newer, datetime(2026, 10, 30, tzinfo=UTC))
    error = {"Error Message": "Limit Reach"}
    _store(db_path, "ratios-ttm", error, AT, error="unusable payload: {...}")
    _store(db_path, "ratios-ttm", None, AT, status=500, error="HTTP 500")
    body = _get(client, OVERVIEW)
    assert body["statistics"]["margins"]["gross"] == 0.6
    assert body["dataDate"] == "2026-10-30"


def test_the_quote_row_comes_through_the_observation(client: TestClient, db_path: Path) -> None:
    """The design's 10.4: the row of the response the newest ``quote`` observation cites, a
    single quote's, then a price refresh's batch, stored under no symbol. ``BRK.B``'s row is
    ``BRK-B`` in FMP's form, read by a path in either case."""
    _store(db_path, "profile", pages.PROFILE, AT)
    _store(db_path, "price-history", pages.HISTORY, AT)
    _quote(db_path, pages.QUOTE, AT, [SYMBOL])
    head = _get(client, OVERVIEW)["quote"]
    assert (head["price"], head["change"], head["day"]) == (182.4, 2.15, "2026-11-16")
    # A later batch, its row on the history's newest day: no day is added to the prices.
    on_the_13th = 1794600000  # 13 Nov 2026, 20:00 UTC
    row = pages.QUOTE[0] | {"price": 185.0, "change": 4.75, "timestamp": on_the_13th}
    batch = [pages.BATCH_QUOTE[0], row]
    later = AT + timedelta(minutes=30)
    _quote(db_path, batch, later, ["BRK.B", SYMBOL])
    body = _get(client, OVERVIEW)
    assert body["quote"] == page_fmp.head_quote(row)
    assert (body["quote"]["price"], body["quote"]["day"]) == (185.0, "2026-11-13")
    assert body["trading"] == page_fmp.trading(row, pages.PROFILE, None)
    assert body["prices"] == page_fmp.prices(pages.HISTORY, row)
    assert body["prices"][-1] == ["2026-11-13", 180.25, 7650200]
    assert body["statistics"]["size"]["marketCap"] == {"value": 412600000000, "currency": "USD"}
    # The estimates read carries the same row's head figures, and the date of its response.
    estimates = _get(client, ESTIMATES)
    assert (estimates["quote"], estimates["dataDate"]) == (body["quote"], "2026-11-01")
    _store(db_path, "profile", pages.PROFILE, AT, symbol="BRK.B")
    brk = _get(client, "/api/companies/brk.b/page/overview")
    assert (brk["symbol"], brk["quote"]["price"]) == ("BRK.B", 512.3)
    assert _get(client, "/api/companies/brk.b/page/estimates")["quote"] == brk["quote"]


def test_the_reads_call_no_vendor(
    tmp_path: Path, db_path: Path, policy: Policy, vendor: Vendor, passthrough: Passthrough
) -> None:
    """An app with a pass-through whose every call fails: the three reads answer from the store,
    the stale news and statements three days old among them, and the vendor is never asked."""
    vendor.answer = lambda request: httpx.Response(500)
    _store(db_path, "profile", pages.PROFILE, AT)
    _store(db_path, "news", pages.NEWS, AT - timedelta(days=3))
    _store(db_path, "income-annual", pages.INCOME_ANNUAL, AT - timedelta(days=3))
    _store(db_path, "segments-product", pages.SEGMENTS_PRODUCT, AT - timedelta(days=3))
    with passthrough_client(tmp_path, db_path, policy, passthrough) as client:
        news = _get(client, OVERVIEW)["news"]
        _get(client, ESTIMATES)
        financials = _get(client, FINANCIALS)
    assert (news["stale"], len(news["stories"])) == (True, 3)
    assert len(financials["statements"]["income"]["annual"]["columns"]) == 3
    assert len(financials["segments"]["product"]["rows"]) == 3
    assert financials["dataDate"] == "2026-10-29"
    assert vendor.paths == []


def test_the_reads_find_what_the_fetch_stores(
    db_path: Path, client: TestClient, policy: Policy
) -> None:
    """The refresh's fetch of ACME over the fixtures, then the three reads: each answer they draw
    is found under the params the fetch stored it with, so a figure of each is there, and no table
    of the financials is empty."""
    router = Router()
    with (
        VendorHttp(
            fmp_api.BASE_URL,
            [FMP_KEY],
            policy.refresh,
            transport=router.transport,
            sleep=lambda _: None,
            clock=lambda: NOW,
        ) as http,
        closing(connect(db_path)) as conn,
    ):
        outcome = fetch_company(conn, Fmp(http, FMP_KEY), "ACME", policy, NOW, [FMP_KEY])
    assert outcome.failed == ()
    overview = _get(client, "/api/companies/ACME/page/overview")
    estimates = _get(client, "/api/companies/ACME/page/estimates")
    statistics = overview["statistics"]
    one_of_each = {
        "profile": overview["company"]["sector"],
        "quote": overview["quote"]["price"],
        "price-history": overview["prices"][0],
        "earnings": overview["trading"]["nextEarnings"],
        "ratios-ttm": statistics["margins"]["gross"],
        "key-metrics-ttm": statistics["returns"]["roe"],
        "financial-growth": statistics["growth"]["revenue"],
        "financial-scores": statistics["health"]["altmanZ"],
        "price-change": overview["priceChange"]["d1"],
        "dividends": statistics["dividends"]["frequency"],
        "shares-float": statistics["size"]["freeFloat"],
        "news": overview["news"]["observedAt"],
        "estimates-annual": estimates["consensus"][0],
        "price-target": estimates["target"]["consensus"],
        "grades": estimates["ratings"]["consensus"],
    }
    assert {name for name, figure in one_of_each.items() if figure is None} == set()
    assert (overview["dataDate"], estimates["dataDate"]) == ("2026-11-01", "2026-11-01")
    assert estimates["quote"] == overview["quote"]
    assert overview["news"]["stale"] is False
    financials = _get(client, "/api/companies/ACME/page/financials")
    tables = _tables(financials)
    assert [table for table in tables if not table["columns"] or not table["rows"]] == []
    assert len(tables) == 9
    assert (financials["dataDate"], financials["currency"], financials["cadence"]) == (
        "2026-11-01",
        "USD",
        "quarterly",
    )
    assert financials["quote"] == overview["quote"]


def test_the_detail_carries_the_moat_in_force_and_the_note_count(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The design's 7.2, as spec 2026-11-19 8.6 has it: the class of the company's row of the moat
    table, a refused row's too, whatever a counted review holds; and 11.1: the count of the
    company's notes."""
    aapl = _get(client, "/api/companies/AAPL")
    assert (aapl["moat"], aapl["noteCount"]) == ("Wide", 0)
    # refused for its target margin, AAL has its row's class all the same
    assert results["AAL"].value is None
    assert _get(client, "/api/companies/AAL")["moat"] == "None"
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "AAPL")
        assert snapshot is not None
        found = insert_override(
            conn,
            "AAPL",
            "moat.class",
            "Wide",
            "Narrow",
            "class",
            "pricing power is fading",
            [{"kind": "filing", "ref": "10-K 2025", "note": None}],
            "lasting",
            None,
            None,
            snapshot.id,
            AGENT,
            NOW,
            "applied",
            "",
        )
        narrow = Override(found, "moat.class", "Narrow", "agent", AGENT.actor, NOW, "fading")
        inputs = replace(mature_growth_inputs(), symbol="AAPL")
        reviewed = review_company(
            inputs, universe_deciles(), policy, TODAY, [narrow], results["AAPL"]
        )
        assert reviewed.result.value is not None
        assert reviewed.result.intermediates["moat"] == "Narrow"
        insert_review(conn, reviewed, "AAPL", snapshot.id, None, clock=lambda: NOW)
        # a counted review's moat is not the row's: the row's stands
        detail = _get(client, "/api/companies/AAPL")
        assert (detail["review"]["value"], detail["moat"]) == (reviewed.result.value, "Wide")
        evidence = [{"kind": "filing", "ref": "10-K 2025", "note": None}]
        set_moat(conn, "AAPL", "Narrow", AGENT, "pricing power is fading", evidence, NOW)
    for text in ("margins look peaked", "the services segment carries the company"):
        r = client.post("/api/companies/AAPL/notes", json={"text": text}, headers=HEADER)
        assert r.status_code == 201, r.text
    aapl = _get(client, "/api/companies/AAPL")
    assert (aapl["moat"], aapl["noteCount"]) == ("Narrow", 2)


def test_a_refused_row_with_a_counted_valued_review_has_its_row_s_moat(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """AAL's snapshot is refused for its target margin; an applied margin.target override gives a
    counted review that values it on the class None, and the detail's moat is the row's, Narrow
    once an agent sets it, not the review's."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "AAL")
        assert snapshot is not None and snapshot.value is None
        found = insert_override(
            conn,
            "AAL",
            "margin.target",
            None,
            0.2,
            "ratio",
            "the peers by hand",
            [{"kind": "filing", "ref": "10-K 2025", "note": None}],
            "lasting",
            None,
            None,
            snapshot.id,
            AGENT,
            NOW,
            "applied",
            "",
        )
        target = Override(found, "margin.target", 0.2, "agent", AGENT.actor, NOW, "peers")
        inputs = replace(young_growth_inputs(), symbol="AAL", peers=())
        reviewed = review_company(
            inputs, universe_deciles(), policy, TODAY, [target], results["AAL"]
        )
        insert_review(conn, reviewed, "AAL", snapshot.id, None, clock=lambda: NOW)
        evidence = [{"kind": "filing", "ref": "10-K 2025", "note": None}]
        set_moat(conn, "AAL", "Narrow", AGENT, "a regional network", evidence, NOW)
    assert reviewed.result.value is not None
    assert reviewed.result.intermediates["moat"] == "None"
    detail = _get(client, "/api/companies/AAL")
    assert detail["review"]["value"] == reviewed.result.value
    assert detail["moat"] == "Narrow"
