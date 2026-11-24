"""The Decline route through ``value_company``: spec 13.1's row on the run-off DCF with the
distress weighting, the net-current-asset floor and the distress signals; the refusals in order,
the flags and their sentences, the inputs, the JSON round trip and the price refresh.

The fixture (``support.engine_companies.decline_inputs``) is spec 13.1 in USD millions on 100 m
shares, so a share's figures are the spec's and the totals are the spec's times a million."""

import math
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from support.engine_companies import (
    QUARTER_SHEET_SOURCE,
    SHIFT_SENTENCE,
    annual,
    fiscal_years,
    half_yearly,
    judged_moat,
    on_quarter_sheet,
    on_shifted_sheet,
    unshifted,
    with_minority,
    with_ntm_revenue,
)

from fairband.engine.anchor import TrailingFigures
from fairband.engine.balance import NewestSheet
from fairband.engine.classifier import Deciles, Series
from fairband.engine.levels import levels_for
from fairband.engine.overrides import Override
from fairband.engine.revenue_growth import PeerFigures, PeerSource
from fairband.engine.review import review_company
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.route_steps import sheet_entry
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
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)  # the time an override is made
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
    "minority_interest",
    "balance_sheet",
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
    "trailing_end",
    "margin_history",
    "implied_decline_rate",
    "multiples",
    "expected_return",
}
PRICE_KEYS = ("implied_decline_rate", "multiples", "expected_return")
# What a plain refusal keeps: the price facts, the trailing period end and the ten-year median
# margins every refusal of a row with trailing figures and a series carries.
PLAIN_REFUSAL_KEYS = {"price_facts", "trailing_end", "margin_history"}
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


def sheet(inputs: CompanyInputs) -> NewestSheet:
    assert inputs.sheet is not None
    return inputs.sheet


def with_floor(inputs: CompanyInputs, current_assets: float) -> CompanyInputs:
    """The company with the current assets of its newest balance sheet, which the floor reads, at
    ``current_assets``; its fiscal years' balance sheets, which Z″ and F read, as they were."""
    return replace(inputs, sheet=replace(sheet(inputs), total_current_assets=current_assets))


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
    # the fixture's newest balance sheet is its newest fiscal year's
    assert im["balance_sheet"] == {
        "period_end": "2025-12-31",
        "label": "fiscal 2025",
        "quarterly": False,
    }
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
    assert im["eps"] == {
        "reported": 0.45,
        "clean": 0.45,
        "forward": None,
        "forward_after_sbc": None,
    }
    assert im["epv"] == pytest.approx(0.45 / 0.09)
    # $3.00 against $4.9533: 0.606 × the value, above the None row's buy level, 0.60 × the value
    assert (r.price_to_value, r.designation) == (3.0 / r.value, "below")
    assert r.levels is not None and r.levels.buy == pytest.approx(r.value * 0.60)  # None moat
    # the price-side figures: no decline rate in the scan gives $3.00, the run-off being worth
    # 3.1251 at −50% (spec 13.1); the trailing P/E and no forward one; and the expected return
    # growing at the path's rates for years 2 to 4
    assert im["implied_decline_rate"] is None
    assert im["multiples"]["pe_reported"] == pytest.approx(3.0 / 0.45)
    assert im["multiples"]["pe_forward"] is None
    assert im["multiples"]["pe_forward_after_sbc"] is None
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
    assert r.intermediates.keys() == PLAIN_REFUSAL_KEYS
    r = valued(replace(dc, capital_years=(), peers=()))
    assert_refused(r, "no sales-to-capital")
    assert r.intermediates.keys() == PLAIN_REFUSAL_KEYS
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
    floored = with_floor(dc, 1_100 * M)
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
    rich = with_floor(decline_inputs, 1_100 * M)  # NCAV 6.00 a share
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
        "The statement periods on file are neither four consecutive quarters nor two consecutive "
        "half-years, so the trailing figures are fiscal 2025's.",
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


def test_the_floor_reads_the_newest_sheet(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-13 12.2: the newest fiscal year holds current assets 300 and liabilities 500
    (NCAV −200), the quarter of 30 Sep 2026 900 and 500. The floor reads the quarter's: NCAV 400,
    4.00 a share, below the run-off's 5.0748, so the value stays 4.9533. Z″ and F stay on the
    fiscal years; the floor's two lines are cited under their own names, to the sheet with its
    period, beside fiscal 2025's lines under theirs."""
    plain = value_company(decline_inputs, deciles, policy, TODAY)
    dc = on_quarter_sheet(decline_inputs, 900 * M, 500 * M)
    r = value_company(dc, deciles, policy, TODAY)
    im = r.intermediates
    assert (im["ncav"], im["ncav_per_share"]) == (400 * M, 4.0)
    assert im["floored_per_share"] == im["going_concern_per_share"]
    assert r.value == pytest.approx(VALUE, abs=1e-9) and "ncav-floor" not in codes(r)
    assert (im["altman_z"], im["piotroski_f"]) == (
        plain.intermediates["altman_z"],
        plain.intermediates["piotroski_f"],
    )
    assert im["altman_z"]["year"] == 2025
    period = "the balance sheet of fiscal 2026 Q3"
    for name, figure in (
        ("floor_current_assets", 900 * M),
        ("floor_total_liabilities", 500 * M),
        ("debt", 200 * M),
        ("cash", 100 * M),
    ):
        cited = input_named(r, name)
        assert (cited.value, cited.unit, cited.note, cited.tag) == (figure, "USD", period, "DATA")
        assert cited.provenance == dc.provenance["balance_sheet"]
        assert (cited.provenance.source, cited.provenance.as_of) == (
            QUARTER_SHEET_SOURCE,
            date(2026, 9, 30),
        )
    tca, tl = input_named(r, "total_current_assets"), input_named(r, "total_liabilities")
    assert (tca.value, tca.note, tl.value, tl.note) == (
        300 * M,
        "fiscal 2025",
        500 * M,
        "fiscal 2025",
    )
    assert tca.provenance.source == tl.provenance.source == "FMP income-statement"
    q3 = {"period_end": "2026-09-30", "label": "fiscal 2026 Q3", "quarterly": True}
    assert im["balance_sheet"] == q3 == sheet_entry(dc)["balance_sheet"]
    # the floor binds on the sheet's figures alone: current assets 1,100 give 6.00 a share
    floored = value_company(with_floor(dc, 1_100 * M), deciles, policy, TODAY)
    assert floored.value == pytest.approx(5.832244268746113, abs=1e-9)
    assert floored.intermediates["altman_z"] == plain.intermediates["altman_z"]
    # a row refused for its value keeps the sheet and cites the floor's lines
    chronic = value_company(
        with_margins(dc, [-0.02, -0.03, -0.03, -0.03, -0.03]), deciles, policy, TODAY
    )
    assert_refused(chronic, NOT_POSITIVE)
    assert chronic.intermediates["balance_sheet"] == q3
    assert input_named(chronic, "floor_current_assets").value == 900 * M


def test_a_missing_total_liabilities_line_applies_no_floor(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Current assets of 1,100 would floor the value at 11.00 a share on a nil liability; with the
    newest sheet's line missing no floor is applied, and the flag names the sheet's period. Z″
    reads the fiscal year's line, so a fiscal year without it loses Z″ and not the floor."""
    dc = on_quarter_sheet(decline_inputs, 1_100 * M, None)
    r = value_company(dc, deciles, policy, TODAY)
    im = r.intermediates
    assert (im["ncav"], im["ncav_per_share"]) == (None, None)
    assert im["floored_per_share"] == im["going_concern_per_share"]
    assert r.value == pytest.approx(VALUE, abs=1e-9)
    assert "ncav-floor" not in codes(r)
    assert sentence(r, "line-not-presented:totalLiabilities") == (
        "The newest balance sheet (fiscal 2026 Q3) does not present total liabilities, so no "
        "net-current-asset floor is applied."
    )
    assert input_named(r, "floor_total_liabilities").value is None
    assert im["altman_z"] is not None and im["piotroski_f"]["read"] == 9
    # the fiscal year without the line: no Z″ (F does not read it), the sheet's floor stands
    newest = replace(dc.balance_years[-1], total_liabilities=None)
    lacking = replace(dc, sheet=sheet(decline_inputs), balance_years=(dc.balance_years[0], newest))
    r = value_company(lacking, deciles, policy, TODAY)
    assert r.intermediates["altman_z"] is None and r.intermediates["piotroski_f"]["read"] == 9
    assert r.intermediates["ncav"] == -200 * M
    assert "line-not-presented:totalLiabilities" not in codes(r)
    # no balance sheet on file: no floor, and Z″ and F as before
    r = value_company(replace(dc, sheet=None), deciles, policy, TODAY)
    assert sentence(r, "line-not-presented:totalLiabilities") == (
        "No balance sheet is on file, so no net-current-asset floor is applied."
    )
    assert (r.intermediates["ncav"], r.intermediates["balance_sheet"]) == (None, None)
    names = [i.name for i in r.inputs]
    assert "floor_current_assets" not in names and "floor_total_liabilities" not in names
    assert r.intermediates["altman_z"] is not None and r.intermediates["piotroski_f"] is not None
    assert r.value == pytest.approx(VALUE, abs=1e-9)
    # no fiscal year's balance sheet: no Z″, no F, and the sheet's floor stands
    r = value_company(replace(decline_inputs, balance_years=()), deciles, policy, TODAY)
    assert (r.intermediates["altman_z"], r.intermediates["piotroski_f"]) == (None, None)
    assert r.intermediates["ncav"] == -200 * M
    assert "line-not-presented:totalLiabilities" not in codes(r)
    # one balance sheet: Z″ and no F
    r = value_company(replace(dc, balance_years=dc.balance_years[1:]), deciles, policy, TODAY)
    assert r.intermediates["altman_z"] is not None and r.intermediates["piotroski_f"] is None


def _flagged(dc: CompanyInputs) -> CompanyInputs:
    """A row that raises path-held, line-not-presented:cash, ncav-floor, z-distress, f-score-low,
    reinvesting-in-decline and margin-flag: fiscal 2029 missing from the consensus; no cash
    figure; current assets of 1,100 against liabilities of 500 on the newest sheet and on the
    newest fiscal year's, with a deficit of 3,000 (Z″ −0.60); a loss on falling cash flow that
    issued stock and levered up, its current ratio alone up (F 1 of 9); capital spending of 60
    against depreciation of 40, under half the operating cash flow of 150; a sixth fiscal year, so
    the margin flag has its six, and a trailing margin of 13% against their median of 8%."""
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
        with_floor(dc, 1_100 * M),
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
        "ntm_revenue",
        "path_step_2",
        "path_step_3",
        "interest_expense",
        "sales_to_capital",
        "debt",
        "cash",
        "minority_interest",
        "floor_current_assets",
        "floor_total_liabilities",
        "total_current_assets",
        "total_liabilities",
        "depreciation",
    }
    # debt, cash, the minority interest, then the floor's two lines, all from the newest balance
    # sheet, its newest fiscal year's on the fixture, then the lines of the fiscal years Z″ and F
    # read
    at = names.index("debt")
    assert names[at : at + 6] == [
        "debt",
        "cash",
        "minority_interest",
        "floor_current_assets",
        "floor_total_liabilities",
        "total_current_assets",
    ]
    for name, figure in (
        ("debt", 200 * M),
        ("cash", 100 * M),
        ("minority_interest", None),  # the fixture's sheet presents none
        ("floor_current_assets", 300 * M),
        ("floor_total_liabilities", 500 * M),
    ):
        cited = input_named(r, name)
        assert (cited.value, cited.note) == (figure, "the balance sheet of fiscal 2025"), name
        assert cited.provenance == decline_inputs.provenance["balance_sheet"], name
    # the moat class right after the inputs every result carries, the moat table's (spec
    # 2026-11-19 8.5), then the route's rules
    assert rules == [
        "moat_class",
        "required_return",
        "runoff_years",
        "runoff_recovery",
        "distress_sale_fraction",
        "synthetic_rating",
        "default_probability_10y",
        "z_distress",
        "z_safe",
        "f_score_low",
    ]
    for absent in (
        "aggregate_roic",
        "runway_return",
        "terminal_growth",
        "terminal_roic",
        "margin_of_safety",
    ):
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
    # the balance sheet lines Z″ and F read, each year's cited to the annual statements
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
    moat = rows.pop("moat_class")
    assert (moat.note, moat.provenance) == ("None", decline_inputs.provenance["moat_class"])
    assert all(i.provenance.source == f"policy {policy.version}" for i in rows.values())
    # no rating: the two rows say why and cite no figure
    no_debt = value_company(replace(decline_inputs, cash=250 * M), deciles, policy, TODAY)
    rating, pi = (
        input_named(no_debt, "synthetic_rating"),
        input_named(no_debt, "default_probability_10y"),
    )
    assert (rating.value, rating.note) == (None, "no rating: cash covers debt")
    assert (pi.value, pi.note) == (None, "no net debt: π is 0")


def test_the_decline_route_reads_the_table_s_class(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-19 8.5: the Decline route takes the margin of safety of the company's class in
    the moat table, an agent's among them. The run-off reads no moat, so a Wide row's value is the
    None row's, and its levels take Wide's margin of safety."""
    none = value_company(decline_inputs, deciles, policy, TODAY)
    wide = value_company(replace(decline_inputs, moat_class="Wide"), deciles, policy, TODAY)
    assert wide.value is not None and wide.value == none.value
    assert wide.intermediates["moat"] == "Wide"
    assert wide.levels == levels_for(wide.value, "Wide", policy) != none.levels
    assert wide.levels.buy == pytest.approx(wide.value * (1 - policy.margin_of_safety["Wide"]))
    # no result stores the margin itself (spec 2026-11-23 thresholds, 5.3): the levels show it
    assert "margin_of_safety" not in {i.name for i in wide.inputs}
    # at $3.00, 0.606 × the value, the Wide row is under its buy level and the None row is not
    assert (wide.designation, none.designation) == ("well-below", "below")
    agent = judged_moat(decline_inputs, "Wide", "agent claude-opus-5-5", NOW, "a toll road")
    judged = value_company(agent, deciles, policy, TODAY)
    assert (judged.value, judged.levels) == (wide.value, wide.levels)
    assert input_named(judged, "moat_class").tag == "JUDGMENT"


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
    # the value at each trial d is rebuilt with the minority interest (spec 2026-11-13 13): at the
    # value of a row with $50 m of it, 4.4533, the price implies the route's own d, and at $4.00
    # the rate is a valuation's at that price
    held = with_minority(decline_inputs, 50 * M)
    r = value_company(held, deciles, policy, TODAY)
    stored = result_from_json(result_to_json(r))
    at_value = reprice(stored, VALUE - 0.5, REPRICED, policy).intermediates
    assert at_value["implied_decline_rate"] == pytest.approx(-0.04, abs=1e-6)
    assert at_value["minority_interest"] == 50 * M
    moved = reprice(stored, 4.0, REPRICED, policy)
    fresh = value_company(replace(held, price=4.0), deciles, policy, TODAY)
    for key in PRICE_KEYS:
        assert moved.intermediates[key] == fresh.intermediates[key], key
    assert moved.intermediates["implied_decline_rate"] > below


def test_the_minority_interest_comes_off_each_claim(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-13 13 on spec 13.1's row: $50 m of minority interest on 100 m shares takes
    $0.50 off the going concern (5.0748 to 4.5748), off the distress sale (2.6449 to 2.1449) and
    so off the value (4.9533 to 4.4533), and $50 m off the going-concern equity. The distress
    proceeds, NCAV and the rating read the firm value, the sheet, debt and cash alone; the floor a
    share is NCAV less the minority interest, (−200 − 50) ÷ 100. With current assets of 1,100 the
    floor is (600 − 50) ÷ 100 = 5.50, above the run-off's 4.5748, and the value 5.8322 − 0.50."""
    plain = value_company(decline_inputs, deciles, policy, TODAY)
    held = with_minority(decline_inputs, 50 * M)
    r = value_company(held, deciles, policy, TODAY)
    assert r.value == pytest.approx(VALUE - 0.5, abs=1e-9)
    im, was = r.intermediates, plain.intermediates
    assert (im["minority_interest"], was["minority_interest"]) == (50 * M, 0.0)
    assert im["going_concern_per_share"] == pytest.approx(GOING_CONCERN - 0.5, abs=1e-9)
    assert im["distress_per_share"] == pytest.approx(DISTRESS - 0.5, abs=1e-9)
    assert im["value_per_share"] == r.value
    assert im["equity"] == pytest.approx(was["equity"] - 50 * M, abs=1e-3)
    for same in ("firm_value", "distress_proceeds", "ncav", "rating", "pi", "debt", "cash"):
        assert im[same] == was[same], same
    assert (im["ncav"], im["ncav_per_share"]) == (-200 * M, -2.5)
    cited = input_named(r, "minority_interest")
    assert (cited.value, cited.unit, cited.note) == (
        50 * M,
        "USD",
        "the balance sheet of fiscal 2025",
    )
    assert cited.provenance == held.provenance["balance_sheet"]
    # the floor binds less the minority interest
    floored = value_company(with_floor(held, 1_100 * M), deciles, policy, TODAY)
    fim = floored.intermediates
    assert (fim["ncav"], fim["ncav_per_share"]) == (600 * M, pytest.approx(5.5))
    assert fim["floored_per_share"] == pytest.approx(5.5)
    assert floored.value == pytest.approx(5.832244268746113 - 0.5, abs=1e-9)
    assert sentence(floored, "ncav-floor") == (
        "The floored value is the net current asset value less the minority interest, 5.50 a "
        "share; the run-off gives 4.57."
    )
    # nil: as the plain row, but for the entry
    for line in (None, 0.0, -10 * M):
        nil = value_company(with_minority(decline_inputs, line), deciles, policy, TODAY)
        assert (nil.value, nil.flags, nil.intermediates) == (
            plain.value,
            plain.flags,
            plain.intermediates,
        )
        assert input_named(nil, "minority_interest").value == line


def test_the_ncav_floor_names_the_minority_interest(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The ``ncav-floor`` sentence names the floor a share as what it is: with $50 m of minority
    interest in force, from the sheet or an agent's ``balance.minority``, "the net current asset
    value less the minority interest", (600 − 50) ÷ 100 = 5.50 against the run-off's 4.57; with
    none in force (a line not presented, at zero or below zero), word for word as before 1.4,
    6.00 against 5.07. A price refresh keeps the sentence a fresh valuation at the new price
    gives."""
    floor = with_floor(decline_inputs, 1_100 * M)
    less = (
        "The floored value is the net current asset value less the minority interest, 5.50 a "
        "share; the run-off gives 4.57."
    )
    held = value_company(with_minority(floor, 50 * M), deciles, policy, TODAY)
    assert sentence(held, "ncav-floor") == less
    judged = value_company(
        floor,
        deciles,
        policy,
        TODAY,
        {"balance.minority": Override(7, "balance.minority", 50 * M, "agent", None, NOW, "a 10-Q")},
    )
    assert sentence(judged, "ncav-floor") == less
    for line in (None, 0.0, -10 * M):
        nil = value_company(with_minority(floor, line), deciles, policy, TODAY)
        assert sentence(nil, "ncav-floor") == (
            "The floored value is the net current asset value 6.00 a share; the run-off gives 5.07."
        )
    # the price refresh keeps the sentence: the floor does not move with the price
    stored = result_from_json(result_to_json(held))
    moved = reprice(stored, 4.0, REPRICED, policy)
    fresh = value_company(replace(with_minority(floor, 50 * M), price=4.0), deciles, policy, TODAY)
    assert sentence(moved, "ncav-floor") == sentence(fresh, "ncav-floor") == less


def test_a_quarter_sheet_that_shifted_is_noted_and_moves_nothing(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-13 12.5: DCCO's newest sheet is its quarter of 30 Sep 2026, which presents no
    minority interest where fiscal 2025's sheet showed $45 m. The note ``sheet-shift`` shows, the
    bridge's ``line-not-presented`` flags before it and the floor's after; the value, the levels,
    every intermediate, the inputs and the other flags are the row's without the two sheets'
    lines."""
    dc = on_shifted_sheet(decline_inputs)
    r = value_company(dc, deciles, policy, TODAY)
    plain = value_company(unshifted(dc), deciles, policy, TODAY)
    assert r.route == "decline" and r.value is not None
    assert sentence(r, "sheet-shift") == SHIFT_SENTENCE
    assert (r.value, r.levels, r.intermediates, r.inputs) == (
        plain.value,
        plain.levels,
        plain.intermediates,
        plain.inputs,
    )
    assert tuple(f for f in r.flags if f.code != "sheet-shift") == plain.flags
    # its place among the line flags: no cash and no total liabilities on the quarter's sheet
    lines = replace(sheet(decline_inputs), total_liabilities=None)
    bare = on_shifted_sheet(replace(decline_inputs, cash=None, sheet=lines))
    found = route_codes(value_company(bare, deciles, policy, TODAY))
    assert [c for c in found if c.startswith("line-not-presented") or c == "sheet-shift"] == [
        "line-not-presented:cash",
        "sheet-shift",
        "line-not-presented:totalLiabilities",
    ]


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


def test_a_year_3_held_for_want_of_base_plus_2_ends_the_consensus(
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
    + 2, on enough analysts, is past the run-off and not read."""
    steps = [-0.01] * 6 + [0.02]
    years, revenue = [], BASE_2
    for year, step in zip(range(2030, 2037), steps, strict=True):
        revenue *= 1 + step
        years.append((year, revenue, 6))
    r = value_company(
        with_consensus(decline_inputs, *years, (2037, revenue * 0.99, 6)), deciles, policy, TODAY
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


def test_a_far_year_at_zero_ends_the_consensus(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-06 6.1: base + 3 at +1% on 6 analysts and base + 4 at zero on 6 analysts. A year
    past year 3 is read only while its revenue mean is above zero, so base + 4 ends the consensus
    at year 4: no refusal, no flag for it, and the fade from year 5. A mean below zero ends it the
    same way."""
    fade = [-0.04 * (10 - t) / 6 for t in range(5, 11)]
    for mean in (0.0, -5 * M):
        dc = with_consensus(decline_inputs, (2030, BASE_2 * 1.01, 6), (2031, mean, 6))
        r = value_company(dc, deciles, policy, TODAY)
        assert (r.route, r.refusal) == ("decline", None) and r.value is not None
        im = r.intermediates
        assert im["runoff_path"]["consensus_years"] == 4
        assert im["runoff_path"]["steps"] == pytest.approx([-0.03, -0.03, 0.01])
        assert im["growth_rates"] == pytest.approx([-0.03] * 3 + [0.01] + fade)
        assert im["growth_rates"][-1] == 0.0
        assert route_codes(r) == ["consensus-recovery"] and "few-analysts" not in codes(r)
        assert sentence(r, "consensus-recovery") == (
            "The consensus has revenue growing 1.0% in year 4 while the decline rate is −4.0%."
        )
        assert step_names(r) == ["path_step_2", "path_step_3", "path_step_4"]
    # a fall to zero in years 2 and 3 still refuses, as before (test_the_refusal_order)


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


def _ntm_revenue(value: float) -> Override:
    return Override(6, "revenue.ntm", value, "agent", "claude-opus-5-5", NOW, "guided 950")


def test_the_ntm_revenue_override_replaces_year_one(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 13.1's row has an NTM consensus revenue of 970. An override of 950 values it as a
    consensus of 950 would: year 1 of the run-off, its rebuild key, and the recovery flag read
    from it; the JUDGMENT entry stands for the ``ntm_revenue`` data entry, and the bridge's line
    reads the consensus as its old value."""
    mechanical = value_company(decline_inputs, deciles, policy, TODAY)
    guided = [_ntm_revenue(950 * M)]
    judged = value_company(decline_inputs, deciles, policy, TODAY, {"revenue.ntm": guided[0]})
    raised = value_company(with_ntm_revenue(decline_inputs, 950 * M), deciles, policy, TODAY)
    assert judged.value is not None and mechanical.value is not None
    assert judged.value == raised.value and judged.value < mechanical.value
    assert judged.intermediates["runoff_path"] == raised.intermediates["runoff_path"]
    assert judged.intermediates["runoff_path"]["ntm_revenue"] == 950 * M
    assert judged.intermediates["revenue_by_year"][0] == pytest.approx(950 * M)
    assert "ntm_revenue" not in {x.name for x in judged.inputs}
    ntm = input_named(judged, "revenue.ntm")
    assert (ntm.tag, ntm.value, ntm.unit) == ("JUDGMENT", 950 * M, "USD")
    review = review_company(decline_inputs, deciles, policy, TODAY, guided, mechanical)
    [line] = review.bridge
    assert (line.tag, line.old, line.new) == ("revenue.ntm", pytest.approx(970 * M), 950 * M)
    # a guided year 1 that grows names the recovery, as a consensus that grows does
    recovery = value_company(
        decline_inputs, deciles, policy, TODAY, {"revenue.ntm": _ntm_revenue(1_050 * M)}
    )
    assert "consensus-recovery" in codes(recovery)
    assert "consensus-recovery" not in codes(mechanical)


def test_the_ntm_revenue_override_is_read_on_a_consensus_with_its_quarters(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The override stands for the figure the four NTM quarters give: on quarters whose revenue
    sums to zero it makes the consensus usable; with no quarters on file it is not read, and years
    1 to 3 shrink at d as they do without it."""
    q = decline_inputs.quarter_estimates
    zero = tuple(replace(x, revenue=v) for x, v in zip(q, (1e9, -1e9, 0.0, 0.0), strict=True))
    judged = {"revenue.ntm": _ntm_revenue(970 * M)}
    lifted = value_company(
        replace(decline_inputs, quarter_estimates=zero), deciles, policy, TODAY, judged
    )
    assert lifted.value == value_company(decline_inputs, deciles, policy, TODAY).value
    assert "path-on-trend" not in codes(lifted)
    bare = replace(decline_inputs, quarter_estimates=())
    unread = value_company(bare, deciles, policy, TODAY, judged)
    assert unread.value == value_company(bare, deciles, policy, TODAY).value
    assert unread.intermediates["runoff_path"]["ntm_revenue"] is None
    assert "path-on-trend" in codes(unread)


def test_a_half_yearly_reporter_reads_its_two_half_years(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-10 8: DCCO reporting half-yearly, its consensus two half-years of 488 m and
    482 m of revenue ending 2027-03-31 and 2027-09-30. The window is the two: year 1 reads 970 m,
    the base year is 2027 as on the quarters, and the value is the worked row's. A quarterly
    reporter reads no window in them, so its years 1 to 3 shrink at d."""
    halves = half_yearly(decline_inputs)
    r = value_company(halves, deciles, policy, TODAY)
    assert (r.route, r.refusal) == ("decline", None)
    assert r.intermediates["runoff_path"]["ntm_revenue"] == pytest.approx(970 * M)
    assert r.intermediates["runoff_path"]["steps"] == pytest.approx([-0.03, -0.03])
    assert r.value == pytest.approx(VALUE, abs=1e-9)
    assert "path-on-trend" not in codes(r)
    on_quarters = replace(halves, trailing=decline_inputs.trailing)
    on_trend = value_company(on_quarters, deciles, policy, TODAY)
    assert on_trend.intermediates["runoff_path"]["ntm_revenue"] is None
    assert "path-on-trend" in codes(on_trend)
