"""Route dispatch: one ``CompanyInputs`` record in, one ``ValuationResult`` out (spec 6.6).

``value_company`` refuses before any arithmetic, in this order: no universe deciles yet (whatever
else assembly found, which the next run with deciles judges); the refusal assembly set, which
holds, in order, no financial statements, a missing statutory tax rate, the currency's refusals
and the listed-share basis's (spec 2026-11-10 7.5); an unclassified company (the classifier's
reason); no positive price; no positive diluted share count. The ADR flag refuses nothing.
The last guard is the moat class (spec 2026-11-19 8.5): a company with no row in the moat table
(``CompanyInputs.moat_class`` ``None``) is refused ``NO_MOAT_CLASS``. A Start-up row meets it
right before its route (``route_start_up``, on a ``StartUpContext`` whose trailing figures may be
missing), always the refusal "Start-up: no value by design" with its route ``start-up``, its
figures and its inputs. Every other row is refused without trailing figures, then meets the
guard; then the phase's route runs (``route_mature_growth``,
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
agent's count as ``Context.consensus_shares``; a ``shares.committed`` override, shares committed
but not yet in that count, adds to it in ``Context.shares``, the count in force (spec 2026-11-14
4). The routes read the other inputs through
``route_steps.chosen``; ``value.outside`` each valued route adds to its own value a share, the
result's value the sum, which the levels, the designation and the expected return read, its
intermediates' ``value_per_share`` the route's own, and every solve on the price targeting the
price less it, the business's share of the price (spec 2026-11-09 8). Every result, a refusal
too, cites the JUDGMENT entries of the overrides last (``route_steps.judged_inputs``), in place of
the route's own entries for the inputs they set. A route reads the moat class through ``chosen``
too, for a sensitivity reading alone (spec 2026-11-19 8.7), whose ``moat.class`` stands in place
of the table's ``moat_class`` entry.

Every result of ``value_company`` cites the policy's version and its settings hash, and is valid
until the next earnings date when that is after the data date, else for the policy's fallback days.
Its flags are the assembly's, ``share-count-gap`` (``flags.share_count_flag``, on the market cap,
the quote's or else the profile's or the screener's, and the quote's price, both USD, and the
diluted count, an agent's ``shares.diluted`` in its place, without the committed shares, which the
market cap cannot hold yet: spec 2026-11-13 8 and 2026-11-14 4), the classifier's checks and the
route's, the first of each code kept;
``reprice`` keeps the share-count warning as it was, its ratio not moving with the price. Its
intermediates hold ``price_facts``, the price columns of spec 6.3, on a refusal too (``None`` for a
row without a price), and ``trailing_end``, the trailing period end as an ISO date, on every result
whose inputs have trailing figures, a refusal too: the period a period-tied override corrects (spec
2026-11-13 11a); and ``margin_history``, the ten-year median operating and net margins with their
counts of years (``flags.margin_history``, spec 2026-11-13 11), on every result whose series is not
empty, a refusal too. ``reprice`` moves a result to a new price from its intermediates alone, its
price input with it; a refusal takes only the new price, except a revenue-growth row whose
intermediates hold ``revenue_path`` (refused for its target margin or its value), whose margin the
price needs moves too, a Start-up row, whose market cap moves with the price and whose requirement
and ``below-net-cash`` flag are rebuilt at it, and a Mature Stable row refused for its trailing
earnings or for a value not positive under the reinvestment charge, whose cross-check's implied
growth moves. ``refusal_result`` is the shape of every refusal.

A company in another currency (spec 2026-11-10 7.2 and 7.3). The route runs in the reporting
currency: its context holds the USD price and market cap × the rate (``CompanyInputs.fx_rate``)
and the policy restated by the inflation differential (``policy.in_currency``), and the sales
class reads the trailing revenue ÷ the rate, its bounds being USD. The value a share and the
levels go back to USD at the rate: the value is the route's ÷ the rate, the levels the policy's
on it, the designation the USD price against it. Such a row's results, a refusal's too, carry
the intermediates ``currency``, ``fx_rate``, ``fx_date`` (ISO) and ``inflation_differential``,
a valued one ``value_in_currency`` (the route's value a share), and the note ``fx-stale``, last,
when assembly read its rate stale. A row refused for its currency's own reason, with no rate
(``CompanyInputs.currency_refused``), carries ``currency`` alone. A USD row carries none of
them, and its figures are as before: its rate is 1 and its differential 0. ``reprice`` moves the
USD value with the rate of a row that carries one (``types.rated``).

Tagged inputs. A DATA input cites ``CompanyInputs.provenance`` under one of these keys, which
assembly provides: ``price``, ``market_cap``, ``shares_diluted``, ``statements``,
``balance_sheet`` (the newest balance sheet, as of its period end), ``estimates_quarter``,
``estimates_annual``, ``street_ttm_eps``, ``next_earnings``, ``tax_rate_latest``, ``closes``,
and on a row in another currency ``fx_rate``;
the RULE input ``inflation_differential`` cites its key too, the inflation table, with its note.
Every result past the guard "no moat class" cites ``moat_class`` right after the inputs every
result carries (``route_steps.moat_input``): the company's row of the moat table, cited to its
key and noted by assembly's note for it (the class word, and the reason after it on a row that
holds one), RULE for the file's row and JUDGMENT for the owner's or an agent's
(``CompanyInputs.moat_judged``); a result refused before the guard cites none.
A missing key cites the source "unknown". A DATA input named in ``CompanyInputs.estimate_methods``
is an estimate under that method (a tax rate carried forward, say), and so are ``aggregate_roic``
and ``runway_return`` under the method ``estimate_methods`` names ``intangibles`` (D17: invested
capital took the issuer's as-reported intangibles total), the first with a note that says so, the
second keeping its note on the measure the charge used; every other DATA input is observed. A
DATA input named in ``CompanyInputs.notes`` carries that note unless the route writes its own
(assembly's note on the tax rate names the country, the rate's year and its source). Every other
RULE input cites the policy version. The price input is the USD quote (unit ``USD``); every other
money input is in the reporting currency, its unit the code or ``<code> a share``
(``route_steps.money`` and ``per_share``), the market cap the one the route read.

Intermediates hold JSON values only. Totals and per-share figures are in the reporting currency
(USD for a USD row), rates as fractions. Under a ``value.outside`` override a valued route's
intermediates, and a refusal's that keeps the value side, carry ``outside_value_per_share``, the
figure a share, which the rebuilds at the price read; no result without the override carries
it. A sensitivity map is keyed by the runway in years ("5", "10", "20") or by the return of the
charge: "runway", the row's own; the policy's ``roic_sensitivity`` values, "0.15" and "0.09",
each as the runway return; then "ten-year", the ten-year aggregate ROIC as the runway return,
``None`` when it is unavailable or not positive. The value-spread flag reads the first three, the
business's own values, before any value outside the business is added.

- Mature Growth: ``anchor`` (ntm_eps_raw, sbc_adjustment_per_share, ntm_eps, source, periods_sum,
  annual: fiscal_year, eps, analysts, year_sum, share and correction, or ``None``), ``sbc_basis``,
  ``ntm_net_income``, ``path`` (base_year, on_eps, analysts), ``path_steps``, ``belief`` (rate,
  sales_class, median), ``moat``, ``runway``, ``fade_years``, ``growth_rates`` (years 2 to the
  runway), ``roic`` (aggregate, years, by_year, each kept year with its
  average_goodwill_and_intangibles), ``runway_return`` (used, marginal, marginal_usable,
  three_year, ten_year, one_year, constant_margin, without_goodwill, value), ``terminal_roic``,
  ``charge_off``,
  ``charge`` (growth_by_year, return_by_year, hold_years, revenue_steps, the steps the charge
  read, an agent's included, revenue_steps_found, the consensus's as found, and
  revenue_step_source, each year's ``consensus``, ``agent``, ``thin`` or ``none``), ``shares`` (the
  count in force, and ``shares_committed`` beside it only under that override, as on every route),
  ``value_total``, ``value_per_share``, ``value_by_runway``, ``value_by_roic``, ``nri_gap`` (an
  agent's non-recurring gap a share, ``None`` without one: the engine finds none),
  ``ntm_nri`` (the one-time amount a share taken off year 1, only under an override of it, nil
  under a guided EPS), ``cycle_gap`` (a share, only under an override of it), ``eps`` (reported,
  clean, forward: the NTM EPS before any one-time amount or cycle gap), ``epv`` (a share),
  ``dividend_yield``, ``net_buyback_yield``, ``income_basis``, ``price_facts``; at the price,
  ``implied_growth``, ``implied_growth_by_runway``, ``implied_by_roic``, ``multiples``,
  ``growth_share``, ``expected_return``.
- Mature Stable: ``e_trailing``, ``nri_gap``, ``cycle_gap`` (as on Mature Growth), ``ttm_margin``,
  ``median_margin``, ``margin_scaled``, ``e_normalized`` (the E the value rests on: scaled when
  flagged, then less any cycle gap), ``moat``, ``roic``, ``runway_return``, ``terminal_roic``,
  ``charge_off``, ``charge`` (as on Mature Growth, with no revenue steps, each year's source
  ``none``), ``runway``, ``epv``
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
  operating income at the full tax rate), ``terminal_value``, ``firm_value``, ``debt``, ``cash``,
  ``minority_interest`` (the minority interest in force, nil when the sheet holds none above
  zero), ``balance_sheet`` (period_end, label, quarterly: the newest balance sheet the three were
  read from; ``None`` without one), ``equity``, ``shares``, ``value_per_share``,
  ``value_by_margin`` ("low", "median", "high": the peers' lowest, median and highest margins),
  ``return_on_new_capital``, ``peer_roic_median``, ``failure_probability`` (Young Growth only),
  ``eps``, ``epv``, ``dividend_yield``, ``net_buyback_yield``, ``income_basis``, ``price_facts``,
  ``growth_route`` (the cross-check, as on a Mature Stable row); at the price, ``implied_growth``,
  ``implied_margin``, ``multiples``, ``growth_share``, ``expected_return`` and the cross-check's
  ``implied_growth``. A row refused for its target margin holds only the rebuild keys
  (``revenue_path``, ``margin_start``, ``tax_rate``, ``moat``, ``debt``, ``cash``,
  ``minority_interest``, ``shares``, ``sales_to_capital``), ``balance_sheet``, ``implied_margin``
  and ``price_facts``.
- Decline: the rebuild keys (``runoff_path``, ``margin``, ``tax_rate``, ``sales_to_capital``,
  ``runoff_recovery``, ``debt``, ``cash``, ``minority_interest`` (as on revenue growth),
  ``shares``, ``ncav``, ``pi``, ``distress_sale_fraction``), ``balance_sheet`` (as on revenue
  growth: the sheet debt, cash, the minority interest and ``ncav`` were read from), ``moat``,
  ``growth_rates`` (years 1 to 10), the run-off tables (``revenue_by_year`` to ``fcff_by_year``,
  with ``release_by_year``), ``terminal_value``, ``firm_value``, ``equity``,
  ``going_concern_per_share``, ``ncav_per_share``, ``floored_per_share``, ``rating``,
  ``distress_proceeds``, ``distress_per_share``, ``value_per_share``, ``altman_z``,
  ``piotroski_f``, ``capex_vs_depreciation``, ``eps``, ``epv``, ``dividend_yield``,
  ``net_buyback_yield``, ``income_basis``, ``price_facts``; at the price,
  ``implied_decline_rate``, ``multiples`` and ``expected_return``, rebuilt from the rebuild keys.
  A row refused for its value keeps all but the three at the price.
- Start-up (always a refusal): ``requirement`` (reason, revenue_y10, ev_price, revenue_0,
  operating_income_0, target_margin, sales_to_capital, tax_rate, terminal_roic, path,
  terminal_value), ``cash_floor``, ``burn_cover_years``, ``burn``, ``debt``, ``cash``,
  ``minority_interest`` and ``balance_sheet`` (as on revenue growth), ``shares``, ``market_cap``,
  ``price_facts``; at the price, ``market_cap`` and ``requirement``, rebuilt from the
  requirement's rebuild keys with ``debt``, ``cash`` and ``minority_interest``.
"""

import math
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Any, cast

from fairband.engine import METHOD_VERSION
from fairband.engine.anchor import (
    AnnualEstimate,
    QuarterEstimate,
    StockPayHistory,
    TrailingFigures,
)
from fairband.engine.balance import BalanceYear, NewestSheet
from fairband.engine.classifier import Deciles, Series, classify
from fairband.engine.designation import designation_for
from fairband.engine.flags import margin_history, share_count_flag
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
    moat_input,
    price_facts_for,
    rule,
)
from fairband.engine.types import (
    Flag,
    Phase,
    PhaseEvidence,
    Provenance,
    TaggedInput,
    ValuationResult,
    money_of,
    rated,
)
from fairband.policy import Moat, Policy, in_currency

# The refusal of a company the moat table holds no row for (spec 2026-11-19 8.5): one that entered
# the universe after the file was cut. The owner's class, an agent's or the file's next version
# lifts it.
NO_MOAT_CLASS = "no moat class"
_LONG_RUNWAY = "long-runway-high-growth"
_VALUE_SPREAD = "value-spread"
_BELOW_NET_CASH = "below-net-cash"
_BURN_COVER_SHORT = "burn-cover-short"
_FX_STALE = "fx-stale"
_UNKNOWN = Provenance("unknown", None, None, None)
_PAIR_QUOTE = "FMP quote"  # the source of a pair's quote, named with the pair as assembly names it


@dataclass(frozen=True)
class CompanyInputs:
    """Everything the engine reads for one company, as assembly built it from the store.
    ``estimate_methods`` maps an input name to the method assembly estimated it by, and
    ``notes`` an input name to the note assembly wrote for it. ``peers`` are the company's mature
    peers with their figures and ``peer_source`` where they came from, ``debt`` and ``cash`` the
    newest balance sheet's (``None`` unknown); the revenue-growth and Decline routes read them,
    and none is stored with a result. ``sheet`` is that newest balance sheet on file, a fiscal
    year's or a quarter's (``NewestSheet``, spec 2026-11-13 12.2), ``None`` without one.
    ``balance_years`` holds one ``BalanceYear`` per fiscal year of ``series`` with an annual
    balance sheet, oldest first; the Decline route reads them.
    ``adr_ratio`` is the ratio assembly found from the share counts of a row with the ADR flag
    (method 4.2), a whole number, ``None`` where the counts agree and on every other row; assembly
    has read the counts on the quote's basis by it.
    ``stock_pay`` is the stock pay on file beside the trailing figure, the trailing periods at zero
    and the newest fiscal year above zero (``StockPayHistory``), ``None`` without statements; the
    Mature Growth route's ``stock-pay-missing`` note reads it.
    ``moat_class`` is the company's class in the moat table, ``None`` where the table holds no row
    for it (spec 2026-11-19 8.5), and ``moat_judged`` whether the row is the owner's or an agent's
    rather than the file's; ``provenance`` and ``notes`` hold the row's citation and note under
    ``moat_class``.

    A company in another currency (spec 2026-11-10 section 7): ``currency`` is the reporting
    currency, every money figure but ``price`` and ``market_cap`` (the quote's, in USD) and the
    peers' market caps is in it, the street actuals translated by assembly.
    ``fx_rate`` is the currency's units per USD at the price date, read from the close of
    ``fx_date``, ``fx_stale`` when that close is older than the policy's stale bound, and
    ``inflation_differential`` the currency's d against USD. A USD row keeps the defaults: the
    rate 1, no rate date, d 0. ``currency_refused`` marks a row whose refusal is its currency's
    own (no exchange rate, no inflation projection, inflation above the bound): its code known
    from the statements and no rate read, so it keeps the defaults too, and its results name the
    code alone. A row refused before the currency's step (its statements, its tax rate) or whose
    currency is unknown is not so marked.
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
    moat_class: Moat | None
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
    sheet: NewestSheet | None = None
    balance_years: tuple[BalanceYear, ...] = ()
    adr_ratio: float | None = None
    fx_rate: float = 1.0
    fx_date: date | None = None
    inflation_differential: float = 0.0
    fx_stale: bool = False
    currency_refused: bool = False
    stock_pay: StockPayHistory | None = None
    moat_judged: bool = False


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

    def refuse(outcome: str | Refused, moat: TaggedInput | None = None) -> ValuationResult:
        found = Refused(outcome) if isinstance(outcome, str) else outcome
        return _refuse(inputs, policy, today, found, phase, refresh_id, judged, moat)

    if inputs.refusal is not None:
        return refuse(inputs.refusal)
    if phase.phase is None:
        return refuse(phase.reason or "unclassified")
    price, trailing = inputs.price, inputs.trailing
    shares, consensus = _shares(inputs, judged)
    if price is None or not _positive(price):
        return refuse("no price")
    if consensus is None or shares is None or not _positive(consensus):
        return refuse("no diluted share count")
    # the route runs in the reporting currency, on the policy's rates restated into it
    local, rate = in_currency(policy, inputs.inflation_differential), inputs.fx_rate
    in_local = replace(inputs, price=price * rate, market_cap=_times(inputs.market_cap, rate))
    if phase.phase == "Start-up":
        if inputs.moat_class is None:
            return refuse(NO_MOAT_CLASS)
        start_up = StartUpContext(
            in_local, trailing, price * rate, shares, consensus, local, today, judged
        )
        return replace(refuse(value_start_up(start_up), moat_input(inputs)), route="start-up")
    if trailing is None:
        return refuse("no trailing figures")
    if inputs.moat_class is None:
        return refuse(NO_MOAT_CLASS)

    c = Context(in_local, trailing, price * rate, shares, consensus, local, today, phase, judged)
    outcome = _route(c, phase.phase)
    if isinstance(outcome, Refused):
        return refuse(outcome, moat_input(inputs))
    return _valued(inputs, phase, price, policy, refresh_id, outcome, judged, moat_input(inputs))


def _shares(i: CompanyInputs, overrides: Overrides) -> tuple[float | None, float | None]:
    """The count in force and the diluted count (spec 2026-11-14 4). The diluted count is the
    ``shares.diluted`` override's when ``overrides`` holds one, else the reported count (spec
    2026-11-09 8); the count in force is it plus the ``shares.committed`` override's when
    ``overrides`` holds one, which is above 0. Both are ``None`` without a diluted count, so the
    guard refuses as before."""
    override = overrides.get("shares.diluted")
    diluted = i.shares_diluted if override is None else cast(float, override.value)
    if diluted is None:
        return None, None
    committed = overrides.get("shares.committed")
    return diluted + (0.0 if committed is None else cast(float, committed.value)), diluted


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
    fx_rate: float | None = None,
    fx_date: date | None = None,
    fx_observed_at: datetime | None = None,
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
    (``cross_check_at_price``; a refused cross-check stays as it is). ``price_facts``,
    ``trailing_end`` and ``margin_history`` stay as they were. Every solve on the price targets the
    business's share of it, the price less the intermediates' ``outside_value_per_share`` (nil
    without one; ``route_steps.business_price``), the rebuilds reading the figure from the
    intermediates; the designation, the multiples and the expected return read the price against
    the value, the sum.
    Either way the ``price`` input becomes the new quote, so the drawer's arithmetic reproduces:
    its value is ``price`` and its ``as_of`` is ``price_date``; its source stays, and its
    ``observed_at`` and ``entered_at`` become the quote's when given. Every other input stays.

    A row in another currency (``types.money_of``; spec 2026-11-10 7.2) reprices
    at ``fx_rate``, the pair's quote of ``fx_date``, when given, else at the rate it holds: the
    new USD price comes into the currency at that rate, everything above moves on the price in
    the currency, the value in the currency and the policy restated by the row's differential,
    and the value a share is ``value_in_currency`` ÷ the rate, its levels the policy's on it; the
    designation reads the two USD figures. The intermediates' ``fx_rate`` and ``fx_date`` and the
    ``fx_rate`` input take the rate given, the input as the price input moves: its value, its
    ``as_of`` the quote's date and its ``observed_at`` ``fx_observed_at`` when given, and its
    source the pair's quote, ``FMP quote USD<code>``. ``fx-stale``
    is on the row when its rate's date is more than ``fx_stale_days`` before ``price_date``, and
    off otherwise. A row that carries no rate (``types.rated``) reads none: a USD row, whose rate
    is 1 on every day, and a row refused for its currency's own reason, which names the code
    alone; ``fx_rate`` moves nothing on either.

    A price or a rate that is not positive and finite raises ``ValueError``: the caller skips
    such a quote. The policy version is not checked: the caller passes the policy the result
    cites (``result.policy_version`` and ``result.settings_hash``), since r, g_t, the runways, the
    ROIC sensitivity and the repricing horizon come from it. The result keeps its own settings
    hash: a reprice does not revalue.
    """
    if not _positive(price):
        raise ValueError(f"price {price} must be positive and finite")
    im = result.intermediates
    held, currency = money_of(result)
    foreign = rated(result)  # a row with no rate, USD or refused for its currency, reads none
    if foreign and fx_rate is not None and not _positive(fx_rate):
        raise ValueError(f"rate {fx_rate} must be positive and finite")
    rate: float = 1.0
    local, flags = policy, result.flags
    stale: tuple[Flag, ...] = ()
    inputs = tuple(
        _quoted(i, price, price_date, observed_at, entered_at) if i.name == "price" else i
        for i in result.inputs
    )
    if foreign:
        rate = held if fx_rate is None else fx_rate
        when = _stored_date(im) if fx_date is None else fx_date
        local = in_currency(policy, im["inflation_differential"])
        im = im | {"fx_rate": rate, "fx_date": None if when is None else when.isoformat()}
        if fx_rate is not None:
            inputs = tuple(
                _rated(i, rate, when, fx_observed_at, currency) if i.name == "fx_rate" else i
                for i in inputs
            )
        flags = tuple(f for f in flags if f.code != _FX_STALE)
        if when is not None and (price_date - when).days > policy.fx_stale_days:
            stale = (_fx_stale(currency, when, price_date),)
    in_local = price * rate
    if result.value is None or result.levels is None:
        moved = replace(
            result,
            price=price,
            price_date=price_date,
            inputs=inputs,
            intermediates=im,
            flags=flags + stale,
        )
        if "requirement" in im:
            was = _times(result.price, held)
            market_cap = market_cap_at(im["market_cap"], was, in_local)
            held = im.get("minority_interest", 0.0)  # nil on a row stored before method 1.4
            net_cash = below_net_cash(market_cap, im["debt"], im["cash"], held)
            return replace(
                moved,
                intermediates=im | start_up_at_price(im, market_cap, local),
                flags=_swap(flags, _BELOW_NET_CASH, net_cash, _BURN_COVER_SHORT) + stale,
            )
        if "revenue_path" in im:
            return replace(moved, intermediates=im | implied_margin_at_price(im, in_local, local))
        if "growth_route" in im and "e_trailing" in im:
            target = business_price(im, in_local)
            gr = cross_check_at_price(im["growth_route"], target, im["shares"], local)
            return replace(moved, intermediates=im | {"growth_route": gr})
        return moved
    value, levels = result.value, result.levels
    in_currency_value = value
    if foreign:
        in_currency_value = im["value_in_currency"]
        value = in_currency_value / rate
        levels = levels_for(value, im["moat"], policy)
    im = dict(im)
    if result.route == "mature-growth":
        im |= growth_at_price(im, in_local, in_currency_value, local)
        flags = _swap(flags, _LONG_RUNWAY, long_runway(im, local), _VALUE_SPREAD)
    elif result.route == "revenue-growth":
        im |= revenue_at_price(im, in_local, in_currency_value, local)
    elif result.route == "decline":
        im |= decline_at_price(im, in_local, in_currency_value, local)
    else:
        im |= stable_at_price(im, in_local, in_currency_value, local)
    # the row's own edges: the first is its moat class's buy level (spec 2026-11-23 thresholds 5.2)
    price_to_value, designation = designation_for(price, value, policy.edges_for(im["moat"]))
    return replace(
        result,
        value=value,
        levels=levels,
        price=price,
        price_date=price_date,
        price_to_value=price_to_value,
        designation=designation,
        inputs=inputs,
        intermediates=im,
        flags=flags + stale,
    )


def _stored_date(im: dict[str, Any]) -> date | None:
    """The date of the rate a row in another currency was valued or last repriced at."""
    stored = im.get("fx_date")
    return None if stored is None else date.fromisoformat(stored)


def _rated(
    i: TaggedInput, rate: float, when: date | None, observed_at: datetime | None, currency: str
) -> TaggedInput:
    """The ``fx_rate`` input at the pair's quote ``rate`` of ``when``, cited to the quote, FMP's
    ``quote`` of the pair ``USD<code>``, observed when the quote was (as it was without a
    stamp)."""
    p = i.provenance
    stamp = p.observed_at if observed_at is None else observed_at
    source = f"{_PAIR_QUOTE} USD{currency}"
    provenance = replace(p, source=source, as_of=when, observed_at=stamp)
    return replace(i, value=rate, provenance=provenance)


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
    moat: TaggedInput,
) -> ValuationResult:
    """The valued result: the route's value a share and its levels translated to USD at the rate
    (a USD row's rate is 1), the levels the policy's on the USD value, the designation the USD
    price against it (spec 2026-11-10 7.2); its inputs the base inputs, then ``moat``, the moat
    class's entry, then the route's."""
    value = v.value / i.fx_rate
    price_to_value, designation = designation_for(price, value, policy.edges_for(v.moat))
    return ValuationResult(
        symbol=i.symbol,
        route=v.route,
        value=value,
        levels=levels_for(value, v.moat, policy),
        price_to_value=price_to_value,
        designation=designation,
        price=price,
        price_date=i.price_date,
        data_date=i.data_date,
        valid_until=_valid_until(i, policy),
        phase=phase,
        inputs=judged_inputs(_base_inputs(i, policy) + (moat,) + v.inputs, overrides, i.currency),
        intermediates=v.intermediates
        | _currency_entry(i, v.value)
        | _trailing_entry(i)
        | _margin_entry(i),
        flags=_unique(
            i.input_flags
            + _share_count(i, overrides, policy)
            + phase.checks
            + v.flags
            + _stale_flag(i)
        ),
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
    moat: TaggedInput | None = None,
) -> ValuationResult:
    """A refusal from ``value_company``: the company's price when it is one, its price facts
    beside any intermediates the route computed, the base inputs, then ``moat``, the moat class's
    entry on a refusal past its guard (none before it), then any the route cites, with the
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
        inputs=judged_inputs(
            _base_inputs(i, policy) + ((moat,) if moat is not None else ()) + found.inputs,
            overrides,
            i.currency,
        ),
        flags=_unique(
            i.input_flags
            + _share_count(i, overrides, policy)
            + checks
            + found.flags
            + _stale_flag(i)
        ),
        deciles_refresh_id=refresh_id,
        intermediates={
            **found.intermediates,
            "price_facts": price_facts_for(i.closes, price, today),
            **_currency_entry(i, None),
            **_trailing_entry(i),
            **_margin_entry(i),
        },
    )
    return replace(result, valid_until=_valid_until(i, policy))


def _base_inputs(i: CompanyInputs, policy: Policy) -> tuple[TaggedInput, ...]:
    """The inputs every result of ``value_company`` carries: the DATA inputs the guards and the
    price facts read (the price the USD quote); for a row assembly found an ADR ratio on, the ratio
    the share count was read by, every other row carrying none; and for a row in another
    currency at a rate, the rate (``<code> per USD``) and the inflation differential, a RULE input
    cited to the inflation table with its note (spec 2026-11-10 7.2 and 7.3). A USD row carries
    neither."""
    years = [fy.year for fy in i.series]
    span = f"fiscal {years[0]} to {years[-1]}" if years else None
    earnings = None if i.next_earnings is None else i.next_earnings.isoformat()
    currency = (
        (
            data(i, "fx_rate", i.fx_rate, f"{i.currency} per USD"),
            replace(
                rule(policy, "inflation_differential", i.inflation_differential, "ratio"),
                provenance=i.provenance.get("inflation_differential", _UNKNOWN),
                note=i.notes.get("inflation_differential"),
            ),
        )
        if _foreign(i)
        else ()
    )
    return (
        data(i, "statements", float(len(years)), "fiscal years", note=span),
        data(i, "price", i.price, "USD"),
        data(i, "shares_diluted", i.shares_diluted, "shares"),
        data(i, "next_earnings", None, "date", note=earnings),
        data(i, "closes", float(len(i.closes)), "daily closes"),
        *((data(i, "adr_ratio", i.adr_ratio, "ratio"),) if i.adr_ratio is not None else ()),
        *currency,
    )


def _foreign(i: CompanyInputs) -> bool:
    """Whether ``i`` reports in another currency than USD at a rate assembly read: its results
    carry the currency's intermediates and inputs, and ``fx-stale`` when the rate is stale."""
    return i.currency != "USD" and i.fx_date is not None


def _currency_entry(i: CompanyInputs, value: float | None) -> dict[str, Any]:
    """The intermediates of a row in another currency (spec 2026-11-10 7.2): the currency, the
    rate and its date, the differential and, on a valued row, ``value_in_currency``, the route's
    value a share before translation; on a row refused for its currency's own reason, the code
    alone, its figures being in it with no rate to read (the ruling of task 6's fix round 1);
    none for a USD row, whose intermediates stay as they were. Assembly reads the currency on
    every row, so a row refused before the currency's step (its statements, its tax rate) in
    another currency with a rate on file carries the entry as a refusal does, and one whose
    currency has no rate, no projection or inflation above the bound carries none, the earlier
    refusal being its own."""
    if not _foreign(i):
        return {"currency": i.currency} if i.currency_refused and i.currency != "USD" else {}
    entry: dict[str, Any] = {
        "currency": i.currency,
        "fx_rate": i.fx_rate,
        "fx_date": None if i.fx_date is None else i.fx_date.isoformat(),
        "inflation_differential": i.inflation_differential,
    }
    return entry if value is None else entry | {"value_in_currency": value}


def _trailing_entry(i: CompanyInputs) -> dict[str, Any]:
    """``trailing_end``, the trailing period end as an ISO date, the period a period-tied
    override corrects (spec 2026-11-13 11a); none for a row with no trailing figures."""
    return {} if i.trailing is None else {"trailing_end": i.trailing.period_end.isoformat()}


def _margin_entry(i: CompanyInputs) -> dict[str, Any]:
    """``margin_history``, the ten-year median operating and net margins with their counts of
    years (``flags.margin_history``, spec 2026-11-13 11), which the research agent reads for a
    cyclical company; none for a row whose series is empty."""
    return {"margin_history": margin_history(i.series)} if i.series else {}


def _share_count(i: CompanyInputs, overrides: Overrides, policy: Policy) -> tuple[Flag, ...]:
    """``share-count-gap`` on the market cap, the quote's or else the profile's or the screener's,
    and the quote's price, both in US dollars, and the diluted count: an agent's
    ``shares.diluted``, else the count assembly read after the split rule and the ADR basis rule
    (spec 2026-11-13 8). It leaves out an agent's committed shares, since the market cap holds no
    share not yet issued (spec 2026-11-14 4)."""
    found = share_count_flag(i.market_cap, i.price, _shares(i, overrides)[1], policy)
    return () if found is None else (found,)


def _stale_flag(i: CompanyInputs) -> tuple[Flag, ...]:
    """``fx-stale`` for a row in another currency whose rate assembly read stale."""
    if not _foreign(i) or not i.fx_stale or i.fx_date is None or i.price_date is None:
        return ()
    return (_fx_stale(i.currency, i.fx_date, i.price_date),)


def _fx_stale(currency: str, fx_date: date, price_date: date) -> Flag:
    """The ``fx-stale`` note: the rate's close and the price date, and the days between."""
    days = (price_date - fx_date).days
    return Flag(
        _FX_STALE,
        "Rate stale",
        f"The newest close of USD{currency} on file is of {fx_date.isoformat()}, {days} days "
        f"before the price date {price_date.isoformat()}.",
    )


def _times(x: float | None, k: float) -> float | None:
    return None if x is None else x * k


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
