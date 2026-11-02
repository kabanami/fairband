import pytest
from support.stable_value import stable_dcf

from fairband.engine.mature_growth import Charge
from fairband.engine.mature_stable import mature_stable_values, normalize_for_margin


def _charge(runway_roic: float, terminal_roic: float, off: bool = False) -> Charge:
    return Charge(runway_roic, terminal_roic, 0.09, 0.03, off)


def test_equal_to_epv_when_every_return_is_r() -> None:
    epv_v, sg = mature_stable_values(9.0, _charge(0.09, 0.09), 20)
    assert epv_v == pytest.approx(100.0) and sg == pytest.approx(100.0)


def test_one_stage_value_when_the_runway_return_is_the_terminal() -> None:
    # the perpetuity E × (1 − g ÷ ROIC) ÷ (r − g): at most 15% above EPV under the 13% cap
    epv_v, sg = mature_stable_values(9.0, _charge(0.13, 0.13), 20)
    assert sg == pytest.approx(9.0 * (1 - 0.03 / 0.13) / 0.06)
    assert sg / epv_v == pytest.approx(1.1538, abs=1e-3)


def test_own_return_through_the_runway_then_the_terminal() -> None:
    # charged at 44% for 19 years and at 13% in year 20 and the terminal: between the one-stage
    # values at 13% ($115.38) and at 44% ($139.77)
    _, sg = mature_stable_values(9.0, _charge(0.44, 0.13), 20)
    assert sg == pytest.approx(stable_dcf(9.0, 0.44, 0.13, 20))
    assert sg == pytest.approx(131.455, abs=1e-3)
    assert 9.0 * (1 - 0.03 / 0.13) / 0.06 < sg < 9.0 * (1 - 0.03 / 0.44) / 0.06


def test_a_longer_runway_at_a_return_above_the_terminal_is_worth_more() -> None:
    values = [mature_stable_values(9.0, _charge(0.44, 0.13), n)[1] for n in (5, 10, 20)]
    assert values == sorted(values) and len(set(values)) == 3


def test_charge_off_pays_all_earnings_before_the_terminal() -> None:
    _, sg = mature_stable_values(9.0, _charge(0.09, 0.09, off=True), 5)
    assert sg == pytest.approx(stable_dcf(9.0, 0.09, 0.09, 5, off=True))
    assert sg == pytest.approx(110.133, abs=1e-3)  # above EPV: four years pay out in full


def test_margin_scaling_only_when_flagged() -> None:
    assert normalize_for_margin(100.0, 0.30, 0.20, True) == pytest.approx(66.667, abs=1e-2)
    assert normalize_for_margin(100.0, 0.30, 0.20, False) == 100.0


@pytest.mark.parametrize(("ttm", "median"), [(0.0, 0.20), (-0.05, 0.20), (0.30, 0.0), (0.30, -0.1)])
def test_margin_scaling_needs_both_margins_positive(ttm: float, median: float) -> None:
    assert normalize_for_margin(100.0, ttm, median, True) == 100.0
