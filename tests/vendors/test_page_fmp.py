"""The company page's payload readers against the synthetic answers of ``support.page_payloads``:
each figure from its FMP field, the newest rows found by their dates, the quote's row and day,
each money figure's currency, and an answer of the wrong shape read as no figure."""

import json
from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from support import page_payloads as p

from fairband.refresh.fetch import PAGE_ENDPOINTS
from fairband.vendors.page_fmp import (
    company,
    consensus,
    earnings,
    money,
    next_earnings,
    number,
    price_change,
    prices,
    quote_row,
    ratings,
    statistics,
    stories,
    target,
    trading,
    yearly,
)

TODAY = date(2026, 11, 16)
NEWEST_YEAR = date(2025, 12, 31)  # the newest fiscal year on file
ROW = p.QUOTE[0]
ANSWERS: dict[str, Any] = {
    "ratios-ttm": p.RATIOS,
    "key-metrics-ttm": p.KEY_METRICS,
    "financial-growth": p.GROWTH,
    "financial-scores": p.SCORES,
    "price-change": p.PRICE_CHANGE,
    "price-target": p.TARGET,
    "grades": p.GRADES,
    "dividends": p.DIVIDENDS,
    "shares-float": p.FLOAT,
    "news": p.NEWS,
}


def usd(value: float) -> dict[str, Any]:
    return {"value": value, "currency": "USD"}


def twd(value: float) -> dict[str, Any]:
    return {"value": value, "currency": "TWD"}


def is_money(tree: Any) -> bool:
    return isinstance(tree, dict) and set(tree) == {"value", "currency"}


def blank(tree: Any) -> Any:
    """The tree's shape with every figure, a money figure among them, as ``None``."""
    if isinstance(tree, dict) and not is_money(tree):
        return {key: blank(value) for key, value in tree.items()}
    return None


def monies(tree: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[tuple[Any, ...], str]]:
    """Each money figure's path in the tree and its currency."""
    if is_money(tree):
        yield path, tree["currency"]
    elif isinstance(tree, dict):
        for key, value in tree.items():
            yield from monies(value, (*path, key))
    elif isinstance(tree, list):
        for index, value in enumerate(tree):
            yield from monies(value, (*path, index))


@pytest.mark.parametrize("value", [None, "12", True, float("nan"), float("inf"), [], {}])
def test_number_refuses_what_is_not_a_finite_number(value: Any) -> None:
    assert number(value) is None


def test_number_keeps_a_finite_number_as_given() -> None:
    assert number(0) == 0 and isinstance(number(0), int)
    assert number(-2.5) == -2.5
    assert number(167000) == 167000
    assert number(float("-inf")) is None and number(False) is None
    assert number(10**400) is None  # an integer no float holds


def test_money() -> None:
    assert money(19.5, "TWD") == {"value": 19.5, "currency": "TWD"}
    assert money(0, "USD") == {"value": 0, "currency": "USD"}
    assert money("19.5", "TWD") is None and money(None, "USD") is None


def test_yearly() -> None:
    assert yearly(2.314, 10) == pytest.approx(0.1273, abs=1e-4)
    assert yearly(-1.0, 3) is None and yearly(-1.5, 3) is None and yearly(None, 3) is None


def test_yearly_of_a_fall_and_of_none() -> None:
    assert yearly(-0.271, 3) == pytest.approx(-0.1000, abs=1e-4)
    assert yearly(0, 5) == 0


def test_the_quote_row_is_found_in_a_batch() -> None:
    assert quote_row(p.BATCH_QUOTE, p.SYMBOL) is p.QUOTE[0]
    share_class = quote_row(p.BATCH_QUOTE, "BRK.B")
    assert share_class is not None and share_class["symbol"] == "BRK-B"
    assert quote_row(p.QUOTE, p.SYMBOL) is p.QUOTE[0]
    assert quote_row(p.BATCH_QUOTE, "ZZZZ") is None


def test_company() -> None:
    assert company(p.PROFILE) == {
        "brief": p.PROFILE[0]["description"],
        "ceo": "Mara Vellini",
        "website": "https://www.lanternfield.example",
        "employees": 48210,
        "listed": "1997-10-08",
        "sector": "Technology",
        "industry": "Semiconductors",
        "country": "TW",
        "exchange": "NYSE",
    }


def test_company_reads_a_bare_profile_object_and_keeps_any_address_as_text() -> None:
    profile = {**p.PROFILE[0], "website": "javascript:alert(1)", "ceo": "  ", "ipoDate": "soon"}
    answer = company(profile)
    assert answer["website"] == "javascript:alert(1)"  # the page draws it as text
    assert answer["ceo"] is None and answer["listed"] is None
    assert answer["sector"] == "Technology"


@pytest.mark.parametrize(
    ("employees", "count"),
    [("48210", 48210), (" 48210 ", 48210), (48210, 48210), (48210.0, 48210), ("0", 0)],
)
def test_the_employees_are_a_whole_number_from_a_number_or_a_text_of_digits(
    employees: Any, count: int
) -> None:
    profile = [{**p.PROFILE[0], "fullTimeEmployees": employees}]
    assert company(profile)["employees"] == count
    assert isinstance(company(profile)["employees"], int)
    assert statistics({}, profile, None, "USD")["size"]["employees"] == count


@pytest.mark.parametrize(
    "employees",
    [None, "", "48,210", "4.8e4", "-5", "48210.5", "٤٨٢١٠", "9" * 5000, -5, 48210.5, True, [], {}],
)
def test_employees_that_are_not_a_whole_number_read_none(employees: Any) -> None:
    profile = [{**p.PROFILE[0], "fullTimeEmployees": employees}]
    assert company(profile)["employees"] is None
    assert statistics({}, profile, None, "USD")["size"]["employees"] is None


def test_statistics() -> None:
    assert statistics(ANSWERS, p.PROFILE, ROW, "TWD") == {
        "size": {
            "marketCap": usd(412600000000),
            "enterpriseValue": twd(12480000000000),
            "shares": 2586500000,
            "freeFloat": 88.42,
            "revenue": twd(3812000000000),
            "employees": 48210,
            "beta": 1.18,
        },
        "margins": {
            "gross": 0.5912,
            "ebitda": 0.6843,
            "operating": 0.4877,
            "pretax": 0.5034,
            "net": 0.4321,
        },
        "returns": {"roe": 0.3105, "roa": 0.2016, "roic": 0.2689, "roce": 0.3342},
        "valuation": {
            "pe": 24.6,
            "peg": 0.88,
            "pb": 6.72,
            "ps": 10.4,
            "pfcf": 31.9,
            "evSales": 10.1,
            "evEbitda": 14.8,
            "evFcf": 30.7,
            "earningsYield": 0.0407,
            "fcfYield": 0.0313,
        },
        "health": {
            "debtToEquity": 0.214,
            "netDebtToEbitda": -0.42,
            "currentRatio": 2.41,
            "quickRatio": 2.05,
            "interestCover": 126.3,
            "altmanZ": 11.86,
            "piotroski": 7,
        },
        "growth": {
            "fiscalYear": 2025,
            "revenue": 0.3381,
            "ebitda": 0.3012,
            "eps": 0.4005,
            "freeCashFlow": 0.2214,
        },
        "perShare": {
            name: {
                span: pytest.approx(rate, abs=1e-6)
                for span, rate in zip(("y3", "y5", "y10"), rates, strict=True)
            }
            for name, rates in (
                ("revenue", (0.24976, 0.235086, 0.177293)),
                ("netIncome", (0.285036, 0.277759, 0.22009)),
                ("cashFlow", (0.232667, 0.216028, 0.174195)),
                ("dividend", (0.123463, 0.121604, 0.099544)),
            )
        },
        "dividends": {
            "yield": 0.0137,
            "payout": 0.3318,
            "perShare": twd(19.5),
            "frequency": "Quarterly",
            "lastPayment": "2026-10-09",
        },
    }


def test_the_newest_growth_and_dividend_rows_are_found_by_date_not_by_place() -> None:
    oldest_first = {
        **ANSWERS,
        "financial-growth": p.GROWTH[::-1],
        "dividends": p.DIVIDENDS[::-1],
    }
    answer = statistics(oldest_first, p.PROFILE, ROW, "TWD")
    assert answer["growth"]["fiscalYear"] == 2025
    assert answer["growth"]["revenue"] == 0.3381
    assert answer["dividends"]["lastPayment"] == "2026-10-09"
    assert answer == statistics(ANSWERS, p.PROFILE, ROW, "TWD")


def test_the_last_payment_is_an_older_row_s_under_a_newest_row_without_one() -> None:
    declared = {"date": "2026-12-11", "paymentDate": "", "frequency": "Irregular"}
    paid = {**p.DIVIDENDS[0], "frequency": "Semi-Annual"}  # paid 9 Oct 2026
    stored = {**ANSWERS, "dividends": [declared, paid]}
    dividends = statistics(stored, p.PROFILE, ROW, "TWD")["dividends"]
    assert dividends["lastPayment"] == "2026-10-09"
    assert dividends["frequency"] == "Irregular"  # the newest row's, dated by its date


def test_a_dividend_without_a_payment_date_is_placed_by_its_date() -> None:
    declared = {"date": "2026-12-11", "paymentDate": "", "frequency": "Irregular"}
    undated = {"paymentDate": None, "date": None, "frequency": "Monthly"}
    stored = {**ANSWERS, "dividends": [undated, *p.DIVIDENDS, declared]}
    dividends = statistics(stored, p.PROFILE, ROW, "TWD")["dividends"]
    assert dividends["frequency"] == "Irregular" and dividends["lastPayment"] == "2026-10-09"
    early = {**declared, "date": "2026-10-01"}  # before the newest payment date
    stored = {**ANSWERS, "dividends": [early, *p.DIVIDENDS]}
    dividends = statistics(stored, p.PROFILE, ROW, "TWD")["dividends"]
    assert dividends["frequency"] == "Quarterly" and dividends["lastPayment"] == "2026-10-09"
    stored = {**ANSWERS, "dividends": [declared, early]}  # no row holds a payment date
    dividends = statistics(stored, p.PROFILE, ROW, "TWD")["dividends"]
    assert dividends["frequency"] == "Irregular" and dividends["lastPayment"] is None


def test_a_growth_row_without_a_date_is_passed_over() -> None:
    undated = {**p.GROWTH[1], "date": "", "fiscalYear": "2026"}
    stored = {**ANSWERS, "financial-growth": [undated, p.GROWTH[1]]}
    assert statistics(stored, p.PROFILE, ROW, "TWD")["growth"]["fiscalYear"] == 2024


def test_a_field_that_is_not_a_finite_number_reads_none() -> None:
    ratios = json.loads(
        '[{"grossProfitMarginTTM": "0.59", "netProfitMarginTTM": NaN, '
        '"ebitdaMarginTTM": null, "pretaxProfitMarginTTM": true}]'
    )
    margins = statistics({**ANSWERS, "ratios-ttm": ratios}, p.PROFILE, ROW, "TWD")["margins"]
    assert margins == dict.fromkeys(("gross", "ebitda", "operating", "pretax", "net"))


def test_an_endpoint_absent_or_none_reads_as_no_answer() -> None:
    absent = statistics({}, p.PROFILE, ROW, "TWD")
    assert absent == statistics(dict.fromkeys(PAGE_ENDPOINTS), p.PROFILE, ROW, "TWD")
    assert absent["size"] == {
        "marketCap": usd(412600000000),
        "enterpriseValue": None,
        "shares": None,
        "freeFloat": None,
        "revenue": None,
        "employees": 48210,
        "beta": 1.18,
    }
    assert absent["growth"] == dict.fromkeys(
        ("fiscalYear", "revenue", "ebitda", "eps", "freeCashFlow")
    )


def test_interest_cover_is_kept_as_given() -> None:
    ratios = [{**p.RATIOS[0], "interestCoverageRatioTTM": 0, "priceToEarningsRatioTTM": 0}]
    answer = statistics({**ANSWERS, "ratios-ttm": ratios}, p.PROFILE, ROW, "TWD")
    assert answer["health"]["interestCover"] == 0
    assert answer["valuation"]["pe"] == 0


def test_trading() -> None:
    assert trading(ROW, p.PROFILE, "2027-01-14") == {
        "open": usd(180.1),
        "previousClose": usd(180.25),
        "dayLow": usd(179.6),
        "dayHigh": usd(183.05),
        "yearLow": usd(121.75),
        "yearHigh": usd(201.3),
        "average50": usd(176.88),
        "average200": usd(158.42),
        "volume": 8123400,
        "averageVolume": 9412300,
        "nextEarnings": "2027-01-14",
        "price": 182.4,
        "change": 2.15,
        "changePercent": 1.1928,
        "day": "2026-11-16",
    }


def test_trading_without_a_timestamp_has_no_day() -> None:
    row = {key: value for key, value in ROW.items() if key != "timestamp"}
    assert trading(row, p.PROFILE, None)["day"] is None
    assert trading({**ROW, "timestamp": 1e300}, p.PROFILE, None)["day"] is None


def test_price_change() -> None:
    assert price_change(p.PRICE_CHANGE) == {
        "d1": 1.1928,
        "d5": 2.7713,
        "m1": 6.418,
        "m3": 12.905,
        "m6": 21.334,
        "ytd": 32.3,
        "y1": 41.876,
        "y3": 168.2,
        "y5": 244.9,
        "y10": 901.35,
    }


def test_prices() -> None:
    assert prices(p.HISTORY, ROW) == [
        ["2026-11-02", 170.05, 7245100],
        ["2026-11-03", 171.2, 6788500],
        ["2026-11-04", 173.95, 7012600],
        ["2026-11-05", 172.8, 8433700],
        ["2026-11-06", 174.15, 9120400],
        ["2026-11-09", 176.4, 6551900],
        ["2026-11-10", 175.6, 7322800],
        ["2026-11-11", 177.3, 6904100],
        ["2026-11-12", 178.9, 8012300],
        ["2026-11-13", 180.25, 7650200],
        ["2026-11-16", 182.4, 8123400],
    ]


def test_a_day_without_a_close_is_left_out_and_one_without_a_volume_kept() -> None:
    history = [
        {"date": "2026-11-13", "close": "180.25", "volume": 7650200},
        {"date": "2026-11-12", "close": 178.9},
        {"date": "", "close": 177.3, "volume": 6904100},
    ]
    assert prices(history, None) == [["2026-11-12", 178.9, None]]


def test_the_quote_s_day_is_added_when_it_is_the_later_and_only_then() -> None:
    assert prices(p.HISTORY, ROW)[-1] == ["2026-11-16", 182.4, 8123400]
    for timestamp in (1794603600, 1794517200):  # 13 Nov, the newest day, and 12 Nov
        dated = prices(p.HISTORY, {**ROW, "timestamp": timestamp})
        assert len(dated) == 10 and dated[-1] == ["2026-11-13", 180.25, 7650200]
    untimed = {key: value for key, value in ROW.items() if key != "timestamp"}
    assert len(prices(p.HISTORY, untimed)) == 10
    assert len(prices(p.HISTORY, {**ROW, "price": None})) == 10
    assert len(prices(p.HISTORY, None)) == 10
    assert prices([], ROW) == []  # no history, no newest day for the quote's to follow
    no_volume = {key: value for key, value in ROW.items() if key != "volume"}
    assert prices(p.HISTORY, no_volume)[-1] == ["2026-11-16", 182.4, None]


def test_stories() -> None:
    assert stories(p.NEWS) == [
        {
            "day": "2026-11-13",
            "title": "Lanternfield Optics lifts its lens output for car makers",
            "publisher": "Harbor Street Journal",
            "url": "https://harborstreet.example/lanternfield-output",
        },
        {
            "day": "2026-11-12",
            "title": "Three lens makers to watch",
            "publisher": "lensdaily.example",
            "url": "http://lensdaily.example/three-lens-makers",
        },
        {
            "day": "2026-11-10",
            "title": "Lanternfield Optics' October sales",
            "publisher": "Quayside Markets",
            "url": "javascript:alert(1)",  # the page draws it as text
        },
    ]


def test_next_earnings() -> None:
    assert next_earnings(p.EARNINGS, TODAY) == {
        "day": "2027-01-14",
        "time": "amc",
        "confirmed": False,
    }


def test_the_next_earnings_date_is_the_soonest() -> None:
    assert next_earnings(p.EARNINGS[::-1], TODAY) == next_earnings(p.EARNINGS, TODAY)
    past = date(2026, 10, 1)  # the row of 15 Oct, which has no actual, is then the soonest
    assert next_earnings(p.EARNINGS, past) == {
        "day": "2026-10-15",
        "time": "amc",
        "confirmed": None,
    }
    on_the_day = next_earnings(p.EARNINGS, date(2027, 1, 14))
    assert on_the_day is not None and on_the_day["day"] == "2027-01-14"
    later = next_earnings(p.EARNINGS, date(2027, 1, 15))
    assert later == {"day": "2027-04-15", "time": "bmo", "confirmed": False}
    assert next_earnings(p.EARNINGS, date(2027, 4, 16)) is None


def test_earnings() -> None:
    assert earnings(p.EARNINGS, TODAY) == {
        "next": {"day": "2027-01-14", "time": "amc", "confirmed": False},
        "rows": [
            {
                "day": "2027-01-14",
                "eps": None,
                "epsEstimate": usd(2.18),
                "revenue": None,
                "revenueEstimate": usd(28420000000),
            },
            {
                "day": "2026-07-16",
                "eps": usd(1.97),
                "epsEstimate": usd(1.9),
                "revenue": usd(26710000000),
                "revenueEstimate": usd(26050000000),
            },
            {
                "day": "2026-04-16",
                "eps": usd(1.72),
                "epsEstimate": usd(1.75),
                "revenue": usd(24880000000),
                "revenueEstimate": usd(25100000000),
            },
            {
                "day": "2026-01-15",
                "eps": usd(1.64),
                "epsEstimate": usd(1.58),
                "revenue": usd(23940000000),
                "revenueEstimate": usd(23500000000),
            },
        ],
    }


def test_the_reported_rows_are_newest_first_in_any_order() -> None:
    assert earnings(p.EARNINGS[::-1], TODAY) == earnings(p.EARNINGS, TODAY)


def test_earnings_without_a_next_date_hold_the_reported_rows_alone() -> None:
    answer = earnings(p.EARNINGS, date(2027, 5, 1))
    assert answer["next"] is None
    assert [row["day"] for row in answer["rows"]] == ["2026-07-16", "2026-04-16", "2026-01-15"]


def test_consensus() -> None:
    assert consensus(p.ESTIMATES, NEWEST_YEAR, "TWD") == [
        {
            "fiscalYear": 2026,
            "revenue": twd(3990000000000),
            "eps": twd(61.2),
            "epsLow": twd(58.7),
            "epsHigh": twd(63.9),
            "analysts": 18,
        },
        {
            "fiscalYear": 2027,
            "revenue": twd(4620000000000),
            "eps": twd(71.9),
            "epsLow": twd(64.0),
            "epsHigh": twd(80.3),
            "analysts": 16,
        },
        {
            "fiscalYear": 2028,
            "revenue": twd(5310000000000),
            "eps": twd(84.1),
            "epsLow": twd(72.5),
            "epsHigh": twd(96.8),
            "analysts": 10,
        },
        {
            "fiscalYear": 2029,
            "revenue": twd(6120000000000),
            "eps": twd(98.4),
            "epsLow": twd(81.2),
            "epsHigh": twd(117.6),
            "analysts": 5,
        },
    ]


def test_consensus_without_a_year_on_file_keeps_every_row() -> None:
    years = [row["fiscalYear"] for row in consensus(p.ESTIMATES, None, "TWD")]
    assert years == [2025, 2026, 2027, 2028, 2029]
    assert consensus(p.ESTIMATES, date(2029, 12, 31), "TWD") == []


def test_target() -> None:
    assert target(p.TARGET) == {
        "consensus": usd(205.6),
        "median": usd(210),
        "low": usd(150),
        "high": usd(240),
    }


def test_ratings() -> None:
    assert ratings(p.GRADES) == {
        "consensus": "Buy",
        "strongBuy": 3,
        "buy": 14,
        "hold": 4,
        "sell": 1,
        "strongSell": 0,
    }


@pytest.mark.parametrize("payload", [None, {}, [], {"Error Message": "x"}, "text", [None], [[]]])
def test_every_reader_answers_on_a_payload_of_the_wrong_shape(payload: Any) -> None:
    stored = dict.fromkeys(PAGE_ENDPOINTS, payload)
    shaped = [
        (company(payload), company(p.PROFILE)),
        (
            statistics(stored, payload, payload, "TWD"),
            statistics(ANSWERS, p.PROFILE, ROW, "TWD"),
        ),
        (trading(payload, payload, None), trading(ROW, p.PROFILE, "2027-01-14")),
        (price_change(payload), price_change(p.PRICE_CHANGE)),
        (target(payload), target(p.TARGET)),
        (ratings(payload), ratings(p.GRADES)),
    ]
    for wrong, right in shaped:
        assert wrong == blank(right)
    assert quote_row(payload, p.SYMBOL) is None
    assert prices(payload, payload) == []
    assert stories(payload) == []
    assert next_earnings(payload, TODAY) is None
    assert earnings(payload, TODAY) == {"next": None, "rows": []}
    assert consensus(payload, NEWEST_YEAR, "TWD") == []


@pytest.mark.parametrize("row", [None, "text", 7, [], [None]])
def test_a_row_of_the_wrong_shape_in_a_list_is_passed_over(row: Any) -> None:
    assert stories([row, *p.NEWS]) == stories(p.NEWS)
    assert prices([row, *p.HISTORY], ROW) == prices(p.HISTORY, ROW)
    assert earnings([row, *p.EARNINGS], TODAY) == earnings(p.EARNINGS, TODAY)
    assert consensus([row, *p.ESTIMATES], None, "TWD") == consensus(p.ESTIMATES, None, "TWD")
    assert quote_row([row, *p.BATCH_QUOTE], p.SYMBOL) is p.QUOTE[0]


def test_the_reporting_currency_is_on_four_figures_and_usd_on_the_rest() -> None:
    answers = {
        "statistics": statistics(ANSWERS, p.PROFILE, ROW, "TWD"),
        "trading": trading(ROW, p.PROFILE, "2027-01-14"),
        "earnings": earnings(p.EARNINGS, TODAY),
        "consensus": consensus(p.ESTIMATES, NEWEST_YEAR, "TWD"),
        "target": target(p.TARGET),
    }
    found = list(monies(answers))
    reported = {path for path, currency in found if currency == "TWD"}
    in_dollars = {path for path, currency in found if currency == "USD"}
    assert len(found) == len(reported) + len(in_dollars)
    assert reported == {
        ("statistics", "size", "enterpriseValue"),
        ("statistics", "size", "revenue"),
        ("statistics", "dividends", "perShare"),
        *(
            ("consensus", year, name)
            for year in range(4)
            for name in ("revenue", "eps", "epsLow", "epsHigh")
        ),
    }
    trading_rows = ("open", "previousClose", "dayLow", "dayHigh", "yearLow", "yearHigh")
    assert in_dollars == {
        ("statistics", "size", "marketCap"),
        *(("trading", name) for name in (*trading_rows, "average50", "average200")),
        ("earnings", "rows", 0, "epsEstimate"),
        ("earnings", "rows", 0, "revenueEstimate"),
        *(
            ("earnings", "rows", row, name)
            for row in (1, 2, 3)
            for name in ("eps", "epsEstimate", "revenue", "revenueEstimate")
        ),
        *(("target", name) for name in ("consensus", "median", "low", "high")),
    }
