"""The company page's figures from FMP's stored answers (the company page's design, 7.2, 8.3, 8.5,
9, 10.3, 10.4, 14.2 and 14.3): pure readers, a parsed payload in and plain data out, with no store,
network or clock. The page's reads hand them the newest stored answers: the Overview's and the
Estimates' for their figures, the Financials tab's for the head's quote alone, its tables having
their own readers (``page_financials``).

The rule: every figure is the answer's own field, shaped and never recomputed, but for ``yearly``,
which turns FMP's growth over three, five or ten years, a total, into a rate a year. A figure's
name is the page's own (camelCase), not FMP's.

- A number is a finite JSON number as given, an integer staying an integer (``number``): a
  boolean, a text such as ``"12"``, ``NaN``, an infinity and a missing field are ``None``, which
  the page draws as a dash. A multiple or the interest cover at 0 stays 0: the page draws that
  dash too. The employee count, which FMP sends as a text of digits (``"167000"``), and the growth's
  fiscal year (``"2025"``) are whole numbers read from a number or a text of digits. A close of the
  price history is read as the engine reads it (``normalize_fmp_observations.close_rows``), a
  number or a numeric text, so the chart draws the closes the company is valued on.
- Margins, returns, yields and growth are fractions as FMP gives them (0.4879); the free float and
  the price changes are percents as given (99.88).
- A money figure is ``{"value", "currency"}`` (``money``), as the design's 14.2 states it: in the
  reporting currency, the enterprise value, the revenue, the dividend a share and the consensus;
  in US dollars, every other (the quote, the price history, the earnings, the price target). The
  head's price and change (``head_quote``) stay plain numbers in US dollars. Nothing is converted.
- Days are ISO dates. The newest row of an answer is found by its date, not by its place in the
  answer: the growth's by ``date``, the dividends' by ``paymentDate``, else ``date``; the prices,
  the earnings and the consensus are put in order by date. The last payment is the latest
  ``paymentDate`` on or before today among the dividends that hold one, so neither a newest
  dividend declared without one nor a payment still to come hides an older payment. Today comes
  in as an argument, as it does for the next earnings date.
- An answer of the wrong shape (FMP's ``{"Error Message": ...}``, ``null``, a text, a list of
  anything but objects) reads as no answer: each reader gives its shape with ``None`` figures or
  an empty list. None raises on any JSON value.
"""

import math
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from fairband.vendors._fmp_parse import dated, objects, parse_date, text
from fairband.vendors.fmp import to_fmp_symbol
from fairband.vendors.normalize_fmp import close_rows

type Money = dict[str, Any]  # {"value": 182.4, "currency": "USD"}; a figure with no value is None

_USD = "USD"

_DIGITS = re.compile(r"[0-9]+")

# (the page's name, FMP's field)
_MARGINS = (
    ("gross", "grossProfitMarginTTM"),
    ("ebitda", "ebitdaMarginTTM"),
    ("operating", "operatingProfitMarginTTM"),
    ("pretax", "pretaxProfitMarginTTM"),
    ("net", "netProfitMarginTTM"),
)
_RETURNS = (
    ("roe", "returnOnEquityTTM"),
    ("roa", "returnOnAssetsTTM"),
    ("roic", "returnOnInvestedCapitalTTM"),
    ("roce", "returnOnCapitalEmployedTTM"),
)
_RATIO_MULTIPLES = (
    ("pe", "priceToEarningsRatioTTM"),
    ("peg", "priceToEarningsGrowthRatioTTM"),
    ("pb", "priceToBookRatioTTM"),
    ("ps", "priceToSalesRatioTTM"),
    ("pfcf", "priceToFreeCashFlowRatioTTM"),
)
_METRIC_MULTIPLES = (
    ("evSales", "evToSalesTTM"),
    ("evEbitda", "evToEBITDATTM"),
    ("evFcf", "evToFreeCashFlowTTM"),
    ("earningsYield", "earningsYieldTTM"),
    ("fcfYield", "freeCashFlowYieldTTM"),
)
_GROWTH = (
    ("revenue", "revenueGrowth"),
    ("ebitda", "ebitdaGrowth"),
    ("eps", "epsdilutedGrowth"),
    ("freeCashFlow", "freeCashFlowGrowth"),
)
_PER_SHARE = (  # (the page's name, the end of FMP's field)
    ("revenue", "RevenueGrowthPerShare"),
    ("netIncome", "NetIncomeGrowthPerShare"),
    ("cashFlow", "OperatingCFGrowthPerShare"),
    ("dividend", "DividendperShareGrowthPerShare"),
)
_SPANS = (("y3", "threeY", 3), ("y5", "fiveY", 5), ("y10", "tenY", 10))  # (name, prefix, years)
_TRADING = (
    ("open", "open"),
    ("previousClose", "previousClose"),
    ("dayLow", "dayLow"),
    ("dayHigh", "dayHigh"),
    ("yearLow", "yearLow"),
    ("yearHigh", "yearHigh"),
    ("average50", "priceAvg50"),
    ("average200", "priceAvg200"),
)
_PRICE_CHANGE = (
    ("d1", "1D"),
    ("d5", "5D"),
    ("m1", "1M"),
    ("m3", "3M"),
    ("m6", "6M"),
    ("ytd", "ytd"),
    ("y1", "1Y"),
    ("y3", "3Y"),
    ("y5", "5Y"),
    ("y10", "10Y"),
)
_TARGET = (
    ("consensus", "targetConsensus"),
    ("median", "targetMedian"),
    ("low", "targetLow"),
    ("high", "targetHigh"),
)
_RATINGS = (
    ("strongBuy", "strongBuy"),
    ("buy", "buy"),
    ("hold", "hold"),
    ("sell", "sell"),
    ("strongSell", "strongSell"),
)


def number(value: Any) -> float | None:
    """A finite JSON number as given, an integer staying an integer; ``None`` for anything else: a
    boolean, a text (``"12"``), ``NaN``, an infinity, an integer too large for a float."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        return value if math.isfinite(value) else None
    except OverflowError:  # an integer beyond a float's range
        return None


def money(value: Any, currency: str) -> Money | None:
    """``{"value", "currency"}`` for a ``number``; ``None`` without one."""
    figure = number(value)
    return None if figure is None else {"value": figure, "currency": currency}


def yearly(total: float | None, years: int) -> float | None:
    """The yearly rate of a total growth over ``years`` years, ``(1 + total) ** (1 / years) - 1``
    (the design's 14.3); ``None`` without a total or where ``1 + total`` is not above zero."""
    if total is None or 1 + total <= 0:
        return None
    return float((1 + total) ** (1 / years) - 1)


def quote_row(payload: Any, symbol: str) -> dict[str, Any] | None:
    """The row of a ``quote`` answer (a batch holds several) for ``symbol``: its ``symbol`` is the
    symbol's FMP form (``BRK-B`` for ``BRK.B``) or the symbol itself, as ``quote_observations``
    finds it; ``None`` when no row matches."""
    forms = (to_fmp_symbol(symbol), symbol)
    return next((row for row in objects(payload) if row.get("symbol") in forms), None)


def company(profile: Any) -> dict[str, Any]:
    """The Company block from the ``profile`` answer: the brief and the eight facts. The website is
    kept as given, whatever its scheme: the page makes a link only of a web address."""
    row = _first(profile)
    return {
        "brief": text(row.get("description")),
        "ceo": text(row.get("ceo")),
        "website": text(row.get("website")),
        "employees": _whole(row.get("fullTimeEmployees")),
        "listed": _day(row.get("ipoDate")),
        "sector": text(row.get("sector")),
        "industry": text(row.get("industry")),
        "country": text(row.get("country")),
        "exchange": text(row.get("exchange")),
    }


def statistics(
    answers: Mapping[str, Any],
    profile: Any,
    quote: Mapping[str, Any] | None,
    reporting: str,
    today: date,
) -> dict[str, Any]:
    """The Key statistics block, group by group (the design's 8.3). ``answers`` maps a page
    endpoint (``fetch.PAGE_ENDPOINTS``) to its parsed answer, an absent or ``None`` one being no
    answer; ``quote`` is the company's quote row (``quote_row``); ``reporting`` is the company's
    reporting currency. The growth is the newest fiscal year's; the dividend's frequency is the
    newest dividend's, and its last payment the latest ``paymentDate`` on or before ``today``
    that any row holds: a payment still to come is not a last payment."""
    ratios = _first(answers.get("ratios-ttm"))
    metrics = _first(answers.get("key-metrics-ttm"))
    scores = _first(answers.get("financial-scores"))
    floated = _first(answers.get("shares-float"))
    growth = _newest(answers.get("financial-growth"), "date")
    newest_dividend = _newest(answers.get("dividends"), "paymentDate", "date")
    last_paid = _last_payment(answers.get("dividends"), today)
    listed = _row(quote)
    about = _first(profile)
    return {
        "size": {
            "marketCap": money(listed.get("marketCap"), _USD),
            "enterpriseValue": money(metrics.get("enterpriseValueTTM"), reporting),
            "shares": number(floated.get("outstandingShares")),
            "freeFloat": number(floated.get("freeFloat")),
            "revenue": money(scores.get("revenue"), reporting),
            "employees": _whole(about.get("fullTimeEmployees")),
            "beta": number(about.get("beta")),
        },
        "margins": _numbers(ratios, _MARGINS),
        "returns": _numbers(metrics, _RETURNS),
        "valuation": _numbers(ratios, _RATIO_MULTIPLES) | _numbers(metrics, _METRIC_MULTIPLES),
        "health": {
            "debtToEquity": number(ratios.get("debtToEquityRatioTTM")),
            "netDebtToEbitda": number(metrics.get("netDebtToEBITDATTM")),
            "currentRatio": number(ratios.get("currentRatioTTM")),
            "quickRatio": number(ratios.get("quickRatioTTM")),
            "interestCover": number(ratios.get("interestCoverageRatioTTM")),
            "altmanZ": number(scores.get("altmanZScore")),
            "piotroski": number(scores.get("piotroskiScore")),
        },
        "growth": {"fiscalYear": _whole(growth.get("fiscalYear"))} | _numbers(growth, _GROWTH),
        "perShare": {
            name: {
                span: yearly(number(growth.get(prefix + suffix)), years)
                for span, prefix, years in _SPANS
            }
            for name, suffix in _PER_SHARE
        },
        "dividends": {
            "yield": number(ratios.get("dividendYieldTTM")),
            "payout": number(ratios.get("dividendPayoutRatioTTM")),
            "perShare": money(ratios.get("dividendPerShareTTM"), reporting),
            "frequency": text(newest_dividend.get("frequency")),
            "lastPayment": _iso(last_paid),
        },
    }


def trading(quote: Mapping[str, Any] | None, profile: Any, next_day: str | None) -> dict[str, Any]:
    """The Trading group (the design's 8.5) from the quote row: its eight money rows and its
    volume, with the profile's average volume and ``next_day``, the day of ``next_earnings``."""
    row = _row(quote)
    figures: dict[str, Any] = {name: money(row.get(key), _USD) for name, key in _TRADING}
    return figures | {
        "volume": number(row.get("volume")),
        "averageVolume": number(_first(profile).get("averageVolume")),
        "nextEarnings": next_day,
    }


def head_quote(quote: Mapping[str, Any] | None) -> dict[str, Any]:
    """The head's figures from the quote row (the design's 7.2 and 10.4), which every tab draws:
    ``price``, ``change`` and ``changePercent`` (FMP's ``changePercentage``, a percent as given),
    plain numbers in US dollars, and ``day``, the UTC date of the row's ``timestamp``. Each is
    ``None`` where the row lacks it, and every one without a row or with a row of the wrong
    shape."""
    row = _row(quote)
    return {
        "price": number(row.get("price")),
        "change": number(row.get("change")),
        "changePercent": number(row.get("changePercentage")),
        "day": _iso(_utc_day(row.get("timestamp"))),
    }


def price_change(payload: Any) -> dict[str, float | None]:
    """The price changes of ``stock-price-change`` over a day to ten years, percents as given."""
    return _numbers(_first(payload), _PRICE_CHANGE)


def prices(history: Any, quote: Mapping[str, Any] | None) -> list[list[Any]]:
    """``[day, close, volume]`` for each row of the price history with a date and a close, as the
    engine finds its closes (``normalize_fmp_observations.close_rows``: the flat list or FMP's
    older ``{"historical": [...]}`` object, a close given as a number or as numeric text), oldest
    first, the volume read by ``number``, ``None`` where the row has none; then the quote row's
    price and volume on its day where that day is later than the history's newest (the design's
    8.4). Without a history the quote adds nothing. A close beyond a float's range (``"1e400"``,
    a JSON integer of 400 digits), which the engine's reader gives as an infinity, is left out as
    a row with no close is, since an answer's JSON holds no infinity."""
    days = [
        (when, close, number(row.get("volume")))
        for row, when, close in close_rows(history)
        if math.isfinite(close)
    ]
    days.sort(key=lambda day: day[0])
    out: list[list[Any]] = [[when.isoformat(), close, volume] for when, close, volume in days]
    latest = _row(quote)
    day, price = _utc_day(latest.get("timestamp")), number(latest.get("price"))
    if days and day is not None and price is not None and day > days[-1][0]:
        out.append([day.isoformat(), price, number(latest.get("volume"))])
    return out


def stories(payload: Any) -> list[dict[str, Any]]:
    """Each story of the ``news`` answer in its order (newest first, as stored): its day (the
    date of ``publishedDate``), title, publisher (``publisher``, else ``site``) and address. The
    address is kept as given, whatever its scheme: the page makes a link only of a web address."""
    return [
        {
            "day": _day(row.get("publishedDate")),
            "title": text(row.get("title")),
            "publisher": text(row.get("publisher")) or text(row.get("site")),
            "url": text(row.get("url")),
        }
        for row in objects(payload)
    ]


def next_earnings(payload: Any, today: date) -> dict[str, Any] | None:
    """The next earnings date of the ``earnings`` answer by the rule of
    ``normalize_fmp_observations.earnings_observations``: the earliest row dated on or after
    ``today`` with no actual EPS. Its ``time`` as FMP gives it (``"amc"``, ``"bmo"`` or other) and
    ``confirmed`` where FMP gives a boolean, else ``None``; ``None`` without such a row."""
    found = _next_row(payload, today)
    return None if found is None else _next_date(*found)


def earnings(payload: Any, today: date) -> dict[str, Any]:
    """The Earnings block (the design's 9): ``next_earnings``, and the table's rows: the next date
    first where there is one, with its two estimates and no actuals, then every row with an actual
    EPS (an ``epsActual`` that is not null, the test ``next_earnings`` shares), newest first. Every
    figure is in US dollars."""
    rows: list[dict[str, Any]] = []
    found = _next_row(payload, today)
    if found is not None:
        rows.append(_earnings_row(*found, reported=False))
    reported = [(when, row) for row, when in dated(payload) if row.get("epsActual") is not None]
    reported.sort(key=lambda pair: pair[0], reverse=True)
    rows.extend(_earnings_row(when, row, reported=True) for when, row in reported)
    return {"next": None if found is None else _next_date(*found), "rows": rows}


def consensus(payload: Any, after: date | None, reporting: str) -> list[dict[str, Any]]:
    """The Consensus estimates block (the design's 9): one row for each fiscal year of the
    ``estimates-annual`` answer that ends after ``after`` (the newest fiscal year on file; every
    year without one), oldest first. The fiscal year is the year of its ``date``; the four money
    figures are in the reporting currency; the analysts are ``numAnalystsEps``."""
    years = sorted(
        ((when, row) for row, when in dated(payload) if after is None or when > after),
        key=lambda pair: pair[0],
    )
    return [
        {
            "fiscalYear": when.year,
            "revenue": money(row.get("revenueAvg"), reporting),
            "eps": money(row.get("epsAvg"), reporting),
            "epsLow": money(row.get("epsLow"), reporting),
            "epsHigh": money(row.get("epsHigh"), reporting),
            "analysts": number(row.get("numAnalystsEps")),
        }
        for when, row in years
    ]


def target(payload: Any) -> dict[str, Any]:
    """The price target of ``price-target-consensus``, in US dollars."""
    row = _first(payload)
    return {name: money(row.get(key), _USD) for name, key in _TARGET}


def ratings(payload: Any) -> dict[str, Any]:
    """The analysts' consensus word (``"Buy"``) and the five counts of ``grades-consensus``."""
    row = _first(payload)
    return {"consensus": text(row.get("consensus"))} | _numbers(row, _RATINGS)


def _first(payload: Any) -> Mapping[str, Any]:
    """An answer's one row: the first object of a list, or the payload itself where it is an
    object (FMP has sent the profile as both); an empty row for anything else."""
    if isinstance(payload, dict):
        return payload
    return next(objects(payload), {})


def _row(quote: Any) -> Mapping[str, Any]:
    """The quote row as given, or an empty row where it is none."""
    return quote if isinstance(quote, Mapping) else {}


def _newest(payload: Any, *fields: str) -> Mapping[str, Any]:
    """The object row of a list answer with the latest date, a row's date being the first of
    ``fields`` it holds as a date; a row with none is passed over, a tie goes to the first row,
    and an empty row is given where no row has a date."""
    newest: tuple[date, dict[str, Any]] | None = None
    for row in objects(payload):
        when = next(filter(None, (parse_date(row.get(field)) for field in fields)), None)
        if when is not None and (newest is None or when > newest[0]):
            newest = (when, row)
    return {} if newest is None else newest[1]


def _last_payment(payload: Any, today: date) -> date | None:
    """The latest ``paymentDate`` on or before ``today`` among the dividends that hold one."""
    days = (parse_date(row.get("paymentDate")) for row in objects(payload))
    return max((day for day in days if day is not None and day <= today), default=None)


def _numbers(
    row: Mapping[str, Any], fields: tuple[tuple[str, str], ...]
) -> dict[str, float | None]:
    """``number`` of each FMP field of ``fields``, under the page's name."""
    return {name: number(row.get(key)) for name, key in fields}


def _whole(value: Any) -> int | None:
    """A whole number from a JSON number with no fraction or from a text of the digits 0 to 9,
    spaces around it allowed (FMP's ``fullTimeEmployees`` is ``"167000"``, its ``fiscalYear``
    ``"2025"``); ``None`` for anything else, a negative number among them."""
    if isinstance(value, str):
        digits = value.strip()
        if _DIGITS.fullmatch(digits) is None:
            return None
        try:
            return int(digits)
        except ValueError:  # more digits than the interpreter converts
            return None
    figure = number(value)
    if figure is None or figure < 0 or not figure.is_integer():
        return None
    return int(figure)


def _next_row(payload: Any, today: date) -> tuple[date, dict[str, Any]] | None:
    """The earliest ``earnings`` row dated on or after ``today`` with no actual EPS, and its
    date; the first such row on a tie."""
    upcoming = [
        (when, row)
        for row, when in dated(payload)
        if row.get("epsActual") is None and when >= today
    ]
    return min(upcoming, key=lambda pair: pair[0], default=None)


def _next_date(when: date, row: Mapping[str, Any]) -> dict[str, Any]:
    """``next_earnings``'s answer for the row of the next date."""
    confirmed = row.get("confirmed")
    return {
        "day": when.isoformat(),
        "time": text(row.get("time")),
        "confirmed": confirmed if isinstance(confirmed, bool) else None,
    }


def _earnings_row(when: date, row: Mapping[str, Any], *, reported: bool) -> dict[str, Any]:
    """One row of the Earnings table, its actuals ``None`` where it is not ``reported``."""
    return {
        "day": when.isoformat(),
        "eps": money(row.get("epsActual"), _USD) if reported else None,
        "epsEstimate": money(row.get("epsEstimated"), _USD),
        "revenue": money(row.get("revenueActual"), _USD) if reported else None,
        "revenueEstimate": money(row.get("revenueEstimated"), _USD),
    }


def _utc_day(raw: Any) -> date | None:
    """The UTC date of a Unix ``timestamp`` in seconds; ``None`` without one in range."""
    seconds = number(raw)
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(seconds, UTC).date()
    except (OverflowError, OSError, ValueError):
        return None


def _day(raw: Any) -> str | None:
    """The ISO date of an ISO date or date-time text (``"2026-11-11 12:17:56"``)."""
    return _iso(parse_date(raw))


def _iso(when: date | None) -> str | None:
    return None if when is None else when.isoformat()
