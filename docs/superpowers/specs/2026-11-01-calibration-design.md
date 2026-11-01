# Calibration of the Mature Growth charge: design

Status: approved by the founder on 2026-11-01 (the return on new capital, the payout floor and the
fade; return on invested capital kept over return on equity). Builder check done the same day;
its six questions are settled in the text and marked *my call*.

This document amends the mechanical screen spec
(`docs/superpowers/specs/2026-10-31-mechanical-screen-design.md`, section 6.6) and the legacy
design (`docs/legacy/design.md`, sections 6.5 and 6.6). Where it and either of those disagree,
this document wins for the Mature Growth and Mature Stable routes. Everything it does not mention
stays as the mechanical screen spec says.

## 1. What this is

The first full refresh (2026-11-01, 1,759 companies) valued most mature growers far below the
price and far below the stocks repo's `mech/1.2` sheet. CRM came out at $37.57 against a sheet
value of $297. Of 658 valued Mature Growth rows, 438 had a runway ROIC below their growth path.
The median value divided by price was 0.60.

The cause is not the reinvestment charge. Every author in the literature report charges growth
for the capital it uses. The cause is the number the engine feeds into the charge. The formula
wants the return on *new* capital (McKinsey calls it RONIC and has a slide titled "The difference
between RONIC and ROIC"; Damodaran: "the value of the firm is a product of the marginal return on
capital and the reinvestment"). The engine fed it the ten-year average return on *all* capital.
Those differ most for companies whose returns changed (CRM: 1% to 12% over ten years) and for
companies whose capital is acquisition goodwill (CRM: $58 billion of goodwill in $55 billion of
capital).

A second cause is the shape of the growth path. The engine drops from the year-3 consensus rate
to the base-rate belief in one step. No source models that drop. Damodaran fades over five years
and reserves the one-step drop for "moderate growth rates".

This piece changes four things in the engine and adds one cross-check:

1. The runway return becomes the return on new capital, with a fallback and a floor.
2. The payout never goes below zero.
3. The growth path fades from the year-3 rate to the belief over five years.
4. The terminal return reads the runway return, not the ten-year aggregate.
5. A Mature Stable row with a consensus path also shows the growth-route value.

## 2. Goals

- A Mature Growth value that a reader can defend from Damodaran, McKinsey and Mauboussin, line
  by line, with the sources named in the policy file.
- CRM, Amazon and the other large growers valued on what their new capital earns, not on what
  their old capital earned.
- The same inputs and the same policy version give the same value, bit for bit, as the
  mechanical screen spec requires. This is about v2 runs; v1 results are not reproduced.
- Every stored result from the first run can be revalued under the new rules without a vendor
  call, so the calibration can be read on the same data.

## 3. Non-goals

- The required return stays 9%. It is the founder's hurdle (Penman, Greenwald) and becomes a
  user setting in a later piece.
- Terminal growth stays 3%. Damodaran's default is the risk-free rate; raising it moves values by
  about 2% and is left for the settings piece.
- The Wide-moat terminal cap stays 13%. The top of Damodaran's "modest (<4-5%)" range would be
  14% and moves values by under 1%.
- The growth belief stays the Base Rate Book median for the sales class plus 2 points. A moat-
  linked percentile would put the moat into the valuation a third time.
- Return on equity is not used. Damodaran prescribes it for an equity model and offers a buyback
  adjustment when book equity is distorted; the founder keeps invested capital because it is the
  base growth draws on and it holds where book equity is shrunk, zero or negative (Apple, Home
  Depot). The policy file records this.
- The classifier is unchanged: its three-year revenue window, its checks and its deciles. The
  checks firing on 63% of rows, the notes and preferred shares that pass the universe filter and
  the fifteen countries without tax rows are the next piece.
- No user interface work beyond the drawer fields and the columns this document names.
- No route beyond Mature Growth and Mature Stable.

## 4. Anti-goals

- Growth made free. The charge stays in every year, including the faded years and the terminal.
  A value computed without the charge is never shown as the value.
- A rule that only works for the large companies. Every rule here ran over the 563 Mature Growth
  rows of the first refresh with stored intermediates, and the population figures are in
  section 9.
- A third place for the moat. It sets the runway and the terminal return, and nothing else.

## 5. The rules

Notation: r = 9%, g_T = 3%, N the runway in years by moat class (5, 10, 20). "Kept ROIC years"
are the fiscal years the ROIC build keeps today (`roic.py`): a year with a NOPAT and both its
opening and closing invested capital, the last ten of them, oldest first.

### 5.1 The runway return: return on new capital

The return used in the charge for years 1 to N−1 is, in this order:

1. **The five-year marginal return**, when it is usable:

   marginal = (NOPAT_last − NOPAT_first) ÷ (capital_last − capital_first)

   where "last" is the newest kept ROIC year, "first" is the kept year five positions earlier,
   and capital is that year's average invested capital. It needs at least six kept years. It is
   usable when all three hold: capital_last − capital_first > 0; that growth is at least a fifth
   of |capital_first|; NOPAT_last − NOPAT_first > 0.

2. **The three-year aggregate**, otherwise: the sum of NOPAT over the sum of average invested
   capital across the last three kept years. It needs at least five kept years, as the ten-year
   aggregate does today; with fewer, the row is "ROIC unavailable" and the charge uses the
   terminal return in every year, as today.

3. **The floor**: the result is never below r. No cap.

4. **Charge off**: when the marginal is not usable and the three-year capital sum is at or below
   zero, the runway charge is zero (payout 100% in years 1 to N−1) and the row is flagged "Charge
   zeroed". The terminal still charges, at the moat's terminal return with no measured input: 13%
   for Wide, r otherwise (*my call*, from the builder check; today's rule drops the terminal
   charge too, which is the "RONIC equals infinity" terminal every author rejects, and 37 rows
   including Booking were valued that way). A business funded by its customers needs no capital
   to grow in the runway; it does not earn an infinite return forever.

The row records which measure it used, as the input tag's note and in the intermediates:
`runway_return = {"used": "marginal" | "three-year" | "floor" | "off", "marginal": x | null,
"marginal_usable": bool, "three_year": x | null, "ten_year": x | null, "value": x}`. "floor"
means the chosen measure was below r and r was used.

The ten-year aggregate stays computed, stored and shown. It no longer enters the charge.

Sources: Damodaran, Investment Valuation ch. 11, the marginal return measured as the change in
income over the change in capital (openalice note H21); his rule to keep "the company's ROC" for a
company with a strong advantage (H29) is the fallback; McKinsey, continuing-value deck, "The
difference between RONIC and ROIC" (stocks note T31) and marginal returns rising to the cost of
capital (G42) are the floor; Mauboussin, "measuring incremental ROIC" (G22).

The five-year window, the one-fifth test and the three-year fallback window are the founder's
and the author's choices; no source gives a window. They are policy values.

### 5.2 The payout floor

Cash to equity in year t = NI_t × max(0, 1 − g_{t+1} ÷ return_t), with return_t the runway return
for t < N and the terminal return for t = N. The timing convention is unchanged.

When any year's payout is floored, the row is flagged "Growth above return" with the sentence
"Year <t> growth of <g>% exceeds the <return>% return on new capital; the payout is floored at
zero and the growth above the return is treated as efficiency growth, which costs nothing."

Source: Damodaran, Investment Valuation ch. 11: a negative reinvestment rate is not forecast
(H17), and growth above what the return funds is "efficiency generated growth" (H12). The floor
is the simple form of that rule.

### 5.3 The terminal return

Unchanged in form, changed in input. Wide moat: the runway return of 5.1 (before its floor is
applied, the chosen measure), capped at 13% and never below r. Narrow and None: r. A charge-off
row takes 13% for Wide and r otherwise (5.1, rule 4).

This rule is shared by both routes (*my call*, from the builder check). The Mature Stable
stable-growth value reads the same terminal return, so a company has one return measure whatever
its route. Eighteen Wide-moat stable rows of the first run had a ten-year aggregate under the 13%
cap; their stable value can rise by up to 15% where the chosen measure is higher. The stable
route's "ROIC unavailable" case reads the three-year capital sum of 5.1.

### 5.4 The fade

Years 1 to 3 are unchanged: the NTM anchor, then the two consensus steps g_2 and g_3, a missing
step taking the belief. Let b be the belief.

If g_3 > b, years 4 to 8 fade linearly from g_3 to b:

  g_t = g_3 − (g_3 − b) × (t − 3) ÷ 5, for t = 4, 5, 6, 7, 8

so g_8 = b. Years 9 to N grow at b. If g_3 ≤ b, years 4 to N grow at b, as today.

The runway cuts the path, not the fade: with N = 5, years 4 and 5 take g_4 and g_5 and year 5 is
the terminal year; with N = 10, years 4 to 8 fade and 9 to 10 take b.

The fade length, 5 years, is a policy value. The moat does not change it.

Source: Damodaran's template, five growth years then five equal steps down (H2); the one-step
drop fits "firms with moderate growth rates" only (G6). Starting the fade after year 3 rather than
his year 5 is the more conservative reading, because only three consensus years count as data
(stocks method v1.7 section 3, kept). Fading to the belief rather than to the terminal rate keeps
the moat runway as the mechanical screen spec has it.

The guards stay: a path year with fewer than five analysts is flagged "Few analysts", and the
long-runway flag fires at a belief or an implied growth of 10% or more.

### 5.4a The expected return

The three-year expected return (method v1.7 Step 9) keeps its form. Its growth term reads the
path as modeled: g_2, g_3 and the year-4 rate g_4 of 5.4, which is the faded rate when the fade
applies and the belief otherwise (*my call*, from the builder check; 380 of the 658 valued
Mature Growth rows have g_3 above the belief, and for Amazon the term moves from 18.6% to about 24%).
The price refresh recomputes it the same way.

### 5.5 Implied growth

Unchanged in meaning: the belief b for years 4 to N at which the value equals the price, solved
numerically, with the fade of 5.4 applied at each trial b (so the fade target moves with the
trial). Also at each runway and at each return of the sensitivity, as today.

### 5.6 The sensitivity values

`value_by_roic` and `implied_by_roic` keep three keys and change the first: `"runway"` (the
return of 5.1 as used), `"0.15"`, `"0.09"`. A fourth key `"ten-year"` holds the value at the
ten-year aggregate as the runway return, not floored, with the moat's terminal rule applied to
it (which floors the terminal at r), or `null` when the aggregate is unavailable. It is there to
show the old basis: for CRM it is the $37.57 of the first run (*my call*). The value-spread flag
reads the first three, as today.

### 5.7 The Mature Stable cross-check

A Mature Stable row whose inputs allow the Mature Growth route (a positive NTM anchor, no refusal
from the anchor or the path) also carries the growth-route value in its intermediates:
`growth_route = {"value_per_share": x, "runway_return": {...as 5.1}, "path_steps": [...],
"belief": {...}, "implied_growth": x | null, "ntm_net_income": x, "runway": n, "fade_years": n,
"terminal_roic": x, "charge_off": bool, "refusal": null}`. When the growth route would refuse,
`growth_route = {"refusal": "<reason>"}` and the other keys are absent. The last five keys let a
price refresh rebuild the growth path and the charge from the intermediates alone, so
`implied_growth` moves with the price as the headline route's does (amended 2026-11-01 during
the build; the first draft left it at the valuation price).

The levels, the stance and the screen's value column stay on the stable-growth value. The drawer
shows the growth-route value under the headline as "Growth-route cross-check: $x (implied growth
y%)". The column chooser gains one column, "Growth-route value", filled on Mature Stable rows
that have it and on Mature Growth rows with their own value, empty elsewhere.

Source: Damodaran's consistency rule for a stable-growth firm, that it must behave like one
(H38); when the consensus says it does not, both values show the tension. This is a sensible
reading, not a prescription.

### 5.8 Versions

- Method version becomes `fairband-mechanical/0.2`.
- The policy file becomes `fairband-policy-v2.toml` with the new values of section 6 and the
  source lines of this document. `fairband-policy-v1.toml` stays in the repository, unchanged,
  because stored snapshots cite its hash and `record_policy` checks it. The engine loads v2 and
  needs its values; there is no code path that reproduces the v1 rules (*my call*, from the
  builder check). The old results stay readable in their snapshots, which name v1 and method
  0.1.
- A snapshot's method and policy versions tell the reader which rules produced it, as today.

### 5.9 Revalue from stored facts

The refresh gains a mode that runs the engine on the facts already in the store and writes new
snapshots, with no vendor call and no freshness window: `fairband refresh --revalue` (name is the
builder's). It records a refresh of kind `revalue`, reuses the latest stored deciles, and values
every company that has facts. The screen then shows the new snapshots. This is how the
calibration readout of section 9 is produced on the first run's data.

## 6. Policy values added or changed

| Name | Value | Source line |
|---|---|---|
| `marginal_return_span_years` | 5 | this document 5.1; Damodaran H21 gives the measure, not the window; policy value |
| `marginal_capital_growth_min` | 0.20 | this document 5.1; policy value |
| `fallback_return_years` | 3 | this document 5.1; Damodaran H29 "the company's ROC"; the window is a policy value |
| `fade_years` | 5 | this document 5.4; Damodaran's template fades in five equal steps (H2) |
| `roic_sensitivity` | [0.15, 0.09] | unchanged |
| `wide_terminal_roic_cap` | 0.13 | unchanged; the input is now the runway return (5.3) |

The policy file also carries one note under `[values.return_measure]` with no numeric value:
"Return on invested capital, not return on equity. Damodaran prescribes return on equity for an
equity model (H11) and adds back recent buybacks to book equity when buybacks distort it (IV 2e
ch. 13). Fairband uses invested capital because it is the base that growth draws on and it holds
where book equity is shrunk, zero or negative. Founder decision 2026-11-01."

## 7. Worked numbers for the tests

All synthetic. r = 9%, g_T = 3%. The builder's tests pin these to a tolerance of 0.01.

**Fade path.** Year-1 net income 1,000; steps 25% and 26%; belief 5.3%; runway 20. Growth for
years 2 to 9: 0.25, 0.26, 0.2186, 0.1772, 0.1358, 0.0944, 0.053, 0.053. Net income for years 1 to
9: 1,000.00; 1,250.00; 1,575.00; 1,919.29; 2,259.39; 2,566.22; 2,808.47; 2,957.32; 3,114.06.

**Value with the fade and the floor**, runway return 14.9%, terminal return 13%, same path:
24,941.95. Without the fade (today's cliff), same inputs: 19,699.10. With runway 5 and the fade:
20,520.66, with growth for years 2 to 5 of 0.25, 0.26, 0.2186, 0.1772.

**No fade when g_3 ≤ b.** Steps 4% and 5%, belief 5.3%, runway 20, return 14.9%, terminal 13%:
growth for years 2 to 5 is 0.04, 0.05, 0.053, 0.053 and the value is 14,910.79.

**Payout floor.** NI 100, next-year growth 25%, return 14.9%: cash −67.79 before the floor, 0
after, and the flag fires. NI 100, growth 5.3%, return 14.9%: cash 64.43, no flag.

**Marginal return.** Kept years 2017 to 2026 with (NOPAT, average capital): (100, 1,000),
(110, 1,050), (125, 1,100), (140, 1,200), (150, 1,300), (180, 1,500), (220, 1,700),
(260, 1,900), (300, 2,100), (350, 2,300). First = 2021, last = 2026. Marginal = 200 ÷ 1,000 =
0.2000; capital grew 76.9%, usable. Three-year aggregate 0.1444; ten-year aggregate 0.1277. The
runway return is 0.2000, `used = "marginal"`.

**Fallback.** Same NOPATs, capital 2,000 + 10 × (year − 2017): capital grew 50 on 2,040, 2.5%,
not usable. Three-year aggregate 0.1458, `used = "three-year"`.

**Floor.** Three-year aggregate 0.07 with the marginal not usable: runway return 0.09,
`used = "floor"`.

**Terminal.** Wide moat, runway return 0.28: terminal 0.13. Wide, chosen measure 0.098: terminal
0.098. Narrow, any return: 0.09. Charge off, Wide: runway payout 100%, terminal 0.13, so the
terminal multiple is 13.2 and not 17.2.

**Expected return.** Steps 25% and 26%, belief 5.3%: the growth term is
((1.25)(1.26)(1.2186))^(1/3) − 1 = 24.3%; with steps 4% and 5% it is ((1.04)(1.05)(1.053))^(1/3)
− 1 = 4.8%.

## 8. Tests the builder must write

- The fade path, the no-fade path and the runway cut, with the numbers of section 7.
- The value with and without the fade, section 7.
- The payout floor and its flag.
- The marginal return: usable, not usable on capital growth, not usable on falling NOPAT, fewer
  than six kept years; the three-year fallback; the floor; charge off on a non-positive
  three-year sum.
- The terminal return from the chosen measure, both cases, and the charge-off terminal.
- The Mature Stable value reads the shared terminal return: a Wide-moat stable row with a
  marginal return above 13% and a ten-year aggregate of 10% values at the 13% terminal.
- The expected return's growth term with and without the fade, section 7.
- The implied growth with the fade: at a price equal to the value at belief, the solve returns
  the belief within 1e-6.
- The Mature Stable cross-check: present with a path, absent with a refusal, the column filled.
- The sensitivity keys and the spread flag on the first three.
- Determinism: the same inputs twice give identical intermediates.
- The revalue mode: with facts and deciles stored and the vendor client stubbed to fail on any
  call, a revalue produces snapshots and makes no call.
- The policy v2 loads with every value of section 6; v1 still loads and records under its own
  hash.

## 9. Acceptance on the first run's data

Run `--revalue` on the database of the 2026-11-01 refresh. With the 2026-10-30 prices stored
there:

| | before | after |
|---|---|---|
| CRM value | $37.57 | $244.96 |
| Amazon | $162.11 | $250.49 |
| Microsoft | $466.65 | $515.58 |
| Alphabet | $310.08 | $399.55 |
| Meta | $659.00 | $749.28 |
| Nvidia | $331.57 | $457.66 |
| Tesla | $15.52 | $56.19 |
| median value ÷ price | 0.600 | 0.826 |
| share valued at or above price | 19.2% | 33.3% |

The company values are within 1% (they were computed twice outside the engine, by the author and
by the builder check, from the stored intermediates; the engine's own anchor and path code is the
same, so a larger gap is a defect). The two population figures are over the Mature Growth rows
that were valued in the first run without the charge zeroed, 619 rows, and the tolerance is 0.02
on the median and 2 percentage points on the share. QCOM, on the stable route, shows a
growth-route cross-check; its figure depends on the engine's analyst-count rule and is not
pinned.

The calibration readout on the page (mechanical screen spec, Task 24) shows the new distribution.

## 10. Left to the builder

- Where the runway-return build lives: a function beside `aggregate_roic` in `roic.py` or a new
  module; `RoicTerms` grows the fields of 5.1.
- The exact names of the flag codes and the policy keys, following the existing style.
- How the fade is expressed in `GrowthPath` (a precomputed rate tuple is fine) so that
  `growth_at_price` still rebuilds the path from the intermediates alone.
- The revalue mode's command-line form and its refresh kind.
- The drawer layout for the new fields, within the design system's components.
- The order of the migration if the snapshot table needs a column for the growth-route value;
  reading it from the result JSON is acceptable.

## 11. Order of work

1. Policy v2 and the method version.
2. The runway return and the terminal (5.1, 5.3), with the ROIC tests.
3. The payout floor and the fade in `mature_growth.py`, with the pinned numbers.
4. The route: intermediates, sensitivity keys, flags, implied growth.
5. The Mature Stable cross-check and the column.
6. The revalue mode.
7. Run the revalue on the first run's database and check section 9.

## 12. Sources

The labels are the openalice research notes' (`research_notes/Valuation methods by life cycle
phase/*.md`) and the stocks repo's (`docs/growth-duration-research.md`,
`docs/terminal-rate-research.md`, `docs/valuation-notes.md`).

- H2: Damodaran's template fades growth in five equal steps.
- H11: the equity identity, g = reinvestment rate × return on equity.
- H12, H17: efficiency growth; no negative reinvestment rate.
- H21: the marginal return, measured as the change in income over the change in capital.
- H29: keep the company's return during the growth period, then move toward the sector or the
  cost of capital.
- H38: a stable-growth firm must behave like one.
- H57: goodwill in invested capital.
- G6: a two-stage model fits moderate growth.
- G22: Mauboussin, consensus checked against incremental ROIC.
- G42: McKinsey, marginal returns rise to the cost of capital.
- T6: perpetual excess returns "modest (<4-5%)".
- T31: McKinsey, "The difference between RONIC and ROIC".
- V99: the value-driver formula.
- V104, V112: the Base Rate Book's persistence and the analysts' dispersion.

## Decision log

| Date | Decision |
|---|---|
| 2026-11-01 | The runway return is the return on new capital: five-year marginal, three-year aggregate fallback, floored at r. Founder. |
| 2026-11-01 | The payout is floored at zero; growth above the return is efficiency growth. Founder. |
| 2026-11-01 | The growth path fades from the year-3 rate to the belief over five years. Founder. |
| 2026-11-01 | Return on invested capital stays; return on equity and the buyback adjustment are recorded and rejected. Founder. |
| 2026-11-01 | r, terminal growth, the terminal cap, the belief and the classifier are unchanged in this piece. Founder. |
