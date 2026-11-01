"""The ten-year aggregate return on invested capital for the reinvestment charge (``design.md`` 6.6).

Invested capital is built from the operating side: current assets less cash and investments
(D3b), less current liabilities other than short-term debt and the current lease liability, plus
net property and equipment, lease right-of-use assets where reported (D3a), goodwill and the
issuer's total intangibles excluding goodwill (D17). Total current assets, total current
liabilities and net property and equipment are required. An optional line the issuer does not
present counts as nil under method ``not-presented-as-nil-v1`` and is flagged; it is never read
as a reported zero. NOPAT is operating income after the statutory marginal tax rate (D3).

A year's capital is the average of its opening and closing balances (D2), so ten years of NOPAT
need eleven balance sheets. A year drops out when its NOPAT or either balance is missing. The
aggregate is the sum of NOPAT over the sum of average capital across the last ten years kept.
Fewer than ten kept years is flagged; fewer than ``min_years`` leaves no aggregate, and the
capital sum is then not judged. A capital sum at or below zero leaves no aggregate and zeroes
the charge. A year whose average capital is exactly zero has no ROIC of its own but still counts
in the aggregate.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from fairband.engine.types import Flag
from fairband.policy import Moat, Policy

_WINDOW = 10
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


def aggregate_roic(years: Sequence[CapitalYear], min_years: int = 5) -> RoicResult:
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
                "no aggregate ROIC and the charge uses the terminal ROIC in every year.",
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
        capital = sum(row.average_capital for row in by_year)
        if capital <= 0:
            flags.append(
                Flag(
                    "charge-zeroed",
                    "Charge zeroed",
                    f"Average invested capital sums to zero or below over the {n} ROIC years, "
                    "so the reinvestment charge is set to zero.",
                )
            )
        else:
            aggregate = sum(row.nopat for row in by_year) / capital

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


def terminal_roic(aggregate: float | None, moat: Moat, policy: Policy) -> float:
    """Wide: the aggregate capped at the policy's cap and never below r; otherwise r."""
    r = policy.required_return
    if moat != "Wide" or aggregate is None:
        return r
    return max(r, min(aggregate, policy.wide_terminal_roic_cap))


def _nil(x: float | None) -> float:
    return 0.0 if x is None else x
