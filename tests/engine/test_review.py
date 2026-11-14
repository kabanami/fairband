"""The review: the engine under an agent's overrides, applied one at a time in the method's order to
build the bridge from the mechanical value (spec 2026-11-06 Tier 2, 10.4 and 20.2)."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from support.engine_companies import (
    annual,
    decline_inputs,
    high_growth_inputs,
    mature_growth_inputs,
    mature_stable_inputs,
    start_up_inputs,
    young_growth_inputs,
)

from fairband.engine.anchor import StockPayHistory
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
from fairband.engine.types import ValuationResult, result_from_json, result_to_json
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
        ("DCCO", "balance.minority", 50e6),  # the sheet presents none
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


def test_the_minority_interest_line_follows_the_cash_line(policy: Policy, deciles: Deciles) -> None:
    """Spec 2026-11-13 13 on HGCO, 100 m shares, whose newest sheet presents no minority interest.
    Given before the cash, a ``balance.minority`` of $500 m applies after it: the cash at $2,000 m
    in place of $3,000 m takes $1,000 m ÷ 100 m, $10.00 a share, off first; then the minority
    interest, its old value none, the line the sheet does not present, takes $500 m ÷ 100 m, $5.00
    a share, off. The deltas sum to the reviewed value less the mechanical one, and the JUDGMENT
    entry stands in place of the DATA entry ``minority_interest``."""
    inputs = high_growth_inputs()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert current_reading(mechanical, "balance.minority") is None
    overrides = [OVERRIDE("balance.minority", 500e6, 2), OVERRIDE("balance.cash", 2_000e6, 1)]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    assert [line.tag for line in review.bridge] == ["balance.cash", "balance.minority"]
    cash, minority = review.bridge
    assert (cash.old, cash.new, cash.override_id) == (3_000e6, 2_000e6, 1)
    assert cash.delta == pytest.approx(-10.0)
    assert (minority.old, minority.new, minority.override_id) == (None, 500e6, 2)
    assert minority.delta == pytest.approx(-5.0) and minority.refusal is None
    assert review.result.value is not None and mechanical.value is not None
    assert cash.delta + minority.delta == pytest.approx(
        review.result.value - mechanical.value, abs=1e-9
    )
    assert review.result.intermediates["minority_interest"] == 500e6
    assert "minority_interest" in [i.name for i in mechanical.inputs]
    assert "minority_interest" not in [i.name for i in review.result.inputs]
    judged = [(i.name, i.unit) for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert judged == [("balance.cash", "USD"), ("balance.minority", "USD")]


def _codes(result: ValuationResult) -> list[str]:
    return [f.code for f in result.flags]


def test_a_count_that_reconciles_the_market_cap_clears_the_share_count_gap(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-13 8: in a review the warning reads the count in force. MGCO's market cap at
    4.6 times the price times its count warns; an agent's ``shares.diluted`` of 4.6 times the
    count reconciles the two, and the reviewed result carries no ``share-count-gap``. A count
    that does not reconcile them keeps it, its sentence on the agent's count."""
    base = mature_growth_inputs()
    assert base.market_cap is not None and base.shares_diluted is not None
    inputs = replace(base, market_cap=base.market_cap * 4.6)
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert "share-count-gap" in _codes(mechanical)
    count = [OVERRIDE("shares.diluted", base.shares_diluted * 4.6)]
    review = review_company(inputs, deciles, policy, TODAY, count, mechanical)
    assert review.result.value is not None and [line.tag for line in review.bridge] == [
        "shares.diluted"
    ]
    assert "share-count-gap" not in _codes(review.result)
    short = [OVERRIDE("shares.diluted", base.shares_diluted * 2.0)]
    halfway = review_company(inputs, deciles, policy, TODAY, short, mechanical)
    [gap] = [f for f in halfway.result.flags if f.code == "share-count-gap"]
    assert "the diluted count of 2,000.0 million shares" in gap.sentence
    assert "a ratio of 2.30," in gap.sentence


def _excluding(street: float = 8.50) -> CompanyInputs:
    """MGCO with a street trailing EPS of ``street``. Its after-tax stock pay a share is 400 m ×
    0.75 ÷ 1,000 m = 0.30, so the test reads excludes-sbc at a gap over GAAP 5.30 of 0.15 or
    more, and reason 3 of ``sbc-basis-uncertain`` holds at 10 × 0.30 = 3.0 or more: 8.50 lies
    3.20 above."""
    return replace(mature_growth_inputs(), street_ttm_eps=street)


_REASON_3 = (
    "The street trailing EPS is ${gap} above the GAAP one, {times} times the stock pay of $0.30 a "
    "share after tax: the adjusted figure leaves out far more than stock pay, and the figures "
    "cannot say whether it leaves out stock pay too."
)


def test_an_agent_s_basis_moves_the_anchor_by_the_adjustment(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-13 7.2: on MGCO at a street EPS of 8.50 the test reads excludes-sbc and the
    anchor takes the 0.30 off; an agent's ``includes`` gives it back, exactly the mechanical
    adjustment, on one bridge line under the basis's tag, and ``sbc-basis-uncertain`` goes, the
    agent decided. The other way, MGCO as it is reads includes-sbc, and an agent's ``excludes``
    takes 0.30 off its 5.90."""
    inputs = _excluding()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    found = mechanical.intermediates["anchor"]
    assert mechanical.intermediates["sbc_basis"] == "excludes-sbc"
    assert found["sbc_adjustment_per_share"] == pytest.approx(0.30)
    assert "sbc-basis-uncertain" in _codes(mechanical)
    basis = [OVERRIDE("earnings.sbc_basis", "includes")]
    review = review_company(inputs, deciles, policy, TODAY, basis, mechanical)
    anchor = review.result.intermediates["anchor"]
    assert review.result.intermediates["sbc_basis"] == "includes-sbc"
    assert anchor["sbc_adjustment_per_share"] == 0.0 and anchor["ntm_eps"] == anchor["ntm_eps_raw"]
    assert anchor["ntm_eps"] - found["ntm_eps"] == pytest.approx(
        found["sbc_adjustment_per_share"], abs=1e-12
    )
    [line] = review.bridge
    assert (line.tag, line.old, line.new, line.refusal) == (
        "earnings.sbc_basis",
        "excludes",
        "includes",
        None,
    )
    assert review.result.value is not None and mechanical.value is not None
    assert line.delta == pytest.approx(review.result.value - mechanical.value, abs=1e-9)
    assert line.delta is not None and line.delta > 0
    assert "sbc-basis-uncertain" not in _codes(review.result)
    [judged] = [i for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert (judged.name, judged.value, judged.unit) == ("earnings.sbc_basis", None, "basis")
    assert judged.note == "includes: because"

    plain = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    excludes = [OVERRIDE("earnings.sbc_basis", "excludes")]
    charged = review_company(mature_growth_inputs(), deciles, policy, TODAY, excludes, plain)
    assert charged.result.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.90 - 0.30)
    assert charged.bridge[0].old == "includes"
    assert charged.bridge[0].delta is not None and charged.bridge[0].delta < 0


def test_an_agent_s_stock_pay_charges_the_anchor_and_settles_the_notes(
    policy: Policy, deciles: Deciles
) -> None:
    """MGCO at a street EPS of 8.50 with its stored stock pay at nil while fiscal 2025 shows
    $380 m: the test reads excludes-sbc on a stock pay of nil (3.20 is at or above half of 0),
    the anchor takes nothing off, ``stock-pay-missing`` shows, and ``sbc-basis-uncertain`` has no
    stock pay a share to read. An agent's $400 m charges 400 × 0.75 ÷ 1,000 = 0.30 a share, so the
    NTM EPS falls from 5.90 to 5.60; ``stock-pay-missing`` goes, the agent decided; and
    ``sbc-basis-uncertain`` reads the stock pay in force, the agent's: 3.20 is 10.7 times 0.30,
    at or above 10, so reason 3 holds. The JUDGMENT entry stands in place of ``sbc_ttm``."""
    base = _excluding()
    assert base.trailing is not None
    inputs = replace(
        base,
        trailing=replace(base.trailing, sbc=0.0),
        stock_pay=StockPayHistory(4, 2025, 380e6),
    )
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert mechanical.intermediates["sbc_basis"] == "excludes-sbc"
    assert mechanical.intermediates["anchor"]["sbc_adjustment_per_share"] == 0.0
    assert "stock-pay-missing" in _codes(mechanical)
    assert "sbc-basis-uncertain" not in _codes(mechanical)
    pay = [OVERRIDE("earnings.sbc", 400e6)]
    review = review_company(inputs, deciles, policy, TODAY, pay, mechanical)
    im = review.result.intermediates
    assert im["sbc_ttm"] == 400e6 and im["anchor"]["ntm_eps"] == pytest.approx(5.60)
    [line] = review.bridge
    assert (line.tag, line.old, line.new) == ("earnings.sbc", 0.0, 400e6)
    assert line.delta is not None and line.delta < 0
    assert "stock-pay-missing" not in _codes(review.result)
    [uncertain] = [f for f in review.result.flags if f.code == "sbc-basis-uncertain"]
    assert uncertain.sentence == _REASON_3.format(gap="3.20", times="10.7")
    entries = [(i.name, i.tag, i.unit) for i in review.result.inputs if "sbc" in i.name]
    assert entries == [("earnings.sbc", "JUDGMENT", "USD")]


def test_the_basis_note_reads_the_gaap_figure_the_test_read(
    policy: Policy, deciles: Deciles
) -> None:
    """Under an applied ``earnings.nri_gap`` the basis test reads GAAP EPS less the agent's
    correction, and so does reason 3 of ``sbc-basis-uncertain``. MGCO at a street EPS of 8.20:
    2.90 above the reported 5.30 is under 10 × 0.30 = 3.0, so no note. An agent's gap of 0.25
    against the 0.05 found corrects GAAP EPS by 0.20 to 5.10, and 8.20 lies 3.10 above it, 10.3
    times 0.30: reason 3 holds, on the gap the test judged."""
    inputs = _excluding(8.20)
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert mechanical.intermediates["sbc_basis"] == "excludes-sbc"
    assert mechanical.intermediates["nri_gap"] == pytest.approx(0.05)
    assert "sbc-basis-uncertain" not in _codes(mechanical)
    gap = [OVERRIDE("earnings.nri_gap", 0.25)]
    review = review_company(inputs, deciles, policy, TODAY, gap, mechanical)
    assert review.result.intermediates["sbc_basis"] == "excludes-sbc"
    assert "large-nri" not in _codes(review.result)  # 0.25 is 4.7% of 5.30, under 5%
    [uncertain] = [f for f in review.result.flags if f.code == "sbc-basis-uncertain"]
    assert uncertain.sentence == _REASON_3.format(gap="3.10", times="10.3")


def test_the_two_stock_pay_lines_each_move_the_value_in_the_bridge_s_order(
    policy: Policy, deciles: Deciles
) -> None:
    """Design 16, the two stock-pay inputs together with no guided anchor. MGCO at a street EPS of
    8.50 reads excludes-sbc and takes 400 × 0.75 ÷ 1,000 = 0.30 off its 5.90: an NTM EPS of 5.60.
    Given the basis first, the bridge reads the figure first (``BRIDGE_ORDER``). The agent's
    $600 m charges 600 × 0.75 ÷ 1,000 = 0.45, so the NTM EPS falls to 5.45 (the test still reads
    excludes: 3.20 is at or above half of 0.45); the agent's ``includes`` then takes nothing off,
    and the NTM EPS is the consensus's 5.90, MGCO's own figure. The value is linear in the NTM
    EPS, MGCO's value V at 5.90, so the two deltas are V × (5.45 − 5.60) ÷ 5.90 and
    V × (5.90 − 5.45) ÷ 5.90, and they sum to the reviewed value, V, less the mechanical one."""
    inputs = _excluding()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    v = value_company(mature_growth_inputs(), deciles, policy, TODAY).value
    assert v is not None and mechanical.value is not None
    assert mechanical.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.60)
    overrides = [OVERRIDE("earnings.sbc_basis", "includes", 2), OVERRIDE("earnings.sbc", 600e6, 1)]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    tags = [line.tag for line in review.bridge]
    assert tags == ["earnings.sbc", "earnings.sbc_basis"]
    assert tags == sorted(tags, key=BRIDGE_ORDER.index)
    pay, basis = review.bridge
    assert (pay.old, pay.new, pay.override_id) == (400e6, 600e6, 1)
    assert (basis.old, basis.new, basis.override_id) == ("excludes", "includes", 2)
    assert pay.delta == pytest.approx(v * (5.45 - 5.60) / 5.90, abs=1e-9)
    assert basis.delta == pytest.approx(v * (5.90 - 5.45) / 5.90, abs=1e-9)
    assert review.result.value == pytest.approx(v, abs=1e-9)
    assert pay.delta + basis.delta == pytest.approx(
        review.result.value - mechanical.value, abs=1e-9
    )
    judged = [i.name for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert judged == ["earnings.sbc", "earnings.sbc_basis"]


def test_a_stock_pay_input_under_an_ntm_anchor_moves_nothing(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-13 7.2 and method 14.4: under an applied ``earnings.ntm`` the guided EPS stands
    in for the consensus less the adjustment, so a basis and a stock pay applied after it each
    apply with a bridge line of zero, though the anchor's basis and stock pay follow them."""
    inputs = _excluding()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    overrides = [
        OVERRIDE("earnings.sbc_basis", "includes", 3),
        OVERRIDE("earnings.sbc", 600e6, 2),
        OVERRIDE("earnings.ntm", 6.10, 1),
    ]
    review = review_company(inputs, deciles, policy, TODAY, overrides, mechanical)
    assert [line.tag for line in review.bridge] == [
        "earnings.ntm",
        "earnings.sbc",
        "earnings.sbc_basis",
    ]
    _, pay, basis = review.bridge
    assert (pay.refusal, pay.delta) == (None, 0.0)
    assert (basis.refusal, basis.delta) == (None, 0.0)
    im = review.result.intermediates
    assert (im["sbc_basis"], im["sbc_ttm"]) == ("includes-sbc", 600e6)
    assert im["anchor"]["ntm_eps"] == 6.10


def test_the_stock_pay_notes_do_not_show_under_a_guided_anchor(
    policy: Policy, deciles: Deciles
) -> None:
    """The controller's ruling on the whole-branch review's Minor 2: under an applied
    ``earnings.ntm`` the guided EPS stands in for the consensus less the stock-pay adjustment, so
    both stock-pay inputs are moot (spec 2026-11-13 7.2) and neither note shows, as ``thin-ntm``
    does not. MGCO with one trailing quarter at nil while fiscal 2025 shows $500 m, and a
    non-recurring gain of 0.50 a share (9.4% of the trailing EPS of 5.30, so ``large-nri``), on a
    test that reads includes-sbc (5.35 less 5.30 is under half of 400 × 0.75 ÷ 1,000 = 0.30) on a
    material stock pay (0.30 is 5.6% of 5.35): the mechanical row carries both notes. A review
    under another input keeps them."""
    inputs = replace(
        mature_growth_inputs(), stock_pay=StockPayHistory(1, 2025, 500e6), gf_eps_without_nri=4.80
    )
    mechanical = value_company(inputs, deciles, policy, TODAY)
    notes = {"stock-pay-missing", "sbc-basis-uncertain"}
    assert notes <= set(_codes(mechanical))
    guided = review_company(
        inputs, deciles, policy, TODAY, [OVERRIDE("earnings.ntm", 6.10)], mechanical
    )
    assert guided.result.value is not None
    assert not notes & set(_codes(guided.result))
    belief = review_company(
        inputs, deciles, policy, TODAY, [OVERRIDE("growth.belief", 0.08)], mechanical
    )
    assert notes <= set(_codes(belief.result))


def test_the_thin_ntm_note_does_not_show_under_a_guided_anchor(
    policy: Policy, deciles: Deciles
) -> None:
    """Spec 2026-11-13 9: MGCO with an NTM quarter on 4 EPS analysts carries ``thin-ntm``; a review
    under an applied ``earnings.ntm`` does not, its anchor being the guidance. A review under
    another input keeps the note, and the two reviews keep the mechanical row's margins."""
    base = mature_growth_inputs()
    q = base.quarter_estimates
    inputs = replace(base, quarter_estimates=(*q[:3], replace(q[3], analysts=4)))
    mechanical = value_company(inputs, deciles, policy, TODAY)
    assert "thin-ntm" in _codes(mechanical)
    guided = review_company(
        inputs, deciles, policy, TODAY, [OVERRIDE("earnings.ntm", 6.10)], mechanical
    )
    assert guided.result.value is not None and "thin-ntm" not in _codes(guided.result)
    belief = review_company(
        inputs, deciles, policy, TODAY, [OVERRIDE("growth.belief", 0.08)], mechanical
    )
    assert "thin-ntm" in _codes(belief.result)
    margins = mechanical.intermediates["margin_history"]
    for review in (guided, belief):
        assert review.result.intermediates["margin_history"] == margins


def test_a_guided_anchor_stands_in_for_the_annual_figure(policy: Policy, deciles: Deciles) -> None:
    """Spec 2026-11-13 9a: MGCO's NTM window with its first quarter, fiscal 2026's Q4, on 3
    analysts and an annual consensus of $5.70 for fiscal 2026 on 12 reads 0.25 × 5.70 + 0.75 ×
    6.00 = 5.925, so ``thin-ntm`` does not show. Under an applied ``earnings.ntm`` of 6.10 the
    guided EPS stands in for that figure, the bridge line reads it as the old value and sums to
    the reviewed value, and the note stays silent."""
    base = mature_growth_inputs()
    q = base.quarter_estimates
    inputs = replace(
        base,
        quarter_estimates=(replace(q[0], analysts=3), *q[1:]),
        annual_estimates=(annual(2026, 5_700e6, 5.70, 12), *base.annual_estimates),
    )
    mechanical = value_company(inputs, deciles, policy, TODAY)
    found = mechanical.intermediates["anchor"]
    assert (found["source"], found["ntm_eps"]) == ("annual", pytest.approx(5.925))
    review = review_company(
        inputs, deciles, policy, TODAY, [OVERRIDE("earnings.ntm", 6.10)], mechanical
    )
    anchor = review.result.intermediates["anchor"]
    assert anchor["ntm_eps"] == 6.10 and anchor["ntm_eps_raw"] == pytest.approx(5.925)
    [line] = review.bridge
    assert (line.old, line.new) == (pytest.approx(5.925), 6.10)
    assert review.result.value is not None and mechanical.value is not None
    assert line.delta == pytest.approx(review.result.value - mechanical.value, abs=1e-9)
    assert "thin-ntm" not in _codes(mechanical) and "thin-ntm" not in _codes(review.result)


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
