# First Live Session Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the founder's three rulings from the first live report (QCOM, 2026-11-08): the secondary valuation is the fallback only, the report's text renders as the agent wrote it, and the row's levels follow the reviewed value.

**Architecture:** Three small changes on the merged Tier 2 code. (1) The secondary route refuses a call on a valued snapshot and the report check requires a secondary only on a refused one; the playbook, the method and the Methodology page follow. (2) `ReportReader` parses each section's parts into blocks (paragraphs, lists, tables, bold) instead of one paragraph; the check reads a list's number as a mark. (3) `agent_fields` hands the row the filling record's levels and its designation at the latest price; the drawer's and the report page's meter draw the review's band.

**Tech Stack:** Python 3.13, FastAPI, SQLite; plain JavaScript on the vendored design-system bundle patched with `// fairband:` comments; pytest; node 22 for one rendering test.

**Spec:** `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md`, as amended 2026-11-08 for plan 3: sections 11 ("Required where the route refused, refused where it values"), 13.1 ("The text's shape", the Valuation row), 13.3, 14 (steps 10 and 11), 18.1 ("The levels follow the reviewed value"), 18.2 (the meter), 18.4 (the reader's blocks), 19, 24 (plan 3) and the decision log's last row.

## Global Constraints

- `docs/method.md` changes in the same commit as the engine, the check or the route it describes; the Methodology page (`src/fairband/web/static/methodology.html`) in the same commit as the method text it restates.
- The mechanical method stays `fairband-mechanical/0.9`, `fairband-review/1` and `fairband-secondary/2` unchanged; every golden bit for bit. A dated row in the method's versions table records plan 3's rules with no version change, as Task 0 of plan 2 did.
- Never print, log, store or commit a key; never commit vendor data; fixtures are synthetic. The live database, the keys file and the live server on 127.0.0.1:8470 are off limits to every task; a task that needs a server runs its own against a scratch database on another port and stops it.
- The bundle (`src/fairband/web/static/design-system/components/bundle.js`, `bundle.css`, `index.d.ts`) is patched in place; every patch carries a `// fairband:` comment naming the spec section; `index.d.ts` declares every new prop or note.
- Run `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q` before every commit. Commit messages: one plain imperative sentence, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01K4pNFGMWqnrPuvG88Nf31f`.
- The register of `docs/method.md` and the playbook: plain words, the answer first, no first person.
- The playbook in the repository is `playbook/fairband-research/`; `~/.claude/skills/fairband-research` is a link to it, so the live skill changes with main.

## Review Focus

1. A report submitted on a valued snapshot while an older secondary valuation on that snapshot is on file (QCOM's case after plan 3) publishes without naming it; a `secondary:<id>/...` cite in it still resolves. Task 1's test.
2. A refused row with a counting secondary that a revalue then values: the secondary no longer fills Reviewed, the row returns to the engine's levels, the drawer's meter to the mechanical band. Task 3's test.
3. A review that refused on a valued row fills nothing: Reviewed is an em dash and the levels are the engine's. Task 3's test.
4. A table row whose cell holds a cite, a list item with a bold lead, a paragraph with a lone `*`, and a `|` inside a plain sentence that is not a table row: the reader renders the first three as blocks and the last as prose. Task 4's node test.
5. A two-digit list number at a line's start (`10. `) and a table's `|---|---|` row are marks, not quantities: the check publishes them. Task 4's check test.

---

### Task 1: The secondary valuation as the fallback only

**Files:**
- Modify: `src/fairband/web/reviews_api.py` (`post_secondary`, near line 457; the module docstring near line 62)
- Modify: `src/fairband/store/secondary.py` (`no_secondary`, line 246)
- Modify: `src/fairband/reports/check.py` (the docstring's secondary sentence near line 9; `CHECKS` "a secondary valuation on the snapshot", line 133 and near 232 of `render.py`)
- Modify: `src/fairband/reports/render.py` (the glossary and checks text that says every report carries one)
- Modify: `src/fairband/web/reports_api.py` (the module docstring near line 44; `submit` near line 316 if `no_secondary`'s new reason is not enough)
- Modify: `src/fairband/web/rows.py` (`agent_fields` docstring: "the second view beside a route's value, which the drawer's Details and the report show" goes)
- Modify: `src/fairband/mcp/server.py` (the `secondary_valuation` tool description near line 470)
- Modify: `docs/method.md` (15 opening, line 1189; 15.4 first bullet; 16.3's sentence "Every report carries the second view", line 1324; 16.6's Appendix A reasons; the glossary row "Secondary valuation", line 1080; the versions table, a dated row)
- Modify: `src/fairband/web/static/methodology.html` (section `agents`: the secondary paragraph, the stance paragraph, the "Where to read them" sentence on the second view)
- Test: `tests/web/test_reviews_api.py`, `tests/web/test_reports_api.py`, `tests/store/test_secondary.py`, `tests/reports/test_render.py`, `tests/web/test_methodology.py`, `tests/mcp/test_server.py`

**Interfaces:**
- Consumes: `latest_snapshot(conn, symbol)`, `no_secondary(conn, snapshot) -> str | None`, `structure_refusal(..., secondary_on_snapshot, snapshot_id)`.
- Produces: `no_secondary` returns `"the route values the company"` first, when `snapshot.value is not None`; the secondary route's 400 sentence `f"the route values {symbol}: the secondary valuation is the fallback where it refuses"`; Appendix A's `noSecondary` `"no secondary valuation: the route values the company"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_secondary_valuation_is_refused_where_the_route_values(client, valued_company):
    r = client.post("/api/companies/HGCO/secondary", json=standard_form(), headers=AGENT)
    assert r.status_code == 400
    assert r.json()["detail"] == "the route values HGCO: the secondary valuation is the fallback where it refuses"
    assert client.get("/api/companies/HGCO/secondary").json() == []

def test_a_secondary_valuation_is_made_where_the_route_refused(client, refused_company):
    assert client.post("/api/companies/AAL/secondary", json=standard_form(), headers=AGENT).status_code == 201

def test_a_report_on_a_valued_snapshot_needs_no_secondary(client, valued_company):
    r = client.post("/api/companies/HGCO/reports", json=full_report("HGCO"), headers=AGENT)
    assert r.status_code == 201
    a = client.get(f"/api/reports/{r.json()['id']}").json()["appendixA"]
    assert a["secondary"] is None
    assert a["noSecondary"] == "no secondary valuation: the route values the company"

def test_a_report_on_a_refused_snapshot_still_needs_one(client, refused_company):
    r = client.post("/api/companies/AAL/reports", json=full_report("AAL"), headers=AGENT)
    assert r.status_code == 400
    assert r.json()["detail"] == f"the report needs a secondary valuation on snapshot {latest_id('AAL')}"

def test_no_secondary_names_the_valued_route_first(conn, valued_snapshot):
    assert no_secondary(conn, valued_snapshot) == "the route values the company"
```

Also: a report on a valued snapshot that cites an older `secondary:<id>/value` made before plan 3 (insert the record with the store directly) publishes, and its Appendix A names that secondary (Review Focus 1); the Methodology pins (`test_the_agents_section_reads`) on the three changed sentences; the MCP tool description pin if the server's tests pin descriptions.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_reviews_api.py tests/web/test_reports_api.py tests/store/test_secondary.py -q -k "secondary"`
Expected: FAIL on the new sentences (the route answers 201 on a valued snapshot; the check refuses the valued report for a missing secondary).

- [ ] **Step 3: Implement the rule**

In `post_secondary`, after the policy, settings and method checks and before the foreign-filer refusal: `if latest.value is not None: raise HTTPException(400, f"the route values {symbol}: the secondary valuation is the fallback where it refuses")`. In `no_secondary`, the first branch returns `"the route values the company"` when `snapshot.value is not None`; `submit`'s `exempt` then covers the valued case with no other change (check that `structure_refusal` is still passed `secondary is not None or exempt`). Appendix A's `noSecondary` follows from `no_secondary`. Update `CHECKS`' wording for "a secondary valuation on the snapshot" so the rule it states is the refused-row rule. Update the docstrings named above and the MCP tool description: "Value the company a second way by a standard discounted cash flow where the route refuses; refused where it values".

`docs/method.md`: 15's opening sentence names the fallback only and says the call is refused where the route values (15.4); 15.4 gains the refusal as its first bullet, with the founder's date; 16.3 replaces "Every report carries the second view (spec 11); a secondary valuation made before a revalue does not count" with the refused-row rule (a valued latest snapshot needs none; a refused one needs the fallback; one made before a revalue does not count); 16.6 adds the third Appendix A reason; the glossary row says "the fallback where the route gives no value, refused where it does"; the versions table gains `| 0.9, policy v9 | 2026-11-08 | The secondary valuation only where the route refuses (15.4, 16.3); the list mark and the table row in the check (16.3); the row's levels from the reviewed value (14.5). No version changes: the arithmetic of every value is as before. |` (Task 3 and Task 4 add their clauses to this row; Task 1 writes the row with its own clause and leaves the others for them).

`methodology.html`, section `agents`: the secondary paragraph becomes "Where the route refuses or no phase fits, the report carries a secondary valuation: a value a share by a standard discounted cash flow, the fallback. Where the route values the company there is none: the engine refuses the call, so no second value weighs on the stance." (keep the drivers, the grid and the two exemptions sentences); the stance paragraph: "The agent weighs the price against the reviewed value's levels, or on a refused row against the secondary valuation's, and the report's thesis argues the stance."; in "Where to read them", drop "Beside a route's value, the secondary valuation is a second view, in the drawer's Details and the report." Keep the section under 930 words.

- [ ] **Step 4: Run the whole check and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

```bash
git add -A src tests docs/method.md
git commit -m "Make the secondary valuation the fallback only: refuse it where the route values the company, require it on a refused snapshot alone, and say so in the method and on the Methodology page"
```

---

### Task 2: The playbook follows the rule

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (step 10's "Then the second value" list, step 11, step 12's refusal sentence, the section "The secondary valuation" near line 502, the opening paragraph near line 19 "Every report values the company twice")
- Modify: `playbook/fairband-research/reference/report-template.md` (the submission paragraph near line 31; the Summary row and the summary page's shape; the section 8 detail's secondary bullet near line 155; the full example's secondary sentences and `secondary:93` cites; the line "Secondary valuation 93 is the standard discounted cash flow" near 278)
- Modify: `playbook/fairband-research/reference/tools.md` (line 97, `dcf`; lines 140 to 142, `secondary_valuation`)
- Test: `tests/test_playbook.py`

**Interfaces:**
- Consumes: Task 1's sentences, which the playbook quotes verbatim.
- Produces: nothing for later tasks.

- [ ] **Step 1: Write the failing tests**

In `tests/test_playbook.py`, pins: SKILL.md says "Where the route refuses or no route fits, and only there" before `secondary_valuation`; it does not contain "on every report"; step 11 contains "No DCF weighs on the stance where the route values the company"; the template's example contains no `secondary:` cite; tools.md's `dcf` line says "on a refused row only".

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: FAIL on the pins.

- [ ] **Step 3: Rewrite the passages**

Step 10's second-value list: "Where the route refuses or no route fits, and only there: **the secondary valuation**, `secondary_valuation` with `drivers`, the standard discounted cash flow, as the fallback … The server refuses the call where the route values the company: 'the route values <symbol>: the secondary valuation is the fallback where it refuses'. The report check refuses a report on a refused snapshot with no secondary valuation on it … Two refusals exempt …"; FMP's figure: "`dcf(symbol)`, a cross-check on the fallback: read it on a refused row only; never beside a route's value"; the route's grid unchanged. Step 11: "Read the value against its levels. Take the reviewed value when the current review has one, else the snapshot's value; on a refused row, the secondary valuation's. No DCF weighs on the stance where the route values the company: the founder's rule of 2026-11-08." Step 12's structural refusals list: "no secondary valuation on a refused snapshot". The opening paragraph: a report values the company by the engine's route, and by the standard DCF only where the route refuses. "The secondary valuation" section: open with the rule and the refusal sentence. The template: the Summary row's "and the secondary valuation's value" goes (keep it in a sentence for the refused case: "on a refused row, the secondary valuation's value in its place"); section 8's bullet reads "**The secondary valuation**, on a refused row only: … Where the route values the company, write no second value and read no DCF." The example (EXMP, valued): drop its secondary sentences and cites, and the line about secondary valuation 93; keep the sensitivity reading. tools.md as the pins say.

- [ ] **Step 4: Run the whole check and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

```bash
git add playbook tests/test_playbook.py
git commit -m "Have the playbook make the secondary valuation only where the route refuses and keep every DCF out of the stance where the route values the company"
```

---

### Task 3: The row's levels follow the reviewed value

**Files:**
- Modify: `src/fairband/web/rows.py` (`agent_fields`, `NO_AGENT_FIELDS`, `screen_row`)
- Modify: `src/fairband/web/app.py` (the `agent_fields` call near line 240 passes the effective policy's `designation_edges`)
- Modify: `src/fairband/web/static/app.js` (`meter`, near line 738; the section comment near 679)
- Modify: `src/fairband/web/static/design-system/components/index.d.ts` (the `reviewed` note near line 419 and the row's level notes)
- Modify: `src/fairband/web/static/methodology.html` (section `agents`, "Where to read them")
- Modify: `docs/method.md` (14.5's last paragraph: the reviewed value's levels and designation are what the screen's row shows; the versions row of Task 1 gains its clause)
- Test: `tests/web/test_rows.py`, `tests/web/test_app.py` (the pins `test_the_meter_takes_a_reviewed_value` near line 2241), `tests/web/test_screen_api.py` or the screen test that reads `/api/screen` with a review on file, `tests/web/test_methodology.py`

**Interfaces:**
- Consumes: `ReviewRow.{value, buy_level, fair_low, fair_high, trim_level}`, `SecondaryRow.{value_per_share, buy_level, fair_low, fair_high, trim_level}`, `designation_for(price, value, edges) -> (ratio, word)` from `fairband.engine.designation`, `counts_on`.
- Produces: `agent_fields(snapshot, review, secondary, report, cited, today, edges)` returns, beside the four keys, `"levels"`: `None`, or `{"fairValue", "fairLow", "fairHigh", "buyLevel", "trimLevel", "priceToValue", "designation"}` of the record that fills `reviewed`, price ÷ value and its word at `snapshot.price` on `edges` (both `None` without a positive price). `screen_row` writes those seven keys from `agents["levels"]` when it is not `None`, else from the snapshot as today; `mechanical` stays `snapshot.value`.

- [ ] **Step 1: Write the failing tests**

```python
def test_a_counting_review_sets_the_rows_levels(valued_snapshot_at_100, review_at_120):
    fields = agent_fields(valued_snapshot_at_100, review_at_120, None, None, {}, TODAY, EDGES)
    assert fields["reviewed"] == 120.0
    assert fields["levels"] == {"fairValue": 120.0, "fairLow": review_at_120.fair_low, ...,
                                "priceToValue": pytest.approx(price / 120.0), "designation": designation_for(price, 120.0, EDGES)[1]}
    row = screen_row(valued_snapshot_at_100, None, TODAY, 0.6667, [], fields)
    assert row["fairValue"] == 120.0 and row["buyLevel"] == review_at_120.buy_level
    assert row["mechanical"] == 100.0 and row["designation"] == fields["levels"]["designation"]

def test_a_refused_review_leaves_the_engines_levels(...):  # Review Focus 3
def test_a_refused_rows_secondary_sets_the_levels(...):   # the secondary's levels and its word at the latest price
def test_a_revalued_row_returns_to_the_engines_levels(...):  # Review Focus 2: the secondary no longer counts
```

`tests/web/test_app.py`: the pin on `meter` names a `review` branch on a valued row that draws `review.levels` and `review.value` with a caption ending in `' · mechanical ' + F.formatMoney(r.value)`, and no `reviewedValue` on the mechanical branch.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_rows.py tests/web/test_app.py -q -k "levels or meter"`
Expected: FAIL (`agent_fields` takes no edges; the row keeps the snapshot's levels; the pin misses).

- [ ] **Step 3: Implement**

`agent_fields`: when the review fills `reviewed`, `levels` from the review's four levels and value, `priceToValue` and `designation` by `designation_for(snapshot.price, review.value, edges)` when `snapshot.price` is above zero, else `None` for both; when the secondary fills it, the same from the secondary's; else `None`. `NO_AGENT_FIELDS` gains `"levels": None`. `screen_row` overlays the seven keys. The research read already computes the review's word at the latest price (`_review`); do not duplicate. `app.js` `meter`: on a valued row with `review && review.value != null && review.levels`, draw the review's band (`low/high/fairValue/buyLevel/trimLevel/designation` from the review) with `caption: reviewCaption(review, edges) + ' · mechanical ' + F.formatMoney(r.value)`, `showScale: false`; else the mechanical band without `reviewedValue`. The refused-row branches stay. `report.js` draws through `P.meter`, so nothing changes there; its `headline` stays. `index.d.ts`: the row's `fairValue`/levels note says they follow the reviewed value where `reviewed` is filled (spec 18.1, plan 3). `methodology.html` "Where to read them": after the Reviewed sentence, "The band, the buy and trim levels and the designation follow the reviewed value; the Mechanical column keeps the engine's value." `docs/method.md` 14.5: one sentence that the screen's row and the meters show the review's levels and the designation at the latest price where the review fills the row (spec 18.1), the mechanical value kept beside; the versions row gains "the row's levels from the reviewed value (14.5)".

- [ ] **Step 4: Run the whole check and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

```bash
git add -A src tests docs/method.md
git commit -m "Let the row's band, levels and designation follow the reviewed value, draw the review's band on the meters, and keep the engine's value in the Mechanical column"
```

---

### Task 4: The reader renders the text as the agent wrote it

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (`ReportReader`, near line 732: the section body)
- Modify: `src/fairband/web/static/design-system/components/bundle.css` (near line 655: `.fb-report__prose` and the new block classes)
- Modify: `src/fairband/web/static/design-system/components/index.d.ts` (`ReportSection`'s part note; `ReportReaderProps` doc)
- Modify: `src/fairband/web/static/index.html` (the print stylesheet: a table and a list item do not break across pages)
- Modify: `src/fairband/reports/check.py` (`_NOT_QUANTITIES`: a line-leading list mark; the docstring's token rule near line 46)
- Modify: `docs/method.md` (16.3's quantity definition: "a list's leading number at a line's start and a table's separator row are marks, not quantities"; the versions row of Task 1 gains its clause)
- Create: `tests/web/reader_blocks.mjs` (a node harness in the shape of the smoke renders of plan 2: a stub `React.createElement` that builds a tree, the bundle loaded with `new Function('window', 'React', src)`, a renderer to an HTML string)
- Test: `tests/web/test_reader_blocks.py` (runs node on the harness; `pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")`), `tests/web/test_app.py` (a text pin on the patch), `tests/reports/test_check.py`

**Interfaces:**
- Consumes: `sections[i].parts`, strings and `{cite, ref, period?}`; `footnotes` (ref → n); `charts` by heading.
- Produces: the reader renders, per section, a sequence of blocks: `<p class="fb-report__prose body">`, `<ul class="fb-report__list body">`/`<ol class="fb-report__list body" start="n">` with `<li>`, `<div class="fb-report__scroll"><table class="fb-report__table"><thead><tr><th class="label">…` and `<tbody>` rows with `<td class="body">`, and `<strong>` inside any of them; a cite and its `[n]` superscript inline in any block. The drawer's Summary gets the same rendering with no change in `app.js`.

- [ ] **Step 1: Write the failing tests**

`tests/web/test_reader_blocks.py` renders one section whose parts are:

```python
PARTS = [
    "Stance: hold.\n\nThe price of ", {"cite": "$173.19", "ref": "snapshot:1/price"},
    " is below the buy level.\n\nReasons for:\n\n1. Licensing renewed.\n2. Cars grew ",
    {"cite": "51.7%", "ref": "table:QCOM/growth/revenue_growth/2026"}, ".\n\n",
    "| | The quarter | A year before |\n|---|---|---|\n| Revenue | ",
    {"cite": "$10.44 billion", "ref": "fact:QCOM/revenue/2026Q4"}, " | $11.27 billion |\n\n",
    "**The verdict.** The call confirmed the thesis. A lone * stays. A price | value sentence stays prose.",
]
```

and asserts on the HTML: three `<p` before the list; `<ol class="fb-report__list body" start="1">` with two `<li>`, the second holding the cite's `<span class="fb-cite` and `<sup class="fb-cite__n">[2]</sup>`; one `<table class="fb-report__table">` with `<th class="label">The quarter</th>` in `<thead>` and the cite inside a `<td`; no `|---|` text; `<strong>The verdict.</strong>` at the start of the last paragraph; the literal `*` kept; the sentence with `|` inside a `<p` and not a table. With `footnotes` `{"snapshot:1/price": 1, "table:QCOM/growth/revenue_growth/2026": 2}`.

`tests/reports/test_check.py`: a plain part with lines `1. ` to `12. ` and a `|---|---|` row and `**bold**` has no "a number with no reference" finding; `12 analysts` in a sentence still has one.

`tests/web/test_app.py`: a pin that `bundle.js` names `// fairband:` with "13.1" on a function `blocks(` in `ReportReader`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_reader_blocks.py tests/reports/test_check.py tests/web/test_app.py -q -k "blocks or marks or reader"`
Expected: FAIL (one `<p>`; the check flags `10.`).

- [ ] **Step 3: Implement**

In `ReportReader`, replace the one `h('p', …)` with `blocks(s.parts, footnotes)`: walk the parts into lines (a string part splits on `\n`, each piece appended to the current line, a `\n` closing it; a cite part appends an inline node); then group lines into blocks: a blank line closes the block; a line matching `/^\s*[-•] /` opens or extends a bullet list; `/^\s*(\d{1,2})[.)] /` a numbered list whose `start` is the first item's number; a line whose first non-space character is `|` and that holds a second `|` a table row (a row whose cells are all `-` or `:` is the separator and sets the header; cells split on `|` within string pieces, cites staying in their cell); any other line joins the current paragraph with a space. Inline: a `**` toggles `<strong>` across the line's nodes, an unpaired `**` or a lone `*` stays text. Keep `Cite` and the `[n]` superscript as they are. Comment the patch `// fairband: the section's text as blocks … (spec 2026-11-06 Tier 2, 13.1 and 18.4)`. CSS: `.fb-report__list { margin: 0 0 var(--space-2); padding-left: 1.25em; max-width: 72ch; }`, `.fb-report__prose + .fb-report__prose, .fb-report__list + .fb-report__prose { margin-top: var(--space-2) }`, `.fb-report__scroll { overflow-x: auto; margin: 0 0 var(--space-2) }`, `.fb-report__table { border-collapse: collapse } .fb-report__table th, td { padding: var(--space-1) var(--space-2); border-bottom: 1px solid var(--line) ; text-align: left; vertical-align: top }`, `.fb-report strong { color: var(--ink); font-weight: 600 }`; use the bundle's existing tokens (read `bundle.css` for the line and space names in use). `index.html` print: `.fb-report__table, .fb-report__list li { break-inside: avoid }`. `check.py`: add `(?m)^\s*\d{1,2}[.)]\s` to `_NOT_QUANTITIES` and say so in the docstring; `docs/method.md` 16.3 the same sentence; the versions row gains "the list mark and the table row in the check (16.3)".

- [ ] **Step 4: Run the whole check, open the page once and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass. Then start a server on a scratch database with a published report whose sections hold a list and a table (the fixtures' way), open `#report/<symbol>` in headless Chromium or read the rendered HTML through node, and note in the task report that the list, the table and the bold render and that the drawer's Summary does too; stop the server.

```bash
git add -A src tests docs/method.md
git commit -m "Render a report's text as the agent wrote it, paragraphs, lists, tables and bold from the parts with the cites inline, and read a list's number as a mark in the check"
```

---

### Task 5: Finish, restart and hand QCOM back (the controller)

- [ ] **Step 1: Finish the branch** with superpowers:finishing-a-development-branch: the whole-branch review, one fix wave, the merge to main, the push.
- [ ] **Step 2: Backlog and spec.** Rows for the agent's four gaps from the first session: the stock-pay test in `engine/anchor.py` reads GAAP trailing EPS as reported, so a large one-time gain turns the charge off and only an override corrects it; the stored trailing stock pay can lag the release's figure and no override corrects it; the stored closes end on the call day when the call is after the close, so the next-day move needs the next price refresh; FMP's revenue split by region can end years early. B-9's row notes the first live session and plan 3; the spec's status line says plan 3 merged.
- [ ] **Step 3: Restart the server** from main on 8470 (`setsid nohup uv run python -m fairband serve >> ~/.local/share/fairband/server.log 2>&1` from the repository root), check the screen, the QCOM drawer (the review's band, the levels from the review) and the report page (report 1 renders its lists and tables).
- [ ] **Step 4: The founder's second run.** The founder posts a new full-report item on QCOM; the agent's report (revision 2) has no secondary valuation and a stance read against the reviewed value's levels. The readout per spec 22.
