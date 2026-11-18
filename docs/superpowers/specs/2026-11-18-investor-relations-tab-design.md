# The company page's Investor relations tab: design

Status: written 2026-11-18 for backlog item B-217, on the founder's requests of that day and of
2026-11-16, quoted in the decision log. The founder decided what the tab holds (the earnings
calls and the filings), that a filing is a link to the SEC and not a text read inside Fairband
("I think links are enough"), that the insider forms stay out of the list until asked for, that
press releases wait in the backlog, and the look (version 1 of the mockup: "It looks good").
Two of his rulings for the whole page shape this design too: the page's data is stored, not
fetched when a page opens (section 6), and Fairband computes no new figure for it (7.4). Every
other choice below is Claude's, marked *my call* where it is more than a reading of those
requests, and can be overturned as any other. The founder approved this design on 2026-11-18
("Approved"); the plan is `docs/superpowers/plans/2026-11-18-investor-relations-tab-plan.md`.
Nothing is built yet.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value: the method stays `fairband-mechanical/1.5` and the policy v16. The schema stays at
009. A refresh gains two calls a company and, for a call not yet stored, a third (8.1). No
agent's write changes; one agent's read, `transcript_dates`, stores a vendor's error as an
error from now on (8.1). The rest is in `src/fairband/web/` and `src/fairband/vendors/` (three
reads, their readers, one page script and its stylesheet rules) and the documents (section 10).

This design stands on the company page's (`2026-11-16-company-page-design.md`, "the page's
design" below). Its rules hold here unless this document says otherwise: the head on every tab
(7.2), the data date (7.4), loading and failure (7.5), the refresh's page calls (10.1), the
reads (10.3). The rule on vendor reference data holds too (`CLAUDE.md`): the tab's figures and
documents are shown plain, with no cite, no chip and no vendor's name.

## 1. What this is

The fourth of the company page's five tabs, between Estimates and Research: **Investor
relations**. It holds what a company tells its investors, as the vendor carries it: its earnings
calls, read inside Fairband, and its filings, each a link to the SEC's site. The founder's
words for it (2026-11-16): "all related filings and investor call logs".

## 2. Goals

1. A reader finds a company's earnings call by its quarter and reads its transcript in the
   page, with the quarter's reported EPS and revenue beside the analysts' estimates.
2. A reader finds a company's filing by its form and its date and opens it on the SEC's site in
   one press.
3. The tab opens from the store: its lists and its newest call wait on no vendor.
4. What a refresh stored and what an agent fetched for a report are the same copies: one store,
   read by the tab and by the agents' tools.

## 3. Non-goals

- A filing's text inside Fairband. The founder: "I think links are enough." The agents' filing
  reads (`filing_report`, `filing_search`) stay as they are and draw on no page.
- Press releases (B-249).
- Insider trades and ownership as figures: the page's design keeps ownership for a later tab.
  The insider forms are in the filings list, behind their own filter.
- News, estimates, price targets, guidance records: the Overview, the Estimates tab and the
  Research tab's Records hold them.
- A figure Fairband computes, such as the gap between a reported figure and its estimate (7.4).
- A summary or a judgment of a call by Fairband. The tab shows the vendor's text; an agent's
  reading of a call is in its report.
- A search across calls or across companies.
- Every older transcript stored ahead of its first reading: 85 calls a company at AAPL's depth.

## 4. Anti-goals

- A tab whose first draw waits on a vendor (the page's design, section 4: "No block's first
  draw depends on a vendor call").
- A transcript fetched again each time a reader opens it.
- A failed page call that costs a valuation: the refresh's new calls are optional, as the
  page's others are.
- A label the tab cannot stand behind: the questions' start is marked only where the rule of
  7.4 finds it.
- Red and green (the page's design, section 4).

## 5. The evidence (the live store, read-only, 2026-11-18)

- **What a refresh stores today.** Of this tab's data only `earnings`: 12 rows a company, each
  a quarter's `date`, `epsActual`, `epsEstimated`, `revenueActual`, `revenueEstimated`,
  `fiscalPeriod` and `fiscalYear`, every figure in US dollars (`vendors/page_fmp.py`). The
  Estimates tab draws the same rows.
- **What the agents' tools stored.** `transcript-dates` for 31 companies, `transcript` for 65
  calls, `sec-filings` for 16 companies: fetched on request by the pass-throughs
  (`refresh/passthrough.py`), never by a refresh.
- **The calls of one company.** AAPL: 85, the oldest of 2005, each `{quarter, fiscalYear,
  date}`, 6 KB in all.
- **A transcript.** One row `{symbol, period, year, date, content}`. The content is plain text,
  one line a speaker, `Name: words`. Over the 65 stored calls, with the speaker's line of 7.4:
  51 turns at the median, 123 at the most; about 52 KB of text at the median, 95 KB at the
  most. A call's longest turn runs to 10,849 characters at the median, so a turn must be
  broken into paragraphs to be read. One call (NVS) has no speaker line: one block of 63,914
  characters.
- **Where the questions start.** The operator opens 47 of the 65 calls, so "the first turn by
  the operator" is no rule. The rule of 7.4 finds a start in 52 of the 65, none of them among
  the first 3% of the call's turns. A looser rule (any turn with a phrase such as
  "question-and-answer session") finds 62 and puts 12 of them in the opening remarks. So 13
  calls of the 65 have no marked start.
- **The calls against the earnings rows.** Of the 297 calls of the 31 companies that fall
  inside the stored rows' reach, 290 have a row with the same fiscal year and period dated
  within four days of the call. Six have a row with the same label and another date: TSM's
  three, 28 days off, are the same quarter; GOOG's one is a year off and RELX's two are three
  and five months off, another period under the same label. One has no row. So the join of
  7.4 is by the label and a date within 45 days: 293 of the 297.
- **A filing list.** AAPL, 11 November 2025 to 11 November 2026: 86 rows, 33 KB, each
  `{formType, filingDate, acceptedDate, link, finalLink}`, 54 of them Form 4. `link` is the
  filing's index page on sec.gov and `finalLink` its main document. The vendor answers a
  window's newest 1,000 rows at most (`FILINGS_LIMIT`).

## 6. Approaches

The founder ruled on this for the whole page on 2026-11-16 (the page's design, section 6 and
its decision log): "store as much as possible in our data store so that we don't need to fetch
this data everytime." A page that fetches through the pass-throughs when it opens was the way he
ruled out.

**A. The refresh stores the lists and the newest call; a press fetches what is older
(chosen).** A refresh fetches each company's list of calls and its filings of the last 365
days, as it fetches the page's other answers, and the transcript of the newest call where the
store has none. The tab's first draw reads the store alone. An older call's transcript is
fetched when a reader first selects it, and an older year of filings when a reader asks for
it; both are kept. Cost: 8.3.

**B. Fetch everything on opening, keep what was fetched.** No cost at a refresh; a wait of a
second or two on a company's first opening. It is the way the founder ruled out, and Claude
proposed it to him on 2026-11-18 before reading that ruling again. Not chosen; if he prefers it
for this tab, sections 8 and 12 shrink.

**C. Store every transcript at a refresh.** 85 calls for AAPL alone. Rejected: most are never
read.

## 7. The tab

### 7.1 The address and the row

The tabs' row reads Overview, Financials, Estimates, **Investor relations**, Research, the
order of the page's mockup (the page's design, 7.3). The addresses:

- `#company/<symbol>/investor-relations`: the Earnings calls view, on the newest call.
- `#company/<symbol>/investor-relations/<fiscal year>Q<quarter>`, as `2026Q4`: that call.
- `#company/<symbol>/investor-relations/filings`: the Filings view.

An address the tab cannot read (a call the company has none of, any other word) shows the
Earnings calls view on the newest call, and the address is put right. A change of view or of
call inside the tab reads the tab's own read again for nothing: only a call's transcript or an
older window is read (8.2).

### 7.2 The switch and the line

Inside the tab's panel, at its top: a switch of two, **Earnings calls** and **Filings**, drawn
as the Financials tab's switch of statements. At the right end of that row, one line: `Next
earnings report 4 Feb 2027`, the day the Estimates tab reads from the same stored rows
(`page_fmp.next_earnings`, its `day`). Where the rows hold no coming date the line is left out.

```
Overview  Financials  Estimates  Investor relations  Research               data 17 Nov 2026
+---------------------------------------------------------------------------------------------+
| [Earnings calls | Filings]                               Next earnings report 4 Feb 2027    |
|---------------------------------------------------------------------------------------------|
| FISCAL 2026       | Q4 fiscal 2026 earnings call                                            |
| | Q4   2 Nov 2026 | 2 Nov 2026                                                              |
|   Q3  30 Jul 2026 | [EPS reported | EPS estimate | Revenue reported | Revenue estimate]    |
|   Q2  30 Apr 2026 | [Find in this call      ]  [Go to the questions]                       |
|   Q1  29 Jan 2026 | Suhasini Chandramouli                                                   |
| FISCAL 2025       |   Good afternoon, and welcome to ...                                    |
|   Q4  30 Oct 2025 | John Ternus                                                             |
|   ...             |   ...                                                                   |
| [Show all 85 calls]                                                                         |
+---------------------------------------------------------------------------------------------+
```

### 7.3 The list of calls

At the left, 236px wide (*my call*, the mockup's): the calls on file, newest first, under one
head a fiscal year (`Fiscal 2026`). A row is the quarter as the vendor gives it (`Q4`) and the
call's date. The selected row is marked as the Research tab marks its section. The list shows
the newest five fiscal years; under them **Show all 85 calls** draws the rest, where there are
more. The list stays in view while the transcript scrolls.

A company with no call on file draws one sentence in the list's place, "No earnings call on
file.", and no reader.

### 7.4 The reader

At the right of the list, for the selected call:

1. **The title**, `Q4 fiscal 2026 earnings call`, and under it the call's date.
2. **The quarter's figures**, four cells in a row: `EPS reported`, `EPS estimate`, `Revenue
   reported`, `Revenue estimate`, each a figure of the stored `earnings` row, in US dollars and
   in the Estimates tab's words for money. A missing figure draws a dash. The row is the one
   with the call's fiscal year and period and a date within 45 days of the call's (section 5);
   a call with no such row has no figures row.
   **No gap to the estimate is drawn.** The mockup shows one (`+3.0% against the estimate`, in
   a colour). The founder's rulings for the page leave it out: "no need to compute new data",
   the Estimates tab's "No surprise column: Fairband would compute it", and no red and green
   (the page's design, sections 4 and 9, and its decision log). He may want it as an exception;
   the two figures stand side by side either way.
3. **The tools**: a box, `Find in this call`, and, where the questions' start is known, a
   button, **Go to the questions**.
   - The box marks every place the typed words stand in the transcript, whatever the case,
     from two characters on, and writes the count beside it (`3 matches`, `1 match`). It finds
     plain words, no pattern. Emptied, the marks go.
   - The button takes the reader to the first turn of the questions.
4. **The transcript**, at the reading width: one block a turn, the speaker's name over the
   turn's words, in paragraphs. The first turn of the questions carries the label `Questions
   and answers` over it and a heavier rule.

**A speaker's line** is a line of the vendor's text that reads `Name: words`, the name of 2 to
60 characters with no colon in it and of six words at most. It starts a turn. Any other line
that is not blank joins the turn before it, after a space; before any speaker's line it starts
a turn with no name.

**Paragraphs.** The server breaks a turn's words at the ends of sentences (a `.`, `!` or `?`
and the space after it), so that no paragraph passes 520 characters; a sentence longer than
that stands alone.

**Where the questions start** (*my call*, on the evidence of section 5): at the first turn
whose speaker is `Operator`, whatever the case, that has a turn by another speaker somewhere
before it and whose words hold `question`, whatever the case. A call where no turn fits has no
label and no button.

**A call with no words on file** (the vendor answers no row, or a row with no text) draws its
title, its date and its figures, and one sentence: "No transcript on file for this call."

**A transcript that cannot be read now** (it is not stored, and the vendor cannot be asked or
its call fails) draws the title, the date, the figures and "The transcript could not be read:
<reason>.", the reason as the pass-throughs word it (`no FMP key`).

### 7.5 The filings

A row of filters, then a table.

**The filters**, each with the count of its filings among the rows read, one pressed at a
time:

| Filter | The forms |
|---|---|
| Without insider forms (the first shown) | every form but `3`, `4`, `5`, `144` and their amendments |
| 10-K and 10-Q | forms that start `10-K` or `10-Q` |
| 8-K | forms that start `8-K` |
| Insider forms | `3`, `4`, `5`, `144` and their amendments (`4/A`) |
| All | every form |

The insider set is `filings_api.OWNERSHIP_FORMS`, the set the agents' filing list leaves out by
default. A foreign issuer's `20-F` and `6-K` stand under the first filter and under All (*my
call*: no filter of their own until a reader asks).

**The table**, newest first, four columns:

| Column | What it draws |
|---|---|
| Filed | the filing date, as `9 Nov 2026` |
| Form | the form type as the vendor gives it |
| What it is | the form in plain words, from a table in the page's code (below); nothing for a form the table lacks; an amendment (`8-K/A`) reads `Amendment: ` and the form's words |
| On the SEC's site | two links, `Document` (the vendor's `finalLink`) and `All files` (its `link`), each opening in a new tab; a link the row lacks, or one that does not start `https://`, is left out |

The plain words, as the mockup holds them, for the forms met most: `10-K`, `10-Q`, `8-K`,
`DEF 14A`, `DEFA14A`, `3`, `4`, `5`, `144`, `424B2`, `FWP`, `25-NSE`, `SD`, `11-K`, `S-8`,
`S-3ASR`, `20-F`, `6-K`, `SC 13G`, `SC 13G/A`, `PX14A6G`, `ARS`. The builder may add a form;
a line states what the form is and judges nothing.

**The windows.** The first rows are the newest stored filing list (8.2): a refresh's, the 365
days to its day. Under the table one line, `Filed from 11 Nov 2025 to 11 Nov 2026.`, and a
button, **Show older filings**. Each press reads one window more, of 365 days, and adds its
rows under the table's; the line's first date moves back.

- The next window ends the day before the oldest window's first day.
- Where the oldest window read is cut (the vendor's answer holds its limit of 1,000 rows, so
  its oldest filings are missing), the next window ends on the filing day of the oldest row
  shown, and a row already in the table is not drawn twice (the same `files` link, form and
  day). The line adds "The vendor's list is cut at 1,000 filings a window."
- A window that answers no filing takes the button away.

A company with no filing list on file draws "No filing on file." and no button; one whose
first window is empty draws the sentence and the button.

A list cut at 1,000 can hold weeks only, for an issuer of many prospectuses. The universe
leaves out the banks and the other financial industries where that is common (`docs/method.md`
section 1), so the tab does nothing more for it.

### 7.6 Loading, failure and the data date

The page's rules (its design, 7.5) hold: while a read is out the tab keeps what it shows,
faded, with no spinner; a block whose answer the store lacks draws its sentence of 7.3 or 7.5.
What a press can add:

- **An older call read for the first time** waits on the vendor. If it cannot be read, 7.4's
  sentence stands in the reader and the list stays.
- **An older window** waits on the vendor. If it cannot be read, the table stays and one
  sentence stands under it: "The older filings could not be read: <reason>."
- **The data date**, at the right end of the tabs' row (the page's design, 7.4): the oldest
  day among the stored answers the view draws. On the Earnings calls view these are the list
  of calls, the `earnings` rows and the transcript shown; on the Filings view, the filing
  lists read. So the page shows, on the Earnings calls view, the older of the first read's
  `dataDate` and the shown transcript's `observedDay`, and on the Filings view the oldest
  `observedDay` among the filing lists read (8.2).

After the build's first start and before its first refresh the store holds a list for few
companies: the tab draws its two sentences for the rest, as any tab draws a company not yet
fetched.

### 7.7 Words and figures

The tab's own words, each as written here: `Earnings calls`, `Filings`, `Next earnings report
<date>`, `Fiscal <year>`, `Show all <n> calls`, `Q<n> fiscal <year> earnings call`, `EPS
reported`, `EPS estimate`, `Revenue reported`, `Revenue estimate`, `Find in this call`, `<n>
matches`, `1 match`, `Go to the questions`, `Questions and answers`, `No earnings call on
file.`, `No transcript on file for this call.`, `The transcript could not be read:
<reason>.`, the five filters of 7.5, `Filed`, `Form`, `What it is`, `On the SEC's site`,
`Document`, `All files`, `Filed from <date> to <date>.`, `The vendor's list is cut at 1,000
filings a window.`, `Show older filings`, `No filing on file.`, `The older filings could not
be read: <reason>.` Dates read as the page's (`2 Nov 2026`). A speaker's name is the vendor's,
as given.

### 7.8 Width and print

Below 860px (*my call*, the mockup's) the list of calls stands over the reader, in a box of
its own that scrolls, and the four figures stand one under the other. The filings' table
scrolls sideways inside its own box; the page never does. Nothing is wider than a 400px
window.

Print shows the open view alone: the selected call's title, figures and whole transcript, or
the filings' table as filtered; the list of calls, the tools and the buttons are left out.

## 8. The data

### 8.1 The refresh's new calls

`fetch_company` gains two calls, after the page's fourteen. They join `PAGE_ENDPOINTS`, so
every rule of the page's calls holds for them (the page's design, 10.1; the Financials tab's
design, 8.1): reused while fresh, forced by a scoped refresh, stored whole, usable when the
payload is a list (the empty list among them), not required, a 429 stopping the fetch.

| Endpoint as stored | The pass-through that stores under the same key | Params beside the symbol |
|---|---|---|
| `transcript-dates` | `transcript-dates` | none |
| `sec-filings` | `filings` | `from` the refresh's day less 365 days, `to` the refresh's day, `limit` `FILINGS_LIMIT` |

- Each is stored under its pass-through's endpoint and params, so the refresh's copy and an
  agent's reuse each other, as the news and the segments do. The agents' `filings` tool asks
  the same window by default (a year to today), so on the day of a refresh it answers from the
  refresh's copy.
- So the two must agree on what a usable answer is. The `filings` pass-through checks for a
  list already. The `transcript-dates` pass-through stores any JSON today; it gains the same
  check (`usable=_is_list`), as the segments pass-through did: FMP's error object is stored
  with its error and reused by neither. This is the one change an agent's tool sees.

**The newest call's transcript**, a third call for some companies (*my call*): after a usable
list of calls is in hand, where it names a call and the store holds no `transcript` answer
with words for the newest one (8.2's test), the fetch asks for it and stores it under the
`transcript` pass-through's key (`year`, `quarter`). It is optional as the page's calls are. A
call the vendor has no words for yet is asked again at the next refresh, one call a company.

### 8.2 The reads

Three reads in `web/company_api.py`, beside the other tabs'.

**`GET /api/companies/{symbol}/page/investor-relations`**, from the store alone, a plain GET
with no vendor call, as the other tabs' reads are. It answers:

- `symbol`, `quote` (the head's, as the other tabs' reads answer it) and `dataDate`: the oldest
  day among the head's quote, the list of calls and the `earnings` rows, as the Estimates read
  counts its own answers. The filing list is not in it: it carries its own day (7.6).
- `nextEarnings`: the day, or null.
- `calls`: every call of the newest usable stored `transcript-dates` answer, newest first, each
  `{fiscalYear, quarter, date, epsReported, epsEstimate, revenueReported, revenueEstimate}`,
  the four figures null where no stored `earnings` row is the call's by 7.4's rule or the row
  lacks the figure. A row of the list without a whole fiscal year, a quarter of 1 to 4 and an
  ISO date is dropped. Empty where no list is stored.
- `filings`: `{from, to, rows, truncated, observedDay}` of the usable stored `sec-filings`
  answer whose `to` is the latest (the newest among equals), the rows newest first, each `{form,
  filed, document, files}`, a link null unless it starts `https://`; `truncated` true where the
  answer holds `FILINGS_LIMIT` rows; `observedDay` the day the stored answer was observed. Null
  where none is stored. An agent's list of an older window has an earlier `to`, so it never
  stands in for the refresh's.

**`GET /api/companies/{symbol}/page/investor-relations/call?year=<y>&quarter=<q>`** answers
`{symbol, fiscalYear, quarter, date, turns, questionsAt, observedDay}`: `turns` a list of
`{speaker, paragraphs}`, `speaker` null for a turn with no name; `questionsAt` the index of the
questions' first turn, or null; `observedDay` the day the copy was fetched.

- The read looks in the store first, for the newest usable `transcript` answer of that
  company, year and quarter that holds words (a list whose first row has a non-blank
  `content`). Such a copy is used whatever its age (*my call*): a call's words do not change
  once the vendor holds them.
- With none, it asks the `transcript` pass-through, which reuses a copy inside its window (an
  answer with no words among them) and calls the vendor past it. An answer with no words gives
  `turns` empty.
- Where the pass-through cannot ask or its call fails, the read fails as the pass-through
  route does: 503 with `no FMP key` or the busy sentence, 502 with the vendor's sentence,
  scrubbed. The page draws 7.4's sentence from it.

**`GET /api/companies/{symbol}/page/investor-relations/filings?to=<ISO date>`** answers
`{from, to, rows, truncated, observedDay}` for the 365 days that end on `to`, through the
`filings` pass-through. A stored usable answer of that exact window is used whatever its age
where `to` is before today (*my call*: a past year's list does not change); else the
pass-through's window holds. It fails as the call read does.

The last two may call a vendor. So each carries the header `X-Fairband-Request: 1`, else 403,
as the pass-through routes do (`app`, D11): their paths join `_VENDOR_READS` (`web/app.py`),
`add_company_page_routes` takes the `Passthrough`, and the page's `read()` sends the header
for these two.

Rules for all three, beside the page's (its design, 10.3): a symbol that is not one is a 400;
a company with no stored profile is a 404, "no page data for <symbol>"; a `year` or a
`quarter` that is no whole number, a quarter outside 1 to 4, or a `to` that is no ISO date, is
a 400 with its sentence. No answer carries a ref or a response id: no report cites them.

The payload readers are pure functions in `src/fairband/vendors/page_investor.py`, beside
`page_fmp.py` and `page_financials.py`: the turns of a transcript's text, its paragraphs, the
questions' start, the calls joined to the earnings rows, a filing list's rows.

### 8.3 The cost

- Calls: 31 FMP calls a company from 29, so 3,138 more a full refresh at 1,569 companies. The
  Financials tab's four calls, twice as many, took the full refresh from 18.5 minutes to an
  estimate of 21 to 22. The readout states the measured time.
- Bytes: 39 KB a company at AAPL's size (33 KB of filings, 6 KB of calls), so about 60 MB a
  full refresh at the most, on about 1.25 GB.
- Once: the newest call's transcript for every company that has one, about 1,570 calls and
  about 80 MB at the median size. After that, a company's new call each quarter.
- A reader's press: one call for an older transcript read for the first time, one for an
  older window.

## 9. The page's code

- `static/controls.js`: the tab in `COMPANY_TABS`, and its addresses in `keepCompany`,
  `companyPath` and `fromHash`, which keep an id for the Research tab only today: this tab's
  word after its name is a call (`2026Q4`) or `filings`.
- `static/company.js`: the tab's read as the other tabs', with no query from the address (the
  Research tab's id becomes `?report=`; this tab's word does not travel to the server), and the
  header on the two reads that may call a vendor.
- `static/company_investor.js` (*my call* for the name): the tab, drawn by a function on
  `P.companyPage.draw` as the other tabs are, its two later reads, and the find box's marking
  and the forms' plain words as pure functions the tests reach.
- `static/index.html`: the tab's rules, with the page's tokens and no colour of their own.
- No change to the design system's bundle.

## 10. The documents

In the same commits as the code they describe:

- `docs/method.md`, section 10: the full refresh's sentence that counts and names the FMP
  answers only the company page shows counts sixteen, and names the newest call's transcript.
  No method version moves, and the Methodology page does not change.
- The module docstrings that count the fetch's calls and list the page's reads and tabs
  (`fetch.py`, `run.py`, `passthrough.py`, `company_api.py`, `company.js`, `controls.js`).
- `docs/backlog.md`: B-217 moves to Done with its commits, and what the build's reviews leave
  gets rows of its own. **B-249**, press releases on the tab, is filed with this design (the
  founder, 2026-11-18: "keep it in the backlog, we do it later"; FMP's `news/press-releases`
  answered on 2026-11-16 and its fields are not read yet).
- The page's design: a line in its decision log, and 7.3's row with the tab in it.
- `README.md`: the Pages line names the tab ("overview, financials, estimates, investor
  relations and research"), and `docs/agents.md` and the playbook's tools reference say that
  `transcript_dates` and `filings` may answer from a refresh's copy.
- The mockup's sources stand beside this design, in `2026-11-18-investor-relations-tab-mockup/`,
  with no data.

## 11. Tests the builder must write

Test-first, as the repository's tests are written, on synthetic fixtures (the invented
companies of `tests/fixtures/fmp/`):

1. **The readers** (`page_investor`): a transcript's turns from speaker's lines; a line with
   no name joined to the turn before it; a text with no speaker's line as one turn with no
   name; a name of seven words or with a colon as no speaker's line; paragraphs that end at
   sentences and stay at 520 characters or under, a longer sentence alone; the questions' start
   by the rule of 7.4, with a call the operator opens, a call where an operator's turn after
   another speaker lacks `question`, a call with no operator, and `OPERATOR` and `Question` in
   another case; the calls joined to the earnings rows by label and date, with a row 28 days
   off (joined), a row a year off (not joined) and no row; a filing row with a link missing.
2. **The refresh**: the two calls in `PAGE_ENDPOINTS` with their params; the filing window by
   the refresh's day; the copies shared with the pass-throughs both ways; `transcript-dates`'
   error object stored as an error and not reused; the newest call's transcript fetched where
   none with words is stored, not fetched where one is, and not fetched without a usable list;
   a failure of any of the three costing no valuation; a 429 stopping the fetch.
3. **The reads**: the first read with no header and no vendor call; its `calls`, `filings` (the
   latest `to` winning over a newer copy of an older window), `nextEarnings` and `dataDate`;
   the empty answers; the two other reads' 403 without the header; the 400s and the 404 of
   8.2; a transcript with words used whatever its age, one without words asked again past the
   window; a past window's list used whatever its age; the 503s and the 502.
4. **The page**: the tab in the row and its three addresses, a bad address put right, a change
   of call or of view reading the tab's read for nothing; the list by fiscal year with five
   years and **Show all**; the figures row with every figure, with a dash, and no row; no gap
   and no colour of a rise or a fall; the find box's marks and counts at one, two and no
   character; the button and the label only where `questionsAt` is given; each filter's rows
   and counts; an amendment's words; **Show older filings** adding rows, asking for the right
   `to` after a whole window and after a cut one, dropping a row drawn already, and going
   away; the sentences of 7.3 to 7.6; the narrow width's rules by their text; print's.

## 12. Acceptance

On the live data, after the build is merged, the server restarted and one full refresh run (no
migration):

1. The refresh's readout: its calls and its time against 8.3, the bytes added, the count of
   companies with a list of calls, with a filing list and with a newest transcript, and no
   valuation moved by the new calls (the snapshots' values against the refresh before).
2. The tab opens for AAPL, ASML (a foreign issuer: `20-F` and `6-K`), NVS (the transcript with
   no speaker's line), TSM (earnings rows dated 28 days off their calls), FRVO (listed in 2026:
   few calls and filings) and one company with no call on file: no error in the browser's
   console and no vendor call on the first draw.
3. An older call read once is never fetched again; **Show older filings** adds a year.
4. Every transcript in the store draws: its turns, its paragraphs, the questions' label where
   the rule finds a start. The count of calls with a start is read out beside section 5's 52
   of 65.
5. Nothing is wider than a 400px window; both themes are read by eye, at 400, 1,000, 1,200,
   1,440 and 2,000px.
6. The founder looks at the tab.

The readout goes in the decision log.

## 13. Where the design and the mockup differ

- The mockup holds one call's text, cut at 14 of its 73 turns; the tab holds every call, whole.
- The mockup draws each reported figure's gap to its estimate, in a colour. The design leaves
  the gap out (7.4).
- The mockup's **Show older filings** does nothing; 7.5 says what it does.
- The mockup marks the questions at the first turn by the operator. The rule is 7.4's, and a
  call with no start has no button.
- The mockup breaks a turn into paragraphs in the page; the server does it (8.2).
- The mockup has no sentence for a call or a window that cannot be read, no line for a list
  cut at 1,000, and no print rule; 7.4 to 7.8 add them.

## 14. Left to the builder

The names of functions and style rules; the exact height of the list's box below 860px; how
the find box keeps its place while the marks are redrawn; the fixtures' invented calls and
filings; how `fetch_company` runs a call that depends on another's answer.

## 15. Order of work

1. The readers, as pure functions with their tests.
2. The refresh's calls.
3. The three reads.
4. The tab's frame: the row, the addresses, the switch, the line.
5. The Earnings calls view.
6. The Filings view.
7. The documents, a look in a browser at the five widths of 12.5 before the review of the
   whole branch (the Research tab's lesson), then the live steps on the founder's word.

## Decision log

- **2026-11-16, the founder's request** (B-217): the tab holds "all related filings and
  investor call logs".
- **2026-11-18, what the tab holds.** The founder: "now let's work on the investment relation
  tab, what should this tab contain in your opinion?" Claude proposed the earnings calls, the
  filings and press releases, with the news, the estimates, the agent records and ownership left
  to their own places, and asked whether a filing's text should be read inside Fairband. The
  founder: "I think links are enough".
- **2026-11-18, the mockup** (version 1, on AAPL's stored data, a private page:
  https://claude.ai/artifact/9zuQao39K6a4s6KWeiBRu4). Claude named two of its own calls for the
  founder's eye: press releases left out, and the insider forms hidden until asked for. The
  founder: "It looks good, yes it's ok for the insider forms, keep it in the backlog, we do it
  later". Claude reads "it" as the press releases, and said so.
- **2026-11-18, the questions' start.** The mockup's button rested on the first turn by the
  operator. A count over the 65 transcripts in the store showed the operator opens 47 of them,
  so the rule became 7.4's, which finds a start in 52 and marks none where it finds none.
  Claude told the founder before writing this design.
- **2026-11-18, the approach.** Claude first told the founder the tab would fetch on opening
  and keep what it fetched (section 6, B). The check of this design by a fresh reader found the
  founder's ruling of 2026-11-16 against that way for the whole page, so the design follows the
  ruling (A) and says so to him with the cost.
- **2026-11-18, the gap to the estimate.** The mockup the founder approved draws it. The same
  check found his rulings against a computed figure and against red and green on this page, so
  the design leaves the gap out and says so to him.
- **2026-11-18, the check's other points**, each settled by Claude in the text: the earnings
  figures are US dollars (7.4); which stored filing list the tab draws, and what stands in for
  a window cut at 1,000 (7.5, 8.2); a transcript with no words is asked again (8.2); what a
  transcript that cannot be read draws (7.4); the speaker's line and the questions' rule,
  exactly (7.4); the calls joined to the earnings rows by label and date, counted over 297
  calls (section 5); where the addresses, the header and the readers live in the code (8.2, 9).
- **2026-11-18, the approval.** Claude gave the founder the design with the two corrections
  named (the refresh stores the tab's data; no gap to the estimate). The founder: "Approved".
  While writing the plan Claude added one rule: a filing's link is drawn only where it starts
  `https://` (7.5, 8.2), so a vendor's row can put no other kind of address behind a press.
- **2026-11-18, the build's ruling:** the first read's data date covers the calls view's stored
  answers, and each filing list carries its own day, so the page can give each view its caption
  (7.6).
