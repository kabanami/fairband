"""The warning flags of spec 6.7: each warns and never changes a value, a level or a designation.

The margin flag is ``mech/1.2``'s. The margin is operating income ÷ revenue for each fiscal year
that has both and a positive revenue; the median and the high run over the last ten such years,
and the flag needs at least ``margin_flag_min_years`` of them. It fires when the trailing margin
is ``margin_flag_ratio`` times the median or more (a positive median), or when it is above the
high by ``margin_flag_above_high`` of the high's size or more, so a loss-making history that turns
profitable fires too. Its word reads the history: "Newly profitable" for a median at or below
zero, "Possible cycle peak" for a loss year in the window, else "Margin above history".

The gate flags are the three ``mech/1.2`` gate tests on the trailing figures, kept as flags. The
cash-flow statement signs capital spending as an outflow, so ``capex`` is negative for spending:
free cash flow is ``cfo + capex`` and the spending is ``-capex``.

The consensus-basis note follows ``large-nri`` on the mature routes (spec 2026-11-09 7): FMP's
consensus names no basis, so whether the NTM anchor and the path carry the non-recurring items
is unknown.

The two stock-pay notes follow the anchor's flags on Mature Growth (spec 2026-11-13 7.1).
``stock-pay-missing``: the trailing stock pay is zero, or a trailing period's is, while a fiscal
year on file holds stock pay above zero, so the stored figure, and the stock-pay charge on the
consensus with it, may be nil or short. ``sbc-basis-uncertain``: the basis test may misread, one
sentence for each reason that holds. Stock pay is material when its after-tax figure a share is
``sbc_material_share`` of a street trailing EPS above zero or more. Reason 1: the test reads
``includes-sbc`` on a material stock pay with ``large-nri`` on the row, a one-time item that may
sit in GAAP EPS and hide the gap. Reason 2: the same reading on a material stock pay with a
trailing effective tax rate, income tax over a pre-tax income above zero, at or below
``sbc_basis_tax_share`` of the statutory rate, a low tax that may close the gap. Reason 3: the
test reads ``excludes-sbc`` on a stock pay above zero and the street EPS lies above GAAP by
``sbc_basis_gap_multiple`` times the after-tax stock pay a share or more, so the adjusted figure
leaves out far more than stock pay.

``QUALITY_WARNINGS`` are the eleven flags that say the value may be wrong because the business or
its figures are unusual (spec 2026-11-04 9.5); ``flag_count`` counts them on a row. Every other
flag is a note: the classifier checks, the thin-consensus flags, the unknown inputs, the engine's
mechanics and the bookkeeping flags. A note is shown and never counted.
"""

import statistics
from collections.abc import Sequence

from fairband.engine.anchor import SbcBasis, StockPayHistory, TrailingFigures
from fairband.engine.classifier import Series, operating_margin
from fairband.engine.types import Flag
from fairband.policy import Policy

_MARGIN_WINDOW = 10  # mech/1.2: the median and the high over the last ten fiscal years

QUALITY_WARNINGS: frozenset[str] = frozenset(
    {
        "large-nri",
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


def nri_flag(nri_gap_per_share: float | None, eps_ttm: float | None, policy: Policy) -> Flag | None:
    """``large-nri`` when the non-recurring gap is ``nri_flag_share`` of trailing EPS or more, in
    either direction; ``None`` without both figures or with a zero EPS."""
    if nri_gap_per_share is None or eps_ttm is None or eps_ttm == 0:
        return None
    gap, eps = abs(nri_gap_per_share), abs(eps_ttm)
    if gap < policy.nri_flag_share * eps:
        return None
    return Flag(
        "large-nri",
        "Large non-recurring item",
        f"The non-recurring gap of {nri_gap_per_share:.2f} per share is {gap / eps:.1%} of "
        f"trailing EPS of {eps_ttm:.2f}, at or above {policy.nri_flag_share:.1%}.",
    )


def basis_unknown_flag(
    nri: Flag | None, gap: float | None, eps_ttm: float | None, currency: str = "USD"
) -> Flag | None:
    """The ``consensus-basis-unknown`` note beside ``nri``, the row's ``large-nri``: the gap a
    share with its sign, after ``$`` or the reporting ``currency``'s code, and its share of
    trailing EPS in size; ``None`` without ``nri``, or without the gap or a non-zero EPS."""
    if nri is None or gap is None or eps_ttm is None or eps_ttm == 0:
        return None
    sign = ("−" if gap < 0 else "") + ("$" if currency == "USD" else f"{currency} ")
    return Flag(
        "consensus-basis-unknown",
        "Consensus basis unknown",
        f"The non-recurring gap is {sign}{abs(gap):,.2f} a share, {abs(gap) / abs(eps_ttm):.1%} "
        "of trailing EPS. FMP's consensus names no basis, so whether the NTM anchor and the path "
        "carry such items is unknown; a report that reads the filing decides, through "
        "`earnings.nri_gap`, and on Mature Growth `earnings.ntm`.",
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
    large_nri: bool,
    policy: Policy,
) -> Flag | None:
    """``sbc-basis-uncertain`` when the stock-pay basis test may misread (the module docstring),
    one sentence for each reason that holds, joined by a space: the after-tax stock pay a share is
    ``t.sbc`` × (1 − ``tax_rate``) ÷ ``shares``, as the anchor reads it, and ``large_nri`` says
    whether ``large-nri`` is on the row. ``None`` when no reason holds, or without the stock pay,
    the street EPS or a positive share count."""
    if t.sbc is None or street_ttm_eps is None or shares <= 0:
        return None
    per_share = t.sbc * (1 - tax_rate) / shares
    material = street_ttm_eps > 0 and per_share >= policy.sbc_material_share * street_ttm_eps
    reasons: list[str] = []
    if basis == "includes-sbc" and material:
        reads = (
            f"The basis test reads the consensus as counting stock pay, {per_share:,.2f} a share "
            f"after tax and {per_share / street_ttm_eps:.1%} of street trailing EPS, while"
        )
        if large_nri:
            reasons.append(
                f"{reads} a large non-recurring item on the row may sit in GAAP EPS and hide the "
                "gap."
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
                f"The street trailing EPS is {gap:,.2f} above the GAAP one, "
                f"{gap / per_share:,.1f} times the stock pay of {per_share:,.2f} a share after "
                "tax: the adjusted figure leaves out far more than stock pay, and the figures "
                "cannot say whether it leaves out stock pay too."
            )
    if not reasons:
        return None
    return Flag("sbc-basis-uncertain", "Stock-pay basis uncertain", " ".join(reasons))


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


def _margin_history(series: Series, window: int) -> list[float]:
    """The operating margins of the last ``window`` fiscal years that have one, oldest first."""
    return [m for fy in series if (m := operating_margin(fy)) is not None][-window:]
