# The Research Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Research tab on the company page at `#company/<symbol>/research`: the company's report in one panel a section under the company's head, with a list of the sections at the left, the records the database holds drawn as cards beside the text, the references and the two appendixes closed until opened, and a Records view of the company's records; the old report page leaves.

**Architecture:** One new read answers the tab from the store: the reports on file, the report shown, the value card's figures and the records. The design system's vendored bundle exports its reader of a section's text in two steps, read and draw, so a page script can lay the blocks out. Pure functions turn a section's blocks into a layout (plain data); the tab's script draws that layout with the report page's own charts and parts, which move to scripts the tab shares, and the report page's script and panel are removed last.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite; plain JavaScript with React from the design-system bundle, no build step; pytest, with node for the page's own scripts (`tests/web/*.mjs`, `tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-17-research-tab-design.md`. Read it with your task: this plan argues from it, and where the two differ the spec wins. It stands on `docs/superpowers/specs/2026-11-16-company-page-design.md` ("the page's design") and `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md` 13.1 and 18.4 ("the report's design"), both built. The look is the mockup's: `docs/superpowers/specs/2026-11-17-research-tab-mockup/template.html` (its CSS, and its layout rules in its script); the spec's section 13 lists where the build differs from it.

**A map of the code as it stands:**

- `src/fairband/web/company_api.py`: `add_company_page_routes(app, conn_factory, policy, clock)`, the page's three reads (`page/overview`, `page/estimates`, `page/financials`); `_quote(conn, symbol)`, `_payload`, `checked_symbol` (from `reports_api`), `page_fmp.head_quote`.
- `src/fairband/web/reports_api.py`: `_report(conn, report_id)` (404 `no report <id>`), `_report_json(conn, report, policy, tax)` (the report whole: its record, `judgments`, `appendixA`, `appendixB`, `references`), `GET /api/companies/{symbol}/reports` (the list without `sections`), `GET /api/reports/{id}`, `GET /api/reports/{id}/markdown`.
- `src/fairband/web/research_api.py`: `GET /api/companies/{symbol}/research` builds its eight lists inline (`overrides`, `guidance`, `judgments`, `killCriteria`, `newsItems`, `notes`, `findings`, `ledger`), `LEDGER_ROWS = 20`. `src/fairband/web/reviews_api.py`: `review_json(review, with_result=False)`, `secondary_json(secondary)`.
- `src/fairband/web/rows.py`: `standing(value, price, edges) -> (ratio, word)`. `effective(conn, policy)` gives the policy with the user's settings; its `designation_edges` are the four edges.
- The store: `store/reports.py` (`ReportRow`: `snapshot_id`, `review_id`, `secondary_id`, `reuses_full_report_of`; `report_row`, `latest_report`, `reports_for`), `store/reviews.py` (`ReviewRow`: `value`, `buy_level`, `fair_low`, `fair_high`, `trim_level`, `refusal`, `mechanical_value`; `review_row`, `reviews_for`), `store/secondary.py` (`SecondaryRow`: `value_per_share` and the four levels; `secondary_row`, `secondaries_for`), `store/snapshots.py` (`SnapshotRow`: `value`, the four levels, `price`, `price_date`, `data_date`, `valid_until`, `refusal`; `snapshot_row`, `latest_snapshot`), `store/research.py` (`KillCriterionRow.report_id`, `NewsItemRow.report_id`; `kill_criteria_for`, `news_items_for`), `store/ledger.py` (`entries(conn, symbol, limit)`).
- `src/fairband/web/static/controls.js`: `VIEWS` (with `report` and `company`), `COMPANY_TABS = ['overview', 'financials', 'estimates']`, `show(tab, section, id)`, `keepReport`, `reportPath`, `keepCompany(symbol, tab)`, `companyPath()`, `fromHash()`, `P.openReport`.
- `src/fairband/web/static/company.js`: `TABS`, `load()` (reads `/page/<tab>`, keeps the answers by tab in `state.answers`), `tabs(symbol, tab, dataDate)` (three buttons and Research, a link to `#report/<symbol>`), `tabBody`, `failure(err, detail)`, and `P.companyPage` with `draw`, on which a tab's script hangs `draw.<tab>(answer, detail)`.
- `src/fairband/web/static/report.js`: the report page. Its `page()`, `head`, `brief`, `band`, `meta`, `revisions`, `reader`, `references`, `appendixA` (with `part`, `snapshotLine`, `input`, `bridge`, `byId`, `overrides`, `secondary`, `projection`, `partsYears`, `column`, `versions`, `classifier`), `appendixB`, `noReport`, `download`, `readSeries`, `settle`, `cited`, `read`, `refused`, `none`. It exports `P.reportAppendix = { overrides, snapshotLine }` and `P.reportHead`.
- `src/fairband/web/static/charts.js`: `P.reportCharts = { draw, roicPoints, points, kindsLine }`; `draw(report, series)` gives one element a heading; `FINANCIAL` (six groups by table name: `growth`, `cash_flow`, `solvency`, `returns`, `capital_allocation`, `quality`), `QUARTERLY`, `charted`, `bars`, `spread`, `valuation`, `reading`, `secondaryGrid`, `price`, `band`, `multiples`, `panel(key, chart, wide)` (the raised panel `app-chart`).
- `src/fairband/web/static/app.js`: `P.meter`, `P.levelRows`, `P.inputsTable`, `P.inputFigure(v, unit)`, `P.guidanceTable`, `P.phaseEvidence`, `P.pairs`, `P.figuresTable`, `P.secondaryRows`, `P.secondaryPath`, `P.when`, `P.localIso`, `P.footnotes(references)` (ref → n), `gapText(ratio, edges, name)`.
- The design system, vendored: `src/fairband/web/static/design-system/components/bundle.js` (`blocks(parts, footnotes)` at about line 838, which first builds the blocks `{ kind: 'p' | 'ul' | 'ol' | 'table', items, head?, start? }` and then draws them; `cited`; `ReportReader`; `BandMeter` with `low`, `high`, `price`, `fairValue`, `buyLevel`, `trimLevel`, `designation`, `gap`, `showScale`, `hero`; `HistoryBars` and `SpreadChart` with `height`; `SensitivityGrid`; `ValueBridge`; `OverrideRecord`) and `index.d.ts`. Every change there is marked `// fairband:` with the spec it comes from.
- `src/fairband/web/static/index.html`: the stylesheet (classes `app-…`), the panels (`<section id="report" hidden>`, `<section id="company" hidden>`) and the scripts in load order.
- Tests: `tests/support/page.py` (`node(helper, args, *scripts)`, `elements`, `classed`, `text`); `tests/web/page.mjs` (a helper or a bundle component called in node); `tests/web/company_load.mjs` (the company page's loader driven by steps); `tests/web/financials.mjs` (a tab that keeps state driven by steps, with a stub `localStorage`); `tests/support/web_app.py` (`client`, `db_path`, `policy`, `secondaries`); `tests/web/test_reports_api.py` (`_snapshot_id`, `_sections`, `_body`, `_published`: how a test publishes a report); `tests/web/test_report_reader.py`, `test_reader_blocks.py`, `test_report_charts.py`, `test_ticker_link.py`, `test_company_load.py`, `test_company_page.py`.

## Global Constraints

- No file under `src/fairband/engine/` or `src/fairband/policy/` changes. The method stays `fairband-mechanical/1.5` and the policy v16. No migration: the schema stays at 009. Nothing new is stored.
- No agent's write changes: `report_submit`, the number check (`reports/check.py`), the playbook and the Markdown export stay as they are. `GET /api/reports/{id}`, `GET /api/companies/{symbol}/reports` and `GET /api/companies/{symbol}/research` keep their answers.
- The tab's read calls no vendor. The tab writes nothing: no override, no kill criterion's state, no note of its own.
- A layout rule moves a block or sets blocks side by side. It never drops or rewrites one, but for the Summary's first line where it is exactly `Stance: <word>.` and the word is the report's stance.
- The page computes no figure: a card draws stored records and the read's fields. Money is written by `Fairband.formatMoney`, an input's figure by `P.inputFigure`.
- One reader of the text's shape: the tab reads and draws a section's blocks with `Fairband.reportText` alone.
- Every word a person reads is copied from this plan's Words table, which copies the spec's and the mockup's. A changed word is a spec change.
- No test uses the network. Fixtures are synthetic: never commit vendor data or a report on file. Never print, log, store or commit a key.
- Work in a worktree, not in the main checkout: the live server on port 8470 serves the page files of the main checkout as they are on disk.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, then a blank line, then `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- Every dispatched subagent, reviewers included, runs on Opus 5.5 at xhigh (the founder's standing rule).

## Words

| Where | Words |
|---|---|
| Tabs | `Overview`, `Financials`, `Estimates`, `Research` |
| Views | `Report`; `Records` with the count of the rows it draws |
| The bar's line | the stance; the mode; `revision <n>`; the date and time (`P.when`); the writer (`PrincipalChip`); `valid until <date>`; `reuses the full report of <date>` |
| Under the bar | `No full report to reuse.`; `The Markdown did not download: <the server's sentence>.` |
| The bar, right | `Footnote marks`; `Download .md` |
| The bar in Records | `The company's records on file, from any report.` |
| No report | `No report yet.` |
| The list | `The report`; `Kept closed`; `Reports on file · <n>`; an entry: `<date>, revision <n>` over `<mode>, <stance>` |
| The closed parts | `References` and `<n> sources, one for each cited number`; `Appendix A` and `the audit of the records the report rests on`; `Appendix B` and `the glossary, <n> terms` |
| The value card | `The report's call`; `on the data of <date>, priced that day` or `on the data of <date>, priced <date>`; `Value a share`; `mechanical`, `reviewed`, `reviewed, secondary valuation`; the meter's gap `<ratio> × the mechanical value`, `× the reviewed value`, `× the secondary valuation`; `buy below <money>`, `close to the value <money> to <money>`, `trim above <money>`; `Valid until <date>.`; `Today the mechanical value is <money> and the price <money>.` (`reviewed` for `mechanical` where the company's value today is a review's); `The mechanical value was <money>.` |
| The changes card | `Changes to Fairband's inputs`; `none`, or the count; `The report changes no input, so its value is the mechanical value.`; a line: the bridge's label, `<from> → <to>`, `<+ or −><money> a share` |
| The kill criteria card | `Kill criteria`; `<n> open of <m>`; a criterion: its state, `since <date>`, its text, its state's reason; `A criterion keeps its state after the report: an agent marks it when the event happens.` |
| The news card | `The sources on file`; the count; an item: its date, its address's host, its headline |
| The judgments | `Phase`, `Moat`, `Belief`, `Return on new capital`, `Target margin`; `stands`, `changed` |
| Two columns | `The bull case`, `The bear case` |
| A cite's box | `[<n>] <the reference's source>` |
| Records | `Kill criteria`, `Guidance`, `Overrides`, `Notes`, `Reviews`, `Secondary valuations`, `News items`, `Findings`, `Ledger`; `None on file.`; `current`, `superseded`; `the newest 20 of <n>` |
| Failures | 404 `no page data for <symbol>`; 404 `no report <id>`; 404 `report <id> is <its symbol>'s, not <symbol>'s`; any other failure of the read, the page's sentence |

## Review Focus

Five conditions the spec implies and a hurried build would miss. Each has its test in the task that owns the code.

1. **A section whose text has none of the shapes.** One table and nothing else; a named list at the section's end; a heading the rules do not know; no parts at all; a Summary with no stance line or with words after it. The blocks stand in their order, none is lost, and nothing throws (Task 3).
2. **A report on records that lack a figure.** A refused snapshot; a review with no value; a secondary valuation alone; a snapshot with no price. The read gives `call` with a refusal and no levels, and the card draws the sentence, no meter and no `NaN` (Tasks 1, 5).
3. **An address that names the wrong report, and a fast reader.** An id that is not a number, another company's, or gone; a second revision opened before the first one's charts landed. The server's sentence stands under the tabs; a series that lands for a report no longer shown is dropped (Tasks 1, 4, 5).
4. **A series that fails or never lands.** The multiples history refused, a sensitivity reading gone, the financial tables absent. The server's sentence stands in the chart's place and the text is drawn at once (Task 5).
5. **Storage that throws, and thin records.** No `localStorage` or one that throws: Footnote marks is off and no write throws. A company with no record of a kind: `None on file.`; a ledger of 3 rows: no "newest 20" line (Tasks 4, 6).

---

### Task 1: The read (spec 7.5, 8.1; Review Focus 2, 3)

**Files:**
- Create: `src/fairband/web/research_page.py`
- Modify: `src/fairband/web/company_api.py` (the route; `add_company_page_routes` gains `tax`), `src/fairband/web/app.py:478`, `src/fairband/web/reports_api.py` (`_report_json` becomes `report_json`), `src/fairband/web/research_api.py` (its lists move to `research_records`), `src/fairband/store/ledger.py`
- Create: `tests/support/reports.py` (the publish helpers of `tests/web/test_reports_api.py`, moved: `snapshot_id`, `sections`, `body`, `published`; that test imports them)
- Test: `tests/web/test_research_page_api.py`, the ledger's store test

**Interfaces:**
- Produces, Python:
  - `store.ledger.entry_count(conn, symbol: str) -> int`
  - `research_api.research_records(conn, company: str) -> dict[str, Any]` (the eight lists the route answers today)
  - `reports_api.report_json(conn, report, policy, tax) -> dict[str, Any]`
  - `research_page.report_call(snapshot: SnapshotRow, review: ReviewRow | None, secondary: SecondaryRow | None, edges: tuple[float, float, float, float]) -> dict[str, Any]`
  - `research_page.of_report(report: ReportRow, criteria: Sequence[KillCriterionRow], news: Sequence[NewsItemRow]) -> tuple[list[KillCriterionRow], list[NewsItemRow]]`
- Produces, the answer of `GET /api/companies/{symbol}/page/research?report=<id>`:

```
{ "symbol", "dataDate": null, "quote",
  "reports": [the list GET /api/companies/{symbol}/reports answers],
  "report": the answer of GET /api/reports/{id}, or null,
  "call": { "value", "basis", "note", "levels": { "buy", "fairLow", "fairHigh", "trim" } | null,
            "priceToValue", "designation", "price", "priceDate", "dataDate", "validUntil",
            "mechanicalValue", "refusal" } | null,
  "ofReport": { "killCriteria": [...], "newsItems": [...] } | null,
  "records": { ...research_records, "reviews": [review_json(r, with_result=False)],
               "secondaryValuations": [secondary_json(s)], "ledgerCount": int } }
```

- [ ] **Step 1: Write the failing tests of `report_call`**, on rows built from the test database's own (`dataclasses.replace`):

| Test | Rows | Asserts |
|---|---|---|
| `test_the_call_of_a_report_with_no_review` | snapshot valued 100 at price 150, no review | `value == 100`, `basis == "mechanical"`, `note is None`, the snapshot's four levels, `mechanicalValue == 100`, `refusal is None`, `(priceToValue, designation) == standing(100, 150, edges)` |
| `test_the_call_takes_the_review_s_value_and_levels` | the same snapshot, a review of value 80 with its levels | `value == 80`, `basis == "reviewed"`, the review's levels, `mechanicalValue == 100`, the word and the gap of 80 against 150 |
| `test_the_word_is_worked_out_at_the_report_s_price` | a review whose stored `designation` and `price_to_value` are of another price | the answer's are `standing(80, 150, edges)`, not the stored |
| `test_a_review_with_no_value_falls_to_the_secondary_valuation` | a refused snapshot, a review with `value=None`, a secondary of 12 a share | `value == 12`, `basis == "reviewed"`, `note == "secondary valuation"`, the secondary's levels, `mechanicalValue is None` |
| `test_a_refused_snapshot_its_review_values` | a refused snapshot, a review of value 5 | `value == 5`, `basis == "reviewed"`, `mechanicalValue is None`, `refusal is None` |
| `test_no_value_at_all_gives_the_refusal` | a refused snapshot; then with a review that refused | `value is None`, `levels is None`, `designation is None`, `refusal` the snapshot's; then the review's |
| `test_a_secondary_of_zero_does_not_count` | a refused snapshot, a secondary of 0 a share | `value is None` |
| `test_a_snapshot_with_no_price` | a valued snapshot with `price=None` | `value` and `levels` there; `price`, `priceToValue` and `designation` are `None` |

- [ ] **Step 2: Run them.** `uv run pytest tests/web/test_research_page_api.py -q`. Expected: FAIL, no module `research_page`.
- [ ] **Step 3: Implement `report_call`.** The value is the first of three that exists: the review's; the snapshot's; the secondary's where it is above zero. The levels are the same record's. `price`, `priceDate`, `dataDate`, `validUntil` are the snapshot's, dates as ISO days.
- [ ] **Step 4: Write the failing tests of `of_report`:** `test_the_report_s_own_criteria_and_those_it_cites`: criteria with the report's id, with another report's, with none and cited by a part `{"cite": "5.0%", "ref": "kill:7/threshold"}`, with none and not cited; the answer holds the first and the third, each once, in the store's order. `test_the_news_items_of_the_report_s_id_alone`.
- [ ] **Step 5: Implement `of_report`.** A cite names a criterion where its `ref` starts with `kill:<id>`, read from every section's parts.
- [ ] **Step 6: Write the failing tests of the route**, publishing through `tests/support/reports.py`:
  - `test_the_latest_report_and_a_named_revision`: two revisions; no `report` gives the newer id; `?report=<older>` gives the older; `reports` lists both, newest first, with no `sections`.
  - `test_the_report_is_the_report_read_s_answer`: `answer["report"] == client.get(f"/api/reports/{id}").json()`.
  - `test_another_company_s_report_and_none`: 404 `report <id> is MSFT's, not AAPL's`; 404 `no report 999`.
  - `test_a_company_with_no_report`: `report`, `call` and `ofReport` are `None`; `records` holds the nine lists and `ledgerCount`.
  - `test_a_company_with_no_snapshot`: 404 `no page data for ZZZZ`. A text that is no symbol: 400.
  - `test_the_records_carry_the_reviews_the_secondary_valuations_and_the_ledger_s_count`.
  - `test_the_read_calls_no_vendor`: with the transport of `test_company_page_api.py` that fails any call.
- [ ] **Step 7: Implement the route** in `add_company_page_routes`, `report: int | None = None` its query parameter, the policy `effective(conn, policy)`. Move the research route's lists into `research_records` and call it from both. Add `entry_count`.
- [ ] **Step 8: Run** `uv run pytest tests/web/test_research_page_api.py tests/web/test_research_api.py tests/web/test_reports_api.py tests/web/test_company_page_api.py -q`. Expected: PASS.
- [ ] **Step 9: Commit.**

### Task 2: The bundle's export (spec 6, 9)

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (`blocks`), `src/fairband/web/static/design-system/components/index.d.ts`
- Test: `tests/web/test_reader_blocks.py`

**Interfaces:**
- Produces: `Fairband.reportText.read(parts) -> blocks`, each block `{ kind: 'p' | 'ul' | 'ol' | 'table', items, head?, start? }` as `blocks` builds them today (a `p`'s `items` its lines; a list's its items; a table's `head` and `items` rows of cells; a line, an item and a cell a list of pieces, a text or a cite `{ cite, ref }`); `Fairband.reportText.draw(block, footnotes, key) -> element`, the element `blocks` draws for it today.

- [ ] **Step 1: Write the failing test** `test_read_and_draw_give_what_the_reader_drew`: for each fixture of the file, the elements of `Fairband.ReportReader`'s section equal `reportText.read(parts)` drawn one by one with `reportText.draw`; and `test_read_gives_the_blocks_kinds`: a text with a paragraph, a bullet list, a numbered list from 3 and a table gives kinds `['p', 'ul', 'ol', 'table']`, `start == 3`, a head of one row.
- [ ] **Step 2: Run it.** Expected: FAIL, `reportText` is undefined.
- [ ] **Step 3: Split `blocks`** into the two functions, `blocks` calling both, and export them on the bundle's object. Mark the change `// fairband:` with this spec's name and section 9; declare both in `index.d.ts`.
- [ ] **Step 4: Run** `uv run pytest tests/web/test_reader_blocks.py tests/web/test_report_reader.py -q`. Expected: PASS, every earlier test unchanged.
- [ ] **Step 5: Commit.**

### Task 3: The layout rules (spec 7.4, 4; Review Focus 1)

**Files:**
- Create: `src/fairband/web/static/company_research_text.js`
- Create: `tests/support/research_answers.py` (synthetic sections in the report template's shapes, and one synthetic answer of the read for the later tasks)
- Modify: `src/fairband/web/static/index.html` (the script, after `company_financials_chart.js`)
- Test: `tests/web/test_company_research_text.py`

**Interfaces:**
- Consumes: `Fairband.reportText.read`.
- Produces, on `P.researchText`:
  - `plain(pieces) -> string`: the pieces' text, a cite as its `cite`, `**` left out.
  - `named(blocks) -> blocks`: a `p` of one line, 90 characters or fewer, that ends in a colon, directly before a list or a table, becomes `{ kind: 'named', name: pieces without the colon, body: block }` with that block.
  - `isWide(block) -> boolean`: a table, bare or named, of more than four columns or with a cell above 44 characters. `isLong(block)`: with a cell above 44.
  - `GROUPS`: the six keys in order, `growth`, `cash_flow`, `solvency`, `returns`, `capital_allocation`, `quality`. `group(lead) -> key | null` by the spec's rule 3.
  - `lay(heading, parts, stance) -> { rows, cards }`. A row is one of `{ kind: 'run', blocks }` (text at the reading width), `{ kind: 'wide', block }`, `{ kind: 'columns', blocks }` (named lists side by side), `{ kind: 'pair', group, block }`, `{ kind: 'groups', groups }` (charts alone), `{ kind: 'sides', sides: [{ label, block }] }`. `cards` are the named blocks rule 2 moves beside the text.

- [ ] **Step 1: Write the failing tests**, each on synthetic parts:

| Test | Asserts |
|---|---|
| `test_the_stance_line_leaves_only_when_it_is_exact` | `Stance: trim.` with stance `trim`: gone. With stance `hold`, with `Stance: trim, for now.`, and with the line second: kept |
| `test_the_summary_s_named_lists_stand_side_by_side` | three named lists in a row give one `columns` row of three, after a `run` of the text before and before a `run` of what follows. One named list alone is not a `columns` row |
| `test_a_named_list_and_a_narrow_named_table_become_cards` | under `The business`: `cards` holds both, `rows` neither. A named table of five columns, and one with a cell of 45 characters, stay as `wide` rows |
| `test_a_section_that_is_only_named_blocks_keeps_them_in_place` | `cards == []`, the blocks in `rows` |
| `test_the_financial_pairs` | six paragraphs led `**Growth.**`, `**Cash flow.**`, `**Solvency.**`, `**Returns.**`, `**Capital allocation.**`, `**Quality.**`: six `pair` rows with the six keys in order |
| `test_a_group_is_named_once_and_an_unknown_lead_word_is_text` | two `**Growth.**` paragraphs: the second is in a `run`; `**Outlook.**`: a `run` |
| `test_a_group_no_paragraph_names_follows` | four lead words: four pairs, then one `groups` row with the other two keys |
| `test_fewer_than_four_lead_words_put_every_chart_first` | three: the first row is `groups` with all six, then the blocks in `run` rows |
| `test_the_lead_word_s_matching` | `Balance sheet` and `solvency` give `solvency`; `Returns on capital` gives `returns`; `Cash flow follows` gives `cash_flow`; `Growth` any case; `Quality scores` gives `quality` |
| `test_the_two_columns` | two paragraphs opening `The bull case:` and `**The bear case.**`: one `sides` row, labels `The bull case` and `The bear case`, each block's text without the opening words and its first letter upper case. Three paragraphs: `run` rows |
| `test_a_heading_with_no_rule_and_an_empty_section` | the blocks in order; `{ rows: [], cards: [] }` for no parts |
| `test_odd_sections` | a section that is one table: one `wide` or one `run` row and no card; a named list that ends a section: a card where text stands before it; a line that ends in a colon with nothing after it: a paragraph |
| `test_no_rule_drops_a_block` | for every fixture and heading: the blocks of `rows` and `cards`, flattened, are `named(read(parts))` without the stance line, each once |

- [ ] **Step 2: Run them.** `uv run pytest tests/web/test_company_research_text.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the functions. The mockup's `parse`, `labelled`, `isWide`, `summary`, `plain`, `financial` and `debate` hold the rules as the founder saw them; here they give data and draw nothing.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.**

### Task 4: The tab's frame (spec 7.1, 7.2, 7.3, 7.4, 7.7, 7.8; Review Focus 3, 5)

**Files:**
- Create: `src/fairband/web/static/report_parts.js` (moved out of `report.js`, not rewritten: `references`, `appendixA` and its helpers, `appendixB`, `download`, `none`)
- Create: `src/fairband/web/static/company_research.js`
- Create: `tests/web/research.mjs` (the tab driven by steps, as `financials.mjs` drives its tab: `mount`, `land`, `press`, with the stub `localStorage`)
- Modify: `src/fairband/web/static/report.js` (uses `P.reportParts`), `controls.js`, `company.js`, `index.html` (the scripts and the tab's rules)
- Test: `tests/web/test_company_research.py`, `tests/web/test_company_load.py`, `tests/web/test_company_page.py`, `tests/web/test_report_reader.py`

**Interfaces:**
- Consumes: the read's answer (Task 1); `Fairband.reportText` (Task 2); `P.researchText.lay` (Task 3).
- Produces:
  - `P.company = { symbol, tab, id }`, `id` a whole number for `research`, else `null`. `P.show('company', symbol, tab, id)`. The hash is `#company/<symbol>/research` or `#company/<symbol>/research/<id>`.
  - `P.companyPage.researchHref(symbol, id) -> string`; `P.companyPage.redraw()`.
  - `P.reportParts = { references(report), appendixA(report), appendixB(report), download(report, failed), overrides, snapshotLine }`; `P.reportAppendix` stays, the same two functions.
  - `P.companyPage.draw.research(answer, detail) -> element`.
  - `P.research = { bar(answer, view, marks, act), list(answer, shown), section(section, index, report, cards), closed(report), source(ref, references), storedMarks(), keepMarks(on) }`. `cards` is a map by heading that Task 5 fills; a section's panel takes its cards from it.
  - The panels' ids: `research-s<n>` from 1, `research-refs`, `research-a`, `research-b`. The storage key: `fairband.research.marks`.

- [ ] **Step 1: Write the failing tests of the address** in `test_company_load.py` and `test_company_page.py`: `research` is the fourth tab, a button; `show('company', 'AAPL', 'research', 12)` sets the hash `#company/AAPL/research/12` and reads `/api/companies/AAPL/page/research?report=12`; without an id, no query; the hash `#company/AAPL/research/x` keeps no id; another id of the tab shown reads again and the answer of the first, landing late, is dropped; a 404 of the research read draws the server's sentence as it arrives, any other status the page's sentence.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** in `controls.js` (`COMPANY_TABS`, `keepCompany(symbol, tab, id)`, `companyPath`, `show`'s fourth argument, `fromHash`'s fourth part) and `company.js` (`TABS`, the row, `load`, `failure`, `redraw`, `researchHref`). The row's link to `#report/` leaves.
- [ ] **Step 4: Write the failing tests of the frame** in `test_company_research.py`, on the synthetic answer:
  - `test_the_bar_s_line`: the stance chip's classes, with `fb-stance--expired` where `validUntil` is before the detail's `today`; the mode, `revision 2`, `valid until 4 Feb 2027`.
  - `test_a_valuation_review_names_the_report_it_reuses_or_that_it_has_none`.
  - `test_the_list`: twelve names, then `References` with `185`, `Appendix A`, `Appendix B`; ten names for a valuation review; `Reports on file · 2`, the shown one marked, the other a link to `researchHref`.
  - `test_a_section_is_drawn_by_its_layout`: a `run` at the reading width, a `wide` table, `columns`, `sides`; the cards of rule 2 beside the first run; no block drawn twice.
  - `test_the_blocks_are_the_bundle_s`: a paragraph's element equals `Fairband.reportText.draw` of its block.
  - `test_a_cite_s_source`: `source('fact:AAPL/revenue/2026', references) == '[3] FMP income statement, revenue, fiscal 2026'`; `None` for a ref the references lack.
  - `test_footnote_marks`: off at first; a press turns the class on and writes `1`; a reload with the item reads on; a store that throws: off, and the press does not throw.
  - `test_the_closed_parts`: three `details` with no `open`, their heads' words, the references' count; the nine parts of Appendix A as `P.reportParts.appendixA` draws them.
  - `test_a_company_with_no_report`: `No report yet.`, no list and no Request research of the tab's own; Records still a view.
  - `test_the_view_is_report_first_and_a_press_shows_records`: the bar's line gives way to `The company's records on file, from any report.`, and Footnote marks and Download .md leave.
  - `test_a_press_on_a_closed_part_s_name_opens_it`.
  - `test_download_s_refusal`: a failed download draws `The Markdown did not download: <sentence>.` under the bar.
  - `test_a_section_with_no_card_draws_no_cards_column`.
- [ ] **Step 5: Run them.** Expected: FAIL.
- [ ] **Step 6: Move the report's parts** to `report_parts.js`, `report.js` calling them, and run `uv run pytest tests/web/test_report_reader.py tests/web/test_ticker_link.py -q`. Expected: PASS, unchanged.
- [ ] **Step 7: Implement `company_research.js`.** One component keyed on the company keeps the view and the marks with `React.useState`. A section's panel draws `lay`'s rows; the cards column stands beside the first `run`. The section in view is marked in the list (`is-on`) where the browser has an `IntersectionObserver`; without one the first name stays marked. The stylesheet's rules are the mockup's under `app-research…` names, with the design system's tokens: a cite in the text's colour, `accent` on hover and focus, its `[n]` hidden until the marks are on; in an agent's table a cite carries no dotted line; in a card, a table's cells after the first are set right. `report_parts.js` loads before `report.js`, and `company_research.js` after `company_research_text.js`.
- [ ] **Step 8: Run** `uv run pytest tests/web -q`. Expected: PASS.
- [ ] **Step 9: Commit.**

### Task 5: The charts and the cards (spec 7.4 rules 3, 4, 6 to 10, 7.5, 7.6, 7.9, 8.2; Review Focus 2, 3, 4)

**Files:**
- Modify: `src/fairband/web/static/charts.js`, `src/fairband/web/static/company_research.js`, `src/fairband/web/static/index.html`
- Test: `tests/web/test_report_charts.py`, `tests/web/test_company_research_cards.py`

**Interfaces:**
- Consumes: Task 4's `section(…, cards)` and `redraw`.
- Produces, on `P.reportCharts`, each chart drawn with no raised panel: `groupCharts(read, height) -> { growth: [element], … }` or `{ refused: element }`; `quarterCharts(read, height) -> [element] | element | null`; `gridCharts(report, readings) -> [element]`; `priceCharts(series) -> [element]` (the band, the trailing P/E, the forward P/E). `draw` stays for `report.js`.
- Produces, on `P.research`: `valueCard(call, detail)`, `changesCard(report)`, `killCard(criteria)`, `newsCard(items)`, `judgmentCards(report)`, `series(report, held)` (starts the reads once for a report and gives what has landed).

- [ ] **Step 1: Write the failing tests of the charts:** `groupCharts` on the synthetic tables gives the six keys with 3, 2, 2, 1, 2 and 2 charts, each `HistoryBars` or `SpreadChart` given `height: 120`; on a refused read, the sentence; `priceCharts` with the multiples refused gives the band and the sentence; `gridCharts` with a reading that failed gives its sentence in its place. `draw`'s answers are unchanged.
- [ ] **Step 2: Write the failing tests of the cards:**

| Test | Asserts |
|---|---|
| `test_the_value_card` | `Value a share`, the value by `formatMoney`, `mechanical`; `BandMeter` with `low`, `high`, `price`, `fairValue`, `buyLevel`, `trimLevel`, `designation`, `gap: '1.90 × the mechanical value'`, `showScale: false`, `hero: false`; the three levels' words; the caption's two sentences |
| `test_priced_that_day_and_priced_on_another` | the head's two forms |
| `test_a_reviewed_value_names_the_mechanical_one` | `reviewed`, the gap's `the reviewed value`, the third sentence `The mechanical value was $451.42.`; none where `mechanicalValue` is null |
| `test_a_secondary_valuation_s_card` | `reviewed, secondary valuation`, the gap's `the secondary valuation` |
| `test_no_value_draws_the_refusal_and_no_meter` | the sentence; no `BandMeter`; no text holds `NaN` |
| `test_a_call_with_no_price_draws_the_value_and_no_meter` | the value and its kind; no `BandMeter`; no text holds `NaN` or `null` |
| `test_today_s_value_is_the_detail_s` | `reviewed` and the review's value where the detail carries a review with a value |
| `test_the_changes_card` | none: the sentence and `none`; three lines: each label, `25.6% → 19.8%` by `P.inputFigure`, `−$56.55 a share`, `+$3.04 a share`; a line with a refusal and no delta: its refusal |
| `test_the_kill_criteria_card` | `2 open of 3`; a criterion not open with its reason and `since` its state's day; the foot's sentence |
| `test_the_news_card` | newest first; the host without `www.`; a link only for an address that starts `http://` or `https://` |
| `test_the_judgment_cards` | the five names; `stands`; `changed` where `overrideId` is set |
| `test_the_cards_of_each_heading` | Summary: the value card; Valuation: the grids, then the changes card; Price and multiples: the three charts; Recent news; Risks and kill criteria; Key judgments: its cards in a row under the text |
| `test_a_pair_holds_its_group_s_charts_and_the_call_its_quarters` | a `pair` row draws its paragraph and `groupCharts`' charts of its key; a `groups` row the charts alone; The last earnings call opens with `quarterCharts`' row; every section's text is drawn while no series has landed |
| `test_a_series_of_another_report_is_dropped` | the reads of report 1 landing after report 2 is shown change nothing drawn |

- [ ] **Step 3: Run them.** Expected: FAIL.
- [ ] **Step 4: Implement.** The series are read as `report.js` reads them (`readSeries`, `settle`, `cited`), each read carrying `X-Fairband-Request: 1`, kept by the report's id outside the component, each landing calling `P.companyPage.redraw()`.
- [ ] **Step 5: Run** `uv run pytest tests/web -q`. Expected: PASS.
- [ ] **Step 6: Commit.**

### Task 6: Records (spec 7.10; Review Focus 5)

**Files:**
- Create: `src/fairband/web/static/company_research_records.js`
- Modify: `src/fairband/web/static/company_research.js` (the view and the bar's count), `src/fairband/web/static/index.html`
- Test: `tests/web/test_company_research_records.py`

**Interfaces:**
- Produces, on `P.researchRecords`: `panels(records) -> [{ name, count, note, heads, rows }]`, the nine in the spec's order, plain data; `count(records) -> number`, the sum of their rows; `draw(records) -> element`.

- [ ] **Step 1: Write the failing tests:** `test_the_nine_panels_in_order`; `test_each_panel_s_rows` (one synthetic record a kind, each cell's text: a guidance range `7.0% to 10.0%` and a money one by its currency, `current` and `superseded` by `supersededBy`; an override's figures by `P.inputFigure`; a review's value, mechanical value, count of overrides, designation or refusal; a finding's figure in its unit and currency); `test_none_on_file`; `test_the_ledger_says_the_newest_20_only_when_more_are_on_file` (`ledgerCount` 192 with 20 rows: `the newest 20 of 192`; 3 rows of 3: no note); `test_the_bar_s_count_is_the_rows_drawn`; `test_a_press_on_a_review_draws_its_bridge` (`Fairband.ValueBridge` with the row's lines; a second press closes it).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest tests/web -q`. Expected: PASS.
- [ ] **Step 5: Commit.**

### Task 7: The old addresses, the report page's removal, the narrow width and print (spec 7.1, 7.11, 9)

**Files:**
- Delete: `src/fairband/web/static/report.js`
- Modify: `controls.js` (`report` leaves `VIEWS`; `fromHash` and `P.openReport` send a report's address to the tab; `keepReport`, `reportPath` and `P.report` leave), `inbox.js:226`, `company_overview.js:137`, `charts.js` (`draw` leaves, and the docstring), `index.html` (the `report` panel, the script tag, the report page's rules nothing reads, the narrow width, print), `tests/web/page.mjs` and the tests that loaded `report.js`
- Test: `tests/web/test_company_load.py`, `tests/web/test_inbox_launch.py`, `tests/web/test_company_overview.py`, `tests/web/test_report_reader.py`, `tests/web/test_ticker_link.py`, `tests/web/test_app.py`

- [ ] **Step 1: Write the failing tests:** the hash `#report/AAPL` shows the company view on `research` with no id and the hash becomes `#company/AAPL/research`; `#report/AAPL/9` becomes `#company/AAPL/research/9`; `P.openReport('AAPL', 9)` the same; the inbox row's link and the Overview's "Open the report" are `researchHref`'s; `index.html` holds no `id="report"` and no `report.js`; the stylesheet holds the rule that sets the tab to one column below 980 px and, under `@media print`, hides the list, the bar's controls and the head's controls and shows the closed parts.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.** The tests of Appendix A in `test_report_reader.py` load `report_parts.js`; the report head's test in `test_ticker_link.py` leaves with the head. In print the three closed parts are drawn open by the stylesheet alone.
- [ ] **Step 4: Run the whole suite.** `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit.**

### Task 8: The documents, the look, the whole-branch review and the live steps (spec 10, 12)

**Files:**
- Modify: `docs/backlog.md`, `docs/method.md`, `src/fairband/web/static/methodology.html` where it names the report page, the two earlier designs' decision logs, this design's decision log, the design system's `ReportReader.md` and `CompanyReport.md` in the archive `docs/design-system/fairband-design-system_4.tar.gz`, and the module docstrings that name the report page or count the page's tabs and reads (`company_api.py`, `company.js`, `controls.js`, `charts.js`, `research_api.py`, `tests/web/page.mjs`)

- [ ] **Step 1: The documents**, as the spec's section 10 lists them. The backlog's new rows carry the founder's words of 2026-11-17 from the spec's decision log.
- [ ] **Step 2: The look.** The controller draws the tab in a headless browser on a scratch database that holds the reports of AAPL, NVDA, AVGO, FRVO, RKLB, PLTR and ASML, at 2,000 px and at 400 px, in both themes, and sets what the eye finds right before the review.
- [ ] **Step 3: The whole-branch review**, by a fresh reviewer on the whole diff against the spec, and its findings settled.
- [ ] **Step 4: Run the checks** of the Global Constraints. Expected: all pass.
- [ ] **Step 5: Commit.** Then, on the founder's word only: the merge to main, the server's restart, and the acceptance of the spec's section 12 with its readout in the decision log.
