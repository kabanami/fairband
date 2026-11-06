# Fairband method, as built

| | |
|---|---|
| Method version | `fairband-mechanical/0.9` (`fairband.engine.METHOD_VERSION`) |
| Policy version | `fairband-policy-v8` (`src/fairband/policy/fairband-policy-v8.toml`) |
| Status | The single statement of the method the engine runs. Written 2026-11-02 from the code and the specs. |
| Rule of precedence | Where this document and any other document disagree, this document describes what runs. If the code disagrees with this document, one of them has a defect; fix the defect and keep the two aligned. |
| Update rule | Every change to the engine, the classifier, the universe rule or a policy value changes this document in the same commit, and bumps the method version when the value of any row can move. |

The reasons behind the rules are not restated here. They live in `docs/legacy/design.md` (the original design and the literature), `docs/legacy/research.md` (the founder's decisions D1 to D17), the mechanical screen spec, the calibration spec, the growth routes spec and the 2026-11-03 spec of the rate limiter, the classifier fixes and the designation (`2026-11-03-classifier-designation-ends-design.md`) and the 2026-11-04 spec of the Methodology page, the settings and the watchlists (`2026-11-04-methodology-settings-watchlists-design.md`) and the 2026-11-06 spec of the engine round (`2026-11-06-engine-round-design.md`) and the 2026-11-06 spec of the agents, Tier 2 (`2026-11-06-tier-2-agents-design.md`), under `docs/superpowers/specs/`. Section 12 maps each rule to its source.

## 0. How to read this document

- **r** is the required return, **g_T** the terminal growth, **N** the runway in years (on the revenue-growth route, its explicit period, section 5a; on the Decline route, the run-off's horizon, section 6a). Rates are fractions. Totals are in US dollars; per-share figures in dollars a share.
- "Trailing" means the trailing twelve months: the last four reported quarters summed (section 4.2). "Fiscal years" means the annual series.
- Every number the engine reads is either DATA (from a vendor, with its source and dates), RULE (from the effective policy: the policy file, with a source line, under the user's settings, 4.1) or an estimate under a named method. Every valuation constant that the literature or the founder set lives in the policy file (4.1); the code holds only the method's structural constants (4.1a).
- A phase is one of Damodaran's six: Start-up, Young Growth, High Growth, Mature Growth, Mature Stable, Decline. A route is the valuation method for a phase, and every phase has one: Mature Growth (section 5), the revenue-growth route that High Growth and Young Growth share (section 5a), Mature Stable (section 6), Decline (section 6a) and Start-up (section 6b), which gives no value by design: its row is always a refusal that keeps its figures. A foreign filer gets a refusal (section 7).
- A refusal is a result with no value and a reason. It is never an exception, and the row is never missing.
- Determinism: the same inputs under the same policy and method version and the same settings hash give the same result, bit for bit.
- The Methodology page (`web/static/methodology.html`) is written from this document and changes with it, in the same commit.

## 1. The universe

One FMP `company-screener` call per refresh, reused for 24 hours. A listing is admitted when all of these hold:

1. the exchange is NYSE, NASDAQ or AMEX;
2. it is not an ETF or a fund, and it is actively trading;
3. its market cap, in US dollars from the screener, is at least $2 billion;
4. its FMP industry is not one of the excluded industries: banks, insurance and REITs in every FMP spelling, Shell Companies (SPACs), and `Asset Management`, `Financial - Capital Markets`, `Financial - Credit Services`, `Financial - Mortgages`, `Financial - Conglomerates` and `Investment - Banking & Investment Services`. `Financial - Data & Stock Exchanges` stays admitted. The match ignores case and dash style, and an industry that starts with an entry and a space is excluded too, so `Banks—Regional` is out while `Banking Software` is in. A symbol on the manual admission list (`manual_admissions`: V, MA, GPN, payment companies that do not lend) passes rule 4 whatever its industry; a symbol on both lists is excluded. A listed symbol is admitted without the patterns of rules 5 and 6 being checked, and the match is exact on the exchange form (`BRK.B`), as the manual exclusion list's is;
5. its symbol does not match the preferred, warrant, unit or rights patterns (`[-.]P[A-Z]?$`, `[-.]W[ST]?$`, `[-.]U$`, `[-.]R$`) and is not on the manual exclusion list (empty today). A share class such as `BRK.B` passes;
6. its name does not match the note, debenture and preferred-share patterns, compared ignoring case (`\bnotes?\b`, `\bdebentures?\b`, `\bdue 20\d\d\b`, `\d(\.\d+)? ?%(\s|$)`, `\bpreferred\b`, `\bpreference\b`). They catch the notes, debentures and preferreds whose symbols carry no suffix, such as ABXL, "Abacus Global Management, Inc. - 8.875% Fixed Rate Senior Notes due 2028"; a rate may have a space before its percent sign ("5.25 % Debentures") or end the name ("5.625%"). No name pattern covers units, rights or depositary shares: rule 5 covers the first two, a partnership's name can carry "Common Units" or "Limited Partnership Units", and an ADR's name can carry "American Depositary Shares".

A listing that fails rule 1, 2 or 3 is skipped and not recorded (the screener request already asks for these filters; the rules are applied again on the rows). A listing that fails rule 4, 5 or 6 is recorded with its reason (`industry: <industry>`, `name pattern`, `symbol pattern` or `manual exclusion`) and gets no screen row. A listing on the manual exclusion list carries `manual exclusion` whatever else it fails; one that fails more than one of the other rules carries the first of the industry, the name and the symbol rule. A later row whose symbol is already recorded is skipped. An admitted listing gets a cap band: Mega from $200 billion, Large from $10 billion, Mid from $2 billion.

A listing admitted by the manual admission list is recorded as admitted like any other, and the refresh names the list's admissions in one log line in screener order, `manual admission: V, MA, GPN`. A universe is built by a full refresh only (section 10; a revalue values the latest stored universe), so the six financial industries and the admission list apply from the next full refresh.

## 2. The data the method reads

All from FMP unless named. The depth is set in `refresh/fetch.py`.

| Need | Source | Depth |
|---|---|---|
| Income statement, balance sheet, cash flow, annual | `income-statement`, `balance-sheet-statement`, `cash-flow-statement` | 11 fiscal years: ten for the ROIC aggregate plus the opening balance. Among the lines kept, for the Decline route: `grossProfit` and `interestExpense` (income statement), `totalAssets`, `totalLiabilities` and `retainedEarnings` (balance sheet), `depreciationAndAmortization` (cash flow) |
| As-reported balance sheet, annual | `balance-sheet-statement-as-reported` | 11 fiscal years; supplies the issuer's total intangibles excluding goodwill, and the lease lines |
| Income statement and cash flow, quarterly | the same endpoints with `period=quarter` | 8 quarters, for the trailing figures; `grossProfit`, `interestExpense` and `depreciationAndAmortization` among the lines kept |
| Consensus EPS, revenue, net income with analyst counts | `analyst-estimates`, annual and quarterly | 6 annual rows and 40 quarterly rows; the engine picks periods by date, never by row order. FMP gives two analyst counts, for EPS and for revenue; the net-income count reads the EPS count |
| Street actual EPS by quarter | `earnings` | 12 rows, for the stock-compensation basis test |
| Next earnings date | `earnings` | the same rows; the next date on or after today |
| Quote: price, market cap | `quote` | current |
| Profile: country, ADR flag | `profile` | current |
| Daily closes | `historical-price-eod/full` | five years, for the price columns |
| Peers | `stock-peers` | one call a company, reused for 24 hours; not required; usable when it names a peer other than the company or is exactly the empty list; a list of objects without a symbol, or anything but a list, is unusable. The symbols stay in the stored payload; the peers' figures come from their own stored statements (5a.4); when the list leaves fewer than `peer_min` peers that count for the target margin, the company's FMP industry supplies them (5a.4) |
| Moat score | GuruFocus `summary` | current; reused for 7 days |
| EPS trailing and EPS without non-recurring items | GuruFocus `keyratios` | current; reused for 7 days |
| Statutory tax rate | the packaged table `tax-rates-oecd-v2.toml`: the OECD series' 146 jurisdictions, plus Taiwan and Cyprus by hand | by country and fiscal year |

A company's vendor data observed within the last 24 hours is reused, not fetched again. FMP calls are paced to `fmp_calls_per_minute`, one pace shared by every worker; a 429 holds every FMP worker for the vendor's numeric `Retry-After` capped at `rate_limit_hold_s`, else `rate_limit_hold_s`, and the call retries after the hold. A GuruFocus 429 sleeps the same hold before its retry and holds no other worker. The retry counts and the run's 429 path are unchanged. Every response is stored as received with any key scrubbed; normalized facts cite the response they came from. Vendor numbers are stored as decimal text; the engine computes in floats.

Four endpoints are required: the three annual statements and the quote. When one of them fails, the company's row is the refusal "data fetch failed: <the failed required endpoints>". A failure of any other call leaves the company valued on what it has.

Where a field has several sources, the order is: market cap from the quote, else the profile, else the screener row; the ADR flag from the profile, else the screener row; the country from the profile (the headquarters), else the screener row, else "unknown", which has no tax rate.

## 3. The phase classifier

### 3.1 The series

The fiscal-year series runs from the newest annual income statement back, at most eleven years, one row per fiscal year with none skipped: a year the vendor lacks keeps its place with no values. Each row carries revenue, operating income, operating cash flow, investing cash flow, financing cash flow and capital spending (signed as the cash-flow statement signs it, so spending is negative), and the reporting currency of its income statement. A year without one takes the year before's; leading years without one take the first known currency after them; with none known, the currency is "unknown".

### 3.2 Revenue growth

Growth is the compound annual rate from the fiscal year three years back to the last fiscal year:

    g3 = (revenue_last ÷ revenue_first) ^ (1 ÷ span) − 1

- With two or three fiscal years on file, the span is what exists.
- When the first year of the span has a missing, zero or negative revenue, growth runs over the longest run of consecutive positive revenues that ends at the last year.
- Growth cannot be measured when the last revenue is missing or not positive, or that run is shorter than two years.

A **Start-up** is a company whose revenue is zero now, or was zero three years ago. A year not on file is not zero.

### 3.3 Deciles and the growth word

At every full refresh the universe is ranked. The ranking takes every admitted company whose series has no data gap (3.8), is not a Start-up, has a measurable growth and has an operating margin in the last five fiscal years. The nine decile edges are the inclusive quantiles of those growth rates. A value's decile is one plus the number of edges at or below it, at most 10.

| Deciles | Growth word |
|---|---|
| 9 to 10 | Very High |
| 7 to 8 | High |
| 5 to 6 | Moderate |
| 3 to 4 | Low |
| 1 to 2 | Close to zero or negative |

The deciles are stored with the refresh. A scoped refresh (named tickers) and a revalue reuse the latest stored deciles, and each snapshot cites the refresh its deciles came from. With no deciles stored, every company is refused "no universe deciles yet". A full refresh whose fetch stops on an HTTP 429 values the companies it fetched on the stored deciles and saves no new ones; one whose deciles rank no company fails and saves none.

### 3.4 Trends, the margin and its direction

A trend is the least-squares slope of a value against the year index over the last five fiscal years. A year without a value is skipped but keeps its index. A trend needs at least three values.

The operating margin of a year is operating income ÷ revenue, defined only when both are present and revenue is positive. The margin that decides the phase is the margin of the last of the last five fiscal years that has one. The margin trend is the slope of the yearly margins.

The margin direction exists for a margin at or above zero with a trend. The positive-margin companies' margin slopes are ranked into deciles at the refresh, as the growth rates are:

- decile 9 or higher and a slope above zero: **Rising**;
- decile 2 or lower and a slope below zero: **Declining**;
- otherwise **Stable**, which points to no phase (3.6).

### 3.5 The rules

The first rule that fits decides the phase.

1. A Start-up (3.2) that is not established is **Start-up**. An established company whose revenue was zero three years ago goes on to rules 2 to 5, its growth measured over the run of positive revenues after the zero (3.2), and is flagged `revenue-gap`; one whose revenue is zero now has no measurable growth and is unclassified (3.8).
2. A growth word of "Close to zero or negative" with a falling five-year revenue trend and revenue that fell in at least three of the last four year-over-year steps is **Decline**, whatever the margin. The steps are those between the last five fiscal years; a step is a fall when both years have a revenue and the later is below the earlier, and a step with a missing year is not a fall. With fewer than three steps on file the rule cannot fire.
3. With no operating margin in the last five fiscal years, the company is unclassified ("no operating margin").
4. A negative margin:
   - (4a) of an established company takes rule 5's phase by the growth word, as if the margin were positive, and is flagged `loss-year`;
   - (4b) of any other company is **High Growth** when the margin trend is above zero, else **Young Growth** (a missing trend or a slope of exactly zero counts as not improving).
5. A margin at or above zero with a growth word of "Very High", "High" or "Moderate" is **Mature Growth**; with "Low" or "Close to zero or negative" it is **Mature Stable**. A margin of exactly zero counts as positive and is flagged.

A company is **established** when at least three of the last five fiscal years on file, or at least five of the fiscal years on file (3.1, eleven at most), have an operating margin above zero; a year without a margin counts for nothing in either count.

### 3.6 The checks

A check flags the company and never changes its phase.

| Check | Flag code | When it fires |
|---|---|---|
| Growth word | `growth-word-disagrees` | Negative margin of a company that is not established (rule 4b). The growth word points to another phase: Very High → Young Growth, High → High Growth, Moderate → Mature Growth, Low → Mature Stable, Close to zero or negative → Decline. |
| Loss year | `loss-year` | Rule 4a decides the phase: a negative margin of an established company. The sentence names the fiscal year of the deciding margin, how many of the last five fiscal years have a margin above zero and how many of the fiscal years on file do. |
| Revenue gap | `revenue-gap` | Rule 1 lets an established company whose revenue was zero three years ago through to rules 2 to 5. The sentence names the fiscal year of the zero and the two counts of the established test. An unclassified row is not flagged. |
| Revenue falling | `revenue-falling` | A growth word of "Close to zero or negative" with a falling five-year revenue trend, and revenue that fell in fewer than three of the last four year-over-year steps (rule 2). The sentence names the falls. |
| Margin direction | `margin-direction-disagrees` | Margin at or above zero with a direction of Rising or Declining. The direction points to another phase: Rising → Mature Growth, Declining → Decline. Stable points to no phase and never fires. |
| Free cash flow sign | `fcf-sign` | The last fiscal year's operating cash flow plus capital spending is negative in Mature Growth, Mature Stable or Decline, or positive in Start-up, Young Growth or High Growth. A zero does not fire. |
| Short history | `short-history` | Fewer than five fiscal years on file, or a growth span shorter than three years. |
| Zero margin | `margin-zero` | The deciding margin is exactly zero. |
| Currency change | `currency-change` | The reporting currency changes between fiscal years. Growth is still computed from the reported figures. |

### 3.7 The Dickinson stage

Shown beside the phase, never deciding and never flagging. From the signs of the last fiscal year's operating (CFO), investing (CFI) and financing (CFF) cash flows:

| CFO | CFI | CFF | Stage |
|---|---|---|---|
| − | + | any | Decline |
| − | − | + | Introduction |
| + | − | + | Growth |
| + | − | − | Mature |
| every other pattern | | | Shake-out |

A zero has neither sign and lands in Shake-out unless the pattern is Decline. A missing flow gives no stage.

### 3.8 Unclassified companies

A company is unclassified, with the reason as its refusal, when its series has fewer than two fiscal years, no revenue for the last fiscal year, a negative last revenue, no measurable revenue growth (a company rule 1 does not make a Start-up with no positive run of two years, among them an established company whose revenue is zero now), or no operating margin when the margin must decide. An unclassified company does not enter the deciles.

## 4. The engine's shared pieces

### 4.1 Policy values

Every value comes from `fairband-policy-v8.toml` with a source line. The table lists the values the method reads and every setting: a value the user may change on the Settings view, marked yes in the column Setting. The other universe and refresh values are in sections 1 and 2.

| Value | Policy name | Setting | Source |
|---|---|---|---|
| r = 9% | `required_return` | yes | stocks method v1.7 section 3 |
| g_T = 3% | `terminal_growth` | yes | same |
| Runway N: None 5, Narrow 10, Wide 20 years | `runway_years` | yes | same |
| Margin of safety: None 45%, Narrow 35%, Wide 25% | `margin_of_safety` | yes | method v1.7 Step 10 |
| Fair band 0.85 to 1.15 × value | `fair_band` | yes | Step 10 |
| Trim at 1.5 × value | `trim_multiple` | yes | Step 10 |
| Wide-moat terminal spread above r: 4 points | `wide_terminal_roic_spread` | yes | design.md 6.6: the cap is r + the spread, 13% at the defaults; spec 2026-11-04 8.3 |
| Moat: score 8 to 10 Wide, 4 to 7 Narrow, else None | `moat_wide_min`, `moat_narrow_min` | no | mech/1.2 |
| Base-rate medians by sales class (eleven classes) | `base_rates` | no | Base Rate Book, exhibit 4 |
| Held-rate cap by sales class: the 90th-percentile five-year sales growth (eleven classes) | `base_rates`, `sales_p90_5y` | no | Base Rate Book, Sales Growth exhibit 4; growth routes spec 5.4; founder decision 2026-11-03 |
| Inflation addition 2 points | `inflation_addition` | yes | mech/1.2; policy value |
| Marginal return span 5 years | `marginal_return_span_years` | no | calibration spec 5.1; policy value |
| Marginal usability: capital grew by at least 20% | `marginal_capital_growth_min` | no | calibration spec 5.1; policy value |
| Fallback return window 3 years | `fallback_return_years` | no | calibration spec 5.1; policy value |
| Fade 5 years | `fade_years` | yes | calibration spec 5.4; Damodaran's template |
| High-growth years 5 | `high_growth_years` | yes | growth routes spec 5.4; Damodaran's template H2, H3; policy value |
| Margin convergence year 10 | `margin_convergence_year` | yes | growth routes spec 5.5; Damodaran's template H2; policy value |
| Peer minimum: 3 mature peers | `peer_min` | yes | design.md 6.2 and 6.7; no source gives the number |
| Industry peers: at most 10 | `industry_peer_max` | yes | growth routes spec 5.5; no source gives the number; founder decision 2026-11-03 |
| Peer margin: 5 fiscal years at least | `peer_margin_min_years` | no | growth routes spec 5.5; Damodaran H64; policy value |
| Bounds of the margin the price needs: −50% to 100% | `implied_margin_bounds` | no | no source (growth routes spec 5.11) |
| Own sales-to-capital bound: at least 0.5 × the mature peers' median | `own_sales_to_capital_min_share` | no | Damodaran H13, H14 (the industry sales-to-capital serves where the company's own history cannot); no source gives the number; founder decision 2026-11-06 |
| Loss ramp bound: a trailing margin below −100% | `loss_ramp_margin_bound` | no | spec 2026-11-03 9.2 (the Start-up ramp moves operating income in dollars); no source gives the number; founder decision 2026-11-06 |
| Return sensitivity 15% and 9% | `roic_sensitivity` | yes | no source |
| Thin consensus: fewer than 5 analysts | `analyst_min` | yes | method v1.7 section 3 |
| Large non-recurring item: 5% of trailing EPS | `nri_flag_share` | yes | spec 6.7 |
| Value spread flag: 30% | `value_spread_flag` | yes | no source |
| Long runway flag: 10% growth | `long_runway_growth_flag` | yes | design.md 6.5 change 3 |
| Margin flag: 1.5 × median, 10% above the high, 6 years at least | `margin_flag_ratio`, `margin_flag_above_high`, `margin_flag_min_years` | yes | mech/1.2 |
| Heavy capex: above 50% of operating cash flow | `capex_ocf_flag` | yes | method v1.7 Step 0 |
| Equity raise: issuance at or above 1% of market cap | `equity_raise_share` | yes | method v1.7 Step 0 |
| Stock-compensation basis test: 50% of after-tax SBC a share | `sbc_detect` | no | mech/1.2 |
| Forward P/E unit error: below 2 | `forward_pe_unit_error` | no | mech/1.2 |
| Validity fallback: 91 days | `validity_fallback_days` | yes | design.md 8 |
| Aging at 0.6667 of the window | `aging_fraction` | yes | design system |
| Repricing horizon 3 years | `repricing_horizon_years` | yes | stocks method v1.7 Step 9; design.md 1; spec 2026-11-04 8.3 |
| FMP pace: 2,850 calls a minute | `refresh.fmp_calls_per_minute` | yes | the founder's Ultimate plan, 3,000 a minute, less 5%; spec 2026-11-03 5.2; policy value |
| 429 hold: 60 seconds | `refresh.rate_limit_hold_s` | yes | one plan window; spec 2026-11-03 5.2; policy value |
| Excluded industries: banks, insurance, REITs and Shell Companies (section 1), and six financial ones: `Asset Management`, `Financial - Capital Markets`, `Financial - Credit Services`, `Financial - Mortgages`, `Financial - Conglomerates`, `Investment - Banking & Investment Services` | `universe.excluded_industries` | no | design.md 6.1; decision 2026-10-26; spec 2026-11-03 6.4 |
| Manual admissions: V, MA, GPN | `universe.manual_admissions` | yes | founder 2026-11-03: payment companies that do not lend; spec 2026-11-03 6.4 |
| Exchanges: NYSE, NASDAQ, AMEX | `universe.exchanges` | yes | design.md 2; spec 6.1 |
| Size floor: $2 billion of market cap | `universe.cap_floor_usd` | yes | design.md 2; spec 6.1 |
| Cap bands: Mega from $200 billion, Large from $10 billion, Mid from $2 billion | `universe.cap_bands` | yes | design.md 2; spec 6.1 |
| Manual exclusions: none | `universe.manual_exclusions` | yes | design.md 2; spec 6.1 |
| FMP workers: 16 | `refresh.workers` | yes | founder decision 2026-11-01 (was 4, mech/1.2); policy value |
| Reuse window, FMP: 24 hours | `refresh.reuse_hours` | yes | research.md D13; spec 6.2 |
| Reuse window, GuruFocus: 7 days | `refresh.gf_reuse_days` | yes | research.md D13; spec 6.2 |
| Designation edges, derived: 1 − the Narrow margin of safety, the fair band's low and high, the trim multiple (0.65, 0.85, 1.15, 1.50 at the defaults) | — | no | method v1.7 Step 10; spec 2026-11-04 8.3 |
| Run-off horizon: 10 years | `runoff_years` | yes | Damodaran's ten-year template (H2) |
| Divestiture recovery: 60% of the capital released | `runoff_recovery` | yes | Damodaran 2009 Sears: 54% to 67% of the capital released; the midpoint; policy value |
| Distress-sale fraction: 60% of the firm value | `distress_sale_fraction` | yes | Damodaran 2009, "Estimating Distress Sale Proceeds", choice (a), the illustration's $3 billion of $5 billion; policy value |
| Synthetic rating by interest coverage: 15 rows, D to AAA | `synthetic_rating` | no | Damodaran, ratings.html, "For large non-financial service firms", January 2026 |
| Ten-year default probability by rating: 15 ratings | `default_probability_10y` | no | Damodaran 2009, Table 5 (Altman, 1971 to 2007); D 100%; BB+ as BB (policy value) |
| Altman Z″ zones: distress below 1.1, safe above 2.6 | `z_distress`, `z_safe` | no | Altman 2000 |
| Piotroski F low group: 1 or below | `f_score_low` | no | Piotroski 2000, the 0 to 1 group |
| Burn cover flag: below 2 years | `burn_cover_flag_years` | yes | no source |
| Override ranges: growth belief −20% to 60%; held rate −20% to 300%; consensus steps −80% to 300%; target margin −50% to 60%; sales-to-capital 0.1 to 10; runway return 0% to 100%; non-recurring gap −$100 to $100 a share; decline rate −50% to 0%; debt and cash $0 or more ($10^15 at most) | `override_ranges` | no | spec 2026-11-06 Tier 2 10.2; no source gives the numbers; policy value |
| Primary evidence above the 90th percentile: a belief or held rate overridden above the sales class's `sales_p90_5y` needs a filing or a transcript | `override_primary_evidence_above_p90` | no | spec 2026-11-06 Tier 2 10.3; policy value |
| Secondary valuation: at most 10 parts | `secondary_parts_max` | no | spec 2026-11-06 Tier 2 11; no source gives the number; policy value |
| Secondary valuation: a cash-flow path of 3 years at least | `secondary_years_min` | no | same |
| Secondary valuation: a cash-flow path of 15 years at most | `secondary_years_max` | no | same |
| Stance words: buy, hold, trim, avoid | `stance_words` | no | spec 2026-11-06 Tier 2 13.1: the brand book's three zone words and avoid; policy value |

The run-off, distress-sale, rating, default-probability, Z″ and F values are read by the Decline route (section 6a); the burn-cover value by the Start-up route (section 6b). The override ranges and the evidence rule bound an agent's overrides, the secondary values its secondary valuation and the stance words its report (spec 2026-11-06 Tier 2, 10.2, 10.3, 11 and 13.1); no mechanical route reads them.

The user's settings are an overlay: one stored value for each setting changed from the file's. The effective policy is the file's values with the overlay applied, built once for each run and each request. It keeps the file's version, and every range and cross-field rule (spec 2026-11-04 8.2 and 8.9) is checked when it is built, as when the file loads. A RULE input cites the policy version and carries the effective value. Every result cites the settings hash beside the policy version: the sha256 of the overlay's entries for the valuation and flag settings (groups A and B of spec 2026-11-04 8.2) and `validity_fallback_days`, as JSON with sorted keys; an empty overlay hashes `{}`. The universe and refresh settings and `aging_fraction` do not enter the hash: the first two change which companies are valued and how they are fetched, and `aging_fraction` is read when a row is shown, never at valuation.

Policies v1 to v7 stay in the package unchanged, because the snapshots valued under them cite their hashes. The engine loads v8 only.

### 4.1a Constants in code

These set the method's structure, not a valuation judgment, and live in the code: the ROIC window of ten years and its minimum of five; the growth span of three years; the trend window of five years with at least three points; the margin-direction deciles 9 and 2 (3.4); the established company's three of the last five fiscal years, or five of the fiscal years on file, with a margin above zero (3.5); the Decline rule's three falls in the last four year-over-year steps (3.5); the 80 to 100 days between consecutive quarters; the margin flag's ten-year window; the implied-growth scan from −50% to 200% in steps of 1% to a tolerance of 1e-7, on the Mature Growth and the revenue-growth routes alike, and the same step and tolerance for the margin the price needs within its policy bounds; the peers' ten-year margin window; the lease-accounting date of 15 December 2019; the Altman Z″ coefficients of the non-manufacturer form, 6.56, 3.26, 6.72 and 1.05 (Altman 2000), and Piotroski's nine F signals (Piotroski 2000), both for the Decline route's distress signals (6a.8); the Decline route's implied decline rate, scanned from −50% to 0 in steps of 0.1% to a tolerance of 1e-7, and the scan's lower bound, −50%, as the floor of the decline rate (6a.2); the normalized margin's window, the last five fiscal years with at least three margins (6a.3); the Start-up requirement's ramp of ten years and its solve, bisection on [0, 10^13] to a relative tolerance of 1e-9 (6b.2).

### 4.2 Trailing figures and the share count

The trailing figures are the sums of the last four quarterly income statements when there are four and each ends 80 to 100 days after the one before, joined to the quarterly cash-flow statements by period end: revenue, operating income, net income, diluted EPS, stock compensation, operating cash flow, capital spending, dividends, buybacks and stock issued. A sum is missing when any quarter lacks its part. Otherwise the trailing figures are the last fiscal year's, flagged `trailing-on-fiscal-year`.

Two more trailing figures sum the same quarters, or read the same fiscal year: the interest expense and the depreciation and amortization (the cash flow's). As every trailing figure, each is missing when any quarter lacks its line, or, on the fiscal-year fallback, when the year lacks it; a sum of fewer quarters never stands for twelve months. The interest expense counts each quarter by its size, never netted, since FMP signs it either way across companies; the depreciation keeps FMP's sign.

The diluted share count is the newest quarter's weighted average diluted shares, else the newest fiscal year's. One share count serves every year of every route.

### 4.3 The tax rate

NOPAT uses the statutory marginal rate: the OECD combined central and sub-central corporate rate for the company's country and the fiscal year. The table is `tax-rates-oecd-v2.toml`: every jurisdiction of the OECD series (dataflow `DSD_TAX_CIT@DF_CIT`, measure `CIT_C`, sector `S13`, targeting `ST`), 146 at the retrieval of 2026-11-06, each year from 2014 the series gives, each jurisdiction named by its ISO 3166-1 alpha-2 code; and, written by hand because the series lacks them, Taiwan (17% from 2014 to 2017 and 20% from 2018 to 2026; the Income Tax Act, article 5, Ministry of Finance) and Cyprus (12.5% from 2014 to 2025; the Tax Department). A rate cites the table's source, the OECD series, except on a row written by hand, which cites its own source line; a carried-forward estimate cites the newest year's row. `scripts/build_tax_table.py` regenerates the table from the series' CSV export. `tax-rates-oecd-v1.toml`, the sixteen jurisdictions of 0.8 and earlier, stays in the package for the snapshots that cite it. The country is the headquarters country of the FMP profile, else the universe row's. A fiscal year later than the newest year in the table takes the newest year's rate as an estimate under method `tax-rate-latest-oecd-year-v1`, flagged `tax-carried-forward`. An earlier missing year, or a country the table lacks, has no rate: the first fiscal year of the eleven-year span with an operating income and no rate refuses the company, "no statutory tax rate for <country> <year>". For a foreign filer, assembly withholds that refusal, so the route gives the foreign-filer refusal instead. The newest fiscal year's rate also converts stock compensation to after tax in the anchor (5.2), and taxes every forecast year of the revenue-growth route (5a.6).

### 4.4 Invested capital and NOPAT

Invested capital at a fiscal year end, from the operating side:

    capital = (total current assets − cash and short-term investments)
            − (total current liabilities − short-term debt − current lease liability)
            + net property and equipment + lease right-of-use assets + goodwill + intangibles

- Total current assets, total current liabilities and net property and equipment are required; without one of them the year has no capital.
- Cash and investments are cash plus short-term investments; one missing counts as nil.
- Intangibles are the issuer's as-reported total intangibles excluding goodwill (method `bs10-intangibles-total-v1`) where the as-reported balance sheet has it, else FMP's normalized line. On FMP's normalized balance sheet a zero for goodwill or intangibles is read as not presented, never as a reported zero; on the as-reported balance sheet a zero is a reported zero.
- The lease lines come from the as-reported balance sheet only. A balance sheet ending before 15 December 2019 with no lease assets is flagged `leases-not-on-balance-sheet`; nothing is reconstructed.
- Any other optional line the issuer does not present counts as nil under method `not-presented-as-nil-v1` and is flagged `line-not-presented:<field>`. Cash and investments, short-term debt, the current lease liability, lease assets, goodwill and intangibles are the optional lines.

NOPAT for a fiscal year = operating income × (1 − statutory rate).

### 4.5 The ten-year aggregate ROIC

A ROIC year needs its NOPAT and both its opening and closing capital. Its average capital is (opening + closing) ÷ 2, so ten years need eleven balance sheets. The last ten such years, oldest first, are the kept years.

    aggregate = Σ NOPAT ÷ Σ average capital, over the kept years

- Fewer than five kept years: no aggregate, flag `roic-unavailable`.
- Five to nine: flag `roic-on-n-years`.
- A capital sum at or below zero: no aggregate, flag `ten-year-roic-unavailable`.

The aggregate is shown and feeds the "ten-year" sensitivity (5.8). It never enters the charge. The kept years also give the revenue-growth route its own sales-to-capital (5a.5) and the Decline route its own-latest measure (6a.4).

### 4.6 The runway return

The return the charge uses in years 1 to N − 1. From the kept years, in this order:

1. **Unavailable** with fewer than five kept years: the charge uses the terminal return (4.7) in every year.
2. **The five-year marginal return**: with at least six kept years, (NOPAT_last − NOPAT_first) ÷ (capital_last − capital_first), "last" the newest kept year and "first" the kept year five positions earlier, capital the average capital. Usable when capital grew, by at least a fifth of the first year's capital in size, and NOPAT grew.
3. **The three-year aggregate** when the marginal is not usable: Σ NOPAT ÷ Σ average capital over the last three kept years.
4. **Charge off** when the marginal is not usable and the three-year capital sum is at or below zero: the runway years are not charged (payout 100%), flag `charge-zeroed`. The terminal still charges (4.7).
5. **The floor**: a chosen measure below r is replaced by r, flag `return-floored`. There is no cap.

The row records which measure it used ("marginal", "three-year", "floor", "off", "unavailable") with the marginal, its usability, the three-year and the ten-year figures, and the value the charge used.

### 4.7 The terminal return

The return in year N and in the terminal value.

- Narrow or None moat: r.
- Wide moat: the chosen measure of 4.6 before its floor, capped at r plus the spread (`wide_terminal_roic_spread`, 4 points: 13% at the defaults) and never below r. When the runway charge is off: the cap. When the runway return is unavailable: r.

The same rule, applied to a given return, gives the terminal return for each sensitivity value (5.8), and on the revenue-growth and Start-up routes for the return on new capital at the target margin (5a.7, 6b.2).

### 4.8 The charge and the value

Earnings in year t are a total, on the one share count. Each year's reinvestment pays for the next year's growth:

    cash_t = earnings_t × max(0, 1 − g_{t+1} ÷ return_t)

with return_t the runway return for t < N and the terminal return for t = N, and g_{N+1} = g_T. A year whose next growth is above its return pays out nothing, never less; the first such year raises `growth-above-return`. When the charge is off, cash_t = earnings_t for t < N.

    terminal multiple = (1 + g_T) × (1 − g_T ÷ terminal return) ÷ (r − g_T)
    value = Σ_{t=1..N} cash_t ÷ (1 + r)^t + earnings_N × terminal multiple ÷ (1 + r)^N

The value a share is the total ÷ the diluted share count.

### 4.9 The moat class

From the GuruFocus Moat Score: 8 or more Wide, 4 or more Narrow, below 4 or no score None. The moat enters in three places: the runway N, the terminal return and the margin of safety. The revenue-growth route's explicit period does not read it, so there the moat enters the terminal return and the margin of safety only. On the Decline route it enters the margin of safety only (6a.5). On the Start-up route it enters the terminal return only (6b.2): a Start-up row has no levels.

### 4.10 Levels, designation and validity

On the value at belief, each level the exact decimal product:

- buy level = value × (1 − margin of safety for the moat);
- fair band = value × the band's low to value × its high (0.85 and 1.15 at the defaults);
- trim level = value × the trim multiple (1.5 at the defaults).

The levels are computed once at valuation and shown as figures; nothing in the engine reads the price against them. On every valued row the engine reads the price against the value at belief, price ÷ value as a plain division, and gives it a word by the designation edges e1 to e4. The edges are derived from the policy, not set: e1 = 1 − the Narrow margin of safety, e2 = the fair band's low, e3 = the fair band's high, e4 = the trim multiple (0.65, 0.85, 1.15, 1.50 at the defaults; method v1.7 Step 10), so a changed margin of safety, band or trim multiple carries them along. The ratio is compared with each edge as written:

| price ÷ value | Code | Screen word |
|---|---|---|
| below e1 | `well-below` | Well below |
| from e1, below e2 | `below` | Below |
| from e2 to e3, ends included | `near` | Near |
| above e3, below e4 | `above` | Above |
| at or above e4 | `well-above` | Well above |

The word is the band's, never an action. The designation is a fact about the price: a price refresh recomputes it; a refusal and a Start-up row have none. A snapshot valued under method 0.5 carries a stance and no designation; it reads with none until a revalue replaces it.

The data date is the date of the newest observation among the company's stored statement facts (today, when it has none). A result is valid until the next earnings date when that date is after the data date, else `validity_fallback_days` (91) days after the data date. It is current until `aging_fraction` (0.6667) of the window has passed, then aging, then expired after the window's end. An expired row keeps its figures.

## 5. The Mature Growth route

A reverse DCF on net income with the reinvestment charge: year 1 from the quarterly consensus, years 2 and 3 from the annual consensus, a fade to a base-rate belief, the belief to the runway, then the terminal.

### 5.1 Guards and refusals

Before any route, in this order: no universe deciles yet; the assembly's refusal ("no financial statements", or the missing tax rate of 4.3); a foreign filer (an ADR by the profile, or a reporting currency other than USD, an unknown currency included); an unclassified company (3.8); no positive price; no positive diluted share count. A Start-up row then takes its route (6b), which no missing trailing figure refuses; every other row is refused without trailing figures. Every phase has a route: Mature Growth and Mature Stable their own, High Growth and Young Growth the revenue-growth route of section 5a, Decline the run-off of section 6a and Start-up the requirement of section 6b.

Then the route's own, in this order: no trailing revenue; no statutory tax rate; an incomplete NTM consensus (5.2); no positive forward anchor; a forward P/E below 2 (a unit error); consensus earnings that turn negative within the path (a step at or below −100%); a value a share at or below zero under the charge (the intermediates are kept).

### 5.2 Year 1: the NTM anchor

The NTM quarters are the first four quarterly consensus periods ending after the trailing period end, by period end, and only when each ends 80 to 100 days after the one before and each has an EPS mean. NTM EPS raw = their sum.

The stock-compensation basis test: the street trailing EPS is the sum of the four street actuals whose periods are the four trailing quarter ends (missing when one is absent or the trailing figures are a fiscal year). After-tax SBC a share = trailing stock compensation × (1 − the newest fiscal year's statutory rate) ÷ diluted shares. When street EPS − GAAP trailing diluted EPS ≥ 0.5 × after-tax SBC a share, the consensus excludes stock compensation, and the anchor subtracts after-tax SBC a share × (NTM consensus revenue ÷ trailing revenue; the factor is 1 when any NTM quarter lacks a revenue mean or trailing revenue is missing or not positive). When any of the three inputs is missing, the basis is unknown, the consensus stands as it is, flag `sbc-basis-unknown`.

NTM EPS = raw − adjustment. NTM net income = NTM EPS × diluted shares. An NTM EPS at or below zero refuses; so does a price ÷ NTM EPS below 2.

### 5.3 Years 2 and 3: the consensus path

The base year is the fiscal year that holds most of the four NTM quarters; a tie takes the later year. An estimate's fiscal year is FMP's label when the row carries one, else the year derived from the company's fiscal calendar: the month and day of the newest annual income period end, where a period ending up to seven days past a year's end still belongs to that year. The path reads the annual consensus for the base year and the next two:

- on net income when all three years have a positive net-income mean, else on EPS, flag `path-on-eps`;
- a mean of zero with no analyst count, or a count of zero, is no estimate;
- step g_2 = year(base + 1) ÷ year(base) − 1, step g_3 = year(base + 2) ÷ year(base + 1) − 1; a step is missing when either year is missing or the earlier is not positive, and a missing step takes the belief;
- a present step whose landing year has fewer than 5 analysts, or no count, flags `few-analysts`. The count is FMP's EPS analyst count on either series.

### 5.4 The belief

The growth for years 4 to N, before the fade: the Base Rate Book median ten-year net-income growth for the company's sales class plus 2 points. The sales class is the first class whose upper bound is at or above trailing revenue in current dollars; the bounds are in 2015 dollars, and no index is applied.

### 5.5 The growth path

With belief b and year-3 growth g_3: if g_3 > b, years 4 to 8 fade in five equal steps,

    g_t = b + (g_3 − b) × (8 − t) ÷ 5, for t = 4 … 8,

so g_8 = b, and years 9 to N grow at b. If g_3 ≤ b, years 4 to N grow at b. The runway cuts the path: with N = 5 the path ends at g_5 mid-fade.

Earnings_1 = NTM net income; earnings_t = earnings_{t−1} × (1 + g_t).

### 5.6 The value

Section 4.8 on this path, at the runway return (4.6) for years 1 to N − 1 and the terminal return (4.7) for year N and the terminal, N by the moat.

### 5.7 The implied growth

The belief b at which the value equals the price × shares, with the fade recomputed at each trial b. Solved by a scan from −50% to 200% a year in steps of 1% for the first sign change, then bisection to 1e-7. None when no belief in that range reaches the price. Also solved at each runway and at each return of the sensitivity.

### 5.8 Sensitivities

- By runway: the value at N = 5, 10 and 20 under the row's own charge.
- By return, four keys: `runway` (the row's own charge); `0.15` and `0.09`, each as the runway return with the moat's terminal rule (4.7) applied to it and the charge on in every runway year; `ten-year`, the ten-year aggregate the same way, not floored, or none when the aggregate is unavailable or not positive.

The value-spread flag reads the first three return keys, and separately the three runways: it fires when (highest − lowest) ÷ lowest is 30% or more, with a positive lowest value.

### 5.9 EPV, growth share and multiples

- Clean trailing EPS = GAAP trailing diluted EPS − the non-recurring gap, where the gap = GuruFocus EPS trailing − EPS without non-recurring items (nil without both).
- EPV a share = clean trailing EPS ÷ r. It never sets a level. Growth share of price = 1 − EPV ÷ price.
- Trailing P/E reported and clean, forward P/E on NTM EPS; a P/E exists only for a positive EPS.

### 5.10 The expected return over the repricing horizon

H is the repricing horizon in years, `repricing_horizon_years` (3 at the defaults; 4.1).

    income    = (−dividends − buybacks − stock issued) ÷ market cap, trailing flows, FMP's signs
    growth    = ((1 + g_2)(1 + g_3) … (1 + g_{H+1}))^(1/H) − 1, the path's own rates
    repricing = ln(value ÷ price) ÷ H
    total     = income + growth + repricing

The growth term is the geometric mean of the growth over years 2 to H + 1. Past the runway the path grows at g_T, the terminal value's own rate, so a horizon longer than the path never fails: a runway of 4 years gives the rates of years 2 to 4, and a horizon of 6 reads g_T for years 5 to 7. At H = 3 the growth term is ((1 + g_2)(1 + g_3)(1 + g_4))^(1/3) − 1.

Without a positive market cap the income term is nil and the basis says "unavailable".

### 5.11 Flags

In order: `sbc-basis-unknown`; `path-on-eps`, `few-analysts`; the ROIC flags of 4.5, the `line-not-presented` flags, then `charge-zeroed` or `return-floored`; `growth-above-return`; the trailing flags (`margin-flag`, `equity-raise`, `negative-fcf`, `heavy-capex`, `large-nri`); `long-runway-high-growth`; `value-spread`. The result puts the assembly's flags and the classifier's checks before these, and keeps the first flag of each code.

`long-runway-high-growth` fires on a 20-year runway when the belief or the implied growth is 10% or more.

### 5.12 Tagged inputs

DATA: the fiscal years on file, price, diluted shares, next earnings date, daily closes; market cap, trailing revenue, operating income, EPS, dividends, buybacks and stock issued; the aggregate ROIC and the runway return (estimates under the intangibles method when invested capital took the as-reported total); the newest tax rate (with its country, year and source); moat score; GuruFocus EPS and EPS without non-recurring items; trailing stock compensation; NTM EPS and NTM net income; the two path steps; street trailing EPS. RULE: r, g_T, the moat class, the margin of safety, the terminal return, the runway years, the belief with its sales class.

### 5.13 Worked numbers

The tests pin these. Terminal multiple at r 9%, g_T 3%, within 0.05: 17.2× at an infinite return, 15.5× (exactly 15.45) at 30%, 13.7× at 15%, 13.2× at 13%, 11.4× at 9%. The fade, the payout floor, the marginal return and the value figures of calibration spec section 7 (value 24,941.95 on its fade path at a 14.9% runway return and a 13% terminal; 19,699.10 without the fade; 20,520.66 with runway 5).

## 5a. The revenue-growth route (High Growth and Young Growth)

Damodaran's revenue DCF on the firm, one route for both phases: year 1 from the quarterly consensus revenue, years 2 and 3 from the annual consensus, the year-3 rate held to year 5 and faded to g_T by year 10; an operating margin that moves in a straight line to the mature peers' median; reinvestment at a sales-to-capital ratio; the free cash flow and the terminal discounted at r; then debt and cash to equity.

Here N is the explicit period, the years forecast one by one before the terminal value: H + F = 10 years whatever the moat, with H = `high_growth_years` (5) and F = `fade_years` (5). C is `margin_convergence_year` (10).

### 5a.1 Which rows, and the refusals

A company the classifier puts in High Growth or Young Growth (3.5, rule 4b), past the guards of 5.1. The result's route is `revenue-growth`; the phase says which of the two it is.

The route's own refusals, in this order:

1. "no trailing revenue": trailing revenue missing or not positive;
2. "no trailing operating income": without it there is no trailing margin to start from (5a.4);
3. "no statutory tax rate": no rate for the newest fiscal year (4.3);
4. "incomplete NTM consensus" (5a.2);
5. "no positive consensus revenue" (5a.2);
6. "consensus revenue falls to zero or below within the path" (5a.2);
7. "no target margin: <n> mature peers" (5a.4);
8. "no sales-to-capital" (5a.5);
9. "value not positive under the reinvestment charge" (5a.9).

What a refusal keeps beside the price facts every result carries: refusals 1 to 5 nothing; refusal 6 the path's flags; refusal 7 the rebuild keys (5a.14), the margin the price needs (5a.10) and the path's, the capital build's and the bridge's flags and `peers-from-industry` (5a.13); refusal 8 those flags and no intermediates; refusal 9 every value-side intermediate, the margin the price needs and every flag of 5a.13. A row with neither a target margin nor a sales-to-capital gives refusal 7, its margin the price needs None.

### 5a.2 Year 1 and the path

Year 0 is trailing revenue (4.2). Year 1 is the NTM consensus revenue: the sum of the revenue means of the NTM quarters, picked as 5.2 picks them (the first four quarterly consensus periods ending after the trailing period end, by period end, each ending 80 to 100 days after the one before). Without four such quarters, or with one that lacks a revenue mean, the row is refused "incomplete NTM consensus"; the quarters' EPS means are not needed here. An NTM revenue at or below zero is refused "no positive consensus revenue".

    g_1 = NTM revenue ÷ trailing revenue − 1

The base year is 5.3's: the fiscal year that holds most of the four NTM quarters, a tie taking the later. The path reads the annual consensus revenue for the base year and the next two:

- a revenue mean of zero whose revenue analyst count is missing or zero is no estimate;
- step g_2 = revenue(base + 1) ÷ revenue(base) − 1, step g_3 = revenue(base + 2) ÷ revenue(base + 1) − 1; a step is missing when either year has no estimate or the earlier is not positive;
- a missing step holds the rate of the year before: g_2 takes g_1, and g_3 takes g_2 as resolved. The row is flagged `path-held`, naming the fiscal years that left a step missing (a held step's earlier year when it has no estimate or is not positive, its later year when it has no estimate) and the rate each held year took;
- a resolved g_2 or g_3 at or below −100% refuses the row "consensus revenue falls to zero or below within the path";
- a present step whose landing year has fewer than 5 revenue analysts, or no count, flags `few-analysts`. The count is FMP's revenue analyst count. A held step lands on no consensus and is never thin.

### 5a.3 Years 4 to 10

Years 4 to H grow at the held rate: g_3 as resolved, capped at the sales class's 90th-percentile five-year sales growth (the class as 5.4 picks it from trailing revenue; the cap is the class's `sales_p90_5y`), or the rate the implied-growth solve tries (5a.10), which the cap does not touch. When g_3 is above the cap, the row is flagged `consensus-above-base-rate` naming both rates and the class, and `revenue_path.hold` carries the cap so a price refresh rebuilds the same path; the consensus steps g_2 and g_3 are not capped. Years H + 1 to N fade from the held rate to g_T in F equal steps,

    g_t = g_T + (held rate − g_T) × (N − t) ÷ F, for t = H + 1 … N,

so g_N = g_T exactly. With H = 5 and F = 5, years 4 and 5 hold and years 6 to 10 fade. A held rate below g_T rises to g_T on the same line.

    revenue_1 = NTM revenue
    revenue_t = revenue_{t−1} × (1 + g_t), for t = 2 … N

### 5a.4 The margin path and the target margin

The margin starts at the trailing operating margin, m_0 = trailing operating income ÷ trailing revenue, and moves in a straight line to the target margin m*, which it reaches in year C and keeps:

    m_t = m_0 + (m* − m_0) × min(t, C) ÷ C, for t = 1 … N

A trailing margin above the target moves down the same line.

**The dollar ramp.** The margin path stands for a trailing margin m_0 at or above −100% (`loss_ramp_margin_bound`). Below it the loss is larger than revenue, a cost base rather than a margin, and operating income moves instead in dollars, in a straight line, from the trailing operating income to the target margin's share of revenue in year C, as the Start-up ramp of 6b.2 does:

    E_0 = m_0 × revenue_0, the trailing operating income
    E* = m* × revenue_C
    EBIT_t = E_0 + (E* − E_0) × t ÷ C, for t = 1 … C
    EBIT_t = m* × revenue_t, for t = C + 1 … N

When C is past N, revenue_C is not on the path: E* is m* × revenue_N, reached at year C, so year N's margin is below the target, as the margin path's is. Each year's margin is EBIT_t ÷ revenue_t, and `margin_path.by_year` carries it. Tax, the carry, NOPAT, reinvestment, the terminal and the bridge are 5a.5 to 5a.9's on these EBITs. The row records `margin_path.ramp`, "dollars" on the ramp and "margin" on the margin path, cites `loss_ramp_margin_bound` as a RULE input, and is flagged `margin-ramp-in-dollars`, "The trailing loss is larger than revenue (margin −150.0%), so operating income moves in dollars from −$15,000.0 million to the target margin's $7,034.3 million by year 10, as the Start-up ramp does." A trailing margin of exactly −100% keeps the margin path.

**The mature peers.** The candidates are the symbols of the latest usable `stock-peers` response stored for the company (section 2), in its order, in the exchange form (`BRK.B`), the company itself and repeats dropped. A candidate is kept when the latest universe lists it (the admitted companies of the newest refresh that admitted any) and its stored fiscal years classify, on the spot, as Mature Growth or Mature Stable on the deciles the company is valued on (3.3). A candidate outside that universe, without statements, unclassified or in another phase is dropped. Without deciles the company has no peers, and without a stored response no candidates. No vendor call is made for a peer: its figures come from the statements stored for it, its invested capital and NOPAT built by 4.4 at the statutory rate of its own country (4.3):

- its margin: the ten-year aggregate operating margin, Σ operating income ÷ Σ revenue over the last ten of its fiscal years that have both and a positive revenue, with the count of those years; none without such a year;
- its sales-to-capital: the revenue of its newest kept ROIC year (4.5) ÷ that year's average invested capital, both of the same fiscal year; none without a kept year, without a revenue for that year, or with that capital at or below zero;
- its ROIC: its ten-year aggregate (4.5), none when unavailable;
- its market cap: the one on its row in the latest universe.

**The industry fallback.** When the candidates kept leave fewer than `peer_min` peers with a margin on `peer_margin_min_years` years or more, the peers are instead the mature companies of the company's own FMP industry: every company of the latest universe whose row carries the same industry, the company itself excluded, whose fiscal years classify on the spot as Mature Growth or Mature Stable on the same deciles, the largest `industry_peer_max` of them by market cap (a company without one last, ties in symbol order), their figures read as above. The kept candidates are dropped, not merged. The row is flagged `peers-from-industry`, naming the count the candidates left, the industry and the count taken, whether the row is then valued or still refused for the target margin or for its sales-to-capital; such a row also cites `industry_peer_max` as a RULE input. A company without an industry on its universe row has no fallback. Without a stored response the candidates are none and the fallback applies.

**The target margin.** m* is the median margin of the peers with a margin on at least 5 fiscal years (`peer_margin_min_years`). With fewer than 3 such peers (`peer_min`), the row is refused "no target margin: <n> mature peers", n counting them. The row records those peers with their margins and market caps, their count, the lowest and the highest margin, and the largest of them by market cap with its margin (none when none has a market cap); the largest peer sets nothing.

### 5a.5 Sales-to-capital and reinvestment

Sales-to-capital is the revenue a dollar of new invested capital buys. The route takes, in this order:

1. **The company's own five-year marginal measure**, over the kept ROIC years of 4.5: (revenue_last − revenue_first) ÷ (capital_last − capital_first), "last" the newest kept year and "first" the kept year 5 positions earlier (`marginal_return_span_years`), capital the average invested capital, revenue that fiscal year's. Used when it is usable: capital grew, by at least a fifth of the first year's capital in size (`marginal_capital_growth_min`), and revenue grew, and the measure is at least half the mature peers' median of step 2 (`own_sales_to_capital_min_share`, 0.5) when that median exists. With no peers' median the own measure stands on the first two conditions. A measure below the bound is not usable and the peers' median is used; the row cites `own_sales_to_capital_min_share` as a RULE input. There is no own measure with fewer than six kept years, with either year lacking a revenue, or with no change in capital.
2. **The mature peers' median**: the median of the positive sales-to-capital among all the peers of 5a.4, when at least 3 (`peer_min`) are positive.
3. Neither: the row is refused "no sales-to-capital".

The row records the measure used ("own" or "peers", none when neither stands), the own measure and whether it is usable, whether the bound alone rejected it (`own_below_bound`), the peers' median and the value used.

Reinvestment in year t pays for year t + 1's revenue; year N pays for the terminal growth at the terminal return (5a.7), as the mature routes' year N does:

    reinvestment_t = max(0, (revenue_{t+1} − revenue_t) ÷ sales-to-capital), for t = 1 … N − 1
    reinvestment_N = terminal NOPAT × g_T ÷ terminal return

A year before a fall in revenue reinvests nothing, never a negative amount; year N has no floor. The terminal NOPAT is year N's at the full tax rate (5a.7).

### 5a.6 Tax and NOPAT

    EBIT_t = revenue_t × m_t, or on the dollar ramp 5a.4's EBIT_t

The tax rate is the newest fiscal year's statutory rate (4.3), in every year. Tax is charged after the forecast's own losses, the carried loss starting at zero: a year whose EBIT is below zero pays no tax and adds its size to the carried loss; any other year pays

    tax_t = max(0, EBIT_t − carried loss) × tax rate

and reduces the carried loss by EBIT_t, not below zero.

    NOPAT_t = EBIT_t − tax_t

No history of tax losses is stored, so a forecast with a year whose EBIT is below zero, or a trailing margin m_0 below zero (a trailing loss implies losses the store does not hold), is flagged `tax-loss-history-unknown`.

### 5a.7 The free cash flow, the terminal and the firm value

    FCFF_t = NOPAT_t − reinvestment_t, for t = 1 … N
    terminal NOPAT = EBIT_N × (1 − tax rate) when EBIT_N > 0, else EBIT_N
    terminal value = terminal NOPAT × (1 + g_T) × (1 − g_T ÷ terminal return) ÷ (r − g_T)
    firm value = Σ_{t=1..N} FCFF_t ÷ (1 + r)^t + terminal value ÷ (1 + r)^N

The terminal multiple is 4.8's. A negative free cash flow is the method, not a refusal. The terminal value and reinvestment_N read year N's operating income at the full statutory rate, untaxed when it is not positive: a carried loss that outlasts year N − 1 shields year N's own NOPAT, and so FCFF_N, but never the perpetuity. When the carry ends before year N, as in the worked numbers, the terminal NOPAT is NOPAT_N.

The terminal return is 4.7's moat rule on the return on new capital at the target margin:

    return on new capital = m* × (1 − tax rate) × sales-to-capital

Narrow or None moat: r. Wide moat: that return, capped at 4.7's cap (r plus the spread, 13% at the defaults) and never below r. The runway return of 4.6 does not enter this route's charge; the cross-check reads it (5a.11).

### 5a.8 The required return

r in every year and in the terminal. Under the band of every valued row on this route the drawer says so: "Discounted at the required return of <r> in every year; Damodaran's template starts higher and falls to it by year 10".

### 5a.9 Equity and the value a share

    equity = firm value − debt + cash
    value a share = equity ÷ diluted shares

From the newest annual balance sheet: debt is short-term plus long-term debt (`shortTermDebt`, `longTermDebt`), cash is cash and equivalents plus short-term investments (`cashAndCashEquivalents`, `shortTermInvestments`). No other line enters. A line without a value counts as nil, and assembly's note on the input names it ("longTermDebt not presented"); a figure with both its lines missing is unknown and counts as nil. Either case flags `line-not-presented:debt` or `line-not-presented:cash`, the sentence naming the missing lines.

A value a share at or below zero refuses the row "value not positive under the reinvestment charge", which keeps its figures (5a.1). Otherwise the levels, the designation and the validity are 4.10's, with the moat's margin of safety.

### 5a.10 What moves with the price

- **The implied growth**: the held rate of years 4 to H at which the value a share equals the price, the fade recomputed from it; years 1 to 3, the margin path, the terminal return and the sales-to-capital stay. On the dollar ramp (5a.4) each trial rebuilds the ramp from the trial path's revenue_C. Solved as 5.7 solves: a scan from −50% to 200% in steps of 1% for the first sign change, then bisection to 1e-7; None when the scan finds no sign change.
- **The margin the price needs**: the target margin at which the value a share equals the price, the margin path, or the dollar ramp, rebuilt from it and the terminal return re-read at each trial from the return on new capital there (5a.7). Solved the same way between the policy's bounds, −50% and 100% (`implied_margin_bounds`); None without a sales-to-capital or when the scan finds no sign change. It is computed on a valued row and on the two refusals that keep the rebuild keys, "no target margin" and "value not positive".
- **The multiples and the growth share** of 5.9: trailing P/E reported and clean; the forward P/E on the anchor's NTM EPS (5.2) when the anchor stands, none when it refuses; a P/E only for a positive EPS; the growth share of price when EPV exists.
- **The expected return** of 5.10, its growth term on the revenue path's own rates over the repricing horizon, g_T past year N.
- **The cross-check's implied growth** (5a.11).

The rebuild keys (5a.14), with the policy's r, g_T, margin convergence year and `loss_ramp_margin_bound` (and, for the margin solve, its bounds and the wide-moat cap), rebuild the path, the margin path or the dollar ramp, and the charge, so a price refresh moves each of these figures from the intermediates alone (section 10). `margin_start` and `revenue_path` give the ramp's E_0 and revenue_C.

### 5a.11 Sensitivities, the cross-check and the implied-return check

- **By target margin**: the value a share at the lowest, the median and the highest margin of the counted peers, keys `low`, `median`, `high`, each with its own terminal return from the return on new capital at that margin, and on the dollar ramp its own ramp to that margin. `median` is the row's value. The value-spread flag reads the three on 5.8's rule, with one addition: when the value at the lowest margin is at or below zero and the median's is positive, where 5.8's rule is silent, the flag fires with "The value is at or below zero at the lowest mature-peer margin of <x.x%> and <y.yy> a share at the median, so the spread across the peers' margins is unbounded."
- **The growth-route cross-check**: as on a Mature Stable row (6.4), `growth_route` carries the Mature Growth route's value a share under the row's own moat and returns, with the keys that rebuild it and its implied growth at the price, or only the reason that route would refuse. It sets nothing.
- **The implied-return check**: the return on new capital at the target against the median ten-year aggregate ROIC of the peers of 5a.4 that have one. Above that median, the row is flagged `return-above-peers` with both figures. With no peer ROIC there is no check. It flags only.

### 5a.12 Young Growth

The same route: on the same inputs a Young Growth row has High Growth's value, levels and figures. Its intermediates add `failure_probability`, with no value and the reason "no survival table fits a listed company above $2 billion"; the value is the going-concern value, flagged `failure-not-charged`. The drawer shows the failure probability as unavailable with that reason, and says the value range is not computed in tier 1.

### 5a.13 Flags

In order: `sbc-basis-unknown`, when the cross-check has a value and its anchor's stock-compensation basis is unknown (5.2); the path's, `path-held`, `consensus-above-base-rate` (5a.3), then `few-analysts`; the capital build's, the ROIC flags of 4.5 then the `line-not-presented:<field>` flags of the ROIC years (4.4); `line-not-presented:debt`, then `line-not-presented:cash`; `peers-from-industry` (5a.4); `tax-loss-history-unknown` (5a.6); `margin-ramp-in-dollars` on the dollar ramp (5a.4); `return-above-peers`; `failure-not-charged` on a Young Growth row; the trailing flags (`margin-flag`, `equity-raise`, `negative-fcf`, `heavy-capex`, `large-nri`); `value-spread` over the three target margins (5a.11). The result puts the assembly's flags and the classifier's checks before these, and keeps the first flag of each code.

Never raised here: `path-on-eps`, `charge-zeroed`, `return-floored`, `growth-above-return`, `long-runway-high-growth`, nor the cross-check's earnings-path flags. The charge does not read the runway return, and the path is on revenue.

### 5a.14 Intermediates and tagged inputs

Intermediates: `ntm_revenue`; `path` (base_year, the revenue analysts of the two landing years, which steps were held, the sales class and its cap); `path_steps`, g_2 and g_3 as resolved; `growth_rates`, years 1 to N; `margin_path` (start, target, by_year, ramp, "margin" or "dollars"); `target_margin` (value, count, low, high, largest_symbol, largest_margin, the counted peers with each one's margin and market cap, source (fmp or industry) and industry); `revenue_by_year`, `ebit_by_year`, `tax_by_year`, `nopat_by_year`, `reinvestment_by_year`, `fcff_by_year`; `terminal_roic`, `terminal_nopat` (5a.7), `terminal_value`, `firm_value`, `equity`, `value_per_share`; `value_by_margin`; `return_on_new_capital`, `peer_roic_median`; `failure_probability` on Young Growth only; `eps`, `epv`, `dividend_yield`, `net_buyback_yield`, `income_basis`, `price_facts`, `growth_route`; the rebuild keys; and at the price `implied_growth`, `implied_margin`, `multiples`, `growth_share`, `expected_return` and the cross-check's `implied_growth`.

The rebuild keys: `revenue_path` (revenue0, ntm_revenue, the consensus steps as found with None for a missing one, hold None, or the cap when it binds, high_growth_years, fade_years), `margin_start`, `tax_rate`, `moat`, `debt`, `cash`, `shares` and `sales_to_capital` (used, own, own_usable, own_below_bound, peers, value); on a valued row `margin_path`'s target and `terminal_roic` complete them. A refusal that keeps them keeps the moat class for the price refresh; the screen shows the moat on a valued row only.

Tagged inputs. DATA: the fiscal years on file, price, diluted shares, next earnings date, daily closes; market cap, trailing revenue, operating income, EPS, dividends, buybacks and stock issued; the aggregate ROIC and the runway return, as in 5.12, though neither enters this route's charge; the newest tax rate; the moat score; GuruFocus EPS and EPS without non-recurring items; `ntm_revenue`, from the quarterly consensus; `path_step_2` and `path_step_3`, the annual consensus steps as found, a held one empty with the note "no consensus step: the year holds the rate of the year before"; `target_margin`, source "FMP stock-peers and the peers' statements" (on the industry fallback, "the universe's <industry> industry and the peers' statements", the note naming the industry), note "the median ten-year operating margin of <n> mature peers"; `sales_to_capital`, either the own measure cited to the statements (an estimate under the intangibles method when invested capital took the as-reported total, 4.4) with the note "the company's own five-year marginal measure", or the peers' median cited to the peers' source with the note "the mature peers' median; the own measure is not usable", or, when the bound of 5a.5 alone rejected the own measure, "the mature peers' median; the own measure, 0.50, is below half the peers' median, 2.50" (on the industry fallback, "the mature peers' median (<industry> industry); " and the same reason); `debt` and `cash`, cited to the statements, with assembly's note naming a missing line. RULE: r, g_T, the moat class, the margin of safety, the terminal return, `high_growth_years`, `held_growth_cap` with the class and whether it binds in its note, `fade_years`, `margin_convergence_year`, `loss_ramp_margin_bound` on a row on the dollar ramp, `peer_min`, `own_sales_to_capital_min_share` on a row whose own measure the bound rejected, and on a row whose peers are the industry fallback's, `industry_peer_max`.

### 5a.15 Worked numbers

The tests pin these, to 0.01 unless a tolerance is named. r 9%, g_T 3%, tax 21%, None moat (terminal return 9%); trailing revenue 1,000, NTM revenue 1,300, consensus steps 25% and 20%; trailing margin −10%, target margin 20%; sales-to-capital 2.0; debt 100, cash 300, 100 shares.

- Growth, years 1 to 10: 30%, 25%, 20%, 20%, 20%, 16.6%, 13.2%, 9.8%, 6.4%, 3%.
- Revenue: 1,300.00; 1,625.00; 1,950.00; 2,340.00; 2,808.00; 3,274.13; 3,706.31; 4,069.53; 4,329.98; 4,459.88.
- Margins: −7%, −4%, −1%, 2%, 5%, 8%, 11%, 14%, 17%, 20%.
- Tax on EBIT of −91.00; −65.00; −19.50; 46.80; 140.40; 261.93; 407.69; 569.73; 736.10; 891.98: 0; 0; 0; 0; 2.46; 55.01; 85.62; 119.64; 154.58; 187.32. NOPAT is −91.00 in year 1 and 137.94 in year 5. The carried loss of 175.50 is used up in year 5, so the terminal NOPAT, 891.98 × 0.79 = 704.66, is year 10's NOPAT.
- The carry: EBIT of 100, −50, 80, 10 at a rate of 25% pays 25, 0, 7.5, 2.5.
- Reinvestment: 162.50; 162.50; 195.00; 234.00; 233.06; 216.09; 181.61; 130.23; 64.95; 234.89, year 10 at the terminal return.
- Free cash flow −253.50 in year 1 and 469.77 in year 10; terminal value 8,064.46; firm value 3,290.57; equity 3,490.57; value a share 34.91.
- Value a share at target margins of 10% and 30%: 10.09 and 59.64; at a sales-to-capital of 3.0: 38.50; at a terminal return of 13%: 40.45.
- From a trailing margin of −50% the losses outlast year 9: year 10 pays no tax on its EBIT of 891.98, so its NOPAT is 891.98 and its free cash flow 657.09, while the terminal NOPAT is 704.66, reinvestment_10 234.89 and the terminal value 8,064.46; value a share 9.32. At a target margin of −5%, EBIT_10 is −222.99 and the terminal reads it untaxed.
- Return on new capital at the target: 0.20 × 0.79 × 2.0 = 0.316.
- At a price of 25.00, within 1e-5: implied growth 0.086275, margin the price needs 0.160014. At a price of 34.9057 both solves return 0.20 within 1e-4. With a Wide moat at 40.45 the margin solve returns 0.20 within 1e-3, the terminal at the 13% cap; at a 5% target the return on new capital is 7.9%, below r, so the terminal is r, and, with cash 1,000 (at the stated cash of 300 the value at a 5% target is below zero), the solve at that target's value returns 0.05 within 1e-5.
- The dollar ramp from a trailing margin of −150% (operating income −1,500), below the bound: EBIT −1,260.80; −1,021.60; −782.41; −543.21; −304.01; −64.81; 174.38; 413.58; 652.78; 891.98, the margins from −97.0% in year 1 to 20% in year 10. The carried loss shields every year through year 10 (NOPAT_10 891.98, untaxed); the terminal NOPAT is 704.66. Free cash flow −1,423.30 in year 1 and 657.09 in year 10; terminal value 8,064.46; firm value −31.33; equity 168.67; value a share 1.6867 within 1e-4. The margin path from −150% would give −61.94. At a price of 25.00 the margin the price needs is 0.277164 within 1e-5. With C at 5, years 5 to 10 earn the target on each year's revenue; with C at 12, year 10 is ten twelfths of the way to 20% of year 10's revenue.
- Own sales-to-capital, kept years with revenue and average capital from (1,000, 400) to (2,500, 900) five positions later: 1,500 ÷ 500 = 3.0, usable. Capital from 400 to 420 instead: 75.0, not usable, capital grew 5%. Falling revenue: not usable. Five kept years, or a year without revenue: none. Against a peers' median of 2.5, an own measure of 0.5 is below the bound of 1.25 and the median is used; 1.3 is used; 0.5 with no peers' median is used.
- Peers with margins of 10% on 10 years, 30% on 8, 20% on 6 and 40% on 3: target 20% on 3 peers, low 10%, high 30%, the largest by market cap the 30% peer; two peers give none. Peers' sales-to-capital 2.5, 1.5 and 3.0: median 2.5; two give none. Peers' ROIC 12%, 20% and 15%: median 15%.

The route's tests pin the refusal order, the flag order, the `path-held` and `few-analysts` sentences, Young Growth's equality with High Growth, and a price refresh that rebuilds every price-side figure from the intermediates.

## 6. The Mature Stable route

The stable-growth value on normalized trailing earnings, charged as the Mature Growth route charges.

### 6.1 Refusal

E = trailing net income − the non-recurring gap × diluted shares. A missing or non-positive E refuses: "no positive trailing earnings". The refusal keeps the growth-route cross-check of 6.4, with its value a share and its implied growth at the price or only its reason, and the intermediates `e_trailing` (E, or none when net income is missing), `nri_gap`, `eps`, `shares`, `moat` and `price_facts`. It raises no flag of its own and cites no input beyond the ones every result carries.

### 6.2 Normalized earnings

When the margin flag (8) fires and both the trailing operating margin and the ten-year median margin are positive, E is scaled by median margin ÷ trailing margin, and the row says so. Otherwise E stands.

### 6.3 The value

The path grows at g_T in every year from E (year 1 is E, with no (1 + g_T) factor) to the moat's runway N. The value is section 4.8 on that path with the row's charge: the runway return in years 1 to N − 1, the terminal return in year N and the terminal, off in the runway years when 4.6 turns it off. When the runway return equals the terminal return with the charge on, this equals the one-stage formula E × (1 − g_T ÷ terminal return) ÷ (r − g_T). A row floored at r in every year values at EPV. A runway return above the terminal return, or a charge off, lifts the value, and more for a longer runway.

EPV = E ÷ r is shown as the no-growth value. The levels sit on the stable-growth value.

### 6.4 The growth-route cross-check

On a valued row and on the refusal of 6.1: when the row's inputs allow the Mature Growth route (a positive anchor, a path without refusal), the intermediates carry that route's value a share under the row's own moat and returns, with the keys that rebuild its path, and its implied growth at the price. When the growth route would refuse, only its reason is carried. The levels and the designation never read it.

### 6.5 Expected return, multiples, flags and inputs

The expected return of 5.10 with H rates of g_T. Trailing P/E reported and clean; no forward P/E. Flags: the ROIC flags of 4.5 and 4.6, `charge-zeroed` and `return-floored` included, then the trailing flags. Never `sbc-basis-unknown`, `path-on-eps`, `few-analysts`, `growth-above-return`, `long-runway-high-growth` or `value-spread`; so a thin consensus behind the cross-check does not show on a stable row, a known gap. Inputs: the common DATA inputs of 5.12 plus trailing net income; the RULE inputs plus the runway years and a belief of g_T.

## 6a. The Decline route

Damodaran's run-off on the firm: years 1 to 3 from the consensus revenue, then the consensus revenue where it reaches past year 3 on enough analysts, then the five-year trend's decline rate fading to zero by year N; one normalized operating margin in every year; the capital a fall in revenue releases, recovered in part; a flat terminal on year N's revenue; then debt and cash to equity, the net current asset value as a floor, and the distress-sale value weighted by the ten-year probability of default of a synthetic rating.

Here N is `runoff_years` (10) whatever the moat; K is the last year the consensus gives (6a.2); d is the decline rate (6a.2); m_n the normalized margin (6a.3).

### 6a.1 Which rows, and the refusals

A company the classifier puts in Decline (3.5 rule 2), past the guards of 5.1. The result's route is `decline`.

The route's own refusals, in this order:

1. "no trailing revenue": trailing revenue missing or not positive;
2. "no trailing operating income";
3. "no statutory tax rate": no rate for the newest fiscal year (4.3);
4. "consensus revenue falls to zero or below within the path" (6a.2);
5. "no sales-to-capital" (6a.4);
6. "value not positive in the run-off" (6a.7).

What a refusal keeps beside the price facts every result carries: refusals 1 to 3 nothing; refusal 4 the path's flags; refusal 5 the path's flags and `line-not-presented:debt`, `:cash` and `:totalLiabilities`, and no intermediates; refusal 6 every intermediate of 6a.10 but the three at the price, every flag, and its inputs, the tagged inputs a valued row cites (6a.10).

### 6a.2 The revenue path

Year 0 is trailing revenue (4.2). Years 1 to 3 are 5a.2's consensus path: year 1 the NTM consensus revenue, g_1 = NTM revenue ÷ trailing revenue − 1; years 2 and 3 the annual consensus revenue steps from the base year, a missing step holding the rate of the year before (`path-held`, with 5a.2's sentence), a present step landing on a year with fewer than 5 revenue analysts, or no count, flagged `few-analysts`. Nothing is capped: 5a.3's cap is the growth route's.

**Past year 3** the path keeps reading the annual consensus revenue, one fiscal year at a time from base + 3, each step from the year before's consensus revenue, while the year has a revenue mean above zero and at least `analyst_min` (5) revenue analysts. The first year that fails either test ends the consensus at the year before, with no refusal and no flag: nothing is held past year 3, a thin year is not read, so `few-analysts` never names a year past 3, and a year at or below zero is not read, so no step past year 3 falls 100% or more. No step runs from a base + 2 without a consensus revenue above zero, so a year 3 held for want of base + 2 ends the consensus at year 3 (a year 3 held for want of base + 1 still reads year 4 from base + 2). K is the last year the consensus gives, 3 at least and N at most: a year past N is not read. Each step past year 3 is cited as a DATA input (6a.10).

A resolved g_2 or g_3 at or below −100% refuses the row "consensus revenue falls to zero or below within the path".

**The fade.** From year K + 1 the rate falls in a straight line from the decline rate d to zero by year N:

    d = max(−50%, min(0, five-year revenue slope ÷ revenue of the last fiscal year))
    g_t = d × (N − t) ÷ (N − K), for t = K + 1 … N
    revenue_t = revenue_{t−1} × (1 + g_t)

so g_N = 0. With K = 3 and N = 10, g_4 = d × 6 ÷ 7 and the path reaches zero in seven steps; a consensus to year N leaves no year to fade.

The slope is the classifier's revenue trend (3.4), in dollars a year. A trend that shrinks revenue faster than 50% a year takes −50%, the lower bound of the implied-decline scan (4.1a), and the row is flagged `decline-rate-floored`, "The five-year trend shrinks revenue faster than 50% a year; the run-off uses −50%."

An incomplete NTM consensus (5a.2: no four consecutive quarters, or one without a revenue mean) or an NTM revenue at or below zero does not refuse: years 1 to 3 shrink at d, the annual consensus is not read, and the fade runs from year 4 as with K = 3. The row is flagged `path-on-trend`, "No usable consensus: years 1 to 3 shrink at the decline rate, <d>, which fades to zero by year <N>."

A consensus rate above zero in years 1 to K, as found, flags `consensus-recovery`, naming each such year and its rate: "The consensus has revenue growing <g> in year <t> while the decline rate is <d>." A held step is not the consensus's and is not named.

Both sentences name the decline rate as used, signed (−4.0%): on a floored row −50%, not the trend's own figure.

### 6a.3 Margin, tax and NOPAT

The operating margin held in every year and in the terminal is the normalized margin m_n: the median of the operating margins (3.4) of the last five fiscal years that have one, when at least three do; else the trailing margin m_0 = trailing operating income ÷ trailing revenue.

    EBIT_t = revenue_t × m_n

Tax and NOPAT by 5a.6, the carried loss starting at zero, flagged `tax-loss-history-unknown` when a year's EBIT is below zero or m_0 is below zero. The `margin-flag` (section 8) reads m_0, as on every route. The row records the margin used, which one ("median" or "trailing"), the median (none with fewer than three margins), m_0, and the fiscal years and margins read.

### 6a.4 Capital released, reinvestment and sales-to-capital

    release_t = max(0, (revenue_{t−1} − revenue_t) ÷ sales-to-capital) × runoff_recovery
    reinvestment_t = max(0, (revenue_t − revenue_{t−1}) ÷ sales-to-capital)
    FCFF_t = NOPAT_t − reinvestment_t + release_t, for t = 1 … N

A year whose revenue falls releases capital, recovered at `runoff_recovery` (0.6); a year whose revenue rises reinvests in full. Both fall in the year of the change.

Sales-to-capital, in this order:

1. **Own-latest**: the revenue of the company's newest kept ROIC year (4.5) ÷ that year's average invested capital, as 5a.4 measures a peer's. None without a kept year, without a revenue for that fiscal year, or with that capital at or below zero.
2. **The mature peers' median** of 5a.5 step 2, the peers of 5a.4 with their industry fallback. When the industry's peers give it, and only then, the row is flagged `peers-from-industry`.
3. Neither: the row is refused "no sales-to-capital".

The row records the measure used ("own-latest" or "peers") and its value.

### 6a.5 The terminal and the going-concern value

    revenue_{N+1} = revenue_N
    NOPAT_{N+1} = revenue_N × m_n × (1 − tax rate) when m_n is above zero, else revenue_N × m_n
    FCFF_{N+1} = NOPAT_{N+1}
    terminal value_N = FCFF_{N+1} ÷ r
    firm value = Σ_{t=1..N} FCFF_t ÷ (1 + r)^t + terminal value_N ÷ (1 + r)^N
    going-concern value a share = (firm value − debt + cash) ÷ diluted shares

The run-off ends in a business of year N's size that neither grows nor shrinks: no capital is released in the terminal (revenue is flat) and none reinvested (no growth). The terminal NOPAT is at the full tax rate, the carried loss left out, as 5a.7's. Debt and cash are 5a.9's, each line nil when missing, with `line-not-presented:debt` and `:cash`. r in every year. The moat enters the margin of safety of the levels (4.10) and nothing else.

### 6a.6 The liquidation floor

From the newest annual balance sheet:

    NCAV = total current assets − total liabilities
    floored value a share = max(going-concern value a share, NCAV ÷ diluted shares), when NCAV is above zero

When NCAV a share is above zero and above the going-concern value a share and π is not 100% (an unavailable π included), the row is flagged `ncav-floor`, "The floored value is the net current asset value <x> a share; the run-off gives <y>." At π = 100% the floored value has no weight (6a.7, 6a.11) and the flag is not raised. A newest annual balance sheet without total liabilities, or none on file, gives no NCAV and no floor, flagged `line-not-presented:totalLiabilities`. Without total current assets there is no NCAV and no floor either.

### 6a.7 The distress probability and the distress-sale value

    value a share = floored value a share × (1 − π) + distress-sale value a share × π

π, the first rule that fits deciding, on 6a.5's debt and cash:

1. cash at or above a debt on file: π = 0, "no net debt";
2. net debt and a trailing interest expense (4.2) missing or zero: no rating; π is unavailable and the value is the floored value a share, flagged `distress-not-charged`, "No interest expense on file: the distress probability is unavailable and the value is the floored going-concern value." A company whose debt lines are both missing is treated the same, whatever its cash, since unknown debt is not "no net debt": no rating, π unavailable, the debt nil in the bridge (6a.5), flagged `distress-not-charged`, "No debt line on file: the distress probability is unavailable and the value is the floored going-concern value.";
3. otherwise the coverage is EBIT_n ÷ the trailing interest expense, with EBIT_n = trailing revenue × m_n and the expense as its size; an EBIT_n at or below zero is rated D whatever the coverage; else the rating is the `synthetic_rating` row whose coverage range holds the coverage (from its lower bound to below the next row's);
4. π = `default_probability_10y` of the rating.

    distress proceeds = distress_sale_fraction × firm value + cash
    distress-sale value a share = max(0, distress proceeds − debt) ÷ diluted shares

with `distress_sale_fraction` 0.6. A value a share at or below zero refuses the row "value not positive in the run-off", which keeps its figures (6a.1). Otherwise the levels, the designation and the validity are 4.10's, with the moat's margin of safety.

### 6a.8 The distress signals

Shown on every Decline row valued or refused for its value (refusal 6), never deciding the value; the five earlier refusals carry none:

- **Altman Z″**, on the newest annual balance sheet and its fiscal year's operating income: 6.56 × X1 + 3.26 × X2 + 6.72 × X3 + 1.05 × X4, with X1 = (total current assets − total current liabilities) ÷ total assets, X2 = retained earnings ÷ total assets, X3 = operating income ÷ total assets, X4 = stockholders' equity ÷ total liabilities. Below `z_distress` (1.1) the zone is "distress", above `z_safe` (2.6) "safe", else "grey". A missing line, or total assets or total liabilities at or below zero, gives no score. A "distress" zone flags `z-distress`, "Altman Z″ is <z>, in the distress zone below 1.1."
- **Piotroski F**, on the newest two annual balance sheets with their fiscal years' income and cash-flow lines, one point each: return on assets (net income ÷ total assets) above zero; operating cash flow above zero; return on assets higher than the year before's; operating cash flow above net income; long-term debt ÷ total assets lower than the year before's; the current ratio higher; no common stock issued (`commonStockIssuance` at or below zero); gross margin higher; asset turnover (revenue ÷ total assets) higher. A signal whose line is missing, a missing stock-issued line included, or whose ratio has a zero denominator, is not read and scores nothing; the row records how many signals were read. With fewer than two annual balance sheets there is no score. A score at or below `f_score_low` (1), with at least one signal read, flags `f-score-low`, "Piotroski F is <f> of <n read>: the low group of Piotroski (2000)."
- **Reinvesting in decline**: trailing capital spending above trailing depreciation and amortization, both in size and neither missing, while year N's revenue is below trailing revenue, flags `reinvesting-in-decline`, "Capital spending <x> exceeds depreciation <y> while revenue falls: Damodaran's denial."

### 6a.9 What moves with the price

The value, the levels and the validity stay. These are recomputed:

- the designation (4.10);
- **the implied decline rate**: the d at which the value a share, rebuilt from the rebuild keys with the consensus years 1 to K as found, the fade from that d, and the floor and π as built, equals the price. A scan from −50% to 0 in steps of 0.1%, bisected to 1e-7, returns the first root it finds scanning up from −50%; the value need not rise with d, so a second root is not sought. None when the scan finds no sign change;
- the multiples of 5.9: trailing P/E reported and clean; no forward P/E;
- the expected return of 5.10, its growth term the path's own rates (`growth_rates`) for years 2 to H + 1, and zero for a year past N.

A refused Decline row takes only the new price.

### 6a.10 Flags, intermediates and inputs

Flags, in order: `path-held`, `decline-rate-floored`, `path-on-trend`, `consensus-recovery`, `few-analysts` (years 2 and 3 only); `line-not-presented:debt`, `line-not-presented:cash`, `line-not-presented:totalLiabilities`; `peers-from-industry` when the industry's peers gave the sales-to-capital; `tax-loss-history-unknown`; `ncav-floor` (never at π = 100%); `distress-not-charged`; `z-distress`; `f-score-low`; `reinvesting-in-decline`; the trailing flags (`margin-flag`, `equity-raise`, `negative-fcf`, `heavy-capex`, `large-nri`). The result puts the assembly's flags and the classifier's checks before these, and keeps the first flag of each code. Never raised here: the ROIC flags of 4.5 and 4.6, `consensus-above-base-rate`, `return-above-peers`, `value-spread`, `failure-not-charged`, `path-on-eps`, `sbc-basis-unknown`, `growth-above-return`, `long-runway-high-growth`.

Intermediates: the rebuild keys; `moat`; `growth_rates`, years 1 to N; `revenue_by_year`, `ebit_by_year`, `tax_by_year`, `nopat_by_year`, `reinvestment_by_year`, `release_by_year`, `fcff_by_year`; `terminal_value`, `firm_value`, `equity` (the going-concern equity), `going_concern_per_share`, `ncav_per_share`, `floored_per_share`; `rating` (the rating, EBIT_n, the interest expense, the coverage, π, the coverage range of its table row, and the note "no net debt", "no debt line on file" or "no interest expense on file"); `distress_proceeds`, `distress_per_share`, `value_per_share`; `altman_z` (the fiscal year, X1 to X4, the score, the zone; none without a score); `piotroski_f` (the two fiscal years, the nine signals as read, the score, the count read; none with fewer than two balance sheets); `capex_vs_depreciation`; `eps`, `epv`, `dividend_yield`, `net_buyback_yield`, `income_basis`, `price_facts`; and at the price `implied_decline_rate`, `multiples` and `expected_return`.

The rebuild keys: `runoff_path` (revenue0, ntm_revenue, None without a usable consensus, the consensus steps for years 2 to K as found with None for a held one in years 2 and 3, consensus_years K, d, runoff_years), `margin` (6a.3), `tax_rate`, `sales_to_capital` (used, value), `runoff_recovery`, `debt`, `cash`, `shares`, `ncav`, `pi` (its value, rating and coverage) and `distress_sale_fraction`. With the policy's r they rebuild the value at any d (6a.9).

Tagged inputs. DATA: the fiscal years on file, price, diluted shares, next earnings date, daily closes; market cap, trailing revenue, operating income, EPS, dividends, buybacks and stock issued; the newest tax rate; the moat score; GuruFocus EPS and EPS without non-recurring items; `ntm_revenue`, `path_step_2` and `path_step_3` as 5a.14, each noted "no usable consensus: years 1 to 3 shrink at the decline rate" on a `path-on-trend` row, and one `path_step_<t>` for each consensus year t from 4 to K, cited as `path_step_2` is; `interest_expense`, the trailing expense cited to the statements; `sales_to_capital`, the own-latest measure cited to the statements (an estimate under the intangibles method when invested capital took the as-reported total, 4.4), noted "the company's own newest year: revenue over average invested capital", or the peers' median cited as 5a.14 cites it, noted "the mature peers' median; the company has no newest-year measure" (on the industry fallback naming the industry); `debt` and `cash`; the newest annual balance sheet's lines and its fiscal year's that Z″, F and NCAV read (`total_current_assets`, `total_current_liabilities`, `total_assets`, `total_liabilities`, `retained_earnings`, `equity`, `long_term_debt`, `revenue_fy`, `gross_profit_fy`, `operating_income_fy`, `net_income_fy`, `cfo_fy`, `stock_issued_fy`) and the year before's that F reads (the same names ending `_prior`), each noted with its fiscal year; `depreciation`, trailing. RULE: r, `runoff_years`, `runoff_recovery`, `distress_sale_fraction`, `synthetic_rating` (the lower bound of the row used, its range and the company's coverage in the note; none without a rating, the note saying why), `default_probability_10y` (the figure used; none without a rating), `z_distress`, `z_safe`, `f_score_low`, the moat class and the margin of safety, and `peer_min` and, on the industry fallback, `industry_peer_max` when the peers gave the sales-to-capital. Not cited: the aggregate ROIC, the runway return, g_T and the terminal return, which the run-off does not read. A row refused for its value (refusal 6) cites the same inputs.

### 6a.11 Chronic loss-makers

A normalized margin at or below zero makes EBIT_n at or below zero: with net debt the company is rated D, π = 100%, and its value is the distress-sale value alone, a fraction of a firm value at or below zero plus cash less debt, so usually zero; the floor has no weight at π = 100%, and `ncav-floor` is not raised. With net cash π is 0 and the value is the floored going-concern value, below zero when the run-off is. Either way the row is refused "value not positive in the run-off" and keeps every figure: the path, the margin, the rating, the signals and NCAV, with its inputs.

### 6a.12 Worked numbers

The tests pin these (spec 2026-11-03 13.1 and spec 2026-11-06 13.1), to 1e-9 a share. Trailing revenue 1,000 and operating income 80; fiscal margins 7%, 8%, 8%, 9%, 8% (m_n 8%); tax 25%; own sales-to-capital 2.0; the consensus −3% in years 1 to 3; d = −4%; r 9%; debt 200, cash 100, 100 shares; trailing interest 20 (coverage 4.0, A−, π 5%); current assets 300 and total liabilities 500 (NCAV −200, no floor).

- K = 3. Rates, years 1 to 10: −3%, −3%, −3%, −3.428571%, −2.857143%, −2.285714%, −1.714286%, −1.142857%, −0.571429%, 0.
- Revenue 970.00 in year 1 and 808.24 in year 10; free cash flow 67.20 and 48.49; FCFF_11 48.49 (no release); terminal value 538.83; firm value 607.48.
- Going concern 5.0748 a share; distress-sale value (0.6 × 607.48 + 100 − 200) ÷ 100 = 2.6449; value 5.0748 × 0.95 + 2.6449 × 0.05 = 4.9533 (method 0.8 gave 4.3180 on the same figures).
- The consensus reaching year 5 (base + 3 at +1% on 6 analysts, base + 4 at +2% on 6, base + 5 absent): K = 5; rates −3%, −3%, −3%, 1%, 2%, −3.2%, −2.4%, −1.6%, −0.8%, 0; revenue 940.24 in year 5 and 867.10 in year 10; FCFF_11 52.03; terminal value 578.07; firm value 622.19; value 5.0974; `consensus-recovery` names years 4 and 5. With base + 3 on 4 analysts, K = 3 and the row is 4.9533 with no `few-analysts`.
- No usable consensus: years 1 to 3 at −4%, then the fade; value 4.8626, `path-on-trend`.
- Cash 250: π = 0 and 6.5748. No interest expense with net debt: 5.0748, `distress-not-charged`. No debt line on file: no rating, 5.0748 + 2.00 = 7.0748 (the debt nil), `distress-not-charged`. Current assets 1,100 (NCAV 600): the floor 6.00, `ncav-floor`, value 6.00 × 0.95 + 2.6449 × 0.05 = 5.8322; with no interest expense as well, 6.00. A trailing margin of −1% on the same fiscal margins: the same value and rating. Fiscal margins −2%, −3%, −3%, −3%, −3%: D, firm value −241.32, value 0, refused; with cash 250, −1.9132 a share, refused.
- Value at d = 0: 5.2247; at d = −50%: 3.1251. At a price of 4.9533 the implied decline rate is −4%; at 4.00, −21.8%; at 3.00 none, the value at −50% being above the price.

## 6b. The Start-up route

No value by design (design.md 6.8): a Start-up row is a refusal that keeps its figures. What the price needs is stated as one number, the revenue in year 10 that, at the mature peers' margin, makes the company worth its price today; beside it, the net cash a share as a floor and the years the cash covers the trailing burn. The market and the share that would reach that revenue are the agent's to judge.

### 6b.1 Which rows, and the result

A company the classifier puts in Start-up (3.5 rule 1), past the guards of 5.1 that come before its route: no universe deciles, the assembly's refusal, a foreign filer, no positive price, no positive diluted share count. "No trailing figures" does not refuse a Start-up row: a pre-revenue company may lack them, and the route reads what exists.

Every Start-up row is the refusal "Start-up: no value by design", its route `start-up`, with no value, no levels and no designation (4.10), and with the intermediates and inputs of 6b.6. A figure the route cannot compute carries its own reason inside the intermediates; nothing refuses further.

### 6b.2 The price-implied requirement

    EV_price = market cap + debt − cash

The market cap is section 2's: the quote's, else the profile's, else the screener row's. Debt and cash are 5a.9's, each line nil when missing and flagged `line-not-presented:debt` or `line-not-presented:cash`. When EV_price is at or below zero the requirement is 0, the net cash covering the price, and the row is flagged `below-net-cash`, "The price is covered by net cash: market cap <x> against net cash <y>."

Otherwise the requirement is R10, the year-10 revenue at which a ten-year ramp is worth EV_price:

    R_t = R0 + (R10 − R0) × t ÷ 10
    EBIT_t = E0 + (m* × R10 − E0) × t ÷ 10, for t = 1 … 10

R0 is trailing revenue, 0 without one. E0 is trailing operating income, else the last fiscal year's, else 0. m* is the target margin (6b.3). A pre-revenue company has no margin, so operating income moves in dollars, not as a margin.

- Tax and NOPAT by 5a.6 at the newest fiscal year's statutory rate (4.3), the carried loss starting at zero.
- Reinvestment by 5a.5 at the sales-to-capital of 6b.3: reinvestment_t = max(0, (R_{t+1} − R_t) ÷ sales-to-capital) for t = 1 … 9, and reinvestment_10 = terminal NOPAT × g_T ÷ terminal return.
- The free cash flow, the terminal NOPAT, the terminal value and the firm value by 5a.7, at r in every year (5a.8). The terminal return is 5a.7's, 4.7's moat rule on the return on new capital at the target margin, m* × (1 − tax rate) × sales-to-capital: r for a Narrow or None moat; for a Wide moat that return capped at 4.7's cap (13% at the defaults) and never below r. It reads the peers' margin and sales-to-capital and the company's statutory rate; the company has no return on capital to read.

EV(R10) is that firm value. R10 is the least revenue in [0, 10^13] at which EV(R10) is at or above EV_price: 0 when EV(0) already is, else found by bisection to a relative tolerance of 1e-9 (4.1a). EV rises with R10 for sensible inputs, the terminal dominating; when EV(10^13) is below EV_price, as at a target margin at or below zero or a sales-to-capital so low that reinvestment outruns the margin, there is none.

The requirement's reasons, the first that applies, each leaving R10 and the ramp uncomputed: "no target margin: <n> mature peers" (6b.3), "no sales-to-capital" (6b.3), "no statutory tax rate", "no market cap", "no revenue reaches the price". A reason is inside the intermediates; the row's refusal stays "Start-up: no value by design".

### 6b.3 The target margin and sales-to-capital

The target margin is 5a.4's: the median ten-year margin of the mature peers with a margin on `peer_margin_min_years` or more, at least `peer_min` of them, with its industry fallback, its record and its flag `peers-from-industry` as there. Sales-to-capital is 5a.5's step 2 only, the median of the peers' positive measures when at least `peer_min` are positive: a Start-up has no usable own measure, so step 1 is not read and the record says "peers".

### 6b.4 The cash floor and the burn cover

    cash floor = (cash − debt) ÷ diluted shares

the net cash a share, debt and cash as 6b.2 reads them. The `below-net-cash` flag of 6b.2 is the cash floor's test in total: the market cap at or below the net cash, the price at or below the cash floor when the market cap is the price times the diluted shares.

The burn is −(trailing operating cash flow + trailing capital spending) when that sum is below zero. The burn cover is cash ÷ the burn, in years; "not burning" when the sum is zero or above; none without both trailing figures or without a cash figure (an unknown cash is not a cash of nil: the burn shows, the cover does not, `cash_known` is false and no flag is raised). A cover below `burn_cover_flag_years` (2) flags `burn-cover-short`, "Cash covers <x> years of the trailing burn of <y> a year."

### 6b.5 What moves with the price

The market cap moves with the price: the market cap the row read × the new price ÷ the price it was read at, the quote's market cap at an unchanged share count. EV_price, the requirement and its ramp are rebuilt at it from the rebuild keys (6b.6) with the policy's r and g_T, and `below-net-cash` is read again. A requirement whose reason is one of its inputs (the target margin, the sales-to-capital, the tax rate, the market cap) stays. The cash floor, the burn cover and every other flag stay.

### 6b.6 Flags, intermediates and inputs

Flags, in order: `line-not-presented:debt`, `line-not-presented:cash`; `peers-from-industry`; `tax-loss-history-unknown` when the requirement's ramp starts from an operating loss or has a year whose EBIT is below zero, as a loss-maker's always does; `below-net-cash`; `burn-cover-short`. The result puts the assembly's flags and the classifier's checks before these, and keeps the first flag of each code. Never raised here: the ROIC flags of 4.5 and 4.6, `return-above-peers`, `few-analysts` and the trailing flags; no path reads the consensus or the company's return.

Intermediates: `requirement` (`reason`, none when it is computed; `revenue_y10`; `ev_price`; `revenue_0`; `operating_income_0`; `target_margin`, 5a.14's record of the peers and their source; `sales_to_capital`, 5a.14's record with `used` "peers"; `tax_rate`; `terminal_roic`; `path`, the ten years of revenue, EBIT, tax, NOPAT, reinvestment and free cash flow; `terminal_value`; none where a reason leaves a figure uncomputed), `cash_floor`, `burn_cover_years`, `burn` (none when not burning), `debt`, `cash`, `cash_known` (false when no cash figure is on file, `cash` then the nil the floor and the requirement count), `shares`, `market_cap` and `price_facts`.

The rebuild keys: the requirement's `revenue_0`, `operating_income_0`, `target_margin`'s value, `sales_to_capital`'s value, `tax_rate` and `terminal_roic`.

Tagged inputs. DATA: the fiscal years on file, price, diluted shares, next earnings date, daily closes; market cap; trailing revenue and operating income when there are trailing figures, and the last fiscal year's operating income (`operating_income_fy`, noted with its fiscal year) when E0 reads it; trailing operating cash flow and capital spending when there are trailing figures; the newest tax rate; the moat score; `target_margin` and `sales_to_capital` as 5a.14 cites them, when found, the latter noted "the mature peers' median; a Start-up reads no own measure"; `debt` and `cash`. RULE: r, g_T, the moat class, the terminal return (noted with the moat), `peer_min`, `peer_margin_min_years`, `industry_peer_max` on the industry fallback, `burn_cover_flag_years`.

### 6b.7 Worked numbers

The tests pin these (spec 2026-11-03 13.2), to 0.01 unless a tolerance is named. Trailing revenue 0 and operating income −50; target margin 25%, the peers at 20%, 25% and 30%; the peers' sales-to-capital 1.5; tax 25%; r 9%, g_T 3%; no moat score (terminal return r, terminal multiple 11.4444); market cap 2,000, debt 0, cash 300, so EV_price 1,700; 100 diluted shares.

- EV(0) = −166.93: the loss shrinks by 5 a year to nothing in year 10, untaxed, with no reinvestment and no terminal value. EV(1,000) = 931.91.
- R10 = 1,725.73, with EV(R10) = 1,700.00 within 1e-4.
- Trailing operating cash flow −60 and capital spending −15: a burn of 75 a year and a burn cover of 4.0 years, no flag; cash 120 covers 1.6 years, `burn-cover-short`. Operating cash flow 15 is not burning.
- Cash floor 3.00 a share. A market cap of 250 gives EV_price −50, the requirement 0 and `below-net-cash`, "market cap 250 against net cash 300".
- At twice the price the market cap moves to 4,000, EV_price to 3,700 and R10 to 3,616.66, what a valuation at that market cap gives.
- With a Wide moat the return on new capital at the target is 0.25 × 0.75 × 1.5 = 0.28125, so the terminal return is the 13% cap and R10 is 1,514.51.

## 7. Foreign filers

| Case | Refusal |
|---|---|
| Foreign filer: an ADR, or a reporting currency other than USD | "foreign filer: currency and share-unit handling not built yet" |

It keeps its phase, its classifier evidence, its price and its price columns. Assembly withholds the missing-tax-rate refusal from a foreign filer (4.3), so the route reaches the foreign-filer guard; "no financial statements" still refuses a foreign filer first.

Every phase has a route. A Start-up row's refusal is its route's, "Start-up: no value by design" (6b), in place of method 0.6's "Start-up: no value by design; the price-implied requirement comes with the Start-up route".

## 8. The flags

A flag warns and never changes a value, a level or a designation. Each has a code, a short word for the column and one sentence for the drawer.

Eleven flags are quality warnings: they say the value may be wrong because the business or its figures are unusual. They are `large-nri`, `value-spread`, `margin-flag`, `z-distress`, `f-score-low`, `reinvesting-in-decline`, `equity-raise`, `negative-fcf`, `heavy-capex`, `burn-cover-short` and `consensus-recovery` (`QUALITY_WARNINGS` in `engine/flags.py`). A row's flag count is the number of its quality warnings; a refusal row has one too, since its flags are kept. Every other flag is a note: the classifier checks, the thin-consensus flags, the unknown inputs, the engine's mechanics (a floored return, a zeroed charge) and the bookkeeping flags (the lease and line flags, the carried tax rate). A note shows in the Flags column and the drawer and does not count. The column Counts says which flags count.

| Code | Counts | Rule |
|---|---|---|
| `growth-word-disagrees`, `loss-year`, `revenue-gap`, `revenue-falling`, `margin-direction-disagrees`, `fcf-sign`, `short-history`, `margin-zero`, `currency-change` | no | the classifier checks, 3.6 |
| `currency-unknown` | no | no annual income statement gives the reporting currency (the screener row never carries one); the company is treated as a foreign filer |
| `tax-carried-forward` | no | a fiscal year after the tax table's newest year took that year's rate |
| `leases-not-on-balance-sheet` | no | a balance sheet before 15 December 2019 shows no lease assets |
| `trailing-on-fiscal-year` | no | the quarters on file are not four consecutive quarters |
| `sbc-basis-unknown` | no | the stock-compensation basis test lacked an input; on the revenue-growth route, only when the cross-check has a value |
| `path-on-eps` | no | years 2 and 3 grow at the consensus EPS steps |
| `few-analysts` | no | a present path step lands on a year with fewer than 5 analysts or no count: the EPS count on the earnings path (5.3), the revenue count on the revenue path (5a.2, 6a.2); on a Decline row years 2 and 3 only, since a thin year past 3 ends the consensus (6a.2) |
| `path-held` | no | a consensus revenue step is missing, so its year holds the rate of the year before; names the fiscal years that left it missing and the rates held (5a.2, 6a.2) |
| `path-on-trend` | no | a Decline row without a usable NTM consensus: years 1 to 3 of the run-off shrink at the decline rate, which then fades to zero by year N; the sentence names the rate as used (−50% on a floored row) and N (6a.2) |
| `decline-rate-floored` | no | the five-year trend shrinks revenue faster than 50% a year, so the run-off uses −50% (6a.2) |
| `consensus-recovery` | yes | a consensus year of a Decline row, 1 to K, grows while the run-off declines; names each such year and its rate, and the decline rate as used (−50% on a floored row) (6a.2) |
| `consensus-above-base-rate` | no | the year-3 consensus revenue growth is above the sales class's 90th-percentile five-year sales growth, so years 4 and 5 hold the cap and the fade starts from it (5a.3) |
| `peers-from-industry` | no | FMP's peers left fewer than `peer_min` that count for the target margin, so the peers are the largest `industry_peer_max` mature companies of the company's FMP industry in the universe (5a.4, 6b.3); on a Decline row, only when they gave the sales-to-capital (6a.4) |
| `roic-unavailable` | no | fewer than 5 ROIC years |
| `roic-on-n-years` | no | 5 to 9 ROIC years |
| `ten-year-roic-unavailable` | no | the ten-year capital sum is at or below zero |
| `line-not-presented:<field>` | no | an optional balance-sheet line counted as nil in a ROIC year (4.4) |
| `line-not-presented:debt`, `line-not-presented:cash` | no | the bridge to equity counted a debt or cash line as nil: the figure is unknown, or assembly's note names a line the newest annual balance sheet does not present (5a.9, 6a.5, 6b.2) |
| `line-not-presented:totalLiabilities` | no | the newest annual balance sheet of a Decline row lacks total liabilities, or none is on file, so no net-current-asset floor is applied (6a.6) |
| `charge-zeroed` | no | the runway charge is off, 4.6 rule 4 |
| `return-floored` | no | the chosen return measure was below r |
| `growth-above-return` | no | a year's next growth exceeds its return; its payout is floored at zero |
| `tax-loss-history-unknown` | no | the revenue-growth forecast, the run-off or the Start-up ramp has a year whose EBIT is below zero, or the trailing margin (the ramp's starting operating income) is below zero; the tax carry starts at zero and the terminal is taxed in full (5a.6, 5a.7, 6a.3, 6b.6) |
| `margin-ramp-in-dollars` | no | a revenue-growth row's trailing margin is below `loss_ramp_margin_bound` (−100%), so operating income moves in dollars from the trailing loss to the target margin's share of revenue in the convergence year; names the trailing margin and the ramp's two ends (5a.4) |
| `return-above-peers` | no | the return on new capital at the target margin is above the mature peers' median ten-year ROIC (5a.11) |
| `failure-not-charged` | no | a Young Growth row: the failure probability is unavailable and the value is the going-concern value (5a.12) |
| `ncav-floor` | no | the net current asset value a share is above zero and above the run-off's going-concern value, so it floors it, and π is not 100% (an unavailable π included); at π = 100% the floored value has no weight (6a.6) |
| `distress-not-charged` | no | a Decline row with no debt line on file, or with net debt and no trailing interest expense: no rating, π unavailable, the value is the floored going-concern value; the sentence says which (6a.7) |
| `z-distress` | yes | Altman Z″ is below `z_distress` (1.1) (6a.8) |
| `f-score-low` | yes | Piotroski F is at or below `f_score_low` (1), with a signal read (6a.8) |
| `reinvesting-in-decline` | yes | trailing capital spending is above trailing depreciation and amortization in size while the run-off's revenue falls (6a.8) |
| `below-net-cash` | no | a Start-up row's market cap is at or below its net cash, so EV_price is at or below zero and the price needs no revenue (6b.2, 6b.4) |
| `burn-cover-short` | yes | a Start-up row's cash covers fewer than `burn_cover_flag_years` (2) years of its trailing burn; never without a cash figure (6b.4) |
| `margin-flag` | yes | the trailing operating margin is 1.5 × its ten-year median or more (a positive median), or above its ten-year high by 10% of the high's size or more; needs 6 fiscal years with a margin. The word is "Newly profitable" when the median is at or below zero, "Possible cycle peak" when the window holds a loss year, else "Margin above history" |
| `equity-raise` | yes | trailing stock issued is 1% of market cap or more |
| `negative-fcf` | yes | trailing operating cash flow plus capital spending is below zero |
| `heavy-capex` | yes | trailing capital spending is above 50% of a positive operating cash flow |
| `large-nri` | yes | the non-recurring gap is 5% of trailing EPS or more, in either direction |
| `long-runway-high-growth` | no | a 20-year runway with a belief or an implied growth of 10% or more |
| `value-spread` | yes | the value spans 30% or more across the first three return keys or across the three runways; on the revenue-growth route, across the three target margins, or the value at the lowest is at or below zero while the median's is positive (5a.11) |

The three lease and line flags sit on nearly every valued row today; their redesign is a known item.

## 9. The refusal reasons

| Reason | Where |
|---|---|
| no universe deciles yet | 3.3 |
| no financial statements | assembly |
| no statutory tax rate for <country> <year> | 4.3 |
| foreign filer: currency and share-unit handling not built yet | 7 |
| fewer than two fiscal years; no revenue for the last fiscal year; negative revenue; no measurable revenue growth; no operating margin | 3.8 |
| no price; no diluted share count | 5.1 |
| Start-up: no value by design | 6b.1 |
| no trailing figures (never a Start-up row) | 5.1 |
| no trailing revenue; no statutory tax rate | 5.1, 5a.1, 6a.1 |
| no trailing operating income | 5a.1, 6a.1 |
| incomplete NTM consensus | 5.2, 5a.2 |
| no positive forward anchor; forward P/E below 2: unit error | 5.2 |
| no positive consensus revenue | 5a.2 |
| consensus revenue falls to zero or below within the path | 5a.2, 6a.2 |
| no target margin: <n> mature peers | 5a.4 |
| no sales-to-capital | 5a.5, 6a.4 |
| consensus earnings turn negative within the path | 5.3 |
| value not positive under the reinvestment charge | 5.6, 5a.9 |
| value not positive in the run-off | 6a.7, 6a.11 |
| no revenue trend (only a row a `phase` override puts in Decline) | 14.4 |
| no positive trailing earnings | 6.1 |
| inside a Start-up row's `requirement`, not the row's refusal: no target margin: <n> mature peers; no sales-to-capital; no statutory tax rate; no market cap; no revenue reaches the price | 6b.2 |
| data fetch failed: <the failed required endpoints> | the refresh, when an annual statement or the quote fails (section 2) |
| data fetch failed: <error class>: <message>; data fetch incomplete: rate limited; valuation failed: <error class>: <message> | the refresh, when a company's fetch raises, is cut by an HTTP 429, or its valuation raises |

## 10. Refresh kinds and what moves

- **Full refresh**: the universe, the data of section 2 for every admitted company, the deciles, then every company classified and valued, one snapshot per company. A company fetched within the reuse window (`refresh.reuse_hours`, 24 hours by default) is not fetched again.
- **Price refresh**: fresh quotes for the latest universe's admitted companies (before any universe, every company with a snapshot), then each latest snapshot repriced from its intermediates alone: the value, the levels and the validity window stay; the designation, the implied growth and its sensitivities, the margin the price needs (revenue-growth rows), the implied decline rate (Decline rows, 6a.9), the growth-route cross-check's implied growth, the multiples, the growth share, the expected return and the long-runway flag are recomputed; the price input becomes the new quote. A refusal snapshot takes only the new price, its date and the price input, except a revenue-growth refusal whose intermediates carry `revenue_path`: the two refused for their target margin ("no target margin: <n> mature peers") or for a value not positive ("value not positive under the reinvestment charge"). Such a row also recomputes its margin the price needs from its rebuild keys (5a.10); its other figures stay. A Start-up row moves its market cap with the price and rebuilds its requirement and its `below-net-cash` flag at it (6b.5); its other figures stay. A Mature Stable row refused "no positive trailing earnings" moves its growth-route cross-check's implied growth (6.1, 6.4); a cross-check that is itself a refusal stays, and so do its other figures. The price columns (section 2, daily closes) do not move. A snapshot valued under another policy version is not repriced, "policy changed: run a revalue"; under other settings (its settings hash), "settings changed: run a revalue"; under another method version, "method changed: run a revalue". A revalue writes the current versions and hash.
- **Revalue**: the engine on the stored facts of every company, with the latest stored deciles, no vendor call and no freshness window. The new snapshots carry the current method and policy versions and the settings hash.

Every refresh that values (full, scoped, revalue) first backfills the facts of lines added since the payloads were stored, reading the stored responses; a price refresh does not.

Snapshots are appended, never changed. The screen reads the latest snapshot per company.

## 11. Versions

| Method | Date | What changed |
|---|---|---|
| 0.1 | 2026-10-31 | The mechanical screen as first built: the charge at the ten-year aggregate ROIC in the runway years, the terminal from the aggregate, a one-step drop from year 3 to the belief, no payout floor; Mature Stable on the one-stage formula at the terminal return. Policy v1. |
| 0.2 | 2026-11-01 | The calibration: the runway return (4.6), the payout floor (4.8), the fade (5.5), the terminal from the runway return (4.7), the four return keys (5.8), the growth-route cross-check (6.4), the revalue kind. Policy v2 adds four values (the marginal span, the capital-growth test, the fallback window, the fade years) and the recorded decision to keep return on invested capital over return on equity. |
| 0.3 | 2026-11-02 | Mature Stable charges as Mature Growth does (6.3): the runway return through the runway, the terminal return after. Policy unchanged. |
| 0.4 | 2026-11-02 | The High Growth and Young Growth routes (section 5a), the held rate capped at the sales class's base-rate 90th percentile (5a.3), with the `stock-peers` call (section 2); the name patterns on the universe (section 1). Policy v3 adds five values and the `sales_p90_5y` column of `base_rates` (4.1). |
| 0.5 | 2026-11-03 | The industry fallback for the peers (5a.4). Policy v4 adds `industry_peer_max`. |
| 0.6 | 2026-11-03 | The FMP pace (section 2); the universe's six excluded financial industries, its manual admission list, and the manual exclusion checked before every other rule (section 1); the established company with a loss year (3.5 rule 4a) and the Decline duration test (rule 2); the stance leaves the engine; the designation on price ÷ value (4.10). Policy v5 adds the values of the limiter, the universe's admission list and six excluded industries, the designation edges and the Decline and Start-up routes' values (the routes come with 0.7). |
| 0.7 | 2026-11-03 | The Decline route (section 6a): the run-off on the consensus path and the five-year trend's decline rate, floored at −50%; the normalized margin; the capital release; the perpetuity at the decline rate; the net-current-asset floor; the distress-sale value weighted by the synthetic rating's ten-year default probability; Altman Z″, Piotroski F and the reinvesting-in-decline flag; the implied decline rate at the price. The Start-up route (section 6b): no value by design, the refusal "Start-up: no value by design" with the year-10 revenue the price needs on a ten-year ramp to the mature peers' margin, the cash floor and the burn cover; the requirement rebuilt at the price. Policy v5 unchanged. |
| 0.8 | 2026-11-04 | The settings: the forty policy values of 4.1 marked as settings may be changed, and the engine runs the effective policy, the file's values with the user's overlay applied; every result cites its settings hash (4.1). The repricing horizon is a policy value, H (5.10): the growth term reads years 2 to H + 1, the path grows at g_T past the runway (d on the Decline route), and a horizon longer than the path never fails. The flag count: the eleven quality warnings count, every other flag is a note (section 8). Policy v6: the designation edges derived from the Narrow margin of safety, the fair band and the trim multiple (4.10); the Wide cap r plus `wide_terminal_roic_spread` (4.7); `repricing_horizon_years`; the range checks at load. At the defaults every value, level, designation and flag is what method 0.7 and policy v5 give. |
| 0.9 | 2026-11-06 | The engine round (spec 2026-11-06). The Decline route (6a.2, 6a.5): the run-off reads the consensus past year 3 while a year has a revenue mean above zero and at least `analyst_min` revenue analysts, the decline rate then fades in a straight line to zero by year N, and the terminal is flat on year N's revenue. The revenue-growth route (5a.4, 5a.5): the company's own sales-to-capital is usable only at half the mature peers' median or more, and a trailing loss larger than revenue moves in dollars to the target margin, as the Start-up ramp does. The classifier (3.5): a company with a margin above zero in five of the fiscal years on file is established, and an established company is never a Start-up. The margin-direction check (3.4, 3.6): deciles 9 and 2, and Stable points nowhere. The tax table covers every jurisdiction of the OECD series, Taiwan and Cyprus by hand, each hand row citing its own source (4.3). A Mature Stable row refused "no positive trailing earnings" keeps the growth-route cross-check (6.1, 6.4). Policy v7 adds `own_sales_to_capital_min_share` and `loss_ramp_margin_bound`, neither a setting (4.1). At the defaults every row the changes do not touch, directly or through its mature peers, keeps its figures. |
| 0.9, `fairband-review/1`, `fairband-secondary/1` | 2026-11-06 | Tier 2 (spec 2026-11-06). The mechanical method is unchanged at 0.9. A review (section 14) carries `fairband-review/1`, a secondary valuation (section 15) `fairband-secondary/1`. Policy v8 adds six values, none a setting. |

A snapshot names the method and policy versions and the settings hash that produced it. A price refresh refuses to reprice a snapshot from another method version.

## 12. Sources

The labels are those of the research notes in the openalice workspace (H), the stocks repo's growth-duration (G), terminal-rate (T) and valuation (V) notes, and the founder's decisions in `docs/legacy/research.md` (D).

| Rule | Source |
|---|---|
| The six phases, the two deciding variables, the decile grid, the duration test for Decline | Damodaran, *The Corporate Life Cycle* ch. 2 and 3; design.md 5 |
| The established company: a negative margin after a margin above zero in three of the last five fiscal years takes the growth word's phase (3.5 rule 4a) | Damodaran, *The Corporate Life Cycle* ch. 3 (the phases marked by the direction of the numbers); spec 2026-11-03 6.2 |
| The established company also on five profitable fiscal years on file, and never a Start-up (3.5 rules 1 and 4a); the margin direction at deciles 9 and 2, Stable pointing to no phase (3.4, 3.6) | founder decisions 2026-11-06; spec 2026-11-06 8.1 to 8.3 |
| The Decline duration test: revenue fell in three of the last four year-over-year steps (3.5 rule 2) | Damodaran, *The Corporate Life Cycle* ch. 2 s.20 (one or two years of falling revenue can be explained away; a string of years is decay); spec 2026-11-03 6.3 |
| Dickinson's stages | Dickinson (2011), *The Accounting Review* 86(6), Table 1 |
| The reinvestment charge, earnings × (1 − g ÷ return) | McKinsey value-driver formula (V99); design.md 6.5 change 1 |
| One share count, net income not EPS | design.md 6.5 change 2 |
| The marginal return on new capital; the fallback to the company's own return; the floor at r | Damodaran H21, H29; McKinsey T31, G42; Mauboussin G22; calibration spec 5.1 |
| The payout floor; efficiency growth | Damodaran H12, H17; calibration spec 5.2 |
| The fade in five equal steps | Damodaran's template H2; the one-step drop fits moderate growth only (G6); calibration spec 5.4 |
| The terminal return: r by default, a modest excess for a wide moat, never below r | Damodaran T6; McKinsey G42; Mauboussin T25; Morningstar T36; design.md 6.6 |
| Invested capital from the operating side, with goodwill, without cash; average capital; the statutory rate; leases | Damodaran H57; D2, D3, D3a, D3b, D17 |
| The belief: the base-rate median for the sales class | Base Rate Book (Mauboussin and Callahan 2016), exhibit 4; D6 |
| The cap on the held rate: the sales class's 90th-percentile five-year sales growth | Base Rate Book (Mauboussin and Callahan 2016), Sales Growth exhibit 4; design.md 7.3 (a belief above the base-rate 90th percentile needs evidence); founder decision 2026-11-03 |
| The NTM anchor, the SBC basis test, the margin flag, the gate tests, the moat table | stocks mech/1.2 |
| The levels, the expected return, EPV, the P/E bases | stocks method v1.7 Steps 3, 7, 9, 10 |
| The repricing horizon a policy value, the path at g_T past the runway (5.10) | stocks method v1.7 Step 9; design.md 1; spec 2026-11-04 8.3 |
| The settings, the effective policy and the settings hash (4.1) | spec 2026-11-04 8.1 to 8.4 and 8.9; founder agreement 2026-11-04 |
| The flag count: eleven quality warnings, every other flag a note (section 8) | founder decision 2026-11-04, on the figures of the 2026-11-03 run; spec 2026-11-04 9.5 |
| The designation on price ÷ value in five bands, in place of a stance | founder decision 2026-11-03; spec 2026-11-03 7.1; the edges from method v1.7 Step 10 |
| Mature Stable: the stable-growth value with the charge; a stable firm must behave like one | Damodaran H38; design.md 6.11; calibration spec 5.10 |
| The revenue-growth route: a revenue DCF on margins and sales-to-capital, five high-growth years and five fading to g_T; high growth no longer than ten years, its length a judgment tier 1 fixes | Damodaran's template H2; H1; H3; G1, G44; design.md 6.10 |
| The free cash flow as NOPAT less reinvestment | Damodaran H9 |
| The margin moving to a target margin; the target as the mature peers' median ten-year margin, on five years at least | Damodaran H13, H64; design.md 6.7 |
| Sales-to-capital: the company's own marginal measure, else the mature peers' | Damodaran H13, H14; D3c |
| The industry fallback for the peers: the sector averages beside the company's own data, the industry average as the template's default, margins and returns resting at the sector average | Damodaran H13, H16, H29; design.md 6.7; founder decision 2026-11-03 |
| Reinvestment a year ahead of the revenue it buys, never negative | Damodaran H16, H17 |
| The return on new capital against the peers' ROIC | Damodaran H15 |
| Young Growth: the failure probability unavailable, with its reason | D3d; design.md 6.9 |
| The validity window | design.md 8 |
| The six excluded financial industries; the manual admission list, payment companies that do not lend (section 1) | design.md 6.1 (banks, insurers and REITs need methods of their own); decision 2026-10-26; spec 2026-11-03 6.4; founder decision 2026-11-03 (the admission list) |
| The FMP pace and the 429 hold (section 2) | the founder's FMP plan (Ultimate, 3,000 calls a minute) less 5%; one plan window for the hold; spec 2026-11-03 5 |
| The Decline route's run-off: revenue shrinking at a rate a year, the capital released by divestitures recovered in part (`runoff_recovery`, the midpoint of the Sears divestitures' 54% to 67%), one margin held through the run-off (6a.2 to 6a.4) | Damodaran 2009, "Valuing Distressed and Declining Companies", the Sears run-off; Damodaran, *Investment Valuation* ch. 12 (a firm that partially liquidates itself each year); spec 2026-11-03 10.2 to 10.4 |
| The normalized margin: the median of the last five fiscal margins (6a.3) | Damodaran 2009 (the Las Vegas Sands earnings power on a four-year average); spec 2026-11-03 10.3 |
| The decline rate floored at −50% and the implied decline rate's first root (6a.2, 6a.9) | rulings of 2026-11-03 on the run-off core's review: the floor is the implied-decline scan's lower bound; the value need not rise with d |
| The decline runs its course and the firm stabilizes at a smaller size: the decline rate fading to zero by year N, and a flat terminal (6a.2, 6a.5) | Damodaran, "Valuing Distressed and Declining Companies" (2009): a declining firm's revenues fall and then level off; Damodaran, *The Corporate Life Cycle* ch. 2 (decline is not death); spec 2026-11-06 6.1, 6.2 |
| The consensus read past year 3 where it reaches, on `analyst_min` revenue analysts (6a.2) | stocks method v1.7 section 3 (a year with fewer than 5 analysts is not data); method 5a.2; spec 2026-11-06 6.1 |
| The liquidation floor at the net current asset value (6a.6) | Graham's net current asset value; Damodaran (an irreversible decline at the higher of the going-concern and the liquidation value); spec 2026-11-03 10.6 |
| The distress weighting: π from a synthetic rating on interest coverage, the ten-year default probability, the distress-sale value as a fraction of the DCF value (6a.7) | Damodaran, ratings.html, "For large non-financial service firms", January 2026; Damodaran 2009, Table 5 (Altman, 1971 to 2007) and "Estimating Distress Sale Proceeds", choice (a); spec 2026-11-03 10.7 |
| Altman Z″, the non-manufacturer form, and its zones (6a.8) | Altman (2000) |
| Piotroski's nine F signals and the low group (6a.8) | Piotroski (2000) |
| Reinvesting in decline (6a.8) | Damodaran 2009 (declining firms are cheap "only if their managers don't try too hard"); spec 2026-11-03 10.8 |
| The Start-up route: no tier-1 value, the price-implied requirement and a floor at cash (6b) | design.md 6.8; spec 2026-11-03 9.1 |
| The requirement as the revenue in year 10 at the mature peers' margin: value built from a market, a share and a target margin, the screen stating the revenue they must reach (6b.2) | Damodaran 2009, "Valuing Young, Start-up and Growth Companies" (Secure Mail); spec 2026-11-03 9.2 |
| The burn cover: what the market prices at the Start-up phase is capital access (6b.4) | Damodaran, *The Corporate Life Cycle* ch. 9 s.11; the 2-year flag a policy value with no source; spec 2026-11-03 9.4 |

## 13. Glossary

| Term | Meaning |
|---|---|
| Value at belief | The value a share at the growth belief; the one price target |
| Belief | The growth rate for years 4 to N before the fade: the base-rate median plus 2 points |
| Runway N | The years of growth above the terminal rate, set by the moat class |
| Runway return | The return on new capital the charge uses in years 1 to N − 1 |
| Terminal return | The return on new capital after the runway |
| Charge | The share of earnings held back to pay for the next year's growth, g ÷ return |
| Charge off | The runway years are not charged, because measured capital is at or below zero |
| Fade | The five equal steps from the year-3 consensus growth down to the belief |
| EPV | Earnings power value: clean trailing earnings ÷ r, the value with no growth |
| Designation | Where the price stands against the value at belief: one of five bands on price ÷ value (4.10); a fact about the price, never an action |
| Non-recurring gap | GuruFocus EPS trailing less EPS without non-recurring items |
| Growth word, margin direction | The classifier's reading of the deciles for revenue growth and for the margin trend |
| Check | A classifier warning that never changes the phase |
| Snapshot | One company's result under one refresh, with the versions and the settings hash that produced it |
| Setting | A policy value the user may change on the Settings view (4.1) |
| Effective policy | The policy file's values with the user's settings applied over them; the policy the engine runs (4.1) |
| Settings hash | The sha256 of the user's settings that change a result's figures; it names the settings a result was valued under, as the policy version names the file (4.1) |
| Repricing horizon | H: the years over which the expected return assumes the price meets the value (5.10) |
| Quality warning | One of the eleven flags that say the value may be wrong because the business or its figures are unusual; a row's flag count counts them (section 8) |
| Note | Any other flag: shown, never counted (section 8) |
| Mature peers | The company's FMP `stock-peers` that the latest universe lists and the classifier puts in Mature Growth or Mature Stable; when fewer than `peer_min` of them count, the largest mature companies of the company's FMP industry |
| Target margin | The operating margin the revenue-growth route moves to by year 10, and the Start-up ramp reaches in year 10: the median ten-year margin of the mature peers |
| Sales-to-capital | The revenue a dollar of invested capital buys: the company's change in revenue ÷ its change in capital, its newest kept year's revenue ÷ that year's capital (6a.4), or a peer's revenue ÷ its capital. The revenue-growth route reinvests the next year's revenue increase ÷ sales-to-capital |
| Margin the price needs | The target margin at which the revenue-growth value a share equals the price |
| Return on new capital at the target | Target margin × (1 − tax rate) × sales-to-capital: the after-tax return on new capital once the margin reaches the target. It sets the terminal return by the moat's rule and is checked against the peers' ROIC |
| Held rate | The growth the revenue path holds in years 4 and 5 before its fade: g_3 as resolved, or, for the implied growth, the rate at which the value equals the price. A held step is a missing consensus step that takes the rate of the year before |
| Run-off | The Decline route's DCF: a firm that shrinks year by year, releasing the capital its lost revenue needed, until its decline fades to zero by year N, and is valued in the terminal as a business of year N's size that neither grows nor shrinks (6a) |
| Decline rate | d: the five-year revenue slope over the last fiscal year's revenue, at most zero and floored at −50%; the run-off's rate after the consensus years, fading in a straight line to zero by year N (6a.2). The implied decline rate is the d at which the value equals the price (6a.9) |
| Normalized margin | m_n: the median operating margin of the last five fiscal years when at least three have one, else the trailing margin; held in every year of the run-off (6a.3) |
| Synthetic rating | The bond rating that a company's interest coverage, EBIT_n over the trailing interest expense, reads off Damodaran's table; its ten-year default probability is π (6a.7) |
| Distress-sale value | What equity gets in a distress sale: 60% of the firm value plus cash, less debt, not below zero, a share (6a.7) |
| NCAV | Graham's net current asset value: total current assets less total liabilities; the run-off's floor when above zero (6a.6) |
| Requirement | A Start-up row's price-implied requirement: the revenue in year 10 at which a ten-year ramp to the mature peers' margin is worth the market cap plus debt less cash (6b.2) |
| Cash floor | A Start-up row's net cash a share, (cash − debt) ÷ diluted shares (6b.4) |
| Burn cover | The years a Start-up row's cash covers its trailing burn, the trailing operating cash flow plus capital spending when below zero; "not burning" otherwise (6b.4) |
| Override | A change an agent makes to one tagged input, with its reason, its evidence and its lifetime (lasting, or tied to a period); applied, or refused with the rule it breaks, and stored either way. The engine, not the agent, computes the value it gives |
| Review | The engine's valuation of a company under its applied overrides: the reviewed value, its levels and designation on the same edges, and the bridge from the mechanical value, one line per override. It follows the company's snapshots and cites `fairband-review/1` |
| Finding | A dated fact an agent records with its source (a filing, a transcript, a URL, a vendor response or a base rate); the only way a number from outside Fairband enters a report |
| Judgment | One of a report's key judgments (the phase, the moat, the belief, the ROIC, the target margin) with its bull case, its bear case, the decision and the override it produced, if one. An input an override sets is tagged JUDGMENT, beside DATA and RULE |
| Secondary valuation | A second valuation an agent makes from an explicit free-cash-flow path, one part or a sum of parts, discounted at r with a terminal at g_T or below: a second view on a valued company and a fallback where the route gives no value. It cites `fairband-secondary/1` |
| Work item | A request in the inbox for an agent's research on one company, a valuation review or a full report, posted by the owner, an agent or the expiry rule; pending, claimed, done, declined or dropped |

## 14. Reviews: overrides and the reviewed value

An agent changes the method's inputs only through overrides, and the engine, not the agent, computes the value they give: the reviewed value. A review cites `fairband-review/1` (section 11). The mechanical method does not move: with no override every figure is the mechanical one, bit for bit.

### 14.1 What an override is

A change to one tagged input of 14.2, with its reason, its evidence and its lifetime (spec 2026-11-06 Tier 2, 10.1). The evidence is one item or more, each a kind (the kinds of a finding's source, a filing, a transcript, a URL, a vendor response or a base rate, or a finding by its id), a reference and a note. The lifetime is lasting, or period-tied: a correction tied to one period, which keeps the value it corrected (14.6). The record keeps the input as the engine read it on the snapshot it was made on (its old value, 14.4), the new value and its unit, the principal and the actor (the model identifier as it arrived), the time and the state: `applied`; `refused-locked`, `refused-not-input`, `refused-route`, `refused-unit` or `refused-evidence` with the rule's sentence (14.3); or `dropped` with the reason. A refused override is stored and applies nothing. One input has one applied override: a new one on the same input drops the old, "replaced by override <n>". Only an agent adds or drops an override this round.

### 14.2 The inputs an agent may override

| Tag | Routes that read it | The input | Range, the ends included |
|---|---|---|---|
| `phase` | every route | the phase (3.5); the route follows it | the six phases |
| `growth.belief` | Mature Growth | the belief (5.4) | −20% to 60% a year |
| `path.hold` | High Growth, Young Growth | the held rate of years 4 to H (5a.3) | −20% to 300% a year |
| `path.step_2`, `path.step_3` | Mature Growth, High Growth, Young Growth, Decline | the consensus steps g_2 and g_3 (5.3, 5a.2, 6a.2) | −80% to 300% |
| `moat.class` | Mature Growth, Mature Stable, High Growth, Young Growth, Start-up | the moat class (4.9) | None, Narrow or Wide |
| `margin.target` | High Growth, Young Growth, Start-up | the target margin (5a.4, 6b.3) | −50% to 60% |
| `capital.sales_to_capital` | High Growth, Young Growth, Decline | sales-to-capital (5a.5, 6a.4), a multiple | 0.1 to 10 |
| `return.runway` | Mature Growth, Mature Stable | the runway return (4.6) | 0% to 100% |
| `earnings.nri_gap` | Mature Growth, Mature Stable | the non-recurring gap (5.9, 6.1) and the anchor's basis (5.2) | −$100 to $100 a share |
| `decline.rate` | Decline | the decline rate d (6a.2) | −50% to 0% a year |
| `balance.debt`, `balance.cash` | High Growth, Young Growth, Decline, Start-up | the newest annual balance sheet's debt and cash (5a.9, 6a.5, 6b.2); period-tied only, a correction of a vendor error | $0 or more ($10^15 at most) |

The numeric ranges are the policy's `override_ranges` (4.1), not settings; the two word inputs take their words. The Mature Stable value reads no consensus step (its cross-check, 6.4, reads the consensus as found), so that route does not read `path.step_2` or `path.step_3`.

Locked, refused `refused-locked` with the sentence given: r, "r is a locked input: the hurdle rate"; g_T, "g_T is a locked input: the terminal growth ceiling"; the runway years and the margin of safety, which the moat sets; the fade years, the fair band and the trim multiple, policy values; the terminal return, "the terminal return follows the moat"; the deciles and the growth word; and the reported figures, price, diluted shares, market cap, revenue, operating income and EPS, "<name> is reported data". Debt and cash change only through the two balance corrections. Any name not in the table is not an input.

### 14.3 The rules, in the order they are checked

`overrides.check_override` answers with the first rule an override breaks, else `applied`:

1. A locked input: `refused-locked`, the sentence of 14.2.
2. A tag that is not one of the thirteen: `refused-not-input`, "<tag> is not an input".
3. A route that does not read the tag: `refused-route`, "the <route> route does not read <tag>". The route is the one the row takes after any applied `phase` override, so a Start-up row overridden to Young Growth takes `margin.target` on the revenue-growth route.
4. A value the input cannot take: `refused-unit`. A word outside the input's words, "moat.class takes None, Narrow or Wide"; a number outside its range, or a word where a number is due, "growth.belief takes −20% to 60%"; a lasting override of a period-tied input, "balance.debt is period-tied only".
5. The evidence: `refused-evidence`. None at all, "an override needs evidence"; or a `growth.belief` or `path.hold` above the sales class's `sales_p90_5y` (4.1, `base_rates`) without a filing or a transcript among its evidence (the class of the snapshot's trailing revenue, its `revenue_ttm` input, as every route finds it, so the rule holds on a row a `phase` override moves onto a route that reads the input, a Start-up put in Young Growth say; no cap when the snapshot cites no trailing revenue), while `override_primary_evidence_above_p90` holds: "a belief above the base rate's 90th percentile needs a filing or a transcript", or "a held rate above …".

An override, a drop and a recompute are refused with the price refresh's own sentence, "settings changed: run a revalue" (or "policy changed", "method changed"), when the effective settings hash, the policy version or the method version is not the latest snapshot's (section 10); so the bridge's mechanical term is always the row's own figure. For the same reason the recompute first runs the engine with no override on the inputs it builds from the store that day, on the latest deciles: when that run's route or value a share is not the latest snapshot's, the override or the drop is refused, "the store moved since snapshot <id>: run a revalue", and nothing is stored. A store change after the snapshot, a full refresh's deciles stored before its value stage or a peer's figures moved by a scoped refresh, would otherwise land on the bridge's first line as the agent's.

### 14.4 How a route reads an override

`route.value_company` takes the applied overrides by tag, and every route reads each input of 14.2 through one accessor, `route_steps.chosen`: the override's value when one applies, the route's own reading otherwise. What the route computes from the input follows it, its flags included; nothing else moves.

- `phase` replaces the classifier's phase right after the classification, the rest of its evidence as it was, so every guard and the route read it. A Start-up row overridden to another phase takes that phase's route and, as any such row, is refused without trailing figures; a row overridden to Start-up takes 6b. A row put in Decline without a five-year revenue trend or a positive last revenue, and with no `decline.rate` override, is refused "no revenue trend".
- `growth.belief` replaces the belief's rate (5.4); the fade runs to it.
- `path.step_2` and `path.step_3` replace a consensus step before anything reads it: on Mature Growth before the check that the path stays above −100% (5.3); on the revenue-growth route before the cap, the fall check and the path's flags (5a.2, 5a.3); on Decline as the revenue-growth route reads them (6a.2), except on a row without a usable consensus, whose years 1 to 3 shrink at d and read no step. A replaced step is never held, and `few-analysts` names only the steps the consensus still gives.
- `path.hold` replaces the held rate after the cap (5a.3): the agent's rate, which the cap does not bind. `consensus-above-base-rate` is not raised, and `held_growth_cap` notes "does not bind: the held rate is an agent's override".
- `moat.class` replaces the class (4.9), so the runway, the terminal return, the margin of safety and the levels move with it (4.7, 4.10); the cross-check (6.4) reads it too.
- `margin.target` replaces the peers' median (5a.4, 6b.3), the peers' lowest and highest margins kept for the sensitivity; on a row with no counted peers, the override stands alone, its own low and high, and the row is not refused for its target margin.
- `capital.sales_to_capital` replaces the measure (5a.5, 6a.4). Its record's `used` is "override", the measures kept beside it, so the peers neither flag `peers-from-industry` on Decline nor cite their rules for it.
- `return.runway` replaces the runway return of the charge (4.6) and charges the runway years, even where the measured return had the charge off; the terminal return still follows the moat on the measured return (4.7), and `return-floored` and `charge-zeroed` are not raised.
- `earnings.nri_gap` replaces the non-recurring gap: Mature Stable's E (6.1), the clean EPS, EPV and `large-nri` (5.9), and the anchor's basis test (5.2), which reads trailing GAAP EPS less the agent's correction, the override less the gap found (nil without one): the test's mechanical reading moved by the correction alone, so a gap overridden at the figure found leaves the basis as it was. The cross-check (6.4) reads the gap too.
- `decline.rate` replaces d (6a.2), never floored: `decline-rate-floored` is not raised.
- `balance.debt` and `balance.cash` replace the balance sheet's figures before a missing one counts as nil (5a.9, 6a.5, 6b.2): the bridge from firm value to equity, the rating's net debt and whether there is a debt line (6a.7), the cash floor and the burn cover (6b.4). A replaced line raises no `line-not-presented` flag.

An overridden input is tagged JUDGMENT, kind judgment, beside DATA and RULE. Its entry is named by its tag and carries the number (none for a word, which leads the note), the input's unit, and the override's provenance: the source "override <n>, <principal> <actor>", "override 1, agent claude-opus-5-5" say (the principal alone without an actor, "override 1, system"), entered at the override's time, the reason as the note. Every result, a refusal too, cites these entries last, in the bridge's order (14.5), in place of the route's own entry for the input (`belief`, `path_step_2`, `path_step_3`, `moat_class`, `target_margin`, `sales_to_capital`, `runway_return`, `debt`, `cash`), so no DATA or RULE entry carries an agent's figure under the vendor's or the policy's provenance. The intermediates hold the figures the route used.

The engine's reading of an input (`overrides.current_reading`), the bridge's old value and the value a period-tied override corrects, comes from a result's intermediates: the phase; the belief's rate; the held rate, the hold when one is set, else g_3 as resolved; the steps, the route's `path_steps`, else the revenue path's or the run-off's as found; the moat, a Start-up row's from its moat class input; the target margin; sales-to-capital; the runway return, none with the charge off (4.6), whose figure is the terminal return and charges nothing; the non-recurring gap; d; and for debt and cash the reported figure the result cites, none when no line is on file (where the bridge counts nil) and none on a row refused before its route cites the line, whose intermediates hold only the nil. It is none where the result holds no such figure. An override at the engine's reading moves nothing: its bridge line's delta is zero.

### 14.5 The review: the recompute and the bridge

A review is the engine's result under the company's applied overrides (`review.review_company`), built from the mechanical result. The overrides apply one at a time in a fixed order, the method's step order: `phase`, `path.step_2`, `path.step_3`, `path.hold`, `growth.belief`, `earnings.nri_gap`, `margin.target`, `capital.sales_to_capital`, `return.runway`, `decline.rate`, `moat.class`, `balance.debt`, `balance.cash`. Each line of the bridge is one engine run with that override and every earlier one; its old value is the engine's reading on the mechanical result (14.4), its new value the override's.

A line's delta is its value a share less the value of the last step that valued, the mechanical value or an earlier line's, so the deltas sum to the reviewed value less the mechanical value. A line whose step refuses shows the refusal in place of a delta, "value not positive under the reinvestment charge" say, and a review whose last step refuses is a refusal with that reason; the next line that values measures from the last step that valued. A mechanical refusal that an override turns into a value, a Start-up row reclassified, starts the bridge at no mechanical value: the first valuing line carries the whole value as its delta. The reviewed value's levels and designation are 4.10's on the same edges, the levels on the reviewed moat.

A review is stored with its result, its value, levels and designation, the mechanical value, the bridge, the ids of the overrides inside and `fairband-review/1`, and with the policy version, the settings hash and the deciles refresh it ran under, as a snapshot is.

### 14.6 A review follows its snapshot

A review follows its company's snapshots. Every refresh that writes a snapshot for a company with applied overrides writes a review on it, with its log row (14.7) and no ledger row: the system's review is recorded in the log, the agent's override and drop in the ledger. A full or scoped refresh and a revalue recompute it on the new inputs; a price refresh reprices the latest review, the one on the snapshot it reprices, as it reprices the snapshot (section 10), its value, levels and window kept and its designation moved. A company the refresh cannot value (a failed fetch or valuation) gets its refusal snapshot's refusal as its review, with no mechanical value and an empty bridge; a review the engine cannot compute is a refusal, "review failed: <class>: <message>", with an empty bridge, and the mechanical snapshot stands. Before a recompute at a full or scoped refresh or a revalue, a period-tied override is checked: it drops, by the system and with the reason, when the company's data date has moved past its snapshot's, or when the engine's reading of its input on the new snapshot differs from the value it corrected, "the input the override corrected changed". An override binds to the snapshot it was made on for provenance and applies to the latest snapshot and every later one; snapshots are appended at every price refresh, so there is no stale conflict. A review carries its snapshot's validity window and expires with it, a review recomputed after an override past the snapshot's next earnings date included; a review that is a refusal has no value.

### 14.7 The log

One row for each review written: the time, the company, the refresh, the snapshot and the review; the mechanical phase and value; the reviewed phase and value, none on a refusal; the latest secondary value (section 15), none without one; the price; the mechanical designation; and the latest published report's stance. It measures whether the agents' overrides help, read once it has rows.

## 15. The secondary valuation

A second valuation beside the routes, from an explicit cash-flow path an agent supplies (spec 2026-11-06 Tier 2, 11). It is a second view on a valued company and a fallback where no phase or route fits, or where the route refuses. The agent builds the path from its own research; the engine keeps the discounting, the terminal and the bridge to equity, so the number is a tool output. A secondary valuation cites `fairband-secondary/1` (section 11). Neither the mechanical value nor the review reads it.

### 15.1 The inputs

One part or more, at most `secondary_parts_max` (10; 4.1). One part is a discounted cash flow, several a sum of parts. A part is a name; the free cash flow to the firm in dollars for years 1 to N, N from `secondary_years_min` (3) to `secondary_years_max` (15); a terminal growth g at most g_T (3.0% at the defaults), lower or negative allowed; and a note. With the parts, a reason and evidence: one item or more, each of the kinds an override's evidence takes (14.1).

### 15.2 The arithmetic

r is the effective policy's required return, locked as for an override (14.2). Per part:

    PV_t = fcff_t ÷ (1 + r)^t, t = 1 … N
    terminal = fcff_N × (1 + g) ÷ (r − g), discounted by (1 + r)^N
    part value = Σ PV_t + the discounted terminal

The firm value is the sum over the parts; equity = firm value − debt + cash; the value a share = equity ÷ the diluted shares. The levels are 4.10's on the moat class: the current review's when the company has one (14.5), else the snapshot's, else None. The designation is 4.10's on the snapshot's price ÷ the value a share. A value a share at or below zero is kept as computed, with no levels and no designation; it is not a refusal.

### 15.3 Debt, cash and shares

The server reads the debt and the cash at the call as assembly reads them for the growth, Decline and Start-up routes (5a.9, 6a.5, 6b.2): the newest annual balance sheet's short-term plus long-term debt, and its cash and equivalents plus short-term investments, a line it does not present counting as nil. An applied `balance.debt` or `balance.cash` override (14.2) counts in its place. The agent may pass the debt or the cash itself where the balance sheet is wrong or missing; each figure passed needs its own evidence item, one whose `figure` names it, `debt` or `cash`. The record stores the debt, the cash and the shares used, and where the debt and the cash came from: `statements`, the balance sheet's; `agent`, a figure the agent passed or an applied override's. The shares are the snapshot's diluted count: its `shares_diluted` input, else its intermediates' `shares`.

### 15.4 The refusals

Each is answered with its sentence, and nothing is stored:

- a reason that is blank, "a secondary valuation needs a reason"; no evidence, "a secondary valuation needs evidence"; a debt or a cash passed without its own evidence item, "an explicit debt needs its own evidence item" (or cash);
- a company whose latest snapshot was valued under another policy version, other settings or another method version: the price refresh's sentences, "settings changed: run a revalue" (or "policy changed", "method changed"), as for an override (14.3);
- a foreign filer, "foreign filer: currency and share-unit handling not built yet", since a dollar path over local-currency debt would mislead: a snapshot refused as one (section 7), or a universe row that is an ADR or names a currency other than USD (a row naming none leaves it to the snapshot);
- a snapshot with no positive diluted share count, "no diluted share count";
- the bounds, each naming its rule with the effective policy's numbers: no part, "at least one part"; more than `secondary_parts_max`, "at most 10 parts"; a path shorter than `secondary_years_min` or longer than `secondary_years_max`, "a part has 3 to 15 years"; a g above g_T, "the terminal growth is at most g_T, 3.0%".

### 15.5 As of its snapshot

A secondary valuation is stored on the company's latest snapshot with its parts, each with its path, its g, its note, its present values, its terminal, the terminal's present value and its value; the firm value; the debt, the cash and the shares with the two sources; the equity; the value a share; the levels, price ÷ value and the designation at the snapshot's price; the reason and the evidence; the writer (the principal, and an agent's model identifier and client) and the time; and the policy version, the settings hash and the deciles refresh it ran under. It is a ledger row, `secondary`. It is never changed, and no refresh recomputes or reprices it: it is as of its snapshot, its window that snapshot's validity window (4.10), and it stays in the company's history after later refreshes, read with its date. The agent makes a new one at its next review. The owner may make one too: it is a tool's output, not an override. The log (14.7) reads the newest one's value a share.

### 15.6 Worked numbers

The tests pin these within 1e-4 (spec 2026-11-06 Tier 2, 20.1). r 9%, g 3%; one part, free cash flow 100 in year 1 growing 5% a year for 5 years (100, 105, 110.25, 115.7625, 121.550625); debt 200, cash 100, 100 diluted shares. The present values 91.7431, 88.3764, 85.1332, 82.0091 and 78.9996, Σ 426.2614; the terminal 121.550625 × 1.03 ÷ 0.06 = 2,086.6191, discounted 1,356.1592; firm value 1,782.4206; equity 1,682.4206; value a share 16.8242. A second part, 20 flat for 5 years at g 0: Σ PV 77.7930; terminal 20 ÷ 0.09 = 222.2222, discounted 144.4292; part value 222.2222; with both parts the value a share is 19.0464. A g of 3.5% is refused, as are a path of 2 years and an 11th part.

## 16. Reports: the number check

An agent's report is published whole or rejected whole (spec 2026-11-06 Tier 2, 13). Every number in it is a cite of a stored value, so the reader part traces to the records the engine and the store hold; the agent writes the sentences, never a figure of its own. The check is `fairband.reports.check`; the references are `fairband.reports.refs`.

### 16.1 A report

A submission names a mode, a stance, the sections, the key judgments, and optionally kill criteria, news items and the work item it completes. A section is a heading and its parts; a part is plain text or a cite, `{cite, ref, period?}`: the text as the reader sees it, the reference of the stored value, and the period it claims. Before the number check run four structural checks, each refused with one sentence: the mode's section count, ten for a full report and eight for a valuation review, which leaves out "The business" and "Industry and competition" (design.md 7.5); the stance, one of the policy's `stance_words` (buy, hold, trim, avoid; 4.1); the required judgments, `phase`, `moat` and `belief` on every report, `roic` where the route is Mature Growth or Mature Stable and `target_margin` where it is the revenue-growth route or Start-up, the route of the company's current review when it rests on the latest snapshot, else the snapshot's (a refused row's phase's); and the headings, design.md 9.3's ten in order: Summary, The business, Industry and competition, Financial performance and health, Life-cycle phase, Valuation, Price facts and multiples, Key judgments, Recent news, Risks and kill criteria.

A rejected report stores nothing but its ledger row, "rejected: <n> findings", which points at no record; the answer lists the findings. A published one is stored as the company's next revision (from 1) on the snapshot its cites rest on, with the review and the secondary valuation it cites (else the company's current review and newest secondary valuation when they rest on the latest snapshot or one it reprices), its judgments, kill criteria and news items, and it completes the work item it names. A valuation review reuses the company's newest full report, or says there is none. The latest revision is the company's report; the earlier ones stay. The latest report's stance is the one the review log reads (14.7).

### 16.2 The references

A reference is `<form>:<path>`, resolved for the report's company; a record of another company names nothing. Each resolves to a value (a number, a word, or none where the record holds no figure), a unit, a period and the snapshot it rests on.

| Ref | Resolves to | Unit |
|---|---|---|
| `snapshot:<id>/value`, `/price`, `/levels/<name>` (buy, fair_low, fair_high, trim) | the snapshot's value a share, price and levels | per-share |
| `snapshot:<id>/price_to_value` | price ÷ value | multiple |
| `snapshot:<id>/inputs/<name>` | a tagged input; a word input (the moat class) reads the word leading its note | the input's |
| `snapshot:<id>/intermediates/<path>` | an intermediate by its keys and list indexes, `belief/rate` | none |
| `snapshot:<id>/phase/<field>` | a field of the classifier's evidence (3.5), `phase`, `growth_3y` | the field's |
| `review:<id>/value`, `/price_to_value`, `/levels/<name>`, `/bridge/<n>/delta`, `/old`, `/new` | the review's figures (14.5); the bridge's line n counted from 1 | per-share; old and new the input's |
| `secondary:<id>/value`, `/firm_value`, `/equity`, `/debt`, `/cash`, `/shares`, `/price_to_value`, `/levels/<name>`, `/parts/<n>/pv/<t>`, `/parts/<n>/fcff/<t>`, `/parts/<n>/value`, `/terminal`, `/terminal_pv`, `/terminal_growth` | the secondary valuation's (15), part n and year t counted from 1 | per-share, currency, count, percent |
| `fact:<symbol>/<line>/<year or ttm>` | a stored statement line as the engine reads it: a fiscal year's (the store's lines by the engine's names), or the trailing figures' | currency; per-share for EPS; count for the diluted shares |
| `table:<symbol>/<table>/<row>/<year>` | a cell of the financial tables (16.5) | the row's |
| `estimate:<symbol>/<period>/<field>` | a stored consensus figure, the period a fiscal year (`2026`) or a quarter (`2026-Q4`) | currency; per-share for EPS; count for the analysts |
| `close:<symbol>/<date>` | a stored daily close | per-share |
| `peer:<symbol>/<peer>/<field>` | a mature peer's figure as assembly reads it (5a.4): `market_cap`, `margin`, `margin_years`, `sales_to_capital`, `roic` | currency, percent, count, multiple, percent |
| `finding:<id>` | a finding's value, unit and period, as the agent recorded it (a percent as a fraction) | the finding's |
| `derived:<id>` | a derivation's value (16.4) | the derivation's |
| `response:<id>/<json pointer>` | a field of a stored vendor response (RFC 6901) | none |
| `policy:<name>` | a value the Methodology page cites, by name or by name and a moat class or an index (`runway_years.Wide`, `fair_band.0`) | the value's |

The units are the reads': currency (a total, in the statements' currency), per-share, percent (a fraction), multiple, count, score and years. An engine input's unit maps onto them: a currency code is currency (the share price per-share), "<code> a share" per-share, a ratio percent, shares and the other counted things count, years and scores as they are; a word or a date has none. The period is the fiscal year, the quarter, `ttm` or the close's date for the forms that have one, the finding's as recorded, none for the others. A `snapshot:`, `review:` or `secondary:` ref rests on its record's snapshot, a `derived:` ref on its operands'.

The reprice rule (spec 13.2): a report rests on the company's latest snapshot. A later snapshot that reprices the cited one, with the same data date, method version, policy version, settings hash and value, counts as the cited one, so a price refresh during the research does not reject a report; the report keeps the cited snapshot, whose price date its header shows. A revalue or a full refresh in between rejects it.

### 16.3 The check

Every part of every section is read, and so is the text of every judgment, and each failure is a finding `{where, what, detail}`: `where` is the section and the part, counted from 1 in the submission, and the text at fault, "section 1, part 3: $12.345", or the judgment and its field, "judgment moat, bull: 11.2%". The six failures, in the server's words:

- `a number with no reference`: a quantity in plain text, or in a judgment's bull, bear or decision, which carries no cite.
- `unresolved reference`: a cite whose ref names nothing, or names a figure the record does not hold.
- `wrong unit`: a cite whose suffix does not fit the ref's unit, or whose number is not the ref's value at the report's rounding; the detail gives the value as the cite should read. A word cited against a number, or a word that is not the ref's, is also `wrong unit`.
- `wrong period`: a cite whose period is not the ref's (`FY2025` reads `2025`); a cite naming no period passes.
- `wrong snapshot`: a cite whose ref rests on a snapshot other than the company's latest or one the latest reprices; the detail names the latest's id. A `review:` cite must be the company's current review: the newest review on its snapshot, with the current review that one or its reprice; the detail names the current review's id.
- `a derived figure the engine has not emitted`: a `derived:` cite with no stored derivation of the company, or one with no value; and a multiple (`2.4x`) in plain text, a ratio written out rather than derived.

A cite gets one finding, the first of: wrong snapshot, not emitted, unresolved, wrong period, wrong unit. A plain part gets one for each quantity.

The token rule. A quantity is a money amount, any number a currency sign leads (`$`, `€`, `£`, `¥`, a letter prefix before it or not) whatever letters follow it (`$1,234.50`, `$5`, `$ 5`, `US$5`, `$391bn`, `$126M`, `$5mm`, `$3.2T`, `€1.5B`, `£126m`); a decimal joined to a one-letter scale, `m`, `b`, `k` or `t` in any case (`1.5B shares`, `2.3M users`, `4.5k`); a number followed by a unit word, with or without a space and in any case, whatever its digits (`12 billion`, `11.2pp`, `50bps`, `5 basis points`, `5 percentage points`, `2 Years`; the words `thousand`, `million`, `billion`, `trillion`, `mn`, `mm`, `bn`, `tn`, `pp`, `bp`, `bps`, `percentage points`, `basis points`, `years`); a percentage (`11.2%`, `11.2 percent`, `5 per cent`); a multiple (`12.3x`, `5 x`, `12.3×`, and `X` joined to the number, `15X`, `1.12X`, never after a space: `5 X-ray`); a decimal; or an integer of two or more digits; a sign (`-` or the minus `−`) or parentheses around it included. Otherwise a one-letter scale does not count: an integer joined to a letter with no currency sign is a name (`3M`, `401k`, `4K`, `Phase 2b`, and so `150M users` too). These are not quantities: a year from 1990 to 2099; an ISO date, or a day of the month beside a month's name (`27 Oct`), unless a decimal, `%` or a scale follows it or a currency sign leads it (`March 12%`, `June 30.5 million`, `US$30 June` are quantities); a number joined to letters (`FY2025`, `Q3`, `COVID-19`, `5G`, `21st`); a filing form (`10-K`, `8-K`, `20-F`); a section's or an item's number (`section 13.3`, `Item 10`); anything in a URL or after a slash (`fairband-review/1`); and an integer of one digit with no scale or unit word. Small counts are written in words.

A cite's text is one number: an optional sign or parentheses (a negative), `$`, the digits with their thousands separators, a scale word (`thousand`, `million`, `billion`, `trillion`, or `k`, `m`, `mn`, `b`, `bn`, `tn`), and a suffix, `%` (or `percent`), `x` (or `×`, or `X` joined to the number), `years`, or none. The rounding is design.md 9.2's, by the ref's unit:

| Unit | Written to | Suffix |
|---|---|---|
| currency (a total) | whole dollars, or with a scale word at the cite's own precision | `$` or none |
| a price (`snapshot:<id>/price`, `/inputs/price`, a `close:`) | cents | `$` or none |
| per-share (a value a share, a level, an EPS) | cents, or whole dollars as a value and its levels are written | `$` or none |
| percent | one decimal of the fraction × 100 | `%` |
| multiple | two decimals | `x` or none |
| years | one decimal | `years` or none |
| score | two decimals | none |
| count | a whole number, or with a scale word at the cite's own precision; a count takes no `$` | none |

The cite must be written at that rounding or coarser on its grid, so `$12.345` is never a price and `$150` is not one either, and lie within half a step of the value: `22.7%` cites 0.22702, `23%` does not. A ref with no unit (an intermediate, a vendor field) takes any suffix and is compared at the cite's own precision. Four rules more, so a report reads as design.md 9.1 and 9.2 ask:

- A scale word. A total may be cited in its scale with `$` or none, `$391 billion`, `$2.1bn`, `$1.5B`, `$126M`, and a count with none, `12 billion`, compared at the cite's own precision in that scale (the decimals it was written with) and with two significant figures at least: `$2.1 billion` cites 2,123,000,000 and `$2.10 billion` does not; `$2 billion` and `$0.4 billion` are `wrong unit`, the detail naming the rule, as is `$1.0 billion` of a share count. A whole-dollar total still passes.
- Signed outflows. The lines the store signs as outflows, capital spending, dividends and buybacks (as `fact:` lines, the tables' rows of them and the snapshot's trailing inputs; not the net investing or financing flows), may be cited by their size: "capital spending was $126,000,000" cites −126,000,000. A cite with a sign (`−$126,000,000`, `($126,000,000)`) must match the signed value.
- A ratio as a percentage. A `%` cite may cite a multiple that is a ratio of two figures in one unit, a `derived:` ratio or a table's ratio cell, compared at × 100: "stock compensation was 9.5% of net income" cites a ratio of 0.0952.
- Prices to cents. A share price, `snapshot:<id>/price`, its `inputs/price` and a `close:`, is cited to cents; a value a share, a level or an EPS to cents or to whole dollars (design.md 9.2, "values to whole dollars").

### 16.4 Derivations

The agent's arithmetic is a tool output (spec 13.4): `ratio` (a ÷ b), `difference`, `sum`, `growth` (a ÷ b − 1) and `cagr` ((a ÷ b)^(1/years) − 1), over two refs of 16.2 resolved for the company, a table cell included. The unit: multiple for a ratio of two figures in one unit; percent for growth and cagr; a difference or a sum keeps the shared unit; none otherwise. A division by zero, a cagr over a negative ratio and a result that is not finite have no value. A ref that names no number refuses the call. Each result is stored with its refs and cited as `derived:<id>`; it rests on the snapshot its operands rest on.

### 16.5 The financial tables

The six five-year tables of the report's section 4 (spec 13.5; design.md 9.3), computed by the server from the stored statements and the engine's readings, each cell with its ref: growth and profitability, cash flow, balance sheet and solvency, returns on capital, capital allocation, quality scores. A cell that is one stored line cites it as `fact:`; any other cites itself as `table:`. The agent cites the cells and derives none of them; a cell the lines cannot give holds no figure, and a cite of it is `unresolved reference`.

### 16.6 The appendixes and the export

Appendix A and Appendix B are generated from the records when the report is read, never written by the agent. Appendix A: the snapshot the report rests on; every input with its tag (DATA, RULE or JUDGMENT, the review's entries when the report rests on a review), its value at full precision and its provenance; the overrides inside the review with their reasons and evidence; the bridge; the secondary valuation's parts year by year; the checks that ran, the four structural checks and the six failures, each with its rule; the versions (method, policy, settings hash, `fairband-review/1`, `fairband-secondary/1`); and the classifier's evidence. Appendix B: the terms of section 13 the sections use. The Markdown export opens with a line naming the company, the mode, the date, the actor and the revision, then the stance and the snapshot with its price date, the sections under their headings with each cite as its text, Appendix A as tables and Appendix B as a list.
