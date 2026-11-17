# The company page's Financials tab: design

Status: written 2026-11-17 for backlog item B-216, on the founder's requests of that day, quoted
in the decision log. The founder decided what the tab shows (the three statements by fiscal year
and by quarter, the revenue by product and by region, the ratios by fiscal year, a chart of the
lines the reader picks over one wide table), that a ratio draws as a line, that one chart holds
several lines, that the amounts read in millions or in billions, and the look (version 3 of the
mockup: "its right, proceed"). Every other choice below is Claude's, marked *my call* where it
is more than a reading of those requests, and can be overturned as any other. The plan was
built on the branch `worktree-financials-tab` on 2026-11-17; the decision log's entry of that
day on the build records where the build differs from this design. It was merged to main and
the live steps of section 14 ran on 2026-11-17, on the founder's word; the readout is the
decision log's last entry.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value: the method stays `fairband-mechanical/1.5` and the policy v16. The schema stays at
009: nothing new is stored but vendor responses, which have their table. The changes are in
`src/fairband/vendors/`, `src/fairband/refresh/`, `src/fairband/web/`, the design system's
tokens and chart rules, and the documents, `docs/method.md`'s sentence on what a refresh fetches
for the page among them (section 10).

This design stands on the company page's (`2026-11-16-company-page-design.md`, "the page's
design" below). Its rules hold here unless this document says otherwise: the address and the
tabs (7.1, 7.3), the data date (7.4), loading and failure (7.5), the refresh's page calls
(10.1), the reads (10.3), the currency (14.2), no cite and no vendor's name on a figure (4).

## 1. What this is

The company page has an Overview and an Estimates tab. A reader who wants a company's history
(its revenue over ten years, its margins, its buybacks, its debt) has no page for it: the report
page draws six tables for the companies that have a report, and nothing else does.

The Financials tab is one wide block on the company page. At its top a chart of the lines the
reader picks; under it one table a sub-tab: the income statement, the balance sheet, the cash
flow statement, the segments and the ratios. Every figure is FMP's, stored by the refresh.

## 2. Goals

1. A reader opens any company's Financials tab and reads its three statements over eleven fiscal
   years and eight quarters, its revenue by product and by region, and about forty ratios by
   fiscal year.
2. A press on a line charts it. A press on a line's `+` adds it, so up to four lines stand on
   one chart, lines of different sub-tabs among them.
3. The tab opens from the store alone: the refresh fetched the data.
4. The amounts read in millions or in billions, as the reader chose last.

## 3. Non-goals

- A trailing-twelve-months column, year-on-year change rows, a common-size view (each line as a
  percent of revenue). The founder agreed to leave the first two out of the first version.
- Ratios and segments by quarter. FMP holds them; they are two more calls a company each
  (section 8).
- The six financial tables of the report page (`reports/tables.py`: growth, cash flow, solvency,
  returns, capital allocation, quality). They are Fairband's computations for a report and stay
  there. *My call*: the founder asked for the vendor's data as it is, FMP first.
- The statements as reported (FMP's `as-reported` routes), restatement marks, estimates as
  columns after the newest year.
- More than eleven years, a range control on the chart, a comparison of two companies, an export.
- A tool for the agents. The read carries no refs and is not an MCP tool; the agents keep their
  `financials`, `quarters`, `financial_tables` and `segments` tools.

## 4. Anti-goals

- **A figure Fairband computes.** No total of the segments, no margin worked out by the page, no
  sum of four quarters. A figure is FMP's field, shaped and never recomputed. Scaling an amount
  to millions is format, not computation.
- **Two scales on one plot.** A money line and a ratio never share a plot (`charts.md`: "the
  alignment between them is arbitrary and invents a correlation the data does not contain").
- **Colour that judges.** A series colour says which line it is, never that a figure is good or
  bad. No red and green.
- **A page of citations, a page that waits on a vendor, a failed page call that costs a
  valuation**: the page's design, section 4.

## 5. The evidence (probes of 2026-11-17, AAPL, the founder's Ultimate plan)

- The store holds, from every full or scoped refresh, the six statements whole: the income
  statement (39 fields a period), the balance sheet (61) and the cash flow statement (47), each
  for 11 fiscal years and 8 quarters. Each row names its `date` (the period's end), its
  `fiscalYear`, its `period` (`FY`, `Q1` to `Q4`) and its `reportedCurrency`.
- FMP writes 0 where it holds no figure for a line: AAPL's interest income and interest expense
  read 0 for 2024 to 2026.
- `ratios` and `key-metrics` with `period=annual` and `limit=11` answered with eleven rows each:
  66 and 47 fields a row, 31 KB and 20 KB. Their fields are the Overview's (the page's design,
  8.3) without the `TTM` at the end: `grossProfitMargin` beside `grossProfitMarginTTM`. A margin
  or a return is a fraction (0.4879).
- The segments are a pass-through today, fetched on request and stored under
  `segments-product` and `segments-geographic` (`refresh/passthrough.py`). The store holds them
  for 31 companies. AAPL's answers hold 17 fiscal years, a row a year with a `data` object of
  name and revenue: 4 KB and 5 KB. FMP's names are the company's own (`Americas Segment`,
  `Wearables, Home and Accessories`).
- Some companies' answers change currency from one period to the next (the builder check's
  read of the store, 2026-11-17): 23 companies in their annual statements (CRH in EUR to 2019
  and in USD from 2020; DEO in GBP to 2023), about 11 in their quarterly ones, and ASML's
  segment answers name USD for 2014 to 2024 and EUR for 2025.
- For 30 companies FMP's quarterly rows are half-years, named `Q2` and `Q4` (UL, BHP, RIO, BTI,
  DEO, RELX). The engine reads them as half-years (`inputs_statements.cadence_of`).
- A segment answer can end before the statements do (NVS's in fiscal 2022 against 2025) and can
  miss years (RELX's product rows are 2017, then 2023 to 2025). It gives `fiscalYear` as a
  number where a statement gives a text.
- The full refresh of 17 November (refresh 66) made 25 FMP calls for each of 1,569 companies in
  18.5 minutes and grew the database by 1.16 GB.
- The mockup, in three versions, drawn with the app's tokens and AAPL's data, checked in a
  headless browser at desktop and phone width and in both themes. Its sources are in
  `docs/superpowers/specs/2026-11-17-financials-tab-mockup/` (no data in them). The founder on
  version 1: "It looks really nice"; on version 2: "I looks excellent"; on version 3: "its
  right, proceed".
- The four series colours of section 7.6 were found by a search over OKLCH and measured with
  the chart skill's validator: every pair of the four is at least 11.8 apart in dark and 10.6 in
  light under simulated protan and deutan sight (OKLab ΔE × 100; the target is 8), at least 21
  apart under full sight (the floor is 15), and each is 3:1 or more on `surface-raised`.

## 6. Approaches

**The data.** (a) The refresh stores the four new answers whole, and one read shapes the tab's
tables from the newest stored answers, the six statements among them. (b) The tab reads the
reads that exist (`/financials`, `/quarters`, `/financial-tables`) and the segments
pass-through. (c) The tab fetches the ratios when it opens. Picked: (a), *my call*. It is the
page's rule (its design, 6 and 10.3), and the founder ruled (c) out for the page: "store as much
as possible in our data store". (b)'s reads are the agents': they answer the fields the engine
stores as facts, each with a ref, and not FMP's whole statement; the segments pass-through
calls the vendor.

**The chart.** (a) Drawn by the page in SVG with the tokens, as the Overview's price chart is.
(b) The design system's `HistoryBars` and `SpreadChart`. (c) A chart library. Picked: (a), *my
call*. (b) draws one measure in one hue and has no form for several lines the reader picks; (c)
is a dependency to theme by hand.

**Several lines.** (a) Lines of one unit share a plot, and each other unit takes a plot of its
own under it, on the same periods. (b) One plot with two scales, as other tools draw revenue
against margin. (c) One small plot a line, side by side, each in the one series hue. Picked:
(a). The founder judged it on version 2 of the mockup. (b) is the anti-goal of section 4. (c)
keeps the brand book as it is but cannot show three margins against one another, which is the
first thing a reader does with them.

## 7. The tab

### 7.1 The address and the row

`#company/<symbol>/financials`. The tabs' row reads Overview, **Financials**, Estimates,
Research, the mockup's order. The sub-tab, the period and the picked lines are not in the
address (*my call*: the app's views name a view, not its state).

### 7.2 The block

One panel, the page's full width, in this order:

1. A row of controls. Left: the sub-tabs, **Income statement**, **Balance sheet**, **Cash
   flow**, **Segments**, **Ratios**. Right: **Millions** and **Billions**, then **Annual** and
   **Quarterly**. Each is a segmented control of the mockup's form.
2. The chart (7.5).
3. Two captions on one line. Left, what the table holds: `the last 11 fiscal years`, `the last 8
   quarters` (the counts are the table's own), `by fiscal year, as the company reports its
   segments`, or `by fiscal year; the same definitions as Key statistics on the Overview`.
   Right: `press a line to chart it alone, or its + to add it to the chart`.
4. The table (7.3). Segments has two, each under its title: `Revenue by product` and `Revenue
   by region`.

- **Annual and Quarterly** show on the three statements and are hidden on Segments and Ratios,
  which are by fiscal year only. Opening Segments or Ratios sets the period to Annual (*my
  call*: the chart and the table always show one period). For a company that reports twice a
  year the second word is **Half-yearly** (7.9).
- **Millions and Billions** show on every sub-tab but Ratios, no row of which is an amount.
- The sub-tab and the period are kept while the app is open, from one company to the next. The
  unit is kept in the browser (`localStorage`, read and written inside a `try`, as the screen's
  columns are): a browser that keeps nothing shows Millions. *My call* on all three.

### 7.3 The table

- One column a period, oldest at the left, newest at the right. A column's head is the period
  (`2026`, or `Q4 2026`) over the day and month its period ends (`26 Sep`), as FMP dates it.
- The first column holds the lines' names and stays in place while the table scrolls sideways
  inside the block. Its head is a caption that states the unit: `USD, millions, except per
  share` on the income statement, `USD, millions` on the balance sheet, the cash flow statement
  and Segments, `as each row says; per share in USD` on Ratios; `billions` under Billions; the
  company's reporting currency in place of `USD` (7.7).
- The lines, their order, their names and their kinds are section 12's lists. A kind is a
  **total** (bold), a **line**, a **sub-line** (indented under the line above it) or a **section
  head** (a label in upper case across the row, with no figures and no press).
- **A line with no figure in any column of its table is left out**, a figure of exactly 0
  counting as none (section 5: FMP writes 0 for a line it does not hold). A section head with no
  line left under it is left out too. So the annual table may hold a line that the quarterly
  table lacks.
- A table with no line (a company with no segments on file, a statement the store lacks) draws
  one sentence in its place: `No figures on file.`
- Each row but a section head holds a small button before its name: `+` while the line is off
  the chart, the line's colour swatch while it is on it. A row on the chart carries the selected
  ground and a 2px bar of its colour at its left edge.

### 7.4 Picking lines

- **A press on a row** (a click, or Enter or Space on the focused row) charts that line alone.
- **A press on a row's button** adds the line to the chart, or takes it off when it is on it.
  The last line on the chart cannot be taken off.
- The chart holds **four lines** at most. At four, the `+` of every other row is disabled, with
  the title `The chart holds 4 lines. Take one off first.`
- The lines on the chart stay when the reader changes sub-tab or period, so a statement's line
  and a ratio can stand together. They also stay when the reader leaves the tab for another tab
  of the same company and comes back. They do not stay from one company to the next: a company's
  tab opens on **Revenue** alone (*my call*; a company whose income statement has no Revenue
  line opens on the first line of the table). The lines kept are those of the company whose
  Financials tab was drawn last: they go when another company's Financials tab is drawn, and
  not when the reader only looks at another company's other tabs.
- A line is known by its sub-tab, its table and its key (section 9), so `Net income` of the
  income statement and of the cash flow statement are two lines.

### 7.5 The chart

**Its head.** With one line: the line's name, its newest figure in `figure-lg`, and a caption
with the newest period and the unit (`2026, USD, millions`). With two or more: one label a
line, each a swatch, the name, the newest figure and a `×` that takes the line off; after them
the caption `figures for 2026`. The labels are the chart's legend (`charts.md`: a legend with
two or more series, none with one). A swatch is a square for bars and a round dot for a line.

**A line's name on the chart** is its name in the table, but: a ratio of the Margins group
adds `margin` (`Gross margin`), one of Per share adds `a share` (`Revenue a share`), one of
Dividends leads with `Dividend` (`Dividend yield`), and a segment leads with `Revenue:`
(`Revenue: iPhone`).

**The form follows the unit** (the founder, 2026-11-17, on ratios as lines):

| Unit | Lines | Form |
|---|---|---|
| Money, per share, share count | the statements' lines, the segments, the ratios' Per share group | bars from a zero baseline |
| Percent, multiple, plain ratio, days | every other ratio | a 2px line with an end marker, on an axis that fits the figures' range |

**Periods.** The chart stands on every period that a drawn line's table holds: the union of
their columns, known by their labels, in order of the day each ends. So the chart does not
depend on the order of the picks, and a ratio and a statement's line meet on the fiscal year. A
line with no figure for a period draws no mark there (a segment answer that ends before the
statements do, or that misses years). The head's newest period is the union's newest; a line
with no figure for it shows a dash in its label. *My call.*

**Plots.** The lines of one unit share one plot and one scale. Each other unit takes a plot of
its own under it, in the order the units were picked. Every plot stands on the same periods,
and the periods' labels stand once, under the last plot. With two or more lines, each plot
states its unit at its top left (`USD, millions`, `percent`, `multiple`, `ratio`, `days`, `USD a
share`, `millions of shares`). A plot is 160px high alone, 120px each of two, 100px each of
three, 90px each of four.

**Scales.** A bar plot's scale holds zero; a line plot's fits its figures and holds zero only
where they cross it. Four clean steps (three in a plot under 150px), the ticks at the right,
bare and compact (`400B`, `50M`, `35%`, `40x`), the zero line in `border`, the others in
`chart-grid`, solid.

**Marks.** Bars: 4px rounded at the data end, square at the baseline, a 2px gap between
neighbours; two to four bars of one period stand side by side in the lines' order. One line's
bar is at most 44px wide and never over 72% of its period's width; a bar among several is at
most 28px (the mockup's widths; `chart-bar-max`, 24px, stays `HistoryBars`'s, and 7.6's section
of `charts.md` states this chart's own). One line
alone draws its bars in `chart-1` and a figure below zero in `chart-neg-3`, the brand book's
polarity; with two or more lines every bar wears its line's colour, above zero and below. A
period with no figure, an amount of exactly 0, or a figure in another currency than the tab's
(7.9) draws no mark; a line breaks there.

**Hover and keys.** The pointer over the chart picks the period under it. One line alone: a
small box over the mark, `2024 · 391,035`, the other bars faded. Two or more: a box beside the
period with the period, then a row a line (its swatch, its name, its figure); a crosshair runs
through every plot where a line is drawn; each line's point takes a marker. The chart takes the
keyboard's focus: the left and right arrows move a period, Home and End go to the ends, Escape
and a loss of focus clear the box. Nothing animates.

**By quarter.** Ratios and segments have no figures by quarter. Under Quarterly such a line
stays among the labels, faded, with `by year only` in the place of its figure, and draws
nothing. A statement's line that the quarterly table lacks reads `no figures by quarter`. Where
no line can draw, the plot's place holds: `These lines have figures by fiscal year only. Choose
Annual, or press a line in the table.`

No table toggle, no chip and no cite (the page's design, 4 and 8.4).

### 7.6 Colours, and the brand book

The brand book has one series hue: "there is no chart in Fairband where four series are equally
the point" (`charts.md`). This chart is that chart: the reader picks the lines, and none is the
subject. So the design system gains three tokens beside `chart-1`, and `charts.md` a section
for them. The values are *my call*, the mockup's:

| Token | Dark | Light | Reads as |
|---|---|---|---|
| `chart-1` (as it is, the accent) | `#4bc0b0` | `#0f7a6e` | teal |
| `chart-2` | `#437dde` | `#1b3d9c` | blue |
| `chart-3` | `#f3c530` | `#b5820c` | yellow |
| `chart-4` | `#c05296` | `#c562b2` | magenta |

Rules, for `charts.md`:

- The four are for a chart whose lines the reader picks, the Financials tab's alone today.
  Every other chart keeps one hue and `chart-context`.
- A line takes the lowest token that is free when it is picked and keeps it until it leaves the
  chart: taking one line off never repaints the others. When one line is left it takes
  `chart-1`.
- Never a fifth colour: the chart holds four lines.
- Text never wears a series colour; the swatch beside it does.
- None of the four is a `phase-*`, `caution` or `critical` value. `chart-3` is a yellow near
  `caution`; it is a mark in a plot, never a status.
- This chart spans the page, so its bars are wider than `chart-bar-max`: 44px at most for one
  line, 28px at most among several (7.5).

The tokens go into `tokens.json` (the archive's and the vendored copy under
`static/design-system/tokens/`), `tokens.css` is built from it (`build_tokens.py`), and the
archive's `charts.md` takes the section. The design system's artifact does not have them until
it is synced (B-221 gains a line).

### 7.7 Words and figures

- **An amount** is drawn in the unit chosen: in millions grouped with no decimal (`478,834`),
  with one decimal where the table's largest amount is under 1,000 million (*my call*, so a
  small company's lines do not all read 0 or 3); in billions with two decimals (`478.83`). A
  **share count** follows the same switch. A figure below zero leads with `−`.
- **Per share**: two decimals, no sign of the currency (the caption names it). **Percent**: one
  decimal (`33.0%`), two for the dividend yield, as the Overview draws it. **Multiple**: one decimal and `x`. **Plain ratio** (debt to equity, the
  current ratio, PEG): two decimals. **Days**: no decimal.
- **A dash** stands for a figure the answer lacks, an amount or a share count of exactly 0, and
  a multiple of exactly 0 (the page's design, 14.1).
- **Currency.** The statements, the segments and the per-share ratios are in the company's
  reporting currency, as FMP states them (each row's `reportedCurrency`). The captions and the
  plots' units name it: `TWD, millions`. Nothing is converted. The multiples and the yields are
  FMP's own. A company whose answers change currency: 7.9.
- One data date stands at the right end of the tabs' row (the page's design, 7.4): the oldest
  day among the stored answers the tab draws.

### 7.8 Width

The block is one column at every width. The table scrolls sideways inside it, the first column
in place. Under 700px the first column narrows to 168px and a long name wraps. The controls'
row wraps. The chart redraws at the block's width; a period's label is left out where the
labels would touch (every second, or every third, from the newest back).

### 7.9 A change of currency, and half-years

Both are *my call*; the builder check found the companies (section 5).

**A change of currency.** The tab has one currency: the newest annual income statement row's
(8.3). Every caption and every plot of amounts names it. A column whose row names another
currency carries that code as a third line of its head (`2019`, `31 Dec`, `EUR`), and its
figures stand in the table as FMP gives them, unconverted. The chart draws no mark for an
amount or a per-share figure of such a column, so no scale ever mixes two currencies; the hover
box writes that figure with its code before it (`EUR 25,129`). Share counts, percents,
multiples, plain ratios and days are drawn whatever the column's currency.

**Half-years.** Where the company reports twice a year, by the engine's rule on the period ends
of its quarterly income statement (`inputs_statements.cadence_of`, `half-yearly`), the three
quarterly tables are its half-years: the switch reads **Half-yearly**, the caption `the last 8
half-years` (the count is the table's own), and a column whose FMP period is `Q2` is labelled
`H1 2026`, one whose period is `Q4` `H2 2026`. Any other period keeps FMP's name. Every other
company, one whose cadence the rule cannot tell among them, reads Quarterly.

## 8. The data

### 8.1 The refresh's new calls

`fetch_company` gains four calls, after the page's ten, in this order. They join
`PAGE_ENDPOINTS`, so every rule of the page's ten holds for them (its design, 10.1): reused
while fresh, forced by a scoped refresh, stored whole, usable when the payload is a list (the
empty list among them), not required, a 429 stopping the fetch.

| Endpoint as stored | FMP route | Params beside the symbol |
|---|---|---|
| `ratios-annual` | `ratios` | `period` annual, `limit` 11 |
| `key-metrics-annual` | `key-metrics` | `period` annual, `limit` 11 |
| `segments-product` | `revenue-product-segmentation` | none |
| `segments-geographic` | `revenue-geographic-segmentation` | none |

- The limit is `STATEMENT_YEARS`, so the ratios cover the statements' years. `page_params`
  gives the two their `period` and `limit`.
- The two segment answers are stored under the pass-through's endpoints and params
  (`{"symbol": ...}`), so the refresh's copy and the pass-through's reuse each other, as the
  news does. The agents' `segments` tool then answers from the refresh's copy while it is fresh.
- So the two must agree on what a usable answer is. The segments pass-through stores any JSON
  today; it gains the check the news pass-through has (`usable=_is_list`): FMP's error object is
  stored with its error and is not reused by either.
- The Fmp client gains `ratios(symbol, limit)` and `key_metrics(symbol, limit)`; it has the two
  segment methods.

### 8.2 The cost

- Calls: 29 FMP calls a company from 25. At 1,569 companies that is 6,276 more. Refresh 66 made
  39,225 calls in 18.5 minutes; my estimate is 21 to 22 minutes. The readout states the
  measured time.
- Bytes: about 60 KB more a company (the ratios 31 KB, the key metrics 20 KB, the segments 9
  KB): about 94 MB more at each full refresh, on 1.16 GB.

### 8.3 The read

`GET /api/companies/{symbol}/page/financials`, from the store alone, a plain GET with no vendor
call, beside the page's two reads in `web/company_api.py` and under their rules (the page's
design, 10.3): each answer is the newest stored HTTP 200 answer of its endpoint with no error,
whatever its age; a 400 for a symbol that is not one; a 404, `no page data for <symbol>`, for a
company with no stored profile; no refs.

It draws ten stored answers: the six statements, the two of the ratios, the two segment
answers. It answers:

```
{symbol, dataDate, quote, currency,
 statements: {income: {annual: T, quarter: T}, balance: {...}, cashflow: {...}},
 segments: {product: T, region: T},
 ratios: T}
```

`quote` is the head's, as on the page's two reads. `currency` is the reporting currency of the
newest annual income statement row (`reportedCurrency`), else the company's as the other reads
find it. The answer also holds `cadence`, `quarterly` or `half-yearly` (7.9). A table `T` is
`{columns, rows}`:

- `columns`: oldest first, each `{label, end, currency}`: `"2026"`, `"Q4 2026"` or `"H2 2026"`
  (the row's `period` and `fiscalYear`, by 7.9), the period's end as an ISO day, and the row's
  `reportedCurrency`, the tab's where the row names none. A label is a text whatever the answer
  gives (a segment answer's `fiscalYear` is a number), so one fiscal year has one label in every
  table. A statement's columns are the rows of its
  stored answer, put in order by `date`. An answer the store lacks gives a table with no column
  and no row.
- `rows`: in section 12's order, each `{key, label, name, kind, unit, values}`. `key` is the
  page's own name for the line, one name a line in its table. `label` is its name in the table,
  `name` its name on the chart (7.5). `kind` is `total`, `line`, `sub` or `head`. `unit` is
  `money`, `perShare`, `shares`, `percent`, `multiple`, `ratio` or `days`. `values` holds one
  figure a column: a finite number as FMP gives it (an amount in units of the currency, not in
  millions; a percent as a fraction), else `null`. A `head` has no `unit` and no `values`.
- The read leaves out what 7.3 leaves out: a line with no figure but `null` and 0 in its table,
  and a head with no line under it.

**The ratios** join the two answers by the row's `date`: a column a date, the newest eleven,
oldest first; a field of an answer with no row for that date is `null`.

**The segments.** A column a fiscal year, the newest eleven of the answer, oldest first. A line
a name that holds a figure in those years; its `key` is the name. The lines stand by the newest
year's revenue, largest first, a line with none there after them by its largest figure. The
names are FMP's, unchanged.

The readers are pure functions beside the page's others (`vendors/page_fmp.py`, or a module of
its own beside it), payload in and table out. The lists of section 12 live there, once: FMP's
field, the key, the label, the kind or the unit. The page draws what it is given and holds no
list of lines (*my call*: one list sets the order, the words and the tests).

## 9. The page's code

- `company.js` gains the tab in its row and reads `page/financials` as it reads the other two;
  `controls.js` knows the tab's name (`COMPANY_TABS`).
  A tab's function hangs on `companyPage.draw` as the Overview's and the Estimates' do.
- The tab's state (the sub-tab, the period, the unit, the picked lines) is the tab's script's.
  The picks are dropped when another company's answer lands.
- The table and the chart are drawn with `React.createElement`, the chart in SVG with the
  tokens, as `company_chart.js` draws the price chart.
- What a pick holds: the sub-tab, the table (`product` or `region` on Segments), the row's
  `key` and its colour slot. A line's figure for a period is found by the column's `label`
  (7.5).

## 10. The documents

In the same commits as the code they describe:

- The design system: `charts.md` gains the section of 7.6 and loses nothing; `tokens.json` and
  `tokens.css` gain the three tokens, in the archive
  (`docs/design-system/fairband-design-system_4.tar.gz`) and in the vendored copy. `chart-1`'s
  usage text in `tokens.json` names the exception.
- `docs/backlog.md`: B-216 moves to Done at the end; B-221 gains the line of 7.6; the rows this
  design leaves open are filed (section 3's non-goals that the founder may want next: the
  ratios and the segments by quarter, the trailing twelve months, the year-on-year rows).
- `docs/method.md`, section 10: the full refresh's sentence that counts and names the FMP
  answers only the company page shows (ten, `fetch.PAGE_ENDPOINTS`) counts fourteen. No method
  version moves, and the Methodology page does not change.
- The module docstrings that count the fetch's calls and list the page's reads and tabs
  (`fetch.py`, `run.py`, `passthrough.py`, `company_api.py`, `page_fmp.py`, `company.js`,
  `controls.js`).
- The page's design: one line in its decision log that the Financials tab is built, and where.
- This design's decision log: the readout and anything the build overturned.

## 11. Tests the builder must write

Fixtures are synthetic or hand-trimmed: no vendor data is committed.

- **The fetch.** The four calls, their stored endpoints and params, their place after the ten;
  reuse inside the window and force; a failed one named in `failed` with `error` still `None`
  and the company valued; a 429 on one stopping the fetch; an empty list usable and reused, an
  object unusable; a segment answer reused by the pass-through and the other way round, and
  FMP's error object stored with its error by the pass-through and reused by neither.
- **The readers.** A statement's table from a synthetic payload: the columns' order and labels
  by year and by quarter, each kind, each unit, a line of zeros and `null`s left out, a head
  left out with its lines, a text or `NaN` where a number is read as `null`. The ratios' join
  on two answers whose dates differ by a year, and with one answer missing. The segments' order,
  the newest eleven of seventeen years, a name that appears in one year only, a `fiscalYear`
  given as a number. A column's currency where a row names another one. The cadence and the
  `H1` and `H2` labels for rows that end half a year apart, and FMP's labels for rows that end
  a quarter apart. A payload of the wrong shape reads as an empty table and never raises.
- **The read.** The answer whole for a company with every answer stored; with none but the
  profile; the 400 and the 404; `dataDate` as the oldest day of the ten; `currency` for a
  company that reports in another one; no vendor call made (a transport that fails any call).
- **The tab**, in node with the harness the page's tests use: the tab in the row and the hash
  both ways; the controls by sub-tab (the period hidden on Segments and Ratios, the unit hidden
  on Ratios, the period set to Annual on opening one of the two); each table's rows from a
  synthetic answer, the kinds' classes, the caption's unit and currency, the sentence of an
  empty table; the code in the head of a column in another currency; `Half-yearly` and its
  caption for a half-year reporter; a figure's text in millions, in billions and under the
  small-company rule, the
  dash's three cases; the unit kept across a reload (a stub store) and Millions where the store
  throws.
- **Picking.** A press on a row alone; add and take off; the last line kept; the fourth line
  and the disabled `+`; the lowest free colour slot, a line's slot kept when another leaves, and
  `chart-1` for the one left; the picks kept across sub-tabs and dropped for another company.
- **The chart.** For known series: bars for an amount and a line for a rate; one plot a unit in
  pick order and the plots' heights; a bar scale that holds zero and a line scale that does not;
  the ticks' texts; no mark for `null` and for an amount of 0; a figure below zero in
  `chart-neg-3` alone and in its series colour among others; the head with one line and with
  three; a line's name on the chart for each rule of 7.5; the hover box's text with one line and
  with several, and the arrow keys' steps; the periods as the union of two tables' columns in
  either pick order, and no mark where a line has no figure; no mark, and the code in the hover
  box, for a figure in another currency; the bars' widths; a ratio's label and no plot under
  Quarterly, and the
  sentence where nothing draws.
- **The tokens.** The three tokens in both themes in the vendored `tokens.css`, equal to the
  archive's; the page's CSS names no colour of its own for a series.

## 12. The lines

FMP's field, then the line's name. **Bold** is a total; `·` leads a sub-line; a line in upper
case is a section head. The key is the builder's, one a line.

### 12.1 Income statement (`income-annual`, `income-quarter`)

| FMP field | Line | Unit |
|---|---|---|
| `revenue` | **Revenue** | money |
| `costOfRevenue` | Cost of revenue | money |
| `grossProfit` | **Gross profit** | money |
| `researchAndDevelopmentExpenses` | Research and development | money |
| `sellingGeneralAndAdministrativeExpenses` | Selling, general and administrative | money |
| `generalAndAdministrativeExpenses` | · General and administrative | money |
| `sellingAndMarketingExpenses` | · Selling and marketing | money |
| `otherExpenses` | Other expenses | money |
| `operatingExpenses` | Operating expenses | money |
| `operatingIncome` | **Operating income** | money |
| `interestIncome` | Interest income | money |
| `interestExpense` | Interest expense | money |
| `totalOtherIncomeExpensesNet` | Other income, net | money |
| `incomeBeforeTax` | **Income before tax** | money |
| `incomeTaxExpense` | Income tax | money |
| `netIncome` | **Net income** | money |
| | PER SHARE | |
| `eps` | EPS | per share |
| `epsDiluted` | EPS, diluted | per share |
| `weightedAverageShsOut` | Shares | share count |
| `weightedAverageShsOutDil` | Shares, diluted | share count |
| | OTHER | |
| `ebitda` | EBITDA | money |
| `depreciationAndAmortization` | Depreciation and amortization | money |

### 12.2 Balance sheet (`balance-annual`, `balance-quarter`)

| FMP field | Line |
|---|---|
| | ASSETS |
| `cashAndCashEquivalents` | Cash and equivalents |
| `shortTermInvestments` | Short-term investments |
| `netReceivables` | Receivables |
| `inventory` | Inventory |
| `prepaids` | Prepaids |
| `otherCurrentAssets` | Other current assets |
| `totalCurrentAssets` | **Total current assets** |
| `propertyPlantEquipmentNet` | Property, plant and equipment |
| `goodwill` | Goodwill |
| `intangibleAssets` | Intangible assets |
| `longTermInvestments` | Long-term investments |
| `taxAssets` | Tax assets |
| `otherNonCurrentAssets` | Other non-current assets |
| `totalNonCurrentAssets` | **Total non-current assets** |
| `totalAssets` | **Total assets** |
| | LIABILITIES |
| `accountPayables` | Accounts payable |
| `accruedExpenses` | Accrued expenses |
| `shortTermDebt` | Short-term debt |
| `capitalLeaseObligationsCurrent` | Lease obligations, current |
| `taxPayables` | Tax payables |
| `deferredRevenue` | Deferred revenue |
| `otherCurrentLiabilities` | Other current liabilities |
| `totalCurrentLiabilities` | **Total current liabilities** |
| `longTermDebt` | Long-term debt |
| `capitalLeaseObligationsNonCurrent` | Lease obligations, non-current |
| `deferredRevenueNonCurrent` | Deferred revenue, non-current |
| `deferredTaxLiabilitiesNonCurrent` | Deferred tax liabilities |
| `otherNonCurrentLiabilities` | Other non-current liabilities |
| `totalNonCurrentLiabilities` | **Total non-current liabilities** |
| `totalLiabilities` | **Total liabilities** |
| | EQUITY |
| `commonStock` | Common stock |
| `additionalPaidInCapital` | Additional paid-in capital |
| `retainedEarnings` | Retained earnings |
| `accumulatedOtherComprehensiveIncomeLoss` | Accumulated other comprehensive income |
| `treasuryStock` | Treasury stock |
| `totalStockholdersEquity` | **Total stockholders' equity** |
| `minorityInterest` | Minority interest |
| `totalLiabilitiesAndTotalEquity` | **Total liabilities and equity** |
| | OTHER |
| `totalInvestments` | Total investments |
| `totalDebt` | Total debt |
| `netDebt` | Net debt |

Every line is money.

### 12.3 Cash flow statement (`cashflow-annual`, `cashflow-quarter`)

| FMP field | Line |
|---|---|
| | OPERATING |
| `netIncome` | Net income |
| `depreciationAndAmortization` | Depreciation and amortization |
| `deferredIncomeTax` | Deferred income tax |
| `stockBasedCompensation` | Stock-based compensation |
| `changeInWorkingCapital` | Change in working capital |
| `accountsReceivables` | · Receivables |
| `inventory` | · Inventory |
| `accountsPayables` | · Payables |
| `otherWorkingCapital` | · Other working capital |
| `otherNonCashItems` | Other non-cash items |
| `netCashProvidedByOperatingActivities` | **Cash from operations** |
| | INVESTING |
| `investmentsInPropertyPlantAndEquipment` | Capital expenditure |
| `acquisitionsNet` | Acquisitions, net |
| `purchasesOfInvestments` | Purchases of investments |
| `salesMaturitiesOfInvestments` | Sales and maturities of investments |
| `otherInvestingActivities` | Other investing |
| `netCashProvidedByInvestingActivities` | **Cash from investing** |
| | FINANCING |
| `netDebtIssuance` | Debt issued, net |
| `commonStockIssuance` | Stock issued |
| `commonStockRepurchased` | Stock repurchased |
| `netDividendsPaid` | Dividends paid |
| `otherFinancingActivities` | Other financing |
| `netCashProvidedByFinancingActivities` | **Cash from financing** |
| | CASH |
| `effectOfForexChangesOnCash` | Effect of exchange rates |
| `netChangeInCash` | **Net change in cash** |
| `cashAtBeginningOfPeriod` | Cash at the start |
| `cashAtEndOfPeriod` | Cash at the end |
| | OTHER |
| `freeCashFlow` | **Free cash flow** |
| `incomeTaxesPaid` | Income taxes paid |
| `interestPaid` | Interest paid |

Every line is money, with FMP's sign: a payment is below zero.

### 12.4 Ratios (`ratios-annual`: R; `key-metrics-annual`: K)

| Group | Line | FMP field | Unit |
|---|---|---|---|
| MARGINS | Gross, EBITDA, Operating, Pretax, Net | R: `grossProfitMargin`, `ebitdaMargin`, `operatingProfitMargin`, `pretaxProfitMargin`, `netProfitMargin` | percent |
| RETURNS | ROE, ROA, ROIC, ROCE | K: `returnOnEquity`, `returnOnAssets`, `returnOnInvestedCapital`, `returnOnCapitalEmployed` | percent |
| VALUATION | P/E, P/B, P/S, P/FCF | R: `priceToEarningsRatio`, `priceToBookRatio`, `priceToSalesRatio`, `priceToFreeCashFlowRatio` | multiple |
| | PEG (after P/E) | R: `priceToEarningsGrowthRatio` | plain ratio |
| | EV/Sales, EV/EBITDA, EV/FCF | K: `evToSales`, `evToEBITDA`, `evToFreeCashFlow` | multiple |
| | Earnings yield, FCF yield | K: `earningsYield`, `freeCashFlowYield` | percent |
| FINANCIAL HEALTH | Debt to equity | R: `debtToEquityRatio` | plain ratio |
| | Net debt to EBITDA | K: `netDebtToEBITDA` | plain ratio |
| | Current ratio, Quick ratio | R: `currentRatio`, `quickRatio` | plain ratio |
| | Interest cover | R: `interestCoverageRatio` | multiple |
| PER SHARE | Revenue, Net income, Free cash flow, Book value, Dividend | R: `revenuePerShare`, `netIncomePerShare`, `freeCashFlowPerShare`, `bookValuePerShare`, `dividendPerShare` | per share |
| DIVIDENDS | Yield, Payout | R: `dividendYield`, `dividendPayoutRatio` | percent |
| EFFICIENCY | Days of sales outstanding, Days of inventory, Days of payables, Cash conversion cycle | K: `daysOfSalesOutstanding`, `daysOfInventoryOutstanding`, `daysOfPayablesOutstanding`, `cashConversionCycle` | days |
| | Capital expenditure to revenue, Research and development to revenue, Stock pay to revenue | K: `capexToRevenue`, `researchAndDevelopementToRevenue` (FMP's spelling), `stockBasedCompensationToRevenue` | percent |

The groups and the names are the Overview's Key statistics where it has them (the page's
design, 8.3), so a ratio by year and its trailing figure read as one thing. Per share and
Efficiency are the tab's own. The Overview's Altman Z, Piotroski and growth rows have no yearly
answer here and are not in the table.

## 13. Where the design and the mockup differ

The design is right. The mockup:

- shapes the tables in a build script and holds amounts in millions; the product shapes them in
  the read and holds amounts as FMP gives them (8.3);
- opens on three lines as an example; the tab opens on Revenue alone (7.4);
- has no PEG row (12.4 adds it, *my call*, for the Overview's sake);
- draws a 1px stub for an amount of exactly 0; the tab draws no mark (7.5);
- adds a line on a click with Ctrl or Cmd held; the tab does not (*my call*: the `+` is the one
  way, and it is in sight);
- writes amounts with no decimal for every company (7.7's rule for a small company is new);
- names its colours `--series-1` to `--series-4`; they are `chart-1` to `chart-4` (7.6);
- heads the Ratios table `as each row says`; the tab adds `; per share in <currency>` (7.3,
  the whole-branch review's ruling).

## 14. Acceptance

By the founder, on the live data, after the merge:

1. Back the database up, start the server from main (Python changes), run a full refresh, which
   stores the four new answers for every company.
2. Open AAPL's page and its Financials tab. It matches version 3 of the mockup: the sub-tabs,
   the two switches, the chart, the table.
3. Put Revenue, Net income and Operating margin on one chart; open Quarterly; switch to
   Billions and reload the page.
4. Open the Financials tab of three foreign filers (TSM, ASML, NVO), of a company with no
   segments on file, of one whose statements have another shape (a bank or an insurer, if the
   universe holds one), of one that changed currency (CRH, DEO) and of one that reports twice a
   year (RELX, UL).

The readout, in this design's decision log: the full refresh's minutes against 18.5, the count
of failed calls among the four by endpoint, the database's growth, how many companies have no
segments, and what the foreign filers showed (the currency of the per-share lines above all).
Reuse is judged an endpoint at a time, so a full refresh inside the reuse window of the last one
makes only the four new calls a company, and again any call whose last answer failed. The
readout says which it measured: a whole refresh, or the four calls alone.

## 15. Left to the builder

- The names of the modules, the functions, the keys and the CSS classes; the split of the tab's
  script (the table, the chart) if one file reads badly.
- Whether the readers join `page_fmp.py` or stand in a module beside it.
- The exact words of an `aria-label`, so long as each button and the chart names what it does.
- How the chart's periods thin on a narrow block, within 7.8.
- The decimals of an axis tick, within "clean numbers, compact from a thousand up" (`charts.md`).

## 16. Order of work

1. The Fmp client's two methods and the fetch's four calls, optional, with the segments' reuse.
2. The readers of section 12 and the read.
3. The tab: its address and its place in the row, the controls, the tables, the unit and the
   period.
4. The chart of one line: bars or a line by unit, the head, the hover box and the keys.
5. Several lines: the `+`, the labels, the plots by unit, the colours; the tokens and
   `charts.md`.
6. The documents and the backlog.
7. The live steps and the readout.

## Decision log

- 2026-11-17, the founder: "Let's tackle financials, first advise on what we should show here."
  Claude advised: the three statements by year and by quarter, the segments, the ratios by
  fiscal year from FMP under the Overview's definitions, a bar chart of the pressed line over
  one wide table; no trailing-twelve-months column and no year-on-year rows in the first
  version; four more FMP calls a company. The founder: "Sure agreed, show me a mock up on a
  public url please".
- 2026-11-17, the founder, on version 1 of the mockup: "It looks really nice, but a couple of
  questions, first, should ratio's be line graphs rather than bar graphs? Second, is there an
  easy way to add multiple line items and ratios etc. in one graph?" Claude: yes to both; lines
  of one unit on one plot, another unit on a plot of its own under it, never two scales; four
  lines at most; three new series colours, which the brand book does not have.
- 2026-11-17, the founder, on version 2: "I looks excellent. One more request, we need to have
  millions and billions unit options, is that possible?"
- 2026-11-17, the founder, on version 3, with the switch: "its right, proceed".
- 2026-11-17, the builder check (a fresh reader of this design and the store, on Opus 5.5).
  It found three cases the design did not cover and Claude ruled on each, for the founder to
  overturn: a company whose answers change currency (7.9: the code on the column, no mark on
  the chart, nothing converted); the periods of a chart whose lines come from tables with
  different columns (7.5: the union); a company that reports twice a year (7.9: half-years by
  the engine's rule). It also found: the mockup's bars are wider than `chart-bar-max` (7.5 and
  7.6 state this chart's widths); `docs/method.md` counts the page's answers (section 10); the
  segments pass-through stores any JSON, which the refresh would reuse (8.1); the Overview
  draws the dividend yield to two decimals (7.7); `controls.js`, `page_params` and `run.py`
  name what changes (8.1, 9, 10).
- 2026-11-17, Claude's calls, for the founder to overturn: the six financial tables stay on the
  report page (3); the tab opens on Revenue alone and the picks do not follow the reader to
  another company (7.4); the sub-tab and the period are kept while the app is open, the unit in
  the browser (7.2); the three colours' values (7.6); one decimal in millions for a small
  company (7.7); the read holds the lists of lines (8.3); PEG joins the ratios (12.4).
- 2026-11-17, the build, the builder's and the controller's calls, for the founder to overturn:
  - The `key` of a statement's or a ratio's line in the read's answer is FMP's field name (8.3
    says the page's own name for the line; section 12 leaves the key to the builder). FMP's fields
    are unique in each table, so a key is one a line. A segment's key is its name, as 8.3 says.
  - The answer holds nine tables: the three statements by fiscal year and by quarter, the two
    segment tables and the ratios.
  - A count of one in the left caption reads `the last fiscal year`, `the last quarter` or `the
    last half-year`, words 7.2 does not give. On a statement, a table with columns and no line
    has no left caption: its sentence, `No figures on file.`, says what it holds.
  - The tab's component is keyed on the answer's symbol, so the picks are dropped when another
    company's answer lands, and not while the old company's tab is still drawn, faded, as the
    next one loads (9).
  - The block is a `section` with the panel's class and no title, as the mockup's; its name,
    `Financials`, is for a screen reader alone.
  - No mark is drawn for any figure the table writes as a dash: a share count or a multiple of
    exactly 0 as well as an amount, which 7.5 names. A per-share figure of exactly 0, a bar of no
    height, draws none either.
  - The ticks' letter follows the plot's largest tick and includes `T`, for trillions (a plot
    whose largest tick is 3 trillion reads `0T 1T 2T 3T`); 7.5's examples name `B` and `M`.
  - One picked line that cannot draw (a ratio under Quarterly) shows its name and `by year only`
    in the chart's head, and the sentence of 7.5 in the plot's place. With no room on its right,
    the box of several lines stands at the period's left, placed by its right edge.
  - A bar's class is `app-fin__col`; the row of controls keeps `app-fin__bar`, so neither takes
    the other's style.
  - Section 10 says `charts.md` "gains the section of 7.6 and loses nothing". The build reworded
    the sentences the four colours made untrue, on the controller's rulings. In `charts.md`,
    "Because there is no categorical palette, the six categorical checks do not apply." became
    "No other chart has a categorical palette, so the six categorical checks do not apply to
    them; *Several series the reader picks* says what its four colours were held to." The brand
    book's "Charts." paragraph gained "the one chart whose lines the reader picks takes four
    series hues", and `SpreadChart.md`'s "Don't add a third line" says Fairband has no
    categorical palette "for a chart with a subject" where it said "by design". No rule was
    dropped.
  - The section's last bullet states what was measured and what was not. The four colours are
    not held to the palette method's lightness band or to its chroma floor: `chart-1`, the
    accent, `chart-3` in the dark theme and `chart-2` in the light one stand outside them. Two
    pairs share a lightness, and hue alone parts them. Under simulated tritan sight the light
    theme's `chart-3` and `chart-4` are 4.7 apart, which the method reports and does not gate.
    The task's review measured every figure again.
  - The test sketch of the plan's Task 6 expected each of `chart-2`, `chart-3` and `chart-4` in
    `charts.md`, where the section the plan gave named them only as "`chart-1` to `chart-4`".
    The test pins the whole section, word for word.
  - The fixtures of the two new routes are named `ratios.annual.json` and
    `key-metrics.annual.json`, not `ratios.json` and `key-metrics.json` as the plan's Task 1 has
    them: the vendor double keeps a request's period in a shared fixture's name.
- 2026-11-17, the whole-branch review, and the controller's rulings on it, for the founder to
  overturn:
  - The lines on the chart stay when the reader leaves the tab for another tab of the same
    company and comes back (7.4). The tab was drawn anew each time it opened, so it came back on
    Revenue alone, while the sub-tab, the period and the unit came back as they were. The tab's
    script now keeps the picks beside the sub-tab and the period, with the company they belong
    to, and they go only when another company's answer lands in the tab (9). The task reviews had
    not seen it: the tests' node driver drew the tab anew in one step for two events, another
    company's answer landing and the tab opening again. The driver now tells them apart.
  - Two sentences of `charts.md`'s section "Several series the reader picks" did not hold of the
    chart as built. "An amount is a column from zero" left out the per-share figures and the
    share counts, which the chart also draws as columns (7.5); it now reads "An amount, a
    per-share figure or a share count is a column from zero". "The label beside each line names
    it" named a label the chart does not draw, since the labels are a row above the plot; it now
    reads "the hover box names each line with its figure, and a period's columns stand in the
    labels' order".
  - A change of the Words: the first column's head on Ratios reads `as each row says; per share
    in USD`, with the tab's currency in place of `USD` (7.3). No row of the Per share group said
    its currency.
  - With two lines picked and one of them off under Quarterly, the line drawn took
    `chart-neg-3` for a figure below zero while its label wore the line's own colour. The rule of
    7.5 is one line picked against two or more, not one line drawn: with two or more picked,
    drawn or off, every bar wears its line's colour.
  - The read handed `inputs_statements.cadence_of` every period end of the quarterly income
    statement, a date stored twice among them, where the engine takes one end a date, so a
    half-year reporter whose newest row is stored twice read as quarterly. The read now hands it
    each end once, oldest first.
  - The policy files' comment that counts the fetch's calls, "13 FMP and 2 GuruFocus calls each"
    (`fairband-policy-v16.toml`, and v5 to v15), was untrue before this branch, and it is left as
    it is. A policy's hash is its bytes, and the store refuses a known version under another
    hash, so the comment is corrected in the next policy version (B-229).
- 2026-11-17, the fix wave's re-review. Every finding was addressed. What it left, filed in
  B-239 and not fixed on the branch, since the plan has one fix wave: the lines kept for a
  company are not checked against a new answer, so a company first opened with no line keeps
  an empty chart after a refresh gives it lines, until the reader presses a row, and where a
  kept line is gone the reader can take the last drawn line off. Neither raises. Claude's
  ruling on the case the review found unstated in 7.4: the lines kept are those of the company
  whose Financials tab was drawn last, and 7.4 now says so.
- 2026-11-17, the founder, on the built branch and its three options: "1" (merge to main
  locally, with the live steps). The live steps and the readout:
  - The database was backed up with SQLite's backup API
    (`fairband-before-financials-tab-2026-11-17.db`, 7,624,159,232 bytes, `quick_check` ok),
    main moved forward to `72bd218`, and the server on port 8470 was started again from main.
  - Refresh 67, full, ran from 15:44:31 to 15:50:53 UTC: 6 minutes 22 seconds. It ran inside
    the reuse window of refresh 66, so it measured the four new calls and the calls whose last
    answer had failed, not a whole refresh: 6,272 calls of the four (two companies' segment
    answers were fresh and reused) and about 120 others. The minutes against 18.5 are not
    comparable; the estimate of 21 to 22 minutes for a whole refresh (8.2) is not yet measured.
  - 1,569 companies, 1,371 valued, one failed for its three annual statements (RML), as in
    refresh 66. No failed call among the four, by any endpoint, and no 429.
  - Bytes: the four answers hold 85.4 MB (the ratios 47.8, the key metrics 31.1, the segments by
    product 3.7 and by region 2.8), against the 94 MB of 8.2. The database grew by 121 MB, to
    7.75 GB.
  - Every company's read answered. 1,431 companies report in US dollars and 138 in 21 other
    currencies.
  - Segments: FMP answers an empty list by product for 245 companies and by region for 482; 149
    companies have neither table. One company has no ratios (RML, which has no statements).
  - A change of currency inside a table: 21 companies in their annual statements and their
    ratios, 10 or 11 in their quarterly statements, 11 in the segments by product and 16 by
    region. Seen on CRH and DEO: the code stands on those columns, and they draw no bar.
  - Half-year reporters by the engine's rule: 25 (DEO, RELX, UL, BHP). STLA reads Quarterly: its
    quarterly answer holds half-years to 30 June 2026 and then a row that ends 30 September
    2026, and the rule reads the two newest ends.
  - A fiscal year that has not ended (B-238): two companies, CRH and STLA. The newest annual row
    of each ends 30 September 2026, under eleven months after the one before.
  - No table holds one label twice today (B-239's edge). 26 companies have no Revenue line,
    most of them before their first sales; the tab opens on the first line (seen on BHVN).
  - The universe holds no bank and no insurer (13 companies of Financial Services: exchanges,
    data and payments), so that part of step 4 had no company.
  - The foreign filers: TSM in TWD, ASML in EUR with `USD` on most of its segment years, NVO
    in DKK. The per-share lines are in the reporting currency a listed share, as the page's
    design 14.2 says: TSM's EPS of 331.25 is TWD a depositary share (5,186 million of them),
    ASML's 24.71 EUR and NVO's 23.03 DKK a share.
  - The look on the live server, twelve companies at 1,600 pixels: AAPL as version 3 of the
    mockup; revenue, net income and operating margin on one chart; Quarterly; Billions kept
    over a reload; the lines kept over a visit to Estimates; no page error.
  - Still to do by hand: a research session starts its MCP server again, since the segments
    pass-through changed.
