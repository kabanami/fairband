# The refresh experience and five page changes: design

Status: written 2026-11-23 on the founder's decisions of that day, quoted in the decision log
(section 7) with their spelling corrected. Every other choice is Claude's, marked *my call* where it is more than a reading of
those decisions, and can be overturned as any other. The founder saw the mockup (version 3) and
approved the design on 2026-11-23.

No mechanical value moves, and no policy value, schema or method version changes. The work is on
the page and on the two routes that feed it. One rule of the brand book gets a narrow exception
(4.8).

## 1. What this is

Six parts, built in one plan.

1. **The refresh layer.** A refresh of the whole screen darkens and locks the page until it ends.
2. **The end signal.** When new figures land, the figures that changed are highlighted, and the
   status line counts them.
3. **The page follows any refresh.** A bug: the open page does not show the figures of a refresh
   it did not start (an agent's), until the browser reloads it. Reproduced in a headless browser
   on 2026-11-23: the Screen kept the old price 8 seconds on, and after a visit to the company
   page and back.
4. **The phase follows the review.** A bug: OTEX's review (770) values it as Mature Stable under
   the `phase` override 87, and the Screen, the drawer and the company page show Mature Growth,
   the snapshot's. RELX and FRVO show the same difference.
5. **Groups becomes Statistics**, each of its rows a link to the Screen, and the menu takes a new
   order.
6. **The meter's scale.** A price far from the value presses the fair band into a few pixels and
   its two labels overlap (Agilent, $170.38 on a value of $61.77: the band takes 8% of the
   width). The scale comes from the levels alone and a price beyond it is pinned at the end.

Why: on 2026-11-23 the founder ran a price refresh and could not tell that it had run or what it
had changed. Nothing marks the end of a run, and a run started elsewhere does not reach the page.

## 2. Goals, non-goals, anti-goals

Goals:

- A run of the whole screen cannot be missed, and nothing on the page can be used under it,
  except by the reader's own choice on a long run.
- The end of any run shows what changed, in the table and in one count.
- The page never shows figures older than the server's for more than 30 seconds.
- A meter reads the same on every company: the zones in the same places, the labels apart.

Non-goals:

- No change to what a refresh does, to its stages or to its record.
- No new column, no new view. Statistics is the Groups view under its right name.
- Server-sent events or a socket: the page keeps asking, as today.

Anti-goals:

- An agent's work that interrupts the reader: a lock or a darkening he did not start.
- Motion as decoration: a spinner, a pulse, anything that moves while nothing changes.
- A pinned price that reads as a true position.

## 3. Approaches

**How the page learns of a run it did not start.** (a) Ask `/api/refresh/current` on the Inbox's
30-second cycle while idle, every 2 seconds while a run is alive. (b) Carry the latest refresh's
id on the Inbox read. (c) Server-sent events. Chosen: (a). It adds one small read to a cycle the
page already keeps, and no new route. (b) ties two unlike reads together; (c) adds a long-lived
connection and a new failure to handle for a gain of seconds.

**How the page is locked.** (a) One fixed layer over the whole page, with everything under it
made `inert`. (b) Disable each control and link. Chosen: (a). One rule covers every view, the
keyboard included; (b) must be repeated in every script and will miss a control.

**How the end is shown.** (a) Highlight the cells whose figure changed, with a count in the
status line. (b) A notice alone. (c) Highlight whole rows. Chosen: (a). It answers "what
changed" where the reader looks; a notice alone says only that the run ended, and a whole row
says less than its cells.

## 4. The design

### 4.1 The refresh layer

- It shows while a run of the whole screen is alive: kind `price`, kind `full`, and a `revalue`
  that names no company. It shows whoever started the run: this page, another browser tab, a
  change in Settings. *My call.*
- It never shows for a run of named companies: a `scoped` refresh, a `revalue` of one company
  (an agent's, a moat write's). Under such a run nothing darkens, nothing fades and nothing
  locks. The progress the server sends must say which of the two a run is; today it gives the
  kind alone, and a `revalue` can be either.
- The layer covers the whole page, the header included, with a dark scrim from the design tokens
  (`tests/web/test_design_tokens.py` applies). Everything under it is `inert`: no pointer, no
  keyboard, no focus. A change of the address (a hash, Back) is put back while the lock holds.
  Escape does not close it.
- In its centre, one panel on the raised surface: what runs ("Refreshing prices", "Refreshing
  all", "Revaluing"), the stage word, the run bar with its counts (`RunProgress`, as the status
  line draws it today) and Cancel, which does what Cancel does today.
- On a `full` run and on a whole `revalue` the panel has a second button, **Keep reading**. It
  removes the layer for that run, on that page. The run goes on, and the page is as it is under
  a run today: the run bar in the status line, the tables' figures faint, Cancel in the header.
  A price refresh (about 26 seconds) has no such button. A reload of the browser page brings the
  layer back. *My call* on the reload.
- A run that fails or is cancelled removes the layer. The status line says how it ended, as
  today.
- Motion: the scrim and the panel fade in and out over 150 ms, and the run bar's fill eases to
  each new count. Nothing spins. Under `prefers-reduced-motion` the bar's fill does not ease,
  since it moves; the fades of 4.1 and 4.2 run all the same, a fade of colour being no movement.
  The founder's own browser reports that setting (found on the mockup, 2026-11-23), so a rule
  that stopped the fades would stop them for the one reader who asked for them.

### 4.2 The end signal

- Whenever the page reads its rows again after a run ended (4.3), it compares each row with the
  one it held, by ticker, on the figures a row shows: the price, the value, the levels, price ÷
  value, the designation, the reviewed value, the phase.
- Each cell whose figure changed is highlighted for about 1.2 seconds, a tint that fades to
  none, on the Screen and on the watchlist page. The tint is a grey, lighter than the table's
  ground, which means nothing else on the page. The founder chose it on the mockup over the
  accent's teal, which reads as the buy zone's green.
- A changed price carries ▲ or ▼ before it, in `ink-muted`, which fades with the tint: the
  direction, with no colour. Green for a higher price and red for a lower one were set aside:
  on this page green means cheap against the value and red expensive, so a falling price would
  go red beside a designation that turns green. The company page's head does the same for its
  price. `ScreenTable` is the design system's, so the cell's class is a `// fairband:` patch. A
  row that is new, or gone, is not highlighted. The tint fades under `prefers-reduced-motion`
  too (4.1).
- After a run of the whole screen the status line adds a count to its sentence: "· 1,546 prices
  changed", "· 37 values changed", both where both moved, "· no price changed" after a price
  refresh that moved none (one run before the market opens). The page counts them from its own
  comparison, so the count stands until the next run or a reload. *My call*: no count is
  stored.
- After a run of named companies there is no sentence: the line stays about the last run of the
  whole screen (the founder, 2026-11-22). The company's cells are highlighted.

### 4.3 The page follows any refresh

- While no run is alive the page asks `/api/refresh/current` every 30 seconds, on the Inbox's
  cycle: paused while the page is hidden, at once when it shows again. While a run is alive it
  asks every 2 seconds, as today.
- The page keeps the id of the last refresh its rows were read under. A read that shows a run
  alive, or a last refresh with another id, is a run to follow, whoever started it.
- When such a run has ended, the page reads again: the rows, the open drawer, Statistics when it
  shows, and the open company page when the run covered its company (a run of the whole screen,
  or one that names it). Then 4.2 applies. A company page whose company the run did not cover
  is left as it is, so a reader is not moved. *My call.*

### 4.4 The phase follows the review

- Where a review fills a row's Reviewed column (the Tier 2 design, 18.1), the row's `phase` is
  the review's result's phase. Elsewhere it is the snapshot's, as today. A secondary valuation
  has no phase and changes none.
- The company's detail (`GET /api/companies/{symbol}`) answers the same shown phase beside the
  snapshot's result, and the heads of the drawer and of the company page draw their badge from
  it.
- The Screen's phase filter and Statistics by phase read the shown phase. The Methodology page's
  count of companies in each phase stays the classifier's: that page describes the classifier.
- The classifier's phase stays where the engine's own figures are: the Research tab's evidence
  and the bridge's `phase` line.
- The row's route and the columns read from the intermediates stay the mechanical row's (18.1).
  A row whose review changed its phase can so show a column of the route it left. Filed in the
  backlog, not built here.
- The Tier 2 design's 18.1 takes a dated line. If `docs/method.md` or the Methodology page names
  the row's phase or the groups, each changes in the same commit.

### 4.5 Statistics

- The view Groups is named **Statistics**, in the menu and in its address, `#statistics`. The
  old `#groups` opens it. *My call.*
- Its table is as today: for each sector, industry, phase or cap band, the companies, the
  companies valued, the median price ÷ value and the share below value.
- Each group's name is a link. It opens the Screen with that one filter set and every other
  filter and the find cleared: the sector; the industry with its sector, which the industry menu
  needs; the phase; the cap band. The rows `none` and `unclassified` are no links: no filter
  matches a field a row lacks.
- So that a link's count is the Screen's, Statistics reads what the Screen shows: the row's
  shown phase and the row's own value, the reviewed one where Reviewed is filled. This reverses
  the Groups rule of plan 3 (the mechanical value alone), and the caption under the table says
  the new rule. *My call*, after the founder's rulings that a review's figures stand in for the
  engine's on the page (2026-11-08 on the levels, 2026-11-23 on the phase).

### 4.6 The menu

Screen, Watchlists, Statistics, Methodology, Settings, Inbox.

### 4.7 The meter's scale

- `BandMeter` sets its scale from the value, never from the price: from 0.45 to 1.55 times the
  fair value. So the fair value is in the centre and, under policy v19, the fair band takes
  about 18% of the width and the trim level sits at 82% on every meter. The buy edge differs by
  moat class alone (0.80, 0.70, 0.60 times the value).
- The scale widens only for a level that falls outside it (a changed setting), never for the
  price.
- A price inside the scale is drawn to scale. A price beyond either end is pinned at that end,
  with a break mark on the track before it, two short strokes, so its place does not read as
  true. Its title and the head keep the true price and price ÷ value. The reviewed value's
  marker, where a caller passes one, follows the same rule.
- The band's two labels are anchored outward: the low one ends at its tick, the high one starts
  at its tick. They cannot overlap. Each still keeps 8px clear of the price marker, as today.
- Every meter takes it: the drawer's, the company page's and the Research tab's. The change is a
  `// fairband:` patch in the bundle.

### 4.8 The brand book's rule on motion

The brand book says: "Motion. Effectively none." Three motions are allowed from now, and no
other: the refresh layer's fade, the run bar's fill, and the highlight of a changed figure.
`CLAUDE.md`'s paragraph on the brand book takes the line, with the founder's name and the date.

## 5. Checks

- Tests first, in the form of the page's tests today (node for the scripts, pytest for the
  routes).
- A look in a headless browser on a scratch database before the review: the layer and Keep
  reading on a simulated run; the highlight; an agent's run followed with no lock; each meter at
  the drawer's 288px with a nine-character price and with a price pinned at each end; both
  themes; the scrollbars shown.
- Python and page files both change, so the work is in a worktree, and the live server needs a
  restart.

## 6. Left to the builder

- How the progress and the last refresh's record say that a run names companies, and which.
- The scrim's token, the tint's token and the break mark's drawing, each as the mockup shows it
  (`.superpowers/brainstorm/2553069-1795455894/content/refresh-and-meter-v3.html`).
- Whether `/api/groups` keeps its name; how the Methodology page reads the classifier's counts.
- Where the row carries the classifier's phase, if a reader of it remains.
- The README's screenshots show the old menu and stay as they are (`CLAUDE.md`); whether to take
  them again is the founder's, asked at the merge.

## 7. Decision log

| Date | Decision |
|---|---|
| 2026-11-23 | The founder: "the whole refresh experience should be animated, meaning when a refresh happens the page should be darkened indicating that something is being loaded (prices are being refreshed, same with refresh all), and the user should not be able to navigate any pages until its done. Also, there should be some sort of animation once its done indicating that prices are updated." |
| 2026-11-23 | The founder chose Keep reading on Refresh all ("Option B"), and no lock and no darkening for an agent's refresh ("Yes agree with option B"). |
| 2026-11-23 | The founder on the phase: "if the agent on a review changes the company stage, it should override the existing value." |
| 2026-11-23 | The founder kept Groups as Statistics with a link from each row ("I like option 2") and set the menu: "Screen Watchlists Statistics Methodology Settings Inbox". |
| 2026-11-23 | The founder on the meter: "if there is a price too high for trim, just have the price at the end of the spectrum, regardless if its correct equal spacing to the fair value", for a price too high or too low. He agreed that every meter then has the same spacing. |
| 2026-11-23 | The founder: the two bugs (4.3, 4.4) are built with the rest of the plan, not ahead of it. |
| 2026-11-23 | On the mockup (version 3) the founder asked that the highlight fade out, asked about green and red for a price's direction, and chose: "grey with the arrow looks good, and the new scale looks good". The mockup is `refresh-and-meter-v3.html` under `.superpowers/brainstorm/`, not committed: it shows real prices. |
| 2026-11-23 | Claude's calls: the layer for a whole run whoever started it; the 30-second cycle; the count kept on the page alone; a company page left alone by a run that did not cover it; Statistics on the shown value; `#groups` kept; the scale at 0.45 to 1.55 times the value; the labels anchored outward; the three motions of 4.8. |

## 8. What the build changed

Rulings made while the plan was built (2026-11-23 and 24), each a reading of a section above; no
figure moves.

- 4.1: the focus goes to the panel, not to a button, so a key pressed by reflex neither cancels a
  run nor lifts the lock; Tab reaches the buttons. The address put back while locked is the one
  the page held as the lock began. Keep reading also stands on any run after a status read that
  failed, so the reader is never held behind the layer while the server does not answer.
- 4.2: a company valued for the first time, its price none before, is tinted and counted, with no
  arrow. The count's own tint plays once, as the rows land.
- 4.2: the arrow takes no room: a box of no width and no height on the price's baseline, its
  glyph 4px before the price. Set in the line, it widened the price's column, and every column of
  the Screen moved about 11px as the arrows came and went (the look in a browser, 2026-11-24).
- 4.3: a run the server lists as running while it reports no run alive (one of the command-line
  tool) is not followed until its record says it ended. It draws no bar and no layer.
- 4.3: with no run alive, a status read that failed says "The page asks again every 30 seconds."
- 4.5: an industry group none of whose rows has a sector has no link.
- 4.7: the scale also widens for a level within 0.10 times the value of an end, so an outer zone
  keeps a width. Under policy v19 no meter widens.
- 4.7: a pinned reviewed marker takes no break mark; the break is for a pinned price alone. No
  caller passes a reviewed value beyond the scale.
- 4.7: a marker inside the scale stands where its figure lies, but never nearer an end than the
  7px a pinned one takes. A price at 0.45 or 1.55 times the value stood on the track's end, its
  dot 6.5px off the meter (the look, 2026-11-24).

The look of section 5 is `2026-11-23-refresh-experience-mockup/` (`README.md`, `look.mjs`).
