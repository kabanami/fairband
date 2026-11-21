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
    fx_inputs,
    high_growth_inputs,
    judged_moat,
    mature_growth_inputs,
    mature_stable_inputs,
    start_up_inputs,
    with_minority,
)

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import (
    BRIDGE_ORDER,
    INPUT_OF,
    LABELS,
    LOCKED,
    MOAT_SET,
    TAGS,
    Lifetime,
    Override,
    OverrideTag,
    State,
    check_input,
    check_override,
    current_reading,
    range_text,
    route_of,
    unit_in,
)
from fairband.engine.route import value_company
from fairband.engine.route_steps import Context, chosen, judgment_inputs
from fairband.engine.types import Provenance, Route, money_of
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
    # the moat class's words are a sensitivity reading's alone: an override of it is refused first
    assert check_input("moat.class", "Huge", "mature-growth", policy) == (
        "refused-unit",
        "moat.class takes None, Narrow or Wide",
    )
    assert check_input("moat.class", 2.0, "mature-growth", policy)[0] == "refused-unit"
    assert checked(policy, "earnings.sbc_basis", "partly", "mature-growth") == (
        "refused-unit",
        "earnings.sbc_basis takes includes or excludes",
    )
    assert checked(policy, "growth.belief", "high", "mature-growth") == (
        "refused-unit",
        "growth.belief takes −20% to 60%",
    )
    assert checked(policy, "phase", "Mature Growth", "start-up") == ("applied", "")


def test_an_override_of_the_moat_is_refused_locked(policy: Policy) -> None:
    """Spec 2026-11-19 8.7: the class is the moat table's, which an agent sets with ``moat_set``,
    so ``check_override`` refuses the tag before its other rules, whatever the route, the value,
    the evidence or the lifetime; ``check_input``, a sensitivity reading's rules, takes it as
    before, since a reading may vary the class and changes no input."""
    assert MOAT_SET == "moat.class is the moat table's: record the verdict with moat_set"
    assert check_override(
        "moat.class", "Wide", "mature-stable", policy, ["filing"], "lasting", None
    ) == ("refused-locked", MOAT_SET)
    assert check_input("moat.class", "Wide", "mature-stable", policy) == ("applied", "")
    # first: before the route, the words, the evidence and the lifetime
    assert checked(policy, "moat.class", "Huge", "decline", [], "period-tied") == (
        "refused-locked",
        MOAT_SET,
    )
    assert check_input("moat.class", "Narrow", "decline", policy)[0] == "refused-route"
    assert "moat.class" in TAGS and "moat.class" not in LOCKED  # a tag still, a reading's axis


def test_check_refuses_a_lasting_balance_correction(policy: Policy) -> None:
    assert checked(policy, "balance.debt", 100.0, "decline") == (
        "refused-unit",
        "balance.debt is period-tied only",
    )
    tied = checked(policy, "balance.debt", 100.0, "decline", lifetime="period-tied")
    assert tied == ("applied", "")


def test_the_minority_interest_tag_s_rules(policy: Policy) -> None:
    """Spec 2026-11-13 13: a total of $0 or more on the three firm-value routes, period-tied
    only, bridged right after cash under the label "minority interest"."""
    tied = ("balance.minority", 120e6, "revenue-growth", policy, ["filing"], "period-tied", None)
    assert check_override(*tied) == ("applied", "")
    assert check_override(*tied[:1], 0.0, *tied[2:]) == ("applied", "")
    assert check_override(*tied[:1], -1.0, *tied[2:]) == (
        "refused-unit",
        "balance.minority takes $0 or more",
    )
    assert check_override(*tied[:5], "lasting", None) == (
        "refused-unit",
        "balance.minority is period-tied only",
    )
    for route in ("decline", "start-up"):
        assert check_input("balance.minority", 120e6, route, policy) == ("applied", "")
    for route in ("mature-growth", "mature-stable"):
        assert check_input("balance.minority", 120e6, route, policy)[0] == "refused-route"
    assert BRIDGE_ORDER.index("balance.minority") == BRIDGE_ORDER.index("balance.cash") + 1
    assert LABELS["balance.minority"] == "minority interest"
    assert INPUT_OF["balance.minority"] == "minority_interest"


def test_the_committed_shares_tag_s_rules(policy: Policy) -> None:
    """Spec 2026-11-14 4: a count of shares above 0, on all five routes, period-tied only, bridged
    right after the diluted count under the label "committed shares"; it stands for no entry of
    the route's, the reported count's entry staying beside it."""
    tied = ("shares.committed", 60e6, "mature-growth", policy, ["filing"], "period-tied", None)
    for route in get_args(Route):
        assert check_override(*tied[:2], route, *tied[3:]) == ("applied", ""), route
    for count in (0.0, -5.0):
        assert check_override(*tied[:1], count, *tied[2:]) == (
            "refused-unit",
            "shares.committed takes above 0 to 1,000,000,000,000 shares",
        )
    assert check_override(*tied[:5], "lasting", None) == (
        "refused-unit",
        "shares.committed is period-tied only",
    )
    spec = TAGS["shares.committed"]
    assert spec.unit == "shares" and spec.words is None
    assert spec.period_tied_only and spec.low_open
    assert BRIDGE_ORDER.index("shares.committed") == BRIDGE_ORDER.index("shares.diluted") + 1
    assert LABELS["shares.committed"] == "committed shares"
    assert "shares.committed" not in INPUT_OF


def test_the_one_time_item_tag_s_rules(policy: Policy) -> None:
    """Spec 2026-11-14 5: an amount a share on Mature Growth alone, −$100 to $100 with both ends,
    period-tied only, bridged right before the cycle gap under the label "one-time item in the
    NTM consensus"; it stands for no entry of the route's, which cites the consensus as found."""
    tied = ("earnings.ntm_nri", 0.59, "mature-growth", policy, ["filing"], "period-tied", None)
    assert check_override(*tied) == ("applied", "")
    for end in (-100.0, 100.0):
        assert check_override(*tied[:1], end, *tied[2:]) == ("applied", ""), end
    assert check_override(*tied[:1], -100.01, *tied[2:]) == (
        "refused-unit",
        "earnings.ntm_nri takes −$100 to $100 a share",
    )
    assert check_override(*tied[:5], "lasting", None) == (
        "refused-unit",
        "earnings.ntm_nri is period-tied only",
    )
    for route, name in (
        ("mature-stable", "Mature Stable"),
        ("revenue-growth", "revenue-growth"),
        ("decline", "Decline"),
        ("start-up", "Start-up"),
    ):
        assert check_input("earnings.ntm_nri", 0.59, route, policy) == (
            "refused-route",
            f"the {name} route does not read earnings.ntm_nri",
        )
    spec = TAGS["earnings.ntm_nri"]
    assert spec.routes == {"mature-growth"}
    assert spec.unit == "USD a share" and spec.words is None
    assert spec.period_tied_only and not spec.low_open and spec.lasting_value is None
    assert BRIDGE_ORDER.index("earnings.ntm_nri") == BRIDGE_ORDER.index("earnings.cycle_gap") - 1
    assert LABELS["earnings.ntm_nri"] == "one-time item in the NTM consensus"
    assert "earnings.ntm_nri" not in INPUT_OF


def test_the_two_revenue_step_tags_rules(policy: Policy) -> None:
    """Spec 2026-11-14 6.1: a growth rate on Mature Growth alone, −80% to 300% with both ends,
    period-tied only, bridged right after the two consensus steps under the labels "revenue step
    2" and "revenue step 3"; each stands for no entry of the route's."""
    for tag in ("revenue.step_2", "revenue.step_3"):
        tied = (tag, 0.05, "mature-growth", policy, ["filing"], "period-tied", None)
        assert check_override(*tied) == ("applied", ""), tag
        for end in (-0.80, 3.00):
            assert check_override(*tied[:1], end, *tied[2:]) == ("applied", ""), (tag, end)
        assert check_override(*tied[:1], 3.01, *tied[2:]) == (
            "refused-unit",
            f"{tag} takes −80% to 300%",
        )
        assert check_override(*tied[:5], "lasting", None) == (
            "refused-unit",
            f"{tag} is period-tied only",
        )
        for route, name in (
            ("mature-stable", "Mature Stable"),
            ("revenue-growth", "revenue-growth"),
            ("decline", "Decline"),
            ("start-up", "Start-up"),
        ):
            assert check_input(tag, 0.05, route, policy) == (
                "refused-route",
                f"the {name} route does not read {tag}",
            )
        spec = TAGS[tag]
        assert spec.routes == {"mature-growth"}
        assert spec.unit == "ratio" and spec.words is None
        assert spec.period_tied_only and not spec.low_open and spec.lasting_value is None
        assert tag not in INPUT_OF
    steps = BRIDGE_ORDER.index("path.step_2")
    assert BRIDGE_ORDER[steps : steps + 4] == (
        "path.step_2",
        "path.step_3",
        "revenue.step_2",
        "revenue.step_3",
    )
    assert (LABELS["revenue.step_2"], LABELS["revenue.step_3"]) == (
        "revenue step 2",
        "revenue step 3",
    )


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
    bridge line follows the gap's, the two stock-pay lines (spec 2026-11-13 7.2) and the one-time
    item's (spec 2026-11-14 5) under its own label."""
    cycle, nri = TAGS["earnings.cycle_gap"], TAGS["earnings.nri_gap"]
    assert cycle.routes == nri.routes == {"mature-growth", "mature-stable"}
    assert cycle.unit == "USD a share" and cycle.words is None
    gap = BRIDGE_ORDER.index("earnings.nri_gap")
    assert BRIDGE_ORDER[gap : gap + 5] == (
        "earnings.nri_gap",
        "earnings.sbc",
        "earnings.sbc_basis",
        "earnings.ntm_nri",
        "earnings.cycle_gap",
    )
    assert LABELS == {
        "phase": "phase",
        "growth.belief": "belief",
        "path.hold": "held rate",
        "path.step_2": "consensus step 2",
        "path.step_3": "consensus step 3",
        "revenue.step_2": "revenue step 2",
        "revenue.step_3": "revenue step 3",
        "moat.class": "moat",
        "margin.target": "target margin",
        "capital.sales_to_capital": "sales to capital",
        "return.runway": "runway return",
        "earnings.nri_gap": "non-recurring gap",
        "earnings.sbc": "stock pay",
        "earnings.sbc_basis": "stock-pay basis",
        "earnings.ntm_nri": "one-time item in the NTM consensus",
        "earnings.cycle_gap": "mid-cycle earnings",
        "earnings.ntm": "NTM earnings",
        "revenue.ntm": "NTM revenue",
        "decline.rate": "decline rate",
        "balance.debt": "debt",
        "balance.cash": "cash",
        "balance.minority": "minority interest",
        "shares.diluted": "diluted shares",
        "shares.committed": "committed shares",
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
    # the committed shares follow the count (spec 2026-11-14 4); the outside value stays last
    assert BRIDGE_ORDER[-3:] == ("shares.diluted", "shares.committed", "value.outside")
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


def test_the_count_s_reading_leaves_the_committed_shares_out(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-14 4 on every route: the intermediates keep ``shares``, the count in force, and
    gain ``shares_committed`` under the override alone; the engine's reading of the diluted count
    is the one less the other, so the committed shares never pass for a corrected count; the
    engine finds no committed shares, nil on every result, a refusal before the route too. The
    reported count's DATA entry stays beside the JUDGMENT entry, in shares."""
    for build in (
        mature_growth_inputs,
        mature_stable_inputs,
        high_growth_inputs,
        decline_inputs,
        start_up_inputs,
    ):
        plain = value_company(build(), deciles, policy, TODAY)
        count = plain.intermediates["shares"]
        committed = {"shares.committed": override("shares.committed", 0.1 * count)}
        judged = value_company(build(), deciles, policy, TODAY, committed)
        assert "shares_committed" not in plain.intermediates, build.__name__
        im = judged.intermediates
        assert im["shares"] == pytest.approx(1.1 * count) and im["shares_committed"] == 0.1 * count
        assert current_reading(judged, "shares.diluted") == pytest.approx(count)
        assert current_reading(plain, "shares.committed") == 0.0
        assert current_reading(judged, "shares.committed") == 0.0
        names = [(x.name, x.tag, x.unit) for x in judged.inputs if "shares" in x.name]
        assert names == [
            ("shares_diluted", "DATA", "shares"),
            ("shares.committed", "JUDGMENT", "shares"),
        ]
    no_trailing = replace(mature_growth_inputs(), trailing=None)
    committed = {"shares.committed": override("shares.committed", 60e6)}
    refused = value_company(no_trailing, deciles, policy, TODAY, committed)
    assert refused.refusal == "no trailing figures" and "shares" not in refused.intermediates
    assert current_reading(refused, "shares.diluted") == 1_000e6
    assert current_reading(refused, "shares.committed") == 0.0


def test_the_two_stock_pay_tags_rules(policy: Policy) -> None:
    """Spec 2026-11-13 7.2 and 7.3: the basis takes its two words, lasting or period-tied; the
    stock pay is a total of $0 or more, period-tied, or lasting at 0 alone, for a company that
    pays no stock; both on Mature Growth alone, their bridge lines right after the non-recurring
    gap's, the figure first. The stock pay stands in for the route's own ``sbc_ttm`` entry; the
    basis stands for no entry."""
    assert check_input("earnings.sbc_basis", "excludes", "mature-growth", policy) == ("applied", "")
    assert check_input("earnings.sbc_basis", "maybe", "mature-growth", policy) == (
        "refused-unit",
        "earnings.sbc_basis takes includes or excludes",
    )
    for tag, value in (("earnings.sbc", 40e6), ("earnings.sbc_basis", "includes")):
        for route in ("mature-stable", "revenue-growth"):
            state, _ = check_input(tag, value, route, policy)
            assert state == "refused-route", (tag, route)
    lasting = ("earnings.sbc", 40e6, "mature-growth", policy, ["filing"], "lasting", None)
    assert check_override(*lasting) == (
        "refused-unit",
        "a lasting earnings.sbc takes 0 only: a figure is period-tied",
    )
    assert check_override(*lasting[:1], 0.0, *lasting[2:]) == ("applied", "")
    assert TAGS["earnings.sbc"].lasting_value == 0.0
    assert TAGS["balance.cash"].lasting_value is None
    # the other period-tied inputs take no lasting figure, nil included
    assert check_override("balance.cash", 0.0, "decline", policy, ["filing"], "lasting", None) == (
        "refused-unit",
        "balance.cash is period-tied only",
    )
    # the input's own rules come first: a lasting figure below 0 is refused for its range
    assert check_override(*lasting[:1], -1.0, *lasting[2:]) == (
        "refused-unit",
        "earnings.sbc takes $0 or more",
    )
    tied = ("earnings.sbc", 40e6, "mature-growth", policy, ["filing"], "period-tied", None)
    assert check_override(*tied) == ("applied", "")
    assert check_override(*tied[:1], 0.0, *tied[2:]) == ("applied", "")  # nil is a figure
    for refused in (-1.0, "lots"):
        assert check_override(*tied[:1], refused, *tied[2:]) == (
            "refused-unit",
            "earnings.sbc takes $0 or more",
        )
    for lifetime in ("lasting", "period-tied"):
        basis = check_override(
            "earnings.sbc_basis", "includes", "mature-growth", policy, ["filing"], lifetime, None
        )
        assert basis == ("applied", ""), lifetime
    sbc, basis_spec = TAGS["earnings.sbc"], TAGS["earnings.sbc_basis"]
    assert (sbc.routes, sbc.unit, sbc.words) == ({"mature-growth"}, "USD", None)
    assert sbc.period_tied_only and not sbc.low_open
    assert (basis_spec.routes, basis_spec.unit) == ({"mature-growth"}, "basis")
    assert basis_spec.words == ("includes", "excludes") and not basis_spec.period_tied_only
    assert basis_spec.lasting_value is None
    assert BRIDGE_ORDER.index("earnings.sbc") == BRIDGE_ORDER.index("earnings.nri_gap") + 1
    assert BRIDGE_ORDER.index("earnings.sbc_basis") == BRIDGE_ORDER.index("earnings.sbc") + 1
    assert (LABELS["earnings.sbc"], LABELS["earnings.sbc_basis"]) == (
        "stock pay",
        "stock-pay basis",
    )
    assert INPUT_OF["earnings.sbc"] == "sbc_ttm" and "earnings.sbc_basis" not in INPUT_OF


def test_the_stock_pay_range_is_read_in_the_row_s_currency(
    policy: Policy, deciles: Deciles
) -> None:
    """``earnings.sbc`` is a total in the reporting currency, its range read as ``balance.cash``'s
    is: on FXCO, in SEK at 8.0, the lower end 0 × 8.0 is 0 SEK, and the upper end, the policy's
    stand-in for no bound, stays one and is not written, so the refusal of −1 reads "0 SEK or
    more"; the stand-in end itself, 10^15 SEK, applies; the override's unit is the code."""
    rate, currency = money_of(value_company(fx_inputs(), deciles, policy, TODAY))
    assert (rate, currency) == (8.0, "SEK")
    pay = ("earnings.sbc", 1e15, "mature-growth", policy, ["filing"], "period-tied", None)
    assert check_override(*pay, fx_rate=rate, currency=currency) == ("applied", "")
    assert check_override(*pay[:1], 320e6, *pay[2:], fx_rate=rate, currency=currency) == (
        "applied",
        "",
    )
    assert check_override(*pay[:1], -1.0, *pay[2:], fx_rate=rate, currency=currency) == (
        "refused-unit",
        "earnings.sbc takes 0 SEK or more",
    )
    assert unit_in(TAGS["earnings.sbc"].unit, currency) == "SEK"
    assert unit_in(TAGS["earnings.sbc_basis"].unit, currency) == "basis"


def test_the_two_stock_pay_readings(policy: Policy, deciles: Deciles) -> None:
    """The stock pay the anchor read, the stored $400 m on MGCO until an agent's figure replaces
    it; the basis as the test read it, in the input's words, ``None`` on an unknown basis and on
    every other route. MGCO's street EPS of 5.80 lies 0.50 above GAAP 5.30, at or above half the
    0.30 of after-tax stock pay a share: excludes."""
    mg = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    assert current_reading(mg, "earnings.sbc") == mg.intermediates["sbc_ttm"] == 400e6
    assert current_reading(mg, "earnings.sbc_basis") == "includes"
    excludes = value_company(
        replace(mature_growth_inputs(), street_ttm_eps=5.80), deciles, policy, TODAY
    )
    assert current_reading(excludes, "earnings.sbc_basis") == "excludes"
    unknown = value_company(
        replace(mature_growth_inputs(), street_ttm_eps=None), deciles, policy, TODAY
    )
    assert unknown.intermediates["sbc_basis"] == "unknown"
    assert current_reading(unknown, "earnings.sbc_basis") is None
    pay = {"earnings.sbc": override("earnings.sbc", 600e6)}
    judged = value_company(mature_growth_inputs(), deciles, policy, TODAY, pay)
    assert current_reading(judged, "earnings.sbc") == judged.intermediates["sbc_ttm"] == 600e6
    entries = [(x.name, x.tag, x.unit) for x in judged.inputs if "sbc" in x.name]
    assert entries == [("earnings.sbc", "JUDGMENT", "USD")]
    basis = {"earnings.sbc_basis": override("earnings.sbc_basis", "excludes")}
    charged = value_company(mature_growth_inputs(), deciles, policy, TODAY, basis)
    assert current_reading(charged, "earnings.sbc_basis") == "excludes"
    for build in (mature_stable_inputs, high_growth_inputs, decline_inputs, start_up_inputs):
        r = value_company(build(), deciles, policy, TODAY)
        assert current_reading(r, "earnings.sbc") is None, r.symbol
        assert current_reading(r, "earnings.sbc_basis") is None, r.symbol


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


def test_a_runway_return_is_above_zero(policy: Policy) -> None:
    """The charge divides by the runway return, so 0 is not one it can take: the range's lower
    end is excluded, as the NTM anchors' are, and the policy's pair is [0, 5] (policy v13)."""
    assert TAGS["return.runway"].low_open
    assert policy.override_ranges["return.runway"] == (0.0, 5.0)
    refusal = ("refused-unit", "return.runway takes above 0% to 500%")
    for route in ("mature-growth", "mature-stable"):
        assert checked(policy, "return.runway", 0.0, route) == refusal
        assert checked(policy, "return.runway", -0.01, route) == refusal
        assert checked(policy, "return.runway", 5.01, route) == refusal
        assert checked(policy, "return.runway", 5.0, route) == ("applied", "")
        assert checked(policy, "return.runway", 0.001, route) == ("applied", "")


def test_the_runway_return_takes_up_to_500_percent(policy: Policy) -> None:
    """Spec 2026-11-13 10: the engine's own measure, 332.6% on AAPL, is a value the input takes;
    the bound still catches a percent typed as a whole number."""
    assert check_input("return.runway", 3.326, "mature-growth", policy) == ("applied", "")
    assert check_input("return.runway", 5.0, "mature-growth", policy) == ("applied", "")
    state, sentence = check_input("return.runway", 5.01, "mature-growth", policy)
    assert state == "refused-unit" and "500" in sentence
    assert check_input("return.runway", 0.0, "mature-growth", policy)[0] == "refused-unit"


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


def test_a_money_range_is_read_in_the_row_s_currency(policy: Policy, deciles: Deciles) -> None:
    """Spec 2026-11-10 7.3: on a row in another currency a money range is the policy's × the
    snapshot's rate (``money_of``), an end of no bound staying one; the rule passes the rate
    through ``check_override``; a ratio's range and every USD row's are as before."""
    sek = value_company(fx_inputs(), deciles, policy, TODAY)
    usd = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    assert (money_of(sek), money_of(usd)) == ((8.0, "SEK"), (1.0, "USD"))
    rate, currency = money_of(sek)
    debt = ("balance.debt", -1.0, "decline", policy, ["filing"], "period-tied", None)
    assert check_override(*debt, fx_rate=rate, currency=currency) == (
        "refused-unit",
        "balance.debt takes 0 SEK or more",  # the end of no bound stays one
    )
    assert check_override(*debt) == ("refused-unit", "balance.debt takes $0 or more")
    # the minority interest, a total as debt is: its range in SEK, and its unit the code
    minority = ("balance.minority", -1.0, "revenue-growth", policy, ["filing"], "period-tied", None)
    assert check_override(*minority, fx_rate=rate, currency=currency) == (
        "refused-unit",
        "balance.minority takes 0 SEK or more",
    )
    held = (*minority[:1], 960e6, *minority[2:])
    assert check_override(*held, fx_rate=rate, currency=currency) == ("applied", "")
    assert unit_in(TAGS["balance.minority"].unit, currency) == "SEK"
    gap = ("earnings.nri_gap", 500.0, "mature-growth", policy, ["filing"], "lasting", None)
    assert check_override(*gap, fx_rate=rate, currency=currency) == ("applied", "")
    assert check_override(*gap) == ("refused-unit", "earnings.nri_gap takes −$100 to $100 a share")
    assert check_override(*gap[:1], 900.0, *gap[2:], fx_rate=rate, currency=currency) == (
        "refused-unit",
        "earnings.nri_gap takes −800 to 800 SEK a share",
    )
    assert (unit_in("USD a share", "SEK"), unit_in("USD", "SEK"), unit_in("ratio", "SEK")) == (
        "SEK a share",
        "SEK",
        "ratio",
    )


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
    mechanical = Context(i, i.trailing, 150.0, 1_000e6, 1_000e6, policy, TODAY)
    assert chosen(mechanical, "moat.class", "Narrow") == "Narrow"
    assert chosen(mechanical, "growth.belief", 0.063) == 0.063
    judged = Context(
        i,
        i.trailing,
        150.0,
        1_000e6,
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
    assert current_reading(mg, "earnings.nri_gap") == 0.0
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


def test_the_moat_s_reading_whatever_its_tag(policy: Policy, deciles: Deciles) -> None:
    """The engine's reading of ``moat.class`` is the intermediates' ``moat``, else the word leading
    the note of the ``moat_class`` input, whatever its tag (spec 2026-11-19 8.5): a Start-up
    result, whose intermediates hold no moat, on the owner's row noted "Wide: ..." reads Wide, and
    on the file's row its RULE note's word; a Mature Growth result on an agent's row its moat."""
    reason = "a network no rival can build"
    owner = judged_moat(start_up_inputs(), "Wide", "owner", NOW, reason)
    su = value_company(owner, deciles, policy, TODAY)
    assert "moat" not in su.intermediates
    [moat] = [x for x in su.inputs if x.name == "moat_class"]
    assert (moat.tag, moat.note) == ("JUDGMENT", f"Wide: {reason}")
    assert current_reading(su, "moat.class") == "Wide"
    plain = value_company(replace(start_up_inputs(), moat_class="Narrow"), deciles, policy, TODAY)
    assert current_reading(plain, "moat.class") == "Narrow"
    agent = judged_moat(mature_growth_inputs(), "Narrow", "agent claude-opus-5-5", NOW, reason)
    assert current_reading(value_company(agent, deciles, policy, TODAY), "moat.class") == "Narrow"


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
    trough = replace(ms, trailing=replace(ms.trailing, net_income=-50e6))
    refused = value_company(trough, deciles, policy, TODAY)
    assert refused.refusal == "no positive trailing earnings" and refused.route is None
    assert "cycle_gap" not in refused.intermediates
    assert current_reading(refused, "earnings.cycle_gap") == 0.0
    lifted = {"earnings.cycle_gap": override("earnings.cycle_gap", -1.0)}
    r = value_company(trough, deciles, policy, TODAY, lifted)
    assert r.refusal is None and r.intermediates["cycle_gap"] == -1.0
    assert current_reading(r, "earnings.cycle_gap") == -1.0


def test_the_one_time_item_reads_nil_until_an_override_sets_it(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-14 5: the engine finds no one-time item. A Mature Growth result reads nil, a
    row refused before its route too (its route is the one its phase takes); every other route
    reads none. The route writes ``ntm_nri`` into its intermediates under the override alone: on
    MGCO, an NTM EPS of $5.90, a one-time item of $0.59 leaves the anchor at $5.31. The NTM
    earnings read $5.31, the EPS a guided override would stand in for to give the result, since
    the item is moot under it; with a cycle gap of $1.00 too, the anchor is $4.31 and the NTM
    earnings read $5.31, the gap alone added back."""
    plain = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    assert "ntm_nri" not in plain.intermediates
    assert current_reading(plain, "earnings.ntm_nri") == 0.0
    for build in (mature_stable_inputs, high_growth_inputs, decline_inputs, start_up_inputs):
        r = value_company(build(), deciles, policy, TODAY)
        assert current_reading(r, "earnings.ntm_nri") is None, build.__name__
    no_trailing = replace(mature_growth_inputs(), trailing=None)
    refused = value_company(no_trailing, deciles, policy, TODAY)
    assert refused.route is None and current_reading(refused, "earnings.ntm_nri") == 0.0
    one_time = {"earnings.ntm_nri": override("earnings.ntm_nri", 0.59)}
    r = value_company(mature_growth_inputs(), deciles, policy, TODAY, one_time)
    assert r.intermediates["ntm_nri"] == 0.59
    assert r.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.31)
    assert current_reading(r, "earnings.ntm_nri") == 0.59
    assert current_reading(r, "earnings.ntm") == pytest.approx(5.31)
    both = one_time | {"earnings.cycle_gap": override("earnings.cycle_gap", 1.0)}
    r = value_company(mature_growth_inputs(), deciles, policy, TODAY, both)
    assert r.intermediates["anchor"]["ntm_eps"] == pytest.approx(4.31)
    assert current_reading(r, "earnings.ntm") == pytest.approx(4.31 + 1.00)


def test_the_revenue_step_readings_are_the_consensus_s_as_found(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-14 6.1 and 6.3: the engine's reading of a revenue step is the consensus's step
    as found, ``charge.revenue_steps_found``, and never an agent's. On MGCO with fiscal 2027 to
    2029 revenue of $25,000 m, $27,500 m and $29,700 m the readings are 10% and 8%, and the
    reading of step 3 stays 8% under a ``revenue.step_3`` of 5%. Without a consensus revenue step,
    on MGCO as it is, the reading is none; off Mature Growth it is none, on a Mature Stable row
    whose cross-check reads the same consensus too; and on a Mature Growth row refused before its
    charge, none. A result stored before the steps found were kept reads its charge's
    ``revenue_steps``, which then held the steps as found."""
    rows = tuple(
        replace(a, revenue=x, analysts_revenue=10)
        for a, x in zip(
            mature_growth_inputs().annual_estimates, (25_000e6, 27_500e6, 29_700e6), strict=True
        )
    )
    inputs = replace(mature_growth_inputs(), annual_estimates=rows)
    plain = value_company(inputs, deciles, policy, TODAY)
    assert current_reading(plain, "revenue.step_2") == pytest.approx(0.10)
    assert current_reading(plain, "revenue.step_3") == pytest.approx(0.08)
    step = {"revenue.step_3": override("revenue.step_3", 0.05)}
    agent = value_company(inputs, deciles, policy, TODAY, step)
    assert agent.intermediates["charge"]["revenue_steps"][1] == 0.05
    assert current_reading(agent, "revenue.step_3") == current_reading(plain, "revenue.step_3")
    bare = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    for tag in ("revenue.step_2", "revenue.step_3"):
        assert current_reading(bare, tag) is None, tag
    stable_inputs = replace(
        mature_stable_inputs(),
        quarter_estimates=inputs.quarter_estimates,
        annual_estimates=inputs.annual_estimates,
    )
    stable = value_company(stable_inputs, deciles, policy, TODAY)
    assert stable.intermediates["growth_route"]["charge"]["revenue_steps_found"] == [
        pytest.approx(0.10),
        pytest.approx(0.08),
    ]
    others = [
        value_company(build(), deciles, policy, TODAY)
        for build in (high_growth_inputs, decline_inputs, start_up_inputs)
    ]
    for r in (stable, *others):
        assert current_reading(r, "revenue.step_2") is None, r.route
    refused = value_company(replace(inputs, trailing=None), deciles, policy, TODAY)
    assert refused.route is None and current_reading(refused, "revenue.step_2") is None
    charge = {
        k: v
        for k, v in plain.intermediates["charge"].items()
        if k not in ("revenue_steps_found", "revenue_step_source")
    }
    before = replace(plain, intermediates=plain.intermediates | {"charge": charge})
    assert current_reading(before, "revenue.step_2") == pytest.approx(0.10)
    assert current_reading(before, "revenue.step_3") == pytest.approx(0.08)


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


def test_the_minority_interest_reads_the_sheet_s_line(policy: Policy, deciles: Deciles) -> None:
    """Spec 2026-11-13 13 on HGCO: the engine's reading of the minority interest is the line the
    result cites, the DATA entry ``minority_interest`` as the newest sheet presents it: $120 m with
    the line, none where the sheet does not present it, and a figure below zero as it stands,
    though the route counts that as nil. Under a ``balance.minority`` of $500 m the JUDGMENT entry
    stands in its place, so the reading is the agent's figure, the one the route subtracts; the
    Start-up route takes an agent's figure the same way. The two mature routes cite no such line
    and read none."""
    plain = value_company(high_growth_inputs(), deciles, policy, TODAY)
    assert current_reading(plain, "balance.minority") is None
    held = with_minority(high_growth_inputs(), 120e6)
    line = value_company(held, deciles, policy, TODAY)
    assert current_reading(line, "balance.minority") == 120e6
    assert line.intermediates["minority_interest"] == 120e6
    below = value_company(with_minority(high_growth_inputs(), -10e6), deciles, policy, TODAY)
    assert current_reading(below, "balance.minority") == -10e6
    assert below.intermediates["minority_interest"] == 0.0
    minority = {"balance.minority": override("balance.minority", 500e6)}
    judged = value_company(held, deciles, policy, TODAY, minority)
    assert current_reading(judged, "balance.minority") == 500e6
    assert judged.intermediates["minority_interest"] == 500e6
    entries = [(x.name, x.tag, x.unit) for x in judged.inputs if "minority" in x.name]
    assert entries == [("balance.minority", "JUDGMENT", "USD")]
    start_up = value_company(start_up_inputs(), deciles, policy, TODAY, minority)
    assert start_up.intermediates["minority_interest"] == 500e6
    assert current_reading(start_up, "balance.minority") == 500e6
    for build in (mature_growth_inputs, mature_stable_inputs):
        r = value_company(build(), deciles, policy, TODAY)
        assert current_reading(r, "balance.minority") is None, r.symbol


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


def test_the_basis_test_takes_the_agents_whole_figure(policy: Policy, deciles: Deciles) -> None:
    """Spec 2026-11-19 7.1: the engine finds no gap, so the anchor's basis test corrects GAAP EPS
    by the agent's whole figure. MGCO: street EPS 5.35 is 0.05 above GAAP EPS 5.30, under half
    the 0.30 of after-tax stock compensation a share, so the consensus includes it. The gap reads
    0.0, and an override of 0.0 moves nothing; one of 0.12 takes GAAP EPS to 5.18, 5.35 lies 0.17
    above it, at or above half of 0.30, so the basis reads excludes-sbc and the value moves."""
    inputs = mature_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert current_reading(mechanical, "earnings.nri_gap") == 0.0
    assert mechanical.intermediates["sbc_basis"] == "includes-sbc"
    nil = {"earnings.nri_gap": override("earnings.nri_gap", 0.0)}
    same = value_company(inputs, deciles, policy, TODAY, nil)
    assert same.value == mechanical.value and same.intermediates["sbc_basis"] == "includes-sbc"
    whole = {"earnings.nri_gap": override("earnings.nri_gap", 0.12)}
    moved = value_company(inputs, deciles, policy, TODAY, whole)
    assert moved.intermediates["sbc_basis"] == "excludes-sbc" and moved.value != mechanical.value


def test_the_engine_reads_a_nil_gap_on_the_mature_routes(policy: Policy, deciles: Deciles) -> None:
    """Spec 2026-11-19 7.1: the engine finds no non-recurring gap, so its reading is nil on a
    Mature Growth or Mature Stable result, a refusal's too (the route its phase takes), as the
    cycle gap's is, and a bridge's old value is 0.00; none on another route. A result stored
    before method 1.7 holds the gap the engine found then, and reads it."""
    mg = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    ms = value_company(mature_stable_inputs(), deciles, policy, TODAY)
    hg = value_company(high_growth_inputs(), deciles, policy, TODAY)
    assert (mg.intermediates["nri_gap"], ms.intermediates["nri_gap"]) == (None, None)
    assert current_reading(mg, "earnings.nri_gap") == 0.0
    assert current_reading(ms, "earnings.nri_gap") == 0.0
    dc = value_company(decline_inputs(), deciles, policy, TODAY)
    assert current_reading(hg, "earnings.nri_gap") is None
    assert current_reading(dc, "earnings.nri_gap") is None
    stable = mature_stable_inputs()
    assert stable.trailing is not None
    loss = replace(stable, trailing=replace(stable.trailing, net_income=-500e6, eps_diluted=-0.50))
    refused = value_company(loss, deciles, policy, TODAY)
    assert refused.refusal == "no positive trailing earnings"
    assert current_reading(refused, "earnings.nri_gap") == 0.0
    before = replace(ms, intermediates={**ms.intermediates, "nri_gap": -0.423})
    assert current_reading(before, "earnings.nri_gap") == -0.423
