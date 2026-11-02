# The High Growth and Young Growth routes, and four screen fixes: design

Status: approved by the founder on 2026-11-02, after a brainstorm. The decisions in the log at the
end are the founder's. Items marked *my call* were settled by Claude while writing and can be
overturned. Builder check done 2026-11-02: its two questions are settled in 5.3 and 5.11.

This document amends `docs/method.md` (the method as built) for two new routes, and
`docs/legacy/design.md` sections 6.9 and 6.10 where it says so. The mechanical screen spec and the
calibration spec stand for everything it does not mention. When the routes are built, their
sections go into `docs/method.md` in the same commit, and that document stays the statement of
what runs.

## 1. What this is

The screen values 1,052 of its 1,759 rows. Of the rest, 110 rows are High Growth and 56 Young
Growth: companies with a negative operating margin, improving or worsening, that get a phase and
the refusal "route not built yet". This piece builds the one route both phases share, Damodaran's
revenue DCF: revenue from the consensus, margins converging to a target taken from mature peers,
reinvestment from sales-to-capital, a flat required return, the terminal return rule the mature
routes already use. Young Growth differs from High Growth only in what it adds on top, and in this
piece it adds a flag.

Four fixes to the page ride along, from the founder's hand check of 2026-11-02: the status line
under the header, the FIND field's focus ring, the menus' closing behaviour, and a clear control
on FIND. A universe fix rides along too: notes and preferred shares that pass the symbol rule.

## 2. Goals

- A value, the levels and a stance for a High Growth or Young Growth row whose consensus, target
  margin and sales-to-capital exist, defensible line by line from Damodaran's template, with the
  sources in the policy file.
- A row that cannot be valued says which input is missing, and still shows the margin the price
  needs when the path exists.
- Every mature-route convention that applies carries over unchanged: trailing figures, one share
  count, the statutory tax rate, invested capital, the terminal return rule, the levels, the
  flags, the validity window.
- The same inputs under the same policy version give the same result, bit for bit.
- The page's four defects fixed within the design system's rules.

## 3. Non-goals

- The value range (10th, 50th, 90th percentiles) for Young Growth. Tier 1 shows one value; the
  range comes with tier 2, where an agent sets the driver distributions with a reason. No source
  gives the widths.
- The failure probability. Tier 1 reports it as unavailable with the reason (section 5.13); a
  source that fits listed companies above $2 billion is a research item for later.
- A year-specific cost of capital. Tier 1 discounts at the flat required return (5.9); the path
  is a tier-2 judgment.
- The company's own published margin target (design.md 6.7 rule 1). No tier-1 source carries it.
- The Decline and Start-up routes. Decline is the next piece.
- Industry filtering, the failed-count button, saved filters, settings. Unchanged non-goals of the
  screen-controls spec.

## 4. Anti-goals

- A number no source gives, dressed as a rule. Every constant is a policy value with a source
  line or an explicit "no source".
- Growth made free. Reinvestment is charged in every explicit year and in the terminal.
- A value shown where an input is missing. A missing target margin or sales-to-capital is a
  refusal, never a default the literature does not give.
- A different structure for the two phases. One route, one code path.
- A glyph for a control, or a hard-coded colour, size or radius on the page.

## 5. The route

Notation as in `docs/method.md`: r = 9%, g_T = 3%. The explicit period is N = 10 years: five
of high growth, five of transition.

### 5.1 Which rows

A company the classifier puts in High Growth or Young Growth (method.md 3.5, rule 4), after the
common guards of method.md 5.1. The two phases run the same route; the result's route name is
`revenue-growth`, and the phase says which it was.

### 5.2 Refusals

In this order, after the common guards: no trailing revenue (missing or not positive); no
statutory tax rate; incomplete NTM consensus (5.3); no target margin, "no target margin: <n>
mature peers" (5.5); no sales-to-capital (5.6); a value a share at or below zero, "value not
positive under the reinvestment charge". A row refused for the target margin still carries the
path, the sales-to-capital and the margin the price needs (5.11) in its intermediates, and the
screen shows that margin.

### 5.3 The revenue path, years 1 to 3

Year 0 is trailing revenue. Year 1 is the NTM consensus revenue: the sum of the revenue means of
the four quarterly consensus periods the anchor rule picks (method.md 5.2: the first four ending
after the trailing period end, consecutive). Without four such quarters each with a revenue mean,
the row is refused "incomplete NTM consensus" (*my call*: the same window and the same refusal
as the earnings anchor, so the two routes read the consensus the same way).

Years 2 and 3 grow at the annual consensus revenue steps from the base year (the fiscal year
holding most of the four quarters, a tie taking the later): g_2 = revenue(base + 1) ÷
revenue(base) − 1, g_3 = revenue(base + 2) ÷ revenue(base + 1) − 1. A step is missing when either
year has no revenue mean (a mean of zero with no analyst count, or a count of zero, is no
estimate) or the earlier is not positive. A missing step holds the last known rate, g_1 for g_2
and g_2 for g_3, and the row is flagged `path-held` (*my call*: there is no revenue base rate
to fall back on, and holding is the template's own device for years 4 and 5). A path year with
fewer than 5 analysts, or no count, flags `few-analysts`; the count is FMP's revenue analyst
count, which the store already holds beside the EPS count (*my call*, from the builder check:
the revenue count is the honest measure of a revenue step).

### 5.4 Years 4 to 10

Years 4 and 5 grow at g_3. Years 6 to 10 fade in five equal steps to g_T:

    g_t = g_3 − (g_3 − g_T) × (t − 5) ÷ 5, for t = 6 … 10, so g_10 = g_T.

When g_3 is below g_T the same formula rises to g_T. The five high-growth years are the policy
value `high_growth_years`; the fade reuses `fade_years`.

Source: Damodaran's template (H2: years 2 to 5 at one rate, years 6 to 10 stepping down to the
terminal rate); his warning against growth periods over ten years (H1); the split of the period
into a constant half and a transition half (H3). Founder decision 2026-11-02.

### 5.5 The margin path and the target margin

The operating margin moves in a straight line from the trailing margin m_0 to the target m* by
year 10:

    m_t = m_0 + (m* − m_0) × t ÷ 10, for t = 1 … 10.

The convergence year is the policy value `margin_convergence_year`, 10 (*my call*: Damodaran's
template default, and his Zomato case; a company already above the target moves down the same
line).

The target margin is design.md 6.7's peer default, rule 2: the FMP `stock-peers` list, kept to
the peers that are in the latest universe and that the classifier puts in Mature Growth or Mature
Stable on this refresh's deciles, from their stored statements (*my call*: classified on the spot
from the store, so the route needs no ordering of companies within the refresh). Each peer's
margin is its ten-year aggregate operating margin, Σ operating income ÷ Σ revenue over its last
ten fiscal years with both, at least `peer_margin_min_years` (5) of them. The target is the median
across those peers. Fewer than `peer_min` (3) peers: the row is refused "no target margin: <n>
mature peers", and shows the margin the price needs. The largest such peer's margin, by market
cap, is recorded as the success scenario (6.7 rule 4) and shown; it sets nothing.

The peers call is one FMP `stock-peers` per company per refresh, stored and reused like every
other call (24 hours). A failed peers call is not a required-endpoint failure; the row is refused
for the target margin with the count it has.

### 5.6 Sales-to-capital and reinvestment

Reinvestment in year t pays for year t + 1's revenue, the template's one-year lag:

    reinvestment_t = max(0, (revenue_{t+1} − revenue_t) ÷ sales-to-capital), for t = 1 … 9.

The floor at zero is H17's rule that reinvestment is never negative (the payout floor's analog).
Year 10 charges at the terminal return, as the mature routes' year N does:
reinvestment_10 = NOPAT_10 × g_T ÷ terminal return.

Sales-to-capital, in this order (founder decision 2026-11-02):

1. **The company's own five-year marginal measure**: (revenue_last − revenue_first) ÷
   (capital_last − capital_first), over the kept capital years of method.md 4.5 with "last" the
   newest and "first" the kept year `marginal_return_span_years` (5) positions earlier, capital
   the average invested capital, revenue the fiscal year's. Usable when capital grew, by at least
   `marginal_capital_growth_min` (a fifth) of the first year's capital in size, and revenue grew.
   It needs six kept years.
2. **The mature peers' median**, otherwise: each peer's last fiscal-year revenue ÷ its newest
   average invested capital (the level ratio Damodaran's industry figure is), the median across
   the same peers as 5.5, at least `peer_min` of them with a positive capital.
3. Neither: the row is refused "no sales-to-capital".

The row records which measure it used and both figures. Source: Damodaran, CLC ch. 11 ("the
company's data ... and the sector averages", H13), IV ch. 11 (the marginal measure, and Ashford.com
set between its own marginal ratio and the industry's, H14); D3c for the peer population.

### 5.7 Operating income, tax and NOPAT

EBIT_t = revenue_t × m_t. Tax is the statutory rate of method.md 4.3, the newest fiscal year's,
charged on taxable income after the forecast's own losses: a loss year adds to a carried loss, a
profit year uses the carried loss before it is taxed. The carried loss starts at zero, because no
history of tax losses is stored; a row whose forecast has a loss year is flagged
`tax-loss-history-unknown` (*my call*). NOPAT_t = EBIT_t − tax_t.

### 5.8 The free cash flow and the firm value

    FCFF_t = NOPAT_t − reinvestment_t, for t = 1 … 10
    terminal value = NOPAT_10 × (1 + g_T) × (1 − g_T ÷ terminal return) ÷ (r − g_T)
    firm value = Σ FCFF_t ÷ (1 + r)^t + terminal value ÷ (1 + r)^10

Negative free cash flow in the early years is the method, not a refusal.

The terminal return is method.md 4.7's rule with the chosen measure the return on new capital at
the target: m* × (1 − tax rate) × sales-to-capital. Wide moat: that return capped at 13% and never
below r; Narrow or None: r. Most of these rows have no moat score and take r.

### 5.9 The required return

Flat r = 9% in every year, the founder's hurdle. This departs from Damodaran's year-specific cost
of capital, which starts higher and falls to the mature level by year 10; his starting value comes
from a beta or from the market cross-section, which design rule 1 forbids. The 45% margin of
safety of a no-moat company carries the risk in tier 1, and the drawer says so on every row of
these routes. A tier-2 agent may set a path with a written reason. Founder decision 2026-11-02.

### 5.10 Equity and the value a share

    equity = firm value − (short-term debt + long-term debt) + (cash + short-term investments)

from the newest annual balance sheet, a missing line counting as nil and flagged
`line-not-presented:<field>` as the capital build flags one (*my call*). Lease liabilities stay
out: operating income is already after lease cost, so taking them off again would double count.
The value a share is equity ÷ the diluted share count. The levels and the stance follow
method.md 4.10 with the moat's margin of safety.

### 5.11 What moves with the price

- **Implied growth**: the rate held in years 4 and 5 at which the value equals the price, the
  fade of 5.4 recomputed from it, years 1 to 3 unchanged; solved as method.md 5.7 solves, between
  −50% and 200%, `None` when no rate in that range reaches the price.
- **The margin the price needs**: the target margin at which the value equals the price, the
  margin path of 5.5 recomputed from it and the terminal return (5.8) read from the return on new
  capital at the trial margin; solved between −50% and 100%. Computed on every row that has the
  path and the sales-to-capital, a row refused for the target margin included: it is that row's
  only figure, and design.md 6.4's "price-implied margin only" (*my call* on the bounds). On such
  a refused row the figure moves with the price too: the refusal keeps no route, and the price
  refresh recognises the row by the path and the sales-to-capital in its intermediates (*my
  call*, from the builder check; method.md section 10's "a refusal snapshot takes only the new
  price and date" gains this one exception).
- The multiples (no P/E for a negative EPS), the growth share of price when EPV exists, and the
  expected return: income from the trailing flows, growth from the revenue path's years 2 to 4,
  repricing from the value against the price, as method.md 5.10, with the drawer saying the
  growth term is revenue growth (*my call*).

A price refresh rebuilds all of these from the intermediates alone, as it does for the mature
routes.

### 5.12 Sensitivities, the cross-check and the implied-return check

- **By target margin**: the value at the lowest, the median and the highest mature-peer margin,
  keys `low`, `median`, `high`. The value-spread flag reads them, as it reads the mature route's
  three returns (*my call*).
- **The growth-route cross-check**: a row whose NTM EPS anchor is positive and whose earnings path
  has no refusal also carries the Mature Growth route's value as `growth_route`, exactly as a
  Mature Stable row does (calibration spec 5.7), with its implied growth at the price. A company
  about to turn profitable shows both readings (*my call*).
- **The implied-return check** (Damodaran H15): the return on new capital at the target,
  m* × (1 − tax) × sales-to-capital, against the mature peers' median ten-year aggregate ROIC.
  When above it, the row is flagged `return-above-peers` with both figures. Damodaran lowers the
  sales-to-capital by hand until the return converges; tier 1 flags only (*my call*).

### 5.13 Young Growth

The same route. The failure probability that design.md 6.9 applies to the value is reported as
unavailable: "no survival table fits a listed company above $2 billion" (the BLS tables measure
establishments, most of them tiny; D3d's own fallback when the mapping cannot be justified). The
value is the going-concern value, flagged `failure-not-charged`, and the drawer says the range is
not computed in tier 1. Founder decision 2026-11-02.

### 5.14 Flags

New: `path-held`, `tax-loss-history-unknown`, `return-above-peers`, `failure-not-charged`. Kept
from the mature routes where they read inputs these routes have: `few-analysts`, `value-spread`,
`sbc-basis-unknown` (the cross-check's anchor), the capital build's flags of method.md 4.4 and
4.5 (the sales-to-capital reads invested capital), the gate flags and `large-nri`, the assembly's
flags and the classifier's checks. The `margin-flag` needs a positive margin history and will
seldom fire. Order: the path's, the capital build's, `tax-loss-history-unknown`,
`return-above-peers`, `failure-not-charged`, the trailing flags, `value-spread`.

### 5.15 Intermediates and inputs

Intermediates: `ntm_revenue`, `path` (base year, analysts), `path_steps` (g_2, g_3, held flags),
`growth_rates` (years 1 to 10), `margin_path` (m_0, m*, the ten margins), `target_margin`
(value, the peers used with each one's margin and market cap, the median, the largest peer's),
`sales_to_capital` (used, own, own_usable, peers, value), `revenue_by_year`, `ebit_by_year`,
`tax_by_year`, `nopat_by_year`, `reinvestment_by_year`, `fcff_by_year`, `terminal_roic`,
`terminal_value`, `firm_value`, `debt`, `cash`, `equity`, `shares`, `value_per_share`,
`value_by_margin`, `return_on_new_capital`, `peer_roic_median`, `failure_probability`
(`None`, with its reason, Young Growth only), `eps`, `epv`, `dividend_yield`,
`net_buyback_yield`, `income_basis`, `price_facts`, `growth_route`; at the price,
`implied_growth`, `implied_margin`, `multiples`, `growth_share`, `expected_return`.

Inputs: the common DATA inputs of method.md 5.12; `ntm_revenue`, `path_step_2`, `path_step_3`
(estimates), `target_margin` (DATA, source "FMP stock-peers and the peers' statements", with the
peer count in its note), `sales_to_capital` (DATA, statements, with the measure in its note),
`debt`, `cash`. RULE: r, g_T, the moat class, the margin of safety, the terminal return,
`high_growth_years`, `fade_years`, `margin_convergence_year`, `peer_min`.

### 5.16 Versions

Method `fairband-mechanical/0.4`. Policy `fairband-policy-v3.toml` with section 7's values; v2
stays in the package for the snapshots that cite it. After the merge the founder's database needs
a full refresh, not a revalue: the peers are a new vendor call, and the 24-hour reuse covers the
rest. Until then a price refresh refuses every v2 snapshot with "policy changed: run a full
refresh", as it does today.

### 5.17 The universe: notes and preferred shares

A listing whose name matches one of `name_exclude_patterns` is recorded, not eligible, with the
reason "name pattern" (*my call*; the first full refresh's calibration counts them). The patterns,
matched ignoring case: `\bnotes?\b`, `\bdue 20\d\d\b`, `\d(\.\d+)?% `, `\bpreferred\b`,
`\bpreference\b`. ABXL, "Abacus Global Management, Inc. - 8.875% Fixed Rate Senior Notes due
2028", is the known case. Warrants, units and rights carry symbol suffixes the symbol rule already
catches, and "depositary" is left out because an ADR's name can carry "American Depositary
Shares" and ADRs belong in the universe (*my call*, amended while planning).

## 6. The four screen fixes

### 6.1 The status line

Today the line under the header runs to three lines: the kind, the counts, every phase count and
every refusal reason. It becomes one line:

    <kind> <status> <finished at> · <valued> of <companies> valued

for example `revalue done 2 Nov 2026, 19:27 · 1,052 of 1,759 valued`, with `· <n> failed` added
when a run failed companies, and the status word as today (`done`, `failed`, `cancelled`). Beside
it a `Details ▾` control, in the style of `Filters ▾`, opens a popover with three parts: the
flagged-by-a-classifier-check count; the phase counts in phase order with unclassified last;
the refusal reasons with their counts, largest first. The popover closes as the menus do (6.3).
During a run the run bar replaces the line, as today. The header's `engine ran` stamp is
unchanged. (Founder's ask: the breakdown out of the way; the popover is *my call*, a tooltip
cannot hold twenty-five reasons.)

### 6.2 The FIND focus ring

The focus ring on the FIND field is clipped at its top edge. It is a CSS defect in the design
system's bundle; the repository's copy gets a `/* fairband: */` patch so the ring draws on all
four sides at the token's width and offset, and the defect is noted for the design-system
artifact (*my call* on the fix location, as the screen-controls spec allows).

### 6.3 The menus

`Filters ▾`, `Columns ▾` and `Details ▾`: a click outside an open menu closes it; Escape closes
it; opening one closes any other. One menu open at a time. (Founder's ask; Escape is *my call*.)

### 6.4 Clear on FIND

A `Clear` text control inside the FIND field at its right edge, shown only while the field has
text, that empties the query and nothing else. The bar's `n of 1,759 · Clear`, which clears the
query and the filters, is unchanged. The control is a word because the brand book names controls
by words and reserves `×` for "expired" (*my call* on the form).

## 7. Policy values added

| Name | Value | Source line |
|---|---|---|
| `high_growth_years` | 5 | Damodaran's template, years 2 to 5 at one rate (H2); H3's half-and-half split; policy value |
| `margin_convergence_year` | 10 | Damodaran's template default (H2), his Zomato case; policy value |
| `peer_min` | 3 | design.md 6.2 and 6.7: minimum mature peers; no source gives the number |
| `peer_margin_min_years` | 5 | Damodaran H64, margins at "averages over the last five or ten years"; policy value |
| `implied_margin_bounds` | [−0.5, 1.0] | no source: solve bounds |
| `universe.name_exclude_patterns` | section 5.17 | design.md 2: listings that are not operating companies; policy value |

Unchanged and reused: `fade_years` (5), `marginal_return_span_years` (5),
`marginal_capital_growth_min` (0.20), `required_return`, `terminal_growth`,
`wide_terminal_roic_cap`, `margin_of_safety`, `analyst_min`, `value_spread_flag`.

## 8. Worked numbers for the tests

All synthetic, to a tolerance of 0.01. r = 9%, g_T = 3%, tax 21%, None moat (terminal return
9%). Trailing revenue 1,000; trailing margin −10%; target margin 20%; consensus steps 30%, 25%,
20%; sales-to-capital 2.0; debt 100; cash 300; 100 shares.

- Growth, years 1 to 10: 0.30, 0.25, 0.20, 0.20, 0.20, 0.166, 0.132, 0.098, 0.064, 0.03.
- Revenue: 1,300.00; 1,625.00; 1,950.00; 2,340.00; 2,808.00; 3,274.13; 3,706.31; 4,069.53;
  4,329.98; 4,459.88.
- Margins: −7%, −4%, −1%, 2%, 5%, 8%, 11%, 14%, 17%, 20%.
- EBIT: −91.00; −65.00; −19.50; 46.80; 140.40; 261.93; 407.69; 569.73; 736.10; 891.98.
- Tax: 0; 0; 0; 0; 2.46; 55.01; 85.62; 119.64; 154.58; 187.32 (the carried loss of 175.50 is
  used up in year 5).
- NOPAT: −91.00; −65.00; −19.50; 46.80; 137.94; 206.92; 322.08; 450.09; 581.52; 704.66.
- Reinvestment: 162.50; 162.50; 195.00; 234.00; 233.06; 216.09; 181.61; 130.23; 64.95; 234.89
  (year 10 at the terminal return).
- Free cash flow: −253.50; −227.50; −214.50; −187.20; −95.12; −9.17; 140.47; 319.87; 516.57;
  469.77.
- Present value of the ten years −115.94; terminal value 8,064.46, present value 3,406.51; firm
  value 3,290.57; equity 3,490.57; value a share 34.91.
- The return on new capital at the target: 0.20 × 0.79 × 2.0 = 0.316; against a peer median
  ROIC of 15% the flag fires.
- At a price of 25.00: the implied held growth is 8.63%; the margin the price needs is 16.00%.
- Value at target margins 10%, 20%, 30%: 10.09, 34.91, 59.64.
- The same row with sales-to-capital 3.0: 38.50. With a Wide moat (terminal return 13%): 40.45.
- Sales-to-capital, own measure: kept years with (revenue, average capital) (1,000, 400) five
  positions before (2,500, 900): marginal 1,500 ÷ 500 = 3.0; capital grew 125%, revenue grew:
  usable. Capital (2,500, 420) instead: grew 5%, not usable, the peer median is used.

## 9. Tests the builder must write

- The revenue path: the three steps, the hold, the fade, the rise when g_3 < g_T, the held step
  and its flag, the refusal without four quarters.
- The margin path, both directions.
- The tax carry within the forecast, section 8's figures.
- Reinvestment with the floor, and year 10 at the terminal return.
- The value, section 8, and the sensitivity at the three margins.
- The implied growth and the implied margin at a price equal to the value return the inputs
  within 1e-6; the implied margin on a row refused for the target margin.
- The target margin: the peer filter (universe, phase, years), the median, the refusal below
  `peer_min` with the count in the string, the largest peer recorded.
- Sales-to-capital: own usable, not usable on capital growth, not usable on falling revenue,
  fewer than six kept years, the peer fallback, the refusal.
- The terminal return from the return on new capital, Wide and None.
- Equity: debt and cash, missing lines as nil with their flags.
- The implied-return flag, both sides of the peer median.
- Young Growth: the same value as High Growth on the same inputs, plus `failure-not-charged`.
- The cross-check present with a positive anchor, absent otherwise.
- Determinism and the price refresh rebuilding every price-side figure from the intermediates.
- The peers call stored, reused, and its failure leaving the row refused for the target margin.
- The name patterns on the universe: ABXL's name excluded, an operating company's kept.
- Policy v3 loads with every value; v2 records under its own hash.
- The page: file-content assertions as the repository does, for the one-line status, the
  `Details ▾` control, the focus-ring patch marker, the outside-click and Escape handlers, the
  single-open rule and the `Clear` control.

## 10. Acceptance

1. After a full refresh of the founder's database, every High Growth and Young Growth row shows a
   value and a stance, or a refusal naming the missing input, and the rows refused for the
   target margin show the margin the price needs.
2. The drawer of a valued row shows the ten-year table (revenue, margin, EBIT, tax, NOPAT,
   reinvestment, free cash flow), the peers and their margins, the sales-to-capital measure, the
   terminal, the bridge to equity and the solves; the arithmetic reproduces from it.
3. The readout, written up for the founder: rows valued, refused by reason, the median value ÷
   price and the share at or above price for each of the two phases, the count flagged
   `return-above-peers`, the peer-count distribution.
4. The status line is one line with `Details ▾`; the FIND ring draws on four sides; the menus
   close on an outside click and on Escape and only one is open; `Clear` appears with text and
   empties the field.
5. `docs/method.md` has the route's sections and the version log entry for 0.4.
6. `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
   passes.

## 11. Left to the builder

- Module layout: a `revenue_growth.py` core beside `mature_growth.py`, a `route_revenue_growth.py`
  beside the two route modules, the peers fetch in `refresh/fetch.py` and its normalizer; the
  peer margin and capital reads from the store. The peers' phases, margins, sales-to-capital and
  ROIC are computed in assembly, which gains the deciles for it, so the route stays pure.
- The exact flag words and sentences, the drawer layout within the design system, the two new
  columns (the target margin and the margin the price needs) in the chooser.
- The popover's markup within the design system's menu style; where the menus' open state lives.
- The solve's scan step for the implied margin.

## 12. Order of work

1. Policy v3, the method version, the name patterns on the universe.
2. The peers fetch, stored and normalized; the peer margin and sales-to-capital reads.
3. The route core on hand-built inputs, with section 8's numbers.
4. The route: guards, intermediates, solves, sensitivities, flags, the cross-check, the price
   refresh.
5. The drawer and the columns.
6. The four screen fixes.
7. `docs/method.md`.
8. The full refresh on the founder's database and the readout.

## 13. Sources

The labels are the openalice research notes' (H), the stocks repo's (G, T, V) and the founder's
decisions (D).

- H1, H2, H3: do not keep a firm in high growth past ten years; the template's five-plus-five;
  the half-and-half split.
- H9: cash flow = earnings − reinvestment; the growth period's length comes from competitive
  advantage.
- H13, H14, H15, H16, H17: the top-down route for changing margins; the sales-to-capital
  measure from the company's data and the sector; the implied-ROIC check; the template's
  one-year lag; no negative reinvestment.
- H64: mature margins at five- to ten-year averages (the peer margin window).
- G1, G44: the length of high growth is a judgment set by competitive advantage.
- D3c: the mature-peer population for sales-to-capital; D3d: the failure-probability fallback.
- design.md 6.7: the target-margin default; design.md 6.10: the High Growth method.

## Decision log

| Date | Decision |
|---|---|
| 2026-11-02 | High Growth and Young Growth are built together, before Decline, on one route. Founder. |
| 2026-11-02 | Young Growth shows one value in tier 1; the range is tier 2's. Founder. |
| 2026-11-02 | Sales-to-capital: the company's own five-year marginal measure first, the mature-peer median as the fallback, with the implied-return check as a flag. Founder. |
| 2026-11-02 | The path is Damodaran's five-plus-five template, for both phases; the mature routes keep their structure. Founder. |
| 2026-11-02 | The required return is a flat 9%; the departure from the year-specific path is stated. Founder. |
| 2026-11-02 | The failure probability is reported as unavailable with the reason; the value is the going-concern value, flagged. A fitting source is a later research item. Founder. |
| 2026-11-02 | The four screen fixes of section 6, and the notes and preferreds filter, ride along. Founder (the filter is my call). |
