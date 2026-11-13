"""The six five-year financial tables of a report's section 4 (spec 2026-11-06 Tier 2, 13.5;
design.md 9.3), computed by the server from the stored statements and the engine's own readings,
each cell with its reference: the agent cites the cells and derives none of them.

The periods are the last five fiscal years on file, oldest first, each named by its fiscal year
as text. The lines are read as the engine joins them (``annual_lines``): the year's income
statement, the cash flow ending on its period end and the balance sheet of its fiscal year. A
cell that is one stored line cites it, ``fact:<symbol>/<line>/<year>`` with ``<line>`` its name in
``LINES``; any other cell cites itself, ``table:<symbol>/<table>/<row>/<year>``. Every row is in
every table; a cell the lines cannot give holds ``None``. A ratio is ``None`` when either term is
missing or its denominator is at or below zero.

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
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

from fairband.engine.distress import altman_z, piotroski_f
from fairband.engine.roic import aggregate_roic
from fairband.engine.types import rated
from fairband.policy import Policy, in_currency
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh.inputs_statements import (
    Statements,
    annual_lines,
    balance_sums,
    country_for,
    statements_for,
)
from fairband.reports.refs import fact_ref, table_ref
from fairband.store.companies import latest_company
from fairband.store.snapshots import latest_snapshot

TABLES = ("growth", "cash_flow", "solvency", "returns", "capital_allocation", "quality")
YEARS = 5
NOT_ON_FILE = "not on file"
NEWEST_ONLY = "the ten-year aggregate is the newest year's figure"
NO_INTEREST = "the interest expense on file is zero"
NO_CAPITAL = "average invested capital is at or below zero"

Unit = Literal["currency", "percent", "multiple", "count", "per-share", "score", "years"]

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
class Table:
    name: str
    rows: tuple[Row, ...]


def year_lines(conn: sqlite3.Connection, symbol: str) -> dict[int, dict[str, float | None]]:
    """Each fiscal year on file, oldest first, with every line of ``LINES`` by name as a
    ``fact:`` ref of that year reads it; ``None`` where the year's statement lacks it."""
    return {year: _named(sheets) for year, sheets in annual_lines(conn, symbol).items()}


def financial_tables(
    conn: sqlite3.Connection, symbol: str, policy: Policy, tax: TaxTable | None = None
) -> tuple[Table, ...]:
    """The six tables of ``symbol`` over its last five fiscal years on file, in ``TABLES``' order;
    every row without cells when the store holds no annual income statement. ``tax`` is the table
    the capital years are taxed with, the packaged one when ``None``; the hurdle rate is
    ``policy``'s r, restated on a company in another currency (module docstring)."""
    country, _ = country_for(conn, symbol, latest_company(conn, symbol))
    taxed = load_tax_table() if tax is None else tax
    stated = statements_for(conn, symbol, country, taxed, _NO_DAY)
    f = _Figures(symbol, annual_lines(conn, symbol), stated, policy, _hurdle(conn, symbol, policy))
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


class _Figures:
    """One company's lines by fiscal year and the engine's readings over them, building rows."""

    def __init__(
        self,
        symbol: str,
        sheets: Mapping[int, Mapping[str, Mapping[str, float | None]]],
        stated: Statements,
        policy: Policy,
        hurdle: float,
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

    def line(self, name: str, year: int) -> float | None:
        return self.lines.get(year, {}).get(name)

    def balance_sum(self, name: str, year: int) -> tuple[float | None, str | None]:
        """The year's debt or cash as assembly reads it, with the note naming a missing line."""
        return balance_sums(self.sheets.get(year, {}).get("balance-annual", {}))[name]

    def fact(self, row: str, line: str, unit: Unit) -> Row:
        """A row of one stored line, each cell citing it."""
        cells = (
            Cell(str(y), self.line(line, y), unit, fact_ref(self.symbol, line, str(y)))
            for y in self.years
        )
        return Row(row, unit, tuple(cells))

    def computed(self, table: str, row: str, unit: Unit, read: Callable[[int], _Reading]) -> Row:
        """A row ``read`` computes for each year, a value or a value and its note, each cell
        citing itself."""
        cells = []
        for y in self.years:
            found = read(y)
            value, note = found if isinstance(found, tuple) else (found, None)
            ref = table_ref(self.symbol, table, row, str(y))
            cells.append(Cell(str(y), value, unit, ref, note))
        return Row(row, unit, tuple(cells))


def _growth(f: _Figures) -> Table:
    def margin(line: str) -> Callable[[int], _Reading]:
        return lambda y: _per(f.line(line, y), f.line("revenue", y))

    t = "growth"
    return Table(
        t,
        (
            f.fact("revenue", "revenue", "currency"),
            f.computed(
                t,
                "revenue_growth",
                "percent",
                lambda y: _change(f.line("revenue", y), f.line("revenue", y - 1)),
            ),
            f.computed(t, "gross_margin", "percent", margin("gross_profit")),
            f.computed(t, "operating_margin", "percent", margin("operating_income")),
            f.computed(t, "net_margin", "percent", margin("net_income")),
            f.fact("eps", "eps_diluted", "per-share"),
        ),
    )


def _cash_flow(f: _Figures) -> Table:
    def free(y: int) -> float | None:
        return _sum(f.line("cfo", y), f.line("capex", y))

    t = "cash_flow"
    return Table(
        t,
        (
            f.fact("operating_cash_flow", "cfo", "currency"),
            f.fact("capital_spending", "capex", "currency"),
            f.computed(t, "free_cash_flow", "currency", free),
            f.computed(
                t, "fcf_to_net_income", "multiple", lambda y: _per(free(y), f.line("net_income", y))
            ),
            f.computed(
                t,
                "stock_compensation_to_revenue",
                "percent",
                lambda y: _per(f.line("sbc", y), f.line("revenue", y)),
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
    return Table(
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
    return Table(
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
    return Table(
        t,
        (
            f.fact("dividends", "dividends", "currency"),
            f.fact("buybacks", "buybacks", "currency"),
            f.computed(
                t,
                "share_count_change",
                "percent",
                lambda y: _change(f.line("shares_diluted", y), f.line("shares_diluted", y - 1)),
            ),
            f.computed(t, "acquisitions", "currency", lambda y: (None, NOT_ON_FILE)),
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
    return Table(
        t,
        (
            f.computed(t, "altman_z", "score", z),
            f.computed(t, "piotroski_f", "score", piotroski),
            f.computed(t, "beneish_m", "score", lambda y: (None, NOT_ON_FILE)),
        ),
    )


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
