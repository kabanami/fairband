"""The company page's four reads for one made-up company, ``page_payloads``' Lanternfield Optics
(``LFOX``), which lists in US dollars and reports in New Taiwan dollars: the overview answer, the
estimates answer, the financials answer and the company's detail, as the page's node tests hand
them to its scripts.

The three answers are the readers' (``vendors.page_fmp`` and ``vendors.page_financials``) on
``page_payloads``' answers, put together as ``web/company_api.py`` puts them, so their shapes are
the server's. Only the data date, the news' time and the financials' currency and cadence are set
by hand: the server takes the first two from when its answers were stored, and finds the others
on the stored statements (the newest annual income row names New Taiwan dollars, and the quarters
end a quarter apart). The detail is written by hand in the shape of ``GET
/api/companies/{symbol}`` (``web/app.py``, ``company``): LFOX valued on the Mature Growth route at
$196.50 against a price of $182.40, a wide moat, two notes, no review, no report and no open item.

The builders give the variants: a refused row, a reviewed row with a published report, the three
answers of a company with nothing stored but its profile, and the overview of one with nothing
stored at all. Each returns a new copy."""

import copy
from datetime import date
from typing import Any

from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.refresh.fetch import NEWS_STORIES, STATEMENT_YEARS
from fairband.refresh.inputs_statements import YEAR_END_DRIFT
from fairband.vendors import page_financials, page_fmp
from fairband.vendors.fmp import StatementKind
from support import page_payloads as pages

SYMBOL = pages.SYMBOL
TODAY = date(2026, 11, 16)  # the clock's day: the earnings of 14 Jan 2027 are the next
DATA_DATE = "2026-11-14"  # the oldest stored answer each read draws
REPORTING = "TWD"
NEWEST_YEAR = date(2025, 12, 31)  # the newest fiscal year on file: the consensus starts after it
REFUSAL = "fewer than three fiscal years of statements on file"

_ROW = page_fmp.quote_row(pages.QUOTE, SYMBOL)
_NEXT = page_fmp.next_earnings(pages.EARNINGS, TODAY)
_STATISTICS: dict[str, Any] = {
    "ratios-ttm": pages.RATIOS,
    "key-metrics-ttm": pages.KEY_METRICS,
    "financial-growth": pages.GROWTH,
    "financial-scores": pages.SCORES,
    "dividends": pages.DIVIDENDS,
    "shares-float": pages.FLOAT,
}

OVERVIEW: dict[str, Any] = {
    "symbol": SYMBOL,
    "dataDate": DATA_DATE,
    "quote": page_fmp.head_quote(_ROW),
    "company": page_fmp.company(pages.PROFILE),
    "statistics": page_fmp.statistics(_STATISTICS, pages.PROFILE, _ROW, REPORTING, TODAY),
    "trading": page_fmp.trading(_ROW, pages.PROFILE, None if _NEXT is None else _NEXT["day"]),
    "priceChange": page_fmp.price_change(pages.PRICE_CHANGE),
    "prices": page_fmp.prices(pages.HISTORY, _ROW),
    "news": {
        "stories": page_fmp.stories(pages.NEWS),
        "observedAt": "2026-11-16T06:00:00+00:00",
        "stale": False,
        "limit": NEWS_STORIES,
    },
}

ESTIMATES: dict[str, Any] = {
    "symbol": SYMBOL,
    "dataDate": DATA_DATE,
    "quote": page_fmp.head_quote(_ROW),
    "earnings": page_fmp.earnings(pages.EARNINGS, TODAY),
    "consensus": page_fmp.consensus(pages.ESTIMATES, NEWEST_YEAR + YEAR_END_DRIFT, REPORTING),
    "target": page_fmp.target(pages.TARGET),
    "ratings": page_fmp.ratings(pages.GRADES),
}

# Each statement's answers by fiscal year and by quarter.
_STATEMENTS: dict[StatementKind, tuple[Any, Any]] = {
    "income": (pages.INCOME_ANNUAL, pages.INCOME_QUARTER),
    "balance": (pages.BALANCE_ANNUAL, pages.BALANCE_QUARTER),
    "cashflow": (pages.CASHFLOW_ANNUAL, pages.CASHFLOW_QUARTER),
}

FINANCIALS: dict[str, Any] = {
    "symbol": SYMBOL,
    "dataDate": DATA_DATE,
    "quote": page_fmp.head_quote(_ROW),
    "currency": REPORTING,
    "cadence": "quarterly",
    "statements": {
        kind: {
            "annual": page_financials.statement(annual, kind, REPORTING),
            "quarter": page_financials.statement(quarter, kind, REPORTING, quarterly=True),
        }
        for kind, (annual, quarter) in _STATEMENTS.items()
    },
    "segments": {
        "product": page_financials.segments(pages.SEGMENTS_PRODUCT, REPORTING, STATEMENT_YEARS),
        "region": page_financials.segments(pages.SEGMENTS_GEOGRAPHIC, REPORTING, STATEMENT_YEARS),
    },
    "ratios": page_financials.ratios(
        pages.RATIOS_ANNUAL, pages.KEY_METRICS_ANNUAL, REPORTING, STATEMENT_YEARS
    ),
}

DETAIL: dict[str, Any] = {
    "company": {
        "symbol": SYMBOL,
        "refreshId": 3,
        "name": "Lanternfield Optics Ltd",
        "exchange": "NYSE",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "TW",
        "currency": "USD",
        "isAdr": True,
        "capBand": "mega",
        "marketCap": 412600000000.0,
        "eligible": True,
        "exclusionReason": None,
        "observedAt": "2026-11-14T05:40:00+00:00",
    },
    "brief": pages.PROFILE[0]["description"],
    "logo": f"/api/companies/{SYMBOL}/logo",
    "currency": REPORTING,
    "isAdr": True,
    "adrRatio": 5.0,
    "fxRate": 32.4,
    "fxDate": "2026-11-13",
    "snapshot": {
        "id": 41,
        "refreshId": 3,
        "decilesRefreshId": 3,
        "createdAt": "2026-11-14T06:20:00+00:00",
    },
    "result": {
        "symbol": SYMBOL,
        "route": "mature-growth",
        "value": 196.5,
        "levels": {"buy": 147.38, "fair_low": 176.85, "fair_high": 216.15, "trim": 294.75},
        "price_to_value": 0.93,
        "designation": "near",
        "price": 182.4,  # the quote's price, so the head draws the quote's change
        "price_date": "2026-11-16",
        "data_date": DATA_DATE,
        "valid_until": "2027-02-12",
        "phase": {
            "phase": "Mature Growth",
            "reason": None,
            "years_used": 10,
            "positive_years_last_five": 5,
            "positive_years_on_file": 10,
            "growth_3y": 0.25,
            "growth_word": "fast",
            "growth_decile": 9,
            "revenue_slope": 0.21,
            "margin": 0.4877,
            "margin_slope": 0.012,
            "margin_direction": "rising",
            "fcf_sign": "positive",
            "dickinson": "mature",
            "checks": [],
        },
        "inputs": [],
        "intermediates": {
            "currency": REPORTING,
            "fx_rate": 32.4,
            "fx_date": "2026-11-13",
            "moat": "Wide",
        },
        "flags": [],
        "refusal": None,
        "policy_version": "16",
        "method_version": "fairband-mechanical/1.5",
        "settings_hash": EMPTY_SETTINGS_HASH,
        "deciles_refresh_id": 3,
    },
    "today": TODAY.isoformat(),
    "designationEdges": [0.75, 0.9, 1.1, 1.5],
    "agingFraction": 0.6667,
    "review": None,
    "priceNeeds": None,
    "moat": "Wide",
    "secondary": None,
    "report": None,
    "item": None,
    "noteCount": 2,
    "launchReady": False,
}

# A review that counts on the latest snapshot: its moat override narrows the moat and lowers the
# value, so the moat in force is the review's.
REVIEW: dict[str, Any] = {
    "id": 7,
    "value": 182.0,
    "levels": {"buy": 145.6, "fairLow": 163.8, "fairHigh": 200.2, "trim": 273.0},
    "priceToValue": 1.0,
    "designation": "near",
    "refusal": None,
    "bridge": [
        {
            "overrideId": 12,
            "tag": "moat.class",
            "label": "Moat",
            "old": "Wide",
            "new": "Narrow",
            "unit": None,
            "delta": -14.5,
            "refusal": None,
            "reason": "Two new rivals sell lenses of the same grade at lower prices.",
            "principal": "agent",
            "actor": "claude-opus-5-5",
        }
    ],
    "overrideCount": 1,
    "mechanical": 196.5,
    "flags": [],
}

# The company's latest published report, within its window.
REPORT: dict[str, Any] = {
    "id": 31,
    "mode": "full report",
    "stance": "hold",
    "revision": 1,
    "createdAt": "2026-11-11T14:05:00+00:00",
    "principal": "agent",
    "actor": "claude-opus-5-5",
    "expired": False,
    "summary": {"heading": "Summary", "parts": ["The price sits inside the fair band."]},
    "references": [],
}


def detail(**changes: Any) -> dict[str, Any]:
    """A copy of ``DETAIL`` with its top-level fields in ``changes`` replaced."""
    return copy.deepcopy(DETAIL) | copy.deepcopy(changes)


def refused_detail() -> dict[str, Any]:
    """LFOX refused: no route, value, levels or designation, the refusal's sentence, no moat."""
    found = detail(moat=None)
    found["result"] |= {
        "route": None,
        "value": None,
        "levels": None,
        "price_to_value": None,
        "designation": None,
        "refusal": REFUSAL,
    }
    del found["result"]["intermediates"]["moat"]
    return found


def reviewed_detail() -> dict[str, Any]:
    """LFOX with ``REVIEW`` counting, its moat in force, and ``REPORT`` published."""
    return detail(review=REVIEW, moat="Narrow", report=REPORT)


def profile_only_overview() -> dict[str, Any]:
    """The overview answer of a company with nothing stored but its profile: every figure
    ``None``, no prices and no stories, its data date the profile's day."""
    return {
        "symbol": SYMBOL,
        "dataDate": DATA_DATE,
        "quote": page_fmp.head_quote(None),
        "company": page_fmp.company(pages.PROFILE),
        "statistics": page_fmp.statistics({}, pages.PROFILE, None, "USD", TODAY),
        "trading": page_fmp.trading(None, pages.PROFILE, None),
        "priceChange": page_fmp.price_change(None),
        "prices": page_fmp.prices(None, None),
        "news": {"stories": [], "observedAt": None, "stale": True, "limit": NEWS_STORIES},
    }


def empty_overview() -> dict[str, Any]:
    """The overview answer of a company with nothing stored, not even its profile: every figure
    and every fact ``None``, no prices and no stories."""
    return profile_only_overview() | {
        "company": page_fmp.company(None),
        "statistics": page_fmp.statistics({}, None, None, "USD", TODAY),
        "trading": page_fmp.trading(None, None, None),
    }


def profile_only_estimates() -> dict[str, Any]:
    """The estimates answer of a company with nothing stored but its profile, which that read
    does not draw: every figure ``None``, no rows and no data date."""
    return {
        "symbol": SYMBOL,
        "dataDate": None,
        "quote": page_fmp.head_quote(None),
        "earnings": page_fmp.earnings(None, TODAY),
        "consensus": page_fmp.consensus(None, None, "USD"),
        "target": page_fmp.target(None),
        "ratings": page_fmp.ratings(None),
    }


def profile_only_financials() -> dict[str, Any]:
    """The financials answer of a company with nothing stored but its profile, which that read
    does not draw: every table with no column and no row, no data date, the currency the
    company's (USD, since it has no snapshot) and the cadence quarterly."""
    return {
        "symbol": SYMBOL,
        "dataDate": None,
        "quote": page_fmp.head_quote(None),
        "currency": "USD",
        "cadence": "quarterly",
        "statements": {
            kind: {
                "annual": page_financials.statement(None, kind, "USD"),
                "quarter": page_financials.statement(None, kind, "USD", quarterly=True),
            }
            for kind in _STATEMENTS
        },
        "segments": {
            "product": page_financials.segments(None, "USD", STATEMENT_YEARS),
            "region": page_financials.segments(None, "USD", STATEMENT_YEARS),
        },
        "ratios": page_financials.ratios(None, None, "USD", STATEMENT_YEARS),
    }
