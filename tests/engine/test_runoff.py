import math
from collections.abc import Sequence

import pytest

from fairband.engine.runoff import (
    RunoffValuation,
    implied_decline_rate,
    runoff_equity,
    runoff_rates,
    runoff_valuation,
)

RATES = runoff_rates(-0.03, -0.03, -0.03, (), -0.04, 10)
# Spec 2026-11-06 13.1: d = −4% fades to zero from year 4 to year 10, g_t = d × (10 − t) ÷ 7.
FADE = (-0.034285714, -0.028571429, -0.022857143, -0.017142857, -0.011428571, -0.005714286, 0.0)


def _valuation(margin: float = 0.08, rates: Sequence[float] = RATES) -> RunoffValuation:
    """Spec 13.1's Decline row: revenue 1,000, tax 25%, sales-to-capital 2.0, recovery 0.6,
    r 9%."""
    return runoff_valuation(1000.0, rates, margin, 0.25, 2.0, 0.6, 0.09)


FIRM = _valuation().firm_value


def test_rates_fade_from_d_to_zero_after_the_consensus() -> None:
    assert RATES == pytest.approx((-0.03, -0.03, -0.03, *FADE))
    assert RATES[-1] == 0.0 and math.copysign(1.0, RATES[-1]) == 1.0  # zero, not −0.0
    k5 = runoff_rates(-0.03, -0.03, -0.03, (0.01, 0.02), -0.04, 10)
    assert k5[3:] == pytest.approx((0.01, 0.02, -0.032, -0.024, -0.016, -0.008, 0.0))


def test_no_consensus_takes_d_then_the_fade() -> None:
    assert runoff_rates(None, None, None, (), -0.04, 10) == pytest.approx((-0.04,) * 3 + FADE)
    assert runoff_rates(None, 0.05, 0.05, (), -0.04, 10) == pytest.approx((-0.04,) * 3 + FADE)


def test_a_consensus_to_year_ten_leaves_no_fade() -> None:
    beyond = (0.01, 0.02, -0.01, -0.02, 0.0, 0.03, 0.01)
    rates = runoff_rates(-0.03, -0.03, -0.03, beyond, -0.04, 10)
    assert rates == (-0.03, -0.03, -0.03, *beyond)
    with pytest.raises(ValueError, match="8 consensus years past year 3"):
        runoff_rates(-0.03, -0.03, -0.03, (*beyond, 0.01), -0.04, 10)


def test_the_worked_decline_row() -> None:
    """Spec 13.1's figures to its decimals, pinned to the exact decimals the arithmetic gives."""
    v = _valuation()
    assert v.revenue[0] == 970.0 and v.fcff[0] == pytest.approx(67.2, abs=1e-9)
    assert v.revenue[9] == pytest.approx(808.243918251305, abs=1e-9)  # spec 808.24
    assert v.fcff[9] == pytest.approx(48.49463509507831, abs=1e-9)  # spec 48.49
    assert v.fcff_n1 == pytest.approx(48.49463509507831, abs=1e-9)  # spec 48.49
    assert v.terminal_value == pytest.approx(538.8292788342035, abs=1e-9)  # spec 538.83
    assert v.pv_flows == pytest.approx(379.87358536899904, abs=1e-9)
    assert v.pv_terminal == pytest.approx(227.607310451378, abs=1e-9)
    assert v.firm_value == pytest.approx(607.4808958203771, abs=1e-9)  # spec 607.48
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6)
    assert e.gc_per_share == pytest.approx(5.074808958203771, abs=1e-9)  # spec 5.0748
    assert e.distress_per_share == pytest.approx(2.6448853749222625, abs=1e-9)  # spec 2.6449
    assert e.value_per_share == pytest.approx(4.9533, abs=1e-4)  # spec 4.9533
    assert e.value_per_share == pytest.approx(4.953312779039696, abs=1e-9)
    assert not e.floor_bound and e.ncav_per_share == pytest.approx(-2.0)
    assert e.floored_per_share == e.gc_per_share


def test_the_minority_interest_comes_off_each_claim() -> None:
    """Spec 2026-11-13 13: 50 of minority interest on 100 shares takes 0.50 off the going
    concern (5.0748 to 4.5748) and off the distress sale (2.6449 to 2.1449), so off the value
    (4.9533 to 4.4533); the floor is the NCAV less it, 600 − 50 on 100 shares."""
    v = _valuation()
    e = runoff_equity(
        v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6, minority=50.0
    )
    assert e.gc_per_share == pytest.approx(4.574808958203771, abs=1e-9)
    assert e.distress_per_share == pytest.approx(2.1448853749222626, abs=1e-9)
    assert e.value_per_share == pytest.approx(4.453312779039696, abs=1e-9)
    assert e.ncav_per_share == pytest.approx(-2.5)
    floored = runoff_equity(
        v.firm_value, 200.0, 100.0, 100.0, ncav=600.0, pi=None, fraction=0.6, minority=50.0
    )
    assert floored.floor_bound and floored.value_per_share == pytest.approx(5.5)
    drowned = runoff_equity(
        100.0, 200.0, 100.0, 100.0, ncav=None, pi=1.0, fraction=0.6, minority=50.0
    )
    assert drowned.distress_per_share == 0.0  # 60 + 100 − 200 − 50 is below zero
    # a nil minority interest is the worked row's, to the last digit
    assert runoff_equity(
        v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6, minority=0.0
    ) == runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6)


def test_the_worked_table() -> None:
    v = _valuation()
    revenue = (970.00, 940.90, 912.67, 881.38, 856.20, 836.63, 822.29, 812.89, 808.24, 808.24)
    ebit = (77.60, 75.27, 73.01, 70.51, 68.50, 66.93, 65.78, 65.03, 64.66, 64.66)
    nopat = (58.20, 56.45, 54.76, 52.88, 51.37, 50.20, 49.34, 48.77, 48.49, 48.49)
    net = (-9.00, -8.73, -8.47, -9.39, -7.55, -5.87, -4.30, -2.82, -1.39, 0.0)
    fcff = (67.20, 65.18, 63.23, 62.27, 58.93, 56.07, 53.64, 51.59, 49.89, 48.49)
    assert v.revenue == pytest.approx(revenue, abs=0.01)
    assert v.ebit == pytest.approx(ebit, abs=0.01)
    assert v.nopat == pytest.approx(nopat, abs=0.01)
    assert v.tax == pytest.approx(tuple(e * 0.25 for e in v.ebit))
    assert v.reinvestment == (0.0,) * 10
    assert tuple(i - rel for i, rel in zip(v.reinvestment, v.release, strict=True)) == (
        pytest.approx(net, abs=0.01)
    )
    assert v.fcff == pytest.approx(fcff, abs=0.01)
    assert v.revenue_n1 == pytest.approx(808.24, abs=0.01)
    assert v.nopat_n1 == pytest.approx(48.49, abs=0.01)


def test_the_terminal_is_flat() -> None:
    """Revenue_{N+1} is year N's, the NOPAT on it is year N's, and nothing is released or
    reinvested: FCFF_{N+1} is that NOPAT and the terminal value FCFF_{N+1} ÷ r."""
    for rates in (RATES, runoff_rates(-0.03, -0.03, -0.03, (0.05,) * 7, -0.04, 10)):
        v = _valuation(rates=rates)
        assert v.revenue_n1 == v.revenue[-1]
        assert v.nopat_n1 == v.revenue[-1] * 0.08 * 0.75 == pytest.approx(v.nopat[-1])
        assert v.fcff_n1 == v.nopat_n1
        assert v.terminal_value == v.fcff_n1 / 0.09
    # a loss in the terminal is not taxed
    v = _valuation(margin=-0.01)
    assert v.nopat_n1 == v.revenue[-1] * -0.01 == v.fcff_n1


def test_the_consensus_to_year_five() -> None:
    """Spec 13.1: base + 3 at +1% and base + 4 at +2%, so K = 5 and the fade runs from year 6."""
    v = _valuation(rates=runoff_rates(-0.03, -0.03, -0.03, (0.01, 0.02), -0.04, 10))
    assert v.revenue[4] == pytest.approx(940.2357246, abs=1e-6)  # spec 940.24
    assert v.revenue[9] == pytest.approx(867.0990170494869, abs=1e-9)  # spec 867.10
    rising = (v.revenue[3] - v.revenue[2], v.revenue[4] - v.revenue[3])
    assert v.reinvestment[3:5] == (rising[0] / 2.0, rising[1] / 2.0)
    assert v.release[3:5] == (0.0, 0.0) and v.release[5] > 0
    assert v.fcff_n1 == pytest.approx(52.02594102296922, abs=1e-9)  # spec 52.03
    assert v.terminal_value == pytest.approx(578.0660113663247, abs=1e-9)  # spec 578.07
    assert v.firm_value == pytest.approx(622.1850070160989, abs=1e-9)  # spec 622.19
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6)
    assert e.value_per_share == pytest.approx(5.0974, abs=1e-4)  # spec 5.0974
    assert e.value_per_share == pytest.approx(5.097413068757769, abs=1e-9)


def test_net_cash_takes_no_distress() -> None:
    e = runoff_equity(FIRM, 200.0, 250.0, 100.0, ncav=-200.0, pi=0.0, fraction=0.6)
    assert e.gc_per_share == pytest.approx(6.574808958203771, abs=1e-9)
    assert e.value_per_share == e.gc_per_share


def test_no_pi_is_the_floored_value() -> None:
    e = runoff_equity(FIRM, 200.0, 100.0, 100.0, ncav=-200.0, pi=None, fraction=0.6)
    assert e.value_per_share == pytest.approx(5.074808958203771, abs=1e-9)  # spec 5.0748
    assert e.value_per_share == e.floored_per_share == e.gc_per_share


def test_the_ncav_floor_binds() -> None:
    e = runoff_equity(FIRM, 200.0, 100.0, 100.0, ncav=600.0, pi=0.05, fraction=0.6)
    assert e.floor_bound and e.ncav_per_share == pytest.approx(6.0)
    assert e.floored_per_share == pytest.approx(6.0)
    assert e.gc_per_share == pytest.approx(5.074808958203771, abs=1e-9)
    assert e.value_per_share == pytest.approx(5.832244268746113, abs=1e-9)


def test_no_ncav_and_an_ncav_below_the_going_concern_leave_no_floor() -> None:
    for ncav in (None, 0.0, 400.0):
        e = runoff_equity(FIRM, 200.0, 100.0, 100.0, ncav=ncav, pi=0.05, fraction=0.6)
        assert not e.floor_bound and e.floored_per_share == e.gc_per_share
    assert runoff_equity(FIRM, 200.0, 100.0, 100.0, None, 0.05, 0.6).ncav_per_share is None


def test_a_chronic_loss_with_net_debt() -> None:
    """At a margin of -1% nothing is taxed. Each lost dollar of revenue releases 0.5 of capital
    recovered at 0.6, so in year 4, where d × 6 ÷ 7 takes 3.4% of revenue away, the release
    outweighs the loss; as the decline fades the release shrinks, and the flat terminal releases
    nothing, so the firm value is below zero, −52.70. The distress proceeds, 0.6 × −52.70 + 100,
    are below the debt of 200, so at π = 100% the value is zero."""
    v = _valuation(margin=-0.01)
    assert v.tax == (0.0,) * 10 and v.nopat == v.ebit
    assert v.nopat_n1 == pytest.approx(v.revenue_n1 * -0.01)
    assert v.fcff[0] == pytest.approx(-0.7) and v.fcff[3] > 0 and v.fcff[4] < 0
    assert v.firm_value == pytest.approx(-52.69598832271605, abs=1e-9)
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=1.0, fraction=0.6)
    assert e.gc_per_share < 0
    assert e.distress_per_share == 0.0 and e.value_per_share == 0.0


def test_a_rising_consensus_step_reinvests_in_full() -> None:
    rates = runoff_rates(-0.03, 0.02, -0.03, (), -0.04, 10)
    v = _valuation(rates=rates)
    assert v.revenue[:2] == pytest.approx((970.0, 989.4))
    assert v.reinvestment[1] == pytest.approx((989.4 - 970.0) / 2.0) and v.release[1] == 0.0
    assert v.fcff[1] == pytest.approx(v.nopat[1] - v.reinvestment[1])
    assert v.release[0] == pytest.approx(9.0) and v.reinvestment[0] == 0.0


def test_a_missing_step_holds_the_rate_of_the_year_before() -> None:
    assert runoff_rates(-0.03, None, None, (), -0.04, 10) == pytest.approx((-0.03,) * 3 + FADE)
    assert runoff_rates(-0.03, -0.02, None, (), -0.04, 10) == pytest.approx(
        (-0.03, -0.02, -0.02, *FADE)
    )
    assert runoff_rates(-0.03, None, -0.01, (), -0.04, 10) == pytest.approx(
        (-0.03, -0.03, -0.01, *FADE)
    )


def test_a_steep_decline_rate_still_values() -> None:
    rates = runoff_rates(-0.03, -0.03, -0.03, (), -0.8, 10)
    assert rates[3] == pytest.approx(-0.8 * 6 / 7) and rates[-1] == 0.0
    v = _valuation(rates=rates)
    assert all(math.isfinite(x) for x in (*v.fcff, v.terminal_value, v.firm_value))
    assert v.terminal_value > 0 and v.firm_value > 0


def _value_at(d: float) -> float:
    v = _valuation(rates=runoff_rates(-0.03, -0.03, -0.03, (), d, 10))
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6)
    return e.value_per_share


def test_the_implied_decline_rate_recovers_d() -> None:
    assert _value_at(0.0) == pytest.approx(5.2246997259006, abs=1e-9)  # spec 5.2247
    assert _value_at(-0.5) == pytest.approx(3.1250993474228768, abs=1e-9)  # spec 3.1251
    implied = implied_decline_rate(_value_at, 4.9533)
    assert implied is not None and implied == pytest.approx(-0.04, abs=1e-4)
    exact = implied_decline_rate(_value_at, 4.953312779039696)
    assert exact is not None and exact == pytest.approx(-0.04, abs=1e-7)
    # the value at −50% is above a price of 3.00: no decline rate gives it
    assert implied_decline_rate(_value_at, 3.00) is None
    assert implied_decline_rate(_value_at, _value_at(0.0) + 0.01) is None
