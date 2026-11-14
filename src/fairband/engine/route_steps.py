"""The steps the routes share, below ``route`` and the route modules.

A route reads the company through a ``Context``, built by ``route.value_company`` once the guards
have passed: so with trailing figures, a positive price and a positive diluted share count. The
Start-up route reads a ``StartUpContext``, the same with the trailing figures when there are any.
A route returns ``Valued`` or ``Refused`` and ``route`` builds the result from it.

``RoicTerms`` carries the returns of the charge to both routes (calibration spec 5.1 and 5.3): the
runway return for the runway years, and the terminal return read from it. The ten-year aggregate
ROIC is shown, and when positive it feeds the sensitivity; it never enters the charge. When the
marginal return is not usable and the fallback years' capital sums to zero or below, the
runway charge is off, on either route; the terminal still charges. The income term of the
expected return is the trailing flows over the market cap: FMP signs dividends and buybacks as
outflows (negative) and stock issued as an inflow, and a missing flow counts as nil.

An agent's applied overrides ride on the context (``overrides``, by tag; empty for the mechanical
method), and a route reads each input of ``overrides.TAGS`` through ``chosen``: the override's
value when one applies, else the route's own reading. ``judgment_inputs`` are the JUDGMENT
entries ``route`` cites for them. ``RoicTerms.of`` takes an overriding runway return as
``runway_override``: it replaces the runway return the charge uses, the start of its fade, and
charges the runway years, and the terminal return still follows the moat on the measured return,
save on a row the engine started at the return without goodwill, where the moat's rule reads the
override (14.4).
``outside_value`` is an agent's value outside the business a share, nil without one: each valued
route adds it to its own value a share, and every solve on the price targets the price less it,
``business_price``, the business's share of the price (``method.md`` 14.4). The diluted share
count reaches a route as ``Context.shares``, an agent's count in place of the reported one.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from typing import TYPE_CHECKING, Any, cast

from fairband.engine.anchor import TrailingFigures
from fairband.engine.flags import basis_unknown_flag, gate_flags, margin_flag, nri_flag
from fairband.engine.mature_growth import Charge
from fairband.engine.multiples import multiples
from fairband.engine.overrides import (
    BRIDGE_ORDER,
    INPUT_OF,
    TAGS,
    Override,
    Overrides,
    OverrideTag,
    unit_in,
)
from fairband.engine.price_facts import price_facts
from fairband.engine.returns import expected_return
from fairband.engine.roic import (
    CapitalYear,
    RoicResult,
    RunwayReturn,
    aggregate_roic,
    runway_note,
    runway_return,
    terminal_return,
    terminal_roic,
)
from fairband.engine.types import Flag, Kind, PhaseEvidence, Provenance, Route, TaggedInput
from fairband.policy import Moat, Policy

if TYPE_CHECKING:
    from fairband.engine.route import CompanyInputs

_UNKNOWN = Provenance("unknown", None, None, None)
# The ``estimate_methods`` key assembly sets when invested capital takes the issuer's as-reported
# intangibles total; no input bears the name, so the inputs read from invested capital carry it.
_INTANGIBLES = "intangibles"
_INTANGIBLES_NOTE = "invested capital uses the issuer's total intangibles excluding goodwill"
# The measure the charge's return starts at, as the ``heavy-capex`` sentence names it; a runway
# return that is off or unavailable names none.
_CHARGE_START = {
    "marginal": "the five-year marginal",
    "three-year": "the three-year aggregate",
    "without-goodwill": "read on capital without goodwill and intangibles, at most the cap",
    "floor": "floored at the required return",
}
# The measured return beside an agent's ``return.runway``, which the charge starts at instead:
# the chosen measure before any floor, and, where the measure is below r and the return without
# goodwill would lift the start, that start (the second figure).
_MEASURED = {
    "marginal": "the five-year marginal is {}",
    "three-year": "the three-year aggregate is {}",
    "without-goodwill": (
        "the measured return is {}, below the required return, and the charge would start at "
        "{}, on capital without goodwill and intangibles"
    ),
    "floor": "the measured return is {}, below the required return",
}


@dataclass(frozen=True)
class Context:
    """A company past the guards of ``route.value_company``, with the classifier's evidence that
    put it in its phase (the Decline route reads its revenue trend) and the applied overrides by
    tag; ``shares`` is the diluted count, an agent's ``shares.diluted`` when one applies."""

    inputs: CompanyInputs
    trailing: TrailingFigures
    price: float
    shares: float
    policy: Policy
    today: date
    evidence: PhaseEvidence | None = None
    overrides: Overrides = field(default_factory=dict)


@dataclass(frozen=True)
class StartUpContext:
    """A Start-up company past the guards ``route.value_company`` runs before its route: a
    positive price and diluted share count (an agent's ``shares.diluted`` when one applies), and
    the trailing figures when there are any, since a pre-revenue company may lack them; and the
    applied overrides by tag."""

    inputs: CompanyInputs
    trailing: TrailingFigures | None
    price: float
    shares: float
    policy: Policy
    today: date
    overrides: Overrides = field(default_factory=dict)


@dataclass(frozen=True)
class Valued:
    """A route's value a share and what ``route`` needs to build the result around it."""

    route: Route
    value: float
    moat: Moat
    intermediates: dict[str, Any]
    inputs: tuple[TaggedInput, ...]
    flags: tuple[Flag, ...]


@dataclass(frozen=True)
class Refused:
    """A route's refusal, with the flags it had raised, the intermediates it had computed and the
    inputs it cites beyond the ones every result carries (the Start-up route's)."""

    reason: str
    flags: tuple[Flag, ...] = ()
    intermediates: dict[str, Any] = field(default_factory=dict)
    inputs: tuple[TaggedInput, ...] = ()


@dataclass(frozen=True)
class RoicTerms:
    """The ten-year ROIC result, the runway return, the usable (positive) ten-year aggregate the
    sensitivity reads, the runway and terminal returns of the charge, whether the runway charge
    is off, the ROIC flags (the ten-year ones, then the runway return's), and whether the runway
    return is an agent's override."""

    result: RoicResult
    runway_return: RunwayReturn
    usable: float | None
    runway: float
    terminal: float
    charge_off: bool
    flags: tuple[Flag, ...]
    overridden: bool = False

    @classmethod
    def of(
        cls,
        years: Sequence[CapitalYear],
        moat: Moat,
        policy: Policy,
        *,
        runway_override: float | None = None,
    ) -> RoicTerms:
        """The returns of ``years`` under ``moat``; with ``runway_override``, an agent's runway
        return in place of the measured one: it charges the runway years, and the flags of the
        measured return (``return-floored``, ``return-without-goodwill``, ``charge-zeroed``) are
        not raised. The terminal return stays on the measured return, save on a row whose
        measured start is the return without goodwill: there the engine's own terminal return
        rests on that start, the override judges it, and the moat's terminal rule reads the
        override (``method.md`` 14.4). Every other row keeps the rule it had before method 1.2,
        a floored one too."""
        result = aggregate_roic(years)
        rr = runway_return(result, moat, policy)
        terminal = terminal_return(rr, moat, policy)
        aggregate = result.aggregate
        usable = aggregate if aggregate is not None and aggregate > 0 else None
        if runway_override is not None:
            if rr.used == "without-goodwill":
                terminal = terminal_roic(runway_override, moat, policy)
            return cls(result, rr, usable, runway_override, terminal, False, result.flags, True)
        flags = result.flags + rr.flags
        return cls(result, rr, usable, rr.value, terminal, rr.charge_off, flags)

    def intermediates(self) -> dict[str, Any]:
        r, rr = self.result, self.runway_return
        return {
            "roic": {
                "aggregate": r.aggregate,
                "years": r.years_used,
                "by_year": [asdict(y) for y in r.by_year],
            },
            "runway_return": {
                "used": rr.used,
                "marginal": rr.marginal,
                "marginal_usable": rr.marginal_usable,
                "three_year": rr.three_year,
                "ten_year": rr.ten_year,
                "one_year": rr.one_year,
                "without_goodwill": (
                    None if rr.without_goodwill is None else asdict(rr.without_goodwill)
                ),
                "value": self.runway,
            },
            "terminal_roic": self.terminal,
        }

    def charge(self, policy: Policy, hold: int | None = None) -> Charge:
        """This row's charge, as both routes apply it: its runway and terminal returns, off in
        the runway years when the marginal return is not usable and the three-year capital sum
        is at or below zero, and the ``hold`` of ``charge_for``."""
        return charge_for(self.runway, self.terminal, self.charge_off, policy, hold)


def charge_for(
    runway_roic: float,
    terminal: float,
    charge_off: bool,
    policy: Policy,
    hold: int | None = None,
) -> Charge:
    """The reinvestment charge at these returns: ``runway_roic`` held through year ``hold`` then
    faded to ``terminal`` in year N, the terminal at ``terminal``, and none in years 1 to N−1 when
    ``charge_off``. A ``hold`` of ``None`` is the shape before method 1.0: ``runway_roic`` in
    years 1 to N−1."""
    return Charge(
        runway_roic, terminal, policy.required_return, policy.terminal_growth, charge_off, hold
    )


def chosen[T](c: Context | StartUpContext, tag: OverrideTag, computed: T) -> T:
    """The overriding value of ``tag`` when the context holds an override of it, else
    ``computed``, the route's own reading. The value is passed as stored: the override's number
    or word, which the rules of ``overrides.check_override`` gave the input's type."""
    found = c.overrides.get(tag)
    return computed if found is None else cast(T, found.value)


def judgment_inputs(overrides: Overrides, currency: str = "USD") -> tuple[TaggedInput, ...]:
    """The JUDGMENT entries of the overrides, in the bridge's order: each named by its tag, its
    number as the value (``None`` for a word, which leads the note), the input's unit in the
    row's ``currency`` (``overrides.unit_in``), and the override's provenance: the source
    "override <id>, <principal> <actor>", entered at the override's time, the reason as the
    note."""
    return tuple(_judgment(overrides[tag], currency) for tag in BRIDGE_ORDER if tag in overrides)


def _judgment(o: Override, currency: str) -> TaggedInput:
    """The override's entry; its source names the override, the principal and the actor, "override
    1, agent claude-opus-5-5", or the principal alone without an actor, "override 1, owner"."""
    record = "override" if o.id is None else f"override {o.id}"
    writer = o.principal if o.actor is None else f"{o.principal} {o.actor}"
    provenance = Provenance(f"{record}, {writer}", None, None, o.at)
    value: float | None = None
    note = o.reason
    if isinstance(o.value, str):
        note = f"{o.value}: {o.reason}"
    else:
        value = o.value
    unit = unit_in(TAGS[o.tag].unit, currency)
    return TaggedInput(o.tag, value, unit, "JUDGMENT", "judgment", provenance, note=note)


def judged_inputs(
    inputs: tuple[TaggedInput, ...], overrides: Overrides, currency: str = "USD"
) -> tuple[TaggedInput, ...]:
    """``inputs`` with the JUDGMENT entries of ``overrides`` in place of the route's own entries
    for the inputs they set (``overrides.INPUT_OF``), last, their units in the row's
    ``currency``."""
    if not overrides:
        return inputs
    replaced = {INPUT_OF[tag] for tag in overrides if tag in INPUT_OF}
    kept = tuple(x for x in inputs if x.name not in replaced)
    return kept + judgment_inputs(overrides, currency)


def nri_gap(i: CompanyInputs) -> float | None:
    """GuruFocus EPS less EPS without non-recurring items, a share; ``None`` without both."""
    if i.gf_eps_ttm is None or i.gf_eps_without_nri is None:
        return None
    return i.gf_eps_ttm - i.gf_eps_without_nri


def cycle_gap(c: Context) -> float | None:
    """An agent's cycle gap, the correction to mid-cycle earnings a share, ``None`` without one:
    the engine finds none (``overrides.current_reading`` reads its absence as nil)."""
    return chosen(c, "earnings.cycle_gap", None)


def cycle_entry(cycle: float | None) -> dict[str, float]:
    """The intermediates' ``cycle_gap``, written only under an override, so a mechanical
    result's intermediates do not carry it."""
    return {} if cycle is None else {"cycle_gap": cycle}


def outside_value(c: Context) -> float:
    """An agent's value outside the business a share, after tax, which the valued routes add to
    their value a share (spec 2026-11-09 8); nil without one: the engine finds none
    (``overrides.current_reading`` reads its absence as nil)."""
    return chosen(c, "value.outside", 0.0)


def outside_entry(c: Context) -> dict[str, float]:
    """The intermediates' ``outside_value_per_share``, written only under an override, so a
    mechanical result's intermediates do not carry it."""
    return {"outside_value_per_share": outside_value(c)} if "value.outside" in c.overrides else {}


def business_price(im: dict[str, Any], price: float) -> float:
    """The business's share of ``price``: the price less the intermediates'
    ``outside_value_per_share``, the price itself without one. Every solve on the price targets
    it (spec 2026-11-09 8), so a stored row moves to a new price from its intermediates alone."""
    outside: float = im.get("outside_value_per_share", 0.0)
    return price - outside


def eps(t: TrailingFigures, gap: float | None, forward: float | None) -> dict[str, float | None]:
    """Reported and clean (less the non-recurring gap) trailing EPS, and the forward EPS."""
    clean = None if t.eps_diluted is None else t.eps_diluted - nil(gap)
    return {"reported": t.eps_diluted, "clean": clean, "forward": forward}


def multiples_at(price: float, e: dict[str, float | None]) -> dict[str, float | None]:
    return asdict(multiples(price, e["reported"], e["clean"], e["forward"]))


def price_facts_for(
    closes: Sequence[tuple[date, float]], price: float | None, today: date
) -> dict[str, float | None] | None:
    """The price columns of spec 6.3 for every row with a price, a refused one too; ``None`` for
    a row without a price."""
    return None if price is None else asdict(price_facts(closes, today))


def ttm_margin(t: TrailingFigures) -> float | None:
    if t.revenue is None or t.operating_income is None or t.revenue <= 0:
        return None
    return t.operating_income / t.revenue


def income(market_cap: float | None, t: TrailingFigures) -> dict[str, Any]:
    """The dividend and net buyback yields of the expected return's income term; nil, with
    the basis "unavailable", without a positive, finite market cap."""
    if market_cap is None or not math.isfinite(market_cap) or market_cap <= 0:
        return {"dividend_yield": 0.0, "net_buyback_yield": 0.0, "income_basis": "unavailable"}
    return {
        "dividend_yield": -nil(t.dividends) / market_cap,
        "net_buyback_yield": (-nil(t.buybacks) - nil(t.equity_issued)) / market_cap,
        "income_basis": "flows over market cap",
    }


def expected(
    price: float,
    value: float,
    im: dict[str, Any],
    rates: Sequence[float],
    horizon: int,
    terminal: float,
) -> dict[str, float] | None:
    """The Step 9 expected return over ``horizon`` years on the income in ``im`` and the route's
    growth ``rates`` for years 2 onwards; past the rates the path grows at ``terminal``, the
    route's rate after its runway, so a horizon longer than the path never raises. ``None`` for a
    value at or below zero, which has no rate."""
    if value <= 0:
        return None
    padded = tuple(rates[:horizon]) + (terminal,) * max(horizon - len(rates), 0)
    er = expected_return(
        price, value, im["dividend_yield"], im["net_buyback_yield"], padded, horizon=horizon
    )
    return asdict(er)


def trailing_flags(
    i: CompanyInputs,
    t: TrailingFigures,
    gap: float | None,
    policy: Policy,
    roic: RoicTerms | None = None,
) -> tuple[Flag, ...]:
    """The margin flag, the three gate flags and the non-recurring flag, in that order. The two
    mature routes pass their ``roic``: ``consensus-basis-unknown`` then follows ``large-nri``,
    and the ``heavy-capex`` sentence names the return the charge starts at and the newest year's
    marginal return (spec 2026-11-09 6.3 and 7). The other routes pass none."""
    gates = gate_flags(t, i.market_cap, policy)
    nri = nri_flag(gap, t.eps_diluted, policy)
    basis: Flag | None = None
    if roic is not None:
        gates = tuple(_heavy_capex(f, roic) if f.code == "heavy-capex" else f for f in gates)
        basis = basis_unknown_flag(nri, gap, t.eps_diluted, i.currency)
    return (
        present(margin_flag(i.series, ttm_margin(t), policy))
        + gates
        + present(nri)
        + present(basis)
    )


def _heavy_capex(flag: Flag, roic: RoicTerms) -> Flag:
    """The ``heavy-capex`` flag with the runway return read beside it (spec 2026-11-09 6.3): the
    return the charge starts at and its measure, then the newest year's marginal return and its
    fiscal year, which leave a spending surge still under way to the agent's ``return.runway``.
    Under that override the start is the override's value and the measured return follows as the
    measure. Without a one-year figure the sentence stops there; without an override, as built
    when the runway return is off or unavailable."""
    rr = roic.runway_return
    if roic.overridden:
        start = (
            f"{flag.sentence} The charge's return starts at {signed(roic.runway)}, the agent's "
            "override"
        )
        measured = _MEASURED.get(rr.used)
        if measured is not None and rr.chosen is not None:
            start += f"; {measured.format(signed(rr.chosen), signed(rr.value))}"
    else:
        measure = _CHARGE_START.get(rr.used)
        if measure is None:
            return flag
        start = f"{flag.sentence} The charge's return starts at {signed(rr.value)}, {measure}"
    if rr.one_year is None or not roic.result.by_year:
        return replace(flag, sentence=f"{start}.")
    year = roic.result.by_year[-1].year
    return replace(
        flag,
        sentence=f"{start}; the newest year's marginal return is {signed(rr.one_year)}, on the "
        f"capital added in fiscal {year}. The stored years end at fiscal {year}, so a return on "
        "a spending surge still under way is the agent's judgment: `return.runway`.",
    )


def common_inputs(i: CompanyInputs, t: TrailingFigures, roic: RoicTerms) -> tuple[TaggedInput, ...]:
    """The DATA inputs every route reads, beyond the ones every result carries; the market cap is
    the one the route read, in the reporting currency."""
    return (
        data(i, "market_cap", i.market_cap, money(i)),
        data(i, "revenue_ttm", t.revenue, money(i), "statements"),
        data(i, "operating_income_ttm", t.operating_income, money(i), "statements"),
        data(i, "eps_ttm", t.eps_diluted, per_share(i), "statements"),
        data(i, "dividends_ttm", t.dividends, money(i), "statements"),
        data(i, "buybacks_ttm", t.buybacks, money(i), "statements"),
        data(i, "equity_issued_ttm", t.equity_issued, money(i), "statements"),
        from_capital(i, "aggregate_roic", roic.result.aggregate),
        from_capital(i, "runway_return", roic.runway, runway_note(roic.runway_return)),
        data(i, "tax_rate_latest", i.tax_rate_latest, "ratio"),  # the newest ROIC year's rate
        data(i, "moat_score", i.moat_score, "score"),
        data(i, "gf_eps_ttm", i.gf_eps_ttm, per_share(i)),
        data(i, "gf_eps_without_nri", i.gf_eps_without_nri, per_share(i)),
    )


def money(i: CompanyInputs) -> str:
    """The unit of a money total of ``i``: its reporting currency's code, ``USD`` or ``TWD``."""
    return i.currency


def per_share(i: CompanyInputs) -> str:
    """The unit of a figure a share of ``i``: ``USD a share``, ``TWD a share``."""
    return f"{i.currency} a share"


def from_capital(
    i: CompanyInputs, name: str, value: float | None, note: str | None = None
) -> TaggedInput:
    """A ratio read from invested capital (a return, or sales-to-capital), cited to the
    statements: an estimate under the intangibles method when assembly took the issuer's
    as-reported intangibles total into invested capital (D17). Its note is ``note``; without
    one, an estimate's note says why."""
    found = data(i, name, value, "ratio", "statements", note)
    method = i.estimate_methods.get(_INTANGIBLES)
    if method is None:
        return found
    why = _INTANGIBLES_NOTE if note is None else note
    return replace(found, kind="estimate", estimate_method=method, note=why)


def sheet_note(i: CompanyInputs, name: str | None = None) -> str | None:
    """The note of an input read from the newest balance sheet (``CompanyInputs.sheet``): its
    period, "the balance sheet of fiscal 2026 Q3", then "; " and the note ``notes`` holds for
    ``name``, assembly's on the lines the sheet does not present. Without a sheet that note alone;
    ``None`` with neither. The period stays out of ``notes``, whose entries raise
    ``line-not-presented``."""
    missing = None if name is None else i.notes.get(name)
    if i.sheet is None:
        return missing
    period = f"the balance sheet of {i.sheet.label}"
    return period if missing is None else f"{period}; {missing}"


def debt_and_cash(i: CompanyInputs) -> tuple[TaggedInput, TaggedInput]:
    """The DATA entries ``debt`` and ``cash`` of the three firm-value routes: the newest balance
    sheet's figures as assembly summed them, cited to that sheet (``balance_sheet``, as of its
    period end), each noted with the sheet's period and the lines it does not present
    (``sheet_note``)."""
    return (
        data(i, "debt", i.debt, money(i), "balance_sheet", sheet_note(i, "debt")),
        data(i, "cash", i.cash, money(i), "balance_sheet", sheet_note(i, "cash")),
    )


def sheet_entry(i: CompanyInputs) -> dict[str, Any]:
    """The intermediates' ``balance_sheet``: the period of the newest balance sheet, its end (ISO),
    label and whether it is a quarter's; ``None`` without a sheet. The three firm-value routes
    carry it beside the debt and the cash they read from it."""
    sheet = i.sheet
    if sheet is None:
        return {"balance_sheet": None}
    found = {
        "period_end": sheet.period_end.isoformat(),
        "label": sheet.label,
        "quarterly": sheet.quarterly,
    }
    return {"balance_sheet": found}


def common_rules(policy: Policy, moat: Moat, terminal: float) -> tuple[TaggedInput, ...]:
    """The RULE inputs every route uses, with the route's terminal return."""
    return (
        rule(policy, "required_return", policy.required_return, "ratio"),
        rule(policy, "terminal_growth", policy.terminal_growth, "ratio"),
        rule(policy, "moat_class", None, "class", moat),
        rule(policy, "margin_of_safety", policy.margin_of_safety[moat], "ratio", f"{moat} moat"),
        rule(policy, "terminal_roic", terminal, "ratio", f"{moat} moat"),
    )


def data(
    i: CompanyInputs,
    name: str,
    value: float | None,
    unit: str,
    source: str | None = None,
    note: str | None = None,
) -> TaggedInput:
    """A DATA input citing ``provenance[source]`` (default: its own name), or the source
    "unknown"; an estimate when ``estimate_methods`` names it, else observed. Its note is
    ``note``, else the one ``notes`` holds for it. A value that is not a finite number is stored
    as ``None``."""
    provenance = i.provenance.get(source or name, _UNKNOWN)
    finite = None if value is None or not math.isfinite(value) else value
    method = i.estimate_methods.get(name)
    kind: Kind = "observed" if method is None else "estimate"
    note = i.notes.get(name) if note is None else note
    return TaggedInput(name, finite, unit, "DATA", kind, provenance, method, note)


def rule(
    policy: Policy, name: str, value: float | None, unit: str, note: str | None = None
) -> TaggedInput:
    """A RULE input citing the policy version."""
    provenance = Provenance(f"policy {policy.version}", None, None, None)
    return TaggedInput(name, value, unit, "RULE", "rule", provenance, note=note)


def present(flag: Flag | None) -> tuple[Flag, ...]:
    return () if flag is None else (flag,)


def nil(x: float | None) -> float:
    return 0.0 if x is None else x


def signed(x: float) -> str:
    """A rate as a percent to one decimal with the thousands grouped, a negative one with the
    minus sign."""
    return f"{x:,.1%}".replace("-", "−")
