"""The expected annual return over the repricing horizon (method v1.7 Step 9).

Income is the dividend yield plus the net buyback yield; a net issuer's buyback yield is negative.
Growth is the geometric mean of the earnings steps 2 to H + 1: the path's steps for years 2 and 3
(a ``None`` step takes the belief), then the belief. At H = 3 it is
((1 + g2)(1 + g3)(1 + belief))^(1/3) − 1. Repricing is ln(value ÷ price) ÷ H, the fair forward
multiple against the current one on the same year-1 earnings. The total is the sum of the three.
"""

import math
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
    steps: tuple[float | None, float | None],
    belief: float,
    horizon: int = 3,
) -> ExpectedReturn:
    """The Step 9 decomposition; ``ValueError`` for a price or value at or below zero, or a path
    whose earnings fall to zero or below, where no annual rate exists."""
    if price <= 0 or value <= 0:
        raise ValueError(f"price {price} and value {value} must be positive")
    rates = [belief if g is None else g for g in steps]
    rates += [belief] * (horizon - len(rates))
    level = math.prod(1 + g for g in rates[:horizon])
    if level <= 0:
        raise ValueError(f"growth over the path {rates[:horizon]} takes earnings to zero or below")
    income = dividend_yield + net_buyback_yield
    growth = level ** (1 / horizon) - 1
    repricing = math.log(value / price) / horizon
    return ExpectedReturn(income, growth, repricing, income + growth + repricing)
