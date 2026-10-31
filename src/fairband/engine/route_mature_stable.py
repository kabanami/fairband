"""The Mature Stable route (spec 6.6): the stable-growth value on normalized trailing earnings.

E is trailing net income less the non-recurring gap on the diluted shares; when the margin flag
fires, E is scaled to the ten-year median operating margin. The value at belief is the
stable-growth value at the moat's terminal ROIC, or with no charge when invested capital sums to
zero or below (the ROIC rules of spec 6.6); EPV is shown beside it as the no-growth value.
"""

import math
from dataclasses import asdict
from typing import Any

from fairband.engine.anchor import moat_class
from fairband.engine.flags import margin_flag, median_margin
from fairband.engine.mature_stable import mature_stable_values, normalize_for_margin
from fairband.engine.price_facts import price_facts
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
    trailing_flags,
    ttm_margin,
)
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
    charged = math.inf if roic.charge_off else roic.terminal
    epv_total, stable = mature_stable_values(
        e_normalized, charged, policy.required_return, policy.terminal_growth
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
        "epv": epv_total,
        "stable_growth": stable,
        "shares": c.shares,
        "value_per_share": value,
        "eps": eps(t, gap, None),
        **income(i.market_cap, t),
        "price_facts": asdict(price_facts(i.closes, c.today)),
    }
    im |= stable_at_price(im, c.price, value, policy)
    inputs = (
        *common_inputs(i, t, roic),
        data(i, "net_income_ttm", t.net_income, "USD", "statements"),
        *common_rules(policy, moat, roic),
    )
    flags = roic.flags + trailing_flags(i, t, gap, policy)
    return Valued("mature-stable", value, moat, im, inputs, flags)


def stable_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price; growth runs at the terminal growth."""
    return {
        "multiples": multiples_at(price, im["eps"]),
        "expected_return": expected(price, value, im, (None, None), policy.terminal_growth),
    }
