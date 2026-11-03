from dataclasses import replace
from datetime import date

import pytest

from fairband.engine.anchor import (
    AnnualEstimate,
    Belief,
    QuarterEstimate,
    TrailingFigures,
    base_fiscal_year,
    belief_from_sales,
    moat_class,
    ntm_anchor,
    ntm_quarters,
    path_steps,
    sales_class,
    sbc_basis,
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
    annual = [a(2027, 2.0, 200.0), a(2028, 2.4, 220.0), a(2029, 3.0, 264.0)]
    got = path_steps(annual, 2027, policy)
    assert got.steps == pytest.approx((0.10, 0.20))
    assert not got.on_eps and got.flags == ()

    no_ni = [a(2027, 2.0), a(2028, 2.4, 220.0), a(2029, 3.0, 264.0)]
    got = path_steps(no_ni, 2027, policy)
    assert got.steps == pytest.approx((0.20, 0.25))
    assert got.on_eps and codes(got.flags) == ["path-on-eps"]

    loss_ni = [a(2027, 2.0, -5.0), a(2028, 2.4, 220.0), a(2029, 3.0, 264.0)]
    assert path_steps(loss_ni, 2027, policy).on_eps


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
    annual = [a(2027, 2.0, 200.0), a(2028, 2.4, 220.0), a(2029, 3.0, 264.0, n_ni=3)]
    got = path_steps(annual, 2027, policy)
    assert got.analysts == (10, 3) and codes(got.flags) == ["few-analysts"]

    unknown = [a(2027, 2.0, 200.0), a(2028, 2.4, 220.0, n_ni=None), a(2029, 3.0, 264.0, n_ni=4)]
    assert codes(path_steps(unknown, 2027, policy).flags) == ["few-analysts"]

    enough = [a(2027, 2.0, 200.0), a(2028, 2.4, 220.0, n_ni=5), a(2029, 3.0, 264.0, n_ni=5)]
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
