"""High Growth and Young Growth: Damodaran's revenue DCF, from the revenue path to the value a
share, the two figures the price implies, and the sales-to-capital and peer figures it reads
(growth-routes spec 5.3 to 5.8, 5.10 and 5.11).

Year 0 is trailing revenue and year 1 the NTM consensus revenue, so g_1 is the NTM revenue over
trailing revenue less one. Years 2 and 3 grow at the consensus steps; a missing step holds the
last known rate, g_1 for g_2 and g_2 for g_3. Years 4 to H, H being ``high_growth_years``, grow
at the hold rate, g_3 as resolved unless one is given. Years H + 1 to N = H + ``fade_years`` fade
from the hold rate to the terminal growth g_T in equal steps,
g_t = g_T + (hold − g_T) × (N − t) ÷ ``fade_years``, the last on g_T exactly; when the hold rate is
below g_T the same line rises to it.

The operating margin moves in a straight line from the trailing margin to the target, reaching it
in ``convergence_year`` and staying there: m_t = start + (target − start) × min(t, convergence
year) ÷ convergence year. A margin above the target moves down the same line.

Tax is charged after the forecast's own losses, the carried loss starting at zero because no
history of tax losses is stored. A loss year adds its size to the carried loss and pays no tax; a
profit year is taxed on what it earns above the carried loss and uses the carried loss up by its
operating income, never below zero. NOPAT is operating income less tax.

Reinvestment in year t pays for year t + 1's revenue at the sales-to-capital,
(revenue_{t+1} − revenue_t) ÷ sales-to-capital, never below zero, for years 1 to N − 1. Year N
pays for the terminal growth at the terminal return, NOPAT_N × g_T ÷ terminal return, as the
mature routes' year N does; it has no floor. The free cash flow is NOPAT less reinvestment, and
a negative one is the method, not a refusal. The terminal value is NOPAT_N times the mature
routes' terminal multiple, (1 + g_T) × (1 − g_T ÷ terminal return) ÷ (r − g_T). The firm value is
the free cash flows and the terminal value discounted at r, the terminal N years; equity is the
firm value less debt plus cash, and the value a share is equity over the diluted share count.

The return on new capital at the target margin is target × (1 − tax rate) × sales-to-capital;
the terminal return is ``roic.terminal_roic`` on it. Two figures move with the price, each the
first root of the value a share less the price, found by ``mature_growth.solve_root``: the hold
rate, between −50% and 200%, the fade recomputed from it and years 1 to 3 unchanged; and the
target margin, between the policy's implied-margin bounds, the terminal return re-read from the
return on new capital at each trial margin, at the policy's required return and the path's g_T.

The company's own sales-to-capital is the change in revenue over the change in average invested
capital from the kept ROIC year ``span`` positions before the newest to the newest, each year's
revenue its fiscal year's. It is usable when capital grew, by at least ``growth_min`` of the
earlier year's capital in size, and revenue grew; there is none with fewer than ``span + 1`` kept
years, either year without a revenue, or no change in capital.

The peer figures are the mature peers'. The target margin is the median of the ten-year
aggregate operating margins of the peers with at least the policy's minimum years of margin, with
the lowest, the highest and the largest such peer's by market cap; there is none below the
policy's peer minimum. The peers' sales-to-capital is the median of the positive ones, none below
the peer minimum; the peers' ROIC is the median of those known.
"""

import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import accumulate, pairwise

from fairband.engine.mature_growth import solve_root, terminal_multiple
from fairband.engine.roic import RoicYear, terminal_roic
from fairband.policy import Moat, Policy


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
    the fade to g_T, the last on g_T exactly."""
    (g2, g3), _ = resolved_steps(path)
    hold = g3 if path.hold is None else path.hold
    h, f = path.high_growth_years, path.fade_years
    n = h + f
    fade = tuple(path.g_t + (hold - path.g_t) * (n - t) / f for t in range(h + 1, n + 1))
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


@dataclass(frozen=True)
class RevenueCharge:
    """The required return, the terminal growth, the terminal return on new capital, and the
    revenue a unit of new capital buys."""

    r: float
    g_t: float
    terminal_return: float
    sales_to_capital: float


@dataclass(frozen=True)
class Bridge:
    """Debt and cash from the newest annual balance sheet, and the diluted share count."""

    debt: float
    cash: float
    shares: float


def reinvestment_by_year(
    revenue: Sequence[float], nopat: Sequence[float], charge: RevenueCharge
) -> tuple[float, ...]:
    """Reinvestment for years 1 to N: years 1 to N − 1 pay for the next year's revenue at the
    sales-to-capital, never below zero; year N pays for g_T at the terminal return."""
    growth = (max(0.0, (nxt - cur) / charge.sales_to_capital) for cur, nxt in pairwise(revenue))
    return (*growth, nopat[-1] * charge.g_t / charge.terminal_return)


@dataclass(frozen=True)
class RevenueValuation:
    """The tables for years 1 to N, the terminal value, the firm value, equity and the value a
    share."""

    revenue: tuple[float, ...]
    margins: tuple[float, ...]
    ebit: tuple[float, ...]
    tax: tuple[float, ...]
    nopat: tuple[float, ...]
    reinvestment: tuple[float, ...]
    fcff: tuple[float, ...]
    terminal_value: float
    firm_value: float
    equity: float
    value_per_share: float


def revenue_valuation(
    path: RevenuePath, margin: MarginPath, tax_rate: float, charge: RevenueCharge, bridge: Bridge
) -> RevenueValuation:
    """The revenue DCF from the revenue path to the value a share."""
    revenue = revenue_by_year(path)
    margins = margins_by_year(margin, len(revenue))
    ebit = tuple(rev * m for rev, m in zip(revenue, margins, strict=True))
    tax, nopat = tax_and_nopat(ebit, tax_rate)
    reinvestment = reinvestment_by_year(revenue, nopat, charge)
    fcff = tuple(n - i for n, i in zip(nopat, reinvestment, strict=True))
    r = charge.r
    terminal = nopat[-1] * terminal_multiple(charge.terminal_return, r, charge.g_t)
    discounted = sum(f / (1 + r) ** t for t, f in enumerate(fcff, start=1))
    firm = discounted + terminal / (1 + r) ** len(fcff)
    equity = firm - bridge.debt + bridge.cash
    return RevenueValuation(
        revenue,
        margins,
        ebit,
        tax,
        nopat,
        reinvestment,
        fcff,
        terminal,
        firm,
        equity,
        equity / bridge.shares,
    )


def return_on_new_capital(target_margin: float, tax_rate: float, sales_to_capital: float) -> float:
    """The after-tax return on new capital at the target margin."""
    return target_margin * (1 - tax_rate) * sales_to_capital


def implied_hold_growth(
    target_value: float,
    path: RevenuePath,
    margin: MarginPath,
    tax_rate: float,
    charge: RevenueCharge,
    bridge: Bridge,
    lo: float = -0.5,
    hi: float = 2.0,
) -> float | None:
    """The hold rate at which the value a share equals ``target_value``, or ``None`` when
    ``[lo, hi]`` has none."""

    def gap(hold: float) -> float:
        value = revenue_valuation(replace(path, hold=hold), margin, tax_rate, charge, bridge)
        return value.value_per_share - target_value

    return solve_root(gap, lo, hi)


def implied_target_margin(
    target_value: float,
    path: RevenuePath,
    margin: MarginPath,
    tax_rate: float,
    sales_to_capital: float,
    moat: Moat,
    policy: Policy,
    bridge: Bridge,
) -> float | None:
    """The target margin at which the value a share equals ``target_value``, or ``None`` when the
    policy's implied-margin bounds have none; the terminal return is re-read at each trial."""

    def gap(target: float) -> float:
        new_capital = return_on_new_capital(target, tax_rate, sales_to_capital)
        terminal = terminal_roic(new_capital, moat, policy)
        charge = RevenueCharge(policy.required_return, path.g_t, terminal, sales_to_capital)
        trial = replace(margin, target=target)
        value = revenue_valuation(path, trial, tax_rate, charge, bridge)
        return value.value_per_share - target_value

    lo, hi = policy.implied_margin_bounds
    return solve_root(gap, lo, hi)


def own_sales_to_capital(
    kept: Sequence[RoicYear],
    revenue_by_fiscal_year: Mapping[int, float],
    span: int,
    growth_min: float,
) -> tuple[float | None, bool]:
    """The change in revenue over the change in average capital from the kept year ``span``
    positions before the newest to the newest, and whether it is usable: capital grew, by at
    least ``growth_min`` of the earlier year's capital, and revenue grew.

    ``(None, False)`` with fewer than ``span + 1`` kept years, either year without a revenue, or
    no change in capital.
    """
    if len(kept) < span + 1:
        return None, False
    first, last = kept[-1 - span], kept[-1]
    revenue_first = revenue_by_fiscal_year.get(first.year)
    revenue_last = revenue_by_fiscal_year.get(last.year)
    if revenue_first is None or revenue_last is None:
        return None, False
    delta_capital = last.average_capital - first.average_capital
    if delta_capital == 0:
        return None, False
    delta_revenue = revenue_last - revenue_first
    usable = (
        delta_capital > 0
        and delta_capital >= growth_min * abs(first.average_capital)
        and delta_revenue > 0
    )
    return delta_revenue / delta_capital, usable


@dataclass(frozen=True)
class PeerFigures:
    """A mature peer: its market cap; its ten-year aggregate operating margin and the years in
    it; its last fiscal year's revenue over its newest average invested capital; its ten-year
    aggregate ROIC. ``None`` is unknown."""

    symbol: str
    market_cap: float | None
    margin: float | None
    margin_years: int
    sales_to_capital: float | None
    roic: float | None


@dataclass(frozen=True)
class TargetMargin:
    """The peers' median margin, the number of peers counted, the lowest and the highest, the
    largest counted peer by market cap and its margin (``None`` when no counted peer has a market
    cap), and the counted peers."""

    value: float
    count: int
    low: float
    high: float
    largest_symbol: str | None
    largest_margin: float | None
    peers: tuple[PeerFigures, ...]


def target_margin(peers: Sequence[PeerFigures], policy: Policy) -> TargetMargin | None:
    """The median margin of the peers with a margin on at least the policy's minimum years;
    ``None`` below the policy's peer minimum."""
    min_years = policy.peer_margin_min_years
    counted = tuple(p for p in peers if p.margin is not None and p.margin_years >= min_years)
    if len(counted) < policy.peer_min:
        return None
    margins = [p.margin for p in counted if p.margin is not None]
    sized = [(p.market_cap, p) for p in counted if p.market_cap is not None]
    largest = max(sized, key=lambda pair: pair[0])[1] if sized else None
    return TargetMargin(
        value=statistics.median(margins),
        count=len(counted),
        low=min(margins),
        high=max(margins),
        largest_symbol=None if largest is None else largest.symbol,
        largest_margin=None if largest is None else largest.margin,
        peers=counted,
    )


def peer_sales_to_capital(peers: Sequence[PeerFigures], policy: Policy) -> float | None:
    """The median of the peers' positive sales-to-capital; ``None`` below the peer minimum."""
    known = [p.sales_to_capital for p in peers if p.sales_to_capital is not None]
    positive = [x for x in known if x > 0]
    return statistics.median(positive) if len(positive) >= policy.peer_min else None


def peer_roic_median(peers: Sequence[PeerFigures]) -> float | None:
    """The median of the peers' known ROIC; ``None`` when none is known."""
    roics = [p.roic for p in peers if p.roic is not None]
    return statistics.median(roics) if roics else None
