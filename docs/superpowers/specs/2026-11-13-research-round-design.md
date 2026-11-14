# The research round: the consensus read from one answer, the stock-pay charge an agent can set, the share-count check, the thin-consensus note, the wider runway range, the ten-year margins, the newest balance sheet and the minority interest: design

Status: written 2026-11-13. The research agents' reports 20 to 31 named gaps in the engine and its
data; the founder's review of 2026-11-13 filed them (B-172 to B-179) and chose this group for the
next iteration. The founder skipped the brainstorm's questions and asked for the design from
Claude's recommendations, so each decision in the log at the end is Claude's recommendation,
taken on that word, but for one: the design check found that a full refresh drops every
period-tied correction, and the founder ruled on it (section 11a). Items marked *my call* were
settled by Claude while writing and can be overturned as the others can. Builder check: see the
status line at the end of the log. Plan 1 is built and live since 2026-11-14 (method 1.3, policy
v13, main `6cba2e0`), with its readout in the decision log. On that readout the founder ruled on
three open questions on 2026-11-14 (B-175, B-180, B-181), each on Claude's recommendation; they
are sections 9a, 8a and 7.3 and join plan 2, whose plan is
`docs/superpowers/plans/2026-11-14-research-round-plan-2.md`. Plan 2 is not built.

This document amends `docs/method.md` (the method as built) in sections 2, 4.1, 4.2, 5.2, 5.11,
5.12, 5a.2, 5a.9, 5a.13, 5a.14, 6.5, 6a.5, 6a.6, 6a.7, 6a.10, 6b.2, 6b.4, 6b.6, 8, 10, 11, 14.2
to 14.6, 15.3 and 16.2, and the Methodology page with them. Every earlier spec stands for what it
does not mention. When a piece is built, its sections go into `docs/method.md` in the same
commits, and that document stays the statement of what runs.

## 1. What this is

Twelve changes in two plans: the nine of 2026-11-13, and three the founder ruled on plan 1's
readout on 2026-11-14. Each plan has its own method version, its own policy version and its own
live step, so each readout shows one cause. Plan 2 now holds two causes of a moved value, and its
readout keeps them apart by route: the balance sheet moves the revenue-growth, Decline and
Start-up rows, and the anchor rule moves Mature Growth rows.

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
10. **The NTM anchor on a thin window** (B-175, section 9a). Where a period of the NTM window
    in the last fiscal year it reaches has fewer than 5 EPS analysts, year 1 adds the window's
    share of the gap between that year's annual estimate and its periods' estimates. `thin-ntm`
    then fires only where a thin period is left as it is.
11. **A lasting nil stock pay** (B-181, section 7.3). `earnings.sbc` may be lasting at 0, for a
    company that pays no stock. `stock-pay-missing` stays as built.
12. **A reviewed row's flags** (B-180, section 8a). Where a review fills a row, the screen and
    the drawer show the review's flags. No value changes in 11 and 12.

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

- In plan 1, no change to how the NTM anchor is summed (B-175's other options). The note came
  first; the founder decided the anchor on plan 1's readout, and plan 2 builds it (section 9a).
  No change to the NTM revenue of the revenue-growth and Decline routes.
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
- A mature row that the balance sheet moves in plan 2. Mature Growth and Mature Stable read no
  balance sheet line for their value; a scratch revalue proves it (section 17). A Mature Stable
  value does not move at all. A Mature Growth value moves only by the anchor rule of section 9a,
  on a thin window whose annual figure exists.
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
and 60 rows. In a review, `sbc-basis-uncertain` does not show under an applied
`earnings.sbc_basis`, nor `stock-pay-missing` under an applied `earnings.sbc`: the agent decided.

### 7.2 Two inputs

| Tag | Routes | Takes | Lifetime | Bridge label |
|---|---|---|---|---|
| `earnings.sbc` | Mature Growth | the trailing stock pay, a total in the reporting currency, 0 or more | period-tied only in plan 1; from plan 2 also lasting at 0 (7.3) | stock pay |
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

### 7.3 A lasting nil (B-181)

The founder's ruling of 2026-11-14, built in plan 2. `stock-pay-missing` stays as built: on plan
1's readout it shows on 308 rows, and on the 242 with a nil trailing period the stored figure is
short, so the note is right there. A limit by the fiscal year's age would hide AZN, whose newest
year with stock pay on file is fiscal 2023 and whose filings show stock pay. What changes is the
repeat work for a company that pays no stock: `earnings.sbc` is period-tied, so its agent would
set a nil again each period.

**The rule.** `earnings.sbc` may be lasting when its value is 0, and only then: the company pays
no stock. A lasting figure other than 0 is refused, as now, with a sentence that names the
lasting form. A lasting 0 is also refused at the write where the snapshot's own trailing stock
pay reads above zero (*my call*): the store contradicts it, and the period-tied form is the one
for a period the vendor has wrong. A snapshot with no reading (a row refused before its route
wrote one) takes it.

**Its life.** A lasting 0 holds across periods. Before a recompute at a full or scoped refresh
or a revalue it drops, by the system, when the store's trailing stock pay is above zero: "the
store holds a trailing stock pay above zero". A trailing figure that is nil, or missing because
a period lacks the line, keeps it. The test reads the assembled trailing figure, not the
result's `sbc_ttm`, which a row refused before its route does not carry.

**What it does.** As any applied `earnings.sbc`: the anchor reads 0 for the stock pay, and
`stock-pay-missing` does not show. It is a rule in code, not a policy value.

The playbook's step for `stock-pay-missing` gains one sentence: where the filings show nil too,
the agent sets a lasting `earnings.sbc` of 0 with the filing as evidence.

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

## 8a. A reviewed row's flags (B-180)

The founder's ruling of 2026-11-14, built in plan 2. Plan 1 left a reviewed row's flags the
snapshot's, as every flag was before; its flags are the first that an input settles, so SYM
still counted `share-count-gap` after its `shares.diluted` reconciled the count (ratio 1.005 in
the review). It amends method 8 and 14.5.

**The rule.** Where a review fills the screen's Reviewed column (it counts on the latest
snapshot and has a value, method 14.5), the row's Flags column and its Warnings count read the
flags of the review's result, and with the count the Clean filter and the sort by warnings. The
drawer's flag list reads them too, under a line that says they are the review's. A review's
result is stored whole, so the read computes nothing and the store gains no column.

**What stays the snapshot's.** A row that a secondary valuation fills: it has no flags. A row
whose review refuses. The Clean filter's other condition, a value from the engine (*my call*: a
row the engine refused is not clean, whatever a review made of it). The inputs and intermediates
the drawer shows behind Details, and the Start-up section's `below-net-cash` test, which reads
the snapshot's own figures. The refresh's calibration counts.

**To the agent.** The `screen` tool's rows are the page's, so they follow. The `company` tool's
`review` record gains the review's flags, each with its code, word and sentence, so an agent
reads what its inputs settled without writing an override.

## 9. The thin-consensus note (B-175)

**`thin-ntm`**, "Thin NTM consensus", a note. On a Mature Growth row whose NTM window holds a
period with fewer than `analyst_min` (5) EPS analysts, or with no count. The sentence gives the
number of such periods, the smallest count and its period. It does not show in a review under an
applied `earnings.ntm`, whose anchor is the guidance. The window's quarters carry the count
already (`QuarterEstimate.analysts`).

## 9a. The NTM anchor on a thin window (B-175)

The founder's ruling of 2026-11-14, on plan 1's readout: the note of section 9 fires on 636 of
the 748 valued Mature Growth rows, so no threshold makes it a signal, and the anchor changes
instead. Built in plan 2, under method 1.4. It amends method 5.2 and 5.11.

The rule below is the second form. The first, built as plan 2's Task 8 (`7d80ba9`), read the
annual estimates of both fiscal years the window reaches, each by its share of the window's
periods. The scratch readout showed its fault: the estimate of the fiscal year that is partly
reported holds the quarters already reported, with their one-time items, and earnings inside a
year are not even (CPNG −94%, GOOG +16.7%, ALNY +61%, ASML −6.9%). The founder ruled on
2026-11-14, on that readout: repair it. The decision log holds both readouts.

**The rule.** The NTM window is found as now, and each of its periods still needs an EPS mean.
A period is thin when it has fewer than `analyst_min` (5) EPS analysts or no count, as section 9
reads it. Let F be the last fiscal year the window reaches. No period of F is reported: F starts
inside the window, or the window is F whole. Where a period of the window in F is thin and the
annual figure of F exists:

    NTM EPS raw = the sum of the window's EPS means
                + (annual EPS mean of F − the sum of the EPS means of F's periods)
                  × (the window's periods in F ÷ the periods in a year)

with four periods in a year on the quarterly cadence and two on the half-yearly one. The annual
consensus sets the level of F; the periods' consensus sets the split inside F. A window that is
F whole reads F's annual estimate. A calendar company whose last reported quarter is the third
keeps its fourth quarter's estimate as it is, and adds three quarters of the gap between next
year's annual estimate and next year's four quarters.

**The annual figure of F exists** when F has an annual consensus row with an EPS estimate (a
mean of zero with no analyst count, or a count of zero, is no estimate, as method 5.3 has it) on
`analyst_min` EPS analysts or more, and the periods' consensus holds every period of F, four or
two, each with an estimate by the same test. A period's fiscal year and an annual row's are the
labels the path already matches by (method 5.3). Where it does not exist, the sum of the periods
stands, as today.

**The fiscal year that is partly reported is never corrected.** The window's periods before F
keep their own estimates, thin or not, and that year's annual estimate is not read.

**What stays.** A window with no thin period in F keeps the sum of its periods. The stock-pay
adjustment and its scale by the window's revenue, the refusals, `earnings.ntm` and
`earnings.cycle_gap` read the raw figure so found, as now. The base year and the path are
untouched. The NTM revenue of the revenue-growth and Decline routes stays the sum of the
window's revenue means (*my call*: B-175 and the count on file are the EPS's).

**Where it reaches.** Every reading of the anchor of method 5.2: the Mature Growth value, the
growth-route cross-check of a Mature Stable or a revenue-growth row, and the forward EPS of the
revenue-growth route's multiples (*my call*: one rule wherever the anchor is read). Only the
first moves a value.

**The error it accepts.** The gap of F is spread evenly over F's periods. Where the annual
consensus and the periods' consensus of F agree, the rule changes nothing, whatever the seasons
or the growth inside the year. An offline test of this form on the scratch store of 2026-11-14
left 91% of the 450 rows within 5% of the periods' sum and 97% within 10%.

**The note.** `thin-ntm` fires where a thin period of the window is left as it is: a thin
period before F, or a thin period in F where the annual figure of F does not exist. Its sentence
keeps section 9's words, counts those periods, names the thinnest, and says why the annual
consensus does not correct it: its fiscal year is partly reported; or F has no annual EPS
estimate; or F's annual consensus has too few EPS analysts or no count; or not every period of
F has an estimate.

**What the result records.** The route's `anchor` intermediate gains `source` (`periods` or
`annual`), `periods_sum` (the sum of the window's EPS means, on either source) and `annual`:
on the annual source the fiscal year F, its annual EPS mean and analyst count, the sum of its
periods, the window's share of them and the correction a share; else nothing. The DATA entries
`ntm_eps` and `ntm_net_income` keep citing the periods' consensus and carry the correction as
their note when the source is `annual`.

**The founder decides on the readout.** The scratch run of section 17 lists what the rule moves
before the live step. The rule is commits of its own, so it can be left out of the merge.

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

Where a snapshot made before 1.3 does not carry its trailing period end as a figure of its own, the
builder reads it from the `as_of` of its diluted share count, which assembly dates at the newest
quarterly row's period end, the fiscal year's when that row holds no count (method 4.2), so such a
snapshot may read as an older period, and its correction then drops as "a newer period is on file";
the trailing inputs' own `as_of` is the fiscal year's end and is not read. From 1.3 on, a result
carries the period end.

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
10^15). Each source line names this spec and its section. Sections 7.3, 8a and 9a add no policy
value: the anchor rule reads `analyst_min`, which v13 holds, and the lasting nil is a rule in
code.

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
- For sections 7.3, 8a and 9a, in plan 2: `docs/method.md` 5.2 and 5.11 (the anchor's source and
  the note's new condition and sentence), 5.12, 5a.14 and 6.4 (the `anchor` entry and the cited
  estimates), 8 (whose flags a reviewed row shows), 14.2 to 14.6 (the lasting 0 and its drop)
  and 14.5 (the row and the drawer under a review); the Methodology page where it states the
  NTM anchor, the life of an override and what a reviewed row shows; the playbook's entries for
  `thin-ntm`, `stock-pay-missing` and `earnings.sbc`, its lifetimes, and its tools reference for
  `screen` and `company`.

## 16. Tests the builder must write

Each test fails before its change, and its expected figures are worked by hand.

Plan 1:
- Two stored answers of one company whose period ends differ by a day: assembly, `/estimates`
  and an `estimate:` ref read the newest answer's rows alone, whatever the analyst counts. An
  empty newest answer leaves the older rows read.
- `stock-pay-missing` on a zero trailing figure and on one zero quarter, each with a fiscal year
  above zero; silent on a history of zeros, and under an applied `earnings.sbc`.
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
  the `as_of` of that snapshot's diluted share count.

Plan 2:
- A company with a quarterly sheet newer than its annual one: each route of 12.2 reads the
  quarter's debt and cash; a tie reads the annual; no quarterly sheet reads the annual.
- The ROIC years, Z″ and F are unchanged by a quarterly sheet.
- The minority interest in each formula of section 13, hand-worked; nil at zero, below zero and
  when not presented; rebuilt at a price refresh.
- `balance.minority` applies, bridges and drops as the other balance corrections do.
- A period-tied `balance.cash` drops when a newer sheet changes the reading.
- A Mature Stable golden keeps its value, levels and refusal under 1.4, and so does a Mature
  Growth golden whose window is not thin or whose annual figure does not exist.
- The anchor (9a): a thin period in the last fiscal year the window reaches, with that year's
  annual estimate on 5 analysts or more and all its periods estimated, adds the window's share
  of the year's gap, hand-worked for a window in two fiscal years and in one, on quarters and on
  half-years; the annual estimate of the year partly reported is never read; a window with no
  thin period in that last year keeps its sum; a thin period before it, an annual estimate with
  fewer than 5 EPS analysts, with no count or absent, and a year whose periods are not all
  estimated each keep the sum and raise `thin-ntm` with its reason; the stock-pay adjustment and
  the refusals read the figure so found; `earnings.ntm` still stands in for it; a Mature Stable
  row's cross-check and a revenue-growth row's forward EPS follow, and neither row's value moves.
- The lasting nil (7.3): a lasting `earnings.sbc` of 0 applies; a lasting figure above 0 is
  refused; a lasting 0 is refused at the write on a snapshot whose trailing stock pay reads
  above zero; it stays applied when a newer period is on file; it drops with its sentence when
  the store's trailing figure is above zero, and stays on a nil and on a missing one.
- A reviewed row (8a): the row's flags and count are the review's; a row a secondary valuation
  fills and a row whose review refuses keep the snapshot's; the drawer's `review` record carries
  the flags; the Clean filter still needs a value from the engine.

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
  Stable row, and every Mature Growth row whose anchor stays on its periods, identical in value,
  levels and refusal; every other row's move listed, by cause.
- The anchor (9a), read by the founder before the live step, who decides with it whether the
  rule merges: the Mature Growth rows by the anchor's source; the rows where `thin-ntm` still
  fires, by reason; the moves of the value (the median, the share within 2% and within 5%, the
  ten largest each way named with the anchor before and after); AZN and RELX named; the rows
  that newly refuse or newly value; each review whose value moved. The first form was read out on
  2026-11-14 and repaired on the founder's word; the second form is read out the same way.
- A reviewed row (8a): SYM's row no longer counts `share-count-gap`; the count of rows whose
  flags now differ from their snapshot's.
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
three routes; `balance.minority`; the anchor on a thin window, as its own commits; the lasting
nil; a reviewed row's flags; the drawer, the Methodology page and the playbook; the scratch
runs, the founder's reading of the anchor's readout, and the live step.

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
| 2026-11-13 | A snapshot from before 1.3 gives its trailing period end by the `as_of` of its diluted share count, not of its trailing inputs, whose `as_of` is the fiscal year's end (found by the implementer of plan 1's Task 3; the trailing inputs would have dropped all ten corrections on file at the first revalue). Claude's ruling. |
| 2026-11-14 | Plan 1 built (`docs/superpowers/plans/2026-11-13-research-round-plan-1.md`), subagent-driven on 2026-11-13 and 2026-11-14: the computer crashed during Task 3's review on 13 Nov, and the build resumed from its ledger on 14 Nov. The commits `af156f9` to `6cba2e0` were fast-forwarded to main and pushed on 2026-11-14: method `fairband-mechanical/1.3`, policy `fairband-policy-v13`, 2,886 tests. By item: policy v13, method 1.3 and the runway range to 500% (B-178) `af156f9`; the consensus from one answer (B-172) `ee18abc`, `e8cd99c`, `86124c9`; the life of a period-tied correction (section 11a) `9c84425`; the two stock-pay notes (B-115, B-116) `70deebd`, on the refusal "no positive forward anchor" `8c5fba9`, silent under an applied `earnings.ntm` `ae3c560`; the two stock-pay inputs `earnings.sbc` and `earnings.sbc_basis` (B-115, B-116) `9b43c20`; the share-count warning (B-162) `09ea715`; the thin-consensus note (B-175) and the ten-year median margins (B-164) `1ada9a3`, the drawer's percentages `c865ef6`; the review's document corrections `38e2e8f`, `5046047`, `6cba2e0`. Tasks 1 to 7 each passed a task review; Task 8 changed no file (the drawer and the report page needed no change), and the whole-branch review covered it. The whole-branch review found two sentences of `docs/method.md` untrue and six small points; one fix round corrected the two and five of the six and was re-reviewed, the re-review's residual words went into `6cba2e0`, and the sixth point, one map written twice, is parked with the reviews' other minors in B-183. Claude. |
| 2026-11-14 | Settled by Claude during the build, each open to the founder, who was given the full list on 2026-11-14. The two stock-pay notes read the figures the anchor read: the stock pay in force (the agent's under `earnings.sbc`) and the GAAP EPS the basis test read (less the correction under `earnings.nri_gap`). The two notes also show on the refusal "no positive forward anchor", which a wrong charge can cause, and on no other refusal of the anchor or the path; they are silent under an applied `earnings.ntm`, as `thin-ntm` is. `sbc-basis-uncertain` prints its per-share figures with the currency. The stand-in for no upper bound of `earnings.sbc` stays 10^15 in the reporting currency, unscaled by the rate, as on `balance.cash`. The playbook holds an entry for each of the four new flags, with what the agent reads and the input that decides it. `margin_history` is on every result whose series is not empty, a refusal before any route too, where section 11 promised routed results. The DATA entries `ntm_eps` and `ntm_net_income` are the consensus less the stock-pay adjustment in force, so they follow `earnings.sbc`, `earnings.sbc_basis`, an `earnings.nri_gap` that changes the basis and `shares.diluted`; `docs/method.md` 14.4 says so. On a reviewed row the screen's Flags, Warnings and Clean and the drawer's flags stay the snapshot's, as for every flag before; the review's own flags reach the agent through the review; the founder's call, filed as B-180. The share-count sentence prints the ratio to two decimals, so a ratio between 0.695 and 0.7 reads "0.70, outside 0.70 to 1.30". The re-read of the Methodology page's examples was done on the scratch revalue, before the merge (`6cba2e0`). The live step went on though `thin-ntm`'s count was not near 310: no value differed from the expectation, and the count that was wrong was section 5's. Claude's calls. |
| 2026-11-14 | Readout of plan 1 (section 17): the steps and the live run. In order, on 2026-11-14: two copies of the live database made with SQLite's backup; one revalued with the branch's code (method 1.3), the other with main's code before the merge (method 1.2), as a control; the merge and the push; the backup `fairband-before-method-1.3-2026-11-14.db`; the live revalue, refresh 58, by the command line with the server down; the server started from main on 8470. The live refresh 58 is identical to the scratch run: every column and every stored result of the 1,598 rows, the 27 reviews it wrote, and the overrides' states. 1,598 companies, 1,386 valued. Claude, on the founder's word of 2026-11-14. |
| 2026-11-14 | Readout of plan 1: the values. Against the 1.2 control, 1,574 rows are identical in phase, route, value, levels and refusal, and 24 moved. Each of the 24 has a changed consensus input (`ntm_eps` and `ntm_net_income` on 19, `ntm_revenue` on 4, a path step on 6) and no row moved without one. AAP −52.7% ($18.66 to $8.83, Decline: under 1.2 its consensus read "no usable consensus" and years 1 to 3 shrank at the decline rate; under 1.3 the window is whole, NTM revenue $8.61 billion, steps +2.1% to +3.4%), CNR −13.6%, MTSI +13.1% (its period ends moved from 3 Oct to 2 Oct between answers), LITE +11.3%, FN +7.2%, AAPL +4.9% ($187.28 to $196.51), AMD +4.2% ($329.34 to $343.34), LDOS −3.9%, FBIN −2.5%, TXRH −2.3%, KTOS −1.9%, CALX −1.4%, MSI +1.0%, QCOM +0.9%, ON +0.8%, VVX +0.8%, HNI −0.5%, ITT +0.3%, PFGC −0.3%, MDLN −0.2%, SWK +0.1%, WTS +0.1%, KTB −0.0%. CAVA is newly valued ($5.11; under 1.2 "incomplete NTM consensus"). Here the result differs from this design: no row newly refuses, where section 6 expected some (a row whose newest answer lacks a period that an old row supplied). AAPL's NTM EPS is $9.2807, the sum of its newest answer's four quarters ($9.3197 before), as section 17 asked. Against the live snapshots of refresh 57 (a price refresh), 135 rows moved: the 24, and 111 rows of companies that report in another currency, on which only the exchange rate and the market cap changed. The cause is not method 1.3, and the 1.2 control moves the same 111: a revalue read the rate of 11 Nov 2026 where the price refresh 57 had read the pair's quote of 13 Nov 2026. ABEV: BRL 5.6422 at refresh 57, BRL 5.5626 at refreshes 56 and 58, the value $2.1065 at 57 and $2.1367 at 56 and 58; ASML: 0.9041 against 0.9016, $2,801.69 against $2,809.46. The moves are up to 1.6%. Filed as B-182. Claude. |
| 2026-11-14 | Readout of plan 1: the four flags against section 5. `share-count-gap`: 32 rows (18 valued, 14 refused); SYM 4.54, ANDG 8.48, EROK 4.10, EE 3.46, TKO 0.37; ROAD absent; as expected. `sbc-basis-uncertain`: 135 rows, all valued Mature Growth; the one-time-item reason on 50, the low-tax reason on 44, the gap reason on 60 (19 rows hold the first two together); as expected. `stock-pay-missing`: 308 rows (300 valued Mature Growth, 8 refused): 66 with a nil trailing figure (section 5 counted 64) and 242 with a nil trailing period; the trailing period's year less the newest fiscal year above zero is 0 on 26 rows, 1 on 164, 2 on 74, 3 or more on 44 (up to 11); how often it should fire is B-181. `thin-ntm`: 645 rows (636 of the 748 valued Mature Growth rows, 9 refused); the thinnest period has 1 analyst on 359 rows, 2 on 100, 3 on 140, 4 on 44, a count of 0 on 2; the window is thin in 1 of 4 periods on 45 rows, 2 of 4 on 239, 3 of 4 on 126, 4 of 4 on 227, 2 of 2 on 8. Here the result differs from this design: section 17 expected near 310. Section 5's counts, 310 with a quarter below 5 analysts and 164 below 3, were miscounted: an independent count from the stored quarterly estimates gives 636 and 452 of the 748 valued Mature Growth rows under the one-answer read, and 626 and 448 under the read before 1.3. The note is right by its rule; the anchor of five rows in six rests on a thin period. B-175 now holds the corrected counts. Claude. |
| 2026-11-14 | Readout of plan 1: the intermediates, the scratch checks and the overrides. `margin_history` is on all 1,433 routed rows (a net median on 1,404; empty on 29 with no year of revenue above zero) and on 163 rows refused before a route; ASML's ten-year net margin reads 26.0% and TTMI's 3.1%, as B-164 worked them. `trailing_end` is on all but 2 rows (no statements). On the scratch copy only: NVS under `earnings.sbc_basis` = `includes`: NTM EPS $9.5405 to $9.7957, the $0.2552 a share given back, the reviewed value $170.24 to $174.80, and `sbc-basis-uncertain` gone from the review. CLS under `excludes`: applied, the charge on at $0.9371 a share, the value unchanged at $272.54 with a bridge line of zero, since its `earnings.nri_gap` already made the test read `excludes`. AAPL's sensitivity holds 332.6% with a value in each cell; 5.01 is refused ("return.runway takes above 0% to 500%"). The overrides: the ten period-tied (SYM 22 and 23, CLS 36 to 38, FRVO 42 and 43, RKLB 54 to 56) are all still applied, with no drop for a newer period; the 43 lasting are all still applied; the revalue dropped none. Of the 27 reviews it wrote, 21 are unchanged; AMD's reviewed value moved +6.8% ($205.05 to $219.04) and QCOM's +0.9% ($240.69 to $242.94) by the consensus; ASML's, NVO's, RELX's and TSM's moved by 0.1% to 0.3% by the exchange rate. The Methodology page's six examples (Microsoft, Coca-Cola, CrowdStrike, Roku, 3M, Revolution Medicines) are identical under 1.3. Owed after the live step: every research session restarts its MCP process (or reconnects `fairband`) to read the new flags and inputs; a price refresh brings the 111 rows back to the newest rate. Claude. |
| 2026-11-14 | The price refresh the readout owed ran on the founder's word: refresh 59, the prices of 13 Nov 2026 and each pair's quote of 14 Nov 2026 on all 139 rows with a rate. 111 values moved against refresh 58, by −1.9% (SBSW) to +0.7% (PAC), and no row without a rate moved; four reviewed values moved with the rate (ASML, NVO, RELX, TSM, by 0.1% to 0.6%). B-182 stays open. Claude. |
| 2026-11-14 | B-175: the anchor changes, not the note. On a window with a thin period, year 1 reads the annual estimates weighted by the window's periods, where each has 5 EPS analysts or more; `thin-ntm` then fires only where year 1 still rests on thin evidence (section 9a). The founder, on Claude's recommendation, after plan 1's readout showed the note on 636 of 748 valued Mature Growth rows and the thinnest period at one analyst on 359. It joins plan 2 under method 1.4, as its own commits, and the founder reads the scratch readout of its moves before the live step. |
| 2026-11-14 | B-180: where a review fills a row, the screen's Flags, Warnings and Clean and the drawer's flags follow the review, as the levels do since 2026-11-08 (section 8a). The founder, on Claude's recommendation. This replaces the line of the build's rulings above that left them the snapshot's. |
| 2026-11-14 | B-181: `stock-pay-missing` stays as built, and `earnings.sbc` gains a lasting form at 0 for a company that pays no stock (section 7.3). The founder, on Claude's recommendation, which set aside a limit by the fiscal year's age because it would hide AZN. |
| 2026-11-14 | Settled by Claude while writing sections 7.3, 8a and 9a, each open to the founder. The annual figure stands in only where every year it reads has `analyst_min` EPS analysts or more, so the rule never trades a thin quarter for a thin year. The weights are the window's periods in each fiscal year over the periods in a year, by the fiscal-year labels the path matches by. The rule reaches every reading of the anchor (the Mature Growth value, the growth-route cross-check, the revenue-growth route's forward EPS) and not the NTM revenue of the revenue-growth and Decline routes. The stock-pay scale keeps the window's revenue. A lasting 0 is refused at the write where the snapshot's stock pay reads above zero, and drops when the store's trailing figure is above zero. The Clean filter keeps its condition of a value from the engine. A row that a secondary valuation fills keeps the snapshot's flags. |
| 2026-11-14 | Plan 2 written (`docs/superpowers/plans/2026-11-14-research-round-plan-2.md`, twelve tasks) on a map of the code as it stands. Settled by Claude where sections 12 and 13 met the code, each open to the founder. The quarterly sheet stays out of the data date and of the `statements` input's stamps (method 4.10), so no mature row's stored result moves with it; the newest sheet is cited under a key of its own, `balance_sheet`, whose `as_of` is the sheet's period end. The period goes on the entries' notes and never into the notes that raise `line-not-presented`. Each quarterly sheet in another currency is skipped and the newest of the rest stands against the annual one. The vendor's zero for goodwill and intangibles reads as not presented on a quarterly sheet, as on an annual one. The floor's two entries are `floor_current_assets` and `floor_total_liabilities`, and `line-not-presented:totalLiabilities` follows the floor's sheet. The Decline `equity` entry subtracts the minority interest, `distress_proceeds` stays the fraction of the firm value plus cash, and `ncav_per_share` is the floor a share, less the minority interest. The DATA entry `minority_interest` holds the line as presented and the intermediate the figure in force. The four glossary rows of method 13 and of the report change with section 13. The secondary valuation's default debt and cash follow the newest sheet, and it gains no minority term (section 3). The drawer shows the minority interest's row only above zero. The vendor check of 12.3 adds DXC, for the minority interest's line: ten calls. A balance correction drops at the first refresh under 1.4 as "a newer period is on file" where the company's trailing period moved, since that test comes first (section 11a); a correction whose own period is newer than the sheet the engine now reads drops for a changed reading too, and the readout lists each for its agent to make again. The scratch run widens the reuse window on the scratch store only, so it fetches the one new dataset, and compares two revalues on the same stored answers, one under 1.3 and one under 1.4, so the exchange rate of B-182 is the same in both. |
| 2026-11-14 | Plan 2's Tasks 1 to 11 built on the founder's "go", subagent-driven, on the branch `research-round-plan-2`: `7ea6990` policy v14 and method 1.4; `33cce4b` the quarterly balance sheet and `minorityInterest` in the store; `07b5361`, `9d1f63c` the newest sheet in assembly; `4b0fe37` the routes cite it and the Decline floor reads it; `83a9277` the minority interest in the three routes; `a5a4449` `balance.minority`; `7d80ba9` the anchor rule's first form; `a4775e7` the lasting nil; `4f2ec37` a reviewed row's flags; `5281b91` the drawer; `eeab62f` the whole-branch review's one fix (the floor's words named no minority interest). Each task passed a task review; the whole-branch review was clean after that fix. The vendor check of 12.3 (twelve calls): FMP's quarterly sheet exists for FRVO, RKLB, RELX, ABVX and DXC and ends after the annual one; a half-year reporter's answer holds half-years labelled Q2 and Q4; a line with no figure reads 0, not null; ABVX's newest half-year reads its two debt lines as nil. Claude. |
| 2026-11-14 | The scratch readout of the anchor rule's first form (a backup copy of the live store; a full refresh on it that fetched 1,598 `balance-quarter` answers and reused the rest; then a revalue under 1.4 against a control revalue under 1.3 on a second copy). 450 of 796 Mature Growth rows read the annual figure, and HIMS was refused through it. Of 448 valued on both sides the median move was +0.7%, 80% within 5%, 35 rows beyond 10% and 12 beyond 25%. The fault: the estimate of the fiscal year partly reported holds the reported quarters with their one-time items, and earnings inside a year are not even. CPNG −94% (its 2026 estimate is −0.73 on a reported loss; its next quarter alone is +0.03), ALNY +61% (2026 at 18.42, 2027 at 8.96), GOOG +16.7% (2026 at 19.69, 2027 at 15.03, the four quarters ahead 13.88), ASML −6.9% and CLS +7.6% (fast growth inside the year). It also corrected real errors (CCEP's one-analyst half-years, BA's sum of 0.001). Every Mature Stable row and every Mature Growth row on its periods was identical. Claude. |
| 2026-11-14 | B-175, the anchor rule repaired (section 9a, the second form): the periods' sum plus the window's share of the gap between the annual estimate and the periods' estimates of the last fiscal year the window reaches; the fiscal year partly reported is never corrected and its annual estimate never read. The founder ("fix it"), on the first form's readout and on Claude's offline test of three other forms on the scratch store: this year's estimate less the street's reported EPS was worse (61% of rows within 5% of the periods' sum, since the vendor's annual estimate and the reported EPS are often on two bases); next year's estimate by an even split left 67% within 5%; this form left 91% within 5% and 97% within 10%, with GOOG at +0.9%, ASML at −2.1%, CLS at +1.3% and CPNG at −31%. Settled by Claude with it, each open to the founder: the rule needs every period of that fiscal year estimated, so a year with a period of 0 on 0 analysts (EDU) keeps its sum and its note; `thin-ntm` fires on a thin period of the year partly reported, which nothing corrects; the two DATA entries keep citing the periods' consensus and carry the correction as their note. |

Builder check: done 2026-11-13, one round (Opus 5.5, xhigh). It found two statements about the
method that were wrong (the drop rule of 12.4; a refusal for an override that moves nothing,
which no rule gives) and one acceptance line that clashed with method 14.6; all three are
corrected above. Of its five questions, one was the founder's (section 11a) and four were
settled as *my call*. Its findings in the code are stated where they apply: sections 6, 7.1, 11,
12.1, 12.2, 14 and 15.
