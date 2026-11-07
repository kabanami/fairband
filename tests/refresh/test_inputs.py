"""``build_inputs`` and ``series_for`` over a temporary database that ``fetch_company`` fills.

The router answers each endpoint a test sets with a synthetic payload from ``synthetic``, and every
other endpoint with its ACME fixture (consensus, quote, profile, closes, GuruFocus).
"""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from support.engine_companies import mature_growth_inputs, universe_deciles
from synthetic import (
    NOW,
    QUARTERS,
    YEARS,
    M,
    add_company,
    balance_annual,
    bodies,
    cashflow_annual,
    cashflow_quarter,
    earnings,
    income_annual,
    income_quarter,
    statement,
)
from vendor_double import FIXTURES, Clients, Clock, Router

from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures, ntm_quarters
from fairband.engine.balance import BalanceYear
from fairband.engine.classifier import Deciles, FiscalYear
from fairband.engine.roic import CapitalYear
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import Provenance
from fairband.policy import Policy, load_policy
from fairband.policy.tax import LATEST_YEAR_METHOD, TaxTable, load_tax_table
from fairband.refresh.fetch import fetch_company
from fairband.refresh.inputs import build_inputs, series_for
from fairband.refresh.inputs_statements import newest_debt_and_cash
from fairband.refresh.peers import peer_figures

TODAY = date(2026, 11, 1)
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"
DECILES = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)
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
        interest_expense=16 * M,  # four quarters of -$4 m, summed by size
        depreciation=(16 + 17 + 18 + 19) * M,
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
        interest_expense=10 * M,  # the annual lines
        depreciation=105 * M,
    )
    assert inputs.street_ttm_eps is None  # the SBC basis stays unknown
    assert "trailing-on-fiscal-year" in codes(inputs)
    assert inputs.shares_diluted == 104 * M


def test_interest_expense_is_summed_as_its_size(store: Store) -> None:
    """FMP signs the interest expense either way: each quarter counts by its size, never netted."""
    quarters = income_quarter(QUARTERS)
    for row, interest in zip(quarters[1:], (-5, 5, -5, 5), strict=True):
        row["interestExpense"] = interest
    inputs = build(store(**{**bodies(), "income-quarter": quarters}))
    assert inputs.trailing is not None and inputs.trailing.quarters == 4
    assert inputs.trailing.interest_expense == 20


def _lacking(payload: list[dict[str, Any]], index: int, line: str) -> list[dict[str, Any]]:
    """The payload with its row ``index`` not presenting ``line``."""
    del payload[index][line]
    return payload


@pytest.mark.parametrize(
    ("payloads", "expected"),
    [
        (
            {
                "income-quarter": _lacking(income_quarter(QUARTERS), 2, "interestExpense"),
                "cashflow-quarter": _lacking(
                    cashflow_quarter(QUARTERS), 3, "depreciationAndAmortization"
                ),
            },
            (None, None),
        ),
        ({}, (4 * 4 * M, (16 + 17 + 18 + 19) * M)),  # four quarters of -$4 m: by size
        (
            {
                "income-annual": _lacking(income_annual(YEARS), -1, "interestExpense"),
                "income-quarter": income_quarter(q for q in QUARTERS if q != date(2026, 3, 31)),
            },
            (None, (50 + 5 * 11) * M),  # fiscal 2025's lines
        ),
    ],
    ids=["a-quarter-lacks-the-line", "four-quarters", "fiscal-year"],
)
def test_interest_and_depreciation_are_missing_when_a_quarter_lacks_the_line(
    store: Store,
    payloads: dict[str, Any],
    expected: tuple[float | None, float | None],
) -> None:
    """As every trailing figure: a quarter without the line leaves the sum missing, never a sum of
    fewer quarters standing for twelve months. Four quarters give the interest as the sum of their
    sizes and the depreciation as the plain sum; the fiscal-year fallback reads the annual lines,
    missing when the year lacks one."""
    inputs = build(store(**{**bodies(), **payloads}))
    assert inputs.trailing is not None
    assert (inputs.trailing.interest_expense, inputs.trailing.depreciation) == expected


def test_balance_years_read_the_lines_by_name(conn_with_company: sqlite3.Connection) -> None:
    inputs = build(conn_with_company)
    assert [y.year for y in inputs.balance_years] == list(range(2015, 2026))
    assert inputs.balance_years[-1] == BalanceYear(
        year=2025,
        period_end=date(2025, 12, 31),
        total_current_assets=710 * M,
        total_current_liabilities=300 * M,
        total_assets=1610 * M,
        total_liabilities=800 * M,
        retained_earnings=510 * M,
        equity=810 * M,
        long_term_debt=300 * M,
        revenue=2100 * M,
        gross_profit=840 * M,
        operating_income=420 * M,
        net_income=315 * M,
        cfo=525 * M,
        stock_issued=5 * M,
    )


def test_balance_years_one_per_fiscal_year_with_a_balance_sheet(store: Store) -> None:
    """2020 has no balance sheet: no row. 2019 has one but no income statement or cash flow: its
    balance lines, and none of the others."""
    payloads = bodies()
    payloads["balance-annual"] = balance_annual(y for y in YEARS if y != 2020)
    payloads["income-annual"] = income_annual(y for y in YEARS if y != 2019)
    payloads["cashflow-annual"] = cashflow_annual(y for y in YEARS if y != 2019)
    years = {y.year: y for y in build(store(**payloads)).balance_years}
    assert list(years) == [y for y in range(2015, 2026) if y != 2020]
    gap = years[2019]
    assert (gap.period_end, gap.total_assets, gap.retained_earnings) == (
        date(2019, 12, 31),
        1550 * M,
        450 * M,
    )
    assert (gap.revenue, gap.gross_profit, gap.operating_income, gap.net_income) == (None,) * 4
    assert (gap.cfo, gap.stock_issued) == (None, None)


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
    assert "its 2024 statutory rate" in inputs.notes["tax_rate_latest"]  # the rate's own year
    assert inputs.refusal is None

    from_2017 = {("United States", y): 0.25 for y in range(2017, 2027)}
    late = TaxTable(from_2017, "t", {"US": "United States"})
    assert build(conn_with_company, late).refusal == "no statutory tax rate for US 2015"


def test_a_profile_country_outside_the_tax_table_is_refused(store: Store) -> None:
    profiles = [{"symbol": "ACME", "isAdr": False, "country": "PR"}]  # not in the OECD series
    conn = store(profile=profiles, **bodies())  # the universe row says US
    inputs = build(conn)
    assert (inputs.country, inputs.refusal) == ("PR", "no statutory tax rate for PR 2015")
    assert inputs.notes == {}


@pytest.mark.parametrize(
    ("country", "listed", "expected", "origin"),
    [
        ("US", None, "US", "FMP profile"),  # a scoped ticker outside the universe
        ("US", "TW", "US", "FMP profile"),  # the profile wins over the universe row
        (None, "CA", "CA", "FMP company-screener"),  # a profile without a country
    ],
    ids=["profile", "profile-over-universe", "universe"],
)
def test_the_country_is_the_profiles(
    store: Store, country: str | None, listed: str | None, expected: str, origin: str
) -> None:
    """The tax country is the FMP profile's (the headquarters, spec 6.6), else the universe
    row's; the tax input's note names it, where it came from, and the rate's year and source."""
    profiles = [{"symbol": "ACME", "isAdr": False, "marketCap": 5_000 * M, "country": country}]
    conn = store(company=False, profile=profiles, **bodies())
    if listed is not None:
        add_company(conn, country=listed)
    inputs = build(conn)
    table = load_tax_table()
    rate = table.rate_for(expected, 2025)
    assert rate is not None and not rate.estimate
    assert (inputs.country, inputs.refusal, inputs.tax_rate_latest) == (expected, None, rate.rate)
    assert inputs.notes == {
        "tax_rate_latest": f"{expected}, the headquarters country in the {origin}: its 2025 "
        f"statutory rate, from {table.source}"
    }


def test_the_country_is_unknown_without_profile_or_universe_row(store: Store) -> None:
    profiles = [{"symbol": "ACME", "isAdr": False}]
    inputs = build(store(company=False, profile=profiles, **bodies()))
    assert (inputs.country, inputs.refusal) == ("unknown", "no statutory tax rate for unknown 2015")


@pytest.mark.parametrize(
    ("is_adr", "currency"), [(True, "USD"), (False, "RUB")], ids=["adr", "currency"]
)
def test_foreign_filer_outside_the_tax_table_is_refused_as_foreign(
    store: Store, policy: Policy, is_adr: bool, currency: str
) -> None:
    """A Russian filer: no tax rate on file (Russia is not in the OECD series), so a U.S. filer
    would be refused for it."""
    annual = [{**row, "reportedCurrency": currency} for row in income_annual(YEARS)]
    profiles = [{"symbol": "ACME", "isAdr": is_adr, "marketCap": 5_000 * M}]
    conn = store(company=False, profile=profiles, **{**bodies(), "income-annual": annual})
    add_company(conn, country="RU")
    inputs = build(conn)
    assert (inputs.is_adr, inputs.currency) == (is_adr, currency)
    assert inputs.refusal is None
    assert inputs.tax_rate_latest is None and {y.tax_rate for y in inputs.capital_years} == {None}

    deciles = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)
    result = value_company(inputs, deciles, policy, TODAY)
    assert result.refusal == "foreign filer: currency and share-unit handling not built yet"
    assert result.phase.phase is not None


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
        AnnualEstimate(2026, date(2026, 12, 31), 2.0, 1300 * M, 200 * M, 14, 14, 16),
        AnnualEstimate(2027, date(2027, 12, 31), 2.2, 1400 * M, 220 * M, 12, 12, 14),
        AnnualEstimate(2028, date(2028, 12, 31), 2.4, 1500 * M, 240 * M, 10, 10, 12),
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


def test_estimate_fiscal_years_across_the_turn_of_the_calendar_year(store: Store) -> None:
    """A year that ends on the Saturday nearest 31 December: FY2026 ends 2027-01-02 and FY2027
    ends 2028-01-01, each within a week after the 2025 end's month and day in the year before."""
    annual = [
        statement(date(2024, 12, 28), 2024, "FY", revenue=900 * M),
        statement(date(2025, 12, 27), 2025, "FY", revenue=1000 * M),
    ]
    quarter_ends = ["2025-12-27", "2027-01-02", "2027-04-03", "2028-01-01", "2028-12-30"]
    year_ends = ["2027-01-02", "2028-01-01", "2028-12-30"]
    conn = store(
        **{
            "income-annual": annual,
            "estimates-quarter": [{"date": d, "epsAvg": 1.0} for d in quarter_ends],
            "estimates-annual": [{"date": d, "epsAvg": 4.0} for d in year_ends],
        }
    )
    inputs = build(conn)
    assert [(q.fiscal_year, q.fiscal_period) for q in inputs.quarter_estimates] == [
        (2025, "Q4"),
        (2026, "Q4"),
        (2027, "Q1"),
        (2027, "Q4"),
        (2028, "Q4"),
    ]
    assert [a.fiscal_year for a in inputs.annual_estimates] == [2026, 2027, 2028]


def _on_a_september_year(
    store: Store, quarters: list[dict[str, Any]], years: list[dict[str, Any]]
) -> sqlite3.Connection:
    """ACME on AAPL's calendar, a September year that ends on the last Saturday (FY2025 ends
    2025-09-27), with the given quarterly and annual consensus."""
    annual = [
        statement(date(2024, 9, 28), 2024, "FY", revenue=900 * M),
        statement(date(2025, 9, 27), 2025, "FY", revenue=1000 * M),
    ]
    payloads = {"income-annual": annual, "estimates-quarter": quarters, "estimates-annual": years}
    return store(**payloads)


def test_one_consensus_row_per_fiscal_period(store: Store) -> None:
    """FMP reports AAPL under two fiscal calendars: two rows for one fiscal period, their period
    ends a day apart. The row kept has the larger EPS analyst count, the earlier end's when it has
    it, and a count beats none; a period with one row keeps it; the rows stay in period-end order."""
    conn = _on_a_september_year(
        store,
        quarters=[
            {"date": "2027-09-25", "epsAvg": 2.0, "numAnalystsEps": 25},  # FY2027 Q4
            {"date": "2027-12-26", "epsAvg": 2.6, "revenueAvg": 140_000 * M, "numAnalystsEps": 12},
            {
                "date": "2027-12-27",
                "epsAvg": 2.8,
                "revenueAvg": 145_000 * M,
                "netIncomeAvg": 41_000 * M,
                "numAnalystsEps": 30,
            },
            {"date": "2028-03-25", "epsAvg": 1.9, "numAnalystsEps": 8},  # FY2028 Q2
            {"date": "2028-03-26", "epsAvg": 1.7},  # no count
        ],
        years=[
            {
                "date": "2028-09-29",
                "epsAvg": 8.5,
                "revenueAvg": 450_000 * M,
                "netIncomeAvg": 125_000 * M,
                "numAnalystsEps": 38,
                "numAnalystsRevenue": 36,
            },
            {"date": "2028-09-30", "epsAvg": 8.1, "numAnalystsEps": 9, "numAnalystsRevenue": 9},
        ],
    )
    inputs = build(conn)
    assert inputs.quarter_estimates == (
        QuarterEstimate(date(2027, 9, 25), 2027, "Q4", 2.0, None, None, 25),
        QuarterEstimate(date(2027, 12, 27), 2028, "Q1", 2.8, 145_000 * M, 41_000 * M, 30),
        QuarterEstimate(date(2028, 3, 25), 2028, "Q2", 1.9, None, None, 8),
    )
    assert inputs.annual_estimates == (
        AnnualEstimate(2028, date(2028, 9, 29), 8.5, 450_000 * M, 125_000 * M, 38, 38, 36),
    )


@pytest.mark.parametrize(
    "rows",
    [
        pytest.param([{"numAnalystsEps": 12}, {"numAnalystsEps": 12}], id="tie"),
        pytest.param([{}, {}], id="no-counts"),
        pytest.param(
            [{"numAnalystsEps": 30}, {"numAnalystsEps": 12}, {"numAnalystsEps": 30}],
            id="three-rows",
        ),
        pytest.param(
            [
                {"numAnalystsEps": 12, "fiscalYear": 2028, "fiscalPeriod": "Q1"},
                {"numAnalystsEps": 12},
            ],
            id="fmp-label",
        ),
    ],
)
def test_a_tie_keeps_the_later_period_end(store: Store, rows: list[dict[str, Any]]) -> None:
    """Of the rows for FY2028 Q1, and for FY2028, whose largest EPS analyst count is shared, or
    that have no count, the row with the later period end is kept, whether FMP labels the period
    or the calendar does."""
    quarter_ends = ("2027-12-26", "2027-12-27", "2027-12-28")[: len(rows)]
    year_ends = ("2028-09-29", "2028-09-30", "2028-10-01")[: len(rows)]
    conn = _on_a_september_year(
        store,
        quarters=[
            {"date": end, "epsAvg": 2.0 + k, **row}
            for k, (end, row) in enumerate(zip(quarter_ends, rows, strict=True))
        ],
        years=[
            {
                "date": end,
                "epsAvg": 8.0 + k,
                **{f: v for f, v in row.items() if f != "fiscalPeriod"},
            }
            for k, (end, row) in enumerate(zip(year_ends, rows, strict=True))
        ],
    )
    inputs = build(conn)
    last = len(rows) - 1
    [quarter] = inputs.quarter_estimates
    assert (quarter.fiscal_year, quarter.fiscal_period, quarter.period_end, quarter.eps) == (
        2028,
        "Q1",
        date.fromisoformat(quarter_ends[last]),
        2.0 + last,
    )
    [year] = inputs.annual_estimates
    assert (year.fiscal_year, year.period_end, year.eps) == (
        2028,
        date.fromisoformat(year_ends[last]),
        8.0 + last,
    )


def test_the_ntm_chain_holds_on_a_company_with_duplicate_rows(store: Store) -> None:
    """Each of the four quarters after the trailing period end, and each year of the path, comes
    twice, a day apart, the earlier row with fewer analysts and other figures. Assembly keeps
    Mature Growth Co's consensus, so the four NTM quarters chain and the golden's arithmetic
    values the row instead of refusing it "incomplete NTM consensus"."""
    mgco = mature_growth_inputs()
    quarters = [
        row
        for q in mgco.quarter_estimates
        for row in (
            {"date": str(q.period_end - timedelta(days=1)), "epsAvg": 0.1, "numAnalystsEps": 6},
            {"date": str(q.period_end), "epsAvg": q.eps, "numAnalystsEps": q.analysts},
        )
    ]
    years = [
        row
        for a in mgco.annual_estimates
        for row in (
            {"date": str(a.period_end - timedelta(days=1)), "epsAvg": 0.1, "numAnalystsEps": 2},
            {
                "date": str(a.period_end),
                "epsAvg": a.eps,
                "netIncomeAvg": a.net_income,
                "numAnalystsEps": a.analysts_eps,
            },
        )
    ]
    conn = store(**{**bodies(), "estimates-quarter": quarters, "estimates-annual": years})
    inputs = build(conn)
    assert inputs.trailing is not None and inputs.trailing.period_end == date(2026, 9, 30)
    ntm = ntm_quarters(inputs.quarter_estimates, inputs.trailing.period_end)
    assert ntm == mgco.quarter_estimates
    assert inputs.annual_estimates == mgco.annual_estimates
    stored = replace(
        mgco,
        quarter_estimates=inputs.quarter_estimates,
        annual_estimates=inputs.annual_estimates,
    )
    result = value_company(stored, universe_deciles(), load_policy(), date(2026, 10, 31))
    golden = json.loads((GOLDEN / "MGCO.json").read_text())
    assert (result.refusal, result.value) == (None, golden["value"])


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
    assert inputs.balance_years == ()
    assert inputs.data_date == TODAY
    assert inputs.price == 50.0  # the market side is still read


def test_inputs_carry_peers_debt_cash_and_the_revenue_analysts(
    store: Store, clients: Clients, clock: Clock, policy: Policy
) -> None:
    """Debt and cash from ACME's newest balance sheet. BOLT, fetched and listed, is ACME's mature
    peer once there are deciles."""
    conn = store(company=False, **bodies())
    fetch_company(conn, clients.fmp, clients.gf, "BOLT", policy, clock(), clients.secrets)
    add_company(conn, symbols=("ACME", "BOLT"))  # one universe
    tax = load_tax_table()
    i = build_inputs(conn, "ACME", policy, tax, TODAY, DECILES)
    newest = balance_annual(YEARS)[-1]
    assert i.debt == pytest.approx(newest["shortTermDebt"] + newest["longTermDebt"])
    assert i.cash == pytest.approx(
        newest["cashAndCashEquivalents"] + newest["shortTermInvestments"]
    )
    assert "debt" not in i.notes and "cash" not in i.notes
    fixture = FIXTURES / "fmp" / "analyst-estimates.annual.ACME.json"
    [first] = [r for r in json.loads(fixture.read_text()) if r["date"] == "2026-12-31"]
    assert i.annual_estimates[0].analysts_revenue == first["numAnalystsRevenue"]
    assert [p.symbol for p in i.peers] == ["BOLT"]
    peers = peer_figures(conn, "ACME", DECILES, policy, tax, TODAY)
    assert (i.peers, i.peer_source) == (peers.figures, peers.source)
    no_deciles = build_inputs(conn, "ACME", policy, tax, TODAY)
    assert (no_deciles.peers, no_deciles.peer_source) == ((), None)  # no deciles: no peers


def test_debt_and_cash_read_the_newest_balance_sheet(store: Store) -> None:
    """Each sum counts a missing line as nil; with both lines missing it is unknown. The note
    names the missing lines. The secondary valuation reads the two figures the same way."""
    sheets = balance_annual(YEARS)
    sheets[-1] = {
        **sheets[-1],
        "longTermDebt": None,
        "cashAndCashEquivalents": None,
        "shortTermInvestments": None,
    }
    conn = store(**{**bodies(), "balance-annual": sheets})
    inputs = build(conn)
    assert (inputs.debt, inputs.cash) == (20 * M, None)  # the older years' lines are not read
    assert newest_debt_and_cash(conn, "ACME") == (20 * M, None)
    assert newest_debt_and_cash(conn, "BOLT") == (None, None)  # no balance sheet on file
    assert inputs.notes["debt"] == "longTermDebt not presented"
    assert inputs.notes["cash"] == "cashAndCashEquivalents and shortTermInvestments not presented"
