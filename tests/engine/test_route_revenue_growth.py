"""The revenue-growth route through ``value_company``: High Growth and Young Growth rows valued on
Damodaran's revenue DCF, the refusals in order, the flags, the growth-route cross-check, and the
price refresh rebuilding every price-side figure from the intermediates."""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest
from support.engine_companies import annual, capital_years, fiscal_years

from fairband.engine.anchor import AnnualEstimate
from fairband.engine.classifier import Deciles
from fairband.engine.revenue_growth import (
    Bridge,
    MarginPath,
    PeerFigures,
    PeerSource,
    RevenueCharge,
    RevenuePath,
    revenue_valuation,
)
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.route_revenue_growth import consensus_beyond, implied_margin_at_price
from fairband.engine.types import TaggedInput, ValuationResult, result_from_json, result_to_json
from fairband.policy import Policy

TODAY = date(2026, 10, 31)
REPRICED = date(2026, 11, 2)

REVENUE_GROWTH_KEYS = {
    "ntm_revenue",
    "path",
    "path_steps",
    "revenue_path",
    "growth_rates",
    "margin_start",
    "margin_path",
    "target_margin",
    "tax_rate",
    "moat",
    "sales_to_capital",
    "revenue_by_year",
    "ebit_by_year",
    "tax_by_year",
    "nopat_by_year",
    "reinvestment_by_year",
    "fcff_by_year",
    "terminal_roic",
    "terminal_nopat",
    "terminal_value",
    "firm_value",
    "debt",
    "cash",
    "equity",
    "shares",
    "value_per_share",
    "value_by_margin",
    "return_on_new_capital",
    "peer_roic_median",
    "eps",
    "epv",
    "dividend_yield",
    "net_buyback_yield",
    "income_basis",
    "price_facts",
    "growth_route",
    "implied_growth",
    "implied_margin",
    "multiples",
    "growth_share",
    "expected_return",
}
# What a row refused for its target margin keeps: the keys that rebuild the margin the price
# needs, that margin, and the price facts every refusal carries.
TARGET_REFUSAL_KEYS = {
    "revenue_path",
    "margin_start",
    "tax_rate",
    "moat",
    "debt",
    "cash",
    "shares",
    "sales_to_capital",
    "implied_margin",
    "price_facts",
}
# The fixture's sales class from its $10 bn of trailing revenue, and that class's cap on the held
# rate; the year-3 consensus of 20% is above it.
CLASS = "$7,000-12,000 Mn"
CAP = 0.15
CAP_NOTE = (
    "the Base Rate Book's 90th-percentile five-year sales growth for the $7,000-12,000 Mn sales "
    "class; "
)
# The fixture's three peers as the industry fallback's, FMP's list having left one that counts.
INDUSTRY = "Specialty Industrial Machinery"
FROM_INDUSTRY = PeerSource("industry", INDUSTRY, 1)
INDUSTRY_SOURCE = "the universe's Specialty Industrial Machinery industry and the peers' statements"
FMP_SOURCE = "FMP stock-peers and the peers' statements"
PRICE_KEYS = (
    "implied_growth",
    "implied_margin",
    "multiples",
    "growth_share",
    "expected_return",
    "growth_route",
)


# The fixture's own five-year marginal sales-to-capital: revenue up 35% a year on invested
# capital of 0.83 × revenue.
OWN = 2 * 1.35 / (0.83 * 2.35)
# A trailing operating loss of $15 bn on the fixture's $10 bn of revenue, a margin of -150%, below
# the loss ramp bound; one of $10.5 bn, -105%, is below it and still valued.
LOSS = -15_000e6
VALUED_LOSS = -10_500e6


def with_loss(inputs: CompanyInputs, operating_income: float) -> CompanyInputs:
    """The company with its trailing operating income replaced."""
    t = inputs.trailing
    assert t is not None
    return replace(inputs, trailing=replace(t, operating_income=operating_income))


def with_own_measure(inputs: CompanyInputs, own: float) -> CompanyInputs:
    """The company with its invested capital scaled so that its own five-year marginal
    sales-to-capital is ``own``; its returns on capital are unchanged."""
    scale = OWN / own
    figures = [(fy.revenue, fy.operating_income) for fy in inputs.series]
    revenue = [rev * scale for rev, _ in figures if rev is not None]
    margins = [oi / rev for rev, oi in figures if rev is not None and oi is not None]
    assert len(revenue) == len(margins) == len(figures)
    return replace(inputs, capital_years=capital_years(fiscal_years(revenue, margins)))


def codes(r: ValuationResult) -> list[str]:
    return [f.code for f in r.flags]


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


def test_high_growth_is_valued_on_the_revenue_route(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(high_growth_inputs, deciles, policy, TODAY)
    assert r.route == "revenue-growth" and r.value is not None and r.levels is not None
    assert r.phase.phase == "High Growth" and r.refusal is None
    im = r.intermediates
    assert set(im) == REVENUE_GROWTH_KEYS
    assert len(im["revenue_by_year"]) == 10 and len(im["margin_path"]["by_year"]) == 10
    assert len(im["growth_rates"]) == 10 and im["growth_rates"][-1] == pytest.approx(0.03)
    assert im["ntm_revenue"] == pytest.approx(12_400e6)
    assert im["revenue_by_year"][0] == im["ntm_revenue"]
    assert im["path"] == {
        "base_year": 2027,
        "analysts": [15, 12],
        "held": [False, False],
        "sales_class": CLASS,
        "cap": pytest.approx(CAP),
    }
    assert im["path_steps"] == pytest.approx([16_000 / 13_000 - 1, 19_200 / 16_000 - 1])
    assert im["margin_start"] == pytest.approx(-0.09)
    assert im["margin_path"]["by_year"][-1] == pytest.approx(0.20)
    assert im["margin_path"]["ramp"] == "margin"
    assert im["target_margin"]["value"] == pytest.approx(0.20) and im["target_margin"]["count"] == 3
    assert im["target_margin"]["largest_symbol"] == "PEER2"
    assert [p["symbol"] for p in im["target_margin"]["peers"]] == ["PEER1", "PEER2", "PEER3"]
    assert im["sales_to_capital"]["used"] in ("own", "peers")
    # revenue up 35% a year on invested capital 0.83 × revenue: 2 × 1.35 ÷ (0.83 × 2.35)
    assert im["sales_to_capital"] == {
        "used": "own",
        "own": pytest.approx(2 * 1.35 / (0.83 * 2.35)),
        "own_usable": True,
        "own_below_bound": False,
        "peers": pytest.approx(2.5),
        "value": pytest.approx(2 * 1.35 / (0.83 * 2.35)),
    }
    # no moat score: the terminal return is r
    assert im["moat"] == "None" and im["terminal_roic"] == policy.required_return
    # the terminal reads year 10's operating income at the full 25%, whatever carry is left
    assert im["terminal_nopat"] == pytest.approx(im["ebit_by_year"][-1] * 0.75)
    assert im["value_by_margin"].keys() == {"low", "median", "high"}
    assert im["value_by_margin"]["median"] == im["value_per_share"] == r.value
    assert im["equity"] == pytest.approx(im["firm_value"] - 1_000e6 + 3_000e6)
    assert r.value == pytest.approx(im["equity"] / 100e6)
    assert im["implied_growth"] is not None and im["implied_margin"] is not None
    assert "failure-not-charged" not in [f.code for f in r.flags]
    assert im["growth_route"] == {"refusal": "no positive forward anchor"}
    names = [i.name for i in r.inputs]
    for name in ("ntm_revenue", "path_step_2", "path_step_3", "target_margin", "sales_to_capital"):
        assert name in names, name
    for name in ("debt", "cash", "high_growth_years", "margin_convergence_year", "peer_min"):
        assert name in names, name
    [target] = [i for i in r.inputs if i.name == "target_margin"]
    assert target.provenance.source == "FMP stock-peers and the peers' statements"
    assert target.note is not None and "3 mature peers" in target.note


def test_flags_follow_the_spec_order(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The path's, the capital build's, the bridge's, the industry peers, the tax carry, the
    implied-return check, the trailing flags and the value spread, each code once."""
    thin = (*high_growth_inputs.annual_estimates[:2],)  # fiscal 2029 missing: the path holds
    inputs = replace(
        high_growth_inputs, annual_estimates=thin, cash=None, peer_source=FROM_INDUSTRY
    )
    r = value_company(inputs, deciles, policy, TODAY)
    route_codes = [c for c in codes(r) if c not in {f.code for f in r.phase.checks}]
    assert route_codes == [
        "path-held",
        "consensus-above-base-rate",
        "roic-on-n-years",
        "line-not-presented:cash",
        "peers-from-industry",
        "tax-loss-history-unknown",
        "return-above-peers",
        "equity-raise",
        "negative-fcf",
        "value-spread",
    ]
    assert len(codes(r)) == len(set(codes(r)))


def test_young_growth_values_like_high_growth_and_is_flagged(
    young_growth_inputs: CompanyInputs,
    high_growth_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
) -> None:
    same = replace(
        young_growth_inputs,
        series=high_growth_inputs.series,
        capital_years=high_growth_inputs.capital_years,
    )
    high = value_company(same, deciles, policy, TODAY)
    assert high.phase.phase == "High Growth"
    r = value_company(young_growth_inputs, deciles, policy, TODAY)
    assert r.phase.phase == "Young Growth" and r.route == "revenue-growth"
    # same inputs, the phase apart: identical value, levels and figures, one route
    assert r.value == high.value and r.levels == high.levels
    young = dict(r.intermediates)
    assert young.pop("failure_probability") == {
        "value": None,
        "reason": "no survival table fits a listed company above $2 billion",
    }
    assert young == high.intermediates
    assert [f.code for f in r.flags if f.code == "failure-not-charged"] == ["failure-not-charged"]
    assert "failure-not-charged" not in codes(high)
    # after the implied-return check, before the trailing flags
    route = codes(r)
    assert route.index("return-above-peers") < route.index("failure-not-charged")
    assert route.index("failure-not-charged") < route.index("equity-raise")


def test_refusal_order(high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    hg, t = high_growth_inputs, high_growth_inputs.trailing
    assert t is not None

    def valued(inputs: CompanyInputs) -> ValuationResult:
        return value_company(inputs, deciles, policy, TODAY)

    for revenue in (None, 0.0, -5.0):
        no_revenue = replace(hg, trailing=replace(t, revenue=revenue), tax_rate_latest=None)
        assert_refused(valued(no_revenue), "no trailing revenue")
    no_income = replace(hg, trailing=replace(t, operating_income=None), tax_rate_latest=None)
    assert_refused(valued(no_income), "no trailing operating income")
    assert_refused(valued(replace(hg, tax_rate_latest=None, peers=())), "no statutory tax rate")
    assert_refused(valued(replace(hg, quarter_estimates=(), peers=())), "incomplete NTM consensus")
    q = hg.quarter_estimates
    gap = (*q[:3], replace(q[3], revenue=None))
    assert_refused(valued(replace(hg, quarter_estimates=gap)), "incomplete NTM consensus")
    # an NTM window whose revenue means sum to zero, before a path that falls to zero
    a = hg.annual_estimates
    zero_ntm = tuple(replace(x, revenue=r) for x, r in zip(q, (1e9, -1e9, 0.0, 0.0), strict=True))
    falls = (a[0], replace(a[1], revenue=0.0, analysts_revenue=15), a[2])
    r = valued(replace(hg, quarter_estimates=zero_ntm, annual_estimates=falls, peers=()))
    assert_refused(r, "no positive consensus revenue")
    assert r.intermediates.keys() == {"price_facts"}
    # an annual mean of zero with analysts is an estimate: year 2 falls 100%, before the margin
    thin_falls = (a[0], replace(a[1], revenue=0.0, analysts_revenue=3), a[2])
    r = valued(replace(hg, annual_estimates=thin_falls, peers=()))
    assert_refused(r, "consensus revenue falls to zero or below within the path")
    assert r.intermediates.keys() == {"price_facts"} and codes(r)[-1] == "few-analysts"
    r = valued(replace(hg, peers=hg.peers[:2]))
    assert_refused(r, "no target margin: 2 mature peers")
    assert r.intermediates["implied_margin"] is not None and "revenue_path" in r.intermediates
    assert set(r.intermediates) == TARGET_REFUSAL_KEYS
    no_s2c = replace(hg, peers=(), capital_years=hg.capital_years[:3])
    r = valued(no_s2c)
    assert_refused(r, "no target margin: 0 mature peers")  # the margin refuses first
    assert r.intermediates["sales_to_capital"]["value"] is None
    assert r.intermediates["implied_margin"] is None
    # a peer with too few years of margin is not counted
    short = (*hg.peers[:2], replace(hg.peers[2], margin_years=4))
    assert_refused(valued(replace(hg, peers=short)), "no target margin: 2 mature peers")


def test_no_sales_to_capital_refuses(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    peers = tuple(replace(p, sales_to_capital=None) for p in high_growth_inputs.peers)
    short = replace(
        high_growth_inputs, peers=peers, capital_years=high_growth_inputs.capital_years[-4:]
    )
    r = value_company(short, deciles, policy, TODAY)
    assert_refused(r, "no sales-to-capital")
    assert r.intermediates.keys() == {"price_facts"}  # a plain refusal: nothing to reprice


def test_peers_sales_to_capital_when_the_own_measure_is_not_usable(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    short = replace(high_growth_inputs, capital_years=high_growth_inputs.capital_years[-4:])
    r = value_company(short, deciles, policy, TODAY)
    assert r.intermediates["sales_to_capital"] == {
        "used": "peers",
        "own": None,
        "own_usable": False,
        "own_below_bound": False,
        "peers": pytest.approx(2.5),
        "value": pytest.approx(2.5),
    }
    [s2c] = [i for i in r.inputs if i.name == "sales_to_capital"]
    assert s2c.value == pytest.approx(2.5) and s2c.note is not None and "peers" in s2c.note


def test_the_own_sales_to_capital_must_reach_half_the_peers_median(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-06 13.3: an own measure of 0.5, usable on the first two tests, is below half
    the peers' median of 2.5, so the median serves; 1.3 is not; with no peers' median the own 0.5
    stands."""
    below = value_company(with_own_measure(high_growth_inputs, 0.5), deciles, policy, TODAY)
    assert below.intermediates["sales_to_capital"] == {
        "used": "peers",
        "own": pytest.approx(0.5),
        "own_usable": False,
        "own_below_bound": True,
        "peers": pytest.approx(2.5),
        "value": pytest.approx(2.5),
    }
    s2c = input_named(below, "sales_to_capital")
    assert s2c.value == pytest.approx(2.5) and s2c.provenance.source == FMP_SOURCE
    assert s2c.note == (
        "the mature peers' median; the own measure, 0.50, is below half the peers' median, 2.50"
    )
    bound = input_named(below, "own_sales_to_capital_min_share")
    assert (bound.value, bound.unit, bound.tag) == (0.5, "ratio", "RULE")
    # on the industry fallback the note names the industry as today's does
    industry = value_company(
        replace(with_own_measure(high_growth_inputs, 0.5), peer_source=FROM_INDUSTRY),
        deciles,
        policy,
        TODAY,
    )
    assert input_named(industry, "sales_to_capital").note == (
        "the mature peers' median (Specialty Industrial Machinery industry); the own measure, "
        "0.50, is below half the peers' median, 2.50"
    )

    above = value_company(with_own_measure(high_growth_inputs, 1.3), deciles, policy, TODAY)
    s = above.intermediates["sales_to_capital"]
    assert (s["used"], s["own_usable"], s["own_below_bound"]) == ("own", True, False)
    assert s["value"] == pytest.approx(1.3)
    assert input_named(above, "sales_to_capital").note == (
        "the company's own five-year marginal measure"
    )
    assert "own_sales_to_capital_min_share" not in [i.name for i in above.inputs]

    no_median = tuple(replace(p, sales_to_capital=None) for p in high_growth_inputs.peers)
    alone = replace(with_own_measure(high_growth_inputs, 0.5), peers=no_median)
    r = value_company(alone, deciles, policy, TODAY)
    s = r.intermediates["sales_to_capital"]
    assert (s["used"], s["own_usable"], s["own_below_bound"], s["peers"]) == (
        "own",
        True,
        False,
        None,
    )
    assert s["value"] == pytest.approx(0.5)
    assert "own_sales_to_capital_min_share" not in [i.name for i in r.inputs]
    # an own measure not usable on the first two tests is not below the bound: the median serves
    short = replace(high_growth_inputs, capital_years=high_growth_inputs.capital_years[-4:])
    r = value_company(short, deciles, policy, TODAY)
    assert r.intermediates["sales_to_capital"]["own_below_bound"] is False
    assert "own_sales_to_capital_min_share" not in [i.name for i in r.inputs]


def _without_source(im: dict[str, Any]) -> dict[str, Any]:
    target = {k: v for k, v in im["target_margin"].items() if k not in ("source", "industry")}
    return {**im, "target_margin": target}


def test_peers_from_the_industry_change_words_not_figures(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The fixture's peers as the industry's: the row is flagged, and its target margin and the
    peer-cited inputs name the industry; every figure is the one FMP's peers give."""
    unchanged = value_company(high_growth_inputs, deciles, policy, TODAY)
    from_fmp = replace(high_growth_inputs, peer_source=PeerSource("fmp", None, 3))
    fmp = value_company(from_fmp, deciles, policy, TODAY)
    r = value_company(
        replace(high_growth_inputs, peer_source=FROM_INDUSTRY), deciles, policy, TODAY
    )
    assert sentence(r, "peers-from-industry") == (
        "FMP's peer list leaves 1 mature peer with a margin on 5 years or more, fewer than 3, so "
        "the peers are the 3 largest mature companies of the Specialty Industrial Machinery "
        "industry in the universe."
    )
    assert [f.word for f in r.flags if f.code == "peers-from-industry"] == ["Industry peers"]
    assert "peers-from-industry" not in codes(fmp) + codes(unchanged)
    tm = r.intermediates["target_margin"]
    assert (tm["source"], tm["industry"]) == ("industry", INDUSTRY)
    for row in (unchanged, fmp):
        tm = row.intermediates["target_margin"]
        assert (tm["source"], tm["industry"]) == ("fmp", None)
    # the source changes words, not figures
    assert r.value == fmp.value == unchanged.value and r.levels == fmp.levels
    assert _without_source(r.intermediates) == _without_source(fmp.intermediates)
    target, fmp_target = input_named(r, "target_margin"), input_named(fmp, "target_margin")
    assert target.provenance.source == INDUSTRY_SOURCE
    assert target.note == (
        "the median ten-year operating margin of 3 mature peers of the Specialty Industrial "
        "Machinery industry"
    )
    assert fmp_target.provenance.source == FMP_SOURCE
    assert fmp_target.note == "the median ten-year operating margin of 3 mature peers"
    assert target.value == fmp_target.value
    # the own measure is the statements', whatever the peers' source
    assert input_named(r, "sales_to_capital") == input_named(fmp, "sales_to_capital")
    # the bound on the fallback is cited only where it bounded the peers
    bound = input_named(r, "industry_peer_max")
    assert (bound.value, bound.unit, bound.tag) == (policy.industry_peer_max, "peers", "RULE")
    assert bound.note == (
        "the largest mature companies of the Specialty Industrial Machinery industry taken, at most"
    )
    assert "industry_peer_max" not in [i.name for i in fmp.inputs + unchanged.inputs]


def test_the_peers_sales_to_capital_names_the_industry(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    short = replace(high_growth_inputs, capital_years=high_growth_inputs.capital_years[-4:])
    fmp = value_company(short, deciles, policy, TODAY)
    r = value_company(replace(short, peer_source=FROM_INDUSTRY), deciles, policy, TODAY)
    s2c, fmp_s2c = input_named(r, "sales_to_capital"), input_named(fmp, "sales_to_capital")
    assert s2c.provenance.source == INDUSTRY_SOURCE
    assert s2c.note == (
        "the mature peers' median (Specialty Industrial Machinery industry); the own measure is "
        "not usable"
    )
    assert fmp_s2c.provenance.source == FMP_SOURCE
    assert fmp_s2c.note == "the mature peers' median; the own measure is not usable"
    assert s2c.value == fmp_s2c.value == pytest.approx(2.5) and r.value == fmp.value


def test_rows_refused_on_industry_peers_carry_the_flag(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The industry's mature companies can fall short too: the refusal keeps its wording and
    counts them, and the row is flagged, the sentence by the count taken, as is a row refused for
    its sales-to-capital."""
    hg = high_growth_inputs
    zero_from_fmp = PeerSource("industry", INDUSTRY, 0)
    first = "FMP's peer list leaves 0 mature peers with a margin on 5 years or more, fewer than 3, "
    taken = {
        2: "so the peers are the 2 largest mature companies of the Specialty Industrial Machinery "
        "industry in the universe.",
        1: "so the peer is the one mature company of the Specialty Industrial Machinery industry "
        "in the universe.",
        0: "and the Specialty Industrial Machinery industry has no mature company in the universe "
        "either.",
    }
    for k, rest in taken.items():
        r = value_company(
            replace(hg, peers=hg.peers[:k], peer_source=zero_from_fmp), deciles, policy, TODAY
        )
        assert_refused(r, f"no target margin: {k} mature peers")
        assert codes(r)[-1] == "peers-from-industry"
        assert sentence(r, "peers-from-industry") == first + rest
    peers = tuple(replace(p, sales_to_capital=None) for p in hg.peers)
    short = replace(hg, peers=peers, capital_years=hg.capital_years[-4:])
    r = value_company(replace(short, peer_source=FROM_INDUSTRY), deciles, policy, TODAY)
    assert_refused(r, "no sales-to-capital")
    assert codes(r)[-1] == "peers-from-industry"


def test_path_held_flag_and_few_analysts(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    hg = high_growth_inputs
    a = hg.annual_estimates
    r = value_company(hg, deciles, policy, TODAY)
    # three EPS analysts a year, but the revenue path reads the revenue counts: not thin
    assert "few-analysts" not in codes(r) and "path-held" not in codes(r)

    held = value_company(replace(hg, annual_estimates=a[:2]), deciles, policy, TODAY)
    g2 = 16_000 / 13_000 - 1
    assert sentence(held, "path-held") == (
        "The consensus revenue for fiscal 2029 is missing or not positive, so year 3 holds the "
        f"{g2:.1%} of the year before."
    )
    assert held.intermediates["path"]["held"] == [False, True]
    assert held.intermediates["path_steps"] == pytest.approx([g2, g2])
    # g_3 holds g_2's 23.1%, above the class's cap: years 4 and 5 hold the cap, both flagged
    assert held.intermediates["growth_rates"][3:5] == pytest.approx([CAP, CAP])
    assert held.intermediates["revenue_path"]["hold"] == pytest.approx(CAP)
    assert codes(held).index("path-held") < codes(held).index("consensus-above-base-rate")
    assert "The year-3 consensus growth of 23.1% is above 15.0%" in sentence(
        held, "consensus-above-base-rate"
    )

    # no fiscal 2028: neither step stands, year 2 holds year 1's growth and year 3 holds that
    both = value_company(replace(hg, annual_estimates=(a[0], a[2])), deciles, policy, TODAY)
    g1 = 12_400 / 10_000 - 1
    assert sentence(both, "path-held") == (
        "The consensus revenue for fiscal 2028 is missing or not positive, so year 2 holds the "
        f"{g1:.1%} of the year before and year 3 holds the {g1:.1%} of the year before."
    )
    assert both.intermediates["path"]["held"] == [True, True]
    # a base year present but not positive is named, not the year after it
    negative = (replace(a[0], revenue=-5e6), a[1], a[2])
    r = value_company(replace(hg, annual_estimates=negative), deciles, policy, TODAY)
    assert sentence(r, "path-held") == (
        "The consensus revenue for fiscal 2027 is missing or not positive, so year 2 holds the "
        f"{g1:.1%} of the year before."
    )
    # the base year and the next both missing: both are named
    last = value_company(replace(hg, annual_estimates=a[2:]), deciles, policy, TODAY)
    assert sentence(last, "path-held") == (
        "The consensus revenue for fiscal 2027 and 2028 is missing or not positive, so year 2 "
        f"holds the {g1:.1%} of the year before and year 3 holds the {g1:.1%} of the year before."
    )

    thin = (a[0], replace(a[1], analysts_revenue=3), a[2])
    r = value_company(replace(hg, annual_estimates=thin), deciles, policy, TODAY)
    assert "fiscal 2028" in sentence(r, "few-analysts")
    assert r.intermediates["path"]["analysts"] == [3, 12]
    uncounted = (a[0], a[1], replace(a[2], analysts_revenue=None))
    r = value_company(replace(hg, annual_estimates=uncounted), deciles, policy, TODAY)
    assert "fiscal 2029" in sentence(r, "few-analysts")
    # a held step lands on no consensus, so it is never thin
    assert "few-analysts" not in codes(held)


def _years(*points: tuple[int, float | None, int | None]) -> tuple[AnnualEstimate, ...]:
    """Annual consensus rows from (fiscal year, revenue mean, revenue analysts)."""
    return tuple(annual(year, 1.0, 0.01, 10, mean, n) for year, mean, n in points)


def test_consensus_beyond_reads_past_base_plus_two_on_enough_analysts(policy: Policy) -> None:
    """Spec 2026-11-06 6.1: the steps for base + 3 onward, each from the year before's consensus
    revenue, while the year has a mean above zero and at least ``analyst_min`` revenue analysts;
    the first year that fails ends the consensus, so a later year is not read."""
    base = [(2027, 1_000.0, 10), (2028, 970.0, 8), (2029, 940.0, 6)]
    reaching = _years(*base, (2030, 940.0 * 1.01, 6), (2031, 940.0 * 1.01 * 1.02, 6))
    assert consensus_beyond(reaching, 2027, policy) == pytest.approx((0.01, 0.02))
    assert consensus_beyond(_years(*base), 2027, policy) == ()
    # a thin year, a year without a count and a year without a mean each end the consensus
    for stop in ((2030, 950.0, 4), (2030, 950.0, None), (2030, None, 6)):
        found = _years(*base, stop, (2031, 960.0, 6))
        assert consensus_beyond(found, 2027, policy) == (), stop
    later = _years(*base, (2030, 950.0, 6), (2031, 960.0, 4), (2032, 970.0, 6))
    assert consensus_beyond(later, 2027, policy) == pytest.approx((950 / 940 - 1,))
    # the base year is the quarters', not the first on file
    assert consensus_beyond(reaching, 2026, policy) == pytest.approx((940 / 970 - 1, 0.01, 0.02))


def test_consensus_beyond_needs_base_plus_two(policy: Policy) -> None:
    """No step past year 3 without base + 2's consensus revenue to step from: missing, a zero
    with no analysts (no estimate at all), or at or below zero."""
    later = ((2030, 950.0, 6), (2031, 960.0, 6))
    for third in ((), ((2029, 0.0, None),), ((2029, 0.0, 6),), ((2029, -5.0, 6),)):
        found = _years((2027, 1_000.0, 10), (2028, 970.0, 8), *third, *later)
        assert consensus_beyond(found, 2027, policy) == (), third


def test_consensus_beyond_ends_at_a_year_at_zero_or_below(policy: Policy) -> None:
    """A year whose consensus revenue is zero or below, on however many analysts, is not read: it
    ends the consensus at the year before, so no step past year 3 falls 100% or more."""
    base = [(2027, 1_000.0, 10), (2028, 970.0, 8), (2029, 940.0, 6)]
    for mean in (0.0, -94.0):
        found = _years(*base, (2030, mean, 6), (2031, 900.0, 6))
        assert consensus_beyond(found, 2027, policy) == (), mean
        found = _years(*base, (2030, 950.0, 6), (2031, mean, 6), (2032, 960.0, 6))
        assert consensus_beyond(found, 2027, policy) == pytest.approx((950 / 940 - 1,)), mean


def test_the_held_rate_is_capped_at_the_sales_class_ninetieth_percentile(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """$10 bn of trailing revenue is the $7,000-12,000 Mn class, whose 90th-percentile five-year
    sales growth is 15%; the year-3 consensus of 20% is above it, so years 4 and 5 hold 15% and
    the fade starts from it. The consensus steps stand as found."""
    r = value_company(high_growth_inputs, deciles, policy, TODAY)
    im = r.intermediates
    assert sentence(r, "consensus-above-base-rate") == (
        "The year-3 consensus growth of 20.0% is above 15.0%, the Base Rate Book's 90th-percentile "
        "five-year sales growth for the $7,000-12,000 Mn sales class, so years 4 and 5 hold 15.0% "
        "and the fade starts from it."
    )
    assert im["path"]["sales_class"] == CLASS and im["path"]["cap"] == pytest.approx(CAP)
    assert im["revenue_path"]["hold"] == pytest.approx(CAP)
    g2, g3 = 16_000 / 13_000 - 1, 19_200 / 16_000 - 1
    assert im["path_steps"] == pytest.approx([g2, g3])
    assert im["growth_rates"][1:3] == pytest.approx([g2, g3])
    assert im["growth_rates"][3:5] == pytest.approx([CAP, CAP])
    assert im["growth_rates"][5] == pytest.approx(0.03 + 0.12 * 4 / 5)
    # the value is the core's at the cap
    assert im["tax_rate"] == 0.25
    core = revenue_valuation(
        RevenuePath(10_000e6, 12_400e6, (g2, g3), CAP, 5, 5, 0.03),
        MarginPath(-0.09, 0.20, 10),
        0.25,
        RevenueCharge(0.09, 0.03, im["terminal_roic"], im["sales_to_capital"]["value"]),
        Bridge(1_000e6, 3_000e6, 100e6),
    )
    assert core.value_per_share == pytest.approx(r.value)
    cap = input_named(r, "held_growth_cap")
    assert (cap.value, cap.unit, cap.tag) == (CAP, "ratio", "RULE")
    assert cap.note == CAP_NOTE + "binds: the year-3 consensus is above it"
    names = [i.name for i in r.inputs]
    assert names.index("high_growth_years") + 1 == names.index("held_growth_cap")


def test_the_cap_lowers_the_value(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """With every class's cap out of reach, years 4 and 5 hold the 20% of year 3 and the value is
    higher."""
    capped = value_company(high_growth_inputs, deciles, policy, TODAY)
    loose = replace(
        policy, base_rates=tuple(replace(c, sales_p90_5y=10.0) for c in policy.base_rates)
    )
    r = value_company(high_growth_inputs, deciles, loose, TODAY)
    im = r.intermediates
    assert "consensus-above-base-rate" not in codes(r)
    assert im["revenue_path"]["hold"] is None
    g3 = 19_200 / 16_000 - 1
    assert im["growth_rates"][3:5] == pytest.approx([g3, g3])
    assert r.value is not None and capped.value is not None and r.value > capped.value
    # the implied-growth solve tries its own held rate, so the cap does not touch it
    assert im["implied_growth"] == capped.intermediates["implied_growth"]


def test_a_year_3_consensus_at_the_cap_does_not_bind(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A cap equal to g_3 bit for bit does not bind: the rule is strictly above."""
    g3 = 19_200 / 16_000 - 1
    at_cap = replace(
        policy, base_rates=tuple(replace(c, sales_p90_5y=g3) for c in policy.base_rates)
    )
    r = value_company(high_growth_inputs, deciles, at_cap, TODAY)
    im = r.intermediates
    assert "consensus-above-base-rate" not in codes(r)
    assert im["revenue_path"]["hold"] is None
    assert im["path"]["sales_class"] == CLASS and im["path"]["cap"] == g3
    assert im["growth_rates"][3:5] == [g3, g3]
    cap = input_named(r, "held_growth_cap")
    assert cap.value == g3
    assert cap.note == CAP_NOTE + "does not bind: the year-3 consensus is at or below it"


def test_return_above_peers_flag(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    hg = high_growth_inputs
    r = value_company(hg, deciles, policy, TODAY)
    im = r.intermediates
    # 20% × (1 − 25%) × the own 1.38 is 20.8%, above the peers' median of 15%
    roc = im["return_on_new_capital"]
    assert roc == pytest.approx(0.20 * 0.75 * im["sales_to_capital"]["value"])
    assert im["peer_roic_median"] == pytest.approx(0.15) and roc > 0.15
    assert sentence(r, "return-above-peers") == (
        f"The return on new capital at the target margin, {roc:.1%}, is above the mature peers' "
        "median return of 15.0%; the sales-to-capital may be too high (Damodaran's check)."
    )

    higher = tuple(replace(p, roic=0.40) for p in hg.peers)
    r = value_company(replace(hg, peers=higher), deciles, policy, TODAY)
    assert r.intermediates["peer_roic_median"] == pytest.approx(0.40)
    assert "return-above-peers" not in codes(r)
    unknown = tuple(replace(p, roic=None) for p in hg.peers)
    r = value_company(replace(hg, peers=unknown), deciles, policy, TODAY)
    assert r.intermediates["peer_roic_median"] is None and "return-above-peers" not in codes(r)

    # invested capital near zero and growing: a huge own measure, usable, and the flag fires
    small = [0.01 * fy.revenue for fy in hg.series if fy.revenue is not None]
    tiny = capital_years(fiscal_years(small, [0.0] * 8))
    r = value_company(replace(hg, capital_years=tiny), deciles, policy, TODAY)
    s2c = r.intermediates["sales_to_capital"]
    assert s2c["used"] == "own" and s2c["own_usable"] and s2c["value"] > 100
    assert "return-above-peers" in codes(r)
    # near zero and flat: not usable, so the peers' median serves
    flat = capital_years(fiscal_years([10e6] * 8, [0.0] * 8))
    r = value_company(replace(hg, capital_years=flat), deciles, policy, TODAY)
    assert r.intermediates["sales_to_capital"]["used"] == "peers"


def test_tax_loss_flag_and_the_bridge(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    hg, t = high_growth_inputs, high_growth_inputs.trailing
    assert t is not None
    r = value_company(hg, deciles, policy, TODAY)
    assert min(r.intermediates["ebit_by_year"]) < 0
    assert "tax-loss-history-unknown" in codes(r)
    assert sentence(r, "tax-loss-history-unknown") == (
        "The forecast carries its own losses forward from zero and the terminal value is taxed at "
        "the full rate; losses before the forecast are not stored, so the carry is unknown in both "
        "directions."
    )
    profitable = replace(hg, trailing=replace(t, operating_income=500e6))
    p = value_company(profitable, deciles, policy, TODAY)
    assert min(p.intermediates["ebit_by_year"]) > 0
    assert "tax-loss-history-unknown" not in codes(p)
    # a trailing loss implies losses the store does not hold, though every forecast year profits
    slight = replace(hg, trailing=replace(t, operating_income=-50e6))
    s = value_company(slight, deciles, policy, TODAY)
    assert s.intermediates["margin_start"] < 0 < min(s.intermediates["ebit_by_year"])
    assert "tax-loss-history-unknown" in codes(s)

    im = r.intermediates
    assert (im["debt"], im["cash"]) == (1_000e6, 3_000e6)
    assert not [c for c in codes(r) if c in ("line-not-presented:debt", "line-not-presented:cash")]
    no_debt = value_company(replace(hg, debt=None), deciles, policy, TODAY)
    assert no_debt.intermediates["debt"] == 0.0 and "line-not-presented:debt" in codes(no_debt)
    assert no_debt.intermediates["equity"] == pytest.approx(im["firm_value"] + 3_000e6)
    assert no_debt.value is not None and r.value is not None and no_debt.value > r.value
    no_cash = value_company(replace(hg, cash=None), deciles, policy, TODAY)
    assert no_cash.intermediates["cash"] == 0.0 and "line-not-presented:cash" in codes(no_cash)
    assert no_cash.intermediates["equity"] == pytest.approx(im["firm_value"] - 1_000e6)
    # one of the two lines missing: assembly's note names it, the figure stands, the flag fires
    note = "longTermDebt not presented"
    noted = value_company(replace(hg, notes={"debt": note}), deciles, policy, TODAY)
    assert noted.intermediates["debt"] == 1_000e6
    assert note in sentence(noted, "line-not-presented:debt")
    [debt] = [i for i in noted.inputs if i.name == "debt"]
    assert (debt.value, debt.note) == (1_000e6, note)


def test_a_trailing_margin_below_the_bound_takes_the_dollar_ramp(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 2026-11-06 7.2: a trailing loss of $15 bn on $10 bn of revenue moves in dollars to the
    target margin's share of year 10's revenue, and is worth more than the margin path from -150%,
    which the bound moved below it gives."""
    hg = high_growth_inputs
    r = value_company(with_loss(hg, LOSS), deciles, policy, TODAY)
    im = r.intermediates
    assert im["margin_start"] == -1.5 and im["margin_path"]["ramp"] == "dollars"
    revenue, ebit = im["revenue_by_year"], im["ebit_by_year"]
    end = 0.20 * revenue[9]
    assert ebit[0] == pytest.approx(LOSS + (end - LOSS) / 10)
    assert ebit[9] == pytest.approx(end)
    assert im["margin_path"]["by_year"] == pytest.approx(
        [e / rev for e, rev in zip(ebit, revenue, strict=True)]
    )
    route = codes(r)
    assert route.index("tax-loss-history-unknown") + 1 == route.index("margin-ramp-in-dollars")
    assert sentence(r, "margin-ramp-in-dollars") == (
        "The trailing loss is larger than revenue (margin −150.0%), so operating income moves in "
        f"dollars from −$15,000.0 million to the target margin's ${end / 1e6:,.1f} million by year "
        "10, as the Start-up ramp does."
    )
    [word] = [f.word for f in r.flags if f.code == "margin-ramp-in-dollars"]
    assert word == "Ramp in dollars"
    on_margin_path = replace(policy, loss_ramp_margin_bound=-2.0)
    m = value_company(with_loss(hg, LOSS), deciles, on_margin_path, TODAY)
    assert m.intermediates["margin_path"]["ramp"] == "margin"
    assert "margin-ramp-in-dollars" not in codes(m)
    assert m.intermediates["margin_path"]["by_year"][0] == pytest.approx(-1.5 + 1.7 / 10)
    assert im["value_per_share"] > m.intermediates["value_per_share"]
    # a loss of $10.5 bn is on the ramp and valued: the bound is cited, after the convergence year
    valued = value_company(with_loss(hg, VALUED_LOSS), deciles, policy, TODAY)
    assert valued.value is not None and valued.intermediates["margin_path"]["ramp"] == "dollars"
    bound = input_named(valued, "loss_ramp_margin_bound")
    assert (bound.value, bound.unit, bound.tag) == (-1.0, "ratio", "RULE")
    names = [i.name for i in valued.inputs]
    assert names.index("margin_convergence_year") + 1 == names.index("loss_ramp_margin_bound")
    margin_path = value_company(with_loss(hg, VALUED_LOSS), deciles, on_margin_path, TODAY)
    assert valued.value > margin_path.intermediates["value_per_share"]
    # each value by margin is a fresh ramp valuation with every peer at that margin
    by_margin = valued.intermediates["value_by_margin"]
    target = valued.intermediates["target_margin"]
    assert (target["low"], target["value"], target["high"]) == (0.10, 0.20, 0.30)
    assert by_margin["low"] < by_margin["median"] == valued.value < by_margin["high"]
    for key in ("low", "median", "high"):
        at = tuple(replace(p, margin=target["value" if key == "median" else key]) for p in hg.peers)
        fresh = value_company(replace(with_loss(hg, VALUED_LOSS), peers=at), deciles, policy, TODAY)
        assert fresh.intermediates["margin_path"]["ramp"] == "dollars"
        assert by_margin[key] == fresh.intermediates["value_per_share"], key


def test_the_ramp_note_groups_the_thousands_of_a_margin(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A CLDX-sized loss, 2,909.48 times revenue: the note's margin reads with a separator."""
    hg = high_growth_inputs
    r = value_company(with_loss(hg, -2_909.48 * 10_000e6), deciles, policy, TODAY)
    assert sentence(r, "margin-ramp-in-dollars").startswith(
        "The trailing loss is larger than revenue (margin −290,948.0%), so operating income moves "
        "in dollars from −$29,094,800.0 million"
    )


def test_a_trailing_margin_at_the_bound_keeps_the_margin_path(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(with_loss(high_growth_inputs, -10_000e6), deciles, policy, TODAY)
    im = r.intermediates
    assert im["margin_start"] == -1.0 and im["margin_path"]["ramp"] == "margin"
    assert im["margin_path"]["by_year"][0] == pytest.approx(-1.0 + 1.2 / 10)
    assert "margin-ramp-in-dollars" not in codes(r)
    assert "tax-loss-history-unknown" in codes(r)
    plain = value_company(high_growth_inputs, deciles, policy, TODAY)
    assert "loss_ramp_margin_bound" not in [i.name for i in plain.inputs]


def test_reprice_rebuilds_the_ramp(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A row on the dollar ramp moves to a new price from its intermediates alone, its two solves
    on the ramp: at its own value they return the held rate and the target margin."""
    ramp = with_loss(high_growth_inputs, VALUED_LOSS)
    r = value_company(ramp, deciles, policy, TODAY)
    assert r.value is not None and r.price is not None and r.price_date is not None
    stored = result_from_json(result_to_json(r))
    assert reprice(stored, r.price, r.price_date, policy) == r
    r2 = reprice(stored, r.price * 0.5, REPRICED, policy)
    assert r2.value == r.value
    assert r2.intermediates["ebit_by_year"] == r.intermediates["ebit_by_year"]
    assert r2.intermediates["implied_growth"] != r.intermediates["implied_growth"]
    assert r2.intermediates["implied_margin"] < r.intermediates["implied_margin"]
    fresh = value_company(replace(ramp, price=r.price * 0.5), deciles, policy, TODAY)
    for key in PRICE_KEYS:
        assert r2.intermediates[key] == fresh.intermediates[key], key
    at_value = reprice(stored, r.value, REPRICED, policy).intermediates
    assert at_value["implied_growth"] == pytest.approx(CAP, abs=1e-4)
    assert at_value["implied_margin"] == pytest.approx(0.20, abs=1e-4)
    # refused for its target margin on the ramp: the margin the price needs is the ramp's
    no_peers = replace(with_loss(high_growth_inputs, LOSS), peers=())
    refused = value_company(no_peers, deciles, policy, TODAY)
    assert refused.refusal == "no target margin: 0 mature peers" and refused.price is not None
    im = refused.intermediates
    on_margin_path = replace(policy, loss_ramp_margin_bound=-2.0)
    assert im["implied_margin"] is not None
    on_margin = implied_margin_at_price(im, refused.price, on_margin_path)["implied_margin"]
    assert im["implied_margin"] != on_margin
    stored = result_from_json(result_to_json(refused))
    moved = reprice(stored, refused.price * 0.5, REPRICED, policy)
    assert moved.intermediates["implied_margin"] < im["implied_margin"]
    fresh = value_company(replace(no_peers, price=refused.price * 0.5), deciles, policy, TODAY)
    assert moved.intermediates == fresh.intermediates


def test_young_growth_equals_high_growth_on_the_ramp(
    young_growth_inputs: CompanyInputs,
    high_growth_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
) -> None:
    young = with_loss(young_growth_inputs, VALUED_LOSS)
    same = replace(
        young, series=high_growth_inputs.series, capital_years=high_growth_inputs.capital_years
    )
    high = value_company(same, deciles, policy, TODAY)
    r = value_company(young, deciles, policy, TODAY)
    assert (high.phase.phase, r.phase.phase) == ("High Growth", "Young Growth")
    assert r.intermediates["margin_path"]["ramp"] == "dollars"
    assert r.value is not None and r.value == high.value and r.levels == high.levels
    figures = dict(r.intermediates)
    figures.pop("failure_probability")
    assert figures == high.intermediates
    assert sentence(r, "margin-ramp-in-dollars") == sentence(high, "margin-ramp-in-dollars")
    for row in (r, high):
        assert "loss_ramp_margin_bound" in [i.name for i in row.inputs]
    route = codes(r)
    assert route.index("margin-ramp-in-dollars") < route.index("failure-not-charged")


def test_cross_check_present_with_a_positive_anchor(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    hg = high_growth_inputs
    r = value_company(hg, deciles, policy, TODAY)
    assert r.intermediates["growth_route"] == {"refusal": "no positive forward anchor"}
    assert "sbc-basis-unknown" not in codes(r)  # no cross-check value, no warning on its anchor
    assert r.intermediates["eps"]["forward"] is None

    positive = replace(
        hg,
        quarter_estimates=tuple(replace(q, eps=0.60) for q in hg.quarter_estimates),
        annual_estimates=(
            annual(2027, 250e6, 2.50, 3, 13_000e6, 20),
            annual(2028, 320e6, 3.20, 3, 16_000e6, 15),
            annual(2029, 400e6, 4.00, 3, 19_200e6, 12),
        ),
    )
    p = value_company(positive, deciles, policy, TODAY)
    gr = p.intermediates["growth_route"]
    assert gr["value_per_share"] is not None and gr["refusal"] is None
    assert "implied_growth" in gr and gr["path_steps"] == pytest.approx([0.28, 0.25])
    assert p.value == r.value  # the cross-check never moves the value
    assert p.intermediates["eps"]["forward"] == pytest.approx(2.40)
    assert p.intermediates["multiples"]["pe_forward"] == pytest.approx(150 / 2.40)
    # no street EPS: the cross-check's anchor is untested for stock compensation, and says so
    assert codes(p)[len(p.phase.checks) :][0] == "sbc-basis-unknown"


def test_value_spread_flag_over_the_margins(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(high_growth_inputs, deciles, policy, TODAY)
    by_margin = r.intermediates["value_by_margin"]
    assert by_margin["low"] < by_margin["median"] < by_margin["high"]
    assert "value-spread" in codes(r) and "target margins" in sentence(r, "value-spread")
    close = (
        replace(high_growth_inputs.peers[0], margin=0.195),
        high_growth_inputs.peers[1],
        replace(high_growth_inputs.peers[2], margin=0.205),
    )
    narrow = value_company(replace(high_growth_inputs, peers=close), deciles, policy, TODAY)
    assert narrow.value == r.value and "value-spread" not in codes(narrow)


def test_value_spread_is_unbounded_when_the_lowest_margin_values_at_or_below_zero(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The mature routes' rule needs a positive lowest value; here a peer at a loss leaves the
    value at its margin below zero while the median's is positive, and the flag says so."""
    hg = high_growth_inputs
    losing = (replace(hg.peers[0], margin=-0.30), *hg.peers[1:])
    r = value_company(replace(hg, peers=losing), deciles, policy, TODAY)
    by_margin = r.intermediates["value_by_margin"]
    assert by_margin["low"] <= 0 < by_margin["median"] == r.value
    assert sentence(r, "value-spread") == (
        "The value is at or below zero at the lowest mature-peer margin of -30.0% and "
        f"{by_margin['median']:,.2f} a share at the median, so the spread across the peers' "
        "margins is unbounded."
    )
    # every margin at a loss: the median's value is not positive either, and nothing is flagged
    all_losing = tuple(replace(p, margin=-0.05) for p in hg.peers)
    refused = value_company(replace(hg, peers=all_losing), deciles, policy, TODAY)
    assert refused.intermediates["value_by_margin"]["median"] <= 0
    assert "value-spread" not in codes(refused)


def test_value_not_positive_is_refused_with_the_figures(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    losing = tuple(replace(p, margin=-0.05) for p in high_growth_inputs.peers)
    r = value_company(replace(high_growth_inputs, peers=losing), deciles, policy, TODAY)
    assert_refused(r, "value not positive under the reinvestment charge")
    assert r.intermediates["value_per_share"] <= 0
    assert r.intermediates["implied_margin"] is not None
    assert "implied_growth" not in r.intermediates


def test_determinism_and_json_round_trip(
    high_growth_inputs: CompanyInputs,
    young_growth_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
) -> None:
    for inputs in (
        high_growth_inputs,
        young_growth_inputs,
        replace(high_growth_inputs, peers=()),
        replace(high_growth_inputs, peer_source=FROM_INDUSTRY),
        replace(high_growth_inputs, peers=(), peer_source=PeerSource("industry", INDUSTRY, 0)),
    ):
        first = value_company(inputs, deciles, policy, TODAY)
        assert value_company(inputs, deciles, policy, TODAY) == first
        assert result_from_json(result_to_json(first)) == first


def test_reprice_moves_every_price_side_figure(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(high_growth_inputs, deciles, policy, TODAY)
    assert r.price is not None and r.price_date is not None
    assert r.intermediates["revenue_path"]["hold"] == pytest.approx(CAP)  # a bound row
    stored = result_from_json(result_to_json(r))  # from the intermediates alone
    assert reprice(stored, r.price, r.price_date, policy) == r
    r2 = reprice(stored, r.price * 0.5, REPRICED, policy)
    assert r2.value == r.value and r2.levels == r.levels
    assert r2.intermediates["growth_rates"] == r.intermediates["growth_rates"]
    assert r2.intermediates["revenue_path"] == r.intermediates["revenue_path"]
    assert r2.intermediates["implied_growth"] != r.intermediates["implied_growth"]
    assert r2.intermediates["implied_margin"] != r.intermediates["implied_margin"]
    assert r2.intermediates["revenue_by_year"] == r.intermediates["revenue_by_year"]
    fresh = value_company(replace(high_growth_inputs, price=r.price * 0.5), deciles, policy, TODAY)
    for key in PRICE_KEYS:
        assert r2.intermediates[key] == fresh.intermediates[key], key
    assert (r2.price_to_value, r2.designation) == (fresh.price_to_value, fresh.designation)


def test_reprice_moves_the_implied_margin_on_a_refused_row(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(replace(high_growth_inputs, peers=()), deciles, policy, TODAY)
    assert r.price is not None
    assert r.intermediates["revenue_path"]["hold"] == pytest.approx(CAP)  # the cap rebuilds too
    r2 = reprice(result_from_json(result_to_json(r)), r.price * 0.5, REPRICED, policy)
    assert r2.refusal == r.refusal and r2.value is None and r2.route is None
    assert r2.intermediates["implied_margin"] < r.intermediates["implied_margin"]
    fresh = value_company(
        replace(high_growth_inputs, peers=(), price=r.price * 0.5), deciles, policy, TODAY
    )
    assert r2.intermediates == fresh.intermediates
    assert (r2.price, r2.price_date) == (r.price * 0.5, REPRICED)
    plain = value_company(replace(high_growth_inputs, trailing=None), deciles, policy, TODAY)
    assert reprice(plain, 10.0, REPRICED, policy).intermediates == plain.intermediates


def test_implied_margin_needs_a_sales_to_capital(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    hg = high_growth_inputs
    r = value_company(replace(hg, peers=()), deciles, policy, TODAY)
    im = r.intermediates
    assert implied_margin_at_price(im, 75.0, policy) == {
        "implied_margin": reprice(r, 75.0, REPRICED, policy).intermediates["implied_margin"]
    }
    no_s2c = {**im, "sales_to_capital": {**im["sales_to_capital"], "value": None}}
    assert implied_margin_at_price(no_s2c, 75.0, policy) == {"implied_margin": None}


def test_peers_the_route_reads_are_the_inputs_peers(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The largest peer by market cap is recorded and sets nothing; a peer with no market cap
    still counts for the median."""
    peers = (*high_growth_inputs.peers, PeerFigures("PEER4", None, 0.40, 10, 2.0, 0.10))
    r = value_company(replace(high_growth_inputs, peers=peers), deciles, policy, TODAY)
    tm = r.intermediates["target_margin"]
    assert tm["count"] == 4 and tm["value"] == pytest.approx(0.25)
    assert (tm["low"], tm["high"]) == (0.10, 0.40)
    assert (tm["largest_symbol"], tm["largest_margin"]) == ("PEER2", 0.20)
    assert tm["peers"][3] == {"symbol": "PEER4", "margin": 0.40, "market_cap": None}


def test_own_sales_to_capital_is_an_estimate_under_the_intangibles_method(
    high_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Like the returns read from invested capital, the own measure is an estimate when invested
    capital took the issuer's as-reported intangibles total."""
    r = value_company(high_growth_inputs, deciles, policy, TODAY)
    [plain] = [i for i in r.inputs if i.name == "sales_to_capital"]
    assert (plain.kind, plain.provenance.source) == ("observed", "FMP income-statement")
    method = "bs10-intangibles-total-v1"
    estimated = replace(high_growth_inputs, estimate_methods={"intangibles": method})
    r = value_company(estimated, deciles, policy, TODAY)
    [s2c] = [i for i in r.inputs if i.name == "sales_to_capital"]
    assert (s2c.kind, s2c.estimate_method) == ("estimate", method)
    assert s2c.note == "the company's own five-year marginal measure"
