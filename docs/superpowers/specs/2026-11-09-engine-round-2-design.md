# The engine round 2: the reinvestment charge without its floor and on revenue growth, the fading runway return, the consensus-basis flag, the value outside the business and the share-count override, the step-series check, and stock splits: design

Status: written 2026-11-09 from the brainstorm of that day. The founder asked what the literature
says on B-129 and B-130, saw five variants probed on the five companies the agents have reported
(GOOG, QCOM, AMZN, META, RELY), chose the version closest to Damodaran's text over one that read the
agents' judgment into the mechanical row, and asked for the spec on it. The decisions in the log at
the end are the founder's. Items marked *my call* were settled by Claude while writing and can be
overturned. Builder check: see the status line at the end of the log.

This document amends `docs/method.md` (the method as built) in sections 2, 4.1, 4.1a, 4.2, 4.6,
4.8, 5.3, 5.6, 5.7, 5.8, 5.11, 5.12, 6.3, 6.5, 8, 10, 11, 14.2, 14.3, 14.4 and 14.5, and the
Methodology page with them. The mechanical screen spec, the calibration spec, the growth routes
spec, the 2026-11-03 spec, the 2026-11-06 engine round spec and the Tier 2 spec stand for
everything it does not mention. When the pieces are built, their sections go into `docs/method.md`
in the same commits, and that document stays the statement of what runs.

## 1. What this is

Six changes, built as one piece under method `fairband-mechanical/1.0` and policy
`fairband-policy-v10`, applied by one revalue. The charge changes move every Mature Growth and
Mature Stable value, which is why the method version steps to 1.0 (*my call*: the first change
since 0.2 that moves every mature row). No vendor call is needed for five of the six; the sixth adds
one dataset per company, the splits, which the next full or scoped refresh fetches.

1. **The charge without its floor** (B-129). A runway year whose growth outruns its return pays
   nothing today: the floor at zero treats the growth above the return as free. The floor goes.
   Such a year pays a negative cash flow, the owner's money going in.
2. **The charge on revenue growth** (B-129, the shape). The charge pays for the next year's
   revenue growth, not its earnings growth. Earnings growth above revenue growth is margin change
   on the capital already in place and needs no new capital; earnings growth below it still pays
   for the revenue. In the belief years the two are one rate, so nothing moves there.
3. **The runway return held, then faded** (B-130). The return the charge uses holds through the
   years that pay for growth above the belief (the consensus steps and the growth fade), then fades
   in a straight line to the terminal return in year N, instead of holding for N − 1 years. The
   `heavy-capex` sentence names the newest year's marginal return and the `return.runway` override
   as the remedy for a capital-spending surge the stored years cannot see.
4. **The consensus-basis flag** (B-133). FMP's consensus EPS names no basis. When `large-nri`
   fires, a note says that whether the consensus carries the non-recurring items is unknown.
5. **The value outside the business and the share count** (B-139). Two inputs an agent may set
   with evidence: a figure a share outside the business, positive or negative, nil by default,
   added to the route's value a share as its own bridge line; and the diluted share count, for
   shares not yet in the reported count, period-tied as the balance corrections are.
6. **The step-series check** (B-140) and **stock splits** (B-143). A note when a consensus step
   read on net income and the same step on EPS differ by more than five points, naming both rates.
   Splits are fetched from FMP; a figure whose source predates a split is read on the quote date's
   share basis, and the row says what was scaled.

## 2. Goals

- A Mature Growth row whose consensus growth outruns its return is charged for the outside money
  the growth needs. AMZN's mechanical row moves from 288.84 to about 299 and its reviewed value
  from 254.01 to about 259 at a price of 259.30 (section 5): the floor's waiver and the revenue
  charge roughly offset there, since its earnings growth of 22% and 34% sits on revenue growth of
  17% and 15%.
- The return the charge uses fades as the literature says returns do. The five agents' reviewed
  values stay within 5% of what they judged by hand: GOOG 339.71 → about 339, QCOM 210.72 → 199,
  META 681.91 → 650, RELY 23.67 → 24.04.
- The agent sees the capital-spending lag and has a named remedy: the `heavy-capex` sentence
  carries the newest year's marginal return beside the five-year measure and names the override.
- A report can carry an asset or a liability outside the business, and shares not yet in the
  count, as the agent's judgment with evidence, on the bridge where every other judgment sits.
- A split between the newest statement and the quote no longer halves a row's price ÷ value.
- At the defaults, every row on the revenue-growth, Decline and Start-up routes keeps its value,
  levels, designation, flags and refusal bit for bit, except for `split-pending` (section 10), a
  note that changes no figure until a split is on file. The charge changes reach every Mature Growth and Mature Stable row,
  and the readout names the distribution of the moves, not each row.

## 3. Non-goals

- No one-year marginal return as the charge's start. It was probed (section 5, variant H) and
  reproduced both agents' overrides, but Damodaran prefers multi-year figures to one-year ones, and
  the founder chose fidelity. The newest year's figure is shown, not used.
- No change to `wide_terminal_roic_spread`. A 6-point spread was probed and lifts every Wide row 2%
  to 3%; the value is a user setting already, so the founder moves it from the Settings view when
  he wants, with no method change.
- No fade toward a sector-average return. The fade's end is the terminal return of 4.7. The peer
  figures carry a ROIC to build a sector target from later if the unreviewed heavy-capex rows bite.
- No override of the revenue steps the charge reads. `path.step_2` and `path.step_3` move the
  earnings path only; `return.runway` is the agent's lever on the charge.
- No per-company consensus-basis record (B-133's second option). A guidance record holds figures a
  company gave; the basis is a judgment the agent makes through `earnings.nri_gap` and
  `earnings.ntm`, and the flag points at it.
- No change to the universe rule on share classes: a company with two listed classes keeps a row
  for each, as FOX and FOXA do today, and META's new class will get its own row when FMP lists it
  (*my call*; design.md 67's "value each company once" stays proposed, not built).
- No change to the secondary valuation, the growth routes' charge (sales-to-capital), the Decline
  route or the Start-up route.
- Foreign filers (B-28) are the plan after this one.

## 4. Anti-goals

- Growth charged twice. The charge reads one growth rate a year, the revenue growth; the margin
  change rides free. Nothing charges the earnings growth as well.
- An asset outside the business counted twice. The route's earnings carry the asset's gains when
  GAAP does (AMZN's mark-ups through other income). The agent who adds the asset strips its gains
  through `earnings.nri_gap`, and the playbook says so beside the new input; the engine cannot know
  which gains belong to which asset.
- A split scaled twice. A figure is scaled only when its source predates the split and the vendor
  has not restated it; the builder establishes the vendor's behaviour live before writing the rule
  (section 10).
- Any loss of a stored figure. Every change is a method version bump; the snapshots valued under
  0.9 stay as they are, and the revalue writes new ones.

## 5. The evidence (the live database, read-only, 2026-11-09)

A probe reran the engine on the five companies' stored inputs and reproduced every stored
mechanical and reviewed value exactly before any change. "Reviewed" applies each company's applied
overrides (GOOG and META a `return.runway` of 21.4% and 21.0%, the newest year's marginal, which
both agents computed by hand; AMZN two step overrides; QCOM a non-recurring gap and a step; RELY a
step). The variants, each with the floor off:

| Ticker | Price | Reviewed, as built | Linear fade from year 1, earnings charged, one-year start (D) | Hold then fade, revenue charged, 6-pt spread, one-year start (H) | **Hold then fade, revenue charged, the five-year start and the 4-pt spread as built (this spec)** |
|---|---|---|---|---|---|
| GOOG | 287.30 | 339.71 | 320.31 | 349.40 | **339.28** |
| QCOM | 173.19 | 210.72 | 196.63 | 204.13 | **199.04** |
| AMZN | 259.30 | 254.01 | 189.68 | 241.25 | **259.40** |
| META | 610.15 | 681.91 | 646.90 | 669.93 | **650.49** |
| RELY | 23.29 | 23.67 | 21.36 | 24.04 | **24.04** |

The mechanical rows under this spec: GOOG 404.28 → 394.73, QCOM 342.38 → 336.88, AMZN 288.84 →
299.18, META 751.01 → 716.57, RELY 46.66 → 50.07. The consensus steps behind the moves, earnings
then revenue: GOOG 21%, 22% / 22%, 16%; QCOM 24%, 28% / 16%, 20%; AMZN 22%, 34% / 17%, 15%; META
19%, 15% / 19%, 17%; RELY 24%, 59% / 18%, 17%. The marginal returns: GOOG five-year 47.2%,
three-year 39.1%, one-year 21.4%; AMZN 14.9%, 32.2%, 11.4%; META 31.3%, 45.9%, 21.0%; RELY 31.9%,
102.7%, −154.6%; QCOM's five-year is not usable (−5.6%), the three-year aggregate 35.3% is used.

What the probe showed: the fade alone lowers every value 5% to 9%; the floor bites only where
consensus growth outruns the return (AMZN, RELY's raw path); the revenue charge cuts both ways
(META and the QCOM review fall, since their revenue grows faster than their earnings path in one
year); the three-year marginal is blind to a surge that sits in the 2026 guidance, since the stored
capital ends at fiscal 2025.

The probe was a throwaway script in the session's scratch directory that patched the engine's
charge in place; it is not kept. Its values at the belief in force are the figures above, and the
builder's engine must give them within 0.1% on the same stored inputs; where it does not, the
builder names which rule of section 6 reads differently before changing anything, and this
document's words govern. The probe recomputed the hold K at each trial of the implied-growth solve,
which 6.3 now fixes, so the implied growth figures it printed are not acceptance figures.

## 6. The charge

### 6.1 The cash flow of a year

Section 4.8 becomes, for every year t of the path on the Mature Growth and Mature Stable routes:

    cash_t = earnings_t × (1 − h_{t+1} ÷ return_t)

with no floor, where h_{t+1} is the growth the charge pays for (6.2) and return_t the return of 6.3.
A year whose growth outruns its return pays a negative cash flow. `charge_off` still drops the
charge in years 1 to N − 1 (4.6 rule 4): cash_t = earnings_t there. The terminal multiple and the
value's sum are unchanged.

`growth-above-return` keeps its code and stays a note. Its sentence changes: "In year t the charge
pays for h_{t+1} of revenue growth at a return of r_t, so the year pays out less than nothing: the
owner funds the growth." It names the first such year and counts the rest.

### 6.2 The growth the charge pays for

On Mature Growth, h for years 2 and 3 is the consensus revenue step: the annual consensus revenue
mean of the base year and the next two, read as 5.3 reads the net-income means (the same rows, the
same base year, `growth_step` on revenue, a mean of zero with no analyst count no estimate). A
revenue step that is missing, or whose earlier year is not positive, takes the earnings step of the
same year (as resolved, an override included), which is the rule as built. Years 4 to 3 + the fade
years fade from the year-3 revenue step to the belief in equal steps, as 5.5 fades the earnings
path, and the years after grow at the belief; the runway cuts the path as before. So h and the
earnings growth differ only in the consensus and fade years, and in the belief years h is the
belief. h_{N+1} is g_T.

An earnings step override (`path.step_2`, `path.step_3`) moves the earnings path and, where a
revenue step is missing, the h that falls back on it; it never moves a revenue step the consensus
gives. The implied growth (5.7) solves on the belief with both paths' fades recomputed at each
trial, as the earnings fade is today, and the hold K of 6.3 fixed.

On Mature Stable the path grows at g_T in every year (6.3), so h_t = g_T in every year and the
charge is as built but for the fade of 6.3.

The intermediates carry `charge.growth_by_year`, h for years 2 to N + 1, and `charge.revenue_steps`,
the two revenue steps as found (`None` where missing), beside the earnings path's `path_steps`.

### 6.3 The return by year

Section 4.6 still chooses the runway return R (the five-year marginal when usable, else the
three-year aggregate, floored at r) and 4.7 the terminal return T. The charge no longer holds R for
years 1 to N − 1. Let K be the hold: the last year t in 1 … N − 1 whose next earnings growth
g_{t+1} is above the belief, 0 when none is, so the hold runs through the consensus steps and the
growth fade even when a flat step sits inside them (*my call*, from the builder check: the last
such year, not a count, so a path with g_2 at the belief and g_3 above it holds through the fade).
K is read once from the row's own path at the belief in force, the mechanical belief or an
override's, and the implied growth (5.7) and the sensitivities hold it fixed while the trial belief
moves, so the value stays continuous in the belief; `charge.hold_years` is a rebuild key (6.4).
Then

    return_t = R                                   for t ≤ K
    return_t = R + (T − R) × (t − K) ÷ (N − K)     for K < t ≤ N

so return_N = T, as today. With K = 0 (a path with no growth above the belief, every Mature Stable
row) the return fades from R in year 1; with K ≥ N − 1 (a short runway cut mid-fade) only year N
takes T, which is the rule as built. A `return.runway` override replaces R, the fade's start, and T
still follows the moat on the measured return (14.4); `charge_off` leaves years 1 to N − 1
uncharged as before.

`RoicTerms` gains the newest year's marginal return, `runway_return.one_year`, the change in NOPAT
over the change in average capital from the kept year before the newest to the newest, with no
usability test, `None` with fewer than two kept years or no change in capital. It is shown, never
used.

The `heavy-capex` sentence (8) becomes: "Trailing capital spending is X% of operating cash flow,
above 50%. The charge's return starts at R, the five-year marginal (or: the three-year aggregate);
the newest year's marginal return is Y%, on the capital added in <fiscal year>. The stored years
end at <fiscal year>, so a return on a spending surge still under way is the agent's judgment:
`return.runway`." Without a one-year figure the sentence stops at R.

The intermediates carry `charge.return_by_year` (years 1 to N) and `charge.hold_years` (K). The
four return keys of 5.8 each give their return the same shape: the key's return as R, the moat's
terminal rule on it as T, the hold from the row's own path; `ten-year` likewise.

### 6.4 What moves with the price

`growth_at_price` rebuilds the paths and the charge from the intermediates alone, so the rebuild
keys gain `charge.revenue_steps`, `charge.hold_years` and the terminal return as before; a reprice
and the growth-route cross-check (6.4 of the method) read them.

## 7. The consensus-basis flag (B-133)

A note, `consensus-basis-unknown`, on a Mature Growth or Mature Stable row when `large-nri` fires:
"The non-recurring gap is $X a share, Y% of trailing EPS. FMP's consensus names no basis, so whether
the NTM anchor and the path carry such items is unknown; a report that reads the filing decides,
through `earnings.ntm` or `earnings.nri_gap`." It fires after `large-nri` in the flag order, never
without it, and changes no figure.

## 8. The value outside the business and the share count (B-139)

Two inputs join 14.2. Neither has a mechanical reading: the engine finds nil and none.

| Tag | Routes that read it | The input | Range | Lifetime |
|---|---|---|---|---|
| `value.outside` | Mature Growth, Mature Stable, High Growth, Young Growth, Decline | a figure a share outside the business, after tax, added to the route's value a share: a stake, an asset held for sale, a settlement still owed (negative) | −$1,000 to $1,000 a share | lasting or period-tied |
| `shares.diluted` | every route | the diluted share count of 4.2, for shares committed but not yet in the reported count (a forward sale, a mandatory convertible) | above 0 to 10^12 shares | period-tied only |

- `value.outside` applies after the route's value a share and before the levels: value a share =
  the route's + the figure; the levels, price ÷ value and the designation read the sum (4.10). The
  implied growth, the margin the price needs and every other solve on the price target the price
  less the figure, the business's share of the price. Sensitivity cells and the values by runway
  and by return each add the figure. The expected return's repricing term reads the sum. Start-up
  reads it not (no value). The bridge line is last, after `balance.cash`, labelled "outside the
  business"; its old value is nil. The intermediates carry `outside_value_per_share` under the
  override only. Evidence: any kind, as the other inputs (*my call*: a filing is the usual source,
  but B-142 showed the filing may be unreadable and the figure taken from secondary coverage,
  which the report then says).
- `shares.diluted` replaces the diluted count of 4.2 before the guard "no positive diluted share
  count" and everywhere the count is read: the value a share, NTM net income (5.2, which is NTM EPS
  × the count), after-tax SBC a share, Mature Stable's E a share, the growth routes' and Decline's
  value a share, the Start-up requirement. The agent is told this in the playbook: a count raised
  for shares not yet issued raises NTM net income with it, so the agent reads the consensus EPS's
  own share basis first. Period-tied only, so each new statement re-asks the question (the
  period-tied drop of 14.6). Its bridge line follows `balance.cash` and precedes `value.outside`,
  labelled "diluted shares". `current_reading` is the count the result cites. "shares_diluted is
  reported data" leaves LOCKED; the tag is the one door.
- Both are JUDGMENT entries as 14.4 describes; `INPUT_OF` names `shares_diluted` for the count and
  nothing for the outside value.

## 9. The step-series check (B-140)

In `path_steps`, both series are read: the step on net income and the step on EPS for each of the
two steps, where each series has the figures. When both exist for a step and they differ by more
than `step_series_gap_max` (5 points) in size, the note `step-series-disagree` fires: "Step n reads
g% on net income and h% on EPS: the two consensus series imply different share counts (A and B
against the diluted count C). The path is on <series>; `path.step_n` decides." The path stays on
the series 5.3 chooses. The note fires once, naming each such step; never on a step an override
replaced. It fires on the Mature Growth route alone: the growth routes and Decline read the
revenue series and no earnings series, and the Mature Stable cross-check reads it but a stable row
shows none of the cross-check's notes (method 6.5), which stands. A test on the implied count's
level is not added (META's 2026 to 2028 all run 3% to 7% high with the steps unharmed).

## 10. Stock splits (B-143)

### 10.1 The dataset

A new per-company call, `splits`, on FMP's stable `splits` endpoint (symbol; each row a date, a
numerator and a denominator, to be confirmed live as the other endpoints were), fetched with the
company's datasets at every full and scoped refresh, stored as a response with normalized rows
(date, ratio = numerator ÷ denominator). The ratio is above 1 for a split and below 1 for a reverse
split. A failed call stores its error as the others do and the row carries no split handling.

### 10.2 The rule

Every per-share figure and every share count is read on the share basis of the quote date. For a
split whose date is after a figure's source period end and at or before the price date:

- a share count from that source is multiplied by the ratio;
- a per-share figure from that source is divided by the ratio: the trailing diluted EPS (each
  quarter by its own period end, so a trailing sum of mixed quarters scales each quarter),
  the street actuals of the basis test, GuruFocus's trailing EPS and EPS without non-recurring
  items by their observation date, and the daily closes before the split date, unless the live
  check of 10.3 finds FMP's refetched series already on the post-split basis;
- the consensus EPS by fiscal year and quarter: scaled only when its implied share count, the
  net-income mean ÷ the EPS mean, is within `split_implied_count_tolerance` (15%) of the pre-split
  count (the diluted count before scaling) and not of the post-split one; a consensus FMP has
  already adjusted is left alone. Without a net-income mean the consensus EPS is left alone and
  the sentence says so.

The flag `split-pending` (a note) names the split, its date and ratio, and each figure scaled: "A
2-for-1 split of 28 Jan 2027 falls after the newest statement (30 Sep 2026): the diluted count,
trailing EPS of 4 quarters, the street actuals, the closes before the split and the consensus EPS
for fiscal 2026 to 2028 are read on the post-split basis." It fires until the stored sources are
themselves post-split.

### 10.3 The vendor check, and what each refresh kind does

Before writing the rule, the builder checks live on three companies that split in 2024 (NVDA
10-for-1 of June 2024, AVGO 10-for-1 of July 2024, WMT 3-for-1 of February 2024): whether FMP's
quarterly statement rows before the split carry restated or as-filed EPS and share counts; whether
its consensus rows are restated; whether `historical-price-eod/full`'s `close`, the field
`price_closes` reads, is on the post-split basis after the split; and whether the `splits`
endpoint lists a split before its effective date. The rule scales only what the vendor leaves as
filed, and the readout records the four findings; if FMP restates every statement row, the
statement branch above is dropped and the rule covers the GuruFocus figures and the consensus
alone, and the closes branch goes if the refetched closes are already adjusted.

The rule runs in assembly (4.2), so it runs at a full, a scoped or a revalue refresh. A price
refresh reprices from the intermediates and applies no split rule: on a split day the stored
pre-split value meets a post-split quote until the next refresh that runs assembly, which is the
symptom B-143 filed. The remedy is a scoped refresh of the company, which refetches its statements,
closes and splits and runs assembly on them (*my call*, from the builder check; no second vendor
call for announced splits). The playbook's step 3 says so: when a split is announced or recent,
start the scoped refresh, not the price one, and read `split-pending` on the row. For META's
January 2027 split the acceptance is a scoped refresh of META after the split date showing
`split-pending` with the scaled figures and a price ÷ value near the pre-split one.

A second listed class of a company is a row of its own (section 3).

## 11. Policy v10

| Value | Name | Setting | Source |
|---|---|---|---|
| Step-series gap: 5 points | `step_series_gap_max` | no | the AMZN and META sessions; no source gives the number |
| Split implied-count tolerance: 15% | `split_implied_count_tolerance` | no | the META session (its 2026 to 2028 counts run 3% to 7% high); no source gives the number |
| Override range of the outside value: −$1,000 to $1,000 a share | `override_ranges` | no | spec 2026-11-09 8; no source gives the numbers |
| Override range of the diluted count: above 0 to 10^12 shares, the lower end excluded | `override_ranges` | no | spec 2026-11-09 8; no source gives the numbers |

Every v9 value is unchanged; v9 stays byte-identical under its hash. No new setting.

## 12. The method document, the Methodology page, the drawer, the report page and the playbook

- `docs/method.md`: 4.8 rewritten on 6.1; 4.6 gains the one-year figure and 6.3's shape, as a new
  4.8a or inside 4.8 as the builder sees fit; 5.3 gains the revenue steps; 5.6 to 5.8 read the new
  charge; 5.11, 6.5 and 8 the new notes and sentences; 2 and 10 the splits dataset and what a
  refresh does with it; 4.2 the split basis and the share-count override; 14.2 to 14.5 the two
  inputs; 4.1, 4.1a and 11 the version rows. The Methodology page's charge section says the charge
  pays for revenue growth, that a year can pay less than nothing, and that the return fades; its
  examples' figures are re-read at method 1.0.
- The drawer: the charge's row shows the return by year as a short series or its ends, and the
  growth it pays for beside the earnings growth; the bridge shows the two new lines with their
  labels; the flags' new sentences.
- The report page: section 8's outside-value line reads from the bridge as the other lines do.
- The playbook (`playbook/fairband-research`): the return judgment's row says, when `heavy-capex`
  fires, read `intermediates/runway_return/one_year` and the capex guidance, decide the runway
  return and cite both figures; section 8's detail names the outside value and the share count as
  the agent's inputs, with the double-count rule (anti-goal 2) and the NTM net-income effect
  (section 8); `split-pending`, `consensus-basis-unknown` and `step-series-disagree` join the
  flags the agent reads; step 3 starts a scoped refresh, not a price one, when a split is announced
  or recent (10.3); `reference/tools.md` and `reference/citations.md` name the new tags and
  intermediates; `reports/refs.py` gives the new intermediates their words.

## 13. Worked numbers for the tests

r 9%, g_T 3%, runway return R 20%, terminal T 13% (terminal multiple 13.2051), year-1 earnings 100,
consensus earnings steps 25% and 20%, revenue steps 15% and 10%, belief 5%, fade 5 years.

### 13.1 Runway 5

Earnings by year 100, 125, 150, 175.5, 200.07. Growth paid for, earnings 25%, 20%, 17%, 14%, 3%
(g_T); revenue 15%, 10%, 9%, 8%, 3%. K = 4, so year 5 alone takes T, as built.

| | Cash by year | PV of the years | PV of the terminal | Value |
|---|---|---|---|---|
| As built (0.9) | 0, 0, 22.5, 52.65, 153.9 | 154.6972 | 1,717.0862 | 1,871.7834 |
| The floor off alone, earnings charged | −25, 0, 22.5, 52.65, 153.9 | 131.7614 | 1,717.0862 | 1,848.8476 |
| This spec | 25, 62.5, 82.5, 105.3, 153.9 | 313.8675 | 1,717.0862 | 2,030.9538 |

### 13.2 Runway 10

Earnings 100, 125, 150, 175.5, 200.07, 222.08, 239.84, 251.84, 264.43, 277.65. Earnings growth paid
for 25%, 20%, 17%, 14%, 11%, 8%, 5%, 5%, 5%, 3%; revenue 15%, 10%, 9%, 8%, 7%, 6%, 5%, 5%, 5%, 3%.
K = 6. Return by year 20%, 20%, 20%, 20%, 20%, 20%, 18.25%, 16.5%, 14.75%, 13%. Cash by year 25,
62.5, 82.5, 105.3, 130.0455, 155.4544, 174.1333, 175.5221, 174.7913, 213.5764. PV of the years
745.0974, PV of the terminal 1,548.7248, value 2,293.8222. As built: cash 0, 0, 22.5, 52.65,
90.0315, 133.2466, 179.8829, 188.8771, 198.3209, 213.5764; value 2,116.085.

### 13.3 A Mature Stable path, runway 10

E 100 growing at g_T; K = 0; the return fades from year 1: 19.3%, 18.6%, 17.9%, 17.2%, 16.5%,
15.8%, 15.1%, 14.4%, 13.7%, 13%. Cash 84.456, 86.3871, 88.3096, 90.2135, 92.0871, 93.9159,
95.6823, 97.365, 98.9375, 100.3672; value 1,315.0993 (as built 1,335.796). EPV 1,111.11.

### 13.4 The other pieces

- A revenue step missing in year 3 (no revenue mean) takes the earnings step: on 13.1 with the
  year-3 revenue step missing, h is 15%, 20%, then the fade from 20%, so years 3 and 4 pay for
  17% and 14%; the cash by year is 25, 0, 22.5, 52.65, 153.9 (year 2 pays for 20% at a 20% return),
  the PV of the years 177.6329 and the value 1,894.7191.
- `value.outside` of $12 a share on a route value of $100: value $112, the levels on $112, the
  implied growth solved to a target of price − 12.
- `shares.diluted` from 1,000 to 1,060 with an NTM EPS of $5: NTM net income 5,300, not 5,000.
- `step-series-disagree`: net income 8.33 → 10.00 and EPS 0.83 → 1.10 on 10.0 shares give 20.0%
  against 32.5%, a gap of 12.5 points, fires; 20.0% against 24.0% does not.
- A split of 2 dated between a quarter ending 30 Sep and a price of 30 Oct: a count of 1,000
  reads 2,000; a trailing EPS of four quarters at $1 each, all predating the split, reads $0.50
  each and $2 in sum; a consensus EPS of $4.20 on a net-income mean of 4,200 implies 1,000 shares,
  within 15% of the pre-split count, so it reads $2.10; one of $2.10 implying 2,000 is left alone.

## 14. Tests the builder must write

- `mature_growth.py`: 13.1 to 13.3 in full (cash by year, the return by year, the hold, the
  value), the fallback of 13.4; `cash_to_equity` with no floor; `terminal_multiple` unchanged;
  `implied_growth` solving with both paths recomputed.
- `roic.py` and `route_steps.py`: the one-year marginal; `RoicTerms.charge` carrying R, T and the
  hold; the `heavy-capex` sentence with and without a one-year figure.
- `route_mature_growth.py` and `route_mature_stable.py`: the revenue steps read on the base year;
  `growth-above-return`'s new sentence; `consensus-basis-unknown` after `large-nri` and never
  without it; the rebuild keys; a reprice and the cross-check rebuilding the same charge; the four
  return keys on the new shape; every worked figure of method 5.13 and 6.3 re-pinned.
- `anchor.py`: `step-series-disagree` on both series, silent on a replaced step and under the gap.
- `overrides.py`, `review.py`, `route.py`: the two tags' rules (routes, ranges, the period-tied
  lifetime of the count), their bridge lines and labels, `current_reading` (nil and the count),
  the JUDGMENT entries; `value.outside` on the levels, the implied growth's target and the
  sensitivities; `shares.diluted` on NTM net income and the value a share.
- The splits: the normalized rows; the rule of 10.2 on each figure; `split-pending`'s sentence;
  the consensus test both ways; a reverse split; a fetch failure leaving the row as built.
- `policy`: v10 loads, the four values, v9 byte-identical under its hash.
- The goldens (`tests/fixtures/golden`): MGCO and MSCO re-captured under 1.0 with a note in the
  README naming the sections that moved them; HGCO, YGCO, DCCO and SUCO unchanged bit for bit,
  which the test asserts.
- `web` and `reports`: the drawer's charge row and the two bridge lines; the Methodology page's
  text; the refs' words for the new intermediates; the playbook tests on the new lines.

## 15. Acceptance and the readout

After the merge, a backup of the live database, the server restarted from main, and one revalue.
The readout, on the same shape as the earlier readouts:

- The five companies: mechanical and reviewed values against section 5's figures within rounding
  (GOOG 394.73 and 339.28, QCOM 336.88 and 199.04, AMZN 299.18 and 259.40, META 716.57 and 650.49,
  RELY 50.07 and 24.04), the designations named.
- Mature Growth and Mature Stable: the valued counts, the median move in value, the count of rows
  with a negative cash year, the count whose runway return starts above the terminal (the fade
  bites), the `consensus-basis-unknown` and `step-series-disagree` counts.
- Every revenue-growth, Decline and Start-up row: value, levels, designation and refusal bit for
  bit as refresh 21, flags too but for the new notes.
- The splits: after the first full refresh with the dataset, the rows with a split on file, the
  rows flagged `split-pending`, and the vendor finding of 10.2.
- The existing overrides: GOOG's and META's `return.runway` keep applying (the start of the fade);
  AMZN's, QCOM's and RELY's step overrides keep applying; the period-tied drops as 14.6 says.

## 16. Left to the builder

- Where the revenue steps are read: `anchor.path_steps` on both series, or a sibling for the
  revenue series, as the builder sees fit, on the same base year.
- The shape of `Charge` with a return by year and the hold, and of `_years`; whether
  `mature_stable_values` keeps its signature.
- The names of the new intermediates within section 6's keys; the drawer's exact sentences in the
  page's register; the refs' words.
- The splits dataset's normalized shape and where the scaling lives (assembly, 4.2, is the natural
  place); the live vendor check of 10.2 and its record in the readout.
- The order of the two new bridge lines after `balance.cash` is fixed (count, then outside value);
  their place among the JUDGMENT entries follows.

## 17. Order of work

1. Policy v10 and the 1.0 rows of `docs/method.md` (4.1, 4.1a, 11); the goldens' baseline check.
2. The charge (6): `mature_growth.py`, `roic.py`, `route_steps.py`, the two mature routes; method
   4.6, 4.8, 5.3, 5.6 to 5.8, 5.11, 6.3, 6.5, 8; the goldens re-captured.
3. The notes (7, 9); method 5.11, 8.
4. The two inputs (8); method 14.2 to 14.5.
5. The splits (10): the vendor check, the dataset, the rule; method 2, 4.2, 10.
6. The drawer, the report page, the Methodology page, the refs' words and the playbook (12).
7. Backup, merge, revalue, the examples' figures re-read, the readout (15); the splits dataset
   arrives with the next full refresh.

## 18. Sources

| Rule | Source |
|---|---|
| Reinvestment above earnings is a negative cash flow to equity, funded by new shares or debt; no floor | Damodaran, *Investment Valuation* 2e, ch. 11 and 12 (the equity reinvestment rate above 100%); "growth is never free", *Return on Capital* pp. 60–61; Koller's value-driver formula (stocks V99) and Mauboussin V101 carry the same sign |
| Growth splits into reinvestment × return and efficiency growth from margin change on existing capital, which is temporary | Damodaran, *Investment Valuation* 2e, ch. 11 (research note H12); CLC ch. 11 (margins converge) |
| Reinvestment follows the change in revenue | Damodaran's Ginzu template, reinvestment_t = ΔRevenue ÷ sales-to-capital (H13, H16); method 5a.5 on the growth routes |
| The return holds through high growth, then fades toward the stable return | Damodaran, *Return on Capital* pp. 58–60, the advantage-and-barriers lookup (H29); excess returns fade faster at heavy reinvestors (H5, citing Madden); the Ginzu template fades inputs linearly over years 6 to 10 |
| Multi-year figures over one-year ones for the marginal return | Damodaran, *Investment Valuation* 2e, ch. 11, footnote on averaging dollar reinvestment over three to five years (H17); the marginal return is what matters for growth (H21) |
| The agent owns the judgment inputs; the engine owns the arithmetic | the literature report's engine table, "All Narrative to All Numbers"; design.md 7 |
| Assets outside the business added to the value a share; shares committed but not issued in the count | Damodaran, *Investment Valuation* 2e, ch. 16 (cash, cross-holdings and other non-operating assets added to operating asset value; options and other claims subtracted); the AMZN and META sessions |
| A split changes no value; every per-share figure moves to one basis | arithmetic; the META session |

## Decision log

| Date | Decision |
|---|---|
| 2026-11-09 | The order: the inline round (B-131, B-132, B-141, B-144), then this engine round (B-129, B-130, B-133, B-139, B-140, B-143), then B-28. Founder. |
| 2026-11-09 | B-129: the floor goes; a year whose growth outruns its return pays a negative cash flow. Claude's advice from the literature; the founder agreed. |
| 2026-11-09 | B-129, the shape: the charge pays for revenue growth, earnings growth above it being margin change. Claude's proposal after the founder asked for a rule that is logical, rooted in the literature and not fitted to AMZN; probed on the five companies; the founder accepted the fidelity version. |
| 2026-11-09 | B-130: the return holds through the high-growth years, then fades to the terminal return (Damodaran's lookup); the five-year marginal stays the start; the one-year marginal is shown in the `heavy-capex` sentence, not used; the override is the remedy. Founder, choosing fidelity over the variant (H) that read the one-year figure into the mechanical row, after Claude set out the trade-off: H reproduced both agents' overrides but rests on a one-year figure Damodaran calls noisy, and the three-year marginal proved blind to a surge still in guidance. |
| 2026-11-09 | The Wide spread stays at 4 points in the policy; it is a setting the founder can move. Founder. |
| 2026-11-09 | B-133 as the flag alone; B-139 as two inputs on the bridge; B-140 as a note; B-143 as a fetched dataset and a basis rule with a live vendor check first; a second share class keeps its own row. Claude's calls, written into the spec for the founder to overturn. |
| 2026-11-09 | Method 1.0, since every mature row's value moves; policy v10 with no new setting. Claude's call. |
| 2026-11-09 | Builder check done. Five questions, all settled by Claude: the hold K is the last year above the belief, not a count, read once at the belief in force and fixed in the solve (6.3); a price refresh applies no split rule, a scoped refresh is the remedy and the vendor check gains the closes and the endpoint's dating (10.3); the probe is a throwaway and the words govern, the five values within 0.1% (5); the step-series note fires on Mature Growth alone (9); 13.4's fallback figures corrected to 25, 0, 22.5, 52.65, 153.9. Nothing for the founder. |
