# The research round: the consensus read from one answer, the stock-pay charge an agent can set, the share-count check, the thin-consensus note, the wider runway range, the ten-year margins, the newest balance sheet and the minority interest: design

Status: written 2026-11-13. The research agents' reports 20 to 31 named gaps in the engine and its
data; the founder's review of 2026-11-13 filed them (B-172 to B-179) and chose this group for the
next iteration. The founder skipped the brainstorm's questions and asked for the design from
Claude's recommendations, so each decision in the log at the end is Claude's recommendation,
taken on that word, but for one: the design check found that a full refresh drops every
period-tied correction, and the founder ruled on it (section 11a). Items marked *my call* were
settled by Claude while writing and can be overturned as the others can. Builder check: see the
status line at the end of the log.

This document amends `docs/method.md` (the method as built) in sections 2, 4.1, 4.2, 5.2, 5.11,
5.12, 5a.2, 5a.9, 5a.13, 5a.14, 6.5, 6a.5, 6a.6, 6a.7, 6a.10, 6b.2, 6b.4, 6b.6, 8, 10, 11, 14.2
to 14.6, 15.3 and 16.2, and the Methodology page with them. Every earlier spec stands for what it
does not mention. When a piece is built, its sections go into `docs/method.md` in the same
commits, and that document stays the statement of what runs.

## 1. What this is

Nine changes in two plans. Each plan has its own method version, its own policy version and its
own live step, so each readout shows one cause.

**Plan 1: what the store already holds, read better.** Method `fairband-mechanical/1.3`, policy
`fairband-policy-v13`, applied by one revalue. No vendor call.

1. **The consensus from one answer** (B-172). Assembly reads each estimate dataset from one vendor
   answer, the newest that holds rows. Today it reads the newest row of each period across every
   stored answer, so a period FMP moved by a day keeps its old row beside the new one, and the old
   row can be the one kept.
2. **The stock-pay charge** (B-115, B-116). Two notes say when the charge may be wrong: the stored
   stock pay is missing, or the basis test may misread. Two inputs let an agent decide with
   evidence: the basis itself, and the trailing stock pay.
3. **The share-count check** (B-162). A warning when the market cap and the price times the
   diluted count disagree by more than 30%. No value changes.
4. **The thin-consensus note** (B-175). A note when the next-twelve-months EPS sums a period with
   fewer than 5 analysts. No value changes.
5. **The runway return's range** (B-178). An override and a sensitivity axis take up to 500%.
6. **The ten-year median margins** (B-164). Every routed result carries the ten-year median
   operating margin and net margin with their counts of years, for the agent's cycle judgment.
7. **The life of a period-tied correction** (the design check's finding, the founder's ruling).
   An agent's correction of one period's figure drops when a newer period is on file or its
   reading changed. Today it drops whenever the statements are fetched again.

**Plan 2: the balance sheet.** Method `fairband-mechanical/1.4`, policy `fairband-policy-v14`,
applied by one full refresh, which fetches one more dataset per company.

8. **The newest balance sheet** (B-173). The refresh fetches the quarterly balance sheet. Debt,
   cash and the liquidation floor read the newest sheet on file, a year's or a quarter's.
9. **The minority interest** (B-174). The routes that value the firm subtract the minority
   interest at book before the value a share. An agent may correct the figure.

## 2. Goals

- A value input is never a stale row that the vendor no longer gives.
- A row whose stock-pay charge may be wrong says so, and an agent can set the charge right with a
  filing, in either direction.
- A row whose share count the market cap contradicts says so, on the screen and to the agent.
- The debt and the cash of a firm-value route are at most a quarter old where a quarter is on
  file.
- The value a share of a firm-value route leaves out what belongs to minority owners.
- Each change is read out on the live data against the row it came from.

## 3. Non-goals

- No change to how the NTM anchor is summed (B-175's other options). The note comes first; the
  anchor is decided after plan 1's revalue shows the corrected rows.
- No change to the share count the engine divides by (B-162's other options). ROAD shows that
  the market cap can be the wrong figure.
- No refetch of a cash flow statement when a release is newer (B-116's second half). The new
  input is the door.
- No minority interest at market value, and none in the secondary valuation, whose debt figure
  an agent may raise with evidence.
- No balance lines in the `quarters` tool, and no quarterly ROIC or quality scores.
- No change to the return on capital near zero (B-8), the cycle cut's start (B-165), the Mature
  Growth inputs of B-145, B-146 and B-148, or the report page's charts.
- B-106 asks for a peak-margin flag. `margin-flag` is that flag, built with the first screen; it
  fires on 8 of the 10 cyclical companies reported (not LRCX, not ASML). The row closes in the
  backlog with this spec, and no code follows.

## 4. Anti-goals

- A flag that changes a value. Sections 7.1, 8 and 9 add words to a row and nothing else.
- A threshold fitted to the reported companies. Each new threshold is a policy value with its
  count on the whole screen beside it (section 5).
- A mature row that moves in plan 2. Mature Growth and Mature Stable read no balance sheet line
  for their value; a scratch revalue proves it (section 17).
- An override an agent made that silently stops meaning what it said. Section 12.4 says what
  happens to each balance correction on file.

## 5. The evidence (the live database, read-only, 2026-11-13)

The screen of refresh 57: 1,598 rows, 1,385 valued (747 Mature Growth, 454 Mature Stable, 94
revenue-growth, 90 Decline).

**The consensus.** No stored answer of any of the 1,598 companies holds two estimate rows within
seven days of each other, on either dataset. FMP moved AAPL's period ends from the 27th to the
26th between the answers of 3 Nov and 5 Nov. 58 companies hold an old estimate row ending after
1 Oct 2026 within seven days of a current one; the engine keeps the old row on 53 (30 valued
Mature Growth, 20 valued Mature Stable, 4 Decline among the 58; QCOM and TXRH 13 rows each, MTSI
12, AMD 7). AAPL's stored NTM EPS of $9.32 sums three current quarters and one of 3 Nov; the
current four sum to $9.28. Its fiscal 2027 row is the old $9.555 on 30 analysts where FMP now
gives $9.425 on 28. No split row is missing from a company's newest split answer.

**Stock pay.** Trailing stock pay is exactly 0 on 95 of the 747 valued Mature Growth rows and
missing on 11; 64 of the 95 hold a fiscal year above zero (WMT, GE, PM, MCK, AZN, NVO). The basis
test reads `excludes-sbc` on 474 rows, `includes-sbc` on 245, unknown on 28. Of the 221
`includes-sbc` rows with stock pay on file, after-tax stock pay a share is 2% of street EPS or
more and `large-nri` fires on 50, and the trailing effective tax rate is at or below half the
statutory rate on 44. Of the 395 `excludes-sbc` rows with stock pay, the gap between street and
GAAP EPS is 3 times the after-tax stock pay a share or more on 174, 5 times on 124 and 10 times
on 60. Five reports of 32 met a misread: QCOM, PLTR and CLS with the charge off, NVS and V with
it on (NVS: street $8.89 against GAAP $5.24 on a stock pay of $0.26 a share after tax).

**The share count.** On refresh 34 (2026-11-11), 32 of 1,598 eligible rows had a market cap more
than 30% away from the price times the diluted count, 18 of them valued (SYM 4.6x, ANDG 8.5x,
EROK 4.1x, EE 3.5x; TKO 0.38x). ROAD reads 0.85 because FMP's market cap leaves out its Class B
shares.

**The NTM quarters.** Of the 747 valued Mature Growth rows, 310 have an NTM quarter with fewer
than 5 EPS analysts and 164 one with fewer than 3.

**The balance sheet.** On the 184 valued revenue-growth and Decline rows, the newest quarter on
file ends a median 273 days after the balance sheet in use, and more than 170 days after it on
170. Of the 184, 49 that report in US dollars show a minority interest above zero; at book it is
more than 5% of the value a share on 17 and more than 20% on 8 (DXC, TDS, CIFR, MRVI, CVI, DOW,
IEP, MPC). Seven more report in another currency and were not converted.

## 6. The consensus from one answer (B-172)

**The rule.** For `estimate-annual` and for `estimate-quarter`, a company's rows are those of one
stored answer: the newest answer of that dataset that holds at least one row for the company.
Rows of an older answer are not read. The rule lives in assembly's read of the two datasets
(`build_inputs`), which every reader of the consensus goes through: the `/estimates` read, the
`estimate:` refs and the guided-year drop; the multiples log is written from results. It does not
live in `observations_for`, which also serves the quote, the profile, the splits and the rates.
That function picks the newest row of each period and field, so today one period's fields can
even come from two answers.

**An empty answer** (*my call*). FMP's `[]` is stored as an error with no rows, so the newest
answer that holds rows is the newest usable one, and an empty answer leaves the earlier rows
read, as today. A vendor that answers empty once must not turn a valued row into a refusal. The
consensus input's `as_of` is the answer's date, so its age shows where the input is cited.

**What stays.** The row a week after the trailing period end is still skipped (method 5.2): the
statements and the consensus can end a day apart inside one answer. The rule that keeps one row
of two within seven days also stays, as a guard (*my call*): no stored answer needs it today, and
without it two such rows would break the window's chain into a refusal. Method 2 and 5.2 lose the
words "FMP's two fiscal calendars": the two rows were two answers.

**The other datasets** keep their reads. A street actual is a past fact matched by its exact
period end. A split's answer is the whole history and no stored answer contradicts another. The
quote, the profile and the scores have no period.

**What moves.** The anchor, a step or the base year of the 53 companies whose kept row was an old
one. A row whose newest answer lacks a period that an old row supplied refuses "incomplete NTM
consensus"; the readout names each.

## 7. The stock-pay charge (B-115, B-116)

Method 5.2 stands: the anchor subtracts after-tax stock pay a share when the consensus leaves it
out, and the basis test decides that from the gap between street and GAAP trailing EPS. Mature
Growth alone reads it.

### 7.1 Two notes

Both are notes: shown, never counted, no value moved.

**`stock-pay-missing`**, "Stock pay missing". On a Mature Growth row whose trailing stock pay is
zero, or has a trailing period at zero, while a fiscal year on file is above zero. The sentence
names the newest such fiscal year and its figure, and says the charge is nil or short.

**`sbc-basis-uncertain`**, "Stock-pay basis uncertain". On a Mature Growth row, one sentence for
each reason that holds:

1. The basis reads `includes-sbc`, the stock pay is material, and `large-nri` is on the row: a
   one-time item may sit in GAAP earnings and hide the gap.
2. The basis reads `includes-sbc`, the stock pay is material, and the trailing effective tax
   rate is at or below `sbc_basis_tax_share` (0.5) of the statutory rate: a low tax may close
   the gap. The rate is the trailing periods' income tax over their pre-tax income, and has no
   reading on a pre-tax income at or below zero. Both lines are stored already; their trailing
   sums are new in the trailing figures.
3. The basis reads `excludes-sbc` and the gap is `sbc_basis_gap_multiple` (10) times the
   after-tax stock pay a share or more: the adjusted figure leaves out far more than stock pay,
   and the figures cannot say whether it leaves out stock pay too.

Stock pay is material when its after-tax figure a share is `sbc_material_share` (2%) of the
street trailing EPS or more, on a street EPS above zero. Expected on today's screen: about 50, 44
and 60 rows. Neither note shows in a review under an applied `earnings.sbc_basis`: the agent
decided.

### 7.2 Two inputs

| Tag | Routes | Takes | Lifetime | Bridge label |
|---|---|---|---|---|
| `earnings.sbc` | Mature Growth | the trailing stock pay, a total in the reporting currency, 0 or more | period-tied only | stock pay |
| `earnings.sbc_basis` | Mature Growth | `includes` or `excludes` | lasting or period-tied | stock-pay basis |

`earnings.sbc` replaces the stored trailing figure wherever the anchor reads it: the test and
the adjustment. `earnings.sbc_basis` replaces the test's reading; the test is not run.
`earnings.nri_gap` keeps its effect on the test while no basis override is applied. In the
bridge's order they follow `earnings.nri_gap`, the figure first and the basis second (*my call*).
Both follow the rules of method 14.3 as they stand, and no rule is added (*my call*): on a row
where an applied `earnings.ntm` already replaces the adjusted consensus, either one applies with
a bridge line of zero, as method 14.4 has it for any input that an earlier override made moot.

The playbook asks the agent, in every Mature Growth report, to read the company's own definition
of its adjusted EPS in the release, to state whether it leaves out stock pay, and to set
`earnings.sbc_basis` with that passage as evidence when the row's reading differs. It asks for
`earnings.sbc` from the filing's cash flow statement when `stock-pay-missing` shows.

## 8. The share-count check (B-162)

**`share-count-gap`**, "Share count and market cap disagree". On every result that has a market
cap, a price and a diluted count, valued or refused:

    ratio = market cap ÷ (price × diluted shares)

with the market cap brought to US dollars by the row's exchange rate on a company in another
currency, and the count as the row reads it after the split rule and the ADR basis rule. The
flag fires when the ratio is outside `share_count_gap_band` (0.7 to 1.3), an edge being inside.
The sentence gives the ratio, both figures, and the two readings: the count may leave out a
share class or units that convert to shares, or the market cap may leave one out. In a review it
reads the count in force, so a `shares.diluted` that reconciles the two clears it.

It is a quality warning, the twelfth (*my call*): the value a share of such a row can be wrong
by the ratio, so the row leaves the Clean filter and counts in the Warnings column.

## 9. The thin-consensus note (B-175)

**`thin-ntm`**, "Thin NTM consensus", a note. On a Mature Growth row whose NTM window holds a
period with fewer than `analyst_min` (5) EPS analysts, or with no count. The sentence gives the
number of such periods, the smallest count and its period. It does not show in a review under an
applied `earnings.ntm`, whose anchor is the guidance. The window's quarters carry the count
already (`QuarterEstimate.analysts`).

## 10. The runway return's range (B-178)

`return.runway` takes above 0% up to 500% (policy v13, `override_ranges`: 0.0 to 5.0, the lower
end excluded as now). A sensitivity axis is checked as an override, so a grid can hold the
engine's own measure: 332.6% on AAPL, 193.9% on ADSK. The bound still catches a percent typed as
a whole number.

## 11. The ten-year median margins (B-164)

Every result that reached a route, valued or refused there, carries in its intermediates:

    margin_history: { operating: { median, years }, net: { median, years } }

The operating margin is `margin-flag`'s: operating income over revenue for each fiscal year with
both and a revenue above zero, over the last ten such years. The net margin is net income over
revenue on the same rule; the engine's fiscal-year series carries no net income (method 3.1), so
assembly reads it from the annual statements' lines. `years` is the count behind each median; a
median with no year is
absent. Both are on the statements' basis, as reported. Mature Stable's own `median_margin`
stays where the route reads it.

The playbook's cycle formula changes one term: the mid-cycle margin is the ten-year median net
margin, `snapshot:<id>/intermediates/margin_history/net/median`, in place of the middle of the
growth table's five years. The ruling of 2026-11-11 stands otherwise: the full gap by default,
half with evidence from a filing or a transcript, never less. Two sentences are new. A history
of fewer than ten years is named with its count. And where the consensus EPS is on a basis that
leaves out the amortization of bought intangibles while the history is as reported (AMD, report
30), the full gap cuts for accounting as well as for the cycle: the agent says so, and that is
evidence for half. An `earnings.cycle_gap` on file keeps its figure until its review is made
again.

## 11a. The life of a period-tied correction

The founder's ruling of 2026-11-13, built in plan 1. It amends method 14.6 and the Tier 2 spec's
rule behind it.

A period-tied override is a correction of one period's figure. Before a recompute at a full or
scoped refresh or a revalue, it drops, by the system and with the reason, on the first test that
holds:

1. **A newer period is on file.** The trailing period end the new snapshot reads is after the
   trailing period end of the snapshot the override was made on: "a newer period is on file
   than the one the override corrected". On the fiscal-year fallback the period end is the
   fiscal year's.
2. **The reading changed.** The engine's reading of the input on the new snapshot differs from
   the value the override corrected: "the input the override corrected changed", as today.

The day the statements were fetched drops nothing. A refetch of the same statements leaves every
correction applied. The lasting overrides and the guided-year rule of 14.6 are untouched.

Where a snapshot made before 1.3 does not carry its trailing period end as a figure of its own,
the builder reads it from the `as_of` its trailing inputs cite; from 1.3 on, a result carries it.

The playbook's line on when a period-tied override ends changes with the rule: it holds until
the company reports a new period or the figure it corrected changes.

## 12. The newest balance sheet (B-173)

### 12.1 The dataset

The refresh fetches FMP's balance sheet by quarter, eight periods, as it fetches the income and
cash flow statements, stored as `balance-quarter` with the annual sheet's lines. It is not a
required call: a company without one reads its annual sheet as today. The dataset joins the
statement endpoints, so the backfill covers it, and a company's fetch becomes fifteen FMP calls.

### 12.2 The rule

**The newest balance sheet** of a company is the stored sheet with the latest period end among
`balance-annual` and `balance-quarter`; on a tie, the annual one. A quarterly sheet in a currency
other than the reporting currency is skipped (*my call*), as method 4.2 skips such a quarter of
the income statement.

It gives: the debt and the cash (`shortTermDebt`, `longTermDebt`, `cashAndCashEquivalents`,
`shortTermInvestments`, as method 5a.9 sums them) for the revenue-growth route's equity, the
Decline route's going concern, distress sale and rating, the Start-up route's requirement, cash
floor and burn cover, and the secondary valuation's default debt and cash; the lines of the
Decline route's liquidation floor (6a.6); and the minority interest (section 13).

It does not give: the capital years of the ROIC and the sales-to-capital, the balance years of
Altman's Z″ and Piotroski's F, or the report's solvency table. Those stay on fiscal years. The
Decline route cites `total_current_assets` and `total_liabilities` today for both the floor and
Z″; the floor's two lines get their own input names, since they can now be a quarter's.

A line the newest sheet does not present counts as nil and is named, as today. Each input's
`as_of` is the sheet's period end, and its note names the period, "the balance sheet of fiscal
2026 Q3".

### 12.3 The vendor check

The builder's first task in plan 2, on FRVO, RKLB and two companies that report by half-year:
does FMP's quarterly balance sheet exist, does its newest period end at or after the annual
one's, which of the lines of 12.2 does it present, and what does a half-year reporter's answer
hold. The findings go into the readout. A finding that breaks 12.2 comes back to the founder
before the build goes on.

### 12.4 The corrections on file

Method 14.6 drops a period-tied override on either of two tests, and the code checks them in
this order (`refresh/reviews._drop_reason`): the company's data date moved past the override's
snapshot's, "the statements moved past the override's snapshot"; or the engine's reading of the
input changed, "the input the override corrected changed". The data date is the day the
statements were last fetched (method 4.10), not a period end. So any full refresh that fetches a
company's statements on a later day drops every period-tied override of that company, whatever
the statements say. Ten are applied on 2026-11-13: SYM's share count and cash, CLS's gap and two
steps, FRVO's cash and debt, RKLB's cash, debt and share count. They stand only because no full
refresh fetched those companies since.

The founder ruled on 2026-11-13 that the drop follows the period (section 11a), and plan 1
builds it, so the rule is in force before plan 2's refresh. Under it, the first refresh under 1.4
drops a balance correction only where a newer sheet changed the engine's reading: RKLB's and
FRVO's corrections brought in a later quarter that the engine now reads itself. SYM's share count
stays. The readout lists each drop with the reviewed value before and the mechanical value after,
and each period-tied override that stays.

## 13. The minority interest (B-174)

**The figure.** `minorityInterest` joins the stored balance lines, annual and quarterly; the
backfill stage reads it from the answers already stored. A company's minority interest is the
newest balance sheet's line. A line not presented, or a figure at or below zero, counts as nil,
with no flag: most companies have none.

**Where it enters.**

- Revenue-growth (5a.9): equity = firm value − debt − minority interest + cash.
- Decline: the going-concern value a share (6a.5) = (firm value − debt − minority interest +
  cash) ÷ diluted shares. The distress-sale value a share (6a.7) = max(0, distress proceeds −
  debt − minority interest) ÷ diluted shares. The liquidation floor (6a.6) reads NCAV − minority
  interest (*my call* on the last two: each is the common owners' claim). The distress
  probability's rules read debt and cash alone, as now.
- Start-up (6b.2): the price's enterprise value = market cap + debt + minority interest − cash.
  The cash floor (6b.4) = (cash − debt − minority interest) ÷ diluted shares (*my call*), so
  `below-net-cash` stays the floor's test in total.
- Mature Growth and Mature Stable: nowhere. Their earnings are after the minority's share.

The routes cite it as a DATA input, `minority_interest`, and carry it in their intermediates
beside debt and cash, so a price refresh rebuilds with it.

**At book.** Damodaran subtracts the minority interest at market value where he can estimate
one. The book figure is the mechanical floor; the Methodology page says so.

**The input.** `balance.minority`: the minority interest, a total in the reporting currency, 0
or more; revenue-growth, Decline and Start-up; period-tied only; bridge label "minority
interest", after `balance.cash`. An agent uses it for a market value, or for a redeemable stake
that the line leaves out (FRVO's tax-equity partners).

## 14. Policy v13 and v14

v13 adds four values, none a setting: `sbc_material_share` 0.02, `sbc_basis_tax_share` 0.5,
`sbc_basis_gap_multiple` 10, `share_count_gap_band` 0.7 to 1.3. Its `override_ranges` gain
`earnings.sbc` (0 to 10^15, the stand-in for no upper bound) and change `return.runway` to 0.0
to 5.0. `earnings.sbc_basis` takes words and has no range. v14 adds `balance.minority` (0 to
10^15). Each source line names this spec and its section.

No database migration is needed: a tag, a state and a dataset are text, and the schema has no
check constraint on them.

## 15. The documents

- `docs/method.md`: the sections named at the top, the flag table of section 8 (four new rows,
  `share-count-gap` counted), the version rows of section 11, and 14.2 to 14.5 for the three
  inputs: twenty inputs after plan 1 and twenty-one after plan 2, where the documents count them.
  The counts also stand in code and on the page: "eleven" in `engine/flags.py` and
  `reports/render.py`, "eighteen" in `engine/overrides.py` and `methodology.html`.
- The Methodology page: the flags it lists, twelve quality warnings where it says eleven, the
  growth, Decline and Start-up entries' equity step, and each worked example of a route plan 2
  moves, re-read on the new method version.
- The drawer: the new flags in its lists; the minority interest beside debt and cash; the
  balance sheet's period on those rows.
- The playbook: section 7.2's two steps, the cycle formula of section 11, the three inputs in
  the overrides table with what evidence each needs, and the new intermediates and flags in the
  citations and tools references.
- `docs/backlog.md`: each row closed moves to Done with its commits; B-106 closes as built;
  what a review parks goes in as new rows.

## 16. Tests the builder must write

Each test fails before its change, and its expected figures are worked by hand.

Plan 1:
- Two stored answers of one company whose period ends differ by a day: assembly, `/estimates`
  and an `estimate:` ref read the newest answer's rows alone, whatever the analyst counts. An
  empty newest answer leaves the older rows read.
- `stock-pay-missing` on a zero trailing figure and on one zero quarter, each with a fiscal year
  above zero; silent on a history of zeros.
- `sbc-basis-uncertain`, one test for each reason at its edge (2%, half the rate, 10 times), and
  silent just inside each; silent under an applied `earnings.sbc_basis`.
- `earnings.sbc_basis` in both directions moves the NTM EPS by exactly the adjustment; with
  `earnings.sbc` the adjustment uses the new figure; the bridge's deltas sum to the reviewed
  value; under an applied `earnings.ntm` each applies with a bridge line of zero.
- `share-count-gap` at 0.7 and 1.3 (silent) and just outside (fires); on a company in another
  currency; cleared by a `shares.diluted` that reconciles; counted by `flag_count`.
- `thin-ntm` at 4 and at 5 analysts, and on a missing count.
- A `return.runway` of 3.326 applies, and a sensitivity axis holds it; 5.01 is refused.
- `margin_history` on a row of each route, with a hand-worked median of an even and an odd
  count, and a history shorter than ten years.
- A period-tied override stays applied when the same statements are fetched again on a later
  day; it drops with the first sentence of 11a when the trailing period end moves, and with the
  second when its reading changes; an override made on a snapshot from before 1.3 is judged by
  the `as_of` of that snapshot's trailing inputs.

Plan 2:
- A company with a quarterly sheet newer than its annual one: each route of 12.2 reads the
  quarter's debt and cash; a tie reads the annual; no quarterly sheet reads the annual.
- The ROIC years, Z″ and F are unchanged by a quarterly sheet.
- The minority interest in each formula of section 13, hand-worked; nil at zero, below zero and
  when not presented; rebuilt at a price refresh.
- `balance.minority` applies, bridges and drops as the other balance corrections do.
- A period-tied `balance.cash` drops when a newer sheet changes the reading.
- A Mature Growth and a Mature Stable golden are bit for bit under 1.3 and 1.4.

## 17. Acceptance and the readouts

Each plan: the merge, a backup of the live database, the server restarted from main, a scratch
run first and then the live step, the two compared. The readout goes into this spec's decision
log.

**Plan 1, one revalue.**
- Every row whose value, levels or refusal differs from the snapshot before, by cause. Expected:
  the companies whose kept row was an old one, and no other row. AAPL's NTM EPS is the sum of
  its newest answer's four quarters.
- The counts of the four flags against section 5: `stock-pay-missing` 64 or more (the 64 rows
  with a zero trailing figure, and those with one zero quarter, which section 5 did not count),
  `sbc-basis-uncertain` near 50, 44 and 60 by reason, `share-count-gap` near 32 with SYM, ANDG,
  EROK and EE named and ROAD absent, `thin-ntm` near 310.
- On a scratch copy: NVS under `earnings.sbc_basis` = `includes` gains its $0.26 of NTM EPS; CLS
  under `excludes` is charged its stock pay; AAPL's sensitivity holds 332.6%.
- `margin_history` on every routed row; ASML's ten-year net margin reads 26.0% and TTMI's 3.1%,
  as B-164 worked them.
- Every lasting override keeps applying. A period-tied override of a consensus input (a step or
  an NTM anchor) drops where the one-answer read changed the reading it corrected, by method
  14.6; the readout names each, and that is the right outcome (*my call*).
- The ten period-tied overrides of section 12.4, each named with its state after the revalue.

**Plan 2, one full refresh.**
- The vendor check of 12.3.
- A scratch store that holds the new dataset, revalued under 1.3 and under 1.4: every Mature
  Growth and Mature Stable row bit for bit; every other row's move listed.
- The revenue-growth, Decline and Start-up rows: how many read a quarter's sheet, the sheet's
  median age before and after, the ten largest moves named, the rows that newly refuse or newly
  value.
- The minority interest: the rows with a figure, the moves, DXC and TDS named.
- The period-tied overrides (12.4): SYM's share count still applied after the refetch, the
  balance corrections dropped for a changed reading, RKLB's and FRVO's mechanical values beside
  their reviewed ones.

## 18. Left to the builder

- How the one-answer read is written: an argument of `observations_for` or a sibling; the SQL.
- The names inside the anchor for the override of the basis and of the figure, and how the
  result records that the basis came from an agent.
- The flags' exact sentences in the page's register; their place in each route's flag order,
  after the flag each is nearest to (`sbc-basis-unknown` for the stock-pay pair, the share
  guards for `share-count-gap`, `few-analysts` for `thin-ntm`).
- The record that carries the newest balance sheet into `CompanyInputs`, and how the Decline
  floor takes its lines from it.
- Whether `margin_history` shares code with `margin-flag`'s window.
- The split of each plan into tasks.

## 19. Order of work

Plan 1: policy v13 and the 1.3 rows of `docs/method.md`; the one-answer read with its readers;
the life of a period-tied correction; the two stock-pay notes; the two inputs; the share-count
check; the thin-consensus note and the range; `margin_history`; the drawer, the Methodology page
and the playbook; the scratch revalue and the live step.

Plan 2: the vendor check; policy v14 and the 1.4 rows; the dataset, its normalizer and the
backfill; the newest balance sheet in assembly and its readers; the minority interest in the
three routes; `balance.minority`; the drawer, the Methodology page and the playbook; the scratch
runs and the live step.

## 20. Sources

- Damodaran, *Investment Valuation* and *The Dark Side of Valuation*: equity is the firm's value
  less debt and less minority interests, plus cash; the minority interest at market value where
  one can be estimated.
- Damodaran, "Ups and Downs: Valuing Cyclical and Commodity Companies" (2009), as B-164 cites
  it: a normalized margin is averaged over a period long enough to hold a whole cycle.
- The research reports 20 to 31 and the founder's reviews of 2026-11-11 and 2026-11-13
  (`docs/backlog.md`, B-115, B-116, B-162, B-164, B-172 to B-178).

## Decision log

| Date | Decision |
|---|---|
| 2026-11-13 | The shape of the iteration: the small fixes with no spec (done, main 5d95da6), then this round as one spec and two plans, then one spec for each later theme. Claude's advice; the founder agreed. |
| 2026-11-13 | The founder skipped the brainstorm's questions: the design follows Claude's recommendations. Each line below is one of them. |
| 2026-11-13 | B-172: estimates are read from the newest answer that holds rows; the seven-day merge stays as a guard; an empty newest answer leaves the older rows read. |
| 2026-11-13 | B-115 and B-116: two notes and two inputs, `earnings.sbc_basis` and `earnings.sbc`; no change to the test itself. |
| 2026-11-13 | B-162: the flag only, counted as a quality warning; the count the engine divides by is not changed. |
| 2026-11-13 | B-175: the note only; the anchor is decided after plan 1's revalue. |
| 2026-11-13 | B-178: the range goes to 500%. |
| 2026-11-13 | B-164: the ten-year medians in the intermediates; the playbook's formula reads the net one; a basis that leaves out amortization is evidence for half the gap. |
| 2026-11-13 | B-173: the newest balance sheet for debt, cash and the liquidation floor; the ROIC and the quality scores stay on fiscal years. |
| 2026-11-13 | B-174: the minority interest subtracted at book on the three firm-value routes, with `balance.minority` as the agent's correction. |
| 2026-11-13 | The life of a period-tied correction: it drops when a newer period is on file or its reading changed, not when the statements are fetched again. Founder, on the design check's finding that any full refresh drops all ten on file (SYM, CLS, FRVO, RKLB), choosing this over keeping the rule and making the corrections again. Built in plan 1. |
| 2026-11-13 | Settled by Claude after the design check, each marked *my call* where it stands: no new rule for an override that an applied `earnings.ntm` makes moot (a bridge line of zero); a period-tied consensus override that drops at plan 1's revalue for a changed reading is the right outcome; a quarterly balance sheet in another currency is skipped; the Start-up cash floor subtracts the minority interest. |

Builder check: done 2026-11-13, one round (Opus 5.5, xhigh). It found two statements about the
method that were wrong (the drop rule of 12.4; a refusal for an override that moves nothing,
which no rule gives) and one acceptance line that clashed with method 14.6; all three are
corrected above. Of its five questions, one was the founder's (section 11a) and four were
settled as *my call*. Its findings in the code are stated where they apply: sections 6, 7.1, 11,
12.1, 12.2, 14 and 15.
