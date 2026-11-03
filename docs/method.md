# Fairband method, as built

| | |
|---|---|
| Method version | `fairband-mechanical/0.6` (`fairband.engine.METHOD_VERSION`) |
| Policy version | `fairband-policy-v5` (`src/fairband/policy/fairband-policy-v5.toml`) |
| Status | The single statement of the method the engine runs. Written 2026-11-02 from the code and the specs. |
| Rule of precedence | Where this document and any other document disagree, this document describes what runs. If the code disagrees with this document, one of them has a defect; fix the defect and keep the two aligned. |
| Update rule | Every change to the engine, the classifier, the universe rule or a policy value changes this document in the same commit, and bumps the method version when the value of any row can move. |

The reasons behind the rules are not restated here. They live in `docs/legacy/design.md` (the original design and the literature), `docs/legacy/research.md` (the founder's decisions D1 to D17), the mechanical screen spec, the calibration spec and the growth routes spec under `docs/superpowers/specs/`. Section 12 maps each rule to its source.

## 0. How to read this document

- **r** is the required return, **g_T** the terminal growth, **N** the runway in years (on the revenue-growth route, its explicit period, section 5a). Rates are fractions. Totals are in US dollars; per-share figures in dollars a share.
- "Trailing" means the trailing twelve months: the last four reported quarters summed (section 4.2). "Fiscal years" means the annual series.
- Every number the engine reads is either DATA (from a vendor, with its source and dates), RULE (from the policy file, with a source line) or an estimate under a named method. Every valuation constant that the literature or the founder set lives in the policy file (4.1); the code holds only the method's structural constants (4.1a).
- A phase is one of Damodaran's six: Start-up, Young Growth, High Growth, Mature Growth, Mature Stable, Decline. A route is the valuation method for a phase. Three routes are built: Mature Growth (section 5), the revenue-growth route that High Growth and Young Growth share (section 5a) and Mature Stable (section 6). Start-up and Decline get a row, a phase and a refusal (section 7).
- A refusal is a result with no value and a reason. It is never an exception, and the row is never missing.
- Determinism: the same inputs under the same policy and method version give the same result, bit for bit.

## 1. The universe

One FMP `company-screener` call per refresh, reused for 24 hours. A listing is admitted when all of these hold:

1. the exchange is NYSE, NASDAQ or AMEX;
2. it is not an ETF or a fund, and it is actively trading;
3. its market cap, in US dollars from the screener, is at least $2 billion;
4. its FMP industry is not one of the excluded industries: banks, insurance and REITs in every FMP spelling, Shell Companies (SPACs), and `Asset Management`, `Financial - Capital Markets`, `Financial - Credit Services`, `Financial - Mortgages`, `Financial - Conglomerates` and `Investment - Banking & Investment Services`. `Financial - Data & Stock Exchanges` stays admitted. The match ignores case and dash style, and an industry that starts with an entry and a space is excluded too, so `Banks—Regional` is out while `Banking Software` is in;
5. its symbol does not match the preferred, warrant, unit or rights patterns (`[-.]P[A-Z]?$`, `[-.]W[ST]?$`, `[-.]U$`, `[-.]R$`) and is not on the manual exclusion list (empty today). A share class such as `BRK.B` passes;
6. its name does not match the note, debenture and preferred-share patterns, compared ignoring case (`\bnotes?\b`, `\bdebentures?\b`, `\bdue 20\d\d\b`, `\d(\.\d+)? ?%(\s|$)`, `\bpreferred\b`, `\bpreference\b`). They catch the notes, debentures and preferreds whose symbols carry no suffix, such as ABXL, "Abacus Global Management, Inc. - 8.875% Fixed Rate Senior Notes due 2028"; a rate may have a space before its percent sign ("5.25 % Debentures") or end the name ("5.625%"). No name pattern covers units, rights or depositary shares: rule 5 covers the first two, a partnership's name can carry "Common Units" or "Limited Partnership Units", and an ADR's name can carry "American Depositary Shares".

A listing that fails rule 1, 2 or 3 is skipped and not recorded (the screener request already asks for these filters; the rules are applied again on the rows). A listing that fails rule 4, 5 or 6 is recorded with its reason (`industry: <industry>`, `name pattern`, `symbol pattern` or `manual exclusion`) and gets no screen row; one that fails more than one carries the first of the industry, the name and the symbol rule. A later row whose symbol is already recorded is skipped. An admitted listing gets a cap band: Mega from $200 billion, Large from $10 billion, Mid from $2 billion.

The policy lists a manual admission list (`manual_admissions`: V, MA, GPN, payment companies that do not lend) that the universe does not yet read; Task 3 of the 2026-11-03 plan applies it.

## 2. The data the method reads

All from FMP unless named. The depth is set in `refresh/fetch.py`.

| Need | Source | Depth |
|---|---|---|
| Income statement, balance sheet, cash flow, annual | `income-statement`, `balance-sheet-statement`, `cash-flow-statement` | 11 fiscal years: ten for the ROIC aggregate plus the opening balance |
| As-reported balance sheet, annual | `balance-sheet-statement-as-reported` | 11 fiscal years; supplies the issuer's total intangibles excluding goodwill, and the lease lines |
| Income statement and cash flow, quarterly | the same endpoints with `period=quarter` | 8 quarters, for the trailing figures |
| Consensus EPS, revenue, net income with analyst counts | `analyst-estimates`, annual and quarterly | 6 annual rows and 40 quarterly rows; the engine picks periods by date, never by row order. FMP gives two analyst counts, for EPS and for revenue; the net-income count reads the EPS count |
| Street actual EPS by quarter | `earnings` | 12 rows, for the stock-compensation basis test |
| Next earnings date | `earnings` | the same rows; the next date on or after today |
| Quote: price, market cap | `quote` | current |
| Profile: country, ADR flag | `profile` | current |
| Daily closes | `historical-price-eod/full` | five years, for the price columns |
| Peers | `stock-peers` | one call a company, reused for 24 hours; not required; usable when it names a peer other than the company or is exactly the empty list; a list of objects without a symbol, or anything but a list, is unusable. The symbols stay in the stored payload; the peers' figures come from their own stored statements (5a.4); when the list leaves fewer than `peer_min` peers that count for the target margin, the company's FMP industry supplies them (5a.4) |
| Moat score | GuruFocus `summary` | current; reused for 7 days |
| EPS trailing and EPS without non-recurring items | GuruFocus `keyratios` | current; reused for 7 days |
| Statutory tax rate | the packaged OECD table `tax-rates-oecd-v1.toml` | by country and fiscal year |

A company's vendor data observed within the last 24 hours is reused, not fetched again. Every response is stored as received with any key scrubbed; normalized facts cite the response they came from. Vendor numbers are stored as decimal text; the engine computes in floats.

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

- decile 8 or higher and a slope above zero: **Rising**;
- decile 3 or lower and a slope below zero: **Declining**;
- otherwise **Stable**.

### 3.5 The rules

The first rule that fits decides the phase.

1. A Start-up (3.2) is **Start-up**.
2. A growth word of "Close to zero or negative" with a falling five-year revenue trend is **Decline**, whatever the margin.
3. With no operating margin in the last five fiscal years, the company is unclassified ("no operating margin").
4. A negative margin is **High Growth** when the margin trend is above zero, else **Young Growth** (a missing trend or a slope of exactly zero counts as not improving).
5. A margin at or above zero with a growth word of "Very High", "High" or "Moderate" is **Mature Growth**; with "Low" or "Close to zero or negative" it is **Mature Stable**. A margin of exactly zero counts as positive and is flagged.

### 3.6 The checks

A check flags the company and never changes its phase.

| Check | Flag code | When it fires |
|---|---|---|
| Growth word | `growth-word-disagrees` | Negative margin only. The growth word points to another phase: Very High → Young Growth, High → High Growth, Moderate → Mature Growth, Low → Mature Stable, Close to zero or negative → Decline. |
| Margin direction | `margin-direction-disagrees` | Margin at or above zero with a direction. The direction points to another phase: Rising → Mature Growth, Stable → Mature Stable, Declining → Decline. |
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

A company is unclassified, with the reason as its refusal, when its series has fewer than two fiscal years, no revenue for the last fiscal year, a negative last revenue, no measurable revenue growth (a non-Start-up with no positive run of two years), or no operating margin when the margin must decide. An unclassified company does not enter the deciles.

## 4. The engine's shared pieces

### 4.1 Policy values

Every value comes from `fairband-policy-v5.toml` with a source line. The ones below are the ones the method reads; the universe and refresh values are in sections 1 and 2, and the ones policy v5 adds are listed here as well.

| Value | Policy name | Source |
|---|---|---|
| r = 9% | `required_return` | stocks method v1.7 section 3 |
| g_T = 3% | `terminal_growth` | same |
| Runway N: None 5, Narrow 10, Wide 20 years | `runway_years` | same |
| Margin of safety: None 45%, Narrow 35%, Wide 25% | `margin_of_safety` | method v1.7 Step 10 |
| Fair band 0.85 to 1.15 × value | `fair_band` | Step 10 |
| Trim at 1.5 × value | `trim_multiple` | Step 10 |
| Wide-moat terminal return cap 13% | `wide_terminal_roic_cap` | design.md 6.6: r + 4 points |
| Moat: score 8 to 10 Wide, 4 to 7 Narrow, else None | `moat_wide_min`, `moat_narrow_min` | mech/1.2 |
| Base-rate medians by sales class (eleven classes) | `base_rates` | Base Rate Book, exhibit 4 |
| Held-rate cap by sales class: the 90th-percentile five-year sales growth (eleven classes) | `base_rates`, `sales_p90_5y` | Base Rate Book, Sales Growth exhibit 4; growth routes spec 5.4; founder decision 2026-11-03 |
| Inflation addition 2 points | `inflation_addition` | mech/1.2; policy value |
| Marginal return span 5 years | `marginal_return_span_years` | calibration spec 5.1; policy value |
| Marginal usability: capital grew by at least 20% | `marginal_capital_growth_min` | calibration spec 5.1; policy value |
| Fallback return window 3 years | `fallback_return_years` | calibration spec 5.1; policy value |
| Fade 5 years | `fade_years` | calibration spec 5.4; Damodaran's template |
| High-growth years 5 | `high_growth_years` | growth routes spec 5.4; Damodaran's template H2, H3; policy value |
| Margin convergence year 10 | `margin_convergence_year` | growth routes spec 5.5; Damodaran's template H2; policy value |
| Peer minimum: 3 mature peers | `peer_min` | design.md 6.2 and 6.7; no source gives the number |
| Industry peers: at most 10 | `industry_peer_max` | growth routes spec 5.5; no source gives the number; founder decision 2026-11-03 |
| Peer margin: 5 fiscal years at least | `peer_margin_min_years` | growth routes spec 5.5; Damodaran H64; policy value |
| Bounds of the margin the price needs: −50% to 100% | `implied_margin_bounds` | no source (growth routes spec 5.11) |
| Return sensitivity 15% and 9% | `roic_sensitivity` | no source |
| Thin consensus: fewer than 5 analysts | `analyst_min` | method v1.7 section 3 |
| Large non-recurring item: 5% of trailing EPS | `nri_flag_share` | spec 6.7 |
| Value spread flag: 30% | `value_spread_flag` | no source |
| Long runway flag: 10% growth | `long_runway_growth_flag` | design.md 6.5 change 3 |
| Margin flag: 1.5 × median, 10% above the high, 6 years at least | `margin_flag_ratio`, `margin_flag_above_high`, `margin_flag_min_years` | mech/1.2 |
| Heavy capex: above 50% of operating cash flow | `capex_ocf_flag` | method v1.7 Step 0 |
| Equity raise: issuance at or above 1% of market cap | `equity_raise_share` | method v1.7 Step 0 |
| Stock-compensation basis test: 50% of after-tax SBC a share | `sbc_detect` | mech/1.2 |
| Forward P/E unit error: below 2 | `forward_pe_unit_error` | mech/1.2 |
| Validity fallback: 91 days | `validity_fallback_days` | design.md 8 |
| Aging at 0.6667 of the window | `aging_fraction` | design system |
| FMP pace: 2,850 calls a minute | `refresh.fmp_calls_per_minute` | the founder's Ultimate plan, 3,000 a minute, less 5%; spec 2026-11-03 5.2; policy value |
| 429 hold: 60 seconds | `refresh.rate_limit_hold_s` | one plan window; spec 2026-11-03 5.2; policy value |
| Excluded industries: banks, insurance, REITs and Shell Companies (section 1), and six financial ones: `Asset Management`, `Financial - Capital Markets`, `Financial - Credit Services`, `Financial - Mortgages`, `Financial - Conglomerates`, `Investment - Banking & Investment Services` | `universe.excluded_industries` | design.md 6.1; decision 2026-10-26; spec 2026-11-03 6.4 |
| Manual admissions: V, MA, GPN | `universe.manual_admissions` | founder 2026-11-03: payment companies that do not lend; spec 2026-11-03 6.4 |
| Designation edges: 0.65, 0.85, 1.15, 1.50 × value | `designation_edges` | method v1.7 Step 10 (the fair band, the trim multiple, the Narrow margin of safety); spec 2026-11-03 7.1 |
| Run-off horizon: 10 years | `runoff_years` | Damodaran's ten-year template (H2) |
| Divestiture recovery: 60% of the capital released | `runoff_recovery` | Damodaran 2009 Sears: 54% to 67% of the capital released; the midpoint; policy value |
| Distress-sale fraction: 60% of the firm value | `distress_sale_fraction` | Damodaran 2009, "Estimating Distress Sale Proceeds", choice (a), the illustration's $3 billion of $5 billion; policy value |
| Synthetic rating by interest coverage: 15 rows, D to AAA | `synthetic_rating` | Damodaran, ratings.html, "For large non-financial service firms", January 2026 |
| Ten-year default probability by rating: 15 ratings | `default_probability_10y` | Damodaran 2009, Table 5 (Altman, 1971 to 2007); D 100%; BB+ as BB (policy value) |
| Altman Z″ zones: distress below 1.1, safe above 2.6 | `z_distress`, `z_safe` | Altman 2000 |
| Piotroski F low group: 1 or below | `f_score_low` | Piotroski 2000, the 0 to 1 group |
| Burn cover flag: below 2 years | `burn_cover_flag_years` | no source |

The run-off, distress-sale, rating, default-probability, Z″, F and burn-cover values are read by the Decline and Start-up routes, which come with method 0.7 (section 11).

Policies v1 to v4 stay in the package unchanged, because the snapshots valued under them cite their hashes. The engine loads v5 only.

### 4.1a Constants in code

These set the method's structure, not a valuation judgment, and live in the code: the ROIC window of ten years and its minimum of five; the growth span of three years; the trend window of five years with at least three points; the margin-direction deciles 8 and 3; the 80 to 100 days between consecutive quarters; the margin flag's ten-year window; the implied-growth scan from −50% to 200% in steps of 1% to a tolerance of 1e-7, on the Mature Growth and the revenue-growth routes alike, and the same step and tolerance for the margin the price needs within its policy bounds; the peers' ten-year margin window; the three-year horizon of the expected return; the lease-accounting date of 15 December 2019.

### 4.2 Trailing figures and the share count

The trailing figures are the sums of the last four quarterly income statements when there are four and each ends 80 to 100 days after the one before, joined to the quarterly cash-flow statements by period end: revenue, operating income, net income, diluted EPS, stock compensation, operating cash flow, capital spending, dividends, buybacks and stock issued. A sum is missing when any quarter lacks its part. Otherwise the trailing figures are the last fiscal year's, flagged `trailing-on-fiscal-year`.

The diluted share count is the newest quarter's weighted average diluted shares, else the newest fiscal year's. One share count serves every year of every route.

### 4.3 The tax rate

NOPAT uses the statutory marginal rate: the OECD combined central and sub-central corporate rate for the company's country and the fiscal year. The country is the headquarters country of the FMP profile, else the universe row's. A fiscal year later than the newest year in the table takes the newest year's rate as an estimate under method `tax-rate-latest-oecd-year-v1`, flagged `tax-carried-forward`. An earlier missing year, or a country the table lacks, has no rate: the first fiscal year of the eleven-year span with an operating income and no rate refuses the company, "no statutory tax rate for <country> <year>". For a foreign filer, assembly withholds that refusal, so the route gives the foreign-filer refusal instead. The newest fiscal year's rate also converts stock compensation to after tax in the anchor (5.2), and taxes every forecast year of the revenue-growth route (5a.6).

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

The aggregate is shown and feeds the "ten-year" sensitivity (5.8). It never enters the charge. The kept years also give the revenue-growth route its own sales-to-capital (5a.5).

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
- Wide moat: the chosen measure of 4.6 before its floor, capped at 13% and never below r. When the runway charge is off: 13%. When the runway return is unavailable: r.

The same rule, applied to a given return, gives the terminal return for each sensitivity value (5.8), and on the revenue-growth route for the return on new capital at the target margin (5a.7).

### 4.8 The charge and the value

Earnings in year t are a total, on the one share count. Each year's reinvestment pays for the next year's growth:

    cash_t = earnings_t × max(0, 1 − g_{t+1} ÷ return_t)

with return_t the runway return for t < N and the terminal return for t = N, and g_{N+1} = g_T. A year whose next growth is above its return pays out nothing, never less; the first such year raises `growth-above-return`. When the charge is off, cash_t = earnings_t for t < N.

    terminal multiple = (1 + g_T) × (1 − g_T ÷ terminal return) ÷ (r − g_T)
    value = Σ_{t=1..N} cash_t ÷ (1 + r)^t + earnings_N × terminal multiple ÷ (1 + r)^N

The value a share is the total ÷ the diluted share count.

### 4.9 The moat class

From the GuruFocus Moat Score: 8 or more Wide, 4 or more Narrow, below 4 or no score None. The moat enters in three places: the runway N, the terminal return and the margin of safety. The revenue-growth route's explicit period does not read it, so there the moat enters the terminal return and the margin of safety only.

### 4.10 Levels, stance and validity

On the value at belief, each level the exact decimal product:

- buy level = value × (1 − margin of safety for the moat);
- fair band = value × 0.85 to value × 1.15;
- trim level = value × 1.5.

| Price | Five-step stance | Screen word |
|---|---|---|
| below the buy level | BUY | buy |
| from the buy level, below the fair band | ACCUMULATE / HOLD | hold |
| inside the fair band, ends included | HOLD | hold |
| above the fair band, below the trim level | HOLD — above fair band | hold |
| at or above the trim level | TRIM | trim |

The data date is the date of the newest observation among the company's stored statement facts (today, when it has none). A result is valid until the next earnings date when that date is after the data date, else 91 days after the data date. It is current until 0.6667 of the window has passed, then aging, then expired after the window's end. An expired row keeps its figures.

## 5. The Mature Growth route

A reverse DCF on net income with the reinvestment charge: year 1 from the quarterly consensus, years 2 and 3 from the annual consensus, a fade to a base-rate belief, the belief to the runway, then the terminal.

### 5.1 Guards and refusals

Before any route, in this order: no universe deciles yet; the assembly's refusal ("no financial statements", or the missing tax rate of 4.3); a foreign filer (an ADR by the profile, or a reporting currency other than USD, an unknown currency included); an unclassified company (3.8); Start-up; a phase whose route is not built, which is Decline (Mature Growth and Mature Stable have their routes, and High Growth and Young Growth share the revenue-growth route of section 5a); no positive price; no positive diluted share count; no trailing figures.

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

### 5.10 The expected return over three years

    income    = (−dividends − buybacks − stock issued) ÷ market cap, trailing flows, FMP's signs
    growth    = ((1 + g_2)(1 + g_3)(1 + g_4))^(1/3) − 1, the path's own rates
    repricing = ln(value ÷ price) ÷ 3
    total     = income + growth + repricing

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

A company the classifier puts in High Growth or Young Growth (3.5, rule 4), past the guards of 5.1. The result's route is `revenue-growth`; the phase says which of the two it is.

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

**The mature peers.** The candidates are the symbols of the latest usable `stock-peers` response stored for the company (section 2), in its order, in the exchange form (`BRK.B`), the company itself and repeats dropped. A candidate is kept when the latest universe lists it (the admitted companies of the newest refresh that admitted any) and its stored fiscal years classify, on the spot, as Mature Growth or Mature Stable on the deciles the company is valued on (3.3). A candidate outside that universe, without statements, unclassified or in another phase is dropped. Without deciles the company has no peers, and without a stored response no candidates. No vendor call is made for a peer: its figures come from the statements stored for it, its invested capital and NOPAT built by 4.4 at the statutory rate of its own country (4.3):

- its margin: the ten-year aggregate operating margin, Σ operating income ÷ Σ revenue over the last ten of its fiscal years that have both and a positive revenue, with the count of those years; none without such a year;
- its sales-to-capital: the revenue of its newest kept ROIC year (4.5) ÷ that year's average invested capital, both of the same fiscal year; none without a kept year, without a revenue for that year, or with that capital at or below zero;
- its ROIC: its ten-year aggregate (4.5), none when unavailable;
- its market cap: the one on its row in the latest universe.

**The industry fallback.** When the candidates kept leave fewer than `peer_min` peers with a margin on `peer_margin_min_years` years or more, the peers are instead the mature companies of the company's own FMP industry: every company of the latest universe whose row carries the same industry, the company itself excluded, whose fiscal years classify on the spot as Mature Growth or Mature Stable on the same deciles, the largest `industry_peer_max` of them by market cap (a company without one last, ties in symbol order), their figures read as above. The kept candidates are dropped, not merged. The row is flagged `peers-from-industry`, naming the count the candidates left, the industry and the count taken, whether the row is then valued or still refused for the target margin or for its sales-to-capital; such a row also cites `industry_peer_max` as a RULE input. A company without an industry on its universe row has no fallback. Without a stored response the candidates are none and the fallback applies.

**The target margin.** m* is the median margin of the peers with a margin on at least 5 fiscal years (`peer_margin_min_years`). With fewer than 3 such peers (`peer_min`), the row is refused "no target margin: <n> mature peers", n counting them. The row records those peers with their margins and market caps, their count, the lowest and the highest margin, and the largest of them by market cap with its margin (none when none has a market cap); the largest peer sets nothing.

### 5a.5 Sales-to-capital and reinvestment

Sales-to-capital is the revenue a dollar of new invested capital buys. The route takes, in this order:

1. **The company's own five-year marginal measure**, over the kept ROIC years of 4.5: (revenue_last − revenue_first) ÷ (capital_last − capital_first), "last" the newest kept year and "first" the kept year 5 positions earlier (`marginal_return_span_years`), capital the average invested capital, revenue that fiscal year's. Used when it is usable: capital grew, by at least a fifth of the first year's capital in size (`marginal_capital_growth_min`), and revenue grew. There is no own measure with fewer than six kept years, with either year lacking a revenue, or with no change in capital.
2. **The mature peers' median**: the median of the positive sales-to-capital among all the peers of 5a.4, when at least 3 (`peer_min`) are positive.
3. Neither: the row is refused "no sales-to-capital".

The row records the measure used ("own" or "peers", none when neither stands), the own measure and whether it is usable, the peers' median and the value used.

Reinvestment in year t pays for year t + 1's revenue; year N pays for the terminal growth at the terminal return (5a.7), as the mature routes' year N does:

    reinvestment_t = max(0, (revenue_{t+1} − revenue_t) ÷ sales-to-capital), for t = 1 … N − 1
    reinvestment_N = terminal NOPAT × g_T ÷ terminal return

A year before a fall in revenue reinvests nothing, never a negative amount; year N has no floor. The terminal NOPAT is year N's at the full tax rate (5a.7).

### 5a.6 Tax and NOPAT

    EBIT_t = revenue_t × m_t

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

Narrow or None moat: r. Wide moat: that return, capped at 13% and never below r. The runway return of 4.6 does not enter this route's charge; the cross-check reads it (5a.11).

### 5a.8 The required return

r in every year and in the terminal. Under the band of every valued row on this route the drawer says so: "Discounted at the required return of <r> in every year; Damodaran's template starts higher and falls to it by year 10".

### 5a.9 Equity and the value a share

    equity = firm value − debt + cash
    value a share = equity ÷ diluted shares

From the newest annual balance sheet: debt is short-term plus long-term debt (`shortTermDebt`, `longTermDebt`), cash is cash and equivalents plus short-term investments (`cashAndCashEquivalents`, `shortTermInvestments`). No other line enters. A line without a value counts as nil, and assembly's note on the input names it ("longTermDebt not presented"); a figure with both its lines missing is unknown and counts as nil. Either case flags `line-not-presented:debt` or `line-not-presented:cash`, the sentence naming the missing lines.

A value a share at or below zero refuses the row "value not positive under the reinvestment charge", which keeps its figures (5a.1). Otherwise the levels, the stance and the validity are 4.10's, with the moat's margin of safety.

### 5a.10 What moves with the price

- **The implied growth**: the held rate of years 4 to H at which the value a share equals the price, the fade recomputed from it; years 1 to 3, the margin path, the terminal return and the sales-to-capital stay. Solved as 5.7 solves: a scan from −50% to 200% in steps of 1% for the first sign change, then bisection to 1e-7; None when the scan finds no sign change.
- **The margin the price needs**: the target margin at which the value a share equals the price, the margin path rebuilt from it and the terminal return re-read at each trial from the return on new capital there (5a.7). Solved the same way between the policy's bounds, −50% and 100% (`implied_margin_bounds`); None without a sales-to-capital or when the scan finds no sign change. It is computed on a valued row and on the two refusals that keep the rebuild keys, "no target margin" and "value not positive".
- **The multiples and the growth share** of 5.9: trailing P/E reported and clean; the forward P/E on the anchor's NTM EPS (5.2) when the anchor stands, none when it refuses; a P/E only for a positive EPS; the growth share of price when EPV exists.
- **The expected return** of 5.10, its growth term on the revenue path's own rates, ((1 + g_2)(1 + g_3)(1 + g_4))^(1/3) − 1.
- **The cross-check's implied growth** (5a.11).

The rebuild keys (5a.14), with the policy's r, g_T and margin convergence year (and, for the margin solve, its bounds and the wide-moat cap), rebuild the path, the margin path and the charge, so a price refresh moves each of these figures from the intermediates alone (section 10).

### 5a.11 Sensitivities, the cross-check and the implied-return check

- **By target margin**: the value a share at the lowest, the median and the highest margin of the counted peers, keys `low`, `median`, `high`, each with its own terminal return from the return on new capital at that margin. `median` is the row's value. The value-spread flag reads the three on 5.8's rule, with one addition: when the value at the lowest margin is at or below zero and the median's is positive, where 5.8's rule is silent, the flag fires with "The value is at or below zero at the lowest mature-peer margin of <x.x%> and <y.yy> a share at the median, so the spread across the peers' margins is unbounded."
- **The growth-route cross-check**: as on a Mature Stable row (6.4), `growth_route` carries the Mature Growth route's value a share under the row's own moat and returns, with the keys that rebuild it and its implied growth at the price, or only the reason that route would refuse. It sets nothing.
- **The implied-return check**: the return on new capital at the target against the median ten-year aggregate ROIC of the peers of 5a.4 that have one. Above that median, the row is flagged `return-above-peers` with both figures. With no peer ROIC there is no check. It flags only.

### 5a.12 Young Growth

The same route: on the same inputs a Young Growth row has High Growth's value, levels and figures. Its intermediates add `failure_probability`, with no value and the reason "no survival table fits a listed company above $2 billion"; the value is the going-concern value, flagged `failure-not-charged`. The drawer shows the failure probability as unavailable with that reason, and says the value range is not computed in tier 1.

### 5a.13 Flags

In order: `sbc-basis-unknown`, when the cross-check has a value and its anchor's stock-compensation basis is unknown (5.2); the path's, `path-held`, `consensus-above-base-rate` (5a.3), then `few-analysts`; the capital build's, the ROIC flags of 4.5 then the `line-not-presented:<field>` flags of the ROIC years (4.4); `line-not-presented:debt`, then `line-not-presented:cash`; `peers-from-industry` (5a.4); `tax-loss-history-unknown` (5a.6); `return-above-peers`; `failure-not-charged` on a Young Growth row; the trailing flags (`margin-flag`, `equity-raise`, `negative-fcf`, `heavy-capex`, `large-nri`); `value-spread` over the three target margins (5a.11). The result puts the assembly's flags and the classifier's checks before these, and keeps the first flag of each code.

Never raised here: `path-on-eps`, `charge-zeroed`, `return-floored`, `growth-above-return`, `long-runway-high-growth`, nor the cross-check's earnings-path flags. The charge does not read the runway return, and the path is on revenue.

### 5a.14 Intermediates and tagged inputs

Intermediates: `ntm_revenue`; `path` (base_year, the revenue analysts of the two landing years, which steps were held, the sales class and its cap); `path_steps`, g_2 and g_3 as resolved; `growth_rates`, years 1 to N; `margin_path` (start, target, by_year); `target_margin` (value, count, low, high, largest_symbol, largest_margin, the counted peers with each one's margin and market cap, source (fmp or industry) and industry); `revenue_by_year`, `ebit_by_year`, `tax_by_year`, `nopat_by_year`, `reinvestment_by_year`, `fcff_by_year`; `terminal_roic`, `terminal_nopat` (5a.7), `terminal_value`, `firm_value`, `equity`, `value_per_share`; `value_by_margin`; `return_on_new_capital`, `peer_roic_median`; `failure_probability` on Young Growth only; `eps`, `epv`, `dividend_yield`, `net_buyback_yield`, `income_basis`, `price_facts`, `growth_route`; the rebuild keys; and at the price `implied_growth`, `implied_margin`, `multiples`, `growth_share`, `expected_return` and the cross-check's `implied_growth`.

The rebuild keys: `revenue_path` (revenue0, ntm_revenue, the consensus steps as found with None for a missing one, hold None, or the cap when it binds, high_growth_years, fade_years), `margin_start`, `tax_rate`, `moat`, `debt`, `cash`, `shares` and `sales_to_capital` (used, own, own_usable, peers, value); on a valued row `margin_path`'s target and `terminal_roic` complete them. A refusal that keeps them keeps the moat class for the price refresh; the screen shows the moat on a valued row only.

Tagged inputs. DATA: the fiscal years on file, price, diluted shares, next earnings date, daily closes; market cap, trailing revenue, operating income, EPS, dividends, buybacks and stock issued; the aggregate ROIC and the runway return, as in 5.12, though neither enters this route's charge; the newest tax rate; the moat score; GuruFocus EPS and EPS without non-recurring items; `ntm_revenue`, from the quarterly consensus; `path_step_2` and `path_step_3`, the annual consensus steps as found, a held one empty with the note "no consensus step: the year holds the rate of the year before"; `target_margin`, source "FMP stock-peers and the peers' statements" (on the industry fallback, "the universe's <industry> industry and the peers' statements", the note naming the industry), note "the median ten-year operating margin of <n> mature peers"; `sales_to_capital`, either the own measure cited to the statements (an estimate under the intangibles method when invested capital took the as-reported total, 4.4) with the note "the company's own five-year marginal measure", or the peers' median cited to the peers' source with the note "the mature peers' median; the own measure is not usable" (on the industry fallback, "the mature peers' median (<industry> industry); the own measure is not usable"); `debt` and `cash`, cited to the statements, with assembly's note naming a missing line. RULE: r, g_T, the moat class, the margin of safety, the terminal return, `high_growth_years`, `held_growth_cap` with the class and whether it binds in its note, `fade_years`, `margin_convergence_year`, `peer_min`, and on a row whose peers are the industry fallback's, `industry_peer_max`.

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
- Own sales-to-capital, kept years with revenue and average capital from (1,000, 400) to (2,500, 900) five positions later: 1,500 ÷ 500 = 3.0, usable. Capital from 400 to 420 instead: 75.0, not usable, capital grew 5%. Falling revenue: not usable. Five kept years, or a year without revenue: none.
- Peers with margins of 10% on 10 years, 30% on 8, 20% on 6 and 40% on 3: target 20% on 3 peers, low 10%, high 30%, the largest by market cap the 30% peer; two peers give none. Peers' sales-to-capital 2.5, 1.5 and 3.0: median 2.5; two give none. Peers' ROIC 12%, 20% and 15%: median 15%.

The route's tests pin the refusal order, the flag order, the `path-held` and `few-analysts` sentences, Young Growth's equality with High Growth, and a price refresh that rebuilds every price-side figure from the intermediates.

## 6. The Mature Stable route

The stable-growth value on normalized trailing earnings, charged as the Mature Growth route charges.

### 6.1 Refusal

E = trailing net income − the non-recurring gap × diluted shares. A missing or non-positive E refuses: "no positive trailing earnings".

### 6.2 Normalized earnings

When the margin flag (8) fires and both the trailing operating margin and the ten-year median margin are positive, E is scaled by median margin ÷ trailing margin, and the row says so. Otherwise E stands.

### 6.3 The value

The path grows at g_T in every year from E (year 1 is E, with no (1 + g_T) factor) to the moat's runway N. The value is section 4.8 on that path with the row's charge: the runway return in years 1 to N − 1, the terminal return in year N and the terminal, off in the runway years when 4.6 turns it off. When the runway return equals the terminal return with the charge on, this equals the one-stage formula E × (1 − g_T ÷ terminal return) ÷ (r − g_T). A row floored at r in every year values at EPV. A runway return above the terminal return, or a charge off, lifts the value, and more for a longer runway.

EPV = E ÷ r is shown as the no-growth value. The levels sit on the stable-growth value.

### 6.4 The growth-route cross-check

When the row's inputs allow the Mature Growth route (a positive anchor, a path without refusal), the intermediates carry that route's value a share under the row's own moat and returns, with the keys that rebuild its path, and its implied growth at the price. When the growth route would refuse, only its reason is carried. The levels and the stance never read it.

### 6.5 Expected return, multiples, flags and inputs

The expected return of 5.10 with g_T as each of the three rates. Trailing P/E reported and clean; no forward P/E. Flags: the ROIC flags of 4.5 and 4.6, `charge-zeroed` and `return-floored` included, then the trailing flags. Never `sbc-basis-unknown`, `path-on-eps`, `few-analysts`, `growth-above-return`, `long-runway-high-growth` or `value-spread`; so a thin consensus behind the cross-check does not show on a stable row, a known gap. Inputs: the common DATA inputs of 5.12 plus trailing net income; the RULE inputs plus the runway years and a belief of g_T.

## 7. Phases without a route, and foreign filers

| Case | Refusal |
|---|---|
| Start-up | "Start-up: no value by design; the price-implied requirement comes with the Start-up route" |
| Decline | "Decline route not built yet" |
| Foreign filer: an ADR, or a reporting currency other than USD | "foreign filer: currency and share-unit handling not built yet" |

Each keeps its phase, its classifier evidence, its price and its price columns. Assembly withholds the missing-tax-rate refusal from a foreign filer (4.3), so the route reaches the foreign-filer guard; "no financial statements" still refuses a foreign filer first.

## 8. The flags

A flag warns and never changes a value, a level or a stance. Each has a code, a short word for the column and one sentence for the drawer.

| Code | Rule |
|---|---|
| `growth-word-disagrees`, `margin-direction-disagrees`, `fcf-sign`, `short-history`, `margin-zero`, `currency-change` | the classifier checks, 3.6 |
| `currency-unknown` | no annual income statement gives the reporting currency (the screener row never carries one); the company is treated as a foreign filer |
| `tax-carried-forward` | a fiscal year after the tax table's newest year took that year's rate |
| `leases-not-on-balance-sheet` | a balance sheet before 15 December 2019 shows no lease assets |
| `trailing-on-fiscal-year` | the quarters on file are not four consecutive quarters |
| `sbc-basis-unknown` | the stock-compensation basis test lacked an input; on the revenue-growth route, only when the cross-check has a value |
| `path-on-eps` | years 2 and 3 grow at the consensus EPS steps |
| `few-analysts` | a present path step lands on a year with fewer than 5 analysts or no count: the EPS count on the earnings path (5.3), the revenue count on the revenue path (5a.2) |
| `path-held` | a consensus revenue step is missing, so its year holds the rate of the year before; names the fiscal years that left it missing and the rates held (5a.2) |
| `consensus-above-base-rate` | the year-3 consensus revenue growth is above the sales class's 90th-percentile five-year sales growth, so years 4 and 5 hold the cap and the fade starts from it (5a.3) |
| `peers-from-industry` | FMP's peers left fewer than `peer_min` that count for the target margin, so the peers are the largest `industry_peer_max` mature companies of the company's FMP industry in the universe (5a.4) |
| `roic-unavailable` | fewer than 5 ROIC years |
| `roic-on-n-years` | 5 to 9 ROIC years |
| `ten-year-roic-unavailable` | the ten-year capital sum is at or below zero |
| `line-not-presented:<field>` | an optional balance-sheet line counted as nil in a ROIC year (4.4) |
| `line-not-presented:debt`, `line-not-presented:cash` | the bridge to equity counted a debt or cash line as nil: the figure is unknown, or assembly's note names a line the newest annual balance sheet does not present (5a.9) |
| `charge-zeroed` | the runway charge is off, 4.6 rule 4 |
| `return-floored` | the chosen return measure was below r |
| `growth-above-return` | a year's next growth exceeds its return; its payout is floored at zero |
| `tax-loss-history-unknown` | the revenue-growth forecast has a year whose EBIT is below zero, or the trailing margin is below zero; the tax carry starts at zero and the terminal is taxed in full (5a.6, 5a.7) |
| `return-above-peers` | the return on new capital at the target margin is above the mature peers' median ten-year ROIC (5a.11) |
| `failure-not-charged` | a Young Growth row: the failure probability is unavailable and the value is the going-concern value (5a.12) |
| `margin-flag` | the trailing operating margin is 1.5 × its ten-year median or more (a positive median), or above its ten-year high by 10% of the high's size or more; needs 6 fiscal years with a margin. The word is "Newly profitable" when the median is at or below zero, "Possible cycle peak" when the window holds a loss year, else "Margin above history" |
| `equity-raise` | trailing stock issued is 1% of market cap or more |
| `negative-fcf` | trailing operating cash flow plus capital spending is below zero |
| `heavy-capex` | trailing capital spending is above 50% of a positive operating cash flow |
| `large-nri` | the non-recurring gap is 5% of trailing EPS or more, in either direction |
| `long-runway-high-growth` | a 20-year runway with a belief or an implied growth of 10% or more |
| `value-spread` | the value spans 30% or more across the first three return keys or across the three runways; on the revenue-growth route, across the three target margins, or the value at the lowest is at or below zero while the median's is positive (5a.11) |

The three lease and line flags sit on nearly every valued row today; their redesign is a known item.

## 9. The refusal reasons

| Reason | Where |
|---|---|
| no universe deciles yet | 3.3 |
| no financial statements | assembly |
| no statutory tax rate for <country> <year> | 4.3 |
| foreign filer: currency and share-unit handling not built yet | 7 |
| fewer than two fiscal years; no revenue for the last fiscal year; negative revenue; no measurable revenue growth; no operating margin | 3.8 |
| Start-up: no value by design …; <phase> route not built yet | 7 |
| no price; no diluted share count; no trailing figures | 5.1 |
| no trailing revenue; no statutory tax rate | 5.1, 5a.1 |
| no trailing operating income | 5a.1 |
| incomplete NTM consensus | 5.2, 5a.2 |
| no positive forward anchor; forward P/E below 2: unit error | 5.2 |
| no positive consensus revenue; consensus revenue falls to zero or below within the path | 5a.2 |
| no target margin: <n> mature peers | 5a.4 |
| no sales-to-capital | 5a.5 |
| consensus earnings turn negative within the path | 5.3 |
| value not positive under the reinvestment charge | 5.6, 5a.9 |
| no positive trailing earnings | 6.1 |
| data fetch failed: <the failed required endpoints> | the refresh, when an annual statement or the quote fails (section 2) |
| data fetch failed: <error class>: <message>; data fetch incomplete: rate limited; valuation failed: <error class>: <message> | the refresh, when a company's fetch raises, is cut by an HTTP 429, or its valuation raises |

## 10. Refresh kinds and what moves

- **Full refresh**: the universe, the data of section 2 for every admitted company, the deciles, then every company classified and valued, one snapshot per company. A company fetched within 24 hours is not fetched again.
- **Price refresh**: fresh quotes for the latest universe's admitted companies (before any universe, every company with a snapshot), then each latest snapshot repriced from its intermediates alone: the value, the levels and the validity window stay; the stance, the implied growth and its sensitivities, the margin the price needs (revenue-growth rows), the growth-route cross-check's implied growth, the multiples, the growth share, the expected return and the long-runway flag are recomputed; the price input becomes the new quote. A refusal snapshot takes only the new price, its date and the price input, except a revenue-growth refusal whose intermediates carry `revenue_path`: the two refused for their target margin ("no target margin: <n> mature peers") or for a value not positive ("value not positive under the reinvestment charge"). Such a row also recomputes its margin the price needs from its rebuild keys (5a.10); its other figures stay. The price columns (section 2, daily closes) do not move. A snapshot valued under another policy version is not repriced, "policy changed: run a full refresh"; under another method version, "method changed: run a revalue".
- **Revalue**: the engine on the stored facts of every company, with the latest stored deciles, no vendor call and no freshness window. New snapshots under the current method and policy versions.

Snapshots are appended, never changed. The screen reads the latest snapshot per company.

## 11. Versions

| Method | Date | What changed |
|---|---|---|
| 0.1 | 2026-10-31 | The mechanical screen as first built: the charge at the ten-year aggregate ROIC in the runway years, the terminal from the aggregate, a one-step drop from year 3 to the belief, no payout floor; Mature Stable on the one-stage formula at the terminal return. Policy v1. |
| 0.2 | 2026-11-01 | The calibration: the runway return (4.6), the payout floor (4.8), the fade (5.5), the terminal from the runway return (4.7), the four return keys (5.8), the growth-route cross-check (6.4), the revalue kind. Policy v2 adds four values (the marginal span, the capital-growth test, the fallback window, the fade years) and the recorded decision to keep return on invested capital over return on equity. |
| 0.3 | 2026-11-02 | Mature Stable charges as Mature Growth does (6.3): the runway return through the runway, the terminal return after. Policy unchanged. |
| 0.4 | 2026-11-02 | The High Growth and Young Growth routes (section 5a), the held rate capped at the sales class's base-rate 90th percentile (5a.3), with the `stock-peers` call (section 2); the name patterns on the universe (section 1). Policy v3 adds five values and the `sales_p90_5y` column of `base_rates` (4.1). |
| 0.5 | 2026-11-03 | The industry fallback for the peers (5a.4). Policy v4 adds `industry_peer_max`. |
| 0.6 | 2026-11-03 | Policy v5 adds the values of the limiter, the universe's admission list and six excluded industries, the designation edges and the Decline and Start-up routes' values (the routes come with 0.7). |

A snapshot names the method and policy versions that produced it. A price refresh refuses to reprice a snapshot from another method version.

## 12. Sources

The labels are those of the research notes in the openalice workspace (H), the stocks repo's growth-duration (G), terminal-rate (T) and valuation (V) notes, and the founder's decisions in `docs/legacy/research.md` (D).

| Rule | Source |
|---|---|
| The six phases, the two deciding variables, the decile grid, the duration test for Decline | Damodaran, *The Corporate Life Cycle* ch. 2 and 3; design.md 5 |
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
| The levels, the stance, the expected return, EPV, the P/E bases | stocks method v1.7 Steps 3, 7, 9, 10 |
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
| Non-recurring gap | GuruFocus EPS trailing less EPS without non-recurring items |
| Growth word, margin direction | The classifier's reading of the deciles for revenue growth and for the margin trend |
| Check | A classifier warning that never changes the phase |
| Snapshot | One company's result under one refresh, with the versions that produced it |
| Mature peers | The company's FMP `stock-peers` that the latest universe lists and the classifier puts in Mature Growth or Mature Stable; when fewer than `peer_min` of them count, the largest mature companies of the company's FMP industry |
| Target margin | The operating margin the revenue-growth route moves to by year 10: the median ten-year margin of the mature peers |
| Sales-to-capital | The revenue a dollar of invested capital buys: the company's change in revenue ÷ its change in capital, or a peer's revenue ÷ its capital. The revenue-growth route reinvests the next year's revenue increase ÷ sales-to-capital |
| Margin the price needs | The target margin at which the revenue-growth value a share equals the price |
| Return on new capital at the target | Target margin × (1 − tax rate) × sales-to-capital: the after-tax return on new capital once the margin reaches the target. It sets the terminal return by the moat's rule and is checked against the peers' ROIC |
| Held rate | The growth the revenue path holds in years 4 and 5 before its fade: g_3 as resolved, or, for the implied growth, the rate at which the value equals the price. A held step is a missing consensus step that takes the rate of the year before |
