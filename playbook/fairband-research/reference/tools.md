# The tools

Fairband's MCP server, `fairband mcp`, serves these tools. Each one calls the Fairband web server
on this machine; none holds a key. The lists follow the server's order. An argument marked `?` may
be left out.

## How a tool answers

- A tool answers the web server's JSON, an object. Its keys are camelCase (`responseId`). A ref
  names a field by the engine's snake_case name (`snapshot:412/inputs/market_cap`).
- The reads of stored figures, `financials`, `financial_tables`, `estimates`, `price_history`,
  `peers` and `multiples_history`, give each figure with its `ref`. Cite the `ref` as given. For
  every other figure, build the ref from its record's id (`reference/citations.md`). A percent is a
  fraction: `0.112` is 11.2%.
- A refusal is `{"refused": <sentence>, "status": <code>}`, with the rest of the answer beside it:
  a refused override's `override`, a rejected report's `findings`. The status says what kind of
  refusal it is: 400 a value the call cannot take, or a report's structural refusal; 404 a record
  that does not exist; 409 a state the write cannot move from (a snapshot valued under other
  settings, a store that moved, a superseded guidance record); 422 a rejected report; 502 a vendor
  call that failed; 503 a pass-through that is busy or has no key.
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
  follow the reviewed value where `reviewed` is filled; `mechanical` is the engine's value.
- `company(symbol)`: the latest snapshot in full: `snapshot.id`, `snapshot.refreshId` (the refresh
  that wrote the snapshot), the `result` (the value, the levels, the price, the inputs, the
  intermediates, the phase evidence, the flags, `valid_until`) and the company's row in the
  universe. An input scaled for a split is an estimate under the method `split-scaled` with a
  note naming the split, and the row's `split-pending` note names the rest.
- `financials(symbol)`: the fiscal years, the trailing figures and the balance years from the
  stored statements, each figure with its `fact:` ref.
- `financial_tables(symbol)`: the six five-year tables of the report's section 4, `growth`,
  `cash_flow`, `solvency`, `returns`, `capital_allocation` and `quality`, each cell
  `{period, value, unit, ref, note}`.
- `estimates(symbol)`: the stored analyst consensus by quarter and by fiscal year, each figure with
  its `estimate:` ref.
- `price_history(symbol, years?)`: the stored daily closes, oldest first, each with its `close:`
  ref; `years` keeps the latest years only.
- `multiples_history(symbol, daily?)`: the trailing P/E (`pe`, GuruFocus's daily series) and the
  forward P/E (`peForward`, Fairband's own log, kept since `since`) over the ten years on file,
  the last point of each month; `daily` answers every point, about 2,500 a series, which
  overflows the host's result. Each point is `{day, value, ref}`; each statistic, `avg10y`,
  `median10y`, `high10y` and `low10y`, is `{value, unit, ref}` over every daily point, its ref
  `multiple:<symbol>/pe/avg_10y` and its siblings. `peNote` says why the trailing series could
  not be fetched or read, when it could not ("the series could not be read"); the read then
  serves the newest one stored. Read this, not `pe_history`, for the points and the statistics
  with their refs.
- `peers(symbol)`: the company's mature peers with their figures, each with its `peer:` ref, and
  where the list of peers came from.
- `watchlists()`: the watchlists with their companies.
- `inbox_list(state?)`: the work items, newest first, or those in one state: `pending`, `claimed`,
  `done`, `declined` or `dropped`.
- `reports(symbol)`: the company's published reports, newest first, without their text.
- `report(symbol, id?)`: one published report whole, with its judgments and its appendixes: the
  one with that id, or the company's latest.
- `notes(symbol)`: the company's notes, newest first.
- `findings(symbol)`: the company's findings with their sources; cite one as `finding:<id>`.
- `guidance(symbol)`: the company's guidance records, newest first, each with its midpoint, its
  step and `supersededBy`, the newer record that superseded it, if any; cite one's figures as
  `guidance:<id>/midpoint` and its siblings.
- `overrides(symbol)`: the company's overrides, newest first, each with its state.
- `reviews(symbol)`: the company's reviews, newest first, each with its bridge and without its
  result. The review's intermediates, cited as `review:<id>/intermediates/<path>`, are in the
  `result` of the review that `override_add` and `override_drop` answer.
- `secondary(symbol)`: the company's secondary valuations, newest first.
- `kill_criteria(symbol)`: the company's kill criteria, each with its state: `open`, `triggered`
  or `retired`.
- `news_items(symbol)`: the company's news items.
- `ledger(symbol?, limit?)`: the ledger's newest rows, for one company or for all: every write, who
  made it and what it rests on.
- `review_log(symbol?)`: the review log, newest first: each review's mechanical and reviewed value
  beside the price.
- `policy()`: the policy values in force, the user's settings over the file's, each with its
  source.
- `methodology(section?)`: one section of the Methodology page in plain words, with the live
  values; without a section, the list of sections.
- `refresh_status()`: the running refresh's progress, or the last refresh's record when none runs.

## The vendor pass-throughs

Seven vendor reads the engine does not use, six from FMP and one from GuruFocus. The server fetches
each with its own key and stores it, so a report can cite it.

- `transcript(symbol, year, quarter)`: the earnings call transcript of one fiscal quarter, the
  quarter 1 to 4. Take the year and the quarter from `transcript_dates`.
- `news(symbol, limit?)`: recent stock news: 20 items, or `limit` up to 100.
- `segments(symbol)`: the revenue by product and by region, two responses under `product` and
  `geographic`.
- `insider_trades(symbol)`: the insiders' trades.
- `transcript_dates(symbol)`: the fiscal year, the quarter and the date of every earnings call on
  file, newest first. It finds the last call, so you never guess a year.
- `dcf(symbol)`: FMP's discounted cash flow value and its levered one, two responses under `dcf`
  and `levered`. Read it only where neither the route nor the review values the company, as a
  cross-check on the secondary valuation; never beside a route's value. Neither the engine nor the
  secondary valuation reads it.
- `pe_history(symbol)`: GuruFocus's daily trailing P/E series, reused for seven days. It answers
  the whole daily series, thousands of rows. Read `multiples_history` instead for the points and
  the statistics with their refs; it reads the same stored series.

Each answers `{responseId, observedAt, reused, payload}`. `segments` and `dcf` answer two of them,
`{responses: {product: ..., geographic: ...}}` and `{responses: {dcf: ..., levered: ...}}`. Cite
a field of a payload as `response:<responseId>/<json pointer>`, such as `response:731/0/revenue`.
The server reuses a response it fetched within the reuse window, so a repeated call costs no
vendor call. The refusals:

- "the pass-throughs are busy: four calls are in flight, try again" (503): wait a little and call
  again.
- "no FMP key" (503): the server has no FMP key, so it serves no pass-through; use the host's own
  tools and record findings.
- "no GuruFocus key: the pe-history pass-through is off" (503): the server has no GuruFocus key;
  `multiples_history` still serves the trailing series stored before, if any, and the forward one.
- A vendor call that failed (502), with the vendor's sentence.

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
- `finding_add(symbol, as_of, text, source, value?, unit?, period?)`: record a fact from outside
  Fairband with its source, so a report can cite it as `finding:<id>`.
- `guidance_add(symbol, metric, period, low, high, basis, as_of, text, source)`: record a figure
  the company guided on a call for a future period, low and high equal for a point; it answers the
  record with the midpoint and, for a fiscal-year revenue or EPS figure, the step the server
  computed. An override cites it in its evidence as `guidance:<id>`; a report cites its figures.
- `override_add(symbol, tag, new, reason, evidence, lifetime, period?)`: override one input of
  the eighteen in `SKILL.md`'s table, the diluted share count (`shares.diluted`) and the value
  outside the business (`value.outside`) among them; applied, it answers `{override, review,
  bridge}`; refused, the sentence and the `override`.
- `override_drop(override_id, reason)`: drop an applied override; the review is recomputed over
  the rest, or cleared when none is left.
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
  "<code>: expected inflation <π>% above the 10% bound"; "share basis unclear: ...".
- `sensitivity(symbol, row_tag, row_values, col_tag, col_values)`: the route's value a share
  across two inputs' values, at most five by five, stored to cite as `sensitivity:<id>/<i>/<j>`,
  and its axes' values as `sensitivity:<id>/rows/<i>` and `/cols/<j>`; nothing is overridden.
  `current` marks the pair in force as `[i, j]`; a cell whose valuation refuses is `null`.
- `derive(symbol, derivations)`: compute figures from refs; it answers
  `{derivations: [{id, value, unit}]}`, each cited as `derived:<id>`.
- `report_submit(symbol, mode, stance, sections, judgments, kill_criteria?, news_items?, work_item_id?)`:
  submit a report; published whole, it answers `{report: {id, symbol, createdAt, workItemId}}`,
  and `report(symbol, id)` reads it whole; rejected whole, the `findings`.
- `kill_criterion_add(symbol, text)`: add a kill criterion to the company.
- `kill_criterion_set(id, state, reason)`: move a kill criterion to `open`, `triggered` or
  `retired`, with the reason.
- `news_item_add(symbol, date, headline, source, text, kill_criterion_id?)`: record a dated news
  item, tied to a kill criterion when one is named.
- `refresh_start(kind, symbols?)`: start a refresh: `full`, `price`, `scoped` with `symbols`, or
  `revalue`. It answers `{"refreshId": <id>}`, the started refresh's id. A refresh already running
  refuses it (409), with that refresh's id as `running`.
- `refresh_cancel()`: ask the running refresh to stop after the companies in flight.

## The records inside the arguments

- An evidence item (`override_add`, `secondary_valuation`): `{kind, ref, note}`. The kind is
  `filing`, `transcript`, `url`, `vendor`, `base-rate`, `finding` or `guidance`. The ref says
  where: `10-K 2025, Item 7`, a URL, `response:<id>` for a stored vendor response, a finding's id,
  and for a `guidance` item `guidance:<id>`, the record's id with no path. A `guidance` item of
  any other form is refused, "a guidance item cites its record as guidance:<id>" (400); a record
  that is not the company's, "no guidance record <id> for <symbol>" (404); a record a later call
  replaced, "guidance record <id> is superseded by record <id>" (409). An NTM anchor override
  needs one: "an NTM anchor override needs a guidance record among its evidence". Its records hold a
  `gaap` record of its metric for a fiscal year, else 400, nothing stored: "an NTM anchor override
  needs a gaap guidance record of eps for a fiscal year" (or of revenue, on `revenue.ntm`). On
  `secondary_valuation`, the item that backs a debt or a cash you pass adds `figure`, `debt` or
  `cash`, and one item at least names no `figure`: "the path needs its own evidence item".
- A guidance record (`guidance_add`): the `metric` is `revenue`, `eps`, `operating_margin`,
  `free_cash_flow`, `capex`, `revenue_growth` or `eps_growth`; the `period` a fiscal year (`2027`)
  or a quarter (`2027Q1`, no dash); `low` and `high` in the metric's unit, dollars in full, a
  percent as a fraction; the `basis` `gaap`, `adjusted` or `constant-currency`; `as_of` the call's
  date; `text` the sentence verbatim; `source` a string, the transcript's `response:<id>` or a
  filing. A newer record of the same metric, period and basis supersedes the older, in the order of
  the calls' dates. A value the record cannot take is refused (400), nothing stored, with the first
  of these sentences that applies: "metric is one of revenue, eps, operating_margin,
  free_cash_flow, capex, revenue_growth or eps_growth"; "period is a fiscal year or a quarter
  (2026, 2026Q3)"; "low is above high"; "basis is one of gaap, adjusted or constant-currency"; "a
  guidance record needs its text"; "a guidance record needs its source". A low or a high that is
  not a number never reaches the web server: the tool's own arguments are typed as numbers, so the
  MCP tool answers a tool error first and calls nothing. A number that is not finite (NaN or
  infinity) fails when the tool encodes the body, since httpx refuses to write one in JSON: the
  tool answers an error and calls nothing.
- A finding's source (`finding_add`): `{kind, ref, note}`, the kind one of `filing`,
  `transcript`, `url`, `vendor` or `base-rate`. `as_of` is the date the fact describes, as
  `2026-09-30`. The `unit` is `currency`, `percent`, `multiple`, `count`, `per-share`, `score` or
  `years`. The `value` is in that unit: dollars in full, a percent as a fraction. The `period` is a
  fiscal year (`2025`), a quarter (`2026-Q2`) or `ttm`.
- The drivers (`secondary_valuation`): `{years, revenue_growth, operating_margin, tax_rate,
  sales_to_capital, terminal_growth}`, rates as fractions: `years` N from 3 to 15; the
  `revenue_growth` and `operating_margin` lists with an entry for each year; the terminal growth
  from −1.00 to g_T. The ranges are the policy's `secondary_driver_ranges` (`SKILL.md`, "The
  secondary valuation").
- A part (`secondary_valuation`): `{name, fcff, terminal_growth, note}`, `fcff` a list of dollars
  for years one to N.
- A sensitivity axis (`sensitivity`): a tag of the overrides table the route reads, and one to five
  values in the unit an override of it takes: "an axis holds one to five values"; the two tags
  differ, "the two tags differ".
- A derivation (`derive`): `{operation, a, b, years?}`. The operation is `ratio` (a ÷ b),
  `difference` (a − b), `sum` (a + b), `growth` (a ÷ b − 1) or `cagr`, the compound annual growth
  over `years`. `a` and `b` are refs.
- A section (`report_submit`): `{heading, parts}`, a part a plain string or a cite
  `{cite, ref, period?}`.
- A judgment (`report_submit`): `{judgment, decision, override_id?}`, the judgment one of
  `phase`, `moat`, `belief`, `roic` and `target_margin`; it takes no other key.
- A kill criterion (`report_submit`): `{text}`, a measurable event that would prove the view wrong.
- A news item (`report_submit`): `{date, headline, source, text, kill_criterion_id?}`, the source a
  URL or a stored vendor response.
