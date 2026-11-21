"""The rule that drafts the moat table (spec 2026-11-19 8.2; ``docs/method.md`` 4.9a).

The rule writes the first class of a company in the moat table (``fairband.policy.moat``); the
engine never runs it. ``scripts/build_moat_table.py`` reads each company's facts (``MoatFacts``)
from a database and runs ``draft_classes`` on the whole universe at once, since a company's rank
is read among its group's.

It is the rule as it ran on 2026-11-19 on the data of refresh 68, the run the counts of the
decision document's 6.6 and its 74 corrections rest on (spec section 5, point 2), with the
readings the decision document's 6.5 leaves open:

- A year's return is NOPAT ÷ its average invested capital; a year whose capital is at or below
  zero is above any bar when its NOPAT is above zero, else below any bar (``inf``, ``-inf``). The
  ten-year total is the ten years' NOPAT ÷ their capital, by the same reading of the sums; the
  five-year median is ``statistics.median`` of the last five years' returns. A loss year is one
  whose NOPAT is at or below zero. A company with fewer than ten return years is Narrow.
- Growth is read over the fiscal revenues that are neither ``None`` nor zero: the newest ÷ the
  tenth newest, to the power 1 ÷ 9, less 1; none with fewer than ten such years, or when either
  end is not above zero.
- The gross margin is gross profit ÷ revenue of the last ten annual income statements by date
  (``gross_margins``); it is steady with ten margins, the lowest at or above 80% of their median.
- The group is the company's industry when the industry holds five companies with a revenue or
  more; else the companies of its sector whose industries hold fewer than five, together. The
  rank is by revenue, largest first, among the group's companies with a revenue, a tie by symbol,
  A first. A company without a revenue counts in no group's five and has no rank.
- The marks of the scale route: size, revenue of $50 billion or more; leader, first or second in
  the group; growth, revenue of $12 billion or more with growth of 10% a year or more; steady,
  the steady gross margin.

The class is the first of these that holds: fewer than ten return years, Narrow; a phase of
Start-up, Young Growth or High Growth, Narrow, never None; a ten-year total and a five-year median
both below 3%, None; a phase of Decline, Narrow; at most one loss year, none in the last five, a
ten-year total and a five-year median both above 9%, and two marks or more, or a total and a
median both above 20% with the steady mark: Wide, but Narrow in an industry of ``CYCLICAL``;
else Narrow. A company with no phase (no snapshot) passes the two phase tests. Industry names
compare exactly: ``Chemicals - Specialty`` is not ``Chemicals``.

``CYCLICAL`` holds the run's 24 FMP industries, its string that matched no company ("Oil & Gas
Energy") gone, and Aluminum, Silver and Uranium, which the decision document adds and which hold
no Wide row (spec section 5, point 2). Semiconductors are left out on purpose. Size is revenue,
never market value.
"""

import math
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from fairband.policy import Moat

CYCLICAL: frozenset[str] = frozenset(
    {
        # housing and construction
        "Residential Construction",
        "Engineering & Construction",
        "Construction Materials",
        "Real Estate - Services",
        # autos
        "Auto - Dealerships",
        "Auto - Manufacturers",
        "Auto - Recreational Vehicles",
        # commodities
        "Oil & Gas Drilling",
        "Oil & Gas Exploration & Production",
        "Oil & Gas Integrated",
        "Oil & Gas Refining & Marketing",
        "Oil & Gas Equipment & Services",
        "Oil & Gas Midstream",
        "Coal",
        "Steel",
        "Copper",
        "Gold",
        "Other Precious Metals",
        "Industrial Materials",
        "Chemicals",
        "Agricultural Inputs",
        "Paper, Lumber & Forest Products",
        # transport capacity
        "Airlines, Airports & Air Services",
        "Marine Shipping",
        # not in the run of 2026-11-19
        "Aluminum",
        "Silver",
        "Uranium",
    }
)

_YEARS = 10  # return years, fiscal revenues and gross margins
_RECENT = 5  # the years of the median and of no loss
_YOUNG = frozenset({"Start-up", "Young Growth", "High Growth"})
_NONE_BELOW = 0.03
_WIDE_ABOVE = 0.09
_RETURN_ROUTE_ABOVE = 0.20
_MAX_LOSSES = 1
_MARKS = 2  # of four, for the scale route
_SIZE = 50e9
_GROWTH_SIZE = 12e9
_GROWTH = 0.10
_LEADER = 2  # first or second
_GROUP = 5  # companies with a revenue for an industry to be its own group
_STEADY = 0.8  # of the median margin


@dataclass(frozen=True)
class ReturnYear:
    """One return year: its NOPAT and its average invested capital."""

    nopat: float
    capital: float


@dataclass(frozen=True)
class MoatFacts:
    """What the rule reads of one company of the universe: its industry and sector (``""`` where
    the universe has none), the phase of its latest snapshot, the last ten return years the engine
    keeps, oldest first, its trailing revenue in USD (``None`` without one), the revenue of each
    fiscal year assembly reads, oldest first, and the gross margins of its last ten annual income
    statements, oldest first."""

    symbol: str
    industry: str
    sector: str
    phase: str | None
    years: tuple[ReturnYear, ...]
    revenue_usd: float | None
    fiscal_revenues: tuple[float | None, ...]
    gross_margins: tuple[float, ...]


def gross_margins(payload: object) -> tuple[float, ...]:
    """Gross profit ÷ revenue of the last ten rows of an FMP annual income statement answer by
    ``date``, oldest first: ``()`` for a payload that is not a non-empty list. A row counts where
    its ``grossProfit`` is an ``int`` or a ``float`` and its ``revenue`` a number not zero; a row
    that does not count leaves no margin and takes no older row's place."""
    if not isinstance(payload, list) or not payload:
        return ()
    rows = sorted(
        (r for r in payload if isinstance(r, dict)), key=lambda r: str(r.get("date") or "")
    )
    margins: list[float] = []
    for row in rows[-_YEARS:]:
        profit, revenue = row.get("grossProfit"), row.get("revenue")
        if isinstance(profit, int | float) and isinstance(revenue, int | float) and revenue != 0:
            margins.append(profit / revenue)
    return tuple(margins)


def draft_classes(companies: Sequence[MoatFacts]) -> dict[str, Moat]:
    """The rule's class of each company, read with its group among ``companies``, in their
    order."""
    ranks = _ranks(companies)
    return {c.symbol: _class(c, ranks.get(c.symbol)) for c in companies}


def _ranks(companies: Sequence[MoatFacts]) -> dict[str, int]:
    """Each company's rank by revenue in its group, 1 the largest; none without a revenue."""
    counts = Counter(c.industry for c in companies if c.revenue_usd is not None)
    groups: defaultdict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    for c in companies:
        if c.revenue_usd is None:
            continue
        group = ("industry", c.industry) if counts[c.industry] >= _GROUP else ("sector", c.sector)
        groups[group].append((c.revenue_usd, c.symbol))
    ranks: dict[str, int] = {}
    for members in groups.values():
        ordered = sorted(members, key=lambda m: (-m[0], m[1]))
        for k, (_, symbol) in enumerate(ordered, start=1):
            ranks[symbol] = k
    return ranks


def _class(c: MoatFacts, rank: int | None) -> Moat:
    years = c.years[-_YEARS:]
    if len(years) < _YEARS or c.phase in _YOUNG:
        return "Narrow"
    total = _return(sum(y.nopat for y in years), sum(y.capital for y in years))
    median = statistics.median(_return(y.nopat, y.capital) for y in years[-_RECENT:])
    if total < _NONE_BELOW and median < _NONE_BELOW:
        return "None"
    if c.phase == "Decline":
        return "Narrow"
    losses = [y.nopat <= 0 for y in years]
    conditions = (
        sum(losses) <= _MAX_LOSSES
        and not any(losses[-_RECENT:])
        and total > _WIDE_ABOVE
        and median > _WIDE_ABOVE
    )
    steady = _steady(c.gross_margins)
    revenue = c.revenue_usd
    growth = _growth(c.fiscal_revenues)
    marks = (
        steady,
        revenue is not None and revenue >= _SIZE,
        rank is not None and rank <= _LEADER,
        revenue is not None
        and revenue >= _GROWTH_SIZE
        and growth is not None
        and growth >= _GROWTH,
    )
    scale = sum(marks) >= _MARKS
    by_return = total > _RETURN_ROUTE_ABOVE and median > _RETURN_ROUTE_ABOVE and steady
    if conditions and (scale or by_return):
        return "Narrow" if c.industry in CYCLICAL else "Wide"
    return "Narrow"


def _return(nopat: float, capital: float) -> float:
    """NOPAT ÷ capital; with capital at or below zero, above any bar on a profit, else below."""
    if capital <= 0:
        return math.inf if nopat > 0 else -math.inf
    return nopat / capital


def _growth(revenues: Sequence[float | None]) -> float | None:
    years = [r for r in revenues if r]
    if len(years) < _YEARS or years[-_YEARS] <= 0 or years[-1] <= 0:
        return None
    return float((years[-1] / years[-_YEARS]) ** (1 / (_YEARS - 1)) - 1)


def _steady(margins: Sequence[float]) -> bool:
    return len(margins) >= _YEARS and min(margins) >= _STEADY * statistics.median(margins)
