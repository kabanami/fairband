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
    established,
    falling_steps,
    growth_3y,
    is_startup,
    operating_margin,
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


def sentence(ev: PhaseEvidence, code: str) -> str:
    return next(c.sentence for c in ev.checks if c.code == code)


@pytest.fixture
def deciles() -> Deciles:
    return Deciles(
        growth_edges=(-0.10, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.30),
        margin_slope_edges=(-0.03, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 0.03),
        n_growth=100,
        n_margin=80,
        refresh_id=1,
    )


def bottom_word(deciles: Deciles) -> Deciles:
    """The fixture with its second growth edge at -4% instead of -5%, so growth of -4.4% and
    -4.9% (spec 13.4's falling revenues) read "Close to zero or negative" instead of "Low"."""
    return replace(deciles, growth_edges=(-0.10, -0.04, *deciles.growth_edges[2:]))


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
    assert growth_3y(series([100, None, None, 133.1], ones[:4])) == pytest.approx(0.1)
    assert growth_3y(series([100, 110, 121], ones[:3])) == pytest.approx(0.1)
    assert growth_3y(series([100, 121], ones[:2])) == pytest.approx(0.21)
    assert growth_3y(series([121], ones[:1])) is None
    # a missing, zero or negative first year falls back to the run of positive revenues
    assert growth_3y(series([None, 110, 121, 133.1], ones[:4])) == pytest.approx(0.1)
    assert growth_3y(series([None, None, 121, 133.1], ones[:4])) == pytest.approx(0.1)
    assert growth_3y(series([-5, 110, 121, 133.1], ones[:4])) == pytest.approx(0.1)
    assert growth_3y(series([0, 110, 121], ones[:3])) == pytest.approx(0.1)
    assert growth_3y(series([None, 110, None, 133.1], ones[:4])) is None
    assert growth_3y(series([None, 121], ones[:2])) is None
    # the last year missing or negative, and a Start-up, have no growth
    assert growth_3y(series([100, 110, 121, None], ones[:4])) is None
    assert growth_3y(series([100, -5], ones[:2])) is None
    assert growth_3y(series([0, 10, 40, 120], ones[:4])) is None
    assert growth_3y(series([10, 20, 0], ones[:3])) is None


def test_is_startup() -> None:
    losses: list[float | None] = [-5, -5, -5, -5]
    assert is_startup(series([10, 20, 30, 0], losses))
    assert is_startup(series([0, 10, 40, 120], losses))
    assert not is_startup(series([0, 10, 40], losses[:3]))  # no year three years back
    assert not is_startup(series([None, 10, 40, 120], losses))  # unknown is not zero


def test_startup_when_revenue_zero_three_years_ago(deciles: Deciles) -> None:
    s = (fy(2022, 0, -5), fy(2023, 10, -8), fy(2024, 40, -9), fy(2025, 120, -9))
    assert classify(s, deciles).phase == "Start-up"


def test_an_established_company_is_never_a_start_up(deciles: Deciles) -> None:
    # spec 2026-11-06 13.4: revenue zero in 2022, three years back, then three years at 10%
    s = series([0, 100, 120, 150], [-5, 10, 12, 15])
    assert is_startup(s) and established(s) == (True, 3, 3)
    ev = classify(s, deciles)
    assert ev.growth_3y == pytest.approx(1.5**0.5 - 1) and ev.growth_word == "Very High"
    assert ev.phase == "Mature Growth" and ev.margin_direction == "Stable"
    assert ev.checks == (
        Flag(
            "revenue-gap",
            "Revenue gap",
            "Revenue was zero in fiscal 2022, but the margin was above zero in 3 of the last "
            "five fiscal years and in 3 of the 4 on file, so the company is not a Start-up.",
        ),
        Flag(
            "short-history",
            "Short history",
            "Only 4 fiscal years are on file, so the trends cover fewer than five years; "
            "revenue for fiscal 2022 is zero, so growth runs from fiscal 2023 to 2025 instead "
            "of over three years.",
        ),
    )


def test_a_non_established_company_with_zero_revenue_now_is_a_start_up(deciles: Deciles) -> None:
    s = series([100, 80, 50, 0], [-5, -8, -9, -9])
    assert established(s) == (False, 0, 0)
    ev = classify(s, deciles)
    assert ev.phase == "Start-up" and ev.reason is None and ev.growth_3y is None
    assert "revenue-gap" not in codes(ev)


def test_an_established_company_with_zero_revenue_now_is_unclassified(deciles: Deciles) -> None:
    # four profitable years, then a reported zero: no positive run ends at the last year
    s = series([100, 110, 120, 130, 0], [10, 11, 12, 13, -2])
    assert is_startup(s) and established(s) == (True, 4, 4)
    ev = classify(s, deciles)
    assert ev.phase is None and ev.reason == "no measurable revenue growth"
    assert ev.checks == ()
    assert (ev.positive_years_last_five, ev.positive_years_on_file) == (None, None)  # a data gap


def test_an_established_company_past_the_start_up_rule_can_be_decline(deciles: Deciles) -> None:
    # revenue zero in 2022, three years back, after a profitable 2021; three falls in four steps
    s = series([200, 0, 150, 120, 100], [20, -5, 15, 12, 10])
    assert is_startup(s) and established(s) == (True, 4, 4) and falling_steps(s) == (3, 4)
    ev = classify(s, deciles)
    assert ev.growth_3y == pytest.approx((100 / 150) ** 0.5 - 1)
    assert ev.growth_word == "Close to zero or negative"
    assert ev.revenue_slope == pytest.approx(-8.0)
    assert ev.phase == "Decline"
    assert sentence(ev, "revenue-gap") == (
        "Revenue was zero in fiscal 2022, but the margin was above zero in 4 of the last five "
        "fiscal years and in 4 of the 5 on file, so the company is not a Start-up."
    )
    assert sentence(ev, "short-history") == (
        "Revenue for fiscal 2022 is zero, so growth runs from fiscal 2023 to 2025 instead of "
        "over three years."
    )


def test_zero_first_revenue_in_a_short_series_falls_back(deciles: Deciles) -> None:
    ev = classify(series([0, 110, 121], [-5, -8, -9]), deciles)
    assert ev.phase == "Young Growth" and ev.growth_3y == pytest.approx(0.1)
    assert (
        Flag(
            "short-history",
            "Short history",
            "Only 3 fiscal years are on file, so the trends cover fewer than five years; "
            "growth runs from fiscal 2024 to 2025 instead of over three years.",
        )
        in ev.checks
    )


def test_missing_last_revenue_is_unclassified(deciles: Deciles) -> None:
    ev = classify(series([100, 110, 121, None], [10, 11, 12, 13]), deciles)
    assert ev.phase is None and ev.reason == "no revenue for the last fiscal year"
    # a zero three years back does not make it a Start-up when the last year is missing
    ev = classify(series([0, 110, 121, None], [-5, -8, -9, -9]), deciles)
    assert ev.phase is None and ev.reason == "no revenue for the last fiscal year"


def test_missing_revenue_three_years_back_falls_back(deciles: Deciles) -> None:
    ev = classify(series([100, None, 110, 121, 133.1], [10, 10, 11, 12, 13]), deciles)
    assert ev.growth_3y == pytest.approx(0.1) and ev.phase == "Mature Growth"
    assert (
        Flag(
            "short-history",
            "Short history",
            "Revenue for fiscal 2022 is missing or negative, so growth runs from fiscal 2023 "
            "to 2025 instead of over three years.",
        )
        in ev.checks
    )

    gap = classify(series([100, None, 110, None, 133.1], [10, 10, 11, 12, 13]), deciles)
    assert gap.phase is None and gap.reason == "no measurable revenue growth"


def test_negative_revenue(deciles: Deciles) -> None:
    last = classify(series([100, 110, 121, -5], [10, 11, 12, 13]), deciles)
    assert last.phase is None and last.reason == "negative revenue"

    first = classify(series([-5, 110, 121, 133.1], [10, 11, 12, 13]), deciles)
    assert first.growth_3y == pytest.approx(0.1) and first.phase == "Mature Growth"
    assert "short-history" in codes(first)
    assert first.margin_slope is not None and first.margin_slope < 0  # -5's margin skipped

    no_run = classify(series([-5, 110, -3, 133.1], [10, 11, 12, 13]), deciles)
    assert no_run.phase is None and no_run.reason == "no measurable revenue growth"


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


def test_decline_needs_three_falling_steps(deciles: Deciles) -> None:
    four = series([100, 95, 90, 86, 83], [10, 10, 10, 10, 10])
    assert falling_steps(four) == (4, 4)
    ev = classify(four, bottom_word(deciles))
    assert ev.growth_word == "Close to zero or negative"
    assert ev.revenue_slope is not None and ev.revenue_slope < 0
    assert ev.phase == "Decline" and "revenue-falling" not in codes(ev)

    three = series([100, 95, 90, 91, 83], [10, 10, 10, 10, 10])
    assert falling_steps(three) == (3, 4)
    assert classify(three, bottom_word(deciles)).phase == "Decline"

    two = series([100, 101, 95, 96, 83], [10, 10, 10, 10, 10])
    assert falling_steps(two) == (2, 4)
    ev = classify(two, deciles)
    assert ev.growth_word == "Close to zero or negative"
    assert ev.revenue_slope is not None and ev.revenue_slope < 0
    assert ev.phase == "Mature Stable" and "revenue-falling" in codes(ev)


def test_one_falling_step_is_not_decline_and_is_flagged(deciles: Deciles) -> None:
    s = series([100, 120, 80, 82, 84], [10, 12, 8, 8.2, 8.4])
    assert falling_steps(s) == (1, 4)
    ev = classify(s, deciles)
    assert ev.growth_word == "Close to zero or negative"
    assert ev.revenue_slope is not None and ev.revenue_slope < 0
    assert ev.margin is not None and ev.margin > 0
    assert ev.phase == "Mature Stable"
    assert ev.checks == (
        Flag(
            "revenue-falling",
            "Revenue falling",
            "Revenue fell in 1 of the last four fiscal years with a falling five-year trend; "
            "the Decline rule needs three.",
        ),
    )


def test_three_steps_all_falling_is_decline(deciles: Deciles) -> None:
    s = series([100, 95, 90, 86], [10, 10, 10, 10])
    assert falling_steps(s) == (3, 3)
    ev = classify(s, bottom_word(deciles))
    assert ev.growth_word == "Close to zero or negative" and ev.phase == "Decline"


def test_two_steps_on_file_cannot_make_decline(deciles: Deciles) -> None:
    short = series([100, 90, 80], [10, 9, 8])
    assert falling_steps(short) == (2, 2)
    ev = classify(short, deciles)
    assert ev.growth_word == "Close to zero or negative"
    assert ev.revenue_slope is not None and ev.revenue_slope < 0
    assert ev.phase == "Mature Stable"
    assert (
        Flag(
            "revenue-falling",
            "Revenue falling",
            "Revenue fell in 2 of the last four fiscal years with a falling five-year trend; "
            "the Decline rule needs three.",
        )
        in ev.checks
    )

    # a step with a missing year is no step: five years on file, two steps
    gap = series([100, 95, None, 86, 83], [10, 10, 10, 10, 10])
    assert falling_steps(gap) == (2, 2)
    ev = classify(gap, bottom_word(deciles))
    assert ev.growth_word == "Close to zero or negative"
    assert ev.revenue_slope is not None and ev.revenue_slope < 0
    assert ev.phase == "Mature Stable" and "revenue-falling" in codes(ev)


def test_decline_comes_before_the_established_rule(deciles: Deciles) -> None:
    # margins 4%, 4%, 3%, 2%, -1% on four falling steps
    s = series([100, 95, 90, 85, 80], [4, 3.8, 2.7, 1.7, -0.8])
    assert established(s) == (True, 4, 4) and falling_steps(s) == (4, 4)
    ev = classify(s, deciles)
    assert ev.growth_word == "Close to zero or negative"
    assert ev.margin is not None and ev.margin < 0
    assert ev.phase == "Decline"
    assert "loss-year" not in codes(ev) and "growth-word-disagrees" not in codes(ev)


def test_young_vs_high_growth_by_margin_slope(deciles: Deciles) -> None:
    revenue: list[float | None] = [100, 150, 225, 337.5, 506.25]
    young = classify(series(revenue, [-10, -20, -40, -80, -200]), deciles)
    assert young.growth_word == "Very High"
    assert young.margin_slope is not None and young.margin_slope < 0
    assert young.phase == "Young Growth"

    high = classify(series(revenue, [-50, -60, -70, -60, -40]), deciles)
    assert high.margin_slope is not None and high.margin_slope > 0
    assert high.phase == "High Growth"


def loss_year(year: int, n5: int, on_file: int, years: int) -> Flag:
    return Flag(
        "loss-year",
        "Loss year",
        f"The operating margin is negative in fiscal {year} after a positive margin in {n5} of "
        f"the last five fiscal years and in {on_file} of the {years} on file; the phase follows "
        "the growth word.",
    )


def test_an_established_company_with_a_loss_year_follows_its_growth_word(
    deciles: Deciles,
) -> None:
    # margins 4%, 4%, 3%, 2%, -1%
    s = series([100, 105, 110, 115, 120], [4, 4.2, 3.3, 2.3, -1.2])
    assert established(s) == (True, 4, 4)
    ev = classify(s, deciles)
    assert ev.growth_word == "Moderate" and ev.margin == pytest.approx(-0.01)
    assert ev.phase == "Mature Growth"
    assert (ev.positive_years_last_five, ev.positive_years_on_file) == (4, 4)
    assert ev.checks == (loss_year(2025, 4, 4, 5),)
    assert ev.checks[0].sentence == (
        "The operating margin is negative in fiscal 2025 after a positive margin in 4 of the "
        "last five fiscal years and in 4 of the 5 on file; the phase follows the growth word."
    )


def test_an_established_company_with_a_low_growth_word_is_mature_stable(
    deciles: Deciles,
) -> None:
    ev = classify(series([100, 100, 100, 100, 100], [4, 4, 3, 2, -1]), deciles)
    assert ev.growth_word == "Low" and ev.margin == pytest.approx(-0.01)
    assert ev.phase == "Mature Stable"
    assert ev.checks == (loss_year(2025, 4, 4, 5),)


def test_a_pre_profit_company_keeps_the_margin_trend_rule(deciles: Deciles) -> None:
    revenue: list[float | None] = [100, 105, 110, 115, 120]  # "Moderate"
    # margins -5%, -4%, -3%, 1%, -1%: one positive year, an improving trend
    rising = series(revenue, [-5, -4.2, -3.3, 1.15, -1.2])
    assert established(rising) == (False, 1, 1)
    ev = classify(rising, deciles)
    assert ev.margin_slope is not None and ev.margin_slope > 0
    assert ev.phase == "High Growth" and "loss-year" not in codes(ev)
    assert (
        Flag(
            "growth-word-disagrees",
            "Growth word disagrees",
            'Revenue growth is "Moderate", which points to Mature Growth, '
            "while the margin rule gave High Growth.",
        )
        in ev.checks
    )

    # margins -1%, 1%, -3%, -4%, -5%: one positive year, a worsening trend
    falling = series(revenue, [-1, 1.05, -3.3, -4.6, -6])
    assert established(falling) == (False, 1, 1)
    ev = classify(falling, deciles)
    assert ev.margin_slope is not None and ev.margin_slope < 0
    assert ev.phase == "Young Growth" and "loss-year" not in codes(ev)
    assert "growth-word-disagrees" in codes(ev)


def test_exactly_three_positive_years_is_established(deciles: Deciles) -> None:
    flat: list[float | None] = [100, 100, 100, 100, 100]
    three = series(flat, [4, 3, -2, 2, -1])
    assert established(three) == (True, 3, 3)
    ev = classify(three, deciles)
    assert ev.phase == "Mature Stable" and loss_year(2025, 3, 3, 5) in ev.checks

    two = series(flat, [4, -3, -2, 2, -1])
    assert established(two) == (False, 2, 2)
    ev = classify(two, deciles)
    assert ev.phase == "Young Growth" and "loss-year" not in codes(ev)

    # a margin of exactly zero is not above zero
    assert established(series(flat, [4, 0, -2, 2, -1])) == (False, 2, 2)
    # the 2019 and 2020 profits are outside the last five fiscal years, and four profitable
    # years on file are fewer than five
    seven: list[float | None] = [100, 100, 100, 100, 100, 100, 100]
    assert established(series(seven, [4, 4, 4, -2, -2, 2, -1])) == (False, 2, 4)


def test_a_year_without_a_margin_counts_for_nothing(deciles: Deciles) -> None:
    flat: list[float | None] = [100, 100, 100, 100, 100]
    s = series(flat, [5, None, 5, 5, -1])  # 3 positive among the four with a margin
    assert established(s) == (True, 3, 3)
    ev = classify(s, deciles)
    assert ev.phase == "Mature Stable" and loss_year(2025, 3, 3, 5) in ev.checks

    assert established(series(flat, [5, None, None, 5, -1])) == (False, 2, 2)

    # the flag names the year of the deciding margin, the last of the five that has one
    ev = classify(series(flat, [5, 5, 5, -1, None]), deciles)
    assert ev.phase == "Mature Stable" and loss_year(2024, 3, 3, 5) in ev.checks


def test_five_profitable_years_on_file_make_an_established_company(deciles: Deciles) -> None:
    # spec 2026-11-06 13.4: eleven years, a 5% margin six times and then -5% five times
    flat: list[float | None] = [100] * 11
    s = series(flat, [5, 5, 5, 5, 5, 5, -5, -5, -5, -5, -5])
    assert established(s) == (True, 0, 6)
    ev = classify(s, deciles)
    assert ev.growth_word == "Low" and ev.phase == "Mature Stable"
    assert (ev.positive_years_last_five, ev.positive_years_on_file) == (0, 6)
    assert ev.checks == (loss_year(2025, 0, 6, 11),)
    assert "0 of the last five fiscal years and in 6 of the 11 on file" in sentence(ev, "loss-year")


def test_four_profitable_years_on_file_are_not_established(deciles: Deciles) -> None:
    flat: list[float | None] = [100] * 11
    s = series(flat, [5, 5, 5, 5, -5, -5, -5, -5, -5, -5, -5])
    assert established(s) == (False, 0, 4)
    ev = classify(s, deciles)
    assert ev.margin_slope == 0.0 and ev.phase == "Young Growth"  # rule 4b, no improving trend
    assert (ev.positive_years_last_five, ev.positive_years_on_file) == (0, 4)
    assert "loss-year" not in codes(ev)


def test_growth_word_disagrees_is_silent_under_the_established_rule(deciles: Deciles) -> None:
    # "Very High" growth points to Young Growth; margins 4%, 4%, 3%, 2%, -1%
    s = series([100, 125, 156.25, 195.3125, 244.140625], [4, 5, 4.6875, 3.90625, -2.44140625])
    ev = classify(s, deciles)
    assert ev.growth_word == "Very High" and ev.phase == "Mature Growth"
    assert "growth-word-disagrees" not in codes(ev)
    assert ev.checks == (loss_year(2025, 4, 4, 5),)


def test_mature_growth_vs_stable_by_growth_word(deciles: Deciles) -> None:
    growth = classify(series([100, 110, 121, 133.1], [10, 11, 12, 13]), deciles)
    assert growth.growth_decile == 7 and growth.growth_word == "High"
    assert growth.phase == "Mature Growth"

    stable = classify(series([100, 100, 101, 102, 103], [10, 10, 10, 10, 10]), deciles)
    assert stable.growth_decile == 4 and stable.growth_word == "Low"
    assert stable.phase == "Mature Stable"
    assert stable.years_used == 5 and stable.reason is None
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
    rising = classify(series([100, 101, 102, 103], [10, 13, 16, 19]), deciles)
    assert rising.margin_slope is not None
    assert decile(rising.margin_slope, deciles.margin_slope_edges) == 9
    assert rising.margin_direction == "Rising" and rising.phase == "Mature Stable"
    assert "margin-direction-disagrees" in codes(rising)

    declining = classify(series([100, 101, 102, 103], [20, 15, 10, 5]), deciles)
    assert declining.margin_direction == "Declining" and declining.phase == "Mature Stable"
    assert "margin-direction-disagrees" in codes(declining)

    stable = classify(series([100, 101, 102, 103], [10, 10, 10, 10]), deciles)
    assert stable.margin_direction == "Stable" and stable.phase == "Mature Stable"
    assert "margin-direction-disagrees" not in codes(stable)

    negative = classify(series([100, 101, 102, 103], [-50, -40, -30, -20]), deciles)
    assert negative.margin_direction is None


def test_margin_direction_needs_the_slope_sign(deciles: Deciles) -> None:
    # a slope below zero in decile 9 (eight edges below it, the ninth at zero) is not Rising
    falling_year = replace(deciles, margin_slope_edges=(*(-k / 100 for k in range(9, 1, -1)), 0.0))
    ev = classify(series([100, 101, 102, 103], [10, 10, 10, 10]), falling_year)
    assert ev.margin_slope is not None and ev.margin_slope < 0
    assert decile(ev.margin_slope, falling_year.margin_slope_edges) == 9
    assert ev.margin_direction == "Stable"

    # a slope above zero in decile 2 (the first edge at zero, the rest above it) is not Declining
    rising_year = replace(deciles, margin_slope_edges=(0.0, *(k / 100 for k in range(2, 10))))
    ev = classify(series([100, 101, 102, 103], [10, 10.2, 10.4, 10.6]), rising_year)
    assert ev.margin_slope is not None and ev.margin_slope > 0
    assert decile(ev.margin_slope, rising_year.margin_slope_edges) == 2
    assert ev.margin_direction == "Stable"


@pytest.mark.parametrize(
    ("income", "slope_decile", "direction"),
    [
        ([10, 12.5, 15, 17.5], 9, "Rising"),
        ([10, 11.5, 13, 14.5], 8, "Stable"),
        ([20, 17.5, 15, 12.5], 2, "Declining"),
        ([20, 18.5, 17, 15.5], 3, "Stable"),
    ],
)
def test_margin_direction_reads_deciles_nine_and_two(
    deciles: Deciles, income: list[float | None], slope_decile: int, direction: str
) -> None:
    # spec 2026-11-06 13.4: margin slopes of +2.5, +1.5, -2.5 and -1.5 points a year
    ev = classify(series([100, 100, 100, 100], income), deciles)
    assert ev.margin_slope is not None
    assert decile(ev.margin_slope, deciles.margin_slope_edges) == slope_decile
    assert ev.margin_direction == direction


def test_stable_points_nowhere(deciles: Deciles) -> None:
    # "High" growth at a flat 10% margin: Mature Growth, Stable, no check
    growth = classify(series([100, 110, 120, 130], [10, 11, 12, 13]), deciles)
    assert growth.phase == "Mature Growth" and growth.margin_direction == "Stable"
    assert "margin-direction-disagrees" not in codes(growth)

    # four falls at a flat 10% margin: Decline, Stable, no check
    decline = classify(series([100, 95, 90, 85, 80], [10, 9.5, 9, 8.5, 8]), deciles)
    assert decline.phase == "Decline" and decline.margin_direction == "Stable"
    assert "margin-direction-disagrees" not in codes(decline)

    # flat revenue with the margin up 2.5 points a year: Mature Stable, Rising, the check
    rising = classify(series([100, 100, 100, 100], [10, 12.5, 15, 17.5]), deciles)
    assert rising.phase == "Mature Stable" and rising.margin_direction == "Rising"
    assert (
        Flag(
            "margin-direction-disagrees",
            "Margin direction disagrees",
            'The operating margin trend is "Rising", which points to Mature Growth, '
            "while the rules gave Mature Stable.",
        )
        in rising.checks
    )


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
            "Only 2 fiscal years are on file, so the trends cover fewer than five years; "
            "growth runs from fiscal 2024 to 2025 instead of over three years.",
        )
        in two.checks
    )

    four = classify(series([100, 110, 121, 133.1], [10, 11, 12, 13]), deciles)
    assert (
        Flag(
            "short-history",
            "Short history",
            "Only 4 fiscal years are on file, so the trends cover fewer than five years.",
        )
        in four.checks
    )
    five = classify(series([100, 100, 110, 121, 133.1], [10, 10, 11, 12, 13]), deciles)
    assert "short-history" not in codes(five)

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


def test_trend_keeps_the_year_index_across_gaps(deciles: Deciles) -> None:
    # 2021-2025 margins -10%, -20%, none, none, -11%: on the year index (0, 1, 4) the trend
    # improves; packed together as 0, 1, 2 the same three values would worsen
    ev = classify(series([100, 100, 100, 100, 100], [-10, -20, None, None, -11]), deciles)
    assert ev.margin_slope == pytest.approx(0.005)
    assert ev.phase == "High Growth"


def test_margin_lookback_stops_at_five_years(deciles: Deciles) -> None:
    revenue: list[float | None] = [100 * 1.1**k for k in range(9)]  # 2017 to 2025
    income: list[float | None] = [10, None, None, None, None, None, None, None, None]
    ev = classify(series(revenue, income), deciles)
    assert ev.phase is None and ev.reason == "no operating margin" and ev.margin is None


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

    # an unclassifiable series stays out of the margin ranking even with a margin trend
    no_last_revenue = series([100, 110, 121, 133.1, None], [10, 11, 12, 13, 14])
    assert compute_deciles({"A": series_a, "G": no_last_revenue}).n_margin == 1

    # a Start-up with a margin trend, and a series with no margin, stay out of both rankings
    startup_with_margin = series([0, 100, 110, 121], [-5, 10, 11, 12])
    no_margin = series([100, 110, 121, 133.1], [None, None, None, None])
    d = compute_deciles({"A": series_a, "S": startup_with_margin, "M": no_margin})
    assert d.n_growth == 1 and d.n_margin == 1

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


def test_operating_margin() -> None:
    assert operating_margin(fy(2025, 200, 50)) == 0.25
    assert operating_margin(fy(2025, 200, -50)) == -0.25
    assert operating_margin(fy(2025, None, 50)) is None
    assert operating_margin(fy(2025, 200, None)) is None
    assert operating_margin(fy(2025, 0, 50)) is None  # a zero revenue cannot be divided
