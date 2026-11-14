"""The distress measures of spec 2026-11-03 sections 10.6 to 10.8: the synthetic rating and π by
the rule order of 10.7 and the table edges of section 12, Altman Z″ on the worked lines, Piotroski
F on two hand-built years, and the net current asset value."""

from dataclasses import replace
from datetime import date

import pytest

from fairband.engine.balance import BalanceYear, NewestSheet
from fairband.engine.distress import (
    FScore,
    Rating,
    altman_z,
    ncav,
    piotroski_f,
    rate,
)
from fairband.policy import load_policy

POLICY = load_policy()

# Working capital 100, retained earnings 200, operating income 60, equity 400, total liabilities
# 500, total assets 1,000: the worked lines of the Z″ test.
YEAR = BalanceYear(
    year=2025,
    period_end=date(2025, 12, 31),
    total_current_assets=300.0,
    total_current_liabilities=200.0,
    total_assets=1000.0,
    total_liabilities=500.0,
    retained_earnings=200.0,
    equity=400.0,
    long_term_debt=200.0,
    revenue=1100.0,
    gross_profit=330.0,
    operating_income=60.0,
    net_income=50.0,
    cfo=80.0,
    stock_issued=0.0,
)
LAST = replace(
    YEAR,
    year=2024,
    period_end=date(2024, 12, 31),
    total_current_assets=400.0,
    long_term_debt=300.0,
    revenue=1000.0,
    gross_profit=400.0,
    net_income=60.0,
)


def test_coverage_4_is_a_minus_with_five_percent() -> None:
    assert rate(80.0, 20.0, 200.0, 100.0, POLICY) == Rating("A-", 4.0, 0.05, None)


def test_net_cash_is_no_default_risk() -> None:
    assert rate(80.0, 20.0, 200.0, 250.0, POLICY) == Rating("—", None, 0.0, "no net debt")
    assert rate(80.0, None, 200.0, 200.0, POLICY) == Rating("—", None, 0.0, "no net debt")


@pytest.mark.parametrize("interest", [None, 0.0])
def test_net_debt_without_interest_is_unavailable(interest: float | None) -> None:
    assert rate(80.0, interest, 200.0, 100.0, POLICY) is None


@pytest.mark.parametrize(
    "ebit, interest, coverage", [(-10.0, 20.0, -0.5), (0.0, 20.0, 0.0), (-10.0, 0.5, -20.0)]
)
def test_a_loss_is_rated_d_whatever_the_interest(
    ebit: float, interest: float, coverage: float
) -> None:
    assert rate(ebit, interest, 200.0, 100.0, POLICY) == Rating("D", coverage, 1.0, None)


@pytest.mark.parametrize(
    "coverage, rating, pi",
    [
        (0.199999, "D", 1.0),
        (0.2, "C", 0.8103),
        (2.249999, "BB", 0.1963),
        (2.25, "BB+", 0.1963),
        (8.499999, "AA", 0.0051),
        (8.5, "AAA", 0.0007),
        (100.0, "AAA", 0.0007),
    ],
)
def test_the_table_edges(coverage: float, rating: str, pi: float) -> None:
    assert rate(coverage, 1.0, 200.0, 100.0, POLICY) == Rating(rating, coverage, pi, None)


def test_altman_z_on_the_worked_lines() -> None:
    z = altman_z(YEAR, POLICY)
    assert z is not None
    assert (z.x1, z.x2, z.x3, z.x4) == pytest.approx((0.1, 0.2, 0.06, 0.8))
    assert z.score == pytest.approx(2.5512, abs=1e-12)
    assert z.zone == "grey"


def test_altman_z_zones_and_missing_lines() -> None:
    safe = altman_z(replace(YEAR, operating_income=200.0), POLICY)
    distress = altman_z(
        replace(YEAR, total_current_assets=100.0, total_current_liabilities=400.0), POLICY
    )
    assert safe is not None and safe.score == pytest.approx(3.492) and safe.zone == "safe"
    assert distress is not None and distress.score == pytest.approx(-0.0728)
    assert distress.zone == "distress"

    worked = altman_z(YEAR, POLICY)
    assert worked is not None
    on_the_low_edge = replace(POLICY, z_distress=worked.score)
    on_the_high_edge = replace(POLICY, z_safe=worked.score)
    assert altman_z(YEAR, on_the_low_edge) == worked
    assert altman_z(YEAR, on_the_high_edge) == worked

    for line in (
        "total_current_assets",
        "total_current_liabilities",
        "total_assets",
        "total_liabilities",
        "retained_earnings",
        "equity",
        "operating_income",
    ):
        assert altman_z(replace(YEAR, **{line: None}), POLICY) is None, line
    for line in ("total_assets", "total_liabilities"):
        assert altman_z(replace(YEAR, **{line: 0.0}), POLICY) is None, line
        assert altman_z(replace(YEAR, **{line: -1.0}), POLICY) is None, line
    assert altman_z(replace(YEAR, net_income=None, cfo=None), POLICY) == worked


def test_piotroski_f_counts_true_signals_and_reads_missing_as_none() -> None:
    assert piotroski_f(YEAR, LAST) == FScore(
        signals=(
            ("roa_positive", True),
            ("cfo_positive", True),
            ("roa_up", False),
            ("accrual", True),
            ("leverage_down", True),
            ("liquidity_up", False),
            ("no_issuance", True),
            ("gross_margin_up", False),
            ("turnover_up", True),
        ),
        score=6,
        read=9,
    )

    no_gross = piotroski_f(replace(YEAR, gross_profit=None), LAST)
    assert dict(no_gross.signals)["gross_margin_up"] is None
    assert (no_gross.score, no_gross.read) == (6, 8)

    no_revenue_last = piotroski_f(YEAR, replace(LAST, revenue=0.0))
    assert dict(no_revenue_last.signals)["gross_margin_up"] is None
    assert dict(no_revenue_last.signals)["turnover_up"] is True
    assert no_revenue_last.read == 8

    no_assets_last = dict(piotroski_f(YEAR, replace(LAST, total_assets=0.0)).signals)
    assert (no_assets_last["roa_up"], no_assets_last["leverage_down"]) == (None, None)
    assert no_assets_last["turnover_up"] is None

    no_income = piotroski_f(replace(YEAR, net_income=None), LAST)
    signals = dict(no_income.signals)
    assert (signals["roa_positive"], signals["roa_up"], signals["accrual"]) == (None, None, None)
    assert (no_income.score, no_income.read) == (4, 6)


def test_piotroski_no_issuance_is_unread_when_the_line_is_missing() -> None:
    no_line = piotroski_f(replace(YEAR, stock_issued=None), LAST)
    assert dict(no_line.signals)["no_issuance"] is None
    assert (no_line.score, no_line.read) == (5, 8)
    assert dict(piotroski_f(replace(YEAR, stock_issued=-5.0), LAST).signals)["no_issuance"] is True
    assert dict(piotroski_f(replace(YEAR, stock_issued=5.0), LAST).signals)["no_issuance"] is False


def test_ncav() -> None:
    assert ncav(YEAR) == -200.0
    assert ncav(replace(YEAR, total_current_assets=1100.0)) == 600.0
    assert ncav(replace(YEAR, total_current_assets=None)) is None
    assert ncav(replace(YEAR, total_liabilities=None)) is None


def test_ncav_on_the_newest_sheet() -> None:
    """The floor reads the newest balance sheet, a quarter's here (spec 2026-11-13 12.2): current
    assets 900 less total liabilities 500."""
    sheet = NewestSheet(date(2026, 9, 30), "fiscal 2026 Q3", True, 900.0, 500.0, None)
    assert ncav(sheet) == 400.0
    assert ncav(replace(sheet, total_current_assets=None)) is None
    assert ncav(replace(sheet, total_liabilities=None)) is None
