"""What the price needs (method 4.11): on a row whose price is at or above the trim level, the
figures the row already solves at its price, in a reader's sentences."""

from typing import Any

import pytest

from fairband.engine.price_needs import price_needs
from fairband.engine.types import Route

WELL_ABOVE = "well-above"
R = 0.09
NO_RATE = "in the range the route reads reaches the price"


def growth_row(
    implied: float | None, returns: tuple[float, ...] = (0.20, 0.20, 0.13)
) -> dict[str, Any]:
    return {
        "implied_growth": implied,
        "belief": {"rate": 0.053},
        "runway": 20,
        "charge": {"return_by_year": list(returns)},
        "charge_off": False,
        "implied_by_roic": {"runway": implied, "0.15": 0.107, "0.09": None, "ten-year": 0.31},
    }


def stable_row(
    cross_check: dict[str, Any], returns: tuple[float, ...] = (0.18, 0.13)
) -> dict[str, Any]:
    return {
        "runway": 10,
        "growth_route": cross_check,
        "charge": {"growth_by_year": [0.03] * 10, "return_by_year": list(returns)},
        "charge_off": False,
    }


def revenue_row(
    implied: float | None, margin: float | None, last: int = 5, reached: int = 10
) -> dict[str, Any]:
    """A row that holds 20% to year ``last`` and reaches its 11.1% target in year ``reached``."""
    ramp = [0.111 * min(year, reached) / reached for year in range(1, 11)]
    return {
        "implied_growth": implied,
        "implied_margin": margin,
        "growth_rates": [0.35, 0.21, 0.20, 0.20, 0.20, 0.166, 0.132, 0.098, 0.064, 0.03],
        "revenue_path": {"high_growth_years": last},
        "margin_path": {"target": 0.111, "by_year": ramp},
    }


def decline_row(implied: float | None) -> dict[str, Any]:
    return {"implied_decline_rate": implied, "runoff_path": {"d": -0.04}}


def test_a_mature_growth_row_names_the_growth_the_price_needs_against_the_belief() -> None:
    assert price_needs("mature-growth", growth_row(0.119), WELL_ABOVE, R) == (
        "The price needs long-run earnings growth of 11.9% a year to year 20. The route holds 5.3%."
    )


def test_a_mature_growth_row_says_when_no_growth_rate_reaches_the_price() -> None:
    assert price_needs("mature-growth", growth_row(None), WELL_ABOVE, R) == (
        f"No long-run earnings growth rate {NO_RATE}. The route holds 5.3%."
    )


def test_a_row_charged_at_the_hurdle_rate_says_growth_adds_no_value() -> None:
    """At a return equal to r in every year, growth adds no value, so the solve finds no rate
    whatever the price (method 5.8). The sentence gives that reason, never "no rate in the
    range", and the growth the price needs at the sensitivity's return above r, as the report
    template tells the agent."""
    at_r = growth_row(None, returns=(R, R, R))
    lead = (
        "The route charges growth at the hurdle rate, so growth adds no value and no growth rate "
        "reaches the price."
    )
    assert price_needs("mature-growth", at_r, WELL_ABOVE, R) == (
        f"{lead} At a return of 15.0% on new capital, the price needs long-run earnings growth of "
        "10.7% a year to year 20. The route holds 5.3%."
    )
    no_case = at_r | {"implied_by_roic": {"runway": None, "0.15": None, "0.09": None}}
    assert price_needs("mature-growth", no_case, WELL_ABOVE, R) == f"{lead} The route holds 5.3%."
    # a return key at or below r is never the case named: only one above it adds value
    low = at_r | {"implied_by_roic": {"runway": None, "0.09": 0.5, "0.05": 0.4}}
    assert price_needs("mature-growth", low, WELL_ABOVE, R) == f"{lead} The route holds 5.3%."
    # without r, or with the runway years uncharged, the plain sentence stands
    plain = f"No long-run earnings growth rate {NO_RATE}. The route holds 5.3%."
    assert price_needs("mature-growth", at_r, WELL_ABOVE) == plain
    assert price_needs("mature-growth", at_r | {"charge_off": True}, WELL_ABOVE, R) == plain


def test_a_mature_stable_row_reads_the_growth_route_s_path() -> None:
    valued = {"value_per_share": 60.0, "implied_growth": 0.084}
    assert price_needs("mature-stable", stable_row(valued), WELL_ABOVE, R) == (
        "On the growth route's path, the price needs long-run earnings growth of 8.4% a year to "
        "year 10. This route holds terminal growth, 3.0%."
    )
    no_root = {"value_per_share": 60.0, "implied_growth": None}
    assert price_needs("mature-stable", stable_row(no_root), WELL_ABOVE, R) == (
        f"On the growth route's path, no long-run earnings growth rate {NO_RATE}. This route "
        "holds terminal growth, 3.0%."
    )
    assert price_needs("mature-stable", stable_row(no_root, (R, R)), WELL_ABOVE, R) == (
        "The route charges growth at the hurdle rate, so growth adds no value and no growth rate "
        "reaches the price. This route holds terminal growth, 3.0%."
    )


def test_a_mature_stable_row_without_a_cross_check_has_no_sentence() -> None:
    refused = {"refusal": "incomplete NTM consensus"}
    assert price_needs("mature-stable", stable_row(refused), WELL_ABOVE, R) is None
    assert price_needs("mature-stable", {"runway": 10}, WELL_ABOVE, R) is None


GROWTH = "The price needs revenue growth of 45.0% a year in years 4 to 5, against 20.0% held."
NO_GROWTH = f"No revenue growth rate in years 4 to 5 {NO_RATE}."


@pytest.mark.parametrize(
    ("implied", "margin", "sentence"),
    [
        (
            0.45,
            0.352,
            (
                f"{GROWTH} Or it needs an operating margin of 35.2% by year 10, against a target of "
                "11.1%."
            ),
        ),
        (0.45, None, f"{GROWTH} No operating margin by year 10 {NO_RATE}."),
        (
            None,
            0.352,
            (
                f"{NO_GROWTH} The price needs an operating margin of 35.2% by year 10, against a target "
                "of 11.1%."
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
    assert price_needs("revenue-growth", revenue_row(implied, margin), WELL_ABOVE, R) == sentence


def test_the_held_years_follow_the_high_growth_setting() -> None:
    """The held rate runs from year 4 to the last high-growth year, a setting of 3 to 9: one
    year at 4; none at 3, where year 4 already fades, so only the margin speaks."""
    seven = price_needs("revenue-growth", revenue_row(0.45, None, last=7), WELL_ABOVE, R)
    four = price_needs("revenue-growth", revenue_row(0.45, None, last=4), WELL_ABOVE, R)
    assert seven is not None and four is not None
    assert seven.startswith("The price needs revenue growth of 45.0% a year in years 4 to 7,")
    assert four.startswith("The price needs revenue growth of 45.0% a year in year 4, against")
    assert price_needs("revenue-growth", revenue_row(0.45, 0.352, last=3), WELL_ABOVE, R) == (
        "The price needs an operating margin of 35.2% by year 10, against a target of 11.1%."
    )
    assert price_needs("revenue-growth", revenue_row(0.45, None, last=3), WELL_ABOVE, R) == (
        f"No operating margin by year 10 {NO_RATE}. The route holds 11.1%."
    )


def test_the_margin_s_year_is_the_year_the_path_reaches_the_target() -> None:
    """``margin_convergence_year`` is a setting of 1 to 10: the sentence names the year the
    stored margin path first stands at its target, not the forecast's length."""
    needs = price_needs("revenue-growth", revenue_row(None, 0.352, reached=5), WELL_ABOVE, R)
    assert needs is not None
    assert needs.endswith(
        "The price needs an operating margin of 35.2% by year 5, against a target of 11.1%."
    )
    never = revenue_row(None, 0.352) | {"margin_path": {"target": 0.111, "by_year": [0.05] * 10}}
    needs = price_needs("revenue-growth", never, WELL_ABOVE, R)
    assert needs is not None and "by year 10, against" in needs  # the path's last year


def test_a_decline_row_names_the_decline_rate_with_its_sign() -> None:
    """The decline rate is the route's own term: it starts a fade to zero and, without a usable
    consensus, shrinks years 1 to 3 too (6a.2), so the sentence names the rate and no years."""
    assert price_needs("decline", decline_row(-0.008), WELL_ABOVE, R) == (
        "The price needs a decline rate of −0.8% a year. The route holds −4.0%."
    )
    assert price_needs("decline", decline_row(None), WELL_ABOVE, R) == (
        f"No decline rate {NO_RATE}. The route holds −4.0%."
    )


@pytest.mark.parametrize("designation", ["well-below", "below", "near", "above", None])
def test_only_a_price_well_above_the_value_gets_the_sentence(designation: str | None) -> None:
    assert price_needs("mature-growth", growth_row(0.119), designation, R) is None


@pytest.mark.parametrize("route", ["start-up", None])
def test_a_row_without_a_valued_route_has_no_sentence(route: Route | None) -> None:
    assert price_needs(route, {}, WELL_ABOVE, R) is None


@pytest.mark.parametrize("route", ["mature-growth", "mature-stable", "revenue-growth", "decline"])
def test_a_row_missing_its_figures_has_no_sentence(route: Route) -> None:
    """A snapshot valued before the keys existed, or a refusal's partial record: no sentence, and
    never an error."""
    assert price_needs(route, {}, WELL_ABOVE, R) is None
    assert price_needs(route, {"charge": None, "margin_path": 3}, WELL_ABOVE, R) is None
