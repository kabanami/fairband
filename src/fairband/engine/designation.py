"""The designation (spec 7.1): where the price stands against the value at belief, in five bands.

The ratio is price ÷ value as a plain float division, and the band compares it with the edges of
the row's moat class, the policy's ``edges_for(moat)`` [e1, e2, e3, e4], as floats: below e1
``well-below``; from e1, below e2 ``below``; from e2 to e3, ends included, ``near``; above e3,
below e4 ``above``; at or above e4 ``well-above``. e1 is the row's own buy level over its value
(spec 2026-11-23 thresholds, 5.2), so the five words match the row's four levels. As doubles,
90 ÷ 100 and 135 ÷ 100 equal the edge literals 0.9 and 1.35, so a price on an edge reads the band
the table gives it. The word is a fact about the price, never an action.
"""

from fairband.engine.types import Designation


def designation_for(
    price: float, value: float, edges: tuple[float, float, float, float]
) -> tuple[float, Designation]:
    """Price ÷ value and its band; the caller passes a positive price and value."""
    ratio = price / value
    e1, e2, e3, e4 = edges
    if ratio < e1:
        return ratio, "well-below"
    if ratio < e2:
        return ratio, "below"
    if ratio <= e3:
        return ratio, "near"
    if ratio < e4:
        return ratio, "above"
    return ratio, "well-above"
