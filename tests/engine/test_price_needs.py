"""What the price needs (method 4.11): on a row whose price is at or above the trim level, the
figures the row already solves at its price, in a reader's sentences."""

from typing import Any

import pytest

from fairband.engine.price_needs import price_needs
from fairband.engine.types import Route

WELL_ABOVE = "well-above"


def growth_row(implied: float | None) -> dict[str, Any]:
    return {"implied_growth": implied, "belief": {"rate": 0.053}, "runway": 20}


def stable_row(cross_check: dict[str, Any]) -> dict[str, Any]:
    return {
        "runway": 10,
        "growth_route": cross_check,
        "charge": {"growth_by_year": [0.03] * 10},
    }


def revenue_row(implied: float | None, margin: float | None) -> dict[str, Any]:
    return {
        "implied_growth": implied,
        "implied_margin": margin,
        "growth_rates": [0.35, 0.21, 0.20, 0.20, 0.20, 0.166, 0.132, 0.098, 0.064, 0.03],
        "revenue_path": {"high_growth_years": 5},
        "margin_path": {"target": 0.111, "by_year": [0.0] * 10},
    }


def decline_row(implied: float | None) -> dict[str, Any]:
    return {"implied_decline_rate": implied, "runoff_path": {"d": -0.04}}


def test_the_held_years_follow_the_high_growth_setting() -> None:
    """The held rate runs from year 4 to the last high-growth year, a setting of 3 to 9: one
    year at 4; none at 3, where year 4 already fades, so the row has no sentence."""
    seven = revenue_row(0.45, None) | {"revenue_path": {"high_growth_years": 7}}
    four = revenue_row(0.45, None) | {"revenue_path": {"high_growth_years": 4}}
    three = revenue_row(0.45, 0.352) | {"revenue_path": {"high_growth_years": 3}}
    needs_seven = price_needs("revenue-growth", seven, WELL_ABOVE)
    needs_four = price_needs("revenue-growth", four, WELL_ABOVE)
    assert needs_seven is not None and needs_four is not None
    assert needs_seven.startswith("The price needs revenue growth of 45.0% a year in years 4 to 7,")
    assert needs_four.startswith(
        "The price needs revenue growth of 45.0% a year in year 4, against"
    )
    assert price_needs("revenue-growth", three, WELL_ABOVE) is None


def test_a_mature_growth_row_names_the_growth_the_price_needs_against_the_belief() -> None:
    assert price_needs("mature-growth", growth_row(0.119), WELL_ABOVE) == (
        "The price needs long-run earnings growth of 11.9% a year to year 20. The route holds 5.3%."
    )


def test_a_mature_growth_row_says_when_no_growth_rate_reaches_the_price() -> None:
    assert price_needs("mature-growth", growth_row(None), WELL_ABOVE) == (
        "No long-run earnings growth rate in the range the route reads reaches the price. "
        "The route holds 5.3%."
    )


def test_a_mature_stable_row_reads_the_growth_route_s_path() -> None:
    valued = {"value_per_share": 60.0, "implied_growth": 0.084}
    assert price_needs("mature-stable", stable_row(valued), WELL_ABOVE) == (
        "On the growth route's path, the price needs long-run earnings growth of 8.4% a year to "
        "year 10. This route holds terminal growth, 3.0%."
    )
    no_root = {"value_per_share": 60.0, "implied_growth": None}
    assert price_needs("mature-stable", stable_row(no_root), WELL_ABOVE) == (
        "On the growth route's path, no long-run earnings growth rate in the range the route "
        "reads reaches the price. This route holds terminal growth, 3.0%."
    )


def test_a_mature_stable_row_without_a_cross_check_has_no_sentence() -> None:
    refused = {"refusal": "incomplete NTM consensus"}
    assert price_needs("mature-stable", stable_row(refused), WELL_ABOVE) is None
    assert price_needs("mature-stable", {"runway": 10}, WELL_ABOVE) is None


@pytest.mark.parametrize(
    ("implied", "margin", "sentence"),
    [
        (
            0.45,
            0.352,
            (
                "The price needs revenue growth of 45.0% a year in years 4 to 5, against 20.0% held. "
                "Or it needs an operating margin of 35.2% by year 10, against a target of 11.1%."
            ),
        ),
        (
            0.45,
            None,
            (
                "The price needs revenue growth of 45.0% a year in years 4 to 5, against 20.0% held. "
                "No operating margin by year 10 in the range the route reads reaches the price."
            ),
        ),
        (
            None,
            0.352,
            (
                "No revenue growth rate in years 4 to 5 in the range the route reads reaches the "
                "price. The price needs an operating margin of 35.2% by year 10, against a target of "
                "11.1%."
            ),
        ),
        (
            None,
            None,
            (
                "No revenue growth rate in years 4 to 5 and no operating margin by year 10, in the "
                "ranges the route reads, reaches the price. The route holds 20.0% and 11.1%."
            ),
        ),
    ],
)
def test_a_revenue_growth_row_names_the_growth_and_the_margin(
    implied: float | None, margin: float | None, sentence: str
) -> None:
    assert price_needs("revenue-growth", revenue_row(implied, margin), WELL_ABOVE) == sentence


def test_a_decline_row_names_the_decline_rate_with_its_sign() -> None:
    assert price_needs("decline", decline_row(-0.008), WELL_ABOVE) == (
        "The price needs revenue to change by −0.8% a year after the consensus years. "
        "The route holds −4.0%."
    )
    assert price_needs("decline", decline_row(None), WELL_ABOVE) == (
        "No decline rate in the range the route reads reaches the price. The route holds −4.0%."
    )


@pytest.mark.parametrize("designation", ["well-below", "below", "near", "above", None])
def test_only_a_price_well_above_the_value_gets_the_sentence(designation: str | None) -> None:
    assert price_needs("mature-growth", growth_row(0.119), designation) is None


@pytest.mark.parametrize("route", ["start-up", None])
def test_a_row_without_a_valued_route_has_no_sentence(route: Route | None) -> None:
    assert price_needs(route, {}, WELL_ABOVE) is None


@pytest.mark.parametrize("route", ["mature-growth", "mature-stable", "revenue-growth", "decline"])
def test_a_row_missing_its_figures_has_no_sentence(route: Route) -> None:
    """A snapshot valued before the keys existed, or a refusal's partial record: no sentence, and
    never an error."""
    assert price_needs(route, {}, WELL_ABOVE) is None
