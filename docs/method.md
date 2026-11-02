# Fairband method, as built

| | |
|---|---|
| Method version | `fairband-mechanical/0.3` (`fairband.engine.METHOD_VERSION`) |
| Policy version | `fairband-policy-v2` (`src/fairband/policy/fairband-policy-v2.toml`) |
| Status | The single statement of the method the engine runs. Written 2026-11-02 from the code and the specs. |
| Rule of precedence | Where this document and any other document disagree, this document describes what runs. If the code disagrees with this document, one of them has a defect; fix the defect and keep the two aligned. |
| Update rule | Every change to the engine, the classifier, the universe rule or a policy value changes this document in the same commit, and bumps the method version when the value of any row can move. |

The reasons behind the rules are not restated here. They live in `docs/legacy/design.md` (the original design and the literature), `docs/legacy/research.md` (the founder's decisions D1 to D17), the mechanical screen spec and the calibration spec under `docs/superpowers/specs/`. Section 12 maps each rule to its source.

## 0. How to read this document

- **r** is the required return, **g_T** the terminal growth, **N** the runway in years. Rates are fractions. Totals are in US dollars; per-share figures in dollars a share.
- "Trailing" means the trailing twelve months: the last four reported quarters summed (section 4.2). "Fiscal years" means the annual series.
- Every number the engine reads is either DATA (from a vendor, with its source and dates), RULE (from the policy file, with a source line) or an estimate under a named method. Every valuation constant that the literature or the founder set lives in the policy file (4.1); the code holds only the method's structural constants (4.1a).
- A phase is one of Damodaran's six: Start-up, Young Growth, High Growth, Mature Growth, Mature Stable, Decline. A route is the valuation method for a phase. Two routes are built: Mature Growth and Mature Stable. The other four phases get a row, a phase and a refusal (section 7).
- A refusal is a result with no value and a reason. It is never an exception, and the row is never missing.
- Determinism: the same inputs under the same policy and method version give the same result, bit for bit.

## 1. The universe

One FMP `company-screener` call per refresh, reused for 24 hours. A listing is admitted when all of these hold:

1. the exchange is NYSE, NASDAQ or AMEX;
2. it is not an ETF or a fund, and it is actively trading;
3. its market cap, in US dollars from the screener, is at least $2 billion;
4. its FMP industry is not one of the excluded industries: banks, insurance and REITs in every FMP spelling, and Shell Companies (SPACs). The match ignores case and dash style, and an industry that starts with an entry and a space is excluded too, so `Banks—Regional` is out while `Banking Software` is in;
5. its symbol does not match the preferred, warrant, unit or rights patterns (`[-.]P[A-Z]?$`, `[-.]W[ST]?$`, `[-.]U$`, `[-.]R$`) and is not on the manual exclusion list (empty today). A share class such as `BRK.B` passes.

A listing that fails rule 1, 2 or 3 is skipped and not recorded (the screener request already asks for these filters; the rules are applied again on the rows). A listing that fails rule 4 or 5 is recorded with its reason and gets no screen row. A later row whose symbol is already recorded is skipped. An admitted listing gets a cap band: Mega from $200 billion, Large from $10 billion, Mid from $2 billion.

Known gaps, for the next piece: some financials pass rule 4 under industries the list does not name (Capital Markets, Credit Services, Asset Management), and some notes and preferreds pass rule 5 because their symbols carry no suffix.

## 2. The data the method reads

All from FMP unless named. The depth is set in `refresh/fetch.py`.

| Need | Source | Depth |
|---|---|---|
| Income statement, balance sheet, cash flow, annual | `income-statement`, `balance-sheet-statement`, `cash-flow-statement` | 11 fiscal years: ten for the ROIC aggregate plus the opening balance |
| As-reported balance sheet, annual | `balance-sheet-statement-as-reported` | 11 fiscal years; supplies the issuer's total intangibles excluding goodwill, and the lease lines |
| Income statement and cash flow, quarterly | the same endpoints with `period=quarter` | 8 quarters, for the trailing figures |
| Consensus EPS, revenue, net income with analyst counts | `analyst-estimates`, annual and quarterly | 6 annual rows and 40 quarterly rows; the engine picks periods by date, never by row order. FMP gives one analyst count, for EPS; the net-income count reads it too |
| Street actual EPS by quarter | `earnings` | 12 rows, for the stock-compensation basis test |
| Next earnings date | `earnings` | the same rows; the next date on or after today |
| Quote: price, market cap | `quote` | current |
| Profile: country, ADR flag | `profile` | current |
| Daily closes | `historical-price-eod/full` | five years, for the price columns |
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

Every value comes from `fairband-policy-v2.toml` with a source line. The ones below are the ones the method reads; the universe and refresh values are in sections 1 and 2.

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
| Inflation addition 2 points | `inflation_addition` | mech/1.2; policy value |
| Marginal return span 5 years | `marginal_return_span_years` | calibration spec 5.1; policy value |
| Marginal usability: capital grew by at least 20% | `marginal_capital_growth_min` | calibration spec 5.1; policy value |
| Fallback return window 3 years | `fallback_return_years` | calibration spec 5.1; policy value |
| Fade 5 years | `fade_years` | calibration spec 5.4; Damodaran's template |
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

Policy v1 stays in the package unchanged, because the snapshots of the first run cite its hash. The engine loads v2 only.

### 4.1a Constants in code

These set the method's structure, not a valuation judgment, and live in the code: the ROIC window of ten years and its minimum of five; the growth span of three years; the trend window of five years with at least three points; the margin-direction deciles 8 and 3; the 80 to 100 days between consecutive quarters; the margin flag's ten-year window; the implied-growth scan from −50% to 200% in steps of 1% to a tolerance of 1e-7; the three-year horizon of the expected return; the lease-accounting date of 15 December 2019.

### 4.2 Trailing figures and the share count

The trailing figures are the sums of the last four quarterly income statements when there are four and each ends 80 to 100 days after the one before, joined to the quarterly cash-flow statements by period end: revenue, operating income, net income, diluted EPS, stock compensation, operating cash flow, capital spending, dividends, buybacks and stock issued. A sum is missing when any quarter lacks its part. Otherwise the trailing figures are the last fiscal year's, flagged `trailing-on-fiscal-year`.

The diluted share count is the newest quarter's weighted average diluted shares, else the newest fiscal year's. One share count serves every year of every route.

### 4.3 The tax rate

NOPAT uses the statutory marginal rate: the OECD combined central and sub-central corporate rate for the company's country and the fiscal year. The country is the headquarters country of the FMP profile, else the universe row's. A fiscal year later than the newest year in the table takes the newest year's rate as an estimate under method `tax-rate-latest-oecd-year-v1`, flagged `tax-carried-forward`. An earlier missing year, or a country the table lacks, has no rate: the first fiscal year of the eleven-year span with an operating income and no rate refuses the company, "no statutory tax rate for <country> <year>". For a foreign filer, assembly withholds that refusal, so the route gives the foreign-filer refusal instead. The newest fiscal year's rate also converts stock compensation to after tax in the anchor (5.2).

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

The aggregate is shown and feeds the "ten-year" sensitivity (5.8). It never enters the charge.

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

The same rule, applied to a given return, gives the terminal return for each sensitivity value (5.8).

### 4.8 The charge and the value

Earnings in year t are a total, on the one share count. Each year's reinvestment pays for the next year's growth:

    cash_t = earnings_t × max(0, 1 − g_{t+1} ÷ return_t)

with return_t the runway return for t < N and the terminal return for t = N, and g_{N+1} = g_T. A year whose next growth is above its return pays out nothing, never less; the first such year raises `growth-above-return`. When the charge is off, cash_t = earnings_t for t < N.

    terminal multiple = (1 + g_T) × (1 − g_T ÷ terminal return) ÷ (r − g_T)
    value = Σ_{t=1..N} cash_t ÷ (1 + r)^t + earnings_N × terminal multiple ÷ (1 + r)^N

The value a share is the total ÷ the diluted share count.

### 4.9 The moat class

From the GuruFocus Moat Score: 8 or more Wide, 4 or more Narrow, below 4 or no score None. The moat enters in three places: the runway N, the terminal return and the margin of safety.

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

Before any route, in this order: no universe deciles yet; the assembly's refusal ("no financial statements", or the missing tax rate of 4.3); a foreign filer (an ADR by the profile, or a reporting currency other than USD, an unknown currency included); an unclassified company (3.8); Start-up; a phase whose route is not built; no positive price; no positive diluted share count; no trailing figures.

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
| Young Growth, High Growth, Decline | "<phase> route not built yet" |
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
| `sbc-basis-unknown` | the stock-compensation basis test lacked an input |
| `path-on-eps` | years 2 and 3 grow at the consensus EPS steps |
| `few-analysts` | a path year with fewer than 5 analysts or no count |
| `roic-unavailable` | fewer than 5 ROIC years |
| `roic-on-n-years` | 5 to 9 ROIC years |
| `ten-year-roic-unavailable` | the ten-year capital sum is at or below zero |
| `line-not-presented:<field>` | an optional balance-sheet line counted as nil in a ROIC year |
| `charge-zeroed` | the runway charge is off, 4.6 rule 4 |
| `return-floored` | the chosen return measure was below r |
| `growth-above-return` | a year's next growth exceeds its return; its payout is floored at zero |
| `margin-flag` | the trailing operating margin is 1.5 × its ten-year median or more (a positive median), or above its ten-year high by 10% of the high's size or more; needs 6 fiscal years with a margin. The word is "Newly profitable" when the median is at or below zero, "Possible cycle peak" when the window holds a loss year, else "Margin above history" |
| `equity-raise` | trailing stock issued is 1% of market cap or more |
| `negative-fcf` | trailing operating cash flow plus capital spending is below zero |
| `heavy-capex` | trailing capital spending is above 50% of a positive operating cash flow |
| `large-nri` | the non-recurring gap is 5% of trailing EPS or more, in either direction |
| `long-runway-high-growth` | a 20-year runway with a belief or an implied growth of 10% or more |
| `value-spread` | the value spans 30% or more across the first three return keys or across the three runways |

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
| no trailing revenue; no statutory tax rate | 5.1 |
| incomplete NTM consensus; no positive forward anchor; forward P/E below 2: unit error | 5.2 |
| consensus earnings turn negative within the path | 5.3 |
| value not positive under the reinvestment charge | 5.6 |
| no positive trailing earnings | 6.1 |
| data fetch failed: <the failed required endpoints> | the refresh, when an annual statement or the quote fails (section 2) |
| data fetch failed: <error class>: <message>; data fetch incomplete: rate limited; valuation failed: <error class>: <message> | the refresh, when a company's fetch raises, is cut by an HTTP 429, or its valuation raises |

## 10. Refresh kinds and what moves

- **Full refresh**: the universe, the data of section 2 for every admitted company, the deciles, then every company classified and valued, one snapshot per company. A company fetched within 24 hours is not fetched again.
- **Price refresh**: fresh quotes for the latest universe's admitted companies (before any universe, every company with a snapshot), then each latest snapshot repriced from its intermediates alone: the value, the levels and the validity window stay; the stance, the implied growth and its sensitivities, the Mature Stable cross-check's implied growth, the multiples, the growth share, the expected return and the long-runway flag are recomputed; the price input becomes the new quote. A refusal snapshot takes only the new price and date. The price columns (section 2, daily closes) do not move. A snapshot valued under another policy version is not repriced, "policy changed: run a full refresh"; under another method version, "method changed: run a revalue".
- **Revalue**: the engine on the stored facts of every company, with the latest stored deciles, no vendor call and no freshness window. New snapshots under the current method and policy versions.

Snapshots are appended, never changed. The screen reads the latest snapshot per company.

## 11. Versions

| Method | Date | What changed |
|---|---|---|
| 0.1 | 2026-10-31 | The mechanical screen as first built: the charge at the ten-year aggregate ROIC in the runway years, the terminal from the aggregate, a one-step drop from year 3 to the belief, no payout floor; Mature Stable on the one-stage formula at the terminal return. Policy v1. |
| 0.2 | 2026-11-01 | The calibration: the runway return (4.6), the payout floor (4.8), the fade (5.5), the terminal from the runway return (4.7), the four return keys (5.8), the growth-route cross-check (6.4), the revalue kind. Policy v2 adds four values (the marginal span, the capital-growth test, the fallback window, the fade years) and the recorded decision to keep return on invested capital over return on equity. |
| 0.3 | 2026-11-02 | Mature Stable charges as Mature Growth does (6.3): the runway return through the runway, the terminal return after. Policy unchanged. |

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
| The NTM anchor, the SBC basis test, the margin flag, the gate tests, the moat table | stocks mech/1.2 |
| The levels, the stance, the expected return, EPV, the P/E bases | stocks method v1.7 Steps 3, 7, 9, 10 |
| Mature Stable: the stable-growth value with the charge; a stable firm must behave like one | Damodaran H38; design.md 6.11; calibration spec 5.10 |
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
