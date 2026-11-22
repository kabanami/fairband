# The Watchlist Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The watchlist page shows one list with the Screen's table and drawer, a list has no
Request research, the drawer's Request research box stays inside the window, and the Inbox's
ticker opens the company page.

**Architecture:** The Screen's own mount in `app.js` draws the table and the drawer for both
views. It keeps a second set of FIND, filters and sort for the list, and `controls.js` shows the
`#screen` panel under the `#watchlists` panel on the Watchlists view. `watchlists.js` keeps only
the list's head: the selector, the default, the writes. It tells `app.js` which list to draw.

**Tech Stack:** Plain ES5 scripts with the vendored React (`h = React.createElement`), no build
step; pytest tests that read the scripts as text and run their helpers in node through
`tests/web/page.mjs`.

**Spec:** `docs/superpowers/specs/2026-11-22-watchlist-page-design.md`. Read it first; section
numbers below are its.

## Global Constraints

- Work only in the worktree `.claude/worktrees/watchlist-page`, on the branch `watchlist-page`.
  Never edit the main checkout: the live server on port 8470 serves its page files.
- Never start a server on the live data folder and never send a write to port 8470.
- Page files only: nothing under `src/fairband/` changes outside `src/fairband/web/static/`. No
  route, no store, no schema, no MCP tool. `docs/method.md` and the README's screenshots do not
  change.
- The document holds one `ScreenTable` with a bar at a time: its FIND field has the fixed id
  `fb-q`.
- Scripts stay in the files' own manner: `var`, `function`, no arrow functions, a block comment
  on each function that says what it does and why.
- Every test is written first and seen to fail. Test fixtures are synthetic.
- Exact words and values: the button `Set as default`, and `Default` on the default list; the
  selector's entry of the default list ends ` (default)`; the storage key
  `fairband.watchlist.default`; the address `#watchlists/<id>`; the sentences "No watchlists yet.
  Create one here, or press the mark beside a ticker on the screen." and "No companies on this
  list yet.".
- Before every commit, from the worktree:
  `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
- A commit message is one plain sentence in the imperative and ends with
  `Co-Authored-By: Claude <model> <noreply@anthropic.com>`, naming the model that wrote the
  change. A test of the old view that is rewritten or removed is named in the message of the
  commit that does it.

## Review Focus

1. **The Screen's place after a visit to a list.** The two views share one scroller. A reader
   who scrolls the Screen, opens Watchlists and returns expects the Screen where it was, with its
   FIND, filters and sort untouched (Task 3, the pins of `top`, `shown` and `find`; Task 5,
   checks 2 and 8).
2. **An address that names no list**: `#watchlists/999`, `#watchlists/abc`, or a list deleted in
   another tab. The page opens the default, or the first list by name, and writes that list's
   address (Task 4, `test_the_list_the_page_opens_on` and `test_show_reads_the_lists_id`).
3. **The lists arrive after the view opens**, as on a reload at `#watchlists/3`. The page waits
   for them and keeps the address; it does not turn to the default first (Task 4,
   `test_the_head_follows_the_lists`; Task 5, check 3).
4. **A deleted default.** A stored default that names a deleted list is ignored, and the store
   never gives a deleted list's id again (`watchlists.id` is `AUTOINCREMENT`), so it can name no
   other list. Delete of the default list still clears the stored default, so nothing stale
   stays in the browser (Task 4, `test_delete_clears_a_default_it_removes`).
5. **No storage**, as in a private window: the page loads and works, and the default lasts until
   the page reloads (Task 4: the node tests load `watchlists.js` with no `localStorage`).

---

### Task 1: The drawer's Request research box opens inside the window

**Files:**
- Modify: `src/fairband/web/static/index.html` (the rule `.app-request .fb-menu`, its comment, and
  the rule `.app-company__actions .app-request .fb-menu`)
- Test: `tests/web/test_app.py` (the pin of the old rule, near line 2085),
  `tests/web/test_company_page.py:291`

**Interfaces:**
- Consumes: the bundle's `.fb-menu { position: absolute; right: 0; … }`.
- Produces: one rule for both places that draw `.app-request`, the drawer and the company page's
  head: `.app-request .fb-menu { left: auto; right: 0; }`.
- Amended in the build (the review of 18ad8ba): that rule alone cut the box off at the drawer's
  left edge whenever the drawer had a scrollbar, since its two buttons then wrap. In the drawer
  the box is fixed to the row of buttons, not to the button:
  `.app-drawer__actions { position: relative; }` and
  `.app-drawer__actions .app-request { position: static; }` (commit f893d26).

- [ ] **Step 1: Change the two pins so they fail**

In `tests/web/test_app.py` replace the assertion of the old rule with:

```python
    assert ".app-request .fb-menu { left: auto; right: 0; }" in page
    assert ".app-company__actions .app-request .fb-menu" not in page
```

In `tests/web/test_company_page.py:291` read the shared rule instead:

```python
    assert "left: auto; right: 0;" in _rule(".app-request .fb-menu {")
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest -q tests/web/test_app.py tests/web/test_company_page.py`
Expected: 2 failures, each on the lines above.

- [ ] **Step 3: Change the rule in `index.html`**

The shared rule becomes `.app-request .fb-menu { left: auto; right: 0; }`. The company page's own
rule goes: it now repeats the shared one. The comment above `.app-request` says the box opens
from the button's right edge, and why: in the drawer the button stands near the window's right
edge.

- [ ] **Step 4: Run the full check, then commit**

Message: `Open the Request research box from its button's right edge, so the drawer's stays inside the window`

### Task 2: The Inbox's ticker is a link to the company page

**Files:**
- Modify: `src/fairband/web/static/inbox.js` (`row`, and the file's head comment where it
  describes the ticker)
- Test: `tests/web/test_inbox_launch.py`, `tests/web/test_app.py` (the Inbox view's pin of
  `P.openRow(item.symbol)`, near line 1629)

**Interfaces:**
- Consumes: `P.companyHref(row) -> string`, which reads `row.ticker`.
- Produces: the ticker as `a.ticker.app-link.app-inbox__symbol` with
  `href: P.companyHref({ ticker: item.symbol })` and no `onClick`. `inbox.js` no longer calls
  `P.openRow`. `openRow` itself stays until Task 4.

- [ ] **Step 1: Write the failing tests**

In `tests/web/test_inbox_launch.py`:

```python
@pytest.mark.parametrize(("symbol", "href"), [("AAPL", "#company/AAPL"), ("A&B", "#company/A%26B")])
def test_the_ticker_links_to_the_company_page(symbol: str, href: str) -> None:
    """Spec 2026-11-22, 11: an item's ticker is a plain link to the company page, the address
    companyHref gives, with no click of its own; the row has no click."""
    tree = node("inbox.row", [_item() | {"symbol": symbol}], INBOX)
    [link] = classed(tree, "app-inbox__symbol")
    assert link["type"] == "a"
    assert link["props"]["href"] == href
    js = _static_file("inbox.js")
    assert "P.openRow" not in js
    assert "h('tr', { 'data-item': item.id }," in js  # the row has no handler
```

Import `classed` and `_static_file` there if the file lacks them. In
`test_a_done_item_links_to_its_report_on_the_research_tab` the report's link is no longer the
only one with an address, so find it without the ticker's:

```python
    [link] = [
        e for e in elements(tree)
        if e.get("type") == "a" and "app-inbox__symbol" not in e["props"]["className"]
    ]
```

In `tests/web/test_app.py`, the Inbox view's `_in_order` list: replace the `P.openRow` line with
`"href: P.companyHref({ ticker: item.symbol })"`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest -q tests/web/test_inbox_launch.py tests/web/test_app.py`

- [ ] **Step 3: Change `row` in `inbox.js`** as the Interfaces block says.

- [ ] **Step 4: Run the full check, then commit**

Message: `Link the Inbox's ticker to the company page`

### Task 3: The Screen's table draws a list

**Files:**
- Modify: `src/fairband/web/static/app.js`
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (`ScreenTable`'s Filters
  menu)
- Create: `tests/web/test_watchlist_page.py`

**Interfaces:**
- Consumes: `narrow(rows, query, filters)`, `sectorsOf`, `industriesOf`, `listedFilters`,
  `localRow`, `open`, `watch`, `Screen`, all in `app.js`.
- Produces, on `window.FairbandPage`:
  - `listRows(rows, symbols) -> rows`. `rows` are screen rows in the server's order, `symbols`
    a list of tickers. It returns the rows whose ticker is in `symbols`, in `rows`' order, each
    with `watched: true`, then one row for each symbol with no row, by ticker:
    `{ ticker, name: null, price: null, mechanical: null, reviewed: null, phase: null,
    fairLow: null, fairHigh: null, watched: true }`.
  - `onList(on)`. `on` is a boolean: the table draws the selected list, or the Screen.
  - `selectList(id)`. `id` is a list's id or null. An id already selected changes nothing and
    draws nothing.
- Produces, in the bundle: `ScreenTable`'s prop `listFilter`. With `listFilter: false` the Filters
  menu draws no WATCHLISTS section and no rule before it.

Task 3 changes nothing a reader sees: nothing calls `onList` until Task 4.

- [ ] **Step 1: Write the failing tests** in the new `tests/web/test_watchlist_page.py`

```python
"""The watchlist page (spec 2026-11-22): one list drawn by the Screen's own table and drawer."""

from typing import Any

import pytest
from support.page import NODE, STATIC, node
from support.web import _component_file, _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

WATCHLISTS = STATIC / "watchlists.js"
EMPTY: dict[str, Any] = {
    "designation": [], "stance": [], "phase": [], "cap": [], "sector": [], "industry": [],
    "watchlist": [], "reviewedOnly": False, "hideExpired": False,
}
GONE = {
    "name": None, "price": None, "mechanical": None, "reviewed": None, "phase": None,
    "fairLow": None, "fairHigh": None, "watched": True,
}


def _row(ticker: str, **more: Any) -> dict[str, Any]:
    return {"ticker": ticker, "name": f"{ticker} Holdings", "phase": 4, "price": 10.0} | more


def _listed() -> list[dict[str, Any]]:
    rows = [_row("MSFT"), _row("AAPL"), _row("ZZZZ")]
    listed: list[dict[str, Any]] = node("listRows", [rows, ["AAPL", "QQQQ", "MSFT", "BBBB"]])
    return listed


def test_a_lists_rows_keep_the_servers_order_then_the_symbols_with_no_row() -> None:
    listed = _listed()
    assert [r["ticker"] for r in listed] == ["MSFT", "AAPL", "BBBB", "QQQQ"]
    assert all(r["watched"] is True for r in listed)
    assert listed[2] == {"ticker": "BBBB"} | GONE


def test_find_reaches_a_symbol_with_no_row_and_no_filter_does() -> None:
    listed = _listed()
    assert [r["ticker"] for r in node("narrow", [listed, "bb", EMPTY])] == ["BBBB"]
    by_phase = node("narrow", [listed, "", EMPTY | {"phase": [4]}])
    assert [r["ticker"] for r in by_phase] == ["MSFT", "AAPL"]


def test_the_table_draws_a_list_with_its_own_find_filters_and_sort() -> None:
    app = _static_file("app.js")
    for pin in (
        "listRows: listRows, onList: onList, selectList: selectList,",
        "function shown() { return state.onList ? state.list : state; }",
        "key: state.onList ? 'list' : 'screen',",
        "listFilter: state.onList ? false : undefined,",
        "top: state.onList ? 0 : state.screenTop,",  # the Screen's place comes back with it
        "note('No companies on this list yet.')",
    ):
        assert pin in app, pin
    # the Methodology page's examples still go to the Screen's own FIND and filters
    find = app[app.index("  function find(symbol) {") :]
    find = find[: find.index("\n  }\n")]
    assert "state.query = symbol;" in find and "state.filters = F.EMPTY_FILTERS;" in find
    assert "p.listFilter === false ? [] : lists" in _component_file("bundle.js")
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest -q tests/web/test_watchlist_page.py`
Expected: 3 failures; the first two because `listRows` is no function of the page.

- [ ] **Step 3: The bundle's prop**

In `ScreenTable`, beside `var lists = p.watchlists || [];`, add
`var menuLists = p.listFilter === false ? [] : lists;` with a `// fairband:` comment in the
bundle's manner. The Filters menu's WATCHLISTS section and its `hr` read `menuLists`. The chips
and the Watchlists column still read `lists`.

- [ ] **Step 4: The list's state and `listRows` in `app.js`**

Add to `state`:

```js
    onList: false, /* the table draws the watchlist page's list, not the screen (onList) */
    /* The watchlist page's own FIND, filters and sort, and the list it shows (spec 2026-11-22,
       7.1); rows holds the screen's rows in this sort where it differs from the Screen's. */
    list: { id: null, query: '', filters: F.EMPTY_FILTERS,
            sort: { column: 'ticker', direction: 'asc' }, rows: null },
    screenTop: 0, /* where the Screen's scroller stood when the list took the table */
```

Write `listRows` as its Interfaces line says, and `shown()` as the test pins it. `setQuery`,
`setFilters` and `sortBy` write to `shown()`. `setFilters` hands `listedFilters` the rows of the
view it writes for. `find` keeps writing the Screen's own `state.query` and `state.filters`.

- [ ] **Step 5: The list's rows**

The list reads no rows of its own while its sort equals the Screen's: it then uses `state.rows`.
Where the sorts differ, `loadList()` reads `/api/screen` with the list's sort into
`state.list.rows`, through `localRow`, with a request counter of its own as `load` has. It reads
only while `state.onList`. `load()` calls it too, so the list follows every reload, and so does a
sort on either view.

- [ ] **Step 6: `onList` and `selectList`**

- `onList(on)`: no change, no work. Turning on keeps the Screen's place,
  `state.screenTop = <.app-main>.scrollTop`, then calls `loadList()` and draws. Turning off draws.
- `selectList(id)`: no change, no work, no draw. A new id clears the list's `query` and
  `filters`, keeps its sort, puts the scroller at its top and draws.

- [ ] **Step 7: `render` in list mode**

The drawer, Top and the three boxes draw as today in both modes. On the list, `main` is:

- nothing while the lists or the rows are not loaded, or no list is selected;
- `note('No companies on this list yet.')` for a list with no company;
- else `Screen` on `narrow(all, list.query, list.filters)`, where `all` is `listRows` of the
  list's source rows and the selected list's symbols. Its props are the Screen's with the list's
  `query`, `filters` and `sort`, `total: all.length`, `sectors` and `industries` read from `all`,
  and the three props the test pins, `key`, `listFilter` and `top`. The Screen's own table takes
  the same three lines.

`Screen` puts the scroller at its prop `top` in its mount effect. The root draws after `render()` returns, so the place
cannot be set from `onList` itself; the `key` remounts the table on a change of view, and the
effect then runs with the new rows in the document.

- [ ] **Step 8: Run the tests, then the full check**

A pin elsewhere of the old text of `setQuery`, `setFilters`, `sortBy`, `load` or `render` is
rewritten to the new text. Commit.

Message: `Draw a watchlist's rows in the Screen's table, with FIND, filters and a sort of its own`

### Task 4: The page of one list

**Files:**
- Modify: `src/fairband/web/static/watchlists.js` (rewritten: the head alone)
- Modify: `src/fairband/web/static/controls.js` (`show`, a new `keepList`, the page's `listId`)
- Modify: `src/fairband/web/static/app.js` (`openRow` goes, with its export and its comments;
  the comment on `reloadDetail` no longer names a watchlist's Request research)
- Modify: `src/fairband/web/static/index.html` (the panels' rules, the old view's rules)
- Modify: `src/fairband/web/static/methodology.html` (one sentence goes)
- Modify: `docs/superpowers/specs/2026-11-04-methodology-settings-watchlists-design.md`,
  `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md` (one decision log line each)
- Test: `tests/web/test_watchlist_page.py`, `tests/web/test_app.py`,
  `tests/web/test_ticker_link.py:74`

**Interfaces:**
- Consumes: `P.onList(on)`, `P.selectList(id)`, `P.listRows` (Task 3); `P.watchlists()`,
  `P.reloadWatchlists()`, `P.reload()`, `P.rows()`, `P.api`, `P.refusal`, `P.localIso`.
- Produces:
  - `P.listId`: the id the address names, a number or null. `controls.js` sets it from the hash,
    `watchlists.js` when the reader chooses a list.
  - `P.lists = { opens: opens, head: head }`, for the tests.
  - `opens(lists, addressId, defaultId) -> id | null`: the first of the list `addressId` names,
    the list `defaultId` names, `lists[0]`; null with no list.
  - `head(list, lists, defaultId) -> element`: the selected list's head.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_watchlist_page.py`

```python
LISTS = [
    {"id": 4, "name": "Core", "createdAt": "2026-11-20T10:00:00+00:00", "count": 2,
     "symbols": [{"symbol": "AAPL", "addedAt": "2026-11-20T10:00:00+00:00"},
                 {"symbol": "MSFT", "addedAt": "2026-11-20T10:00:00+00:00"}]},
    {"id": 2, "name": "Mag7", "createdAt": "2026-11-22T10:00:00+00:00", "count": 0, "symbols": []},
]


@pytest.mark.parametrize(
    ("lists", "address", "default", "opened"),
    [
        (LISTS, 2, 4, 2),  # the address first
        (LISTS, 999, 2, 2),  # an address that names no list: the default
        (LISTS, None, 999, 4),  # a default that names no list: the first by name
        (LISTS, None, None, 4),
        ([], 2, 4, None),
    ],
)
def test_the_list_the_page_opens_on(
    lists: list[dict[str, Any]], address: int | None, default: int | None, opened: int | None
) -> None:
    assert node("lists.opens", [lists, address, default], WATCHLISTS) == opened


def test_the_head_has_the_selector_and_the_default_and_no_request_research() -> None:
    tree = node("lists.head", [LISTS[0], LISTS, 4], WATCHLISTS)
    [pick] = [e for e in elements(tree) if e.get("type") == "select"]
    assert pick["props"]["value"] == "4"
    options = [e for e in elements(pick) if e.get("type") == "option"]
    assert [text(o) for o in options] == ["Core (default)", "Mag7"]
    buttons = [e for e in elements(tree) if e.get("type") == "button"]
    assert [text(b) for b in buttons] == ["Default", "Rename", "Delete"]
    assert buttons[0]["props"]["aria-pressed"] == "true"
    other = node("lists.head", [LISTS[1], LISTS, 4], WATCHLISTS)
    [first] = [e for e in elements(other) if e.get("type") == "button"][:1]
    assert text(first) == "Set as default" and first["props"]["aria-pressed"] == "false"
    js = _static_file("watchlists.js")
    for gone in ("Request research", "requestResearch", "state.requested", "P.openRow",
                 "F.ScreenTable"):
        assert gone not in js, gone


def test_the_head_follows_the_lists() -> None:
    js = _static_file("watchlists.js")
    follow = js[js.index("  function follow() {") :]
    follow = follow[: follow.index("\n  }\n")]
    for pin in (
        "if (panel.hidden) return;",
        "var lists = P.watchlists();",
        "if (lists) {",  # no list is chosen, and no address written, before the lists arrive
        "want = opens(lists, P.listId, state.defaultId);",
        "if (want !== state.selected || want !== P.listId) select(want);",
    ):
        assert pin in follow, pin
    assert "'fairband.watchlist.default'" in js
    assert "history.replaceState(null, '', '#watchlists' + (id == null ? '' : '/' + id));" in js


def test_delete_clears_a_default_it_removes() -> None:
    js = _static_file("watchlists.js")
    drop = js[js.index("  function drop(d) {") :]
    assert "if (!error && d.id === state.defaultId) setDefault(null);" in drop[: drop.index("\n  }\n")]


def test_show_reads_the_lists_id() -> None:
    js = _static_file("controls.js")
    for pin in (
        "var id = /^\\d+$/.test(String(word)) ? Number(word) : null;",
        "var listed = tab === 'watchlists' && keepList(section);",
        "panels[id].hidden = id !== tab && !(id === 'screen' && tab === 'watchlists');",
        "if (tab === 'screen' || tab === 'watchlists') P.onList(tab === 'watchlists');",
        "P.listId = null;",
    ):
        assert pin in js, pin


def test_the_old_view_is_gone() -> None:
    assert "function openRow(" not in _static_file("app.js")
    page = _static_file("index.html")
    assert "#watchlists .fb-screen { --bar-height: 0px; }" not in page
    assert "#groups, #methodology, #settings, #inbox { overflow: auto; }" in page
    assert "On a watchlist, it posts" not in _static_file("methodology.html")
```

Import `elements` and `text` from `support.page`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run pytest -q tests/web/test_watchlist_page.py`

- [ ] **Step 3: `controls.js`**

Beside `P.onShow = {};` add `P.listId = null;`. Add `keepList(word)`: it sets `P.listId` to the
whole number `word` spells, or null, and answers whether that changed. In `show`:

- `var listed = tab === 'watchlists' && keepList(section);`
- the hash gains `(tab === 'watchlists' && P.listId != null ? '/' + P.listId : '')`;
- the early return also needs `!listed`;
- the panels' line and the `P.onList` line are as the test pins them, the `P.onList` line before
  `P.onShow[tab]` runs. `onList` is not told of any other view: the table keeps its mode while
  `#screen` is hidden, so the Screen's place is put back only when the Screen itself shows.

Bring the comments on `show` and `fromHash` up to date: `#watchlists/<id>`.

- [ ] **Step 4: `watchlists.js`, the head alone**

It no longer draws a table. `rowsOf`, `section`, `requestResearch`, `requested` and
`state.requested` go. The state gains `selected` (a list's id), `next` (a list just created,
until the lists hold it) and `defaultId`, read once from storage inside `try`, a stored value
that is no whole number read as none. `setDefault(id)` stores the id, or removes the key for
null, inside `try`, and keeps `state.defaultId` either way.

`select` and `follow` are these:

```js
  function select(id) {
    state.selected = id;
    P.listId = id;
    history.replaceState(null, '', '#watchlists' + (id == null ? '' : '/' + id));
    P.selectList(id);
  }

  function follow() {
    if (panel.hidden) return;
    var lists = P.watchlists();
    if (lists) {
      var ids = lists.map(function (w) { return w.id; });
      var want = state.selected;
      if (state.next != null && ids.indexOf(state.next) !== -1) {
        want = state.next;
        state.next = null;
      } else if (ids.indexOf(want) === -1) {
        want = opens(lists, P.listId, state.defaultId);
      }
      if (want !== state.selected || want !== P.listId) select(want);
    }
    render();
  }
```

- `P.onShow.watchlists` forgets the selection, `state.selected = null`, then calls `follow`, so
  the header's link opens the default and an address opens its list. `P.onRender` calls `follow`.
- The view: New watchlist with Create and its refusal; with no list, the sentence of the Global
  Constraints; else `head` of the selected list, a refused write's sentence, and Add a company
  with its matches and hint, as today. Delete's dialog as today.
- `head(list, lists, defaultId)`: a `select.control.app-select.app-wl__pick` named
  `aria-label: 'Watchlist'`, its value the list's id as text, an `option` for each list in the
  lists' order; the count and the day, as today; then `Set as default` or `Default`
  (`app-wl__default`, `aria-pressed`), which sets the default to this list or clears it; Rename,
  which turns the selector into the name's field as the title turned into it; Delete.
- The selector's change calls `select(Number(event.target.value))` and draws.
- Create's last step sets `state.next` to the new list's id. Delete's last step is as
  `test_delete_clears_a_default_it_removes` pins it.

- [ ] **Step 5: `app.js`, `index.html`, `methodology.html`, the two decision logs**

- `openRow` goes from `app.js` with its export and its mentions in comments. In
  `tests/web/test_ticker_link.py:74` the row's handler becomes `{"$page": "find"}`.
- `index.html`: `#watchlists` leaves the two shared panel rules and gets
  `#watchlists { flex: none; padding: var(--space-2) var(--space-6); }`. The rules of the old
  sections and their tables go (`.app-wl__table`, the two `#watchlists .fb-screen` rules, the
  card's frame if the head no longer uses it); the empty cell's em dash moves to
  `#screen .fb-screen__name:empty::before`. The comment above the rules describes the new page.
- `methodology.html`: the sentence "On a watchlist, it posts a valuation review for each company
  on the list with no open item." goes.
- Each of the two older specs gains one decision log line, dated 2026-11-22 and in that log's own
  form, that points to the spec of 2026-11-22: the view of 9.6 is replaced; 18.6 is withdrawn.

- [ ] **Step 6: Bring the old tests in line**

In `tests/web/test_app.py`: `test_the_watchlist_requests_research` goes (the server's 409 stays
tested in `tests/web/test_agents_api.py`); the three `test_watchlists_view_*` tests keep only the
pins that still hold and lose the rest; the two pins of the panels' rules follow the new rules.

- [ ] **Step 7: Run the full check, then commit**

Message: `Show one watchlist on its page with a selector and a default, open its rows' drawer there, and drop a list's Request research` followed by the names of the tests removed or rewritten.

### Task 5: The acceptance look, and the backlog

**Files:**
- Modify: `docs/backlog.md` (a Done row, B-285)
- Scratch only, never committed: a data folder, a script and screenshots in the session's
  scratchpad

- [ ] **Step 1: A scratch server.** Make a scratch database (`connect` and `migrate` from
  `fairband.store.db`), attach the live file read-only and copy `policy_versions`, `refreshes`,
  `deciles`, `settings` and, for about twelve symbols, the newest universe rows of `companies`
  and the newest `snapshots` row. Start the branch's server on it:
  `FAIRBAND_DATA_DIR=<scratch>/data XDG_CONFIG_HOME=<scratch>/config uv run python -m fairband serve --port 8499`,
  with `FAIRBAND_FMP_KEY` unset. Create two lists through the scratch server, one with a symbol
  that has no row.

- [ ] **Step 2: The checks**, with `playwright-core` and the cached Chromium, in both themes:

1. A row click on the watchlist page opens the drawer there; the address stays `#watchlists/<id>`.
2. FIND, a filter and a sort each change the list's table; the Screen then shows its own FIND
   empty, no chip and its own sort. A column switched off is off on both.
3. The selector changes the list and the address; a reload keeps the list; with a default set,
   `#watchlists` opens it after a reload; after Delete of the default, the first list by name.
4. Create, Rename, Delete and Add a company work on the selected list, and Create shows the new
   list.
5. The head has no Request research. The drawer's box lies wholly inside the window and the
   drawer at 1280, 1600 and 1920 px, on the Screen and on the watchlist page, and also with
   scrollbars shown in a window 600 px high, where the drawer scrolls and its buttons wrap
   (Chromium hides scrollbars unless launched with `ignoreDefaultArgs: ['--hide-scrollbars']`).
6. A ticker in the Inbox opens the company page; a click on the row's Mode cell changes nothing.
7. The Screen's Filters menu still has its WATCHLISTS section; the list's menu has none.
8. The Screen, scrolled to 5,000 px, is at 5,000 px after a visit to Watchlists and back.

- [ ] **Step 3: Fix what a check finds**, test first, each fix a commit of its own. Stop the
  scratch server: `lsof -ti:8499 -sTCP:LISTEN | xargs -r kill`.

- [ ] **Step 4: The backlog.** Add B-285 to Done in the table's own form: what was built in two
  or three sentences, the spec and this plan, and the commits. A debt row that the rewrite made
  moot (among B-79, B-80) is closed there only where its code is gone; say which in the row.
  This commit is of documents alone and runs the short check of `CLAUDE.md`.

- [ ] **Step 5: Show the founder.** Screenshots of the watchlist page with the drawer open, in
  both themes, and the results of the eight checks. The merge, the live page and the push wait
  for the founder's word.
