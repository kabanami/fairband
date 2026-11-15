"""The six financial tables of a report's section 4 (spec 2026-11-06 Tier 2, 13.5; design.md 9.3),
computed by the server from the stored statements, the engine's own readings and the stored
consensus, each cell with its reference: the agent cites the cells and derives none of them.

A table carries its columns (spec 2026-11-15 6.1), and every row one cell under each, in order,
the cell's period the column's. A column has a period, a kind and a label in words, made here
once for every reader of the table: the last five fiscal years on file, oldest first, each
``fiscal``, its period and its label the year as text (``2025``); then, on ``growth``,
``cash_flow`` and ``capital_allocation``, the trailing twelve months, ``trailing``, its period
``ttm`` and its label "12 months to 30 Sep 2026", the trailing period's end as the references write
a day; then, on ``growth`` alone, the estimate columns, ``estimate``, its period the consensus
year and ``E`` (``2026E``) and its label "2026 estimate".

The fiscal lines are read as the engine joins them (``annual_lines``): the year's income
statement, the cash flow ending on its period end and the balance sheet of its fiscal year. A
cell that is one stored line cites it, ``fact:<symbol>/<line>/<year>`` with ``<line>`` its name in
``LINES``; any other cell cites itself, ``table:<symbol>/<table>/<row>/<period>``. Every row is in
every table; a cell the lines cannot give holds ``None``. A ratio is ``None`` when either term is
missing or its denominator is at or below zero.

The trailing column (6.2) stands when the trailing figures (``Statements.trailing``) are on file,
are sums of stored periods rather than the last fiscal year standing in, and end after the newest
fiscal year's period end; otherwise the table has none. Its cells: the revenue, the EPS
(``eps_diluted``), the operating cash flow (``cfo``), the capital spending (``capex``), the
dividends and the buybacks, each the trailing figure citing ``fact:<symbol>/<line>/ttm``; the
margins, the free cash flow and its ratios computed from the trailing lines as the fiscal cells
are from the year's; the revenue growth, the trailing revenue over the revenue of the twelve
months before − 1, the sum of the stored periods (``stored_quarters``) a year earlier, as many as
the trailing figures sum, each ending 80 to 100 days after the one before (170 to 195 for
half-years, ``consecutive_periods``) and the trailing ones' first likewise after the last of
them, ``None`` noted "fewer than two years of periods on file" where those are not all stored;
the gross margin and the share count change ``None`` noted "not measured over the trailing twelve
months", since neither the trailing figures nor the stored periods' read carries the gross profit
and the tables read no trailing share count; the acquisitions ``None``, "not on file".

The estimate columns (6.3) are the consensus fiscal years after the newest fiscal year on file
that hold a revenue or an EPS, in order, ``ESTIMATE_YEARS`` at most, each read as an
``estimate:`` ref reads it (``build_inputs``' annual consensus, a later row of one year winning).
Their cells: the revenue and the EPS, the consensus figures citing
``estimate:<symbol>/<year>/revenue`` and ``/eps``; the revenue growth, the consensus revenue over
the year before's − 1, the reported revenue for the year after the newest fiscal year and the
consensus revenue for a later one, ``None`` where the year before has no figure; the three
margins ``None``, "no estimate for this line".

- ``growth``: revenue (``revenue``); revenue growth, the revenue over the year before's − 1; the
  gross, operating and net margins, gross profit, operating income and net income over revenue;
  EPS (``eps_diluted``, the diluted EPS).
- ``cash_flow``: operating cash flow (``cfo``); capital spending (``capex``, negative as the cash
  flow signs it); free cash flow, their sum; free cash flow over net income; stock compensation
  (``sbc``) over revenue.
- ``solvency``: cash, cash and equivalents plus short-term investments, and debt, short-term plus
  long-term debt, as assembly reads them (``balance_sums``: a line not presented counts as nil
  and the cell's note names it, both missing ``None``); net debt (debt − cash) over EBITDA,
  operating income plus depreciation and amortization; the interest coverage, operating income
  over the interest expense by its size, ``None`` noted "the interest expense on file is zero"
  on an expense of zero; the current ratio; the cash runway in ``years``, cash
  over the operating cash outflow when operating cash flow is below zero, else ``None`` noted
  "operating cash flow is not negative".
- ``returns``: ROIC by year, ``roic.aggregate_roic``'s kept year on the capital years
  (``statements_for``, taxed at the company's country as assembly taxes it), the engine's figure
  noted "average invested capital is at or below zero" on such a year, where the figure has the
  wrong sign or none and no meaning; ROE, net income over
  the average of the opening and closing equity; the ten-year aggregate ROIC in the newest year's
  cell only, ``aggregate_roic`` over all the capital years as assembly reads it (the store keeps
  eleven statement years, so an earlier year has fewer than ten ROIC years behind it), the
  earlier cells ``None`` noted "the ten-year aggregate is the newest year's figure"; the hurdle
  rate, the policy's r, which on a company in another currency, whose ROIC is in it, is restated
  by the inflation differential of its latest snapshot when that snapshot carries a rate
  (``policy.in_currency``, ``types.rated``; spec 2026-11-10 7.5), the r its route discounts at.
- ``capital_allocation``: dividends (``dividends``) and buybacks (``buybacks``), negative as the
  cash flow signs them; the share count change, the diluted weighted-average share count over the
  year before's − 1; acquisitions, a line the store does not keep: ``None``, "not on file".
- ``quality``: Altman's Z″ (``distress.altman_z``) and Piotroski's F (``distress.piotroski_f``,
  against the year before) on the balance years, ``None`` without the year's balance sheet, or
  the year before's for F; F is ``None`` with no signal read and noted "<n> of 9 signals read"
  when some go unread. Beneish M, which no source supplies yet: ``None``, "not on file".
"""

import sqlite3
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

from fairband.engine.anchor import AnnualEstimate, TrailingFigures, consecutive_periods
from fairband.engine.distress import altman_z, piotroski_f
from fairband.engine.roic import aggregate_roic
from fairband.engine.types import rated
from fairband.policy import Policy, in_currency
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.inputs import build_inputs
from fairband.refresh.inputs_statements import (
    QuarterFigures,
    Statements,
    annual_lines,
    balance_sums,
    country_for,
    statements_for,
    stored_quarters,
)
from fairband.reports.refs import day_words, estimate_ref, fact_ref, table_ref
from fairband.store.companies import latest_company
from fairband.store.snapshots import latest_snapshot

TABLES = ("growth", "cash_flow", "solvency", "returns", "capital_allocation", "quality")
YEARS = 5
TRAILING = "ttm"
ESTIMATE_YEARS = 3
NOT_ON_FILE = "not on file"
NEWEST_ONLY = "the ten-year aggregate is the newest year's figure"
NO_INTEREST = "the interest expense on file is zero"
NO_CAPITAL = "average invested capital is at or below zero"
NOT_TRAILING = "not measured over the trailing twelve months"
NO_ESTIMATE = "no estimate for this line"
SHORT_HISTORY = "fewer than two years of periods on file"
# The tables with a trailing column, and the one with estimate columns (spec 2026-11-15 6.2, 6.3).
_TRAILING_TABLES = frozenset({"growth", "cash_flow", "capital_allocation"})
_ESTIMATE_TABLES = frozenset({"growth"})

Unit = Literal["currency", "percent", "multiple", "count", "per-share", "score", "years"]
Kind = Literal["fiscal", "trailing", "estimate", "quarter"]

# The fiscal-year lines a ``fact:`` ref names, by the engine's field names (``FiscalYear``,
# ``BalanceYear``, and the trailing figures' names for the lines those leave out), each with the
# statement and the FMP field it reads.
LINES: dict[str, tuple[str, str]] = {
    "revenue": ("income-annual", "revenue"),
    "gross_profit": ("income-annual", "grossProfit"),
    "operating_income": ("income-annual", "operatingIncome"),
    "net_income": ("income-annual", "netIncome"),
    "eps_diluted": ("income-annual", "epsDiluted"),
    "shares_diluted": ("income-annual", "weightedAverageShsOutDil"),
    "interest_expense": ("income-annual", "interestExpense"),
    "cfo": ("cashflow-annual", "netCashProvidedByOperatingActivities"),
    "cfi": ("cashflow-annual", "netCashProvidedByInvestingActivities"),
    "cff": ("cashflow-annual", "netCashProvidedByFinancingActivities"),
    "capex": ("cashflow-annual", "capitalExpenditure"),
    "sbc": ("cashflow-annual", "stockBasedCompensation"),
    "depreciation": ("cashflow-annual", "depreciationAndAmortization"),
    "dividends": ("cashflow-annual", "netDividendsPaid"),
    "buybacks": ("cashflow-annual", "commonStockRepurchased"),
    "stock_issued": ("cashflow-annual", "commonStockIssuance"),
    "total_current_assets": ("balance-annual", "totalCurrentAssets"),
    "total_current_liabilities": ("balance-annual", "totalCurrentLiabilities"),
    "total_assets": ("balance-annual", "totalAssets"),
    "total_liabilities": ("balance-annual", "totalLiabilities"),
    "retained_earnings": ("balance-annual", "retainedEarnings"),
    "equity": ("balance-annual", "totalStockholdersEquity"),
    "long_term_debt": ("balance-annual", "longTermDebt"),
}
# FMP signs the interest expense either way; the engine reads it by its size.
_BY_SIZE = frozenset({"interest_expense"})
# ``statements_for`` reads its day only as the data date of a store without statements, which
# the tables do not read.
_NO_DAY = date.min

type _Reading = float | None | tuple[float | None, str | None]


@dataclass(frozen=True)
class Cell:
    period: str
    value: float | None
    unit: Unit
    ref: str
    note: str | None = None


@dataclass(frozen=True)
class Row:
    name: str
    unit: Unit
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class Column:
    """A table's column: the period of each cell under it, its kind and its label in words."""

    period: str  # "2025", "ttm", "2026E", "2026-Q3"
    kind: Kind
    label: str  # "2025", "12 months to 30 Sep 2026", "2026 estimate", "Q3 2026"


@dataclass(frozen=True)
class Table:
    name: str
    rows: tuple[Row, ...]
    columns: tuple[Column, ...] = ()


def estimate_period(year: int) -> str:
    """An estimate column's period, the consensus year and ``E``: ``2026E``."""
    return f"{year}E"


def year_lines(conn: sqlite3.Connection, symbol: str) -> dict[int, dict[str, float | None]]:
    """Each fiscal year on file, oldest first, with every line of ``LINES`` by name as a
    ``fact:`` ref of that year reads it; ``None`` where the year's statement lacks it."""
    return {year: _named(sheets) for year, sheets in annual_lines(conn, symbol).items()}


def financial_tables(
    conn: sqlite3.Connection,
    symbol: str,
    policy: Policy,
    tax: TaxTable | None = None,
    *,
    consensus: Sequence[AnnualEstimate] | None = None,
) -> tuple[Table, ...]:
    """The six tables of ``symbol`` with their columns, in ``TABLES``' order: its last five fiscal
    years on file, the trailing twelve months and the consensus years where a table has them
    (module docstring); no column and every row without cells when the store holds no annual
    income statement. ``tax`` is the table the capital years are taxed with, the packaged one
    when ``None``; the hurdle rate is ``policy``'s r, restated on a company in another currency.
    ``consensus`` is the annual consensus as an ``estimate:`` ref reads it (``build_inputs``
    under ``policy`` and ``tax``), handed in by a caller that holds it, read here when ``None``."""
    country, _ = country_for(conn, symbol, latest_company(conn, symbol))
    taxed = load_tax_table() if tax is None else tax
    stated = statements_for(conn, symbol, country, taxed, _NO_DAY)
    sheets = annual_lines(conn, symbol)
    if consensus is None:
        consensus = (
            build_inputs(conn, symbol, policy, taxed, _NO_DAY).annual_estimates if sheets else ()
        )
    f = _Figures(
        symbol,
        sheets,
        stated,
        policy,
        _hurdle(conn, symbol, policy),
        consensus,
        stored_quarters(conn, symbol).periods,
    )
    return (
        _growth(f),
        _cash_flow(f),
        _solvency(f),
        _returns(f),
        _capital_allocation(f),
        _quality(f),
    )


def _hurdle(conn: sqlite3.Connection, symbol: str, policy: Policy) -> float:
    """The policy's r in the currency the company's ROIC is in: restated by the inflation
    differential of its latest snapshot when that snapshot carries a rate, else as it is."""
    snapshot = latest_snapshot(conn, symbol)
    if snapshot is None or not rated(snapshot.result):
        return policy.required_return
    differential = snapshot.result.intermediates["inflation_differential"]
    return in_currency(policy, differential).required_return


def _not_trailing(_: TrailingFigures) -> _Reading:
    return None, NOT_TRAILING


def _no_estimate(_: int) -> _Reading:
    return None, NO_ESTIMATE


class _Figures:
    """One company's lines by fiscal year, its trailing figures and its consensus, and the
    engine's readings over them, building each table's columns and its rows' cells under them."""

    def __init__(
        self,
        symbol: str,
        sheets: Mapping[int, Mapping[str, Mapping[str, float | None]]],
        stated: Statements,
        policy: Policy,
        hurdle: float,
        consensus: Sequence[AnnualEstimate],
        stored: Sequence[QuarterFigures],
    ) -> None:
        self.symbol = symbol
        self.policy = policy
        self.hurdle = hurdle
        self.sheets = sheets
        self.lines = {year: _named(s) for year, s in sheets.items()}
        self.years = sorted(sheets)[-YEARS:]
        self.balance = {y.year: y for y in stated.balance_years}
        engine = aggregate_roic(stated.capital_years)
        self.roic = {y.year: y.roic for y in engine.by_year}
        self.capital = {y.year: y.average_capital for y in engine.by_year}
        self.aggregate = engine.aggregate
        self.trailing = _standing(stated)
        self.year_before = (
            None
            if self.trailing is None
            else _year_before(stored, self.trailing, stated.trailing_periods[0].end)
        )
        self.consensus = {a.fiscal_year: a for a in consensus}  # as an ``estimate:`` ref reads it
        newest = self.years[-1] if self.years else None
        self.estimate_years = [
            y
            for y, a in sorted(self.consensus.items())
            if newest is not None and y > newest and (a.revenue is not None or a.eps is not None)
        ][:ESTIMATE_YEARS]

    def line(self, name: str, year: int) -> float | None:
        return self.lines.get(year, {}).get(name)

    def balance_sum(self, name: str, year: int) -> tuple[float | None, str | None]:
        """The year's debt or cash as assembly reads it, with the note naming a missing line."""
        return balance_sums(self.sheets.get(year, {}).get("balance-annual", {}))[name]

    def trailing_of(self, table: str) -> TrailingFigures | None:
        """The trailing figures where ``table`` has the trailing column, else ``None``."""
        return self.trailing if table in _TRAILING_TABLES else None

    def estimates_of(self, table: str) -> list[int]:
        """The consensus years of ``table``'s estimate columns, none on a table without them."""
        return self.estimate_years if table in _ESTIMATE_TABLES else []

    def columns(self, table: str) -> tuple[Column, ...]:
        """The table's columns: the fiscal years, then the trailing twelve months and the
        consensus years where the table has them."""
        fiscal = [Column(str(y), "fiscal", str(y)) for y in self.years]
        trailing = self.trailing_of(table)
        label = None if trailing is None else f"12 months to {day_words(trailing.period_end)}"
        ttm = [] if label is None else [Column(TRAILING, "trailing", label)]
        estimates = [
            Column(estimate_period(y), "estimate", f"{y} estimate")
            for y in self.estimates_of(table)
        ]
        return (*fiscal, *ttm, *estimates)

    def table(self, name: str, rows: Iterable[Row]) -> Table:
        return Table(name, tuple(rows), self.columns(name))

    def cells(
        self,
        table: str,
        fiscal: Callable[[int], Cell],
        trailing: Callable[[TrailingFigures], Cell],
        estimate: Callable[[int], Cell],
    ) -> tuple[Cell, ...]:
        """A cell under each of the table's columns (``columns``), in order."""
        found = [fiscal(y) for y in self.years]
        ttm = self.trailing_of(table)
        if ttm is not None:
            found.append(trailing(ttm))
        found.extend(estimate(y) for y in self.estimates_of(table))
        return tuple(found)

    def fact(self, table: str, row: str, line: str, unit: Unit, estimate: str = "") -> Row:
        """A row of one stored line, each cell citing it: the fiscal year's line, the trailing
        figures' and, under an estimate column, the consensus field ``estimate``, which a row of
        a table with estimate columns must name and a row of another table does not."""
        if (table in _ESTIMATE_TABLES) != bool(estimate):
            raise ValueError(
                f"{table}/{row}: a row names its consensus field where its table has estimate"
                " columns, and only there"
            )

        def fiscal(y: int) -> Cell:
            return Cell(str(y), self.line(line, y), unit, fact_ref(self.symbol, line, str(y)))

        def trailing(ttm: TrailingFigures) -> Cell:
            figure = getattr(ttm, line)
            return Cell(TRAILING, figure, unit, fact_ref(self.symbol, line, TRAILING))

        def consensus(y: int) -> Cell:
            figure = getattr(self.consensus[y], estimate)
            ref = estimate_ref(self.symbol, str(y), estimate)
            return Cell(estimate_period(y), figure, unit, ref)

        return Row(row, unit, self.cells(table, fiscal, trailing, consensus))

    def computed(
        self,
        table: str,
        row: str,
        unit: Unit,
        read: Callable[[int], _Reading],
        trailing: Callable[[TrailingFigures], _Reading] = _not_trailing,
        estimate: Callable[[int], _Reading] = _no_estimate,
    ) -> Row:
        """A row ``read`` computes for each fiscal year, ``trailing`` from the trailing figures
        and ``estimate`` for each consensus year, a value or a value and its note, each cell
        citing itself; by default the trailing cell holds none, "not measured over the trailing
        twelve months", and an estimate cell none, "no estimate for this line"."""

        def cell(period: str, found: _Reading) -> Cell:
            value, note = found if isinstance(found, tuple) else (found, None)
            return Cell(period, value, unit, table_ref(self.symbol, table, row, period), note)

        cells = self.cells(
            table,
            lambda y: cell(str(y), read(y)),
            lambda ttm: cell(TRAILING, trailing(ttm)),
            lambda y: cell(estimate_period(y), estimate(y)),
        )
        return Row(row, unit, cells)

    def trailing_growth(self, ttm: TrailingFigures) -> _Reading:
        """The trailing revenue over the revenue of the twelve months before − 1; none, noted,
        where those months' periods are not all stored."""
        if self.year_before is None:
            return None, SHORT_HISTORY
        return _change(ttm.revenue, _total(q.revenue for q in self.year_before))

    def estimate_growth(self, year: int) -> _Reading:
        """The consensus revenue over the year before's − 1: the reported revenue for the year
        after the newest fiscal year, the consensus revenue for a later one."""
        before = year - 1
        if before <= self.years[-1]:
            revenue = self.line("revenue", before)
        else:
            revenue = None if before not in self.consensus else self.consensus[before].revenue
        return _change(self.consensus[year].revenue, revenue)


def _growth(f: _Figures) -> Table:
    def margin(line: str) -> Callable[[int], _Reading]:
        return lambda y: _per(f.line(line, y), f.line("revenue", y))

    t = "growth"
    return f.table(
        t,
        (
            f.fact(t, "revenue", "revenue", "currency", estimate="revenue"),
            f.computed(
                t,
                "revenue_growth",
                "percent",
                lambda y: _change(f.line("revenue", y), f.line("revenue", y - 1)),
                f.trailing_growth,
                f.estimate_growth,
            ),
            f.computed(t, "gross_margin", "percent", margin("gross_profit")),
            f.computed(
                t,
                "operating_margin",
                "percent",
                margin("operating_income"),
                lambda ttm: _per(ttm.operating_income, ttm.revenue),
            ),
            f.computed(
                t,
                "net_margin",
                "percent",
                margin("net_income"),
                lambda ttm: _per(ttm.net_income, ttm.revenue),
            ),
            f.fact(t, "eps", "eps_diluted", "per-share", estimate="eps"),
        ),
    )


def _cash_flow(f: _Figures) -> Table:
    def free(y: int) -> float | None:
        return _sum(f.line("cfo", y), f.line("capex", y))

    def trailing_free(ttm: TrailingFigures) -> float | None:
        return _sum(ttm.cfo, ttm.capex)

    t = "cash_flow"
    return f.table(
        t,
        (
            f.fact(t, "operating_cash_flow", "cfo", "currency"),
            f.fact(t, "capital_spending", "capex", "currency"),
            f.computed(t, "free_cash_flow", "currency", free, trailing_free),
            f.computed(
                t,
                "fcf_to_net_income",
                "multiple",
                lambda y: _per(free(y), f.line("net_income", y)),
                lambda ttm: _per(trailing_free(ttm), ttm.net_income),
            ),
            f.computed(
                t,
                "stock_compensation_to_revenue",
                "percent",
                lambda y: _per(f.line("sbc", y), f.line("revenue", y)),
                lambda ttm: _per(ttm.sbc, ttm.revenue),
            ),
        ),
    )


def _solvency(f: _Figures) -> Table:
    def net_debt_to_ebitda(y: int) -> float | None:
        debt, cash = f.balance_sum("debt", y)[0], f.balance_sum("cash", y)[0]
        net = None if debt is None or cash is None else debt - cash
        return _per(net, _sum(f.line("operating_income", y), f.line("depreciation", y)))

    def coverage(y: int) -> _Reading:
        interest = f.line("interest_expense", y)
        if interest == 0:
            return None, NO_INTEREST
        return _per(f.line("operating_income", y), interest)

    def runway(y: int) -> _Reading:
        cfo = f.line("cfo", y)
        if cfo is not None and cfo >= 0:
            return None, "operating cash flow is not negative"
        return _per(f.balance_sum("cash", y)[0], None if cfo is None else -cfo)

    t = "solvency"
    return f.table(
        t,
        (
            f.computed(t, "cash", "currency", lambda y: f.balance_sum("cash", y)),
            f.computed(t, "debt", "currency", lambda y: f.balance_sum("debt", y)),
            f.computed(t, "net_debt_to_ebitda", "multiple", net_debt_to_ebitda),
            f.computed(t, "interest_coverage", "multiple", coverage),
            f.computed(
                t,
                "current_ratio",
                "multiple",
                lambda y: _per(
                    f.line("total_current_assets", y), f.line("total_current_liabilities", y)
                ),
            ),
            f.computed(t, "cash_runway_years", "years", runway),
        ),
    )


def _returns(f: _Figures) -> Table:
    def roe(y: int) -> float | None:
        closing, opening = f.line("equity", y), f.line("equity", y - 1)
        average = None if closing is None or opening is None else (closing + opening) / 2
        return _per(f.line("net_income", y), average)

    def roic(y: int) -> _Reading:
        capital = f.capital.get(y)
        return f.roic.get(y), NO_CAPITAL if capital is not None and capital <= 0 else None

    def aggregate(y: int) -> _Reading:
        return f.aggregate if y == f.years[-1] else (None, NEWEST_ONLY)

    t = "returns"
    return f.table(
        t,
        (
            f.computed(t, "roic", "percent", roic),
            f.computed(t, "roe", "percent", roe),
            f.computed(t, "aggregate_roic_ten_year", "percent", aggregate),
            f.computed(t, "hurdle_rate", "percent", lambda y: f.hurdle),
        ),
    )


def _capital_allocation(f: _Figures) -> Table:
    t = "capital_allocation"
    return f.table(
        t,
        (
            f.fact(t, "dividends", "dividends", "currency"),
            f.fact(t, "buybacks", "buybacks", "currency"),
            f.computed(
                t,
                "share_count_change",
                "percent",
                lambda y: _change(f.line("shares_diluted", y), f.line("shares_diluted", y - 1)),
            ),
            f.computed(
                t,
                "acquisitions",
                "currency",
                lambda y: (None, NOT_ON_FILE),
                lambda ttm: (None, NOT_ON_FILE),
            ),
        ),
    )


def _quality(f: _Figures) -> Table:
    def z(y: int) -> float | None:
        this = f.balance.get(y)
        score = None if this is None else altman_z(this, f.policy)
        return None if score is None else score.score

    def piotroski(y: int) -> _Reading:
        this, last = f.balance.get(y), f.balance.get(y - 1)
        if this is None or last is None:
            return None
        found = piotroski_f(this, last)
        if found.read == 0:
            return None
        signals = len(found.signals)
        return (
            found.score,
            None if found.read == signals else f"{found.read} of {signals} signals read",
        )

    t = "quality"
    return f.table(
        t,
        (
            f.computed(t, "altman_z", "score", z),
            f.computed(t, "piotroski_f", "score", piotroski),
            f.computed(t, "beneish_m", "score", lambda y: (None, NOT_ON_FILE)),
        ),
    )


def _standing(stated: Statements) -> TrailingFigures | None:
    """The trailing figures where they give a column (spec 2026-11-15 6.2): on file, sums of
    stored periods rather than the last fiscal year standing in, and ending after the newest
    fiscal year's period end; ``None`` otherwise."""
    trailing = stated.trailing
    if trailing is None or trailing.on_fiscal_year or not stated.series:
        return None
    return trailing if trailing.period_end > stated.series[-1].period_end else None


def _year_before(
    stored: Sequence[QuarterFigures], trailing: TrailingFigures, first: date
) -> tuple[QuarterFigures, ...] | None:
    """The stored periods of the twelve months before the trailing figures', whose first period
    ends ``first``: as many as the trailing figures sum, ending before ``first``, each ending 80 to
    100 days after the one before (170 to 195 for half-years, ``consecutive_periods``) and
    ``first`` likewise after the last of them; ``None`` unless all of them are stored."""
    before = tuple(q for q in stored if q.period_end < first)[-trailing.quarters :]
    ends = [*(q.period_end for q in before), first]
    if len(before) < trailing.quarters or not consecutive_periods(ends, trailing.cadence):
        return None
    return before


def _named(sheets: Mapping[str, Mapping[str, float | None]]) -> dict[str, float | None]:
    """A year's statements read into ``LINES``' names."""
    out = {}
    for name, (dataset, field) in LINES.items():
        value = sheets.get(dataset, {}).get(field)
        out[name] = abs(value) if value is not None and name in _BY_SIZE else value
    return out


def _per(numerator: float | None, denominator: float | None) -> float | None:
    """The ratio; ``None`` when either is missing or the denominator is at or below zero."""
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _change(now: float | None, before: float | None) -> float | None:
    ratio = _per(now, before)
    return None if ratio is None else ratio - 1


def _sum(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def _total(values: Iterable[float | None]) -> float | None:
    """The sum; ``None`` when any of the values is missing."""
    total = 0.0
    for value in values:
        if value is None:
            return None
        total += value
    return total
