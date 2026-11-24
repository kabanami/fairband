# The tools

Fairband's MCP server, `fairband mcp`, serves these tools. Each one calls the Fairband web server
on this machine; none holds a key. The lists follow the server's order. An argument marked `?` may
be left out.

## How a tool answers

- A tool answers the web server's JSON, an object. Its keys are camelCase (`responseId`). A ref
  names a field by the engine's snake_case name (`snapshot:412/inputs/market_cap`).
- The reads of stored figures, `financials`, `quarters`, `financial_tables`, `estimates`,
  `price_history`, `peers` and `multiples_history`, give each figure with its `ref`. Cite the
  `ref` as given. `filing_report` and `filing_search` give each row of a filing report with its
  `rowRef`: cite a cell as the `rowRef` plus `/<col>`. For every other figure, build the ref from
  its record's id (`reference/citations.md`). A percent is a fraction: `0.112` is 11.2%.
- A refusal is `{"refused": <sentence>, "status": <code>}`, with the rest of the answer beside it:
  a refused override's `override`, a rejected report's `findings`. The status says what kind of
  refusal it is: 400 a value the call cannot take, or a report's structural refusal; 404 a record
  that does not exist (and, to `company`, `estimates`, `price_history` and `peers`, a company with
  no snapshot: "no snapshot for <symbol>"); 409 a state the write cannot move from (a snapshot
  valued under other settings, a store that moved, a superseded guidance record, a kill criterion
  moved to the state it is in); 422 a rejected report; 502 a vendor call that failed; 503 a
  pass-through that is busy or has no key.
- A write before `identify` answers `{"refused": "identify first: the model identifier you run
  as"}` and calls nothing. The reads and the pass-throughs need no identity.
- When the web server is down, every tool answers `{"refused": "the Fairband server is not
  running: start `uv run fairband serve`"}`. When it took the call but did not answer in time, the
  tool answers `{"refused": "the Fairband server did not answer in 60 seconds: try again"}`: call
  again.
- A symbol is letters, digits, dots and dashes, in any case (`brk.b` reads `BRK.B`). Any other
  symbol answers `{"refused": "a symbol is letters, digits, dots and dashes"}` and calls nothing.
- A record inside an argument (an evidence item, a part, a cite) may name its keys in snake_case
  (`terminal_growth`) or in camelCase (`terminalGrowth`).

## The reads

- `screen(sort?, direction?)`: the screen's rows, one a company, sorted by a column key;
  `direction` is `asc` or `desc`. A row's `fairValue`, band, levels, price ÷ value and designation
  follow the reviewed value where `reviewed` is filled; `mechanical` is the engine's value. Where
  `reviewed` is a review's value, the row's `flags` and `flagCount` are the review's flags too;
  where it is a secondary valuation's, they stay the snapshot's, since a secondary valuation has
  none. Where `reviewed` is filled, `freshness` and `validUntil` are the held record's, and
  `expiredEarly` is true while it expired early; `freshness` then reads `expired`. A row's
  `warnings` are the plain words of the snapshot's quality warnings, never the
  review's, and `marked` is whether the page marks the mechanical value: `warning_mark_min`
  warnings or more and no reviewed value. Every money column is in US dollars, on a company in
  another currency too: its EPV, cross-check value and required revenue are the route's figures
  in the currency ÷ the rate.
- `company(symbol)`: the latest snapshot in full: `snapshot.id`, `snapshot.refreshId` (the refresh
  that wrote the snapshot), the `result` (the value, the levels, the price, the inputs, the
  intermediates, the phase evidence, the flags, `valid_until`) and the company's row in the
  universe. `moatClass`: the company's row of the moat table, `{class, source, fileVersion,
  judgedOn, previous, reason, actor, at, fileClass}`: the class in force; whose it is, `file`
  (Fairband's own file, of version `fileVersion`), `owner` (the user) or `agent` (with its
  `actor`); the day it was judged; on a class the user or an agent set, the class before it and
  the reason; and `fileClass`, the class Fairband's file holds for the company, `null` where it
  holds none. `moatClass` is `null` for a company with no class, which the engine refuses "no
  moat class"; `moat` is the class in force. `review`: the review the company holds, on the
  latest snapshot, `null` without one. Its `held` is the state of that review: `state`
  (`current`, `aging`, `expired`, `expired-early`), `earlyAt`, `reasons`, the sentences of the
  reasons it expired early for, `reading` and `readingRefusal`, what the review gives on today's
  data, `readingLine`, that reading's sentence where it is no reason, and `validUntil`, the end
  of the review's own window. A `secondary` that holds its row carries `held` the same way,
  with no reading. Where the review has a value, its `flags` are the review's own, each with
  its `code`,
  `word` and `sentence`, as the screen's row shows them, so you read what your inputs settled; on a
  refused review `flags` is `null`. The `result`'s flags stay the snapshot's. `priceNeeds`: where
  the price is well above the value, one or two sentences on what the price needs of the business
  beside what the route holds, read under your review when it has a value; `null` otherwise.
  `priceNeeds` is also `null` for a held review whose result holds `held_as_made`: a refresh
  carried it under another method or policy version, or after a split, and its figures that
  follow the price are those of the day it was made; make the review again to read it.
  `warnings`: the plain words of the snapshot's quality warnings, never the review's; `marked`:
  whether the page marks the mechanical value, `warning_mark_min` warnings or more and no
  reviewed value. An input scaled for a split is an estimate under the method `split-scaled` with a
  note naming the split, and the row's `split-pending` note names the rest. What the figures are in:
  `currency`, the reporting currency; `isAdr`, the ADR flag as the valuation reads it, the company
  profile's, else the universe row's; `adrRatio`, the whole number Fairband found between FMP's
  stored share count and the quote's, `null` where the counts agree; `fxRate` and `fxDate`, the
  exchange rate the value was translated at, units of the currency per US dollar, and its close's
  date, `null` on a company in US dollars and on one refused for its currency, which has no rate
  ("no exchange rate for <code>", "no inflation projection for <code>" or "<code>: expected
  inflation <π>% above the 10% bound"). An input in the currency names its code as its unit (`TWD`,
  `TWD a share`); one read on the ADS basis is an estimate under `basis-scaled`, and the input
  `adr_ratio`, the ratio found, one under `counts-ratio`.
- `financials(symbol)`: the fiscal years, the trailing figures and the balance years from the
  stored statements, each figure with its `fact:` ref.
- `quarters(symbol)`: the newest eight stored quarters, oldest first, each by its fiscal label
  (`period`, `2027-Q1`) with its `periodEnd`, and the trailing figures' lines, each with its
  `fact:` ref (`fact:<symbol>/revenue/2027-Q1`). A quarter's lines are its own terms of the
  trailing sum: where the trailing figures are the sum of four quarters, the newest four add to
  them; on the fiscal-year fallback (the row flagged `trailing-on-fiscal-year`) they do not, and
  for a half-yearly reporter the newest two add. `otherCurrency` counts the stored
  quarters left out for another currency than the reporting one. A half-yearly reporter's
  periods are its half-years, served by the labels FMP stores for them, `Q2` and `Q4`
  (`2026-Q2`, `2026-Q4`). The diluted EPS is the statement's as stored: on a row flagged
  `split-pending` or `basis-scaled` it may sit on another share basis than the quote's. It calls
  no vendor. Without an annual income statement on file it answers "no financial statements for
  <symbol>" (404), as `financials` does.
- `financial_tables(symbol)`: the six tables of the report's section 4 under `tables`, `growth`,
  `cash_flow`, `solvency`, `returns`, `capital_allocation` and `quality`, and the quarters table
  of section 5 beside them under `quarters`. Each table has its `columns`, each
  `{period, kind, label}`, and its `rows`, each `{name, unit, cells}` with one cell
  `{period, value, unit, ref, note}` under each column. The columns: the last five fiscal years,
  kind `fiscal` (`2025`, "2025"); on `growth`, `cash_flow` and `capital_allocation`, then the
  trailing twelve months, kind `trailing`, where the trailing figures end after the newest fiscal
  year (`ttm`, "12 months to 30 Sep 2026"); and on `growth`, then the analysts' years after the
  newest fiscal year, three at most, kind `estimate` (`2026E`, "2026 estimate"). The quarters
  table's columns are the newest eight stored periods, kind `quarter` (`2026-Q3`, "Q3 2026"), and
  its rows the revenue, the operating margin and the EPS. A cell that is one stored line gives its
  `fact:` ref, and an estimate of revenue or EPS its `estimate:` ref: cite the ref as given.
- `estimates(symbol)`: the stored analyst consensus by quarter and by fiscal year, each figure with
  its `estimate:` ref.
- `price_history(symbol, years?)`: the stored daily closes, oldest first, each with its `close:`
  ref; `years` keeps the latest years only.
- `multiples_history(symbol, daily?)`: the trailing P/E (`pe`) and the forward P/E (`peForward`,
  the price over the analysts' EPS for the next twelve months as they state it, with no charge
  for stock pay, Fairband's own log, kept since `since`) over the ten years on file, the last
  point of each month; `daily` answers every point, about 2,500 a series, which overflows the
  host's result.
  Fairband builds the trailing series from FMP's daily closes and quarterly diluted EPS: a day's
  close ÷ the EPS of the four quarters (two half-years for a company that reports twice a year)
  ended by that day, for a company in another currency each period's EPS brought into USD at
  the pair's last close on or before the period's end, and the close in USD ÷ their sum; a loss
  day has no point. It fetches FMP's answers when you call and reuses them for a day. Each point
  is `{day, value, ref}`; each statistic, `avg10y`, `median10y`, `high10y` and `low10y`, is
  `{value, unit, ref}` over every daily point, its ref `multiple:<symbol>/pe/avg_10y` and its
  siblings. `peNote` says why the trailing series could not be fetched or read, when it could not
  ("the series could not be read"); the read then serves the newest one stored. An EPS near zero
  gives a very large P/E: the median is the safe statistic.
- `peers(symbol)`: the company's mature peers with their figures, each with its `peer:` ref, and
  where the list of peers came from.
- `watchlists()`: the watchlists with their companies.
- `inbox_list(state?)`: the work items, newest first, or those in one state: `pending`, `claimed`,
  `done`, `declined` or `dropped`. An open item's `launch` is the window the page last opened for
  it, if any, and `launchReady` says whether the page can open one; neither changes what you do.
- `reports(symbol)`: the company's published reports, newest first, without their text.
- `report(symbol, id?)`: one published report whole, with its judgments and its appendixes: the
  one with that id, or the company's latest.
- `notes(symbol)`: the company's notes, newest first.
- `findings(symbol)`: the company's findings with their sources, each with `currency`, the
  currency of its money figure (see "A money figure" below); cite one as `finding:<id>`.
- `guidance(symbol)`: the company's guidance records, newest first, each with its midpoint, its
  step, `currency` as a finding's, and `supersededBy`, the newer record that superseded it, if
  any; cite one's figures as `guidance:<id>/midpoint` and its siblings. A record that names a
  currency other than that of the year before's statement has no step.
- `overrides(symbol)`: the company's overrides, newest first, each with its state.
- `reviews(symbol)`: `held`, the state of the review the company holds (as `company` gives it,
  with `reviewId`, `madeAt` and `readAgainAt`, the time a refresh first read it again; `null`
  for a company that holds none), and `reviews`, the company's reviews, newest first, each with
  its `kind`, `made`, `held` or `reading`, its bridge and without its result. A `made` review is
  an act's: an override written or dropped, a moat class written, or `review_again`. A `held`
  one is a copy a refresh carried onto a newer snapshot. A `reading` is what the review gives on
  a newer snapshot, which replaces nothing. The review's intermediates, cited as
  `review:<id>/intermediates/<path>`, are in the
  `result` of the review that `override_add` and `override_drop` answer.
- `secondary(symbol)`: the company's secondary valuations, newest first, each with `fxRate`, the
  rate it ran at, 1 for a company in US dollars: its totals are in the reporting currency, its
  value a share and levels in US dollars.
- `kill_criteria(symbol)`: the company's kill criteria, each with its state: `open`, `triggered`
  or `retired`, and its `threshold`, `unit` and `currency`, `null` on one with no threshold. A
  threshold you chose is cited as `kill:<id>` in Risks and kill criteria alone.
- `news_items(symbol)`: the company's news items.
- `ledger(symbol?, limit?)`: the ledger's newest rows, for one company or for all: every write, who
  made it and what it rests on.
- `review_log(symbol?)`: the review log, newest first: each review's mechanical and reviewed value
  beside the price, and `stance`, the stance of the company's newest report when the review was
  written: a review your overrides write carries the stance of the report before yours, and one
  written before a company's first report carries none (`null`).
- `policy()`: the policy values in force, the user's settings over the file's, each with its
  source.
- `methodology(section?)`: one section of the Methodology page in plain words, with the live
  values; without a section, the list of sections.
- `refresh_status()`: the running refresh's progress in `refresh`. With none running, `refresh` is
  `null` and it answers `last`, the newest refresh's record, and `shown`, the record the page's
  status line describes: the same one, but passing over a finished revalue that names its
  companies, which a write of the moat class records.

## The vendor pass-throughs

Nine vendor reads the engine does not use: six pass-throughs, all from FMP, then three filing
reads from FMP. The server fetches each with its own key and stores the response, so a report can
cite it. It reuses a response stored within the reuse window, a filing report at any age, so a
repeated call costs no vendor call. A refresh stores five of these
calls' responses for each company under the same keys, so within the reuse window such a call may
answer from the refresh's copy, `reused` true: `segments`; `news` at a `limit` of 60;
`transcript_dates`; `filings` with its default window, on the refresh's day; and `transcript` of
the newest call, where the store held no copy of it with words.

### The six pass-throughs, all from FMP

Each answers the stored response whole, `{responseId, observedAt, reused, payload}`. `segments`
and `dcf` answer two of them, `{responses: {product: ..., geographic: ...}}` and `{responses:
{dcf: ..., levered: ...}}`. Cite a field of a payload as `response:<responseId>/<json pointer>`,
such as `response:731/0/revenue`.

- `transcript(symbol, year, quarter)`: the earnings call transcript of one fiscal quarter, the
  quarter 1 to 4. Take the year and the quarter from `transcript_dates`.
- `news(symbol, limit?)`: recent stock news: 20 items, or `limit` up to 100.
- `segments(symbol)`: the revenue by product and by region, two responses under `product` and
  `geographic`, each with `newestYear`, the newest fiscal year among its rows, `null` with none.
  FMP's split by region can end years before its split by product: where a split's `newestYear` is
  null or is before the company's newest fiscal year, read the 10-K's segment note (`SKILL.md`,
  step 4).
- `insider_trades(symbol, limit?)`: the insiders' newest trades: 25, or `limit` up to 100.
  `tradeCount` says how many are on file; a trade keeps its place in the stored page, so its
  `response:` ref is the same at any limit.
- `transcript_dates(symbol)`: the fiscal year, the quarter and the date of every earnings call on
  file, newest first. It finds the last call, so you never guess a year. Where FMP answers its
  error object in place of the list, the answer is that object, stored as an error and never
  reused, so the next call asks FMP again.
- `dcf(symbol)`: FMP's discounted cash flow value and its levered one, two responses under `dcf`
  and `levered`. Read it only where neither the route nor the review values the company, as a
  cross-check on the secondary valuation; never beside a route's value. Neither the engine nor the
  secondary valuation reads it.

### The three filing reads

They serve FMP's filing list and its filing reports, a 10-Q or a 10-K as JSON, a part at a time,
so no answer holds a whole report. Each answer carries `symbol`, and `responseId`, `observedAt`
and `reused` of the stored response it was read from, beside its own keys below. A filing report,
once stored, is reused whatever its age, since a filing does not change once filed; the filing
list and the list of reports are fetched again after the reuse window. A sheet's name, a label and
a text cell are served with every run of white space as one space and the ends trimmed; an offset
or a length counts in that text.

The budget: a list an answer holds (the filings, the sheets, a sheet's rows, the hits) stops
before the item that would take it past 30,000 characters as the tool prints it, its JSON indented,
one item at least, and the answer says that more remains (`nextRow`, `more`). So an answer stays
under about 40,000 characters as you receive it. The counts below are upper bounds beside it.

- `filings(symbol, forms?, from_date?, to_date?, from_row?)`: the company's filings from FMP's
  filing list, newest first. The window runs from `from_date` to `to_date`, ISO dates: the past
  365 days when they are left out, `to_date` today and `from_date` 365 days before `to_date`.
  `forms` is a comma list of form types, matched whole and without regard to case
  (`10-K,10-Q,8-K`), or `all`; left out, every form but the ownership forms `3`, `4`, `5` and
  `144` and their amendments (`4/A`), which `insider_trades` serves. The answer: `from` and `to`,
  the window; `filings`, from `from_row` of the kept filings (0 when left out), at most 100 within
  the budget, each `{formType, filingDate, acceptedDate, link, finalLink}`, `link` the filing's
  index page on sec.gov, which lists its exhibits, and `finalLink` its main document; `nextRow`,
  the next `from_row`, or `null`; `count`, the filings the filter kept; `leftOut`, the rows it
  dropped; and `truncated`, `true` when FMP answered 1,000 filings, the most Fairband asks it for,
  so older filings of the window are missing: ask again with an earlier `to_date` for them. On
  the day of a refresh the default window is the one the refresh stored, so the answer may come
  from its copy.
- `filing_report(symbol, year?, period?, sheet?, from_row?, row?, col?, offset?)`: FMP's filing
  report, a part at a time. Its newest stored copy is reused without a limit, never one FMP
  answered with an error, so a report read once is not fetched again. Four views, by the arguments
  given; an argument the view does not read is not read:
  1. Neither `year` nor `period`: `reports`, the reports FMP holds as it orders them, each
     `{year, period}`, a 10-K as `FY` and a 10-Q as its quarter, `Q1` to `Q3`. Take `year` and
     `period` from this list. A US filer files no 10-Q for its fourth quarter: its 10-K, `FY`,
     reports the whole year. Where FMP lists a `Q4` for such a filer, it holds the 10-K again
     (MSFT, fiscal 2026): read `FY`.
  2. `year` and `period`: `year`, `period` and `sheets` from `from_row` (0 when left out), at most
     100 sheets an answer within the budget, with `nextRow`, the next `from_row`, or `null` after
     the last sheet. Each sheet is `{name, title, rows, chars}`: the sheet's name, its title (its
     first row's label, which names the scale, `$ in Millions`), its row count and the length of
     its JSON text. The sheets are the statements, each note as text and each note's detail
     tables. FMP cuts a sheet's name at 31 characters and makes it unique
     (`SEGMENT INFORMATION AND GEOGR_1`): pass `sheet` as the list names it.
  3. With `sheet`: `sheet`, `title`, `columns` and `rows` from `from_row` (0 when left out), at most
     100 rows an answer, and at most 30,000 characters of the answer's list as it is printed, with
     `nextRow`, the next `from_row`, or `null` after the last row. `columns` names each column of
     the page's rows, by index from 0: its span and its date from the sheet's top rows (`3 Months
     Ended, Sep. 30, 2026`), its date alone where one span covers two dates, or its title row's cell
     on a sheet with no row of dates; `null` where nothing names it. A later page names them too. A
     column's words are cut at 200 characters, and they count in the page's budget beside its rows.
     A row is `{row, label, rowRef, cells}`: its index in the sheet from 0, its label, its ref and
     its cells in order. A number cell is the number. A cell longer than 2,000 characters is cut,
     with its length, as `{text, chars}`: read it whole with `row` and `col`. A row holds its first
     cells alone, 100 at most and 10,000 characters of them as printed; a row cut so has
     `cellCount`, the count of all its cells, and `columns` names the cells served. A long note's
     sheet has one such row: the note's whole text as its first cell, then the note's tables
     flattened into text cells, most of them empty, thousands on a long note. Read the note's text
     with `row` and `col` 0, and its numbers from the note's detail sheets, whose cells are numbers.
     A cell past the cut is read with `row` and `col`, or found by `filing_search`; each names the
     cell's column as `column`, and its ref is the row's `rowRef` plus `/<col>` as any cell's. A row
     of another shape has `label` and `rowRef` `null` and one cell, its JSON text: it holds no cell
     to cite.
  4. With `sheet` and `row`: one cell's text, `col` and `offset` 0 when left out. The answer:
     `sheet`, `row`, `col`, `column` (the words of the cell's column, or `null`), `label`, `chars`
     (the text's whole length), `offset`, `text` (a page of 20,000 characters from `offset`) and
     `nextOffset`, the next `offset`, or `null` after the text's end. A number cell answers its JSON
     text.

  Cite a number cell as its row's `rowRef` plus `/<col>` (`filing:812/LEASES/2/0`), after reading
  its column's words in `columns`. Never build a `filing:` ref by hand: a sheet name with a `/` or
  a `~` is written `~1` or `~0` inside a ref.
- `filing_search(symbol, year, period, text)`: a search of one filing report for `text`, three
  characters or more, without regard to case, in every label and every cell. A number cell is found
  by its JSON text, or by `text` with its commas removed, so `33,165` finds the number cell `33165`;
  a text cell is found as it reads. A hit is a row, in the report's order: `{sheet, row, col,
  column, label, excerpt, offset, rowRef, numbers}`. `col` is the first cell that matches, or `null`
  when only the label does, and `column` the words of that cell's column, or `null`; `excerpt` holds
  300 characters each side of the first match; `offset` is the match's place in that cell's text
  (the label's when `col` is `null`), so view 4 of `filing_report` opens the cell there; `numbers`
  lists the row's number cells as `{col, value, column}`, `column` the column's words as a sheet's
  `columns` gives them, or `null`: the first 60 of them, with `numberCount`, the count of all, where
  the row holds more. A hit in a sheet that has the name of an earlier sheet has `rowRef` `null`: no
  ref reaches that sheet, so its cells are findings. The answer holds at most 20 hits, within the
  budget, with `more` `true` when a further row matched, and `year`, `period` and `text`, the text
  searched. A search has no next page: when `more` is `true`, search a longer text. Cite a number
  cell as the hit's `rowRef` plus `/<col>`.

### The refusals

The vendor reads' refusals:

- "the pass-throughs are busy: four calls are in flight, try again" (503): wait a little and call
  again.
- "no FMP key" (503): the server has no FMP key, so it serves no pass-through and no filing read;
  use the host's own tools and record findings.
- A vendor call that failed (502), with the vendor's sentence.

The filing reads add their own. The first four refuse before any vendor call, so they cost none
and store nothing:

- "a filing report needs year and period" (400): `sheet`, `from_row`, `row`, `col` or `offset`
  without `year` and `period`, or one of the two without the other.
- "period is FY or Q1 to Q4" (400), in either case: `q1` reads as `Q1`.
- "text needs three characters or more" (400): a search text shorter than three characters once
  its white space is served.
- "from and to are ISO dates, from on or before to" (400): a `from_date` or a `to_date` that is no
  ISO date, or a `from_date` after the `to_date`.
- "FMP holds no filing report for <symbol> <year> <period>: ask without year and period for the
  reports on file" (404): call `filing_report(symbol)` and take a year and a period it lists.
- "FMP answered no filing list for <symbol>" or "FMP answered no filing reports for <symbol>"
  (502): FMP's answer was not a list.
- "no sheet named <name>: ask without sheet for the sheet list" (404): take the sheet's `name`
  from the sheet list as it stands.
- "<name> is 0 to <last>" (400), or "<name> is out of range: there is none" where the sheet has no
  row or the row no cell: a `row`, `col`, `offset` or `from_row` past its end, named as the web
  server names it (`fromRow`). On the filing list, with no filing kept, 0 alone is in range.

## The writes

- `identify(agent)`: name the model identifier you run as; every later write is recorded under it.
  The identifier is printable ASCII: any other answers `{"refused": "the model identifier must be
  printable ASCII"}`.
- `inbox_post(symbol, mode, note?)`: post a work item for a company; `mode` is `valuation review`
  or `full report`; `note` is the request in the user's own words, on one line, with no commentary
  and without adding the mode.
- `inbox_claim(item_id?)`: claim the named work item, or the oldest pending one; naming a claimed
  item takes it over.
- `inbox_complete(item_id, report_id)`: complete a work item with a published report of its
  company.
- `inbox_decline(item_id, reason)`: decline a work item, with the reason.
- `note_add(symbol, text, override_id?)`: add a note to the company, tied to an override when one
  is named.
- `finding_add(symbol, as_of, text, source, value?, unit?, period?, currency?)`: record a fact
  from outside Fairband with its source, so a report can cite it as `finding:<id>`; a money value
  with `currency` when it is not in the reporting currency (see "A money figure" below).
- `guidance_add(symbol, metric, period, low, high, basis, as_of, text, source, currency?)`: record
  a figure the company guided on a call for a future period, low and high equal for a point, with
  `currency` as a finding's; it answers the record with the midpoint and, for a fiscal-year
  revenue, EPS or net income figure on the `gaap` basis, the step the server computed. An override
  cites it in its evidence as `guidance:<id>`; a report cites its figures.
- `moat_set(symbol, moat_class, reason, evidence)`: record your verdict on the company's moat
  class, `Wide`, `Narrow` or `None`, with your reason and one evidence item or more, each
  `{kind, ref, note}` of an override's kinds, also when you agree with the class in force
  (`SKILL.md`, step 10). The company's row of the moat table becomes yours, and the company is
  valued again at once on the data the store holds, with no vendor call: a new snapshot, and a
  new review on it where overrides apply. It answers `{moatClass, snapshot}`: the row as
  `company` gives it, and the new snapshot's `{id, value, refusal}`. Read `company` again before
  you cite the snapshot. Refused, nothing stored: "a moat verdict needs a reason" (400); "a moat
  verdict needs evidence" (400); "no snapshot for <symbol>" (404); and "a refresh is running: set
  the class when it ends" (409): wait until `refresh_status()` shows no refresh running, then call
  again. A class that is not one of the three never reaches the web server: the tool's argument
  names them, so the MCP tool answers a tool error and calls nothing.
- `override_add(symbol, tag, new, reason, evidence, lifetime, period?)`: override one input of
  the twenty-four in `SKILL.md`'s table that take an override, every row but `moat.class`, which
  `moat_set` sets: an override of it is refused, "moat.class is the moat table's: record the
  verdict with moat_set". Among them are the diluted share count (`shares.diluted`), the
  committed shares (`shares.committed`), the value outside the business (`value.outside`), the
  one-time item in the NTM consensus (`earnings.ntm_nri`), the two revenue steps of the Mature
  Growth charge (`revenue.step_2`, `revenue.step_3`), the trailing stock pay (`earnings.sbc`),
  the stock-pay basis (`earnings.sbc_basis`) and the minority interest (`balance.minority`).
  Applied, it answers `{override, review, bridge, dropped}`, `dropped` the overrides
  the system dropped with it because the row's route no longer reads them, each
  `{id, tag, reason}`, empty when none (a `phase` override, new or replacing another, can move the
  route); refused, the sentence and the `override`. A lasting `earnings.sbc` of 0 on a row whose
  trailing stock pay is above zero is refused with the sentence alone, and nothing is stored.
- `override_drop(override_id, reason)`: drop an applied override; the review is recomputed over
  the rest, or cleared when none is left. It answers `{override, review, bridge, dropped}`,
  `dropped` as `override_add`'s: dropping a `phase` override drops the overrides only its route
  read.
- `review_again(symbol)`: make the company's review again on its latest snapshot, over the
  overrides still applied and with no change of an input. The review it writes is the one the
  company holds from there, so what the review gives today takes the held value's place. It
  answers `{review, bridge, dropped}`, as `override_add` does without the override. With no
  override applied it clears the held review and answers `review` none: the row is mechanical
  again. Refused, "no review for <symbol>", for a company that holds none.
- `secondary_valuation(symbol, reason, evidence, drivers?, parts?, debt?, cash?)`: the fallback
  where neither the route nor your review values the company: value the company by the standard
  discounted cash flow from your `drivers`, or from your own free-cash-flow path in `parts`,
  exactly one of the two; it answers the stored secondary valuation, with its projection or its
  parts and its grid. Where the route values the company it is refused: "the route values
  <symbol>: the secondary valuation is the fallback where it refuses"; where the current review
  values it: "the review values <symbol>: the secondary valuation is the fallback where neither
  the route nor the review values the company". A report on a refused snapshot your review does
  not value needs one on it, except where the snapshot's refusal is one you cannot fix, which the
  secondary valuation refuses in the refusal's own words: "no diluted share count"; "reporting
  currency unknown", "no exchange rate for <code>", "no inflation projection for <code>" or
  "<code>: expected inflation <π>% above the 10% bound"; "share basis unclear: the newest
  period's count <c> against the quote's <Q>". On a company in another currency pass the path,
  the debt and the cash in the reporting currency; the value a share comes back in US dollars. Its
  levels and its grid's cells are in US dollars too; its firm value, equity and projection stay in
  the currency, and the record carries the rate as `fxRate`.
- `sensitivity(symbol, row_tag, row_values, col_tag, col_values)`: the route's value a share
  across two inputs' values, at most five by five, stored to cite as `sensitivity:<id>/<i>/<j>`,
  and its axes' values as `sensitivity:<id>/rows/<i>` and `/cols/<j>`; nothing is overridden.
  `current` marks the pair in force as `[i, j]`; a cell whose valuation refuses is `null`.
- `derive(symbol, derivations)`: compute figures from refs; it answers
  `{derivations: [{id, value, unit}]}`, each cited as `derived:<id>`. A derivation is
  `{operation, a, b, years?}` (below). One operand may be a fixed number, `number:<n>` where a ref
  goes, `<n>` in digits alone, with no sign, separator, point or exponent: the whole numbers 0 to
  12, then 52, 100, 365, 1000 and each further power of ten up to 1,000,000,000,000. Any other is
  refused (400), "a fixed number is one of 0 to 12, 52, 100, 365 or a power of ten up to
  1,000,000,000,000, not <what was written>", and so are two numbers in one derivation, "a
  derivation needs a stored figure". A derivation with a number anywhere in it, its own operands
  or those of a `derived:` operand, must move with a stored figure: one that keeps its value
  whatever its figures are, a figure times `number:0`, a number over a figure over itself, a
  figure plus a number less the same figure, is refused, "a derivation with a fixed number must
  depend on a stored figure: this one has the same value whatever its figures are". Where it rests
  on an earlier derivation whose figures changed since, or are no longer on file, the words go on,
  "a derivation with a fixed number must depend on a stored figure: this one has the same value
  whatever its figures are, or rests on an earlier derivation whose figures changed: derive it
  again": derive that one again from its refs. A refusal stores none of the call's derivations. A
  number has no unit, so the result's follows the stored figure:

  | Operation | Unit |
  |---|---|
  | `sum`, `difference`, `product` with a number | the stored figure's unit |
  | `ratio` of a figure over a number | the figure's unit |
  | `ratio` of a number over a figure | none |
  | `growth`, `cagr` | percent |

  A fixed number is a number of arithmetic, never a figure you chose: the recipes are in
  `SKILL.md`, step 10. `growth` and `cagr` have no value from a base at or below zero. A `kill:`
  ref is refused, "unresolved reference: kill:<id>": a threshold you chose enters no arithmetic.
  On a company in another currency the rate is `snapshot:<id>/inputs/fx_rate`: a `ratio` of a
  figure in the currency and the rate is that figure in US dollars, a derivation with no unit, so
  its cite takes `$` or none at the decimals you write. A finding or a guidance record in another
  currency than the reporting one stays out of money arithmetic until you convert it, and so does
  every derivation of it, its quarter or its average among them: with a money figure not in its
  own currency it has no value, and no derivation with it has a money unit. The `product` of a
  US-dollar record, or of a derivation of one, and the rate is the figure in the reporting
  currency, with no unit, which then combines with anything: convert first, or keep to figures in
  its own currency.
- `report_submit(symbol, mode, stance, sections, judgments, kill_criteria?, news_items?,
  work_item_id?)`:
  submit a report; published whole, it answers `{report: {id, symbol, createdAt, workItemId}}`,
  and `report(symbol, id)` reads it whole; rejected whole, the `findings`.
- `kill_criterion_add(symbol, text, threshold?, unit?, currency?)`: add an open kill criterion to
  the company: `text`, the event that would prove the view wrong, and, where you chose the line it
  crosses, `threshold` and `unit` together, the unit one of a finding's, with `currency` for a
  money threshold as a finding's. It answers the criterion with its `threshold`, `unit` and
  `currency`. Record a criterion with a threshold before you write the report, cite the threshold
  as `kill:<id>` in Risks and kill criteria alone, and leave the criterion out of the report's
  `kill_criteria`. Refused (400), nothing stored: "a kill criterion needs text"; "a kill
  criterion's threshold and unit come together"; a currency's two refusals, as a finding's. A
  unit that is not a finding's never reaches the web server: the tool's argument names the units,
  so the MCP tool answers a tool error and calls nothing.
- `kill_criterion_set(id, state, reason)`: move a kill criterion to `open`, `triggered` or
  `retired`, with the reason. A move to the state it is in answers "kill criterion <id> is
  already <state>" (409).
- `news_item_add(symbol, date, headline, source, text, kill_criterion_id?)`: record a dated news
  item, tied to a kill criterion when one is named.
- `refresh_start(kind, symbols?)`: start a refresh: `full`, `price`, `scoped` with `symbols`, or
  `revalue`, which values the `symbols` given alone, or every company without them. It answers
  `{"refreshId": <id>}`, the started refresh's id. A refresh already running refuses it (409), with
  that refresh's id as `running`. A server with no FMP key refuses every kind but `revalue`, "no fmp
  key: ..." (400). A stored setting outside its range refuses every kind, "settings: ...; reset it
  on the Settings page" (400), and every read of the policy answers the same sentence (409) until
  the user resets it. A server with no refresh worker answers "no refresh worker" (503). Step 3 of
  `SKILL.md` says what to do on each.
- `refresh_cancel()`: ask the running refresh to stop after the companies in flight.

## The records inside the arguments

- An evidence item (`override_add`, `secondary_valuation`, `moat_set`): `{kind, ref, note}`. The
  kind is `filing`, `transcript`, `url`, `vendor`, `base-rate`, `finding` or `guidance`. The ref
  says where: `10-K 2025, Item 7`, a URL, `response:<id>` for a stored vendor response, a finding's
  id, and for a `guidance` item `guidance:<id>`, the record's id with no path. A `guidance` item of
  any other form is refused, "a guidance item cites its record as guidance:<id>" (400); a record
  that is not the company's, "no guidance record <id> for <symbol>" (404); a record a later call
  replaced, "guidance record <id> is superseded by record <id>" (409). An NTM anchor override
  needs one: "an NTM anchor override needs a guidance record among its evidence". Its records hold a
  `gaap` record of one of its metrics for a fiscal year, else 400, nothing stored: "an NTM anchor
  override needs a gaap guidance record of eps or net_income for a fiscal year" (or of revenue, on
  `revenue.ntm`). The server checks the record, not the override's figure against it. On
  `secondary_valuation`, the item that backs a debt or a cash you pass adds `figure`, `debt` or
  `cash`, and one item at least names no `figure`: "the path needs its own evidence item".
- A guidance record (`guidance_add`): the `metric` is `revenue`, `eps`, `net_income`,
  `operating_margin`, `free_cash_flow`, `capex`, `revenue_growth` or `eps_growth` (`net_income` a
  total, the net income that belongs to the shareholders); the `period` a fiscal year (`2027`)
  or a quarter (`2027Q1`, no dash); `low` and `high` in the metric's unit, money as "A money
  figure" below says, a percent as a fraction; the `basis` `gaap`, `adjusted` or
  `constant-currency`; `as_of` the call's date; `text` the sentence verbatim; `source` a string,
  the transcript's `response:<id>` or a filing. A newer record of the same metric, period and
  basis supersedes the older, in the order of the calls' dates, whatever the currency of either.
  A value the record cannot take is refused (400), nothing stored, with the first of these
  sentences that applies: "metric is one of revenue, eps, net_income, operating_margin,
  free_cash_flow, capex, revenue_growth or eps_growth"; "period is a fiscal year or a quarter
  (2026, 2026Q3)"; "low is above high"; "basis is one of gaap, adjusted or constant-currency"; "a
  guidance record needs its text"; "a guidance record needs its source"; then a currency's two
  refusals. A low or a high that is not a number never reaches the web server: the tool's own
  arguments are typed as numbers, so the MCP tool answers a tool error first and calls nothing. A
  number that is not finite (NaN or infinity) fails when the tool encodes the body, since httpx
  refuses to write one in JSON: the tool answers an error and calls nothing.
- A finding's source (`finding_add`): `{kind, ref, note}`, the kind one of `filing`,
  `transcript`, `url`, `vendor` or `base-rate`. `as_of` is the date the fact describes, as
  `2026-09-30`. The `unit` is `currency`, `percent`, `multiple`, `count`, `per-share`, `score` or
  `years`. The `value` is in that unit: money as "A money figure" below says, a percent as a
  fraction. The `period` is a fiscal year (`2025`), a quarter (`2026-Q2`) or `ttm`.
- A money figure (`finding_add`'s `value` of unit `currency` or `per-share`, `guidance_add`'s
  `low` and `high` of a money metric, `kill_criterion_add`'s `threshold` of either unit): in full,
  in the currency the company states it in, with `currency`, three capital letters, when that is
  not the reporting currency, such as a US-dollar outlook of a company that reports in TWD. Every
  read answers the record's `currency`: the stored code, else the reporting currency; `null` for a
  figure that is not money. In the report it takes `$` where it is in US dollars, and its code in
  the plain text before a bare cite otherwise. To set an input from it, or to compare it with a
  statement, convert it first: the `derive` `product` of a US-dollar figure and
  `snapshot:<id>/inputs/fx_rate` is the figure in the reporting currency. A figure in a third
  currency, neither the reporting currency nor the US dollar, has no rate and enters no arithmetic
  with the company's figures. Refused (400), nothing stored: "a currency is three capital letters,
  not <what was written>"; "a currency goes with a money figure", a code on any other figure.
- The drivers (`secondary_valuation`): `{years, revenue_growth, operating_margin, tax_rate,
  sales_to_capital, terminal_growth}`, rates as fractions: `years` N from 3 to 15; the
  `revenue_growth` and `operating_margin` lists with an entry for each year; the terminal growth
  from −1.00 to g_T, the currency's restated on a company in another currency. The ranges are the
  policy's `secondary_driver_ranges` (`SKILL.md`, "The secondary valuation").
- A part (`secondary_valuation`): `{name, fcff, terminal_growth, note}`, `fcff` a list of figures
  in the reporting currency for years one to N.
- A sensitivity axis (`sensitivity`): a tag of the overrides table the route reads, and one to five
  values in the unit an override of it takes: "an axis holds one to five values"; the two tags
  differ, "the two tags differ".
- A derivation (`derive`): `{operation, a, b, years?}`. The operation is `ratio` (a ÷ b),
  `difference` (a − b), `sum` (a + b), `product` (a × b), `growth` (a ÷ b − 1) or `cagr`, the
  compound annual growth over `years`. `a` and `b` are refs, or one of them a fixed number,
  `number:<n>` (see `derive`).
- A section (`report_submit`): `{heading, parts}`, a part a plain string or a cite
  `{cite, ref, period?}`.
- A judgment (`report_submit`): `{judgment, decision, override_id?}`, the judgment one of
  `phase`, `moat`, `belief`, `roic` and `target_margin`; it takes no other key.
- A kill criterion (`report_submit`): `{text}`, a measurable event that would prove the view wrong;
  text alone, so a threshold there is dropped without a word: record a criterion with a threshold
  through `kill_criterion_add` before you write the report.
- A news item (`report_submit`): `{date, headline, source, text, kill_criterion_id?}`, the source a
  URL or a stored vendor response.
