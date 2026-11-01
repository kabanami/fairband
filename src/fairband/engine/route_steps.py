"""The steps the two mature routes share, below ``route`` and the two route modules.

A route reads the company through a ``Context``, built by ``route.value_company`` once the guards
have passed: so with trailing figures, a positive price and a positive diluted share count. It
returns ``Valued`` or ``Refused`` and ``route`` builds the result from it.

``RoicTerms`` reads the aggregate ROIC as the charge takes it (spec 6.6, ROIC): an aggregate at or
below zero counts as unavailable, so the runway years take the terminal ROIC and the row is
flagged; a capital sum at or below zero turns Mature Growth's charge off. The income term of the
expected return is the trailing flows over the market cap: FMP signs dividends and buybacks as
outflows (negative) and stock issued as an inflow, and a missing flow counts as nil.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from typing import TYPE_CHECKING, Any

from fairband.engine.anchor import TrailingFigures
from fairband.engine.flags import gate_flags, margin_flag, nri_flag
from fairband.engine.multiples import multiples
from fairband.engine.price_facts import price_facts
from fairband.engine.returns import expected_return
from fairband.engine.roic import CapitalYear, RoicResult, aggregate_roic, terminal_roic
from fairband.engine.types import Flag, Kind, Provenance, Route, TaggedInput
from fairband.policy import Moat, Policy

if TYPE_CHECKING:
    from fairband.engine.route import CompanyInputs

_UNKNOWN = Provenance("unknown", None, None, None)
# The ``estimate_methods`` key assembly sets when invested capital takes the issuer's as-reported
# intangibles total; no input bears the name, so the aggregate ROIC carries the method.
_INTANGIBLES = "intangibles"
_INTANGIBLES_NOTE = "invested capital uses the issuer's total intangibles excluding goodwill"


@dataclass(frozen=True)
class Context:
    """A company past the guards of ``route.value_company``."""

    inputs: CompanyInputs
    trailing: TrailingFigures
    price: float
    shares: float
    policy: Policy
    today: date


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
    """A route's refusal, with the flags it had raised and the intermediates it had computed."""

    reason: str
    flags: tuple[Flag, ...] = ()
    intermediates: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RoicTerms:
    """The aggregate ROIC, the usable (positive) aggregate, the runway and terminal ROIC of the
    charge, whether the charge is off, and the ROIC flags."""

    result: RoicResult
    usable: float | None
    runway: float
    terminal: float
    charge_off: bool
    flags: tuple[Flag, ...]

    @classmethod
    def of(cls, years: Sequence[CapitalYear], moat: Moat, policy: Policy) -> RoicTerms:
        result = aggregate_roic(years)
        aggregate = result.aggregate
        usable = aggregate if aggregate is not None and aggregate > 0 else None
        terminal = terminal_roic(usable, moat, policy)
        flags = result.flags
        if aggregate is not None and usable is None:
            flags += (
                Flag(
                    "roic-unavailable",
                    "ROIC unavailable",
                    f"The aggregate ROIC over {result.years_used} fiscal years is "
                    f"{aggregate:.1%}, which is not positive, so the charge uses the terminal "
                    "ROIC in every year.",
                ),
            )
        charge_off = any(f.code == "charge-zeroed" for f in result.flags)
        runway = terminal if usable is None else usable
        return cls(result, usable, runway, terminal, charge_off, flags)

    def intermediates(self) -> dict[str, Any]:
        r = self.result
        return {
            "roic": {
                "aggregate": r.aggregate,
                "years": r.years_used,
                "by_year": [asdict(y) for y in r.by_year],
            },
            "terminal_roic": self.terminal,
        }


def nri_gap(i: CompanyInputs) -> float | None:
    """GuruFocus EPS less EPS without non-recurring items, a share; ``None`` without both."""
    if i.gf_eps_ttm is None or i.gf_eps_without_nri is None:
        return None
    return i.gf_eps_ttm - i.gf_eps_without_nri


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
    steps: tuple[float | None, float | None],
    belief: float,
) -> dict[str, float] | None:
    """The Step 9 expected return; ``None`` for a value at or below zero, which has no rate."""
    if value <= 0:
        return None
    er = expected_return(price, value, im["dividend_yield"], im["net_buyback_yield"], steps, belief)
    return asdict(er)


def trailing_flags(
    i: CompanyInputs, t: TrailingFigures, gap: float | None, policy: Policy
) -> tuple[Flag, ...]:
    """The margin flag, the three gate flags and the non-recurring flag, in that order."""
    return (
        present(margin_flag(i.series, ttm_margin(t), policy))
        + gate_flags(t, i.market_cap, policy)
        + present(nri_flag(gap, t.eps_diluted, policy))
    )


def common_inputs(i: CompanyInputs, t: TrailingFigures, roic: RoicTerms) -> tuple[TaggedInput, ...]:
    """The DATA inputs both routes read, beyond the ones every result carries."""
    return (
        data(i, "market_cap", i.market_cap, "USD"),
        data(i, "revenue_ttm", t.revenue, "USD", "statements"),
        data(i, "operating_income_ttm", t.operating_income, "USD", "statements"),
        data(i, "eps_ttm", t.eps_diluted, "USD a share", "statements"),
        data(i, "dividends_ttm", t.dividends, "USD", "statements"),
        data(i, "buybacks_ttm", t.buybacks, "USD", "statements"),
        data(i, "equity_issued_ttm", t.equity_issued, "USD", "statements"),
        _aggregate_roic(i, roic),
        data(i, "tax_rate_latest", i.tax_rate_latest, "ratio"),  # the newest ROIC year's rate
        data(i, "moat_score", i.moat_score, "score"),
        data(i, "gf_eps_ttm", i.gf_eps_ttm, "USD a share"),
        data(i, "gf_eps_without_nri", i.gf_eps_without_nri, "USD a share"),
    )


def _aggregate_roic(i: CompanyInputs, roic: RoicTerms) -> TaggedInput:
    """The aggregate ROIC, an estimate under the intangibles method when assembly took the
    issuer's as-reported intangibles total into invested capital (D17)."""
    found = data(i, "aggregate_roic", roic.result.aggregate, "ratio", "statements")
    method = i.estimate_methods.get(_INTANGIBLES)
    if method is None:
        return found
    return replace(found, kind="estimate", estimate_method=method, note=_INTANGIBLES_NOTE)


def common_rules(policy: Policy, moat: Moat, roic: RoicTerms) -> tuple[TaggedInput, ...]:
    """The RULE inputs both routes use."""
    return (
        rule(policy, "required_return", policy.required_return, "ratio"),
        rule(policy, "terminal_growth", policy.terminal_growth, "ratio"),
        rule(policy, "moat_class", None, "class", moat),
        rule(policy, "margin_of_safety", policy.margin_of_safety[moat], "ratio", f"{moat} moat"),
        rule(policy, "terminal_roic", roic.terminal, "ratio", f"{moat} moat"),
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
