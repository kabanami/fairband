from datetime import date

import pytest

from fairband.engine.levels import levels_for, stance3, stance5, validity_state
from fairband.engine.types import Levels
from fairband.policy import load_policy

policy = load_policy()


def test_levels_wide() -> None:
    lv = levels_for(100.0, "Wide", policy)
    assert lv == Levels(buy=75.0, fair_low=85.0, fair_high=115.0, trim=150.0)


def test_levels_none_moat() -> None:
    assert levels_for(100.0, "None", policy).buy == 55.0


@pytest.mark.parametrize(
    "price,s5,s3",
    [
        (74.99, "BUY", "buy"),
        (75.0, "ACCUMULATE / HOLD", "hold"),
        (84.99, "ACCUMULATE / HOLD", "hold"),
        (85.0, "HOLD", "hold"),
        (115.0, "HOLD", "hold"),
        (115.01, "HOLD — above fair band", "hold"),
        (149.99, "HOLD — above fair band", "hold"),
        (150.0, "TRIM", "trim"),
    ],
)
def test_stances(price: float, s5: str, s3: str) -> None:
    lv = levels_for(100.0, "Wide", policy)
    assert stance5(price, lv) == s5 and stance3(price, lv) == s3


def test_validity_states() -> None:
    f, u = date(2026, 1, 1), date(2026, 4, 1)  # 90 days
    assert validity_state(f, u, date(2026, 2, 1), 2 / 3) == "current"
    assert validity_state(f, u, date(2026, 3, 5), 2 / 3) == "aging"
    assert validity_state(f, u, date(2026, 4, 2), 2 / 3) == "expired"
