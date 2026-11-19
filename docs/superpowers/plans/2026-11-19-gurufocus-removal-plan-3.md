# GuruFocus Removal, Plan 3: The Moat Table, and GuruFocus Out

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fairband reads each company's moat class from its own table, which the owner and an agent
can change and which values the company again at once; then GuruFocus leaves the code.

**Architecture:** A packaged TOML file holds a class for every company. A stage of every refresh
that values loads it into the table `moat_classes`, where the owner's and an agent's rows keep
priority. Assembly reads the row; the engine refuses a company without one. One route,
`PUT /api/companies/{symbol}/moat`, serves the page and the agent's `moat_set`, and revalues the
company inside the request. A script runs the drafting rule; the engine never does.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, tomllib; plain JavaScript with React from the
design-system bundle; pytest, with node for the page's scripts (`tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-19-gurufocus-removal-design.md`, section 8, bound by
sections 3, 4, 5 (points 1 to 4) and 9 to 14; the decisions in `docs/gurufocus-removal.md`, section
6. Where the plan and the spec differ, the spec wins; reopen no decision. The look: `moat.mjs` in
`docs/superpowers/specs/2026-11-19-gurufocus-removal-mockup/`; translate from it, import nothing.

**A map of the code as it stands** (after plans 1 and 2: method 1.7, policy v17, schema 009, 54
tools; named by function, since those plans moved lines):

- Models: `policy/tax.py` and `tests/policy/test_tax.py`; `scripts/build_tax_table.py` (`_string`);
  `tests/policy/test_inflation.py::_script`, a script loaded by path.
- Engine: `CompanyInputs.moat_score`; `anchor.moat_class`; `route_steps.common_inputs` (DATA
  `moat_score`) and `common_rules` (RULE `moat_class`); Decline reads `moat_class(...)` without
  `chosen`; Decline and Start-up write their own `moat_class`; `overrides.current_reading` reads a
  RULE note only (`_rule_note`).
- Refresh: `inputs.build_inputs` (`gf-score`);
  `run.Refresh(conn_factory, fmp, gf, policy, tax, clock, cancel, ...)` and `_value_stage`;
  `fetch.py` (provider `gf`); `clients.py`; `config.Keys.gurufocus`.
- Store, web, page: `db.transaction` joins the caller's; `refreshes.create_refresh` raises
  `RefreshRunning`; `reviews_api.Evidence`, `require_current`; `check.STRUCTURE` (five);
  `refs.same_snapshot`; `agents_api.gist`; `mcp/client.py` has no `put`; `app.js` `moatStamp`,
  `notesControl`, `openNotes`, `notesBox`.

## Global Constraints

- Work in a git worktree: the live server on 8470 serves the main checkout's page files.
- Test first: a failing test, then the code, then the passing run, then the commit.
- Before every commit:
  `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`. A
  commit of documents alone runs `CLAUDE.md`'s shorter check.
- A commit message is one plain sentence in the imperative, then a blank line, then
  `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- No test uses the network; fixtures are synthetic; never commit vendor data; never print, log,
  store or commit a key.
- Nothing under `~/.local/share/fairband/` is committed; the reference database is never written.
- The moat file holds tickers, classes, dates and the decision document's reasons, and no vendor
  figure beyond those.
- `docs/method.md` and the Methodology page change in the same commit as the engine, classifier or
  policy change they describe.
- Method 1.8 in Task 6, policy v18 in Task 7, schema 010 in Task 4, and nowhere else.
- GuruFocus keeps working until Task 12, after the engine reads the table (Task 6).
- A migration, once applied, is never edited.
- Every dispatched subagent runs on Opus 5.5 at xhigh effort.
- Every word on a page and every refusal comes from the Words table; a changed word is a spec
  change.
- The live steps need the founder's consent, asked once with the list; nothing is pushed without it.

## Words

Rows marked *plan* hold sentences the spec leaves to the builder (spec 14).

| Where | Words |
|---|---|
| The engine's refusal | `no moat class` |
| The write's refusals | 400 `a moat verdict needs a reason`; 400 `a moat verdict needs evidence`; 409 `a refresh is running: set the class when it ends`; 404 `no snapshot for <symbol>`; *plan*: 403 `returning to Fairband's class is the owner's`; 404 `the moat table holds no class for <symbol>` |
| An override of the tag | `moat.class is the moat table's: record the verdict with moat_set` |
| The report's check | `the report needs the moat verdict recorded on snapshot <id>: call moat_set`; *plan*: in `STRUCTURE`, `the moat verdict on the snapshot` |
| The secondary valuation | `set the moat class first: moat_set` |
| The migration's drop | `moved to the moat table` |
| The ledger, kind `moat` | `moat Narrow → Wide: <the reason's gist>`; `moat Narrow → Wide` without a reason; *plan*: `moat Wide: <gist>` with no class before it; `moat Wide → Narrow: Fairband's class` for the owner's return |
| The input `moat_class` | sources `moat table fairband-moat-v1`, `owner`, `agent claude-opus-5-5`; notes `Wide`, `Wide: <reason>` |
| The stamp | `WIDE MOAT`, `NARROW MOAT`, `NO MOAT`; `MOAT NOT SET`, dashed |
| The chip | `◆ Owner`, `◆ Agent claude-opus-5-5`; *plan*: its `reason` prop `19 Nov 2026: <reason>`, or `19 Nov 2026`, which the bundle's title writes after `Written by you — ` |
| The control | `Change ▾`; `Set ▾` |
| The box | `Fairband's class, table version 1, judged 19 Nov 2026.`; `Your class since 19 Nov 2026. Before: Narrow.` (no `Before:` without a class before it); *plan*, an agent's: its chip, then `since 19 Nov 2026. Before: Narrow.`; the reason under the line; `None`, `Narrow`, `Wide`; `Reason (optional)`; `Set moat class`; `Use Fairband's class (Narrow)` |
| The Methodology page's moat (*plan*) | `Fairband keeps its own table of moat classes, one for each company. A rule on ten years of returns drafted it, and the table corrects the rule by hand where it is wrong. You may change a company's class on its page, and an agent records its own in each review. The newest class is in force, and the company is valued again at once.` |
| The Methodology page, the rest (*plan*) | the examples' row `Moat, from the moat table`; the agents' section: `An agent may change twenty-four inputs by an override, such as the phase and the belief, each within set bounds.` and `The moat class is not one: an agent records its verdict, with its reasons, in each review.` |
| The decision document, CRM's kept row | `A ROIC of 5% over ten years and 7% over five, after large purchases. Its review of 2026-11-10 confirmed GuruFocus's Wide before the moat was a standing step of a review.` |
| `CLAUDE.md`, the brand-book line | `An owner's moat class is saved without a reason (the founder, 2026-11-19).` |

## Review Focus

1. **A ticker with a dot** (`BF.B`, `MOG.A`, `PBR.A`): the file, `PUT`/`DELETE`
   `/api/companies/BF.B/moat`, `moat_set` and the page reach it (Tasks 8, 10, 11).
2. **A company with no row** (an entrant): `MOAT NOT SET`, `Set ▾`, no return; the write has no
   class before it, the ledger reads `moat Wide`, the company is valued; `DELETE` is 404 (Tasks 8,
   11).
3. **A reason with `"`, `\`, an accented letter or a line break** round-trips through the TOML
   writer and the reader (Task 2).
4. **A reason of spaces**: the owner's is stored as none, no `: ` in the note or the ledger; an
   agent's is a 400 (Task 8).
5. **The script on a snapshot refused `no moat class`**: its revenue is assembly's trailing revenue
   ÷ its rate; one refused before its route for another reason has none (Task 2).

---

### Task 1: The moat file's reader (spec 8.1)

**Files:** Create `src/fairband/policy/moat.py`, `tests/policy/test_moat.py`.

**Interfaces:**
- Produces, in `policy/moat.py`:

```python
MOAT_FILE = "moat-classes-v1.toml"
@dataclass(frozen=True)
class MoatEntry:   # rule_class, reason, decided_by: a correction's; note, decided_by: a kept entry's
    symbol: str; moat: Moat; judged: date; source: Literal["rule", "correction"]
    rule_class: Moat | None = None; reason: str | None = None
    decided_by: str | None = None; note: str | None = None
@dataclass(frozen=True)
class MoatTable:
    version: str; date: date; universe: str; rule: str
    entries: Mapping[str, MoatEntry]   # by symbol, in the file's order
def load_moat_table(path: Path | None = None) -> MoatTable   # default: the packaged MOAT_FILE
```

- [ ] **Step 1: Write the failing tests** on files under `tmp_path` in spec 8.1's layout:

```python
def test_a_file_loads_its_meta_and_its_entries(tmp_path)  # the four meta fields; entries in order
def test_a_correction_and_a_kept_entry(tmp_path)          # SMCI's three fields; SONY's note
@pytest.mark.parametrize(("entries", "message"), [
    (TWICE, "AAPL appears twice"),
    (MEDIUM, "AAPL class 'Medium' is not Wide, Narrow or None"),
    (NO_REASON, "SMCI is a correction without reason"),  # likewise rule_class, decided_by
    (RULE_WITH_RULE_CLASS, "AAPL is the rule's class and holds rule_class"),  # likewise reason
    (GUESS, "AAPL source 'guess' is not rule or correction"),
])
def test_a_malformed_file_is_refused(tmp_path, entries, message)   # ValueError
def test_a_judged_that_is_not_a_date_is_refused(tmp_path)          # TypeError, "AAPL judged"
```

- [ ] **Step 2: Run them** (`uv run pytest tests/policy/test_moat.py -q`: `ModuleNotFoundError`),
      **then write the reader** as `tax.py` is written: messages start `moat table: `; a `[meta]`
      missing a field is refused by name. No test reads the packaged default before Task 3.
- [ ] **Step 3: Run the full check; commit:** "Read the moat table's packaged file and refuse a
      malformed one".

### Task 2: The drafting rule and its script (spec 8.2; Review Focus 3, 5)

**Files:** Create `src/fairband/policy/moat_rule.py`, `scripts/build_moat_table.py`,
`tests/policy/test_moat_rule.py`, `tests/policy/test_moat_script.py`.

**Interfaces:**
- Produces, in `policy/moat_rule.py`, pure, importing neither the store nor the engine:

```python
CYCLICAL: frozenset[str]   # the run's 24 FMP industry names, then Aluminum, Silver, Uranium
@dataclass(frozen=True)
class ReturnYear:
    nopat: float; capital: float          # capital: the year's average invested capital
@dataclass(frozen=True)
class MoatFacts:
    symbol: str; industry: str; sector: str; phase: str | None   # the latest snapshot's phase
    years: tuple[ReturnYear, ...]         # the last ten the engine keeps, oldest first
    revenue_usd: float | None; fiscal_revenues: tuple[float | None, ...]
    gross_margins: tuple[float, ...]
def gross_margins(payload: object) -> tuple[float, ...]
def draft_classes(companies: Sequence[MoatFacts]) -> dict[str, Moat]
```

- Produces, in `scripts/build_moat_table.py` (each command opens `--database` with `mode=ro`):

```python
def read_facts(conn: sqlite3.Connection) -> list[MoatFacts]
def snapshot_revenue(result: ValuationResult, assemble: Callable[[], CompanyInputs]) -> float | None
def parse_log(text: str) -> tuple[dict[str, Correction], dict[str, Kept]]
    # Correction(symbol, rule_class, moat, reason, decided_by); Kept(symbol, moat, note, decided_by)
def first_version(classes, corrections, kept, judged, version, cut, universe) -> MoatTable
def new_version(current, drafted, today, version, universe) -> MoatTable
def yearly_read(current, drafted) -> list[tuple[str, Moat, Moat]]   # symbol, file's, rule's
def render(table: MoatTable) -> str
# first --database DB --log docs/gurufocus-removal.md --judged 2026-11-19 --out TOML
# new --database DB --current TOML --version V --out TOML     (prints those drafted)
# read --database DB --current TOML                           (prints yearly_read)
```

**The rule as it ran** (method 4.9a; `points2.py`, `repair.py`, `final.py` of the research folder):
- A return: NOPAT ÷ capital; capital at or below zero gives `inf` with NOPAT above zero, else
  `-inf`; the ten-year total likewise on the sums; the median, `statistics.median` of the last five.
  A loss year: NOPAT at or below zero. Fewer than ten years: `len(years) < 10`.
- Growth over the fiscal revenues neither `None` nor 0: `(newest / tenth newest) ** (1 / 9) - 1`;
  none with fewer than ten, or when either end is not above zero.
- The group: the industry when it counts five companies with a revenue or more, else its sector's
  industries under five, together. The rank: by revenue, largest first, among the group's companies
  with one; a tie by symbol, A first.
- The marks: size, revenue of 50e9 or more; leader, rank 1 or 2; growth, revenue of 12e9 or more and
  growth of 0.10 or more; steady, ten margins, `min >= 0.8 * median`.
- The order: fewer than ten years, Narrow; Start-up, Young Growth or High Growth, Narrow; total and
  median below 0.03, None; Decline, Narrow; at most one loss year, none in the last five, total and
  median above 0.09, and two marks or more, or total and median above 0.20 with the steady mark:
  Wide, but Narrow on `CYCLICAL`; else Narrow. Names compare exactly.
- `gross_margins`: `()` for a payload that is not a non-empty list; the rows by `date`, the last
  ten; a row counts where `grossProfit` is an `int` or `float` and `revenue` a number not 0.

**What the script reads**, as the run did: `latest_companies(conn)`, each row's industry and sector
(`""` when missing); each `latest_snapshot`, its phase; `today`, their newest `data_date`;
`build_inputs(conn, symbol, effective_policy(conn), load_tax_table(), today, latest_deciles(conn))`,
then `aggregate_roic(inputs.capital_years).by_year[-10:]` and `inputs.series` (an exception: no
years, no revenues, a line on stderr); the revenue by `snapshot_revenue`: the `revenue_ttm` input ÷
the `fx_rate` input where one is, `None` without `revenue_ttm`, and on `no moat class`
`assemble()`'s trailing revenue ÷ its rate; the margins from the newest of the three newest FMP
`income-annual` answers by `observed_at` with no error and a non-empty list. From Task 6 on,
`build_inputs` reads the table, so the script needs a database at schema 010.

- [ ] **Step 1: Write the failing tests of the rule**, on `facts(symbol, **changes)`, a Wide default
      (ten years at 25%, steady, $60 billion, Mature Stable, an industry of five):

```python
def test_too_few_years_or_a_young_phase_is_narrow()   # nine years at 1%; each young phase at 1%
def test_none_needs_both_below_three_percent()        # 2.9% and 2.9%: None; a total of 3.0%: Narrow
def test_decline_is_none_or_narrow()                  # 1%: None; the Wide default: Narrow
def test_the_scale_route()                            # size and steady: Wide; size alone: Narrow; 50e9 and 49.9e9; 12e9 at 10.0% growth
def test_the_return_route()                           # $1bn, 21% and 21%, steady: Wide; 20%: Narrow
def test_the_conditions()                             # two losses; one in the last five; 9.5%, 9.0%
def test_a_year_without_capital()                     # profit: above any bar; loss: below any bar
def test_the_list()                                   # Steel: Narrow; 1% in Steel: None; Chemicals - Specialty: Wide; 27 names, no "Oil & Gas Energy"
def test_the_group_and_the_rank()                     # five, four, a company without revenue, a tie
def test_growth_and_the_margins()                     # ten revenues, both ends; twelve statements; one without grossProfit; the 80% edge
```

- [ ] **Step 2: Run them; then write `moat_rule.py`**, its docstring naming the run's readings. Run:
      PASS.
- [ ] **Step 3: Write the failing tests of the script**, loaded by path:

```python
def test_parse_log_reads_the_decision_document():
    corrections, kept = script.parse_log(DECISION.read_text(encoding="utf-8"))
    assert len(corrections) == 74 and len(kept) == 15 and "BF.B" in kept
    assert Counter((c.rule_class, c.moat) for c in corrections.values()) == {
        ("Wide", "None"): 5, ("Wide", "Narrow"): 28, ("Narrow", "Wide"): 25,
        ("Narrow", "None"): 1, ("None", "Narrow"): 15}
def test_first_version_applies_the_log_and_refuses_one_the_rule_does_not_bear_out()
def test_new_version_and_the_yearly_read()    # entries kept; the rest judged today; rule entries alone
def test_a_reason_round_trips(tmp_path)       # Review Focus 3
def test_the_snapshot_s_revenue()             # Review Focus 5: a rate; USD; none; "no moat class"
```

- [ ] **Step 4: Run them; then write the script.** `render` writes `[meta]` and one `[[classes]]` an
      entry by symbol, strings by `json.dumps(..., ensure_ascii=False)`; each command loads its
      output back through `load_moat_table`. Run the full check; commit: "Write the rule that drafts
      the moat table as a pure function, and its read-only script".

### Task 3: The first file (spec 8.1, 10; section 5, point 1)

**Files:** Modify `docs/gurufocus-removal.md` (CRM's kept row in 6.7). Create
`src/fairband/policy/moat-classes-v1.toml`, and `accept_plan3_rule.py` in the research folder,
`~/.local/share/fairband/research/gurufocus-removal-2026-11-19/`. Test `tests/policy/test_moat.py`.

- [ ] **Step 1: Correct CRM's sentence** in the decision document by the Words table, so the file
      copies it.
- [ ] **Step 2: Write the failing tests** of the packaged file:

```python
def test_refresh_68_s_companies_take_the_corrected_classes():
    first = [e for e in load_moat_table().entries.values() if e.judged == date(2026, 11, 19)]
    assert len(first) == 1558
    assert Counter(e.moat for e in first) == {"Wide": 162, "Narrow": 1320, "None": 76}
    assert sum(e.source == "correction" for e in first) == 74
    assert sum(e.note is not None for e in first) == 15
def test_every_reason_and_note_is_the_decision_document_s()   # each verbatim in the document
def test_the_entries_the_spec_names()       # SMCI, TTMI, NVO, RELX, SONY; CRM's new note
def test_the_meta_and_the_later_entries()   # "fairband-moat-v1"; every later entry the rule's
```

- [ ] **Step 3: Run them** (no file), **then draft on the reference database `REF`:**

```
uv run python scripts/build_moat_table.py first --database REF --log docs/gurufocus-removal.md \
    --judged 2026-11-19 --out <research>/moat-ref.toml
```

- [ ] **Step 4: The rule's acceptance.** `accept_plan3_rule.py` (`uv run python -I`) compares the
      rule classes of `moat-ref.toml` (`rule_class`, else `class`) with `final_class.pkl`. Pass: the
      same class on all 1,558; 170, 1,303 and 85, and 169, 1,138 and 56 on the 1,363 valued at
      refresh 68; with the corrections 162, 1,320 and 76, and 161, 1,155 and 47. A miss is Task 2's
      defect.
- [ ] **Step 5: Cut the version on the live database**, read-only, keeping the printed list for Task
      13. `[meta]`: today; "the universe of the full refresh of <date>, <n> companies", the live
      database's latest.

```
uv run python scripts/build_moat_table.py new --database ~/.local/share/fairband/fairband.db \
    --current <research>/moat-ref.toml --version fairband-moat-v1 \
    --out src/fairband/policy/moat-classes-v1.toml
```

- [ ] **Step 6: Run the full check; commit:** "Cut the first moat table from the rule's draft with
      the decision document's 74 corrections and 15 notes, correcting CRM's sentence there".

### Task 4: Migration 010 and the store's rows (spec 8.3, 8.4)

**Files:** Create `src/fairband/store/migrations/010_moat_classes.sql`,
`src/fairband/store/moat.py`, `tests/store/test_moat_store.py`. Modify
`src/fairband/store/refreshes.py` (its docstring's "the only rows the store updates"). Test
`tests/store/test_db.py` (`_ALL`, `applied_versions` to 10).

**Interfaces:**
- Produces, in `store/moat.py` (each write joins the caller's transaction):

```python
type MoatSource = Literal["file", "owner", "agent"]
@dataclass(frozen=True)
class MoatRow:   # spec 8.3's columns
    symbol: str; moat: Moat; source: MoatSource; file_version: str | None; judged_on: date
    previous: Moat | None; reason: str | None; evidence: tuple[dict[str, str], ...] | None
    principal: Principal; actor: str | None; client: str | None; at: datetime
    snapshot_id: int | None
@dataclass(frozen=True)
class Loaded:
    written: int; replaced: int; deleted: int
def moat_row(conn: sqlite3.Connection, symbol: str) -> MoatRow | None
def set_moat(conn, symbol: str, moat: Moat, writer: Writer, reason: str | None,
             evidence: Sequence[Mapping[str, str]] | None, at: datetime) -> MoatRow
    # judged_on: at's UTC day; previous: the class in force or None; a system writer: ValueError
def file_moat(conn, symbol: str, table: MoatTable, at: datetime) -> MoatRow
    # source "file", principal "system", previous None; KeyError without an entry
def set_snapshot(conn, symbol: str, snapshot_id: int) -> None
def load_moat_file(conn, table: MoatTable, at: datetime) -> Loaded
```

- [ ] **Step 1: Write the failing tests:**

```python
def test_migration_010_moves_the_applied_moat_overrides(tmp_path, monkeypatch, conn)
    # at 009: TTMI's moat.class applied (new "None", old "Narrow"), one dropped, one refused, another
    # tag applied. After 010: one agent row, None, previous Narrow, the override's reason, evidence,
    # actor, client and at, judged_on its day, no snapshot; that override dropped, "moved to the moat
    # table", a dropped_at load_stamp reads; the others as they were
def test_the_load_writes_replaces_and_deletes_file_rows(conn)   # each of spec 8.4's three cases
def test_the_load_never_touches_a_local_row(conn)               # owner's and agent's, a new version
def test_a_load_that_changes_nothing_writes_nothing(conn)       # Loaded(0, 0, 0); every at as it was
def test_set_moat_and_file_moat(conn)                           # previous; None without a row; KeyError
```

- [ ] **Step 2: Run them; then write the migration:** spec 8.3's table; one `INSERT ... SELECT` from
      `overrides` where `tag = 'moat.class' AND state = 'applied'` (`json_extract(new, '$')`,
      `json_extract(old, '$')`, `substr(at, 1, 10)`); one `UPDATE` of those rows to `dropped` with
      the drop reason and `dropped_at = strftime('%Y-%m-%dT%H:%M:%f', 'now') || '+00:00'`. No ledger
      row.
- [ ] **Step 3: Write `store/moat.py`;** the load reads every row once and writes the differences in
      one transaction. Run the full check; commit: "Add the moat table with migration 010, moving
      each applied moat.class override into its agent's row".

### Task 5: The `moat` stage and a revalue that names companies (spec 8.4, 8.6)

**Files:** Modify `src/fairband/refresh/run.py`, `src/fairband/__main__.py`,
`src/fairband/mcp/server.py` (`refresh_start`'s description), `docs/method.md` (10). Create
`tests/support/moat.py`. Test `tests/refresh/test_run_revalue.py`, `test_run.py`,
`test_run_full.py`, `refresh_env.py`; `tests/web/test_refresh_api.py`.

**Interfaces:**
- Produces:
  - `Refresh(..., close=None, moat: MoatTable | None = None)`, the packaged file by default; the
    stage `moat` first in `_value_stage`, so before every value stage, after a 429 too.
  - `Refresh.run("revalue", symbols)`: those alone, the record naming them, no calibration (as a
    scoped refresh).
  - In `run.py`, on the caller's transaction: `record_policy`, a `revalue` record naming the symbol
    (`RefreshRunning` while one runs), the stage `moat`, the symbol's work shared with
    `_value_stage`, `finish_refresh` `done`; an exception rises:

```python
def revalue_company(conn: sqlite3.Connection, symbol: str, policy: Policy, tax: TaxTable,
                    moat: MoatTable, clock: Callable[[], datetime]) -> int   # the snapshot's id
def moat_table(classes: Mapping[str, Moat], *, version: str = "fairband-moat-v1",
               judged: date = date(2026, 11, 19)) -> MoatTable   # tests/support/moat.py
```

Every test that builds a `Refresh` passes `moat_table(...)` with the classes the GuruFocus fixtures
give (ACME's score 7, Narrow; no score, None), so no expected figure moves here or in Task 6.

- [ ] **Step 1: Write the failing tests:**

```python
def test_every_refresh_that_values_loads_the_moat_file_first(env_valued)
    # full, scoped, revalue: "backfill", "moat", "value", "done"; a file row per company of the table
def test_a_revalue_that_names_companies_values_those_alone(env_valued):
    refresh_id = env.refresh().run("revalue", ["KRON", "ACME"])
    assert env.items(refresh_id) == [("KRON", "valued", None), ("ACME", "valued", None)]
    assert env.last().symbols == ("KRON", "ACME") and env.last().calibration is None
def test_revalue_company(env_valued)    # one record, stages moat and value, one snapshot, no call; a review follows it; RefreshRunning while a refresh runs
def test_cli_revalue_with_symbols(...)  # "refresh ACME --kind revalue" exits 0
```

`POST /api/refresh` with `{"kind": "revalue", "symbols": ["ACME"]}` answers the id; the pins of "a
revalue takes no symbols" go.
- [ ] **Step 2: Run them; then change the runner, the command and the tool.** `method.md` 10: a
      revalue may name companies and values those alone; every refresh that values reads the
      packaged moat file into the table (4.9) after its backfill.
- [ ] **Step 3: Run the full check; commit:** "Load the moat file into its table before every value
      stage, and let a revalue name its companies".

### Task 6: The engine reads the table, under method 1.8 (spec 8.5)

**Files:** Modify `src/fairband/engine/route.py`, `route_steps.py`, the five `route_*.py`,
`anchor.py`, `overrides.py`, `__init__.py`; `src/fairband/refresh/inputs.py`; `docs/method.md` (2,
4.9, 4.9a, 5.1, 5.12, 6b.1, 9, 11, the head); `docs/method-overview.md`;
`src/fairband/web/static/methodology.html`. Test `tests/engine/test_route.py`,
`test_route_start_up.py`, `test_route_decline.py`, `test_overrides.py`, `test_anchor.py`,
`test_golden.py` with `tests/fixtures/golden/`; `tests/support/engine_companies.py`;
`tests/refresh/test_inputs.py`; `tests/reports/test_refs.py`; `tests/test_method_doc.py`;
`tests/web/test_methodology.py`; what `grep -rn "mechanical/1.7" src tests docs/method*.md` finds.

**Interfaces:**
- Produces:
  - `CompanyInputs.moat_class: Moat | None` in `moat_score`'s place;
    `CompanyInputs.moat_judged: bool = False`, true for an owner's or agent's row;
    `provenance["moat_class"]` and `notes["moat_class"]` by spec 8.5's table
    (`Provenance("moat table fairband-moat-v1", entry day, None, row at)`, or `"owner"`,
    `"agent <actor>"` as of the write's day; the word, or `"<word>: <reason>"`).
  - `with_table_moat(conn, inputs: CompanyInputs) -> CompanyInputs` in `refresh/inputs.py`:
    `build_inputs` ends with it; a test's fake may call it.
  - `NO_MOAT_CLASS = "no moat class"` in `route.py`; in `route_steps.py`, `table_moat(i) -> Moat`
    (`AssertionError` with no class) and `moat_input(i) -> TaggedInput` (`moat_class`, value `None`,
    unit `class`; RULE, kind `rule`, or JUDGMENT, kind `judgment`).
  - `METHOD_VERSION == "fairband-mechanical/1.8"`; `anchor.moat_class` and the DATA input
    `moat_score` go.

The guard follows `no diluted share count`: a Start-up row meets it right before its route, every
other row after `no trailing figures`. Past it, `value_company` hands `_refuse` and `_valued`
`moat_input(inputs)`, after `_base_inputs`; a result refused before it has none. The routes read
`chosen(c, "moat.class", table_moat(i))`, Decline `table_moat(i)`; their own `moat_class` entries
go. `current_reading(result, "moat.class")`: `im["moat"]`, else the word leading the `moat_class`
input's note, whatever its tag.

- [ ] **Step 1: Write the failing tests:**

```python
def test_a_row_without_a_class_is_refused_after_the_data_guards():
    no = replace(ms_inputs, moat_class=None)
    assert value_company(no, deciles, policy, TODAY).refusal == "no moat class"
    assert value_company(replace(no, price=None), deciles, policy, TODAY).refusal == "no price"
    assert value_company(replace(no, trailing=None), ...).refusal == "no trailing figures"
    assert value_company(replace(start_up_inputs(), moat_class=None), ...).refusal == "no moat class"
def test_the_moat_input_names_its_source()   # spec 8.5's three rows; one such input on a valued result and on a route's refusal; none on "no price"
def test_the_decline_route_reads_the_table_s_class()      # Wide's margin of safety
def test_a_sensitivity_reading_still_varies_the_class()   # {"moat.class": "None"}: None's value, the JUDGMENT "moat.class", no "moat_class"
def test_the_moat_s_reading_whatever_its_tag()            # a Start-up result, the owner's "Wide: ..."
def test_assembly_reads_the_table_s_row()                 # file, owner, agent; no row: None
def test_a_ref_on_an_owner_s_moat_reads_its_word()        # inputs/moat_class: "Wide"
```

`engine_companies.py`: `moat_score=8.0` becomes `moat_class="Wide"`, `None` becomes `"None"`, with
the file's provenance and note; `test_route.py`'s `moat_score=policy.moat_narrow_min` becomes
`moat_class="Narrow"`.
- [ ] **Step 2: Run them; then change assembly, the guard, the input and the routes;** `moat_class`
      leaves `anchor.py` with its tests.
- [ ] **Step 3: Set `METHOD_VERSION` to 1.8,** change each literal copy, make the goldens again as
      `test_golden.py` says, and read the diff: `moat_score` leaves, `moat_class` cites the moat
      table, no figure moves. The goldens' README says so.
- [ ] **Step 4: `method.md`.** 4.9: spec 8.5's text. 4.9a: spec 8.2's, with Task 2's readings
      (growth "none with fewer than ten such years, or when either end is not above zero"; a tie in
      revenue ranks by symbol), the 27 names, semiconductors, size as revenue. 5.1, 6b.1, 9: the
      guard (`no moat class | 4.9, 5.1`). 5.12: the input's three forms. 2: no GuruFocus `summary`
      row. 12: the moat class's source is the founder's table (`docs/gurufocus-removal.md` 6).
      11: "1.8, policy v17 | <day> | The moat table (spec 2026-11-19 8) …".
      `test_method_doc.py`'s pin moves to the 1.8 row, the 1.7 row's to `rows[-2]`.
- [ ] **Step 5: The Methodology page** by the Words table: the moat's paragraph in place of the Moat
      Score's sentence and its two spans; the examples' rows; the agents' section; each sentence 25
      words or fewer. `method-overview.md`: the table's class, and 1.8. Run the full check; commit:
      "Value every company on its row of the moat table under method 1.8, refusing one without a
      row".

### Task 7: Policy v18 (spec 8.9, 7.4)

**Files:** Create `src/fairband/policy/fairband-policy-v18.toml`. Modify
`src/fairband/policy/__init__.py`, `settings.py`, `src/fairband/web/policy_rows.py`,
`src/fairband/refresh/fetch.py`, `docs/method.md` (4.1, 11). Test `tests/policy/test_policy.py`,
`test_settings.py`, `tests/web/test_settings_api.py`, `tests/store/test_settings_overlay.py`,
`tests/test_method_doc.py`.

**Interfaces:**
- Produces: `load_policy().version == "fairband-policy-v18"`; no `moat_wide_min`, `moat_narrow_min`,
  `RefreshPolicy.gf_reuse_days` or setting `refresh.gf_reuse_days`;
  `fetch._GF_REUSE = timedelta(days=7)` until Task 12.

- [ ] **Step 1: Write the failing tests:** `test_v18_is_the_packaged_policy`;
      `test_v18_is_v17_without_the_three_values` (`_file_values`: v17's less the three, the rest
      equal); `test_v17_holds_the_moat_thresholds` (8 and 4, read without the loader);
      `test_a_stored_gf_reuse_days_is_ignored_and_deleted` (plan 2's path). `test_settings.py`: one
      setting fewer, the last `refresh.reuse_hours`; `test_settings_api.py`: the two values leave
      its rows.
- [ ] **Step 2: Run them; then write v18,** a full copy of v17 less the three values; its
      comments and source lines name no GuruFocus call (v17's refresh lines count "2 GuruFocus
      calls" and name "GuruFocus's observation dates"); set `_POLICY_FILE`; remove the fields, the
      setting, its check and the two units; `fetch.py` takes `_GF_REUSE`.
- [ ] **Step 3: `method.md`.** 4.1 loses the moat-score row and the GuruFocus reuse row; 11 gains
      "1.8, policy v18 | <day> | The policy drops the Moat Score's two thresholds and GuruFocus's
      reuse window. The method is unchanged at 1.8: no value moves." The pins: `rows[-1]` the v18
      row, `rows[-2]` the 1.8 row. Run the full check; commit: "Drop the Moat Score's thresholds and
      GuruFocus's reuse window under policy v18".

### Task 8: The write and the reads (spec 8.6, 8.7; Review Focus 1, 2, 4)

**Files:** Create `src/fairband/web/moat_api.py`, `tests/web/test_moat_api.py`. Modify
`src/fairband/web/app.py`, `research_api.py` (`_moat`), `reviews_api.py` (`_moat`, the secondary
route), `tests/support/web_app.py`. Test `tests/web/test_research_api.py`,
`test_company_page_api.py`, `test_secondary_api.py`.

**Interfaces:**
- Produces:
  - `add_moat_routes(app, conn_factory, policy, tax, moat: MoatTable, clock) -> None`;
    `create_app(..., moat: MoatTable | None = None)`.
  - `PUT /api/companies/{symbol}/moat` `{"class", "reason"?, "evidence"?}` (`reviews_api.Evidence`;
    the field aliased `class`); `DELETE`, the owner's. Each answers
    `{"moatClass": ..., "snapshot": {"id", "value", "refusal"}}`.
  - `moat_json(row: MoatRow | None, table: MoatTable) -> dict[str, Any] | None`:
    `{"class", "source", "fileVersion", "judgedOn", "previous", "reason", "actor", "at",`
    `"fileClass"}`. The detail gains `moatClass`; its `moat` is the row's class, a refused row's
    too.
  - `research_api._moat(conn, symbol) -> str | None`;
    `reviews_api._moat(conn, symbol) -> Moat | None`.

The write, in one immediate transaction: `writer_of`; an agent's blank reason, then no evidence,
400; the owner's blank reason stored as `None`; no snapshot, 404; `current_refresh` running, 409;
`set_moat`;
`record(conn, writer, at, "moat", symbol, None, None, snapshot_id=<latest>, summary=...)`, the gist
by `agents_api.gist`; `revalue_company` under the effective policy; `set_snapshot`. `DELETE`: an
agent's, 403; no entry, 404; `file_moat`, its ledger row, `revalue_company`. An exception rolls it
all back. The secondary route's 400 comes right after `require_current`.

- [ ] **Step 1: Write the failing tests;** the app's table from `moat_table`, `run.build_inputs`
      patched to `with_table_moat(conn, <a fixture's inputs>)`, as
      `test_reviews_api.py::stored_inputs` does:

```python
def test_the_owner_sets_a_class(client)    # "owner", previous "Narrow"; "moat Narrow → Wide"; a revalue of AAPL;
                                           # its snapshot's moat_class JUDGMENT "owner" "Wide"; row.snapshot_id that snapshot
def test_an_agent_needs_a_reason_and_evidence(client)   # two 400s; nothing stored
def test_a_reason_of_spaces(client)                     # Review Focus 4
def test_the_other_refusals(client)                     # "Medium": 400; ZZZZ: 404; a running refresh: 409
def test_the_same_class_again_and_the_newest_write(client)   # the writer's row; the newest in force
def test_a_review_follows_the_new_snapshot(client)
def test_a_company_without_a_row(client)                # Review Focus 2
def test_the_owner_returns_to_the_file_and_an_agent_cannot(client)   # 200 "file"; 403
def test_a_dotted_symbol(client)                        # Review Focus 1
def test_the_write_calls_no_vendor(client)              # an app with no worker, no pass-through
def test_the_detail_carries_the_row(client)             # file; owner with fileClass; none; refused
def test_the_secondary_valuation_reads_the_row(client)  # no row: the 400, "share basis unclear" too; refused for its statements, Wide: Wide's levels
```

- [ ] **Step 2: Run them; then write `moat_api.py`, register it, change both `_moat` and the
      detail;** the detail's `moat` pins in `test_company_page_api.py` and `test_research_api.py`
      move to the row's class.
- [ ] **Step 3: Run the full check; commit:** "Let the owner and an agent set a company's moat
      class, valued again at once, and read it from the table".

### Task 9: `moat.class` is no override; the report's verdict (spec 8.7)

**Files:** Modify `src/fairband/engine/overrides.py`, `src/fairband/reports/check.py`,
`src/fairband/web/reports_api.py`, `docs/method.md` (14.2, 14.3, 16.3),
`playbook/fairband-research/reference/citations.md`. Test `tests/engine/test_overrides.py`,
`tests/web/test_reviews_api.py`, `test_sensitivity_api.py`, `test_reports_api.py`,
`tests/reports/test_check.py`, `tests/test_playbook.py`.

**Interfaces:**
- Produces: `MOAT_SET`; `check_override` answers `("refused-locked", MOAT_SET)` for the tag first,
  `check_input` as before. `STRUCTURE` gains `"the moat verdict on the snapshot"` before the
  secondary valuation's. `structure_refusal(..., snapshot_id, *, moat_on_snapshot: bool)`; `submit`
  passes whether the row is an agent's whose `snapshot_id` is the latest snapshot or one it reprices
  (`same_snapshot`).

- [ ] **Step 1: Write the failing tests:**

```python
def test_an_override_of_the_moat_is_refused_locked(policy):
    assert check_override("moat.class", "Wide", "mature-stable", policy, ["filing"], "lasting",
                          None) == ("refused-locked", MOAT_SET)
    assert check_input("moat.class", "Wide", "mature-stable", policy) == ("applied", "")
def test_the_override_route_stores_it_refused(client)    # 400; state "refused-locked"
def test_a_grid_still_varies_the_moat(client)            # return.runway × moat.class: 201
def test_a_stored_bridge_with_a_moat_line_still_reads(client)
def test_a_report_needs_the_agent_s_verdict(client)      # none, file, owner, an agent's on an older snapshot: 400; on the latest or repriced: passes
```

`test_check.py`'s `STRUCTURE` pin gains the name; `test_reports_api.py` gains an autouse fixture
that writes an agent's row on each latest snapshot.
- [ ] **Step 2: Run them; then write both refusals;** `citations.md` names the new check.
      `method.md`: 14.2's `moat.class` row, the class of 4.9, a sensitivity axis alone, set with
      `moat_set`; 14.3, the sentence among the locked; 16.3, six structural checks.
- [ ] **Step 3: Run the full check; commit:** "Refuse an override of moat.class, and a report
      without its agent's moat verdict on its snapshot".

### Task 10: `moat_set`, `company`'s `moatClass`, the playbook (spec 8.6, 8.9)

**Files:** Modify `src/fairband/mcp/server.py`, `client.py`; `playbook/fairband-research/SKILL.md`,
`reference/tools.md`; `docs/agents.md`, `README.md` (55 tools). Test `tests/mcp/test_server.py`,
`tests/test_playbook.py`.

**Interfaces:**
- Produces: `FairbandClient.put(path, body)`;
  `moat_set(symbol: str, moat_class: Moat, reason: str, evidence: list[dict[str, Any]])`
  `-> dict[str, Any]` before `override_add` in `TOOL_NAMES` (55), sending
  `{"class", "reason", "evidence": _camel(evidence)}`, described as "Record your verdict on the
  company's moat class, Wide, Narrow or None, with your reason and evidence, also when you agree
  with the class in force; the company is valued again at once."; `company`'s description names
  `moatClass`.

- [ ] **Step 1: Write the failing tests:** `len(TOOL_NAMES) == 55` and `moat_set` right before
      `override_add` in `SPEC_TOOLS`; `WRITES` gains `moat_set`; `test_moat_set_puts_the_verdict`
      (Review Focus 1: `PUT /api/companies/BF.B/moat`, the body); in `test_playbook.py`,
      `STEPS[10]` gains `moat_set`, `REFUSALS` gain `no moat class`, `MOAT_SET`, the report's and
      the secondary valuation's sentences and the write's 409, and
      `test_the_moat_is_a_standing_step_before_the_overrides`: step 10 names "brand name, switching
      costs, network effect, cost advantages and efficient scale", calls `moat_set` before
      `override_add`, records the verdict also when the agent agrees; the overrides table's
      `moat.class` row names `moat_set`.
- [ ] **Step 2: Run them; then write the tool, `put` and the playbook.** Step 10 opens with spec
      8.9's standing step, for a valuation review too: the five sources a guide, the agent's own
      judgment, `moat_set` with the reason and evidence, before any override, since it gives a new
      snapshot. The `moat.class` row: set through `moat_set`, its override refused, a grid may vary
      it. `no moat class` joins the refusals with its remedy; `tools.md` lists `moat_set` in the
      server's order. `docs/agents.md` and `README.md` count 55.
- [ ] **Step 3: Run the full check; commit:** "Give the agent moat_set and make the moat verdict a
      standing step of every review".

### Task 11: The control on the company page (spec 8.8, 9; Review Focus 1, 2)

**Files:** Modify `src/fairband/web/static/app.js`, `company.js`, `index.html`; `CLAUDE.md`. Create
`tests/web/test_moat_control.py`. Test `tests/web/test_company_page.py`, `test_drawer_form.py`,
`test_notes_control.py`, `tests/support/page_answers.py`.

**Interfaces:**
- Produces, through `FairbandPage`:
  - `moatStamp(body) -> element`: `label app-moat` with the words; `label app-moat app-moat--unset`,
    `MOAT NOT SET`, where `body.moat` is `null`.
  - `moatChip(body) -> element | null`: `F.PrincipalChip({principal, actor, compact: true, reason})`
    on an owner's or agent's row.
  - `moatControl(body, after) -> element`: quiet, small, `app-moat-open`, `Change ▾` or `Set ▾`;
    opens the box under it or closes its own.
  - `moatBox(box, ref) -> element`, `box = {symbol, row, pick, draft, error, posting}`, built as
    `notesBox` (`fb-menu fb-menu--filters app-moat-box`): the line, the reason, the classes
    (`app-fin__seg`, `aria-pressed`), the field, `Set moat class`, and the return on a local row
    with a `fileClass`. Its own classes start `app-moat`.
  - One box at a time: it closes Notes and the watchlists popup, `openNotes` closes it; a press or
    focus outside, or Escape, closes it, focus back on the control.

The page's head: stamp, chip, control after the phase badge (`.app-company__line`); the drawer:
stamp and chip. A set is `api.put` with `{class, reason}`, a blank reason left out; a return
`api.del`; then `after()`. A refusal's sentence stands under the buttons (`refusalDetail`).

- [ ] **Step 1: Write the failing tests** (node):

```python
def test_the_stamp_s_four_words()          # null: "MOAT NOT SET", "app-moat--unset"
def test_the_chip_by_whose_class_it_is()   # owner; agent and actor; none for a file row; reason "19 Nov 2026: Its brands keep rivals out."
def test_the_control_s_words()             # "Change ▾", "Set ▾"
def test_the_box_s_four_states()           # file, owner, agent, none: each line of the Words table, the class pressed, the return only on a local row
def test_the_set_and_the_return()          # PUT /api/companies/BF.B/moat {"class": "Wide"}; DELETE
def test_a_refusal_s_sentence_under_the_buttons()
def test_the_page_s_head_and_the_drawer_s()   # page: stamp, chip, control; drawer: no control
def test_the_unset_stamp_is_dashed()       # ".app-moat--unset {": "border-style: dashed;"
```

Pins that move: in `test_company_page.py`, `test_the_moat_stamp_s_three_words_and_none`,
`test_the_head_stamps_the_moat_in_force_and_none_on_a_refused_row` and `test_the_head_s_parts`; in
`test_drawer_form.py`, `test_the_moat_stamp_follows_the_phase_badge` and the refused row's
`classed(tree, "app-moat") == []`; in `test_notes_control.py`,
`test_the_box_opens_under_its_control_and_closes_as_the_popup_does` (`openNotes` closes the moat
box).
`page_answers.py`: `detail()` and `refused_detail()` gain a file row's `moatClass`; `unset_detail()`
has `moat` and `moatClass` `null`.
- [ ] **Step 2: Run them; then write the stamp, chip, control, box and CSS** as `moat.mjs`'s six
      states draw them; add the brand-book exception to `CLAUDE.md`.
- [ ] **Step 3: Run the full check; commit:** "Show whose moat class is in force on the company page
      and let the owner change it there".

### Task 12: GuruFocus out (spec 8.10)

**Files:** Delete `src/fairband/vendors/gurufocus.py`, `normalize_gf.py`,
`tests/vendors/test_gurufocus.py`, `tests/fixtures/gurufocus/`. Modify
`src/fairband/refresh/fetch.py`, `clients.py`, `run.py`, `inputs.py`, `passthrough.py` (what plan 1
left); `config.py`; `__main__.py`; `README.md`, `docs/agents.md`, `docs/method-overview.md`,
`docs/method.md` (2's 429 sentence, any line naming GuruFocus as a source; 11 stays). Test
`tests/refresh/vendor_double.py`, `refresh_env.py`, `conftest.py`, `synthetic.py`,
`fixture_universe.py`, `test_fetch.py`, `test_run.py`, `test_run_full.py`, `test_clients.py`;
`tests/support/vendor.py`; `tests/test_config.py`; web tests that build a `Refresh`.

**Interfaces:**
- Produces:
  `Refresh(conn_factory, fmp, policy, tax, clock, cancel, on_progress=None, secrets=(),`
  `close=None, moat=None)`;
  `fetch_company(conn, fmp, symbol, policy, now, secrets, force)`;
  `build_clients(keys, policy, ...) -> tuple[Fmp, tuple[str, ...]]`; `Keys(fmp)`;
  `Vendor = Literal["fmp"]`. Stored GuruFocus rows stay, unread.

- [ ] **Step 1: Write the failing tests:** `test_a_keys_file_with_a_gurufocus_line_loads`
      (`keys.fmp`; no log record); `test_a_full_refresh_makes_no_gurufocus_call` (with
      `FAIRBAND_GURUFOCUS_KEY` set and without: no request to its host);
      `test_the_fetch_has_no_gurufocus_endpoint`. The call counts in `test_run.py` and
      `test_run_full.py` lose two a company.
- [ ] **Step 2: Run them; then remove the code, fixtures, the doubles' host and token,** `_GF_REUSE`
      and `_PROVIDER_NAMES["gf"]`. The README asks for one key, its keys file holds one line, its
      diagram has no GuruFocus box. `grep -rilE "gurufocus|guru_focus" src/fairband` finds the
      policy files v1 to v17 alone, which stay byte for byte; no Python file and no page file.
- [ ] **Step 3: Run the full check; commit:** "Take GuruFocus out of Fairband: its client,
      normalizer, key and calls (B-261)".

### Task 13: Acceptance, the readout and the live steps (spec 10, 11, 12)

**Files:** Create `accept_plan3.py` in the research folder. Modify
`src/fairband/web/static/methodology.html`, `tests/web/test_methodology.py`,
`docs/gurufocus-removal.md` (the status), the spec's decision log, `docs/backlog.md`.

- [ ] **Step 1: The copy and two revalues.** Copy the reference database by SQLite's backup to
      `<research>/accept/fairband.db`. Run a revalue from a worktree at main (the values after plan
      2), then one from the branch (migration 010, the stage `moat`), reading no key:

```
env -u FAIRBAND_FMP_KEY -u FAIRBAND_GURUFOCUS_KEY FAIRBAND_DATA_DIR=<research>/accept \
    XDG_CONFIG_HOME=<scratch>/config uv run python -m fairband refresh --kind revalue
```

- [ ] **Step 2: The figures.** `accept_plan3.py` (`uv run python -I`, `mode=ro`). Pass: no snapshot
      of the branch's revalue refused `no moat class`; TTMI, NVO, RELX an agent's row each (None,
      Narrow, Wide), their overrides dropped; CRM Narrow; 161, 1,155 and 47 among the `moat_class`
      inputs of the 1,363 valued at refresh 68; `build_moat_table.py read` lists nothing. Reported:
      the values and buy levels that moved between the two revalues (up, down, 20% or more), the
      reviewed values that moved (CRM's expected), Task 3's companies drafted.
- [ ] **Step 3: The examples under 1.8.** For each, its company's class in the file: the class it
      shows keeps its figures, and the caption says unchanged under 1.8; a class that differs is
      valued again on the copy, its figures and their data's date taken. Move the caption's pin;
      full check; commit: "Re-read the Methodology page's examples under method 1.8".
- [ ] **Step 4: The page,** by the mockup README's recipe with the branch: `make_scratch.py`, a
      revalue on it, the server on 8499. On KO, both themes: the file's row closed and open, the
      owner's set by the control, an agent's by `PUT` with its headers, no row (its table row
      deleted on the scratch); the drawer's head with the chip. Screenshots stay outside the
      repository.
- [ ] **Step 5: The whole-branch review** by a fresh reviewer with the spec, this plan and the
      Review Focus; its findings fixed or filed.
- [ ] **Step 6: Ask the founder once,** with the list: merge and push, backup, the server's restart,
      the revalue that applies migration 010.
- [ ] **Step 7: The live steps,** in spec 11's order: the backup
      `fairband-before-method-1.8-<date>.db`; the server stopped by its process id; main
      fast-forwarded and pushed; `uv run python -m fairband refresh --kind revalue`; the server
      started from main on 8470 as before, `GET /api/policy` 200; the page on the live data.
- [ ] **Step 8: The live readout:** the classes over the universe and the valued rows; any row
      refused `no moat class`; the values, levels and reviews moved against plan 2's revalue; the
      three agent rows.
- [ ] **Step 9: The documents.** The readout (Steps 2 and 8, the backup, the refreshes, the commits,
      Task 3's companies for the founder to read) in the spec's decision log; the decision
      document's status, plan 3 built; B-254, B-260, B-261 and B-232 to Done with their commits
      (B-232: the stamp, the column and a review read one class); the limits met filed.
      Documents-only check; commit: "Write plan 3's readout and close B-254, B-260, B-261 and
      B-232". Push with the founder's word.
- [ ] **Step 10: Tell the founder** every research session must restart its MCP process: `moat_set`
      is new, `company` answers `moatClass`.
