"""The revenue-growth route: High Growth and Young Growth on Damodaran's revenue DCF (growth-routes
spec 5), one route for both phases, on the core of ``revenue_growth``.

What it reads. Year 0 is trailing revenue; year 1 is the NTM consensus revenue, the sum of the
revenue means of the four quarters the earnings anchor picks (``anchor.ntm_quarters``). Years 2
and 3 grow at the annual consensus revenue steps from the base year (``anchor.base_fiscal_year``),
a mean of zero with no analyst count being no estimate (``anchor.consensus_value``); a missing step
holds the rate of the year before, and a present step landing on a year with fewer than
``analyst_min`` revenue analysts, or no count, is thin. Years 4 to 10 hold and fade as
``revenue_growth.growth_rates`` says, the held rate g_3 as resolved capped at the 90th-percentile
five-year sales growth of the sales class (``anchor.sales_class`` on trailing revenue, the class's
``sales_p90_5y``); the consensus steps are not capped. The operating margin moves in a straight line
from the trailing margin to the target margin, the median ten-year margin of the mature peers
(``revenue_growth.target_margin``); a trailing margin below ``loss_ramp_margin_bound`` is a loss
larger than revenue, and operating income moves instead in dollars from the trailing operating
income to the target's share of revenue in the convergence year, as the Start-up ramp does
(``MarginPath.in_dollars``; spec 2026-11-06 7.2). Sales-to-capital is the company's own five-year
marginal measure over the kept ROIC years (``RoicTerms``) when it is usable and, when the mature
peers have a median, at least ``own_sales_to_capital_min_share`` of it (spec 2026-11-06 7.1), else
the mature peers' median. Tax is the newest fiscal year's statutory rate, charged after the
forecast's own losses; the terminal reads year 10's operating income at the full rate
(``revenue_growth.terminal_nopat``). The terminal return is the moat's rule
(``roic.terminal_roic``) on the return on new capital at the target margin. Equity is the firm
value less debt plus cash from the newest annual balance sheet, each nil when unknown. The value is
discounted at r in every year.

Refusals, in this order: no trailing revenue (missing or not positive); no trailing operating
income, without which there is no trailing margin to start from; no statutory tax rate; an
incomplete NTM consensus (no four consecutive quarters, or one without a revenue mean); no
positive consensus revenue (an NTM revenue at or below zero); consensus revenue that falls to zero
or below within the path (g_2 or g_3 as resolved at or below −100%), with the path's flags; no
target margin, "no target margin: <n> mature peers", n counting the peers with a margin on enough years;
no sales-to-capital; a value a share at or below zero under the reinvestment charge. A row refused
for the target margin keeps the rebuild keys below and ``implied_margin``, the margin the price
needs (``None`` without a sales-to-capital); one refused for its value keeps every value-side
intermediate and ``implied_margin``; the others keep nothing.

Intermediates: ``ntm_revenue``; ``path`` (base_year, the revenue analysts of the years the two
steps land on, which step was held, the sales class and its cap); ``path_steps``, g_2 and g_3 as
resolved; ``growth_rates`` for years 1 to 10; ``margin_path`` (start, target, by_year, each year's
operating income over its revenue, and ramp, "margin" or "dollars");
``target_margin`` (value, the median; count; low; high; largest_symbol and largest_margin, the
largest counted peer by market cap, which sets nothing; peers, each with its margin and market cap;
source, "fmp" or "industry", and industry, the industry's name on the fallback);
``sales_to_capital`` (used, "own" or "peers"; own; own_usable; own_below_bound, true when the bound
alone rejected an own measure; peers; value); the tables
``revenue_by_year``, ``ebit_by_year``, ``tax_by_year``, ``nopat_by_year``, ``reinvestment_by_year``,
``fcff_by_year``; ``terminal_roic``, ``terminal_nopat`` (year 10's operating income at the full tax
rate), ``terminal_value``, ``firm_value``, ``debt``, ``cash``, ``equity``, ``shares``,
``value_per_share``; ``value_by_margin`` at the peers' lowest, median and highest margins (``low``,
``median``, ``high``), each with its own terminal return; ``return_on_new_capital`` and
``peer_roic_median``; ``failure_probability`` on a Young Growth row only; ``eps`` (the forward EPS
is the earnings anchor's when it stands), ``epv``, ``dividend_yield``, ``net_buyback_yield``,
``income_basis``, ``price_facts``; ``growth_route``, the Mature Growth route's cross-check as a
Mature Stable row carries it; at the price, ``implied_growth``, ``implied_margin``, ``multiples``,
``growth_share``, ``expected_return`` (its growth term the revenue path's years 2 to H + 1, H the
policy's repricing horizon, g_T past the path).

The rebuild keys: ``revenue_path`` (revenue0, ntm_revenue, the consensus steps as found with
``None`` for a missing one, hold ``None``, or the cap when it binds, high_growth_years, fade_years),
``margin_start``, ``tax_rate``, ``moat``, ``debt``, ``cash``, ``shares`` and ``sales_to_capital``; a
valued row adds ``margin_path``'s target and ``terminal_roic``. With the policy's r, g_T,
convergence year and loss ramp bound they rebuild the path, the margin path or the dollar ramp, and
the charge, so ``revenue_at_price`` moves a stored row to a new price from its intermediates alone,
and ``implied_margin_at_price`` moves the margin the price needs on any row that carries
``revenue_path``. The implied growth is the rate held in years 4 to the last high-growth year, the
fade recomputed from it, the cap not applied; the implied margin is the target margin, the
terminal return re-read at each trial; on the dollar ramp each trial rebuilds the ramp.

Flags, in order: ``sbc-basis-unknown`` when the cross-check has a value on an anchor whose basis is
unknown; the path's, ``path-held``, ``consensus-above-base-rate`` when the year-3 consensus is above
the cap, then ``few-analysts``; the capital build's, the ten-year ROIC flags and their line flags,
then ``line-not-presented:debt`` and ``line-not-presented:cash`` when a figure is unknown or
assembly's note names a line it lacks; ``peers-from-industry`` when the peers are the industry
fallback's (``CompanyInputs.peer_source``), on a row refused for the target margin or the
sales-to-capital too; ``tax-loss-history-unknown`` when the forecast has a loss
year or the trailing margin is below zero; ``margin-ramp-in-dollars`` on the dollar ramp, naming the
trailing margin and the ramp's two ends; ``return-above-peers`` when the return on new capital at
the target is above the peers' median ROIC; ``failure-not-charged`` on a Young Growth row; the
trailing flags; ``value-spread`` over the three margins, unbounded when the value at the lowest
margin is at or below zero and the median's is positive. The runway-return flags of the mature
routes are not raised: this route's charge does not read the runway return.

``consensus_beyond`` reads the annual consensus revenue past base + 2 for the Decline route's
run-off (spec 2026-11-06 6.1); this route's path ends its consensus at year 3.
"""

from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from itertools import count
from typing import Any, Literal

from fairband.engine.anchor import (
    AnnualEstimate,
    QuarterEstimate,
    base_fiscal_year,
    consensus_value,
    few_analysts,
    growth_step,
    moat_class,
    ntm_anchor,
    ntm_quarters,
    sales_class,
)
from fairband.engine.flags import value_spread_flag
from fairband.engine.multiples import epv, growth_share
from fairband.engine.revenue_growth import (
    Bridge,
    MarginPath,
    PeerSource,
    RevenueCharge,
    RevenuePath,
    RevenueValuation,
    TargetMargin,
    growth_rates,
    implied_hold_growth,
    implied_target_margin,
    margin_peers,
    own_sales_to_capital,
    peer_roic_median,
    peer_sales_to_capital,
    ramp_ends,
    resolved_steps,
    return_on_new_capital,
    revenue_valuation,
    target_margin,
)
from fairband.engine.roic import terminal_roic
from fairband.engine.route_mature_growth import cross_check_at_price, growth_cross_check
from fairband.engine.route_steps import (
    Context,
    Refused,
    RoicTerms,
    StartUpContext,
    Valued,
    common_inputs,
    common_rules,
    data,
    eps,
    expected,
    from_capital,
    income,
    millions,
    multiples_at,
    nil,
    nri_gap,
    present,
    price_facts_for,
    rule,
    signed,
    trailing_flags,
)
from fairband.engine.types import Flag, Phase, Provenance, TaggedInput
from fairband.policy import BaseRateClass, Moat, Policy

_NOT_POSITIVE = "value not positive under the reinvestment charge"
_PEERS = Provenance("FMP stock-peers and the peers' statements", None, None, None)
_MARGINS_TESTED = "the peers' lowest, median and highest target margins"
TAX_LOSS = Flag(
    "tax-loss-history-unknown",
    "Tax losses unknown",
    "The forecast carries its own losses forward from zero and the terminal value is taxed at the "
    "full rate; losses before the forecast are not stored, so the carry is unknown in both "
    "directions.",
)
_FAILURE = Flag(
    "failure-not-charged",
    "Failure not charged",
    "No survival table fits a listed company above $2 billion, so the failure probability is "
    "unavailable and the value is the going-concern value.",
)
_FAILURE_PROBABILITY = {
    "value": None,
    "reason": "no survival table fits a listed company above $2 billion",
}


@dataclass(frozen=True)
class _SalesToCapital:
    """The measure used (``None`` when neither stands), the company's own five-year marginal
    measure, whether it is usable and whether the bound on the peers' median alone rejected it,
    the mature peers' median, and the value used."""

    used: Literal["own", "peers"] | None
    own: float | None
    own_usable: bool
    own_below_bound: bool
    peers: float | None
    value: float | None


def value_revenue_growth(c: Context, phase: Phase) -> Valued | Refused:
    """The revenue DCF's value a share for a High Growth or Young Growth row, or the refusal."""
    i, t, policy = c.inputs, c.trailing, c.policy
    if t.revenue is None or t.revenue <= 0:
        return Refused("no trailing revenue")
    if t.operating_income is None:
        return Refused("no trailing operating income")
    tax = i.tax_rate_latest
    if tax is None:
        return Refused("no statutory tax rate")
    quarters = ntm_quarters(i.quarter_estimates, t.period_end)
    ntm = ntm_revenue(quarters)
    if quarters is None or ntm is None:
        return Refused("incomplete NTM consensus")
    if ntm <= 0:
        return Refused("no positive consensus revenue")
    base_year = base_fiscal_year(quarters)
    sales = sales_class(t.revenue / 1e6, policy)
    path, analysts, path_flags = revenue_path_for(
        t.revenue, ntm, i.annual_estimates, base_year, sales, policy
    )
    if any(g <= -1 for g in resolved_steps(path)[0]):
        return Refused("consensus revenue falls to zero or below within the path", path_flags)
    moat = moat_class(i.moat_score, policy)
    roic = RoicTerms.of(i.capital_years, moat, policy)
    s2c = _sales_to_capital(c, roic)
    rebuild: dict[str, Any] = {
        "revenue_path": {
            "revenue0": path.revenue0,
            "ntm_revenue": path.ntm_revenue,
            "steps": list(path.steps),
            "hold": path.hold,
            "high_growth_years": path.high_growth_years,
            "fade_years": path.fade_years,
        },
        "margin_start": t.operating_income / t.revenue,
        "tax_rate": tax,
        "moat": moat,
        "debt": nil(i.debt),
        "cash": nil(i.cash),
        "shares": c.shares,
        "sales_to_capital": asdict(s2c),
    }
    path_and_capital = path_flags + roic.result.flags + bridge_flags(c) + present(from_industry(c))
    target = target_margin(i.peers, policy)
    if target is None:
        counted = len(margin_peers(i.peers, policy))
        rebuild |= implied_margin_at_price(rebuild, c.price, policy)
        return Refused(f"no target margin: {counted} mature peers", path_and_capital, rebuild)
    if s2c.value is None:
        return Refused("no sales-to-capital", path_and_capital)

    start, bridge = rebuild["margin_start"], Bridge(rebuild["debt"], rebuild["cash"], c.shares)
    margin = _margin_path(start, target.value, policy)
    v, terminal = _at_margin(path, start, target.value, tax, s2c.value, moat, bridge, policy)
    value = v.value_per_share
    by_margin = {
        "low": _at_margin(path, start, target.low, tax, s2c.value, moat, bridge, policy)[0],
        "median": v,
        "high": _at_margin(path, start, target.high, tax, s2c.value, moat, bridge, policy)[0],
    }
    new_capital = return_on_new_capital(target.value, tax, s2c.value)
    peer_roic = peer_roic_median(i.peers)
    growth_route = growth_cross_check(c, moat, roic)
    anchor = ntm_anchor(quarters, t, i.street_ttm_eps, c.shares, tax, c.price, policy)
    gap = nri_gap(i)
    e = eps(t, gap, anchor.ntm_eps if anchor.refusal is None else None)
    (g2, g3), held = resolved_steps(path)
    im: dict[str, Any] = {
        "ntm_revenue": ntm,
        "path": {
            "base_year": base_year,
            "analysts": list(analysts),
            "held": list(held),
            "sales_class": sales.label,
            "cap": sales.sales_p90_5y,
        },
        "path_steps": [g2, g3],
        "growth_rates": list(growth_rates(path)),
        "margin_path": {
            "start": start,
            "target": target.value,
            "by_year": list(v.margins),
            "ramp": "dollars" if margin.in_dollars else "margin",
        },
        "target_margin": target_intermediates(target, i.peer_source),
        **rebuild,
        "revenue_by_year": list(v.revenue),
        "ebit_by_year": list(v.ebit),
        "tax_by_year": list(v.tax),
        "nopat_by_year": list(v.nopat),
        "reinvestment_by_year": list(v.reinvestment),
        "fcff_by_year": list(v.fcff),
        "terminal_roic": terminal,
        "terminal_nopat": v.terminal_nopat,
        "terminal_value": v.terminal_value,
        "firm_value": v.firm_value,
        "equity": v.equity,
        "value_per_share": value,
        "value_by_margin": {key: x.value_per_share for key, x in by_margin.items()},
        "return_on_new_capital": new_capital,
        "peer_roic_median": peer_roic,
        "eps": e,
        "epv": None if e["clean"] is None else epv(e["clean"], policy.required_return),
        **income(i.market_cap, t),
        "price_facts": price_facts_for(i.closes, c.price, c.today),
        "growth_route": growth_route,
    }
    young = phase == "Young Growth"
    if young:
        im["failure_probability"] = dict(_FAILURE_PROBABILITY)
    sbc = anchor.flags if growth_route.get("value_per_share") is not None else ()
    flags = (
        sbc
        + path_and_capital
        + ((TAX_LOSS,) if start < 0 or any(x < 0 for x in v.ebit) else ())
        + present(_ramp_in_dollars(margin, v.revenue, path.revenue0))
        + present(_return_above_peers(new_capital, peer_roic))
        + ((_FAILURE,) if young else ())
        + trailing_flags(i, t, gap, policy)
        + present(_value_spread(im["value_by_margin"], target, policy))
    )
    if value <= 0:
        return Refused(_NOT_POSITIVE, flags, im | implied_margin_at_price(im, c.price, policy))
    im |= revenue_at_price(im, c.price, value, policy)
    industry = peer_industry(c)
    of_industry = "" if industry is None else f" of the {industry} industry"
    inputs = (
        *common_inputs(i, t, roic),
        data(i, "ntm_revenue", ntm, "USD", "estimates_quarter"),
        step_input(c, "path_step_2", path.steps[0], held[0]),
        step_input(c, "path_step_3", path.steps[1], held[1]),
        from_peers(
            c,
            "target_margin",
            target.value,
            f"the median ten-year operating margin of {target.count} mature peers{of_industry}",
        ),
        _sales_to_capital_input(c, s2c),
        data(i, "debt", i.debt, "USD", "statements"),
        data(i, "cash", i.cash, "USD", "statements"),
        *common_rules(policy, moat, terminal),
        rule(policy, "high_growth_years", policy.high_growth_years, "years"),
        _cap_input(policy, sales, path.hold is not None),
        rule(policy, "fade_years", policy.fade_years, "years"),
        rule(policy, "margin_convergence_year", policy.margin_convergence_year, "year"),
        *_rule_if(
            margin.in_dollars, policy, "loss_ramp_margin_bound", policy.loss_ramp_margin_bound
        ),
        rule(policy, "peer_min", policy.peer_min, "peers"),
        *_rule_if(
            s2c.own_below_bound,
            policy,
            "own_sales_to_capital_min_share",
            policy.own_sales_to_capital_min_share,
        ),
        *industry_peer_max_input(policy, industry),
    )
    return Valued("revenue-growth", value, moat, im, inputs, flags)


def revenue_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price, from the value-side intermediates ``im``: the
    implied growth and margin, the multiples, the growth share, the expected return on the revenue
    path's years 2 to H + 1, and the cross-check's implied growth."""
    s2c = im["sales_to_capital"]["value"]
    margin = _margin_path(im["margin_start"], im["margin_path"]["target"], policy)
    charge = RevenueCharge(policy.required_return, policy.terminal_growth, im["terminal_roic"], s2c)
    path, bridge = _rebuilt_path(im, policy), _rebuilt_bridge(im)
    return {
        "implied_growth": implied_hold_growth(price, path, margin, im["tax_rate"], charge, bridge),
        **implied_margin_at_price(im, price, policy),
        "multiples": multiples_at(price, im["eps"]),
        "growth_share": None if im["epv"] is None else growth_share(im["epv"], price),
        "expected_return": expected(
            price,
            value,
            im,
            im["growth_rates"][1:],
            policy.repricing_horizon_years,
            policy.terminal_growth,
        ),
        "growth_route": cross_check_at_price(im["growth_route"], price, im["shares"], policy),
    }


def implied_margin_at_price(im: dict[str, Any], price: float, policy: Policy) -> dict[str, Any]:
    """The margin the price needs, from the rebuild keys in ``im``: the target margin at which the
    value a share equals ``price``, the terminal return re-read and, on the dollar ramp, the ramp
    rebuilt at each trial; ``None`` without a sales-to-capital or when the policy's bounds hold no
    such margin."""
    s2c = im["sales_to_capital"]["value"]
    if s2c is None:
        return {"implied_margin": None}
    start = im["margin_start"]
    margin = _margin_path(start, start, policy)  # the solve sets the target
    path, bridge = _rebuilt_path(im, policy), _rebuilt_bridge(im)
    implied = implied_target_margin(
        price, path, margin, im["tax_rate"], s2c, im["moat"], policy, bridge
    )
    return {"implied_margin": implied}


def ntm_revenue(quarters: tuple[QuarterEstimate, ...] | None) -> float | None:
    """The sum of the NTM quarters' revenue means; ``None`` without the quarters or with one that
    lacks its mean."""
    if quarters is None:
        return None
    means = [q.revenue for q in quarters if q.revenue is not None]
    return sum(means) if len(means) == len(quarters) else None


def revenue_path_for(
    revenue0: float,
    ntm: float,
    annual: tuple[AnnualEstimate, ...],
    base_year: int,
    sales: BaseRateClass | None,
    policy: Policy,
) -> tuple[RevenuePath, tuple[int | None, int | None], tuple[Flag, ...]]:
    """The revenue path from the annual consensus revenue of the base year and the next two, its
    held rate the sales class's cap when g_3 as resolved is above it, the revenue analysts of the
    years the two steps land on, and the path's flags: ``path-held``,
    ``consensus-above-base-rate``, then ``few-analysts``. Without a sales class nothing is capped
    or flagged above the base rate: the Decline route reads only years 1 to 3 of the path."""
    by_year = {x.fiscal_year: x for x in annual}
    rows = [by_year.get(base_year + k) for k in range(3)]
    points = [(None, None) if r is None else (r.revenue, r.analysts_revenue) for r in rows]
    values = [consensus_value(mean, n) for mean, n in points]
    steps = (growth_step(values[0], values[1]), growth_step(values[1], values[2]))
    analysts = (points[1][1], points[2][1])
    found = RevenuePath(
        revenue0,
        ntm,
        steps,
        None,
        policy.high_growth_years,
        policy.fade_years,
        policy.terminal_growth,
    )
    (_, g3), _ = resolved_steps(found)
    path = found
    if sales is not None and g3 > sales.sales_p90_5y:
        path = replace(found, hold=sales.sales_p90_5y)
    flags = (
        present(_path_held(path, values, base_year))
        + (() if sales is None else present(_above_base_rate(path, sales)))
        + present(few_analysts(base_year, steps, analysts, policy))
    )
    return path, analysts, flags


def consensus_beyond(
    annual: Sequence[AnnualEstimate], base_year: int, policy: Policy
) -> tuple[float, ...]:
    """The consensus revenue steps for base + 3 onward, each from the year before's consensus
    revenue (``consensus_value``), while the year has a revenue mean above zero and at least
    ``analyst_min`` revenue analysts. The first year that fails either test ends them at the year
    before: nothing is held past year 3, a thin year is not read, and no step falls 100% or more.
    Empty when base + 2 has no consensus revenue above zero to step from (``growth_step``). Spec
    2026-11-06 6.1."""
    by_year = {x.fiscal_year: x for x in annual}
    third = by_year.get(base_year + 2)
    earlier = None if third is None else consensus_value(third.revenue, third.analysts_revenue)
    steps: list[float] = []
    for year in count(base_year + 3):
        row = by_year.get(year)
        if row is None or row.analysts_revenue is None or row.analysts_revenue < policy.analyst_min:
            break
        later = consensus_value(row.revenue, row.analysts_revenue)
        step = growth_step(earlier, later)
        if later is None or later <= 0 or step is None:
            break
        steps.append(step)
        earlier = later
    return tuple(steps)


def _path_held(path: RevenuePath, values: list[float | None], base_year: int) -> Flag | None:
    """``path-held`` naming the fiscal years whose consensus revenue left a step missing, and the
    rate each held step took. A step from year y to y + 1 is missing when y's mean is missing or
    not positive, or y + 1's is missing; each such year is named."""
    (g2, _), held = resolved_steps(path)
    years: set[int] = set()
    clauses: list[str] = []
    for k, (was_held, rate) in enumerate(zip(held, (growth_rates(path)[0], g2), strict=True)):
        if not was_held:
            continue
        earlier, later = values[k], values[k + 1]
        if earlier is None or earlier <= 0:
            years.add(base_year + k)
        if later is None:
            years.add(base_year + k + 1)
        clauses.append(f"year {k + 2} holds the {rate:.1%} of the year before")
    if not clauses:
        return None
    return Flag(
        "path-held",
        "Path held",
        f"The consensus revenue for fiscal {' and '.join(map(str, sorted(years)))} is missing or "
        f"not positive, so {' and '.join(clauses)}.",
    )


def _above_base_rate(path: RevenuePath, sales: BaseRateClass) -> Flag | None:
    """``consensus-above-base-rate`` when the path holds the sales class's cap, g_3 as resolved
    being above it; naming both rates and the class."""
    if path.hold is None:
        return None
    (_, g3), _ = resolved_steps(path)
    cap = path.hold
    return Flag(
        "consensus-above-base-rate",
        "Above base rate",
        f"The year-3 consensus growth of {g3:.1%} is above {cap:.1%}, the Base Rate Book's "
        f"90th-percentile five-year sales growth for the {sales.label} sales class, so years 4 "
        f"and 5 hold {cap:.1%} and the fade starts from it.",
    )


def _sales_to_capital(c: Context, roic: RoicTerms) -> _SalesToCapital:
    """The company's own five-year marginal measure over the kept ROIC years, each year's revenue
    its fiscal year's, when usable and, with a peers' median, at least the policy's share of it
    (spec 2026-11-06 7.1); else the mature peers' median; else none."""
    i, policy = c.inputs, c.policy
    revenue = {fy.year: fy.revenue for fy in i.series if fy.revenue is not None}
    own, usable = own_sales_to_capital(
        roic.result.by_year,
        revenue,
        policy.marginal_return_span_years,
        policy.marginal_capital_growth_min,
    )
    peers = peer_sales_to_capital(i.peers, policy)
    below = (
        usable
        and own is not None
        and peers is not None
        and own < policy.own_sales_to_capital_min_share * peers
    )
    if usable and not below:
        return _SalesToCapital("own", own, True, False, peers, own)
    if peers is not None:
        return _SalesToCapital("peers", own, False, below, peers, peers)
    return _SalesToCapital(None, own, False, False, None, None)


def _margin_path(start: float, target: float, policy: Policy) -> MarginPath:
    """The margin path from the trailing margin to ``target``, on the dollar ramp when the
    trailing margin is below the loss ramp bound: a loss larger than revenue (spec 2026-11-06
    7.2)."""
    in_dollars = start < policy.loss_ramp_margin_bound
    return MarginPath(start, target, policy.margin_convergence_year, in_dollars)


def _at_margin(
    path: RevenuePath,
    start: float,
    target: float,
    tax: float,
    sales_to_capital: float,
    moat: Moat,
    bridge: Bridge,
    policy: Policy,
) -> tuple[RevenueValuation, float]:
    """The valuation at a target margin, and its terminal return: the moat's rule on the return on
    new capital at that margin."""
    new_capital = return_on_new_capital(target, tax, sales_to_capital)
    terminal = terminal_roic(new_capital, moat, policy)
    charge = RevenueCharge(
        policy.required_return, policy.terminal_growth, terminal, sales_to_capital
    )
    margin = _margin_path(start, target, policy)
    return revenue_valuation(path, margin, tax, charge, bridge), terminal


def _ramp_in_dollars(
    margin: MarginPath, revenue: tuple[float, ...], revenue0: float
) -> Flag | None:
    """``margin-ramp-in-dollars`` on the dollar ramp, naming the trailing margin, the trailing
    operating income and the target's share of revenue the ramp reaches in the convergence year."""
    if not margin.in_dollars:
        return None
    e0, end = ramp_ends(revenue, margin, revenue0)
    return Flag(
        "margin-ramp-in-dollars",
        "Ramp in dollars",
        f"The trailing loss is larger than revenue (margin {signed(margin.start)}), so operating "
        f"income moves in dollars from {millions(e0)} to the target margin's {millions(end)} "
        f"by year {margin.convergence_year}, as the Start-up ramp does.",
    )


def _rule_if(cited: bool, policy: Policy, name: str, value: float) -> tuple[TaggedInput, ...]:
    """A RULE input, a ratio, cited only on a row it applied to."""
    return (rule(policy, name, value, "ratio"),) if cited else ()


def bridge_flags(c: Context | StartUpContext) -> tuple[Flag, ...]:
    """``line-not-presented:debt`` and ``:cash`` for a figure the bridge counts as nil in part or
    in full: unknown, or with a line assembly's note names as not presented."""
    i = c.inputs
    lines = (
        ("debt", i.debt, "short- and long-term debt"),
        ("cash", i.cash, "cash and short-term investments"),
    )
    return tuple(
        Flag(
            f"line-not-presented:{name}",
            f"Line not presented: {name}",
            f"The newest annual balance sheet does not present all of the {words} "
            f"({i.notes.get(name) or 'no line on file'}); what is missing counts as nil in the "
            "bridge from firm value to equity.",
        )
        for name, figure, words in lines
        if figure is None or name in i.notes
    )


def peer_industry(c: Context | StartUpContext) -> str | None:
    """The industry the peers came from on the industry fallback; ``None`` on FMP's list."""
    source = c.inputs.peer_source
    return source.industry if source is not None and source.kind == "industry" else None


def industry_peer_max_input(policy: Policy, industry: str | None) -> tuple[TaggedInput, ...]:
    """The bound on the industry fallback's peers, cited only on a row whose peers it bounded."""
    if industry is None:
        return ()
    note = f"the largest mature companies of the {industry} industry taken, at most"
    return (rule(policy, "industry_peer_max", policy.industry_peer_max, "peers", note),)


def from_industry(c: Context | StartUpContext) -> Flag | None:
    """``peers-from-industry`` when the peers are the industry fallback's, naming FMP's count, the
    industry and the count taken, the sentence's end worded by that count."""
    source, policy = c.inputs.peer_source, c.policy
    if source is None or source.kind != "industry":
        return None
    n, k, industry = source.fmp_counted, len(c.inputs.peers), source.industry
    if k == 0:
        taken = f"and the {industry} industry has no mature company in the universe either."
    elif k == 1:
        taken = f"so the peer is the one mature company of the {industry} industry in the universe."
    else:
        taken = (
            f"so the peers are the {k} largest mature companies of the {industry} industry in "
            "the universe."
        )
    return Flag(
        "peers-from-industry",
        "Industry peers",
        f"FMP's peer list leaves {n} mature peer{'' if n == 1 else 's'} with a margin on "
        f"{policy.peer_margin_min_years} years or more, fewer than {policy.peer_min}, {taken}",
    )


def _return_above_peers(new_capital: float, peer_roic: float | None) -> Flag | None:
    """``return-above-peers`` when the return on new capital at the target is above the peers'
    median ROIC (Damodaran's implied-ROIC check); ``None`` without a median."""
    if peer_roic is None or new_capital <= peer_roic:
        return None
    return Flag(
        "return-above-peers",
        "Return above peers",
        f"The return on new capital at the target margin, {new_capital:.1%}, is above the mature "
        f"peers' median return of {peer_roic:.1%}; the sales-to-capital may be too high "
        "(Damodaran's check).",
    )


def _value_spread(by_margin: dict[str, float], target: TargetMargin, policy: Policy) -> Flag | None:
    """``value-spread`` over the three target margins: unbounded when the value at the lowest
    margin is at or below zero and the median's is positive, where the mature routes' rule, which
    needs a positive lowest value, would be silent; else that rule."""
    low, median = by_margin["low"], by_margin["median"]
    if low <= 0 < median:
        return Flag(
            "value-spread",
            "Value spread",
            f"The value is at or below zero at the lowest mature-peer margin of {target.low:.1%} "
            f"and {median:,.2f} a share at the median, so the spread across the peers' margins is "
            "unbounded.",
        )
    return value_spread_flag(list(by_margin.values()), policy, _MARGINS_TESTED)


def target_intermediates(target: TargetMargin, source: PeerSource | None) -> dict[str, Any]:
    """The target margin's figures, its counted peers, and the peers' source: ``"fmp"`` with no
    industry unless they are the industry fallback's."""
    return {
        "value": target.value,
        "count": target.count,
        "low": target.low,
        "high": target.high,
        "largest_symbol": target.largest_symbol,
        "largest_margin": target.largest_margin,
        "peers": [
            {"symbol": p.symbol, "margin": p.margin, "market_cap": p.market_cap}
            for p in target.peers
        ],
        "source": "fmp" if source is None else source.kind,
        "industry": None if source is None else source.industry,
    }


def step_input(c: Context, name: str, step: float | None, held: bool) -> TaggedInput:
    """A consensus revenue step as found; a held one is missing, and its note says so."""
    note = "no consensus step: the year holds the rate of the year before" if held else None
    return data(c.inputs, name, step, "ratio", "estimates_annual", note)


def _cap_input(policy: Policy, sales: BaseRateClass, binds: bool) -> TaggedInput:
    """The cap on the held rate, its note naming the sales class and whether it binds."""
    whether = (
        "binds: the year-3 consensus is above it"
        if binds
        else "does not bind: the year-3 consensus is at or below it"
    )
    note = (
        "the Base Rate Book's 90th-percentile five-year sales growth for the "
        f"{sales.label} sales class; {whether}"
    )
    return rule(policy, "held_growth_cap", sales.sales_p90_5y, "ratio", note)


def from_peers(
    c: Context | StartUpContext, name: str, value: float | None, note: str
) -> TaggedInput:
    """A DATA input read from the mature peers' figures, cited to the peers call and statements, or
    on the industry fallback to the universe's industry and the peers' statements."""
    industry = peer_industry(c)
    provenance = (
        _PEERS
        if industry is None
        else Provenance(
            f"the universe's {industry} industry and the peers' statements", None, None, None
        )
    )
    return replace(data(c.inputs, name, value, "ratio", note=note), provenance=provenance)


def _sales_to_capital_input(c: Context, s2c: _SalesToCapital) -> TaggedInput:
    """The sales-to-capital used: the own measure from the statements (an estimate under the
    intangibles method when invested capital took it), or the peers' median, its note naming both
    figures when the bound alone rejected the own measure."""
    if s2c.used == "own":
        return from_capital(
            c.inputs, "sales_to_capital", s2c.value, "the company's own five-year marginal measure"
        )
    industry = peer_industry(c)
    median = "the mature peers' median" + ("" if industry is None else f" ({industry} industry)")
    why = (
        f"the own measure, {s2c.own:.2f}, is below half the peers' median, {s2c.peers:.2f}"
        if s2c.own_below_bound
        else "the own measure is not usable"
    )
    return from_peers(c, "sales_to_capital", s2c.value, f"{median}; {why}")


def _rebuilt_path(im: dict[str, Any], policy: Policy) -> RevenuePath:
    p = im["revenue_path"]
    s2, s3 = p["steps"]
    return RevenuePath(
        p["revenue0"],
        p["ntm_revenue"],
        (s2, s3),
        p["hold"],
        p["high_growth_years"],
        p["fade_years"],
        policy.terminal_growth,
    )


def _rebuilt_bridge(im: dict[str, Any]) -> Bridge:
    return Bridge(im["debt"], im["cash"], im["shares"])
