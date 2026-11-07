---
name: fairband-research
description: Research one company for Fairband over its MCP tools, from a work item to a published report in which every number is cited, when the user asks for a Fairband valuation review or full report or names a Fairband work item.
---

# Fairband research

Fairband is a valuation screen on the user's own machine. Its engine computes every value. You
research a company, change the engine's inputs with evidence, and write a report. You never write
a value yourself.

This skill takes one work item (a request for research on one company) from the inbox to a
published report. Run the thirteen steps below in order. Write every sentence, in the report and
in every reason, in the register of `reference/register.md`.

The report argues the business, and only its valuation section talks about the valuation. The
steps build it as a chain. The last earnings call gives management's story (step 5). The bull
case and the bear case argue it, and the thesis decides it (step 9). The decisions turn the
thesis into the engine's inputs (step 10). Every report values the company twice: by the
engine's route, and by a standard discounted cash flow from drivers you set, the secondary
valuation. A cyclical business (one whose profits rise and fall with its industry's cycle) is
valued at mid-cycle (step 7).

## Before you start

- The Fairband server must be running. When a tool answers "the Fairband server is not running:
  start `uv run fairband serve`", tell the user and wait. Go on once a tool answers.
- Every tool answers JSON. A refusal is `{"refused": <sentence>, "status": <code>}`. The sentence
  names the rule that stopped the call. Fix what it names. Repeat a call unchanged only when the
  sentence says to try again.
- The tools, their arguments and their answers: `reference/tools.md`.
- The rules the server checks every number by: `reference/citations.md`. Read it before you write.
- The report's twelve sections, the summary page and a full example submission:
  `reference/report-template.md`.
- The register and the product's words: `reference/register.md`.

## The steps

### 1. Identify yourself

Call `identify(agent)` with the model identifier you run as, such as `claude-opus-5-5`. Give it in
lower case, exactly as the host reports it. Fairband records every write under it. A write before
`identify` is refused: "identify first: the model identifier you run as".

Only the lead agent calls `identify`. A subagent the host starts never does: the identity belongs
to the Fairband MCP process, which the lead and its subagents share, so a subagent's `identify`
would rename every later write.

### 2. Take the work item

Call `inbox_list()` to see the work items. Claim one with `inbox_claim(item_id)`. Without an id, it
claims the oldest pending item. Keep the item's id, its symbol, its mode and its note. Do not take
over an item that another agent has claimed unless the user asks.

When the user asks for research in chat, post the request first with `inbox_post(symbol, mode,
note)`, then claim the item it answers. Every piece of work has a work item. The mode is
`valuation review` or `full report`. A company holds one open item (pending or claimed) at a time:
when `inbox_post` answers "an item for <symbol> is open", claim that item instead.

A full report covers the business, the industry and the value. A valuation review re-values the
company and reuses the newest full report for the business and the industry.

An item of origin `expiry` is a company whose validity window has ended: its snapshot is stale.
Refresh it first, at the start of step 3.

### 3. Read the company

First, the window. When the item's origin is `expiry`, or `company(symbol)` shows a `valid_until`
before today, refresh the company before you read further:

- Call `refresh_start("scoped", [symbol])`. When it is refused because a refresh is running, call
  `refresh_status()` until that one ends, then start yours.
- Call `refresh_status()` until its `refresh` is `null`: no refresh is running, and `last` is the
  one you started.
- Read `company(symbol)` again. The snapshot id is new.

Then read everything the page shows:

- `company(symbol)`: the latest snapshot (the company's frozen inputs and the engine's result on
  them). Keep `snapshot.id`: the report cites this snapshot.
- `financials(symbol)`, `financial_tables(symbol)`, `estimates(symbol)`, `peers(symbol)` and
  `price_history(symbol)`: the stored figures, each with the ref to cite it by.
- `multiples_history(symbol)`: the trailing and the forward P/E (the price over the earnings a
  share) over the years on file, with their ten-year average, median, high and low, each with its
  ref. Section 9 of the report sets the multiples against this history.
- `report(symbol)`: the latest report, when there is one. `reports(symbol)` lists every revision.
  Its thesis is the one the last earnings call tests in step 5.
- `notes(symbol)`, `findings(symbol)`, `guidance(symbol)`, `overrides(symbol)`, `reviews(symbol)`,
  `secondary(symbol)` and `kill_criteria(symbol)`: the research already on file. `guidance` holds
  the figures the company guided on earlier calls, and so its track record.
- `policy()`: the policy values in force.
- `methodology(section)` for the company's route: `mature-growth`, `mature-stable`, `growth` (High
  Growth and Young Growth), `decline` or `start-up`. `methodology()` lists every section.

Section 4 of the report is written from the cells of `financial_tables`. Read each open kill
criterion (a measurable event that would prove the view wrong). When one has happened, move it with
`kill_criterion_set(id, "triggered", reason)`.

### 4. The fundamentals: the business and the industry

Read the filings with the host's own tools: the 10-K, the 10-Q, the proxy statement, the company's
own site. From Fairband, read `segments(symbol)` for the revenue by product and by region, and
`transcript(symbol, year, quarter)` for the earlier earnings calls; the last call is step 5's.
`insider_trades(symbol)` shows what the insiders bought and sold.

Record a finding (a dated fact with its source) with `finding_add` for every number from outside
Fairband that the report will cite. Fairband's own figures need no finding. `financials`,
`financial_tables`, `estimates`, `price_history`, `peers` and `multiples_history` give each figure
with its ref; for the others, build the ref from the record's id (`reference/citations.md`).

### 5. The last earnings call

The call often forms, confirms or breaks the thesis, and the price moves on it. Section 5 of the
report is this step's record, in seven parts (`reference/report-template.md`).

Find the call. `transcript_dates(symbol)` lists every call on file, newest first, with its fiscal
year, its quarter and its date. Never guess a year. Read the newest call with
`transcript(symbol, year, quarter)`. Read the call before it the same way, for the drift.

When the vendor has no transcript of the newest quarter, say so in the section. Read the
company's earnings press release with the host's own tools instead. The quarter's figures still
come from the filings, as findings.

Then build the seven parts:

1. **The verdict.** The call's date and quarter. Whether it confirmed, changed or broke the thesis
   (the newest report's, or the one this report forms). The price's move on the next trading day:
   `derive` `growth` of the first close after the call over the last close before it, two `close:`
   refs from `price_history`.
2. **The quarter against expectations.** Revenue, EPS, the operating margin and free cash flow,
   each against the same quarter a year before and against the consensus for the quarter.
   Fairband's refs name fiscal years and the trailing twelve months, not single quarters, so record
   each quarter's figure as a finding from the 10-Q or the press release, with its period
   (`2026-Q3`). The consensus for the quarter is the `estimates` quarter's ref, when the store
   holds it (revenue and EPS). The surprise is `derive` `growth` of the actual over the consensus;
   the change on the year is `growth` of the actual over the prior year's. Then name what drove the
   quarter: price, volume, mix, currency, one-time items. Name the one-time items: the engine
   anchors on earnings without them.
3. **The story management is telling.** Quote the frame in their words. Then take three to five
   claims. For each: the claim with its figure and its timeline; the evidence for it in the
   numbers; the driver it moves in the engine's terms (the growth of years two and three, the held
   rate, the target margin, the reinvestment, the moat, the risk); and the test that would show it
   true or false, and by when. Give each a verdict in Damodaran's words. **Possible**: it could
   happen. **Plausible**: the evidence makes it believable. **Probable**: the evidence makes it
   more likely than not. Only a probable claim moves a figure in step 10. Then the drift since the
   previous call: a claim that grew or vanished, new words such as "macro" or "visibility", a
   metric no longer reported. Then what they did not say.
4. **The guidance.** Record every clear figure the company guided with `guidance_add` (see
   "Guidance" below). The section shows each record: the metric, the period, the low, the high,
   the midpoint, the basis, and whether it was raised, held or cut against the previous record and
   how it sits against the consensus. Then one sentence on what the valuation takes from it: the
   override of step 10, or "the consensus stands".
5. **The positives and the negatives**, each tied to a figure or a quote.
6. **The questions and answers.** The two or three analysts' pushbacks that matter to the thesis,
   and whether the answers were direct.
7. **What the thesis takes from it.** The kill criteria the call touched, the one thing to watch
   next quarter, and the gap between how far the price moved and how far the reviewed value moved.

Every figure quoted from the call that the report cites is a finding first: record it with
`finding_add`, its source the transcript, `{kind: "transcript", ref: "response:<responseId>",
note}`, the `responseId` that `transcript` answered.

### 6. The news

Read `news(symbol, limit)` and the web. Explain each large price move in the price history. Note
the candidate kill criteria. Record each news item that matters to the value with
`news_item_add`, or pass it with the report.

### 7. The cycle

Decide whether the business is cyclical. The engine does not flag a cyclical, and it values a peak
as if the peak lasted. So the call is yours, and the valuation then rests on mid-cycle figures.

The signs:

- the industry: memory and other semiconductors, energy, mining, steel, chemicals, shipping, autos,
  airlines, homebuilders, machinery;
- ten years of revenue and operating margin (operating profit over revenue) that swing from peak
  to trough, in `financials`;
- prices set by a commodity or by the industry's capacity;
- inventory cycles;
- a consensus that extends a peak;
- the engine's `margin-flag`: the trailing operating margin far above its ten-year median or its
  ten-year high. Its word is "Possible cycle peak" when those years hold a loss year, else "Margin
  above history".

For a cyclical, place the company in its cycle. Set the operating margin against its ten-year
median, and revenue against its trend, from the cells of `financial_tables` and the years of
`financials`. On Mature Stable the snapshot's intermediates hold the median (`median_margin`).
Record the evidence as findings with `finding_add`: the peak and the trough you found, the
industry's capacity or prices. The thesis names the position. The summary says "cyclical". Step
10 sets the inputs at mid-cycle.

### 8. The valuation

Read the engine's result in the answer of `company`: the value, the levels (the buy level, the fair
band and the trim level), the inputs with their tags (DATA, RULE or JUDGMENT), the intermediates,
the phase evidence and the flags. `methodology` explains each in plain words. Put the result in
plain words for yourself first. Note each place where the evidence of steps 4 to 7 disagrees with
an input. Those are the candidate judgments.

### 9. The debate and the thesis

Write the bull case and the bear case. Each argues the business and its outlook: demand and how
long it lasts, where the company is in its cycle, competition and the moat, pricing power, capital
allocation, management, the balance sheet, and the claims of the call. Give each side its
strongest case, in words a reader without the method follows. Figures may be cited. The debate is
never about inputs, tags or parameters: valuation arithmetic belongs in section 8 alone.

Then write the thesis: the report's own story, set against management's. It opens with a position
on each claim of step 5:

- **accepted**: the claim is a driver the valuation moves;
- **rejected**: the report's value parts from the consensus or the guidance here, and why;
- **held open**: the claim becomes a kill criterion or a thing to watch.

Then the case that settles the debate and leads to the stance: what must be true for the stance to
be right, and what you expect to happen. Write it for every stance:

- a buy says why the market is wrong on the downside;
- a hold says why the price is fair and what the view waits for;
- a trim says why the price ran ahead of the business;
- an avoid says why the business is not worth owning at the prices shown.

The kill criteria of section 11 test the thesis.

### 10. The decisions, the overrides and the two values

Decide each judgment from the thesis (see "The judgments" below). Move an input for a claim of the
call only when the thesis accepts it and step 5 judged it probable. Where a decision changes an
input, write an override (a change to one input, with its reason and its evidence) with
`override_add`.
One override changes one input. Its answer carries the override's state and, when it applied, the
review (the engine's value under the applied overrides) with its bridge (the change from the
mechanical value, one line per override). Read both. `override_drop` drops an applied override.
See "Overrides" below.

The guidance, at your best effort and never required. A clear full-year guidance, or a next quarter
that completes the fiscal year, may replace the consensus anchor: `earnings.ntm` on Mature Growth,
`revenue.ntm` on High Growth, Young Growth and Decline, or a consensus step, `path.step_2` or
`path.step_3`. The override's evidence holds an item of kind `guidance` that cites the record as
`guidance:<id>`. Where the guidance is not clear, the consensus stands. See "Guidance" below.

A cyclical, valued at mid-cycle:

- on Mature Growth and Mature Stable, the anchor's earnings at mid-cycle through
  `earnings.cycle_gap` (a positive figure lowers them), and on Mature Growth the belief at the
  growth rate through the cycle;
- on High Growth and Young Growth, the target margin (`margin.target`) at the mid-cycle margin, and
  the held rate (`path.hold`) at the growth rate through the cycle;
- a kill criterion on the operating margin against its median.

Then the second value, and the two checks beside it:

- **The secondary valuation**, on every report: `secondary_valuation` with `drivers`, the standard
  discounted cash flow. Set the drivers from the thesis, at mid-cycle for a cyclical. Use `parts`
  instead where a sum of parts fits the company better. The report check refuses a report with no
  secondary valuation on the latest snapshot: "the report needs a secondary valuation on snapshot
  <id>". Make it after any revalue, since one made before does not count. See "The secondary
  valuation" below.
- **FMP's own figure**, a cross-check: `dcf(symbol)` gives FMP's discounted cash flow value and
  its levered one. Section 8 may cite it in one sentence, as a third opinion beside the engine's
  two.
- **The route's grid**: `sensitivity` sets two of the route's inputs across a few values each, and
  answers the route's value a share at every pair. Section 8 cites it. See "The sensitivity
  reading" below.

Compute every other figure the report needs from stored figures with `derive`: a ratio, a
difference, a sum, a growth rate or a compound annual growth rate. Never compute one yourself.

### 11. The stance

Choose the stance: `buy`, `hold`, `trim` or `avoid`. Read the value against its levels. Take the
reviewed value when the current review has one. Take the snapshot's value when the company has no
review. Take the secondary valuation's when neither gives a value. Where both give a value, the
route's value leads and the secondary valuation is the second view. `avoid` is for a company you
would not hold at any price shown. Weigh the thesis as well as the levels. The report's reasons
carry the stance.

### 12. The report

Write the twelve sections of `reference/report-template.md`, ten for a valuation review. Cite every
quantity, by the rules of `reference/citations.md`. Give the judgments as the record of your
decisions, each `{judgment, decision, override_id?}`. Submit with `report_submit`. The server
publishes a report whole or rejects it whole. A structural refusal (the section count, the stance,
a judgment, a heading, or no secondary valuation on the snapshot) is one sentence: fix it and
submit again. A rejection (422) lists the findings: fix each one and submit again.

### 13. Complete the work item

Call `inbox_complete(item_id, report_id)` with the id of the published report. Or name the item in
the submission as `work_item_id`: the report then completes it in the same write, and a later
`inbox_complete` is refused. When you cannot do the work, call `inbox_decline(item_id, reason)`
instead.

## The rules

- Never write a number you did not get from a tool.
- Cite every quantity. In a report, every number is a cite `{cite, ref, period?}`.
- Write small counts in words: "three years", "two quarters".
- A number from outside Fairband becomes a finding first, then a cite `finding:<id>`.
- Your own arithmetic goes through `derive`, then a cite `derived:<id>`.
- A threshold you choose is never a finding: tie it to a stored figure, cited, or state it in
  words (`reference/citations.md`).
- The decision of a judgment holds no figure at all.
- The valuation and its detail are in section 8 only. The rest of the report argues the business
  and its outlook.
- Write the thesis for every stance, a hold and an avoid included.
- Use guidance only when it is clear. Otherwise the consensus stands.
- Write in the register of design.md 9.2 (`reference/register.md`): the answer first; short
  sentences, one idea each; every term explained the first time; rounded numbers.
- No first person. Fairband has no voice: never "I", "we" or "our".
- The reason on an override is your own words. Fairband keeps it verbatim and shows it on the
  bridge.
- Start a refresh only in three cases: a scoped refresh of a company whose window has ended (an
  `expiry` item, or a `valid_until` before today; step 3); a revalue when a refusal asks for one;
  or when the user asks.
- Only the lead agent calls `identify`; a subagent never does (step 1).

## Guidance

A guidance record is a figure the company itself gave on an earnings call for a future period.
Record one with `guidance_add(symbol, metric, period, low, high, basis, as_of, text, source)`:

- `metric`: `revenue`, `eps`, `operating_margin`, `free_cash_flow`, `capex`, `revenue_growth` or
  `eps_growth`.
- `period`: a fiscal year, `2027`, or a quarter, `2027Q1`, written with no dash.
- `low` and `high`: the range, equal for a point. Dollars in full; a percent as a fraction.
- `basis`: `gaap`, `adjusted` or `constant-currency`.
- `as_of`: the call's date, from `transcript_dates`.
- `text`: the sentence, verbatim. `source`: the transcript's `response:<responseId>`, or a filing.

The server computes the midpoint. For a fiscal-year revenue or EPS record it also computes the
step: the growth from the year before's actual on file. So you never compute a rate. A newer record
of the same metric, period and basis supersedes the older one, in the order of the calls' dates.
Record the previous call's figure too, so the section can say raised, held or cut: written after
the newer one, it is stored already superseded. Every record stays, so a later report reads the
track record, guided against delivered.

The rules:

- Guidance reaches the valuation only when it is clear: a number or a range, for a stated metric,
  for a stated period, on a reported basis. A range takes its midpoint.
- A figure in words ("upper teens"), a one-sided figure ("at least"), an adjusted figure with no
  bridge to GAAP and a constant-currency figure stay out of the valuation. Discuss them in section
  5: the consensus stands. Record an adjusted or a constant-currency range with its basis. A
  figure in words or a one-sided one has no low and high: record it as a finding with its text and
  no value.
- A next-quarter figure enters only when it completes the fiscal year: three quarters of that year
  already reported, and the guided fourth. The year's figure is then the `derive` `sum` of the
  three reported quarters, each a finding, and the record's midpoint, and it serves as a full-year
  figure would. Otherwise the quarter stays in section 5, read against the consensus for that
  quarter.
- Use it at your best effort. It is never required: a report with no guidance override is a normal
  report. Where the guidance is not clear, the consensus is the fallback.

Guidance enters the reviewed value only through an override, never the mechanical value. The
figure you pass as `new` comes from a tool:

- for an NTM anchor, the record's midpoint;
- for a consensus step, the growth the path reads: `derive` `growth` of the record's midpoint over
  the consensus of the year before (its `estimate:` ref). Step 2 grows from the base year (the
  `base_year` of the snapshot's `path` intermediate) into the next year; step 3 into the year after
  that.

The override's evidence names the record: `{kind: "guidance", ref: "guidance:<id>", note}`.
The server refuses the override, and stores nothing, when that item is not right: "a guidance item
cites its record as guidance:<id>" (400) for a ref of any other form; "no guidance record <id> for
<symbol>" (404); "guidance record <id> is superseded by record <id>" (409) when a later call's
record replaced it. Cite the newer record instead.

## Overrides

`override_add(symbol, tag, new, reason, evidence, lifetime, period?)` changes one input. The engine,
not you, computes the value it gives.

- `tag`: the input, from the table below.
- `new`: the new value in the unit the engine reads. A rate is a fraction: `0.12` is 12%. A word
  input takes its word, as a string: `"Wide"`, `"None"`.
- `reason`: your own words, kept verbatim.
- `evidence`: one item or more, each `{kind, ref, note}`. The kind is `filing`, `transcript`,
  `url`, `vendor`, `base-rate`, `finding` or `guidance`; the ref says where the evidence is. A
  `guidance` item's ref is `guidance:<id>`, the record's id with no path.
- `lifetime`: `lasting`, or `period-tied` with `period`, the fiscal year it corrects (`2025`).

| Tag | Routes that read it | The input | Takes, the ends included |
|---|---|---|---|
| `phase` | every route | the life-cycle phase; the route follows it | `Start-up`, `Young Growth`, `High Growth`, `Mature Growth`, `Mature Stable` or `Decline` |
| `earnings.ntm` | Mature Growth | the anchor's EPS for the next twelve months (NTM), from a clear full-year EPS guidance | above 0 to 1,000 dollars a share; evidence of kind `guidance` required |
| `revenue.ntm` | High Growth, Young Growth, Decline | the NTM revenue, year one of the revenue path or of the run-off, from a clear full-year revenue guidance | above 0 dollars; evidence of kind `guidance` required |
| `growth.belief` | Mature Growth | the belief: the growth rate after the analysts' years, before the fade to the long-run rate | −0.20 to 0.60 a year |
| `path.hold` | High Growth, Young Growth | the held rate of years four to the end of high growth | −0.20 to 3.00 a year |
| `path.step_2`, `path.step_3` | Mature Growth, High Growth, Young Growth, Decline | the consensus growth of year two or year three | −0.80 to 3.00 |
| `moat.class` | Mature Growth, Mature Stable, High Growth, Young Growth, Start-up | the moat class; it sets the margin of safety, the runway and the terminal return | `None`, `Narrow` or `Wide` |
| `margin.target` | High Growth, Young Growth, Start-up | the operating margin the company reaches in year ten | −0.50 to 0.60 |
| `capital.sales_to_capital` | High Growth, Young Growth, Decline | the revenue a dollar of invested capital buys | 0.1 to 10 |
| `return.runway` | Mature Growth, Mature Stable | the return on new capital in the runway years | 0 to 1.00 |
| `earnings.nri_gap` | Mature Growth, Mature Stable | the non-recurring gap in the earnings a share | −100 to 100 dollars a share |
| `earnings.cycle_gap` | Mature Growth, Mature Stable | the correction that takes the anchor's earnings to mid-cycle; a positive figure lowers them | −100 to 100 dollars a share |
| `decline.rate` | Decline | the rate at which revenue shrinks | −0.50 to 0 a year |
| `balance.debt`, `balance.cash` | High Growth, Young Growth, Decline, Start-up | the newest annual balance sheet's debt or cash | 0 dollars or more; period-tied only |

The ranges are the policy's `override_ranges`; `policy()` gives the values in force.

The two NTM anchors and the cycle gap:

- `earnings.ntm` and `revenue.ntm` stand in for the consensus of the next twelve months, from a
  guidance record (see "Guidance"). Each is lasting. The consensus moves at every refresh and the
  guidance at every call, so at each later call drop it with `override_drop`, or replace it with
  an override citing the new record.
- `earnings.cycle_gap` is a dollar figure a share. It comes off the anchor's earnings and nothing
  else: the NTM EPS on Mature Growth, the normalized earnings on Mature Stable. On Mature Stable,
  when the `margin-flag` fires, the engine has already scaled the earnings to the ten-year median
  margin. The gap adds to that scaling, so set it for what the median misses. A negative figure
  lifts a trough's earnings to mid-cycle. Set the figure from the evidence of step 7, by `derive`
  from stored figures where they serve.

The server checks an override by these rules, in this order, and answers the first one it breaks:

1. `refused-locked`: a locked input (one no override may change). These are r (the hurdle rate),
   g_T (the terminal growth ceiling), the runway years, the fade years, the margin of safety, the
   fair band, the trim multiple, the terminal return, the deciles, the growth word, and every
   reported figure (the price, the shares, the market cap, the revenue, the operating income, the
   EPS). Debt and cash change only through the two balance tags. The consensus of the next twelve
   months changes only through the two NTM anchors.
2. `refused-not-input`: a tag that is not in the table.
3. `refused-route`: a route that does not read the tag. The route follows an applied `phase`
   override, so override the phase first. The Mature Stable route reads no consensus step, so
   `path.step_2` and `path.step_3` are refused there. A company with no phase reads no input but its
   phase: set its phase first.
4. `refused-unit`: a value outside the range, a word outside the words, a word where a number is
   due, an NTM anchor at 0 or below, or a lasting override of a balance tag.
5. `refused-evidence`: no evidence, "an override needs evidence". An NTM anchor with no item of
   kind `guidance`: "an NTM anchor override needs a guidance record among its evidence". A
   `growth.belief` or a `path.hold` above the sales class's 90th percentile (`sales_p90_5y` in the
   base rates) also needs an item of kind `filing` or `transcript`. An item of kind `finding` does
   not count for this rule, even when the finding came from a filing.

Before the rules, the server checks each `guidance` item (see "Guidance"); a bad one stores nothing.

A refused override is stored with its state and applies nothing. Its answer is the refusal's
sentence with the `override` record beside it. Fix the one thing the sentence names, and try again.

An applied override answers `{override, review, bridge}`. The bridge starts at the mechanical value
(the engine's value with no override), adds one line for each override, and ends at the reviewed
value. The lines run in the method's order: phase, NTM earnings, NTM revenue, consensus step 2,
consensus step 3, held rate, belief, non-recurring gap, mid-cycle earnings, target margin, sales to
capital, runway return, decline rate, moat, debt, cash. A line whose step refuses shows the refusal
in place of a change. A review whose last line refuses has no value: the secondary valuation then
stands in.

One input holds one applied override. A new override on the same tag replaces the old one. An
override applies to the latest snapshot and to every later one. A period-tied override (a correction
of one period's vendor error) drops by itself once the company's data date moves or the engine's
own reading of the input changes. Add a note with `note_add(symbol, text, override_id)` when the
reason needs more words.

An override, a drop, a secondary valuation and a sensitivity reading are refused with "settings
changed: run a revalue" (or "policy changed", or "method changed") when the latest snapshot was
valued under other settings. Call `refresh_start("revalue")`. Wait until `refresh_status()` shows no
refresh running. Read `company` again, since the snapshot id changes, and try again. An override, a
drop and a sensitivity reading are also refused with "the store moved since snapshot <id>: run a
revalue" when the stored data changed after the latest snapshot: a refresh is under way, or a peer
was refreshed. When `refresh_status()` shows a refresh running, wait until it ends; otherwise call
`refresh_start("revalue")` and wait the same way. Read `company` again and try again. A secondary
valuation made before a revalue does not count for the report: make a new one.

## The secondary valuation

A second value a share, by the standard discounted cash flow, on every report. You set the drivers;
the engine projects the free cash flow to the firm (the cash the business makes after its
investment, before any payment to lenders or owners), discounts it, adds the terminal value and
bridges the firm value to a value a share. So the figure is a tool output. It is the second view
beside the route's value, and it stands in where the route refuses or no route fits.

Call `secondary_valuation(symbol, reason, evidence, drivers?, parts?, debt?, cash?)` with exactly
one of `drivers` and `parts`.

### The drivers

`drivers` is `{years, revenue_growth, operating_margin, tax_rate, sales_to_capital,
terminal_growth}`, every rate a fraction:

- `years`: N, the years projected, from 3 to 15.
- `revenue_growth`: a list of N rates, the growth of revenue in each year, each −0.80 to 3.00.
- `operating_margin`: a list of N rates, the operating profit over revenue in each year, each
  −0.50 to 0.60.
- `tax_rate`: the share of operating profit paid in tax, 0 to 0.50.
- `sales_to_capital`: the revenue a dollar of new capital buys, 0.1 to 10. It sets how much each
  year reinvests to grow.
- `terminal_growth`: the growth after year N, forever, from −1.00 to g_T (`0.03` at the
  defaults).

The ranges are the policy's `secondary_years_min`, `secondary_years_max` and
`secondary_driver_ranges`; `policy()` gives the values in force.

The engine starts from the trailing revenue on file (`fact:<symbol>/revenue/ttm`). Each year it
grows revenue at that year's rate and takes the margin, then the tax. It reinvests the year's new
revenue divided by sales-to-capital. A year whose revenue falls reinvests nothing, so a decline
does not create cash. It discounts each year's free cash flow at r, the policy's required return,
which no one may change. The terminal value grows the last year's after-tax operating profit at the
terminal growth and reinvests the share that growth needs at the terminal return the moat sets (r
on a Narrow or None moat; on a Wide one, the company's ten-year ROIC, held between r and the
policy's cap). A
terminal growth at or below zero reinvests nothing. This is the engine's own
stable-growth rule, so the route's value and this one rest on one terminal convention. The equity
is the firm value less debt plus cash. The value a share is the equity over the diluted shares.

Set the drivers from the thesis, and say in the reason why each one is where it is. The consensus,
or a clear guidance, serves the first years. A cyclical takes its margins at mid-cycle. On High
Growth and Young Growth the route's own path in the intermediates (`growth_rates`, `margin_path`,
`tax_rate`, `sales_to_capital`) is a fair start: change what the thesis changes.

### The grid

Every record carries a three-by-three grid: the value a share at r less one point, r, and r plus
one point (the columns), across the terminal growth less one point, the terminal growth, and the
lower of the terminal growth plus one point and g_T (the rows). The centre cell is the value. The
grid shows how much of the value is assumption; it is never a value. A record has no grid when r
less one point would not exceed the highest growth. Cite a cell as `secondary:<id>/grid/<i>/<j>`,
rows and columns counted from 1.

### The parts

Use `parts` instead where a sum of parts fits better: a conglomerate, or a company whose cash
flows you build segment by segment. `parts` is one to ten, each `{name, fcff, terminal_growth,
note}`. `fcff` is the free cash flow to the firm in dollars for years one to N, N from three to
fifteen. Each `terminal_growth` runs from −1.00 to g_T. On this form the grid's rows move every
part's terminal growth together by one point down, none and one point up, each capped at g_T.

### Common to both

- `reason` and `evidence`: as on an override. At least one evidence item backs the drivers or the
  path itself and names no `figure`: "the path needs its own evidence item".
- `debt` and `cash`: leave them out, and the server reads the newest annual balance sheet, or an
  applied balance override. Pass one only where the balance sheet is wrong or missing. Each figure
  passed needs its own evidence item, with `figure` set to `debt` or `cash`.
- The levels take the moat class of the current review, else the snapshot's. A value a share at or
  below zero is kept as computed, with no levels.

The refusals, each a sentence, nothing stored: a blank reason; no evidence; both forms, "a
secondary valuation takes drivers or parts, not both", or neither, "a secondary valuation needs
drivers or parts"; "the path needs its own evidence item"; a debt or a cash with no evidence item
of its own; "settings changed: run a revalue" and its two siblings; a `guidance` item's 400, 404 and
409, as on an override; "foreign filer: currency and share-unit handling not built yet"; "no
diluted share count"; on the drivers form, "no trailing revenue on file". Then the bounds, each
naming its rule with the policy's figures: "a secondary valuation runs 3 to 15 years"; "revenue_growth
has 4 entries for 5 years" (or `operating_margin`); a driver out of its range, "tax_rate is 0% to
50%"; the terminal growth, "the terminal growth is −100% to g_T, 3.0%"; on the parts form, "at least
one part", "at most 10 parts", "a part has 3 to 15 years".

The drivers or the path are your judgment, carried by the evidence: a tool's input, not a report's
text. The report cites the stored record: `secondary:<id>/value`, `/years/<t>/<line>`,
`/drivers/<name>`, `/grid/<i>/<j>` and the others of `reference/citations.md`.

## The sensitivity reading

How much of the route's value is assumption, as a grid you cite and never compute. Call
`sensitivity(symbol, row_tag, row_values, col_tag, col_values)`. The engine values the latest
snapshot under the applied overrides, with the two inputs set to each pair of the values given.
Nothing is overridden, and the review does not move.

- The two tags are inputs of the overrides table that the route reads, and they differ: "the two
  tags differ".
- Each axis holds one to five values, in the unit the engine reads, like an override's `new`: "an
  axis holds one to five values".
- A value is refused as an override of the input would be: a locked input, a tag that is not an
  input, a route that does not read it, a value outside its range. The evidence rules do not apply.
- The answer marks `current`, the pair in force as `[i, j]`, or `null` when no pair is.
- A cell whose valuation refuses is `null`. A cite of it is `unresolved reference`.

Cite a cell as `sensitivity:<id>/<i>/<j>`, rows and columns counted from 1. A grid the route
reads well:

| Route | Rows | Columns |
|---|---|---|
| Mature Growth | `growth.belief` | `return.runway` |
| Mature Stable | `return.runway` | `moat.class` |
| High Growth, Young Growth | `margin.target` | `path.hold` |
| Decline | `decline.rate` | `capital.sales_to_capital` |

Put the input's current value in the middle of each axis, so the grid reads around it. A Start-up
company has no route value, so it has no grid: its section 8 states the price-implied requirement,
and the secondary valuation stands in.

## The judgments

A judgment is the record of one of the report's input decisions: `{judgment, decision,
override_id?}`. The decision is one or two sentences, in words. Name the override it produced, when
it produced one. Give each kind once. A judgment takes no other key: one with a `bull` or a `bear`
is refused (400), naming the key. The debate lives in section 6, and the thesis in section 7.

| Judgment | On | What it records |
|---|---|---|
| `phase` | every report | the life-cycle phase the classifier gave, and whether it fits |
| `moat` | every report | the moat class: how long the company can earn more than its cost of capital |
| `belief` | every report | the growth rate the route holds: the belief on Mature Growth, the held rate on High Growth and Young Growth, the decline rate on Decline; on Mature Stable and Start-up, which hold none, the growth the evidence supports against the growth the price needs |
| `roic` | Mature Growth, Mature Stable | the return on invested capital and the runway return |
| `target_margin` | High Growth, Young Growth, Start-up | the operating margin the company reaches in year ten |

The route that decides the list is the current review's when the company has one, else the
snapshot's. The decision holds no figure, not even a cited one: the check rejects any quantity
there. Put the figures in section 8, cited, and keep the decision in words. Section 12 of the report
lists the decisions in one sentence each.
