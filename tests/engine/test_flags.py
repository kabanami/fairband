from dataclasses import replace
from datetime import date

import pytest

from fairband.engine.anchor import TrailingFigures
from fairband.engine.classifier import FiscalYear, Series
from fairband.engine.flags import (
    QUALITY_WARNINGS,
    flag_count,
    gate_flags,
    long_runway_flag,
    margin_flag,
    median_margin,
    nri_flag,
    value_spread_flag,
)
from fairband.engine.types import Flag
from fairband.policy import Policy, load_policy


@pytest.fixture
def policy() -> Policy:
    return load_policy()


def margins(points: list[float | None], revenue: float = 100.0) -> Series:
    """Fiscal years ending in 2025, oldest first, with the operating margin in percent points;
    ``None`` is a year with no operating income."""
    first = 2026 - len(points)
    return tuple(
        FiscalYear(
            year=first + i,
            period_end=date(first + i, 12, 31),
            currency="USD",
            revenue=revenue,
            operating_income=None if m is None else m * revenue / 100,
            cfo=None,
            cfi=None,
            cff=None,
            capex=None,
        )
        for i, m in enumerate(points)
    )


def test_margin_flag_labels(policy: Policy) -> None:
    cycle = margins([-5, 10, 12, 15, 15, 16, 18, 20, 20, 22])
    flag = margin_flag(cycle, 0.40, policy)
    assert flag is not None
    assert (flag.code, flag.word) == ("margin-flag", "Possible cycle peak")

    losses = margins([-30, -25, -20, -15, -10, -5, 2, 5])
    flag = margin_flag(losses, 0.10, policy)
    assert flag is not None
    assert (flag.code, flag.word) == ("margin-flag", "Newly profitable")

    steady = margins([20, 20, 20, 20, 20, 20, 20])
    flag = margin_flag(steady, 0.31, policy)
    assert flag is not None
    assert (flag.code, flag.word) == ("margin-flag", "Margin above history")

    assert margin_flag(margins([20, 20, 20, 20, 20]), 0.90, policy) is None


def test_margin_flag_above_high(policy: Policy) -> None:
    history = margins([24, 25, 26, 27, 28, 30])  # median 0.265: 1.5 times is 0.3975
    flag = margin_flag(history, 0.33, policy)
    assert flag == Flag(
        "margin-flag",
        "Margin above history",
        "The trailing operating margin is 33.0%, against a median of 26.5% and a high of "
        "30.0% over 6 fiscal years.",
    )
    assert margin_flag(history, 0.32, policy) is None


def test_margin_flag_by_median(policy: Policy) -> None:
    history = margins([10, 20, 25, 25, 30, 35])  # median 0.25; the high step is 0.385
    assert margin_flag(history, 0.375, policy) is not None
    assert margin_flag(history, 0.37, policy) is None


def test_margin_flag_sentence_names_the_loss_year(policy: Policy) -> None:
    flag = margin_flag(margins([-5, 10, 12, 15, 15, 16, 18, 20, 20, 22]), 0.40, policy)
    assert flag is not None
    assert flag.sentence == (
        "The trailing operating margin is 40.0%, against a median of 15.5% and a high of "
        "22.0% over 10 fiscal years; the window holds a loss year."
    )


def test_margin_flag_window_is_the_last_ten_years(policy: Policy) -> None:
    # The loss year is the eleventh from the end: outside the window, so no cycle-peak word.
    flag = margin_flag(margins([-5, 10, 12, 15, 15, 16, 18, 20, 20, 22, 22]), 0.40, policy)
    assert flag is not None and flag.word == "Margin above history"


def test_margin_flag_skips_years_without_a_margin(policy: Policy) -> None:
    # Six years on file, one without operating income: five margins, below the minimum of six.
    assert margin_flag(margins([20, None, 20, 20, 20, 20]), 0.90, policy) is None
    # A zero revenue gives no margin either.
    zero_revenue = margins([20, 20, 20, 20, 20, 20])
    zero_revenue = (replace(zero_revenue[0], revenue=0.0), *zero_revenue[1:])
    assert margin_flag(zero_revenue, 0.90, policy) is None


def test_margin_flag_needs_a_trailing_margin(policy: Policy) -> None:
    assert margin_flag(margins([20, 20, 20, 20, 20, 20]), None, policy) is None


def test_margin_flag_below_a_negative_high(policy: Policy) -> None:
    # Every margin negative: -10.5% is not above the high of -10%, and the median of -17.5%
    # cannot fire.
    assert margin_flag(margins([-40, -30, -20, -15, -12, -10]), -0.105, policy) is None


def test_margin_flag_losses_turned_profitable(policy: Policy) -> None:
    # mech/1.2's case: a loss-making history, then a positive trailing margin.
    flag = margin_flag(margins([-30, -25, -20, -15, -12, -10]), 0.05, policy)
    assert flag is not None
    assert (flag.code, flag.word) == ("margin-flag", "Newly profitable")
    assert flag.sentence == (
        "The trailing operating margin is 5.0%, against a median of -17.5% and a high of "
        "-10.0% over 6 fiscal years; the window holds a loss year."
    )


def test_margin_flag_high_of_zero(policy: Policy) -> None:
    flag = margin_flag(margins([-20, -15, -10, -5, -2, 0]), 0.01, policy)
    assert flag is not None and flag.word == "Newly profitable"
    assert margin_flag(margins([-20, -15, -10, -5, -2, 0]), 0.0, policy) is None


def test_median_margin_is_the_margin_flags_median(policy: Policy) -> None:
    # the last ten years that have a margin; a year with no operating income is skipped
    history = margins([90, None, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    assert median_margin(history) == pytest.approx(0.55)
    assert median_margin(history, window=3) == pytest.approx(0.90)
    flag = margin_flag(history, 1.50, policy)
    assert flag is not None and "median of 55.0%" in flag.sentence
    assert median_margin(margins([None, None])) is None
    assert median_margin(()) is None


def trailing(
    cfo: float | None = 100.0,
    capex: float | None = -30.0,
    equity_issued: float | None = 0.0,
) -> TrailingFigures:
    return TrailingFigures(
        period_end=date(2026, 6, 30),
        quarters=4,
        on_fiscal_year=False,
        revenue=500.0,
        operating_income=None,
        net_income=None,
        eps_diluted=None,
        sbc=None,
        cfo=cfo,
        capex=capex,
        dividends=None,
        buybacks=None,
        equity_issued=equity_issued,
    )


def gate_codes(t: TrailingFigures, market_cap: float | None, policy: Policy) -> list[str]:
    return [f.code for f in gate_flags(t, market_cap, policy)]


def test_gate_flags(policy: Policy) -> None:
    assert gate_codes(trailing(), 1000.0, policy) == []
    assert gate_codes(trailing(capex=-60.0, equity_issued=20.0), 1000.0, policy) == [
        "equity-raise",
        "heavy-capex",
    ]
    assert gate_codes(trailing(capex=-120.0), 1000.0, policy) == ["negative-fcf", "heavy-capex"]
    # A negative operating cash flow is negative free cash flow but not heavy capex.
    assert gate_codes(trailing(cfo=-10.0, capex=-5.0), 1000.0, policy) == ["negative-fcf"]


def test_gate_flags_boundaries(policy: Policy) -> None:
    # Issuance at exactly 1% of the market cap is a raise; capex at exactly 50% of OCF is not heavy.
    assert gate_codes(trailing(equity_issued=10.0), 1000.0, policy) == ["equity-raise"]
    assert gate_codes(trailing(capex=-50.0), 1000.0, policy) == []
    assert gate_codes(trailing(cfo=50.0, capex=-50.0), 1000.0, policy) == ["heavy-capex"]


def test_gate_flags_missing_inputs(policy: Policy) -> None:
    raise_ = trailing(equity_issued=20.0)
    assert gate_codes(raise_, None, policy) == []
    assert gate_codes(raise_, 0.0, policy) == []
    assert gate_codes(trailing(equity_issued=None), 1000.0, policy) == []
    assert gate_codes(trailing(cfo=None, capex=-120.0), 1000.0, policy) == []
    assert gate_codes(trailing(cfo=-10.0, capex=None), 1000.0, policy) == []


def test_gate_flag_words_and_sentences(policy: Policy) -> None:
    flags = gate_flags(trailing(capex=-120.0, equity_issued=15.0), 1000.0, policy)
    assert flags == (
        Flag(
            "equity-raise",
            "Equity raise",
            "Trailing stock issuance is 1.5% of the market cap, at or above the 1.0% that "
            "counts as a raise.",
        ),
        Flag(
            "negative-fcf",
            "Negative free cash flow",
            "Trailing operating cash flow of 100 less capital spending of 120 leaves a free "
            "cash flow of -20.",
        ),
        Flag(
            "heavy-capex",
            "Heavy capex",
            "Trailing capital spending is 120.0% of operating cash flow, above 50.0%.",
        ),
    )


def test_nri_flag(policy: Policy) -> None:
    flag = nri_flag(0.6, 10.0, policy)
    assert flag == Flag(
        "large-nri",
        "Large non-recurring item",
        "The non-recurring gap of 0.60 per share is 6.0% of trailing EPS of 10.00, at or above "
        "5.0%.",
    )
    assert nri_flag(-0.6, 10.0, policy) is not None
    assert nri_flag(0.6, -10.0, policy) is not None
    assert nri_flag(0.5, 10.0, policy) is not None  # exactly 5% fires
    assert nri_flag(0.4, 10.0, policy) is None
    assert nri_flag(0.6, 0.0, policy) is None
    assert nri_flag(None, 10.0, policy) is None
    assert nri_flag(0.6, None, policy) is None


def test_long_runway_flag(policy: Policy) -> None:
    flag = long_runway_flag(20, 0.10, None, policy)
    assert flag == Flag(
        "long-runway-high-growth",
        "Long runway, high growth",
        "The runway is 20 years and the growth belief is 10.0%, at or above 10.0%.",
    )
    flag = long_runway_flag(20, 0.06, 0.12, policy)
    assert flag is not None
    assert flag.sentence == (
        "The runway is 20 years and the implied growth is 12.0%, at or above 10.0%."
    )
    flag = long_runway_flag(20, 0.11, 0.12, policy)
    assert flag is not None
    assert flag.sentence == (
        "The runway is 20 years and the growth belief is 11.0% and the implied growth is "
        "12.0%, at or above 10.0%."
    )
    assert long_runway_flag(20, 0.06, None, policy) is None
    assert long_runway_flag(20, 0.06, 0.09, policy) is None
    assert long_runway_flag(10, 0.15, 0.15, policy) is None


def test_value_spread_flag(policy: Policy) -> None:
    flag = value_spread_flag([100.0, 131.0], policy)
    assert flag == Flag(
        "value-spread",
        "Value spread",
        "The value ranges from 100.00 to 131.00 across the ROIC values or runways tested, "
        "a spread of 31.0%, at or above 30.0%.",
    )
    assert value_spread_flag([100.0, 129.0], policy) is None
    assert value_spread_flag([115.0, 100.0, 130.0], policy) is not None  # exactly 30% fires


def test_value_spread_flag_needs_two_positive_values(policy: Policy) -> None:
    assert value_spread_flag([100.0, None, 131.0], policy) is not None
    assert value_spread_flag([100.0, None], policy) is None
    assert value_spread_flag([], policy) is None
    assert value_spread_flag([0.0, 131.0], policy) is None
    assert value_spread_flag([-10.0, 131.0], policy) is None


def test_flag_count_counts_the_eleven_quality_warnings_only() -> None:
    flags = (
        Flag("leases-not-on-balance-sheet", "", ""),
        Flag("few-analysts", "", ""),
        Flag("margin-direction-disagrees", "", ""),
        Flag("line-not-presented:cash", "", ""),
    )
    assert flag_count(flags) == 0
    assert flag_count(flags + (Flag("large-nri", "", ""), Flag("value-spread", "", ""))) == 2
    assert QUALITY_WARNINGS == frozenset(
        {
            "large-nri",
            "value-spread",
            "margin-flag",
            "z-distress",
            "f-score-low",
            "reinvesting-in-decline",
            "equity-raise",
            "negative-fcf",
            "heavy-capex",
            "burn-cover-short",
            "consensus-recovery",
        }
    )
