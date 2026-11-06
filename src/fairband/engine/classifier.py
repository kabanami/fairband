"""Damodaran's six life-cycle phases from revenue growth and operating margin (``design.md`` 5).

The rules run in the order of ``method.md`` 3.5 and the first that fits decides the phase: a zero
revenue now or three years back is Start-up unless the company is established (an operating
margin above zero in at least three of the last five fiscal years, or in at least five of the
fiscal years on file); growth "Close to zero or negative" with a falling five-year revenue trend
and revenue that fell in at least three of the last four year-over-year steps is Decline; a
negative margin of an established company takes the growth word's phase as a positive margin
would, and any other negative margin is Young Growth, or High Growth when its trend improves; a
positive margin is Mature Growth or Mature Stable by the growth word. A margin of exactly zero
counts as positive. The checks flag a company but never change its phase.

A data gap leaves the phase ``None`` with a reason: fewer than two fiscal years, no revenue or a
negative revenue for the last fiscal year, no measurable revenue growth, or no operating margin
when the margin must decide. A zero revenue is a reported zero, never a missing one; an
established company whose revenue is zero now has no measurable growth.

Growth is the CAGR from the fiscal year three years back to the last, or over the span on file
when there are two or three years. When the first year of that span has a missing, zero or
negative revenue, growth runs over the longest run of consecutive positive revenues that ends
at the last year. The growth word and the margin direction are deciles of the universe at the
refresh (``Deciles``): the direction is Rising at decile 9 or higher with a slope above zero,
Declining at decile 2 or lower with a slope below zero, and Stable otherwise, which points to
no phase. The revenue and margin trends are least-squares slopes against the year index of the
last five fiscal years, at least three points; a year with no value (for the margin: revenue or
operating income missing, or revenue zero or negative) is skipped but the years after it keep
their place. The margin sign comes from the last of those five years that has a margin. Fewer
than five fiscal years, or a shortened growth span, is "short history".
"""

import itertools
import statistics
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from fairband.engine.types import Flag, Phase, PhaseEvidence

_GROWTH_SPAN = 3
_TREND_WINDOW = 5
_TREND_MIN_POINTS = 3

ESTABLISHED_YEARS = 3
ESTABLISHED_YEARS_ON_FILE = 5
DECLINE_FALLS = 3
DECLINE_STEPS = 4

GROWTH_WORDS = ("Close to zero or negative", "Low", "Moderate", "High", "Very High")

_GROWTH_WORD_PHASE: dict[str, Phase] = {
    "Very High": "Young Growth",
    "High": "High Growth",
    "Moderate": "Mature Growth",
    "Low": "Mature Stable",
    "Close to zero or negative": "Decline",
}
_DIRECTION_PHASE: dict[str, Phase] = {  # Stable points to no phase (spec 2026-11-06 8.3)
    "Rising": "Mature Growth",
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
    """The yearly revenue growth (CAGR) from three years back to the last fiscal year.

    With two or three years on file the span is what exists. When the first year of the span has
    a missing, zero or negative revenue, growth runs over the longest run of consecutive positive
    revenues that ends at the last year. ``None`` for a Start-up (``is_startup``), when the last
    revenue is missing or negative, or when that run is shorter than two years.
    """
    growth = None if is_startup(series) else _growth(series)
    return None if growth is None else growth[0]


def is_startup(series: Series) -> bool:
    """Revenue is zero now, or was zero three years ago; a year not on file is not zero."""
    if not series:
        return False
    back = series[-1 - _GROWTH_SPAN].revenue if len(series) > _GROWTH_SPAN else None
    return series[-1].revenue == 0 or back == 0


def operating_margin(fy: FiscalYear) -> float | None:
    """Operating income ÷ revenue; ``None`` when either is missing or the revenue is not positive."""
    if fy.revenue is None or fy.operating_income is None or fy.revenue <= 0:
        return None
    return fy.operating_income / fy.revenue


def established(series: Series) -> tuple[bool, int, int]:
    """Whether the company is established, with the two counts that decide it: the fiscal years
    with an operating margin above zero among the last five, and among all on file.

    Established: at least three of the last five fiscal years, or at least five of the fiscal
    years on file, have an operating margin above zero. A year without a margin counts for
    nothing in either count.
    """
    positive = [(m := operating_margin(fy)) is not None and m > 0 for fy in series]
    last_five, on_file = sum(positive[-_TREND_WINDOW:]), sum(positive)
    is_established = last_five >= ESTABLISHED_YEARS or on_file >= ESTABLISHED_YEARS_ON_FILE
    return is_established, last_five, on_file


def falling_steps(series: Series) -> tuple[int, int]:
    """The falls and the steps among the last four year-over-year steps.

    A step counts only when both years have a revenue; it is a fall when the later revenue is
    below the earlier.
    """
    falls = steps = 0
    for earlier, later in itertools.pairwise(fy.revenue for fy in series[-DECLINE_STEPS - 1 :]):
        if earlier is None or later is None:
            continue
        steps += 1
        if later < earlier:
            falls += 1
    return falls, steps


def compute_deciles(
    series_by_symbol: Mapping[str, Series], refresh_id: int | None = None
) -> Deciles:
    """The universe's growth and margin-slope deciles, nine edges each.

    Both rankings take only a series with no data gap, not a Start-up, with a measurable growth
    and with an operating margin in the last five fiscal years. Growth ranks each of them; the
    margin slope ranks those whose last margin is positive (zero counts as positive) and whose
    margin trend exists. With fewer than two values a side gets no edges, and ``classify`` then
    puts every value in decile 1; a universe this small does not occur in practice.
    """
    growth: list[float] = []
    margin_slopes: list[float] = []
    for series in series_by_symbol.values():
        if _data_gap(series) is not None or is_startup(series):
            continue
        g, margin = growth_3y(series), _last_margin(series)
        if g is None or margin is None:
            continue
        growth.append(g)
        m_slope = _trend(series, operating_margin)
        if margin >= 0 and m_slope is not None:
            margin_slopes.append(m_slope)
    return Deciles(
        growth_edges=_edges(growth),
        margin_slope_edges=_edges(margin_slopes),
        n_growth=len(growth),
        n_margin=len(margin_slopes),
        refresh_id=refresh_id,
    )


def dickinson(fy: FiscalYear) -> str | None:
    """Dickinson's stage from the signs of CFO, CFI and CFF; ``None`` when one is missing.

    Dickinson (2011), "Cash Flow Patterns as a Proxy for Firm Life Cycle", *The Accounting
    Review* 86(6), Table 1: Introduction (-, -, +), Growth (+, -, +), Mature (+, -, -), Decline
    (-, +, +) and (-, +, -), Shake-out (-, -, -), (+, +, +) and (+, +, -). A zero has neither
    sign; it lands in Shake-out unless the pattern is Decline.
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
    """The phase by the rules of ``method.md`` 3.5, with the evidence and the checks.

    A data gap, or no operating margin in any year when the margin must decide, leaves the phase
    ``None`` with the reason.
    """
    n = len(series)
    gap = _data_gap(series)
    if gap is not None:
        return PhaseEvidence(
            phase=None,
            reason=gap,
            years_used=n,
            positive_years_last_five=None,
            positive_years_on_file=None,
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

    is_established, positive_years, positive_on_file = established(series)
    start_up = _start_up(series)
    growth = None if start_up else _growth(series)
    g3 = None if growth is None else growth[0]
    span = None if growth is None else growth[1]
    g_decile = None if g3 is None else decile(g3, deciles.growth_edges)
    g_word = None if g_decile is None else GROWTH_WORDS[(g_decile - 1) // 2]
    rev_slope = _trend(series, lambda fy: fy.revenue)
    deciding = _deciding_year(series)
    margin = None if deciding is None else operating_margin(deciding)
    m_slope = _trend(series, operating_margin)
    direction = _margin_direction(margin, m_slope, deciles.margin_slope_edges)
    fcf = _fcf_sign(series[-1])
    falls, _ = falling_steps(series)

    phase: Phase | None
    if start_up:
        phase = "Start-up"
    elif (
        g_word == GROWTH_WORDS[0]
        and rev_slope is not None
        and rev_slope < 0
        and falls >= DECLINE_FALLS
    ):
        phase = "Decline"
    elif margin is None:
        phase = None
    elif margin < 0 and not is_established:
        phase = "High Growth" if m_slope is not None and m_slope > 0 else "Young Growth"
    elif g_word in ("Very High", "High", "Moderate"):  # rule 5, and rule 4a's loss year
        phase = "Mature Growth"
    else:
        phase = "Mature Stable"

    return PhaseEvidence(
        phase=phase,
        reason="no operating margin" if phase is None else None,
        years_used=n,
        positive_years_last_five=positive_years,
        positive_years_on_file=positive_on_file,
        growth_3y=g3,
        growth_word=g_word,
        growth_decile=g_decile,
        revenue_slope=rev_slope,
        margin=margin,
        margin_slope=m_slope,
        margin_direction=direction,
        fcf_sign=fcf,
        dickinson=dickinson(series[-1]),
        checks=(
            ()
            if phase is None
            else _checks(
                series,
                phase,
                span,
                g_word,
                rev_slope,
                margin,
                None if deciding is None else deciding.year,
                direction,
                fcf,
                is_established,
                positive_years,
                positive_on_file,
                falls,
            )
        ),
    )


def _data_gap(series: Series) -> str | None:
    """Why the series cannot be classified whatever the deciles, or ``None``."""
    if len(series) < 2:
        return "fewer than two fiscal years"
    last = series[-1].revenue
    if last is None:
        return "no revenue for the last fiscal year"
    if last < 0:
        return "negative revenue"
    if not _start_up(series) and _growth(series) is None:
        return "no measurable revenue growth"
    return None


def _start_up(series: Series) -> bool:
    """Rule 1: a Start-up (``is_startup``) that is not established."""
    return is_startup(series) and not established(series)[0]


def _growth(series: Series) -> tuple[float, int] | None:
    """``growth_3y`` with its span in years, a Start-up's too: rule 1 lets an established company
    with a zero revenue three years back through on the run of positive revenues after it."""
    revenues = [fy.revenue for fy in series[-1 - _GROWTH_SPAN :]]  # up to four, oldest first
    if len(revenues) < 2:
        return None
    first, last = revenues[0], revenues[-1]
    if last is None or last <= 0:
        return None
    span = len(revenues) - 1
    if first is None or first <= 0:
        run: list[float] = []  # the positive revenues that end at the last year, newest first
        for r in reversed(revenues):
            if r is None or r <= 0:
                break
            run.append(r)
        if len(run) < 2:
            return None
        first, span = run[-1], len(run) - 1
    return float((last / first) ** (1 / span) - 1), span


def _checks(
    series: Series,
    phase: Phase,
    span: int | None,
    g_word: str | None,
    rev_slope: float | None,
    margin: float | None,
    margin_year: int | None,
    direction: str | None,
    fcf: str | None,
    is_established: bool,
    positive_years: int,
    positive_on_file: int,
    falls: int,
) -> tuple[Flag, ...]:
    checks: list[Flag] = []
    if margin is not None and margin < 0 and not is_established and g_word is not None:
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
    # rule 4a: only an established company's loss year reaches a mature phase with a negative margin
    if (
        margin is not None
        and margin < 0
        and is_established
        and phase in ("Mature Growth", "Mature Stable")
    ):
        checks.append(
            Flag(
                "loss-year",
                "Loss year",
                f"The operating margin is negative in fiscal {margin_year} after a positive "
                f"margin in {positive_years} of the last five fiscal years and in "
                f"{positive_on_file} of the {len(series)} on file; "
                "the phase follows the growth word.",
            )
        )
    # rule 1: an established company is never a Start-up; its revenue was zero three years back,
    # since a zero now leaves no measurable growth and the phase unclassified
    if is_established and is_startup(series):
        checks.append(
            Flag(
                "revenue-gap",
                "Revenue gap",
                f"Revenue was zero in fiscal {series[-1 - _GROWTH_SPAN].year}, but the margin "
                f"was above zero in {positive_years} of the last five fiscal years and in "
                f"{positive_on_file} of the {len(series)} on file, so the company is not a "
                "Start-up.",
            )
        )
    if (
        g_word == GROWTH_WORDS[0]
        and rev_slope is not None
        and rev_slope < 0
        and falls < DECLINE_FALLS
    ):
        checks.append(
            Flag(
                "revenue-falling",
                "Revenue falling",
                f"Revenue fell in {falls} of the last four fiscal years with a falling "
                "five-year trend; the Decline rule needs three.",
            )
        )
    if direction in _DIRECTION_PHASE:  # Stable points nowhere
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
    n = len(series)
    clauses: list[str] = []
    if n < _TREND_WINDOW:
        clauses.append(
            f"Only {n} fiscal years are on file, so the trends cover fewer than five years"
        )
    if span is not None and span < _GROWTH_SPAN:
        clause = (
            f"growth runs from fiscal {series[-1 - span].year} to {series[-1].year} "
            "instead of over three years"
        )
        if n > _GROWTH_SPAN:  # the year three years back is on file: its revenue cut the span
            back = series[-1 - _GROWTH_SPAN]
            state = "zero" if back.revenue == 0 else "missing or negative"  # zero: revenue-gap
            clause = f"revenue for fiscal {back.year} is {state}, so {clause}"
        clauses.append(clause)
    if clauses:
        sentence = "; ".join(clauses)
        checks.append(
            Flag("short-history", "Short history", sentence[:1].upper() + sentence[1:] + ".")
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


def _trend(series: Series, value: Callable[[FiscalYear], float | None]) -> float | None:
    """The least-squares slope of ``value`` against the year index of the last five years.

    A year without a value is skipped but keeps its index, so a gap does not pull the later
    years back; ``None`` with fewer than three values.
    """
    positions: list[int] = []
    values: list[float] = []
    for i, fy in enumerate(series[-_TREND_WINDOW:]):
        v = value(fy)
        if v is not None:
            positions.append(i)
            values.append(v)
    if len(values) < _TREND_MIN_POINTS:
        return None
    return statistics.linear_regression(positions, values).slope


def _deciding_year(series: Series) -> FiscalYear | None:
    """The last of the last five fiscal years that has an operating margin; its margin decides."""
    window = series[-_TREND_WINDOW:]
    return next((fy for fy in reversed(window) if operating_margin(fy) is not None), None)


def _last_margin(series: Series) -> float | None:
    """The margin of the last of the last five fiscal years that has one."""
    deciding = _deciding_year(series)
    return None if deciding is None else operating_margin(deciding)


def _margin_direction(
    margin: float | None, m_slope: float | None, edges: Sequence[float]
) -> str | None:
    """Rising, Stable or Declining for a margin at or above zero; ``None`` otherwise.

    Rising is decile 9 or higher with a slope above zero, Declining decile 2 or lower with a slope
    below zero (spec 2026-11-06 8.3).
    """
    if margin is None or margin < 0 or m_slope is None:
        return None
    d = decile(m_slope, edges)
    if d >= 9 and m_slope > 0:
        return "Rising"
    if d <= 2 and m_slope < 0:
        return "Declining"
    return "Stable"


def _fcf_sign(fy: FiscalYear) -> str | None:
    """The sign of the year's free cash flow, operating cash flow plus the (negative) capex."""
    if fy.cfo is None or fy.capex is None:
        return None
    fcf = fy.cfo + fy.capex
    return "positive" if fcf > 0 else "negative" if fcf < 0 else "zero"
