"""The Financials tab's readers (the tab's design, 7.3, 7.5, 7.9, 8.3 and 12) on synthetic answers:
every line of section 12 in its order with its key, kind and unit, the columns by year, by quarter
and by half-year with their currencies, the lines and heads left out, a figure that is not a number
read as null, the ratios joined by date, the segments' years and order, and an answer of the wrong
shape read as an empty table."""

from datetime import date
from typing import Any

import pytest

from fairband.vendors.fmp import StatementKind
from fairband.vendors.page_financials import (
    period_ends,
    ratios,
    reported_currency,
    segments,
    statement,
)

# Section 12 as the spec writes it: FMP's field, then the line. ``**`` marks a total, ``· `` leads
# a sub-line, and a line in upper case with no field is a section head.
INCOME = (
    ("revenue", "**Revenue**"),
    ("costOfRevenue", "Cost of revenue"),
    ("grossProfit", "**Gross profit**"),
    ("researchAndDevelopmentExpenses", "Research and development"),
    ("sellingGeneralAndAdministrativeExpenses", "Selling, general and administrative"),
    ("generalAndAdministrativeExpenses", "· General and administrative"),
    ("sellingAndMarketingExpenses", "· Selling and marketing"),
    ("otherExpenses", "Other expenses"),
    ("operatingExpenses", "Operating expenses"),
    ("operatingIncome", "**Operating income**"),
    ("interestIncome", "Interest income"),
    ("interestExpense", "Interest expense"),
    ("totalOtherIncomeExpensesNet", "Other income, net"),
    ("incomeBeforeTax", "**Income before tax**"),
    ("incomeTaxExpense", "Income tax"),
    ("netIncome", "**Net income**"),
    (None, "PER SHARE"),
    ("eps", "EPS"),
    ("epsDiluted", "EPS, diluted"),
    ("weightedAverageShsOut", "Shares"),
    ("weightedAverageShsOutDil", "Shares, diluted"),
    (None, "OTHER"),
    ("ebitda", "EBITDA"),
    ("depreciationAndAmortization", "Depreciation and amortization"),
)
BALANCE = (
    (None, "ASSETS"),
    ("cashAndCashEquivalents", "Cash and equivalents"),
    ("shortTermInvestments", "Short-term investments"),
    ("netReceivables", "Receivables"),
    ("inventory", "Inventory"),
    ("prepaids", "Prepaids"),
    ("otherCurrentAssets", "Other current assets"),
    ("totalCurrentAssets", "**Total current assets**"),
    ("propertyPlantEquipmentNet", "Property, plant and equipment"),
    ("goodwill", "Goodwill"),
    ("intangibleAssets", "Intangible assets"),
    ("longTermInvestments", "Long-term investments"),
    ("taxAssets", "Tax assets"),
    ("otherNonCurrentAssets", "Other non-current assets"),
    ("totalNonCurrentAssets", "**Total non-current assets**"),
    ("totalAssets", "**Total assets**"),
    (None, "LIABILITIES"),
    ("accountPayables", "Accounts payable"),
    ("accruedExpenses", "Accrued expenses"),
    ("shortTermDebt", "Short-term debt"),
    ("capitalLeaseObligationsCurrent", "Lease obligations, current"),
    ("taxPayables", "Tax payables"),
    ("deferredRevenue", "Deferred revenue"),
    ("otherCurrentLiabilities", "Other current liabilities"),
    ("totalCurrentLiabilities", "**Total current liabilities**"),
    ("longTermDebt", "Long-term debt"),
    ("capitalLeaseObligationsNonCurrent", "Lease obligations, non-current"),
    ("deferredRevenueNonCurrent", "Deferred revenue, non-current"),
    ("deferredTaxLiabilitiesNonCurrent", "Deferred tax liabilities"),
    ("otherNonCurrentLiabilities", "Other non-current liabilities"),
    ("totalNonCurrentLiabilities", "**Total non-current liabilities**"),
    ("totalLiabilities", "**Total liabilities**"),
    (None, "EQUITY"),
    ("commonStock", "Common stock"),
    ("additionalPaidInCapital", "Additional paid-in capital"),
    ("retainedEarnings", "Retained earnings"),
    ("accumulatedOtherComprehensiveIncomeLoss", "Accumulated other comprehensive income"),
    ("treasuryStock", "Treasury stock"),
    ("totalStockholdersEquity", "**Total stockholders' equity**"),
    ("minorityInterest", "Minority interest"),
    ("totalLiabilitiesAndTotalEquity", "**Total liabilities and equity**"),
    (None, "OTHER"),
    ("totalInvestments", "Total investments"),
    ("totalDebt", "Total debt"),
    ("netDebt", "Net debt"),
)
CASHFLOW = (
    (None, "OPERATING"),
    ("netIncome", "Net income"),
    ("depreciationAndAmortization", "Depreciation and amortization"),
    ("deferredIncomeTax", "Deferred income tax"),
    ("stockBasedCompensation", "Stock-based compensation"),
    ("changeInWorkingCapital", "Change in working capital"),
    ("accountsReceivables", "· Receivables"),
    ("inventory", "· Inventory"),
    ("accountsPayables", "· Payables"),
    ("otherWorkingCapital", "· Other working capital"),
    ("otherNonCashItems", "Other non-cash items"),
    ("netCashProvidedByOperatingActivities", "**Cash from operations**"),
    (None, "INVESTING"),
    ("investmentsInPropertyPlantAndEquipment", "Capital expenditure"),
    ("acquisitionsNet", "Acquisitions, net"),
    ("purchasesOfInvestments", "Purchases of investments"),
    ("salesMaturitiesOfInvestments", "Sales and maturities of investments"),
    ("otherInvestingActivities", "Other investing"),
    ("netCashProvidedByInvestingActivities", "**Cash from investing**"),
    (None, "FINANCING"),
    ("netDebtIssuance", "Debt issued, net"),
    ("commonStockIssuance", "Stock issued"),
    ("commonStockRepurchased", "Stock repurchased"),
    ("netDividendsPaid", "Dividends paid"),
    ("otherFinancingActivities", "Other financing"),
    ("netCashProvidedByFinancingActivities", "**Cash from financing**"),
    (None, "CASH"),
    ("effectOfForexChangesOnCash", "Effect of exchange rates"),
    ("netChangeInCash", "**Net change in cash**"),
    ("cashAtBeginningOfPeriod", "Cash at the start"),
    ("cashAtEndOfPeriod", "Cash at the end"),
    (None, "OTHER"),
    ("freeCashFlow", "**Free cash flow**"),
    ("incomeTaxesPaid", "Income taxes paid"),
    ("interestPaid", "Interest paid"),
)
# Section 12.4: the answer, FMP's field, the line and its unit; a head has no answer and no field.
RATIO_LINES = (
    (None, None, "MARGINS", None),
    ("ratios", "grossProfitMargin", "Gross", "percent"),
    ("ratios", "ebitdaMargin", "EBITDA", "percent"),
    ("ratios", "operatingProfitMargin", "Operating", "percent"),
    ("ratios", "pretaxProfitMargin", "Pretax", "percent"),
    ("ratios", "netProfitMargin", "Net", "percent"),
    (None, None, "RETURNS", None),
    ("key-metrics", "returnOnEquity", "ROE", "percent"),
    ("key-metrics", "returnOnAssets", "ROA", "percent"),
    ("key-metrics", "returnOnInvestedCapital", "ROIC", "percent"),
    ("key-metrics", "returnOnCapitalEmployed", "ROCE", "percent"),
    (None, None, "VALUATION", None),
    ("ratios", "priceToEarningsRatio", "P/E", "multiple"),
    ("ratios", "priceToEarningsGrowthRatio", "PEG", "ratio"),
    ("ratios", "priceToBookRatio", "P/B", "multiple"),
    ("ratios", "priceToSalesRatio", "P/S", "multiple"),
    ("ratios", "priceToFreeCashFlowRatio", "P/FCF", "multiple"),
    ("key-metrics", "evToSales", "EV/Sales", "multiple"),
    ("key-metrics", "evToEBITDA", "EV/EBITDA", "multiple"),
    ("key-metrics", "evToFreeCashFlow", "EV/FCF", "multiple"),
    ("key-metrics", "earningsYield", "Earnings yield", "percent"),
    ("key-metrics", "freeCashFlowYield", "FCF yield", "percent"),
    (None, None, "FINANCIAL HEALTH", None),
    ("ratios", "debtToEquityRatio", "Debt to equity", "ratio"),
    ("key-metrics", "netDebtToEBITDA", "Net debt to EBITDA", "ratio"),
    ("ratios", "currentRatio", "Current ratio", "ratio"),
    ("ratios", "quickRatio", "Quick ratio", "ratio"),
    ("ratios", "interestCoverageRatio", "Interest cover", "multiple"),
    (None, None, "PER SHARE", None),
    ("ratios", "revenuePerShare", "Revenue", "perShare"),
    ("ratios", "netIncomePerShare", "Net income", "perShare"),
    ("ratios", "freeCashFlowPerShare", "Free cash flow", "perShare"),
    ("ratios", "bookValuePerShare", "Book value", "perShare"),
    ("ratios", "dividendPerShare", "Dividend", "perShare"),
    (None, None, "DIVIDENDS", None),
    ("ratios", "dividendYield", "Yield", "percent"),
    ("ratios", "dividendPayoutRatio", "Payout", "percent"),
    (None, None, "EFFICIENCY", None),
    ("key-metrics", "daysOfSalesOutstanding", "Days of sales outstanding", "days"),
    ("key-metrics", "daysOfInventoryOutstanding", "Days of inventory", "days"),
    ("key-metrics", "daysOfPayablesOutstanding", "Days of payables", "days"),
    ("key-metrics", "cashConversionCycle", "Cash conversion cycle", "days"),
    ("key-metrics", "capexToRevenue", "Capital expenditure to revenue", "percent"),
    (
        "key-metrics",
        "researchAndDevelopementToRevenue",
        "Research and development to revenue",
        "percent",
    ),
    ("key-metrics", "stockBasedCompensationToRevenue", "Stock pay to revenue", "percent"),
)


def labels(lines: tuple[tuple[str | None, str], ...]) -> tuple[str, ...]:
    """The lines' labels: the spec's words without the marks of a total or a sub-line."""
    return tuple(written.strip("*").removeprefix("· ") for _key, written in lines)


INCOME_LABELS = labels(INCOME)
BALANCE_LABELS = labels(BALANCE)
CASHFLOW_LABELS = labels(CASHFLOW)
RATIO_LABELS = tuple(label for _answer, _field, label, _unit in RATIO_LINES)

STATEMENTS: dict[StatementKind, tuple[tuple[tuple[str | None, str], ...], tuple[str, ...]]] = {
    "income": (INCOME, INCOME_LABELS),
    "balance": (BALANCE, BALANCE_LABELS),
    "cashflow": (CASHFLOW, CASHFLOW_LABELS),
}
# The income statement's lines that are not money; every other statement line is.
INCOME_UNITS = {
    "eps": "perShare",
    "epsDiluted": "perShare",
    "weightedAverageShsOut": "shares",
    "weightedAverageShsOutDil": "shares",
}
# A ratio's name on the chart where it is not its label (7.5).
CHART_NAMES = {
    "grossProfitMargin": "Gross margin",
    "ebitdaMargin": "EBITDA margin",
    "operatingProfitMargin": "Operating margin",
    "pretaxProfitMargin": "Pretax margin",
    "netProfitMargin": "Net margin",
    "revenuePerShare": "Revenue a share",
    "netIncomePerShare": "Net income a share",
    "freeCashFlowPerShare": "Free cash flow a share",
    "bookValuePerShare": "Book value a share",
    "dividendPerShare": "Dividend a share",
    "dividendYield": "Dividend yield",
    "dividendPayoutRatio": "Dividend payout",
}
EMPTY: dict[str, Any] = {"columns": [], "rows": []}
MISSING = object()  # a field the row does not hold


def kind_of(key: str | None, written: str) -> str:
    """A line's kind as the spec marks it."""
    if key is None:
        return "head"
    if written.startswith("**"):
        return "total"
    return "sub" if written.startswith("· ") else "line"


def head(label: str) -> dict[str, Any]:
    return {"key": None, "label": label, "name": None, "kind": "head", "unit": None, "values": None}


def year_row(year: int, **fields: Any) -> dict[str, Any]:
    """An answer's row for fiscal year ``year``, ending 30 September, in US dollars."""
    return {
        "date": f"{year}-09-30",
        "fiscalYear": str(year),
        "period": "FY",
        "reportedCurrency": "USD",
        **fields,
    }


def quarter_row(day: str, period: str, **fields: Any) -> dict[str, Any]:
    return {
        "date": day,
        "fiscalYear": "2026",
        "period": period,
        "reportedCurrency": "USD",
        **fields,
    }


def segment_row(year: int, data: Any) -> dict[str, Any]:
    """A segment answer's row: the fiscal year as a number, as FMP gives it there."""
    return {
        "symbol": "XYZ",
        "fiscalYear": year,
        "period": "FY",
        "reportedCurrency": "USD",
        "date": f"{year}-09-30",
        "data": data,
    }


def filled(fields: list[str]) -> dict[str, float]:
    """A figure, none of them 0, in every one of ``fields``."""
    return {field: 1000.0 * (index + 1) for index, field in enumerate(fields)}


def by_key(table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["key"]: row for row in table["rows"] if row["kind"] != "head"}


def column_labels(table: dict[str, Any]) -> list[str]:
    return [column["label"] for column in table["columns"]]


def row_labels(table: dict[str, Any]) -> list[str]:
    return [row["label"] for row in table["rows"]]


def test_every_line_of_a_statement_in_the_spec_s_order() -> None:
    for kind, (lines, expected) in STATEMENTS.items():
        figures = filled([key for key, _written in lines if key is not None])
        rows = statement([year_row(2026, **figures)], kind, "USD")["rows"]
        assert tuple(row["label"] for row in rows) == expected
        assert [(row["key"], row["kind"]) for row in rows] == [
            (key, kind_of(key, written)) for key, written in lines
        ]
        for row in rows:
            if row["kind"] == "head":
                assert row == head(row["label"])
                continue
            unit = INCOME_UNITS.get(row["key"], "money") if kind == "income" else "money"
            assert row["unit"] == unit
            assert row["name"] == row["label"]
            assert row["values"] == [figures[row["key"]]]
    income = by_key(statement([year_row(2026, **filled(["revenue", "eps"]))], "income", "USD"))
    assert (income["revenue"]["kind"], income["revenue"]["unit"]) == ("total", "money")
    assert (income["eps"]["kind"], income["eps"]["unit"]) == ("line", "perShare")
    general = statement(
        [year_row(2026, generalAndAdministrativeExpenses=4.0, weightedAverageShsOut=15.0)],
        "income",
        "USD",
    )
    assert general["rows"][0] == {
        "key": "generalAndAdministrativeExpenses",
        "label": "General and administrative",
        "name": "General and administrative",
        "kind": "sub",
        "unit": "money",
        "values": [4.0],
    }
    assert by_key(general)["weightedAverageShsOut"]["unit"] == "shares"


def test_the_columns_by_year_and_by_quarter() -> None:
    newest_first = [year_row(year, revenue=year * 1_000_000_000) for year in (2026, 2025, 2024)]
    table = statement(newest_first, "income", "USD")
    assert column_labels(table) == ["2024", "2025", "2026"]
    assert [column["end"] for column in table["columns"]] == [
        "2024-09-30",
        "2025-09-30",
        "2026-09-30",
    ]
    assert by_key(table)["revenue"]["values"] == [2024e9, 2025e9, 2026e9]  # units, not millions

    quarters = [
        quarter_row("2026-09-30", "Q4", revenue=2.0),
        quarter_row("2026-06-30", "Q3", revenue=1.0),
    ]
    by_quarter = statement(quarters, "income", "USD", quarterly=True)
    assert column_labels(by_quarter) == ["Q3 2026", "Q4 2026"]
    assert by_key(by_quarter)["revenue"]["values"] == [1.0, 2.0]

    for fiscal_year in (2026, "2026", MISSING):
        row: dict[str, Any] = {"date": "2026-09-30", "period": "Q4", "revenue": 1.0}
        if fiscal_year is not MISSING:
            row["fiscalYear"] = fiscal_year
        assert column_labels(statement([row], "income", "USD")) == ["2026"]
        assert column_labels(statement([row], "income", "USD", quarterly=True)) == ["Q4 2026"]


def test_a_fiscal_year_that_is_not_a_year_reads_the_year_of_the_date() -> None:
    for fiscal_year in ("1e3", "-5", " 20 26", 2026.5, True, 0, 10_000, "x", None, "1e99999999"):
        row = {"date": "2025-12-31", "fiscalYear": fiscal_year, "revenue": 1.0}
        assert column_labels(statement([row], "income", "USD")) == ["2025"], fiscal_year


def test_a_quarter_with_no_period_is_labelled_by_its_year_alone() -> None:
    rows = [
        quarter_row("2026-06-30", "", revenue=1.0),
        {**quarter_row("2026-09-30", "Q4", revenue=1.0), "period": None},
    ]
    assert column_labels(statement(rows, "income", "USD", quarterly=True)) == ["2026", "2026"]


def test_half_years_are_named_h1_and_h2() -> None:
    rows = [
        quarter_row("2026-03-31", "Q2", revenue=1.0),
        quarter_row("2026-06-30", "Q3", revenue=2.0),
        quarter_row("2026-09-30", "Q4", revenue=3.0),
    ]
    halves = statement(rows, "income", "GBP", quarterly=True, half_yearly=True)
    assert column_labels(halves) == ["H1 2026", "Q3 2026", "H2 2026"]
    quarters = statement(rows, "income", "GBP", quarterly=True, half_yearly=False)
    assert column_labels(quarters) == ["Q2 2026", "Q3 2026", "Q4 2026"]


def test_a_line_of_zeros_and_nulls_is_left_out_with_its_empty_head() -> None:
    blank = {
        "interestIncome": 0,
        "eps": None,
        "weightedAverageShsOut": None,
        "weightedAverageShsOutDil": 0.0,
    }
    rows = [
        year_row(2025, revenue=10.0, ebitda=0, **blank),
        year_row(2026, revenue=12.0, ebitda=5, **blank),
    ]
    table = statement(rows, "income", "USD")
    assert row_labels(table) == ["Revenue", "OTHER", "EBITDA"]
    assert by_key(table)["ebitda"]["values"] == [0, 5]

    only_revenue = statement([year_row(2026, revenue=10.0, ebitda=0)], "income", "USD")
    assert row_labels(only_revenue) == ["Revenue"]  # a head with no line before the end goes too


def test_a_figure_that_is_not_a_number_is_null() -> None:
    raws: list[Any] = ["12", True, float("nan"), float("inf"), float("-inf"), 10**400, MISSING]
    rows = [
        year_row(2010 + index) | ({} if raw is MISSING else {"revenue": raw})
        for index, raw in enumerate(raws)
    ]
    rows.append(year_row(2026, revenue=7))
    values = by_key(statement(rows, "income", "USD"))["revenue"]["values"]
    assert values == [None] * len(raws) + [7]
    assert isinstance(values[-1], int)  # a figure as FMP gives it


def test_a_column_carries_its_row_s_currency() -> None:
    rows = [
        year_row(2024, revenue=1.0, reportedCurrency="EUR"),
        year_row(2025, revenue=1.0, reportedCurrency="EUR"),
        year_row(2026, revenue=1.0),
    ]
    table = statement(rows, "income", "USD")
    assert [column["currency"] for column in table["columns"]] == ["EUR", "EUR", "USD"]

    unnamed = [
        {"date": "2024-12-31", "revenue": 1.0},
        {"date": "2025-12-31", "revenue": 1.0, "reportedCurrency": ""},
        {"date": "2026-12-31", "revenue": 1.0, "reportedCurrency": 7},
    ]
    table = statement(unnamed, "income", "USD")
    assert [column["currency"] for column in table["columns"]] == ["USD", "USD", "USD"]


def test_the_ratios_join_two_answers_by_date() -> None:
    answer = [
        {**year_row(2025, grossProfitMargin=0.469, currentRatio=1.5), "date": "2025-09-29"},
        year_row(2026, grossProfitMargin=0.488, currentRatio=1.25),
    ]
    metrics = [year_row(2026, returnOnInvestedCapital=0.53, grossProfitMargin=0.9, currentRatio=9)]
    table = ratios(answer, metrics, "USD", 11)
    assert table["columns"] == [
        {"label": "2025", "end": "2025-09-29", "currency": "USD"},
        {"label": "2026", "end": "2026-09-30", "currency": "USD"},
    ]
    lines = by_key(table)
    assert lines["returnOnInvestedCapital"]["values"] == [None, 0.53]
    assert lines["grossProfitMargin"]["values"] == [0.469, 0.488]  # each field from its answer
    assert lines["currentRatio"]["values"] == [1.5, 1.25]
    assert row_labels(table) == [
        "MARGINS",
        "Gross",
        "RETURNS",
        "ROIC",
        "FINANCIAL HEALTH",
        "Current ratio",
    ]

    alone = ratios(answer, None, "USD", 11)
    assert column_labels(alone) == ["2025", "2026"]
    assert row_labels(alone) == ["MARGINS", "Gross", "FINANCIAL HEALTH", "Current ratio"]

    only_metrics = ratios(None, metrics, "EUR", 11)
    assert only_metrics["columns"] == [{"label": "2026", "end": "2026-09-30", "currency": "USD"}]
    assert row_labels(only_metrics) == ["RETURNS", "ROIC"]


def test_a_ratio_s_name_on_the_chart() -> None:
    answers: dict[str, dict[str, float]] = {"ratios": {}, "key-metrics": {}}
    for index, (answer, field, _label, _unit) in enumerate(RATIO_LINES):
        if answer is not None and field is not None:
            answers[answer][field] = 0.5 + index
    figures = answers["ratios"] | answers["key-metrics"]
    table = ratios(
        [year_row(2026, **answers["ratios"])], [year_row(2026, **answers["key-metrics"])], "USD", 11
    )
    assert tuple(row_labels(table)) == RATIO_LABELS
    assert [(row["key"], row["unit"]) for row in table["rows"]] == [
        (field, unit) for _answer, field, _label, unit in RATIO_LINES
    ]
    for row in table["rows"]:
        if row["kind"] == "head":
            assert row == head(row["label"])
            continue
        assert row["kind"] == "line"
        assert row["name"] == CHART_NAMES.get(row["key"], row["label"])
        assert row["values"] == [figures[row["key"]]]
    lines = by_key(table)
    assert lines["grossProfitMargin"]["name"] == "Gross margin"
    assert lines["revenuePerShare"]["name"] == "Revenue a share"
    assert lines["dividendYield"]["name"] == "Dividend yield"
    assert lines["dividendPayoutRatio"]["name"] == "Dividend payout"
    assert lines["returnOnInvestedCapital"]["name"] == "ROIC"
    assert lines["priceToEarningsRatio"]["unit"] == "multiple"
    assert lines["priceToEarningsGrowthRatio"]["unit"] == "ratio"
    assert lines["daysOfSalesOutstanding"]["unit"] == "days"
    keys = [row["key"] for row in table["rows"]]
    assert keys[keys.index("priceToEarningsRatio") + 1] == "priceToEarningsGrowthRatio"


def test_the_ratios_keep_the_newest_limit_dates() -> None:
    answer = [year_row(year, grossProfitMargin=year / 10_000) for year in range(2014, 2026)]
    metrics = [year_row(year, returnOnEquity=year / 10_000) for year in range(2015, 2027)]
    table = ratios(answer, metrics, "USD", 11)
    assert column_labels(table) == [str(year) for year in range(2016, 2027)]
    lines = by_key(table)
    assert lines["grossProfitMargin"]["values"] == [year / 10_000 for year in range(2016, 2026)] + [
        None
    ]
    assert lines["returnOnEquity"]["values"] == [year / 10_000 for year in range(2016, 2027)]


def test_the_segments_newest_years_and_their_order() -> None:
    rows = [segment_row(year, {"Gone": 4}) for year in range(2010, 2016)]
    rows += [segment_row(year, {"Zero": 0}) for year in range(2016, 2025)]
    rows += [
        segment_row(2025, {"A": 7, "Old": 3, "Zero": None}),
        segment_row(2026, {"A": 5, "B": 9, "Old": 0}),
    ]
    assert len(rows) == 17
    table = segments(list(reversed(rows)), "USD", 11)
    assert column_labels(table) == [str(year) for year in range(2016, 2027)]
    assert table["columns"][-1] == {"label": "2026", "end": "2026-09-30", "currency": "USD"}
    assert row_labels(table) == ["B", "A", "Old"]
    early = [None] * 9
    assert table["rows"] == [
        {
            "key": "B",
            "label": "B",
            "name": "Revenue: B",
            "kind": "line",
            "unit": "money",
            "values": [*early, None, 9],
        },
        {
            "key": "A",
            "label": "A",
            "name": "Revenue: A",
            "kind": "line",
            "unit": "money",
            "values": [*early, 7, 5],
        },
        {
            "key": "Old",
            "label": "Old",
            "name": "Revenue: Old",
            "kind": "line",
            "unit": "money",
            "values": [*early, 3, 0],
        },
    ]


def test_the_segments_order_a_tie_by_name_and_a_line_absent_from_the_newest_year_last() -> None:
    rows = [
        segment_row(2024, {"Small": 2, "Big": "10"}),
        segment_row(2025, {"Big": 10, "Small": 2, "Neg": 3, "Loss": -3, "Minus": -1}),
        segment_row(2026, {"Zeta": 4, "Alpha": 4, "Neg": -1, "Big": 0, "Loss": 0}),
        segment_row(2027, "not an object"),
    ]
    table = segments(rows, "EUR", 11)
    assert column_labels(table) == ["2024", "2025", "2026", "2027"]
    assert row_labels(table) == ["Big", "Alpha", "Zeta", "Neg", "Small", "Minus", "Loss"]
    assert by_key(table)["Big"]["values"] == [None, 10, 0, None]

    newest = segments(rows[:3], "EUR", 11)  # Loss's largest figure is −3: its 0 is none
    assert row_labels(newest) == ["Alpha", "Zeta", "Neg", "Big", "Small", "Minus", "Loss"]


@pytest.mark.parametrize(
    "payload",
    [
        {"Error Message": "x"},
        None,
        "text",
        7,
        [1, 2],
        [[2026, 1.0]],
        [{"no": "date"}],
        [{"date": "2026-13-45", "revenue": 1.0, "data": {"A": 1}}],
    ],
)
def test_a_payload_of_the_wrong_shape_is_an_empty_table(payload: Any) -> None:
    for kind in STATEMENTS:
        assert statement(payload, kind, "USD") == EMPTY
        assert statement(payload, kind, "USD", quarterly=True, half_yearly=True) == EMPTY
    assert ratios(payload, payload, "USD", 11) == EMPTY
    assert segments(payload, "USD", 11) == EMPTY
    assert reported_currency(payload) is None
    assert period_ends(payload) == []


def test_the_newest_row_names_the_currency_and_the_ends_are_in_order() -> None:
    rows = [
        year_row(2026, reportedCurrency="USD"),
        year_row(2024, reportedCurrency="EUR"),
        {"no": "date", "reportedCurrency": "JPY"},
        year_row(2025, reportedCurrency="EUR"),
    ]
    assert reported_currency(rows) == "USD"
    assert period_ends(rows) == [date(2024, 9, 30), date(2025, 9, 30), date(2026, 9, 30)]
    assert reported_currency([year_row(2026, reportedCurrency=None), *rows[1:]]) is None


def test_no_limit_keeps_no_column() -> None:
    assert ratios([year_row(2026, grossProfitMargin=0.5)], None, "USD", 0) == EMPTY
    assert segments([segment_row(2026, {"A": 1})], "USD", 0) == EMPTY
