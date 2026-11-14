from dataclasses import replace

import pytest

from fairband.engine.mature_growth import terminal_multiple
from fairband.engine.revenue_growth import (
    Bridge,
    MarginPath,
    PeerFigures,
    RevenueCharge,
    RevenuePath,
    ebit_by_year,
    growth_rates,
    implied_hold_growth,
    implied_target_margin,
    margins_by_year,
    own_sales_to_capital,
    peer_roic_median,
    peer_sales_to_capital,
    resolved_steps,
    return_on_new_capital,
    revenue_by_year,
    revenue_valuation,
    target_margin,
    tax_and_nopat,
    terminal_nopat,
)
from fairband.engine.roic import RoicYear, terminal_roic
from fairband.policy import Policy

PATH = RevenuePath(1_000.0, 1_300.0, (0.25, 0.20), None, 5, 5, 0.03)
MARGIN = MarginPath(-0.10, 0.20, 10)
CHARGE = RevenueCharge(0.09, 0.03, 0.09, 2.0)
BRIDGE = Bridge(100.0, 300.0, 100.0)


def test_growth_rates_hold_then_fade() -> None:
    assert growth_rates(PATH) == pytest.approx(
        (0.30, 0.25, 0.20, 0.20, 0.20, 0.166, 0.132, 0.098, 0.064, 0.03)
    )


def test_revenue_by_year() -> None:
    assert revenue_by_year(PATH) == pytest.approx(
        (1300.0, 1625.0, 1950.0, 2340.0, 2808.0, 3274.13, 3706.31, 4069.53, 4329.98, 4459.88),
        abs=0.01,
    )


def test_missing_steps_hold_the_last_known_rate() -> None:
    (g2, g3), held = resolved_steps(replace(PATH, steps=(None, None)))
    assert (g2, g3) == pytest.approx((0.30, 0.30)) and held == (True, True)
    (g2, g3), held = resolved_steps(replace(PATH, steps=(0.25, None)))
    assert (g2, g3) == pytest.approx((0.25, 0.25)) and held == (False, True)


def test_hold_overrides_g3() -> None:
    assert growth_rates(replace(PATH, hold=0.10))[3:5] == pytest.approx((0.10, 0.10))
    assert growth_rates(replace(PATH, hold=0.10))[9] == pytest.approx(0.03)


def test_fade_rises_when_g3_is_below_the_terminal_rate() -> None:
    rates = growth_rates(replace(PATH, steps=(0.0, -0.02)))
    assert rates[4] == pytest.approx(-0.02) and rates[5] == pytest.approx(-0.01)
    assert rates[9] == pytest.approx(0.03)


def test_margins_converge_linearly_both_ways() -> None:
    assert margins_by_year(MarginPath(-0.10, 0.20, 10), 10) == pytest.approx(
        (-0.07, -0.04, -0.01, 0.02, 0.05, 0.08, 0.11, 0.14, 0.17, 0.20)
    )
    assert margins_by_year(MarginPath(0.30, 0.20, 10), 10)[9] == pytest.approx(0.20)
    assert margins_by_year(MarginPath(-0.10, 0.20, 5), 10)[4:] == pytest.approx((0.20,) * 6)


def test_tax_carries_the_forecast_losses() -> None:
    ebit = (-91.0, -65.0, -19.5, 46.8, 140.4, 261.93, 407.69, 569.73, 736.1, 891.98)
    tax, nopat = tax_and_nopat(ebit, 0.21)
    assert tax == pytest.approx((0, 0, 0, 0, 2.46, 55.01, 85.62, 119.64, 154.58, 187.32), abs=0.01)
    assert nopat[4] == pytest.approx(137.94, abs=0.01) and nopat[0] == pytest.approx(-91.0)


def test_a_loss_after_profit_years_starts_a_new_carry() -> None:
    tax, nopat = tax_and_nopat((100.0, -50.0, 80.0, 10.0), 0.25)
    assert tax == pytest.approx((25.0, 0.0, 7.5, 2.5))
    assert nopat == pytest.approx((75.0, -50.0, 72.5, 7.5))


def test_terminal_nopat_is_taxed_in_full_and_a_loss_untaxed() -> None:
    assert terminal_nopat(891.98, 0.21) == pytest.approx(704.66, abs=0.01)
    assert terminal_nopat(-222.99, 0.21) == -222.99
    assert terminal_nopat(0.0, 0.21) == 0.0


def test_reinvestment_with_the_lag_and_the_terminal_year() -> None:
    v = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, BRIDGE)
    assert v.reinvestment == pytest.approx(
        (162.5, 162.5, 195.0, 234.0, 233.06, 216.09, 181.61, 130.23, 64.95, 234.89), abs=0.01
    )


def test_reinvestment_never_negative() -> None:
    v = revenue_valuation(
        replace(PATH, ntm_revenue=900.0, steps=(-0.1, -0.1)), MARGIN, 0.21, CHARGE, BRIDGE
    )
    assert min(v.reinvestment[:9]) == 0.0


def test_value_of_the_worked_example() -> None:
    v = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, BRIDGE)
    assert v.fcff[0] == pytest.approx(-253.5, abs=0.01) and v.fcff[9] == pytest.approx(
        469.77, abs=0.01
    )
    assert v.terminal_value == pytest.approx(8064.46, abs=0.01)
    assert v.firm_value == pytest.approx(3290.57, abs=0.01)
    assert v.equity == pytest.approx(3490.57, abs=0.01)
    assert v.value_per_share == pytest.approx(34.91, abs=0.01)


def test_the_bridge_subtracts_the_minority_interest() -> None:
    """Spec 2026-11-13 13: a minority interest of 50 on 100 shares takes 0.50 off the value a
    share, and a nil one changes nothing."""
    base = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, BRIDGE)
    less = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, replace(BRIDGE, minority=50.0))
    assert less.value_per_share == pytest.approx(base.value_per_share - 0.5)
    assert less.equity == pytest.approx(base.equity - 50.0) and less.firm_value == base.firm_value
    assert revenue_valuation(PATH, MARGIN, 0.21, CHARGE, replace(BRIDGE, minority=0.0)) == base


def test_the_worked_examples_carry_ends_before_year_10() -> None:
    """The carried loss of 175.50 is used up in year 5, so year 10's NOPAT after the carry is
    already the one at the full rate that the terminal reads."""
    v = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, BRIDGE)
    assert v.terminal_nopat == pytest.approx(v.nopat[9], rel=1e-12)
    assert v.terminal_nopat == pytest.approx(v.ebit[9] * 0.79)
    assert v.terminal_nopat == pytest.approx(704.66, abs=0.01)


def test_a_carry_past_year_9_shields_year_10_but_not_the_terminal() -> None:
    """From a trailing margin of -50% the forecast's losses outlast year 9: year 10 pays no tax
    on its 891.98, but the terminal value and year 10's reinvestment read 891.98 × 0.79."""
    v = revenue_valuation(PATH, replace(MARGIN, start=-0.50), 0.21, CHARGE, BRIDGE)
    assert v.ebit[9] == pytest.approx(891.98, abs=0.01)
    assert v.tax[9] == 0.0 and v.nopat[9] == v.ebit[9]
    assert v.terminal_nopat == pytest.approx(v.ebit[9] * 0.79)
    assert v.terminal_nopat == pytest.approx(704.66, abs=0.01)
    multiple = terminal_multiple(0.09, 0.09, 0.03)
    assert v.terminal_value == pytest.approx(v.terminal_nopat * multiple)
    assert v.terminal_value == pytest.approx(8064.46, abs=0.01)
    assert v.reinvestment[9] == pytest.approx(v.terminal_nopat * 0.03 / 0.09)
    assert v.reinvestment[9] == pytest.approx(234.89, abs=0.01)
    assert v.fcff[9] == pytest.approx(v.nopat[9] - v.reinvestment[9])  # the carried NOPAT
    assert v.fcff[9] == pytest.approx(657.09, abs=0.01)
    assert v.value_per_share == pytest.approx(9.32, abs=0.01)


def test_a_loss_in_year_10_reaches_the_terminal_untaxed() -> None:
    v = revenue_valuation(PATH, replace(MARGIN, target=-0.05), 0.21, CHARGE, BRIDGE)
    assert v.ebit[9] == pytest.approx(-222.99, abs=0.01)
    assert v.terminal_nopat == v.ebit[9] == v.nopat[9]
    assert v.terminal_value == pytest.approx(v.ebit[9] * terminal_multiple(0.09, 0.09, 0.03))
    assert v.reinvestment[9] == pytest.approx(v.ebit[9] * 0.03 / 0.09)


def test_value_at_other_inputs() -> None:
    assert revenue_valuation(
        PATH, replace(MARGIN, target=0.10), 0.21, CHARGE, BRIDGE
    ).value_per_share == pytest.approx(10.09, abs=0.01)
    assert revenue_valuation(
        PATH, replace(MARGIN, target=0.30), 0.21, CHARGE, BRIDGE
    ).value_per_share == pytest.approx(59.64, abs=0.01)
    assert revenue_valuation(
        PATH, MARGIN, 0.21, replace(CHARGE, sales_to_capital=3.0), BRIDGE
    ).value_per_share == pytest.approx(38.50, abs=0.01)
    assert revenue_valuation(
        PATH, MARGIN, 0.21, replace(CHARGE, terminal_return=0.13), BRIDGE
    ).value_per_share == pytest.approx(40.45, abs=0.01)


def test_the_dollar_ramp_from_a_loss_larger_than_revenue() -> None:
    """Spec 2026-11-06 13.2: from a trailing margin of -150% the operating income moves in dollars
    from -1,500 to 20% of year 10's revenue, 891.98, and the margins are the EBITs over revenue."""
    ramp = MarginPath(-1.5, 0.20, 10, in_dollars=True)
    ebit = ebit_by_year(revenue_by_year(PATH), ramp, 1000.0)
    assert ebit == pytest.approx(
        (-1260.80, -1021.60, -782.41, -543.21, -304.01, -64.81, 174.38, 413.58, 652.78, 891.98),
        abs=0.01,
    )
    v = revenue_valuation(PATH, ramp, 0.21, CHARGE, BRIDGE)
    assert v.ebit == ebit
    assert v.margins[0] == pytest.approx(-0.9698, abs=1e-4) and v.margins[9] == pytest.approx(0.20)
    assert v.nopat[9] == pytest.approx(891.98, abs=0.01) and v.tax == (0.0,) * 10
    assert v.terminal_nopat == pytest.approx(704.66, abs=0.01)
    assert v.fcff[0] == pytest.approx(-1423.30, abs=0.01)
    assert v.fcff[9] == pytest.approx(657.09, abs=0.01)
    assert v.terminal_value == pytest.approx(8064.46, abs=0.01)
    assert v.firm_value == pytest.approx(-31.33, abs=0.01)
    assert v.equity == pytest.approx(168.67, abs=0.01)
    assert v.value_per_share == pytest.approx(1.6867, abs=1e-4)


def test_the_margin_path_from_the_same_loss_gives_minus_61_94() -> None:
    v = revenue_valuation(PATH, MarginPath(-1.5, 0.20, 10), 0.21, CHARGE, BRIDGE)
    assert v.ebit[0] == pytest.approx(1300.0 * -1.33)
    assert v.value_per_share == pytest.approx(-61.94, abs=0.01)


def test_the_ramp_holds_the_target_margin_after_the_convergence_year() -> None:
    v = revenue_valuation(PATH, MarginPath(-1.5, 0.20, 5, in_dollars=True), 0.21, CHARGE, BRIDGE)
    assert v.ebit[4] == pytest.approx(0.20 * v.revenue[4])
    assert v.margins[4:] == pytest.approx((0.20,) * 6)
    assert v.ebit[0] == pytest.approx(-1500.0 + (0.20 * v.revenue[4] + 1500.0) / 5)


def test_the_ramp_past_the_explicit_period_ends_at_year_ten_revenue() -> None:
    """With the convergence year past year 10 the ramp's end is the target margin on year 10's
    revenue at year 12, so year 10 is ten twelfths of the way there, below the target."""
    v = revenue_valuation(PATH, MarginPath(-1.5, 0.20, 12, in_dollars=True), 0.21, CHARGE, BRIDGE)
    end = 0.20 * v.revenue[9]
    assert end == pytest.approx(891.98, abs=0.01)
    assert v.ebit[0] == pytest.approx(-1500.0 + (end + 1500.0) / 12)
    assert v.ebit[9] == pytest.approx(-1500.0 + (end + 1500.0) * 10 / 12)
    assert v.margins[9] < 0.20


def test_return_on_new_capital() -> None:
    assert return_on_new_capital(0.20, 0.21, 2.0) == pytest.approx(0.316)


def test_implied_growth_and_margin_at_the_price(policy: Policy) -> None:
    assert implied_hold_growth(25.0, PATH, MARGIN, 0.21, CHARGE, BRIDGE) == pytest.approx(
        0.086275, abs=1e-5
    )
    assert implied_target_margin(
        25.0, PATH, MARGIN, 0.21, 2.0, "None", policy, BRIDGE
    ) == pytest.approx(0.160014, abs=1e-5)
    # round trips
    assert implied_hold_growth(34.9057, PATH, MARGIN, 0.21, CHARGE, BRIDGE) == pytest.approx(
        0.20, abs=1e-4
    )
    assert implied_target_margin(
        34.9057, PATH, MARGIN, 0.21, 2.0, "None", policy, BRIDGE
    ) == pytest.approx(0.20, abs=1e-4)


def test_the_margin_the_price_needs_on_the_ramp(policy: Policy) -> None:
    """The solve rebuilds the dollar ramp from each trial margin (spec 2026-11-06 13.2)."""
    ramp = MarginPath(-1.5, -1.5, 10, in_dollars=True)  # the solve sets the target
    assert implied_target_margin(
        25.0, PATH, ramp, 0.21, 2.0, "None", policy, BRIDGE
    ) == pytest.approx(0.277164, abs=1e-5)


def test_implied_margin_reads_the_terminal_from_the_trial_margin(policy: Policy) -> None:
    # Wide moat: at a 20% target the return on new capital is 31.6%, so the terminal is the 13% cap
    # and the value is 40.45; the solve at that price returns 20%.
    assert implied_target_margin(
        40.45, PATH, MARGIN, 0.21, 2.0, "Wide", policy, BRIDGE
    ) == pytest.approx(0.20, abs=1e-3)


def test_implied_margin_reads_the_terminal_at_each_trial_margin(policy: Policy) -> None:
    # Wide moat at a 5% target: the return on new capital is 7.9%, below r, so the terminal is r.
    # The input target of 20% would give the 13% cap; a single read of it would solve near 4.5%.
    terminal = terminal_roic(return_on_new_capital(0.05, 0.21, 2.0), "Wide", policy)
    assert terminal == policy.required_return
    bridge = replace(BRIDGE, cash=1_000.0)
    at_five = replace(MARGIN, target=0.05)
    price = revenue_valuation(
        PATH, at_five, 0.21, replace(CHARGE, terminal_return=terminal), bridge
    ).value_per_share
    assert price > 0
    assert implied_target_margin(
        price, PATH, MARGIN, 0.21, 2.0, "Wide", policy, bridge
    ) == pytest.approx(0.05, abs=1e-5)


def test_sales_to_capital_must_be_positive() -> None:
    for s2c in (0.0, -1.0):
        with pytest.raises(ValueError, match="sales-to-capital"):
            RevenueCharge(0.09, 0.03, 0.09, s2c)


def test_negative_target_margin_values_below_zero(policy: Policy) -> None:
    charge = replace(
        CHARGE,
        terminal_return=terminal_roic(return_on_new_capital(-0.05, 0.21, 2.0), "Wide", policy),
    )
    assert charge.terminal_return == 0.09
    assert (
        revenue_valuation(PATH, replace(MARGIN, target=-0.05), 0.21, charge, BRIDGE).value_per_share
        < 0
    )


def test_own_sales_to_capital_usability() -> None:
    def kept(caps: list[float]) -> list[RoicYear]:
        return [RoicYear(2017 + k, 10.0, c, None) for k, c in enumerate(caps)]

    revenue = {2017 + k: 1000.0 + 300.0 * k for k in range(6)}  # 2,500 in 2022
    s2c, usable = own_sales_to_capital(kept([400, 500, 600, 700, 800, 900]), revenue, 5, 0.20)
    assert s2c == pytest.approx(3.0) and usable
    s2c, usable = own_sales_to_capital(kept([400, 404, 408, 412, 416, 420]), revenue, 5, 0.20)
    assert s2c == pytest.approx(75.0) and not usable  # capital grew 5%
    assert own_sales_to_capital(kept([400, 500, 600, 700, 800]), revenue, 5, 0.20) == (None, False)
    falling = {y: 2000.0 - 100.0 * k for k, y in enumerate(revenue)}
    assert own_sales_to_capital(kept([400, 500, 600, 700, 800, 900]), falling, 5, 0.20)[1] is False
    assert own_sales_to_capital(kept([400, 500, 600, 700, 800, 900]), {2022: 2500.0}, 5, 0.20) == (
        None,
        False,
    )


def test_target_margin_from_peers(policy: Policy) -> None:
    peers = [
        PeerFigures("A", 10e9, 0.10, 10, 2.5, 0.12),
        PeerFigures("B", 50e9, 0.30, 8, 1.5, 0.20),
        PeerFigures("C", 20e9, 0.20, 6, 3.0, 0.15),
        PeerFigures("D", 5e9, 0.40, 3, None, None),
    ]
    t = target_margin(peers, policy)
    assert t is not None and t.value == pytest.approx(0.20) and t.count == 3
    assert (t.low, t.high) == (0.10, 0.30) and t.largest_symbol == "B" and t.largest_margin == 0.30
    assert target_margin(peers[:2], policy) is None
    assert peer_sales_to_capital(peers, policy) == pytest.approx(2.5)
    assert peer_sales_to_capital(peers[:2], policy) is None
    assert peer_roic_median(peers) == pytest.approx(0.15)
