"""What the price needs (``method.md`` 4.11).

On a row whose price is at or above the trim level, the designation ``well-above``, the value
alone says only that the method cannot reach the price. The sentences here say what the price
asks of the business, from the figures the row already solves at its price: the implied growth
against the belief on Mature Growth; the growth-route cross-check's implied growth on Mature
Stable; the implied held rate and the margin the price needs on the revenue-growth route; the
implied decline rate on Decline. Where a solve found no rate in its range, the sentence says so.
It computes nothing and moves nothing: the value, the levels and the designation stand as they
are.

A mature row charged at the required return in every year is a case of its own. There growth
adds no value: the solve's rate is often none and, when it finds one, comes from the uncharged
margin change alone and never measures the business's growth (5.8). So "no rate in the range"
would give the wrong reason, and a rate found there is not named. The sentence says that the
route charges growth at the hurdle rate, and on Mature Growth it names the growth the price
needs at the sensitivity's return above r (``implied_by_roic``), when that has one.

The margin the price needs is a target margin, the one the path reaches in the convergence year,
a setting that can lie past the forecast's last year; the sentence names the target and no year.

A row with no route's figures (a Start-up row, a refusal, a snapshot valued before a key
existed) has no sentence, and neither has a Mature Stable row whose cross-check refused, which
solved nothing at the price. A revenue-growth row under a ``high_growth_years`` setting of 3
holds no year at the held rate, so only its margin speaks.
"""

from collections.abc import Mapping
from typing import Any

from fairband.engine.types import Route

WELL_ABOVE = "well-above"
_NO_RATE = "in the range the route reads reaches the price"
_AT_R = (
    "The route charges growth at the hurdle rate, so growth adds no value and no growth rate "
    "reaches the price."
)


def price_needs(
    route: Route | None,
    intermediates: Mapping[str, Any],
    designation: str | None,
    required_return: float | None = None,
) -> str | None:
    """The sentences on what the price needs of a row on ``route`` with ``intermediates`` and
    the ``designation`` of its price against its value; ``None`` unless the price is well above
    the value and the row carries the figures. ``required_return`` is the row's own r, restated
    in its currency, by which a mature row charged at r in every year is told apart; without it
    no row is read as one."""
    if designation != WELL_ABOVE:
        return None
    try:
        match route:
            case "mature-growth":
                return _mature_growth(intermediates, required_return)
            case "mature-stable":
                return _mature_stable(intermediates, required_return)
            case "revenue-growth":
                return _revenue_growth(intermediates)
            case "decline":
                return _decline(intermediates)
    except (KeyError, IndexError, TypeError, AttributeError, ValueError):
        return None  # a record without the figures: no sentence
    return None


def _mature_growth(im: Mapping[str, Any], r: float | None) -> str:
    holds = f"The route holds {_percent(im['belief']['rate'])}."
    implied, runway = im["implied_growth"], im["runway"]
    if _charged_at_r(im, r):  # before the solve's rate, which measures no growth here (5.8)
        case = _case_above_r(im.get("implied_by_roic") or {}, r)
        if case is None:
            return f"{_AT_R} {holds}"
        at, growth = case
        return (
            f"{_AT_R} At a return of {_percent(at)} on new capital, the price needs long-run "
            f"earnings growth of {_percent(growth)} a year to year {runway}. {holds}"
        )
    if implied is None:
        return f"No long-run earnings growth rate {_NO_RATE}. {holds}"
    return (
        f"The price needs long-run earnings growth of {_percent(implied)} a year to year "
        f"{runway}. {holds}"
    )


def _mature_stable(im: Mapping[str, Any], r: float | None) -> str | None:
    cross_check = im["growth_route"]
    if cross_check.get("value_per_share") is None:
        return None
    holds = f"This route holds terminal growth, {_percent(im['charge']['growth_by_year'][-1])}."
    implied = cross_check["implied_growth"]
    if _charged_at_r(im, r):  # before the solve's rate, as on Mature Growth
        return f"{_AT_R} {holds}"
    if implied is None:
        return f"On the growth route's path, no long-run earnings growth rate {_NO_RATE}. {holds}"
    return (
        "On the growth route's path, the price needs long-run earnings growth of "
        f"{_percent(implied)} a year to year {im['runway']}. {holds}"
    )


def _revenue_growth(im: Mapping[str, Any]) -> str:
    implied, margin = im["implied_growth"], im["implied_margin"]
    last = im["revenue_path"]["high_growth_years"]
    target = _percent(im["margin_path"]["target"])
    margin_needs = (
        None
        if margin is None
        else f"needs a target operating margin of {_percent(margin)}, against {target}."
    )
    if last < 4:  # no held year: year 4 already fades, so only the margin speaks
        if margin_needs is None:
            return f"No target operating margin {_NO_RATE}. The route holds {target}."
        return f"The price {margin_needs}"
    held = _percent(im["growth_rates"][3])
    years = "in year 4" if last == 4 else f"in years 4 to {last}"
    if implied is None and margin_needs is None:
        return (
            f"No revenue growth rate {years} and no target operating margin, in the ranges "
            f"the route reads, reaches the price. The route holds {held} and {target}."
        )
    growth = (
        f"No revenue growth rate {years} {_NO_RATE}."
        if implied is None
        else f"The price needs revenue growth of {_percent(implied)} a year {years}, against "
        f"{held} held."
    )
    if margin_needs is None:
        return f"{growth} No target operating margin {_NO_RATE}."
    return f"{growth} {'The price' if implied is None else 'Or it'} {margin_needs}"


def _decline(im: Mapping[str, Any]) -> str:
    holds = f"The route holds {_percent(im['runoff_path']['d'])}."
    implied = im["implied_decline_rate"]
    if implied is None:
        return f"No decline rate {_NO_RATE}. {holds}"
    return f"The price needs a decline rate of {_percent(implied)} a year. {holds}"


def _charged_at_r(im: Mapping[str, Any], r: float | None) -> bool:
    """Whether the row charges growth at ``r`` in every year, year N's terminal return included,
    so that growth adds no value; never when the runway years go uncharged."""
    if r is None or im.get("charge_off"):
        return False
    returns = im["charge"]["return_by_year"]
    return bool(returns) and all(abs(x - r) <= 1e-12 for x in returns)


def _case_above_r(by_roic: Mapping[str, Any], r: float | None) -> tuple[float, float] | None:
    """Of the return sensitivity's implied growths, the one at its highest return above ``r``
    that found a rate, as (return, growth); ``None`` without one. The keys that name no rate
    (``runway``, ``ten-year``) are passed over."""
    cases = []
    for key, growth in by_roic.items():
        try:
            at = float(key)
        except ValueError:
            continue
        if r is not None and at > r and growth is not None:
            cases.append((at, float(growth)))
    return max(cases) if cases else None


def _percent(x: float) -> str:
    """A rate as a percent to one decimal, a negative one with the minus sign."""
    return f"{x:,.1%}".replace("-", "−")
