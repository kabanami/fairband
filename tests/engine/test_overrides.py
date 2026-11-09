"""The override rules, the accessor the routes read through, the JUDGMENT inputs and the engine's
reading of each overridable input (spec 2026-11-06 Tier 2, 10.2 to 10.4)."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import get_args

import pytest
from support.engine_companies import (
    decline_inputs,
    fiscal_years,
    high_growth_inputs,
    mature_growth_inputs,
    mature_stable_inputs,
    start_up_inputs,
)

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import (
    BRIDGE_ORDER,
    LABELS,
    TAGS,
    Lifetime,
    Override,
    OverrideTag,
    State,
    check_override,
    current_reading,
    range_text,
    route_of,
)
from fairband.engine.route import value_company
from fairband.engine.route_steps import Context, chosen, judgment_inputs
from fairband.engine.types import Provenance, Route
from fairband.policy import Policy

TODAY = date(2026, 10, 31)
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)


def override(tag: OverrideTag, value: float | str, id: int | None = 7) -> Override:
    return Override(id, tag, value, "agent", "claude-opus-5-5", NOW, "guidance raised")


def checked(
    policy: Policy,
    tag: str,
    value: float | str,
    route: Route,
    evidence: Sequence[str] = ("filing",),
    lifetime: Lifetime = "lasting",
    cap: float | None = None,
) -> tuple[State, str]:
    return check_override(tag, value, route, policy, evidence, lifetime, cap)


def test_check_refuses_a_locked_input(policy: Policy) -> None:
    assert check_override(
        "terminal_growth", 0.04, "mature-growth", policy, ["filing"], "lasting", None
    ) == ("refused-locked", "g_T is a locked input: the terminal growth ceiling")
    assert checked(policy, "required_return", 0.08, "mature-growth") == (
        "refused-locked",
        "r is a locked input: the hurdle rate",
    )
    assert checked(policy, "terminal_return", 0.2, "mature-growth") == (
        "refused-locked",
        "the terminal return follows the moat",
    )
    assert checked(policy, "price", 99.0, "decline") == ("refused-locked", "price is reported data")


def test_check_refuses_a_tag_that_is_not_an_input(policy: Policy) -> None:
    assert checked(policy, "colour", 0.1, "mature-growth") == (
        "refused-not-input",
        "colour is not an input",
    )


def test_check_refuses_a_tag_the_route_does_not_read(policy: Policy) -> None:
    assert checked(policy, "decline.rate", -0.02, "mature-growth") == (
        "refused-route",
        "the Mature Growth route does not read decline.rate",
    )
    assert checked(policy, "growth.belief", 0.08, "revenue-growth") == (
        "refused-route",
        "the revenue-growth route does not read growth.belief",
    )
    assert checked(policy, "path.step_2", 0.1, "mature-stable")[0] == "refused-route"


def test_check_refuses_a_value_outside_its_range(policy: Policy) -> None:
    assert checked(policy, "growth.belief", 0.7, "mature-growth") == (
        "refused-unit",
        "growth.belief takes −20% to 60%",
    )
    assert checked(policy, "capital.sales_to_capital", 11.0, "decline") == (
        "refused-unit",
        "capital.sales_to_capital takes 0.1 to 10",
    )
    assert checked(policy, "earnings.nri_gap", -101.0, "mature-stable") == (
        "refused-unit",
        "earnings.nri_gap takes −$100 to $100 a share",
    )
    assert checked(policy, "earnings.cycle_gap", 101.0, "mature-growth") == (
        "refused-unit",
        "earnings.cycle_gap takes −$100 to $100 a share",
    )


def test_a_range_includes_its_ends(policy: Policy) -> None:
    assert checked(policy, "growth.belief", -0.2, "mature-growth") == ("applied", "")
    assert checked(policy, "growth.belief", 0.6, "mature-growth") == ("applied", "")


def test_check_refuses_a_word_outside_its_words(policy: Policy) -> None:
    assert checked(policy, "moat.class", "Huge", "mature-growth") == (
        "refused-unit",
        "moat.class takes None, Narrow or Wide",
    )
    assert checked(policy, "moat.class", 2.0, "mature-growth")[0] == "refused-unit"
    assert checked(policy, "growth.belief", "high", "mature-growth") == (
        "refused-unit",
        "growth.belief takes −20% to 60%",
    )
    assert checked(policy, "phase", "Mature Growth", "start-up") == ("applied", "")


def test_check_refuses_a_lasting_balance_correction(policy: Policy) -> None:
    assert checked(policy, "balance.debt", 100.0, "decline") == (
        "refused-unit",
        "balance.debt is period-tied only",
    )
    tied = checked(policy, "balance.debt", 100.0, "decline", lifetime="period-tied")
    assert tied == ("applied", "")


def test_check_needs_evidence(policy: Policy) -> None:
    assert checked(policy, "growth.belief", 0.08, "mature-growth", evidence=[]) == (
        "refused-evidence",
        "an override needs evidence",
    )


def test_a_belief_above_the_cap_needs_a_filing_or_a_transcript(policy: Policy) -> None:
    assert (
        check_override(
            "growth.belief", 0.30, "mature-growth", policy, ["finding"], "lasting", 0.25
        )[0]
        == "refused-evidence"
    )
    assert checked(policy, "growth.belief", 0.30, "mature-growth", ["finding"], cap=0.25) == (
        "refused-evidence",
        "a belief above the base rate's 90th percentile needs a filing or a transcript",
    )
    assert check_override(
        "growth.belief", 0.30, "mature-growth", policy, ["transcript"], "lasting", 0.25
    ) == ("applied", "")
    assert checked(policy, "path.hold", 0.30, "revenue-growth", ["url"], cap=0.25) == (
        "refused-evidence",
        "a held rate above the base rate's 90th percentile needs a filing or a transcript",
    )
    at_the_cap = checked(policy, "path.hold", 0.25, "revenue-growth", ["url"], cap=0.25)
    assert at_the_cap == ("applied", "")


def test_the_checks_run_in_the_method_order(policy: Policy) -> None:
    """Locked, not an input, the route, the unit, the evidence: the first rule broken answers."""
    assert checked(policy, "fade_years", 9.0, "decline", evidence=[])[0] == "refused-locked"
    assert checked(policy, "decline.rate", 0.5, "mature-growth", evidence=[])[0] == (
        "refused-route"
    )
    assert checked(policy, "decline.rate", 0.5, "decline", evidence=[])[0] == "refused-unit"


def test_every_tag_has_a_place_in_the_bridge_and_a_range_or_words(policy: Policy) -> None:
    assert sorted(BRIDGE_ORDER) == sorted(get_args(OverrideTag)) == sorted(TAGS)
    for tag, spec in TAGS.items():
        assert spec.tag == tag
        assert (spec.words is None) == (tag in policy.override_ranges), tag
    assert TAGS["phase"].routes == {
        "mature-growth",
        "mature-stable",
        "revenue-growth",
        "decline",
        "start-up",
    }


def test_the_cycle_gap_is_a_mature_tag() -> None:
    """The mid-cycle correction reads where the non-recurring gap reads, in the same unit, and its
    bridge line follows the gap's under its own label."""
    cycle, nri = TAGS["earnings.cycle_gap"], TAGS["earnings.nri_gap"]
    assert cycle.routes == nri.routes == {"mature-growth", "mature-stable"}
    assert cycle.unit == "USD a share" and cycle.words is None
    assert BRIDGE_ORDER.index("earnings.cycle_gap") == BRIDGE_ORDER.index("earnings.nri_gap") + 1
    assert LABELS == {
        "phase": "phase",
        "growth.belief": "belief",
        "path.hold": "held rate",
        "path.step_2": "consensus step 2",
        "path.step_3": "consensus step 3",
        "moat.class": "moat",
        "margin.target": "target margin",
        "capital.sales_to_capital": "sales to capital",
        "return.runway": "runway return",
        "earnings.nri_gap": "non-recurring gap",
        "earnings.cycle_gap": "mid-cycle earnings",
        "earnings.ntm": "NTM earnings",
        "revenue.ntm": "NTM revenue",
        "decline.rate": "decline rate",
        "balance.debt": "debt",
        "balance.cash": "cash",
        "shares.diluted": "diluted shares",
        "value.outside": "outside the business",
    }
    assert sorted(LABELS) == sorted(TAGS)


def test_the_two_new_tags_rules(policy: Policy) -> None:
    """The value outside the business on every valued route, the diluted count on every route
    and period-tied only (spec 2026-11-09 8); both close the bridge, the count first."""
    assert check_override(
        "value.outside", 12.0, "mature-growth", policy, ["filing"], "lasting", None
    ) == ("applied", "")
    assert check_override(
        "value.outside", 12.0, "start-up", policy, ["filing"], "lasting", None
    ) == ("refused-route", "the Start-up route does not read value.outside")
    assert (
        check_override(
            "value.outside", 1200.0, "mature-growth", policy, ["filing"], "lasting", None
        )[0]
        == "refused-unit"
    )
    assert check_override(
        "shares.diluted", 1.06e9, "mature-growth", policy, ["filing"], "period-tied", None
    ) == ("applied", "")
    assert check_override(
        "shares.diluted", 1.06e9, "mature-growth", policy, ["filing"], "lasting", None
    ) == ("refused-unit", "shares.diluted is period-tied only")
    assert (
        check_override(
            "shares.diluted", 0.0, "mature-growth", policy, ["filing"], "period-tied", None
        )[0]
        == "refused-unit"
    )
    assert BRIDGE_ORDER[-2:] == ("shares.diluted", "value.outside")
    assert LABELS["shares.diluted"] == "diluted shares"
    assert LABELS["value.outside"] == "outside the business"


def test_the_two_new_tags_read_where_spec_8_says(policy: Policy) -> None:
    """The outside value on every route but Start-up, a figure a share from −$1,000 to $1,000 and
    any evidence; the count on every route, above 0 shares, never lasting; the ranges as the
    refusals name them."""
    outside, count = TAGS["value.outside"], TAGS["shares.diluted"]
    assert outside.routes == {"mature-growth", "mature-stable", "revenue-growth", "decline"}
    assert outside.unit == "USD a share" and not outside.period_tied_only
    assert count.routes == TAGS["phase"].routes and count.unit == "shares"
    assert count.period_tied_only and count.low_open
    for route in ("mature-stable", "revenue-growth", "decline"):
        assert checked(policy, "value.outside", -1000.0, route, ("url",)) == ("applied", "")
    assert checked(policy, "value.outside", -1000.5, "decline") == (
        "refused-unit",
        "value.outside takes −$1,000 to $1,000 a share",
    )
    tied = checked(policy, "shares.diluted", 1e12, "start-up", lifetime="period-tied")
    assert tied == ("applied", "")
    assert checked(policy, "shares.diluted", -5.0, "decline", lifetime="period-tied") == (
        "refused-unit",
        "shares.diluted takes above 0 to 1,000,000,000,000 shares",
    )
    assert range_text(0.0, 1e12, "shares", low_open=True) == "above 0 to 1,000,000,000,000 shares"
    # the reported count stays locked: the tag is the one door
    assert checked(policy, "shares_diluted", 1.06e9, "mature-growth") == (
        "refused-locked",
        "shares_diluted is reported data",
    )


def test_the_two_new_readings(policy: Policy, deciles: Deciles) -> None:
    """The engine finds no value outside the business, nil on every route that reads it and none
    on Start-up; the count is the one the result cites, the reported one until an override sets
    it, and on a row refused before its route the DATA entry or the JUDGMENT entry in its place."""
    mg = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    assert "outside_value_per_share" not in mg.intermediates
    assert current_reading(mg, "value.outside") == 0.0
    assert current_reading(mg, "shares.diluted") == mg.intermediates["shares"] == 1_000e6
    su = value_company(start_up_inputs(), deciles, policy, TODAY)
    assert current_reading(su, "value.outside") is None
    assert current_reading(su, "shares.diluted") == su.intermediates["shares"]
    for build in (mature_stable_inputs, high_growth_inputs, decline_inputs):
        r = value_company(build(), deciles, policy, TODAY)
        assert current_reading(r, "value.outside") == 0.0
        assert current_reading(r, "shares.diluted") == r.intermediates["shares"]
    outside = {"value.outside": override("value.outside", 12.0)}
    judged = value_company(mature_growth_inputs(), deciles, policy, TODAY, outside)
    assert current_reading(judged, "value.outside") == 12.0
    no_trailing = replace(mature_growth_inputs(), trailing=None)
    refused = value_company(no_trailing, deciles, policy, TODAY)
    assert refused.refusal == "no trailing figures" and "shares" not in refused.intermediates
    assert current_reading(refused, "shares.diluted") == 1_000e6
    assert current_reading(refused, "value.outside") == 0.0  # the route its phase takes
    count = {"shares.diluted": override("shares.diluted", 1_060e6)}
    refused = value_company(no_trailing, deciles, policy, TODAY, count)
    assert current_reading(refused, "shares.diluted") == 1_060e6
    names = [(x.name, x.tag, x.unit) for x in refused.inputs if "shares" in x.name]
    assert names == [("shares.diluted", "JUDGMENT", "shares")]


def test_the_two_ntm_anchors_are_tags(policy: Policy) -> None:
    """The NTM EPS on Mature Growth and the NTM revenue on the revenue-growth and Decline routes,
    each in the unit the route reads it in, their bridge lines right after the phase's."""
    eps, revenue = TAGS["earnings.ntm"], TAGS["revenue.ntm"]
    assert eps.routes == {"mature-growth"} and eps.unit == "USD a share" and eps.words is None
    assert revenue.routes == {"revenue-growth", "decline"} and revenue.unit == "USD"
    assert not eps.period_tied_only and not revenue.period_tied_only
    assert BRIDGE_ORDER[:3] == ("phase", "earnings.ntm", "revenue.ntm")
    assert checked(policy, "earnings.ntm", 6.45, "mature-stable") == (
        "refused-route",
        "the Mature Stable route does not read earnings.ntm",
    )
    assert checked(policy, "revenue.ntm", 12e9, "mature-growth")[0] == "refused-route"
    assert checked(policy, "revenue.ntm", 12e9, "start-up")[0] == "refused-route"


def test_an_ntm_anchor_is_above_zero(policy: Policy) -> None:
    """The range's lower end, 0, is not an anchor the route can value: refused, as a figure past
    the upper end is."""
    guidance = ("guidance",)
    for tag, route, high, text in (
        ("earnings.ntm", "mature-growth", 1_000.0, "above $0 to $1,000 a share"),
        ("revenue.ntm", "decline", 1e15, "above $0"),  # the stand-in for no bound is not written
    ):
        refusal = ("refused-unit", f"{tag} takes {text}")
        assert checked(policy, tag, 0.0, route, guidance) == refusal
        assert checked(policy, tag, -1.0, route, guidance) == refusal
        assert checked(policy, tag, high * 1.01, route, guidance) == refusal
        assert checked(policy, tag, high, route, guidance) == ("applied", "")
        assert checked(policy, tag, 0.01, route, guidance) == ("applied", "")


def test_a_range_with_no_upper_bound_names_its_lower_end_alone(policy: Policy) -> None:
    """The balance corrections' 10^15 dollars stands for no bound (spec 10.2: 0 or more), so the
    sentence names the lower end alone; a bounded range names both ends."""
    assert checked(policy, "balance.debt", -1.0, "decline", lifetime="period-tied") == (
        "refused-unit",
        "balance.debt takes $0 or more",
    )
    assert checked(policy, "balance.cash", 2e15, "start-up", lifetime="period-tied") == (
        "refused-unit",
        "balance.cash takes $0 or more",
    )
    assert range_text(0.0, 1e15, "USD") == "$0 or more"
    assert range_text(0.0, 1e15, "USD", low_open=True) == "above $0"
    assert range_text(0.0, 1_000.0, "USD a share", low_open=True) == "above $0 to $1,000 a share"
    assert range_text(-0.2, 0.6, "ratio") == "−20% to 60%"


def test_an_ntm_anchor_needs_a_guidance_item(policy: Policy) -> None:
    sentence = "an NTM anchor override needs a guidance record among its evidence"
    for tag, value, route in (
        ("earnings.ntm", 6.45, "mature-growth"),
        ("revenue.ntm", 12.6e9, "revenue-growth"),
        ("revenue.ntm", 950.0, "decline"),
    ):
        refused = checked(policy, tag, value, route, ("transcript",))
        assert refused == ("refused-evidence", sentence), tag
        assert checked(policy, tag, value, route, ("transcript", "guidance")) == ("applied", "")
        assert checked(policy, tag, value, route, ()) == (
            "refused-evidence",
            "an override needs evidence",
        )
    # the other tags take a guidance record as any other evidence, and need none
    assert checked(policy, "growth.belief", 0.08, "mature-growth", ("guidance",)) == ("applied", "")
    assert checked(policy, "path.step_2", 0.1, "decline", ("filing",)) == ("applied", "")


def test_a_cycle_gap_is_refused_on_a_growth_route(policy: Policy) -> None:
    assert checked(policy, "earnings.cycle_gap", 2.0, "revenue-growth") == (
        "refused-route",
        "the revenue-growth route does not read earnings.cycle_gap",
    )
    assert checked(policy, "earnings.cycle_gap", 2.0, "decline")[0] == "refused-route"
    assert checked(policy, "earnings.cycle_gap", -2.0, "mature-stable") == ("applied", "")


def test_the_route_follows_the_phase() -> None:
    assert route_of("Start-up") == "start-up"
    assert route_of("Young Growth") == route_of("High Growth") == "revenue-growth"
    assert route_of("Mature Growth") == "mature-growth"
    assert route_of("Mature Stable") == "mature-stable"
    assert route_of("Decline") == "decline"


def test_the_accessor_returns_the_engines_reading_without_an_override(policy: Policy) -> None:
    i = mature_growth_inputs()
    assert i.trailing is not None
    mechanical = Context(i, i.trailing, 150.0, 1_000e6, policy, TODAY)
    assert chosen(mechanical, "moat.class", "Narrow") == "Narrow"
    assert chosen(mechanical, "growth.belief", 0.063) == 0.063
    judged = Context(
        i,
        i.trailing,
        150.0,
        1_000e6,
        policy,
        TODAY,
        overrides={"moat.class": override("moat.class", "Wide")},
    )
    assert chosen(judged, "moat.class", "Narrow") == "Wide"
    assert chosen(judged, "growth.belief", 0.063) == 0.063


def test_a_judgment_input_carries_the_overrides_provenance() -> None:
    belief, moat = override("growth.belief", 0.08, 3), override("moat.class", "Wide", 4)
    # given out of the bridge's order, read in it
    found = judgment_inputs({"moat.class": moat, "growth.belief": belief})
    assert [x.name for x in found] == ["growth.belief", "moat.class"]
    assert all(x.tag == "JUDGMENT" and x.kind == "judgment" for x in found)
    assert found[0].value == 0.08 and found[0].unit == TAGS["growth.belief"].unit
    assert found[0].provenance == Provenance("override 3, agent claude-opus-5-5", None, None, NOW)
    assert found[0].note == "guidance raised"
    assert found[1].value is None and found[1].note == "Wide: guidance raised"
    system = Override(5, "phase", "Decline", "system", None, NOW, "reclassified")
    assert judgment_inputs({"phase": system})[0].provenance.source == "override 5, system"


def test_current_reading_on_each_golden(policy: Policy, deciles: Deciles) -> None:
    mg = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    assert current_reading(mg, "growth.belief") == mg.intermediates["belief"]["rate"]
    assert current_reading(mg, "path.step_2") == mg.intermediates["path_steps"][0]
    assert current_reading(mg, "return.runway") == mg.intermediates["runway_return"]["value"]
    assert current_reading(mg, "earnings.nri_gap") == mg.intermediates["nri_gap"]
    assert current_reading(mg, "earnings.cycle_gap") == 0.0
    assert current_reading(mg, "moat.class") == "Wide"
    assert current_reading(mg, "decline.rate") is None
    dc = value_company(decline_inputs(), deciles, policy, TODAY)
    assert current_reading(dc, "decline.rate") == dc.intermediates["runoff_path"]["d"]
    assert current_reading(dc, "path.step_3") == dc.intermediates["runoff_path"]["steps"][1]
    assert current_reading(dc, "capital.sales_to_capital") == pytest.approx(2.0)
    assert current_reading(dc, "balance.debt") == 200e6
    hg = value_company(high_growth_inputs(), deciles, policy, TODAY)
    assert current_reading(hg, "path.hold") == hg.intermediates["growth_rates"][3]
    assert current_reading(hg, "margin.target") == hg.intermediates["target_margin"]["value"]
    assert current_reading(hg, "balance.cash") == 3_000e6
    su = value_company(start_up_inputs(), deciles, policy, TODAY)
    assert current_reading(su, "phase") == "Start-up"
    assert current_reading(su, "margin.target") == pytest.approx(0.25)
    assert current_reading(su, "moat.class") == "None"
    ms = value_company(mature_stable_inputs(), deciles, policy, TODAY)
    assert current_reading(ms, "margin.target") is None
    assert current_reading(ms, "path.hold") is None
    assert current_reading(ms, "earnings.cycle_gap") == 0.0
    assert current_reading(hg, "earnings.cycle_gap") is None
    assert current_reading(dc, "earnings.cycle_gap") is None
    # the two NTM anchors: the figure each route stored, none on a route that reads neither
    assert current_reading(mg, "earnings.ntm") == mg.intermediates["anchor"]["ntm_eps"]
    assert mg.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.9)
    assert current_reading(hg, "revenue.ntm") == hg.intermediates["ntm_revenue"]
    assert current_reading(dc, "revenue.ntm") == dc.intermediates["runoff_path"]["ntm_revenue"]
    for result in (ms, hg, dc, su):
        assert current_reading(result, "earnings.ntm") is None
    for result in (mg, ms, su):
        assert current_reading(result, "revenue.ntm") is None


def test_the_ntm_readings_off_a_valued_route(policy: Policy, deciles: Deciles) -> None:
    """Under a cycle gap the NTM earnings read the anchor before it; a revenue-growth row refused
    for its target margin reads the NTM revenue of its rebuild keys; a Decline row with no usable
    consensus reads none."""
    gap = {"earnings.cycle_gap": override("earnings.cycle_gap", 1.0)}
    mg = value_company(mature_growth_inputs(), deciles, policy, TODAY, gap)
    assert mg.intermediates["anchor"]["ntm_eps"] == pytest.approx(4.9)
    assert current_reading(mg, "earnings.ntm") == pytest.approx(5.9)
    hg = high_growth_inputs()
    refused = value_company(replace(hg, peers=()), deciles, policy, TODAY)
    assert refused.refusal == "no target margin: 0 mature peers"
    found = refused.intermediates["revenue_path"]["ntm_revenue"]
    assert current_reading(refused, "revenue.ntm") == found and found > 0
    no_consensus = value_company(
        replace(decline_inputs(), quarter_estimates=()), deciles, policy, TODAY
    )
    assert no_consensus.intermediates["runoff_path"]["ntm_revenue"] is None
    assert current_reading(no_consensus, "revenue.ntm") is None


def test_the_cycle_gap_reads_nil_until_an_override_sets_it(
    policy: Policy, deciles: Deciles
) -> None:
    """The engine finds no cycle gap: a mature row's reading is nil, a Mature Stable row refused
    for its trailing earnings too (its route is the one its phase takes), and the route writes
    the gap into its intermediates only under an override."""
    ms = mature_stable_inputs()
    assert ms.trailing is not None
    trough = replace(ms, trailing=replace(ms.trailing, net_income=50e6))
    refused = value_company(trough, deciles, policy, TODAY)
    assert refused.refusal == "no positive trailing earnings" and refused.route is None
    assert "cycle_gap" not in refused.intermediates
    assert current_reading(refused, "earnings.cycle_gap") == 0.0
    lifted = {"earnings.cycle_gap": override("earnings.cycle_gap", -1.0)}
    r = value_company(trough, deciles, policy, TODAY, lifted)
    assert r.refusal is None and r.intermediates["cycle_gap"] == -1.0
    assert current_reading(r, "earnings.cycle_gap") == -1.0


def test_a_balance_line_not_on_file_reads_none(policy: Policy, deciles: Deciles) -> None:
    """The bridge counts an unknown line as nil; the engine's reading of it is none."""
    hg = value_company(replace(high_growth_inputs(), cash=None), deciles, policy, TODAY)
    assert hg.intermediates["cash"] == 0.0
    assert current_reading(hg, "balance.cash") is None


def test_a_row_refused_before_it_cites_its_lines_reads_none(
    policy: Policy, deciles: Deciles
) -> None:
    """A revenue-growth row refused for its target margin keeps the rebuild keys, its missing cash
    line counted as nil, and cites no balance line: the engine's reading is none, not the nil."""
    inputs = replace(high_growth_inputs(), peers=(), cash=None)
    refused = value_company(inputs, deciles, policy, TODAY)
    assert refused.refusal == "no target margin: 0 mature peers"
    assert refused.intermediates["cash"] == 0.0
    assert current_reading(refused, "balance.cash") is None
    cash = override("balance.cash", 500e6)
    judged = value_company(inputs, deciles, policy, TODAY, {"balance.cash": cash})
    assert current_reading(judged, "balance.cash") == 500e6


# The read points: each route reads its inputs through the accessor, and what the route computes
# from an overridden input, its flags included, follows it (method.md 14).


def test_the_judgment_entry_stands_for_the_routes_own(policy: Policy, deciles: Deciles) -> None:
    belief = override("growth.belief", 0.08)
    r = value_company(mature_growth_inputs(), deciles, policy, TODAY, {"growth.belief": belief})
    assert [x.name for x in r.inputs if x.name in ("belief", "growth.belief")] == ["growth.belief"]
    assert r.inputs[-1].tag == "JUDGMENT" and r.intermediates["belief"]["rate"] == 0.08


def test_a_held_rate_override_is_not_capped(policy: Policy, deciles: Deciles) -> None:
    """HGCO's year-3 consensus, 20%, is above its class's 15% cap; an agent's 30% stands."""
    hold = override("path.hold", 0.30)
    mechanical = value_company(high_growth_inputs(), deciles, policy, TODAY)
    r = value_company(high_growth_inputs(), deciles, policy, TODAY, {"path.hold": hold})
    assert mechanical.intermediates["revenue_path"]["hold"] == 0.15
    assert "consensus-above-base-rate" in [f.code for f in mechanical.flags]
    assert r.intermediates["revenue_path"]["hold"] == 0.30
    assert r.intermediates["growth_rates"][3] == 0.30
    assert "consensus-above-base-rate" not in [f.code for f in r.flags]
    (cap,) = [x for x in r.inputs if x.name == "held_growth_cap"]
    assert cap.note is not None
    assert cap.note.endswith("does not bind: the held rate is an agent's override")


def test_a_balance_correction_replaces_a_missing_line(policy: Policy, deciles: Deciles) -> None:
    inputs = replace(high_growth_inputs(), cash=None)
    cash = override("balance.cash", 3_000e6)
    mechanical = value_company(inputs, deciles, policy, TODAY)
    r = value_company(inputs, deciles, policy, TODAY, {"balance.cash": cash})
    assert "line-not-presented:cash" in [f.code for f in mechanical.flags]
    assert "line-not-presented:cash" not in [f.code for f in r.flags]
    assert r.value == value_company(high_growth_inputs(), deciles, policy, TODAY).value


def test_a_target_margin_override_values_a_row_with_no_peers(
    policy: Policy, deciles: Deciles
) -> None:
    inputs = replace(high_growth_inputs(), peers=())
    refused = value_company(inputs, deciles, policy, TODAY)
    assert refused.refusal == "no target margin: 0 mature peers"
    judged = {
        "margin.target": override("margin.target", 0.20),
        "capital.sales_to_capital": override("capital.sales_to_capital", 1.5),
    }
    r = value_company(inputs, deciles, policy, TODAY, judged)
    assert r.value is not None and r.value > 0
    assert r.intermediates["target_margin"]["count"] == 0
    assert r.intermediates["sales_to_capital"]["used"] == "override"


def test_an_overriding_decline_rate_is_never_floored(policy: Policy, deciles: Deciles) -> None:
    """Revenue falling from $5 bn to $1 bn over five years shrinks faster than 50% a year on the
    trend, so d is floored; an agent's d stands as given."""
    steep = fiscal_years(
        [5_000e6, 3_000e6, 2_000e6, 1_200e6, 1_000e6], [0.07, 0.08, 0.08, 0.09, 0.08]
    )
    inputs = replace(decline_inputs(), series=steep)
    rate = {"decline.rate": override("decline.rate", -0.1)}
    mechanical = value_company(inputs, deciles, policy, TODAY)
    r = value_company(inputs, deciles, policy, TODAY, rate)
    assert "decline-rate-floored" in [f.code for f in mechanical.flags]
    assert r.intermediates["runoff_path"]["d"] == -0.1
    assert "decline-rate-floored" not in [f.code for f in r.flags]


def test_a_row_put_in_decline_without_a_trend_is_refused(policy: Policy, deciles: Deciles) -> None:
    """Two fiscal years give no five-year revenue trend, so no decline rate: a refusal, not an
    exception; an agent's decline rate values the row."""
    mg = mature_growth_inputs()
    inputs = replace(mg, series=mg.series[-2:])
    to_decline = {"phase": override("phase", "Decline")}
    assert value_company(inputs, deciles, policy, TODAY, to_decline).refusal == "no revenue trend"
    judged = to_decline | {"decline.rate": override("decline.rate", -0.05)}
    r = value_company(inputs, deciles, policy, TODAY, judged)
    assert r.route == "decline" and r.refusal is None


def test_a_cross_check_reads_the_consensus_as_found(policy: Policy, deciles: Deciles) -> None:
    """A revenue step overridden on a revenue-growth row is not the growth route's earnings
    step: the cross-check's figures stay the mechanical row's."""
    step = override("path.step_2", 0.40)
    mechanical = value_company(high_growth_inputs(), deciles, policy, TODAY)
    r = value_company(high_growth_inputs(), deciles, policy, TODAY, {"path.step_2": step})
    assert r.intermediates["path_steps"][0] == 0.40
    assert r.intermediates["growth_route"] == mechanical.intermediates["growth_route"]


def test_an_overriding_runway_return_charges_the_runway(policy: Policy, deciles: Deciles) -> None:
    """MGCO with its capital at or below zero has the runway charge off (4.6); an agent's runway
    return charges the runway years at it, and the terminal return still follows the moat."""
    mg = mature_growth_inputs()
    negative = tuple(
        replace(y, total_current_liabilities=3 * (y.total_current_assets or 0))
        for y in mg.capital_years
    )
    inputs = replace(mg, capital_years=negative)
    mechanical = value_company(inputs, deciles, policy, TODAY)
    runway = {"return.runway": override("return.runway", 0.20)}
    r = value_company(inputs, deciles, policy, TODAY, runway)
    assert mechanical.intermediates["charge_off"] is True
    assert "charge-zeroed" in [f.code for f in mechanical.flags]
    # with the charge off the runway return is the terminal's, which charges nothing: no reading
    assert current_reading(mechanical, "return.runway") is None
    assert r.intermediates["charge_off"] is False
    assert r.intermediates["runway_return"]["value"] == 0.20
    assert r.intermediates["terminal_roic"] == mechanical.intermediates["terminal_roic"]
    assert "charge-zeroed" not in [f.code for f in r.flags]
    assert r.value is not None and mechanical.value is not None and r.value < mechanical.value


def test_the_basis_test_takes_only_the_agents_correction_to_the_gap(
    policy: Policy, deciles: Deciles
) -> None:
    """MGCO with a non-recurring gap of 0.12: street EPS 5.35 is 0.05 above GAAP EPS 5.30, under
    half the 0.30 of after-tax stock compensation a share, so the consensus includes it. GAAP less
    the whole gap, 5.18, would read 0.17 and switch the basis; the test takes only the agent's
    correction, so the gap overridden at 0.12 moves nothing and at 0.32 switches the basis."""
    inputs = replace(mature_growth_inputs(), gf_eps_without_nri=5.18)
    mechanical = value_company(inputs, deciles, policy, TODAY)
    found = current_reading(mechanical, "earnings.nri_gap")
    assert found == pytest.approx(0.12) and mechanical.intermediates["sbc_basis"] == "includes-sbc"
    assert isinstance(found, float)
    same = value_company(
        inputs, deciles, policy, TODAY, {"earnings.nri_gap": override("earnings.nri_gap", found)}
    )
    assert same.value == mechanical.value and same.intermediates["sbc_basis"] == "includes-sbc"
    shifted = {"earnings.nri_gap": override("earnings.nri_gap", 0.32)}
    moved = value_company(inputs, deciles, policy, TODAY, shifted)
    assert moved.intermediates["sbc_basis"] == "excludes-sbc" and moved.value != mechanical.value
