"""The settings: the policy values the user may change, their ranges, and the overlay.

``SETTINGS`` names the forty policy values of spec 2026-11-04 8.2 in its order and groups, each
with the label, the plain sentence, the unit, the range and the effect the Settings page shows.
A dotted name (``universe.cap_floor_usd``, ``refresh.workers``) addresses a value inside the
file's ``[values.universe]`` or ``[values.refresh]`` table.

The user's values are an overlay of name to value, in the JSON form the API serves; ``default_of``
and ``value_of`` give a setting's file value and its value in a policy in that form.
``apply_overlay`` converts each value as ``load_policy`` converts the file's, replaces it in the
policy, sets the settings hash and checks every range; the policy's version stays the file's.
``check`` holds the ranges of 8.2 and the rules of 8.9 and runs at the end of ``load_policy``
too, so a file and an overlay fail alike, with the sentence ``"<name>[, <name>]: <rule>"`` the API
serves; a rule between two settings names both.

The settings hash (8.4) is the sha256 of the JSON, sorted by key, of the overlay's entries that
change a snapshot's figures: groups valuation and flags and ``validity_fallback_days``. The
universe and refresh settings change which companies are valued and how they are fetched, and
``aging_fraction`` is read when a row is shown, so none of them enters it.
"""

import copy
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any, Literal

from fairband.policy import (
    _MOATS,
    Policy,
    _by_moat,
    _cap_bands,
    _num,
    _pair,
    _texts,
    _whole,
)

Group = Literal["valuation", "flags", "validity", "universe", "refresh"]
Unit = Literal[
    "fraction",
    "points",
    "years",
    "times",
    "days",
    "seconds",
    "hours",
    "count",
    "usd",
    "symbols",
    "exchanges",
    "cap_bands",
]
Effect = Literal["revalue", "full", "run", "at once"]

EMPTY_SETTINGS_HASH = hashlib.sha256(b"{}").hexdigest()

_EXCHANGES = ("NYSE", "NASDAQ", "AMEX")
_CAP_BAND_LABELS = ("Mega", "Large", "Mid")
_SYMBOL = re.compile(r"[A-Z0-9.-]{1,10}")


@dataclass(frozen=True)
class Setting:
    """A policy value the user may change. ``range_text`` is the Range column of spec 8.2;
    ``effect`` says when a change is read; ``hashed`` says whether it enters the settings hash."""

    name: str
    group: Group
    label: str
    description: str
    unit: Unit
    effect: Effect
    range_text: str
    hashed: bool


# Each row: name, group, label, description, unit, effect, range, hashed.
SETTINGS: tuple[Setting, ...] = (
    # A. Valuation
    Setting(
        "required_return",
        "valuation",
        "Hurdle rate r",
        "The yearly return you require of a share; every value discounts its cash flows at it.",
        "fraction",
        "revalue",
        "4% to 20%, above g_T",
        True,
    ),
    Setting(
        "terminal_growth",
        "valuation",
        "Terminal growth g_T",
        "The rate a company grows at forever after its runway, in the terminal value.",
        "fraction",
        "revalue",
        "0% to 5%, below r",
        True,
    ),
    Setting(
        "runway_years",
        "valuation",
        "Runway, by moat (None, Narrow, Wide)",
        "The years the mature routes forecast before the terminal value; a wider moat runs longer.",
        "years",
        "revalue",
        "4 to 30 years each, non-decreasing None ≤ Narrow ≤ Wide",
        True,
    ),
    Setting(
        "margin_of_safety",
        "valuation",
        "Margin of safety, by moat",
        "The discount to the value that sets the buy level; the Narrow figure also sets the first "
        "designation edge.",
        "fraction",
        "revalue",
        "5% to 70% each, non-increasing None ≥ Narrow ≥ Wide",
        True,
    ),
    Setting(
        "fair_band",
        "valuation",
        "Fair band (low, high)",
        "The range of price to value in which a price reads Near.",
        "times",
        "revalue",
        "low 0.50 to 0.99, high 1.01 to 1.50",
        True,
    ),
    Setting(
        "trim_multiple",
        "valuation",
        "Trim multiple",
        "The price to value of the trim level; a price at or above it reads Well above.",
        "times",
        "revalue",
        "above the band's high, up to 3.0",
        True,
    ),
    Setting(
        "wide_terminal_roic_spread",
        "valuation",
        "Wide-moat terminal spread above r",
        "How far above r a Wide-moat company's terminal return may sit.",
        "points",
        "revalue",
        "0 to 10 points",
        True,
    ),
    Setting(
        "inflation_addition",
        "valuation",
        "Inflation addition to the belief",
        "The points for inflation added to the base-rate median growth to form the growth belief.",
        "points",
        "revalue",
        "0 to 5 points",
        True,
    ),
    Setting(
        "repricing_horizon_years",
        "valuation",
        "Repricing horizon",
        "The years over which the expected return assumes the price moves to the value.",
        "years",
        "revalue",
        "1 to 10 years",
        True,
    ),
    Setting(
        "roic_sensitivity",
        "valuation",
        "Return sensitivities (high, low)",
        "Two returns on capital at which the Mature Growth route values the company again, to "
        "show how the value moves.",
        "fraction",
        "revalue",
        "1% to 50% each, high above low",
        True,
    ),
    Setting(
        "fade_years",
        "valuation",
        "Fade years",
        "The years over which growth steps down evenly after the consensus years or the held rate.",
        "years",
        "revalue",
        "1 to 9",
        True,
    ),
    Setting(
        "high_growth_years",
        "valuation",
        "High-growth years",
        "The years the revenue-growth routes hold their growth rate before the fade.",
        "years",
        "revalue",
        "3 to 9; with the fade years, at most 10",
        True,
    ),
    Setting(
        "margin_convergence_year",
        "valuation",
        "Margin convergence year",
        "The year by which the revenue-growth routes' operating margin reaches the peers' target "
        "margin.",
        "years",
        "revalue",
        "1 to 10",
        True,
    ),
    Setting(
        "peer_min",
        "valuation",
        "Fewest peers for a target margin",
        "The fewest mature peers needed to set a target margin from their figures.",
        "count",
        "revalue",
        "1 to 10",
        True,
    ),
    Setting(
        "industry_peer_max",
        "valuation",
        "Industry peers on the fallback",
        "The most companies of the same industry read when the company's own peers are too few.",
        "count",
        "revalue",
        "the fewest peers to 50",
        True,
    ),
    Setting(
        "runoff_years",
        "valuation",
        "Run-off years",
        "The years a declining company's revenue runs off before its terminal value.",
        "years",
        "revalue",
        "5 to 20",
        True,
    ),
    Setting(
        "runoff_recovery",
        "valuation",
        "Run-off recovery",
        "The share of the capital a shrinking company releases that it recovers as cash.",
        "fraction",
        "revalue",
        "0% to 100%",
        True,
    ),
    Setting(
        "distress_sale_fraction",
        "valuation",
        "Distress-sale fraction",
        "The share of its firm value a distressed company would fetch in a forced sale.",
        "fraction",
        "revalue",
        "0% to 100%",
        True,
    ),
    Setting(
        "burn_cover_flag_years",
        "valuation",
        "Burn-cover flag years",
        "A start-up whose cash covers fewer years of its trailing cash burn than this is flagged.",
        "years",
        "revalue",
        "0.5 to 5",
        True,
    ),
    # B. Flags
    Setting(
        "analyst_min",
        "flags",
        "Fewest analysts behind a path year",
        "A consensus year with fewer analysts than this is flagged as thin; past year 3 it ends a "
        "Decline row's consensus.",
        "count",
        "revalue",
        "1 to 20",
        True,
    ),
    Setting(
        "nri_flag_share",
        "flags",
        "Non-recurring gap, share of EPS",
        "A gap this large between reported and recurring EPS, as a share of trailing EPS, is "
        "flagged.",
        "fraction",
        "revalue",
        "1% to 50%",
        True,
    ),
    Setting(
        "value_spread_flag",
        "flags",
        "Value spread",
        "A value that moves this much across its sensitivities is flagged.",
        "fraction",
        "revalue",
        "5% to 100%",
        True,
    ),
    Setting(
        "long_runway_growth_flag",
        "flags",
        "Long-runway growth",
        "Growth at or above this on the longest runway is flagged.",
        "fraction",
        "revalue",
        "1% to 30%",
        True,
    ),
    Setting(
        "margin_flag_ratio",
        "flags",
        "Margin flag: ratio to the median",
        "A trailing operating margin this many times its ten-year median is flagged.",
        "times",
        "revalue",
        "1.1 to 3.0",
        True,
    ),
    Setting(
        "margin_flag_above_high",
        "flags",
        "Margin flag: above the high",
        "A trailing operating margin this far above its ten-year high is flagged.",
        "fraction",
        "revalue",
        "1% to 50%",
        True,
    ),
    Setting(
        "margin_flag_min_years",
        "flags",
        "Margin flag: fewest years",
        "The fewest fiscal years with a margin that the margin flag needs.",
        "years",
        "revalue",
        "3 to 10",
        True,
    ),
    Setting(
        "capex_ocf_flag",
        "flags",
        "Heavy capex, share of operating cash flow",
        "Capital spending above this share of operating cash flow is flagged.",
        "fraction",
        "revalue",
        "10% to 100%",
        True,
    ),
    Setting(
        "equity_raise_share",
        "flags",
        "Equity raise, share of market cap",
        "Stock issued over the trailing year at or above this share of market cap is flagged as "
        "a raise.",
        "fraction",
        "revalue",
        "0.1% to 10%",
        True,
    ),
    # C. Validity
    Setting(
        "validity_fallback_days",
        "validity",
        "Validity fallback",
        "How long a value stays valid when no next earnings date is known.",
        "days",
        "revalue",
        "30 to 365",
        True,
    ),
    Setting(
        "aging_fraction",
        "validity",
        "Aging after",
        "The share of its validity window after which a value reads as aging.",
        "fraction",
        "at once",
        "10% to 95%",
        False,
    ),
    # D. Universe
    Setting(
        "universe.exchanges",
        "universe",
        "Exchanges",
        "The exchanges whose listings may enter the universe.",
        "exchanges",
        "full",
        "a non-empty subset of the three",
        False,
    ),
    Setting(
        "universe.cap_floor_usd",
        "universe",
        "Size floor",
        "The smallest market cap a company needs to enter the universe.",
        "usd",
        "full",
        "$100 m to $50 bn",
        False,
    ),
    Setting(
        "universe.cap_bands",
        "universe",
        "Cap bands (Mega, Large, Mid floors)",
        "The market caps at which the Mega, Large and Mid bands start.",
        "cap_bands",
        "full",
        "descending; the lowest equals the size floor",
        False,
    ),
    Setting(
        "universe.manual_admissions",
        "universe",
        "Admitted symbols",
        "Symbols admitted to the universe whatever their industry or name.",
        "symbols",
        "full",
        "a list of symbols",
        False,
    ),
    Setting(
        "universe.manual_exclusions",
        "universe",
        "Excluded symbols",
        "Symbols kept out of the universe whatever their size or industry.",
        "symbols",
        "full",
        "a list of symbols",
        False,
    ),
    # E. Refresh
    Setting(
        "refresh.workers",
        "refresh",
        "FMP workers",
        "How many companies a refresh fetches at the same time.",
        "count",
        "run",
        "1 to 64",
        False,
    ),
    Setting(
        "refresh.fmp_calls_per_minute",
        "refresh",
        "FMP calls a minute",
        "The pace of FMP calls, kept below the plan's limit.",
        "count",
        "run",
        "10 to 10,000",
        False,
    ),
    Setting(
        "refresh.rate_limit_hold_s",
        "refresh",
        "Hold after a 429",
        "How long every FMP call waits after FMP answers 429 (too many calls).",
        "seconds",
        "run",
        "1 to 3,600, finite",
        False,
    ),
    Setting(
        "refresh.reuse_hours",
        "refresh",
        "Reuse window, FMP",
        "A full refresh reuses FMP data fetched within this many hours; a scoped one fetches "
        "again.",
        "hours",
        "run",
        "0 to 720",
        False,
    ),
    Setting(
        "refresh.gf_reuse_days",
        "refresh",
        "Reuse window, GuruFocus",
        "A full refresh reuses GuruFocus data fetched within this many days; a scoped one "
        "fetches again.",
        "days",
        "run",
        "0 to 90",
        False,
    ),
)

_BY_NAME = {s.name: s for s in SETTINGS}


def setting(name: str) -> Setting:
    """The setting of that name; ``KeyError`` for a name that is not a setting."""
    return _BY_NAME[name]


def settings_hash(overlay: Mapping[str, Any]) -> str:
    """The sha256 of the sorted JSON of the overlay's hashed entries (spec 8.4)."""
    hashed = {k: v for k, v in overlay.items() if setting(k).hashed}
    return hashlib.sha256(json.dumps(hashed, sort_keys=True).encode()).hexdigest()


def default_of(name: str, base: Policy) -> Any:
    """The file's value for the name, in the JSON form the API serves: a number, a table by moat,
    or a list. Read from ``base.raw``, so an overlaid policy still gives the file's value."""
    setting(name)
    group, _, field = name.rpartition(".")
    values = base.raw["values"]
    value = values[group]["value"][field] if group else values[field]["value"]
    return copy.deepcopy(value)


def value_of(name: str, policy: Policy) -> Any:
    """The setting's value in ``policy``, in the JSON form the API serves and the overlay stores:
    tuples become lists, a table by moat a dict. ``KeyError`` for a name that is not a setting."""
    setting(name)
    group, _, field = name.rpartition(".")
    holder = getattr(policy, group) if group else policy
    return json.loads(json.dumps(getattr(holder, field), allow_nan=False))


def apply_overlay(base: Policy, overlay: Mapping[str, Any]) -> Policy:
    """``base`` with each overlay value converted and in place, the settings hash set, and every
    range checked. A value that is not a setting, or does not convert, raises
    ``ValueError("<name>: <reason>")``.

    A size floor changed without the cap bands carries the lowest band's floor with it, since the
    lowest band must equal the size floor (spec 8.9)."""
    top: dict[str, Any] = {}
    nested: dict[str, dict[str, Any]] = {"universe": {}, "refresh": {}}
    for name, value in overlay.items():
        if name not in _BY_NAME:
            raise ValueError(f"{name}: not a setting")
        try:
            converted = _converted(_BY_NAME[name], value)
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(f"{name}: {e}") from e
        group, _, field = name.rpartition(".")
        (nested[group] if group else top)[field] = converted
    universe = nested["universe"]
    if "cap_floor_usd" in universe and "cap_bands" not in universe and base.universe.cap_bands:
        *upper, (_, label) = base.universe.cap_bands
        universe["cap_bands"] = (*upper, (universe["cap_floor_usd"], label))
    policy = replace(
        base,
        **top,
        universe=replace(base.universe, **universe),
        refresh=replace(base.refresh, **nested["refresh"]),
        settings_hash=settings_hash(overlay),
    )
    check(policy)
    return policy


def _converted(s: Setting, value: Any) -> Any:
    """The value in the policy's form, by the loader's converters."""
    match s.name:
        case "runway_years":
            return _by_moat(value, _whole)
        case "margin_of_safety":
            return _by_moat(value, _num)
        case "fair_band" | "roic_sensitivity":
            return _pair(value)
        case "burn_cover_flag_years":
            return _num(value)
    match s.unit:
        case "years" | "days" | "count" | "hours":
            return _whole(value)
        case "symbols":
            return tuple(exchange_symbol(text) for text in _texts(value))
        case "exchanges":
            return _texts(value)
        case "cap_bands":
            return _cap_bands(value)
        case _:  # fraction, points, times, usd, seconds
            return _num(value)


def exchange_symbol(text: str) -> str:
    """The text upper-cased, as a symbol in the exchange form the store keeps (``BRK.B``);
    ``ValueError("'<text>' is not a symbol")`` when it is not one."""
    symbol = text.upper()
    if not _SYMBOL.fullmatch(symbol):
        raise ValueError(f"{text!r} is not a symbol")
    return symbol


def check(policy: Policy) -> None:
    """Every range of spec 8.2 and every rule of 8.9, in the order of 8.2; the first that fails
    raises ``ValueError("<name>: <rule>")``. Ranges are inclusive, and a NaN or an infinity is
    outside every one. A rule between two settings names both, in the order of 8.2 and joined by
    a comma, so r against g_T reads ``"required_return, terminal_growth: …"``; the Settings page
    then stands the sentence beside the one the user changed (B-75). Then the ranges of the two
    values policy v10 adds and the three v11 adds, which are not settings and so are only ever
    the file's (spec 2026-11-09, section 11; spec 2026-11-10, section 9)."""
    p, u, f = policy, policy.universe, policy.refresh
    # A. Valuation
    if not 0.04 <= p.required_return <= 0.20:
        raise ValueError("required_return: must be from 4% to 20%")
    if not p.terminal_growth < p.required_return:
        raise ValueError("required_return, terminal_growth: g_T must be below r")
    if not 0 <= p.terminal_growth <= 0.05:
        raise ValueError("terminal_growth: must be from 0% to 5%")
    runway = [p.runway_years[m] for m in _MOATS]
    if not all(4 <= n <= 30 for n in runway):
        raise ValueError("runway_years: each must be from 4 to 30 years")
    if not runway[0] <= runway[1] <= runway[2]:
        raise ValueError("runway_years: None, Narrow, Wide must not decrease")
    safety = [p.margin_of_safety[m] for m in _MOATS]
    if not all(0.05 <= m <= 0.70 for m in safety):
        raise ValueError("margin_of_safety: each must be from 5% to 70%")
    if not safety[0] >= safety[1] >= safety[2]:
        raise ValueError("margin_of_safety: None, Narrow, Wide must not increase")
    low, high = p.fair_band
    if not 0.50 <= low <= 0.99:
        raise ValueError("fair_band: the low must be from 0.50 to 0.99")
    if not low > 1 - p.margin_of_safety["Narrow"]:  # the derived edges ascend: e1 below e2
        raise ValueError(
            "margin_of_safety, fair_band: the band's low must be above 1 − the Narrow margin"
            " of safety"
        )
    if not 1.01 <= high <= 1.50:
        raise ValueError("fair_band: the high must be from 1.01 to 1.50")
    if not p.trim_multiple <= 3.0:
        raise ValueError("trim_multiple: must be up to 3.0")
    if not high < p.trim_multiple:
        raise ValueError(
            "fair_band, trim_multiple: the trim multiple must be above the band's high"
        )
    if not 0 <= p.wide_terminal_roic_spread <= 0.10:
        raise ValueError("wide_terminal_roic_spread: must be from 0 to 10 points")
    if not 0 <= p.inflation_addition <= 0.05:
        raise ValueError("inflation_addition: must be from 0 to 5 points")
    if not 1 <= p.repricing_horizon_years <= 10:
        raise ValueError("repricing_horizon_years: must be from 1 to 10 years")
    s_high, s_low = p.roic_sensitivity
    if not (0.01 <= s_high <= 0.50 and 0.01 <= s_low <= 0.50):
        raise ValueError("roic_sensitivity: each must be from 1% to 50%")
    if not s_high > s_low:
        raise ValueError("roic_sensitivity: the high must be above the low")
    if not 1 <= p.fade_years <= 9:
        raise ValueError("fade_years: must be from 1 to 9")
    if not 3 <= p.high_growth_years <= 9:
        raise ValueError("high_growth_years: must be from 3 to 9")
    if not p.high_growth_years + p.fade_years <= 10:
        raise ValueError("fade_years, high_growth_years: together at most 10")
    if not 1 <= p.margin_convergence_year <= 10:
        raise ValueError("margin_convergence_year: must be from 1 to 10")
    if not 1 <= p.peer_min <= 10:
        raise ValueError("peer_min: must be from 1 to 10")
    if not 1 <= p.industry_peer_max <= 50:
        raise ValueError("industry_peer_max: must be from 1 to 50")
    if not p.peer_min <= p.industry_peer_max:
        raise ValueError(
            "peer_min, industry_peer_max: the industry peers must be at least the fewest peers"
        )
    if not 5 <= p.runoff_years <= 20:
        raise ValueError("runoff_years: must be from 5 to 20")
    if not 0 <= p.runoff_recovery <= 1:
        raise ValueError("runoff_recovery: must be from 0% to 100%")
    if not 0 <= p.distress_sale_fraction <= 1:
        raise ValueError("distress_sale_fraction: must be from 0% to 100%")
    if not 0.5 <= p.burn_cover_flag_years <= 5:
        raise ValueError("burn_cover_flag_years: must be from 0.5 to 5")
    # B. Flags
    if not 1 <= p.analyst_min <= 20:
        raise ValueError("analyst_min: must be from 1 to 20")
    if not 0.01 <= p.nri_flag_share <= 0.50:
        raise ValueError("nri_flag_share: must be from 1% to 50%")
    if not 0.05 <= p.value_spread_flag <= 1:
        raise ValueError("value_spread_flag: must be from 5% to 100%")
    if not 0.01 <= p.long_runway_growth_flag <= 0.30:
        raise ValueError("long_runway_growth_flag: must be from 1% to 30%")
    if not 1.1 <= p.margin_flag_ratio <= 3.0:
        raise ValueError("margin_flag_ratio: must be from 1.1 to 3.0")
    if not 0.01 <= p.margin_flag_above_high <= 0.50:
        raise ValueError("margin_flag_above_high: must be from 1% to 50%")
    if not 3 <= p.margin_flag_min_years <= 10:
        raise ValueError("margin_flag_min_years: must be from 3 to 10")
    if not 0.10 <= p.capex_ocf_flag <= 1:
        raise ValueError("capex_ocf_flag: must be from 10% to 100%")
    if not 0.001 <= p.equity_raise_share <= 0.10:
        raise ValueError("equity_raise_share: must be from 0.1% to 10%")
    # C. Validity
    if not 30 <= p.validity_fallback_days <= 365:
        raise ValueError("validity_fallback_days: must be from 30 to 365")
    if not 0.10 <= p.aging_fraction <= 0.95:
        raise ValueError("aging_fraction: must be from 10% to 95%")
    # D. Universe
    exchanges = set(u.exchanges)
    if not (exchanges and exchanges <= set(_EXCHANGES) and len(exchanges) == len(u.exchanges)):
        raise ValueError("universe.exchanges: must be a non-empty subset of NYSE, NASDAQ, AMEX")
    if not 1e8 <= u.cap_floor_usd <= 5e10:
        raise ValueError("universe.cap_floor_usd: must be from $100 m to $50 bn")
    if tuple(label for _, label in u.cap_bands) != _CAP_BAND_LABELS:
        raise ValueError("universe.cap_bands: must be the Mega, Large and Mid floors")
    floors = [floor for floor, _ in u.cap_bands]
    if not all(a > b for a, b in pairwise(floors)):
        raise ValueError("universe.cap_bands: the floors must descend")
    if floors[-1] != u.cap_floor_usd:
        raise ValueError(
            "universe.cap_floor_usd, universe.cap_bands: the lowest band must equal the size floor"
        )
    for name, symbols in (
        ("universe.manual_admissions", u.manual_admissions),
        ("universe.manual_exclusions", u.manual_exclusions),
    ):
        for symbol in symbols:
            if not _SYMBOL.fullmatch(symbol):
                raise ValueError(f"{name}: {symbol!r} is not a symbol")
    # E. Refresh
    if not 1 <= f.workers <= 64:
        raise ValueError("refresh.workers: must be from 1 to 64")
    if not 10 <= f.fmp_calls_per_minute <= 10_000:
        raise ValueError("refresh.fmp_calls_per_minute: must be from 10 to 10000")
    if not 1 <= f.rate_limit_hold_s <= 3600:
        raise ValueError("refresh.rate_limit_hold_s: must be from 1 to 3600")
    if not 0 <= f.reuse_hours <= 720:
        raise ValueError("refresh.reuse_hours: must be from 0 to 720")
    if not 0 <= f.gf_reuse_days <= 90:
        raise ValueError("refresh.gf_reuse_days: must be from 0 to 90")
    # Policy values that are not settings
    if not 0 <= p.step_series_gap_max <= 0.5:
        raise ValueError("step_series_gap_max: must be from 0 to 50 points")
    if not 0 <= p.split_implied_count_tolerance <= 0.5:
        raise ValueError("split_implied_count_tolerance: must be from 0% to 50%")
    if not 0 < p.inflation_max < 1:
        raise ValueError("inflation_max: must be above 0 and below 1")
    if not p.fx_stale_days >= 1:
        raise ValueError("fx_stale_days: must be at least 1 day")
    if not f.fx_history_years >= 1:
        raise ValueError("refresh.fx_history_years: must be at least 1 year")
