# The company page's Research tab: design

Status: written 2026-11-17 for backlog item B-218, on the founder's requests of that day, quoted
in the decision log. The founder decided that the report moves into the Research tab, under the
company's head and tabs; that the agents write nothing new for it (way B of section 6); and the
look (version 3 of the mockup, which is version 1 with the chart corrections: "it looks good",
then "I prefer the apple version. Let's just go with that"). Every other choice below is
Claude's, marked *my call* where it is more than a reading of those requests, and can be
overturned as any other. Not built.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value: the method stays `fairband-mechanical/1.5` and the policy v16. The schema stays at
009 and nothing new is stored. No agent's write changes: a report keeps its twelve sections, the
number check, the playbook, `report_submit` and the Markdown export as they are. The changes
are in `src/fairband/web/` (one read, the page's scripts and its stylesheet), one export of the
design system's vendored bundle, and the documents (section 10).

This design stands on the company page's (`2026-11-16-company-page-design.md`, "the page's
design" below) and on the report's (`2026-11-06-tier-2-agents-design.md`, 13.1 and 18.4, "the
report's design" below). Their rules hold here unless this document says otherwise: the head on
every tab (the page's design, 7.2), loading and failure (7.5), the reads (10.3); the text's
shape, the cites, the references and the two appendixes (the report's design, 13.1).

## 1. What this is

The company page has an Overview, a Financials and an Estimates tab. Its fourth name in the
row, Research, is a link to the report page (`#report/<symbol>`), a view older than the company
page. A reader who presses it loses the company's head and the tabs. The report page then
draws the report as one column of text about 700 px wide: Apple's is 23,519 px tall in a
2,000 px window, with no list of its sections, and its references and its two appendixes,
always open, are 42% of that height.

The Research tab holds the report on the company page. A list of the sections stands at the
left. Each section is a panel. The records the database already holds for a section (the
report's value and its levels, the kill criteria and their states, the judgments, the news
sources, the sensitivity grids, the changes to the inputs) are drawn beside its text as cards.
The references and the appendixes stay closed until the reader opens them. A second view of
the tab, Records, lists the company's records on file.

## 2. Goals

1. Research is a tab of the company page: the head and the tabs' row stay.
2. A reader reaches any section of a report in one press, and reads its text at the reading
   width with its charts and its records beside it.
3. What the database holds as records is drawn as records, not only as sentences.
4. Every report and revision of the company is one press away, and the company's records on
   file are on the tab.
5. The 33 reports on file draw in the new form as they are stored.
6. A link to the old report page still opens the report.

## 3. Non-goals

- Any change to what an agent writes (way C of section 6). Three were named with the founder
  and left: typed fields for the thesis's claims; a report without the Recent news section;
  a Risks section that does not repeat the risks of the Summary and of the bear case. Each
  changes the playbook and the server's check. They are filed in the backlog (section 10).
- The valuation's mechanics outside a report (B-220): the inputs, the route's sections, the
  charge and the flags of the latest snapshot. Appendix A lists a report's inputs, as today.
- A write from the tab. No override is added or dropped, no kill criterion is marked, and a
  note is taken in the head's Notes control alone, as on every tab.
- A search, a filter or an export of the records.
- A new chart, or a change to one of the design system's charts.
- The Investor relations tab (B-217) and ownership (B-71).

## 4. Anti-goals

- **A rule that hides or rewrites an agent's sentence.** A layout rule moves a block or sets
  two blocks side by side. It never drops one, with one exception: the Summary's first line
  where it is exactly `Stance: <word>.` and the word is the report's stance, which the bar
  states (7.2).
- **A figure no record holds.** A card draws stored records and the read's fields. The page
  computes none.
- **Two readers of the text's shape.** The tab reads a section's blocks with the design
  system's own reader (9), so the tab and the Markdown export never differ on what a list or
  a table is.
- **One company's report under another's head.** A revision of another company is refused, as
  the report page refuses it.
- **A layout that fails on a report whose text has another shape.** Every rule of 7.4 has a
  fallback: the blocks in their order, as the report page draws them today.

## 5. The evidence (the live database at refresh 67, read-only, 2026-11-17)

- 33 reports of 31 companies are on file (QCOM and AVGO have two revisions). 30 rest on a
  review; AAPL, ROAD and AZN changed no input. One is a valuation review (AVGO, revision 2).
- Apple's report on the report page, in a 2,000 px window: 23,519 px. The head, the brief and
  the meter 861 px; the twelve sections 12,762 px; the references (185) 5,596 px; Appendix A
  3,814 px; Appendix B 486 px. The same report in the mockup: 10,235 px.
- A report is stored as sections of parts, text and cites (`reports.sections`), not as a file.
  The records beside it are in their own tables: 132 judgments, 137 kill criteria (all open),
  153 guidance records, 1,045 findings, 211 news items, 59 overrides, 424 reviews, 2 secondary
  valuations, 16 notes, 54 sensitivity readings.
- The shapes the layout rules read, counted on the 33 reports:

| Shape | Reports |
|---|---|
| The Summary opens with `Stance: <word>.` | 33 |
| The Summary has a list named "Reasons for" (2 more write "Reasons for the stance") | 31 |
| The Summary has a list named "Main risks" (1 more writes "Main risks to the stance") | 32 |
| The Summary has a list named "What would change the view" | 33 |
| The bull and bear section is two paragraphs that open "The bull case" and "The bear case" | 33 |
| The financial section has four or more paragraphs that open with a bold lead word | 30 |
| The earnings call section holds a table | 33 |
| The industry section has one list under a short line that names it | 26 of 31 |
| The thesis names its claims Accepted, Held open or Rejected | 32 |

- 15 of the 33 reports rest on a snapshot priced on another day than its data's (NVDA: data
  of 10 Nov, priced 9 Nov).
- FRVO's report rests on a review with no value and on a secondary valuation. RKLB's rests on
  a refused snapshot that its review values.
- 6 of the 137 kill criteria carry no report's id: ADBE's one, which its report cites
  (`kill:133`), and five of PLTR's, which no report cites. 8 of the 211 news items carry none,
  all PLTR's. The ledger's rows for them name no work item, so nothing else ties them to a
  report.
- The ledger holds up to 192 rows a company (AVGO); the research read answers the newest 20.
- The thesis's claims have two shapes: sentences in one paragraph (AAPL) and a list (NVDA,
  ROAD). No rule draws both, so the thesis stays text (section 3).
- NVDA, FRVO and ADSK write the financial section with no bold lead word.

## 6. Approaches

**What changes.** (A) Layout only: the report in the tab, a section list, panels, the closed
parts. (B) A, and the records on file drawn beside the text. (C) B, and new fields an agent
fills (the Summary's lists, the bull and bear points, the thesis's claims). The founder asked
for a mockup of B and took it. B draws all 33 reports at once and changes no agent's write. C
changes `report_submit`, the check, the playbook, the export and `docs/method.md` 16, and
leaves the 33 reports in the old shape until they are written again.

**How the sections are drawn.** (a) New properties on the design system's `ReportReader`, for
the panels, the cards and the rules. (b) A script of the page that reads each section's blocks
with the design system's reader and lays them out itself. (b), *my call*: the layouts are this
page's, not a look every Fairband surface shares, and (a) adds many hand-kept patches to the
bundle (B-40). (b) needs one export from the bundle (9).

## 7. The tab

### 7.1 The address and the row

`#company/<symbol>/research` is the tab on the company's latest report.
`#company/<symbol>/research/<id>` is the tab on the report with that id, an earlier revision.
Research is the fourth tab of the row, after Overview, Financials and Estimates, a tab as the
other three: a press replaces the hash and reads the tab.

`#report/<symbol>` and `#report/<symbol>/<id>` open the tab on the same report, and the hash
is replaced by the tab's. The inbox's link to a report and the Overview's "Open the report"
name the tab's address. The report page's panel and its script leave (9).

An id that names another company's report, or none, draws the server's sentence under the
tabs as it arrives ("report 9 is NVDA's, not AAPL's"), and no report: a 404 of the tab's read
is the server's own sentence, as the detail's 404 is, since opening the page again would not
help. Any other failure of the read takes the page's sentence (its design, 7.5).

The tab shows no data date at the row's right end (*my call*): the bar states the report's own
dates, and each record carries its own.

### 7.2 The bar

Under the tabs' row, one bar:

- At the left, **Report** and **Records**, the tab's two views, Records with the count of the
  records on file. Report is shown first. The view is not in the address (*my call*).
- In the Report view, the report's line: its stance in the Stance column's chip, faded once
  the report's validity has ended, with the title the report page gives it; its mode; its
  revision; its date and time; who wrote it; "valid until" with the date; and, for a valuation
  review that reuses a full report, "reuses the full report of" with that report's date, as
  the report page's line says it today. Under the bar, "No full report to reuse." for a
  valuation review that has none, as today.
- At the right, in the Report view: **Footnote marks**, a switch, off at first, the choice
  kept in the browser as the Financials tab keeps its unit; and **Download .md**, as today,
  its refusal in one sentence under the bar.
- In the Records view, in the line's place: "The company's records on file, from any
  report."

Request research is in the head, as on every tab. The report page's second copy of it leaves.

A company with no report: the Report view draws "No report yet." and nothing else. Records
draws what is on file.

### 7.3 The section list

At the left of the Report view, 196 px wide, a list that stays in view while the report
scrolls:

- **The report**: the sections' headings in their order, twelve or ten.
- **Kept closed**: References with their count, Appendix A, Appendix B.
- **Reports on file**, with the count: every report and revision of the company, newest
  first, each with its date, its revision, its mode and its stance. The one shown is marked. A
  press on another opens it at its address.

A press on a name scrolls to its panel, and opens it where it is one of the closed three. The
section in view is marked as the app marks a selection: `surface-selected` and a 2 px `accent`
left edge.

Below 980 px the list is a row above the report that scrolls sideways, and the reports on file
stand in a line under the bar (*my call*).

### 7.4 A section's panel, and the layout rules

Each section is a panel on `surface-raised` with its heading. Inside:

- **Text** (a paragraph, a list) at the reading width: 16 px on a 24 px line, 72 characters,
  the founder's ruling of 2026-11-08.
- **A wide table** (more than four columns, or a cell above 44 characters) across the panel.
  It takes the panel's whole width where a cell is above 44 characters, else its own.
- **Cards** at the right of the first run of text, in a column that stays in view while the
  panel scrolls. Below 980 px the cards stand under that text.

A **named block** is a list or a table directly under a line of 90 characters or fewer that
ends in a colon. The line is its name.

The rules, by heading. Where a rule's shape is absent, the section's blocks are drawn in their
order, text and wide tables, as the report page draws them today.

1. **Summary.** The value card (7.5) beside the text. The first line is left out where it is
   exactly `Stance: <word>.` and the word is the report's stance. Two or more named lists in a
   row stand side by side, under the text before them; what follows them stands under them.
2. **Any section with no card of its own** (The business, Industry and competition, The
   thesis): a named list, and a named table that is not wide, become cards beside the text,
   each under its name.
3. **Financial performance and health.** A paragraph that opens with a bold lead word stands
   beside the charts of its group. The lead word is the bold text at the paragraph's start,
   read without its full stop and without regard to case: one that starts with "growth" names
   the growth charts; one that starts with "cash", the cash flow's; one that holds "solvency"
   or "balance", the solvency's; one that starts with "return", the returns'; one that holds
   "capital allocation", its own; one that holds "quality", the quality scores'. A group is
   named once, by the first paragraph that names it. A paragraph whose lead word names no
   group, and a block that is no such paragraph, stands as text in its place. A group no
   paragraph names stands in a row of its own after them. Where fewer than four paragraphs
   name a group, every chart stands first, by group, and the text follows.
4. **The last earnings call.** The three charts by quarter in one row, then the blocks.
5. **The bull case and the bear case.** Where the section is exactly two paragraphs that open
   "The bull case" and "The bear case", they stand in two columns, each under those words as
   its label, the words taken off the paragraph's start.
6. **Valuation.** Cards: each sensitivity grid the section cites and the secondary
   valuation's grid, as today's charts draw them; then Changes to Fairband's inputs (7.6).
7. **Price and multiples.** Cards: the price against the band, the trailing P/E, the forward
   P/E, as today's charts draw them.
8. **Recent news.** A card, "The sources on file": the news items that carry this report's
   id, newest first, each with its date, its address's host and its headline, a link where the address
   is a web address.
9. **Risks and kill criteria.** A card, "Kill criteria", with "n open of m": the criteria that
   carry this report's id and the criteria the report cites (`kill:<id>`), each once, each with
   its state today, the day of that state, its text and the state's
   reason where it has one.
10. **Key judgments.** Under the text, one card a judgment in a row: its name (Phase, Moat,
    Belief, Return on new capital, Target margin), "stands" or "changed" (changed where the
    judgment names an override), and the decision.

### 7.5 The value card

"The report's call", with what it rests on in its head: "on the data of" and the date, then
"priced that day", or "priced" and the price's date where it is another day.

- The report's value a share and its kind. The value is the first of three that exists: the
  review's, where the report rests on a review that has a value, `reviewed`; the snapshot's,
  `mechanical`; the secondary valuation's, where it is above zero, `reviewed` with "secondary
  valuation", as the report page's head names it today.
- The design system's meter (`BandMeter`) on that value, its four levels and the price of the
  report's snapshot, whole: its own line of the price, the designation's word and the gap,
  then the three zones, the value's mark and the price's.
- The three levels in words: buy below, close to the value from and to, trim above.
- One caption: "Valid until" and the date; "Today the mechanical value is $198.26 and the
  price $352.78." (reviewed where the company's value today is); and, where the report's value
  is a review's and its snapshot has a mechanical value, "The mechanical value was $451.42."
  (*my call*; the mockup shows a report with no review).

Money is written as the design system writes it, to cents, so the card's figures and the
meter's are the same (*my call*; the mockup writes the value and the levels in whole dollars).
The word and the gap are the report's value against the price of the report's snapshot, worked
out by the server (8.1). Where no record gives a value, the card draws the refusal's sentence
and no meter.

### 7.6 Changes to Fairband's inputs

A card in the Valuation panel. For a report with no review: "The report changes no input, so
its value is the mechanical value." For a report that rests on a review, one line a change, in
the bridge's order (*my call*; the mockup shows no such report): the input's label as the
bridge names it, its figure before and after in the input's unit, and its effect on the value
a share, signed, to cents; the line's refusal where it has one. Appendix A keeps the whole
bridge and each override's record.

### 7.7 A cited number

A cite stays the design system's: the figure in the mono face with a dotted line under it. On
the tab it takes the text's colour, and `accent` on hover and on focus. Its source, the
reference's number and its words, shows in a small box on hover and on keyboard focus. Its
footnote mark, `[n]`, is hidden until Footnote marks is on. In a table the dotted line is left
out, and in a card a table's cells after the first are set right.

### 7.8 The closed parts

After the last section, three panels, closed when the tab opens, each with one line in its
head: References and their count; Appendix A, "the audit of the records the report rests on";
Appendix B, "the glossary" and its count. Opened, each draws what the report page draws
today: the references numbered, in two columns where the width allows; Appendix A's nine
parts; the glossary. Which are open is not kept.

### 7.9 The charts

The charts are the report page's (`charts.js`), on the same series, with the same titles,
notes and rules: the trailing twelve months, the estimates, the ROIC years left out. They sit
on their section's panel, with no panel of their own. In a pair of rule 3 and in rule 4's row
they are drawn smaller, by the charts' `height` (*my call*: 120 px; the mockup's charts are
its own and simpler, section 13). A read the server refused draws its sentence in the chart's
place, as today.

### 7.10 Records

The Records view: one panel a kind, each with its count, each a table, newest first, "None on
file." where it is empty. The company's records of nine kinds, whatever report wrote them. The
count beside Records in the bar is the sum of the rows the panels draw.

| Panel | Columns |
|---|---|
| Kill criteria | the state; the text; the day set; the state's day and reason |
| Guidance | the metric; the period; the range; the midpoint; the basis; the call's day; `current` or `superseded`, today's state |
| Overrides | the input; from; to; the state; the reason |
| Notes | when; the note |
| Reviews | when; the value; the mechanical value; the count of overrides inside; the designation, or the refusal. A press on a row draws its bridge under it |
| Secondary valuations | when; the form; the value a share; the reason |
| News items | the date; the headline, a link; what happened |
| Findings | as of; the period; the figure in its unit and currency; the words; the kind of source |
| Ledger | when; the kind; what was written; by whom. The newest 20, and its head says so with the count on file ("the newest 20 of 192") |

The judgments have no panel (*my call*): a judgment belongs to its report, whose Key judgments
panel draws it, and the reports on file are one press away.

### 7.11 Loading, failure, print and width

Loading and failure are the page's (its design, 7.5): the tab's failed read is one sentence
under the tabs. The series the charts read land one by one after the report, as today.

Print draws the Report view alone: the company's name and ticker, the bar's line, every
section with its cards under its text, and the three closed parts, open. The app's header,
the head's controls, the bar's controls and the section list are not printed. The report
page's print rules for an agent's table hold.

The tab takes the company page's width. Below 980 px it is one column.

## 8. The data

### 8.1 The read

`GET /api/companies/{symbol}/page/research`, with `?report=<id>` for a revision. It answers
from the store alone, as the page's other three reads do:

- `quote`: the stored quote, as every tab's read carries it for the head.
- `reports`: the company's reports and revisions, newest first, without their sections.
- `report`: the report shown, whole, as `GET /api/reports/{id}` answers it; the latest where
  no id is given; `null` for a company with none.
- `call`: the value card's figures, from the records the report rests on; `null` without a
  report. Its `value`, `basis` and `note`, by 7.5's order of three; its four `levels`, the
  same record's; `priceToValue` and `designation`, that value against the snapshot's price on
  the policy's edges, as `rows.standing` works them out, never the word stored with a record;
  the `price`, `priceDate` and `dataDate` of the report's snapshot; `validUntil`;
  `mechanicalValue`, the snapshot's, `null` on a refused one; `refusal`, where no record gives
  a value, the review's where the report rests on one, else the snapshot's.
- `ofReport`: the records the report's cards draw: its `killCriteria` and its `newsItems`, by
  the rules of 7.4's 8 and 9.
- `records`: what `GET /api/companies/{symbol}/research` answers, with the company's reviews
  and secondary valuations, and `ledgerCount`, the count of the company's ledger rows.

It answers 404 with the page's sentence for a company with no snapshot, and 404 with "report
<id> is <symbol>'s, not <symbol>'s" for an id that is another company's, or "no report <id>"
for one that names none.

### 8.2 The other reads

Unchanged, and read by the tab as the report page reads them, each on its own after the
report lands: the financial tables, the price history of five years, the band's history, each
sensitivity reading the report cites, and the multiples history. The multiples history is the
tab's one read that may call a vendor, as it is the report page's; it carries the request
header. The head's detail gives today's value and price for the value card's caption.

`GET /api/reports/{id}`, `GET /api/companies/{symbol}/reports` and
`GET /api/companies/{symbol}/research` stay for the agents' tools and the export.

### 8.3 Nothing new is stored

No migration, no new vendor call, no change to a refresh.

## 9. The page's code

- `controls.js` knows the tab (`COMPANY_TABS`) and the report's id after it, and sends
  `#report/...` to the tab. `report` leaves its views. `company.js` gains the tab in its row,
  reads `page/research` with the id, and draws no link in the row.
- The tab's script, `company_research.js`, hangs on `companyPage.draw` as the other tabs do.
  It holds the bar, the section list, the panels, the cards, the closed parts and Records. The
  layout rules of 7.4 are plain functions over a section's blocks, apart from the drawing, so
  the tests run them in node.
- `report.js` leaves. What it draws that the tab keeps moves to the tab's script: the
  references, Appendix A's parts, the glossary, the download.
- `charts.js` stays. It gives its charts by group, so a group can stand beside its paragraph.
- The design system's vendored bundle exports the reader of a section's text in two steps,
  `Fairband.reportText.read(parts)`, the blocks, and `Fairband.reportText.draw(block,
  footnotes)`, one block's element. `ReportReader` calls the two and draws as before. One
  `fairband:` patch in `bundle.js` and one in `index.d.ts` (B-40).
- `index.html`: the report page's panel and its script tag leave; the tab's script joins; the
  stylesheet gains the tab's rules and loses the report page's that nothing reads.

## 10. The documents

In the same commits as the code they describe:

- `docs/backlog.md`: B-218 moves to Done at the end. New rows: the three non-goals of section
  3 that change an agent's write (the thesis's claims as fields; a report without Recent news;
  the repeated risks), each with the founder's words of 2026-11-17. B-220 stays open and loses
  "the records that the Research tab takes later". B-222 loses one copy of `read` and
  `refused`.
- `docs/method.md`: the sentences that name the report page name the Research tab. No method
  version moves, and the Methodology page changes only where it names the report page.
- The page's design and the report's design: one line each in the decision log, that the
  report page is the Research tab since this design, and where.
- The design system's documents in the archive and the vendored copy: `ReportReader.md` gains
  `reportText`; `CompanyReport.md` says that in the app the report stands in the company
  page's Research tab, with this design's name. The artifact's side joins B-221.
- The module docstrings that name the report page or count the page's tabs and reads.
- The mockup's sources stand beside this design, in `2026-11-17-research-tab-mockup/`.
- This design's decision log: the readout and anything the build overturned.

## 11. Tests the builder must write

Fixtures are synthetic or hand-trimmed: no vendor data and no report on file is committed.

- **The read.** A company with two revisions and no id: the latest; with an id: that one; an
  id of another company and an id that names none: the two 404s; a company with no report:
  `report` and `call` null and the records there; `call` for a report with no review, with a
  review, with a review that has no value and a secondary valuation, on a refused snapshot
  its review values, and with no value at all, its refusal; the word and the gap at the
  report's snapshot's price where the review was stored at another; `ofReport` with a
  criterion of the report's id, one the report cites that carries none, one of another report
  and one with neither; the reviews, the secondary valuations and `ledgerCount` in `records`;
  no vendor call made (a transport that fails any call).
- **The addresses**, in node with the harness the page's tests use: the tab in the row; the
  hash both ways with and without an id; `#report/AAPL` and `#report/AAPL/9` replaced by the
  tab's; the inbox's and the Overview's links.
- **The layout rules**, each on a synthetic section and on its fallback: the stance line left
  out and kept (another word, more words on the line); one named list and three in a row; a
  named table narrow and wide; the financial pairs with six lead words, with three, with a
  group no paragraph names, with a lead word that names no group, and with two paragraphs that
  name one group; the two columns, and three paragraphs; a section with no rule.
  No rule drops a block: the blocks drawn are the blocks read, but the stance line.
- **The cards.** The value card for each `call` of the read's tests, "priced that day" and
  "priced" with a date, the caption's three sentences, the refusal; the changes card with none, with three lines, with a line's refusal;
  the kill criteria of this report alone, with a state that is not open and its reason; the
  judgments' "stands" and "changed"; the news sources' order, the host, no link for an address
  that is not a web address.
- **The bar and the list.** The report's line; the faded stance; a valuation review's reused
  report and the note of one that reuses none; a 404's sentence as it arrives;
  Footnote marks off at first, kept across a reload (a stub store), off where the store
  throws; the list's names for twelve and for ten sections; the reports on file and the one
  marked; a company with no report.
- **The closed parts.** Closed at first; the references' count; Appendix A's parts as the
  report page's tests read them today (`test_report_reader.py`), moved.
- **Records.** Each panel's rows from a synthetic answer, its count, "None on file."; a
  superseded guidance record; the ledger's head with 20 of more on file; the bar's count; a
  review's bridge on a press.
- **The export.** `reportText.read` and `draw` give, for the report reader's fixtures
  (`test_reader_blocks.py`), the blocks and the elements `ReportReader` gave before.

## 12. Acceptance

On the live data, after the build is merged and the server restarted (no migration, no
refresh):

1. Every one of the 33 reports opens in the tab with no error in the browser's console, and
   its sections, references and appendixes hold what `GET /api/reports/{id}` answers.
2. AAPL (no review), NVDA (three overrides, no lead words in the financial section, priced
   on another day than its data), AVGO (two revisions, one a valuation review), FRVO (a
   review with no value and a secondary valuation), RKLB (a refused snapshot its review
   values), PLTR (records that carry no report's id) and ASML (another currency) are read by
   eye in a browser, at 2,000 px and at 400 px, in both themes.
3. `#report/AAPL` and an inbox row's link open the tab.
4. The founder looks at the tab.

The readout goes in the decision log: the heights of the seven, and what the eye found.

## 13. Where the design and the mockup differ

- The mockup draws its own small charts. The build draws the report page's charts (7.9), so a
  chart has the design system's head, its basis chip, the trailing twelve months and the
  estimates. The mockup has no P/E chart, and its price chart is drawn by week against the
  report's levels; the build draws the price against the band by quarter and the two P/E
  charts.
- The mockup's source box and its meter are its own. The build uses the design system's cite
  and its meter, whole: the meter's own line holds the price, the word and the gap, which the
  mockup draws beside the value, and its figures are to cents, where the mockup writes the
  value and the levels in whole dollars (7.5). The mockup's "Price that day" is the head's
  "priced that day" or "priced" with the date.
- The mockup sets the figures of every table right, by reading each column. The build draws a
  table with the design system's reader, whose cells carry no kind: a card's table has its
  cells after the first set right, and a wide table's cells stand as the reader sets them.
- The mockup shows Apple's report alone, which rests on no review. The value card's kind and
  its third caption sentence (7.5), and the lines of the changes card (7.6), are this design's.
- The mockup's Records has no Reviews and no Secondary valuations panel (7.10).
- The mockup is not a view of the app: its header, its head and its buttons other than the
  tab's own are drawn for their place.

## 14. Left to the builder

- Whether the layout rules live in the tab's script or in one of their own.
- How the source box is drawn and placed, and how the native title is kept from showing a
  second one.
- The closed panels' element, and the scroll's behaviour on a press in the list.
- The stylesheet's names, and which of the report page's rules are kept under them.
- The charts' sizes in a pair below the widths the mockup shows.

## 15. Order of work

1. The read, with its tests.
2. The bundle's export, with its tests.
3. The addresses: the tab in the row, the id, the old links.
4. The Report view: the bar, the list, the panels and the rules, the cards, the closed parts.
5. Records.
6. Print and the narrow width.
7. The report page's removal, the documents, the acceptance.

## Decision log

- **2026-11-17, the founder's requests.** "When I click the research tab, the company page sub
  menu vanishes." "The research page looks terrible … my thinking is for agents to populate
  sections of the research in the database, so that when we display the research, we pull
  different content from the db and the content looks better." Claude found that the report is
  stored by section already, with the records beside it in their own tables, and that the
  layout causes most of the fault (section 5), and gave three ways (section 6).
- **2026-11-17, way B.** The founder: "show me a mockup for B". On version 1: "it looks good."
- **2026-11-17, the founder's four questions on version 1**, and Claude's answers. The value
  is mechanical for Apple because the agent changed no input. The report's news list differs
  from the Overview's feed: it is the agent's choice of events on the report's day. A kill
  criterion is a test with a yes or no answer that an agent checks later; the bear case is an
  argument. The key judgments are the agent's rulings on the inputs the engine sets by rule.
  Version 2 changed the value card, the news, the kill criteria's name and the judgments, and
  added NVIDIA's report.
- **2026-11-17, the look.** The founder, on version 2's list of changes: "with the exception
  to the corrected charts (number 8), I prefer the apple version. Let's just go with that."
  So the look is version 1's with the chart corrections (version 3 of the mockup), and no
  agent's write changes. Claude reads this as "leave" on the three choices put to him: the
  news section, the repeated risks, the thesis's claims (section 3).
- **2026-11-17, the builder check.** A reviewer read this design as a builder and asked six
  questions. The code and the live data answered each, so none went to the founder. The
  cards' kill criteria are those of the report's id and those the report cites, and its news
  items those of its id (7.4; six criteria and eight news items carry no id, section 5). The
  card's value is the first of three that exists, and its word and gap are worked out at the
  report's snapshot's price (7.5, 8.1). The bar names the full report a valuation review
  reuses (7.2). Records draws nine kinds, the guidance with today's state and the ledger's
  newest 20 (7.10). The lead words of the financial section are matched as the mockup matched
  them (7.4). The meter is the design system's whole, with money to cents, and a 404 of the
  tab's read is the server's sentence as it arrives (7.5, 7.1).
- **2026-11-17, approved.** The founder: "approved". The plan is
  `docs/superpowers/plans/2026-11-17-research-tab-plan.md`. Writing it set one sentence of 7.7:
  a cite in any table has no dotted line, since the reader's cells carry no kind.
- **Claude's calls, for the founder to overturn**: the sections drawn by a script of the page
  on one export of the bundle (6); no data date on the tab and the view not in the address
  (7.1, 7.2); the list's form below 980 px (7.3); the kind and the third caption sentence of
  the value card for a report that rests on a review, and its money to cents (7.5); which
  records a report's cards draw (7.4); the lines of the changes card
  (7.6); the report page's charts at a smaller height (7.9); the Records panels and the
  bridge on a press (7.10); one read for the tab (8.1).
