"""The secondary valuation (spec 2026-11-06 Tier 2, 11, 20.1 and 20.4; ``method.md`` 15): the
standard form projects the free cash flow to the firm from the agent's drivers, the parts form
discounts an explicit cash-flow path; both at r, with the terminal at g, the equity bridge, the
levels and designation on a value a share above zero, and a three-by-three grid. The worked
numbers are pinned to 1e-4."""

import math
import re
from collections.abc import Sequence
from dataclasses import replace
from typing import Any

import pytest

from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.secondary import (
    SECONDARY_METHOD,
    Drivers,
    Part,
    SecondaryValuation,
    project,
    secondary_value,
)
from fairband.policy import Moat, Policy

PATH = (100.0, 105.0, 110.25, 115.7625, 121.550625)  # 100 growing 5% a year for 5 years
ONE = [Part("the business", PATH, 0.03, None)]
UNIT = Part("a unit", (20.0,) * 5, 0.0, "a flat royalty")
# Spec 20.4: three years growing 10%, 8% and 5% at a 20% margin, tax 25%, sales-to-capital 2,
# a terminal growth of 2%; trailing revenue 1,000, ROIC_T 12%, debt 200, cash 100, 50 shares.
DRIVERS = Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02)
BRIDGE: dict[str, Any] = {"debt": 200.0, "cash": 100.0, "shares": 50.0, "price": 30.0}
RUNS = "a secondary valuation runs 3 to 15 years"
GROWTH = "revenue_growth is −80% to 300%"
MARGIN = "operating_margin is −50% to 60%"
TAX = "tax_rate is 0% to 50%"
SALES = "sales_to_capital is 0.1 to 10"
G_RANGE = "the terminal growth is −100% to g_T, 3.0%"


def _raises(sentence: str) -> Any:
    return pytest.raises(ValueError, match=f"^{re.escape(sentence)}$")


def _flat(years: int, g: float = 0.0) -> list[Part]:
    return [Part("p", (10.0,) * years, g, None)]


def at_r(policy: Policy, r: float) -> Policy:
    """The policy with its required return replaced."""
    return replace(policy, required_return=r)


def _parts(
    parts: Sequence[Part],
    debt: float,
    cash: float,
    shares: float,
    price: float | None,
    moat: Moat,
    policy: Policy,
) -> SecondaryValuation:
    """The parts form, its arguments in plan 1's order."""
    return secondary_value(
        parts=parts, debt=debt, cash=cash, shares=shares, price=price, moat=moat, policy=policy
    )


def _drivers(drivers: Drivers, policy: Policy, **bridge: Any) -> SecondaryValuation:
    """The standard form on spec 20.4's trailing revenue, ROIC_T, bridge and a Narrow moat."""
    return secondary_value(
        drivers=drivers,
        revenue_0=1000.0,
        roic_t=0.12,
        **(BRIDGE | {"moat": "Narrow"} | bridge),
        policy=policy,
    )


def test_a_secondary_valuation_reads_well_below_from_its_class_s_buy_level(policy: Policy) -> None:
    """Spec 2026-11-23 thresholds, 5.2: a secondary valuation's word reads the edges of its moat
    class, as a route's does: at 0.78 × its value a share, Well below on a Wide moat, whose buy
    level is 0.80 ×, and Below on a Narrow one."""
    for moat, word in (("Wide", "well-below"), ("Narrow", "below")):
        value = _parts(ONE, 200.0, 100.0, 100.0, None, moat, policy).value_per_share  # type: ignore[arg-type]
        made = _parts(ONE, 200.0, 100.0, 100.0, 0.78 * value, moat, policy)  # type: ignore[arg-type]
        assert made.designation == word


def test_one_part(policy: Policy) -> None:
    v = _parts(ONE, 200.0, 100.0, 100.0, 15.0, "None", policy)
    [part] = v.parts
    assert part.name == "the business"
    assert part.pv == pytest.approx((91.7431, 88.3764, 85.1332, 82.0091, 78.9996), abs=1e-4)
    assert sum(part.pv) == pytest.approx(426.2614, abs=1e-4)
    assert part.terminal == pytest.approx(2086.6191, abs=1e-4)
    assert part.terminal_pv == pytest.approx(1356.1592, abs=1e-4)
    assert part.value == pytest.approx(1782.4206, abs=1e-4)
    assert (v.firm_value, v.equity, v.value_per_share) == pytest.approx(
        (1782.4206, 1682.4206, 16.8242), abs=1e-4
    )
    assert (v.debt, v.cash, v.shares) == (200.0, 100.0, 100.0)
    assert v.levels == levels_for(v.value_per_share, "None", policy)
    assert (v.price_to_value, v.designation) == designation_for(
        15.0, v.value_per_share, policy.edges_for("None")
    )
    assert v.designation == "below"  # 15 ÷ 16.8242 = 0.8916, under the band's low of 0.90
    assert SECONDARY_METHOD == "fairband-secondary/2"


def test_two_parts(policy: Policy) -> None:
    v = _parts([*ONE, UNIT], 200.0, 100.0, 100.0, 15.0, "None", policy)
    unit = v.parts[1]
    assert sum(unit.pv) == pytest.approx(77.7930, abs=1e-4)
    assert unit.terminal == pytest.approx(222.2222, abs=1e-4)
    assert unit.terminal_pv == pytest.approx(144.4292, abs=1e-4)
    assert unit.value == pytest.approx(222.2222, abs=1e-4)
    assert v.firm_value == pytest.approx(v.parts[0].value + unit.value)
    assert v.value_per_share == pytest.approx(19.0464, abs=1e-4)


def test_the_terminal_growth_is_capped_at_g_t(policy: Policy) -> None:
    with _raises(G_RANGE):
        _parts(_flat(5, 0.035), 200.0, 100.0, 100.0, 15.0, "None", policy)
    at_g_t = _parts(_flat(5, 0.03), 0.0, 0.0, 1.0, None, "None", policy)
    assert at_g_t.parts[0].terminal == pytest.approx(10.0 * 1.03 / 0.06)
    shrinking = _parts(_flat(5, -0.02), 0.0, 0.0, 1.0, None, "None", policy)
    assert shrinking.parts[0].terminal == pytest.approx(10.0 * 0.98 / 0.11)


def test_a_part_has_three_to_fifteen_years(policy: Policy) -> None:
    for years in (2, 16):
        with _raises("a part has 3 to 15 years"):
            _parts(_flat(years), 0.0, 0.0, 1.0, None, "None", policy)
    for years in (3, 15):
        v = _parts(_flat(years), 0.0, 0.0, 1.0, None, "None", policy)
        assert len(v.parts[0].pv) == years


def test_at_most_ten_parts(policy: Policy) -> None:
    ten = [Part(f"unit {n}", (20.0,) * 5, 0.0, None) for n in range(10)]
    assert len(_parts(ten, 0.0, 0.0, 1.0, None, "None", policy).parts) == 10
    with _raises("at most 10 parts"):
        _parts([*ten, UNIT], 0.0, 0.0, 1.0, None, "None", policy)
    with _raises("at least one part"):
        _parts([], 0.0, 0.0, 1.0, None, "None", policy)


def test_a_positive_diluted_share_count(policy: Policy) -> None:
    for shares in (0.0, -100.0):
        with _raises("a positive diluted share count"):
            _parts(ONE, 200.0, 100.0, shares, 15.0, "None", policy)
        with _raises("a positive diluted share count"):
            _drivers(DRIVERS, policy, shares=shares)


def test_a_negative_equity_is_stored_with_no_levels(policy: Policy) -> None:
    loss = [Part("a loss", (-50.0,) * 3, 0.0, None)]
    v = _parts(loss, 1000.0, 0.0, 100.0, 15.0, "None", policy)
    assert v.value_per_share < 0 and v.equity == pytest.approx(v.firm_value - 1000.0)
    assert v.value_per_share == pytest.approx(v.equity / 100.0)
    assert (v.levels, v.price_to_value, v.designation) == (None, None, None)


def test_no_price_gives_levels_and_no_designation(policy: Policy) -> None:
    v = _parts(ONE, 200.0, 100.0, 100.0, None, "None", policy)
    assert v.levels is not None and (v.price_to_value, v.designation) == (None, None)


def test_levels_follow_the_moat(policy: Policy) -> None:
    v = _parts(ONE, 200.0, 100.0, 100.0, 15.0, "Wide", policy)
    assert v.levels is not None
    assert v.levels.buy == pytest.approx(v.value_per_share * (1 - policy.margin_of_safety["Wide"]))
    assert v.levels == levels_for(v.value_per_share, "Wide", policy)
    narrow = _parts(ONE, 200.0, 100.0, 100.0, 15.0, "Narrow", policy).levels
    assert narrow is not None and narrow.buy < v.levels.buy


def test_the_drivers_worked_numbers(policy: Policy) -> None:  # spec 20.4
    p = project(DRIVERS, 1000.0, 0.09, 0.12)
    assert [y.t for y in p.years] == [1, 2, 3]
    assert [y.revenue for y in p.years] == pytest.approx([1100.0, 1188.0, 1247.4])
    assert [y.ebit for y in p.years] == pytest.approx([220.0, 237.6, 249.48])
    assert [y.nopat for y in p.years] == pytest.approx([165.0, 178.2, 187.11])
    assert [y.reinvestment for y in p.years] == pytest.approx([50.0, 44.0, 29.7])
    assert [y.fcff for y in p.years] == pytest.approx([115.0, 134.2, 157.41])
    assert [y.pv for y in p.years] == pytest.approx([105.504587, 112.953455, 121.549402], abs=1e-4)
    assert sum(y.pv for y in p.years) == pytest.approx(340.007444, abs=1e-4)
    assert p.terminal_fcff == pytest.approx(159.0435, abs=1e-4)
    assert p.terminal == pytest.approx(2272.05, abs=1e-4)
    assert p.terminal_pv == pytest.approx(1754.439476, abs=1e-4)
    assert p.value == pytest.approx(2094.44692, abs=1e-4)
    v = secondary_value(
        drivers=DRIVERS,
        revenue_0=1000.0,
        roic_t=0.12,
        debt=200.0,
        cash=100.0,
        shares=50.0,
        price=30.0,
        moat="Narrow",
        policy=at_r(policy, 0.09),
    )
    assert v.form == "drivers"
    assert (v.drivers, v.projection, v.parts) == (DRIVERS, p, ())
    assert v.firm_value == pytest.approx(2094.44692, abs=1e-4)
    assert v.equity == pytest.approx(1994.44692, abs=1e-4)
    assert v.value_per_share == pytest.approx(39.888938, abs=1e-4)
    assert v.levels == levels_for(v.value_per_share, "Narrow", policy)
    assert (v.price_to_value, v.designation) == designation_for(
        30.0, v.value_per_share, policy.edges_for("Narrow")
    )
    assert v.grid is not None
    assert v.grid.cells[1][1] == v.value_per_share  # the same arithmetic, bit for bit
    assert v.grid.rows == pytest.approx((0.01, 0.02, 0.03))
    assert v.grid.cols == pytest.approx((0.08, 0.09, 0.10))
    assert v.grid.cells[0][0] == pytest.approx(44.220636, abs=1e-4)  # r 8%, g 1%


def test_the_grid_is_the_value_at_each_pair(policy: Policy) -> None:
    v = _drivers(DRIVERS, policy)
    assert v.grid is not None and [len(row) for row in v.grid.cells] == [3, 3, 3]
    for i, g in enumerate(v.grid.rows):
        for j, r in enumerate(v.grid.cols):
            at_pair = _drivers(replace(DRIVERS, terminal_growth=g), at_r(policy, r))
            assert v.grid.cells[i][j] == pytest.approx(at_pair.value_per_share, abs=1e-12)
    # ROIC_T is held at 12%, above every rate: the value rises with g and falls with r
    for row in v.grid.cells:
        assert row[0] > row[1] > row[2]
    for column in zip(*v.grid.cells, strict=True):
        assert column[0] < column[1] < column[2]


def test_a_falling_year_reinvests_nothing(policy: Policy) -> None:
    drivers = Drivers(3, (0.10, 0.08, -0.05), (0.20,) * 3, 0.25, 2.0, 0.02)
    falling = project(drivers, 1000.0, 0.09, 0.12).years[2]
    assert falling.revenue == pytest.approx(1128.6)
    assert falling.reinvestment == 0.0
    assert falling.fcff == falling.nopat == pytest.approx(1128.6 * 0.20 * 0.75)


def test_a_shrinking_terminal_releases_no_capital(policy: Policy) -> None:
    shrinking = project(replace(DRIVERS, terminal_growth=-0.05), 1000.0, 0.09, 0.12)
    nopat_n = shrinking.years[-1].nopat
    assert shrinking.terminal_fcff == pytest.approx(nopat_n * 0.95)  # 187.11 × 0.95, no release
    assert shrinking.terminal == pytest.approx(187.11 * 0.95 / 0.14)


def test_the_terminal_growth_runs_from_minus_100_percent_to_g_t(policy: Policy) -> None:
    for g in (-math.inf, math.nan, -1.01):
        with _raises(G_RANGE):
            _drivers(replace(DRIVERS, terminal_growth=g), policy)
        with _raises(G_RANGE):
            _parts(_flat(5, g), 0.0, 0.0, 1.0, None, "None", policy)
    floor = _drivers(replace(DRIVERS, terminal_growth=-1.0), policy).projection
    assert floor is not None and floor.terminal == 0.0  # the business is gone at the terminal
    assert _parts(_flat(5, -1.0), 0.0, 0.0, 1.0, None, "None", policy).parts[0].terminal == 0.0


def test_the_grid_caps_the_terminal_growth_at_g_t(policy: Policy) -> None:
    v = _drivers(replace(DRIVERS, terminal_growth=0.03), policy)
    assert v.grid is not None
    assert v.grid.rows == pytest.approx((0.02, 0.03, 0.03))
    assert v.grid.cells[2] == v.grid.cells[1]


def test_no_grid_where_its_lowest_rate_meets_its_highest_growth(policy: Policy) -> None:
    # r 5% and g_T 4%, both inside the settings' ranges: r − 1 pp is g_T, so the grid's corner
    # at g = g_T has no terminal; the value at r stands
    tight = replace(policy, required_return=0.05, terminal_growth=0.04)
    at_g_t = _drivers(replace(DRIVERS, terminal_growth=0.04), tight)
    assert at_g_t.grid is None and at_g_t.value_per_share > 0
    below = _drivers(replace(DRIVERS, terminal_growth=0.02), tight)
    assert below.grid is not None and below.grid.cols == pytest.approx((0.04, 0.05, 0.06))
    flat = [Part("p", (10.0,) * 5, 0.04, None)]
    assert _parts(flat, 0.0, 0.0, 1.0, None, "None", tight).grid is None


def test_one_form_only(policy: Policy) -> None:
    with _raises("a secondary valuation takes drivers or parts, not both"):
        secondary_value(
            parts=ONE,
            drivers=DRIVERS,
            revenue_0=1000.0,
            roic_t=0.12,
            **BRIDGE,
            moat="None",
            policy=policy,
        )
    with _raises("a secondary valuation needs drivers or parts"):
        secondary_value(**BRIDGE, moat="None", policy=policy)


def test_the_drivers_form_takes_the_trailing_revenue_and_the_terminal_return(
    policy: Policy,
) -> None:
    with pytest.raises(TypeError):
        secondary_value(drivers=DRIVERS, roic_t=0.12, **BRIDGE, moat="None", policy=policy)
    with pytest.raises(TypeError):
        secondary_value(drivers=DRIVERS, revenue_0=1000.0, **BRIDGE, moat="None", policy=policy)


@pytest.mark.parametrize(
    ("drivers", "sentence"),
    [
        (Drivers(2, (0.1,) * 2, (0.2,) * 2, 0.25, 2.0, 0.02), RUNS),
        (Drivers(16, (0.1,) * 16, (0.2,) * 16, 0.25, 2.0, 0.02), RUNS),
        (replace(DRIVERS, revenue_growth=(0.1, 0.1, -0.81)), GROWTH),
        (replace(DRIVERS, revenue_growth=(3.01, 0.1, 0.1)), GROWTH),
        (replace(DRIVERS, operating_margin=(0.2, -0.51, 0.2)), MARGIN),
        (replace(DRIVERS, operating_margin=(0.2, 0.2, 0.61)), MARGIN),
        (replace(DRIVERS, tax_rate=-0.01), TAX),
        (replace(DRIVERS, tax_rate=0.51), TAX),
        (replace(DRIVERS, tax_rate=float("nan")), TAX),
        (replace(DRIVERS, sales_to_capital=0.09), SALES),
        (replace(DRIVERS, sales_to_capital=10.5), SALES),
        (replace(DRIVERS, terminal_growth=0.035), G_RANGE),
    ],
)
def test_each_driver_range_refuses_by_name(policy: Policy, drivers: Drivers, sentence: str) -> None:
    with _raises(sentence):
        _drivers(drivers, policy)


def test_the_driver_ranges_include_their_ends(policy: Policy) -> None:
    for drivers in (
        Drivers(3, (-0.80, 3.00, 0.0), (-0.50, 0.60, 0.0), 0.0, 0.1, -0.05),
        Drivers(15, (0.05,) * 15, (0.20,) * 15, 0.50, 10.0, 0.03),
    ):
        projection = _drivers(drivers, policy).projection
        assert projection is not None and len(projection.years) == drivers.years


def test_a_list_of_the_wrong_length_is_refused(policy: Policy) -> None:
    with _raises("revenue_growth has 2 entries for 3 years"):
        _drivers(replace(DRIVERS, revenue_growth=(0.1, 0.1)), policy)
    with _raises("revenue_growth has 1 entry for 3 years"):
        _drivers(replace(DRIVERS, revenue_growth=(0.1,)), policy)
    with _raises("operating_margin has 4 entries for 3 years"):
        _drivers(replace(DRIVERS, operating_margin=(0.2,) * 4), policy)


def test_the_drivers_refusals_run_in_order(policy: Policy) -> None:
    short = replace(DRIVERS, revenue_growth=(0.1, 0.1))
    with _raises(RUNS):  # the years before the lists
        _drivers(replace(short, years=2, operating_margin=(0.2,)), policy)
    with _raises("revenue_growth has 2 entries for 3 years"):  # the lists before the ranges
        _drivers(replace(short, tax_rate=0.9), policy)
    with _raises(GROWTH):  # the growth before the margin
        _drivers(replace(DRIVERS, revenue_growth=(5.0,) * 3, operating_margin=(0.9,) * 3), policy)
    with _raises(TAX):  # the ranges before the terminal growth
        _drivers(replace(DRIVERS, tax_rate=0.9, terminal_growth=0.05), policy)
    with _raises(G_RANGE):  # the terminal growth before the shares
        _drivers(replace(DRIVERS, terminal_growth=0.05), policy, shares=0.0)


def test_the_parts_form_is_unchanged(policy: Policy) -> None:
    v = secondary_value(
        parts=ONE, debt=200.0, cash=100.0, shares=100.0, price=15.0, moat="None", policy=policy
    )
    assert v.form == "parts" and (v.drivers, v.projection) == (None, None)
    assert v.parts[0].pv == pytest.approx((91.7431, 88.3764, 85.1332, 82.0091, 78.9996), abs=1e-4)
    assert v.parts[0].terminal_pv == pytest.approx(1356.1592, abs=1e-4)
    assert v.value_per_share == pytest.approx(16.8242, abs=1e-4)
    assert v.grid is not None
    assert v.grid.cells[1][1] == v.value_per_share
    assert v.grid.cols == pytest.approx((0.08, 0.09, 0.10))


def test_the_parts_grid_s_top_row_is_the_shift_applied(policy: Policy) -> None:
    """A part at g_T rises nothing, so the top row of a grid of it alone is no shift; a part half a
    point under g_T rises half a point; beside a part a point under g_T, a point."""
    at_g_t = _parts(ONE, 200.0, 100.0, 100.0, 15.0, "None", policy).grid
    assert at_g_t is not None and at_g_t.rows == (-0.01, 0.0, 0.0)
    assert at_g_t.cells[2] == at_g_t.cells[1]
    near = [replace(ONE[0], terminal_growth=0.025)]
    half = _parts(near, 200.0, 100.0, 100.0, 15.0, "None", policy).grid
    assert half is not None and half.rows == pytest.approx((-0.01, 0.0, 0.005), abs=1e-12)
    beside = _parts([*near, UNIT], 200.0, 100.0, 100.0, 15.0, "None", policy).grid
    assert beside is not None and beside.rows == (-0.01, 0.0, 0.01)


def test_the_parts_grid_moves_every_part_together(policy: Policy) -> None:
    # ONE is at g_T, UNIT at 0: the third row lifts UNIT by a point and holds ONE at g_T
    v = _parts([*ONE, UNIT], 200.0, 100.0, 100.0, 15.0, "None", policy)
    assert v.grid is not None and v.grid.rows == pytest.approx((-0.01, 0.0, 0.01))
    shifted = (
        [replace(ONE[0], terminal_growth=0.02), replace(UNIT, terminal_growth=-0.01)],
        [*ONE, UNIT],
        [ONE[0], replace(UNIT, terminal_growth=0.01)],
    )
    for i, parts in enumerate(shifted):
        for j, r in enumerate(v.grid.cols):
            at_pair = _parts(parts, 200.0, 100.0, 100.0, 15.0, "None", at_r(policy, r))
            assert v.grid.cells[i][j] == pytest.approx(at_pair.value_per_share, abs=1e-12)
