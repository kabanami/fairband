from datetime import date

from fairband.engine.levels import levels_for, validity_state
from fairband.engine.types import Levels
from fairband.policy import load_policy

policy = load_policy()


def test_levels_wide() -> None:
    lv = levels_for(100.0, "Wide", policy)
    assert lv == Levels(buy=75.0, fair_low=85.0, fair_high=115.0, trim=150.0)


def test_levels_none_moat() -> None:
    assert levels_for(100.0, "None", policy).buy == 55.0


def test_validity_states() -> None:
    f, u = date(2026, 1, 1), date(2026, 4, 1)  # 90 days
    assert validity_state(f, u, date(2026, 2, 1), 2 / 3) == "current"
    assert validity_state(f, u, date(2026, 3, 5), 2 / 3) == "aging"
    assert validity_state(f, u, date(2026, 4, 2), 2 / 3) == "expired"
