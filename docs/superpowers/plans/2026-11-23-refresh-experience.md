# The Refresh Experience and Five Page Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A refresh of the whole screen darkens and locks the page and ends with a visible signal; the page follows any refresh and shows a review's phase; Groups becomes Statistics in a new menu; the meter takes a fixed scale.

**Architecture:** The server gains three small things: the shown phase on a row and on the detail, the companies a run names with the newest runs, and a statistics route on the Screen's own figures. Everything else is in the page: `controls.js` owns the status reads, the layer and the menu, `app.js` owns the rows and their marks, and the design system's `bundle.js` takes three marked patches (the meter, the changed cell, the price's arrow).

**Tech Stack:** Python 3.13, FastAPI, SQLite; React 18 without a build step (`web/static/*.js`), the design system bundle; pytest, with the page scripts run in node by the drivers in `tests/web/*.mjs`.

**Spec:** `docs/superpowers/specs/2026-11-23-refresh-experience-design.md`. Read it first. The mockup the founder approved is `.superpowers/brainstorm/2553069-1795455894/content/refresh-and-meter-v3.html` (not committed: it shows real prices).

## Global Constraints

- Work in the git worktree `.claude/worktrees/refresh-experience`, on the branch `worktree-refresh-experience`. The live server reads the page files from the main checkout, so nothing is edited there before the merge. The mockup is under the main checkout's `.superpowers/`, not the worktree's.
- `uv run` for every command. Before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`. A commit of documents alone runs the short check of `CLAUDE.md`.
- A commit message is one plain sentence in the imperative and ends with `Co-Authored-By: Claude <model> <noreply@anthropic.com>`, naming the model that wrote the change.
- No engine, policy, schema or method change: `docs/method.md`, `METHOD_VERSION` and the policy files stay as they are. If `tests/test_method_doc.py` fails, stop and say so.
- No vendor data in a fixture or a committed file. The tests' companies are the synthetic ones of `tests/support/engine_companies.py`.
- `tokens.css` and the archive are not touched (`test_the_vendored_tokens_are_the_archive_s`). A change in `bundle.js` or `bundle.css` is a patch marked `// fairband:` (in CSS `/* fairband: */`) with the spec's date and section, and `index.d.ts` says the new prop or key.
- Comments follow each file's own form: a block comment over a function that says what it does and names the spec section.
- Motion: only the three of spec 4.8. The layer fades over 150 ms, the run bar eases over 200 ms, the highlight fades over 1.2 s. Under `prefers-reduced-motion` only the bar's ease stops.
- Copy, exact: the menu `Screen`, `Watchlists`, `Statistics`, `Methodology`, `Settings`, `Inbox`; the layer's titles `Refreshing prices`, `Refreshing all`, `Revaluing`; its buttons `Cancel`, `Keep reading`. The other sentences are given in their tasks.
- A subagent, a reviewer included, runs on Opus 5.5 at xhigh (the founder, 2026-11-10).

## Review Focus

1. The status read fails while the page is locked (the server restarts): the reader must be able to leave the layer. Task 7 offers Keep reading on any kind then.
2. Several runs end between two idle reads, or more than `recent` holds: every one is followed, and past the list everything is read again. Task 5.
3. A row with no price or no value, before or after (a placeholder, a refusal, a new or a removed company): no mark, no arrow, no error, and no count. Task 6.
4. A meter with a level missing, a level outside the scale, a value at or below zero, or a price exactly at an end: no `NaN` in the markup, and the end counts as inside. Task 2.
5. The page loads while a whole run is alive, or is reloaded after Keep reading, or the reader presses Back while locked: the layer shows, and the address is put back. Task 7.

---

### Task 1: The phase follows the review

**Files:**
- Modify: `src/fairband/web/rows.py` (`NO_AGENT_FIELDS`, `agent_fields`, `screen_row`, `placeholder_row`, `_group_name`)
- Modify: `src/fairband/web/research_api.py` (`agent_records`)
- Modify: `src/fairband/web/static/app.js` (`sections`), `src/fairband/web/static/company.js` (`head`)
- Modify: `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md` (18.1, one dated line)
- Test: `tests/web/test_rows.py`, `tests/web/test_groups.py`, `tests/web/test_research_api.py`, `tests/web/test_drawer_form.py`, `tests/web/test_company_page.py`

**Interfaces:**
- Produces: `rows.shown_phase(snapshot: SnapshotRow, review: ReviewRow | None) -> Phase | None`, the review's result's phase where the review has a value, else the snapshot's.
- Produces: `agent_fields(...)["phase"]`, that phase's name where a review fills the row, else `None`; `NO_AGENT_FIELDS["phase"] = None`, set aside in `placeholder_row` as `levels` is.
- Produces: row key `phase`, the shown phase as the menu's number, and row key `mechanicalPhase`, the snapshot's (not in `ROW_KEYS`).
- Produces: the detail's key `phase`, the shown phase's engine name or `null`, from `agent_records`. The detail's `result` stays the snapshot's.
- `_group_name(row, "phase")` reads `mechanicalPhase`, so `/api/groups` and the Methodology page's counts do not move.

- [ ] **Step 1: Write the failing tests.** Build the review as `test_a_counting_review_sets_the_rows_levels` builds its own, its result's phase replaced.

```python
def test_a_review_that_changes_the_phase_sets_the_rows_phase(...):
    row = _row(client, "AAPL")  # the engine: Mature Growth; the review's result: Mature Stable
    assert row["phase"] == PHASE_NUMBER["Mature Stable"]
    assert row["mechanicalPhase"] == PHASE_NUMBER["Mature Growth"]

def test_a_refused_review_leaves_the_snapshots_phase(...):      # review.value is None
    assert row["phase"] == row["mechanicalPhase"] == PHASE_NUMBER["Mature Growth"]

def test_an_unclassified_row_takes_its_reviews_phase(...):      # snapshot phase None, review Young Growth
    assert (row["phase"], row["mechanicalPhase"]) == (PHASE_NUMBER["Young Growth"], None)

def test_a_secondary_valuation_changes_no_phase(...)
def test_the_detail_answers_the_shown_phase(...):               # tests/web/test_research_api.py
    assert body["phase"] == "Mature Stable" and body["result"]["phase"]["phase"] == "Mature Growth"
def test_the_groups_count_the_classifiers_phase(...):           # tests/web/test_groups.py, by=phase
```

In `test_drawer_form.py` and `test_company_page.py`: a body with `phase: "Mature Stable"` over a result of Mature Growth draws `PhaseBadge` with `phase: 5`; `phase: null` draws no badge.

- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_rows.py tests/web/test_groups.py tests/web/test_research_api.py tests/web/test_drawer_form.py tests/web/test_company_page.py`
- [ ] **Step 3: Implement the interfaces above.** The two heads read `PHASE_NUMBER[body.phase]` in place of `r.phase.phase`; the fixtures of the page tests gain `phase`.
- [ ] **Step 4: Add the dated line to the Tier 2 design's 18.1:** the row's phase is the review's where Reviewed is filled by a review (the founder, 2026-11-23; spec 2026-11-23 refresh experience, 4.4).
- [ ] **Step 5: Run the full check, then commit.**

### Task 2: The meter's scale

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (`BandMeter`), `bundle.css`, `index.d.ts`
- Test: `tests/web/test_band_meter.py`

**Interfaces:**
- Produces, in `BandMeter`'s markup: the tier's class `fb-band__tier--under`, `--in` or `--over` (the price under the band's low end, inside the band, over its high end); the labels' classes `fb-band__tier-label--low` and `--high`, each with `--tick`, `--price`, `--len` and `--other` (the other label's length in ch); the price marker's class `fb-band__price-mark--pinned` and one `fb-band__break fb-band__break--low` or `--high` in the track, for a pinned price alone.

- [ ] **Step 1: Write the failing tests.** `AGILENT = {"low": 55.59, "high": 67.94, "fairValue": 61.77, "buyLevel": 43.24, "trimLevel": 83.39, "price": 170.38, "designation": "well-above"}`.

```python
def test_the_scale_comes_from_the_value_not_the_price():
    # the fair mark at 50% and the bracket at 40.9% + 18.2%, for a price of 170.38 as for one of 61.77
def test_a_price_beyond_the_scale_is_pinned_behind_a_break_mark():
    # 170.38: the marker has --pinned and left: calc(100% - 7px), one fb-band__break--high,
    # its title still "Price $170.38 — Well above"; 12.40: left: 7px and fb-band__break--low
def test_a_price_inside_the_scale_is_drawn_to_scale_with_no_break():
    # 61.77 at 50%; a price of exactly 1.55 × the value is not pinned
def test_the_band_labels_sit_outside_their_ticks():
    # --low and --high; the tier --under at 50.00, --in at 61.77, --over at 80.00
def test_a_level_outside_the_scale_widens_it():        # trimLevel 111.19 (1.8 ×): the trim zone starts at 93.1%
def test_a_meter_without_a_buy_or_a_trim_level_keeps_the_scale()
def test_a_value_at_or_below_zero_draws_no_nan()
```

Change `test_each_tier_label_is_placed_off_the_price_marker` to the new classes.

- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_band_meter.py`
- [ ] **Step 3: Set the scale in `BandMeter`.**

```js
// fairband: the scale comes from the value, never from the price (spec 2026-11-23 refresh
// experience, 4.7): 0.45 to 1.55 times the fair value, widened only for a level outside it.
var levels = [low, high].concat(buy == null ? [] : [buy], trim == null ? [] : [trim]);
if (fair > 0) {
  min = Math.min(fair * 0.45, Math.min.apply(null, levels) - fair * 0.10);
  max = Math.max(fair * 1.55, Math.max.apply(null, levels) + fair * 0.10);
} else { /* the rule before this one: every point with 12% of padding */ }
var pinned = price > max ? 'high' : price < min ? 'low' : null;
```

A pinned marker's `left` (and its `--price`) is `calc(100% - 7px)` or `7px`. The reviewed marker takes the same rule.

- [ ] **Step 4: Place the labels in `bundle.css`.**

```css
.fb-band__tier > span.fb-band__tier-label--low,
.fb-band__tier > span.fb-band__tier-label--high { transform: none; }
.fb-band__tier--under > .fb-band__tier-label--low  { left: max(calc(var(--tick) - 5px - var(--len)), calc(var(--price) + 8px)); }
.fb-band__tier--under > .fb-band__tier-label--high { left: max(calc(var(--tick) + 5px), calc(var(--price) + 16px + var(--other))); }
.fb-band__tier--in > .fb-band__tier-label--low     { left: min(calc(var(--tick) - 5px - var(--len)), calc(var(--price) - 8px - var(--len))); }
.fb-band__tier--in > .fb-band__tier-label--high    { left: max(calc(var(--tick) + 5px), calc(var(--price) + 8px)); }
.fb-band__tier--over > .fb-band__tier-label--low   { left: min(calc(var(--tick) - 5px - var(--len)), calc(var(--price) - 16px - var(--other) - var(--len))); }
.fb-band__tier--over > .fb-band__tier-label--high  { left: min(calc(var(--tick) + 5px), calc(var(--price) - 8px - var(--len))); }
```

The break mark is two strokes of `surface-raised`, 3px each and 3px apart, slanted, across the track 20px from the pinned end, as the mockup draws it. The old `--left` and `--right` label rules go.

- [ ] **Step 5: Run the full check, then commit.**

### Task 3: Statistics and the menu

**Files:**
- Modify: `src/fairband/web/rows.py` (new `statistics_rows`), `src/fairband/web/app.py` (new route)
- Modify: `src/fairband/web/static/controls.js`, `src/fairband/web/static/app.js`, `src/fairband/web/static/index.html` (`<section id="statistics">` and the selectors that name `#groups`)
- Test: `tests/web/test_statistics.py` (new, built as `test_groups.py` is), `tests/web/test_header.py`, `tests/web/header.mjs`

**Interfaces:**
- Consumes: Task 1's row keys `phase` and `mechanicalPhase`.
- Produces: `rows.statistics_rows(rows: Sequence[dict[str, Any]], by: str, below_value: float) -> list[dict[str, Any]]`. Each group: `name`, `count`, `valued` (rows with a `fairValue`), `medianPriceToValue` (over the valued rows' `priceToValue` that are not `None`), `shareBelowValue` (those under `below_value` ÷ `valued`), and `filter`. By phase the group is the row's shown `phase`.
- `filter`: `{"sector": [name]}`; `{"sector": [the sorted sectors of its rows], "industry": [name]}`; `{"phase": [number]}`; `{"cap": [name.lower()]}`; `None` for `none` and `unclassified`.
- Produces: `GET /api/statistics?by=sector|industry|phase|cap` answers `{"by", "groups"}`; another `by` is 400, in `/api/groups`'s words. `/api/groups` stays for the Methodology page.
- Produces: `FairbandPage.filterScreen(filter)`: the Screen's filters become `F.EMPTY_FILTERS` with `filter` over them, through `listedFilters` on the loaded rows; its find is cleared; `P.show('screen')`.
- Produces: the view id `statistics`. `VIEWS = ['screen', 'watchlists', 'statistics', 'methodology', 'settings', 'inbox', 'company']`, the header's views in that order, and `fromHash` reads `groups` as `statistics`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_statistics_read_the_value_the_screen_shows(...):   # a company with a counting review at another value and phase
def test_a_group_s_filter_is_the_screens(...):              # the four shapes above, and None for none and unclassified
def test_a_group_s_count_is_the_rows_its_filter_leaves(...) # against GET /api/screen, for every group with a filter
def test_an_unknown_grouping_is_400(...)
# tests/web/test_header.py
def test_the_menu_is_in_the_founders_order():   # Screen, Watchlists, Statistics, Methodology, Settings, Inbox
def test_the_old_groups_address_opens_statistics()
def test_a_group_s_name_opens_the_screen_on_its_filter():
    # the driver's trace gains `filters`, the filters prop of the table the screen's root last drew:
    # after filterScreen({"sector": ["Technology"]}) the view is screen, the find is '' and
    # filters equals EMPTY_FILTERS with sector ["Technology"]
```

- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_statistics.py tests/web/test_header.py`
- [ ] **Step 3: Implement.** The Statistics table is the Groups table with each name a link (`href` the page's own path, its press calls `filterScreen(row.filter)`), plain text where `filter` is `null`. Its failure sentence reads "The statistics did not load: …". Its caption reads: "The median and the share read the value the Screen shows, the reviewed one where a company has it, over the companies with a value; below value is a price in its Below or Well below band."
- [ ] **Step 4: Run the full check, then commit.**

### Task 4: The server names a run's companies

**Files:**
- Modify: `src/fairband/store/refreshes.py`, `src/fairband/web/rows.py`, `src/fairband/web/app.py` (`refresh_current`)
- Test: `tests/web/test_refresh_api.py`, the store's refresh tests

**Interfaces:**
- Produces: `store.refreshes.recent_refreshes(conn: sqlite3.Connection, limit: int = 20) -> list[RefreshRow]`, the newest first.
- Produces: `refresh_json(refresh)["symbols"]`, the run's companies as a list, or `None`.
- Produces: `progress_json(progress: Progress, kind: str | None, symbols: tuple[str, ...] | None)`, with `"symbols"` the same way.
- Produces: with no run alive, `GET /api/refresh/current` also answers `"recent"`: for each of the 20 newest runs `{"id", "kind", "symbols", "status"}`, the newest first.

- [ ] **Step 1: Write the failing tests:** a revalue of `["AAPL"]` answers `symbols == ["AAPL"]` while it runs and in `last`, and leads `recent`; a price refresh answers `symbols is None`; `recent` holds 20 of 25 runs, the newest first.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_refresh_api.py`
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run the full check, then commit.**

### Task 5: The page follows any refresh

**Files:**
- Modify: `src/fairband/web/static/controls.js`
- Test: `tests/web/test_header.py`, `tests/web/header.mjs`

**Interfaces:**
- Consumes: Task 4's `symbols` and `recent`; Task 3's view id.
- Produces: `whole(run)`: `run.symbols == null` and `run.kind` is `price`, `full` or `revalue`.
- Produces: `state.seen`, the id of the newest refresh the rows were read under; `state.ended`, `{ id, kind, status }` of the newest whole run among those just followed, else `null`.
- Produces: at a run's end the calls `P.reload(true)`, `P.reloadDrawer()`, the statistics' read when that view shows, and `P.onShow.company(true)` when the company page shows and a followed run is whole or names `P.company.symbol`.
- `IDLE_MS = 30000`.

The rule, exact:
1. An answer with `refresh === null` gives the runs to follow: the entries of `recent` with an id over `state.seen`. The first answer sets `state.seen` to `last.id` (0 with no last) and follows none. Where `recent` holds 20 and its oldest id is over `state.seen + 1`, runs are missing: follow them as one whole run.
2. Runs are followed when that list is not empty, or a run was alive at the answer before, or the page started one. Then `state.seen = last.id`.
3. The next read comes after `POLL_MS` while a run is alive, else after `IDLE_MS`; none while `document.hidden`; at once when the page shows again.
4. The panels take `is-recomputing` only while a whole run is alive. A run of named companies keeps the run bar and Cancel in the header, and fades nothing.

- [ ] **Step 1: Write the failing tests.** The driver gains a step `{"do": "tick"}`, which fires the pending timer, and a step that hides or shows the document; its trace gains `reads`, the urls asked since the step before, and `recomputing`, whether a panel holds the class.

```python
def test_a_run_the_page_did_not_start_is_followed()        # last 66; tick; last 68, recent [68 revalue [OTEX], 67 scoped [OTEX]]: reads hold /api/screen
def test_the_first_answer_follows_no_run()
def test_a_company_page_is_read_again_only_for_its_own_company()   # AAPL shown: OTEX's run reads no detail; AAPL's and a whole run do
def test_a_run_of_named_companies_fades_nothing()          # the bar is drawn, recomputing is false
def test_a_hidden_page_does_not_ask_and_asks_at_once_when_shown()
def test_runs_past_the_list_read_everything_again()        # seen 10, recent ids 40..21
```

- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_header.py`
- [ ] **Step 3: Implement the rule.** `P.followRefresh` keeps its meaning.
- [ ] **Step 4: Run the full check, then commit.**

### Task 6: The end signal

**Files:**
- Modify: `src/fairband/web/static/app.js` (`load`, `loadList`, new `marks`), `controls.js` (`lastLine`), `company.js` (`load`, `head`)
- Modify: `bundle.js` (`ScreenTable`'s row, the price column's cell), `bundle.css`, `index.d.ts`
- Modify: `CLAUDE.md` (the brand book's paragraph)
- Test: `tests/web/test_end_signal.py` (new, through `tests/support/page.py`'s `node`), `tests/web/test_header.py`, `tests/web/test_company_load.py`

**Interfaces:**
- Consumes: Task 5's `P.reload(true)`, `P.onShow.company(true)` and `state.ended`.
- Produces: `FairbandPage.marks(fresh, held) -> { rows, prices, values }`, pure. A fresh row whose ticker `held` has, and that differs from it on a key of `CHANGE_KEYS = ['price', 'fairValue', 'fairLow', 'fairHigh', 'buyLevel', 'trimLevel', 'priceToValue', 'designation', 'reviewed', 'mechanical', 'phase']`, gains `changed`, those keys each `true`. A price that changed between two numbers gains `priceMove`, `1` or `-1`. `prices` counts the rows with `changed.price`, `values` those with `changed.fairValue`. With `held` null: no mark, both 0.
- Produces: `FairbandPage.reload(mark)`. With `mark === true` the rows that land are marked against those held, `P.onChanged({ prices, values })` is called as the Screen's rows land, and after `MARK_MS = 1300` the marks are taken off in one draw. The list's own read marks its rows the same way.
- Produces: in `ScreenTable`, a row's `changed` gives the class `is-changed` to the cells of its changed columns (`band` reads `fairLow` and `fairHigh`, every other column its own key), by `React.cloneElement` on a `td`; `priceMove` puts `<span class="fb-screen__move" aria-hidden="true">` with ▲ or ▼ before the price.
- Produces: `P.onChanged` in `controls.js`: where `state.ended` is a whole run that ended `done`, `state.changes = { id, kind, prices, values }`; `lastLine` adds ` · ` and `changeWords(state.changes)` in a span of class `is-changed`, while `state.last.id === state.changes.id`.
- Produces: `company.js`'s `load(mark)`: with `mark === true` and a detail held for the same symbol at another price, the head's price takes `is-changed` and the arrow for `MARK_MS`.

```js
function changeWords(c) {
  var p = c.prices ? count(c.prices) + (c.prices === 1 ? ' price changed' : ' prices changed') : null;
  var v = c.values ? count(c.values) + (c.values === 1 ? ' value changed' : ' values changed') : null;
  if (p && v) return p + ', ' + v;
  return p || v || (c.kind === 'price' ? 'no price changed' : 'no figure changed');
}
```

```css
/* fairband: the end signal (spec 2026-11-23 refresh experience, 4.2 and 4.8) */
@keyframes fb-changed { from { background-color: color-mix(in srgb, var(--border) 45%, transparent); } to { background-color: transparent; } }
@keyframes fb-gone { from { opacity: 1; } to { opacity: 0; } }
.is-changed { animation: fb-changed 1.2s ease-out; }
.fb-screen__move { color: var(--ink-muted); font-size: 10px; margin-right: 4px; animation: fb-gone 1.2s ease-out forwards; }
.fb-run__seg { transition: width 200ms ease-out; }
@media (prefers-reduced-motion: reduce) { .fb-run__seg { transition: none; } }
```

- [ ] **Step 1: Write the failing tests.**

```python
def test_a_changed_price_is_marked_with_its_direction():
    got = node("marks", [[row("A", price=167.65, priceToValue=2.71)], [row("A", price=170.38, priceToValue=2.76)]])
    assert got["rows"][0]["changed"] == {"price": True, "priceToValue": True}
    assert (got["rows"][0]["priceMove"], got["prices"], got["values"]) == (-1, 1, 0)
def test_a_row_that_is_new_or_unchanged_carries_no_mark()
def test_a_price_that_was_none_is_marked_with_no_direction()   # a placeholder that gained a snapshot
def test_without_held_rows_nothing_is_marked()
def test_the_table_tints_only_the_changed_cells()              # changed {price, designation}; then {fairLow}: the band's cell
def test_a_changed_price_carries_its_arrow()                   # ▲ for 1, ▼ for -1, none without priceMove
# tests/web/test_header.py
def test_a_whole_run_that_ended_done_adds_its_count()
    # "· 1,546 prices changed"; "· 1,546 prices changed, 37 values changed"; "· no price changed" after a
    # price run; "· no figure changed" after a full run; none after a named run; none after a failed run
# tests/web/test_company_load.py
def test_the_head_marks_a_price_that_a_run_changed()           # and not on a plain open, nor for another symbol
```

The node stubs that draw `ScreenTable` gain `cloneElement`.

- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_end_signal.py tests/web/test_header.py tests/web/test_company_load.py`
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Add to `CLAUDE.md`'s paragraph on the brand book:** "Motion is allowed in three places and no other (the founder, 2026-11-23): the refresh layer's fade, the run bar's fill and the highlight of a changed figure. The two fades run under the system's reduced-motion setting too."
- [ ] **Step 5: Run the full check, then commit.**

### Task 7: The refresh layer

**Files:**
- Modify: `src/fairband/web/static/index.html` (`<div id="layer"></div>` after `</main>`, the styles), `src/fairband/web/static/controls.js`
- Test: `tests/web/test_header.py`, `tests/web/header.mjs`

**Interfaces:**
- Consumes: Task 5's `whole`, the run bar's `runProps`, `cancel`.
- Produces: `locked()`: a run is alive, it is whole, and `state.kept` is not its id.
- While locked: `main.app-page` is `inert`, and the layer's root draws `div.app-layer.is-on` (`role="dialog"`, `aria-modal="true"`, labelled by its title) holding `div.app-layer__panel`: the title by kind; the run bar, or the stage word alone where the total is 0; the sentence; the notice, where there is one; Cancel, disabled once asked; Keep reading. Its first enabled button takes the focus as the layer turns on. Not locked: `div.app-layer`, empty and `aria-hidden`.
- The sentence: "The page is locked until the refresh ends." With Keep reading it goes on: " Keep reading removes the lock; the refresh goes on."
- Keep reading stands on a `full` run and a whole `revalue`, and on any kind after a status read that failed. Its press sets `state.kept` to the run's id.
- `show` keeps the address it set in `state.address`. `fromHash`, while locked, puts that address back with `history.replaceState` and shows nothing. Escape does nothing to the layer.

```css
/* The refresh layer (spec 2026-11-23 refresh experience, 4.1). The scrim is no token: the
   archive's tokens are fixed. One value for each theme, named as tokens.css names its themes. */
:root, [data-theme="dark"] { --app-scrim: rgb(0 0 0 / 0.62); }
[data-theme="light"] { --app-scrim: rgb(17 22 27 / 0.5); }
.app-layer { position: fixed; inset: 0; z-index: 1000; display: flex; align-items: center; justify-content: center;
  background: var(--app-scrim); opacity: 0; visibility: hidden; transition: opacity 150ms, visibility 0s 150ms; }
.app-layer.is-on { opacity: 1; visibility: visible; transition: opacity 150ms; }
.app-layer__panel { width: min(400px, calc(100vw - 32px)); padding: var(--space-5); background: var(--surface-raised);
  border: 1px solid var(--hairline); border-radius: var(--radius-lg); box-shadow: var(--shadow-popover); }
```

The light value also goes under `tokens.css`'s own `prefers-color-scheme` selector.

- [ ] **Step 1: Write the failing tests.** The trace gains `layer`, `{ on, title, sentence, keep, cancel, notice }`, and `inert`.

```python
def test_a_whole_run_locks_the_page(kind, title)                 # price, full, revalue with no symbols
def test_a_run_of_named_companies_draws_no_layer()               # scoped; a revalue of ["OTEX"]
def test_keep_reading_stands_on_the_long_runs_only()             # full and revalue; not price
def test_keep_reading_lifts_the_lock_for_that_run_alone()        # then the bar and the fade, as today; another id locks again
def test_the_run_s_end_lifts_the_lock()
def test_a_whole_run_another_page_started_locks_too()            # the first answer is a run alive
def test_a_failed_status_read_offers_keep_reading_on_a_price_run()
def test_back_and_forward_are_put_back_while_locked()
def test_cancel_in_the_layer_asks_the_server_and_is_disabled_after()
```

- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_header.py`
- [ ] **Step 3: Implement the interfaces above.**
- [ ] **Step 4: Run the full check, then commit.**

### Task 8: The look in a browser, and the records

**Files:**
- Create: `docs/superpowers/specs/2026-11-23-refresh-experience-mockup/README.md`, `look.mjs`
- Modify: `docs/backlog.md`; the spec, where the build changed something

- [ ] **Step 1: Make a scratch database of the whole universe and start the branch's server on port 8499,** as `docs/superpowers/specs/2026-11-19-gurufocus-removal-mockup/` does it (`make_scratch.py`, `pw.mjs`). Never a second server on the live data.
- [ ] **Step 2: Write `look.mjs`** (Playwright from the npx cache, the scrollbars shown, both themes, 1,600px and 600px high). It exits with an error on any failed check and saves a screenshot of each state:
  - A simulated price run, by stubbed status reads as the probe of 2026-11-23 did: the layer is up and a press on the menu changes no view; at the end the changed cells hold the tint, the changed prices their arrows, and the line its count; 3 seconds on no tint is left, with `reducedMotion: 'reduce'` too.
  - A simulated full run: Keep reading lifts the layer, and the bar stays in the status line.
  - A run of one named company: no layer, no fade, and that row's cells tinted.
  - Statistics: a press on a group's name opens the Screen, and its count is the group's Companies.
  - The meters, on a page that mounts `Fairband.BandMeter` from the built bundle: prices at 0.20, 0.45, 0.50, 0.88, 0.90, 0.95, 1.00, 1.10, 1.12, 1.55, 1.60 and 2.76 times the value, on values of 9.99, 61.77 and 1,587.00, at 256px and 380px. By `getBoundingClientRect`: the two labels do not overlap, neither overlaps the price marker's dot, and nothing leaves the meter.
- [ ] **Step 3: Run it, read every screenshot, and correct what it shows.** A correction goes back through the task that owns it, test first.
- [ ] **Step 4: Write the records.** In `docs/backlog.md`: the route's columns on a row whose review changed its phase (spec 4.4); the README's screenshots, which show the old menu, for the founder's word; each minor the build left. In the spec, a short section on what the build changed, if anything.
- [ ] **Step 5: Run the full check, then commit.**

After Task 8: ask the founder, in one message, for the merge, the restart of the live server, the push, and the word to leave the worktree.
