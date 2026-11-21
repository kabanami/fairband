"""``build_inputs`` and ``series_for`` over a temporary database that ``fetch_company`` fills.

The router answers each endpoint a test sets with a synthetic payload from ``synthetic``, and every
other endpoint with its ACME fixture (consensus, quote, profile, closes, GuruFocus).
"""

import json
import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
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
    balance_quarter,
    bodies,
    cashflow_annual,
    cashflow_quarter,
    estimates_quarter,
    income_annual,
    income_quarter,
    statement,
)
from vendor_double import FIXTURES, Clients, Clock, Router

from fairband.engine.anchor import (
    AnnualEstimate,
    Cadence,
    QuarterEstimate,
    StockPayHistory,
    TrailingFigures,
    ntm_quarters,
    ntm_window,
)
from fairband.engine.balance import BalanceYear, NewestSheet, SheetFigures
from fairband.engine.classifier import Deciles, FiscalYear
from fairband.engine.roic import CapitalYear
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import Provenance
from fairband.policy import Policy, load_policy
from fairband.policy.inflation import load_inflation_table
from fairband.policy.tax import LATEST_YEAR_METHOD, TaxTable, load_tax_table
from fairband.refresh.fetch import fetch_company
from fairband.refresh.inputs import build_inputs, series_for
from fairband.refresh.inputs_statements import (
    QuarterFigures,
    StoredQuarters,
    cadence_of,
    newest_debt_and_cash,
    statements_for,
    stored_quarters,
)
from fairband.refresh.peers import peer_figures
from fairband.refresh.rates import FX_QUOTE, fetch_rates
from fairband.store.observations import insert_observations
from fairband.store.vendor import record_response
from fairband.vendors.normalize_fmp import fx_quote_observations

TODAY = date(2026, 11, 1)
GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"
DECILES = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)
ROUTE_KEYS = {
    "price",
    "market_cap",
    "shares_diluted",
    "statements",
    "balance_sheet",  # the newest balance sheet, the synthetic quarter of 2026-09-30
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

SHEET_SOURCE = "FMP balance-sheet-statement"
# The five lines of the synthetic company's annual sheet of fiscal 2025 the note sheet-shift
# compares, and the sheet as the engine reads it (``balance_annual``): its own lines are its
# figures, and no annual sheet stands beside them.
FY2025_FIGURES = SheetFigures("fiscal 2025", 20 * M, 300 * M, 200 * M, 50 * M, None)
FY2025 = NewestSheet(
    date(2025, 12, 31), "fiscal 2025", False, 710 * M, 800 * M, None, figures=FY2025_FIGURES
)
# The same lines of its quarter of 2026-06-30, the second of fiscal 2026 (``balance_quarter``).
Q2_FIGURES = SheetFigures("fiscal 2026 Q2", 30 * M, 280 * M, 220 * M, 40 * M, None)

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
        net_income=165 * M,
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


def test_the_series_carries_each_year_s_net_income(conn_with_company: sqlite3.Connection) -> None:
    """Spec 2026-11-13 11: each fiscal year carries the annual income statement's net income, 15%
    of the synthetic company's revenue every year ($150 m on $1,000 m in 2014, up $15 m a year),
    which the ten-year median net margin reads; the classifier reads it in no rule."""
    series = series_for(conn_with_company, "ACME")
    assert [fy.net_income for fy in series] == [(150 + 15 * k) * M for k in range(1, 12)]
    for fy in series:
        assert fy.revenue is not None and fy.net_income is not None
        assert fy.net_income / fy.revenue == pytest.approx(0.15)


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
        income_tax=(12 + 13 + 14 + 15) * M,
        pretax_income=(58 + 60 + 62 + 64) * M,
    )
    assert inputs.street_ttm_eps == pytest.approx(0.51 + 0.52 + 0.53 + 0.54)
    assert inputs.shares_diluted == 104 * M  # the newest quarter's
    assert "trailing-on-fiscal-year" not in codes(inputs)
    # no trailing quarter at zero (the one without stock pay is missing, not zero); every fiscal
    # year's cash flow holds $20 m
    assert inputs.stock_pay == StockPayHistory(0, 2025, 20 * M)


def test_the_stock_pay_history_counts_the_trailing_quarters_at_zero(store: Store) -> None:
    """Spec 2026-11-13 7.1: the quarter to 2026-06-30 at zero and the one to 2026-03-31, which
    has none in the fixture, at $5 m: one trailing quarter at zero, a trailing sum of $15 m, and
    fiscal 2025 the newest year above zero."""
    flows = cashflow_quarter(QUARTERS)
    flows[2]["stockBasedCompensation"] = 5 * M
    flows[3]["stockBasedCompensation"] = 0
    inputs = build(store(**{**bodies(), "cashflow-quarter": flows}))
    assert inputs.trailing is not None and inputs.trailing.sbc == 15 * M
    assert inputs.stock_pay == StockPayHistory(1, 2025, 20 * M)


def test_the_stock_pay_history_on_the_fiscal_year(store: Store) -> None:
    """On the fiscal-year fallback the one trailing period is the year: fiscal 2025 at zero is one
    period at zero, and fiscal 2024's $20 m the newest year above zero."""
    years = cashflow_annual(YEARS)
    years[-1]["stockBasedCompensation"] = 0
    gap = [q for q in QUARTERS if q != date(2026, 3, 31)]
    inputs = build(store(**{**bodies(quarters=gap), "cashflow-annual": years}))
    assert inputs.trailing is not None and inputs.trailing.on_fiscal_year
    assert inputs.trailing.sbc == 0
    assert inputs.stock_pay == StockPayHistory(1, 2024, 20 * M)


@pytest.mark.parametrize(
    ("cadence", "periods", "missing"),
    [("quarterly", 4, "2026-03-31"), ("half-yearly", 2, "2025-12-31")],
)
def test_street_eps_needs_each_trailing_period(
    store: Store, cadence: Cadence, periods: int, missing: str
) -> None:
    """No street actual at one trailing period end, a quarter's or a half-year's: none is read."""
    payloads = bodies(cadence=cadence)
    actuals = [row for row in payloads["earnings"] if row["periodEnding"] != missing]
    inputs = build(store(**{**payloads, "earnings": actuals}))
    assert inputs.trailing is not None and inputs.trailing.quarters == periods
    assert inputs.trailing.cadence == cadence
    assert inputs.street_ttm_eps is None and "street_ttm_eps" not in inputs.provenance


@pytest.mark.parametrize(
    ("currencies", "sentence"),
    [
        (
            {4: "USD"},
            (
                "The quarter to 2026-09-30 is in USD while the fiscal years are in CAD, so the "
                "trailing figures are fiscal 2025's."
            ),
        ),
        (
            {1: "USD", 2: "GBP", 4: "USD"},
            (
                "The quarters to 2025-12-31 and 2026-09-30 are in USD and the quarter to "
                "2026-03-31 is in GBP while the fiscal years are in CAD, so the trailing figures "
                "are fiscal 2025's."
            ),
        ),
    ],
    ids=["one", "several"],
)
def test_a_quarter_in_another_currency_sends_the_trailing_figures_to_the_fiscal_year(
    store: Store, currencies: dict[int, str], sentence: str
) -> None:
    """The fiscal years report in CAD and a trailing quarter in another currency (spec 2026-11-10
    7): the four quarters are not summed, the trailing figures are fiscal 2025's and the note
    names the quarters, their currency and the years'; no street actual is read, as on any
    fallback."""
    payloads = bodies(currency="CAD")
    quarters = payloads["income-quarter"]
    for k, currency in currencies.items():
        quarters[k] = {**quarters[k], "reportedCurrency": currency}
    inputs = build(store(**payloads))
    assert inputs.currency == "CAD"
    assert inputs.trailing is not None and inputs.trailing.on_fiscal_year
    assert inputs.trailing.period_end == date(2025, 12, 31)
    assert inputs.street_ttm_eps is None
    note = next(f for f in inputs.input_flags if f.code == "trailing-on-fiscal-year")
    assert note.sentence == sentence


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


ON_FISCAL_YEAR = (
    "The statement periods on file are neither four consecutive quarters nor two consecutive "
    "half-years, so the trailing figures are fiscal 2025's."
)


def test_quarterly_rows_read_as_today(conn_with_company: sqlite3.Connection) -> None:
    """Rows 91 or 92 days apart (spec 2026-11-10 11.4): the quarterly cadence, four quarters."""
    inputs = build(conn_with_company)
    assert inputs.trailing is not None
    assert (inputs.trailing.cadence, inputs.trailing.quarters) == ("quarterly", 4)


def test_half_year_rows_give_a_two_period_trailing_sum(store: Store) -> None:
    """Spec 2026-11-10 11.4: statement rows ending 2025-06-30, 2025-12-31 and 2026-06-30 (184 and
    181 days apart) are half-years. The trailing figures sum the last two, joined to their cash
    flows by period end; the trailing periods and the street actuals are the two, and the street
    trailing EPS is the two actuals' sum."""
    conn = store(**bodies(cadence="half-yearly"))
    inputs = build(conn)
    assert inputs.trailing == TrailingFigures(
        period_end=date(2026, 6, 30),
        quarters=2,
        on_fiscal_year=False,
        revenue=(320 + 330) * M,
        operating_income=(64 + 66) * M,
        net_income=(47 + 48) * M,
        eps_diluted=pytest.approx(0.47 + 0.48),
        sbc=None,  # the older half-year has none
        cfo=(72 + 73) * M,
        capex=-(22 + 23) * M,
        dividends=-20 * M,
        buybacks=-30 * M,
        equity_issued=2 * M,
        interest_expense=8 * M,  # two half-years of -$4 m, summed by size
        depreciation=(17 + 18) * M,
        cadence="half-yearly",
        income_tax=(13 + 14) * M,  # the two half-years' lines, periods 2 and 3 of the fixture
        pretax_income=(60 + 62) * M,
    )
    stated = statements_for(conn, "ACME", "US", load_tax_table(), TODAY)
    assert [p.end for p in stated.trailing_periods] == [date(2025, 12, 31), date(2026, 6, 30)]
    assert stated.trailing_quarter_ends == (date(2025, 12, 31), date(2026, 6, 30))
    assert inputs.street_ttm_eps == pytest.approx(0.52 + 0.53)
    assert inputs.shares_diluted == 103 * M  # the newest half-year's
    assert "trailing-on-fiscal-year" not in codes(inputs)


def test_rows_a_year_apart_give_no_cadence_and_fall_back(store: Store) -> None:
    """Rows ending 2025-06-30 and 2026-06-30 only, a year apart, give no cadence at all: the
    trailing figures are fiscal 2025's, flagged, on the quarterly cadence a fallback carries when
    the rows give none, with no trailing period ends and no street EPS."""
    conn = store(**bodies(cadence="half-yearly", quarters=(date(2025, 6, 30), date(2026, 6, 30))))
    inputs = build(conn)
    t = inputs.trailing
    assert t is not None and t.on_fiscal_year
    assert (t.period_end, t.quarters, t.cadence) == (date(2025, 12, 31), 1, "quarterly")
    assert statements_for(conn, "ACME", "US", load_tax_table(), TODAY).trailing_quarter_ends == ()
    assert inputs.street_ttm_eps is None
    [note] = [f for f in inputs.input_flags if f.code == "trailing-on-fiscal-year"]
    assert note.sentence == ON_FISCAL_YEAR


def test_a_quarterly_filer_missing_its_second_newest_quarter_falls_back(store: Store) -> None:
    """The gap guard (BNY's shape): quarters to 2026-09-30 with 2026-06-30 missing put the two
    newest rows 183 days apart, but the row before the older of them is a quarter earlier (90
    days), so the rows give no cadence. The trailing figures are fiscal 2025's, flagged, and never
    two quarters summed as a year."""
    inputs = build(store(**bodies(quarters=[q for q in QUARTERS if q != date(2026, 6, 30)])))
    t = inputs.trailing
    assert t is not None and t.on_fiscal_year
    assert (t.period_end, t.quarters, t.cadence) == (date(2025, 12, 31), 1, "quarterly")
    assert t.revenue == 2100 * M
    [note] = [f for f in inputs.input_flags if f.code == "trailing-on-fiscal-year"]
    assert note.sentence == ON_FISCAL_YEAR


def test_a_half_yearly_reporter_missing_an_older_half_year_stays_half_yearly(
    store: Store,
) -> None:
    """MAAS's shape: half-years ending 2024-12-31, 2025-12-31 and 2026-06-30, the first half of
    2025 missing. The row before the older of the two newest is a year earlier, not a quarter, so
    the company reads half-yearly and its trailing figures are the last two half-years."""
    ends = (date(2024, 12, 31), date(2025, 12, 31), date(2026, 6, 30))
    inputs = build(store(**bodies(cadence="half-yearly", quarters=ends)))
    t = inputs.trailing
    assert t is not None
    assert (t.cadence, t.quarters, t.on_fiscal_year) == ("half-yearly", 2, False)
    assert (t.period_end, t.revenue) == (date(2026, 6, 30), (320 + 330) * M)
    assert "trailing-on-fiscal-year" not in codes(inputs)


def test_the_quarterly_fallback_sentence_names_both_cadences(
    conn_with_gap: sqlite3.Connection,
) -> None:
    """Four quarters that are not consecutive fall back with the same sentence."""
    [note] = [f for f in build(conn_with_gap).input_flags if f.code == "trailing-on-fiscal-year"]
    assert note.sentence == ON_FISCAL_YEAR


def test_a_half_year_in_another_currency_sends_the_trailing_figures_to_the_fiscal_year(
    store: Store,
) -> None:
    """Spec 2026-11-10 7 on half-years: the fiscal years report in CAD and the newest half-year in
    USD, so the two are not summed; the note names the half-year. The fallback keeps the
    half-yearly cadence the rows gave, so the NTM window after the fiscal year is still the two
    half-years its consensus gives."""
    payloads = bodies(currency="CAD", cadence="half-yearly")
    rows = payloads["income-quarter"]
    rows[3] = {**rows[3], "reportedCurrency": "USD"}
    halves = ("2026-06-30", "2026-12-31")
    payloads["estimates-quarter"] = [
        {"symbol": "ACME", "date": d, "epsAvg": 1.0, "revenueAvg": 650 * M} for d in halves
    ]
    inputs = build(store(**payloads))
    t = inputs.trailing
    assert t is not None and t.on_fiscal_year
    assert (t.period_end, t.quarters, t.cadence) == (date(2025, 12, 31), 1, "half-yearly")
    assert inputs.street_ttm_eps is None
    [note] = [f for f in inputs.input_flags if f.code == "trailing-on-fiscal-year"]
    assert note.sentence == (
        "The half-year to 2026-06-30 is in USD while the fiscal years are in CAD, so the "
        "trailing figures are fiscal 2025's."
    )
    window = ntm_window(inputs.quarter_estimates, t.period_end, t.cadence)
    assert window is not None
    periods, cadence = window
    assert cadence == "half-yearly" and [p.period_end.isoformat() for p in periods] == list(halves)


def test_a_half_yearly_reporter_with_quarterly_consensus_reads_four_quarters(
    store: Store,
) -> None:
    """ABVX's shape (spec 2026-11-10 8): half-year statements and quarterly consensus rows. The
    trailing figures are the two half-years, the street actuals those at their two ends, and the
    NTM window the four quarters its consensus gives, on the quarterly cadence."""
    ends = ("2026-09-30", "2026-12-31", "2027-03-31", "2027-06-30")
    consensus = [{"symbol": "ACME", "date": d, "epsAvg": 0.25, "revenueAvg": 170 * M} for d in ends]
    inputs = build(store(**{**bodies(cadence="half-yearly"), "estimates-quarter": consensus}))
    t = inputs.trailing
    assert t is not None and (t.cadence, t.quarters) == ("half-yearly", 2)
    assert inputs.street_ttm_eps == pytest.approx(0.52 + 0.53)
    window = ntm_window(inputs.quarter_estimates, t.period_end, t.cadence)
    assert window is not None
    periods, cadence = window
    assert cadence == "quarterly"
    assert [p.period_end.isoformat() for p in periods] == list(ends)


@pytest.mark.parametrize(
    ("days", "cadence"),
    [
        (79, None),
        (80, "quarterly"),
        (91, "quarterly"),
        (100, "quarterly"),
        (101, None),
        (169, None),
        (170, "half-yearly"),
        (181, "half-yearly"),
        (195, "half-yearly"),
        (196, None),
        (365, None),
    ],
)
def test_the_cadence_reads_the_two_newest_period_ends(days: int, cadence: Cadence | None) -> None:
    """Quarterly when the two newest rows end 80 to 100 days apart, half-yearly when 170 to 195,
    else none; an older gap does not count, and one row has no cadence."""
    newest = date(2026, 6, 30)
    assert cadence_of([date(2024, 1, 1), newest - timedelta(days=days), newest]) == cadence
    assert cadence_of([newest]) is None and cadence_of([]) is None


@pytest.mark.parametrize(
    ("before", "cadence"),
    [
        (79, "half-yearly"),
        (80, None),
        (90, None),
        (100, None),
        (101, "half-yearly"),
        (181, "half-yearly"),
        (365, "half-yearly"),
    ],
)
def test_a_quarter_before_the_two_newest_rows_rules_out_half_years(
    before: int, cadence: Cadence | None
) -> None:
    """The gap guard: two newest rows 183 days apart read half-yearly only when the row before the
    older of them, if there is one, does not end 80 to 100 days before it (a quarterly filer
    missing its second-newest quarter)."""
    older, newest = date(2026, 3, 31), date(2026, 9, 30)
    assert cadence_of([older - timedelta(days=before), older, newest]) == cadence
    assert cadence_of([older, newest]) == "half-yearly"


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


# The trailing figures' lines, which a stored quarter holds too.
TRAILING_LINES = (
    "revenue",
    "operating_income",
    "net_income",
    "eps_diluted",
    "sbc",
    "cfo",
    "capex",
    "dividends",
    "buybacks",
    "equity_issued",
    "interest_expense",
    "depreciation",
    "income_tax",
    "pretax_income",
)


def test_the_stored_quarters_read_as_the_trailing_figures_read_them(store: Store) -> None:
    """Spec 2026-11-11, 7.1: every stored quarter, oldest first, by its fiscal label as stored,
    each line that period's own term of the trailing sum (the interest expense by its size, the
    rest as signed), so the newest four add to the trailing figure of every line both hold."""
    conn = store(**bodies())
    stored = stored_quarters(conn, "ACME")
    quarters = stored.periods
    assert [q.period for q in quarters] == ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]
    assert [q.period_end for q in quarters] == list(QUARTERS)
    assert stored.other_currency == 0
    assert quarters[-1] == QuarterFigures(
        fiscal_year=2026,
        fiscal_period="Q3",
        period_end=date(2026, 9, 30),
        revenue=340 * M,
        operating_income=68 * M,
        net_income=49 * M,
        eps_diluted=pytest.approx(0.49),
        sbc=5 * M,
        cfo=74 * M,
        capex=-24 * M,
        dividends=-10 * M,
        buybacks=-15 * M,
        equity_issued=1 * M,
        interest_expense=4 * M,  # -$4 m as stored, by its size
        depreciation=19 * M,
        income_tax=15 * M,
        pretax_income=64 * M,
    )
    assert quarters[2].sbc is None  # the third period has no stock compensation
    trailing = build(conn).trailing
    assert trailing is not None and (trailing.quarters, trailing.on_fiscal_year) == (4, False)
    held = [line for line in TRAILING_LINES if getattr(trailing, line) is not None]
    assert len(held) == 13  # all but the stock compensation
    for line in held:
        total = sum(getattr(q, line) for q in quarters[-4:])
        assert total == pytest.approx(getattr(trailing, line)), line


def test_a_half_yearly_reporter_s_stored_periods_are_its_half_years(store: Store) -> None:
    """Spec 2026-11-11, 7.1: a half-yearly reporter's stored periods are served by their stored
    labels, and the newest two add to its trailing figures."""
    conn = store(**bodies(cadence="half-yearly"))
    halves = stored_quarters(conn, "ACME").periods
    assert [h.period for h in halves] == ["2024-Q4", "2025-Q2", "2025-Q4", "2026-Q2"]
    trailing = build(conn).trailing
    assert trailing is not None and trailing.cadence == "half-yearly"
    assert halves[-2].revenue + halves[-1].revenue == trailing.revenue == (320 + 330) * M


@pytest.mark.parametrize(
    "kept",
    [{"quarters": ()}, {"years": ()}],
    ids=["no-quarterly-rows", "no-annual-income-statement"],
)
def test_no_quarter_rows_give_no_quarters(store: Store, kept: dict[str, Any]) -> None:
    """Review Focus 5: a company stored without quarterly rows has no quarters; one without an
    annual income statement has none either, its quarterly rows notwithstanding."""
    assert stored_quarters(store(**bodies(**kept)), "ACME") == StoredQuarters((), 0)


@pytest.mark.parametrize(
    ("annual", "kept", "counted"),
    [
        ("USD", ["2026-Q1", "2026-Q2", "2026-Q3"], 2),
        (None, ["2025-Q3", "2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"], 0),
    ],
    ids=["usd-years", "years-without-a-currency"],
)
def test_a_quarter_in_another_currency_is_left_out_and_counted(
    store: Store, annual: str | None, kept: list[str], counted: int
) -> None:
    """Review Focus 5 (spec 2026-11-11, 7.1): beside annual statements in USD, the two oldest
    quarters reported in CAD are left out and counted, and a quarter with no currency on file
    counts as the reporting one's, as the trailing figures judge a period; where the annual
    statements name no currency, no quarter is left out."""
    payloads = bodies()
    payloads["income-annual"] = [
        {**row, "reportedCurrency": annual} for row in payloads["income-annual"]
    ]
    rows = payloads["income-quarter"]
    for k in (0, 1):
        rows[k] = {**rows[k], "reportedCurrency": "CAD"}
    rows[2] = {**rows[2], "reportedCurrency": None}
    stored = stored_quarters(store(**payloads), "ACME")
    assert [q.period for q in stored.periods] == kept
    assert stored.other_currency == counted


def test_a_period_without_a_fiscal_label_is_left_out(store: Store) -> None:
    """Spec 2026-11-11, 7.1: a quarter stored without its fiscal year, and one without its fiscal
    period, are left out and not counted."""
    payloads = bodies()
    rows = payloads["income-quarter"]
    del rows[1]["fiscalYear"]
    del rows[3]["period"]
    stored = stored_quarters(store(**payloads), "ACME")
    assert [q.period for q in stored.periods] == ["2025-Q3", "2026-Q1", "2026-Q3"]
    assert stored.other_currency == 0


def test_two_periods_with_one_label_keep_the_later_end(store: Store) -> None:
    """Spec 2026-11-11, 7.1: two stored periods labelled 2025-Q4, ending 2025-09-30 and
    2025-12-31: the one with the later end is kept, in its place."""
    payloads = bodies()
    payloads["income-quarter"][0] |= {"period": "Q4"}
    stored = stored_quarters(store(**payloads), "ACME")
    assert [q.period for q in stored.periods] == ["2025-Q4", "2026-Q1", "2026-Q2", "2026-Q3"]
    assert (stored.periods[0].period_end, stored.periods[0].revenue) == (
        date(2025, 12, 31),
        310 * M,
    )


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
def test_a_missing_tax_rate_refuses_every_company(
    store: Store, policy: Policy, is_adr: bool, currency: str
) -> None:
    """A Russian filer: no tax rate on file (Russia is not in the OECD series). The refusal holds
    for an ADR and for a company in another currency as for a U.S. filer, and comes before the
    currency's own refusals (spec 2026-11-10 7.5): RUB has no rate on file."""
    annual = [{**row, "reportedCurrency": currency} for row in income_annual(YEARS)]
    profiles = [{"symbol": "ACME", "isAdr": is_adr, "marketCap": 5_000 * M}]
    conn = store(company=False, profile=profiles, **{**bodies(), "income-annual": annual})
    add_company(conn, country="RU")
    inputs = build(conn)
    assert (inputs.is_adr, inputs.currency) == (is_adr, currency)
    assert inputs.refusal == "no statutory tax rate for RU 2015"
    assert inputs.tax_rate_latest is None and {y.tax_rate for y in inputs.capital_years} == {None}
    assert not inputs.currency_refused  # refused before the currency's step

    deciles = Deciles((-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3), (0.0,) * 9, 1, 1, 1)
    result = value_company(inputs, deciles, policy, TODAY)
    assert result.refusal == "no statutory tax rate for RU 2015"
    assert result.phase.phase is not None
    assert "currency" not in result.intermediates


def _sek_store(
    store: Store, clients: Clients, clock: Clock, policy: Policy, **payloads: Any
) -> sqlite3.Connection:
    """ACME with its statements in SEK, and ``payloads`` in place of its fixtures, and the pair
    USDSEK's closes fetched, as KRON's are in a full refresh: 7.8, 7.9, 8.1 and 8.2 at the four
    trailing quarter ends, 10.52 at the quote's date, 2026-10-30."""
    conn = store(**{**bodies(currency="SEK"), **payloads})
    fetch_rates(conn, clients.fmp, ("SEK",), policy, clock(), clients.secrets)
    return conn


def _pair_history(router: Router, code: str) -> None:
    """Serve the made-up USDSEK closes as the pair ``USD<code>``'s."""
    fixture = FIXTURES / "fmp" / "historical-price-eod-light.USDSEK.json"
    body = fixture.read_bytes().replace(b"USDSEK", f"USD{code}".encode())
    router.symbol_bodies[("fx-history", f"USD{code}")] = body


def test_a_company_in_another_currency_reads_its_rate_and_its_street_figures(
    store: Store, clients: Clients, clock: Clock, policy: Policy
) -> None:
    """Spec 2026-11-10 7.2: the rate is the close at the price date, the street actuals come in at
    their period ends' rates; the differential is the inflation table's, cited with its note; the
    price and the market cap stay the quote's, in USD. The engine reads no GuruFocus EPS (spec
    2026-11-19 7.1), so the inputs carry none."""
    consensus = {"estimates-quarter": estimates_quarter()}  # four NTM quarters, as KRON's
    inputs = build(_sek_store(store, clients, clock, policy, **consensus))
    table = load_inflation_table()
    assert inputs.refusal is None and inputs.currency == "SEK"
    assert (inputs.fx_rate, inputs.fx_date, inputs.fx_stale) == (10.52, date(2026, 10, 30), False)
    assert (inputs.price, inputs.market_cap) == (50.0, 5_000 * M)
    assert inputs.street_ttm_eps == pytest.approx(
        0.51 * 7.8 + 0.52 * 7.9 + 0.53 * 8.1 + 0.54 * 8.2  # 16.807
    )
    assert inputs.inflation_differential == pytest.approx(table.differential("SEK"))
    assert inputs.provenance["fx_rate"] == Provenance(
        "FMP historical-price-eod/light USDSEK", date(2026, 10, 30), NOW, None
    )
    assert inputs.provenance["inflation_differential"] == Provenance(
        table.source, date(2026, 11, 10), None, None
    )
    assert inputs.notes["inflation_differential"] == (
        "SEK 2.120% against USD 2.120%, the IMF World Economic Outlook October 2026 means of 2027 "
        "to 2031"
    )
    assert "currency-unknown" not in codes(inputs)
    result = value_company(inputs, DECILES, policy, TODAY)
    assert result.refusal is None and result.value is not None
    assert result.intermediates["value_in_currency"] == pytest.approx(result.value * 10.52)


def test_a_rate_a_pair_quote_supplied_names_the_quote(
    store: Store, clients: Clients, clock: Clock, policy: Policy
) -> None:
    """A price refresh stored USDSEK's quote of the price date, 2026-10-30, at 10.60: it wins over
    the history's 10.52 of that day, and the rate's input names the quote, FMP's ``quote`` of the
    pair, as of its date; a close the history supplied names the history (the test above)."""
    conn = _sek_store(store, clients, clock, policy)
    day = date(2026, 10, 30)
    payload = [{"symbol": "USDSEK", "price": 10.6, "timestamp": 1793390400}]
    response = record_response(
        conn, "fmp", FX_QUOTE, {"symbol": "USDSEK"}, "USDSEK", 200, json.dumps(payload), None, NOW
    )
    insert_observations(conn, fx_quote_observations(payload, "USDSEK", response, NOW, NOW))
    inputs = build(conn)
    assert (inputs.fx_rate, inputs.fx_date) == (10.6, day)
    assert inputs.provenance["fx_rate"] == Provenance("FMP quote USDSEK", day, NOW, None)


def test_a_rate_older_than_the_bound_is_stale(
    store: Store, clients: Clients, clock: Clock, policy: Policy
) -> None:
    """The quote of 2026-11-20 reads the newest close, 2026-11-05's, 15 days before it."""
    quote = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text())
    stamp = int(datetime(2026, 11, 20, 21, tzinfo=UTC).timestamp())
    conn = _sek_store(store, clients, clock, policy, quote=[{**quote[0], "timestamp": stamp}])
    inputs = build(conn)
    assert (inputs.fx_rate, inputs.fx_date, inputs.fx_stale) == (10.6, date(2026, 11, 5), True)
    assert inputs.price_date == date(2026, 11, 20)


def test_a_period_end_with_no_rate_leaves_the_street_figures_unknown(
    store: Store, clients: Clients, clock: Clock, router: Router, policy: Policy
) -> None:
    """A history that starts after the oldest trailing quarter's end: the street actuals have no
    rate there, so they are unknown, never a refusal."""
    fixture = FIXTURES / "fmp" / "historical-price-eod-light.USDSEK.json"
    rows = [r for r in json.loads(fixture.read_text()) if r["date"] >= "2026-01-01"]
    router.symbol_bodies[("fx-history", "USDSEK")] = json.dumps(rows).encode()
    inputs = build(_sek_store(store, clients, clock, policy))
    assert inputs.refusal is None and inputs.fx_rate == 10.52
    assert inputs.street_ttm_eps is None
    assert "street_ttm_eps" not in inputs.provenance


@pytest.mark.parametrize(
    ("code", "history", "refusal"),
    [
        ("SEK", False, "no exchange rate for SEK"),
        ("XXX", False, "no exchange rate for XXX"),  # the rate first, then the projection
        ("XXX", True, "no inflation projection for XXX"),
        ("ARS", True, "ARS: expected inflation 12.1% above the 10% bound"),
    ],
)
def test_a_currency_the_method_cannot_price_is_refused(
    store: Store,
    clients: Clients,
    clock: Clock,
    router: Router,
    policy: Policy,
    code: str,
    history: bool,
    refusal: str,
) -> None:
    """Spec 2026-11-10 7.5: no rate on file, then no inflation projection, then a projection above
    the bound, each refuses the row with its sentence after the statements' and the tax rate's."""
    if history:
        _pair_history(router, code)
        conn = store(**bodies(currency=code))
        fetch_rates(conn, clients.fmp, (code,), policy, clock(), clients.secrets)
    else:
        conn = store(**bodies(currency=code))
    inputs = build(conn)
    assert inputs.refusal == refusal
    assert (inputs.fx_rate, inputs.fx_date) == (1.0, None)
    # the refusal is the currency's own, its code known: the engine names the code alone
    assert inputs.currency_refused and inputs.currency == code


def test_no_statements_comes_before_an_unknown_currency(store: Store, router: Router) -> None:
    """Without statements the universe row names no currency either: the statements' refusal is
    the one given (spec 2026-11-10 7.5), not one of the currency's."""
    router.fail.add("income-annual")
    conn = store(company=False)
    add_company(conn, currency=None)
    inputs = build(conn)
    assert inputs.refusal == "no financial statements" and not inputs.currency_refused


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
    assert p["balance_sheet"] == Provenance(SHEET_SOURCE, date(2026, 9, 30), NOW, NOW)
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
    assert inputs.moat_score == 7.0
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
    """One answer holds two rows for one fiscal period, their period ends a day apart. The row kept
    has the larger EPS analyst count, the earlier end's when it has it, and a count beats none; a
    period with one row keeps it; the rows stay in period-end order."""
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


def test_the_consensus_is_one_answer_s_rows(store: Store, clock: Clock) -> None:
    """FMP moved the period ends by a day between two answers. The older answer's rows have
    more analysts; they are not read, and a far year only the older answer held is not
    revived."""
    _on_a_september_year(
        store,
        quarters=[
            {"date": "2026-12-27", "epsAvg": 2.9, "numAnalystsEps": 13},
            {"date": "2027-03-27", "epsAvg": 2.2, "numAnalystsEps": 10},
        ],
        years=[
            {"date": "2027-09-27", "epsAvg": 9.5, "numAnalystsEps": 30},
            {"date": "2028-09-27", "epsAvg": 10.6, "numAnalystsEps": 22},
        ],
    )
    clock.now += timedelta(days=2)  # past the reuse window: the next fetch asks FMP again
    newer = {
        "estimates-quarter": [
            {"date": "2026-12-26", "epsAvg": 2.8, "numAnalystsEps": 6},
            {"date": "2027-03-26", "epsAvg": 2.1, "numAnalystsEps": 6},
        ],
        "estimates-annual": [{"date": "2027-09-26", "epsAvg": 9.4, "numAnalystsEps": 28}],
    }
    conn = store(company=False, **newer)  # the statements' bodies stay as the first call set them
    inputs = build(conn)
    assert [(q.period_end, q.eps, q.analysts) for q in inputs.quarter_estimates] == [
        (date(2026, 12, 26), 2.8, 6),
        (date(2027, 3, 26), 2.1, 6),
    ]
    assert [(a.period_end, a.eps, a.analysts_eps) for a in inputs.annual_estimates] == [
        (date(2027, 9, 26), 9.4, 28)
    ]


def test_an_empty_answer_leaves_the_earlier_answer_read(store: Store, clock: Clock) -> None:
    """FMP answers both consensus calls with an empty list once. The empty answers are stored as
    errors with no rows, so the earlier answer's rows are still read, and the consensus is cited
    as of the earlier answer's date, not the later fetch's."""
    _on_a_september_year(
        store,
        quarters=[
            {"date": "2026-12-27", "epsAvg": 2.9, "numAnalystsEps": 13},
            {"date": "2027-03-27", "epsAvg": 2.2, "numAnalystsEps": 10},
        ],
        years=[{"date": "2027-09-27", "epsAvg": 9.5, "numAnalystsEps": 30}],
    )
    first = clock.now.date()
    clock.now += timedelta(days=2)  # past the reuse window: the next fetch asks FMP again
    conn = store(company=False, **{"estimates-quarter": [], "estimates-annual": []})
    for endpoint in ("estimates-quarter", "estimates-annual"):
        stored = conn.execute(
            "SELECT error FROM vendor_responses WHERE endpoint = ? ORDER BY id", (endpoint,)
        ).fetchall()
        assert [row["error"] is None for row in stored] == [True, False], endpoint
    inputs = build(conn)
    assert [(q.period_end, q.eps, q.analysts) for q in inputs.quarter_estimates] == [
        (date(2026, 12, 27), 2.9, 13),
        (date(2027, 3, 27), 2.2, 10),
    ]
    assert [(a.period_end, a.eps, a.analysts_eps) for a in inputs.annual_estimates] == [
        (date(2027, 9, 27), 9.5, 30)
    ]
    assert inputs.provenance["estimates_quarter"].as_of == first
    assert inputs.provenance["estimates_annual"].as_of == first


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


def test_quarters_that_share_a_calendar_label_are_kept_apart(store: Store) -> None:
    """A December fiscal year whose quarters end a month later, as after a change of fiscal year:
    the calendar labels the quarters ending 2027-01-31 and 2027-04-30 both FY2027 Q1, yet they are
    two quarters, and the NTM chain holds on all four. A duplicate a day apart, and one a week
    apart, still collapse to the row with more analysts; the labels stay on the kept rows."""
    ends = (date(2025, 7, 31), date(2025, 10, 31), date(2026, 1, 31), date(2026, 4, 30))
    redated = {
        endpoint: [
            {**row, "date": str(end)}
            for row, end in zip(rows, (*ends, date(2026, 7, 31)), strict=True)
        ]
        for endpoint, rows in (
            ("income-quarter", income_quarter(QUARTERS)),
            ("cashflow-quarter", cashflow_quarter(QUARTERS)),
        )
    }
    quarters = [
        {"date": "2026-10-31", "epsAvg": 0.5, "numAnalystsEps": 12},
        {"date": "2027-01-30", "epsAvg": 0.1, "numAnalystsEps": 3},  # a day before
        {"date": "2027-01-31", "epsAvg": 0.6, "numAnalystsEps": 12},
        {"date": "2027-04-23", "epsAvg": 0.1, "numAnalystsEps": 3},  # a week before
        {"date": "2027-04-30", "epsAvg": 0.7, "numAnalystsEps": 11},
        {"date": "2027-07-31", "epsAvg": 0.8, "numAnalystsEps": 10},
    ]
    inputs = build(store(**{**bodies(), **redated, "estimates-quarter": quarters}))
    assert inputs.trailing is not None and not inputs.trailing.on_fiscal_year
    assert inputs.trailing.period_end == date(2026, 7, 31)
    assert inputs.quarter_estimates == (
        QuarterEstimate(date(2026, 10, 31), 2026, "Q3", 0.5, None, None, 12),
        QuarterEstimate(date(2027, 1, 31), 2027, "Q1", 0.6, None, None, 12),
        QuarterEstimate(date(2027, 4, 30), 2027, "Q1", 0.7, None, None, 11),
        QuarterEstimate(date(2027, 7, 31), 2027, "Q2", 0.8, None, None, 10),
    )
    ntm = ntm_quarters(inputs.quarter_estimates, inputs.trailing.period_end)
    assert ntm == inputs.quarter_estimates


def test_the_reported_quarter_s_duplicate_is_not_an_ntm_quarter(store: Store) -> None:
    """The quarter just reported, ending 2026-09-30 in the statements, comes twice in the
    consensus, and the row kept is the one ending a day after the trailing period end.
    The NTM quarters skip it: the first ends 80 to 100 days after the trailing period end, and
    the golden's arithmetic values Mature Growth Co from the four after it."""
    mgco = mature_growth_inputs()
    reported = [
        {"date": "2026-09-30", "epsAvg": 1.30, "numAnalystsEps": 8},
        {"date": "2026-10-01", "epsAvg": 1.35, "numAnalystsEps": 25},
    ]
    ahead = [
        {"date": str(x.period_end), "epsAvg": x.eps, "numAnalystsEps": x.analysts}
        for x in mgco.quarter_estimates
    ]
    inputs = build(store(**{**bodies(), "estimates-quarter": reported + ahead}))
    assert inputs.trailing is not None and inputs.trailing.period_end == date(2026, 9, 30)
    assert inputs.quarter_estimates[0].period_end == date(2026, 10, 1)  # the duplicate kept
    ntm = ntm_quarters(inputs.quarter_estimates, inputs.trailing.period_end)
    assert ntm == mgco.quarter_estimates
    assert 80 <= (ntm[0].period_end - inputs.trailing.period_end).days <= 100
    stored = replace(mgco, quarter_estimates=inputs.quarter_estimates)
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
    # no currency from the statements or the universe row: the refusal, no note
    assert inputs.currency == "unknown" and "currency-unknown" not in codes(inputs)
    assert inputs.refusal == "reporting currency unknown"
    assert not inputs.currency_refused  # no code to name
    assert inputs.closes == () and "closes" not in inputs.provenance
    assert "price" not in inputs.provenance


def test_no_financial_statements_is_a_refusal(store: Store, router: Router) -> None:
    router.fail.add("income-annual")
    conn = store()
    assert series_for(conn, "ACME") == ()
    inputs = build(conn)
    assert inputs.refusal == "no financial statements"
    assert (inputs.series, inputs.capital_years, inputs.trailing) == ((), (), None)
    assert inputs.balance_years == () and inputs.stock_pay is None
    assert inputs.data_date == TODAY
    assert inputs.price == 50.0  # the market side is still read


def test_inputs_carry_peers_debt_cash_and_the_revenue_analysts(
    store: Store, clients: Clients, clock: Clock, policy: Policy
) -> None:
    """Debt and cash from ACME's newest balance sheet, the quarter's of 2026-09-30. BOLT, fetched
    and listed, is ACME's mature peer once there are deciles."""
    conn = store(company=False, **bodies())
    fetch_company(conn, clients.fmp, clients.gf, "BOLT", policy, clock(), clients.secrets)
    add_company(conn, symbols=("ACME", "BOLT"))  # one universe
    tax = load_tax_table()
    i = build_inputs(conn, "ACME", policy, tax, TODAY, DECILES)
    [newest] = balance_quarter([date(2026, 9, 30)])
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
    names the missing lines. The newest sheet is the quarter's of 2026-09-30, whose short-term
    debt is $35 m. The secondary valuation reads the two figures the same way."""
    payloads = bodies()
    payloads["balance-quarter"][-1] |= {
        "longTermDebt": None,
        "cashAndCashEquivalents": None,
        "shortTermInvestments": None,
    }
    conn = store(**payloads)
    inputs = build(conn)
    # neither the older quarters' lines nor the annual sheet's are read
    assert (inputs.debt, inputs.cash) == (35 * M, None)
    assert newest_debt_and_cash(conn, "ACME") == (35 * M, None)
    assert newest_debt_and_cash(conn, "BOLT") == (None, None)  # no balance sheet on file
    assert inputs.notes["debt"] == "longTermDebt not presented"
    assert inputs.notes["cash"] == "cashAndCashEquivalents and shortTermInvestments not presented"


def test_the_newest_sheet_is_the_quarter_s_when_it_ends_later(store: Store) -> None:
    """Spec 2026-11-13 12.2: the annual sheet ends with fiscal 2025 and the newest quarterly sheet
    two quarters later, on 2026-06-30 (fiscal 2026 Q2: cash $220 m and short-term investments
    $40 m, short-term debt $30 m and long-term debt $280 m). The quarter's sheet is read, cited
    as of its own period end."""
    sheets = balance_quarter(q for q in QUARTERS if q <= date(2026, 6, 30))
    inputs = build(store(**{**bodies(), "balance-quarter": sheets}))
    assert inputs.sheet == NewestSheet(
        date(2026, 6, 30),
        "fiscal 2026 Q2",
        True,
        716 * M,
        820 * M,
        None,
        figures=Q2_FIGURES,
        annual=FY2025_FIGURES,
    )
    assert (inputs.debt, inputs.cash) == (310 * M, 260 * M)
    assert inputs.provenance["balance_sheet"] == Provenance(
        SHEET_SOURCE, date(2026, 6, 30), NOW, NOW
    )
    assert "debt" not in inputs.notes and "cash" not in inputs.notes


def test_a_tie_reads_the_annual_sheet(store: Store) -> None:
    """Spec 2026-11-13 12.2: the newest quarterly sheet ends on the annual sheet's day,
    2025-12-31, with other figures: the annual sheet is read, debt $320 m and cash $250 m."""
    [q3, q4] = balance_quarter([date(2025, 9, 30), date(2025, 12, 31)])
    other = q4 | {"shortTermDebt": 90 * M, "cashAndCashEquivalents": 90 * M}
    inputs = build(store(**{**bodies(), "balance-quarter": [q3, other]}))
    assert inputs.sheet == FY2025
    assert (inputs.debt, inputs.cash) == (320 * M, 250 * M)
    assert inputs.provenance["balance_sheet"].as_of == date(2025, 12, 31)


def test_no_quarterly_sheet_reads_the_annual_one(store: Store) -> None:
    """The quarterly call answered nothing: the annual sheet of fiscal 2025 is read, as before
    method 1.4."""
    inputs = build(store(**{**bodies(), "balance-quarter": []}))
    assert inputs.sheet == FY2025
    assert (inputs.debt, inputs.cash) == (320 * M, 250 * M)
    assert inputs.provenance["balance_sheet"] == Provenance(
        SHEET_SOURCE, date(2025, 12, 31), NOW, NOW
    )


@pytest.mark.parametrize(
    ("currencies", "end", "label", "debt", "cash"),
    [
        ({date(2026, 9, 30): "EUR"}, date(2026, 6, 30), "fiscal 2026 Q2", 310 * M, 260 * M),
        ({q: "EUR" for q in QUARTERS[1:]}, date(2025, 12, 31), "fiscal 2025", 320 * M, 250 * M),
        ({date(2026, 9, 30): None}, date(2026, 9, 30), "fiscal 2026 Q3", 305 * M, 265 * M),
    ],
    ids=["the-next-quarter", "the-annual-sheet", "no-currency"],
)
def test_a_quarterly_sheet_in_another_currency_is_skipped(
    store: Store,
    currencies: dict[date, str | None],
    end: date,
    label: str,
    debt: float,
    cash: float,
) -> None:
    """Spec 2026-11-13 12.2: beside statements in USD, a quarterly sheet in EUR is skipped. With
    the newest in EUR, the quarter before it is read, ending after the annual sheet; with every
    quarter from 2025-12-31 in EUR, the one left, 2025-09-30, ends before the annual sheet, which
    is read. A sheet with no currency counts as the reporting currency's."""
    sheets = balance_quarter(QUARTERS)
    for row in sheets:
        day = date.fromisoformat(row["date"])
        if day in currencies:
            row["reportedCurrency"] = currencies[day]
    inputs = build(store(**{**bodies(), "balance-quarter": sheets}))
    sheet = inputs.sheet
    assert sheet is not None and (sheet.period_end, sheet.label) == (end, label)
    assert sheet.quarterly == (end > date(2025, 12, 31))  # a quarter's when after the annual's
    assert (inputs.debt, inputs.cash) == (debt, cash)
    assert inputs.provenance["balance_sheet"].as_of == end


def test_the_newest_sheet_is_read_whole(store: Store) -> None:
    """Review Focus (spec 2026-11-13 12.2): the newest quarter lacks ``shortTermInvestments`` and
    holds no ``longTermDebt``, both of which the annual sheet presents. No line falls back to the
    annual sheet: cash is the quarter's cash and equivalents alone, $230 m, debt its short-term
    debt alone, $35 m, and the notes name the missing lines."""
    payloads = bodies()
    newest = payloads["balance-quarter"][-1]
    del newest["shortTermInvestments"]
    newest["longTermDebt"] = None
    annual = payloads["balance-annual"][-1]
    assert annual["shortTermInvestments"] and annual["longTermDebt"]  # the annual presents both
    inputs = build(store(**payloads))
    assert inputs.sheet is not None and inputs.sheet.period_end == date(2026, 9, 30)
    assert (inputs.debt, inputs.cash) == (35 * M, 230 * M)
    assert inputs.notes["debt"] == "longTermDebt not presented"
    assert inputs.notes["cash"] == "shortTermInvestments not presented"


def test_a_half_year_sheet_is_read_as_a_quarter_s(store: Store) -> None:
    """Review Focus (spec 2026-11-13 12.2): a half-yearly reporter's sheets by quarter are its
    half-years, which FMP labels Q2 and Q4. The newest, 2026-06-30, is read under its row's own
    label, "fiscal 2026 Q2": debt $30 m + $280 m, cash $220 m + $40 m."""
    inputs = build(store(**bodies(cadence="half-yearly")))
    assert inputs.sheet == NewestSheet(
        date(2026, 6, 30),
        "fiscal 2026 Q2",
        True,
        716 * M,
        820 * M,
        None,
        figures=Q2_FIGURES,
        annual=FY2025_FIGURES,
    )
    assert (inputs.debt, inputs.cash) == (310 * M, 260 * M)


def test_the_sheets_hand_the_engine_their_five_lines(store: Store) -> None:
    """Spec 2026-11-13 12.5: the newest quarter, fiscal 2026 Q3, ends after the annual sheet of
    fiscal 2025, so the sheet in use holds the quarter's five lines (short-term debt $35 m,
    long-term debt $270 m, cash $230 m, short-term investments $35 m, a minority interest of
    $90 m) and the annual sheet's stand beside them ($20 m, $300 m, $200 m, $50 m and $4 m), each
    as its sheet presents it."""
    payloads = bodies()
    payloads["balance-quarter"][-1]["minorityInterest"] = 90 * M
    payloads["balance-annual"][-1]["minorityInterest"] = 4 * M
    sheet = build(store(**payloads)).sheet
    assert sheet is not None and (sheet.label, sheet.minority_interest) == (
        "fiscal 2026 Q3",
        90 * M,
    )
    assert sheet.figures == SheetFigures("fiscal 2026 Q3", 35 * M, 270 * M, 230 * M, 35 * M, 90 * M)
    assert sheet.annual == replace(FY2025_FIGURES, minority_interest=4 * M)


@pytest.mark.parametrize("tie", [False, True], ids=["no-quarterly-sheet", "a-tie"])
def test_the_annual_sheet_in_use_stands_alone(store: Store, tie: bool) -> None:
    """Spec 2026-11-13 12.5: with no quarterly sheet, or a quarterly sheet that ends on the annual
    sheet's day with other figures, the annual sheet is in use: its five lines are the figures,
    under its label, and no annual sheet stands beside them, so the note sheet-shift has nothing
    to compare."""
    [q3, q4] = balance_quarter([date(2025, 9, 30), date(2025, 12, 31)])
    quarters = [q3, q4 | {"shortTermDebt": 90 * M}] if tie else []
    sheet = build(store(**{**bodies(), "balance-quarter": quarters})).sheet
    assert sheet is not None and not sheet.quarterly
    assert (sheet.figures, sheet.annual) == (FY2025_FIGURES, None)


@pytest.mark.parametrize(
    ("labels", "label"),
    [
        ({"fiscalYear": "2027", "period": "Q2"}, "fiscal 2027 Q2"),
        ({"fiscalYear": None}, "the period ending 30 Sep 2026"),
        ({"period": None}, "the period ending 30 Sep 2026"),
    ],
    ids=["the-row-s-labels", "no-fiscal-year", "no-fiscal-period"],
)
def test_the_sheet_s_label_is_its_row_s_own(
    store: Store, labels: dict[str, str | None], label: str
) -> None:
    """The label reads the row's own fiscal year and period, as FMP labels the quarter to 30
    September after a March year end with the next fiscal year's Q2; a row with no fiscal year, or
    no fiscal period, names its period end."""
    payloads = bodies()
    payloads["balance-quarter"][-1] |= labels
    sheet = build(store(**payloads)).sheet
    assert sheet is not None and (sheet.period_end, sheet.label) == (date(2026, 9, 30), label)


def test_the_quarterly_sheet_moves_no_fiscal_year_figure(
    store: Store, router: Router, clock: Clock
) -> None:
    """Spec 2026-11-13 12.2 and its decision of 2026-11-14: the quarterly call fails on the first
    fetch and answers on a second 20 hours later, on the next day, so only the quarterly sheet is
    observed then. It is read, cited at its own observation, and the capital years, the balance
    years, the data date and the ``statements`` input are what they were without it."""
    router.fail.add("balance-quarter")
    router.fail_status = 404  # not retried
    without = build(store(**bodies()))
    router.fail.clear()
    clock.now += timedelta(hours=20)  # 2026-11-02, inside the reuse window of the other calls
    later = clock()
    with_sheet = build(store(company=False))
    assert without.sheet == FY2025
    assert with_sheet.sheet is not None and with_sheet.sheet.quarterly
    assert with_sheet.provenance["balance_sheet"] == Provenance(
        SHEET_SOURCE, date(2026, 9, 30), later, later
    )
    assert with_sheet.capital_years == without.capital_years
    assert with_sheet.balance_years == without.balance_years
    assert with_sheet.data_date == without.data_date == NOW.date()
    assert with_sheet.provenance["statements"] == without.provenance["statements"]


def _summary(ratio: str | None) -> dict[str, Any]:
    """The ACME GuruFocus summary with its depositary receipt ratio set to ``ratio``."""
    body: dict[str, Any] = json.loads((FIXTURES / "gurufocus" / "summary.ACME.json").read_text())
    body["summary"]["company_data"]["depositary_receipt_ratio"] = ratio
    return body


def _quote(count: float) -> list[dict[str, Any]]:
    """The ACME quote at its price of $50 with a market cap of $50 × ``count``."""
    (row,) = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text())
    return [{**row, "marketCap": row["price"] * count}]


def _profile(is_adr: bool) -> list[dict[str, Any]]:
    """The ACME profile with FMP's ADR flag set to ``is_adr``."""
    (row,) = json.loads((FIXTURES / "fmp" / "profile.ACME.json").read_text())
    return [{**row, "isAdr": is_adr}]


def test_assembly_finds_the_ratio_of_a_flagged_adr(store: Store) -> None:
    """Spec 2026-11-19 6.2: ACME flagged as an ADR, its statements at 104 m shares and a quote whose
    count is 1,040 m, and a stored GuruFocus ratio of 5, which is not read: the counts give 10, an
    estimate under ``counts-ratio`` cited to the quote, and the count reads × 10."""
    conn = store(**bodies(), profile=_profile(True), summary=_summary("5"), quote=_quote(1040 * M))
    inputs = build(conn)
    assert inputs.adr_ratio == 10.0
    assert inputs.estimate_methods["adr_ratio"] == "counts-ratio"
    assert inputs.provenance["adr_ratio"].source == inputs.provenance["price"].source
    assert inputs.provenance["adr_ratio"] == Provenance("FMP quote", date(2026, 10, 30), NOW, NOW)
    assert inputs.notes["adr_ratio"] == (
        "the whole number that brings the stored count, 104.0 m, to the quote's, 1,040.0 m"
    )
    assert inputs.shares_diluted == pytest.approx(1040 * M)
    assert inputs.refusal is None


def test_an_adr_reads_its_counts_on_the_quotes_share_basis(store: Store) -> None:
    """ACME flagged as an ADR, with a quote at a tenth of its count (10.4 m against 104 m): the
    counts give ρ 10, and each quarter's count, 101 m to 104 m, fits the newest's on the quote's
    basis only × 1 ÷ 10, so the count reads ÷ 10 and the trailing EPS × 10; the street actuals
    stand."""
    conn = store(**bodies(), profile=_profile(True), quote=_quote(10.4 * M))
    inputs = build(conn)
    assert inputs.adr_ratio == 10.0
    assert inputs.provenance["adr_ratio"] == Provenance("FMP quote", date(2026, 10, 30), NOW, NOW)
    assert inputs.refusal is None
    assert inputs.shares_diluted == pytest.approx(10.4 * M)
    assert inputs.trailing is not None and inputs.trailing.eps_diluted == pytest.approx(19.0)
    assert inputs.street_ttm_eps == pytest.approx(2.10)
    assert {k: v for k, v in inputs.estimate_methods.items() if v == "basis-scaled"} == {
        "shares_diluted": "basis-scaled",
        "eps_ttm": "basis-scaled",
    }
    assert inputs.notes["eps_ttm"] == "×10 to the quote's share basis (the ratio 10)"
    assert codes(inputs)[-1] == "basis-scaled"


def test_assembly_reads_no_ratio_where_the_counts_agree(store: Store) -> None:
    """A flagged ADR whose counts agree with the quote's (104 m against 100 m), with a GuruFocus
    ratio of 5 on file: no ratio, and the counts read as stored."""
    conn = store(**bodies(), profile=_profile(True), summary=_summary("5"))
    inputs = build(conn)
    assert inputs.is_adr is True
    assert inputs.adr_ratio is None and "adr_ratio" not in inputs.provenance
    assert "adr_ratio" not in inputs.notes and "adr_ratio" not in inputs.estimate_methods
    assert inputs.shares_diluted == 104 * M and inputs.refusal is None
    assert "basis-scaled" not in codes(inputs)


@pytest.mark.parametrize("ratio", ["10", "0", None], ids=["ratio", "zero", "absent"])
def test_a_row_without_the_adr_flag_reads_no_ratio(store: Store, ratio: str | None) -> None:
    """ACME as FMP profiles it, no ADR, with a quote at a tenth of its count: whatever ratio
    GuruFocus holds, the rule does not run, and the counts read as stored."""
    conn = store(**bodies(), summary=_summary(ratio), quote=_quote(10.4 * M))
    inputs = build(conn)
    assert inputs.adr_ratio is None and "adr_ratio" not in inputs.provenance
    assert inputs.shares_diluted == 104 * M and inputs.refusal is None
    assert "basis-scaled" not in codes(inputs)
    assert "basis-scaled" not in inputs.estimate_methods.values()


def test_the_tax_refusal_comes_before_the_basis_refusal(store: Store) -> None:
    """A flagged ADR whose quote's count is 78 m against the statements' 104 m, a multiple of 0.75
    that no whole number explains: refused for the basis; with a tax table that lacks a year,
    refused for the tax rate first (spec 2026-11-10 7.5)."""
    conn = store(**bodies(), profile=_profile(True), quote=_quote(78 * M))
    refusal = "share basis unclear: the newest period's count 104.0 m against the quote's 78.0 m"
    assert build(conn).refusal == refusal
    assert build(conn).adr_ratio is None
    from_2017 = {("United States", y): 0.25 for y in range(2017, 2027)}
    late = TaxTable(from_2017, "t", {"US": "United States"})
    assert build(conn, late).refusal == "no statutory tax rate for US 2015"
    assert build(conn, late).shares_diluted == 104 * M
