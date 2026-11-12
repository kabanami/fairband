"""A company in another currency (spec 2026-11-10, 7.2, 7.3 and 11): the policy's rates restated
by the inflation differential, the route on the price and the market cap in the currency, the
value and the levels translated to USD at the rate, the reprice at a new rate and the override
ranges in the currency. The companies are ``support.engine_companies``' restated in SEK at 8.0
(``in_sek``, ``fx_inputs``)."""

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest
from support.engine_companies import (
    decline_inputs,
    fx_inputs,
    high_growth_inputs,
    in_sek,
    mature_growth_inputs,
    mature_stable_inputs,
    start_up_inputs,
    young_growth_inputs,
)

from fairband.engine.classifier import Deciles
from fairband.engine.flags import basis_unknown_flag, nri_flag
from fairband.engine.overrides import Override, OverrideTag, check_input, range_text
from fairband.engine.review import review_company
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.route_steps import millions
from fairband.engine.sensitivity import sensitivity_grid
from fairband.engine.types import ValuationResult, money_of, rated
from fairband.policy import Policy, in_currency
from fairband.policy.inflation import load_inflation_table

TODAY = date(2026, 10, 31)
NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)
VALUED = {
    "mature-growth": mature_growth_inputs,
    "mature-stable": mature_stable_inputs,
    "high-growth": high_growth_inputs,
    "young-growth": young_growth_inputs,
    "decline": decline_inputs,
}
CURRENCY_KEYS = {"currency", "fx_rate", "fx_date", "value_in_currency", "inflation_differential"}


def inputs_of(r: ValuationResult) -> dict[str, Any]:
    return {i.name: i for i in r.inputs}


def flag_codes(r: ValuationResult) -> list[str]:
    return [f.code for f in r.flags]


# --- the rates in the currency (spec 7.3, 11.1) ---


def test_in_currency_restates_the_five_rates(policy: Policy) -> None:
    local = in_currency(policy, 0.02)
    assert local.required_return == pytest.approx(0.11180)
    assert local.terminal_growth == pytest.approx(0.05060)
    assert local.inflation_addition == pytest.approx(0.04040)
    assert local.return_without_goodwill_cap == pytest.approx(1.25 * 1.02 - 1)
    for found, base in zip(local.base_rates, policy.base_rates, strict=True):
        assert found.sales_p90_5y == pytest.approx((1 + base.sales_p90_5y) * 1.02 - 1)
        assert (found.upper_musd, found.median, found.label) == (
            base.upper_musd,
            base.median,
            base.label,
        )
    assert local.version == policy.version and local.hash == policy.hash
    assert local.settings_hash == policy.settings_hash
    assert local.wide_terminal_roic_cap == pytest.approx(0.11180 + policy.wide_terminal_roic_spread)
    # the flag thresholds and the margin bounds are not restated
    assert local.long_runway_growth_flag == policy.long_runway_growth_flag
    assert local.implied_margin_bounds == policy.implied_margin_bounds
    assert in_currency(policy, 0.0) is policy


@pytest.mark.parametrize(
    ("code", "differential", "r", "g"),
    [
        ("TWD", -0.00509, 0.08445, 0.02476),
        ("BRL", 0.01097, 0.10195, None),
        ("KZT", 0.04034, 0.13398, None),
    ],
)
def test_in_currency_on_the_packaged_table(
    policy: Policy, code: str, differential: float, r: float, g: float | None
) -> None:
    """Spec 11.1's figures on the packaged inflation table, to three decimals of a percent: TWD's
    d −0.509%, r 8.445% and g_T 2.476%; BRL's d +1.097%, r 10.195%; KZT's d +4.034%, r 13.398%."""
    d = load_inflation_table().differential(code)
    assert d is not None and d == pytest.approx(differential, abs=1e-5)
    local = in_currency(policy, d)
    assert local.required_return == pytest.approx(r, abs=1e-5)
    if g is not None:
        assert local.terminal_growth == pytest.approx(g, abs=1e-5)


# --- the translation (spec 7.2, 11.2) ---


def test_a_currency_row_values_in_the_currency_and_translates(
    policy: Policy, deciles: Deciles
) -> None:
    """FXCO: SEK at 8.0, price USD 50, market cap USD 5,000 m, d 0.02."""
    r = value_company(fx_inputs(), deciles, policy, TODAY)
    usd = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    assert r.route == "mature-growth" and r.value is not None and r.levels is not None
    assert r.price == 50.0 and r.price_date == date(2026, 10, 31)
    im = r.intermediates
    assert (im["currency"], im["fx_rate"], im["fx_date"]) == ("SEK", 8.0, "2026-10-31")
    assert im["inflation_differential"] == 0.02
    assert im["value_in_currency"] == pytest.approx(r.value * 8.0)
    assert r.levels.buy == pytest.approx(r.value * (1 - policy.margin_of_safety["Wide"]))
    assert r.levels.trim == pytest.approx(r.value * policy.trim_multiple)
    assert r.price_to_value == pytest.approx(50.0 / r.value)
    # the route read a price of 400 in SEK: its P/E is the price in SEK over the EPS in SEK
    assert im["multiples"]["pe_reported"] == pytest.approx(400.0 / (5.30 * 8.0))
    found = inputs_of(r)
    assert found["eps_ttm"].unit == "SEK a share" and found["revenue_ttm"].unit == "SEK"
    assert (found["price"].value, found["price"].unit) == (50.0, "USD")
    assert (found["market_cap"].value, found["market_cap"].unit) == (
        pytest.approx(40_000e6),
        "SEK",
    )
    assert (found["fx_rate"].value, found["fx_rate"].unit) == (8.0, "SEK per USD")
    assert found["fx_rate"].tag == "DATA"
    assert found["fx_rate"].provenance.source == "FMP historical-price-eod/light USDSEK"
    assert found["fx_rate"].provenance.as_of == date(2026, 10, 31)
    d = found["inflation_differential"]
    assert (d.value, d.unit, d.tag, d.kind) == (0.02, "ratio", "RULE", "rule")
    assert d.note == (
        "SEK 4.040% against USD 2.000%, the IMF World Economic Outlook October 2026 means of 2027 "
        "to 2031"
    )
    assert d.provenance.source.startswith("IMF World Economic Outlook, October 2026")
    # the route ran on the restated policy
    assert found["required_return"].value == pytest.approx(0.1118)
    assert found["terminal_growth"].value == pytest.approx(0.0506)
    # the USD row carries none of it
    assert not {"fx_rate", "inflation_differential"} & set(inputs_of(usd))
    assert not CURRENCY_KEYS & set(usd.intermediates)
    assert "fx-stale" not in flag_codes(r)


@pytest.mark.parametrize("phase", sorted(VALUED))
def test_every_route_values_in_the_currency(policy: Policy, deciles: Deciles, phase: str) -> None:
    """A company restated in SEK at 8.0 with the differential 0.02 has the USD value of the same
    company in USD under the restated policy, its route's value in SEK eight times it; the levels
    are the policy's on the USD value and the designation reads the USD price against it."""
    usd = VALUED[phase]()
    local = in_currency(policy, 0.02)
    restated = value_company(usd, deciles, local, TODAY)
    r = value_company(in_sek(usd), deciles, policy, TODAY)
    assert r.route == restated.route and r.value is not None and restated.value is not None
    assert r.value == pytest.approx(restated.value)
    assert r.intermediates["value_in_currency"] == pytest.approx(restated.value * 8.0)
    assert r.levels is not None and restated.levels is not None
    assert r.levels.buy == pytest.approx(restated.levels.buy)
    assert r.levels.fair_high == pytest.approx(restated.levels.fair_high)
    assert (r.price, r.designation) == (usd.price, restated.designation)
    assert r.price_to_value == pytest.approx(restated.price_to_value)
    assert set(r.intermediates) == set(restated.intermediates) | CURRENCY_KEYS
    assert inputs_of(r)["required_return"].value == pytest.approx(
        inputs_of(restated)["required_return"].value
    )


@pytest.mark.parametrize("phase", sorted(VALUED))
def test_a_currency_at_the_dollar_s_inflation_values_as_the_dollar_row(
    policy: Policy, deciles: Deciles, phase: str
) -> None:
    """With no differential the rates are the policy's own: the row in SEK has the USD row's
    value, levels and designation (the translation undoes the restatement exactly at 8.0)."""
    usd = value_company(VALUED[phase](), deciles, policy, TODAY)
    r = value_company(in_sek(VALUED[phase](), differential=0.0), deciles, policy, TODAY)
    assert r.value == pytest.approx(usd.value)
    assert r.levels is not None and usd.levels is not None
    for level in ("buy", "fair_low", "fair_high", "trim"):
        assert getattr(r.levels, level) == pytest.approx(getattr(usd.levels, level)), level
    assert r.designation == usd.designation
    assert inputs_of(r)["inflation_differential"].value == 0.0


def test_a_start_up_row_s_requirement_is_in_the_currency(policy: Policy, deciles: Deciles) -> None:
    """SUCO in SEK: the market cap, EV_price and the year-10 revenue the price needs in SEK, eight
    times the USD row's under the restated policy; still the refusal by design."""
    usd = start_up_inputs()
    restated = value_company(usd, deciles, in_currency(policy, 0.02), TODAY)
    r = value_company(in_sek(usd), deciles, policy, TODAY)
    assert r.refusal == restated.refusal == "Start-up: no value by design"
    assert r.route == "start-up" and r.price == 20.0
    im, base = r.intermediates, restated.intermediates
    assert im["market_cap"] == pytest.approx(2_000.0 * 8.0)
    assert im["requirement"]["ev_price"] == pytest.approx(base["requirement"]["ev_price"] * 8.0)
    assert im["requirement"]["revenue_y10"] == pytest.approx(
        base["requirement"]["revenue_y10"] * 8.0
    )
    assert im["cash_floor"] == pytest.approx(base["cash_floor"] * 8.0)
    assert (im["currency"], im["fx_rate"]) == ("SEK", 8.0) and "value_in_currency" not in im
    assert inputs_of(r)["market_cap"].unit == "SEK" and inputs_of(r)["cash"].unit == "SEK"


def test_a_decline_row_s_levels_are_in_usd(policy: Policy, deciles: Deciles) -> None:
    r = value_company(in_sek(decline_inputs()), deciles, policy, TODAY)
    assert r.route == "decline" and r.value is not None and r.levels is not None
    assert r.intermediates["value_in_currency"] == pytest.approx(r.value * 8.0)
    assert r.intermediates["value_per_share"] == pytest.approx(r.value * 8.0)
    assert r.levels.buy == pytest.approx(r.value * (1 - policy.margin_of_safety["None"]))
    assert inputs_of(r)["depreciation"].unit == "SEK"


def test_the_sales_class_reads_revenue_in_usd(policy: Policy, deciles: Deciles) -> None:
    """Trailing revenue of 8,000 m in SEK is USD 1,000 m: the belief's sales class is the one of
    the USD row with revenue of 1,000 m, $700-1,250 Mn, not the 8,000 m one."""
    sek = fx_inputs()
    assert sek.trailing is not None
    r = value_company(
        replace(sek, trailing=replace(sek.trailing, revenue=8_000e6)), deciles, policy, TODAY
    )
    usd = mature_growth_inputs()
    assert usd.trailing is not None
    dollar = value_company(
        replace(usd, trailing=replace(usd.trailing, revenue=1_000e6)), deciles, policy, TODAY
    )
    assert r.intermediates["belief"]["sales_class"] == "$700-1,250 Mn"
    assert dollar.intermediates["belief"]["sales_class"] == "$700-1,250 Mn"
    # the class's median plus the inflation addition restated: 5.3% + 4.04%
    assert r.intermediates["belief"]["rate"] == pytest.approx(0.053 + 0.0404)


def test_the_held_rate_cap_is_restated(policy: Policy, deciles: Deciles) -> None:
    """The revenue-growth route's cap on the held rate is the sales class's 90th percentile in the
    currency: HGCO's $7,000-12,000 Mn class, 15%, is 17.3% in SEK at d 0.02."""
    r = value_company(in_sek(high_growth_inputs()), deciles, policy, TODAY)
    assert r.intermediates["path"]["sales_class"] == "$7,000-12,000 Mn"
    assert r.intermediates["path"]["cap"] == pytest.approx(1.15 * 1.02 - 1)


# --- the reprice at a new rate (spec 7.2, 11.2) ---


def test_reprice_moves_the_usd_value_with_the_rate(policy: Policy, deciles: Deciles) -> None:
    r = value_company(fx_inputs(), deciles, policy, TODAY)
    assert r.value is not None and r.levels is not None
    day = date(2026, 11, 2)
    moved = reprice(r, 55.0, day, policy, fx_rate=8.5, fx_date=day, fx_observed_at=NOW)
    assert moved.value is not None and moved.levels is not None
    assert moved.intermediates["value_in_currency"] == r.intermediates["value_in_currency"]
    assert moved.value == pytest.approx(r.intermediates["value_in_currency"] / 8.5)
    assert moved.levels.trim == pytest.approx(r.levels.trim * moved.value / r.value)
    assert moved.levels.buy == pytest.approx(r.levels.buy * moved.value / r.value)
    assert moved.price_to_value == pytest.approx(55.0 / moved.value)
    assert (moved.intermediates["fx_rate"], moved.intermediates["fx_date"]) == (8.5, "2026-11-02")
    # the at-price figures read the price in SEK, 55 × 8.5
    assert moved.intermediates["multiples"]["pe_reported"] == pytest.approx(467.5 / 42.4)
    # the rate input moves as the price input does: its value, its date and the quote's stamp
    rate, was = inputs_of(moved)["fx_rate"], inputs_of(r)["fx_rate"]
    assert (rate.value, rate.provenance.as_of, rate.provenance.observed_at) == (8.5, day, NOW)
    # the close is the pair's quote now, not the history's: the source names it
    assert was.provenance.source == "FMP historical-price-eod/light USDSEK"
    assert rate.provenance.source == "FMP quote USDSEK"
    assert inputs_of(moved)["price"].value == 55.0
    kept = reprice(r, 55.0, date(2026, 11, 12), policy)  # no fresh pair quote
    assert kept.value == r.value and kept.levels == r.levels
    assert kept.intermediates["fx_rate"] == 8.0
    assert "fx-stale" in flag_codes(kept)  # 12 days past the stored 2026-10-31
    stale = next(f for f in kept.flags if f.code == "fx-stale")
    assert stale.word == "Rate stale"
    assert stale.sentence == (
        "The newest close of USDSEK on file is of 2026-10-31, 12 days before the price date "
        "2026-11-12."
    )
    assert "fx-stale" not in flag_codes(reprice(r, 55.0, date(2026, 11, 5), policy))
    assert "fx-stale" not in flag_codes(
        reprice(kept, 55.0, date(2026, 11, 12), policy, fx_rate=8.4, fx_date=date(2026, 11, 12))
    )


def _refused_for_its_target_margin() -> CompanyInputs:
    """HGCO with no peers: the revenue-growth refusal that keeps its rebuild keys and the margin
    the price needs."""
    return replace(high_growth_inputs(), peers=())


def _refused_for_its_earnings() -> CompanyInputs:
    """MSCO at a trailing loss, with MGCO's consensus and at $80: the Mature Stable refusal that
    keeps the growth-route cross-check and its implied growth at the price."""
    stable, growth = mature_stable_inputs(), mature_growth_inputs()
    assert stable.trailing is not None
    return replace(
        stable,
        price=80.0,
        trailing=replace(stable.trailing, net_income=-100e6),
        quarter_estimates=growth.quarter_estimates,
        annual_estimates=growth.annual_estimates,
    )


REPRICED = {
    **VALUED,
    "revenue-growth-refused": _refused_for_its_target_margin,
    "mature-stable-refused": _refused_for_its_earnings,
}
_RATE_KEYS = ("fx_rate", "fx_date")


def _at_price(r: ValuationResult) -> dict[str, Any]:
    """The intermediates but the rate's two, which say when the rate was read."""
    return {k: v for k, v in r.intermediates.items() if k not in _RATE_KEYS}


@pytest.mark.parametrize("case", sorted(REPRICED))
def test_reprice_in_the_currency_matches_the_engine(
    policy: Policy, deciles: Deciles, case: str
) -> None:
    """Every valued route, the revenue-growth refusal for its target margin (the margin the price
    needs) and the Mature Stable refusal for its earnings (the cross-check), in SEK at 8.0. At
    the rate it was valued at, a reprice is the engine at the new price: the same value, levels,
    designation and intermediates. At a new rate, 10.0, every figure that moves with the price is
    the one at the same price in SEK, and the value a share is ``value_in_currency`` ÷ 10.0."""
    sek = in_sek(REPRICED[case]())
    assert sek.price is not None
    r = value_company(sek, deciles, policy, TODAY)
    day = date(2026, 11, 2)
    same = reprice(r, sek.price * 1.25, day, policy, fx_rate=8.0, fx_date=day)
    again = value_company(replace(sek, price=sek.price * 1.25), deciles, policy, TODAY)
    assert (same.value, same.levels, same.refusal) == (again.value, again.levels, again.refusal)
    assert same.designation == again.designation
    assert _at_price(same) == _at_price(again)
    moved = reprice(r, sek.price, day, policy, fx_rate=10.0, fx_date=day)
    in_sek_alike = reprice(r, sek.price * 10.0 / 8.0, day, policy, fx_rate=8.0, fx_date=day)
    assert _at_price(moved) == _at_price(in_sek_alike)
    assert moved.intermediates["fx_rate"] == 10.0
    if r.value is None:
        assert (moved.value, moved.levels, moved.refusal) == (None, None, r.refusal)
    else:
        assert moved.value == pytest.approx(r.intermediates["value_in_currency"] / 10.0)
        assert moved.levels is not None and r.levels is not None
        assert moved.levels.buy == pytest.approx(r.levels.buy * 8.0 / 10.0)
        assert moved.price_to_value == pytest.approx(sek.price / moved.value)


def test_reprice_moves_a_start_up_row_s_market_cap_in_the_currency(
    policy: Policy, deciles: Deciles
) -> None:
    """SUCO in SEK at USD 20 and 8.0 is 16,000 in SEK; at USD 25 and 8.5 its market cap is
    2,000 × 25 × 8.5 ÷ 20 = 21,250 in SEK, and the requirement follows."""
    r = value_company(in_sek(start_up_inputs()), deciles, policy, TODAY)
    moved = reprice(r, 25.0, date(2026, 11, 2), policy, fx_rate=8.5, fx_date=date(2026, 11, 2))
    assert moved.intermediates["market_cap"] == pytest.approx(21_250.0)
    assert moved.intermediates["requirement"]["ev_price"] == pytest.approx(
        21_250.0 - moved.intermediates["cash"] + moved.intermediates["debt"]
    )
    assert moved.intermediates["fx_rate"] == 8.5


def test_a_usd_row_reprices_as_before(policy: Policy, deciles: Deciles) -> None:
    """A rate given for a USD row moves nothing: its rate is 1 on every day."""
    r = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    plain = reprice(r, 160.0, date(2026, 11, 2), policy)
    rated = reprice(r, 160.0, date(2026, 11, 2), policy, fx_rate=9.0, fx_date=date(2026, 11, 2))
    assert rated == plain and plain.value == r.value
    assert not CURRENCY_KEYS & set(plain.intermediates)


# --- the guards and the words ---


def test_a_usd_adr_reads_as_a_domestic_row(policy: Policy, deciles: Deciles) -> None:
    """The ADR flag is no ground for refusal: a USD ADR is valued exactly as the domestic row, the
    ADR ratio input apart."""
    usd = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    adr = value_company(
        replace(mature_growth_inputs(), is_adr=True, adr_ratio=5.0), deciles, policy, TODAY
    )
    assert adr.refusal is None and adr.value == usd.value and adr.levels == usd.levels
    assert adr.intermediates == usd.intermediates and adr.flags == usd.flags
    assert [i for i in adr.inputs if i.name != "adr_ratio"] == list(usd.inputs)


def test_the_assembly_s_currency_refusals_stand(policy: Policy, deciles: Deciles) -> None:
    """A refusal for the currency's own reason, its code known and no rate read (assembly's
    ``currency_refused``), carries the intermediate ``currency`` alone: its figures are in that
    currency, and it has no rate, rate date or differential. ``money_of`` gives the code with the
    rate 1.0, a default, and ``rated`` says the row has no rate. An unknown currency carries
    nothing (the controller's ruling of fix round 1)."""
    for code, reason in (
        ("SEK", "no exchange rate for SEK"),
        ("XXX", "no inflation projection for XXX"),
        ("ARS", "ARS: expected inflation 12.1% above the 10% bound"),
    ):
        inputs = replace(
            in_sek(mature_growth_inputs()),
            currency=code,
            refusal=reason,
            fx_date=None,
            fx_rate=1.0,
            currency_refused=True,
        )
        r = value_company(inputs, deciles, policy, TODAY)
        assert r.refusal == reason and r.phase.phase == "Mature Growth"
        assert CURRENCY_KEYS & set(r.intermediates) == {"currency"}
        assert r.intermediates["currency"] == code
        assert money_of(r) == (1.0, code) and not rated(r)
        assert "fx_rate" not in inputs_of(r)
    unknown = replace(
        in_sek(mature_growth_inputs()),
        currency="unknown",
        refusal="reporting currency unknown",
        fx_date=None,
        fx_rate=1.0,
    )
    r = value_company(unknown, deciles, policy, TODAY)
    assert not CURRENCY_KEYS & set(r.intermediates) and money_of(r) == (1.0, "USD")


def test_a_refusal_before_the_currency_step_carries_no_currency(
    policy: Policy, deciles: Deciles
) -> None:
    """A row refused for its tax rate, a step before the currency's, in a currency with no rate:
    assembly does not mark it ``currency_refused``, so it carries nothing, as before."""
    inputs = replace(
        in_sek(mature_growth_inputs()),
        currency="ARS",
        refusal="no statutory tax rate for AR 2025",
        fx_date=None,
        fx_rate=1.0,
    )
    r = value_company(inputs, deciles, policy, TODAY)
    assert not CURRENCY_KEYS & set(r.intermediates) and not rated(r)


def test_a_reprice_leaves_a_currency_refusal_without_a_rate(
    policy: Policy, deciles: Deciles
) -> None:
    """A row refused for its currency carries no rate, so a reprice moves only its price, even
    with a pair's quote given: it neither reads nor writes a rate."""
    inputs = replace(
        in_sek(mature_growth_inputs()),
        currency="ARS",
        refusal="ARS: expected inflation 12.1% above the 10% bound",
        fx_date=None,
        fx_rate=1.0,
        currency_refused=True,
    )
    r = value_company(inputs, deciles, policy, TODAY)
    moved = reprice(r, 55.0, date(2026, 11, 3), policy, fx_rate=1400.0, fx_date=date(2026, 11, 3))
    assert moved.intermediates == r.intermediates and moved.flags == r.flags
    assert (moved.price, moved.refusal) == (55.0, r.refusal) and not rated(moved)
    # an override's range on such a row names its currency, unscaled: there is no rate
    rate, code = money_of(r)
    assert check_input(
        "earnings.ntm", 1_500.0, "mature-growth", policy, fx_rate=rate, currency=code
    ) == (
        "refused-unit",
        "earnings.ntm takes above 0 to 1,000 ARS a share",
    )


def test_a_stale_rate_is_noted(policy: Policy, deciles: Deciles) -> None:
    inputs = replace(fx_inputs(), fx_date=date(2026, 10, 20), fx_stale=True)
    r = value_company(inputs, deciles, policy, TODAY)
    assert r.value is not None and flag_codes(r)[-1] == "fx-stale"
    assert r.flags[-1].sentence == (
        "The newest close of USDSEK on file is of 2026-10-20, 11 days before the price date "
        "2026-10-31."
    )


def test_an_override_s_entry_names_the_currency(policy: Policy, deciles: Deciles) -> None:
    """The JUDGMENT entry of a money override carries the row's currency in its unit."""
    override = Override(1, "earnings.ntm", 50.0, "agent", "claude-opus-5-5", NOW, "guided")
    overrides: dict[OverrideTag, Override] = {"earnings.ntm": override}
    r = value_company(fx_inputs(), deciles, policy, TODAY, overrides)
    assert inputs_of(r)["earnings.ntm"].unit == "SEK a share"
    usd = value_company(mature_growth_inputs(), deciles, policy, TODAY, overrides)
    assert inputs_of(usd)["earnings.ntm"].unit == "USD a share"


def test_the_review_s_bridge_and_the_sensitivity_grid_are_in_usd(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-10 7.6: the bridge's steps and the grid's cells are USD a share, as the value
    is, while the engine's reading an override replaces stays in SEK."""
    mechanical = value_company(fx_inputs(), deciles, policy, TODAY)
    assert mechanical.value is not None
    belief = Override(1, "growth.belief", 0.08, "agent", "claude-opus-5-5", NOW, "guided")
    review = review_company(fx_inputs(), deciles, policy, TODAY, [belief], mechanical)
    alone = value_company(fx_inputs(), deciles, policy, TODAY, {"growth.belief": belief})
    assert alone.value is not None and review.result.value == alone.value
    assert review.bridge[0].delta == pytest.approx(alone.value - mechanical.value)
    assert alone.intermediates["value_in_currency"] == pytest.approx(alone.value * 8.0)
    grid = sensitivity_grid(
        fx_inputs(),
        deciles,
        policy,
        TODAY,
        {},
        "growth.belief",
        [0.05, 0.08],
        "moat.class",
        ["Narrow", "Wide"],
    )
    assert grid.cells[1][1] == pytest.approx(alone.value)  # FXCO's own moat is Wide


def test_the_dollar_ramp_names_the_currency(policy: Policy, deciles: Deciles) -> None:
    """HGCO at a trailing loss of 15,000 m, larger than its revenue, in SEK: the ramp moves in SEK
    from SEK −120,000.0 million, the figures in SEK; the USD row's sentence says dollars."""
    usd = high_growth_inputs()
    assert usd.trailing is not None
    lossy = replace(usd, trailing=replace(usd.trailing, operating_income=-15_000e6))
    sek = value_company(in_sek(lossy), deciles, policy, TODAY)
    dollar = value_company(lossy, deciles, policy, TODAY)
    [ramp] = [f.sentence for f in sek.flags if f.code == "margin-ramp-in-dollars"]
    assert "income moves in SEK from −SEK 120,000.0 million to the target margin's SEK " in ramp
    assert "dollars" not in ramp
    [ramp] = [f.sentence for f in dollar.flags if f.code == "margin-ramp-in-dollars"]
    assert "income moves in dollars from −$15,000.0 million" in ramp


def test_the_sentences_name_the_currency(policy: Policy) -> None:
    """A money figure a sentence prints is after ``$`` on a USD row and after the code on any
    other."""
    assert millions(-1_234.5e6) == "−$1,234.5 million"
    assert millions(-1_234.5e6, "SEK") == "−SEK 1,234.5 million"
    note = basis_unknown_flag(nri_flag(-0.60, 5.00, policy), -0.60, 5.00, "SEK")
    assert note is not None
    assert note.sentence.startswith("The non-recurring gap is −SEK 0.60 a share, 12.0% of ")


# --- the override ranges (spec 7.3) ---


def test_override_ranges_read_in_the_currency(policy: Policy) -> None:
    """earnings.ntm's range, above 0 to 1,000 USD a share, is above 0 to 32,956 TWD a share at
    32.956 TWD per USD and above 0 to 790 GBP a share at 0.79 GBP per USD: a figure outside the USD
    range but inside the TWD one, and one inside the USD range but outside the GBP one (plan
    review focus 5)."""
    twd = {"fx_rate": 32.956, "currency": "TWD"}
    gbp = {"fx_rate": 0.79, "currency": "GBP"}
    assert check_input("earnings.ntm", 900.0, "mature-growth", policy)[0] == "applied"
    assert check_input("earnings.ntm", 900.0, "mature-growth", policy, **gbp) == (
        "refused-unit",
        "earnings.ntm takes above 0 to 790 GBP a share",
    )
    assert check_input("earnings.ntm", 32_000.0, "mature-growth", policy, **twd)[0] == "applied"
    state, sentence = check_input("earnings.ntm", 33_000.0, "mature-growth", policy, **twd)
    assert state == "refused-unit"
    assert sentence == "earnings.ntm takes above 0 to 32,956 TWD a share"
    assert check_input("earnings.ntm", 1_500.0, "mature-growth", policy)[0] == "refused-unit"
    assert check_input("earnings.ntm", 900.0, "mature-growth", policy)[0] == "applied"
    # a ratio and a count do not move with the rate
    assert check_input("growth.belief", 0.5, "mature-growth", policy, **twd)[0] == "applied"
    assert check_input("shares.diluted", 2e12, "mature-growth", policy, **twd)[0] == (
        "refused-unit"
    )
    state, sentence = check_input("value.outside", -40_000.0, "mature-growth", policy, **twd)
    assert sentence == "value.outside takes −32,956 to 32,956 TWD a share"
    state, sentence = check_input("balance.debt", -1.0, "decline", policy, **twd)
    assert sentence == "balance.debt takes 0 TWD or more"


def test_a_scaled_money_end_is_checked_as_it_is_printed(policy: Policy) -> None:
    """A money end × the rate rounds half up to two decimals before the check and prints the
    decimals it has: earnings.nri_gap's ±100 at 32.956 is ±3,295.6, so 3,295.6 passes and
    3,295.8 is refused with the end it printed; at 0.16478 the end 16.478 is 16.48. A USD end
    is a whole number, as before."""
    twd = {"fx_rate": 32.956, "currency": "TWD"}
    assert check_input("earnings.nri_gap", 3_295.6, "mature-growth", policy, **twd)[0] == "applied"
    assert check_input("earnings.nri_gap", 3_295.8, "mature-growth", policy, **twd) == (
        "refused-unit",
        "earnings.nri_gap takes −3,295.6 to 3,295.6 TWD a share",
    )
    odd = {"fx_rate": 0.16478, "currency": "GBP"}
    assert check_input("earnings.nri_gap", 16.48, "mature-growth", policy, **odd)[0] == "applied"
    assert check_input("earnings.nri_gap", 16.481, "mature-growth", policy, **odd) == (
        "refused-unit",
        "earnings.nri_gap takes −16.48 to 16.48 GBP a share",
    )
    assert check_input("earnings.nri_gap", 100.5, "mature-growth", policy) == (
        "refused-unit",
        "earnings.nri_gap takes −$100 to $100 a share",
    )
    assert range_text(-3_295.6, 3_295.6, "USD a share", currency="TWD") == (
        "−3,295.6 to 3,295.6 TWD a share"
    )


def test_range_text_names_the_currency() -> None:
    assert range_text(0.0, 1_000.0, "USD a share", low_open=True) == "above $0 to $1,000 a share"
    assert range_text(0.0, 1e15, "USD", low_open=True) == "above $0"
    assert (
        range_text(0.0, 32_956.0, "USD a share", low_open=True, currency="TWD")
        == "above 0 to 32,956 TWD a share"
    )
    assert range_text(0.0, 1e15, "USD", low_open=True, currency="TWD") == "above 0 TWD"
