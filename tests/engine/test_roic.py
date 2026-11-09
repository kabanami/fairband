from dataclasses import replace

import pytest

from fairband.engine.roic import (
    CapitalYear,
    RoicResult,
    RoicYear,
    RunwayReturn,
    Used,
    aggregate_roic,
    invested_capital,
    nopat,
    not_presented,
    runway_note,
    runway_return,
    terminal_return,
    terminal_roic,
    window_aggregate,
)
from fairband.engine.route_steps import RoicTerms, charge_for
from fairband.policy import Moat, Policy, load_policy


def cy(year: int, oi: float | None = 20.0, ppe: float | None = 100.0) -> CapitalYear:
    """A year whose capital sits all in net PP&E, every other line 0, tax 0: NOPAT is ``oi``."""
    return CapitalYear(
        year=year,
        operating_income=oi,
        tax_rate=0.0,
        total_current_assets=0.0,
        cash_and_investments=0.0,
        total_current_liabilities=0.0,
        short_term_debt=0.0,
        current_lease_liability=0.0,
        net_ppe=ppe,
        lease_rou_asset=0.0,
        goodwill=0.0,
        intangibles=0.0,
    )


def history(n: int, ppe: float = 100.0) -> list[CapitalYear]:
    """``n`` year-end balance sheets ending in fiscal 2025, each year earning 20 on ``ppe``."""
    return [cy(2026 - n + i, ppe=ppe) for i in range(n)]


def codes(r: RoicResult) -> tuple[str, ...]:
    return tuple(f.code for f in r.flags)


def kept(pairs: list[tuple[float, float]], first_year: int = 2017) -> RoicResult:
    """Kept ROIC years from ``(nopat, average_capital)`` pairs, oldest first."""
    rows = tuple(
        RoicYear(first_year + k, n, c, n / c if c else None) for k, (n, c) in enumerate(pairs)
    )
    return RoicResult(
        aggregate=window_aggregate(rows, 10)[0], years_used=len(rows), by_year=rows, flags=()
    )


# Spec section 7: kept years 2017 to 2026 as (NOPAT, average capital).
SPEC = [
    (100, 1000),
    (110, 1050),
    (125, 1100),
    (140, 1200),
    (150, 1300),
    (180, 1500),
    (220, 1700),
    (260, 1900),
    (300, 2100),
    (350, 2300),
]


@pytest.fixture
def policy() -> Policy:
    return load_policy()


def test_design_example_aggregate() -> None:
    # design 6.6: seven years earn 20 on capital of 100, year 8 earns -10 on 100, year 9 earns 20
    # on 20 and year 10 earns 22 on 110, so the aggregate is 172 / 930 = 18.5%. The design's
    # capital is each year's average of the opening and closing balances (D2), so the eleven
    # year-end balances, all in net PP&E with every other line 0 and tax 0, are 100 nine times,
    # then -60 and 280. Fiscal 2015 is the opening balance only; its income is not used.
    balances = [100.0] * 9 + [-60.0, 280.0]
    income: list[float | None] = [None] + [20.0] * 7 + [-10.0, 20.0, 22.0]
    years = [
        cy(2015 + i, oi, ppe) for i, (oi, ppe) in enumerate(zip(income, balances, strict=True))
    ]
    r = aggregate_roic(years)
    assert [y.year for y in r.by_year] == list(range(2016, 2026))
    assert [y.average_capital for y in r.by_year] == [100.0] * 8 + [20.0, 110.0]
    assert [y.nopat for y in r.by_year] == income[1:]
    assert r.by_year[8].roic == pytest.approx(1.0)
    assert (
        r.aggregate == pytest.approx(172 / 930, abs=1e-6) and r.years_used == 10 and r.flags == ()
    )


def test_not_presented_counts_nil_and_flags() -> None:
    y = CapitalYear(2025, 100, 0.21, 500, 200, 300, 50, None, 400, None, None, None)
    assert invested_capital(y) == pytest.approx(500 - 200 - (300 - 50) + 400)
    assert not_presented(y) == (
        "current_lease_liability",
        "lease_rou_asset",
        "goodwill",
        "intangibles",
    )
    years = history(11)
    years[3] = replace(years[3], goodwill=None)
    years[7] = replace(years[7], goodwill=None)
    r = aggregate_roic(years)
    assert r.aggregate == pytest.approx(0.2) and r.years_used == 10
    assert codes(r) == ("line-not-presented:goodwill",)
    flag = r.flags[0]
    assert flag.word == "Line not presented: goodwill"  # the Flags column names the field
    assert "goodwill" in flag.sentence and "not-presented-as-nil-v1" in flag.sentence


def test_line_not_presented_reads_kept_years_and_their_opening_balance() -> None:
    years = history(13)  # fiscal 2013 to 2025; the last ten kept years are 2016 to 2025
    years[0] = replace(years[0], intangibles=None)  # 2013: opens 2014, which is not kept
    years[2] = replace(years[2], short_term_debt=None)  # 2015: opens 2016, which is kept
    years[12] = replace(years[12], cash_and_investments=None)  # 2025: kept
    r = aggregate_roic(years)
    assert [y.year for y in r.by_year] == list(range(2016, 2026))
    assert codes(r) == (
        "line-not-presented:cash_and_investments",
        "line-not-presented:short_term_debt",
    )


def test_nopat_and_capital_need_their_inputs() -> None:
    y = replace(cy(2025, oi=100.0), tax_rate=0.25)
    assert nopat(y) == pytest.approx(75.0)
    assert nopat(replace(y, operating_income=None)) is None
    assert nopat(replace(y, tax_rate=None)) is None
    assert invested_capital(y) == pytest.approx(100.0)
    for field in ("total_current_assets", "total_current_liabilities", "net_ppe"):
        assert invested_capital(replace(y, **{field: None})) is None


def test_required_total_missing_drops_year() -> None:
    years = history(11)
    years[-1] = replace(years[-1], net_ppe=None)
    r = aggregate_roic(years)
    assert r.years_used == 9 and [y.year for y in r.by_year] == list(range(2016, 2025))
    assert r.aggregate == pytest.approx(0.2)
    assert codes(r) == ("roic-on-n-years",) and r.flags[0].word == "ROIC on 9 years"


@pytest.mark.parametrize(
    ("field", "dropped"),
    [
        ("net_ppe", {2020, 2021}),  # the 2020 balance closes 2020 and opens 2021
        ("total_current_assets", {2020, 2021}),
        ("total_current_liabilities", {2020, 2021}),
        ("operating_income", {2020}),
        ("tax_rate", {2020}),
    ],
)
def test_missing_input_drops_the_years_that_need_it(field: str, dropped: set[int]) -> None:
    years = history(11)
    years[5] = replace(years[5], **{field: None})  # fiscal 2020
    r = aggregate_roic(years)
    assert {y.year for y in r.by_year} == set(range(2016, 2026)) - dropped
    assert r.years_used == 10 - len(dropped)


def test_keeps_the_last_ten_years() -> None:
    years = history(13)  # twelve usable years, 2014 to 2025
    years[1] = replace(years[1], operating_income=1000.0)  # 2014: outside the last ten
    r = aggregate_roic(years)
    assert r.years_used == 10 and r.by_year[0].year == 2016
    assert r.aggregate == pytest.approx(0.2) and r.flags == ()


def test_an_older_year_fills_in_for_a_dropped_one() -> None:
    years = history(12)  # eleven usable years, 2015 to 2025
    years[7] = replace(years[7], operating_income=None)  # 2021 dropped
    r = aggregate_roic(years)
    assert [y.year for y in r.by_year] == [*range(2015, 2021), *range(2022, 2026)]
    assert r.years_used == 10 and r.flags == ()


def test_fewer_than_five_years_unavailable() -> None:
    r = aggregate_roic(history(5))
    assert r.aggregate is None and r.years_used == 4 and len(r.by_year) == 4
    assert codes(r) == ("roic-unavailable",)
    # the revenue-growth route's charge never reads it, so the sentence names the mature routes
    assert r.flags[0].sentence == (
        "Fewer than 5 fiscal years have the data for ROIC (4), so there is no aggregate ROIC; on "
        "the mature routes the charge uses the terminal ROIC in every year."
    )
    five = aggregate_roic(history(6))
    assert five.aggregate == pytest.approx(0.2) and five.flags[0].word == "ROIC on 5 years"
    assert aggregate_roic(history(5), min_years=4).aggregate == pytest.approx(0.2)


def test_no_usable_year_is_unavailable_not_zeroed() -> None:
    for years in ([], history(1)):
        r = aggregate_roic(years)
        assert r.aggregate is None and r.years_used == 0 and r.by_year == ()
        assert codes(r) == ("roic-unavailable",)


def test_negative_capital_leaves_the_ten_year_roic_unavailable() -> None:
    r = aggregate_roic(history(11, ppe=-50.0))
    assert r.aggregate is None and r.years_used == 10
    assert codes(r) == ("ten-year-roic-unavailable",)
    assert r.flags[0].word == "Ten-year ROIC unavailable"
    assert r.flags[0].sentence == (
        "Average invested capital sums to zero or below over the 10 ROIC years, so the ten-year "
        "ROIC is unavailable."
    )
    short = aggregate_roic(history(8, ppe=-50.0))
    assert short.aggregate is None
    assert codes(short) == ("roic-on-n-years", "ten-year-roic-unavailable")


def test_zero_capital_does_not_divide_by_zero() -> None:
    years = [cy(2015 + i, ppe=50.0 if i % 2 else -50.0) for i in range(11)]  # every average is 0
    r = aggregate_roic(years)
    assert r.aggregate is None and codes(r) == ("ten-year-roic-unavailable",)
    assert all(y.average_capital == 0 and y.roic is None for y in r.by_year)


def test_zero_capital_year_has_no_roic_but_counts() -> None:
    balances = [100.0] * 9 + [-100.0, 300.0]  # 2024 averages 0, 2025 averages 100
    r = aggregate_roic([cy(2015 + i, ppe=b) for i, b in enumerate(balances)])
    assert r.by_year[8].average_capital == 0 and r.by_year[8].roic is None
    assert r.aggregate == pytest.approx(200 / 900) and r.flags == ()


def test_terminal_roic_rules(policy: Policy) -> None:
    assert terminal_roic(0.25, "Wide", policy) == 0.13
    assert terminal_roic(0.11, "Wide", policy) == 0.11
    assert terminal_roic(0.05, "Wide", policy) == 0.09
    assert (
        terminal_roic(0.25, "Narrow", policy) == 0.09
        and terminal_roic(None, "Wide", policy) == 0.09
    )
    assert terminal_roic(0.25, "None", policy) == 0.09


def test_terminal_roic_reads_the_policy(policy: Policy) -> None:
    other = replace(policy, required_return=0.10, wide_terminal_roic_spread=0.05)
    assert terminal_roic(0.25, "Wide", other) == pytest.approx(0.15)  # r + the spread
    assert terminal_roic(0.05, "Wide", other) == 0.10
    assert terminal_roic(0.25, "Narrow", other) == 0.10


# --- The runway return and the terminal return (calibration spec 5.1, 5.3) ---------------------


def test_marginal_return_spec_example(policy: Policy) -> None:
    rr = runway_return(kept(SPEC), "Wide", policy)
    assert rr.marginal == pytest.approx(0.2000) and rr.marginal_usable
    assert rr.three_year == pytest.approx(0.1444, abs=5e-5)
    assert rr.ten_year == pytest.approx(0.1277, abs=5e-5)
    assert rr.used == "marginal" and rr.chosen == rr.value == pytest.approx(0.2000)
    assert rr.charge_off is False and rr.flags == ()


def test_the_one_year_marginal_is_shown_not_used(policy: Policy) -> None:
    rr = runway_return(kept(SPEC), "Wide", policy)
    by_year = kept(SPEC).by_year
    expected = (by_year[-1].nopat - by_year[-2].nopat) / (
        by_year[-1].average_capital - by_year[-2].average_capital
    )
    assert rr.one_year == pytest.approx(expected) == pytest.approx(50 / 200)
    assert rr.value == pytest.approx(rr.marginal)  # the five-year measure still charges


def test_the_one_year_marginal_is_none_without_two_years_or_a_capital_change(
    policy: Policy,
) -> None:
    assert runway_return(kept(SPEC[-1:]), "Wide", policy).one_year is None  # one kept year
    assert runway_return(kept([(100, 1000), (120, 1000)]), "Wide", policy).one_year is None
    flat_end = runway_return(kept(SPEC[:-1] + [(360, 2100)]), "Wide", policy)
    assert flat_end.one_year is None and flat_end.used == "marginal"


@pytest.mark.parametrize(
    ("pairs", "used", "one_year"),
    [
        (SPEC, "marginal", 50 / 200),
        ([(n, 2000 + 10 * k) for k, (n, _) in enumerate(SPEC)], "three-year", 50 / 10),
        ([(n * 0.3, c) for n, c in SPEC], "floor", 15 / 200),
        ([(20.0, -50.0)] * 9 + [(10.0, -40.0)], "off", -10 / 10),
        (SPEC[-4:], "unavailable", 50 / 200),
    ],
)
def test_the_one_year_marginal_is_recorded_on_every_branch(
    policy: Policy, pairs: list[tuple[float, float]], used: Used, one_year: float
) -> None:
    rr = runway_return(kept(pairs), "Wide", policy)
    assert rr.used == used and rr.one_year == pytest.approx(one_year)


def test_the_intermediates_record_the_one_year_marginal_and_the_charge_takes_a_hold(
    policy: Policy,
) -> None:
    # NOPAT 20 + 5k on capital 100 + 10k: the newest kept year adds 5 of NOPAT on 10 of capital
    years = [cy(2015 + k, oi=20.0 + 5 * k, ppe=100.0 + 10 * k) for k in range(11)]
    terms = RoicTerms.of(years, "Wide", policy)
    assert terms.intermediates()["runway_return"]["one_year"] == pytest.approx(0.5)
    assert terms.charge(policy).hold is None  # the shape as built until a route passes a hold
    assert terms.charge(policy, 4).hold == 4
    assert charge_for(0.20, 0.13, False, policy, 4).hold == 4
    assert charge_for(0.20, 0.13, False, policy).hold is None


def test_fallback_when_capital_barely_grows(policy: Policy) -> None:
    flat = [(n, 2000 + 10 * k) for k, (n, _) in enumerate(SPEC)]
    rr = runway_return(kept(flat), "Wide", policy)
    assert rr.marginal_usable is False and rr.used == "three-year"
    assert rr.value == pytest.approx(0.1458, abs=5e-5)


def test_fallback_when_nopat_falls(policy: Policy) -> None:
    falling = SPEC[:5] + [(90, 1500), (80, 1700), (70, 1900), (60, 2100), (50, 2300)]
    rr = runway_return(kept(falling), "Wide", policy)
    assert rr.marginal == pytest.approx(-0.10) and rr.marginal_usable is False
    assert rr.three_year == pytest.approx(180 / 6300)  # below r, so the floor applies
    assert rr.used == "floor" and rr.chosen == rr.three_year and rr.value == 0.09


def test_floor_at_the_required_return(policy: Policy) -> None:
    low = [(n * 0.3, c) for n, c in SPEC]  # marginal (105 − 45) ÷ 1000 = 0.06, usable, under r
    rr = runway_return(kept(low), "Wide", policy)
    assert rr.used == "floor" and rr.value == 0.09 and rr.chosen == pytest.approx(0.06)
    assert [f.code for f in rr.flags] == ["return-floored"]


def test_marginal_needs_six_kept_years(policy: Policy) -> None:
    six = runway_return(kept(SPEC[-6:]), "Wide", policy)
    assert six.used == "marginal" and six.marginal == pytest.approx(200 / 1000)
    five = runway_return(kept(SPEC[-5:]), "Wide", policy)
    assert five.marginal is None and five.used == "three-year"
    four = runway_return(kept(SPEC[-4:]), "Wide", policy)
    assert four.used == "unavailable" and four.value == 0.09 and four.chosen is None


def test_charge_off_on_a_non_positive_three_year_sum(policy: Policy) -> None:
    negative = [(20.0, -50.0)] * 10
    wide = runway_return(kept(negative), "Wide", policy)
    assert wide.used == "off" and wide.charge_off and wide.value == 0.13
    assert [f.code for f in wide.flags] == ["charge-zeroed"]
    narrow = runway_return(kept(negative), "Narrow", policy)
    assert narrow.value == 0.09


@pytest.mark.parametrize(
    ("moat", "used", "chosen", "expected"),
    [
        ("Wide", "marginal", 0.28, 0.13),
        ("Wide", "three-year", 0.098, 0.098),
        ("Wide", "floor", 0.06, 0.09),
        ("Narrow", "marginal", 0.28, 0.09),
        ("Wide", "off", None, 0.13),
        ("None", "off", None, 0.09),
        ("Wide", "unavailable", None, 0.09),
    ],
)
def test_terminal_return(
    policy: Policy, moat: Moat, used: Used, chosen: float | None, expected: float
) -> None:
    rr = RunwayReturn(used, None, False, None, None, chosen, 0.0, used == "off", (), None)
    assert terminal_return(rr, moat, policy) == pytest.approx(expected)


def test_ten_year_capital_at_or_below_zero_is_unavailable_not_zeroed() -> None:
    r = aggregate_roic(history(11, ppe=-50.0))
    assert r.aggregate is None and codes(r) == ("ten-year-roic-unavailable",)


def test_runway_flags_say_what_the_charge_used(policy: Policy) -> None:
    negative = [(20.0, -50.0)] * 10
    [zeroed] = runway_return(kept(negative), "Wide", policy).flags
    assert zeroed.word == "Charge zeroed"
    assert zeroed.sentence == (
        "The marginal return is not usable and average invested capital sums to zero or below "
        "over the last 3 ROIC years, so the runway charge is zero; the terminal still charges at "
        "13.0%."
    )
    [narrow] = runway_return(kept(negative), "Narrow", policy).flags
    assert narrow.sentence.endswith("the terminal still charges at 9.0%.")
    [floored] = runway_return(kept([(n * 0.3, c) for n, c in SPEC]), "Wide", policy).flags
    assert floored.word == "Return floored"
    assert floored.sentence == (
        "The five-year marginal return of 6.0% is below the required return, so the charge uses "
        "9.0%."
    )


def test_runway_note_names_the_measure(policy: Policy) -> None:
    flat = [(n, 2000 + 10 * k) for k, (n, _) in enumerate(SPEC)]
    low = [(n * 0.3, c) for n, c in SPEC]
    falling = SPEC[:5] + [(90, 1500), (80, 1700), (70, 1900), (60, 2100), (50, 2300)]
    cases = [
        (SPEC, "five-year marginal return on new capital"),
        (flat, "three-year aggregate ROIC (marginal not usable)"),
        (low, "floored at the required return; the five-year marginal was 6.0%"),
        (falling, "floored at the required return; the three-year was 2.9%"),
        ([(20.0, -50.0)] * 10, "charge off: capital at or below zero"),
        (SPEC[-4:], "unavailable: fewer than 5 ROIC years"),
    ]
    for pairs, note in cases:
        assert runway_note(runway_return(kept(pairs), "Wide", policy)) == note
