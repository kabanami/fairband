# Removing the GuruFocus dependency: design

Status: written 2026-11-19 for backlog items B-254 to B-261. The decisions are the founder's, of
2026-11-19, and stand in `docs/gurufocus-removal.md` ("the decision document" below). This design
does not repeat them and does not reopen them. It settles what that document leaves to the build,
and the seven points where the document and the code or the stored data disagree (section 5),
which the founder ruled on the same day ("Approved", the decision log). Every other choice below
is Claude's, marked *my call* where it is more than a reading of the decisions, and can be
overturned as any other. The founder approved this design on 2026-11-19 ("Approved"); the plans
are `docs/superpowers/plans/2026-11-19-gurufocus-removal-plan-1.md`, `-plan-2.md` and
`-plan-3.md`.

Three plans build it, each with its own live steps and readout:

| Plan | Backlog rows | What moves | Method | Policy | Schema |
|---|---|---|---|---|---|
| 1 | B-255, B-256, B-257 | no value | 1.6 | v16, unchanged | 009 |
| 2 | B-258, B-259 | Mature Stable values | 1.7 | v17 | 009 |
| 3 | B-260, B-261 | the moat class of every row | 1.8 | v18 | 010 |

GuruFocus keeps working until plan 3 ends: after plans 1 and 2 a user with a GuruFocus key still
reads the Moat Score from it, and a user without one reads the class None on every row, as today.

## 1. What this is

Fairband needs two paid data sources, FMP and GuruFocus. A second paid source is the largest
barrier for a user of the public repository. After plan 3 Fairband makes no GuruFocus call and a
user needs one key.

## 2. Goals, non-goals, anti-goals

Goals:

1. Each of the five GuruFocus items is replaced or dropped as the decision document rules.
2. Each plan reproduces the acceptance figures of refresh 68 (section 10) before its live steps.
3. One class of moat is in force for a company, and one value under it: the mechanical value, the
   reviewed value, the levels and the pages read the same class.
4. The reader of the screen sees, by one mark and on request, that a mechanical value may not be
   sound.

Non-goals:

- No change to a decision of the decision document, and no alternative to one.
- No new data source. Yahoo's line and the SEC's tags stay out (decision document 2.5).
- B-162 (share classes), B-253 (the bond in the universe), B-199 and B-190 (a pending split) are
  not built here.
- The README's screenshots in `docs/images/` are not redrawn (`CLAUDE.md`).

Anti-goals:

- A word of trust on a row ("high confidence" and words like it).
- A block of text in plain view where the decision asks for a visual cue.
- A class copied from GuruFocus, Morningstar or another vendor.
- A second class for one company: a review that values under another class than the mechanical
  value.
- Vendor data in the repository: the test scripts, the pickles, the reference database and the
  screenshots of the look stay outside it.

## 3. Constraints

- **The method documents change with the engine.** `docs/method.md` and the Methodology page
  (`web/static/methodology.html`) change in the same commit as any change to the engine, the
  classifier or a policy value, and a change of method version re-reads the page's examples
  (`CLAUDE.md`). `tests/test_method_doc.py` pins the last row of section 11 as the 1.5 row
  (`rows[-1]`); each plan's version row moves that pin.
- **A price refresh refuses a snapshot of another method version**, so each plan's live steps
  end with a revalue.
- **The repository is public.** Nothing under
  `~/.local/share/fairband/research/gurufocus-removal-2026-11-19/` is committed. Test fixtures
  are synthetic.
- **The reference database.** `fairband-refresh-68-reference.db` in that folder is a copy of the
  live database of 2026-11-19, at refresh 68 (9.3 GB, made with SQLite's backup, quick check
  ok). Every acceptance run reads it, or a copy of it; the file itself is never written. The
  acceptance figures then hold whatever the live database holds by the day of a plan.
- **Subagents** run on Opus 5.5 at xhigh (the founder, 2026-11-10).

## 4. Approaches

The decisions fix what is built. Four choices of how were open.

**One design and three plans** (the founder's structure). The cut follows what moves: plan 1
moves no value, plan 2 moves Mature Stable alone, plan 3 moves the class. A readout after each
plan then has one cause.

**How an agent's class reaches the table** (section 8.6). Considered:

1. *A write of its own, `moat_set`, on the same route as the owner's control* (taken). The table
   is the one place a class lives. `moat.class` stops being an input an override may set, so no
   review can hold a second class, and the bridge (the list of an agent's changes between the
   mechanical and the reviewed value) has no moat line: the mechanical value already holds the
   class.
2. *`override_add` with `moat.class`, mirrored into the table.* The agent's call would not
   change. But the override would stay applied in the review, and an owner's later class would
   then meet an agent's class in the same company: the review under one, the mechanical value
   under the other. Every write of the owner would have to drop the agent's override. Left.

**How the file reaches the table** (section 8.4). Considered: a load at every refresh that
values, in a stage before the value stage (taken, the decision document's 6.4 item 4); a load at
the server's start only (left: a command-line refresh would miss it); a load inside a migration
(left: a migration runs once, and a later file must reach every user).

**How a company is valued again at once** (section 8.6). Considered: a revalue of the one
company inside the request, on the stored facts, with no vendor call (taken); a scoped refresh
(left: it fetches every call again, about thirty FMP calls, and needs a key); waiting for the
next refresh (left: the decision asks for "at once").

## 5. Where the decision document and the code or the data disagree

The founder ruled on each on 2026-11-19 (the decision log).

1. **The old moat verdicts.** The decision document (6.7) says 25 of the 28 reviews carried
   GuruFocus's class through and said nothing. The database holds a moat verdict with reasons in
   every report (`judgments`, kind `moat`): 33 reports on 31 companies, 28 of them "the class
   stands", written while the class found was GuruFocus's and the moat was no standing step.
   After the 74 corrections the file differs from a stored verdict on two companies: CRM (report
   7: Wide stands; the file: Narrow, by the rule for a low return after large purchases) and FRVO
   (report 22: None stands; the file: Narrow, the rule's class for fewer than ten years; a
   refused row, so no value moves). **Ruling:** the file stays as the decision document has it.
   Only the three applied `moat.class` overrides (TTMI, NVO, RELX) become rows of an agent
   (8.3). CRM's reviewed value moves at plan 3; it is the one reviewed value the class moves. The
   sentence of CRM's log entry, "not a judgment", is corrected in the decision document when plan
   3 is built: the report confirmed GuruFocus's Wide before the standing step existed.
2. **The rule as it ran.** The run behind the counts of 6.6 differs from the text of 6.5 in
   three places that change classes: the sector fallback ranks a company among its sector's
   small industries only; a company in Start-up, Young Growth or High Growth is always Narrow,
   never None (60 rows of refresh 68 meet the None test and are Narrow); the cyclical list holds
   neither Aluminum, Silver nor Uranium, and one string that matches no company. The text is
   also silent on six readings (8.2). **Ruling:** `method.md` states the rule as it ran, since
   the counts and the 74 corrections rest on that run. Aluminum, Silver and Uranium join the
   list, which changes no class, and the dead string goes.
3. **A reason.** The brand book says an input change without a reason is not saved
   (`values-and-provenance.md`, "Reasons"; `TaggedInput.md`). The decision document (6.4 item
   10) says the owner need not give one for a moat class. **Ruling:** the decision stands.
   `CLAUDE.md`'s brand-book line records the exception; the archive does not change.
4. **A removed setting.** `nri_flag_share` and `refresh.gf_reuse_days` are settings. A stored
   value for a name that is no longer a setting makes every refresh and every policy read refuse
   ("<name>: not a setting", then "settings: …; reset it on the Settings page"). **Ruling:**
   Fairband ignores a stored value of a removed setting and deletes it (7.4, 8.9). The founder's
   database holds no stored setting.
5. **A note that reads `large-nri`.** The first reason of `sbc-basis-uncertain`, on Mature
   Growth, fires on `large-nri` (`route_mature_growth.py`, `_stock_pay_notes`). **Ruling:** it
   reads the test of the new warning in its place (7.3).
6. **CLS's gap override.** Override 36, `earnings.nri_gap`, is tied to a period and corrected
   GuruFocus's gap of −0.423. Once the engine finds no gap, the standing test "the input the
   override corrected changed" drops it at the first revalue. **Ruling:** it drops, and plan 2's
   readout names it. PLTR's override 20 is lasting and stays.
7. **The mark's count.** `large-nri` sits on 655 valued rows of refresh 68. Without it, three
   warnings or more is on 151 to 193 valued rows (11% to 14%), by whether the new warning fires
   on no Mature Stable row or on every one, against 286 (21%) today. **Ruling:** the cut-off
   stays three; plan 2's readout gives the count.

Smaller differences, settled here:

- The decision document (3.5 item 3) says the playbook changes "in two places" for the ADR ratio.
  It names the ratio or the note in nine (`SKILL.md` 123–135, 274–276, 515–520, 666–668;
  `tools.md` 55–56, 61, 73, 351–352; `citations.md` 57). Plan 1 changes each.
- The decision document (2.1) says every other route fires `consensus-basis-unknown`. The code
  fires it on the two mature routes only. Nothing follows: the flag goes.
- The decision document (4.1) says Fairband keeps ten years of points with four statistics. The
  code keeps the vendor's whole answer and computes the window and the statistics at each read.
  The built series does the same (6.3).
- The agents' `moat.class` does not reach a Decline row today (its routes leave Decline out),
  though the class sets that route's margin of safety. The table reaches every route (8.5).

## 6. Plan 1: Altman's Z″, the ADR ratio, the P/E series

No value moves. The method is 1.6, since the listed-share rule changes and a value can move
under it on other data.

### 6.1 Altman's Z″ (B-255)

`z2score` leaves the summary's rows in `vendors/normalize_gf.py` (`_SUMMARY`), with its tests
and the fixture's use. The rows already stored stay. No document names the figure.

### 6.2 The ADR ratio from the two counts (B-256)

**The rule.** `apply_splits` (`refresh/inputs_splits.py`) takes the ADR flag in the place of
GuruFocus's ratio. The flag is `is_adr` as assembly reads it today (`_adr_flag` in
`refresh/inputs.py`: the profile's `isAdr`, else the universe row's, as built; `apply_splits`
takes no flag today). On a flagged row it finds the ratio from the
counts, as `adr.py` of the research folder did (`plain`, `cand`, `infer`), then runs today's
basis rule with it. On a row without the flag the basis rule does not run, whatever ratio a
vendor holds.

`method.md` 4.2, "The listed-share basis", reads:

> A row's statements are read on the quote's share basis before the split rule when FMP flags
> the company as an ADR (the ADR flag of section 2), the quote gives its count and a
> diluted count is on file. A row without the flag reads its counts as the split rule alone
> reads them. FMP states an ADR's count and EPS per ADS, the unit the quote prices, but on some
> periods holds a count off by a whole number or its inverse, the depositary's ratio. No vendor
> on file states the ratio, so the rule finds it from the counts.
>
> A count *differs* from the count it is judged against when neither it, nor it × the ratio of
> the pending splits after its period's end, lies within `split_implied_count_tolerance` (15%)
> of that count. For a count c that differs from the count A it is judged against, the multiple
> m is A ÷ c, then A ÷ (c × the pending splits' ratio). At m of 1.5 or more the candidate is the
> whole number n nearest to m, and the factor is n. At m of 1 ÷ 1.5 or less the candidate is the
> whole number n nearest to 1 ÷ m, and the factor is 1 ÷ n. A multiple between the two gives no
> candidate. A candidate fits when c × the factor, × the splits' ratio on the second multiple,
> lies within the tolerance of A.
>
> The ratio ρ is the n of the first count that differs and fits, in this order: the diluted
> count against the quote's count; then, when the diluted count does not differ, each trailing
> period (the four quarters or the two half-years, or the fiscal year on the fallback), oldest
> first, the newest against the quote's count and each older one against the diluted count. A
> period that differs and fits no whole number is passed over. A diluted count that differs and
> fits no whole number is the refusal "share basis unclear: the newest period's count <c>
> against the quote's <Q>", the counts in millions to one decimal, every figure as stored. With
> no ratio found, the row reads its counts as the split rule alone reads them.
>
> With a ratio found, a count fits a factor f of 1, ρ and 1 ÷ ρ, tried in that order, …

The rest of the paragraph stands as written, from "tried in that order" on, with these changes:
the refusal there is the one above and prints no ratio; "the ADR ratio 10" in a note's words
reads "the ratio 10"; "three ADSs to one share (the ADR ratio 0.3333)" reads "a third (the
ratio 3)"; "whatever FMP's ADR flag (JBS and MAAS …)" goes; "GuruFocus's EPS" goes from the
figures that take no factor in plan 2, when the figure itself goes.

**The limits**, to say in 4.2 after the rule: no whole number is too large to be a ratio (a
count held in thousands reads as a ratio of 1,000); a ratio that is no whole number or its
inverse, 1.5 say, is not found and the row is refused; the counts cannot say which way the
depositary's ratio runs, so ρ is always the whole number, 3 where a vendor would state 0.3333.

**The input.** `adr_ratio` is on a row the rule found a ratio on, and absent on every other row,
an ADR whose counts agree among them: today `_base_inputs` (`engine/route.py`) writes it on
every flagged ADR, with no value where none is on file, and that goes. Its value is ρ, its unit
`ratio`, an estimate under the
method `counts-ratio`, cited to FMP's quote as of the price date, its note "the whole number
that brings the stored count, 145.8 m, to the quote's, 1,450.8 m". `method.md` 5.12 and 7.1
say so; 7.1 no longer says a vendor states the ratio. `company`'s `adrRatio` is the input's
value, `null` without one. The ref's words (`reports/refs.py`, `inputs/adr_ratio`) read "the
ratio between FMP's stored share count and the quote's".

**The words on the page** (*my call*). The line under the drawer's head and the Research tab's
bar (`currencyLine`, `adsWords` in `app.js`) says today "one ADS is five ordinary shares", or
"the ADR ratio is not on file", which would then stand on every ADR whose counts agree, about
133 of 137. `adsWords` goes. For an ADR the line reads "an ADR: every per-share figure is per
ADS", with or without a ratio.

**The refusal's text** loses "(the ADR ratio <ρ>)". Section 9's row says a snapshot valued
before method 1.6 may carry the old ending. Every reader that matches the reason (the secondary
valuation's `cannot_fix`, the playbook's `REFUSALS`) matches the new text and a stored old one.

**The note `basis-scaled`** (section 8 of `method.md`) keeps its rule with "the ratio" for "the
ADR ratio", and "any row whose ratio is neither 0 nor 1, whatever its ADR flag" reads "a
flagged ADR the rule found a ratio on".

**The call.** `summary` stays: it carries the Moat Score until plan 3. Assembly stops reading
its `depositary_receipt_ratio`; the normalizer keeps storing it until plan 3 removes the
normalizer.

### 6.3 The daily trailing P/E series from FMP's data (B-257)

**The data.** When the history is opened, Fairband fetches through the pass-through, with its
pacing, its slots and its key scrubbing:

| Answer | FMP call | Stored under |
|---|---|---|
| Ten years of daily closes | `historical-price-eod/full`, from ten years before today | provider `fmp`, endpoint `pe-closes` |
| 44 quarterly income statements | `income-statement`, `period=quarter`, `limit=44` | endpoint `pe-quarters` |
| Eleven years of the pair's closes, a company in another currency only (changed on 2026-11-21 by the founder's ruling; see the decision log) | `historical-price-eod/light` on `USD<code>`, from eleven years before today | endpoint `pe-rates` |

The endpoint names are the series' own. A deeper answer stored as `price-history` would become
the newest copy for every reader of the five-year closes, the engine among them. One stored as
`income-quarter` would become facts at the next refresh, since the statement backfill reads
every response of that endpoint whatever its parameters. One stored as `fx-history` would
replace the three-year rates. No fact and no observation is written from the three answers.
They are reused for `refresh.reuse_hours`, 24 hours (*my call*: the series is then as fresh as
the screen's data; the seven days were GuruFocus's).

**The rule.** `method.md` 16.7, the trailing P/E, reads:

> **The trailing P/E** (`pe`): Fairband builds it from FMP's data. A day's P/E is its close ÷
> the trailing diluted EPS of that day: the sum of `epsDiluted` over the four quarterly income
> statements with the latest period ends at or before the day, or over the two half-years of a
> company that reports twice a year (the cadence of 4.2, read once from the newest rows). The
> EPS changes at a period's end, not at its filing date. The sum stands only when the periods
> are consecutive by 4.2's spacing and each holds the line; else the day has no point. A day
> whose trailing EPS is not above zero is a loss: it has no point and nothing fills it, so the
> series keeps the gap. A company in another currency: each period's EPS comes into USD at the
> pair's last close at or before the period's end (units of the currency per USD, so the EPS ÷
> the rate, 7.3), the trailing EPS is the sum of those USD figures, and the day's P/E is the
> day's close in USD ÷ that sum. A past period's earnings so stand at the rate of their time,
> and the day's rate is not read. A day whose periods are not all in the reporting currency, or
> that holds a period with no rate at or before its end, has no point. A period that names no
> currency is in the reporting currency, as 4.2 reads a statement, and a close or a rate that is
> not a positive number is not read. FMP's closes are adjusted for splits and its EPS restated
> for them; the series applies no split rule and no share-basis rule.

The quote's sentence on a company in another currency and its "restated for them" are new
(changed on 2026-11-21 by the founder's ruling; see the decision log).

The paragraph on the fetch follows it: the three answers and their names, the reuse, and what
the read serves when the fetch cannot be had (the newest stored answers, whatever their age,
with the reason in `peNote`: "no FMP key", the busy sentence or the vendor's). The last
paragraph of 16.7 stands, with `since` "the series' first day on file", which is now at most
ten years back.

**A series with no point.** A company with a loss on every day has a usable series with no
point and no statistic, stored and reused like any other (*my call*). Today such an answer is
stored as unusable and fetched again at every open (FRVO and RKLB on the live data).

**The limits**, to say in 16.7: a pending split (4.2) can leave the newest periods' EPS on the
old share basis for some days, and the series then steps by the split's ratio (B-199's family);
an ADR period whose EPS FMP holds off by the depositary's ratio (6.2) steps the same way; the
cadence is today's for all ten years; an EPS near zero gives a very large P/E, so the median is
the safe statistic. Added (changed on 2026-11-21 by the founder's ruling; see the decision
log): FMP can hold an ADR's period off by the ratio on a company that is no ADR on the screen;
FMP states EPS to the cent; FMP's EPS is as FMP holds it (a restatement for an accounting change
can stand as first reported, and one period held wrong moves every day of the year that holds
it), and the series checks no EPS against another line; the series steps on FMP's period end,
the fiscal week's end for a 52- or 53-week year, and its newest days change when a quarter is
filed; and for a company in another currency the forward P/E and a row's own P/E (5.9) read the
price at the day's rate, so they differ from the trailing series' newest point by the
currency's move since the periods' ends. The comparison of 2026-11-21 with GuruFocus's stored
series, on 29 companies over ten years, is in the decision log.

**The foreign filers and the half-yearly reporters were not tested** (decision document 4.4).
Plan 1 tests them before the merge: the built series against GuruFocus's stored series for
ASML, NVO, TSM and RELX (RELX reports twice a year, in GBP). Where a company misses "96% of days
within 5%" by more than a few points, the plan tests the quarter's EPS translated at its period
end's rate in the place of the day's rate, offline, and brings both figures to the founder
before the merge (the founder's rule of 2026-11-14).

**What goes.** `GuruFocus.pe_ttm`, `pe_ttm_rows`, the pass-through's `pe-history` kind with its
GuruFocus client, `PassthroughNoKey` and the sentence "no GuruFocus key: the pe-history
pass-through is off", the route `GET /api/vendor/pe-history/{symbol}`, and the MCP tool
`pe_history` (*the founder's ruling*: the tool goes; `multiples_history` serves the built
series, each day with `daily`). The server then has 54 tools, six vendor pass-throughs, all
FMP's. `GET /api/companies/{symbol}/multiples-history` keeps its shape. The stored `gf` /
`pettm` answers stay in the database, unread.

**The published reports.** A report stores its cites as text and its refs unresolved, and the
number check ran once, at submission. 31 reports cite 129 `multiple:` refs. Their text does not
change. The chart and the export's tables beside them read the built series from now on, which
can differ a little from a cited figure, as a series fetched again after seven days already
does.

## 7. Plan 2: no gap, the warning, the mark and the note

Mature Stable values move. Method 1.7, policy v17.

### 7.1 The mechanical routes take no gap (B-258)

- `nri_gap(i)` goes from `engine/route_steps.py`. On the two mature routes the gap is the
  agent's `earnings.nri_gap` or nil. On the other routes it is nil.
- The `keyratios` call, its two observations (`gf-ratio`), the inputs `gf_eps_ttm` and
  `gf_eps_without_nri`, their split rule (`_gurufocus_side`, `_observed`, the sentence
  "GuruFocus's EPS observed … is read …") and their currency rule (`_Money.mean`, and
  `FxSeries.mean_at` if nothing else calls it) go.
- `method.md` 6.1 reads "E = trailing net income − an agent's non-recurring gap × diluted
  shares; the mechanical route takes no gap". Section 2 loses the `keyratios` row; 4.2, 5.9,
  5.12, 6.5, 7.1, 7.4 and 14 lose GuruFocus's EPS.
- **The reading of the input** (*my call*). `current_reading(result, "earnings.nri_gap")` reads
  0.0 on a mature route's result without an override, as the cycle gap's reads, so a bridge's
  old value is 0.00 and a sensitivity grid has a marked cell. An override made from now on then
  corrects 0.0 and stays until a newer period is on file.
- **The basis test on Mature Growth.** The anchor's stock-pay basis test corrects GAAP EPS by
  the agent's gap less the gap found (`route_mature_growth.py`: `gap - nil(nri_gap(i))`). With
  no gap found, the correction is the agent's whole figure, as the decision document's "the
  agent's figure is the whole gap" has it. PLTR's override 20 corrected a found gap of 0.0, so
  its review does not move by this. A review that does move by it is no defect; the readout
  names each.
- The clean EPS, EPV on Mature Growth and the clean P/E equal the reported ones on a mechanical
  row, and differ under an agent's gap alone. The screen's clean P/E column stays.
- The glossary's "Non-recurring gap" (`reports/render.py`, `method.md` 13) reads "the one-time
  items in the trailing earnings a share, after tax, which an agent sets in a review; a net
  charge is negative".
- `tests/fixtures/golden/`: MSCO's value rests on a gap of 0.10 and moves; MGCO and FXCO lose a
  clean EPS that differs. The goldens are made again and read.

### 7.2 The warning `one-time-items` (B-258)

`large-nri` and `consensus-basis-unknown` go. `one-time-items` joins `QUALITY_WARNINGS` in the
place of `large-nri`; the warnings stay twelve. The set has no order of its own: where an order
is needed, on the Methodology page's list and in a hover, `one-time-items` stands where
`large-nri` stood, first.

`method.md` section 8, the row:

> `one-time-items` | yes | a Mature Stable row, valued or refused "no positive trailing
> earnings", whose GAAP trailing diluted EPS and street trailing EPS (5.12) differ by
> `one_time_items_share` (20%) of the GAAP figure's size or more: |GAAP − street| ÷ |GAAP|;
> silent without a street figure, with a GAAP EPS of zero, and under an agent's
> `earnings.nri_gap`, which decides the items. Word "One-time items". The sentence names the
> two figures and the share: "GAAP trailing EPS is $4.10 and the analysts' is $5.20, apart by
> 26.8% of GAAP EPS, at or above 20.0%. The trailing earnings may hold one-time items, which
> the mechanical value keeps; a review takes them out through `earnings.nri_gap`."

- Mature Stable gains the DATA input `street_ttm_eps`, as Mature Growth has it, so the
  sentence's second figure is cited.
- *My call:* the refusal "no positive trailing earnings" carries the warning when its test
  holds. It raises no flag today. The 19 rows that the missing gap refuses are companies whose
  loss is a one-time charge, and an agent that reads the row should see the cue.
- The test as run (`warn_test.py`) matched a street quarter within ten days of the statement's
  period end. The engine matches the period end exactly, so the count can differ from the 177 of
  392 rows of the decision document. Plan 2's readout gives the engine's count.

### 7.3 The stock-pay note's first reason

`sbc-basis-uncertain`'s first reason (Mature Growth) reads the test of 7.2 in the place of
`large-nri`: "`includes-sbc` on a material stock pay where GAAP trailing EPS and the street's
differ by `one_time_items_share` or more". Its sentence ends "while GAAP trailing EPS and the
analysts' differ by X%, so a one-time item may sit in GAAP EPS and hide the gap." The warning
itself stays on Mature Stable alone. Plan 2's readout counts the reason against the 50 rows of
refresh 58.

### 7.4 Policy v17

- `nri_flag_share` goes. `one_time_items_share` = 0.20 comes, a setting in its place on the
  Settings view with its range, 1% to 50%, source "the founder, 2026-11-19: of four thresholds
  tested on 392 Mature Stable rows, 20% warns 45% of rows and finds 89% of the large moves".
- `warning_mark_min` = 3 comes, not a setting (*my call*: a setting would change the settings
  hash and ask for a revalue over a number that moves no value), source "the founder,
  2026-11-19: three warnings or more".
- **A removed setting** (section 5, point 4): `apply_overlay` skips a stored name the policy no
  longer holds as a setting, and the store deletes it at the next settings read that writes.
  Plan 3 uses the same path for `refresh.gf_reuse_days`.

### 7.5 The mark and the note (B-259)

**The row.** `/api/screen`'s rows gain two fields, read from the snapshot's own flags, not a
review's:

- `warnings`: the plain words of the row's quality warnings, in the order of the result's
  flags.
- `marked`: true when the row has a mechanical value, no reviewed value, and
  `warning_mark_min` warnings or more.

`flags` and `flagCount` stay in the row for the agents' `screen` tool.

**The plain words** (*my call*, the founder's to change):

| Warning | Words |
|---|---|
| `one-time-items` | one-time items |
| `value-spread` | value sensitive to its inputs |
| `margin-flag` | margin above its history; newly profitable; possible cycle peak (by its word) |
| `z-distress` | distress signal |
| `f-score-low` | weak financial health |
| `reinvesting-in-decline` | investing while revenue falls |
| `equity-raise` | new shares issued |
| `negative-fcf` | negative free cash flow |
| `heavy-capex` | heavy capital spending |
| `burn-cover-short` | cash covers under two years |
| `consensus-recovery` | analysts expect a recovery |
| `share-count-gap` | share count unclear |

They live in the web layer, by flag code. `Flag.word` in the engine does not change: it is in
every stored result.

**The mark.** The bullet of IBM Plex Mono (U+2022), enlarged to read as a dot, in the ink of the
value, before the figure (form A of the look, section 9). The vendored font holds this glyph;
it does not hold U+25CF, which a system font would draw, and a drawn circle is the shape the
brand book reserves for a point on a scale. The mark is `role="img"` with the hover's first
sentence as its `aria-label`, as the coverage mark beside a ticker is.

**The hover**, a `title`, as every hover text on the pages is:

| Where | Text |
|---|---|
| The head of the Mechanical column | the note |
| A mechanical value on the screen, and its mark | "3 warnings: heavy capital spending; negative free cash flow; new shares issued. " then the note; "1 warning: …" for one; the note alone for none |
| The drawer and the company page | the same, with the second note |

The note on the screen: "Preliminary estimate only. To ask an agent for a reviewed valuation,
open the company and click Request research." In the drawer and on the company page:
"Preliminary estimate only. To ask an agent for a reviewed valuation, click Request research."

**Where the mechanical value stands in the drawer and on the company page.** Neither has an
element of its own for it. On a row without a review, the mechanical value is the meter's fair
value and the figure of the "Fair value" row: both carry the hover, and the row's figure the
mark. On a reviewed row it is the meter's caption "mechanical $…": the caption carries the
hover with the note and the snapshot's warnings, and no mark. The company page's "Fairband
value" panel draws the same meter and rows.

**What goes from the screen:** the Flags and the Warnings columns from the columns a reader can
add (`bundle.js`, `index.d.ts`), and the Clean filter (`FILTER_FLAGS`, `FLAG_WORDS`,
`FLAG_ROWS`, `EMPTY_FILTERS`, `app.js`'s test). A saved column list that names a removed column
loses it without an error, as `normalise` already does.

**The Methodology page** says, in its value section, that a mechanical value is preliminary:
fixed rules made it and no one checked it; it includes one-time items; a review takes them
out. Its flags section names the mark and the hover in the place of the two columns and the
filter, and `one-time-items` in the place of `large-nri`. Its Mature Stable steps lose "with
one-off items removed", and KO's example is read again under 1.7.

**The playbook.**

- Step 5's sentence "the engine anchors on earnings without them" is wrong from now on: "the
  mechanical value keeps them, and step 8 takes them out".
- Step 8 gains the standing step of every Mature Stable review, with no flag needed, and the
  recipe: sum the one-time items of the trailing four quarters; count restructuring,
  impairments, gains and losses on sales, litigation and debt retirement; take them after tax
  and a diluted share; write a net charge as a negative figure; set it through
  `earnings.nri_gap`, tied to the period, with the filing as evidence; where the filings show
  none, say so in section 8 and set nothing.
- The entry of `consensus-basis-unknown` goes. Its advice for Mature Growth, to read whether
  the NTM consensus carries a one-time item (`earnings.ntm_nri`), stays, with no flag named.
- The rule for an asset outside the business reads "the agent's figure is the whole gap" for
  "the gap found, raised by the gains".
- The clean P/E's gloss says it differs from the reported one under the agent's gap alone.

## 8. Plan 3: the moat table, and GuruFocus out

Method 1.8, policy v18, schema 010, moat table `fairband-moat-v1`.

### 8.1 The file (B-260)

`src/fairband/policy/moat-classes-v1.toml`, packaged beside the tax table and loaded by a
reader beside `policy/tax.py`. The package holds the newest version only; git holds the
history (*my call*: no stored figure is computed again from an old version).

```toml
[meta]
version = "fairband-moat-v1"
date = 2026-11-25                    # the day the version was cut
universe = "the universe of the full refresh of 2026-11-18, 1,558 companies"
rule = "docs/method.md 4.9a"

[[classes]]
symbol = "AAPL"
class = "Wide"
judged = 2026-11-19
source = "rule"

[[classes]]
symbol = "SMCI"
class = "None"
judged = 2026-11-19
source = "correction"
rule_class = "Wide"
reason = "It assembles servers from other companies' parts, and rivals sell the same. …"
decided_by = "the founder"

[[classes]]
symbol = "SONY"
class = "Wide"
judged = 2026-11-19
source = "rule"
note = "First doubted as a mixed group. …"
decided_by = "Claude, after the closer look the founder asked for"
```

- One entry for every company of the universe at the cut, Narrow written out like the others.
- `source` is `rule` or `correction`. A corrected entry holds `rule_class`, `reason` and
  `decided_by`, word for word from the log of the decision document's 6.7 (74 entries). A
  questioned and kept entry holds `note` and `decided_by` (15 entries).
- The reader refuses a file with no entry (added on 2026-11-21 by the review of the reader; see
  the decision log), a symbol twice, a class outside the three, a `correction` without its three
  fields, or a `rule` entry with `rule_class` or `reason`.
- The first version is cut when plan 3 is built, on the universe the live database then holds.
  The companies of refresh 68 take the classes of the run of 2026-11-19 with the corrections,
  `judged` 2026-11-19. A company that entered since is drafted by the rule, `judged` the day of
  the cut, and plan 3's readout lists these for the founder to read.

### 8.2 The rule that drafts the file

The rule is no part of the engine. It is a pure function in the package, so it has tests, and
`scripts/build_moat_table.py` runs it, beside `build_tax_table.py`.

`method.md` gains 4.9a, "The rule that drafts the moat table", stating the rule as it ran:

> The rule writes the first class of a company in the moat table (4.9). The engine does not run
> it. It reads, for each company of the universe:
>
> - **The return years:** the last ten ROIC years the engine keeps (4.4, 4.5), each with its
>   NOPAT and its average invested capital. A year's return is NOPAT ÷ capital; a year whose
>   capital is at or below zero is above any bar when its NOPAT is above zero and below any bar
>   otherwise. The ten-year total is the ten years' NOPAT ÷ their capital, by the same rule on
>   the sums. The five-year median is the median of the last five years' returns. A loss year
>   is a year whose NOPAT is at or below zero.
> - **Revenue:** the trailing revenue of the company's latest snapshot, in US dollars at the
>   snapshot's rate; for a company whose latest snapshot is refused "no moat class", which
>   holds none, the trailing revenue as assembly reads it today, at assembly's rate. A company
>   with none has no size, growth or leader mark.
> - **Growth:** over the fiscal years with a revenue that is not zero, the newest ÷ the tenth
>   newest, to the power 1 ÷ 9, less 1; none with fewer than ten such years.
> - **The gross margin:** gross profit ÷ revenue of the last ten annual income statements on
>   file. It is steady with ten margins, none below 80% of their median.
> - **The phase** of the latest snapshot, and **the industry and the sector** of the universe.
> - **The group:** the company's industry when it holds five companies with a revenue or more;
>   else the companies of its sector whose industries hold fewer than five, together.
>
> The class, by the first of these that holds:
>
> 1. Fewer than ten return years: Narrow.
> 2. A phase of Start-up, Young Growth or High Growth: Narrow.
> 3. *None:* a ten-year total and a five-year median both below 3%.
> 4. A phase of Decline: Narrow.
> 5. *Wide:* at most one loss year in the ten and none in the last five, a ten-year total and a
>    five-year median both above 9%, and one of two routes; and an industry off the cyclical
>    list.
>    - The scale route, two of four marks: revenue of $50 billion or more; first or second by
>      revenue in its group; revenue of $12 billion or more with growth of 10% a year or more;
>      a steady gross margin.
>    - The return route: a ten-year total and a five-year median both above 20%, with a steady
>      gross margin.
> 6. Else Narrow.
>
> A company on the cyclical list that meets rule 5 is Narrow; rule 3 comes first, so the list
> never lifts a None.

then the cyclical list, the 24 industries of the run with their exact FMP names and Aluminum,
Silver and Uranium, 27 in all, without "Oil & Gas Energy"; the sentence that semiconductors are
left out on purpose; and the sentence that size is revenue, never market value.

Rule 3 before rule 4 gives the run's result for a company in Decline: None when the None test
holds, else Narrow. `Chemicals` is an exact name: `Chemicals - Specialty` is not on the list.

The revenue's second source is new and is not in the run of 2026-11-19 (*my call*). From plan
3 on, a company that enters the universe is refused "no moat class" before any route, and a
snapshot refused there cites no trailing revenue. Without the second source every later
entrant would lack its size, growth and leader marks and would not count in its group. On the
reference database no snapshot holds that refusal, so the run's classes are made again
exactly: a company refused for another reason still has no revenue here, as in the run.

**The script** opens a database read-only and reads what the run of 2026-11-19 read:
`build_inputs` and `aggregate_roic` for the return years and the fiscal series, the latest
snapshot's `revenue_ttm` and `fx_rate` inputs and its phase, the stored annual income
statements for the gross margins, the universe's rows for the industry and the sector. It
makes no vendor call and values nothing. Its work:

- *A new version:* every entry of the current file is kept as it is; each company of the
  universe that the file lacks is drafted, `judged` today. No entry is dropped (a company that
  left the universe keeps its entry; the yearly read prunes).
- *The yearly read:* it lists each `rule` entry whose class the rule gives differently today,
  for the maintainer; it changes no entry by itself.

### 8.3 The table in the database

Migration `010_moat_classes.sql`:

```sql
CREATE TABLE moat_classes (
    symbol TEXT PRIMARY KEY,
    class TEXT NOT NULL,          -- Wide, Narrow, None
    source TEXT NOT NULL,         -- file, owner, agent
    file_version TEXT,            -- a file row: the table's version; else NULL
    judged_on TEXT NOT NULL,      -- the entry's date, or the day of an owner's or agent's write
    previous TEXT,                -- a local change: the class in force before it, NULL if none
    reason TEXT,                  -- an agent's, required; an owner's, optional; a file row's NULL
    evidence TEXT,                -- JSON [{kind, ref, note}], an agent's; else NULL
    principal TEXT NOT NULL,      -- system for a file row; owner; agent
    actor TEXT,
    client TEXT,
    at TEXT NOT NULL,             -- when the row was written
    snapshot_id INTEGER           -- a local change: the snapshot its revalue wrote
);
```

One row a company, the class in force. The history of changes is the ledger's: each owner's or
agent's write is a ledger row of kind `moat`, "moat Narrow → Wide: <the reason's gist>".

**The existing judgments.** The same migration turns each applied `moat.class` override that is
not dropped into a row of an agent: its `new` the class, its `old` the previous class, its
reason, evidence, actor and time; `snapshot_id` NULL. It then marks each such override dropped,
"moved to the moat table". In the founder's database these are overrides 31 (TTMI, None), 34
(NVO, Narrow) and 45 (RELX, Wide). No row is made from a report's verdict in words (section 5,
point 1).

### 8.4 The file read into the table

A stage `moat` runs in every refresh that values (full, scoped, revalue), before the value
stage, and in the revalue of one company (8.6). It compares the packaged file with the table
each time, about 1,600 rows, and writes only what differs:

- a company the file holds and the table does not: its file row is written;
- a file row that differs from the file's entry (its class, its date or its version): replaced;
- a file row whose company the file no longer holds: deleted;
- a row of the owner or of an agent: never touched, whatever the file holds.

`at` is the time a row was written, `principal` `system`, `judged_on` the entry's `judged`.
A load that changes no row writes nothing, so a refresh on an unchanged file leaves every
`at` as it was.

### 8.5 The engine

- `CompanyInputs.moat_score` becomes `moat_class`, the row's class or `None`, with the row's
  provenance. `moat_class(score, policy)` in `engine/anchor.py`, the policy's `moat_wide_min`
  and `moat_narrow_min`, and the DATA input `moat_score` go.
- **The refusal.** A company with no row is refused "no moat class". It is the last guard
  before a route: after "no price" and "no diluted share count", then, for a Start-up company,
  right before the Start-up route, and for every other, after "no trailing figures"
  (`value_company`, `engine/route.py`). So a company refused for its data keeps that reason,
  and an agent that sets the class is not met by a guard's refusal behind it. A route's own
  refusals come after, as they must. A Start-up company with no row reads "no moat class", not
  "Start-up: no value by design", since its requirement needs the class. `method.md` 5.1, 6b.1
  and section 9 say so.
- **The input.** Every result that passed the guard carries `moat_class`, its note led by the
  class word, as today, so a ref still reads its word:

  | The row is | Tag | Source | As of | Note |
  |---|---|---|---|---|
  | the file's | RULE | "moat table fairband-moat-v1" | the entry's date | "Wide" |
  | the owner's | JUDGMENT | "owner" | the day of the write | "Wide", or "Wide: <reason>" |
  | an agent's | JUDGMENT | "agent claude-opus-5-5" | the day of the write | "Wide: <reason>" |

  So a snapshot names where its class came from (decision document 6.4, item 4).
- `method.md` 4.9 reads:

  > The moat class is the company's row in the moat table (`moat_classes`): Wide, Narrow or
  > None. The table is Fairband's own. A packaged file, `moat-classes-v1.toml`, holds a class
  > for every company of the universe at its cut: the draft of the rule of 4.9a, corrected by
  > hand where the rule is wrong, each corrected entry with the rule's class, the reason and
  > who decided. Every refresh that values reads the file into the table first, and the file
  > replaces its own rows alone: a class the owner set on the company page, or an agent
  > recorded in a review (`moat_set`), stays in force whatever a later file holds, and of the
  > two the newest is in force. A company with no row is refused, "no moat class" (5.1): one
  > that entered the universe after the file was cut. The owner's class, an agent's verdict or
  > the file's next version lifts the refusal. The moat enters in three places: …

  The rest of 4.9 stands as written.
- The Decline route reads the same class for its margin of safety, an agent's among them.

### 8.6 The write: the owner's control and the agent's `moat_set`

One route serves both: `PUT /api/companies/{symbol}/moat` with `{class, reason?, evidence?}`.

- The writer is read as on every write (`web/identity.py`): the owner without the agent's
  headers, else the agent with its actor.
- An agent's write needs a reason and one evidence item or more, as an override does: 400 "a
  moat verdict needs a reason", "a moat verdict needs evidence". The owner's needs neither.
- A class outside the three: 400. A company with no snapshot: 404. While a refresh runs: 409 "a
  refresh is running: set the class when it ends", and nothing is stored.
- In one transaction: the row is written, `previous` the class in force before it; the ledger
  row; then **the revalue of the one company**: a refresh record of kind `revalue` that names
  the symbol, the stage `moat`, then the company's value stage as a revalue runs it
  (`build_inputs` on the stored facts and the latest deciles, the snapshot, the multiples log,
  `follow_snapshot`, so a review follows). No vendor call is made. The row's `snapshot_id` is
  the snapshot written.
- The same class as the one in force is a write like any other: the row becomes the writer's,
  and the company is valued again, since the snapshot names whose class it holds. This is the
  agent's "the class stands" and the owner's confirmation.
- It answers the row and the new snapshot's value or refusal.

`DELETE /api/companies/{symbol}/moat`, the owner's alone (403 for an agent): the row returns to
the file's entry, and the company is valued again the same way; 404 where the file holds no
entry for the company. The decision document does not say how an owner returns to the file's
class; without this an owner's mistaken click parts the company from the file for good (*my
call*, approved with the look).

**A revalue that names companies** is new: today a revalue takes no symbol. `method.md` 10
says a revalue may name companies and then values those alone; the command line and the
refresh route take the symbols as a scoped refresh does (*my call*: the kind exists for the
write, and costs nothing more to offer).

**The reads.** `GET /api/companies/{symbol}` gains `moatClass`: the row (`class`, `source`,
`fileVersion`, `judgedOn`, `previous`, `reason`, `actor`, `at`) and `fileClass`, the file's
class for the company or `null`. The field `moat` stays, and is the table's class on every row
with one, valued or refused (`research_api._moat` reads the table, not a result).

**Every reader of the class outside the engine reads the table's row.** A valued snapshot's
class is the table's, since every write values the company again; a snapshot refused before
its route carries none. So the secondary valuation's levels (`_moat` in `web/reviews_api.py`)
read the table: a company refused for its statements or its tax rate, with a row of Wide, gets
Wide's margin of safety, not None's. The screen's Moat column keeps its rule, a row with a
value only, and reads that row's class, which is the table's. The stamp, the column and a
review then agree, which closes B-232.

**The MCP tool** `moat_set(symbol, moat_class, reason, evidence)` calls the route as an agent.
`company` returns `moatClass`. The server has 55 tools again.

### 8.7 `moat.class` is no override; the report's verdict

- `check_override` refuses the tag before its other rules, `refused-locked`: "moat.class is
  the moat table's: record the verdict with moat_set". After the migration no applied override
  of the tag exists.
- The tag stays in `TAGS`, and a route still reads it through `chosen`, for a sensitivity
  reading alone: a reading may vary the class on an axis (the Mature Stable grid of the
  playbook is `return.runway` × `moat.class`), and a reading changes no input. `method.md` 14.2
  keeps the row and says so; 14.3's locked list gains the sentence. A stored bridge that holds
  a `moat.class` line still draws.
- **The verdict every time.** `report_submit` gains a structural refusal, beside the secondary
  valuation's: "the report needs the moat verdict recorded on snapshot <id>: call moat_set",
  when the company's row is not an agent's whose `snapshot_id` is the report's snapshot or one
  it reprices (`refs.same_snapshot`). It catches the slip of a verdict in words alone. The
  report's `moat` judgment stays as it is, bull, bear and decision.
- **The secondary valuation** of a company with no row in the table answers 400 "set the moat
  class first: moat_set", whatever its snapshot's refusal: its levels need the class (8.6), and
  an agent can set it.

### 8.8 The control on the company page

As the look's six states (section 9):

- After the phase badge, the stamp, as today: `WIDE MOAT`, `NARROW MOAT`, `NO MOAT`. It shows
  on every company with a row, a refused one too. A company with no row shows `MOAT NOT SET`
  with a dashed border.
- After the stamp, where the class is the owner's or an agent's, a compact principal chip, "◆
  Owner" or "◆ Agent claude-opus-5-5", its hover the reason and the day. A file's class has no
  chip: quiet is the signal that nothing was changed.
- Then a quiet small button, "Change ▾", or "Set ▾" with no row. It opens a box built as the
  Notes box is (`fb-menu`, placed under its control, closed by a press outside or Escape, focus
  returned): one line saying whose the class is ("Fairband's class, table version 1, judged 19
  Nov 2026."; "Your class since 19 Nov 2026. Before: Narrow."; an agent's with its chip), the
  reason under it where one is on file, the three classes as a segmented control with the one
  in force pressed, a field "Reason (optional)", the button "Set moat class", and on a row of
  the owner or an agent, where the file holds the company, "Use Fairband's class (Narrow)".
- After a write the page reads the company again. A refusal's sentence stands under the
  buttons.
- The drawer's head shows the stamp and the chip and no control.
- `CLAUDE.md`'s brand-book line gains: an owner's moat class is saved without a reason (the
  founder, 2026-11-19).

### 8.9 The playbook, and policy v18

**The playbook.** The moat is a standing step of every review, a valuation review too, placed
before the decisions and the overrides: the five sources as a guide (brand name, switching
costs, network effect, cost advantages, efficient scale), the agent's own judgment and what
else the business shows, then `moat_set` with the reason and the evidence, also when the agent
agrees with the class it found. The step says to record the verdict before any override, since
the write values the company again and gives it a new snapshot. The overrides table's row for
`moat.class` says the class is set through `moat_set`. The refusal "no moat class" joins the
refusals with its remedy.

**Policy v18.** `moat_wide_min`, `moat_narrow_min` and `refresh.gf_reuse_days` go (the last by
the path of 7.4). The Methodology page loses its two `data-policy` spans with the sentence
they stand in.

### 8.10 Taking GuruFocus out (B-261)

Once the summary call has no reader:

- `vendors/gurufocus.py`, `vendors/normalize_gf.py`, `build_gurufocus` and the GuruFocus half
  of `build_clients` (`refresh/clients.py`).
- In `refresh/fetch.py`: the provider `gf`, its two calls, its reuse window, the "no GuruFocus
  key" failure. In `refresh/run.py`: the client and the provider's name in the rate-limit
  words. In `refresh/inputs.py`: the reads of `gf-score` and `gf-ratio`.
- `config.py`: the vendor `gurufocus`, `FAIRBAND_GURUFOCUS_KEY`, `Keys.gurufocus`. A keys file
  that still holds a `gurufocus` line loads without an error and without a warning.
  `__main__.py`: `_NO_GF_KEY` and the clients.
- The tests and fixtures of each (`tests/vendors/test_gurufocus.py`,
  `tests/fixtures/gurufocus/`, the vendor doubles' GuruFocus host and token).
- `method.md` section 2 (the two GuruFocus rows, the 429 sentence), section 12 where it names
  the source; the Methodology page's sentence on the Moat Score; `README.md` (the two keys, the
  keys file, the diagram's GuruFocus box, the tool counts); `docs/agents.md`;
  `docs/method-overview.md`.
- The rows GuruFocus's calls stored (`vendor_responses` of provider `gf`, the `gf-score` and
  `gf-ratio` observations) stay in a user's database, unread.

## 9. The look

Drawn on the real pages over a scratch database on 2026-11-19 and approved by the founder with
this design. The sources are in `2026-11-19-gurufocus-removal-mockup/`; the sheets hold vendor
data and are in the research folder's `look/`.

- The dot: four forms were drawn. The bullet at the cell's size is too small to see. The
  enlarged bullet (A) and a drawn circle (C) read alike; A is taken (7.5).
- The moat control: six states, in both themes (8.8).
- No test pins the Mechanical cell's markup today. The moat stamp, the drawer's head and the
  company page's actions are pinned (`test_company_page.py`, `test_drawer_form.py`,
  `test_notes_control.py`); plan 3 moves those pins.
- A hover text is a `title`, which a keyboard and a touch screen do not reach. The brand book
  is silent on it. The mark's `aria-label` carries the warnings for a screen reader.

Each plan that changes a page checks it in a real browser, in both themes, by the recipe of
the mockup's README, before its review.

## 10. Acceptance

Each plan's figures are made on the reference database before the merge, then read on the live
data in the readout.

**Plan 1.**

- Every company of refresh 68 valued under the branch gives the stored value: 1,558 rows, 1,363
  valued. CX is $7.49 and SIMO $95.71. The rule finds 10 on CX, 4 on SIMO, 2 on XPEV and 3 on
  TAL. GDS is refused "share basis unclear: …", with no ratio in its text.
- The built P/E series against GuruFocus's stored series, the companies that report in USD,
  ten years: 96% of days within 5%, or more. ASML, NVO, TSM and RELX are reported apart (6.3).
  This needs about 90 FMP calls.

**Plan 2.**

- Mature Growth, High Growth, Young Growth and Decline: no value moves (915 valued rows).
- Mature Stable (448 valued rows): 301 values down, 90 up, 38 the same, 19 refused "no positive
  trailing earnings"; row by row against `nogap.pkl`.
- Reported: the rows `one-time-items` is on, the rows the mark is on, the first reason of
  `sbc-basis-uncertain`, and the reviews that moved (CLS).

**Plan 3.**

- The rule on the reference database gives the class of `final_class.pkl` on all 1,558
  companies: 170 Wide, 1,303 Narrow, 85 None, and on the 1,363 valued rows 169, 1,138 and 56.
  With the 74 corrections: 162, 1,320 and 76, and on the valued rows 161, 1,155 and 47.
- A revalue of a copy of the reference database under the branch: no row is refused "no moat
  class"; TTMI, NVO and RELX hold an agent's row; CRM reads Narrow.
- Reported: the values and buy levels that moved against the values after plan 2, the reviewed
  values that moved, the companies drafted since refresh 68.
- A refresh makes no GuruFocus call, with a `gurufocus` key in the keys file and without one.
  `grep -ri gurufocus src/` finds no code that reads it.

## 11. The live steps of each plan

Asked of the founder once a plan, with the list:

1. The acceptance of section 10 on the reference database, and the page in a browser.
2. A backup of the live database with SQLite's backup,
   `fairband-before-method-<version>-<date>.db`.
3. The server stopped by its process id; main fast-forwarded and pushed.
4. `uv run python -m fairband refresh --kind revalue` by the command line. In plan 3 the
   migration runs with it.
5. The server started from main on 8470; the page looked at on the live data.
6. The readout in this design's decision log; the backlog's rows moved to Done with their
   commits; the limits found filed as new rows.
7. The founder told that every research session must restart its MCP process: the tools change
   in plans 1 and 3.

## 12. The documents

| Document | Plan 1 | Plan 2 | Plan 3 |
|---|---|---|---|
| `docs/method.md` | 2, 4.2, 5.12, 7.1, 8, 9, 11, 16.7 | 2, 4.1, 4.2, 5.9, 5.11, 5.12, 6.1, 6.5, 7, 8, 11, 13, 14 | 2, 4.1, 4.9, 4.9a, 5.1, 5.12, 6b.1, 9, 10, 11, 12, 14.2, 14.3, 16.3 |
| The Methodology page | the share basis' words, the caption | the value and flags sections, Mature Stable, KO | the moat, the agents' section, the caption |
| The playbook | the ratio's nine places, `pe_history` out, the P/E's source | 7.5's list | 8.9's list, `moat_set` |
| `docs/agents.md`, `README.md` | the tool counts | | the keys, the diagram, the counts |
| `docs/method-overview.md` | the version | the gap, the version | the moat, the source, the version |
| `CLAUDE.md` | | | the brand-book line |
| `docs/gurufocus-removal.md` | | | CRM's sentence; the status |

## 13. Tests the builder must write

Each change is built test first. The ones a plan must not miss:

- **Plan 1:** the ratio found on the diluted count and on a period; a count that differs and
  fits no whole number refuses; a row without the flag is never scaled; a multiple between 1 ÷
  1.5 and 1.5 gives none; a pending split with a ratio. The series: the EPS stepping at a
  period's end, a loss day, a half-yearly reporter, a company in another currency, periods that
  are not consecutive, a series with no point; a stored `pe-quarters` answer writes no fact and
  no reader of `income-quarter` sees it, the same for the closes and the rates.
- **Plan 2:** each mechanical route with no gap; the override still applied on both mature
  routes; the warning at 19.9% and 20%, without a street figure, with a GAAP EPS of zero, under
  an override, on the refusal; a stored value of a removed setting ignored and deleted; the
  row's `warnings` and `marked`, a reviewed row unmarked; the hover's three forms.
- **Plan 3:** the rule's every branch on synthetic companies, and the file's reader on a
  malformed file; the load's four cases, a local row kept under a new file version; the
  refusal's place among the guards; the migration on a database with applied `moat.class`
  overrides; the write by the owner and by an agent, the same class written again, a refresh
  running, the delete; the one-company revalue with a review that follows; `check_override` on
  the tag and a sensitivity axis on it; the report's refusal; no GuruFocus call at a refresh.

## 14. Left to the builder

Names of modules, functions, stages and CSS classes not given here; the layout of the TOML
file within the fields of 8.1; the script's command line; the exact markup of the mark and the
box within the look; how the migration writes its time stamps; the sentences of flags, notes
and refusals this design does not quote, in the style of the ones beside them; where the
plain words of 7.5 live in the web layer; the response id `multiples-history` names for a
series built from several answers; the order of work inside a plan.

## Decision log

- **2026-11-19, the founder: "Approved"**, on Claude's message of that day, which held the seven
  points of section 5 with a recommendation on each, the recommendations on the eight questions
  he set for this design (the rule texts, the file, the table, the refusal, the page, the
  agent's write, `pe_history`, the versions and live steps), and three sheets of the look. The
  rulings in section 5 and the choices marked as the founder's are that approval. The choices
  marked *my call* were not all named in the message and stay Claude's.
- **2026-11-19, Claude:** the reference database was copied from the live one before any plan
  (section 3), so that the figures of refresh 68 can be made again after later refreshes.
- **2026-11-19, the builder's check.** A reviewer read this design as a builder would and asked
  five questions. Each was answered from the code or the decisions, and none went to the
  founder: the drafting script's revenue for a company refused "no moat class" (8.2); an
  agent's gap on Mature Growth acting by its whole figure, and PLTR's review, which does not
  move by it (7.1); every reader of the class outside the engine reading the table, the
  secondary valuation's levels among them (8.6, 8.7); the refusal's place after "no trailing
  figures" (8.5); the load comparing the file with the table at every refresh (8.4). Three
  statements about the code were corrected: the warnings are a set with no order (7.2), the
  `adr_ratio` input that every flagged ADR carries today (6.2), and the ADR flag's fallback
  (6.2).
- **2026-11-19, the founder: "Approved"**, on this design as written, with the twelve calls of
  Claude's that the hand-over named: the P/E answers' names and their reuse, a series with a
  loss on every day, the ADR line on the page, the warning on the refusal, the two policy
  values, the hover's words, the refusal's place, the drafting script's revenue, the other
  readers of the class, the same class written again, a revalue that names companies, and the
  package holding the newest moat file only.
- **2026-11-21, plan 1 built.** Seven tasks, each built by a subagent and reviewed, then a
  review of the whole branch and one wave of fixes (commits 0c26a7c to 74948aa). Tasks 5 and 6
  ran as one task, since the suite could not pass between them.
- **2026-11-21, the values on the reference database (section 10).** Every company of refresh
  68 valued in memory with the branch's code: 1,558 rows, 1,363 valued; no value differs from
  its stored snapshot, and no route, buy level, designation or settings hash. CX is 7.49 and
  SIMO 95.71. The ratio found is 10 on CX, 4 on SIMO, 2 on XPEV and 3 on TAL, and none on the
  other 1,554 rows (137 carry the ADR flag). GDS's refusal reads as section 10 words it.
  `basis-scaled` is on those four rows, against ten stored: JBS and MAAS carry no ADR flag, and
  KT, PAC, PKX and VEON are flagged rows whose diluted count agrees with the quote's and whose
  differing periods fit no whole number. None of the six moves a value; JBS carries
  `share-count-gap` in its place. The stored refusals of RML and TXR ("data fetch failed") are
  the fetch stage's, which a valuation in memory cannot make.
- **2026-11-21, the founder: the rule stands for GRFS.** The rule refuses a second row beside
  GDS: GRFS, "share basis unclear: the newest period's count 680.6 m against the quote's
  846.0 m", a flagged ADR whose diluted count is off by a multiple of 1.24, outside the
  tolerance and no whole number. Under 1.5 GuruFocus's ratio of 1 kept the rule off the row,
  which was refused "incomplete NTM consensus"; no value moves. The decision document's count
  of the rows that differ used a wider band than the tolerance and so missed it. Claude ruled
  that the rule stands, as decision 3.5 and section 6.2 word it, and asked the founder, who
  answered "Yes proceed on both points" (the live steps and GRFS). A flagged ADR whose counts
  are 15% to 50% apart for an ordinary reason is filed in the backlog.
- **2026-11-21, the P/E series against GuruFocus's (6.3).** The built series against
  GuruFocus's stored series on the 29 companies that hold one in the reference database, over
  ten years, each day both hold a point; 66 FMP calls. Over the 25 companies that report in
  USD, 49,547 of 52,259 days are within 5%: 94.81%, under the 96% of section 10, which the
  decision document measured on ten companies. Of the 2,712 days that differ, 953 are
  GuruFocus stepping to the new quarter's EPS one to three trading days before FMP's period
  end (counted as within: 96.63%), and 1,288 are one or two runs on AMD, AVGO, AZN, CRM and
  ROAD, each from one period that FMP holds otherwise than GuruFocus (an EPS whose sign
  differs from its net income's, one period on the depositary's basis, a year as first
  reported, cents on a small split-adjusted EPS). OMC's newest year is 27.5% under
  GuruFocus's, from a diluted count FMP did not update after a merger, until that quarter
  leaves the trailing year. Two repaired forms were tested offline (the founder's rule of
  2026-11-14): the EPS as net income ÷ the diluted count for every period gives 93.54% and
  harms TTMI, AVGO and OMC; FMP's EPS replaced only where it disagrees with that figure by
  sign or by more than 30% gives 95.64%, repairs ROAD, AZN and SYM and replaces one correct
  EPS on AMD. Neither is built; the second is filed in the backlog with its figures.
- **2026-11-21, the founder: "I am fine with being within 94.8%, the 96% rule was arbitrary.
  Logically, it just needs to be close enough. And 94.8% is close enough."** The USD
  comparison is accepted as built. `method.md` 16.7 names the limits it met.
- **2026-11-21, the founder: a company in another currency reads each period's EPS at its
  period end's rate.** Under the rule as first built (the day's close brought into the
  reporting currency at the day's rate) the share of days within 5% of GuruFocus's was 72.7%
  on ASML, 68.1% on NVO, 90.2% on TSM and 71.6% on RELX: the two series part by the currency's
  move between the periods' ends and the day, up to 25% in 2022. With each period's EPS
  brought into USD at its period end's rate, the product's code (8a73098) gives 97.8%, 99.3%,
  98.2% and 99.3%, each on 2,507 days, and ten-year statistics within about 1% of GuruFocus's
  (2% for the highs and lows). Claude recommended the first rule, since a row's own P/E and
  the forward P/E read the price at the day's rate (`method.md` 7.3). The founder asked what
  the second rule costs, whether the forward P/E can take it (it cannot: its periods have no
  rate yet), and what other sources do. Seeking Alpha converts at the rate of the time each
  number was reported, Morningstar at the period's average rate, and the accounting rule for
  income is the rate of the time; Siblis Research and MSCI's index formula convert at the
  price date; no stated method was found for Yahoo Finance, Bloomberg, FactSet or S&P Capital
  IQ. His words were "before you do, can you check what other sites do?"; Claude read them as
  his choice of the second rule should the check support it, told him it would build it, and
  built it as one more task, reviewed (8a73098). The method stays 1.6, since no refresh had
  run under it. The pair's closes are fetched eleven years back, so the first trailing year
  has its rates. The scripts, the answers and the outputs of the comparison are kept outside
  the repository, with the other results of 2026-11-19.
- **2026-11-21, plan 1 live.** The backup is `fairband-before-method-1.6-2026-11-21.db`. Main
  went to ac27be0 by a fast-forward and was pushed. Refresh 70, a revalue under method 1.6 and
  policy v16: 1,558 rows, 1,363 valued; the server runs on 8470 from main. Against each row's
  snapshot before it (refresh 69, a price refresh): CX is 7.49 and SIMO 95.71; `basis-scaled`
  is on CX, SIMO, TAL and XPEV, and the six rows of the acceptance lost it; GDS and GRFS are
  refused "share basis unclear"; RML and TXR read "no financial statements" where the fetch
  stage had written "data fetch failed". One value differs, SBS (5.3364 against 5.3452), and
  ACN, BSP, GRDN and MNDY gain `equity-raise`: the code of before this plan, run in memory on
  the same data, gives the same value and the same four flags, so these come from the data a
  price refresh does not value again, not from this plan (B-267). No route, phase, designation
  or settings hash differs. The P/E history opened on AAPL, ASML and RELX through the live
  server: 2,514 points each from 2016-11-21, with no note. B-255, B-256 and B-257 are closed;
  the limits met are B-262 to B-267. Every research session must restart its MCP process,
  since `pe_history` is gone.
- **2026-11-21, plan 2 built.** Nine tasks, each built by a subagent and reviewed, one fix round
  on the playbook, then a review of the whole branch and one wave of fixes (commits 5e2bec7 to
  8e4410f). The build's own rulings, for the founder to overturn: the playbook's template says
  that under the agent's gap the clean P/E is the review's and that a report with no gap gives
  the reported P/E alone, since a snapshot's two P/Es are equal from now on; its example cites
  one P/E; the `split-pending` entry names GuruFocus's EPS no more; the rule for an asset
  outside the business keeps its guard against counting a gain twice; and the cycle gap of a
  Mature Stable row is measured on the trailing figures less the agent's `earnings.nri_gap`,
  since the engine takes that gap off first and a one-time charge would else be added back
  twice (the formula of 2026-11-11 does not change). In the drawer the dot hangs in the gap
  before the Fair value figure, so the four levels keep one left edge. The warning fires at an
  exact 20% within 1e-12.
- **2026-11-21, plan 2 on the reference database (section 10).** Every company of refresh 68
  valued in memory with the branch's code: 1,558 read, none raising. The 915 valued rows of
  Mature Growth, High Growth, Young Growth and Decline keep their values. Of Mature Stable's
  448 valued rows 301 go down, 90 up, 38 stay and 19 are refused "no positive trailing
  earnings", each value and refusal the one the test of 2026-11-19 gave with no gap.
  `one-time-items` is on 211 rows, 173 valued and 38 refused: 191 of the 437 valued Mature
  Stable rows that hold both EPS figures (the test's own 392 rows give 176, not 177: NTAP's
  street quarters do not sit on the exact period end). 162 valued rows hold three warnings or
  more, 156 of them with no reviewed value. Reason 1 of `sbc-basis-uncertain` is on 24 rows,
  against 48 under 1.6 on the same data. CLS's override 36 is the one override that drops;
  PLTR's 20 stays. The look was checked in a browser in both themes on a scratch copy valued
  under 1.7: the dot is U+2022 of the page's own IBM Plex Mono, as form A draws it, and every
  hover reads as section 7.5 words it.
- **2026-11-21, the founder: "you have concent for live steps"**, given while the fix wave ran,
  and then "when this completes, please feel free to merge and push to main, then kick off
  plan 3 implementation".
- **2026-11-21, plan 2 live.** The backup is `fairband-before-method-1.7-2026-11-21.db`. Main
  went to 8e4410f by a fast-forward and was pushed. Refresh 71, a revalue under method 1.7 and
  policy v17: 1,558 rows, 1,344 valued (1,363 before); the server runs on 8470 from main.
  Against refresh 70: of the 448 valued Mature Stable rows 301 go down, 90 up, 38 stay and 19
  are refused "no positive trailing earnings"; no value differs on any other row. The largest
  moves are GPC (60.65 to 2.49), CRL, LFUS, APD and ACI down, and TAC (0.28 to 2.54), ZIM, SUZ,
  CNX and BKV up; CX goes from 7.49 to 4.93 and SIMO from 95.71 to 105.82. 76 rows change
  designation. `one-time-items` is on 211 rows, 173 valued and 38 refused; `large-nri` left
  691 rows and `consensus-basis-unknown` 559; `sbc-basis-uncertain` is on 115 rows (133
  before), reason 1 on 24. 164 valued rows hold three warnings or more and 158 carry the mark.
  No `split-pending` sentence changes. CLS's override 36 dropped, "the input the override
  corrected changed", and its review went from 271.27 to 291.62 (+7.50%): the override was
  the agent's way to make the basis test charge stock pay, and the charge left with it; the
  other 27 reviews keep their values, PLTR's with its override 20. EPV, the growth share and
  the clean P/E also move on rows of other routes that had a found gap; their values do not.
  B-258 and B-259 are closed; the limits met are B-268 to B-272. No tool changed, so no MCP
  process restarts, but a research session started before the merge holds the old playbook.

