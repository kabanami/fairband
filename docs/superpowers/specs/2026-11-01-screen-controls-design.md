# Screen controls: header, run progress, find, filters, column order

Status: approved by the founder 2026-11-01, after the builder check. Companion to
`2026-11-01-calibration-design.md`; both are built in one iteration on one branch, the engine
tasks first. Where this document and `2026-10-31-mechanical-screen-design.md` disagree, this
document wins; everywhere else the mechanical-screen spec stands.

## 1. Intent

After the first live run on 2026-11-01 the founder asked for five changes to the page:

1. a progress bar during a refresh that shows what is fetched, what remains and what failed;
2. a search bar that narrows the table to a typed ticker;
3. columns that can be moved along the table, with the chosen columns and their order kept;
4. filters on columns such as cap size and sector;
5. a header with the Fairband mark.

The founder's design system was re-exported on 2026-11-01 (second build) as
`docs/design-system/fairband-design-system_4.tar.gz`. It adds the mark (`Fairband.Mark`), the
44px application header (`AppHeader`), the run bar (`RunProgress`), and the `FIND` field and
`Filters ▾` menu on `ScreenTable`. Items 1, 2, 4 and 5 are those components, mounted. Item 3 is
not in the design system; the repository's copy of the table is extended for it, as the
mechanical-screen spec already allows ("that copy is the one the repository owns and may
extend").

Success: the founder opens the page, sees the lockup in the header with the engine's last run,
starts a refresh and watches the counts move, types a ticker and sees one row, narrows to Mega
caps in Technology, drags a column to where they want it, and finds it there after a reload.

## 2. Goals, non-goals, anti-goals

Goals: the five items above, on the design system's 2026-11-01 build, with no new vendor calls,
no new tables and no change to the engine.

Non-goals, left for later pieces:

- a filter on industry (121 names in the universe; the design system has no control for that);
- the failed count as a button that narrows the screen to the failed companies
  (`onShowFailed`); the design system has no filter group for it, and a narrowing that does not
  show as a chip in the bar breaks the rule that every active filter is stated there;
- filtering on the server, or filtered groups on the Groups view;
- saving the query or the filters across reloads;
- moving a column from the keyboard;
- the repository README with the cover image;
- settings (workers, required return, 429 handling), which are the settings piece.

Anti-goals, what would make this wrong even if it worked:

- a spinner, a percentage, or an estimated finish time on the run;
- blanking, greying or skeleton rows in the table while a run is in flight;
- a sticky header with a shadow, or a header taller than 44px to fit the mark;
- an image of the wordmark; the name is live type;
- a hard-coded colour, size or radius; the tokens carry every value.

## 3. Constraints

- The design system's rules apply as written in its archive: `docs/brand-book.md`,
  `docs/components/AppHeader.md`, `RunProgress.md`, `ScreenTable.md`, `assets/Logos/README.md`.
  The ones this piece leans on: the header is 44px and carries the lockup, the views and the
  engine stamp, nothing else; controls are named by words, never a glyph; the run bar is
  determinate and leaves every zero count out; the table keeps the last finished run's figures
  during a run; every filter group is a whitelist; a filter must also be a column the reader can
  show; sector gets no colour.
- No build step and no JSX: `React.createElement` against `window.Fairband`, as today.
- Every change to the exported bundle carries a `// fairband:` comment (the test
  `test_bundle_patches_marked` counts them) so the next export can be diffed against them.
- Keys and vendor data: unchanged; this piece makes no vendor call and stores nothing new.
- Archive 4 is committed under `docs/design-system/` beside archive 2, which stays for the
  record. `CLAUDE.md`'s brand-book pointer moves to archive 4.

## 4. Design

### 4.1 The design system upgrade

The package's static copy (`src/fairband/web/static/design-system/`) moves from the 29 October
export to the 2026-11-01 build:

- replace `tokens/tokens.json`, `tokens/tokens.css`, `components/bundle.css`,
  `components/bundle.js`, `components/index.d.ts`; `fonts/` and `tokens/build_tokens.py` are
  byte-identical between the two exports and stay;
- add `assets/Logos/` with the four SVG marks and its README; the two PNG covers are not
  served (they are for the repository README, a later piece);
- re-apply the repository's patches on the new `bundle.js`. They are the hunks of
  `git diff` between the 29 October export's `bundle.js` and the installed copy, eight in all:
  a timestamp reads as its date; a null phase draws an em dash, never "1 Start-up"; the
  formats and the sixteen extra column definitions of spec 6.3; a row without levels has no
  stance; `onSort` on header cells (click, Enter, Space); `onOpen` on rows with
  `aria-current`; `formatPercent` exported. The declarations of `onSort` and `onOpen` are
  re-added to `index.d.ts` (two tests read them).

Nothing else in the page changes in this task; `app.js` and `controls.js` keep working on the
new bundle. The `.fb-mark` class stays the freshness glyph on the Entered cell; the mark's
classes are `.fb-logo*` in this build, so there is no collision.

New token: `--header-height: 44px`. The only token change between the exports.

### 4.2 The header

`Fairband.AppHeader` is the first thing on the page and the app's only chrome. It replaces the
`h1` and the two tab buttons.

- `views`: `[{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' }]`; `view`
  is the open tab; `onViewChange` opens the other, as the tab buttons do today.
- `engineRanAt`: the latest refresh's `finishedAt`, whatever its status; the status line
  under the header still says how that run ended. With no finished refresh on file, nothing is
  passed: an absent stamp is honest, a placeholder is noise.
- while a refresh is in flight, neither `engineRanAt` nor `run` is passed, so the header shows
  nothing where the stamp was: the stamp describes a finished run, and the one bar of section
  4.3 sits on the status line directly under the header. The stamp returns when the run ends.
  The component's `run` prop (its compact bar) is not used in this cut (*my call*: one bar, the
  full one, rather than two with the same numbers 44px apart).
- `children`: the refresh controls, small size: `Refresh prices` (secondary) and `Refresh all`
  (primary). While a run is in flight both are replaced by one `Cancel` (quiet). After Cancel is
  asked, the notice line says so, as today, and Cancel is disabled until the run ends.

The page's `<title>` stays `Fairband`. The favicon is the mark: `mark-on-dark.svg` from
`assets/Logos/`, served from the static path (*my call*: the page follows the operating
system's theme, dark by default, and a favicon cannot follow it).

The header is not sticky. The `hairline` rule the component draws is the separation.

### 4.3 The run bar

The poll of `/api/refresh/current` every 2 seconds stays. From its `refresh` body the page
derives the props of `RunProgress`:

- `total = done + failed + remaining`, `done`, `failed`, all of the current stage, because the
  server's counts are per stage and add up to the stage's symbols;
- `stage`, a lowercase verb phrase from the server's stage name:

| Server stage | Kind | Word shown |
| --- | --- | --- |
| `universe` | full, scoped | `reading the universe` |
| `deciles` | full, scoped | `ranking` |
| `fetch` | full, scoped | `fetching` |
| `value` | full, scoped | `valuing` |
| `quotes` | price | `fetching prices` |
| `reprice` | price | `repricing` |
| `done` | any | `finishing` |

For the `universe` and `deciles` stages the server reports every symbol as done; the page
passes `done: 0` and `total` as the symbol count instead, because no company is fetched or
valued yet, and the word says what is happening (*my call*). An unknown stage name is shown as
it is.

A stage's first report can be all zeros (`universe` before the symbols are known; `done`). The
component draws nothing for a total of 0; then the status line shows the stage word alone,
with no bar and no counts (*my call*).

One place shows the run: the full form of `RunProgress` on the status line under the header,
in place of the caption that holds the progress text today: the bar, then `done`, `pending`
and `failed` written as words with their counts, zero counts left out, and the stage word.
The header's compact form is not used (section 4.2).

`onShowFailed` is not passed (section 2). When the run ends, the status line returns to the
last-refresh line as today, with its calibration; a price refresh's `failed` count is in that
line already.

The tables keep their old figures at `ink-faint` during a run, as today.

### 4.4 Find and filters

`ScreenTable` gets `query`, `onQueryChange`, `filters`, `onFiltersChange`, `total` and
`sectors`. The component draws the `FIND` field, the `Filters ▾` menu, the chips and the
`41 of 1,759 · Clear` count; it narrows nothing. The page narrows the rows it loaded, after
every load and every change, with the design system's reference rule (the gallery's `apply`):

- query: the trimmed, lower-cased text matches a ticker prefix or a company-name substring;
- `stance`: the row's stance from its price against its buy and trim levels, the same rule the
  stance column uses; a row without levels has no stance and drops out while a stance filter is
  active;
- `phase`: the row's phase number (the page's `PHASE_NUMBER` of the engine's phase name); an
  unclassified row has none and drops out while a phase filter is active;
- `cap`: the row's `capBand` lower-cased (`Mega` → `mega`, `Large` → `large`, `Mid` → `mid`);
  `small` is in the menu because the design system draws it, and never matches, since the
  universe's floor is $2 bn;
- `sector`: exact match on the row's `sector`;
- `reviewedOnly`: the row's `reviewed` is not null, which empties the table in this cut
  (the count reads `0 of 1,759 · Clear`, which is true);
- `hideExpired`: the row's `freshness` is not `expired`.

`sectors` is the sorted list of distinct `sector` values across the loaded rows, with null left
out. They are the screener's eleven names (Technology, Healthcare, Consumer Cyclical, Financial
Services, Basic Materials, Consumer Defensive, Industrials, Energy, Utilities, Communication
Services, Real Estate), not the GICS names the component defaults to; the component takes the
override for this reason. Sector and Cap are already columns in the repository's copy, so the
rule that a filter is also a column holds.

`total` is the count of loaded rows. Sorting stays on the server; the narrowing applies to the
sorted rows, so the order is unchanged. The query and the filters start empty on every page
load and are not saved (section 2). The drawer stays open when a filter hides its row.

The Groups view ignores the query and the filters.

### 4.5 Column order

In the repository's copy of `ScreenTable` (a new `// fairband:` patch):

- the visible columns render in the order of the `columns` list, not the catalog's order;
  locked columns (`ticker`, `price`) render where the list puts them and move like any other
  column; the lock is on visibility, not on position (*my call*);
- a header cell is draggable; dropping it on another header cell moves the dragged column to
  that column's position (removed from the list, inserted at the target's index), and the
  component calls `onColumnsChange` with the new list. The target header shows a 2px `accent`
  inset edge on its leading side while a column is over it; nothing else moves, and there is no
  animation. A click that does not move the pointer still sorts;
- the `Columns ▾` menu lists the chosen columns in the table's order, then the unchosen ones in
  catalog order; `Reset to the default eight` restores the default list in its default order.

The page keeps the list in `localStorage["fairband.columns"]`, as today; its order is now
meaningful. On load the page normalises a saved list: a missing `ticker` goes first, a missing
`price` goes last, unknown keys are dropped (*my call*, for lists saved before this change).

`index.d.ts` says `columns` is ordered and that dropping a header calls `onColumnsChange`.

### 4.6 The page

Top to bottom: the header (44px), the status line (the run bar during a run, else the
last-refresh line) with the notice line under it when there is one, then the open view. The
`h1` and the tabs go. Everything else on the page stays as it is.

## 5. Left to the builder

- The CSS of the drop edge and the drag cursor, from the tokens.
- How a drop suppresses the click that would otherwise sort the dragged column.
- The exact text of the full run bar's words and separators, within the component's rules.
- The test strategy for the browser scripts: as today, file-content assertions in
  `tests/web/test_app.py`, since the repository runs no JavaScript tests.

## 6. Acceptance

- The page shows the lockup in a 44px header with `Screen` and `Groups` and
  `engine ran <date>, <time>`, the latest refresh's finish formatted by the component.
- During a refresh the header shows no stamp; the bar sits on the status line with the stage
  word and the counts; `Cancel` stands where the two refresh buttons were; the table's figures
  stay, faded. When the run ends the stamp and the buttons return and the rows reload, as
  today.
- `FIND` with `aap` narrows to tickers starting with `AAP` and names containing `aap`; the bar
  reads `n of 1,759 · Clear`; `Clear` empties the field and the filters.
- `Filters ▾` offers stance, phase, the four cap sizes and the eleven screener sectors; a chosen
  group shows as a chip; clicking the chip clears that group.
- Dragging the `Phase` header onto the `Price` header puts Phase where Price was; after a
  reload the order is the same. `Reset to the default eight` restores the default order.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
  passes; the existing bundle tests pass on the new bundle; new tests assert the bundle defines
  `AppHeader`, `RunProgress`, `Mark`, `CAPS`, `SECTORS` and `EMPTY_FILTERS`, that the tokens
  carry `--header-height`, that `/static/design-system/assets/Logos/mark-on-dark.svg` is
  served, and that `index.html` carries the favicon link and no `h1`.

## 7. Decision log

Calls made in this document, for the founder to check:

1. The refresh controls live in the header's `children` slot, small size; Cancel replaces them
   during a run.
2. One bar, the full form, on the status line under the header; the header shows no stamp
   while a run is in flight (the founder asked whether two bars were needed, 2026-11-01).
3. The `universe` and `deciles` stages show `0 of n` with their word.
4. The favicon is `mark-on-dark.svg`.
5. The `engine ran` stamp is the latest refresh's finish whatever its status.
6. Narrowing happens in the page, on the loaded rows; the API is unchanged.
7. Sector names are the screener's eleven, passed through the component's `sectors` override.
8. Column order is a drag on the header; keyboard moving waits; a saved list is normalised on
   load.
9. Industry filtering, the failed-count button and saved filters wait for later pieces.
10. A stage reported with a total of 0 shows the stage word alone on the status line (from the
    builder check).
11. Ticker and Price can be dragged anywhere; the normaliser only adds a missing one (from the
    builder check).

Builder check done 2026-11-01: two questions, both settled above as calls 10 and 11.
