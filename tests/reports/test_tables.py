"""The six financial tables of a report's section 4 (spec 2026-11-06 Tier 2, 13.5; design.md 9.3)
on the synthetic company of ``conftest.py``: ACME, a Mature Growth company with revenue of
$1,000 m in 2014 up $100 m a year, a 40% gross margin, a 20% operating margin, a 15% net margin,
and balance lines every year (``refresh/synthetic.py`` states the lines), and five quarters to
2026-09-30, so three tables carry the trailing twelve months after the fiscal years (spec
2026-11-15 6.2); AAPL on the ``snapshots`` fixture, the same statements with the consensus for
2026 and 2027, whose growth table carries them as estimate columns (6.3)."""

import sqlite3
from collections.abc import Sequence
from datetime import date
from typing import Any

import pytest
from refresh.synthetic import (
    HALF_YEARS,
    NOW,
    add_company,
    bodies,
    cashflow_quarter,
    income_quarter,
)
from support.engine_companies import fx_inputs, universe_deciles
from support.payloads import store_payloads

from fairband.engine.roic import aggregate_roic
from fairband.engine.route import value_company
from fairband.policy import Policy, in_currency
from fairband.policy.tax import load_tax_table
from fairband.refresh.inputs_statements import statements_for
from fairband.reports.refs import Resolver
from fairband.reports.tables import (
    ESTIMATE_YEARS,
    LINES,
    NO_ESTIMATE,
    NOT_ON_FILE,
    NOT_TRAILING,
    SHORT_HISTORY,
    TABLES,
    TRAILING,
    Cell,
    Table,
    estimate_period,
    financial_tables,
)
from fairband.store.db import transaction
from fairband.store.facts import facts_for
from fairband.store.snapshots import insert_snapshot

M = 1_000_000
PERIODS = ["2021", "2022", "2023", "2024", "2025"]
# The tables that carry the trailing twelve months after the fiscal years (spec 2026-11-15 6.2).
TRAILING_TABLES = ("growth", "cash_flow", "capital_allocation")
# Eight quarter ends, the last four the trailing ones and the four before them a year earlier.
EIGHT_QUARTERS = (
    date(2024, 12, 31),
    date(2025, 3, 31),
    date(2025, 6, 30),
    date(2025, 9, 30),
    date(2025, 12, 31),
    date(2026, 3, 31),
    date(2026, 6, 30),
    date(2026, 9, 30),
)
ROWS = {
    "growth": (
        "revenue",
        "revenue_growth",
        "gross_margin",
        "operating_margin",
        "net_margin",
        "eps",
    ),
    "cash_flow": (
        "operating_cash_flow",
        "capital_spending",
        "free_cash_flow",
        "fcf_to_net_income",
        "stock_compensation_to_revenue",
    ),
    "solvency": (
        "cash",
        "debt",
        "net_debt_to_ebitda",
        "interest_coverage",
        "current_ratio",
        "cash_runway_years",
    ),
    "returns": ("roic", "roe", "aggregate_roic_ten_year", "hurdle_rate"),
    "capital_allocation": ("dividends", "buybacks", "share_count_change", "acquisitions"),
    "quality": ("altman_z", "piotroski_f", "beneish_m"),
}


def _row(tables: tuple[Table, ...], table: str, row: str) -> dict[str, Cell]:
    found = next(r for t in tables if t.name == table for r in t.rows if r.name == row)
    return {cell.period: cell for cell in found.cells}


def _value(tables: tuple[Table, ...], table: str, row: str, period: str) -> float | None:
    return _row(tables, table, row)[period].value


def _drop(conn: sqlite3.Connection, dataset: str, field: str, end: str) -> None:
    with transaction(conn):
        conn.execute(
            "DELETE FROM facts WHERE symbol = 'ACME' AND dataset = ? AND field = ?"
            " AND period_end = ?",
            (dataset, field, end),
        )


def _table(tables: tuple[Table, ...], name: str) -> Table:
    return next(t for t in tables if t.name == name)


def _cells(table: Table) -> dict[str, dict[str, Cell]]:
    """Each row's cells by their period."""
    return {r.name: {c.period: c for c in r.cells} for r in table.rows}


def _periods(table: Table) -> list[str]:
    """The table's columns' periods, which every row's cells hold in order."""
    periods = [c.period for c in table.columns]
    for row in table.rows:
        assert [c.period for c in row.cells] == periods, (table.name, row.name)
    return periods


def _store_quarters(conn: sqlite3.Connection, symbol: str, ends: Sequence[date]) -> None:
    """The quarterly income statements and cash flows of ``ends`` in place of the stored ones,
    period i of ``ends`` with the synthetic figures of period i (``refresh/synthetic.py``)."""
    with transaction(conn):
        conn.execute(
            "DELETE FROM facts WHERE symbol = ?"
            " AND dataset IN ('income-quarter', 'cashflow-quarter')",
            (symbol,),
        )
    payloads = {
        "income-quarter": income_quarter(ends, ends),
        "cashflow-quarter": cashflow_quarter(ends, ends),
    }
    store_payloads(conn, symbol, payloads, NOW)


def _consensus(conn: sqlite3.Connection, years: Sequence[int]) -> None:
    """A newer annual consensus answer for AAPL holding ``years`` alone: revenue $2,000 m +
    $200 m a year after 2025, EPS 3.00 + 0.30 a year."""
    rows: list[dict[str, Any]] = [
        {
            "symbol": "AAPL",
            "date": f"{y}-12-31",
            "revenueAvg": (2_000 + 200 * (y - 2025)) * M,
            "epsAvg": 3.0 + 0.3 * (y - 2025),
            "numAnalystsEps": 9,
        }
        for y in reversed(years)  # FMP's order: the furthest year first
    ]
    store_payloads(conn, "AAPL", {"estimates-annual": rows}, NOW)


def test_six_tables_with_five_years(conn: sqlite3.Connection, policy: Policy) -> None:
    tables = financial_tables(conn, "ACME", policy)
    assert tuple(t.name for t in tables) == TABLES == tuple(ROWS)
    for table in tables:
        assert tuple(r.name for r in table.rows) == ROWS[table.name]
        trailing = [TRAILING] if table.name in TRAILING_TABLES else []
        assert _periods(table) == PERIODS + trailing
        assert [(c.kind, c.label) for c in table.columns[:5]] == [("fiscal", p) for p in PERIODS]
        for row in table.rows:
            assert {c.unit for c in row.cells} == {row.unit}

    def at(table: str, row: str) -> float | None:
        return _value(tables, table, row, "2025")

    # fiscal 2025 against the fixture's lines ($ m): revenue 2,100 (2,000 in 2024), gross profit
    # 840, operating income 420, net income 315, operating cash flow 525, capital spending -126,
    # D&A 105, interest 10, current assets 710 and liabilities 300, cash 200 + 50, debt 20 + 300,
    # equity 810 (800 in 2024)
    assert at("growth", "revenue") == 2100 * M
    assert at("growth", "revenue_growth") == pytest.approx(0.05)
    assert at("growth", "gross_margin") == pytest.approx(0.40)
    assert at("growth", "operating_margin") == pytest.approx(0.20)
    assert at("growth", "net_margin") == pytest.approx(0.15)
    assert at("growth", "eps") == pytest.approx(3.15)
    assert at("cash_flow", "operating_cash_flow") == 525 * M
    assert at("cash_flow", "capital_spending") == -126 * M
    assert at("cash_flow", "free_cash_flow") == 399 * M
    assert at("cash_flow", "fcf_to_net_income") == pytest.approx(399 / 315)
    assert at("cash_flow", "stock_compensation_to_revenue") == pytest.approx(20 / 2100)
    assert (at("solvency", "cash"), at("solvency", "debt")) == (250 * M, 320 * M)
    assert at("solvency", "net_debt_to_ebitda") == pytest.approx(70 / 525)
    assert at("solvency", "interest_coverage") == pytest.approx(42.0)
    assert at("solvency", "current_ratio") == pytest.approx(710 / 300)
    runway = _row(tables, "solvency", "cash_runway_years")["2025"]
    assert (runway.value, runway.unit) == (None, "years")
    assert runway.note == "operating cash flow is not negative"
    assert at("returns", "roe") == pytest.approx(315 / 805)
    assert at("returns", "hurdle_rate") == policy.required_return
    assert (at("capital_allocation", "dividends"), at("capital_allocation", "buybacks")) == (
        -40 * M,
        -60 * M,
    )
    assert at("capital_allocation", "share_count_change") == 0.0


def test_returns_read_the_engine_s_roic(conn: sqlite3.Connection, policy: Policy) -> None:
    tables = financial_tables(conn, "ACME", policy)
    capital = statements_for(conn, "ACME", "US", load_tax_table(), date(2026, 11, 1)).capital_years
    engine = aggregate_roic(capital)
    by_year = {str(y.year): y.roic for y in engine.by_year}
    assert {p: c.value for p, c in _row(tables, "returns", "roic").items()} == {
        p: by_year[p] for p in PERIODS
    }
    # the newest cell is the engine's ten-year aggregate; an earlier year has fewer than ten
    # ROIC years behind it in the store, so its cell holds none
    aggregate = _row(tables, "returns", "aggregate_roic_ten_year")
    assert engine.years_used == 10 and engine.aggregate is not None
    assert (aggregate["2025"].value, aggregate["2025"].note) == (engine.aggregate, None)
    earlier = [(aggregate[p].value, aggregate[p].note) for p in PERIODS[:-1]]
    assert earlier == [(None, "the ten-year aggregate is the newest year's figure")] * 4


def test_the_hurdle_rate_of_a_company_in_another_currency_is_restated(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-10 7.5 on FXCO, in SEK at 8.0 a dollar with an inflation differential of 2%:
    the ROIC beside the hurdle rate is in SEK, nominal, so the hurdle rate is the policy's r
    restated by its latest snapshot's differential, 1.09 × 1.02 − 1 = 11.18%, the rate its route
    discounts at; its ``table:`` ref resolves to it. ACME, a USD company, reads the policy's r."""
    refresh_id = add_company(conn, symbols=("FXCO",))
    fxco = value_company(fx_inputs(), universe_deciles(), policy, date(2026, 11, 1))
    insert_snapshot(conn, fxco, refresh_id)
    statements = {e: p for e, p in bodies(currency="SEK").items() if e != "earnings"}
    store_payloads(conn, "FXCO", statements, NOW)
    restated = in_currency(policy, fxco.intermediates["inflation_differential"]).required_return
    assert restated == pytest.approx(0.1118)
    hurdle = _row(financial_tables(conn, "FXCO", policy), "returns", "hurdle_rate")
    assert [cell.value for cell in hurdle.values()] == [restated] * 5
    found = Resolver(conn, "FXCO", policy).resolve("table:FXCO/returns/hurdle_rate/2025")
    assert found is not None and found.value == restated
    usd = _row(financial_tables(conn, "ACME", policy), "returns", "hurdle_rate")
    assert [cell.value for cell in usd.values()] == [policy.required_return] * 5


def test_every_cell_has_a_ref_that_resolves(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Every cell's ref resolves to the cell's value. A fiscal year's ``fact:`` ref names a line
    of ``LINES`` and a fiscal year whose stored fact is the cell's value; a trailing one names
    ``ttm``; an ``estimate:`` ref names the consensus year and the field; a ``table:`` ref is the
    cell's own path, its period the column's."""
    resolver = Resolver(conn, "AAPL", policy)
    forms: dict[str, int] = {}
    for table in financial_tables(conn, "AAPL", policy):
        for row in table.rows:
            for cell in row.cells:
                found = resolver.resolve(cell.ref)
                assert found is not None and found.value == cell.value, cell.ref
                form, _, path = cell.ref.partition(":")
                forms[form] = forms.get(form, 0) + 1
                if form == "table":
                    assert path == f"AAPL/{table.name}/{row.name}/{cell.period}"
                elif form == "estimate":
                    assert path.split("/")[:2] == ["AAPL", cell.period.removesuffix("E")]
                    assert cell.period == estimate_period(int(path.split("/")[1]))
                elif cell.period == TRAILING:
                    assert form == "fact" and path.endswith("/ttm"), cell.ref
                else:
                    assert form == "fact", cell.ref
                    symbol, line, period = path.split("/")
                    assert (symbol, period) == ("AAPL", cell.period)
                    dataset, field = LINES[line]
                    stored = {
                        f.fiscal_year: f.value
                        for f in facts_for(conn, symbol, dataset)
                        if f.field == field
                    }
                    value = stored[int(period)]
                    assert value is not None and cell.value == float(value)
    # revenue, EPS, operating cash flow, capital spending, dividends and buybacks, over the five
    # years and the trailing twelve months; the revenue and the EPS of the two consensus years
    assert (forms["fact"], forms["estimate"]) == (6 * 6, 2 * 2)


def test_z_and_f_on_a_mature_growth_row(conn: sqlite3.Connection, policy: Policy) -> None:
    tables = financial_tables(conn, "ACME", policy)
    z, f = _row(tables, "quality", "altman_z"), _row(tables, "quality", "piotroski_f")
    assert all(c.value is not None and c.unit == "score" for c in (*z.values(), *f.values()))
    # fiscal 2025 ($ m): current assets 710, current liabilities 300, total assets 1,610, total
    # liabilities 800, retained earnings 510, equity 810, operating income 420
    x1, x2, x3, x4 = (710 - 300) / 1610, 510 / 1610, 420 / 1610, 810 / 800
    assert z["2025"].value == pytest.approx(6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4)
    # against 2024 every signal is true but the stock issued ($5 m) and the gross margin (flat)
    assert (f["2025"].value, f["2025"].note) == (7, None)


def test_beneish_m_is_not_on_file(conn: sqlite3.Connection, policy: Policy) -> None:
    tables = financial_tables(conn, "ACME", policy)
    cells = _row(tables, "quality", "beneish_m")
    assert [(c.value, c.note) for c in cells.values()] == [(None, "not on file")] * 5
    assert cells["2024"].ref == "table:ACME/quality/beneish_m/2024"
    # the store keeps no acquisitions line either, over the trailing twelve months too
    acquisitions = _row(tables, "capital_allocation", "acquisitions").values()
    assert [(c.value, c.note) for c in acquisitions] == [(None, "not on file")] * 6


def test_a_missing_line_is_a_none_cell(conn: sqlite3.Connection, policy: Policy) -> None:
    _drop(conn, "income-annual", "grossProfit", "2024-12-31")
    _drop(conn, "balance-annual", "totalAssets", "2025-12-31")
    tables = financial_tables(conn, "ACME", policy)
    margins = _row(tables, "growth", "gross_margin")
    assert margins["2024"].value is None and margins["2025"].value == pytest.approx(0.40)
    z = _row(tables, "quality", "altman_z")
    assert z["2025"].value is None and z["2024"].value is not None
    # without 2025's total assets and 2024's gross profit, four signals are read: operating
    # cash flow, the accrual, the liquidity (true) and the stock issued (false)
    f = _row(tables, "quality", "piotroski_f")["2025"]
    assert (f.value, f.note) == (3, "4 of 9 signals read")


def test_a_cash_runway_when_operating_cash_flow_is_negative(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE facts SET value = '-100000000' WHERE symbol = 'ACME'"
            " AND dataset = 'cashflow-annual' AND field = 'netCashProvidedByOperatingActivities'"
            " AND period_end = '2025-12-31'"
        )
    runway = _row(financial_tables(conn, "ACME", policy), "solvency", "cash_runway_years")
    # cash $250 m over an outflow of $100 m
    assert (runway["2025"].value, runway["2025"].unit, runway["2025"].note) == (2.5, "years", None)
    assert runway["2024"].value is None


def test_no_interest_coverage_on_an_interest_expense_of_zero_says_why(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """The vendor stores some companies' interest expense as 0: the year has no coverage, and the
    cell says why, so the gap does not read as a year not on file."""
    with transaction(conn):
        conn.execute(
            "UPDATE facts SET value = '0' WHERE symbol = 'ACME' AND dataset = 'income-annual'"
            " AND field = 'interestExpense' AND period_end = '2025-12-31'"
        )
    coverage = _row(financial_tables(conn, "ACME", policy), "solvency", "interest_coverage")
    assert (coverage["2025"].value, coverage["2025"].note) == (
        None,
        "the interest expense on file is zero",
    )
    assert coverage["2024"].value is not None and coverage["2024"].note is None


def test_a_roic_on_capital_at_or_below_zero_says_so(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A company its customers pay ahead can hold invested capital below zero, on which a year's
    ROIC has the wrong sign and no meaning: the cell keeps the engine's figure and its note names
    the capital."""
    with transaction(conn):
        conn.execute(
            "UPDATE facts SET value = '9000000000' WHERE symbol = 'ACME'"
            " AND dataset = 'balance-annual' AND field = 'totalCurrentLiabilities'"
            " AND period_end IN ('2024-12-31', '2025-12-31')"
        )
    roic = _row(financial_tables(conn, "ACME", policy), "returns", "roic")
    assert roic["2025"].value is not None and roic["2025"].value < 0
    assert roic["2025"].note == "average invested capital is at or below zero"
    assert roic["2023"].value is not None and roic["2023"].value > 0
    assert roic["2023"].note is None


def test_a_company_without_statements_has_no_cells(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    tables = financial_tables(conn, "NONE", policy)
    assert tuple(t.name for t in tables) == TABLES
    assert all(row.cells == () for t in tables for row in t.rows)
    assert all(t.columns == () for t in tables)


def test_the_growth_table_carries_its_columns_past_the_last_fiscal_year(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    growth = next(t for t in financial_tables(conn, "AAPL", policy) if t.name == "growth")
    assert [(c.period, c.kind, c.label) for c in growth.columns] == [
        ("2021", "fiscal", "2021"),
        ("2022", "fiscal", "2022"),
        ("2023", "fiscal", "2023"),
        ("2024", "fiscal", "2024"),
        ("2025", "fiscal", "2025"),
        ("ttm", "trailing", "12 months to 30 Sep 2026"),
        ("2026E", "estimate", "2026 estimate"),
        ("2027E", "estimate", "2027 estimate"),
    ]
    for row in growth.rows:
        assert [c.period for c in row.cells] == [c.period for c in growth.columns], row.name
    cell = {r.name: {c.period: c for c in r.cells} for r in growth.rows}
    # the four quarters to 30 Sep 2026: revenue 310 + 320 + 330 + 340, operating income 260,
    # net income 190, EPS 0.46 + 0.47 + 0.48 + 0.49
    assert cell["revenue"]["ttm"].value == 1_300 * M
    assert cell["revenue"]["ttm"].ref == "fact:AAPL/revenue/ttm"
    assert cell["operating_margin"]["ttm"].value == pytest.approx(260 / 1300)
    assert cell["operating_margin"]["ttm"].ref == "table:AAPL/growth/operating_margin/ttm"
    assert cell["net_margin"]["ttm"].value == pytest.approx(190 / 1300)
    assert cell["eps"]["ttm"].value == pytest.approx(1.90)
    assert cell["eps"]["ttm"].ref == "fact:AAPL/eps_diluted/ttm"
    assert (cell["gross_margin"]["ttm"].value, cell["gross_margin"]["ttm"].note) == (
        None,
        NOT_TRAILING,
    )
    # five stored quarters: the twelve months before the trailing ones are not all on file
    assert (cell["revenue_growth"]["ttm"].value, cell["revenue_growth"]["ttm"].note) == (
        None,
        SHORT_HISTORY,
    )
    # the estimates: 2026 on the reported 2025 ($2,100 m), 2027 on the 2026 estimate
    assert cell["revenue"]["2026E"].value == 2_200 * M
    assert cell["revenue"]["2026E"].ref == "estimate:AAPL/2026/revenue"
    assert cell["eps"]["2027E"].value == pytest.approx(3.63)
    assert cell["eps"]["2027E"].ref == "estimate:AAPL/2027/eps"
    assert cell["revenue_growth"]["2026E"].value == pytest.approx(2200 / 2100 - 1)
    assert cell["revenue_growth"]["2026E"].ref == "table:AAPL/growth/revenue_growth/2026E"
    assert cell["revenue_growth"]["2027E"].value == pytest.approx(0.10)
    for row in ("gross_margin", "operating_margin", "net_margin"):
        assert (cell[row]["2026E"].value, cell[row]["2026E"].note) == (None, NO_ESTIMATE)


def test_the_cash_flow_and_capital_allocation_tables_gain_the_trailing_column_alone(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The four quarters to 30 Sep 2026: operating cash flow 71 + 72 + 73 + 74, capital spending
    −(21 + 22 + 23 + 24), dividends 4 × −10 and buybacks 4 × −15; net income 190."""
    tables = financial_tables(conn, "AAPL", policy)
    for name in ("cash_flow", "capital_allocation"):
        table = _table(tables, name)
        assert _periods(table) == [*PERIODS, TRAILING], name
        assert (table.columns[-1].kind, table.columns[-1].label) == (
            "trailing",
            "12 months to 30 Sep 2026",
        )
    flows = _cells(_table(tables, "cash_flow"))
    cfo, capex = flows["operating_cash_flow"]["ttm"], flows["capital_spending"]["ttm"]
    assert (cfo.value, cfo.ref) == (290 * M, "fact:AAPL/cfo/ttm")
    assert (capex.value, capex.ref) == (-90 * M, "fact:AAPL/capex/ttm")
    free = flows["free_cash_flow"]["ttm"]
    assert (free.value, free.ref) == (200 * M, "table:AAPL/cash_flow/free_cash_flow/ttm")
    assert flows["fcf_to_net_income"]["ttm"].value == pytest.approx(200 / 190)
    # the quarter to 31 Mar 2026 has no stock compensation, so neither has the sum
    sbc = flows["stock_compensation_to_revenue"]["ttm"]
    assert (sbc.value, sbc.note) == (None, None)
    allocation = _cells(_table(tables, "capital_allocation"))
    dividends, buybacks = allocation["dividends"]["ttm"], allocation["buybacks"]["ttm"]
    assert (dividends.value, dividends.ref) == (-40 * M, "fact:AAPL/dividends/ttm")
    assert (buybacks.value, buybacks.ref) == (-60 * M, "fact:AAPL/buybacks/ttm")
    shares, acquisitions = (
        allocation["share_count_change"]["ttm"],
        allocation["acquisitions"]["ttm"],
    )
    assert (shares.value, shares.note) == (None, NOT_TRAILING)
    assert (acquisitions.value, acquisitions.note) == (None, NOT_ON_FILE)
    assert shares.ref == "table:AAPL/capital_allocation/share_count_change/ttm"


def test_returns_solvency_and_quality_keep_their_fiscal_columns(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    tables = financial_tables(conn, "AAPL", policy)
    for name in ("returns", "solvency", "quality"):
        table = _table(tables, name)
        assert _periods(table) == PERIODS, name
        assert {c.kind for c in table.columns} == {"fiscal"}, name


def test_a_year_ago_on_file_gives_the_trailing_revenue_growth(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Eight stored quarters, period i with revenue $300 m + $10 m × i: the trailing revenue is
    340 + 350 + 360 + 370 and the four quarters before it 300 + 310 + 320 + 330."""
    _store_quarters(conn, "ACME", EIGHT_QUARTERS)
    growth = _cells(_table(financial_tables(conn, "ACME", policy), "growth"))
    assert growth["revenue"]["ttm"].value == 1_420 * M
    found = growth["revenue_growth"]["ttm"]
    assert (found.value, found.note) == (pytest.approx(1420 / 1260 - 1), None)
    assert found.ref == "table:ACME/growth/revenue_growth/ttm"


def test_a_gap_in_the_year_before_gives_no_trailing_revenue_growth(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Nine quarters stored but the one to 31 Mar 2025: the four stored before the trailing ones
    span more than the twelve months before them, so they are not that year."""
    nine = (date(2024, 9, 30), *EIGHT_QUARTERS)
    _store_quarters(conn, "ACME", [end for end in nine if end != date(2025, 3, 31)])
    growth = _cells(_table(financial_tables(conn, "ACME", policy), "growth"))
    assert growth["revenue"]["ttm"].value is not None
    found = growth["revenue_growth"]["ttm"]
    assert (found.value, found.note) == (None, SHORT_HISTORY)


def test_no_trailing_column_when_the_trailing_figures_stand_on_the_fiscal_year(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    _store_quarters(conn, "ACME", ())
    stated = statements_for(conn, "ACME", "US", load_tax_table(), date.min)
    assert stated.trailing is not None and stated.trailing.on_fiscal_year
    for table in financial_tables(conn, "ACME", policy):
        assert _periods(table) == PERIODS, table.name


def test_no_trailing_column_when_the_trailing_period_ends_with_the_fiscal_year(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Four quarters summed, the last ending 31 Dec 2025 as fiscal 2025 does: the trailing twelve
    months are that fiscal year's."""
    _store_quarters(
        conn,
        "ACME",
        (date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)),
    )
    trailing = statements_for(conn, "ACME", "US", load_tax_table(), date.min).trailing
    assert trailing is not None and not trailing.on_fiscal_year
    assert trailing.period_end == date(2025, 12, 31)
    for table in financial_tables(conn, "ACME", policy):
        assert _periods(table) == PERIODS, table.name


def test_a_consensus_year_already_reported_gives_no_estimate_column(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The consensus still holds fiscal 2025, which is on file: its column is the reported year's
    and no ``2025E`` stands beside it."""
    _consensus(conn, [2025, 2026, 2027, 2028, 2029])
    growth = _table(financial_tables(conn, "AAPL", policy), "growth")
    periods = _periods(growth)
    assert "2025E" not in periods and periods[:5] == PERIODS
    cells = _cells(growth)
    assert cells["revenue"]["2025"].value == 2_100 * M
    assert cells["revenue"]["2025"].ref == "fact:AAPL/revenue/2025"


def test_at_most_three_estimate_years(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    _consensus(conn, [2025, 2026, 2027, 2028, 2029])
    growth = _table(financial_tables(conn, "AAPL", policy), "growth")
    estimates = [c.period for c in growth.columns if c.kind == "estimate"]
    assert estimates == ["2026E", "2027E", "2028E"] and len(estimates) == ESTIMATE_YEARS
    assert _periods(growth) == [*PERIODS, TRAILING, *estimates]
    cells = _cells(growth)
    assert cells["revenue"]["2028E"].value == 2_600 * M
    assert cells["revenue_growth"]["2028E"].value == pytest.approx(2600 / 2400 - 1)


def test_a_gap_in_the_consensus_years_leaves_the_growth_after_it_empty(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    _consensus(conn, [2026, 2028])
    growth = _table(financial_tables(conn, "AAPL", policy), "growth")
    assert [c.period for c in growth.columns if c.kind == "estimate"] == ["2026E", "2028E"]
    cells = _cells(growth)
    assert cells["revenue_growth"]["2026E"].value == pytest.approx(2200 / 2100 - 1)
    assert cells["revenue"]["2028E"].value == 2_600 * M
    assert cells["revenue_growth"]["2028E"].value is None  # no figure for 2027


def test_a_half_year_filer_sums_two_halves(conn: sqlite3.Connection, policy: Policy) -> None:
    """Four half-years to 30 Jun 2026, half i with revenue $300 m + $10 m × i: the trailing
    revenue is 320 + 330 and the two halves before it 300 + 310; without the oldest half the
    twelve months before are not all on file."""
    payloads = {e: p for e, p in bodies(cadence="half-yearly").items() if e != "earnings"}
    store_payloads(conn, "HALF", payloads, NOW)
    growth = _table(financial_tables(conn, "HALF", policy), "growth")
    assert _periods(growth) == [*PERIODS, TRAILING]
    assert growth.columns[-1].label == "12 months to 30 Jun 2026"
    cells = _cells(growth)
    assert cells["revenue"]["ttm"].value == 650 * M
    assert cells["revenue_growth"]["ttm"].value == pytest.approx(650 / 610 - 1)
    with transaction(conn):
        conn.execute(
            "DELETE FROM facts WHERE symbol = 'HALF' AND period_end = ?"
            " AND dataset IN ('income-quarter', 'cashflow-quarter')",
            (HALF_YEARS[0].isoformat(),),
        )
    growth = _table(financial_tables(conn, "HALF", policy), "growth")
    found = _cells(growth)["revenue_growth"]["ttm"]
    assert (found.value, found.note) == (None, SHORT_HISTORY)


def test_a_company_with_no_consensus_has_no_estimate_column(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    for table in financial_tables(conn, "ACME", policy):
        assert "estimate" not in {c.kind for c in table.columns}, table.name
