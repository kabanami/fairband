from dataclasses import replace

import pytest

from fairband.engine.roic import (
    CapitalYear,
    RoicResult,
    RoicYear,
    RunwayReturn,
    Used,
    WithoutGoodwill,
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
from fairband.engine.route_steps import RoicTerms, charge_for, constant_margin_return
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


# --- The return without goodwill and intangibles (method 4.6 rule 5) ---------------------------


def kept_with(triples: list[tuple[float, float, float]], first_year: int = 2017) -> RoicResult:
    """Kept ROIC years from ``(nopat, average_capital, average goodwill and intangibles)``."""
    rows = tuple(
        RoicYear(first_year + k, n, c, n / c if c else None, g)
        for k, (n, c, g) in enumerate(triples)
    )
    return RoicResult(
        aggregate=window_aggregate(rows, 10)[0], years_used=len(rows), by_year=rows, flags=()
    )


def bought(goodwill: float, nopat_each: float = 100.0) -> RoicResult:
    """Ten flat years of a company that bought a business: capital 2,000, of which ``goodwill``
    is goodwill and intangibles. Capital never changes, so no marginal return exists."""
    return kept_with([(nopat_each, 2000.0, goodwill)] * 10)


def test_a_kept_year_records_its_average_goodwill_and_intangibles() -> None:
    years = [
        replace(cy(2015 + k), goodwill=30.0 + 10 * k, intangibles=None if k == 0 else 10.0)
        for k in range(3)
    ]
    first, second = aggregate_roic(years, min_years=1).by_year
    # opening 30 + nil, closing 40 + 10; then opening 50, closing 50 + 10
    assert first.average_goodwill_and_intangibles == pytest.approx(40.0)
    assert second.average_goodwill_and_intangibles == pytest.approx(55.0)
    assert first.average_capital == pytest.approx((130.0 + 150.0) / 2)  # capital keeps both


def test_a_measure_below_r_reads_the_return_without_goodwill(policy: Policy) -> None:
    rr = runway_return(bought(1500.0), "Narrow", policy)  # 5% with them, 20% without
    assert rr.chosen == pytest.approx(0.05) and rr.marginal is None
    assert rr.used == "without-goodwill" and rr.value == pytest.approx(0.20)
    assert rr.charge_off is False
    assert rr.without_goodwill == WithoutGoodwill(
        marginal=None,
        marginal_usable=False,
        three_year=pytest.approx(0.20),
        measure=pytest.approx(0.20),
        capital_free=False,
    )
    [flag] = rr.flags
    assert (flag.code, flag.word) == ("return-without-goodwill", "Return without goodwill")
    assert flag.sentence == (
        "The three-year return of 5.0% is below the required return. On capital without "
        "goodwill and intangibles the three-year return is 20.0%, so the charge starts at 20.0%."
    )


def test_the_return_without_goodwill_is_capped(policy: Policy) -> None:
    assert policy.return_without_goodwill_cap == 0.25
    rr = runway_return(bought(1800.0), "Narrow", policy)  # 100 on 200: 50% without them
    assert rr.used == "without-goodwill" and rr.value == 0.25
    assert rr.without_goodwill is not None and rr.without_goodwill.measure == pytest.approx(0.5)
    [flag] = rr.flags
    assert flag.sentence == (
        "The three-year return of 5.0% is below the required return. On capital without "
        "goodwill and intangibles the three-year return is 50.0%, above the cap, so the charge "
        "starts at 25.0%."
    )


def test_the_floor_stands_when_the_return_without_goodwill_is_not_above_r(
    policy: Policy,
) -> None:
    for goodwill, without in ((500.0, 100 / 1500), (0.0, 0.05)):
        rr = runway_return(bought(goodwill), "Narrow", policy)
        assert rr.used == "floor" and rr.value == 0.09, goodwill
        assert [f.code for f in rr.flags] == ["return-floored"]
        assert rr.without_goodwill is not None
        assert rr.without_goodwill.measure == pytest.approx(without)
    # 9 on 100 without goodwill is r exactly, and only a return above r lifts the start
    at_r = runway_return(kept_with([(9.0, 1000.0, 900.0)] * 10), "Narrow", policy)
    assert at_r.without_goodwill is not None and at_r.without_goodwill.measure == 0.09
    assert at_r.used == "floor" and at_r.value == 0.09


def test_capital_at_or_below_zero_without_goodwill_takes_the_cap(policy: Policy) -> None:
    rr = runway_return(bought(2100.0), "Narrow", policy)  # capital of −100 without them
    assert rr.used == "without-goodwill" and rr.value == 0.25
    assert rr.without_goodwill == WithoutGoodwill(None, False, None, None, True)
    [flag] = rr.flags
    assert flag.sentence == (
        "The three-year return of 5.0% is below the required return. Capital without goodwill "
        "and intangibles sums to zero or below over the last 3 ROIC years, so the charge starts "
        "at the cap, 25.0%."
    )
    exactly_zero = runway_return(bought(2000.0), "Narrow", policy)
    assert exactly_zero.used == "without-goodwill" and exactly_zero.value == 0.25


def test_a_loss_on_no_capital_without_goodwill_stays_at_the_floor(policy: Policy) -> None:
    for nopat_each in (-10.0, 0.0):
        rr = runway_return(bought(2100.0, nopat_each), "Narrow", policy)
        assert rr.used == "floor" and rr.value == 0.09
        assert rr.without_goodwill == WithoutGoodwill(None, False, None, None, False)


def test_the_marginal_without_goodwill_is_read_when_usable_there(policy: Policy) -> None:
    # NOPAT 100 + 10k on own capital 500 + 50k; a purchase adds 2,000 of goodwill from year 5.
    # With it the five-year marginal is 50 ÷ 2,250 = 2.2%, usable and below r; without it
    # 50 ÷ 250 = 20%, usable too.
    triples = [
        (100.0 + 10 * k, 500.0 + 50 * k + (2000.0 if k >= 5 else 0.0), 2000.0 if k >= 5 else 0.0)
        for k in range(10)
    ]
    rr = runway_return(kept_with(triples), "Narrow", policy)
    assert rr.marginal == pytest.approx(50 / 2250) and rr.marginal_usable
    assert rr.used == "without-goodwill" and rr.value == pytest.approx(0.20)
    assert rr.without_goodwill is not None and rr.without_goodwill.marginal_usable
    assert rr.without_goodwill.marginal == pytest.approx(0.20)
    [flag] = rr.flags
    assert flag.sentence == (
        "The five-year marginal return of 2.2% is below the required return. On capital without "
        "goodwill and intangibles the five-year marginal return is 20.0%, so the charge starts "
        "at 20.0%."
    )


def test_growth_that_was_bought_keeps_the_floor(policy: Policy) -> None:
    """Capital grew with goodwill and not without it: the growth of the stored years was bought,
    so the level of return on the business's own flat capital says nothing of what its growth
    costs, and the floor stands (method 4.6 rule 5; the review of 2026-11-12, on Roper, S&P
    Global and 21 more rows of the scratch revalue)."""
    # own capital flat at 500; NOPAT 100 to 140 only through 1,000 of goodwill bought in year 5:
    # with goodwill the five-year marginal is 40 ÷ 1,000 = 4.0%, usable; without it capital
    # did not grow, so no marginal exists and the three-year level is 140 ÷ 500 = 28%
    triples = [
        (100.0 if k < 5 else 140.0, 500.0 + (1000.0 if k >= 5 else 0.0), 1000.0 if k >= 5 else 0.0)
        for k in range(10)
    ]
    rr = runway_return(kept_with(triples), "Wide", policy)
    assert rr.marginal == pytest.approx(0.04) and rr.marginal_usable
    level = pytest.approx(0.28)
    assert rr.without_goodwill == WithoutGoodwill(None, False, level, level, False, bought=True)
    assert rr.used == "floor" and rr.value == 0.09
    [flag] = rr.flags
    assert flag.code == "return-floored" and flag.sentence == (
        "The five-year marginal return of 4.0% is below the required return, so the charge uses "
        "9.0%. The return on capital without goodwill and intangibles is not read: purchases "
        "carried the growth of the capital."
    )
    assert runway_note(rr) == (
        "floored at the required return; the five-year marginal was 4.0%; purchases carried "
        "the capital's growth"
    )
    assert terminal_return(rr, "Wide", policy) == 0.09
    # a business with no capital of its own (−100 in every year) whose capital with goodwill
    # grew from 1,000 to 2,000 by a purchase: the same 4.0%, usable, and the floor too
    free = [
        (100.0 if k < 5 else 140.0, 1000.0 if k < 5 else 2000.0, 1100.0 if k < 5 else 2100.0)
        for k in range(10)
    ]
    rr = runway_return(kept_with(free), "Wide", policy)
    assert rr.marginal == pytest.approx(0.04) and rr.marginal_usable
    assert rr.without_goodwill == WithoutGoodwill(None, False, None, None, True, bought=True)
    assert rr.used == "floor" and rr.value == 0.09


def test_growth_is_bought_only_where_goodwill_grew(policy: Policy) -> None:
    """The three tests of bought growth stand together: a usable marginal with goodwill, none
    usable without it, and goodwill and intangibles that grew over the span. With one missing
    the measures without goodwill are read (the second review of 2026-11-12)."""
    # nothing was bought: goodwill flat at 1,000, the business's own capital −800 to −750, so
    # capital grew 200 to 250, a quarter, and NOPAT 100 to 102: the marginal with goodwill is
    # 4.0% and usable, the one without is not (50 is under a fifth of 800), yet the business
    # needs no capital of its own, and the charge starts at the cap
    flat = [(100.0 if k < 5 else 102.0, 200.0 if k < 5 else 250.0, 1000.0) for k in range(10)]
    rr = runway_return(kept_with(flat), "Narrow", policy)
    assert rr.marginal == pytest.approx(0.04) and rr.marginal_usable
    assert rr.without_goodwill == WithoutGoodwill(
        pytest.approx(0.04), False, None, None, True, bought=False
    )
    assert rr.used == "without-goodwill" and rr.value == 0.25
    # goodwill grew, 1,000 to 1,250, and capital with it by a sixth only, under the fifth a
    # marginal needs: the three-year level with goodwill is read, below r, and the level without
    # it, 110 ÷ 500 = 22%, starts the charge. A purchase this small against the capital is the
    # rule's known edge (method 4.6)
    small = [
        (100.0 if k < 5 else 110.0, 1500.0 if k < 5 else 1750.0, 1000.0 if k < 5 else 1250.0)
        for k in range(10)
    ]
    rr = runway_return(kept_with(small), "Narrow", policy)
    assert not rr.marginal_usable and rr.without_goodwill is not None
    assert rr.without_goodwill.bought is False
    assert rr.used == "without-goodwill" and rr.value == pytest.approx(0.22)
    # a company that bought and grew its own capital by more than a fifth reads the marginal
    # without goodwill (AMD's shape): the purchases' earnings are in it, and the cap bounds it
    both = [
        (100.0 + 10 * k, 500.0 + 50 * k + (2000.0 if k >= 5 else 0.0), 2000.0 if k >= 5 else 0.0)
        for k in range(10)
    ]
    rr = runway_return(kept_with(both), "Narrow", policy)
    assert rr.without_goodwill is not None and rr.without_goodwill.bought is False
    assert rr.used == "without-goodwill" and rr.value == pytest.approx(0.20)
    # a row at or above r records the test all the same, and never reads it
    above = runway_return(
        kept_with([(n * 3, c, g) for n, c, g in triples_of_a_purchase()]), "Wide", policy
    )
    assert above.used == "marginal" and above.without_goodwill is not None
    assert above.without_goodwill.bought is True and above.flags == ()


def triples_of_a_purchase() -> list[tuple[float, float, float]]:
    """Own capital flat at 500; NOPAT 100 to 140 through 1,000 of goodwill bought in year 5."""
    return [
        (100.0 if k < 5 else 140.0, 500.0 + (1000.0 if k >= 5 else 0.0), 1000.0 if k >= 5 else 0.0)
        for k in range(10)
    ]


def test_a_usable_marginal_without_goodwill_at_or_below_r_keeps_the_floor(
    policy: Policy,
) -> None:
    # as above with NOPAT growing 2 a year: 10 ÷ 250 = 4% without goodwill, usable, below r; the
    # three-year return without goodwill, far above r, is not read
    triples = [
        (100.0 + 2 * k, 500.0 + 50 * k + (2000.0 if k >= 5 else 0.0), 2000.0 if k >= 5 else 0.0)
        for k in range(10)
    ]
    rr = runway_return(kept_with(triples), "Narrow", policy)
    assert rr.used == "floor" and rr.value == 0.09
    assert rr.without_goodwill is not None
    assert rr.without_goodwill.measure == pytest.approx(0.04)
    assert rr.without_goodwill.three_year is not None and rr.without_goodwill.three_year > 0.09


def test_a_measure_at_or_above_r_never_reads_the_return_without_goodwill(
    policy: Policy,
) -> None:
    rows = kept_with([(n, c, 500.0) for n, c in SPEC])
    rr = runway_return(rows, "Wide", policy)
    assert rr.used == "marginal" and rr.value == pytest.approx(0.20) and rr.flags == ()
    # recorded all the same, for the agent: the same change in NOPAT on the same change in capital
    assert rr.without_goodwill is not None
    assert rr.without_goodwill.measure == pytest.approx(0.20)
    at_r = runway_return(bought(1500.0, 180.0), "Narrow", policy)  # 9% with goodwill, 36% without
    assert at_r.used == "three-year" and at_r.value == pytest.approx(0.09) and at_r.flags == ()


def test_the_return_without_goodwill_is_recorded_only_with_five_kept_years(
    policy: Policy,
) -> None:
    short = runway_return(kept_with([(100.0, 2000.0, 1500.0)] * 4), "Wide", policy)
    assert short.used == "unavailable" and short.without_goodwill is None
    off = runway_return(kept([(20.0, -50.0)] * 10), "Wide", policy)
    assert off.used == "off" and off.without_goodwill is not None


@pytest.mark.parametrize(
    ("moat", "goodwill", "expected"),
    [
        ("Wide", 1500.0, 0.13),  # 20% without goodwill, capped at r plus the spread
        ("Wide", 2000.0 - 100 / 0.11, 0.11),  # 11% without goodwill
        ("Wide", 2100.0, 0.13),  # no capital without goodwill: the cap of 25%, then 13%
        ("Wide", 500.0, 0.09),  # the floor stands
        ("Narrow", 1500.0, 0.09),
        ("None", 1500.0, 0.09),
    ],
)
def test_the_terminal_return_follows_the_return_without_goodwill(
    policy: Policy, moat: Moat, goodwill: float, expected: float
) -> None:
    rr = runway_return(bought(goodwill), moat, policy)
    assert terminal_return(rr, moat, policy) == pytest.approx(expected)


def test_runway_note_names_the_return_without_goodwill(policy: Policy) -> None:
    measure = "three-year return on capital without goodwill and intangibles"
    was = "with them the three-year was 5.0%"
    cases = {
        1500.0: f"{measure}; {was}",
        1800.0: f"{measure}, 50.0%, capped; {was}",
        2100.0: f"the cap: capital without goodwill and intangibles at or below zero; {was}",
    }
    for goodwill, note in cases.items():
        assert runway_note(runway_return(bought(goodwill), "Narrow", policy)) == note


def test_the_intermediates_record_the_return_without_goodwill(policy: Policy) -> None:
    # 11 balance sheets: net PP&E 500 and goodwill 1,500, operating income 100, tax 0
    years = [replace(cy(2015 + k, oi=100.0, ppe=500.0), goodwill=1500.0) for k in range(11)]
    terms = RoicTerms.of(years, "Wide", policy)
    im = terms.intermediates()
    assert im["runway_return"]["used"] == "without-goodwill"
    assert im["runway_return"]["value"] == pytest.approx(0.20)
    assert im["runway_return"]["without_goodwill"] == {
        "marginal": None,
        "marginal_usable": False,
        "three_year": pytest.approx(0.20),
        "measure": pytest.approx(0.20),
        "capital_free": False,
        "bought": False,
    }
    assert im["terminal_roic"] == pytest.approx(0.13)
    assert im["roic"]["by_year"][-1]["average_goodwill_and_intangibles"] == pytest.approx(1500.0)
    assert [f.code for f in terms.flags] == ["return-without-goodwill"]
    short = RoicTerms.of(years[-4:], "Wide", policy)
    assert short.intermediates()["runway_return"]["without_goodwill"] is None


@pytest.mark.parametrize(
    ("override", "terminal"),
    [(0.09, 0.09), (0.11, 0.11), (0.20, 0.13), (0.05, 0.09)],
)
def test_an_override_on_a_return_without_goodwill_sets_the_terminal_return_too(
    policy: Policy, override: float, terminal: float
) -> None:
    """On a row the engine started at the return without goodwill, the agent's ``return.runway``
    moves the Wide moat's terminal return too: an agent who finds the growth is bought takes the
    whole lift back (method 14.4)."""
    years = [replace(cy(2015 + k, oi=100.0, ppe=500.0), goodwill=1500.0) for k in range(11)]
    terms = RoicTerms.of(years, "Wide", policy, runway_override=override)
    assert terms.runway_return.used == "without-goodwill" and terms.overridden
    assert terms.runway == override and terms.terminal == pytest.approx(terminal)
    assert terms.flags == terms.result.flags  # the measured return's flag is not raised
    assert RoicTerms.of(years, "Narrow", policy, runway_override=override).terminal == 0.09


def test_an_override_sets_the_terminal_return_by_the_moats_rule_on_every_measure(
    policy: Policy,
) -> None:
    """An agent's ``return.runway`` is the return in force, so the terminal return reads it by
    the moat's rule whatever the engine measured (the founder's ruling of 2026-11-15, B-170):
    Wide, the override under the cap and never below r; otherwise r. The terminal return then
    never stands above an agent's lower start, the same override gives a floored row and one
    just above r the same terminal return, and an override equals the return sensitivity at the
    same figure (method 5.8)."""
    years = [cy(2015 + k, oi=20.0 + 5 * k, ppe=100.0 + 10 * k) for k in range(11)]  # marginal 50%
    terms = RoicTerms.of(years, "Wide", policy, runway_override=0.10)
    assert terms.runway_return.used == "marginal" and terms.terminal == pytest.approx(0.10)
    assert RoicTerms.of(years, "Wide", policy, runway_override=0.30).terminal == 0.13
    assert RoicTerms.of(years, "Wide", policy, runway_override=0.05).terminal == 0.09
    low = [cy(2015 + k, oi=9.5, ppe=100.0) for k in range(11)]  # 9.5%: above r, under the cap
    above = RoicTerms.of(low, "Wide", policy, runway_override=0.15)
    assert above.runway_return.used == "three-year" and above.terminal == 0.13
    floored = [cy(2015 + k, oi=8.9, ppe=100.0) for k in range(11)]  # 8.9% and no goodwill
    below = RoicTerms.of(floored, "Wide", policy, runway_override=0.15)
    assert below.runway_return.used == "floor" and below.terminal == above.terminal
    off = [cy(2015 + k, oi=20.0, ppe=-50.0) for k in range(11)]
    assert RoicTerms.of(off, "Wide", policy, runway_override=0.10).terminal == pytest.approx(0.10)
    assert RoicTerms.of(years[-4:], "Wide", policy, runway_override=0.20).terminal == 0.13
    for measured in (years, low, floored, off, years[-4:]):  # no moat but Wide reads the override
        assert RoicTerms.of(measured, "Narrow", policy, runway_override=0.20).terminal == 0.09
        assert RoicTerms.of(measured, "None", policy, runway_override=0.20).terminal == 0.09


def test_no_override_leaves_the_terminal_return_on_the_measure(policy: Policy) -> None:
    years = [cy(2015 + k, oi=20.0 + 5 * k, ppe=100.0 + 10 * k) for k in range(11)]  # marginal 50%
    assert RoicTerms.of(years, "Wide", policy).terminal == 0.13
    low = [cy(2015 + k, oi=9.5, ppe=100.0) for k in range(11)]
    assert RoicTerms.of(low, "Wide", policy).terminal == pytest.approx(0.095)
    assert RoicTerms.of(years[-4:], "Wide", policy).terminal == 0.09  # unavailable: r


# NOPAT 100 on capital 1,000 and revenue 1,000, then in five years NOPAT 400 on capital 2,000 and
# revenue 2,000: the margin rose from 10% to 20%, so the marginal return of 30% counts 100 of
# margin gain on the revenue already there, and at the newest margin the capital added earned 20%
RISING_MARGIN = [(100, 1000), (160, 1200), (220, 1400), (280, 1600), (340, 1800), (400, 2000)]
REVENUE = {2017: 1000.0, 2018: 1200.0, 2019: 1400.0, 2020: 1600.0, 2021: 1800.0, 2022: 2000.0}


def test_the_return_at_a_constant_margin_leaves_the_margins_change_out(policy: Policy) -> None:
    by_year = kept(RISING_MARGIN).by_year
    assert runway_return(kept(RISING_MARGIN), "Wide", policy).marginal == pytest.approx(0.30)
    assert constant_margin_return(by_year, REVENUE, policy) == pytest.approx(0.20)
    # the newest margin times the revenue added over the capital added
    assert constant_margin_return(by_year, REVENUE, policy) == pytest.approx(
        (400 / 2000) * (2000 - 1000) / (2000 - 1000)
    )
    # a steady margin: the two measures agree
    steady = [(100 + 20 * k, 1000 + 200 * k) for k in range(6)]
    revenue = {2017 + k: 1000.0 + 200 * k for k in range(6)}
    assert constant_margin_return(kept(steady).by_year, revenue, policy) == pytest.approx(0.10)
    assert runway_return(kept(steady), "Wide", policy).marginal == pytest.approx(0.10)
    # a margin that fell reads above the marginal: 300 of NOPAT on 3,000 of revenue is 10%
    fell = [(200, 1000), (220, 1200), (240, 1400), (260, 1600), (280, 1800), (300, 2000)]
    wide = {2017 + k: 1000.0 + 400 * k for k in range(6)}
    assert constant_margin_return(kept(fell).by_year, wide, policy) == pytest.approx(0.20)
    assert runway_return(kept(fell), "Wide", policy).marginal == pytest.approx(0.10)


def test_the_return_at_a_constant_margin_holds_no_figure_without_its_terms(
    policy: Policy,
) -> None:
    by_year = kept(RISING_MARGIN).by_year
    assert constant_margin_return(by_year[1:], REVENUE, policy) is None  # five kept years
    for year in (2017, 2022):  # either end of the span without a revenue
        missing = {y: v for y, v in REVENUE.items() if y != year}
        assert constant_margin_return(by_year, missing, policy) is None
    assert constant_margin_return(by_year, {**REVENUE, 2022: 0.0}, policy) is None
    assert constant_margin_return(by_year, {**REVENUE, 2022: 900.0}, policy) is None  # it fell
    slow = [(n, 1000 + 30 * k) for k, (n, _) in enumerate(RISING_MARGIN)]  # capital grew 15%
    assert constant_margin_return(kept(slow).by_year, REVENUE, policy) is None
    shrinking = [(n, 2000 - 100 * k) for k, (n, _) in enumerate(RISING_MARGIN)]
    assert constant_margin_return(kept(shrinking).by_year, REVENUE, policy) is None
    # a loss in the newest year is still the arithmetic: shown, never used
    loss = [*RISING_MARGIN[:-1], (-100, 2000)]
    assert constant_margin_return(kept(loss).by_year, REVENUE, policy) == pytest.approx(-0.05)


def test_the_intermediates_record_the_return_at_a_constant_margin(policy: Policy) -> None:
    # 11 balance sheets, tax 0: NOPAT 20 + 5k on capital 100 + 10k, the average capital of the
    # kept year k (fiscal 2016 + k) 105 + 10k; revenue 1,000 + 100k
    years = [cy(2015 + k, oi=20.0 + 5 * k, ppe=100.0 + 10 * k) for k in range(11)]
    revenue = {2016 + k: 1000.0 + 100 * k for k in range(10)}
    terms = RoicTerms.of(years, "Wide", policy, revenue=revenue)
    # the newest margin 70 / 1,900, times 500 of revenue added on 50 of capital added
    expected = (70 / 1900) * 500 / 50
    assert terms.constant_margin == pytest.approx(expected)
    rr = terms.intermediates()["runway_return"]
    assert rr["constant_margin"] == pytest.approx(expected) and rr["marginal"] == pytest.approx(0.5)
    assert list(rr).index("constant_margin") == list(rr).index("one_year") + 1
    assert terms.runway == pytest.approx(0.5)  # shown, never used: the marginal still charges
    # an agent's override keeps the measured figure beside it
    judged = RoicTerms.of(years, "Wide", policy, runway_override=0.2, revenue=revenue)
    assert judged.constant_margin == pytest.approx(expected) and judged.runway == 0.2
    # no revenue passed, or too few kept years: no figure
    assert (
        RoicTerms.of(years, "Wide", policy).intermediates()["runway_return"]["constant_margin"]
        is None
    )
    assert RoicTerms.of(years[-4:], "Wide", policy, revenue=revenue).constant_margin is None
