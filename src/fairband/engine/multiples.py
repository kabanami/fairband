"""The trailing and forward P/E (method Step 7), EPV and the growth share of price (Step 3).

A P/E exists only for a positive EPS; a missing, zero or negative EPS has none. EPV is clean
trailing EPS ÷ r, and the growth share is the part of the price EPV does not cover.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Multiples:
    """Price over reported trailing, clean trailing and forward EPS; ``None`` where there is none."""

    pe_reported: float | None
    pe_clean: float | None
    pe_forward: float | None


def _pe(price: float, eps: float | None) -> float | None:
    if eps is None or eps <= 0:
        return None
    return price / eps


def multiples(
    price: float, eps_reported: float | None, eps_clean: float | None, eps_forward: float | None
) -> Multiples:
    """The three P/E multiples at ``price``."""
    return Multiples(_pe(price, eps_reported), _pe(price, eps_clean), _pe(price, eps_forward))


def epv(eps_clean: float, r: float) -> float:
    """The earnings power value per share: clean trailing EPS with no growth, at ``r``."""
    return eps_clean / r


def growth_share(epv_value: float, price: float) -> float:
    """The share of ``price`` that EPV does not cover."""
    return 1 - epv_value / price
