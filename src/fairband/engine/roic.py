"""The return on invested capital: the ten-year aggregate (``design.md`` 6.6), and the runway
return and the terminal return the reinvestment charge reads (calibration spec 5.1 and 5.3).

Invested capital is built from the operating side: current assets less cash and investments
(D3b), less current liabilities other than short-term debt and the current lease liability, plus
net property and equipment, lease right-of-use assets where reported (D3a), goodwill and the
issuer's total intangibles excluding goodwill (D17). Total current assets, total current
liabilities and net property and equipment are required. An optional line the issuer does not
present counts as nil under method ``not-presented-as-nil-v1`` and is flagged; it is never read
as a reported zero. NOPAT is operating income after the statutory marginal tax rate (D3).

A year's capital is the average of its opening and closing balances (D2), so ten years of NOPAT
need eleven balance sheets. A year drops out when its NOPAT or either balance is missing; the
last ten years kept are the ROIC years. The ten-year aggregate is the sum of NOPAT over the sum
of average capital across them: it is shown and feeds the sensitivity, never the charge. Fewer
than ten kept years is flagged; fewer than ``min_years`` leaves no aggregate, and the capital sum
is then not judged. A capital sum at or below zero leaves the ten-year aggregate unavailable. A
year whose average capital is exactly zero has no ROIC of its own but still counts in the
aggregate.

The runway return feeds the charge in years 1 to N−1. It is the marginal return on new capital,
the change in NOPAT over the change in average capital from the kept year the policy's span
before the newest to the newest, when that is usable: capital grew, by at least the policy's
share of the earlier capital, and NOPAT grew. Otherwise it is the aggregate over the policy's
fallback years, the last ones kept. The chosen measure is floored at r, with no cap. When the
marginal is not usable and the fallback years' capital sums to zero or below, the runway charge
is off. With fewer than ``min_years`` kept years the runway return is unavailable, and the charge
uses the terminal return in every year.

The terminal return is r unless the moat is Wide. For Wide it is the chosen measure before the
floor, capped at the policy's cap and never below r; the cap when the runway charge is off; r
when the runway return is unavailable. ``terminal_roic`` is the same rule on a given ROIC, for
the sensitivity.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Literal

from fairband.engine.types import Flag
from fairband.policy import Moat, Policy

_WINDOW = 10
_MIN_YEARS = 5
_NIL_METHOD = "not-presented-as-nil-v1"

# The optional balance-sheet lines in field order, with the words a flag sentence uses for each.
_OPTIONAL_LINES = {
    "cash_and_investments": "cash and investments",
    "short_term_debt": "short-term debt",
    "current_lease_liability": "the current lease liability",
    "lease_rou_asset": "lease right-of-use assets",
    "goodwill": "goodwill",
    "intangibles": "intangible assets",
}


@dataclass(frozen=True)
class CapitalYear:
    """One fiscal year's operating income, statutory tax rate and year-end balance sheet."""

    year: int
    operating_income: float | None
    tax_rate: float | None
    total_current_assets: float | None
    cash_and_investments: float | None
    total_current_liabilities: float | None
    short_term_debt: float | None
    current_lease_liability: float | None
    net_ppe: float | None
    lease_rou_asset: float | None
    goodwill: float | None
    intangibles: float | None


@dataclass(frozen=True)
class RoicYear:
    """A kept year: ``roic`` is ``None`` when the average capital is exactly zero."""

    year: int
    nopat: float
    average_capital: float
    roic: float | None


@dataclass(frozen=True)
class RoicResult:
    aggregate: float | None
    years_used: int
    by_year: tuple[RoicYear, ...]
    flags: tuple[Flag, ...]


# The measure the runway return took: "floor" when the chosen measure was below r.
Used = Literal["marginal", "three-year", "floor", "off", "unavailable"]


@dataclass(frozen=True)
class RunwayReturn:
    """The return the charge uses in the runway years and the measures it was chosen from.

    ``chosen`` is the measure before the floor (``None`` when the charge is off or the return is
    unavailable). ``value`` is what the charge uses: ``chosen`` floored at r, or the terminal
    return when the charge is off or the return is unavailable. ``flags`` are the ones this step
    raises, which follow those of ``aggregate_roic``.
    """

    used: Used
    marginal: float | None
    marginal_usable: bool
    three_year: float | None
    ten_year: float | None
    chosen: float | None
    value: float
    charge_off: bool
    flags: tuple[Flag, ...]


def invested_capital(y: CapitalYear) -> float | None:
    """Operating working capital plus long-term operating assets at the year end.

    ``None`` when a required total is missing; an optional line that is missing counts as nil.
    """
    tca, tcl, ppe = y.total_current_assets, y.total_current_liabilities, y.net_ppe
    if tca is None or tcl is None or ppe is None:
        return None
    assets = tca - _nil(y.cash_and_investments)
    liabilities = tcl - _nil(y.short_term_debt) - _nil(y.current_lease_liability)
    long_term = ppe + _nil(y.lease_rou_asset) + _nil(y.goodwill) + _nil(y.intangibles)
    return assets - liabilities + long_term


def not_presented(y: CapitalYear) -> tuple[str, ...]:
    """The optional balance-sheet lines missing from the year, in field order."""
    return tuple(name for name in _OPTIONAL_LINES if getattr(y, name) is None)


def nopat(y: CapitalYear) -> float | None:
    """Operating income after the statutory marginal tax rate; ``None`` if either is missing."""
    if y.operating_income is None or y.tax_rate is None:
        return None
    return y.operating_income * (1 - y.tax_rate)


def aggregate_roic(years: Sequence[CapitalYear], min_years: int = _MIN_YEARS) -> RoicResult:
    """Sum of NOPAT over sum of average capital for the last ten usable years, oldest first."""
    kept: list[tuple[RoicYear, CapitalYear, CapitalYear]] = []
    for opening, closing in pairwise(years):
        profit = nopat(closing)
        start, end = invested_capital(opening), invested_capital(closing)
        if profit is None or start is None or end is None:
            continue
        average = (start + end) / 2
        roic = profit / average if average != 0 else None
        kept.append((RoicYear(closing.year, profit, average, roic), opening, closing))
    kept = kept[-_WINDOW:]
    by_year = tuple(row for row, _, _ in kept)
    n = len(by_year)

    aggregate: float | None = None
    flags: list[Flag] = []
    if n < min_years:
        flags.append(
            Flag(
                "roic-unavailable",
                "ROIC unavailable",
                f"Fewer than {min_years} fiscal years have the data for ROIC ({n}), so there is "
                "no aggregate ROIC; on the mature routes the charge uses the terminal ROIC in "
                "every year.",
            )
        )
    else:
        if n < _WINDOW:
            flags.append(
                Flag(
                    "roic-on-n-years",
                    f"ROIC on {n} years",
                    f"The aggregate ROIC covers {n} fiscal years instead of ten.",
                )
            )
        aggregate, _ = window_aggregate(by_year, _WINDOW)
        if aggregate is None:
            flags.append(
                Flag(
                    "ten-year-roic-unavailable",
                    "Ten-year ROIC unavailable",
                    f"Average invested capital sums to zero or below over the {n} ROIC years, "
                    "so the ten-year ROIC is unavailable.",
                )
            )

    missing = {name for _, a, b in kept for name in (*not_presented(a), *not_presented(b))}
    flags.extend(
        Flag(
            f"line-not-presented:{name}",
            f"Line not presented: {name}",
            f"A balance sheet in the ROIC years does not present {words}; it counted as nil "
            f"under method {_NIL_METHOD}.",
        )
        for name, words in _OPTIONAL_LINES.items()
        if name in missing
    )
    return RoicResult(aggregate=aggregate, years_used=n, by_year=by_year, flags=tuple(flags))


def window_aggregate(by_year: Sequence[RoicYear], n: int) -> tuple[float | None, float]:
    """Sum of NOPAT over sum of average capital across the last ``n`` kept years, and that
    capital sum; the aggregate is ``None`` when the capital sum is at or below zero."""
    rows = by_year[max(0, len(by_year) - n) :]
    capital = sum(row.average_capital for row in rows)
    if capital <= 0:
        return None, capital
    return sum(row.nopat for row in rows) / capital, capital


def marginal_return(
    by_year: Sequence[RoicYear], span: int, growth_min: float
) -> tuple[float | None, bool]:
    """The change in NOPAT over the change in average capital from the kept year ``span``
    positions before the newest to the newest, and whether it is usable: capital grew, by at
    least ``growth_min`` of the earlier year's capital, and NOPAT grew.

    ``(None, False)`` with fewer than ``span + 1`` kept years or no change in capital.
    """
    if len(by_year) < span + 1:
        return None, False
    first, last = by_year[-1 - span], by_year[-1]
    delta_capital = last.average_capital - first.average_capital
    if delta_capital == 0:
        return None, False
    delta_nopat = last.nopat - first.nopat
    usable = (
        delta_capital > 0
        and delta_capital >= growth_min * abs(first.average_capital)
        and delta_nopat > 0
    )
    return delta_nopat / delta_capital, usable


def runway_return(
    result: RoicResult, moat: Moat, policy: Policy, min_years: int = _MIN_YEARS
) -> RunwayReturn:
    """The return the charge uses in years 1 to N−1, from the kept years of ``result``: the
    marginal return when usable, else the aggregate over the fallback years, floored at r. The
    charge is off when the marginal is not usable and the fallback years' capital sums to zero or
    below; the return is unavailable with fewer than ``min_years`` kept years.
    """
    r = policy.required_return
    ten_year = result.aggregate
    if result.years_used < min_years:
        # aggregate_roic has flagged "roic-unavailable"; the charge takes the terminal return
        unavailable = RunwayReturn("unavailable", None, False, None, ten_year, None, 0.0, False, ())
        return replace(unavailable, value=terminal_return(unavailable, moat, policy))

    span, growth_min = policy.marginal_return_span_years, policy.marginal_capital_growth_min
    marginal, usable = marginal_return(result.by_year, span, growth_min)
    n = policy.fallback_return_years
    three_year, _ = window_aggregate(result.by_year, n)
    chosen = marginal if usable else three_year
    if chosen is None:  # the marginal is not usable and the fallback capital sums to zero or below
        off = RunwayReturn("off", marginal, False, three_year, ten_year, None, 0.0, True, ())
        terminal = terminal_return(off, moat, policy)
        zeroed = Flag(
            "charge-zeroed",
            "Charge zeroed",
            "The marginal return is not usable and average invested capital sums to zero or "
            f"below over the last {n} ROIC years, so the runway charge is zero; the terminal "
            f"still charges at {terminal:.1%}.",
        )
        return replace(off, value=terminal, flags=(zeroed,))

    flags: tuple[Flag, ...] = ()
    used: Used = "marginal" if usable else "three-year"
    if chosen < r:
        used = "floor"
        flags = (
            Flag(
                "return-floored",
                "Return floored",
                f"The {_measure(usable)} return of {chosen:.1%} is below the required return, "
                f"so the charge uses {r:.1%}.",
            ),
        )
    return RunwayReturn(
        used, marginal, usable, three_year, ten_year, chosen, max(r, chosen), False, flags
    )


def terminal_return(rr: RunwayReturn, moat: Moat, policy: Policy) -> float:
    """The terminal return: Wide reads the chosen measure before the floor, under the rule of
    ``terminal_roic``, and takes the cap when the runway charge is off; otherwise r."""
    if moat == "Wide" and rr.used == "off":
        return policy.wide_terminal_roic_cap
    return terminal_roic(rr.chosen, moat, policy)


def terminal_roic(aggregate: float | None, moat: Moat, policy: Policy) -> float:
    """Wide: the aggregate capped at the policy's cap and never below r; otherwise r."""
    r = policy.required_return
    if moat != "Wide" or aggregate is None:
        return r
    return max(r, min(aggregate, policy.wide_terminal_roic_cap))


def runway_note(rr: RunwayReturn) -> str:
    """The note on the runway-return input: the measure the charge used, and why."""
    match rr.used:
        case "marginal":
            return "five-year marginal return on new capital"
        case "three-year":
            return "three-year aggregate ROIC (marginal not usable)"
        case "floor":
            return (
                f"floored at the required return; the {_measure(rr.marginal_usable)} was "
                f"{rr.chosen:.1%}"
            )
        case "off":
            return "charge off: capital at or below zero"
        case "unavailable":
            return f"unavailable: fewer than {_MIN_YEARS} ROIC years"


def _measure(marginal_usable: bool) -> str:
    """The measure a floored runway return was chosen from, as a flag or a note names it."""
    return "five-year marginal" if marginal_usable else "three-year"


def _nil(x: float | None) -> float:
    return 0.0 if x is None else x
