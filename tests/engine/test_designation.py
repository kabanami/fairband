"""The designation of spec 7.1: price ÷ value as a plain float division, and its band by the
policy's edges; the worked numbers of spec 13.3 on a value of 100."""

import pytest

from fairband.engine.designation import designation_for
from fairband.policy import load_policy

EDGES = (0.65, 0.85, 1.15, 1.50)


@pytest.mark.parametrize(
    "price, word",
    [
        (64.99, "well-below"),
        (65, "below"),
        (84.99, "below"),
        (85, "near"),
        (115, "near"),
        (115.01, "above"),
        (149.99, "above"),
        (150, "well-above"),
    ],
)
def test_the_five_bands_on_a_value_of_100(price: float, word: str) -> None:
    ratio, got = designation_for(price, 100.0, EDGES)
    assert got == word and ratio == pytest.approx(price / 100)


def test_the_ratio_is_the_plain_division() -> None:
    assert designation_for(150.0, 133.37, EDGES) == (150.0 / 133.37, "near")


def test_the_policy_holds_the_edges() -> None:
    assert load_policy().designation_edges == EDGES
