"""The Mature Stable route (spec 6.6, calibration spec 5.10): the stable-growth value on
normalized trailing earnings, charged as the growth route charges.

E is trailing net income less the non-recurring gap on the diluted shares; when the margin flag
fires, E is scaled to the ten-year median operating margin. The value at belief is the
stable-growth value: the reverse DCF of ``mature_growth`` on a path that grows at the terminal
growth in every year, with the reinvestment charge of ``RoicTerms.charge``: the runway return in
years 1 to N−1 of the moat's runway, the terminal return in year N and the terminal, and off in
the runway years when the growth route's would be. A row whose runway return is the terminal
return, with the charge on, values at the one-stage perpetuity; a floored row, charged at r in
every year, values at EPV under any moat; a row whose runway return is above the terminal return
is worth more, and more for a longer runway; a charge-off row is worth more still, its runway
years uncharged. EPV is shown as the no-growth value. ``epv`` and ``stable_growth`` are a share;
``epv_total`` and ``stable_growth_total`` are the totals. The ROIC flags are the growth route's.

``growth_route`` is the growth route's value on the same row as a cross-check (calibration spec
5.7), or that route's refusal; the value, the levels and the designation stay on the stable-growth
value. Its implied growth moves with the price, as the growth route's does.

A missing or non-positive E refuses "no positive trailing earnings" (engine-round spec 9). The
refusal keeps ``e_trailing``, ``nri_gap``, ``eps``, ``shares``, ``moat``, ``price_facts`` and the
cross-check with its implied growth at the price, which ``route.reprice`` moves as on a valued
row; it raises no flag and cites no input beyond the ones every result carries.

Overrides (``method.md`` 14) through ``route_steps.chosen``: ``earnings.nri_gap`` the
non-recurring gap E is taken less, ``moat.class`` the moat and ``return.runway`` the runway return
of the charge; the cross-check reads the same moat, returns and gap.
"""

from typing import Any

from fairband.engine.anchor import moat_class
from fairband.engine.flags import margin_flag, median_margin
from fairband.engine.mature_stable import mature_stable_values, normalize_for_margin
from fairband.engine.route_mature_growth import cross_check_at_price, growth_cross_check
from fairband.engine.route_steps import (
    Context,
    Refused,
    RoicTerms,
    Valued,
    chosen,
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
from fairband.policy import Policy


def value_mature_stable(c: Context) -> Valued | Refused:
    i, t, policy = c.inputs, c.trailing, c.policy
    gap = chosen(c, "earnings.nri_gap", nri_gap(i))
    e = None if t.net_income is None else t.net_income - nil(gap) * c.shares
    moat = chosen(c, "moat.class", moat_class(i.moat_score, policy))
    runway_return: float | None = chosen(c, "return.runway", None)
    roic = RoicTerms.of(i.capital_years, moat, policy, runway_override=runway_return)
    growth_route = growth_cross_check(c, moat, roic)
    if e is None or e <= 0:
        # engine-round spec 9: the refusal keeps the cross-check, at the price
        refused: dict[str, Any] = {
            "e_trailing": e,
            "nri_gap": gap,
            "eps": eps(t, gap, None),
            "shares": c.shares,
            "moat": moat,
            "growth_route": cross_check_at_price(growth_route, c.price, c.shares, policy),
            "price_facts": price_facts_for(i.closes, c.price, c.today),
        }
        return Refused("no positive trailing earnings", (), refused, ())
    margin = ttm_margin(t)
    median = median_margin(i.series)
    flagged = margin_flag(i.series, margin, policy) is not None
    e_normalized = e
    if flagged and margin is not None and median is not None:
        e_normalized = normalize_for_margin(e, margin, median, flagged)

    runway = policy.runway_years[moat]
    epv_total, stable = mature_stable_values(e_normalized, roic.charge(policy), runway)
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
    flags = roic.flags + trailing_flags(i, t, gap, policy)
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
