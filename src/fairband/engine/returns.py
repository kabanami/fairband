"""The expected annual return over the repricing horizon (method v1.7 Step 9).

Income is the dividend yield plus the net buyback yield; a net issuer's buyback yield is negative.
Growth is the geometric mean of the earnings growth for years 2 to H + 1, the rates as the route's
path models them, which the caller resolves (calibration spec 5.4a): for Mature Growth the two
consensus steps and year 4's rate, the faded one when the fade applies and the belief otherwise;
for Mature Stable the terminal growth each year. At H = 3 it is
((1 + g2)(1 + g3)(1 + g4))^(1/3) − 1. Repricing is ln(value ÷ price) ÷ H, the fair forward
multiple against the current one on the same year-1 earnings. The total is the sum of the three.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ExpectedReturn:
    income: float
    growth: float
    repricing: float
    total: float


def expected_return(
    price: float,
    value: float,
    dividend_yield: float,
    net_buyback_yield: float,
    rates: Sequence[float],
    horizon: int = 3,
) -> ExpectedReturn:
    """The Step 9 decomposition, its growth over the first ``horizon`` of ``rates``, the growth
    for years 2 onwards; ``ValueError`` for a price or value at or below zero, fewer rates than
    the horizon, or a path whose earnings fall to zero or below, where no annual rate exists."""
    if price <= 0 or value <= 0:
        raise ValueError(f"price {price} and value {value} must be positive")
    if len(rates) < horizon:
        raise ValueError(f"{len(rates)} growth rates for a {horizon}-year horizon")
    level = math.prod(1 + g for g in rates[:horizon])
    if level <= 0:
        raise ValueError(
            f"growth over the path {list(rates[:horizon])} takes earnings to zero or below"
        )
    income = dividend_yield + net_buyback_yield
    growth = level ** (1 / horizon) - 1
    repricing = math.log(value / price) / horizon
    return ExpectedReturn(income, growth, repricing, income + growth + repricing)
