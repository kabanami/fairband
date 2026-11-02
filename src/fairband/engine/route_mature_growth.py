"""The Mature Growth route (spec 6.6, steps 1 to 11, under the calibration spec 5).

Year 1 is the NTM anchor and years 2 and 3 the consensus path. When year 3's growth is above the
belief, years 4 to 3 + the policy's ``fade_years`` fade from it to the belief; the other years to
the runway N grow at the belief. The value is the reverse DCF with the reinvestment charge at the
runway return in years 1 to N−1 and at the terminal return in year N and the terminal value
(``RoicTerms``). A year whose next growth is above its return pays out nothing, never less; the
first such year raises "growth above return", after the ROIC flags and before the trailing ones.

The value is also computed at each policy runway and at each return of the sensitivity, and so is
the implied growth at the price. The sensitivity is keyed ``"runway"``, the row's own charge;
then the policy's ``roic_sensitivity`` values, each as the runway return with the moat's terminal
rule applied to it; then ``"ten-year"``, the ten-year aggregate ROIC as the runway return, not
floored, with the moat's terminal rule applied to it, ``None`` when the aggregate is unavailable
or not positive. The value-spread flag reads the first three.

``growth_at_price`` rebuilds the growth path and the charges from the intermediates alone, so a
stored result moves to a new price without its inputs. The implied growth is the belief at which
the value equals the price, the fade moving with it; it is solved between −50% and 200% a year,
and ``None`` means no growth in that range reaches the price. The expected return's growth reads
the path's rates from year 2.

``growth_cross_check`` runs the same anchor, path and charge for a Mature Stable row, on that
row's moat and returns, so its value is the one this route would reach (calibration spec 5.7).
It carries the keys the rebuild reads, so ``cross_check_at_price`` gives its implied growth at
any price by the same solve, from the intermediates alone.
"""

from dataclasses import asdict, replace
from typing import Any

from fairband.engine.anchor import (
    Anchor,
    Belief,
    Path,
    base_fiscal_year,
    belief_from_sales,
    moat_class,
    ntm_anchor,
    ntm_quarters,
    path_steps,
)
from fairband.engine.flags import long_runway_flag, value_spread_flag
from fairband.engine.mature_growth import (
    Charge,
    GrowthPath,
    first_floored_year,
    growth_rates,
    implied_growth,
    value_at_belief,
)
from fairband.engine.multiples import epv, growth_share
from fairband.engine.roic import terminal_roic
from fairband.engine.route_steps import (
    Context,
    Refused,
    RoicTerms,
    Valued,
    common_inputs,
    common_rules,
    data,
    eps,
    expected,
    income,
    multiples_at,
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


def value_mature_growth(c: Context) -> Valued | Refused:
    i, t, policy = c.inputs, c.trailing, c.policy
    found = _anchor_and_path(c)
    if isinstance(found, Refused):
        return found
    anchor, path, base_year, belief = found
    moat = moat_class(i.moat_score, policy)
    roic = RoicTerms.of(i.capital_years, moat, policy)
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
    gap = nri_gap(i)
    e = eps(t, gap, anchor.ntm_eps)
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
        "shares": c.shares,
        "value_total": value_total,
        "value_per_share": value,
        "value_by_runway": by_runway,
        "value_by_roic": by_roic,
        "nri_gap": gap,
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
        + trailing_flags(i, t, gap, policy)
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
        data(i, "ntm_eps", anchor.ntm_eps, "USD a share", "estimates_quarter"),
        data(i, "ntm_net_income", anchor.ntm_net_income, "USD", "estimates_quarter"),
        data(i, "path_step_2", path.steps[0], "ratio", "estimates_annual"),
        data(i, "path_step_3", path.steps[1], "ratio", "estimates_annual"),
        data(i, "street_ttm_eps", i.street_ttm_eps, "USD a share"),
        *common_rules(policy, moat, roic),
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


def _anchor_and_path(c: Context) -> tuple[Anchor, Path, int, Belief] | Refused:
    """Year 1's anchor, the consensus path with its base fiscal year, and the belief; or the
    route's refusal, with the flags raised before it."""
    i, t, policy = c.inputs, c.trailing, c.policy
    if t.revenue is None:
        return Refused("no trailing revenue")
    if i.tax_rate_latest is None:
        return Refused("no statutory tax rate")
    quarters = ntm_quarters(i.quarter_estimates, t.period_end) or ()
    anchor = ntm_anchor(quarters, t, i.street_ttm_eps, c.shares, i.tax_rate_latest, c.price, policy)
    if anchor.refusal is not None:
        return Refused(anchor.refusal, anchor.flags)
    base_year = base_fiscal_year(quarters)
    path = path_steps(i.annual_estimates, base_year, policy)
    if any(g is not None and g <= -1 for g in path.steps):
        return Refused(
            "consensus earnings turn negative within the path", anchor.flags + path.flags
        )
    return anchor, path, base_year, belief_from_sales(t.revenue / 1e6, policy)


def _growth_and_charge(
    anchor: Anchor, path: Path, belief: Belief, moat: Moat, roic: RoicTerms, policy: Policy
) -> tuple[GrowthPath, Charge]:
    """The growth path to the moat's runway and the charge at the returns of ``roic``."""
    runway = policy.runway_years[moat]
    growth = GrowthPath(anchor.ntm_net_income, path.steps, belief.rate, runway, policy.fade_years)
    return growth, roic.charge(policy)


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
        "expected_return": expected(price, value, im, growth_rates(growth)),
    }


def long_runway(im: dict[str, Any], policy: Policy) -> Flag | None:
    """The long-runway flag at the price in ``im``."""
    return long_runway_flag(im["runway"], im["belief"]["rate"], im["implied_growth"], policy)


def _rebuilt(im: dict[str, Any], policy: Policy) -> tuple[GrowthPath, Charge]:
    """The growth path and the charge from intermediates: the route's own or a cross-check's,
    which carry the same keys."""
    g2, g3 = im["path_steps"]
    belief = im["belief"]["rate"]
    growth = GrowthPath(im["ntm_net_income"], (g2, g3), belief, im["runway"], im["fade_years"])
    charge = _charge(im["runway_return"]["value"], im["terminal_roic"], im["charge_off"], policy)
    return growth, charge


def _charge(runway_roic: float, terminal: float, charge_off: bool, policy: Policy) -> Charge:
    return Charge(runway_roic, terminal, policy.required_return, policy.terminal_growth, charge_off)


def _roic_charges(
    own: Charge, ten_year: float | None, moat: Moat, policy: Policy
) -> dict[str, Charge | None]:
    """The charge at each return of the sensitivity, in order: the row's own; each of the policy's
    values as the runway return; the usable ten-year aggregate as the runway return, not floored
    (``None`` without one). All but the first take the moat's terminal rule on that return and
    charge in every runway year."""

    def at(x: float) -> Charge:
        return _charge(x, terminal_roic(x, moat, policy), False, policy)

    return {
        "runway": own,
        **{f"{x:g}": at(x) for x in policy.roic_sensitivity},
        "ten-year": None if ten_year is None else at(ten_year),
    }


def _growth_above_return(growth: GrowthPath, charge: Charge) -> Flag | None:
    """``growth-above-return`` on the first year t whose payout the floor raised to zero: year
    t + 1's growth, which year t's reinvestment pays for, and the return year t pays at."""
    floored = first_floored_year(growth, charge)
    if floored is None:
        return None
    t, g, ret = floored
    return Flag(
        "growth-above-return",
        "Growth above return",
        f"Year {t + 1} growth of {g:.1%} exceeds the {ret:.1%} return on new capital; year {t}'s "
        "payout is floored at zero and the growth above the return is treated as efficiency "
        "growth, which costs nothing.",
    )


def _runways(policy: Policy) -> list[int]:
    return sorted(set(policy.runway_years.values()))
