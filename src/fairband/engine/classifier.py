"""Damodaran's six life-cycle phases from revenue growth and operating margin (``design.md`` 5).

The rules run in the order of 5.5 and the first that fits decides the phase: growth that cannot
be measured is Start-up; growth "Close to zero or negative" with a falling five-year revenue
trend is Decline; a negative margin is Young Growth, or High Growth when its trend improves; a
positive margin is Mature Growth or Mature Stable by the growth word. A margin of exactly zero
counts as positive. The checks flag a company but never change its phase.

Growth is the CAGR from the fiscal year three years back to the last, or over the span on file
when there are two or three years. The growth word and the margin direction are deciles of the
universe at the refresh (``Deciles``). The revenue and margin trends are least-squares slopes
through the last five fiscal years, at least three; a year with no margin (revenue or operating
income missing, or revenue zero) is skipped.
"""

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from fairband.engine.types import Flag, Phase, PhaseEvidence

_GROWTH_SPAN = 3
_TREND_WINDOW = 5
_TREND_MIN_POINTS = 3
_SHORT_HISTORY_YEARS = 4

GROWTH_WORDS = ("Close to zero or negative", "Low", "Moderate", "High", "Very High")

_GROWTH_WORD_PHASE: dict[str, Phase] = {
    "Very High": "Young Growth",
    "High": "High Growth",
    "Moderate": "Mature Growth",
    "Low": "Mature Stable",
    "Close to zero or negative": "Decline",
}
_DIRECTION_PHASE: dict[str, Phase] = {
    "Rising": "Mature Growth",
    "Stable": "Mature Stable",
    "Declining": "Decline",
}
_FCF_EXPECTED: dict[Phase, str] = {
    "Start-up": "negative",
    "Young Growth": "negative",
    "High Growth": "negative",
    "Mature Growth": "positive",
    "Mature Stable": "positive",
    "Decline": "positive",
}


@dataclass(frozen=True)
class FiscalYear:
    """One fiscal year as the cash-flow statement signs it: ``capex`` is negative for spending."""

    year: int
    period_end: date
    currency: str
    revenue: float | None
    operating_income: float | None
    cfo: float | None
    cfi: float | None
    cff: float | None
    capex: float | None


Series = tuple[FiscalYear, ...]
"""Fiscal years, oldest first."""


@dataclass(frozen=True)
class Deciles:
    """The universe's nine decile edges for growth and for the positive-margin slope."""

    growth_edges: tuple[float, ...]
    margin_slope_edges: tuple[float, ...]
    n_growth: int
    n_margin: int
    refresh_id: int | None


def slope(values: Sequence[float]) -> float:
    """The least-squares slope against the index 0..n-1; two values at least."""
    return statistics.linear_regression(range(len(values)), values).slope


def decile(value: float, edges: Sequence[float]) -> int:
    """1 to 10: one more than the number of edges at or below the value."""
    return min(10, 1 + sum(1 for e in edges if e <= value))


def growth_3y(series: Series) -> float | None:
    """The yearly revenue growth (CAGR) over three years, or over the span when shorter.

    ``None`` with fewer than two fiscal years, or when an endpoint is missing or not positive: a
    CAGR needs two positive revenues, and a zero revenue is growth that cannot be measured.
    """
    if len(series) < 2:
        return None
    span = min(_GROWTH_SPAN, len(series) - 1)
    first, last = series[-1 - span].revenue, series[-1].revenue
    if first is None or last is None or first <= 0 or last <= 0:
        return None
    return float((last / first) ** (1 / span) - 1)


def is_startup(series: Series) -> bool:
    """Revenue is zero now, or was zero three years ago; a year not on file is not zero."""
    if not series:
        return False
    back = series[-1 - _GROWTH_SPAN].revenue if len(series) > _GROWTH_SPAN else None
    return series[-1].revenue == 0 or back == 0


def compute_deciles(
    series_by_symbol: Mapping[str, Series], refresh_id: int | None = None
) -> Deciles:
    """The universe's growth and margin-slope deciles, nine edges each.

    Growth ranks every series with a measurable ``growth_3y``. The margin slope ranks every
    series whose last margin is positive (zero counts as positive) and whose five-year margin
    trend exists. With fewer than two values a side gets no edges, and ``classify`` then puts
    every value in decile 1; a universe this small does not occur in practice.
    """
    growth: list[float] = []
    margin_slopes: list[float] = []
    for series in series_by_symbol.values():
        g = growth_3y(series)
        if g is not None:
            growth.append(g)
        margin, m_slope = _last_margin(series), _margin_trend(series)
        if margin is not None and margin >= 0 and m_slope is not None:
            margin_slopes.append(m_slope)
    return Deciles(
        growth_edges=_edges(growth),
        margin_slope_edges=_edges(margin_slopes),
        n_growth=len(growth),
        n_margin=len(margin_slopes),
        refresh_id=refresh_id,
    )


def dickinson(fy: FiscalYear) -> str | None:
    """Dickinson's (2011) stage from the signs of CFO, CFI and CFF; ``None`` when one is missing.

    Introduction (-, -, +), Growth (+, -, +), Mature (+, -, -), Decline (-, +, any). Every other
    pattern is Shake-out; a zero has neither sign, so it lands there unless the pattern is Decline.
    """
    cfo, cfi, cff = fy.cfo, fy.cfi, fy.cff
    if cfo is None or cfi is None or cff is None:
        return None
    if cfo < 0 and cfi > 0:
        return "Decline"
    if cfi < 0 and cfo < 0 and cff > 0:
        return "Introduction"
    if cfi < 0 and cfo > 0 and cff > 0:
        return "Growth"
    if cfi < 0 and cfo > 0 and cff < 0:
        return "Mature"
    return "Shake-out"


def classify(series: Series, deciles: Deciles) -> PhaseEvidence:
    """The phase by the rules of ``design.md`` 5.5, with the evidence and the checks.

    Fewer than two fiscal years, or no operating margin in any year when the margin must decide,
    leaves the phase ``None`` with the reason.
    """
    n = len(series)
    if n < 2:
        return PhaseEvidence(
            phase=None,
            reason="fewer than two fiscal years",
            years_used=n,
            growth_3y=None,
            growth_word=None,
            growth_decile=None,
            revenue_slope=None,
            margin=None,
            margin_slope=None,
            margin_direction=None,
            fcf_sign=None,
            dickinson=None,
            checks=(),
        )

    g3 = growth_3y(series)
    g_decile = None if g3 is None else decile(g3, deciles.growth_edges)
    g_word = None if g_decile is None else GROWTH_WORDS[(g_decile - 1) // 2]
    revenues = [fy.revenue for fy in series[-_TREND_WINDOW:] if fy.revenue is not None]
    rev_slope = _trend(revenues)
    margin, m_slope = _last_margin(series), _margin_trend(series)
    direction = _margin_direction(margin, m_slope, deciles.margin_slope_edges)
    fcf = _fcf_sign(series[-1])

    phase: Phase | None
    if is_startup(series) or g3 is None:
        phase = "Start-up"
    elif g_word == GROWTH_WORDS[0] and rev_slope is not None and rev_slope < 0:
        phase = "Decline"
    elif margin is None:
        phase = None
    elif margin < 0:
        phase = "High Growth" if m_slope is not None and m_slope > 0 else "Young Growth"
    elif g_word in ("Very High", "High", "Moderate"):
        phase = "Mature Growth"
    else:
        phase = "Mature Stable"

    return PhaseEvidence(
        phase=phase,
        reason="no operating margin" if phase is None else None,
        years_used=n,
        growth_3y=g3,
        growth_word=g_word,
        growth_decile=g_decile,
        revenue_slope=rev_slope,
        margin=margin,
        margin_slope=m_slope,
        margin_direction=direction,
        fcf_sign=fcf,
        dickinson=dickinson(series[-1]),
        checks=() if phase is None else _checks(series, phase, g_word, margin, direction, fcf),
    )


def _checks(
    series: Series,
    phase: Phase,
    g_word: str | None,
    margin: float | None,
    direction: str | None,
    fcf: str | None,
) -> tuple[Flag, ...]:
    checks: list[Flag] = []
    if margin is not None and margin < 0 and g_word is not None:
        pointed = _GROWTH_WORD_PHASE[g_word]
        if pointed != phase:
            checks.append(
                Flag(
                    "growth-word-disagrees",
                    "Growth word disagrees",
                    f'Revenue growth is "{g_word}", which points to {pointed}, '
                    f"while the margin rule gave {phase}.",
                )
            )
    if direction is not None:
        pointed = _DIRECTION_PHASE[direction]
        if pointed != phase:
            checks.append(
                Flag(
                    "margin-direction-disagrees",
                    "Margin direction disagrees",
                    f'The operating margin trend is "{direction}", which points to {pointed}, '
                    f"while the rules gave {phase}.",
                )
            )
    expected = _FCF_EXPECTED[phase]
    if fcf in ("positive", "negative") and fcf != expected:
        checks.append(
            Flag(
                "fcf-sign",
                "Free cash flow disagrees",
                f"Free cash flow for fiscal {series[-1].year} is {fcf}, "
                f"while a {phase} company's is usually {expected}.",
            )
        )
    if len(series) < _SHORT_HISTORY_YEARS:
        checks.append(
            Flag(
                "short-history",
                "Short history",
                f"Only {len(series)} fiscal years are on file; growth runs over the years "
                "that exist instead of three.",
            )
        )
    if margin == 0:
        checks.append(
            Flag(
                "margin-zero",
                "Zero margin",
                "The operating margin is exactly zero; it was counted as positive.",
            )
        )
    currencies = list(dict.fromkeys(fy.currency for fy in series))
    if len(currencies) > 1:
        checks.append(
            Flag(
                "currency-change",
                "Currency change",
                f"The reported currency changes between fiscal years ({', '.join(currencies)}); "
                "growth is still computed from the reported figures.",
            )
        )
    return tuple(checks)


def _edges(values: list[float]) -> tuple[float, ...]:
    if len(values) < 2:
        return ()
    return tuple(statistics.quantiles(values, n=10, method="inclusive"))


def _trend(values: list[float]) -> float | None:
    return slope(values) if len(values) >= _TREND_MIN_POINTS else None


def _margin(fy: FiscalYear) -> float | None:
    if fy.revenue is None or fy.operating_income is None or fy.revenue == 0:
        return None
    return fy.operating_income / fy.revenue


def _last_margin(series: Series) -> float | None:
    """The margin of the last fiscal year that has one."""
    return next((m for fy in reversed(series) if (m := _margin(fy)) is not None), None)


def _margin_trend(series: Series) -> float | None:
    return _trend([m for fy in series[-_TREND_WINDOW:] if (m := _margin(fy)) is not None])


def _margin_direction(
    margin: float | None, m_slope: float | None, edges: Sequence[float]
) -> str | None:
    """Rising, Stable or Declining for a margin at or above zero; ``None`` otherwise."""
    if margin is None or margin < 0 or m_slope is None:
        return None
    d = decile(m_slope, edges)
    if d >= 8 and m_slope > 0:
        return "Rising"
    if d <= 3 and m_slope < 0:
        return "Declining"
    return "Stable"


def _fcf_sign(fy: FiscalYear) -> str | None:
    """The sign of the year's free cash flow, operating cash flow plus the (negative) capex."""
    if fy.cfo is None or fy.capex is None:
        return None
    fcf = fy.cfo + fy.capex
    return "positive" if fcf > 0 else "negative" if fcf < 0 else "zero"
