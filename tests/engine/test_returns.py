import math

import pytest

from fairband.engine.returns import expected_return


def test_expected_return_design_example() -> None:
    # Method v1.7, the worked example's Step 9: growth 14.8%, repricing 11.2%, total about 25.3%.
    er = expected_return(338.46, 473.0, 0.0025, -0.01, (0.199, 0.169), 0.08)
    assert er.income == pytest.approx(-0.0075)
    assert er.growth == pytest.approx(0.148, abs=0.002)
    assert er.repricing == pytest.approx(0.112, abs=0.002)
    assert er.total == pytest.approx(0.253, abs=0.002)
    assert er.total == pytest.approx(er.income + er.growth + er.repricing)


def test_missing_steps_take_the_belief() -> None:
    er = expected_return(100.0, 100.0, 0.0, 0.0, (None, None), 0.05)
    assert (er.income, er.repricing) == (0.0, 0.0)
    assert er.growth == pytest.approx(0.05) and er.total == pytest.approx(0.05)
    er = expected_return(100.0, 100.0, 0.0, 0.0, (0.20, None), 0.05)
    assert er.growth == pytest.approx((1.20 * 1.05 * 1.05) ** (1 / 3) - 1)


def test_repricing_over_the_horizon() -> None:
    er = expected_return(100.0, 80.0, 0.02, 0.01, (0.05, 0.05), 0.05, horizon=5)
    assert er.repricing == pytest.approx(math.log(0.8) / 5)
    assert er.income == pytest.approx(0.03)
    # The growth term covers the same five years: steps 2 and 3, then the belief.
    assert er.growth == pytest.approx(0.05)


def test_growth_through_a_loss_is_refused() -> None:
    # A step below -100% takes earnings negative; the geometric mean has no real value.
    with pytest.raises(ValueError, match="growth"):
        expected_return(100.0, 120.0, 0.0, 0.0, (-1.5, 0.10), 0.05)


@pytest.mark.parametrize(("price", "value"), [(0.0, 100.0), (100.0, 0.0), (100.0, -5.0)])
def test_needs_a_positive_price_and_value(price: float, value: float) -> None:
    with pytest.raises(ValueError, match="positive"):
        expected_return(price, value, 0.0, 0.0, (0.05, 0.05), 0.05)
