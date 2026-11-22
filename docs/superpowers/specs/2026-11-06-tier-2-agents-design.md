# Tier 2: the agents over MCP, overrides and the reviewed value, the secondary valuation, reports and the work inbox: design

Status: written 2026-11-06 from the founder's decisions of that evening, in a brainstorm that
started from the backlog. The founder moved Tier 2 ahead of B-28 and B-87, described the first
session (the inbox, the playbook, the MCP interface, the request from the screen or a watchlist),
chose the row and the drawer's shape, ruled that the agent's value is the engine's own figure under
the agent's inputs with the stance free, and added the secondary valuation as a second view and a
fallback. Items marked *my call* were settled by Claude while writing and can be overturned. The
decisions are in the log at the end. Builder check: see the status line at the end of the log.
Amended 2026-11-07, after plan 1 merged and the founder read the playbook: the report's twelve
sections with the last earnings call, the debate and the thesis, the guidance record, cites and overrides as footnotes, the standard DCF on
every report, the cycle, the key judgments as the last section, the multiples history, the charts
on the report page, and the Inbox view's count (11, 12, 13, 14, 15.3, 18.4, 18.5, 19, 24, and the
log's three rows of that date). Plan 1b (merged 2026-11-07) carries the report's side; plan 2
(merged 2026-11-08) the page; plan 3 (merged 2026-11-08, `docs/superpowers/plans/2026-11-08-first-session-fixes.md`)
the first live session's rulings; plan 4 (merged 2026-11-08, `docs/superpowers/plans/2026-11-08-second-run-page-fixes.md`)
the page fixes of the second live session; plan 5
(merged 2026-11-09, `docs/superpowers/plans/2026-11-09-playbook-price-and-words.md`) the latest
price and the report's words, from the GOOG session of 2026-11-09. The readout of section 22 was taken on 2026-11-09 over five
runs (the log's row of that date) and B-9 closed with it. The build rulings of the plans are marked in place and
listed in the log's last rows.

This document adds to `docs/method.md` (sections 14, 15 and 16, and the versions table) and to the
Methodology page. It changes no mechanical figure: the mechanical method stays
`fairband-mechanical/0.9`. The earlier specs stand for everything it does not mention. When the
pieces are built, their sections go into `docs/method.md` in the same commits.

Every `B-n` is a backlog item (`docs/backlog.md`); every `FC-n` a feature candidate of the product
brief; `design.md` is `docs/legacy/design.md`; the brand book and the component guidelines are the
design system's (`docs/design-system/`, read with `tar -xzOf`).

## 1. What this is

Fairband's second surface: an agent in the user's own host (Claude Code first; Codex and Claude
Desktop by the same transport) connects to Fairband over MCP, takes a research request from the
work inbox, reads everything the page shows, researches, changes the engine's inputs with evidence,
reads the engine's reviewed value, values the company by a standard DCF only when neither the
route nor the review can, writes
the report, and completes the request. The user asks for research from the screen or a watchlist
and reads the report and the value on the page. Twelve backlog items, B-48 to B-59, plus one new
one, the secondary valuation (B-97), as one design and two plans:

1. **The agent's side** (plan 1): the MCP server, identity and the ledger, the inbox, notes and
   findings, overrides with the reviewed value and the value bridge, the secondary valuation,
   reports with the number check, kill criteria and news items, the log, the playbook. After it
   an agent can take an item and publish a report, and every write is on file.
2. **The page** (plan 2): the reviewed value and the stance on the row, the coverage mark, the
   drawer led by the valuation and the report with everything else behind Details, the report
   page with its export, the Inbox view, the research request on the drawer and on a watchlist.

The founder's three rulings shape everything below:

- **The number is rigid; the stance is free.** An agent never writes a value. It changes one
  input at a time, with a reason and evidence, and the engine recomputes. The stance is the
  agent's word, with its reasons in the report.
- **The secondary valuation is the fallback.** A tool beside the engine projects a cash-flow path
  from the agent's drivers and discounts it under the policy's rules, so a company neither the
  route nor the review values still gets a figure that is a tool output (plan 3; it was a second
  view on a valued company until 2026-11-08).
- **The user reads the report and sees the value.** The drawer's main view is the valuation and
  the report. The phase evidence, the inputs, the bridge, the overrides and every audit item sit
  behind one Details control.

## 2. Goals

- From Claude Code with the playbook installed, an agent lists the inbox, claims an item, reads
  the company, writes findings, overrides, a secondary valuation where needed, and a report, and
  completes the item, with no input typed in chat.
- Every reviewed value on the screen rebuilds from the mechanical snapshot and the applied
  overrides, a week later too; the bridge's deltas sum to the difference exactly.
- Every number in a published report resolves to a stored fact, an engine figure, a tool output
  or a recorded finding; a report with one that does not is rejected whole with the failure
  named and located, and the published report is unchanged.
- Every write names its principal (owner, agent with the model identifier, system) and the
  snapshot it rests on, in one ledger the page and the agent can read.
- The page shows, per row, the reviewed value, the agent's stance and a mark that an agent
  covered the company; the drawer leads with the meter and the report; a report page shows the
  whole report and exports it.
- The mechanical-versus-reviewed log starts filling from the first review.
- At the defaults every mechanical value, level, designation and flag is bit for bit what method
  0.9 and policy v7 give.

## 3. Non-goals

- The portfolio layer (B-60 to B-62) and proposals (the design system's `ProposalCard`: trades,
  policy changes, thesis revisions). Nothing in this round waits for the owner's confirmation.
- The owner's own override form on the page, and any owner write on an override: the owner
  neither adds nor drops one; the owner adds a note. Founder, 2026-11-06: the whole user
  override function waits for a commitment to all of it; the agent is the one who changes
  inputs.
- Charts on the screen or in the drawer: the brand book puts charts on a company report only.
  The report page's charts are in scope since 2026-11-07 (18.4); the band's history over the
  snapshots on file is what `BandHistory` draws, and the rest of B-68 stays with B-87.
- A network transport, a token or an account. The server stays on 127.0.0.1 with the
  request-header rule; the MCP server is a local stdio process (B-48).
- The agent's own research tools: filings from EDGAR, the web, the host's other MCP servers. The
  playbook names them; Fairband serves what it stores and four vendor pass-throughs (15.3).
- Ownership evidence and recent picks joined to the rows (B-71, B-72), a free data path (B-65),
  point-in-time reads and a backtest (B-64).
- Automatic kill-criterion checks and automatic re-research. An expired watchlist company posts
  an item; nothing runs by itself (B-55, B-58).

## 4. Anti-goals

- A reviewed value that nobody can rebuild: a free number, a number from the agent's own
  arithmetic outside a tool, an override with no evidence.
- A report with a number that traces to nothing, or a rejection that replaces the published
  report.
- A drawer that opens on the phase evidence and the inputs. The main view is the valuation and
  the report; one control opens the rest.
- A second writer on the database file. The web server owns the database and the refresh
  worker; the MCP server holds no connection.
- A key in a tool result, a log line or a stored payload.
- An agent named by a category ("AI", "assistant") rather than by the model identifier it
  connected under.

## 5. Constraints

- Python 3.13, uv, FastAPI, SQLite; the design system vendored under `web/static/design-system/`
  with `// fairband:` patches re-applied by hand on each export (B-40). New behaviour in the
  bundle is a patch, named and listed in the plan.
- The MCP server uses the official Python SDK, the `mcp` package (`FastMCP`, stdio). *My call.*
  It is the one new dependency.
- The repository runs no JavaScript tests; page-script tests pin file content in `tests/web/`.
  Behaviour that can be tested in Python is put in Python.
- No key is ever stored, logged or shown. The pass-through routes return payloads the scrub has
  cleaned, as the store already requires.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
  passes at every commit.
- `docs/method.md` and the Methodology page change in the same commit as the engine (CLAUDE.md).
- The brand book governs the look and the words: override, review, snapshot, finding, judgment,
  note, news item, report, work item; the model identifier in `mono`, lower case, as it arrived;
  no emoji, no exclamation marks; `◆` on a write, `ƒ` on a computed number, never on one chip.

## 6. The shape: one API, two clients

The web server (`fairband serve`) owns the database and the refresh worker, as today. The MCP
server is `fairband mcp`, a stdio process the agent host starts. It holds no database connection
and no key. Every tool is one or more calls to the web API at `http://127.0.0.1:<port>` (`--port`,
8470 by default) with the `X-Fairband-Request: 1` header and the identity headers of section 7.
When the server does not answer, every tool returns one sentence: "the Fairband server is not
running: start `uv run fairband serve`".

*My call*, for three reasons. One writer process: SQLite's locks never contend between two
long-lived processes. The refresh stays on the one worker, so an agent's refresh and the page's
never collide (B-44's rule stays a CLI matter). And the page and the agent read one API, so
whatever the page shows the agent can read, by construction, which is B-48's first promise.

Every write that the page or the agent makes is a web API route (section 16), so the page's
own writes (a note, a research request, dropping an override) use the same code and the same
ledger.

## 7. Identity and the ledger (B-49)

Every write carries a principal: `owner` (the page, the CLI), `agent`, or `system` (the engine's
own writes: a period-tied override dropped, an expiry item posted; a review recomputed at a
refresh is a system write the review log records, with no ledger row).

An agent is named by the model identifier it runs as, exactly as the brand book asks:
`claude-opus-5-5`, `gpt-5`. MCP's handshake carries the client's name and version
(`clientInfo`), not the model, so the playbook's first step is `identify(agent)`, the model
identifier as the host reports it. The MCP server keeps it for the session and sends it on every
write as `X-Fairband-Actor`, with `X-Fairband-Principal: agent` and `X-Fairband-Client:
<name>/<version>` from the handshake. A write tool called before `identify` is refused:
"identify first: the model identifier you run as". A request without the principal header is the
owner's. *My call.*

The ledger is one table (17): every write, with `at`, `principal`, `actor`, `client`, `kind`
(`note`, `finding`, `override`, `override-drop`, `secondary`, `derivation`, `report`,
`judgment`, `kill-criterion`, `news-item`, `work-item`, `claim`, `complete`, `decline`, `drop`,
`request`), `symbol`, the record it points to (table and id), what it rests on (the snapshot id
and, when one, the work item id) and one line of summary. The ledger is read over the API and
MCP, for a symbol or whole, newest first; the drawer's Details shows the company's entries.

## 8. The work inbox (B-58)

A work item: `symbol`, `mode` (`valuation review` or `full report`), `note` (the request in
the requester's own words, one line, no commentary, the mode not repeated; may be empty; plan 4), `snapshot_id` at posting (none for a company without one), `origin`
(`owner`, `agent`, `expiry`), the principal and time of posting, and a state:

| State | Set by | Carries |
|---|---|---|
| `pending` | the post | |
| `claimed` | `inbox_claim` | the actor and the time |
| `done` | `inbox_complete`, or `report_submit` with the item named | the report id |
| `declined` | `inbox_decline` | the reason |
| `dropped` | the system | an expiry item whose company left every watchlist while pending |

Three ways in:

- **The page.** The drawer's `Request research` button on a company with no open item (18.3),
  and `Request research` on a watchlist (18.6), which posts a valuation review for every company
  on the list with no open item. Both are the owner's writes.
- **MCP** `inbox_post`, so a request made in chat becomes an item first: the playbook posts it,
  then claims it. Every piece of work has an item and a ledger trail.
- **Expiry.** When the inbox is read, on the page or over MCP, every symbol on any watchlist
  whose latest snapshot is expired (`valid_until` before today), with no open item (pending or
  claimed) and no expiry item yet posted for that same `valid_until`, gets a `valuation review`
  item with origin `expiry`, posted by the system. A pending expiry item drops when the company
  leaves every watchlist.

`inbox_claim(item_id?)` takes the named item, or the oldest pending one. A claimed item can be
claimed again by naming it; the ledger records the takeover. *My call*: no claim timeout. The
founder is the only user, and a stale claim is a fact to see, not a rule to enforce.
`inbox_complete(item_id, report_id)` needs a published report for the item's symbol.
`inbox_decline(item_id, reason)` needs a reason. The header's Inbox count is the pending and
claimed items (18.5).

## 9. Notes, findings, kill criteria and news items (B-54, B-55)

- **A note** (B-54): `symbol`, `text`, the principal and actor, `at`, and an optional
  `override_id`, so a note can carry an override's provenance. Written over MCP and on the page
  (the owner's, under Details).
- **A finding**: a dated, sourced fact an agent records, the brand book's word. `symbol`,
  `as_of` (the date the fact describes), `text`, `source` (`{kind, ref, note}` with kind one of
  `filing`, `transcript`, `url`, `vendor`, `base-rate`), and optionally a `value` with its `unit`
  (`currency`, `percent`, `multiple`, `count`, `per-share`) and a `period` (a fiscal year, a
  quarter, `ttm`). A finding or a guidance record (9) is the only way a number from outside Fairband enters a report
  (13.3): the agent records it, then cites it. The check cannot prove a finding true; it proves
  it is recorded with its source.
- **A kill criterion** (B-55): `symbol`, `text` (a measurable event that would prove the view
  wrong), `state` (`open`, `triggered`, `retired`), the report that set it, the principal and
  time. `kill_criterion_set` moves the state with a reason. No automatic check: the playbook's
  review step reads the open ones.
- **A news item** (B-55): `symbol`, `date`, `headline`, `source` (a URL or a vendor response
  id), `text`, and the kill criterion it touches, if any.

- **A guidance record** (2026-11-07): a figure the company itself gave on an earnings call for
  a future period. `symbol`, `metric` (`revenue`, `eps`, `operating_margin`, `free_cash_flow`,
  `capex`, or the growth rate of the first two, `revenue_growth`, `eps_growth`), `period` (a
  fiscal year or a quarter), `low` and `high` (equal for a point), `basis` (`gaap`, `adjusted`,
  `constant-currency`), `as_of` (the call's date), `text` (the sentence, verbatim), `source` (the
  transcript's `response:` ref, or a filing), the principal and actor. The server computes
  `midpoint`, and, for a fiscal-year revenue or EPS figure, `step`: the growth from the base
  year's actual on file, so the agent never computes a rate. A newer record for the same metric,
  period and basis supersedes the older (`superseded_by`), in the order of the calls' dates: a
  record of an earlier call recorded later is stored already superseded; an override or a
  secondary valuation citing a superseded record is refused 409 "guidance record <id> is
  superseded by record <id>" (build rulings of Task 6b, 2026-11-07); an NTM anchor override
  (`earnings.ntm`, `revenue.ntm`) needs among its evidence a current record of the tag's metric
  (`eps` or `revenue`) for a fiscal year on the `gaap` basis, else `refused-evidence`; a lasting
  NTM override drops at the next full refresh or revalue once its record's fiscal year is before
  the snapshot's base year, "the guided year has passed" (build rulings of the final review,
  2026-11-07). Every record stays, so a
  later report shows the track record, guided against delivered. Written with `guidance_add`, read with `guidance`.

  **The rules** (the founder, 2026-11-07): guidance reaches the valuation only when it is clear,
  a number or a range for a stated metric, a stated period, on a reported basis; a range takes
  the midpoint. Words ("upper teens"), one-sided forms ("at least"), adjusted figures with no
  bridge to GAAP and constant-currency figures are recorded and discussed in the report's call
  section and do not enter the valuation: the consensus stands. No words table. A next-quarter
  figure feeds no override, even when it completes the fiscal year (three quarters reported on
  file plus the guided fourth): the engine's year-one anchor is the fiscal year that holds most
  of the next four quarters, so a completed year is behind every input it reads; the completed
  year's figure is read against the consensus for that year in the call section, a signal for
  the thesis (build ruling of Task 8, 2026-11-07, which replaces the quarter rule agreed that
  morning). A guidance-backed input takes its fiscal year by one rule: `earnings.ntm` and
  `revenue.ntm` the base year, `path.step_2` the base year plus one, `path.step_3` plus two, each
  step as the growth of the midpoint over the consensus of the year before.
  Use is at the agent's best effort, never required: a report with no guidance override is a
  normal report. Guidance enters the reviewed value through an override whose evidence names the
  record (kind `guidance`, ref `guidance:<id>`), never the mechanical value: the review log then
  shows the company's own outlook against the consensus, company by company.

All five are read over MCP and the API, and shown in the drawer's Details.

## 10. Overrides and the reviewed value (B-50, B-51, B-56)

### 10.1 What an override is

A change to one tagged input, with its reason, its evidence and its lifetime; design.md 7.3,
decided. The record: `symbol`, `tag` (10.2), `old` (the input as the engine read it on the
snapshot), `new`, `unit`, `reason`, `evidence` (one or more `{kind, ref, note}`; the kinds of a
finding's source plus `finding`, a finding id, and `guidance`, a guidance record's id (9)),
`lifetime` (`lasting`, or `period-tied` with
`period` and `corrected_value`, the value the override corrected), `snapshot_id` (the snapshot it
was made on), the principal and actor, `at`, `state` and `review_id`.

The states are the design system's words: `applied`, `refused-locked`, `refused-evidence`,
`refused-unit` (the component's word for a unit or a range the input cannot take),
`refused-not-input`, `refused-route` (the row's route does not read the tag; *my call*, a state
the component's union lacks, which the plan adds as one `// fairband:` patch), and `dropped`
with `drop_reason`. The component's `conflict-stale` is never produced (10.3). A refused override is stored with its state and
applies nothing; the answer names the rule in terms the agent can act on ("`terminal.g` is a
locked input: the terminal growth ceiling").

### 10.2 The inputs an agent may override

| Tag | Routes that read it | Unit | Range | Note |
|---|---|---|---|---|
| `phase` | every row | word | the six phases | the route follows the phase; a Start-up row overridden to Young Growth is valued by the revenue-growth route where the mechanical row had no value; the classifier's evidence stays as it was |
| `earnings.ntm` | Mature Growth | $ a share | above 0 to 1,000 | plan 1b, policy v9: the forward anchor, the NTM EPS of 5.2, from a clear full-year EPS guidance (9); an override on this tag needs an evidence item of kind `guidance`, else `refused-evidence` |
| `revenue.ntm` | High Growth, Young Growth, Decline | $ | above 0 (the range's high is the 10^15 stand-in, which the refusal sentence does not print) | plan 1b, policy v9: the NTM revenue of 5a.2 and 6a.2, from a clear full-year revenue guidance (9); evidence of kind `guidance` required |
| `growth.belief` | Mature Growth | % a year | −20% to 60% | above the sales class's `sales_p90_5y` needs primary evidence (10.3) |
| `path.hold` | High Growth, Young Growth | % a year | −20% to 300% | the held rate of years 4 to `high_growth_years`; above the cap of 5a.3 needs primary evidence |
| `path.step_2`, `path.step_3` | Mature Growth, High Growth, Young Growth, Decline | % | −80% to 300% | a consensus step; replaces a held or thin one too. Not Mature Stable: its value reads no step, only its cross-check does, and an override that moves nothing is refused `refused-route` |
| `moat.class` | Mature Growth, Mature Stable, High Growth, Young Growth, Start-up | word | None, Narrow, Wide | moves the margin of safety, the runway and the terminal return together, as the class does today |
| `margin.target` | High Growth, Young Growth, Start-up | % | −50% to 60% | |
| `capital.sales_to_capital` | High Growth, Young Growth, Decline | multiple | 0.1 to 10 | |
| `return.runway` | Mature Growth, Mature Stable | % | 0% to 100% | the runway return of 4.6 |
| `earnings.nri_gap` | Mature Growth, Mature Stable | $ a share | −100 to 100 | the non-recurring gap of 6.2 and the anchor's basis |
| `earnings.cycle_gap` | Mature Growth, Mature Stable | $ a share | −100 to 100 | plan 1b, policy v9: the correction that takes the anchor's earnings to mid-cycle for a cyclical business (14, step 6); taken off the anchor earnings and nothing else: E on Mature Stable, after the engine's own margin normalization so the two corrections add, and the NTM EPS on Mature Growth (the forward P/E, the clean EPS and the flags read the consensus as found); its bridge line labelled "mid-cycle earnings", so the reader sees a cycle judgment and not a one-time item. Build ruling of Task 1, 2026-11-07 |
| `decline.rate` | Decline | % a year | −50% to 0% | d of 6a.2 |
| `balance.debt`, `balance.cash` | High Growth, Young Growth, Decline, Start-up | $ | 0 or more | period-tied only: a correction of a vendor error |

Locked, refused `refused-locked`: r, g_T, the runway years, the fade years, the margin of
safety, the fair band, the trim multiple, the terminal return (it follows the moat), the
deciles and the growth word, and every reported figure (statements, prices, shares, estimates)
other than the two balance corrections and, since 2026-11-07, the two NTM anchors, which a
clear guidance may replace. A tag not in the table is `refused-not-input`. The
ranges are policy values (19), not settings this round. *My call* on every range.

### 10.3 The rules

- Evidence is required: at least one item. A `growth.belief` or `path.hold` above the sales
  class's 90th percentile needs one item of kind `filing` or `transcript`, else
  `refused-evidence` ("a belief above the base rate's 90th percentile needs a filing or a
  transcript").
- A value outside its range is `refused-unit`, naming the range.
- One input has one applied override: a new override on a tag with an applied one drops the old
  (`dropped`, "replaced by override n") and applies the new.
- `override_drop(override_id, reason)` drops an applied override; the review is recomputed. It is
  an agent's write: the owner neither adds nor drops an override this round (founder,
  2026-11-06: no user override function until there is a commitment to the whole of it).
- An override binds to the snapshot it was made on for provenance, and applies to the company's
  latest snapshot and every later one (10.5). There is no stale conflict: snapshots are appended
  at every price refresh, and a conflict on each would stop every agent. *My call.*
- The effective policy must be the latest snapshot's. An override, a drop, a recompute and a
  secondary valuation are refused with the price refresh's own sentence, "settings changed: run a
  revalue" (or "policy changed", "method changed"), when the effective settings hash, the policy
  version or the method version differs from the latest snapshot's; the agent runs
  `refresh_start("revalue")` and tries again. So the bridge's mechanical term is always the row's
  own figure. A review and a secondary valuation record the policy version, the settings hash
  and the deciles refresh id they ran under, as a snapshot does. *My call*, from the builder
  check: the same rule the price refresh already applies.

### 10.4 The review: the recompute and the bridge

The engine takes the applied overrides as a new argument: `value_company(inputs, deciles,
policy, today, overrides)`. Each route reads the inputs of 10.2 through one accessor that returns
the override's value when one applies and the engine's own reading otherwise, and tags an
overridden input `JUDGMENT` with the override's provenance: source "override n", the principal
and actor, `entered_at` the override's time. The result is a `ValuationResult` as today, stored
as a **review** (17): `symbol`, `snapshot_id`, `created_at`, the result, its value, levels and
designation (price ÷ reviewed value on the same edges), the override ids inside, the bridge,
and `review_method` `fairband-review/1`.

The bridge, design.md 7.4: the mechanical value, then one line per applied override in a fixed
order, then the reviewed value. The order is the method's step order: `phase`, `earnings.ntm`,
`revenue.ntm`, `path.step_2`, `path.step_3`, `path.hold`, `growth.belief`, `earnings.nri_gap`,
`earnings.cycle_gap`,
`margin.target`, `capital.sales_to_capital`, `return.runway`, `decline.rate`, `moat.class`,
`balance.debt`, `balance.cash`. Each line's delta is the value with this override and every earlier one applied,
less the value with the earlier ones only, so the deltas sum to reviewed less mechanical exactly.
A line whose step refuses ("value not positive under the reinvestment charge") shows the refusal
in place of a delta; the next valuing line measures its delta from the last valued step, and the
review is a refusal with the reason when its last line refuses; a mechanical refusal that an
override turns into a value (a Start-up reclassified) starts the bridge at "no mechanical value"
and the first valuing line carries the whole value as its delta. An overridden input's JUDGMENT
entry names its principal and actor in its source, "override n, agent claude-opus-5-5". The review's levels read the
reviewed moat. The `ValueBridge` component renders it, with each override's reason in full.

### 10.5 Following the snapshots

A review follows its company's snapshots. Every refresh that writes a snapshot for a company with
applied overrides writes a review on it: a full or scoped refresh and a revalue recompute it on
the new inputs; a price refresh reprices the latest review as it reprices the snapshot
(`reprice`), so the reviewed value, its levels and its window stay and its designation moves.
Before a recompute at a full or scoped refresh, a period-tied override is checked: it drops
(`dropped`, by the system, with the reason) when the company's data date moved, or when the
engine's own reading of its input on the new snapshot differs from `corrected_value`. A review
carries its snapshot's validity window and expires with it. A review that is a refusal has no
value; the row shows an em dash and the Details say why.

### 10.6 The log (B-56)

One row per review written: `at`, `symbol`, `refresh_id`, `snapshot_id`, `review_id`, the
mechanical phase and value, the reviewed phase and value (none on a refusal), the latest
secondary value (none without one), the price, the mechanical designation, and the latest
published report's stance. Read over the API and MCP (`review_log`). It is the measure of whether
the agents help, read once it has rows; this round only writes it.

## 11. The secondary valuation (B-97)

A second valuation beside the engine's routes, computed by the engine from inputs the agent
supplies, made only where the route refuses or no route fits. The founder, 2026-11-07, first
asked for it on every report ("rather than it being a fall back, to always be done (and act as
fallback if the main route is refused). I want a secondary valuation following a standard DCF
method"), and reversed that on reading the first live report, 2026-11-08, whose agent held a
company the route put well above the price because the DCF sat below it: "If the DCF says one
thing and our main method says another, then the DCF should only act as a fallback if the main
method is rejected. I don't want the DCF to be a factor in the agent's judgement if the main
method is working. … Don't do a DCF if the main method is working." It serves one need: the
fallback where no phase or route fits or where the route refuses, so a company the method cannot
value still has a value on the row and in the report.

Two forms, one tool: `secondary_valuation(symbol, reason, evidence, drivers?, parts?, debt?,
cash?)`, with exactly one of `drivers` and `parts`.

**The standard form, `drivers`.** The free cash flow to the firm is projected from drivers the
agent sets, by Damodaran's FCFF model, from the trailing revenue on file:

    drivers = {years: N, revenue_growth: [g_1 … g_N], operating_margin: [m_1 … m_N],
               tax_rate: t, sales_to_capital: s, terminal_growth: g}

    revenue_0 = the trailing revenue as the engine reads it (fact:<symbol>/revenue/ttm)
    revenue_t = revenue_{t−1} × (1 + g_t)
    EBIT_t = revenue_t × m_t;  NOPAT_t = EBIT_t × (1 − t)
    reinvestment_t = max(0, revenue_t − revenue_{t−1}) ÷ s
    FCFF_t = NOPAT_t − reinvestment_t;  PV_t = FCFF_t ÷ (1 + r)^t
    terminal FCFF = NOPAT_N × (1 + g) × (1 − g ÷ ROIC_T) when g > 0, NOPAT_N × (1 + g) when g ≤ 0
    terminal = terminal FCFF ÷ (r − g), discounted by (1 + r)^N

with r the policy's required return, locked (the founder, 2026-11-07: "keep the policy's hurdle
rate"), ROIC_T the policy's terminal return for the moat class as reviewed, and g from −100% to g_T (a
terminal growth at or below zero releases no capital, as the explicit years reinvest nothing in a
shrinking year; build ruling of Task 3, 2026-11-07). N runs from `secondary_years_min` (3) to `secondary_years_max` (15); every list has N entries;
each driver is bounded by `secondary_driver_ranges` (19): a growth rate −0.80 to 3.00, a margin
−0.50 to 0.60, a tax rate 0 to 0.50, sales-to-capital 0.1 to 10. *My call* on the reinvestment
floor (a shrinking year reinvests nothing, so a decline does not create cash) and on the
terminal reinvestment through the policy's terminal return, which is the engine's own stable-growth
rule, so the two values rest on one terminal convention. The record stores the projection table,
every year's revenue, EBIT, NOPAT, reinvestment, FCFF and present value, cited
`secondary:<id>/years/<t>/<line>`, and the drivers, cited `secondary:<id>/drivers/<name>` (a list
driver by `<name>/<t>`).

**The sum-of-parts form, `parts`.** As built in plan 1: one to `secondary_parts_max` (10) parts,
each `{name, fcff, terminal_growth, note}`, `fcff` the free cash flow to the firm in dollars for
years 1 to N, each `terminal_growth` from −100% to g_T; the arithmetic of method 15.2, with the
same terminal rule at or below zero. It stays for a conglomerate or a company whose
cash flows the agent builds segment by segment; the playbook uses the standard form unless the
parts form fits better. *My call* to keep it: it is built, tested and a different question.

**Common to both.** Firm value is the sum over the parts or the one projection; equity = firm
value − debt + cash; value a share = equity ÷ diluted shares; the levels by the moat class (as
reviewed); the designation on price ÷ value. Debt and cash are the newest annual balance sheet's
on file, read by the server at the call as assembly reads them for the growth and Decline routes
(an applied `balance.*` override counts); the agent may pass `debt` and `cash` explicitly, each
with evidence, where the balance sheet is wrong or missing, and the record stores the three
figures used with their source, so the value rebuilds. A foreign filer is refused, "foreign
filer: currency and share-unit handling not built yet" (B-28); a row with no diluted share count
is refused. Evidence is required, as on an override; at least one item backs the path or the
drivers and names no `figure`. A driver outside its range, a `terminal_growth` outside −100% to
g_T, an N
outside the range, a list of the wrong length, or a part count above the maximum is refused
naming the rule. Why drivers and not a value: the agent's judgment is the drivers; the tool keeps
the projection, the discounting, the terminal and the equity bridge, which is what makes the
number a tool output.

**The grid.** Every record carries a three-by-three sensitivity grid: the value a share at r −1
pp, r and r +1 pp across g −1 pp, g and min(g +1 pp, g_T), computed with the record and cited
`secondary:<id>/grid/<i>/<j>`; on the parts form the rows are shifts of −1, 0 and +1 pp applied
to every part's growth, each capped at g_T; the grid is absent where r − 1 pp would not exceed
the highest growth (build rulings of Task 3). It is a display of how much of the value is assumption, not a
value: the rate in force stays r. *My call*; `SensitivityGrid` draws it (18.4).

**Required where neither the route nor the review values the company, refused where one does
(plan 3).** The report check refuses a submission on a refused latest snapshot whose current review
has no value and that cites no secondary valuation on it: "the report needs a secondary valuation
on snapshot <id>" (13.3). A review that values a refused row (an override routed it) is the main
method working, so the fallback is not made there either: the route refuses the call, 400 "the
review values <symbol>: the secondary valuation is the fallback where neither the route nor the
review values the company", and Appendix A says "no secondary valuation: the review values the
company" (build ruling of plan 3's final review, 2026-11-08). The rule does not apply to a company that
cannot have one: a foreign filer or a snapshot with no diluted share count, the two refusals the
secondary route makes that no agent can fix; Appendix A names the reason and the playbook has the
agent say it in the Valuation section (build ruling of the final review, 2026-11-07). Where the
latest snapshot has a value, the secondary route refuses the call, 400 "the route values
<symbol>: the secondary valuation is the fallback where it refuses", the check requires none,
Appendix A says "no secondary valuation: the route values the company", and the report talks
about the route's value alone: FMP's DCF figure (`dcf`) is read as a cross-check on the fallback
only, never beside a route's value (*my call*, from the founder's rule that no DCF is a factor
where the route works). Where neither the route nor the review values the company, the secondary stands in on the
row, in the drawer and in the report (18.1, 18.2). A secondary valuation made before plan 3 on a
valued snapshot stays on file and reads as it was; a report that cites it stays published.

Stored (17) with the form, the drivers or the parts, the projection or the per-year present
values, the grid, the firm value, the equity, the value a share, the levels, the reason and the
evidence, the snapshot id, the principal and actor, and `secondary_method` `fairband-secondary/2`
(the drivers form and the grid; a plan 1 record stays `fairband-secondary/1` and reads as it was).
It is as of its snapshot: no refresh touches it; its stored price ÷ value and designation are at
its snapshot's price, and the page reads price ÷ value against the latest quote where it shows
the figure; it expires with the snapshot's window and stays in the history after a full refresh
writes new statements, shown with its date. The agent makes a new one at the next review.

**FMP's own DCF as a cross-check.** A fifth pass-through, `dcf(symbol)` (15.3), fetches FMP's
discounted-cash-flow and levered-discounted-cash-flow figures and stores them as vendor responses,
so the Valuation section of a report on a refused row may cite FMP's figure beside the secondary
valuation as a second opinion on the fallback, in one sentence (plan 3: not on a valued row). FMP's custom DCF endpoints, which take drivers and return a projection, are not used: the
value would rest on FMP's own cost of capital and template, which the method cannot state. *My
call*; the founder named FMP's template as the reference, and the drivers form above is that
template under the policy's rate.

## 12. Key judgments (B-52)

A judgment is the record of one of the report's input decisions: `judgment` (`phase`, `moat`,
`belief`, `roic`, `target_margin`), `decision` (one or two sentences, in words, no figure) and
the override it produced, if one. Judgments come with a report submission (13.1) and are stored
with the report. Every report carries `phase`, `moat` and `belief` (`belief` reads as the rate
the route holds: the belief, the held rate, or the decline rate); `roic` and `target_margin`
where the route reads them.

The founder, 2026-11-07: "Key judgements to me is just a record of overrides etc. … this is not
an important section and could be the last section at the end." So the record holds no `bull`
and `bear` text: the debate about the business is the report's own section (13.1, section 5),
and the judgments are the audit trail of what the agent changed. The report's last section,
"Key judgments", lists them in one sentence each; the drawer's Details lists the latest.
Migration 006 drops the `bull` and `bear` columns; a plan 1 report's judgments keep their
decisions.

## 13. Reports and the number check (B-53, B-59)

### 13.1 A report

`report_submit(symbol, mode, stance, sections, judgments, kill_criteria, news_items,
work_item_id?)`. `mode` is `valuation review` or `full report`. `stance` is one of `buy`,
`hold`, `trim`, `avoid`: the three zone words of the brand book and one for a company the agent
would not hold at any price shown; *my call* on the four. `sections` are the twelve below, in
order, each `{heading, parts}` where a part is a plain string or `{cite, ref, period?}` (13.3);
a valuation review omits sections 2 and 3 and names `reuses_full_report_of`, the full report it
reuses, or says there is none (design.md 7.5). The server generates Appendix A (every input with
its tag, source and dates; the overrides with reasons and evidence; the bridge; the secondary
valuation's drivers or parts and its projection; the checks that ran; the versions; the
classifier's evidence) and Appendix B (the glossary: the terms of `docs/method.md` 13 the report
uses) from the stored records; the agent writes neither.

**The sections.** The founder, 2026-11-07: "These reports need to be human readable friendly, the
valuation and the details of that should only be talked about in the valuation section. The rest
of the report should detail and debate the merits of the business and its outlook." The list
replaces design.md 9.3's ten:

| # | Heading | Mode | What it holds |
|---|---|---|---|
| 1 | Summary | both | One page: the stance; the thesis in two or three sentences; the value against the price and the levels; the phase in one sentence, with the word "cyclical" when the agent finds the business cyclical; three reasons for; three risks; what would change the view; the end of the validity window. |
| 2 | The business | full report | The products; the revenue by product and by region over three years; what drives revenue; the customers and any concentration; the unit economics. |
| 3 | Industry and competition | full report | The value chain; the industry's size and growth; the competitors; the company's position; the moat by Damodaran's five sources; "are the economics favorable?" in a plain answer. |
| 4 | Financial performance and health | both | Six parts, one for each table of 13.5, each two or three plain sentences that cite its cells; on the page, each part's charts above its sentences (18.4). |
| 5 | The last earnings call | both | The founder, 2026-11-07: "prices crash or increase based on the earnings call"; "in many cases, the thesis is formulated, confirmed, or broken in the last earnings call". One page, in this order. (a) The verdict: the call's date and quarter, whether it confirmed, changed or broke the thesis, and the price's move on the next trading day from the stored closes. (b) The quarter against expectations: a table of revenue, EPS, the operating margin and free cash flow, each against the prior year and against the consensus for the quarter with the surprise, every cell a fact, a stored estimate or a derivation; then what drove it: price, volume, mix, currency, one-time items, named because the engine anchors on earnings without them. (c) The story management is telling: the frame in their words, quoted; three to five claims, each with the claim and its figure and timeline, the evidence in the numbers, the driver it moves, written as the register's phrase for it (plan 5; the inputs it may name: the growth of years two and three, the held rate, the target margin, reinvestment, the moat, the risk) and the test that would show it true or false and by when; a verdict on each in Damodaran's words, possible, plausible or probable, and only a probable claim moves a figure; the drift since the last call (a claim that grew or vanished, new words such as "macro" or "visibility", a metric no longer reported); what they did not say. (d) The guidance: a table of the records (metric, period, low, high, midpoint, basis, raised, held or cut against the prior record, against the consensus), then one sentence on what the valuation takes from it: the override, or that the analysts' average estimate stands (9; the words of plan 5). (e) The positives and the negatives, each tied to a figure or a quote. (f) The questions and answers: the two or three analysts' pushbacks that matter to the thesis and whether the answers were direct. (g) What the thesis takes from it: the kill criteria touched, the one thing to watch next quarter, and the gap: the price moved X, the reviewed value moved Y. When the vendor has no transcript (five of a hundred random companies on 2026-11-07, companies that hold no call), the section says so and reads the press release through the host's tools, the figures still from the statements. |
| 6 | The bull case and the bear case | both | The debate about the business and its outlook, in arguments: demand and how long it lasts, where the company is in its cycle, competition and the moat, pricing power, capital allocation, management, the balance sheet. Each side's strongest case, in words a reader without the method follows. Figures may be cited; valuation arithmetic, inputs, tags and parameters are not in this section. |
| 7 | The thesis | both | This report's own story, written against management's (the founder, 2026-11-07: "the company narrative should be the basis for the thesis, whether its accepted or rejected and everything in between"). It opens by taking a position on each claim of section 5: accepted, rejected or held open. The claims accepted are the drivers the valuation moves; the claims rejected are where the report's value parts from the consensus or the guidance, and why; the claims held open are the kill criteria and what to watch. Then the investment case that settles the debate and leads to the stance: what must be true for the stance to be right, and what the agent expects to happen. Written for every stance: a buy says why the market is wrong on the downside; a hold says why the price is fair and what the view waits for; a trim says why the price ran ahead of the business; an avoid says why the business is not worth owning at the prices shown. The kill criteria of section 11 test it. |
| 8 | Valuation | both | The only section that talks about the valuation and its detail. Where a guidance override moved an anchor or a step, one sentence names it (9). The phase: the growth word and the margin direction behind it, any warning the figures raised (a check flag, in the method's words; plan 5), the Dickinson stage, and why if an override changed it. The growth the price needs; the belief and why. The mechanical value and the reviewed value, with one sentence in words for each override that moved it (the figures may be cited here); no bridge table, no tags. Where the route refused: the secondary valuation stands in and leads the section, the drivers in words with their figures cited, the value, and FMP's figure in one sentence when read; where the route values the company there is no second value (11, plan 3). For a cyclical business, where it is in its cycle and the mid-cycle basis used. The sensitivity grid. For Start-up, the price-implied requirement; for Decline, the floor and the distress-weighted value. |
| 9 | Price and multiples | both | The price facts: the current price; the high and the low of the past year and where the price sits between them; the change over one, three and five years and the drop from the last peak. The multiples: the trailing P/E on two bases (the clean P/E on the method's earnings, the reported P/E) and the forward P/E, each against its own history: the ten-year average, median, high and low of the trailing series (13.7), and the forward series since Fairband began logging it. The phase's multiples. None is a target. On the page, the charts of 18.4. |
| 10 | Recent news | both | The dated items that matter to the value. |
| 11 | Risks and kill criteria | both | The risks, and the measurable events that would prove the thesis wrong. A threshold the agent chooses is never a finding: tie each event to a stored figure, cited, or state it in words. |
| 12 | Key judgments | both | The record (12): each judgment's decision in one sentence, naming the override it produced. Last, because it is the audit trail and not the reading. |

A valuation review has ten sections. The old section "Life-cycle phase" is folded into 8; the
old "Key judgments" with its bull and bear text is replaced by 6, 7 and 12. The three sections 5,
6 and 7 chain: the call gives the story, the debate argues it, the thesis decides it.

**Cites and overrides out of the main text.** The founder, 2026-11-07: "Citations and overrides
can be footnotes, but never in the main report content." The submission keeps every cite as
`{cite, ref, period?}`, since the check needs the ref; the rendering changes. On the page and in
the export, a cite shows as its text followed by a footnote mark, and the references are listed
once, numbered, after section 12 and before Appendix A, each with its ref and the source in
words ("snapshot 412, the price, 3 Nov 2026"; "the 10-K for 2025, finding 88"). No ref appears
in the main text. The overrides, the bridge and the secondary's projection are in Appendix A
only; the main text may say in words what an override changed and why (section 8), and nowhere
else. `ReportReader` keeps its dotted underline on a cited number as the affordance, with the
footnote number beside it.

**The words (plan 5).** The founder, 2026-11-09, on the GOOG report: the agent wrote "The belief
is 5.3%" and explained the term only when asked; the repository is to be open-sourced, so a
reader has none of the method's context. The report writes what a figure is, not what Fairband
calls it. The method's terms (`docs/method.md` 13, and the register's table) do not carry a
sentence: the text gives the plain phrase, and the term once, in brackets after it, in section 8
only, where the reader needs it to find the figure in Appendix A or on the Methodology page;
outside section 8 the term does not appear. The names of Fairband's parts never appear: "Fairband"
for the product, and what the thing did for the rest. Appendix B still lists the terms the text
uses, which under this rule are the bracketed ones. The playbook's register carries the table of
terms and phrases, the template's example is written in them, and step 12 reads the report once
as such a reader before it is submitted (14). A warning at publish was considered and deferred
(B-135): a word list is never complete, and a match is not a defect once the term was explained.

**The text's shape (plan 3).** A part may hold line breaks, and the shape the agent writes is
the shape the page shows. The founder, 2026-11-08, on the first live report: "the report is very
difficult to read on the html page. Its like its a text dump." The agent's text was structured;
`ReportReader` rendered each section as one paragraph. The subset, which the template teaches and
the reader and the export render: a blank line between paragraphs; a bullet line `- `; a numbered
line `1. ` (the number as written, one or two digits); a table as lines beginning with `|`, the
first row the header and the `|---|` row the separator; `**bold**` for a lead word or phrase. A
cite is inline in any of them. Nothing else is rendered: no heading marks (the section's heading
is the server's), no links, no nested list, no image. The reader (18.4) renders these as blocks
with the design system's type: paragraphs at the prose measure, lists, tables with a header row,
bold in `ink`; a table spans the reader's width and scrolls only when wider than it (build
ruling of plan 3, Task 4: a four-column claims table cannot read at the prose measure). The check (13.3) reads a list's number and
a table's separator as marks, never as quantities. The Markdown export passes the text through,
which GFM renders the same way.

A submission is published whole or rejected whole. Published: stored (17) with its revision
number for the symbol, the snapshot, review and secondary it cites, the principal and actor; the
work item named is completed in the same write. Rejected: nothing stored but the ledger row;
the answer carries the findings, each `{where, what, detail}`, with `where` the section index,
the part index and the citation; the published report is unchanged.

The latest published report is the company's report; earlier revisions stay, listed by date.

### 13.2 References

A `ref` names a stored value:

| Ref | Resolves to |
|---|---|
| `snapshot:<id>/value`, `/price`, `/price_to_value`, `/levels/<name>` (buy, fair_low, fair_high, trim) | the snapshot's figures |
| `snapshot:<id>/inputs/<name>`, `/intermediates/<path>`, `/phase/<field>` | a tagged input, an intermediate by its JSON path, a classifier field |
| `review:<id>/value`, `/levels/<name>`, `/bridge/<n>/delta` | the review's figures |
| `secondary:<id>/value`, `/firm_value`, `/parts/<n>/pv/<t>`, `/years/<t>/<line>`, `/drivers/<name>`, `/grid/<i>/<j>` | the secondary valuation's: its value, its parts' present values, its projection's lines (`revenue`, `ebit`, `nopat`, `reinvestment`, `fcff`, `pv`), its drivers and its grid (11) |
| `sensitivity:<id>/<i>/<j>` | a cell of a stored sensitivity grid of the route (13.8) |
| `guidance:<id>/low`, `/high`, `/midpoint`, `/step` | a guidance record's figures (9), in the metric's unit; `step` a ratio |
| `multiple:<symbol>/<series>/<date>`, `/<stat>` | a point of the trailing or forward P/E history (`pe`, `pe_forward`), or its `avg_10y`, `median_10y`, `high_10y`, `low_10y` (13.7) |
| `fact:<symbol>/<line>/<fiscal_year or ttm>` | a stored statement line, normalized as the engine reads it |
| `table:<symbol>/<table>/<row>/<year>` | a cell of the financial tables (13.5) |
| `estimate:<symbol>/<period>/<field>` | a stored consensus figure (the estimates read) |
| `close:<symbol>/<date>` | a stored daily close (the price-history read) |
| `peer:<symbol>/<peer>/<field>` | a mature peer's figure as assembly reads it (the peers read) |
| `finding:<id>` | a finding's value |
| `derived:<id>` | a derivation (13.4) |
| `response:<id>/<json pointer>` | a field of a stored vendor payload (15.3) |
| `policy:<name>` | a policy value |

A report cites the snapshot it rests on: the company's latest when the agent read it. A ref to
another snapshot is `wrong snapshot`. A price refresh during the research does not reject the
report: a later snapshot that is a reprice of the cited one, with the same data date, method,
policy and settings hash, counts as the cited one, and the report keeps the cited snapshot's
figures and its price date, which the header shows. A revalue or a full refresh in between does
reject, with the latest snapshot's id in the detail; the agent re-reads. *My call*, from the
builder check.

### 13.3 The check

The structure first, each failure one sentence: twelve sections for a full report and ten for a
valuation review, under the exact headings of 13.1 in order; the stance a `stance_words` word;
one judgment of each kind the route needs, each with a `decision` and no figure in it; and, on
a refused latest snapshot whose current review has no value (11, plan 3), a secondary valuation on it, refused "the report
needs a secondary valuation on snapshot <id>", unless the snapshot is a foreign filer or has no
diluted share count. A valued snapshot needs none and the route refuses one. Then the numbers.

The six failures, in the server's words, which the component and the playbook match on:
`unresolved reference`, `wrong unit`, `wrong period`, `wrong snapshot`, `a number with no
reference`, `a derived figure the engine has not emitted`.

- A quantity in a plain part is `a number with no reference`. A quantity is a money amount, a
  percentage, a multiple, a decimal, or an integer of two or more digits that is not a year
  (1990 to 2099), a fiscal-year or quarter form (`FY2025`, `Q3`), a filing form (`10-K`) or a
  section number. The playbook tells the agent to cite every quantity and to write small counts
  in words. *My call* on the token rule; the builder refines it on the test fixture.
- A cite's ref that resolves to nothing is `unresolved reference`.
- A cite's text is parsed as a number with a unit suffix (`$`, `%`, `x`, none) and compared with
  the referenced value in the ref's unit after the report's rounding (design.md 9.2: prices to
  cents, values to whole dollars, percentages to one decimal, multiples to two). A suffix that
  does not fit the unit is `wrong unit`; a number that does not match is also `wrong unit`, with
  the referenced value in the detail. *My call*: one failure word for both, since the component
  lists six, not seven.
- A cite with a `period` that is not the ref's is `wrong period`; a ref whose value has a period
  and a cite with none passes.
- A cite whose ref is `derived:` with no stored derivation, or a plain part that names a ratio of
  two cited figures, is `a derived figure the engine has not emitted`.

### 13.4 Derivations

`derive(symbol, derivations)`: the agent's arithmetic as a tool output; `derivations` is a list
of `{operation, a, b, years?}`, one call for many. The operations: `ratio` (a ÷ b),
`difference`, `sum`, `growth` (a ÷ b − 1) and `cagr` (over `years`). `a` and `b` are refs, a
`table:` cell included. Each result is stored with its refs and operation, and cited as
`derived:<id>`. *My call*: five operations; a sixth comes when a report needs it.

### 13.5 The financial tables

design.md 9.3 says it: in tier 1 scripts compute all the numbers; in tier 2 the analysts write the
sentences. The six five-year tables of the report's section 4 (growth and profitability; cash
flow; balance sheet and solvency; returns on capital; capital allocation; quality scores) are
computed by the server from the stored facts and the engine's own readings, each cell with its
ref `table:<symbol>/<table>/<row>/<year>`, and served by `financial_tables(symbol)`. The agent
cites the cells; it derives none of them. The quality-score row carries Altman Z″ and Piotroski F
for every row whose balance lines are on file, by `distress.py`'s arithmetic, which today runs on
Decline rows only; Beneish M reads "not on file" until a source ships. `financials` likewise
answers with a ref beside every figure, so a cite costs the agent nothing to build. *My call*,
from the builder check: without the tables, section 4 alone would take the agent a hundred
`derive` calls.

### 13.6 Export (B-59)

`GET /api/reports/{id}/markdown` renders the published report as Markdown: the twelve sections
with cited numbers as plain text, each followed by its footnote mark, then the references list,
then Appendix A as tables and Appendix B as a list, with a header line naming the symbol, the
mode, the date, the actor and the revision. Where the page draws a chart (18.4), the export
carries the chart's table twin under the same title. The report page's `Download .md` button
fetches it; the page's print stylesheet serves save-as-PDF. No server-side PDF unless the print
result falls short.

### 13.7 The multiples history

The founder, 2026-11-07: the report shows "the PE and Forward PE multiples, where does it sit
historically on those, with line graphs for each showing average horizontal lines". Two series
on file, served by `GET /api/companies/{symbol}/multiples-history` and the read tool
`multiples_history(symbol)`, each point with its ref:

- **The trailing P/E**, daily, ten years: GuruFocus's `pettm` series, fetched as a pass-through
  (15.3, `pe_history`), stored as a vendor response and reused for seven days. The read serves
  the points as `multiple:<symbol>/pe/<date>` and the series' statistics over the ten years on
  file as `multiple:<symbol>/pe/avg_10y`, `/median_10y`, `/high_10y`, `/low_10y`, computed by the
  server over the points at or above zero (a loss year has no P/E). The stocks repo's notes
  record the endpoint as working, with daily rows since 1997.
- **The forward P/E**, Fairband's own log: no vendor on file gives a forward P/E history
  (GuruFocus's history is zero for every forward ratio; FMP has none), so the server appends a
  row to `multiples_log` at every price refresh and every snapshot: the date, the price, the
  clean, reported and forward P/E of the engine's intermediates. The read serves it as
  `multiple:<symbol>/pe_forward/<date>` with the same four statistics over the rows on file, and
  says in `since` when the log began. The chart says so while the log is short, and with fewer than five readings the page shows
  the newest reading as a figure with the sentence, no line and no average (plan 4: a one-point
  line with an average read as broken). *My call*: an
  honest short series over a vendor's absent one.

The two series are not the mechanical multiples of 8's text, which stay the snapshot's
intermediates at the snapshot's price; the history is context, and the agent cites a point or a
statistic of it as any other ref.

### 13.8 The sensitivity grid of the route

The Valuation section shows how much of the route's value is assumption. The agent cannot
compute that: every number is a tool output. `sensitivity(symbol, row_tag, row_values, col_tag,
col_values)` runs the engine on the company's latest snapshot under the current review's applied
overrides, with two overridable inputs (10.2) set to each pair of the values given, at most five
by five, and stores the grid as a record cited `sensitivity:<id>/<i>/<j>`, with the pair in
force marked. Nothing is overridden: the record is a reading, logged like a derivation. A tag the
route does not read, or a value outside its range, is refused as an override would be. The page
draws the record the report cites with `SensitivityGrid` (18.4), the price as the baseline. *My
call*: plan 1's template promised "a small sensitivity table" with no tool to make one. A reading
taken under a review that is no longer the company's current review on its snapshot is cited as
`wrong snapshot` ("the review moved"), as a `review:` cite is (build ruling of the final review).

## 14. The playbook (B-57)

A skill directory in the repository, `playbook/fairband-research/`, with `SKILL.md` (the Agent
Skills format: frontmatter `name` and `description`, then the instructions) and a `reference/`
folder (the tool list, the citation rules, the report template, the register). The user installs
it in the host: a copy or a link under `~/.claude/skills/` for Claude Code and Claude Desktop, and
a line in `AGENTS.md` for Codex. The README gives the MCP registration for each host; for Claude
Code: `claude mcp add fairband -- uv run --directory <repo> fairband mcp`. First host: Claude
Code. *My call.* The plan adds the `fairband` console script to `pyproject.toml`
(`[project.scripts]`), which does not exist today; `uv run python -m fairband mcp` works either
way.

The flow, the TradingAgents roles of design.md 7.1 as steps the one skill runs (the host may use
subagents for the analysts and the debate; the skill does not require it). The founder's rulings
of 2026-11-07 reshape steps 6 to 10: the debate is about the business and its outlook, the thesis
settles it, a company the route cannot value gets the standard DCF as its fallback (plan 3:
never beside a route's value), and a cyclical business is valued at mid-cycle.

1. `identify` with the model identifier you run as.
2. `inbox_list`; claim the item, or post one for a request made in chat and claim it.
3. Read the company: `company`, `financials`, `financial_tables`, `estimates`, `peers`,
   `price_history`, `multiples_history`, the latest `report`, `notes`, `findings`, `overrides`,
   `reviews`, `secondary`, `kill_criteria`, `policy`, and `methodology` for the route. Section 4
   of the report is written from the tables' cells. The company is refreshed first, a scoped
   refresh on every item, so the report reads the latest price and the row's price, price ÷
   value and designation are current when it publishes (B-126, plan 5; before plan 5 only an
   `expiry` item was refreshed, and QCOM's report 2 of 8 Nov 2026 read the close of 4 Nov). The
   agent keeps the id `refresh_start` answers and reads the new snapshot's refresh id against
   it: a company whose fetch failed inside a run that ended `done` has no new snapshot, and the
   agent then goes on with the stored one and names the price's date in section 9 (the build's
   final review, plan 5).
4. The Fundamentals Analyst: the business and the industry from the filings (the host's own
   tools), `transcript` and `segments` from Fairband; record a `finding` for every number from
   outside Fairband that the report will cite, with its source.
5. The last earnings call: `transcript_dates` for the newest call, `transcript` for its text,
   the previous call's for the drift; the quarter's figures from the statements and the stored
   consensus for the quarter, the surprise by `derive`; the price's move on the next trading day
   by `derive` of two closes; each figure quoted from the call a finding with the transcript as
   its source; every clear guidance figure a `guidance_add` record (9), and the one-sided, worded
   or adjusted ones recorded with their text for the section; the story's claims with their
   drivers, tests and verdicts, the drift and what was not said (13.1, section 5). When the vendor
   has no transcript, the press release through the host's tools.
6. The News Analyst: `news` from Fairband and the web; candidate kill criteria; large price
   moves explained.
7. The cycle. Is the business cyclical? The signs: the industry (memory and other
   semiconductors, energy, mining, steel, chemicals, shipping, autos, airlines, homebuilders,
   machinery); ten years of revenue and operating margin with a swing from peak to trough; prices
   set by a commodity or by industry capacity; inventory cycles; a consensus that extends a peak.
   The engine does not flag a cyclical and values a peak as if it lasted; the stocks repo's notes
   record the same limit (MU, FRO). For a cyclical, place the company in its cycle: the operating
   margin against its ten-year median and revenue against its trend, from the tables; record the
   evidence as findings. The thesis names the position, the Summary says "cyclical", and the
   valuation rests on mid-cycle figures (step 8).
8. The Valuation Analyst: the engine's result, its inputs and intermediates, in plain words; the
   candidate judgments.
9. The debate: the bull case and the bear case about the business and its outlook, as arguments
   a reader follows without the method: demand and how long it lasts, the cycle, competition and
   the moat, pricing power, capital allocation, management, the balance sheet, and the claims of
   the call. Not a debate about inputs or parameters. The thesis settles it: a position on each
   claim of the call, accepted, rejected or held open, then what must be true for the stance to be
   right, for every stance.
10. The Research Manager decides the judgments from the thesis and writes the overrides, one
   input each with evidence; a clear full-year guidance, or a quarter that completes the year,
   replaces the NTM anchor or a consensus step through an override citing the record, best
   effort, never required (9); reads the review and the bridge. For a cyclical: on the mature routes the
   anchor at mid-cycle earnings through `earnings.cycle_gap` and the belief at the through-cycle
   rate; on the growth routes the target margin at the mid-cycle margin and the held rate at the
   through-cycle rate; a kill criterion on the margin against its median. Where neither the route
   nor the review values the company, and only there (plan 3): the standard DCF with `secondary_valuation` as the fallback,
   the drivers at mid-cycle for a cyclical, the parts form where a sum of parts fits better, and
   `dcf` for FMP's figure as a cross-check on it. Where the route values the company, no DCF of
   any kind. `sensitivity` for the route's grid; `derive` for any ratio the report needs.
11. The stance, from the reviewed value against its levels and the thesis; on a refused row, from
    the secondary valuation's value against its levels and the thesis; the report's reasons carry
    it. No DCF weighs on the stance where the route values the company (plan 3).
12. The report: the twelve sections with every quantity cited; the judgments as the record of
    the decisions; read once as a reader who has never seen Fairband before it is submitted
    (plan 5); `report_submit`; on a rejection, fix each finding and submit again.
13. `inbox_complete`, or name the item in the submission.

Rules the skill states: never write a number you did not get from a tool; cite every quantity;
small counts in words; the register of design.md 9.2 (the answer first, short sentences, rounded
numbers); the report writes what a figure is, not what Fairband calls it: the method's terms as
`reference/register.md` writes them, the plain phrase in the text and the term once in brackets
in section 8 only, and the names of Fairband's parts (the engine, the classifier, the route, the
snapshot, the check, a flag, the bridge, a tag, an id) never (plan 5; the founder, 2026-11-09, on
the GOOG report: "The belief is 5.3%" assumes a reader who knows the method, and the repository
is to be open-sourced); no first person, Fairband has no voice; the reason on an
override is your own words and is kept verbatim; the valuation and its detail are in section 8
only, and the rest of the report argues the business; guidance is used only when it is clear, and
the consensus is the fallback; a chosen threshold is never a finding; only
the lead agent identifies.

## 15. The MCP server (B-48)

### 15.1 The command

`uv run fairband mcp [--port 8470]`: stdio, started by the host. Tools only; no resources or
prompts this round. *My call.* Each tool's description is one sentence; the result is the API's
JSON, or one sentence on a refusal with the API's detail.

### 15.2 Read tools

`screen(sort?, direction?)`, `company(symbol)` (the drawer's body: the latest snapshot in full),
`financials(symbol)` (the fiscal-year series, the trailing figures and the balance years, from the
stored facts, a ref beside every figure), `financial_tables(symbol)` (13.5), `estimates(symbol)` (the stored consensus), `price_history(symbol, years?)` (the
stored closes), `peers(symbol)` (the mature peers with their figures and the source),
`watchlists()`, `inbox_list(state?)`, `reports(symbol)`, `report(symbol, id?)`,
`notes(symbol)`, `findings(symbol)`, `overrides(symbol)`, `reviews(symbol)`,
`secondary(symbol)`, `kill_criteria(symbol)`, `news_items(symbol)`, `ledger(symbol?, limit?)`,
`review_log(symbol?)`, `policy()`, `methodology(section?)` (the Methodology page's section text,
in plain words, with the live values), `refresh_status()`.

### 15.3 Vendor pass-throughs

Seven vendor endpoints the engine does not read, fetched by the server with its key, stored as
vendor responses (so a report can cite `response:<id>/...`) and reused inside `reuse_hours`:
`transcript(symbol, year, quarter)` (the earnings call transcript), `news(symbol, limit?)` (stock
news), `segments(symbol)` (revenue by product and by region), `insider_trades(symbol)`, all four
from FMP as built in plan 1; `transcript_dates(symbol)` (FMP's earning-call-transcript-dates: the
fiscal year, the quarter and the date of every call on file, newest first, so the agent never
guesses a year; checked live 2026-11-07: 84 calls for MSFT, the newest Q1 FY2027 on 28 Oct 2026;
95 of 100 random companies of the live universe had a transcript inside 120 days, the five without
being companies that hold no call); `dcf(symbol)` (FMP's discounted-cash-flow and
levered-discounted-cash-flow figures, two responses under `dcf` and `levered`; 11); and
`pe_history(symbol)` (GuruFocus's `pettm` daily trailing P/E series, reused for seven days;
13.7), the first GuruFocus pass-through, on a GuruFocus client built as the refresh builds its
own, unpaced (GuruFocus's quota is monthly) and stored under the refresh's provider name `gf`; a
payload that reads as no series is stored as unusable and never reused (build rulings of Task 6,
2026-11-07). The exact
routes are the builder's to check against each vendor's documentation at build time. The calls
run on the server through one rate limiter per vendor shared with the refresh worker, so the pace
holds, on FastAPI's sync-route thread: at most four vendor calls are in flight (a semaphore), a
fifth waits at most ten seconds for a slot and is answered 503 "the pass-throughs are busy: four
calls are in flight, try again" past it; a stored response inside its reuse window takes no slot;
no answer carries a key. *My call* on the seven; the thread shape as built (Task 8's rulings). The
ownership and picks pass-throughs wait for B-71 and B-72.

### 15.4 Write tools

`identify(agent)`; `inbox_post(symbol, mode, note?)`, `inbox_claim(item_id?)`,
`inbox_complete(item_id, report_id)`, `inbox_decline(item_id, reason)`; `note_add(symbol, text,
override_id?)`; `finding_add(symbol, as_of, text, source, value?, unit?, period?)`; `guidance_add(symbol,
metric, period, low, high, basis, as_of, text, source)` (9), with the read `guidance(symbol)`
among 15.2's;
`override_add(symbol, tag, new, reason, evidence, lifetime, period?)` returning the override's
state and, when applied, the review with its bridge; `override_drop(override_id, reason)`;
`secondary_valuation(symbol, reason, evidence, drivers?, parts?, debt?, cash?)` (11);
`sensitivity(symbol, row_tag, row_values, col_tag, col_values)` (13.8); `derive(...)` (13.4);
`report_submit(...)` (13.1); `kill_criterion_add(symbol, text)`, `kill_criterion_set(id, state,
reason)`; `news_item_add(symbol, date, headline, source, text, kill_criterion_id?)`;
`refresh_start(kind, symbols?)` (the four kinds of the CLI), `refresh_cancel()`.

## 16. The web API

The routes the tools of 15 call and the page of 18 uses, under `/api`. Reads are `GET`; writes
are `POST` (create), `PATCH` (a state change) or `DELETE`, need the request header, and read the
identity headers of 7. New reads: `/companies/{symbol}/financials`, `/financial-tables`, `/estimates`,
`/price-history`, `/peers`, `/notes`, `/findings`, `/overrides`, `/reviews`, `/secondary`,
`/kill-criteria`, `/news-items`, `/ledger`, `/reports`; `/reports/{id}`,
`/reports/{id}/markdown`; `/inbox`; `/ledger`; `/review-log`; `/methodology/{section}`;
`/vendor/{kind}/{symbol}` for the pass-throughs. Writes: `POST /inbox`, `PATCH /inbox/{id}`
(claim, complete, decline), `POST /companies/{symbol}/notes`, `/findings`, `/overrides`,
`/secondary`, `/derivations`, `/reports`, `/kill-criteria`, `/news-items`; `DELETE
/overrides/{id}` with a reason body (the drop). The screen rows (`GET /api/screen`) gain
`reviewed`, `overrides`, `agentStance` and `covered` (18.1). The refusals follow
`watchlists_api`'s pattern: 400 on a bad value, 404 on a missing record, 409 on a state the write
cannot move from, each with the sentence the agent can act on.

## 17. Storage

Migration `005_agents.sql`, *my call* on the names: `ledger`; `work_items`; `notes`; `findings`;
`overrides`; `reviews` (the result as JSON, as `snapshots` stores it, with the bridge); `secondary_valuations`;
`derivations`; `reports` (the sections as JSON, the generated appendixes as JSON, the Markdown
rendered at read time); `judgments`; `kill_criteria`; `news_items`; `review_log`. Every table
carries `created_at`, `principal`, `actor` and `client` where a write made it. The builder writes
the DDL from sections 7 to 13; the plan lists the columns.

## 18. The page (plan 2)

### 18.1 The row

Two columns and a mark. `Reviewed` is the design system's own `reviewed` key, filled: the latest
review's value when it is on the company's latest snapshot (or a reprice of it) and has a value;
else, only where the route refused, the latest secondary valuation's value a share above zero
while it is current (11: the secondary stands in where neither the route nor the review values
the company; build rulings of plan 2's and plan 3's final reviews, 2026-11-08); else an em dash. `overrides` is the count
inside. `Stance` (key `agentStance`, a `// fairband:` patch beside the designation column, which
keeps its key) is the latest published report's word, coloured by the stance tokens, an em dash
without a report; it fades to `ink-faint` with the mark when the report's snapshot window has
expired, so a stale stance is not read as current (build ruling of plan 2, Task 1). A secondary
valuation whose value a share is at or below zero does not fill `Reviewed` (the record stays in
Details). Both are in the chooser and sortable; the Filters menu gains `STANCE` (the four
words) and the design system's `reviewedOnly` row, "Has a review". The chooser's default eight
do not change. *My call.*

**The levels follow the reviewed value (plan 3).** The founder, 2026-11-08: "The fairbands, trim
levels, buy level, all should be updated based on the updated agent valuation, its still using
the engine based levels." Where `Reviewed` is filled, the row's `fairValue`, `fairLow`,
`fairHigh`, `buyLevel`, `trimLevel`, `priceToValue` and `designation` are the record's that fills
it: the review's levels, or on a refused row the secondary valuation's; price ÷ value and its word
are computed at the latest snapshot's price on the effective policy's edges, as the research read
computes them, never read from the record's stored word at an older price. `mechanical` keeps the
engine's value; the engine's own levels stay on the snapshot and in Appendix A. The intermediates
(`impliedGrowth`, `expectedReturn`, `epv`, the multiples) stay the mechanical row's. A review that
refused fills nothing, and the row stays the engine's.

The coverage mark: `◆` after the ticker in the Ticker cell, in `prov-input`, present when the
company has a published report; its title "Report <date> by <actor>"; `ink-faint` when the
report's snapshot window has expired. The brand book's write glyph fits: a report is a write. It
is not a control; the row opens as it does today. A `// fairband:` patch: a row field `covered`
`{at, actor, expired}`. *My call* on the glyph; the founder asked for a mark beside the ticker.

### 18.2 The drawer's main view

In order, and nothing else:

1. The head as today: the ticker, the phase badge, the name.
2. The meter: `BandMeter`. Where the current review counts on the latest snapshot and has a
   value, the meter draws the review's levels and value, the head beside the price saying price ÷
   value and the value's name in one form ("0.82 × the reviewed value"), its caption the mechanical
   value in words ("mechanical $342") and nothing the head already says (plan 4; before it the
   caption repeated the designation sentence in a second form); without one,
   the mechanical band as today (plan 3; the `reviewedValue` second-marker patch of plan 2 is no
   longer drawn on a valued row and may stay in the bundle for the caller that passes it). On a row the route refused, the meter draws from the
   current review's levels and value when the review has one, else from the secondary valuation's
   when it counts on the latest snapshot (its head "× the secondary valuation", no caption; plan 4), with the refusal
   line kept under it; a refused row with neither keeps no meter (build rulings of plan 2, Task 2
   and the final review). A label on the tier above the track is set off the price marker: centred on its own
   position, moved only as far as keeps its near edge 8px off the marker, at any width (plan 4: on
   QCOM the marker's dot covered "$179.11"; the build's final review replaced a six-point
   threshold, which left the labels touching in the drawer, with the clamp).
3. The stance line, when a report exists: the word, then a `PrincipalChip` (agent, the actor,
   the report's date). Without a report, nothing.
4. The report's Summary section, rendered by `ReportReader` (section 1 only), then one button,
   `Open the report` (secondary), to the report page; without a report, neither. Then one button, `Request research`, on a
   company with a report as on one without (plan 4: the founder found none on a company with a
   report), which opens a small menu in the bundle's style with the mode (valuation review,
   full report) and a note line, and posts the item; it then reads `Requested · pending` (or
   `claimed by <actor>`) until the item is done. A refusal row shows its refusal sentence
   under the meter's place as today.
5. `Details ▾`, a disclosure button (not a menu), closed when the drawer opens; its state lasts
   for the page's life. *My call.*

### 18.3 Details

In order: the review (the `ValueBridge` when a review with a value exists; the review's refusal
when it refused; the secondary valuation with its parts, value and date); the overrides
(`OverrideRecord` each, read-only: no Drop button); the guidance on file (metric, period, the
range and the midpoint, the call's date, superseded or current, and whether an override cites
it); the judgments; the kill criteria; the news items; the notes, with the owner's `Add a note` field and
button; the findings; the company's ledger entries; then everything the drawer shows today in its
order: the validity window, the phase evidence, the route section, the inputs, the intermediates,
the flags, the estimates and the versions line.

### 18.4 The report page

A view at `#report/<symbol>` and `#report/<symbol>/<id>` for an earlier revision, in the
`CompanyReport` layout: the header (the ticker, the name, the phase badge, the one `figure-lg`:
the reviewed value where one exists, else the mechanical, with the price beside it), the
`BandMeter` (the review's band where the review counts and has a value, as the drawer draws it;
18.2), then `ReportReader` with the twelve sections, the references list, and Appendix A
and B. The reader renders each section's text as blocks (13.1, "The text's shape"): paragraphs,
bullet and numbered lists, tables with a header row, bold, the cites and their footnote marks
inline; a `// fairband:` patch in the bundle naming 13.1, the same renderer under the drawer's
Summary. The page's table toggle covers the charts' twins only; the agent's tables are text and
always show. Print keeps a table on one page. Above the reader: the mode, the date, the actor, the revision, `Download .md`, the page's
one table toggle, a line listing the other revisions, each by its number and its date and time
("revision 1, 8 Nov 2026, 07:24"; plan 4: two revisions on one day read the same by date alone),
then `Request research` with its menu and the open item's line, as the drawer has it (18.2, plan 4).
The reader's text is set at 16px on a 24px line, the column 72ch wide at that size (the founder,
2026-11-08: the text was too small to read at ease). A link back to the screen. A
print stylesheet: the reader part, the references and the appendixes, no header chrome.

**The charts.** The founder, 2026-11-07: charts for the price and the multiples and for the
financial performance and health section, in the design system's look. The brand book puts charts
on a company report and nowhere else, and `charts.md` and `CompanyReport.md` of the archive set
the rules the page follows: one measure per chart, two to a row as small multiples, one series hue
with `chart-context` for a reference, the diverging pair for a measure that crosses zero, columns
from zero, solid grid lines, nothing animated, text never in the series colour, every chart with a
table twin behind the page's one toggle, and a `BasisChip` on each chart's header. The charts sit
inside the reader, above the sentences of the section they belong to, on `surface-raised` panels:

| Section | Charts |
|---|---|
| 4, growth | `HistoryBars`: revenue; the operating margin; the EPS |
| 4, cash flow | `HistoryBars`: free cash flow; stock compensation over revenue |
| 4, solvency | `HistoryBars`: net debt over EBITDA; the interest coverage |
| 4, returns | `SpreadChart`: ROIC against the hurdle rate, the gap filled |
| 4, capital allocation | `HistoryBars`: buybacks and dividends; the share count |
| 4, quality | `HistoryBars`: Altman's Z″; Piotroski's F |
| 8, valuation | `SensitivityGrid`: the route's grid the report cites (13.8); the secondary's grid (11) |
| 9, price | `BandHistory`: the stored closes over the years on file, the band from the snapshots on file (it begins at the first snapshot's date), the past year's high and low marked and labelled |
| 9, multiples | `MultipleHistory`, twice: the trailing P/E and the forward P/E (13.7), each a line in `chart-1` with its average as a `chart-context` reference line labelled at its end and the current value labelled at the line's end; a loss year leaves a gap; a forward log of fewer than five readings is no chart but the newest reading as a figure with "logged since <date>; a reading is added at each price refresh", no line and no average (plan 4) |

Each chart reads the series the section cites: the six tables, the two multiples series, the
closes, the snapshots and the two grids, so the chart and the sentence under it never disagree.
`MultipleHistory` is a `// fairband:` patch in the bundle, in `BandHistory`'s marks and tokens
(a line, a reference line, the end label, the table twin); the four others are the bundle's own.
A cell with no value leaves a gap, never a zero. *My call* on the chart per part: two or three
each, and the table twin holds the rest.

### 18.5 The Inbox view

A sixth header view, `Inbox`, with `AppHeader`'s `count` set to the open items, pending and
claimed. The founder, 2026-11-07: "a work inbox page and a link in the header, showing a number
of pending work items"; the count is the open items since both states are work not yet done
(*my call*, open to pending only). The 2026-11-04 spec reserved the count for the inbox; six words
fit beside the mark at desktop width and wrap below 980px (the six overflowed between 840 and
965px, so the wrap point of the 2026-11-04 spec moves; the views' own line wraps below 450px). The
count is read by its own thirty-second call to `/api/inbox`, paused while the page is hidden and
read once when it is shown again, since every such read runs the expiry rule under a write lock
(build rulings of plan 2, Task 5). The view: a table of
items, newest first, with the symbol (opening the drawer as a watchlist row does), the mode, the
state word, the posted date and time and the principal, the claimant, the note, the report link when done,
named by its revision ("revision 2"; plan 4: two items on one day read the same by date alone), and
for the owner `Decline` with a reason line on a pending or claimed item. Reading the view runs
the expiry rule (8).

### 18.6 Watchlists

Each list gains `Request research` beside `Rename` and `Delete`: it posts a valuation review for
every company on the list with no open item and says how many it posted.

## 19. Policy v8 and v9, the method document and the Methodology page

Policy `fairband-policy-v8` adds, none a setting this round (*my call*; they become settings
when the founder asks): `override_ranges` (the table of 10.2), `override_primary_evidence_above_p90`
(true), `secondary_parts_max` (10), `secondary_years_min` (3), `secondary_years_max` (15),
`stance_words` (the four). Every v7 value is unchanged; v7 stays byte-identical under its hash.

Policy `fairband-policy-v9` (plan 1b) adds `earnings.cycle_gap` to `override_ranges` (−100 to
100 dollars a share, as the non-recurring gap), `earnings.ntm` (0 to 1,000 dollars a share, the
lower end excluded by the route's own positive-anchor rule) and `revenue.ntm` (0 to 10^15 dollars,
as the balance tags), and `secondary_driver_ranges` (11: a growth rate
−0.80 to 3.00, a margin −0.50 to 0.60, a tax rate 0 to 0.50, sales-to-capital 0.1 to 10). Every
v8 value is unchanged. The live snapshots, at v7 on 2026-11-07, are revalued once under v9 at
the live steps (22).

`docs/method.md` gains: section 14, "Reviews: overrides and the reviewed value" (10.2 to 10.5,
with the bridge's order and the JUDGMENT tag; plan 1b adds the cycle gap to 14.2 and 14.4, after
the non-recurring gap in the bridge's order, its line labelled "mid-cycle earnings"); section 15,
"The secondary valuation" (11; plan 1b adds the drivers form's arithmetic, the grid and
`fairband-secondary/2`, with worked numbers); section 16, "Reports: the number check" (13.2 and
13.3; plan 1b adds the twelve sections, the secondary rule, the sensitivity record and the
`multiple:` refs). The versions table gains rows: mechanical 0.9 unchanged, `fairband-review/1`,
`fairband-secondary/1` and, in plan 1b, `fairband-secondary/2`, with the dates. Section 13's
glossary gains override, review, finding, judgment, secondary valuation, work item, thesis,
cyclical.

The Methodology page gains a section, "Agents and reviews" (`agents`), in plain words: what an
override is and that the engine computes the reviewed value; the value bridge; the secondary
valuation as the standard DCF that stands in where the route refuses, and nowhere else (plan 3);
the mid-cycle basis for a cyclical; the stance is the agent's, weighed against the reviewed
value's levels; the report's rule that every number traces to a stored fact; where the records
are read, the screen's band and levels following the reviewed value (plan 3). No example figure until a real review
exists; then one, as 7.5 of the 2026-11-04 spec does.

## 20. Worked numbers for the tests

### 20.1 The secondary valuation

r 9%, g 3%; one part, FCFF 100 in year 1 growing 5% a year for 5 years (100, 105, 110.25,
115.7625, 121.550625); debt 200, cash 100, 100 diluted shares.

| Year | FCFF | PV |
|---|---|---|
| 1 | 100 | 91.7431 |
| 2 | 105 | 88.3764 |
| 3 | 110.25 | 85.1332 |
| 4 | 115.7625 | 82.0091 |
| 5 | 121.550625 | 78.9996 |

Σ PV 426.2614; terminal 121.550625 × 1.03 ÷ 0.06 = 2,086.6191, discounted 1,356.1592; firm
value 1,782.4206; equity 1,682.4206; value a share **16.8242**. With a second part, FCFF 20 flat
for 5 years and g 0: its Σ PV 77.7930, its terminal 20 ÷ 0.09 = 222.2222 discounted 144.4292,
part value 222.2222; two parts, value a share **19.0464**. Pinned to 1e-4. A g of 3.5% is
refused; a path of 2 years is refused; an 11th part is refused.

### 20.2 The bridge

On each golden fixture (`tests/fixtures/golden`: MGCO, MSCO, HGCO, DCCO, YGCO, SUCO) one
override per tag its route reads, at a value inside the range: the review's value equals
`value_company` with that input changed, to 1e-9 a share; the bridge has one line, whose delta
is the review's value less the golden's; with two overrides, the two deltas sum to the
difference to 1e-9 a share; SUCO with `phase` Young Growth is valued by the revenue-growth
route, its bridge starting at no mechanical value. The figures are pinned at build time from the
engine, with the override named beside each.

### 20.3 The number check

A fixture report on MGCO's golden with one of each failure, and a clean one that publishes:
a cite to `snapshot:<other>/value` (wrong snapshot); `$12.345` against a price (wrong unit,
rounding); `12.3x` against a percentage (wrong unit); `period: 2024` against a 2025 fact (wrong
period); `fact:MGCO/revenue/2031` (unresolved reference); "revenue grew 11.2%" in a plain part
(a number with no reference); `derived:999` (a derived figure the engine has not emitted); and
"three reasons", "FY2025", "the 10-K", which pass.

### 20.4 The secondary valuation's drivers form (plan 1b)

r = 0.09, ROIC_T = 0.12 (the terminal return of the moat class as reviewed), g = 0.02, t = 0.25,
s = 2.0, trailing revenue 1,000, N = 3, growth 10%, 8%, 5%, margin 20% in every year; debt 200,
cash 100, 50 diluted shares:

| t | revenue | EBIT | NOPAT | reinvestment | FCFF | PV |
|---|---|---|---|---|---|---|
| 1 | 1,100.00 | 220.00 | 165.00 | 50.00 | 115.00 | 105.504587 |
| 2 | 1,188.00 | 237.60 | 178.20 | 44.00 | 134.20 | 112.953455 |
| 3 | 1,247.40 | 249.48 | 187.11 | 29.70 | 157.41 | 121.549402 |

The sum of the present values is 340.007444. The terminal FCFF is 187.11 × 1.02 × (1 − 0.02 ÷
0.12) = 159.043500; the terminal value 159.043500 ÷ 0.07 = 2,272.05, discounted 1,754.439476.
Firm value 2,094.446920; equity 1,994.446920; value a share 39.888938. The grid's centre cell
is this value; its corner at r = 0.08 and g = 0.01 and the rest follow the same arithmetic. A
year whose revenue falls reinvests nothing: with growth −5% in year 3, reinvestment_3 = 0.

## 21. Tests the builder must write

- `store`: every table's insert and read; the ledger row on every write; the expiry rule's
  once-per-`valid_until`; the drop of a pending expiry item.
- `engine`: 20.2; the accessor returns the engine's reading without an override; a JUDGMENT
  input's provenance; the refusal line in the bridge; the period-tied drop on a moved data date
  and on a changed corrected value; the review repriced at a price refresh; the locked, unit,
  evidence, route and not-input refusals each by name; the "settings changed" refusal on an
  override and on a secondary valuation.
- `engine/secondary`: 20.1 and the three refusals; the balance figures read from the store and
  passed explicitly; the foreign-filer and no-shares refusals.
- `reports/tables`: the six tables on the golden fixtures, each cell's ref resolving; Z″ and F on
  a Mature Growth row; a repriced snapshot resolving as the cited one and a revalued one not.
- `reports`: 20.3; the appendixes generated from the records; the Markdown render; a review-mode
  report naming the full report it reuses, and one saying there is none.
- `web`: every route of 16, with the identity headers read and the owner default; the inbox's
  state moves and their 409s; the pass-through routes on the vendor double, stored and reused;
  the screen rows' four new keys; the report Markdown route.
- `mcp`: the adapter's tools against the app in process (the SDK's in-memory client): `identify`
  before a write; each tool's call maps to its route; the not-running sentence.
- `web` page tests: the drawer's main-view order pinned in `app.js`; Details' order; the report
  view's hash route; the Inbox view's count; the Watchlists action.
- `policy`: v8 loads; v7 byte-identical under its hash; the ranges read.
- `docs`: the method's new sections cite the policy names; the Methodology page's `agents`
  section exists and its live values resolve.
- Plan 1b: `engine/secondary` on 20.4, the reinvestment floor, each driver's range refusal, a
  list of the wrong length, the grid's nine cells and the cap at g_T; `engine/overrides` the
  cycle gap on both mature routes, its bridge line after the non-recurring gap and labelled
  "mid-cycle earnings"; the policy v9 file's hash and the v8 values unchanged; migration 006 on
  a 005 database with a plan 1 report (the judgments keep their decisions); the sensitivity
  record on a five-by-five grid, a tag the route does not read refused, the pair in force
  marked; the multiples log written at a price refresh and at a snapshot, the `pe_history`
  response served as points and statistics, the `multiple:` refs resolving and a `wrong unit`
  on one; the check's twelve and ten headings, the secondary rule's sentence, a judgment with
  `bull` refused as an unknown field; the guidance record's midpoint and step, a superseding
  record, an `earnings.ntm` override refused without a `guidance` evidence item and applied with
  one, its bridge line first after the phase, the `guidance:` refs; the transcript-dates
  pass-through; the render's footnote marks and the references list with
  no ref left in the main text, and the chart tables in the Markdown; the playbook's test on the
  thirteen steps and the twelve headings.

## 22. Acceptance and the readout

After plan 1b merges (plan 1's live steps were held for the 2026-11-07 rulings): the live
database is backed up and migrated (005 and 006), revalued once under policy v9, and the server
runs from main; `fairband mcp` is registered in Claude Code and the playbook installed. The first
live session waits for plan 2, so that the report is read on its page. Then the founder posts an
item for one company; one playbook run produces findings, judgments, at least one applied
override with a review and a bridge, a secondary valuation, a call section with its guidance
records, a published report, and the completed item; the ledger carries every write with the actor; the log has its first row; a draft with a
bare number was rejected on the way and the findings named it. The readout: the company, the
mechanical, reviewed and secondary values, the bridge, the stance, the number of findings and the
report's length.

After plan 2 merges: the row shows the reviewed value, the stance and the mark; the drawer opens
on the meter, the stance and the summary; the report page shows the whole report and downloads it;
`Request research` posts an item the agent then takes; a watchlist company past its window shows
in the Inbox; the Methodology page's section reads. The readout: the first three companies
reviewed, each with its mechanical, reviewed and secondary values, and its stance.

At the defaults, every mechanical figure on every row is bit for bit refresh 16's; the readout
checks it over the whole universe.

The readout was taken on 2026-11-09 over five runs, QCOM twice, GOOG, AMZN and META; the
decision log's row of that date holds it, and B-9 closed with it.

## 23. Left to the builder

- The accessor's shape in `Context` and the routes, and how the Start-up route reads a phase
  override (the row leaves the Start-up branch before its route).
- The thread shape of the pass-through calls on the server (a small pool beside the worker, or
  a job on the worker that is not a refresh) within 15.3's rules; the exact FMP routes.
- The number tokenizer's details within 13.3, settled on the fixture of 20.3.
- The DDL of 17 from sections 7 to 13; the JSON shapes of the records on the API.
- The MCP tool descriptions' sentences; the `SKILL.md` text within section 14.
- The report Markdown's layout; the print stylesheet.
- The `BandMeter` second-marker patch; the `ScreenTable` patches for `agentStance` and
  `covered`; the Inbox view's columns; the hash route for the report page.
- Where the review is recomputed in `run.py`'s value stage, and how a price refresh finds the
  latest review beside the latest snapshot.
- The rows of each financial table within design.md 9.3's list, and which stored line or engine
  reading each reads.

## 24. Order of work

Plan 1, the agent's side (merged 2026-11-07, main e0fd4e8):

1. Policy v8; `docs/method.md` 14 to 16 and the versions row; migration 005; identity and the
   ledger; the request and identity headers on the app.
2. The inbox, notes, findings, kill criteria and news items: store, API, the expiry rule.
3. Overrides and the review in the engine: the accessor, the JUDGMENT tag, the rules, the
   bridge; the review's storage; following the snapshots in `run.py` and `run_price.py`; the
   log.
4. The secondary valuation and `derive`.
5. Reports and judgments: the references, the check, the appendixes, the Markdown export; the
   financials, estimates, price-history and peers reads.
6. The pass-through routes.
7. The MCP server and the playbook; the README's host registrations.

Plan 1b, the report (the founder's rulings of 2026-11-07 on reading the playbook):

1. Policy v9 and migration 006: the cycle gap in the engine and the bridge; the judgments without
   bull and bear; the secondary's drivers, projection and grid; `multiples_log`; the
   sensitivities.
2. The secondary valuation's drivers form and grid, `fairband-secondary/2`; the secondary rule in
   the check; `docs/method.md` 15.
3. The sensitivity tool and record.
4. The multiples history: the `pe_history` and `dcf` pass-throughs, the log at every price
   refresh and snapshot, the read and the `multiple:` refs.
4b. The guidance record and its tool, the two NTM anchor tags with the `guidance` evidence
   rule, the `guidance:` refs, the `transcript_dates` pass-through.
5. The report's twelve sections in the check, the references list in the render and the export,
   the chart tables in the export; `docs/method.md` 16; the Methodology section.
6. The playbook: the thirteen steps, the call, the cycle, the debate and the thesis, the
   template and the references; the MCP tools added.
7. Merge; the live steps (22) up to the revalue under v9 and the MCP registration. The first
   live session waits for plan 2.

Plan 2, the page:

1. The screen rows' keys; the two columns, the filter rows and the mark.
2. The drawer's main view and Details; the request menu.
3. The report page with the references and the appendixes, the download and the print
   stylesheet.
4. The charts: the bundle's four on their sections, the `MultipleHistory` patch, the table
   toggle, the series reads.
5. The Inbox view with the header count, and the watchlist action.
6. The Methodology page's section.
7. Merge; the first live session; the readout (22).

Plan 3, the first live session's rulings (the founder, 2026-11-08, on the QCOM report;
`docs/superpowers/plans/2026-11-08-first-session-fixes.md`):

1. The secondary valuation as the fallback only: the route's refusal on a valued snapshot, the
   check's rule, Appendix A's reason, `docs/method.md` 15 and 16, the Methodology section.
2. The playbook: steps 10 to 12, the secondary section, the template's Summary and Valuation,
   the tools' notes.
3. The row's levels and designation from the reviewed value; the two meters; the Methodology
   section's reading paragraph.
4. The reader's blocks: paragraphs, lists, tables and bold from the parts; the check's marks.
5. Merge; restart; the backlog rows for the agent's four gaps; the founder's second run on QCOM.

## 25. Sources

| Rule | Source |
|---|---|
| An override changes one input, with reason, evidence and a lifetime; locked inputs; extra evidence above the base-rate 90th percentile | design.md 7.3 (Decided); the brand book, "Values and provenance" |
| The bridge in the method's step order, deltas that sum | design.md 7.4 (Decided); `ValueBridge` guideline |
| The engine owns every number; `ƒ` and `◆` never on one chip; the model identifier as it arrived | the brand book, three rules; `BasisChip`, `PrincipalChip` |
| The report's sections, rules and number check; the two modes | design.md 9.2, 9.3, 9.4, 7.5; `ReportReader` guideline (the six failures) |
| The roles and the flow | design.md 7.1, 7.2, from TradingAgents (Apache-2.0) |
| The validity window ends the whole result | design.md 8 |
| The inbox's two ways in and its states | B-58, founder 2026-11-04 |
| The DCF on an explicit path with a terminal at g ≤ g_T, r the policy's | Damodaran, *Investment Valuation*, the FCFF model; method 4.1 (r, g_T) |
| The log of mechanical against reviewed values as evidence | design.md 7.3, logging; the literature report (no study tests the method by stage) |
| MCP over stdio, started by the host; tools with one-sentence descriptions | the Model Context Protocol specification, the Python SDK |

## Decision log

| Date | Decision |
|---|---|
| 2026-11-06 | Tier 2 moves ahead of B-28 and B-87. Founder: "I want to work on the MCP server". |
| 2026-11-06 | The MCP server is never read-only: the writes are B-49 to B-59 and every one arrives through it. Claude's "read-only" label of the first slice was wrong and withdrawn. |
| 2026-11-06 | The first session: the agent sees the inbox, takes a research request, runs the playbook with the MCP interface for data, publishes the report; the user requests research from the screen or a watchlist. Founder, open to a smoother way; Claude: the item carries everything, no new channel. |
| 2026-11-06 | The row: the reviewed value column filled and a mark beside the ticker that an agent covered the company (founder); the stance column filled with the agent's word (Claude, from the 2026-11-03 decision that the stance is the agent's). |
| 2026-11-06 | The drawer: the valuation and the report in the main view; the phase, the bridge, the window and every mechanical detail behind one Details control. Founder: "the user's main concern is to read the report and see the valuation, not to audit the agent". |
| 2026-11-06 | One spec for the whole of Tier 2, two plans: the agent's side, then the page. Claude proposed; founder: "yes". |
| 2026-11-06 | The number is rigid and the stance is free: the reviewed value is the engine's figure under the agent's inputs; the override set is wide and includes the phase; a refused row gets no reviewed value from the route. Claude's recommendation; the founder accepted and reframed the escape. |
| 2026-11-06 | The secondary valuation is a second view that complements the engine and the fallback where no phase or route fits, not an "own-method" escape. Founder. Built as one tool on an explicit cash-flow path with parts (Claude's shape). |
| 2026-11-06 | No owner write on an override: the owner neither adds nor drops one over the API or on the page, until the founder commits to the whole user override function; `override_drop` stays as the agent's tool (3, 10.3, 18.3). Founder, on reading plan 1. |
| 2026-11-06 | Build rulings, plan 1 (later tasks): no refresh touches a secondary valuation, the page reads its price ÷ value against the latest quote (11); the reads hand out `estimate:`, `close:` and `peer:` refs, which the resolver reads (13.2); the pass-throughs run on the sync-route thread, four in flight, a ten-second wait then 503 busy (15.3); the cite rules of method 16.3 (scale words at the cite's precision with two significant figures, unsigned outflows by their size, `%` on a ratio, prices to cents); `news_items` carries the report's id. Claude, during the build. |
| 2026-11-06 | Build rulings, plan 1: the consensus-step overrides do not apply on Mature Stable, whose value reads no step (10.2); a mid-bridge refusal does not end the review, the last line decides (10.4); the JUDGMENT entry names its principal and actor in its source string (10.4); the ledger kind `drop` for a dropped expiry item (7). Claude, during the build. |
| 2026-11-06 | Builder check done. Four questions, all settled by Claude: the secondary valuation reads debt and cash from the newest balance sheet on file or takes them with evidence, stores the figures used, and is refused on a foreign filer (11); an override, a recompute and a secondary are refused "settings changed: run a revalue" when the effective policy is not the latest snapshot's, and both records cite their versions and hash (10.3); the server computes the report's six financial tables with a ref per cell, `financials` carries refs, and `derive` takes a list (13.5, 13.4); a reprice of the cited snapshot counts as the cited one, a revalue or full refresh does not (13.2). Two notes taken in: the `fairband` console script is added (14); `refused-range` is the component's `refused-unit`, so `refused-route` is the one state patch (10.1). Nothing for the founder. |
| 2026-11-06 | The MCP server talks to the web API, holds no database connection and no key (6); identity by `identify` and headers (7); no claim timeout and no stale conflict (8, 10.3); the override ranges and the bridge order (10.2, 10.4); the four stance words (13.1); the five derivations (13.4); the four pass-throughs (15.3); the `◆` coverage mark, the sixth header view, the Details disclosure (18); policy v8's values not settings (19). Claude's calls, open to the founder. |
| 2026-11-07 | On reading the playbook, the founder's six rulings: (1) cites and overrides are footnotes, never in the main text (13.1); (2) the secondary valuation is made on every report by a standard DCF and is the fallback when the route refuses, at the policy's hurdle rate ("keep the policy's hurdle rate"), FMP's template the reference (11); (3) the bull and bear views argue the business and its outlook, never the phase or the overrides, and a thesis tied to the debate leads to the stance; Claude: a thesis for every stance (13.1, sections 5 and 6); (4) the agent finds a cyclical business and values it at mid-cycle, since the engine overvalues MU, AVGO and the like at a peak (14 step 6; `earnings.cycle_gap`, 10.2); (5) key judgments are the record of the decisions and the last section (12); (6) section 8 shows the price against its year's range and the P/E and forward P/E against their history, as line charts with average lines (13.7, 18.4). |
| 2026-11-07 | Charts for the financial performance and health section too, in the design system's look (18.4); a work inbox page and a header link with the count of open items (18.5). Founder. Claude's calls: the charts per part, the `MultipleHistory` patch, the forward P/E from Fairband's own log since no vendor keeps one, the count as pending plus claimed. |
| 2026-11-07 | Claude's calls in the amendment: the drivers form beside the parts form, the reinvestment floor and the terminal reinvestment through the policy's terminal return, the three-by-three grid on the secondary record, FMP's DCF as a read and not its custom template; the `sensitivity` tool (13.8); `earnings.cycle_gap` as a tag of its own under policy v9; the life-cycle phase section folded into Valuation; a valuation review keeps the debate and the thesis (nine sections); migration 006 drops `bull` and `bear`; plan 1b (the report) before plan 2 (the page); the first live session after plan 2. The engine's own peak-margin flag is a backlog item, not this round. |
| 2026-11-07 | The last earnings call is a section of its own (13.1, section 5), in both modes, since "prices crash or increase based on the earnings call" and "the thesis is formulated, confirmed, or broken in the last earnings call". Its shape, Claude's, accepted: the verdict first; the quarter against expectations; the story management is telling, tested claim by claim (claim, evidence, driver, test; possible, plausible, probable; the drift; what was not said); the guidance table; the positives and the negatives; the questions and answers; what the thesis takes, ending on the gap between the price's move and the value's. The thesis takes a position on each claim of the call: "the company narrative should be the basis for the thesis, whether its accepted or rejected and everything in between". Founder. |
| 2026-11-07 | Guidance: a stored record with the midpoint and the step computed by the server (9); it reaches the reviewed value through an override citing the record, never the mechanical value. The rules, founder: "only use guidance as overrides if its very clear, any ambiguity etc. then the fall back is the consensus … no need for a fixed words table"; "usage of guidance is on a best effort basis, not required"; a next-quarter figure was to enter when it completes the fiscal year (Claude's rule, agreed); the build found the completed year behind every engine input, so it feeds no override and is read against the consensus in the call section (Task 8's ruling). Two anchor tags, `earnings.ntm` and `revenue.ntm`, guidance-backed only, since the NTM anchors were locked (10.2); Claude's call, open to the founder. |
| 2026-11-07 | The transcript probe: one FMP call for MSFT (five keys, the call as plain speaker-labelled text, the `year` the fiscal year) and the dates endpoint over 100 random companies of the live universe: 95 with a transcript inside 120 days, five companies that hold no call. The dates endpoint becomes the `transcript_dates` pass-through (15.3). |
| 2026-11-07 | Build rulings, plan 1b (Claude, during the build, each in place above): the cycle gap comes off the anchor earnings only, after the margin normalization on Mature Stable (10.2); a secondary valuation's terminal releases no capital at or below zero growth, the terminal growth runs from −100% to g_T, the parts grid's rows are shifts (11); the drivers form's trailing revenue from the statements and ROIC_T from the ten-year aggregate (11); grid and sensitivity refs count from 1; the sensitivity reading is an agent's write and a reading under a moved review is `wrong snapshot` (13.8); the P/E history on an unpaced GuruFocus client under `gf`, an unreadable or all-zero series never reused, a failure logs no multiples and a day's logged multiple is never blanked (13.7, 15.3); a guidance record supersedes by metric, period and basis in the order of the calls, a superseded record backs nothing, an NTM anchor needs a gaap fiscal-year record of its metric and drops once the guided year is behind the base year, a next-quarter figure feeds no override (9); the secondary rule spares a foreign filer and a row with no diluted share count (11, 13.3); the judgments refused 400 on `bull`/`bear`; the Markdown keeps GFM footnotes. |
| 2026-11-08 | Build rulings, plan 2 (Claude, during the build, each in place above): B-111's one consensus row per fiscal period by the closeness of the period ends, a row ending within a week after the trailing period end skipped as the reported quarter's duplicate (Task 0; method 2, 5.2, 5.3, 5a.2); the Stance column as the agent's word (the component's derived stance unused), the stance chip fading with the mark, a non-positive secondary not filling Reviewed, the rows' records read in bulk (Task 1); the drawer's Summary with the full report's footnote numbers, the secondary's parts in Details, the secondary's band on a refused row, one request state per view (Task 2); the `report` panel outside the header's views, `ReportReader.footnotes`, one `figure-lg` on the page, the secondary's headline with basis `reviewed` and the caption naming the tool, print without the head figures (Task 3); the chart titles the export's words, `HistoryBars.inverse`, a one-quarter band shown, `hurdleLabel`, the band table in the export (Task 4); the count as pending plus claimed on a thirty-second read, the Inbox table following the header's read, a declined expiry item holding for its window (Task 5); the Methodology section following the method where the playbook's wording differs (Task 6). |
| 2026-11-08 | The first live session (QCOM, report 1, stance hold; the founder's three rulings): (1) no DCF where the route values the company: the secondary valuation is the fallback only, refused on a valued snapshot, required on a refused one, and no DCF weighs on the stance (11, 13.3, 14; reverses 2026-11-07's "always done"); (2) the report's text renders as the agent wrote it: paragraphs, lists, tables and bold from the parts, in the reader and under the drawer's Summary (13.1, 18.4); (3) the row's band, buy and trim levels, price ÷ value and designation follow the reviewed value, the engine's value kept in the Mechanical column, and the meters draw the review's band (18.1, 18.2, 18.4). Claude's calls: FMP's `dcf` figure read only on a refused row; the designation at the latest price on the effective edges; the second-marker patch left in the bundle. |
| 2026-11-08 | Build rulings, plan 3 (Claude, during the build): an older secondary valuation on a company the route or the review values is linked to a new report only when the report cites it, so Appendix A carries no uncited DCF (Task 1); the fallback is for a company neither the route nor the review values, so a review that routes a refused row also bars the DCF (the final review); a review that refuses on a valued snapshot is the agent's to fix, the mechanical value stands meanwhile and no secondary is made, and the values are read in order, the reviewed value, else the snapshot's, else on a refused row the secondary's (Task 2); the drawer's level list under the meter follows the review, the Clean filter and the group view read the mechanical value, the designation at the latest price on the effective edges (Task 3); a table spans the reader's width, one margin per block, headers in the agent's case, a plain line after a list item starts a paragraph, a number alone on its line stays a quantity (Task 4). |
| 2026-11-08 | The second live session (QCOM, report 2, stance hold, no secondary valuation since the route values the company; the founder's page feedback): `Request research` on a company with a report, under `Open the report` and on the report page (18.2, 18.4); a forward P/E log of fewer than five readings shown as a figure with its sentence, no line and no average (13.7, 18.4); the reader's text at 16px on a 24px line (18.4); the note's form, the request in the requester's own words on one line (8); the meter's head saying price ÷ value and the value's name in one form, its caption only the mechanical value, a level label anchored off the price marker (18.2); revisions and Inbox items named by number and by date and time (18.4, 18.5). The founder's ruling: an item posted over MCP for a chat request keeps origin `agent` (B-125). |
| 2026-11-09 | The GOOG session (a full report, in progress): the agent read the stored price, since the playbook refreshed only an expired company (B-126; 14 step 3: a scoped refresh at the start of every item's step 3), and wrote the method's terms as if the reader knew them ("The belief is 5.3%"; B-134; 13.1 "The words", 14 step 12 and the rules: the plain phrase in the text, the term once in brackets in section 8 only, Fairband's parts never named, the report read once as a reader who has never seen Fairband before it is submitted). The founder: the repository is to be open-sourced. A words warning at publish deferred as B-135 by his ruling, a warning never a refusal, and only if the next two reports still carry the terms. Plan 5. |
| 2026-11-09 | The spec 22 readout: five runs of the playbook by claude-opus-5-5, every report a full report with the stance hold, each with its findings, its judgments, an applied override with a review and a bridge, a call section with guidance records, a published report and a completed work item (the ledger: 5 claims, 5 reports, 5 completions, 7 overrides and one dropped, 8 sensitivities, 15 guidance records, 20 judgments, 20 kill criteria, 175 findings, 205 derivations, 32 news items). QCOM report 1 (8 Nov, snapshot 25400, $173.19 of 4 Nov): mechanical $342.38, reviewed $235.62 (step 3 28.2% to 20.1%, −$53.0; the non-recurring gap −$0.03 to $5.32, −$53.7), secondary DCF $156.22, price ÷ value 0.74, 38 findings, about 5,400 words. QCOM report 2 (8 Nov, the same snapshot): reviewed $210.72 (step 3 to 14.8%, −$83.6; the gap, −$48.0), no secondary valuation since the route values the company (the 2026-11-08 ruling), 0.82, 49 findings, about 6,400 words. GOOG report 3 (9 Nov, snapshot 24859, $287.30 of 4 Nov, the stored price; B-126): mechanical $404.28, reviewed $339.71 (runway return 47.2% to 21.4%, −$64.6), 0.85, 47 findings, about 5,500 words. AMZN report 4 (9 Nov, snapshot 25830, $259.30 of 6 Nov after plan 5's scoped refresh): mechanical $288.84, reviewed $254.01 (step 2 21.9% to 35.3%, +$31.8; step 3 34.0% to 23.8%, −$66.6), 1.02, 43 findings, about 5,200 words. META report 5 (9 Nov, snapshot 25831, $610.15 of 6 Nov, the refresh id matched): mechanical $751.01, reviewed $681.91 (runway return 31.3% to 21.0%, −$69.1), 0.89, 36 findings, about 4,800 words. Reports 2 to 5 passed the check at the first submission; a rejected draft is no write, so the rejection path has no live record. The mechanical figures at the defaults: refresh 17 (policy v9) matched refresh 16 bit for bit; refresh 18 changed 18 rows under B-111's one consensus row per period (plan 2). The runs' gaps are B-115 to B-118, B-129 to B-133 and B-139 to B-144; the next engine round decides B-129, B-130, B-133, B-139, B-140 and B-143 (due before META's split of late January 2027). B-9 closed. |
| 2026-11-11 | The cyclical recipe (the founder's ruling on reading ASML's report 15, where the agent asked which of two recipes sets `earnings.cycle_gap`; five semiconductor reports had used two: the trailing operating margin against the middle year's on NVDA and AVGO, the margin inside the NTM EPS against the middle year's net margin on LRCX and ASML; MU kept its peak years and dropped step 3). One formula: full gap = NTM EPS − NTM EPS ÷ (NTM net margin ÷ mid-cycle net margin), the NTM net margin `ntm_net_income` over the NTM window's consensus revenue and the mid-cycle one the middle of the growth table's five net margins, since the cut is measured on the earnings it comes off; the trailing form leaves in the margin rise the analysts forecast (ASML: 34.1% trailing, 38.4% inside the NTM EPS). The full gap by default; half only where a filing or a transcript shows a lasting cause for part of the rise; never less than half. The value is linear in the anchor's EPS, so half the gap is the even mix of the two scenarios' values, with no engine change. The sensitivity grid shows nil, half and the full gap. The cut lowers the order-backed years too (about 2% of ASML's value) and the report says so; no step-3 drop on a business that still grows, where every later year would grow at the belief (method 5.5). Sources: Damodaran, "Ups and Downs: Valuing Cyclical and Commodity Companies" (2009): the relative average, an average margin applied to current revenue, over a period long enough to cover a cycle; "incomplete normalization"; and "adaptive growth", the cycle for the short term and normal figures after. Koller, Goedhart and Wessels, *Valuation*, 8th ed., ch. 42 "Cyclical Companies": consensus forecasts ignore the cycle; two scenarios, the normal cycle on the long-term trend line and a new trend line, weighted by their economic rationale; share prices sit near a 50-50 mix and anchor on current earnings. Mauboussin and Callahan, the Base Rate Book (2016): operating margins persist, a five-year correlation of 0.72 for all firms and 0.62 in information technology, measured against the sector. ASML at $1,507.85: $2,140 with no cut, $1,864 at half, $1,587 at the full gap (report 15), $1,450 on the ten-year median net margin of 26.0%; hold with any cut. A check on a second basis: ten years of net income lie on a line of 22.8% a year, which gives about €14.9 billion for the next twelve months, against €16.2 billion after the report's cut and €21.8 billion in the consensus. Report 15 stands; NVDA's and AVGO's overrides are re-made on the formula at their re-reads. In the playbook: "The cycle gap's figure" (SKILL.md) and section 8's detail (the template). Not built: the ten-year median for the agent (B-164) and a later start for the cut (B-165). |
| 2026-11-11 | The founder's ruling on amortization of acquired intangibles (the TTMI agent's feedback, report 18, its gap 5: the analysts' EPS leaves this amortization out, by the agent's note $12.1 million for the fourth quarter, and no input corrects the anchor without a GAAP guidance record). Not charged, and no input is built for it: on Mature Growth the anchor stays before this amortization. The reason: invested capital keeps the goodwill and the intangibles (method 4.4), so the cost of the acquisitions is in the return the growth is charged at; to take the amortization off the earnings too would count that cost twice. Source: Koller, Goedhart and Wessels, *Valuation*, the reorganized statements: operating profit before the amortization of acquired intangibles (EBITA), invested capital with goodwill and acquired intangibles. Two limits, accepted: the engine's intangibles are net of amortization where the book adds the cumulative amortization back, so the return reads a little high; and Mature Stable values GAAP trailing earnings, which carry the amortization. In the playbook: the `consensus-basis-unknown` entry (SKILL.md), which also tells the agent to state the size in section 8 and not to report it as a gap. The same review of that feedback: the cycle formula stands, the half gap being the answer to a change of level (TTMI is a case on B-164); `implied_growth` at a runway return equal to the hurdle rate is null or no measure by design (method 5.8), and the report template now says what section 8 writes there; FMP's segment and quarter errors stay with the agent, who reads the filing through `filing_report`. B-145 stays open for a non-recurring gain the consensus carries. |
| 2026-11-17 | The report page draws no link back to the screen (18.4 gave it one), and under the header neither the last refresh's line nor Details ▾, unless that run did not end done: the founder's rulings on his look at the live company page ("why do we have a back to the screen link? we already have the screen link in the header"), recorded in the decision log of `2026-11-16-company-page-design.md`. The header's Screen view is the way back, and the header gains a finder that opens a company's page. |
| 2026-11-18 | The report page (18.4) is the company page's Research tab since `docs/superpowers/specs/2026-11-17-research-tab-design.md` (B-218), merged to main and live on 2026-11-18 (`bc18aad`): the report in a panel a section under the company's head and tabs, with the records on file beside its text, its references and its two appendixes closed until opened, and a Records view of the company's records; `#report/<symbol>` and `#report/<symbol>/<id>` open the tab on the same report. The text's shape, the cites, the references and the appendixes of 13.1 hold there. |
| 2026-11-22 | A list's `Request research` (18.6) is withdrawn: research is asked for one company at a time, from the drawer or the company page, on the watchlist page as on the screen (`docs/superpowers/specs/2026-11-22-watchlist-page-design.md`, 8). Founder: "we should not have a request research button for all companies in the watchlist". |
