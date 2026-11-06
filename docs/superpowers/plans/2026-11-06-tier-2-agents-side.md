# Tier 2, plan 1, the agent's side: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An agent in Claude Code connects to Fairband over MCP, takes a work item from the inbox, reads the company, records findings, overrides inputs with evidence and reads the engine's reviewed value and bridge, values a company a second way where the route cannot, publishes a report whose every number traces to a stored value, and completes the item, with every write in the ledger under the model identifier it runs as.

**Architecture:** The web server keeps the database and the refresh worker; every new write is a web API route under `/api` that reads the principal from three headers; the MCP server (`fairband mcp`) is a stdio process that calls those routes and holds no connection and no key. The engine gains an `overrides` argument that each route reads through one accessor, and a `review` module that applies the overrides in a fixed order to build the bridge; the refresh follows each new snapshot with a review. A `reports` package resolves references, checks the numbers, computes the six financial tables and renders Markdown. A `secondary` engine module discounts an explicit cash-flow path. The playbook is a skill directory in the repository.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite; the `mcp` package (2.3.0 at the time of writing) for the MCP server; httpx for the adapter.

**Spec:** `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md` (sections 6 to 17, 19 to 24). The method as built is `docs/method.md`; the spec cites its sections.

## Global Constraints

- The constraints of every earlier plan: never print, log or commit a key; never commit vendor data; `docs/method.md` changes in the same commit as the engine; the same inputs give the same result bit for bit; every valuation constant lives in the policy file with a source line; one imperative sentence per commit with the `Co-Authored-By` line; `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q` before every commit.
- The mechanical method stays `fairband-mechanical/0.9`; this plan ends at `fairband-policy-v8`, `fairband-review/1` and `fairband-secondary/1`. v7 stays in the package byte-identical under its hash. At the defaults every mechanical figure on every golden and every row is bit for bit what 0.9 and v7 give (spec 2).
- Policy v8's values are not settings: `override_ranges`, `override_primary_evidence_above_p90` true, `secondary_parts_max` 10, `secondary_years_min` 3, `secondary_years_max` 15, `stance_words` buy, hold, trim, avoid (spec 19).
- A write names its principal: `owner` without the headers, `agent` with `X-Fairband-Principal: agent`, `X-Fairband-Actor: <model identifier>` and `X-Fairband-Client: <name>/<version>`; `system` for the engine's own writes (spec 7). Every write is a ledger row.
- The server's refusal words are the design system's: the override states `applied`, `refused-locked`, `refused-evidence`, `refused-unit`, `refused-not-input`, `refused-route`, `dropped`; the report failures `unresolved reference`, `wrong unit`, `wrong period`, `wrong snapshot`, `a number with no reference`, `a derived figure the engine has not emitted` (spec 10.1, 13.3).
- An override, a drop, a recompute and a secondary valuation are refused `409` with `settings changed: run a revalue` (or `policy changed`, `method changed`) when the effective policy is not the latest snapshot's (spec 10.3).
- A refusal is a result or an answer with a reason, never an exception; the API's refusals are 400 (a bad value), 404 (a missing record), 409 (a state the write cannot move from), each with the sentence the agent can act on (spec 16).
- The brand book's words in every sentence the server emits: override, review, snapshot, finding, judgment, note, news item, report, work item; the model identifier as it arrived.
- Tolerances: 1e-9 a share on the bridge, 1e-4 on the secondary's worked numbers (spec 20).

## Review Focus

1. A `phase` override to Young Growth on a Start-up row followed by a `margin.target` override: the route check reads the route after the phase override, so the margin override is applied, not `refused-route` (Task 3's `test_the_route_check_reads_the_overridden_phase`).
2. A period-tied `balance.cash` override whose line is missing on the new snapshot (the engine's reading is `None`): the override drops with the reason "the input the override corrected changed", it does not raise (Task 4's `test_a_period_tied_override_drops_when_its_line_vanishes`).
3. A company on two watchlists past its window: one expiry item, not two; removing it from one list while it stays on the other leaves the pending item (Task 2's `test_an_expired_company_on_two_lists_posts_one_item`).
4. A cite written `$1,234.50`, `−3.2%` (the Unicode minus) or `(12.3%)`: the parser reads the thousands separator and both minus forms, so a correct figure is not rejected `wrong unit` (Task 7's `test_the_cite_parser_reads_separators_and_minus_signs`).
5. A secondary path whose equity is at or below zero: the value a share is stored as computed, the levels are `None` and the designation `None`, and the row would show the figure, not a refusal (Task 5's `test_a_negative_equity_is_stored_with_no_levels`).

---

### Task 1: Policy v8, the JUDGMENT tag, migration 005 and the ledger

**Files:**
- Create: `src/fairband/policy/fairband-policy-v8.toml` (a copy of v7 with the six values and a header line for v8)
- Create: `src/fairband/store/migrations/005_agents.sql`
- Create: `src/fairband/store/ledger.py`
- Modify: `src/fairband/policy/__init__.py:28` (`_POLICY_FILE`), the `Policy` fields and `load_policy`'s reads
- Modify: `src/fairband/engine/types.py:23-24` (`Tag`, `Kind`)
- Modify: `docs/method.md` sections 4.1 (the six rows, Setting "no"), 11 (the row for `fairband-review/1` and `fairband-secondary/1`, mechanical 0.9 unchanged), 13 (override, review, finding, judgment, secondary valuation, work item)
- Test: `tests/policy/test_policy.py`, `tests/store/test_db.py`, `tests/store/test_ledger.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `Policy.override_ranges: dict[str, tuple[float, float]]` (the numeric tags of spec 10.2: `growth.belief` (−0.20, 0.60), `path.hold` (−0.20, 3.00), `path.step_2` and `path.step_3` (−0.80, 3.00), `margin.target` (−0.50, 0.60), `capital.sales_to_capital` (0.1, 10.0), `return.runway` (0.0, 1.0), `earnings.nri_gap` (−100.0, 100.0), `decline.rate` (−0.50, 0.0), `balance.debt` and `balance.cash` (0.0, 1e15)); `Policy.override_primary_evidence_above_p90: bool`; `Policy.secondary_parts_max: int`; `Policy.secondary_years_min: int`; `Policy.secondary_years_max: int`; `Policy.stance_words: tuple[str, ...]`; `policy.version == "fairband-policy-v8"`.
- Produces: `Tag = Literal["DATA", "RULE", "JUDGMENT"]`, `Kind = Literal["observed", "estimate", "rule", "judgment"]`.
- Produces, in `fairband.store.ledger`: `Principal = Literal["owner", "agent", "system"]`; `Writer(principal: Principal, actor: str | None, client: str | None)` (frozen dataclass); `OWNER = Writer("owner", None, None)`; `SYSTEM = Writer("system", None, None)`; `LedgerRow(id, at: datetime, principal, actor, client, kind: str, symbol: str | None, ref_table: str, ref_id: int, snapshot_id: int | None, work_item_id: int | None, summary: str)`; `record(conn, writer: Writer, at: datetime, kind: str, symbol: str | None, ref_table: str, ref_id: int, *, snapshot_id: int | None = None, work_item_id: int | None = None, summary: str) -> int`; `entries(conn, symbol: str | None = None, limit: int = 100) -> list[LedgerRow]` newest first.
- Produces: the tables of migration 005, each with `created_at`, `principal`, `actor` and `client` where a write makes it: `ledger`, `work_items`, `notes`, `findings`, `kill_criteria`, `news_items`, `overrides`, `reviews`, `review_log`, `secondary_valuations`, `derivations`, `reports`, `judgments`. The columns are the records of Tasks 2 to 7's Interfaces; this task writes the DDL for all of them from the spec's sections 7 to 13 so one migration ships.

- [ ] **Step 1: Write the failing tests**

In `tests/policy/test_policy.py`: `test_v8_is_the_packaged_policy` (version `fairband-policy-v8`; `override_ranges["growth.belief"] == (-0.20, 0.60)` and the other ten pairs above; `override_primary_evidence_above_p90 is True`; `secondary_parts_max == 10`, `secondary_years_min == 3`, `secondary_years_max == 15`; `stance_words == ("buy", "hold", "trim", "avoid")`; each with a non-empty source); `test_v7_is_byte_identical_under_its_hash` on the pattern of the v6 test; `test_v8_is_v7_with_the_six_values_added`. In `tests/store/test_db.py`: `test_migration_005_creates_the_agent_tables` (after `migrate`, `sqlite_master` lists the thirteen tables). In `tests/store/test_ledger.py`:

```python
def test_record_and_entries(conn):
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    first = record(conn, writer, NOW, "note", "AAPL", "notes", 1, summary="a note")
    second = record(conn, SYSTEM, NOW + timedelta(minutes=1), "work-item", "MSFT", "work_items", 1, summary="expiry")
    rows = entries(conn)
    assert [r.id for r in rows] == [second, first]
    assert rows[1].actor == "claude-opus-5-5" and rows[1].client == "claude-code/2.1"
    assert [r.symbol for r in entries(conn, "AAPL")] == ["AAPL"]
    assert len(entries(conn, limit=1)) == 1
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/policy/test_policy.py tests/store/test_db.py tests/store/test_ledger.py -q`
Expected: FAIL on the v8 tests, the migration test and the ledger test.

- [ ] **Step 3: Implement**

The v8 file: v7's text with `version = "fairband-policy-v8"`, a header line "v8: v7 with the override ranges, the evidence rule, the secondary valuation's bounds and the stance words (spec 2026-11-06 Tier 2, section 19)", and six `[values.<name>]` tables; `override_ranges` holds one sub-table per tag (`"growth.belief" = [-0.20, 0.60]`), its source line spec 10.2. The loader: six `read(...)` calls (`_ranges` parses the tag table into `dict[str, tuple[float, float]]` and refuses a pair whose low is not below its high) and six `Policy` fields. `types.py`: the two literals widened; `result_from_json` passes a `JUDGMENT` input through as it does the others. The migration's DDL from the Interfaces of this plan; `reviews.result` holds the result JSON as `snapshots.result` does. `ledger.py` on the pattern of `watchlists.py`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS; the goldens match (the version fields are masked).

- [ ] **Step 5: Update `docs/method.md`**

4.1's six rows with Setting "no" and spec 19's sources; 11's row: "2026-11-xx: Tier 2 (spec 2026-11-06). The mechanical method is unchanged at 0.9. A review (section 14) carries `fairband-review/1`, a secondary valuation (section 15) `fairband-secondary/1`. Policy v8 adds six values, none a setting."; 13's six terms.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/policy src/fairband/store src/fairband/engine/types.py docs/method.md tests
git commit -m "Add policy v8, the JUDGMENT tag, the agent tables and the ledger"
```

### Task 2: The work inbox and the research records

**Files:**
- Create: `src/fairband/store/inbox.py`, `src/fairband/store/research.py`
- Create: `src/fairband/web/identity.py`, `src/fairband/web/agents_api.py`
- Modify: `src/fairband/web/app.py` (`add_agent_routes` registered beside the watchlist routes; the module docstring's identity paragraph)
- Test: `tests/store/test_inbox.py`, `tests/store/test_research.py`, `tests/web/test_identity.py`, `tests/web/test_agents_api.py`

**Interfaces:**
- Produces, `fairband.store.inbox`: `Mode = Literal["valuation review", "full report"]`; `State = Literal["pending", "claimed", "done", "declined", "dropped"]`; `Origin = Literal["owner", "agent", "expiry"]`; `WorkItem(id, symbol, mode, note: str, snapshot_id: int | None, origin, posted_by: Principal, posted_actor: str | None, posted_at: datetime, state, claimed_by: str | None, claimed_at: datetime | None, report_id: int | None, reason: str | None, finished_at: datetime | None, expiry_valid_until: date | None)`; `post_item(conn, symbol, mode, note, snapshot_id, origin, writer: Writer, at, *, expiry_valid_until: date | None = None) -> int`; `claim_item(conn, item_id, actor: str, at) -> WorkItem` (`KeyError` on no item; `ValueError("work item n is done")` and the like on a finished one); `complete_item(conn, item_id, report_id, at) -> WorkItem`; `decline_item(conn, item_id, reason, at) -> WorkItem` (`ValueError("a decline needs a reason")` on an empty one); `drop_item(conn, item_id, at) -> WorkItem`; `work_items(conn, state: State | None = None) -> list[WorkItem]` newest first; `work_item(conn, item_id) -> WorkItem`; `open_item(conn, symbol) -> WorkItem | None` (pending or claimed); `oldest_pending(conn) -> WorkItem | None`; `post_expiry_items(conn, today: date, at: datetime) -> tuple[list[int], list[int]]` (the ids posted, the ids dropped).
- Produces, `fairband.store.research`: `NoteRow(id, symbol, text, principal, actor, client, at, override_id)`, `add_note(conn, symbol, text, writer, at, override_id=None) -> int`, `notes_for(conn, symbol) -> list[NoteRow]`; `FindingRow(id, symbol, as_of: date, text, source_kind, source_ref, source_note, value: float | None, unit: str | None, period: str | None, principal, actor, client, at)`, `add_finding(conn, symbol, as_of, text, source: dict, writer, at, *, value=None, unit=None, period=None) -> int` (`ValueError` on a kind outside `filing`, `transcript`, `url`, `vendor`, `base-rate`, or a unit outside `currency`, `percent`, `multiple`, `count`, `per-share`), `findings_for(conn, symbol)`, `finding_row(conn, finding_id) -> FindingRow | None`; `KillCriterionRow(id, symbol, text, state, report_id, principal, actor, client, at, state_reason, state_at)`, `add_kill_criterion(conn, symbol, text, writer, at, report_id=None) -> int`, `set_kill_criterion(conn, criterion_id, state, reason, at)` (states `open`, `triggered`, `retired`), `kill_criteria_for(conn, symbol)`; `NewsItemRow(id, symbol, date, headline, source, text, kill_criterion_id, principal, actor, client, at)`, `add_news_item(...) -> int`, `news_items_for(conn, symbol)`.
- Produces, `fairband.web.identity`: `PRINCIPAL_HEADER = "X-Fairband-Principal"`, `ACTOR_HEADER = "X-Fairband-Actor"`, `CLIENT_HEADER = "X-Fairband-Client"`, `IDENTIFY_FIRST = "identify first: the model identifier you run as"`; `writer_of(request: Request) -> Writer` (no headers → `OWNER`; principal `agent` without an actor → `HTTPException(400, IDENTIFY_FIRST)`; a principal other than `owner` or `agent` → 400).
- Produces, `fairband.web.agents_api`: `add_agent_routes(app, conn_factory, clock)` with `GET /api/inbox` (runs `post_expiry_items` first; `{items: [...]}` with the camelCase keys of `WorkItem`), `POST /api/inbox` `{symbol, mode, note?}` → 201 the item (origin from the writer's principal; 409 "an item for <symbol> is open" when one is), `POST /api/inbox/claim` `{itemId?}` → the item claimed by the writer's actor (the named one, else the oldest pending; 404 "no pending work item" with none; an owner's claim is 400 "a claim is an agent's write"), `PATCH /api/inbox/{id}` `{action: "complete" | "decline", reportId?, reason?}` (`complete` needs a published report of the symbol, Task 7; until then 404 "no report <id> for <symbol>"), `GET/POST /api/companies/{symbol}/notes`, `/findings`, `/kill-criteria`, `/news-items`, `PATCH /api/kill-criteria/{id}` `{state, reason}`, `GET /api/ledger?symbol=&limit=`, `GET /api/companies/{symbol}/ledger`; every write records a ledger row with the writer and the company's latest snapshot id.

- [ ] **Step 1: Write the failing tests**

`tests/store/test_inbox.py`, on `tests/store/conftest.py`'s migrated connection with AAPL and MSFT snapshots and a watchlist holding both (build them in the test module with `insert_snapshot` on `refusal_result` rows whose `valid_until` the test sets):

```python
def test_post_claim_complete(conn):
    item_id = post_item(conn, "AAPL", "full report", "why", 1, "owner", OWNER, NOW)
    assert work_item(conn, item_id).state == "pending"
    claimed = claim_item(conn, item_id, "claude-opus-5-5", NOW)
    assert (claimed.state, claimed.claimed_by) == ("claimed", "claude-opus-5-5")
    done = complete_item(conn, item_id, 7, NOW)
    assert (done.state, done.report_id) == ("done", 7)
    with pytest.raises(ValueError, match="work item 1 is done"):
        claim_item(conn, item_id, "gpt-5", NOW)

def test_a_claim_can_be_taken_over_by_name(conn): ...  # claimed_by moves to the second actor
def test_oldest_pending_and_open_item(conn): ...
def test_decline_needs_a_reason(conn): ...
def test_an_expired_watchlist_company_posts_one_valuation_review(conn):
    # AAPL valid_until 2026-10-01, today 2026-11-01, on a list: one item, origin "expiry", mode "valuation review", expiry_valid_until 2026-10-01; a second call posts nothing
def test_an_expired_company_on_two_lists_posts_one_item(conn):
    # on two lists: one item; removed from one list: still pending; removed from both: dropped
def test_an_open_item_blocks_the_expiry_post(conn): ...
def test_a_new_valid_until_posts_again_after_the_first_is_done(conn): ...
```

`tests/store/test_research.py`: one test per record kind (add, read back, the ordering newest first), `test_a_finding_refuses_an_unknown_source_kind_or_unit`, `test_a_kill_criterion_moves_state_with_a_reason`. `tests/web/test_identity.py`: `test_no_headers_is_the_owner`, `test_an_agent_with_an_actor_and_a_client`, `test_an_agent_without_an_actor_is_told_to_identify` (400, `IDENTIFY_FIRST`), `test_an_unknown_principal_is_refused`. `tests/web/test_agents_api.py`, on `tests/web/conftest.py`'s client: `test_post_and_list_inbox` (201, then `GET /api/inbox` lists it with `postedBy == "owner"`), `test_an_agent_post_carries_its_actor` (the headers; `postedActor == "claude-opus-5-5"`, the ledger row's `actor` too), `test_a_second_open_item_is_409`, `test_claim_and_decline_over_the_api`, `test_notes_findings_kill_criteria_and_news_items_round_trip`, `test_every_write_is_a_ledger_row` (`GET /api/companies/AAPL/ledger` lists one row per write, newest first, each with `snapshotId` the AAPL snapshot's), `test_the_inbox_read_runs_the_expiry_rule` (a watchlist with AAPL, the clock past its window: `GET /api/inbox` shows the expiry item with `origin == "expiry"` and `postedBy == "system"`).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/store/test_inbox.py tests/store/test_research.py tests/web/test_identity.py tests/web/test_agents_api.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement**

`inbox.py` and `research.py` on `watchlists.py`'s pattern (frozen rows, `transaction`, `_require`). `post_expiry_items`: one query joins `watchlist_entries` to each symbol's latest snapshot (`MAX(id)` per symbol) where `valid_until < today`, excludes symbols with an open item or an expiry item with the same `expiry_valid_until`, posts the rest with `SYSTEM`; then drops pending expiry items whose symbol is on no list. `identity.py` reads the three headers. `agents_api.py` on `watchlists_api.py`'s pattern with `_refusals` mapping `KeyError` → 404, `ValueError` → 400, and the open-item and finished-state cases → 409; the JSON shapes camelCase; the ledger row written in the same transaction as the record.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/store/inbox.py src/fairband/store/research.py src/fairband/web tests
git commit -m "Add the work inbox with its expiry rule, the research records and the identity headers"
```

### Task 3: Overrides in the engine and the review's bridge

**Files:**
- Create: `src/fairband/engine/overrides.py`, `src/fairband/engine/review.py`
- Modify: `src/fairband/engine/route_steps.py:54-80` (`Context`, `StartUpContext`: `overrides`; `chosen`, `judgment_inputs`)
- Modify: `src/fairband/engine/route.py:208-245` (`value_company`'s `overrides` argument; the phase override; the JUDGMENT inputs on `_valued` and `_refuse`)
- Modify: the read points: `route_mature_growth.py:86` (moat), `:99` (nri gap), `:204-222` (the steps, the belief), the runway return where `RoicTerms.of` is read (`return.runway` replaces `rr.value` and `terminal` follows the moat as today); `route_mature_stable.py:56-58`; `route_revenue_growth.py:215-236, 259` (moat, sales-to-capital, target, the held rate and the steps), `:230-231` (debt, cash); `route_decline.py:204-220` (d, sales-to-capital, debt, cash); `route_start_up.py:94-97` (debt, cash, moat, target)
- Modify: `docs/method.md`: section 14 "Reviews: overrides and the reviewed value"
- Test: `tests/engine/test_overrides.py`, `tests/engine/test_review.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces, `fairband.engine.overrides`: `OverrideTag = Literal["phase", "growth.belief", "path.hold", "path.step_2", "path.step_3", "moat.class", "margin.target", "capital.sales_to_capital", "return.runway", "earnings.nri_gap", "decline.rate", "balance.debt", "balance.cash"]`; `BRIDGE_ORDER: tuple[OverrideTag, ...]` in spec 10.4's order; `TagSpec(tag, routes: frozenset[Route], unit: str, words: tuple[str, ...] | None, period_tied_only: bool)`; `TAGS: dict[OverrideTag, TagSpec]` (`phase` on every route including `start-up`, words the six phases; `moat.class` words `None`, `Narrow`, `Wide`; the routes per spec 10.2); `Lifetime = Literal["lasting", "period-tied"]`; `State = Literal["applied", "refused-locked", "refused-evidence", "refused-unit", "refused-not-input", "refused-route", "dropped"]`; `LOCKED: dict[str, str]` (`required_return` → "r is a locked input: the hurdle rate", `terminal_growth` → "g_T is a locked input: the terminal growth ceiling", `runway_years`, `fade_years`, `margin_of_safety`, `fair_band`, `trim_multiple`, `terminal_return` → "the terminal return follows the moat", and the DATA names `price`, `shares_diluted`, `market_cap`, `revenue`, `operating_income`, `eps` → "<name> is reported data"); `Override(id: int | None, tag: OverrideTag, value: float | str, principal: Principal, actor: str | None, at: datetime, reason: str)`; `Overrides = Mapping[OverrideTag, Override]`; `route_of(phase: Phase) -> Route`; `check_override(tag: str, value: float | str, route: Route, policy: Policy, evidence_kinds: Sequence[str], lifetime: Lifetime, cap: float | None) -> tuple[State, str]` (`("applied", "")` or the state with its sentence; the order of checks: locked, not-input, route, unit (a word outside `words`, a number outside `policy.override_ranges[tag]`, a period-tied-only tag with lifetime `lasting`), evidence (none; or `growth.belief` and `path.hold` above `cap` without `filing` or `transcript` when `policy.override_primary_evidence_above_p90`)); `current_reading(result: ValuationResult, tag: OverrideTag) -> float | str | None` from the intermediates (`phase` → `result.phase.phase`; `growth.belief` → `belief.rate`; `path.hold` → `path.held`; the steps → `path_steps[0]`, `[1]`; `moat.class` → `moat`; `margin.target` → `target_margin.value` or `requirement.target_margin`; `capital.sales_to_capital` → `sales_to_capital.value`; `return.runway` → `runway_return.value`; `earnings.nri_gap` → `nri_gap`; `decline.rate` → `runoff_path.d`; `balance.debt`/`cash` → `debt`/`cash`; `None` where the key is absent).
- Produces, `fairband.engine.route_steps`: `Context.overrides: Overrides` and `StartUpContext.overrides: Overrides` (default empty); `chosen[T](c: Context | StartUpContext, tag: OverrideTag, computed: T) -> T` (the override's value when present, else `computed`); `judgment_inputs(overrides: Overrides) -> tuple[TaggedInput, ...]` (name the tag, value the number or `None`, note the word for `phase` and `moat.class`, unit the spec's, tag `JUDGMENT`, kind `judgment`, provenance source `override <id>`, `entered_at` the override's `at`, `note` the reason).
- Produces, `fairband.engine.route`: `value_company(inputs, deciles, policy, today, overrides: Overrides | None = None) -> ValuationResult`; with a `phase` override the evidence is `replace(phase, phase=<word>)` and the route follows; the result's inputs end with `judgment_inputs(overrides)`.
- Produces, `fairband.engine.review`: `REVIEW_METHOD = "fairband-review/1"`; `BridgeLine(tag, override_id, old: float | str | None, new: float | str, delta: float | None, refusal: str | None)`; `Review(result: ValuationResult, mechanical_value: float | None, bridge: tuple[BridgeLine, ...], override_ids: tuple[int, ...])`; `review_company(inputs, deciles, policy, today, overrides: Sequence[Override], mechanical: ValuationResult) -> Review` (sorts by `BRIDGE_ORDER`, applies cumulatively, one `value_company` call per line; `delta` is this step's value less the last valued step's, `None` where either is a refusal, in which case the line carries the refusal; `old` is `current_reading(mechanical, tag)`).

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_overrides.py`:

```python
def test_check_refuses_a_locked_input(policy):
    assert check_override("terminal_growth", 0.04, "mature-growth", policy, ["filing"], "lasting", None) == ("refused-locked", "g_T is a locked input: the terminal growth ceiling")

def test_check_refuses_a_tag_that_is_not_an_input(policy):  # ("refused-not-input", "colour is not an input")
def test_check_refuses_a_tag_the_route_does_not_read(policy):  # decline.rate on mature-growth → "refused-route", "the Mature Growth route does not read decline.rate"
def test_check_refuses_a_value_outside_its_range(policy):  # growth.belief 0.7 → "refused-unit", "growth.belief takes −20% to 60%"
def test_check_refuses_a_word_outside_its_words(policy):  # moat.class "Huge" → refused-unit
def test_check_refuses_a_lasting_balance_correction(policy):  # balance.debt lasting → refused-unit, "balance.debt is period-tied only"
def test_check_needs_evidence(policy):  # [] → ("refused-evidence", "an override needs evidence")
def test_a_belief_above_the_cap_needs_a_filing_or_a_transcript(policy):
    assert check_override("growth.belief", 0.30, "mature-growth", policy, ["finding"], "lasting", 0.25)[0] == "refused-evidence"
    assert check_override("growth.belief", 0.30, "mature-growth", policy, ["transcript"], "lasting", 0.25) == ("applied", "")
def test_current_reading_on_each_golden():  # MGCO growth.belief == im["belief"]["rate"]; DCCO decline.rate == im["runoff_path"]["d"]; SUCO phase == "Start-up"; MSCO margin.target is None
```

`tests/engine/test_review.py`, with `OVERRIDE = lambda tag, value, id=1: Override(id, tag, value, "agent", "claude-opus-5-5", NOW, "because")` and the golden inputs of `support.engine_companies`:

```python
@pytest.mark.parametrize("symbol,tag,value", [
    ("MGCO", "growth.belief", 0.08), ("MGCO", "moat.class", "Wide"), ("MGCO", "earnings.nri_gap", 0.5),
    ("MGCO", "return.runway", 0.20), ("MGCO", "path.step_2", 0.12), ("MSCO", "moat.class", "Narrow"),
    ("HGCO", "margin.target", 0.25), ("HGCO", "capital.sales_to_capital", 1.5), ("HGCO", "path.hold", 0.30),
    ("YGCO", "balance.cash", 500.0), ("DCCO", "decline.rate", -0.02), ("DCCO", "capital.sales_to_capital", 1.8),
])
def test_one_override_equals_the_engine_with_that_input(symbol, tag, value, policy, deciles):
    inputs = FIXTURES[symbol]()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    review = review_company(inputs, deciles, policy, TODAY, [OVERRIDE(tag, value)], mechanical)
    direct = value_company(inputs, deciles, policy, TODAY, {tag: OVERRIDE(tag, value)})
    assert review.result.value == pytest.approx(direct.value, abs=1e-9)
    assert review.result.value != mechanical.value
    assert len(review.bridge) == 1 and review.bridge[0].delta == pytest.approx(review.result.value - mechanical.value, abs=1e-9)
    assert review.bridge[0].old == current_reading(mechanical, tag)
    judged = [i for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert [i.name for i in judged] == [tag] and judged[0].provenance.source == "override 1"

def test_two_overrides_sum_to_the_difference(policy, deciles):  # MGCO belief 0.08 and moat Wide: deltas sum to reviewed − mechanical to 1e-9; the lines in BRIDGE_ORDER (belief before moat)
def test_a_start_up_overridden_to_young_growth_is_valued(policy, deciles):
    # SUCO with phase "Young Growth": result.route == "revenue-growth", result.value is not None or the refusal names the route's own guard; bridge[0].old == "Start-up"; mechanical_value is None
def test_the_route_check_reads_the_overridden_phase(policy):
    # route_of("Young Growth") == "revenue-growth"; check_override("margin.target", 0.2, route_of("Young Growth"), ...) is applied
def test_a_refusing_step_ends_the_bridge(policy, deciles):
    # HGCO with capital.sales_to_capital 0.1 (a reinvestment that outruns the terminal): the line's refusal == "value not positive under the reinvestment charge", delta None, review.result.value is None
def test_no_override_leaves_the_golden_bit_for_bit(policy, deciles):  # value_company(..., overrides={}) == value_company(...) for every golden
```

`test_golden.py`: no change; it must still pass. `tests/test_method_doc.py` (new): `test_section_14_names_every_override_tag` reads `docs/method.md` from the repository root and asserts every `OverrideTag` and `override_ranges` appear under the heading "## 14."; written here with the section, so the test fails until Step 5.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_overrides.py tests/engine/test_review.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement**

`overrides.py` as the Interfaces say; the sentences in the brand book's register. `route_steps.chosen` casts nothing: the caller passes `computed` of the right type and the override's stored value is a float or a word. The read points: `moat = chosen(c, "moat.class", moat_class(i.moat_score, policy))`; the belief `replace(belief, rate=...)` when chosen; the steps replace `path.steps[k]` and mark the step not held; `path.hold` replaces the resolved g_3 after the cap (the override is the agent's rate, the cap does not bind it; the flag `path-held` stays off); `return.runway` replaces `rr.value` inside `RoicTerms.of` through a new keyword `runway_override: float | None`; `decline.rate` replaces `_decline_rate`'s result with `floored` false; `balance.*` replace `i.debt`/`i.cash` before `nil`. `value_company`: the phase override before the price guard; `_route` on the overridden phase; a Start-up override to another phase takes that phase's route with a `Context` (trailing figures required as for any such row). `review.py`'s loop.

- [ ] **Step 4: Run the suite, then the goldens**

Run: `uv run pytest -q`
Expected: PASS; `test_defaults_match_the_golden` for all six unchanged.

- [ ] **Step 5: Update `docs/method.md`**

Section 14: what an override is (10.1); the table of 10.2 with the routes and ranges (citing `override_ranges`); the rules of 10.3 in the check's order; the JUDGMENT tag and its provenance; the recompute and the bridge's order (10.4); the refusal line; "a review follows its snapshot" (10.5, built in Task 4, stated here); the log (10.6).

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine docs/method.md tests/engine
git commit -m "Let the routes read overridden inputs and build the review's bridge in the method's order"
```

### Task 4: Reviews in the store, the override routes and the refresh that follows

**Files:**
- Create: `src/fairband/store/overrides.py`, `src/fairband/store/reviews.py`, `src/fairband/refresh/reviews.py`, `src/fairband/web/reviews_api.py`
- Modify: `src/fairband/refresh/run.py:469-508` (`_value_stage`: `follow_snapshot` after `insert_snapshot`), `src/fairband/refresh/run_price.py:249-290` (`_reprice_stage`: `reprice_review` after the snapshot)
- Modify: `src/fairband/web/app.py:100-110` (`create_app` gains `tax: TaxTable | None = None`, loading the packaged table when `None`; `add_review_routes` registered), `src/fairband/__main__.py:118-150` (`_serve` passes `tax`)
- Test: `tests/store/test_overrides.py`, `tests/store/test_reviews.py`, `tests/refresh/test_reviews_follow.py`, `tests/web/test_reviews_api.py`

**Interfaces:**
- Produces, `fairband.store.overrides`: `OverrideRow(id, symbol, tag, old: float | str | None, new: float | str, unit, reason, evidence: tuple[dict, ...], lifetime, period: str | None, corrected_value: float | str | None, snapshot_id, principal, actor, client, at, state, message: str, review_id: int | None, drop_reason: str | None, dropped_at: datetime | None)`; `insert_override(conn, symbol, tag, old, new, unit, reason, evidence, lifetime, period, corrected_value, snapshot_id, writer, at, state, message) -> int`; `set_review(conn, override_id, review_id)`; `drop_override(conn, override_id, reason, at)` (state `dropped`); `applied_overrides(conn, symbol) -> list[OverrideRow]` (state `applied`, by id); `overrides_for(conn, symbol) -> list[OverrideRow]` newest first; `override_row(conn, override_id) -> OverrideRow | None`; `as_override(row: OverrideRow) -> Override` (the engine's record).
- Produces, `fairband.store.reviews`: `ReviewRow(id, symbol, snapshot_id, refresh_id: int | None, created_at, value, buy_level, fair_low, fair_high, trim_level, price_to_value, designation, refusal, mechanical_value, bridge: tuple[dict, ...], override_ids: tuple[int, ...], policy_version, method_version, review_method, settings_hash, deciles_refresh_id, result: ValuationResult)`; `insert_review(conn, review: Review, symbol, snapshot_id, refresh_id, *, clock) -> int`; `latest_review(conn, symbol) -> ReviewRow | None`; `reviews_for(conn, symbol) -> list[ReviewRow]`; `latest_reviews(conn) -> dict[str, ReviewRow]`; `LogRow(id, at, symbol, refresh_id, snapshot_id, review_id, mechanical_phase, mechanical_value, reviewed_phase, reviewed_value, secondary_value, price, designation, stance)`; `log_review(conn, at, symbol, refresh_id, snapshot_id, review_id, mechanical_phase, mechanical_value, reviewed_phase, reviewed_value, secondary_value, price, designation, stance) -> int`; `review_log(conn, symbol: str | None = None) -> list[LogRow]`; `latest_secondary_value(conn, symbol) -> float | None` and `latest_stance(conn, symbol) -> str | None`, two readers over the `secondary_valuations` and `reports` tables of migration 005 (empty until Tasks 5 and 7 write them), which `follow_snapshot` reads for the log.
- Produces, `fairband.refresh.reviews`: `follow_snapshot(conn, inputs: CompanyInputs, result: ValuationResult, snapshot_id: int, deciles, policy, today, refresh_id: int | None, clock) -> int | None` (drops a period-tied override whose `corrected_value` differs from `current_reading(result, tag)` or whose company's `data_date` moved past the override's snapshot's, with `SYSTEM` ledger rows; returns `None` with no applied override left; else `review_company` on the rest, `insert_review`, `log_review` with the latest secondary's value and the latest report's stance, the review id); `reprice_review(conn, symbol, snapshot_id, price, price_date, policy, refresh_id, clock, *, observed_at, entered_at) -> int | None` (the latest review's result through `route.reprice`, inserted on the new snapshot with the same bridge and override ids; `None` without a review).
- Produces, `fairband.web.reviews_api`: `add_review_routes(app, conn_factory, policy, tax, clock)` with `POST /api/companies/{symbol}/overrides` `{tag, new, reason, evidence: [{kind, ref, note}], lifetime, period?}` → 201 `{override: {...}, review: {...} | null, bridge: [...]}` (the state and message of the check; on `applied`, `build_inputs` on the latest deciles, `review_company` over every applied override, `insert_review`, `log_review`); `DELETE /api/overrides/{id}` `{reason}` (the drop and a recompute of the rest, or no review left); `GET /api/companies/{symbol}/overrides`, `/reviews` (newest first, the bridge included), `/reviews/latest`; `GET /api/review-log?symbol=`; `require_current(effective: Policy, snapshot: SnapshotRow) -> None` raising `HTTPException(409, SETTINGS_CHANGED | POLICY_CHANGED | METHOD_CHANGED)` from `run_price`'s constants; the `cap` for the evidence rule read from the snapshot's `belief.sales_class` or `path.sales_class` through `policy.base_rates` (`sales_p90_5y`), `None` without one.
- Consumes: Task 3's engine; Task 1's ledger; `settings_api.effective`.

- [ ] **Step 1: Write the failing tests**

`tests/store/test_overrides.py` and `tests/store/test_reviews.py`: the round trips, `applied_overrides` after a drop, `latest_reviews` with two companies, `review_log` by symbol. `tests/refresh/test_reviews_follow.py` on `refresh_env`'s `env_valued` (ACME is Mature Growth): `test_a_revalue_writes_a_review_for_a_company_with_an_applied_override` (insert an applied `growth.belief` override for ACME, run a revalue: `latest_review(conn, "ACME")` is on the new snapshot, its `refresh_id` the revalue's, `review_log` has one row with both values); `test_a_price_refresh_reprices_the_review` (after the revalue, a price refresh: a new review on the new snapshot with the same `value` and `bridge`, a moved `price_to_value`); `test_a_period_tied_override_drops_when_its_line_vanishes` (a period-tied `balance.cash` on AXLE with `corrected_value` 100; the next revalue's inputs give `None` for cash because the fixture's balance sheet is served without the line: the override is `dropped` with "the input the override corrected changed", no review, a `SYSTEM` ledger row); `test_a_period_tied_override_drops_when_the_data_date_moves` (a full refresh serving a newer statement). `tests/web/test_reviews_api.py`:

```python
def test_an_applied_override_returns_the_review_and_the_bridge(client):
    r = client.post("/api/companies/AAPL/overrides", json=BELIEF_8, headers=AGENT)
    assert r.status_code == 201
    body = r.json()
    assert body["override"]["state"] == "applied" and body["review"]["value"] != body["review"]["mechanicalValue"]
    assert body["bridge"][0]["tag"] == "growth.belief" and body["bridge"][0]["old"] == pytest.approx(MGCO_BELIEF)
    assert client.get("/api/companies/AAPL/reviews/latest").json()["overrideIds"] == [body["override"]["id"]]

def test_a_refused_override_is_stored_with_its_state(client):  # terminal_growth → 201? no: 400 with the state and message, and the row stored; GET /overrides lists it with state "refused-locked"
def test_a_second_override_on_a_tag_replaces_the_first(client):  # the first reads dropped, "replaced by override 2"
def test_a_drop_recomputes_or_clears_the_review(client):
def test_settings_changed_refuses_an_override(client):  # PUT a setting through /api/settings, then POST → 409 "settings changed: run a revalue"
def test_the_owner_cannot_add_an_override_but_can_drop_one(client):  # POST without headers → 403 "an override is an agent's write; the owner drops one"; DELETE without headers → 200
def test_every_override_write_is_a_ledger_row(client):
```

(`BELIEF_8` is `{"tag": "growth.belief", "new": 0.08, "reason": "guidance raised", "evidence": [{"kind": "transcript", "ref": "Q3 call", "note": ""}], "lifetime": "lasting"}`; `AGENT` the three headers with `HEADER`; `MGCO_BELIEF` the fixture's `belief.rate`.)

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/store/test_overrides.py tests/store/test_reviews.py tests/refresh/test_reviews_follow.py tests/web/test_reviews_api.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement**

The store modules on `snapshots.py`'s pattern (`result` as JSON, the floats as `repr`). `follow_snapshot` in `run.py` inside the same transaction as the snapshot; `reprice_review` likewise in `run_price.py`. The API: `require_current` first; the check with `check_override`; the route of the check is `route_of(<the phase override's value>)` when the applied set holds one, else the snapshot's route (a Start-up row's route is `start-up`); a refused override answers 400 with `{override: {...}}` and is stored; the owner's `POST` is 403 (*my call* in the plan, within spec 3's non-goal: the owner's overrides come later).

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/store src/fairband/refresh src/fairband/web src/fairband/__main__.py tests
git commit -m "Store overrides and reviews, serve them over the API, and follow every new snapshot with a review"
```

### Task 5: The secondary valuation and derivations

**Files:**
- Create: `src/fairband/engine/secondary.py`, `src/fairband/store/secondary.py`
- Modify: `src/fairband/web/reviews_api.py` (`POST /api/companies/{symbol}/secondary`, `GET .../secondary`, `POST /api/companies/{symbol}/derivations`, `GET /api/derivations/{id}`)
- Modify: `src/fairband/refresh/inputs_statements.py:281` (`balance_lines` is what the secondary reads for debt and cash; confirm it returns `debt` and `cash` as assembly's `CompanyInputs.debt`/`cash` are read, else add `newest_debt_and_cash(conn, symbol) -> tuple[float | None, float | None]`)
- Modify: `docs/method.md`: section 15 "The secondary valuation"
- Test: `tests/engine/test_secondary.py`, `tests/store/test_secondary.py`, `tests/web/test_secondary_api.py`

**Interfaces:**
- Produces, `fairband.engine.secondary`: `SECONDARY_METHOD = "fairband-secondary/1"`; `Part(name: str, fcff: tuple[float, ...], terminal_growth: float, note: str | None)`; `PartValue(name, pv: tuple[float, ...], terminal: float, terminal_pv: float, value: float)`; `SecondaryValuation(parts: tuple[PartValue, ...], firm_value, debt, cash, shares, equity, value_per_share, levels: Levels | None, price_to_value: float | None, designation: Designation | None)`; `secondary_value(parts: Sequence[Part], debt: float, cash: float, shares: float, price: float | None, moat: Moat, policy: Policy) -> SecondaryValuation` (raises `ValueError` naming the rule: "a part has 3 to 15 years", "the terminal growth is at most g_T, 3.0%", "at most 10 parts", "at least one part", "a positive diluted share count"); the levels and designation only when the value a share is above zero.
- Produces, `fairband.store.secondary`: `SecondaryRow(id, symbol, snapshot_id, created_at, principal, actor, client, parts: tuple[dict, ...], firm_value, debt, cash, shares, equity, value_per_share, buy_level, fair_low, fair_high, trim_level, price_to_value, designation, reason, evidence, debt_source: str, cash_source: str, policy_version, settings_hash, deciles_refresh_id, secondary_method)`; `insert_secondary(...) -> int`; `latest_secondary(conn, symbol) -> SecondaryRow | None`; `secondaries_for(conn, symbol)`; `DerivationRow(id, symbol, operation, a: str, b: str, years: int | None, value: float | None, unit: str | None, principal, actor, client, at)`; `insert_derivation(...) -> int`; `derivation_row(conn, derivation_id) -> DerivationRow | None`.
- Produces, routes: `POST /api/companies/{symbol}/secondary` `{parts: [{name, fcff, terminalGrowth, note?}], reason, evidence, debt?, cash?}` → 201 the row (after `require_current`; debt and cash from the newest balance sheet's lines unless passed, each then needing its own evidence item, `debt_source` "statements" or "agent"; a foreign filer → 400 "foreign filer: currency and share-unit handling not built yet"; no shares → 400 "no diluted share count"; a `ValueError` of the engine → 400 its sentence); `POST .../derivations` `{derivations: [{operation, a, b, years?}]}` → 201 `{derivations: [{id, value, unit}]}` with the five operations over refs resolved by Task 7's `resolve` (until Task 7 lands, this route resolves `snapshot:` and `fact:` refs through a local stub the task replaces; *the plan's order puts Task 7 after*, so this task registers the route and Task 7 switches it to `resolve`).
- Consumes: Task 4's `require_current`; `balance_lines`.

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_secondary.py` with spec 20.1's figures:

```python
ONE = [Part("the business", (100.0, 105.0, 110.25, 115.7625, 121.550625), 0.03, None)]

def test_one_part(policy):
    v = secondary_value(ONE, 200.0, 100.0, 100.0, 15.0, "None", policy)
    assert v.parts[0].pv == pytest.approx((91.7431, 88.3764, 85.1332, 82.0091, 78.9996), abs=1e-4)
    assert v.parts[0].terminal == pytest.approx(2086.6191, abs=1e-4) and v.parts[0].terminal_pv == pytest.approx(1356.1592, abs=1e-4)
    assert (v.firm_value, v.equity, v.value_per_share) == pytest.approx((1782.4206, 1682.4206, 16.8242), abs=1e-4)

def test_two_parts(policy):  # + Part("a unit", (20.0,) * 5, 0.0, None) → 19.0464
def test_the_terminal_growth_is_capped_at_g_t(policy):  # 0.035 → ValueError "the terminal growth is at most g_T, 3.0%"
def test_a_part_has_three_to_fifteen_years(policy):  # 2 years and 16 years refused
def test_at_most_ten_parts(policy):
def test_a_negative_equity_is_stored_with_no_levels(policy):  # fcff (-50,)*3, debt 1000: value_per_share < 0, levels None, designation None
def test_levels_follow_the_moat(policy):  # "Wide" → buy level = value × (1 − margin_of_safety["Wide"])
```

`tests/store/test_secondary.py`: the round trips. `tests/test_method_doc.py`: `test_section_15_names_the_three_bounds` (`secondary_parts_max`, `secondary_years_min`, `secondary_years_max` under "## 15."). `tests/web/test_secondary_api.py`: `test_a_secondary_valuation_reads_the_balance_sheet` (AAPL's fixture lines; `debtSource == "statements"`), `test_explicit_debt_and_cash_need_evidence`, `test_a_foreign_filer_is_refused`, `test_settings_changed_refuses_a_secondary`, `test_derivations_in_one_call` (ratio, growth and cagr over two `snapshot:` refs of AAPL's `inputs/revenue` and the like, the values checked by hand), `test_a_secondary_is_a_ledger_row`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_secondary.py tests/store/test_secondary.py tests/web/test_secondary_api.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement**

`secondary.py`: the arithmetic of spec 11 with `policy.required_return`; `levels_for` and `designation_for` as the routes use them. The store on `snapshots.py`'s pattern. The routes in `reviews_api.py`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md`**

Section 15: the inputs, the arithmetic (the three lines of spec 11), the bounds citing `secondary_parts_max`, `secondary_years_min`, `secondary_years_max` and g_T, the sources of debt and cash, the two refusals, "as of its snapshot", the worked numbers of spec 20.1.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine/secondary.py src/fairband/store/secondary.py src/fairband/web/reviews_api.py src/fairband/refresh docs/method.md tests
git commit -m "Value a company a second way from an explicit cash-flow path, and store the agent's derivations"
```

### Task 6: The company reads and the financial tables

**Files:**
- Create: `src/fairband/reports/__init__.py`, `src/fairband/reports/tables.py`, `src/fairband/web/reports_api.py`
- Modify: `src/fairband/web/app.py` (`add_report_routes` registered)
- Test: `tests/reports/test_tables.py`, `tests/web/test_company_reads.py`

**Interfaces:**
- Produces, `fairband.reports.tables`: `TABLES = ("growth", "cash_flow", "solvency", "returns", "capital_allocation", "quality")`; `Cell(period: str, value: float | None, unit: str, ref: str)`; `Row(name: str, unit: str, cells: tuple[Cell, ...])`; `Table(name: str, rows: tuple[Row, ...])`; `financial_tables(conn, symbol: str, policy: Policy) -> tuple[Table, ...]` over the last five fiscal years on file (the `fact:` refs of each line; a ratio's ref is `table:<symbol>/<table>/<row>/<year>`): `growth` (revenue, revenue growth, gross margin, operating margin, net margin, EPS), `cash_flow` (operating cash flow, capital spending, free cash flow, free cash flow ÷ net income, stock compensation ÷ revenue), `solvency` (cash, debt, net debt ÷ EBITDA, interest coverage, current ratio, cash runway in years when operating cash flow is negative), `returns` (ROIC by year from `roic.py`'s capital years, ROE, the ten-year aggregate ROIC against r), `capital_allocation` (dividends, buybacks, share count change, acquisitions when the line is on file), `quality` (Altman Z″ by `distress.altman_z` and Piotroski F by `distress.piotroski_f` on the balance years, Beneish M as a `None` cell whose ref is `table:.../quality/beneish_m/<year>` with the note "not on file"); the rows of each table are the builder's within design.md 9.3's list (spec 23).
- Produces, `fairband.web.reports_api`: `add_report_routes(app, conn_factory, policy, clock)` with `GET /api/companies/{symbol}/financials` (the fiscal-year series of `series_for`, the trailing figures, the balance years, each figure `{value, unit, ref}` with its `fact:` ref), `/financial-tables`, `/estimates` (the stored quarterly and annual consensus with `fact:`-style refs `estimate:<symbol>/<period>/<field>`), `/price-history?years=` (the stored closes), `/peers` (the mature peers with their figures and the source, as `build_inputs` reads them); `GET /api/methodology/{section}` → `{id, title, text}`, the Methodology page's section parsed from `methodology.html` with `html.parser`, its text whitespace-collapsed, the elements `methodology.js` fills with a live value replaced by the effective policy's value formatted as that script formats it (the builder reads the script for the attribute name; 404 on an unknown id); the report routes come in Task 7.

- [ ] **Step 1: Write the failing tests**

`tests/reports/test_tables.py` on a migrated connection holding the fixture statements of `tests/refresh/synthetic.py` for one company (reuse `refresh_env`'s `env_valued`): `test_six_tables_with_five_years`, `test_every_cell_has_a_ref_that_resolves` (each `fact:` ref names a line and a year the store holds; each `table:` ref is the cell's own path), `test_z_and_f_on_a_mature_growth_row` (ACME's `quality` rows carry a score where the lines exist), `test_beneish_m_is_not_on_file`, `test_a_missing_line_is_a_none_cell`. `tests/web/test_company_reads.py`: one test per route on the web fixtures, each asserting the shape and one figure against the fixture; `test_a_methodology_section_reads_with_its_live_values` (`mature-growth` names the hurdle rate as `9.0%`; an unknown id is 404).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/reports tests/web/test_company_reads.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement**

`tables.py` reads the statements through `inputs_statements.statements_for` and `balance_years`; the ratios in one place; every `Cell` carries its ref. The routes in `reports_api.py`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/reports src/fairband/web tests
git commit -m "Serve the company's financials, estimates, price history, peers and six financial tables with a reference on every figure"
```

### Task 7: Reports, the number check, judgments and the export

**Files:**
- Create: `src/fairband/reports/refs.py`, `src/fairband/reports/check.py`, `src/fairband/reports/render.py`, `src/fairband/store/reports.py`
- Modify: `src/fairband/web/reports_api.py` (the report routes), `src/fairband/web/reviews_api.py` (derivations through `resolve`), `src/fairband/web/agents_api.py` (`complete` checks the report)
- Modify: `docs/method.md`: section 16 "Reports: the number check"
- Test: `tests/reports/test_refs.py`, `tests/reports/test_check.py`, `tests/reports/test_render.py`, `tests/store/test_reports.py`, `tests/web/test_reports_api.py`

**Interfaces:**
- Produces, `fairband.reports.refs`: `Resolved(value: float | str | None, unit: str | None, period: str | None, snapshot_id: int | None)`; `resolve(conn, symbol: str, ref: str, policy: Policy) -> Resolved | None` for every ref form of spec 13.2 (`snapshot:`, `review:`, `secondary:`, `fact:`, `table:`, `finding:`, `derived:`, `response:` with a JSON pointer, `policy:`); `same_snapshot(conn, cited: int, latest: int) -> bool` (the two are one, or the latest is a reprice of the cited: equal `data_date`, `method_version`, `policy_version`, `settings_hash` and `value`).
- Produces, `fairband.reports.check`: `UNRESOLVED = "unresolved reference"`, `WRONG_UNIT = "wrong unit"`, `WRONG_PERIOD = "wrong period"`, `WRONG_SNAPSHOT = "wrong snapshot"`, `NO_REFERENCE = "a number with no reference"`, `NOT_EMITTED = "a derived figure the engine has not emitted"`; `Finding(where: str, what: str, detail: str)` (`where` is `section <i>, part <j>` and the cite text); `quantities(text: str) -> list[str]` (spec 13.3's token rule); `parse_cite(text: str) -> tuple[float, str] | None` (the number and the unit suffix `$`, `%`, `x` or `""`; reads `1,234.50`, `−3.2`, `-3.2`, `(3.2)`); `rounded_equal(cite: float, suffix: str, value: float, unit: str) -> bool` (design.md 9.2's rounding: `$` to cents on a per-share or price, whole dollars on a total; `%` to one decimal of value × 100; `x` to two decimals; plain to the value's own unit); `check_sections(conn, symbol, snapshot_id, sections: Sequence[dict], policy) -> list[Finding]`.
- Produces, `fairband.reports.render`: `GLOSSARY: dict[str, str]` (the terms of `docs/method.md` 13); `appendix_a(conn, report: ReportRow, policy) -> dict` (the inputs with tags and provenance, the overrides, the bridge, the secondary parts, the checks that ran, the versions, the classifier evidence); `appendix_b(sections) -> list[dict]` (the glossary terms the sections use); `markdown(report: ReportRow, a: dict, b: list[dict]) -> str`.
- Produces, `fairband.store.reports`: `ReportRow(id, symbol, revision: int, mode, stance, sections: tuple[dict, ...], reuses_full_report_of: int | None, snapshot_id, review_id, secondary_id, work_item_id, principal, actor, client, created_at)`; `insert_report(...) -> int` (the revision is one more than the symbol's last); `latest_report(conn, symbol)`; `report_row(conn, report_id)`; `reports_for(conn, symbol)`; `latest_reports(conn) -> dict[str, ReportRow]`; `JudgmentRow(id, report_id, symbol, judgment, bull, bear, decision, override_id)`; `insert_judgments(conn, report_id, symbol, judgments) -> list[int]`; `judgments_for(conn, report_id)`; `latest_judgments(conn, symbol)`.
- Produces, routes: `POST /api/companies/{symbol}/reports` `{mode, stance, sections, judgments, killCriteria?, newsItems?, workItemId?}` → 201 `{report: {...}}` on publish, or 422 `{findings: [{where, what, detail}]}` on a rejection (nothing stored but the ledger row); the checks before the number check: the mode's section count (10, or 8 for a valuation review), the stance in `policy.stance_words`, the required judgments (phase, moat, belief; roic and target_margin where the route reads them), the sections' headings in design.md 9.3's order; a review mode with no full report stores `reuses_full_report_of` `None` and the first section must say so (the playbook's job; the server does not check the prose); `GET /api/companies/{symbol}/reports`, `GET /api/reports/{id}`, `GET /api/reports/{id}/markdown` (`text/markdown`).
- Consumes: Task 6's tables (the `table:` refs), Task 5's derivations, Task 4's reviews, Task 2's inbox (`complete_item` on `workItemId`) and research records (kill criteria and news items in the submission are inserted with the report's id).

- [ ] **Step 1: Write the failing tests**

`tests/reports/test_check.py` with spec 20.3's fixture on the web fixtures' AAPL (the golden MGCO renamed):

```python
def test_a_clean_report_has_no_findings(conn, policy): ...
def test_wrong_snapshot(conn, policy):  # a cite to snapshot:<AAL's id>/value
def test_wrong_unit_on_rounding(conn, policy):  # "$12.345" against inputs/price
def test_wrong_unit_on_a_suffix(conn, policy):  # "12.3x" against a percent
def test_wrong_period(conn, policy):  # period "2024" against fact:AAPL/revenue/2025
def test_unresolved_reference(conn, policy):  # fact:AAPL/revenue/2031
def test_a_number_with_no_reference(conn, policy):  # "revenue grew 11.2%" in a plain part
def test_a_derived_figure_the_engine_has_not_emitted(conn, policy):  # derived:999
def test_years_quarters_forms_and_small_counts_pass(conn, policy):  # "three reasons", "FY2025", "the 10-K", "Q3", "2026"
def test_the_cite_parser_reads_separators_and_minus_signs():
    assert parse_cite("$1,234.50") == (1234.5, "$") and parse_cite("−3.2%") == (-3.2, "%") and parse_cite("(12.3%)") == (-12.3, "%")
def test_findings_are_located():  # where == "section 1, part 3: $12.345"
```

`tests/reports/test_refs.py`: one test per ref form, plus `same_snapshot` on a reprice (true) and a revalue (false). `tests/reports/test_render.py`: the Markdown holds the header line, the ten headings, "Appendix A" and "Appendix B"; `appendix_b` lists only the terms used; `test_the_glossary_matches_the_method_document` (every term of `docs/method.md` section 13's table is a `GLOSSARY` key, read from the repository file). `tests/store/test_reports.py`: revisions count up per symbol; judgments round trip. `tests/test_method_doc.py`: `test_section_16_names_the_six_failures`. `tests/web/test_reports_api.py`: `test_a_clean_submission_publishes_and_completes_the_item`, `test_a_rejection_stores_nothing_but_the_ledger_row` (422 with findings; `GET .../reports` still empty; the ledger has a `report` row with summary "rejected: 2 findings"), `test_a_review_mode_has_eight_sections`, `test_an_unknown_stance_is_refused`, `test_the_required_judgments`, `test_markdown_download` (`text/markdown`, the header line names AAPL, the mode, the actor and revision 1), `test_a_second_submission_is_revision_two`, `test_kill_criteria_and_news_items_are_stored_with_the_report`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/reports tests/store/test_reports.py tests/web/test_reports_api.py -q`
Expected: FAIL with import errors.

- [ ] **Step 3: Implement**

`refs.py`: one parser for the ref forms, one reader per form. `check.py`: the token rule as a regular expression plus the exclusions; `check_sections` walks the parts. `render.py`: Markdown with the cited numbers as text. The route: the structural checks, then `check_sections`; on no findings, `insert_report`, `insert_judgments`, the kill criteria and news items, `complete_item` when `workItemId` is given, the ledger row; on findings, the ledger row and 422. `reviews_api`'s derivations switch to `resolve`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md`**

Section 16: the ref forms (13.2), the six failures and the token rule (13.3), the rounding, the reprice rule, the derivations (13.4), the tables (13.5).

- [ ] **Step 6: Commit**

```bash
git add src/fairband/reports src/fairband/store/reports.py src/fairband/web docs/method.md tests
git commit -m "Publish a report only when every number resolves, with the six failures named and located"
```

### Task 8: The vendor pass-throughs

**Files:**
- Create: `src/fairband/refresh/passthrough.py`, `src/fairband/web/vendor_api.py`
- Modify: `src/fairband/vendors/fmp.py:125-135` (four methods), `src/fairband/vendors/http.py:143-160` (`limiter: RateLimiter | None = None`), `src/fairband/refresh/clients.py:21-40` (`limiter` passed through), `src/fairband/__main__.py:118-150` (`_serve` builds one `RateLimiter` for the worker's runs and the pass-through), `src/fairband/web/app.py` (`create_app(..., passthrough: Passthrough | None = None)`; the module docstring's vendor rule amended: the pass-through routes call the vendor on FastAPI's sync-route thread through the shared limiter, and no answer carries a key)
- Test: `tests/refresh/test_passthrough.py`, `tests/web/test_vendor_api.py`, `tests/vendors/test_fmp.py`

**Interfaces:**
- Produces, `fairband.vendors.fmp.Fmp`: `transcript(symbol, year: int, quarter: int)`, `news(symbol, limit: int)`, `segments_product(symbol)`, `segments_geographic(symbol)`, `insider_trades(symbol)`, each a `VendorResponse` over the stable API's route the builder confirms at build time (the registry names: `earning-call-transcript`, `news/stock`, `revenue-product-segmentation`, `revenue-geographic-segmentation`, `insider-trading/search`).
- Produces, `fairband.refresh.passthrough`: `KINDS = ("transcript", "news", "segments", "insider-trades")`; `Passthrough(fmp: Fmp, conn_factory, policy, clock, secrets)`; `fetch(kind: str, symbol: str, params: Mapping[str, str]) -> tuple[ResponseRow, Any]` (the stored response inside `policy.refresh.reuse_hours` when one exists, else the call, scrubbed with `scrub` and stored with `record_response`; `segments` makes two calls and returns both payloads under `product` and `geographic`; a `VendorError` raises through).
- Produces, routes: `GET /api/vendor/{kind}/{symbol}?year=&quarter=&limit=` → `{responseId, observedAt, reused: bool, payload}` (503 "no FMP key" without a pass-through; 502 with the vendor's sentence on a `VendorError`; 400 on an unknown kind or a missing parameter).
- Produces: `build_clients(keys, policy, *, transport=None, limiter: RateLimiter | None = None)`; `VendorHttp(..., limiter=None)` uses the given limiter in place of its own.

- [ ] **Step 1: Write the failing tests**

`tests/vendors/test_fmp.py`: the four methods' routes and parameters on the vendor double. `tests/refresh/test_passthrough.py` on `refresh_env`: `test_a_transcript_is_fetched_stored_and_reused` (two calls, one vendor hit, `reused` true the second time, the stored `endpoint` and `symbol`), `test_segments_fetch_two_endpoints`, `test_a_shared_limiter_paces_both_clients` (the worker's client and the pass-through's share one `RateLimiter`: `totals()` counts both). `tests/web/test_vendor_api.py`: `test_no_passthrough_is_503`, `test_an_unknown_kind_is_400`, `test_a_transcript_over_the_api` (the double's payload comes back with `responseId`), `test_no_key_in_the_answer` (the key string of the double is absent from the body).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/vendors/test_fmp.py tests/refresh/test_passthrough.py tests/web/test_vendor_api.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

As the Interfaces say; `_serve` builds `limiter = RateLimiter(policy.refresh.fmp_calls_per_minute, utcnow, time.sleep)` once (a changed pace setting reaches the pass-through at the next start; the worker's runs read the effective policy as today and share the limiter object).

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband tests
git commit -m "Fetch transcripts, news, segments and insider trades on request through the shared limiter, stored for citation"
```

### Task 9: The MCP server, the command and the README

**Files:**
- Create: `src/fairband/mcp/__init__.py`, `src/fairband/mcp/client.py`, `src/fairband/mcp/server.py`
- Modify: `pyproject.toml` (`mcp>=2.3.0` under `dependencies`; `[project.scripts] fairband = "fairband.__main__:main"`; `uv lock`), `src/fairband/__main__.py` (the `mcp` command with `--port`), `README.md` (the MCP registration for Claude Code, Claude Desktop and Codex; the playbook's install, Task 10)
- Test: `tests/mcp/test_client.py`, `tests/mcp/test_server.py`, `tests/test_cli_mcp.py`

**Interfaces:**
- Produces, `fairband.mcp.client`: `NOT_RUNNING = "the Fairband server is not running: start `uv run fairband serve`"`; `FairbandClient(http: httpx.Client)` (the caller builds the client with `base_url` `http://127.0.0.1:<port>`; tests pass a `TestClient`); `identify(agent: str, client_name: str, client_version: str)`; `get(path, params=None) -> Any`, `post(path, body) -> Any`, `patch(path, body) -> Any`, `delete(path, body) -> Any` (each sends `X-Fairband-Request: 1` and, after `identify`, the three identity headers; a connection error raises `ServerDown(NOT_RUNNING)`; a 4xx or 5xx raises `Refused(status, detail)` with the API's `detail` sentence); `identified: bool`.
- Produces, `fairband.mcp.server`: `TOOL_NAMES: tuple[str, ...]` (every tool of spec 15.2 to 15.4, `financial_tables` and `refresh_status` included); `build_server(client: FairbandClient) -> FastMCP` (one tool per name, each a one-sentence description, each returning the API's JSON or, on `Refused`, `{"refused": detail}` and on `ServerDown`, `{"refused": NOT_RUNNING}`; a write tool before `identify` returns `{"refused": IDENTIFY_FIRST}` without calling the server); `main(port: int) -> None` runs stdio.
- Produces: `uv run fairband mcp --port 8470` and `uv run python -m fairband mcp`.

- [ ] **Step 1: Write the failing tests**

`tests/mcp/test_client.py` with a `TestClient` of the web app: `test_get_and_post_carry_the_request_header`, `test_identify_adds_the_identity_headers`, `test_a_refusal_carries_the_detail` (a 409 from the inbox → `Refused(409, "an item for AAPL is open")`), `test_a_connection_error_is_server_down` (an `httpx.Client` on a closed port). `tests/mcp/test_server.py`: `test_every_spec_tool_is_registered` (`TOOL_NAMES` against the server's tool list), `test_a_write_before_identify_is_refused`, `test_inbox_list_calls_the_api` (through the SDK's in-process call path, `await server.call_tool("inbox_list", {})` or the tool manager's equivalent in 2.3.0; if the SDK offers none, call the wrapped functions, which `build_server` exposes as `server.tools[name]`), `test_report_submit_passes_the_sections_through`, `test_server_down_is_one_sentence`. `tests/test_cli_mcp.py`: `parse_args(["mcp", "--port", "9000"])`; the console script entry in `pyproject.toml`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/mcp tests/test_cli_mcp.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`uv add mcp`; the client over httpx; the server with `FastMCP("fairband")` and a decorator per tool, the arguments typed as spec 15 names them; `_mcp` in `__main__` builds the client on `http://127.0.0.1:<port>` and runs `main`. The README gains a section "Agents over MCP": the registration lines (`claude mcp add fairband -- uv run --directory <repo> fairband mcp`; the Desktop config JSON; the Codex `config.toml` entry), the identity rule, and the playbook's install.

- [ ] **Step 4: Run the suite and the server by hand**

Run: `uv run pytest -q`, then with the web server running `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}' | uv run fairband mcp`
Expected: PASS; the server answers the initialize request on stdout.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/fairband/mcp src/fairband/__main__.py README.md tests
git commit -m "Serve Fairband's tools to an agent over MCP as a stdio adapter over the web API"
```

### Task 10: The playbook

**Files:**
- Create: `playbook/fairband-research/SKILL.md`, `playbook/fairband-research/reference/tools.md`, `reference/citations.md`, `reference/report-template.md`, `reference/register.md`
- Test: `tests/test_playbook.py`

**Interfaces:**
- Produces: the skill in the Agent Skills format: frontmatter `name: fairband-research`, `description` one sentence; the eleven steps of spec 14 in order with the tool names; the rules of spec 14; `reference/tools.md` listing every `TOOL_NAMES` entry with its arguments and one line; `reference/citations.md` with the ref forms of spec 13.2, the six failures and the token rule in the agent's terms; `reference/report-template.md` with the ten sections, their headings in design.md 9.3's order, the summary page's shape (design.md 9.6), and a cited part's JSON shape; `reference/register.md` with design.md 9.2's rules and the brand book's words.

- [ ] **Step 1: Write the failing test**

`tests/test_playbook.py`: `test_the_skill_names_every_tool` (every `TOOL_NAMES` entry appears in `SKILL.md` or `reference/tools.md`), `test_the_skill_has_the_frontmatter_and_the_eleven_steps` (`name: fairband-research`; the numbered steps 1 to 11 each naming the tool spec 14 gives it), `test_the_citation_reference_names_the_six_failures`.

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: FAIL.

- [ ] **Step 3: Write the playbook**

In the register of design.md 9.2 and the brand book; the steps as spec 14 lists them; the rules as its last paragraph states them; the report template's section 4 written from `financial_tables`' cells.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add playbook tests/test_playbook.py
git commit -m "Add the research playbook as a skill the agent host installs"
```

### Task 11: Merge, the first live session and the readout

**Files:**
- Modify: `docs/backlog.md` (the Done rows for B-48, B-49, B-50, B-51, B-52, B-53, B-54, B-55, B-56, B-57, B-58, B-97's agent side; B-59's Markdown export; B-9 stays in Now for plan 2)

- [ ] **Step 1: The whole-branch review and the fix wave**

As every plan: the final review, one fix wave, one scoped re-review; `uv run pytest -q` green.

- [ ] **Step 2: Merge and back up**

`superpowers:finishing-a-development-branch`; the live database backed up as `fairband-before-v8-<date>.db` before the server restarts from main; `uv run fairband migrate`; the server restarted on 8470.

- [ ] **Step 3: Register and install**

`claude mcp add fairband -- uv run --directory <repo> fairband mcp`; the playbook linked under `~/.claude/skills/fairband-research`; `identify` answers in a Claude Code session.

- [ ] **Step 4: The first live session**

Post one `full report` item over MCP for a Mature Growth company the founder names; run the playbook in Claude Code; keep the session's transcript path in the scratchpad.

- [ ] **Step 5: The readout**

Spec 22's first list: the company; the mechanical and reviewed values and the bridge; the stance; the number of findings and the report's length; the ledger's rows by kind and the actor on each; the log's first row; the draft the check rejected and the findings it named (if the first draft published clean, say so).

- [ ] **Step 6: Close the backlog and commit**

```bash
git add docs/backlog.md
git commit -m "Close the agent-side items of Tier 2 in the backlog with the first live session's readout"
```
