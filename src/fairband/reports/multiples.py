"""The multiples history (spec 2026-11-06 Tier 2, 13.7; ``method.md`` 16.7): the two P/E series a
report reads the price against, as the read serves them and the refs resolve them.

- The trailing P/E (``pe``): GuruFocus's daily ``pettm`` series as the newest usable stored
  ``pe-history`` response holds it, whatever its age, each row's closing P/E
  (``normalize_gf.pe_ttm_rows``). A loss row has no point; nothing fills its days, so the series
  keeps the gap. A payload without the series' shape, or with no point above zero, gives no
  series (``None``); the pass-through stores such a payload as unusable, so the newest usable one
  holds the series.
- The forward P/E (``pe_forward``): the multiples log's forward P/E by day; a row with none has no
  point.

Each series holds the points of the ten years to its newest day, from the same day ten years
before, and over them the four statistics, ``avg_10y``, ``median_10y``, ``high_10y`` and
``low_10y``, ``None`` each without a point. ``since`` is the series' first day on file, a loss day
or a row with no forward P/E included: when the vendor's series or the log began.
"""

import json
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean, median
from typing import Any

from fairband.store.multiples import MultiplesRow, multiples_log_for
from fairband.store.vendor import latest_response, response_payload
from fairband.vendors.gurufocus import PE_TTM, PROVIDER
from fairband.vendors.normalize_gf import pe_ttm_rows

SERIES = ("pe", "pe_forward")
STATS = ("avg_10y", "median_10y", "high_10y", "low_10y")
WINDOW_YEARS = 10


@dataclass(frozen=True)
class Series:
    """The points oldest first, each day with its P/E; the statistics by name; the first day."""

    points: tuple[tuple[date, float], ...]
    stats: dict[str, float | None]
    since: date | None


def trailing_series(payload: Any) -> Series | None:
    """The trailing series of a ``pe-history`` payload; ``None`` when it cannot be read."""
    rows = pe_ttm_rows(payload)
    return None if rows is None else _series(rows)


def forward_series(rows: Sequence[MultiplesRow]) -> Series:
    """The forward series of the multiples log's rows."""
    return _series((row.day, row.pe_forward) for row in rows)


def stored_trailing(conn: sqlite3.Connection, symbol: str) -> tuple[int, Series | None] | None:
    """The newest usable ``pe-history`` response stored for the company, whatever its age: its id
    and its series (``None`` when it cannot be read); ``None`` when none is stored."""
    row = latest_response(conn, PROVIDER, PE_TTM, symbol, {"symbol": symbol})
    text = None if row is None else response_payload(conn, row.id)
    if row is None or text is None:
        return None
    try:
        payload = json.loads(text)
    except ValueError:
        return row.id, None
    return row.id, trailing_series(payload)


def stored_series(conn: sqlite3.Connection, symbol: str, name: str) -> Series | None:
    """The company's series ``name`` as stored: the trailing one from the newest stored
    ``pe-history`` response (``None`` without one, or when it cannot be read), the forward one
    from the log."""
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
