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

RATES = runoff_rates(-0.03, -0.03, -0.03, -0.04, 10)


def _valuation(
    margin: float = 0.08, rates: Sequence[float] = RATES, d: float = -0.04
) -> RunoffValuation:
    """Spec 13.1's Decline row: revenue 1,000, tax 25%, sales-to-capital 2.0, recovery 0.6,
    r 9%."""
    return runoff_valuation(1000.0, rates, margin, 0.25, 2.0, 0.6, 0.09, d)


FIRM = _valuation().firm_value


def test_the_worked_decline_row() -> None:
    """Spec 13.1's figures to its decimals, pinned to the exact decimals the arithmetic gives."""
    v = _valuation()
    assert v.revenue[0] == 970.0 and v.fcff[0] == pytest.approx(67.2, abs=1e-9)
    assert v.revenue[9] == pytest.approx(685.8258241874084, abs=1e-9)  # spec 685.83
    assert v.fcff[9] == pytest.approx(49.72237225358714, abs=1e-9)  # spec 49.72
    assert v.fcff_n1 == pytest.approx(47.73347736344364, abs=1e-9)  # spec 47.73
    assert v.terminal_value == pytest.approx(367.1805951034126, abs=1e-9)  # spec 367.18
    assert v.pv_flows == pytest.approx(387.55123129552135, abs=1e-9)  # spec 387.55
    assert v.pv_terminal == pytest.approx(155.10105145407172, abs=1e-9)  # spec 155.10
    assert v.firm_value == pytest.approx(542.652282749593, abs=1e-9)  # spec 542.65
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6)
    assert e.gc_per_share == pytest.approx(4.426522827495931, abs=1e-9)  # spec 4.4265
    assert e.distress_per_share == pytest.approx(2.255913696497558, abs=1e-9)  # spec 2.2559
    assert e.value_per_share == pytest.approx(4.317992370946012, abs=1e-9)  # spec 4.3180
    assert not e.floor_bound and e.ncav_per_share == pytest.approx(-2.0)
    assert e.floored_per_share == e.gc_per_share


def test_the_worked_table() -> None:
    v = _valuation()
    revenue = (970.00, 940.90, 912.67, 876.17, 841.12, 807.47, 775.18, 744.17, 714.40, 685.83)
    ebit = (77.60, 75.27, 73.01, 70.09, 67.29, 64.60, 62.01, 59.53, 57.15, 54.87)
    nopat = (58.20, 56.45, 54.76, 52.57, 50.47, 48.45, 46.51, 44.65, 42.86, 41.15)
    net = (-9.00, -8.73, -8.47, -10.95, -10.51, -10.09, -9.69, -9.30, -8.93, -8.57)
    fcff = (67.20, 65.18, 63.23, 63.52, 60.98, 58.54, 56.20, 53.95, 51.79, 49.72)
    assert v.revenue == pytest.approx(revenue, abs=0.01)
    assert v.ebit == pytest.approx(ebit, abs=0.01)
    assert v.nopat == pytest.approx(nopat, abs=0.01)
    assert v.tax == pytest.approx(tuple(e * 0.25 for e in v.ebit))
    assert v.reinvestment == (0.0,) * 10
    assert tuple(i - rel for i, rel in zip(v.reinvestment, v.release, strict=True)) == (
        pytest.approx(net, abs=0.01)
    )
    assert v.fcff == pytest.approx(fcff, abs=0.01)
    assert v.revenue_n1 == pytest.approx(658.39, abs=0.01)
    assert v.nopat_n1 == pytest.approx(41.15 * 0.96, abs=0.01)


def test_net_cash_takes_no_distress() -> None:
    e = runoff_equity(FIRM, 200.0, 250.0, 100.0, ncav=-200.0, pi=0.0, fraction=0.6)
    assert e.gc_per_share == pytest.approx(5.926522827495931, abs=1e-9)  # spec 5.9265
    assert e.value_per_share == e.gc_per_share


def test_no_pi_is_the_floored_value() -> None:
    e = runoff_equity(FIRM, 200.0, 100.0, 100.0, ncav=-200.0, pi=None, fraction=0.6)
    assert e.value_per_share == pytest.approx(4.426522827495931, abs=1e-9)  # spec 4.4265
    assert e.value_per_share == e.floored_per_share == e.gc_per_share


def test_the_ncav_floor_binds() -> None:
    e = runoff_equity(FIRM, 200.0, 100.0, 100.0, ncav=600.0, pi=0.05, fraction=0.6)
    assert e.floor_bound and e.ncav_per_share == pytest.approx(6.0)
    assert e.floored_per_share == pytest.approx(6.0)
    assert e.gc_per_share == pytest.approx(4.426522827495931, abs=1e-9)
    assert e.value_per_share == pytest.approx(5.812795684824877, abs=1e-9)  # spec 5.8128


def test_no_ncav_and_an_ncav_below_the_going_concern_leave_no_floor() -> None:
    for ncav in (None, 0.0, 400.0):
        e = runoff_equity(FIRM, 200.0, 100.0, 100.0, ncav=ncav, pi=0.05, fraction=0.6)
        assert not e.floor_bound and e.floored_per_share == e.gc_per_share
    assert runoff_equity(FIRM, 200.0, 100.0, 100.0, None, 0.05, 0.6).ncav_per_share is None


def test_a_chronic_loss_with_net_debt() -> None:
    """At a margin of -1% nothing is taxed. Each lost dollar of revenue releases 0.5 of capital
    recovered at 0.6, so from year 4 the release (1.2% of the year before's revenue) outweighs the
    loss and the firm value stays above zero, 11.29; the equity is below zero and the distress
    proceeds, 0.6 × 11.29 + 100, are below the debt of 200, so at π = 100% the value is zero."""
    v = _valuation(margin=-0.01)
    assert v.tax == (0.0,) * 10 and v.nopat == v.ebit
    assert v.nopat_n1 == pytest.approx(v.revenue_n1 * -0.01)
    assert v.fcff[0] == pytest.approx(-0.7) and v.fcff[3] > 0
    assert v.firm_value == pytest.approx(11.288502182042098, abs=1e-9)
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=1.0, fraction=0.6)
    assert e.gc_per_share < 0
    assert e.distress_per_share == 0.0 and e.value_per_share == 0.0


def test_a_rising_consensus_step_reinvests_in_full() -> None:
    rates = runoff_rates(-0.03, 0.02, -0.03, -0.04, 10)
    v = _valuation(rates=rates)
    assert v.revenue[:2] == pytest.approx((970.0, 989.4))
    assert v.reinvestment[1] == pytest.approx((989.4 - 970.0) / 2.0) and v.release[1] == 0.0
    assert v.fcff[1] == pytest.approx(v.nopat[1] - v.reinvestment[1])
    assert v.release[0] == pytest.approx(9.0) and v.reinvestment[0] == 0.0


def test_no_consensus_takes_d_in_every_year() -> None:
    assert runoff_rates(None, None, None, -0.04, 10) == (-0.04,) * 10
    assert runoff_rates(None, 0.05, 0.05, -0.04, 10) == (-0.04,) * 10


def test_a_missing_step_holds_the_rate_of_the_year_before() -> None:
    assert runoff_rates(-0.03, None, None, -0.04, 10) == (-0.03,) * 3 + (-0.04,) * 7
    assert runoff_rates(-0.03, -0.02, None, -0.04, 10) == (-0.03, -0.02, -0.02) + (-0.04,) * 7
    assert runoff_rates(-0.03, None, -0.01, -0.04, 10) == (-0.03, -0.03, -0.01) + (-0.04,) * 7


def test_a_steep_decline_rate_still_values() -> None:
    rates = runoff_rates(-0.03, -0.03, -0.03, -0.8, 10)
    v = _valuation(rates=rates, d=-0.8)
    assert all(math.isfinite(x) for x in (*v.fcff, v.terminal_value, v.firm_value))
    assert v.terminal_value > 0 and v.firm_value > 0


def _value_at(d: float) -> float:
    rates = runoff_rates(-0.03, -0.03, -0.03, d, 10)
    v = _valuation(rates=rates, d=d)
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6)
    return e.value_per_share


def test_the_implied_decline_rate_recovers_d() -> None:
    implied = implied_decline_rate(_value_at, 4.3180)
    assert implied is not None and implied == pytest.approx(-0.04, abs=1e-4)
    exact = implied_decline_rate(_value_at, 4.317992370946012)
    assert exact is not None and exact == pytest.approx(-0.04, abs=1e-7)
    assert implied_decline_rate(_value_at, _value_at(0.0) + 0.01) is None
    assert implied_decline_rate(_value_at, _value_at(-0.5) - 0.01) is None
