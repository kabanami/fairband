# The engine round: a gentler Decline route, the growth routes' two faults, the classifier's established test, the margin-direction check and the tax table: design

Status: written 2026-11-06 from the founder's decisions of that day. The founder skipped the
brainstorm's questions ("skip the questions, propose a set from the backlog"), agreed to the three
proposals made on the probes' figures, and added the classifier item after the age table. The
decisions in the log at the end are the founder's. Items marked *my call* were settled by Claude
while writing and can be overturned. Builder check: see the status line at the end of the log.

This document amends `docs/method.md` (the method as built) in sections 3.4, 3.5, 3.6, 4.1, 4.1a,
4.3, 5a.4, 5a.5, 5a.10, 5a.13, 5a.14, 6.1, 6.4, 6a.2, 6a.5, 6a.9, 6a.10, 8, 9 and 11, and the
Methodology page with them. The mechanical screen spec, the calibration spec, the growth routes spec
and the 2026-11-03 spec of the Start-up and Decline routes stand for everything it does not mention.
When the pieces are built, their sections go into `docs/method.md` in the same commits, and that
document stays the statement of what runs.

## 1. What this is

Five changes to the engine, built as one piece under method `fairband-mechanical/0.9` and policy
`fairband-policy-v7`, applied by one revalue. No vendor call is needed: every field they read is on
file.

1. **A gentler Decline route** (B-1). The run-off holds the five-year trend's decline rate from year
   4 through the terminal, a perpetuity shrinking forever. Now the decline runs its course: the rate
   fades to zero by year 10 and the terminal is flat. And the consensus is read past year 3 where it
   reaches, on at least `analyst_min` analysts.
2. **The growth routes' two faults** (B-7). 63 of 151 High Growth and Young Growth rows are refused
   "value not positive under the reinvestment charge". Fifty of them are a reinvestment that outruns
   the terminal, from one of two faults: the company's own sales-to-capital can be absurd (ZYME 0.01,
   CRSP 0.01, AUR 0.00), and a loss larger than revenue on a straight-line margin path grows the
   dollar loss with revenue for years (CLDX at −2909%). The own measure must now be at least half the
   mature peers' median, and a loss larger than revenue moves in dollars, as the Start-up ramp does.
3. **The classifier's established test and the Start-up rule** (new, 2026-11-06). Take-Two (18
   profitable years of 29), Silicon Labs (20 of 27), Synaptics (21 of 28) and AXT (14 of 28) are
   Young Growth because their loss stretch is longer than two years and the established test reads
   3 of the last 5 fiscal years only. Kyivstar, a 30-year-old telecom listed through a SPAC, is a
   Start-up because its shell year 2022 has zero revenue. A company with 5 profitable years among the
   11 on file is established too, and an established company is never a Start-up.
4. **The margin-direction check** (B-74). It fires on 744 of 1,602 rows; 308 of them say "Stable
   points to Mature Stable" on a Mature Growth row, which says nothing. Stable points nowhere, and
   the direction deciles move from 8 and 3 to 9 and 2.
5. **The tax table** (B-27). The OECD series covers 146 jurisdictions; the packaged table holds 16.
   125 admitted companies in 32 countries have no row. The table is regenerated for every
   jurisdiction, with Taiwan and Cyprus by hand.

A sixth, small change rides with the classifier: a Mature Stable row refused "no positive trailing
earnings" keeps the growth-route cross-check, so the rows the classifier moves there (Silicon Labs,
Synaptics, AXT) keep a figure from the consensus.

## 2. Goals

- A Decline row's value says what a business that shrinks and then stabilizes is worth, not what
  a business that shrinks forever is worth. The probe on refresh 15 puts the median valued Decline
  row at 0.66 of its no-growth earnings value (EPV) as built and at 0.73 under the fade; the
  well-above count moves from 67 of 76 to about 63.
- A growth row whose history cannot give a sales-to-capital, or whose loss is larger than its
  revenue, is valued on the method's own fallbacks instead of refused. The probe values 26 of the 63
  refused rows under the two rules (22 well above, 2 above, 2 near): CRSP 41.92 at a price of 51.77,
  ZYME 27.30 at 30.94, VRDN 26.01 at 29.05. Two valued rows move (NEO, TWST).
- A company that made money in 5 of the 11 years on file is treated as established on a loss
  year, and a profitable company is never a Start-up. Seven rows move: TTWO to Mature Growth;
  SLAB, SYNA and AXTI to Mature Stable; AVAV and NBIS from High Growth to Mature Growth; KYIV from
  Start-up to rule 5 by its growth word.
- The margin-direction check fires on about 272 rows (17%) instead of 744 (46%).
- No admitted company refuses for a missing tax row while its country is in the OECD series.
- At the defaults, every row the changes do not touch, directly or through its mature peers, keeps
  its value, levels, designation, flags and refusal bit for bit. The seven rows the classifier moves
  count as mature peers from then on, and a foreign peer in a country the tax table gains gets a
  ROIC, so a growth, Decline or Start-up row that reads those peers can move; the readout names each
  such row. Holding the peers' classification at 0.8 would mean two classifiers, so the spillover is
  accepted. *My call*, from the builder check.

## 3. Non-goals

- No change to r, g_T, the moat table, the charge, the fade of the mature route, the base rates, the
  designation edges or the levels.
- No change to the Decline route's margin (the five-year median stays), its capital release, its
  distress weighting, its NCAV floor or its signals. Holding the trailing margin when it is above
  the median was tested and lifts the cyclicals at peak margins (TTE 61 → 77); it is not adopted.
- No calendar age bound on the phases. Celldex, Plug Power, Insmed and NovaGold are 27 to 40 years
  old and have never made money; they are economically what the phase says, and no other route can
  value a company without earnings. An age bound would only turn their figures into refusals.
- No reading of more than the 11 fiscal years the store holds. Reading 30 years would catch
  Ambarella (9 profitable of 17) but also QXO, whose history is a shell's.
- The growth routes' target margin and the peers stay as built. The 37 rows still refused after the
  two rules need a margin far above the peers' median (VRNS 56%, IRTC 42%, CRWV 24%); the drawer
  already shows that figure.
- No new setting on the Settings view. The two new policy values are calibration constants, marked
  "no" in the Setting column of method 4.1, as `marginal_capital_growth_min` is.
- Foreign filers (B-28) are the plan after this one.

## 4. Anti-goals

- A Decline row valued as a growing business. The consensus is read where it reaches; nothing
  grows past it, and the terminal has no growth.
- A growth row valued on a sales-to-capital the company never showed. The bound replaces an absurd
  own measure with the peers' median; it never invents one where neither exists.
- A classifier that reads the calendar. The established test reads profits.
- Any loss of a stored figure. Every change is a method version bump; the snapshots valued under
  0.8 stay as they are, and the revalue writes new ones.

## 5. The evidence (refresh 15, 2026-11-05, method 0.8: 1,602 companies, 1,176 valued)

The probes rebuilt every row's stored value from its intermediates to 1e-15 before changing a
rule, so the figures below are the engine's own. The scripts are in the session's scratchpad, not
the repo.

**Decline (109 rows, 76 valued, 17 refused for their value, 16 foreign or without a share
count).** The median valued row is worth 0.66 of its EPV; the market pays 1.6 × EPV for those rows
and 1.93 × EPV for Mature Stable rows, whose value is EPV at the floor. So of the median price ÷
value of 2.48, the run-off's own haircut is a third and the rest is the no-growth-at-9% gap every
mature row carries.

| Path | value ÷ EPV | price ÷ value | well above (of 76) | BBY (101) | TTE (90) | AAP (51) |
|---|---|---|---|---|---|---|
| as built | 0.66 | 2.48 | 67 | 53 | 61 | 19 |
| the rate fades to zero by year 10, flat terminal | 0.73 | 2.24 | 63 | 65 | 71 | 12 |
| the consensus's year-3 rate fades to zero | 0.76 | 1.99 | 54 | 71 | 75 | 7 |

AAP, DXC and GME move little under any path: their value is the capital release at a 2% margin
or the CCC rating's 59% default weight, so a gentler path lowers AAP. The 17 refused rows stay
refused under every path: ten are rated D on a zero or negative normalized margin (INTC, KMX,
LUMN, VTRS, XRAY, PTON, MSTR, PPLI, ILMN, ECHO), seven are debt-heavy (WHR, SMG, PBI, NWL, HAS,
DK, CLF). 41 of the 109 rows have a revenue consensus on at least 5 analysts for four or five
future fiscal years; BBY's runs to FY2030 at about +2% a year.

**Growth (63 refused: 40 High Growth, 23 Young Growth).** 50 are a reinvestment that outruns the
terminal, 9 have a target margin at or below zero because the mature peers lose money (ASAN, BBIO,
BRZE, COMP, FIG, FROG, IONS, SAIL, ASTS), 4 carry debt above the firm value. 29 have a trailing
margin below −100%. Own sales-to-capital below half the peers' median among the refused: 16 rows.

| Rule | valued of 63 | not well above |
|---|---|---|
| as built | 0 | 0 |
| the own sales-to-capital usable only at half the peers' median or more | 6 | 0 |
| operating income in dollars when the margin is below −100% | 14 | 1 |
| both | 26 | 4 |
| both, with the dollar ramp for every row | 34 | 6, and every valued growth row moves |

**The classifier.** Of the 49 Young Growth rows, 24 have no profitable year in the 11 on file and
17 have 15 or more years of statements at FMP (fetched 2026-11-06 at a limit of 40 years, kept in
the scratchpad). Of the 45 Start-up rows, one has a positive operating margin in 3 of the last 5
fiscal years (KYIV). The wider established test moves 6 rows, the Start-up rule 1.

**The margin-direction check.** By (direction, phase) as built: Stable on Mature Growth 308,
Declining on Mature Stable 192, Declining on Mature Growth 150, Rising on Mature Stable 67, Stable
on Decline 14, Rising on Decline 11, two on Start-up rows. With Stable pointing nowhere and the
deciles at 9 and 2: Declining on Mature Stable 137, on Mature Growth 90, Rising on Mature Stable 36,
on Decline 8, one on a Start-up row: 272.

**The tax table.** The OECD dataflow `DSD_TAX_CIT@DF_CIT` (measure `CIT_C`, sector `S13`,
targeting `ST`) has the combined rate for 146 jurisdictions, 2014 to 2026. Of the 32 countries
without a row, 30 are in it; Taiwan and Cyprus are not. Only 4 rows refuse for a tax rate today
because the foreign-filer refusal comes first; B-28 would expose all 125.

## 6. The Decline route

### 6.1 The revenue path

Year 0 is trailing revenue. Years 1 to 3 are read as today (method 6a.2): year 1 the NTM
consensus revenue, years 2 and 3 the annual consensus steps from the base year, a missing step held
with `path-held`, a thin step flagged `few-analysts`.

**Past year 3.** The path keeps reading the annual consensus revenue, one fiscal year at a time
from base + 3, while the year has a revenue mean above zero and at least `analyst_min` revenue
analysts. The first year that fails either test ends the consensus; nothing is held past year 3,
and a thin year is not read, so `few-analysts` never fires past year 3. K is the last year the
consensus gives, 3 at least and `runoff_years` at most. A step at or below −100% in any consensus
year refuses the row "consensus revenue falls to zero or below within the path", as today.

**The fade.** From year K + 1 the rate falls in a straight line from the decline rate d to zero by
year N:

    g_t = d × (N − t) ÷ (N − K), for t = K + 1 … N

so g_N = 0 exactly. d is 6a.2's: the five-year revenue slope ÷ the last fiscal year's revenue, at
most zero, floored at −50% with `decline-rate-floored`. With K = 3 and N = 10, g_4 = d × 6 ÷ 7 and
the path reaches zero in seven steps.

**No usable consensus** (`path-on-trend`): years 1 to 3 shrink at d, then the fade from year 4 as
with K = 3. The sentence: "No usable consensus: years 1 to 3 shrink at the decline rate, <d>, which
fades to zero by year <N>."

`consensus-recovery` names every consensus year, 1 to K, whose rate is above zero, as today it
names years 1 to 3.

### 6.2 The terminal

The run-off ends in a business of year N's size that neither grows nor shrinks:

    revenue_{N+1} = revenue_N
    NOPAT_{N+1}   = revenue_N × m_n × (1 − tax rate) when m_n is above zero, else revenue_N × m_n
    FCFF_{N+1}    = NOPAT_{N+1}
    terminal value_N = FCFF_{N+1} ÷ r

No capital is released in the terminal (revenue is flat) and none reinvested (no growth). Everything
else in 6a.3 to 6a.8 stands: the normalized margin, the tax carry, the capital release and
reinvestment in years 1 to N, the bridge to equity, the NCAV floor, the distress weighting, the
signals.

### 6.3 What moves with the price

The implied decline rate is the d at which the value a share, rebuilt from the rebuild keys with the
consensus years as found and the fade from the trial d, equals the price. The scan is 6a.9's, from
−50% to 0 in steps of 0.1%, the first root; none when the scan finds no sign change. The expected
return's growth term reads the path's own rates for years 2 to H + 1 and zero past year N, where
today it reads d past year N.

### 6.4 Intermediates, inputs and the drawer

`runoff_path` carries `revenue0`, `ntm_revenue`, `steps` (the consensus steps for years 2 to K as
found, `None` for a held one in years 2 and 3), `consensus_years` (K), `d` and `runoff_years`.
`growth_rates` carries years 1 to N as before. The tagged inputs add one DATA input per consensus
year past year 3, `path_step_<t>`, cited as `path_step_2` and `path_step_3` are.

The drawer's path sentence names K and the fade: "Years 1 to 5 from the consensus; the decline rate
−4.0% fades to zero by year 10; flat after." The Methodology page's Decline section says the same
in its words, and its MMM example is re-read after the revalue.

## 7. The growth routes

### 7.1 The own sales-to-capital bound

Method 5a.5 step 1 gains one condition. The company's own five-year marginal measure is usable when
capital grew, by at least `marginal_capital_growth_min` of the first year's capital in size, revenue
grew, and the measure is at least `own_sales_to_capital_min_share` (0.5) × the mature peers' median
of step 2, when that median exists. With no peers' median (fewer than `peer_min` positive peer
measures) the own measure stands on the first two conditions, as today. A measure below the bound
is not usable and the peers' median is used.

The record (`sales_to_capital`: used, own, own_usable, peers, value) is unchanged in shape. The DATA
input's note says why the peers' median was used: "the mature peers' median; the own measure, 0.01,
is below half the peers' median, 1.45". The Decline route's own-latest measure (6a.4) and the
Start-up route are not touched.

### 7.2 The loss larger than revenue

Method 5a.4's margin path stands for a trailing margin m_0 at or above `loss_ramp_margin_bound`
(−1.0). Below it the loss is a cost base, not a margin: the trailing operating income moves in
dollars, in a straight line, to the target margin's share of revenue in the convergence year, as the
Start-up ramp of 6b.2 does:

    E_0    = trailing operating income (= m_0 × revenue_0)
    E_t    = E_0 + (m* × revenue_C − E_0) × t ÷ C, for t = 1 … C
    EBIT_t = E_t for t ≤ C, and m* × revenue_t for t > C

with C = `margin_convergence_year`. When C is past N (the explicit period), revenue_C is not on the
path and the ramp's end is m* × revenue_N at year C, so the margin at year N is below the target,
as the margin path's is. *My call.* The year's margin is EBIT_t ÷ revenue_t and `margin_path.by_year`
carries it; `margin_path` adds `ramp`, "margin" or "dollars". Tax, the carry, NOPAT, reinvestment,
the terminal and the bridge are 5a.5 to 5a.9's on these EBITs, and the terminal NOPAT reads EBIT_N
at the full rate as today. `tax-loss-history-unknown` fires as today.

A new note flag, `margin-ramp-in-dollars`: "The trailing loss is larger than revenue (margin
−290.6%), so operating income moves in dollars from −223.5 million to the target margin's 494.6
million by year 10, as the Start-up ramp does."

The margin the price needs (5a.10) and the value by target margin (5a.11) rebuild the same ramp from
each trial margin, with the terminal return re-read as today. The implied growth rebuilds the ramp
from the trial path's revenue_C. The rebuild keys are unchanged: `margin_start` and `revenue_path`
give E_0 and revenue_C.

### 7.3 Young Growth, flags and inputs

Young Growth is the same route and takes both rules. The flag order of 5a.13 puts
`margin-ramp-in-dollars` after `tax-loss-history-unknown`. The RULE inputs add
`own_sales_to_capital_min_share` on a row whose own measure the bound rejected, and
`loss_ramp_margin_bound` on a row on the dollar ramp.

## 8. The classifier

### 8.1 The established company

Method 3.5: a company is established when at least three of the last five fiscal years on file have
an operating margin above zero, **or at least five of the fiscal years on file do** (the series of
3.1, eleven years at most). A year without a margin counts for nothing in both counts. The second
count is a structural constant of 4.1a, beside the three of five.

The `loss-year` sentence names both counts: "The operating margin of fiscal 2025 is below zero;
the margin was above zero in 1 of the last 5 fiscal years and in 6 of the 11 on file, so the
company is established and takes the growth word's phase."

### 8.2 An established company is never a Start-up

Method 3.5 rule 1 becomes: a Start-up (3.2) that is not established is **Start-up**. An established
company whose revenue was zero three years ago falls through to rules 2 to 5 on its series, which
3.2's longest run of positive revenues already measures. A new note flag, `revenue-gap`, says why:
"Revenue was zero in fiscal 2022, but the margin was above zero in 3 of the last 5 fiscal years, so
the company is not a Start-up." A company with zero revenue now that is not established stays a
Start-up, as today: a reported zero is a Start-up, and only a missing last revenue is unclassified by
3.8. An established company with zero revenue now, say one that sold its business after four
profitable years, leaves rule 1 and is unclassified by 3.8, "no measurable revenue growth", since no
positive run ends at the last year; `revenue-gap` is not raised on an unclassified row. *My call*,
from the builder check.

### 8.3 The margin-direction check

Method 3.4: Rising is decile 9 or higher with a slope above zero; Declining is decile 2 or lower
with a slope below zero; otherwise Stable. Method 3.6: the check fires when Rising on a row that is
not Mature Growth or Declining on a row that is not Decline. Stable points nowhere and never fires.
The sentence is unchanged for the two directions. The deciles 9 and 2 replace 8 and 3 in 4.1a.

### 8.4 Everything else

Rules 2, 3, 4b and 5, the growth word, the checks of 3.6 other than the margin direction, the
Dickinson stage and 3.8 stand. The deciles are computed as today; the margin-direction change reads
the stored edges differently and needs no new deciles.

## 9. The Mature Stable refusal

A Mature Stable row refused "no positive trailing earnings" (method 6.1) keeps, beside the price
facts every result carries, `eps`, `nri_gap`, `e_trailing` and `growth_route`, the cross-check of
6.4 with its value a share or its reason, and its rebuild keys. A price refresh moves the
cross-check's implied growth on such a refusal as it does on a valued stable row. The drawer shows
the cross-check on the refusal where it shows it on a valued row, with the refusal's sentence above.
The Mature Growth route's refusals are not touched.

## 10. The tax table

`tax-rates-oecd-v2.toml` replaces v1 as the table the loader reads; v1 stays in the package, since
the inputs of the snapshots valued under 0.8 and earlier cite it. v2 holds, for every jurisdiction
the OECD series gives the combined rate (`CIT_C`, `S13`, `ST`), every year from 2014 to the newest,
as v1 holds its 16, and an alias from the ISO 3166-1 alpha-2 code to the OECD name for each. The
`[meta]` keeps the dataflow, the URL and the retrieval date. Two jurisdictions the series lacks are
written by hand with a source line each: Taiwan (20% from 2018, 17% from 2010 to 2017; the Income
Tax Act, article 5, Ministry of Finance) and Cyprus (12.5% through 2025; the Tax Department). A
2026 rate for Cyprus goes in only with a government source for the enacted change; otherwise 2025's
rate is carried forward with `tax-carried-forward`, as 4.3 does for any later year. *My call.*
A country the series still lacks refuses as today.

The builder regenerates the file with a script kept outside the package (the repo's `scripts/` or
the scratchpad; *my call*: `scripts/build_tax_table.py`, committed, so the next retrieval is one
command), reading the series' CSV export. The payload is public data, not vendor data, and may be
committed as the TOML it produces; the CSV itself is not committed.

## 11. Policy v7

`fairband-policy-v7.toml` is v6 with two values, each with a source line; v6 stays in the package
unchanged. The engine loads v7 only. Neither is a setting; the Settings view and the settings hash
are unchanged, and spec 2026-11-04 8.2's catalogue is unchanged.

| Value | Policy name | Source |
|---|---|---|
| Own sales-to-capital bound: at least 0.5 × the mature peers' median | `own_sales_to_capital_min_share` | Damodaran H13, H14 (the industry sales-to-capital serves where the company's own history cannot); no source gives the number; founder decision 2026-11-06 |
| Loss ramp bound: a trailing margin below −100% | `loss_ramp_margin_bound` | spec 2026-11-03 9.2 (the Start-up ramp moves operating income in dollars); no source gives the number; founder decision 2026-11-06 |

The structural constants of method 4.1a change: the margin-direction deciles 9 and 2 (were 8 and
3), and the established company's five profitable years on file beside its three of the last five.

## 12. The method document, the Methodology page and the drawer

`docs/method.md` changes in the same commits as the code, section by section as section 1 lists,
with a 0.9 row in section 11 and the new flags in section 8 (`margin-ramp-in-dollars` and
`revenue-gap`, both notes). Section 9 keeps every refusal. The Methodology page changes with it: the
Decline, High Growth, Young Growth and classifier sections, the flags list, and the six examples'
figures re-read after the revalue (CLAUDE.md: a change of method version re-reads its examples'
figures). The drawer: the Decline path sentence (6.4), the dollar-ramp sentence on a growth row, the
cross-check on a Mature Stable refusal (9), the loss-year and revenue-gap sentences.

## 13. Worked numbers for the tests

To 1e-9 a share unless a tolerance is named, on the same figures as method 6a.12 and 5a.15.

### 13.1 The Decline row

Trailing revenue 1,000 and operating income 80; fiscal margins 7%, 8%, 8%, 9%, 8% (m_n 8%); tax
25%; own sales-to-capital 2.0; the consensus −3% in years 1 to 3; d = −4%; r 9%; debt 200, cash 100,
100 shares; trailing interest 20 (coverage 4.0, A−, π 5%); current assets 300 and total liabilities
500 (NCAV −200, no floor).

- K = 3. Rates, years 1 to 10: −3%, −3%, −3%, −3.428571%, −2.857143%, −2.285714%, −1.714286%,
  −1.142857%, −0.571429%, 0.
- Revenue 970.00 in year 1 and 808.24 in year 10; free cash flow 67.20 and 48.49; FCFF_11 48.49
  (no release); terminal value 538.83; firm value 607.48.
- Going concern 5.0748 a share; distress-sale value (0.6 × 607.48 + 100 − 200) ÷ 100 = 2.6449;
  value 5.0748 × 0.95 + 2.6449 × 0.05 = 4.9533 (method 0.8 gives 4.3180 on the same figures).
- The consensus reaching year 5 (base + 3 at +1% on 6 analysts, base + 4 at +2% on 6, base + 5
  absent): K = 5; rates −3%, −3%, −3%, 1%, 2%, −3.2%, −2.4%, −1.6%, −0.8%, 0; revenue 940.24 in year
  5 and 867.10 in year 10; FCFF_11 52.03; terminal value 578.07; firm value 622.19; value 5.0974.
  `consensus-recovery` names years 4 and 5. With base + 3 on 4 analysts, K = 3 and the row is
  4.9533 with no `few-analysts` for year 4.
- No usable consensus: years 1 to 3 at −4%, then the fade; value 4.8626, `path-on-trend`.
- Value at d = 0: 5.2247; at d = −50%: 3.1251. At a price of 4.9533 the implied decline rate is
  −4% (within 1e-4); at a price of 3.00 it is none, since the value at −50% is above the price.
- The variants of 6a.12 (cash 250, no interest expense, no debt line, current assets 1,100, the
  chronic loss-maker) are re-pinned on the new path by the builder; the rules that produce them are
  unchanged.

### 13.2 The growth row on the dollar ramp

The 5a.15 figures (r 9%, g_T 3%, tax 21%, None moat, trailing revenue 1,000, NTM 1,300, steps 25%
and 20%, target margin 20%, sales-to-capital 2.0, debt 100, cash 300, 100 shares) with a trailing
margin of −150% (operating income −1,500), below the bound:

- EBIT by year: −1,260.80; −1,021.60; −782.41; −543.21; −304.01; −64.81; 174.38; 413.58; 652.78;
  891.98. The implied margins run from −97.0% in year 1 to 20% in year 10.
- The carried loss shields every year through year 10 (NOPAT_10 = 891.98, untaxed); the terminal
  NOPAT is 891.98 × 0.79 = 704.66 as in 5a.15. Free cash flow −1,423.30 in year 1 and 657.09 in year
  10; terminal value 8,064.46; firm value −31.33; equity 168.67; value a share 1.6867. The margin
  path from −150% would give −61.94.
- At a price of 25.00 the margin the price needs is 0.277164, within 1e-5.
- At a trailing margin of −10% (5a.15's own figure) nothing changes: 34.91 a share, `ramp` "margin".

### 13.3 The own sales-to-capital bound

Own measure 0.5, usable on the two existing tests, with a peers' median of 2.5: not usable (below
1.25), the peers' median used, the note naming both figures. Own 1.3: usable. Own 0.5 with no peers'
median: usable. The peers' median 1.447 and own 0.941 of RKLB (refresh 15): usable.

### 13.4 The classifier

- Margins over 11 fiscal years, oldest first, +, +, +, +, +, +, −, −, −, −, −: 6 on file, 0 of the
  last 5; established, `loss-year` naming both counts; rule 5 by the growth word.
- +, +, +, +, −, −, −, −, −, −, −: 4 on file; not established; rule 4b.
- A four-year series with revenue 0, 100, 120, 150 and margins none, +, +, +: revenue zero three
  years ago, 3 of the last 5 positive; not a Start-up; `revenue-gap`; rule 5 on the growth of the
  three-year run, with `short-history`.
- Revenue 0 in the last year after four years with margins +, +, +, +: established, not a Start-up,
  unclassified "no measurable revenue growth". The same with the earlier margins −, −, −, −: a
  Start-up, as today (SUCO's golden stands).
- A margin slope at decile 9 and above zero: Rising; at decile 8: Stable, no flag; at decile 2 and
  below zero: Declining; at decile 3: Stable. Rising on a Mature Stable row fires; Stable on a
  Mature Growth row does not.

### 13.5 The Mature Stable refusal

A row with negative trailing net income and a positive anchor: the refusal "no positive trailing
earnings" with `growth_route.value_per_share` set and its implied growth at the price; a reprice
moves the implied growth. The same row without an anchor: the refusal with `growth_route.refusal`
only.

### 13.6 The tax table

Every v1 row is in v2 with the same rate. Greece 2024 is 22%, Sweden 20.6%, Italy 27.81%, India
25.17%, Hong Kong 16.5%, Belgium 25% (2024), the Bahamas and Guernsey 0%, the UAE 9%, China 25%,
Taiwan 20% (2018 on) and 17% (2014 to 2017), Cyprus 12.5%. `GR`, `TW` and `CY` resolve through the
aliases. The United States' 2025 rate is 25.569714%, as v1 has it.

## 14. Tests the builder must write

- `runoff.py`: the rates with K = 3 and K = 5, the flat terminal, the value at d = 0 and at the
  floor; `runoff_rates` with K past N refuses (K is at most N).
- `route_decline.py`: 13.1 in full; the consensus past year 3 stopping at the first thin or
  missing year; the `consensus-recovery` sentence naming years 4 and 5; `path-on-trend`'s new
  sentence; the implied decline rate on the fade; the reprice rebuilding the same path; every
  6a.12 variant re-pinned.
- `revenue_growth.py` and `route_revenue_growth.py`: 13.2 and 13.3; the ramp with C past N; the
  flag order; the RULE inputs; the margin the price needs and the value by margin on the ramp; a
  reprice rebuilding the ramp; Young Growth's equality with High Growth on the ramp.
- `classifier.py`: 13.4; the `loss-year` and `revenue-gap` sentences; the deciles 9 and 2; the
  check silent on Stable.
- `route_mature_stable.py`: 13.5.
- `policy`: v7 loads, the two values with their sources, v6 byte-identical under its hash.
- `tax.py`: 13.6; the alias of every jurisdiction in v2; v1 still loads for provenance.
- The goldens (`tests/fixtures/golden`): DCCO, HGCO and YGCO re-captured under 0.9 with a note in
  the README naming the sections that moved them; MGCO, MSCO and SUCO unchanged bit for bit, which
  the test asserts. MGCO's margin slope sits in decile 8 of the test universe's edges and reads
  Rising today; the builder shifts the test edges so it stays Rising at decile 9, keeping the
  fixture's intent, rather than re-capturing MGCO.
- `web`: the drawer's Decline path sentence, the dollar-ramp sentence, the cross-check on a Mature
  Stable refusal; the Methodology page's text for the five changes.

## 15. Acceptance and the readout

After the merge, a backup of the live database, the server restarted from main, and one revalue.
The readout, on the same shape as the 2026-11-04 readouts:

- Decline: the valued count, the designations, the median price ÷ value and value ÷ EPV (expected
  about 0.73 and 2.2), the rows whose K is past 3, BBY, TTE and AAP.
- Growth: the refused count for "value not positive" (expected 37 of 63), the rows now valued with
  their designations, the rows on the dollar ramp, the rows whose own measure the bound rejected.
- The classifier: the seven moves; the rows that moved through their peers (a growth, Decline or
  Start-up row whose counted peers now include one of the seven, or whose peers' ROIC median gained
  a foreign peer from a country v2 covers), each named with the figure that moved; the
  `margin-direction-disagrees` count (expected about 272); `loss-year` and `revenue-gap` counts.
- The tax table: no "no statutory tax rate" refusal for a country in v2.
- Every row not named above: value, levels, designation, flags and refusal bit for bit as refresh
  15, which the readout checks over the whole universe. A probe before the revalue lists the rows
  that carry one of the seven as a counted peer, or a foreign peer in a v2 country, so the readout
  tells spillover from a defect.

## 16. Left to the builder

- Where the consensus years past 3 are read: `revenue_path_for` reads base + 1 and base + 2
  today; a reader for base + 3 onward belongs in `revenue_growth.py` or `route_decline.py` as the
  builder sees fit, on the same fiscal-year derivation.
- The shape of `_Consensus` and `runoff_rates` with K; the reprice of a Decline row from the new
  `runoff_path`.
- The ramp in `revenue_growth.py` (`margins_by_year` or a sibling that returns EBITs); the Start-up
  route's `ramp_ev` is the reference, not shared code, unless sharing is clean.
- The regeneration script's shape and the v2 file's layout, within section 10.
- The drawer's exact sentences, in the page's register.
- The test universe's margin-slope edges, so MGCO's golden stands (14).

## 17. Order of work

1. Policy v7 and the 0.9 rows of `docs/method.md` (4.1, 4.1a, 11); the goldens' baseline check.
2. The classifier (8) and the Mature Stable refusal (9); method 3.4, 3.5, 3.6, 6.1, 6.4, 8.
3. The growth routes (7); method 5a.4, 5a.5, 5a.10, 5a.13, 5a.14.
4. The Decline route (6); method 6a.2, 6a.5, 6a.9, 6a.10.
5. The tax table (10); method 2, 4.3.
6. The drawer and the Methodology page (12); the goldens re-captured.
7. Backup, merge, revalue, the examples' figures re-read, the readout (15).

## 18. Sources

| Rule | Source |
|---|---|
| The decline runs its course and the firm stabilizes at a smaller size; a flat terminal | Damodaran, "Valuing Distressed and Declining Companies" (2009): a declining firm's revenues fall and then level off; *The Corporate Life Cycle* ch. 2 (decline is not death) |
| The consensus read where it reaches, on `analyst_min` analysts | stocks method v1.7 section 3 (a year with fewer than 5 analysts is not data); method 5a.2 |
| The industry sales-to-capital where the company's own history cannot give one | Damodaran H13, H14; design.md 6.2, D3c |
| A loss larger than revenue moves in dollars | the Start-up ramp, spec 2026-11-03 9.2; Damodaran 2009, "Valuing Young, Start-up and Growth Companies" (operating losses in dollars on a pre-revenue firm) |
| The established company on its profit record, not its age | Damodaran, *The Corporate Life Cycle* ch. 3 (the phases marked by the direction of the numbers); spec 2026-11-03 6.2 |
| Stable margins point to no phase | design.md 5.4 (a direction is a decile of the slope; the middle deciles are no direction) |
| The OECD combined statutory rate | research.md D9; OECD Corporate Tax Statistics, Table II.1 |

## Decision log

| Date | Decision |
|---|---|
| 2026-11-06 | The next set: the engine round (B-1, B-7, B-74, B-27), then B-28 foreign filers, then the page after a refresh (B-68, B-47, B-32, B-31), then Tier 2 over MCP. Founder: "go". |
| 2026-11-06 | Decline: the rate fades to zero by year 10 with a flat terminal, and the consensus is read past year 3 on 5 analysts or more. Claude's recommendation on the probe; the founder agreed. The alternative, the consensus's year-3 rate fading to zero, was shown and not chosen. |
| 2026-11-06 | Growth: the own sales-to-capital bound at half the peers' median and the dollar ramp below −100%, both as policy values that are not settings. Claude's recommendation; the founder agreed. The dollar ramp for every row was shown and not chosen. |
| 2026-11-06 | Margin direction: Stable points nowhere and the deciles move to 9 and 2. Claude's recommendation; the founder agreed over 10 and 1. |
| 2026-11-06 | Tax rows: the table regenerated for every jurisdiction in the series, Taiwan and Cyprus by hand. Claude's call, stated to the founder. |
| 2026-11-06 | The classifier: no calendar age bound; established on 5 profitable years of the 11 on file beside 3 of the last 5; an established company is never a Start-up; the Mature Stable refusal keeps the growth cross-check. Founder, after the age table: "agreed, add it to the engine round". |
| 2026-11-06 | Builder check done. Two questions, both settled by Claude: the classifier's moves and the tax rows reach rows through their mature peers, and the spillover is accepted and named in the readout (2, 15); a non-established company with zero revenue now stays a Start-up, an established one is unclassified "no measurable revenue growth" (8.2, 13.4). One note taken into 14: the test deciles shift so MGCO's golden stands. Nothing for the founder. |
| 2026-11-06 | The goldens are re-captured when only their JSON's shape moves (the phase evidence's second count, `margin_path.ramp`, `sales_to_capital.own_below_bound`) and for DCCO's lost `margin-direction-disagrees`, since Stable now points nowhere (8.3); the golden README names each cause. Their figures stand, so 14's "unchanged bit for bit" holds for the figures, not the JSON; DCCO's figures move with the fade, as 14 says. Claude, during the build. |
| 2026-11-06 | The phase evidence carries both counts of the established test, `positive_years_last_five` beside `positive_years_on_file`, so the drawer and the `loss-year` and `revenue-gap` sentences can name both (8.1). Claude, during the build. |
| 2026-11-06 | A year past year 3 whose consensus revenue mean is not above zero ends the consensus at the year before, with no refusal, as 6.1 reads; the plan's test, which refused the row, gave way to the spec. Claude, during the build. |
| 2026-11-06 | Belgium's statutory rate is 25%, the OECD series' combined rate (`CIT_C`, `S13`, `ST`); the 20% 13.6 first gave was the small-business row. 13.6 is corrected and the test pins 0.25. Claude, during the build. |
| 2026-11-06 | The formatters `millions` and `signed` moved to `route_steps`, so the growth route's dollar-ramp note can use them without a circular import. Claude, during the build. |
| 2026-11-06 | The readout's revalue ran on a scratch copy of the live database, made with SQLite's backup API, before the merge; the live backup, the live revalue and the server restart wait for the final review and the founder's consent. A revalue is deterministic on the stored facts and deciles, so the copy's figures are the live ones. Claude, during the build. |
| 2026-11-06 | The readout (the revalue of refresh 15 under 0.9 and v7): 1,220 of 1,602 valued (1,176 under 0.8). Exactly the seven rows of 8 change phase. Decline: 76 valued, median value ÷ EPV 0.66 → 0.73, well above 67 → 63; 22 rows read the consensus past year 3. Growth: refused for the charge 63 → 37, 26 of the 63 valued, 29 rows on the dollar ramp, 27 past the bound. `margin-direction-disagrees` 744 → 272. Tax refusals 22 → 1, none for a country v2 covers. No row outside the named sets moved through the engine round; 7 fetch-failed rows of refresh 15 read "no financial statements" after any revalue, 0.8's too. Claude, during the build. |
