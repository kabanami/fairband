---
name: fairband-research
description: Research one company for Fairband over its MCP tools, from a work item to a published report in which every number is cited, when the user asks for a Fairband valuation review or full report or names a Fairband work item.
---

# Fairband research

Fairband is a valuation screen on the user's own machine. Its engine computes every value. You
research a company, change the engine's inputs with evidence, and write a report. You never write
a value yourself.

This skill takes one work item (a request for research on one company) from the inbox to a
published report. Run the eleven steps below in order. Write every sentence, in the report and in
every reason, in the register of `reference/register.md`.

## Before you start

- The Fairband server must be running. When a tool answers "the Fairband server is not running:
  start `uv run fairband serve`", tell the user and wait. Go on once a tool answers.
- Every tool answers JSON. A refusal is `{"refused": <sentence>, "status": <code>}`. The sentence
  names the rule that stopped the call. Fix what it names. Repeat a call unchanged only when the
  sentence says to try again.
- The tools, their arguments and their answers: `reference/tools.md`.
- The rules the server checks every number by: `reference/citations.md`. Read it before you write.
- The report's sections, the summary page and a full example submission:
  `reference/report-template.md`.
- The register and the product's words: `reference/register.md`.

## The steps

### 1. Identify yourself

Call `identify(agent)` with the model identifier you run as, such as `claude-opus-5-5`. Give it in
lower case, exactly as the host reports it. Fairband records every write under it. A write before
`identify` is refused: "identify first: the model identifier you run as".

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

### 3. Read the company

Read everything the page shows:

- `company(symbol)`: the latest snapshot (the company's frozen inputs and the engine's result on
  them). Keep `snapshot.id`: the report cites this snapshot.
- `financials(symbol)`, `financial_tables(symbol)`, `estimates(symbol)`, `peers(symbol)` and
  `price_history(symbol)`: the stored figures, each with the ref to cite it by.
- `report(symbol)`: the latest report, when there is one. `reports(symbol)` lists every revision.
- `notes(symbol)`, `findings(symbol)`, `overrides(symbol)`, `reviews(symbol)`, `secondary(symbol)`
  and `kill_criteria(symbol)`: the research already on file.
- `policy()`: the policy values in force.
- `methodology(section)` for the company's route: `mature-growth`, `mature-stable`, `growth` (High
  Growth and Young Growth), `decline` or `start-up`. `methodology()` lists every section.

Section 4 of the report is written from the cells of `financial_tables`. Read each open kill
criterion (a measurable event that would prove the view wrong). When one has happened, move it with
`kill_criterion_set(id, "triggered", reason)`.

### 4. The fundamentals: the business and the industry

Read the filings with the host's own tools: the 10-K, the 10-Q, the proxy statement, the company's
own site. From Fairband, read `transcript(symbol, year, quarter)` for the earnings calls and
`segments(symbol)` for the revenue by product and by region. `insider_trades(symbol)` shows what
the insiders bought and sold.

Record a finding (a dated fact with its source) with `finding_add` for every number from outside
Fairband that the report will cite. Fairband's own figures need no finding: each read gives them
with their refs.

### 5. The news

Read `news(symbol, limit)` and the web. Explain each large price move in the price history. Note
the candidate kill criteria. Record each news item that matters to the value with `news_item_add`,
or pass it with the report.

### 6. The valuation

Read the engine's result in the answer of `company`: the value, the levels (the buy level, the fair
band and the trim level), the inputs with their tags (DATA, RULE or JUDGMENT), the intermediates,
the phase evidence and the flags. `methodology` explains each in plain words. Note each place where
the evidence of steps 4 and 5 disagrees with an input. Those are the candidate judgments.

### 7. The debate

For each judgment, write the bull view and the bear view. Every report judges the phase, the moat
and the belief. A Mature Growth or Mature Stable company adds the ROIC. A High Growth, Young Growth
or Start-up company adds the target margin. See "The judgments" below.

### 8. The decisions, the overrides and the value

Decide each judgment. Where a decision changes an input, write an override (a change to one input,
with its reason and its evidence) with `override_add`. One override changes one input. Its answer
carries the override's state and, when it applied, the review (the engine's value under the applied
overrides) with its bridge (the change from the mechanical value, one line per override). Read
both. `override_drop` drops an applied override. See "Overrides" below.

When the review is a refusal, or no route fits the company, value it a second way with
`secondary_valuation`. A second view on a valued company is allowed too. See "The secondary
valuation" below.

Compute every figure the report needs from stored figures with `derive`: a ratio, a difference, a
sum, a growth rate or a compound annual growth rate. Never compute one yourself.

### 9. The stance

Choose the stance: `buy`, `hold`, `trim` or `avoid`. Read the value against its levels. Take the
reviewed value when the current review has one. Take the snapshot's value when the company has no
review. Take the secondary valuation's when neither gives a value. Where a value and a secondary
valuation both exist, the value leads and the secondary valuation is the second view. `avoid` is
for a company you would not hold at any price shown. Weigh the research as well as the levels. The
report's reasons carry the stance.

### 10. The report

Write the sections of `reference/report-template.md`. Cite every quantity, by the rules of
`reference/citations.md`. Submit with `report_submit`. The server publishes a report whole or
rejects it whole. On a rejection, fix each finding and submit again. A structural refusal (a section
count, a heading, a judgment or the stance) is one sentence: fix it and submit again.

### 11. Complete the work item

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
- The text of a judgment holds no figure at all.
- Write in the register of design.md 9.2 (`reference/register.md`): the answer first; short
  sentences, one idea each; every term explained the first time; rounded numbers.
- No first person. Fairband has no voice: never "I", "we" or "our".
- The reason on an override is your own words. Fairband keeps it verbatim and shows it on the
  bridge.
- Start a refresh only when a refusal asks for a revalue, or when the user asks.

## Overrides

`override_add(symbol, tag, new, reason, evidence, lifetime, period?)` changes one input. The engine,
not you, computes the value it gives.

- `tag`: the input, from the table below.
- `new`: the new value in the unit the engine reads. A rate is a fraction: `0.12` is 12%. A word
  input takes its word, as a string: `"Wide"`, `"None"`.
- `reason`: your own words, kept verbatim.
- `evidence`: one item or more, each `{kind, ref, note}`. The kind is `filing`, `transcript`,
  `url`, `vendor`, `base-rate` or `finding`; the ref says where the evidence is.
- `lifetime`: `lasting`, or `period-tied` with `period`, the fiscal year it corrects (`2025`).

| Tag | Routes that read it | The input | Takes, the ends included |
|---|---|---|---|
| `phase` | every route | the life-cycle phase; the route follows it | `Start-up`, `Young Growth`, `High Growth`, `Mature Growth`, `Mature Stable` or `Decline` |
| `growth.belief` | Mature Growth | the belief: the growth rate after the analysts' years, before the fade to the long-run rate | −0.20 to 0.60 a year |
| `path.hold` | High Growth, Young Growth | the held rate of years four to the end of high growth | −0.20 to 3.00 a year |
| `path.step_2`, `path.step_3` | Mature Growth, High Growth, Young Growth, Decline | the consensus growth of year two or year three | −0.80 to 3.00 |
| `moat.class` | Mature Growth, Mature Stable, High Growth, Young Growth, Start-up | the moat class; it sets the margin of safety, the runway and the terminal return | `None`, `Narrow` or `Wide` |
| `margin.target` | High Growth, Young Growth, Start-up | the operating margin the company reaches in year ten | −0.50 to 0.60 |
| `capital.sales_to_capital` | High Growth, Young Growth, Decline | the revenue a dollar of invested capital buys | 0.1 to 10 |
| `return.runway` | Mature Growth, Mature Stable | the return on new capital in the runway years | 0 to 1.00 |
| `earnings.nri_gap` | Mature Growth, Mature Stable | the non-recurring gap in the earnings a share | −100 to 100 dollars a share |
| `decline.rate` | Decline | the rate at which revenue shrinks | −0.50 to 0 a year |
| `balance.debt`, `balance.cash` | High Growth, Young Growth, Decline, Start-up | the newest annual balance sheet's debt or cash | 0 dollars or more; period-tied only |

The ranges are the policy's `override_ranges`; `policy()` gives the values in force. The server
checks an override by these rules, in this order, and answers the first one it breaks:

1. `refused-locked`: a locked input (one no override may change). These are r (the hurdle rate),
   g_T (the terminal growth ceiling), the runway years, the fade years, the margin of safety, the
   fair band, the trim multiple, the terminal return, the deciles, the growth word, and every
   reported figure (the price, the shares, the market cap, the revenue, the operating income, the
   EPS). Debt and cash change only through the two balance tags.
2. `refused-not-input`: a tag that is not in the table.
3. `refused-route`: a route that does not read the tag. The route follows an applied `phase`
   override, so override the phase first. The Mature Stable route reads no consensus step, so
   `path.step_2` and `path.step_3` are refused there. A company with no phase reads no input but its
   phase: set its phase first.
4. `refused-unit`: a value outside the range, a word outside the words, a word where a number is
   due, or a lasting override of a balance tag.
5. `refused-evidence`: no evidence. A `growth.belief` or a `path.hold` above the sales class's
   90th percentile (`sales_p90_5y` in the base rates) also needs an item of kind `filing` or
   `transcript`. An item of kind `finding` does not count for this rule, even when the finding came
   from a filing.

A refused override is stored with its state and applies nothing. Its answer is the refusal's
sentence with the `override` record beside it. Fix the one thing the sentence names, and try again.

An applied override answers `{override, review, bridge}`. The bridge starts at the mechanical value
(the engine's value with no override), adds one line for each override in a fixed order, and ends at
the reviewed value. A line whose step refuses shows the refusal in place of a change. A review whose
last line refuses has no value: see "The secondary valuation".

One input holds one applied override. A new override on the same tag replaces the old one. An
override applies to the latest snapshot and to every later one. A period-tied override (a correction
of one period's vendor error) drops by itself once the company's data date moves or the engine's
own reading of the input changes. Add a note with `note_add(symbol, text, override_id)` when the
reason needs more words.

An override, a drop and a secondary valuation are refused with "settings changed: run a revalue"
(or "policy changed", or "method changed") when the latest snapshot was valued under other
settings. Call `refresh_start("revalue")`. Wait until `refresh_status()` shows no refresh running.
Read `company` again, since the snapshot id changes, and try again.

## The secondary valuation

A second valuation from a cash-flow path you supply. The engine discounts the path at r, adds the
terminal value, and bridges the firm value to a value a share, so the figure is a tool output. Use
it when the review is a refusal, when no route fits the company, or for a second view on a valued
company. It is refused for a foreign filer: "foreign filer: currency and share-unit handling not
built yet".

Call `secondary_valuation(symbol, parts, reason, evidence, debt?, cash?)`:

- `parts`: one to ten, each `{name, fcff, terminal_growth, note}`. One part is a discounted cash
  flow; several are a sum of parts.
- `fcff`: the free cash flow to the firm (the cash the business makes after its investment, before
  any payment to lenders or owners), in dollars, for years one to N. N runs from three to fifteen.
- `terminal_growth`: a fraction, at most g_T (`0.03` at the defaults; `policy()` gives the value in
  force). A lower or a negative rate is allowed.
- `reason` and `evidence`: as on an override. At least one evidence item.
- `debt` and `cash`: leave them out, and the server reads the newest annual balance sheet, or an
  applied balance override. Pass one only where the balance sheet is wrong or missing. Each figure
  passed needs its own evidence item, with `figure` set to `debt` or `cash`.

Each bound is refused with its sentence, nothing stored: no part or too many, a path too short or
too long, a terminal growth above g_T, a company with no diluted share count. The same 409 as on an
override applies: "settings changed: run a revalue".

The path's figures are your judgment, carried by the evidence; they are a tool's input, not a
report's text. The report cites the stored record: `secondary:<id>/value` and the others of
`reference/citations.md`. A value a share at or below zero is kept as computed, with no levels.

## The judgments

A judgment is one of the report's key decisions: `{judgment, bull, bear, decision, override_id?}`.
Name the override it produced, when it produced one. Give each kind once.

| Judgment | On | What it weighs |
|---|---|---|
| `phase` | every report | the life-cycle phase the classifier gave, and whether it fits |
| `moat` | every report | the moat class: how long the company can earn more than its cost of capital |
| `belief` | every report | the growth rate the route holds: the belief on Mature Growth, the held rate on High Growth and Young Growth, the decline rate on Decline; on Mature Stable and Start-up, which hold none, the growth the evidence supports against the growth the price needs |
| `roic` | Mature Growth, Mature Stable | the return on invested capital and the runway return |
| `target_margin` | High Growth, Young Growth, Start-up | the operating margin the company reaches in year ten |

The route that decides the list is the current review's when the company has one, else the
snapshot's. The text of `bull`, `bear` and `decision` holds no figure, not even a cited one: the
check rejects any quantity there. Put the figures in section 8, cited, and keep the judgment in
words.
