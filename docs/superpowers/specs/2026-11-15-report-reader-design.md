# The report the reader sees: figures past the last fiscal year, the server's own words, an override at a split, and the playbook's words: design

Status: written 2026-11-15. This is theme 6 of the research agents' issues (the founder's review
of 2026-11-13): what a reader of a report sees on the report page and in the Markdown export.
The founder chose no item of it one by one. He said on 2026-11-15: "Choose between theme 5 or 6,
and proceed with spec, plan, then implementation", so every choice below is Claude's, marked *my
call* where it is more than a reading of a backlog row, and can be overturned as any other. Not
built.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value: the method stays `fairband-mechanical/1.5` and the policy v16. The changes are in
`src/fairband/reports/`, `src/fairband/web/`, the design-system copy under
`src/fairband/web/static/design-system/` and the playbook.

This document amends `docs/method.md` (the method as built) in sections 16.2, 16.5 and 16.6, and
the playbook with them. Every earlier spec stands for what it does not mention.

## 1. What this is

Thirty-two reports are on file. A reader meets four things in them that are wrong or thin, each
filed in the backlog:

1. **The charts and tables stop at the last fiscal year** (B-136, the founder on the GOOG report
   of 2026-11-09). Section 4's six tables and their charts read fiscal years only. GOOG's charts
   end at fiscal 2025 in November 2026, while the store holds the trailing twelve months, the
   stored quarters and the analysts' estimates.
2. **The server's own lines name Fairband's parts** (B-137). The export's second line reads "On
   snapshot 412, priced 2026-11-04, valid until …". The register rules that a report never
   writes "the snapshot" or "the route" and writes a date as "4 Nov 2026"; the agent's text
   follows it and the server's does not.
3. **Appendix A shows an override's figure as entered beside a bridge that shows it scaled at a
   split** (B-191, due before META's split of late January 2027).
4. **Small faults of the export and the page** (clauses of B-108 and B-119), and **words of the
   playbook that are wrong or unclear** (B-138), which reach the reader through the agent's text.

And one item is closed by its own evidence, with no code: the words warning at publish (B-135).

## 2. Goals

- A report's financial charts and tables show the present and the expected, not only the last
  closed year: the trailing twelve months, the analysts' estimates where a line has them, and
  the stored quarters in section 5.
- Every line the server itself writes outside Appendix A reads as the register rules: no name
  of a part of Fairband, dates in words.
- Appendix A never shows two figures for one override without saying why.
- The export reads right in a Markdown viewer and prints right.
- The playbook's words state the method as it runs.

## 3. Non-goals

- No engine change and no new input. No value, level, flag or review moves.
- The number check's token rule (B-102: `52-week`, `S&P 500` and the like) is the agent's
  trouble, not the reader's, and stays filed.
- The refactors filed with these rows stay filed: `refs.py`'s size, `reviews_api.py`'s size, the
  three camelCase helpers, the label copies.
- The list of checks in an older report's Appendix A (B-110) needs the checks stored with the
  report; it stays filed.
- An ordered list that interrupts a paragraph (B-119) changes what the number check reads; it
  stays filed.
- The engine and review debt of B-107 is not a reader's matter.
- Two things found while writing are filed, not built: the sentence of what the price needs
  (method 4.11, `engine/price_needs.py`) names "the route" on the report page and in the
  drawer, and it is the engine's sentence with its own pins; and the stored periods' gross
  profit, which the trailing figures and the quarters read do not carry.

## 4. Anti-goals

- A chart that makes an estimate look like a reported figure. An estimate and the trailing
  twelve months are told apart from a fiscal year by the bar's look and by words under the
  chart, in the table twin and in the export.
- A report that reads differently on the page and in the export. Titles, column labels and the
  words under a chart come from the server, once.
- A stored report that stops rendering. Every report on file renders after the change, with no
  migration and no republish: the page's charts and the export's chart tables already read the
  store when the report is viewed (`report.js`, `readSeries`; `charts.py`).

## 5. The evidence (a copy of the live database at refresh 62, read-only, 2026-11-15)

- 32 reports, 31 full reports and one valuation review; 26 written after B-134 (the plain words,
  merged 2026-11-09).
- In those 26 the names of Fairband's parts that a report never writes ("the engine", "the
  route", "the snapshot", "the bridge" and the others of the register's list) appear twice: "the
  bridge" in report 19 (NVO) and in report 31 (RKLB). The method terms that appear outside the
  Valuation section are mostly the ones the template itself uses there: "kill criterion" 36
  times, "moat" 33, "phase" 25.
- The store holds, beyond the fiscal years: the trailing figures (`TrailingFigures`: revenue,
  operating income, net income, diluted EPS, stock pay, operating cash flow, capital spending,
  dividends, buybacks; no gross profit), the stored quarters (`stored_quarters`, eight a fetch,
  the same lines), and the consensus by fiscal year and by quarter (`AnnualEstimate`,
  `QuarterEstimate`: EPS, revenue, net income, analyst counts).
- The design system's `HistoryBars` styles a bar by its sign alone. Its points take a period, a
  value and a freshness that marks the axis label only.

## 6. Figures past the last fiscal year (B-136)

### 6.1 A table's columns

A financial table carries its columns. Each column has the period its cells are in, a kind and a
label in words:

| Kind | Period | Label | Example |
|---|---|---|---|
| fiscal | the fiscal year, `2025` | the year | "2025" |
| trailing | `ttm` | "12 months to" and the trailing period's end as the references write a day | "12 months to 30 Sep 2026" |
| estimate | the fiscal year and `E`, `2026E` | the year and "estimate" | "2026 estimate" |

The page, the table twin and the export read the label; none makes its own. The fiscal columns
are the last five fiscal years on file, as today.

### 6.2 The trailing column

Three tables gain one trailing column after the fiscal years: `growth`, `cash_flow` and
`capital_allocation`. It stands when the trailing figures are on file, are sums of stored
periods and not the last fiscal year standing in (`on_fiscal_year` false), and end after the
newest fiscal year's period end. Otherwise the table has no trailing column.

| Table | Row | The trailing cell |
|---|---|---|
| growth | revenue | the trailing revenue, citing `fact:<symbol>/revenue/ttm` |
| growth | revenue growth | the trailing revenue over the revenue of the twelve months before it − 1, the sum of the stored periods a year earlier; none, noted "fewer than two years of periods on file", where those are not all stored |
| growth | gross margin | none, noted "not measured over the trailing twelve months": the store keeps each period's gross profit, but neither the trailing figures nor the stored periods' read carries it, and reading it is assembly work this design leaves filed |
| growth | operating margin, net margin | the trailing operating income, and net income, over the trailing revenue |
| growth | EPS | the trailing diluted EPS, citing `fact:<symbol>/eps_diluted/ttm` |
| cash flow | operating cash flow, capital spending | the trailing lines, citing `fact:<symbol>/cfo/ttm` and `/capex/ttm` |
| cash flow | free cash flow, free cash flow over net income, stock compensation over revenue | from the trailing lines, as the fiscal cells are from the year's |
| capital allocation | dividends, buybacks | the trailing lines, citing their `fact:` refs |
| capital allocation | share count change, acquisitions | none: "not measured over the trailing twelve months", "not on file" |

A computed trailing cell cites itself, `table:<symbol>/<table>/<row>/ttm`, as a computed fiscal
cell does. `returns`, `solvency` and `quality` keep their fiscal columns alone: a return on
capital, a balance and a score are not measured here over the trailing twelve months (*my call*:
B-136 names them as staying annual for the estimates; the same holds for the trailing column,
since a trailing ROIC needs a balance the tables do not read).

### 6.3 The estimate columns

`growth` alone gains estimate columns, after the trailing column: the consensus fiscal years
after the newest fiscal year on file, in order, three at most (*my call*: the years of the path
the valuation reads).

| Row | The estimate cell |
|---|---|
| revenue | the consensus revenue, citing `estimate:<symbol>/<year>/revenue` |
| revenue growth | the consensus revenue over the revenue of the year before − 1: the newest fiscal year's reported revenue for the first estimate year, the estimate before it for the others; none where the year before has no figure; it cites itself, `table:<symbol>/growth/revenue_growth/<year>E` |
| EPS | the consensus EPS, citing `estimate:<symbol>/<year>/eps` |
| gross, operating and net margin | none, noted "no estimate for this line" |

A consensus year with neither a revenue nor an EPS gives no column. No other table gains an
estimate column: no estimate exists for its lines.

The column's period, `2026E`, is the table's key for the year: it keeps an estimate apart from
the fiscal year's own column once the year is reported. A revenue or EPS estimate cell cites an
`estimate:` ref, whose own period is the year, `2026`, as today. So the number check reads
`2026E` and `2026` as one period: a cite of an estimate cell may give either, on an `estimate:`
ref and on a `table:` ref alike, and no cite is refused for the letter.

### 6.4 The quarters (section 5)

A seventh table, `quarters`, holds the newest eight stored periods, oldest first, each column a
fiscal column of its own kind, `quarter`, labelled as the period is named ("Q3 2026" for
`2026-Q3`). Its rows: revenue and EPS, each citing the stored period's line
(`fact:<symbol>/revenue/2026-Q3`, `fact:<symbol>/eps_diluted/2026-Q3`), and the operating
margin, operating income over revenue, citing itself (`table:<symbol>/quarters/operating_margin/2026-Q3`).
A company with no stored period has the table with no column. A company that reports twice a
year has its half-years, under the labels the store gives them.

The table is not one of the six of section 4: `financial_tables` keeps returning six, and the
quarters come from a function of their own that the `table:` resolver, the `/financial-tables`
read and the export also call (*my call*: a seventh entry in the same tuple would put a quarter
table under section 4's heading in every place that maps the six by position).

### 6.5 Where each shows

- **The `/financial-tables` read** serves each of the six tables with its `columns`, and the
  quarters beside them under `quarters`. An agent's read of it through the MCP `financial_tables`
  tool shows the same.
- **The references.** A `table:` ref to a trailing, an estimate or a quarter cell resolves like
  a fiscal one, by the cell's period, and its source reads "the growth table, revenue growth,
  the trailing twelve months", "…, fiscal 2026, the analysts' estimate" and "the quarters
  table, operating margin, Q3 of fiscal 2026". The period match of the number check reads
  `2026E` as the year (6.3).
- **The export.** Section 4's chart tables carry the new columns under their labels; the header's
  first cell reads "Period" in place of "Fiscal year" on a table with a trailing or an estimate
  column. Section 5, "The last earnings call", gains one chart table, "By quarter", before its
  text. A valuation review has section 5 too and gains it.
- **The page.** Each chart of section 4 draws the trailing bar and the estimate bars after the
  fiscal bars. Section 5 draws three charts, revenue, the operating margin and EPS by quarter,
  under the title "By quarter". The annual charts never hold a quarter.

### 6.6 How a bar tells its kind

A patch to the design-system copy (`// fairband:`), as `inverse` is one: a `HistoryBars` point
takes a `kind`, `trailing` or `estimate`, none for a fiscal year.

- A trailing bar is filled in the de-emphasis grey, the token `chart-context`.
- An estimate bar is an outline in the series colour with no fill.
- On a signed series the trailing bar keeps the grey and the estimate's outline takes the sign's
  colour.
- The value printed above a bar goes to the last bar that is not an estimate, so the figure a
  reader sees first is a reported one.
- The chart's accessible name reads "by period" where a point has a kind, "by quarter" on the
  quarter charts, and "by fiscal year" otherwise, as today.

Under a chart that has such a bar the page writes one line, from the columns' labels: "Grey: the
12 months to 30 Sep 2026. Outlined: analysts' estimates." (the first sentence alone without an
estimate, the second alone without a trailing bar). The table twin shows each column's label.

This departs from two lines of the design system's own documents, which say that every column
of `HistoryBars` is `chart-1` and that touching marks are parted by a gap, never by a stroke.
The founder's row asks for both looks in these words: "the last bar in the de-emphasis grey,
marked 'to date', and the consensus years as outlined bars marked 'estimate'". The patch is
marked and tested as the other patches are.

## 7. The server's own words (B-137, and the dates of B-108)

The rule covers the lines the server writes above the sections, which a stranger reads first:
the export's two header lines and its line on a reused full report, and the page's line under
the title. They name no part of Fairband and write every date as the references do ("4 Nov
2026"). The record is not in the rule: the references name the records they cite, in the words
method 16.6 fixes ("snapshot 412, the price, priced 3 Nov 2026"), a chart's title names the
reading it shows ("Sensitivity 7: …"), Appendix A uses the register's record words (override,
review, snapshot, judgment), which the register gives it, and Appendix B is the glossary of
those terms. Two things change inside Appendix A all the same: its dates are written in words,
and the one full sentence that tells the reader why there is no secondary valuation loses
"the route", a name the register forbids and has no record word for. The checks' rule
sentences and a stored refusal's own words stand as they are.

| Where | Today | After |
|---|---|---|
| The export's first line | `GOOG · full report · 2026-11-09 · claude-opus-5-5 · revision 1` | the date as "9 Nov 2026" |
| The export's second line | "Stance: hold. On snapshot 412, priced 2026-11-04, valid until 2027-01-27." | "Stance: hold. On the data of 4 Nov 2026, priced that day, valid until 27 Jan 2027." |
| The export's line on a reused full report | "Reuses full report 3." | "Reuses the full report of 3 Nov 2026." |
| The page's line under the title (the reader's `cites` line) | "cites snapshot 412 · review 88 · reuses the full report of 3 Nov 2026" | "On the data of 4 Nov 2026 · priced that day · valid until 27 Jan 2027 · reuses the full report of 3 Nov 2026" |
| Appendix A, no secondary valuation | "no secondary valuation: the route values the company" | "No secondary valuation: Fairband's own valuation gives the company a value" |
| Appendix A, the same under a review | "… the review values the company" | "No secondary valuation: the review gives the company a value" |
| Appendix A, the Inputs table's "As of" and the guidance's "Call" | ISO dates | dates in words |

The second line's rule: "On the data of" and the snapshot's data date; then "priced that day"
where the price date is the same day, "priced" and the price date where it is another, and
nothing where the snapshot has no price date; then "valid until" and the date. The page's line
follows the same rule with the reader's `·` between its parts, and names a thesis no more: the
record's ids are in Appendix A's Snapshot and Versions parts, where they are today.

The refusal reasons that `no_secondary` passes through (a snapshot's own refusal, "no diluted
share count") keep their words after "No secondary valuation: ".

## 8. An override at a split (B-191)

Where the review a report rests on applied an override at a figure other than the one entered,
because a split fell between (method 14.6), Appendix A's Overrides part shows both, in the
export and on the page: the figure in force, and "entered as $30.00 a share before the 2-for-1
split of 27 Jan 2027", the words the review already holds on the override's JUDGMENT entry.
The row's old figure is then the review's too, the reading on the new share basis, so that the
pair reads on one basis: a reading of $60 cut to $30 before a 2-for-1 split shows "$30.00 →
$15.00" with the words, never "$60.00 → $15.00". Where the review applied the figure as
entered the row shows the stored pair, as today.

The pair in force is the review's bridge line's old and new, for that override's id; the words
are the clause of the JUDGMENT entry's note that the scaling added. Both are read from the stored
review, not computed again from the splits on file today, so Appendix A states what the review
did. An override the review did not apply shows as today.

## 9. Small faults a reader meets

- **The export's references come last** (B-108). GitHub-flavoured Markdown renders footnote
  definitions at the end of the document, so today's "References" heading stands empty before
  Appendix A and the list lands after Appendix B. The export's order becomes: the sections,
  Appendix A, Appendix B, References. The page keeps its order.
- **Section 9's statistics rows name the series as the other table does** (B-108): "Trailing
  P/E" and "Forward P/E", not "trailing P/E" and "forward P/E".
- **A cite's number stays with its figure** (B-119): in a report's table the number `[n]` after
  a cited figure does not wrap to a line of its own.
- **A wide table prints whole** (B-119): the print rules let a report's table take the paper's
  width at a smaller size, in place of clipping at the screen's scroll box.

## 10. The playbook's words (B-138)

Each clause of B-138 that still holds (the map of 2026-11-15 found all but one) is corrected in
the playbook and its pin in `tests/test_playbook.py`:

- The register's hurdle-rate phrase says it is one rate for every company, not the company's.
- The register's belief phrase names the fade and the runway's end; `SKILL.md`'s overrides table
  says the growth fades from the year-3 rate down to the belief, as method 5.5 does, not "before
  the fade to the long-run rate".
- The template says the forward P/E sits beside the assumed growth, not that it "rests on" it.
- The Driver column's words that have no register row ("the growth of years two and three", "the
  reinvestment", "the risk") gain rows or give way to phrases that have one; the example's "The
  protection from rivals." becomes the moat's phrase.
- "On the method's earnings" becomes a phrase a reader can follow.
- Section 9's detail asks for the price's date where the refresh of step 3 failed.
- The validity-window phrase says what stays valid and that the row ages before the window's
  end, and the Summary's "Valid until" says what is valid until then.
- Step 3 gains the branch for a `refresh_start` refused for another reason than a running
  refresh.
- The register says whether an override's reason may use the record words.
- "Stage" names the phase alone; the Dickinson reading is named so that the two are not confused.
- `SKILL.md`'s rules on the secondary valuation name the parts form beside the standard
  discounted cash flow.
- The example's figures agree with each other, its Valuation names the Dickinson stage, and it
  gives "thesis" and the three words of likelihood their meaning at first use.
- The tests: the docstring of the step 12 test says what the test asserts; the pin that bans
  "review" lets "valuation review", a mode's name, stand; the bracket check exempts the one term
  in brackets, not any parenthetical.

The clause on step 3's "again" no longer holds (a scoped refresh fetches every call) and is
dropped from the row.

## 11. Closed with no code

- **B-135, the words warning at publish.** The row says to judge the need by the reports after
  B-134. In 26 reports the parts' names appear twice (section 5). A warning would also need a
  channel that does not exist (the check returns refusals alone, and the page shows no check
  result), and it would flag the method terms the template itself uses outside section 8. Not
  built (*my call*).
- **B-102's clause** that Appendix A has no row for `fact:`, `table:`, `estimate:`, `close:`,
  `finding:`, `derived:` and `policy:` cites: the references list of method 16.6 gives every
  cited ref its number and its source.
- **B-108's clause** on the year-end table's title, and **B-110's clause** on the "no secondary
  valuation" reason read from the latest row: both were corrected since they were filed.

## 12. The documents

- `docs/method.md`: 16.2 (the `table:` ref's periods and their words), 16.5 (the columns, the
  trailing and estimate cells, the quarters table) and 16.6 (the export's order, its header
  lines, the chart tables' new columns and section 5's table, Appendix A's two figures at a
  split). Section 11 gains no row: the method version does not change.
- The playbook: `reference/report-template.md` says what section 4's charts now show and that
  section 5 has the quarters chart beside the agent's own table of the quarter against the
  expectations; `reference/citations.md` names the new periods of a `table:` ref;
  `reference/tools.md` names the columns and the quarters in the `financial_tables` read; and
  section 10's corrections.
- The Methodology page states none of this and does not change.
- `docs/backlog.md`: B-136, B-137, B-191, B-138 and B-135 move to Done; B-102, B-108, B-110 and
  B-119 lose the clauses closed here.

## 13. Tests the builder must write

- The tables: the columns of each table on a company with a trailing period and consensus years;
  each trailing and estimate cell's value against the stored lines; no trailing column where the
  trailing figures stand on the fiscal year or end with it; no estimate column for a consensus
  year already reported; revenue growth of the first estimate year on the reported year; the
  quarters table on eight, on fewer and on no stored periods, and on a half-year filer; every
  new cell's ref resolves to the cell's value and reads its words.
- The number check: a section that cites a trailing, an estimate and a quarter cell passes, and
  one that cites `2026E` for a year the consensus lacks fails as an unresolved reference.
- The export: the new columns under their labels; "Period" in the header's first cell; section
  5's table; the references last; the header's two lines in each of the price-date cases; the
  statistics rows' names; Appendix A's dates, its two "No secondary valuation" sentences and an
  override scaled at a split with both figures.
- The page, in node (`tests/web/page.mjs`): a chart's points carry each column's kind and label;
  the line under the chart in its three forms; the quarter charts; the reader's line under the
  title in each price-date case; an override scaled at a split.
- The design-system patch: a trailing and an estimate bar's class, the value's place, the
  accessible name; the patch's marks, as the other patches are tested.
- A stored report of today renders, page and export, with no error (a fixture report written
  before the change).
- The playbook: each corrected sentence pinned, and the three test corrections of section 10.

## 14. Acceptance

- On a copy of the live database, with the branch's server: GOOG's report page and export show
  the twelve months to its newest stored quarter and the estimate years in section 4, and eight
  quarters in section 5; every one of the 32 reports' pages and exports renders (HTTP 200 and no
  refusal sentence) and none shows "snapshot" or "route" in its first two lines.
- The four checks pass.
- No snapshot, review or override differs before and after: the change stores nothing.

## 15. Left to the builder

- The names and shapes of the column record and of the function that returns the quarters table.
- How the page reads a column's kind and label into a chart's points and its table twin.
- The CSS of the two bar kinds, within the tokens the design system has, and the print rules.
- The exact new sentences of section 10, in the register's own style.

## 16. Order of work

The tables' columns with the trailing and estimate cells and their refs; the quarters table; the
export; the design-system patch and the page's charts; the server's words and the dates; the
override at a split; the small faults; the playbook's words; the documents, the backlog and the
whole-branch review; the acceptance on a copy, and the live step on the founder's word.

## Decision log

| Date | Decision |
|---|---|
| 2026-11-15 | The founder left the choice between themes 5 and 6 to Claude and asked for a spec, a plan and a subagent-driven build. Claude chose theme 6: it needs no ruling before it is built, it moves no valuation, and its largest item, B-136, is the founder's own request of 2026-11-09. Theme 5 holds three questions only the founder can answer (B-99, B-161, B-167). |
| 2026-11-15 | The builder check (Opus 5.5, xhigh), one round, five questions, all settled by Claude: the rule on the server's words covers the lines above the sections and not the references, the chart titles or Appendix B, and inside Appendix A only the dates and the one sentence on the secondary valuation change; the check reads `2026E` and `2026` as one period; the trailing gross margin stays empty under a true note, since the store keeps the periods' gross profit but no read carries it; an override scaled at a split shows the review's old and new, both on the new basis. Filed: the price-needs sentence that names the route, and the periods' gross profit. |
| 2026-11-15 | Settled by Claude while writing, on a map of the code, each marked *my call* above or stated here. The trailing column goes on three tables and the estimate columns on one. The quarters are a table of their own, not a seventh of section 4. The bar kinds are a marked patch to the design-system copy, against two lines of its documents, on the founder's own words in B-136. Inside Appendix A the register's record words stand and only "the route" goes. An override's two figures at a split are read from the stored review. B-135 is closed on the evidence of 26 reports. Left filed: the checks stored with a report, the ordered list that interrupts a paragraph, the number check's token rule and the refactors. |
| 2026-11-15 | The readout. Built subagent-driven in eleven tasks (Opus 5.5, xhigh), each reviewed alone, then one whole-branch review and its fix wave: 3,280 tests; nothing under `engine/`, `policy/`, `refresh/` or `store/` changed; the method stays 1.5 and nothing new is stored. **The acceptance**, on a copy of the live database at refresh 62, with the branch's server and no vendor key: 32 reports, every page read and every export answers 200, no fault; every export opens "On the data of …" with its dates in words, carries "By quarter" and a Snapshot part in Appendix A, and ends Appendix A, Appendix B, References; estimate columns on all 32 exports, a trailing column on 26 (25 of the 30 companies), eight quarters on 29 companies and three on FRVO; a tables read takes 0.04 s and an export 0.17 s at the median; the copy's row counts did not change. **The whole-branch review** found no Critical and three Important, all fixed: the export named no snapshot once its second line dropped the id, so its Appendix A now opens with a Snapshot part as the page's does; the EPS estimates stood beside the reported EPS with nothing saying that the bases can differ; one axis sentence of method 16.6. **Claude's rulings during the build**, each open to the founder: a small read may be added under `refresh/` where it changes nothing assembly computes; the line under a chart is composed on the page from the server's labels; an override whose step refused at a split shows the pair in force; in print a report's table takes the floor of the type scale (12px words and cites, an 11px cite number); the consensus and surprise cells of a quarter's operating margin and free cash flow stay empty and the company's guidance goes in a sentence; the method document's wording of the belief and the fade was corrected with the playbook's; every EPS estimate says it is on the analysts' own basis, always, not only where the stock-pay basis test reads a difference (if wrong, one clause to drop or to make conditional); where the consensus cannot be read the tables come back without estimate columns and a warning is logged, so no read that answered before can fail (if wrong, a refresh failure is less visible on a report). **Not seen** in a browser or on paper: the bar kinds, the ticks, the cite pair and the print rules (B-200). Closed: B-136, B-137, B-191, B-138, B-135; filed: B-197, B-198, B-199, B-200. The founder gave his word for the live step on 2026-11-15: the branch merges to main with this commit and the server restarts from main on 8470, with no backup and no revalue, since nothing is stored. Every research session must restart its MCP process, since the playbook changed. |
