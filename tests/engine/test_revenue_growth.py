from dataclasses import replace

import pytest

from fairband.engine.revenue_growth import (
    MarginPath,
    RevenuePath,
    growth_rates,
    margins_by_year,
    resolved_steps,
    revenue_by_year,
    tax_and_nopat,
)

PATH = RevenuePath(1_000.0, 1_300.0, (0.25, 0.20), None, 5, 5, 0.03)


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
