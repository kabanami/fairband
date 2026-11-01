"""The FMP normalizer against the synthetic fixtures in ``tests/fixtures/fmp``.

ACME's fiscal years end in December; BOLT's end in June, and its normalized balance sheet reads
zero goodwill and intangibles while its as-reported balance sheet presents neither line.
"""

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fairband.store.facts import FactRow
from fairband.store.observations import ObservationRow
from fairband.vendors.normalize_fmp import (
    ScreenerRow,
    as_reported_balance_facts,
    earnings_observations,
    estimate_observations,
    price_closes,
    profile_country,
    profile_observations,
    quote_observations,
    screener_rows,
    statement_facts,
    value_as_date,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "fmp"
OBSERVED = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
ENTERED = datetime(2026, 11, 1, 9, 31, tzinfo=UTC)
TODAY = date(2026, 11, 1)
RID = 7


def load(name: str) -> Any:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def facts(name: str, symbol: str, dataset: str) -> list[FactRow]:
    return statement_facts(load(name), symbol, dataset, RID, OBSERVED, ENTERED)


def fact(rows: list[FactRow], period_end: str, field: str) -> FactRow:
    [row] = [r for r in rows if r.period_end == date.fromisoformat(period_end) and r.field == field]
    return row


def obs(rows: list[ObservationRow], dataset: str, period: str | None, field: str) -> ObservationRow:
    when = None if period is None else date.fromisoformat(period)
    [row] = [r for r in rows if r.dataset == dataset and r.period == when and r.field == field]
    return row


INCOME = {
    "revenue",
    "operatingIncome",
    "netIncome",
    "eps",
    "epsDiluted",
    "weightedAverageShsOutDil",
    "incomeTaxExpense",
    "incomeBeforeTax",
}
BALANCE = {
    "cashAndCashEquivalents",
    "shortTermInvestments",
    "totalCurrentAssets",
    "totalCurrentLiabilities",
    "shortTermDebt",
    "propertyPlantEquipmentNet",
    "goodwill",
    "intangibleAssets",
    "longTermDebt",
    "totalStockholdersEquity",
}
CASHFLOW = {
    "netCashProvidedByOperatingActivities",
    "netCashProvidedByInvestingActivities",
    "netCashProvidedByFinancingActivities",
    "capitalExpenditure",
    "stockBasedCompensation",
    "netDividendsPaid",
    "commonStockRepurchased",
    "commonStockIssuance",
}


def test_income_annual_facts() -> None:
    rows = facts("income-statement.annual.ACME", "ACME", "income-annual")
    assert len(rows) == 3 * 8
    assert {r.field for r in rows} == INCOME
    revenue = fact(rows, "2025-12-31", "revenue")
    assert revenue == FactRow(
        symbol="ACME",
        dataset="income-annual",
        period_end=date(2025, 12, 31),
        fiscal_year=2025,
        fiscal_period="FY",
        field="revenue",
        value=Decimal(1200000000),
        unit="currency",
        currency="USD",
        kind="observed",
        estimate_method=None,
        missing_reason=None,
        as_of=date(2025, 12, 31),
        observed_at=OBSERVED,
        entered_at=ENTERED,
        response_id=RID,
    )
    assert fact(rows, "2025-12-31", "epsDiluted").value == Decimal("1.8")
    assert fact(rows, "2025-12-31", "epsDiluted").unit == "per-share"
    assert fact(rows, "2025-12-31", "weightedAverageShsOutDil").unit == "shares"


def test_null_statement_field_recorded_absent() -> None:
    rows = facts("income-statement.annual.ACME", "ACME", "income-annual")
    tax = fact(rows, "2023-12-31", "incomeTaxExpense")
    assert (tax.value, tax.missing_reason, tax.kind) == (None, "null", "observed")
    # A field the row leaves out is recorded the same way.
    [row] = load("income-statement.annual.ACME")[:1]
    del row["netIncome"]
    rows = statement_facts([row], "ACME", "income-annual", RID, OBSERVED, ENTERED)
    missing = fact(rows, "2025-12-31", "netIncome")
    assert (missing.value, missing.missing_reason) == (None, "null")


def test_income_quarter_facts_carry_the_fiscal_labels() -> None:
    rows = facts("income-statement.quarter.BOLT", "BOLT", "income-quarter")
    assert len(rows) == 2 * 8
    first = fact(rows, "2026-09-30", "netIncome")
    assert (first.fiscal_year, first.fiscal_period, first.value) == (2027, "Q1", Decimal(123000000))
    assert first.dataset == "income-quarter"


def test_balance_annual_facts() -> None:
    rows = facts("balance-sheet-statement.annual.ACME", "ACME", "balance-annual")
    assert len(rows) == 3 * 10
    assert {r.field for r in rows} == BALANCE
    goodwill = fact(rows, "2024-12-31", "goodwill")
    assert (goodwill.value, goodwill.missing_reason) == (Decimal(250000000), None)
    assert fact(rows, "2023-12-31", "intangibleAssets").value == Decimal(300000000)


def test_vendor_zero_goodwill_becomes_not_presented() -> None:
    rows = facts("balance-sheet-statement.annual.BOLT", "BOLT", "balance-annual")
    assert len(rows) == 2 * 10
    for period_end in ("2026-06-30", "2025-06-30"):
        for field in ("goodwill", "intangibleAssets"):
            row = fact(rows, period_end, field)
            assert (row.value, row.missing_reason, row.kind) == (None, "vendor-zero", "observed")
    # Every other zero is a real zero.
    sti = fact(rows, "2026-06-30", "shortTermInvestments")
    assert (sti.value, sti.missing_reason) == (Decimal(0), None)
    debt = fact(rows, "2026-06-30", "shortTermDebt")
    assert (debt.value, debt.missing_reason) == (Decimal(0), None)


def test_cashflow_facts_keep_the_vendor_sign_and_real_zeros() -> None:
    annual = facts("cash-flow-statement.annual.ACME", "ACME", "cashflow-annual")
    assert len(annual) == 3 * 8
    assert {r.field for r in annual} == CASHFLOW
    assert fact(annual, "2025-12-31", "capitalExpenditure").value == Decimal(-90000000)
    issued = fact(annual, "2024-12-31", "commonStockIssuance")
    assert (issued.value, issued.missing_reason) == (Decimal(0), None)
    quarter = facts("cash-flow-statement.quarter.ACME", "ACME", "cashflow-quarter")
    assert len(quarter) == 3 * 8
    assert fact(quarter, "2026-06-30", "stockBasedCompensation").value == Decimal(6000000)
    assert fact(quarter, "2026-06-30", "stockBasedCompensation").fiscal_period == "Q2"


def test_unparseable_values_and_malformed_rows() -> None:
    bad_values = {"revenue": "n/a", "operatingIncome": "125.5", "netIncome": True, "eps": "NaN"}
    payload = [
        {"date": "2025-12-31", "fiscalYear": "2025", "period": "FY", **bad_values},
        {"fiscalYear": "2024", "revenue": 1},  # no date: skipped
        {"date": "not a date", "revenue": 1},  # unparseable date: skipped
        "not a row",
    ]
    rows = statement_facts(payload, "ACME", "income-annual", RID, OBSERVED, ENTERED)
    assert len(rows) == 8
    assert {r.period_end for r in rows} == {date(2025, 12, 31)}
    assert fact(rows, "2025-12-31", "revenue").missing_reason == "unparseable"
    assert fact(rows, "2025-12-31", "operatingIncome").value == Decimal("125.5")
    assert fact(rows, "2025-12-31", "netIncome").missing_reason == "unparseable"
    assert fact(rows, "2025-12-31", "eps").missing_reason == "unparseable"
    assert (
        statement_facts({"Error Message": "x"}, "ACME", "income-annual", RID, OBSERVED, ENTERED)
        == []
    )


def test_as_reported_balance_facts() -> None:
    rows = as_reported_balance_facts(
        load("balance-sheet-statement-as-reported.annual.ACME"), "ACME", RID, OBSERVED, ENTERED
    )
    assert len(rows) == 3 * 3
    assert {r.dataset for r in rows} == {"balance-asreported-annual"}
    intangibles = fact(rows, "2024-12-31", "intangibles_ex_goodwill")
    assert intangibles.value == Decimal(280000000)
    assert (intangibles.kind, intangibles.estimate_method) == (
        "estimate",
        "bs10-intangibles-total-v1",
    )
    assert (intangibles.fiscal_year, intangibles.fiscal_period, intangibles.currency) == (
        2024,
        "FY",
        "USD",
    )
    assert fact(rows, "2025-12-31", "intangibles_ex_goodwill").value == Decimal(260000000)
    rou = fact(rows, "2025-12-31", "lease_rou_asset")
    assert (rou.value, rou.kind, rou.unit) == (Decimal(90000000), "observed", "currency")
    assert fact(rows, "2023-12-31", "current_lease_liability").value == Decimal(13000000)


def test_as_reported_absent_tag_is_not_presented() -> None:
    rows = as_reported_balance_facts(
        load("balance-sheet-statement-as-reported.annual.BOLT"), "BOLT", RID, OBSERVED, ENTERED
    )
    assert len(rows) == 2 * 3
    for period_end in ("2026-06-30", "2025-06-30"):
        row = fact(rows, period_end, "intangibles_ex_goodwill")
        assert (row.value, row.missing_reason) == (None, "not-presented")
        assert (row.kind, row.estimate_method) == ("observed", None)
    assert fact(rows, "2026-06-30", "lease_rou_asset").value == Decimal(120000000)
    assert fact(rows, "2025-06-30", "lease_rou_asset").missing_reason == "not-presented"
    assert fact(rows, "2025-06-30", "current_lease_liability").missing_reason == "not-presented"


def test_as_reported_tag_search_order() -> None:
    tags = {
        "intangibleassetsnetexcludinggoodwill": 1,
        "finitelivedintangibleassetsnet": 2,
        "otherintangibleassetsnet": 3,
    }

    def picked(data: dict[str, Any], nested: bool = True) -> Decimal | None:
        row: dict[str, Any] = {"date": "2025-12-31", "fiscalYear": 2025, "period": "FY"}
        row.update({"data": data} if nested else data)
        rows = as_reported_balance_facts([row], "ACME", RID, OBSERVED, ENTERED)
        return fact(rows, "2025-12-31", "intangibles_ex_goodwill").value

    assert picked(tags) == Decimal(1)
    assert picked({**tags, "intangibleassetsnetexcludinggoodwill": None}) == Decimal(2)
    assert picked({"otherintangibleassetsnet": 3, "finitelivedintangibleassetsnet": 2}) == 2
    assert picked({"otherintangibleassetsnet": 3}) == Decimal(3)
    assert picked(tags, nested=False) == Decimal(1)  # a flat row reads the same tags


def test_estimate_observations_annual() -> None:
    rows = estimate_observations(
        load("analyst-estimates.annual.ACME"), "ACME", "annual", RID, OBSERVED, ENTERED
    )
    assert len(rows) == 3 * 8
    assert {r.dataset for r in rows} == {"estimate-annual"}
    eps = obs(rows, "estimate-annual", "2027-12-31", "eps_avg")
    assert eps == ObservationRow(
        symbol="ACME",
        dataset="estimate-annual",
        period=date(2027, 12, 31),
        field="eps_avg",
        value=Decimal("2.2"),
        unit="per-share",
        as_of=OBSERVED.date(),
        observed_at=OBSERVED,
        entered_at=ENTERED,
        response_id=RID,
    )
    assert obs(rows, "estimate-annual", "2027-12-31", "net_income_avg").value == 220000000
    assert obs(rows, "estimate-annual", "2027-12-31", "analysts_revenue").value == 14
    # FMP has no net-income analyst count; the EPS count stands in for it.
    ni_count = obs(rows, "estimate-annual", "2027-12-31", "analysts_net_income")
    assert (ni_count.value, ni_count.unit) == (Decimal(12), "count")
    # The stable route's rows carry no fiscal year or period.
    assert obs(rows, "estimate-annual", "2027-12-31", "fiscal_year").value is None
    assert obs(rows, "estimate-annual", "2027-12-31", "fiscal_period").value is None


def test_estimate_observations_quarter_keep_every_row() -> None:
    rows = estimate_observations(
        load("analyst-estimates.quarter.ACME"), "ACME", "quarter", RID, OBSERVED, ENTERED
    )
    assert len(rows) == 3 * 8
    periods = sorted({r.period for r in rows if r.period is not None})
    assert periods == [date(2026, 12, 31), date(2027, 3, 31), date(2027, 6, 30)]
    assert obs(rows, "estimate-quarter", "2027-03-31", "eps_avg").value == Decimal("0.54")
    labelled = [{"date": "2026-12-31", "epsAvg": 1, "fiscalYear": 2027, "fiscalPeriod": "Q2"}]
    rows = estimate_observations(labelled, "ACME", "quarter", RID, OBSERVED, ENTERED)
    assert obs(rows, "estimate-quarter", "2026-12-31", "fiscal_year").value == 2027
    assert obs(rows, "estimate-quarter", "2026-12-31", "fiscal_period").value == 2


def test_earnings_observations() -> None:
    rows = earnings_observations(load("earnings.ACME"), "ACME", RID, OBSERVED, ENTERED, TODAY)
    actuals = [r for r in rows if r.dataset == "street-actual"]
    assert len(actuals) == 2
    q3 = obs(rows, "street-actual", "2026-09-30", "eps_actual")
    assert (q3.value, q3.unit, q3.as_of) == (Decimal("0.51"), "per-share", date(2026, 10, 30))
    [nxt] = [r for r in rows if r.dataset == "earnings-date"]
    assert (nxt.field, nxt.period, nxt.unit) == ("next_date", date(2026, 12, 31), None)
    assert nxt.value is not None and value_as_date(nxt.value) == date(2027, 2, 4)
    assert nxt.as_of == OBSERVED.date()
    bolt = earnings_observations(load("earnings.BOLT"), "BOLT", RID, OBSERVED, ENTERED, TODAY)
    [nxt] = [r for r in bolt if r.dataset == "earnings-date"]
    assert nxt.value is not None and value_as_date(nxt.value) == date(2027, 1, 28)


def test_earnings_without_report_times_and_without_a_next_date() -> None:
    payload = [
        {"date": "2026-10-30", "epsActual": 0.51},
        {"date": "2026-10-29", "epsActual": None},  # past and unreported: not the next date
        {"date": "2026-11-01", "epsActual": None},  # today counts
        {"date": "2027-02-04", "epsActual": None},
    ]
    rows = earnings_observations(payload, "ACME", RID, OBSERVED, ENTERED, TODAY)
    # Without periodEnding the street actual is keyed by its report date.
    assert obs(rows, "street-actual", "2026-10-30", "eps_actual").value == Decimal("0.51")
    nxt = obs(rows, "earnings-date", None, "next_date")
    assert nxt.value is not None and value_as_date(nxt.value) == date(2026, 11, 1)
    reported = [{"date": "2026-10-30", "epsActual": 0.51}]
    later = earnings_observations(reported, "ACME", RID, OBSERVED, ENTERED, TODAY)
    assert [r.dataset for r in later] == ["street-actual"]


def test_quote_observations() -> None:
    rows = quote_observations(load("quote.ACME"), "ACME", RID, OBSERVED, ENTERED)
    assert {r.field for r in rows} == {
        "price",
        "market_cap",
        "shares_outstanding",
        "year_high",
        "year_low",
    }
    price = obs(rows, "quote", None, "price")
    assert (price.value, price.unit, price.as_of) == (
        Decimal("50.0"),
        "currency",
        date(2026, 10, 30),
    )
    assert obs(rows, "quote", None, "market_cap").value == Decimal(5000000000)
    assert obs(rows, "quote", None, "year_low").value == Decimal(40)
    # The stable quote carries no share count.
    shares = obs(rows, "quote", None, "shares_outstanding")
    assert (shares.value, shares.unit) == (None, "shares")


def test_quote_observations_pick_the_symbol_from_a_batch() -> None:
    batch = load("quote.ACME") + load("quote.BOLT")
    rows = quote_observations(batch, "BOLT", RID, OBSERVED, ENTERED)
    assert obs(rows, "quote", None, "price").value == Decimal(100)
    assert quote_observations(batch, "ZZZ", RID, OBSERVED, ENTERED) == []
    share_class = [{"symbol": "BRK-B", "price": 500, "timestamp": None}]
    rows = quote_observations(share_class, "BRK.B", RID, OBSERVED, ENTERED)
    assert obs(rows, "quote", None, "price").as_of == OBSERVED.date()  # no timestamp


def test_profile_observations() -> None:
    rows = profile_observations(load("profile.ACME"), "ACME", RID, OBSERVED, ENTERED)
    assert {r.field for r in rows} == {"is_adr", "market_cap"}
    adr = obs(rows, "profile", None, "is_adr")
    assert (adr.value, adr.unit, adr.as_of) == (Decimal(0), None, OBSERVED.date())
    cap = obs(rows, "profile", None, "market_cap")
    assert (cap.value, cap.unit, cap.response_id) == (Decimal(5000000000), "currency", RID)


def test_profile_observations_shapes() -> None:
    # A bare object reads like a one-item list; an ADR is 1; an absent or non-boolean flag has no
    # value; a payload without an object gives no rows.
    bare = profile_observations({"isAdr": True, "marketCap": "7"}, "X", RID, OBSERVED, ENTERED)
    assert obs(bare, "profile", None, "is_adr").value == Decimal(1)
    assert obs(bare, "profile", None, "market_cap").value == Decimal(7)
    for flag in ({}, {"isAdr": None}, {"isAdr": "true"}):
        rows = profile_observations([flag], "X", RID, OBSERVED, ENTERED)
        assert obs(rows, "profile", None, "is_adr").value is None
        assert obs(rows, "profile", None, "market_cap").value is None
    for empty in ([], ["x"], None, "profile"):
        assert profile_observations(empty, "X", RID, OBSERVED, ENTERED) == []


def test_profile_country() -> None:
    """The headquarters country of the profile object (spec 6.6), from a list or a bare object;
    ``None`` without a non-empty string."""
    assert profile_country(load("profile.ACME")) == "US"
    assert profile_country({"country": " TW "}) == "TW"
    for missing in ([{}], [{"country": ""}], [{"country": None}], [{"country": 7}], [], None, "US"):
        assert profile_country(missing) is None


def test_price_closes() -> None:
    assert price_closes(load("historical-price-eod-full.ACME")) == [
        (date(2026, 10, 28), 49.0),
        (date(2026, 10, 29), 49.5),
        (date(2026, 10, 30), 50.0),
    ]
    legacy = {"symbol": "ACME", "historical": [{"date": "2026-10-30", "close": 50}]}
    assert price_closes(legacy) == [(date(2026, 10, 30), 50.0)]
    bad = [
        {"date": "2026-10-30", "close": None},
        {"close": 1.0},
        {"date": "2026-10-29", "close": "x"},
    ]
    assert price_closes(bad) == []
    assert price_closes(None) == []


def test_screener_rows_symbol_forms() -> None:
    rows = screener_rows(load("company-screener"))
    assert [r.symbol for r in rows] == [
        "ACME",
        "BOLT",
        "BRK.B",
        "ACME-PA",
        "CAPE",
        "OTCX",
        "FIRB",
        "OFFR",
        "BOLT-WS",
        "NEWC.U",
        "SMLL",
        "BIGX",
        "ADRX",
        "ACME",
    ]


def test_screener_rows_fields() -> None:
    first, bolt, *_ = screener_rows(load("company-screener"))
    assert first == ScreenerRow(
        symbol="ACME",
        name="Acme Corp",
        exchange="NASDAQ",
        sector="Industrials",
        industry="Specialty Industrial Machinery",
        country="US",
        currency=None,
        market_cap=Decimal(5000000000),
        is_etf=False,
        is_fund=False,
        is_actively_trading=True,
        is_adr=False,
    )
    assert bolt.exchange == "NYSE"
    flagged = [{"symbol": "ADRX", "exchange": "NYSE", "isAdr": True, "currency": "USD"}]
    [adr] = screener_rows(flagged)
    assert (adr.is_adr, adr.exchange, adr.currency, adr.market_cap) == (True, "NYSE", "USD", None)
    assert adr.is_actively_trading is False
    assert screener_rows([{"companyName": "no symbol"}, "x"]) == []
