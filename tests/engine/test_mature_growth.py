import math
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import cast

import pytest
from support.engine_companies import half_yearly

from fairband.engine.classifier import Deciles
from fairband.engine.mature_growth import (
    Charge,
    GrowthPath,
    cash_to_equity,
    charge_growth,
    earnings_by_year,
    first_negative_year,
    growth_rates,
    hold_years,
    implied_growth,
    negative_years,
    return_by_year,
    solve_root,
    terminal_multiple,
    value_at_belief,
)
from fairband.engine.overrides import Override, OverrideTag, current_reading
from fairband.engine.review import review_company
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.route_mature_growth import value_mature_growth
from fairband.engine.route_steps import Context, Valued
from fairband.policy import Policy

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
R, GT = 0.09, 0.03
FADE = GrowthPath(1000.0, (0.25, 0.26), 0.053, 20, fade_years=5)
CHARGE = Charge(0.149, 0.13, R, GT)
# spec 2026-11-09 section 13: the worked path, runway 5, with its revenue steps and its hold
TOY = GrowthPath(100.0, (0.25, 0.20), 0.05, 5, 5, revenue_steps=(0.15, 0.10))
TOY_CHARGE = Charge(0.20, 0.13, R, GT, hold=4)


def worked_example() -> GrowthPath:
    """design 6.5: Wide moat, N = 20, consensus path 12% then 10%, belief 8%, year 1 = 1."""
    return GrowthPath(year1=1.0, steps=(0.12, 0.10), belief=0.08, runway=20)


def uncharged() -> Charge:
    return Charge(math.inf, math.inf, R, GT)


# The exact multiple at 30% is 1.03 × 0.9 ÷ 0.06 = 15.45; the design rounds it to 15.5, which sits
# on the edge of the 0.05 tolerance.
@pytest.mark.parametrize(
    ("roic", "expected"),
    [(math.inf, 17.2), (0.30, 15.5), (0.15, 13.7), (0.13, 13.2), (0.09, 11.4)],
)
def test_terminal_multiples_design_table(roic: float, expected: float) -> None:
    assert terminal_multiple(roic, R, GT) == pytest.approx(expected, abs=0.05)


def test_uncharged_matches_design() -> None:
    assert value_at_belief(worked_example(), uncharged()) == pytest.approx(31.7, abs=0.1)


@pytest.mark.parametrize(("roic", "expected"), [(0.30, 25.5), (0.20, 22.4), (0.15, 19.3)])
def test_charged_terminal_equals_runway(roic: float, expected: float) -> None:
    value = value_at_belief(worked_example(), Charge(roic, roic, R, GT))
    assert value == pytest.approx(expected, abs=0.1)


def test_implied_growth_at_20pct_roic() -> None:
    # the design's price proxy is the uncharged value at 8%; at a 20% ROIC that price needs 11.8%
    price = value_at_belief(worked_example(), uncharged())
    g = implied_growth(price, worked_example(), Charge(0.20, 0.20, R, GT))
    assert g == pytest.approx(0.118, abs=0.002)


@pytest.mark.parametrize(("roic", "expected"), [(0.30, 23.6), (0.20, 21.2), (0.15, 18.9)])
def test_charged_with_wide_cap(roic: float, expected: float) -> None:
    # production rule: terminal ROIC capped at 13%
    value = value_at_belief(worked_example(), Charge(roic, 0.13, R, GT))
    assert value == pytest.approx(expected, abs=0.1)


def test_implied_growth_round_trip() -> None:
    p, c = worked_example(), Charge(0.20, 0.13, R, GT)
    assert implied_growth(value_at_belief(p, c), p, c) == pytest.approx(0.08, abs=1e-5)


def test_implied_growth_none_when_out_of_range() -> None:
    assert implied_growth(1e9, worked_example(), Charge(0.20, 0.13, R, GT)) is None


def test_charge_off_keeps_the_terminal_charge() -> None:
    off = Charge(0.20, 0.13, R, GT, charge_off=True)
    assert value_at_belief(worked_example(), off) == pytest.approx(28.2647, abs=0.001)
    assert value_at_belief(FADE, replace(CHARGE, charge_off=True)) == pytest.approx(
        37618.17, abs=0.01
    )
    assert negative_years(FADE, replace(CHARGE, charge_off=True)) == ()  # no charge, none < 0


def test_growth_rates_take_the_belief_for_missing_steps() -> None:
    assert len(growth_rates(worked_example())) == 19
    assert growth_rates(worked_example())[:4] == (0.12, 0.10, 0.08, 0.08)
    path = GrowthPath(year1=1.0, steps=(None, 0.10), belief=0.05, runway=5)
    assert growth_rates(path) == (0.05, 0.10, 0.05, 0.05)


@pytest.mark.parametrize(
    ("runway", "expected"), [(1, ()), (2, (0.12,)), (3, (0.12, 0.10)), (4, (0.12, 0.10, 0.08))]
)
def test_growth_rates_short_runways(runway: int, expected: tuple[float, ...]) -> None:
    path = GrowthPath(year1=1.0, steps=(0.12, 0.10), belief=0.08, runway=runway)
    assert growth_rates(path) == expected


def test_earnings_by_year() -> None:
    path = GrowthPath(year1=100.0, steps=(0.10, None), belief=0.05, runway=4)
    assert earnings_by_year(path) == pytest.approx((100.0, 110.0, 115.5, 121.275))
    assert earnings_by_year(GrowthPath(100.0, (0.10, None), 0.05, 1)) == (100.0,)


def test_cash_to_equity_has_no_floor() -> None:
    assert cash_to_equity(100.0, 0.25, 0.20) == pytest.approx(-25.0)
    assert cash_to_equity(100.0, 0.25, 0.20, charge_off=True) == 100.0
    assert cash_to_equity(100.0, 0.25, math.inf) == 100.0


def test_value_timing_by_hand() -> None:
    # Year 1 pays for year 2's growth at the runway ROIC; year 2 (= N) pays for the terminal
    # growth at the terminal ROIC, and the terminal value grows year 2's earnings once.
    path = GrowthPath(year1=1.0, steps=(0.10, 0.50), belief=0.50, runway=2)
    year1 = 1.0 * (1 - 0.10 / 0.20) / 1.09
    year2 = 1.1 * (1 - 0.03 / 0.13) / 1.09**2
    terminal = 1.1 * 1.03 * (1 - 0.03 / 0.13) / 0.06 / 1.09**2
    assert value_at_belief(path, Charge(0.20, 0.13, R, GT)) == pytest.approx(
        year1 + year2 + terminal
    )


def test_value_with_a_one_year_runway() -> None:
    path = GrowthPath(year1=1.0, steps=(0.10, 0.10), belief=0.10, runway=1)
    expected = (1 - 0.03 / 0.13) * (1 + 1.03 / 0.06) / 1.09
    assert value_at_belief(path, Charge(0.20, 0.13, R, GT)) == pytest.approx(expected)


def test_implied_growth_when_value_falls_with_growth() -> None:
    # a runway ROIC below r makes growth destroy value; the scan still finds the belief
    p, c = GrowthPath(1.0, (None, None), 0.04, 10), Charge(0.06, 0.09, R, GT)
    assert value_at_belief(replace(p, belief=0.06), c) < value_at_belief(p, c)
    assert implied_growth(value_at_belief(p, c), p, c) == pytest.approx(0.04, abs=1e-5)


def test_fade_path_rates_and_earnings() -> None:
    assert growth_rates(FADE)[:8] == pytest.approx(
        (0.25, 0.26, 0.2186, 0.1772, 0.1358, 0.0944, 0.053, 0.053), abs=1e-4
    )
    assert earnings_by_year(FADE)[:9] == pytest.approx(
        (1000.00, 1250.00, 1575.00, 1919.29, 2259.39, 2566.22, 2808.47, 2957.32, 3114.06),
        abs=0.01,
    )
    # the last fade year lands on the belief exactly, as do the years after it
    assert growth_rates(FADE)[6:] == (0.053,) * 13


def test_fade_cut_by_the_runway() -> None:
    five = replace(FADE, runway=5)
    assert growth_rates(five) == pytest.approx((0.25, 0.26, 0.2186, 0.1772), abs=1e-4)
    # spec 2026-11-09 6.1: years 1 to 4 pay for growth above the 14.9% return and pay out less
    # than nothing, where the floor held them at zero (20,520.66)
    assert value_at_belief(five, CHARGE) == pytest.approx(18289.57, abs=0.01)


def test_no_fade_when_g3_is_at_or_below_the_belief() -> None:
    path = GrowthPath(1000.0, (0.04, 0.05), 0.053, 20, fade_years=5)
    assert growth_rates(path)[:4] == pytest.approx((0.04, 0.05, 0.053, 0.053))
    assert value_at_belief(path, CHARGE) == pytest.approx(14910.79, abs=0.01)


def test_no_fade_when_g3_is_the_belief() -> None:
    path = GrowthPath(1000.0, (0.25, None), 0.053, 20, fade_years=5)
    assert growth_rates(path)[1:4] == pytest.approx((0.053, 0.053, 0.053))
    assert negative_years(path, CHARGE) == (1,)  # year 1 pays for the 25% step, above 14.9%


def test_charge_growth_reads_the_revenue_steps_then_fades_to_the_belief() -> None:
    assert charge_growth(TOY) == pytest.approx((0.15, 0.10, 0.09, 0.08))
    assert growth_rates(TOY) == pytest.approx((0.25, 0.20, 0.17, 0.14))


def test_a_missing_revenue_step_takes_the_earnings_step() -> None:
    path = replace(TOY, revenue_steps=(0.15, None))
    assert charge_growth(path) == pytest.approx((0.15, 0.20, 0.17, 0.14))
    assert charge_growth(replace(TOY, revenue_steps=None)) == growth_rates(TOY)


def test_a_missing_earnings_step_with_a_present_revenue_step() -> None:
    path = replace(TOY, steps=(None, 0.20))  # the earnings step takes the belief
    assert growth_rates(path)[0] == pytest.approx(0.05)
    assert charge_growth(path)[0] == pytest.approx(0.15)


def test_hold_years_is_the_last_year_above_the_belief() -> None:
    assert hold_years(TOY) == 4
    assert hold_years(replace(TOY, runway=10)) == 6
    assert hold_years(GrowthPath(100.0, (0.02, 0.20), 0.05, 10, 5)) == 6  # a flat step inside
    assert hold_years(GrowthPath(100.0, (GT, GT), GT, 10, 5)) == 0
    assert hold_years(GrowthPath(100.0, (0.25, 0.20), 0.05, 1, 5)) == 0


def test_return_by_year_holds_then_fades() -> None:
    assert return_by_year(TOY_CHARGE, 5) == pytest.approx((0.20, 0.20, 0.20, 0.20, 0.13))
    ten = Charge(0.20, 0.13, R, GT, hold=6)
    assert return_by_year(ten, 10) == pytest.approx(
        (0.20, 0.20, 0.20, 0.20, 0.20, 0.20, 0.1825, 0.165, 0.1475, 0.13)
    )
    stable = Charge(0.20, 0.13, R, GT, hold=0)
    assert return_by_year(stable, 10)[0] == pytest.approx(0.193)
    assert return_by_year(stable, 1) == (0.13,)  # a one-year runway: T alone, no division by zero
    as_built = Charge(0.20, 0.13, R, GT)  # hold None: R through year N − 1, T in year N
    assert return_by_year(as_built, 5) == pytest.approx((0.20, 0.20, 0.20, 0.20, 0.13))
    assert return_by_year(as_built, 1) == (0.13,)


def test_value_on_the_spec_s_runway_5_path() -> None:
    assert value_at_belief(TOY, TOY_CHARGE) == pytest.approx(2030.9538, abs=1e-3)
    earnings_only = replace(TOY, revenue_steps=None)
    flat = Charge(0.20, 0.13, R, GT, hold=4)
    assert value_at_belief(earnings_only, flat) == pytest.approx(1848.8476, abs=1e-3)


def test_value_on_the_spec_s_runway_10_paths() -> None:
    ten = replace(TOY, runway=10)
    assert value_at_belief(ten, Charge(0.20, 0.13, R, GT, hold=6)) == pytest.approx(
        2293.8222, abs=1e-3
    )
    stable = GrowthPath(100.0, (GT, GT), GT, 10, 5)
    assert value_at_belief(stable, Charge(0.20, 0.13, R, GT, hold=0)) == pytest.approx(
        1315.0993, abs=1e-3
    )


def test_the_fallback_example() -> None:
    path = replace(TOY, revenue_steps=(0.15, None))
    assert value_at_belief(path, TOY_CHARGE) == pytest.approx(1894.7191, abs=1e-3)


def test_at_a_return_of_r_the_belief_enters_only_through_the_margin_change() -> None:
    """Method 5.8: at a return equal to r in every year the charge takes every dollar of revenue
    growth, so the value is year-1 earnings over r plus the present value of the uncharged margin
    change in the years the two paths differ, and the belief enters only through those years'
    figures. Pinned: on the review's path (earnings steps 12% and 10%, revenue steps 8% and 7%)
    the value moves with the belief; on a path whose two steps agree, with no earnings step
    missing, it is flat at year-1 earnings over r."""
    at_r = Charge(0.09, 0.09, 0.09, 0.03, hold=6)
    path = GrowthPath(100.0, (0.12, 0.10), 0.063, 20, 5, revenue_steps=(0.08, 0.07))

    def value(p: GrowthPath, belief: float) -> float:
        return value_at_belief(replace(p, belief=belief), at_r)

    moving = [value(path, b) for b in (-0.5, 0.0, 0.063, 0.08, 0.095)]
    assert len(set(moving)) == 5
    assert implied_growth(1240.0, path, at_r) == pytest.approx(-0.3503, abs=1e-4)
    agree = replace(path, revenue_steps=(0.12, 0.10))  # the earnings steps as the revenue steps
    assert value(agree, 0.0) == pytest.approx(value(agree, 0.10))
    assert value(agree, 0.0) == pytest.approx(100.0 / 0.09)
    no_revenue = replace(path, revenue_steps=None)  # the charge falls back on the earnings steps
    for belief in (-0.5, 0.063, 0.3):
        assert value(no_revenue, belief) == pytest.approx(100.0 / 0.09)


def test_negative_years_name_the_owner_s_money_going_in() -> None:
    path = replace(TOY, revenue_steps=None)
    assert negative_years(path, TOY_CHARGE) == (1,)
    assert first_negative_year(path, TOY_CHARGE) == pytest.approx((1, 0.25, 0.20))
    assert negative_years(TOY, TOY_CHARGE) == ()
    assert negative_years(path, Charge(0.20, 0.13, R, GT, True, 4)) == ()  # the charge off


def test_solve_root_finds_the_first_sign_change() -> None:
    assert solve_root(lambda x: x * x - 4, 0.0, 10.0) == pytest.approx(2.0, abs=1e-6)
    assert solve_root(lambda x: x + 20, 0.0, 10.0) is None


# The cycle gap on the Mature Growth route (method.md 14.4): it lowers the NTM anchor the value
# rests on, and nothing else. ``mg_context`` and ``with_overrides`` are conftest.py's.

WithOverrides = Callable[..., Context]


def _valued(c: Context) -> Valued:
    found = value_mature_growth(c)
    assert isinstance(found, Valued)
    return found


def test_a_cycle_gap_lowers_the_anchor_earnings(
    mg_context: Context, with_overrides: WithOverrides
) -> None:
    plain = _valued(mg_context)
    lowered = _valued(with_overrides(mg_context, {"earnings.cycle_gap": 1.0}))
    assert lowered.intermediates["cycle_gap"] == 1.0
    assert "cycle_gap" not in plain.intermediates
    assert plain.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.90)
    assert lowered.intermediates["anchor"]["ntm_eps"] == pytest.approx(4.90)
    assert lowered.intermediates["ntm_net_income"] == pytest.approx(
        plain.intermediates["ntm_net_income"] - 1.0 * mg_context.shares
    )
    assert lowered.value < plain.value
    # the data entries keep the consensus as found; the JUDGMENT entry carries the agent's gap
    cited = {x.name: x.value for x in lowered.inputs}
    assert cited["ntm_eps"] == plain.intermediates["anchor"]["ntm_eps"]
    assert cited["ntm_net_income"] == plain.intermediates["ntm_net_income"]


def test_a_cycle_gap_of_nothing_moves_nothing(
    mg_context: Context, with_overrides: WithOverrides
) -> None:
    nothing = _valued(with_overrides(mg_context, {"earnings.cycle_gap": 0.0}))
    plain = _valued(mg_context)
    assert nothing.value == plain.value
    assert nothing.intermediates.pop("cycle_gap") == 0.0
    assert nothing == plain


def test_the_cycle_gap_lowers_the_anchor_and_leaves_the_gap_its_own(
    mg_context: Context, with_overrides: WithOverrides
) -> None:
    """A cycle gap of 1.00 takes the NTM anchor and the value down and stays out of what the
    non-recurring gap moves: the basis test for stock compensation, the clean EPS, EPV and the
    P/E. Alone it leaves MGCO's basis as found, where a correction of 1.00 to the gap would switch
    it; beside a gap of 0.50 the basis is the gap's alone."""
    c = mg_context
    plain = _valued(c)
    cycle = _valued(with_overrides(c, {"earnings.cycle_gap": 1.0}))
    gap = _valued(with_overrides(c, {"earnings.nri_gap": 0.5}))
    both = _valued(with_overrides(c, {"earnings.nri_gap": 0.5, "earnings.cycle_gap": 1.0}))
    assert plain.intermediates["sbc_basis"] == cycle.intermediates["sbc_basis"] == "includes-sbc"
    assert gap.intermediates["sbc_basis"] == both.intermediates["sbc_basis"] == "excludes-sbc"
    for alone, beside in ((plain, cycle), (gap, both)):
        a, b = alone.intermediates, beside.intermediates
        assert b["anchor"]["ntm_eps_raw"] == a["anchor"]["ntm_eps_raw"]
        assert b["anchor"]["sbc_adjustment_per_share"] == a["anchor"]["sbc_adjustment_per_share"]
        assert b["anchor"]["ntm_eps"] == pytest.approx(a["anchor"]["ntm_eps"] - 1.0)
        assert (b["nri_gap"], b["eps"], b["epv"]) == (a["nri_gap"], a["eps"], a["epv"])
        assert b["multiples"] == a["multiples"]
        assert beside.value < alone.value


def test_the_forward_eps_is_the_analysts_as_found_and_a_second_one_bears_stock_pay(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Method 5.9 under 1.10. MGCO at a street trailing EPS of 8.50 reads excludes-sbc, and the
    anchor takes 0.30 a share of stock pay off the analysts' 5.90. The forward EPS is the
    analysts' as they state it, 5.90, and the forward P/E the price over it; the forward EPS
    after stock pay is the 5.60 the value rests on, with its own P/E. A reprice moves both."""
    charged = value_company(replace(mg_inputs, street_ttm_eps=8.50), deciles, policy, TODAY)
    im = charged.intermediates
    assert im["sbc_basis"] == "excludes-sbc"
    assert im["anchor"]["sbc_adjustment_per_share"] == pytest.approx(0.30)
    assert im["anchor"]["ntm_eps"] == pytest.approx(5.60)
    assert im["eps"]["forward"] == pytest.approx(5.90)
    assert im["eps"]["forward_after_sbc"] == pytest.approx(5.60)
    assert im["multiples"]["pe_forward"] == pytest.approx(150 / 5.90)
    assert im["multiples"]["pe_forward_after_sbc"] == pytest.approx(150 / 5.60)
    # the value's own input is still the analysts' EPS less the charge
    assert {x.name: x.value for x in charged.inputs}["ntm_eps"] == pytest.approx(5.60)
    at_170 = reprice(charged, 170.0, date(2026, 11, 2), policy).intermediates["multiples"]
    assert at_170["pe_forward"] == pytest.approx(170 / 5.90)
    assert at_170["pe_forward_after_sbc"] == pytest.approx(170 / 5.60)


# The NTM earnings override on the Mature Growth route (method.md 14.4): a clear guidance stands in
# for the consensus NTM EPS the anchor reads, and the cycle gap is still taken off it.


def _consensus_eps(i: CompanyInputs, ntm_eps: float) -> CompanyInputs:
    """``i`` with its NTM consensus at ``ntm_eps`` a share: the four quarters' EPS means sum to it
    exactly, the whole of it in the first."""
    assert len(i.quarter_estimates) == 4  # MGCO's are its NTM quarters
    means = (ntm_eps, 0.0, 0.0, 0.0)
    quarters = tuple(replace(q, eps=x) for q, x in zip(i.quarter_estimates, means, strict=True))
    return replace(i, quarter_estimates=quarters)


def _judged(**values: float) -> dict[OverrideTag, Override]:
    """Applied overrides by tag, ``earnings_ntm`` naming ``earnings.ntm``."""
    tags = {name: cast(OverrideTag, name.replace("_", ".", 1)) for name in values}
    return {
        tags[name]: Override(n, tags[name], x, "agent", "claude-opus-5-5", NOW, "guided")
        for n, (name, x) in enumerate(values.items(), start=4)
    }


def test_the_ntm_earnings_override_replaces_the_anchor(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """MGCO's NTM consensus of 5.90 a share includes stock compensation, so its anchor is the
    consensus as found. An override of 6.45 values the row as a consensus of 6.45 would; the
    JUDGMENT entry stands for the ``ntm_eps`` data entry, the NTM net income entry and the forward
    P/E keep the consensus as found, and the bridge's line reads the consensus as its old value."""
    mechanical = value_company(mg_inputs, deciles, policy, TODAY)
    guided = _judged(earnings_ntm=6.45)
    judged = value_company(mg_inputs, deciles, policy, TODAY, guided)
    raised = value_company(_consensus_eps(mg_inputs, 6.45), deciles, policy, TODAY)
    assert judged.value is not None and mechanical.value is not None
    assert judged.value == raised.value and judged.value > mechanical.value
    anchor = judged.intermediates["anchor"]
    assert anchor["ntm_eps"] == 6.45 and anchor["ntm_eps_raw"] == pytest.approx(5.90)
    assert judged.intermediates["ntm_net_income"] == raised.intermediates["ntm_net_income"]
    assert judged.intermediates["eps"]["forward"] == pytest.approx(5.90)
    assert judged.intermediates["eps"]["forward_after_sbc"] == pytest.approx(5.90)
    assert judged.intermediates["multiples"] == mechanical.intermediates["multiples"]
    cited = {x.name: x for x in judged.inputs}
    assert "ntm_eps" not in cited and "ntm_eps" in {x.name for x in mechanical.inputs}
    shares = mg_inputs.shares_diluted
    assert shares is not None
    assert cited["ntm_net_income"].value == pytest.approx(5.90 * shares)
    ntm = cited["earnings.ntm"]
    assert (ntm.tag, ntm.value, ntm.unit) == ("JUDGMENT", 6.45, "USD a share")
    review = review_company(mg_inputs, deciles, policy, TODAY, list(guided.values()), mechanical)
    [line] = review.bridge
    assert line.tag == "earnings.ntm" and line.old == pytest.approx(5.90) and line.new == 6.45
    assert line.delta == judged.value - mechanical.value


def test_the_cycle_gap_comes_off_the_guided_anchor(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The cycle gap applies to the override's figure as it does to the consensus: a guided 6.45
    less a gap of 1.00 is an anchor of 5.45, and the reading of the NTM earnings stays 6.45."""
    both = value_company(
        mg_inputs, deciles, policy, TODAY, _judged(earnings_ntm=6.45, earnings_cycle_gap=1.0)
    )
    lowered = value_company(
        _consensus_eps(mg_inputs, 6.45), deciles, policy, TODAY, _judged(earnings_cycle_gap=1.0)
    )
    assert both.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.45)
    assert both.value == lowered.value
    assert current_reading(both, "earnings.ntm") == pytest.approx(6.45)
    judgments = [x.name for x in both.inputs if x.tag == "JUDGMENT"]
    assert judgments == ["earnings.ntm", "earnings.cycle_gap"]


def test_a_guided_anchor_at_or_below_the_cycle_gap_refuses(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    judged = _judged(earnings_ntm=2.0, earnings_cycle_gap=2.0)
    r = value_company(mg_inputs, deciles, policy, TODAY, judged)
    assert r.refusal == "no positive forward anchor"
    assert current_reading(r, "earnings.ntm") is None  # a refusal before the anchor is stored


def test_the_cross_check_reads_the_consensus_eps_as_found(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The NTM earnings override is the Mature Growth route's own: a Mature Stable row's
    cross-check reads the consensus as found and does not move under it."""
    mechanical = value_company(ms_inputs, deciles, policy, TODAY)
    judged = value_company(ms_inputs, deciles, policy, TODAY, _judged(earnings_ntm=9.0))
    assert judged.intermediates["growth_route"] == mechanical.intermediates["growth_route"]
    assert judged.value == mechanical.value


# A half-yearly reporter (spec 2026-11-10 8): the NTM window is its two half-years, or the four
# quarters its consensus gives.


def test_a_half_yearly_reporter_values_on_its_two_half_years(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """MGCO reporting half-yearly, its consensus two half-years of 2.85 and 3.05 a share ending
    2027-03-31 and 2027-09-30: the anchor sums the two to its four quarters' 5.90, the base year
    is 2027 as on the quarters, and the value is the quarterly row's."""
    quarterly = value_company(mg_inputs, deciles, policy, TODAY)
    r = value_company(half_yearly(mg_inputs), deciles, policy, TODAY)
    assert (r.route, r.refusal) == ("mature-growth", None)
    assert r.intermediates["anchor"]["ntm_eps_raw"] == pytest.approx(2.85 + 3.05)
    assert r.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.90)
    assert r.intermediates["path"]["base_year"] == 2027
    assert r.value is not None and r.value == pytest.approx(quarterly.value)


def test_the_window_follows_the_trailing_cadence(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The ruling on spec 2026-11-10 8: a quarterly reporter reads no window in two half-years
    and is refused "incomplete NTM consensus"; a half-yearly reporter whose consensus rows are
    quarters (ABVX) reads the four quarters and values as the quarterly row."""
    quarterly = value_company(mg_inputs, deciles, policy, TODAY)
    halves = half_yearly(mg_inputs)
    on_quarters = replace(halves, trailing=mg_inputs.trailing)
    assert value_company(on_quarters, deciles, policy, TODAY).refusal == (
        "incomplete NTM consensus"
    )
    abvx = value_company(replace(mg_inputs, trailing=halves.trailing), deciles, policy, TODAY)
    assert abvx.value == quarterly.value and abvx.intermediates == quarterly.intermediates
