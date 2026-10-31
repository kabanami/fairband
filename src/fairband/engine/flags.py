"""The warning flags of spec 6.7: each warns and never changes a value or a stance.

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
"""

import statistics
from collections.abc import Sequence

from fairband.engine.anchor import TrailingFigures
from fairband.engine.classifier import FiscalYear, Series
from fairband.engine.types import Flag
from fairband.policy import Policy

_MARGIN_WINDOW = 10  # mech/1.2: the median and the high over the last ten fiscal years


def margin_flag(series: Series, ttm_margin: float | None, policy: Policy) -> Flag | None:
    """The ``margin-flag`` for the trailing operating margin against its own history."""
    history = [m for fy in series if (m := _margin(fy)) is not None][-_MARGIN_WINDOW:]
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


def value_spread_flag(values: Sequence[float | None], policy: Policy) -> Flag | None:
    """``value-spread`` when the values (``None`` skipped) span ``value_spread_flag`` of the
    lowest or more; ``None`` with fewer than two values or a lowest value at or below zero."""
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
        f"The value ranges from {low:,.2f} to {high:,.2f} across the ROIC values or runways "
        f"tested, a spread of {spread:.1%}, at or above {policy.value_spread_flag:.1%}.",
    )


def _margin(fy: FiscalYear) -> float | None:
    if fy.revenue is None or fy.operating_income is None or fy.revenue <= 0:
        return None
    return fy.operating_income / fy.revenue
