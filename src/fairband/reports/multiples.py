"""The multiples history (spec 2026-11-06 Tier 2, 13.7; ``method.md`` 16.7): the two P/E series a
report reads the price against, as the read serves them and the refs resolve them.

- The trailing P/E (``pe``): built from FMP's data (spec 2026-11-19 6.3), the three answers the
  pass-through stores for the P/E history (``refresh.passthrough.series_answers``): the daily
  closes, the quarterly income statements and, for a company in another currency, the pair's
  closes (``trailing_series``). The stored series is the one of the newest usable answer of each,
  whatever its age (``stored_trailing``).
- The forward P/E (``pe_forward``): the multiples log's forward P/E by day; a row with none has no
  point.

Each series holds the points of the ten years to its newest day, from the same day ten years
before, and over them the four statistics, ``avg_10y``, ``median_10y``, ``high_10y`` and
``low_10y``, ``None`` each without a point. ``since`` is the series' first day on file, a loss day
or a row with no forward P/E included: the first close the trailing series could read, or when
the log began.

The trailing series (``built_series``, the text of ``method.md`` 16.7): a day's P/E is its close ÷
the trailing diluted EPS of that day, the sum of ``epsDiluted`` over the four quarters, or the two
half-years of a company that reports twice a year (``cadence_of`` on the periods' ends, quarterly
when they give none), with the latest period ends at or before the day, so the EPS changes at a
period's end. The sum stands only when the periods are consecutive by that spacing
(``consecutive_periods``), each holds its EPS and each is in the reporting currency, a period that
names none counting as in it, as 4.2 reads a statement; a day with no such sum is no row. A
company in another currency has each period's EPS brought into USD at the pair's last close at or
before the period's end (units of the currency per USD, so the EPS ÷ the rate), and the day's
close, in USD, ÷ the sum of those USD figures: a past period's earnings stand at the rate of their
time, the day's rate is not read, and a period with no rate at or before its end leaves every
year that holds it with no sum. A day whose trailing EPS is not above zero is a loss: a row with
no point, and nothing fills its days, so the series keeps the gap. A close or a rate that is not
a positive number is not read. No split rule and no share-basis rule applies: FMP's closes are
adjusted for splits and its EPS restated for them.
"""

import json
import math
import sqlite3
from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean, median
from typing import Any

from fairband.engine.anchor import PERIODS_PER_YEAR, consecutive_periods
from fairband.refresh.inputs_statements import cadence_of
from fairband.refresh.passthrough import FMP, series_answers
from fairband.store.currency import reporting_currency
from fairband.store.multiples import MultiplesRow, multiples_log_for
from fairband.store.vendor import latest_response, response_payload
from fairband.vendors._fmp_parse import dated, number, text
from fairband.vendors.normalize_fmp import fx_closes, price_closes

SERIES = ("pe", "pe_forward")
STATS = ("avg_10y", "median_10y", "high_10y", "low_10y")
WINDOW_YEARS = 10
_USD = "USD"


@dataclass(frozen=True)
class Series:
    """The points oldest first, each day with its P/E; the statistics by name; the first day."""

    points: tuple[tuple[date, float], ...]
    stats: dict[str, float | None]
    since: date | None


@dataclass(frozen=True)
class PeriodEps:
    """One statement period of the trailing EPS: its end, its diluted EPS (``epsDiluted``;
    ``None`` when the line is missing or holds no finite number) and its reported currency."""

    end: date
    eps: float | None
    currency: str | None


def trailing_series(parts: Mapping[str, Any], currency: str) -> Series | None:
    """The trailing series of the P/E history's answers, the payloads by part (``closes``,
    ``quarters`` and ``rates``), for a company reporting in ``currency`` (``built_series``): the
    closes and the pair's closes that are positive numbers. ``None`` when the closes or the
    quarters cannot be read (missing, or not a list), or, in another currency, the rates; an empty
    list reads, a series with no point."""
    closes, periods = parts.get("closes"), period_eps(parts.get("quarters"))
    if not isinstance(closes, list) or periods is None:
        return None
    rates = None
    if currency != _USD:
        pair = parts.get("rates")
        if not isinstance(pair, list):
            return None
        rates = [(day, rate) for day, rate in fx_closes(pair) if _positive(rate)]
    days = [(day, close) for day, close in price_closes(closes) if _positive(close)]
    return built_series(days, periods, currency, rates)


def _positive(figure: float) -> bool:
    """Whether a close or a rate can be read: a finite number above zero."""
    return math.isfinite(figure) and figure > 0


def period_eps(payload: Any) -> list[PeriodEps] | None:
    """The periods of an FMP ``income-statement`` answer, oldest first: each row with a date, its
    ``epsDiluted`` (``None`` without a finite number, ``"1e400"`` say) and its
    ``reportedCurrency``; ``None`` when the payload is not a list."""
    if not isinstance(payload, list):
        return None
    periods = []
    for row, end in dated(payload):
        figure = number(row.get("epsDiluted"))
        eps = None if figure is None else float(figure)
        if eps is not None and not math.isfinite(eps):
            eps = None
        periods.append(PeriodEps(end, eps, text(row.get("reportedCurrency"))))
    return sorted(periods, key=lambda period: period.end)


def built_rows(
    closes: Sequence[tuple[date, float]],
    periods: Sequence[PeriodEps],
    currency: str,
    rates: Sequence[tuple[date, float]] | None,
) -> list[tuple[date, float | None]]:
    """Each day of ``closes`` that has a trailing EPS, with its P/E, in the order of ``closes``:
    the close, in USD as FMP gives it, ÷ the trailing EPS of the newest period ended at or before
    the day (``_trailing_eps``), each period's EPS of a company in ``currency`` other than USD
    brought into USD at the last of ``rates`` (units of the currency per USD, each above zero;
    ``None``, and not read, for USD) at or before the period's end; the day's own rate is not
    read. A loss day is ``(day, None)``."""
    ordered = sorted(periods, key=lambda period: period.end)
    ends = [period.end for period in ordered]
    trailing = _trailing_eps(ordered, currency, None if currency == _USD else (rates or ()))
    rows: list[tuple[date, float | None]] = []
    for day, close in closes:
        newest = bisect_right(ends, day) - 1
        eps = trailing[newest] if newest >= 0 else None
        if eps is not None:
            rows.append((day, close / eps if eps > 0 else None))
    return rows


def built_series(
    closes: Sequence[tuple[date, float]],
    periods: Sequence[PeriodEps],
    currency: str,
    rates: Sequence[tuple[date, float]] | None,
) -> Series:
    """The trailing series built from FMP's closes and periods (``built_rows``)."""
    return _series(built_rows(closes, periods, currency, rates))


def _trailing_eps(
    periods: Sequence[PeriodEps], currency: str, rates: Sequence[tuple[date, float]] | None
) -> list[float | None]:
    """By period, oldest first: the sum of the EPS over the year of periods it ends, ``None``
    where there are too few, they are not consecutive, or one has no EPS, is in another currency
    or has no rate; a period that names no currency is in ``currency``, as 4.2 reads a statement.
    With ``rates`` (a company in another currency) each EPS is in USD, ÷ the last rate at or
    before the period's end; with ``None`` (USD) the EPS is summed as stated."""
    cadence = cadence_of([period.end for period in periods]) or "quarterly"
    count = PERIODS_PER_YEAR[cadence]
    pair = None if rates is None else sorted(rates)
    rate_days = [day for day, _ in pair or ()]
    figures: list[float | None] = []
    for period in periods:
        eps = period.eps if period.currency in (None, currency) else None
        if eps is not None and pair is not None:
            at = bisect_right(rate_days, period.end) - 1
            eps = eps / pair[at][1] if at >= 0 else None
        figures.append(eps)
    sums: list[float | None] = []
    for newest in range(len(periods)):
        first = max(0, newest + 1 - count)
        year = [eps for eps in figures[first : newest + 1] if eps is not None]
        ends = [period.end for period in periods[first : newest + 1]]
        whole = len(year) == count and consecutive_periods(ends, cadence)
        sums.append(sum(year) if whole else None)
    return sums


def forward_series(rows: Sequence[MultiplesRow]) -> Series:
    """The forward series of the multiples log's rows."""
    return _series((row.day, row.pe_forward) for row in rows)


def stored_trailing(conn: sqlite3.Connection, symbol: str) -> tuple[int, Series | None] | None:
    """The trailing series of the P/E history's answers stored for the company (the store's
    exchange form), whatever their age: the newest usable closes and quarters, and, for a company
    in another currency (``reporting_currency``), the newest usable pair's closes. The closes'
    response id and the series (``None`` when it cannot be read); ``None`` when the closes or the
    quarters are not stored. The ``pettm`` answers of the provider ``gf``, stored before, are not
    read."""
    currency = reporting_currency(conn, symbol)
    rows = {
        part: latest_response(conn, FMP, answer.endpoint, answer.symbol, answer.params)
        for part, answer in series_answers(symbol, currency).items()
    }
    stored = {part: response_payload(conn, row.id) for part, row in rows.items() if row is not None}
    closes = rows["closes"]
    if closes is None or stored["closes"] is None or stored.get("quarters") is None:
        return None
    payloads = {part: _parsed(payload) for part, payload in stored.items()}
    return closes.id, trailing_series(payloads, currency)


def _parsed(payload: str | None) -> Any:
    """A stored payload parsed; ``None``, which no series reads, when it does not parse."""
    try:
        return None if payload is None else json.loads(payload)
    except ValueError:
        return None


def stored_series(conn: sqlite3.Connection, symbol: str, name: str) -> Series | None:
    """The company's series ``name`` as stored: the trailing one from the P/E history's stored
    answers (``None`` without them, or when they cannot be read), the forward one from the
    log."""
    if name == "pe_forward":
        return forward_series(multiples_log_for(conn, symbol))
    stored = stored_trailing(conn, symbol)
    return None if stored is None else stored[1]


def _series(rows: Iterable[tuple[date, float | None]]) -> Series:
    by_day = dict(rows)  # a day given twice keeps its later value
    if not by_day:
        return Series((), dict.fromkeys(STATS), None)
    days = sorted(by_day)
    start = years_before(days[-1], WINDOW_YEARS)
    points: list[tuple[date, float]] = []
    for day in days:
        value = by_day[day]
        if day >= start and value is not None:
            points.append((day, value))
    values = [value for _, value in points]
    stats: dict[str, float | None] = dict.fromkeys(STATS)
    if values:
        stats = {
            "avg_10y": fmean(values),
            "median_10y": median(values),
            "high_10y": max(values),
            "low_10y": min(values),
        }
    return Series(tuple(points), stats, days[0])


def years_before(day: date, years: int) -> date:
    """The same day ``years`` earlier; 29 February becomes the 28th."""
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)
