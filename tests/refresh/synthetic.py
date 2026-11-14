"""A synthetic company for the refresh tests: ACME's FMP payloads and its universe row.

The router serves these payloads in place of the fixtures (``Router.bodies``). The company is
twelve calendar fiscal years, 2014 to 2025, and five quarters to 2026-09-30, or, reporting
half-yearly, four half-years to 2026-06-30; money is in USD, or in the currency ``bodies`` is given
(the statements' ``reportedCurrency``). The consensus, quote, profile, closes and GuruFocus answers
stay the ACME fixtures'.
"""

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from fairband.engine.anchor import Cadence
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.refreshes import create_refresh, finish_refresh

M = 1_000_000
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)  # the refresh fixtures' clock
YEARS = tuple(range(2014, 2026))  # one fiscal year more than assembly keeps
QUARTERS = (
    date(2025, 9, 30),
    date(2025, 12, 31),
    date(2026, 3, 31),
    date(2026, 6, 30),
    date(2026, 9, 30),
)
# A half-yearly reporter's statement periods (spec 2026-11-10 11.4): 181, 184 and 181 days apart.
HALF_YEARS = (date(2024, 12, 31), date(2025, 6, 30), date(2025, 12, 31), date(2026, 6, 30))
# The statement lines the normalizer kept from 2026-11-03: a test drops their facts to stand for a
# store from before.
SIX_LINES = (
    "grossProfit",
    "interestExpense",
    "totalAssets",
    "totalLiabilities",
    "retainedEarnings",
    "depreciationAndAmortization",
)


type Payload = list[dict[str, Any]]


def statement(day: date, fiscal_year: int, period: str, **fields: Any) -> dict[str, Any]:
    return {
        "date": day.isoformat(),
        "symbol": "ACME",
        "reportedCurrency": "USD",
        "fiscalYear": str(fiscal_year),
        "period": period,
        **fields,
    }


def income_annual(years: Iterable[int]) -> Payload:
    """Revenue $1,000 m in 2014, up $100 m a year; the gross margin 40%, the operating margin
    20%; an interest expense of $10 m a year."""
    return [
        statement(
            date(y, 12, 31),
            y,
            "FY",
            revenue=(1000 + 100 * k) * M,
            grossProfit=(400 + 40 * k) * M,
            operatingIncome=(200 + 20 * k) * M,
            interestExpense=10 * M,
            netIncome=(150 + 15 * k) * M,
            epsDiluted=1.5 + 0.15 * k,
            weightedAverageShsOutDil=100 * M,
        )
        for y in years
        if (k := y - 2014) >= 0
    ]


def cashflow_annual(years: Iterable[int]) -> Payload:
    return [
        statement(
            date(y, 12, 31),
            y,
            "FY",
            netCashProvidedByOperatingActivities=(250 + 25 * k) * M,
            netCashProvidedByInvestingActivities=-(100 + 10 * k) * M,
            netCashProvidedByFinancingActivities=-(120 + 12 * k) * M,
            capitalExpenditure=-(60 + 6 * k) * M,
            depreciationAndAmortization=(50 + 5 * k) * M,
            stockBasedCompensation=20 * M,
            netDividendsPaid=-40 * M,
            commonStockRepurchased=-60 * M,
            commonStockIssuance=5 * M,
        )
        for y in years
        if (k := y - 2014) >= 0
    ]


def balance_annual(years: Iterable[int]) -> Payload:
    """No short-term investments in 2017; a vendor-zero goodwill in 2018. Total assets $1,500 m in
    2014, up $10 m a year with the current assets, retained earnings and equity; the total
    liabilities $800 m."""
    return [
        statement(
            date(y, 12, 31),
            y,
            "FY",
            cashAndCashEquivalents=200 * M,
            shortTermInvestments=None if y == 2017 else 50 * M,
            totalCurrentAssets=(600 + 10 * k) * M,
            totalCurrentLiabilities=300 * M,
            shortTermDebt=20 * M,
            longTermDebt=300 * M,
            propertyPlantEquipmentNet=400 * M,
            goodwill=0 if y == 2018 else 250 * M,
            intangibleAssets=260 * M,
            totalAssets=(1500 + 10 * k) * M,
            totalLiabilities=800 * M,
            retainedEarnings=(400 + 10 * k) * M,
            totalStockholdersEquity=(700 + 10 * k) * M,
        )
        for y in years
        if (k := y - 2014) >= 0
    ]


def balance_as_reported(years: Iterable[int]) -> Payload:
    """The issuer's intangibles total ($240 m) every year but 2016; leases from 2019."""
    rows = []
    for y in years:
        tags: dict[str, int] = {}
        if y != 2016:
            tags["intangibleassetsnetexcludinggoodwill"] = 240 * M
        if y >= 2019:
            tags |= {
                "operatingleaserightofuseasset": 90 * M,
                "operatingleaseliabilitycurrent": 15 * M,
            }
        rows.append(
            {"symbol": "ACME", "fiscalYear": y, "date": f"{y}-12-31", "period": "FY", "data": tags}
        )
    return rows


def income_quarter(ends: Iterable[date], periods: Sequence[date] = QUARTERS) -> Payload:
    """Period i of ``periods`` (``QUARTERS``, or ``HALF_YEARS``), for each of ``ends``: revenue
    $300 m + $10 m × i; diluted shares 100 m + 1 m × i; an interest expense of $4 m, signed
    negative (FMP signs it either way); a pre-tax income of $56 m + $2 m × i, the operating income
    less the interest, and an income tax of $11 m + $1 m × i, the pre-tax income less the net
    income."""
    return [
        statement(
            end,
            end.year,
            f"Q{(end.month + 2) // 3}",
            revenue=(300 + 10 * i) * M,
            grossProfit=(120 + 4 * i) * M,
            operatingIncome=(60 + 2 * i) * M,
            interestExpense=-4 * M,
            incomeBeforeTax=(56 + 2 * i) * M,
            incomeTaxExpense=(11 + i) * M,
            netIncome=(45 + i) * M,
            epsDiluted=0.45 + 0.01 * i,
            weightedAverageShsOutDil=(100 + i) * M,
        )
        for i, end in enumerate(periods)
        if end in ends
    ]


def cashflow_quarter(ends: Iterable[date], periods: Sequence[date] = QUARTERS) -> Payload:
    """The third period has no stock compensation; depreciation and amortization $15 m + $1 m × i
    in period i of ``periods``."""
    return [
        statement(
            end,
            end.year,
            f"Q{(end.month + 2) // 3}",
            netCashProvidedByOperatingActivities=(70 + i) * M,
            capitalExpenditure=-(20 + i) * M,
            depreciationAndAmortization=(15 + i) * M,
            stockBasedCompensation=None if i == 2 else 5 * M,
            netDividendsPaid=-10 * M,
            commonStockRepurchased=-15 * M,
            commonStockIssuance=1 * M,
        )
        for i, end in enumerate(periods)
        if end in ends
    ]


def balance_quarter(quarters: Iterable[date]) -> Payload:
    """A balance sheet for each of ``quarters`` (spec 2026-11-13 12.1), labelled as the quarterly
    income statement's periods are. A quarter that ends a fiscal year, 31 December, carries that
    year's annual figures (``balance_annual``), as FMP's does. The n-th quarter of a year, n 1 to
    3, carries figures of its own: cash $200 m + $10 m × n, short-term investments $50 m − $5 m ×
    n, short-term debt $20 m + $5 m × n and long-term debt $300 m − $10 m × n; on the year before's
    annual figures, the current assets up $3 m × n, the current liabilities and PP&E up $5 m × n,
    the intangibles down $5 m × n, the total liabilities up $10 m × n, and the total assets up
    $12 m × n, so the retained earnings and the equity rise $2 m × n."""
    rows = []
    for end in quarters:
        label = f"Q{(end.month + 2) // 3}"
        if end.month == 12:
            [year] = balance_annual([end.year])
            rows.append({**year, "period": label})
            continue
        n, k = end.month // 3, end.year - 1 - 2014
        rows.append(
            statement(
                end,
                end.year,
                label,
                cashAndCashEquivalents=(200 + 10 * n) * M,
                shortTermInvestments=(50 - 5 * n) * M,
                totalCurrentAssets=(600 + 10 * k + 3 * n) * M,
                totalCurrentLiabilities=(300 + 5 * n) * M,
                shortTermDebt=(20 + 5 * n) * M,
                longTermDebt=(300 - 10 * n) * M,
                propertyPlantEquipmentNet=(400 + 5 * n) * M,
                goodwill=250 * M,
                intangibleAssets=(260 - 5 * n) * M,
                totalAssets=(1500 + 10 * k + 12 * n) * M,
                totalLiabilities=(800 + 10 * n) * M,
                retainedEarnings=(400 + 10 * k + 2 * n) * M,
                totalStockholdersEquity=(700 + 10 * k + 2 * n) * M,
            )
        )
    return rows


def earnings(periods: Sequence[date] = QUARTERS) -> Payload:
    """A street actual of 0.50 + 0.01 × i for period i of ``periods``, reported 30 days after its
    end; the next report on 2027-02-04."""
    rows: Payload = [
        {"symbol": "ACME", "date": "2027-02-04", "epsActual": None, "periodEnding": "2026-12-31"}
    ]
    rows += [
        {
            "symbol": "ACME",
            "date": (end + timedelta(days=30)).isoformat(),
            "epsActual": 0.50 + 0.01 * i,
            "periodEnding": end.isoformat(),
        }
        for i, end in enumerate(periods)
    ]
    return rows


def estimates_quarter() -> Payload:
    """The four quarters after the last reported one (the fixture has three): EPS 0.52 + 0.02 × i
    and net income $52 m + $2 m × i for quarter i, eleven analysts less one a quarter."""
    ends = (date(2026, 12, 31), date(2027, 3, 31), date(2027, 6, 30), date(2027, 9, 30))
    return [
        {
            "symbol": "ACME",
            "date": end.isoformat(),
            "revenueAvg": (340 + 5 * i) * M,
            "netIncomeAvg": (52 + 2 * i) * M,
            "epsAvg": 0.52 + 0.02 * i,
            "numAnalystsEps": 11 - i,
        }
        for i, end in enumerate(ends)
    ]


def bodies(
    years: Iterable[int] = YEARS,
    quarters: Iterable[date] | None = None,
    currency: str = "USD",
    cadence: Cadence = "quarterly",
) -> dict[str, Any]:
    """The payloads by endpoint; the six statements name ``currency`` as their
    ``reportedCurrency``, their figures unchanged. The quarterly statements and the street
    actuals are at ``QUARTERS``, or at ``HALF_YEARS`` for a ``half-yearly`` company, the income
    statements and cash flows with the same figures period by period, the balance sheets with the
    year's figures at a fiscal year's end and their own between (``balance_quarter``);
    ``quarters`` keeps only those statement periods."""
    periods = HALF_YEARS if cadence == "half-yearly" else QUARTERS
    years, kept = tuple(years), periods if quarters is None else tuple(quarters)
    statements = {
        "income-annual": income_annual(years),
        "balance-annual": balance_annual(years),
        "cashflow-annual": cashflow_annual(years),
        "income-quarter": income_quarter(kept, periods),
        "cashflow-quarter": cashflow_quarter(kept, periods),
        "balance-quarter": balance_quarter(p for p in periods if p in kept),
    }
    return {
        **{
            endpoint: [{**row, "reportedCurrency": currency} for row in rows]
            for endpoint, rows in statements.items()
        },
        "balance-asreported-annual": balance_as_reported(years),
        "earnings": earnings(periods),
    }


def add_company(
    conn: sqlite3.Connection,
    country: str | None = "US",
    currency: str | None = "USD",
    symbols: Sequence[str] = ("ACME",),
) -> int:
    """List ``symbols`` in the universe of a new finished full refresh; return its id."""
    refresh_id = create_refresh(
        conn, "full", None, "fairband-policy-v1", "m", NOW, EMPTY_SETTINGS_HASH
    )
    finish_refresh(conn, refresh_id, "done", NOW)
    rows = [
        CompanyRow(
            symbol=symbol,
            refresh_id=refresh_id,
            name=f"{symbol.capitalize()} Corp",
            exchange="NASDAQ",
            sector="Industrials",
            industry="Specialty Industrial Machinery",
            country=country,
            currency=currency,
            is_adr=False,
            cap_band="mid",
            market_cap=Decimal(4_000 * M),
            eligible=True,
            exclusion_reason=None,
            observed_at=NOW,
        )
        for symbol in symbols
    ]
    insert_companies(conn, rows)
    return refresh_id
