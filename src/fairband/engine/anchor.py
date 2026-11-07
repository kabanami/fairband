"""The Mature Growth route's consensus inputs: the NTM anchor, the path and the belief (spec 6.6).

Year 1 is the NTM anchor: the sum of the four consensus quarters after the last reported quarter,
picked by period end and never by row order, and only when they are consecutive quarters. The SBC
basis test of ``mech/1.2``: when the street's trailing EPS sits above the GAAP trailing EPS by at
least ``sbc_detect`` times the after-tax SBC per share, the consensus excludes stock compensation,
and the anchor subtracts the after-tax SBC per share held at its trailing share of revenue (scaled
by the NTM consensus revenue over the trailing revenue, or unscaled when either is missing). A
missing input leaves the basis unknown; the consensus then stands as it is and is flagged.

Years 2 and 3 are the next two steps of the annual consensus from the base year, the fiscal year
that holds most of the NTM quarters (a tie takes the later). The steps read net income when the base
year and the next two all have a positive consensus, else EPS, flagged. A step the consensus does
not reach is ``None`` and takes the belief. The belief for years 4 to N is the Base Rate Book median
for the sales class plus the inflation addition; the moat class reads the GuruFocus Moat Score.
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

# Days from one quarter end to the next: 89 to 92 on calendar quarters, 91 or 98 on 52/53-week
# fiscal years.
_QUARTER_DAYS_MIN, _QUARTER_DAYS_MAX = 80, 100
_NTM_QUARTERS = 4

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
    """The trailing twelve months: the last four quarters summed, or the last fiscal year when
    ``on_fiscal_year``; a figure is ``None`` when any of the periods lacks it.
    ``interest_expense`` sums each period's interest expense by its size (FMP signs it either way)
    and ``depreciation`` the cash flow's depreciation and amortization as signed."""

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
    step lands on, read from the series the steps use."""

    steps: tuple[float | None, float | None]
    on_eps: bool
    analysts: tuple[int | None, int | None]
    flags: tuple[Flag, ...]


@dataclass(frozen=True)
class Belief:
    """The growth belief for years 4 to N, the sales class it came from and that class's median."""

    rate: float
    sales_class: str
    median: float


def ntm_quarters(
    estimates: Sequence[QuarterEstimate], last_reported: date
) -> tuple[QuarterEstimate, ...] | None:
    """The first four quarters ending after ``last_reported``, by period end; ``None`` unless there
    are four and each ends 80 to 100 days after the one before."""
    after = sorted(
        (e for e in estimates if e.period_end > last_reported), key=lambda e: e.period_end
    )
    window = after[:_NTM_QUARTERS]
    if len(window) < _NTM_QUARTERS or not consecutive_quarters([e.period_end for e in window]):
        return None
    return tuple(window)


def consecutive_quarters(ends: Sequence[date]) -> bool:
    """Each period end falls 80 to 100 days after the one before."""
    return all(
        _QUARTER_DAYS_MIN <= (later - earlier).days <= _QUARTER_DAYS_MAX
        for earlier, later in pairwise(ends)
    )


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
    quarters: Sequence[QuarterEstimate],
    trailing: TrailingFigures,
    street_ttm_eps: float | None,
    shares: float,
    tax_rate: float,
    price: float,
    policy: Policy,
    *,
    nri_correction: float | None = None,
    cycle_gap: float | None = None,
    guided_eps: float | None = None,
) -> Anchor:
    """The NTM EPS with stock compensation as a cost and the NTM net income on ``shares``. The
    basis test reads trailing GAAP EPS as reported; with ``nri_correction``, an agent's
    non-recurring gap less the gap found (``method.md`` 14), GAAP EPS less that correction, so a
    gap overridden at the figure found leaves the test as it was. With ``guided_eps``, an agent's
    NTM EPS from a clear guidance, that figure stands in for the consensus less the SBC
    adjustment, the four quarters still required; with ``cycle_gap``, an agent's correction to
    mid-cycle earnings a share, the NTM EPS is then taken less it, and "no positive forward
    anchor" reads the figure so set and lowered. The unit-error check reads the consensus as
    found, a check on the vendor's units (on a positive figure: a trough lifted by a negative gap
    has no forward P/E to check), the raw sum and the adjustment are the consensus's, and the
    basis test reads neither override."""
    sbc_per_share = None if trailing.sbc is None else trailing.sbc * (1 - tax_rate) / shares
    gaap = trailing.eps_diluted
    if gaap is not None and nri_correction is not None:
        gaap -= nri_correction
    basis = sbc_basis(street_ttm_eps, gaap, sbc_per_share, policy.sbc_detect)
    flags = (_SBC_UNKNOWN,) if basis == "unknown" else ()

    eps = [x.eps for x in quarters if x.eps is not None]
    if len(quarters) != _NTM_QUARTERS or len(eps) != _NTM_QUARTERS:
        return Anchor(0.0, 0.0, 0.0, 0.0, basis, flags, "incomplete NTM consensus")
    raw = sum(eps)
    adjustment = 0.0
    if basis == "excludes-sbc" and sbc_per_share is not None:
        adjustment = sbc_per_share * _revenue_scale(quarters, trailing.revenue)
    found = raw - adjustment
    anchor = found if guided_eps is None else guided_eps
    ntm_eps = anchor if cycle_gap is None else anchor - cycle_gap

    refusal = None
    if ntm_eps <= 0:
        refusal = "no positive forward anchor"
    elif found > 0 and price / found < policy.forward_pe_unit_error:
        refusal = f"forward P/E below {policy.forward_pe_unit_error:g}: unit error"
    return Anchor(raw, adjustment, ntm_eps, ntm_eps * shares, basis, flags, refusal)


def base_fiscal_year(quarters: Sequence[QuarterEstimate]) -> int:
    """The fiscal year that holds most of the quarters; a tie takes the later year."""
    counts = Counter(x.fiscal_year for x in quarters)
    return max(counts, key=lambda year: (counts[year], year))


def path_steps(annual: Sequence[AnnualEstimate], base_year: int, policy: Policy) -> Path:
    """The consensus steps from ``base_year`` to the next year and from that to the one after."""
    by_year = {x.fiscal_year: x for x in annual}
    rows = [by_year.get(base_year + i) for i in range(3)]
    on_eps = not all(r is not None and r.net_income is not None and r.net_income > 0 for r in rows)
    points = [_point(r, on_eps) for r in rows]
    values = [consensus_value(mean, n) for mean, n in points]
    steps = (growth_step(values[0], values[1]), growth_step(values[1], values[2]))
    analysts = (points[1][1], points[2][1])

    flags = [_PATH_ON_EPS] if on_eps else []
    thin = few_analysts(base_year, steps, analysts, policy)
    if thin is not None:
        flags.append(thin)
    return Path(steps=steps, on_eps=on_eps, analysts=analysts, flags=tuple(flags))


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
