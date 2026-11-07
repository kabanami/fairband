"""Overrides: the inputs an agent may change, the rules an override must pass, and the engine's
own reading of each input (spec 2026-11-06 Tier 2, 10.1 to 10.3; ``method.md`` 14).

An override changes one tagged input. ``TAGS`` names the sixteen inputs, the routes that read
each, its unit and, for the two word inputs, its words; the numeric ranges are the policy's
``override_ranges``, the ends included but the two NTM anchors' lower end, 0, which an anchor
must be above (``TagSpec.low_open``). ``LABELS`` names each input's bridge line in a reader's
words. ``check_override`` applies the rules in this order and answers with the first one broken:
a locked input (``LOCKED``); a tag that is not an input; a route that does not read the tag; a
value outside its words or its range, or a lasting override of a period-tied input; no evidence,
an NTM anchor (``earnings.ntm``, ``revenue.ntm``) without a guidance record among its evidence,
or a belief or held rate above the sales class's 90th percentile without a filing or a
transcript (when the policy's ``override_primary_evidence_above_p90`` holds). The rule reads the
evidence's kinds alone: the records an NTM anchor cites must hold a gaap record of its metric for
a fiscal year (``ANCHOR_METRICS``, ``anchor_misfit``), which the override route checks on the
records before the rules, since it reads them. A passing override is ``("applied", "")``; a
refused one names its state and a sentence the agent can act on.
``check_input`` applies the first four alone, the fourth without the lifetime: the rules on the
input and its value, which a sensitivity reading's values meet and no others, since a reading
changes no input (``method.md`` 14.8).

The routes read an override through ``route_steps.chosen``; ``route.value_company`` takes the
applied ones as a mapping by tag. ``current_reading`` is the engine's reading of an input from a
result's intermediates, ``None`` where the result holds none: the bridge's old value and the
value a period-tied override corrected. A balance line reads the reported figure the result
cites, ``None`` when no line is on file (the bridge then counts it as nil) or the result cites
none; the runway return reads ``None`` with the charge off. The engine finds no cycle gap: a
mature route writes ``cycle_gap`` into its intermediates only under an override, so a Mature
Growth or Mature Stable result without one reads 0.0 (a refusal, the route its phase takes). The
NTM earnings read the anchor the Mature Growth route stored, before the cycle gap came off it;
the NTM revenue reads the year one the revenue-growth or Decline route stored, none on a Decline
row with no usable consensus. An override at the engine's reading moves nothing.

``INPUT_OF`` names the route's own entry each tag stands for in a result's inputs: a result
valued under an override cites the JUDGMENT entry in its place, so no DATA or RULE entry carries
the agent's figure under the vendor's or the policy's provenance.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TypeIs, cast, get_args

from fairband.engine.types import Phase, Route, ValuationResult
from fairband.policy import Policy

OverrideTag = Literal[
    "phase",
    "earnings.ntm",
    "revenue.ntm",
    "growth.belief",
    "path.hold",
    "path.step_2",
    "path.step_3",
    "moat.class",
    "margin.target",
    "capital.sales_to_capital",
    "return.runway",
    "earnings.nri_gap",
    "earnings.cycle_gap",
    "decline.rate",
    "balance.debt",
    "balance.cash",
]
# The bridge's order, the method's step order (spec 10.4).
BRIDGE_ORDER: tuple[OverrideTag, ...] = (
    "phase",
    "earnings.ntm",
    "revenue.ntm",
    "path.step_2",
    "path.step_3",
    "path.hold",
    "growth.belief",
    "earnings.nri_gap",
    "earnings.cycle_gap",
    "margin.target",
    "capital.sales_to_capital",
    "return.runway",
    "decline.rate",
    "moat.class",
    "balance.debt",
    "balance.cash",
)
Lifetime = Literal["lasting", "period-tied"]
State = Literal[
    "applied",
    "refused-locked",
    "refused-evidence",
    "refused-unit",
    "refused-not-input",
    "refused-route",
    "dropped",
]
# The ledger's principals (``store.ledger.Principal``), restated: the engine imports no store.
Principal = Literal["owner", "agent", "system"]


@dataclass(frozen=True)
class TagSpec:
    """An input an agent may override: the routes that read it, the unit the engine reads it in,
    its words (``None`` for a number, whose range is the policy's), whether only a period-tied
    override may change it, and whether its range's lower end is excluded: an NTM anchor must be
    above 0, as the route's own positive-anchor rule asks of the consensus."""

    tag: OverrideTag
    routes: frozenset[Route]
    unit: str
    words: tuple[str, ...] | None
    period_tied_only: bool
    low_open: bool


@dataclass(frozen=True)
class Override:
    """An applied override as the engine reads it: the stored id (``None`` before it is stored),
    the input, the new value, who made it and when, and why."""

    id: int | None
    tag: OverrideTag
    value: float | str
    principal: Principal
    actor: str | None
    at: datetime
    reason: str


Overrides = Mapping[OverrideTag, Override]

_ALL: frozenset[Route] = frozenset(get_args(Route))
_MATURE: frozenset[Route] = frozenset({"mature-growth", "mature-stable"})
_GROWTH: frozenset[Route] = frozenset({"revenue-growth"})
_BALANCE: frozenset[Route] = frozenset({"revenue-growth", "decline", "start-up"})
# The routes whose value reads a consensus step; the Mature Stable value reads none.
_STEPS: frozenset[Route] = frozenset({"mature-growth", "revenue-growth", "decline"})
_PHASES: tuple[str, ...] = get_args(Phase)
_MOATS = ("None", "Narrow", "Wide")


def _spec(
    tag: OverrideTag,
    routes: frozenset[Route],
    unit: str,
    words: tuple[str, ...] | None = None,
    period_tied_only: bool = False,
    low_open: bool = False,
) -> TagSpec:
    return TagSpec(tag, routes, unit, words, period_tied_only, low_open)


TAGS: dict[OverrideTag, TagSpec] = {
    s.tag: s
    for s in (
        _spec("phase", _ALL, "phase", _PHASES),
        _spec("earnings.ntm", frozenset({"mature-growth"}), "USD a share", low_open=True),
        _spec("revenue.ntm", _GROWTH | {"decline"}, "USD", low_open=True),
        _spec("growth.belief", frozenset({"mature-growth"}), "ratio"),
        _spec("path.hold", _GROWTH, "ratio"),
        _spec("path.step_2", _STEPS, "ratio"),
        _spec("path.step_3", _STEPS, "ratio"),
        _spec("moat.class", _MATURE | _GROWTH | {"start-up"}, "class", _MOATS),
        _spec("margin.target", _GROWTH | {"start-up"}, "ratio"),
        _spec("capital.sales_to_capital", _GROWTH | {"decline"}, "multiple"),
        _spec("return.runway", _MATURE, "ratio"),
        _spec("earnings.nri_gap", _MATURE, "USD a share"),
        _spec("earnings.cycle_gap", _MATURE, "USD a share"),
        _spec("decline.rate", frozenset({"decline"}), "ratio"),
        _spec("balance.debt", _BALANCE, "USD", period_tied_only=True),
        _spec("balance.cash", _BALANCE, "USD", period_tied_only=True),
    )
}

# Each input's line on the bridge, in a reader's words: the cycle gap reads as a cycle judgment,
# not as a one-time item.
LABELS: dict[OverrideTag, str] = {
    "phase": "phase",
    "earnings.ntm": "NTM earnings",
    "revenue.ntm": "NTM revenue",
    "growth.belief": "belief",
    "path.hold": "held rate",
    "path.step_2": "consensus step 2",
    "path.step_3": "consensus step 3",
    "moat.class": "moat",
    "margin.target": "target margin",
    "capital.sales_to_capital": "sales to capital",
    "return.runway": "runway return",
    "earnings.nri_gap": "non-recurring gap",
    "earnings.cycle_gap": "mid-cycle earnings",
    "decline.rate": "decline rate",
    "balance.debt": "debt",
    "balance.cash": "cash",
}

# The route's own entry in a result's inputs that each tag stands for. The two gaps stand for
# none: a route cites the gap found and the NTM consensus as found as data. An NTM anchor stands
# for its consensus figure's entry; Mature Growth's NTM net income entry keeps the consensus.
INPUT_OF: dict[OverrideTag, str] = {
    "earnings.ntm": "ntm_eps",
    "revenue.ntm": "ntm_revenue",
    "growth.belief": "belief",
    "path.step_2": "path_step_2",
    "path.step_3": "path_step_3",
    "moat.class": "moat_class",
    "margin.target": "target_margin",
    "capital.sales_to_capital": "sales_to_capital",
    "return.runway": "runway_return",
    "balance.debt": "debt",
    "balance.cash": "cash",
}

_REPORTED = ("price", "shares_diluted", "market_cap", "revenue", "operating_income", "eps")
LOCKED: dict[str, str] = {
    "required_return": "r is a locked input: the hurdle rate",
    "terminal_growth": "g_T is a locked input: the terminal growth ceiling",
    "runway_years": "the runway years are a locked input: the moat sets them",
    "fade_years": "the fade years are a locked input: a policy value",
    "margin_of_safety": "the margin of safety is a locked input: the moat sets it",
    "fair_band": "the fair band is a locked input: a policy value",
    "trim_multiple": "the trim multiple is a locked input: a policy value",
    "terminal_return": "the terminal return follows the moat",
    "deciles": "the deciles are a locked input: the universe's",
    "growth_word": "the growth word is a locked input: the deciles set it",
    **{name: f"{name} is reported data" for name in _REPORTED},
}

_ROUTE_NAMES: dict[Route, str] = {
    "mature-growth": "Mature Growth",
    "mature-stable": "Mature Stable",
    "revenue-growth": "revenue-growth",
    "decline": "Decline",
    "start-up": "Start-up",
}
_PRIMARY = frozenset({"filing", "transcript"})
_ABOVE_P90: dict[str, str] = {"growth.belief": "a belief", "path.hold": "a held rate"}
# The anchors a clear guidance may replace: an override of one cites a guidance record.
_NTM_ANCHORS = frozenset({"earnings.ntm", "revenue.ntm"})
NO_GUIDANCE = "an NTM anchor override needs a guidance record among its evidence"
# The metric of the guidance record an NTM anchor reads, a gaap record for a fiscal year: the
# reported basis, and a full year, the only figures that may stand in for the consensus.
ANCHOR_METRICS: dict[str, str] = {"earnings.ntm": "eps", "revenue.ntm": "revenue"}
# The policy's stand-in for a range with no upper bound (10^15 dollars: the balance corrections
# and the NTM revenue); a refusal names such a range by its lower end alone.
NO_BOUND = 1e15


_ROUTE_OF: dict[Phase, Route] = {
    "Start-up": "start-up",
    "Young Growth": "revenue-growth",
    "High Growth": "revenue-growth",
    "Mature Growth": "mature-growth",
    "Mature Stable": "mature-stable",
    "Decline": "decline",
}


def route_of(phase: Phase) -> Route:
    """The route a phase takes: High Growth and Young Growth the revenue-growth route, every other
    phase its own."""
    return _ROUTE_OF[phase]


def anchor_misfit(tag: str) -> str:
    """The refusal of an override of the NTM anchor ``tag`` whose guidance records hold no gaap
    record of the anchor's metric for a fiscal year (``ANCHOR_METRICS``)."""
    metric = ANCHOR_METRICS[tag]
    return f"an NTM anchor override needs a gaap guidance record of {metric} for a fiscal year"


def check_override(
    tag: str,
    value: float | str,
    route: Route,
    policy: Policy,
    evidence_kinds: Sequence[str],
    lifetime: Lifetime,
    cap: float | None,
) -> tuple[State, str]:
    """``("applied", "")``, or the first rule ``value`` breaks for ``tag`` on ``route``, in the
    order of the module's docstring, with its sentence. ``cap`` is the sales class's 90th
    percentile, ``None`` when the row has none."""
    state, message = check_input(tag, value, route, policy)
    if state != "applied":
        return state, message
    if TAGS[cast(OverrideTag, tag)].period_tied_only and lifetime == "lasting":
        return "refused-unit", f"{tag} is period-tied only"
    if not evidence_kinds:
        return "refused-evidence", "an override needs evidence"
    if tag in _NTM_ANCHORS and "guidance" not in evidence_kinds:
        return "refused-evidence", NO_GUIDANCE
    if (
        tag in _ABOVE_P90
        and cap is not None
        and policy.override_primary_evidence_above_p90
        and _number(value)
        and value > cap
        and not _PRIMARY & set(evidence_kinds)
    ):
        return "refused-evidence", (
            f"{_ABOVE_P90[tag]} above the base rate's 90th percentile needs a filing or a "
            "transcript"
        )
    return "applied", ""


def check_input(tag: str, value: float | str, route: Route, policy: Policy) -> tuple[State, str]:
    """``("applied", "")``, or the first of the input's own rules ``value`` breaks for ``tag`` on
    ``route``, with its sentence: a locked input, a tag that is not an input, a route that does
    not read it, a value outside its words or its range."""
    if tag in LOCKED:
        return "refused-locked", LOCKED[tag]
    if tag not in TAGS:
        return "refused-not-input", f"{tag} is not an input"
    spec = TAGS[tag]
    if route not in spec.routes:
        return "refused-route", f"the {_ROUTE_NAMES[route]} route does not read {tag}"
    unit = _unit_refusal(spec, value, policy)
    if unit is not None:
        return "refused-unit", unit
    return "applied", ""


def _unit_refusal(spec: TagSpec, value: float | str, policy: Policy) -> str | None:
    """Why ``value`` is not one the input takes, or ``None``: a word outside its words, a number
    outside its range (the ends included)."""
    if spec.words is not None:
        if not isinstance(value, str) or value not in spec.words:
            return f"{spec.tag} takes {', '.join(spec.words[:-1])} or {spec.words[-1]}"
        return None
    low, high = policy.override_ranges[spec.tag]
    if not _number(value) or not _within(value, low, high, spec.low_open):
        return f"{spec.tag} takes {range_text(low, high, spec.unit, low_open=spec.low_open)}"
    return None


def _within(x: float, low: float, high: float, low_open: bool) -> bool:
    """Whether ``x`` lies in the range, its upper end included and its lower end unless
    ``low_open``."""
    return (low < x if low_open else low <= x) and x <= high


def _number(value: object) -> TypeIs[float]:
    return isinstance(value, int | float) and not isinstance(value, bool)


def range_text(low: float, high: float, unit: str, *, low_open: bool = False) -> str:
    """A range in the input's unit: percents for a ratio, dollars for money (a share for the two
    gaps and the NTM EPS), the figures for a multiple; a negative end with the minus sign, and
    "above" before a lower end the range excludes. An upper end of ``NO_BOUND`` or more stands for
    no bound and is not written: the range names its lower end alone, "$0 or more", or "above $0"
    when it excludes it. The override's refusal and the secondary valuation's driver refusals
    write their ranges with it."""
    per = " a share" if unit == "USD a share" else ""
    if high >= NO_BOUND:
        bound = f"above {_end(low, unit)}" if low_open else f"{_end(low, unit)} or more"
        return f"{bound}{per}"
    above = "above " if low_open else ""
    return f"{above}{_end(low, unit)} to {_end(high, unit)}{per}"


def _end(x: float, unit: str) -> str:
    """One end of a range in the input's unit (``range_text``)."""
    if unit == "ratio":
        return f"{_signed(x * 100)}%"
    if unit in ("USD", "USD a share"):
        return _dollars(x)
    return _signed(x)


def _signed(x: float) -> str:
    return f"{'−' if x < 0 else ''}{abs(x):g}"


def _dollars(x: float) -> str:
    return f"{'−' if x < 0 else ''}${abs(x):,.0f}"


def current_reading(result: ValuationResult, tag: OverrideTag) -> float | str | None:
    """The engine's reading of ``tag``'s input on ``result``, from its intermediates; ``None``
    where it holds none."""
    found = _reading(result, tag)
    return found if isinstance(found, int | float | str) and not isinstance(found, bool) else None


def _reading(result: ValuationResult, tag: OverrideTag) -> Any:
    im = result.intermediates
    match tag:
        case "phase":
            return result.phase.phase
        case "earnings.ntm":
            # the anchor before the cycle gap came off it: the figure an override stands for
            ntm_eps = _at(im, "anchor", "ntm_eps")
            return None if ntm_eps is None else ntm_eps + im.get("cycle_gap", 0.0)
        case "revenue.ntm":
            # year one as the route stored it, none on a Decline row with no usable consensus
            return _first(
                im.get("ntm_revenue"),
                _at(im, "revenue_path", "ntm_revenue"),
                _at(im, "runoff_path", "ntm_revenue"),
            )
        case "growth.belief":
            return _at(im, "belief", "rate")
        case "path.hold":
            # the held rate: the hold when one is set (the cap, or an agent's), else g_3 resolved
            if "revenue_path" not in im:
                return None
            return _first(_at(im, "revenue_path", "hold"), _at(im, "path_steps", 1))
        case "path.step_2" | "path.step_3":
            k = 0 if tag == "path.step_2" else 1
            for steps in ("path_steps",), ("revenue_path", "steps"), ("runoff_path", "steps"):
                if _at(im, *steps) is not None:
                    return _at(im, *steps, k)
            return None
        case "moat.class":
            return im.get("moat", _rule_note(result, "moat_class"))
        case "margin.target":
            return _first(
                _at(im, "target_margin", "value"), _at(im, "requirement", "target_margin", "value")
            )
        case "capital.sales_to_capital":
            return _first(
                _at(im, "sales_to_capital", "value"),
                _at(im, "requirement", "sales_to_capital", "value"),
            )
        case "return.runway":
            # with the charge off the value is the terminal return, which charges nothing
            if _at(im, "runway_return", "used") == "off":
                return None
            return _at(im, "runway_return", "value")
        case "earnings.nri_gap":
            return im.get("nri_gap")
        case "earnings.cycle_gap":
            # written only under an override; the engine's own reading is nil
            return im.get("cycle_gap", 0.0) if _route(result) in TAGS[tag].routes else None
        case "decline.rate":
            return _at(im, "runoff_path", "d")
        case "balance.debt" | "balance.cash":
            return _balance(result, tag.removeprefix("balance."))


def _route(result: ValuationResult) -> Route | None:
    """The result's route; for a refusal, the route its phase takes, ``None`` without a phase."""
    if result.route is not None:
        return result.route
    phase = result.phase.phase
    return None if phase is None else route_of(phase)


def _balance(result: ValuationResult, name: str) -> Any:
    """The reported line the result cites, ``None`` when no line is on file (the bridge counts it
    as nil); on a result that cites an override in its place, the override's figure. ``None`` on
    a result that cites neither, a row refused before its route cites the line: its
    intermediates hold the nil the bridge counts, not the line."""
    for x in result.inputs:
        if (
            x.name == name
            and x.tag == "DATA"
            or x.name == f"balance.{name}"
            and x.tag == "JUDGMENT"
        ):
            return x.value
    return None


def _rule_note(result: ValuationResult, name: str) -> str | None:
    """The note of the RULE input ``name``: a Start-up row's moat class, which its intermediates
    do not hold."""
    return next((x.note for x in result.inputs if x.name == name and x.tag == "RULE"), None)


def _first(*xs: Any) -> Any:
    return next((x for x in xs if x is not None), None)


def _at(x: Any, *path: str | int) -> Any:
    """The value at ``path`` through dicts and lists; ``None`` where a step is absent."""
    for key in path:
        if isinstance(key, str) and isinstance(x, dict):
            x = x.get(key)
        elif isinstance(key, int) and isinstance(x, list) and key < len(x):
            x = x[key]
        else:
            return None
    return x
