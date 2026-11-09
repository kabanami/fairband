"""The Mature Stable route (spec 6.6, calibration spec 5.10): the stable-growth value on
normalized trailing earnings, charged as the growth route charges.

E is trailing net income less the non-recurring gap on the diluted shares; when the margin flag
fires, E is scaled to the ten-year median operating margin; an agent's cycle gap a share then
comes off the E so normalized on the diluted shares, so the engine's scaling and the agent's
correction add (``e_normalized`` is the E the value rests on). The value at belief is the
stable-growth value: the reverse DCF of ``mature_growth`` on a path that grows at the terminal
growth in every year, with the reinvestment charge of ``RoicTerms.charge`` on a hold of 0, since
no year grows above the belief (spec 2026-11-09 6.3): the return fades in equal steps from the
runway return in year 1 to the terminal return in year N of the moat's runway and the terminal,
and the charge is off in the runway years when the growth route's would be. A row whose runway
return is the terminal return, with the charge on, values at the one-stage perpetuity; a floored
row, charged at r in every year, values at EPV under any moat; a row whose runway return is above
the terminal return is worth more, and more for a longer runway; a charge-off row is worth more
still, its runway years uncharged. EPV is shown as the no-growth value. ``epv`` and
``stable_growth`` are a share; ``epv_total`` and ``stable_growth_total`` are the totals;
``charge`` records the growth paid for (g_T in every year), the return by year, the hold and no
revenue steps. The ROIC flags are the growth route's, and so are the trailing flags' readings of
the runway return: the ``heavy-capex`` sentence and ``consensus-basis-unknown`` after
``large-nri``.

``growth_route`` is the growth route's value on the same row as a cross-check (calibration spec
5.7), or that route's refusal; the value, the levels and the designation stay on the stable-growth
value. Its implied growth moves with the price, as the growth route's does.

A missing or non-positive E, the normalized E less any cycle gap, refuses "no positive trailing
earnings" (engine-round spec 9); the scaling keeps E's sign, so without a cycle gap this is E
before the scaling. The refusal keeps ``e_trailing``, ``nri_gap``, ``eps``, ``shares``,
``moat``, ``price_facts`` and the cross-check with its implied growth at the price, which
``route.reprice`` moves as on a valued row; it raises no flag and cites no input beyond the ones
every result carries.

Overrides (``method.md`` 14) through ``route_steps.chosen``: ``earnings.nri_gap`` the
non-recurring gap E is taken less, ``moat.class`` the moat and ``return.runway`` the runway return
of the charge; the cross-check reads the same moat, returns and gap. ``earnings.cycle_gap``, the
correction to mid-cycle earnings, comes off the normalized E, and off the cross-check's NTM
anchor; ``e_trailing``, the clean EPS, the P/E and ``large-nri`` do not read it. ``cycle_gap`` is
in the intermediates, a refusal's too, only under that override.
"""

from typing import Any

from fairband.engine.anchor import moat_class
from fairband.engine.flags import margin_flag, median_margin
from fairband.engine.mature_growth import GrowthPath
from fairband.engine.mature_stable import mature_stable_values, normalize_for_margin
from fairband.engine.route_mature_growth import (
    charge_entry,
    cross_check_at_price,
    growth_cross_check,
)
from fairband.engine.route_steps import (
    Context,
    Refused,
    RoicTerms,
    Valued,
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
    price_facts_for,
    rule,
    trailing_flags,
    ttm_margin,
)
from fairband.policy import Policy


def value_mature_stable(c: Context) -> Valued | Refused:
    i, t, policy = c.inputs, c.trailing, c.policy
    gap = chosen(c, "earnings.nri_gap", nri_gap(i))
    cycle = cycle_gap(c)
    e = None if t.net_income is None else t.net_income - nil(gap) * c.shares
    moat = chosen(c, "moat.class", moat_class(i.moat_score, policy))
    runway_return: float | None = chosen(c, "return.runway", None)
    roic = RoicTerms.of(i.capital_years, moat, policy, runway_override=runway_return)
    growth_route = growth_cross_check(c, moat, roic)
    margin = ttm_margin(t)
    median = median_margin(i.series)
    flagged = margin_flag(i.series, margin, policy) is not None
    scaled = e
    if e is not None and flagged and margin is not None and median is not None:
        scaled = normalize_for_margin(e, margin, median, flagged)
    # the cycle gap comes off the E the engine normalized, so the scaling and the correction add
    e_normalized = scaled if scaled is None or cycle is None else scaled - cycle * c.shares
    if e_normalized is None or e_normalized <= 0:
        # engine-round spec 9: the refusal keeps the cross-check, at the price
        refused: dict[str, Any] = {
            "e_trailing": e,
            "nri_gap": gap,
            **cycle_entry(cycle),
            "eps": eps(t, gap, None),
            "shares": c.shares,
            "moat": moat,
            "growth_route": cross_check_at_price(growth_route, c.price, c.shares, policy),
            "price_facts": price_facts_for(i.closes, c.price, c.today),
        }
        return Refused("no positive trailing earnings", (), refused, ())

    runway, g_t = policy.runway_years[moat], policy.terminal_growth
    charge = roic.charge(policy, 0)  # no year grows above g_T: the return fades from year 1
    epv_total, stable = mature_stable_values(e_normalized, charge, runway)
    value = stable / c.shares
    im: dict[str, Any] = {
        "e_trailing": e,
        "nri_gap": gap,
        **cycle_entry(cycle),
        "ttm_margin": margin,
        "median_margin": median,
        "margin_scaled": scaled != e,
        "e_normalized": e_normalized,
        "moat": moat,
        **roic.intermediates(),
        "charge": charge_entry(GrowthPath(e_normalized, (g_t, g_t), g_t, runway), charge),
        "runway": runway,
        "epv": epv_total / c.shares,
        "epv_total": epv_total,
        "stable_growth": value,
        "stable_growth_total": stable,
        "shares": c.shares,
        "value_per_share": value,
        "eps": eps(t, gap, None),
        **income(i.market_cap, t),
        "price_facts": price_facts_for(i.closes, c.price, c.today),
        "growth_route": growth_route,
    }
    im |= stable_at_price(im, c.price, value, policy)
    inputs = (
        *common_inputs(i, t, roic),
        data(i, "net_income_ttm", t.net_income, "USD", "statements"),
        *common_rules(policy, moat, roic.terminal),
        rule(policy, "runway_years", runway, "years", f"{moat} moat"),
        rule(
            policy,
            "belief",
            policy.terminal_growth,
            "ratio",
            "the terminal growth, the expected return's growth for a stable company",
        ),
    )
    flags = roic.flags + trailing_flags(i, t, gap, policy, roic)
    return Valued("mature-stable", value, moat, im, inputs, flags)


def stable_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price; growth runs at the terminal growth. The
    growth-route cross-check takes its implied growth at the price."""
    g_t = policy.terminal_growth
    return {
        "multiples": multiples_at(price, im["eps"]),
        "expected_return": expected(price, value, im, (), policy.repricing_horizon_years, g_t),
        "growth_route": cross_check_at_price(im["growth_route"], price, im["shares"], policy),
    }
