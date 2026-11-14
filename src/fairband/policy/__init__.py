"""The policy: every valuation constant, in one versioned TOML file with a source line per value.

``load_policy`` reads ``fairband-policy-v16.toml`` from the package unless given a path. Each
``[values.<name>]`` table holds ``value`` and ``source``; a missing or malformed one raises
``ValueError`` naming the section. ``Policy.hash`` is the sha256 of the file bytes, so a result can
cite the exact policy it was computed under. Code elsewhere holds no valuation constant. The v1
to v15 files stay in the package byte for byte, because the snapshots valued under them cite their
hashes.

The designation edges and the Wide moat's terminal return cap are derived, not read (spec
2026-11-04 8.3): ``Policy.designation_edges`` and ``Policy.wide_terminal_roic_cap`` are
properties. The file's values are the defaults the user's settings overlay
(``fairband.policy.settings``); ``load_policy`` checks every setting's range as the overlay does,
so a file outside them fails at load with the setting's name.

The six values v8 adds for the agents and the one v9 adds (spec 2026-11-06 Tier 2, section 19)
are not settings: the override ranges (v9 adds the cycle gap's), the evidence rule above the 90th
percentile, the secondary valuation's bounds, its driver ranges (v9) and the stance words. An
override range or a driver range whose low is not below its high fails at load. The two values v10
adds (spec 2026-11-09, section 11), the step-series gap and the split implied-count tolerance, are
not settings either, nor are the two override ranges it adds, the outside value's and the diluted
count's; either value outside 0 to 0.5 fails at load. Nor are the three values v11 adds (spec
2026-11-10, section 9): the inflation bound, which fails at load outside 0 to 1, the ends
excluded, and the stale-rate bound and the rate history depth (``refresh.fx_history_years``),
which fail below 1. The inflation table they work beside is a packaged table of its own
(``fairband.policy.inflation``), as the tax table is. Nor is the value v12 adds (``method.md`` 4.6
rule 5), the cap on the runway return read on capital without goodwill and intangibles: it fails
at load unless above 20%, the highest required return a setting allows, and at most 100%. Nor
are the four values v13 adds (spec 2026-11-13, sections 7.1 and 8): the share of the street EPS
at which stock pay is material and the share of the statutory tax rate, each failing at load
outside 0 to 1; the multiple of the stock pay a share, failing at or below 0; and the
share-count band, whose low must be below 1 and whose high above 1. Nor is the trailing stock
pay's override range v13 adds, nor the runway return's, which v13 widens to 500%. v14 adds no
value, only the minority interest's override range (spec 2026-11-13, sections 13 and 14). Nor is
the value v15 adds (spec 2026-11-13, section 12.5), the multiple by which a quarter's minority
interest differs from the newest annual sheet's before the note ``sheet-shift`` names it: it
fails at load at or below 1. v16 adds four override ranges (spec 2026-11-14,
section 10): the committed shares', the one-time item's in the NTM consensus and the two revenue
steps'.
Nor is the value v16 gains with the thin rule (spec 2026-11-14, section 6.2, as narrowed on
2026-11-15), the size above which a revenue step on too few revenue analysts is not read: it
fails at load below 0, or at a NaN or an infinity.

``in_currency`` restates the policy for a company in another currency (spec 2026-11-10 7.3): the
five nominal USD rates, the required return, the terminal growth, the inflation addition, the cap
on the return without goodwill and each Base Rate Book class's ``sales_p90_5y``, by the
currency's inflation differential d, each
(1 + rate) × (1 + d) − 1; every rate derived from them (the Wide moat's terminal return cap)
follows. The flag thresholds and the margin bounds are not restated, and the version, the hash
and the settings hash stay: the restated policy is the same policy read in another currency.
"""

import hashlib
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, replace
from importlib import resources
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal

Moat = Literal["Wide", "Narrow", "None"]

_POLICY_FILE = "fairband-policy-v16.toml"
_MOATS: tuple[Moat, ...] = ("None", "Narrow", "Wide")


@dataclass(frozen=True)
class BaseRateClass:
    """A Base Rate Book sales class: upper bound in USD millions (2015 dollars), median CAGR,
    label, and the 90th-percentile five-year sales CAGR that caps the revenue-growth route's held
    rate."""

    upper_musd: float
    median: float
    label: str
    sales_p90_5y: float


@dataclass(frozen=True)
class RatingRow:
    """A synthetic rating row: an interest coverage at or above ``coverage_min`` and below the next
    row's takes ``rating``. The first row's ``coverage_min`` is minus infinity."""

    coverage_min: float
    rating: str


@dataclass(frozen=True)
class UniversePolicy:
    exchanges: tuple[str, ...]
    cap_floor_usd: float
    cap_bands: tuple[tuple[float, str], ...]
    excluded_industries: tuple[str, ...]
    symbol_exclude_patterns: tuple[str, ...]
    name_exclude_patterns: tuple[str, ...]
    manual_exclusions: tuple[str, ...]
    manual_admissions: tuple[str, ...]


@dataclass(frozen=True)
class RefreshPolicy:
    reuse_hours: int
    gf_reuse_days: int
    workers: int
    connect_timeout_s: float
    read_timeout_s: float
    deadline_s: float
    attempts: int
    backoff_s: tuple[float, ...]
    fmp_calls_per_minute: int
    rate_limit_hold_s: float
    fx_history_years: int


@dataclass(frozen=True)
class Policy:
    version: str
    hash: str
    required_return: float
    terminal_growth: float
    runway_years: dict[Moat, int]
    margin_of_safety: dict[Moat, float]
    fair_band: tuple[float, float]
    trim_multiple: float
    wide_terminal_roic_spread: float
    moat_wide_min: float
    moat_narrow_min: float
    base_rates: tuple[BaseRateClass, ...]
    inflation_addition: float
    marginal_return_span_years: int
    marginal_capital_growth_min: float
    fallback_return_years: int
    return_without_goodwill_cap: float
    fade_years: int
    high_growth_years: int
    margin_convergence_year: int
    peer_min: int
    industry_peer_max: int
    peer_margin_min_years: int
    implied_margin_bounds: tuple[float, float]
    own_sales_to_capital_min_share: float
    loss_ramp_margin_bound: float
    roic_sensitivity: tuple[float, float]
    analyst_min: int
    thin_revenue_step_max: float
    step_series_gap_max: float
    split_implied_count_tolerance: float
    inflation_max: float
    fx_stale_days: int
    nri_flag_share: float
    value_spread_flag: float
    long_runway_growth_flag: float
    margin_flag_ratio: float
    margin_flag_above_high: float
    margin_flag_min_years: int
    capex_ocf_flag: float
    equity_raise_share: float
    sbc_detect: float
    sbc_material_share: float
    sbc_basis_tax_share: float
    sbc_basis_gap_multiple: float
    share_count_gap_band: tuple[float, float]
    sheet_shift_multiple: float
    forward_pe_unit_error: float
    validity_fallback_days: int
    aging_fraction: float
    repricing_horizon_years: int
    runoff_years: int
    runoff_recovery: float
    distress_sale_fraction: float
    synthetic_rating: tuple[RatingRow, ...]
    default_probability_10y: dict[str, float]
    z_distress: float
    z_safe: float
    f_score_low: int
    burn_cover_flag_years: float
    override_ranges: dict[str, tuple[float, float]]
    override_primary_evidence_above_p90: bool
    secondary_parts_max: int
    secondary_years_min: int
    secondary_years_max: int
    secondary_driver_ranges: dict[str, tuple[float, float]]
    stance_words: tuple[str, ...]
    universe: UniversePolicy
    refresh: RefreshPolicy
    raw: dict[str, Any]
    settings_hash: str

    @property
    def designation_edges(self) -> tuple[float, float, float, float]:
        """e1 to e4: 1 − the Narrow margin of safety, the fair band's ends, the trim multiple."""
        low, high = self.fair_band
        return (1 - self.margin_of_safety["Narrow"], low, high, self.trim_multiple)

    @property
    def wide_terminal_roic_cap(self) -> float:
        """The Wide moat's terminal return cap: r + the spread."""
        return self.required_return + self.wide_terminal_roic_spread


def in_currency(policy: Policy, differential: float) -> Policy:
    """``policy`` restated into a currency whose inflation differential against USD is
    ``differential`` (the module docstring); a differential of 0 gives ``policy`` itself."""
    if differential == 0:
        return policy

    def restated(rate: float) -> float:
        return (1 + rate) * (1 + differential) - 1

    return replace(
        policy,
        required_return=restated(policy.required_return),
        terminal_growth=restated(policy.terminal_growth),
        inflation_addition=restated(policy.inflation_addition),
        return_without_goodwill_cap=restated(policy.return_without_goodwill_cap),
        base_rates=tuple(
            replace(c, sales_p90_5y=restated(c.sales_p90_5y)) for c in policy.base_rates
        ),
    )


def load_policy(path: Path | None = None) -> Policy:
    """Parse the policy file (default: the packaged v16 file) into a ``Policy`` with the empty
    overlay's settings hash, and check every setting's range."""
    from fairband.policy.settings import EMPTY_SETTINGS_HASH, check

    if path is None:
        data = resources.files(__name__).joinpath(_POLICY_FILE).read_bytes()
    else:
        data = path.read_bytes()
    raw = tomllib.loads(data.decode("utf-8"))
    try:
        version = _text(raw["meta"]["version"])
    except (KeyError, TypeError) as e:
        raise ValueError("policy: [meta] has no version") from e
    values = raw.get("values")
    values = values if isinstance(values, dict) else {}

    def read[T](name: str, convert: Callable[[Any], T]) -> T:
        entry = values.get(name)
        if not isinstance(entry, dict) or "value" not in entry:
            raise ValueError(f"policy: [values.{name}] is missing or has no value")
        if "source" not in entry:
            raise ValueError(f"policy: [values.{name}] has no source line")
        try:
            return convert(entry["value"])
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(
                f"policy: [values.{name}] is malformed ({type(e).__name__}: {e})"
            ) from e

    policy = Policy(
        version=version,
        hash=hashlib.sha256(data).hexdigest(),
        required_return=read("required_return", _num),
        terminal_growth=read("terminal_growth", _num),
        runway_years=read("runway_years", lambda t: _by_moat(t, _whole)),
        margin_of_safety=read("margin_of_safety", lambda t: _by_moat(t, _num)),
        fair_band=read("fair_band", _pair),
        trim_multiple=read("trim_multiple", _num),
        wide_terminal_roic_spread=read("wide_terminal_roic_spread", _num),
        moat_wide_min=read("moat_wide_min", _num),
        moat_narrow_min=read("moat_narrow_min", _num),
        base_rates=read("base_rates", _base_rates),
        inflation_addition=read("inflation_addition", _num),
        marginal_return_span_years=read("marginal_return_span_years", _whole),
        marginal_capital_growth_min=read("marginal_capital_growth_min", _num),
        fallback_return_years=read("fallback_return_years", _whole),
        return_without_goodwill_cap=read("return_without_goodwill_cap", _num),
        fade_years=read("fade_years", _whole),
        high_growth_years=read("high_growth_years", _whole),
        margin_convergence_year=read("margin_convergence_year", _whole),
        peer_min=read("peer_min", _whole),
        industry_peer_max=read("industry_peer_max", _whole),
        peer_margin_min_years=read("peer_margin_min_years", _whole),
        implied_margin_bounds=read("implied_margin_bounds", _pair),
        own_sales_to_capital_min_share=read("own_sales_to_capital_min_share", _num),
        loss_ramp_margin_bound=read("loss_ramp_margin_bound", _num),
        roic_sensitivity=read("roic_sensitivity", _pair),
        analyst_min=read("analyst_min", _whole),
        thin_revenue_step_max=read("thin_revenue_step_max", _num),
        step_series_gap_max=read("step_series_gap_max", _num),
        split_implied_count_tolerance=read("split_implied_count_tolerance", _num),
        inflation_max=read("inflation_max", _num),
        fx_stale_days=read("fx_stale_days", _whole),
        nri_flag_share=read("nri_flag_share", _num),
        value_spread_flag=read("value_spread_flag", _num),
        long_runway_growth_flag=read("long_runway_growth_flag", _num),
        margin_flag_ratio=read("margin_flag_ratio", _num),
        margin_flag_above_high=read("margin_flag_above_high", _num),
        margin_flag_min_years=read("margin_flag_min_years", _whole),
        capex_ocf_flag=read("capex_ocf_flag", _num),
        equity_raise_share=read("equity_raise_share", _num),
        sbc_detect=read("sbc_detect", _num),
        sbc_material_share=read("sbc_material_share", _num),
        sbc_basis_tax_share=read("sbc_basis_tax_share", _num),
        sbc_basis_gap_multiple=read("sbc_basis_gap_multiple", _num),
        share_count_gap_band=read("share_count_gap_band", _pair),
        sheet_shift_multiple=read("sheet_shift_multiple", _num),
        forward_pe_unit_error=read("forward_pe_unit_error", _num),
        validity_fallback_days=read("validity_fallback_days", _whole),
        aging_fraction=read("aging_fraction", _num),
        repricing_horizon_years=read("repricing_horizon_years", _whole),
        runoff_years=read("runoff_years", _whole),
        runoff_recovery=read("runoff_recovery", _num),
        distress_sale_fraction=read("distress_sale_fraction", _num),
        synthetic_rating=read("synthetic_rating", _synthetic_rating),
        default_probability_10y=read("default_probability_10y", _probabilities),
        z_distress=read("z_distress", _num),
        z_safe=read("z_safe", _num),
        f_score_low=read("f_score_low", _whole),
        burn_cover_flag_years=read("burn_cover_flag_years", _num),
        override_ranges=read("override_ranges", _ranges),
        override_primary_evidence_above_p90=read("override_primary_evidence_above_p90", _bool),
        secondary_parts_max=read("secondary_parts_max", _whole),
        secondary_years_min=read("secondary_years_min", _whole),
        secondary_years_max=read("secondary_years_max", _whole),
        secondary_driver_ranges=read("secondary_driver_ranges", _ranges),
        stance_words=read("stance_words", _texts),
        universe=read("universe", _universe),
        refresh=read("refresh", _refresh),
        raw=raw,
        settings_hash=EMPTY_SETTINGS_HASH,
    )
    check(policy)
    return policy


def _num(x: Any) -> float:
    if isinstance(x, bool) or not isinstance(x, int | float):
        raise TypeError(f"{x!r} is not a number")
    return float(x)


def _whole(x: Any) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{x!r} is not a whole number")
    return x


def _bool(x: Any) -> bool:
    if not isinstance(x, bool):
        raise TypeError(f"{x!r} is not true or false")
    return x


def _text(x: Any) -> str:
    if not isinstance(x, str):
        raise TypeError(f"{x!r} is not a string")
    return x


def _texts(x: Any) -> tuple[str, ...]:
    if not isinstance(x, list):
        raise TypeError(f"{x!r} is not a list")
    return tuple(_text(s) for s in x)


def _pair(x: Any) -> tuple[float, float]:
    if not isinstance(x, list) or len(x) != 2:
        raise TypeError(f"{x!r} is not a pair of numbers")
    return (_num(x[0]), _num(x[1]))


def _ranges(t: Any) -> dict[str, tuple[float, float]]:
    """Name to its range, a pair of numbers whose low is below its high: an override tag's, or a
    secondary valuation driver's."""
    if not isinstance(t, dict):
        raise TypeError(f"{t!r} is not a table of ranges")
    table = {_text(tag): _pair(pair) for tag, pair in t.items()}
    for tag, (low, high) in table.items():
        if not low < high:
            raise ValueError(f"the range of {tag}, {low} to {high}, does not ascend")
    return table


def _by_moat[T](t: Any, convert: Callable[[Any], T]) -> dict[Moat, T]:
    if not isinstance(t, dict) or set(t) != set(_MOATS):
        raise TypeError(f"{t!r} is not a table of None, Narrow and Wide")
    return {m: convert(t[m]) for m in _MOATS}


def _cap_bands(x: Any) -> tuple[tuple[float, str], ...]:
    if not isinstance(x, list) or not all(isinstance(b, list) and len(b) == 2 for b in x):
        raise TypeError(f"{x!r} is not a list of [floor, label] pairs")
    return tuple((_num(floor), _text(label)) for floor, label in x)


def _synthetic_rating(rows: Any) -> tuple[RatingRow, ...]:
    """The rating rows, ascending strictly by ``coverage_min`` from minus infinity, which the file
    writes as the string ``"-inf"`` (the only string a bound may be)."""
    if not isinstance(rows, list) or not rows:
        raise TypeError(f"{rows!r} is not a list of rows")
    table = tuple(RatingRow(_bound(r["coverage_min"]), _text(r["rating"])) for r in rows)
    if table[0].coverage_min != float("-inf"):
        raise ValueError(f"the first row's coverage_min is {table[0].coverage_min}, not -inf")
    for low, high in pairwise(table):
        if not high.coverage_min > low.coverage_min:
            raise ValueError(f"coverage_min does not ascend strictly at {high.rating}")
    return table


def _bound(x: Any) -> float:
    if isinstance(x, str):
        if x != "-inf":
            raise ValueError(f'{x!r} is not a number or "-inf"')
        return float("-inf")
    return _num(x)


def _probabilities(t: Any) -> dict[str, float]:
    """Rating to probability of default, each a fraction from 0 to 1; D's must be 1."""
    if not isinstance(t, dict):
        raise TypeError(f"{t!r} is not a table")
    table = {_text(rating): _num(p) for rating, p in t.items()}
    for rating, p in table.items():
        if not 0 <= p <= 1:
            raise ValueError(f"the probability of {rating}, {p}, is outside 0 to 1")
    if table["D"] != 1.0:
        raise ValueError(f"the probability of D must be 1.0, not {table['D']}")
    return table


def _base_rates(rows: Any) -> tuple[BaseRateClass, ...]:
    return tuple(
        BaseRateClass(
            _num(r["upper_musd"]), _num(r["median"]), _text(r["label"]), _num(r["sales_p90_5y"])
        )
        for r in rows
    )


def _universe(t: Any) -> UniversePolicy:
    return UniversePolicy(
        exchanges=_texts(t["exchanges"]),
        cap_floor_usd=_num(t["cap_floor_usd"]),
        cap_bands=_cap_bands(t["cap_bands"]),
        excluded_industries=_texts(t["excluded_industries"]),
        symbol_exclude_patterns=_texts(t["symbol_exclude_patterns"]),
        name_exclude_patterns=_texts(t["name_exclude_patterns"]),
        manual_exclusions=_texts(t["manual_exclusions"]),
        manual_admissions=_texts(t["manual_admissions"]),
    )


def _refresh(t: Any) -> RefreshPolicy:
    return RefreshPolicy(
        reuse_hours=_whole(t["reuse_hours"]),
        gf_reuse_days=_whole(t["gf_reuse_days"]),
        workers=_whole(t["workers"]),
        connect_timeout_s=_num(t["connect_timeout_s"]),
        read_timeout_s=_num(t["read_timeout_s"]),
        deadline_s=_num(t["deadline_s"]),
        attempts=_whole(t["attempts"]),
        backoff_s=tuple(_num(s) for s in t["backoff_s"]),
        fmp_calls_per_minute=_whole(t["fmp_calls_per_minute"]),
        rate_limit_hold_s=_num(t["rate_limit_hold_s"]),
        fx_history_years=_whole(t["fx_history_years"]),
    )
