"""Build the Financials tab's mockup page from the gathered data.

    python build_fin.py <gathered.json> <template.html> <out.html>

The page holds the company's figures as JSON; the template draws them. A throwaway."""

import json
import sys
from pathlib import Path

src, template, out = (Path(arg) for arg in sys.argv[1:4])
data = json.loads(src.read_text())
stored = data["stored"]

# kind: t total, l line, s sub-line, h section head, p per share, n share count (millions)
INCOME = [
    ("revenue", "Revenue", "t"),
    ("costOfRevenue", "Cost of revenue", "l"),
    ("grossProfit", "Gross profit", "t"),
    ("researchAndDevelopmentExpenses", "Research and development", "l"),
    ("sellingGeneralAndAdministrativeExpenses", "Selling, general and administrative", "l"),
    ("generalAndAdministrativeExpenses", "General and administrative", "s"),
    ("sellingAndMarketingExpenses", "Selling and marketing", "s"),
    ("otherExpenses", "Other expenses", "l"),
    ("operatingExpenses", "Operating expenses", "l"),
    ("operatingIncome", "Operating income", "t"),
    ("interestIncome", "Interest income", "l"),
    ("interestExpense", "Interest expense", "l"),
    ("totalOtherIncomeExpensesNet", "Other income, net", "l"),
    ("incomeBeforeTax", "Income before tax", "t"),
    ("incomeTaxExpense", "Income tax", "l"),
    ("netIncome", "Net income", "t"),
    (None, "Per share", "h"),
    ("eps", "EPS", "p"),
    ("epsDiluted", "EPS, diluted", "p"),
    ("weightedAverageShsOut", "Shares", "n"),
    ("weightedAverageShsOutDil", "Shares, diluted", "n"),
    (None, "Other", "h"),
    ("ebitda", "EBITDA", "l"),
    ("depreciationAndAmortization", "Depreciation and amortization", "l"),
]
BALANCE = [
    (None, "Assets", "h"),
    ("cashAndCashEquivalents", "Cash and equivalents", "l"),
    ("shortTermInvestments", "Short-term investments", "l"),
    ("netReceivables", "Receivables", "l"),
    ("inventory", "Inventory", "l"),
    ("prepaids", "Prepaids", "l"),
    ("otherCurrentAssets", "Other current assets", "l"),
    ("totalCurrentAssets", "Total current assets", "t"),
    ("propertyPlantEquipmentNet", "Property, plant and equipment", "l"),
    ("goodwill", "Goodwill", "l"),
    ("intangibleAssets", "Intangible assets", "l"),
    ("longTermInvestments", "Long-term investments", "l"),
    ("taxAssets", "Tax assets", "l"),
    ("otherNonCurrentAssets", "Other non-current assets", "l"),
    ("totalNonCurrentAssets", "Total non-current assets", "t"),
    ("totalAssets", "Total assets", "t"),
    (None, "Liabilities", "h"),
    ("accountPayables", "Accounts payable", "l"),
    ("accruedExpenses", "Accrued expenses", "l"),
    ("shortTermDebt", "Short-term debt", "l"),
    ("capitalLeaseObligationsCurrent", "Lease obligations, current", "l"),
    ("taxPayables", "Tax payables", "l"),
    ("deferredRevenue", "Deferred revenue", "l"),
    ("otherCurrentLiabilities", "Other current liabilities", "l"),
    ("totalCurrentLiabilities", "Total current liabilities", "t"),
    ("longTermDebt", "Long-term debt", "l"),
    ("capitalLeaseObligationsNonCurrent", "Lease obligations, non-current", "l"),
    ("deferredRevenueNonCurrent", "Deferred revenue, non-current", "l"),
    ("deferredTaxLiabilitiesNonCurrent", "Deferred tax liabilities", "l"),
    ("otherNonCurrentLiabilities", "Other non-current liabilities", "l"),
    ("totalNonCurrentLiabilities", "Total non-current liabilities", "t"),
    ("totalLiabilities", "Total liabilities", "t"),
    (None, "Equity", "h"),
    ("commonStock", "Common stock", "l"),
    ("additionalPaidInCapital", "Additional paid-in capital", "l"),
    ("retainedEarnings", "Retained earnings", "l"),
    ("accumulatedOtherComprehensiveIncomeLoss", "Accumulated other comprehensive income", "l"),
    ("treasuryStock", "Treasury stock", "l"),
    ("totalStockholdersEquity", "Total stockholders' equity", "t"),
    ("minorityInterest", "Minority interest", "l"),
    ("totalLiabilitiesAndTotalEquity", "Total liabilities and equity", "t"),
    (None, "Other", "h"),
    ("totalInvestments", "Total investments", "l"),
    ("totalDebt", "Total debt", "l"),
    ("netDebt", "Net debt", "l"),
]
CASHFLOW = [
    (None, "Operating", "h"),
    ("netIncome", "Net income", "l"),
    ("depreciationAndAmortization", "Depreciation and amortization", "l"),
    ("deferredIncomeTax", "Deferred income tax", "l"),
    ("stockBasedCompensation", "Stock-based compensation", "l"),
    ("changeInWorkingCapital", "Change in working capital", "l"),
    ("accountsReceivables", "Receivables", "s"),
    ("inventory", "Inventory", "s"),
    ("accountsPayables", "Payables", "s"),
    ("otherWorkingCapital", "Other working capital", "s"),
    ("otherNonCashItems", "Other non-cash items", "l"),
    ("netCashProvidedByOperatingActivities", "Cash from operations", "t"),
    (None, "Investing", "h"),
    ("investmentsInPropertyPlantAndEquipment", "Capital expenditure", "l"),
    ("acquisitionsNet", "Acquisitions, net", "l"),
    ("purchasesOfInvestments", "Purchases of investments", "l"),
    ("salesMaturitiesOfInvestments", "Sales and maturities of investments", "l"),
    ("otherInvestingActivities", "Other investing", "l"),
    ("netCashProvidedByInvestingActivities", "Cash from investing", "t"),
    (None, "Financing", "h"),
    ("netDebtIssuance", "Debt issued, net", "l"),
    ("commonStockIssuance", "Stock issued", "l"),
    ("commonStockRepurchased", "Stock repurchased", "l"),
    ("netDividendsPaid", "Dividends paid", "l"),
    ("otherFinancingActivities", "Other financing", "l"),
    ("netCashProvidedByFinancingActivities", "Cash from financing", "t"),
    (None, "Cash", "h"),
    ("effectOfForexChangesOnCash", "Effect of exchange rates", "l"),
    ("netChangeInCash", "Net change in cash", "t"),
    ("cashAtBeginningOfPeriod", "Cash at the start", "l"),
    ("cashAtEndOfPeriod", "Cash at the end", "l"),
    (None, "Other", "h"),
    ("freeCashFlow", "Free cash flow", "t"),
    ("incomeTaxesPaid", "Income taxes paid", "l"),
    ("interestPaid", "Interest paid", "l"),
]
# unit: % percent, x multiple, r plain ratio, p per share, d days
RATIOS = [
    (None, "Margins", "h", None),
    ("grossProfitMargin", "Gross", "%", "ratios"),
    ("ebitdaMargin", "EBITDA", "%", "ratios"),
    ("operatingProfitMargin", "Operating", "%", "ratios"),
    ("pretaxProfitMargin", "Pretax", "%", "ratios"),
    ("netProfitMargin", "Net", "%", "ratios"),
    (None, "Returns", "h", None),
    ("returnOnEquity", "ROE", "%", "key-metrics"),
    ("returnOnAssets", "ROA", "%", "key-metrics"),
    ("returnOnInvestedCapital", "ROIC", "%", "key-metrics"),
    ("returnOnCapitalEmployed", "ROCE", "%", "key-metrics"),
    (None, "Valuation", "h", None),
    ("priceToEarningsRatio", "P/E", "x", "ratios"),
    ("priceToBookRatio", "P/B", "x", "ratios"),
    ("priceToSalesRatio", "P/S", "x", "ratios"),
    ("priceToFreeCashFlowRatio", "P/FCF", "x", "ratios"),
    ("evToSales", "EV/Sales", "x", "key-metrics"),
    ("evToEBITDA", "EV/EBITDA", "x", "key-metrics"),
    ("evToFreeCashFlow", "EV/FCF", "x", "key-metrics"),
    ("earningsYield", "Earnings yield", "%", "key-metrics"),
    ("freeCashFlowYield", "FCF yield", "%", "key-metrics"),
    (None, "Financial health", "h", None),
    ("debtToEquityRatio", "Debt to equity", "r", "ratios"),
    ("netDebtToEBITDA", "Net debt to EBITDA", "r", "key-metrics"),
    ("currentRatio", "Current ratio", "r", "ratios"),
    ("quickRatio", "Quick ratio", "r", "ratios"),
    ("interestCoverageRatio", "Interest cover", "x", "ratios"),
    (None, "Per share", "h", None),
    ("revenuePerShare", "Revenue", "p", "ratios"),
    ("netIncomePerShare", "Net income", "p", "ratios"),
    ("freeCashFlowPerShare", "Free cash flow", "p", "ratios"),
    ("bookValuePerShare", "Book value", "p", "ratios"),
    ("dividendPerShare", "Dividend", "p", "ratios"),
    (None, "Dividends", "h", None),
    ("dividendYield", "Yield", "%", "ratios"),
    ("dividendPayoutRatio", "Payout", "%", "ratios"),
    (None, "Efficiency", "h", None),
    ("daysOfSalesOutstanding", "Days of sales outstanding", "d", "key-metrics"),
    ("daysOfInventoryOutstanding", "Days of inventory", "d", "key-metrics"),
    ("daysOfPayablesOutstanding", "Days of payables", "d", "key-metrics"),
    ("cashConversionCycle", "Cash conversion cycle", "d", "key-metrics"),
    ("capexToRevenue", "Capital expenditure to revenue", "%", "key-metrics"),
    ("researchAndDevelopementToRevenue", "Research and development to revenue", "%", "key-metrics"),
    ("stockBasedCompensationToRevenue", "Stock pay to revenue", "%", "key-metrics"),
]


def columns(rows: list[dict], quarterly: bool) -> list[dict]:
    """The periods oldest first: a label and the day the period ends."""
    ordered = sorted(rows, key=lambda r: r["date"])
    return [
        {
            "label": (f"{r['period']} {r['fiscalYear']}" if quarterly else str(r["fiscalYear"])),
            "end": r["date"],
        }
        for r in ordered
    ]


def statement(endpoint: str, spec: list[tuple], quarterly: bool) -> dict:
    rows = sorted(stored[endpoint]["payload"], key=lambda r: r["date"])
    out_rows = []
    for field, label, kind in spec:
        if field is None:
            out_rows.append({"label": label, "kind": "h"})
            continue
        scale = 1 if kind == "p" else 1e6
        values = [None if r.get(field) is None else r[field] / scale for r in rows]
        if all(v in (None, 0) for v in values):
            continue  # a line the company does not report
        out_rows.append({"label": label, "kind": kind, "values": values})
    # a section head with no line under it goes
    kept = [
        row
        for i, row in enumerate(out_rows)
        if row["kind"] != "h" or (i + 1 < len(out_rows) and out_rows[i + 1]["kind"] != "h")
    ]
    return {
        "columns": columns(rows, quarterly),
        "rows": kept,
        "currency": rows[-1]["reportedCurrency"],
    }


def ratios() -> dict:
    by_year: dict[str, dict] = {}
    for route in ("ratios", "key-metrics"):
        for row in data["fmp"][route]:
            by_year.setdefault(row["date"], {"date": row["date"], "fiscalYear": row["fiscalYear"]})[
                route
            ] = row
    years = [by_year[day] for day in sorted(by_year)]
    out_rows = []
    for field, label, unit, route in RATIOS:
        if field is None:
            out_rows.append({"label": label, "kind": "h"})
            continue
        values = [(y.get(route) or {}).get(field) for y in years]
        if all(v in (None, 0) for v in values):
            continue
        out_rows.append({"label": label, "kind": "l", "unit": unit, "values": values})
    kept = [
        row
        for i, row in enumerate(out_rows)
        if row["kind"] != "h" or (i + 1 < len(out_rows) and out_rows[i + 1]["kind"] != "h")
    ]
    cols = [{"label": str(y["fiscalYear"]), "end": y["date"]} for y in years]
    return {"columns": cols, "rows": kept}


def segments(endpoint: str, years: int = 11) -> dict:
    rows = sorted(stored[endpoint]["payload"], key=lambda r: r["date"])[-years:]
    names: dict[str, float] = {}
    for r in rows:
        for name, value in (r.get("data") or {}).items():
            names[name] = max(names.get(name, 0), value or 0)
    newest = rows[-1].get("data") or {}
    order = sorted(names, key=lambda n: (-(newest.get(n) or 0), -names[n]))
    out_rows = [
        {"label": name, "kind": "l", "values": [(r.get("data") or {}).get(name) for r in rows]}
        for name in order
    ]
    out_rows = [
        {**row, "values": [None if v is None else v / 1e6 for v in row["values"]]}
        for row in out_rows
    ]
    return {
        "columns": [{"label": str(r["fiscalYear"]), "end": r["date"]} for r in rows],
        "rows": out_rows,
    }


detail = data["detail"]
company = detail.get("company") or {}
result = detail.get("result") or {}
page = {
    "symbol": data["symbol"],
    "name": company.get("name") or data["symbol"],
    "sub": " · ".join(
        str(part)
        for part in (company.get("exchange"), company.get("sector"), company.get("industry"))
        if part
    ),
    "price": result.get("price"),
    "phase": (result.get("phase") or {}).get("phase")
    if isinstance(result.get("phase"), dict)
    else result.get("phase"),
    "moat": detail.get("moat"),
    "logo": data.get("logo"),
    "income": {
        "annual": statement("income-annual", INCOME, False),
        "quarter": statement("income-quarter", INCOME, True),
    },
    "balance": {
        "annual": statement("balance-annual", BALANCE, False),
        "quarter": statement("balance-quarter", BALANCE, True),
    },
    "cashflow": {
        "annual": statement("cashflow-annual", CASHFLOW, False),
        "quarter": statement("cashflow-quarter", CASHFLOW, True),
    },
    "ratios": ratios(),
    "product": segments("segments-product"),
    "region": segments("segments-geographic"),
}
html = template.read_text().replace("/*__DATA__*/null", json.dumps(page, separators=(",", ":")))
out.write_text(html)
print("wrote", out.name, out.stat().st_size, "bytes")
print(
    "head:",
    page["name"],
    "|",
    page["sub"],
    "|",
    page["price"],
    "|",
    page["phase"],
    "|",
    page["moat"],
    "|",
    "logo" if page["logo"] else "no logo",
)
for key in ("income", "balance", "cashflow"):
    for period in ("annual", "quarter"):
        t = page[key][period]
        print(
            key,
            period,
            len(t["columns"]),
            "columns",
            sum(1 for r in t["rows"] if r["kind"] != "h"),
            "lines",
            t["columns"][0]["label"],
            "to",
            t["columns"][-1]["label"],
        )
print(
    "ratios",
    len(page["ratios"]["columns"]),
    "columns",
    sum(1 for r in page["ratios"]["rows"] if r["kind"] != "h"),
    "lines",
)
print("product", [r["label"] for r in page["product"]["rows"]])
print("region", [r["label"] for r in page["region"]["rows"]])
