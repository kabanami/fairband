from datetime import date
from typing import get_args

import pytest

from fairband.engine.levels import levels_for, standing_for, validity_state
from fairband.engine.types import Levels
from fairband.policy import Moat, load_policy

policy = load_policy()


def test_levels_wide() -> None:
    lv = levels_for(100.0, "Wide", policy)
    assert lv == Levels(buy=80.0, fair_low=90.0, fair_high=110.0, trim=135.0)


def test_levels_none_moat() -> None:
    assert levels_for(100.0, "None", policy).buy == 60.0


def test_standing_for_gives_the_rows_own_levels_and_word() -> None:
    """Spec 2026-11-23 thresholds, 5.2, 5.3 and 7: one function gives a record's levels, price ÷
    value and word from its value, its moat class, a price and the policy. GOOG's reviewed row,
    $339.38 on a Wide moat at $264.00, is under its buy level of $271.50 and reads Well below; at
    0.78 × the value a Wide row reads Well below and a Narrow row Below; a None row reads Below at
    0.65 and Well below at 0.59; every class reads Well above from 1.35."""
    goog = standing_for(339.38, "Wide", 264.00, policy)
    assert goog.levels == levels_for(339.38, "Wide", policy)
    assert goog.levels.buy == pytest.approx(271.50, abs=0.005)
    assert goog.levels.trim == pytest.approx(458.16, abs=0.005)
    assert (goog.price_to_value, goog.designation) == (264.00 / 339.38, "well-below")
    assert standing_for(100.0, "Wide", 78.0, policy).designation == "well-below"
    assert standing_for(100.0, "Narrow", 78.0, policy).designation == "below"
    assert standing_for(100.0, "None", 65.0, policy).designation == "below"
    assert standing_for(100.0, "None", 59.0, policy).designation == "well-below"
    for moat in get_args(Moat):
        assert standing_for(100.0, moat, 135.0, policy).designation == "well-above"
        assert standing_for(100.0, moat, 134.0, policy).designation == "above"


@pytest.mark.parametrize("price", [None, 0.0, -1.0])
def test_standing_for_without_a_price_gives_the_levels_alone(price: float | None) -> None:
    s = standing_for(100.0, "Wide", price, policy)
    assert s.levels.buy == 80.0 and (s.price_to_value, s.designation) == (None, None)


def test_validity_states() -> None:
    f, u = date(2026, 1, 1), date(2026, 4, 1)  # 90 days
    assert validity_state(f, u, date(2026, 2, 1), 2 / 3) == "current"
    assert validity_state(f, u, date(2026, 3, 5), 2 / 3) == "aging"
    assert validity_state(f, u, date(2026, 4, 2), 2 / 3) == "expired"
