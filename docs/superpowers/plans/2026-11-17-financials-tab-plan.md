# The Financials Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Financials tab on the company page at `#company/<symbol>/financials`: the three statements by fiscal year and by quarter, the revenue by product and by region, and about forty ratios by fiscal year, in one wide table a sub-tab under a chart of up to four lines the reader picks, with the amounts in millions or billions.

**Architecture:** The refresh's per-company fetch gains four optional FMP calls, stored whole as vendor responses beside the page's ten. Pure readers shape the newest stored answers, the six statements the engine already fetches among them, into tables of columns and rows, and one read answers them with no vendor call and no refs. Two page scripts draw the tab with `React.createElement`: one the controls, the tables and the picks, one the chart in SVG with the tokens. The design system gains three series tokens and a section of `charts.md` for this chart.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, httpx; plain JavaScript with React from the design-system bundle, no build step; pytest, with node for the page's own scripts (`tests/web/page.mjs`, `tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-17-financials-tab-design.md`. Read it with your task: this plan argues from it, and where the two differ the spec wins. It stands on `docs/superpowers/specs/2026-11-16-company-page-design.md` ("the page's design"), which is built. The look is the mockup's: `docs/superpowers/specs/2026-11-17-financials-tab-mockup/template.html` (its CSS and its chart code); the spec's section 13 lists where the mockup is wrong.

**A map of the code as it stands:**

- `src/fairband/vendors/fmp.py`: `Fmp`, one method a route, each `return self._get(route, params)` with `to_fmp_symbol(symbol)`; `segments_product(symbol)` and `segments_geographic(symbol)` exist; `type StatementKind = Literal["income", "balance", "cashflow"]`.
- `src/fairband/refresh/fetch.py`: `PAGE_ENDPOINTS` (the page's ten, fetched last), `page_params(endpoint, symbol)`, `_calls` (its `page_sends` map), `_rows` (a page endpoint's payload is usable when it is a list), `STATEMENT_YEARS = 11`, `STATEMENT_QUARTERS = 8`. A statement is stored under endpoint `income-annual` with params `{"symbol", "period": "annual", "limit": "11"}`, and so on for the six.
- `src/fairband/refresh/passthrough.py`: the `segments` kind makes two `_Call`s, `segments-product` and `segments-geographic`, each with params `{"symbol": symbol}`; a `_Call` takes `usable=_is_list` (the news has it); an unusable payload is stored with the error `unusable payload: ...`, answered as fetched and never reused.
- `src/fairband/refresh/inputs_statements.py`: `cadence_of(ends: Sequence[date]) -> Cadence | None`, `"quarterly"`, `"half-yearly"` or `None`, on period ends oldest first.
- `src/fairband/vendors/page_fmp.py`: the page's pure readers; `number(value) -> float | None`. `src/fairband/vendors/_fmp_parse.py`: `objects`, `dated(payload)` (each object row with a parseable `date`, and that date), `whole`, `text`, `parse_date`.
- `src/fairband/web/company_api.py`: `add_company_page_routes`, the two reads; `_profile` (a 404 without one), `_stored(conn, endpoint, symbol) -> _Answer | None` (finds an answer under `page_params` for a page endpoint, else under `_ENGINE_PARAMS[endpoint]`), `_quote`, `_payload`, `_data_date`.
- `src/fairband/web/static/company.js`: `TABS`, `load()` (reads `/page/<tab>`), `tabs()`, and `P.companyPage`: `panel`, `percent(x, digits)`, `multiple(x)`, `decimal(x, dp)`, `count(n)`, `day(iso)` and `draw`, on which a tab's script hangs `draw.<tab>(answer, detail)`. `controls.js`: `COMPANY_TABS`.
- `src/fairband/web/static/company_chart.js`: the price chart, the model for a chart: pure functions of the data and the width on `P.companyChart` (`niceStep`, `geometry`, `keyed(at, key, n)`), and a `Chart` component that keeps the state with `React.useState` and measures its width.
- `src/fairband/web/static/index.html`: the page's CSS (classes `app-…`) and the scripts in load order, `company_estimates.js` last.
- The design system: the archive `docs/design-system/fairband-design-system_4.tar.gz` (root folder `fairband-design-system/`, with `docs/charts.md`, `tokens/tokens.json`, `tokens/tokens.css`, `tokens/build_tokens.py`), and the vendored copy `src/fairband/web/static/design-system/tokens/`, whose `tokens.json` and `tokens.css` equal the archive's today.
- Tests: `tests/support/page.py` (`node(helper, args, *scripts)`, `classed`, `elements`, `text`); `tests/support/page_payloads.py` and `page_answers.py` (the page's synthetic payloads and the answers the readers give on them); `tests/refresh/vendor_double.py` (`Router`, `_FMP_ENDPOINTS`, fixtures under `tests/fixtures/fmp/`, `<route>.json` for every symbol); `tests/refresh/test_fetch.py` (its own `PAGE_ENDPOINTS`, the news' reuse tests at its end); `tests/web/test_company_page_api.py` (`_store`, `_store_all`, the reads' tests); `tests/web/test_company_chart.py` (how a chart's functions are read in node).

## Global Constraints

- No file under `src/fairband/engine/` or `src/fairband/policy/` changes. The method stays `fairband-mechanical/1.5` and the policy v16. No migration: the schema stays at 009. No value, level, flag or settings hash moves.
- The read calls no vendor. The tab's first draw waits on no vendor.
- A figure is FMP's field, shaped and never recomputed: no total of the segments, no margin worked out, no sum of quarters. Scaling an amount to millions or billions is format.
- No figure and no block names a vendor, carries a chip, a cite or a ref.
- Never two scales on one plot. A series colour says which line it is; text never wears one; no red and green.
- A dash, `—`, stands for a figure the answer lacks, an amount or a share count of exactly 0, and a multiple of exactly 0. A figure below zero leads with `−` (U+2212).
- Every word a person reads is copied from this plan's Words table, which copies the spec's. A changed word is a spec change.
- No test uses the network. Fixtures and payloads are synthetic: never commit vendor data. Never print, log, store or commit a key.
- Work in a worktree, not in the main checkout: the live server on port 8470 serves the page files of the main checkout as they are on disk.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, then a blank line, then `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- Every dispatched subagent, reviewers included, runs on Opus 5.5 at xhigh (the founder's standing rule).

## Words

| Where | Words |
|---|---|
| Tabs | `Overview`, `Financials`, `Estimates`, `Research` |
| Sub-tabs | `Income statement`, `Balance sheet`, `Cash flow`, `Segments`, `Ratios` |
| Switches | `Millions`, `Billions`; `Annual`, `Quarterly`, and `Half-yearly` in `Quarterly`'s place for a half-year reporter |
| Caption, left | `the last 11 fiscal years`, `the last 8 quarters`, `the last 8 half-years` (the count is the table's own); `by fiscal year, as the company reports its segments`; `by fiscal year; the same definitions as Key statistics on the Overview` |
| Caption, right | `press a line to chart it alone, or its + to add it to the chart` |
| First column's head | `USD, millions, except per share` (income statement); `USD, millions` (balance sheet, cash flow, segments); `as each row says` (ratios); `billions` for `millions` under Billions; the tab's currency for `USD` |
| Tables' titles | `Revenue by product`, `Revenue by region` |
| A column's head | `2026` over `26 Sep`; `Q4 2026` or `H2 2026` over `26 Sep`; a third line, the code (`EUR`), where the column's currency is not the tab's |
| An empty table | `No figures on file.` |
| The lines | the spec's section 12, as written there |
| A line on the chart | its name in the table; `Gross margin` (Margins), `Revenue a share` (Per share), `Dividend yield`, `Dividend payout` (Dividends); `Revenue: iPhone` (a segment) |
| The chart's head, one line | the name, the newest figure, then `2026, USD, millions` |
| The chart's head, several | a label a line (swatch, name, newest figure, `×`), then `figures for 2026` |
| A plot's unit | `USD, millions`, `USD, billions`, `USD a share`, `millions of shares`, `billions of shares`, `percent`, `multiple`, `ratio`, `days` |
| By quarter | `by year only`; `no figures by quarter`; `These lines have figures by fiscal year only. Choose Annual, or press a line in the table.` |
| The hover box | one line: `2024 · 391,035`; several: the period, then a row a line; another currency's figure as `EUR 25,129` |
| Buttons' titles | `Add to the chart`, `Take off the chart`, `The chart holds 4 lines. Take one off first.` |
| Failures | 404 `no page data for <symbol>`; a tab whose read fails, as the other tabs |

## Review Focus

Five conditions the spec implies and a hurried build would miss. Each has its test in the task that owns the code.

1. **A vendor answer of the wrong shape.** FMP answers HTTP 200 with `{"Error Message": ...}` (a segments answer the pass-through stored before this build may be one), a row with no `date`, a `fiscalYear` that is a number, a text or missing, a number as text, `NaN`. The fetch stores an object as unusable; a reader gives `null` for the field or an empty table and never raises (Tasks 1, 2).
2. **A company with a profile and little else.** No statement, no ratios or no segments on file: the read answers 200 with empty tables; each empty table draws `No figures on file.`; the tab opens on the first line there is, and with no line at all it draws no chart and does not throw (Tasks 3, 4, 5).
3. **Figures in another currency than the tab's.** A column in EUR in a USD table; a segment answer whose every year but the newest names another currency. The head carries the code, the chart draws no mark there, a plot with no mark at all still draws its frame, and no scale is built from such a figure (Tasks 4, 5, 7).
4. **Lines whose periods differ, and thin series.** A segment answer that ends three years before the statements or misses years; one figure only; every figure equal; every figure `null` or 0. The periods are the union in order of their end; a single figure draws a dot; a flat series' scale is widened so nothing divides by zero (Tasks 5, 7).
5. **Storage that throws or holds junk.** No `localStorage` (the node harness, a private window) or a stored unit that is neither: Millions, and no throw on write (Task 4).

And one the reviewer reads the code for: the picks are dropped when another company's answer lands, and a line's colour slot never changes while it stays on the chart.

---

### Task 1: The Fmp client's two routes and the fetch's four page calls (spec 8.1, 8.2, 10; Review Focus 1)

**Files:**
- Modify: `src/fairband/vendors/fmp.py` (two methods; the module docstring's list of routes), `src/fairband/refresh/fetch.py` (`PAGE_ENDPOINTS`, `page_params`, `_calls`, the docstrings' counts), `src/fairband/refresh/passthrough.py` (the segments' `usable`, its docstring), `src/fairband/refresh/run.py` (the docstring's "25 FMP"), `docs/method.md` (section 10, the sentence that counts the page's answers), `tests/refresh/vendor_double.py` (`_FMP_ENDPOINTS`)
- Create: `tests/fixtures/fmp/ratios.json`, `key-metrics.json`, and `revenue-product-segmentation.json`, `revenue-geographic-segmentation.json` where the double has no fixture that serves every symbol (synthetic, two rows each, no company's real figures; a fixture the pass-through's tests read for one symbol stays as it is)
- Test: `tests/vendors/test_fmp.py`, `tests/refresh/test_fetch.py`, `tests/refresh/test_passthrough.py`, and every test that counts a company's calls (`tests/refresh/test_run.py`, `test_run_full.py`; grep the tests for `27`, `25` and `PAGE_ENDPOINTS`)

**Interfaces:**
- Produces, in `fmp.py`: `Fmp.ratios(self, symbol: str, limit: int) -> VendorResponse` (route `ratios`) and `Fmp.key_metrics(self, symbol: str, limit: int) -> VendorResponse` (route `key-metrics`), each with params `{"symbol": to_fmp_symbol(symbol), "period": "annual", "limit": str(limit)}`.
- Produces, in `fetch.py`: `PAGE_ENDPOINTS` ends `..., "news", "ratios-annual", "key-metrics-annual", "segments-product", "segments-geographic"`; `page_params("ratios-annual", s) == page_params("key-metrics-annual", s) == {"symbol": s, "period": "annual", "limit": str(STATEMENT_YEARS)}`; `page_params("segments-product", s) == page_params("segments-geographic", s) == {"symbol": s}`.

- [ ] **Step 1: Write the failing tests**

In `tests/vendors/test_fmp.py`, beside the page routes' test:

```python
def test_the_ratios_and_the_key_metrics_by_fiscal_year(...) -> None:
    # fmp.ratios("BRK.B", 11) requests the route "ratios", fmp.key_metrics("BRK.B", 11) "key-metrics",
    # each with exactly {"symbol": "BRK-B", "period": "annual", "limit": "11"} beside the key
```

In `tests/refresh/test_fetch.py`: the module's `PAGE_ENDPOINTS` gains the four at its end, and the tests that read it follow: `list(responses(conn))[-15:] == ["keyratios", *PAGE_ENDPOINTS]`; the stored params' `expected` gains the two ratio endpoints with `{"symbol": "ACME", "period": "annual", "limit": "11"}`; a whole fetch is `calls=31` where it was 27, and a second fetch after unusable page payloads `(14, 17, PAGE_ENDPOINTS)` where it was `(10, 17, ...)`. Add, after the news' two:

```python
def test_the_segments_are_stored_under_the_pass_through_s_key(env: Env) -> None:
    # the fetch stores both; passthrough.fetch("segments", "ACME", {}) then makes no call and
    # answers the fetch's two payloads; and the other way round: after the pass-through alone,
    # the fetch reuses both and calls neither route

def test_a_segments_error_body_the_pass_through_stored_is_not_reused(env: Env) -> None:
    # the router answers both routes {"Error Message": "x"}; the pass-through stores each with an
    # error that starts "unusable payload:"; the fetch then calls both routes again
```

In `tests/refresh/test_passthrough.py`: a `segments` part whose body is an object is stored with `unusable payload: ...` and is fetched again by the next request, as the news' test asserts for the news.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/vendors/test_fmp.py tests/refresh/test_fetch.py tests/refresh/test_passthrough.py -q`
Expected: FAIL (`Fmp` has no `ratios`; the endpoint lists differ).

- [ ] **Step 3: Write the two methods, the four calls and the segments' check**

`_calls`' `page_sends` gains `partial(fmp.ratios, symbol, STATEMENT_YEARS)`, `partial(fmp.key_metrics, symbol, STATEMENT_YEARS)`, `partial(fmp.segments_product, symbol)` and `partial(fmp.segments_geographic, symbol)`. The two segment `_Call`s of `passthrough.py` take `usable=_is_list`. Nothing else in `fetch_company`, `_store` or `_rows` changes: the four are page endpoints.

- [ ] **Step 4: Correct the counts in words**

`fetch.py`'s docstrings (twenty-nine FMP calls, the page's fourteen, the segments stored under the pass-through's endpoints and params so each reuses the other's copy); `run.py`'s "25 FMP"; `passthrough.py`'s paragraph on what is usable (the segments join the news); `fmp.py`'s list of routes (`ratios`, `key-metrics`: `symbol`, `period`, `limit`; checked live on 2026-11-17, eleven rows each for AAPL). In `docs/method.md` section 10 the sentence "fetches for each company ten FMP answers that only the company page shows" says fourteen and names both specs; no version moves. A test that pins that sentence follows it.

- [ ] **Step 5: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: PASS.
Commit: `Fetch the ratios and the key metrics by fiscal year and the two segment answers with the company page's calls, stored under the keys the segments pass-through reads, which now refuses an answer that is not a list`

---

### Task 2: The readers (spec 7.3, 7.5, 7.9, 8.3, 12; Review Focus 1, 4)

**Files:**
- Create: `src/fairband/vendors/page_financials.py`, `tests/vendors/test_page_financials.py`

**Interfaces:**
- Consumes: `page_fmp.number`, `_fmp_parse.dated`, `whole`, `text`; `fmp.StatementKind`.
- Produces, all pure, none raising on any JSON value:

```python
type Table = dict[str, Any]  # {"columns": [Column, ...], "rows": [Row, ...]}
# Column: {"label": "2026" | "Q4 2026" | "H2 2026", "end": "2026-09-26", "currency": "USD"}
# Row:    {"key", "label", "name", "kind", "unit", "values"}
#   kind: "total" | "line" | "sub" | "head"
#   unit: "money" | "perShare" | "shares" | "percent" | "multiple" | "ratio" | "days"
#   a head: {"key": None, "label": "ASSETS", "name": None, "kind": "head", "unit": None, "values": None}

def statement(payload: Any, kind: StatementKind, currency: str, *,
              quarterly: bool = False, half_yearly: bool = False) -> Table: ...
def ratios(ratios: Any, metrics: Any, currency: str, limit: int) -> Table: ...
def segments(payload: Any, currency: str, limit: int) -> Table: ...
def reported_currency(payload: Any) -> str | None: ...   # the newest dated row's reportedCurrency
def period_ends(payload: Any) -> list[date]: ...          # the dated rows' days, oldest first
```

The rules, each from the spec:

- **Columns.** The payload's dated rows in order of `date`, oldest first. `label`: the fiscal year as text (`fiscalYear` as a number or a text of digits, else the year of `date`); for `quarterly`, the row's `period` and the year (`Q4 2026`), and under `half_yearly` `Q2` reads `H1` and `Q4` `H2`, any other period as FMP names it. `end`: the `date` as an ISO day. `currency`: the row's `reportedCurrency` where it is a text, else `currency`.
- **Rows.** In section 12's order. A statement's `key` is FMP's field and its `name` its `label`. A ratio's `key` is FMP's field; its `name` is its label, but `<label> margin` in Margins, `<label> a share` in Per share and `Dividend <label in lower case>` in Dividends. A segment's `key` and `label` are FMP's name and its `name` is `Revenue: <name>`. A head's label is in upper case as section 12 writes it.
- **Values.** `page_fmp.number` of the field, one a column: an amount stays in units of the currency.
- **Left out.** A line whose every value is `None` or 0; then a head with no line before the next head or the end.
- **`ratios`.** The two answers joined by `date`: a column a date among either's rows, the newest `limit`, oldest first; a field whose answer has no row for the date is `None`. PEG stands after P/E; its unit is `ratio`.
- **`segments`.** The newest `limit` dated rows, oldest first; each row's `data` object is name to figure. A line a name with a figure that is not 0 in those rows. Order: by the newest column's figure, largest first, a line with none there after those, by its largest figure; a tie by name.
- **Wrong shape.** Anything but a list of objects reads as `{"columns": [], "rows": []}`; `reported_currency` gives `None`, `period_ends` `[]`.

The lists of section 12 are module constants, written once here: FMP's field, the label, the kind and the unit for a statement; the answer (`ratios` or `key-metrics`), FMP's field, the label and the unit for a ratio, with the heads between.

- [ ] **Step 1: Write the failing tests**

`tests/vendors/test_page_financials.py` holds section 12's labels as four tuples, written out in the spec's order (`INCOME_LABELS`, `BALANCE_LABELS`, `CASHFLOW_LABELS`, `RATIO_LABELS`, the heads among them in upper case), and builds its payloads in the file (a row with a figure in every field of a list). The tests:

```python
def test_every_line_of_a_statement_in_the_spec_s_order() -> None:
    # for income, balance and cashflow: [row["label"] for row in table["rows"]] == the tuple, and
    # revenue is "total"/"money", "· General and administrative" reads "sub" with label
    # "General and administrative", eps "line"/"perShare", weightedAverageShsOut "shares"

def test_the_columns_by_year_and_by_quarter() -> None:
    # three annual rows given newest first: labels ["2024", "2025", "2026"], ends oldest first;
    # quarterly rows Q3 2026, Q4 2026: labels ["Q3 2026", "Q4 2026"]; fiscalYear 2026 (a number),
    # "2026" (a text) and missing (the date's year) all label "2026"

def test_half_years_are_named_h1_and_h2() -> None:
    # quarterly=True, half_yearly=True: periods Q2 and Q4 of 2026 label "H1 2026", "H2 2026";
    # a row named Q3 keeps "Q3 2026"; with half_yearly=False the same rows read "Q2 2026", "Q4 2026"

def test_a_line_of_zeros_and_nulls_is_left_out_with_its_empty_head() -> None:
    # interestIncome 0 in every row and eps/epsDiluted/shares all None: no "Interest income" row,
    # no "PER SHARE" head; a line that is 0 in one row and 5 in another stays, its 0 a 0

def test_a_figure_that_is_not_a_number_is_null() -> None:
    # "12", True, NaN, an infinity and a missing field each give None in values

def test_a_column_carries_its_row_s_currency() -> None:
    # rows naming EUR, EUR, USD with currency="USD": ["EUR", "EUR", "USD"]; a row naming none: "USD"

def test_the_ratios_join_two_answers_by_date() -> None:
    # ratios rows dated 2025-09-27 and 2026-09-26, metrics rows 2026-09-26 only: two columns;
    # ROIC's values [None, 0.53]; gross margin's [0.469, 0.488]; with metrics=None the Returns
    # head and its lines are left out and the table still draws the ratios' lines

def test_a_ratio_s_name_on_the_chart() -> None:
    # names by key: grossProfitMargin "Gross margin", revenuePerShare "Revenue a share",
    # dividendYield "Dividend yield", dividendPayoutRatio "Dividend payout",
    # returnOnInvestedCapital "ROIC"; units: priceToEarningsRatio "multiple",
    # priceToEarningsGrowthRatio "ratio", daysOfSalesOutstanding "days"; PEG follows P/E

def test_the_ratios_keep_the_newest_limit_dates() -> None:
    # thirteen dates across the two answers, limit 11: eleven columns, the two oldest gone

def test_the_segments_newest_years_and_their_order() -> None:
    # seventeen rows, limit 11: eleven columns; data {"A": 5, "B": 9, "Old": 0} newest and
    # {"A": 7, "Old": 3} before: rows B, A, Old; "Old" kept (a figure in a shown year); a name
    # that is 0 or missing in every shown year left out; name "Revenue: B"; fiscalYear given as
    # the number 2026 labels "2026"

def test_a_payload_of_the_wrong_shape_is_an_empty_table() -> None:
    # for {"Error Message": "x"}, None, "text", 7, [1, 2], [{"no": "date"}]: statement, ratios and
    # segments each give {"columns": [], "rows": []}; reported_currency None; period_ends []

def test_the_newest_row_names_the_currency_and_the_ends_are_in_order() -> None:
    # rows given newest first naming USD then EUR: reported_currency "USD";
    # period_ends oldest first
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/vendors/test_page_financials.py -q`
Expected: FAIL with `ModuleNotFoundError: fairband.vendors.page_financials`.

- [ ] **Step 3: Write `page_financials.py`**

One function builds a table's rows from a spec and the ordered rows, and drops what is left out; the three readers differ in their columns and their spec. The module's docstring states the rules above and names the spec's sections.

- [ ] **Step 4: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: PASS.
Commit: `Read a company's statements, ratios by fiscal year and segments from FMP's stored answers into tables of periods and lines, each line with its name, its kind and its unit`

---

### Task 3: The read (spec 7.4, 7.9, 8.3; Review Focus 2)

**Files:**
- Modify: `src/fairband/web/company_api.py` (the route, `_ENGINE_PARAMS`, the module docstring), `tests/support/page_payloads.py` (synthetic statements, ratios and segments for its company), `tests/support/page_answers.py` (`FINANCIALS`, `profile_only_financials()`)
- Test: `tests/web/test_company_page_api.py`

**Interfaces:**
- Consumes: Task 1's `PAGE_ENDPOINTS` and `page_params`; Task 2's five functions; `cadence_of`; `STATEMENT_YEARS`, `STATEMENT_QUARTERS`.
- Produces: `GET /api/companies/{symbol}/page/financials`, a plain GET:

```
{"symbol", "dataDate", "quote", "currency", "cadence",
 "statements": {"income": {"annual": T, "quarter": T}, "balance": {...}, "cashflow": {...}},
 "segments": {"product": T, "region": T},
 "ratios": T}
```

- `currency`: `page_financials.reported_currency` of the stored `income-annual`, else `reporting_currency(conn, symbol)`. Every reader is handed it.
- `cadence`: `"half-yearly"` where `cadence_of(page_financials.period_ends(<income-quarter>))` says so, else `"quarterly"`. The three quarterly tables are read with `quarterly=True, half_yearly=<that>`.
- `ratios` and both segment tables are read with `limit=STATEMENT_YEARS`.
- `dataDate`: `_data_date` of the ten answers the read draws (the six statements, `ratios-annual`, `key-metrics-annual`, `segments-product`, `segments-geographic`). `quote`: `page_fmp.head_quote`, as the other two reads.
- `_ENGINE_PARAMS` gains the six statements, each `{"period": <period>, "limit": str(<its depth>)}`, as `fetch._calls` stores them.
- A symbol that is not one is a 400; a company with no stored profile a 404, `no page data for <symbol>`.

- [ ] **Step 1: Write the failing tests**

`page_payloads.py` gains, for its company: three annual and three quarterly rows of each statement, two rows of `ratios` and of `key-metrics`, three rows of each segment answer, all invented, in the company's reporting currency (`TWD`, as `page_answers.REPORTING`). `page_answers.FINANCIALS` is the readers' output on them, as `OVERVIEW` is. In `tests/web/test_company_page_api.py`, with its `_store` and `_store_all` storing the ten under the fetch's params:

```python
def test_the_financials_whole(client, db_path, policy) -> None:
    # _get(client, FINANCIALS_PATH) == answers.FINANCIALS; its currency "TWD", cadence "quarterly",
    # eight tables present

def test_the_financials_of_a_company_with_a_profile_and_nothing_else(client, db_path) -> None:
    # 200; every table {"columns": [], "rows": []}; dataDate None; currency the company's, "USD"
    # with no snapshot; cadence "quarterly"

def test_the_financials_refuse_a_bad_symbol_and_a_company_with_no_profile(client) -> None:
    # 400 for "a b"; 404 with detail "no page data for NOPE"

def test_the_financials_data_date_is_the_oldest_of_its_ten_answers(client, db_path) -> None:
    # one statement stored a day before the rest: that day; the quote's and the profile's days
    # do not count

def test_a_half_year_reporter_s_cadence_and_labels(client, db_path) -> None:
    # quarterly income rows ending 2025-12-31 and 2026-06-30 named Q4 and Q2: cadence
    # "half-yearly", and the quarterly income, balance and cash flow columns read "H2 2025", "H1 2026"

def test_the_currency_is_the_newest_annual_income_row_s(client, db_path) -> None:
    # annual income rows naming EUR then USD (newest): currency "USD", the older column "EUR"

def test_the_financials_call_no_vendor(...) -> None:
    # as test_the_reads_call_no_vendor: a transport that fails any call, and the read answers
```

`test_the_reads_find_what_the_fetch_stores` gains the financials read: after a fetch through the vendor double, no table of statements, ratios or segments is empty.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/web/test_company_page_api.py -q`
Expected: FAIL with 404 on `/page/financials`.

- [ ] **Step 3: Write the route**

Beside `page_estimates`, in the same `closing(conn_factory())` form. The module docstring gains the read, its ten answers and its rules.

- [ ] **Step 4: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: PASS.
Commit: `Answer a company's statements, segments and ratios by fiscal year from the store at page/financials, with the tab's currency, the company's reporting cadence and the oldest day among the ten answers it draws`

---

### Task 4: The tab: its address, its controls and its tables (spec 7.1, 7.2, 7.3, 7.7, 7.8, 7.9; Review Focus 2, 3, 5)

**Files:**
- Create: `src/fairband/web/static/company_financials.js`, `tests/web/test_company_financials.py`
- Modify: `src/fairband/web/static/controls.js` (`COMPANY_TABS`, its comment), `src/fairband/web/static/company.js` (`TABS`, the head comment), `src/fairband/web/static/index.html` (the script after `company_estimates.js`; the CSS), `tests/web/company_load.mjs` (loads the new script)
- Test: `tests/web/test_company_financials.py`, and the pins of the tabs and the script list (`tests/web/test_app.py`, `tests/web/test_company_page.py`, `tests/web/test_company_load.py`)

**Interfaces:**
- Consumes: Task 3's answer; `P.companyPage` (`C`): `percent`, `multiple`, `decimal`, `count`, `day`, `draw`.
- Produces: the tab in the row, second: `TABS = [['overview', 'Overview'], ['financials', 'Financials'], ['estimates', 'Estimates']]`; `COMPANY_TABS = ['overview', 'financials', 'estimates']`; `C.draw.financials(answer, detail)`.
- Produces, on `P.companyFinancials`, pure but for the two that touch storage:

```js
SUBTABS    // [['income','Income statement'],['balance','Balance sheet'],['cashflow','Cash flow'],['segments','Segments'],['ratios','Ratios']]
yearly(kind)                       // true for 'segments' and 'ratios'
step(view, change)                 // view {kind, period, scale} with `change` laid over it; a yearly kind sets period 'annual'
tables(answer, kind, period)       // [{id, title, table}]: id null, or 'product' / 'region' with their titles
digits(table)                      // 1 where the table's largest money figure is under 1e9 in size, else 0
figure(row, value, scale, digits)  // a cell's text
caption(kind, currency, scale)     // the first column's head
note(kind, period, cadence, count) // the left caption
head(column, currency)             // [label, '26 Sep', code or null]
storedScale()                      // 'm' or 'b' from localStorage 'fairband.financials.unit'; 'm' on anything else or a throw
keepScale(scale)                   // writes it; never throws
Financials                         // the component: props {answer, symbol}
```

- `figure`: `money` and `shares`: a dash for `null` and for 0; under `'m'`, `C.decimal(value / 1e6, digits)`; under `'b'`, `C.decimal(value / 1e9, 2)`. `perShare`: `C.decimal(value, 2)`. `percent`: `C.percent(value, 1)`, two decimals for the row whose key is `dividendYield`. `multiple`: `C.multiple(value)`. `ratio`: `C.decimal(value, 2)`. `days`: `C.count(value)`.
- The view (`kind`, `period`) is kept in the module while the app is open; the scale in storage. `Financials` holds the view in `React.useState`, starts from what is kept, and is drawn with `key: symbol` (the page's company, `P.company.symbol`) so another company's tab is a new component.
- `draw.financials` returns one `C.panel` of the page's full width holding, in order: the controls' row, the chart's place (empty until Task 5), the two captions, the tables.
- The classes the tests and the later tasks read: `app-fin` (the block), `app-fin__tab` (a sub-tab, `aria-selected`), `app-fin__scale` and `app-fin__period` (a switch's button, `aria-pressed`), `app-fin__note` (the two captions), `app-fin__title` (a table's title), `app-fin__table`, a row's `is-total`, `is-sub`, `is-head`, a cell's `is-nil` (a dash), `app-fin__code` (a column's currency code), `app-fin__none` (the empty sentence).

- [ ] **Step 1: Write the failing tests**

`tests/web/test_company_financials.py` runs `company.js` and `company_financials.js` in node (`SCRIPTS`, as `test_company_chart.py`), on a small synthetic answer built in the file (two annual columns, two quarterly, a product table, a ratios table):

```python
def test_the_tab_stands_second_and_its_hash_reads_both_ways() -> None:
    # the tabs' row reads Overview, Financials, Estimates, then the Research link; controls.js
    # holds 'financials' among COMPANY_TABS (source pin); the loader reads /page/financials for
    # #company/ACME/financials (tests/web/test_company_load.py)

def test_the_controls_by_sub_tab() -> None:
    # step({kind:'income',period:'quarter',scale:'m'}, {kind:'ratios'}) -> period 'annual';
    # the drawn tab on 'income' holds five app-fin__tab, two app-fin__scale, two app-fin__period;
    # on 'segments' no app-fin__period; on 'ratios' neither app-fin__period nor app-fin__scale;
    # cadence 'half-yearly' writes 'Half-yearly' on the second period button

def test_the_tables_of_each_sub_tab() -> None:
    # tables(answer,'income','annual') one table with no title; 'segments' two, titled
    # 'Revenue by product' and 'Revenue by region'; 'ratios' one

def test_a_table_s_rows_and_kinds() -> None:
    # a total row carries is-total, a sub-line is-sub, a head is-head with one cell spanning
    # every column and no figure; the columns stand oldest first

def test_the_captions() -> None:
    # caption: ('income','USD','m') 'USD, millions, except per share'; ('balance','TWD','b')
    # 'TWD, billions'; ('segments','USD','m') 'USD, millions'; ('ratios',...) 'as each row says'
    # note: ('income','annual','quarterly',11) 'the last 11 fiscal years'; ('cashflow','quarter',
    # 'quarterly',8) 'the last 8 quarters'; (...,'half-yearly',6) 'the last 6 half-years';
    # segments and ratios their sentences; the right caption's words

def test_a_column_s_head() -> None:
    # head({label:'2026',end:'2026-09-26',currency:'USD'},'USD') -> ['2026','26 Sep',None];
    # currency 'EUR' in a 'USD' tab -> ['2019','31 Dec','EUR'], drawn as an app-fin__code

def test_a_figure_s_text() -> None:
    # money 478834e6: 'm',0 -> '478,834'; 'b' -> '478.83'; -86390e6 'm' -> '−86,390';
    # digits(table whose largest money figure is 640e6) == 1 and 12.34e6 -> '12.3'; a table
    # with 5e9 -> 0; money 0 and null -> '—'; shares 15.2e9 'm' -> '15,200', 'b' -> '15.20';
    # perShare 7.906 -> '7.91'; percent 0.33 -> '33.0%'; the dividendYield row 0.0042 -> '0.42%';
    # multiple 37.94 -> '37.9x', multiple 0 -> '—'; ratio 1.034 -> '1.03'; days 61.4 -> '61';
    # a money figure of -3 under 'b' draws '0.00', with no sign

def test_an_empty_table_says_so() -> None:
    # a table with no row draws 'No figures on file.' in an app-fin__none and no <table>

def test_the_unit_is_millions_where_storage_fails() -> None:
    # the harness has no localStorage: storedScale() == 'm' and keepScale('b') returns without
    # throwing; with a stub store holding 'b' it is 'b', holding 'x' it is 'm' (a small .mjs
    # driver beside header.mjs if the harness cannot stub the store)
```

And source pins of the layout node cannot run: `.app-fin__scroll` holds `overflow-x: auto`; the first column's cells hold `position: sticky` and `left: 0`; an `@media (width < 700px)` rule narrows the first column to `168px`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/web/test_company_financials.py -q`
Expected: FAIL (`companyFinancials` is undefined).

- [ ] **Step 3: Write the tab**

The CSS is the mockup's (`.seg`, `.fin__*`, the table's rules) under the `app-fin` names and the app's tokens; the mockup's `+` button, its chart and its series colours wait for Tasks 5 and 7. The script's head comment says what the tab is, where its state lives and what the tests read.

- [ ] **Step 4: Look at it**

Start a scratch server on a spare port against a scratch database with a company's ten answers stored (memory note "view the page in a headless browser"), open `#company/<symbol>/financials` at 1600, 1250 and 400 pixels in both themes: the five sub-tabs, the two switches, each table, the sticky first column, no sideways scroll of the page.

- [ ] **Step 5: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: PASS.
Commit: `Add the company page's Financials tab, its five sub-tabs with one table of periods each, the amounts in millions or billions as the browser last kept, and the period by year, by quarter or by half-year`

---

### Task 5: The chart of one line (spec 7.4, 7.5, 7.7, 7.9; Review Focus 2, 3, 4)

**Files:**
- Create: `src/fairband/web/static/company_financials_chart.js`, `tests/web/test_company_financials_chart.py`
- Modify: `src/fairband/web/static/company_financials.js` (the picks, a row's press, the chart's place), `src/fairband/web/static/index.html` (the script after `company_financials.js`; the chart's CSS), `tests/web/company_load.mjs`, the script list's pin

**Interfaces:**
- Consumes: Task 4's `tables`, `figure`, `digits`, `yearly`; `P.companyChart.niceStep` and `keyed`.
- Produces, on `P.companyFinancials`: a pick is `{kind, table, key, slot}` (`table` is `null`, `'product'` or `'region'`); `first(answer)` (the pick the tab opens on: the income statement's `revenue`, else the first line of its annual table, else of the first table that has one, else `null`); `alone(line)` (`[{...line, slot: 0}]`). A press on a row (a click, Enter or Space on the focused row) sets the picks to `alone` of its line. A row on the chart carries `is-on` and `aria-selected="true"`.
- Produces, on `P.companyFinancialsChart`, pure functions of the answer, the picks, the period, the scale and the width:

```js
series(answer, picks, period)   // one a pick: {pick, slot, name, unit, form, off, columns, at}
                                //   form 'bars' for money, perShare, shares; 'line' for the rest
                                //   off null | 'by year only' | 'no figures by quarter'
                                //   at: label -> {value, currency}
periods(drawn)                  // the union of the drawn series' columns by label, in order of `end`
unitWords(unit, currency, scale)
geometry(drawn, width, currency)  // the plots with their scales, ticks and marks, and the periods' labels
box(g, i, scale)                // what the hover shows for period i
view                            // the component: props {answer, picks, period, scale, onDrop}
```

- A figure draws a mark only where it is a number, is not an amount of exactly 0, and, for `money` and `perShare`, its column's currency is the tab's.
- One plot here (one line): 160px of plot, 18px above, 22px below. Bars: one a period, at most 44px wide and at most 72% of the period's width, 4px rounded at the data end, `chart-1`, a figure below zero `chart-neg-3`. A line: 2px in `chart-1`, an end marker of 10px ringed in `surface-raised`, a lone figure between gaps a dot. A bar plot's scale holds zero; a line plot's fits its figures and is widened by a step where they are all equal. Four steps; the ticks at the right, bare and compact.
- The head: the line's name, its newest figure in `figure-lg` (`figure` at the table's `digits`), the caption `<newest period>, <unitWords>`.
- The hover and the keys, as `company_chart.js` does them: the pointer's period, the arrows, Home, End and Escape through `keyed`, a loss of focus; one line's box reads `<period> · <figure>`, with the code before a figure in another currency; the other bars fade.
- The periods' labels stand under the plot; where two would touch, every second or every third is left out, counted from the newest back.
- With no pick (a company with no line at all) the chart's place is empty. So it is where the one pick is `off` (a ratio under Quarterly); Task 7 writes the sentence there.

- [ ] **Step 1: Write the failing tests**

`tests/web/test_company_financials_chart.py`, on series made in the file (eleven years of revenue from 215,639e6 to 478,834e6; a margin from 0.245 to 0.33; a line with a figure below zero; one with gaps):

```python
def test_the_tab_opens_on_revenue_and_falls_back() -> None:
    # first(answer) == {kind:'income', table:None, key:'revenue', slot:0}; with no revenue row the
    # first line of the annual income table; with no statement the first segment or ratio line;
    # with no line anywhere None, and the tab draws without a chart

def test_a_press_on_a_row_charts_it_alone() -> None:
    # the row's onClick sets the picks to [that line at slot 0]; its row carries is-on

def test_an_amount_is_bars_and_a_rate_is_a_line() -> None:
    # series form by unit: money, perShare, shares 'bars'; percent, multiple, ratio, days 'line'

def test_the_bar_plot_s_scale_holds_zero_and_its_ticks_are_compact() -> None:
    # revenue: eleven bars, the scale from 0, the ticks' texts ['0B','200B','400B','600B'] from
    # the baseline up; no bar wider than 44

def test_the_line_plot_s_scale_fits_its_figures() -> None:
    # the margin: ticks ['20%','25%','30%','35%'], no zero line, one path of eleven points and
    # an end marker at the last

def test_a_figure_below_zero_hangs_from_the_baseline_in_the_negative_colour() -> None:

def test_no_mark_for_a_gap_a_zero_amount_or_another_currency() -> None:
    # values [5e9, None, 0, 7e9] draw two bars; a column in 'EUR' in a 'USD' tab draws none and
    # the scale is built without it; a line breaks at a gap and a lone figure draws a dot

def test_a_flat_or_single_series_divides_by_nothing() -> None:
    # every figure 0.2: finite geometry; one figure only: one bar, or one dot

def test_the_head_of_one_line() -> None:
    # 'Revenue', '478,834', '2026, USD, millions'; under 'b' '478.83' and '2026, USD, billions'

def test_the_hover_box_and_the_keys() -> None:
    # box(g, 8, 'm') text '2024 · 391,035'; a figure in another currency 'EUR 25,129'; no box
    # for a period with no figure; ArrowLeft from none picks the newest

def test_the_periods_labels_thin_on_a_narrow_plot() -> None:
    # eleven years at a width of 1,200: eleven labels; at 300: fewer, the newest among them, and
    # no two closer than a label's width

def test_a_pick_that_is_off_draws_no_plot() -> None:
    # a ratio picked and period 'quarter': series' off is 'by year only', and the view draws no svg
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/web/test_company_financials_chart.py -q`
Expected: FAIL (`companyFinancialsChart` is undefined).

- [ ] **Step 3: Write the chart of one line**

Port the mockup's `chart()` and `showAt()` to pure functions and React elements, as `company_chart.js` is built: `geometry` computes, the component draws and keeps the period picked and the measured width. Write `periods`, `series` and `geometry` for a list of series from the start (Task 7 hands them several).

- [ ] **Step 4: Look at it**

As Task 4's step 4: press Revenue, Gross profit, a cash flow line below zero, a ratio; hover and use the arrow keys; both themes; 400 pixels.

- [ ] **Step 5: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: PASS.
Commit: `Draw the line the reader presses on the Financials tab's chart, an amount as bars from zero and a rate as a line on an axis that fits it, with the newest figure in its head and a period's figure under the pointer or the arrow keys`

---

### Task 6: The three series tokens and the chart rules (spec 7.6, 10)

**Files:**
- Modify: `docs/design-system/fairband-design-system_4.tar.gz` (inside it `fairband-design-system/tokens/tokens.json`, `tokens/tokens.css`, `docs/charts.md`), `src/fairband/web/static/design-system/tokens/tokens.json`, `tokens.css`
- Test: `tests/web/test_design_tokens.py` (new)

**Interfaces:**
- Produces: the CSS variables `--chart-2`, `--chart-3`, `--chart-4`, in the dark root, the light theme and the light preference:

| Token | Dark | Light |
|---|---|---|
| `chart-2` | `#437dde` | `#1b3d9c` |
| `chart-3` | `#f3c530` | `#b5820c` |
| `chart-4` | `#c05296` | `#c562b2` |

- [ ] **Step 1: Write the failing test**

```python
def test_the_three_series_tokens_stand_in_both_themes() -> None:
    # in the vendored tokens.css each of --chart-2, --chart-3, --chart-4 appears three times,
    # with its dark value once and its light value twice

def test_the_vendored_tokens_are_the_archive_s() -> None:
    # tokens.json and tokens.css under static/design-system/tokens equal, byte for byte, the
    # archive's fairband-design-system/tokens/ files (tarfile, read without unpacking)

def test_the_chart_rules_name_the_chart_with_several_series() -> None:
    # the archive's docs/charts.md holds the heading '## Several series the reader picks' and
    # each of 'chart-2', 'chart-3', 'chart-4', and still holds 'Never two y-scales on one plot'
```

- [ ] **Step 2: Run it and see it fail**

Run: `uv run pytest tests/web/test_design_tokens.py -q`
Expected: FAIL (no `--chart-2`).

- [ ] **Step 3: Change the archive and the vendored copy**

Unpack the archive into a folder outside the repository. In `tokens/tokens.json`, after `chart-1`, add the three with the values above and these usages; `chart-1`'s usage gains the last sentence:

- `chart-1`, added: "One chart has no subject, the Financials tab's, whose lines the reader picks: there `chart-1` to `chart-4` name the lines."
- `chart-2`: "The second series hue, blue, on a chart whose lines the reader picks. Never on a chart with a subject."
- `chart-3`: "The third series hue, yellow, on a chart whose lines the reader picks. A mark in a plot, never a status: `caution` is the status."
- `chart-4`: "The fourth and last series hue, magenta, on a chart whose lines the reader picks."

Run the folder's `python3 tokens/build_tokens.py`. In `docs/charts.md`, end the paragraph of "Emphasis, not categorical colour" that says there is no chart where four series are equally the point with: "One chart is the exception; see *Several series the reader picks*." After that section add:

```markdown
## Several series the reader picks

One chart in Fairband has no subject: the Financials tab's, where the reader picks up to four
lines and none is the point more than another. That chart, and only a chart like it, takes
`chart-1` to `chart-4`. Every other chart keeps one hue and `chart-context`.

- A line takes the lowest of the four that is free when it is picked and keeps it until it
  leaves the chart. Taking one line off never repaints the others. One line alone wears
  `chart-1`.
- Never a fifth colour: the chart holds four lines.
- Lines of one unit share a plot and a scale. Another unit takes a plot of its own under it, on
  the same periods. Never two scales on one plot.
- An amount is a column from zero; a rate is a line on an axis that fits its range.
- With one line, a figure below zero takes `chart-neg-3`, the polarity pair. With several, a
  column wears its line's colour above zero and below: colour is identity there.
- The legend is the row of labels above the plot, each a swatch, a name and the newest figure.
  Text never wears a series colour.
- This chart spans the page, so a column is at most 44px wide alone and 28px among several.
  `chart-bar-max` stays `HistoryBars`'s.
- The four were measured as a set: every pair is 10.6 or more apart under simulated protan and
  deutan sight and 21 or more under full sight (OKLab ΔE × 100), and each is 3:1 or more on
  `surface-raised`, in both themes. None is a `phase-*`, `caution` or `critical` value.
```

Pack the folder again under the same name (`tar -czf <repo>/docs/design-system/fairband-design-system_4.tar.gz -C <folder> fairband-design-system`) and copy its `tokens.json` and `tokens.css` over the vendored two. Check that the archive lists the same files as before (`tar -tzf`, before and after) and that `tests/test_playbook.py` still reads the brand book.

- [ ] **Step 4: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: PASS.
Commit: `Give the design system three more series colours for a chart whose lines the reader picks, and state in its chart rules where they are used and how`

---

### Task 7: Several lines on one chart (spec 7.3, 7.4, 7.5, 7.6, 7.9; Review Focus 3, 4)

**Files:**
- Modify: `src/fairband/web/static/company_financials.js` (a row's button, the picks' rules), `src/fairband/web/static/company_financials_chart.js` (the plots by unit, the labels, the box of several), `src/fairband/web/static/index.html` (the CSS: the button, the labels, the four colours)
- Test: `tests/web/test_company_financials.py`, `tests/web/test_company_financials_chart.py`

**Interfaces:**
- Consumes: Task 5's picks, `series`, `periods`, `geometry`, `box`, `view`; Task 6's `--chart-2` to `--chart-4`.
- Produces, on `P.companyFinancials`: `MAX = 4`; `toggle(picks, line)` (adds the line at the lowest free slot of 0 to 3, or takes it off; leaves `picks` as they are when the line is the only one, or when it is a fifth); `drop(picks, pick)` (takes one off; the one left takes slot 0); the row's button, class `app-fin__add`, `aria-pressed`, with the Words' titles, `disabled` on a line that is off the chart while it holds four.
- A slot `n` draws in `--chart-<n + 1>`. A row on the chart carries a 2px bar of its colour at its left edge; its button shows its swatch.
- `geometry`: one plot a unit, in the order the units were first picked; a plot's height 160px alone, 120px each of two, 100px of three, 90px of four; with two or more lines each plot states its unit at its top left, and a plot under 150px has three steps. Two to four bars of a period stand side by side in pick order, each at most 28px, 2px apart, in its line's colour above zero and below.
- The head with two or more picks: a label a pick, drawn or not (class `app-fin__label`, `is-off` when it does not draw), each a swatch (a square for bars, a round dot for a line), the name, the newest period's figure or the `off` words, and a `×` (`aria-label` and title `Take off the chart`) that calls `onDrop`; then the caption `figures for <newest period>`.
- The box of several: the period, then a row a drawn line; a crosshair through every plot where a line plot is drawn; each line's point a marker.
- Where no pick draws: no plot, and the Words' sentence.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_company_financials.py
def test_the_plus_adds_a_line_and_takes_it_off() -> None:
    # toggle([revenue@0], netIncome) -> [revenue@0, netIncome@1]; toggle of that with revenue ->
    # [netIncome@0]: the one line left takes slot 0

def test_the_last_line_stays_and_a_fifth_is_refused() -> None:
    # toggle([revenue@0], revenue) -> unchanged; four picks and a fifth line -> unchanged, and
    # every app-fin__add of a row off the chart is disabled with the Words' title

def test_a_line_keeps_its_colour_while_another_leaves() -> None:
    # picks at slots 0, 1, 2; drop the one at 1 -> the others still 0 and 2; the next added takes 1

def test_the_picks_stay_across_sub_tabs_and_go_with_the_company() -> None:
    # step to 'ratios' keeps the picks; the component is keyed on the symbol (the tree's key)

def test_a_row_on_the_chart_shows_its_colour() -> None:
    # its button aria-pressed true with a swatch of its slot; a row off the chart reads '+'

# tests/web/test_company_financials_chart.py
def test_one_plot_a_unit_in_pick_order() -> None:
    # revenue, net income, operating margin: two plots, ['money','percent'], 120 high each, the
    # first with 22 bars, the second with one path; units stated 'USD, millions' and 'percent'

def test_the_plots_heights_and_steps() -> None:
    # one plot 160 with four steps; three plots 100 each with three steps; four plots 90 each

def test_bars_of_one_period_stand_side_by_side_in_their_colours() -> None:
    # two money lines: at a period the first line's bar is left of the second's, 2 apart, each
    # no wider than 28, classes of slots 0 and 1; a figure below zero keeps its slot's colour

def test_the_periods_are_the_union_whatever_the_order() -> None:
    # a statement line over 2016..2026 with a segment line over 2017, 2023..2025: eleven periods
    # either way round; the segment draws four marks; its label shows a dash for 2026

def test_the_labels_of_several_lines() -> None:
    # three labels with names, newest figures and a × each; the caption 'figures for 2026';
    # a ratio's swatch round, a statement line's square

def test_by_quarter_a_ratio_is_off_and_draws_nothing() -> None:
    # period 'quarter': the ratio's label is-off reading 'by year only', one plot; a statement
    # line whose key the quarterly table lacks reads 'no figures by quarter'; with only ratios
    # picked no plot and the sentence

def test_the_box_of_several_lines() -> None:
    # box(g, 8, 'm'): label '2024', rows [('Revenue','391,035'), ('Net income','93,736'),
    # ('Operating margin','31.5%')]; a figure in another currency reads 'EUR 25,129'

def test_a_plot_whose_every_figure_is_in_another_currency() -> None:
    # it draws its frame and its unit, no mark, and a finite scale
```

And source pins: the page's CSS names `var(--chart-1)` to `var(--chart-4)` for the four slots and no hex colour of its own for a series.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest tests/web/test_company_financials.py tests/web/test_company_financials_chart.py -q`
Expected: FAIL (`toggle` is undefined; `geometry` gives one plot).

- [ ] **Step 3: Write the picks' rules, the button, the plots and the labels**

The mockup's `press`, `drop`, `freeSlot`, its panels and its labels are the model. The mockup's add on a click with Ctrl or Cmd held is not built (spec 13).

- [ ] **Step 4: Look at it**

As Task 4's step 4, the mockup's cases: revenue, net income and operating margin; three margins; four mixed lines over two units; four segments; Quarterly with a ratio picked; the labels' `×` down to one line; 400 pixels with four bars a period; both themes. Then a company that changed currency and one whose segments end early, where the scratch database holds one.

- [ ] **Step 5: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: PASS.
Commit: `Let the reader add up to four lines to the Financials tab's chart, the lines of one unit on one plot and each other unit on a plot of its own under it, each line in a colour it keeps, with a label that names it and takes it off`

---

### Task 8: The documents, the whole-branch review and the live steps (spec 10, 14)

**Files:**
- Modify: `docs/backlog.md`, `docs/superpowers/specs/2026-11-17-financials-tab-design.md` (its decision log), `docs/superpowers/specs/2026-11-16-company-page-design.md` (one line in its decision log), the module docstrings and head comments not yet true

- [ ] **Step 1: The documents**

- `docs/backlog.md`: B-216 moves to Done with what was built. B-221 gains: the artifact lacks `chart-2`, `chart-3`, `chart-4` and the section "Several series the reader picks" of `charts.md`. New rows for what the spec's section 3 leaves out and the founder may want next: the ratios and the segments by quarter (two more calls a company each), a trailing-twelve-months column, year-on-year rows; and the deferred minors of this plan's reviews.
- The page's design, decision log: the Financials tab is built, with this design's path.
- Grep the documents, the playbook and the docstrings for the fetch's count of calls, the page's "ten" answers and the list of the page's tabs and reads, and correct what the build made untrue.

- [ ] **Step 2: The whole-branch review**

One review of the branch against the spec on the most capable model, then one fix wave (`superpowers:subagent-driven-development`, its final review). Before it, look at the tab in a real browser at six widths from 400 to 2,400 pixels, in both themes, on at least five companies of a scratch database: a layout fault is found there, not by the tests.

- [ ] **Step 3: Stop for the founder**

The merge, the push and the live steps wait for the founder's word (`superpowers:finishing-a-development-branch`). The live steps, in order: back the database up; merge; start the server from main (Python changed); run a full refresh; open the pages of the spec's section 14. The readout goes into the spec's decision log: the full refresh's minutes against 18.5, the count of failed calls among the four by endpoint, the database's growth, how many companies have no segments, and what the foreign filers, the company that changed currency and the half-year reporter showed.
