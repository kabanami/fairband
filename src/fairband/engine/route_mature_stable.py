"""The Mature Stable route (spec 6.6): the stable-growth value on normalized trailing earnings.

E is trailing net income less the non-recurring gap on the diluted shares; when the margin flag
fires, E is scaled to the ten-year median operating margin. The value at belief is the
stable-growth value at the moat's terminal return (``RoicTerms``), always: so it equals EPV for a
Narrow or no moat and is about 15% above it for a Wide one (15.4% at r 9%, g_t 3% and the 13%
cap). A capital sum at or below zero does not turn the charge off here: the value takes the moat's
terminal return, and the row says so. EPV is shown as the no-growth value. ``epv`` and
``stable_growth`` are a share; ``epv_total`` and ``stable_growth_total`` are the totals.

``growth_route`` is the growth route's value on the same row as a cross-check (calibration spec
5.7), or that route's refusal; the value, the levels and the stance stay on the stable-growth
value.
"""

from typing import Any

from fairband.engine.anchor import moat_class
from fairband.engine.flags import margin_flag, median_margin
from fairband.engine.mature_stable import mature_stable_values, normalize_for_margin
from fairband.engine.route_mature_growth import growth_cross_check
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
    nil,
    nri_gap,
    price_facts_for,
    rule,
    trailing_flags,
    ttm_margin,
)
from fairband.engine.types import Flag
from fairband.policy import Policy


def value_mature_stable(c: Context) -> Valued | Refused:
    i, t, policy = c.inputs, c.trailing, c.policy
    gap = nri_gap(i)
    e = None if t.net_income is None else t.net_income - nil(gap) * c.shares
    if e is None or e <= 0:
        return Refused("no positive trailing earnings")
    margin = ttm_margin(t)
    median = median_margin(i.series)
    flagged = margin_flag(i.series, margin, policy) is not None
    e_normalized = e
    if flagged and margin is not None and median is not None:
        e_normalized = normalize_for_margin(e, margin, median, flagged)

    moat = moat_class(i.moat_score, policy)
    roic = RoicTerms.of(i.capital_years, moat, policy)
    epv_total, stable = mature_stable_values(
        e_normalized, roic.terminal, policy.required_return, policy.terminal_growth
    )
    value = stable / c.shares
    im: dict[str, Any] = {
        "e_trailing": e,
        "nri_gap": gap,
        "ttm_margin": margin,
        "median_margin": median,
        "margin_scaled": e_normalized != e,
        "e_normalized": e_normalized,
        "moat": moat,
        **roic.intermediates(),
        "epv": epv_total / c.shares,
        "epv_total": epv_total,
        "stable_growth": value,
        "stable_growth_total": stable,
        "shares": c.shares,
        "value_per_share": value,
        "eps": eps(t, gap, None),
        **income(i.market_cap, t),
        "price_facts": price_facts_for(i.closes, c.price, c.today),
        "growth_route": growth_cross_check(c, moat, roic),
    }
    im |= stable_at_price(im, c.price, value, policy)
    inputs = (
        *common_inputs(i, t, roic),
        data(i, "net_income_ttm", t.net_income, "USD", "statements"),
        *common_rules(policy, moat, roic),
        rule(
            policy,
            "belief",
            policy.terminal_growth,
            "ratio",
            "the terminal growth, the expected return's growth for a stable company",
        ),
    )
    flags = _roic_flags(roic, policy) + trailing_flags(i, t, gap, policy)
    return Valued("mature-stable", value, moat, im, inputs, flags)


def stable_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price; growth runs at the terminal growth."""
    g_t = policy.terminal_growth
    return {
        "multiples": multiples_at(price, im["eps"]),
        "expected_return": expected(price, value, im, (g_t, g_t, g_t)),
    }


def _roic_flags(roic: RoicTerms, policy: Policy) -> tuple[Flag, ...]:
    """The ROIC flags as this route reads them. It never zeroes the charge, so a fallback capital
    sum at or below zero is not "charge zeroed" here but an unavailable ROIC, in the same place;
    the ten-year flag, about the ten-year figure shown, stays."""
    if not roic.charge_off:
        return roic.flags
    unavailable = Flag(
        "roic-unavailable",
        "ROIC unavailable",
        "Operating capital summed to zero or below over the last "
        f"{policy.fallback_return_years} ROIC years and the marginal return is not usable, so the "
        "stable-growth value uses the moat's terminal return.",
    )
    return tuple(unavailable if f.code == "charge-zeroed" else f for f in roic.flags)
