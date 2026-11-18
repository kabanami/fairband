# The company page: design

Status: written 2026-11-16 for backlog item B-215, plan 1, on the founder's requests of that day,
quoted in the decision log. The founder decided that there is a company page with tabs, what its
Overview and its Estimates tab show, that the data is FMP's and is stored by the refresh, that no
figure and no block names a vendor or carries a cite, the layout (version 3 of the mockup), the
drawer's new form (form A of the mockup), that a click on the ticker opens the page, the moat
stamp, the Notes control, and that no chart has a Table button, the report page's among them. Every
other choice below is Claude's, marked *my call* where it is more than a reading of those
requests, and can be overturned as any other. Plan 1 was built on the branch `company-page` on
2026-11-17; the decision log's entries of that day record where the build differs from this
design. It was merged to main and the live steps of section 17 ran on 2026-11-17, on the
founder's word; the readout is in the decision log, and after it the rulings the founder made on
his own look at the live pages the same day.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value: the method stays `fairband-mechanical/1.5` and the policy v16. The schema stays at
009: nothing new is stored but vendor responses, which have their table. The changes are in
`src/fairband/vendors/`, `src/fairband/refresh/`, `src/fairband/web/` and the documents.

## 1. What this is

Today a company is read in two places: the drawer beside the screen's table, and the report page.
Neither shows what a reader looks up first about a company: what it does, its price history, its
margins, its multiples, its news. The founder looks those up on fiscal.ai.

The company page is one page per company, with a row of tabs, in Fairband's own look. Plan 1
builds the page, its Overview tab and its Estimates tab, has the refresh fetch and store the FMP
data they show, makes the drawer a short card that leads to the page, and makes the ticker in the
screen's table a link to it. The later tabs (Financials, Investor relations, Research) are
backlog items B-216, B-217 and B-218, one plan each.

## 2. Goals

1. A reader opens any company of the screen and sees, on one page: the company's brief and
   facts, Fairband's value, about fifty statistics, five years of prices with volume, the price
   facts and the news.
2. The page opens from the store alone. The refresh fetched the data; opening a page calls no
   vendor, except for news older than a day (10.5).
3. Each tab's two columns end on one line at every desktop width (8.7, 9).
4. The drawer is a short card: the company, the value band, two buttons.
5. From the screen, one click on a ticker opens the company's page.

## 3. Non-goals

- The Financials, Investor relations and Research tabs (B-216, B-217, B-218), and ownership
  (B-71).
- A chart range longer than five years, chart indicators, a currency switch, the industry median
  of a ratio (B-219).
- A new home for what the drawer's Details listed (B-220).
- A tool for the agents. The page's reads carry no refs and are not MCP tools: an agent cites
  through the tools it has.
- Any figure Fairband computes anew, but for the two in 14.3.
- GuruFocus data on the page. The refresh's two GuruFocus calls stay as the engine reads them.

## 4. Anti-goals

- **A page of citations.** No figure and no block on the page names its vendor, carries a chip or
  a cite, or draws three dates. One data date stands on the page (7.4). The founder: "the whole
  page will be just citations. That is not practical." `CLAUDE.md` and the brand book's "What the
  rules cover" state the scope: the provenance rules cover Fairband's own values and writes.
- **The valuation's mechanics in front of the reader.** The drawer and the report page lose the
  sentences of what the price needs, and the drawer loses the route's name, the captions under
  its levels and Details. The founder: "These are internal about the mechanics of the valuation."
- **A vendor's opinion beside Fairband's value.** The price target, the ratings and the earnings
  against their estimates are on the Estimates tab, never on the Overview.
- **A page that waits on a vendor.** No block's first draw depends on a vendor call.
- **A failed page call that costs a valuation.** The new calls are optional: a company is valued
  on what the engine needs whether they come or not. A 429 is not such a failure: it stops the
  run, as today (10.1).
- **Red and green.** A change carries its sign and the text's own colour (brand book).

## 5. The evidence (probes of 2026-11-16, AAPL, the founder's Ultimate plan)

- The store holds, from every full or scoped refresh, FMP's `profile` (the brief, the CEO, the
  website, the employees, the IPO date, the beta, the average volume), `quote` (the open, the
  previous close, the day's and the year's range, the 50-day and 200-day averages, the volume,
  the change), `price-history` (1,255 daily rows, five years, with volume), `earnings` (12 rows,
  the next date among them) and `estimates-annual`.
- Nine FMP routes that Fairband does not call answered with HTTP 200 and one row or a list:
  `ratios-ttm`, `key-metrics-ttm`, `financial-growth`, `financial-scores`, `stock-price-change`,
  `price-target-consensus`, `grades-consensus`, `dividends`, `shares-float`. Section 8.3 names
  each field the page reads.
- FMP's three, five and ten-year growth figures are totals, not yearly rates:
  `tenYRevenueGrowthPerShare` read 2.314 for AAPL.
- `interestCoverageRatioTTM` read 0 for AAPL, a company that reports no interest expense line.
- Three foreign filers (TSM in TWD, NVO in DKK, ASML in EUR) showed which currency FMP states
  each money figure in; 14.2 holds the table. FMP's ratios read consistent for them: TSM's P/E
  22.5, its EV to sales 11.1 (EV 54.80T over revenue 4.94T, both in TWD).
- The owner has written no note from the page: the store's 16 notes are all agents'.
- The news pass-through's stored answer for 60 stories is 44 KB. One company's full refresh
  stores 449 KB in 15 FMP responses, 289 KB of it the price history.
- The full refresh of 14 November (refresh 60) made 15 FMP calls for each of 1,601 companies in
  13 minutes.
- The mockups: the Overview in three versions and the drawer in three forms, drawn with the
  app's own tokens, components and AAPL's data, checked in a headless browser at six widths and
  in both themes. Their sources are in `docs/superpowers/specs/2026-11-16-company-page-mockup/`
  (no data in them). The founder on version 3 of the Overview: "I love it, looks good."

## 6. Approaches

**The page.** (a) A new view of the one page the app is, named by the hash, as the report page
is. (b) A document of its own at `/company/AAPL`. (c) The report page grown into the company
page. Picked: (a), *my call*. The app's views share the header, the lists, the request button and
the drawer's parts through `window.FairbandPage`; (b) loads all of that twice or copies it; (c)
puts tabs around a reader that B-218 moves into a tab anyway.

**The data.** (a) The refresh stores each answer whole, and a read shapes the page's figures
from the newest stored answers. (b) The refresh normalizes each figure into the observations
table. (c) The page fetches through pass-throughs when it opens. The founder ruled out (c):
"store as much as possible in our data store so that we don't need to fetch this data
everytime." Picked: (a), *my call*. Nothing but the page reads these figures, the price history
and the peers are stored the same way today, and (b) writes about sixty rows a company at every
refresh for no reader.

**The chart.** (a) Drawn by the page in SVG with the tokens, as the mockup draws it. (b) A chart
library vendored into `static/vendor/`. Picked: (a), *my call*. The mockup's chart is the proof
that (a) is enough for a line, a volume plot, seven ranges and a hover; (b) is a dependency to
theme by hand and gives a pan and a zoom nobody asked for.

## 7. The page

### 7.1 The address

`#company/<symbol>` is the Overview. `#company/<symbol>/estimates` is the Estimates tab. The
symbol is encoded as the report page's links encode it and upper-cased on read. A tab the page
does not know is the Overview. `company` joins the views of `controls.js`, with its panel
`<section id="company" hidden>` and its script `company.js`; no header view names it, as none
names the report page. A change of tab replaces the hash, as a change of view does, and reads
only what the tab has not yet read. So the browser's Back leaves the company page for the place
the reader came from
and never steps through the tabs (*my call*: it is the app's rule for its views). The ticker's
link, the drawer's button and the Research tab are plain links, which add an entry: Back from
the report page returns to the company page's tab.

### 7.2 The head, on every tab

Left: the logo (the drawer's logo rule and ground, at 40px), the name, the ticker, the phase
badge, and one caption line, `NASDAQ · Technology · Consumer Electronics`. Right: the price in
`figure-lg`, the day's change and its percent with their sign, `close 13 Nov 2026`, then the
controls: Notes (11.1), the watchlists control and Request research.

- The moat stamp stands after the phase badge (the founder, 2026-11-16): `WIDE MOAT`, `NARROW
  MOAT` or `NO MOAT`. It is the moat class in force (method 4.9): the review's where a review
  counts, else the snapshot's, as the screen's row reads it (`rows.py`, `moat`). It is an
  outlined label in `ink-muted` with no fill and none of the phase colours, which mean the phase
  alone. A row with no value has no moat and no stamp. *My call* on its look and its words.
- The price and its date are the latest snapshot's, as the screen's row and the drawer read
  them. The change and its percent are the stored quote's (10.4).
- The watchlists control opens the popup the screen's mark opens, for this company.
- Request research is the report page's: its menu, its box, the open item's line under it and
  the following of a launch (`FairbandPage.asking`, `requestResearch`).
- A link back to the screen stands above the head, as on the report page.

### 7.3 The tabs

The mockup's row is Overview, Financials, Estimates, Investor relations, Research. Plan 1 shows
three (*my call*): **Overview**, **Estimates** and **Research**. Research is a link to the
report page (`#report/<symbol>`) until B-218 moves the reports into the tab. Financials and
Investor relations join the row with their plans: a tab with nothing behind it is a dead
control. The founder: "we have freedom to define the tabs as we like." Since the Investor
relations tab (decision log, 2026-11-18) the row holds the mockup's five in its order,
Overview, Financials, Estimates, Investor relations and Research, and wraps onto a second line
where the window cannot hold them on one.

### 7.4 The data date

One caption at the right end of the tabs' row: `data 14 Nov 2026`. It is the oldest day among
the stored answers the open tab draws (so it never claims more than the oldest block has),
without the news, whose stories carry their own days.

### 7.5 Loading and failure

- The head needs the company's detail (`GET /api/companies/{symbol}`). Without a snapshot the
  page shows the detail's sentence and the link back, as the report page does.
- While a read is out, the page shown stays, faded, as every view does. No spinner.
- A block whose answer the store lacks draws its rows with a dash. No block shows an error for a
  missing answer; the tab shows one sentence only when its read itself fails.

## 8. The Overview tab

Two columns. Left: Company, Fairband value, Key statistics. Right: Price, Price facts, News.

```
[logo] Apple Inc.  AAPL  [4 MATURE GROWTH] [NARROW MOAT]   $356.27  +$1.39 (+0.39%)  close 13 Nov 2026
NASDAQ · Technology · Consumer Electronics             [Notes 3] [Watchlists ▾] [Request research]
Overview | Estimates | Research                                              data 14 Nov 2026
+-----------------------------------------+-----------------------------------------+
| Company: brief, eight facts             | Price: ranges, close line, volume       |
| Fairband value: meter, four levels,     | Price facts: trading, price change,     |
|   the report's stance                   |   price change in years                 |
| Key statistics: seven groups in         | News: fills what is left; its list      |
|   three columns                         |   scrolls inside the panel              |
+-----------------------------------------+-----------------------------------------+
```

### 8.1 Company

The brief (`profile.description`), three lines with Show more and Show less. Under it, eight
facts in two columns: CEO (`ceo`), Website (`website`, shown without its scheme and `www.`,
opening in a new tab), Employees (`fullTimeEmployees`), Listed (`ipoDate`), Sector, Industry,
Country, Exchange.

### 8.2 Fairband value

The one block of Fairband's own figures, so the brand book's rules hold here: the basis chip
(mechanical or reviewed) in the block's head, and the meter as the drawer draws it
(`FairbandPage.meter`), the reviewed value where a review counts. Under the meter four levels in
the screen's words, in two columns: Fair value, Buy level, Fair band, Trim level. A refused row
shows its refusal's sentence in the meter's place, as the drawer does.

Where the company has a published report, one line under a rule: the stance chip (faded once
the report's window has ended, as today), the mode and the date, the principal chip, and a link
to the report page.

### 8.3 Key statistics

Seven groups in three columns. Each row is a name and a figure. The caption in the block's head:
`trailing twelve months, unless the row says`.

| Group | Row | FMP answer and field |
|---|---|---|
| Size | Market cap | `quote.marketCap` |
| | Enterprise value | `key-metrics-ttm.enterpriseValueTTM` |
| | Shares | `shares-float.outstandingShares` |
| | Free float | `shares-float.freeFloat`, a percent as given |
| | Revenue | `financial-scores.revenue` |
| | Employees | `profile.fullTimeEmployees` |
| | Beta | `profile.beta` |
| Margins | Gross, EBITDA, Operating, Pretax, Net | `ratios-ttm`: `grossProfitMarginTTM`, `ebitdaMarginTTM`, `operatingProfitMarginTTM`, `pretaxProfitMarginTTM`, `netProfitMarginTTM` |
| Returns | ROE, ROA, ROIC, ROCE | `key-metrics-ttm`: `returnOnEquityTTM`, `returnOnAssetsTTM`, `returnOnInvestedCapitalTTM`, `returnOnCapitalEmployedTTM` |
| Valuation | P/E, PEG, P/B, P/S, P/FCF | `ratios-ttm`: `priceToEarningsRatioTTM`, `priceToEarningsGrowthRatioTTM`, `priceToBookRatioTTM`, `priceToSalesRatioTTM`, `priceToFreeCashFlowRatioTTM` |
| | EV/Sales, EV/EBITDA, EV/FCF, Earnings yield, FCF yield | `key-metrics-ttm`: `evToSalesTTM`, `evToEBITDATTM`, `evToFreeCashFlowTTM`, `earningsYieldTTM`, `freeCashFlowYieldTTM` |
| Financial health | Debt to equity, Current ratio, Quick ratio, Interest cover | `ratios-ttm`: `debtToEquityRatioTTM`, `currentRatioTTM`, `quickRatioTTM`, `interestCoverageRatioTTM` |
| | Net debt to EBITDA | `key-metrics-ttm.netDebtToEBITDATTM` |
| | Altman Z, Piotroski | `financial-scores`: `altmanZScore`, `piotroskiScore` ("9 of 9") |
| Growth, fiscal 2026 | Revenue, EBITDA, EPS, Free cash flow | `financial-growth` (the newest fiscal year): `revenueGrowth`, `ebitdaGrowth`, `epsdilutedGrowth`, `freeCashFlowGrowth`; the group's title names its `fiscalYear` |
| Growth a year, per share | Revenue, Net income, Cash flow, Dividend, each over 3, 5 and 10 years | `financial-growth`: `threeY`, `fiveY` and `tenY` with `RevenueGrowthPerShare`, `NetIncomeGrowthPerShare`, `OperatingCFGrowthPerShare`, `DividendperShareGrowthPerShare`, each as a yearly rate (14.3) |
| Dividends | Yield, Payout, Dividend a share | `ratios-ttm`: `dividendYieldTTM`, `dividendPayoutRatioTTM`, `dividendPerShareTTM` |
| | Paid, Last payment | the newest row of `dividends`: `frequency`, `paymentDate` |

The first column holds Size, Margins and Returns; the second Valuation and Financial health; the
third the two Growth groups and Dividends.

FMP's ROIC is not the engine's return on capital, and the page does not set them side by side:
this block is the vendor's, and Fairband value is the engine's.

### 8.4 Price

The stored price history's daily closes, five years. Where the stored quote's day (10.4) is
later than the history's newest day, the read adds the quote's price and volume as that day's
row, so after a price refresh the chart ends on the head's price (*my call*). The price
changes and the statistics move with the next full or scoped refresh, and the data date says
so. The ranges 1M, 3M, 6M, YTD, 1Y, 3Y and 5Y stand in the block's head; 1Y is chosen when the
page opens. Above the plot, the newest close in `figure-lg` and
the change over the range with its percent and the range in words (`+$83.32 (+30.5%) past
year`).

Two plots on one time axis, each with one measure (`charts.md`: never two scales on one plot):
the close as a 2px line in `chart-1` with an end marker and the newest close in a tag on the
axis; under it the volume as bars in `chart-context`. Grid lines solid in `chart-grid`; ticks
bare, monospaced, in `ink-faint`; the first tick shown and each January name the year, and a
range over two years ticks by year. A tick the tag covers is left out. A hover draws a
crosshair and a small box with the day, the close and the volume; nothing animates.

The chart has no table and no Table button (the founder, 2026-11-16: "why do we need a table
button for every chart? I don't agree"). The hover box gives a day's exact figures. The design
system's rule that every chart has a table twin is withdrawn (`charts.md` in the archive, "A
table is optional"). The report page loses its Tables button too (13).

### 8.5 Price facts

Three groups side by side.

- **Trading**, from the stored quote's row: Open, Previous close, Day range, 52 weeks, 50-day
  average, 200-day average, Volume; Average volume from `profile.averageVolume`; Next earnings,
  the next earnings date by the rule the engine's reader has (the earliest date on or after
  today among the stored `earnings` rows with no actual EPS; `normalize_fmp_observations.py`),
  a dash without one.
- **Price change**, from `stock-price-change`: 1 day, 5 days, 1 month, 3 months, 6 months, Year
  to date (`1D`, `5D`, `1M`, `3M`, `6M`, `ytd`), percents as given.
- **Price change, years**: 1 year, 3 years, 5 years, 10 years (`1Y`, `3Y`, `5Y`, `10Y`).

### 8.6 News

The stored news, every story of it (60): the day, the title as a link that opens in a new tab,
the publisher under it. The count in the block's head (`60 stories`). No button.

### 8.7 The two columns end on one line

The left column sets the row's height. The right column takes that height and adds none of its
own, and News, its last block, fills what is left; the list scrolls inside the block, under a
floor of 260px. Below 1180px the page is one column, the right column's blocks after the left's,
and the news list scrolls under a height of 520px. The mockup's rule
(`.cp-col--match { height: 0; min-height: 100%; }`) held at six widths from 1,250 to 2,400
pixels. Inside a block, three columns become two under 700px of block width and one under 460px.

## 9. The Estimates tab

Two columns. Left: Earnings. Right: Analysts, then Consensus estimates.

The columns end on one line here too (the founder, 2026-11-16, on the first form, whose left
side was the longer): both take the row's height, and the last block of the shorter column
grows to it. Nothing scrolls; what is left over is blank at the foot of that block, 45px for
AAPL. The rule is the page's, for every tab but the Overview's news block, which has 8.7's.

- **Earnings.** In the head, the next date (8.5's rule) with `after the close` or `before the open` (FMP's
  `amc`, `bmo`) and `not confirmed` where FMP says so. A table: Reported, EPS, Estimate, Revenue,
  Estimate. Its first row is the next date with the two estimates; then every reported quarter
  the stored answer holds, newest first (eleven of its twelve rows today). From the stored
  `earnings` answer. No surprise column: Fairband would compute it.
- **Consensus estimates.** One row for each fiscal year after the newest year on file: Fiscal
  year, Revenue, EPS, EPS low, EPS high, Analysts (`revenueAvg`, `epsAvg`, `epsLow`, `epsHigh`,
  `numAnalystsEps`). From the newest stored `estimates-annual` answer, as stored.
- **Analysts.** In the head, `consensus Buy` (`grades-consensus.consensus`). Price target:
  Consensus, Median, Low, High (`price-target-consensus`). Ratings: five counts in a row, Strong
  buy, Buy, Hold, Sell, Strong sell. No marks on a track: the founder did not want them.

## 10. The data

### 10.1 The refresh's new calls

`fetch_company` gains ten calls, after the two GuruFocus calls, in this order:

| Endpoint as stored | FMP route | Params beside the symbol |
|---|---|---|
| `ratios-ttm` | `ratios-ttm` | none |
| `key-metrics-ttm` | `key-metrics-ttm` | none |
| `financial-growth` | `financial-growth` | `limit` 1 |
| `financial-scores` | `financial-scores` | none |
| `price-change` | `stock-price-change` | none |
| `price-target` | `price-target-consensus` | none |
| `grades` | `grades-consensus` | none |
| `dividends` | `dividends` | `limit` 4 |
| `shares-float` | `shares-float` | none |
| `news` | `news/stock` | `limit` 60 |

- Each is reused, called and stored as the fetch's other calls are: the reuse window, the force
  of a scoped refresh, the scrub of the keys, a `VendorError` stored as a row with its error, a
  429 stopping the fetch.
- **None is required.** A failure is logged and named in `FetchOutcome.failed`, and never sets
  `error`: the company is valued. The builder checks that the refresh's counts and the screen
  show no failed company for one.
- **A 429 on one of the ten is the run's rate-limit stop, as on any call.** The runner stays
  as it is (`run.py`): that one company takes the refusal "data fetch incomplete: rate
  limited", the run ends failed, and the next run reuses what is fresh and values it. *My
  call*: the run has stopped and is run again whatever that company's state, so a second path
  through the runner buys nothing.
- A payload is usable when it is a list, the empty list among them (a company with no dividend,
  no analyst or no news has none, and that answer is reused like any other); anything else is
  unusable, stored with its error and not reused. None gives a fact or an observation.
- `news` is stored under the pass-through's endpoint and params, so the refresh's copy and a
  pass-through's copy at the same limit reuse each other (the pass-through's key holds
  `limit`). The page reads at that limit, 60, a constant beside the fetch's other depths.
- The price refresh stays as it is: quotes only.
- The Fmp client gains one method a route, each returning the response as received.

### 10.2 The cost

- Calls: 25 FMP calls a company from 15. At 1,601 companies that is 40,025 calls from 24,015.
  The limiter's pace (2,850 a minute) alone needs 14 minutes for them; the last full refresh
  took 13 minutes for 24,015. My estimate is 20 minutes. The readout states the measured time.
- Bytes: about 54 KB more a company (the news 44 KB, the nine others about 10 KB), on 449 KB
  today: about 86 MB more at each full refresh, on about 720 MB.

### 10.3 The reads

Two reads, each from the store alone, each a plain GET with no vendor call:

- `GET /api/companies/{symbol}/page/overview`: the company's facts, the statistics by group,
  the trading rows, the price changes, the prices (`[day, close, volume]`, oldest first, the
  stored five years and the quote's day of 8.4), the news (`stories`, `observedAt`, `stale`) and `dataDate`.
- `GET /api/companies/{symbol}/page/estimates`: the earnings (the next date and the reported
  rows), the consensus by fiscal year, the price target, the ratings and `dataDate`.

Rules for both:

- Each figure is read from the newest stored HTTP 200 answer of its endpoint that has no error,
  whatever its age. A field the answer lacks, or holds as something other than a finite number
  where a number is read, is `null`. A figure's name in the answer is the page's own (camelCase),
  not FMP's.
- The server does the page's arithmetic (14.3), so the page draws what it is given.
- A symbol that is not one is a 400. A company with no stored profile is a 404, "no page data
  for <symbol>".
- The answers carry no refs. They are not MCP tools and no report cites them.
- The payload readers are pure functions, payload in and fields out, in a module of their own,
  as the normalizers are; the routes are in a module of their own (`web/company_api.py`).

### 10.4 The quote's row

The store keeps a quote's price, market cap and year range as observations; the open, the
previous close, the day's range, the averages, the volume and the change are in the payload
only, and a price refresh stores its quotes in batches under no symbol. So the trading rows and
the head's change read **the row for the symbol in the payload of the response that the
company's newest `quote` observation cites**. Every refresh that moves a snapshot's price stores
that quote, so the head's change and the snapshot's price agree. Where the row's price is not
the snapshot's price, the head draws no change (*my call*).

### 10.5 News older than a day

The overview read marks the news `stale` when its stored answer is older than the refresh's
reuse window (`reuse_hours`, 24) or when there is none. The page draws the stored stories at
once. Then, once for each opening of the page, it asks the pass-through that exists
(`GET /api/vendor/news/{symbol}?limit=60`, with the header a write carries), which fetches,
stores and answers, and the page draws its stories in the stored ones' place. Where that call
fails (no FMP key, the pass-throughs busy, the vendor's failure), the stored stories stay and
one caption in the block's head says `newer news did not load: <the server's sentence>`.

### 10.6 Links from vendor text

A story's address and the company's website come from the vendor. The page makes a link only of
an address whose scheme is `http` or `https`; anything else is drawn as text. Every such link
opens in a new tab with `rel="noopener noreferrer"`.

## 11. The drawer

Form A of the mockup. The bar at the top holds Notes (11.1) at its left and Close at its right.
Under it, in order:

1. The head as today: the logo, the ticker, the phase badge, the name, the currency line of a
   company not in US dollars. The moat stamp of 7.2 stands after the phase badge, by the same
   rule and in the same look (the founder, 2026-11-16: "yes I want it in the drawer as well").
2. One caption, the sector and the industry, then the brief in body text, six lines, cut with an
   ellipsis. The whole brief is on the company page.
3. The value band: the meter as today (the reviewed value where a review counts, a refused
   row's review or secondary band as today), then four levels in the screen's words: Fair value,
   Buy level, Fair band, Trim level. A refused row with no band shows its refusal's sentence.
4. Two buttons: **Company page**, primary, a link to `#company/<symbol>`, and **Request
   research**, with its menu and the open item's line as today.

What leaves the drawer: the sentences of what the price needs; the route's name; the caption
under the margin of safety and the `1.5 × value` label; the cross-check line and the lines of a
Young Growth and a Start-up row; the stance line, the report's Summary and Open the report (the
screen has its Stance column and the company page has the stance and the link); and Details
with all it listed. The page's code for those parts goes with them, but for what the report
page still uses through `FairbandPage`. The read `GET /api/companies/{symbol}/research` stays:
B-218 reads it.

Details also holds Add a note, the page's one way for the owner to write a note. It moves to
the Notes control (11.1).

B-220 asks where the inputs, the route's sections, the charge and the flags are shown after
this. Until it is answered they are on no page; the agents read them over MCP, and a report's
Appendix A lists the records.

### 11.1 Notes

The founder, 2026-11-16, on Add a note leaving with Details: a control for it in the drawer, and
not a third button; asked to choose between a word and a pencil mark: "Sure use Notes." (The
brand book has no icon set, and a control is named by a word.)

- **The control** is the word `Notes` in the quiet button's look, followed by the count of the
  company's notes when it has one or more (`Notes 3`). In the drawer it stands at the left of
  the top bar, Close staying at the right. On the company page it stands in the head, before the
  watchlists control.
- **The box.** A click opens a box under the control, in the frame of the watchlists popup: the
  company's notes, newest first, each with its day, its principal chip and its text, in a list
  that scrolls under 240px; `No notes yet.` without one. Under the list, Add a note as Details
  has it today, moved: its field, its button, the server's sentence under the field on a
  refusal, the text kept. Escape or a click outside closes the box; the draft stays until the
  drawer or the page shows another company.
- **The reads and the write** exist: `GET /api/companies/{symbol}/notes` when the box opens, and
  `POST /api/companies/{symbol}/notes` as the owner. A note taken is first in the list and the
  count follows. The company's detail gains `noteCount`, so the control draws its count without
  a read of its own (*my call*).
- B-218's Research tab will list the notes too; the control stays.

## 12. The ticker in the screen's table

The ticker's text in the Ticker cell is a link to `#company/<symbol>`, in the screen's table and
in a watchlist's. A click on it, or Enter on it, opens the page and does not open the drawer; a
click anywhere else on the row opens the drawer, as today; the watchlist mark keeps its own
click. The link is in the vendored `ScreenTable`, so it is a `fairband:` patch of `bundle.js`,
as the watchlist mark is: a prop gives the address for a row, and without the prop the cell is
as it was. `index.d.ts` documents the prop. The link reads as the ticker does and takes an
underline on hover and the focus ring on focus.

## 13. The report page

- It loses the sentences of what the price needs above its meter (*my call*: the founder named
  the drawer, and the same sentences lead this page's band).
- Its head gains a link to the company page (*my call*).
- It loses its Tables button (the founder, 2026-11-16: "it has a tables button that doesnt do
  anything. I think better to remove it from the reports page, no need for it"). The button,
  its state and the `tableView` it handed each chart go (`report.js`, `charts.js`), with their
  tests; the vendored components keep the prop, unset. The build does not look for why the
  button did nothing on the reports the founder opened: the control goes.
- Nothing else of it changes. B-218 moves it into the Research tab.

The engine still builds the sentences and the company's detail still carries `priceNeeds`: an
agent reads it through `company` and its report's valuation section leads with what the price
needs (the playbook, section 8). No page draws them.

## 14. Words and figures

### 14.1 Format

- Money: `$356.27`; large amounts compact, `$5.18T`, `$478.8B`, `39.1M`. A multiple: `39.3x`.
  A percent: one decimal, two for the dividend yield and the day's change. A count: grouped,
  `167,000`. A date: `13 Nov 2026`, monospaced.
- A missing figure is an em dash. So is a multiple or the interest cover at exactly 0.
- A change carries `+` or `−` and the text's own colour.
- Lower case for sentences; a group's title in `label`, upper case.

### 14.2 Currency

Every company of the universe lists in US dollars, and many report in another currency. FMP
states the page's money figures in one or the other, by answer (the probe of section 5):

| In US dollars | In the reporting currency |
|---|---|
| The price, its change, the chart, the trading rows (`quote`, `price-history`) | Enterprise value (`key-metrics-ttm`) |
| Market cap (`quote.marketCap`) | Revenue (`financial-scores`, which names its `reportedCurrency`) |
| The earnings' EPS and revenue, actual and estimate (`earnings`) | Dividend a share (`ratios-ttm.dividendPerShareTTM`) |
| The price target (`price-target-consensus`) | The consensus revenue and EPS (`estimates-annual`) |

The reads give each money figure its currency: USD for the left column, the company's reporting
currency for the right, as the engine reads it (`store.currency.reporting_currency`, the
detail's `currency`). A figure in US dollars is drawn with `$`; one in another currency with its
code in place of `$` (`TWD 4.94T`), as a report's figure is (method 16). For a company that
reports in US dollars nothing changes. Nothing is converted: Fairband would compute it.

So a foreign filer's Estimates tab shows its earnings in US dollars and its consensus in its own
currency, each as FMP states it; the code on the figure says which.

Per-share figures are per listed share (per ADS for a depositary receipt), as FMP gives them.

The founder's acceptance (17) opens five foreign filers. A figure there that does not fit the
table is reported in the readout.

### 14.3 The page's two computations

1. A yearly rate from FMP's total over n years: `(1 + total)^(1/n) − 1`; `null` where
   `1 + total` is not above zero. Done by the server.
2. The change over the chart's range: the newest close less the range's first close, and that
   over the first close. Done by the page, since the range is the reader's.

## 15. The documents

In the same commits as the code they describe:

- `docs/method.md` 4.11: the sentences are written for an agent's research; no page draws them.
- The Methodology page's paragraph on a price well above the value (`methodology.html`, the
  value section) says the same, and its pin in `tests/web/test_company_reads.py` follows.
- `docs/backlog.md`: B-215's plan 1 moves to Done at the end; B-197 moves with it (no reader of
  a page meets the sentence); the plan's deferred minors are filed.
- The module docstrings that list the fetch's calls and the views.
- This design's decision log: the readout and anything the build overturned.

The builder greps the documents and the playbook for the drawer's Details, the report's Summary
in the drawer and the fetch's count of calls, and corrects what the build makes untrue.

## 16. Tests the builder must write

Fixtures are synthetic or hand-trimmed: no vendor data is committed.

- **The fetch.** The ten calls, their stored endpoints and params, their order; reuse inside the
  window and force; a failed one named in `failed` with `error` still `None` and the company
  valued; a 429 on one stopping the fetch; an empty list usable and reused, an object unusable;
  `news` reused by the pass-through at limit 60 and the other way round.
- **The readers.** Each field of 8.3, 8.5 and 9 from a synthetic payload; a missing field, a
  string where a number is read, `NaN` and an empty list each `null`; the yearly rate, its
  refusal at a total of −1 or below; the quote's row found through the observation, in a single
  quote and in a batch.
- **The reads.** The two answers whole for a company with every answer stored; with none but
  the profile; the 400 and the 404; `stale` on either side of the window; `dataDate` as the
  oldest day; no vendor call made by either (a transport that fails any call); the quote's
  day added to the prices when it is the later, and not when it is not; each money figure's
  currency for a company that reports in another one; the next earnings date among two future
  rows and a past row without an actual.
- **The page**, in node with the harness the drawer's tests use: the head's parts, the moat
  stamp's three words, the review's moat over the snapshot's and no stamp on a refused row; the
  tabs and
  the hash both ways; each block's rows from a synthetic answer; the dash; the sign with no
  colour class; the chart's path, ticks, tag and hover box for a known series and each range;
  the link rule of 10.6 on `javascript:` and `data:` addresses; the stale
  news' second read and its failure's caption.
- **The drawer.** The four parts in order; the moat stamp by the head's rule; none of the parts
  that left; a refused row; a
  reviewed row; the two buttons and the Company page link's address.
- **Notes.** The control with no count and with one, in the drawer's bar and in the page's
  head; the box's list, newest first, and its empty line; a post, its place in the list and the
  count after it; a refusal's sentence with the text kept; Escape; the detail's `noteCount`.
- **The report page.** No Tables button; no chart is given `tableView`; the link to the
  company page.
- **The ticker.** The link's address; that its click does not call `onOpen`; that a click on the
  row does; that the cell without the prop is as before.
- **The sentences.** No page script names `priceNeeds`; the detail still carries it.

## 17. Acceptance

By the founder, on the live data, after the merge:

1. Back the database up, start the server from main, run a full refresh.
2. Open AAPL's page from the ticker in the screen's table. It matches version 3 of the mockup:
   the blocks, their order, the two columns ending on one line.
3. Open the Estimates tab, then Research. The browser's Back returns to the Estimates tab, and
   Back again to the screen.
4. Open a row's drawer: form A, and Company page opens the page.
5. Open the pages of five foreign filers (ASML, TSM, NVO, AZN, RELX) and of a company with no
   dividend and one with no report.

The readout, in this design's decision log: the full refresh's minutes against 13, the count of
failed page calls by endpoint, the database's growth, and what the five foreign filers showed.

## 18. Left to the builder

- The names of the modules, the functions and the CSS classes; the split of `company.js` if it
  grows past what one file reads well.
- How keyboard focus reaches the chart's days.
- Which of the drawer's functions in `app.js` are dead after section 11, and their tests.
- The answers' exact field names, so long as they are the page's own and one name means one
  figure.
- Whether the two reads share one module with the routes or the readers stand apart.

## 19. Order of work

1. The sentences of what the price needs leave the drawer and the report page, with the method
   document, the Methodology page and their pins.
2. The Fmp client's nine methods and the fetch's ten calls, optional.
3. The payload readers and the two reads.
4. The company view: the address, the head, the tabs, the data date, loading and failure.
5. The Overview's Company, Fairband value, Key statistics and Price facts.
6. The Overview's Price chart.
7. The Overview's News, the columns' rule and the stale news' read.
8. The Estimates tab.
9. The drawer's form A, the removal of what left it, and the Notes control with its box, in the
   drawer's bar and in the page's head.
10. The ticker's link, the report page's link and the removal of its Tables button.
11. The documents and the backlog.
12. The live steps and the readout.

## Decision log

- 2026-11-16, the founder: "I want to add new feature, a proper company page (rather than just
  a drawer and a report page), the company page needs to have multiple tabs", with a picture of
  fiscal.ai's company page.
- 2026-11-16, the founder: "let's start with what we have from our data sources, no need to
  compute new data. Moreover, let's start page by page starting with the overview page."
- 2026-11-16, the founder, on a vendor's name on each block: "I don't want each block names its
  vendor, the whole page will be just citations. That is not practical"; and on GuruFocus: "I
  don't want the GuruFocus view. I want to stick to FMP as much as possible."
- 2026-11-16, the founder: "the rule for each number having to have a citation is more for agent
  research to make sure that no numbers are invented, not for every number that exists on the
  fairband page"; and "Make sure that we store as much as possible in our data store so that we
  don't need to fetch this data everytime." `CLAUDE.md` and the brand book in the archive state
  the rule's scope since that day; B-221 carries the wording to the artifact.
- 2026-11-16, the founder, on the drawer's sentences of what the price needs: "remove the
  garbage written about the 'route charges growth...' ... These are internal about the mechanics
  of the valuation"; "there should be a button to research and a button for the company page.
  Also, once a user clicks on the ticker symbol on the screen, they should be able to go to the
  company page"; and that the removal is a task of the plan, not a change ahead of it.
- 2026-11-16, the founder, on the first mockup: "I like it a lot"; no marks for the price
  target; the tabs are not locked and an Ownership tab is in doubt ("I don't know what that
  means even"); and, asked whether the Overview is the place for earnings and analysts' figures,
  agreed to an Estimates tab in plan 1 ("yes, add the estimates tab to plan 1").
- 2026-11-16, the founder, on the drawer's three forms: "I like option A so you can lock that";
  on the Overview: "I don't like that the left side is shorter than the right side"; on version
  3, where the news fills the right column: "I love it, looks good."
- 2026-11-16, the founder, on the Estimates tab: "if we can also balance the Estimates tab as
  the left side is larger then the right side." Section 9: Earnings on the left, Analysts and
  Consensus estimates on the right, and the last block of the shorter column grows.
- 2026-11-16, the founder, after the mockups: "I am thinking of showing a moat designation stamp
  next to the phase stamp." In the page's head, 7.2; and, asked about the drawer: "yes I want it
  in the drawer as well", section 11.
- 2026-11-16, the founder, on the Table button this design gave the chart from the design
  system's rule: "why do we need a table button for every chart? I don't agree, and remove
  that from the design system." The button is out of 8.4, and `charts.md` in the archive says
  "A table is optional"; B-221 carries the wording to the artifact.
- 2026-11-16, the builder check (a fresh agent read this document against the code). Answered
  from the code or a probe: the next earnings date is the soonest, not the newest row (8.5);
  the currency of each money figure, from three foreign filers (14.2); the acceptance's section
  number. Settled as Claude's calls: a 429 on a page call is the run's stop and the runner
  stays (10.1); a tab replaces the hash, so Back leaves the page (7.1); the chart ends on the
  stored quote after a price refresh (8.4). It also found that Add a note would leave with
  Details; the founder then asked for the Notes control (11.1).
- 2026-11-16, the founder, on a control for notes in the drawer ("Maybe not a button as it
  would be too many buttons") and on the word against a pencil mark: "Sure use Notes." And on
  the report page's Tables button: "it has a tables button that doesnt do anything. I think
  better to remove it from the reports page, no need for it." Sections 11.1 and 13.
- 2026-11-16, Claude's calls, each marked in its section: a view named by the hash; answers
  stored whole and shaped at read; the chart drawn by the page; three tabs shown in plan 1, with
  Research a link to the report page; the ten calls optional and last in the fetch; news read
  again through the pass-through when older than a day; the quote's row found through the
  observation; the yearly rate computed by the server; the report page losing the sentences too
  and gaining a link to the company page; a link only of an `http` or `https` address.
- 2026-11-17, the build, Claude's call (10.3): both page reads carry a top-level `quote`,
  `{price, change, changePercent, day}`, for the head, since the head is on every tab; the
  overview's `trading` holds the eight money rows, the two volumes and the next earnings date.
- 2026-11-17, the build, Claude's call (8.3, 10.3): `Last payment` is the latest payment date on
  or before the day of the read, never a date still to come; the reader takes that day as an
  argument.
- 2026-11-17, the build, Claude's call (9): the consensus rows are cut at the newest fiscal year's
  end plus the engine's drift of a 52/53-week year's end (`inputs_statements.YEAR_END_DRIFT`,
  seven days), so a reported year whose estimate row is dated a few days after its end is not
  drawn as a consensus year.
- 2026-11-17, the build, Claude's call (8.3): the Key statistics list eight groups; "seven
  groups" in sections 8 and 8.3 and in the plan was a miscount. With no fiscal year in the answer
  the growth group's title is `Growth, last fiscal year`.
- 2026-11-17, the build, Claude's call (14.1): money is written as the design system writes an
  amount (`Fairband.formatMoney`), with no thousands separator, in every currency, so the page
  agrees with the meter, the drawer and the screen; a count is grouped (`167,000`). The rule that
  a date is monospaced covers a date drawn as a figure (a row's value, a column's cell); a date
  inside a caption's words (`close 13 Nov 2026`, `data 14 Nov 2026`) keeps the caption's face, as
  in the mockup the founder approved. A fiscal year is a row's name, in body type.
- 2026-11-17, the build, Claude's call (4, 14.1): a growth rate and a yearly rate are rates, not
  changes: no sign when positive, the minus when negative, as the mockup draws them. The sign
  rule covers the price's change: the head's, the chart's lead and the Price change groups.
- 2026-11-17, the build, Claude's call (7.2): the stamp shows the moat in force, the counting
  review's where it has a value, else the snapshot's. The clause "as the screen's row reads it"
  was wrong: the screen's row reads the snapshot's moat alone, so the stamp and the screen's Moat
  column can differ once a review changes the moat.
- 2026-11-17, the build, Claude's call (7.5): the company page reads again when a refresh ends
  while it shows, as the report page does. A detail read that fails for a reason other than a 404
  draws the tab's failure sentence; a 404 draws the server's own.
- 2026-11-17, the build, Claude's call (7.2): the head's watchlists button is disabled until the
  page knows the company's memberships (the screen's row, or the loaded lists), so the popup can
  never replace them with one list.
- 2026-11-17, the build, Claude's call (10.1): the pass-through's `news` kind stores an answer
  that is not a list as unusable, as the fetch does, since the two share a key at sixty stories.
  `fetch.page_params(endpoint, symbol)` gives the params the fetch stores for a page endpoint.
- 2026-11-17, the build, Claude's call (10.5): where the news pass-through answers with a payload
  that is not a list, or with a body that is not JSON, the stored stories stay and the note reads
  `newer news did not load: the answer held no stories`.
- 2026-11-17, the build, Claude's call (8.4): the chart is keyed on the company, so each company
  opens at 1Y; the year-to-date range includes 31 December of the year before, as the mockup's
  filter does; the x ticks are thinned counting from January, so that each January shows.
- 2026-11-17, the build, Claude's call (8.2): the basis chip is `reviewed` exactly where the
  meter draws a review's or a secondary valuation's band (`bandBasis`), and the four levels come
  from one builder the drawer shares (`levelRows`). A refused row whose review or secondary
  valuation gives a band draws that band and no refusal sentence, on the page and in the drawer.
- 2026-11-17, the build, Claude's call (11.1): `notesControl(symbol, count, after)` takes the read
  to run again after a note is taken. The line `on override N` that Details drew after a note's
  chip is not drawn in the box: its words are in neither the Words table nor this section.
- 2026-11-17, the build, Claude's call (11): the drawer's `Company page` button is the default
  size, as Request research beside it is. The code of the drawer's removed parts is in git at
  commit 6da1b0f, for whoever answers B-220.
- 2026-11-17, the build, Claude's call (13): the `Company page` link stands at the right end of
  the report page's head, after its figures.
- 2026-11-17, the build, Claude's call (12): Space on the focused ticker link is not stopped, as
  the section names Enter alone, so it opens the drawer as Space on the row does.
- 2026-11-17, the build, Claude's call: the plan
  (`docs/superpowers/plans/2026-11-16-company-page-plan.md`) is not rewritten. Its Task 4 and
  Task 5 blocks give the shapes as planned; this log gives them as built.
- 2026-11-17, the whole-branch review (8.7, goal 3): the rule as designed worked in one
  direction only. The right column took the row's height and added none of its own, so the left
  column set the row; where the left column was the shorter, as on a refused company with no
  meter and no levels, the right column ran 70px past the row at a width of 1,600. The built rule
  holds both ways: the row is as tall as the taller column, and the news list has no height of
  its own, so its stories never size the row. Where the left column is the taller, News fills
  what is left and its list scrolls inside it; where the right column's least height (the chart,
  Price facts and News at its floor of 260px) is the greater, the left column's last block, Key
  statistics, grows to the row, blank at its foot, and News stands at its floor.
- 2026-11-17, the build, the controller's sentence (11.1): a failed read of the notes draws
  `The notes did not load: <message>. Open Notes again to retry.` in the list's place, a sentence
  the Words table lacked.
- 2026-11-17, the whole-branch review, Claude's call (8.3, 8.7): inside a block, three columns
  become two under 810px of block width, not 700px, and the table `Growth a year, per share`
  draws its rates in `figure-sm`. Just above 700px a column is about 215px wide, and the table
  with its rates in `figure` needs about 245px with negative rates (8px past its column at a
  width of 1,600) and 272px with `−134.4%` in every cell; in `figure-sm` it needs 247px, which
  each of three columns has from 810px. Three columns stand from a window about 1,750px wide;
  below it Key statistics and Price facts stand in two. A word or a name in a list (a Company
  fact, Paid) wraps inside its half of the row, so a long industry
  (`Drug Manufacturers - Specialty & Generic`) stays in its list; a figure stays on one line.
- 2026-11-17, the whole-branch review, Claude's call (8.4): the year-to-date range starts at the
  last close of the year before, the last row dated before 1 January of the newest row's year,
  or at that year's first row where there is none, so it starts at Friday 30 December when 31
  December is a Saturday, and its change is over the close that FMP's year to date in Price facts
  is over. This replaces the entry above that has the range include 31 December as the mockup's
  filter does.
- 2026-11-17, the fix wave's follow-up, Claude's call (8.3, 8.5, 8.7): the three columns from
  810px (above) made two inner columns the form of Key statistics and Price facts at every common
  width, from a window of 1,180 to about 1,750px, where the third column's groups wrapped under
  the first and left the block's right half blank: about 540px in Key statistics, 250px in Price
  facts. In the two-column form (460px to under 810px of block width) Key statistics' third stack
  spans both columns and lays its groups out in them, Growth beside the yearly rates a share,
  which span two rows, and Dividends under Growth; Price facts' Trading spans two rows beside
  Price change and Price change, years, one under the other. The halves end about 160px apart in
  Key statistics and 65px in Price facts; each column keeps its order of reading, Size first and
  Valuation at the top of the second. The three-column and one-column forms are unchanged.
- 2026-11-17, the readout of the live steps (17), run by Claude on the founder's "option 1"
  (merge to main, with the backup, the restart, the full refresh and the push named to him):
  - The steps. The live database was backed up by SQLite's backup to
    `fairband-before-company-page-2026-11-17.db` (6,465,626,112 bytes, quick check ok). Main was
    fast-forwarded to the branch (4,306 tests passed on that commit), and the server on 8470 was
    started from main, down about ten seconds. No migration: the schema stays at 9.
  - The full refresh, 66: 18.5 minutes against 13.1 for the last full refresh (60, on 14 Nov), so
    5.4 minutes more. It stored 39,242 answers, 25.0 a company, against 23,843 (15.1 a company).
    1,569 companies were admitted (1,581 in refresh 60, on three days of newer data), 1,371
    valued, 198 refused and 1 failed, the same one as in refresh 60
    (`data fetch failed: income-annual, balance-annual, cashflow-annual`). No call answered 429.
  - Failed page calls by endpoint: none. Each of the ten page endpoints stored an answer for all
    1,569 companies, the failed one among them, and none was stored as unusable.
  - The database's growth: from 6,465,626,112 to 7,622,893,568 bytes, 1.16 GB for the refresh.
    Its stored answers are 705.9 MB (660.1 MB in refresh 60), of which the ten page endpoints are
    64.0 MB: the news 49.9 MB, `ratios-ttm` 4.8, `financial-growth` 3.4, `key-metrics-ttm` 3.1,
    `dividends` 1.0 and the other five 1.7 together. That is 40.8 KB a company, under 10.2's
    estimate of 54 KB (the news 31.8 KB against 44 KB).
  - AAPL from the ticker in the screen's table (a headless browser on the live server, a window of
    1,600px): the head with the phase badge and the moat stamp, the tabs Overview, Estimates and
    Research with `data 17 Nov 2026`, the blocks in the design's order, and the two columns ending
    on one line on both tabs. Research opened the report page; Back returned to the Estimates tab
    and Back again to the screen. The row's drawer is form A, and its Company page opened the
    page. No page error and no failed request on any page opened.
  - The five foreign filers (ASML, TSM, NVO, AZN, RELX). On each: the head's price in US dollars,
    the ADR's quote; Market cap in US dollars; Enterprise value and Revenue in the reporting
    currency with its code (ASML `EUR 497.5B` and `EUR 39.47B`, TSM `TWD 54.67T` and `TWD 4.94T`,
    NVO `DKK 1.35T` and `DKK 333.7B`, RELX `GBP 61.87B` and `GBP 9.72B`; AZN reports in US
    dollars and carries no code); the dividend a share in the reporting currency (NVO
    `DKK 11.70`); on the Estimates tab the earnings in US dollars, as FMP gives the ADR's, the
    consensus by fiscal year in the reporting currency with its code, and the price target in US
    dollars. The value block drew the review's band and the report's line for ASML, TSM, NVO and
    RELX and the mechanical band with the report's line for AZN. The columns ended on one line on
    both tabs and nothing overflowed. One figure of the vendor's reads oddly and is drawn as
    given: RELX's consensus price target, $26.00 beside a price of $40.44.
  - A company with no dividend (AMZN): Yield `0.00%`, Payout `0.0%`, Dividend a share `$0.00`,
    Paid and Last payment a dash. A company with no report (VLTO): the mechanical band and the
    four levels, and no report line.
- 2026-11-17, after the founder's look at the live page ("it looks very good, a couple of small
  edits"), four rulings of his, built the same day:
  - The line of the last refresh and its Details ▾, under the header (7.1 drew the page under it):
    "why not remove the text below the header on the engine run along with its details button? we
    already have info in the header on the right hand side, having this distracts". The company page
    and the report page, each a page of one company, draw neither: both describe the whole universe,
    and the header's stamp says when the engine ran. The Screen and the other views of many
    companies keep them. *My call*: a refresh that runs still draws its bar on those two pages, and
    a notice its sentence, since the header has neither; so does the line of a run that did not end
    done (failed, cancelled or interrupted), since the header's stamp is that run's finish too and
    would read as a fresh run over figures it did not renew (the review of the change found it); the
    status region stays, empty, so a run that starts is announced; a bar that draws nothing takes no
    room; Details ▾ left open is shut as a view opens.
  - The link back to the screen (7.2, 7.5; the report page's own, at its foot): "why do we have a
    back to the screen link? we already have the screen link in the header". Neither page draws it.
    The header's Screen view is the way back, and the browser's Back returns to the view left. A
    failed read of the detail draws its sentence alone.
  - A finder in the header: "why not have the search bar again in this page, Let's say I am on a
    company page now, and wanted to go to another company page?". *My call* on its form: a field in
    the header's right slot, before the refresh controls, on every view but the Screen, whose table
    has a field of its own (two fields with the same words on one view would confuse). It matches as
    the Screen's field does, a ticker that starts with the text or a name that holds it, on the rows
    the page already holds, so it asks the server nothing, and lists eight at most: the ticker that
    is the text, then the tickers that start with it, the names that start with it and the names
    that hold it, the larger company first within each. The arrow keys move the mark, Enter opens
    the marked company's page, Escape empties the field, and a pick sets the hash, so the browser's
    Back returns to the view left. The page of another company opens at its top, not at the depth
    the reader left on the one before (the review found it: the panel stays shown from one company
    to the next). With nothing found, and before the rows are in, the list says so in one row. The
    field is 220px and alone gives way, down to 96px, where the one-line header is tight; under
    1,100px of window, where the header has no room for it beside the six views, the refresh
    controls and the stamp, it is not drawn (B-235).
  - The moat stamp keeps its form, an outlined label with no colour (7.2). The founder asked whether
    it should carry a colour code, as a strip does in a deck of his; a mockup showed four forms (as
    now; one blue in three strengths; the same in grey; teal, yellow and terracotta), and Claude
    advised against the three colours, which on these pages already mean the buy zone, phase 4 and
    the trim zone. The founder: "keep as is, no strip".
- 2026-11-17, the Financials tab (B-216): designed in
  `docs/superpowers/specs/2026-11-17-financials-tab-design.md` and built on the branch
  `worktree-financials-tab`, which was merged to main the same day. 7.3's row of tabs now holds
  Financials, second: Overview, Financials, Estimates and Research.
- 2026-11-18, the Research tab (B-218): designed in
  `docs/superpowers/specs/2026-11-17-research-tab-design.md`, built, and merged to main and
  live on 2026-11-18 (`bc18aad`). The report page is the company page's Research tab
  since that design: 7.3's Research is a tab of the row, no longer a link to `#report/<symbol>`,
  which opens the tab on the same report, and section 13's report page left, its references, its
  appendixes and its charts drawn in the tab.
- 2026-11-18, the Investor relations tab (B-217): designed in
  `docs/superpowers/specs/2026-11-18-investor-relations-tab-design.md` and built on the branch
  `worktree-investor-relations-tab` on 2026-11-18, not yet merged. What it changes of this
  design: 7.3's row holds five tabs, Investor relations fourth, and wraps where the window
  cannot hold them on one line; the data date of 7.4 may be a tab's script's own
  (`companyPage.dataDate`), as the Investor relations tab's two views each count their own
  answers; and two reads of that tab may call a vendor, each behind the request header: a call's
  transcript as the reader first shows the call, the newest as soon as the Earnings calls view
  opens on it, where the store holds no copy of the call with words; and an older year of
  filings on a press of Show older filings. The tab's first draw is its own read of the store,
  which waits on neither, so the anti-goal "No block's first draw depends on a vendor call"
  (section 4) still holds.
