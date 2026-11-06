"""The Decline route through ``value_company``: spec 13.1's row on the run-off DCF with the
distress weighting, the net-current-asset floor and the distress signals; the refusals in order,
the flags and their sentences, the inputs, the JSON round trip and the price refresh.

The fixture (``support.engine_companies.decline_inputs``) is spec 13.1 in USD millions on 100 m
shares, so a share's figures are the spec's and the totals are the spec's times a million."""

import math
from dataclasses import replace
from datetime import date

import pytest
from support.engine_companies import annual, fiscal_years

from fairband.engine.anchor import TrailingFigures
from fairband.engine.classifier import Deciles, Series
from fairband.engine.revenue_growth import PeerFigures, PeerSource
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.types import (
    Flag,
    TaggedInput,
    ValuationResult,
    result_from_json,
    result_to_json,
)
from fairband.policy import Policy

TODAY = date(2026, 10, 31)
REPRICED = date(2026, 11, 2)
M = 1e6
# Spec 2026-11-06 13.1 to the core's last digits (tests/engine/test_runoff.py pins the same
# figures).
VALUE = 4.953312779039696  # spec 4.9533
GOING_CONCERN = 5.074808958203771  # spec 5.0748
DISTRESS = 2.6448853749222625  # spec 2.6449
FIRM = 607.4808958203771 * M  # spec 607.48
RUNOFF_REVENUE = (970.00, 940.90, 912.67, 881.38, 856.20, 836.63, 822.29, 812.89, 808.24, 808.24)
FCFF = (67.20, 65.18, 63.23, 62.27, 58.93, 56.07, 53.64, 51.59, 49.89, 48.49)
# d = −4% fading to zero by year 10 after the consensus's three years: d × (10 − t) ÷ 7 (spec 6.1)
FADE = [-0.04 * (10 - t) / 7 for t in range(4, 11)]
# The fixture's base + 2 consensus revenue (fiscal 2029), from which the years past 3 step.
BASE_2 = 940.9 * M
FISCAL_REVENUE = [1_125 * M, 1_200 * M, 1_120 * M, 1_050 * M, 1_000 * M]

DECLINE_KEYS = {
    "runoff_path",
    "margin",
    "tax_rate",
    "sales_to_capital",
    "runoff_recovery",
    "debt",
    "cash",
    "shares",
    "ncav",
    "pi",
    "distress_sale_fraction",
    "moat",
    "growth_rates",
    "revenue_by_year",
    "ebit_by_year",
    "tax_by_year",
    "nopat_by_year",
    "reinvestment_by_year",
    "release_by_year",
    "fcff_by_year",
    "terminal_value",
    "firm_value",
    "equity",
    "going_concern_per_share",
    "ncav_per_share",
    "floored_per_share",
    "rating",
    "distress_proceeds",
    "distress_per_share",
    "value_per_share",
    "altman_z",
    "piotroski_f",
    "capex_vs_depreciation",
    "eps",
    "epv",
    "dividend_yield",
    "net_buyback_yield",
    "income_basis",
    "price_facts",
    "implied_decline_rate",
    "multiples",
    "expected_return",
}
PRICE_KEYS = ("implied_decline_rate", "multiples", "expected_return")
NOT_POSITIVE = "value not positive in the run-off"
FMP_SOURCE = "FMP stock-peers and the peers' statements"
PEERS = (
    PeerFigures("PEER1", 10e9, 0.10, 10, 2.5, 0.12),
    PeerFigures("PEER2", 50e9, 0.20, 10, 1.5, 0.20),
    PeerFigures("PEER3", 20e9, 0.30, 10, 3.0, 0.15),
)


def codes(r: ValuationResult) -> list[str]:
    return [f.code for f in r.flags]


def route_codes(r: ValuationResult) -> list[str]:
    """The route's flags: every flag but the classifier's checks and assembly's."""
    others = {f.code for f in r.phase.checks}
    return [c for c in codes(r) if c not in others]


def sentence(r: ValuationResult, code: str) -> str:
    [found] = [f.sentence for f in r.flags if f.code == code]
    return found


def input_named(r: ValuationResult, name: str) -> TaggedInput:
    [found] = [i for i in r.inputs if i.name == name]
    return found


def assert_refused(r: ValuationResult, reason: str) -> None:
    """A refusal is a full row with no value, never an exception."""
    assert r.refusal == reason
    assert (r.route, r.value, r.levels, r.price_to_value, r.designation) == (None,) * 5
    assert result_from_json(result_to_json(r)) == r


def with_margins(inputs: CompanyInputs, margins: list[float | None]) -> CompanyInputs:
    """The fixture's five fiscal years at these operating margins, ``None`` a year without an
    operating income."""
    series = fiscal_years(FISCAL_REVENUE, [0.0] * 5)
    return replace(
        inputs,
        series=tuple(
            replace(fy, operating_income=None if m is None else m * fy.revenue)
            for fy, m in zip(series, margins, strict=True)
            if fy.revenue is not None
        ),
    )


def trailing(inputs: CompanyInputs) -> TrailingFigures:
    assert inputs.trailing is not None
    return inputs.trailing


def with_consensus(inputs: CompanyInputs, *years: tuple[int, float, int | None]) -> CompanyInputs:
    """The fixture with the consensus revenue of these fiscal years past base + 2 (fiscal 2029),
    each (fiscal year, revenue mean, revenue analysts)."""
    extra = tuple(annual(year, 39 * M, 0.39, 6, revenue, n) for year, revenue, n in years)
    return replace(inputs, annual_estimates=(*inputs.annual_estimates, *extra))


def step_names(r: ValuationResult) -> list[str]:
    return [i.name for i in r.inputs if i.name.startswith("path_step_")]


def test_the_worked_decline_row_values_at_4_953(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(decline_inputs, deciles, policy, TODAY)
    assert (r.route, r.refusal, r.phase.phase) == ("decline", None, "Decline")
    assert r.value is not None and r.value == pytest.approx(VALUE, abs=1e-9)
    im = r.intermediates
    assert set(im) == DECLINE_KEYS
    assert im["runoff_path"] == {
        "revenue0": 1_000 * M,
        "ntm_revenue": pytest.approx(970 * M),
        "steps": pytest.approx([-0.03, -0.03]),
        "consensus_years": 3,
        "d": pytest.approx(-0.04),
        "runoff_years": 10,
    }
    assert im["growth_rates"] == pytest.approx([-0.03] * 3 + FADE)
    assert im["revenue_by_year"] == pytest.approx([x * M for x in RUNOFF_REVENUE], abs=0.01 * M)
    assert im["fcff_by_year"] == pytest.approx([x * M for x in FCFF], abs=0.01 * M)
    assert im["ebit_by_year"] == pytest.approx([x * 0.08 for x in im["revenue_by_year"]])
    assert im["reinvestment_by_year"] == [0.0] * 10 and im["release_by_year"][0] == pytest.approx(
        9 * M
    )
    assert im["terminal_value"] == pytest.approx(538.8292788342035 * M, abs=1e-3)
    assert im["firm_value"] == pytest.approx(FIRM, abs=1e-3)
    assert im["equity"] == pytest.approx(FIRM - 200 * M + 100 * M, abs=1e-3)
    assert im["going_concern_per_share"] == pytest.approx(GOING_CONCERN, abs=1e-9)
    assert (im["ncav"], im["ncav_per_share"]) == (-200 * M, -2.0)  # no floor
    assert im["floored_per_share"] == im["going_concern_per_share"]
    assert im["rating"] == {
        "rating": "A-",
        "ebit": pytest.approx(80 * M),
        "interest": 20 * M,
        "coverage": pytest.approx(4.0),
        "pi": 0.05,
        "row": {"coverage_from": 3.0, "coverage_below": 4.25},
        "note": None,
    }
    assert im["pi"] == {"value": 0.05, "rating": "A-", "coverage": pytest.approx(4.0)}
    assert im["distress_proceeds"] == pytest.approx(0.6 * FIRM + 100 * M, abs=1e-3)
    assert im["distress_per_share"] == pytest.approx(DISTRESS, abs=1e-9)
    assert im["value_per_share"] == r.value
    assert im["margin"] == {
        "value": pytest.approx(0.08),
        "used": "median",
        "median": pytest.approx(0.08),
        "trailing": pytest.approx(0.08),
        "years": [2021, 2022, 2023, 2024, 2025],
        "margins": pytest.approx([0.07, 0.08, 0.08, 0.09, 0.08]),
    }
    assert im["sales_to_capital"] == {"used": "own-latest", "value": pytest.approx(2.0)}
    assert (im["tax_rate"], im["runoff_recovery"], im["distress_sale_fraction"]) == (
        0.25,
        0.6,
        0.6,
    )
    assert (im["debt"], im["cash"], im["shares"], im["moat"]) == (200 * M, 100 * M, 100 * M, "None")
    z = 6.56 * 100 / 900 + 3.26 * 250 / 900 + 6.72 * 80 / 900 + 1.05 * 400 / 500
    assert im["altman_z"] == {
        "year": 2025,
        "x1": pytest.approx(100 / 900),
        "x2": pytest.approx(250 / 900),
        "x3": pytest.approx(80 / 900),
        "x4": pytest.approx(0.8),
        "score": pytest.approx(z),
        "zone": "safe",
    }
    f = im["piotroski_f"]
    assert (f["year"], f["prior_year"], f["score"], f["read"]) == (2025, 2024, 6, 9)
    assert [s["name"] for s in f["signals"]] == [
        "roa_positive",
        "cfo_positive",
        "roa_up",
        "accrual",
        "leverage_down",
        "liquidity_up",
        "no_issuance",
        "gross_margin_up",
        "turnover_up",
    ]
    assert [s["value"] for s in f["signals"]] == [True, True, False, True, True, True, True] + [
        False,
        False,
    ]
    assert im["capex_vs_depreciation"] == {"capex": -30 * M, "depreciation": 40 * M}
    assert im["eps"] == {"reported": 0.45, "clean": 0.45, "forward": None}
    assert im["epv"] == pytest.approx(0.45 / 0.09)
    # $3.00 against $4.9533: 0.606 × the value, below 0.65
    assert (r.price_to_value, r.designation) == (3.0 / r.value, "well-below")
    assert r.levels is not None and r.levels.buy == pytest.approx(r.value * 0.55)  # None moat
    # the price-side figures: no decline rate in the scan gives $3.00, the run-off being worth
    # 3.1251 at −50% (spec 13.1); the trailing P/E and no forward one; and the expected return
    # growing at the path's rates for years 2 to 4
    assert im["implied_decline_rate"] is None
    assert im["multiples"]["pe_reported"] == pytest.approx(3.0 / 0.45)
    assert im["multiples"]["pe_forward"] is None
    growth = (0.97 * 0.97 * (1 + FADE[0])) ** (1 / 3) - 1
    assert im["expected_return"]["growth"] == pytest.approx(growth, abs=1e-12)
    assert route_codes(r) == []
    assert r.valid_until == decline_inputs.next_earnings


def test_the_refusal_order(decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    dc, t = decline_inputs, trailing(decline_inputs)

    def valued(inputs: CompanyInputs) -> ValuationResult:
        return value_company(inputs, deciles, policy, TODAY)

    nothing_after = {"tax_rate_latest": None, "capital_years": (), "peers": ()}
    for revenue in (None, 0.0, -5.0):
        no_revenue = replace(dc, trailing=replace(t, revenue=revenue), **nothing_after)
        assert_refused(valued(no_revenue), "no trailing revenue")
    no_income = replace(dc, trailing=replace(t, operating_income=None), **nothing_after)
    assert_refused(valued(no_income), "no trailing operating income")
    no_tax = replace(dc, tax_rate_latest=None, capital_years=(), peers=())
    assert_refused(valued(no_tax), "no statutory tax rate")
    # a consensus year of zero with analysts: year 2 falls 100%, before the sales-to-capital
    a = dc.annual_estimates
    falls = (a[0], replace(a[1], revenue=0.0), a[2])
    r = valued(replace(dc, annual_estimates=falls, capital_years=(), peers=()))
    assert_refused(r, "consensus revenue falls to zero or below within the path")
    assert r.intermediates.keys() == {"price_facts"}
    r = valued(replace(dc, capital_years=(), peers=()))
    assert_refused(r, "no sales-to-capital")
    assert r.intermediates.keys() == {"price_facts"}
    # a chronic loss: the run-off at a normalized margin of −3% is worth less than nothing
    chronic = with_margins(dc, [-0.02, -0.03, -0.03, -0.03, -0.03])
    r = valued(chronic)
    assert_refused(r, NOT_POSITIVE)
    assert set(r.intermediates) == DECLINE_KEYS - set(PRICE_KEYS)


def test_a_chronic_loss_is_refused_with_its_figures(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Ruling 3 on spec 13.1: fiscal margins of −2% and four of −3% (m_n = −3%, EBIT_n = −30) rate
    the company D, π = 100%; the firm value is −241.32, so with net debt the distress-sale value
    is max(0, 0.6 × −241.32 + 100 − 200) = 0, and with cash 250 π is 0 and the going-concern
    value −1.9132 a share. Both refuse and keep every figure, and the inputs that gave them."""
    chronic = with_margins(decline_inputs, [-0.02, -0.03, -0.03, -0.03, -0.03])
    r = value_company(chronic, deciles, policy, TODAY)
    assert_refused(r, NOT_POSITIVE)
    im = r.intermediates
    assert im["margin"]["value"] == pytest.approx(-0.03) and im["margin"]["used"] == "median"
    assert im["firm_value"] == pytest.approx(-241.3179552207426 * M, abs=1e-3)
    assert (im["rating"]["rating"], im["rating"]["pi"]) == ("D", 1.0)
    assert im["rating"]["ebit"] == pytest.approx(-30 * M)
    assert im["rating"]["row"] == {"coverage_from": None, "coverage_below": 0.2}
    assert im["distress_per_share"] == 0.0 and im["value_per_share"] == 0.0
    assert im["altman_z"] is not None and im["piotroski_f"]["read"] == 9
    assert "tax-loss-history-unknown" in codes(r)
    # the refusal cites the route's inputs as a valued row does: the base inputs first, then the
    # interest, the balance lines, the run-off's rules, the rating's row and π
    names = [i.name for i in r.inputs]
    assert len(names) == len(set(names))
    assert names[:5] == ["statements", "price", "shares_diluted", "next_earnings", "closes"]
    valued = value_company(decline_inputs, deciles, policy, TODAY)
    assert names == [i.name for i in valued.inputs]
    assert input_named(r, "interest_expense").value == 20 * M
    tca, tl = input_named(r, "total_current_assets"), input_named(r, "total_liabilities")
    assert (tca.value, tl.value, tca.note) == (300 * M, 500 * M, "fiscal 2025")
    assert input_named(r, "total_assets_prior").value == 900 * M
    assert (
        input_named(r, "runoff_recovery").value,
        input_named(r, "distress_sale_fraction").value,
    ) == (
        0.6,
        0.6,
    )
    rating, pi = input_named(r, "synthetic_rating"), input_named(r, "default_probability_10y")
    assert (rating.value, rating.note) == (
        None,
        "the D row: an interest coverage below 0.2; the company's is -1.50",
    )
    assert (pi.value, pi.note) == (1.0, "the ten-year probability of default of the D rating")
    net_cash = value_company(replace(chronic, cash=250 * M), deciles, policy, TODAY)
    assert_refused(net_cash, NOT_POSITIVE)
    im = net_cash.intermediates
    assert (im["rating"]["rating"], im["rating"]["pi"], im["rating"]["note"]) == (
        "—",
        0.0,
        "no net debt",
    )
    assert im["going_concern_per_share"] == pytest.approx(-1.913179552207426, abs=1e-9)
    assert im["value_per_share"] == im["floored_per_share"] == im["going_concern_per_share"]
    # a refusal takes only the new price on a price refresh
    p = reprice(r, 5.0, REPRICED, policy)
    assert (p.price, p.price_date, p.intermediates, p.refusal) == (
        5.0,
        REPRICED,
        r.intermediates,
        NOT_POSITIVE,
    )


def test_the_distress_variants(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 13.1's variants and the π rules in their order: net cash first, then no interest
    expense, then the rating (a chronic loss-maker with net cash is not rated D)."""
    dc, t = decline_inputs, trailing(decline_inputs)

    def valued(inputs: CompanyInputs) -> ValuationResult:
        return value_company(inputs, deciles, policy, TODAY)

    net_cash = valued(replace(dc, cash=250 * M))
    assert net_cash.value == pytest.approx(6.574808958203771, abs=1e-9)
    assert net_cash.intermediates["pi"] == {"value": 0.0, "rating": "—", "coverage": None}
    assert "distress-not-charged" not in codes(net_cash)
    for interest in (None, 0.0):
        r = valued(replace(dc, trailing=replace(t, interest_expense=interest)))
        assert r.value == pytest.approx(GOING_CONCERN, abs=1e-9)  # spec 5.0748
        assert sentence(r, "distress-not-charged") == (
            "No interest expense on file: the distress probability is unavailable and the value "
            "is the floored going-concern value."
        )
        assert r.intermediates["pi"] == {"value": None, "rating": None, "coverage": None}
        assert r.intermediates["rating"]["note"] == "no interest expense on file"
        assert input_named(r, "synthetic_rating").note == "no rating: no interest expense on file"
    # with net cash, no interest is no matter: π is 0
    r = valued(replace(dc, cash=250 * M, trailing=replace(t, interest_expense=None)))
    assert r.intermediates["pi"]["value"] == 0.0 and "distress-not-charged" not in codes(r)
    # unknown debt is not "no net debt": with both debt lines missing there is no rating, even
    # against cash 250, and the value is the going concern with the debt counted as nil
    for cash in (100 * M, 250 * M):
        r = valued(replace(dc, debt=None, cash=cash))
        assert r.intermediates["pi"] == {"value": None, "rating": None, "coverage": None}
        assert r.intermediates["rating"]["note"] == "no debt line on file"
        assert r.intermediates["debt"] == 0.0
        assert r.value == pytest.approx(r.intermediates["going_concern_per_share"], abs=1e-12)
        assert r.value == pytest.approx((FIRM + cash) / (100 * M), abs=1e-9)
        assert sentence(r, "distress-not-charged") == (
            "No debt line on file: the distress probability is unavailable and the value is the "
            "floored going-concern value."
        )
        assert route_codes(r) == ["line-not-presented:debt", "distress-not-charged"]
        rating, pi = input_named(r, "synthetic_rating"), input_named(r, "default_probability_10y")
        assert (rating.value, rating.note) == (None, "no rating: no debt line on file")
        assert (pi.value, pi.note) == (None, "no rating: π unavailable")
    # the floor: current assets 1,100 give NCAV 600, 6.00 a share, above the run-off's 5.0748
    newest = replace(dc.balance_years[-1], total_current_assets=1_100 * M)
    floored = replace(dc, balance_years=(dc.balance_years[0], newest))
    r = valued(floored)
    assert r.value == pytest.approx(5.832244268746113, abs=1e-9)  # 6.00 × 0.95 + 2.6449 × 0.05
    assert r.intermediates["floored_per_share"] == pytest.approx(6.0)
    assert sentence(r, "ncav-floor") == (
        "The floored value is the net current asset value 6.00 a share; the run-off gives 5.07."
    )
    # π unavailable: the floored value is the value, and the floor is flagged
    r = valued(replace(floored, trailing=replace(t, interest_expense=None)))
    assert r.value == pytest.approx(6.0, abs=1e-12)
    assert route_codes(r) == ["ncav-floor", "distress-not-charged"]
    # the coverage reads EBIT_n: a normalized margin of 10% on trailing revenue 1,000 covers the
    # interest of 20 five times (A), where the trailing 80 would cover it four times (A−)
    r = valued(with_margins(dc, [0.08, 0.10, 0.10, 0.12, 0.10]))
    assert (r.intermediates["rating"]["rating"], r.intermediates["rating"]["coverage"]) == (
        "A",
        pytest.approx(5.0),
    )


def test_the_floor_has_no_weight_at_a_pi_of_one(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A company rated D defaults: π = 100% and the value is the distress-sale value alone, so an
    NCAV above zero and above the going concern floors a value that has no weight, and
    ``ncav-floor`` is not raised (spec 10.6, 10.11)."""
    dc = decline_inputs
    newest = replace(dc.balance_years[-1], total_current_assets=1_100 * M)  # NCAV 6.00 a share
    rich = replace(dc, balance_years=(dc.balance_years[0], newest))
    # a normalized margin of zero: EBIT_n 0, rated D; the release alone gives a firm value above
    # zero, 41.61, and with cash 199 against debt 200 the distress-sale value is above zero too
    thin = with_margins(replace(rich, cash=199 * M), [-0.02, 0.0, 0.0, 0.0, 0.0])
    r = value_company(thin, deciles, policy, TODAY)
    assert r.route == "decline" and r.value is not None
    im = r.intermediates
    assert im["firm_value"] == pytest.approx(41.614995126297245 * M, abs=1e-3)
    assert (im["rating"]["rating"], im["pi"]["value"]) == ("D", 1.0)
    assert im["floored_per_share"] == pytest.approx(6.0)
    assert im["floored_per_share"] > im["going_concern_per_share"]
    assert r.value == im["distress_per_share"]
    assert r.value == pytest.approx((0.6 * im["firm_value"] + 199 * M - 200 * M) / (100 * M))
    assert "ncav-floor" not in codes(r)
    # the chronic loss at −3%: refused, the floor computed and not flagged
    chronic = with_margins(rich, [-0.02, -0.03, -0.03, -0.03, -0.03])
    r = value_company(chronic, deciles, policy, TODAY)
    assert_refused(r, NOT_POSITIVE)
    assert r.intermediates["floored_per_share"] == pytest.approx(6.0)
    assert r.intermediates["pi"]["value"] == 1.0 and "ncav-floor" not in codes(r)


def test_no_consensus_takes_the_trend_then_the_fade(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-06 13.1: years 1 to 3 at d = −4%, then the fade from year 4 as with K = 3;
    4.8626 a share. The annual consensus past year 3 is not read without a usable NTM revenue."""
    dc = with_consensus(decline_inputs, (2030, BASE_2 * 1.01, 6))
    r = value_company(replace(dc, quarter_estimates=()), deciles, policy, TODAY)
    assert r.route == "decline" and r.value is not None
    assert r.value == pytest.approx(4.8626, abs=1e-4)  # spec 4.8626
    assert r.value == pytest.approx(4.862642425851334, abs=1e-9)
    im = r.intermediates
    assert im["runoff_path"] == {
        "revenue0": 1_000 * M,
        "ntm_revenue": None,
        "steps": [None, None],
        "consensus_years": 3,
        "d": pytest.approx(-0.04),
        "runoff_years": 10,
    }
    assert im["growth_rates"] == pytest.approx([-0.04] * 3 + FADE)
    assert sentence(r, "path-on-trend") == (
        "No usable consensus: years 1 to 3 shrink at the decline rate, −4.0%, which fades to zero "
        "by year 10."
    )
    assert [f.word for f in r.flags if f.code == "path-on-trend"] == ["Path on trend"]
    assert "path-held" not in codes(r) and "few-analysts" not in codes(r)
    note = "no usable consensus: years 1 to 3 shrink at the decline rate"
    for name in ("ntm_revenue", "path_step_2", "path_step_3"):
        found = input_named(r, name)
        assert (found.value, found.note) == (None, note), name
    assert step_names(r) == ["path_step_2", "path_step_3"]
    # a quarter without a revenue mean, or an NTM revenue at or below zero, does not refuse
    q = dc.quarter_estimates
    gap = (*q[:3], replace(q[3], revenue=None))
    zero = tuple(replace(x, revenue=v) for x, v in zip(q, (1e9, -1e9, 0.0, 0.0), strict=True))
    for quarters in (gap, zero):
        other = value_company(replace(dc, quarter_estimates=quarters), deciles, policy, TODAY)
        assert other.value == r.value and "path-on-trend" in codes(other)
    assert input_named(
        value_company(replace(dc, quarter_estimates=zero), deciles, policy, TODAY), "ntm_revenue"
    ).value == pytest.approx(0.0)


def test_a_held_step_flags_path_held(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    dc = decline_inputs
    a = dc.annual_estimates
    held = value_company(replace(dc, annual_estimates=a[:2]), deciles, policy, TODAY)
    assert sentence(held, "path-held") == (
        "The consensus revenue for fiscal 2029 is missing or not positive, so year 3 holds the "
        "-3.0% of the year before."
    )
    assert held.intermediates["runoff_path"]["steps"] == [pytest.approx(-0.03), None]
    assert held.intermediates["growth_rates"][:4] == pytest.approx([-0.03] * 3 + FADE[:1])
    assert held.value == pytest.approx(VALUE, abs=1e-9)
    assert input_named(held, "path_step_3").note == (
        "no consensus step: the year holds the rate of the year before"
    )
    # a thin landing year, and a held one: both flags, the held first
    thin = (a[0], replace(a[1], analysts_revenue=3))
    r = value_company(replace(dc, annual_estimates=thin), deciles, policy, TODAY)
    assert route_codes(r) == ["path-held", "few-analysts"]
    assert "fiscal 2028" in sentence(r, "few-analysts")


def test_a_rising_step_flags_consensus_recovery(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    dc = decline_inputs
    a = dc.annual_estimates
    rising = (a[0], replace(a[1], revenue=1_020 * M), replace(a[2], revenue=1_020 * M * 0.97))
    r = value_company(replace(dc, annual_estimates=rising), deciles, policy, TODAY)
    assert sentence(r, "consensus-recovery") == (
        "The consensus has revenue growing 2.0% in year 2 while the decline rate is −4.0%."
    )
    assert [f.word for f in r.flags if f.code == "consensus-recovery"] == ["Consensus recovery"]
    im = r.intermediates
    r1, r2 = 970 * M, 970 * M * 1.02
    assert im["revenue_by_year"][:2] == pytest.approx([r1, r2])
    assert im["reinvestment_by_year"][1] == pytest.approx((r2 - r1) / 2.0)
    assert im["release_by_year"][1] == 0.0
    # every rising consensus year is named
    up = tuple(replace(x, revenue=1_067 * M / 4) for x in dc.quarter_estimates)
    both = replace(dc, quarter_estimates=up, annual_estimates=rising)
    r = value_company(both, deciles, policy, TODAY)
    assert sentence(r, "consensus-recovery") == (
        "The consensus has revenue growing 6.7% in year 1 and 2.0% in year 2 while the decline "
        "rate is −4.0%."
    )


def test_a_steep_trend_is_floored_at_minus_half(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Revenue 4,000, 3,500, 3,000, 2,000 and 600: the slope is −830 a year, −138% of the last
    revenue; the run-off shrinks at −50%, and the path's sentences name the decline rate as used,
    never the trend's own −138%."""
    series = fiscal_years([4_000 * M, 3_500 * M, 3_000 * M, 2_000 * M, 600 * M], [0.08] * 5)
    steep = replace(
        decline_inputs,
        series=series,
        quarter_estimates=(),
        trailing=replace(trailing(decline_inputs), revenue=600 * M, operating_income=48 * M),
    )
    r = value_company(steep, deciles, policy, TODAY)
    assert r.phase.phase == "Decline"
    assert r.intermediates["runoff_path"]["d"] == -0.5
    assert sentence(r, "decline-rate-floored") == (
        "The five-year trend shrinks revenue faster than 50% a year; the run-off uses −50%."
    )
    assert [f.word for f in r.flags if f.code == "decline-rate-floored"] == ["Decline rate floored"]
    assert route_codes(r)[:2] == ["decline-rate-floored", "path-on-trend"]
    assert sentence(r, "path-on-trend") == (
        "No usable consensus: years 1 to 3 shrink at the decline rate, −50.0%, which fades to zero "
        "by year 10."
    )
    assert r.intermediates["growth_rates"][2:4] == pytest.approx([-0.5, -0.5 * 6 / 7])
    # with the consensus and fiscal 2029 missing from it: the held step first, then the floor;
    # the NTM revenue of 970 is above the trailing 600, so year 1 grows against the floored rate
    held = replace(
        steep,
        quarter_estimates=decline_inputs.quarter_estimates,
        annual_estimates=decline_inputs.annual_estimates[:2],
    )
    r = value_company(held, deciles, policy, TODAY)
    assert r.intermediates["runoff_path"]["d"] == -0.5
    assert route_codes(r)[:3] == ["path-held", "decline-rate-floored", "consensus-recovery"]
    assert "path-on-trend" not in codes(r)
    assert sentence(r, "path-held") == (
        "The consensus revenue for fiscal 2029 is missing or not positive, so year 3 holds the "
        "-3.0% of the year before."
    )
    assert sentence(r, "consensus-recovery") == (
        "The consensus has revenue growing 61.7% in year 1 while the decline rate is −50.0%."
    )
    assert r.intermediates["growth_rates"][2:4] == pytest.approx([-0.03, -0.5 * 6 / 7])


def test_sales_to_capital_falls_back_to_the_peers(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    dc = decline_inputs
    r = value_company(replace(dc, capital_years=(), peers=PEERS), deciles, policy, TODAY)
    assert r.intermediates["sales_to_capital"] == {"used": "peers", "value": pytest.approx(2.5)}
    s2c = input_named(r, "sales_to_capital")
    assert s2c.provenance.source == FMP_SOURCE
    assert s2c.note == "the mature peers' median; the company has no newest-year measure"
    assert input_named(r, "peer_min").value == policy.peer_min
    assert "industry_peer_max" not in [i.name for i in r.inputs]
    assert "peers-from-industry" not in codes(r)
    # an own year whose average capital is at or below zero is no measure
    nil_capital = tuple(replace(y, net_ppe=-20 * M) for y in dc.capital_years)
    r = value_company(replace(dc, capital_years=nil_capital, peers=PEERS), deciles, policy, TODAY)
    assert r.intermediates["sales_to_capital"]["used"] == "peers"
    # the own measure first, whatever the peers
    own = value_company(replace(dc, peers=PEERS), deciles, policy, TODAY)
    assert own.intermediates["sales_to_capital"] == {
        "used": "own-latest",
        "value": pytest.approx(2.0),
    }
    assert "peer_min" not in [i.name for i in own.inputs]
    # the industry's peers serve: flagged and bounded
    industry = PeerSource("industry", "Department Stores", 1)
    r = value_company(
        replace(dc, capital_years=(), peers=PEERS, peer_source=industry), deciles, policy, TODAY
    )
    assert "peers-from-industry" in codes(r)
    assert input_named(r, "sales_to_capital").note == (
        "the mature peers' median (Department Stores industry); the company has no newest-year "
        "measure"
    )
    assert input_named(r, "industry_peer_max").value == policy.industry_peer_max
    # the industry's peers that do not serve raise nothing
    r = value_company(replace(dc, peers=PEERS, peer_source=industry), deciles, policy, TODAY)
    assert "peers-from-industry" not in codes(r)
    # two peers are no median
    r = value_company(replace(dc, capital_years=(), peers=PEERS[:2]), deciles, policy, TODAY)
    assert_refused(r, "no sales-to-capital")


def test_the_margin_is_the_five_year_median(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    dc, t = decline_inputs, trailing(decline_inputs)
    worked = value_company(dc, deciles, policy, TODAY)
    # a trailing loss of 1% with the same fiscal margins: the same run-off and rating
    loss = value_company(
        replace(dc, trailing=replace(t, operating_income=-10 * M)), deciles, policy, TODAY
    )
    assert loss.value == worked.value
    assert loss.intermediates["rating"] == worked.intermediates["rating"]
    assert loss.intermediates["margin"]["trailing"] == pytest.approx(-0.01)
    assert loss.intermediates["margin"]["median"] == pytest.approx(0.08)
    assert loss.intermediates["margin"]["used"] == "median"
    assert "tax-loss-history-unknown" in codes(loss)
    # five fiscal margins, three, and two: the median of five, of three, else the trailing 7%
    seven = replace(t, operating_income=70 * M)
    five = with_margins(replace(dc, trailing=seven), [0.04, 0.06, 0.08, 0.10, 0.12])
    three = with_margins(replace(dc, trailing=seven), [None, None, 0.08, 0.10, 0.12])
    two = with_margins(replace(dc, trailing=seven), [None, None, None, 0.10, 0.12])
    found = [
        value_company(x, deciles, policy, TODAY).intermediates["margin"] for x in (five, three, two)
    ]
    assert [(m["used"], m["value"]) for m in found] == [
        ("median", pytest.approx(0.08)),
        ("median", pytest.approx(0.10)),
        ("trailing", pytest.approx(0.07)),
    ]
    assert found[1]["years"] == [2023, 2024, 2025]
    assert found[2]["median"] is None and found[2]["margins"] == pytest.approx([0.10, 0.12])


def test_a_fiscal_year_fallback_still_rates_the_company(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Two quarters on file: assembly falls back to fiscal 2025, the interest expense its annual
    line (method 4.2), and flags it. The route reads the trailing figures as they come: it rates
    the company on them and values it, the NTM quarters picked after the fiscal year's end."""
    fiscal = TrailingFigures(
        period_end=date(2025, 12, 31),
        quarters=1,
        on_fiscal_year=True,
        revenue=1_000 * M,
        operating_income=80 * M,
        net_income=45 * M,
        eps_diluted=0.45,
        sbc=5 * M,
        cfo=100 * M,
        capex=-30 * M,
        dividends=-20 * M,
        buybacks=0.0,
        equity_issued=0.0,
        interest_expense=25 * M,
        depreciation=40 * M,
    )
    on_fiscal_year = Flag(
        "trailing-on-fiscal-year",
        "Trailing on fiscal year",
        "The quarters on file are not four consecutive quarters, so the trailing figures are "
        "fiscal 2025's.",
    )
    inputs = replace(decline_inputs, trailing=fiscal, input_flags=(on_fiscal_year,))
    r = value_company(inputs, deciles, policy, TODAY)
    assert r.route == "decline" and r.value is not None
    rating = r.intermediates["rating"]
    assert (rating["interest"], rating["coverage"], rating["rating"]) == (
        25 * M,
        pytest.approx(3.2),
        "A-",
    )
    assert r.intermediates["runoff_path"]["ntm_revenue"] == pytest.approx(970 * M)
    assert codes(r)[0] == "trailing-on-fiscal-year"


def test_a_missing_total_liabilities_line_applies_no_floor(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Current assets of 1,100 would floor the value at 11.00 a share on a nil liability; with the
    line missing no floor is applied."""
    dc = decline_inputs
    newest = replace(dc.balance_years[-1], total_current_assets=1_100 * M, total_liabilities=None)
    r = value_company(
        replace(dc, balance_years=(dc.balance_years[0], newest)), deciles, policy, TODAY
    )
    im = r.intermediates
    assert (im["ncav"], im["ncav_per_share"]) == (None, None)
    assert im["floored_per_share"] == im["going_concern_per_share"]
    assert r.value == pytest.approx(VALUE, abs=1e-9)
    assert "ncav-floor" not in codes(r)
    assert sentence(r, "line-not-presented:totalLiabilities") == (
        "The newest annual balance sheet (fiscal 2025) does not present total liabilities, so no "
        "net-current-asset floor is applied."
    )
    assert im["altman_z"] is None  # Z″ reads the line too; F does not
    assert im["piotroski_f"]["read"] == 9
    # no balance sheet on file: no floor, no Z″, no F
    r = value_company(replace(dc, balance_years=()), deciles, policy, TODAY)
    assert sentence(r, "line-not-presented:totalLiabilities") == (
        "No annual balance sheet is on file, so no net-current-asset floor is applied."
    )
    assert (r.intermediates["altman_z"], r.intermediates["piotroski_f"]) == (None, None)
    assert r.value == pytest.approx(VALUE, abs=1e-9)
    # one balance sheet: Z″ and no F
    r = value_company(replace(dc, balance_years=dc.balance_years[1:]), deciles, policy, TODAY)
    assert r.intermediates["altman_z"] is not None and r.intermediates["piotroski_f"] is None


def _flagged(dc: CompanyInputs) -> CompanyInputs:
    """A row that raises path-held, line-not-presented:cash, ncav-floor, z-distress, f-score-low,
    reinvesting-in-decline and margin-flag: fiscal 2029 missing from the consensus; no cash
    figure; current assets of 1,100 against liabilities of 500 and a deficit of 3,000 (Z″ −0.60);
    a loss on falling cash flow that issued stock and levered up, its current ratio alone up (F 1
    of 9); capital spending of 60 against depreciation of 40, under half the operating cash flow
    of 150; a sixth fiscal year, so the margin flag has its six, and a trailing margin of 13%
    against their median of 8%."""
    last = dc.balance_years[0]
    newest = replace(
        dc.balance_years[1],
        total_current_assets=1_100 * M,
        total_current_liabilities=400 * M,
        total_assets=1_600 * M,
        equity=1_100 * M,
        retained_earnings=-3_000 * M,
        long_term_debt=500 * M,
        net_income=-10 * M,
        cfo=-20 * M,
        stock_issued=50 * M,
    )
    series: Series = fiscal_years(
        [1_100 * M, *FISCAL_REVENUE], [0.08, 0.07, 0.08, 0.08, 0.09, 0.08]
    )
    return replace(
        dc,
        series=series,
        annual_estimates=dc.annual_estimates[:2],
        cash=None,
        balance_years=(last, newest),
        trailing=replace(trailing(dc), operating_income=130 * M, capex=-60 * M, cfo=150 * M),
    )


def test_the_flag_order(decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(_flagged(decline_inputs), deciles, policy, TODAY)
    assert r.route == "decline"
    assert route_codes(r) == [
        "path-held",
        "line-not-presented:cash",
        "ncav-floor",
        "z-distress",
        "f-score-low",
        "reinvesting-in-decline",
        "margin-flag",
    ]
    assert sentence(r, "z-distress") == (
        f"Altman Z″ is {r.intermediates['altman_z']['score']:.2f}, in the distress zone below 1.1."
    )
    assert r.intermediates["altman_z"]["zone"] == "distress"
    assert sentence(r, "f-score-low") == (
        "Piotroski F is 1 of 9: the low group of Piotroski (2000)."
    )
    assert sentence(r, "reinvesting-in-decline") == (
        "Capital spending $60.0 million exceeds depreciation $40.0 million while revenue falls: "
        "Damodaran's denial."
    )
    words = {f.code: f.word for f in r.flags}
    assert (words["ncav-floor"], words["z-distress"], words["f-score-low"]) == (
        "NCAV floor",
        "Z″ distress",
        "Low F-score",
    )
    assert words["reinvesting-in-decline"] == "Reinvesting in decline"
    # never the ROIC flags: the fixture keeps one ROIC year
    assert "roic-unavailable" not in codes(r)
    # depreciation larger than the spending, or a missing line, raises nothing
    dc = _flagged(decline_inputs)
    for capex, depreciation in ((-30 * M, 40 * M), (-60 * M, None), (None, 40 * M)):
        t = replace(trailing(dc), capex=capex, depreciation=depreciation)
        r = value_company(replace(dc, trailing=t), deciles, policy, TODAY)
        assert "reinvesting-in-decline" not in codes(r)


def test_the_inputs(decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(decline_inputs, deciles, policy, TODAY)
    names = [i.name for i in r.inputs]
    assert len(names) == len(set(names))
    data = {i.name for i in r.inputs if i.tag == "DATA"}
    rules = [i.name for i in r.inputs if i.tag == "RULE"]
    assert data >= {
        "statements",
        "price",
        "shares_diluted",
        "next_earnings",
        "closes",
        "market_cap",
        "revenue_ttm",
        "operating_income_ttm",
        "eps_ttm",
        "dividends_ttm",
        "buybacks_ttm",
        "equity_issued_ttm",
        "tax_rate_latest",
        "moat_score",
        "gf_eps_ttm",
        "gf_eps_without_nri",
        "ntm_revenue",
        "path_step_2",
        "path_step_3",
        "interest_expense",
        "sales_to_capital",
        "debt",
        "cash",
        "total_current_assets",
        "total_liabilities",
        "depreciation",
    }
    assert rules == [
        "required_return",
        "runoff_years",
        "runoff_recovery",
        "distress_sale_fraction",
        "synthetic_rating",
        "default_probability_10y",
        "z_distress",
        "z_safe",
        "f_score_low",
        "moat_class",
        "margin_of_safety",
    ]
    for absent in ("aggregate_roic", "runway_return", "terminal_growth", "terminal_roic"):
        assert absent not in names, absent
    interest = input_named(r, "interest_expense")
    assert (interest.value, interest.unit, interest.provenance.source) == (
        20 * M,
        "USD",
        "FMP income-statement",
    )
    assert interest.note == "trailing twelve months, each period's expense by its size"
    assert input_named(r, "depreciation").note == "trailing twelve months"
    s2c = input_named(r, "sales_to_capital")
    assert (s2c.value, s2c.kind) == (pytest.approx(2.0), "observed")
    assert s2c.note == "the company's own newest year: revenue over average invested capital"
    assert input_named(r, "ntm_revenue").provenance.source == "FMP analyst-estimates"
    assert input_named(r, "path_step_2").value == pytest.approx(-0.03)
    # the balance sheet lines Z″, F and NCAV read, each year's cited to the annual statements
    tca, tl = input_named(r, "total_current_assets"), input_named(r, "total_liabilities")
    assert (tca.value, tca.note, tl.value, tl.note) == (
        300 * M,
        "fiscal 2025",
        500 * M,
        "fiscal 2025",
    )
    prior = input_named(r, "total_assets_prior")
    assert (prior.value, prior.note, prior.tag) == (900 * M, "fiscal 2024", "DATA")
    for name in ("retained_earnings", "equity", "net_income_fy", "cfo_fy", "stock_issued_fy"):
        assert input_named(r, name).note == "fiscal 2025", name
    rows = {i.name: i for i in r.inputs if i.tag == "RULE"}
    assert (rows["runoff_years"].value, rows["runoff_recovery"].value) == (10, 0.6)
    assert rows["distress_sale_fraction"].value == 0.6
    assert (rows["synthetic_rating"].value, rows["synthetic_rating"].note) == (
        3.0,
        "the A- row: an interest coverage from 3 to below 4.25; the company's is 4.00",
    )
    assert (rows["default_probability_10y"].value, rows["default_probability_10y"].note) == (
        0.05,
        "the ten-year probability of default of the A- rating",
    )
    assert (rows["z_distress"].value, rows["z_safe"].value, rows["f_score_low"].value) == (
        1.1,
        2.6,
        1,
    )
    assert rows["moat_class"].note == "None"
    assert all(i.provenance.source == f"policy {policy.version}" for i in rows.values())
    # no rating: the two rows say why and cite no figure
    no_debt = value_company(replace(decline_inputs, cash=250 * M), deciles, policy, TODAY)
    rating, pi = (
        input_named(no_debt, "synthetic_rating"),
        input_named(no_debt, "default_probability_10y"),
    )
    assert (rating.value, rating.note) == (None, "no rating: cash covers debt")
    assert (pi.value, pi.note) == (None, "no net debt: π is 0")


def test_the_json_round_trip_and_the_price_refresh(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(decline_inputs, deciles, policy, TODAY)
    assert value_company(decline_inputs, deciles, policy, TODAY) == r
    stored = result_from_json(result_to_json(r))
    assert stored == r
    assert r.price is not None and r.price_date is not None
    assert reprice(stored, r.price, r.price_date, policy) == r
    # 4.00 ÷ 4.9533 = 0.81, below the fair band; 5.00 is 1.01, inside it; 6.00 is 1.21, above it
    # and below the trim
    for price, word in ((4.0, "below"), (5.0, "near"), (6.0, "above")):
        moved = reprice(stored, price, REPRICED, policy)
        assert (moved.value, moved.levels, moved.designation) == (r.value, r.levels, word)
        fresh = value_company(replace(decline_inputs, price=price), deciles, policy, TODAY)
        for key in PRICE_KEYS:
            assert moved.intermediates[key] == fresh.intermediates[key], key
        assert (moved.price_to_value, moved.designation) == (
            fresh.price_to_value,
            fresh.designation,
        )
        assert moved.intermediates["multiples"]["pe_reported"] == pytest.approx(price / 0.45)
        others = {k: v for k, v in moved.intermediates.items() if k not in PRICE_KEYS}
        assert others == {k: v for k, v in r.intermediates.items() if k not in PRICE_KEYS}
    below = reprice(stored, 4.0, REPRICED, policy).intermediates["implied_decline_rate"]
    near = reprice(stored, 5.0, REPRICED, policy).intermediates["implied_decline_rate"]
    assert below is not None and near is not None and -0.5 < below < -0.04 < near < 0.0
    assert reprice(stored, 8.0, REPRICED, policy).designation == "well-above"
    # at the value the price implies the route's own d
    at_value = reprice(stored, VALUE, REPRICED, policy).intermediates["implied_decline_rate"]
    assert at_value == pytest.approx(-0.04, abs=1e-6)
    # $6.00 is above the run-off's value even at d = 0 (5.2247), and $3.00 below it at −50%
    # (3.1251): no decline rate gives either
    assert reprice(stored, 6.0, REPRICED, policy).intermediates["implied_decline_rate"] is None
    assert r.intermediates["implied_decline_rate"] is None


def test_the_consensus_is_read_past_year_three_on_enough_analysts(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-06 13.1: base + 3 at +1% on 6 analysts, base + 4 at +2% on 6, base + 5
    absent: K = 5, the fade from year 6, 5.0974 a share."""
    dc = with_consensus(decline_inputs, (2030, BASE_2 * 1.01, 6), (2031, BASE_2 * 1.01 * 1.02, 6))
    r = value_company(dc, deciles, policy, TODAY)
    assert r.value == pytest.approx(5.0974, abs=1e-4)  # spec 5.0974
    assert r.value == pytest.approx(5.097413068757769, abs=1e-9)
    im = r.intermediates
    assert im["runoff_path"]["consensus_years"] == 5
    assert im["runoff_path"]["steps"] == pytest.approx([-0.03, -0.03, 0.01, 0.02])
    assert im["growth_rates"] == pytest.approx(
        [-0.03] * 3 + [0.01, 0.02, -0.032, -0.024, -0.016, -0.008, 0.0]
    )
    assert im["revenue_by_year"][4] == pytest.approx(940.2357246 * M, abs=1e-3)  # spec 940.24
    assert im["revenue_by_year"][9] == pytest.approx(867.0990170494869 * M, abs=1e-3)
    assert im["terminal_value"] == pytest.approx(578.0660113663247 * M, abs=1e-3)
    assert im["firm_value"] == pytest.approx(622.1850070160989 * M, abs=1e-3)
    assert sentence(r, "consensus-recovery") == (
        "The consensus has revenue growing 1.0% in year 4 and 2.0% in year 5 while the decline "
        "rate is −4.0%."
    )
    assert route_codes(r) == ["consensus-recovery"]
    assert step_names(r) == ["path_step_2", "path_step_3", "path_step_4", "path_step_5"]
    step_3, step_4, step_5 = (input_named(r, f"path_step_{t}") for t in (3, 4, 5))
    assert (step_4.value, step_5.value) == (pytest.approx(0.01), pytest.approx(0.02))
    for step in (step_4, step_5):
        assert (step.tag, step.unit, step.note, step.provenance) == (
            "DATA",
            "ratio",
            None,
            step_3.provenance,
        )


def test_a_thin_year_past_three_ends_the_consensus(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Base + 3 on 4 analysts is not read, nor base + 4 after it on 6: K = 3 and the row is the
    worked row's 4.9533. A thin year past year 3 is not the consensus's, so ``few-analysts``
    does not name it."""
    dc = with_consensus(decline_inputs, (2030, BASE_2 * 1.01, 4), (2031, BASE_2 * 1.01 * 1.02, 6))
    r = value_company(dc, deciles, policy, TODAY)
    assert r.value == pytest.approx(VALUE, abs=1e-9)
    assert r.intermediates["runoff_path"]["consensus_years"] == 3
    assert r.intermediates["runoff_path"]["steps"] == pytest.approx([-0.03, -0.03])
    assert "few-analysts" not in codes(r) and route_codes(r) == []
    assert step_names(r) == ["path_step_2", "path_step_3"]


def test_a_held_year_3_ends_the_consensus_at_year_3(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """No consensus for base + 2 (fiscal 2029): year 3 holds year 2's rate, and the years past 3
    have no consensus revenue to step from, so base + 3 on 6 analysts is not read."""
    a = decline_inputs.annual_estimates
    dc = replace(decline_inputs, annual_estimates=(a[0], a[1]))
    r = value_company(with_consensus(dc, (2030, BASE_2 * 1.01, 6)), deciles, policy, TODAY)
    assert r.intermediates["runoff_path"]["consensus_years"] == 3
    assert r.intermediates["runoff_path"]["steps"] == [pytest.approx(-0.03), None]
    assert route_codes(r) == ["path-held"]
    assert r.value == pytest.approx(VALUE, abs=1e-9)
    assert step_names(r) == ["path_step_2", "path_step_3"]


def test_a_consensus_to_year_ten_leaves_no_fade(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Seven years past base + 2 on 6 analysts: K = N = 10, no year fades, year 10 grows at the
    consensus's own +2%, and the terminal is flat on year 10's revenue. An eighth year past base
    + 2 is past the run-off and not read, so its fall to zero refuses nothing."""
    steps = [-0.01] * 6 + [0.02]
    years, revenue = [], BASE_2
    for year, step in zip(range(2030, 2037), steps, strict=True):
        revenue *= 1 + step
        years.append((year, revenue, 6))
    r = value_company(
        with_consensus(decline_inputs, *years, (2037, 0.0, 6)), deciles, policy, TODAY
    )
    assert r.route == "decline" and r.value is not None
    im = r.intermediates
    assert im["runoff_path"]["consensus_years"] == 10
    assert im["runoff_path"]["steps"] == pytest.approx([-0.03, -0.03, *steps])
    assert im["growth_rates"] == pytest.approx([-0.03] * 3 + steps)
    year_10 = im["revenue_by_year"][-1]
    assert year_10 == pytest.approx(im["revenue_by_year"][-2] * 1.02)
    assert im["terminal_value"] == pytest.approx(year_10 * 0.08 * 0.75 / 0.09)
    assert sentence(r, "consensus-recovery") == (
        "The consensus has revenue growing 2.0% in year 10 while the decline rate is −4.0%."
    )
    assert step_names(r) == [f"path_step_{t}" for t in range(2, 11)]


def test_a_far_year_at_minus_100_refuses(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A consensus year past year 3 whose revenue falls to zero or below, on enough analysts,
    refuses the row as a year 2 or 3 does, with the path's flags."""
    dc = replace(decline_inputs, capital_years=(), peers=())
    for years in (((2030, 0.0, 6),), ((2030, BASE_2 * 1.01, 6), (2031, -5 * M, 6))):
        r = value_company(with_consensus(dc, *years), deciles, policy, TODAY)
        assert_refused(r, "consensus revenue falls to zero or below within the path")
        assert r.intermediates.keys() == {"price_facts"}
    # the path's flags: the rising year 4 is named before the fall in year 5
    assert route_codes(r) == ["consensus-recovery"]
    assert "1.0% in year 4" in sentence(r, "consensus-recovery")


def test_the_expected_return_grows_at_the_path_then_zero(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The growth term reads the path's own rates for years 2 to H + 1, and zero past year N
    (spec 2026-11-06 6.3), where d once served."""
    r = value_company(decline_inputs, deciles, policy, TODAY)
    rates = r.intermediates["growth_rates"]
    growth = math.prod(1 + g for g in rates[1:4]) ** (1 / 3) - 1
    assert r.intermediates["expected_return"]["growth"] == pytest.approx(growth, abs=1e-12)
    # a horizon of 12 years: years 2 to 10, then three years at zero
    long = replace(policy, repricing_horizon_years=12)
    r = value_company(decline_inputs, deciles, long, TODAY)
    growth = math.prod(1 + g for g in rates[1:]) ** (1 / 12) - 1
    assert r.intermediates["expected_return"]["growth"] == pytest.approx(growth, abs=1e-12)


def test_reprice_rebuilds_the_same_path(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A Decline row whose consensus reaches year 5 moves to a new price from its stored
    intermediates: the path, its rates and the value stay; the implied decline rate, read with
    the consensus years as found and the fade from the trial d, moves to the fresh valuation's."""
    dc = with_consensus(decline_inputs, (2030, BASE_2 * 1.01, 6), (2031, BASE_2 * 1.01 * 1.02, 6))
    r = value_company(dc, deciles, policy, TODAY)
    assert r.value is not None
    stored = result_from_json(result_to_json(r))
    moved = reprice(stored, 4.5, REPRICED, policy)
    fresh = value_company(replace(dc, price=4.5), deciles, policy, TODAY)
    assert moved.value == r.value
    assert moved.intermediates["runoff_path"] == r.intermediates["runoff_path"]
    assert moved.intermediates["growth_rates"] == r.intermediates["growth_rates"]
    for key in PRICE_KEYS:
        assert moved.intermediates[key] == fresh.intermediates[key], key
    implied = moved.intermediates["implied_decline_rate"]
    assert implied is not None and implied != r.intermediates["implied_decline_rate"]
    at_value = reprice(stored, r.value, REPRICED, policy).intermediates["implied_decline_rate"]
    assert at_value == pytest.approx(-0.04, abs=1e-6)
