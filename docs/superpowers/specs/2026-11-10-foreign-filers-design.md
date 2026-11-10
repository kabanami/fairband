# Foreign filers: the reporting currency, the listed-share basis and the half-year reporters: design

Status: written 2026-11-10 from the brainstorm of that day. The founder read the findings on the
live data, chose to value in the reporting currency with the policy's rates restated by the
inflation differential, set the inflation bound at 10%, took the half-year window as a second plan
of this spec and the pairs' quotes in a price refresh, and said "go". The decisions in the log at
the end are the founder's. Items marked *my call* were settled by Claude while writing and can be
overturned. Builder check: done 2026-11-10; its four questions are settled in the last rows of
the log and written into sections 3, 5, 6.1, 7 and 7.3.

This document amends `docs/method.md` (the method as built) in sections 2, 4.1, 4.1a, 4.2, 4.3,
4.10, 5.1, 5.2, 5.12, 5a.1, 6.1, 6a.1, 6b.1, 7, 8, 9, 10, 11, 12, 13, 14.2, 14.3, 15.3, 15.4, 16.3
and 16.6, and the Methodology page with them. The mechanical screen spec (its section 11 in
particular, which this document replaces), the Tier 2 spec and the 2026-11-09 engine round spec
stand for everything it does not mention. When the pieces are built, their sections go into
`docs/method.md` in the same commits, and that document stays the statement of what runs.

## 1. What this is

One piece under method `fairband-mechanical/1.1` and policy `fairband-policy-v11`, built as two
plans. Plan 1 values the 192 rows the screen refuses today as foreign filers (refresh 15, the
latest full one): the 48 that report in USD and were refused for the ADR flag alone, and the 144
that report in another currency. Plan 2 values the 26 among them that report twice a year.

1. **The listed-share basis.** FMP already states an ADR's share count, its EPS and its consensus
   per American depositary share (ADS), the unit the quote prices. The ADR ratio is not applied;
   it is read for the row's words and, on an ADR whose ratio is not one, for the statement periods
   where FMP's count is off by the ratio or its inverse, each judged on its own as the split rule
   judges a period, and scaled to the quote's basis with a note. A newest period that fits no
   basis is a refusal; every other row reads its counts as today.
2. **The reporting currency.** The engine values in the currency the statements are in. The
   price, the market cap, the street actuals and GuruFocus's EPS come into that currency at FMP's
   exchange rate; the value and the levels go back to USD per ADS, which the screen shows. Growth
   ratios stay currency-free, as the mechanical screen spec wanted.
3. **The rates in the currency.** The required return, the terminal growth and the inflation
   addition are nominal USD rates. Each is restated into the reporting currency by the inflation
   differential, Damodaran's rule for valuing in another currency, from a packaged table of the
   IMF's inflation projections. A currency whose expected inflation is above the bound is refused.
4. **The half-year window** (plan 2). A company whose statement periods are half-years takes its
   trailing figures from the last two and its NTM consensus from the next two, in place of the
   four quarters.

The method version steps to 1.1: 192 rows gain a route, the engine gains an input class, and every
other row keeps its figures bit for bit (*my call*: a change that values rows it refused before is
a method change, as the growth routes were).

## 2. Goals

- The 192 rows get a route: the mature routes, the revenue-growth route, the run-off and the
  Start-up requirement as their phases say, on the same rules as a domestic filer, with every
  figure the drawer and Appendix A show in its own currency and named so.
- The screen compares like with like: the value, the levels and the price in USD per ADS, the
  price-to-value and the designation from them.
- An agent reading a foreign filer knows the currency of every figure, the rate, the differential
  and the share basis from the row itself, and the override ranges fit the currency.
- A row the data cannot place on one basis, or whose currency the method cannot price, says why
  in one refusal sentence, as every refusal does.
- Every domestic row keeps its figures bit for bit under 1.1.

## 3. Non-goals

- Converting the eleven years of statements to USD at dated rates. That puts currency swings
  into the growth ratios the classifier ranks. The founder chose the reporting currency.
- A currency-specific required return beyond the inflation differential (a country risk premium,
  a local risk-free rate). The policy's required return is the owner's hurdle; the differential
  keeps it the same real return in every currency. Country risk stays the agent's judgment.
- Forward exchange rates year by year. The value in the reporting currency is translated at the
  spot rate of the price date; under purchasing-power parity, which the differential assumes, that
  is the same figure.
- Hyperinflation accounting (IAS 29). A currency above the inflation bound is refused, not
  restated.
- GuruFocus's annual consensus, the stocks repo's annual route (I388). FMP's consensus rows carry
  the reporting currency per ADS for every company checked, so the window reads them; a company
  whose consensus is in another unit is caught by the implied-count test of the split rule and by
  the forward P/E unit check, as today.
- The companies table's currency column. The screener never carries one; the statements' currency
  is the reporting currency, as today.
- A fiscal-year series that changes currency across the years (21 rows on file, 12 of them valued
  today: CRH, SW, TFII, WFG and other companies that moved to USD reporting). It is read as today:
  the newest year's currency is the reporting currency, the growth ratios are computed from the
  reported figures and the row carries `currency-change` (3.6). Translating the older years at
  dated rates is the conversion the founder declined; refusing would refuse the twelve. The
  ten-year ROIC aggregate mixes the years on such a row; the flag is the agent's signal.

## 4. Anti-goals

- A figure in one currency compared with a figure in another. Every comparison the engine makes
  happens in the reporting currency, and the translation happens once, on the way out.
- A silent basis fix. A count scaled to the quote's basis is an estimate with a note, as a split
  scaling is; the row never scales what the data does not show.
- A stale rate read as today's without a word. A rate older than the stale bound carries a note;
  no rate at all is a refusal.
- A domestic row that moves. Every rule below is conditioned on the currency or the basis; a USD
  row with a count that agrees with its quote reads exactly as under 1.0.

## 5. The evidence (the live database, read-only, 2026-11-10; refresh 15)

The 192 rows refused "foreign filer": 142 ADRs by the profile and 50 direct listings; by phase
Mature Growth 95, Mature Stable 64, Decline 14, High Growth 11, Start-up 6, Young Growth 1, one
unclassified. The statements' currency: USD 48, CAD 28, EUR 27, CNY 25, BRL 12, GBP 9, MXN 7, KRW
6, ZAR 5, JPY 5, TWD 4, ARS 3, INR 3, and one each of VND, TRY, PHP, SEK, COP, CLP, DKK, KZT, CHF,
IDR (23 currencies). The tax table (`tax-rates-oecd-v2.toml`) covers every country of the 192.

What each vendor field carries, checked on the stored payloads:

| Field | Unit on file | Evidence |
|---|---|---|
| FMP statements: totals | the reporting currency (`reportedCurrency`) | TSM FY2025 revenue TWD 3,809,054,300,000; TM FY2026 (March) JPY 50,684,952,000,000 |
| FMP statements: `weightedAverageShsOutDil`, `epsDiluted` | the listed-share (ADS) count and the reporting currency per ADS | TSM 5,186,111,400 shares (its 25.9 bn ordinary shares ÷ the ratio 5), EPS TWD 331.25 (net income ÷ that count: 327); TM 1,303,327,400 (÷ 10), EPS JPY 3,130. On the newest quarterly count, 184 of 192 lie within 15% of the quote's count (market cap ÷ price); 6 are off by the ADR ratio or its inverse (CX ÷10, SIMO ÷4, XPEV ÷2, DRD ÷10, JBS ÷2; TAL ×3, the ratio 1/3); 2 are unclear (WSE 0.78, GRFS 0.80, both dual-class) |
| FMP consensus, annual and quarterly: `epsAvg`, `netIncomeAvg`, `revenueAvg` | the reporting currency, per ADS | TSM FY2029 EPS TWD 949.56 on net income TWD 4,924,545,723,601: the implied count 5,186,111,401, the ADS count; TM FY2031 JPY 4,781.62 on 6,232,012,170,455: 1,303,327,401; UL FY2030 EUR 3.96 on 8,691,412,233: 2,195,300,001 |
| FMP `earnings` (street actuals): `epsActual` | USD per ADS | TSM Q3 2026 4.60 against the statement's TWD 147.15, the quarter's rate; SAP Q3 2026 2.18; TM Q2 FY2027 4.12 |
| FMP quote: `price`, `marketCap` | USD per ADS; USD | TSM 388.62 and 2,015,569,857,600: 5,186,480,000 ADS |
| FMP profile: `currency`, `isAdr` | the listing's currency, always USD here; the flag | TSM USD, true; SHOP USD, false (a Canadian direct listing reporting in USD) |
| FMP closes | USD per ADS | the price history as today |
| GuruFocus `keyratios`: EPS (TTM), EPS without NRI | USD per ADS | TSM 15.54 and 15.54; TM 22.68; ASML 40.60 |
| GuruFocus `summary`: `depositary_receipt_ratio` | ordinary shares per ADS; 0 for a direct listing | TSM 5, TM 10, SHEL 2, BABA 8, AMX 20, KT 0.5, TAL 0.3333; SHOP 0 |
| FMP forex: `historical-price-eod/light?symbol=USD<code>&from=` | daily rows `{symbol, date, price, volume}`, newest first, the price in units of the currency per USD | USDTWD 876 rows for three years, 32.956 on 2026-11-10; USDJPY 158.58; EURUSD and USDEUR both listed. `forex-list` lists both directions for all 23 currencies and every other one checked (HKD, SGD, AUD, NOK, ILS, AED). `quote?symbol=USDTWD` and `batch-quote?symbols=USDTWD,EURUSD,USDJPY` answer the pairs' quotes |
| IMF World Economic Outlook (October 2026, the datamapper's `last-modified` 2026-10-08), `PCPIPCH` (inflation, average consumer prices, percent change), the datamapper API `https://www.imf.org/external/datamapper/api/v1/PCPIPCH` | one series per country, ISO 3166-1 alpha-3, actuals and projections to 2031; `EURO` is the euro area, `TWN` Taiwan; the `indicators` endpoint names the vintage | USA 2027 to 2031: 2.8, 2.1, 1.9, 1.9, 1.9; TWN 1.8, 1.6, 1.5, 1.6, 1.5; ARG 21.2, 14.8, 9.6, 7.5, 7.5; TUR 26.5, 20.6, 17.1, 15.0, 13.2 |

The share basis, period by period (the builder check, 2026-11-10): FMP's basis errors sit on
some periods and not others. UMC's newest quarter (2026-09-30) holds 496.9 m shares, a fifth of
the quote's 2,494.4 m (the ratio 5), while its quarter before holds 2,508.3 m, the quote's basis;
XPEV's and JBS's last four quarters are all half the quote's (the ratio 2); KOF's newest quarter
holds 1,680.7 m against the quote's 210.1 m, eight times, which neither its ratio 10 nor the
inverse explains, while its quarter before holds 210.1 m. About 53 domestic rows valued today
have a diluted count outside 15% of the quote's (Up-C structures, dual classes, buybacks: TSN,
PINS, ETSY, QSR, CVNA among them), which the split rule reads as stored; a basis rule on every row
would refuse them.

The currencies, period by period: 21 rows have a fiscal-year series in two currencies, 9 of them
among the 192 (ARGX, DEO, FMX, GMAB, YPF, RTO, ENIC, TLX, AERO) and 12 valued today (section 3);
5 rows have a trailing quarter in another currency than their newest annual statement (RTO and
TLX one of GBP or AUD before three in USD; TGB and ALM three in CAD before one in USD; BVC, valued
today, one in CNY before three in USD).

The reporting cadence: 166 of the 192 have quarterly statement rows (the two newest 89 to 92 days
apart) and 26 half-years (178 to 182 days): SSL, NGG, ABVX, RELX, SBSW, WPP, DEO, CCEP, MAAS, WDS,
HLN, ZGN, VOD, GFI, TLX, IHG, DRD, BHP, UL, RIO, BTI, SNN, RTO, WSE, PSO, HMY. For these, FMP's
quarterly consensus rows and its street actuals are half-years too (UL: consensus 2027-06-30 and
2027-12-30, actuals 181 days apart; ABVX's actuals are quarterly, MAAS has neither). For them the
trailing figures already fall back to the fiscal year (4.2), and the NTM window (5.2) finds no four
consecutive quarters, so every route but Start-up refuses "incomplete NTM consensus".

The stocks repo's issue log (I290, I388) found FMP's consensus "in the home currency per ordinary
share" and GuruFocus's annual consensus in USD per ADS. On the stored payloads the per-ordinary
reading does not hold: FMP computes its consensus EPS as the net-income mean over the ADS count,
so it is the reporting currency per ADS, which the implied counts above show. The I290 trap
(YPF's consensus in pesos beside a USD street figure) is exactly the mixed-unit case this design
closes by bringing every figure to one currency before any comparison.

## 6. The listed-share basis

### 6.1 The rule

The rule applies to an ADR whose GuruFocus depositary receipt ratio ρ (ordinary shares per ADS)
is known and not one (*my call* after the builder check: a direct listing has no ratio, a ratio
of one explains nothing, and the 53 domestic rows whose count sits off the quote's for reasons of
their own keep reading as today). Every other row reads its counts as the split rule reads them.

It is the split rule's per-period judgment (method 4.2) with two more candidate factors. Each
trailing period (the four quarters, the two half-years of plan 2, or the fiscal year on the
fallback) is judged on its own count against the count on the quote's basis: the newest against
Q, the quote's count (market cap ÷ price), the older ones against S, the newest's count on the
quote's basis; `within(a, b)` reads |a − b| ≤ `split_implied_count_tolerance` (15%) × b. A
period's count c fits a basis when c × ρ_split × f lies within the count it is judged against, for
the period's split ratio ρ_split (1 without a pending split after its end) and a factor f in {1,
ρ, 1 ÷ ρ}; the factor that fits is the one applied, with the split ratio as today. The newest
period decides the diluted count D the engine reads and S. Then:

- a period whose count fits with f = 1 reads as today (its split scaling or none);
- a period whose count fits only with f = ρ or 1 ÷ ρ reads its count × f and its EPS ÷ f, on top
  of its split scaling, the period's street actual untouched (the street side is on the quote's
  basis, section 5);
- a period whose count fits two factors, or none, reads as stored and is named with its reason, as
  the split rule names a period;
- the newest period fitting none, or two, is the refusal "share basis unclear: the newest
  period's count <c> against the quote's <Q> (the ADR ratio <ρ>)", the counts in millions to one
  decimal; without Q there is no judgment and every period reads as stored.

The consensus side, GuruFocus's EPS and the closes are on the quote's basis by the evidence of
section 5 and take no factor; the consensus rows keep the split rule's implied-count test, which
names a row that fits neither count. The count and the trailing EPS so scaled are estimates under
the method `basis-scaled`, keyed as the split rule keys them (`shares_diluted`, `eps_ttm`; the
trailing EPS's note says "on 3 of 4 quarters" when not every period scaled), each with a note:
"×10 to the quote's share basis: the stored count, 145.8 m, is a tenth of the quote's, 1,450.8 m
(the ADR ratio 10)" and "÷10 ..." on the per-share figure; a factor 1 ÷ ρ prints "×3" with "three
ADSs to one share (the ADR ratio 0.3333)". The row carries the note `basis-scaled` (section 8):
"Share basis scaled", one sentence naming the factor, the periods scaled and the two counts, and,
where a period reads as stored, why. On a row with both a pending split and a basis factor the
`split-pending` sentence stands beside it, each naming its own scaling.

### 6.2 The words

The row's inputs name the basis: a DATA input `adr_ratio` (unit `ratio`, GuruFocus `summary`,
absent for a direct listing) and the currency on every statement figure's unit (section 7.4).
The report's words: "one ADS is five ordinary shares; every per-share figure here is per ADS".

## 7. The reporting currency

The reporting currency is the newest annual income statement's `reportedCurrency` (method 2, as
today), else the universe row's, else unknown. A trailing period (a quarter, or a half-year of
plan 2) whose income statement names another currency is not read: the trailing figures fall back
to the fiscal year, flagged `trailing-on-fiscal-year`, the sentence naming the period and its
currency (*my call* after the builder check: five rows on file, BVC among the valued ones, sum a
quarter in one currency with three in another today; the fallback is the reading the method
already has for a defective set of quarters, and a refusal would be harsher than the defect). A
fiscal year in another currency stays as section 3 says.

### 7.1 The rate

The exchange rate of a currency on a day is FMP's close of the pair `USD<code>`, in units of the
currency per USD (*my call*: one direction for every currency, so a figure in the currency is
always ÷ the rate to USD and × the rate from it). A new dataset, the pair's daily history, is
fetched from `historical-price-eod/light` for `refresh.fx_history_years` (3) back from today, one
call per currency, stored whole as the price history is (no rows; the closes stay in the payload),
under the pair as the response's symbol, and reused within the 24-hour window like any FMP call.
The rate at a date is the last close at or before it. A close more than `fx_stale_days` (7) before
the date puts the note `fx-stale` on the row (section 8), its sentence naming both dates; no close
within the history is the refusal "no exchange rate for <code>". A currency with no usable pair
response at all is the same refusal. USD has the rate 1 on every day and fetches nothing.

A full or scoped refresh fetches the rates in a stage of its own, `rates`, after the fetch stage:
the currencies are read from the newest annual income statement of each company fetched, each
pair fetched once (*my call*: a stage, since a company's currency is known only from its
statements, and one call a currency beats one a company). A scoped refresh fetches its pairs
again whatever the window, as it fetches everything else. A revalue fetches nothing and reads the
rates on file. A price refresh asks `batch-quote` for the pairs of the repriced companies'
currencies in one call per hundred pairs, stores each answer as it stores a quote (endpoint
`fx-quote`, the pair as the symbol), and reprices at the quote's rate; a pair whose quote fails
reprices at the rate the snapshot holds, with the `fx-stale` note when that rate is older than the
bound (*my call*).

### 7.2 What comes into the currency, and what goes out

In the engine, before any route, every USD figure is brought into the reporting currency at the
rate of its own date, and the routes then run as they run for a domestic filer, on one currency:

| Figure | Rate | Why that date |
|---|---|---|
| the price | the price date's | the quote's day |
| the market cap (the quote's, else the profile's or the screener's) | the price date's | the same quote |
| each street actual (one per trailing period) | its period end's | FMP translates each quarter at that quarter's rate (section 5: TSM's 4.60 against TWD 147.15) |
| GuruFocus's EPS (TTM) and EPS without NRI | the mean of the trailing periods' period-end rates | a trailing sum; *my call*, since GuruFocus does not say how it translates |
| the trailing revenue for the sales class (4.1's `base_rates`, the class bounds in USD millions) | the price date's, the figure ÷ the rate | the one place a currency total meets a USD bound |

Everything else the routes read is in the reporting currency already: the statements, the
consensus, the tax rate (by country), the balance sums, the peers' ratios. The peers' market caps
stay USD, since they rank peers against each other and against the company's USD market cap.

On the way out, the value a share and the four levels of 4.10 are ÷ the price date's rate to USD
per ADS; the price input stays the USD quote; the price-to-value and the designation read the two
USD figures. The result's intermediates carry `currency`, `fx_rate`, `fx_date`, `value_in_currency`
(the route's value a share before translation) and `inflation_differential` (7.3), and every other
intermediate in the reporting currency as the route made it. A reprice brings the new USD price
into the currency at the new rate, moves what a price refresh moves (method 10) on the figures in
the currency, and translates the value and the levels at the new rate: the value in the currency
stays, its USD figure moves with the rate (founder, decision 4).

The DATA input `fx_rate` carries the rate (unit `<code> per USD`, provenance FMP `USD<code>`
close of its date). The P/E the engine logs for the multiples history reads the price in the
currency over the EPS in the currency, a currency-free ratio, so the history needs no change.

### 7.3 The rates in the currency

Four policy values are nominal USD rates: `required_return`, `terminal_growth`,
`inflation_addition` and, in each Base Rate Book class of `base_rates`, `sales_p90_5y`, the
90th-percentile five-year sales growth that caps the revenue-growth route's held rate (5a.2) and
sets the evidence rule of 14.3 (`override_primary_evidence_above_p90`) (*my call* after the
builder check: a nominal growth cap in USD would bind a KZT consensus four points too early and a
CHF one a point too late). For a company in another currency each is restated by the inflation
differential d:

    d = (1 + π_currency) ÷ (1 + π_USD) − 1
    rate_currency = (1 + rate) × (1 + d) − 1

π is the expected inflation of the currency from the packaged table `inflation-imf-weo-v1.toml`
(4.1): for each currency, the IMF World Economic Outlook's `PCPIPCH` projections of the currency's
issuing economy for the five years after the current year, 2027 to 2031 at the 2026 retrieval, and
their mean, as a fraction. The table names the economy by the WEO's code (`EURO` for the euro
area, `TWN` for Taiwan), its five figures, the mean, the WEO vintage and the retrieval date; it is
generated by `scripts/build_inflation_table.py` from the datamapper's JSON, saved outside the
repository and never committed, as the tax table is built from the OECD export. It covers every
currency of section 5 and the other currencies FMP lists pairs for among the economies the WEO
projects, about forty (*my call*: so a new currency in the universe needs no release). USD is in
the table and gives π_USD. A currency the table lacks is the refusal "no inflation projection for
<code>". A currency whose π is above `inflation_max` (10%) is the refusal "<code>: expected
inflation <π>% above the 10% bound" (founder, decision 2): ARS (12.1%) and TRY (18.5%) today,
KZT (6.2%) valued.

The restated policy is the one the route reads, version and settings hash unchanged; every
derived rate (the Wide moat's terminal return cap at r + 4 points, 4.7) follows r. The flag
thresholds (`long_runway_growth_flag` at 10%, the margin flags) and the margin bounds are not
restated: a flag threshold is a reader's mark, and a margin has no currency. The RULE input
`inflation_differential` (unit `ratio`) names d with a note giving both π figures and the table's
vintage; a USD row has d = 0 and carries neither the input nor a restated policy.

The override ranges of 14.2 that are in USD or USD a share (`earnings.ntm`, `revenue.ntm`,
`earnings.nri_gap`, `earnings.cycle_gap`, `balance.debt`, `balance.cash`, `value.outside`) are
read in the reporting currency: each bound × the price date's rate, the refusal sentence naming
the currency ("earnings.ntm is above 0 to 32,956 TWD a share"). A guidance record's figures are
in the reporting currency as the company states them.

### 7.4 The words on every figure

An engine input whose unit is `USD` or `USD a share` today carries the reporting currency's code
in its place: `TWD`, `TWD a share`. `reports/refs.py` already maps a currency code to the unit
`currency` and `<code> a share` to `per-share`. The drawer and the report page print a USD figure
with `$` as today and any other with its code before the number (`TWD 12,807.36`), totals to whole
units and per-share figures to two decimals. The `company` read (web and MCP) gains `currency`,
`is_adr` and `adr_ratio`.

The report's number check (16.3) needs no new rule: a figure led by `€`, `£` or `¥` is a money
amount already; a figure after a code (`TWD 331.25`) is a decimal or an integer, a quantity, and
its cite's unit decides. The citations reference says: `$` for a USD figure only; for another
currency the code before the number, or its sign where the sign is one of the four.

### 7.5 The guard order (5.1)

Before any route, in this order: no universe deciles yet; the assembly's refusal ("no financial
statements", or the missing tax rate of 4.3, which now refuses every company); the currency
refusals of 7.1 and 7.3 ("reporting currency unknown" for a row whose statements and universe row
name none, in place of today's `currency-unknown` note leading to the foreign-filer refusal; "no
exchange rate for <code>"; "no inflation projection for <code>"; "<code>: expected inflation
above the bound"); the basis refusal of 6.1, on an ADR with a ratio other than one; an
unclassified company; no positive price; no positive diluted share count. "Foreign filer: currency and share-unit handling not built yet"
goes, and with it the ADR flag as a ground for refusal.

### 7.6 The secondary valuation, the review and the report

The secondary valuation (15) runs in the reporting currency on the restated rates: its totals
(firm value, equity, debt, cash, the projection's lines) in the currency, its value a share and
its levels ÷ the rate to USD per ADS, as the snapshot's; the record carries the rate. Its
foreign-filer refusal (15.4) goes. The report rule of 16.3 that spares a company the secondary
valuation for a refusal the agent cannot fix reads the list: no diluted share count, the currency
refusals of 7.5 and the basis refusal; Appendix A's reason names the refusal. The review's
overrides are in the reporting currency (7.3) and the reviewed value translates as the mechanical
one does. The sensitivity grid's cells are USD a share, as the value is.

## 8. The half-year window (plan 2)

A company's reporting cadence is read from its quarterly statement rows: quarterly when the
newest rows end 80 to 100 days apart, half-yearly when 170 to 195 days apart (*my call* on the
bounds: 178 to 184 on file, with 52/53-week years in reach). Under the half-year cadence:

- the trailing figures (4.2) sum the last two half-year rows when each ends 170 to 195 days after
  the one before, joined to the cash-flow rows by period end; else the fiscal year, flagged as
  today. The trailing periods for the split rule and the share basis are the two;
- the street actuals (4.2, 5.2) are the two at the two period ends; their sum is the street
  trailing EPS;
- the NTM window (5.2) is the two consensus rows ending more than `SAME_PERIOD_DAYS` after the last
  reported period, each 170 to 195 days after the one before; the anchor sums the two; the base
  fiscal year holds most of the two, a tie taking the later, which lands where a quarterly
  reporter's window lands; the SBC adjustment's revenue scale reads the window's revenue over the
  trailing revenue, as today;
- the Decline route's and the revenue-growth route's windows are the same window.

A company whose consensus rows are quarterly while its statements are half-years (ABVX's
actuals) reads the window its consensus cadence gives and the trailing figures its statements
give; the street actuals need rows at the trailing period ends, else the basis test is unknown, as
today. Nothing else changes: the validity window reads the next earnings date as today, the split
rule reads periods of either cadence, the fiscal-year fallback stays for a company with neither
four quarters nor two halves.

## 9. Policy v11

| Value | Name | Setting | Source |
|---|---|---|---|
| Inflation bound: 10% | `inflation_max` | no | founder 2026-11-10: IAS 29 restates statements in constant currency above roughly that; ARS and TRY refused, KZT at 6% valued; no source gives the number |
| Stale-rate bound: 7 days | `fx_stale_days` | no | *my call*; no source gives the number |
| Rate history depth: 3 years | `refresh.fx_history_years` | no | *my call*: the trailing periods' ends and GuruFocus's observation dates lie within 15 months; three years leaves room |
| The inflation table | `inflation-imf-weo-v1.toml` | no | the IMF World Economic Outlook, `PCPIPCH`, the datamapper API; the table's `[meta]` names the vintage and the retrieval date |

Every v10 value is unchanged; v10 stays byte-identical under its hash. No new setting. The basis
factor and the split rule share `split_implied_count_tolerance`.

## 10. The method document, the Methodology page, the drawer, the report page and the playbook

- `docs/method.md`: section 7 rewritten as the foreign filers' rules (6, 7); 2 gains the rates
  dataset and the pairs' quotes, and names each vendor field's unit by section 5's table; 4.1 and
  4.1a the v11 values and the inflation table; 4.2 the basis factor inside the split rule's
  per-period judgment, the trailing period in another currency, and, in plan 2, the half-year
  trailing figures; 3.6's `currency-change` row says the route values the row on the newest
  year's currency; 4.3 loses the withholding for foreign filers; 4.10 the translation of the
  value and the levels; 5.1, 5a.1, 6.1, 6a.1, 6b.1 the guard order of 7.5; 5.2 the half-year
  window; 5.12 and the inputs sections the currency on the units, `fx_rate`, `adr_ratio` and
  `inflation_differential`; 8 the notes `basis-scaled` and `fx-stale`, with `currency-unknown`
  gone; 9 the refusals; 10 what each refresh kind fetches and what a price refresh moves; 11 the
  1.1 row; 12 the IMF and FMP forex sources; 13 the glossary's ADS, reporting currency and
  differential; 14.2 and 14.3 the ranges in the currency; 15.3 and 15.4 the secondary valuation;
  16.3 and 16.6 the report rule and Appendix A's reason. The Methodology page gains a foreign
  filers section in the page's register: the currency, the rate, the differential, the basis, the
  bound, with one example.
- The drawer: the code on every figure; the rate, the differential and the ratio among the
  inputs; the two notes' sentences. The report page the same.
- The playbook (`playbook/fairband-research`): a foreign filer paragraph in step 2 (the currency
  of every figure, the ADS basis, the rate ref `snapshot:<id>/inputs/fx_rate` for any arithmetic
  across USD and the currency through `derive`, the override ranges in the currency, the guidance
  figures in the currency); `basis-scaled` and `fx-stale` join the flags the agent reads;
  `reference/citations.md`'s format rows name the currency; `reference/tools.md` the new fields
  and the secondary valuation's currency; the secondary valuation's refusal list loses the
  foreign-filer line.

## 11. Worked numbers for the tests

### 11.1 The rates

Policy: r 9%, g_T 3%, the inflation addition 2%. A test table with USD at 2.00% and the currency
at 4.04%: d = 1.0404 ÷ 1.02 − 1 = 2.000%; r_currency = 1.09 × 1.02 − 1 = 11.180%; g_T 1.03 × 1.02 −
1 = 5.060%; the addition 1.02 × 1.02 − 1 = 4.040%. On the packaged table (the IMF's 2027 to 2031
means): USD 2.120%; TWD 1.600%, d −0.509%, r 8.445%, g_T 2.476%; JPY 2.120%, d 0; BRL 3.240%, d
+1.097%, r 10.195%; CHF 0.740%, d −1.351%, r 7.527%; KZT 6.240%, d +4.034%, r 13.398%; ARS 12.120%
and TRY 18.480%, refused. The pinned figures are to three decimals of a percent.

### 11.2 The translation

A company in a currency at 8.0 per USD on the price date, quoting USD 50.00 with a market cap of
USD 5,000 m: the route reads a price of 400.00 and a market cap of 40,000 m in the currency; a
route value of 480.00 a share is USD 60.00, the buy level at a 25% margin of safety USD 45.00, the
price-to-value 0.8333. Trailing periods ending at rates 7.8, 7.9, 8.1 and 8.2: street actuals of
USD 0.60, 0.62, 0.64 and 0.66 read 4.680, 4.898, 5.184 and 5.412, the street trailing EPS 20.174;
GuruFocus's EPS (TTM) of USD 2.50 reads 2.50 × 8.0 (the mean) = 20.00. A trailing revenue of
8,000 m in the currency is USD 1,000 m for the sales class. A reprice to USD 55.00 at 8.5: the
price in the currency 467.50, the value 480.00 ÷ 8.5 = USD 56.47, the price-to-value 0.9740. A
close of 2026-11-01 read for a price date of 2026-11-10 is `fx-stale` (9 days); one of 2026-11-05
is not.

### 11.3 The basis

CX: every trailing quarter holds 145.8 m, Q is 1,450.8 m, ρ 10: 145.8 × 10 = 1,458.0 m lies within
15% of Q and 145.8 m does not, so every period reads × 10 on the count and ÷ 10 on the EPS, D
1,458.0 m, S the same, the trailing EPS ÷ 10 with no "of" clause. UMC: the newest quarter 496.9 m
against Q 2,494.4 m, ρ 5: × 5 = 2,484.5 m fits, so the newest reads × 5, D = S = 2,484.5 m; the
three older quarters hold 2,508.3 m, which fits S with f = 1, so they read as today; the trailing
EPS's note says "on 1 of 4 quarters". TAL: 184.0 m against Q 608.5 m, ρ 0.3333: ÷ ρ = 552.1 m fits
(9.3% off) and 184.0 m does not, f = 3.0003, the note "×3". KOF: the newest 1,680.7 m against Q
210.1 m, ρ 10: 1,680.7, 16,807 and 168.1 m fit nothing, so the row is refused "share basis
unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the ADR ratio 10)".
GRFS: ρ 1, so the rule does not apply; its 680.6 m against 846.0 m reads as the split rule reads it,
as stored, valued. WSE: no ρ, the same. A domestic row with D off Q by 30%: as stored, no note, no
estimate, bit for bit. A period whose count fits both f = 1 and f = ρ cannot happen under a 15%
tolerance with ρ ≥ 2 or ≤ 0.5; the builder pins the "two factors" branch on a synthetic ρ of 1.2.

### 11.4 The half-year window (plan 2)

Statement rows ending 2025-06-30, 2025-12-31 and 2026-06-30 (184 and 181 days): the cadence is
half-yearly, the trailing figures the sum of the last two. Consensus rows ending 2026-12-31 and
2027-06-30: the window; the base fiscal year 2027 (one each, the later). A company with rows 91
days apart keeps today's reading bit for bit.

## 12. Tests the builder must write

- `policy`: v11 loads, the three values, v10 byte-identical under its hash; the inflation table
  loads, every currency of section 5 present with five figures and the mean, USD among them; the
  build script round-trips a saved datamapper JSON into the packaged table.
- The rates: the normalizer reads the light history's rows; `rates_for` gives the close at or
  before a date, the stale note past the bound, none past the history; the `rates` stage fetches
  one pair a currency, reuses within the window, forces on a scoped refresh; the price refresh's
  pairs' quotes, the fallback to the stored rate; a vendor failure on a pair leaving the company
  refused "no exchange rate" and every other company valued.
- The engine: 11.1's rates on the restated policy, the version and hash unchanged, the terminal
  cap following r; 11.2's translation on every route (a Mature Growth, a Mature Stable, a
  revenue-growth, a Decline and a Start-up row in a currency), the levels, the designation, the
  intermediates' keys, the reprice at a new rate; the override ranges × the rate; the sensitivity
  grid in USD; the review's bridge in USD.
- The basis: 11.3's cases, UMC's per-period reading among them; the scaled figures' notes and
  methods; a row with a pending split and a factor; a ratio of one or none leaving the row as
  today; the 53 domestic rows' shape (a count off the quote's with no ratio) bit for bit.
- The currency of the periods: a trailing quarter in another currency sending the figures to the
  fiscal year with the sentence; a fiscal-year series in two currencies valued on the newest
  year's currency with `currency-change`.
- The restated cap: `sales_p90_5y` on the held rate and on the evidence rule in a currency with
  a differential.
- The guards: each refusal sentence of 7.5 in order; a USD ADR valued with no rate input; the
  `currency-unknown` note gone and the refusal in its place.
- The secondary valuation on a foreign filer: totals in the currency, the value a share in USD,
  the record's rate; the report rule's cannot-fix list.
- The goldens (`tests/fixtures/golden`): every existing golden unchanged bit for bit under 1.1,
  which the test asserts; a new golden for a foreign filer in a currency.
- `web`, `reports` and the playbook tests: the units' words, the company read's fields, the
  Methodology page's section, the citations reference's rows.
- Plan 2: 11.4; the trailing figures, the street actuals, the window and the base year under the
  half-year cadence; a quarterly company bit for bit; the Decline and revenue-growth windows.

## 13. Acceptance and the readout

After plan 1's merge, a backup of the live database, the server restarted from main, and one full
refresh (the first with the rates). The readout, on the shape of the earlier ones:

- The 192: the counts valued by route and refused by reason; the rows flagged `basis-scaled`
  (expected CX, SIMO, XPEV, DRD, JBS, TAL, UMC) and refused for the basis (expected KOF); GRFS
  and WSE valued as stored; ARS and TRY refused by the bound; the five rows on the fiscal-year
  fallback for a period's currency (RTO, TLX, TGB, ALM; BVC among the domestic rows); the 26
  half-year reporters refused "incomplete NTM consensus" until plan 2.
- Six companies named: TSM, ASML, SAP, NVO, TM, SHEL, each with its rate, its differential, its
  value in the currency and in USD, its price-to-value and its trailing P/E as a sanity check
  against the vendor's.
- Every domestic row: value, levels, designation, flags and refusal bit for bit as the refresh
  before, the version rows apart, except BVC, whose trailing figures move to its fiscal year.
- After plan 2's merge, a scoped refresh of the 26 and the same readout on them.

## 14. Left to the builder

- Where the translation lives: in `route.value_company` around the routes, with the routes
  untouched, is the natural place; the restated policy as a `replace` of the three values.
- The rates module's shape (`refresh/rates.py`) and the `rates` stage's place in `run.py` and the
  progress report; the pair's response symbol; the normalizer's reader for the light history.
- The basis factor's place: assembly, beside the split rule, reusing its period scaling.
- The inflation table's TOML shape and the script's currency-to-economy map; the forty currencies.
- The drawer's and the report page's exact print forms for a non-USD code; the Methodology page's
  sentences; the refs' words for the new intermediates.
- Plan 2's cadence reader and the window function's name, shared by the three routes.

## 15. Order of work

Plan 1:

1. Policy v11, the inflation table and its script, the 1.1 rows of `docs/method.md` (4.1, 4.1a,
   11, 12); the goldens' baseline check.
2. The rates: the adapter route, the dataset, the `rates` stage, the price refresh's pairs;
   method 2, 10.
3. The basis factor (6); method 4.2, 8, 9.
4. The engine: the guards (7.5), the translation (7.2), the restated rates (7.3), the ranges, the
   reprice; method 4.3, 4.10, 5.1, 5a.1, 6.1, 6a.1, 6b.1, 5.12, 7, 8, 9, 13, 14.2, 14.3.
5. The secondary valuation and the report rule (7.6); method 15.3, 15.4, 16.3, 16.6.
6. The words (7.4, 10): the units, the company read, the drawer, the report page, the Methodology
   page, the refs, the playbook.
7. Backup, merge, restart, the full refresh, the readout (13).

Plan 2: the cadence and the half-year window (8); method 4.2, 5.2, 5a.1, 6a.1; the scoped refresh
of the 26 and the readout.

## 16. Sources

| Rule | Source |
|---|---|
| Value in the currency of the cash flows with a discount rate in that currency; translate at the spot rate; the two routes agree under purchasing-power parity | Damodaran, *Investment Valuation* 2e, ch. 7 and the "Dealing with currency" notes: the expected inflation differential restates a rate from one currency to another, (1 + r_local) = (1 + r_USD) × (1 + π_local) ÷ (1 + π_USD) |
| Expected inflation from the IMF's projections | IMF World Economic Outlook database, `PCPIPCH`; the datamapper API |
| Hyperinflation accounting restates statements in constant currency, which breaks a nominal growth reading | IAS 29, *Financial Reporting in Hyperinflationary Economies* (the cumulative three-year inflation near 100% test) |
| FMP's per-ADS basis, its consensus unit, its street actuals in USD, its forex routes | the live check of section 5 |
| GuruFocus's EPS in USD per ADS and the depositary receipt ratio | the live check of section 5; the stocks repo's I388 |
| Growth ratios are currency-free; the anchor is not | the mechanical screen spec, section 8 open questions and section 11; `design.md` 11.4 |
| The half-year reporters need a window of their own | the stocks repo's I388 (`mech/1.1`, the annual route); `design.md` 8 and 11.4 |

## Decision log

| Date | Decision |
|---|---|
| 2026-11-10 | B-28 after plan 2 of the engine round 2 (the founder's order of 2026-11-06). Founder. |
| 2026-11-10 | Decision 1: value in the reporting currency with the three nominal rates restated by the inflation differential, over converting the statements to USD at dated rates. Claude's recommendation; the founder chose it. |
| 2026-11-10 | Decision 2: a bound on expected inflation at 10%, refusing ARS and TRY and valuing KZT. Claude's recommendation; the founder chose it. |
| 2026-11-10 | Decision 3: the half-year window built now, as plan 2 of this spec. Claude's recommendation; the founder chose it. |
| 2026-11-10 | Decision 4: a price refresh fetches the pairs' quotes too, so the price and the USD value sit on the same day's rate. Claude's call; the founder did not object. |
| 2026-11-10 | The ADR ratio is not applied to FMP's figures, which are per ADS on file; it is read for the words and for the basis factor. Claude, from the evidence of section 5. |
| 2026-11-10 | Builder check (Opus 5.5): four questions. (1) The basis rule's scope: an ADR with a ratio other than one; every other row, the 53 domestic rows with a count off the quote's among them, reads as today, so the domestic goldens hold. Claude. (2) The basis judged per trailing period inside the split rule, with the ratio and its inverse as candidate factors beside the period's split ratio; UMC, XPEV, JBS and KOF on file show the errors sit on some periods. Claude. (3) Two currencies: a trailing period in another currency sends the figures to the fiscal-year fallback with the sentence; a fiscal-year series in two currencies is read as today with `currency-change`, since twelve valued domestic rows have one. Claude. (4) `sales_p90_5y` is restated with the three rates; the flag thresholds and margin bounds are not. Claude. |
| 2026-11-11 | Readout of refresh 34, the first full refresh under method 1.1 (plan 1 merged as main 354c809; backup `fairband-before-method-1.1-2026-11-11.db`; migration 007; 18 minutes; 22 pair histories, every call 200; 1,596 companies valued or refused, 2 vendor fetch failures, AGLT and RML). Of the 199 rows refused "foreign filer" before it, 144 are valued (Mature Stable 59, Mature Growth 66, revenue-growth 7, Decline 12) and 45 refused: incomplete NTM consensus 17, Start-up 6, no positive trailing earnings 4, share basis unclear 3 (KOF as expected, 1,680.7 m against the quote's 210.1 m at ratio 10; GDS 259.5 m against 194.9 m at 8; PKX 501.9 m against 309.2 m at 0.25), the inflation bound 4 (TEO, TGS, YPF at ARS 12.1%; TKC at TRY 18.5%), value not positive 4, other refusals 7; 10 are no longer in the universe (financials excluded or dropped). `basis-scaled` on 10: CX, DRD, SIMO, TAL, XPEV as expected, and KT, PAC, TS, VEON, MAAS (an older period scaled; the newest fits as stored); not JBS (no diluted share count on file) nor UMC (its newest count now fits as stored, 2,520 m against 2,494 m). GRFS refused "incomplete NTM consensus"; WSE valued, Mature Growth $13.60. No `fx-stale`, no "reporting currency unknown", no "no exchange rate". 47 USD reporters carry no currency; 22 currencies carried. The 26 half-year reporters are all on the fiscal-year fallback: 11 refused "incomplete NTM consensus" (DEO, CCEP, MAAS, ZGN, GFI, TLX, IHG, DRD, SNN, RTO, HMY), 9 valued Mature Stable on the fiscal year (UL $66.64 against $66.47, RIO $80.82 against $84.54, BHP $54.10 against $81.12, RELX, WPP, WDS, HLN, SSL, PSO), SBSW and BTI Decline, WSE Mature Growth, ABVX Start-up, VOD and NGG refused on earnings; section 5's "every route but Start-up refuses" was wrong for Mature Stable and Decline, which need no NTM window; plan 2 gives the 26 the half-year trailing sum and window. The six: TSM TWD 32.937 per USD, d −0.51%, TWD 14,282 a share → $433.63 against $396.48 (price-to-value 0.91, trailing P/E 26.6); ASML EUR 0.8953, d +0.08%, €2,533 → $2,829 against $1,507.85 (0.53, 38.6); SAP €147.05 → $164.25 against $233.74 (1.42, 29.8); NVO DKK 6.694, d −0.02%, DKK 445 → $66.54 against $40.70 (0.61, 10.7); TM JPY 158.7, d 0, ¥35,733 → $225.16 against $214.78 (0.95, 9.8); SHEL reports in USD, Decline, $76.61 against $97.27 (1.27, 8.4); FMP's stored quote carries no P/E, so the ratios are checked by eye. Domestic rows: 1,409; 522 bit for bit against their latest snapshot; 872 moved with new statements, consensus or price (a full refresh fetches everything again) or with the deciles (SYM, same dates and price: refresh 34's industry medians replaced refresh 15's); none by a rule of 1.1; BVC was already on the fiscal-year fallback and refused "incomplete NTM consensus" since refresh 30, so nothing moved. Refresh 34 values 1,377 of 1,598 rows against refresh 15's 1,176 of 1,602. Claude, read-only on the live store. |
