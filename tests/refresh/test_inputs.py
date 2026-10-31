"""``build_inputs`` and ``series_for`` over a temporary database that ``fetch_company`` fills.

The router answers each endpoint a test sets with a synthetic payload built here, and every other
endpoint with its ACME fixture (consensus, quote, profile, closes, GuruFocus). The company is
twelve calendar fiscal years, 2014 to 2025, and five quarters to 2026-09-30; money is in USD.
"""

import json
import sqlite3
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from vendor_double import Clients, Clock, Router

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.classifier import FiscalYear
from fairband.engine.roic import CapitalYear
from fairband.engine.route import CompanyInputs
from fairband.engine.types import Provenance
from fairband.policy import Policy, load_policy
from fairband.policy.tax import LATEST_YEAR_METHOD, TaxTable, load_tax_table
from fairband.refresh.fetch import fetch_company
from fairband.refresh.inputs import build_inputs, series_for
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.refreshes import create_refresh, finish_refresh

M = 1_000_000
TODAY = date(2026, 11, 1)
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)  # the refresh fixtures' clock
YEARS = tuple(range(2014, 2026))  # one fiscal year more than assembly keeps
QUARTERS = (
    date(2025, 9, 30),
    date(2025, 12, 31),
    date(2026, 3, 31),
    date(2026, 6, 30),
    date(2026, 9, 30),
)
ROUTE_KEYS = {
    "price",
    "market_cap",
    "shares_diluted",
    "statements",
    "estimates_quarter",
    "estimates_annual",
    "street_ttm_eps",
    "moat_score",
    "gf_eps_ttm",
    "gf_eps_without_nri",
    "next_earnings",
    "tax_rate_latest",
    "closes",
}

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
    conn: sqlite3.Connection, country: str | None = "US", currency: str | None = "USD"
) -> None:
    refresh_id = create_refresh(conn, "full", None, "fairband-policy-v1", "m", NOW)
    finish_refresh(conn, refresh_id, "done", NOW)
    row = CompanyRow(
        symbol="ACME",
        refresh_id=refresh_id,
        name="Acme Corp",
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
    insert_companies(conn, [row])


type Store = Callable[..., sqlite3.Connection]


@pytest.fixture
def store(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> Store:
    """Fetches ACME with the given payloads in place of its fixtures, then lists the company."""

    def fill(company: bool = True, **payloads: Any) -> sqlite3.Connection:
        router.bodies.update(
            {endpoint: json.dumps(body).encode() for endpoint, body in payloads.items()}
        )
        fetch_company(conn, clients.fmp, clients.gf, "ACME", policy, clock(), clients.secrets)
        if company:
            add_company(conn)
        return conn

    return fill


@pytest.fixture
def conn_with_company(store: Store) -> sqlite3.Connection:
    return store(**bodies())


@pytest.fixture
def conn_with_gap(store: Store) -> sqlite3.Connection:
    """The quarter ending 2026-03-31 is missing."""
    return store(**bodies(quarters=[q for q in QUARTERS if q != date(2026, 3, 31)]))


@pytest.fixture
def tax_table_without_2025() -> TaxTable:
    """The packaged table up to 2024."""
    table = load_tax_table()
    rates = {}
    for country, year in table.years():
        rate = table.rate_for(country, year)
        if year < 2025 and rate is not None:
            rates[(country, year)] = rate.rate
    return TaxTable(rates, table.source, {"US": "United States"})


def build(
    conn: sqlite3.Connection, tax: TaxTable | None = None, today: date = TODAY
) -> CompanyInputs:
    return build_inputs(conn, "ACME", load_policy(), tax or load_tax_table(), today)


def codes(inputs: CompanyInputs) -> list[str]:
    return [f.code for f in inputs.input_flags]


def test_builds_series_and_capital_years(conn_with_company: sqlite3.Connection) -> None:
    inputs = build(conn_with_company)
    assert [fy.year for fy in inputs.series] == list(range(2015, 2026))
    assert inputs.series[0] == FiscalYear(
        year=2015,
        period_end=date(2015, 12, 31),
        currency="USD",
        revenue=1100 * M,
        operating_income=220 * M,
        cfo=275 * M,
        cfi=-110 * M,
        cff=-132 * M,
        capex=-66 * M,
    )
    assert inputs.series[-1].revenue == 2100 * M
    assert series_for(conn_with_company, "ACME") == inputs.series

    years = {cy.year: cy for cy in inputs.capital_years}
    assert list(years) == list(range(2015, 2026))
    assert years[2015] == CapitalYear(
        year=2015,
        operating_income=220 * M,
        tax_rate=0.389975,
        total_current_assets=610 * M,
        cash_and_investments=250 * M,
        total_current_liabilities=300 * M,
        short_term_debt=20 * M,
        current_lease_liability=None,  # not presented before 2019
        net_ppe=400 * M,
        lease_rou_asset=None,
        goodwill=250 * M,
        intangibles=240 * M,  # the issuer's total, not the normalized 260
    )
    assert years[2016].intangibles == 260 * M  # no as-reported total: the normalized line
    assert years[2017].cash_and_investments == 200 * M  # the missing investments count as nil
    assert years[2018].goodwill is None  # a vendor zero is not a reported zero
    assert (years[2019].lease_rou_asset, years[2019].current_lease_liability) == (90 * M, 15 * M)
    assert inputs.estimate_methods == {"intangibles": "bs10-intangibles-total-v1"}
    assert codes(inputs) == ["leases-not-on-balance-sheet"]
    assert "2015, 2016, 2017, 2018" in inputs.input_flags[0].sentence
    assert inputs.tax_rate_latest == 0.25569714
    assert inputs.refusal is None


def test_a_missing_fiscal_year_keeps_its_place(store: Store) -> None:
    conn = store(**bodies(years=[y for y in YEARS if y != 2020]))
    inputs = build(conn)
    assert [fy.year for fy in inputs.series] == list(range(2015, 2026))
    assert inputs.series[5] == FiscalYear(
        2020, date(2020, 12, 31), "USD", None, None, None, None, None, None
    )
    gap = inputs.capital_years[5]
    assert gap.year == 2020 and gap.operating_income is None
    assert (gap.total_current_assets, gap.total_current_liabilities, gap.net_ppe) == (None,) * 3
    assert series_for(conn, "ACME") == inputs.series


def test_trailing_from_four_consecutive_quarters(conn_with_company: sqlite3.Connection) -> None:
    inputs = build(conn_with_company)
    assert inputs.trailing == TrailingFigures(
        period_end=date(2026, 9, 30),
        quarters=4,
        on_fiscal_year=False,
        revenue=1300 * M,
        operating_income=260 * M,
        net_income=190 * M,
        eps_diluted=pytest.approx(1.90),
        sbc=None,  # one quarter has none
        cfo=290 * M,
        capex=-90 * M,
        dividends=-40 * M,
        buybacks=-60 * M,
        equity_issued=4 * M,
    )
    assert inputs.street_ttm_eps == pytest.approx(0.51 + 0.52 + 0.53 + 0.54)
    assert inputs.shares_diluted == 104 * M  # the newest quarter's
    assert "trailing-on-fiscal-year" not in codes(inputs)


def test_street_eps_needs_each_trailing_quarter(store: Store) -> None:
    """No street actual for the quarter ending 2026-03-31."""
    actuals = [row for row in earnings() if row["periodEnding"] != "2026-03-31"]
    inputs = build(store(**{**bodies(), "earnings": actuals}))
    assert inputs.trailing is not None and inputs.trailing.quarters == 4
    assert inputs.street_ttm_eps is None and "street_ttm_eps" not in inputs.provenance


def test_trailing_falls_back_when_quarters_not_consecutive(
    conn_with_gap: sqlite3.Connection,
) -> None:
    inputs = build(conn_with_gap)
    assert inputs.trailing == TrailingFigures(
        period_end=date(2025, 12, 31),
        quarters=1,
        on_fiscal_year=True,
        revenue=2100 * M,
        operating_income=420 * M,
        net_income=315 * M,
        eps_diluted=pytest.approx(3.15),
        sbc=20 * M,
        cfo=525 * M,
        capex=-126 * M,
        dividends=-40 * M,
        buybacks=-60 * M,
        equity_issued=5 * M,
    )
    assert inputs.street_ttm_eps is None  # the SBC basis stays unknown
    assert "trailing-on-fiscal-year" in codes(inputs)
    assert inputs.shares_diluted == 104 * M


def test_tax_rate_estimate_flag_and_refusal(
    conn_with_company: sqlite3.Connection, tax_table_without_2025: TaxTable
) -> None:
    inputs = build(conn_with_company, tax_table_without_2025)
    rate_2024 = tax_table_without_2025.rate_for("US", 2024)
    assert rate_2024 is not None and inputs.tax_rate_latest == rate_2024.rate
    assert inputs.capital_years[-1].tax_rate == rate_2024.rate
    assert codes(inputs).count("tax-carried-forward") == 1
    [carried] = [f for f in inputs.input_flags if f.code == "tax-carried-forward"]
    assert "2024" in carried.sentence and "2025" in carried.sentence
    assert inputs.estimate_methods["tax_rate_latest"] == LATEST_YEAR_METHOD
    assert inputs.refusal is None

    from_2017 = {("United States", y): 0.25 for y in range(2017, 2027)}
    late = TaxTable(from_2017, "t", {"US": "United States"})
    assert build(conn_with_company, late).refusal == "no statutory tax rate for US 2015"

    add_company(conn_with_company, country="TW")  # a newer universe row, outside the table
    assert build(conn_with_company).refusal == "no statutory tax rate for TW 2015"


def test_provenance_dates(conn_with_company: sqlite3.Connection) -> None:
    inputs = build(conn_with_company)
    p = inputs.provenance
    assert set(p) == ROUTE_KEYS
    assert p["estimates_quarter"].source == "FMP analyst-estimates"
    assert p["estimates_quarter"] == Provenance("FMP analyst-estimates", TODAY, NOW, NOW)
    assert p["estimates_annual"] == Provenance("FMP analyst-estimates", TODAY, NOW, NOW)
    assert p["price"] == Provenance("FMP quote", date(2026, 10, 30), NOW, NOW)
    assert p["market_cap"] == Provenance("FMP quote", date(2026, 10, 30), NOW, NOW)
    assert p["shares_diluted"] == Provenance("FMP income-statement", date(2026, 9, 30), NOW, NOW)
    assert p["statements"].as_of == date(2025, 12, 31)
    assert (p["statements"].observed_at, p["statements"].entered_at) == (NOW, NOW)
    assert p["street_ttm_eps"] == Provenance("FMP earnings", date(2026, 10, 30), NOW, NOW)
    assert p["next_earnings"] == Provenance("FMP earnings", TODAY, NOW, NOW)
    assert p["moat_score"] == Provenance("GuruFocus summary", TODAY, NOW, NOW)
    assert p["gf_eps_ttm"] == p["gf_eps_without_nri"]
    assert p["gf_eps_ttm"] == Provenance("GuruFocus keyratios", TODAY, NOW, NOW)
    assert p["closes"] == Provenance("FMP historical-price-eod/full", date(2026, 10, 30), NOW, None)
    assert p["tax_rate_latest"].source.startswith("OECD")
    assert inputs.data_date == TODAY


def test_consensus_and_market_values(conn_with_company: sqlite3.Connection) -> None:
    inputs = build(conn_with_company)
    assert inputs.quarter_estimates == (
        QuarterEstimate(date(2026, 12, 31), 2026, "Q4", 0.52, 340 * M, 52 * M, 11),
        QuarterEstimate(date(2027, 3, 31), 2027, "Q1", 0.54, 345 * M, 54 * M, 10),
        QuarterEstimate(date(2027, 6, 30), 2027, "Q2", 0.56, 350 * M, 56 * M, 9),
    )
    assert inputs.annual_estimates == (
        AnnualEstimate(2026, date(2026, 12, 31), 2.0, 1300 * M, 200 * M, 14, 14),
        AnnualEstimate(2027, date(2027, 12, 31), 2.2, 1400 * M, 220 * M, 12, 12),
        AnnualEstimate(2028, date(2028, 12, 31), 2.4, 1500 * M, 240 * M, 10, 10),
    )
    assert (inputs.symbol, inputs.name, inputs.country, inputs.currency) == (
        "ACME",
        "Acme Corp",
        "US",
        "USD",
    )
    assert (inputs.price, inputs.price_date, inputs.market_cap) == (
        50.0,
        date(2026, 10, 30),
        5_000 * M,
    )
    assert inputs.is_adr is False
    assert (inputs.moat_score, inputs.gf_eps_ttm, inputs.gf_eps_without_nri) == (7.0, 6.11, 5.87)
    assert inputs.next_earnings == date(2027, 2, 4)
    assert inputs.closes == (
        (date(2026, 10, 28), 49.0),
        (date(2026, 10, 29), 49.5),
        (date(2026, 10, 30), 50.0),
    )
    assert all(isinstance(x, float) for x in (inputs.price, inputs.series[0].revenue))
    assert build(conn_with_company, today=date(2027, 3, 1)).next_earnings is None  # in the past


def test_estimate_fiscal_years_follow_a_52_53_week_year(store: Store) -> None:
    """A September year that ends on the last Saturday: FY2026 ends 2026-10-03, six days after
    the 2025 end's month and day."""
    annual = [
        statement(date(2024, 9, 28), 2024, "FY", revenue=900 * M),
        statement(date(2025, 9, 27), 2025, "FY", revenue=1000 * M),
    ]
    quarter_ends = ["2025-12-27", "2026-03-28", "2026-06-27", "2026-10-03", "2027-01-02"]
    conn = store(
        **{
            "income-annual": annual,
            "estimates-quarter": [{"date": d, "epsAvg": 1.0} for d in quarter_ends],
            "estimates-annual": [{"date": d, "epsAvg": 4.0} for d in ("2026-10-03", "2027-10-02")],
        }
    )
    inputs = build(conn)
    assert [(q.fiscal_year, q.fiscal_period) for q in inputs.quarter_estimates] == [
        (2026, "Q1"),
        (2026, "Q2"),
        (2026, "Q3"),
        (2026, "Q4"),
        (2027, "Q1"),
    ]
    assert [a.fiscal_year for a in inputs.annual_estimates] == [2026, 2027]


@pytest.mark.parametrize(
    ("profile", "market_cap", "source"),
    [
        ({"isAdr": True, "marketCap": 4_500 * M}, 4_500 * M, "FMP profile"),
        ({"isAdr": True}, 4_000 * M, "FMP company-screener"),
    ],
)
def test_market_values_fall_back(
    store: Store, router: Router, profile: dict[str, Any], market_cap: float, source: str
) -> None:
    router.fail.add("price-history")
    annual = [
        {k: v for k, v in row.items() if k != "reportedCurrency"} for row in income_annual(YEARS)
    ]
    profiles = [{"symbol": "ACME", **profile}]
    conn = store(company=False, quote=[], profile=profiles, **{"income-annual": annual})
    add_company(conn, currency=None)
    inputs = build(conn)
    assert (inputs.price, inputs.price_date) == (None, None)
    assert inputs.market_cap == market_cap and inputs.provenance["market_cap"].source == source
    assert inputs.is_adr is True
    assert inputs.currency == "unknown" and "currency-unknown" in codes(inputs)
    assert inputs.closes == () and "closes" not in inputs.provenance
    assert "price" not in inputs.provenance


def test_no_financial_statements_is_a_refusal(store: Store, router: Router) -> None:
    router.fail.add("income-annual")
    conn = store()
    assert series_for(conn, "ACME") == ()
    inputs = build(conn)
    assert inputs.refusal == "no financial statements"
    assert (inputs.series, inputs.capital_years, inputs.trailing) == ((), (), None)
    assert inputs.data_date == TODAY
    assert inputs.price == 50.0  # the market side is still read
