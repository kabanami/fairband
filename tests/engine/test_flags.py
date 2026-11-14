import math
from dataclasses import replace
from datetime import date

import pytest

from fairband.engine.anchor import SbcBasis, StockPayHistory, TrailingFigures
from fairband.engine.classifier import FiscalYear, Series
from fairband.engine.flags import (
    QUALITY_WARNINGS,
    basis_unknown_flag,
    flag_count,
    gate_flags,
    long_runway_flag,
    margin_flag,
    margin_history,
    median_margin,
    nri_flag,
    sbc_basis_uncertain_flag,
    share_count_flag,
    stock_pay_missing_flag,
    value_spread_flag,
)
from fairband.engine.roic import Used
from fairband.engine.route import CompanyInputs
from fairband.engine.route_steps import RoicTerms, trailing_flags
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


def test_margin_history_is_the_median_of_the_last_ten_years() -> None:
    nets = [1.0, 2.0, 3.0, None]
    four = tuple(
        replace(fy, net_income=n) for fy, n in zip(margins([10, 20, 30, 40]), nets, strict=True)
    )
    assert margin_history(four) == {
        "operating": {"median": pytest.approx(0.25), "years": 4},
        "net": {"median": pytest.approx(0.02), "years": 3},
    }
    # twelve years: the oldest two, 90% and 80%, are outside the window; no net income on file
    twelve = margins([90, 80, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert margin_history(twelve) == {"operating": {"median": pytest.approx(0.055), "years": 10}}
    # a year with no revenue above zero is skipped
    dead = replace(four[0], year=2026, period_end=date(2026, 12, 31), revenue=0.0)
    assert margin_history((*four, dead)) == margin_history(four)
    assert margin_history(()) == {}


def test_the_net_margin_takes_the_operating_margin_s_window() -> None:
    """Spec 2026-11-13 11: the net margin's window is the last ten fiscal years with net income and
    a revenue above zero, as the operating margin's is with operating income; a loss year counts,
    and each median's count is its own. Eleven years of net income at 1% to 11% of a revenue of
    100, the newest without operating income: the net median runs over 2% to 11%, 6.5%; the
    operating median over the ten years before the newest."""
    years = margins([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, None])
    series = tuple(replace(fy, net_income=float(k + 1)) for k, fy in enumerate(years))
    history = margin_history(series)
    assert history["net"] == {"median": pytest.approx(0.065), "years": 10}
    assert history["operating"] == {"median": pytest.approx(0.275), "years": 10}
    assert history["operating"]["median"] == median_margin(series)
    nets = [-5.0, 1.0, 2.0]  # a loss year counts
    losses = tuple(replace(fy, net_income=n) for fy, n in zip(margins([10] * 3), nets, strict=True))
    assert margin_history(losses)["net"] == {"median": pytest.approx(0.01), "years": 3}


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


def test_consensus_basis_unknown_follows_large_nri(policy: Policy) -> None:
    nri = nri_flag(0.60, 5.00, policy)
    note = basis_unknown_flag(nri, 0.60, 5.00)
    assert note is not None and note.code == "consensus-basis-unknown"
    assert "$0.60 a share, 12.0% of trailing EPS" in note.sentence
    assert basis_unknown_flag(None, 0.10, 5.00) is None
    assert note == Flag(
        "consensus-basis-unknown",
        "Consensus basis unknown",
        "The non-recurring gap is $0.60 a share, 12.0% of trailing EPS. FMP's consensus names no "
        "basis, so whether the NTM anchor and the path carry such items is unknown; a report that "
        "reads the filing decides, through `earnings.nri_gap`, and on Mature Growth "
        "`earnings.ntm`.",
    )
    assert nri is not None and flag_count((nri, note)) == 1  # a note: only large-nri counts
    negative = basis_unknown_flag(nri_flag(-0.60, 5.00, policy), -0.60, 5.00)
    assert negative is not None and "is −$0.60 a share, 12.0% of trailing EPS" in negative.sentence


# Spec 2026-11-13 7.1: 96 million shares, a statutory rate of 25% and a trailing stock pay of $32
# million, so the after-tax stock pay a share is 32 × 0.75 ÷ 96 = 0.25.
_T = replace(trailing(), sbc=32e6, eps_diluted=12.5, income_tax=100.0, pretax_income=800.0)


def _uncertain(
    basis: SbcBasis, t: TrailingFigures = _T, street: float = 12.5, nri: bool = False
) -> Flag | None:
    return sbc_basis_uncertain_flag(basis, t, street, 96e6, 0.25, nri, load_policy())


def test_stock_pay_missing_names_the_newest_year_above_zero() -> None:
    history = StockPayHistory(zero_periods=0, newest_year=2024, newest_figure=69.8e6)
    flag = stock_pay_missing_flag(0.0, history)
    assert flag is not None and flag.code == "stock-pay-missing"
    assert "fiscal 2024" in flag.sentence and "$69.8 million" in flag.sentence
    one_quarter = StockPayHistory(zero_periods=1, newest_year=2025, newest_figure=1.33e9)
    assert stock_pay_missing_flag(1.0e9, one_quarter) is not None
    # a history of zeros, a full trailing figure, an unknown figure: silent
    assert stock_pay_missing_flag(0.0, StockPayHistory(4, None, None)) is None
    assert stock_pay_missing_flag(84.1e6, StockPayHistory(0, 2025, 80e6)) is None
    assert stock_pay_missing_flag(None, history) is None
    assert stock_pay_missing_flag(0.0, None) is None


def test_stock_pay_missing_words_and_currency() -> None:
    """The two sentences, a trailing figure at zero and a trailing period at zero, and the
    figure in the reporting currency on a row in another."""
    assert stock_pay_missing_flag(0.0, StockPayHistory(4, 2024, 69.8e6)) == Flag(
        "stock-pay-missing",
        "Stock pay missing",
        "The trailing stock pay is nil while fiscal 2024 shows $69.8 million, so the stored "
        "figure may be missing and the stock-pay charge on the consensus nil.",
    )
    one = stock_pay_missing_flag(1.0e9, StockPayHistory(1, 2025, 1.33e9))
    assert one is not None and one.sentence == (
        "The stock pay is nil in 1 trailing period while fiscal 2025 shows $1,330.0 million, so "
        "the trailing figure may be short, and the stock-pay charge on the consensus with it."
    )
    two = stock_pay_missing_flag(1.0e9, StockPayHistory(2, 2025, 1.33e9), "SEK")
    assert two is not None
    assert "nil in 2 trailing periods while fiscal 2025 shows SEK 1,330.0 million" in two.sentence


def test_the_basis_is_uncertain_on_a_one_time_item() -> None:
    """Reason 1: the test reads includes-sbc, the stock pay is material (0.25 is 2% of a street
    EPS of 12.5, the edge) and large-nri is on the row."""
    taxed = replace(_T, income_tax=200.0)  # a full tax, so reason 2 is out of the way
    assert _uncertain("includes-sbc", t=taxed, nri=True) is not None
    assert _uncertain("includes-sbc", t=taxed, nri=True, street=12.6) is None  # 0.25 is below 2%
    assert _uncertain("includes-sbc", t=taxed) is None  # no reason holds


def test_the_basis_is_uncertain_on_a_low_tax() -> None:
    """Reason 2: a trailing tax of 100 on a pre-tax income of 800 is 12.5%, half of 25%, the
    edge; 101 is above it; a pre-tax income at or below zero gives no reading."""
    assert _uncertain("includes-sbc") is not None
    assert _uncertain("includes-sbc", t=replace(_T, income_tax=101.0)) is None
    assert _uncertain("includes-sbc", t=replace(_T, pretax_income=0.0)) is None
    assert _uncertain("includes-sbc", t=replace(_T, income_tax=None)) is None


def test_the_basis_is_uncertain_on_a_gap_far_above_stock_pay() -> None:
    """Reason 3: the test reads excludes-sbc and the gap, 12.5 less 10.0, is 10 times 0.25, the
    edge; a GAAP EPS of 10.01 is inside it."""
    wide = replace(_T, eps_diluted=10.0, income_tax=200.0)
    flag = _uncertain("excludes-sbc", t=wide)
    assert flag is not None and flag.code == "sbc-basis-uncertain"
    assert _uncertain("excludes-sbc", t=replace(wide, eps_diluted=10.01)) is None
    assert _uncertain("unknown", t=wide) is None


def test_the_basis_uncertain_sentences() -> None:
    """One sentence for each reason that holds, joined by a space, each figure a share after
    ``$``, or after the reporting currency's code on a row in another; a stock pay of zero gives
    reason 3 no reading, and neither note is counted."""
    both = _uncertain("includes-sbc", nri=True)
    assert both == Flag(
        "sbc-basis-uncertain",
        "Stock-pay basis uncertain",
        "The basis test reads the consensus as counting stock pay, $0.25 a share after tax and "
        "2.0% of street trailing EPS, while a large non-recurring item on the row may sit in GAAP "
        "EPS and hide the gap. The basis test reads the consensus as counting stock pay, $0.25 a "
        "share after tax and 2.0% of street trailing EPS, while a trailing tax rate of 12.5%, at "
        "or below 50.0% of the statutory 25.0%, may close the gap.",
    )
    wide_t = replace(_T, eps_diluted=10.0, income_tax=200.0)
    wide = _uncertain("excludes-sbc", t=wide_t)
    assert wide is not None and wide.sentence == (
        "The street trailing EPS is $2.50 above the GAAP one, 10.0 times the stock pay of $0.25 a "
        "share after tax: the adjusted figure leaves out far more than stock pay, and the figures "
        "cannot say whether it leaves out stock pay too."
    )
    sek = sbc_basis_uncertain_flag(
        "excludes-sbc", wide_t, 12.5, 96e6, 0.25, False, load_policy(), currency="SEK"
    )
    assert sek is not None and sek.sentence.startswith(
        "The street trailing EPS is SEK 2.50 above the GAAP one, 10.0 times the stock pay of "
        "SEK 0.25 a share after tax:"
    )
    assert _uncertain("excludes-sbc", t=replace(_T, sbc=0.0, eps_diluted=10.0)) is None
    missing = stock_pay_missing_flag(0.0, StockPayHistory(4, 2024, 69.8e6))
    assert missing is not None and flag_count((missing, both)) == 0


def mature_terms(
    i: CompanyInputs,
    policy: Policy,
    used: Used = "marginal",
    one_year: float | None = 0.2142,
    override: float | None = None,
) -> RoicTerms:
    """MGCO's returns with the runway return as an agent would meet it on a capex surge: the
    measure ``used`` at 47.2%, or a floored one at 6.5% before its floor and r after it, or one at
    6.5% that starts at 20% on capital without goodwill, and the newest year's marginal return
    ``one_year``; with ``override``, an agent's ``return.runway`` in place of the measure."""
    terms = RoicTerms.of(i.capital_years, "Wide", policy, runway_override=override)
    below_r = {"floor": (0.065, policy.required_return), "without-goodwill": (0.065, 0.20)}
    chosen, value = below_r.get(used, (0.4716, 0.4716))
    rr = replace(
        terms.runway_return,
        used=used,
        chosen=chosen,
        value=value,
        marginal=0.4716,
        one_year=one_year,
    )
    return replace(terms, runway_return=rr)


def heavy_capex(flags: tuple[Flag, ...]) -> str:
    return next(f.sentence for f in flags if f.code == "heavy-capex")


def test_heavy_capex_names_the_start_and_the_newest_year_s_marginal(
    mg_inputs: CompanyInputs, policy: Policy
) -> None:
    assert mg_inputs.trailing is not None
    t = replace(mg_inputs.trailing, cfo=6_000e6, capex=-4_000e6)  # 66.7% of operating cash flow
    roic = mature_terms(mg_inputs, policy)
    assert roic.result.by_year[-1].year == 2025  # the newest kept ROIC year
    heavy = heavy_capex(trailing_flags(mg_inputs, t, None, policy, roic))
    assert "starts at 47.2%, the five-year marginal" in heavy
    assert "newest year's marginal return is 21.4%" in heavy
    assert "`return.runway`" in heavy
    assert heavy == (
        "Trailing capital spending is 66.7% of operating cash flow, above 50.0%. The charge's "
        "return starts at 47.2%, the five-year marginal; the newest year's marginal return is "
        "21.4%, on the capital added in fiscal 2025. The stored years end at fiscal 2025, so a "
        "return on a spending surge still under way is the agent's judgment: `return.runway`."
    )
    three = heavy_capex(
        trailing_flags(mg_inputs, t, None, policy, mature_terms(mg_inputs, policy, "three-year"))
    )
    assert "starts at 47.2%, the three-year aggregate; the newest year's" in three
    floor = heavy_capex(
        trailing_flags(mg_inputs, t, None, policy, mature_terms(mg_inputs, policy, "floor"))
    )
    assert "starts at 9.0%, floored at the required return; the newest year's" in floor
    lifted = mature_terms(mg_inputs, policy, "without-goodwill")
    # the words fit a start at the measure, a start at the cap under a higher measure, and the
    # cap alone where the business has no capital of its own: none calls the start "the return"
    assert (
        "starts at 20.0%, read on capital without goodwill and intangibles, at most the cap; the "
        "newest year's" in heavy_capex(trailing_flags(mg_inputs, t, None, policy, lifted))
    )
    # without a one-year figure the sentence stops at the start
    short = heavy_capex(
        trailing_flags(mg_inputs, t, None, policy, mature_terms(mg_inputs, policy, one_year=None))
    )
    assert short == (
        "Trailing capital spending is 66.7% of operating cash flow, above 50.0%. The charge's "
        "return starts at 47.2%, the five-year marginal."
    )
    # no charge return to name, and the other routes, which pass no returns: as built
    built = "Trailing capital spending is 66.7% of operating cash flow, above 50.0%."
    for used in ("off", "unavailable"):
        terms = mature_terms(mg_inputs, policy, used)
        assert heavy_capex(trailing_flags(mg_inputs, t, None, policy, terms)) == built
    assert heavy_capex(trailing_flags(mg_inputs, t, None, policy)) == built


def test_heavy_capex_names_an_override_as_the_start_and_the_measure_beside_it(
    mg_inputs: CompanyInputs, policy: Policy
) -> None:
    """Under a ``return.runway`` override the sentence names the override's value as the charge's
    start and the measured figure as the measure, then the newest year's marginal return."""
    assert mg_inputs.trailing is not None
    t = replace(mg_inputs.trailing, cfo=6_000e6, capex=-4_000e6)
    roic = mature_terms(mg_inputs, policy, override=0.214)
    assert roic.overridden and roic.runway == 0.214
    assert heavy_capex(trailing_flags(mg_inputs, t, None, policy, roic)) == (
        "Trailing capital spending is 66.7% of operating cash flow, above 50.0%. The charge's "
        "return starts at 21.4%, the agent's override; the five-year marginal is 47.2%; the "
        "newest year's marginal return is 21.4%, on the capital added in fiscal 2025. The stored "
        "years end at fiscal 2025, so a return on a spending surge still under way is the agent's "
        "judgment: `return.runway`."
    )
    three = mature_terms(mg_inputs, policy, "three-year", override=0.214)
    assert "starts at 21.4%, the agent's override; the three-year aggregate is 47.2%; the " in (
        heavy_capex(trailing_flags(mg_inputs, t, None, policy, three))
    )
    floor = mature_terms(mg_inputs, policy, "floor", override=0.214)
    assert (
        "starts at 21.4%, the agent's override; the measured return is 6.5%, below the required "
        "return; the newest" in heavy_capex(trailing_flags(mg_inputs, t, None, policy, floor))
    )
    lifted = mature_terms(mg_inputs, policy, "without-goodwill", override=0.214)
    assert (
        "starts at 21.4%, the agent's override; the measured return is 6.5%, below the required "
        "return, and the charge would start at 20.0%, on capital without goodwill and "
        "intangibles; the newest" in heavy_capex(trailing_flags(mg_inputs, t, None, policy, lifted))
    )
    # a measured return that is off or unavailable has no measure to name; the start stands
    for used in ("off", "unavailable"):
        terms = mature_terms(mg_inputs, policy, used, one_year=None, override=0.214)
        assert heavy_capex(trailing_flags(mg_inputs, t, None, policy, terms)) == (
            "Trailing capital spending is 66.7% of operating cash flow, above 50.0%. The "
            "charge's return starts at 21.4%, the agent's override."
        )
    assert not mature_terms(mg_inputs, policy).overridden


def test_consensus_basis_unknown_only_on_the_mature_routes(
    mg_inputs: CompanyInputs, policy: Policy
) -> None:
    assert mg_inputs.trailing is not None
    t = mg_inputs.trailing  # trailing EPS 5.30, so a gap of 0.60 is 11.3% of it
    roic = mature_terms(mg_inputs, policy)
    codes = [f.code for f in trailing_flags(mg_inputs, t, 0.60, policy, roic)]
    assert codes[-2:] == ["large-nri", "consensus-basis-unknown"]
    other_routes = trailing_flags(mg_inputs, t, 0.60, policy)  # large-nri, but no returns
    assert [f.code for f in other_routes][-1] == "large-nri"
    no_nri = trailing_flags(mg_inputs, t, 0.05, policy, roic)  # under 5% of EPS
    assert {"large-nri", "consensus-basis-unknown"}.isdisjoint(f.code for f in no_nri)


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


@pytest.mark.parametrize(
    ("market_cap", "fires"),
    [(70.0, False), (69.9, True), (130.0, False), (130.1, True), (100.0, False)],
)
def test_the_share_count_gap_fires_outside_the_band(market_cap: float, fires: bool) -> None:
    """A price of 1 on 100 shares: the ratio is the market cap over 100. The band's edges, 0.7
    and 1.3, are inside it."""
    flag = share_count_flag(market_cap, 1.0, 100.0, load_policy())
    assert (flag is not None) is fires
    if flag is not None:
        assert flag.code == "share-count-gap" and f"{market_cap / 100:.2f}" in flag.sentence


def test_the_share_count_gap_needs_its_three_figures() -> None:
    policy = load_policy()
    assert share_count_flag(None, 1.0, 100.0, policy) is None
    assert share_count_flag(460.0, None, 100.0, policy) is None
    assert share_count_flag(460.0, 1.0, None, policy) is None
    assert share_count_flag(460.0, 0.0, 100.0, policy) is None
    # a figure at or below zero, or not finite, is no figure
    for market_cap, price, shares in (
        (0.0, 1.0, 100.0),
        (460.0, 1.0, 0.0),
        (460.0, -1.0, 100.0),
        (math.nan, 1.0, 100.0),
        (460.0, math.inf, 100.0),
    ):
        assert share_count_flag(market_cap, price, shares, policy) is None


def test_the_share_count_gap_names_both_figures_and_both_readings(policy: Policy) -> None:
    """Spec 2026-11-13 8: the ratio to two decimals, the market cap, the price times the count, the
    band, and the two readings. The figures are the quote's, in US dollars on every row."""
    flag = share_count_flag(6_900e6, 15.0, 100e6, policy)
    assert flag == Flag(
        "share-count-gap",
        "Share count and market cap disagree",
        "The market cap is $6,900.0 million and the price of $15.00 times the diluted count of "
        "100.0 million shares is $1,500.0 million: a ratio of 4.60, outside 0.70 to 1.30. The "
        "count may leave out a share class or units that convert to shares, or the market cap "
        "may leave a class out.",
    )
    low = share_count_flag(380e6, 10.0, 100e6, policy)  # 0.38, as TKO read on refresh 34
    assert low is not None and "is $1,000.0 million: a ratio of 0.38," in low.sentence
    assert flag_count((flag,)) == 1


def test_flag_count_counts_the_twelve_quality_warnings_only() -> None:
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
            "share-count-gap",
        }
    )
