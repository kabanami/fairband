"""FMP's answers for the company page, one constant an endpoint, for one made-up company:
Lanternfield Optics (``LFOX``), which lists in US dollars and reports in New Taiwan dollars.

Every figure is invented; the shapes are FMP's stable routes' as stored (a list of rows), with the
fields the page reads and a few it does not. ``QUOTE``'s day (16 Nov 2026, UTC) is later than
``HISTORY``'s newest (13 Nov 2026). ``EARNINGS`` holds two future dates (14 Jan and 15 Apr 2027),
a past date without an actual (15 Oct 2026) and three reported quarters. ``NEWS``'s third story's
address is not a web address.

The Financials tab's ten answers are in New Taiwan dollars, newest row first as FMP gives them:
each statement by fiscal year (2023 to 2025, ending 31 Dec) and by quarter (Q4 2025 to Q2 2026,
a quarter apart), the ratios and the key metrics by fiscal year (2024 and 2025), and the revenue
by product and by region (2023 to 2025), whose rows give ``fiscalYear`` as a number and name no
currency, as FMP's segment answers do. Each statement holds a line FMP gives as 0 in every period,
which the tab leaves out.
"""

from typing import Any

SYMBOL = "LFOX"

PROFILE: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "companyName": "Lanternfield Optics Ltd",
        "ceo": "Mara Vellini",
        "website": "https://www.lanternfield.example",
        "description": (
            "Lanternfield Optics designs and makes precision lenses and optical sensors for "
            "cameras, cars and factory machines. It sells to device makers in Asia, Europe and "
            "North America."
        ),
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "TW",
        "fullTimeEmployees": "48210",
        "ipoDate": "1997-10-08",
        "exchange": "NYSE",
        "beta": 1.18,
        "averageVolume": 9412300,
        "marketCap": 412600000000,
        "currency": "USD",
        "isAdr": True,
    }
]

QUOTE: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "name": "Lanternfield Optics Ltd",
        "price": 182.4,
        "change": 2.15,
        "changePercentage": 1.1928,
        "volume": 8123400,
        "dayLow": 179.6,
        "dayHigh": 183.05,
        "yearHigh": 201.3,
        "yearLow": 121.75,
        "marketCap": 412600000000,
        "priceAvg50": 176.88,
        "priceAvg200": 158.42,
        "exchange": "NYSE",
        "open": 180.1,
        "previousClose": 180.25,
        "timestamp": 1794862800,  # 16 Nov 2026, 21:00 UTC
    }
]

BATCH_QUOTE: list[dict[str, Any]] = [
    {
        "symbol": "BRK-B",
        "name": "A share class in FMP's form",
        "price": 512.3,
        "change": -1.4,
        "changePercentage": -0.2725,
        "volume": 3012000,
        "dayLow": 509.8,
        "dayHigh": 514.6,
        "yearHigh": 540.2,
        "yearLow": 455.1,
        "marketCap": 1104000000000,
        "priceAvg50": 506.7,
        "priceAvg200": 497.3,
        "open": 513.0,
        "previousClose": 513.7,
        "timestamp": 1794862800,
    },
    QUOTE[0],
]

HISTORY: list[dict[str, Any]] = [
    {"symbol": SYMBOL, "date": day, "open": o, "high": h, "low": lo, "close": c, "volume": v}
    for day, o, h, lo, c, v in (
        ("2026-11-13", 179.0, 181.2, 178.4, 180.25, 7650200),
        ("2026-11-12", 177.5, 179.9, 176.8, 178.9, 8012300),
        ("2026-11-11", 176.0, 177.8, 175.1, 177.3, 6904100),
        ("2026-11-10", 176.2, 176.9, 174.9, 175.6, 7322800),
        ("2026-11-09", 174.5, 176.8, 174.0, 176.4, 6551900),
        ("2026-11-06", 173.1, 174.7, 172.2, 174.15, 9120400),
        ("2026-11-05", 173.6, 174.4, 172.0, 172.8, 8433700),
        ("2026-11-04", 171.5, 174.3, 171.0, 173.95, 7012600),
        ("2026-11-03", 170.4, 171.9, 169.8, 171.2, 6788500),
        ("2026-11-02", 169.2, 170.6, 168.5, 170.05, 7245100),
    )
]

EARNINGS: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "date": "2027-04-15",
        "epsActual": None,
        "epsEstimated": 2.31,
        "revenueActual": None,
        "revenueEstimated": 30150000000,
        "time": "bmo",
        "periodEnding": "2027-03-31",
        "confirmed": False,
    },
    {
        "symbol": SYMBOL,
        "date": "2027-01-14",
        "epsActual": None,
        "epsEstimated": 2.18,
        "revenueActual": None,
        "revenueEstimated": 28420000000,
        "time": "amc",
        "periodEnding": "2026-12-31",
        "confirmed": False,
    },
    {  # past, and FMP never filled its actuals
        "symbol": SYMBOL,
        "date": "2026-10-15",
        "epsActual": None,
        "epsEstimated": 2.05,
        "revenueActual": None,
        "revenueEstimated": 27300000000,
        "time": "amc",
        "periodEnding": "2026-09-30",
    },
    {
        "symbol": SYMBOL,
        "date": "2026-07-16",
        "epsActual": 1.97,
        "epsEstimated": 1.9,
        "revenueActual": 26710000000,
        "revenueEstimated": 26050000000,
        "time": "amc",
        "periodEnding": "2026-06-30",
        "confirmed": True,
    },
    {
        "symbol": SYMBOL,
        "date": "2026-04-16",
        "epsActual": 1.72,
        "epsEstimated": 1.75,
        "revenueActual": 24880000000,
        "revenueEstimated": 25100000000,
        "time": "amc",
        "periodEnding": "2026-03-31",
        "confirmed": True,
    },
    {
        "symbol": SYMBOL,
        "date": "2026-01-15",
        "epsActual": 1.64,
        "epsEstimated": 1.58,
        "revenueActual": 23940000000,
        "revenueEstimated": 23500000000,
        "time": "amc",
        "periodEnding": "2025-12-31",
        "confirmed": True,
    },
]

ESTIMATES: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "date": day,
        "revenueAvg": revenue,
        "epsAvg": eps,
        "epsLow": low,
        "epsHigh": high,
        "numAnalystsRevenue": revenue_analysts,
        "numAnalystsEps": eps_analysts,
    }
    for day, revenue, eps, low, high, revenue_analysts, eps_analysts in (
        ("2029-12-31", 6120000000000, 98.4, 81.2, 117.6, 6, 5),
        ("2028-12-31", 5310000000000, 84.1, 72.5, 96.8, 11, 10),
        ("2027-12-31", 4620000000000, 71.9, 64.0, 80.3, 17, 16),
        ("2026-12-31", 3990000000000, 61.2, 58.7, 63.9, 19, 18),
        ("2025-12-31", 3270000000000, 47.6, 46.9, 48.2, 20, 19),
    )
]

NEWS: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "publishedDate": "2026-11-13 18:42:10",
        "publisher": "Harbor Street Journal",
        "site": "harborstreet.example",
        "title": "Lanternfield Optics lifts its lens output for car makers",
        "text": "Lanternfield Optics said it would add a fourth line at its sensor plant.",
        "url": "https://harborstreet.example/lanternfield-output",
    },
    {
        "symbol": SYMBOL,
        "publishedDate": "2026-11-12 09:05:33",
        "publisher": "",
        "site": "lensdaily.example",
        "title": "Three lens makers to watch",
        "text": "A look at the makers of camera lenses after a strong quarter.",
        "url": "http://lensdaily.example/three-lens-makers",
    },
    {
        "symbol": SYMBOL,
        "publishedDate": "2026-11-10 22:17:56",
        "publisher": "Quayside Markets",
        "site": "quayside.example",
        "title": "Lanternfield Optics' October sales",
        "text": "Lanternfield Optics reported its sales for October.",
        "url": "javascript:alert(1)",
    },
]

RATIOS: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "grossProfitMarginTTM": 0.5912,
        "ebitdaMarginTTM": 0.6843,
        "operatingProfitMarginTTM": 0.4877,
        "pretaxProfitMarginTTM": 0.5034,
        "netProfitMarginTTM": 0.4321,
        "priceToEarningsRatioTTM": 24.6,
        "priceToEarningsGrowthRatioTTM": 0.88,
        "priceToBookRatioTTM": 6.72,
        "priceToSalesRatioTTM": 10.4,
        "priceToFreeCashFlowRatioTTM": 31.9,
        "debtToEquityRatioTTM": 0.214,
        "currentRatioTTM": 2.41,
        "quickRatioTTM": 2.05,
        "interestCoverageRatioTTM": 126.3,
        "dividendYieldTTM": 0.0137,
        "dividendPayoutRatioTTM": 0.3318,
        "dividendPerShareTTM": 19.5,
        "netIncomePerShareTTM": 59.8,
    }
]

KEY_METRICS: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "marketCap": 412600000000,
        "enterpriseValueTTM": 12480000000000,
        "evToSalesTTM": 10.1,
        "evToEBITDATTM": 14.8,
        "evToFreeCashFlowTTM": 30.7,
        "netDebtToEBITDATTM": -0.42,
        "returnOnEquityTTM": 0.3105,
        "returnOnAssetsTTM": 0.2016,
        "returnOnInvestedCapitalTTM": 0.2689,
        "returnOnCapitalEmployedTTM": 0.3342,
        "earningsYieldTTM": 0.0407,
        "freeCashFlowYieldTTM": 0.0313,
    }
]

GROWTH: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "date": "2025-12-31",
        "fiscalYear": "2025",
        "period": "FY",
        "reportedCurrency": "TWD",
        "revenueGrowth": 0.3381,
        "ebitdaGrowth": 0.3012,
        "epsdilutedGrowth": 0.4005,
        "freeCashFlowGrowth": 0.2214,
        "threeYRevenueGrowthPerShare": 0.952,
        "fiveYRevenueGrowthPerShare": 1.874,
        "tenYRevenueGrowthPerShare": 4.115,
        "threeYNetIncomeGrowthPerShare": 1.122,
        "fiveYNetIncomeGrowthPerShare": 2.406,
        "tenYNetIncomeGrowthPerShare": 6.31,
        "threeYOperatingCFGrowthPerShare": 0.873,
        "fiveYOperatingCFGrowthPerShare": 1.659,
        "tenYOperatingCFGrowthPerShare": 3.982,
        "threeYDividendperShareGrowthPerShare": 0.418,
        "fiveYDividendperShareGrowthPerShare": 0.775,
        "tenYDividendperShareGrowthPerShare": 1.583,
    },
    {
        "symbol": SYMBOL,
        "date": "2024-12-31",
        "fiscalYear": "2024",
        "period": "FY",
        "reportedCurrency": "TWD",
        "revenueGrowth": 0.1254,
        "ebitdaGrowth": 0.0987,
        "epsdilutedGrowth": 0.1418,
        "freeCashFlowGrowth": -0.0533,
        "threeYRevenueGrowthPerShare": 0.611,
        "fiveYRevenueGrowthPerShare": 1.302,
        "tenYRevenueGrowthPerShare": 3.274,
        "threeYNetIncomeGrowthPerShare": 0.704,
        "fiveYNetIncomeGrowthPerShare": 1.815,
        "tenYNetIncomeGrowthPerShare": 4.92,
        "threeYOperatingCFGrowthPerShare": 0.588,
        "fiveYOperatingCFGrowthPerShare": 1.247,
        "tenYOperatingCFGrowthPerShare": 3.105,
        "threeYDividendperShareGrowthPerShare": 0.333,
        "fiveYDividendperShareGrowthPerShare": 0.651,
        "tenYDividendperShareGrowthPerShare": 1.296,
    },
]

SCORES: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "reportedCurrency": "TWD",
        "altmanZScore": 11.86,
        "piotroskiScore": 7,
        "workingCapital": 1840000000000,
        "totalAssets": 7210000000000,
        "retainedEarnings": 4650000000000,
        "ebit": 1859000000000,
        "marketCap": 412600000000,
        "totalLiabilities": 2380000000000,
        "revenue": 3812000000000,
    }
]

PRICE_CHANGE: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "1D": 1.1928,
        "5D": 2.7713,
        "1M": 6.418,
        "3M": 12.905,
        "6M": 21.334,
        "ytd": 32.3,
        "1Y": 41.876,
        "3Y": 168.2,
        "5Y": 244.9,
        "10Y": 901.35,
        "max": 5120.4,
    }
]

TARGET: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "targetHigh": 240,
        "targetLow": 150,
        "targetConsensus": 205.6,
        "targetMedian": 210,
    }
]

GRADES: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "strongBuy": 3,
        "buy": 14,
        "hold": 4,
        "sell": 1,
        "strongSell": 0,
        "consensus": "Buy",
    }
]

DIVIDENDS: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "date": day,
        "recordDate": day,
        "paymentDate": paid,
        "declarationDate": declared,
        "adjDividend": 0.98,
        "dividend": 0.98,
        "yield": 1.37,
        "frequency": "Quarterly",
    }
    for day, paid, declared in (
        ("2026-09-17", "2026-10-09", "2026-08-13"),
        ("2026-06-12", "2026-07-10", "2026-05-14"),
        ("2026-03-17", "2026-04-09", "2026-02-12"),
        ("2025-12-11", "2026-01-08", "2025-11-13"),
    )
]

FLOAT: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "date": "2026-11-14 08:00:00",
        "freeFloat": 88.42,
        "floatShares": 2287000000,
        "outstandingShares": 2586500000,
    }
]

# The Financials tab's periods, newest first: a row's date, its fiscal year and its period.
_YEARS = (("2025-12-31", "2025", "FY"), ("2024-12-31", "2024", "FY"), ("2023-12-31", "2023", "FY"))
_QUARTERS = (
    ("2026-06-30", "2026", "Q2"),
    ("2026-03-31", "2026", "Q1"),
    ("2025-12-31", "2025", "Q4"),
)


def _by_period(
    periods: tuple[tuple[str, str, str], ...], figures: dict[str, tuple[float, ...]]
) -> list[dict[str, Any]]:
    """FMP's rows of an answer, one a period of ``periods``: its head, then each field's figure in
    that period, the figures given in the order of ``periods``."""
    return [
        {
            "date": day,
            "symbol": SYMBOL,
            "reportedCurrency": "TWD",
            "fiscalYear": year,
            "period": period,
        }
        | {field: values[index] for field, values in figures.items()}
        for index, (day, year, period) in enumerate(periods)
    ]


_SHARES = {
    "weightedAverageShsOut": (21500000000, 21500000000, 21500000000),
    "weightedAverageShsOutDil": (21530000000, 21530000000, 21530000000),
}

INCOME_ANNUAL = _by_period(
    _YEARS,
    {
        "revenue": (3270000000000, 2440000000000, 2030000000000),
        "costOfRevenue": (1800000000000, 1390000000000, 1190000000000),
        "grossProfit": (1470000000000, 1050000000000, 840000000000),
        "researchAndDevelopmentExpenses": (260000000000, 214000000000, 188000000000),
        "sellingGeneralAndAdministrativeExpenses": (150000000000, 131000000000, 117000000000),
        "otherExpenses": (0, 0, 0),  # FMP's 0 for a line it does not hold
        "operatingExpenses": (410000000000, 345000000000, 305000000000),
        "operatingIncome": (1060000000000, 705000000000, 535000000000),
        "interestIncome": (42000000000, 35000000000, 24000000000),
        "interestExpense": (12000000000, 13000000000, 14000000000),
        "incomeBeforeTax": (1090000000000, 727000000000, 545000000000),
        "incomeTaxExpense": (196000000000, 131000000000, 98000000000),
        "netIncome": (894000000000, 596000000000, 447000000000),
        "eps": (41.58, 27.72, 20.79),
        "epsDiluted": (41.52, 27.68, 20.76),
        **_SHARES,
        "ebitda": (1580000000000, 1170000000000, 960000000000),
        "depreciationAndAmortization": (520000000000, 465000000000, 425000000000),
    },
)

INCOME_QUARTER = _by_period(
    _QUARTERS,
    {
        "revenue": (912000000000, 861000000000, 884000000000),
        "costOfRevenue": (497000000000, 471000000000, 485000000000),
        "grossProfit": (415000000000, 390000000000, 399000000000),
        "researchAndDevelopmentExpenses": (69000000000, 67000000000, 68000000000),
        "sellingGeneralAndAdministrativeExpenses": (40000000000, 39000000000, 39000000000),
        "otherExpenses": (0, 0, 0),
        "operatingExpenses": (109000000000, 106000000000, 107000000000),
        "operatingIncome": (306000000000, 284000000000, 292000000000),
        "interestIncome": (11000000000, 11000000000, 11000000000),
        "interestExpense": (3000000000, 3000000000, 3000000000),
        "incomeBeforeTax": (314000000000, 292000000000, 300000000000),
        "incomeTaxExpense": (57000000000, 53000000000, 54000000000),
        "netIncome": (257000000000, 239000000000, 246000000000),
        "eps": (11.95, 11.12, 11.44),
        "epsDiluted": (11.94, 11.1, 11.43),
        **_SHARES,
        "ebitda": (448000000000, 422000000000, 428000000000),
        "depreciationAndAmortization": (142000000000, 138000000000, 136000000000),
    },
)

BALANCE_ANNUAL = _by_period(
    _YEARS,
    {
        "cashAndCashEquivalents": (1450000000000, 1180000000000, 960000000000),
        "netReceivables": (330000000000, 270000000000, 230000000000),
        "inventory": (290000000000, 250000000000, 220000000000),
        "totalCurrentAssets": (2280000000000, 1870000000000, 1550000000000),
        "propertyPlantEquipmentNet": (3900000000000, 3310000000000, 2880000000000),
        "goodwill": (0, 0, 0),
        "totalAssets": (7210000000000, 6060000000000, 5190000000000),
        "totalCurrentLiabilities": (820000000000, 700000000000, 610000000000),
        "longTermDebt": (910000000000, 930000000000, 950000000000),
        "totalLiabilities": (2380000000000, 2190000000000, 2030000000000),
        "totalStockholdersEquity": (4830000000000, 3870000000000, 3160000000000),
        "totalLiabilitiesAndTotalEquity": (7210000000000, 6060000000000, 5190000000000),
        "totalDebt": (1020000000000, 1050000000000, 1070000000000),
        "netDebt": (-430000000000, -130000000000, 110000000000),
    },
)

BALANCE_QUARTER = _by_period(
    _QUARTERS,
    {
        "cashAndCashEquivalents": (1610000000000, 1520000000000, 1450000000000),
        "netReceivables": (352000000000, 341000000000, 330000000000),
        "inventory": (305000000000, 298000000000, 290000000000),
        "totalCurrentAssets": (2492000000000, 2377000000000, 2280000000000),
        "propertyPlantEquipmentNet": (4210000000000, 4050000000000, 3900000000000),
        "goodwill": (0, 0, 0),
        "totalAssets": (7752000000000, 7467000000000, 7210000000000),
        "totalCurrentLiabilities": (868000000000, 844000000000, 820000000000),
        "longTermDebt": (905000000000, 908000000000, 910000000000),
        "totalLiabilities": (2438000000000, 2410000000000, 2380000000000),
        "totalStockholdersEquity": (5314000000000, 5057000000000, 4830000000000),
        "totalLiabilitiesAndTotalEquity": (7752000000000, 7467000000000, 7210000000000),
        "totalDebt": (1012000000000, 1016000000000, 1020000000000),
        "netDebt": (-598000000000, -504000000000, -430000000000),
    },
)

CASHFLOW_ANNUAL = _by_period(
    _YEARS,
    {
        "netIncome": (894000000000, 596000000000, 447000000000),
        "depreciationAndAmortization": (520000000000, 465000000000, 425000000000),
        "stockBasedCompensation": (18000000000, 15000000000, 13000000000),
        "changeInWorkingCapital": (-64000000000, -41000000000, -30000000000),
        "netCashProvidedByOperatingActivities": (1368000000000, 1035000000000, 855000000000),
        "investmentsInPropertyPlantAndEquipment": (-880000000000, -720000000000, -640000000000),
        "acquisitionsNet": (0, 0, 0),
        "netCashProvidedByInvestingActivities": (-930000000000, -760000000000, -690000000000),
        "netDividendsPaid": (-168000000000, -147000000000, -129000000000),
        "netCashProvidedByFinancingActivities": (-168000000000, -55000000000, -95000000000),
        "netChangeInCash": (270000000000, 220000000000, 70000000000),
        "freeCashFlow": (488000000000, 315000000000, 215000000000),
    },
)

CASHFLOW_QUARTER = _by_period(
    _QUARTERS,
    {
        "netIncome": (257000000000, 239000000000, 246000000000),
        "depreciationAndAmortization": (142000000000, 138000000000, 136000000000),
        "stockBasedCompensation": (5000000000, 5000000000, 5000000000),
        "changeInWorkingCapital": (-18000000000, -12000000000, -15000000000),
        "netCashProvidedByOperatingActivities": (386000000000, 370000000000, 372000000000),
        "investmentsInPropertyPlantAndEquipment": (-240000000000, -232000000000, -238000000000),
        "acquisitionsNet": (0, 0, 0),
        "netCashProvidedByInvestingActivities": (-252000000000, -256000000000, -250000000000),
        "netDividendsPaid": (-44000000000, -44000000000, -42000000000),
        "netCashProvidedByFinancingActivities": (-44000000000, -44000000000, -42000000000),
        "netChangeInCash": (90000000000, 70000000000, 80000000000),
        "freeCashFlow": (146000000000, 138000000000, 134000000000),
    },
)

RATIOS_ANNUAL = _by_period(
    _YEARS[:2],
    {
        "grossProfitMargin": (0.4495, 0.4303),
        "ebitdaMargin": (0.4832, 0.4795),
        "operatingProfitMargin": (0.3242, 0.2889),
        "netProfitMargin": (0.2734, 0.2443),
        "priceToEarningsRatio": (21.4, 24.9),
        "priceToBookRatio": (3.96, 3.84),
        "debtToEquityRatio": (0.2112, 0.2713),
        "currentRatio": (2.78, 2.67),
        "revenuePerShare": (152.09, 113.49),
        "dividendPerShare": (7.81, 6.84),
        "dividendYield": (0.0088, 0.0099),
        "dividendPayoutRatio": (0.1879, 0.2466),
    },
)

KEY_METRICS_ANNUAL = _by_period(
    _YEARS[:2],
    {
        "enterpriseValue": (18330000000000, 15320000000000),
        "returnOnEquity": (0.2055, 0.1696),
        "returnOnInvestedCapital": (0.1762, 0.1428),
        "evToEBITDA": (11.6, 13.1),
        "netDebtToEBITDA": (-0.27, -0.11),
        "daysOfInventoryOutstanding": (58.8, 65.6),
        "capexToRevenue": (0.2691, 0.2951),
        "researchAndDevelopementToRevenue": (0.0795, 0.0877),  # FMP's spelling
    },
)

SEGMENTS_PRODUCT: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "fiscalYear": year,
        "period": "FY",
        "reportedCurrency": None,
        "date": f"{year}-12-31",
        "data": {
            "Camera lenses": camera,
            "Automotive sensors": cars,
            "Industrial optics": machines,
        },
    }
    for year, camera, cars, machines in (
        (2025, 1610000000000, 1080000000000, 580000000000),
        (2024, 1300000000000, 720000000000, 420000000000),
        (2023, 1150000000000, 520000000000, 360000000000),
    )
]

SEGMENTS_GEOGRAPHIC: list[dict[str, Any]] = [
    {
        "symbol": SYMBOL,
        "fiscalYear": year,
        "period": "FY",
        "reportedCurrency": None,
        "date": f"{year}-12-31",
        "data": {"Asia": asia, "North America": america, "Europe": europe},
    }
    for year, asia, america, europe in (
        (2025, 1520000000000, 1030000000000, 720000000000),
        (2024, 1180000000000, 740000000000, 520000000000),
        (2023, 1010000000000, 600000000000, 420000000000),
    )
]
