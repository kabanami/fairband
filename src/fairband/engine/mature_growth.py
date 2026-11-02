"""Mature Growth: the reverse DCF with the reinvestment charge (``design.md`` 6.5 and 6.6), with
the fade, the payout floor and the charge-off rule of the calibration spec (5.4, 5.2, 5.1 rule 4).

Year-1 earnings are the NTM net income, a total held on one share count. Years 2 and 3 grow by
the consensus steps, a missing step taking the belief. When year 3's growth is above the belief,
years 4 to 3 + ``fade_years`` fade from it to the belief in equal steps; the other years to the
runway N grow at the belief. The runway cuts the path, not the fade.

Each year's reinvestment pays for the next year's growth: cash to equity in year t is
earnings_t × max(0, 1 − g_{t+1} ÷ ROIC), at the runway ROIC for years 1 to N−1 and, in year N, at
the terminal growth and the terminal ROIC. The floor at zero treats the growth above the return
as efficiency growth, which costs nothing. The terminal value is earnings_N times the terminal
multiple at the terminal ROIC, discounted N years. An infinite ROIC means no charge. ``charge_off``,
set when the marginal return is not usable and the three-year capital sum is at or below zero
(spec 5.1 rule 4), drops the charge in years 1 to N−1 only: year N and the terminal value still
charge at the terminal ROIC.
"""

import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from itertools import accumulate
from typing import NamedTuple

_SCAN_STEP = 0.01


@dataclass(frozen=True)
class GrowthPath:
    """Year-1 net income, the growth for years 2 and 3 (``None`` is the belief), the belief for
    years 4 to ``runway``, reached over ``fade_years`` when year 3's growth is above it."""

    year1: float
    steps: tuple[float | None, float | None]
    belief: float
    runway: int
    fade_years: int = 0


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
    g2, g3 = (path.belief if g is None else g for g in path.steps)
    fade = _fade(g3, path.belief, path.fade_years)
    rates = (g2, g3, *fade) + (path.belief,) * max(path.runway - 3 - len(fade), 0)
    return rates[: max(path.runway - 1, 0)]


def _fade(g3: float, belief: float, years: int) -> tuple[float, ...]:
    """The growth for years 4 to 3 + ``years``, in equal steps from ``g3`` down to the belief,
    the last on the belief exactly; empty when ``g3`` is at or below the belief."""
    if years <= 0 or g3 <= belief:
        return ()
    return tuple(belief + (g3 - belief) * (years - k) / years for k in range(1, years + 1))


def earnings_by_year(path: GrowthPath) -> tuple[float, ...]:
    """Net income for years 1 to the runway."""
    return tuple(accumulate(growth_rates(path), lambda e, g: e * (1 + g), initial=path.year1))


def cash_to_equity(ni: float, g_next: float, roic: float, charge_off: bool = False) -> float:
    """Earnings less the reinvestment that pays for the next year's growth, never below zero."""
    if charge_off or roic == math.inf:
        return ni
    return ni * max(0.0, 1 - g_next / roic)


def terminal_multiple(roic: float, r: float, g_t: float) -> float:
    """The terminal value as a multiple of the final year's earnings."""
    return (1 + g_t) * (1 - g_t / roic) / (r - g_t)


class _Year(NamedTuple):
    """One year of the runway: its earnings, the growth it pays for, the return it pays at, and
    whether its charge is off."""

    t: int
    ni: float
    g_next: float
    roic: float
    charge_off: bool


def _years(path: GrowthPath, charge: Charge) -> Iterator[_Year]:
    """Years 1 to the runway; ``charge_off`` reaches years 1 to N−1 only."""
    n = path.runway
    following = (*growth_rates(path), charge.g_t)
    for t, (ni, g_next) in enumerate(zip(earnings_by_year(path), following, strict=True), start=1):
        roic = charge.runway_roic if t < n else charge.terminal_roic
        yield _Year(t, ni, g_next, roic, charge.charge_off and t < n)


def value_at_belief(path: GrowthPath, charge: Charge) -> float:
    """The total equity value: the discounted cash to equity for each year and the terminal."""
    n, r = path.runway, charge.r
    years = tuple(_years(path, charge))
    value = 0.0
    for y in years:
        value += cash_to_equity(y.ni, y.g_next, y.roic, y.charge_off) / (1 + r) ** y.t
    final = years[-1].ni
    return value + final * terminal_multiple(charge.terminal_roic, r, charge.g_t) / (1 + r) ** n


def _floored(path: GrowthPath, charge: Charge) -> Iterator[_Year]:
    """The years whose payout the floor raised to zero: growth above the return."""
    return (y for y in _years(path, charge) if not y.charge_off and 1 - y.g_next / y.roic < 0)


def floored_years(path: GrowthPath, charge: Charge) -> tuple[int, ...]:
    """The years, in order, whose payout the floor raised to zero: growth above the return."""
    return tuple(y.t for y in _floored(path, charge))


def first_floored_year(path: GrowthPath, charge: Charge) -> tuple[int, float, float] | None:
    """The first year whose payout the floor raised to zero as ``(t, g_next, roic)``: the year,
    the growth its reinvestment pays for (year t + 1's) and the return it pays at; ``None`` when
    no year floors."""
    first = next(_floored(path, charge), None)
    return None if first is None else (first.t, first.g_next, first.roic)


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

    return solve_root(gap, lo, hi, tol=tol)


def solve_root(
    gap: Callable[[float], float],
    lo: float,
    hi: float,
    step: float = _SCAN_STEP,
    tol: float = 1e-7,
) -> float | None:
    """The first root of ``gap`` in ``[lo, hi]``, or ``None`` when the scan finds no sign change.

    Scans from ``lo`` to ``hi`` in equal steps of about ``step`` for the first sign change, then
    bisects it to ``tol``.
    """
    n = max(1, round((hi - lo) / step))
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
