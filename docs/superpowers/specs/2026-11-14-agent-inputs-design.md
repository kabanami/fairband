# The inputs an agent could not set: committed shares, a one-time item in the NTM consensus, the revenue steps, overrides at a split, overrides on another route and guidance in net income: design

Status: written 2026-11-14. This is theme 4 of the research agents' issues (the founder's review
of 2026-11-13): corrections an agent wanted to make on a Mature Growth row and could not, with
two rules about what happens to an override when the row under it changes. The founder ruled on
each item on 2026-11-14 ("all as recommended"), on Claude's recommendations. Items marked *my
call* were settled by Claude while writing, on a map of the code as it stands, and can be
overturned as the others can. Not built.

This document amends `docs/method.md` (the method as built) in sections 4.1, 4.2, 4.8, 5.2, 5.3,
5.11 to 5.13, 6.1, 6.4, 8, 11, 14.2 to 14.6 and 14.9, the Methodology page and the playbook with
them. Every earlier spec stands for what it does not mention.

## 1. What this is

Six changes in one plan.

1. **Committed shares** (B-146). A new input, `shares.committed`: shares the company has
   committed to issue that neither its diluted count nor the analysts' EPS holds yet. The value
   a share is divided among them too. On Mature Growth the earnings stay on the count the
   consensus is on.
2. **A one-time item in the NTM consensus** (B-145). A new input, `earnings.ntm_nri`: an amount
   a share that the consensus carries and that does not recur. It comes off year 1.
3. **The revenue steps** (B-148). Two new inputs, `revenue.step_2` and `revenue.step_3`, for
   the consensus revenue growth the charge pays for. And one rule: a consensus revenue step on
   fewer than 5 revenue analysts is not read. The rule is measured before it is kept.
4. **Overrides at a split** (B-151). An applied override in dollars a share, or in shares, is
   scaled by the ratio of a split that took effect after it was made, and the row says so.
5. **An override the route no longer reads** (B-98). At a recompute the system drops it, with
   the reason.
6. **Guidance in net income** (B-179). A guidance record may hold net income, and an NTM EPS
   may rest on it.

B-150, META's acceptance after its split of late January 2027, has nothing to build before then.

## 2. Goals

- An agent can state dilution, a one-time item and a revenue step on a Mature Growth row, each
  with evidence, and each moves the value as the statement means.
- An override keeps its meaning when the row under it changes: at a split it is on the new
  basis, and on another route it does not stay applied in name only.
- Each mechanical change is read out on the live data before it is kept.

## 3. Non-goals and anti-goals

- No change to `shares.diluted`. It stays the count itself, for a share class or units that the
  vendor's count leaves out, with today's arithmetic on every route (section 4 says why).
- No server check that an `earnings.ntm` equals its guidance record's figure. The playbook and
  the report's number check carry that, as now.
- No new flag on the screen for a thin revenue step. The drawer says which growth the charge
  paid for.
- Anti-goal: an input that moves a value another input already moved. Sections 4 and 5 say on
  which count each figure a share stands.
- Anti-goal: a mechanical rule kept without its readout. Section 6.2 is commits of its own.

## 4. Committed shares (B-146)

**The problem.** On Mature Growth, year 1 is the consensus EPS times the count, and the value a
share divides by the same count. So a higher `shares.diluted` moves the value only through the
stock pay a share. AMD gave two customers warrants for up to 320 million shares at $0.01, 16.2%
of the enlarged count, and no input brings that dilution into its value.

**Why not the count itself.** `shares.diluted` also serves a company whose vendor count leaves
out a share class or units (an Up-C: SYM, HESM). There the consensus EPS is a Class A share's,
and today's arithmetic is right: the earnings scale with the count, and the value a share
stands. One number cannot serve both cases. So dilution gets its own input (*my call*; the
founder's ruling was the behaviour, on the AMD case).

**The input.**

| Tag | Routes | Takes | Lifetime | Bridge label |
|---|---|---|---|---|
| `shares.committed` | Mature Growth, Mature Stable, revenue-growth, Decline, Start-up | a count of shares, above 0 | period-tied only | committed shares |

**The rule.** The count in force is the diluted count, an agent's `shares.diluted` in its place,
plus the committed shares. Every division of a value among the owners uses it, as now. Two
counts differ only where a figure a share from the vendor or the consensus becomes a total:

- Mature Growth (5.2): NTM net income = NTM EPS × the count without the committed shares; the
  stock pay a share, in the basis test and the adjustment, is over that count too. The value a
  share divides by the count in force. So committed shares of x on a count of n lower the value
  a share by x ÷ (n + x).
- The growth-route cross-check (6.4) follows, on every row that carries one.
- Mature Stable (6.1): the two gaps a share become totals on the count without the committed
  shares. Its earnings are a total already, so the value a share falls as on Mature Growth.
- Revenue-growth, Decline, Start-up: the committed shares add to the count that divides equity
  and the floors. Nothing else changes.

On a row with no reported count and no `shares.diluted`, the route refuses as now.

**Proceeds.** The input is a count. Cash that the issue brings is the agent's to add, through
`balance.cash` or `value.outside`, with its evidence.

**What the result records.** The intermediates keep `shares`, the count in force, and gain
`shares_committed` under the override. The engine's reading of `shares.diluted` is `shares` less
it; the reading of `shares.committed` is nil.

**The playbook.** Shares not yet issued go through `shares.committed`, on every route; a class
or units the count leaves out go through `shares.diluted`. The sentences that say a raised count
barely moves a Mature Growth value change.

## 5. A one-time item in the NTM consensus (B-145)

**The problem.** Where the consensus EPS carries gains on an asset outside the business (AMZN's
Anthropic stake), adding the asset through `value.outside` counts it twice, and no input takes
the gains out of year 1. The playbook tells the agent to leave the asset out.

**The input.**

| Tag | Routes | Takes | Lifetime | Bridge label |
|---|---|---|---|---|
| `earnings.ntm_nri` | Mature Growth | an amount a share in the reporting currency, −100 to 100 | period-tied only | one-time item in the NTM consensus |

**The rule.** NTM EPS = the consensus less the stock-pay adjustment, less the one-time amount,
less a cycle gap. A negative amount, a one-time loss, raises year 1. It is a share of the count
the consensus is on (section 4). "No positive forward anchor" reads the figure so lowered; the
unit-error check and the two DATA entries stay on the consensus as found, as under a cycle gap.
The route's own anchor reads it; a cross-check does not.

Under an applied `earnings.ntm` the guided EPS stands in for the consensus with its items, so
the one-time amount applies with a bridge line of zero (*my call*, as method 14.4 has the two
stock-pay inputs).

The engine's reading of the input is nil, so it drops when a newer period is on file. The
reading of `earnings.ntm` does not add it back: a guided EPS stands in for the consensus with its
items, so the EPS that gives the same result already has the amount off.

**The playbook.** "Nothing counts twice" on Mature Growth becomes: read the filing's
other-income line against the analysts' basis; where the consensus carries the asset's gains,
set `earnings.ntm_nri` to them, a share and after tax, then add the asset through
`value.outside`.

## 6. The revenue steps (B-148)

The charge pays for the consensus revenue growth of years 2 and 3 (method 4.8, 5.3). On Mature
Growth the revenue steps are read with no test of their analysts, and `path.step_2` and
`path.step_3` move the earnings steps alone.

**Evidence** (a copy of refresh 61, 2026-11-14). Of 744 valued Mature Growth rows with a charge,
309 have a revenue step whose landing year has fewer than 5 revenue analysts: one analyst on
82, two on 75, three on 55, four on 97. On 155 that step is more than 10 points from the
earnings step of its year, and on 13 it is above 30% (ACM +90.7% on one analyst, a value of $14;
FRO +61.0% on two; HESM +69.6% on two; BIPC +310.5% on one, refused).

### 6.1 Two inputs

| Tag | Routes | Takes | Lifetime | Bridge label |
|---|---|---|---|---|
| `revenue.step_2`, `revenue.step_3` | Mature Growth | a growth rate, −80% to 300% | period-tied only | revenue step 2, revenue step 3 |

Each replaces the consensus revenue step of its year in the charge. An agent's step is never
thin: it wins over the rule of 6.2. The engine's reading is the consensus revenue step as
found, so the override drops when that step moves or a newer period is on file. They are
period-tied only (*my call*): a lasting step would name another year when the base year rolls,
as a lasting `path.step` does today.

On the revenue-growth and Decline routes the path is the revenue series, and `path.step_2` and
`path.step_3` already are the revenue steps. So the two inputs are Mature Growth's alone. A
cross-check reads the consensus as found and takes no agent's step.

### 6.2 A thin revenue step is not read

A consensus revenue step whose landing year has fewer than `analyst_min` (5) revenue analysts,
or no count, is not read. The charge then takes the earnings step of that year, as resolved, as
it does today for a missing revenue step (method 4.8). The Decline route already leaves out a
consensus year on too few revenue analysts (method 6a.2).

The rule reaches the Mature Growth value and every growth-route cross-check. It is method 1.5,
commits of its own, and the founder reads its scratch readout before the live step and decides
whether it merges.

No flag (*my call*): on about 300 rows it would be noise. The drawer says, for each of years 2
and 3, which growth the charge paid for and why.

### 6.3 What the result records

The intermediates' `charge` entry keeps `revenue_steps`, the steps the charge read, which the
price refresh rebuilds from: an agent's step, the consensus's, or none. It gains
`revenue_steps_found`, the consensus's steps as found, and `revenue_step_source`, for each year
one of `consensus`, `agent`, `thin` or `none`. `growth-above-return` says "revenue growth" where
the year's growth is a revenue step, the consensus's or an agent's.

## 7. Overrides at a split (B-151)

**The problem.** A review's lasting override in dollars a share (`earnings.ntm`,
`earnings.cycle_gap`, `earnings.nri_gap`, `value.outside`) is re-applied unchanged after a
split, on figures the split rule scaled. A lasting `earnings.ntm` doubles META's reviewed value
on a 2-for-1, with nothing naming it. META splits in late January 2027.

**The rule.** When the overrides of a row become the engine's, an override whose unit is dollars
a share is divided by ρ, and one whose unit is shares is multiplied by ρ. ρ is the product of
the ratios of the splits that the figures of the snapshot being reviewed saw and the figures of
the snapshot the override was made on did not. A snapshot's figures saw a split dated at or
before its basis date. The basis date is the earlier of the price date and the data date of the
snapshot that assembled the figures: the snapshot itself, or, for a snapshot a price refresh
made, the latest earlier snapshot of the company that a full or scoped refresh or a revalue
made. The split rule applies a split only from the price date on (method 4.2), and the data date
is the day the figures were fetched (method 4.10); a price refresh fetches no splits and
re-assembles nothing. The stored override keeps the figure the agent entered.

It is done where the store's overrides become the engine's, once, for the refresh's follow, the
web's recompute and a sensitivity reading. The engine knows no split.

**The row says so.** The override's JUDGMENT entry gives the figure in force, and its note adds
the figure as entered and the split: "entered as $30.00 a share before the 2-for-1 split of 27
Jan 2027". The review's result carries the note `override-split-scaled`, "Override scaled at a
split", naming each such input. The bridge line's new value is the figure in force.

**What stays.** A period-tied override whose reading the split rule itself rescales
(`earnings.nri_gap`, `earnings.ntm`, `shares.diluted`) still drops as "the input the override
corrected changed", as today (*my call*: its period ends soon after, and a second scaling in
the drop test buys little). So the rule serves the lasting overrides and those with no engine
reading. The playbook's instruction to drop and re-make per-share overrides after a split goes.

## 8. An override the route no longer reads (B-98)

**The problem.** The route of a row is checked when an override is written and never again.
After a `phase` override is dropped or replaced, or the classifier moves the phase, an override
only the old route read stays applied with a bridge line of zero. Its JUDGMENT entry even stands
in place of the entry the route did read: a stale `moat.class` on a Decline row hides the moat
the route used.

**The rule.** At a recompute, an applied override whose tag the row's route does not read is
dropped by the system: "the <route> route does not read the input". The row's route is the
route of its applied `phase` override, else of its mechanical phase. It runs:

- at a full or scoped refresh and a revalue, after the `phase` override's own drop tests and
  before the other overrides' tests, so the reason given is the true one;
- in the web's recompute, after an override is posted, replaced or dropped; a first `phase` override moves the route as a replacing one does. The answer names
  the overrides the system dropped with it.

An unclassified row has no route. Its overrides stay (*my call*): a row unclassified for one
refresh must not lose its review's inputs.

## 9. Guidance in net income (B-179)

**The problem.** A guidance record holds revenue, EPS, the operating margin, free cash flow,
capital spending and two growth rates. A company that guides net income alone (ROAD) cannot
back an NTM anchor.

**The rule.** `net_income` joins the metrics, a total in the reporting currency, with a step
against the prior year's net income as revenue and EPS have. An `earnings.ntm` may cite a
`gaap` fiscal-year record of `eps` or of `net_income`. The guided-year drop reads either.

`earnings.ntm` stays an EPS. The agent derives it: the record's midpoint over the count the
consensus is on (section 4), cited with the `derive` tool, so the report's number check sees the
division (*my call*: the founder's ruling was that such guidance can back the anchor; the
division is the agent's cited step, as every figure of a report is).

## 10. Policy v16 and the versions

Policy v16 adds four pairs to `override_ranges`: `shares.committed` (above 0 to 10^12 shares,
the lower end excluded as `shares.diluted`'s is), `earnings.ntm_nri` (−100 to 100),
`revenue.step_2` and `revenue.step_3` (−0.80 to 3.00). No other value.

The method version stays 1.4 for sections 4, 5, 6.1, 7, 8 and 9: no mechanical figure moves
(method 11 has such rows, "0.9, policy v9"). Section 6.2 is method 1.5. If the founder leaves it
out, the method stays 1.4.

The inputs an agent may override become twenty-five. No database migration is needed.

## 11. The documents

- `docs/method.md`: 4.1 (v16), 5.2 and 5.12 (the two counts, the one-time amount), 4.8 and 5.3
  (the revenue steps, the thin rule), 5.11 (the flag's words), 5.13 (the worked `shares.diluted`
  line), 6.1 and 6.4, 8 (the note `override-split-scaled`), 11 (the rows), 14.2 to 14.6 (the
  four inputs, the count "twenty-five", the split scaling, the route drop) and 14.9 (the
  metric).
- The Methodology page: the count of inputs, and what an agent may change, in its register; its
  six examples re-read if method 1.5 merges.
- The drawer: the charge's lines for years 2 and 3; the committed shares beside the count.
- The playbook: the overrides table and the four inputs' entries, "Nothing counts twice", the
  share-count passage, the split passage, the guidance metric, and the tools reference.
- `docs/backlog.md`: the rows closed, and what a review parks.

## 12. Tests the builder must write

Each test fails before its change, and its expected figures are worked by hand.

- `shares.committed`: on Mature Growth, x committed shares on a count of n lower the value a
  share by exactly x ÷ (n + x), and the NTM net income and the stock-pay adjustment do not move;
  on Mature Stable the value falls by the same share; on the three firm-value routes it equals
  a `shares.diluted` raised by x; with `shares.diluted` also applied both hold; the bridge's
  deltas sum; a price refresh rebuilds the same figures; the reading of `shares.diluted` is the
  count without it.
- `earnings.ntm_nri`: year 1 falls by the amount, and rises for a negative one; under an
  applied `earnings.ntm` the bridge line is zero; with a cycle gap both come off; the reading
  of `earnings.ntm` does not add it back, and a sensitivity grid on `earnings.ntm` marks the
  cell in force; it drops when a newer period is on file; a cross-check does not read it.
- `revenue.step_2` and `revenue.step_3`: the charge pays for the agent's step; the reading is
  the consensus's step as found; it drops when that step moves; `charge` records the three
  entries; a price refresh rebuilds the same value.
- The thin rule: a revenue step on 4 revenue analysts, or with no count, is not read and the
  charge takes the earnings step, an overridden earnings step too; on 5 it is read; an agent's
  revenue step wins over the rule; a Mature Stable row's cross-check follows.
- Overrides at a split: a lasting `value.outside` made before a 2-for-1 is applied at half and
  a `shares.committed` at double; an override made after the split is not scaled; two splits
  multiply; an override made on a snapshot of the split's day whose price date is the day before
  is scaled on the next; the JUDGMENT note, the bridge's new value and the note on the review;
  the same figures through the web's recompute and a sensitivity reading.
- The route drop: a lasting `return.runway` on a row whose phase moves from Mature Growth to Decline drops with the
  route's reason; after a `phase` override is dropped in the web, the overrides only its route
  read drop in the same answer; an unclassified row keeps its overrides; a period-tied override
  on another route drops with the route's reason, not "the input changed".
- Guidance: a `net_income` record is stored, stepped and referenced; an `earnings.ntm` citing
  one is accepted; one citing a `revenue` record is refused as now; the guided year drops it.

## 13. Acceptance and the readout

The merge needs no vendor call: one revalue applies it. First a scratch revalue on a copy,
twice: once without the commits of 6.2 and once with them.

- Without 6.2: every row identical to the live refresh in value, levels and refusal, and every
  review identical, since no input of sections 4 to 9 is on file yet.
- With 6.2, for the founder's reading: the Mature Growth rows whose revenue step is not read,
  by the analysts' count; the moves of the value (the median, the share within 5% and within
  10%, the ten largest each way); ACM, FRO, HESM and BIPC named; the rows that newly value or
  newly refuse; the cross-checks that moved; each review whose value moved.
- Then the live step: the backup, the server from main, one revalue, the two compared.

## 14. Left to the builder

- The name of the count without the committed shares on the route's context, and where
  Mature Stable takes it.
- How the split helper reads the splits and the two data dates, and the note's exact words.
- Where the route drop sits among the drop tests, and the shape of the web answer's list.
- The drawer's words.
- The split of the plan into tasks.

## 15. Order of work

Policy v16; committed shares; the one-time item; the two revenue inputs; overrides at a split;
the route drop; guidance in net income; the thin rule with method 1.5, as its own commits; the
drawer and the whole-branch review; the scratch revalues, the founder's reading, the live step.

## Decision log

| Date | Decision |
|---|---|
| 2026-11-14 | The founder ruled on the six items of theme 4, each on Claude's recommendation ("all as recommended"): a higher share count dilutes a Mature Growth value; an input takes a one-time amount a share off the next twelve months' earnings; two inputs for the revenue growth of years 2 and 3, and a rule that a revenue forecast from fewer than 5 analysts gives way to the earnings growth, measured on a copy before it is kept; a correction in dollars a share is scaled at a split and the row says so; a correction the row's route no longer reads is dropped with its reason; a guidance record may hold net income. |
| 2026-11-14 | Settled by Claude while writing, on a map of the code, each marked *my call* above or stated here. Dilution is a new input, `shares.committed`, and `shares.diluted` keeps its arithmetic, because the count also corrects a share class or units, where the founder's rule would cut a right value (an Up-C on Mature Growth: HESM). The committed shares are period-tied only, as the diluted count is. The one-time item is Mature Growth's alone, period-tied only, moot under an applied `earnings.ntm`. The two revenue inputs are Mature Growth's alone and period-tied only. A missing revenue analyst count is thin. A thin revenue step raises no flag. The split's scaling reads the two snapshots' data dates and covers counts as well as dollars a share; a period-tied override whose reading the split rescales still drops. An unclassified row keeps its overrides. The agent derives an EPS from guided net income; the server does not divide. The method stays 1.4 but for the thin rule. |
| 2026-11-14 | Changed at the build, on the review of Task 3: the reading of `earnings.ntm` does not add the one-time amount back. Under a guided EPS the amount is moot, so the add-back made a sensitivity grid mark the mechanical value as the pair in force. |
| 2026-11-14 | Changed at the build, on Task 5's report: the scaling reads a basis date, the earlier of the price date and the data date of the snapshot that assembled the figures, in place of the data date alone. A refresh on a split's day before the US close has the split's day as its data date and the day before as its price date, so its figures did not see the split, and under the data date alone an override made on it was never scaled. Two residuals stay: a failed fetch of the splits beside a good fetch of the statements, and a refusal snapshot from a failed fetch. |
| 2026-11-14 | Changed at the build, on Task 6's report: the test example of the route drop is a move from Mature Growth to Decline, since the Start-up route reads `moat.class`; and a first `phase` override is named beside a replaced or dropped one. |
