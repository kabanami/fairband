from dataclasses import replace

import pytest

from fairband.engine.roic import (
    CapitalYear,
    RoicResult,
    aggregate_roic,
    invested_capital,
    nopat,
    not_presented,
    terminal_roic,
)
from fairband.policy import Policy, load_policy


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
    five = aggregate_roic(history(6))
    assert five.aggregate == pytest.approx(0.2) and five.flags[0].word == "ROIC on 5 years"
    assert aggregate_roic(history(5), min_years=4).aggregate == pytest.approx(0.2)


def test_no_usable_year_is_unavailable_not_zeroed() -> None:
    for years in ([], history(1)):
        r = aggregate_roic(years)
        assert r.aggregate is None and r.years_used == 0 and r.by_year == ()
        assert codes(r) == ("roic-unavailable",)


def test_negative_capital_zeroes_charge() -> None:
    r = aggregate_roic(history(11, ppe=-50.0))
    assert r.aggregate is None and r.years_used == 10
    assert codes(r) == ("charge-zeroed",)
    short = aggregate_roic(history(8, ppe=-50.0))
    assert short.aggregate is None and codes(short) == ("roic-on-n-years", "charge-zeroed")


def test_zero_capital_does_not_divide_by_zero() -> None:
    years = [cy(2015 + i, ppe=50.0 if i % 2 else -50.0) for i in range(11)]  # every average is 0
    r = aggregate_roic(years)
    assert r.aggregate is None and codes(r) == ("charge-zeroed",)
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
    other = replace(policy, required_return=0.10, wide_terminal_roic_cap=0.15)
    assert terminal_roic(0.25, "Wide", other) == 0.15
    assert terminal_roic(0.05, "Wide", other) == 0.10
    assert terminal_roic(0.25, "Narrow", other) == 0.10
