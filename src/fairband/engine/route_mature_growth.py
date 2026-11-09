"""The Mature Growth route (spec 6.6, steps 1 to 11, under the calibration spec 5).

Year 1 is the NTM anchor and years 2 and 3 the consensus path. When year 3's growth is above the
belief, years 4 to 3 + the policy's ``fade_years`` fade from it to the belief; the other years to
the runway N grow at the belief. The value is the reverse DCF with the reinvestment charge of spec
2026-11-09 6 (``RoicTerms``): each year pays for the next year's revenue growth, the consensus
revenue steps for years 2 and 3 (a missing one taking the earnings step) fading to the belief as
the earnings path fades, at a return that holds at the runway return through the hold K, the last
year whose next earnings growth is above the belief, then fades in equal steps to the terminal
return in year N. K is read once, from the row's own path at the belief in force, and every
sensitivity and solve holds it. A year whose growth outruns its return pays out less than nothing;
the first such year raises "growth above return", which counts the rest, after the ROIC flags and
before the trailing ones, where the ``heavy-capex`` sentence names the return the charge starts at
and ``consensus-basis-unknown`` follows ``large-nri``. ``charge`` in the intermediates records the
growth paid for, the return by year, the hold and the revenue steps as found.

The value is also computed at each policy runway and at each return of the sensitivity, and so is
the implied growth at the price. The sensitivity is keyed ``"runway"``, the row's own charge;
then the policy's ``roic_sensitivity`` values, each as the runway return with the moat's terminal
rule applied to it; then ``"ten-year"``, the ten-year aggregate ROIC as the runway return, not
floored, with the moat's terminal rule applied to it, ``None`` when the aggregate is unavailable
or not positive; each on the row's hold. The value-spread flag reads the first three.

``growth_at_price`` rebuilds the growth path and the charges from the intermediates alone, the
``charge`` entry's revenue steps and hold among them, so a stored result moves to a new price
without its inputs. The implied growth is the belief at which the value equals the price, both
paths' fades moving with it and the hold fixed; it is solved between −50% and 200% a year, and
``None`` means no growth in that range reaches the price. The expected return's growth reads the
earnings path's rates from year 2.

``growth_cross_check`` runs the same anchor, path and charge for a Mature Stable row, on that
row's moat and returns, so its value is the one this route would reach (calibration spec 5.7).
It carries the keys the rebuild reads, so ``cross_check_at_price`` gives its implied growth at
any price by the same solve, from the intermediates alone.

Overrides (``method.md`` 14) through ``route_steps.chosen``: ``moat.class`` the moat, so the
runway, the terminal return and the margin of safety with it; ``return.runway`` the runway return
of the charge, the start of its fade (``RoicTerms.of``); ``earnings.nri_gap`` the non-recurring
gap, the anchor's basis test then taking the correction, the override less the gap found, off
trailing GAAP EPS (``anchor.ntm_anchor``), so an override at the gap found moves nothing;
``path.step_2`` and ``path.step_3`` the consensus steps, before the check that the path stays
above −100%, a replaced step not counted thin nor named in ``step-series-disagree``, the revenue
steps the charge pays for left as found; ``growth.belief`` the belief's rate, and the hold read on
it; ``earnings.ntm``, the NTM EPS from a clear guidance, which stands in for the consensus less
the SBC adjustment, the four NTM quarters still required; ``earnings.cycle_gap`` the correction
to mid-cycle earnings, which the NTM EPS, the consensus's or the guided one, is taken less, before
the positive-anchor refusal (``anchor.ntm_anchor``). Nothing else reads the two: the basis test,
the clean EPS, EPV and ``large-nri`` read the non-recurring gap alone, and the forward EPS of
the P/E and the ``ntm_eps`` and ``ntm_net_income`` data entries are the consensus as found
(``Anchor.ntm_eps_found``), the ``ntm_eps`` entry giving way to the JUDGMENT entry under the
guided EPS. ``cycle_gap`` is in the intermediates only under that override. The cross-check reads
the row's moat, returns and two gaps, and the consensus and belief as found.
"""

from dataclasses import asdict, replace
from typing import Any

from fairband.engine.anchor import (
    Anchor,
    Belief,
    Path,
    base_fiscal_year,
    belief_from_sales,
    few_analysts,
    moat_class,
    ntm_anchor,
    ntm_quarters,
    path_steps,
    step_series_flag,
)
from fairband.engine.flags import long_runway_flag, value_spread_flag
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
    charge_for,
    chosen,
    common_inputs,
    common_rules,
    cycle_entry,
    cycle_gap,
    data,
    eps,
    expected,
    income,
    multiples_at,
    nil,
    nri_gap,
    present,
    price_facts_for,
    rule,
    trailing_flags,
)
from fairband.engine.types import Flag
from fairband.policy import Moat, Policy

_IMPLIED_HI = 2.0  # the highest growth the implied-growth solve tries: 200% a year
_NOT_POSITIVE = "value not positive under the reinvestment charge"
_STEP_TAGS: tuple[OverrideTag, OverrideTag] = ("path.step_2", "path.step_3")


def value_mature_growth(c: Context) -> Valued | Refused:
    i, t, policy = c.inputs, c.trailing, c.policy
    found = _anchor_and_path(c, own=True)
    if isinstance(found, Refused):
        return found
    anchor, path, base_year, belief = found
    moat = chosen(c, "moat.class", moat_class(i.moat_score, policy))
    runway_return: float | None = chosen(c, "return.runway", None)
    roic = RoicTerms.of(i.capital_years, moat, policy, runway_override=runway_return)
    growth, charge = _growth_and_charge(anchor, path, belief, moat, roic, policy)
    value_total = value_at_belief(growth, charge)
    value = value_total / c.shares
    by_runway = {
        str(n): value_at_belief(replace(growth, runway=n), charge) / c.shares
        for n in _runways(policy)
    }
    by_roic = {
        key: None if ch is None else value_at_belief(growth, ch) / c.shares
        for key, ch in _roic_charges(charge, roic.usable, moat, policy).items()
    }
    gap = chosen(c, "earnings.nri_gap", nri_gap(i))
    e = eps(t, gap, anchor.ntm_eps_found)
    im: dict[str, Any] = {
        "anchor": {
            "ntm_eps_raw": anchor.ntm_eps_raw,
            "sbc_adjustment_per_share": anchor.sbc_adjustment_per_share,
            "ntm_eps": anchor.ntm_eps,
        },
        "sbc_basis": anchor.basis,
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
        "charge": charge_entry(growth, charge),
        "shares": c.shares,
        "value_total": value_total,
        "value_per_share": value,
        "value_by_runway": by_runway,
        "value_by_roic": by_roic,
        "nri_gap": gap,
        **cycle_entry(cycle_gap(c)),
        "eps": e,
        "epv": None if e["clean"] is None else epv(e["clean"], policy.required_return),
        **income(i.market_cap, t),
        "price_facts": price_facts_for(i.closes, c.price, c.today),
    }
    flags = (
        anchor.flags
        + path.flags
        + roic.flags
        + present(_growth_above_return(growth, charge))
        + trailing_flags(i, t, gap, policy, roic)
    )
    spread = present(value_spread_flag(list(by_roic.values())[:3], policy)) + present(
        value_spread_flag(list(by_runway.values()), policy)
    )
    if value <= 0:
        return Refused(_NOT_POSITIVE, flags + spread, im)
    im |= growth_at_price(im, c.price, value, policy)
    flags += present(long_runway(im, policy)) + spread
    inputs = (
        *common_inputs(i, t, roic),
        data(i, "sbc_ttm", t.sbc, "USD", "statements"),
        # the consensus as found: an agent's guided EPS or cycle gap is its JUDGMENT entry
        data(i, "ntm_eps", anchor.ntm_eps_found, "USD a share", "estimates_quarter"),
        data(i, "ntm_net_income", anchor.ntm_eps_found * c.shares, "USD", "estimates_quarter"),
        data(i, "path_step_2", path.steps[0], "ratio", "estimates_annual"),
        data(i, "path_step_3", path.steps[1], "ratio", "estimates_annual"),
        data(i, "street_ttm_eps", i.street_ttm_eps, "USD a share"),
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
    return Valued("mature-growth", value, moat, im, inputs, flags)


def growth_cross_check(c: Context, moat: Moat, roic: RoicTerms) -> dict[str, Any]:
    """The growth route's value a share for a Mature Stable row (calibration spec 5.7), from the
    row's moat and returns, with what the value rests on: the anchor's net income, the path, the
    belief, the runway and fade, and the returns of the charge; or only the refusal the route
    would give. ``cross_check_at_price`` adds the implied growth at a price."""
    found = _anchor_and_path(c)
    if isinstance(found, Refused):
        return {"refusal": found.reason}
    anchor, path, _, belief = found
    growth, charge = _growth_and_charge(anchor, path, belief, moat, roic, c.policy)
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
        "charge": charge_entry(growth, charge),
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


def _anchor_and_path(c: Context, own: bool = False) -> tuple[Anchor, Path, int, Belief] | Refused:
    """Year 1's anchor, the consensus path with its base fiscal year, and the belief; or the
    route's refusal, with the flags raised before it. The anchor's basis test reads an overriding
    non-recurring gap as its correction to the gap found, and its NTM EPS is taken less an
    overriding cycle gap; with ``own``, the route's own anchor, path and belief read the NTM EPS,
    step and belief overrides, which a cross-check leaves as found."""
    i, t, policy = c.inputs, c.trailing, c.policy
    if t.revenue is None:
        return Refused("no trailing revenue")
    if i.tax_rate_latest is None:
        return Refused("no statutory tax rate")
    quarters = ntm_quarters(i.quarter_estimates, t.period_end) or ()
    gap: float | None = chosen(c, "earnings.nri_gap", None)
    correction = None if gap is None else gap - nil(nri_gap(i))
    guided: float | None = chosen(c, "earnings.ntm", None) if own else None
    anchor = ntm_anchor(
        quarters,
        t,
        i.street_ttm_eps,
        c.shares,
        i.tax_rate_latest,
        c.price,
        policy,
        nri_correction=correction,
        cycle_gap=cycle_gap(c),
        guided_eps=guided,
    )
    if anchor.refusal is not None:
        return Refused(anchor.refusal, anchor.flags)
    base_year = base_fiscal_year(quarters)
    path = path_steps(i.annual_estimates, base_year, policy)
    belief = belief_from_sales(t.revenue / 1e6, policy)
    if own:
        path, belief = _judged(c, path, belief, base_year)
    if any(g is not None and g <= -1 for g in path.steps):
        return Refused(
            "consensus earnings turn negative within the path", anchor.flags + path.flags
        )
    return anchor, path, base_year, belief


def _judged(c: Context, path: Path, belief: Belief, base_year: int) -> tuple[Path, Belief]:
    """The route's own path and belief: under the step and belief overrides, an overriding step
    replaces the consensus's; ``few-analysts`` and ``step-series-disagree`` name only the steps the
    consensus still gives, the latter against the diluted count (spec 2026-11-09 9)."""
    read = (_STEP_TAGS[0] not in c.overrides, _STEP_TAGS[1] not in c.overrides)
    consensus = tuple(step if r else None for r, step in zip(read, path.steps, strict=True))
    thin = few_analysts(base_year, (consensus[0], consensus[1]), path.analysts, c.policy)
    disagree = step_series_flag(path, c.shares, c.policy, read)
    flags = tuple(f for f in path.flags if f.code != "few-analysts") + present(thin)
    steps = (chosen(c, "path.step_2", path.steps[0]), chosen(c, "path.step_3", path.steps[1]))
    rate = chosen(c, "growth.belief", belief.rate)
    judged = replace(path, steps=steps, flags=flags + present(disagree))
    return judged, replace(belief, rate=rate)


def _growth_and_charge(
    anchor: Anchor, path: Path, belief: Belief, moat: Moat, roic: RoicTerms, policy: Policy
) -> tuple[GrowthPath, Charge]:
    """The growth path to the moat's runway, with the revenue steps the charge pays for, and the
    charge at the returns of ``roic``, holding the runway return through the path's hold."""
    runway = policy.runway_years[moat]
    growth = GrowthPath(
        anchor.ntm_net_income,
        path.steps,
        belief.rate,
        runway,
        policy.fade_years,
        revenue_steps=path.revenue_steps,
    )
    return growth, roic.charge(policy, hold_years(growth))


def charge_entry(growth: GrowthPath, charge: Charge) -> dict[str, Any]:
    """The intermediates' ``charge`` (spec 2026-11-09 6.2 and 6.3): the growth each year's
    reinvestment pays for, years 2 to N + 1 with g_T last; the return years 1 to N pay at; the
    hold; and the revenue steps as found, ``None`` where missing (both on a path without them)."""
    return {
        "growth_by_year": [*charge_growth(growth), charge.g_t],
        "return_by_year": list(return_by_year(charge, growth.runway)),
        "hold_years": charge.hold,
        "revenue_steps": list(growth.revenue_steps or (None, None)),
    }


def growth_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price, from the value-side intermediates ``im``."""
    growth, charge = _rebuilt(im, policy)
    target = price * im["shares"]
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
    which carry the same keys, the ``charge`` entry's revenue steps and hold among them."""
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


def _growth_above_return(growth: GrowthPath, charge: Charge) -> Flag | None:
    """``growth-above-return`` (spec 2026-11-09 6.1) on the first year t that pays out less than
    nothing: the growth year t's reinvestment pays for, year t + 1's, and the return year t pays
    at; then the count of the other such years."""
    first = first_negative_year(growth, charge)
    if first is None:
        return None
    t, h, ret = first
    sentence = (
        f"In year {t} the charge pays for {h:.1%} of revenue growth at a return of {ret:.1%}, so "
        "the year pays out less than nothing: the owner funds the growth."
    )
    more = len(negative_years(growth, charge)) - 1
    if more:
        sentence += f" {more} more such year{'s' if more > 1 else ''}."
    return Flag("growth-above-return", "Growth above return", sentence)


def _runways(policy: Policy) -> list[int]:
    return sorted(set(policy.runway_years.values()))
