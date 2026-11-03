# The rate limiter, the classifier fixes, the price-to-value designation, the sticky controls, and the Start-up and Decline routes: design

Status: written 2026-11-03 from the founder's decisions of that day; the founder skipped the
brainstorm's questions ("write the spec from what we settled"). The decisions in the log at the
end are the founder's. Items marked *my call* were settled by Claude while writing and can be
overturned. Builder check: see the status line at the end of the log.

This document amends `docs/method.md` (the method as built) in sections 1, 2, 3, 4.10, 7, 8, 9,
10 and 11, and `docs/legacy/design.md` sections 6.8 and 6.12 where it says so. The mechanical
screen spec, the calibration spec, the screen-controls spec and the growth routes spec stand for
everything it does not mention. When the pieces are built, their sections go into
`docs/method.md` in the same commits, and that document stays the statement of what runs.

## 1. What this is

Five pieces, in the build order the founder agreed on 2026-11-03:

1. **The FMP rate limiter.** A full refresh at 16 workers answers HTTP 429 after about 5,500
   calls and needed five runs on 2026-11-03, each reusing the last run's fetches. The client
   paces its calls to the plan's limit so a full refresh completes in one run.
2. **The classifier fixes.** Insperity (NSP, founded 1986) is Young Growth on a −0.15% operating
   margin in fiscal 2025 after ten profitable years, because rule 4 reads the sign of the last
   margin alone. Of the 163 growth rows, 24 are established companies with a loss year; three of
   the four growth buys are among them. The Decline rule reads revenue only and takes a single
   bad year for decay: EQT, Nike and Expeditors are Decline on one falling year in four. And the
   universe admits insurers and lenders that FMP files under industries the exclusion list does
   not name (Corebridge, an insurer, under "Asset Management").
3. **The price-to-value designation.** The engine stops giving a stance (buy, hold, trim). The
   stance is the agent's call after research; the engine's value is a best effort. In its place
   a mechanical word says where the price stands against the value, in five bands.
4. **The sticky controls and the back-to-top control.** The FIND, filter and columns bar scrolls
   with the table header; a control returns the reader to the top of the table.
5. **The Start-up and Decline routes.** The two phases that still get a refusal (section 7 of the
   method). Start-up rows (45 today) show what the price needs, not a value. Decline rows (253
   today, 118 after the classifier fix) get Damodaran's run-off DCF with a distress weighting.

Policy `fairband-policy-v5.toml` carries every value from the start. The work is two plans
(2026-11-03): the first (the limiter, the classifier, the designation, the controls) lands as
method `fairband-mechanical/0.6`, the second (the two routes) as `fairband-mechanical/0.7`.
A revalue applies each; no vendor call is needed, because every new field the routes read is
already in the stored statements (section 11).

## 2. Goals

- A full refresh of the founder's database in one run, at the plan's rate, with the 429 retry
  as a safety net that is rarely used.
- An established company with a loss year classified by its growth word, not as a young
  company; a Decline phase that needs a string of falling years; the financials the method
  cannot value out of the universe.
- One word per valued row, the same meaning on every row, that describes the price against the
  value and recommends nothing. The moat and the margin of safety stay as the row's levels, as
  figures for the agent.
- Controls that stay in view while the table scrolls, and a way back to the top.
- A Start-up row that says what revenue the price needs by year 10 at the mature peers'
  margin, and how long its cash lasts. A Decline row valued on shrinking cash flows, with the
  distress probability from a synthetic rating, a floor at net current assets and the distress
  signals (Altman Z″, Piotroski F) shown.
- Every mature-route convention that applies carries over unchanged: trailing figures, one
  share count, the statutory tax rate, invested capital, the peers of 5a.4, the levels, the
  flags, the validity window.
- The same inputs under the same policy version give the same result, bit for bit.

## 3. Non-goals

- The settings surface: the worker count, the plan rate, the hurdle rate, the time horizon and
  the other values the founder will parametize come later. This piece adds the values to the
  policy file, where every value lives today.
- The server marking a running CLI refresh interrupted at startup: a separate defect, noted in
  the method as a known gap, not fixed here.
- A GuruFocus limiter: its quota is 40,000 calls a month and its two calls a company are reused
  for seven days; no pacing is needed.
- The agent's stance (tier 2) and where it is stored: the stance column leaves the screen until
  the agent writes one.
- Young Growth's failure probability: the founder's decision of 2026-11-02 stands (reported
  unavailable, flagged). The synthetic rating does not fit a loss-making company (its interest
  coverage is negative), so the distress table of section 10 serves Decline only.
- A Start-up value: Damodaran values pre-revenue companies on a market build, which is the
  agent's; tier 1 shows the requirement and no value, as `design.md` 6.8 decided.
- Decline's orderly-liquidation value by asset class, the reversibility of the decline and
  management's response: the agent's (`design.md` 6.12).
- The peer-figure cost (about 28 seconds a value stage) and the parked minors of the growth
  routes.

## 4. Anti-goals

- A designation that embeds a judgment: no moat, no margin of safety, no colour that says "act".
- A distress-sale value above the going-concern value: the distress weighting must never raise
  a value.
- A classifier that reads age, a founding date or a listing date: the phases stay Damodaran's,
  marked by the numbers' direction, never by thresholds on age.
- A value for a Start-up row, or a stance anywhere, from the engine.
- A second source of truth for the levels: `buy`, `fair_low`, `fair_high` and `trim` keep their
  names and arithmetic; only the word that reads the price against them changes.

## 5. The FMP rate limiter

### 5.1 What exists

`VendorHttp.get` (`src/fairband/vendors/http.py`) is the one place every FMP and GuruFocus call
goes through; `clients.py` builds one `VendorHttp` per vendor. A call retries up to `attempts`
(3) on a transport error or on 408, 429, 500, 502, 503 or 504, sleeping `backoff_s` (2 s, then
4 s) or a numeric `Retry-After` when smaller, within `deadline_s` (30 s) from the call's start.
`fetch_company` stores a 429 as a failed response, sets `rate_limited` and skips the company's
remaining endpoints; the run starts no new company, values the ones fetched on the stored
deciles, saves no deciles and ends failed, "rate limited by FMP: stopped after N companies".
Sixteen worker threads each fetch one company at a time, 13 FMP calls and 2 GuruFocus calls per
company not reused. The policy's comment ("12 FMP calls per company") and the module docstrings
("fourteen calls") are stale; the code makes 13 and 2.

### 5.2 The limiter

A pacer, one per vendor, shared by every thread that uses that vendor's client:

- `RateLimiter(calls_per_minute, clock, sleep)`. The interval is 60 ÷ `calls_per_minute`
  seconds. `acquire()` takes the next slot: under a lock, slot = max(now, next slot), the next
  slot moves to slot + interval; outside the lock the thread sleeps until its slot. A
  `calls_per_minute` of 0 is no pacing: `acquire()` returns at once.
- `hold(seconds)`: under the lock, the next slot moves to max(next slot, now + seconds). Every
  thread's next `acquire()` waits for it.
- `VendorHttp.get` calls `acquire()` before every try, retries included. When a try answers 429,
  it calls `hold` with the numeric `Retry-After` capped at `rate_limit_hold_s` when the answer
  carries one, else `rate_limit_hold_s`, and the retry's sleep is that hold instead of the
  backoff. A GuruFocus 429 sleeps that hold before its retry and holds no other worker: its
  limiter does not pace. A try that answers 429 after the last attempt raises as today.
- The time a call spends waiting in the limiter does not count against its `deadline_s`: the
  deadline clock runs from the first try's start, and each wait in `acquire()` or a hold
  extends it by the time waited.
- The FMP client's limiter reads `refresh.fmp_calls_per_minute`; the GuruFocus client gets a
  limiter at 0 (none). Tests pass a fake clock and a recording sleep, as `tests/vendors/test_http.py`
  does with its `Script` helper.

The pace is even, not bursty: at most one call per interval, so in any 60 seconds at most
`calls_per_minute` calls start, plus the one whose slot was the window's first instant. The plan
counts per minute; an even pace stays under any window shape FMP uses.

*My call:* `fmp_calls_per_minute` = 2,850, the Ultimate plan's 3,000 a minute less a 5% margin
for clock drift between the client and the vendor's counter; `rate_limit_hold_s` = 60, one
plan window. With 16 workers at 2,850 a minute, each call waits at most about a third of a
second; the fetch stage of a full refresh (about 23,000 calls for 1,735 companies, none reused)
takes at least eight minutes, which the plan sets, not the code.

### 5.3 What stays

The retry counts, the backoff for the other retryable statuses, the 429 path through
`fetch_company` and the run (section 9 and 10 of the method) all stay as the safety net: a run
still ends failed when a call answers 429 three times. The worker count stays 16. Price and
scoped refreshes use the same client and so the same pacer. The method's section 2 gains one
sentence: "FMP calls are paced to `fmp_calls_per_minute`, one pace shared by every worker; a 429
holds every FMP worker for the vendor's numeric `Retry-After` capped at `rate_limit_hold_s`,
else `rate_limit_hold_s`, and the call retries after the hold. A GuruFocus 429 sleeps the same
hold before its retry and holds no other worker." The policy comment on the worker count is
corrected to 13 FMP calls, and the module docstrings with it.

## 6. The classifier

### 6.1 What the probes showed (2026-11-03, refresh 11, 1,735 eligible rows)

| Phase | Rows |
|---|---|
| Mature Growth | 853 |
| Mature Stable | 400 |
| Decline | 253 |
| High Growth | 106 |
| Young Growth | 57 |
| Start-up | 45 |
| Unclassified (under two fiscal years) | 21 |

Of the 163 growth rows, 24 had a positive operating margin in at least three of the last five
fiscal years (19 in at least four). They are NSP, CNC, CRBG, APD, TAP, HRB, IP, HMC, IVZ, BAX,
AXON, CSGP, EQH, FLR, HASI, NEOG, RXO, SUPN, TALO, TBBB, AIN, CNR, COTY and DNOW. The other
139 growth rows are pre-profit; 120 of them have a "Very High" or "High" growth word, and the 19
with a lower word (SNAP, Zillow, Take-Two among them) are loss-makers the revenue DCF values as
it should: the `growth-word-disagrees` counts I reported earlier (90 of 106 High Growth rows)
mostly mark "Very High" against "High", one growth phase against the other, not growth against
maturity. So the growth phases keep their rule, and the fix is the established company.

Of the 253 Decline rows, the revenue fell in all four of the last four year-over-year steps for
22, in three for 94, in two for 110, in one for 26, in none for 1. The one-fall rows include
EQT, NKE, EXPD and GTES, the two-fall rows AGCO, BALL, ARW and BN: cyclicals in a down year or
companies after a divestiture, not decay. The three- and four-fall rows are AAP, ADM, BBY, BIIB,
KSS, DXC, GME, INTC, LUMN, KMX and their like.

The universe admits 122 rows of FMP's Financial Services sector: Asset Management 50, Capital
Markets 29, Credit Services 24, Data & Stock Exchanges 10, Banking & Investment Services 5,
Mortgages 3, Conglomerates 1.

### 6.2 Rule 4: the established company with a loss year

The margin that decides the phase stays the last of the last five fiscal years that has one
(3.4). A company is **established** when at least three of the last five fiscal years on file
have an operating margin above zero (a year without a margin counts for nothing). The window is
the method's five-year trend window; three of five is a majority of it, a structural constant in
code like the margin-direction deciles (4.1a).

Rule 4 becomes:

4. A negative margin:
   a. of an established company: the phase is rule 5's, by the growth word, as if the margin
      were positive; the company is flagged `loss-year`;
   b. otherwise **High Growth** when the margin trend is above zero, else **Young Growth** (a
      missing trend or a slope of exactly zero counts as not improving), as today.

Rule 2 (Decline) still comes first, so an established company with a loss year and a string of
falling revenue is Decline. NSP goes to Mature Growth ("Moderate" growth), CRBG and CNC to
Mature Growth ("High"), APD and EQH to Mature Stable. Their routes then value them or refuse
them honestly: the Mature Growth route needs a positive forward anchor and the Mature Stable
route positive trailing earnings; a loss company whose consensus stays negative is refused "no
positive forward anchor", which is the truth about it.

The flag: code `loss-year`, word "Loss year", sentence "The operating margin is negative in
fiscal {year} after a positive margin in {n} of the last five fiscal years; the phase follows
the growth word." It is a classifier check (3.6), listed with them, raised on rule 4a only. The
`growth-word-disagrees` check keeps its rule and now fires on rule 4b only, since under 4a the
growth word decides.

This is the founder's complaint of 2026-11-03 ("why is NSP considered young growth? its a
company that was founded in 1986") answered without reading age: Damodaran marks the phases by
the direction of the numbers, and a margin history is a direction.

### 6.3 Rule 2: the Decline duration test

Damodaran's test for decay is duration: "one or two years" of falling revenue "can be explained
away as extraordinary", while "a string that lasts five or ten years is indicative of decay in
the underlying business" (CLC ch. 2, s.20). Today's rule reads the three-year growth word and
the five-year slope, which a single bad year can both set.

Rule 2 becomes: a growth word of "Close to zero or negative" with a falling five-year revenue
trend **and revenue that fell in at least three of the last four year-over-year steps** of the
series is Decline, whatever the margin. A step is a fall when both years have a revenue and the
later is below the earlier; a step with a missing year is not a fall. With fewer than three
steps on file the rule cannot fire. Three of four is the structural constant, in code.

*My call:* three of four, the literal reading of the duration test on the method's five-year
window. It leaves 118 Decline rows and sends 135 to rule 5, where a "Close to zero or negative"
growth word gives Mature Stable (or, with a negative margin, rule 4). The alternative, two of
four, would keep 226 rows and the cyclicals with them. The Decline route is new and untested on
real data, so the smaller, cleaner population is the safer first run; the founder can loosen the
test after the readout.

A company that passed the old rule and fails the new one is flagged `revenue-falling`: word
"Revenue falling", sentence "Revenue fell in {n} of the last four fiscal years with a falling
five-year trend; the Decline rule needs three." Raised when the growth word is "Close to zero or
negative", the trend falls and the falling steps are fewer than three. A classifier check (3.6).

### 6.4 The financial industries

`design.md` 6.1 and the decision of 2026-10-26 put banks, insurers and REITs out of scope: "they
need their own methods in every phase". Operating income and invested capital have no meaning
for a company whose debt is its raw material. FMP's industry names do not sort these cleanly:
Corebridge (an insurer) and Equitable (an insurer) are "Asset Management"; Capital One,
Synchrony, Ally and SoFi (lenders) are "Credit Services"; Goldman Sachs and Morgan Stanley
(investment banks) are "Capital Markets"; Bank of New York Mellon is "Banking & Investment
Services".

The universe rule 4 adds these FMP industries to the excluded list: `Asset Management`,
`Financial - Capital Markets`, `Financial - Credit Services`, `Financial - Mortgages`,
`Financial - Conglomerates`, `Investment - Banking & Investment Services`, with the same
case-insensitive, dash-insensitive, prefix-and-space matching as the list today. `Financial -
Data & Stock Exchanges` stays admitted: S&P Global, Moody's, MSCI, CME and ICE are fee businesses
with ordinary statements.

*My call,* and the cost is stated: the exclusion also drops Visa, Mastercard and American
Express (Credit Services), BlackRock, T. Rowe Price and Blackstone (Asset Management) and the
brokers. Visa and Mastercard have ordinary statements and the method values them well; they
would leave because FMP files them with the lenders and the rule is by industry. So the universe
gains a **manual admission list** (`universe.manual_admissions`, the mirror of
`manual_exclusions`): a listing whose symbol is on it passes rule 4 whatever its industry and is
recorded as admitted like any other; the universe logs one INFO line
`manual admission: <symbols>`, and nothing is stored on the companies row. The founder's rule
for the list (2026-11-03): payment companies that do not lend. Today that is V (Visa), MA
(Mastercard) and GPN (Global Payments, a merchant processor); American Express and PayPal lend
and stay out. The rows of the six industries not on the list are recorded with their reason as
today (`industry: <industry>`), so nothing is lost from the store, and the readout names what
left.

The universe rules apply when a universe is built, which only a full refresh does (method
section 10; a revalue values the latest stored universe). So the exclusions take effect at the
full refresh of step 17.9, which also re-ranks the deciles without the excluded rows (design.md
6.4's suggestion: rank only the companies the engine values). The revalue before it still
values the financials under the old universe; the readout counts them.

### 6.5 Everything else

The series, growth, deciles, the growth word, the trends, the margin direction, the Dickinson
stage, the other checks and the unclassified reasons stay as they are. The deciles are not
re-ranked by the rule change: they rank growth rates, not phases, and a revalue reuses the
stored ones. The method's 3.5 is rewritten with the two rules above and 3.6 gains the two
flags.

## 7. The designation: price against value

### 7.1 The rule

On every valued row, the engine reads the price against the value at belief:

    price-to-value = price ÷ value

and gives it a word by the edges `designation_edges` = [e1, e2, e3, e4] of the policy:

| price ÷ value | Code | Screen word |
|---|---|---|
| below e1 | `well-below` | Well below |
| from e1, below e2 | `below` | Below |
| from e2 to e3, ends included | `near` | Near |
| above e3, below e4 | `above` | Above |
| at or above e4 | `well-above` | Well above |

*My call,* the edges: 0.65, 0.85, 1.15, 1.50. The inner pair is the fair band of method 4.10
(0.85 to 1.15 × value, ends included, as today's HOLD reads it); 1.50 is the trim multiple; 0.65
is one less the Narrow moat's margin of safety (0.35), the middle class, so the lowest band
starts where the middle class's buy level stood. (I told the founder 0.70; 0.65 is the one with
a source.) The column head is "Price vs value"; the word is the band's, never an action.

The designation is a fact about the price, so it moves with the price: a price refresh
recomputes it as it recomputed the stance. A refusal has none. A Start-up row has none (no
value).

### 7.2 What leaves and what stays

The five-step stance and the three screen words (method 4.10's table) leave the engine: no
`stance5`, no `stance3` on the result, in the snapshot JSON, on the API row, in the table, the
filter menu or the drawer. The levels stay exactly as they are: `buy` = value × (1 − the
moat's margin of safety), the fair band, `trim` = value × 1.5, computed once at valuation,
unchanged by a price refresh, shown in the drawer and on the band meter as marks. They are the
agent's figures for its stance.

The result gains `price_to_value: float | None` and `designation: str | None` (the code). The
JSON reader tolerates a snapshot that still carries `stance5` and `stance3` (the ones valued
under 0.5, read by the screen until the revalue replaces them) and ignores them.

### 7.3 The screen

- The `stance` column becomes the `designation` column: head "Price vs value", the word as a
  chip in the design system's chip style with no stance colour (anti-goal 1); sortable, the sort
  key `priceToValue` ascending by the ratio, rows without one last. Default columns: `ticker`,
  `name`, `phase`, `band`, `mechanical`, `reviewed`, `price`, `designation`.
- The filter menu's STANCE section becomes PRICE VS VALUE with the five words.
- The drawer's band meter marks the price on the band, with its scale off; the level labels sit
  in a list under the meter: "Fair value", "Margin of safety" (the buy level: "value less the
  {moat} moat's 35%", or "value less the 45% margin for no moat"), "Fair band" and "1.5 × value"
  (the trim level); the data keys `buyLevel` and `trimLevel` keep their names. The designation's
  chip sits in the meter's head, and the meter's caption states the word and the ratio ("Below:
  the price is 0.72 × the value"; two decimals, or three kept off the edge where two would land
  on a designation edge the ratio is not on); the "Five-step stance" caption goes. The zones
  keep their fills without words. (The Task 6 departure, ruled acceptable: on the scale, in the
  drawer's 288px rail, the labels collide; the zone words are the founder's design-system call.)
- The groups view's "Below buy" share becomes "Below value": the share of valued rows whose
  price ÷ value is below e2 (the `below` and `well-below` bands).
- The API row carries `priceToValue` and `designation`; `stance3` and `stance5` leave
  `EXTRA_KEYS`, `ROW_KEYS` and the tests that pin them.
- `bundle.js`'s `stanceOf`, the STANCE words and the menu section are replaced under new
  `// fairband:` markers; `app.js`'s `stanceOf` and the pinned line
  `if (r.price == null || r.buyLevel == null || r.trimLevel == null) return null;` go with the
  tests that pin them; the designation comes from the row, not derived on the client.

The method's 4.10 becomes "Levels, designation and validity": the levels as today, the table
above in place of the stance table, the validity unchanged.

## 8. The sticky controls and the back-to-top control

### 8.1 What exists

The window does not scroll. `.app-main` (in `index.html`) is the scroller; inside it the FIND,
filter and columns bar (`.fb-screen__bar`, from the vendored `bundle.js`) sits above the table,
and the table header already sticks (`bundle.css`: `.fb-table thead th { position: sticky;
top: 0 }`). So the bar scrolls away and the header stays. The page header above `.app-main`
deliberately does not stick (`index.html` comment). The design system's rule is no motion.

### 8.2 The sticky bar

The bar sticks at the top of `.app-main` (`position: sticky; top: 0`), on the raised surface
with a z-index above the header cells, and the header cells' `top` becomes the bar's height, so
the two stack with no gap and no overlap. The bar's height varies (chips wrap), so the page
measures it with a `ResizeObserver` and sets a custom property (`--bar-height`) on the screen
container that the header cells' `top` reads; the fallback value is the bar's one-line height.
The FIND focus ring keeps its room (the `padding-top` the screen-controls spec gave `.app-main`
moves inside the sticky bar or stays, whichever keeps the ring unclipped; a test pins the ring's
room as today). The drawer and the groups view are untouched.

### 8.3 Back to top

A control at the bottom right of the table's scroller: the design system's quiet small button
(`F.Button`, variant `quiet`, size `sm`) with the text "Top" and an up arrow glyph, `aria-label`
"Back to top". It is rendered only when `.app-main` has scrolled past its own height (one
screen), and removed otherwise; it sits over the table, inside the screen's layout cell, so the
drawer rail never covers it. Activating it sets the scroller's `scrollTop` to 0 (instantly, no
smooth scrolling) and moves focus to the FIND field, because the control itself disappears at
the top. Keyboard: a button, reached by Tab.

Tests: Python string tests as the page's others (`tests/web/test_app.py`): the bar's sticky
rule and the header's `top` reading the property; the observer; the button's `aria-label`, its
threshold and the focus move. No browser test exists in the project and none is added.

## 9. The Start-up route

### 9.1 Which rows, and the result

A company the classifier puts in Start-up (3.2: revenue zero now, or zero three years ago).
The result's route is `start-up`. It has no value, no levels, no designation: a refusal, the
reason "Start-up: no value by design", that keeps its figures, as the growth route's target-margin
refusal keeps the margin the price needs. `design.md` 6.8 decided this: "Tier 1: no value. The
row shows the price-implied requirement ... and a floor at cash." The refusal text of method
section 7 changes to this shorter form.

The route's guards, in order, after the shared ones of 5.1 that apply (no universe deciles, the
assembly's refusal, a foreign filer, no price, no positive diluted share count; "no trailing
figures" does not refuse here, since a pre-revenue company may lack a trailing revenue and the
route reads what exists): none refuse further. Every Start-up row gets the refusal above with
the intermediates below; what cannot be computed carries its own reason inside the
intermediates.

### 9.2 The price-implied requirement

What the price needs, as one number: the revenue in year 10 that, at the mature peers' margin,
makes the company worth its price today. Damodaran's pre-revenue case (Secure Mail) built value
from a market, a share and a target margin; the market and the share are the agent's, so the
screen states the product, revenue, that any market-and-share story must reach.

The enterprise value the price implies:

    EV_price = market cap + debt − cash

with debt and cash as 5a.9 reads them (a missing line nil, flagged `line-not-presented:<field>`).
Market cap is the quote's (section 2). When EV_price is at or below zero the requirement is
zero: the net cash covers the price; the row is flagged `below-net-cash` ("The price is covered
by net cash: market cap {x} against net cash {y}").

Otherwise the route solves for R10, the year-10 revenue, on a ten-year path:

- revenue: a straight line from R0, the trailing revenue (zero when there is none), to R10:
  R_t = R0 + (R10 − R0) × t ÷ 10;
- operating income, in dollars, a straight line from E0, the trailing operating income (the
  trailing figure when it exists, else the last fiscal year's, else zero), to m* × R10, with m*
  the target margin: EBIT_t = E0 + (m* × R10 − E0) × t ÷ 10. A pre-revenue company has no
  margin, so the path is on the loss in dollars, not on a margin;
- tax and NOPAT by 5a.6 (the carried loss starting at zero; the tax-loss flag applies);
- reinvestment by 5a.5's formula on the revenue steps, at the sales-to-capital of 9.3:
  reinvestment_t = max(0, (R_{t+1} − R_t) ÷ sales-to-capital) for t = 1 … 9, and year 10's
  = terminal NOPAT × g_T ÷ terminal return;
- the free cash flow, the terminal and the firm value by 5a.7 at r in every year (5a.8), the
  terminal return by 4.7 (the moat from the GuruFocus score as 4.9; a Start-up without a score
  is None and takes r).

EV(R10) is the firm value so built. The solve finds R10 ≥ 0 with EV(R10) = EV_price by
bisection on [0, 10^13] to a relative tolerance of 1e-9 (the scan bounds and tolerance are
structural constants, 4.1a). EV(R10) rises with R10 for every sensible input (the terminal
dominates); the solve checks EV(10^13) ≥ EV_price and otherwise records "no revenue reaches
the price". The intermediates record `requirement`: `revenue_y10`, `ev_price`, `revenue_0`,
`operating_income_0`, `target_margin` (with 5a.4's record of the peers and the source),
`sales_to_capital` (as 5a.5 records it), `path` (the ten years of revenue, EBIT, tax, NOPAT,
reinvestment, free cash flow), `terminal_value`, or `reason` when it cannot be computed: "no
target margin: {n} mature peers", "no sales-to-capital", "no statutory tax rate", "no market
cap", "no revenue reaches the price".

Beside R10 the drawer says the multiple of today's revenue when R0 is positive ("12.4 × the
trailing revenue") and the margin and peer count behind m*.

### 9.3 The target margin and sales-to-capital

The target margin is 5a.4's, with the mature peers, the industry fallback and the records,
flags and RULE inputs as there (`peer_min`, `peer_margin_min_years`, `industry_peer_max`,
`peers-from-industry`). Sales-to-capital is 5a.5's peers' median only: a Start-up has no usable
own measure (no six kept ROIC years with revenue), so step 1 never stands and the record says
"peers". Without three positive peer measures the requirement's reason is "no sales-to-capital".

### 9.4 The cash floor and the burn cover

Two figures the drawer shows and a row column can carry:

- `cash_floor`: (cash − debt) ÷ diluted shares, the net cash a share. When the price is below
  it the row is flagged `below-net-cash` (9.2).
- `burn_cover_years`: cash ÷ the yearly burn, the burn = −(trailing operating cash flow +
  trailing capital spending) when that sum is below zero; "not burning" when it is zero or
  above; none without trailing figures. Below `burn_cover_flag_years` the row is flagged
  `burn-cover-short`: word "Cash cover short", sentence "Cash covers {x} years of the trailing
  burn of {y} a year." *My call:* 2 years; no source gives a number; Damodaran's Start-up
  pricing table names "capital access" as what the market prices at this phase (CLC ch. 9,
  s.11).

### 9.5 Flags, intermediates and inputs

Flags, in order: the assembly's and the classifier's checks first (as every route); then
`line-not-presented:debt`, `line-not-presented:cash`; `peers-from-industry`; `tax-loss-history-unknown`
when the path has a loss year (always, for a loss-maker); `below-net-cash`; `burn-cover-short`.
Never the ROIC flags, `return-above-peers`, `few-analysts` or the trailing flags: no path reads
the consensus or a return.

Intermediates: `requirement` (9.2), `cash_floor`, `burn_cover_years`, `burn`, `price_facts`
(as every refusal carries), `debt`, `cash`, `shares`, `market_cap`.

Tagged inputs. DATA: the fiscal years on file, price, diluted shares, market cap, trailing
revenue and operating income when they exist, trailing operating cash flow and capital
spending, `target_margin` and `sales_to_capital` as 5a.14 cites them, `debt` and `cash`. RULE:
r, g_T, the moat class, the terminal return, `peer_min`, `peer_margin_min_years`,
`industry_peer_max` on a fallback row, `burn_cover_flag_years`.

The price refresh: a Start-up row recomputes `requirement.revenue_y10` and `ev_price` from the
new quote's market cap and its stored path inputs (the rebuild keys: `revenue_0`,
`operating_income_0`, `target_margin.value`, `sales_to_capital.value`, `tax_rate`, the terminal
return), `cash_floor`'s flag and nothing else.

## 10. The Decline route

### 10.1 Which rows, and the refusals

A company the classifier puts in Decline (6.3). The result's route is `decline`. The shared
guards of 5.1 apply in their order. Then the route's own, in this order: no trailing revenue;
no trailing operating income; no statutory tax rate; no sales-to-capital (10.4); a value a share
at or below zero after the distress weighting, "value not positive in the run-off", which keeps
the figures.

### 10.2 The revenue path

Damodaran's run-off: "a firm partially liquidates itself each year until it just about
disappears" (Investment Valuation ch. 12); the Sears model shrinks revenue 5% a year and counts
the cash from divestitures (Damodaran 2009, "Valuing Distressed and Declining Companies").

Years 1 to 3 are the consensus path of 5a.2, as every route reads the near term: year 1 the NTM
consensus revenue, years 2 and 3 the annual consensus steps, a missing step holding the rate of
the year before (`path-held`), thin landing years `few-analysts`. The departures: an incomplete
NTM consensus or a non-positive NTM revenue does not refuse; every year then takes the decline
rate, and the row is flagged `path-on-trend` ("No usable consensus: every year shrinks at the
five-year trend's {d}"). A step at or below −100% refuses "consensus revenue falls to zero or
below within the path" as 5a.2.

Years 4 to N (N = `runoff_years`, 10) shrink at the decline rate:

    d = min(0, five-year revenue slope ÷ revenue of the last fiscal year)

the slope the classifier's least-squares trend (3.4), in dollars a year, over the last fiscal
year's revenue, so d is the trend as a fraction of today's size. The Decline rule makes the slope
negative, so d is below zero on every row; the min guards the definition. No fade and no floor:
the terminal continues at d.

    revenue_t = revenue_{t−1} × (1 + d), for t = 4 … N

A consensus step above zero on a Decline row flags `consensus-recovery`: "The consensus has
revenue growing {g} in year {t} while the five-year trend falls {d}." (Damodaran: declining
firms "look cheap" when forward numbers assume good health.)

### 10.3 Margin, tax and NOPAT

The operating margin held in every year is the **normalized margin** m_n: the median of the
operating margins of the last five fiscal years that have one (3.4's margins), when at least
three exist; else the trailing margin m_0 = trailing operating income ÷ trailing revenue.
Damodaran's Sears model holds one margin through the run-off; his Las Vegas Sands earnings
power took a four-year average "as a reasonable measure of earnings from existing assets"; the
Mature Stable route normalizes its earnings the same way (6.2). A one-year loss at an
established decliner (Intel, CarMax) does not zero its run-off; a chronic loss-maker's median is
below zero and the run-off says so. *My call,* after the builder check: the first draft held
the trailing margin, which refused every decliner with one loss year.

    EBIT_t = revenue_t × m_n

Tax and NOPAT by 5a.6, the carried loss starting at zero, the tax-loss flag as there. The
intermediates record `margin` (the median, the trailing margin, the fiscal years and margins
read, which one the route used), and the drawer states both margins. The `margin-flag` of
section 8 applies to the trailing margin as on every route.

### 10.4 Capital released, reinvestment and sales-to-capital

A shrinking company needs less capital; the capital a dollar of lost revenue frees is the
inverse of sales-to-capital, and the company recovers only a part of it in a divestiture:
Damodaran's Sears divestitures recovered 54% to 67% of the capital they released.

    release_t = max(0, (revenue_{t−1} − revenue_t) ÷ sales-to-capital) × runoff_recovery
    reinvestment_t = max(0, (revenue_t − revenue_{t−1}) ÷ sales-to-capital)
    FCFF_t = NOPAT_t − reinvestment_t + release_t

A year whose revenue falls releases capital; a year whose revenue rises (a consensus step above
zero) reinvests in full. The release and the reinvestment are in the year of the change, not a
year ahead: the growth route's one-year lag (5a.5) funds growth before it comes; a divestiture
is cash in the year of the sale. *My call:* `runoff_recovery` = 0.6, the midpoint of the Sears
range, rounded.

Sales-to-capital is the company's own newest-year measure: the revenue of its newest kept ROIC
year (4.5) ÷ that year's average invested capital, as 5a.4 defines a peer's. The five-year
marginal measure of 5a.5 does not fit a shrinking company (its capital shrinks). Without a
kept year, or with that capital at or below zero, the mature peers' median of 5a.5 step 2 (the
peers of 5a.4 with the industry fallback); without that, the refusal "no sales-to-capital". The
record says "own-latest" or "peers".

### 10.5 The terminal and the going-concern value

The terminal is a perpetuity at d, Damodaran's negative-growth perpetuity (Myth 5.4: with
asset sales the terminal value rises because reinvestment turns negative):

    revenue_{N+1} = revenue_N × (1 + d)
    NOPAT_{N+1} = revenue_{N+1} × m_0 × (1 − tax rate), when m_0 is above zero, else revenue_{N+1} × m_0
    FCFF_{N+1} = NOPAT_{N+1} + max(0, (revenue_N − revenue_{N+1}) ÷ sales-to-capital) × runoff_recovery
    terminal value_N = FCFF_{N+1} ÷ (r − d)

    firm value = Σ_{t=1..N} FCFF_t ÷ (1 + r)^t + terminal value_N ÷ (1 + r)^N
    equity_gc = firm value − debt + cash
    going-concern value a share = equity_gc ÷ diluted shares

Debt and cash as 5a.9, with its flags. r in every year (5a.8).

### 10.6 The liquidation floor

Damodaran values an irreversible decline at the higher of the going-concern and the
orderly-liquidation value; Greenwald and Graham use net current assets as the floor. Tier 1's
orderly-liquidation stand-in is Graham's net current asset value, from the newest annual
balance sheet:

    NCAV = total current assets − total liabilities
    floored value a share = max(going-concern value a share, NCAV ÷ diluted shares)

The floor binds only when NCAV is above zero and above the going-concern equity; a bound row
is flagged `ncav-floor`: "The value is the net current asset value {x} a share; the run-off
gives {y}." `totalLiabilities` missing counts as nil and flags `line-not-presented:totalLiabilities`,
and then no floor is applied (a nil liability would overstate it).

### 10.7 The distress probability and the distress-sale value

Damodaran keeps distress out of the discount rate and weighs it once:

    value a share = floored value × (1 − π) + distress-sale value a share × π

**π** is the ten-year cumulative probability of default of the company's synthetic rating.
The rules, the first that fits deciding:

1. a company whose cash is at or above its debt has π = 0: there is no debt to default on. The
   intermediates say "no net debt";
2. a company with net debt and no interest expense on file (the line not presented, or zero
   over the four trailing quarters) has no rating: π is unavailable, the value is the floored
   going-concern value, flagged `distress-not-charged` ("No interest expense on file: the
   distress probability is unavailable and the value is the going-concern value");
3. otherwise the coverage is the route's own EBIT over the interest: EBIT_n ÷ trailing interest
   expense, with EBIT_n = trailing revenue × m_n (10.3) and the expense as its size (FMP signs
   it either way), over the same four quarters. A one-year loss does not rate an established
   company D; a chronic loss-maker's EBIT_n is at or below zero and takes the lowest row (D),
   whatever the interest. The rating is the row of `synthetic_rating` (Damodaran's table for
   large non-financial firms, January 2026, 15 rows from D to AAA) whose coverage range holds
   the coverage;
4. π = `default_probability_10y[rating]`, from Damodaran 2009, Table 5 (Altman, 1971 to 2007),
   the ten-year column; D is 100%; BB+ is not in that table and takes BB's figure (*my call:*
   the nearest lower rating, so a BB+ company is charged a little more, never less).

**The distress-sale value** is Damodaran's choice (a) in "Estimating Distress Sale Proceeds"
(2009): a fraction of the discounted cash flow value of the assets, "if the discounted cash
flow valuation yields $5 billion ... $3 billion in the event of a distress sale":

    distress proceeds = distress_sale_fraction × firm value + cash
    distress-sale value a share = max(0, distress proceeds − debt) ÷ diluted shares

*My call:* `distress_sale_fraction` = 0.6, his illustration's ratio. Not his choice (b), the
no-growth earnings power of the assets at a healthy cost of capital, which `design.md` 6.12
named: on a shrinking firm a no-growth perpetuity exceeds the going-concern value, and the
distress weighting would raise the value (anti-goal 2). The worked numbers (13.1) show it. The
agent may replace the fraction with an asset-by-asset estimate in tier 2.

### 10.8 The distress signals

Shown on every Decline row, never deciding the value:

- **Altman Z″**, the non-manufacturer form: 6.56 × X1 + 3.26 × X2 + 6.72 × X3 + 1.05 × X4,
  with X1 = working capital ÷ total assets (current assets − current liabilities), X2 =
  retained earnings ÷ total assets, X3 = operating income ÷ total assets, X4 = book equity ÷
  total liabilities, every line from the newest annual balance sheet and its fiscal year's
  income statement. The coefficients are the model's, in code; the zones are policy: below
  `z_distress` (1.1) "distress", above `z_safe` (2.6) "safe", between "grey" (Altman 2000).
  A zone of "distress" flags `z-distress`: "Altman Z″ is {z}, in the distress zone below 1.1."
  Any missing line gives no score.
- **Piotroski F**, the nine signals on the newest fiscal year against the one before, one point
  each: net income ÷ total assets above zero; operating cash flow above zero; that return on
  assets higher than the year before's; operating cash flow above net income; long-term debt ÷
  total assets lower than the year before's; the current ratio higher; no common stock issued
  (`commonStockIssuance` at or below zero); gross margin higher; asset turnover (revenue ÷ total
  assets) higher. A signal whose line is missing scores nothing and the score says how many
  signals it read. Below or at `f_score_low` (1) the row is flagged `f-score-low`: "Piotroski F
  is {f} of {n}: the low group of Piotroski (2000)."
- **Reinvesting in decline**: trailing capital spending above trailing depreciation and
  amortization in size while the revenue path falls flags `reinvesting-in-decline` ("Capital
  spending {x} exceeds depreciation {y} while revenue falls: Damodaran's denial"). The flag is
  his value trap in mechanical form: a company "cheap, only if their managers don't try too
  hard".

### 10.9 What moves with the price

As 5a.10 for the shape: the levels and the validity stay; the designation, the implied decline
rate (the d at which the going-concern path, floored and weighted as built, equals the price,
scanned from −50% to 0 in steps of 0.1% to 1e-7; "none" when the price is above the value at d
= 0 or below the value at −50%), the multiples of 5.9 (trailing P/E reported and clean, no
forward P/E) and the expected return of 5.10 with g_T replaced by d. The rebuild keys:
`runoff_path` (revenue_0, ntm_revenue, the consensus steps as found, d, runoff_years),
`margin`, `tax_rate`, `sales_to_capital` (used, value), `runoff_recovery`, `debt`, `cash`,
`shares`, `ncav`, `pi` with its rating and coverage, `distress_sale_fraction`.

### 10.10 Flags, intermediates and inputs

Flags, in order: the assembly's and the classifier's checks; `path-held`, `path-on-trend`,
`consensus-recovery`, `few-analysts`; `line-not-presented:debt`, `line-not-presented:cash`,
`line-not-presented:totalLiabilities`; `peers-from-industry` when the peers served;
`tax-loss-history-unknown`; `ncav-floor`; `distress-not-charged`; `z-distress`; `f-score-low`;
`reinvesting-in-decline`; the trailing flags (`margin-flag`, `equity-raise`, `negative-fcf`,
`heavy-capex`, `large-nri`). Never the ROIC flags, `return-above-peers`, `value-spread`,
`consensus-above-base-rate` or `failure-not-charged`.

Intermediates: `runoff_path`; `margin` (10.3); `growth_rates` years 1 to N; `revenue_by_year`, `ebit_by_year`,
`tax_by_year`, `nopat_by_year`, `reinvestment_by_year`, `release_by_year`, `fcff_by_year`;
`terminal_value`, `firm_value`, `equity`, `going_concern_per_share`, `ncav`,
`ncav_per_share`, `floored_per_share`; `rating` (coverage, interest, the rating, π, the source
row), `distress_proceeds`, `distress_per_share`, `value_per_share`; `altman_z` (the four
ratios, the score, the zone), `piotroski_f` (the nine signals as read, the score, the count
read); `capex_vs_depreciation`; `eps`, `epv`, `price_facts`, `multiples`, `expected_return`,
`implied_decline_rate`; the rebuild keys.

Tagged inputs. DATA: the common ones of 5.12 that exist (the fiscal years, price, diluted
shares, next earnings date, daily closes, market cap, trailing revenue, operating income, EPS,
dividends, buybacks and stock issued, the newest tax rate, GuruFocus EPS figures), `ntm_revenue`,
`path_step_2`, `path_step_3` as 5a.14, `interest_expense` (trailing, cited to the quarterly
statements), `sales_to_capital` (own-latest cited to the statements, or the peers' as 5a.14),
`debt`, `cash`, `total_current_assets`, `total_liabilities`, the Z″ and F lines (cited to the
annual statements), `depreciation` (trailing). RULE: r, `runoff_years`, `runoff_recovery`,
`distress_sale_fraction`, `synthetic_rating` (the row used, noted), `default_probability_10y`
(the figure used), `z_distress`, `z_safe`, `f_score_low`, `peer_min` and `industry_peer_max`
when the peers served, the moat class (the margin of safety for the levels only; the route's
terminal is at d, not the terminal return).

### 10.11 Young Growth and the shared table

The synthetic rating reads interest coverage, which is negative for a loss-maker, so the table
cannot give Young Growth its failure probability; Damodaran uses survival tables by age there,
which the founder ruled unavailable for a listed company above $2 billion (2026-11-02). So the
table serves Decline. A chronic loss-maker (a normalized margin at or below zero) with net debt
is rated D, π = 100%, and its value is the distress-sale value alone: a fraction of a firm value
that is itself at or below zero, plus cash, less debt, so usually zero, and the row is refused
"value not positive in the run-off" with every figure kept (the path, the rating, the
signals, NCAV). The net-current-asset floor has no weight at π = 100%: a company that defaults
does not liquidate in an orderly way. That is the honest mechanical reading of a company losing
money on three falling years with net debt; whether the decline is reversible and what the
equity's option is worth are the agent's (`design.md` 6.12). In today's database 63 of the
Decline rows have a negative last-year margin; the normalized margin of 10.3 separates the
one-year losses among them (valued) from the chronic ones (refused with figures).

## 11. The statement fields and the backfill

The routes read six FMP lines the normalizer does not keep as facts today, all present in the
stored payloads: `grossProfit` and `interestExpense` (income statement, annual and quarterly),
`totalAssets`, `totalLiabilities` and `retainedEarnings` (annual balance sheet),
`depreciationAndAmortization` (cash flow, annual and quarterly). The normalizer
(`vendors/normalize_fmp_statements.py`) gains them, so every fetch from now on stores them as
facts citing their response.

The stored payloads are re-read once by a **backfill**: for every stored statement response of
the six endpoints, it writes the facts of the new fields that are missing, keyed to that
response, and touches nothing else. It is idempotent (a second run writes nothing) and logged
with its count. It runs first in every refresh that values: the revalue, the full refresh and
the scoped refresh, before their value stage. A full refresh is not exempt: it reuses any
response observed within 24 hours without a fetch, and those responses carry no new facts until
the backfill writes them (the builder check caught this). The price refresh does not value and
does not run it. The trailing figures (4.2) gain `interest_expense` and `depreciation`, summed
over the same four quarters as the rest; `CapitalYear` or a new per-year balance record carries
the annual lines the Z″, the F-score and NCAV read.

The method's section 2 table gains the six lines and section 10 one sentence: every refresh
that values runs the facts backfill first.

## 12. Policy v5

`fairband-policy-v5.toml`: v4 plus the rows below. v1 to v4 stay in the package unchanged; the
engine loads v5 only; `tests/policy/test_policy.py` pins v4's hash as it pins v3's.

| Value | Policy name | Source |
|---|---|---|
| FMP pace 2,850 calls a minute | `refresh.fmp_calls_per_minute` | the founder's Ultimate plan, 3,000 a minute, less 5%; my call |
| 429 hold 60 s | `refresh.rate_limit_hold_s` | one plan window; my call |
| Excluded industries + the six of 6.4 | `universe.excluded_industries` | design.md 6.1; decision 2026-10-26; this spec 6.4 |
| Manual admissions: V, MA, GPN | `universe.manual_admissions` | founder 2026-11-03: payment companies that do not lend; this spec 6.4 |
| Designation edges 0.65, 0.85, 1.15, 1.50 | `designation_edges` | method v1.7 Step 10 (the fair band, the trim multiple, the Narrow margin of safety); this spec 7.1 |
| Run-off horizon 10 years | `runoff_years` | Damodaran's ten-year template (H2) |
| Divestiture recovery 0.6 | `runoff_recovery` | Damodaran 2009 Sears: 54% to 67% of the capital released; the midpoint |
| Distress-sale fraction 0.6 | `distress_sale_fraction` | Damodaran 2009, "Estimating Distress Sale Proceeds", choice (a), the illustration's $3 billion of $5 billion |
| Synthetic rating table, 15 rows | `synthetic_rating` | Damodaran, ratings.html, "For large non-financial service firms", January 2026 |
| Ten-year default probability by rating, 15 rows | `default_probability_10y` | Damodaran 2009, Table 5 (Altman, 1971 to 2007); D 100%; BB+ as BB (my call) |
| Z″ zones 1.1 and 2.6 | `z_distress`, `z_safe` | Altman 2000 |
| Piotroski low group: 1 | `f_score_low` | Piotroski 2000, the 0 to 1 group |
| Burn cover flag 2 years | `burn_cover_flag_years` | no source; my call |

The synthetic rating rows (coverage above, up to; rating): −∞ to 0.199999 D; 0.2 to 0.649999
C; 0.65 to 0.799999 CC; 0.8 to 1.249999 CCC; 1.25 to 1.499999 B−; 1.5 to 1.749999 B; 1.75 to
1.999999 B+; 2 to 2.2499999 BB; 2.25 to 2.49999 BB+; 2.5 to 2.999999 BBB; 3 to 4.249999 A−;
4.25 to 5.499999 A; 5.5 to 6.499999 A+; 6.5 to 8.499999 AA; above 8.5 AAA. The policy stores
the lower bound of each row (a coverage at or above it and below the next row's) and the
rating; the default spreads are not stored (no route reads them).

The ten-year default probabilities (percent): AAA 0.07; AA 0.51; A+ 0.57; A 0.66; A− 5.00;
BBB 7.54; BB+ 19.63 (as BB); BB 19.63; B+ 28.25; B 36.80; B− 42.12; CCC 59.02; CC 66.6; C
81.03; D 100. (The table's C+ 75.16 and C− 87.16 rows have no synthetic-rating row and are not
stored.)

The structural constants added to code (4.1a): the established test (three of the last five
fiscal years with a margin above zero); the Decline duration test (three of the last four
steps); the requirement's bisection bounds and tolerance; the Z″ coefficients; the nine
Piotroski signals; the implied-decline scan (−50% to 0 in steps of 0.1%).

## 13. Worked numbers for the tests

### 13.1 A Decline row

Trailing revenue 1,000, trailing operating income 80 (m_0 = 8%), the five fiscal margins 7%,
8%, 8%, 9%, 8% (m_n = 8%, EBIT_n = 80), tax rate 25%, own sales-to-capital 2.0, recovery 0.6,
the consensus steps −3% in each of years 1 to 3 (NTM 970; base + 1 940.9; base + 2 912.67),
five-year slope −40 a year so d = −4%, r = 9%, debt 200, cash 100, 100 diluted shares,
trailing interest expense 20 (coverage 4.0, rating A−, π = 5.00%), total current assets 300 and
total liabilities 500 (NCAV −200, no floor).

| Year | Revenue | EBIT | NOPAT | Reinvest − release | FCFF |
|---|---|---|---|---|---|
| 1 | 970.00 | 77.60 | 58.20 | −9.00 | 67.20 |
| 2 | 940.90 | 75.27 | 56.45 | −8.73 | 65.18 |
| 3 | 912.67 | 73.01 | 54.76 | −8.47 | 63.23 |
| 4 | 876.17 | 70.09 | 52.57 | −10.95 | 63.52 |
| 5 | 841.12 | 67.29 | 50.47 | −10.51 | 60.98 |
| 6 | 807.47 | 64.60 | 48.45 | −10.09 | 58.54 |
| 7 | 775.18 | 62.01 | 46.51 | −9.69 | 56.20 |
| 8 | 744.17 | 59.53 | 44.65 | −9.30 | 53.95 |
| 9 | 714.40 | 57.15 | 42.86 | −8.93 | 51.79 |
| 10 | 685.83 | 54.87 | 41.15 | −8.57 | 49.72 |

FCFF_11 = 41.15 × 0.96 + (685.83 − 658.40) ÷ 2 × 0.6 = 47.73; terminal value_10 = 47.73 ÷ 0.13
= 367.18; present value of the flows 387.55, of the terminal 155.10; firm value 542.65; equity
442.65; going concern 4.4265 a share. Distress proceeds 0.6 × 542.65 + 100 = 425.59; less debt
225.59; 2.2559 a share. Value = 4.4265 × 0.95 + 2.2559 × 0.05 = 4.3180 a share (tolerance
1e-3 on the figures above; the test pins the exact decimals the builder's arithmetic gives, to
1e-9, after checking them against these).

Variants the tests pin: cash 250 (net cash) gives π = 0 and the value 4.4265 + 1.50 = 5.9265
(cash enters the equity bridge); interest expense nil with net debt gives `distress-not-charged`
and 4.4265; NCAV 600 (current assets 1,100) gives the floor 6.00 a share, `ncav-floor`, and the
value 6.00 × 0.95 + 2.2559 × 0.05 = 5.8128; a trailing margin of −1% with the same five
fiscal margins gives the same run-off and rating (m_n = 8%) and records both margins; fiscal
margins −2%, −1%, −1%, −1%, −1% (m_n = −1%, EBIT_n = −10) give rating D, π = 100%, a firm value
below zero, a distress-sale value of max(0, 0.6 × firm value + 100 − 200) = 0 and the refusal
"value not positive in the run-off" with the figures kept; the same with cash 250 gives π = 0
and the floored going-concern value, below zero, so the same refusal; three fiscal margins on
file use their median, two fall back to the trailing margin; a consensus step of +2% in year 2
flags `consensus-recovery` and reinvests (R_2 − R_1) ÷ 2.0 in full.

### 13.2 A Start-up row

Trailing revenue 0, trailing operating income −50, target margin 25% (the peers' median), the
peers' sales-to-capital 1.5, tax rate 25%, r = 9%, g_T = 3%, no moat score (terminal return r,
terminal multiple 11.4444), market cap 2,000, debt 0, cash 300, EV_price 1,700, 100 diluted
shares. EV(0) = −166.93; EV(1,000) = 931.91; the solve gives R10 = 1,725.73 (tolerance 0.01),
with EV(R10) = 1,700.00. Trailing operating cash flow −60 and capital spending −15: burn 75 a
year, `burn_cover_years` 4.0, no flag at the 2-year threshold; cash 120 gives 1.6 and
`burn-cover-short`. Cash floor 3.00 a share; a market cap of 250 gives EV_price −50, the
requirement 0 and `below-net-cash`.

### 13.3 The designation

Value 100: prices 64.99 well-below, 65 below, 84.99 below, 85 near, 115 near, 115.01 above,
149.99 above, 150 well-above. A price refresh from 70 to 120 moves the word from below to
above and leaves the levels.

### 13.4 The classifier

Five fiscal years with operating margins 4%, 4%, 3%, 2%, −1% and a "Moderate" growth word:
established, Mature Growth, `loss-year`. Margins −5%, −4%, −3%, 1%, −1%: one positive year,
not established, Young Growth or High Growth by the trend. Revenues 100, 95, 90, 86, 83 with a
bottom growth word and a falling slope: four falls, Decline. Revenues 100, 120, 80, 82, 84:
one fall, not Decline, `revenue-falling` ("1 of the last four"), Mature Stable with a
positive margin. Revenues 100, 95, 90, 86 (four years, three steps, all falls): Decline.

### 13.5 The limiter

At 60 calls a minute with a fake clock: three threads calling at once get slots 0, 1 and 2
seconds apart; a 429 at t = 5 with no `Retry-After` holds the next slot to t = 65, and a call
from another thread at t = 10 sleeps 55 seconds; a `Retry-After: 7` holds to t = 12; at 0 calls
a minute no call waits. The deadline: a call admitted at t = 55 after waiting 55 seconds has
its full `deadline_s` from t = 55.

## 14. Tests the builder must write

- The limiter's unit tests of 13.5; `VendorHttp.get` with a limiter: the acquire before every
  try, the hold on 429, the deadline extension; `clients.py` wiring (FMP paced, GuruFocus not);
  a full-refresh run on the Router where the Nth call answers 429 once and the run completes
  in one run, with the hold observed by the other workers; the existing 429 tests still pass
  (three 429s fail the run).
- The classifier: 13.4, the two flags' sentences, the rule order (Decline before the
  established rule), the established test's edge (exactly three of five; a year without a
  margin), the duration test's edge (fewer than three steps on file), `growth-word-disagrees`
  silent under rule 4a.
- The universe: a row in each of the six industries excluded with `industry: <industry>`; Data &
  Stock Exchanges admitted; the prefix match; a row on the admission list admitted from an
  excluded industry, with the one INFO line `manual admission: <symbols>` and nothing stored on
  the companies row; a row on both lists follows the exclusion (a test pins the order).
- The designation: 13.3, the edges from policy, `None` on a refusal and on a Start-up row,
  the price refresh moving the word, the JSON round trip, a 0.5 snapshot with `stance5` and
  `stance3` read without error.
- rows.py: `priceToValue` and `designation` on the row, no `stance3`/`stance5`; the sort by
  `priceToValue` with none last; the groups' "Below value".
- The page: the bar's sticky rule, the header's `top` reading the custom property, the
  observer, the button's label, threshold and focus move; the chip and the filter section's
  five words; the drawer's caption and level labels.
- The Start-up route: 13.2 (the solve, the burn cover, the net-cash case), each `reason` of
  the requirement, the flag order, the inputs, the price refresh rebuilding `revenue_y10`.
- The Decline route: 13.1 and its variants, the path with a held step and with no consensus
  (`path-on-trend`), the sales-to-capital fallback to the peers, each flag's sentence, the
  refusal order, the Z″ and F arithmetic on hand-built statements (one example each, with a
  missing line), the implied decline rate at the price, the JSON round trip and the price
  refresh.
- The backfill: a stored payload of each statement kind gains the six facts; a second run
  writes nothing; the revalue, the full refresh and the scoped refresh run it before valuing
  and the price refresh does not; a full refresh that reuses a response from before the
  change values the company with the new facts; the trailing interest expense and
  depreciation.
- The Decline margin: the median of five fiscal margins, of three, the trailing fallback with
  two; the coverage on EBIT_n; the π rule order (net cash first, then no interest, then D).
- The policy: v5's values, v4's hash pinned, the tables' row counts and monotonic bounds.

## 15. Acceptance

1. A full refresh of the founder's database completes in one run at 16 workers, with the
   limiter's wait and no 429 in the log.
2. After the revalue: NSP is Mature Growth with `loss-year`; EQT, NKE and EXPD are not
   Decline and carry `revenue-falling`. After the full refresh: CRBG, COF, GS, BK, AXP and PYPL
   are excluded with their industry; V, MA and GPN are admitted by the list and valued.
3. No row shows a stance; every valued row shows a designation word; the drawer shows the
   levels with the new labels and the ratio.
4. The bar and the header stay in view while the table scrolls; the Top control appears past
   one screen, returns to the top and focuses FIND.
5. Every Start-up row shows the requirement or its reason, the cash floor and the burn cover;
   every Decline row shows a value or a refusal naming the missing input, π with its rating,
   Z″ and F.
6. The readout, written up for the founder: the phase counts before and after; the growth,
   Mature Growth and Mature Stable rows moved by the classifier and their outcomes; the
   designation counts by band; the Start-up requirements' distribution (the multiple of
   trailing revenue where it exists); the Decline rows valued and refused by reason, the median
   price ÷ value, the ratings' distribution, the floor and distress-charged counts, the flags;
   the companies the industry exclusion removed.
7. `docs/method.md` has the new sections and the version log entry for 0.6; the stale call
   counts corrected.
8. `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
   passes.

## 16. Left to the builder

- Module layout: `vendors/limiter.py`; the classifier's two rules in `engine/classifier.py`;
  `engine/designation.py` beside `levels.py`; `route_start_up.py` and `route_decline.py` beside
  the route modules with a `runoff.py` core; `engine/distress.py` for the rating, Z″ and F; the
  backfill in `store/facts.py` or a `refresh/backfill.py`; the page work in `index.html`,
  `app.js`, `controls.js` and the vendored bundle under `// fairband:` markers.
- The exact drawer layout for the requirement, the run-off table, the rating and the two
  scores, within the design system; the optional columns (`requiredRevenue`, `burnCover`,
  `rating`, `altmanZ`, `piotroskiF`) in the chooser, off by default.
- How the trailing interest expense and depreciation enter `TrailingFigures`, and the per-year
  balance record.
- The limiter's log line in the run summary.

## 17. Order of work

1. The limiter, its tests, the policy comment and the docstrings. (No policy bump yet: the
   value can be read from v4's structure with a default until v5 lands, or v5 is cut first;
   the builder's call, stated in the plan.)
2. Policy v5, the method version, the universe exclusions, the classifier rules and flags.
3. The designation: engine, JSON, rows.py, the page, the drawer.
4. The sticky bar and the back-to-top control.
5. The normalizer fields, the backfill, the trailing figures.
6. The Decline route core on hand-built inputs (13.1), then the route: guards, intermediates,
   the rating, the floor, the weighting, the signals, the price refresh, the drawer.
7. The Start-up route (13.2), the price refresh, the drawer.
8. `docs/method.md`.
9. The revalue on the founder's database, a full refresh in one run, the readout.

## 18. Sources

- Damodaran, *The Corporate Life Cycle* (2024), ch. 2 s.20 (the duration test for decay); ch. 3
  (phases marked by direction, no thresholds); ch. 9 s.11 (what the market prices at each
  phase); ch. 13 s.9–10, 15 (the four responses to decline; declining firms "look cheap").
- Damodaran, "Valuing Distressed and Declining Companies" (2009): the Sears run-off (5% a year,
  divestitures recovering 54% to 67%); Table 5, bond rating and probability of default, 1971 to
  2007 (Altman); "Estimating Distress Sale Proceeds", choices (a), (b), (c); the Las Vegas Sands
  illustration (the earnings-power estimate and its cash and debt treatment).
- Damodaran, ratings.html (January 2026): the synthetic rating table for large non-financial
  firms.
- Damodaran, *Investment Valuation* ch. 12 and the blog "Myth 5.4" (negative growth forever;
  asset sales raise the terminal).
- Damodaran 2009, "Valuing Young, Start-up and Growth Companies" (Secure Mail: value from a
  market, a share and a margin; failure outside the discount rate).
- Altman (2000), the Z″ model and zones. Piotroski (2000), the F-score and its 0 to 1 and 8 to
  9 groups. Graham, net current asset value. Greenwald, EPV below asset value.
- The literature report, sections "Start-up and Young Growth", "Decline", "The engine needs one
  core, six input sets and three probabilities".
- design.md 6.1 (financials out of scope), 6.8 (Start-up: no tier-1 value, the requirement, a
  cash floor), 6.12 (Decline: the run-off, the higher of going concern and liquidation, π, the
  NCAV floor, the value-trap flag, Z″ and F).
- method v1.7 Step 10 (the fair band, the trim multiple, the margins of safety) for the
  designation edges.
- The founder's FMP plan (Ultimate, 3,000 calls a minute; memory 2026-11-01).

## Decision log

| Date | Decision |
|---|---|
| 2026-11-03 | The next work is the classifier fixes, then the Start-up and Decline routes; parametization and the settings surface come after. Founder. |
| 2026-11-03 | The FMP rate limiter is in scope. Founder ("please add the rate limiter to the scope"). |
| 2026-11-03 | The engine stops giving a stance; the agent decides it after research. A mechanical column designates the price against the fair value by the percentage difference, in bands, with Fairband's own words. Founder. |
| 2026-11-03 | The designation is the pure price ÷ value comparison; the moat and the margin of safety stay as the row's levels, figures for the agent. Founder ("agreed"). |
| 2026-11-03 | The table controls scroll with the table header; a control returns to the top. Founder. |
| 2026-11-03 | The spec is written from what was settled, without the brainstorm's questions. Founder. The calls marked *my call*: the limiter's rate and hold; the established test (three of five); the duration test (three of four); the six excluded industries; the designation edges (0.65 in place of the 0.70 mentioned); the run-off's same-year release; the recovery 0.6; the distress-sale fraction 0.6 (choice (a), not design.md's earnings-power form); BB+ as BB; π = 0 with net cash; the burn cover flag at 2 years; the requirement as year-10 revenue on a straight ramp. |
| 2026-11-03 | A manual admission list for payment companies that do not lend: Visa, Mastercard and Global Payments; American Express and PayPal lend and stay excluded. Founder. |
| 2026-11-03 | Two plans: method 0.6 for the limiter, the classifier, the designation and the controls; 0.7 for the routes; policy v5 for both. Claude's call at planning. |
| 2026-11-03 | After the builder check: the Decline margin is the five-year median (10.3) and the rating reads it (10.7), so a one-year loss does not refuse an established decliner; the π rules are ordered (net cash, no interest, D); the industry exclusions take effect at the full refresh (6.4); the backfill runs before every valuing refresh (11). Claude's calls. |
| 2026-11-03 | The 429 hold is capped at `rate_limit_hold_s` (the final review found an unbounded vendor value could hold every worker or overflow the clock). Claude's call. |

Builder check: done 2026-11-03 on Claude Opus 5.5; its three questions are settled in 10.3 and
10.7, 6.4 and 11. It recomputed the worked numbers of 13.1 and 13.2 from the formulas and they
matched.
