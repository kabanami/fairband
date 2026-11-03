"""Levels and validity state (``design.md`` 6.3 and 8).

The buy level is the value times one less the moat's margin of safety; the fair band and the trim
level are the value times the policy's factors. Each level is the exact decimal product of the
value and the factor as written, rounded once to a float: plain float multiplication gives
``100 * 1.15 == 114.99999999999999``, which would put a price at the top of the band above it.
"""

from datetime import date
from decimal import Decimal
from typing import Literal

from fairband.engine.types import Levels
from fairband.policy import Moat, Policy


def levels_for(value: float, moat: Moat, policy: Policy) -> Levels:
    low, high = policy.fair_band
    return Levels(
        buy=_times(value, 1 - _decimal(policy.margin_of_safety[moat])),
        fair_low=_times(value, _decimal(low)),
        fair_high=_times(value, _decimal(high)),
        trim=_times(value, _decimal(policy.trim_multiple)),
    )


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
