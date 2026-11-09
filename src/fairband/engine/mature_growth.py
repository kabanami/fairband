"""Mature Growth: the reverse DCF with the reinvestment charge (``design.md`` 6.5 and 6.6), with
the fade and the charge-off rule of the calibration spec (5.4, 5.1 rule 4) and the charge of the
engine round 2 spec (2026-11-09, 6.1 to 6.3).

Year-1 earnings are the NTM net income, a total held on one share count. Years 2 and 3 grow by
the consensus steps, a missing step taking the belief. When year 3's growth is above the belief,
years 4 to 3 + ``fade_years`` fade from it to the belief in equal steps; the other years to the
runway N grow at the belief. The runway cuts the path, not the fade.

Each year's reinvestment pays for the next year's growth h: cash to equity in year t is
earnings_t × (1 − h_{t+1} ÷ return_t), with no floor, so a year whose growth outruns its return
pays out less than nothing: the owner funds the growth (6.1). h for years 2 and 3 is the
consensus revenue step, a missing one taking the earnings step of the same year; h fades from
year 3's to the belief as the earnings path fades, grows at the belief after, and h_{N+1} is the
terminal growth (6.2). A path without revenue steps charges its earnings growth.

The return holds at the runway return R through the hold K, then fades in equal steps to the
terminal return T, which year N takes: return_t = R + (T − R) × (t − K) ÷ (N − K) for K < t ≤ N
(6.3). K is the last year t below N whose next earnings growth is above the belief, read once
from the row's own path. A hold of ``None`` is the shape as built, R for years 1 to N − 1 and T
in year N, which every caller keeps until the routes pass a hold; a hold of N − 1 or more gives
the same. The terminal value is earnings_N times the terminal multiple at T, discounted N years.
An infinite return means no charge. ``charge_off``, set when the marginal return is not usable and
the three-year capital sum is at or below zero (spec 5.1 rule 4), drops the charge in years 1 to
N−1 only: year N and the terminal value still charge at the terminal return.
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
    years 4 to ``runway``, reached over ``fade_years`` when year 3's growth is above it, and the
    revenue steps for years 2 and 3 that the charge pays for (``None``, for either or both, takes
    the earnings step)."""

    year1: float
    steps: tuple[float | None, float | None]
    belief: float
    runway: int
    fade_years: int = 0
    revenue_steps: tuple[float | None, float | None] | None = None


@dataclass(frozen=True)
class Charge:
    """The ROIC for the runway years and the terminal, the required return and terminal growth,
    whether the runway years' charge is off, and the hold: the years the runway ROIC holds before
    it fades to the terminal (``None`` is the shape as built, the runway ROIC to year N − 1)."""

    runway_roic: float
    terminal_roic: float
    r: float
    g_t: float
    charge_off: bool = False
    hold: int | None = None


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


def charge_growth(path: GrowthPath) -> tuple[float, ...]:
    """The growth the charge pays for, h, for years 2 to the runway: the revenue steps for years 2
    and 3, each missing one taking the earnings step of the same year, then the fade from year 3's
    to the belief as the earnings path fades; the earnings growth without revenue steps."""
    r2, r3 = path.revenue_steps or (None, None)
    e2, e3 = path.steps
    return growth_rates(replace(path, steps=(e2 if r2 is None else r2, e3 if r3 is None else r3)))


def hold_years(path: GrowthPath) -> int:
    """The hold K: the last year t in 1 to N − 1 whose next earnings growth g_{t+1} is above the
    belief, so a flat step inside the consensus steps or the fade does not end it; 0 when none is."""
    above = (t for t, g in enumerate(growth_rates(path), start=1) if g > path.belief)
    return max(above, default=0)


def return_by_year(charge: Charge, n: int) -> tuple[float, ...]:
    """The return years 1 to ``n`` pay at: the runway ROIC through the hold, then in equal steps to
    the terminal ROIC, which year ``n`` takes exactly. A hold of ``None``, or of ``n`` − 1 or more,
    is the shape as built: the runway ROIC to year ``n`` − 1."""
    runway, terminal, hold = charge.runway_roic, charge.terminal_roic, charge.hold
    if hold is None or hold >= n - 1 or n <= 1:
        return (runway,) * max(n - 1, 0) + (terminal,)
    fade = (runway + (terminal - runway) * (t - hold) / (n - hold) for t in range(hold + 1, n))
    return (runway,) * hold + tuple(fade) + (terminal,)


def earnings_by_year(path: GrowthPath) -> tuple[float, ...]:
    """Net income for years 1 to the runway."""
    return tuple(accumulate(growth_rates(path), lambda e, g: e * (1 + g), initial=path.year1))


def cash_to_equity(ni: float, g_next: float, roic: float, charge_off: bool = False) -> float:
    """Earnings less the reinvestment that pays for the next year's growth, with no floor: below
    zero when the growth outruns the return."""
    if charge_off or roic == math.inf:
        return ni
    return ni * (1 - g_next / roic)


def terminal_multiple(roic: float, r: float, g_t: float) -> float:
    """The terminal value as a multiple of the final year's earnings."""
    return (1 + g_t) * (1 - g_t / roic) / (r - g_t)


class _Year(NamedTuple):
    """One year of the runway: its earnings, the growth it pays for, the return it pays at, and
    whether its charge is off."""

    t: int
    ni: float
    h_next: float
    roic: float
    charge_off: bool


def _years(path: GrowthPath, charge: Charge) -> Iterator[_Year]:
    """Years 1 to the runway; ``charge_off`` reaches years 1 to N−1 only."""
    n = path.runway
    paid_for = (*charge_growth(path), charge.g_t)
    years = zip(earnings_by_year(path), paid_for, return_by_year(charge, n), strict=True)
    for t, (ni, h_next, roic) in enumerate(years, start=1):
        yield _Year(t, ni, h_next, roic, charge.charge_off and t < n)


def value_at_belief(path: GrowthPath, charge: Charge) -> float:
    """The total equity value: the discounted cash to equity for each year and the terminal."""
    n, r = path.runway, charge.r
    years = tuple(_years(path, charge))
    value = 0.0
    for y in years:
        value += cash_to_equity(y.ni, y.h_next, y.roic, y.charge_off) / (1 + r) ** y.t
    final = years[-1].ni
    return value + final * terminal_multiple(charge.terminal_roic, r, charge.g_t) / (1 + r) ** n


def _negative(path: GrowthPath, charge: Charge) -> Iterator[_Year]:
    """The years that pay out less than nothing: the growth they pay for above their return."""
    return (y for y in _years(path, charge) if not y.charge_off and 1 - y.h_next / y.roic < 0)


def negative_years(path: GrowthPath, charge: Charge) -> tuple[int, ...]:
    """The years, in order, that pay out less than nothing: the owner funds the growth."""
    return tuple(y.t for y in _negative(path, charge))


def first_negative_year(path: GrowthPath, charge: Charge) -> tuple[int, float, float] | None:
    """The first year that pays out less than nothing as ``(t, h_next, roic)``: the year, the
    growth its reinvestment pays for (year t + 1's) and the return it pays at; ``None`` when no
    year does."""
    first = next(_negative(path, charge), None)
    return None if first is None else (first.t, first.h_next, first.roic)


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
