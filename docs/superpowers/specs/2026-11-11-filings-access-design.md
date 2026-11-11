# Filings access for the research agent: design

Status: written 2026-11-11. The founder read the Microsoft session (report 16), where the agent
sent subagents to SEC EDGAR for figures FMP already serves, accepted four items ("build items 1 to
4 now") and skipped the questions, so every detail below that the four items do not fix is *my
call* (Claude's) and can be overturned. The decision log at the end lists them. Builder check: done
2026-11-11; its five questions are settled in the log and written into sections 2, 5, 5.5, 5.6
and 7. Built 2026-11-11 and 2026-11-12, six tasks and one fix wave after the whole-branch review;
the build's rulings are the log's last row, and the sections below say what was built.

This document adds to `docs/method.md` in section 16.2 (one new ref form and one new period of an
old one) and wherever that document describes the agent's reads and pass-throughs. The Tier 2 spec
(2026-11-06) stands for everything this one does not mention: the pass-through store, the reuse
rule, the slots, the MCP process, the report check.

## 1. What this is and why

The research agent reads a company's filings with the host's own tools: it searches EDGAR, fetches
pages and types what it finds as findings. On Microsoft (report 16) 11 findings came from
sec.gov. A live probe on 2026-11-11 found that FMP holds 6 of the 11 in its JSON form of the 10-Q
and the 10-K, and lists every filing with a direct link. Fairband calls neither route. The same
session fetched the quarter's revenue, operating income, EPS and cash flow from the press release,
though the refresh had stored them: no tool serves the stored quarters, and the playbook's step 5
tells the agent to take a quarter's figures from the 10-Q.

Four items, one piece:

1. **The filing report.** A pass-through of FMP's `financial-reports-json`, stored, served a part
   at a time: the reports on file, a report's sheet list, one sheet, one long cell, and a text
   search across a report. A cell is cited by a new ref form, `filing:`.
2. **The filing list.** A pass-through of FMP's `sec-filings-search/symbol`: every filing in a
   window with its form type, its dates and its links.
3. **The quarters.** A new read answers the newest stored quarterly periods, each line with a
   `fact:` ref the report check resolves.
4. **The playbook.** Read Fairband first; go outside only for what remains; check what is stored
   before a subagent is briefed.

Why it matters: a figure typed as a finding is not checked against anything. A figure cited from a
stored response is checked by the report check. The run is also shorter and does not depend on
sec.gov answering the host's fetch tool (B-142).

## 2. Goals, non-goals, anti-goals

Goals:

- An agent reads the statements and the notes of a 10-Q or a 10-K from Fairband, finds a sentence
  in them by text, and cites a number cell by a ref it copies from the answer.
- An agent gets the link of any filing without searching EDGAR.
- An agent cites a single quarter's statement lines from the store.
- No answer of the new reads is longer than about 40,000 characters as the agent's host receives
  it. The MCP process prints an answer's JSON indented, which lengthens it, so each list a route
  answers is held to 30,000 characters as it is printed (section 5).

Non-goals:

- No fetch of sec.gov by Fairband. The text FMP lacks (8-K exhibits, Item 1, the MD&A, risk
  factors, the proxy, another company's filings) stays with the host's tools, opened by the link
  the filing list gives.
- No change to the page's code: nothing in the screen, the drawer or the report page reads the
  new routes. The references list of a report names a filing's cell in words (5.6), which the
  page shows as it shows any reference.
- No engine, classifier, policy or refresh change. The refresh does not fetch a filing report;
  only an agent's request does.
- No change to `financials` or to `segments`.

Anti-goals:

- A read that returns a whole report (1 to 1.5 MB).
- A ref the agent must retype from a long label: a ref is short and holds indexes.
- A key, or a link that carries one, in a stored payload, an answer or a log.
- Vendor data in a test fixture.

## 3. What FMP serves (live probes of 2026-11-11, the Ultimate plan)

- `sec-filings-search/symbol`: `symbol`, `from` and `to` (both required: without them HTTP 400),
  `page`, `limit`. Rows newest first: `symbol`, `cik`, `filingDate` and `acceptedDate`
  (`2026-10-28 00:00:00`), `formType`, `link` (the filing's index page on sec.gov) and `finalLink`
  (the main document). The default limit is 100; `limit=1000` answers up to 1,000 rows. MSFT has
  190 rows in a year, 140 of them Form 4; ASML has 12.
- `financial-reports-dates`: `symbol`. Rows newest first: `symbol`, `fiscalYear`, `period`
  (`FY`, `Q1` to `Q4`), `linkJson`, `linkXlsx`. MSFT has 76 reports, to fiscal 2027 Q1; ASML has
  11 and TSM 7, annual ones mostly. An unknown symbol answers `[]`.
- `financial-reports-json`: `symbol`, `year` (the fiscal year), `period`. A JSON object: `symbol`,
  `period`, `year`, then one key a sheet, 85 sheets for MSFT's 10-Q of fiscal 2027 Q1 and 112 for
  its 10-K of fiscal 2026, 950,000 to 1,500,000 characters. A sheet is a list of rows, a row an
  object with one key, the row's label, whose value is the list of the row's cells: numbers,
  strings and empty strings. The first row's label is the sheet's title with its scale
  (`Leases - Additional Information (Detail) $ in Billions`). The sheets are the statements, each
  note as one long text cell (up to 91,000 characters), each note's tables as text, and the
  notes' detail tables as number cells. Sheet names are cut at 31 characters and made unique
  (`SEGMENT INFORMATION AND GEOGR_1`). The report holds no Item 1, no MD&A and no risk factors.
  A period FMP does not hold, or an unknown symbol, answers HTTP 200 with
  `{"Error Message": "..."}`; a period that is not one of the five answers HTTP 400.

## 4. The pass-through kinds

Three kinds join `refresh/passthrough.py`, fetched and stored as the others are (the reuse rule,
the slots, the scrub, the error rows). They are not kinds of the generic route
`/api/vendor/{kind}/{symbol}`, whose answer is the whole payload: `KINDS` stays the generic
route's list, and the three sit in a list of their own.

| Kind | Stored endpoint | FMP route | Logical params (the reuse key) | Reuse |
|---|---|---|---|---|
| `filings` | `sec-filings` | `sec-filings-search/symbol`, `page=0`, `limit=1000` | `symbol`, `from`, `to`, `limit` | `reuse_hours` |
| `filing-reports` | `filing-report-dates` | `financial-reports-dates` | `symbol` | `reuse_hours` |
| `filing-report` | `filing-report` | `financial-reports-json` | `symbol`, `year`, `period` | 720 hours |

- A filing does not change once filed, so a usable report is reused for 30 days (*my call*).
- A `filing-report` payload is usable when it is an object without the key `Error Message` that
  holds one sheet or more (a key whose value is a list). An unusable one is stored with its
  error and never reused, as `pe-history`'s is. A `filings` or a `filing-reports` payload is
  usable when it is a list.
- `period` is `FY`, `Q1`, `Q2`, `Q3` or `Q4`, else `ValueError` "period is FY or Q1 to Q4" before
  any call; `year` a whole number.
- `Fmp` gains one method a route (`vendors/fmp.py`), with the module docstring's note of what was
  checked live on 2026-11-11 (section 3).

## 5. The routes

A new module, `web/filings_api.py`. Each route may call a vendor, so each joins the reads that
need `X-Fairband-Request: 1` (`app._VENDOR_READS`), else 403. The symbol is read as the vendor
route reads it. Each answer carries `symbol`, `responseId`, `observedAt` and `reused` of the stored
response it was read from.

Served text: a sheet's name, a label or a string cell is served with every run of white space, the
no-break space included, as one space, and its ends trimmed. Offsets and lengths count in the
served text. A sheet is named by its served name everywhere: in the sheet list, in the `sheet`
parameter and in a ref. The stored payload is not changed.

The budget: a list an answer holds (the sheets, a sheet's rows, the filings, the search hits)
stops before the item that would take the list past 30,000 characters as the MCP process prints
it (each item's JSON indented by two, four more spaces a line for its place in the answer, two
for the comma and the line break), one item at least, and the answer says that more remains
(`nextRow`, `more`). The counts below (100 rows, 20 hits) are upper bounds beside it. The first
build measured 20,000 characters of compact JSON; the whole-branch review measured a 60-column
sheet page at 63,172 characters printed, so the measure became the printed one.

### 5.1 `GET /api/companies/{symbol}/filings?from=&to=&forms=&fromRow=`

- `to` defaults to the clock's date and `from` to 365 days before `to`; each an ISO date.
- `forms`: a comma list of form types matched whole and without regard to case (`10-K,10-Q,8-K`),
  or `all`. Left out, every form but the ownership forms `3`, `4`, `5` and `144` and their
  amendments (`4/A`): `insider_trades` serves those (*my call*).
- Answer: `from`, `to`, `filings` (newest first, from `fromRow` of the filtered list, 0 when left
  out, at most 100 and within the budget; each `formType`, `filingDate` as an ISO date,
  `acceptedDate` as FMP gives it, `link`, `finalLink`), `nextRow` (the next `fromRow`, or null),
  `count` (the filings the filter kept), `leftOut` (the number of rows the filter dropped) and
  `truncated`, true when FMP answered 1,000 rows, so older filings of the window are missing.

### 5.2 `GET /api/companies/{symbol}/filing-report?year=&period=&sheet=&fromRow=&row=&col=&offset=`

Four views, by the parameters given:

1. **Neither `year` nor `period`: the reports on file.** `reports`, as FMP orders them, each
   `{year, period}`; the links are dropped.
2. **`year` and `period`: the sheet list.** `year`, `period`, `sheets` from `fromRow` (0 when
   left out), at most 100 and within the budget, each `{name, title, rows, chars}`: the sheet's
   served name, the first row's label, its row count and the length of its JSON text; and
   `nextRow`. `period` is read without regard to case.
3. **With `sheet`: the sheet's rows.** `sheet`, `title`, `rows` from `fromRow` (0 when left out),
   at most 100 and within the budget, and `nextRow` (the next `fromRow`, or null). A row is
   `{row, label, rowRef, cells}`: its index in the sheet from 0, its label, the ref of the row
   (5.5), and its cells in order. A number cell is the number; a string cell is its served text,
   cut at 2,000 characters, and when cut it is `{text, chars}` with the full length. The view also
   answers `columns`, the words that name each column (5.6), so a later page still names them.
4. **With `sheet` and `row`: one cell's text.** `col` is 0 when left out, `offset` 0. Answer:
   `sheet`, `row`, `col`, `label`, `chars`, `offset`, `text` (at most 20,000 characters from
   `offset`) and `nextOffset` (or null). A number cell answers its JSON text.

### 5.3 `GET /api/companies/{symbol}/filing-report/search?year=&period=&text=`

A plain-text search of one report, without regard to case, in the served text of every label and
every cell (a number by its JSON text). A hit is a row: `{sheet, row, col, label, excerpt, offset,
rowRef, numbers}`. `col` is the first cell that matches, or null when only the label does;
`excerpt` is 300 characters each side of the first match; `offset` is the match's place in that
cell; `numbers` lists the row's number cells as `{col, value, column}`, `column` the words that
name the column (5.6). A number as it is printed finds a number cell (`33,165` finds `33165`). At
most 20 hits and within the budget, in the report's order, and `more` true when hits were left
out; a search has no paging, so the agent searches a longer text.

### 5.4 The refusals

| Case | Status | Sentence |
|---|---|---|
| The server has no FMP key | 503 | `no FMP key` |
| Every slot is taken | 503 | the pass-through's `BUSY` |
| The vendor call fails | 502 | the vendor's sentence, scrubbed |
| One of `year` and `period` without the other | 400 | `a filing report needs year and period` |
| A bad `period` | 400 | `period is FY or Q1 to Q4` |
| `sheet`, `row`, `col`, `offset`, `fromRow` or `text` without `year` and `period` | 400 | `a filing report needs year and period` |
| FMP holds no such report | 404 | `FMP holds no filing report for <symbol> <year> <period>: ask without year and period for the reports on file` |
| No such sheet | 404 | `no sheet named <name>: ask without sheet for the sheet list` |
| `row`, `col`, `fromRow` or `offset` out of range | 400 | `<name> is 0 to <last>` |
| `text` shorter than three characters as served, judged before the report is fetched | 400 | `text needs three characters or more` |
| An index asked of a sheet with no rows or a row with no cells | 400 | `<name> is out of range: there is none` |
| The request header is missing | 403 | the app's guard, before anything else |
| `from` or `to` not a date, or `from` after `to` | 400 | `from and to are ISO dates, from on or before to` |
| FMP's filing list, or its list of reports, is not a list | 502 | `FMP answered no filing list for <symbol>`, `FMP answered no filing reports for <symbol>` |

### 5.5 The `filing:` ref

A cell of a stored filing report is cited as

    filing:<responseId>/<sheet>/<row>/<col>

the stored response's id, the sheet's served name (`~` written `~0` and `/` written `~1`, as a
JSON pointer's token is), and the row's and the cell's indexes from 0. A `rowRef` is the ref
without its last part, so a cell's ref is the row's plus `/<col>`. It resolves for the report's
company to the cell: a number, or a string as it is served (the text the agent read, so a cite of
a word fits it; *the build's ruling*, Task 2), with no unit and no period, as a
`response:` field does. A response that is not a filing report, a sheet, a row or a cell that is
not there, and a row that is not a label with its cells resolve to nothing. Where two sheets have
one served name, the first is meant, and a row of the second carries no ref.

Why a form of its own (*my call*, after the builder check): a JSON pointer into the stored
payload would hold the row's label as stored, long and with white space the agent cannot see,
and the cite would fail on exactly the rows the feature is for. `response:<id>/<json pointer>`
still reads any field of the payload as it stands.

### 5.6 The references list

A report's references list names a `filing:` ref as `FMP filing report of fiscal <year> <period>,
<sheet>: <label>, column <col> (<words>), observed <day>`: the year and the period of the stored
call, the sheet's served name, the row's served label, the column and the day the response was
observed. So the reader sees which filing, which row and which period a figure came from.

A column's words: the cell at the column of the sheet's row labelled `items` (the column's date,
`Sep. 30, 2026`), with the title row's cell before it (the span, `3 Months Ended`) where the title
row is as wide as the `items` row; on a sheet with no `items` row, the title row's cell. A column
with no such words is named by its index alone. A `filing:` ref has no period, so the check
cannot catch a figure cited from the wrong column; the words are how the agent and the reader see
it (the whole-branch review's finding).

## 6. The MCP tools

Four tools join `TOOL_NAMES`. `quarters` follows `financials` among the reads. The other three
follow `pe_history` at the end of the vendor pass-throughs, in this order. Each is one call to its
route and answers the route's JSON.

- `quarters(symbol)`: 7.1.
- `filings(symbol, forms?, from_date?, to_date?, from_row?)`: 5.1; `from_date` and `to_date` are
  the route's `from` and `to`, `from_row` its `fromRow`.
- `filing_report(symbol, year?, period?, sheet?, from_row?, row?, col?, offset?)`: 5.2.
- `filing_search(symbol, year, period, text)`: 5.3.

They need no identity, as the other reads and pass-throughs.

## 7. The quarters

### 7.1 `GET /api/companies/{symbol}/quarters`

A company read beside `financials`, with no vendor call: `symbol`, `currency` (the reporting
currency, as `financials` names it), `quarters` and `otherCurrency`. It is 404 without statements,
as `financials` is. `financials` itself does not change: with the quarters in it, its answer would
pass the size goal.

- `quarters`: the newest eight stored periods of the quarterly statements that are in the
  reporting currency, oldest first. The refresh fetches eight quarters a run and the store keeps
  every period it ever stored, so the read is capped and the list does not grow.
- A period is `{period, periodEnd, fiscalYear, fiscalPeriod}` and one figure a line, `{value,
  unit, ref}` as `financials` gives its figures. The lines are the trailing figures'
  (`TrailingFigures`): revenue, operating income, net income, diluted EPS, stock compensation,
  cash from operations, capital spending, dividends, buybacks, equity issued, interest expense and
  depreciation.
- `period` is the stored fiscal label, `<fiscalYear>-<fiscalPeriod>` (`2027-Q1`), the form a
  consensus quarter already takes (`estimate:MSFT/2027-Q1/eps`).
- A quarter's figure for a line is that period's own term in the trailing figure's sum, signed
  and read as the trailing figures read it. So where the trailing figures are the sum of four
  quarters, the newest four add to the trailing figure of every line both hold; not on the
  fiscal-year fallback, and a half-yearly reporter's newest two add.
- A period in another currency than the reporting one is left out and counted in
  `otherCurrency`: the trailing figures do not sum such periods either. A period with no
  currency on file counts as the reporting one's, as the trailing figures read it.
- A half-yearly reporter's stored periods are its half-years, served by their stored labels.
- A period without a fiscal year or a fiscal period on file is left out. Two periods with one
  label: the one with the later period end is served (*my call*).
- The diluted EPS is the statement's as stored. On a row flagged `split-pending` or
  `basis-scaled` it may sit on another share basis than the quote's; the playbook says so.

### 7.2 The `fact:` ref of a quarter

`fact:<symbol>/<line>/<period>` takes a third period form beside the fiscal year and `ttm`: the
stored period's label (`fact:MSFT/revenue/2027-Q1`), whatever label the store holds. It resolves to the figure of that period and line
as 7.1 reads it, for any stored period in the reporting currency, the newest eight or older, with
the line's unit and the quarter as its period, so a cite's period `2027-Q1` (or `2027Q1`) fits and
another is `wrong period`. A period in another currency, or not on file, resolves to nothing. The
references list names it as it names a year's ("the revenue line of Q1 of fiscal 2027 on file").

No version changes: the mechanical method, the policy, the review and the secondary versions stand,
since no stored value changes its meaning (*my call*).

## 8. The playbook

`playbook/fairband-research/SKILL.md` and its references change with the tools:

- **Step 3** names `quarters`.
- **Step 4** reads Fairband first. `filing_report(symbol)` lists the reports FMP holds;
  `filing_search` finds a sentence or a label in one; `filing_report` with a sheet reads a table.
  A number cell of a sheet is cited as the row's ref plus `/<col>`, with no finding: the sheet's
  title names the scale (`$ in Millions`), the cite is the number as the cell holds it, and the
  scale word stands outside the cite. A sentence of a note is a finding whose source is `{kind:
  "filing", ref: "response:<responseId>", note}`, the note naming the report and the sheet.
  `filings(symbol)` gives the link of every filing. The host's own tools read only what Fairband
  does not hold: an 8-K's exhibits (the press release, recast figures), the 10-K's Item 1, the
  MD&A, the risk factors, the proxy statement and a filing FMP holds no report for (another
  company's S-1). A filing opens by its `finalLink`, an exhibit by the filing's `link`. Another
  listed company's 10-K or 10-Q is read with `filing_report` under its own symbol, and a figure
  from it is a finding, since a `filing:` ref names a cell of the report's own company. A sheet's
  columns are periods: the agent reads a column's words before it cites a number. A cell is at
  its sheet's scale, so it is not put through `derive` with a figure in full units.
- **Step 5**, part 2: the quarter's figures are `quarters`' figures, cited by their `fact:` refs.
  The sentence that sends the agent to the 10-Q or the press release for them goes. A quarter's
  EPS on a row flagged `split-pending` or `basis-scaled` is checked against the note first.
- **A rule on subagents**, in "The rules": before a subagent is briefed to fetch a figure, check
  what Fairband holds: the statements, the quarters and the filing report. Brief a subagent only
  for what is not there, and give it the document's link.
- `reference/tools.md` names the four tools; `reference/citations.md` names the `fact:` quarter
  and the `filing:` ref.

`tests/test_playbook.py` pins the tools each step names and the ref forms; it changes with them.

## 9. Documents

- `docs/method.md`: 16.2's `fact:` row takes the quarter, and the table takes the `filing:` row;
  the passages that describe the pass-throughs and the agent's reads take the three kinds, the
  routes, the budget and the caps, and the `quarters` read. The builder finds the passages; the
  document stays the statement of what runs.
- The Methodology page changes only if it names the ref forms or the agent's tools; the builder
  checks.
- `docs/backlog.md`: B-142's SEC fetch stays open for what FMP lacks; the plan's parked findings
  move there at its end, as CLAUDE.md says.

## 10. Constraints

- CLAUDE.md's: no key printed, logged, stored or committed; no vendor data committed. Every
  fixture is synthetic: an invented company, a hand-made report of a few sheets in FMP's shape.
- `financial-reports-dates` answers links. They are dropped from the answer; the stored payload is
  scrubbed of the key as every stored payload is, and a test pins that a key inside a link does
  not reach the store.
- The builder's subagents make no live vendor call. The live check is the controller's, after the
  merge (section 12).
- The checks of CLAUDE.md pass before every commit; commits follow its message rule.

## 11. Tests and acceptance

- The three kinds: the call each makes, the reuse key, the 30-day reuse of a usable report, an
  `Error Message` payload stored with its error and never reused, the bad `period`.
- The routes: each view of 5.2 on a synthetic report; the caps and the budget (a 100-row answer
  with `nextRow`, a page that the budget ends before 100 rows, a cut cell with `chars`, a
  20,000-character page with `nextOffset`, 20 hits with `more`); the white space rule; every
  refusal of 5.4; the header rule.
- `filing:`: a row's ref plus `/<col>` resolves through `reports.refs` to the cell's number, for a
  sheet name that holds a space, a comma, an apostrophe, a `/`, a `~` and a no-break space; the
  references list names the cell (5.6); a report that cites a cell, the scale word outside the
  cite, passes the check.
- The filing list: the default window from the clock, the default form filter, `forms`, `all`,
  `count`, `leftOut`, `nextRow`, `truncated`.
- The MCP tools: the names in order, the arguments, one call each.
- `quarters`: the newest eight oldest first with refs; the newest four add to the trailing figure;
  a period without a label and a period in another currency left out, the second counted.
  `fact:<symbol>/<line>/<YYYY>-Q<n>` resolves, with its unit, its period check and its words in
  the references list; a report that cites a quarter passes the check.
- The playbook: the steps' tools, the ref forms, the sentences of section 8.
- Acceptance, live, after the merge: for MSFT, `filing_search` for "not yet commenced" in the
  10-Q of fiscal 2027 Q1 answers the lease row with 364.6; the row's ref plus `/0` resolves to
  364.6; `filings` lists the 10-Q of 28 Oct 2026 with its link; `quarters` lists eight quarters
  whose newest four revenues add to the trailing revenue; no answer of these is longer than 40,000
  characters as the MCP tool returns it.

## 12. Left to the builder

- The module and function names, the dataclasses, the exact JSON key casing (camelCase, as the
  API's other answers).
- Where the quarter figures are built (beside the trailing figures) and how the route and the
  resolver share one reading.
- A row of a sheet that is not a one-key object with a list: serve it so that nothing is lost and
  no cap is passed; say how in the route's docstring.
- The wording of the tools' descriptions and of the playbook's sentences, in the playbook's
  register.
- Whether `method.md` needs a new subsection for the filing reads or a paragraph in an existing
  one.

After the merge, the controller's steps: restart the server from main; restart the Claude Code
process that runs research, so its MCP process loads the new tools; run the acceptance of section
11; record the readout in the decision log.

## Decision log

| Date | Decision |
|---|---|
| 2026-11-11 | The founder, on the Microsoft session: FMP should serve the filings, and Fairband should make them available. The live probe agreed: 6 of the 11 EDGAR findings of report 16 are in FMP's `financial-reports-json` (OpenAI revenue of $10.0 billion in the quarter and $24.1 billion in fiscal 2026, the 24% stake, the leases not yet commenced of $364.6 billion and $329.1 billion, Azure revenue of $33,165 million), and 5 are not (three recast figures of an 8-K exhibit, the employee count of Item 1, Anthropic's S-1). The founder: "build items 1 to 4 now", by the superpowers method, and "skip" the questions. |
| 2026-11-11 | Claude's calls, the founder having skipped the questions: `filing_search` beside `filing_report`, since a note is one cell of up to 91,000 characters and the facts wanted were all found by text; the reports on file as `filing_report` without a period, from a third pass-through kind; the scale word outside a cell's cite; the caps (100 rows, 2,000 characters a cell in a sheet, 20,000 a page, 20 hits, 300 characters each side); served text with white space collapsed; the filing list's default of one year without the ownership forms; 30 days of reuse for a report; the quarters as a third period of `fact:`, their lines the trailing figures', the EPS as stored; no version change; no page code change; no sec.gov fetch. |
| 2026-11-11 | The builder check's five questions, each settled by Claude. (1) The caps alone do not hold an answer under 40,000 characters, and the MCP process prints JSON indented: every list is held to 20,000 characters of compact JSON, the filing list pages by `fromRow` as a sheet does, and `leftOut` is a count. (2) The store keeps every quarter it ever stored, and `financials` with the quarters would pass the size goal: the quarters are a read and a tool of their own, `quarters`, the newest eight, and `financials` does not change; the founder's item 3 named `financials`, and this is the one place the build departs from its letter. (3) A row's label as stored holds white space the agent cannot see, so a JSON pointer through it would fail: a cell is cited by a new form, `filing:<responseId>/<sheet>/<row>/<col>`, indexes and the sheet's served name alone. (4) The references list names the filing, the sheet and the row of a `filing:` ref. (5) A stored quarter in another currency than the reporting one is left out of `quarters` and counted, and its `fact:` ref resolves to nothing, as the trailing figures do not sum such periods. |
| 2026-11-12 | The build's rulings (Claude, as controller of a subagent-driven build; every implementer and reviewer on Opus 5.5 at xhigh), each in place above. From the tasks: a `filing:` ref resolves a string cell as it is served; a row that is not a label with its cells has no ref; an index asked of an empty sheet or row is refused "<name> is out of range: there is none"; a short search text is refused before the report is fetched; the refusals run in the order header, no key, parameters, fetch, view, the no-key 503 before the parameters as the vendor route has it; a filing-list row that is not an object is dropped and counted; the playbook narrows "another company's filings" (a listed company's report is read by `filing_report` under its own symbol, its figures findings) and opens an exhibit by the filing's `link`; the agent cites a cell by copying the row's `rowRef`, never a ref built by hand. From the whole-branch review, which found no Critical issue and two Important ones: the budget is measured as the answer is printed, 30,000 characters a list, and the sheet list is budgeted and paged (the compact measure let a 60-column sheet page print at 63,172 characters); a cited cell's column is named, in the sheet view's `columns`, in a hit's numbers and in the references list, since a `filing:` ref has no period and a wrong-column cite passes the check. Also from it: the `sheet` asked for is served before it is matched; a lower-case `period` is read; a number as printed finds a number cell; the `fact:` reader resolves any stored label; a hit carries no ref into a second sheet of one served name; the newest four add to the trailing figures only where those are the sum of four quarters; a window before the calendar's first year is a 400; one test runs a searched cell through a published report. Not built, in the backlog: a huge ref id that raises in the `filing:` and `response:` readers, a retention rule for stored filing reports, and a test of a quarter without a cash-flow period. |
