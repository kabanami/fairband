"""The Start-up route's core: the ten-year ramp to a year-10 revenue and the revenue the price needs
(spec 2026-11-03 sections 9.2 and 13.2)."""

import pytest

from fairband.engine.requirement import ramp_ev, required_revenue

# Spec 13.2: no revenue, a trailing operating loss of 50, the peers' 25% margin and 1.5
# sales-to-capital, tax 25%, r 9%, g_T 3% and no moat (terminal return r).
RAMP = {
    "revenue0": 0.0,
    "ebit0": -50.0,
    "target_margin": 0.25,
    "tax_rate": 0.25,
    "sales_to_capital": 1.5,
    "r": 0.09,
    "g_t": 0.03,
    "terminal_return": 0.09,
}
MULTIPLE = 1.03 * (1 - 0.03 / 0.09) / (0.09 - 0.03)  # 11.4444


def test_the_worked_start_up_requirement() -> None:
    at_zero = ramp_ev(0.0, **RAMP)
    assert at_zero.firm_value == pytest.approx(-166.93, abs=0.005)
    # no revenue: the loss shrinks by 5 a year to nothing in year 10, untaxed, with no reinvestment
    assert at_zero.revenue == (0.0,) * 10
    assert at_zero.ebit == pytest.approx([-50 + 5 * t for t in range(1, 11)])
    assert at_zero.tax == (0.0,) * 10 and at_zero.nopat == at_zero.ebit
    assert at_zero.reinvestment == (0.0,) * 10 and at_zero.fcff == at_zero.ebit
    assert (at_zero.terminal_nopat, at_zero.terminal_value) == (0.0, 0.0)

    at_1000 = ramp_ev(1_000.0, **RAMP)
    assert at_1000.firm_value == pytest.approx(931.91, abs=0.005)
    assert at_1000.revenue == pytest.approx([100.0 * t for t in range(1, 11)])
    # operating income from −50 to 0.25 × 1,000 = 250 in a straight line: 30 a year
    assert at_1000.ebit == pytest.approx([-50 + 30 * t for t in range(1, 11)])
    # year 1's loss of 20 carries: year 2 pays nothing on its 10, year 3 pays on 30 of its 40
    assert at_1000.tax[:4] == pytest.approx([0.0, 0.0, 7.5, 17.5])
    # years 1 to 9 reinvest the next year's 100 of revenue at 1.5; year 10 pays for g_T on the
    # terminal NOPAT, 250 × 0.75 = 187.5, at the terminal return
    assert at_1000.reinvestment == pytest.approx([100 / 1.5] * 9 + [187.5 * 0.03 / 0.09])
    assert at_1000.fcff == pytest.approx(
        [n - i for n, i in zip(at_1000.nopat, at_1000.reinvestment, strict=True)]
    )
    assert at_1000.terminal_nopat == pytest.approx(187.5)
    assert at_1000.terminal_value == pytest.approx(187.5 * MULTIPLE)
    assert at_1000.pv_terminal == pytest.approx(at_1000.terminal_value / 1.09**10)
    assert at_1000.firm_value == pytest.approx(at_1000.pv_flows + at_1000.pv_terminal)

    revenue = required_revenue(1_700.0, **RAMP)
    assert revenue == pytest.approx(1_725.73, abs=0.01)
    assert revenue is not None and ramp_ev(revenue, **RAMP).firm_value == pytest.approx(
        1_700.0, abs=1e-4
    )


def test_no_revenue_reaches_the_price() -> None:
    assert required_revenue(1e15, **RAMP) is None
    # a target margin below zero loses more the more revenue the path reaches
    assert required_revenue(100.0, **(RAMP | {"target_margin": -0.05})) is None


def test_a_price_the_ramp_covers_at_no_revenue_needs_none() -> None:
    """The requirement is the least year-10 revenue at which the ramp is worth the price: none when
    the ramp to zero revenue is already worth it."""
    profitable = RAMP | {"revenue0": 400.0, "ebit0": 100.0}
    at_zero = ramp_ev(0.0, **profitable).firm_value
    assert at_zero > 0
    assert required_revenue(at_zero / 2, **profitable) == 0.0
    assert required_revenue(at_zero, **profitable) == 0.0
    above = required_revenue(at_zero + 500, **profitable)
    assert above is not None and above > 0


def test_the_ramp_starts_from_trailing_revenue() -> None:
    """A positive trailing revenue: the path is a straight line from it, and a year-10 revenue below
    it reinvests nothing in years 1 to 9."""
    v = ramp_ev(2_000.0, **(RAMP | {"revenue0": 1_000.0}))
    assert v.revenue == pytest.approx([1_000 + 100 * t for t in range(1, 11)])
    assert v.reinvestment[:9] == pytest.approx([100 / 1.5] * 9)
    shrinking = ramp_ev(500.0, **(RAMP | {"revenue0": 1_000.0}))
    assert shrinking.revenue == pytest.approx([1_000 - 50 * t for t in range(1, 11)])
    assert shrinking.reinvestment[:9] == (0.0,) * 9
