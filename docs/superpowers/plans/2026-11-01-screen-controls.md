# Screen Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The page gets the design system's 2026-11-01 build: the 44px header with the mark, one run bar during a refresh, the FIND field and the Filters menu on the screen, and columns the reader can drag into an order that is kept.

**Architecture:** The package's static copy of the design system moves to the new export, with the repository's own patches re-applied on top. `controls.js` mounts `AppHeader` with the views, the engine stamp and the refresh controls, and the full `RunProgress` on the status line from the existing poll. `app.js` narrows the loaded rows for the query and the filters and hands `ScreenTable` the controls' state. The repository's copy of `ScreenTable` gains ordered columns and a header drag. No server change.

**Tech Stack:** The vendored React 18 and the design-system bundle (classic scripts, no JSX, no build step); FastAPI serves them. Tests are Python file-content assertions in `tests/web/test_app.py`, as the repository does today.

**Spec:** `docs/superpowers/specs/2026-11-01-screen-controls-design.md`. Design rules: the brand book and the component notes inside `docs/design-system/fairband-design-system_4.tar.gz` (`fairband-design-system/docs/brand-book.md`, `docs/components/AppHeader.md`, `RunProgress.md`, `ScreenTable.md`, `assets/Logos/README.md`), read with `tar -xzOf`.

## Global Constraints

- `uv run` for every command; before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- No JSX, no bundler, no Node: `React.createElement` against `window.Fairband`, as `app.js` and `controls.js` do today.
- Every change to the exported `bundle.js` carries a `// fairband:` comment; `test_bundle_patches_marked` counts them.
- Colours, sizes and radii come from the tokens (`var(--…)`); never a hard-coded value. The header is 44px (`--header-height`) and not sticky.
- Controls are named by words, never a glyph: `FIND`, `Filters ▾`, `Columns ▾`, `Refresh prices`, `Refresh all`, `Cancel`.
- The run bar is determinate: no spinner, no percentage, no estimate; zero counts are left out; the table keeps its figures at `ink-faint` during a run.
- The page makes no request off the machine: every reference is `/static/...` (`test_static_design_system_served_offline`).
- Archive 4 is committed under `docs/design-system/`; archive 2 stays. `*:Zone.Identifier` files are ignored, never committed.
- Commit messages: one plain sentence in the imperative; every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Work on the iteration's branch, after the calibration plan's tasks.

## Review Focus

Inputs the spec implies but no acceptance line covers. Each has its test in the task named.

1. **A saved column list from before this change** (no order meaning, or missing a locked key) must load without an error and show Ticker first and Price last. Test in Task 5 (`test_app_js_normalises_a_saved_column_list`).
2. **A poll body with `remaining` only** (the first report of a stage: `done` 0, `failed` 0) must show the stage word and no bar, not a bar at zero or a crash on `total` 0. Test in Task 3 (`test_controls_js_handles_a_zero_total`).
3. **A row with no sector or no cap band** (a placeholder row) must stay visible with no filter active and drop out only when a sector or cap filter is active. Test in Task 4 (`test_app_js_filter_rule_handles_missing_fields`).
4. **A query with surrounding spaces or capitals** (`" aap "`) must match the same rows as `aap`. Test in Task 4 (`test_app_js_query_is_trimmed_and_lower_cased`).
5. **The `.fb-mark` freshness glyph** must still render after the upgrade (the first November build collided with the logo class). Test in Task 1 (`test_bundle_keeps_the_freshness_glyph_class`).

---

## File structure

```
docs/design-system/fairband-design-system_4.tar.gz   committed (was untracked)
.gitignore                                           + *:Zone.Identifier
CLAUDE.md                                            brand-book pointer → archive 4
src/fairband/web/static/
  design-system/tokens/tokens.json, tokens.css       replaced (v4)
  design-system/components/bundle.css, bundle.js     replaced (v4) + the repository's patches
  design-system/components/index.d.ts                replaced (v4) + onSort/onOpen + ordered columns note
  design-system/assets/Logos/*.svg, README.md        added
  index.html                                         header mount, favicon, no h1, no tabs
  controls.js                                        AppHeader, RunProgress, Cancel swap
  app.js                                             query, filters, narrowing, column normalisation
tests/web/test_app.py                                new file-content and static tests
```

---

### Task 1: The design system upgrade to the 2026-11-01 build

**Files:**
- Modify: `src/fairband/web/static/design-system/{tokens,components}/…`, `.gitignore`, `CLAUDE.md`
- Create: `src/fairband/web/static/design-system/assets/Logos/` (four SVGs and `README.md`)
- Commit: `docs/design-system/fairband-design-system_4.tar.gz`
- Test: `tests/web/test_app.py`

**Interfaces:**
- Produces: `window.Fairband.AppHeader`, `RunProgress`, `Mark`, `CAPS`, `SECTORS`, `EMPTY_FILTERS`, `formatDate` (timestamps as `29 Oct 2026, 03:12`), `ScreenTable` with `query`, `onQueryChange`, `filters`, `onFiltersChange`, `sectors`, `total`; the token `--header-height: 44px`; the static path `/static/design-system/assets/Logos/mark-on-dark.svg`.
- Keeps: every `key: '<name>', head: '<head>'` of `EXTRA_COLUMN_HEADS` (including `growthRouteValue` from the calibration plan), `onSort`, `onOpen`, the null-phase dash, the no-levels stance dash, the timestamp date, `formatPercent`, the `.fb-mark` freshness glyph.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_app.py`:

```python
def test_bundle_is_the_november_build() -> None:
    bundle = _component_file("bundle.js")
    for name in ("AppHeader", "RunProgress", "Mark", "CAPS", "SECTORS", "EMPTY_FILTERS"):
        assert f"{name}: {name}" in bundle, name  # exported on window.Fairband
    assert "'fb-logo" in bundle and "'fb-screen__find'" in bundle
    tokens = resources.files("fairband.web").joinpath("static/design-system/tokens/tokens.css").read_text()
    assert "--header-height: 44px;" in tokens

def test_bundle_keeps_the_freshness_glyph_class() -> None:
    bundle = _component_file("bundle.js")
    assert "className: 'fb-mark fb-mark--' + f" in bundle
    css = _component_file("bundle.css")
    assert ".fb-mark--aging" in css and ".fb-logo" in css

def test_logos_served(client: TestClient) -> None:
    for name in ("mark-on-dark.svg", "mark-on-light.svg", "mark-one-ink-on-dark.svg", "mark-one-ink-on-light.svg"):
        response = client.get(f"/static/design-system/assets/Logos/{name}")
        assert response.status_code == 200 and response.headers["content-type"].startswith("image/svg"), name
```

Raise the count in `test_bundle_patches_marked` to `>= 8` (the hunks: timestamp, null phase, formats, extra columns, stance, onSort, onOpen, formatPercent).

- [ ] **Step 2: Run** `uv run pytest tests/web -q -k "november or glyph or logos"`. Expected: FAIL.

- [ ] **Step 3: Save the repository's patches**: in the scratchpad, extract the 29 October export's `bundle.js` (`tar -xzOf docs/design-system/fairband-design-system_2.tar.gz fairband-design-system/components/bundle.js > v2.js`) and write `diff -u v2.js src/fairband/web/static/design-system/components/bundle.js > patches.diff`; also `diff -u` the two `index.d.ts` files. Read `patches.diff` once: eight hunks on `bundle.js`, each with a `// fairband:` line.

- [ ] **Step 4: Replace the files**: extract from archive 4 into the static directory `tokens/tokens.json`, `tokens/tokens.css`, `components/bundle.css`, `components/bundle.js`, `components/index.d.ts`, and `assets/Logos/{mark-on-dark,mark-on-light,mark-one-ink-on-dark,mark-one-ink-on-light}.svg` and `assets/Logos/README.md` (not the PNG covers). `fonts/` and `tokens/build_tokens.py` are identical between the exports; leave them.

- [ ] **Step 5: Re-apply the patches**: `patch src/fairband/web/static/design-system/components/bundle.js patches.diff` (fuzz is expected on the hunks near `ScreenTable`'s bar; resolve any reject by hand, keeping the `// fairband:` lines). Same for `index.d.ts` (the `onSort` and `onOpen` declarations inside `ScreenTableProps`). Check `git diff --stat` shows only the design-system files.

- [ ] **Step 6: Repository hygiene**: `git add docs/design-system/fairband-design-system_4.tar.gz`; add `*:Zone.Identifier` to `.gitignore`; in `CLAUDE.md` change the brand-book line to archive 4 (`fairband-design-system_4.tar.gz`, same inner path).

- [ ] **Step 7: Run** `uv run pytest tests/web -q`. Expected: PASS (the existing column, patch and offline tests included). Open `previews/gallery.html` from the archive is not needed; the page's own check is Task 6.

- [ ] **Step 8: Commit**: `git commit -am "Move the design system to its 2026-11-01 build and re-apply the repository's patches"` (plus the added files).

---

### Task 2: The header

**Files:**
- Modify: `src/fairband/web/static/index.html`, `src/fairband/web/static/controls.js`
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `Fairband.AppHeader({ views, view, onViewChange, engineRanAt, children })`, `Fairband.Button`.
- Produces: `index.html` with `<div id="header"></div>` as the first child of `main`, no `<h1>`, no tab buttons, `<link rel="icon" href="/static/design-system/assets/Logos/mark-on-dark.svg" type="image/svg+xml">` in `<head>`; `controls.js` renders the header into `#header` on every `render()` with `views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' }]`, `view: state.tab`, `onViewChange: show`, `engineRanAt: state.last && state.last.finishedAt` when no run is alive (the latest refresh's finish, whatever its status), and `children`: the two refresh buttons (`size: 'sm'`) while no run is alive, else one `Cancel` (`variant: 'quiet'`, `size: 'sm'`, disabled once a cancel was asked). The `.app-tabs`, `.app-tab` and `.app-name` CSS and the `h1` go; the `.app-bar` keeps the status and notice lines.

- [ ] **Step 1: Write the failing tests**:

```python
def test_index_mounts_the_header_and_the_favicon(client: TestClient) -> None:
    page = client.get("/").text
    assert "<h1" not in page and 'role="tab"' not in page
    assert 'id="header"' in page
    assert '<link rel="icon" href="/static/design-system/assets/Logos/mark-on-dark.svg"' in page

def test_controls_js_mounts_app_header() -> None:
    script = _static_file("controls.js")
    assert "h(F.AppHeader, {" in script
    assert "views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' }]" in script
    assert "engineRanAt:" in script and "onViewChange: show" in script
```

Add `_static_file(name)` beside `_component_file`, reading `fairband.web/static/<name>`. In `test_static_design_system_served_offline`, insert the favicon path first in the expected `references.urls` list (the parser collects every `href`).

- [ ] **Step 2: Run** `uv run pytest tests/web -q -k "header or offline"`. Expected: FAIL.

- [ ] **Step 3: Implement** as in Interfaces. The header's root is a second `ReactDOM.createRoot` in `controls.js` (`#header`); `render()` renders it and the bar. The cancel-asked state: a `cancelAsked` flag set in `cancel()`'s `onOk`, cleared when the run ends.

- [ ] **Step 4: Run** `uv run pytest tests/web -q`. Expected: PASS.

- [ ] **Step 5: Commit**: `git commit -am "Put the design system's header on the page with the views, the engine stamp and the refresh controls"`.

---

### Task 3: The run bar

**Files:**
- Modify: `src/fairband/web/static/controls.js`, `src/fairband/web/static/index.html` (the `.app-status` CSS, if the bar needs a block)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `Fairband.RunProgress({ total, done, failed, stage })`; the poll body `{ refresh: { kind, stage, done, failed, remaining, current } }`.
- Produces, in `controls.js`: `var STAGE_WORDS = { universe: 'reading the universe', deciles: 'ranking', fetch: 'fetching', value: 'valuing', quotes: 'fetching prices', reprice: 'repricing', done: 'finishing' };` and `function runProps(r)` returning `{ total, done, failed, stage }` where `stage = STAGE_WORDS[r.stage] || r.stage`; for `r.stage` of `universe` or `deciles`: `total = r.done + r.failed + r.remaining`, `done = 0`; otherwise `total = r.done + r.failed + r.remaining`, `done = r.done`; `failed = r.failed`. While a run is alive the status line renders `h(F.RunProgress, runProps(state.running))` when `total > 0`, else a `caption` with the stage word alone; `progressLine` goes. The header gets no `run` prop (spec 4.2).

- [ ] **Step 1: Write the failing tests**:

```python
def test_controls_js_run_bar() -> None:
    script = _static_file("controls.js")
    assert "h(F.RunProgress, runProps(state.running))" in script
    for stage, word in (("universe", "reading the universe"), ("deciles", "ranking"), ("fetch", "fetching"),
                        ("value", "valuing"), ("quotes", "fetching prices"), ("reprice", "repricing"), ("done", "finishing")):
        assert f"{stage}: '{word}'" in script, stage
    assert "progressLine" not in script
    assert "run:" not in script.split("h(F.AppHeader, {")[1].split("})")[0]  # the header gets no run prop

def test_controls_js_handles_a_zero_total() -> None:
    script = _static_file("controls.js")
    assert "total > 0 ? h(F.RunProgress" in script or "props.total > 0 ? h(F.RunProgress" in script
    assert "done: 0" in script  # the universe and deciles stages show nothing done
```

- [ ] **Step 2: Run** `uv run pytest tests/web -q -k run_bar`. Expected: FAIL.

- [ ] **Step 3: Implement** as in Interfaces. The old `progressLine` text is removed; the last-refresh line and the notice stay.

- [ ] **Step 4: Run** `uv run pytest tests/web -q`. Expected: PASS.

- [ ] **Step 5: Commit**: `git commit -am "Show one run bar on the status line from the refresh poll"`.

---

### Task 4: Find and filters

**Files:**
- Modify: `src/fairband/web/static/app.js`
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `ScreenTable`'s `query`, `onQueryChange`, `filters`, `onFiltersChange`, `sectors`, `total`; `Fairband.EMPTY_FILTERS`; `PHASE_NUMBER` (in `app.js`).
- Produces, in `app.js`: `state.query = ''`, `state.filters = F.EMPTY_FILTERS`; `function stanceOf(r)` (`null` without price or levels; else `buy` below the buy level, `trim` at or above the trim level, else `hold`, the bundle's rule); `function narrow(rows, query, filters)` with the design system's reference rule: `needle = (query || '').trim().toLowerCase()`; a row passes when (`needle` is empty or `r.ticker.toLowerCase()` starts with it or `(r.name || '').toLowerCase()` contains it) and for each group with a non-empty list the row's value is in it (`stance`: `stanceOf(r)`; `phase`: `r.phase`; `cap`: `(r.capBand || '').toLowerCase()`; `sector`: `r.sector`) and (`!filters.reviewedOnly || r.reviewed != null`) and (`!filters.hideExpired || r.freshness !== 'expired'`); `function sectorsOf(rows)` the sorted distinct non-null sectors. `render()` passes `rows: narrow(...)`, `total: state.rows.length`, `query`, `onQueryChange`, `filters`, `onFiltersChange`, `sectors: sectorsOf(state.rows)`, and drops `footnote`. The "No snapshots yet" note stays for an empty load; a narrowing that leaves no row renders the table with its bar (`0 of 1,759 · Clear`).

- [ ] **Step 1: Write the failing tests**:

```python
def test_app_js_find_and_filters() -> None:
    script = _static_file("app.js")
    for prop in ("query: state.query", "onQueryChange:", "filters: state.filters", "onFiltersChange:",
                 "sectors: sectorsOf(state.rows)", "total: state.rows.length"):
        assert prop in script, prop
    assert "footnote" not in script

def test_app_js_query_is_trimmed_and_lower_cased() -> None:
    script = _static_file("app.js")
    assert "(query || '').trim().toLowerCase()" in script
    assert "r.ticker.toLowerCase().indexOf(needle) === 0" in script
    assert "(r.name || '').toLowerCase().indexOf(needle) !== -1" in script

def test_app_js_filter_rule_handles_missing_fields() -> None:
    script = _static_file("app.js")
    assert "(r.capBand || '').toLowerCase()" in script
    assert "if (r.price == null || r.buyLevel == null || r.trimLevel == null) return null;" in script
```

- [ ] **Step 2: Run** `uv run pytest tests/web -q -k "find or query or missing_fields"`. Expected: FAIL.

- [ ] **Step 3: Implement** as in Interfaces; the sort stays on the server and `narrow` runs on the sorted rows.

- [ ] **Step 4: Run** `uv run pytest tests/web -q`. Expected: PASS.

- [ ] **Step 5: Commit**: `git commit -am "Add the FIND field and the Filters menu to the screen, narrowing the loaded rows in the page"`.

---

### Task 5: Column order

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (the repository's `ScreenTable`), `components/bundle.css` (the drop edge), `components/index.d.ts`, `src/fairband/web/static/app.js`
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `ScreenTable`'s `columns` and `onColumnsChange`; `localStorage["fairband.columns"]`.
- Produces, in `bundle.js` (each change `// fairband:` marked):
  - `shown` is `visible.map(key → the COLUMNS entry)` filtered to known keys, in list order; a locked column absent from the list is appended (`ticker` first, `price` last) so the table never loses them.
  - each header cell gets `draggable: p.onColumnsChange ? true : null`, `onDragStart` (stores the key on the drag state and `event.dataTransfer`), `onDragOver` (prevents default; marks the target with the class `is-drop`), `onDragLeave`, `onDrop` (calls `p.onColumnsChange(moved(visible, from, to))` where `moved` removes `from` and inserts it at `to`'s index), `onDragEnd` (clears the drag state and the mark). A drop sets a flag that the next `onClick` of the same cell consumes without sorting.
  - the `Columns ▾` menu lists `shown`'s keys in table order, then the unchosen catalog entries in catalog order; `Reset to the default eight` passes `DEFAULT_COLUMNS.slice()`.
  - `bundle.css`: `.fb-table thead th.is-drop { box-shadow: inset 2px 0 0 var(--accent); }` and `.fb-table thead th[draggable="true"] { cursor: grab; }`.
  - `index.d.ts`: on `columns`: "fairband: ordered; the table renders in this order and a header drop calls `onColumnsChange` with the new order".
- Produces, in `app.js`: `loadColumns()` normalises: keeps only known keys (`F.DEFAULT_COLUMNS` ∪ the extra keys the bundle defines; read them from `F.COLUMN_KEYS`, a new export `COLUMN_KEYS: COLUMNS.map(c => c.key)` in the bundle, `// fairband:` marked), puts `ticker` first when missing and `price` last when missing; the saved list's order is the column order.

- [ ] **Step 1: Write the failing tests**:

```python
def test_bundle_orders_columns_by_the_list() -> None:
    bundle = _component_file("bundle.js")
    assert "var shown = visible.map(function (key) {" in bundle
    assert "draggable: p.onColumnsChange ? true : null" in bundle
    assert "p.onColumnsChange(moved(visible, " in bundle
    assert "COLUMN_KEYS: COLUMNS.map(function (c) { return c.key; })" in bundle
    assert bundle.count("// fairband:") >= 10
    css = _component_file("bundle.css")
    assert "th.is-drop { box-shadow: inset 2px 0 0 var(--accent); }" in css

def test_index_d_ts_says_columns_are_ordered() -> None:
    declarations = _component_file("index.d.ts")
    assert "fairband: ordered" in declarations

def test_app_js_normalises_a_saved_column_list() -> None:
    script = _static_file("app.js")
    assert "function normalise(columns)" in script
    assert "F.COLUMN_KEYS" in script
    assert "if (kept.indexOf('ticker') === -1) kept.unshift('ticker');" in script
    assert "if (kept.indexOf('price') === -1) kept.push('price');" in script
```

- [ ] **Step 2: Run** `uv run pytest tests/web -q -k "orders_columns or ordered or normalises"`. Expected: FAIL.

- [ ] **Step 3: Implement** as in Interfaces. Keep the drag state in a `React.useRef` inside `ScreenTable`. No animation: the only visual change during a drag is the drop edge.

- [ ] **Step 4: Run** `uv run pytest tests/web -q`. Expected: PASS.

- [ ] **Step 5: Commit**: `git commit -am "Let the reader drag a column to a new place and keep the order with the chosen columns"`.

---

### Task 6: Hand check on the running page

**Files:** none.

- [ ] **Step 1:** `uv run python -m fairband serve` (with the keys file in place) and open `http://127.0.0.1:8470`.
- [ ] **Step 2:** Check, against spec section 6: the lockup in a 44px header with `Screen` and `Groups` and the engine stamp; `Refresh prices` then `Cancel` in the header while the run is alive, the bar on the status line with the stage word and the counts, the table faded; after the run, the stamp and the buttons return and the rows reload; `FIND` with `aap`; the Filters menu with Mega and Technology, the chips and `Clear`; dragging `Phase` onto `Price`, then a reload. Note anything off for the founder; fix a defect in the task that owns it before the final review.

---

## Self-review notes

- Spec coverage: 4.1 → Task 1; 4.2 → Task 2; 4.3 → Task 3; 4.4 → Task 4; 4.5 → Task 5; 4.6 → Tasks 2 and 3; 6 → Tasks 1 to 5 (tests) and Task 6 (the page).
- Names used across tasks: `_static_file` (Task 2) in Tasks 3 to 5; `F.COLUMN_KEYS` (Task 5) read by `app.js` in the same task; `runProps` and `STAGE_WORDS` (Task 3) in `controls.js` only.
- The tests are file-content assertions because the repository runs no JavaScript; Task 6 is the behaviour check. The strings the tests pin are the ones the implementer writes; an implementer who writes an equivalent line changes the assertion to match, not the behaviour.
- Task 1 runs after the calibration plan's Task 5, so the `growthRouteValue` column is among the patches re-applied.
- Review Focus: each line names its test and task.
