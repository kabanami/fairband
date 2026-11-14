"""The Mature Growth route's consensus inputs: the NTM anchor, the path and the belief (spec 6.6).

Year 1 is the NTM anchor: the sum of the consensus periods of the NTM window after the last
reported period, picked by period end and never by row order (``ntm_window``). The window is four
consecutive quarters for a company that reports quarterly; for one that reports half-yearly
(spec 2026-11-10 8) it is two consecutive half-years with no consensus row 80 to 100 days from
either (a quarterly consensus with a gap is no half-year pair), else four consecutive quarters,
the window its consensus cadence gives. The cadence is the trailing figures' (``TrailingFigures.cadence``),
read from the spacing of the statement periods; a row ending within ``SAME_PERIOD_DAYS`` after
the last reported period is that period, whose end in the consensus can lie a day or a few days
from the statements' (a 52/53-week year), not the first of the window. The SBC basis test of
``mech/1.2``:
when the street's trailing EPS sits above the GAAP trailing EPS by at least ``sbc_detect`` times
the after-tax SBC per share, the consensus excludes stock compensation, and the anchor subtracts
the after-tax SBC per share held at its trailing share of revenue (scaled by the NTM consensus
revenue over the trailing revenue, or unscaled when either is missing). A missing input leaves the
basis unknown; the consensus then stands as it is and is flagged.

Years 2 and 3 are the next two steps of the annual consensus from the base year, the fiscal year
that holds most of the window's periods (a tie takes the later). The steps read net income when
the base year and the next two all have a positive consensus, else EPS, flagged. A step the
consensus does not reach is ``None`` and takes the belief. Both earnings series are read and
kept, and ``step_series_flag`` notes a step whose rate on net income and rate on EPS lie more than
``step_series_gap_max`` apart, with the diluted count the route holds (spec 2026-11-09 section 9).
The revenue steps on the same years are kept as found, for the charge. The belief for
years 4 to N is the Base Rate Book median for the sales class plus the inflation addition; the moat
class reads the GuruFocus Moat Score.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from itertools import pairwise
from typing import Literal

from fairband.engine.types import Flag
from fairband.policy import BaseRateClass, Moat, Policy

SbcBasis = Literal["excludes-sbc", "includes-sbc", "unknown"]
# How often a company reports, read from the spacing of its statement periods
# (``inputs_statements.cadence_of``): the trailing figures and the NTM window sum a year of them.
Cadence = Literal["quarterly", "half-yearly"]

# Days from one quarter end to the next: 89 to 92 on calendar quarters, 91 or 98 on 52/53-week
# fiscal years.
QUARTER_DAYS_MIN, QUARTER_DAYS_MAX = 80, 100
# Days from one half-year end to the next: 178 to 184 on file, with 52/53-week years in reach
# (spec 2026-11-10 8).
HALF_DAYS_MIN, HALF_DAYS_MAX = 170, 195
_DAYS_APART: dict[Cadence, tuple[int, int]] = {
    "quarterly": (QUARTER_DAYS_MIN, QUARTER_DAYS_MAX),
    "half-yearly": (HALF_DAYS_MIN, HALF_DAYS_MAX),
}
# The periods in a year under each cadence: the trailing figures and the NTM window sum as many.
PERIODS_PER_YEAR: dict[Cadence, int] = {"quarterly": 4, "half-yearly": 2}
# Period ends at most this many days apart are one period. The statements and the consensus can end
# one period a day or a few days apart (a 52/53-week year), so a consensus row ending this soon
# after the trailing period end is the period just reported. Assembly merges two consensus rows
# this close as a guard for two rows of one period inside one vendor answer; no stored answer held
# such a pair on 2026-11-13 (spec 2026-11-13 6).
SAME_PERIOD_DAYS = 7
# A step's two rates that lie exactly ``step_series_gap_max`` apart are within the gap, whatever
# binary floating point does to the rates: without it, five points fire on one step and not another.
_GAP_TOLERANCE = 1e-12

_SBC_UNKNOWN = Flag(
    "sbc-basis-unknown",
    "SBC basis unknown",
    "The street trailing EPS, the GAAP trailing EPS or the stock compensation is missing, so the "
    "NTM consensus is used as it stands, without the test for stock compensation.",
)
_PATH_ON_EPS = Flag(
    "path-on-eps",
    "Path on EPS",
    "The annual consensus has no positive net income for the base year and the next two, so years "
    "2 and 3 grow at the consensus EPS steps.",
)


@dataclass(frozen=True)
class QuarterEstimate:
    """One fiscal quarter of consensus: the mean EPS, revenue and net income, and the analysts."""

    period_end: date
    fiscal_year: int
    fiscal_period: str
    eps: float | None
    revenue: float | None
    net_income: float | None
    analysts: int | None


@dataclass(frozen=True)
class AnnualEstimate:
    """One fiscal year of consensus, with the analyst counts for EPS, for net income and for
    revenue."""

    fiscal_year: int
    period_end: date
    eps: float | None
    revenue: float | None
    net_income: float | None
    analysts_eps: int | None
    analysts_net_income: int | None
    analysts_revenue: int | None = None


@dataclass(frozen=True)
class TrailingFigures:
    """The trailing twelve months: the last four quarters summed, or the last two half-years for
    a company whose ``cadence`` is half-yearly, ``quarters`` counting the periods summed; or the
    last fiscal year when ``on_fiscal_year``, whose cadence is the one the statement rows gave,
    ``quarterly`` when they gave none. A figure is ``None`` when any of the periods lacks it.
    ``interest_expense`` sums each period's interest expense by its size (FMP signs it either
    way) and ``depreciation`` the cash flow's depreciation and amortization as signed;
    ``income_tax`` and ``pretax_income`` sum the income statements' income tax and income before
    tax, which the stock-pay basis note reads (spec 2026-11-13 7.1)."""

    period_end: date
    quarters: int
    on_fiscal_year: bool
    revenue: float | None
    operating_income: float | None
    net_income: float | None
    eps_diluted: float | None
    sbc: float | None
    cfo: float | None
    capex: float | None
    dividends: float | None
    buybacks: float | None
    equity_issued: float | None
    interest_expense: float | None = None
    depreciation: float | None = None
    cadence: Cadence = "quarterly"
    income_tax: float | None = None
    pretax_income: float | None = None


@dataclass(frozen=True)
class StockPayHistory:
    """The stock pay on file beside the trailing figure (spec 2026-11-13 7.1): how many of the
    trailing periods hold a stock pay of exactly zero, and the newest fiscal year whose stock pay
    is above zero with its figure, both ``None`` without one."""

    zero_periods: int
    newest_year: int | None
    newest_figure: float | None


@dataclass(frozen=True)
class Anchor:
    """Year 1 per share and in total: the consensus less the SBC adjustment, or an agent's guided
    NTM EPS in its place, less an agent's cycle gap when one applies; under the refusal
    "incomplete NTM consensus" the numbers are 0."""

    ntm_eps_raw: float
    sbc_adjustment_per_share: float
    ntm_eps: float
    ntm_net_income: float
    basis: SbcBasis
    flags: tuple[Flag, ...]
    refusal: str | None

    @property
    def ntm_eps_found(self) -> float:
        """The NTM EPS as the engine finds it, before any override: the consensus less the SBC
        adjustment, the figure ``ntm_eps`` is without one."""
        return self.ntm_eps_raw - self.sbc_adjustment_per_share


@dataclass(frozen=True)
class Path:
    """The growth for years 2 and 3 (``None`` takes the belief) and the analysts of the year each
    step lands on, read from the series the steps use; the consensus revenue steps on the same
    years as found, ``None`` where missing, for the charge; and the base year's and the next two
    years' consensus means on net income and on EPS, ``None`` where missing, for
    ``step_series_flag``."""

    steps: tuple[float | None, float | None]
    on_eps: bool
    analysts: tuple[int | None, int | None]
    flags: tuple[Flag, ...]
    revenue_steps: tuple[float | None, float | None]
    net_income_means: tuple[float | None, float | None, float | None]
    eps_means: tuple[float | None, float | None, float | None]


@dataclass(frozen=True)
class Belief:
    """The growth belief for years 4 to N, the sales class it came from and that class's median."""

    rate: float
    sales_class: str
    median: float


def ntm_window(
    estimates: Sequence[QuarterEstimate], last_reported: date, cadence: Cadence
) -> tuple[tuple[QuarterEstimate, ...], Cadence] | None:
    """The NTM window every route reads after ``last_reported``, the trailing period end, and the
    window's own cadence, which the anchor's count and the base year take. ``cadence`` is the
    trailing figures': a quarterly reporter's window is four consecutive quarters only, never two
    rows about half a year apart, which on a consensus with gaps would sum two quarters as a
    year; a half-yearly reporter's is two consecutive half-years, unless a consensus row ending
    after ``last_reported`` sits 80 to 100 days from either of them (quarters with one missing,
    WSE's consensus), else four consecutive quarters, the window its consensus cadence gives
    (spec 2026-11-10 8: ABVX reports half-years, its consensus quarters). ``None`` without
    one."""
    tried: tuple[Cadence, ...] = (
        ("half-yearly", "quarterly") if cadence == "half-yearly" else ("quarterly",)
    )
    for each in tried:
        window = ntm_periods(estimates, last_reported, each)
        if window is None:
            continue
        if each == "half-yearly" and _quarter_beside(estimates, last_reported, window):
            continue
        return window, each
    return None


def _quarter_beside(
    estimates: Sequence[QuarterEstimate],
    last_reported: date,
    window: Sequence[QuarterEstimate],
) -> bool:
    """A consensus row ending after ``last_reported`` sits a quarter (80 to 100 days) from a
    period of ``window``: its rows are quarters with one missing, not half-years."""
    return any(
        consecutive_periods(sorted((e.period_end, p.period_end)), "quarterly")
        for e in estimates
        if e.period_end > last_reported
        for p in window
    )


def ntm_periods(
    estimates: Sequence[QuarterEstimate], last_reported: date, cadence: Cadence
) -> tuple[QuarterEstimate, ...] | None:
    """The first ``PERIODS_PER_YEAR[cadence]`` consensus periods ending more than
    ``SAME_PERIOD_DAYS`` after ``last_reported``, by period end, since a row ending sooner is the
    reported period, its consensus end a day or a few days from the statements'; ``None`` unless
    there are as many and each ends the cadence's days after the one before
    (``consecutive_periods``)."""
    count = PERIODS_PER_YEAR[cadence]
    after = sorted(
        (e for e in estimates if (e.period_end - last_reported).days > SAME_PERIOD_DAYS),
        key=lambda e: e.period_end,
    )
    window = after[:count]
    if len(window) < count or not consecutive_periods([e.period_end for e in window], cadence):
        return None
    return tuple(window)


def ntm_quarters(
    estimates: Sequence[QuarterEstimate], last_reported: date
) -> tuple[QuarterEstimate, ...] | None:
    """The four consecutive quarters after ``last_reported`` (``ntm_periods`` on the quarterly
    cadence)."""
    return ntm_periods(estimates, last_reported, "quarterly")


def consecutive_periods(ends: Sequence[date], cadence: Cadence) -> bool:
    """Each period end falls 80 to 100 days after the one before on the quarterly cadence, 170 to
    195 on the half-yearly one."""
    low, high = _DAYS_APART[cadence]
    return all(low <= (later - earlier).days <= high for earlier, later in pairwise(ends))


def sbc_basis(
    street_ttm_eps: float | None,
    gaap_ttm_eps: float | None,
    sbc_after_tax_per_share: float | None,
    detect: float,
) -> SbcBasis:
    """``excludes-sbc`` when street EPS exceeds GAAP EPS by ``detect`` × after-tax SBC per share."""
    if street_ttm_eps is None or gaap_ttm_eps is None or sbc_after_tax_per_share is None:
        return "unknown"
    if street_ttm_eps - gaap_ttm_eps >= detect * sbc_after_tax_per_share:
        return "excludes-sbc"
    return "includes-sbc"


def ntm_anchor(
    periods: Sequence[QuarterEstimate],
    trailing: TrailingFigures,
    street_ttm_eps: float | None,
    shares: float,
    tax_rate: float,
    price: float,
    policy: Policy,
    *,
    cadence: Cadence = "quarterly",
    nri_correction: float | None = None,
    cycle_gap: float | None = None,
    guided_eps: float | None = None,
) -> Anchor:
    """The NTM EPS with stock compensation as a cost and the NTM net income on ``shares``, on the
    window's ``periods``: ``PERIODS_PER_YEAR[cadence]`` of them, the window's cadence, each with
    an EPS mean. The basis test reads trailing GAAP EPS as reported; with ``nri_correction``, an
    agent's non-recurring gap less the gap found (``method.md`` 14), GAAP EPS less that
    correction, so a gap overridden at the figure found leaves the test as it was. With
    ``guided_eps``, an agent's NTM EPS from a clear guidance, that figure stands in for the
    consensus less the SBC adjustment, the window's periods still required; with ``cycle_gap``,
    an agent's correction to mid-cycle earnings a share, the NTM EPS is then taken less it, and
    "no positive forward anchor" reads the figure so set and lowered. The unit-error check reads
    the consensus as found, a check on the vendor's units (on a positive figure: a trough lifted
    by a negative gap has no forward P/E to check), the raw sum and the adjustment are the
    consensus's, and the basis test reads neither override."""
    sbc_per_share = None if trailing.sbc is None else trailing.sbc * (1 - tax_rate) / shares
    gaap = trailing.eps_diluted
    if gaap is not None and nri_correction is not None:
        gaap -= nri_correction
    basis = sbc_basis(street_ttm_eps, gaap, sbc_per_share, policy.sbc_detect)
    flags = (_SBC_UNKNOWN,) if basis == "unknown" else ()

    count = PERIODS_PER_YEAR[cadence]
    eps = [x.eps for x in periods if x.eps is not None]
    if len(periods) != count or len(eps) != count:
        return Anchor(0.0, 0.0, 0.0, 0.0, basis, flags, "incomplete NTM consensus")
    raw = sum(eps)
    adjustment = 0.0
    if basis == "excludes-sbc" and sbc_per_share is not None:
        adjustment = sbc_per_share * _revenue_scale(periods, trailing.revenue)
    found = raw - adjustment
    anchor = found if guided_eps is None else guided_eps
    ntm_eps = anchor if cycle_gap is None else anchor - cycle_gap

    refusal = None
    if ntm_eps <= 0:
        refusal = "no positive forward anchor"
    elif found > 0 and price / found < policy.forward_pe_unit_error:
        refusal = f"forward P/E below {policy.forward_pe_unit_error:g}: unit error"
    return Anchor(raw, adjustment, ntm_eps, ntm_eps * shares, basis, flags, refusal)


def base_fiscal_year(periods: Sequence[QuarterEstimate]) -> int:
    """The fiscal year that holds most of the window's periods; a tie takes the later year."""
    counts = Counter(x.fiscal_year for x in periods)
    return max(counts, key=lambda year: (counts[year], year))


def base_year(
    estimates: Sequence[QuarterEstimate], last_reported: date, cadence: Cadence = "quarterly"
) -> int | None:
    """The base year as every route that reads one finds it: the fiscal year that holds most of
    the NTM window after ``last_reported`` on the trailing ``cadence`` (``ntm_window``,
    ``base_fiscal_year``); ``None`` without a window."""
    window = ntm_window(estimates, last_reported, cadence)
    return None if window is None else base_fiscal_year(window[0])


def path_steps(annual: Sequence[AnnualEstimate], base_year: int, policy: Policy) -> Path:
    """The consensus steps from ``base_year`` to the next year and from that to the one after, on
    the path's series, with the revenue steps on the same years and both earnings series' means,
    which ``step_series_flag`` reads."""
    by_year = {x.fiscal_year: x for x in annual}
    rows = [by_year.get(base_year + i) for i in range(3)]
    on_eps = not all(r is not None and r.net_income is not None and r.net_income > 0 for r in rows)
    net_income = _three([consensus_value(*_point(r, False)) for r in rows])
    per_share = _three([consensus_value(*_point(r, True)) for r in rows])
    revenue = [None if r is None else consensus_value(r.revenue, r.analysts_revenue) for r in rows]
    steps = _steps(per_share if on_eps else net_income)
    analysts = (_point(rows[1], on_eps)[1], _point(rows[2], on_eps)[1])

    flags = [_PATH_ON_EPS] if on_eps else []
    thin = few_analysts(base_year, steps, analysts, policy)
    if thin is not None:
        flags.append(thin)
    return Path(
        steps=steps,
        on_eps=on_eps,
        analysts=analysts,
        flags=tuple(flags),
        revenue_steps=_steps(revenue),
        net_income_means=net_income,
        eps_means=per_share,
    )


def few_analysts(
    base_year: int,
    steps: tuple[float | None, float | None],
    analysts: tuple[int | None, int | None],
    policy: Policy,
) -> Flag | None:
    """``few-analysts`` when a present step from ``base_year`` lands on a year with fewer than
    ``analyst_min`` analysts or no count; ``analysts`` are the counts of the years the two steps
    land on."""
    thin = [
        str(base_year + 1 + i)
        for i, (step, n) in enumerate(zip(steps, analysts, strict=True))
        if step is not None and (n is None or n < policy.analyst_min)
    ]
    if not thin:
        return None
    return Flag(
        "few-analysts",
        "Few analysts",
        f"The consensus for fiscal {' and '.join(thin)} has fewer than "
        f"{policy.analyst_min} analysts or no count, so its step is thin evidence.",
    )


def sales_class(revenue_ttm_musd: float, policy: Policy) -> BaseRateClass:
    """The sales class of trailing revenue in USD millions: the first whose upper bound is at or
    above it. The revenue is in current dollars and the bounds in 2015 dollars (D6)."""
    return next(c for c in policy.base_rates if revenue_ttm_musd <= c.upper_musd)


def belief_from_sales(revenue_ttm_musd: float, policy: Policy) -> Belief:
    """The belief for trailing revenue in USD millions: its sales class's median plus the
    inflation addition."""
    c = sales_class(revenue_ttm_musd, policy)
    return Belief(rate=c.median + policy.inflation_addition, sales_class=c.label, median=c.median)


def moat_class(score: float | None, policy: Policy) -> Moat:
    """The moat class from the GuruFocus Moat Score; no score gives None."""
    if score is None:
        return "None"
    if score >= policy.moat_wide_min:
        return "Wide"
    if score >= policy.moat_narrow_min:
        return "Narrow"
    return "None"


def _revenue_scale(quarters: Sequence[QuarterEstimate], trailing_revenue: float | None) -> float:
    """NTM consensus revenue over trailing revenue; 1 when either is missing or trailing is not
    positive."""
    revenue = [x.revenue for x in quarters if x.revenue is not None]
    if len(revenue) != len(quarters) or trailing_revenue is None or trailing_revenue <= 0:
        return 1.0
    return sum(revenue) / trailing_revenue


def _steps(values: Sequence[float | None]) -> tuple[float | None, float | None]:
    """The growth from the first of three years to the second and from the second to the third."""
    return growth_step(values[0], values[1]), growth_step(values[1], values[2])


def _three(values: Sequence[float | None]) -> tuple[float | None, float | None, float | None]:
    """The three years' means as a tuple."""
    return values[0], values[1], values[2]


def step_series_flag(
    path: Path, shares: float, policy: Policy, read: tuple[bool, bool] = (True, True)
) -> Flag | None:
    """``step-series-disagree`` (spec 2026-11-09 9) naming each step still ``read`` whose rate on
    net income and rate on EPS both exist and lie more than ``step_series_gap_max`` apart in size,
    with the share counts the two series imply for its earlier year and its landing year against
    the diluted count ``shares``; a step an override replaced is not read, so it drops its own
    clause. A count the two means do not imply leaves the parenthetical out."""
    net_income, eps = path.net_income_means, path.eps_means
    parts: list[str] = []
    tags: list[str] = []
    rates = zip(read, _steps(net_income), _steps(eps), strict=True)
    for i, (still_read, g, h) in enumerate(rates):
        if not still_read or g is None or h is None:
            continue
        if abs(g - h) <= policy.step_series_gap_max + _GAP_TOLERANCE:
            continue
        earlier = _implied_count(net_income[i], eps[i])
        landing = _implied_count(net_income[i + 1], eps[i + 1])
        counts = (
            ""
            if earlier is None or landing is None
            else f" ({_count(earlier)} and {_count(landing)} against the diluted count "
            f"{_count(shares)})"
        )
        parts.append(
            f"step {i + 2} reads {_percent(g)} on net income and {_percent(h)} on EPS: the two "
            f"consensus series imply different share counts{counts}"
        )
        tags.append(f"`path.step_{i + 2}`")
    if not parts:
        return None
    steps = "; ".join(parts)
    series = "EPS" if path.on_eps else "net income"
    decide = "decides" if len(tags) == 1 else "decide"
    return Flag(
        "step-series-disagree",
        "Step series disagree",
        f"{steps[0].upper()}{steps[1:]}. The path is on {series}; {' and '.join(tags)} {decide}.",
    )


def _implied_count(net_income: float | None, eps: float | None) -> float | None:
    """The share count a year's two consensus means imply, net income over EPS; ``None`` when
    either is missing or the quotient is not a positive count."""
    if net_income is None or eps is None or eps == 0 or net_income / eps <= 0:
        return None
    return net_income / eps


def _count(shares: float) -> str:
    """A share count in billions to one decimal, below a billion in millions."""
    if shares >= 1e9:
        return f"{shares / 1e9:.1f}B"
    return f"{shares / 1e6:.1f}M"


def _percent(rate: float) -> str:
    """A rate as a percent to one decimal, a negative one with the minus sign."""
    return f"{rate:,.1%}".replace("-", "−")


def _point(row: AnnualEstimate | None, on_eps: bool) -> tuple[float | None, int | None]:
    """A year's consensus mean and analyst count on the path's series."""
    if row is None:
        return None, None
    if on_eps:
        return row.eps, row.analysts_eps
    return row.net_income, row.analysts_net_income


def consensus_value(mean: float | None, analysts: int | None) -> float | None:
    """The mean, or ``None`` when absent or a 0 with no analysts (no estimate at all)."""
    if mean is None or (mean == 0 and not analysts):
        return None
    return mean


def growth_step(earlier: float | None, later: float | None) -> float | None:
    """The growth from one year to the next; ``None`` when either is missing or ``earlier`` is not
    positive, since growth from a base at or below zero has no meaning."""
    if earlier is None or later is None or earlier <= 0:
        return None
    return later / earlier - 1
