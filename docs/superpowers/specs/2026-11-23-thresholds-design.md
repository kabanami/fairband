# The thresholds: design

Status: written 2026-11-23 on the founder's decisions of that day, quoted in the decision log.
The founder decided the three values (margins of safety of 20%, 30% and 40%, a fair band of 0.90
to 1.10, a trim multiple of 1.35), that a change of thresholds shows on the screen at once, that
"Well below" starts at the company's own buy level, and that a published report keeps its text
with no mark. Every other choice below is Claude's, marked *my call* where it is more than a
reading of those decisions, and can be overturned as any other. The founder approved the design
on 2026-11-23.

No value moves. The three thresholds set the levels and the word of a row, and nothing a route
computes reads them. The change does touch three policy values and the engine's designation, so
`docs/method.md` and the Methodology page change in the same commit, the policy becomes v19 and
the method 1.9.

A second design follows this one: a reviewed value that holds until the next review. Its levels
and its word follow the rule of section 5.3 here.

## 1. What this is

A row has four levels, each its value times a factor: the buy level (1 − the margin of safety of
its moat class), the two ends of the fair band, and the trim level. A word says where the price
stands against them: Well below, Below, Near, Above or Well above.

Three things are wrong today.

- **The numbers have no source.** The margins of 25%, 35% and 45%, the band of 0.85 to 1.15 and
  the trim multiple of 1.5 came from the earlier method (v1.7, Step 10), which gives no reason
  for any of them.
- **A change of thresholds waits for a revalue.** A mechanical row stores its levels and its word
  when it is valued. The founder changed his settings on 22 Nov 2026 at 18:50; the rows kept the
  old words until the revalue of 23 Nov at 04:09, which took seven minutes. A reviewed row
  already reads its word on the settings in force, so the two kinds of row disagree in between.
- **"Well below" does not mean "under the buy level".** Its edge is 1 − the Narrow margin for
  every company. GOOG, a Wide company, has a reviewed value of $339.38 and a buy level of $271.50
  at a 20% margin. At $264.00 the price is $7.50 under the buy level, and the row reads "Below".

After this work the defaults follow one published scheme, a change of a threshold shows on every
row with no revalue, and the five words match the row's own four levels.

## 2. Goals, non-goals, anti-goals

Goals:

- The defaults are the founder's three values, in the policy file, so the Methodology page and a
  new user's screen show them.
- A saved change of a threshold is on every row, in the drawer, on the company page and in the
  agents' tools at the next read. No revalue, and no refusal "settings changed: run a revalue".
- A price under a row's buy level reads "Well below" for a Wide, a Narrow and a None row alike.

Non-goals:

- A band, a margin or a trim multiple that depends on the uncertainty of the value, as
  Morningstar's does. The founder chose one band and one trim multiple for every company, and the
  margin stays by moat class.
- A mark on a published report whose stance no longer fits the new levels (the founder's ruling:
  the value did not change, and the row's word shows the difference).
- Any change to a value, a route, the classifier or a flag.

Anti-goals:

- A threshold that changes a value, a flag or an agent's override. If the build finds one that
  does, it stops and says so.
- Two places that compute a word and disagree. One function serves every reader.

## 3. The three values

| Policy value | v18 | v19 | Where the figure comes from |
|---|---|---|---|
| `margin_of_safety` | Wide 0.25, Narrow 0.35, None 0.45 | Wide 0.20, Narrow 0.30, None 0.40 | Morningstar's discount for 5 stars at Low, Medium and High uncertainty |
| `fair_band` | 0.85 to 1.15 | 0.90 to 1.10 | Morningstar's 3-star range at Medium uncertainty |
| `trim_multiple` | 1.5 | 1.35 | Morningstar's 1-star price at Medium uncertainty |

The source is Morningstar's Equity Research Methodology of September 2022 (Exhibit 4) and its
Uncertainty Rating FAQ of July 2022:
<https://www.morningstar.com/content/dam/marketing/shared/research/methodology/705988Morningstar_Equity_Research_Methodology.pdf>.
Each value's `source` in the policy file names it and the founder's decision of 2026-11-23.

Two readings that stood behind the decisions:

- A value from forward earnings is within 15% of the price for about half of companies (Liu,
  Nissim and Thomas, 2002), so a band under ±10% would claim an accuracy no method has.
- Every source that varies the margin varies it with the uncertainty of the value, and none with
  the moat. The margin stays by moat class here, a known difference from the source.

What moves on the live screen, read on the 1,344 rows that carry a word on 23 Nov 2026 (Narrow
1,141, Wide 159, None 44):

| Word | v18 defaults | The founder's settings of 23 Nov | After this work |
|---|---|---|---|
| Well below | 147 | 175 | 183 |
| Below | 144 | 152 | 144 |
| Near | 206 | 129 | 129 |
| Above | 217 | 258 | 177 |
| Well above | 630 | 630 | 711 |

Against the settings in force today, 89 rows change their word: 81 from Above to Well above (the
trim multiple) and 8 from Below to Well below (the row's own buy level).

## 4. Approaches

Three ways to make a change of thresholds show at once.

- **A. Read the levels and the word on the settings in force, and take the three thresholds out
  of the settings hash.** A reader computes them from the stored value, the row's moat class and
  the effective policy. A reviewed row's word is read this way today (`web/rows.py`, `standing`).
  The settings already have the two switches: an effect of "at once" and `hashed` (`policy/
  settings.py`). The cost is that every reader of a level must go through one function.
- **B. A fast pass at each save.** A save of a threshold alone would start a pass that writes a
  new snapshot for every row, repriced from its intermediates with new levels. Every reader stays
  as it is. The cost is a new refresh kind, a run after every save, and a second or more of old
  words on each save.
- **C. Keep the revalue, and say so more clearly.** Nothing is built; the Settings page already
  says "Your settings changed since the last valuation." This is today's behaviour, which the
  founder rejected.

**A is chosen** (*my call*; the founder asked for the outcome, not the way). The hash exists so
that a result names what it was valued under, and the method already keeps a number that moves no
value out of it (`warning_mark_min`, method 4.1). The thresholds move no value, so they do not
belong in it. B keeps a stored copy that can fall behind again.

## 5. The design

### 5.1 Policy v19

`fairband-policy-v19.toml` is v18 with the three values of section 3 and their sources.
`load_policy` reads it. No other value changes.

### 5.2 The first edge is the row's own

The edges of a row of moat class c are 1 − the margin of safety of c, the band's low, the band's
high and the trim multiple: 0.80, 0.90, 1.10 and 1.35 for a Wide row at the defaults, 0.70 for a
Narrow row's first edge and 0.60 for a None row's. The comparison of method 4.10 stays as it is.

| Price is | Word |
|---|---|
| under the buy level | Well below |
| from the buy level, under the band's low end | Below |
| inside the fair band, ends included | Near |
| above the band, under the trim level | Above |
| at or above the trim level | Well above |

`Policy.designation_edges` becomes a function of the moat class, and `designation_for` is called
with the row's class everywhere: the valuation and the reprice (`engine/route.py`), the secondary
valuation (`engine/secondary.py`), a review's write (`web/reviews_api.py`), and the readers of
5.3. Every valued row has a class (a row without one is refused), and a Start-up row has no word,
as today.

The cross-field rule of the settings changes with it: the band's low must be above 1 − the
**Wide** margin, the smallest, so each class's buy level is under the band (today: above 1 − the
Narrow margin).

### 5.3 The levels and the word are read on the settings in force

`margin_of_safety`, `fair_band` and `trim_multiple` become settings with the effect "at once" and
`hashed` false. A save of one changes no settings hash, so no row reads as valued under other
settings and no write is refused for it.

One function gives a record's levels, price ÷ value and word: from the record's stored value, its
moat class, the price it is read at and the effective policy. Every reader calls it, for a
snapshot, a review and a secondary valuation alike:

- the screen's rows, their sort, their filters and their groups, the drawer, the company page and
  the watchlist page (`web/rows.py`, `web/app.py`, `web/research_api.py`, `web/company_api.py`),
  with the row's own edges sent to the page where it draws the price ÷ value figure (`app.js`,
  `gapText`);
- the agents' tools that give a level or a word, and the refs `snapshot:<id>/levels/<name>`,
  `review:<id>/levels/<name>` and `secondary:<id>/levels/<name>` (`mcp/server.py`,
  `reports/refs.py`), so a cite of a level is the figure the page shows;
- the command line's snapshot line (`__main__.py`).

A stored result keeps the levels and the word it was valued with, as a record of that day; no
reader shows them. *My call*: the columns stay, since snapshots are never changed, and the schema
does not move.

The Settings page's captions for the three say that a change shows at once, and the description
of the margin says that each class's figure sets where its rows read "Well below".

### 5.4 Reports

A published report is a record: its text, its cited figures and its stance stay as published. A
report written after this work cites the levels in force through the refs of 5.3. The README's
screenshots stay as they are (`CLAUDE.md`).

### 5.5 The method document, the Methodology page and the versions

`docs/method.md` changes in the same commit: the three rows of 4.1 and the row of the derived
edges, 4.10 (the edges by class, the table above, and that the levels and the word are read on
the settings in force), section 10 (a change of a threshold needs no revalue), the version table
(method 1.9, policy v19) and every other sentence that names an old figure. The Methodology
page's table of the five words names the buy level in place of one figure for all, and its
examples are read again under 1.9.

### 5.6 Going live

The policy version changes, so the live data needs one revalue after the restart, as at every
policy version. The founder's stored settings for the margin and the band equal v19's defaults
and are reset, so his settings hold only what differs from the file. The merge, the restart of
the live server and the push wait for the founder's word.

## 6. Left to the builder

- Where the one function lives and what it is called, and whether the stored row's own columns
  are read through it or beside it.
- Whether the engine still writes the margin of safety as a RULE input of a result
  (`route_steps.py`, `route_decline.py`). The page and the tools must show the margin in force;
  a stored entry may show an older one.
- How the groups of the screen count words when the first edge differs by class
  (`group_rows`).
- The wording of the Settings captions and of the Methodology page's table.
- The tests' form. They must hold the cases of section 7.

## 7. How we know it works

- GOOG's reviewed row, value $339.38, Wide, at $264.00: buy level $271.50, band $305.44 to
  $373.31, trim level $458.16, word "Well below".
- At a price ÷ value of 0.78 a Wide row reads "Well below" and a Narrow row "Below". At 0.65 a
  None row reads "Below", and at 0.59 "Well below".
- At a price ÷ value of 1.35 every row reads "Well above", and at 1.34 "Above".
- On a scratch database, a save of a new trim multiple changes the words of the rows at the next
  read of the screen, with no refresh run, and an override written right after it is accepted.
- The settings hash of a policy with a changed threshold equals the hash without it.
- A snapshot's value is the same number before and after, on every route.

## 8. Decision log

| Date | Decision | Whose |
|---|---|---|
| 2026-11-23 | The fair band becomes 0.90 to 1.10 for every company: "the fairband is too wide I feel", then "I agree with option 1" (±10%, Morningstar's medium level, against a band by moat class) | the founder |
| 2026-11-23 | The margins of safety become 20%, 30% and 40%: "I agree with 20/30/40" (against 15/25/35, and against a margin set by uncertainty) | the founder |
| 2026-11-23 | The trim multiple becomes 1.35: "why not 1.35, just following the morningstar mid threshold?", then "I confirm 1.35". Claude had advised 1.5 on judgment (taxes, and good businesses that keep growing) and agreed that 1.35 has a source and 1.5 has none | the founder |
| 2026-11-23 | The words move with the thresholds at once: "these are just indicators that help a user to navigate in the screen and gives hints on what are some under valued stocks, these should change with the updated thresholds" | the founder |
| 2026-11-23 | "Well below" starts at the company's own buy level, and a published report keeps its text and its stance with no mark, on GOOG's row: "I accept it" | the founder |
| 2026-11-23 | The defaults change in the policy file, not only in the founder's settings: the repository is public, and the Methodology page should show the chosen figures | Claude, not objected to |
| 2026-11-23 | Approach A of section 4; the method becomes 1.9; the stored columns stay | Claude |
