"""The Start-up route through ``value_company``: spec 13.2's row, always a refusal that keeps its
figures (the year-10 revenue the price needs, the cash floor, the burn cover); each reason the
requirement can carry, the flags in order, the inputs, the JSON round trip and the price refresh.

The fixture (``support.engine_companies.start_up_inputs``) is spec 13.2 in USD as the spec states
it: a market cap of 2,000 on 100 diluted shares at $20, debt 0 and cash 300."""

from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from fairband.engine.anchor import TrailingFigures
from fairband.engine.classifier import Deciles
from fairband.engine.revenue_growth import PeerSource
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.route_start_up import start_up_at_price
from fairband.engine.types import TaggedInput, ValuationResult, result_from_json, result_to_json
from fairband.policy import Policy

TODAY = date(2026, 10, 31)
REPRICED = date(2026, 11, 2)
REASON = "Start-up: no value by design"
R10 = 1_725.7277865837668  # spec 1,725.73
START_UP_KEYS = {
    "requirement",
    "cash_floor",
    "burn_cover_years",
    "burn",
    "price_facts",
    "debt",
    "cash",
    "shares",
    "market_cap",
}
REQUIREMENT_KEYS = {
    "reason",
    "revenue_y10",
    "ev_price",
    "revenue_0",
    "operating_income_0",
    "target_margin",
    "sales_to_capital",
    "tax_rate",
    "terminal_roic",
    "path",
    "terminal_value",
}
PATH_KEYS = {"revenue", "ebit", "tax", "nopat", "reinvestment", "fcff"}


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


def trailing(inputs: CompanyInputs) -> TrailingFigures:
    assert inputs.trailing is not None
    return inputs.trailing


def assert_start_up(r: ValuationResult) -> None:
    """A Start-up row: its route, the one reason, no value, levels or designation, and every
    figure kept through a JSON round trip."""
    assert (r.route, r.refusal, r.phase.phase) == ("start-up", REASON, "Start-up")
    assert (r.value, r.levels, r.price_to_value, r.designation) == (None,) * 4
    assert set(r.intermediates) == START_UP_KEYS
    assert set(r.intermediates["requirement"]) == REQUIREMENT_KEYS
    assert result_from_json(result_to_json(r)) == r


def requirement(r: ValuationResult) -> dict[str, Any]:
    found: dict[str, Any] = r.intermediates["requirement"]
    return found


def test_the_route_is_always_the_refusal_with_figures(
    start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(start_up_inputs, deciles, policy, TODAY)
    assert_start_up(r)
    assert r.price == 20.0 and r.valid_until == start_up_inputs.next_earnings
    im = r.intermediates
    req = im["requirement"]
    assert req["reason"] is None
    assert req["revenue_y10"] == pytest.approx(R10, abs=1e-6)  # spec 1,725.73
    assert (req["ev_price"], req["revenue_0"], req["operating_income_0"]) == (1_700.0, 0.0, -50.0)
    assert (req["tax_rate"], req["terminal_roic"]) == (0.25, 0.09)  # no moat: r
    assert req["target_margin"] == {
        "value": 0.25,
        "count": 3,
        "low": 0.20,
        "high": 0.30,
        "largest_symbol": "PEER2",
        "largest_margin": 0.25,
        "peers": [
            {"symbol": "PEER1", "margin": 0.20, "market_cap": 10e9},
            {"symbol": "PEER2", "margin": 0.25, "market_cap": 50e9},
            {"symbol": "PEER3", "margin": 0.30, "market_cap": 20e9},
        ],
        "source": "fmp",
        "industry": None,
    }
    assert req["sales_to_capital"] == {
        "used": "peers",
        "own": None,
        "own_usable": False,
        "peers": 1.5,
        "value": 1.5,
    }
    path = req["path"]
    assert set(path) == PATH_KEYS and all(len(path[k]) == 10 for k in PATH_KEYS)
    assert path["revenue"] == pytest.approx([R10 * t / 10 for t in range(1, 11)])
    assert path["ebit"][-1] == pytest.approx(0.25 * R10)
    assert path["ebit"][0] == pytest.approx(-50 + (0.25 * R10 + 50) / 10)
    assert path["reinvestment"][:9] == pytest.approx([R10 / 10 / 1.5] * 9)
    terminal_nopat = 0.25 * R10 * 0.75
    assert path["reinvestment"][9] == pytest.approx(terminal_nopat * 0.03 / 0.09)
    multiple = 1.03 * (1 - 0.03 / 0.09) / 0.06  # spec 11.4444
    assert req["terminal_value"] == pytest.approx(terminal_nopat * multiple)
    # the cash floor and the burn cover: net cash 300 on 100 shares; 300 against a burn of 75
    assert im["cash_floor"] == pytest.approx(3.00)
    assert (im["burn"], im["burn_cover_years"]) == (75.0, 4.0)
    assert (im["debt"], im["cash"], im["shares"], im["market_cap"]) == (0.0, 300.0, 100.0, 2_000.0)
    # a loss-maker's path has a loss year; nothing else is flagged
    assert route_codes(r) == ["tax-loss-history-unknown"]
    # a Wide moat changes nothing: a Start-up reads no return on capital, so the terminal is r
    wide = value_company(replace(start_up_inputs, moat_score=9.0), deciles, policy, TODAY)
    assert requirement(wide) == req
    assert input_named(wide, "moat_class").note == "Wide"


def test_each_requirement_reason(
    start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 9.2's reasons, in their order; each row is still the Start-up refusal with its cash
    floor and burn cover."""
    su = start_up_inputs
    peers = su.peers

    def reason(inputs: CompanyInputs) -> str | None:
        r = value_company(inputs, deciles, policy, TODAY)
        assert_start_up(r)
        assert r.intermediates["cash_floor"] == pytest.approx(3.00)
        assert r.intermediates["burn_cover_years"] == 4.0
        req = requirement(r)
        if req["reason"] is not None:
            assert (req["revenue_y10"], req["path"], req["terminal_value"]) == (None, None, None)
        return req["reason"]

    assert reason(replace(su, peers=())) == "no target margin: 0 mature peers"
    assert reason(replace(su, peers=peers[:2])) == "no target margin: 2 mature peers"
    # a peer's margin on four years does not count
    short = (*peers[:2], replace(peers[2], margin_years=4))
    assert reason(replace(su, peers=short)) == "no target margin: 2 mature peers"
    no_s2c = (*peers[:2], replace(peers[2], sales_to_capital=-1.0))
    assert reason(replace(su, peers=no_s2c)) == "no sales-to-capital"
    assert reason(replace(su, tax_rate_latest=None)) == "no statutory tax rate"
    assert reason(replace(su, market_cap=None)) == "no market cap"
    losing = tuple(replace(p, margin=m) for p, m in zip(peers, (-0.10, -0.05, 0.0), strict=True))
    assert reason(replace(su, peers=losing)) == "no revenue reaches the price"
    # the order: the target margin, the sales-to-capital, the tax rate, the market cap
    everything = replace(su, peers=(), tax_rate_latest=None, market_cap=None)
    assert reason(everything) == "no target margin: 0 mature peers"
    assert reason(replace(su, peers=no_s2c, tax_rate_latest=None)) == "no sales-to-capital"
    assert reason(replace(su, tax_rate_latest=None, market_cap=None)) == "no statutory tax rate"
    # what the requirement could read stays recorded beside its reason
    r = value_company(replace(su, peers=losing), deciles, policy, TODAY)
    req = requirement(r)
    assert (req["ev_price"], req["tax_rate"]) == (1_700.0, 0.25)
    assert req["target_margin"]["value"] == pytest.approx(-0.05)
    r = value_company(replace(su, peers=()), deciles, policy, TODAY)
    req = requirement(r)
    assert (req["target_margin"], req["sales_to_capital"], req["ev_price"]) == (None, None, None)
    assert req["tax_rate"] == 0.25


def test_no_market_cap_gives_the_reason_and_keeps_the_floor(
    start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(replace(start_up_inputs, market_cap=None), deciles, policy, TODAY)
    assert_start_up(r)
    req = requirement(r)
    assert (req["reason"], req["ev_price"], req["revenue_y10"]) == ("no market cap", None, None)
    assert req["target_margin"] is not None and req["sales_to_capital"] is not None
    im = r.intermediates
    assert (im["cash_floor"], im["market_cap"], im["burn_cover_years"]) == (3.0, None, 4.0)
    assert "below-net-cash" not in codes(r)
    # without a market cap the price refresh has none to move either
    p = reprice(r, 2.0, REPRICED, policy)
    assert p.intermediates == r.intermediates and p.flags == r.flags


def test_net_cash_above_the_market_cap(
    start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 13.2: a market cap of 250 against net cash of 300 gives EV_price −50, so the price needs
    no revenue at all."""
    r = value_company(replace(start_up_inputs, market_cap=250.0), deciles, policy, TODAY)
    assert_start_up(r)
    req = requirement(r)
    assert (req["reason"], req["ev_price"], req["revenue_y10"]) == (None, -50.0, 0.0)
    # the ramp at no revenue: the loss shrinks by 5 a year to nothing in year 10
    assert req["path"]["revenue"] == [0.0] * 10
    assert req["path"]["ebit"] == pytest.approx([-50 + 5 * t for t in range(1, 11)])
    assert req["terminal_value"] == 0.0
    assert route_codes(r) == ["tax-loss-history-unknown", "below-net-cash"]
    assert sentence(r, "below-net-cash") == (
        "The price is covered by net cash: market cap 250 against net cash 300."
    )
    assert {f.code: f.word for f in r.flags}["below-net-cash"] == "Below net cash"
    # at exactly the net cash, EV_price is zero: still covered
    at = value_company(replace(start_up_inputs, market_cap=300.0), deciles, policy, TODAY)
    assert requirement(at)["revenue_y10"] == 0.0 and "below-net-cash" in codes(at)
    # debt counts against the cash: net cash 100 is below a market cap of 250
    indebted = value_company(
        replace(start_up_inputs, market_cap=250.0, debt=200.0), deciles, policy, TODAY
    )
    assert requirement(indebted)["ev_price"] == 150.0
    assert indebted.intermediates["cash_floor"] == pytest.approx(1.00)
    assert "below-net-cash" not in codes(indebted)


def test_the_burn_cover(start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    """Spec 13.2: operating cash flow −60 and capital spending −15 burn 75 a year; cash 300 covers
    4.0 years and cash 120 covers 1.6, below the 2-year threshold."""
    su, t = start_up_inputs, trailing(start_up_inputs)

    def valued(inputs: CompanyInputs) -> ValuationResult:
        r = value_company(inputs, deciles, policy, TODAY)
        assert_start_up(r)
        return r

    r = valued(su)
    assert (r.intermediates["burn"], r.intermediates["burn_cover_years"]) == (75.0, 4.0)
    assert "burn-cover-short" not in codes(r)
    short = valued(replace(su, cash=120.0))
    assert short.intermediates["burn_cover_years"] == pytest.approx(1.6)
    assert sentence(short, "burn-cover-short") == (
        "Cash covers 1.6 years of the trailing burn of 75 a year."
    )
    assert {f.code: f.word for f in short.flags}["burn-cover-short"] == "Cash cover short"
    # exactly two years is not short
    two = valued(replace(su, cash=150.0))
    assert two.intermediates["burn_cover_years"] == 2.0 and "burn-cover-short" not in codes(two)
    # operating cash flow of 15 pays for the spending: not burning; 10 still burns 5 a year
    level = valued(replace(su, trailing=replace(t, cfo=15.0)))
    assert (level.intermediates["burn"], level.intermediates["burn_cover_years"]) == (
        None,
        "not burning",
    )
    assert "burn-cover-short" not in codes(level)
    small = valued(replace(su, trailing=replace(t, cfo=10.0)))
    assert (small.intermediates["burn"], small.intermediates["burn_cover_years"]) == (5.0, 60.0)
    # no burn cover without both trailing figures
    for missing in (replace(t, cfo=None), replace(t, capex=None)):
        r = valued(replace(su, trailing=missing))
        assert (r.intermediates["burn"], r.intermediates["burn_cover_years"]) == (None, None)
        assert "burn-cover-short" not in codes(r)


def test_a_start_up_without_trailing_figures_still_runs(
    start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The Start-up branch runs before the "no trailing figures" guard: with none, the ramp starts
    from no revenue and the last fiscal year's operating income, and there is no burn cover."""
    su = start_up_inputs
    r = value_company(replace(su, trailing=None), deciles, policy, TODAY)
    assert_start_up(r)
    req = requirement(r)
    assert (req["revenue_0"], req["operating_income_0"]) == (0.0, -50.0)  # fiscal 2025's loss
    assert req["revenue_y10"] == pytest.approx(R10, abs=1e-6)
    assert (r.intermediates["burn"], r.intermediates["burn_cover_years"]) == (None, None)
    names = [i.name for i in r.inputs]
    for absent in ("revenue_ttm", "operating_income_ttm", "cfo_ttm", "capex_ttm"):
        assert absent not in names, absent
    fy = input_named(r, "operating_income_fy")
    assert (fy.value, fy.note) == (-50.0, "fiscal 2025: the trailing operating income is missing")
    # a trailing figure without its operating income also starts from the fiscal year's
    t = replace(trailing(su), operating_income=None)
    r = value_company(replace(su, trailing=t), deciles, policy, TODAY)
    assert requirement(r)["operating_income_0"] == -50.0
    assert input_named(r, "operating_income_ttm").value is None
    # and without that either, from zero
    series = (*su.series[:-1], replace(su.series[-1], operating_income=None))
    r = value_company(replace(su, trailing=None, series=series), deciles, policy, TODAY)
    assert requirement(r)["operating_income_0"] == 0.0
    assert input_named(r, "operating_income_fy").value is None
    # a positive trailing revenue starts the ramp there
    r = value_company(
        replace(su, trailing=replace(trailing(su), revenue=40.0)), deciles, policy, TODAY
    )
    assert requirement(r)["revenue_0"] == 40.0
    assert requirement(r)["path"]["revenue"][0] == pytest.approx(
        40 + (requirement(r)["revenue_y10"] - 40) / 10
    )
    # the guards before the route still refuse
    for inputs, guard in (
        (replace(su, price=None, trailing=None), "no price"),
        (replace(su, shares_diluted=0.0, trailing=None), "no diluted share count"),
    ):
        refused = value_company(inputs, deciles, policy, TODAY)
        assert (refused.refusal, refused.route, refused.phase.phase) == (guard, None, "Start-up")


def test_the_flag_order_and_inputs(
    start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Every flag the route raises, in spec 9.5's order: an unknown debt, a cash line not
    presented, the industry's peers, the tax carry, a market cap below the net cash and a short
    burn cover. Never the ROIC, return-above-peers, few-analysts or trailing flags."""
    flagged = replace(
        start_up_inputs,
        debt=None,
        cash=120.0,
        notes={"cash": "shortTermInvestments not presented"},
        market_cap=100.0,
        peer_source=PeerSource("industry", "Biotechnology", 1),
    )
    r = value_company(flagged, deciles, policy, TODAY)
    assert_start_up(r)
    assert route_codes(r) == [
        "line-not-presented:debt",
        "line-not-presented:cash",
        "peers-from-industry",
        "tax-loss-history-unknown",
        "below-net-cash",
        "burn-cover-short",
    ]
    assert sentence(r, "below-net-cash") == (
        "The price is covered by net cash: market cap 100 against net cash 120."
    )
    for never in ("roic-unavailable", "return-above-peers", "few-analysts", "negative-fcf"):
        assert never not in codes(r), never

    # the inputs of the plain row
    r = value_company(start_up_inputs, deciles, policy, TODAY)
    names = [i.name for i in r.inputs]
    assert len(names) == len(set(names))
    assert [i.name for i in r.inputs if i.tag == "DATA"] == [
        "statements",
        "price",
        "shares_diluted",
        "next_earnings",
        "closes",
        "market_cap",
        "revenue_ttm",
        "operating_income_ttm",
        "cfo_ttm",
        "capex_ttm",
        "tax_rate_latest",
        "moat_score",
        "target_margin",
        "sales_to_capital",
        "debt",
        "cash",
    ]
    assert [i.name for i in r.inputs if i.tag == "RULE"] == [
        "required_return",
        "terminal_growth",
        "moat_class",
        "terminal_roic",
        "peer_min",
        "peer_margin_min_years",
        "burn_cover_flag_years",
    ]
    target = input_named(r, "target_margin")
    assert (target.value, target.provenance.source) == (
        0.25,
        "FMP stock-peers and the peers' statements",
    )
    assert target.note == "the median ten-year operating margin of 3 mature peers"
    s2c = input_named(r, "sales_to_capital")
    assert (s2c.value, s2c.note) == (
        1.5,
        "the mature peers' median; a Start-up reads no own measure",
    )
    assert (input_named(r, "cfo_ttm").value, input_named(r, "capex_ttm").value) == (-60.0, -15.0)
    assert input_named(r, "market_cap").provenance.source == "FMP quote"
    rules = {i.name: i for i in r.inputs if i.tag == "RULE"}
    assert (rules["terminal_roic"].value, rules["terminal_roic"].note) == (
        0.09,
        "None moat; r: a Start-up reads no return on capital",
    )
    assert (rules["burn_cover_flag_years"].value, rules["peer_margin_min_years"].value) == (2, 5)
    assert all(i.provenance.source == f"policy {policy.version}" for i in rules.values())
    # the industry's peers: cited to the universe's industry, with the bound on their number
    r = value_company(flagged, deciles, policy, TODAY)
    target = input_named(r, "target_margin")
    assert (
        target.provenance.source
        == "the universe's Biotechnology industry and the peers' statements"
    )
    assert target.note == (
        "the median ten-year operating margin of 3 mature peers of the Biotechnology industry"
    )
    assert input_named(r, "sales_to_capital").note == (
        "the mature peers' median (Biotechnology industry); a Start-up reads no own measure"
    )
    assert input_named(r, "industry_peer_max").value == 10
    assert requirement(r)["target_margin"]["source"] == "industry"
    # without a target margin or sales-to-capital, neither is cited
    r = value_company(replace(start_up_inputs, peers=()), deciles, policy, TODAY)
    names = [i.name for i in r.inputs]
    assert "target_margin" not in names and "sales_to_capital" not in names


def test_the_price_refresh_rebuilds_the_requirement(
    start_up_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A price refresh moves the market cap with the price, rebuilds the requirement from its
    rebuild keys at it and re-reads the net-cash flag; the cash floor and the burn cover stay."""
    r = value_company(start_up_inputs, deciles, policy, TODAY)
    stored = result_from_json(result_to_json(r))
    assert r.price_date is not None and reprice(stored, 20.0, r.price_date, policy) == r
    doubled = reprice(stored, 40.0, REPRICED, policy)
    assert_start_up(doubled)
    req = requirement(doubled)
    assert req["ev_price"] == 3_700.0 and doubled.intermediates["market_cap"] == 4_000.0
    assert req["revenue_y10"] == pytest.approx(3_616.66, abs=0.01)  # method 6b.7
    # what a valuation at that market cap gives, and the same from the rebuild keys alone
    fresh = value_company(
        replace(start_up_inputs, market_cap=4_000.0, price=40.0), deciles, policy, TODAY
    )
    assert req == requirement(fresh)
    assert start_up_at_price(stored.intermediates, 4_000.0, policy) == {
        "market_cap": 4_000.0,
        "requirement": req,
    }
    for key in ("cash_floor", "burn_cover_years", "burn", "price_facts", "debt", "cash", "shares"):
        assert doubled.intermediates[key] == r.intermediates[key], key
    assert (doubled.price, doubled.price_date, doubled.refusal) == (40.0, REPRICED, REASON)
    assert input_named(doubled, "price").value == 40.0
    assert input_named(doubled, "market_cap").value == 2_000.0  # the valuation's input stays
    # down to $2.50: a market cap of 250 is below the net cash, and back to $20 it is not
    low = reprice(doubled, 2.5, REPRICED, policy)
    assert requirement(low)["revenue_y10"] == 0.0 and requirement(low)["ev_price"] == -50.0
    assert route_codes(low) == ["tax-loss-history-unknown", "below-net-cash"]
    assert sentence(low, "below-net-cash") == (
        "The price is covered by net cash: market cap 250 against net cash 300."
    )
    back = reprice(low, 20.0, REPRICED, policy)
    assert back.intermediates == r.intermediates and back.flags == r.flags
    # the flag keeps its place before a short burn cover
    short = value_company(replace(start_up_inputs, cash=120.0), deciles, policy, TODAY)
    low = reprice(short, 0.5, REPRICED, policy)
    assert route_codes(low) == ["tax-loss-history-unknown", "below-net-cash", "burn-cover-short"]
    # a requirement refused for its inputs takes only the new price
    no_peers = value_company(replace(start_up_inputs, peers=()), deciles, policy, TODAY)
    p = reprice(no_peers, 40.0, REPRICED, policy)
    assert requirement(p) == requirement(no_peers)
    assert p.intermediates["market_cap"] == 4_000.0
