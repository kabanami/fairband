"""Route dispatch: one ``CompanyInputs`` record in, one ``ValuationResult`` out (spec 6.6).

``value_company`` refuses before any arithmetic, in this order: no universe deciles yet (whatever
else assembly found, which the next run with deciles judges); the refusal assembly set; a foreign
filer (spec 11); an unclassified company (the classifier's reason); Start-up; a phase without a
route (Decline); no positive price; no positive diluted share count; no trailing figures. Then the
phase's route runs (``route_mature_growth``, ``route_mature_stable``, and
``route_revenue_growth`` for High Growth and Young Growth, on the shared ``route_steps``) and
refuses on its own guards. Mature Growth: no trailing revenue, no statutory tax rate, the anchor's
refusals (an incomplete NTM consensus, no positive forward anchor, a forward P/E unit error),
consensus earnings that turn negative within the path, a value a share at or below zero under the
reinvestment charge (which keeps the value-side intermediates). Mature Stable: no positive
trailing earnings. Revenue growth: the refusals of its module docstring, in its order. A refusal
is a result with no value and a reason, never an exception.

Every result of ``value_company`` is valid until the next earnings date when that is after the
data date, else for the policy's fallback days. Its flags are the assembly's, the classifier's
checks and the route's, the first of each code kept. Its intermediates hold ``price_facts``, the
price columns of spec 6.3, on a refusal too (``None`` for a row without a price). ``reprice``
moves a result to a new price from its intermediates alone, its price input with it; a refusal
takes only the new price, except a revenue-growth row whose intermediates hold ``revenue_path``
(refused for its target margin or its value), whose margin the price needs moves too.
``refusal_result`` is the shape of every refusal.

Tagged inputs. A DATA input cites ``CompanyInputs.provenance`` under one of these keys, which
assembly provides: ``price``, ``market_cap``, ``shares_diluted``, ``statements``,
``estimates_quarter``, ``estimates_annual``, ``street_ttm_eps``, ``moat_score``, ``gf_eps_ttm``,
``gf_eps_without_nri``, ``next_earnings``, ``tax_rate_latest``, ``closes``. A missing key cites
the source "unknown". A DATA input named in ``CompanyInputs.estimate_methods`` is an estimate
under that method (a tax rate carried forward, say), and so are ``aggregate_roic`` and
``runway_return`` under the method ``estimate_methods`` names ``intangibles`` (D17: invested
capital took the issuer's as-reported intangibles total), the first with a note that says so, the
second keeping its note on the measure the charge used; every other DATA input is observed. A
DATA input named in ``CompanyInputs.notes`` carries that note unless the route writes its own
(assembly's note on the tax rate names the country, the rate's year and its source). A RULE input
cites the policy version.

Intermediates hold JSON values only. Totals are in USD, per-share figures in USD a share, rates
as fractions. A sensitivity map is keyed by the runway in years ("5", "10", "20") or by the
return of the charge: "runway", the row's own; the policy's ``roic_sensitivity`` values, "0.15"
and "0.09", each as the runway return; then "ten-year", the ten-year aggregate ROIC as the runway
return, ``None`` when it is unavailable or not positive. The value-spread flag reads the first
three.

- Mature Growth: ``anchor`` (ntm_eps_raw, sbc_adjustment_per_share, ntm_eps), ``sbc_basis``,
  ``ntm_net_income``, ``path`` (base_year, on_eps, analysts), ``path_steps``, ``belief`` (rate,
  sales_class, median), ``moat``, ``runway``, ``fade_years``, ``growth_rates`` (years 2 to the
  runway), ``roic`` (aggregate, years, by_year), ``runway_return`` (used, marginal,
  marginal_usable, three_year, ten_year, value), ``terminal_roic``, ``charge_off``, ``shares``,
  ``value_total``, ``value_per_share``, ``value_by_runway``, ``value_by_roic``, ``nri_gap``,
  ``eps`` (reported, clean, forward), ``epv`` (a share), ``dividend_yield``,
  ``net_buyback_yield``, ``income_basis``, ``price_facts``; at the price, ``implied_growth``,
  ``implied_growth_by_runway``, ``implied_by_roic``, ``multiples``, ``growth_share``,
  ``expected_return``.
- Mature Stable: ``e_trailing``, ``nri_gap``, ``ttm_margin``, ``median_margin``,
  ``margin_scaled``, ``e_normalized``, ``moat``, ``roic``, ``runway_return``, ``terminal_roic``,
  ``runway``, ``epv`` and ``stable_growth`` (a share), ``epv_total`` and ``stable_growth_total``,
  ``shares``,
  ``value_per_share``, ``eps``, ``dividend_yield``, ``net_buyback_yield``, ``income_basis``,
  ``price_facts``, ``growth_route`` (the growth route's cross-check: value_per_share,
  ntm_net_income, path_steps, belief, runway, fade_years, runway_return, terminal_roic,
  charge_off, refusal ``None``; or only its refusal); at the price, ``multiples``,
  ``expected_return`` and the cross-check's ``implied_growth``, rebuilt from its own keys.
- Revenue growth (High Growth and Young Growth): ``ntm_revenue``, ``path`` (base_year, analysts,
  held), ``path_steps``, ``revenue_path``, ``growth_rates`` (years 1 to 10), ``margin_start``,
  ``margin_path`` (start, target, by_year), ``target_margin`` (value, count, low, high,
  largest_symbol, largest_margin, peers), ``tax_rate``, ``moat``, ``sales_to_capital`` (used, own,
  own_usable, peers, value), ``revenue_by_year``, ``ebit_by_year``, ``tax_by_year``,
  ``nopat_by_year``, ``reinvestment_by_year``, ``fcff_by_year``, ``terminal_roic``,
  ``terminal_nopat`` (year 10's operating income at the full tax rate), ``terminal_value``,
  ``firm_value``, ``debt``, ``cash``, ``equity``, ``shares``,
  ``value_per_share``, ``value_by_margin`` ("low", "median", "high": the peers' lowest, median
  and highest margins), ``return_on_new_capital``, ``peer_roic_median``, ``failure_probability``
  (Young Growth only), ``eps``, ``epv``, ``dividend_yield``, ``net_buyback_yield``,
  ``income_basis``, ``price_facts``, ``growth_route`` (the cross-check, as on a Mature Stable
  row); at the price, ``implied_growth``, ``implied_margin``, ``multiples``, ``growth_share``,
  ``expected_return`` and the cross-check's ``implied_growth``. A row refused for its target
  margin holds only the rebuild keys (``revenue_path``, ``margin_start``, ``tax_rate``, ``moat``,
  ``debt``, ``cash``, ``shares``, ``sales_to_capital``), ``implied_margin`` and ``price_facts``.
"""

import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any

from fairband.engine import METHOD_VERSION
from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.classifier import Deciles, Series, classify
from fairband.engine.levels import levels_for, stance3, stance5
from fairband.engine.revenue_growth import PeerFigures
from fairband.engine.roic import CapitalYear
from fairband.engine.route_mature_growth import growth_at_price, long_runway, value_mature_growth
from fairband.engine.route_mature_stable import stable_at_price, value_mature_stable
from fairband.engine.route_revenue_growth import (
    implied_margin_at_price,
    revenue_at_price,
    value_revenue_growth,
)
from fairband.engine.route_steps import Context, Refused, Valued, data, price_facts_for
from fairband.engine.types import (
    Flag,
    Phase,
    PhaseEvidence,
    Provenance,
    TaggedInput,
    ValuationResult,
)
from fairband.policy import Policy

_FOREIGN = "foreign filer: currency and share-unit handling not built yet"
_START_UP = (
    "Start-up: no value by design; the price-implied requirement comes with the Start-up route"
)
_LONG_RUNWAY = "long-runway-high-growth"
_VALUE_SPREAD = "value-spread"
_ROUTED: tuple[Phase, ...] = ("Mature Growth", "Mature Stable", "High Growth", "Young Growth")


@dataclass(frozen=True)
class CompanyInputs:
    """Everything the engine reads for one company, as assembly built it from the store.
    ``estimate_methods`` maps an input name to the method assembly estimated it by, and
    ``notes`` an input name to the note assembly wrote for it. ``peers`` are the company's mature
    peers with their figures, ``debt`` and ``cash`` the newest annual balance sheet's (``None``
    unknown); the revenue-growth route reads them, and none is stored with a result."""

    symbol: str
    name: str
    country: str
    currency: str
    is_adr: bool
    market_cap: float | None
    price: float | None
    price_date: date | None
    shares_diluted: float | None
    series: Series
    capital_years: tuple[CapitalYear, ...]
    tax_rate_latest: float | None
    trailing: TrailingFigures | None
    quarter_estimates: tuple[QuarterEstimate, ...]
    annual_estimates: tuple[AnnualEstimate, ...]
    street_ttm_eps: float | None
    moat_score: float | None
    gf_eps_ttm: float | None
    gf_eps_without_nri: float | None
    next_earnings: date | None
    closes: tuple[tuple[date, float], ...]
    data_date: date
    provenance: dict[str, Provenance]
    input_flags: tuple[Flag, ...]
    refusal: str | None
    estimate_methods: dict[str, str] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    peers: tuple[PeerFigures, ...] = ()
    debt: float | None = None
    cash: float | None = None


def value_company(
    inputs: CompanyInputs, deciles: Deciles | None, policy: Policy, today: date
) -> ValuationResult:
    """The company's value by its phase's route, or a refusal with the reason."""
    assert policy.required_return > policy.terminal_growth, "policy: r must exceed g_t"
    assert min(policy.runway_years.values()) >= 1, "policy: a runway is a year or more"
    if deciles is None:
        return _refuse(inputs, policy, today, "no universe deciles yet", None, None)
    phase = classify(inputs.series, deciles)
    refresh_id = deciles.refresh_id

    def refuse(
        reason: str, flags: tuple[Flag, ...] = (), intermediates: dict[str, Any] | None = None
    ) -> ValuationResult:
        return _refuse(inputs, policy, today, reason, phase, refresh_id, flags, intermediates)

    if inputs.refusal is not None:
        return refuse(inputs.refusal)
    if inputs.is_adr or inputs.currency != "USD":
        return refuse(_FOREIGN)
    if phase.phase is None:
        return refuse(phase.reason or "unclassified")
    if phase.phase == "Start-up":
        return refuse(_START_UP)
    if phase.phase not in _ROUTED:
        return refuse(f"{phase.phase} route not built yet")
    price, shares, trailing = inputs.price, inputs.shares_diluted, inputs.trailing
    if price is None or not _positive(price):
        return refuse("no price")
    if shares is None or not _positive(shares):
        return refuse("no diluted share count")
    if trailing is None:
        return refuse("no trailing figures")

    c = Context(inputs, trailing, price, shares, policy, today)
    outcome = _route(c, phase.phase)
    if isinstance(outcome, Refused):
        return refuse(outcome.reason, outcome.flags, outcome.intermediates)
    return _valued(inputs, phase, price, policy, refresh_id, outcome)


def _route(c: Context, phase: Phase) -> Valued | Refused:
    """The phase's route: Mature Growth and Mature Stable their own, High Growth and Young Growth
    the revenue-growth route."""
    if phase == "Mature Growth":
        return value_mature_growth(c)
    if phase == "Mature Stable":
        return value_mature_stable(c)
    return value_revenue_growth(c, phase)


def refusal_result(
    symbol: str,
    reason: str,
    policy: Policy,
    data_date: date,
    price: float | None = None,
    price_date: date | None = None,
    phase: PhaseEvidence | None = None,
    inputs: tuple[TaggedInput, ...] = (),
    flags: tuple[Flag, ...] = (),
    deciles_refresh_id: int | None = None,
    intermediates: dict[str, Any] | None = None,
) -> ValuationResult:
    """A row with no value and the reason, valid for the policy's fallback days; its
    intermediates are empty unless given."""
    if phase is None:
        phase = PhaseEvidence(
            None, reason, 0, None, None, None, None, None, None, None, None, None, ()
        )
    return ValuationResult(
        symbol=symbol,
        route=None,
        value=None,
        levels=None,
        stance5=None,
        stance3=None,
        price=price,
        price_date=price_date,
        data_date=data_date,
        valid_until=data_date + timedelta(days=policy.validity_fallback_days),
        phase=phase,
        inputs=inputs,
        intermediates={} if intermediates is None else intermediates,
        flags=flags,
        refusal=reason,
        policy_version=policy.version,
        method_version=METHOD_VERSION,
        deciles_refresh_id=deciles_refresh_id,
    )


def reprice(
    result: ValuationResult,
    price: float,
    price_date: date,
    policy: Policy,
    *,
    observed_at: datetime | None = None,
    entered_at: datetime | None = None,
) -> ValuationResult:
    """The result at a new price: the same value, levels and validity; the stance, the
    price-dependent intermediates and the long-runway flag recomputed from the intermediates.
    A result with no value only takes the new price and date, except that a revenue-growth
    refusal whose intermediates hold ``revenue_path`` also moves its ``implied_margin``, the
    margin the price needs; ``price_facts`` stay as they were.
    Either way the ``price`` input becomes the new quote, so the drawer's arithmetic reproduces:
    its value is ``price`` and its ``as_of`` is ``price_date``; its source stays, and its
    ``observed_at`` and ``entered_at`` become the quote's when given. Every other input stays.

    A price that is not positive and finite raises ``ValueError``: the caller skips such a quote.
    The policy version is not checked: the caller passes the policy the result cites
    (``result.policy_version``), since r, g_t, the runways and the ROIC sensitivity come from it.
    """
    if not _positive(price):
        raise ValueError(f"price {price} must be positive and finite")
    inputs = tuple(
        _quoted(i, price, price_date, observed_at, entered_at) if i.name == "price" else i
        for i in result.inputs
    )
    if result.value is None or result.levels is None:
        moved = replace(result, price=price, price_date=price_date, inputs=inputs)
        if "revenue_path" not in result.intermediates:
            return moved
        margin = implied_margin_at_price(result.intermediates, price, policy)
        return replace(moved, intermediates=result.intermediates | margin)
    im, flags = dict(result.intermediates), result.flags
    if result.route == "mature-growth":
        im |= growth_at_price(im, price, result.value, policy)
        flags = _swap_long_runway(flags, long_runway(im, policy))
    elif result.route == "revenue-growth":
        im |= revenue_at_price(im, price, result.value, policy)
    else:
        im |= stable_at_price(im, price, result.value, policy)
    return replace(
        result,
        price=price,
        price_date=price_date,
        stance5=stance5(price, result.levels),
        stance3=stance3(price, result.levels),
        inputs=inputs,
        intermediates=im,
        flags=flags,
    )


def _quoted(
    i: TaggedInput,
    price: float,
    price_date: date,
    observed_at: datetime | None,
    entered_at: datetime | None,
) -> TaggedInput:
    """The price input at a new quote, from the same source."""
    p = i.provenance
    provenance = replace(
        p,
        as_of=price_date,
        observed_at=p.observed_at if observed_at is None else observed_at,
        entered_at=p.entered_at if entered_at is None else entered_at,
    )
    return replace(i, value=price, provenance=provenance)


def _valued(
    i: CompanyInputs,
    phase: PhaseEvidence,
    price: float,
    policy: Policy,
    refresh_id: int | None,
    v: Valued,
) -> ValuationResult:
    levels = levels_for(v.value, v.moat, policy)
    return ValuationResult(
        symbol=i.symbol,
        route=v.route,
        value=v.value,
        levels=levels,
        stance5=stance5(price, levels),
        stance3=stance3(price, levels),
        price=price,
        price_date=i.price_date,
        data_date=i.data_date,
        valid_until=_valid_until(i, policy),
        phase=phase,
        inputs=_base_inputs(i) + v.inputs,
        intermediates=v.intermediates,
        flags=_unique(i.input_flags + phase.checks + v.flags),
        refusal=None,
        policy_version=policy.version,
        method_version=METHOD_VERSION,
        deciles_refresh_id=refresh_id,
    )


def _refuse(
    i: CompanyInputs,
    policy: Policy,
    today: date,
    reason: str,
    phase: PhaseEvidence | None,
    refresh_id: int | None,
    flags: tuple[Flag, ...] = (),
    intermediates: dict[str, Any] | None = None,
) -> ValuationResult:
    """A refusal from ``value_company``: the company's price when it is one, its price facts
    beside any intermediates the route computed, the base inputs, the flags so far and the
    validity window of every result."""
    price = i.price if i.price is not None and _positive(i.price) else None
    checks = () if phase is None else phase.checks
    result = refusal_result(
        i.symbol,
        reason,
        policy,
        i.data_date,
        price=price,
        price_date=None if price is None else i.price_date,
        phase=phase,
        inputs=_base_inputs(i),
        flags=_unique(i.input_flags + checks + flags),
        deciles_refresh_id=refresh_id,
        intermediates={
            **(intermediates or {}),
            "price_facts": price_facts_for(i.closes, price, today),
        },
    )
    return replace(result, valid_until=_valid_until(i, policy))


def _base_inputs(i: CompanyInputs) -> tuple[TaggedInput, ...]:
    """The DATA inputs every result of ``value_company`` carries: what the guards and the
    price facts read."""
    years = [fy.year for fy in i.series]
    span = f"fiscal {years[0]} to {years[-1]}" if years else None
    earnings = None if i.next_earnings is None else i.next_earnings.isoformat()
    return (
        data(i, "statements", float(len(years)), "fiscal years", note=span),
        data(i, "price", i.price, "USD"),
        data(i, "shares_diluted", i.shares_diluted, "shares"),
        data(i, "next_earnings", None, "date", note=earnings),
        data(i, "closes", float(len(i.closes)), "daily closes"),
    )


def _valid_until(i: CompanyInputs, policy: Policy) -> date:
    """The next earnings date when it is after the data date; else the fallback window."""
    if i.next_earnings is not None and i.next_earnings > i.data_date:
        return i.next_earnings
    return i.data_date + timedelta(days=policy.validity_fallback_days)


def _unique(flags: tuple[Flag, ...]) -> tuple[Flag, ...]:
    """The first flag of each code, in order."""
    first: dict[str, Flag] = {}
    for f in flags:
        first.setdefault(f.code, f)
    return tuple(first.values())


def _swap_long_runway(flags: tuple[Flag, ...], new: Flag | None) -> tuple[Flag, ...]:
    """``flags`` with the long-runway flag replaced by ``new`` in its place, just before the
    value-spread flag as ``value_company`` orders them, or dropped for ``None``."""
    kept = [f for f in flags if f.code != _LONG_RUNWAY]
    if new is not None:
        at = next((k for k, f in enumerate(kept) if f.code == _VALUE_SPREAD), len(kept))
        kept.insert(at, new)
    return tuple(kept)


def _positive(x: float) -> bool:
    return math.isfinite(x) and x > 0
