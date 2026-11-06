"""The secondary valuation (spec 2026-11-06 Tier 2, 11 and 20.1; ``method.md`` 15): an explicit
cash-flow path discounted at r, the terminal at the part's growth, the equity bridge, and the
levels and designation on a value a share above zero. The worked numbers are pinned to 1e-4."""

import re
from typing import Any

import pytest

from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.secondary import SECONDARY_METHOD, Part, secondary_value
from fairband.policy import Policy

PATH = (100.0, 105.0, 110.25, 115.7625, 121.550625)  # 100 growing 5% a year for 5 years
ONE = [Part("the business", PATH, 0.03, None)]
UNIT = Part("a unit", (20.0,) * 5, 0.0, "a flat royalty")


def _raises(sentence: str) -> Any:
    return pytest.raises(ValueError, match=f"^{re.escape(sentence)}$")


def _flat(years: int, g: float = 0.0) -> list[Part]:
    return [Part("p", (10.0,) * years, g, None)]


def test_one_part(policy: Policy) -> None:
    v = secondary_value(ONE, 200.0, 100.0, 100.0, 15.0, "None", policy)
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
        15.0, v.value_per_share, policy.designation_edges
    )
    assert v.designation == "near"  # 15 ÷ 16.8242 = 0.8916
    assert SECONDARY_METHOD == "fairband-secondary/1"


def test_two_parts(policy: Policy) -> None:
    v = secondary_value([*ONE, UNIT], 200.0, 100.0, 100.0, 15.0, "None", policy)
    unit = v.parts[1]
    assert sum(unit.pv) == pytest.approx(77.7930, abs=1e-4)
    assert unit.terminal == pytest.approx(222.2222, abs=1e-4)
    assert unit.terminal_pv == pytest.approx(144.4292, abs=1e-4)
    assert unit.value == pytest.approx(222.2222, abs=1e-4)
    assert v.firm_value == pytest.approx(v.parts[0].value + unit.value)
    assert v.value_per_share == pytest.approx(19.0464, abs=1e-4)


def test_the_terminal_growth_is_capped_at_g_t(policy: Policy) -> None:
    with _raises("the terminal growth is at most g_T, 3.0%"):
        secondary_value(_flat(5, 0.035), 200.0, 100.0, 100.0, 15.0, "None", policy)
    at_g_t = secondary_value(_flat(5, 0.03), 0.0, 0.0, 1.0, None, "None", policy)
    assert at_g_t.parts[0].terminal == pytest.approx(10.0 * 1.03 / 0.06)
    shrinking = secondary_value(_flat(5, -0.02), 0.0, 0.0, 1.0, None, "None", policy)
    assert shrinking.parts[0].terminal == pytest.approx(10.0 * 0.98 / 0.11)


def test_a_part_has_three_to_fifteen_years(policy: Policy) -> None:
    for years in (2, 16):
        with _raises("a part has 3 to 15 years"):
            secondary_value(_flat(years), 0.0, 0.0, 1.0, None, "None", policy)
    for years in (3, 15):
        v = secondary_value(_flat(years), 0.0, 0.0, 1.0, None, "None", policy)
        assert len(v.parts[0].pv) == years


def test_at_most_ten_parts(policy: Policy) -> None:
    ten = [Part(f"unit {n}", (20.0,) * 5, 0.0, None) for n in range(10)]
    assert len(secondary_value(ten, 0.0, 0.0, 1.0, None, "None", policy).parts) == 10
    with _raises("at most 10 parts"):
        secondary_value([*ten, UNIT], 0.0, 0.0, 1.0, None, "None", policy)
    with _raises("at least one part"):
        secondary_value([], 0.0, 0.0, 1.0, None, "None", policy)


def test_a_positive_diluted_share_count(policy: Policy) -> None:
    for shares in (0.0, -100.0):
        with _raises("a positive diluted share count"):
            secondary_value(ONE, 200.0, 100.0, shares, 15.0, "None", policy)


def test_a_negative_equity_is_stored_with_no_levels(policy: Policy) -> None:
    loss = [Part("a loss", (-50.0,) * 3, 0.0, None)]
    v = secondary_value(loss, 1000.0, 0.0, 100.0, 15.0, "None", policy)
    assert v.value_per_share < 0 and v.equity == pytest.approx(v.firm_value - 1000.0)
    assert v.value_per_share == pytest.approx(v.equity / 100.0)
    assert (v.levels, v.price_to_value, v.designation) == (None, None, None)


def test_no_price_gives_levels_and_no_designation(policy: Policy) -> None:
    v = secondary_value(ONE, 200.0, 100.0, 100.0, None, "None", policy)
    assert v.levels is not None and (v.price_to_value, v.designation) == (None, None)


def test_levels_follow_the_moat(policy: Policy) -> None:
    v = secondary_value(ONE, 200.0, 100.0, 100.0, 15.0, "Wide", policy)
    assert v.levels is not None
    assert v.levels.buy == pytest.approx(v.value_per_share * (1 - policy.margin_of_safety["Wide"]))
    assert v.levels == levels_for(v.value_per_share, "Wide", policy)
    narrow = secondary_value(ONE, 200.0, 100.0, 100.0, 15.0, "Narrow", policy).levels
    assert narrow is not None and narrow.buy < v.levels.buy
