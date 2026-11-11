# Filings access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the research agent FMP's filing report (the 10-Q or 10-K as JSON) and filing list through Fairband, the stored quarters with `fact:` refs, and a playbook that reads Fairband before it goes outside.

**Architecture:** Three new pass-through kinds fetch and store FMP's responses as the existing kinds do. A pure module reads a stored filing report into bounded views (sheet list, sheet rows, one cell's text, a text search), and a new ref form, `filing:`, cites a cell by indexes. A new route module serves the views and the filing list; three MCP tools call the routes. The quarters come from the same reading as the trailing figures, are served by a read and a tool of their own, and resolve as a third period of `fact:`.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, the MCP server, pytest, mypy, ruff.

**Spec:** `docs/superpowers/specs/2026-11-11-filings-access-design.md`. Read it whole before a task; a task names its sections.

## Global Constraints

- Work only in `/home/kaban/workspace/fairband/.claude/worktrees/filings-access` (branch `worktree-filings-access`). Never read or write the main checkout.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- Never print, log, store or commit a key. Never commit vendor data: every fixture is synthetic, for the invented companies the tests already use (ACME on the vendor doubles, AAPL in the web store).
- No live vendor call and no network call from a task. The live check is the controller's, after the merge.
- The caps, exact: 100 rows a sheet answer or a filing-list answer, 2,000 characters a cell in a sheet answer, 20,000 characters a cell page, 20 search hits, 300 characters each side of a match, a search text of 3 characters or more, 1,000 rows FMP is asked for, 365 days the default window, 720 hours of reuse for a filing report, 8 quarters a `quarters` answer.
- The budget, exact: a list an answer holds (a sheet's rows, the filings, the search hits) stops before the item that would take the list's compact JSON (`json.dumps(items, ensure_ascii=False, separators=(",", ":"))`) past 20,000 characters, one item at least.
- `docs/method.md` changes in the same commit as the behaviour it describes. No version changes: the method, the policy, the review and the secondary versions stand.
- No change to the page's code, the engine, the refresh, `financials` or `segments` (spec 2).
- Commit messages: one plain sentence in the imperative (see `git log`), ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- No subagent dispatches another subagent; review arrives from the controller.

## Review Focus

1. A sheet name with a space, a comma, an apostrophe, `/`, `~`, `%`, `?`, `#`, a no-break space or a non-ASCII letter: the route reads the `sheet` parameter by its served name, and the row's ref plus `/<col>` resolves to the cell. Tests: Task 2 Step 1 (`test_a_filing_ref_resolves_whatever_the_sheet_s_name_holds`), Task 3 Step 1 (`test_a_sheet_name_with_odd_characters_round_trips`), Task 4 Step 1 (the tool sends the name unchanged).
2. FMP answers HTTP 200 with `{"Error Message": ...}` for a period it does not hold: a 404 with the sentence, the response stored with its error, and the next ask calls FMP again. Tests: Task 1 Step 1 (`test_a_report_fmp_does_not_hold_is_stored_unusable_and_never_reused`), Task 3 Step 1 (`test_a_report_fmp_does_not_hold_is_404`).
3. A search text with regular-expression characters or other white space than the cell's (`$12.5`, `(Detail)`, `not  yet commenced` against a no-break space): matched as plain text on the served text, and a cell page read at the hit's `offset` starts with the match. Test: Task 2 Step 1 (`test_search_matches_plain_text_and_its_offset_opens_the_page`).
4. A sheet of many wide rows, or of rows with long cells: the answer ends its page by the budget before 100 rows, and `nextRow` continues without a gap or a repeat. Test: Task 2 Step 1 (`test_the_budget_ends_a_page_before_a_hundred_rows`).
5. A company with no stored quarterly rows, or with quarters in another currency: `quarters` is `[]` or leaves those periods out and counts them, and a `fact:` ref of such a quarter is `unresolved reference`, never an error. Tests: Task 5 Step 1 (`test_no_quarter_rows_give_no_quarters`, `test_a_quarter_in_another_currency_is_left_out_and_counted`, `test_a_quarter_not_on_file_is_unresolved`).

---

### Task 1: The three FMP routes and the three pass-through kinds

Spec sections 3, 4, 10.

**Files:**
- Modify: `src/fairband/vendors/fmp.py` (three methods, `FILINGS_LIMIT`, the docstring's note of the live check of 2026-11-11)
- Modify: `src/fairband/refresh/passthrough.py` (the kinds, the docstring)
- Modify: `tests/refresh/vendor_double.py` (`_FMP_ENDPOINTS`: `"sec-filings-search/symbol": "sec-filings"`, `"financial-reports-dates": "filing-report-dates"`, `"financial-reports-json": "filing-report"`; and `_resolve` leaves the request's `period` out of the fixture's name and of the endpoint it counts for `financial-reports-json`, whose `period` is a fiscal period and not `annual` or `quarter`)
- Create: `tests/fixtures/fmp/sec-filings-search-symbol.ACME.json`, `tests/fixtures/fmp/financial-reports-dates.ACME.json`, `tests/fixtures/fmp/financial-reports-json.ACME.json` (one name for both test doubles: the web tests' `Vendor` reads `fmp/<route>.<symbol>.json`)
- Test: `tests/vendors/test_fmp.py`, `tests/refresh/test_passthrough.py`

**Interfaces:**
- Produces, in `vendors/fmp.py`: `FILINGS_LIMIT = 1000`; `Fmp.filings(symbol: str, start: date, end: date) -> VendorResponse` (GET `sec-filings-search/symbol` with `symbol`, `from` and `to` as ISO dates, `page` `"0"`, `limit` `"1000"`); `Fmp.filing_report_dates(symbol: str) -> VendorResponse` (GET `financial-reports-dates`); `Fmp.filing_report(symbol: str, year: int, period: str) -> VendorResponse` (GET `financial-reports-json` with `symbol`, `year`, `period`). Each sends `to_fmp_symbol(symbol)`.
- Produces, in `refresh/passthrough.py`: `FILING_KINDS = ("filings", "filing-reports", "filing-report")`; `FILING_PERIODS = ("FY", "Q1", "Q2", "Q3", "Q4")`; `FILING_REPORT_REUSE_HOURS = 720`; the sentences `BAD_PERIOD = "period is FY or Q1 to Q4"`, `NEEDS_PERIOD = "a filing report needs year and period"`, `BAD_WINDOW = "from and to are ISO dates, from on or before to"`. `KINDS` is unchanged and `unknown_kind` still names `KINDS` alone.
- Produces: `Passthrough.fetch(kind, symbol, params)` for the three kinds, each one part named as its kind:

  | Kind | `params` | Stored endpoint | Logical params | Reuse | Usable |
  |---|---|---|---|---|---|
  | `filings` | `from`, `to` (ISO dates, both required) | `sec-filings` | `symbol`, `from`, `to`, `limit` (`"1000"`) | `reuse_hours` | a list |
  | `filing-reports` | none | `filing-report-dates` | `symbol` | `reuse_hours` | a list |
  | `filing-report` | `year`, `period` (both required) | `filing-report` | `symbol`, `year`, `period` | 720 hours | `filing_report_usable` |

- Produces: `filing_report_usable(payload: Any) -> bool`: an object without the key `Error Message` that holds a key whose value is a list. An unusable payload is stored with its error and answered as fetched, `Fetched.row.error` set, as `pe-history`'s is.

**The fixtures** (hand-made, in FMP's shape, spec 3):
- `sec-filings-search-symbol.ACME.json`: eight rows, newest first, each `symbol`, `cik` (`"0000000001"`), `filingDate` and `acceptedDate` (`"2026-10-28 00:00:00"`), `formType`, `link`, `finalLink`, the links under `https://www.sec.gov/Archives/edgar/data/1/`. Form types in order: `8-K`, `4`, `10-Q`, `8-K`, `4/A`, `144`, `10-K`, `DEF 14A`; dates falling from 2026-10-30 to 2026-07-29, the `10-Q` on 2026-10-28.
- `financial-reports-dates.ACME.json`: three rows, `{"symbol": "ACME", "fiscalYear": 2027, "period": "Q1", "linkJson": "https://financialmodelingprep.com/stable/financial-reports-json?symbol=ACME&year=2027&period=Q1&apikey=YOUR_API_KEY", "linkXlsx": ...}`, then 2026 `Q4` and 2026 `FY`.
- `financial-reports-json.ACME.json`: `symbol`, `period` `"Q1"`, `year` `"2027"`, then five sheets:
  - `Cover Page`: three rows of strings.
  - `INCOME STATEMENTS`: a title row `{"INCOME STATEMENTS - USD ($) $ in Millions": ["3 Months Ended", "3 Months Ended"]}`, `{"items": ["Sep. 30, 2026", "Sep. 30, 2025"]}`, `{"Revenue": [340, 310]}`, `{"Operating income": [68, 60]}`.
  - `LEASES`: a title row, an `items` row, and `{"LEASES": [<one string of about 3,000 characters>]}`. The string holds runs of spaces and a no-break space, and the sentence `we had additional leases, primarily for warehouses, that had not yet commenced of $12.5 million` once, past character 2,100 of the served text.
  - `Leases - Additional Informatio`: a title row `{"Leases - Additional Information (Detail) $ in Millions": ["3 Months Ended"]}`, an `items` row, `{"Additional leases, primarily for warehouses, that have  not yet commenced": [12.5]}` (a no-break space and a double space in the label, as FMP's labels hold), `{"Lease terms, minimum/maximum ~ years": ["1 year"]}`.
  - `Revenue by Product/Region`: a title row, `{"Widgets": [210, 190]}`, `{"Gadgets, other": [130, 120]}`.

- [ ] **Step 1: Write the failing tests**

`tests/vendors/test_fmp.py`, in the file's style (the mock transport that records the request):

```python
def test_the_filing_routes(...) -> None:
    """Spec 2026-11-11, 3: the three routes and their parameters, the key apart."""
    fmp.filings("BRK.B", date(2025, 11, 11), date(2026, 11, 11))
    assert (path, params) == ("/stable/sec-filings-search/symbol",
        {"symbol": "BRK-B", "from": "2025-11-11", "to": "2026-11-11", "page": "0", "limit": "1000"})
    fmp.filing_report_dates("ACME")
    assert (path, params) == ("/stable/financial-reports-dates", {"symbol": "ACME"})
    fmp.filing_report("ACME", 2027, "Q1")
    assert (path, params) == ("/stable/financial-reports-json",
        {"symbol": "ACME", "year": "2027", "period": "Q1"})
```

`tests/refresh/test_passthrough.py`:

```python
WINDOW = {"from": "2025-11-11", "to": "2026-11-11"}
REPORT = {"year": "2027", "period": "Q1"}


def test_the_filing_kinds_are_not_the_generic_route_s() -> None:
    assert FILING_KINDS == ("filings", "filing-reports", "filing-report")
    assert not set(FILING_KINDS) & set(KINDS)  # test_kinds stays as it is


def test_the_filing_list_is_one_call_stored_with_its_window(env: Env) -> None:
    [(part, first)] = _passthrough(env).fetch("filings", "ACME", WINDOW).items()
    assert part == "filings" and env.router.calls == {"sec-filings": 1}
    assert env.router.requested["sec-filings"] == {
        "symbol": "ACME", "from": "2025-11-11", "to": "2026-11-11", "page": "0", "limit": "1000"}
    params = {"symbol": "ACME", "from": "2025-11-11", "to": "2026-11-11", "limit": "1000"}
    assert _stored(env, first.row.id) == ("sec-filings", "ACME", params, None)
    # the same window is reused inside reuse_hours; another window is another call


def test_the_reports_on_file_are_one_call(env: Env) -> None:
    # "filing-reports": endpoint "filing-report-dates", params {"symbol": "ACME"}, reused inside
    # reuse_hours, called again after it


def test_a_report_is_reused_for_thirty_days(env: Env) -> None:
    passthrough = _passthrough(env)
    first = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert _stored(env, first.row.id) == (
        "filing-report", "ACME", {"symbol": "ACME", "year": "2027", "period": "Q1"}, None)
    env.clock.now += timedelta(hours=FILING_REPORT_REUSE_HOURS - 1)
    assert passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"].reused is True
    env.clock.now += timedelta(hours=1)
    again = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert again.reused is False and again.row.id != first.row.id
    assert env.router.calls == {"filing-report": 2}
    with closing(env.connect()) as conn:  # a ref made on the first row still has its payload
        assert response_payload(conn, first.row.id) is not None


def test_a_report_fmp_does_not_hold_is_stored_unusable_and_never_reused(env: Env) -> None:
    env.router.bodies["filing-report"] = b'{"Error Message": "No Data for this symbol"}'
    passthrough = _passthrough(env)
    first = passthrough.fetch("filing-report", "ACME", REPORT)["filing-report"]
    assert first.row.error is not None and first.row.error.startswith("unusable payload")
    passthrough.fetch("filing-report", "ACME", REPORT)
    assert env.router.calls == {"filing-report": 2}


@pytest.mark.parametrize(("kind", "params", "sentence"), [
    ("filing-report", {"year": "2027"}, "a filing report needs year and period"),
    ("filing-report", {"period": "Q1"}, "a filing report needs year and period"),
    ("filing-report", {"year": "2027", "period": "Q5"}, "period is FY or Q1 to Q4"),
    ("filing-report", {"year": "soon", "period": "Q1"}, "year must be a whole number, not 'soon'"),
    ("filings", {}, "from and to are ISO dates, from on or before to"),
    ("filings", {"from": "2026-11-11", "to": "2025-11-11"}, "from and to are ISO dates, from on or before to"),
    ("filings", {"from": "yesterday", "to": "2026-11-11"}, "from and to are ISO dates, from on or before to"),
])
def test_a_bad_filing_request_is_a_value_error_before_any_call(env, kind, params, sentence) -> None:
    with pytest.raises(ValueError, match=re.escape(sentence)):
        _passthrough(env).fetch(kind, "ACME", params)
    assert not env.router.calls


def test_a_key_inside_a_link_does_not_reach_the_store(env: Env) -> None:
    """Spec 10: FMP's dates answer links; one that carried the key is stored scrubbed."""
    body = json.dumps([{"symbol": "ACME", "fiscalYear": 2027, "period": "Q1",
                        "linkJson": f"https://example.invalid/r?apikey={FMP_KEY}"}])
    env.router.bodies["filing-report-dates"] = body.encode()
    fetched = _passthrough(env).fetch("filing-reports", "ACME", {})["filing-reports"]
    with closing(env.connect()) as conn:
        assert FMP_KEY not in (response_payload(conn, fetched.row.id) or "")
    assert FMP_KEY not in json.dumps(fetched.payload)
```

Add the three kinds to the parametrized `test_each_kind_stores_its_call` where its shape fits.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/vendors/test_fmp.py tests/refresh/test_passthrough.py -q`
Expected: FAIL, `Fmp` has no `filings`, and `FILING_KINDS` cannot be imported.

- [ ] **Step 3: Implement the three `Fmp` methods and the three kinds**

The kinds are three more cases of `Passthrough._calls`; `_Call.reuse` and `_Call.usable` already carry a reuse window and a usable test. `fetch` raises the same `ValueError(unknown_kind(kind))` for a kind in neither list.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/vendors/test_fmp.py tests/refresh/test_passthrough.py -q`
Expected: PASS.

- [ ] **Step 5: Run the checks and commit**

Run the Global Constraints' command, then:

```bash
git add src/fairband/vendors/fmp.py src/fairband/refresh/passthrough.py tests/refresh/vendor_double.py tests/fixtures/fmp tests/vendors/test_fmp.py tests/refresh/test_passthrough.py
git commit -m "Fetch and store FMP's filing list, its filing reports on file and a filing report as pass-through kinds, a report reused for thirty days and a missing one never reused"
```

---

### Task 2: The views of a filing report and the `filing:` ref

Spec sections 5 (the served text, the budget), 5.2, 5.3, 5.5, 5.6, 9.

**Files:**
- Create: `src/fairband/reports/filing_report.py`
- Modify: `src/fairband/reports/refs.py` (the reader of `filing:` in `Resolver._readers`, its words in `Resolver.describe`, the module docstring's list of forms)
- Modify: `docs/method.md` (16.2: a row for `filing:<id>/<sheet>/<row>/<col>`, "a cell of a stored filing report by its sheet's served name and its row's and cell's indexes from 0 (spec 2026-11-11, 5.5)", unit none; and the references list's words where 16 describes them)
- Modify: `playbook/fairband-research/reference/citations.md` (the same row in its table of refs) and `tests/test_playbook.py` (`REF_FORMS` gains `"filing"`)
- Test: `tests/reports/test_filing_report.py`, `tests/reports/test_refs.py`, `tests/reports/test_check.py`

**Interfaces:**
- Consumes: nothing of Task 1 but the stored endpoint's name, `filing-report`, and its params `year` and `period`.
- Produces, in `reports/filing_report.py` (pure functions over the parsed payload; no database, no HTTP):

```python
ENDPOINT = "filing-report"   # the stored endpoint a filing report is read from
SHEET_ROWS = 100
CELL_CHARS = 2_000
PAGE_CHARS = 20_000
SEARCH_HITS = 20
SEARCH_WINDOW = 300
SEARCH_MIN = 3
LIST_CHARS = 20_000
SHORT_TEXT = "text needs three characters or more"

class NoSheet(LookupError): ...      # str(): "no sheet named <name>: ask without sheet for the sheet list"
class OutOfRange(ValueError): ...    # str(): "<name> is 0 to <last>", the name row, col, fromRow or offset

def served(text: str) -> str
def fitting(items: Sequence[Any], limit: int) -> int
def sheet_list(report: Mapping[str, Any]) -> list[dict[str, Any]]
def row_ref(response_id: int, sheet: str, row: int) -> str
def sheet_rows(report: Mapping[str, Any], response_id: int, sheet: str, from_row: int = 0) -> dict[str, Any]
def cell_text(report: Mapping[str, Any], sheet: str, row: int, col: int = 0, offset: int = 0) -> dict[str, Any]
def search(report: Mapping[str, Any], response_id: int, text: str) -> dict[str, Any]
def cell(report: Mapping[str, Any], sheet: str, row: int, col: int) -> Any
def label(report: Mapping[str, Any], sheet: str, row: int) -> str | None
```

- `served`: every run of white space, the no-break space (U+00A0) among it, as one space; the ends trimmed.
- `fitting`: how many leading items of `items` an answer holds: at most `limit`, and as many as keep `json.dumps(items[:n], ensure_ascii=False, separators=(",", ":"))` at or under `LIST_CHARS`; 1 at least when there is an item.
- A sheet is a key of the report whose value is a list (`symbol`, `period` and `year` are not sheets). A sheet is named by its served name: every function takes `sheet` as a served name and matches the stored key by `served(key)`, the first match where two keys serve alike; none: `NoSheet`. A row is an object with one key, the label, whose value is the list of cells. A row of any other shape is served with `label` null and one cell, the row's JSON text (*the plan's call*; spec 12 leaves it to the builder), and holds no cell to cite.
- `sheet_list`: one `{"name", "title", "rows", "chars"}` a sheet, in the report's order; `name` the served key; `title` the first row's label, served; `chars` is `len(json.dumps(sheet, ensure_ascii=False))`.
- `row_ref`: `f"filing:{response_id}/{sheet}/{row}"` with the served sheet name escaped, `~` as `~0` first, then `/` as `~1`.
- `sheet_rows`: `{"sheet", "title", "rows", "nextRow"}`; `rows` holds the rows from `from_row` that `fitting(..., SHEET_ROWS)` allows, each `{"row", "label", "rowRef", "cells"}`, the label served; a number cell is the number, a string cell its served text, and a served text longer than `CELL_CHARS` is `{"text": <the first 2,000 characters>, "chars": <the full length>}`; `nextRow` is the next `from_row` or `None`. `from_row` at or past the row count, or below zero: `OutOfRange("fromRow is 0 to <last>")`.
- `cell_text`: `{"sheet", "row", "col", "label", "chars", "offset", "text", "nextOffset"}`: at most `PAGE_CHARS` of the cell's served text from `offset` (a number cell's JSON text); `nextOffset` the next offset or `None`. `row`, `col` or `offset` out of range (an offset past the last character; 0 is always in range): `OutOfRange`.
- `search`: `{"hits", "more"}`. The needle is `served(text)`; shorter than `SEARCH_MIN`: `ValueError(SHORT_TEXT)`. A plain-text, case-blind match in the served text of each row's label and cells (a number by its JSON text), rows in the report's order, one hit a row: `{"sheet", "row", "col", "label", "excerpt", "offset", "rowRef", "numbers"}`; `col` the first cell that matches, `None` when only the label does; `excerpt` the served text from `SEARCH_WINDOW` before the first match to `SEARCH_WINDOW` after its end; `offset` the match's place in that cell (in the label for a label hit); `numbers` the row's number cells as `{"col", "value"}`. `hits` holds what `fitting(..., SEARCH_HITS)` allows; `more` is true when a further row matched.
- `cell`: the stored cell at the sheet (by served name), the row and the column, as stored (a number, a string); a sentinel the resolver reads as nothing where the sheet, the row or the cell is not there or the row is not a label with its cells. `label`: the row's served label, `None` likewise.
- Produces, in `refs.py`: `filing:<responseId>/<sheet>/<row>/<col>` resolves to `_figure(cell, None)` when the response is the report's company's, its endpoint is `filing_report.ENDPOINT`, its payload parses and the path has the four parts (the sheet token unescaped as `_unescaped` reads a pointer's token); nothing otherwise. `describe` reads it as `FMP filing report of fiscal <year> <period>, <sheet>: <label>, observed <day>`, the year and the period from the row's params, the day by `day_words`.

- [ ] **Step 1: Write the failing tests**

`tests/reports/test_filing_report.py`, on reports built in the test (a helper `_report(**sheets)` adds `symbol`, `period`, `year`):

```python
LEASES = "Leases - Additional Informatio"
RAW_LABEL = "Additional leases, primarily for warehouses, that have  not yet commenced"
LABEL = "Additional leases, primarily for warehouses, that have not yet commenced"


def test_served_text_has_single_spaces() -> None:
    assert served("  As of  September 30,\n\n 2026 ") == "As of September 30, 2026"


def test_the_sheet_list_names_each_sheet_with_its_title_and_size() -> None:
    report = _report(**{"INCOME  STATEMENTS ": [{"INCOME STATEMENTS - USD ($) $ in Millions": ["3 Months Ended"]},
                                                {"Revenue": [340, 310]}]})
    [sheet] = sheet_list(report)
    assert (sheet["name"], sheet["title"], sheet["rows"]) == (
        "INCOME STATEMENTS", "INCOME STATEMENTS - USD ($) $ in Millions", 2)
    assert sheet["chars"] == len(json.dumps(report["INCOME  STATEMENTS "], ensure_ascii=False))


def test_a_sheet_s_rows_carry_a_short_ref_and_the_cells() -> None:
    rows = sheet_rows(_report(**{LEASES: [{"Leases (Detail) $ in Millions": ["3 Months Ended"]}, {RAW_LABEL: [12.5]}]}), 7, LEASES)
    assert rows["title"] == "Leases (Detail) $ in Millions" and rows["nextRow"] is None
    assert rows["rows"][1] == {"row": 1, "label": LABEL, "rowRef": f"filing:7/{LEASES}/1", "cells": [12.5]}
    assert row_ref(7, "Revenue by Product/Region ~ net", 3) == "filing:7/Revenue by Product~1Region ~0 net/3"


def test_a_long_cell_is_cut_with_its_length() -> None:
    # a cell of 2,500 "x": {"text": "x" * 2000, "chars": 2500}; a cell of 2,000: the string whole


def test_a_sheet_answers_a_hundred_rows_and_the_next() -> None:
    # 250 short rows: rows 0..99 and nextRow 100; from_row=200: rows 200..249 and nextRow None;
    # from_row=250 or -1: OutOfRange("fromRow is 0 to 249")


def test_the_budget_ends_a_page_before_a_hundred_rows() -> None:
    """Review Focus 4: 60 rows, each one cell of 1,500 characters."""
    report = _report(NOTES=[{f"row {n}": ["x" * 1_500]} for n in range(60)])
    seen, start = [], 0
    while start is not None:
        page = sheet_rows(report, 7, "NOTES", start)
        assert 1 <= len(page["rows"]) < 100
        assert len(json.dumps(page["rows"], ensure_ascii=False, separators=(",", ":"))) <= 20_000
        seen += [r["row"] for r in page["rows"]]
        start = page["nextRow"]
    assert seen == list(range(60))  # no gap and no repeat
    # one item longer than the budget by itself is still served, alone
    assert fitting([{"a": "x" * 30_000}, {"b": 1}], 100) == 1 and fitting([], 100) == 0


def test_a_cell_page_is_twenty_thousand_characters() -> None:
    # a cell of 45,000 characters: offset 0 -> 20,000 chars, nextOffset 20000; 40000 -> 5,000 chars,
    # nextOffset None; chars 45000; offset 45001 -> OutOfRange("offset is 0 to 45000");
    # row 9 of a 2-row sheet -> OutOfRange("row is 0 to 1"); col 3 of a 1-cell row -> "col is 0 to 0";
    # a number cell 12.5 pages as "12.5"


def test_an_unknown_sheet_is_no_sheet() -> None:
    with pytest.raises(NoSheet, match="no sheet named Nope: ask without sheet for the sheet list"):
        sheet_rows(_report(), 7, "Nope")


def test_a_row_of_another_shape_is_served_as_its_json() -> None:
    # a sheet [["loose"], {"a": 1, "b": 2}]: each row label None, one cell, the row's JSON text;
    # cell(report, sheet, 0, 0) is the sentinel and label(report, sheet, 0) is None


def test_search_finds_a_label_and_a_cell() -> None:
    # the lease label row, searched as "not yet commenced": col None, numbers [{"col": 0, "value": 12.5}],
    # rowRef f"filing:7/{LEASES}/1", label LABEL; a note cell holding the sentence: col 0, the excerpt
    # 300 characters each side of the match (cut at the cell's ends), offset the match's place


def test_search_matches_plain_text_and_its_offset_opens_the_page() -> None:
    """Review Focus 3."""
    note = "x" * 2_500 + "  leases that had not yet commenced of $12.5 million (Detail). " + "y" * 500
    report = _report(LEASES=[{"LEASES": [note]}])
    for needle in ("$12.5", "(Detail)", "NOT  YET commenced"):
        [hit] = search(report, 7, needle)["hits"]
        page = cell_text(report, "LEASES", hit["row"], hit["col"], hit["offset"])
        assert page["text"].lower().startswith(served(needle).lower())


def test_search_stops_at_twenty_hits_and_at_the_budget() -> None:
    # 25 matching short rows: 20 hits, more True; 20: more False;
    # 12 matching rows whose excerpts and labels make each hit about 2,500 characters: fewer than 12 hits,
    # the hits' compact JSON at or under 20,000 characters, more True


def test_a_short_search_text_is_refused() -> None:
    with pytest.raises(ValueError, match="text needs three characters or more"):
        search(_report(), 7, " ab ")
```

`tests/reports/test_refs.py`, beside `test_response_refs` and with its way of storing a response:

```python
def test_a_filing_ref_resolves_whatever_the_sheet_s_name_holds(conn, policy, snapshots) -> None:
    """Review Focus 1. A response stored for the company under the endpoint "filing-report" with
    params {"symbol": ..., "year": "2027", "period": "Q1"}; one sheet's stored key is
    "Rev by  Product/Region ~ O'Neil, 5% net? #1 é", its rows a title row and {RAW_LABEL: [12.5, "1 year"]}."""
    # row_ref(id, served(key), 1) + "/0" resolves to Resolved(12.5, None, ...) and + "/1" to the word "1 year";
    # the same ref for another company's resolver, a response of another endpoint, a sheet that is not
    # there, row 9, col 9 and a ref with three parts or five each resolve to None;
    # describe(ref) == "FMP filing report of fiscal 2027 Q1, <the served key>: " + LABEL + ", observed <day>"
```

`tests/reports/test_check.py`: a report part `{"cite": "$12.5", "ref": <the cell's ref>}` followed by the plain text " million" passes the number check; `{"cite": "$13.5", ...}` fails as a wrong number does today.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/reports/test_filing_report.py tests/reports/test_refs.py tests/reports/test_check.py tests/test_playbook.py -q`
Expected: FAIL, the module `fairband.reports.filing_report` does not exist.

- [ ] **Step 3: Implement the module, the reader and the words**

- [ ] **Step 4: Write the `filing:` row in `docs/method.md` 16.2 and in `reference/citations.md`, and add `"filing"` to `REF_FORMS`**

Check `src/fairband/web/static/methodology.html` too: change it only if it names the ref forms.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/reports tests/test_playbook.py tests/test_method_doc.py -q`
Expected: PASS.

- [ ] **Step 6: Run the checks and commit**

```bash
git add src/fairband/reports/filing_report.py src/fairband/reports/refs.py docs/method.md playbook/fairband-research/reference/citations.md tests/reports tests/test_playbook.py
git commit -m "Read a stored filing report as a sheet list, a sheet's rows, one cell's text and a text search, each bounded, and cite a cell by a filing ref of indexes that the references list names"
```

---

### Task 3: The routes

Spec sections 5, 9 (`docs/method.md`), 11.

**Files:**
- Create: `src/fairband/web/filings_api.py`
- Modify: `src/fairband/web/app.py` (register the routes with the pass-through and the clock; `_VENDOR_READS` takes `/api/companies/[^/]+/filings`, `/api/companies/[^/]+/filing-report` and `/api/companies/[^/]+/filing-report/search`; the module docstring's list of the reads that may call a vendor)
- Modify: `docs/method.md` (where it describes the pass-throughs and the agent's reads: the three kinds, the three routes, the views, the budget, the caps and the refusals; find the passages by searching for `pass-through`, `/api/vendor` and `transcript-dates`, and add a subsection where none fits)
- Test: `tests/web/test_filings_api.py` (the app with a `Passthrough` on a mock transport, as `tests/web/test_vendor_api.py` builds it; move that file's `Vendor` double and its fixtures to `tests/support/` if both files need them)

**Interfaces:**
- Consumes: Task 1's kinds and sentences; Task 2's functions, constants and exceptions; `vendor_api.NO_FMP_KEY`; `policy.settings.exchange_symbol`.
- Produces: `add_filing_routes(app: FastAPI, passthrough: Passthrough | None, clock: Callable[[], datetime]) -> None`, and the sentences `NO_REPORT = "FMP holds no filing report for {symbol} {year} {period}: ask without year and period for the reports on file"`, `NO_LIST = "FMP answered no filing list for {symbol}"` and `NO_REPORTS = "FMP answered no filing reports for {symbol}"`.
- The routes, their answers in camelCase, each with `symbol`, `responseId`, `observedAt` and `reused`:
  - `GET /api/companies/{symbol}/filings?from=&to=&forms=&fromRow=` → `from`, `to`, `filings` (each `formType`, `filingDate` as `YYYY-MM-DD`, `acceptedDate`, `link`, `finalLink`; from `fromRow` of the filtered list, what `fitting(..., 100)` allows), `nextRow`, `count` (the filings the filter kept), `leftOut` (a number), `truncated`. `to` defaults to `clock().date()`, `from` to 365 days before `to`. `forms`: a comma list matched whole, case-blind, or `all`; left out, every form but `3`, `4`, `5`, `144` and those with `/A` after them. `fromRow` past the last filing or below zero: 400, `fromRow is 0 to <last>` (with no filing kept, only 0 is in range and the list is empty).
  - `GET /api/companies/{symbol}/filing-report?year=&period=&sheet=&fromRow=&row=&col=&offset=` → the four views of spec 5.2: `reports` (each `{year, period}`); or `year`, `period`, `sheets`; or those and Task 2's `sheet_rows`; or those and Task 2's `cell_text`.
  - `GET /api/companies/{symbol}/filing-report/search?year=&period=&text=` → `year`, `period`, `text`, `hits`, `more`.
- The refusals of spec 5.4, each sentence exact. `NoSheet` is a 404; `OutOfRange`, `SHORT_TEXT`, `BAD_PERIOD`, `NEEDS_PERIOD` and `BAD_WINDOW` are 400s; a `sheet`, `row`, `col`, `offset`, `fromRow` or `text` without `year` and `period` is `NEEDS_PERIOD` (declare the query parameters optional, so a missing one is this 400 and not the framework's 422); a `Fetched.row.error` on the report is the 404 `NO_REPORT`, and on the two lists the 502 `NO_LIST` or `NO_REPORTS`; no pass-through is 503 `no FMP key`; `PassthroughBusy` 503; `VendorError` 502.

- [ ] **Step 1: Write the failing tests**

`tests/web/test_filings_api.py`, with Task 1's three fixtures and the clock of the web tests (`NOW`):

```python
def test_the_filing_list_drops_the_ownership_forms_by_default(client, vendor) -> None:
    body = client.get("/api/companies/acme/filings", headers=HEADER).json()
    assert [f["formType"] for f in body["filings"]] == ["8-K", "10-Q", "8-K", "10-K", "DEF 14A"]
    assert (body["count"], body["leftOut"], body["truncated"], body["nextRow"]) == (5, 3, False, None)
    assert body["filings"][1]["filingDate"] == "2026-10-28"
    assert (body["to"], body["from"]) == (NOW.date().isoformat(), (NOW.date() - timedelta(days=365)).isoformat())
    # the vendor was asked for that window with page 0 and limit 1000


def test_forms_picks_and_all_keeps_everything(client) -> None:
    # forms=10-k,10-q -> two rows, count 2, leftOut 6; forms=all -> eight rows, leftOut 0


def test_a_long_filing_list_pages_within_the_budget(client, vendor) -> None:
    # vendor answers 1,000 rows of form 8-K with links of real length: truncated True, count 1000,
    # fewer than 100 rows in the answer, their compact JSON at or under 20,000 characters, nextRow set;
    # fromRow=<nextRow> continues with no gap; fromRow=1000 -> 400, "fromRow is 0 to 999"


@pytest.mark.parametrize("query", ["from=2026-11-11&to=2025-11-11", "from=soon", "to=2026-13-01"])
def test_a_bad_window_is_400(client, query) -> None:
    # 400, "from and to are ISO dates, from on or before to"


def test_the_reports_on_file_without_their_links(client) -> None:
    body = client.get("/api/companies/ACME/filing-report", headers=HEADER).json()
    assert body["reports"] == [{"year": 2027, "period": "Q1"}, {"year": 2026, "period": "Q4"}, {"year": 2026, "period": "FY"}]
    assert "link" not in json.dumps(body).lower()


def test_the_sheet_list(client) -> None:
    body = client.get("/api/companies/ACME/filing-report?year=2027&period=Q1", headers=HEADER).json()
    assert [s["name"] for s in body["sheets"]] == [
        "Cover Page", "INCOME STATEMENTS", "LEASES", "Leases - Additional Informatio", "Revenue by Product/Region"]
    assert (body["year"], body["period"]) == (2027, "Q1") and isinstance(body["responseId"], int)


def test_a_sheet_and_a_cited_cell(client, db_path) -> None:
    """The row's ref plus /0 resolves through the report check's resolver to 12.5 (spec 5.5)."""
    body = client.get("/api/companies/ACME/filing-report",
                      params={"year": 2027, "period": "Q1", "sheet": "Leases - Additional Informatio"},
                      headers=HEADER).json()
    row = body["rows"][2]
    assert row["cells"] == [12.5]
    assert row["label"] == "Additional leases, primarily for warehouses, that have not yet commenced"
    assert row["rowRef"] == f"filing:{body['responseId']}/Leases - Additional Informatio/2"
    # a Resolver for ACME on the same database resolves row["rowRef"] + "/0" to 12.5


def test_a_sheet_name_with_odd_characters_round_trips(client) -> None:
    """Review Focus 1: "Revenue by Product/Region" as a query parameter; its rows' refs write the
    slash as ~1, and each resolves."""


def test_a_long_cell_is_cut_and_paged(client) -> None:
    # sheet LEASES: the note's cell is {"text": 2,000 chars, "chars": n}; row=2 answers the whole
    # served text (n <= 20,000), nextOffset None; offset=2100 starts inside the text


def test_search_finds_the_sentence_and_the_row(client) -> None:
    body = client.get("/api/companies/ACME/filing-report/search",
                      params={"year": 2027, "period": "Q1", "text": "not yet commenced"}, headers=HEADER).json()
    assert [(h["sheet"], h["col"]) for h in body["hits"]] == [
        ("LEASES", 0), ("Leases - Additional Informatio", None)]
    assert body["hits"][1]["numbers"] == [{"col": 0, "value": 12.5}] and body["more"] is False


def test_a_report_fmp_does_not_hold_is_404(client, vendor) -> None:
    """Review Focus 2."""
    # vendor answers {"Error Message": ...} at 200 -> 404,
    # "FMP holds no filing report for ACME 2027 Q3: ask without year and period for the reports on file";
    # a second ask calls the vendor again


@pytest.mark.parametrize(("query", "status", "sentence"), [
    ("year=2027", 400, "a filing report needs year and period"),
    ("sheet=LEASES", 400, "a filing report needs year and period"),
    ("year=2027&period=Q5", 400, "period is FY or Q1 to Q4"),
    ("year=2027&period=Q1&sheet=Nope", 404, "no sheet named Nope: ask without sheet for the sheet list"),
    ("year=2027&period=Q1&sheet=LEASES&row=9", 400, "row is 0 to 2"),
    ("year=2027&period=Q1&sheet=LEASES&row=2&col=4", 400, "col is 0 to 0"),
    ("year=2027&period=Q1&sheet=LEASES&fromRow=3", 400, "fromRow is 0 to 2"),
])
def test_the_refusals(client, query, status, sentence) -> None: ...


def test_a_search_without_its_report_is_400(client) -> None:
    # /filing-report/search?text=lease and ?year=2027&text=lease -> 400, "a filing report needs year and period"


def test_a_short_search_text_is_400(client) -> None:  # text=ab -> 400, "text needs three characters or more"


def test_a_filing_list_that_is_not_a_list_is_502(client, vendor) -> None:
    # vendor answers {"Error Message": ...} at 200 for the list -> 502, "FMP answered no filing list for ACME";
    # for the dates -> 502, "FMP answered no filing reports for ACME"


def test_each_route_needs_the_request_header(client) -> None:
    for path in ("/api/companies/ACME/filings", "/api/companies/ACME/filing-report",
                 "/api/companies/ACME/filing-report/search?year=2027&period=Q1&text=lease"):
        assert client.get(path).status_code == 403


def test_without_a_pass_through_each_route_is_503(no_key_client) -> None:  # "no FMP key"


def test_no_key_in_an_answer(client) -> None:  # the fake key is in no answer of the three routes
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_filings_api.py -q`
Expected: FAIL with 404s: the routes are not registered.

- [ ] **Step 3: Implement `web/filings_api.py`, register it in `app.py` and widen `_VENDOR_READS`**

The routes are sync, as the vendor route is. Read the symbol as the vendor route does (`exchange_symbol`).

- [ ] **Step 4: Write the passages of `docs/method.md`**

Check `src/fairband/web/static/methodology.html` too: change it only if it names the agent's reads or the pass-throughs.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/web/test_filings_api.py tests/web/test_vendor_api.py tests/web/test_app.py tests/test_method_doc.py -q`
Expected: PASS.

- [ ] **Step 6: Run the checks and commit**

```bash
git add src/fairband/web/filings_api.py src/fairband/web/app.py docs/method.md tests/web tests/support
git commit -m "Serve the filing list and the views of a filing report over the API, each answer within the budget and each read behind the request header"
```

---

### Task 4: The filing tools

Spec section 6.

**Files:**
- Modify: `src/fairband/mcp/server.py` (`TOOL_NAMES`, three tools, the module docstring)
- Modify: `playbook/fairband-research/reference/tools.md` (the three signatures, so the playbook's test of the tools' order stays green)
- Test: `tests/mcp/test_server.py`

**Interfaces:**
- Consumes: Task 3's routes.
- Produces: in `TOOL_NAMES`, after `"pe_history"` and before the writes, `"filings"`, `"filing_report"`, `"filing_search"`:
  - `filings(symbol: str, forms: str | None = None, from_date: str | None = None, to_date: str | None = None, from_row: int | None = None)` → `GET /api/companies/<SYMBOL>/filings` with `forms`, `from`, `to` and `fromRow`.
  - `filing_report(symbol: str, year: int | None = None, period: str | None = None, sheet: str | None = None, from_row: int | None = None, row: int | None = None, col: int | None = None, offset: int | None = None)` → `GET /api/companies/<SYMBOL>/filing-report` with `year`, `period`, `sheet`, `fromRow`, `row`, `col`, `offset`.
  - `filing_search(symbol: str, year: int, period: str, text: str)` → `GET /api/companies/<SYMBOL>/filing-report/search`.
- Each description is one sentence that says what the tool answers and that a cell is cited as `filing:<id>/<sheet>/<row>/<col>`, in the register of the tools beside it. None needs `identify`.

- [ ] **Step 1: Write the failing tests**

In `tests/mcp/test_server.py`: add the three names to the expected tool order after `pe_history`; add to `READS`, after the pass-throughs' entries (the test's last line then counts ten reads that reach a route with no FMP key, not seven):

```python
"filings": ({"symbol": "AAPL", "forms": "10-K,10-Q", "from_date": "2026-01-01", "to_date": "2026-11-11", "from_row": 50},
            "/api/companies/AAPL/filings?forms=10-K%2C10-Q&from=2026-01-01&to=2026-11-11&fromRow=50"),
"filing_report": ({"symbol": "aapl", "year": 2027, "period": "Q1", "sheet": "Revenue by Product/Region", "from_row": 100},
                  "/api/companies/AAPL/filing-report?year=2027&period=Q1&sheet=Revenue+by+Product%2FRegion&fromRow=100"),
"filing_search": ({"symbol": "AAPL", "year": 2027, "period": "Q1", "text": "not yet commenced"},
                  "/api/companies/AAPL/filing-report/search?year=2027&period=Q1&text=not+yet+commenced"),
```

Add: `filing_report` with a symbol alone sends no parameter; a symbol of `..` is refused before any call, as the other reads are (the test that lists such calls takes the three tools); and a test on a client that records its calls, that `filing_report` sends the sheet name `Revenue by Product/Region` unchanged as the `sheet` parameter (Review Focus 1).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/mcp/test_server.py -q`
Expected: FAIL: the three tools are not registered.

- [ ] **Step 3: Implement the three tools**

- [ ] **Step 4: Add the three entries to `reference/tools.md`**

`tests/test_playbook.py::test_the_skill_names_every_tool` reads the tools' signatures from that file in the server's order. Add the three entries after `pe_history`'s, each with its full signature (`?` on an optional argument, as the file marks them) and one sentence on what it answers; Task 6 writes them in full and the playbook's steps.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/mcp tests/test_playbook.py -q`
Expected: PASS.

- [ ] **Step 6: Run the checks and commit**

```bash
git add src/fairband/mcp/server.py tests/mcp/test_server.py playbook/fairband-research/reference/tools.md
git commit -m "Add the filings, filing_report and filing_search tools over the filing routes"
```

---

### Task 5: The quarters: the read, the tool and the `fact:` ref of a quarter

Spec sections 6, 7, 9 (method 16.2), 11.

**Files:**
- Modify: `src/fairband/refresh/inputs_statements.py` (`QuarterFigures`, `StoredQuarters`, `stored_quarters`; `_trailing` reads its lines through the same helper)
- Modify: `src/fairband/web/reports_api.py` (the `quarters` route beside `financials`; `QUARTERS_SERVED = 8`)
- Modify: `src/fairband/reports/refs.py` (`Resolver._fact`: the quarter; the module docstring's `fact:` line)
- Modify: `src/fairband/mcp/server.py` (`"quarters"` in `TOOL_NAMES` after `"financials"`, the tool)
- Modify: `docs/method.md` (16.2: the `fact:` row reads `fact:<symbol>/<line>/<year, quarter or ttm>`, "a fiscal year's, a stored quarter's by its fiscal label (`2027-Q1`), or the trailing figures'"; and the `quarters` read where the document describes the company reads)
- Modify: `playbook/fairband-research/reference/citations.md` (the `fact:` row, the same words) and `reference/tools.md` (the `quarters` entry after `financials`')
- Test: `tests/refresh/test_inputs.py`, `tests/web/test_company_reads.py`, `tests/reports/test_refs.py`, `tests/reports/test_check.py`, `tests/mcp/test_server.py`

**Interfaces:**
- Produces, in `inputs_statements.py`:

```python
@dataclass(frozen=True)
class QuarterFigures:
    """One stored period of the quarterly statements, read as the trailing figures read it."""
    fiscal_year: int
    fiscal_period: str          # "Q1" to "Q4", as stored
    period_end: date
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
    interest_expense: float | None
    depreciation: float | None

    @property
    def period(self) -> str:    # "2027-Q1"


@dataclass(frozen=True)
class StoredQuarters:
    periods: tuple[QuarterFigures, ...]   # every stored period in the reporting currency, oldest first
    other_currency: int                   # the stored periods left out for another currency


def stored_quarters(conn: sqlite3.Connection, symbol: str) -> StoredQuarters
```

  The periods of `income-quarter`, oldest first, each joined to the `cashflow-quarter` period of the same end. Each line is that one period's term of the trailing sum: `_trailing` and `stored_quarters` read the lines through one helper, so the interest expense is read by its size and every other line as signed, as today. The reporting currency is the newest annual income statement's; a period whose currency is neither that nor missing is left out and counted in `other_currency`, as `_trailing` judges a period's currency. A period whose facts carry no fiscal year or no fiscal period is left out, uncounted; of two periods with one label, the later period end is kept. Without an annual income statement: no periods.
- Produces: `GET /api/companies/{symbol}/quarters` → `{"symbol", "currency", "quarters", "otherCurrency"}`: 404 as `financials` without statements; `quarters` the newest `QUARTERS_SERVED` periods, oldest first, each `{"period", "periodEnd", "fiscalYear", "fiscalPeriod", <line>: {"value", "unit", "ref"}}` with `ref` `fact:<SYMBOL>/<line>/<period>`; `[]` without quarterly rows. `financials` does not change.
- Produces: the tool `quarters(symbol: str)` → `GET /api/companies/<SYMBOL>/quarters`, a read with no vendor call and no header rule of its own.
- Produces: `fact:<symbol>/<line>/<YYYY>-Q<n>` resolves to the quarter's figure for a line of `QuarterFigures`, for any period of `StoredQuarters.periods`, the unit by `_line_unit`, the period the label, an outflow line as the trailing one. A label not on file, a period left out for its currency, or a line that is not one of the quarter's, resolves to nothing. `describe` already words a quarter (`_period_words`): "the revenue line of Q1 of fiscal 2027 on file".

- [ ] **Step 1: Write the failing tests**

`tests/refresh/test_inputs.py`, on the synthetic company's quarterly rows:

```python
def test_the_stored_quarters_read_as_the_trailing_figures_read_them(store) -> None:
    """Spec 2026-11-11, 7.1: the newest four add to the trailing figure of every line both hold."""
    conn = store(**bodies())
    quarters = stored_quarters(conn, SYMBOL).periods
    trailing = build(conn).trailing
    assert [q.period_end for q in quarters] == sorted(q.period_end for q in quarters)
    assert quarters[-1].period == f"{quarters[-1].fiscal_year}-{quarters[-1].fiscal_period}"
    for line in ("revenue", "operating_income", "net_income", "eps_diluted", "sbc", "cfo", "capex",
                 "dividends", "buybacks", "equity_issued", "interest_expense", "depreciation"):
        total = getattr(trailing, line)
        if total is not None:
            assert sum(getattr(q, line) for q in quarters[-4:]) == pytest.approx(total), line


def test_no_quarter_rows_give_no_quarters(store) -> None:
    """Review Focus 5."""
    # the company stored without income-quarter rows: StoredQuarters((), 0)


def test_a_quarter_in_another_currency_is_left_out_and_counted(store) -> None:
    """Review Focus 5: the two oldest quarters reported in CAD beside a USD annual statement."""
    # periods hold the others only; other_currency == 2


def test_a_period_without_a_fiscal_label_is_left_out(store) -> None: ...
def test_two_periods_with_one_label_keep_the_later_end(store) -> None: ...
```

`tests/web/test_company_reads.py`, in `test_financials`' store (AAPL: the last four quarters' revenue $310 m to $340 m):

```python
def test_quarters_lists_the_newest_stored_quarters(client: TestClient) -> None:
    body = _get(client, "/api/companies/aapl/quarters")
    assert (body["symbol"], body["currency"], body["otherCurrency"]) == ("AAPL", "USD", 0)
    quarters = body["quarters"]
    newest = quarters[-1]
    assert newest["periodEnd"] == "2026-09-30"
    assert newest["period"] == f"{newest['fiscalYear']}-{newest['fiscalPeriod']}"
    assert newest["revenue"] == _figure(340 * M, "currency", f"fact:AAPL/revenue/{newest['period']}")
    assert sum(q["revenue"]["value"] for q in quarters[-4:]) == 1300 * M  # the trailing revenue
    assert newest["epsDiluted"]["unit"] == "per-share"
    assert [q["periodEnd"] for q in quarters] == sorted(q["periodEnd"] for q in quarters)
    assert len(quarters) <= 8


def test_quarters_serves_eight_of_more(client, ...) -> None:
    # a store with twelve quarterly periods: eight served, the newest eight, oldest first


def test_quarters_without_statements_is_404(client: TestClient) -> None:
    # as test_financials_without_statements: "no financial statements for AAL"


def test_financials_is_unchanged(client: TestClient) -> None:
    assert "quarters" not in _get(client, "/api/companies/aapl/financials")
```

Add `quarters` to the loop of company reads that the file tests together (the one that lists `"financials", "financial-tables", ...`), where its shape fits.

`tests/reports/test_refs.py`, in `test_fact_refs`' store:

```python
def test_a_quarter_s_fact_resolves(conn, policy, snapshots) -> None:
    # fact:<SYMBOL>/revenue/<label> -> the quarter's revenue, unit "currency", period the label;
    # fact:<SYMBOL>/eps_diluted/<label> -> unit "per-share"; capex an outflow as fact:.../capex/ttm is;
    # describe(...) == "the revenue line of Q<n> of fiscal <year> on file"


def test_a_quarter_not_on_file_is_unresolved(conn, policy, snapshots) -> None:
    """Review Focus 5."""
    # fact:<SYMBOL>/revenue/1999-Q1 and fact:<SYMBOL>/total_assets/<label> resolve to None
```

`tests/reports/test_check.py`: a report section that cites a quarter's revenue with `period` set to the label (and to the label without its dash) passes the number check; with another quarter's label it fails `wrong period`.

`tests/mcp/test_server.py`: `"quarters"` after `"financials"` in the expected order, and in `READS`: `"quarters": ({"symbol": "AAPL"}, "/api/companies/AAPL/quarters")`, placed with the company reads so the last ten entries stay the reads that reach a vendor route.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/refresh/test_inputs.py tests/web/test_company_reads.py tests/reports/test_refs.py tests/reports/test_check.py tests/mcp/test_server.py -q`
Expected: FAIL: `stored_quarters` cannot be imported, and the route answers 404.

- [ ] **Step 3: Implement `QuarterFigures`, `StoredQuarters` and `stored_quarters`, the route, the tool, and the quarter in `Resolver._fact`**

The resolver reads the quarters once a resolver (`self._once`), as it reads the year lines.

- [ ] **Step 4: Write `docs/method.md` 16.2 and the read's passage, the citations reference and the tools reference**

Check `src/fairband/web/static/methodology.html` too: change it only if it names the ref forms or the company reads.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/refresh/test_inputs.py tests/web tests/reports tests/mcp tests/test_method_doc.py tests/test_playbook.py -q`
Expected: PASS.

- [ ] **Step 6: Run the checks and commit**

```bash
git add src/fairband docs/method.md playbook/fairband-research/reference tests
git commit -m "Serve the newest stored quarters by a read and a tool of their own, each line with a fact ref the report check resolves as a third period beside the fiscal year and the trailing twelve months"
```

---

### Task 6: The playbook

Spec section 8.

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (steps 3, 4 and 5, "The rules")
- Modify: `playbook/fairband-research/reference/tools.md` (the four tools in full, with each view, the budget and each cap), `reference/citations.md` (how a filing report's cell is cited)
- Test: `tests/test_playbook.py`

**Interfaces:**
- Consumes: the tools of Tasks 4 and 5 and the `filing:` ref of Task 2, by their names and answers.

- [ ] **Step 1: Write the failing test**

`tests/test_playbook.py`: `STEPS[3]` gains `"quarters"`; `STEPS[4]` becomes `("filing_report", "filing_search", "filings", "transcript", "segments", "finding_add")`; `STEPS[5]` gains `"quarters"`. A new test:

```python
def test_the_agent_reads_fairband_before_it_goes_outside() -> None:
    """Spec 2026-11-11, 8: the filing report, the filing list and the quarters come from Fairband;
    the host's tools read only what Fairband does not hold; a subagent is briefed after the check."""
    skill = _read(SKILL)
    steps = _steps(_frontmatter(skill)[1])
    four, five = _flat(steps[4]), _flat(steps[5])
    for words in (
        "Read Fairband first",
        "`filing_report(symbol)` lists the reports FMP holds",
        "the row's ref plus `/<col>`",
        "the sheet's title names the scale",
        "the scale word stands outside the cite",
        '{kind: "filing", ref: "response:<responseId>", note}',
        "an 8-K's exhibits",
        "by its `finalLink`",
    ):
        assert words in four, words
    assert "`quarters(symbol)`" in five and "`fact:`" in five
    assert "record each quarter's figure as a finding from the 10-Q or the press release" not in five
    assert "`split-pending` or `basis-scaled`" in five
    rules = _flat(skill[skill.index("## The rules") : skill.index("## Guidance")])
    assert "Before you brief a subagent to fetch a figure, check what Fairband holds" in rules
    tools = _flat(_read(TOOLS))
    for words in ("at most 100 rows", "20,000 characters of the answer's list", "2,000 characters",
                  "a page of 20,000 characters", "at most 20 hits", "the newest eight"):
        assert words in tools, words
    citations = _read(CITATIONS)
    assert "`fact:<symbol>/<line>/<year, quarter or ttm>`" in citations
    assert "`filing:<id>/<sheet>/<row>/<col>`" in citations
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: FAIL on the first phrase.

- [ ] **Step 3: Write the playbook**

Write in the playbook's own register (short sentences, the imperative, each tool in backticks). The content, by place:
- Step 3: `quarters(symbol)` lists the newest eight stored quarters, each line with its `fact:` ref.
- Step 4 opens with "Read Fairband first." Then, in this order: `filing_report(symbol)` lists the reports FMP holds, a 10-K as `FY` and a 10-Q as its quarter; `filing_report(symbol, year, period)` lists the sheets, which are the statements, each note as text and each note's detail tables; `filing_search(symbol, year, period, text)` finds a sentence or a row's label; `filing_report` with `sheet` reads a table, and with `row` a long cell's text. A number cell is cited as the row's ref plus `/<col>`, with no finding; the sheet's title names the scale (`$ in Millions`), the cite is the number as the cell holds it, and the scale word stands outside the cite. A sentence of a note is a finding whose source is `{kind: "filing", ref: "response:<responseId>", note}`, the note naming the report and the sheet. A foreign filer has annual reports only. `filings(symbol)` lists every filing of the past year with its links. Then: the host's own tools read only what Fairband does not hold: an 8-K's exhibits (the press release, recast figures), Item 1, the MD&A, the risk factors, the proxy statement and another company's filings; open each by its `finalLink`. The existing sentences on `segments`, `transcript` and `insider_trades` stay.
- Step 5, part 2: the quarter's revenue, EPS, operating income and cash flow are the figures of `quarters(symbol)`, cited by their `fact:` refs, the same quarter a year before among them; the operating margin and the free cash flow by `derive`. On a row flagged `split-pending` or `basis-scaled`, check a quarter's EPS against the note before you cite it. The paragraph "When the vendor has no transcript..." keeps its first two sentences; its last becomes: the quarter's figures still come from `quarters`.
- "The rules": "Before you brief a subagent to fetch a figure, check what Fairband holds: the statements, the quarters and the filing report. Brief a subagent only for what is not there, and give it the document's link."
- `reference/tools.md`: the four tools with their arguments; the four views of `filing_report`; the budget and the caps in words ("at most 100 rows an answer, and at most 20,000 characters of the answer's list, with `nextRow`"; "a cell longer than 2,000 characters is cut, with its length"; "a page of 20,000 characters, with `nextOffset`"; "at most 20 hits, with `more`"; `quarters` answers "the newest eight" stored quarters and counts those left out for another currency); the refusal sentences of spec 5.4; the default form filter of `filings`.
- `reference/citations.md`: beside the `filing:` row, one worked cite: `{"cite": "$12.5", "ref": "filing:<id>/Leases - Additional Informatio/2/0"}` followed by the plain word "million".

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: PASS, every test of the file.

- [ ] **Step 5: Run the checks and commit**

```bash
git add playbook tests/test_playbook.py
git commit -m "Tell the research agent to read the filing report, the filing list and the stored quarters from Fairband first and to brief a subagent only for what Fairband does not hold"
```

---

### Task 7: The end of the plan (the controller's)

- [ ] The whole-branch review, then its fixes.
- [ ] The ledger's deferred minors and parked findings move to `docs/backlog.md`, one row a file or a theme (CLAUDE.md).
- [ ] The spec's decision log takes the build's rulings.
- [ ] After the merge, with the founder's consent: restart the server from main; restart the Claude Code process that runs research; run the acceptance of spec 11 live for MSFT; write the readout in the spec's decision log.
