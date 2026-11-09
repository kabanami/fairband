"""The review: the engine under an agent's overrides, applied one at a time in the method's order to
build the bridge from the mechanical value (spec 2026-11-06 Tier 2, 10.4 and 20.2)."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from support.engine_companies import (
    decline_inputs,
    high_growth_inputs,
    mature_growth_inputs,
    mature_stable_inputs,
    start_up_inputs,
    young_growth_inputs,
)

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import (
    BRIDGE_ORDER,
    TAGS,
    Override,
    OverrideTag,
    check_override,
    current_reading,
    route_of,
)
from fairband.engine.review import REVIEW_METHOD, review_company
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import result_from_json, result_to_json
from fairband.policy import Policy

TODAY = date(2026, 10, 31)
NOW = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
FIXTURES: dict[str, Callable[[], CompanyInputs]] = {
    "MGCO": mature_growth_inputs,
    "MSCO": mature_stable_inputs,
    "HGCO": high_growth_inputs,
    "YGCO": young_growth_inputs,
    "DCCO": decline_inputs,
    "SUCO": start_up_inputs,
}


def OVERRIDE(tag: OverrideTag, value: float | str, id: int = 1) -> Override:
    return Override(id, tag, value, "agent", "claude-opus-5-5", NOW, "because")


@pytest.mark.parametrize(
    "symbol,tag,value",
    [
        ("MGCO", "growth.belief", 0.08),
        ("MGCO", "moat.class", "Narrow"),  # MGCO is Wide
        ("MGCO", "earnings.nri_gap", 0.5),
        ("MGCO", "earnings.cycle_gap", 1.0),
        ("MGCO", "return.runway", 0.20),
        ("MGCO", "path.step_2", 0.15),  # the consensus step is 12%
        ("MSCO", "moat.class", "Narrow"),
        ("MSCO", "earnings.cycle_gap", 1.0),
        ("HGCO", "margin.target", 0.25),
        ("HGCO", "capital.sales_to_capital", 1.5),
        ("HGCO", "path.hold", 0.30),
        ("YGCO", "balance.cash", 500.0),
        ("DCCO", "decline.rate", -0.02),
        ("DCCO", "capital.sales_to_capital", 1.8),
    ],
)
def test_one_override_equals_the_engine_with_that_input(
    symbol: str, tag: OverrideTag, value: float | str, policy: Policy, deciles: Deciles
) -> None:
    inputs = FIXTURES[symbol]()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    review = review_company(inputs, deciles, policy, TODAY, [OVERRIDE(tag, value)], mechanical)
    direct = value_company(inputs, deciles, policy, TODAY, {tag: OVERRIDE(tag, value)})
    assert review.result.value is not None and mechanical.value is not None
    assert direct.value is not None
    assert review.result.value == pytest.approx(direct.value, abs=1e-9)
    assert review.result.value != mechanical.value
    assert len(review.bridge) == 1
    assert review.bridge[0].delta == pytest.approx(review.result.value - mechanical.value, abs=1e-9)
    assert review.bridge[0].old == current_reading(mechanical, tag)
    assert review.bridge[0].new == value and review.bridge[0].refusal is None
    assert review.mechanical_value == mechanical.value and review.override_ids == (1,)
    judged = [i for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert [i.name for i in judged] == [tag]
    source = judged[0].provenance.source
    assert source.startswith("override 1") and "agent" in source and "claude-opus-5-5" in source
    assert review.result.inputs[-1] == judged[0]


@pytest.mark.parametrize("symbol", sorted(FIXTURES))
def test_an_override_at_the_engines_reading_moves_nothing(
    symbol: str, policy: Policy, deciles: Deciles
) -> None:
    """For every tag its route reads, an override at the engine's own reading leaves the value
    as it was, so a bridge line whose old and new agree carries no delta."""
    inputs = FIXTURES[symbol]()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert mechanical.route is not None
    tried: list[OverrideTag] = []
    for tag in BRIDGE_ORDER:
        old = current_reading(mechanical, tag)
        if mechanical.route not in TAGS[tag].routes or old is None:
            continue
        judged = value_company(inputs, deciles, policy, TODAY, {tag: OVERRIDE(tag, old)})
        assert judged.refusal == mechanical.refusal, tag
        if mechanical.value is None:
            assert judged.value is None, tag
        else:
            assert judged.value == pytest.approx(mechanical.value, abs=1e-9), tag
        tried.append(tag)
    assert tried[0] == "phase" and len(tried) > 1


def test_two_overrides_sum_to_the_difference(policy: Policy, deciles: Deciles) -> None:
    inputs = mature_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    # given moat first; the bridge reads the belief first, the method's order
    overrides = [OVERRIDE("moat.class", "Narrow", 2), OVERRIDE("growth.belief", 0.08, 1)]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    assert [line.tag for line in review.bridge] == ["growth.belief", "moat.class"]
    assert [line.override_id for line in review.bridge] == [1, 2]
    assert review.override_ids == (1, 2)
    assert review.result.value is not None and mechanical.value is not None
    deltas = [line.delta for line in review.bridge]
    assert all(d is not None for d in deltas)
    assert sum(d for d in deltas if d is not None) == pytest.approx(
        review.result.value - mechanical.value, abs=1e-9
    )
    belief_only = value_company(
        inputs, deciles, policy, TODAY, {"growth.belief": OVERRIDE("growth.belief", 0.08, 1)}
    )
    assert belief_only.value is not None
    assert deltas[0] == pytest.approx(belief_only.value - mechanical.value, abs=1e-9)
    assert review.bridge[1].old == "Wide"
    # the review's levels read the reviewed moat
    assert review.result.levels is not None and review.result.levels != mechanical.levels


def test_the_cycle_gap_line_follows_the_non_recurring_gap(policy: Policy, deciles: Deciles) -> None:
    """Given the cycle gap first, the bridge reads the non-recurring gap first, the method's order;
    the cycle line's old value is the engine's nil, and the two deltas sum to the difference."""
    inputs = mature_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    overrides = [OVERRIDE("earnings.cycle_gap", 1.0, 2), OVERRIDE("earnings.nri_gap", 0.5, 1)]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    tags = [line.tag for line in review.bridge]
    assert tags == ["earnings.nri_gap", "earnings.cycle_gap"]
    assert tags == sorted(tags, key=BRIDGE_ORDER.index)
    nri, cycle = review.bridge
    assert nri.old == mechanical.intermediates["nri_gap"] and nri.new == 0.5
    assert cycle.old == 0.0 and cycle.new == 1.0 and cycle.override_id == 2
    assert review.result.value is not None and mechanical.value is not None
    assert nri.delta is not None and cycle.delta is not None and cycle.delta < 0
    assert nri.delta + cycle.delta == pytest.approx(
        review.result.value - mechanical.value, abs=1e-9
    )
    judged = [i.name for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert judged == ["earnings.nri_gap", "earnings.cycle_gap"]


def test_the_two_new_lines_close_the_bridge(policy: Policy, deciles: Deciles) -> None:
    """Given out of order, the count's line and the outside value's close the bridge, in that
    order (spec 2026-11-09 8). The count's old value is the engine's count, and on Mature Growth a
    count raised with NTM net income leaves the value a share; the outside line's old value is the
    engine's nil and its delta the figure. The JUDGMENT entries carry each input's unit."""
    inputs = mature_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    count = mechanical.intermediates["shares"] * 1.06
    overrides = [
        OVERRIDE("value.outside", 12.0, 3),
        OVERRIDE("shares.diluted", count, 2),
        OVERRIDE("growth.belief", 0.08, 1),
    ]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    assert [line.tag for line in review.bridge] == [
        "growth.belief",
        "shares.diluted",
        "value.outside",
    ]
    _, shares, outside = review.bridge
    assert shares.old == mechanical.intermediates["shares"] and shares.new == count
    assert shares.delta == pytest.approx(0.0, abs=1e-9)
    assert outside.old == 0.0 and outside.new == 12.0
    assert outside.delta == pytest.approx(12.0)
    assert review.result.value is not None and mechanical.value is not None
    deltas = [line.delta for line in review.bridge if line.delta is not None]
    assert sum(deltas) == pytest.approx(review.result.value - mechanical.value, abs=1e-9)
    judged = [(i.name, i.unit) for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert judged == [
        ("growth.belief", "ratio"),
        ("shares.diluted", "shares"),
        ("value.outside", "USD a share"),
    ]
    assert result_from_json(result_to_json(review.result)) == review.result


def test_a_step_override_moves_the_charge_only_where_the_revenue_step_is_missing(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-09 6.2: an earnings step override moves the earnings path and, where the
    consensus gives no revenue step, the growth the charge pays for, which falls back on the
    earnings step; it never moves a revenue step the consensus gives."""
    plain = mature_growth_inputs()  # no consensus revenue
    revenue = (24_000e6, 25_920e6, 27_734.4e6)  # up 8% then 7%
    rows = tuple(
        replace(a, revenue=x, analysts_revenue=20)
        for a, x in zip(plain.annual_estimates, revenue, strict=True)
    )
    for inputs, paid_for in ((plain, 0.15), (replace(plain, annual_estimates=rows), 0.08)):
        mechanical = value_company(inputs, deciles, policy, TODAY)
        overrides = [OVERRIDE("path.step_2", 0.15)]
        im = review_company(inputs, deciles, policy, TODAY, overrides, mechanical).result
        assert im.intermediates["path_steps"][0] == 0.15
        charge = im.intermediates["charge"]
        assert charge["growth_by_year"][0] == pytest.approx(paid_for)
        assert charge["revenue_steps"] == mechanical.intermediates["charge"]["revenue_steps"]


def test_the_hold_is_read_on_the_overriding_belief(policy: Policy, deciles: Deciles) -> None:
    """The hold is the last year whose next growth is above the belief in force: at a belief of
    13%, MGCO's steps of 12% and 10% are below it, so the return fades from year 1."""
    inputs = mature_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert mechanical.intermediates["charge"]["hold_years"] == 6
    overrides = [OVERRIDE("growth.belief", 0.13)]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    charge = review.result.intermediates["charge"]
    assert charge["hold_years"] == 0
    runway, terminal = mechanical.intermediates["runway_return"]["value"], 0.13
    assert charge["return_by_year"][0] == pytest.approx(runway + (terminal - runway) / 20)


def test_a_start_up_overridden_to_young_growth_is_valued(policy: Policy, deciles: Deciles) -> None:
    """SUCO has no trailing revenue, so the revenue-growth route, not the Start-up one, refuses it
    on its own first guard; the bridge starts at no mechanical value."""
    inputs = start_up_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    review = review_company(
        inputs, deciles, policy, TODAY, [OVERRIDE("phase", "Young Growth")], mechanical
    )
    assert review.mechanical_value is None
    assert review.result.phase.phase == "Young Growth"
    assert review.result.refusal == "no trailing revenue"
    assert review.bridge[0].old == "Start-up" and review.bridge[0].new == "Young Growth"
    assert review.bridge[0].delta is None and review.bridge[0].refusal == "no trailing revenue"


def test_a_reclassified_start_up_carries_its_whole_value_on_the_first_line(
    policy: Policy, deciles: Deciles
) -> None:
    """A mechanical refusal that an override turns into a value starts the bridge at no mechanical
    value: the first valuing line's delta is the whole value (spec 10.4). The Young Growth company
    with no revenue in fiscal 2022, three years back, is a Start-up; its trailing figures and
    consensus value it on the revenue-growth route."""
    young = young_growth_inputs()
    series = tuple(
        replace(fy, revenue=0.0, operating_income=0.0) if fy.year == 2022 else fy
        for fy in young.series
    )
    inputs = replace(young, series=series)
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert mechanical.route == "start-up" and mechanical.value is None
    phase, cash = OVERRIDE("phase", "Young Growth", 2), OVERRIDE("balance.cash", 500e6, 3)
    review = review_company(inputs, deciles, policy, TODAY, [cash, phase], mechanical)
    young_only = value_company(inputs, deciles, policy, TODAY, {"phase": phase})
    assert review.result.route == "revenue-growth" and review.result.value is not None
    assert young_only.value is not None
    first, second = review.bridge
    assert first.tag == "phase" and first.old == "Start-up" and first.new == "Young Growth"
    assert first.delta == pytest.approx(young_only.value, abs=1e-9)
    assert second.old == 3_000e6
    assert second.delta == pytest.approx(review.result.value - young_only.value, abs=1e-9)


def test_the_route_check_reads_the_overridden_phase(policy: Policy) -> None:
    assert route_of("Young Growth") == "revenue-growth"
    assert check_override(
        "margin.target", 0.2, route_of("Young Growth"), policy, ["filing"], "lasting", None
    ) == ("applied", "")
    refused, _ = check_override(
        "margin.target", 0.2, route_of("Mature Growth"), policy, ["filing"], "lasting", None
    )
    assert refused == "refused-route"


def test_a_refusing_step_ends_the_bridge(policy: Policy, deciles: Deciles) -> None:
    inputs = high_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    review = review_company(
        inputs,
        deciles,
        policy,
        TODAY,
        [OVERRIDE("capital.sales_to_capital", 0.1)],
        mechanical,
    )
    line = review.bridge[0]
    assert line.refusal == "value not positive under the reinvestment charge"
    assert line.delta is None
    assert review.result.value is None
    assert review.result.refusal == line.refusal


def test_a_refused_step_is_skipped_by_the_next_delta(policy: Policy, deciles: Deciles) -> None:
    """A line after a refusing step measures from the last step that valued, so the deltas still sum
    to the reviewed value less the mechanical one."""
    inputs = high_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    overrides = [
        OVERRIDE("balance.cash", 1e13, 2),  # enough cash to carry the reinvestment
        OVERRIDE("capital.sales_to_capital", 0.1, 1),
    ]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    capital, cash = review.bridge
    assert capital.tag == "capital.sales_to_capital" and cash.tag == "balance.cash"
    assert capital.delta is None and capital.refusal is not None
    assert review.result.value is not None and mechanical.value is not None
    assert cash.refusal is None
    assert cash.delta == pytest.approx(review.result.value - mechanical.value, abs=1e-9)


def test_no_override_leaves_the_golden_bit_for_bit(policy: Policy, deciles: Deciles) -> None:
    for build in FIXTURES.values():
        inputs = build()
        mechanical = value_company(inputs, deciles, policy, TODAY)
        assert result_to_json(value_company(inputs, deciles, policy, TODAY, {})) == (
            result_to_json(mechanical)
        )
        review = review_company(inputs, deciles, policy, TODAY, [], mechanical)
        assert review.result == mechanical and review.bridge == () and review.override_ids == ()


def test_a_reviewed_result_round_trips_as_json(policy: Policy, deciles: Deciles) -> None:
    inputs = mature_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    review = review_company(
        inputs, deciles, policy, TODAY, [OVERRIDE("moat.class", "Narrow")], mechanical
    )
    assert REVIEW_METHOD == "fairband-review/1"
    assert result_from_json(result_to_json(review.result)) == review.result


def test_one_input_takes_one_override(policy: Policy, deciles: Deciles) -> None:
    inputs = mature_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    twice = [OVERRIDE("growth.belief", 0.08, 1), OVERRIDE("growth.belief", 0.09, 2)]
    with pytest.raises(ValueError, match="one override for each input"):
        review_company(inputs, deciles, policy, TODAY, twice, mechanical)
