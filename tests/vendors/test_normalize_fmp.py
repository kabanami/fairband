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
    fx_closes,
    fx_quote_observations,
    peer_symbols,
    price_closes,
    profile_brief,
    profile_country,
    profile_observations,
    quote_observations,
    screener_rows,
    split_observations,
    statement_facts,
    statement_fields,
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
    "grossProfit",
    "operatingIncome",
    "interestExpense",
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
    "totalAssets",
    "totalLiabilities",
    "retainedEarnings",
    "minorityInterest",
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
    "depreciationAndAmortization",
}


def test_income_annual_facts() -> None:
    rows = facts("income-statement.annual.ACME", "ACME", "income-annual")
    assert len(rows) == 3 * 10
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
    assert len(rows) == 2 * 10
    first = fact(rows, "2026-09-30", "netIncome")
    assert (first.fiscal_year, first.fiscal_period, first.value) == (2027, "Q1", Decimal(123000000))
    assert first.dataset == "income-quarter"


def test_balance_annual_facts() -> None:
    rows = facts("balance-sheet-statement.annual.ACME", "ACME", "balance-annual")
    assert len(rows) == 3 * 14
    assert {r.field for r in rows} == BALANCE
    goodwill = fact(rows, "2024-12-31", "goodwill")
    assert (goodwill.value, goodwill.missing_reason) == (Decimal(250000000), None)
    assert fact(rows, "2023-12-31", "intangibleAssets").value == Decimal(300000000)


def test_vendor_zero_goodwill_becomes_not_presented() -> None:
    rows = facts("balance-sheet-statement.annual.BOLT", "BOLT", "balance-annual")
    assert len(rows) == 2 * 14
    for period_end in ("2026-06-30", "2025-06-30"):
        for field in ("goodwill", "intangibleAssets"):
            row = fact(rows, period_end, field)
            assert (row.value, row.missing_reason, row.kind) == (None, "vendor-zero", "observed")
    # Every other zero is a real zero.
    sti = fact(rows, "2026-06-30", "shortTermInvestments")
    assert (sti.value, sti.missing_reason) == (Decimal(0), None)
    debt = fact(rows, "2026-06-30", "shortTermDebt")
    assert (debt.value, debt.missing_reason) == (Decimal(0), None)


def _quarterly_sheet() -> list[dict[str, Any]]:
    """Two quarters of the ACME fixture's shape, fiscal 2026 Q1 and Q2, the second with a goodwill
    of 0 and a minority interest of $30 m."""
    [year] = load("balance-sheet-statement.annual.ACME")[:1]
    first = {**year, "date": "2026-03-31", "fiscalYear": "2026", "period": "Q1"}
    second = {**first, "date": "2026-06-30", "period": "Q2", "goodwill": 0}
    return [{**first, "minorityInterest": 0}, {**second, "minorityInterest": 30000000}]


def test_balance_quarter_facts_carry_the_annual_sheet_s_lines() -> None:
    """Spec 2026-11-13 12.1: the quarterly sheet is stored with the annual sheet's lines, the
    minority interest among them, each quarter under its own period end and label; a goodwill of
    0 is not presented there either."""
    rows = statement_facts(_quarterly_sheet(), "ACME", "balance-quarter", RID, OBSERVED, ENTERED)
    assert {r.field for r in rows} == BALANCE
    assert {r.dataset for r in rows} == {"balance-quarter"}
    assert statement_fields("balance-quarter") == statement_fields("balance-annual")
    assert "minorityInterest" in statement_fields("balance-annual")
    zero = next(r for r in rows if r.field == "goodwill" and r.fiscal_period == "Q2")
    assert (zero.value, zero.missing_reason) == (None, "vendor-zero")
    assert len(rows) == 2 * 14
    minority = fact(rows, "2026-06-30", "minorityInterest")
    assert (minority.value, minority.fiscal_year, minority.fiscal_period, minority.as_of) == (
        Decimal(30000000),
        2026,
        "Q2",
        date(2026, 6, 30),
    )
    nil = fact(rows, "2026-03-31", "minorityInterest")  # a real zero, as on every line but two
    assert (nil.value, nil.missing_reason, nil.fiscal_period) == (Decimal(0), None, "Q1")


def test_cashflow_facts_keep_the_vendor_sign_and_real_zeros() -> None:
    annual = facts("cash-flow-statement.annual.ACME", "ACME", "cashflow-annual")
    assert len(annual) == 3 * 9
    assert {r.field for r in annual} == CASHFLOW
    assert fact(annual, "2025-12-31", "capitalExpenditure").value == Decimal(-90000000)
    issued = fact(annual, "2024-12-31", "commonStockIssuance")
    assert (issued.value, issued.missing_reason) == (Decimal(0), None)
    quarter = facts("cash-flow-statement.quarter.ACME", "ACME", "cashflow-quarter")
    assert len(quarter) == 3 * 9
    assert fact(quarter, "2026-06-30", "stockBasedCompensation").value == Decimal(6000000)
    assert fact(quarter, "2026-06-30", "stockBasedCompensation").fiscal_period == "Q2"


def test_the_six_lines_the_decline_and_start_up_routes_read() -> None:
    """Gross profit and interest expense on both income statements, total assets, total
    liabilities and retained earnings on the balance sheet, depreciation and amortization on both
    cash flows; the interest expense keeps the vendor's sign."""
    income = facts("income-statement.annual.ACME", "ACME", "income-annual")
    assert fact(income, "2025-12-31", "grossProfit").value == Decimal(480000000)
    interest = fact(income, "2025-12-31", "interestExpense")
    assert (interest.value, interest.unit, interest.dataset) == (
        Decimal(12000000),
        "currency",
        "income-annual",
    )
    quarter = facts("income-statement.quarter.ACME", "ACME", "income-quarter")
    assert fact(quarter, "2026-09-30", "grossProfit").value == Decimal(132000000)
    assert fact(quarter, "2026-09-30", "interestExpense").value == Decimal(3000000)
    balance = facts("balance-sheet-statement.annual.ACME", "ACME", "balance-annual")
    assert fact(balance, "2025-12-31", "totalAssets").value == Decimal(1510000000)
    assert fact(balance, "2025-12-31", "totalLiabilities").value == Decimal(810000000)
    assert fact(balance, "2025-12-31", "retainedEarnings").value == Decimal(450000000)
    annual = facts("cash-flow-statement.annual.ACME", "ACME", "cashflow-annual")
    assert fact(annual, "2025-12-31", "depreciationAndAmortization").value == Decimal(70000000)
    flows = facts("cash-flow-statement.quarter.ACME", "ACME", "cashflow-quarter")
    assert fact(flows, "2026-09-30", "depreciationAndAmortization").value == Decimal(18000000)
    # BOLT's payloads do not present the retained earnings: no value, the reason null.
    bolt = facts("balance-sheet-statement.annual.BOLT", "BOLT", "balance-annual")
    missing = fact(bolt, "2026-06-30", "retainedEarnings")
    assert (missing.value, missing.missing_reason) == (None, "null")
    row = {"date": "2025-12-31", "interestExpense": -7}
    signed = statement_facts([row], "ACME", "income-annual", RID, OBSERVED, ENTERED)
    assert fact(signed, "2025-12-31", "interestExpense").value == Decimal(-7)


def test_unparseable_values_and_malformed_rows() -> None:
    bad_values = {"revenue": "n/a", "operatingIncome": "125.5", "netIncome": True, "eps": "NaN"}
    payload = [
        {"date": "2025-12-31", "fiscalYear": "2025", "period": "FY", **bad_values},
        {"fiscalYear": "2024", "revenue": 1},  # no date: skipped
        {"date": "not a date", "revenue": 1},  # unparseable date: skipped
        "not a row",
    ]
    rows = statement_facts(payload, "ACME", "income-annual", RID, OBSERVED, ENTERED)
    assert len(rows) == 10
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


def test_split_observations() -> None:
    """Two rows per split, dataset ``split``, the split date as the period and as_of; the
    numerator and denominator kept apart so the sentence can read 2-for-1."""
    rows = split_observations(load("splits.ACME"), "ACME", RID, OBSERVED, ENTERED)
    assert [(r.dataset, r.period, r.field, r.value, r.unit, r.as_of) for r in rows] == [
        ("split", date(2019, 5, 20), "numerator", Decimal(2), "shares", date(2019, 5, 20)),
        ("split", date(2019, 5, 20), "denominator", Decimal(1), "shares", date(2019, 5, 20)),
    ]
    assert {r.response_id for r in rows} == {RID}


def test_split_observations_shapes() -> None:
    # a reverse split keeps its numbers; a row without a date, with a zero or missing number, or
    # a non-list payload gives nothing
    reverse = split_observations(
        [{"date": "2025-01-02", "numerator": 1, "denominator": 10}], "X", RID, OBSERVED, ENTERED
    )
    assert [(r.field, r.value) for r in reverse] == [
        ("numerator", Decimal(1)),
        ("denominator", Decimal(10)),
    ]
    for bad in (
        [{"numerator": 2, "denominator": 1}],
        [{"date": "2025-01-02", "numerator": 0, "denominator": 1}],
        [{"date": "2025-01-02", "numerator": 2}],
        {"date": "2025-01-02"},
        None,
        "x",
    ):
        assert split_observations(bad, "X", RID, OBSERVED, ENTERED) == []


def test_profile_country() -> None:
    """The headquarters country of the profile object (spec 6.6), from a list or a bare object;
    ``None`` without a non-empty string."""
    assert profile_country(load("profile.ACME")) == "US"
    assert profile_country({"country": " TW "}) == "TW"
    for missing in ([{}], [{"country": ""}], [{"country": None}], [{"country": 7}], [], None, "US"):
        assert profile_country(missing) is None


def test_profile_brief() -> None:
    """The company brief (B-149): the profile object's ``description``, stripped, from a list or
    a bare object; ``None`` without a non-empty string."""
    assert profile_brief(load("profile.ACME")) == (
        "Acme Corp designs and builds industrial machinery for factories in North America. The "
        "company sells presses, conveyors and spare parts through its own sales force."
    )
    assert profile_brief({"description": " Bare. "}) == "Bare."
    for missing in (
        [{}],
        [{"description": ""}],
        [{"description": "  "}],
        [{"description": None}],
        [{"description": 7}],
        [],
        None,
        "Acme",
    ):
        assert profile_brief(missing) is None


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


def test_fx_closes_oldest_first_skipping_bad_rows() -> None:
    rows = [
        {"symbol": "USDSEK", "date": "2026-11-05", "price": 10.6},
        {"date": "2026-11-04", "price": "x"},
        {"date": "2026-11-01", "price": 10.5},
        {"price": 10.0},
    ]
    assert fx_closes(rows) == [(date(2026, 11, 1), 10.5), (date(2026, 11, 5), 10.6)]
    assert fx_closes({}) == [] and fx_closes(None) == []
    not_rates = [{"date": "2026-11-05", "price": 0}, {"date": "2026-11-04", "price": -1}]
    assert fx_closes(not_rates) == []  # a rate of zero or below is no rate


def test_fx_closes_reads_the_fixture() -> None:
    closes = fx_closes(load("historical-price-eod-light.USDSEK"))
    assert closes[0] == (date(2025, 9, 30), 7.7) and closes[-1] == (date(2026, 11, 5), 10.6)
    assert dict(closes)[date(2026, 11, 1)] == 10.5
    quarter_ends = (date(2025, 12, 31), date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30))
    assert [dict(closes)[end] for end in quarter_ends] == [7.8, 7.9, 8.1, 8.2]


def test_fx_quote_observations_one_row_per_pair() -> None:
    """Dataset ``fx-quote``, the pair as the symbol, one ``price`` row with no unit, keyed by the
    quote's date (its ``timestamp``, else the observation day); a batch gives the pair's row."""
    batch = [
        {"symbol": "USDSEK", "price": 10.7, "timestamp": 1793390400},  # 2026-10-30 UTC
        {"symbol": "USDTWD", "price": "32.956"},
    ]
    [sek] = fx_quote_observations(batch, "USDSEK", RID, OBSERVED, ENTERED)
    assert sek == ObservationRow(
        symbol="USDSEK",
        dataset="fx-quote",
        period=date(2026, 10, 30),
        field="price",
        value=Decimal("10.7"),
        unit=None,
        as_of=date(2026, 10, 30),
        observed_at=OBSERVED,
        entered_at=ENTERED,
        response_id=RID,
    )
    [twd] = fx_quote_observations(batch, "USDTWD", RID, OBSERVED, ENTERED)
    assert (twd.period, twd.as_of, twd.value) == (TODAY, TODAY, Decimal("32.956"))
    assert fx_quote_observations(batch, "USDJPY", RID, OBSERVED, ENTERED) == []
    for bad in ({"symbol": "USDSEK", "price": None}, {"symbol": "USDSEK", "price": 0}):
        assert fx_quote_observations([bad], "USDSEK", RID, OBSERVED, ENTERED) == []
    assert fx_quote_observations(None, "USDSEK", RID, OBSERVED, ENTERED) == []


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


def test_peer_symbols_drop_self_and_repeats_and_use_the_exchange_form() -> None:
    payload = [
        {"symbol": "BRK-B"},
        {"symbol": "ACME"},
        {"symbol": "BOLT"},
        {"symbol": "BOLT"},
        {"x": 1},
        {"symbol": "ACME-PA"},
    ]
    assert peer_symbols(payload, "ACME") == ["BRK.B", "BOLT", "ACME-PA"]
    assert peer_symbols(payload, "BRK.B") == ["ACME", "BOLT", "ACME-PA"]  # own in exchange form
    assert peer_symbols({"symbol": "X"}, "ACME") == [] and peer_symbols("no", "ACME") == []
    assert peer_symbols(load("stock-peers.ACME"), "ACME") == ["BOLT", "ZZZZ", "NEWT", "FIRB"]
