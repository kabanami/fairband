# The Agents' Tools and Cites Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `derive` takes a fixed number from a list the server holds; a kill criterion can store a threshold that a report cites; a finding, a guidance record and a threshold carry the currency the company states; a stored filing report is reused without a time limit; and the debt rows of the tools close.

**Architecture:** One migration (008) adds a nullable `currency` to `findings`, `guidance` and `kill_criteria`, and `threshold` and `unit` to `kill_criteria`. A small store module holds the currency rule and the reporting currency of a company. The resolver (`reports/refs.py`) gains the operand form `number:`, the ref form `kill:` and a currency on a resolved record; `derive` (`web/reviews_api.py`) and the number check (`reports/check.py`) read them. The page and the export write a record's money in its own currency. The playbook follows in one task.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite; plain JavaScript with React from the design-system bundle; pytest, with node for the page's own script (`tests/web/page.mjs`).

**Spec:** `docs/superpowers/specs/2026-11-15-tools-and-cites-design.md`. Read it with your task: this plan argues from it, and where the two differ the spec wins. A map of the code as it stood before Task 1, with files and lines, is at `/tmp/claude-1000/-home-kaban-workspace-fairband/941bce1d-7722-449c-bac8-0ac2be879850/scratchpad/theme5-map.md`; it saves reading, and the code is the authority.

## Global Constraints

- No file under `src/fairband/engine/` changes. Under `src/fairband/refresh/` only `passthrough.py` changes (Task 6), and under `src/fairband/policy/` only the loader's check of range names (Task 7). No value, level, flag, snapshot or review moves. The method stays `fairband-mechanical/1.5`, the policy v16.
- One migration, `src/fairband/store/migrations/008_record_currency.sql`, written whole in Task 2 and not edited after it: a migration is recorded with its checksum.
- Every record, derivation and report on file reads as it did. A null `currency` means the reporting currency; a kill criterion with no threshold is as today.
- No failure word is added: `check.CHECKS` and `check.FAILURES` keep their members, so Appendix A's "Checks that ran" is unchanged on every report.
- An answer an agent meets today keeps its status and its words, but for the four of spec 12.1 (clauses 1, 3, 6 and 7).
- The reporting currency of a record with no stored currency is one function's answer everywhere it is needed outside a report's Appendix A: `fairband.store.currency.reporting_currency` (Task 2).
- A tool's signature line in `playbook/fairband-research/reference/tools.md` changes in the same commit as the tool in `src/fairband/mcp/server.py` (`tests/test_playbook.py` compares them). The playbook's prose is Task 8's.
- Never print, log, store or commit a key. Never commit vendor data: fixtures are synthetic.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, then a blank line, then these two lines in this order, the second naming the model that wrote the change:
  `Claude-Session: https://claude.ai/code/session_01K4pNFGb6uWekaVUA4NgJbB`
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- `docs/method.md` changes in the same commit as the code it describes; each paragraph of it is one line; a changed sentence is pinned in `tests/test_method_doc.py` as its neighbours are.

## Review Focus

Five conditions the spec implies and a hurried build would miss. Each has its test in the task that owns the code.

1. **A row written before the migration.** A finding, a guidance record and a kill criterion with null in every new column read, resolve, are cited and are described in a references list exactly as before (Tasks 2, 3, 4).
2. **A company with no snapshot.** Its reporting currency is USD; `finding_add`, `findings`, `kill_criterion_add` and `kill_criteria` answer, and nothing raises (Tasks 2, 3).
3. **A record in another currency on a US company.** A EUR finding of a company that reports in US dollars takes no `$`, has no value with a `fact:` total, and reads "EUR" in the drawer (Tasks 4, 5).
4. **A number where arithmetic breaks.** `ratio` of a figure over `number:0` has no value, as any division by zero; `number:1` as both operands is refused; a nested derivation built on a number keeps the unit the table of spec 7.2 gives (Task 1).
5. **A cite that outlives its record's state.** A published report that cites `kill:<id>` keeps its references words after the criterion is retired or triggered; a `kill:` cite outside "Risks and kill criteria" is an unresolved reference in both report modes (Task 3).

---

### Task 1: A fixed number in `derive`, growth from a base at or below zero, the snapshot test (spec 7.1 to 7.4)

**Files:**
- Modify: `src/fairband/reports/refs.py`, `src/fairband/web/reviews_api.py`, `src/fairband/reports/check.py`, `src/fairband/mcp/server.py` (the `derive` tool's description), `docs/method.md` (16.2, 16.3, 16.4)
- Test: `tests/web/test_secondary_api.py` (where the derivation route's tests live), `tests/reports/test_refs.py`, `tests/reports/test_check.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: `reviews_api._operand`, `_derived`, `_product_unit`; `refs.rests_on`; `check._cite_failure`.
- Produces, in `src/fairband/reports/refs.py`:

```python
NUMBER_FORM = "number"
NUMBERS: frozenset[int]  # 0 to 12, 52, 100, 365 and 10**k for k in 3..12

def fixed_number(ref: str) -> int | None: ...
    # the number `number:<n>` names: digits alone, in NUMBERS; None for any other text

def snapshots_of(conn: sqlite3.Connection, ref: str) -> frozenset[int]: ...
    # every snapshot the ref rests on; for `derived:`, those of every operand, nested ones too
```

  `rests_on` keeps its answer (`cited_records` and `Resolver._derived` read it). `Resolver.resolve("number:100")` is `None`.
- The refusals of `POST /api/companies/{symbol}/derivations`, each a 400 that stores none of the call:
  - `a fixed number is one of 0 to 12, 52, 100, 365 or a power of ten up to 1,000,000,000,000, not <the text after "number:">`
  - `a derivation needs a stored figure` (both operands numbers)
- The unit of a derivation with a number: spec 7.2's table. Where the stored figure has no unit the result has none.
- `growth` and `cagr` give `(None, None)` where `b` is at or below zero.
- The check: a `number:` cite is `UNRESOLVED` with the detail `<ref> is an operand of derive: cite the derivation`; the snapshot test of a `derived:` cite fails on the first snapshot of `snapshots_of` that is not the same as the latest, with today's words.
- The references list writes a number operand without its prefix, with separators: `derivation 7: the product of filing:3/BS/2/0 and 1,000,000`.

- [ ] **Step 1: Write the failing tests.** In `tests/web/test_secondary_api.py`: each of `number:0`, `number:1`, `number:12`, `number:52`, `number:100`, `number:365`, `number:1000`, `number:1000000000000` computes; `number:13`, `number:1.5`, `number:1e6`, `number:1,000`, `number:-1`, `number:` and `number:10000000000000` answer the first 400 with their own text and store nothing, also when an earlier derivation of the same call was valid; two numbers answer the second 400. The unit table row by row: `difference` of `number:1` and a percent is a percent with the value 1 − x; `sum` and `product` of a figure a share and a number are figures a share; `ratio` of a total over `number:2` is a total; `ratio` of `number:1` over a multiple has no unit; `growth` and `cagr` are percents; `product` of a figure with no unit and `number:1000000` has no unit. `ratio` of a figure over `number:0` has no value. A figure over itself still gives `(1.0, "multiple")`. A nested derivation of a derivation built on a number resolves. `growth` and `cagr` over a base of zero and of −100 have no value; over a positive base they are as before.
  In `tests/reports/test_refs.py`: `fixed_number` on each case above; `resolve("number:100")` is `None`; the references words of a derivation with a number; `snapshots_of` a derivation whose second operand, and one whose nested operand, rests on another snapshot holds both ids.
  In `tests/reports/test_check.py`: a `number:` cite is an unresolved reference with its detail; a `derived:` cite whose second operand rests on an older snapshot fails `wrong snapshot`, one whose nested operand does also fails, one whose operands all rest on the latest passes.
- [ ] **Step 2: Run them and see them fail.** `uv run pytest -q tests/web/test_secondary_api.py tests/reports/test_refs.py tests/reports/test_check.py`.
- [ ] **Step 3: Implement.** The number is read where an operand is read, before the resolver; `_derived` takes the fact that an operand is a number and applies the table.
- [ ] **Step 4: The documents.** Method 16.2 gains the operand form `number:` (an operand of `derive` alone), 16.3 the number cite's refusal and the snapshot test of every operand, 16.4 the list, the two refusals, the unit table and the base at or below zero. The `derive` tool's description names the form in one clause. Pin each in `tests/test_method_doc.py`.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 2: Migration 008 and a currency on a finding and a guidance record (spec 9.1, 9.2)

**Files:**
- Create: `src/fairband/store/migrations/008_record_currency.sql`, `src/fairband/store/currency.py`
- Modify: `src/fairband/store/research.py`, `src/fairband/store/guidance.py`, `src/fairband/web/agents_api.py`, `src/fairband/web/guidance_api.py`, `src/fairband/web/research_api.py`, `src/fairband/mcp/server.py`, `playbook/fairband-research/reference/tools.md` (two signature lines), `docs/method.md` (14.9, 16.2)
- Test: `tests/store/test_db.py`, `tests/store/test_research.py`, `tests/store/test_guidance.py`, `tests/web/test_agents_api.py`, `tests/web/test_guidance_api.py`, `tests/web/test_research_api.py`, `tests/mcp/test_server.py`, `tests/test_method_doc.py`

**Interfaces:**
- Produces, the migration, whole:

```sql
ALTER TABLE findings ADD COLUMN currency TEXT;       -- NULL: the company's reporting currency
ALTER TABLE guidance ADD COLUMN currency TEXT;       -- NULL: the company's reporting currency
ALTER TABLE kill_criteria ADD COLUMN threshold TEXT; -- a number the author chose, or NULL
ALTER TABLE kill_criteria ADD COLUMN unit TEXT;      -- the threshold's unit; with it or NULL
ALTER TABLE kill_criteria ADD COLUMN currency TEXT;  -- NULL: the company's reporting currency
```

- Produces, in `src/fairband/store/currency.py`:

```python
MONEY_UNITS: frozenset[str]  # {"currency", "per-share"}

def check_currency(currency: str | None, unit: str | None) -> None: ...
    # ValueError "a currency is three capital letters, not <repr>" for a malformed code;
    # ValueError "a currency goes with a money figure" where unit is not in MONEY_UNITS

def reporting_currency(conn: sqlite3.Connection, symbol: str) -> str: ...
    # the latest snapshot's currency as engine.types.money_of reads it; "USD" with no snapshot

def currency_of(stored: str | None, unit: str | None, reporting: str) -> str | None: ...
    # a money figure's currency: the stored code, else `reporting`; None where unit is not money
```

- Produces: `FindingRow.currency: str | None = None` and `GuidanceRow.currency: str | None = None`, the stored code, the last field of each; `add_finding(..., currency: str | None = None)`; `insert_guidance(..., base_actual, *, currency: str | None = None, base_currency: str | None = None)`, which stores no step where `currency` is given and is not `base_currency`. A guidance record's unit for the rule is `guidance.UNITS[metric]`. The key by which a record supersedes another is unchanged.
- Produces: `FindingPost.currency` and `GuidancePost.currency`, each `str | None = None`. The route of guidance passes `base_currency`, the currency of the statements the base actual is read from. Every answer of a finding and of a guidance record (the two routes' posts and reads, and the company read's research block in `research_api.py`) carries `currency`: `currency_of(stored, unit, reporting_currency(conn, symbol))`.
- Produces: `finding_add(..., currency: str | None = None)` and `guidance_add(..., currency: str | None = None)` in the MCP server, with their lines in `tools.md`.

- [ ] **Step 1: Write the failing tests.** The migration on a store that holds a finding, a guidance record and a kill criterion written under 007: each row reads with its fields as before and `currency` null; `schema_versions` gains 008. Store: a finding with `currency="USD"` and unit `currency` reads back; with unit `percent`, or with no value, raises "a currency goes with a money figure"; `"usd"`, `"US"` and `"DOLLAR"` raise the form's refusal. Guidance: `revenue` and `eps` take a currency, `operating_margin` refuses one; a record with `currency="USD"` and `base_currency="TWD"` has no step and one with `currency=None` keeps its step; a `USD` record supersedes the current record with no currency of the same metric, period and basis. `reporting_currency`: a company with no snapshot is `USD`; a company whose latest snapshot names `SEK` is `SEK`. Routes: the posts answer `currency`; the reads answer the reporting currency for a money figure with none stored and null for a percent; a company with no snapshot answers. MCP: the two tools send `currency`. The research block of the company read carries `currency` on each finding and guidance record.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: The documents.** Method 14.9: a record with a stored currency that is not the currency of its base actual takes no step. Method 16.2: a finding and a guidance record may name their currency; none means the reporting currency. Pin both. `tools.md`: the two signature lines only.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 3: A threshold on a kill criterion and the `kill:` ref (spec 8.1, 8.2)

**Files:**
- Modify: `src/fairband/store/research.py`, `src/fairband/web/agents_api.py`, `src/fairband/mcp/server.py`, `src/fairband/reports/refs.py`, `src/fairband/reports/check.py`, `src/fairband/web/reviews_api.py` (`_operand`), `playbook/fairband-research/reference/tools.md` (one signature line), `docs/method.md` (16.2, 16.3)
- Test: `tests/store/test_research.py`, `tests/web/test_agents_api.py`, `tests/mcp/test_server.py`, `tests/reports/test_refs.py`, `tests/reports/test_check.py`, `tests/web/test_secondary_api.py`, `tests/web/test_reports_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: the columns of migration 008; `check_currency`, `currency_of`, `reporting_currency` (Task 2).
- Produces: `KillCriterionRow.threshold: float | None = None`, `.unit: Unit | None = None`, `.currency: str | None = None`, its last three fields; `add_kill_criterion(conn, symbol, text, writer, at, report_id=None, *, threshold=None, unit=None, currency=None)`. Refusals, each a `ValueError`: `a kill criterion's threshold and unit come together`; the unit's as a finding's (`a unit is one of ..., not <repr>`); `a kill criterion's threshold is a finite number`; the currency's (Task 2).
- Produces: `KillCriterionPost` with `threshold`, `unit`, `currency`, each optional; the criterion's JSON carries `threshold`, `unit` and `currency` (`currency_of`). `kill_criterion_add(symbol, text, threshold=None, unit=None, currency=None)` in the MCP server, with its line in `tools.md`. A report's `killCriteria` list is unchanged: text alone.
- Produces, in `refs.py`: the form `kill`: `kill:<id>` resolves to `Resolved(threshold, unit, None, None)` for a criterion of the company that holds a threshold, in any state; `None` otherwise. `describe`: `kill criterion <id>, a threshold the author chose`.
- Produces, in `check.py`: a `kill:` cite in a section whose heading is not `HEADINGS[10]` ("Risks and kill criteria") is `UNRESOLVED` with the detail `<ref> is the author's own threshold: cite it in Risks and kill criteria`. In that section it is checked as a `finding:` cite is.
- Produces, in `reviews_api.py`: an operand `kill:<id>` answers 400 `unresolved reference: kill:<id>`.

- [ ] **Step 1: Write the failing tests.** Store: a criterion with a threshold and unit reads back; a threshold alone, a unit alone, an unknown unit and a non-finite number each raise; a criterion with none is as today. Route and MCP: the post takes the three and answers them; `kill_criteria` lists them; a company with no snapshot answers. Refs: `kill:<id>` resolves open, triggered and retired; a criterion with no threshold and one of another company name nothing; the words of `describe`. Check, on a full report and on a valuation review: a `kill:` cite of 5% written `5%` passes in "Risks and kill criteria" and is an unresolved reference with the detail in the Summary and in Valuation; `5.5%` on a threshold of 5% fails as a finding's would; `len(check.CHECKS)` and `check.FAILURES` are what they were. Derive: a `kill:` operand is the 400. Reports API: a report that cites a `kill:` threshold in section 11 publishes, its references list holds the words, and they stay after the criterion is retired.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: The documents.** Method 16.2: the form `kill:` and its words in the references. Method 16.3: the section rule, an unresolved reference elsewhere, no arithmetic. Pin both. `tools.md`: the signature line only.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 4: The currency in the resolver, `derive` and the check (spec 9.3, 9.4)

**Files:**
- Modify: `src/fairband/reports/refs.py`, `src/fairband/web/reviews_api.py`, `src/fairband/reports/check.py`, `docs/method.md` (16.2, 16.3, 16.4)
- Test: `tests/reports/test_refs.py`, `tests/web/test_secondary_api.py`, `tests/reports/test_check.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: `currency_of`, `reporting_currency`, `MONEY_UNITS` (Task 2); `Resolver._kill` (Task 3).
- Produces: `Resolved.currency: str | None = None`. It is set for a `finding:`, a `guidance:` (its low, high and midpoint, not its step) and a `kill:` money figure, to `currency_of(stored, unit, reporting_currency(conn, symbol))`; `None` for every other ref.
- Produces, in `reviews_api.py`, with "a record in another currency" meaning an operand whose `Resolved.currency` is set and is not the reporting currency:
  1. no value where one operand is such a record and the other has a unit in `MONEY_UNITS` and is not a record in that same currency;
  2. where an operand is such a record, a result unit in `MONEY_UNITS` becomes none.
- Produces, in `check.py`: for a cite whose `Resolved.currency` is set, a `$` passes only where it is `USD`; otherwise `wrong unit` with the detail `<ref> reads <CODE> <number>: write the number without $ and name <CODE> before it`. `shown(value, unit, currency=None)` writes `<CODE> 1,000,000,000` for a total and `<CODE> 12.50` for a figure a share where `currency` is given and is not `USD`; with `USD` or none it writes as today.

- [ ] **Step 1: Write the failing tests.** Refs: `Resolved.currency` of a finding with a stored `USD` on a company whose snapshot names `SEK` is `USD`; of one with none, `SEK`; of a percent finding, `None`; of a guidance midpoint as its record's; of a guidance step, `None`; of a `fact:` total, `None`. Derive, on that company: `growth` of two `USD` findings is a percent; their `ratio` a multiple; their `sum` has a value and no unit; a `USD` finding times `snapshot:<id>/inputs/fx_rate` has a value and no unit, and that derivation's `growth` over a `fact:` total is a percent; a `USD` finding with a `fact:` total, in `ratio`, `growth` and `sum`, has no value; a `USD` finding with a finding with no stored currency has no value; two findings with no stored currency are as today. On a company that reports in US dollars: a `EUR` finding with a `fact:` total has no value; two `USD` findings are as today. Check: `$` on a `USD` finding of the `SEK` company passes; `$` on a finding with no stored currency of that company fails `wrong unit` with `SEK` in the detail; the same bare number passes; on a US company `$` on a finding passes as before and `$` on a `EUR` finding fails; a `fact:` cite of the `SEK` company with `$` is as today.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: The documents.** Method 16.2: a resolved record carries its currency. 16.3: the `$` rule is checked for a record and stays the playbook's for other refs. 16.4: the two rules of a record in another currency. Pin each.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 5: The currency on the page and in the export (spec 9.5)

**Files:**
- Modify: `src/fairband/reports/render.py` (`_guidance`, the export's "Guidance on file"), `src/fairband/web/static/app.js` (`guidanceTable`, the Findings block), `src/fairband/web/static/report.js` if its call needs it, `docs/method.md` (16.6)
- Test: `tests/reports/test_render.py`, `tests/web/test_drawer_currency.py`, `tests/web/test_report_reader.py`, `tests/web/test_reports_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: the `currency` each finding and guidance record carries in the company read (Task 2); `currency_of` (Task 2).
- Produces: each item of Appendix A's `guidance` gains `"currency"`: `currency_of(record.currency, guidance.UNITS[record.metric], <the report's snapshot's currency>)`. The export's table has the header `Guidance, Metric, Period, Low, High, Midpoint, Currency, Basis, Call, State, Cited by`, the currency cell empty for a percent metric.
- Produces, on the page: `guidanceTable(guidance, code)` writes each record in `g.currency || code`; the Findings block writes each finding in `f.currency || code`. The functions keep their names and arguments.

- [ ] **Step 1: Write the failing tests.** Render: a report of a company whose snapshot names `SEK`, with one guidance record with no stored currency, one with `USD` and one of `operating_margin`: the payload's three currencies are `SEK`, `USD`, null, and the export's table holds the column with `SEK`, `USD` and an empty cell. A report of a US company has `USD`. Node tests through `tests/web/page.mjs`: the guidance table writes `$` on the `USD` record and `SEK` on the other; the Findings block writes a `USD` finding with `$` and one with no currency with `SEK`; a US company's drawer is as before, and its `EUR` finding reads with `EUR`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: The documents.** Method 16.6: the guidance table's currency on the page and its column in the export. Pin it.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 6: One stored copy of a filing report, and the segments' newest year (spec 10, 11)

**Files:**
- Modify: `src/fairband/refresh/passthrough.py`, `src/fairband/web/vendor_api.py`, `docs/method.md` (16.8, and the paragraph that describes the `segments` read)
- Test: `tests/refresh/test_passthrough.py`, `tests/web/test_filings_api.py`, `tests/web/test_vendor_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Produces: a `filing-report` call reuses the newest usable stored copy whatever its age; an unusable copy is never reused; `sec-filings` and `filing-report-dates` keep `reuse_hours`. The module's docstring says so.
- Produces: each of `responses.product` and `responses.geographic` in the `segments` answer gains `newestYear: int | None`, the largest `fiscalYear` among the payload's rows that hold a whole number there; null for a payload with none or one that is not a list.

- [ ] **Step 1: Write the failing tests.** Passthrough: a filing report stored 31 days and 400 days before the clock is reused and no vendor call is made; one stored with an error is fetched again; a filing list stored 25 hours before is fetched again. Vendor API: `newestYear` on a product split whose rows end in 2025 and a geographic split whose rows end in 2023; null for an empty list.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: The documents.** Method 16.8: a filing report is reused without a limit and nothing is deleted. The `segments` paragraph: `newestYear`. Pin both.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 7: The debt of B-103 and B-105 (spec 12.1, 12.2)

One implementer, nine small changes of one kind and one test cleanup. Each has its own test.

**Files:**
- Modify: `src/fairband/store/research.py` or `src/fairband/web/agents_api.py` (clause 1), `src/fairband/store/inbox.py` and `agents_api.py` (clause 2), `agents_api.py` (clause 3), `src/fairband/web/identity.py` (clause 4), `src/fairband/web/reports_api.py` (clauses 6, 7, 8), `src/fairband/reports/tables.py` (clause 9), `src/fairband/policy/__init__.py` or where the builder puts the check (clause 10), `tests/test_playbook.py` (B-105), `playbook/fairband-research/reference/tools.md` where it names `fmpCounted` or one of the changed answers, `docs/method.md` where it states one of them
- Test: `tests/web/test_agents_api.py`, `tests/store/test_inbox.py`, `tests/web/test_identity.py`, `tests/web/test_company_reads.py`, `tests/reports/test_tables.py`, `tests/policy/`, `tests/mcp/test_server.py` where a status is pinned

**The changes (spec 12.1's numbers):**
1. `PATCH /api/kill-criteria/{id}` to the state the criterion is in answers 409 with today's words, `kill criterion <id> is already <state>`.
2. `post_expiry_items` writes the ledger rows the route writes today; the route stops; the rows on file after a call are the same.
3. `POST /api/inbox/claim` with no body claims the next item, as `{}` does.
4. A blank or whitespace client header is stored as null.
6. `/estimates`, `/price-history` and `/peers` answer 404 for a symbol with no snapshot, with the status and words `GET /api/companies/{symbol}` gives such a symbol; a company with a snapshot and no rows of the read's kind answers 200 with empty lists.
7. `fmpCounted` leaves the `peers` answer.
8. `/financial-tables` passes the statements it read to `financial_tables` (`stated=`).
9. The newest aggregate ROIC cell of the financial tables carries the note `over <n> years` where the engine's aggregate holds fewer than ten usable years; with ten it carries none.
10. A policy whose ranges name a tag the engine does not know is refused when it is loaded; tests for that refusal and for the two refusals of a malformed range ("does not ascend", "is not a table of ranges").
- B-105: `tests/test_playbook.py` drops the two assertions of its fourth test that `structure_refusal` makes (the twelve headings in order; the judgments' set and uniqueness).

- [ ] **Step 1: Write the failing tests**, one for each change that moves an answer or a stored value (1, 2 as "the same rows", 3, 4, 6, 7, 9, 10).
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.** For 10, `engine.overrides` imports the policy package: use a local import or check where both are known; say which in the report.
- [ ] **Step 4: The documents.** Method and `tools.md` where they state a changed answer. Pin what changes.
- [ ] **Step 5: Run the four commands and commit.**

---

### Task 8: The playbook (spec 7.5, 8.3, 9.6, 11, 12.2, 12.3) and method 14.7

**Files:**
- Modify: `playbook/fairband-research/SKILL.md`, `reference/tools.md`, `reference/citations.md`, `reference/report-template.md`, `reference/register.md`, `docs/method.md` (14.7)
- Test: `tests/test_playbook.py`, `tests/test_method_doc.py`

**What changes, each pinned by a substring test as the file's other rules are:**
- **A fixed number** (spec 7.5): `tools.md`'s `derive` entry gives the form, the list and the unit table; `SKILL.md` and `citations.md` give the recipes (a complement, an average, a change of sign, a cell of a sheet in millions scaled with `number:1000000` before it meets a `fact:` figure, a PEG as two ratios) and the rule that a number is arithmetic, never a figure the agent chose. The rule "do not `derive` a cell with a figure in full units" becomes "scale the cell first"; a finding in full units is no longer the way to compute with a cell.
- **A threshold** (spec 8.3): `citations.md`'s passage on a chosen threshold, the template's section 11 row and the failures table: a threshold the agent chooses goes on the kill criterion with `kill_criterion_add` before the report is written, is cited by `kill:<id>` in "Risks and kill criteria" alone, enters no arithmetic and is left out of the report's `killCriteria` list; an event tied to a stored figure is still the better criterion where one serves. The template's example gains one such criterion. The sentence "a stored threshold on a kill criterion is a later piece of Fairband" goes.
- **A currency** (spec 9.6): one rule in `SKILL.md`, `citations.md` and `tools.md`: record a money figure in the currency the company states it in and pass `currency` when that is not the reporting currency; `$` for a US-dollar figure, the code in the plain text before a bare cite otherwise; convert with `product` and `snapshot:<id>/inputs/fx_rate` before setting an input from it or comparing it with a statement; a figure in a third currency enters no arithmetic with the company's figures. The words "in the reporting currency as the company states it" go.
- **The tools** (spec 11): the `segments` entry names `newestYear`, and `SKILL.md` sends the agent to the 10-K's segment note (`filing_search`, `filing_report`) where a split's newest year is before the newest fiscal year; the call section says that where no close is on file for the trading day after the call, the report states no move and says the close is not on file yet. The filing report's entry says a stored copy is reused without a limit.
- **The debt** (spec 12.2, 12.3): the register's "Means" on snapshot, news item and work item takes the brand book's words (`tar -xzOf docs/design-system/fairband-design-system_4.tar.gz fairband-design-system/docs/brand-book.md`); "the sales class" is explained at its first use; `citations.md` says a figure from a secondary analysis names that source in its finding and the report says the filing was not read; `SKILL.md` says to read a filing's text on the company's investor site where sec.gov refuses a fetch; `tools.md`'s `review_log` entry and method 14.7 say the stance is the one in force when the review was written, none before a company's first report.

- [ ] **Step 1: Write the failing pins** in `tests/test_playbook.py` and `tests/test_method_doc.py`.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Write the words**, in the playbook's register, each line within the file's width where the file is pinned for it.
- [ ] **Step 4: Run the four commands and commit.**

---

### Task 9: The whole-branch review, the acceptance, the live step and the backlog (spec 13, 16)

The controller's.

- [ ] **Step 1: The whole-branch review and its one fix wave.**
- [ ] **Step 2: The acceptance on a copy** (spec 16): a copy of the live database by SQLite's backup API; `fairband migrate` on it; the branch's server on another port with no vendor key; every report's page reads and export answer 200; each export against main's differs only in the "Guidance on file" table; the records read as before; the three writes of spec 16.4.
- [ ] **Step 3: The founder's word**, with the readout of step 2.
- [ ] **Step 4: The live step.** A backup; the merge and the push; the migration; the server's restart from main on 8470. No revalue.
- [ ] **Step 5: The backlog and the readout.** B-99, B-161, B-167, B-103, B-105, B-142, B-117 and B-118 to Done with their commits; new rows for spec 14 and the ledger's parked items; the readout in the spec's decision log and the research round's. Remove the worktree and the workspace; tell the founder that every research session must restart its MCP process.
