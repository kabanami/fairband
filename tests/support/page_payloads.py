"""FMP's answers for the company page, one constant an endpoint, for one made-up company:
Lanternfield Optics (``LFOX``), which lists in US dollars and reports in New Taiwan dollars.

Every figure is invented; the shapes are FMP's stable routes' as stored (a list of rows), with the
fields the page reads and a few it does not. ``QUOTE``'s day (16 Nov 2026, UTC) is later than
``HISTORY``'s newest (13 Nov 2026). ``EARNINGS`` holds two future dates (14 Jan and 15 Apr 2027),
a past date without an actual (15 Oct 2026) and three reported quarters. ``NEWS``'s third story's
address is not a web address.
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
