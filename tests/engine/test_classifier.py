from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from fairband.engine.classifier import (
    Deciles,
    FiscalYear,
    Series,
    classify,
    compute_deciles,
    decile,
    dickinson,
    growth_3y,
    is_startup,
    slope,
)
from fairband.engine.types import Flag, PhaseEvidence


def fy(
    year: int,
    rev: float | None,
    oi: float | None,
    cfo: float | None = 10,
    cfi: float | None = -5,
    cff: float | None = -2,
    capex: float | None = -5,
    cur: str = "USD",
) -> FiscalYear:
    return FiscalYear(
        year=year,
        period_end=date(year, 12, 31),
        currency=cur,
        revenue=rev,
        operating_income=oi,
        cfo=cfo,
        cfi=cfi,
        cff=cff,
        capex=capex,
    )


def series(revenue: list[float | None], income: list[float | None], **last: Any) -> Series:
    """Fiscal years ending in 2025, oldest first; keyword arguments go to the last year."""
    first = 2026 - len(revenue)
    rows = [fy(first + i, r, o) for i, (r, o) in enumerate(zip(revenue, income, strict=True))]
    rows[-1] = fy(2025, revenue[-1], income[-1], **last)
    return tuple(rows)


def codes(ev: PhaseEvidence) -> set[str]:
    return {c.code for c in ev.checks}


@pytest.fixture
def deciles() -> Deciles:
    return Deciles(
        growth_edges=(-0.10, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.30),
        margin_slope_edges=(-0.03, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 0.03),
        n_growth=100,
        n_margin=80,
        refresh_id=1,
    )


def test_slope_and_decile() -> None:
    assert slope([1, 2, 3, 4, 5]) == pytest.approx(1.0)
    edges = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert decile(0.5, edges) == 1 and decile(5, edges) == 6 and decile(100, edges) == 10


def test_decile_boundaries_and_empty_edges() -> None:
    edges = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert decile(1, edges) == 2  # a value on an edge goes to the decile above it
    assert decile(0.999, edges) == 1
    assert decile(9, edges) == 10
    assert decile(5.0, ()) == 1


def test_growth_3y() -> None:
    ones: list[float | None] = [1, 1, 1, 1, 1]
    assert growth_3y(series([50, 100, 110, 121, 133.1], ones)) == pytest.approx(0.1)
    assert growth_3y(series([100, 110, 121], ones[:3])) == pytest.approx(0.1)
    assert growth_3y(series([100, 121], ones[:2])) == pytest.approx(0.21)
    assert growth_3y(series([121], ones[:1])) is None
    assert growth_3y(series([None, 110, 121, 133.1], ones[:4])) is None
    assert growth_3y(series([100, 110, 121, None], ones[:4])) is None
    assert growth_3y(series([0, 10, 40], ones[:3])) is None
    assert growth_3y(series([-5, 10, 40], ones[:3])) is None


def test_is_startup() -> None:
    losses: list[float | None] = [-5, -5, -5, -5]
    assert is_startup(series([10, 20, 30, 0], losses))
    assert is_startup(series([0, 10, 40, 120], losses))
    assert not is_startup(series([0, 10, 40], losses[:3]))  # no year three years back
    assert not is_startup(series([None, 10, 40, 120], losses))  # unknown is not zero


def test_startup_when_revenue_zero_three_years_ago(deciles: Deciles) -> None:
    s = (fy(2022, 0, -5), fy(2023, 10, -8), fy(2024, 40, -9), fy(2025, 120, -9))
    assert classify(s, deciles).phase == "Start-up"


def test_unmeasurable_growth_is_startup(deciles: Deciles) -> None:
    ev = classify(series([0, 10, 40], [-5, -8, -9]), deciles)
    assert ev.phase == "Start-up" and ev.growth_3y is None and ev.growth_word is None
    assert "short-history" in codes(ev)


def test_decline_needs_low_growth_and_falling_trend(deciles: Deciles) -> None:
    falling = classify(series([100, 95, 90, 85, 80], [-5, -5, -5, -5, -5]), deciles)
    assert falling.growth_decile == 2 and falling.growth_word == "Close to zero or negative"
    assert falling.revenue_slope == pytest.approx(-5.0)
    assert falling.phase == "Decline"

    rising_trend = classify(series([60, 120, 70, 80, 100], [10, 10, 10, 10, 10]), deciles)
    assert rising_trend.growth_word == "Close to zero or negative"
    assert rising_trend.revenue_slope == pytest.approx(4.0)
    assert rising_trend.phase == "Mature Stable"

    not_low = classify(series([300, 100, 100, 102, 104], [10, 10, 10, 10, 10]), deciles)
    assert not_low.growth_word == "Low" and not_low.revenue_slope == pytest.approx(-39.0)
    assert not_low.phase == "Mature Stable"


def test_young_vs_high_growth_by_margin_slope(deciles: Deciles) -> None:
    revenue: list[float | None] = [100, 150, 225, 337.5, 506.25]
    young = classify(series(revenue, [-10, -20, -40, -80, -200]), deciles)
    assert young.growth_word == "Very High"
    assert young.margin_slope is not None and young.margin_slope < 0
    assert young.phase == "Young Growth"

    high = classify(series(revenue, [-50, -60, -70, -60, -40]), deciles)
    assert high.margin_slope is not None and high.margin_slope > 0
    assert high.phase == "High Growth"


def test_mature_growth_vs_stable_by_growth_word(deciles: Deciles) -> None:
    growth = classify(series([100, 110, 121, 133.1], [10, 11, 12, 13]), deciles)
    assert growth.growth_decile == 7 and growth.growth_word == "High"
    assert growth.phase == "Mature Growth"

    stable = classify(series([100, 101, 102, 103], [10, 10, 10, 10]), deciles)
    assert stable.growth_decile == 4 and stable.growth_word == "Low"
    assert stable.phase == "Mature Stable"
    assert stable.years_used == 4 and stable.reason is None
    assert stable.dickinson == "Mature" and stable.checks == ()


def test_zero_margin_slope_negative_margin_is_young_growth(deciles: Deciles) -> None:
    ev = classify(series([100, 200, 400, 800], [-10, -20, -40, -80]), deciles)
    assert ev.margin == -0.1 and ev.margin_slope == 0.0
    assert ev.phase == "Young Growth"


def test_zero_margin_counts_positive_and_flags(deciles: Deciles) -> None:
    ev = classify(series([100, 110, 121, 133.1], [5, 3, 1, 0]), deciles)
    assert ev.margin == 0.0 and ev.phase == "Mature Growth"
    assert "margin-zero" in codes(ev)


def test_checks_never_change_phase(deciles: Deciles) -> None:
    ev = classify(series([100, 101, 102, 103], [-50, -40, -30, -20]), deciles)
    assert ev.growth_word == "Low" and ev.phase == "High Growth"
    assert (
        Flag(
            "growth-word-disagrees",
            "Growth word disagrees",
            'Revenue growth is "Low", which points to Mature Stable, '
            "while the margin rule gave High Growth.",
        )
        in ev.checks
    )


def test_margin_direction_and_its_check(deciles: Deciles) -> None:
    rising = classify(series([100, 101, 102, 103], [10, 12, 14, 16]), deciles)
    assert rising.margin_direction == "Rising" and rising.phase == "Mature Stable"
    assert "margin-direction-disagrees" in codes(rising)

    declining = classify(series([100, 101, 102, 103], [20, 15, 10, 5]), deciles)
    assert declining.margin_direction == "Declining" and declining.phase == "Mature Stable"
    assert "margin-direction-disagrees" in codes(declining)

    stable = classify(series([100, 101, 102, 103], [10, 10, 10, 10]), deciles)
    assert stable.margin_direction == "Stable"
    assert "margin-direction-disagrees" not in codes(stable)

    negative = classify(series([100, 101, 102, 103], [-50, -40, -30, -20]), deciles)
    assert negative.margin_direction is None


def test_margin_direction_needs_the_slope_sign(deciles: Deciles) -> None:
    falling_year = replace(deciles, margin_slope_edges=tuple(-k / 100 for k in range(9, 0, -1)))
    ev = classify(series([100, 101, 102, 103], [10, 10, 10, 10]), falling_year)
    assert ev.margin_slope is not None and ev.margin_slope < 0
    assert decile(ev.margin_slope, falling_year.margin_slope_edges) == 10
    assert ev.margin_direction == "Stable"

    rising_year = replace(deciles, margin_slope_edges=tuple(k / 100 for k in range(1, 10)))
    ev = classify(series([100, 101, 102, 103], [10, 10.2, 10.4, 10.6]), rising_year)
    assert ev.margin_slope is not None and ev.margin_slope > 0
    assert decile(ev.margin_slope, rising_year.margin_slope_edges) == 1
    assert ev.margin_direction == "Stable"


def test_fcf_sign_check(deciles: Deciles) -> None:
    revenue: list[float | None] = [100, 110, 121, 133.1]
    income: list[float | None] = [10, 11, 12, 13]
    negative = classify(series(revenue, income, cfo=10, capex=-20), deciles)
    assert negative.phase == "Mature Growth" and negative.fcf_sign == "negative"
    assert "fcf-sign" in codes(negative)

    positive = classify(series(revenue, income), deciles)
    assert positive.fcf_sign == "positive" and "fcf-sign" not in codes(positive)

    young = classify(series([100, 200, 400, 800], [-10, -20, -40, -80]), deciles)
    assert young.phase == "Young Growth" and young.fcf_sign == "positive"
    assert "fcf-sign" in codes(young)

    unknown = classify(series(revenue, income, capex=None), deciles)
    assert unknown.fcf_sign is None and "fcf-sign" not in codes(unknown)


def test_short_history_flagged_and_two_years_unclassified(deciles: Deciles) -> None:
    three = (fy(2023, 100, 10), fy(2024, 110, 12), fy(2025, 121, 14))
    ev = classify(three, deciles)
    assert ev.phase is not None and any(c.code == "short-history" for c in ev.checks)
    one = (fy(2025, 121, 14),)
    assert classify(one, deciles).phase is None
    assert classify(one, deciles).reason == "fewer than two fiscal years"

    two = classify((fy(2024, 110, 12), fy(2025, 121, 14)), deciles)
    assert two.phase == "Mature Growth" and two.growth_3y == pytest.approx(0.1)
    assert two.revenue_slope is None and two.margin_slope is None
    assert (
        Flag(
            "short-history",
            "Short history",
            "Only 2 fiscal years are on file; growth runs over the years that exist "
            "instead of three.",
        )
        in two.checks
    )

    empty = classify((), deciles)
    assert empty.phase is None and empty.years_used == 0
    assert empty.reason == "fewer than two fiscal years"


def test_missing_margin_years_are_skipped(deciles: Deciles) -> None:
    ev = classify(series([100, 110, 121, 133.1, 146.41], [10, None, 12, 13, None]), deciles)
    assert ev.margin == pytest.approx(13 / 133.1)
    assert ev.margin_slope is not None and ev.phase == "Mature Growth"

    too_few = classify(series([100, 110, 121, 133.1], [None, None, -12, -13]), deciles)
    assert too_few.margin_slope is None and too_few.margin_direction is None
    assert too_few.phase == "Young Growth"


def test_no_margin_at_all_is_unclassified(deciles: Deciles) -> None:
    ev = classify(series([100, 110, 121, 133.1], [None, None, None, None]), deciles)
    assert ev.phase is None and ev.reason == "no operating margin"
    assert ev.growth_word == "High" and ev.checks == ()


def test_currency_change_flagged(deciles: Deciles) -> None:
    s = (
        fy(2022, 100, 10, cur="USD"),
        fy(2023, 110, 11, cur="USD"),
        fy(2024, 121, 12, cur="EUR"),
        fy(2025, 133.1, 13, cur="EUR"),
    )
    ev = classify(s, deciles)
    assert ev.growth_3y == pytest.approx(0.1) and "currency-change" in codes(ev)
    same = classify(series([100, 110, 121, 133.1], [10, 11, 12, 13]), deciles)
    assert "currency-change" not in codes(same)


def test_compute_deciles_excludes_unmeasurable() -> None:
    series_a = series([100, 110, 121, 133.1], [10, 11, 12, 13])
    series_b = series([100, 150, 225, 337.5], [-10, -20, -30, -40])
    one_year_series = series([121], [14])
    d = compute_deciles({"A": series_a, "B": series_b, "C": one_year_series})
    assert d.n_growth == 2
    # statistics.quantiles(..., method="inclusive") over the two growths 0.1 and 0.5
    assert d.growth_edges == pytest.approx(tuple(0.1 + 0.04 * k for k in range(1, 10)))
    # only A has a positive last margin and a slope; one value gives no edges
    assert d.n_margin == 1 and d.margin_slope_edges == ()
    assert d.refresh_id is None

    startup = series([0, 10, 40, 120], [-5, -8, -9, -9])
    assert compute_deciles({"A": series_a, "S": startup}, refresh_id=7) == Deciles(
        growth_edges=(),
        margin_slope_edges=(),
        n_growth=1,
        n_margin=1,
        refresh_id=7,
    )


def test_dickinson() -> None:
    assert dickinson(fy(2025, 1, 1, cfo=-1, cfi=-1, cff=1)) == "Introduction"
    assert dickinson(fy(2025, 1, 1, cfo=1, cfi=-1, cff=1)) == "Growth"
    assert dickinson(fy(2025, 1, 1, cfo=1, cfi=-1, cff=-1)) == "Mature"
    assert dickinson(fy(2025, 1, 1, cfo=-1, cfi=1, cff=1)) == "Decline"
    assert dickinson(fy(2025, 1, 1, cfo=-1, cfi=1, cff=-1)) == "Decline"
    assert dickinson(fy(2025, 1, 1, cfo=1, cfi=1, cff=1)) == "Shake-out"
    assert dickinson(fy(2025, 1, 1, cfo=-1, cfi=-1, cff=-1)) == "Shake-out"
    assert dickinson(fy(2025, 1, 1, cfo=1, cfi=1, cff=-1)) == "Shake-out"
    assert dickinson(fy(2025, 1, 1, cfo=None)) is None
