import math
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from fairband.engine.mature_growth import (
    Charge,
    GrowthPath,
    cash_to_equity,
    earnings_by_year,
    first_floored_year,
    floored_years,
    growth_rates,
    implied_growth,
    solve_root,
    terminal_multiple,
    value_at_belief,
)
from fairband.engine.overrides import Override, OverrideTag
from fairband.engine.route import CompanyInputs
from fairband.engine.route_mature_growth import value_mature_growth
from fairband.engine.route_steps import Context, Valued
from fairband.policy import Policy

R, GT = 0.09, 0.03
TODAY = date(2026, 10, 31)
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
FADE = GrowthPath(1000.0, (0.25, 0.26), 0.053, 20, fade_years=5)
CHARGE = Charge(0.149, 0.13, R, GT)


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
    assert floored_years(FADE, replace(CHARGE, charge_off=True)) == ()  # no charge, no floor


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


def test_cash_to_equity() -> None:
    assert cash_to_equity(100.0, 0.10, 0.20) == pytest.approx(50.0)
    assert cash_to_equity(100.0, -0.05, 0.20) == pytest.approx(125.0)
    assert cash_to_equity(100.0, 0.10, math.inf) == 100.0
    assert cash_to_equity(100.0, 0.10, 0.20, charge_off=True) == 100.0


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


def test_value_with_the_fade_and_the_floor() -> None:
    assert value_at_belief(FADE, CHARGE) == pytest.approx(24941.95, abs=0.01)
    assert value_at_belief(replace(FADE, fade_years=0), CHARGE) == pytest.approx(19699.10, abs=0.01)


def test_fade_cut_by_the_runway() -> None:
    five = replace(FADE, runway=5)
    assert growth_rates(five) == pytest.approx((0.25, 0.26, 0.2186, 0.1772), abs=1e-4)
    assert value_at_belief(five, CHARGE) == pytest.approx(20520.66, abs=0.01)


def test_no_fade_when_g3_is_at_or_below_the_belief() -> None:
    path = GrowthPath(1000.0, (0.04, 0.05), 0.053, 20, fade_years=5)
    assert growth_rates(path)[:4] == pytest.approx((0.04, 0.05, 0.053, 0.053))
    assert value_at_belief(path, CHARGE) == pytest.approx(14910.79, abs=0.01)


def test_no_fade_when_g3_is_the_belief() -> None:
    path = GrowthPath(1000.0, (0.25, None), 0.053, 20, fade_years=5)
    assert growth_rates(path)[1:4] == pytest.approx((0.053, 0.053, 0.053))
    assert floored_years(path, CHARGE) == (1,)  # year 1 pays for the 25% step and floors


def test_payout_floor() -> None:
    assert cash_to_equity(100.0, 0.25, 0.149) == 0.0  # -67.79 before the floor
    assert cash_to_equity(100.0, 0.053, 0.149) == pytest.approx(64.43, abs=0.01)
    assert floored_years(FADE, CHARGE) == (1, 2, 3, 4)  # growth above 14.9% in years 2 to 5


def test_first_floored_year() -> None:
    # year 1's reinvestment pays for year 2's 25% at the 14.9% runway return
    assert first_floored_year(FADE, CHARGE) == (1, 0.25, 0.149)
    path = GrowthPath(1000.0, (0.04, 0.05), 0.053, 20, fade_years=5)
    assert floored_years(path, CHARGE) == () and first_floored_year(path, CHARGE) is None
    # year N pays for g_t at the terminal return: one below g_t, which the engine never uses,
    # floors year N alone
    steep = Charge(0.149, 0.02, R, GT)
    assert first_floored_year(path, steep) == (20, GT, 0.02)


def test_solve_root_finds_the_first_sign_change() -> None:
    assert solve_root(lambda x: x * x - 4, 0.0, 10.0) == pytest.approx(2.0, abs=1e-6)
    assert solve_root(lambda x: x + 20, 0.0, 10.0) is None


# The cycle gap on the Mature Growth route (method.md 14.4): it lowers the NTM anchor the value
# rests on, and nothing else.


@pytest.fixture
def context(mg_inputs: CompanyInputs, policy: Policy) -> Context:
    """MGCO past the guards, as ``route.value_company`` builds it: $150 on 1 bn shares, an NTM
    consensus of 5.90 a share that includes stock compensation, a non-recurring gap of 0.05."""
    i = mg_inputs
    assert i.trailing is not None and i.price is not None and i.shares_diluted is not None
    return Context(i, i.trailing, i.price, i.shares_diluted, policy, TODAY)


def with_overrides(c: Context, values: dict[OverrideTag, float]) -> Context:
    """``c`` under an agent's overrides of ``values``, by tag."""
    judged = {
        tag: Override(1, tag, value, "agent", "claude-opus-5-5", NOW, "mid-cycle")
        for tag, value in values.items()
    }
    return replace(c, overrides=judged)


def _valued(c: Context) -> Valued:
    found = value_mature_growth(c)
    assert isinstance(found, Valued)
    return found


def test_a_cycle_gap_lowers_the_anchor_earnings(context: Context) -> None:
    plain = _valued(context)
    lowered = _valued(with_overrides(context, {"earnings.cycle_gap": 1.0}))
    assert lowered.intermediates["cycle_gap"] == 1.0
    assert "cycle_gap" not in plain.intermediates
    assert plain.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.90)
    assert lowered.intermediates["anchor"]["ntm_eps"] == pytest.approx(4.90)
    assert lowered.intermediates["ntm_net_income"] == pytest.approx(
        plain.intermediates["ntm_net_income"] - 1.0 * context.shares
    )
    assert lowered.value < plain.value
    # the data entries keep the consensus as found; the JUDGMENT entry carries the agent's gap
    cited = {x.name: x.value for x in lowered.inputs}
    assert cited["ntm_eps"] == plain.intermediates["anchor"]["ntm_eps"]
    assert cited["ntm_net_income"] == plain.intermediates["ntm_net_income"]


def test_a_cycle_gap_of_nothing_moves_nothing(context: Context) -> None:
    nothing = _valued(with_overrides(context, {"earnings.cycle_gap": 0.0}))
    plain = _valued(context)
    assert nothing.value == plain.value
    assert nothing.intermediates.pop("cycle_gap") == 0.0
    assert nothing == plain


def test_the_cycle_gap_lowers_the_anchor_and_leaves_the_gap_its_own(context: Context) -> None:
    """A cycle gap of 1.00 takes the NTM anchor and the value down and stays out of what the
    non-recurring gap moves: the basis test for stock compensation, the clean EPS, EPV, the P/E
    and ``large-nri``. Alone it leaves MGCO's basis as found, where a correction of 1.00 to the
    gap would switch it; beside a gap of 0.50 the basis is the gap's alone."""
    plain = _valued(context)
    cycle = _valued(with_overrides(context, {"earnings.cycle_gap": 1.0}))
    gap = _valued(with_overrides(context, {"earnings.nri_gap": 0.5}))
    both = _valued(with_overrides(context, {"earnings.nri_gap": 0.5, "earnings.cycle_gap": 1.0}))
    assert plain.intermediates["sbc_basis"] == cycle.intermediates["sbc_basis"] == "includes-sbc"
    assert gap.intermediates["sbc_basis"] == both.intermediates["sbc_basis"] == "excludes-sbc"
    for alone, beside in ((plain, cycle), (gap, both)):
        a, b = alone.intermediates, beside.intermediates
        assert b["anchor"]["ntm_eps_raw"] == a["anchor"]["ntm_eps_raw"]
        assert b["anchor"]["sbc_adjustment_per_share"] == a["anchor"]["sbc_adjustment_per_share"]
        assert b["anchor"]["ntm_eps"] == pytest.approx(a["anchor"]["ntm_eps"] - 1.0)
        assert (b["nri_gap"], b["eps"], b["epv"]) == (a["nri_gap"], a["eps"], a["epv"])
        assert b["multiples"] == a["multiples"]
        large = [f for f in beside.flags if f.code == "large-nri"]
        assert large == [f for f in alone.flags if f.code == "large-nri"]
        assert beside.value < alone.value
