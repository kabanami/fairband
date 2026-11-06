# Tier 2: the agents over MCP, overrides and the reviewed value, the secondary valuation, reports and the work inbox: design

Status: written 2026-11-06 from the founder's decisions of that evening, in a brainstorm that
started from the backlog. The founder moved Tier 2 ahead of B-28 and B-87, described the first
session (the inbox, the playbook, the MCP interface, the request from the screen or a watchlist),
chose the row and the drawer's shape, ruled that the agent's value is the engine's own figure under
the agent's inputs with the stance free, and added the secondary valuation as a second view and a
fallback. Items marked *my call* were settled by Claude while writing and can be overturned. The
decisions are in the log at the end. Builder check: see the status line at the end of the log.

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
reads the engine's reviewed value, values the company a second way when the route cannot, writes
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
- **The secondary valuation is a second view and a fallback.** A tool beside the engine takes an
  explicit cash-flow path from the agent and discounts it under the policy's rules, so a company
  no route fits still gets a figure that is a tool output, and a valued company can get a second
  view.
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
- Charts on the report page (`BandHistory`, `HistoryBars`, `SpreadChart`, `SensitivityGrid`):
  they need the history piece (B-68, B-87).
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
own writes: a review recomputed at a refresh, a period-tied override dropped, an expiry item
posted).

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
`judgment`, `kill-criterion`, `news-item`, `work-item`, `claim`, `complete`, `decline`,
`request`), `symbol`, the record it points to (table and id), what it rests on (the snapshot id
and, when one, the work item id) and one line of summary. The ledger is read over the API and
MCP, for a symbol or whole, newest first; the drawer's Details shows the company's entries.

## 8. The work inbox (B-58)

A work item: `symbol`, `mode` (`valuation review` or `full report`), `note` (the requester's
text, may be empty), `snapshot_id` at posting (none for a company without one), `origin`
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
  quarter, `ttm`). A finding is the only way a number from outside Fairband enters a report
  (13.3): the agent records it, then cites it. The check cannot prove a finding true; it proves
  it is recorded with its source.
- **A kill criterion** (B-55): `symbol`, `text` (a measurable event that would prove the view
  wrong), `state` (`open`, `triggered`, `retired`), the report that set it, the principal and
  time. `kill_criterion_set` moves the state with a reason. No automatic check: the playbook's
  review step reads the open ones.
- **A news item** (B-55): `symbol`, `date`, `headline`, `source` (a URL or a vendor response
  id), `text`, and the kill criterion it touches, if any.

All four are read over MCP and the API, and shown in the drawer's Details.

## 10. Overrides and the reviewed value (B-50, B-51, B-56)

### 10.1 What an override is

A change to one tagged input, with its reason, its evidence and its lifetime; design.md 7.3,
decided. The record: `symbol`, `tag` (10.2), `old` (the input as the engine read it on the
snapshot), `new`, `unit`, `reason`, `evidence` (one or more `{kind, ref, note}`; the kinds of a
finding's source plus `finding`, a finding id), `lifetime` (`lasting`, or `period-tied` with
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
| `growth.belief` | Mature Growth | % a year | −20% to 60% | above the sales class's `sales_p90_5y` needs primary evidence (10.3) |
| `path.hold` | High Growth, Young Growth | % a year | −20% to 300% | the held rate of years 4 to `high_growth_years`; above the cap of 5a.3 needs primary evidence |
| `path.step_2`, `path.step_3` | every valuing route | % | −80% to 300% | a consensus step; replaces a held or thin one too |
| `moat.class` | Mature Growth, Mature Stable, High Growth, Young Growth, Start-up | word | None, Narrow, Wide | moves the margin of safety, the runway and the terminal return together, as the class does today |
| `margin.target` | High Growth, Young Growth, Start-up | % | −50% to 60% | |
| `capital.sales_to_capital` | High Growth, Young Growth, Decline | multiple | 0.1 to 10 | |
| `return.runway` | Mature Growth, Mature Stable | % | 0% to 100% | the runway return of 4.6 |
| `earnings.nri_gap` | Mature Growth, Mature Stable | $ a share | −100 to 100 | the non-recurring gap of 6.2 and the anchor's basis |
| `decline.rate` | Decline | % a year | −50% to 0% | d of 6a.2 |
| `balance.debt`, `balance.cash` | High Growth, Young Growth, Decline, Start-up | $ | 0 or more | period-tied only: a correction of a vendor error |

Locked, refused `refused-locked`: r, g_T, the runway years, the fade years, the margin of
safety, the fair band, the trim multiple, the terminal return (it follows the moat), the
deciles and the growth word, and every reported figure (statements, prices, shares, estimates)
other than the two balance corrections. A tag not in the table is `refused-not-input`. The
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
order, then the reviewed value. The order is the method's step order: `phase`, `path.step_2`,
`path.step_3`, `path.hold`, `growth.belief`, `earnings.nri_gap`, `margin.target`,
`capital.sales_to_capital`, `return.runway`, `decline.rate`, `moat.class`, `balance.debt`,
`balance.cash`. Each line's delta is the value with this override and every earlier one applied,
less the value with the earlier ones only, so the deltas sum to reviewed less mechanical exactly.
A line whose step refuses ("value not positive under the reinvestment charge") shows the refusal
in place of a delta, and the review is a refusal with that reason; a mechanical refusal that an
override turns into a value (a Start-up reclassified) starts the bridge at "no mechanical value"
and the first valuing line carries the whole value as its delta. The review's levels read the
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

A second valuation beside the engine's routes: a tool that takes an explicit cash-flow path from
the agent and discounts it under the policy's rules. It serves two needs the founder named: a
second view on a valued company, and a fallback where no phase or route fits, or where the route
refuses.

`secondary_valuation(symbol, parts, reason, evidence)`. `parts` is one to `secondary_parts_max`
(10) parts, each `{name, fcff, terminal_growth, note}`: `fcff` the free cash flow to the firm in
dollars for years 1 to N, N from `secondary_years_min` (3) to `secondary_years_max` (15);
`terminal_growth` at most the policy's g_T, lower or negative allowed. One part is a DCF; several
are a sum of parts. The arithmetic, per part:

    PV_t = fcff_t ÷ (1 + r)^t, t = 1 … N
    terminal = fcff_N × (1 + g) ÷ (r − g), discounted by (1 + r)^N
    part value = Σ PV_t + the discounted terminal

with r the policy's required return, locked. Firm value is the sum over the parts; equity = firm
value − debt + cash; value a share = equity ÷ diluted shares; the levels by the moat class (as
reviewed); the designation on price ÷ value. Debt and cash are the newest annual balance sheet's
on file, read by the server at the call as assembly reads them for the growth and Decline routes
(an applied `balance.*` override counts), and the shares are the snapshot's diluted count; the
agent may pass `debt` and `cash` explicitly, each with evidence, where the balance sheet is wrong
or missing, and the record stores the three figures used with their source, so the value rebuilds.
A foreign filer is refused, "foreign filer: currency and share-unit handling not built yet"
(B-28), since a dollar path over local-currency debt would mislead; a row with no diluted share
count is refused. A `terminal_growth` above g_T, an N outside the range, or a part count above
the maximum is refused naming the rule. *My call* on the figures' source, from the builder check:
the mature routes store no debt or cash with their results, and the fallback serves refused rows
that store nothing. Evidence is required, as on an override. Why
cash flows and not revenue, margin and capital: the agent builds the path from its own research;
the tool keeps the discounting, the terminal and the equity bridge, which is what makes the number
a tool output.

Stored (17) with the parts, the per-year present values, the firm value, the equity, the value a
share, the levels, the reason and the evidence, the snapshot id, the principal and actor, and
`secondary_method` `fairband-secondary/1`. It is as of its snapshot: a price refresh moves its
designation only; it expires with the snapshot's window and stays in the history after a full
refresh writes new statements, shown with its date. The agent makes a new one at the next
review. *My call.* On the row and in the report it stands in where the route gives no value
(18.1); where both exist, the route's reviewed value leads and the secondary is the second view.

## 12. Key judgments (B-52)

A judgment: `judgment` (`phase`, `moat`, `belief`, `roic`, `target_margin`), `bull`, `bear`,
`decision`, and the override it produced, if one. Judgments come with a report submission (13.1)
and are stored with the report. Every report carries `phase`, `moat` and `belief` (`belief` reads
as the rate the route holds: the belief, the held rate, or the decline rate); `roic` and
`target_margin` where the route reads them. The report's section 8 shows them; the drawer's
Details lists the latest.

## 13. Reports and the number check (B-53, B-59)

### 13.1 A report

`report_submit(symbol, mode, stance, sections, judgments, kill_criteria, news_items,
work_item_id?)`. `mode` is `valuation review` or `full report`. `stance` is one of `buy`,
`hold`, `trim`, `avoid`: the three zone words of the brand book and one for a company the agent
would not hold at any price shown; *my call* on the four. `sections` are the ten of design.md
9.3, in order, each `{heading, parts}` where a part is a plain string or `{cite, ref, period?}`
(13.3); a valuation review omits sections 2 and 3 and names `reuses_full_report_of`, the full
report it reuses, or says there is none (design.md 7.5). The server generates Appendix A (every
input with its tag, source and dates; the overrides with reasons and evidence; the bridge; the
secondary parts; the checks that ran; the versions; the classifier's evidence) and Appendix B
(the glossary: the terms of `docs/method.md` 13 the report uses) from the stored records; the
agent writes neither.

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
| `secondary:<id>/value`, `/firm_value`, `/parts/<n>/pv/<t>` | the secondary valuation's |
| `fact:<symbol>/<line>/<fiscal_year or ttm>` | a stored statement line, normalized as the engine reads it |
| `table:<symbol>/<table>/<row>/<year>` | a cell of the financial tables (13.5) |
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

`GET /api/reports/{id}/markdown` renders the published report as Markdown: the ten sections with
cited numbers as plain text, then Appendix A as tables and Appendix B as a list, with a header
line naming the symbol, the mode, the date, the actor and the revision. The report page's
`Download .md` button fetches it; the page's print stylesheet serves save-as-PDF. No server-side
PDF unless the print result falls short.

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
subagents for the analysts and the debate; the skill does not require it):

1. `identify` with the model identifier you run as.
2. `inbox_list`; claim the item, or post one for a request made in chat and claim it.
3. Read the company: `company`, `financials`, `financial_tables`, `estimates`, `peers`,
   `price_history`, the latest `report`, `notes`, `findings`, `overrides`, `reviews`,
   `secondary`, `kill_criteria`, `policy`, and `methodology` for the route. Section 4 of the
   report is written from the tables' cells.
4. The Fundamentals Analyst: the business and the industry from the filings (the host's own
   tools), `transcript` and `segments` from Fairband; record a `finding` for every number from
   outside Fairband that the report will cite, with its source.
5. The News Analyst: `news` from Fairband and the web; candidate kill criteria; large price
   moves explained.
6. The Valuation Analyst: the engine's result, its inputs and intermediates, in plain words; the
   candidate judgments.
7. The debate: bull and bear on each judgment of section 12.
8. The Research Manager decides the judgments and writes the overrides, one input each with
   evidence; reads the review and the bridge. When the review is a refusal, or no route fits,
   `secondary_valuation`. `derive` for any ratio the report needs.
9. The stance, from the reviewed value against the levels and the research; the report's reasons
   carry it.
10. The report: the ten sections with every quantity cited; `report_submit`; on a rejection, fix
    each finding and submit again.
11. `inbox_complete`, or name the item in the submission.

Rules the skill states: never write a number you did not get from a tool; cite every quantity;
small counts in words; the register of design.md 9.2 (the answer first, short sentences, every
term explained, rounded numbers); no first person, Fairband has no voice; the reason on an
override is your own words and is kept verbatim.

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

Four FMP endpoints the engine does not read, fetched by the server with its key, stored as vendor
responses (so a report can cite `response:<id>/...`) and reused inside `reuse_hours`:
`transcript(symbol, year, quarter)` (the earnings call transcript), `news(symbol, limit?)` (stock
news), `segments(symbol)` (revenue by product and by region), `insider_trades(symbol)`. The exact
routes are the builder's to check against FMP's stable API at build time. The calls run on the
server through the refresh's FMP client and limiter, so the pace holds, on a small pool of their
own beside the worker; the request thread never calls a vendor itself and no answer carries a key.
*My call* on the four and on the thread shape, which the builder settles (23). GuruFocus
pass-throughs wait for B-71 and B-72.

### 15.4 Write tools

`identify(agent)`; `inbox_post(symbol, mode, note?)`, `inbox_claim(item_id?)`,
`inbox_complete(item_id, report_id)`, `inbox_decline(item_id, reason)`; `note_add(symbol, text,
override_id?)`; `finding_add(symbol, as_of, text, source, value?, unit?, period?)`;
`override_add(symbol, tag, new, reason, evidence, lifetime, period?)` returning the override's
state and, when applied, the review with its bridge; `override_drop(override_id, reason)`;
`secondary_valuation(...)` (11); `derive(...)` (13.4); `report_submit(...)` (13.1);
`kill_criterion_add(symbol, text)`, `kill_criterion_set(id, state, reason)`;
`news_item_add(symbol, date, headline, source, text, kill_criterion_id?)`; `refresh_start(kind,
symbols?)` (the four kinds of the CLI), `refresh_cancel()`.

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
review's value when it is on the company's latest snapshot and has a value; else the latest
secondary valuation's value while it is current (11); else an em dash. `overrides` is the count
inside. `Stance` (key `agentStance`, a `// fairband:` patch beside the designation column, which
keeps its key) is the latest published report's word, coloured by the stance tokens, an em dash
without a report. Both are in the chooser and sortable; the Filters menu gains `STANCE` (the four
words) and the design system's `reviewedOnly` row, "Has a review". The chooser's default eight
do not change. *My call.*

The coverage mark: `◆` after the ticker in the Ticker cell, in `prov-input`, present when the
company has a published report; its title "Report <date> by <actor>"; `ink-faint` when the
report's snapshot window has expired. The brand book's write glyph fits: a report is a write. It
is not a control; the row opens as it does today. A `// fairband:` patch: a row field `covered`
`{at, actor, expired}`. *My call* on the glyph; the founder asked for a mark beside the ticker.

### 18.2 The drawer's main view

In order, and nothing else:

1. The head as today: the ticker, the phase badge, the name.
2. The meter: `BandMeter` as today, with a second marker for the reviewed value when one exists,
   labelled by the word "reviewed" in the caption; a `// fairband:` patch (`reviewedValue`). The
   caption keeps the designation sentence.
3. The stance line, when a report exists: the word, then a `PrincipalChip` (agent, the actor,
   the report's date). Without a report, nothing.
4. The report's Summary section, rendered by `ReportReader` (section 1 only), then one button,
   `Open the report` (secondary), to the report page. Without a report: one button, `Request
   research`, which opens a small menu in the bundle's style with the mode (valuation review,
   full report) and a note line, and posts the item; it then reads `Requested · pending` (or
   `claimed by <actor>`) until the item is done. A refusal row shows its refusal sentence
   under the meter's place as today.
5. `Details ▾`, a disclosure button (not a menu), closed when the drawer opens; its state lasts
   for the page's life. *My call.*

### 18.3 Details

In order: the review (the `ValueBridge` when a review with a value exists; the review's refusal
when it refused; the secondary valuation with its parts, value and date); the overrides
(`OverrideRecord` each, read-only: no Drop button); the judgments; the kill criteria; the news items; the notes, with the owner's `Add a note` field and
button; the findings; the company's ledger entries; then everything the drawer shows today in its
order: the validity window, the phase evidence, the route section, the inputs, the intermediates,
the flags, the estimates and the versions line.

### 18.4 The report page

A view at `#report/<symbol>` and `#report/<symbol>/<id>` for an earlier revision, in the
`CompanyReport` layout without the charts: the header (the ticker, the name, the phase badge, the
one `figure-lg`: the reviewed value where one exists, else the mechanical, with the price beside
it), the `BandMeter`, then `ReportReader` with the ten sections and Appendix A and B. Above the
reader: the mode, the date, the actor, the revision, `Download .md`, and a line listing earlier
revisions by date. A link back to the screen. A print stylesheet: the reader part and the
appendixes, no header chrome.

### 18.5 The Inbox view

A sixth header view, `Inbox`, with `AppHeader`'s `count` set to the pending and claimed items.
*My call*: the 2026-11-04 spec reserved the count for the inbox; six words fit beside the mark at
desktop width and wrap below 840px as the five do. The view: a table of items, newest first, with
the symbol (opening the drawer as a watchlist row does), the mode, the state word, the posted date
and principal, the claimant, the note, the report link when done, and for the owner `Decline`
with a reason line on a pending or claimed item. Reading the view runs the expiry rule (8).

### 18.6 Watchlists

Each list gains `Request research` beside `Rename` and `Delete`: it posts a valuation review for
every company on the list with no open item and says how many it posted.

## 19. Policy v8, the method document and the Methodology page

Policy `fairband-policy-v8` adds, none a setting this round (*my call*; they become settings
when the founder asks): `override_ranges` (the table of 10.2), `override_primary_evidence_above_p90`
(true), `secondary_parts_max` (10), `secondary_years_min` (3), `secondary_years_max` (15),
`stance_words` (the four). Every v7 value is unchanged; v7 stays byte-identical under its hash.

`docs/method.md` gains: section 14, "Reviews: overrides and the reviewed value" (10.2 to 10.5,
with the bridge's order and the JUDGMENT tag); section 15, "The secondary valuation" (11, with
the worked numbers of 20.1); section 16, "Reports: the number check" (13.2 and 13.3). The
versions table gains a row: mechanical 0.9 unchanged, `fairband-review/1` and
`fairband-secondary/1` added, with the date. Section 13's glossary gains override, review,
finding, judgment, secondary valuation, work item.

The Methodology page gains a section, "Agents and reviews" (`agents`), in plain words: what an
override is and that the engine computes the reviewed value; the value bridge; the secondary
valuation as a second view and a fallback; the stance is the agent's; the report's rule that
every number traces to a stored fact; where the records are read. No example figure until a real
review exists; then one, as 7.5 of the 2026-11-04 spec does.

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

## 22. Acceptance and the readout

After plan 1 merges: the server runs from main; `fairband mcp` is registered in Claude Code and
the playbook installed; the founder posts an item for one company (over MCP or the API, the page's
button comes with plan 2); one playbook run produces findings, judgments, at least one applied
override with a review and a bridge, a published report, and the completed item; the ledger
carries every write with the actor; the log has its first row; a draft with a bare number was
rejected on the way and the findings named it. The readout: the company, the mechanical and
reviewed values, the bridge, the stance, the number of findings and the report's length.

After plan 2 merges: the row shows the reviewed value, the stance and the mark; the drawer opens
on the meter, the stance and the summary; the report page shows the whole report and downloads it;
`Request research` posts an item the agent then takes; a watchlist company past its window shows
in the Inbox; the Methodology page's section reads. The readout: the first three companies
reviewed, each with its mechanical and reviewed values, its secondary value if any, and its
stance.

At the defaults, every mechanical figure on every row is bit for bit refresh 16's; the readout
checks it over the whole universe.

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

Plan 1, the agent's side:

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
8. Merge; the first live session; the readout (22).

Plan 2, the page:

1. The screen rows' keys; the two columns, the filter rows and the mark.
2. The drawer's main view and Details; the request menu.
3. The report page, the download and the print stylesheet.
4. The Inbox view and the watchlist action.
5. The Methodology page's section.
6. Merge; the readout (22).

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
| 2026-11-06 | Builder check done. Four questions, all settled by Claude: the secondary valuation reads debt and cash from the newest balance sheet on file or takes them with evidence, stores the figures used, and is refused on a foreign filer (11); an override, a recompute and a secondary are refused "settings changed: run a revalue" when the effective policy is not the latest snapshot's, and both records cite their versions and hash (10.3); the server computes the report's six financial tables with a ref per cell, `financials` carries refs, and `derive` takes a list (13.5, 13.4); a reprice of the cited snapshot counts as the cited one, a revalue or full refresh does not (13.2). Two notes taken in: the `fairband` console script is added (14); `refused-range` is the component's `refused-unit`, so `refused-route` is the one state patch (10.1). Nothing for the founder. |
| 2026-11-06 | The MCP server talks to the web API, holds no database connection and no key (6); identity by `identify` and headers (7); no claim timeout and no stale conflict (8, 10.3); the override ranges and the bridge order (10.2, 10.4); the four stance words (13.1); the five derivations (13.4); the four pass-throughs (15.3); the `◆` coverage mark, the sixth header view, the Details disclosure (18); policy v8's values not settings (19). Claude's calls, open to the founder. |
