"""Levels and validity state (``design.md`` 6.3 and 8).

The buy level is the value times one less the moat's margin of safety; the fair band and the trim
level are the value times the policy's factors. Each level is the exact decimal product of the
value and the factor as written, rounded once to a float: plain float multiplication gives
``100 * 1.15 == 114.99999999999999``, which would put a price at the top of the band above it.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from fairband.engine.designation import designation_for
from fairband.engine.types import Designation, Levels
from fairband.policy import Moat, Policy


@dataclass(frozen=True)
class Standing:
    """A record's levels, and where a price stands against its value: price ÷ value and the
    designation's word, both ``None`` without a price above zero."""

    levels: Levels
    price_to_value: float | None
    designation: Designation | None


def levels_for(value: float, moat: Moat, policy: Policy) -> Levels:
    low, high = policy.fair_band
    return Levels(
        buy=_times(value, 1 - _decimal(policy.margin_of_safety[moat])),
        fair_low=_times(value, _decimal(low)),
        fair_high=_times(value, _decimal(high)),
        trim=_times(value, _decimal(policy.trim_multiple)),
    )


def standing_for(value: float, moat: Moat, price: float | None, policy: Policy) -> Standing:
    """A record's levels, price ÷ value and word on ``policy`` (spec 2026-11-23 thresholds, 5.3):
    the levels of ``value`` on the class ``moat`` (``levels_for``), and with a ``price`` above
    zero the ratio and its word on that class's edges (``Policy.edges_for``), so a price under
    the row's own buy level reads Well below. ``value`` is above zero: the caller checks. The
    thresholds move no value, so a reader calls this on the policy in force, whatever policy the
    record was valued under."""
    levels = levels_for(value, moat, policy)
    if price is None or price <= 0:
        return Standing(levels, None, None)
    ratio, word = designation_for(price, value, policy.edges_for(moat))
    return Standing(levels, ratio, word)


def validity_state(
    valid_from: date, valid_until: date, today: date, aging_fraction: float
) -> Literal["current", "aging", "expired"]:
    """Current until ``aging_fraction`` of the window in days, then aging, expired after its end."""
    if today > valid_until:
        return "expired"
    if (today - valid_from).days >= aging_fraction * (valid_until - valid_from).days:
        return "aging"
    return "current"


def _decimal(x: float) -> Decimal:
    return Decimal(repr(x))


def _times(value: float, factor: Decimal) -> float:
    return float(_decimal(value) * factor)
