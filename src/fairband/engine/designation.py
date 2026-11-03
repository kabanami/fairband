"""The designation (spec 7.1): where the price stands against the value at belief, in five bands.

The ratio is price ÷ value as a plain float division, and the band compares it with the policy's
``designation_edges`` [e1, e2, e3, e4] as floats: below e1 ``well-below``; from e1, below e2
``below``; from e2 to e3, ends included, ``near``; above e3, below e4 ``above``; at or above e4
``well-above``. As doubles, 85 ÷ 100 and 150 ÷ 100 equal the edge literals 0.85 and 1.5, so spec
13.3's prices on an edge read the band the table gives them. The word is a fact about the price,
never an action.
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
