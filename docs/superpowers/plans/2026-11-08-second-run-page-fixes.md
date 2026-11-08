# Second Run Page Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the five page faults the founder found on the second QCOM run: no `Request research` on a company with a report, a one-point forward P/E chart, text too small to read at ease, an Inbox note with no form, and labels that collide or name things by date alone.

**Architecture:** Five small changes to the page scripts (`app.js`, `report.js`, `inbox.js`, `charts.js`), two `// fairband:` patches to the design system's bundle (`BandMeter`'s head text and its tier labels; the reader's type size), one field on the inbox read, and one sentence in the playbook and the MCP tool. No engine, method or policy change. The page scripts are pinned by text in `tests/web/test_app.py`; the bundle's components render in node through `tests/web/render.mjs` (today `reader_blocks.mjs`).

**Tech Stack:** Python 3.13, FastAPI, plain JS on the vendored React design-system bundle, node for the bundle tests, pytest.

**Spec:** `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md`, amended 2026-11-08 for plan 4: sections 8 (the note's form), 13.7 (a short forward log), 18.2 items 2 and 4 (the meter's head and labels; `Request research` with a report), 18.4 (the revisions line, `Request research`, the reader's size, the chart row), 18.5 (the Inbox's columns), and the decision log's last row. Backlog items B-120 to B-124; B-125 was ruled by the founder (keep origin `agent`) and needs no code.

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`. The suite is green at the base (2,113 tests).
- The commit message is one plain sentence in the imperative, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01K4pNFGMWqnrPuvG88Nf31f`.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic. The live database (`~/.local/share/fairband`), the keys file and the live server on port 8470 are off limits: no request of any kind. Never push.
- `docs/method.md` and the Methodology page do not change: nothing here touches the engine, the classifier, the universe rule or a policy value. The spec is already amended; a task that finds the spec and the code in conflict stops and reports it.
- A change to the bundle (`src/fairband/web/static/design-system/components/bundle.js`, `bundle.css`) is marked with a `// fairband:` (or `/* fairband: */`) comment naming the spec section, and `index.d.ts` changes in the same commit for a new prop.
- The page's copy is plain English in the spec's words; the wording pinned in a task is used verbatim.
- Node tests skip when node is not installed (`pytest.mark.skipif(NODE is None, ...)`), as `tests/web/test_reader_blocks.py` does.

## Review Focus

1. A company with a report and an open item: `Request research` is disabled while the item is open and the open item's line ("Requested · pending" or "claimed by <actor>") shows under it, exactly as on a company without a report. Pinned in Task 1.
2. The price marker on a level label's own position (distance zero): the label anchors to the after side, never left centred under the dot. Pinned in Task 3's node test.
3. A forward log of exactly five readings draws the line; four readings show the figure. Pinned in Task 5.
4. An Inbox item marked done whose report row is missing: `reportRevision` is null and the link still reads `Open`. Pinned in Task 4.
5. A `BandMeter` caller that passes no `gap` keeps the design system's derived head text ("17.8% below fair value"), so nothing else that draws the meter changes. Pinned in Task 3's node test.

---

### Task 1: Request research on a company with a report (B-120)

**Files:**
- Modify: `src/fairband/web/static/app.js` (the `sections` function near line 650 and its comment; the `asking` comment near line 1027)
- Modify: `src/fairband/web/static/report.js` (the header comment near line 11; `meta` near line 190; `noReport` near line 522; the `state.request` set-up so it exists with a report too)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `requestResearch(ask, item, redraw, after)` in `app.js` (exported as `P.requestResearch`), `asked(symbol)`, `P.asking(symbol)`.
- Produces: nothing new; the drawer's `sections` and the report page's `meta` both call `requestResearch` whether or not a report exists.

- [ ] **Step 1: Write the failing pins**

In `tests/web/test_app.py`, next to the drawer's and the report page's existing pins (`_function(script, "sections")`, `_function(script, "meta")`):

```python
def test_request_research_shows_with_a_report_too() -> None:
    """Spec 18.2 item 4 and 18.4 (plan 4): Request research with its menu and the open item's line
    on a company with a report, under Open the report in the drawer and under the revisions line
    on the report page, as on a company without one."""
    sections = _function(_code(_static_file("app.js")), "sections")
    assert "section('request', null," in sections
    assert ": section('request', null," not in sections  # no longer the Summary's alternative
    meta = _function(_code(_static_file("report.js")), "meta")
    assert "P.requestResearch(state.request, d.item, render, load)" in meta
    no_report = _function(_code(_static_file("report.js")), "noReport")
    assert "P.requestResearch(state.request, d.item, render, load)" in no_report
```

- [ ] **Step 2: Run the pins to see them fail**

Run: `uv run pytest tests/web/test_app.py -q -k request_research_shows`
Expected: FAIL on the `: section('request'` assertion and the `meta` assertion.

- [ ] **Step 3: Change the drawer**

In `sections(body)`: the report's Summary section (with `Open the report`) stays as it is when a report exists; the `request` section is no longer the Summary's alternative but a section of its own, listed after it in every case:

```js
      report ? section('summary', null, ...) : null,
      section('request', null,
        requestResearch(ask, body.item, render, function () { reloadDetail(r.symbol); })),
```

Update the function's comment: "...then `Open the report`, a link to the report page; then Request research with its menu, the server's refusal under it and the open item's line, with or without a report (plan 4: the founder found none on a company with a report)". Update the `asking` comment: the default mode is `full report` on a company with a report as on one without (the founder asked for a full report on the second run); drop the sentence about a company with no report having no full report to reuse.

- [ ] **Step 4: Change the report page**

In `report.js`, `meta(d, report)` renders `P.requestResearch(state.request, d.item, render, load)` after `revisions(report)` and before the download error line. `noReport` keeps its note and the same call. Make sure `state.request` is set to `P.asking(symbol)` whenever the page loads a company, not only on the no-report path (today `state.request` is described as "for a company with no report"; it is now for the page's company). Update the header comment at the top of the file (the sentence "A company with no report shows the head, the meter and Request research") to say the page shows Request research with or without a report.

- [ ] **Step 5: Run the pins and the web suite**

Run: `uv run pytest tests/web -q`
Expected: all pass, the new test included.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/web/static/app.js src/fairband/web/static/report.js tests/web/test_app.py
git commit -m "Show Request research on a company with a report, in the drawer under Open the report and on the report page under the revisions line"
```

---

### Task 2: The note's form (B-123)

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (the paragraph at lines 56 to 59, "When the user asks for research in chat, post the request first...")
- Modify: `playbook/fairband-research/reference/tools.md` (the `inbox_post` line near line 124)
- Modify: `src/fairband/mcp/server.py` (the `inbox_post` tool's `description`, near line 367)
- Modify: `src/fairband/web/static/app.js` (the `RequestMenu`'s note `placeholder`, near line 1118)
- Test: `tests/test_playbook.py`, `tests/mcp/test_server.py`, `tests/web/test_app.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: the sentence other documents may quote: "the request in the user's own words, on one line, with no commentary and without the mode".

- [ ] **Step 1: Write the failing pins**

```python
# tests/test_playbook.py
def test_the_note_has_one_form() -> None:
    """Spec 8 (plan 4): the note is the request in the user's own words, on one line."""
    skill = SKILL.read_text()
    tools = (REFERENCE / "tools.md").read_text()
    sentence = "the request in the user's own words, on one line, with no commentary and without the mode"
    assert sentence in skill
    assert sentence in tools
    assert "asked in chat on 2026-11-08 (the second run)" in skill  # the counter-example

# tests/mcp/test_server.py, beside the dcf description pin
def test_inbox_post_says_what_the_note_holds() -> None:
    tools = ...  # as the dcf pin reads them
    post = next(t.description or "" for t in tools if t.name == "inbox_post")
    assert "its note the request in the requester's own words on one line" in post

# tests/web/test_app.py
def test_the_request_menu_asks_for_the_request_in_the_owners_words() -> None:
    menu = _function(_code(_static_file("app.js")), "RequestMenu")
    assert "placeholder: 'The request in your words, one line'" in menu
```

Use the file-path names `tests/test_playbook.py` already defines for the skill and its reference directory.

- [ ] **Step 2: Run the pins to see them fail**

Run: `uv run pytest tests/test_playbook.py tests/mcp/test_server.py tests/web/test_app.py -q -k "note_has_one_form or what_the_note_holds or owners_words"`
Expected: FAIL, three tests.

- [ ] **Step 3: Write the sentence in the four places**

- `SKILL.md`, after "Every piece of work has a work item.": "The note is the request in the user's own words, on one line, with no commentary and without the mode: "Complete research on QCOM", not "Complete research on QCOM, asked in chat on 2026-11-08 (the second run)"."
- `tools.md`: "`inbox_post(symbol, mode, note?)`: post a work item for a company; `mode` is `valuation review` or `full report`; `note` is the request in the user's own words, on one line, with no commentary and without the mode."
- `server.py`: `description="Post a work item for a company, its mode valuation review or full report, its note the request in the requester's own words on one line with no commentary."` (one sentence: the suite checks no `". "` inside a description).
- `app.js`: `placeholder: 'The request in your words, one line'`.

- [ ] **Step 4: Run the three files' tests**

Run: `uv run pytest tests/test_playbook.py tests/mcp/test_server.py tests/web/test_app.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add playbook/fairband-research/SKILL.md playbook/fairband-research/reference/tools.md src/fairband/mcp/server.py src/fairband/web/static/app.js tests/test_playbook.py tests/mcp/test_server.py tests/web/test_app.py
git commit -m "Give the work item's note one form, the request in the requester's own words on one line, in the playbook, the inbox_post tool and the drawer's menu"
```

---

### Task 3: The meter's head in one form, and a label anchored off the price marker (B-124 a and d)

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (`BandMeter`, lines 420 to 525)
- Modify: `src/fairband/web/static/design-system/components/bundle.css` (the `.fb-band__tier` rules near line 383)
- Modify: `src/fairband/web/static/design-system/components/index.d.ts` (`BandMeterProps`, line 195 on)
- Modify: `src/fairband/web/static/app.js` (`meter`, near line 743; `standing`, `reviewCaption`, `mechanicalCaption`, `secondaryCaption`, lines 1389 to 1430)
- Rename: `tests/web/reader_blocks.mjs` → `tests/web/render.mjs`, taking the component's name as a third argument (default `ReportReader`); `tests/web/test_reader_blocks.py` points at the new name
- Create: `tests/web/test_band_meter.py`
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `ratioFigure(ratio, edges)` in `app.js` (price ÷ value to two decimals, kept off the policy's edges); `F.formatMoney`.
- Produces: `BandMeter` prop `gap?: string` — when given (including `''`), the head's gap text is it (`''` draws none); when undefined, the derived "17.8% below fair value" as before. The tier label classes `fb-band__tier-label--after` and `fb-band__tier-label--before`. `app.js` helper `gapText(ratio, edges, of)` → `ratioFigure(ratio, edges) + ' × ' + of`, or `''` when `ratio` is null.

- [ ] **Step 1: Generalize the node harness**

`git mv tests/web/reader_blocks.mjs tests/web/render.mjs`. Its usage line becomes `node render.mjs <bundle.js> [Component] < props.json > out.html`; the last line renders `window.Fairband[process.argv[3] || 'ReportReader']`. `tests/web/test_reader_blocks.py` sets `HARNESS = Path(__file__).with_name("render.mjs")`. Run `uv run pytest tests/web/test_reader_blocks.py -q`: still passes.

- [ ] **Step 2: Write the failing node test**

`tests/web/test_band_meter.py`, in the style of `test_reader_blocks.py` (same skip, same subprocess call with `"BandMeter"` as the third argument):

```python
QCOM = {"low": 179.11, "high": 242.32, "price": 173.19, "fairValue": 210.72,
        "buyLevel": 158.04, "trimLevel": 316.08, "designation": "below", "showScale": False}

def test_the_head_says_the_gap_the_caller_gives() -> None:
    html = render({**QCOM, "gap": "0.82 × the reviewed value", "caption": "mechanical $342.38"})
    assert '<span class="fb-band__gap caption">0.82 × the reviewed value</span>' in html
    assert "fair value" not in html
    assert 'class="fb-band__caption caption">mechanical $342.38<' in html

def test_an_empty_gap_draws_no_gap_text() -> None:
    html = render({**QCOM, "gap": ""})
    assert "fb-band__gap" not in html

def test_without_a_gap_the_derived_text_stays() -> None:
    html = render(QCOM)
    assert "17.8% below fair value" in html

def test_a_label_near_the_price_marker_is_anchored_away_from_it() -> None:
    # the price 173.19 sits 1.8% of the axis left of the low label 179.11: the label anchors after
    html = render(QCOM)
    assert 'class="fb-band__tier-label--after"' in html and "$179.11" in html
    assert "fb-band__tier-label--before" not in html
    # the price just above the high label: that label anchors before
    html = render({**QCOM, "price": 245.0, "designation": "above"})
    assert 'class="fb-band__tier-label--before"' in html
    # the price on the label's own position anchors after
    html = render({**QCOM, "price": 179.11})
    assert 'class="fb-band__tier-label--after"' in html
    # a price far from both labels: no anchor class
    html = render({**QCOM, "price": 100.0, "designation": "well-below"})
    assert "fb-band__tier-label--" not in html
```

The `render(props)` helper calls `node render.mjs <bundle.js> BandMeter` with the props as JSON on stdin and returns the HTML.

- [ ] **Step 3: Run it to see it fail**

Run: `uv run pytest tests/web/test_band_meter.py -q`
Expected: FAIL (the gap text is derived; no anchor classes).

- [ ] **Step 4: Patch `BandMeter`**

In `bundle.js`, with `// fairband:` comments naming spec 18.2 item 2 (plan 4):

- `var gap = p.gap === undefined ? pct(Math.abs(toFair) * 100) + (toFair >= 0 ? ' below' : ' above') + ' fair value' : p.gap;` and the head renders the gap span only when `gap` is non-empty.
- A label on the tier (the `low` and `high` spans) within six points of the price: `var near = function (v) { return Math.abs(at(v) - at(price)) < 6; };` and `var anchor = function (v) { return near(v) ? (at(v) >= at(price) ? 'fb-band__tier-label--after' : 'fb-band__tier-label--before') : null; };`, passed as each span's `className`.
- `bundle.css`, after the `.fb-band__tier > span` rule: `.fb-band__tier > span.fb-band__tier-label--after { transform: none; margin-left: 8px; }` and `.fb-band__tier > span.fb-band__tier-label--before { transform: translateX(-100%); margin-left: -8px; }`, with a `/* fairband: */` comment.
- `index.d.ts`: `gap?: string;` on `BandMeterProps`, with a one-line doc: the head's gap text; `''` draws none; undefined keeps the derived percentage.

- [ ] **Step 5: Run the node test**

Run: `uv run pytest tests/web/test_band_meter.py tests/web/test_reader_blocks.py -q`
Expected: PASS.

- [ ] **Step 6: Write the failing pins for the drawer's callers**

In `tests/web/test_app.py`, replacing the pins that assert the old captions ("Above: the price is 1.42 × the reviewed value · mechanical $133.37" and the `mechanicalCaption`/`reviewCaption`/`secondaryCaption` pins; find them with `grep -n "Caption\|× the reviewed value" tests/web/test_app.py`):

```python
def test_the_meter_says_the_ratio_and_the_values_name_once() -> None:
    """Spec 18.2 item 2 (plan 4): the head says price ÷ value and the value's name in one form;
    the caption says only what the head does not."""
    script = _code(_static_file("app.js"))
    meter = _function(script, "meter")
    assert "gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value')" in meter
    assert "gap: gapText(r.price_to_value, body.designationEdges, 'the mechanical value')" in meter
    assert "gap: gapText(secondary.priceToValue, body.designationEdges, 'the secondary valuation')" in meter
    assert "caption: 'mechanical ' + F.formatMoney(r.value)" in meter
    assert meter.count("caption:") == 1  # the other three branches pass none
    gap = _function(script, "gapText")
    assert "ratioFigure(ratio, edges) + ' × ' + of" in gap
    assert "mechanicalCaption" not in script and "secondaryCaption" not in script
```

- [ ] **Step 7: Change the drawer's meter**

In `app.js`:

- `function gapText(ratio, edges, of) { return ratio == null ? '' : ratioFigure(ratio, edges) + ' × ' + of; }` with a comment naming spec 18.2 item 2 (plan 4).
- `meter(body, hero)`: the valued reviewed branch passes `gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value')` and `caption: 'mechanical ' + F.formatMoney(r.value)`; the valued mechanical branch `gap: gapText(r.price_to_value, body.designationEdges, 'the mechanical value')` and no caption; the refused review-band branch `gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value')` and no caption (the bundle adds "reviewed $x" from `reviewedValue`); the secondary branch `gap: gapText(secondary.priceToValue, body.designationEdges, 'the secondary valuation')` and no caption.
- Delete `mechanicalCaption`, `reviewCaption` and `secondaryCaption`. Keep `standing(r, edges, of)` only if something else still calls it (`grep -n "standing(" app.js`); delete it too when nothing does.
- Update `meter`'s comment to the new rule.

- [ ] **Step 8: Run the web suite**

Run: `uv run pytest tests/web -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add src/fairband/web/static/design-system/components/bundle.js src/fairband/web/static/design-system/components/bundle.css src/fairband/web/static/design-system/components/index.d.ts src/fairband/web/static/app.js tests/web/render.mjs tests/web/test_reader_blocks.py tests/web/test_band_meter.py tests/web/test_app.py
git commit -m "Say price ÷ value and the value's name once in the meter's head, keep only the mechanical value in its caption, and anchor a level label away from the price marker"
```

---

### Task 4: Revisions and Inbox items by number and time, and the reader's size (B-124 b and c, B-122)

**Files:**
- Modify: `src/fairband/web/static/report.js` (`revisionLink`, near line 252)
- Modify: `src/fairband/web/static/inbox.js` (`posted`, near line 104; the Report cell in `row`, near line 133)
- Modify: `src/fairband/web/agents_api.py` (the `GET /api/inbox` route, near line 175, and its module docstring)
- Modify: `src/fairband/store/reports.py` (a new `revisions_by_id`)
- Modify: `src/fairband/web/static/design-system/components/bundle.css` (the `.fb-report__prose`, `.fb-report__list` and `.fb-report__table` rules near lines 655 to 676)
- Test: `tests/web/test_agents_api.py`, `tests/web/test_app.py`, `tests/store/test_reports.py` (or the store test file that covers `fairband.store.reports`)

**Interfaces:**
- Consumes: `P.when(iso)` in `app.js` (an instant as "8 Nov 2026, 17:56" in the reader's local time), `P.localIso`.
- Produces: `revisions_by_id(conn, ids: Iterable[int]) -> dict[int, int]` in `store/reports.py` (one query, `SELECT id, revision FROM reports WHERE id IN (...)`, an empty dict for no ids); each item of `GET /api/inbox` gains `reportRevision`: the report's revision, or `null` when the item has no report or its report row is missing.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_agents_api.py, beside test_post_and_list_inbox
def test_the_inbox_names_a_done_items_report_revision(client: TestClient) -> None:
    """Spec 18.5 (plan 4): a done item carries its report's revision; a pending one null."""
    ...  # post an item, publish a report for its symbol, complete the item with it, as the
         # existing tests do; then
    items = client.get("/api/inbox").json()["items"]
    done = next(i for i in items if i["state"] == "done")
    assert done["reportRevision"] == 1
    pending = next(i for i in items if i["state"] == "pending")
    assert pending["reportRevision"] is None

# the store test file for fairband.store.reports
def test_revisions_by_id_reads_one_query_and_skips_missing_ids(conn) -> None:
    ...  # two stored reports with ids a and b, revisions 1 and 2
    assert revisions_by_id(conn, [a, b, 999]) == {a: 1, b: 2}
    assert revisions_by_id(conn, []) == {}

# tests/web/test_app.py
def test_revisions_and_items_are_named_by_number_and_time() -> None:
    """Spec 18.4 and 18.5 (plan 4): two revisions or two items on one day read the same by
    date alone."""
    link = _function(_code(_static_file("report.js")), "revisionLink")
    assert "'revision ' + r.revision + ', ' + P.when(r.createdAt)" in link
    assert "title:" not in link
    inbox = _code(_static_file("inbox.js"))
    assert "P.when(iso)" in _function(inbox, "posted")
    row = _function(inbox, "row")
    assert "item.reportRevision != null ? 'revision ' + item.reportRevision : 'Open'" in row
    assert "'aria-label': 'Open the report for ' + item.symbol" in row

def test_the_reader_is_set_at_sixteen_pixels() -> None:
    """Spec 18.4 (plan 4): the reader's text at 16px on a 24px line, the column 72ch at that size."""
    css = _static_file("design-system/components/bundle.css")
    assert ".fb-report .fb-report__prose, .fb-report .fb-report__list, .fb-report .fb-report__table {\n  font-size: 16px;\n  line-height: 24px;\n}" in css
    assert ".fb-report__prose { margin: 0; max-width: 72ch; color: var(--ink); }" in css
```

`_static_file` reads a path under `src/fairband/web/static`; if it takes a bare name only, add the subdirectory form.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/web/test_agents_api.py tests/web/test_app.py tests/store -q -k "report_revision or revisions_by_id or named_by_number or sixteen"`
Expected: FAIL, four tests.

- [ ] **Step 3: The store helper and the read**

`revisions_by_id` in `store/reports.py` as the Interfaces block says. In `agents_api.py`'s `inbox` route, after reading the items, one call for the done items' report ids, and each item's JSON gains `"reportRevision": found.get(item.report_id)`; the module docstring's sentence on `GET /api/inbox` names the field.

- [ ] **Step 4: The page**

- `report.js` `revisionLink`: the text `'revision ' + r.revision + ', ' + P.when(r.createdAt)`, no `title`; update its comment.
- `inbox.js` `posted(iso)`: `h('time', { dateTime: local, title: local }, P.when(iso))`; the Report cell's link text `item.reportRevision != null ? 'revision ' + item.reportRevision : 'Open'`, the `aria-label` unchanged. Update the two comments.
- `bundle.css`: a two-class rule so it wins over `.body` (14px/20px in `tokens/tokens.css`), placed after the `.fb-report__table td` rule:

```css
/* fairband: the reader's text at 16px on a 24px line (spec 2026-11-06 Tier 2, 18.4, plan 4:
   the founder found 14px too small to read at ease); the 72ch column scales with it. */
.fb-report .fb-report__prose, .fb-report .fb-report__list, .fb-report .fb-report__table {
  font-size: 16px;
  line-height: 24px;
}
```

Check in the bundle that the reader's root carries the class `fb-report` (the `ReportReader` component's outer element); if its class differs, use that class in the rule and in the pin.

- [ ] **Step 5: Run the suites**

Run: `uv run pytest tests/web tests/store -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/web/static/report.js src/fairband/web/static/inbox.js src/fairband/web/agents_api.py src/fairband/store/reports.py src/fairband/web/static/design-system/components/bundle.css tests/web/test_agents_api.py tests/web/test_app.py tests/store
git commit -m "Name a revision and an Inbox item by number and time, carry a done item's report revision in the inbox read, and set the reader's text at 16px"
```

---

### Task 5: A short forward P/E log shown as a figure (B-121)

**Files:**
- Modify: `src/fairband/web/static/charts.js` (`multiples` and `multiple`, lines 255 to 275; `noData` near line 300)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: the multiples read's `peForward` (`{points: [{day, value}], stats, since}`), `F.BasisChip`, `F.formatDate`, the formatter `MultipleHistory` uses for its end label ("17.5x"; find it in the bundle and call the same, or `value.toFixed(1) + 'x'` if it is not exported).
- Produces: `SHORT_LOG = 5` and `shortLog(forward)` in `charts.js`.

- [ ] **Step 1: Write the failing pins**

```python
# tests/web/test_app.py
def test_a_short_forward_log_is_a_figure_not_a_chart() -> None:
    """Spec 13.7 and 18.4 (plan 4): fewer than five readings show the newest as a figure with the
    sentence, no line and no average; five draw the line."""
    script = _code(_static_file("charts.js"))
    assert "var SHORT_LOG = 5;" in script
    multiples = _function(script, "multiples")
    assert "logged.length < SHORT_LOG ? panel('forward', shortLog(forward)) :" in multiples
    short = _function(script, "shortLog")
    assert "'logged since ' + F.formatDate(forward.since) + '; a reading is added at each price refresh'" in short
    assert "F.BasisChip" in short and "average" not in short
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/web/test_app.py -q -k short_forward_log`
Expected: FAIL.

- [ ] **Step 3: Change `multiples`**

In `charts.js`: `var SHORT_LOG = 5;` at the top with the others. In `multiples(read, tables)`: `var logged = forward.points.filter(function (p) { return p.value != null; });` and the forward entry becomes `logged.length < SHORT_LOG ? panel('forward', shortLog(forward)) : multiple('Forward P/E', ...)` as today. `shortLog(forward)` returns a `figure.fb-c` like `noData`: the figcaption with the title `Forward P/E` and the mechanical `BasisChip`; then, when `logged` has a reading, `h('p', { className: 'figure' }, <newest value as "17.5x"> + ' on ' + F.formatDate(newest.day))` where newest is the last logged point; then `h('p', { className: 'caption app-muted' }, 'logged since ' + F.formatDate(forward.since) + '; a reading is added at each price refresh')`. With no reading at all, keep today's `noData` path (the `since` sentence applies only when `forward.since` is set; without it, the caption is `NO_DATA` as today). No table twin for the short log; the Tables toggle leaves it as it is. Update the `multiples` comment.

- [ ] **Step 4: Run the web suite**

Run: `uv run pytest tests/web -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/web/static/charts.js tests/web/test_app.py
git commit -m "Show a forward P/E log of fewer than five readings as the newest reading with its sentence instead of a one-point line"
```

---

### Task 6: The finish (the controller's steps, not a subagent's)

- [ ] **Step 1: Final whole-branch review** (superpowers:requesting-code-review), one fix wave, a clean re-review.
- [ ] **Step 2: Merge to main and push**, per the founder's standing instruction: `git merge --ff-only`, the full check on main, push, remove the worktree and the branch.
- [ ] **Step 3: The backlog.** B-120, B-121, B-122, B-123 and B-124 move to Done with their commits; B-125 moves to Done with the founder's ruling of 2026-11-08, "keep origin `agent`"; the plan's deferred minors and parked findings move in as one row.
- [ ] **Step 4: The live server.** Restart it from main on port 8470, as after plan 3; open QCOM's report page and the Inbox and check the five fixes by eye: `Request research` under `Open the report`; the forward P/E figure with its sentence; the reader at 16px; the meter's head "0.82 × the reviewed value" with the low label clear of the marker; "revision 1, 8 Nov 2026, …" and the Inbox's times and revision names.
- [ ] **Step 5: Memory** and the message to the founder.
