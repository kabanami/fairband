"""The Start-up route's price-implied requirement (spec 2026-11-03 section 9.2): the firm value of a
ten-year ramp to a year-10 revenue, and the year-10 revenue at which that firm value is the
enterprise value the price implies.

The ramp. Revenue moves in a straight line from trailing revenue R0 to the year-10 revenue R10,
R_t = R0 + (R10 − R0) × t ÷ 10; operating income, in dollars, from the trailing operating income
E0 to the target margin's share of R10, EBIT_t = E0 + (m* × R10 − E0) × t ÷ 10. A pre-revenue
company has no margin, so the path is on the loss in dollars. Tax and NOPAT follow the
revenue-growth route's carried loss from zero (``revenue_growth.tax_and_nopat``); the terminal
reads year 10's operating income at the full rate, untaxed when not positive
(``revenue_growth.terminal_nopat``). Reinvestment in years 1 to 9 pays for the next year's revenue
at the sales-to-capital, never below zero, and year 10's for g_T on the terminal NOPAT at the
terminal return (``revenue_growth.reinvestment_by_year``). The free cash flow is NOPAT less
reinvestment; the terminal value is the terminal NOPAT times the mature routes' terminal multiple;
the firm value is the flows and the terminal value discounted at r, the terminal ten years.

The requirement is the least R10 in [0, 10^13] at which the ramp is worth the price's enterprise
value: 0 when the ramp to no revenue already is; else found by bisection to a relative tolerance
of 1e-9 (method 4.1a); ``None`` when even 10^13 falls short.
"""

from dataclasses import dataclass

from fairband.engine.mature_growth import terminal_multiple
from fairband.engine.revenue_growth import (
    RevenueCharge,
    reinvestment_by_year,
    tax_and_nopat,
    terminal_nopat,
)

_RAMP_YEARS = 10
# The requirement's solve: bisection on [0, 10^13] to a relative tolerance of 1e-9 (method 4.1a).
_REVENUE_BOUNDS = (0.0, 1e13)
_REVENUE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class RampValuation:
    """The tables for years 1 to 10, year 10's NOPAT at the full tax rate that the terminal reads,
    the terminal value, the flows' and the terminal's present values, and the firm value."""

    revenue: tuple[float, ...]
    ebit: tuple[float, ...]
    tax: tuple[float, ...]
    nopat: tuple[float, ...]
    reinvestment: tuple[float, ...]
    fcff: tuple[float, ...]
    terminal_nopat: float
    terminal_value: float
    pv_flows: float
    pv_terminal: float
    firm_value: float


def ramp_ev(
    revenue_y10: float,
    revenue0: float,
    ebit0: float,
    target_margin: float,
    tax_rate: float,
    sales_to_capital: float,
    r: float,
    g_t: float,
    terminal_return: float,
) -> RampValuation:
    """The firm value of the ten-year ramp from ``revenue0`` and ``ebit0`` to ``revenue_y10`` at
    the target margin; ``sales_to_capital`` must be positive."""
    steps = range(1, _RAMP_YEARS + 1)
    revenue = tuple(revenue0 + (revenue_y10 - revenue0) * t / _RAMP_YEARS for t in steps)
    ebit_y10 = target_margin * revenue_y10
    ebit = tuple(ebit0 + (ebit_y10 - ebit0) * t / _RAMP_YEARS for t in steps)
    tax, nopat = tax_and_nopat(ebit, tax_rate)
    taxed = terminal_nopat(ebit[-1], tax_rate)
    charge = RevenueCharge(r, g_t, terminal_return, sales_to_capital)
    reinvestment = reinvestment_by_year(revenue, taxed, charge)
    fcff = tuple(n - i for n, i in zip(nopat, reinvestment, strict=True))
    terminal = taxed * terminal_multiple(terminal_return, r, g_t)
    pv_flows = sum(f / (1 + r) ** t for t, f in enumerate(fcff, start=1))
    pv_terminal = terminal / (1 + r) ** _RAMP_YEARS
    return RampValuation(
        revenue,
        ebit,
        tax,
        nopat,
        reinvestment,
        fcff,
        taxed,
        terminal,
        pv_flows,
        pv_terminal,
        pv_flows + pv_terminal,
    )


def required_revenue(ev_price: float, **ramp: float) -> float | None:
    """The least year-10 revenue in [0, 10^13] at which ``ramp_ev`` with ``ramp``'s other inputs is
    worth ``ev_price``: 0 when the ramp to no revenue is; ``None`` when 10^13 is not."""
    lo, hi = _REVENUE_BOUNDS
    if ramp_ev(hi, **ramp).firm_value < ev_price:
        return None
    if ramp_ev(lo, **ramp).firm_value >= ev_price:
        return lo
    while hi - lo > _REVENUE_TOLERANCE * hi:
        mid = (lo + hi) / 2
        if not lo < mid < hi:  # the floats between them are exhausted
            break
        if ramp_ev(mid, **ramp).firm_value < ev_price:
            lo = mid
        else:
            hi = mid
    return hi
