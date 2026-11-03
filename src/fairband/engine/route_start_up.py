"""The Start-up route (spec 2026-11-03 section 9): no value by design, as design.md 6.8 decided, but
the figures that frame the price: the revenue in year 10 the price needs at the mature peers'
margin, the net cash a share as a floor, and the years the cash covers the trailing burn.

Which rows. A company the classifier puts in Start-up (revenue zero now or three years ago), past
the guards ``route.value_company`` runs before it: no universe deciles, the assembly's refusal, a
foreign filer, no price, no positive diluted share count. "No trailing figures" does not refuse: a
pre-revenue company may lack them, and the route reads what exists. ``value_start_up`` always
returns the refusal "Start-up: no value by design" with its figures; what it cannot compute
carries its own reason inside the intermediates.

The requirement. EV_price = market cap + debt − cash, debt and cash from the newest annual balance
sheet, each nil when unknown. At or below zero the price needs no revenue: the requirement is 0.
Otherwise it is the year-10 revenue at which the ramp of ``requirement.ramp_ev`` is worth
EV_price (``requirement.required_revenue``): from R0, trailing revenue (0 without one), and E0,
trailing operating income (else the last fiscal year's, else 0), to the target margin, the mature
peers' median ten-year margin (``revenue_growth.target_margin``, on the industry's peers when
assembly fell back to them), at the peers' median sales-to-capital (a Start-up's own measure
never stands), the newest fiscal year's statutory tax rate, r and g_T in every year, and the
terminal return of the revenue-growth route: the moat's rule (``roic.terminal_roic``) on the
return on new capital at the target margin, m* × (1 − tax rate) × sales-to-capital. It reads the
peers' margin and sales-to-capital and the company's statutory rate; the company has no return
on capital to read (r without all three inputs, when there is no requirement anyway).
The requirement's reasons, the first that applies: "no target margin: <n> mature peers", "no
sales-to-capital", "no statutory tax rate", "no market cap", "no revenue reaches the price".

The cash floor and the burn cover. ``cash_floor`` = (cash − debt) ÷ diluted shares. The burn is
−(trailing operating cash flow + trailing capital spending) when that sum is below zero;
``burn_cover_years`` is cash over the burn, "not burning" when the sum is zero or above, ``None``
without both trailing figures or without a cash figure, and then never ``burn-cover-short``: an
unknown cash is not a cash of nil.

Intermediates: ``requirement`` (reason, ``None`` when it is computed; revenue_y10; ev_price;
revenue_0; operating_income_0; target_margin, the revenue-growth route's record of the peers;
sales_to_capital, used "peers", own ``None``, own_usable false, peers, value; tax_rate;
terminal_roic; path, the ten years' revenue, ebit, tax, nopat, reinvestment and fcff;
terminal_value; ``None`` where the reason leaves a figure uncomputed), ``cash_floor``,
``burn_cover_years``, ``burn`` (``None`` when not burning), ``debt``, ``cash``, ``cash_known``
(false when no cash figure is on file: ``cash`` is then the nil the floor and the requirement
count), ``shares``, ``market_cap``; ``route`` adds ``price_facts``.

The rebuild keys: the requirement's revenue_0, operating_income_0, target_margin's value,
sales_to_capital's value, tax_rate and terminal_roic, with the policy's r and g_T.
``start_up_at_price`` rebuilds the requirement from them at the market cap of a new price
(``market_cap_at``), and ``below_net_cash`` re-reads its flag; nothing else moves.

Flags, in order: ``line-not-presented:debt`` and ``:cash``; ``peers-from-industry`` when the peers
are the industry's; ``tax-loss-history-unknown`` when the requirement's ramp starts from a loss or
has a loss year; ``below-net-cash`` when EV_price is at or below zero; ``burn-cover-short`` below
``burn_cover_flag_years``. Never the ROIC flags, ``return-above-peers``, ``few-analysts`` or the
trailing flags: no path reads the consensus or the company's return.
"""

from typing import Any

from fairband.engine.anchor import TrailingFigures, moat_class
from fairband.engine.classifier import FiscalYear, Series
from fairband.engine.requirement import RampValuation, ramp_ev, required_revenue
from fairband.engine.revenue_growth import (
    TargetMargin,
    margin_peers,
    peer_sales_to_capital,
    return_on_new_capital,
    target_margin,
)
from fairband.engine.roic import terminal_roic
from fairband.engine.route_revenue_growth import (
    TAX_LOSS,
    bridge_flags,
    from_industry,
    from_peers,
    industry_peer_max_input,
    peer_industry,
    target_intermediates,
)
from fairband.engine.route_steps import Refused, StartUpContext, data, nil, present, rule
from fairband.engine.types import Flag, TaggedInput
from fairband.policy import Moat, Policy

_REASON = "Start-up: no value by design"
_NOT_BURNING = "not burning"
_UNSOLVED: dict[str, Any] = {
    "revenue_y10": None,
    "ev_price": None,
    "path": None,
    "terminal_value": None,
}


def value_start_up(c: StartUpContext) -> Refused:
    """A Start-up row's refusal with its figures: the requirement, the cash floor, the burn
    cover."""
    i, t, policy = c.inputs, c.trailing, c.policy
    debt, cash = nil(i.debt), nil(i.cash)
    moat = moat_class(i.moat_score, policy)
    target = target_margin(i.peers, policy)
    s2c = peer_sales_to_capital(i.peers, policy)
    tax = i.tax_rate_latest
    terminal = (
        policy.required_return
        if target is None or s2c is None or tax is None
        else terminal_roic(return_on_new_capital(target.value, tax, s2c), moat, policy)
    )
    revenue0 = 0.0 if t is None or t.revenue is None else t.revenue
    ebit0, fiscal = _operating_income_0(i.series, t)
    found: dict[str, Any] = {
        "reason": _input_reason(target, s2c, tax, c),
        **_UNSOLVED,
        "revenue_0": revenue0,
        "operating_income_0": ebit0,
        "target_margin": None if target is None else target_intermediates(target, i.peer_source),
        "sales_to_capital": None if s2c is None else _s2c_record(s2c),
        "tax_rate": tax,
        "terminal_roic": terminal,
    }
    requirement = _requirement(found, i.market_cap, debt, cash, policy)
    burn, cover = _burn(t, i.cash)
    im: dict[str, Any] = {
        "requirement": requirement,
        "cash_floor": (cash - debt) / c.shares,
        "burn_cover_years": cover,
        "burn": burn,
        "debt": debt,
        "cash": cash,
        "cash_known": i.cash is not None,
        "shares": c.shares,
        "market_cap": i.market_cap,
    }
    flags = (
        bridge_flags(c)
        + present(from_industry(c))
        + ((TAX_LOSS,) if _loss(requirement) else ())
        + present(below_net_cash(i.market_cap, debt, cash))
        + present(_cover_short(burn, cover, policy))
    )
    inputs = _inputs(c, moat, terminal, target, s2c, fiscal)
    return Refused(_REASON, flags, im, inputs)


def start_up_at_price(
    im: dict[str, Any], market_cap: float | None, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price, from the rebuild keys in ``im``: the market cap
    at the new price and the requirement rebuilt at it; a requirement whose reason is one of its
    inputs stays as it is."""
    requirement = _requirement(im["requirement"], market_cap, im["debt"], im["cash"], policy)
    return {"market_cap": market_cap, "requirement": requirement}


def market_cap_at(market_cap: float | None, price: float | None, new_price: float) -> float | None:
    """The market cap at a new price: the one the row read, moved with the price at the share
    count it implies; ``None`` without it or its price."""
    if market_cap is None or price is None:
        return None
    return market_cap * (new_price / price)


def below_net_cash(market_cap: float | None, debt: float, cash: float) -> Flag | None:
    """``below-net-cash`` when the market cap is at or below the net cash, so EV_price is at or
    below zero."""
    if market_cap is None or market_cap + debt - cash > 0:
        return None
    return Flag(
        "below-net-cash",
        "Below net cash",
        f"The price is covered by net cash: market cap {market_cap:,.0f} against net cash "
        f"{cash - debt:,.0f}.",
    )


def _input_reason(
    target: TargetMargin | None, s2c: float | None, tax: float | None, c: StartUpContext
) -> str | None:
    """The requirement's reason when one of its inputs is missing, in spec 9.2's order."""
    if target is None:
        return f"no target margin: {len(margin_peers(c.inputs.peers, c.policy))} mature peers"
    if s2c is None:
        return "no sales-to-capital"
    if tax is None:
        return "no statutory tax rate"
    return None


def _requirement(
    found: dict[str, Any], market_cap: float | None, debt: float, cash: float, policy: Policy
) -> dict[str, Any]:
    """The requirement at ``market_cap`` from the rebuild keys in ``found``: the year-10 revenue,
    EV_price, the ramp and its terminal value; 0 when EV_price is at or below zero; or the reason.
    ``found`` is returned as it is when one of its inputs is missing."""
    if any(found[key] is None for key in ("target_margin", "sales_to_capital", "tax_rate")):
        return found
    if market_cap is None:
        return found | _UNSOLVED | {"reason": "no market cap"}
    ev_price = market_cap + debt - cash
    ramp = {
        "revenue0": found["revenue_0"],
        "ebit0": found["operating_income_0"],
        "target_margin": found["target_margin"]["value"],
        "tax_rate": found["tax_rate"],
        "sales_to_capital": found["sales_to_capital"]["value"],
        "r": policy.required_return,
        "g_t": policy.terminal_growth,
        "terminal_return": found["terminal_roic"],
    }
    revenue = 0.0 if ev_price <= 0 else required_revenue(ev_price, **ramp)
    if revenue is None:
        return found | _UNSOLVED | {"reason": "no revenue reaches the price", "ev_price": ev_price}
    v = ramp_ev(revenue, **ramp)
    return found | {
        "reason": None,
        "revenue_y10": revenue,
        "ev_price": ev_price,
        "path": _path(v),
        "terminal_value": v.terminal_value,
    }


def _path(v: RampValuation) -> dict[str, list[float]]:
    return {
        "revenue": list(v.revenue),
        "ebit": list(v.ebit),
        "tax": list(v.tax),
        "nopat": list(v.nopat),
        "reinvestment": list(v.reinvestment),
        "fcff": list(v.fcff),
    }


def _s2c_record(value: float) -> dict[str, Any]:
    """The sales-to-capital as the revenue-growth route records it: the peers' median; a
    Start-up reads no own measure."""
    return {"used": "peers", "own": None, "own_usable": False, "peers": value, "value": value}


def _operating_income_0(
    series: Series, t: TrailingFigures | None
) -> tuple[float, FiscalYear | None]:
    """E0: the trailing operating income; else the last fiscal year's, with that year; else 0."""
    if t is not None and t.operating_income is not None:
        return t.operating_income, None
    last = series[-1]
    return nil(last.operating_income), last


def _burn(t: TrailingFigures | None, cash: float | None) -> tuple[float | None, float | str | None]:
    """The yearly burn and the years the cash covers it: (``None``, "not burning") when the
    trailing free cash flow is zero or above; ``None`` and ``None`` without both trailing
    figures; the burn and ``None`` without a cash figure."""
    if t is None or t.cfo is None or t.capex is None:
        return None, None
    flow = t.cfo + t.capex
    if flow >= 0:
        return None, _NOT_BURNING
    return -flow, None if cash is None else cash / -flow


def _cover_short(burn: float | None, cover: float | str | None, policy: Policy) -> Flag | None:
    if burn is None or not isinstance(cover, float) or cover >= policy.burn_cover_flag_years:
        return None
    return Flag(
        "burn-cover-short",
        "Cash cover short",
        f"Cash covers {cover:.1f} years of the trailing burn of {burn:,.0f} a year.",
    )


def _loss(requirement: dict[str, Any]) -> bool:
    """Whether the requirement's ramp starts from a loss or has a loss year: the tax carry it
    starts from zero is then unknown."""
    path = requirement["path"]
    if path is None:
        return False
    return requirement["operating_income_0"] < 0 or any(e < 0 for e in path["ebit"])


def _inputs(
    c: StartUpContext,
    moat: Moat,
    terminal: float,
    target: TargetMargin | None,
    s2c: float | None,
    fiscal: FiscalYear | None,
) -> tuple[TaggedInput, ...]:
    """The route's DATA and RULE inputs, beyond the ones every result carries."""
    i, t, policy = c.inputs, c.trailing, c.policy
    industry = peer_industry(c)
    of_industry = "" if industry is None else f" of the {industry} industry"
    median = "the mature peers' median" + ("" if industry is None else f" ({industry} industry)")
    trailing = (
        ()
        if t is None
        else (
            data(i, "revenue_ttm", t.revenue, "USD", "statements"),
            data(i, "operating_income_ttm", t.operating_income, "USD", "statements"),
        )
    )
    fiscal_income = (
        ()
        if fiscal is None
        else (
            data(
                i,
                "operating_income_fy",
                fiscal.operating_income,
                "USD",
                "statements",
                f"fiscal {fiscal.year}: the trailing operating income is missing",
            ),
        )
    )
    flows = (
        ()
        if t is None
        else (
            data(i, "cfo_ttm", t.cfo, "USD", "statements"),
            data(i, "capex_ttm", t.capex, "USD", "statements"),
        )
    )
    peers = (
        ()
        if target is None
        else (
            from_peers(
                c,
                "target_margin",
                target.value,
                f"the median ten-year operating margin of {target.count} mature peers{of_industry}",
            ),
        )
    ) + (
        ()
        if s2c is None
        else (from_peers(c, "sales_to_capital", s2c, f"{median}; a Start-up reads no own measure"),)
    )
    return (
        data(i, "market_cap", i.market_cap, "USD"),
        *trailing,
        *fiscal_income,
        *flows,
        data(i, "tax_rate_latest", i.tax_rate_latest, "ratio"),
        data(i, "moat_score", i.moat_score, "score"),
        *peers,
        data(i, "debt", i.debt, "USD", "statements"),
        data(i, "cash", i.cash, "USD", "statements"),
        rule(policy, "required_return", policy.required_return, "ratio"),
        rule(policy, "terminal_growth", policy.terminal_growth, "ratio"),
        rule(policy, "moat_class", None, "class", moat),
        rule(policy, "terminal_roic", terminal, "ratio", f"{moat} moat"),
        rule(policy, "peer_min", policy.peer_min, "peers"),
        rule(policy, "peer_margin_min_years", policy.peer_margin_min_years, "years"),
        *industry_peer_max_input(policy, industry),
        rule(policy, "burn_cover_flag_years", policy.burn_cover_flag_years, "years"),
    )
