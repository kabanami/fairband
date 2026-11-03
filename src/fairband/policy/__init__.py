"""The policy: every valuation constant, in one versioned TOML file with a source line per value.

``load_policy`` reads ``fairband-policy-v3.toml`` from the package unless given a path. Each
``[values.<name>]`` table holds ``value`` and ``source``; a missing or malformed one raises
``ValueError`` naming the section. ``Policy.hash`` is the sha256 of the file bytes, so a result can
cite the exact policy it was computed under. Code elsewhere holds no valuation constant. The v1
and v2 files stay in the package byte for byte, because the snapshots valued under them cite their
hashes.
"""

import hashlib
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Literal

Moat = Literal["Wide", "Narrow", "None"]

_POLICY_FILE = "fairband-policy-v3.toml"
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
class UniversePolicy:
    exchanges: tuple[str, ...]
    cap_floor_usd: float
    cap_bands: tuple[tuple[float, str], ...]
    excluded_industries: tuple[str, ...]
    symbol_exclude_patterns: tuple[str, ...]
    name_exclude_patterns: tuple[str, ...]
    manual_exclusions: tuple[str, ...]


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
    wide_terminal_roic_cap: float
    moat_wide_min: float
    moat_narrow_min: float
    base_rates: tuple[BaseRateClass, ...]
    inflation_addition: float
    marginal_return_span_years: int
    marginal_capital_growth_min: float
    fallback_return_years: int
    fade_years: int
    high_growth_years: int
    margin_convergence_year: int
    peer_min: int
    peer_margin_min_years: int
    implied_margin_bounds: tuple[float, float]
    roic_sensitivity: tuple[float, float]
    analyst_min: int
    nri_flag_share: float
    value_spread_flag: float
    long_runway_growth_flag: float
    margin_flag_ratio: float
    margin_flag_above_high: float
    margin_flag_min_years: int
    capex_ocf_flag: float
    equity_raise_share: float
    sbc_detect: float
    forward_pe_unit_error: float
    validity_fallback_days: int
    aging_fraction: float
    universe: UniversePolicy
    refresh: RefreshPolicy
    raw: dict[str, Any]


def load_policy(path: Path | None = None) -> Policy:
    """Parse the policy file (default: the packaged v3 file) into a ``Policy``."""
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

    return Policy(
        version=version,
        hash=hashlib.sha256(data).hexdigest(),
        required_return=read("required_return", _num),
        terminal_growth=read("terminal_growth", _num),
        runway_years=read("runway_years", lambda t: {m: _whole(t[m]) for m in _MOATS}),
        margin_of_safety=read("margin_of_safety", lambda t: {m: _num(t[m]) for m in _MOATS}),
        fair_band=read("fair_band", _pair),
        trim_multiple=read("trim_multiple", _num),
        wide_terminal_roic_cap=read("wide_terminal_roic_cap", _num),
        moat_wide_min=read("moat_wide_min", _num),
        moat_narrow_min=read("moat_narrow_min", _num),
        base_rates=read("base_rates", _base_rates),
        inflation_addition=read("inflation_addition", _num),
        marginal_return_span_years=read("marginal_return_span_years", _whole),
        marginal_capital_growth_min=read("marginal_capital_growth_min", _num),
        fallback_return_years=read("fallback_return_years", _whole),
        fade_years=read("fade_years", _whole),
        high_growth_years=read("high_growth_years", _whole),
        margin_convergence_year=read("margin_convergence_year", _whole),
        peer_min=read("peer_min", _whole),
        peer_margin_min_years=read("peer_margin_min_years", _whole),
        implied_margin_bounds=read("implied_margin_bounds", _pair),
        roic_sensitivity=read("roic_sensitivity", _pair),
        analyst_min=read("analyst_min", _whole),
        nri_flag_share=read("nri_flag_share", _num),
        value_spread_flag=read("value_spread_flag", _num),
        long_runway_growth_flag=read("long_runway_growth_flag", _num),
        margin_flag_ratio=read("margin_flag_ratio", _num),
        margin_flag_above_high=read("margin_flag_above_high", _num),
        margin_flag_min_years=read("margin_flag_min_years", _whole),
        capex_ocf_flag=read("capex_ocf_flag", _num),
        equity_raise_share=read("equity_raise_share", _num),
        sbc_detect=read("sbc_detect", _num),
        forward_pe_unit_error=read("forward_pe_unit_error", _num),
        validity_fallback_days=read("validity_fallback_days", _whole),
        aging_fraction=read("aging_fraction", _num),
        universe=read("universe", _universe),
        refresh=read("refresh", _refresh),
        raw=raw,
    )


def _num(x: Any) -> float:
    if isinstance(x, bool) or not isinstance(x, int | float):
        raise TypeError(f"{x!r} is not a number")
    return float(x)


def _whole(x: Any) -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{x!r} is not a whole number")
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
        cap_bands=tuple((_num(bound), _text(label)) for bound, label in t["cap_bands"]),
        excluded_industries=_texts(t["excluded_industries"]),
        symbol_exclude_patterns=_texts(t["symbol_exclude_patterns"]),
        name_exclude_patterns=_texts(t["name_exclude_patterns"]),
        manual_exclusions=_texts(t["manual_exclusions"]),
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
    )
