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
fallback years, the last ones kept. A chosen measure at or above r stands, with no cap. When the
marginal is not usable and the fallback years' capital sums to zero or below, the runway charge
is off. With fewer than ``min_years`` kept years the runway return is unavailable, and the charge
uses the terminal return in every year. Beside it the row records the newest year's marginal
return, the change in NOPAT over the change in average capital from the kept year before the
newest to the newest, with no usability test: it is shown and never used.

A chosen measure below r is read again on capital without goodwill and intangibles (``method.md``
4.6 rule 5): a past purchase's price sits in the capital and can push the measure below r while
the business itself earns more on what it reinvests. The same order runs on each kept year's
average capital less its average goodwill and intangibles, NOPAT unchanged: the marginal return
when usable there, else the fallback aggregate. Above r, the charge starts at that return, at
most the policy's ``return_without_goodwill_cap``, since the measure leaves out capital the
company paid for. When the marginal is not usable there and the fallback years' capital without
goodwill sums to zero or below while their NOPAT sums above zero, the business needs no capital
of its own and the charge starts at the cap. Otherwise the floor stands: the charge starts at r.
It stands too where purchases carried the capital's growth over the marginal span: the marginal
with goodwill is usable, so capital grew by the policy's share and NOPAT grew; the marginal
without goodwill is not; and goodwill and intangibles grew. The level of return on the
business's own capital then counts the bought earnings and none of their price, so it is not
read. The measures without goodwill are recorded on every row with ``min_years`` kept
years, for the agent, whichever measure the charge took.

The terminal return is r unless the moat is Wide. For Wide it is the chosen measure before the
floor, capped at the policy's cap and never below r; on a row whose charge starts at the return
without goodwill, that start under the same cap; the cap when the runway charge is off; r when
the runway return is unavailable. ``terminal_roic`` is the same rule on a given ROIC, for the
sensitivity.
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
    """A kept year: ``roic`` is ``None`` when the average capital is exactly zero. The average
    capital holds ``average_goodwill_and_intangibles``, the mean of goodwill plus intangibles at
    the year's opening and closing balance sheets, a line not presented counting as nil."""

    year: int
    nopat: float
    average_capital: float
    roic: float | None
    average_goodwill_and_intangibles: float = 0.0


@dataclass(frozen=True)
class RoicResult:
    aggregate: float | None
    years_used: int
    by_year: tuple[RoicYear, ...]
    flags: tuple[Flag, ...]


# The measure the runway return took. When the chosen measure was below r: "without-goodwill"
# when the return on capital without goodwill and intangibles lifted the start above r, else
# "floor".
Used = Literal["marginal", "three-year", "without-goodwill", "floor", "off", "unavailable"]


@dataclass(frozen=True)
class WithoutGoodwill:
    """The runway measures read on capital without goodwill and intangibles, NOPAT unchanged.

    ``measure`` is the marginal return when usable there, else the fallback aggregate
    (``three_year``, ``None`` when its capital sums to zero or below). ``capital_free`` says the
    marginal is not usable there and the fallback years' capital sums to zero or below while
    their NOPAT sums above zero: the business needs no capital of its own. ``bought`` says
    purchases carried the growth of the capital over the marginal span: the marginal with
    goodwill is usable, the one without is not, and goodwill and intangibles grew. Then the
    charge does not read these measures, whatever they say (``method.md`` 4.6 rule 5).
    """

    marginal: float | None
    marginal_usable: bool
    three_year: float | None
    measure: float | None
    capital_free: bool
    bought: bool = False


@dataclass(frozen=True)
class RunwayReturn:
    """The return the charge uses in the runway years and the measures it was chosen from.

    ``chosen`` is the measure before the floor (``None`` when the charge is off or the return is
    unavailable). ``value`` is what the charge uses: ``chosen`` when it is at or above r; below
    r, the return without goodwill under its cap when that is above r and purchases did not
    carry the capital's growth (``without_goodwill.bought``), else r; the terminal
    return when the charge is off or the return is unavailable. ``flags`` are the ones this step
    raises, which follow those of ``aggregate_roic``. ``one_year`` is the newest year's marginal
    return, shown and never used: ``None`` with fewer than two kept years or no change in capital.
    ``without_goodwill`` holds the measures on capital without goodwill and intangibles, read by
    the charge only when ``chosen`` is below r: ``None`` when the return is unavailable.
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
    one_year: float | None
    without_goodwill: WithoutGoodwill | None = None


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
        goodwill = (_goodwill_and_intangibles(opening) + _goodwill_and_intangibles(closing)) / 2
        kept.append((RoicYear(closing.year, profit, average, roic, goodwill), opening, closing))
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


def without_goodwill(by_year: Sequence[RoicYear], policy: Policy) -> WithoutGoodwill:
    """The runway measures of ``by_year`` on capital without goodwill and intangibles: each kept
    year's average capital less its average goodwill and intangibles, its NOPAT unchanged, under
    the policy's marginal span, usability test and fallback window; and whether purchases
    carried the capital's growth over the span (``WithoutGoodwill.bought``)."""
    rows = tuple(
        replace(
            y, average_capital=y.average_capital - y.average_goodwill_and_intangibles, roic=None
        )
        for y in by_year
    )
    span, growth_min = policy.marginal_return_span_years, policy.marginal_capital_growth_min
    marginal, usable = marginal_return(rows, span, growth_min)
    n = policy.fallback_return_years
    three_year, _ = window_aggregate(rows, n)
    capital_free = not usable and three_year is None and sum(y.nopat for y in rows[-n:]) > 0
    _, usable_with_goodwill = marginal_return(by_year, span, growth_min)
    bought = (
        usable_with_goodwill  # so the span exists: capital grew by the share, and NOPAT grew
        and not usable
        and by_year[-1].average_goodwill_and_intangibles
        > by_year[-1 - span].average_goodwill_and_intangibles
    )
    return WithoutGoodwill(
        marginal, usable, three_year, marginal if usable else three_year, capital_free, bought
    )


def runway_return(
    result: RoicResult, moat: Moat, policy: Policy, min_years: int = _MIN_YEARS
) -> RunwayReturn:
    """The return the charge uses in years 1 to N−1, from the kept years of ``result``: the
    marginal return when usable, else the aggregate over the fallback years. A measure below r
    gives way to the return on capital without goodwill and intangibles, under its cap, when that
    is above r and purchases did not carry the capital's growth, and to r otherwise. The charge
    is off when the marginal is not usable and the
    fallback years' capital sums to zero or below; the return is unavailable with fewer than
    ``min_years`` kept years. On every branch it records the newest year's marginal return, which
    the charge never uses.
    """
    r = policy.required_return
    ten_year = result.aggregate
    one_year, _ = marginal_return(result.by_year, 1, 0.0)  # None with fewer than two kept years
    if result.years_used < min_years:
        # aggregate_roic has flagged "roic-unavailable"; the charge takes the terminal return
        unavailable = RunwayReturn(
            "unavailable", None, False, None, ten_year, None, 0.0, False, (), one_year
        )
        return replace(unavailable, value=terminal_return(unavailable, moat, policy))

    span, growth_min = policy.marginal_return_span_years, policy.marginal_capital_growth_min
    marginal, usable = marginal_return(result.by_year, span, growth_min)
    n = policy.fallback_return_years
    three_year, _ = window_aggregate(result.by_year, n)
    chosen = marginal if usable else three_year
    organic = without_goodwill(result.by_year, policy)
    if chosen is None:  # the marginal is not usable and the fallback capital sums to zero or below
        off = RunwayReturn(
            "off", marginal, False, three_year, ten_year, None, 0.0, True, (), one_year, organic
        )
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
    value = chosen
    if chosen < r:
        below = f"The {_measure(usable)} return of {chosen:.1%} is below the required return"
        lifted = _lifted(organic, policy)
        if lifted is None:
            used, value = "floor", r
            why = (
                " The return on capital without goodwill and intangibles is not read: purchases "
                "carried the growth of the capital."
                if organic.bought
                else ""
            )
            flags = (
                Flag(
                    "return-floored",
                    "Return floored",
                    f"{below}, so the charge uses {r:.1%}.{why}",
                ),
            )
        else:
            used, value = "without-goodwill", lifted
            flags = (
                Flag(
                    "return-without-goodwill",
                    "Return without goodwill",
                    f"{below}. {_lifted_words(organic, lifted, policy)}",
                ),
            )
    return RunwayReturn(
        used, marginal, usable, three_year, ten_year, chosen, value, False, flags, one_year, organic
    )


def _lifted(organic: WithoutGoodwill, policy: Policy) -> float | None:
    """The return a charge whose measure is below r starts at instead, from the measures without
    goodwill and intangibles: the cap when the business needs no capital of its own; the measure
    when it is above r, at most the cap; ``None`` when the floor stands. It stands too where
    purchases carried the capital's growth (``organic.bought``): the level of return on the
    business's own capital then counts the bought earnings and none of their price, and says
    nothing of what the growth costs."""
    if organic.bought:
        return None
    cap = policy.return_without_goodwill_cap
    if organic.capital_free:
        return cap
    if organic.measure is not None and organic.measure > policy.required_return:
        return min(organic.measure, cap)
    return None


def _lifted_words(organic: WithoutGoodwill, lifted: float, policy: Policy) -> str:
    """The second sentence of the ``return-without-goodwill`` flag: the measure the start came
    from, and the cap where it applied."""
    if organic.measure is None:  # the business needs no capital of its own
        return (
            "Capital without goodwill and intangibles sums to zero or below over the last "
            f"{policy.fallback_return_years} ROIC years, so the charge starts at the cap, "
            f"{lifted:.1%}."
        )
    capped = " above the cap," if organic.measure > lifted else ""
    return (
        f"On capital without goodwill and intangibles the {_measure(organic.marginal_usable)} "
        f"return is {organic.measure:.1%},{capped} so the charge starts at {lifted:.1%}."
    )


def terminal_return(rr: RunwayReturn, moat: Moat, policy: Policy) -> float:
    """The terminal return: Wide reads the chosen measure before the floor, or the charge's
    start on a row that starts at the return without goodwill, under the rule of
    ``terminal_roic``, and takes the cap when the runway charge is off; otherwise r."""
    if moat == "Wide" and rr.used == "off":
        return policy.wide_terminal_roic_cap
    if rr.used == "without-goodwill":
        return terminal_roic(rr.value, moat, policy)
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
        case "without-goodwill":
            return f"{_without_goodwill_note(rr)}; with them the {_was(rr)}"
        case "floor":
            bought = rr.without_goodwill is not None and rr.without_goodwill.bought
            why = "; purchases carried the capital's growth" if bought else ""
            return f"floored at the required return; the {_was(rr)}{why}"
        case "off":
            return "charge off: capital at or below zero"
        case "unavailable":
            return f"unavailable: fewer than {_MIN_YEARS} ROIC years"


def _was(rr: RunwayReturn) -> str:
    """The measure below r that the charge did not take, as a note names it."""
    return f"{_measure(rr.marginal_usable)} was {rr.chosen:.1%}"


def _without_goodwill_note(rr: RunwayReturn) -> str:
    """The start of the note on a runway return read on capital without goodwill."""
    organic = rr.without_goodwill
    if organic is None or organic.measure is None:
        return "the cap: capital without goodwill and intangibles at or below zero"
    words = (
        f"{_measure(organic.marginal_usable)} return on capital without goodwill and intangibles"
    )
    return f"{words}, {organic.measure:.1%}, capped" if organic.measure > rr.value else words


def _measure(marginal_usable: bool) -> str:
    """A runway measure as a flag or a note names it: the marginal when usable, else the
    fallback aggregate."""
    return "five-year marginal" if marginal_usable else "three-year"


def _goodwill_and_intangibles(y: CapitalYear) -> float:
    return _nil(y.goodwill) + _nil(y.intangibles)


def _nil(x: float | None) -> float:
    return 0.0 if x is None else x
