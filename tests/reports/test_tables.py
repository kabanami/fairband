"""The six financial tables of a report's section 4 (spec 2026-11-06 Tier 2, 13.5; design.md 9.3)
on the synthetic company of ``conftest.py``: ACME, a Mature Growth company with revenue of
$1,000 m in 2014 up $100 m a year, a 40% gross margin, a 20% operating margin, a 15% net margin,
and balance lines every year (``refresh/synthetic.py`` states the lines)."""

import sqlite3
from datetime import date

import pytest
from refresh.synthetic import NOW, add_company, bodies
from support.engine_companies import fx_inputs, universe_deciles
from support.payloads import store_payloads

from fairband.engine.roic import aggregate_roic
from fairband.engine.route import value_company
from fairband.policy import Policy, in_currency
from fairband.policy.tax import load_tax_table
from fairband.refresh.inputs_statements import statements_for
from fairband.reports.refs import Resolver
from fairband.reports.tables import LINES, TABLES, Cell, Table, financial_tables
from fairband.store.db import transaction
from fairband.store.facts import facts_for
from fairband.store.snapshots import insert_snapshot

M = 1_000_000
PERIODS = ["2021", "2022", "2023", "2024", "2025"]
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


def test_six_tables_with_five_years(conn: sqlite3.Connection, policy: Policy) -> None:
    tables = financial_tables(conn, "ACME", policy)
    assert tuple(t.name for t in tables) == TABLES == tuple(ROWS)
    for table in tables:
        assert tuple(r.name for r in table.rows) == ROWS[table.name]
        for row in table.rows:
            assert [c.period for c in row.cells] == PERIODS
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


def test_every_cell_has_a_ref_that_resolves(conn: sqlite3.Connection, policy: Policy) -> None:
    """A ``fact:`` ref names a line of ``LINES`` and a fiscal year whose stored fact is the cell's
    value; a ``table:`` ref is the cell's own path."""
    facts = 0
    for table in financial_tables(conn, "ACME", policy):
        for row in table.rows:
            for cell in row.cells:
                form, _, path = cell.ref.partition(":")
                if form == "table":
                    assert path == f"ACME/{table.name}/{row.name}/{cell.period}"
                    continue
                assert form == "fact", cell.ref
                symbol, line, period = path.split("/")
                assert (symbol, period) == ("ACME", cell.period)
                dataset, field = LINES[line]
                stored = {
                    f.fiscal_year: f.value
                    for f in facts_for(conn, symbol, dataset)
                    if f.field == field
                }
                assert stored[int(period)] is not None and cell.value == float(stored[int(period)])
                facts += 1
    # revenue, EPS, operating cash flow, capital spending, dividends and buybacks
    assert facts == 6 * 5


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
    # the store keeps no acquisitions line either
    acquisitions = _row(tables, "capital_allocation", "acquisitions").values()
    assert [(c.value, c.note) for c in acquisitions] == [(None, "not on file")] * 5


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


def test_a_company_without_statements_has_no_cells(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    tables = financial_tables(conn, "NONE", policy)
    assert tuple(t.name for t in tables) == TABLES
    assert all(row.cells == () for t in tables for row in t.rows)
