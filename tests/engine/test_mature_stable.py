import pytest

from fairband.engine.mature_stable import mature_stable_values, normalize_for_margin


def test_equal_when_terminal_roic_is_r() -> None:
    epv_v, sg = mature_stable_values(9.0, 0.09, 0.09, 0.03)
    assert epv_v == pytest.approx(100.0) and sg == pytest.approx(100.0)


def test_wide_cap_at_most_15pct_above_epv() -> None:
    epv_v, sg = mature_stable_values(9.0, 0.13, 0.09, 0.03)
    assert sg / epv_v == pytest.approx(1.1538, abs=1e-3)


def test_margin_scaling_only_when_flagged() -> None:
    assert normalize_for_margin(100.0, 0.30, 0.20, True) == pytest.approx(66.667, abs=1e-2)
    assert normalize_for_margin(100.0, 0.30, 0.20, False) == 100.0


@pytest.mark.parametrize(("ttm", "median"), [(0.0, 0.20), (-0.05, 0.20), (0.30, 0.0), (0.30, -0.1)])
def test_margin_scaling_needs_both_margins_positive(ttm: float, median: float) -> None:
    assert normalize_for_margin(100.0, ttm, median, True) == 100.0
