"""A synthetic company for the refresh tests: ACME's FMP payloads and its universe row.

The router serves these payloads in place of the fixtures (``Router.bodies``). The company is
twelve calendar fiscal years, 2014 to 2025, and five quarters to 2026-09-30; money is in USD. The
consensus, quote, profile, closes and GuruFocus answers stay the ACME fixtures'.
"""

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

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
    """Revenue $1,000 m in 2014, up $100 m a year; the operating margin 20%."""
    return [
        statement(
            date(y, 12, 31),
            y,
            "FY",
            revenue=(1000 + 100 * k) * M,
            operatingIncome=(200 + 20 * k) * M,
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
            stockBasedCompensation=20 * M,
            netDividendsPaid=-40 * M,
            commonStockRepurchased=-60 * M,
            commonStockIssuance=5 * M,
        )
        for y in years
        if (k := y - 2014) >= 0
    ]


def balance_annual(years: Iterable[int]) -> Payload:
    """No short-term investments in 2017; a vendor-zero goodwill in 2018."""
    return [
        statement(
            date(y, 12, 31),
            y,
            "FY",
            cashAndCashEquivalents=200 * M,
            shortTermInvestments=None if y == 2017 else 50 * M,
            totalCurrentAssets=(600 + 10 * (y - 2014)) * M,
            totalCurrentLiabilities=300 * M,
            shortTermDebt=20 * M,
            propertyPlantEquipmentNet=400 * M,
            goodwill=0 if y == 2018 else 250 * M,
            intangibleAssets=260 * M,
        )
        for y in years
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


def income_quarter(ends: Iterable[date]) -> Payload:
    """Quarter i of ``QUARTERS``: revenue $300 m + $10 m × i; diluted shares 100 m + 1 m × i."""
    return [
        statement(
            end,
            end.year,
            f"Q{(end.month + 2) // 3}",
            revenue=(300 + 10 * i) * M,
            operatingIncome=(60 + 2 * i) * M,
            netIncome=(45 + i) * M,
            epsDiluted=0.45 + 0.01 * i,
            weightedAverageShsOutDil=(100 + i) * M,
        )
        for i, end in enumerate(QUARTERS)
        if end in ends
    ]


def cashflow_quarter(ends: Iterable[date]) -> Payload:
    """The third quarter has no stock compensation."""
    return [
        statement(
            end,
            end.year,
            f"Q{(end.month + 2) // 3}",
            netCashProvidedByOperatingActivities=(70 + i) * M,
            capitalExpenditure=-(20 + i) * M,
            stockBasedCompensation=None if i == 2 else 5 * M,
            netDividendsPaid=-10 * M,
            commonStockRepurchased=-15 * M,
            commonStockIssuance=1 * M,
        )
        for i, end in enumerate(QUARTERS)
        if end in ends
    ]


def earnings() -> Payload:
    """A street actual of 0.50 + 0.01 × i for quarter i, reported 30 days after its end; the
    next report on 2027-02-04."""
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
        for i, end in enumerate(QUARTERS)
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


def bodies(years: Iterable[int] = YEARS, quarters: Iterable[date] = QUARTERS) -> dict[str, Any]:
    years, quarters = tuple(years), tuple(quarters)
    return {
        "income-annual": income_annual(years),
        "balance-annual": balance_annual(years),
        "cashflow-annual": cashflow_annual(years),
        "balance-asreported-annual": balance_as_reported(years),
        "income-quarter": income_quarter(quarters),
        "cashflow-quarter": cashflow_quarter(quarters),
        "earnings": earnings(),
    }


def add_company(
    conn: sqlite3.Connection,
    country: str | None = "US",
    currency: str | None = "USD",
    symbols: Sequence[str] = ("ACME",),
) -> int:
    """List ``symbols`` in the universe of a new finished full refresh; return its id."""
    refresh_id = create_refresh(conn, "full", None, "fairband-policy-v1", "m", NOW)
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
