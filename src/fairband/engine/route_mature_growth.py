"""The Mature Growth route (spec 6.6, steps 1 to 11).

Year 1 is the NTM anchor, years 2 and 3 the consensus path, years 4 to N the belief; the value is
the reverse DCF with the reinvestment charge at the company's aggregate ROIC, the terminal at the
moat's terminal ROIC. The value is also computed at each policy runway and at each ROIC of the
sensitivity (the company's, then the policy's ``roic_sensitivity``, each with the moat's terminal
rule applied to it), and so is the implied growth at the price.

``growth_at_price`` rebuilds the growth path and the charge from the intermediates alone, so a
stored result moves to a new price without its inputs. The implied growth is solved between −50%
and 200% a year; ``None`` means no growth in that range reaches the price.
"""

from dataclasses import replace
from typing import Any

from fairband.engine.anchor import (
    base_fiscal_year,
    belief_from_sales,
    moat_class,
    ntm_anchor,
    ntm_quarters,
    path_steps,
)
from fairband.engine.flags import long_runway_flag, value_spread_flag
from fairband.engine.mature_growth import Charge, GrowthPath, implied_growth, value_at_belief
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


def value_mature_growth(c: Context) -> Valued | Refused:
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

    belief = belief_from_sales(t.revenue / 1e6, policy)
    moat = moat_class(i.moat_score, policy)
    runway = policy.runway_years[moat]
    roic = RoicTerms.of(i.capital_years, moat, policy)
    growth = GrowthPath(anchor.ntm_net_income, path.steps, belief.rate, runway)
    charge = _charge(roic.runway, roic.terminal, roic.charge_off, policy)
    value_total = value_at_belief(growth, charge)
    value = value_total / c.shares
    by_runway = {
        str(n): value_at_belief(replace(growth, runway=n), charge) / c.shares
        for n in _runways(policy)
    }
    by_roic = {
        key: None if ch is None else value_at_belief(growth, ch) / c.shares
        for key, ch in _roic_charges(roic.usable, moat, policy).items()
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
        "belief": {"rate": belief.rate, "sales_class": belief.sales_class, "median": belief.median},
        "moat": moat,
        "runway": runway,
        **roic.intermediates(),
        "runway_roic": roic.runway,
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
    flags = anchor.flags + path.flags + roic.flags + trailing_flags(i, t, gap, policy)
    spread = present(value_spread_flag(list(by_roic.values()), policy)) + present(
        value_spread_flag(list(by_runway.values()), policy)
    )
    if value <= 0:
        return Refused("value not positive under the reinvestment charge", flags + spread, im)
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
        data(i, "tax_rate_latest", i.tax_rate_latest, "ratio"),
        *common_rules(policy, moat, roic),
        rule(policy, "runway_years", runway, "years", f"{moat} moat"),
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


def growth_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price, from the value-side intermediates ``im``."""
    g2, g3 = im["path_steps"]
    growth = GrowthPath(im["ntm_net_income"], (g2, g3), im["belief"]["rate"], im["runway"])
    charge = _charge(im["runway_roic"], im["terminal_roic"], im["charge_off"], policy)
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
            for key, ch in _roic_charges(usable, im["moat"], policy).items()
        },
        "multiples": multiples_at(price, im["eps"]),
        "growth_share": None if im["epv"] is None else growth_share(im["epv"], price),
        "expected_return": expected(price, value, im, (g2, g3), im["belief"]["rate"]),
    }


def long_runway(im: dict[str, Any], policy: Policy) -> Flag | None:
    """The long-runway flag at the price in ``im``."""
    return long_runway_flag(im["runway"], im["belief"]["rate"], im["implied_growth"], policy)


def _charge(runway_roic: float, terminal: float, charge_off: bool, policy: Policy) -> Charge:
    return Charge(runway_roic, terminal, policy.required_return, policy.terminal_growth, charge_off)


def _roic_charges(usable: float | None, moat: Moat, policy: Policy) -> dict[str, Charge | None]:
    """The charge at each runway ROIC of the sensitivity, as if the company's aggregate were that
    ROIC: the aggregate itself (``None`` when unavailable), then the policy's values."""
    cases = [("aggregate", usable), *((f"{x:g}", x) for x in policy.roic_sensitivity)]
    return {
        key: None if x is None else _charge(x, terminal_roic(x, moat, policy), False, policy)
        for key, x in cases
    }


def _runways(policy: Policy) -> list[int]:
    return sorted(set(policy.runway_years.values()))
