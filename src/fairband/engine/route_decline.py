"""The Decline route: Damodaran's run-off (spec 2026-11-03 section 10, spec 2026-11-06 section 6),
on the core of ``runoff`` and the measures of ``distress``.

What it reads. Year 0 is trailing revenue. Years 1 to 3 are the revenue-growth route's consensus
path, uncapped (``route_revenue_growth.ntm_revenue`` and ``revenue_path_for``): year 1 the NTM
consensus revenue, years 2 and 3 the annual consensus steps from the base year, a missing step
holding the rate of the year before and a thin landing year flagged. Past year 3 the path reads
the annual consensus revenue one fiscal year at a time (``route_revenue_growth.consensus_beyond``)
while a year has a revenue mean above zero and at least ``analyst_min`` revenue analysts, to year
K, at most ``runoff_years``; the first year that fails either test ends it at the year before,
with no refusal and no flag: nothing is held past year 3 and a thin year is not read.
From year K + 1 the decline rate d fades in a straight line to zero by year ``runoff_years``.
Without a usable NTM consensus (no NTM window, the revenue-growth route's: four consecutive
quarters, or two half-years for a half-yearly reporter; a period without a revenue mean; or a sum
at or below zero) the row is not refused: years 1 to 3 shrink at d, the years past 3 are not read,
and the fade runs from year 4. d is the classifier's five-year revenue slope
(``PhaseEvidence.revenue_slope``, which ``Context.evidence`` carries) over the last fiscal year's
revenue, at most zero and floored at ``runoff.DECLINE_FLOOR``, −50%. The terminal is flat on year
N's revenue (``runoff.runoff_valuation``). One operating margin is held in every year and in the
terminal, the normalized margin: the median of the operating margins of the last five fiscal years
that have one when at least three do, else the trailing margin. Tax is the newest fiscal year's
statutory rate after the forecast's own losses. Sales-to-capital is the company's own newest kept
ROIC year's revenue over its average invested capital, else the mature peers' median.

The value. ``runoff.runoff_valuation`` gives the firm value and ``runoff.runoff_equity`` the value
a share: the going-concern value from debt and cash of the newest balance sheet
(``CompanyInputs.sheet``, a quarter's or a fiscal year's; each nil when unknown), floored by the
net current asset value of the same sheet (none when it lacks total liabilities or no sheet is on
file), weighted against the distress-sale value at π, the ten-year probability of default of the
synthetic rating (``distress.rate``) on EBIT_n, trailing revenue times the normalized margin, over
the trailing interest expense: 0 with no net debt; unavailable with no debt line on file (both
debt lines missing: unknown debt is not "no net debt"), or with net debt and no interest expense
on file, when the floored value stands. The same sheet's minority interest at book
(``route_steps.minority``: nil when not presented or at or below zero; spec 2026-11-13 13) comes
off the going-concern value, the floor and the distress-sale value, the common owners' claims;
the rating reads debt and cash alone, and ``ncav`` and ``distress_proceeds`` are recorded before
it comes off.

Refusals, in this order, after the shared guards: no trailing revenue (missing or not positive);
no trailing operating income; no statutory tax rate; consensus revenue that falls to zero or below
within the path (g_2 or g_3 as resolved at or below −100%; no step past year 3 can be), with the
path's flags; no sales-to-capital, with the path's and the balance sheet's flags; a value a share
at or below zero after the weighting, "value not positive in the run-off", which keeps every
value-side intermediate, every flag and the route's inputs.

Intermediates: the rebuild keys below; ``moat``; ``growth_rates`` for years 1 to N; the tables
``revenue_by_year``, ``ebit_by_year``, ``tax_by_year``, ``nopat_by_year``, ``reinvestment_by_year``,
``release_by_year``, ``fcff_by_year``; ``terminal_value``, ``firm_value``, ``equity`` (the
going-concern equity, less the minority interest), ``going_concern_per_share``, ``ncav_per_share``
(NCAV less the minority interest, a share), ``floored_per_share``;
``rating`` (rating, ebit, interest, coverage, pi, row, the coverage range of the table's row as
coverage_from and coverage_below, ``None`` at an open end; note, "no net debt", "no debt line on
file" or "no interest expense on file"); ``distress_proceeds``, ``distress_per_share``,
``value_per_share``; ``altman_z`` (year, x1 to x4, score, zone; ``None`` without a score) and
``piotroski_f`` (year, prior_year, the nine signals by name with their values, score, read;
``None`` with fewer than two balance sheets); ``capex_vs_depreciation``; ``eps`` (no forward
EPS), ``epv``, ``dividend_yield``, ``net_buyback_yield``, ``income_basis``, ``price_facts``; at
the price, ``implied_decline_rate``, ``multiples`` and ``expected_return``, its growth term the
path's own rates for years 2 to H + 1, H the policy's repricing horizon, and zero past year N.

The rebuild keys: ``runoff_path`` (revenue0, ntm_revenue, ``None`` without a usable consensus, the
consensus steps for years 2 to K as found with ``None`` for a held one in years 2 and 3,
consensus_years K, d, runoff_years); ``margin`` (value, used, "median" or "trailing", median,
trailing, the fiscal years and margins read); ``tax_rate``; ``sales_to_capital`` (used,
"own-latest" or "peers", value); ``runoff_recovery``; ``debt``; ``cash``; ``minority_interest``
(the figure in force; nil on a row stored before method 1.4 carried it); ``shares``; ``ncav``;
``pi`` (value, rating, coverage); ``distress_sale_fraction``. With the policy's r they rebuild the
value at any decline rate, so ``decline_at_price`` moves a stored row to a new price from its
intermediates alone. Beside them ``balance_sheet``, the period of the newest balance sheet that
debt, cash, the minority interest and NCAV were read from (``route_steps.sheet_entry``), which
rebuilds nothing. The implied decline rate is the first root the scan from −50% to 0 finds
(``runoff.implied_decline_rate``), the consensus years as found and the fade from each trial d;
the value need not rise with d.

Flags, in order: ``path-held``, ``decline-rate-floored``, ``path-on-trend``,
``consensus-recovery`` naming each consensus year 1 to K that grows, ``few-analysts`` on years 2
and 3 only; ``line-not-presented:debt`` and ``:cash``, then ``sheet-shift`` when the newest sheet
is a quarter's whose debt, cash or minority interest shifted against the newest annual sheet's
(``route_revenue_growth.bridge_flags``), then ``line-not-presented:totalLiabilities``;
``peers-from-industry`` when the industry's peers gave the sales-to-capital;
``tax-loss-history-unknown``; ``ncav-floor`` when the floor binds and π is not 1 (at π = 1 the
floor has no weight); ``distress-not-charged``; ``z-distress``; ``f-score-low``;
``reinvesting-in-decline``; the trailing flags. Never the ROIC flags. ``path-on-trend`` and
``consensus-recovery`` name the decline rate d as used, so a floored row names −50%, not the
trend's own figure.

Overrides (``method.md`` 14) through ``route_steps.chosen``. ``decline.rate`` replaces d, never
floored (``decline-rate-floored`` is not raised); ``revenue.ntm``, the NTM revenue from a clear
guidance, the sum of the NTM window's revenue means, which year 1, the rebuild key and
``consensus-recovery`` then read, so a guided figure makes usable a consensus whose sum is at or
below zero; it is not read without the window or with a period lacking its mean, and the
``ntm_revenue`` data entry cites the consensus as found; ``path.step_2`` and ``path.step_3`` the
consensus steps as the revenue-growth route reads them (``revenue_path_for``), not read on a row
without a usable consensus, whose years 1 to 3 shrink at d; ``capital.sales_to_capital`` the
measure (``used`` "override", so the peers raise no flag and cite no rule); ``balance.debt`` and
``balance.cash`` the balance sheet's figures before they count as nil, the rating read on a
replaced debt figure; ``balance.minority`` the sheet's minority interest
(``route_steps.minority``), which the rating does not read. A row a ``phase`` override puts in
Decline without a revenue trend or a positive last revenue, and no ``decline.rate`` override, is
refused "no revenue trend".

``value.outside``, the value outside the business a share (``route_steps.outside_value``), comes
after the weighting: the result's value is the route's value a share plus the figure, which the
levels and the designation read; ``value_per_share`` and its parts stay the business's, and
``outside_value_per_share`` carries the figure under the override only. A sum at or below zero
refuses "value not positive in the run-off", which keeps the figure beside the value side.
``decline_at_price`` reads the price and the sum: the multiples and the expected return read them
as they are, and the implied decline rate solves to the price less the figure, the business's
share of the price. The diluted share count is ``Context.shares`` and the rebuild key
``shares``, an agent's ``shares.diluted`` in place of the reported count, which every value a
share divides by.
"""

import math
import statistics
from dataclasses import asdict, dataclass
from typing import Any, Literal

from fairband.engine.anchor import TrailingFigures, base_fiscal_year, moat_class, ntm_window
from fairband.engine.balance import BalanceYear, NewestSheet
from fairband.engine.classifier import Series, operating_margin
from fairband.engine.distress import FScore, Rating, ZScore, altman_z, ncav, piotroski_f, rate
from fairband.engine.flags import millions
from fairband.engine.multiples import epv
from fairband.engine.revenue_growth import (
    newest_sales_to_capital,
    peer_sales_to_capital,
    resolved_steps,
)
from fairband.engine.route_revenue_growth import (
    TAX_LOSS,
    bridge_flags,
    consensus_beyond,
    from_industry,
    from_peers,
    industry_peer_max_input,
    judged_steps,
    ntm_revenue,
    peer_industry,
    revenue_path_for,
    step_input,
)
from fairband.engine.route_steps import (
    Context,
    Refused,
    RoicTerms,
    Valued,
    business_price,
    chosen,
    common_inputs,
    data,
    debt_and_cash,
    eps,
    expected,
    from_capital,
    income,
    minority,
    minority_input,
    money,
    multiples_at,
    nil,
    nri_gap,
    outside_entry,
    outside_value,
    present,
    price_facts_for,
    rule,
    sheet_entry,
    sheet_note,
    signed,
    trailing_flags,
)
from fairband.engine.runoff import (
    DECLINE_FLOOR,
    Equity,
    RunoffValuation,
    implied_decline_rate,
    runoff_equity,
    runoff_rates,
    runoff_valuation,
)
from fairband.engine.types import Flag, TaggedInput
from fairband.policy import Policy

_NOT_POSITIVE = "value not positive in the run-off"
# The normalized margin: the last five fiscal years, at least three with a margin (method 4.1a).
_MARGIN_YEARS = 5
_MARGIN_MIN = 3
# The common inputs the run-off does not read: its charge is the release, not the runway return.
_NOT_READ = frozenset({"aggregate_roic", "runway_return"})
_NO_CONSENSUS = "no usable consensus: years 1 to 3 shrink at the decline rate"
# Why a row has no rating, so no π: no debt line on file (unknown debt is not "no net debt"), or
# net debt and no interest expense on file.
_NO_DEBT = "no debt line on file"
_NO_INTEREST = "no interest expense on file"
# The newest annual balance sheet's lines Z″ and F read, by the input names that cite them (a flow
# line of the fiscal year ends in _fy), and the year before's that F reads. The floor reads the
# newest balance sheet, a quarter's or a fiscal year's, under names of its own (``_floor_inputs``).
_BALANCE_INPUTS = {
    "total_current_assets": "total_current_assets",
    "total_current_liabilities": "total_current_liabilities",
    "total_assets": "total_assets",
    "total_liabilities": "total_liabilities",
    "retained_earnings": "retained_earnings",
    "equity": "equity",
    "long_term_debt": "long_term_debt",
    "revenue": "revenue_fy",
    "gross_profit": "gross_profit_fy",
    "operating_income": "operating_income_fy",
    "net_income": "net_income_fy",
    "cfo": "cfo_fy",
    "stock_issued": "stock_issued_fy",
}
_PRIOR_LINES = (
    "total_current_assets",
    "total_current_liabilities",
    "total_assets",
    "long_term_debt",
    "revenue",
    "gross_profit",
    "net_income",
)

_Used = Literal["own-latest", "peers", "override"]


@dataclass(frozen=True)
class _Consensus:
    """Years 1 to K: the NTM revenue as found (``None`` without a window whose periods each have
    a revenue mean) and as year 1 reads it, an agent's guided NTM revenue in its place on the
    window; whether it is usable (on the window and positive), the annual steps of years
    2 and 3 as found and which were held, the steps of years 4 to K (none without a usable
    consensus), whether g_2 or g_3 as resolved falls 100% or more, and the path's flags in
    order."""

    found: float | None
    ntm: float | None
    usable: bool
    steps: tuple[float | None, float | None]
    held: tuple[bool, bool]
    beyond: tuple[float, ...]
    falls: bool
    flags: tuple[Flag, ...]


def value_decline(c: Context) -> Valued | Refused:
    """The run-off's value a share for a Decline row, or the refusal."""
    i, t, policy = c.inputs, c.trailing, c.policy
    if t.revenue is None or t.revenue <= 0:
        return Refused("no trailing revenue")
    if t.operating_income is None:
        return Refused("no trailing operating income")
    tax = i.tax_rate_latest
    if tax is None:
        return Refused("no statutory tax rate")
    revenue0, n = t.revenue, policy.runoff_years
    trend = _decline_rate(c)
    if trend is None:
        return Refused("no revenue trend")
    d, floored = trend
    path = _consensus(c, revenue0, d, floored)
    if path.falls:
        return Refused("consensus revenue falls to zero or below within the path", path.flags)
    years = i.balance_years
    newest = years[-1] if years else None  # the newest fiscal year's, which Z″ reads
    lines = path.flags + bridge_flags(c) + present(_liabilities_flag(i.sheet))
    moat = moat_class(i.moat_score, policy)
    roic = RoicTerms.of(i.capital_years, moat, policy)
    s2c = _sales_to_capital(c, roic)
    if s2c is None:
        return Refused("no sales-to-capital", lines)
    used, sales_to_capital = s2c

    margin = _margin(i.series, t.operating_income / revenue0)
    ebit_n = revenue0 * margin["value"]
    debt_line = chosen(c, "balance.debt", i.debt)
    debt, cash = nil(debt_line), nil(chosen(c, "balance.cash", i.cash))
    minority_interest = minority(c)
    # Unknown debt is not "no net debt": without a debt line there is no rating. The rating reads
    # debt and cash alone, never the minority interest.
    found = None if debt_line is None else rate(ebit_n, t.interest_expense, debt, cash, policy)
    unrated = _NO_DEBT if debt_line is None else _NO_INTEREST
    rebuild: dict[str, Any] = {
        "runoff_path": {
            "revenue0": revenue0,
            "ntm_revenue": path.ntm if path.usable else None,
            "steps": [*path.steps, *path.beyond],
            "consensus_years": 3 + len(path.beyond),
            "d": d,
            "runoff_years": n,
        },
        "margin": margin,
        "tax_rate": tax,
        "sales_to_capital": {"used": used, "value": sales_to_capital},
        "runoff_recovery": policy.runoff_recovery,
        "debt": debt,
        "cash": cash,
        "minority_interest": minority_interest,
        **sheet_entry(i),
        "shares": c.shares,
        "ncav": None if i.sheet is None else ncav(i.sheet),
        "pi": {
            "value": None if found is None else found.pi,
            "rating": None if found is None else found.rating,
            "coverage": None if found is None else found.coverage,
        },
        "distress_sale_fraction": policy.distress_sale_fraction,
    }
    rates = _rates(rebuild["runoff_path"], d)
    v = _valuation(rebuild, rates, policy)
    e = _equity(rebuild, v.firm_value)
    z = None if newest is None else altman_z(newest, policy)
    f = piotroski_f(years[-1], years[-2]) if len(years) >= 2 else None
    gap = nri_gap(i)
    e_ps = eps(t, gap, None)
    im: dict[str, Any] = {
        **rebuild,
        "moat": moat,
        "growth_rates": list(rates),
        "revenue_by_year": list(v.revenue),
        "ebit_by_year": list(v.ebit),
        "tax_by_year": list(v.tax),
        "nopat_by_year": list(v.nopat),
        "reinvestment_by_year": list(v.reinvestment),
        "release_by_year": list(v.release),
        "fcff_by_year": list(v.fcff),
        "terminal_value": v.terminal_value,
        "firm_value": v.firm_value,
        "equity": v.firm_value - debt - minority_interest + cash,
        "going_concern_per_share": e.gc_per_share,
        "ncav_per_share": e.ncav_per_share,
        "floored_per_share": e.floored_per_share,
        "rating": _rating(found, unrated, ebit_n, t.interest_expense, policy),
        "distress_proceeds": policy.distress_sale_fraction * v.firm_value + cash,
        "distress_per_share": e.distress_per_share,
        "value_per_share": e.value_per_share,
        **outside_entry(c),
        "altman_z": None if z is None or newest is None else {"year": newest.year, **asdict(z)},
        "piotroski_f": None if f is None else _f_intermediates(f, years),
        "capex_vs_depreciation": {"capex": t.capex, "depreciation": t.depreciation},
        "eps": e_ps,
        "epv": None if e_ps["clean"] is None else epv(e_ps["clean"], policy.required_return),
        **income(i.market_cap, t),
        "price_facts": price_facts_for(i.closes, c.price, c.today),
    }
    flags = (
        lines
        + (present(from_industry(c)) if used == "peers" else ())
        + ((TAX_LOSS,) if margin["trailing"] < 0 or any(x < 0 for x in v.ebit) else ())
        + present(_ncav_floor(e, rebuild["pi"]["value"], minority_interest))
        + present(_not_charged(found, unrated))
        + present(_z_distress(z, policy))
        + present(_f_score_low(f, policy))
        + present(_reinvesting(t, v.revenue[-1] < revenue0, i.currency))
        + trailing_flags(i, t, gap, policy)
    )
    inputs = (
        *(x for x in common_inputs(i, t, roic) if x.name not in _NOT_READ),
        *_path_inputs(c, path),
        data(
            i,
            "interest_expense",
            t.interest_expense,
            money(i),
            "statements",
            "trailing twelve months, each period's expense by its size",
        ),
        *_sales_to_capital_input(c, used, sales_to_capital),
        *debt_and_cash(i),
        minority_input(i),
        *_floor_inputs(c),
        *_balance_inputs(c),
        data(i, "depreciation", t.depreciation, money(i), "statements", "trailing twelve months"),
        rule(policy, "required_return", policy.required_return, "ratio"),
        rule(policy, "runoff_years", n, "years"),
        rule(
            policy,
            "runoff_recovery",
            policy.runoff_recovery,
            "ratio",
            "the share of the capital a fall in revenue releases that a divestiture recovers",
        ),
        rule(
            policy,
            "distress_sale_fraction",
            policy.distress_sale_fraction,
            "ratio",
            "the share of the firm value a distress sale recovers",
        ),
        *_rating_inputs(found, unrated, policy),
        rule(policy, "z_distress", policy.z_distress, "score"),
        rule(policy, "z_safe", policy.z_safe, "score"),
        rule(policy, "f_score_low", policy.f_score_low, "score"),
        rule(policy, "moat_class", None, "class", moat),
        rule(policy, "margin_of_safety", policy.margin_of_safety[moat], "ratio", f"{moat} moat"),
        *_peer_rules(c, used),
    )
    value, outside = e.value_per_share, outside_value(c)
    if value + outside <= 0:
        return Refused(_NOT_POSITIVE, flags, im, inputs)
    im |= decline_at_price(im, c.price, value + outside, policy)
    return Valued("decline", value + outside, moat, im, inputs, flags)


def decline_at_price(
    im: dict[str, Any], price: float, value: float, policy: Policy
) -> dict[str, Any]:
    """The intermediates that move with the price, from the rebuild keys in ``im``, at ``price``
    and the result's ``value`` a share: the decline rate at which the run-off, the consensus years
    as found and the fade from that rate, floored and weighted as built, is worth the business's
    share of the price (``route_steps.business_price``; ``None`` when the scan finds none), the
    trailing multiples, and the expected return growing at the path's own rates from year 2,
    zero past year N."""

    def value_at(trial: float) -> float:
        v = _valuation(im, _rates(im["runoff_path"], trial), policy)
        return _equity(im, v.firm_value).value_per_share

    horizon = policy.repricing_horizon_years
    return {
        "implied_decline_rate": implied_decline_rate(value_at, business_price(im, price)),
        "multiples": multiples_at(price, im["eps"]),
        "expected_return": expected(price, value, im, im["growth_rates"][1:], horizon, 0.0),
    }


def _decline_rate(c: Context) -> tuple[float, bool] | None:
    """d: the five-year revenue slope over the last fiscal year's revenue, at most zero, floored
    at ``DECLINE_FLOOR``; and whether the floor bound. An agent's ``decline.rate`` stands as it
    is, never floored. The classifier puts a company in Decline only on a falling trend with a
    positive last revenue; a row a ``phase`` override puts here may lack either, and has no d
    (``None``)."""
    judged: float | None = chosen(c, "decline.rate", None)
    if judged is not None:
        return judged, False
    evidence, series = c.evidence, c.inputs.series
    slope = None if evidence is None else evidence.revenue_slope
    last = series[-1].revenue if series else None
    if slope is None or last is None or last <= 0:
        return None
    trend = min(0.0, slope / last)
    return max(DECLINE_FLOOR, trend), trend < DECLINE_FLOOR


def _consensus(c: Context, revenue0: float, d: float, floored: bool) -> _Consensus:
    """Years 1 to K and the path's flags: ``path-held``, ``decline-rate-floored``,
    ``path-on-trend`` without a usable NTM consensus, ``consensus-recovery``, ``few-analysts``.
    The years past 3 are read only on a usable consensus and only to ``runoff_years``. An agent's
    guided NTM revenue stands in for the window's sum before the positive test; without the
    window (``anchor.ntm_window`` on the trailing cadence), or with a period lacking its revenue
    mean, it is not read."""
    i, n = c.inputs, c.policy.runoff_years
    floor = (_floored(),) if floored else ()
    window = ntm_window(i.quarter_estimates, c.trailing.period_end, c.trailing.cadence)
    periods = None if window is None else window[0]
    found = ntm_revenue(periods)
    ntm = found if periods is None or found is None else chosen(c, "revenue.ntm", found)
    if periods is None or ntm is None or ntm <= 0:
        on_trend = (*floor, _on_trend(d, n))
        return _Consensus(found, ntm, False, (None, None), (False, False), (), False, on_trend)
    base = base_fiscal_year(periods)
    path, _, path_flags = revenue_path_for(
        revenue0, ntm, i.annual_estimates, base, None, c.policy, judged=judged_steps(c)
    )
    beyond = consensus_beyond(i.annual_estimates, base, c.policy)[: n - 3]
    resolved, held = resolved_steps(path)
    flags = (
        _coded(path_flags, "path-held")
        + floor
        + present(_recovery((ntm / revenue0 - 1, *path.steps, *beyond), d))
        + _coded(path_flags, "few-analysts")
    )
    falls = any(g <= -1 for g in resolved)
    return _Consensus(found, ntm, True, path.steps, held, beyond, falls, flags)


def _coded(flags: tuple[Flag, ...], code: str) -> tuple[Flag, ...]:
    return tuple(f for f in flags if f.code == code)


def _rates(p: dict[str, Any], d: float) -> tuple[float, ...]:
    """The rates for years 1 to N from ``runoff_path`` at the decline rate ``d``: the consensus
    steps as found to year K, then d fading to zero."""
    ntm = p["ntm_revenue"]
    g1 = None if ntm is None else ntm / p["revenue0"] - 1
    steps = p["steps"]
    return runoff_rates(g1, steps[0], steps[1], steps[2:], d, p["runoff_years"])


def _valuation(im: dict[str, Any], rates: tuple[float, ...], policy: Policy) -> RunoffValuation:
    """The run-off from the rebuild keys at these rates."""
    return runoff_valuation(
        im["runoff_path"]["revenue0"],
        rates,
        im["margin"]["value"],
        im["tax_rate"],
        im["sales_to_capital"]["value"],
        im["runoff_recovery"],
        policy.required_return,
    )


def _equity(im: dict[str, Any], firm_value: float) -> Equity:
    """The value a share from the firm value and the rebuild keys: floored, then weighted, the
    minority interest off each claim, nil on a row stored before method 1.4 carried it."""
    return runoff_equity(
        firm_value,
        im["debt"],
        im["cash"],
        im["shares"],
        im["ncav"],
        im["pi"]["value"],
        im["distress_sale_fraction"],
        im.get("minority_interest", 0.0),
    )


def _margin(series: Series, trailing: float) -> dict[str, Any]:
    """The normalized margin: the median of the operating margins of the last five fiscal years
    that have one, when at least three do; else the trailing margin."""
    read = [
        (fy.year, m) for fy in series[-_MARGIN_YEARS:] if (m := operating_margin(fy)) is not None
    ]
    margins = [m for _, m in read]
    median = statistics.median(margins) if len(margins) >= _MARGIN_MIN else None
    return {
        "value": trailing if median is None else median,
        "used": "trailing" if median is None else "median",
        "median": median,
        "trailing": trailing,
        "years": [year for year, _ in read],
        "margins": margins,
    }


def _sales_to_capital(c: Context, roic: RoicTerms) -> tuple[_Used, float] | None:
    """An agent's figure; else the company's own newest kept ROIC year's revenue over its average
    capital; else the mature peers' median; else none."""
    judged: float | None = chosen(c, "capital.sales_to_capital", None)
    if judged is not None:
        return "override", judged
    i = c.inputs
    revenue = {fy.year: fy.revenue for fy in i.series if fy.revenue is not None}
    own = newest_sales_to_capital(roic.result.by_year, revenue)
    if own is not None:
        return "own-latest", own
    peers = peer_sales_to_capital(i.peers, c.policy)
    return None if peers is None else ("peers", peers)


def _rating(
    found: Rating | None, unrated: str, ebit: float, interest: float | None, policy: Policy
) -> dict[str, Any]:
    """The rating's figures; its row is the coverage range of the table row it came from. Without
    a rating the note says why (``unrated``)."""
    if found is None:
        return {
            "rating": None,
            "ebit": ebit,
            "interest": interest,
            "coverage": None,
            "pi": None,
            "row": None,
            "note": unrated,
        }
    row = None if found.coverage is None else _row(found.rating, policy)
    return {
        "rating": found.rating,
        "ebit": ebit,
        "interest": interest,
        "coverage": found.coverage,
        "pi": found.pi,
        "row": row,
        "note": found.note,
    }


def _row(rating: str, policy: Policy) -> dict[str, float | None]:
    """The coverage range of the rating's row: from its bound to below the next row's, ``None`` at
    an open end."""
    table = policy.synthetic_rating
    k = next(k for k, row in enumerate(table) if row.rating == rating)
    low = table[k].coverage_min
    return {
        "coverage_from": None if math.isinf(low) else low,
        "coverage_below": table[k + 1].coverage_min if k + 1 < len(table) else None,
    }


def _f_intermediates(f: FScore, years: tuple[BalanceYear, ...]) -> dict[str, Any]:
    return {
        "year": years[-1].year,
        "prior_year": years[-2].year,
        "signals": [{"name": name, "value": value} for name, value in f.signals],
        "score": f.score,
        "read": f.read,
    }


def _floored() -> Flag:
    return Flag(
        "decline-rate-floored",
        "Decline rate floored",
        f"The five-year trend shrinks revenue faster than {-DECLINE_FLOOR:.0%} a year; the "
        f"run-off uses −{-DECLINE_FLOOR:.0%}.",
    )


def _on_trend(d: float, n: int) -> Flag:
    """``path-on-trend``, naming the decline rate as used (on a floored row, −50%, not the trend's
    own figure) and the year ``n`` its fade reaches zero."""
    return Flag(
        "path-on-trend",
        "Path on trend",
        f"No usable consensus: years 1 to 3 shrink at the decline rate, {signed(d)}, which fades to "
        f"zero by year {n}.",
    )


def _recovery(rates: tuple[float | None, ...], d: float) -> Flag | None:
    """``consensus-recovery`` naming each consensus year, 1 to K, that grows, and the decline rate
    as used (on a floored row, −50%, not the trend's own figure); a held step is not the
    consensus's and is not named."""
    rising = [
        f"{g:.1%} in year {t}" for t, g in enumerate(rates, start=1) if g is not None and g > 0
    ]
    if not rising:
        return None
    return Flag(
        "consensus-recovery",
        "Consensus recovery",
        f"The consensus has revenue growing {' and '.join(rising)} while the decline rate is "
        f"{signed(d)}.",
    )


def _liabilities_flag(sheet: NewestSheet | None) -> Flag | None:
    """``line-not-presented:totalLiabilities`` when the newest balance sheet, which the floor
    reads, lacks the line, naming its period, or none is on file: no net-current-asset floor is
    applied."""
    if sheet is not None and sheet.total_liabilities is not None:
        return None
    where = (
        "No balance sheet is on file"
        if sheet is None
        else f"The newest balance sheet ({sheet.label}) does not present total liabilities"
    )
    return Flag(
        "line-not-presented:totalLiabilities",
        "Line not presented: totalLiabilities",
        f"{where}, so no net-current-asset floor is applied.",
    )


def _ncav_floor(e: Equity, pi: float | None, minority_interest: float) -> Flag | None:
    """``ncav-floor`` when the net current asset value, less the minority interest, floors the
    going-concern value and π is not 1 (an unavailable π included): at π = 1 the value is the
    distress-sale value alone and the floor has no weight. With a minority interest in force the
    sentence names the floor "the net current asset value less the minority interest"; with none,
    it reads as before method 1.4."""
    if not e.floor_bound or e.ncav_per_share is None or pi == 1:
        return None
    floor = f"{e.ncav_per_share:,.2f} a share"
    named = (
        f"the net current asset value less the minority interest, {floor}"
        if minority_interest > 0
        else f"the net current asset value {floor}"
    )
    return Flag(
        "ncav-floor",
        "NCAV floor",
        f"The floored value is {named}; the run-off gives {e.gc_per_share:,.2f}.",
    )


def _not_charged(found: Rating | None, unrated: str) -> Flag | None:
    """``distress-not-charged`` when there is no rating, saying why (``unrated``)."""
    if found is not None:
        return None
    return Flag(
        "distress-not-charged",
        "Distress not charged",
        f"{unrated[0].upper()}{unrated[1:]}: the distress probability is unavailable and the "
        "value is the floored going-concern value.",
    )


def _z_distress(z: ZScore | None, policy: Policy) -> Flag | None:
    if z is None or z.zone != "distress":
        return None
    return Flag(
        "z-distress",
        "Z″ distress",
        f"Altman Z″ is {z.score:.2f}, in the distress zone below {policy.z_distress:g}.",
    )


def _f_score_low(f: FScore | None, policy: Policy) -> Flag | None:
    """``f-score-low`` at or below the policy's low group, when F read a signal at all."""
    if f is None or f.read == 0 or f.score > policy.f_score_low:
        return None
    return Flag(
        "f-score-low",
        "Low F-score",
        f"Piotroski F is {f.score} of {f.read}: the low group of Piotroski (2000).",
    )


def _reinvesting(t: TrailingFigures, falls: bool, currency: str) -> Flag | None:
    """``reinvesting-in-decline`` when trailing capital spending exceeds trailing depreciation in
    size while the run-off's revenue falls; neither missing. The figures are in ``currency``."""
    capex, depreciation = t.capex, t.depreciation
    if not falls or capex is None or depreciation is None or abs(capex) <= abs(depreciation):
        return None
    return Flag(
        "reinvesting-in-decline",
        "Reinvesting in decline",
        f"Capital spending {millions(abs(capex), currency)} exceeds depreciation "
        f"{millions(abs(depreciation), currency)} while revenue falls: Damodaran's denial.",
    )


def _path_inputs(c: Context, path: _Consensus) -> tuple[TaggedInput, ...]:
    """The NTM revenue as found, the two annual steps as found and one step for each consensus
    year past year 3, ``path_step_4`` to ``path_step_K``; without a usable consensus the first
    three say so. An agent's guided NTM revenue is its JUDGMENT entry, not this data."""
    i = c.inputs
    if not path.usable:
        return (
            data(i, "ntm_revenue", path.found, money(i), "estimates_quarter", _NO_CONSENSUS),
            data(i, "path_step_2", None, "ratio", "estimates_annual", _NO_CONSENSUS),
            data(i, "path_step_3", None, "ratio", "estimates_annual", _NO_CONSENSUS),
        )
    return (
        data(i, "ntm_revenue", path.found, money(i), "estimates_quarter"),
        step_input(c, "path_step_2", path.steps[0], path.held[0]),
        step_input(c, "path_step_3", path.steps[1], path.held[1]),
        *(step_input(c, f"path_step_{t}", g, False) for t, g in enumerate(path.beyond, start=4)),
    )


def _sales_to_capital_input(c: Context, used: _Used, value: float) -> tuple[TaggedInput, ...]:
    """The sales-to-capital used: the own newest year from the statements (an estimate under the
    intangibles method when invested capital took it), or the peers' median; none for an agent's
    figure, which its JUDGMENT entry cites."""
    if used == "override":
        return ()
    if used == "own-latest":
        return (
            from_capital(
                c.inputs,
                "sales_to_capital",
                value,
                "the company's own newest year: revenue over average invested capital",
            ),
        )
    industry = peer_industry(c)
    median = "the mature peers' median" + ("" if industry is None else f" ({industry} industry)")
    return (
        from_peers(
            c, "sales_to_capital", value, f"{median}; the company has no newest-year measure"
        ),
    )


def _floor_inputs(c: Context) -> tuple[TaggedInput, ...]:
    """The two lines of the newest balance sheet the liquidation floor reads, under their own
    names, since the sheet can be a quarter's: cited to it (``balance_sheet``) and noted with its
    period. None without a sheet, which gives no floor."""
    i, sheet = c.inputs, c.inputs.sheet
    if sheet is None:
        return ()
    lines = (
        ("floor_current_assets", sheet.total_current_assets),
        ("floor_total_liabilities", sheet.total_liabilities),
    )
    return tuple(
        data(i, name, figure, money(i), "balance_sheet", sheet_note(i)) for name, figure in lines
    )


def _balance_inputs(c: Context) -> tuple[TaggedInput, ...]:
    """The lines of the newest annual balance sheet and its fiscal year that Z″ and F read, and the
    year before's that F reads, each noted with its fiscal year."""
    years, i = c.inputs.balance_years, c.inputs
    if not years:
        return ()
    newest = years[-1]
    found = [
        data(i, name, getattr(newest, line), money(i), "statements", f"fiscal {newest.year}")
        for line, name in _BALANCE_INPUTS.items()
    ]
    if len(years) >= 2:
        prior = years[-2]
        found += [
            data(
                i,
                f"{_BALANCE_INPUTS[line]}_prior",
                getattr(prior, line),
                money(i),
                "statements",
                f"fiscal {prior.year}",
            )
            for line in _PRIOR_LINES
        ]
    return tuple(found)


def _rating_inputs(
    found: Rating | None, unrated: str, policy: Policy
) -> tuple[TaggedInput, TaggedInput]:
    """The synthetic rating's row and the default probability used, or why there is none."""
    if found is None:
        return (
            rule(policy, "synthetic_rating", None, "coverage", f"no rating: {unrated}"),
            rule(
                policy, "default_probability_10y", None, "probability", "no rating: π unavailable"
            ),
        )
    if found.coverage is None:
        return (
            rule(policy, "synthetic_rating", None, "coverage", "no rating: cash covers debt"),
            rule(policy, "default_probability_10y", None, "probability", "no net debt: π is 0"),
        )
    row = _row(found.rating, policy)
    low, below = row["coverage_from"], row["coverage_below"]
    span = (
        f"below {below:g}"
        if low is None
        else f"from {low:g}" + ("" if below is None else f" to below {below:g}")
    )
    note = f"the {found.rating} row: an interest coverage {span}; the company's is {found.coverage:.2f}"
    return (
        rule(policy, "synthetic_rating", low, "coverage", note),
        rule(
            policy,
            "default_probability_10y",
            found.pi,
            "probability",
            f"the ten-year probability of default of the {found.rating} rating",
        ),
    )


def _peer_rules(c: Context, used: _Used) -> tuple[TaggedInput, ...]:
    """``peer_min``, and ``industry_peer_max`` on the industry's peers, when the peers served."""
    if used != "peers":
        return ()
    policy = c.policy
    return (
        rule(policy, "peer_min", policy.peer_min, "peers"),
        *industry_peer_max_input(policy, peer_industry(c)),
    )
