"""The warning flags of spec 6.7: each warns and never changes a value, a level or a designation.

The margin flag is ``mech/1.2``'s. The margin is operating income ÷ revenue for each fiscal year
that has both and a positive revenue; the median and the high run over the last ten such years,
and the flag needs at least ``margin_flag_min_years`` of them. It fires when the trailing margin
is ``margin_flag_ratio`` times the median or more (a positive median), or when it is above the
high by ``margin_flag_above_high`` of the high's size or more, so a loss-making history that turns
profitable fires too. Its word reads the history: "Newly profitable" for a median at or below
zero, "Possible cycle peak" for a loss year in the window, else "Margin above history".
``margin_history`` is no flag: the ten-year median operating margin on the flag's window and the
ten-year median net margin on the same rule, each with its count of years, which every result
whose series is not empty carries, a refusal too, for the research agent's judgment of a cyclical
company (spec 2026-11-13 11).

The gate flags are the three ``mech/1.2`` gate tests on the trailing figures, kept as flags. The
cash-flow statement signs capital spending as an outflow, so ``capex`` is negative for spending:
free cash flow is ``cfo + capex`` and the spending is ``-capex``.

The warning ``one-time-items`` (spec 2026-11-19 7.2), on Mature Stable alone: GAAP trailing
diluted EPS and the street trailing EPS differ by ``one_time_items_share`` of the GAAP figure's
size or more, |GAAP − street| ÷ |GAAP| (``one_time_share``), so the trailing earnings, which the
mechanical value keeps, may hold one-time items; silent without a street figure or with a GAAP
EPS of zero. The route passes it to ``route_steps.trailing_flags``, and leaves it out under an
agent's ``earnings.nri_gap``, which decides the items.

The two stock-pay notes follow the anchor's flags on Mature Growth (spec 2026-11-13 7.1).
``stock-pay-missing``: the trailing stock pay is zero, or a trailing period's is, while a fiscal
year on file holds stock pay above zero, so the stored figure, and the stock-pay charge on the
consensus with it, may be nil or short. ``sbc-basis-uncertain``: the basis test may misread, one
sentence for each reason that holds. Stock pay is material when its after-tax figure a share is
``sbc_material_share`` of a street trailing EPS above zero or more. Reason 1: the test reads
``includes-sbc`` on a material stock pay where GAAP trailing EPS and the street's differ by
``one_time_items_share`` or more, the warning's test (spec 2026-11-19 7.3), so a one-time item
may sit in GAAP EPS and hide the gap. Reason 2: the same reading on a material stock pay with a
trailing effective tax rate, income tax over a pre-tax income above zero, at or below
``sbc_basis_tax_share`` of the statutory rate, a low tax that may close the gap. Reason 3: the
test reads ``excludes-sbc`` on a stock pay above zero and the street EPS lies above GAAP, as the
test reads it, by ``sbc_basis_gap_multiple`` times the after-tax stock pay a share or more, so the
adjusted figure leaves out far more than stock pay. The stock pay is the one the anchor read, an
agent's ``earnings.sbc`` in place of the stored figure (spec 2026-11-13 7.2).

The share-count warning (spec 2026-11-13 8): ``share-count-gap`` when the market cap over the price
times the diluted count is outside ``share_count_gap_band``, an edge being inside. The market cap is
the quote's, else the profile's or the screener's, and the price the quote's, both in US dollars on
every row, so the ratio has one currency; the count is the one the row reads. Either figure may be
the wrong one: the count may leave out a share class or units that convert to shares, so that the
value a share of the row can be wrong by the ratio, or the market cap may leave a class out.

The sheet-shift note (spec 2026-11-13 12.5): ``sheet-shift`` when the newest balance sheet is a
quarter's and a line of it differs sharply from the newest annual sheet's, one sentence for each
reason that holds. A figure is nil when the sheet does not present it or holds it at or below
zero. Reason 1: the quarter's short-term and long-term debt are both nil and the annual sheet's
sum above zero, so the debt may be short, or the annual line held more than borrowings. Reasons 2
and 3: the quarter's cash and equivalents, or its short-term investments, are nil and the annual
sheet's line is above zero, so the cash may be short. Reason 4: the two minority interests, each
nil counting as zero, differ by more than ``sheet_shift_multiple`` times either way, a figure
above zero against none included, so the vendor's line may be wrong; exactly that multiple is
silent. A balance that only rose or fell raises nothing.

``QUALITY_WARNINGS`` are the twelve flags that say the value may be wrong because the business or
its figures are unusual (spec 2026-11-04 9.5, spec 2026-11-13 8), ``one-time-items`` in the place
of ``large-nri`` since method 1.7 (spec 2026-11-19 7.2); ``flag_count`` counts them on a row, so a
row valued before 1.7 counts neither ``large-nri`` nor ``consensus-basis-unknown``. Every other
flag is a note: the classifier checks, the thin-consensus flags, the unknown inputs, the engine's
mechanics and the bookkeeping flags. A note is shown and never counted.
"""

import math
import statistics
from collections.abc import Callable, Collection, Sequence

from fairband.engine.anchor import SbcBasis, StockPayHistory, TrailingFigures
from fairband.engine.balance import SheetFigures
from fairband.engine.classifier import FiscalYear, Series, operating_margin
from fairband.engine.types import Flag
from fairband.policy import Policy

_MARGIN_WINDOW = 10  # mech/1.2: the median and the high over the last ten fiscal years
# A share of GAAP EPS exactly ``one_time_items_share`` from the street's is at the threshold,
# whatever binary floating point does to it: 1.00 against 1.20 gives 0.19999999999999996.
_ONE_TIME_TOLERANCE = 1e-12

QUALITY_WARNINGS: frozenset[str] = frozenset(
    {
        "one-time-items",
        "value-spread",
        "margin-flag",
        "z-distress",
        "f-score-low",
        "reinvesting-in-decline",
        "equity-raise",
        "negative-fcf",
        "heavy-capex",
        "burn-cover-short",
        "consensus-recovery",
        "share-count-gap",
    }
)


def flag_count(flags: Sequence[Flag]) -> int:
    """The number of the row's quality warnings; notes do not count."""
    return sum(1 for f in flags if f.code in QUALITY_WARNINGS)


def median_margin(series: Series, window: int = _MARGIN_WINDOW) -> float | None:
    """The median operating margin over the last ``window`` fiscal years that have one, the
    median the margin flag uses; ``None`` when no year has one."""
    history = _margin_history(series, window)
    return statistics.median(history) if history else None


def margin_flag(series: Series, ttm_margin: float | None, policy: Policy) -> Flag | None:
    """The ``margin-flag`` for the trailing operating margin against its own history."""
    history = _margin_history(series, _MARGIN_WINDOW)
    if ttm_margin is None or len(history) < policy.margin_flag_min_years:
        return None
    median, high = statistics.median(history), max(history)
    by_median = median > 0 and ttm_margin >= policy.margin_flag_ratio * median
    by_high = ttm_margin > high and ttm_margin >= high + policy.margin_flag_above_high * abs(high)
    if not (by_median or by_high):
        return None
    loss = min(history) < 0  # the revenue is positive, so a negative margin is an operating loss
    if median <= 0:
        word = "Newly profitable"
    elif loss:
        word = "Possible cycle peak"
    else:
        word = "Margin above history"
    sentence = (
        f"The trailing operating margin is {ttm_margin:.1%}, against a median of {median:.1%} "
        f"and a high of {high:.1%} over {len(history)} fiscal years"
    )
    if loss:
        sentence += "; the window holds a loss year"
    return Flag("margin-flag", word, sentence + ".")


def gate_flags(
    trailing: TrailingFigures, market_cap: float | None, policy: Policy
) -> tuple[Flag, ...]:
    """``equity-raise``, ``negative-fcf`` and ``heavy-capex``, in that order, for those that fire;
    a test with a missing input does not fire."""
    flags: list[Flag] = []
    issued, cfo, capex = trailing.equity_issued, trailing.cfo, trailing.capex
    if (
        issued is not None
        and market_cap is not None
        and market_cap > 0
        and issued >= policy.equity_raise_share * market_cap
    ):
        flags.append(
            Flag(
                "equity-raise",
                "Equity raise",
                f"Trailing stock issuance is {issued / market_cap:.1%} of the market cap, at or "
                f"above the {policy.equity_raise_share:.1%} that counts as a raise.",
            )
        )
    if cfo is not None and capex is not None and cfo + capex < 0:
        flags.append(
            Flag(
                "negative-fcf",
                "Negative free cash flow",
                f"Trailing operating cash flow of {cfo:,.0f} less capital spending of "
                f"{-capex:,.0f} leaves a free cash flow of {cfo + capex:,.0f}.",
            )
        )
    if cfo is not None and capex is not None and cfo > 0 and -capex > policy.capex_ocf_flag * cfo:
        flags.append(
            Flag(
                "heavy-capex",
                "Heavy capex",
                f"Trailing capital spending is {-capex / cfo:.1%} of operating cash flow, "
                f"above {policy.capex_ocf_flag:.1%}.",
            )
        )
    return tuple(flags)


def one_time_share(gaap_eps: float | None, street_eps: float | None) -> float | None:
    """|GAAP − street| ÷ |GAAP|, the share of GAAP trailing EPS by which the street trailing EPS
    differs from it, in sizes, so a GAAP loss against a street profit reads as two losses do;
    ``None`` without both figures or with a GAAP EPS of 0."""
    if gaap_eps is None or street_eps is None or gaap_eps == 0:
        return None
    return abs(gaap_eps - street_eps) / abs(gaap_eps)


def one_time_items_flag(
    gaap_eps: float | None, street_eps: float | None, policy: Policy, currency: str = "USD"
) -> Flag | None:
    """``one-time-items`` (spec 2026-11-19 7.2) when ``one_time_share`` of the two figures is
    ``one_time_items_share`` or more, the edge firing within 1e-12 (method 4.1a): the sentence
    names both figures after ``$`` or the reporting ``currency``'s code, a negative one with the
    minus sign first, and the share; ``None`` where the share is ``None`` or below the
    threshold. Reason 1 of ``sbc-basis-uncertain`` reads this test (``route_mature_growth``)."""
    share = one_time_share(gaap_eps, street_eps)
    if gaap_eps is None or street_eps is None or share is None:
        return None
    threshold = policy.one_time_items_share
    if share < threshold - _ONE_TIME_TOLERANCE:
        return None
    return Flag(
        "one-time-items",
        "One-time items",
        f"GAAP trailing EPS is {_money(gaap_eps, currency)} and the analysts' is "
        f"{_money(street_eps, currency)}, apart by {share:,.1%} of GAAP EPS, at or above "
        f"{threshold:.1%}. The trailing earnings may hold one-time items, which the mechanical "
        "value keeps; a review takes them out through `earnings.nri_gap`.",
    )


def stock_pay_missing_flag(
    sbc_ttm: float | None, history: StockPayHistory | None, currency: str = "USD"
) -> Flag | None:
    """``stock-pay-missing`` when the trailing stock pay ``sbc_ttm`` is zero, or ``history``
    counts a trailing period at zero, while a fiscal year holds stock pay above zero: the
    sentence names the newest such year and its figure in the reporting ``currency``. ``None``
    without the trailing figure, without a history, or with no fiscal year above zero."""
    if sbc_ttm is None or history is None:
        return None
    year, figure = history.newest_year, history.newest_figure
    if year is None or figure is None or (sbc_ttm != 0 and history.zero_periods == 0):
        return None
    shows = f"while fiscal {year} shows {millions(figure, currency)}"
    if sbc_ttm == 0:
        sentence = (
            f"The trailing stock pay is nil {shows}, so the stored figure may be missing and the "
            "stock-pay charge on the consensus nil."
        )
    else:
        n = history.zero_periods
        periods = "1 trailing period" if n == 1 else f"{n} trailing periods"
        sentence = (
            f"The stock pay is nil in {periods} {shows}, so the trailing figure may be short, and "
            "the stock-pay charge on the consensus with it."
        )
    return Flag("stock-pay-missing", "Stock pay missing", sentence)


def sbc_basis_uncertain_flag(
    basis: SbcBasis,
    t: TrailingFigures,
    street_ttm_eps: float | None,
    shares: float,
    tax_rate: float,
    one_time: float | None,
    policy: Policy,
    currency: str = "USD",
) -> Flag | None:
    """``sbc-basis-uncertain`` when the stock-pay basis test may misread (the module docstring),
    one sentence for each reason that holds, joined by a space: ``t`` holds the trailing figures
    as the test reads them, so the after-tax stock pay a share is ``t.sbc`` × (1 − ``tax_rate``)
    ÷ ``shares``, as the anchor reads it, and the gap of reason 3 is the street EPS less
    ``t.eps_diluted``; ``one_time`` is the share by which GAAP trailing EPS and the street's
    differ where the warning's test holds, at ``one_time_items_share`` or more, which reason 1
    reads and its sentence prints, else ``None``. Each figure a share is printed after ``$`` or
    the reporting ``currency``'s code. ``None`` when no reason holds, or without the stock pay,
    the street EPS or a positive share count."""
    if t.sbc is None or street_ttm_eps is None or shares <= 0:
        return None
    per_share = t.sbc * (1 - tax_rate) / shares
    material = street_ttm_eps > 0 and per_share >= policy.sbc_material_share * street_ttm_eps
    stock_pay = _money(per_share, currency)
    reasons: list[str] = []
    if basis == "includes-sbc" and material:
        reads = (
            f"The basis test reads the consensus as counting stock pay, {stock_pay} a share "
            f"after tax and {per_share / street_ttm_eps:.1%} of street trailing EPS, while"
        )
        if one_time is not None:
            reasons.append(
                f"{reads} GAAP trailing EPS and the analysts' differ by {one_time:,.1%}, so a "
                "one-time item may sit in GAAP EPS and hide the gap."
            )
        effective = _effective_tax_rate(t)
        if effective is not None and effective <= policy.sbc_basis_tax_share * tax_rate:
            reasons.append(
                f"{reads} a trailing tax rate of {effective:.1%}, at or below "
                f"{policy.sbc_basis_tax_share:.1%} of the statutory {tax_rate:.1%}, may close the "
                "gap."
            )
    gaap = t.eps_diluted
    if basis == "excludes-sbc" and per_share > 0 and gaap is not None:
        gap = street_ttm_eps - gaap
        if gap >= policy.sbc_basis_gap_multiple * per_share:
            reasons.append(
                f"The street trailing EPS is {_money(gap, currency)} above the GAAP one, "
                f"{gap / per_share:,.1f} times the stock pay of {stock_pay} a share after "
                "tax: the adjusted figure leaves out far more than stock pay, and the figures "
                "cannot say whether it leaves out stock pay too."
            )
    if not reasons:
        return None
    return Flag("sbc-basis-uncertain", "Stock-pay basis uncertain", " ".join(reasons))


def share_count_flag(
    market_cap: float | None, price: float | None, shares: float | None, policy: Policy
) -> Flag | None:
    """``share-count-gap`` when ``market_cap`` ÷ (``price`` × ``shares``) is below the low of
    ``share_count_gap_band`` or above its high: the sentence gives both figures, the ratio to two
    decimals, the band and the two readings. ``market_cap`` is the quote's, else the profile's or
    the screener's, and ``price`` the quote's, both in US dollars; ``shares`` is the diluted count
    in force. ``None`` inside the band, its edges included, or without the three figures, a figure
    at or below zero or not finite being none."""
    if market_cap is None or price is None or shares is None:
        return None
    if not all(math.isfinite(x) and x > 0 for x in (market_cap, price, shares)):
        return None
    low, high = policy.share_count_gap_band
    implied = price * shares
    ratio = market_cap / implied
    if low <= ratio <= high:
        return None
    return Flag(
        "share-count-gap",
        "Share count and market cap disagree",
        f"The market cap is {millions(market_cap)} and the price of ${price:,.2f} times the "
        f"diluted count of {shares / 1e6:,.1f} million shares is {millions(implied)}: a ratio of "
        f"{ratio:.2f}, outside {low:.2f} to {high:.2f}. The count may leave out a share class or "
        "units that convert to shares, or the market cap may leave a class out.",
    )


def sheet_shift_flag(
    quarter: SheetFigures,
    annual: SheetFigures,
    policy: Policy,
    currency: str = "USD",
    decided: Collection[str] = (),
) -> Flag | None:
    """``sheet-shift`` when a line of ``quarter``, the quarter's sheet in use, differs sharply
    from ``annual``'s, the newest annual sheet (the module docstring): one sentence for each
    reason that holds, the debt, the cash and equivalents, the short-term investments, the
    minority interest, joined by a space, the first naming the quarter's sheet and each later one
    starting "It shows". Money is in millions after ``$`` or the reporting ``currency``'s code.
    ``decided`` holds the override tags applied in a review: ``balance.debt`` silences the debt's
    sentence, ``balance.cash`` the two cash lines', ``balance.minority`` the minority interest's.
    ``None`` with no sentence left."""
    shown: list[str] = []
    since = f"where {annual.label} showed"
    if "balance.debt" not in decided:
        debt = (annual.short_term_debt or 0.0) + (annual.long_term_debt or 0.0)
        if _nil(quarter.short_term_debt) and _nil(quarter.long_term_debt) and debt > 0:
            shown.append(
                f"no debt {since} {millions(debt, currency)}, so the debt may be short, or the "
                "annual line held more than borrowings."
            )
    if "balance.cash" not in decided:
        for words, held, before in (
            (
                "cash and cash equivalents",
                quarter.cash_and_equivalents,
                annual.cash_and_equivalents,
            ),
            (
                "short-term investments",
                quarter.short_term_investments,
                annual.short_term_investments,
            ),
        ):
            if _nil(held) and before is not None and before > 0:
                shown.append(
                    f"no {words} {since} {millions(before, currency)}, so the cash may be short."
                )
    if "balance.minority" not in decided:
        q, a = _at_book(quarter.minority_interest), _at_book(annual.minority_interest)
        m = policy.sheet_shift_multiple
        wrong = "so the vendor's line may be wrong."
        if q > 0 and a == 0:
            shown.append(f"a minority interest of {millions(q, currency)} {since} none, {wrong}")
        elif q == 0 and a > 0:
            shown.append(f"no minority interest {since} {millions(a, currency)}, {wrong}")
        elif q > 0 and a > 0 and (q > m * a or a > m * q):
            shown.append(
                f"a minority interest of {millions(q, currency)} {since} "
                f"{millions(a, currency)}, more than {m:g} times apart, {wrong}"
            )
    if not shown:
        return None
    first = f"The balance sheet of {quarter.label} shows {shown[0]}"
    sentence = " ".join([first, *(f"It shows {words}" for words in shown[1:])])
    return Flag("sheet-shift", "Balance sheet shift", sentence)


def _nil(figure: float | None) -> bool:
    """A line the sheet does not present, or holds at or below zero."""
    return figure is None or figure <= 0


def _at_book(figure: float | None) -> float:
    """A minority interest as the note reads it: nil where the sheet does not present it or
    holds it at or below zero, as the routes count it (spec 2026-11-13 13)."""
    return 0.0 if figure is None else max(0.0, figure)


def _money(x: float, currency: str) -> str:
    """A figure a share to two decimals after ``$``, or after ``currency``'s code on a row in
    another currency, a negative one with the minus sign first: "−$0.60", "SEK 0.40"."""
    sign = "$" if currency == "USD" else f"{currency} "
    return f"{'−' if x < 0 else ''}{sign}{abs(x):,.2f}"


def _effective_tax_rate(t: TrailingFigures) -> float | None:
    """The trailing income tax over the trailing pre-tax income; ``None`` without both, or on a
    pre-tax income at or below zero."""
    if t.income_tax is None or t.pretax_income is None or t.pretax_income <= 0:
        return None
    return t.income_tax / t.pretax_income


def millions(x: float, currency: str = "USD") -> str:
    """A money figure in millions to one decimal, a negative one with the minus sign: a dollar
    figure after ``$``, one in another currency after its code (``SEK 1,234.5 million``)."""
    sign = "$" if currency == "USD" else f"{currency} "
    return f"{'−' if x < 0 else ''}{sign}{abs(x) / 1e6:,.1f} million"


def long_runway_flag(
    runway: int, belief: float, implied: float | None, policy: Policy
) -> Flag | None:
    """``long-runway-high-growth`` on the longest runway when the belief or the implied growth is
    ``long_runway_growth_flag`` or more."""
    threshold = policy.long_runway_growth_flag
    if runway != max(policy.runway_years.values()):
        return None
    parts: list[str] = []
    if belief >= threshold:
        parts.append(f"the growth belief is {belief:.1%}")
    if implied is not None and implied >= threshold:
        parts.append(f"the implied growth is {implied:.1%}")
    if not parts:
        return None
    return Flag(
        "long-runway-high-growth",
        "Long runway, high growth",
        f"The runway is {runway} years and {' and '.join(parts)}, at or above {threshold:.1%}.",
    )


def value_spread_flag(
    values: Sequence[float | None],
    policy: Policy,
    tested: str = "the ROIC values or runways tested",
) -> Flag | None:
    """``value-spread`` when the values (``None`` skipped) span ``value_spread_flag`` of the
    lowest or more; ``None`` with fewer than two values or a lowest value at or below zero.
    ``tested`` names what the values were computed across, for the sentence."""
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return None
    low, high = min(present), max(present)
    if low <= 0:
        return None
    spread = (high - low) / low
    if spread < policy.value_spread_flag:
        return None
    return Flag(
        "value-spread",
        "Value spread",
        f"The value ranges from {low:,.2f} to {high:,.2f} across {tested}, a spread of "
        f"{spread:.1%}, at or above {policy.value_spread_flag:.1%}.",
    )


def margin_history(series: Series) -> dict[str, dict[str, float | int]]:
    """The ten-year median margins (spec 2026-11-13 11): ``operating``, the median the margin flag
    uses, and ``net``, net income over revenue on the same rule, each with ``years``, the count of
    fiscal years behind it; a margin no year has is absent. Both are the statements' own lines, as
    reported, so no rate enters on a company in another currency."""
    found: dict[str, dict[str, float | int]] = {}
    for key, margin in (("operating", operating_margin), ("net", _net_margin)):
        history = _margin_history(series, _MARGIN_WINDOW, margin)
        if history:
            found[key] = {"median": statistics.median(history), "years": len(history)}
    return found


def _net_margin(fy: FiscalYear) -> float | None:
    """Net income ÷ revenue; ``None`` when either is missing or the revenue is not positive."""
    if fy.revenue is None or fy.net_income is None or fy.revenue <= 0:
        return None
    return fy.net_income / fy.revenue


def _margin_history(
    series: Series,
    window: int,
    margin: Callable[[FiscalYear], float | None] = operating_margin,
) -> list[float]:
    """The margins ``margin`` reads, the operating margin unless another is given, of the last
    ``window`` fiscal years that have one, oldest first."""
    return [m for fy in series if (m := margin(fy)) is not None][-window:]
