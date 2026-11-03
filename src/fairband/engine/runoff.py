"""The Decline route's run-off (spec 2026-11-03 sections 10.2 to 10.7 and 10.9): Damodaran's
shrinking-firm DCF, from the revenue path to the value a share weighted for distress, and the
decline rate the price implies.

Years 1 to 3 take the consensus rates where there are any, a missing step holding the rate of the
year before as the growth route's path does (method 5a.2); with no usable consensus every year
takes the decline rate d. Years 4 to N take d. Revenue_t is the year before's times one plus its
rate, year 0 trailing revenue. One margin is held in every year: EBIT_t = revenue_t × margin. Tax
and NOPAT follow the growth route's carried loss (5a.6).

A year whose revenue falls releases the capital that revenue needed, recovered at ``recovery``:
(revenue_{t−1} − revenue_t) ÷ sales-to-capital × recovery. A year whose revenue rises reinvests
the capital it needs in full, (revenue_t − revenue_{t−1}) ÷ sales-to-capital. Both fall in the
year of the change, not a year ahead as the growth route's reinvestment does (5a.5), and FCFF_t =
NOPAT_t − reinvestment_t + release_t.

The terminal is a perpetuity at d: revenue_{N+1} = revenue_N × (1 + d), its NOPAT at the full tax
rate or untaxed when not positive (``revenue_growth.terminal_nopat``; revenue is positive, so the
test on the operating income is the test on the margin), FCFF_{N+1} that NOPAT plus year N + 1's
release, and the terminal value FCFF_{N+1} ÷ (r − d). The firm value is the flows and the
terminal value discounted at r, the terminal N years.

The going-concern value a share is (firm value − debt + cash) ÷ shares; the net current asset
value a share floors it when it is above zero and above it (10.6). The distress-sale value a
share is max(0, fraction × firm value + cash − debt) ÷ shares, and the value a share is the
floored value × (1 − π) + the distress-sale value × π, the floored value when π is unavailable
(10.7). It may be at or below zero; the route refuses then.

The implied decline rate is the first root of the value a share less the price in [−50%, 0],
scanned in steps of 0.1% and bisected to 1e-7 (method 4.1a), ``None`` when the scan finds no sign
change.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import accumulate, pairwise

from fairband.engine.mature_growth import solve_root
from fairband.engine.revenue_growth import tax_and_nopat, terminal_nopat

# The implied decline rate's scan: from −50% to 0 in steps of 0.1%, bisected to 1e-7 (4.1a).
_IMPLIED_DECLINE_BOUNDS = (-0.5, 0.0)
_IMPLIED_DECLINE_STEP = 0.001
_IMPLIED_DECLINE_TOL = 1e-7


def runoff_rates(
    g1: float | None, g2: float | None, g3: float | None, d: float, years: int
) -> tuple[float, ...]:
    """The rates for years 1 to ``years``: the consensus g_1 to g_3, a missing g_2 or g_3 holding
    the rate of the year before, then d; d in every year when g_1 is ``None`` (no usable
    consensus)."""
    if g1 is None:
        return (d,) * years
    held2 = g1 if g2 is None else g2
    held3 = held2 if g3 is None else g3
    return (g1, held2, held3, *(d,) * (years - 3))


@dataclass(frozen=True)
class RunoffValuation:
    """The tables for years 1 to N, year N + 1's revenue, NOPAT and free cash flow, the terminal
    value at year N, the flows' and the terminal's present values, and the firm value."""

    revenue: tuple[float, ...]
    ebit: tuple[float, ...]
    tax: tuple[float, ...]
    nopat: tuple[float, ...]
    reinvestment: tuple[float, ...]
    release: tuple[float, ...]
    fcff: tuple[float, ...]
    revenue_n1: float
    nopat_n1: float
    fcff_n1: float
    terminal_value: float
    pv_flows: float
    pv_terminal: float
    firm_value: float


def _release(before: float, after: float, sales_to_capital: float, recovery: float) -> float:
    """The capital a fall in revenue frees, recovered at ``recovery``; nothing on a rise."""
    return max(0.0, (before - after) / sales_to_capital) * recovery


def runoff_valuation(
    revenue0: float,
    rates: Sequence[float],
    margin: float,
    tax_rate: float,
    sales_to_capital: float,
    recovery: float,
    r: float,
    d: float,
) -> RunoffValuation:
    """The run-off DCF from trailing revenue and the rates for years 1 to N to the firm value."""
    path = tuple(accumulate(rates, lambda rev, g: rev * (1 + g), initial=revenue0))
    revenue = path[1:]
    ebit = tuple(rev * margin for rev in revenue)
    tax, nopat = tax_and_nopat(ebit, tax_rate)
    steps = tuple(pairwise(path))
    reinvestment = tuple(max(0.0, (after - before) / sales_to_capital) for before, after in steps)
    release = tuple(_release(before, after, sales_to_capital, recovery) for before, after in steps)
    fcff = tuple(n - i + rel for n, i, rel in zip(nopat, reinvestment, release, strict=True))
    revenue_n1 = revenue[-1] * (1 + d)
    nopat_n1 = terminal_nopat(revenue_n1 * margin, tax_rate)
    fcff_n1 = nopat_n1 + _release(revenue[-1], revenue_n1, sales_to_capital, recovery)
    terminal = fcff_n1 / (r - d)
    pv_flows = sum(f / (1 + r) ** t for t, f in enumerate(fcff, start=1))
    pv_terminal = terminal / (1 + r) ** len(fcff)
    return RunoffValuation(
        revenue,
        ebit,
        tax,
        nopat,
        reinvestment,
        release,
        fcff,
        revenue_n1,
        nopat_n1,
        fcff_n1,
        terminal,
        pv_flows,
        pv_terminal,
        pv_flows + pv_terminal,
    )


@dataclass(frozen=True)
class Equity:
    """The value a share and its steps: the going-concern value, the net current asset value a
    share (``None`` without one), the floored value and whether the floor bound, the distress-sale
    value and the value weighted by π."""

    gc_per_share: float
    ncav_per_share: float | None
    floored_per_share: float
    floor_bound: bool
    distress_per_share: float
    value_per_share: float


def runoff_equity(
    firm_value: float,
    debt: float,
    cash: float,
    shares: float,
    ncav: float | None,
    pi: float | None,
    fraction: float,
) -> Equity:
    """The going-concern value a share, floored by the net current asset value when that is above
    zero and above it, weighted against the distress-sale value at π; the floored value when π is
    ``None``. Not clamped: the value may be at or below zero."""
    gc = (firm_value - debt + cash) / shares
    ncav_per_share = None if ncav is None else ncav / shares
    floor = ncav_per_share if ncav_per_share is not None and ncav_per_share > 0 else -math.inf
    floored = max(gc, floor)
    distress = max(0.0, fraction * firm_value + cash - debt) / shares
    value = floored if pi is None else floored * (1 - pi) + distress * pi
    return Equity(gc, ncav_per_share, floored, floor > gc, distress, value)


def implied_decline_rate(value_at: Callable[[float], float], price: float) -> float | None:
    """The decline rate in [−50%, 0] at which ``value_at`` equals the price, or ``None`` when the
    scan finds no sign change: the price above the value at 0 or below the value at −50% when the
    value rises with d."""
    lo, hi = _IMPLIED_DECLINE_BOUNDS
    return solve_root(
        lambda d: value_at(d) - price,
        lo,
        hi,
        step=_IMPLIED_DECLINE_STEP,
        tol=_IMPLIED_DECLINE_TOL,
    )
