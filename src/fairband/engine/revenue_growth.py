"""High Growth and Young Growth: the revenue path, the margin line and the tax carry of
Damodaran's revenue DCF (growth-routes spec 5.3, 5.4, 5.5 and 5.7).

Year 0 is trailing revenue and year 1 the NTM consensus revenue, so g_1 is the NTM revenue over
trailing revenue less one. Years 2 and 3 grow at the consensus steps; a missing step holds the
last known rate, g_1 for g_2 and g_2 for g_3. Years 4 to H, H being ``high_growth_years``, grow
at the hold rate, g_3 as resolved unless one is given. Years H + 1 to H + ``fade_years`` fade
from the hold rate to the terminal growth g_T in equal steps,
g_t = hold − (hold − g_T) × (t − H) ÷ ``fade_years``, the last on g_T; when the hold rate is below
g_T the same line rises to it.

The operating margin moves in a straight line from the trailing margin to the target, reaching it
in ``convergence_year`` and staying there: m_t = start + (target − start) × min(t, convergence
year) ÷ convergence year. A margin above the target moves down the same line.

Tax is charged after the forecast's own losses, the carried loss starting at zero because no
history of tax losses is stored. A loss year adds its size to the carried loss and pays no tax; a
profit year is taxed on what it earns above the carried loss and uses the carried loss up by its
operating income, never below zero. NOPAT is operating income less tax.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate


@dataclass(frozen=True)
class RevenuePath:
    """Trailing and NTM revenue, the consensus growth for years 2 and 3 (``None`` is missing),
    the rate of the high-growth years after year 3 (``None`` is g_3 as resolved), the number of
    high-growth and fade years, and the terminal growth."""

    revenue0: float
    ntm_revenue: float
    steps: tuple[float | None, float | None]
    hold: float | None
    high_growth_years: int
    fade_years: int
    g_t: float


@dataclass(frozen=True)
class MarginPath:
    """The trailing operating margin, the target and the year the margin reaches it."""

    start: float
    target: float
    convergence_year: int


def _g1(path: RevenuePath) -> float:
    """Year 1's growth: the NTM revenue over trailing revenue, less one."""
    return path.ntm_revenue / path.revenue0 - 1


def resolved_steps(path: RevenuePath) -> tuple[tuple[float, float], tuple[bool, bool]]:
    """``(g_2, g_3)``, a missing step holding the last known rate, and which of the two were
    held."""
    s2, s3 = path.steps
    g2 = _g1(path) if s2 is None else s2
    g3 = g2 if s3 is None else s3
    return (g2, g3), (s2 is None, s3 is None)


def growth_rates(path: RevenuePath) -> tuple[float, ...]:
    """The growth for years 1 to H + ``fade_years``: g_1, g_2, g_3, the hold rate to year H, then
    the fade to g_T."""
    (g2, g3), _ = resolved_steps(path)
    hold = g3 if path.hold is None else path.hold
    h, f = path.high_growth_years, path.fade_years
    fade = tuple(hold - (hold - path.g_t) * (t - h) / f for t in range(h + 1, h + f + 1))
    return (_g1(path), g2, g3, *(hold,) * (h - 3), *fade)


def revenue_by_year(path: RevenuePath) -> tuple[float, ...]:
    """Revenue for years 1 to H + ``fade_years``, year 1 the NTM revenue."""
    rates = growth_rates(path)[1:]
    return tuple(accumulate(rates, lambda rev, g: rev * (1 + g), initial=path.ntm_revenue))


def margins_by_year(margin: MarginPath, years: int) -> tuple[float, ...]:
    """The operating margin for years 1 to ``years``, on the target from the convergence year."""
    c = margin.convergence_year
    return tuple(
        margin.start + (margin.target - margin.start) * min(t, c) / c for t in range(1, years + 1)
    )


def tax_and_nopat(
    ebit: Sequence[float], tax_rate: float
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Tax and NOPAT by year, the tax charged after the losses carried from earlier years."""
    carried = 0.0
    tax: list[float] = []
    for e in ebit:
        if e < 0:
            carried -= e
            tax.append(0.0)
        else:
            tax.append(max(0.0, e - carried) * tax_rate)
            carried = max(0.0, carried - e)
    return tuple(tax), tuple(e - t for e, t in zip(ebit, tax, strict=True))
