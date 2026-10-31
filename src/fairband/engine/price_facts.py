"""The price-based columns (spec 6.3, ``design.md`` 9.5): none of them is a target.

The closes come in any order and are sorted by date; a close after ``today`` is ignored, and so is
a close at or below zero, which is not a price. The last close is the latest on or before
``today``. The 52-week high and low run over the 365 days that end on ``today``. The change over
n years compares the last close with the last close on or before the same date n years back
(28 February when that date is 29 February), when one falls within the week before it. The
drawdown is the last close against the highest close on file, zero or below.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

_YEAR_DAYS = 365
_REFERENCE_DAYS = 7  # the week before the date n years back: weekends and holidays have no close


@dataclass(frozen=True)
class PriceFacts:
    high_52w: float | None
    low_52w: float | None
    change_1y: float | None
    change_3y: float | None
    change_5y: float | None
    drawdown_from_peak: float | None


def price_facts(closes: Sequence[tuple[date, float]], today: date) -> PriceFacts:
    """The 52-week range, the 1-, 3- and 5-year changes and the drop from the peak as of ``today``;
    every field ``None`` without a close on or before ``today``."""
    history = sorted((d, c) for d, c in closes if d <= today and c > 0)
    if not history:
        return PriceFacts(None, None, None, None, None, None)
    last = history[-1][1]
    year = [c for d, c in history if d > today - timedelta(days=_YEAR_DAYS)]
    return PriceFacts(
        high_52w=max(year) if year else None,
        low_52w=min(year) if year else None,
        change_1y=_change(history, today, 1),
        change_3y=_change(history, today, 3),
        change_5y=_change(history, today, 5),
        drawdown_from_peak=last / max(c for _, c in history) - 1,
    )


def _change(history: list[tuple[date, float]], today: date, years: int) -> float | None:
    """The last close of ``history`` (sorted, none after ``today``) against its reference close
    ``years`` back, or ``None`` when no close falls in the week up to that date."""
    target = _years_before(today, years)
    ref = next(((d, c) for d, c in reversed(history) if d <= target), None)
    if ref is None or ref[0] < target - timedelta(days=_REFERENCE_DAYS):
        return None
    return history[-1][1] / ref[1] - 1


def _years_before(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:  # 29 February in a year that has none
        return d.replace(year=d.year - years, day=28)
