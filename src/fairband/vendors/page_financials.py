"""The company page's Financials tab from FMP's stored answers (the Financials tab's design, 5, 7.3,
7.5, 7.9, 8.3 and 12): pure readers, a parsed payload in and a table out, with no store, network or
clock, beside the page's others (``page_fmp``). The tab's read hands them the newest stored
answers: the six statements, the ratios and the key metrics by fiscal year, and the two segment
answers.

A table is ``{"columns", "rows"}``, the columns oldest first and the rows in section 12's order.

- A column is a period, ``{"label", "end", "currency"}``. Its label is the fiscal year as a text
  (``"2026"``): the row's ``fiscalYear``, a whole year given as a number or as a text of digits
  (a segment answer gives a number where a statement gives a text), else the year of its
  ``date``. By quarter the row's ``period`` stands before it (``"Q4 2026"``), and for a company
  that reports by half-year ``Q2`` reads ``H1`` and ``Q4`` ``H2`` (``"H2 2026"``); any other
  period keeps FMP's name, and a row with no period is labelled by its year alone. ``end`` is
  the row's ``date`` as an ISO day; ``currency`` is the row's ``reportedCurrency`` where it is a
  text, else the tab's.
- A row is ``{"key", "label", "name", "kind", "unit", "values"}``. ``key`` is FMP's field (a
  segment's name); ``label`` is its name in the table and ``name`` its name on the chart; ``kind``
  is ``total``, ``line``, ``sub`` or ``head``; ``unit`` is ``money``, ``perShare``, ``shares``,
  ``percent``, ``multiple``, ``ratio`` or ``days``. ``values`` holds one figure a column, read by
  ``page_fmp.number``: a finite JSON number as FMP gives it, an amount in units of its currency
  and a percent as a fraction, else ``None`` (a text such as ``"12"``, a boolean, ``NaN``, an
  infinity, a missing field). A section head has its upper-case label and no key, name, unit or
  values.
- A line whose every figure is ``None`` or 0 is left out, since FMP writes 0 for a line it does not
  hold (section 5); then a head with no line under it before the next head or the end.
- A statement's columns are its answer's dated rows in order of ``date``. Its lines are section
  12's, each named on the chart as in the table.
- The ratios join the ``ratios`` and ``key-metrics`` answers by the row's ``date``: a column a date
  among either's rows, the newest ``limit``, oldest first; each line reads its own answer's field,
  ``None`` where that answer has no row for the date (the first row of a date counting). A ratio's
  name on the chart is its label, but ``<label> margin`` under Margins, ``<label> a share`` under
  Per share and ``Dividend <label in lower case>`` under Dividends (7.5).
- A segment answer's columns are its newest ``limit`` dated rows, oldest first; each row's ``data``
  object maps a name to its revenue. A line is a name with a figure that is not 0 in those rows, its
  key and its label FMP's name unchanged and its name on the chart ``Revenue: <name>``. The lines
  stand by the newest column's figure, largest first, then the lines with none there (``None`` or
  0) by their largest figure; a tie goes by name.
- Nothing is computed: no total, no margin, no scaling. An answer of the wrong shape (FMP's
  ``{"Error Message": ...}``, ``null``, a text, a number, a list of anything but objects, rows with
  no date) gives a table with no column and no row; none of the readers raises on any JSON value.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any, NamedTuple

from fairband.vendors._fmp_parse import dated, text, whole
from fairband.vendors.fmp import StatementKind
from fairband.vendors.page_fmp import number

type Table = dict[str, Any]  # {"columns": [Column, ...], "rows": [Row, ...]}
type Column = dict[str, Any]  # {"label": "2026", "end": "2026-09-26", "currency": "USD"}
type Row = dict[str, Any]  # {"key", "label", "name", "kind", "unit", "values"}

_TOTAL, _LINE, _SUB, _HEAD = "total", "line", "sub", "head"
_MONEY, _PER_SHARE, _SHARES = "money", "perShare", "shares"
_PERCENT, _MULTIPLE, _RATIO, _DAYS = "percent", "multiple", "ratio", "days"
_RATIOS, _METRICS = "ratios", "key-metrics"

_DIGITS = re.compile(r"[0-9]+")
_HALVES = {"Q2": "H1", "Q4": "H2"}

# Section 12.1 to 12.3: FMP's field, the line's label, its kind and its unit; a head has no field
# and no unit.
type _StatementLine = tuple[str | None, str, str, str | None]

_INCOME: tuple[_StatementLine, ...] = (
    ("revenue", "Revenue", _TOTAL, _MONEY),
    ("costOfRevenue", "Cost of revenue", _LINE, _MONEY),
    ("grossProfit", "Gross profit", _TOTAL, _MONEY),
    ("researchAndDevelopmentExpenses", "Research and development", _LINE, _MONEY),
    (
        "sellingGeneralAndAdministrativeExpenses",
        "Selling, general and administrative",
        _LINE,
        _MONEY,
    ),
    ("generalAndAdministrativeExpenses", "General and administrative", _SUB, _MONEY),
    ("sellingAndMarketingExpenses", "Selling and marketing", _SUB, _MONEY),
    ("otherExpenses", "Other expenses", _LINE, _MONEY),
    ("operatingExpenses", "Operating expenses", _LINE, _MONEY),
    ("operatingIncome", "Operating income", _TOTAL, _MONEY),
    ("interestIncome", "Interest income", _LINE, _MONEY),
    ("interestExpense", "Interest expense", _LINE, _MONEY),
    ("totalOtherIncomeExpensesNet", "Other income, net", _LINE, _MONEY),
    ("incomeBeforeTax", "Income before tax", _TOTAL, _MONEY),
    ("incomeTaxExpense", "Income tax", _LINE, _MONEY),
    ("netIncome", "Net income", _TOTAL, _MONEY),
    (None, "PER SHARE", _HEAD, None),
    ("eps", "EPS", _LINE, _PER_SHARE),
    ("epsDiluted", "EPS, diluted", _LINE, _PER_SHARE),
    ("weightedAverageShsOut", "Shares", _LINE, _SHARES),
    ("weightedAverageShsOutDil", "Shares, diluted", _LINE, _SHARES),
    (None, "OTHER", _HEAD, None),
    ("ebitda", "EBITDA", _LINE, _MONEY),
    ("depreciationAndAmortization", "Depreciation and amortization", _LINE, _MONEY),
)
_BALANCE: tuple[_StatementLine, ...] = (
    (None, "ASSETS", _HEAD, None),
    ("cashAndCashEquivalents", "Cash and equivalents", _LINE, _MONEY),
    ("shortTermInvestments", "Short-term investments", _LINE, _MONEY),
    ("netReceivables", "Receivables", _LINE, _MONEY),
    ("inventory", "Inventory", _LINE, _MONEY),
    ("prepaids", "Prepaids", _LINE, _MONEY),
    ("otherCurrentAssets", "Other current assets", _LINE, _MONEY),
    ("totalCurrentAssets", "Total current assets", _TOTAL, _MONEY),
    ("propertyPlantEquipmentNet", "Property, plant and equipment", _LINE, _MONEY),
    ("goodwill", "Goodwill", _LINE, _MONEY),
    ("intangibleAssets", "Intangible assets", _LINE, _MONEY),
    ("longTermInvestments", "Long-term investments", _LINE, _MONEY),
    ("taxAssets", "Tax assets", _LINE, _MONEY),
    ("otherNonCurrentAssets", "Other non-current assets", _LINE, _MONEY),
    ("totalNonCurrentAssets", "Total non-current assets", _TOTAL, _MONEY),
    ("totalAssets", "Total assets", _TOTAL, _MONEY),
    (None, "LIABILITIES", _HEAD, None),
    ("accountPayables", "Accounts payable", _LINE, _MONEY),
    ("accruedExpenses", "Accrued expenses", _LINE, _MONEY),
    ("shortTermDebt", "Short-term debt", _LINE, _MONEY),
    ("capitalLeaseObligationsCurrent", "Lease obligations, current", _LINE, _MONEY),
    ("taxPayables", "Tax payables", _LINE, _MONEY),
    ("deferredRevenue", "Deferred revenue", _LINE, _MONEY),
    ("otherCurrentLiabilities", "Other current liabilities", _LINE, _MONEY),
    ("totalCurrentLiabilities", "Total current liabilities", _TOTAL, _MONEY),
    ("longTermDebt", "Long-term debt", _LINE, _MONEY),
    ("capitalLeaseObligationsNonCurrent", "Lease obligations, non-current", _LINE, _MONEY),
    ("deferredRevenueNonCurrent", "Deferred revenue, non-current", _LINE, _MONEY),
    ("deferredTaxLiabilitiesNonCurrent", "Deferred tax liabilities", _LINE, _MONEY),
    ("otherNonCurrentLiabilities", "Other non-current liabilities", _LINE, _MONEY),
    ("totalNonCurrentLiabilities", "Total non-current liabilities", _TOTAL, _MONEY),
    ("totalLiabilities", "Total liabilities", _TOTAL, _MONEY),
    (None, "EQUITY", _HEAD, None),
    ("commonStock", "Common stock", _LINE, _MONEY),
    ("additionalPaidInCapital", "Additional paid-in capital", _LINE, _MONEY),
    ("retainedEarnings", "Retained earnings", _LINE, _MONEY),
    (
        "accumulatedOtherComprehensiveIncomeLoss",
        "Accumulated other comprehensive income",
        _LINE,
        _MONEY,
    ),
    ("treasuryStock", "Treasury stock", _LINE, _MONEY),
    ("totalStockholdersEquity", "Total stockholders' equity", _TOTAL, _MONEY),
    ("minorityInterest", "Minority interest", _LINE, _MONEY),
    ("totalLiabilitiesAndTotalEquity", "Total liabilities and equity", _TOTAL, _MONEY),
    (None, "OTHER", _HEAD, None),
    ("totalInvestments", "Total investments", _LINE, _MONEY),
    ("totalDebt", "Total debt", _LINE, _MONEY),
    ("netDebt", "Net debt", _LINE, _MONEY),
)
_CASHFLOW: tuple[_StatementLine, ...] = (
    (None, "OPERATING", _HEAD, None),
    ("netIncome", "Net income", _LINE, _MONEY),
    ("depreciationAndAmortization", "Depreciation and amortization", _LINE, _MONEY),
    ("deferredIncomeTax", "Deferred income tax", _LINE, _MONEY),
    ("stockBasedCompensation", "Stock-based compensation", _LINE, _MONEY),
    ("changeInWorkingCapital", "Change in working capital", _LINE, _MONEY),
    ("accountsReceivables", "Receivables", _SUB, _MONEY),
    ("inventory", "Inventory", _SUB, _MONEY),
    ("accountsPayables", "Payables", _SUB, _MONEY),
    ("otherWorkingCapital", "Other working capital", _SUB, _MONEY),
    ("otherNonCashItems", "Other non-cash items", _LINE, _MONEY),
    ("netCashProvidedByOperatingActivities", "Cash from operations", _TOTAL, _MONEY),
    (None, "INVESTING", _HEAD, None),
    ("investmentsInPropertyPlantAndEquipment", "Capital expenditure", _LINE, _MONEY),
    ("acquisitionsNet", "Acquisitions, net", _LINE, _MONEY),
    ("purchasesOfInvestments", "Purchases of investments", _LINE, _MONEY),
    ("salesMaturitiesOfInvestments", "Sales and maturities of investments", _LINE, _MONEY),
    ("otherInvestingActivities", "Other investing", _LINE, _MONEY),
    ("netCashProvidedByInvestingActivities", "Cash from investing", _TOTAL, _MONEY),
    (None, "FINANCING", _HEAD, None),
    ("netDebtIssuance", "Debt issued, net", _LINE, _MONEY),
    ("commonStockIssuance", "Stock issued", _LINE, _MONEY),
    ("commonStockRepurchased", "Stock repurchased", _LINE, _MONEY),
    ("netDividendsPaid", "Dividends paid", _LINE, _MONEY),
    ("otherFinancingActivities", "Other financing", _LINE, _MONEY),
    ("netCashProvidedByFinancingActivities", "Cash from financing", _TOTAL, _MONEY),
    (None, "CASH", _HEAD, None),
    ("effectOfForexChangesOnCash", "Effect of exchange rates", _LINE, _MONEY),
    ("netChangeInCash", "Net change in cash", _TOTAL, _MONEY),
    ("cashAtBeginningOfPeriod", "Cash at the start", _LINE, _MONEY),
    ("cashAtEndOfPeriod", "Cash at the end", _LINE, _MONEY),
    (None, "OTHER", _HEAD, None),
    ("freeCashFlow", "Free cash flow", _TOTAL, _MONEY),
    ("incomeTaxesPaid", "Income taxes paid", _LINE, _MONEY),
    ("interestPaid", "Interest paid", _LINE, _MONEY),
)

# Section 12.4: the answer, FMP's field, the line's label and its unit; a head has no answer, no
# field and no unit. Every ratio is a line.
type _RatioLine = tuple[str | None, str | None, str, str | None]

_RATIO_LINES: tuple[_RatioLine, ...] = (
    (None, None, "MARGINS", None),
    (_RATIOS, "grossProfitMargin", "Gross", _PERCENT),
    (_RATIOS, "ebitdaMargin", "EBITDA", _PERCENT),
    (_RATIOS, "operatingProfitMargin", "Operating", _PERCENT),
    (_RATIOS, "pretaxProfitMargin", "Pretax", _PERCENT),
    (_RATIOS, "netProfitMargin", "Net", _PERCENT),
    (None, None, "RETURNS", None),
    (_METRICS, "returnOnEquity", "ROE", _PERCENT),
    (_METRICS, "returnOnAssets", "ROA", _PERCENT),
    (_METRICS, "returnOnInvestedCapital", "ROIC", _PERCENT),
    (_METRICS, "returnOnCapitalEmployed", "ROCE", _PERCENT),
    (None, None, "VALUATION", None),
    (_RATIOS, "priceToEarningsRatio", "P/E", _MULTIPLE),
    (_RATIOS, "priceToEarningsGrowthRatio", "PEG", _RATIO),
    (_RATIOS, "priceToBookRatio", "P/B", _MULTIPLE),
    (_RATIOS, "priceToSalesRatio", "P/S", _MULTIPLE),
    (_RATIOS, "priceToFreeCashFlowRatio", "P/FCF", _MULTIPLE),
    (_METRICS, "evToSales", "EV/Sales", _MULTIPLE),
    (_METRICS, "evToEBITDA", "EV/EBITDA", _MULTIPLE),
    (_METRICS, "evToFreeCashFlow", "EV/FCF", _MULTIPLE),
    (_METRICS, "earningsYield", "Earnings yield", _PERCENT),
    (_METRICS, "freeCashFlowYield", "FCF yield", _PERCENT),
    (None, None, "FINANCIAL HEALTH", None),
    (_RATIOS, "debtToEquityRatio", "Debt to equity", _RATIO),
    (_METRICS, "netDebtToEBITDA", "Net debt to EBITDA", _RATIO),
    (_RATIOS, "currentRatio", "Current ratio", _RATIO),
    (_RATIOS, "quickRatio", "Quick ratio", _RATIO),
    (_RATIOS, "interestCoverageRatio", "Interest cover", _MULTIPLE),
    (None, None, "PER SHARE", None),
    (_RATIOS, "revenuePerShare", "Revenue", _PER_SHARE),
    (_RATIOS, "netIncomePerShare", "Net income", _PER_SHARE),
    (_RATIOS, "freeCashFlowPerShare", "Free cash flow", _PER_SHARE),
    (_RATIOS, "bookValuePerShare", "Book value", _PER_SHARE),
    (_RATIOS, "dividendPerShare", "Dividend", _PER_SHARE),
    (None, None, "DIVIDENDS", None),
    (_RATIOS, "dividendYield", "Yield", _PERCENT),
    (_RATIOS, "dividendPayoutRatio", "Payout", _PERCENT),
    (None, None, "EFFICIENCY", None),
    (_METRICS, "daysOfSalesOutstanding", "Days of sales outstanding", _DAYS),
    (_METRICS, "daysOfInventoryOutstanding", "Days of inventory", _DAYS),
    (_METRICS, "daysOfPayablesOutstanding", "Days of payables", _DAYS),
    (_METRICS, "cashConversionCycle", "Cash conversion cycle", _DAYS),
    (_METRICS, "capexToRevenue", "Capital expenditure to revenue", _PERCENT),
    (  # FMP's spelling
        _METRICS,
        "researchAndDevelopementToRevenue",
        "Research and development to revenue",
        _PERCENT,
    ),
    (_METRICS, "stockBasedCompensationToRevenue", "Stock pay to revenue", _PERCENT),
)


class _Line(NamedTuple):
    """A row of a table before its figures: the field it reads (``None`` for a head), its label,
    its name on the chart, its kind and its unit."""

    key: str | None
    label: str
    name: str | None
    kind: str
    unit: str | None


def statement(
    payload: Any,
    kind: StatementKind,
    currency: str,
    *,
    quarterly: bool = False,
    half_yearly: bool = False,
) -> Table:
    """The table of a statement's answer (``income-annual``, ``balance-quarter`` and so on): a
    column a dated row, by quarter (and by half-year) where ``quarterly`` (and ``half_yearly``)
    say so, and the lines of ``kind``; ``currency`` is the tab's."""
    periods = _in_order(dated(payload))
    columns = [
        _column((row,), when, currency, quarterly=quarterly, half_yearly=half_yearly)
        for row, when in periods
    ]
    return {"columns": columns, "rows": _rows(_STATEMENTS[kind], [row for row, _ in periods])}


def ratios(ratios: Any, metrics: Any, currency: str, limit: int) -> Table:
    """The Ratios table: the ``ratios`` and ``key-metrics`` answers by fiscal year joined by
    ``date``, the newest ``limit`` dates; ``currency`` is the tab's."""
    answers = {_RATIOS: _by_date(ratios), _METRICS: _by_date(metrics)}
    days = _newest(sorted(set(answers[_RATIOS]) | set(answers[_METRICS])), limit)
    columns = [
        _column([answer[day] for answer in answers.values() if day in answer], day, currency)
        for day in days
    ]
    periods = [
        {field: answers[name].get(day, {}).get(field) for name, field in _RATIO_FIELDS}
        for day in days
    ]
    return {"columns": columns, "rows": _rows(_RATIO_TABLE, periods)}


def segments(payload: Any, currency: str, limit: int) -> Table:
    """The table of a segment answer (``segments-product`` or ``segments-geographic``): its newest
    ``limit`` dated rows, a line a name, the lines by revenue; ``currency`` is the tab's."""
    periods = _newest(_in_order(dated(payload)), limit)
    columns = [_column((row,), when, currency) for row, when in periods]
    figures: list[Mapping[str, Any]] = [
        data if isinstance(data := row.get("data"), dict) else {} for row, _ in periods
    ]
    names = dict.fromkeys(name for data in figures for name in data)
    lines = [_Line(name, name, f"Revenue: {name}", _LINE, _MONEY) for name in names]
    return {"columns": columns, "rows": sorted(_rows(lines, figures), key=_by_revenue)}


def reported_currency(payload: Any) -> str | None:
    """The ``reportedCurrency`` of the answer's newest dated row; ``None`` where that row names
    none or the answer has no dated row."""
    newest = max(dated(payload), key=lambda pair: pair[1], default=None)
    return None if newest is None else text(newest[0].get("reportedCurrency"))


def period_ends(payload: Any) -> list[date]:
    """The days the answer's dated rows end, oldest first."""
    return sorted(when for _, when in dated(payload))


def _statement_lines(lines: tuple[_StatementLine, ...]) -> tuple[_Line, ...]:
    """A statement's lines, each named on the chart as in the table."""
    return tuple(
        _Line(key, label, None if key is None else label, kind, unit)
        for key, label, kind, unit in lines
    )


def _ratio_lines(lines: tuple[_RatioLine, ...]) -> tuple[_Line, ...]:
    """The ratios' lines, each named on the chart by the group it stands in (7.5)."""
    out: list[_Line] = []
    group = ""
    for _answer, key, label, unit in lines:
        if key is None:
            group = label
            out.append(_Line(None, label, None, _HEAD, None))
        else:
            out.append(_Line(key, label, _ratio_name(group, label), _LINE, unit))
    return tuple(out)


def _ratio_name(group: str, label: str) -> str:
    """A ratio's name on the chart from its group's head and its label (7.5)."""
    if group == "MARGINS":
        return f"{label} margin"
    if group == "PER SHARE":
        return f"{label} a share"
    if group == "DIVIDENDS":
        return f"Dividend {label.lower()}"
    return label


_STATEMENTS: dict[StatementKind, tuple[_Line, ...]] = {
    "income": _statement_lines(_INCOME),
    "balance": _statement_lines(_BALANCE),
    "cashflow": _statement_lines(_CASHFLOW),
}
_RATIO_TABLE = _ratio_lines(_RATIO_LINES)
# Each ratio's answer and field.
_RATIO_FIELDS = tuple(
    (answer, field) for answer, field, _, _ in _RATIO_LINES if answer is not None and field
)


def _rows(lines: Iterable[_Line], periods: Sequence[Mapping[str, Any]]) -> list[Row]:
    """The table's rows: a line's figure in each period is ``number`` of the period's field
    ``key``. A line whose every figure is ``None`` or 0 is left out, then a head with no line
    under it before the next head or the end."""
    rows: list[Row] = []
    for line in lines:
        if line.key is None:
            rows.append(line._asdict() | {"values": None})
            continue
        values = [number(period.get(line.key)) for period in periods]
        if all(value is None or value == 0 for value in values):
            continue
        rows.append(line._asdict() | {"values": values})
    return [
        row
        for index, row in enumerate(rows)
        if row["kind"] != _HEAD or (index + 1 < len(rows) and rows[index + 1]["kind"] != _HEAD)
    ]


def _column(
    rows: Sequence[Mapping[str, Any]],
    when: date,
    currency: str,
    *,
    quarterly: bool = False,
    half_yearly: bool = False,
) -> Column:
    """The column of a period ending ``when``, whose answers' rows are ``rows`` (one or two for a
    ratio's year, else one): the first ``fiscalYear`` among them that is a year, else the year of
    ``when``; by quarter after the first row's ``period``, ``Q2`` and ``Q4`` reading ``H1`` and
    ``H2`` by half-year; the first ``reportedCurrency`` that is a text, else ``currency``."""
    year = next(filter(None, (_fiscal_year(row.get("fiscalYear")) for row in rows)), when.year)
    period = text(rows[0].get("period")) if quarterly else None
    if period is not None and half_yearly:
        period = _HALVES.get(period, period)
    named = next(filter(None, (text(row.get("reportedCurrency")) for row in rows)), currency)
    return {
        "label": str(year) if period is None else f"{period} {year}",
        "end": when.isoformat(),
        "currency": named,
    }


def _fiscal_year(raw: Any) -> int | None:
    """``fiscalYear`` as a year from 1 to 9999, given as a whole number or as a text of digits;
    ``None`` for anything else (``"1e3"``, ``"-5"``, ``2026.5``), so that no text of an exponent
    is turned into a whole number of its size."""
    if isinstance(raw, str) and _DIGITS.fullmatch(raw.strip()) is None:
        return None
    year = whole(raw)
    return year if year is not None and 0 < year < 10_000 else None


def _in_order(rows: Iterable[tuple[dict[str, Any], date]]) -> list[tuple[dict[str, Any], date]]:
    """Dated rows in order of their date, oldest first, the answer's order kept on a tie."""
    return sorted(rows, key=lambda pair: pair[1])


def _by_date(payload: Any) -> dict[date, dict[str, Any]]:
    """An answer's rows by date, the first row of a date counting."""
    found: dict[date, dict[str, Any]] = {}
    for row, when in dated(payload):
        found.setdefault(when, row)
    return found


def _newest[T](items: Sequence[T], limit: int) -> list[T]:
    """The last ``limit`` of ``items``, ordered oldest first; none for a ``limit`` of 0 or less."""
    return list(items[max(len(items) - limit, 0) :])


def _by_revenue(row: Row) -> tuple[int, float, str]:
    """A segment's place: by the newest column's figure, largest first, then the lines with none
    there by their largest figure; a tie by name. A figure of 0 counts as none, as it does for
    leaving a line out, so a line kept holds at least one figure."""
    newest = row["values"][-1]
    if newest:
        return (0, -newest, row["key"])
    return (1, -max(value for value in row["values"] if value), row["key"])
