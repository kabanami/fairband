# The watchlist page: design

Status: written 2026-11-22 on the founder's requests of that day, quoted in the decision log. The
founder decided that a row opens the drawer on the watchlist page, that the page works as the
Screen does, that it shows one list chosen by a selector with a default the user sets, that a
list has no Request research of its own, that the drawer's Request research box must stay
inside the window, and that the Inbox's ticker opens the company page. Every other choice below is Claude's, marked *my call* where it is more than a
reading of those requests, and can be overturned as any other. Built on 2026-11-22 as backlog
item B-285; the decision log's last lines say where the build differs from this text.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value, so `docs/method.md` does not change, and neither do the method version, the policy
or the schema. No Python changes: no route, no store, no MCP tool. The changes are in the page
files under `src/fairband/web/static/` and in their tests.

## 1. What this is

Today the Watchlists view draws every list on one page, each as a section with a plain table: no
FIND, no Filters, no Columns menu, no sort. A click on a row leaves the view. It shows the Screen
with the drawer open, and the Screen's table stands at its first row, GOOG's own row about
21,000 px below (`watchlists.js`, `onOpen`; `app.js`, `openRow`). The spec of 2026-11-04 recorded
this as a stopgap of the build. Each list also has a Request research button that posts a
valuation review for every company on it with one click, with no confirmation, and starts no
agent. And in the drawer, the box that Request research opens stands from the button's left edge:
81 px of its 254 px are outside the window at widths of 1280, 1600 and 1920 px. The Inbox view's
ticker has the row's fault: a click on it shows the Screen with the drawer open.

After this work the watchlist page is the Screen's table and the Screen's drawer, on the
companies of one list, with a row of watchlist controls above the table.

```
[ Mag7 ▾ ] 7 companies · created 22 Nov 2026  [Set as default] [Rename] [Delete]  [New watchlist] [Create]
[ Add a company ]
FIND [______]                    7 companies  [Filters ▾] [Columns ▾]  |  Notes        Close
TICKER ▲  COMPANY  PHASE  FAIR BAND  MECHANICAL  REVIEWED  PRICE ...   |  GOOG  4 MATURE GROWTH
▶ AAPL ◆  Apple Inc.            ...                                    |  $277.73  BELOW
▶ GOOG ◆  Alphabet Inc.         ...   (selected)                       |  [Company page] [Request research]
```

## 2. Goals

1. A click on a watchlist's row opens the drawer beside the list's table. The view stays.
2. The list's table has the Screen's controls: FIND, Filters, the Columns menu and the sort on a
   column head, working on the list's companies.
3. The page shows one list. A selector chooses it. The page opens on the default list, which the
   user sets on the page.
4. Research is asked for one company at a time, from the drawer or the company page, as on the
   Screen. A list has no Request research.
5. The drawer's Request research box opens inside the window.
6. A click on a ticker in the Inbox opens the company's page.
7. No second copy of the table, the drawer or the narrowing code.

## 3. Non-goals

- A default stored on the server. The browser keeps it (7.3).
- Any change to the Screen view itself, to its Watchlists group in Filters, to the mark's popup,
  to the company page, or to what the drawer shows.
- Any change to the Inbox view but its ticker (11).
- Any change to the watchlist routes, the `watchlists` MCP tool or the inbox routes. Work items
  already posted from a list stay as they are.
- The debts on file for this view and the popup (B-78, B-79, B-80, B-83, B-230, B-246). Where the
  rewrite removes the code a row is about, the builder closes that row and says so; it fixes none
  on purpose.

## 4. Anti-goals

- A row click that changes the view.
- A control that posts work items for many companies at once.
- What the reader does on the watchlist page changing the Screen's FIND, filters or sort, or the
  reverse.
- A second table with its own bar in the document (5).

## 5. Constraints

- The design system's `ScreenTable` gives its FIND field the fixed id `fb-q` and looks it up by
  that id (`design-system/components/bundle.js`); `app.js` finds the bar by `.fb-screen__bar` and
  the scroller by `.app-main`. So the document holds one table with a bar at a time.
- The live server reads the page files from the main checkout's working tree. The build happens
  in a git worktree, so the live page stays as it is until the merge.
- The repository is public. Test fixtures are synthetic. The README's screenshots stay as they
  are.
- The Methodology page loses one sentence (9). `docs/method.md` has no sentence about a list's
  Request research and stays as it is.

## 6. Approaches

**A. One mount draws both views (chosen).** The Screen's own table and drawer in `app.js` draw the
watchlist page too, on the selected list's rows; `watchlists.js` keeps the list's head and its
writes. One table, one drawer, one `narrow`. It costs a second set of FIND, filters and sort in
the Screen's state and a change to how `controls.js` shows the two views.

**B. A full table and a drawer slot in the Watchlists view's own root.** It keeps the two views
apart, but two tables with a bar clash on `fb-q` and on the bundle's own lookup, so the bundle
would change, and the drawer would be drawn in two roots.

**C. The Watchlists link as the Screen with its Watchlists filter set.** The least code, but the
selector, Add a company, Rename and Delete have no place, a symbol with no row on the Screen
could not show, and FIND and the filters would be the Screen's own.

The founder asked whether the Screen's and the drawer's code would be reused and approved A on
that answer.

## 7. The page

### 7.1 The table and its controls

- The table is the Screen's `ScreenTable` with the Screen's props: FIND, Filters, the Columns
  menu, the sort, the mark and its popup, the ticker's link to the company page, the mechanical
  value's hover and mark, Top.
- Its rows are the selected list's companies: the Screen's rows for the list's symbols, and a
  symbol with no row as its ticker alone with an em dash in every other cell, as today
  (`rowsOf`). Such a row matches FIND by its ticker and no filter, and stands after the rows
  that have data, by ticker, whatever the sort (*my call*).
- The bar's count is of the list: "7 companies", or "3 of 7" when narrowed.
- The page keeps its own FIND text, filters and sort, apart from the Screen's (*my call*, said to
  the founder and approved). The sort is the server's, read from `/api/screen` with the sort's key
  as the Screen reads it; the builder decides how the two views hold their rows. FIND and the
  filters clear when the selected list changes; the sort stays (*my call*). None is saved: a page
  load starts with the whole list, as the Screen starts with the whole screen.
- The Columns choice is the Screen's, one choice for both views, as today (*my call*).
- The page's Filters menu has no Watchlists section, since the selector chooses the list
  (*my call*). The Watchlists column still names a company's lists.
- The header's finder stays on this view (*my call*): the table's FIND only narrows the list, and
  the finder is the way to any other company.

### 7.2 The drawer

- A row click, or Enter or Space on a focused row, opens the Screen's drawer beside the list's
  table, the row marked as selected. The ticker still opens the company page.
- It is the one drawer the Screen has, every part the same: Notes, Close, the head, the band,
  Company page, Request research with its box and the open item's line.
- Escape closes it on this view as on the Screen. It stays open when its row is narrowed away,
  when its company leaves the list and when the selected list changes, as the Screen keeps it.
- One drawer serves both views: a drawer open on one is open on the other (*my call*).
- `openRow` goes: the Watchlists view and the Inbox view (11) were its two callers.

### 7.3 The selector and the default

- A selector at the head's left lists the watchlists by name, as `/api/watchlists` orders them,
  and shows the selected one. The default list's entry says so.
- The page opens on, in this order: the list the address names; the default list; the first list
  by name. An id that names no list counts as none.
- The address names the selected list, `#watchlists/<id>`, written as a change of the company
  page's tab is written, so the browser's Back does not step through the lists. The header's
  Watchlists link is `#watchlists` and opens the default (*my call*).
- **Set as default** marks the selected list as the default and shows that it is; a second press
  clears it (*my call*). The browser's storage keeps the list's id, as it keeps the Columns
  choice, and the page works without storage: the default then lasts until the page reloads
  (*my call*, said to the founder and approved). A stored id that names no list is ignored.

### 7.4 The list's controls

- For the selected list: its count and the day it was made, Rename and Delete with its dialog,
  and Add a company with its matches, each as today.
- New watchlist and Create stay. After Create the page shows the new list, and its Add a company
  field takes focus, as today. After Delete the page shows the default list, or the first by
  name.
- With no list, the page shows New watchlist, Create and today's sentence, "No watchlists yet.
  Create one here, or press the mark beside a ticker on the screen.", and no table.
- A refused write's sentence stands under the head, as today.

## 8. Request research on a list goes

The head's Request research button, its run (`requestResearch` in `watchlists.js`), its counts in
the meta line and their state go, with the test of them. The drawer's and the company page's
Request research are the ways to ask, one company at a time. The hover on a mechanical value
already says so and stays.

## 9. The documents

- The Methodology page, "Where to read them": the sentence "On a watchlist, it posts a valuation
  review for each company on the list with no open item." goes.
- This document's decision log is the record. The spec of 2026-11-04 (9.6 and its decision log's
  line on the row) and the Tier 2 spec (18.6) each gain a decision log line that points here.
- The script comments that describe the old view and a list's Request research follow the code.

## 10. The drawer's Request research box

The cause is one rule in `index.html`, `.app-request .fb-menu { left: 0; right: auto; }`: the box
stands from the button's left edge, and in the drawer the button is the second of two, near the
window's right edge. The company page's head already stands its box from the button's right edge
(`.app-company__actions .app-request .fb-menu`). In the drawer the box stands from the button's
right edge too, so it lies inside the drawer's width. The builder checks every place that draws
`.app-request` before it changes the shared rule.

As built: the right edge alone was not enough. A scrollbar in the drawer makes its two buttons
wrap, and the box, fixed to the button, then passed the drawer's left edge. The drawer's box is
fixed to the row of buttons instead, and both places share one rule for the right edge.

## 11. The Inbox's ticker

Today an item's ticker in the Inbox is a link with a click of its own, which opens the company's
drawer on the Screen (`inbox.js`, `row`; `P.openRow`). It becomes a plain link to the company
page, the address `companyHref` gives, `#company/<symbol>`, the page's Overview, as the ticker is
on the Screen and on a watchlist. It has no click of its own, so the browser's own ways of
opening a link work. The row has no click today and gains none: a click on a row outside its
ticker, its buttons and its report link does nothing. The link to an item's report stays as it
is.

## 12. Tests the builder must write

Tests come first, each seen to fail.

- The pure parts as helpers the node tests can call (`tests/web/page.mjs`): which list the page
  opens on, given the address's id, the stored default and the lists; a list's rows from the
  Screen's rows and the list's symbols, the symbol with no row among them; the narrowing of those
  rows by FIND and the filters.
- The page tests in `tests/web/test_app.py`, in the file's own manner, for: the row's open staying
  on the view; the page's own FIND, filters and sort; the selector, the address and the default;
  the Filters menu without its Watchlists section; the head without Request research; the
  Methodology page without its sentence; the rule that places the drawer's box; the Inbox's
  ticker as a link to the company page with no click of its own, and no `openRow`.
- The tests of the old view that no longer hold are rewritten or removed, each named in the
  commit that does it.

## 13. Acceptance

A look in a headless browser on a scratch database with two lists, in both themes:

1. A row click on the watchlist page opens the drawer there; the address and the view stay.
2. FIND, a filter, a column switched off and a sort each change the list's table, and the Screen
   shows none of them afterwards, but for the column.
3. The selector changes the list; a reload keeps it; Set as default decides what `#watchlists`
   opens after a reload; a deleted default falls back to the first list by name.
4. Create, Rename, Delete and Add a company work on the selected list.
5. The head has no Request research, and the drawer's opens its box wholly inside the window at
   1280, 1600 and 1920 px, on the Screen and on the watchlist page.
6. A click on a ticker in the Inbox opens the company's page; a click elsewhere on the row does
   nothing.
7. The Screen view works as before: its table, its drawer, its Watchlists filter and the popup.

Then the founder's own look before the merge.

## 14. Left to the builder

- How `app.js`, `watchlists.js` and `controls.js` share the work: which panel holds the table on
  this view, how the head reaches it, the names of the new state and helpers.
- Where the head stands, in the scroller above the table or above it, so that the sticky bar and
  the header cells behave as on the Screen.
- The parts and the words of the selector and of Set as default, from the design system's bundle.
- How the Filters menu leaves its Watchlists section out, with the smallest change to the bundle.
- The style rules, and which rules of the old view go.

## Decision log

- 2026-11-22, the founder: "it takes me to the screen page and shows the drawer. That is not the
  correct behavior, it should show me the drawer in the watchlist page."
- 2026-11-22, the founder: "the watchlist should have the similar controls to the drawer, like
  filters etc.", then "sorry I meant similar behavior to the screen, not drawer".
- 2026-11-22, the founder: "the page should not show all watchlists together in one page. There
  should be a selection or dropdown where I can select a watchlist, and the page just shows that
  watchlist, with a default watchlist that the user can set."
- 2026-11-22, the founder: "we should not have a request research button for all companies in the
  watchlist, the behavior should be similar to the one in the screen page, click on a company, a
  button in the drawer".
- 2026-11-22, the founder, on the drawer's box: "the half of the div or box that opens is out of
  the screen to the right."
- 2026-11-22, the founder, on the Inbox: "when the user clicks on the ticker, it should take the
  user to the company page. If ths user clicks on the row, nothing should happen."
- 2026-11-22, the founder approved the design as Claude stated it, with approach A, the page's own
  FIND, filters and sort, the Columns choice shared, the default kept in the browser and the list
  named in the address. He asked whether the Screen's and the drawer's code would be reused; the
  answer was yes, with no second copy.
- 2026-11-22, the build (Claude): built as planned, with these differences. The drawer's box is
  fixed to its row of buttons (10, as built). A symbol with no row stands last by ticker
  whatever the sort (7.1). A failed read of a list's rows shows its sentence on the watchlist
  page alone, and the Screen keeps its table. Escape in the name's field, in Delete's dialog, in
  Add a company and in the header's finder closes that alone and leaves the drawer open. The
  bar counts one company in the singular. Accepted on a scratch database in a headless browser,
  49 of 49 checks, in both themes; the leftovers are backlog item B-286.
