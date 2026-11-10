import json
import math
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from support import engine_companies
from support.stable_value import stable_dcf

from fairband.engine import METHOD_VERSION, route_mature_growth
from fairband.engine.classifier import Deciles
from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.mature_growth import (
    Charge,
    GrowthPath,
    growth_rates,
    hold_years,
    implied_growth,
    return_by_year,
    value_at_belief,
)
from fairband.engine.overrides import Override, OverrideTag, check_override, current_reading
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
from fairband.engine.route_steps import Context, Valued, expected
from fairband.engine.types import (
    Flag,
    Provenance,
    ValuationResult,
    result_from_json,
    result_to_json,
)
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH, apply_overlay

TODAY = date(2026, 10, 31)
# At a return equal to r, growth adds no value and the value is year-1 earnings over r, whatever
# the path, when the charge pays for the earnings growth (MGCO has no consensus revenue): with the
# payout floor off (spec 2026-11-09 6.1), years 1 to 3, which pay for growth above r, pay out less
# than nothing, where the floor added their cash back.
VALUE_AT_R = 5.90 / 0.09

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
    "charge",
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
    "charge_off",
    "charge",
    "runway",
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
# A Mature Stable row's growth-route cross-check with a path: the value and the keys its implied
# growth is rebuilt from at a new price.
CROSS_CHECK_KEYS = {
    "value_per_share",
    "ntm_net_income",
    "path_steps",
    "belief",
    "runway",
    "fade_years",
    "runway_return",
    "terminal_roic",
    "charge_off",
    "charge",
    "implied_growth",
    "refusal",
}


def codes(r: ValuationResult) -> list[str]:
    return [f.code for f in r.flags]


def judged(*values: tuple[OverrideTag, float | str]) -> dict[OverrideTag, Override]:
    """An agent's applied overrides of ``values``, by tag, as ``value_company`` takes them."""
    at = datetime(2026, 11, 9, 12, 0, tzinfo=UTC)
    return {
        tag: Override(k, tag, value, "agent", "claude-opus-5-5", at, "because")
        for k, (tag, value) in enumerate(values, start=1)
    }


def with_revenue(i: CompanyInputs, revenue: tuple[float, float, float]) -> CompanyInputs:
    """``i`` with consensus revenue means for its three annual years, 20 revenue analysts each."""
    rows = tuple(
        replace(a, revenue=x, analysts_revenue=20)
        for a, x in zip(i.annual_estimates, revenue, strict=True)
    )
    return replace(i, annual_estimates=rows)


def flag(code: str) -> Flag:
    return Flag(code, code, f"{code}.")


def assert_refused(r: ValuationResult, reason: str) -> None:
    """A refusal is a full row with no value, never an exception."""
    assert r.refusal == reason
    assert (r.route, r.value, r.levels, r.price_to_value, r.designation) == (None,) * 5
    assert result_from_json(result_to_json(r)) == r


# --- Mature Growth ------------------------------------------------------------------------------


def test_mature_growth_end_to_end(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(mg_inputs, deciles, policy, date(2026, 10, 31))
    assert r.route == "mature-growth" and r.refusal is None and r.value is not None
    assert r.price is not None
    assert r.levels == levels_for(r.value, r.intermediates["moat"], policy)
    assert (r.price_to_value, r.designation) == designation_for(
        r.price, r.value, policy.designation_edges
    )
    assert not hasattr(r, "stance5") and not hasattr(r, "stance3")
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
    assert METHOD_VERSION == "fairband-mechanical/1.1"


def test_mature_growth_result(mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    capital = mg_inputs.capital_years
    assert r.symbol == "MGCO" and r.phase.phase == "Mature Growth" and r.phase.checks == ()
    # the value moves 95% between a 9% return and the company's 43.1% marginal return on a
    # 20-year runway
    assert codes(r) == ["value-spread"]
    assert (r.price, r.price_date, r.data_date) == (150.0, date(2026, 10, 30), date(2026, 10, 30))
    assert (r.policy_version, r.method_version) == (policy.version, METHOD_VERSION)
    assert r.deciles_refresh_id == deciles.refresh_id
    # $150 on a value of $127.68 ($133.37 under 0.9, the runway return held to year 19): 1.175
    # × the value, above 1.15
    assert r.value is not None and r.value == pytest.approx(127.675, abs=0.005)
    assert (r.price_to_value, r.designation) == (150.0 / r.value, "above")
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
        "one_year": expected.one_year,
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
    # year 3's 10% fading to the belief over years 4 to 8, the last of them on the belief exactly;
    # the return holds through year 6, whose next growth is the last above the belief, then fades
    # to the terminal return in year 20 (spec 2026-11-09 6.3)
    growth = GrowthPath(5_900e6, (0.12, 0.10), 0.063, 20, fade_years=5)
    charge = Charge(rr["value"], im["terminal_roic"], 0.09, 0.03, hold=6)
    assert im["charge"]["hold_years"] == hold_years(growth) == 6
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
        expected.ten_year, terminal_roic(expected.ten_year, "Wide", policy), 0.09, 0.03, hold=6
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
    # at a ROIC equal to r growth adds no value at any belief, the payout floor being off (spec
    # 2026-11-09 6.1), so no belief reaches the price
    assert im["value_by_roic"]["0.09"] == pytest.approx(VALUE_AT_R)
    assert im["implied_by_roic"]["0.09"] is None
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
        "step-series-disagree",  # net income 50% a year against EPS 12% and 10%
        "roic-on-n-years",  # the ROIC
        "growth-above-return",  # a year that pays out less than nothing
        "margin-flag",
        "large-nri",
        "consensus-basis-unknown",  # FMP's consensus names no basis
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
    # a 2% marginal return: the charge uses r, and with no floor growth then adds no value at
    # all, since the charge pays for the earnings growth (MGCO has no consensus revenue)
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
    # years 1 and 2 reinvest more than they earn, so they pay out less than nothing
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
    # with no consensus revenue the charge pays for the earnings growth: year 1 pays for year 2's
    # 50%, year 2 for year 3's; year 3 pays for year 4's faded 41.3%, below the return
    assert above.sentence == (
        "In year 1 the charge pays for 50.0% of growth at a return of 43.1%, so the year pays out "
        "less than nothing: the owner funds the growth. 1 more such year."
    )
    assert r.value is not None and r.value > 0
    assert "growth-above-return" not in codes(value_company(mg_inputs, deciles, policy, TODAY))


def test_the_mature_growth_charge_intermediates(policy: Policy, deciles: Deciles) -> None:
    # consensus revenue up 8% then 7% beside net income up 12% then 10%: the charge pays for the
    # revenue growth, the margin change above it rides free (spec 2026-11-09 6.2)
    inputs = with_revenue(engine_companies.mature_growth_inputs(), (24_000e6, 25_920e6, 27_734.4e6))
    r = value_company(inputs, deciles, policy, TODAY)
    im = r.intermediates
    path, charge = route_mature_growth._rebuilt(im, policy)
    ch = im["charge"]
    assert ch["hold_years"] == hold_years(path) == charge.hold == 6
    assert len(ch["return_by_year"]) == im["runway"] == 20
    assert ch["return_by_year"][-1] == pytest.approx(im["terminal_roic"])
    assert ch["return_by_year"][0] == pytest.approx(im["runway_return"]["value"])
    assert ch["return_by_year"][5] == ch["return_by_year"][0]  # held through year 6
    runway, terminal = im["runway_return"]["value"], im["terminal_roic"]
    assert ch["return_by_year"][6] == pytest.approx(runway + (terminal - runway) / 14)
    assert ch["return_by_year"] == pytest.approx(list(return_by_year(charge, 20)))
    assert len(ch["growth_by_year"]) == im["runway"]
    assert ch["growth_by_year"][-1] == pytest.approx(policy.terminal_growth)
    # years 2 and 3 the revenue steps, then the fade from 7% to the 6.3% belief over years 4 to 8
    assert ch["growth_by_year"][:7] == pytest.approx(
        [0.08, 0.07, 0.0686, 0.0672, 0.0658, 0.0644, 0.063]
    )
    assert ch["revenue_steps"] == list(path.revenue_steps)
    assert ch["revenue_steps"] == [pytest.approx(0.08), pytest.approx(0.07)]
    assert im["growth_rates"][:2] == [pytest.approx(0.12), pytest.approx(0.10)]  # the earnings
    assert "one_year" in im["runway_return"]
    growth = GrowthPath(5_900e6, (0.12, 0.10), 0.063, 20, 5, revenue_steps=(0.08, 0.07))
    assert im["value_total"] == pytest.approx(
        value_at_belief(growth, Charge(runway, terminal, 0.09, 0.03, hold=6))
    )
    # charging the revenue growth, not the earnings growth, is worth more here
    plain = value_company(engine_companies.mature_growth_inputs(), deciles, policy, TODAY)
    assert plain.value is not None and r.value is not None and r.value > plain.value
    assert plain.intermediates["charge"]["revenue_steps"] == [None, None]
    assert result_from_json(result_to_json(r)) == r


def test_growth_above_return_says_the_owner_funds_the_growth(
    policy: Policy, deciles: Deciles
) -> None:
    # consensus revenue up 50% a year, above the 43.1% marginal return, while net income grows 12%
    # then 10%: years 1 and 2 pay for revenue growth they cannot fund
    revenue = (24_000e6, 36_000e6, 54_000e6)
    r = value_company(
        with_revenue(engine_companies.mature_growth_inputs(), revenue), deciles, policy, TODAY
    )
    above = next(f for f in r.flags if f.code == "growth-above-return")
    assert "pays out less than nothing: the owner funds the growth" in above.sentence
    assert above.sentence == (
        "In year 1 the charge pays for 50.0% of revenue growth at a return of 43.1%, so the year "
        "pays out less than nothing: the owner funds the growth. 1 more such year."
    )
    # a single such year names no more
    single = with_revenue(engine_companies.mature_growth_inputs(), (24_000e6, 36_000e6, 39_600e6))
    flags = value_company(single, deciles, policy, TODAY).flags
    above = next(f for f in flags if f.code == "growth-above-return")
    assert above.sentence.endswith("the owner funds the growth.")
    # no revenue mean for fiscal 2028: year 2's h is net income's 50% step, so "of growth"
    i = engine_companies.mature_growth_inputs()
    base, second, third = with_revenue(i, (24_000e6, 36_000e6, 39_600e6)).annual_estimates
    rows = (base, replace(second, revenue=None, net_income=1.5 * base.net_income), third)
    flags = value_company(replace(i, annual_estimates=rows), deciles, policy, TODAY).flags
    above = next(f for f in flags if f.code == "growth-above-return")
    assert above.sentence.startswith("In year 1 the charge pays for 50.0% of growth at ")
    plain = value_company(engine_companies.mature_growth_inputs(), deciles, policy, TODAY)
    assert codes(plain) == ["value-spread"]


def _charge_off(i: CompanyInputs) -> CompanyInputs:
    """``i`` with invested capital at or below zero in every year: the runway charge is off."""
    negative = tuple(
        replace(y, total_current_liabilities=3 * (y.total_current_assets or 0))
        for y in i.capital_years
    )
    return replace(i, capital_years=negative)


def test_a_runway_override_starts_the_fade_even_with_the_charge_off(
    policy: Policy, deciles: Deciles
) -> None:
    inputs = _charge_off(engine_companies.mature_growth_inputs())
    assert value_company(inputs, deciles, policy, TODAY).intermediates["charge_off"] is True
    r = value_company(inputs, deciles, policy, TODAY, judged(("return.runway", 0.20)))
    ch = r.intermediates["charge"]
    assert ch["return_by_year"][0] == pytest.approx(0.20)
    assert r.intermediates["charge_off"] is False
    # held through year 6, then faded to the Wide cap the measured return leaves as the terminal
    assert ch["hold_years"] == 6 and ch["return_by_year"][5] == pytest.approx(0.20)
    assert ch["return_by_year"][6] == pytest.approx(0.20 + (0.13 - 0.20) / 14)
    assert ch["return_by_year"][-1] == r.intermediates["terminal_roic"] == 0.13


def test_a_reprice_rebuilds_the_same_charge(policy: Policy, deciles: Deciles) -> None:
    inputs = with_revenue(engine_companies.mature_growth_inputs(), (24_000e6, 25_920e6, 27_734.4e6))
    r = value_company(inputs, deciles, policy, TODAY)
    stored = result_from_json(result_to_json(r))  # from the intermediates alone
    moved = reprice(stored, 200.0, date(2026, 11, 2), policy)
    assert moved.value == r.value
    assert moved.intermediates["charge"] == r.intermediates["charge"]
    fresh = value_company(replace(inputs, price=200.0), deciles, policy, TODAY)
    assert moved.intermediates["implied_growth"] == fresh.intermediates["implied_growth"]
    assert moved.intermediates["implied_by_roic"] == fresh.intermediates["implied_by_roic"]
    # the solve moves the belief alone: the hold and the revenue steps stay those of the row's own
    # path at its belief, so the value at the implied growth on that charge is the price
    implied = moved.intermediates["implied_growth"]
    assert implied is not None and implied > 0.10  # above year 3's 10%, so no fade from it
    path, charge = route_mature_growth._rebuilt(moved.intermediates, policy)
    assert charge.hold == 6 and path.revenue_steps == pytest.approx((0.08, 0.07))
    assert hold_years(replace(path, belief=implied)) != charge.hold
    at_price = value_at_belief(replace(path, belief=implied), charge) / 1_000e6
    assert at_price == pytest.approx(200.0, rel=1e-6)


def test_the_heavy_capex_sentence_names_an_override_as_the_start(
    policy: Policy, deciles: Deciles
) -> None:
    i = engine_companies.mature_growth_inputs()
    assert i.trailing is not None
    heavy = replace(i, trailing=replace(i.trailing, cfo=6_000e6, capex=-4_000e6))  # 66.7%
    base = "Trailing capital spending is 66.7% of operating cash flow, above 50.0%."
    newest = (
        "the newest year's marginal return is 45.7%, on the capital added in fiscal 2025. The "
        "stored years end at fiscal 2025, so a return on a spending surge still under way is the "
        "agent's judgment: `return.runway`."
    )
    mechanical = value_company(heavy, deciles, policy, TODAY)
    [sentence] = [f.sentence for f in mechanical.flags if f.code == "heavy-capex"]
    assert sentence == (
        f"{base} The charge's return starts at 43.1%, the five-year marginal; {newest}"
    )
    r = value_company(heavy, deciles, policy, TODAY, judged(("return.runway", 0.214)))
    [sentence] = [f.sentence for f in r.flags if f.code == "heavy-capex"]
    assert "starts at 21.4%, the agent's override; the five-year marginal is 43.1%" in sentence
    assert sentence == (
        f"{base} The charge's return starts at 21.4%, the agent's override; the five-year "
        f"marginal is 43.1%; {newest}"
    )


def test_a_step_override_keeps_the_other_step_s_series_note(
    policy: Policy, deciles: Deciles
) -> None:
    # net income up 50% a year against EPS up 12% then 10%: both steps disagree
    i = engine_companies.mature_growth_inputs()
    base, second, third = i.annual_estimates
    inputs = replace(
        i,
        annual_estimates=(
            base,
            replace(second, net_income=1.50 * base.net_income),
            replace(third, net_income=1.50 * 1.50 * base.net_income),
        ),
    )
    mechanical = value_company(inputs, deciles, policy, TODAY)
    [note] = [f.sentence for f in mechanical.flags if f.code == "step-series-disagree"]
    assert note == (
        "Step 2 reads 50.0% on net income and 12.0% on EPS: the two consensus series imply "
        "different share counts (1.0B and 1.3B against the diluted count 1.0B); step 3 reads "
        "50.0% on net income and 10.0% on EPS: the two consensus series imply different share "
        "counts (1.3B and 1.8B against the diluted count 1.0B). The path is on net income; "
        "`path.step_2` and `path.step_3` decide."
    )
    r = value_company(inputs, deciles, policy, TODAY, judged(("path.step_2", 0.20)))
    [note] = [f.sentence for f in r.flags if f.code == "step-series-disagree"]
    assert note == (
        "Step 3 reads 50.0% on net income and 10.0% on EPS: the two consensus series imply "
        "different share counts (1.3B and 1.8B against the diluted count 1.0B). The path is on "
        "net income; `path.step_3` decides."
    )
    both = judged(("path.step_2", 0.20), ("path.step_3", 0.15))
    assert "step-series-disagree" not in codes(value_company(inputs, deciles, policy, TODAY, both))


def test_value_spread_leaves_out_the_ten_year_value(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # invested capital $10 bn at each year end to 2020, then up $2 bn a year to $20 bn in 2025;
    # NOPAT $3 bn a year to 2020, then up $0.09 bn a year: a 5% marginal return, floored at r, and
    # a 25.1% ten-year aggregate, so the ten-year value lies above the first three
    capital = [10e9] * 6 + [12e9, 14e9, 16e9, 18e9, 20e9]  # the balance sheets of 2015 to 2025
    nopat = [3e9] * 6 + [3e9 + 0.09e9 * k for k in range(1, 6)]
    years = tuple(
        _capital_year(2015 + k, n, ic) for k, (n, ic) in enumerate(zip(nopat, capital, strict=True))
    )
    inputs = replace(mg_inputs, capital_years=years)
    im = value_company(inputs, deciles, policy, TODAY).intermediates
    assert im["runway_return"]["used"] == "floor" and im["roic"]["aggregate"] == pytest.approx(
        0.2508
    )
    by_roic = im["value_by_roic"]
    first_three = [by_roic["runway"], by_roic["0.15"], by_roic["0.09"]]
    low, high = min(first_three), max(first_three)
    assert by_roic["ten-year"] > high
    # at a return of r the value does not move with the runway: only the ROIC spread can fire
    assert max(im["value_by_runway"].values()) == pytest.approx(min(im["value_by_runway"].values()))
    # the first three span 51.8% and the ten-year value would make it 78.9%: at a 60% threshold
    # the flag does not fire; at 40% the first three fire it alone, on their own range
    assert (high - low) / low < 0.60 < (by_roic["ten-year"] - low) / low
    wide = replace(policy, value_spread_flag=0.60)
    assert "value-spread" not in codes(value_company(inputs, deciles, wide, TODAY))
    narrow = replace(policy, value_spread_flag=0.40)
    r = value_company(inputs, deciles, narrow, TODAY)
    [spread] = [f for f in r.flags if f.code == "value-spread"]
    assert spread.sentence.startswith(f"The value ranges from {low:,.2f} to {high:,.2f} ")


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
    assert im["moat"] == "Wide" and im["terminal_roic"] == 0.13 and im["runway"] == 20
    assert im["runway_return"]["used"] == "three-year"
    assert im["runway_return"]["value"] == pytest.approx(0.1825, abs=1e-4)
    assert im["epv_total"] == pytest.approx(3_300e6 / 0.09)
    assert im["epv"] == pytest.approx(3.30 / 0.09)  # a share, as the screen's EPV column
    # 3% growth paid for at a return that fades from 18.25% from year 1, a hold of 0, to 13% in
    # year 20 and the terminal ($44.71 with 18.25% held for 19 years); the one-stage value at 13%
    # was $42.31
    runway_return = im["runway_return"]["value"]
    assert im["stable_growth_total"] == pytest.approx(stable_dcf(3_300e6, runway_return, 0.13, 20))
    assert im["stable_growth"] == pytest.approx(43.849, abs=1e-3)
    ch = im["charge"]
    assert ch["hold_years"] == 0 and ch["revenue_steps"] == [None, None]
    assert ch["growth_by_year"] == [policy.terminal_growth] * 20
    assert ch["return_by_year"][0] == pytest.approx(runway_return + (0.13 - runway_return) / 20)
    assert ch["return_by_year"][-1] == 0.13 and len(ch["return_by_year"]) == 20
    assert im["median_margin"] == pytest.approx(0.20) and im["ttm_margin"] == pytest.approx(0.20)
    assert im["eps"] == {"reported": 3.40, "clean": pytest.approx(3.30), "forward": None}
    assert im["multiples"]["pe_forward"] is None
    er = im["expected_return"]
    assert er["growth"] == pytest.approx(0.03)
    assert er["income"] == pytest.approx((1_500e6 + 500e6) / 40_000e6)
    assert r.levels == levels_for(r.value, "Wide", policy)
    assert (r.price_to_value, r.designation) == designation_for(
        40.0, r.value, policy.designation_edges
    )
    by_name = {i.name: i for i in r.inputs}
    assert {"net_income_ttm", "aggregate_roic", "terminal_roic", "moat_class", "belief"} <= set(
        by_name
    )
    assert by_name["runway_years"].value == 20 and "ntm_net_income" not in by_name
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


def test_mature_stable_zeroes_the_charge_like_the_growth_route(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # capital sums to zero or below and the moat is None: no charge in years 1 to 4, the
    # terminal's charge at r in year 5 and the terminal, so the value sits above EPV
    negative = tuple(
        replace(y, total_current_liabilities=3 * (y.total_current_assets or 0))
        for y in ms_inputs.capital_years
    )
    inputs = replace(ms_inputs, capital_years=negative, moat_score=None)
    r = value_company(inputs, deciles, policy, TODAY)
    im = r.intermediates
    assert "roic-unavailable" not in codes(r) and im["roic"]["aggregate"] is None
    assert "ten-year-roic-unavailable" in codes(r)  # the shown ten-year figure, its own flag
    zeroed = next(f for f in r.flags if f.code == "charge-zeroed")
    assert zeroed.sentence == (
        "The marginal return is not usable and average invested capital sums to zero or below "
        "over the last 3 ROIC years, so the runway charge is zero; the terminal still charges "
        "at 9.0%."
    )
    assert im["moat"] == "None" and im["runway"] == 5
    assert im["terminal_roic"] == policy.required_return
    assert im["stable_growth_total"] == pytest.approx(stable_dcf(3_300e6, 0.09, 0.09, 5, off=True))
    assert r.value == pytest.approx(40.382, abs=1e-3) and r.value > im["epv"]
    assert im["epv_total"] == pytest.approx(3_300e6 / 0.09)


def test_mature_stable_raises_the_return_floored_flag(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # operating income at a tenth: the three-year return of 1.8% floors at r, and the route
    # charges at it, so the flag shows as on the growth route; charged at r in every year, the
    # value is EPV whatever the moat
    poor = tuple(
        replace(y, operating_income=(y.operating_income or 0) / 10) for y in ms_inputs.capital_years
    )
    for moat_score in (None, ms_inputs.moat_score):
        inputs = replace(ms_inputs, capital_years=poor, moat_score=moat_score)
        r = value_company(inputs, deciles, policy, TODAY)
        im = r.intermediates
        assert im["runway_return"]["used"] == "floor" and "return-floored" in codes(r)
        [note] = [i.note for i in r.inputs if i.name == "runway_return"]
        assert note == "floored at the required return; the three-year was 1.8%"
        assert im["terminal_roic"] == policy.required_return
        assert r.value == pytest.approx(im["epv"])


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
    r = value_company(none, deciles, policy, TODAY)
    assert_refused(r, "no positive trailing earnings")
    # the keys of the refusal for a trailing loss (spec 2026-11-06 9), with no E to read
    assert set(r.intermediates) == REFUSED_STABLE_KEYS and r.intermediates["e_trailing"] is None


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
    assert set(gr) == CROSS_CHECK_KEYS
    assert r.value == r.intermediates["stable_growth"]  # the headline stays the stable value
    assert r.levels == levels_for(r.value, "Wide", policy)
    assert result_from_json(result_to_json(r)) == r
    # the cross-check is the value the growth route reaches on the same company, with its implied
    # growth at the price: none at $40, below the $48.43 the growth route gives at -50% a year
    assert inputs.trailing is not None
    for price, implied in ((40.0, None), (120.0, pytest.approx(0.0815, abs=1e-4))):
        priced = replace(inputs, price=price)
        r = value_company(priced, deciles, policy, TODAY)
        gr = r.intermediates["growth_route"]
        c = Context(priced, inputs.trailing, price, 1_000e6, policy, TODAY)
        own = route_mature_growth.value_mature_growth(c)
        assert isinstance(own, Valued) and own.value != r.value
        im = own.intermediates
        assert gr["value_per_share"] == own.value == pytest.approx(108.08, abs=0.01)
        assert gr["implied_growth"] == im["implied_growth"] == implied
        assert gr["runway_return"] == r.intermediates["runway_return"]
        for key in CROSS_CHECK_KEYS - {"value_per_share", "refusal"}:
            assert gr[key] == im[key], key


def test_mature_stable_names_the_charge_s_start_and_the_basis_note(
    ms_inputs: CompanyInputs, mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # capital spending at two thirds of operating cash flow, and a non-recurring gain of $0.40 a
    # share, 11.8% of trailing EPS; the growth company's consensus, whose two series disagree
    assert ms_inputs.trailing is not None
    base, second, third = mg_inputs.annual_estimates
    disagree = (
        base,
        replace(second, net_income=1.50 * base.net_income),
        replace(third, net_income=1.50 * 1.50 * base.net_income),
    )
    inputs = replace(
        _with_consensus(ms_inputs, replace(mg_inputs, annual_estimates=disagree)),
        trailing=replace(ms_inputs.trailing, capex=-3_000e6),
        gf_eps_without_nri=3.00,
    )
    r = value_company(inputs, deciles, policy, TODAY)
    assert codes(r) == ["heavy-capex", "large-nri", "consensus-basis-unknown"]
    heavy, _, basis = r.flags
    assert heavy.sentence == (
        "Trailing capital spending is 66.7% of operating cash flow, above 50.0%. The charge's "
        "return starts at 18.3%, the three-year aggregate; the newest year's marginal return is "
        "18.3%, on the capital added in fiscal 2025. The stored years end at fiscal 2025, so a "
        "return on a spending surge still under way is the agent's judgment: `return.runway`."
    )
    assert basis.sentence == (
        "The non-recurring gap is $0.40 a share, 11.8% of trailing EPS. FMP's consensus names no "
        "basis, so whether the NTM anchor and the path carry such items is unknown; a report that "
        "reads the filing decides, through `earnings.nri_gap`, and on Mature Growth "
        "`earnings.ntm`."
    )
    # the cross-check reads the two series, and its notes stay off the stable row (method 6.5)
    assert r.intermediates["growth_route"]["refusal"] is None


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


# The intermediates of a Mature Stable row refused for its trailing earnings (spec 2026-11-06 9).
REFUSED_STABLE_KEYS = {
    "e_trailing",
    "nri_gap",
    "eps",
    "shares",
    "moat",
    "growth_route",
    "price_facts",
}


def _loss_making(stable: CompanyInputs) -> CompanyInputs:
    """The stable company with a trailing loss of $500m, $0.50 a share."""
    assert stable.trailing is not None
    t = replace(stable.trailing, net_income=-500e6, eps_diluted=-0.50)
    return replace(stable, trailing=t)


def test_no_positive_trailing_earnings_keeps_the_cross_check(
    ms_inputs: CompanyInputs, mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # spec 2026-11-06 13.5: the growth company's consensus gives a positive anchor; at $120 the
    # cross-check has an implied growth
    inputs = replace(_loss_making(_with_consensus(ms_inputs, mg_inputs)), price=120.0)
    r = value_company(inputs, deciles, policy, TODAY)
    assert_refused(r, "no positive trailing earnings")
    assert r.phase.phase == "Mature Stable"
    im = r.intermediates
    assert set(im) == REFUSED_STABLE_KEYS
    assert im["e_trailing"] == pytest.approx(-500e6 - 0.10 * 1_000e6)
    assert im["nri_gap"] == pytest.approx(0.10)
    assert im["eps"] == {"reported": -0.50, "clean": pytest.approx(-0.60), "forward": None}
    assert (im["shares"], im["moat"]) == (1_000e6, "Wide")
    gr = im["growth_route"]
    assert set(gr) == CROSS_CHECK_KEYS and gr["refusal"] is None
    assert gr["value_per_share"] > 0
    assert gr["implied_growth"] is not None
    # the trailing loss does not reach the cross-check: it is the valued row's at the same price
    valued = replace(_with_consensus(ms_inputs, mg_inputs), price=120.0)
    assert gr == value_company(valued, deciles, policy, TODAY).intermediates["growth_route"]


def test_the_cross_check_moves_with_the_price_on_the_refusal(
    ms_inputs: CompanyInputs, mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    inputs = replace(_loss_making(_with_consensus(ms_inputs, mg_inputs)), price=120.0)
    r = value_company(inputs, deciles, policy, TODAY)
    assert r.price is not None
    stored = result_from_json(result_to_json(r))  # from the intermediates alone
    moved = reprice(stored, 2 * r.price, date(2026, 11, 2), policy)
    gr, moved_gr = r.intermediates["growth_route"], moved.intermediates["growth_route"]
    assert moved_gr["implied_growth"] != gr["implied_growth"]
    assert moved.value is None and moved.refusal == r.refusal
    # only the implied growth moves, to what a fresh valuation at that price gives
    assert {k: v for k, v in moved_gr.items() if k != "implied_growth"} == {
        k: v for k, v in gr.items() if k != "implied_growth"
    }
    fresh = value_company(replace(inputs, price=2 * r.price), deciles, policy, TODAY)
    assert moved.intermediates == fresh.intermediates
    [price_input] = [i for i in moved.inputs if i.name == "price"]
    assert (moved.price, price_input.value) == (2 * r.price, 2 * r.price)


def test_a_refused_cross_check_on_a_refused_row_survives_a_reprice(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # spec 2026-11-06 13.5: the stable company has no consensus, so the anchor refuses too
    r = value_company(_loss_making(ms_inputs), deciles, policy, TODAY)
    assert_refused(r, "no positive trailing earnings")
    assert set(r.intermediates) == REFUSED_STABLE_KEYS
    assert r.intermediates["growth_route"] == {"refusal": "incomplete NTM consensus"}
    stored = result_from_json(result_to_json(r))
    moved = reprice(stored, 80.0, date(2026, 11, 2), policy)
    assert moved.intermediates == r.intermediates
    assert moved.value is None and moved.refusal == r.refusal and moved.price == 80.0


def _capital_year(year: int, nopat: float, capital: float) -> CapitalYear:
    """A year whose invested capital is all net property and equipment, taxed at 25%."""
    return CapitalYear(year, nopat / 0.75, 0.25, 0.0, 0.0, 0.0, 0.0, 0.0, capital, 0.0, 0.0, 0.0)


def test_mature_stable_reads_the_shared_terminal(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # a Wide stable row whose marginal return is above 13% and ten-year aggregate 10% charges at
    # a return fading from 28% to 13% in year 20 and after: invested capital is $10 bn at each
    # year end to
    # 2023 and $20 bn at the ends of 2024 and 2025; NOPAT is $0.87 bn a year and $3.67 bn in
    # 2025. Average capital rises $10 bn from 2020 to 2025 and NOPAT $2.8 bn, a 28% marginal
    # return; $11.5 bn of NOPAT over $115 bn of average capital is 10%.
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
    assert r.intermediates["terminal_roic"] == 0.13 and im["runway"] == 20
    assert im["stable_growth_total"] == pytest.approx(stable_dcf(3_300e6, 0.28, 0.13, 20))
    assert im["stable_growth"] == pytest.approx(45.478, abs=1e-3)  # 46.788 held to year 19


def test_mature_stable_narrow_moat_charges_its_own_return_for_ten_years(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # a Narrow moat: the terminal return is r and the runway 10 years, so the charge's return
    # fades from the three-year 18.25% to r in year 10; the value sits above EPV, which the
    # one-stage formula at r gave such a row before
    narrow = replace(ms_inputs, moat_score=policy.moat_narrow_min)
    r = value_company(narrow, deciles, policy, TODAY)
    im = r.intermediates
    assert im["moat"] == "Narrow" and im["runway"] == 10
    assert im["terminal_roic"] == policy.required_return
    runway_return = im["runway_return"]["value"]
    assert runway_return == pytest.approx(0.1825, abs=1e-4)
    assert im["stable_growth_total"] == pytest.approx(stable_dcf(3_300e6, runway_return, 0.09, 10))
    assert im["stable_growth"] == pytest.approx(39.123, abs=1e-3)  # 40.377 held to year 9
    assert im["epv"] == pytest.approx(36.667, abs=1e-3)
    years = next(i for i in r.inputs if i.name == "runway_years")
    assert (years.tag, years.value, years.note) == ("RULE", 10, "Narrow moat")
    assert r.levels == levels_for(r.value, "Narrow", policy)


def test_mature_stable_wide_charge_off_pays_out_in_full_through_the_runway(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # a Wide moat whose capital sums to zero or below: no charge in years 1 to 19, the 13% cap in
    # year 20 and the terminal; the largest lift the rule gives, 38% above EPV
    negative = tuple(
        replace(y, total_current_liabilities=3 * (y.total_current_assets or 0))
        for y in ms_inputs.capital_years
    )
    r = value_company(replace(ms_inputs, capital_years=negative), deciles, policy, TODAY)
    im = r.intermediates
    assert "charge-zeroed" in codes(r) and im["moat"] == "Wide" and im["runway"] == 20
    assert im["runway_return"]["used"] == "off" and im["terminal_roic"] == 0.13
    assert im["stable_growth_total"] == pytest.approx(stable_dcf(3_300e6, 0.13, 0.13, 20, off=True))
    assert im["stable_growth"] == pytest.approx(50.671, abs=1e-3)
    assert r.value / im["epv"] == pytest.approx(1.382, abs=1e-3)


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


def test_a_decline_row_takes_its_route(
    decline_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Decline is no longer refused "route not built yet": the run-off values it
    (``test_route_decline.py``), behind the shared guards."""
    r = value_company(decline_inputs, deciles, policy, TODAY)
    assert (r.phase.phase, r.route, r.refusal) == ("Decline", "decline", None)
    names = [i.name for i in r.inputs]
    assert names[:5] == ["statements", "price", "shares_diluted", "next_earnings", "closes"]
    assert r.inputs[0].value == 5 and r.inputs[0].note == "fiscal 2021 to 2025"
    assert r.intermediates["price_facts"] == asdict(price_facts(decline_inputs.closes, TODAY))
    assert_refused(
        value_company(replace(decline_inputs, trailing=None), deciles, policy, TODAY),
        "no trailing figures",
    )


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


def test_a_start_up_row_takes_its_route_and_an_unclassified_row_is_refused(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """A Start-up row is the Start-up route's refusal with its figures
    (``test_route_start_up.py``): here, revenue zero three years back on a company that never made
    an operating profit (an established one is never a Start-up, method 3.5) and no peers, so the
    requirement carries its reason. An unclassified row keeps the classifier's reason."""
    series = mg_inputs.series
    losses = tuple(replace(fy, operating_income=-1.0) for fy in series)
    start_up = (*losses[:-4], replace(losses[-4], revenue=0.0), *losses[-3:])
    r = value_company(replace(mg_inputs, series=start_up), deciles, policy, TODAY)
    assert (r.phase.phase, r.route, r.refusal) == (
        "Start-up",
        "start-up",
        "Start-up: no value by design",
    )
    assert (r.value, r.levels, r.price_to_value, r.designation) == (None,) * 4
    assert r.intermediates["requirement"]["reason"] == "no target margin: 0 mature peers"
    names = [i.name for i in r.inputs]
    assert names[:5] == ["statements", "price", "shares_diluted", "next_earnings", "closes"]
    assert r.valid_until == mg_inputs.next_earnings
    assert result_from_json(result_to_json(r)) == r
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


# --- The value outside the business and the share count (spec 2026-11-09 8) --------------------

VALUED = {
    "mature-growth": engine_companies.mature_growth_inputs,
    "mature-stable": engine_companies.mature_stable_inputs,
    "revenue-growth": engine_companies.high_growth_inputs,
    "decline": engine_companies.decline_inputs,
}
# The solves each valued route runs on the price; the cross-check's implied growth among them.
SOLVES = {
    "mature-growth": ("implied_growth", "implied_growth_by_runway", "implied_by_roic"),
    "mature-stable": ("growth_route",),
    "revenue-growth": ("implied_growth", "implied_margin", "growth_route"),
    "decline": ("implied_decline_rate",),
}
# The figures each valued route reads at the price as it is.
AS_PRICED = {
    "mature-growth": ("multiples", "growth_share"),
    "mature-stable": ("multiples",),
    "revenue-growth": ("multiples", "growth_share"),
    "decline": ("multiples",),
}
# The value a share each valued route divides by the count: Decline's before the floor and the
# weighting, which a count also moves through the floor's NCAV a share.
PER_SHARE = {"revenue-growth": "value_per_share", "decline": "going_concern_per_share"}


def test_value_outside_adds_to_the_value_and_targets_the_business_price(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 13.4: $12 a share outside the business on the route's value; the levels and the
    designation read the sum, the implied growth solves to the price less the $12, and the values
    by runway and by return each add it."""
    inputs = engine_companies.mature_growth_inputs()
    plain = value_company(inputs, deciles, policy, TODAY)
    outside = value_company(inputs, deciles, policy, TODAY, judged(("value.outside", 12.0)))
    assert plain.value is not None and plain.price is not None
    assert outside.value is not None and outside.levels is not None
    assert outside.value == pytest.approx(plain.value + 12.0)
    assert outside.levels == levels_for(outside.value, outside.intermediates["moat"], policy)
    assert (outside.price_to_value, outside.designation) == designation_for(
        plain.price, outside.value, policy.designation_edges
    )
    im = outside.intermediates
    assert im["outside_value_per_share"] == 12.0
    assert "outside_value_per_share" not in plain.intermediates
    # the intermediates' value a share stays the business's, so the drawer's arithmetic reproduces
    assert im["value_per_share"] == plain.intermediates["value_per_share"]
    path, charge = route_mature_growth._rebuilt(im, policy)
    target = (plain.price - 12.0) * plain.intermediates["shares"]
    assert im["implied_growth"] == pytest.approx(implied_growth(target, path, charge, hi=2.0))
    for key in ("value_by_runway", "value_by_roic"):
        pairs = zip(im[key].values(), plain.intermediates[key].values(), strict=True)
        assert all(v == pytest.approx(w + 12.0) for v, w in pairs if w is not None), key


@pytest.mark.parametrize("route", sorted(VALUED))
def test_every_valued_route_adds_the_outside_value(
    route: str, policy: Policy, deciles: Deciles
) -> None:
    """Each valued route's value a share is its own plus the figure (here a quarter of the
    price). Every solve on the price targets the business's share of it, as a row priced at the
    price less the figure solves; the multiples and the growth share read the price as it is,
    and the expected return's repricing term the sum against the price. A reprice moves the row
    as a fresh valuation at the new price."""
    inputs = VALUED[route]()
    assert inputs.price is not None
    figure = inputs.price / 4
    plain = value_company(inputs, deciles, policy, TODAY)
    outside = value_company(inputs, deciles, policy, TODAY, judged(("value.outside", figure)))
    business = replace(inputs, price=inputs.price - figure)
    at_business = value_company(business, deciles, policy, TODAY)
    assert outside.route == plain.route == route
    assert plain.value is not None and outside.value is not None
    assert outside.value == pytest.approx(plain.value + figure)
    assert outside.levels == levels_for(outside.value, outside.intermediates["moat"], policy)
    assert outside.intermediates["value_per_share"] == plain.intermediates["value_per_share"]
    for key in SOLVES[route]:
        assert outside.intermediates[key] == at_business.intermediates[key], key
    for key in AS_PRICED[route]:
        assert outside.intermediates[key] == plain.intermediates[key], key
    er, found = outside.intermediates["expected_return"], plain.intermediates["expected_return"]
    horizon = policy.repricing_horizon_years
    assert (er["income"], er["growth"]) == (found["income"], found["growth"])
    assert er["repricing"] == pytest.approx(math.log(outside.value / inputs.price) / horizon)
    if route == "revenue-growth":
        pairs = zip(
            outside.intermediates["value_by_margin"].values(),
            plain.intermediates["value_by_margin"].values(),
            strict=True,
        )
        assert all(v == pytest.approx(w + figure) for v, w in pairs)
    moved = reprice(result_from_json(result_to_json(outside)), 2 * inputs.price, TODAY, policy)
    fresh = value_company(
        replace(inputs, price=2 * inputs.price),
        deciles,
        policy,
        TODAY,
        judged(("value.outside", figure)),
    )
    assert moved.value == outside.value and moved.levels == outside.levels
    assert (moved.price_to_value, moved.designation) == (fresh.price_to_value, fresh.designation)
    for key in (*SOLVES[route], *AS_PRICED[route], "expected_return"):
        assert moved.intermediates[key] == fresh.intermediates[key], key


def test_an_outside_value_above_the_price_values_the_row(policy: Policy, deciles: Deciles) -> None:
    """A stake worth more than the price, the business priced below nothing: the row values at
    the sum, the multiples and the expected return read the price, and the solve on the business's
    share of the price finds no decline rate that reaches it."""
    inputs = engine_companies.decline_inputs()
    assert inputs.price == 3.0
    plain = value_company(inputs, deciles, policy, TODAY)
    r = value_company(inputs, deciles, policy, TODAY, judged(("value.outside", 12.0)))
    assert plain.value is not None and r.value == pytest.approx(plain.value + 12.0)
    assert r.designation == "well-below"
    assert r.intermediates["multiples"] == plain.intermediates["multiples"]
    repricing = r.intermediates["expected_return"]["repricing"]
    assert repricing == pytest.approx(math.log(r.value / 3.0) / policy.repricing_horizon_years)
    assert r.intermediates["implied_decline_rate"] is None
    moved = reprice(r, 2.0, TODAY, policy)
    assert moved.intermediates["implied_decline_rate"] is None and moved.designation == "well-below"


@pytest.mark.parametrize(
    ("route", "reason"),
    [
        ("mature-growth", "value not positive under the reinvestment charge"),
        ("mature-stable", "value not positive under the reinvestment charge"),
        ("revenue-growth", "value not positive under the reinvestment charge"),
        ("decline", "value not positive in the run-off"),
    ],
)
def test_an_outside_value_that_sinks_the_value_refuses(
    route: str, reason: str, policy: Policy, deciles: Deciles
) -> None:
    """The sum decides: a figure that takes it to zero or below refuses the row with the route's
    own reason, the value side kept with the figure beside it."""
    inputs = VALUED[route]()
    plain = value_company(inputs, deciles, policy, TODAY)
    r = value_company(inputs, deciles, policy, TODAY, judged(("value.outside", -1000.0)))
    assert_refused(r, reason)
    assert r.intermediates["value_per_share"] == plain.intermediates["value_per_share"]
    assert r.intermediates["outside_value_per_share"] == -1000.0
    assert [x.name for x in r.inputs if x.tag == "JUDGMENT"] == ["value.outside"]


@pytest.mark.parametrize("figure", [200.0, -100.0])
@pytest.mark.parametrize("route", ["mature-growth", "revenue-growth"])
def test_the_value_spread_reads_the_business_before_the_outside_value(
    route: str, figure: float, policy: Policy, deciles: Deciles
) -> None:
    """The flag speaks of the business's sensitivity to its own inputs, so it reads the values by
    return, runway and margin before the figure is added (method 14.4). A large stake would narrow
    the spread or silence it; a large debt would push the lowest value to zero or below and
    silence it, or on the revenue-growth route trip the unbounded sentence. The row still values at
    the sum, and the stored maps keep the figure added."""
    inputs = VALUED[route]()
    plain = value_company(inputs, deciles, policy, TODAY)
    outside = value_company(inputs, deciles, policy, TODAY, judged(("value.outside", figure)))
    assert plain.value is not None and outside.value == pytest.approx(plain.value + figure)
    spread = [f for f in plain.flags if f.code == "value-spread"]
    assert spread  # the plain row's flag fires, so there is a state to keep
    assert [f for f in outside.flags if f.code == "value-spread"] == spread
    for key in ("value_by_runway", "value_by_roic", "value_by_margin"):
        found = plain.intermediates.get(key, {})
        stored = outside.intermediates.get(key, {})
        pairs = zip(stored.values(), found.values(), strict=True)
        assert all(v == pytest.approx(w + figure) for v, w in pairs if w is not None), key


def test_the_ntm_net_income_entry_stays_on_the_reported_count(
    policy: Policy, deciles: Deciles
) -> None:
    """No DATA entry carries an agent's figure under the vendor's provenance (method 14.4): under
    a `shares.diluted` override the ``ntm_net_income`` entry is the consensus NTM EPS × the
    reported count, cited to the estimates, while the intermediates hold the NTM net income on
    the count the route used. With no reported count the entry has no figure."""
    inputs = engine_companies.mature_growth_inputs()
    assert inputs.shares_diluted is not None
    count = inputs.shares_diluted * 1.06
    plain = value_company(inputs, deciles, policy, TODAY)
    more = value_company(inputs, deciles, policy, TODAY, judged(("shares.diluted", count)))

    def entry(r: ValuationResult, name: str) -> Any:
        [found] = [x for x in r.inputs if x.name == name]
        return found

    found = entry(more, "ntm_net_income")
    assert found.tag == "DATA" and found.provenance == inputs.provenance["estimates_quarter"]
    assert found.value == pytest.approx(entry(more, "ntm_eps").value * inputs.shares_diluted)
    assert found == entry(plain, "ntm_net_income")
    assert more.intermediates["ntm_net_income"] == pytest.approx(
        entry(more, "ntm_eps").value * count
    )
    none = value_company(
        replace(inputs, shares_diluted=None),
        deciles,
        policy,
        TODAY,
        judged(("shares.diluted", count)),
    )
    assert none.value is not None and entry(none, "ntm_net_income").value is None


def test_shares_diluted_replaces_the_count_everywhere(policy: Policy, deciles: Deciles) -> None:
    """Spec 13.4: a count raised 6% raises NTM net income 6% with it, the consensus EPS times the
    count, so the Mature Growth value a share, which rests on that EPS, stands; the equity routes
    divide by the count. The JUDGMENT entry stands in place of the reported count's."""
    inputs = engine_companies.mature_growth_inputs()
    plain = value_company(inputs, deciles, policy, TODAY)
    count = plain.intermediates["shares"] * 1.06
    more = value_company(inputs, deciles, policy, TODAY, judged(("shares.diluted", count)))
    assert plain.intermediates["sbc_basis"] == "includes-sbc"  # no SBC a share to move
    assert more.intermediates["shares"] == pytest.approx(plain.intermediates["shares"] * 1.06)
    assert more.intermediates["ntm_net_income"] == pytest.approx(
        plain.intermediates["ntm_net_income"] * 1.06
    )
    assert more.value == pytest.approx(plain.value)
    assert current_reading(plain, "shares.diluted") == pytest.approx(plain.intermediates["shares"])
    assert current_reading(more, "shares.diluted") == count
    cited = [(x.name, x.tag, x.value) for x in more.inputs if "shares" in x.name]
    assert cited == [("shares.diluted", "JUDGMENT", count)]
    for route, key in PER_SHARE.items():
        found = value_company(VALUED[route](), deciles, policy, TODAY)
        shares = found.intermediates["shares"]
        doubled = value_company(
            VALUED[route](), deciles, policy, TODAY, judged(("shares.diluted", 2 * shares))
        )
        assert doubled.intermediates["shares"] == 2 * shares
        assert doubled.intermediates["equity"] == found.intermediates["equity"]
        assert doubled.intermediates[key] == pytest.approx(found.intermediates[key] / 2), route


def test_the_start_up_route_reads_the_count_and_no_outside_value(
    policy: Policy, deciles: Deciles
) -> None:
    """On a Start-up row the count sets the per-share figure, the cash floor, which halves when
    the count doubles; the requirement is a total on the market cap, which no count moves. The
    route reads no outside value: the rule refuses it, and the engine's reading is none."""
    inputs = engine_companies.start_up_inputs()
    plain = value_company(inputs, deciles, policy, TODAY)
    shares = plain.intermediates["shares"]
    doubled = value_company(inputs, deciles, policy, TODAY, judged(("shares.diluted", 2 * shares)))
    assert doubled.refusal == plain.refusal == "Start-up: no value by design"
    assert doubled.route == "start-up" and doubled.intermediates["shares"] == 2 * shares
    assert doubled.intermediates["cash_floor"] == pytest.approx(
        plain.intermediates["cash_floor"] / 2
    )
    assert doubled.intermediates["requirement"] == plain.intermediates["requirement"]
    assert check_override(
        "value.outside", 12.0, "start-up", policy, ["filing"], "lasting", None
    ) == ("refused-route", "the Start-up route does not read value.outside")
    assert current_reading(plain, "value.outside") is None


def test_a_share_count_override_passes_the_share_guard(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """The count is read before the guard: an agent's count values a row with none reported."""
    none = replace(mg_inputs, shares_diluted=None)
    assert_refused(value_company(none, deciles, policy, TODAY), "no diluted share count")
    r = value_company(none, deciles, policy, TODAY, judged(("shares.diluted", 1_000e6)))
    assert r.value == value_company(mg_inputs, deciles, policy, TODAY).value


# --- Reprice ------------------------------------------------------------------------------------


def test_reprice_keeps_value_changes_designation(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    assert r.value is not None and r.levels is not None
    low = r.levels.buy * 0.9  # 0.675 × the value: Wide's buy level is 0.75 × the value
    p = reprice(r, low, date(2026, 11, 2), policy)
    assert (p.value, p.levels, p.valid_until, p.data_date) == (
        r.value,
        r.levels,
        r.valid_until,
        r.data_date,
    )
    assert (p.price, p.price_date, p.designation) == (low, date(2026, 11, 2), "below")
    assert p.price_to_value == low / r.value and r.designation == "above"
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
    for inputs in (mg_inputs, ms_inputs, _with_consensus(ms_inputs, mg_inputs)):
        r = value_company(inputs, deciles, policy, TODAY)
        assert r.price is not None and r.price_date is not None
        stored = result_from_json(result_to_json(r))
        assert reprice(stored, r.price, r.price_date, policy) == r


def test_reprice_mature_stable(ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy) -> None:
    r = value_company(ms_inputs, deciles, policy, TODAY)
    p = reprice(r, 80.0, date(2026, 11, 2), policy)
    fresh = value_company(replace(ms_inputs, price=80.0), deciles, policy, TODAY)
    assert p.value == r.value and p.designation == fresh.designation == "well-above"
    assert p.price_to_value == fresh.price_to_value
    assert p.intermediates["multiples"] == fresh.intermediates["multiples"]
    assert p.intermediates["expected_return"] == fresh.intermediates["expected_return"]
    # a refused cross-check has no implied growth to move
    assert p.intermediates["growth_route"] == {"refusal": "incomplete NTM consensus"}


def test_reprice_moves_the_cross_check_implied_growth(
    ms_inputs: CompanyInputs, mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    inputs = _with_consensus(ms_inputs, mg_inputs)
    r = value_company(inputs, deciles, policy, TODAY)
    stored = result_from_json(result_to_json(r))  # from the intermediates alone
    gr = stored.intermediates["growth_route"]
    assert gr["implied_growth"] is None  # at $40, below what any growth in the solve's range gives
    # at a price equal to the cross-check's value, the implied growth is the belief
    at_value = reprice(stored, gr["value_per_share"], date(2026, 11, 2), policy)
    moved = at_value.intermediates["growth_route"]
    assert moved["implied_growth"] == pytest.approx(gr["belief"]["rate"], abs=1e-6)
    assert {k: v for k, v in moved.items() if k != "implied_growth"} == {
        k: v for k, v in gr.items() if k != "implied_growth"
    }
    assert at_value.value == r.value == r.intermediates["stable_growth"]
    # and a reprice reaches what a fresh valuation at that price gives
    p = reprice(stored, 120.0, date(2026, 11, 2), policy)
    fresh = value_company(replace(inputs, price=120.0), deciles, policy, TODAY)
    assert p.intermediates["growth_route"] == fresh.intermediates["growth_route"]
    assert p.intermediates["growth_route"]["implied_growth"] is not None


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
    decline_inputs: CompanyInputs,
    deciles: Deciles,
    policy: Policy,
) -> None:
    """The drawer reproduces a repriced row: its price input is the fresh quote, as of the new
    price date and stamped as the quote was; its source and every other input stay. A refusal's
    price input moves too."""
    day = date(2026, 11, 2)
    observed = datetime(2026, 11, 2, 21, 0, tzinfo=UTC)
    entered = datetime(2026, 11, 2, 21, 5, tzinfo=UTC)
    for inputs in (mg_inputs, ms_inputs, young_growth_inputs, decline_inputs):
        r = value_company(inputs, deciles, policy, TODAY)
        assert r.route is not None
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
    refused = value_company(replace(decline_inputs, tax_rate_latest=None), deciles, policy, TODAY)
    p = reprice(refused, 65.0, day, policy, observed_at=observed, entered_at=entered)
    assert p.refusal == "no statutory tax rate"
    [price] = [i for i in p.inputs if i.name == "price"]
    assert (p.price, price.value) == (65.0, 65.0)
    assert price.provenance == Provenance("FMP quote", day, observed, entered)


def test_reprice_moves_the_designation_and_leaves_the_levels(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """Spec 13.3: on a value of 100, a price refresh from 70 to 120 moves the word from below to
    above; the levels stay."""
    r = value_company(mg_inputs, deciles, policy, TODAY)
    at_100 = replace(r, value=100.0, levels=levels_for(100.0, "Wide", policy))
    before = reprice(at_100, 70.0, date(2026, 11, 2), policy)
    after = reprice(before, 120.0, date(2026, 11, 3), policy)
    assert (before.price_to_value, before.designation) == (0.7, "below")
    assert (after.price_to_value, after.designation) == (1.2, "above")
    assert after.levels == before.levels == levels_for(100.0, "Wide", policy)
    assert after.value == 100.0


def test_the_designation_reads_the_policy_edges(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    """At 1.175 × the value the row is above under the default edges; with the third edge at 1.20
    it is near, at valuation and at a price refresh alike."""
    assert value_company(mg_inputs, deciles, policy, TODAY).designation == "above"
    wide = replace(policy, fair_band=(0.85, 1.20))
    r = value_company(mg_inputs, deciles, wide, TODAY)
    assert r.designation == "near"
    assert r.price is not None and r.price_date is not None
    assert reprice(r, r.price, r.price_date, policy).designation == "above"


def test_reprice_a_refusal_moves_only_the_price(policy: Policy) -> None:
    r = refusal_result("X", "no trailing figures", policy, date(2026, 10, 31), price=10.0)
    p = reprice(r, 12.0, date(2026, 11, 2), policy)
    assert p == replace(r, price=12.0, price_date=date(2026, 11, 2))
    with pytest.raises(ValueError, match="positive"):
        reprice(r, 0.0, date(2026, 11, 2), policy)


def test_result_cites_the_settings_hash(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    assert r.settings_hash == EMPTY_SETTINGS_HASH and r.method_version == "fairband-mechanical/1.1"
    custom = apply_overlay(policy, {"required_return": 0.1})
    valued = value_company(mg_inputs, deciles, custom, TODAY)
    assert valued.settings_hash == custom.settings_hash != EMPTY_SETTINGS_HASH
    refused = value_company(replace(mg_inputs, price=None), deciles, custom, TODAY)
    assert refused.refusal is not None and refused.settings_hash == custom.settings_hash
    # a reprice does not revalue: the result keeps the hash it was valued under, whatever policy
    # the caller passes
    assert valued.price is not None
    assert reprice(valued, valued.price, TODAY, policy).settings_hash == custom.settings_hash


def test_expected_pads_the_rates_at_the_terminal_rate() -> None:
    # route_steps.expected: two rates, a horizon of 4, padded with the terminal 3%
    im = {"dividend_yield": 0.01, "net_buyback_yield": 0.0}
    er = expected(100.0, 120.0, im, (0.1, 0.05), 4, 0.03)
    assert er is not None
    assert er["growth"] == pytest.approx((1.1 * 1.05 * 1.03 * 1.03) ** (1 / 4) - 1)
    assert er["repricing"] == pytest.approx(math.log(1.2) / 4)
    assert er["income"] == 0.01
    # a horizon shorter than the rates reads only the first ones
    short = expected(100.0, 120.0, im, (0.1, 0.05, 0.5), 2, 0.03)
    assert short is not None and short["growth"] == pytest.approx((1.1 * 1.05) ** (1 / 2) - 1)


def test_long_horizon_never_raises_on_a_short_runway(
    mg_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    # every runway 4 gives the Mature Growth path three rates; a horizon of 6 is padded, not refused
    custom = apply_overlay(
        policy,
        {"repricing_horizon_years": 6, "runway_years": {"None": 4, "Narrow": 4, "Wide": 4}},
    )
    r = value_company(mg_inputs, deciles, custom, TODAY)
    assert r.value is not None and r.price is not None and r.refusal is None
    er = r.intermediates["expected_return"]
    assert er["repricing"] == pytest.approx(math.log(r.value / r.price) / 6)


def test_repricing_horizon_moves_the_expected_return(
    ms_inputs: CompanyInputs, deciles: Deciles, policy: Policy
) -> None:
    base = value_company(ms_inputs, deciles, policy, TODAY).intermediates["expected_return"]
    five = value_company(
        ms_inputs, deciles, apply_overlay(policy, {"repricing_horizon_years": 5}), TODAY
    ).intermediates["expected_return"]
    assert five["repricing"] == pytest.approx(base["repricing"] * 3 / 5)
