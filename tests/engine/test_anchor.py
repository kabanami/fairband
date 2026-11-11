from dataclasses import replace
from datetime import date, timedelta

import pytest

from fairband.engine.anchor import (
    AnnualEstimate,
    Belief,
    QuarterEstimate,
    TrailingFigures,
    base_fiscal_year,
    base_year,
    belief_from_sales,
    consecutive_periods,
    moat_class,
    ntm_anchor,
    ntm_periods,
    ntm_quarters,
    ntm_window,
    path_steps,
    sales_class,
    sbc_basis,
    step_series_flag,
)
from fairband.engine.types import Flag
from fairband.policy import Policy, load_policy


@pytest.fixture
def policy() -> Policy:
    return load_policy()


def q(
    pe: str,
    fy: int,
    fp: str,
    eps: float | None,
    rev: float | None = None,
    ni: float | None = None,
    n: int | None = 10,
) -> QuarterEstimate:
    return QuarterEstimate(date.fromisoformat(pe), fy, fp, eps, rev, ni, n)


def a(
    fy: int,
    eps: float | None,
    ni: float | None = None,
    n_eps: int | None = 10,
    n_ni: int | None = 10,
) -> AnnualEstimate:
    return AnnualEstimate(fy, date(fy, 12, 31), eps, None, ni, n_eps, n_ni)


def _annual(
    base: int,
    *,
    net_income: tuple[float | None, ...] = (None, None, None),
    eps: tuple[float | None, ...] = (None, None, None),
    revenue: tuple[float | None, ...] = (None, None, None),
    analysts: int | None = 10,
) -> list[AnnualEstimate]:
    """The consensus years from ``base``, each series year by year, every count ``analysts``."""
    return [
        AnnualEstimate(base + k, date(base + k, 12, 31), e, rev, ni, analysts, analysts, analysts)
        for k, (e, rev, ni) in enumerate(zip(eps, revenue, net_income, strict=True))
    ]


def trailing(
    revenue: float | None = 100.0, eps: float | None = 4.0, sbc: float | None = 10.0
) -> TrailingFigures:
    return TrailingFigures(
        period_end=date(2026, 6, 30),
        quarters=4,
        on_fiscal_year=False,
        revenue=revenue,
        operating_income=None,
        net_income=None,
        eps_diluted=eps,
        sbc=sbc,
        cfo=None,
        capex=None,
        dividends=None,
        buybacks=None,
        equity_issued=None,
    )


def ntm(eps: float | None = 2.5, rev: float | None = 30.0) -> list[QuarterEstimate]:
    """Four NTM quarters after 2026-06-30, each with ``eps`` and ``rev``."""
    return [
        q("2026-09-30", 2027, "Q1", eps, rev),
        q("2026-12-31", 2027, "Q2", eps, rev),
        q("2027-03-31", 2027, "Q3", eps, rev),
        q("2027-06-30", 2027, "Q4", eps, rev),
    ]


def codes(flags: tuple[Flag, ...]) -> list[str]:
    return [f.code for f in flags]


def test_ntm_quarters_picks_by_period_not_order() -> None:
    far = [
        q("2029-03-31", 2029, "Q3", 9),
        q("2026-12-31", 2027, "Q2", 1),
        q("2026-09-30", 2027, "Q1", 1),
        q("2027-06-30", 2027, "Q4", 1),
        q("2027-03-31", 2027, "Q3", 1),
        q("2028-09-30", 2029, "Q1", 5),
    ]
    got = ntm_quarters(far, date(2026, 6, 30))
    assert got is not None
    assert [x.period_end.isoformat() for x in got] == [
        "2026-09-30",
        "2026-12-31",
        "2027-03-31",
        "2027-06-30",
    ]


def test_ntm_quarters_skips_reported_quarters() -> None:
    rows = [q("2026-06-30", 2026, "Q4", 1), q("2026-03-31", 2026, "Q3", 1), *ntm()]
    got = ntm_quarters(rows, date(2026, 6, 30))
    assert got is not None and got[0].period_end == date(2026, 9, 30)


@pytest.mark.parametrize(("days", "first"), [(7, date(2026, 9, 30)), (8, date(2026, 7, 8))])
def test_ntm_quarters_skip_a_row_within_a_week_after_the_last_reported(
    days: int, first: date
) -> None:
    """A row ending up to seven days after the last reported quarter is that quarter under a
    second fiscal calendar, not the first NTM quarter; a row a day later starts the chain."""
    after = date(2026, 6, 30) + timedelta(days=days)
    got = ntm_quarters([q(str(after), 2026, "Q4", 1), *ntm()], date(2026, 6, 30))
    assert got is not None and got[0].period_end == first


def test_ntm_quarters_none_when_gap() -> None:
    gap = [
        q("2026-09-30", 2027, "Q1", 1),
        q("2026-12-31", 2027, "Q2", 1),
        q("2027-06-30", 2027, "Q4", 1),
        q("2027-09-30", 2028, "Q1", 1),
    ]
    assert ntm_quarters(gap, date(2026, 6, 30)) is None


def test_ntm_quarters_none_when_fewer_than_four() -> None:
    assert ntm_quarters(ntm()[:3], date(2026, 6, 30)) is None


def half(end: date, fy: int, eps: float | None = 1.0, rev: float | None = 30.0) -> QuarterEstimate:
    """A half-year of consensus with ``eps`` and ``rev``."""
    return QuarterEstimate(end, fy, "H1" if end.month <= 6 else "H2", eps, rev, None, 10)


# Spec 2026-11-10 11.4: after a last reported half-year ending 2026-06-30.
HALVES = [
    half(date(2026, 6, 30), 2026),
    half(date(2026, 12, 31), 2026),
    half(date(2027, 6, 30), 2027),
    half(date(2027, 12, 31), 2027),
]


def test_consecutive_periods_reads_the_cadence_s_bounds() -> None:
    """80 to 100 days from one quarter end to the next, 170 to 195 from one half-year's."""
    start = date(2026, 1, 1)

    def apart(days: int) -> list[date]:
        return [start, start + timedelta(days=days)]

    assert all(consecutive_periods(apart(d), "quarterly") for d in (80, 91, 100))
    assert not any(consecutive_periods(apart(d), "quarterly") for d in (79, 101, 181))
    assert all(consecutive_periods(apart(d), "half-yearly") for d in (170, 181, 195))
    assert not any(consecutive_periods(apart(d), "half-yearly") for d in (91, 169, 196))


def test_ntm_periods_half_yearly() -> None:
    """Spec 2026-11-10 11.4: the consensus rows ending 2026-12-31 and 2027-06-30 are the window;
    the base fiscal year is 2027, one each and the tie to the later. The quarterly reading finds
    no window in them, and one row after the last reported is no window."""
    window = ntm_periods(HALVES, date(2026, 6, 30), "half-yearly")
    assert window is not None
    assert [q.period_end for q in window] == [date(2026, 12, 31), date(2027, 6, 30)]
    assert base_fiscal_year(window) == 2027
    assert ntm_periods(HALVES, date(2026, 6, 30), "quarterly") is None
    assert ntm_periods(HALVES[:2], date(2026, 6, 30), "half-yearly") is None


def test_ntm_quarters_is_the_quarterly_reading() -> None:
    assert ntm_quarters(ntm(), date(2026, 6, 30)) == ntm_periods(
        ntm(), date(2026, 6, 30), "quarterly"
    )
    assert ntm_periods(ntm(), date(2026, 6, 30), "half-yearly") is None


def test_a_quarterly_reporter_never_reads_a_half_year_window() -> None:
    """The ruling on spec 2026-11-10 8: a quarterly reporter's window is four consecutive
    quarters only, so consensus rows about 180 days apart give it none (two quarters of a
    consensus with gaps would otherwise sum as a year); a half-yearly reporter reads them as its
    two half-years."""
    assert ntm_window(HALVES, date(2026, 6, 30), "quarterly") is None
    assert base_year(HALVES, date(2026, 6, 30)) is None
    found = ntm_window(HALVES, date(2026, 6, 30), "half-yearly")
    assert found is not None
    window, cadence = found
    assert cadence == "half-yearly"
    assert [q.period_end for q in window] == [date(2026, 12, 31), date(2027, 6, 30)]
    assert base_year(HALVES, date(2026, 6, 30), "half-yearly") == 2027


def test_a_quarter_beside_the_pair_rules_out_a_half_year_window() -> None:
    """The window's gap guard (WSE's consensus: quarters with 2027-06-30 missing). After a last
    reported 2026-12-31 the first two rows, 2027-03-31 and 2027-09-30, are 183 days apart, but the
    row ending 2027-12-31 sits 92 days from the second: they are quarters, not half-years, so a
    half-yearly reporter reads no half-year window, and no four consecutive quarters either. With
    the missing quarter on file the four quarters stand."""
    last = date(2026, 12, 31)
    rows = [
        q("2027-03-31", 2027, "Q1", 1),
        q("2027-09-30", 2027, "Q3", 1),
        q("2027-12-31", 2027, "Q4", 1),
        q("2028-03-31", 2028, "Q1", 1),
    ]
    assert ntm_periods(rows, last, "half-yearly") is not None  # the pair alone reads as halves
    assert ntm_window(rows, last, "half-yearly") is None
    assert base_year(rows, last, "half-yearly") is None
    full = [*rows, q("2027-06-30", 2027, "Q2", 1)]
    found = ntm_window(full, last, "half-yearly")
    assert found is not None and found[1] == "quarterly"
    assert [x.period_end.isoformat() for x in found[0]] == [
        "2027-03-31",
        "2027-06-30",
        "2027-09-30",
        "2027-12-31",
    ]


def test_a_half_yearly_reporter_with_quarterly_consensus_reads_four_quarters() -> None:
    """ABVX (spec 2026-11-10 8): half-year statements and quarterly consensus rows. The window is
    the one its consensus cadence gives, four consecutive quarters, with the cadence
    ``quarterly``; the base year is theirs."""
    found = ntm_window(ntm(), date(2026, 6, 30), "half-yearly")
    assert found is not None
    window, cadence = found
    assert cadence == "quarterly" and list(window) == ntm()
    assert ntm_window(ntm(), date(2026, 6, 30), "quarterly") == (tuple(ntm()), "quarterly")
    assert base_year(ntm(), date(2026, 6, 30), "half-yearly") == 2027
    assert ntm_window(ntm()[:3], date(2026, 6, 30), "half-yearly") is None


def test_sbc_basis() -> None:
    assert sbc_basis(5.0, 4.0, 1.5, 0.5) == "excludes-sbc"  # gap 1.0 ≥ 0.75
    assert sbc_basis(4.2, 4.0, 1.5, 0.5) == "includes-sbc"
    assert sbc_basis(None, 4.0, 1.5, 0.5) == "unknown"
    assert sbc_basis(5.0, None, 1.5, 0.5) == "unknown"
    assert sbc_basis(5.0, 4.0, None, 0.5) == "unknown"


def test_anchor_subtracts_sbc_scaled_by_revenue(policy: Policy) -> None:
    # SBC after tax per share = 10 × 0.79 ÷ 10 = 0.79; NTM revenue 120 against trailing 100.
    got = ntm_anchor(ntm(), trailing(), 5.0, 10.0, 0.21, 100.0, policy)
    assert got.basis == "excludes-sbc"
    assert got.ntm_eps_raw == pytest.approx(10.0)
    assert got.sbc_adjustment_per_share == pytest.approx(0.948)
    assert got.ntm_eps == pytest.approx(9.052)
    assert got.ntm_net_income == pytest.approx(90.52)
    assert got.flags == () and got.refusal is None


def test_anchor_unscaled_without_ntm_revenue(policy: Policy) -> None:
    quarters = [*ntm()[:3], q("2027-06-30", 2027, "Q4", 2.5, None)]
    got = ntm_anchor(quarters, trailing(), 5.0, 10.0, 0.21, 100.0, policy)
    assert got.sbc_adjustment_per_share == pytest.approx(0.79)


def test_anchor_unscaled_without_trailing_revenue(policy: Policy) -> None:
    for rev in (None, 0.0):
        got = ntm_anchor(ntm(), trailing(revenue=rev), 5.0, 10.0, 0.21, 100.0, policy)
        assert got.sbc_adjustment_per_share == pytest.approx(0.79)


def test_anchor_keeps_consensus_that_includes_sbc(policy: Policy) -> None:
    got = ntm_anchor(ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy)
    assert got.basis == "includes-sbc"
    assert got.sbc_adjustment_per_share == 0.0 and got.ntm_eps == pytest.approx(10.0)
    assert got.flags == ()


def test_anchor_flags_unknown_basis(policy: Policy) -> None:
    for t, street in ((trailing(), None), (trailing(sbc=None), 5.0), (trailing(eps=None), 5.0)):
        got = ntm_anchor(ntm(), t, street, 10.0, 0.21, 100.0, policy)
        assert got.basis == "unknown"
        assert got.sbc_adjustment_per_share == 0.0 and got.ntm_eps == pytest.approx(10.0)
        assert codes(got.flags) == ["sbc-basis-unknown"] and got.refusal is None


def test_anchor_refusals(policy: Policy) -> None:
    incomplete = [*ntm()[:3], q("2027-06-30", 2027, "Q4", None, 30.0)]
    got = ntm_anchor(incomplete, trailing(), 4.2, 10.0, 0.21, 100.0, policy)
    assert got.refusal == "incomplete NTM consensus"
    assert ntm_anchor(ntm()[:3], trailing(), 4.2, 10.0, 0.21, 100.0, policy).refusal == (
        "incomplete NTM consensus"
    )

    loss = ntm(eps=-0.5)
    got = ntm_anchor(loss, trailing(), 4.2, 10.0, 0.21, 100.0, policy)
    assert got.refusal == "no positive forward anchor"
    # The SBC adjustment can take a positive consensus below zero: 0.60 − 0.79.
    wiped = ntm(eps=0.15, rev=25.0)
    got = ntm_anchor(wiped, trailing(), 5.0, 10.0, 0.21, 100.0, policy)
    assert got.ntm_eps_raw == pytest.approx(0.60) and got.ntm_eps == pytest.approx(-0.19)
    assert got.refusal == "no positive forward anchor"

    got = ntm_anchor(ntm(eps=0.25), trailing(), 4.2, 10.0, 0.21, 1.0, policy)  # P/E 1
    assert got.refusal == "forward P/E below 2: unit error"
    assert ntm_anchor(ntm(eps=0.25), trailing(), 4.2, 10.0, 0.21, 2.0, policy).refusal is None


def test_ntm_anchor_sums_two_half_years(policy: Policy) -> None:
    """Two half-years at EPS 1.0 and 1.2: the raw anchor is 2.2 on the half-yearly cadence and
    the count check asks for two; the quarterly cadence, the default, refuses them, and four
    quarters on the half-yearly one are refused too."""
    halves = [half(date(2026, 12, 31), 2026, 1.0), half(date(2027, 6, 30), 2027, 1.2)]
    got = ntm_anchor(halves, trailing(), 4.2, 10.0, 0.21, 100.0, policy, cadence="half-yearly")
    assert got.ntm_eps_raw == pytest.approx(2.2) and got.refusal is None
    assert got.ntm_eps == pytest.approx(2.2) and got.ntm_net_income == pytest.approx(22.0)
    quarterly = ntm_anchor(halves, trailing(), 4.2, 10.0, 0.21, 100.0, policy)
    assert quarterly.refusal == "incomplete NTM consensus"
    four = ntm_anchor(ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, cadence="half-yearly")
    assert four.refusal == "incomplete NTM consensus"
    gap = [half(date(2026, 12, 31), 2026, 1.0), half(date(2027, 6, 30), 2027, None)]
    got = ntm_anchor(gap, trailing(), 4.2, 10.0, 0.21, 100.0, policy, cadence="half-yearly")
    assert got.refusal == "incomplete NTM consensus"


def test_the_sbc_scale_reads_the_two_half_years_revenue(policy: Policy) -> None:
    """The SBC adjustment's scale is the window's revenue over the trailing revenue, as on four
    quarters: two half-years of 60 against 100 scale 0.79 a share to 0.948."""
    halves = [half(date(2026, 12, 31), 2026, 5.0, 60.0), half(date(2027, 6, 30), 2027, 5.0, 60.0)]
    got = ntm_anchor(halves, trailing(), 5.0, 10.0, 0.21, 100.0, policy, cadence="half-yearly")
    assert got.basis == "excludes-sbc"
    assert got.sbc_adjustment_per_share == pytest.approx(0.948)
    assert got.ntm_eps == pytest.approx(9.052)


def test_a_cycle_gap_lowers_the_anchor_and_stays_out_of_the_basis_test(policy: Policy) -> None:
    """An agent's cycle gap comes off the NTM EPS after the SBC adjustment, and the refusals read
    the lowered figure; the basis test reads trailing GAAP EPS as reported, where GAAP less 3.00
    would leave the street's 4.20 above it by 3.20 and switch the basis."""
    found = ntm_anchor(ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy)
    got = ntm_anchor(ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, cycle_gap=3.0)
    assert got.basis == found.basis == "includes-sbc"
    assert got.ntm_eps_raw == found.ntm_eps_raw == pytest.approx(10.0)
    assert got.ntm_eps == pytest.approx(7.0) and got.ntm_net_income == pytest.approx(70.0)
    assert got.ntm_eps_found == found.ntm_eps == found.ntm_eps_found
    excludes = ntm_anchor(ntm(), trailing(), 5.0, 10.0, 0.21, 100.0, policy, cycle_gap=1.0)
    assert excludes.ntm_eps_found == pytest.approx(9.052)
    assert excludes.ntm_eps == pytest.approx(8.052)
    wiped = ntm_anchor(ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, cycle_gap=10.0)
    assert wiped.refusal == "no positive forward anchor"
    # a trough lifted to mid-cycle: a loss consensus of −2.00 and a cycle gap of −3.00
    lifted = ntm_anchor(ntm(eps=-0.5), trailing(), 4.2, 10.0, 0.21, 100.0, policy, cycle_gap=-3.0)
    assert lifted.ntm_eps == pytest.approx(1.0) and lifted.refusal is None


def test_the_unit_error_check_reads_the_consensus_as_found(policy: Policy) -> None:
    """The check is on the vendor's units: a cycle gap of −50.00 on a consensus of 10.00 at $100
    takes the forward P/E to 1.7, which is no unit error; a consensus of 1.00 at $1, a P/E of 1, is
    refused under a gap of 0.50 that would read 2."""
    raised = ntm_anchor(ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, cycle_gap=-50.0)
    assert raised.ntm_eps == pytest.approx(60.0) and raised.refusal is None
    unit = ntm_anchor(ntm(eps=0.25), trailing(), 4.2, 10.0, 0.21, 1.0, policy, cycle_gap=0.5)
    assert unit.ntm_eps == pytest.approx(0.5)
    assert unit.refusal == "forward P/E below 2: unit error"


def test_base_fiscal_year_tie_takes_later() -> None:
    qs = [
        q("2026-09-30", 2026, "Q4", 1),
        q("2026-12-31", 2027, "Q1", 1),
        q("2027-03-31", 2027, "Q2", 1),
        q("2027-06-30", 2027, "Q3", 1),
    ]
    assert base_fiscal_year(qs) == 2027
    tie = [
        q("2026-06-30", 2026, "Q3", 1),
        q("2026-09-30", 2026, "Q4", 1),
        q("2026-12-31", 2027, "Q1", 1),
        q("2027-03-31", 2027, "Q2", 1),
    ]
    assert base_fiscal_year(tie) == 2027
    most = [
        q("2026-03-31", 2026, "Q2", 1),
        q("2026-06-30", 2026, "Q3", 1),
        q("2026-09-30", 2026, "Q4", 1),
        q("2026-12-31", 2027, "Q1", 1),
    ]
    assert base_fiscal_year(most) == 2026


def test_path_on_net_income_then_eps_fallback(policy: Policy) -> None:
    # net income 18% and 25% against EPS 20% and 25%: inside the step-series gap
    annual = [a(2027, 2.0, 200.0), a(2028, 2.4, 236.0), a(2029, 3.0, 295.0)]
    got = path_steps(annual, 2027, policy)
    assert got.steps == pytest.approx((0.18, 0.25))
    assert not got.on_eps and got.flags == ()

    no_ni = [a(2027, 2.0), a(2028, 2.4, 236.0), a(2029, 3.0, 295.0)]
    got = path_steps(no_ni, 2027, policy)
    assert got.steps == pytest.approx((0.20, 0.25))
    assert got.on_eps and codes(got.flags) == ["path-on-eps"]

    loss_ni = [a(2027, 2.0, -5.0), a(2028, 2.4, 236.0), a(2029, 3.0, 295.0)]
    assert path_steps(loss_ni, 2027, policy).on_eps


def test_path_carries_the_revenue_steps(policy: Policy) -> None:
    annual = _annual(
        2027,
        revenue=(1000.0, 1150.0, 1265.0),
        net_income=(100.0, 125.0, 150.0),
        eps=(1.0, 1.25, 1.5),
        analysts=20,
    )
    path = path_steps(annual, 2027, policy)
    assert path.revenue_steps == pytest.approx((0.15, 0.10))
    assert path.steps == pytest.approx((0.25, 0.20))
    # the same base year: a year before it is not read
    earlier = [AnnualEstimate(2026, date(2026, 12, 31), 0.5, 500.0, 50.0, 20, 20, 20), *annual]
    assert path_steps(earlier, 2027, policy).revenue_steps == pytest.approx((0.15, 0.10))
    # on the EPS path too
    on_eps = [replace(x, net_income=None) for x in annual]
    assert path_steps(on_eps, 2027, policy).revenue_steps == pytest.approx((0.15, 0.10))


def test_a_missing_or_non_positive_revenue_leaves_the_step_none(policy: Policy) -> None:
    earnings = {"net_income": (100.0, 125.0, 150.0), "eps": (1.0, 1.25, 1.5)}
    middle = _annual(2027, revenue=(1000.0, None, 1265.0), **earnings)
    assert path_steps(middle, 2027, policy).revenue_steps == (None, None)

    base_zero = _annual(2027, revenue=(0.0, 1150.0, 1265.0), **earnings)
    got = path_steps(base_zero, 2027, policy).revenue_steps
    assert got[0] is None and got[1] == pytest.approx(0.10)

    base_negative = _annual(2027, revenue=(-10.0, 1150.0, 1265.0), **earnings)
    assert path_steps(base_negative, 2027, policy).revenue_steps[0] is None

    # a mean of zero is a fall to zero with revenue analysts, and no estimate without them
    zero = _annual(2027, revenue=(1000.0, 0.0, 1265.0), **earnings)
    assert path_steps(zero, 2027, policy).revenue_steps == (-1.0, None)
    no_count = [replace(x, analysts_revenue=None) for x in zero]
    assert path_steps(no_count, 2027, policy).revenue_steps == (None, None)

    short = _annual(2027, revenue=(1000.0, 1150.0), net_income=(100.0, 125.0), eps=(1.0, 1.25))
    got = path_steps(short, 2027, policy).revenue_steps
    assert got[0] == pytest.approx(0.15) and got[1] is None

    assert path_steps([], 2027, policy).revenue_steps == (None, None)


def test_step_series_disagree_names_both_rates(policy: Policy) -> None:
    # spec 2026-11-09 13.4: net income 8.33 to 10.00 and EPS 0.83 to 1.10, on 10.0 bn shares
    annual = _annual(2027, net_income=(8.33e9, 10.0e9, 12.0e9), eps=(0.83, 1.10, 1.32), analysts=20)
    path = path_steps(annual, 2027, policy)
    assert path.flags == ()  # the route raises the note, with the diluted count it holds
    assert path.net_income_means == (8.33e9, 10.0e9, 12.0e9)
    assert path.eps_means == (0.83, 1.10, 1.32)
    note = step_series_flag(path, 10.0e9, policy)
    assert note is not None
    assert "Step 2 reads 20.0% on net income and 32.5% on EPS" in note.sentence
    assert "Step 3" not in note.sentence  # 20.0% against 20.0%
    assert note == Flag(
        "step-series-disagree",
        "Step series disagree",
        "Step 2 reads 20.0% on net income and 32.5% on EPS: the two consensus series imply "
        "different share counts (10.0B and 9.1B against the diluted count 10.0B). The path is on "
        "net income; `path.step_2` decides.",
    )
    assert path.steps == pytest.approx((10.0 / 8.33 - 1, 0.20))  # the path stays on net income


def test_step_series_disagree_names_each_step_and_the_series_the_path_is_on(
    policy: Policy,
) -> None:
    both = _annual(2027, net_income=(8.33e9, 10.0e9, 12.0e9), eps=(0.83, 1.10, 1.21))
    note = step_series_flag(path_steps(both, 2027, policy), 9.5e9, policy)
    assert note is not None and note.sentence == (
        "Step 2 reads 20.0% on net income and 32.5% on EPS: the two consensus series imply "
        "different share counts (10.0B and 9.1B against the diluted count 9.5B); step 3 reads "
        "20.0% on net income and 10.0% on EPS: the two consensus series imply different share "
        "counts (9.1B and 9.9B against the diluted count 9.5B). The path is on net income; "
        "`path.step_2` and `path.step_3` decide."
    )

    # no net income for fiscal 2029: the path is on EPS, and step 2 still reads both series
    on_eps = _annual(2027, net_income=(100e6, 125e6, None), eps=(1.0, 1.10, 1.21), analysts=3)
    path = path_steps(on_eps, 2027, policy)
    assert codes(path.flags) == ["path-on-eps", "few-analysts"]
    note = step_series_flag(path, 110e6, policy)
    assert note is not None and note.sentence == (
        "Step 2 reads 25.0% on net income and 10.0% on EPS: the two consensus series imply "
        "different share counts (100.0M and 113.6M against the diluted count 110.0M). The path "
        "is on EPS; `path.step_2` decides."
    )


def test_step_series_disagree_names_only_the_steps_the_consensus_still_gives(
    policy: Policy,
) -> None:
    """A step an override replaced drops its own clause, as ``few-analysts`` names only the steps
    the consensus still gives; the other step's clause stands."""
    path = path_steps(
        _annual(2027, net_income=(8.33e9, 10.0e9, 12.0e9), eps=(0.83, 1.10, 1.21)), 2027, policy
    )
    third = step_series_flag(path, 9.5e9, policy, (False, True))
    assert third is not None and third.sentence == (
        "Step 3 reads 20.0% on net income and 10.0% on EPS: the two consensus series imply "
        "different share counts (9.1B and 9.9B against the diluted count 9.5B). The path is on "
        "net income; `path.step_3` decides."
    )
    second = step_series_flag(path, 9.5e9, policy, (True, False))
    assert second is not None and second.sentence.endswith("`path.step_2` decides.")
    assert "step 3" not in second.sentence
    assert step_series_flag(path, 9.5e9, policy, (False, False)) is None


def test_step_series_disagree_without_a_count_for_the_landing_year(policy: Policy) -> None:
    # a counted EPS mean of zero implies no share count, and a fall of 100%
    annual = _annual(2027, net_income=(100e6, 120e6, 150e6), eps=(1.0, 0.0, 1.5))
    note = step_series_flag(path_steps(annual, 2027, policy), 100e6, policy)
    assert note is not None and note.sentence == (
        "Step 2 reads 20.0% on net income and −100.0% on EPS: the two consensus series imply "
        "different share counts. The path is on net income; `path.step_2` decides."
    )


def test_step_series_within_the_gap_is_silent(policy: Policy) -> None:
    # 20.0% against 24.0%, then 20.0% against 20.0%
    annual = _annual(2027, net_income=(100e6, 120e6, 144e6), eps=(1.0, 1.24, 1.488))
    path = path_steps(annual, 2027, policy)
    assert path.flags == () and step_series_flag(path, 100e6, policy) is None
    # one series alone gives no comparison
    no_eps = _annual(2027, net_income=(100e6, 150e6, 225e6), eps=(None, None, None))
    assert step_series_flag(path_steps(no_eps, 2027, policy), 100e6, policy) is None


def test_a_gap_of_exactly_the_tolerance_is_silent_on_both_steps(policy: Policy) -> None:
    """Five points apart on each step: binary floating point puts step 2's gap a hair above 0.05
    (20% is 0.19999999999999996) and step 3's a hair below, so a bare comparison fires on one
    step and not the other; within 1e-12 of the gap both are silent."""
    annual = _annual(2027, net_income=(100e6, 120e6, 132e6), eps=(1.0, 1.25, 1.4375))
    path = path_steps(annual, 2027, policy)
    (g2, g3), (h2, h3) = path.steps, (0.25, 0.15)
    assert g2 is not None and g3 is not None
    assert abs(g2 - h2) > policy.step_series_gap_max > abs(g3 - h3)
    assert step_series_flag(path, 100e6, policy) is None


def test_path_analysts_follow_the_series(policy: Policy) -> None:
    annual = [
        a(2027, 2.0, 200.0, n_eps=30, n_ni=20),
        a(2028, 2.4, 220.0, n_eps=31, n_ni=21),
        a(2029, 3.0, 264.0, n_eps=32, n_ni=22),
    ]
    assert path_steps(annual, 2027, policy).analysts == (21, 22)
    on_eps = [replace(x, net_income=None) for x in annual]
    assert path_steps(on_eps, 2027, policy).analysts == (31, 32)


def test_path_few_analysts_flag(policy: Policy) -> None:
    annual = [a(2027, 2.0, 200.0), a(2028, 2.4, 236.0), a(2029, 3.0, 295.0, n_ni=3)]
    got = path_steps(annual, 2027, policy)
    assert got.analysts == (10, 3) and codes(got.flags) == ["few-analysts"]

    unknown = [a(2027, 2.0, 200.0), a(2028, 2.4, 236.0, n_ni=None), a(2029, 3.0, 295.0, n_ni=4)]
    assert codes(path_steps(unknown, 2027, policy).flags) == ["few-analysts"]

    enough = [a(2027, 2.0, 200.0), a(2028, 2.4, 236.0, n_ni=5), a(2029, 3.0, 295.0, n_ni=5)]
    assert path_steps(enough, 2027, policy).flags == ()


def test_path_step_none_where_the_consensus_stops(policy: Policy) -> None:
    short = [a(2027, 2.0), a(2028, 2.4)]
    got = path_steps(short, 2027, policy)
    assert got.steps[0] == pytest.approx(0.20) and got.steps[1] is None
    assert got.analysts == (10, None)

    empty_year = [a(2027, 2.0), a(2028, 2.4), a(2029, 0.0, n_eps=0)]
    got = path_steps(empty_year, 2027, policy)
    assert got.steps[0] == pytest.approx(0.20) and got.steps[1] is None
    assert codes(got.flags) == ["path-on-eps"]

    gap = [a(2027, 2.0), a(2028, 0.0, n_eps=None), a(2029, 3.0)]
    assert path_steps(gap, 2027, policy).steps == (None, None)

    assert path_steps([], 2027, policy).steps == (None, None)


def test_belief_from_sales(policy: Policy) -> None:
    got = belief_from_sales(400_000, policy)
    # 0.033 + 0.02 is 0.053000000000000005 in binary floating point.
    assert got == Belief(pytest.approx(0.053), ">$50,000 Mn", 0.033)
    assert belief_from_sales(100, policy).sales_class == "$0-325 Mn"
    assert belief_from_sales(325, policy).sales_class == "$0-325 Mn"
    assert belief_from_sales(325.5, policy).sales_class == "$325-700 Mn"
    # The cap on the revenue-growth route's held rate reads the same class and leaves the belief
    # as it was; 0.044 + 0.02 is 0.064 to within binary floating point.
    assert belief_from_sales(10_000, policy) == Belief(
        pytest.approx(0.064), "$7,000-12,000 Mn", 0.044
    )


def test_sales_class_is_the_first_whose_upper_bound_holds_the_revenue(policy: Policy) -> None:
    assert sales_class(324.9, policy).label == "$0-325 Mn"
    assert sales_class(325.0, policy).label == "$0-325 Mn"
    assert sales_class(325.1, policy).label == "$325-700 Mn"
    assert sales_class(1e9, policy).label == ">$50,000 Mn"
    assert sales_class(10_000, policy) == policy.base_rates[7]


def test_moat_class(policy: Policy) -> None:
    assert moat_class(8, policy) == "Wide"
    assert moat_class(7.9, policy) == "Narrow"
    assert moat_class(4, policy) == "Narrow"
    assert moat_class(3, policy) == "None"
    assert moat_class(None, policy) == "None"
