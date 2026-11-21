from collections.abc import Callable
from dataclasses import replace

import pytest
from support.stable_value import stable_dcf

from fairband.engine.classifier import Deciles
from fairband.engine.mature_growth import Charge
from fairband.engine.mature_stable import mature_stable_values, normalize_for_margin
from fairband.engine.overrides import current_reading
from fairband.engine.route import value_company
from fairband.engine.route_mature_stable import value_mature_stable
from fairband.engine.route_steps import Context, Valued
from fairband.policy import Policy

WithOverrides = Callable[..., Context]  # the fixture of conftest.py
R, GT = 0.09, 0.03  # the required return and the terminal growth


def _charge(runway_roic: float, terminal_roic: float, off: bool = False) -> Charge:
    """The charge as the route passes it: a hold of 0, the return fading from year 1 (spec
    2026-11-09 6.3)."""
    return Charge(runway_roic, terminal_roic, R, GT, off, hold=0)


def test_equal_to_epv_when_every_return_is_r() -> None:
    epv_v, sg = mature_stable_values(9.0, _charge(0.09, 0.09), 20)
    assert epv_v == pytest.approx(100.0) and sg == pytest.approx(100.0)


def test_one_stage_value_when_the_runway_return_is_the_terminal() -> None:
    # the perpetuity E × (1 − g ÷ ROIC) ÷ (r − g): at most 15% above EPV under the 13% cap
    epv_v, sg = mature_stable_values(9.0, _charge(0.13, 0.13), 20)
    assert sg == pytest.approx(9.0 * (1 - 0.03 / 0.13) / 0.06)
    assert sg / epv_v == pytest.approx(1.1538, abs=1e-3)


def test_own_return_through_the_runway_then_the_terminal() -> None:
    # the return fades from 44% toward 13% from year 1, 42.45% in year 1 and 13% in year 20 and
    # the terminal: between the one-stage values at 13% ($115.38) and at 44% ($139.77), below
    # the $131.46 of 19 years held at 44% (method 0.9)
    _, sg = mature_stable_values(9.0, _charge(0.44, 0.13), 20)
    assert sg == pytest.approx(stable_dcf(9.0, 0.44, 0.13, 20))
    assert sg == pytest.approx(127.771, abs=1e-3)
    assert 9.0 * (1 - 0.03 / 0.13) / 0.06 < sg < 9.0 * (1 - 0.03 / 0.44) / 0.06


def test_a_longer_runway_at_a_return_above_the_terminal_is_worth_more() -> None:
    # the fade from year 1 is slower on a longer runway, so more years charge above the terminal
    values = [mature_stable_values(9.0, _charge(0.44, 0.13), n)[1] for n in (5, 10, 20)]
    assert values == pytest.approx([119.044, 122.616, 127.771], abs=1e-3)
    assert values == sorted(values) and len(set(values)) == 3


def test_a_stable_row_s_value_is_the_spec_s_13_3_figure() -> None:
    """Spec 2026-11-09 13.3: E 100 growing at g_T over a runway of 10, the return fading from 20%
    in a straight line from year 1 (19.3%, 18.6%, ... 13%); 1,335.796 as built (the runway
    return held to year 9)."""
    epv_v, sg = mature_stable_values(100.0, Charge(0.20, 0.13, R, GT, hold=0), 10)
    assert sg == pytest.approx(1315.0993, abs=1e-3)
    assert epv_v == pytest.approx(1111.11, abs=1e-2)
    as_built = mature_stable_values(100.0, Charge(0.20, 0.13, R, GT), 10)[1]
    assert as_built == pytest.approx(1335.796, abs=1e-3)


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


# The cycle gap on the Mature Stable route (method.md 14.4): it comes off E, the anchor earnings,
# after the engine's margin normalization, and nothing else reads it.


def test_a_cycle_gap_lowers_the_anchor_earnings(
    ms_context: Context, with_overrides: WithOverrides, policy: Policy, deciles: Deciles
) -> None:
    plain = value_mature_stable(ms_context)
    lowered = value_mature_stable(with_overrides(ms_context, {"earnings.cycle_gap": 1.0}))
    assert lowered.intermediates["cycle_gap"] == 1.0
    assert lowered.intermediates["e_normalized"] == pytest.approx(
        plain.intermediates["e_normalized"] - 1.0 * ms_context.shares
    )
    assert lowered.intermediates["e_trailing"] == plain.intermediates["e_trailing"]
    assert lowered.intermediates["margin_scaled"] is False
    assert "cycle_gap" not in plain.intermediates
    plain_result = value_company(ms_context.inputs, deciles, policy, ms_context.today)
    assert current_reading(plain_result, "earnings.cycle_gap") == 0.0
    # the clean EPS, the P/E and the flags do not read it
    assert lowered.intermediates["eps"] == plain.intermediates["eps"]
    assert lowered.intermediates["multiples"] == plain.intermediates["multiples"]
    assert lowered.flags == plain.flags
    assert isinstance(lowered, Valued) and isinstance(plain, Valued)
    assert lowered.value < plain.value


def test_the_cycle_gap_comes_off_the_normalized_earnings(
    ms_context: Context, with_overrides: WithOverrides
) -> None:
    """MSCO at a 32% trailing margin against its 20% median: the margin flag fires and the engine
    scales E by 0.20 / 0.32. The agent's cycle gap then comes off the scaled E, so the anchor
    falls by exactly the gap on the shares, not by the gap scaled again."""
    peak_trailing = replace(ms_context.trailing, operating_income=7_680e6)
    peak_inputs = replace(ms_context.inputs, trailing=peak_trailing)
    peak = replace(ms_context, inputs=peak_inputs, trailing=peak_trailing)
    plain = value_mature_stable(peak)
    lowered = value_mature_stable(with_overrides(peak, {"earnings.cycle_gap": 1.0}))
    assert isinstance(plain, Valued) and isinstance(lowered, Valued)
    p, q = plain.intermediates, lowered.intermediates
    assert p["margin_scaled"] is True and q["margin_scaled"] is True
    assert p["e_normalized"] == pytest.approx(p["e_trailing"] * 0.20 / 0.32)
    assert q["e_normalized"] == p["e_normalized"] - 1.0 * peak.shares
    assert q["e_trailing"] == p["e_trailing"]
    assert lowered.value < plain.value


def test_a_cycle_gap_of_nothing_moves_nothing(
    ms_context: Context, with_overrides: WithOverrides
) -> None:
    nothing = value_mature_stable(with_overrides(ms_context, {"earnings.cycle_gap": 0.0}))
    plain = value_mature_stable(ms_context)
    assert isinstance(nothing, Valued) and isinstance(plain, Valued)
    assert nothing.value == plain.value
    assert nothing.intermediates.pop("cycle_gap") == 0.0
    assert nothing == plain
