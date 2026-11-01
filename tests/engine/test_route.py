import json
import math
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from fairband.engine import METHOD_VERSION, route_mature_growth
from fairband.engine.classifier import Deciles
from fairband.engine.levels import levels_for, stance3, stance5
from fairband.engine.mature_growth import Charge, GrowthPath, growth_rates, value_at_belief
from fairband.engine.price_facts import price_facts
from fairband.engine.roic import (
    CapitalYear,
    aggregate_roic,
    runway_return,
    terminal_return,
    terminal_roic,
)
from fairband.engine.route import CompanyInputs, refusal_result, reprice, value_company
from fairband.engine.route_mature_growth import growth_at_price
from fairband.engine.route_steps import Context, Valued
from fairband.engine.types import (
    Flag,
    Provenance,
    ValuationResult,
    result_from_json,
    result_to_json,
)
from fairband.policy import Policy

TODAY = date(2026, 10, 31)
# At a return equal to r, growth up to r adds no value and the value is year-1 earnings over r;
# years 1 to 3 pay for the 12% and 10% steps and year 4's 9.26% (the first fade step from 10% to
# the 6.3% belief), above r, and the payout floor raises their cash from below zero to zero,
# which adds it back.
VALUE_AT_R = (
    5.90 / 0.09
    + 5.90 * (0.12 / 0.09 - 1) / 1.09
    + 5.90 * 1.12 * (0.10 / 0.09 - 1) / 1.09**2
    + 5.90 * 1.12 * 1.10 * (0.0926 / 0.09 - 1) / 1.09**3
)

MATURE_GROWTH_KEYS = {
    "anchor",
    "sbc_basis",
    "ntm_net_income",
    "path",
    "path_steps",
    "belief",
    "moat",
    "runway",
    "roic",
    "runway_return",
    "terminal_roic",
    "charge_off",
    "fade_years",
    "growth_rates",
    "shares",
    "value_total",
    "value_per_share",
    "value_by_runway",
    "value_by_roic",
    "nri_gap",
    "eps",
    "epv",
    "dividend_yield",
    "net_buyback_yield",
    "income_basis",
    "price_facts",
    "implied_growth",
    "implied_growth_by_runway",
    "implied_by_roic",
    "multiples",
    "growth_share",
    "expected_return",
}
MATURE_STABLE_KEYS = {
    "e_trailing",
    "nri_gap",
    "ttm_margin",
    "median_margin",
    "margin_scaled",
    "e_normalized",
    "moat",
    "roic",
    "runway_return",
    "terminal_roic",
    "epv",
    "epv_total",
    "stable_growth",
    "stable_growth_total",
    "shares",
    "value_per_share",
    "eps",
    "dividend_yield",
    "net_buyback_yield",
    "income_basis",
    "price_facts",
    "growth_route",
    "multiples",
    "expected_return",
}


def codes(r: ValuationResult) -> list[str]:
    return [f.code for f in r.flags]


def flag(code: str) -> Flag:
    return Flag(code, code, f"{code}.")


def assert_refused(r: ValuationResult, reason: str) -> None:
    """A refusal is a full row with no value, never an exception."""
    assert r.refusal == reason
    assert (r.route, r.value, r.levels, r.stance5, r.stance3) == (None, None, None, None, None)
    assert result_from_json(result_to_json(r)) == r


# --- Mature Growth ------------------------------------------------------------------------------


def test_mature_growth_end_to_end(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(mg_inputs, deciles, policy, date(2026, 10, 31))
    assert r.route == "mature-growth" and r.refusal is None and r.value is not None
    assert r.price is not None
    assert r.levels == levels_for(r.value, r.intermediates["moat"], policy)
    assert r.stance5 == stance5(r.price, r.levels)
    assert {i.name for i in r.inputs} >= {
        "ntm_net_income",
        "required_return",
        "belief",
        "moat_class",
        "aggregate_roic",
    }
    assert all(i.tag in ("DATA", "RULE") for i in r.inputs)
    assert r.valid_until == mg_inputs.next_earnings
    assert result_from_json(result_to_json(r)) == r
    assert METHOD_VERSION == "fairband-mechanical/0.2"


def test_mature_growth_result(mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    capital = mg_inputs.capital_years
    assert r.symbol == "MGCO" and r.phase.phase == "Mature Growth" and r.phase.checks == ()
    # the value moves 96% between a 9% return and the company's 43.1% marginal return on a
    # 20-year runway
    assert codes(r) == ["value-spread"]
    assert (r.price, r.price_date, r.data_date) == (150.0, date(2026, 10, 30), date(2026, 10, 30))
    assert (r.policy_version, r.method_version) == (policy.version, METHOD_VERSION)
    assert r.deciles_refresh_id == deciles.refresh_id
    assert r.levels is not None and r.stance3 == stance3(150.0, r.levels)
    im = r.intermediates
    assert set(im) == MATURE_GROWTH_KEYS
    assert im["anchor"] == {"ntm_eps_raw": 5.90, "sbc_adjustment_per_share": 0.0, "ntm_eps": 5.90}
    assert im["sbc_basis"] == "includes-sbc"
    assert im["ntm_net_income"] == pytest.approx(5_900e6)
    assert im["path"] == {"base_year": 2027, "on_eps": False, "analysts": [10, 6]}
    assert im["path_steps"] == [pytest.approx(0.12), pytest.approx(0.10)]
    assert im["belief"] == {
        "rate": pytest.approx(0.063),
        "sales_class": "$12,000-25,000 Mn",
        "median": 0.043,
    }
    assert (im["moat"], im["runway"], im["shares"]) == ("Wide", 20, 1_000e6)
    assert im["roic"]["years"] == 10 and len(im["roic"]["by_year"]) == 10
    assert im["roic"]["by_year"][0]["year"] == 2016
    assert im["roic"]["aggregate"] == aggregate_roic(capital).aggregate
    assert im["roic"]["aggregate"] == pytest.approx(0.227, abs=1e-3)
    # the charge reads the five-year marginal return; the terminal, the moat's rule on it
    rr = im["runway_return"]
    expected = runway_return(aggregate_roic(capital), "Wide", policy)
    assert rr == {
        "used": expected.used,
        "marginal": expected.marginal,
        "marginal_usable": expected.marginal_usable,
        "three_year": expected.three_year,
        "ten_year": expected.ten_year,
        "value": expected.value,
    }
    assert (rr["used"], rr["marginal_usable"], rr["ten_year"]) == (
        "marginal",
        True,
        im["roic"]["aggregate"],
    )
    assert rr["value"] == pytest.approx(0.4315, abs=1e-4)
    assert im["fade_years"] == 5 and im["terminal_roic"] == terminal_return(
        expected, "Wide", policy
    )
    assert im["terminal_roic"] == policy.wide_terminal_roic_cap and im["charge_off"] is False

    # the value is the reverse DCF at the belief over the company's own runway and return, with
    # year 3's 10% fading to the belief over years 4 to 8, the last of them on the belief exactly
    growth = GrowthPath(5_900e6, (0.12, 0.10), 0.063, 20, fade_years=5)
    charge = Charge(rr["value"], im["terminal_roic"], 0.09, 0.03)
    assert im["growth_rates"] == pytest.approx(growth_rates(growth))
    assert len(im["growth_rates"]) == 19 and im["growth_rates"][2] == pytest.approx(0.0926)
    assert im["growth_rates"][6:] == [im["belief"]["rate"]] * 13
    assert im["value_total"] == pytest.approx(value_at_belief(growth, charge))
    assert r.value == im["value_per_share"] == pytest.approx(im["value_total"] / 1_000e6)
    assert im["value_by_runway"]["20"] == r.value
    assert im["value_by_runway"]["5"] < im["value_by_runway"]["10"] < r.value
    # the sensitivity: the row's own return, the policy's two, then the ten-year aggregate as the
    # runway return with the moat's terminal rule on it, below the marginal; the spread flag reads
    # the first three
    by_roic = im["value_by_roic"]
    assert list(by_roic) == ["runway", "0.15", "0.09", "ten-year"]
    assert by_roic["runway"] == r.value
    ten_year = Charge(
        expected.ten_year, terminal_roic(expected.ten_year, "Wide", policy), 0.09, 0.03
    )
    assert by_roic["ten-year"] == pytest.approx(value_at_belief(growth, ten_year) / 1_000e6)
    assert by_roic["0.09"] < by_roic["0.15"] < by_roic["ten-year"] < by_roic["runway"]

    # the implied growth is the belief at which the value equals the price
    implied = im["implied_growth"]
    at_price = value_at_belief(replace(growth, belief=implied), charge) / 1_000e6
    assert at_price == pytest.approx(150.0, rel=1e-6)
    assert im["implied_growth_by_runway"]["20"] == implied
    assert set(im["implied_growth_by_runway"]) == {"5", "10", "20"}
    assert list(im["implied_by_roic"]) == ["runway", "0.15", "0.09", "ten-year"]
    assert im["implied_by_roic"]["runway"] == implied
    assert implied < im["implied_by_roic"]["ten-year"] < im["implied_by_roic"]["0.15"]
    # at a ROIC equal to r growth up to r adds no value; only growth above r, which the payout
    # floor makes free, reaches the price
    assert im["value_by_roic"]["0.09"] == pytest.approx(VALUE_AT_R)
    at_r = im["implied_by_roic"]["0.09"]
    assert at_r > 0.09 and at_r > im["implied_by_roic"]["0.15"]
    at_r_value = value_at_belief(replace(growth, belief=at_r), Charge(0.09, 0.09, 0.09, 0.03))
    assert at_r_value / 1_000e6 == pytest.approx(150.0, rel=1e-6)
    # at $170 a 5-year runway needs growth beyond the old 50% bracket of the solve
    assert im["implied_growth_by_runway"]["10"] > implied
    five = reprice(r, 170.0, date(2026, 11, 2), policy).intermediates["implied_growth_by_runway"]
    assert five["5"] > 0.5
    at_five = value_at_belief(replace(growth, belief=five["5"], runway=5), charge) / 1_000e6
    assert at_five == pytest.approx(170.0, rel=1e-6)

    assert im["nri_gap"] == pytest.approx(0.05)
    assert im["eps"] == {"reported": 5.30, "clean": pytest.approx(5.25), "forward": 5.90}
    assert im["epv"] == pytest.approx(5.25 / 0.09)
    assert im["growth_share"] == pytest.approx(1 - 5.25 / 0.09 / 150)
    assert im["multiples"] == {
        "pe_reported": pytest.approx(150 / 5.30),
        "pe_clean": pytest.approx(150 / 5.25),
        "pe_forward": pytest.approx(150 / 5.90),
    }
    assert im["income_basis"] == "flows over market cap"
    assert im["dividend_yield"] == pytest.approx(1_000e6 / 150_000e6)
    assert im["net_buyback_yield"] == pytest.approx((2_000e6 - 100e6) / 150_000e6)
    er = im["expected_return"]
    assert er["income"] == pytest.approx(1_900e6 / 150_000e6 + 1_000e6 / 150_000e6)
    # the growth term reads the path as modeled: the two steps, then year 4's faded rate
    assert er["growth"] == pytest.approx(
        (1.12 * 1.10 * (1 + growth_rates(growth)[2])) ** (1 / 3) - 1
    )
    assert er["repricing"] == pytest.approx(math.log(r.value / 150.0) / 3)
    assert im["price_facts"]["high_52w"] == pytest.approx(150.0)
    assert im["price_facts"]["change_1y"] is not None


def test_mature_growth_inputs_cite_their_sources(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    sources = {"aggregate_roic": "statements", "ntm_net_income": "estimates_quarter"}
    inputs = replace(
        mg_inputs, provenance={k: v for k, v in mg_inputs.provenance.items() if k != "closes"}
    )
    r = value_company(inputs, deciles, policy, TODAY)
    by_name = {i.name: i for i in r.inputs}
    assert len(by_name) == len(r.inputs)
    for name, key in {**sources, "price": "price", "moat_score": "moat_score"}.items():
        assert by_name[name].provenance == mg_inputs.provenance[key]
        assert (by_name[name].tag, by_name[name].kind) == ("DATA", "observed")
    assert by_name["closes"].provenance == Provenance("unknown", None, None, None)
    rule = Provenance(f"policy {policy.version}", None, None, None)
    for name in (
        "required_return",
        "terminal_growth",
        "runway_years",
        "margin_of_safety",
        "belief",
        "moat_class",
        "terminal_roic",
    ):
        assert (by_name[name].tag, by_name[name].kind, by_name[name].provenance) == (
            "RULE",
            "rule",
            rule,
        )
    assert by_name["runway_years"].value == 20 and by_name["margin_of_safety"].value == 0.25
    assert by_name["moat_class"].note == "Wide" and by_name["belief"].value == pytest.approx(0.063)


def test_an_input_assembly_estimated_is_tagged_as_an_estimate(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    method = "tax-rate-latest-oecd-year-v1"
    inputs = replace(mg_inputs, estimate_methods={"tax_rate_latest": method})
    by_name = {i.name: i for i in value_company(inputs, deciles, policy, TODAY).inputs}
    tax = by_name["tax_rate_latest"]
    assert (tax.tag, tax.kind, tax.estimate_method, tax.value) == ("DATA", "estimate", method, 0.25)
    assert tax.provenance == mg_inputs.provenance["tax_rate_latest"]
    assert (by_name["price"].kind, by_name["price"].estimate_method) == ("observed", None)


def test_both_routes_carry_the_tax_rate_with_the_assembly_note(
    mg_inputs: CompanyInputs, ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The statutory rate feeds every NOPAT of the ROIC, and Mature Growth's anchor besides: both
    routes carry it, with the note assembly wrote (the country, the rate's year and source)."""
    note = "US, the headquarters country in the FMP profile: its 2025 statutory rate, from OECD"
    for inputs in (mg_inputs, ms_inputs):
        r = value_company(replace(inputs, notes={"tax_rate_latest": note}), deciles, policy, TODAY)
        assert r.refusal is None
        [tax] = [i for i in r.inputs if i.name == "tax_rate_latest"]
        assert (tax.tag, tax.kind, tax.value, tax.note) == ("DATA", "observed", 0.25, note)
        assert tax.provenance == inputs.provenance["tax_rate_latest"]


def test_the_intangibles_estimate_reaches_the_roic_inputs(
    mg_inputs: CompanyInputs, ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Assembly took the issuer's as-reported intangibles total (D17) into invested capital: on
    both routes the aggregate ROIC and the runway return the drawer shows are estimates under
    that method. The aggregate ROIC says why; the runway return keeps the note naming the measure
    the charge used. The snapshot keeps them."""
    method = "bs10-intangibles-total-v1"
    for inputs in (mg_inputs, ms_inputs):
        plain = {i.name: i for i in value_company(inputs, deciles, policy, TODAY).inputs}
        ten_year, runway = plain["aggregate_roic"], plain["runway_return"]
        assert (ten_year.kind, ten_year.estimate_method, ten_year.note) == ("observed", None, None)
        assert (runway.kind, runway.estimate_method) == ("observed", None)
        r = value_company(
            replace(inputs, estimate_methods={"intangibles": method}), deciles, policy, TODAY
        )
        by_name = {i.name: i for i in r.inputs}
        for name in ("aggregate_roic", "runway_return"):
            found = by_name[name]
            assert (found.tag, found.kind, found.estimate_method) == ("DATA", "estimate", method)
            assert (found.value, found.provenance) == (plain[name].value, plain[name].provenance)
        assert by_name["aggregate_roic"].note == (
            "invested capital uses the issuer's total intangibles excluding goodwill"
        )
        assert by_name["runway_return"].note == runway.note
        assert runway.note is not None
        assert result_from_json(result_to_json(r)) == r


def test_mature_growth_is_deterministic(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    first = result_to_json(value_company(mg_inputs, deciles, policy, TODAY))
    again = result_to_json(value_company(replace(mg_inputs), deciles, policy, TODAY))
    assert first == again
    assert json.loads(first)["intermediates"]["value_by_roic"]["ten-year"] is not None


def test_roic_not_positive_floors_the_runway_return(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # flat losses: the marginal is not usable, and the three-year return, below r, is floored
    losses = tuple(replace(y, operating_income=-100e6) for y in mg_inputs.capital_years)
    r = value_company(replace(mg_inputs, capital_years=losses), deciles, policy, TODAY)
    im = r.intermediates
    assert r.value is not None and im["roic"]["aggregate"] < 0
    assert im["runway_return"]["used"] == "floor" and im["runway_return"]["three_year"] < 0
    assert im["runway_return"]["value"] == im["terminal_roic"] == policy.required_return
    assert im["value_by_roic"]["ten-year"] is None and im["implied_by_roic"]["ten-year"] is None
    assert "roic-unavailable" not in codes(r)
    floored = next(f for f in r.flags if f.code == "return-floored")
    assert floored.sentence.startswith("The three-year return of -")


def test_too_few_roic_years_uses_the_terminal_roic(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    short = replace(mg_inputs, capital_years=mg_inputs.capital_years[-4:])
    r = value_company(short, deciles, policy, TODAY)
    assert r.intermediates["roic"]["aggregate"] is None
    assert r.intermediates["runway_return"]["value"] == r.intermediates["terminal_roic"] == 0.09
    assert codes(r).count("roic-unavailable") == 1


def test_capital_at_or_below_zero_zeroes_the_charge(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    negative = tuple(
        replace(y, total_current_liabilities=3 * (y.total_current_assets or 0))
        for y in mg_inputs.capital_years
    )
    r = value_company(replace(mg_inputs, capital_years=negative), deciles, policy, TODAY)
    im = r.intermediates
    assert im["charge_off"] is True and im["runway_return"]["used"] == "off"
    assert "charge-zeroed" in codes(r) and "roic-unavailable" not in codes(r)
    assert "ten-year-roic-unavailable" in codes(r)
    # the terminal still charges, at the Wide cap
    assert im["terminal_roic"] == im["runway_return"]["value"] == policy.wide_terminal_roic_cap
    zeroed = next(f for f in r.flags if f.code == "charge-zeroed")
    assert zeroed.sentence.endswith("the terminal still charges at 13.0%.")
    growth = GrowthPath(5_900e6, (0.12, 0.10), 0.063, 20, fade_years=5)
    off = Charge(im["runway_return"]["value"], im["terminal_roic"], 0.09, 0.03, charge_off=True)
    assert r.value == pytest.approx(value_at_belief(growth, off) / 1_000e6)
    # no runway charge, so no payout to floor
    assert "growth-above-return" not in codes(r)


def test_charge_off_row_keeps_the_terminal_charge(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    negative = tuple(
        replace(y, total_current_liabilities=3 * (y.total_current_assets or 0))
        for y in mg_inputs.capital_years
    )
    r = value_company(replace(mg_inputs, capital_years=negative), deciles, policy, TODAY)
    im = r.intermediates
    assert im["charge_off"] is True and im["runway_return"]["used"] == "off"
    assert im["terminal_roic"] == 0.13  # Wide; the terminal multiple is 13.2, not 17.2
    growth = GrowthPath(im["ntm_net_income"], tuple(im["path_steps"]), im["belief"]["rate"], 20, 5)
    assert im["value_total"] == pytest.approx(
        value_at_belief(growth, Charge(0.13, 0.13, 0.09, 0.03, charge_off=True))
    )


def test_runway_return_input_carries_its_note(
    mg_inputs: CompanyInputs, ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Both routes carry the runway return the charge used, a DATA input from the statements
    after the aggregate ROIC, with a note naming the measure."""
    notes = {
        "MGCO": "five-year marginal return on new capital",  # capital grew 47% in five years
        "MSCO": "three-year aggregate ROIC (marginal not usable)",  # it grew 10%
    }
    for inputs in (mg_inputs, ms_inputs):
        r = value_company(inputs, deciles, policy, TODAY)
        names = [i.name for i in r.inputs]
        assert names.index("runway_return") == names.index("aggregate_roic") + 1
        [rr] = [i for i in r.inputs if i.name == "runway_return"]
        assert (rr.tag, rr.kind, rr.unit, rr.note) == ("DATA", "observed", "ratio", notes[r.symbol])
        assert rr.provenance == inputs.provenance["statements"]
        assert rr.value == r.intermediates["runway_return"]["value"]
        assert result_from_json(result_to_json(r)) == r


def test_flags_in_order_without_duplicates(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    assert mg_inputs.trailing is not None
    series = mg_inputs.series
    base, second, third = (replace(a, analysts_net_income=3) for a in mg_inputs.annual_estimates)
    inputs = replace(
        mg_inputs,
        input_flags=(flag("trailing-on-fiscal-year"), flag("equity-raise")),
        series=(*series[:-1], replace(series[-1], cfo=1e9, capex=-2e9)),  # a negative FCF
        street_ttm_eps=None,  # the SBC basis is unknown
        annual_estimates=(  # 50% a year, above the 43.1% marginal return
            base,
            replace(second, net_income=1.50 * base.net_income),
            replace(third, net_income=1.50 * 1.50 * base.net_income),
        ),
        capital_years=mg_inputs.capital_years[-8:],  # ROIC on 7 years
        trailing=replace(
            mg_inputs.trailing,
            operating_income=9_120e6,  # a 40% margin against a 30% high
            equity_issued=5_000e6,  # an equity raise, which assembly already flagged
        ),
        gf_eps_without_nri=4.80,  # a non-recurring gain of 0.50 a share
        price=700.0,  # an implied growth above 10% on a 20-year runway
    )
    r = value_company(inputs, deciles, policy, TODAY)
    assert codes(r) == [
        "trailing-on-fiscal-year",  # assembly
        "equity-raise",
        "fcf-sign",  # the classifier
        "sbc-basis-unknown",  # the anchor
        "few-analysts",  # the path
        "roic-on-n-years",  # the ROIC
        "growth-above-return",  # the payout floor
        "margin-flag",
        "large-nri",
        "long-runway-high-growth",
        "value-spread",
    ]
    assert r.flags[1] == flag("equity-raise")


def test_income_needs_a_market_cap(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    for market_cap in (None, 0.0, math.nan, math.inf):
        r = value_company(replace(mg_inputs, market_cap=market_cap), deciles, policy, TODAY)
        im = r.intermediates
        assert (im["income_basis"], im["dividend_yield"], im["net_buyback_yield"]) == (
            "unavailable",
            0.0,
            0.0,
        )
        assert im["expected_return"]["income"] == 0.0
        assert result_from_json(result_to_json(r)) == r


def test_a_return_below_r_is_floored(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # a 2% marginal return: the charge uses r, at which growth up to r adds no value
    poor = tuple(
        replace(y, operating_income=(y.operating_income or 0) / 22) for y in mg_inputs.capital_years
    )
    r = value_company(replace(mg_inputs, capital_years=poor), deciles, policy, TODAY)
    im = r.intermediates
    assert im["runway_return"]["used"] == "floor" and im["runway_return"]["marginal_usable"]
    assert im["runway_return"]["value"] == im["terminal_roic"] == policy.required_return
    assert r.refusal is None and r.value == pytest.approx(VALUE_AT_R)
    floored = next(f for f in r.flags if f.code == "return-floored")
    assert floored.sentence.startswith("The five-year marginal return of 2.0%")
    [note] = [i.note for i in r.inputs if i.name == "runway_return"]
    assert note == "floored at the required return; the five-year marginal was 2.0%"


def test_growth_above_return_flag(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # consensus net income up 50% a year in fiscal 2028 and 2029, above the 43.1% marginal return:
    # years 1 and 2 would reinvest more than they earn, so their payouts floor at zero
    base, second, third = mg_inputs.annual_estimates
    steep = replace(
        mg_inputs,
        annual_estimates=(
            base,
            replace(second, net_income=1.50 * base.net_income),
            replace(third, net_income=1.50 * 1.50 * base.net_income),
        ),
    )
    r = value_company(steep, deciles, policy, TODAY)
    above = next(f for f in r.flags if f.code == "growth-above-return")
    assert above.word == "Growth above return"
    assert above.sentence == (
        "Year 1 growth of 50.0% exceeds the 43.1% return on new capital; the payout is floored "
        "at zero and the growth above the return is treated as efficiency growth, which costs "
        "nothing."
    )
    assert r.value is not None and r.value > 0
    assert "growth-above-return" not in codes(value_company(mg_inputs, deciles, policy, TODAY))


def test_implied_growth_round_trip_with_fade(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    assert r.value is not None
    im = r.intermediates
    at_value = growth_at_price(im, r.value, r.value, policy)["implied_growth"]
    assert at_value == pytest.approx(im["belief"]["rate"], abs=1e-6)


def test_value_at_or_below_zero_is_refused(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy, monkeypatch: pytest.MonkeyPatch
) -> None:
    # with every return floored at r a positive anchor has a positive value; the guard stays
    monkeypatch.setattr(route_mature_growth, "value_at_belief", lambda growth, charge: -1.0)
    r = value_company(mg_inputs, deciles, policy, TODAY)
    assert_refused(r, "value not positive under the reinvestment charge")
    im = r.intermediates
    # the value side is kept for the drawer; nothing at the price is computed
    assert im["value_per_share"] < 0
    assert im["price_facts"] == asdict(price_facts(mg_inputs.closes, TODAY))
    assert not {"implied_growth", "multiples", "expected_return"} & set(im)
    assert r.price == 150.0 and r.phase.phase == "Mature Growth"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"trailing": None}, "no trailing figures"),
        ({"tax_rate_latest": None}, "no statutory tax rate"),
        ({"price": 5.0}, "forward P/E below 2: unit error"),
    ],
)
def test_mature_growth_refusals(
    mg_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
    change: dict[str, Any],
    reason: str,
) -> None:
    r = value_company(replace(mg_inputs, **change), deciles, policy, TODAY)
    assert_refused(r, reason)
    assert r.phase.phase == "Mature Growth"


def test_mature_growth_refusals_on_the_consensus(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    assert mg_inputs.trailing is not None
    no_revenue = replace(mg_inputs, trailing=replace(mg_inputs.trailing, revenue=None))
    assert_refused(value_company(no_revenue, deciles, policy, TODAY), "no trailing revenue")

    three = replace(mg_inputs, quarter_estimates=mg_inputs.quarter_estimates[:3])
    assert_refused(value_company(three, deciles, policy, TODAY), "incomplete NTM consensus")

    losses = tuple(replace(q, eps=-q.eps if q.eps else None) for q in mg_inputs.quarter_estimates)
    r = value_company(replace(mg_inputs, quarter_estimates=losses), deciles, policy, TODAY)
    assert_refused(r, "no positive forward anchor")

    turn = (
        *mg_inputs.annual_estimates[:2],
        replace(mg_inputs.annual_estimates[2], net_income=-1e9, eps=-1.0),
    )
    r = value_company(replace(mg_inputs, annual_estimates=turn), deciles, policy, TODAY)
    assert_refused(r, "consensus earnings turn negative within the path")
    assert "path-on-eps" in codes(r)


# --- Mature Stable ------------------------------------------------------------------------------


def test_mature_stable_end_to_end(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(ms_inputs, deciles, policy, TODAY)
    assert r.route == "mature-stable" and r.refusal is None and r.value is not None
    assert r.phase.phase == "Mature Stable" and r.flags == ()
    im = r.intermediates
    assert set(im) == MATURE_STABLE_KEYS
    assert r.value == im["value_per_share"] == im["stable_growth"]
    assert im["stable_growth"] == pytest.approx(im["stable_growth_total"] / 1_000e6)
    assert im["e_trailing"] == pytest.approx(3_400e6 - 0.10 * 1_000e6)
    assert im["e_normalized"] == im["e_trailing"] and im["margin_scaled"] is False
    assert im["moat"] == "Wide" and im["terminal_roic"] == 0.13
    assert im["epv_total"] == pytest.approx(3_300e6 / 0.09)
    assert im["epv"] == pytest.approx(3.30 / 0.09)  # a share, as the screen's EPV column
    assert im["stable_growth_total"] == pytest.approx(3_300e6 * (1 - 0.03 / 0.13) / 0.06)
    assert im["stable_growth"] / im["epv"] == pytest.approx(1.154, abs=1e-3)  # about 15% above
    assert im["median_margin"] == pytest.approx(0.20) and im["ttm_margin"] == pytest.approx(0.20)
    assert im["eps"] == {"reported": 3.40, "clean": pytest.approx(3.30), "forward": None}
    assert im["multiples"]["pe_forward"] is None
    er = im["expected_return"]
    assert er["growth"] == pytest.approx(0.03)
    assert er["income"] == pytest.approx((1_500e6 + 500e6) / 40_000e6)
    assert r.levels == levels_for(r.value, "Wide", policy)
    assert r.stance5 == stance5(40.0, r.levels)
    by_name = {i.name: i for i in r.inputs}
    assert {"net_income_ttm", "aggregate_roic", "terminal_roic", "moat_class", "belief"} <= set(
        by_name
    )
    assert not {"runway_years", "ntm_net_income"} & set(by_name)
    belief = by_name["belief"]
    assert (belief.tag, belief.value) == ("RULE", policy.terminal_growth)
    assert result_from_json(result_to_json(r)) == r


def test_mature_stable_scales_a_margin_above_history(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    assert ms_inputs.trailing is not None
    peak = replace(ms_inputs, trailing=replace(ms_inputs.trailing, operating_income=7_680e6))
    r = value_company(peak, deciles, policy, TODAY)
    im = r.intermediates
    assert "margin-flag" in codes(r) and im["margin_scaled"] is True
    assert im["e_normalized"] == pytest.approx(im["e_trailing"] * 0.20 / 0.32)
    assert im["epv_total"] == pytest.approx(im["e_normalized"] / 0.09)
    assert im["epv"] == pytest.approx(im["epv_total"] / 1_000e6)


def test_mature_stable_never_zeroes_the_charge(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # capital sums to zero or below and the moat is None: the stable-growth value is EPV
    negative = tuple(
        replace(y, total_current_liabilities=3 * (y.total_current_assets or 0))
        for y in ms_inputs.capital_years
    )
    inputs = replace(ms_inputs, capital_years=negative, moat_score=None)
    r = value_company(inputs, deciles, policy, TODAY)
    im = r.intermediates
    assert "charge-zeroed" not in codes(r) and im["roic"]["aggregate"] is None
    assert "ten-year-roic-unavailable" in codes(r)  # the shown ten-year figure, its own flag
    unavailable = next(f for f in r.flags if f.code == "roic-unavailable")
    assert unavailable.sentence == (
        "Operating capital summed to zero or below over the last 3 ROIC years and the marginal "
        "return is not usable, so the stable-growth value uses the moat's terminal return."
    )
    assert im["moat"] == "None" and im["terminal_roic"] == policy.required_return
    assert r.value == pytest.approx(im["epv"])
    assert im["epv_total"] == pytest.approx(3_300e6 / 0.09)


def test_mature_stable_without_the_nri_gap(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(replace(ms_inputs, gf_eps_without_nri=None), deciles, policy, TODAY)
    assert r.intermediates["nri_gap"] is None
    assert r.intermediates["e_trailing"] == 3_400e6
    assert r.intermediates["eps"]["clean"] == 3.40


def test_mature_stable_refusals(ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    assert ms_inputs.trailing is not None
    r = value_company(replace(ms_inputs, trailing=None), deciles, policy, TODAY)
    assert_refused(r, "no trailing figures")
    loss = replace(ms_inputs, trailing=replace(ms_inputs.trailing, net_income=50e6))
    r = value_company(loss, deciles, policy, TODAY)  # 50m less a 100m gain is a loss
    assert_refused(r, "no positive trailing earnings")
    assert r.phase.phase == "Mature Stable"
    none = replace(ms_inputs, trailing=replace(ms_inputs.trailing, net_income=None))
    assert_refused(value_company(none, deciles, policy, TODAY), "no positive trailing earnings")


def _with_consensus(stable: CompanyInputs, growth: CompanyInputs) -> CompanyInputs:
    """The stable company with the growth company's NTM and annual consensus."""
    return replace(
        stable, quarter_estimates=growth.quarter_estimates, annual_estimates=growth.annual_estimates
    )


def test_mature_stable_cross_check_present_with_a_path(
    ms_inputs: CompanyInputs, mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # the stable company has no consensus of its own; it takes the growth company's
    inputs = _with_consensus(ms_inputs, mg_inputs)
    r = value_company(inputs, deciles, policy, TODAY)
    gr = r.intermediates["growth_route"]
    assert gr["refusal"] is None and gr["value_per_share"] > 0
    assert set(gr) == {
        "value_per_share",
        "runway_return",
        "path_steps",
        "belief",
        "implied_growth",
        "refusal",
    }
    assert r.value == r.intermediates["stable_growth"]  # the headline stays the stable value
    assert r.levels == levels_for(r.value, "Wide", policy)
    assert result_from_json(result_to_json(r)) == r
    # the cross-check is the value the growth route reaches on the same company, with its implied
    # growth at the price: none at $40, below the $48.12 the growth route gives at -50% a year
    assert inputs.trailing is not None
    for price, implied in ((40.0, None), (120.0, pytest.approx(0.0747, abs=1e-4))):
        priced = replace(inputs, price=price)
        r = value_company(priced, deciles, policy, TODAY)
        gr = r.intermediates["growth_route"]
        c = Context(priced, inputs.trailing, price, 1_000e6, policy, TODAY)
        own = route_mature_growth.value_mature_growth(c)
        assert isinstance(own, Valued) and own.value != r.value
        im = own.intermediates
        assert gr["value_per_share"] == own.value == pytest.approx(111.62, abs=0.01)
        assert gr["implied_growth"] == im["implied_growth"] == implied
        assert gr["runway_return"] == im["runway_return"] == r.intermediates["runway_return"]
        assert (gr["path_steps"], gr["belief"]) == (im["path_steps"], im["belief"])


def test_mature_stable_cross_check_absent_with_a_refusal(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(replace(ms_inputs, quarter_estimates=()), deciles, policy, TODAY)
    assert r.intermediates["growth_route"] == {"refusal": "incomplete NTM consensus"}
    assert r.refusal is None and r.value == r.intermediates["stable_growth"]


def test_mature_stable_cross_check_refuses_a_value_not_positive(
    ms_inputs: CompanyInputs,
    mg_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(route_mature_growth, "value_at_belief", lambda growth, charge: -1.0)
    r = value_company(_with_consensus(ms_inputs, mg_inputs), deciles, policy, TODAY)
    reason = "value not positive under the reinvestment charge"
    assert r.intermediates["growth_route"] == {"refusal": reason}
    assert r.refusal is None and r.value == r.intermediates["stable_growth"]


def _capital_year(year: int, nopat: float, capital: float) -> CapitalYear:
    """A year whose invested capital is all net property and equipment, taxed at 25%."""
    return CapitalYear(year, nopat / 0.75, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, capital, 0.0, 0.0, 0.0)


def test_mature_stable_reads_the_shared_terminal(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # a Wide stable row whose marginal return is above 13% and ten-year aggregate 10% values at
    # 13%: invested capital is $10 bn at each year end to 2023 and $20 bn at the ends of 2024 and
    # 2025; NOPAT is $0.87 bn a year and $3.67 bn in 2025. Average capital rises $10 bn from 2020
    # to 2025 and NOPAT $2.8 bn, a 28% marginal return; $11.5 bn of NOPAT over $115 bn of average
    # capital is 10%.
    capital = [10e9] * 9 + [20e9] * 2  # the balance sheets of 2015 to 2025
    nopat = [0.87e9] * 10 + [3.67e9]
    years = tuple(
        _capital_year(2015 + k, n, ic) for k, (n, ic) in enumerate(zip(nopat, capital, strict=True))
    )
    r = value_company(replace(ms_inputs, capital_years=years), deciles, policy, TODAY)
    im = r.intermediates
    assert im["moat"] == "Wide" and im["runway_return"]["used"] == "marginal"
    assert im["runway_return"]["marginal"] == pytest.approx(0.28)
    assert im["roic"]["aggregate"] == pytest.approx(0.10)
    assert r.intermediates["terminal_roic"] == 0.13
    assert im["stable_growth_total"] == pytest.approx(3_300e6 * (1 - 0.03 / 0.13) / 0.06)


# --- Refusals before the route ------------------------------------------------------------------


def test_refuses_without_deciles(mg_inputs: CompanyInputs, policy: Policy) -> None:
    r = value_company(mg_inputs, None, policy, date(2026, 10, 31))
    assert r.phase.phase is None and r.refusal == "no universe deciles yet"
    assert r.phase.reason == "no universe deciles yet" and r.deciles_refresh_id is None
    assert_refused(r, "no universe deciles yet")


def test_assembly_refusal_comes_first_with_the_phase(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    reason = "no statutory tax rate for United States 2015"
    inputs = replace(mg_inputs, refusal=reason, currency="EUR", input_flags=(flag("x"),))
    r = value_company(inputs, deciles, policy, TODAY)
    assert_refused(r, reason)
    assert r.phase.phase == "Mature Growth" and r.flags == (flag("x"),)
    assert r.price == 150.0 and r.valid_until == mg_inputs.next_earnings


def test_no_deciles_outranks_an_assembly_refusal(mg_inputs: CompanyInputs, policy: Policy) -> None:
    """Before the first full refresh the reason is the missing deciles; the assembly refusal is
    judged again by the run that has them."""
    reason = "no statutory tax rate for unknown 2015"
    inputs = replace(mg_inputs, refusal=reason, input_flags=(flag("x"),))
    r = value_company(inputs, None, policy, TODAY)
    assert_refused(r, "no universe deciles yet")
    assert r.phase.phase is None and r.phase.reason == "no universe deciles yet"
    assert r.flags == (flag("x"),) and r.price == 150.0


def test_refuses_foreign_filer(mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    reason = "foreign filer: currency and share-unit handling not built yet"
    for inputs in (replace(mg_inputs, currency="EUR"), replace(mg_inputs, is_adr=True)):
        r = value_company(inputs, deciles, policy, TODAY)
        assert_refused(r, reason)
        assert r.phase.phase == "Mature Growth"


def test_refuses_other_phases(
    young_growth_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(young_growth_inputs, deciles, policy, TODAY)
    assert_refused(r, "Young Growth route not built yet")
    assert r.phase.phase == "Young Growth" and r.price == 150.0
    names = [i.name for i in r.inputs]
    assert names == ["statements", "price", "shares_diluted", "next_earnings", "closes"]
    assert r.inputs[0].value == 6 and r.inputs[0].note == "fiscal 2020 to 2025"
    # the price columns are not value-based: a refused row has them too
    facts = asdict(price_facts(young_growth_inputs.closes, TODAY))
    assert r.intermediates == {"price_facts": facts} and facts["high_52w"] == pytest.approx(150.0)


def test_refusals_carry_the_price_facts(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    facts = asdict(price_facts(mg_inputs.closes, TODAY))
    for r in (
        value_company(replace(mg_inputs, currency="EUR"), deciles, policy, TODAY),
        value_company(mg_inputs, None, policy, TODAY),
    ):
        assert r.value is None and r.intermediates == {"price_facts": facts}
    # a row with no price has no price facts
    r = value_company(replace(mg_inputs, price=None, currency="EUR"), deciles, policy, TODAY)
    assert r.intermediates == {"price_facts": None}


def test_refuses_start_up_and_unclassified(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    series = mg_inputs.series
    start_up = (*series[:-4], replace(series[-4], revenue=0.0), *series[-3:])
    r = value_company(replace(mg_inputs, series=start_up), deciles, policy, TODAY)
    assert_refused(
        r,
        "Start-up: no value by design; the price-implied requirement comes with the Start-up route",
    )
    assert r.phase.phase == "Start-up"
    r = value_company(replace(mg_inputs, series=series[-1:]), deciles, policy, TODAY)
    assert_refused(r, "fewer than two fiscal years")
    assert r.phase.phase is None


def test_refuses_without_shares(mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(replace(mg_inputs, shares_diluted=0.0), deciles, policy, date(2026, 10, 31))
    assert r.refusal == "no diluted share count" and r.value is None
    for shares in (None, -5.0):
        r = value_company(replace(mg_inputs, shares_diluted=shares), deciles, policy, TODAY)
        assert_refused(r, "no diluted share count")


def test_refuses_without_price(mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(
        replace(mg_inputs, price=None, price_date=None), deciles, policy, date(2026, 10, 31)
    )
    assert r.refusal == "no price" and r.phase.phase == "Mature Growth"
    for price in (0.0, -1.0, math.nan):
        r = value_company(replace(mg_inputs, price=price), deciles, policy, TODAY)
        assert_refused(r, "no price")
        assert (r.price, r.price_date) == (None, None)


def test_refusal_result_shape(policy: Policy) -> None:
    r = refusal_result("X", "data fetch failed: quote", policy, date(2026, 10, 31))
    assert r.value is None and r.price is None
    assert r.valid_until == date(2026, 10, 31) + timedelta(days=91)
    assert r.phase.phase is None and r.phase.reason == "data fetch failed: quote"
    assert (r.phase.years_used, r.phase.checks) == (0, ())
    assert (r.inputs, r.intermediates, r.flags, r.deciles_refresh_id) == ((), {}, (), None)
    kept = refusal_result("X", "x", policy, date(2026, 10, 31), intermediates={"price_facts": None})
    assert kept.intermediates == {"price_facts": None}
    assert (r.policy_version, r.method_version) == (policy.version, METHOD_VERSION)
    assert_refused(r, "data fetch failed: quote")


# --- Validity -----------------------------------------------------------------------------------


def test_fallback_validity(mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    fallback = mg_inputs.data_date + timedelta(days=91)
    r = value_company(replace(mg_inputs, next_earnings=None), deciles, policy, TODAY)
    assert r.value is not None and r.valid_until == fallback
    # a next earnings date on or before the data date is stale; it never expires a fresh row
    for stale in (mg_inputs.data_date, date(2026, 7, 30)):
        r = value_company(replace(mg_inputs, next_earnings=stale), deciles, policy, TODAY)
        assert r.valid_until == fallback


# --- Reprice ------------------------------------------------------------------------------------


def test_reprice_keeps_value_changes_stance(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    assert r.value is not None and r.levels is not None
    low = r.levels.buy * 0.9
    p = reprice(r, low, date(2026, 11, 2), policy)
    assert (p.value, p.levels, p.valid_until, p.data_date) == (
        r.value,
        r.levels,
        r.valid_until,
        r.data_date,
    )
    assert (p.price, p.price_date, p.stance5, p.stance3) == (low, date(2026, 11, 2), "BUY", "buy")
    assert r.stance5 != "BUY"
    fresh = value_company(
        replace(mg_inputs, price=low, price_date=date(2026, 11, 2)), deciles, policy, TODAY
    )
    for key in (
        "implied_growth",
        "implied_growth_by_runway",
        "implied_by_roic",
        "multiples",
        "growth_share",
        "expected_return",
    ):
        assert p.intermediates[key] == fresh.intermediates[key]
    assert p.intermediates["price_facts"] == r.intermediates["price_facts"]


def test_reprice_at_the_same_price_changes_nothing(
    mg_inputs: CompanyInputs, ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    for inputs in (mg_inputs, ms_inputs):
        r = value_company(inputs, deciles, policy, TODAY)
        assert r.price is not None and r.price_date is not None
        stored = result_from_json(result_to_json(r))
        assert reprice(stored, r.price, r.price_date, policy) == r


def test_reprice_mature_stable(ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(ms_inputs, deciles, policy, TODAY)
    p = reprice(r, 80.0, date(2026, 11, 2), policy)
    fresh = value_company(replace(ms_inputs, price=80.0), deciles, policy, TODAY)
    assert p.value == r.value and p.stance5 == fresh.stance5 == "TRIM"
    assert p.intermediates["multiples"] == fresh.intermediates["multiples"]
    assert p.intermediates["expected_return"] == fresh.intermediates["expected_return"]


def test_reprice_updates_the_long_runway_flag(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    assert "long-runway-high-growth" not in codes(r)
    high = reprice(r, 400.0, date(2026, 11, 2), policy)
    assert (
        high.flags == value_company(replace(mg_inputs, price=400.0), deciles, policy, TODAY).flags
    )
    assert "long-runway-high-growth" in codes(high)
    assert reprice(high, 150.0, date(2026, 11, 3), policy).flags == r.flags


def test_reprice_moves_the_price_input(
    mg_inputs: CompanyInputs,
    ms_inputs: CompanyInputs,
    young_growth_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
) -> None:
    """The drawer reproduces a repriced row: its price input is the fresh quote, as of the new
    price date and stamped as the quote was; its source and every other input stay. A refusal's
    price input moves too."""
    day = date(2026, 11, 2)
    observed = datetime(2026, 11, 2, 21, 0, tzinfo=UTC)
    entered = datetime(2026, 11, 2, 21, 5, tzinfo=UTC)
    for inputs in (mg_inputs, ms_inputs, young_growth_inputs):
        r = value_company(inputs, deciles, policy, TODAY)
        p = reprice(r, 65.0, day, policy, observed_at=observed, entered_at=entered)
        assert [i.name for i in p.inputs] == [i.name for i in r.inputs]
        [price] = [i for i in p.inputs if i.name == "price"]
        assert (p.price, price.value, price.tag, price.kind) == (65.0, 65.0, "DATA", "observed")
        assert price.provenance == Provenance("FMP quote", day, observed, entered)
        others = [i for i in p.inputs if i.name != "price"]
        assert others == [i for i in r.inputs if i.name != "price"]
        # Without the quote's stamps the price input keeps its own.
        [kept] = [i for i in reprice(r, 65.0, day, policy).inputs if i.name == "price"]
        assert kept.provenance == replace(inputs.provenance["price"], as_of=day)
    assert p.refusal == "Young Growth route not built yet"


def test_reprice_a_refusal_moves_only_the_price(policy: Policy) -> None:
    r = refusal_result("X", "Decline route not built yet", policy, date(2026, 10, 31), price=10.0)
    p = reprice(r, 12.0, date(2026, 11, 2), policy)
    assert p == replace(r, price=12.0, price_date=date(2026, 11, 2))
    with pytest.raises(ValueError, match="positive"):
        reprice(r, 0.0, date(2026, 11, 2), policy)
