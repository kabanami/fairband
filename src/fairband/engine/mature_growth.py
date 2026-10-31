"""Mature Growth: the reverse DCF with the reinvestment charge (``design.md`` 6.5 and 6.6).

Year-1 earnings are the NTM net income, a total held on one share count. Years 2 and 3 grow by
the consensus steps, a missing step taking the belief; years 4 to the runway N grow at the
belief. Each year's reinvestment pays for the next year's growth: cash to equity in year t is
earnings_t × (1 − g_{t+1} ÷ ROIC), at the runway ROIC for years 1 to N−1 and, in year N, at the
terminal growth and the terminal ROIC. The terminal value is earnings_N times the terminal
multiple, discounted N years. An infinite ROIC, or ``charge_off`` when invested capital is zero or
below, means no charge.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import accumulate

_SCAN_STEP = 0.01


@dataclass(frozen=True)
class GrowthPath:
    """Year-1 net income, the growth for years 2 and 3 (``None`` is the belief), the belief for
    years 4 to ``runway``."""

    year1: float
    steps: tuple[float | None, float | None]
    belief: float
    runway: int


@dataclass(frozen=True)
class Charge:
    """The ROIC for the runway years and the terminal, the required return and terminal growth."""

    runway_roic: float
    terminal_roic: float
    r: float
    g_t: float
    charge_off: bool = False


def growth_rates(path: GrowthPath) -> tuple[float, ...]:
    """The growth for years 2 to the runway; empty for a one-year runway."""
    steps = tuple(path.belief if g is None else g for g in path.steps)
    rates = steps + (path.belief,) * max(path.runway - 3, 0)
    return rates[: max(path.runway - 1, 0)]


def earnings_by_year(path: GrowthPath) -> tuple[float, ...]:
    """Net income for years 1 to the runway."""
    return tuple(accumulate(growth_rates(path), lambda e, g: e * (1 + g), initial=path.year1))


def cash_to_equity(ni: float, g_next: float, roic: float, charge_off: bool = False) -> float:
    """Earnings less the reinvestment that pays for the next year's growth."""
    if charge_off or roic == math.inf:
        return ni
    return ni * (1 - g_next / roic)


def terminal_multiple(roic: float, r: float, g_t: float) -> float:
    """The terminal value as a multiple of the final year's earnings."""
    return (1 + g_t) * (1 - g_t / roic) / (r - g_t)


def value_at_belief(path: GrowthPath, charge: Charge) -> float:
    """The total equity value: the discounted cash to equity for each year and the terminal."""
    n, r = path.runway, charge.r
    earnings = earnings_by_year(path)
    following = (*growth_rates(path), charge.g_t)
    value = 0.0
    for t, (ni, g_next) in enumerate(zip(earnings, following, strict=True), start=1):
        roic = charge.runway_roic if t < n else charge.terminal_roic
        value += cash_to_equity(ni, g_next, roic, charge.charge_off) / (1 + r) ** t
    terminal_roic = math.inf if charge.charge_off else charge.terminal_roic
    return value + earnings[-1] * terminal_multiple(terminal_roic, r, charge.g_t) / (1 + r) ** n


def implied_growth(
    target: float,
    path: GrowthPath,
    charge: Charge,
    lo: float = -0.5,
    hi: float = 0.5,
    tol: float = 1e-7,
) -> float | None:
    """The belief at which the value equals ``target``, or ``None`` when ``[lo, hi]`` has none.

    Scans from ``lo`` to ``hi`` in steps of 0.01 for the first sign change, then bisects it.
    """

    def gap(g: float) -> float:
        return value_at_belief(replace(path, belief=g), charge) - target

    n = max(1, round((hi - lo) / _SCAN_STEP))
    a, fa = lo, gap(lo)
    if fa == 0:
        return a
    for i in range(1, n + 1):
        b = lo + (hi - lo) * i / n
        fb = gap(b)
        if fb == 0:
            return b
        if (fa < 0) != (fb < 0):
            return _bisect(gap, a, fa, b, tol)
        a, fa = b, fb
    return None


def _bisect(f: Callable[[float], float], a: float, fa: float, b: float, tol: float) -> float:
    """A root of ``f`` between ``a`` and ``b``, where ``f(a)`` and ``f(b)`` differ in sign."""
    while abs(b - a) > tol:
        m = (a + b) / 2
        fm = f(m)
        if fm == 0:
            return m
        if (fa < 0) == (fm < 0):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2
