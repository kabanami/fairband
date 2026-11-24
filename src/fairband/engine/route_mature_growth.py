"""The Mature Growth route (spec 6.6, steps 1 to 11, under the calibration spec 5).

Year 1 is the NTM anchor and years 2 and 3 the consensus path. When year 3's growth is above the
belief, years 4 to 3 + the policy's ``fade_years`` fade from it to the belief; the other years to
the runway N grow at the belief. The value is the reverse DCF with the reinvestment charge of spec
2026-11-09 6 (``RoicTerms``): each year pays for the next year's revenue growth, the consensus
revenue steps for years 2 and 3 (a missing one taking the earnings step, and so a thin one, whose
landing year has fewer than ``analyst_min`` revenue analysts or no count, spec 2026-11-14 6.2,
``anchor.path_steps``, and which is above ``thin_revenue_step_max``) fading to the belief as
the earnings path fades, at a return that holds at the runway return through the hold K, the last
year whose next earnings growth is above the belief, then fades in equal steps to the terminal
return in year N. K is read once, from the row's own path at the belief in force, and every
sensitivity and solve holds it. A year whose growth outruns its return pays out less than nothing;
the first such year raises "growth above return", which counts the rest, after the ROIC flags and
before the trailing ones, where the ``heavy-capex`` sentence names the return the charge starts
at. The two stock-pay notes, ``stock-pay-missing`` and ``sbc-basis-uncertain``, follow the
anchor's flags (spec 2026-11-13 7.1), on the anchor's refusal "no positive forward anchor" too,
which a stock-pay charge can itself cause, each silent under the input that decides it and both
under an applied ``earnings.ntm``, whose anchor is the guidance; the first reason of
``sbc-basis-uncertain`` reads the test of the warning ``one-time-items``, GAAP trailing EPS and
the street's apart by ``one_time_items_share`` or more, and is silent under an applied
``earnings.nri_gap`` as the warning is (spec 2026-11-19 7.3); the warning itself is Mature
Stable's alone. ``thin-ntm`` (spec 2026-11-13 9), a note on an
NTM window with a period of fewer than ``analyst_min`` EPS analysts or no count, takes the place
right after ``few-analysts``, silent under an applied ``earnings.ntm`` for the same reason.
``charge`` in the intermediates records the growth paid for, the return by year, the hold, the
revenue steps the charge read, the consensus's as found and where each read step came from
(``RevenueSteps``, spec 2026-11-14 6.3); ``sbc_ttm`` the trailing stock pay the anchor read.

Where a period of the NTM window in its last fiscal year has fewer than ``analyst_min`` EPS
analysts or no count, the anchor corrects the periods' sum by that year's annual consensus
(``anchor.annual_gap``, spec 2026-11-13 9a), and ``thin-ntm`` shows only on a thin period left
as it is. The ``anchor`` entry records the source, the periods' sum and the correction, and on
the annual source the ``ntm_eps`` and ``ntm_net_income`` DATA entries, which cite the quarterly
consensus on either source, carry the correction as their note, after any note assembly holds
for them (a pending split's).

The value is also computed at each policy runway and at each return of the sensitivity, and so is
the implied growth at the price. The sensitivity is keyed ``"runway"``, the row's own charge;
then the policy's ``roic_sensitivity`` values, each as the runway return with the moat's terminal
rule applied to it; then ``"ten-year"``, the ten-year aggregate ROIC as the runway return, not
floored, with the moat's terminal rule applied to it, ``None`` when the aggregate is unavailable
or not positive; each on the row's hold. The value-spread flag reads the first three, and
separately the runways, each the business's own value, before any figure outside it is added.

``growth_at_price`` rebuilds the growth path and the charges from the intermediates alone, the
``charge`` entry's revenue steps, the ones the charge read, and hold among them, so a stored
result moves to a new price without its inputs. The implied growth is the belief at which the
value equals the price, both paths' fades moving with it and the hold fixed; it is solved between
−50% and 200% a year, and ``None`` means no growth in that range reaches the price. The expected
return's growth reads the earnings path's rates from year 2.

``growth_cross_check`` runs the same anchor, path and charge for a Mature Stable row, on that
row's moat and returns, so its value is the one this route would reach (calibration spec 5.7).
It carries the keys the rebuild reads, so ``cross_check_at_price`` gives its implied growth at
any price by the same solve, from the intermediates alone.

Overrides (``method.md`` 14) through ``route_steps.chosen``: ``moat.class`` the moat, so the runway,
the terminal return and the margin of safety with it; ``return.runway`` the runway return of the
charge, the start of its fade (``RoicTerms.of``); ``earnings.nri_gap`` the non-recurring gap, the
whole of it, since the engine finds none (spec 2026-11-19 7.1), the anchor's basis test then taking
it off trailing GAAP EPS (``anchor.ntm_anchor``), so an override of nil moves nothing, while no
basis override is applied; ``earnings.sbc`` the trailing stock pay, in the basis test and the
adjustment, and ``earnings.sbc_basis`` the basis, in place of the test (spec 2026-11-13 7.2);
``path.step_2`` and ``path.step_3`` the consensus steps, before the check that the path stays above
−100%, a replaced step not counted thin nor named in ``step-series-disagree``, moving the growth the
charge pays for only in a year with no revenue step read, missing or thin, where the earnings step
stands in; ``revenue.step_2`` and ``revenue.step_3`` the revenue steps the charge pays for, in place
of the consensus's, a thin one's too, since an agent's step is never thin, the steps found kept
beside them (spec 2026-11-14 6.1); ``growth.belief`` the belief's rate, and the hold read on it;
``earnings.ntm``, the NTM EPS from a clear guidance, which stands in for the consensus less the SBC
adjustment, the NTM window's periods still required (``anchor.ntm_window``: four quarters, or two
half-years); ``earnings.ntm_nri`` a one-time amount a share that the consensus carries and that does
not recur (spec 2026-11-14 5), which the consensus less the SBC adjustment is taken less, a share on
the count the consensus is on, and which a guided EPS, standing in for the consensus with its items,
leaves unread; ``earnings.cycle_gap`` the correction to mid-cycle earnings, which the NTM EPS, the
consensus's or the guided one, is then taken less, before the positive-anchor refusal
(``anchor.ntm_anchor``). Nothing else reads the three: the basis test, the clean EPS and EPV read
the agent's non-recurring gap alone, and the forward EPS after stock pay, with its P/E, and the
``ntm_eps`` and ``ntm_net_income`` data entries are the consensus less the stock-pay adjustment in
force (``Anchor.ntm_eps_found``), which the two stock-pay inputs move, the ``ntm_eps`` entry giving
way to the JUDGMENT entry under the guided EPS. The forward EPS of the forward P/E is the
consensus as the analysts state it (``Anchor.ntm_eps_raw``), which no input moves (``method.md``
5.9). ``ntm_nri``, the one-time amount the anchor took off, nil
under the guided EPS, and ``cycle_gap`` are in the intermediates only under their overrides. The
cross-check reads the row's moat, returns and two gaps, and the consensus and belief as found: no
guided EPS, no one-time amount and no agent's revenue step.

``value.outside``, the value outside the business a share (``route_steps.outside_value``), comes
after the route's value: the result's value is the route's value a share plus the figure, which
the levels and the designation read, and so is each value by runway and by return, though the
value-spread flag reads them before the figure, the business's own; the intermediates'
``value_per_share`` stays the route's own, the business's, so the drawer's arithmetic
reproduces, and ``outside_value_per_share`` carries the figure under the override only. A sum at
or below zero refuses the row as a route value would. ``growth_at_price`` reads the price and
the sum: the multiples, the growth share and the expected return read them as they are, and the
implied growth, by runway and by return too, solves to the price less the figure, the business's
share of the price, which it reads from the intermediates.

The share count is two counts (spec 2026-11-14 4). ``Context.consensus_shares`` is the diluted
count, an agent's ``shares.diluted`` in place of the reported count, the count the consensus EPS
is on: NTM net income is the NTM EPS times it, and after-tax SBC a share, in the basis test, the
adjustment and ``sbc-basis-uncertain``, divides by it, so the agent's count can change the basis
test's reading where no basis override is applied, and on a basis that reads ``excludes-sbc`` on
a stock pay above zero it moves the adjustment, and with it the ``ntm_eps`` and
``ntm_net_income`` DATA entries; ``step-series-disagree`` names it. ``Context.shares``, the count
in force, adds an agent's ``shares.committed``, shares committed but not yet in that count nor in
the consensus: the value a share and the values by runway and by return divide by it, so x
committed shares on a count of n lower the value a share by x ÷ (n + x), and the implied growth
solves to the price times it. The intermediates keep ``shares``, the count in force, with
``shares_committed`` beside it under that override, and ``ntm_net_income`` on the diluted count,
so ``growth_at_price`` rebuilds both. The ``ntm_net_income`` DATA entry stays on the reported
count, ``None`` without one: the consensus less the stock-pay adjustment in force times the
reported count. The cross-check reads the same two counts.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from fractions import Fraction
from typing import Any, Literal

from fairband.engine.anchor import (
    NO_POSITIVE_ANCHOR,
    Anchor,
    Belief,
    Path,
    QuarterEstimate,
    base_fiscal_year,
    belief_from_sales,
    few_analysts,
    ntm_anchor,
    ntm_window,
    path_steps,
    step_series_flag,
    thin_ntm_flag,
)
from fairband.engine.flags import (
    long_runway_flag,
    one_time_items_flag,
    one_time_share,
    sbc_basis_uncertain_flag,
    stock_pay_missing_flag,
    value_spread_flag,
)
from fairband.engine.mature_growth import (
    Charge,
    GrowthPath,
    charge_growth,
    first_negative_year,
    growth_rates,
    hold_years,
    implied_growth,
    negative_years,
    return_by_year,
    value_at_belief,
)
from fairband.engine.multiples import epv, growth_share
from fairband.engine.overrides import OverrideTag
from fairband.engine.roic import terminal_roic
from fairband.engine.route_steps import (
    Context,
    Refused,
    RoicTerms,
    Valued,
    business_price,
    charge_for,
    chosen,
    committed_entry,
    common_inputs,
    common_rules,
    cycle_entry,
    cycle_gap,
    data,
    eps,
    expected,
    income,
    money,
    multiples_at,
    ntm_nri_entry,
    outside_entry,
    outside_value,
    per_share,
    present,
    price_facts_for,
    revenue_by_fiscal_year,
    rule,
    table_moat,
    trailing_flags,
)
from fairband.engine.types import Flag
from fairband.policy import Moat, Policy

_IMPLIED_HI = 2.0  # the highest growth the implied-growth solve tries: 200% a year
_NOT_POSITIVE = "value not positive under the reinvestment charge"
_STEP_TAGS: tuple[OverrideTag, OverrideTag] = ("path.step_2", "path.step_3")
# Where the revenue step of a year the charge reads comes from (spec 2026-11-14 6.3).
RevenueSource = Literal["consensus", "agent", "thin", "none"]
Steps = tuple[float | None, float | None]


@dataclass(frozen=True)
class RevenueSteps:
    """The revenue steps of years 2 and 3 for the charge (spec 2026-11-14 6.3): ``read``, the steps
    the charge pays for, ``None`` where the earnings step of the year stands in; ``found``, the
    consensus's steps as found, ``None`` where missing; and ``source``, for each year, where the
    step read comes from: ``"consensus"``, the step as found; ``"agent"``, an agent's
    ``revenue.step_2`` or ``revenue.step_3`` in its place; ``"thin"``, the step found left out,
    its landing year on fewer than ``analyst_min`` revenue analysts or no count (spec 2026-11-14
    6.2) and the step above ``thin_revenue_step_max``; ``"none"``, no step at all."""

    read: Steps
    found: Steps
    source: tuple[RevenueSource, RevenueSource]


def _as_found(path: Path) -> RevenueSteps:
    """The consensus revenue steps of ``path`` as the charge reads them without an agent's: the
    steps the thin rule reads, ``Path.revenue_steps``, the steps found, ``Path.revenue_found``,
    and each year's source, ``thin`` where the rule left the step found out
    (``Path.revenue_thin``), else the consensus, or none where the consensus gives no step."""
    found, thin = path.revenue_found, path.revenue_thin
    source = (_found_source(found[0], thin[0]), _found_source(found[1], thin[1]))
    return RevenueSteps(path.revenue_steps, found, source)


def _found_source(step: float | None, thin: bool = False) -> RevenueSource:
    if thin:
        return "thin"
    return "none" if step is None else "consensus"


def value_mature_growth(c: Context) -> Valued | Refused:
    i, t, policy = c.inputs, c.trailing, c.policy
    found = _anchor_and_path(c, own=True)
    if isinstance(found, Refused):
        return found
    anchor, path, base_year, belief, revenue = found
    moat = chosen(c, "moat.class", table_moat(i))
    runway_return: float | None = chosen(c, "return.runway", None)
    roic = RoicTerms.of(
        i.capital_years,
        moat,
        policy,
        runway_override=runway_return,
        revenue=revenue_by_fiscal_year(i),
    )
    growth, charge = _growth_and_charge(anchor, path, revenue, belief, moat, roic, policy)
    value_total = value_at_belief(growth, charge)
    value = value_total / c.shares
    outside = outside_value(c)
    # the business's own values: the value-spread flag reads these, the stored maps add the figure
    own_by_runway = {
        str(n): value_at_belief(replace(growth, runway=n), charge) / c.shares
        for n in _runways(policy)
    }
    own_by_roic = {
        key: None if ch is None else value_at_belief(growth, ch) / c.shares
        for key, ch in _roic_charges(charge, roic.usable, moat, policy).items()
    }
    by_runway = {key: v + outside for key, v in own_by_runway.items()}
    by_roic = {key: None if v is None else v + outside for key, v in own_by_roic.items()}
    gap: float | None = chosen(c, "earnings.nri_gap", None)  # the engine finds none
    # the forward EPS is the analysts' as they state it; the second bears the stock-pay charge in
    # force, which an agent's stock pay or basis moves (method 5.9)
    e = eps(t, gap, anchor.ntm_eps_raw, anchor.ntm_eps_found)
    im: dict[str, Any] = {
        "anchor": {
            "ntm_eps_raw": anchor.ntm_eps_raw,
            "sbc_adjustment_per_share": anchor.sbc_adjustment_per_share,
            "ntm_eps": anchor.ntm_eps,
            # what the raw figure read (spec 2026-11-13 9a): the window's periods, or their sum
            # corrected by the annual consensus of the last fiscal year the window reaches
            "source": anchor.source,
            "periods_sum": anchor.periods_sum,
            "annual": _gap_entry(anchor),
        },
        "sbc_basis": anchor.basis,
        "sbc_ttm": anchor.sbc_ttm,
        "ntm_net_income": anchor.ntm_net_income,
        "path": {"base_year": base_year, "on_eps": path.on_eps, "analysts": list(path.analysts)},
        "path_steps": list(path.steps),
        "belief": asdict(belief),
        "moat": moat,
        "runway": growth.runway,
        "fade_years": growth.fade_years,
        "growth_rates": list(growth_rates(growth)),
        **roic.intermediates(),
        "charge_off": roic.charge_off,
        "charge": charge_entry(growth, charge, revenue),
        "shares": c.shares,
        **committed_entry(c),
        "value_total": value_total,
        "value_per_share": value,
        "value_by_runway": by_runway,
        "value_by_roic": by_roic,
        **outside_entry(c),
        "nri_gap": gap,
        **ntm_nri_entry(c, anchor.one_time),
        **cycle_entry(cycle_gap(c)),
        "eps": e,
        "epv": None if e["clean"] is None else epv(e["clean"], policy.required_return),
        **income(i.market_cap, t),
        "price_facts": price_facts_for(i.closes, c.price, c.today),
    }
    flags = (
        anchor.flags
        + _stock_pay_notes(c, anchor)
        + path.flags
        + roic.flags
        + present(_growth_above_return(growth, charge))
        + trailing_flags(i, t, policy, roic)
    )
    spread = present(value_spread_flag(list(own_by_roic.values())[:3], policy)) + present(
        value_spread_flag(list(own_by_runway.values()), policy)
    )
    if value + outside <= 0:
        return Refused(_NOT_POSITIVE, flags + spread, im)
    im |= growth_at_price(im, c.price, value + outside, policy)
    flags += present(long_runway(im, policy)) + spread
    corrected = _correction_note(anchor, policy)
    inputs = (
        *common_inputs(i, t, roic),
        data(i, "sbc_ttm", t.sbc, money(i), "statements"),
        # the consensus less the stock-pay adjustment in force, which an agent's stock pay or basis,
        # a gap that changes the basis, or an agent's count moves (method 14.4); a guided EPS or a
        # cycle gap is its own JUDGMENT entry
        data(
            i,
            "ntm_eps",
            anchor.ntm_eps_found,
            per_share(i),
            "estimates_quarter",
            _after_assembly(i.notes, "ntm_eps", corrected),
        ),
        data(
            i,
            "ntm_net_income",
            _on_reported(anchor, i.shares_diluted),
            money(i),
            "estimates_quarter",
            _after_assembly(i.notes, "ntm_net_income", corrected),
        ),
        data(i, "path_step_2", path.steps[0], "ratio", "estimates_annual"),
        data(i, "path_step_3", path.steps[1], "ratio", "estimates_annual"),
        data(i, "street_ttm_eps", i.street_ttm_eps, per_share(i)),
        *common_rules(policy, moat, roic.terminal),
        rule(policy, "runway_years", growth.runway, "years", f"{moat} moat"),
        rule(
            policy,
            "belief",
            belief.rate,
            "ratio",
            f"sales class {belief.sales_class}: Base Rate Book median {belief.median:.1%} "
            f"plus inflation {policy.inflation_addition:.1%}",
        ),
    )
    return Valued("mature-growth", value + outside, moat, im, inputs, flags)


def growth_cross_check(c: Context, moat: Moat, roic: RoicTerms) -> dict[str, Any]:
    """The growth route's value a share for a Mature Stable row (calibration spec 5.7), from the
    row's moat and returns, with what the value rests on: the anchor's net income, on the diluted
    count, the path, the belief, the runway and fade, and the returns of the charge; or only the
    refusal the route would give. The value a share divides by the count in force, so committed
    shares lower it as they lower the route's (spec 2026-11-14 4). ``cross_check_at_price`` adds
    the implied growth at a price, on the count in force."""
    found = _anchor_and_path(c)
    if isinstance(found, Refused):
        return {"refusal": found.reason}
    anchor, path, _, belief, revenue = found
    growth, charge = _growth_and_charge(anchor, path, revenue, belief, moat, roic, c.policy)
    value = value_at_belief(growth, charge) / c.shares
    if value <= 0:
        return {"refusal": _NOT_POSITIVE}
    return {
        "value_per_share": value,
        "ntm_net_income": anchor.ntm_net_income,
        "path_steps": list(path.steps),
        "belief": asdict(belief),
        "runway": growth.runway,
        "fade_years": growth.fade_years,
        "runway_return": roic.intermediates()["runway_return"],
        "terminal_roic": charge.terminal_roic,
        "charge_off": charge.charge_off,
        "charge": charge_entry(growth, charge, revenue),
        "refusal": None,
    }


def cross_check_at_price(
    gr: dict[str, Any], price: float, shares: float, policy: Policy
) -> dict[str, Any]:
    """The cross-check ``gr`` with its implied growth at ``price`` on ``shares``, by the growth
    route's solve on the path and charge rebuilt from ``gr``; a refused one as it is."""
    if gr.get("value_per_share") is None:
        return gr
    growth, charge = _rebuilt(gr, policy)
    target = price * shares
    return gr | {"implied_growth": implied_growth(target, growth, charge, hi=_IMPLIED_HI)}


def _anchor_and_path(
    c: Context, own: bool = False
) -> tuple[Anchor, Path, int, Belief, RevenueSteps] | Refused:
    """Year 1's anchor, the consensus path with its base fiscal year, the belief and the revenue
    steps the charge reads; or the route's refusal, with the flags raised before it, and on the
    route's own refusal "no positive forward anchor" the two stock-pay notes after the anchor's
    flags, since a stock-pay charge can itself cause it (method 5.11), but not on the path's. The
    anchor's basis test takes an overriding non-recurring gap, the whole of it, off trailing GAAP
    EPS, and its NTM EPS is taken less an overriding cycle gap; with ``own``, the route's own
    anchor, path, belief and revenue steps read the NTM EPS, one-time item, stock pay, stock-pay
    basis, step, belief and revenue step overrides, which a cross-check leaves as found."""
    i, t, policy = c.inputs, c.trailing, c.policy
    if t.revenue is None:
        return Refused("no trailing revenue")
    if i.tax_rate_latest is None:
        return Refused("no statutory tax rate")
    window = ntm_window(i.quarter_estimates, t.period_end, t.cadence)
    periods, cadence = ((), t.cadence) if window is None else window
    # the agent's gap is the whole correction: the engine finds none (spec 2026-11-19 7.1)
    correction: float | None = chosen(c, "earnings.nri_gap", None)
    one_time: float | None = chosen(c, "earnings.ntm_nri", None) if own else None
    guided: float | None = chosen(c, "earnings.ntm", None) if own else None
    sbc: float | None = chosen(c, "earnings.sbc", None) if own else None
    basis: Literal["includes", "excludes"] | None = (
        chosen(c, "earnings.sbc_basis", None) if own else None
    )
    anchor = ntm_anchor(
        periods,
        t,
        i.street_ttm_eps,
        c.consensus_shares,  # the count the consensus EPS is on (spec 2026-11-14 4)
        i.tax_rate_latest,
        c.price,
        policy,
        cadence=cadence,
        nri_correction=correction,
        one_time=one_time,
        cycle_gap=cycle_gap(c),
        guided_eps=guided,
        sbc_override=sbc,
        basis_override=basis,
        annual=i.annual_estimates,
        estimates=i.quarter_estimates,
    )
    if anchor.refusal is not None:
        notes: tuple[Flag, ...] = ()
        if own and anchor.refusal == NO_POSITIVE_ANCHOR:
            notes = _stock_pay_notes(c, anchor)
        return Refused(anchor.refusal, anchor.flags + notes)
    base_year = base_fiscal_year(periods)
    path = path_steps(i.annual_estimates, base_year, policy)
    belief = belief_from_sales(t.revenue / i.fx_rate / 1e6, policy)  # the bounds are USD
    revenue = _as_found(path)
    if own:
        path, belief, revenue = _judged(c, path, belief, revenue, base_year, periods)
    if any(g is not None and g <= -1 for g in path.steps):
        return Refused(
            "consensus earnings turn negative within the path", anchor.flags + path.flags
        )
    return anchor, path, base_year, belief, revenue


def _judged(
    c: Context,
    path: Path,
    belief: Belief,
    revenue: RevenueSteps,
    base_year: int,
    periods: Sequence[QuarterEstimate],
) -> tuple[Path, Belief, RevenueSteps]:
    """The route's own path, belief and revenue steps: under the step and belief overrides, an
    overriding step replaces the consensus's; under ``revenue.step_2`` and ``revenue.step_3`` an
    agent's step replaces the revenue step of its year that the charge reads, its source
    ``"agent"``, the steps found kept (spec 2026-11-14 6.1); ``few-analysts`` and
    ``step-series-disagree`` name only the steps the consensus still gives, the latter against the
    diluted count, without any committed shares (spec 2026-11-09 9, 2026-11-14 4). ``thin-ntm``
    (spec 2026-11-13 9) reads the NTM window's ``periods``, the ones the anchor sums, and the
    consensus periods and annual consensus that correct them where they can (spec 2026-11-13 9a),
    and takes the place right after ``few-analysts``; it is silent under an applied
    ``earnings.ntm``, whose anchor is the guidance."""
    read = (_STEP_TAGS[0] not in c.overrides, _STEP_TAGS[1] not in c.overrides)
    consensus = tuple(step if r else None for r, step in zip(read, path.steps, strict=True))
    thin = few_analysts(base_year, (consensus[0], consensus[1]), path.analysts, c.policy)
    thin_ntm = (
        None
        if "earnings.ntm" in c.overrides
        else thin_ntm_flag(periods, c.inputs.quarter_estimates, c.inputs.annual_estimates, c.policy)
    )
    disagree = step_series_flag(path, c.consensus_shares, c.policy, read)
    flags = (
        tuple(f for f in path.flags if f.code != "few-analysts") + present(thin) + present(thin_ntm)
    )
    steps = (chosen(c, "path.step_2", path.steps[0]), chosen(c, "path.step_3", path.steps[1]))
    rate = chosen(c, "growth.belief", belief.rate)
    judged = replace(path, steps=steps, flags=flags + present(disagree))
    paid = (
        chosen(c, "revenue.step_2", revenue.read[0]),
        chosen(c, "revenue.step_3", revenue.read[1]),
    )
    s2, s3 = revenue.source
    source: tuple[RevenueSource, RevenueSource] = (
        "agent" if "revenue.step_2" in c.overrides else s2,
        "agent" if "revenue.step_3" in c.overrides else s3,
    )
    return judged, replace(belief, rate=rate), replace(revenue, read=paid, source=source)


def _growth_and_charge(
    anchor: Anchor,
    path: Path,
    revenue: RevenueSteps,
    belief: Belief,
    moat: Moat,
    roic: RoicTerms,
    policy: Policy,
) -> tuple[GrowthPath, Charge]:
    """The growth path to the moat's runway, with the revenue steps the charge pays for, the ones
    ``revenue`` reads, and the charge at the returns of ``roic``, holding the runway return
    through the path's hold."""
    runway = policy.runway_years[moat]
    growth = GrowthPath(
        anchor.ntm_net_income,
        path.steps,
        belief.rate,
        runway,
        policy.fade_years,
        revenue_steps=revenue.read,
    )
    return growth, roic.charge(policy, hold_years(growth))


def charge_entry(
    growth: GrowthPath, charge: Charge, revenue: RevenueSteps | None = None
) -> dict[str, Any]:
    """The intermediates' ``charge`` (spec 2026-11-09 6.2 and 6.3, 2026-11-14 6.3): the growth
    each year's reinvestment pays for, years 2 to N + 1 with g_T last; the return years 1 to N pay
    at; the hold; ``revenue_steps``, the revenue steps the charge read, an agent's included,
    ``None`` where the earnings step stands in, which the rebuild reads; ``revenue_steps_found``,
    the consensus's as found; and ``revenue_step_source``, each year's source. Without
    ``revenue``, the path's own steps as found (none on a path without them, Mature Stable's)."""
    steps = revenue
    if steps is None:
        own = growth.revenue_steps or (None, None)
        steps = RevenueSteps(own, own, (_found_source(own[0]), _found_source(own[1])))
    return {
        "growth_by_year": [*charge_growth(growth), charge.g_t],
        "return_by_year": list(return_by_year(charge, growth.runway)),
        "hold_years": charge.hold,
        "revenue_steps": list(steps.read),
        "revenue_steps_found": list(steps.found),
        "revenue_step_source": list(steps.source),
    }


def growth_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price, from the value-side intermediates ``im``, at
    ``price`` and the result's ``value`` a share: the implied growth solves to the business's
    share of the price (``route_steps.business_price``)."""
    growth, charge = _rebuilt(im, policy)
    target = business_price(im, price) * im["shares"]
    aggregate = im["roic"]["aggregate"]
    usable = aggregate if aggregate is not None and aggregate > 0 else None
    return {
        "implied_growth": implied_growth(target, growth, charge, hi=_IMPLIED_HI),
        "implied_growth_by_runway": {
            str(n): implied_growth(target, replace(growth, runway=n), charge, hi=_IMPLIED_HI)
            for n in _runways(policy)
        },
        "implied_by_roic": {
            key: None if ch is None else implied_growth(target, growth, ch, hi=_IMPLIED_HI)
            for key, ch in _roic_charges(charge, usable, im["moat"], policy).items()
        },
        "multiples": multiples_at(price, im["eps"]),
        "growth_share": None if im["epv"] is None else growth_share(im["epv"], price),
        "expected_return": expected(
            price,
            value,
            im,
            growth_rates(growth),
            policy.repricing_horizon_years,
            policy.terminal_growth,
        ),
    }


def long_runway(im: dict[str, Any], policy: Policy) -> Flag | None:
    """The long-runway flag at the price in ``im``."""
    return long_runway_flag(im["runway"], im["belief"]["rate"], im["implied_growth"], policy)


def _rebuilt(im: dict[str, Any], policy: Policy) -> tuple[GrowthPath, Charge]:
    """The growth path and the charge from intermediates: the route's own or a cross-check's,
    which carry the same keys, the ``charge`` entry's hold and its revenue steps among them, the
    ones the charge read, an agent's included (spec 2026-11-14 6.3), not the ones found."""
    g2, g3 = im["path_steps"]
    r2, r3 = im["charge"]["revenue_steps"]
    belief = im["belief"]["rate"]
    growth = GrowthPath(
        im["ntm_net_income"],
        (g2, g3),
        belief,
        im["runway"],
        im["fade_years"],
        revenue_steps=(r2, r3),
    )
    charge = charge_for(
        im["runway_return"]["value"],
        im["terminal_roic"],
        im["charge_off"],
        policy,
        im["charge"]["hold_years"],
    )
    return growth, charge


def _roic_charges(
    own: Charge, ten_year: float | None, moat: Moat, policy: Policy
) -> dict[str, Charge | None]:
    """The charge at each return of the sensitivity, in order: the row's own; each of the policy's
    values as the runway return; the usable ten-year aggregate as the runway return, not floored
    (``None`` without one). All but the first take the moat's terminal rule on that return and
    charge in every runway year; every one holds the row's own hold (spec 2026-11-09 6.3)."""

    def at(x: float) -> Charge:
        return charge_for(x, terminal_roic(x, moat, policy), False, policy, own.hold)

    return {
        "runway": own,
        **{f"{x:g}": at(x) for x in policy.roic_sensitivity},
        "ten-year": None if ten_year is None else at(ten_year),
    }


def _stock_pay_notes(c: Context, anchor: Anchor) -> tuple[Flag, ...]:
    """``stock-pay-missing`` and ``sbc-basis-uncertain`` (spec 2026-11-13 7.1), in that order, for
    those that fire: the stored trailing stock pay against the stock pay on file, and the anchor's
    basis against the figures the test read, the stock pay in force (an agent's ``earnings.sbc``,
    else the stored figure) and GAAP EPS less an agent's non-recurring gap, the stock pay a share
    on the diluted count, as the anchor reads it (spec 2026-11-14 4).
    Reason 1 reads the warning's test (spec 2026-11-19 7.3): ``one_time_share`` of the reported
    GAAP trailing EPS and the street trailing EPS at ``one_time_items_share`` or more, silent
    under an applied ``earnings.nri_gap`` as the warning ``one-time-items`` is. A note is silent
    under the input that decides it, the agent having decided (spec 7.1): ``stock-pay-missing``
    under an applied ``earnings.sbc``, ``sbc-basis-uncertain`` under an applied
    ``earnings.sbc_basis``. Both are silent under an applied ``earnings.ntm``, as ``thin-ntm`` is:
    the guided EPS stands in for the consensus less the stock-pay adjustment, so neither stock-pay
    input moves the value (spec 7.2)."""
    if "earnings.ntm" in c.overrides:
        return ()
    i, t, policy = c.inputs, c.trailing, c.policy
    assert i.tax_rate_latest is not None  # the route refused without a statutory rate
    missing = None
    if "earnings.sbc" not in c.overrides:
        missing = stock_pay_missing_flag(t.sbc, i.stock_pay, i.currency)
    uncertain = None
    if "earnings.sbc_basis" not in c.overrides:
        read = replace(t, sbc=anchor.sbc_ttm, eps_diluted=anchor.gaap_ttm_eps)
        uncertain = sbc_basis_uncertain_flag(
            anchor.basis,
            read,
            i.street_ttm_eps,
            c.consensus_shares,
            i.tax_rate_latest,
            _one_time(c),
            policy,
            currency=i.currency,
        )
    return present(missing) + present(uncertain)


def _one_time(c: Context) -> float | None:
    """The share by which the reported GAAP trailing EPS and the street trailing EPS differ where
    it is ``one_time_items_share`` or more, the warning's test, which reason 1 of
    ``sbc-basis-uncertain`` reads; ``None`` below it, without either figure, on a GAAP EPS of 0,
    or under an applied ``earnings.nri_gap``, which decides the items (spec 2026-11-19 7.3)."""
    gaap, street = c.trailing.eps_diluted, c.inputs.street_ttm_eps
    if "earnings.nri_gap" in c.overrides or one_time_items_flag(gaap, street, c.policy) is None:
        return None
    return one_time_share(gaap, street)


def _growth_above_return(growth: GrowthPath, charge: Charge) -> Flag | None:
    """``growth-above-return`` (spec 2026-11-09 6.1) on the first year t that pays out less than
    nothing: the growth year t's reinvestment pays for, year t + 1's, and the return year t pays
    at; then the count of the other such years."""
    first = first_negative_year(growth, charge)
    if first is None:
        return None
    t, h, ret = first
    paid_for = "revenue growth" if _on_revenue(growth, t + 1) else "growth"
    sentence = (
        f"In year {t} the charge pays for {h:.1%} of {paid_for} at a return of {ret:.1%}, so the "
        "year pays out less than nothing: the owner funds the growth."
    )
    more = len(negative_years(growth, charge)) - 1
    if more:
        sentence += f" {more} more such year{'s' if more > 1 else ''}."
    return Flag("growth-above-return", "Growth above return", sentence)


def _on_revenue(growth: GrowthPath, year: int) -> bool:
    """Whether year ``year``'s h is a revenue step, the consensus's or an agent's (spec 2026-11-14
    6.3): year 2's or year 3's own, or the fade from year 3's to the belief; not where an earnings
    step stands in for a missing or thin one, nor in the belief years or after the runway."""
    r2, r3 = growth.revenue_steps or (None, None)
    if year == 2:
        return r2 is not None
    if r3 is None or year < 3 or year > growth.runway:
        return False
    return year == 3 or (r3 > growth.belief and year <= 3 + growth.fade_years)


def _gap_entry(anchor: Anchor) -> dict[str, Any] | None:
    """The ``anchor`` entry's ``annual`` (spec 2026-11-13 9a): on the annual source the fiscal year
    F, its annual EPS mean and analyst count, the sum of its periods, the window's share of them
    and the correction a share; ``None`` on the periods' sum."""
    gap = anchor.annual
    return None if gap is None else asdict(gap) | {"correction": gap.correction}


def _correction_note(anchor: Anchor, policy: Policy) -> str | None:
    """The note the ``ntm_eps`` and ``ntm_net_income`` DATA entries carry on the annual source
    (spec 2026-11-13 9a), the window's share of F's periods as a reduced fraction: "the periods'
    sum plus 3/4 of the gap between fiscal 2027's annual consensus and its periods' sum: ...", or
    for a window that is F whole "fiscal 2027's annual consensus in place of its periods' sum:
    ..."; none on the periods' sum."""
    gap = anchor.annual
    if gap is None:
        return None
    why = f"a period of the NTM window has fewer than {policy.analyst_min} EPS analysts or no count"
    if gap.share == 1:
        return f"fiscal {gap.fiscal_year}'s annual consensus in place of its periods' sum: {why}"
    share = Fraction(gap.share).limit_denominator()
    return (
        f"the periods' sum plus {share} of the gap between fiscal {gap.fiscal_year}'s annual "
        f"consensus and its periods' sum: {why}"
    )


def _after_assembly(notes: dict[str, str], name: str, note: str | None) -> str | None:
    """``note`` after the note assembly holds for the DATA entry ``name`` (a pending split's),
    joined with "; "; either alone where the other is none."""
    return "; ".join(x for x in (notes.get(name), note) if x) or None


def _on_reported(anchor: Anchor, reported: float | None) -> float | None:
    """The ``ntm_net_income`` DATA entry: the consensus NTM EPS less the stock-pay adjustment in
    force (``Anchor.ntm_eps_found``) on the reported count, ``None`` without one; an agent's
    ``shares.diluted`` reaches it only through that adjustment, the stock pay a share being on the
    diluted count, and ``shares.committed`` does not reach it. The intermediates'
    ``ntm_net_income`` is on the diluted count the route used."""
    return None if reported is None else anchor.ntm_eps_found * reported


def _runways(policy: Policy) -> list[int]:
    return sorted(set(policy.runway_years.values()))
