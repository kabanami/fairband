"""The secondary valuation (spec 2026-11-06 Tier 2, section 11; ``method.md`` 15): a second way to
value a company, from an explicit cash-flow path an agent supplies.

A part is a name, the free cash flow to the firm in dollars for years 1 to N, N from the policy's
``secondary_years_min`` to ``secondary_years_max``, a terminal growth g at most the policy's g_T
(lower or negative allowed) and a note. Each part is discounted at r, the policy's required
return:

    PV_t = fcff_t ÷ (1 + r)^t, t = 1 … N
    terminal = fcff_N × (1 + g) ÷ (r − g), discounted by (1 + r)^N
    part value = Σ PV_t + the discounted terminal

One part is a DCF; several, up to ``secondary_parts_max``, a sum of parts. The firm value is the
sum over the parts; equity = firm value − debt + cash; the value a share = equity ÷ the diluted
shares. The levels on the moat (``levels_for``) and, with a price, the designation on price ÷
value (``designation_for``) come only with a value a share above zero: at or below zero the value
is kept as computed, with neither. A path the rules refuse raises ``ValueError`` with the rule's
sentence, checked in this order: the part count, each part's years, each part's terminal growth,
the share count.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.types import Designation, Levels
from fairband.policy import Moat, Policy

SECONDARY_METHOD = "fairband-secondary/1"


@dataclass(frozen=True)
class Part:
    """One part of the path: the free cash flow to the firm for years 1 to N, in dollars."""

    name: str
    fcff: tuple[float, ...]
    terminal_growth: float
    note: str | None


@dataclass(frozen=True)
class PartValue:
    """A part discounted: each year's present value, the terminal at year N, its present value,
    and the part's value."""

    name: str
    pv: tuple[float, ...]
    terminal: float
    terminal_pv: float
    value: float


@dataclass(frozen=True)
class SecondaryValuation:
    parts: tuple[PartValue, ...]
    firm_value: float
    debt: float
    cash: float
    shares: float
    equity: float
    value_per_share: float
    levels: Levels | None
    price_to_value: float | None
    designation: Designation | None


def secondary_value(
    parts: Sequence[Part],
    debt: float,
    cash: float,
    shares: float,
    price: float | None,
    moat: Moat,
    policy: Policy,
) -> SecondaryValuation:
    """The parts discounted at the policy's r and bridged to a value a share (module docstring)."""
    _check(parts, shares, policy)
    valued = tuple(_discounted(part, policy.required_return) for part in parts)
    firm_value = sum(part.value for part in valued)
    equity = firm_value - debt + cash
    per_share = equity / shares
    levels, price_to_value, designation = None, None, None
    if per_share > 0:
        levels = levels_for(per_share, moat, policy)
        if price is not None and price > 0:
            price_to_value, designation = designation_for(
                price, per_share, policy.designation_edges
            )
    return SecondaryValuation(
        parts=valued,
        firm_value=firm_value,
        debt=debt,
        cash=cash,
        shares=shares,
        equity=equity,
        value_per_share=per_share,
        levels=levels,
        price_to_value=price_to_value,
        designation=designation,
    )


def _check(parts: Sequence[Part], shares: float, policy: Policy) -> None:
    if not parts:
        raise ValueError("at least one part")
    if len(parts) > policy.secondary_parts_max:
        raise ValueError(f"at most {policy.secondary_parts_max} parts")
    shortest, longest = policy.secondary_years_min, policy.secondary_years_max
    g_t = policy.terminal_growth
    for part in parts:
        if not shortest <= len(part.fcff) <= longest:
            raise ValueError(f"a part has {shortest} to {longest} years")
        if part.terminal_growth > g_t:
            raise ValueError(f"the terminal growth is at most g_T, {g_t:.1%}")
    if not shares > 0:
        raise ValueError("a positive diluted share count")


def _discounted(part: Part, r: float) -> PartValue:
    pv = tuple(fcff / (1 + r) ** t for t, fcff in enumerate(part.fcff, start=1))
    g = part.terminal_growth
    terminal = part.fcff[-1] * (1 + g) / (r - g)
    terminal_pv = terminal / (1 + r) ** len(part.fcff)
    return PartValue(part.name, pv, terminal, terminal_pv, sum(pv) + terminal_pv)
