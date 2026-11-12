"""What the price needs (``method.md`` 4.11).

On a row whose price is at or above the trim level, the designation ``well-above``, the value
alone says only that the method cannot reach the price. The sentences here say what the price
asks of the business, from the figures the row already solves at its price: the implied growth
against the belief on Mature Growth; the growth-route cross-check's implied growth on Mature
Stable; the implied held rate and the margin the price needs on the revenue-growth route; the
implied decline rate on Decline. Where a solve found no rate in its range, the sentence says so.
It computes nothing and moves nothing: the value, the levels and the designation stand as they
are.

A row with no route's figures (a Start-up row, a refusal, a snapshot valued before a key
existed) has no sentence, and neither has a Mature Stable row whose cross-check refused, which
solved nothing at the price, nor a revenue-growth row under a ``high_growth_years`` setting of
3, which holds no year at the held rate.
"""

from collections.abc import Mapping
from typing import Any

from fairband.engine.types import Route

WELL_ABOVE = "well-above"
_NO_RATE = "in the range the route reads reaches the price"


def price_needs(
    route: Route | None, intermediates: Mapping[str, Any], designation: str | None
) -> str | None:
    """The sentences on what the price needs of a row on ``route`` with ``intermediates`` and
    the ``designation`` of its price against its value; ``None`` unless the price is well above
    the value and the row carries the figures."""
    if designation != WELL_ABOVE:
        return None
    try:
        match route:
            case "mature-growth":
                return _mature_growth(intermediates)
            case "mature-stable":
                return _mature_stable(intermediates)
            case "revenue-growth":
                return _revenue_growth(intermediates)
            case "decline":
                return _decline(intermediates)
    except (KeyError, IndexError, TypeError):
        return None  # a record without the figures: no sentence
    return None


def _mature_growth(im: Mapping[str, Any]) -> str:
    holds = f"The route holds {_percent(im['belief']['rate'])}."
    implied, runway = im["implied_growth"], im["runway"]
    if implied is None:
        return f"No long-run earnings growth rate {_NO_RATE}. {holds}"
    return (
        f"The price needs long-run earnings growth of {_percent(implied)} a year to year "
        f"{runway}. {holds}"
    )


def _mature_stable(im: Mapping[str, Any]) -> str | None:
    cross_check = im["growth_route"]
    if cross_check.get("value_per_share") is None:
        return None
    holds = f"This route holds terminal growth, {_percent(im['charge']['growth_by_year'][-1])}."
    implied = cross_check["implied_growth"]
    if implied is None:
        return f"On the growth route's path, no long-run earnings growth rate {_NO_RATE}. {holds}"
    return (
        "On the growth route's path, the price needs long-run earnings growth of "
        f"{_percent(implied)} a year to year {im['runway']}. {holds}"
    )


def _revenue_growth(im: Mapping[str, Any]) -> str | None:
    implied, margin = im["implied_growth"], im["implied_margin"]
    last = im["revenue_path"]["high_growth_years"]
    if last < 4:  # no held year: year 4 already fades, and its rate is not the held rate
        return None
    held, target = _percent(im["growth_rates"][3]), _percent(im["margin_path"]["target"])
    years = "in year 4" if last == 4 else f"in years 4 to {last}"
    by_year = f"by year {len(im['margin_path']['by_year'])}"
    if implied is None and margin is None:
        return (
            f"No revenue growth rate {years} and no operating margin {by_year}, in the ranges "
            f"the route reads, reaches the price. The route holds {held} and {target}."
        )
    growth = (
        f"No revenue growth rate {years} {_NO_RATE}."
        if implied is None
        else f"The price needs revenue growth of {_percent(implied)} a year {years}, against "
        f"{held} held."
    )
    if margin is None:
        return f"{growth} No operating margin {by_year} {_NO_RATE}."
    subject = "The price" if implied is None else "Or it"
    return (
        f"{growth} {subject} needs an operating margin of {_percent(margin)} {by_year}, against "
        f"a target of {target}."
    )


def _decline(im: Mapping[str, Any]) -> str:
    holds = f"The route holds {_percent(im['runoff_path']['d'])}."
    implied = im["implied_decline_rate"]
    if implied is None:
        return f"No decline rate {_NO_RATE}. {holds}"
    return (
        f"The price needs revenue to change by {_percent(implied)} a year after the consensus "
        f"years. {holds}"
    )


def _percent(x: float) -> str:
    """A rate as a percent to one decimal, a negative one with the minus sign."""
    return f"{x:,.1%}".replace("-", "−")
