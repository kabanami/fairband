# The Report the Reader Sees Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A report's tables and charts show the trailing twelve months, the analysts' estimates and the stored quarters; the lines the server writes above the sections read as the register rules; Appendix A shows an override's two figures at a split; the export and the print read right; the playbook's words state the method as it runs.

**Architecture:** The financial tables (`reports/tables.py`) carry their columns, each with a period, a kind and a label, and gain trailing and estimate cells; a quarters table stands beside the six. The export (`reports/charts.py`, `reports/render.py`) and the page (`web/static/charts.js`, `report.js`) read the columns' labels from the server. A marked patch to the design-system copy lets a `HistoryBars` point carry a kind. Nothing is stored: every report on file renders from the store as before.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite; plain JavaScript with React from the design-system bundle; pytest, with node for the page's own script (`tests/web/page.mjs`).

**Spec:** `docs/superpowers/specs/2026-11-15-report-reader-design.md`. Read it with your task: this plan argues from it, and where the two differ the spec wins. A map of the code as it stood before Task 1, with files and lines, is at `/tmp/claude-1000/-home-kaban-workspace-fairband/941bce1d-7722-449c-bac8-0ac2be879850/scratchpad/theme6-map.md`.

## Global Constraints

- No file under `src/fairband/engine/`, `src/fairband/policy/` or `src/fairband/refresh/` changes, save a read that Task 1 or Task 2 names. No value, level, flag, snapshot or review moves. The method stays `fairband-mechanical/1.5`, the policy v16. `docs/method.md` section 11 gains no row.
- No schema change and no migration. Nothing new is stored. Every report on file renders after each task.
- A label a reader sees (a column's, a chart's title, the line under a chart) is made once, on the server, and read by the page and the export.
- A change to the design-system copy under `src/fairband/web/static/design-system/` is a patch: marked `// fairband: <why>` in `bundle.js`, `/* fairband: <why> */` in `bundle.css`, `fairband:` in the doc comment of `index.d.ts`, and pinned by a substring test in `tests/web/test_app.py` as the `inverse` patch is.
- Never print, log, store or commit a key. Never commit vendor data: fixtures are synthetic.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, then a blank line, then these two lines in this order, the second naming the model that wrote the change:
  `Claude-Session: https://claude.ai/code/session_01K4pNFGb6uWekaVUA4NgJbB`
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- `docs/method.md` changes in the same commit as the code it describes; each paragraph of it is one line.

## Review Focus

Five conditions the spec implies and a hurried build would miss. Each has its test in the task that owns the code.

1. **A company in another currency.** A trailing and an estimate cell of a total or a figure a share print with the currency's code in the export, as a fiscal cell does (Task 3).
2. **The fiscal year just closed.** Trailing figures that stand on the last fiscal year, or end on its period end, give no trailing column; a consensus row for a year already reported gives no estimate column (Task 1).
3. **A company that reports twice a year.** Its trailing figures sum two half-years; its year-ago revenue needs four stored halves; its quarters table holds half-years under their own labels (Tasks 1 and 2).
4. **A report written before the change, and a cite that outlives its cell.** A stored report renders, page and export; a `table:` cite of `2026E` still reads its words in the references after fiscal 2026 is reported and the cell is gone (Tasks 1 and 3).
5. **Bars that are not the usual run.** A signed series with an estimate below zero, a chart whose every point is an estimate, and a chart with one point each draw, with the value on the last bar that is not an estimate or on none (Task 4).

---

### Task 1: The tables' columns, the trailing column and the estimate columns (spec 6.1 to 6.3, 6.5)

**Files:**
- Modify: `src/fairband/reports/tables.py`, `src/fairband/reports/refs.py` (`_period_words`), `src/fairband/reports/check.py` (`_period`), `docs/method.md` (16.2, 16.5)
- Test: `tests/reports/test_tables.py`, `tests/reports/test_refs.py`, `tests/reports/test_check.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: `Statements.trailing` (`TrailingFigures`: `period_end`, `quarters`, `on_fiscal_year`, the lines), `stored_quarters(conn, symbol)` and the stored annual consensus as the resolver's `estimate:` refs read it (`refs.py`, `Resolver._estimate`). `tables.py` must not import `reports.refs`.
- Produces, in `src/fairband/reports/tables.py`:

```python
Kind = Literal["fiscal", "trailing", "estimate", "quarter"]

@dataclass(frozen=True)
class Column:
    period: str  # "2025", "ttm", "2026E", "2026-Q3": equal to the period of each cell under it
    kind: Kind
    label: str   # "2025", "12 months to 30 Sep 2026", "2026 estimate", "Q3 2026"

@dataclass(frozen=True)
class Table:
    name: str
    rows: tuple[Row, ...]
    columns: tuple[Column, ...] = ()

TRAILING = "ttm"
ESTIMATE_YEARS = 3
NOT_TRAILING = "not measured over the trailing twelve months"
NO_ESTIMATE = "no estimate for this line"
SHORT_HISTORY = "fewer than two years of periods on file"

def estimate_period(year: int) -> str: ...  # "2026E"
```

  `financial_tables(conn, symbol, policy, tax=None)` keeps its signature and its six tables in order. Every row of a table has one cell for each of the table's columns, in order, with `cell.period == column.period`. `asdict(table)` therefore serves `columns` to `/financial-tables`.
- Produces, in `refs.py`: `_period_words("2026E") == "fiscal 2026, the analysts' estimate"`. In `check.py`: `_period("2026E") == _period("2026")`.

- [ ] **Step 1: Write the failing tests.** In `tests/reports/test_tables.py`, on the `snapshots` fixture (AAPL: fiscal years to 2025, five quarters to 2026-09-30, consensus for 2026 and 2027):

```python
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
```

  And, each a test of its own, with the assertions its name says:
  - `test_the_cash_flow_and_capital_allocation_tables_gain_the_trailing_column_alone`: `cash_flow`'s and `capital_allocation`'s columns are the five fiscal years then `ttm`; operating cash flow 290 × M citing `fact:AAPL/cfo/ttm`, capital spending −90 × M, free cash flow 200 × M citing `table:AAPL/cash_flow/free_cash_flow/ttm`, free cash flow over net income `200 / 190`; dividends −40 × M and buybacks −60 × M citing their `fact:` refs; share count change `(None, NOT_TRAILING)`, acquisitions `(None, NOT_ON_FILE)`.
  - `test_returns_solvency_and_quality_keep_their_fiscal_columns`: each has exactly the five fiscal columns.
  - `test_a_year_ago_on_file_gives_the_trailing_revenue_growth`: with eight stored quarters (store `income_quarter` and `cashflow_quarter` over eight period ends), the cell is the last four's revenue over the four before − 1.
  - `test_no_trailing_column_when_the_trailing_figures_stand_on_the_fiscal_year` and `test_no_trailing_column_when_the_trailing_period_ends_with_the_fiscal_year` (Review Focus 2): delete the quarterly facts for the first; for the second store quarters that end on 2025-12-31.
  - `test_a_consensus_year_already_reported_gives_no_estimate_column` (Review Focus 2) and `test_at_most_three_estimate_years`: consensus rows for 2025, 2026, 2027, 2028 and 2029 give `2026E`, `2027E`, `2028E`.
  - `test_a_gap_in_the_consensus_years_leaves_the_growth_after_it_empty`: consensus for 2026 and 2028 only: `revenue_growth` of `2028E` is `None`.
  - `test_a_half_year_filer_sums_two_halves` (Review Focus 3): on `HALF_YEARS` payloads the trailing column stands, and the year-ago revenue needs four stored halves.
  - `test_a_company_with_no_consensus_has_no_estimate_column`: the `conn` fixture's ACME.
  - Extend the existing test that every cell's ref resolves to the cell's value (line 157) to the new cells.

  In `tests/reports/test_refs.py`: `table:AAPL/growth/revenue_growth/ttm` reads "the growth table, revenue growth, the trailing twelve months"; `table:AAPL/growth/revenue_growth/2026E` reads "the growth table, revenue growth, fiscal 2026, the analysts' estimate", and still reads those words on a store whose consensus no longer has 2026 (Review Focus 4: `describe` must not need the cell). In `tests/reports/test_check.py`: a section citing an estimate cell with the period `2026E`, and one with `2026`, both pass, on the `estimate:` ref and on the `table:` ref; a cite of `table:AAPL/growth/revenue/2029E` is an unresolved reference.

- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/reports/test_tables.py tests/reports/test_refs.py tests/reports/test_check.py` — the new tests fail on `columns` and on the missing cells.

- [ ] **Step 3: Implement.** In `tables.py`: the `Column` record, the constants, `estimate_period`; `_Figures` builds each table's columns once and each row's cells for them. The trailing column stands by spec 6.2's three conditions. The year-ago revenue is the sum over the `n` stored periods that precede the trailing figures' `n` periods (`n = trailing.quarters`), `None` unless all `n` are stored with a revenue. The estimate columns are the consensus fiscal years after the newest fiscal year on file that hold a revenue or an EPS, the first `ESTIMATE_YEARS`. In `refs.py` and `check.py`, the two period rules above.

- [ ] **Step 4: The method document.** 16.5 gains the columns, the three tables' trailing cells and the growth table's estimate cells, each as spec 6.1 to 6.3 states it; 16.2 says a `table:` ref's period may be `ttm` or a year and `E`, and that the check reads `2026E` as the year. Pin each sentence in `tests/test_method_doc.py`.

- [ ] **Step 5: Run the four commands, then commit.**

### Task 2: The quarters table (spec 6.4, 6.5)

**Files:**
- Modify: `src/fairband/reports/tables.py`, `src/fairband/reports/refs.py` (`Resolver._table`), `src/fairband/web/reports_api.py` (`/financial-tables`), `docs/method.md` (16.5)
- Test: `tests/reports/test_tables.py`, `tests/reports/test_refs.py`, `tests/web/test_company_reads.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: Task 1's `Column`, `Table`, `Kind`; `stored_quarters(conn, symbol)` (`refresh/inputs_statements.py`).
- Produces:

```python
QUARTERS = "quarters"   # the table's name
QUARTERS_SHOWN = 8

def quarters_table(conn: sqlite3.Connection, symbol: str) -> Table: ...
```

  Rows, in order: `revenue` (unit `currency`, each cell `fact:<symbol>/revenue/<period>`), `operating_margin` (`percent`, `table:<symbol>/quarters/operating_margin/<period>`), `eps` (`per-share`, `fact:<symbol>/eps_diluted/<period>`). Columns: the newest `QUARTERS_SHOWN` stored periods, oldest first, kind `quarter`, the period the stored period's own (`2026-Q3`), the label the fiscal period then the fiscal year ("Q3 2026"). No stored period: the table with no column and three rows without cells.
- `GET /api/companies/{symbol}/financial-tables` answers `{"symbol", "currency", "tables": [...six...], "quarters": {...}}`.
- A `table:<symbol>/quarters/<row>/<period>` ref resolves through `Resolver._table` and reads "the quarters table, operating margin, Q3 of fiscal 2026".

- [ ] **Step 1: Write the failing tests.**

```python
def test_the_quarters_table_holds_the_stored_periods(conn: sqlite3.Connection) -> None:
    table = quarters_table(conn, "ACME")  # five stored quarters, 30 Sep 2025 to 30 Sep 2026
    assert table.name == "quarters" and [r.name for r in table.rows] == [
        "revenue",
        "operating_margin",
        "eps",
    ]
    assert [(c.period, c.kind, c.label) for c in table.columns] == [
        ("2025-Q3", "quarter", "Q3 2025"),
        ("2025-Q4", "quarter", "Q4 2025"),
        ("2026-Q1", "quarter", "Q1 2026"),
        ("2026-Q2", "quarter", "Q2 2026"),
        ("2026-Q3", "quarter", "Q3 2026"),
    ]
    cell = {r.name: {c.period: c for c in r.cells} for r in table.rows}
    assert cell["revenue"]["2026-Q3"].value == 340 * M
    assert cell["revenue"]["2026-Q3"].ref == "fact:ACME/revenue/2026-Q3"
    assert cell["operating_margin"]["2026-Q3"].value == pytest.approx(68 / 340)
    assert cell["operating_margin"]["2026-Q3"].ref == "table:ACME/quarters/operating_margin/2026-Q3"
    assert cell["eps"]["2025-Q3"].value == pytest.approx(0.45)
```

  And: `test_the_quarters_table_shows_the_newest_eight` (ten stored periods give the last eight); `test_a_company_without_stored_periods_has_the_table_without_columns`; `test_a_half_year_filer_s_quarters_table_holds_its_half_years` (Review Focus 3: the columns are the stored half-years under the store's own period names); `test_a_quarter_without_revenue_has_no_margin` (the margin is `None` where revenue is missing or at or below zero); the ref test above in `test_refs.py`; in `tests/web/test_company_reads.py`, the read's `quarters` key and that `tables` still holds six.

- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement** `quarters_table`, the resolver's branch for the table named `QUARTERS`, and the read's key. `financial_tables` still returns six.
- [ ] **Step 4: The method document.** 16.5 gains the quarters table as spec 6.4 states it, pinned.
- [ ] **Step 5: Run the four commands, then commit.**

### Task 3: The export (spec 6.5, 9)

**Files:**
- Modify: `src/fairband/reports/charts.py`, `src/fairband/reports/render.py`, `docs/method.md` (16.6)
- Test: `tests/reports/test_charts.py`, `tests/reports/test_render.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: Task 1's columns; Task 2's `quarters_table`.
- Produces, in `charts.py`: `QUARTERS_TITLE = "By quarter"`; `chart_tables(...)` gains the key `HEADINGS[4]` ("The last earnings call") whose value is one `ChartTable(QUARTERS_TITLE, ("Period", *labels), rows)`, or one with no rows where no period is stored; a financial table's header is `("Fiscal year", *labels)` when every column is fiscal and `("Period", *labels)` otherwise. The statistics rows of section 9 read `SERIES_TITLES`' names.
- Produces, in `render.py`: the export's order is the sections, `## Appendix A`, `## Appendix B`, `## References`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_section_4_carries_the_trailing_and_estimate_columns_under_their_labels(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    financial = chart_tables(conn, _report(conn, snapshots["AAPL"]), policy)[HEADINGS[3]]
    growth, returns = financial[0], financial[3]
    assert growth.header == (
        "Period",
        "2021",
        "2022",
        "2023",
        "2024",
        "2025",
        "12 months to 30 Sep 2026",
        "2026 estimate",
        "2027 estimate",
    )
    revenue = dict(zip(growth.header[1:], next(r for r in growth.rows if r[0] == "Revenue")[1:]))
    assert revenue["12 months to 30 Sep 2026"] == "$1,300,000,000"
    assert revenue["2026 estimate"] == "$2,200,000,000"
    assert returns.header == ("Fiscal year", "2021", "2022", "2023", "2024", "2025")


def test_section_5_leads_with_the_quarters(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    tables = chart_tables(conn, _report(conn, snapshots["AAPL"]), policy)
    assert list(tables) == [HEADINGS[3], HEADINGS[4], "Valuation", "Price and multiples"]
    [quarters] = tables[HEADINGS[4]]
    assert quarters.title == "By quarter"
    assert quarters.header == ("Period", "Q3 2025", "Q4 2025", "Q1 2026", "Q2 2026", "Q3 2026")
    assert [row[0] for row in quarters.rows] == ["Revenue", "Operating margin", "EPS"]
    assert quarters.rows[0][-1] == "$340,000,000" and quarters.rows[1][-1] == "20.0%"
```

  And: update `test_the_charts_lead_three_sections` to the four keys; in the test of a company in another currency (line 236), a trailing and an estimate cell of revenue and of EPS carry the code (Review Focus 1; give the fixture a trailing period and a consensus year); the P/E statistics rows are named "Trailing P/E" and "Forward P/E"; in `tests/reports/test_render.py`, the Markdown's headings run sections, "Appendix A", "Appendix B", "References", each footnote definition stands under "References", and section 5 of a valuation review carries "### By quarter"; a report stored by the fixture before any of this renders through `markdown` with no error and with its section 4 tables (Review Focus 4).

- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** `_financial` reads the header from the columns' labels; `row_name` covers the quarters' rows; `chart_tables` adds the key; `render.markdown` moves the references after Appendix B. Where the page's script orders its parts by `chart_tables`' keys, nothing changes here: Task 5 owns the page.
- [ ] **Step 4: The method document.** 16.6: the export's order; the chart tables' columns and the "Period" header; section 5's table; the statistics rows' names. Pinned.
- [ ] **Step 5: Run the four commands, then commit.**

### Task 4: A bar's kind in the design-system copy (spec 6.6)

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (`HistoryBars`, its table twin), `bundle.css`, `index.d.ts`
- Test: `tests/web/test_app.py` (the patch's pins), `tests/web/test_report_charts.py` (node), `tests/web/page.mjs` if a helper must be reached

**Interfaces:**
- Produces, in `index.d.ts`:

```ts
export interface BarPoint {
  period: string;
  value: number;
  freshness?: Freshness;
  /** fairband: a bar that is not a fiscal year: the trailing twelve months, or an estimate. */
  kind?: 'trailing' | 'estimate';
  /** fairband: the period in words, for the table twin and the tooltip; the period when absent. */
  label?: string;
}
export interface HistoryBarsProps {
  // … as today, and:
  /** fairband: what the bars run by, for the accessible name; 'fiscal year' when absent. */
  by?: string;
}
```

- A point's bar takes the class `fb-c__bar--trailing` or `fb-c__bar--estimate` beside the classes it has today. CSS: a trailing bar fills `var(--chart-context)`; an estimate bar has no fill and a 1.5px stroke in the colour its fill would have had (`chart-1`, or the sign's colour on a signed series). The value above a bar goes to the last point whose `kind` is not `estimate`, and to none where every point is an estimate. The accessible name is `title + ' by ' + (by || 'fiscal year')`. The table twin's period cell and the tooltip read `label` where a point has one.

- [ ] **Step 1: Write the failing tests.** In node, through `page.mjs`, call the bundle's `HistoryBars` with the stub React and read the element tree (add a helper to `tests/web/test_report_charts.py` that walks the tree for elements whose `className` holds `fb-c__bar`):
  - `test_a_trailing_and_an_estimate_bar_take_their_classes`: series of 2024, 2025, a `trailing` point and two `estimate` points: the bars' class lists, in order, end `[..., 'fb-c__bar', 'fb-c__bar', 'fb-c__bar fb-c__bar--trailing', 'fb-c__bar fb-c__bar--estimate', 'fb-c__bar fb-c__bar--estimate']` (with the sign's class kept on a signed series).
  - `test_the_value_stands_on_the_last_bar_that_is_not_an_estimate`: the one `fb-c__capvalue` element carries the trailing point's value; with no trailing point, the last fiscal year's.
  - `test_a_chart_of_estimates_alone_prints_no_value_and_one_bar_draws` (Review Focus 5): every point an estimate gives no `fb-c__capvalue`; a single fiscal point draws one bar with its value.
  - `test_an_estimate_below_zero_keeps_the_sign_s_class` (Review Focus 5).
  - `test_the_accessible_name_reads_what_the_bars_run_by`: `by: 'quarter'` gives "… by quarter"; absent, "… by fiscal year".
  - `test_the_table_twin_reads_the_label`: with `tableView: true`, the period cells read the points' labels.
  In `tests/web/test_app.py`, beside the `inverse` pins: the `// fairband:` comment of each change in `bundle.js`, the two CSS rules with their `/* fairband: */` marks, and the three fields in `index.d.ts`.

- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement the patch**, each change marked. Change nothing else in the bundle.
- [ ] **Step 4: Run the four commands, then commit.**

### Task 5: The page's charts past the fiscal year and by quarter (spec 6.5, 6.6)

**Files:**
- Modify: `src/fairband/web/static/charts.js`, `src/fairband/web/static/report.js` if the read's shape needs it
- Test: `tests/web/test_report_charts.py` (node), `tests/web/test_app.py`

**Interfaces:**
- Consumes: the `/financial-tables` read of Tasks 1 and 2 (`tables[].columns`, `quarters`); Task 4's `kind`, `label` and `by`.
- Produces, on `P.reportCharts` beside `draw` and `roicPoints`, for the node tests:
  - `points(row, columns)`: one point for each cell with a value, `{ period, value, kind?, label }`, where `period` is the tick under the bar: the year for a fiscal column, `to date` for the trailing one, the period (`2026E`) for an estimate, and `Q3 26` for a quarter; `kind` is `trailing` or `estimate` and absent otherwise; `label` is the column's label.
  - `kindsLine(columns)`: the line under a chart, from the labels: "Grey: the 12 months to 30 Sep 2026. Outlined: analysts' estimates."; the first sentence alone without an estimate column, the second alone without a trailing one, `null` with neither.
- `draw` returns charts for a fourth heading, "The last earnings call": three `HistoryBars`, revenue, the operating margin and EPS, titled by the rows' names under the part title "By quarter", each with `by: 'quarter'`. A section 4 chart whose table has a trailing or an estimate column passes `by: 'period'` and shows `kindsLine` under it.

- [ ] **Step 1: Write the failing tests**, in node:

```python
def test_a_chart_s_points_carry_each_column_s_kind_and_label() -> None:
    columns = [
        {"period": "2025", "kind": "fiscal", "label": "2025"},
        {"period": "ttm", "kind": "trailing", "label": "12 months to 30 Sep 2026"},
        {"period": "2026E", "kind": "estimate", "label": "2026 estimate"},
    ]
    row = {"name": "revenue", "unit": "currency", "cells": [
        {"period": "2025", "value": 2100.0}, {"period": "ttm", "value": 1300.0},
        {"period": "2026E", "value": 2200.0}]}
    assert _call("reportCharts.points", row, columns) == [
        {"period": "2025", "value": 2100.0, "label": "2025"},
        {"period": "to date", "value": 1300.0, "kind": "trailing",
         "label": "12 months to 30 Sep 2026"},
        {"period": "2026E", "value": 2200.0, "kind": "estimate", "label": "2026 estimate"},
    ]


def test_the_line_under_a_chart_names_the_grey_and_the_outlined_bars() -> None:
    trailing = {"period": "ttm", "kind": "trailing", "label": "12 months to 30 Sep 2026"}
    estimate = {"period": "2026E", "kind": "estimate", "label": "2026 estimate"}
    fiscal = {"period": "2025", "kind": "fiscal", "label": "2025"}
    assert _call("reportCharts.kindsLine", [fiscal, trailing, estimate]) == (
        "Grey: the 12 months to 30 Sep 2026. Outlined: analysts' estimates."
    )
    assert _call("reportCharts.kindsLine", [fiscal, trailing]) == (
        "Grey: the 12 months to 30 Sep 2026."
    )
    assert _call("reportCharts.kindsLine", [fiscal, estimate]) == "Outlined: analysts' estimates."
    assert _call("reportCharts.kindsLine", [fiscal]) is None
```

  And: a cell with no value is left out and its column's kind does not shift the others; a quarter column's tick is `Q3 26`; a table served without `columns` (a cached page against an older server answer) draws its fiscal cells as today; `draw` on a body with `quarters` returns the fourth heading with three charts, and with no stored period the section's "No data on file." panels; the static pins of `tests/web/test_app.py` for the charts follow (the `draw` keys, the part title "By quarter" equal to `charts.QUARTERS_TITLE`, the row titles equal to `row_name`).

- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** `bars` reads the table's columns; `spread` and `returned` keep their fiscal points; the fourth heading's charts read `body.quarters`.
- [ ] **Step 4: Run the four commands, then commit.**

### Task 6: The server's own words and the dates (spec 7)

**Files:**
- Modify: `src/fairband/reports/render.py`, `src/fairband/web/static/report.js`, `src/fairband/web/static/design-system/components/bundle.js` (the reader's `cites` line, a marked patch) and `index.d.ts`, `docs/method.md` (16.6)
- Test: `tests/reports/test_render.py`, `tests/web/test_report_charts.py` or a new node test file for the reader's line, `tests/web/test_app.py`, `tests/test_method_doc.py`

**Interfaces:**
- Produces, in `render.py`: `resting_words(data_date: date, price_date: date | None, valid_until: date | None) -> str`, the sentence without the stance: "On the data of 4 Nov 2026, priced that day, valid until 27 Jan 2027." With another price day: "…, priced 3 Nov 2026, valid until …". With no price date the "priced" part is left out; with no validity date the "valid until" part is.
- The export's first line writes its date with `refs.day_words`. Its line on a reused report reads "Reuses the full report of 3 Nov 2026." (the reused report's date).
- Appendix A: the Inputs table's "As of" and the guidance's "Call" are written with `day_words`; the sentence for no secondary valuation reads "No secondary valuation: Fairband's own valuation gives the company a value" where today's reason is "the route values the company", "No secondary valuation: the review gives the company a value" for the review's, and "No secondary valuation: " and the reason as it stands for any other. If the reason's words are shared with a refusal the API serves, map them where Appendix A's sentence is built and leave the refusal's words alone.
- The reader's line under the title (`ReportReader`'s `cites`): the caller passes `cites: { dataDate, priceDate, validUntil, reusesFullReportOf }` and the line reads "On the data of 4 Nov 2026 · priced that day · valid until 27 Jan 2027 · reuses the full report of 3 Nov 2026", each part by the same rule, with no id.

- [ ] **Step 1: Write the failing tests.**

```python
@pytest.mark.parametrize(
    ("data", "price", "valid", "words"),
    [
        (date(2026, 11, 4), date(2026, 11, 4), date(2027, 1, 27),
         "On the data of 4 Nov 2026, priced that day, valid until 27 Jan 2027."),
        (date(2026, 11, 4), date(2026, 11, 3), date(2027, 1, 27),
         "On the data of 4 Nov 2026, priced 3 Nov 2026, valid until 27 Jan 2027."),
        (date(2026, 11, 4), None, date(2027, 1, 27),
         "On the data of 4 Nov 2026, valid until 27 Jan 2027."),
        (date(2026, 11, 4), date(2026, 11, 4), None,
         "On the data of 4 Nov 2026, priced that day."),
    ],
)
def test_the_export_says_what_the_report_rests_on_in_the_reader_s_words(
    data: date, price: date | None, valid: date | None, words: str
) -> None:
    assert resting_words(data, price, valid) == words
```

  And: the export of the fixture's report has a first line whose date is in words and a second line that begins "Stance: " and holds neither "snapshot" nor an ISO date; a valuation review that reuses a full report says "Reuses the full report of" and its date; Appendix A's Inputs and guidance tables hold no ISO date; the three "No secondary valuation" sentences; in node, the reader's line in the four cases above with ` · ` between its parts and no "snapshot", "review" or "thesis"; the patch's pins.

- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** The checks' rule sentences, the references' sources, the chart titles and Appendix B do not change (spec 7).
- [ ] **Step 4: The method document.** 16.6's sentences on the export's opening lines and on Appendix A's dates and its sentence for no secondary valuation. Pinned.
- [ ] **Step 5: Run the four commands, then commit.**

### Task 7: An override at a split in Appendix A (spec 8)

**Files:**
- Modify: `src/fairband/reports/render.py` (`_overrides`, the Overrides table), `src/fairband/web/static/report.js` (the override's record), `docs/method.md` (16.6)
- Test: `tests/reports/test_render.py`, a node test for the page's record, `tests/test_method_doc.py`

**Interfaces:**
- Produces: each entry of `appendixA.overrides` gains `inForce`, `{"old": …, "new": …}` from the review's bridge line of that override's id, and `rescaled`, the clause of the review's JUDGMENT entry's note that begins "entered as"; both `null` unless the review's JUDGMENT entry for the override's input carries that clause. The export's Overrides row then prints the pair in force in its Old and New cells and the words after the New figure in brackets; the page's record shows the pair in force with the words under it. A row with both `null` prints as today.

- [ ] **Step 1: Write the failing tests.** Build the review as the refresh does: an override of `earnings.ntm` made on a snapshot before a 2-for-1 split, reviewed on a snapshot after it (the fixtures of `tests/refresh/test_reviews_follow.py` for the split scaling show how). Assert on `appendix_a(...)`: the entry's `inForce` is the bridge line's old and new, `rescaled` reads "entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027" (the fixture's own figures and day), the stored `old` and `new` are unchanged beside them; an override the review applied as entered has both `null`; the Markdown row holds the pair in force and the words, and never the stored old figure beside the new one in force. In node: the page's record for such an entry reads the pair in force and the words.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement**, reading the stored review alone: no split is read again at render.
- [ ] **Step 4: The method document.** 16.6 says what Appendix A shows for an override scaled at a split; 14.6's sentence on the note may point to it. Pinned.
- [ ] **Step 5: Run the four commands, then commit.**

### Task 8: The cite's number and the print rules (spec 9)

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` and `bundle.css` (marked patches), `src/fairband/web/static/index.html` (the print block)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Produces: in a report's table a cited figure and its `[n]` do not part at a line break; in print a report's table is not clipped by its scroll box: it takes the paper's width at a smaller type size and its cells wrap.

- [ ] **Step 1: Write the failing tests**: the pins of the patch's marks and rules in `bundle.js` and `bundle.css`, and of the print block's rules for `.fb-report__scroll` and `.fb-report__table` in `index.html`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the four commands, then commit.**

### Task 9: The playbook for the new figures (spec 12)

**Files:**
- Modify: `playbook/fairband-research/reference/report-template.md`, `reference/citations.md`, `reference/tools.md`, `playbook/fairband-research/SKILL.md` where it lists what the charts show
- Test: `tests/test_playbook.py`

**Interfaces:**
- Consumes: the periods and labels of Tasks 1 and 2; the section 5 chart of Tasks 3 and 5.

- [ ] **Step 1: Write the failing pins** for these sentences' substance, then the sentences:
  - The template's passage on the charts says section 4's charts show, after the fiscal years, the twelve months to the newest stored period in grey and the analysts' estimate years as outlined bars, for the lines that have them, and that section 5 shows revenue, the operating margin and EPS by quarter beside the agent's table of the quarter against the expectations; the agent still writes that table.
  - `citations.md`'s row for `table:` names the periods `ttm`, a year and `E`, and a stored period under the table `quarters`, with what each cell is; it says an estimate cell of revenue or EPS is cited by its own `estimate:` ref, which the read gives.
  - `tools.md`'s entry for `financial_tables` names `columns` (period, kind, label) and `quarters`.
- [ ] **Step 2: Run the playbook tests and the four commands, then commit.**

### Task 10: The playbook's words (spec 10, B-138)

**Files:**
- Modify: `playbook/fairband-research/reference/register.md`, `reference/report-template.md`, `playbook/fairband-research/SKILL.md`, `tests/test_playbook.py`
- Read: section F of the map for each clause's file, line and present words.

- [ ] **Step 1: For each bullet of spec 10, change the pin first, see it fail, then change the sentence.** Keep each new sentence in the register's own style: short, plain, one idea. The three test corrections of the last bullet are code: the docstring of the step 12 test states what the test asserts; the loop that bans `TERMS` lets "valuation review" stand while still banning "review" alone; the bracket check exempts a bracket that holds exactly a term of `TERMS`, not any parenthetical.
- [ ] **Step 2: Read the template's example end to end** for the figures that must agree (the growth the price needs, the belief, the value before the changes and the price) and make them agree with each other and with the example's Appendix-style lines.
- [ ] **Step 3: Run the playbook tests and the four commands, then commit.**

### Task 11: The backlog, the acceptance, the live step and the readout (spec 14)

Nothing in steps 3 to 5 runs without the founder's word. The controller does this task.

- [ ] **Step 1: The whole-branch review** and its one fix wave.
- [ ] **Step 2: The acceptance on a copy.** Copy the live database with SQLite's backup; start the branch's server on another port against the copy; for each of the 32 reports fetch the page's reads and the Markdown export: every answer is 200, GOOG's section 4 shows a trailing and an estimate column and its section 5 eight quarters, and no export's first two lines hold "snapshot", "route" or an ISO date. Compare the copy's snapshots, reviews and overrides before and after: identical.
- [ ] **Step 3: The founder's word**, with the readout of step 2.
- [ ] **Step 4: The live step.** Merge to main and push; restart the server from main on 8470. No backup and no revalue are needed: nothing is stored.
- [ ] **Step 5: The backlog and the readout.** B-136, B-137, B-191, B-138 and B-135 move to Done with their commits; B-102, B-108, B-110 and B-119 lose the clauses closed; two rows are filed (the price-needs sentence that names the route; the stored periods' gross profit that no read carries). The readout goes into the spec's decision log. Remove the worktree and the workspace; tell the founder that every research session must restart its MCP process, since the playbook changed.

---

## Self-review notes

- Spec coverage: 6.1 to 6.3 and the refs of 6.5 are Task 1; 6.4 is Task 2; the export of 6.5 and section 9's first two bullets are Task 3; 6.6's patch is Task 4 and the page of 6.5 and 6.6 is Task 5; 7 is Task 6; 8 is Task 7; section 9's last two bullets are Task 8; 12's playbook lines are Task 9 and its method lines ride with Tasks 1, 2, 3, 6 and 7; 10 is Task 10; 11 and 14 are Task 11.
- The order: Task 1's columns before everything that reads them; Task 4's patch before Task 5's page; Tasks 6 to 8 need none of the first five; Task 9 after the features it describes; Task 10 last among the build, since it and Task 9 share files.
- Names used across tasks: `Column`, `Table.columns`, `TRAILING`, `estimate_period`, `quarters_table`, `QUARTERS`, `QUARTERS_TITLE`, `resting_words`, `inForce`, `rescaled`, `P.reportCharts.points`, `P.reportCharts.kindsLine`, `BarPoint.kind`, `BarPoint.label`, `HistoryBarsProps.by`.
