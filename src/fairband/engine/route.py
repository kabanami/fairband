"""Route dispatch: one ``CompanyInputs`` record in, one ``ValuationResult`` out (spec 6.6).

``value_company`` refuses before any arithmetic, in this order: no universe deciles yet (whatever
else assembly found, which the next run with deciles judges); the refusal assembly set; a foreign
filer (spec 11); an unclassified company (the classifier's reason); no positive price; no positive
diluted share count. A Start-up row then takes its route (``route_start_up``, on a
``StartUpContext`` whose trailing figures may be missing), always the refusal "Start-up: no value
by design" with its route ``start-up``, its figures and its inputs. Every other row is refused
without trailing figures; then the phase's route runs (``route_mature_growth``,
``route_mature_stable``, ``route_decline``, and ``route_revenue_growth`` for High Growth and Young
Growth, on the shared ``route_steps``, with the classifier's evidence on the ``Context``) and
refuses on its own guards. Mature Growth: no trailing revenue, no statutory tax rate, the anchor's
refusals (an incomplete NTM consensus, no positive forward anchor, a forward P/E unit error),
consensus earnings that turn negative within the path, a value a share at or below zero under the
reinvestment charge (which keeps the value-side intermediates). Mature Stable: no positive
trailing earnings (which keeps the growth-route cross-check); a value a share plus an agent's
value outside the business at or below zero under the reinvestment charge (which keeps the value
side and the cross-check). On every valued route the value that decides is the sum. Revenue
growth and Decline: the refusals of their module docstrings, in their order. A refusal is a
result with no value and a reason, never an exception.

Overrides (spec 2026-11-06 Tier 2, 10.4; ``method.md`` 14). ``value_company`` takes an agent's
applied overrides by tag, empty for the mechanical method. A ``phase`` override replaces the
classifier's phase right after the classification, its evidence otherwise as it was, so every
guard and the route read the overridden phase: a Start-up row overridden to another phase takes
that phase's route on a ``Context`` and is refused without trailing figures as any such row is,
and a row overridden to Start-up takes the Start-up route. A ``shares.diluted`` override replaces
the reported diluted count before the guard "no diluted share count", so every route reads the
agent's count as ``Context.shares``. The routes read the other inputs through
``route_steps.chosen``; ``value.outside`` each valued route adds to its own value a share, the
result's value the sum, which the levels, the designation and the expected return read, its
intermediates' ``value_per_share`` the route's own, and every solve on the price targeting the
price less it, the business's share of the price (spec 2026-11-09 8). Every result, a refusal
too, cites the JUDGMENT entries of the overrides last (``route_steps.judged_inputs``), in place of
the route's own entries for the inputs they set.

Every result of ``value_company`` cites the policy's version and its settings hash, and is valid
until the next earnings date when that is after the data date, else for the policy's fallback
days. Its flags are the assembly's, the classifier's checks and the route's, the first of each
code kept. Its intermediates hold ``price_facts``, the price columns of spec 6.3, on a refusal
too (``None`` for a row without a price). ``reprice`` moves a result to a new price from its
intermediates alone, its price input with it; a refusal takes only the new price, except a
revenue-growth row whose intermediates hold ``revenue_path`` (refused for its target margin or
its value), whose margin the price needs moves too, a Start-up row, whose market cap moves
with the price and whose requirement and ``below-net-cash`` flag are rebuilt at it, and a Mature
Stable row refused for its trailing earnings or for a value not positive under the reinvestment
charge, whose cross-check's implied growth moves. ``refusal_result`` is the shape of every
refusal.

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
as fractions. Under a ``value.outside`` override a valued route's intermediates, and a refusal's
that keeps the value side, carry ``outside_value_per_share``, the figure a share, which the
rebuilds at the price read; no result without the override carries it. A sensitivity map is
keyed by the runway in years ("5", "10", "20") or by the return of the charge: "runway", the
row's own; the policy's ``roic_sensitivity`` values, "0.15" and "0.09", each as the runway
return; then "ten-year", the ten-year aggregate ROIC as the runway return, ``None`` when it is
unavailable or not positive. The value-spread flag reads the first three, the business's own
values, before any value outside the business is added.

- Mature Growth: ``anchor`` (ntm_eps_raw, sbc_adjustment_per_share, ntm_eps), ``sbc_basis``,
  ``ntm_net_income``, ``path`` (base_year, on_eps, analysts), ``path_steps``, ``belief`` (rate,
  sales_class, median), ``moat``, ``runway``, ``fade_years``, ``growth_rates`` (years 2 to the
  runway), ``roic`` (aggregate, years, by_year), ``runway_return`` (used, marginal,
  marginal_usable, three_year, ten_year, one_year, value), ``terminal_roic``, ``charge_off``,
  ``charge`` (growth_by_year, return_by_year, hold_years, revenue_steps), ``shares``,
  ``value_total``, ``value_per_share``, ``value_by_runway``, ``value_by_roic``, ``nri_gap``,
  ``cycle_gap`` (a share, only under an override of it), ``eps`` (reported, clean, forward: the
  NTM EPS before any cycle gap), ``epv`` (a share), ``dividend_yield``,
  ``net_buyback_yield``, ``income_basis``, ``price_facts``; at the price, ``implied_growth``,
  ``implied_growth_by_runway``, ``implied_by_roic``, ``multiples``, ``growth_share``,
  ``expected_return``.
- Mature Stable: ``e_trailing``, ``nri_gap``, ``cycle_gap`` (as on Mature Growth), ``ttm_margin``,
  ``median_margin``, ``margin_scaled``, ``e_normalized`` (the E the value rests on: scaled when
  flagged, then less any cycle gap), ``moat``, ``roic``, ``runway_return``, ``terminal_roic``,
  ``charge_off``, ``charge`` (as on Mature Growth, with no revenue steps), ``runway``, ``epv``
  and ``stable_growth`` (a share), ``epv_total`` and ``stable_growth_total``, ``shares``,
  ``value_per_share``, ``eps``, ``dividend_yield``, ``net_buyback_yield``, ``income_basis``,
  ``price_facts``, ``growth_route`` (the growth route's cross-check: value_per_share,
  ntm_net_income, path_steps, belief, runway, fade_years, runway_return, terminal_roic,
  charge_off, charge, refusal ``None``; or only its refusal); at the price, ``multiples``,
  ``expected_return`` and the cross-check's ``implied_growth``, rebuilt from its own keys. A row
  refused for its value keeps the value side and the cross-check at the price. A row refused for
  its trailing earnings holds ``e_trailing``, ``nri_gap``, ``cycle_gap`` (under an override),
  ``eps``, ``shares``, ``moat``, ``growth_route`` (with its ``implied_growth`` at the price) and
  ``price_facts``.
- Revenue growth (High Growth and Young Growth): ``ntm_revenue``, ``path`` (base_year, analysts,
  held, sales_class, cap), ``path_steps``, ``revenue_path``, ``growth_rates`` (years 1 to 10),
  ``margin_start``, ``margin_path`` (start, target, by_year, ramp), ``target_margin`` (value,
  count, low, high, largest_symbol, largest_margin, peers, source, industry), ``tax_rate``,
  ``moat``, ``sales_to_capital`` (used, own, own_usable, own_below_bound, peers, value),
  ``revenue_by_year``, ``ebit_by_year``, ``tax_by_year``, ``nopat_by_year``,
  ``reinvestment_by_year``, ``fcff_by_year``, ``terminal_roic``, ``terminal_nopat`` (year 10's
  operating income at the full tax rate), ``terminal_value``,
  ``firm_value``, ``debt``, ``cash``, ``equity``, ``shares``, ``value_per_share``,
  ``value_by_margin`` ("low", "median", "high": the peers' lowest, median and highest margins),
  ``return_on_new_capital``, ``peer_roic_median``, ``failure_probability`` (Young Growth only),
  ``eps``, ``epv``, ``dividend_yield``, ``net_buyback_yield``, ``income_basis``, ``price_facts``,
  ``growth_route`` (the cross-check, as on a Mature Stable row); at the price, ``implied_growth``,
  ``implied_margin``, ``multiples``, ``growth_share``, ``expected_return`` and the cross-check's
  ``implied_growth``. A row refused for its target margin holds only the rebuild keys
  (``revenue_path``, ``margin_start``, ``tax_rate``, ``moat``, ``debt``, ``cash``, ``shares``,
  ``sales_to_capital``), ``implied_margin`` and ``price_facts``.
- Decline: the rebuild keys (``runoff_path``, ``margin``, ``tax_rate``, ``sales_to_capital``,
  ``runoff_recovery``, ``debt``, ``cash``, ``shares``, ``ncav``, ``pi``,
  ``distress_sale_fraction``), ``moat``, ``growth_rates`` (years 1 to 10), the run-off tables
  (``revenue_by_year`` to ``fcff_by_year``, with ``release_by_year``), ``terminal_value``,
  ``firm_value``, ``equity``, ``going_concern_per_share``, ``ncav_per_share``,
  ``floored_per_share``, ``rating``, ``distress_proceeds``, ``distress_per_share``,
  ``value_per_share``, ``altman_z``, ``piotroski_f``, ``capex_vs_depreciation``, ``eps``,
  ``epv``, ``dividend_yield``, ``net_buyback_yield``, ``income_basis``, ``price_facts``; at the
  price, ``implied_decline_rate``, ``multiples`` and ``expected_return``, rebuilt from the
  rebuild keys. A row refused for its value keeps all but the three at the price.
- Start-up (always a refusal): ``requirement`` (reason, revenue_y10, ev_price, revenue_0,
  operating_income_0, target_margin, sales_to_capital, tax_rate, terminal_roic, path,
  terminal_value), ``cash_floor``, ``burn_cover_years``, ``burn``, ``debt``, ``cash``, ``shares``,
  ``market_cap``, ``price_facts``; at the price, ``market_cap`` and ``requirement``, rebuilt from
  the requirement's rebuild keys.
"""

import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, cast

from fairband.engine import METHOD_VERSION
from fairband.engine.anchor import AnnualEstimate, QuarterEstimate, TrailingFigures
from fairband.engine.balance import BalanceYear
from fairband.engine.classifier import Deciles, Series, classify
from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.overrides import Overrides
from fairband.engine.revenue_growth import PeerFigures, PeerSource
from fairband.engine.roic import CapitalYear
from fairband.engine.route_decline import decline_at_price, value_decline
from fairband.engine.route_mature_growth import (
    cross_check_at_price,
    growth_at_price,
    long_runway,
    value_mature_growth,
)
from fairband.engine.route_mature_stable import stable_at_price, value_mature_stable
from fairband.engine.route_revenue_growth import (
    implied_margin_at_price,
    revenue_at_price,
    value_revenue_growth,
)
from fairband.engine.route_start_up import (
    below_net_cash,
    market_cap_at,
    start_up_at_price,
    value_start_up,
)
from fairband.engine.route_steps import (
    Context,
    Refused,
    StartUpContext,
    Valued,
    business_price,
    data,
    judged_inputs,
    price_facts_for,
)
from fairband.engine.types import (
    Flag,
    Phase,
    PhaseEvidence,
    Provenance,
    TaggedInput,
    ValuationResult,
)
from fairband.policy import Policy

FOREIGN_FILER = "foreign filer: currency and share-unit handling not built yet"
_LONG_RUNWAY = "long-runway-high-growth"
_VALUE_SPREAD = "value-spread"
_BELOW_NET_CASH = "below-net-cash"
_BURN_COVER_SHORT = "burn-cover-short"


@dataclass(frozen=True)
class CompanyInputs:
    """Everything the engine reads for one company, as assembly built it from the store.
    ``estimate_methods`` maps an input name to the method assembly estimated it by, and
    ``notes`` an input name to the note assembly wrote for it. ``peers`` are the company's mature
    peers with their figures and ``peer_source`` where they came from, ``debt`` and ``cash`` the
    newest annual balance sheet's (``None`` unknown); the revenue-growth and Decline routes read
    them, and none is stored with a result. ``balance_years`` holds one ``BalanceYear`` per fiscal
    year of ``series`` with an annual balance sheet, oldest first; the Decline route reads them.
    ``adr_ratio`` is GuruFocus's depositary receipt ratio, ordinary shares per ADS, ``None`` for a
    direct listing or without one on file; assembly has read the counts on the quote's basis by it.
    """

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
    peer_source: PeerSource | None = None
    debt: float | None = None
    cash: float | None = None
    balance_years: tuple[BalanceYear, ...] = ()
    adr_ratio: float | None = None


def value_company(
    inputs: CompanyInputs,
    deciles: Deciles | None,
    policy: Policy,
    today: date,
    overrides: Overrides | None = None,
) -> ValuationResult:
    """The company's value by its phase's route, or a refusal with the reason; under
    ``overrides``, the applied overrides by tag, the engine's value with those inputs."""
    assert policy.required_return > policy.terminal_growth, "policy: r must exceed g_t"
    assert min(policy.runway_years.values()) >= 1, "policy: a runway is a year or more"
    judged: Overrides = {} if overrides is None else overrides
    if deciles is None:
        found = Refused("no universe deciles yet")
        return _refuse(inputs, policy, today, found, None, None, judged)
    phase = _phase(classify(inputs.series, deciles), judged)
    refresh_id = deciles.refresh_id

    def refuse(outcome: str | Refused) -> ValuationResult:
        found = Refused(outcome) if isinstance(outcome, str) else outcome
        return _refuse(inputs, policy, today, found, phase, refresh_id, judged)

    if inputs.refusal is not None:
        return refuse(inputs.refusal)
    if inputs.is_adr or inputs.currency != "USD":
        return refuse(FOREIGN_FILER)
    if phase.phase is None:
        return refuse(phase.reason or "unclassified")
    price, shares, trailing = inputs.price, _shares(inputs, judged), inputs.trailing
    if price is None or not _positive(price):
        return refuse("no price")
    if shares is None or not _positive(shares):
        return refuse("no diluted share count")
    if phase.phase == "Start-up":
        start_up = StartUpContext(inputs, trailing, price, shares, policy, today, judged)
        return replace(refuse(value_start_up(start_up)), route="start-up")
    if trailing is None:
        return refuse("no trailing figures")

    c = Context(inputs, trailing, price, shares, policy, today, phase, judged)
    outcome = _route(c, phase.phase)
    if isinstance(outcome, Refused):
        return refuse(outcome)
    return _valued(inputs, phase, price, policy, refresh_id, outcome, judged)


def _shares(i: CompanyInputs, overrides: Overrides) -> float | None:
    """The diluted share count: the override's when ``overrides`` holds one, else the reported
    count (spec 2026-11-09 8)."""
    override = overrides.get("shares.diluted")
    return i.shares_diluted if override is None else cast(float, override.value)


def _phase(found: PhaseEvidence, overrides: Overrides) -> PhaseEvidence:
    """The classifier's evidence, its phase the override's word when ``overrides`` holds one."""
    override = overrides.get("phase")
    if override is None:
        return found
    return replace(found, phase=cast(Phase, override.value))


def _route(c: Context, phase: Phase) -> Valued | Refused:
    """The phase's route: Mature Growth, Mature Stable and Decline their own, High Growth and
    Young Growth the revenue-growth route. A Start-up row never reaches it."""
    if phase == "Mature Growth":
        return value_mature_growth(c)
    if phase == "Mature Stable":
        return value_mature_stable(c)
    if phase == "Decline":
        return value_decline(c)
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
            None, reason, 0, None, None, None, None, None, None, None, None, None, None, None, ()
        )
    return ValuationResult(
        symbol=symbol,
        route=None,
        value=None,
        levels=None,
        price_to_value=None,
        designation=None,
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
        settings_hash=policy.settings_hash,
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
    """The result at a new price: the same value, levels and validity; the designation, the
    price-dependent intermediates and the long-runway flag recomputed from the intermediates.
    A result with no value only takes the new price and date, except that a revenue-growth
    refusal whose intermediates hold ``revenue_path`` also moves its ``implied_margin``, the
    margin the price needs; a Start-up row, whose intermediates hold ``requirement``, moves
    its market cap with the price (``route_start_up.market_cap_at``), rebuilds its requirement at
    it and re-reads its ``below-net-cash`` flag; and a Mature Stable row refused for its trailing
    earnings or for a value not positive under the reinvestment charge, whose intermediates hold
    ``growth_route`` and ``e_trailing``, moves the cross-check's implied growth
    (``cross_check_at_price``; a refused cross-check stays as it is). ``price_facts`` stay as
    they were. Every solve on the price targets the business's share of it, the price less the
    intermediates' ``outside_value_per_share`` (nil without one; ``route_steps.business_price``),
    the rebuilds reading the figure from the intermediates; the designation, the multiples and the
    expected return read the price against the value, the sum.
    Either way the ``price`` input becomes the new quote, so the drawer's arithmetic reproduces:
    its value is ``price`` and its ``as_of`` is ``price_date``; its source stays, and its
    ``observed_at`` and ``entered_at`` become the quote's when given. Every other input stays.

    A price that is not positive and finite raises ``ValueError``: the caller skips such a quote.
    The policy version is not checked: the caller passes the policy the result cites
    (``result.policy_version`` and ``result.settings_hash``), since r, g_t, the runways, the ROIC
    sensitivity and the repricing horizon come from it. The result keeps its own settings hash:
    a reprice does not revalue.
    """
    if not _positive(price):
        raise ValueError(f"price {price} must be positive and finite")
    inputs = tuple(
        _quoted(i, price, price_date, observed_at, entered_at) if i.name == "price" else i
        for i in result.inputs
    )
    if result.value is None or result.levels is None:
        moved = replace(result, price=price, price_date=price_date, inputs=inputs)
        im = result.intermediates
        if "requirement" in im:
            market_cap = market_cap_at(im["market_cap"], result.price, price)
            net_cash = below_net_cash(market_cap, im["debt"], im["cash"])
            return replace(
                moved,
                intermediates=im | start_up_at_price(im, market_cap, policy),
                flags=_swap(result.flags, _BELOW_NET_CASH, net_cash, _BURN_COVER_SHORT),
            )
        if "revenue_path" in im:
            return replace(moved, intermediates=im | implied_margin_at_price(im, price, policy))
        if "growth_route" in im and "e_trailing" in im:
            target = business_price(im, price)
            gr = cross_check_at_price(im["growth_route"], target, im["shares"], policy)
            return replace(moved, intermediates=im | {"growth_route": gr})
        return moved
    im, flags = dict(result.intermediates), result.flags
    if result.route == "mature-growth":
        im |= growth_at_price(im, price, result.value, policy)
        flags = _swap(flags, _LONG_RUNWAY, long_runway(im, policy), _VALUE_SPREAD)
    elif result.route == "revenue-growth":
        im |= revenue_at_price(im, price, result.value, policy)
    elif result.route == "decline":
        im |= decline_at_price(im, price, result.value, policy)
    else:
        im |= stable_at_price(im, price, result.value, policy)
    price_to_value, designation = designation_for(price, result.value, policy.designation_edges)
    return replace(
        result,
        price=price,
        price_date=price_date,
        price_to_value=price_to_value,
        designation=designation,
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
    overrides: Overrides,
) -> ValuationResult:
    price_to_value, designation = designation_for(price, v.value, policy.designation_edges)
    return ValuationResult(
        symbol=i.symbol,
        route=v.route,
        value=v.value,
        levels=levels_for(v.value, v.moat, policy),
        price_to_value=price_to_value,
        designation=designation,
        price=price,
        price_date=i.price_date,
        data_date=i.data_date,
        valid_until=_valid_until(i, policy),
        phase=phase,
        inputs=judged_inputs(_base_inputs(i) + v.inputs, overrides),
        intermediates=v.intermediates,
        flags=_unique(i.input_flags + phase.checks + v.flags),
        refusal=None,
        policy_version=policy.version,
        method_version=METHOD_VERSION,
        settings_hash=policy.settings_hash,
        deciles_refresh_id=refresh_id,
    )


def _refuse(
    i: CompanyInputs,
    policy: Policy,
    today: date,
    found: Refused,
    phase: PhaseEvidence | None,
    refresh_id: int | None,
    overrides: Overrides,
) -> ValuationResult:
    """A refusal from ``value_company``: the company's price when it is one, its price facts
    beside any intermediates the route computed, the base inputs and any the route cites with the
    overrides' JUDGMENT entries, the flags so far and the validity window of every result."""
    price = i.price if i.price is not None and _positive(i.price) else None
    checks = () if phase is None else phase.checks
    result = refusal_result(
        i.symbol,
        found.reason,
        policy,
        i.data_date,
        price=price,
        price_date=None if price is None else i.price_date,
        phase=phase,
        inputs=judged_inputs(_base_inputs(i) + found.inputs, overrides),
        flags=_unique(i.input_flags + checks + found.flags),
        deciles_refresh_id=refresh_id,
        intermediates={
            **found.intermediates,
            "price_facts": price_facts_for(i.closes, price, today),
        },
    )
    return replace(result, valid_until=_valid_until(i, policy))


def _base_inputs(i: CompanyInputs) -> tuple[TaggedInput, ...]:
    """The DATA inputs every result of ``value_company`` carries: what the guards and the
    price facts read, and, for an ADR or a row with a ratio on file, the ADR ratio the share
    count was read by; a direct listing carries none."""
    years = [fy.year for fy in i.series]
    span = f"fiscal {years[0]} to {years[-1]}" if years else None
    earnings = None if i.next_earnings is None else i.next_earnings.isoformat()
    listed = i.is_adr or i.adr_ratio is not None
    return (
        data(i, "statements", float(len(years)), "fiscal years", note=span),
        data(i, "price", i.price, "USD"),
        data(i, "shares_diluted", i.shares_diluted, "shares"),
        data(i, "next_earnings", None, "date", note=earnings),
        data(i, "closes", float(len(i.closes)), "daily closes"),
        *((data(i, "adr_ratio", i.adr_ratio, "ratio"),) if listed else ()),
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


def _swap(flags: tuple[Flag, ...], code: str, new: Flag | None, before: str) -> tuple[Flag, ...]:
    """``flags`` with the flag of ``code`` replaced by ``new`` in its place, just before the flag
    of ``before`` as ``value_company`` orders them (at the end without one), or dropped for
    ``None``: the long-runway flag before the value-spread flag, the net-cash flag before the
    short burn cover."""
    kept = [f for f in flags if f.code != code]
    if new is not None:
        at = next((k for k, f in enumerate(kept) if f.code == before), len(kept))
        kept.insert(at, new)
    return tuple(kept)


def _positive(x: float) -> bool:
    return math.isfinite(x) and x > 0
