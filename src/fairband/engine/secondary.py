"""The secondary valuation (spec 2026-11-06 Tier 2, section 11; ``method.md`` 15): a second way to
value a company, computed by the engine from inputs an agent supplies, in one of two forms.

The standard form, ``drivers``, projects the free cash flow to the firm by Damodaran's FCFF model
from the trailing revenue, over N years from the policy's ``secondary_years_min`` to
``secondary_years_max``, each driver inside its ``secondary_driver_ranges`` pair:

    revenue_t = revenue_{t−1} × (1 + g_t)
    EBIT_t = revenue_t × m_t;  NOPAT_t = EBIT_t × (1 − t)
    reinvestment_t = max(0, revenue_t − revenue_{t−1}) ÷ s
    FCFF_t = NOPAT_t − reinvestment_t;  PV_t = FCFF_t ÷ (1 + r)^t
    terminal FCFF = NOPAT_N × (1 + g) × (1 − g ÷ ROIC_T)
    terminal = terminal FCFF ÷ (r − g), discounted by (1 + r)^N

A year whose revenue falls reinvests nothing, so a decline does not create cash. ROIC_T is the
policy's terminal return for the moat class, which the caller computes (``roic.terminal_roic``).

The parts form, ``parts``, is plan 1's: a part is a name, the free cash flow to the firm in
dollars for years 1 to N, a terminal growth g and a note, and each part is discounted at r:

    PV_t = fcff_t ÷ (1 + r)^t, t = 1 … N
    terminal = fcff_N × (1 + g) ÷ (r − g), discounted by (1 + r)^N
    part value = Σ PV_t + the discounted terminal

One part is a DCF; several, up to ``secondary_parts_max``, a sum of parts.

Common to both: r is the policy's required return; g is at most the policy's g_T (lower or
negative allowed). The firm value is the projection's value or the sum over the parts; equity =
firm value − debt + cash; the value a share = equity ÷ the diluted shares. The levels on the moat
(``levels_for``) and, with a price, the designation on price ÷ value (``designation_for``) come
only with a value a share above zero: at or below zero the value is kept as computed, with
neither. A secondary valuation takes exactly one form. The rules it refuses raise ``ValueError``
with the rule's sentence, checked in this order: on the drivers form the years, each list's length,
each driver's range (each entry of a list), the terminal growth; on the parts form the part count,
each part's years, each part's terminal growth; then the share count.

The grid is a display, never a value: the value a share by the same arithmetic at the rates
r − 1 pp, r and r + 1 pp (the columns) across the terminal growths g − 1 pp, g and
min(g + 1 pp, g_T) (the rows), ROIC_T held. On the parts form a row moves every part's terminal
growth together, each capped at g_T, and the rows hold the shift, −1 pp, 0 and +1 pp. There is no
grid when the lowest rate is at or below the highest growth in it, which only settings that put
r − 1 pp at or below g_T allow.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Literal

from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.types import Designation, Levels
from fairband.policy import Moat, Policy

SECONDARY_METHOD = "fairband-secondary/2"

Form = Literal["parts", "drivers"]

_STEP = 0.01  # the grid's step on the rate and on the terminal growth, one point (method 4.1a)


@dataclass(frozen=True)
class Drivers:
    """The standard form's drivers: N years, the revenue growth and the operating margin for each
    year, the tax rate, sales-to-capital and the terminal growth, rates as fractions."""

    years: int
    revenue_growth: tuple[float, ...]
    operating_margin: tuple[float, ...]
    tax_rate: float
    sales_to_capital: float
    terminal_growth: float


@dataclass(frozen=True)
class Year:
    """One year of the projection, in dollars."""

    t: int
    revenue: float
    ebit: float
    nopat: float
    reinvestment: float
    fcff: float
    pv: float


@dataclass(frozen=True)
class Projection:
    """The drivers projected: the years, the terminal free cash flow, the terminal at year N, its
    present value, and the firm value."""

    years: tuple[Year, ...]
    terminal_fcff: float
    terminal: float
    terminal_pv: float
    value: float


@dataclass(frozen=True)
class Part:
    """One part of the path: the free cash flow to the firm for years 1 to N, in dollars."""

    name: str
    fcff: tuple[float, ...]
    terminal_growth: float
    note: str | None


@dataclass(frozen=True)
class PartValue:
    """A part discounted: each year's present value, the terminal at year N, its present value,
    and the part's value."""

    name: str
    pv: tuple[float, ...]
    terminal: float
    terminal_pv: float
    value: float


@dataclass(frozen=True)
class SecondaryGrid:
    """The value a share at each row's terminal growth (on the parts form, its shift) and each
    column's rate: ``cells[i][j]`` is row i at column j."""

    rows: tuple[float, float, float]
    cols: tuple[float, float, float]
    cells: tuple[tuple[float, ...], ...]


@dataclass(frozen=True)
class SecondaryValuation:
    """The valuation in one form: the parts discounted (none on the drivers form), or the drivers
    and their projection (``None`` on the parts form); the bridge to a value a share; the grid."""

    form: Form
    parts: tuple[PartValue, ...]
    drivers: Drivers | None
    projection: Projection | None
    firm_value: float
    debt: float
    cash: float
    shares: float
    equity: float
    value_per_share: float
    levels: Levels | None
    price_to_value: float | None
    designation: Designation | None
    grid: SecondaryGrid | None


def project(drivers: Drivers, revenue_0: float, r: float, roic_t: float) -> Projection:
    """The drivers projected from ``revenue_0`` and discounted at ``r``, the terminal's
    reinvestment at ``roic_t`` (module docstring)."""
    tax, s = drivers.tax_rate, drivers.sales_to_capital
    years: list[Year] = []
    previous = revenue_0
    paths = zip(drivers.revenue_growth, drivers.operating_margin, strict=True)
    for t, (growth, margin) in enumerate(paths, start=1):
        revenue = previous * (1 + growth)
        ebit = revenue * margin
        nopat = ebit * (1 - tax)
        reinvestment = max(0.0, revenue - previous) / s
        fcff = nopat - reinvestment
        years.append(Year(t, revenue, ebit, nopat, reinvestment, fcff, fcff / (1 + r) ** t))
        previous = revenue
    g = drivers.terminal_growth
    terminal_fcff = years[-1].nopat * (1 + g) * (1 - g / roic_t)
    terminal = terminal_fcff / (r - g)
    terminal_pv = terminal / (1 + r) ** len(years)
    value = sum(year.pv for year in years) + terminal_pv
    return Projection(tuple(years), terminal_fcff, terminal, terminal_pv, value)


def secondary_value(
    *,
    parts: Sequence[Part] | None = None,
    drivers: Drivers | None = None,
    revenue_0: float | None = None,
    roic_t: float | None = None,
    debt: float,
    cash: float,
    shares: float,
    price: float | None,
    moat: Moat,
    policy: Policy,
) -> SecondaryValuation:
    """The drivers projected, or the parts discounted, at the policy's r and bridged to a value a
    share, with the grid (module docstring). The drivers form takes ``revenue_0``, the trailing
    revenue, and ``roic_t``, the terminal return."""
    if parts is not None and drivers is not None:
        raise ValueError("a secondary valuation takes drivers or parts, not both")
    r, g_t = policy.required_return, policy.terminal_growth
    form: Form
    projection: Projection | None = None
    valued: tuple[PartValue, ...] = ()
    if drivers is not None:
        if revenue_0 is None or roic_t is None:
            raise TypeError("the drivers form takes revenue_0 and roic_t")
        _check_drivers(drivers, policy)
        _check_shares(shares)
        form = "drivers"
        projection = project(drivers, revenue_0, r, roic_t)
        firm_value = projection.value
        grid = _drivers_grid(drivers, revenue_0, roic_t, r, g_t, (debt, cash, shares))
    elif parts is not None:
        _check_parts(parts, policy)
        _check_shares(shares)
        form = "parts"
        valued = tuple(_discounted(part, r) for part in parts)
        firm_value = sum(part.value for part in valued)
        grid = _parts_grid(parts, r, g_t, (debt, cash, shares))
    else:
        raise ValueError("a secondary valuation needs drivers or parts")
    equity = firm_value - debt + cash
    per_share = equity / shares
    levels, price_to_value, designation = None, None, None
    if per_share > 0:
        levels = levels_for(per_share, moat, policy)
        if price is not None and price > 0:
            price_to_value, designation = designation_for(
                price, per_share, policy.designation_edges
            )
    return SecondaryValuation(
        form=form,
        parts=valued,
        drivers=drivers,
        projection=projection,
        firm_value=firm_value,
        debt=debt,
        cash=cash,
        shares=shares,
        equity=equity,
        value_per_share=per_share,
        levels=levels,
        price_to_value=price_to_value,
        designation=designation,
        grid=grid,
    )


def _check_drivers(drivers: Drivers, policy: Policy) -> None:
    shortest, longest = policy.secondary_years_min, policy.secondary_years_max
    n = drivers.years
    if not shortest <= n <= longest:
        raise ValueError(f"a secondary valuation runs {shortest} to {longest} years")
    by_year = (
        ("revenue_growth", drivers.revenue_growth),
        ("operating_margin", drivers.operating_margin),
    )
    for name, values in by_year:
        if len(values) != n:
            entries = f"{len(values)} entr{'y' if len(values) == 1 else 'ies'}"
            raise ValueError(f"{name} has {entries} for {n} years")
    ranged = (
        *by_year,
        ("tax_rate", (drivers.tax_rate,)),
        ("sales_to_capital", (drivers.sales_to_capital,)),
    )
    for name, values in ranged:
        low, high = policy.secondary_driver_ranges[name]
        if not all(low <= x <= high for x in values):
            raise ValueError(f"{name} is {_ends(low, high, percent=name != 'sales_to_capital')}")
    if not drivers.terminal_growth <= policy.terminal_growth:
        raise ValueError(_above_g_t(policy.terminal_growth))


def _check_parts(parts: Sequence[Part], policy: Policy) -> None:
    if not parts:
        raise ValueError("at least one part")
    if len(parts) > policy.secondary_parts_max:
        raise ValueError(f"at most {policy.secondary_parts_max} parts")
    shortest, longest = policy.secondary_years_min, policy.secondary_years_max
    g_t = policy.terminal_growth
    for part in parts:
        if not shortest <= len(part.fcff) <= longest:
            raise ValueError(f"a part has {shortest} to {longest} years")
        if part.terminal_growth > g_t:
            raise ValueError(_above_g_t(g_t))


def _check_shares(shares: float) -> None:
    if not shares > 0:
        raise ValueError("a positive diluted share count")


def _above_g_t(g_t: float) -> str:
    return f"the terminal growth is at most g_T, {g_t:.1%}"


def _ends(low: float, high: float, percent: bool) -> str:
    """A driver's range as an override's is written: percents for a rate, the figures for a
    multiple, a negative end with the minus sign."""
    if percent:
        return f"{_signed(low * 100)}% to {_signed(high * 100)}%"
    return f"{_signed(low)} to {_signed(high)}"


def _signed(x: float) -> str:
    return f"{'−' if x < 0 else ''}{abs(x):g}"


def _discounted(part: Part, r: float) -> PartValue:
    pv = tuple(fcff / (1 + r) ** t for t, fcff in enumerate(part.fcff, start=1))
    g = part.terminal_growth
    terminal = part.fcff[-1] * (1 + g) / (r - g)
    terminal_pv = terminal / (1 + r) ** len(part.fcff)
    return PartValue(part.name, pv, terminal, terminal_pv, sum(pv) + terminal_pv)


def _per_share(firm_value: float, bridge: tuple[float, float, float]) -> float:
    """A grid cell's value a share, by the valuation's own bridge."""
    debt, cash, shares = bridge
    equity = firm_value - debt + cash
    return equity / shares


def _growths(g: float, g_t: float) -> tuple[float, float, float]:
    """A grid's three terminal growths: a point below g, g, a point above capped at g_T."""
    return (g - _STEP, g, min(g + _STEP, g_t))


def _drivers_grid(
    drivers: Drivers,
    revenue_0: float,
    roic_t: float,
    r: float,
    g_t: float,
    bridge: tuple[float, float, float],
) -> SecondaryGrid | None:
    rows = _growths(drivers.terminal_growth, g_t)

    def firm_value(row: int, rate: float) -> float:
        at_row = replace(drivers, terminal_growth=rows[row])
        return project(at_row, revenue_0, rate, roic_t).value

    return _grid(rows, max(rows), r, firm_value, bridge)


def _parts_grid(
    parts: Sequence[Part], r: float, g_t: float, bridge: tuple[float, float, float]
) -> SecondaryGrid | None:
    growths = [_growths(part.terminal_growth, g_t) for part in parts]

    def firm_value(row: int, rate: float) -> float:
        at_row = (
            replace(part, terminal_growth=g[row]) for part, g in zip(parts, growths, strict=True)
        )
        return sum(_discounted(part, rate).value for part in at_row)

    highest = max(max(g) for g in growths)
    return _grid((-_STEP, 0.0, _STEP), highest, r, firm_value, bridge)


def _grid(
    rows: tuple[float, float, float],
    highest_growth: float,
    r: float,
    firm_value: Callable[[int, float], float],
    bridge: tuple[float, float, float],
) -> SecondaryGrid | None:
    """The value a share at each row and rate; none when the lowest rate is at or below the
    highest growth in the grid, where a terminal has no value."""
    cols = (r - _STEP, r, r + _STEP)
    if cols[0] <= highest_growth:
        return None
    cells = tuple(
        tuple(_per_share(firm_value(row, rate), bridge) for rate in cols) for row in range(3)
    )
    return SecondaryGrid(rows, cols, cells)
