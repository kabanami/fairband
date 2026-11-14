# The Research Round, plan 2: the balance sheet, the minority interest, the anchor on a thin window and two smaller rulings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build sections 12 and 13 of the research round spec and the founder's three rulings of 2026-11-14 (sections 9a, 7.3 and 8a) under method 1.4 and policy v14: the quarterly balance sheet fetched and the newest sheet read for debt, cash and the Decline floor; the minority interest subtracted at book on the three firm-value routes, with the input `balance.minority`; the NTM anchor read from the annual consensus on a thin window; a lasting `earnings.sbc` of 0; a reviewed row's flags read from its review. Then the scratch runs, the founder's reading of the anchor's readout, one full refresh and its readout.

**Architecture:** The fetch gains one statement call (`balance-quarter`) and the normalizer one line (`minorityInterest`); the backfill brings the line onto the annual sheets already stored. Assembly picks the newest sheet in one function (`inputs_statements.newest_sheet`), which feeds `build_inputs` and the secondary valuation's default, and hands the engine one record (`engine.balance.NewestSheet`) beside `debt` and `cash`. The three firm-value routes cite the sheet under its own provenance key and subtract the minority interest in their bridge functions, which the price refresh rebuilds from one new intermediate. The anchor rule is one function in `engine/anchor.py` behind a keyword of `ntm_anchor`. The lasting nil is one rule in `overrides.check_override` and one test in `refresh/reviews._drop_reason`. A reviewed row's flags are read from the review's stored result in `web/rows.agent_fields`; nothing is recomputed.

**Tech Stack:** Python 3.13, uv, pytest, mypy, ruff; FastAPI; `app.js` run under node by the drawer tests (`tests/web/page.mjs`); the playbook's Markdown.

**Spec:** `docs/superpowers/specs/2026-11-13-research-round-design.md` (sections 7.3, 8a, 9a, 12 to 19, and the decision log's rows of 2026-11-14). Read it before any task; where this plan and the spec differ, the spec governs and the difference is a finding to report.

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- `docs/method.md` changes in the same commit as the engine, the classifier, the universe rule or a policy value it describes; the Methodology page (`src/fairband/web/static/methodology.html`) with it. Where documents disagree, `docs/method.md` describes what runs.
- Method version `fairband-mechanical/1.4`; policy `fairband-policy-v14`; `fairband-policy-v13.toml` stays byte-identical; no new policy value, no new setting, no database migration.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic or hand-trimmed.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- Every dispatched subagent, reviewers included, runs on Opus 5.5 at xhigh (the founder's standing instruction of 2026-11-10).
- The goldens (`tests/fixtures/golden/`): no value, level, designation or refusal of any golden moves in this plan. MGCO, MSCO and FXCO keep every existing intermediate and input; MGCO gains the `anchor` entry's new keys in Task 8. HGCO, YGCO, DCCO and SUCO are re-captured in Tasks 5 and 6 for the sheet's citation, the floor's input names and the new entries. Each re-capture adds a paragraph to `tests/fixtures/golden/README.md` naming its cause.
- No vendor call and no touch of `~/.local/share/fairband` outside Task 1 and Task 12, and none there without the founder's word.
- Work in a git worktree (superpowers:using-git-worktrees), not in the main checkout: research sessions load code from it, and Task 12's control run needs main's code.
- Task 8 (the anchor) is its own commits and touches no file another task's code depends on, so the founder can leave it out of the merge after reading its readout (spec 9a).

## Review Focus

- A quarterly sheet that presents fewer lines than the annual one, or a nil where the annual holds a figure: the newest sheet is read whole. A line it lacks counts as nil and is named; no line falls back to the annual sheet. Test in Task 4.
- A half-yearly reporter, whose answer by quarter holds half-years: the newest half-year sheet is read as any quarter's, with FMP's own period label in its note. Test in Task 4, on what Task 1 found.
- A company in another currency: the minority interest and the floor's two lines are totals in the reporting currency, the range of `balance.minority` is read at the rate, and the Start-up enterprise value adds the minority interest to a market cap already brought into the currency. Tests in Tasks 6 and 7.
- A price refresh after the 1.4 refresh: the minority interest survives the reprice on each of the three routes, and a Start-up row's `below-net-cash` reads it at the new price. Test in Task 6.
- A thin window whose first fiscal year has no annual row any more (the year ended and the vendor dropped its estimate): the sum of the periods stands and `thin-ntm` names that year. Test in Task 8.

---

### Task 1: The vendor check (spec 12.3)

The controller runs this task itself, on the founder's word to build the plan. It changes no file in the repository, so it has no review.

- [ ] **Step 1: Ask FMP.** With a throwaway script in the session's scratch folder, build the client as `refresh/clients.py` does and call `Fmp.statement(symbol, "balance", "annual", 2)` and `Fmp.statement(symbol, "balance", "quarter", 8)` for FRVO, RKLB, RELX, ABVX and DXC: ten calls. The script prints findings only: no key, no URL, no payload, and it stores nothing.

- [ ] **Step 2: Record the findings in the ledger**, one line for each company:
  - whether the quarterly answer holds rows, and whether its newest period end is at or after the annual one's;
  - which of `shortTermDebt`, `longTermDebt`, `cashAndCashEquivalents`, `shortTermInvestments`, `totalCurrentAssets`, `totalLiabilities` and `minorityInterest` the newest quarterly row presents, and for each whether a line the annual row holds above zero reads 0 or is absent in the quarter;
  - the row's `reportedCurrency`, `fiscalYear` and `period` labels;
  - for RELX and ABVX: the days between the period ends (quarters or half-years) and the labels a half-year carries;
  - for DXC: whether `minorityInterest` is above zero on both answers;
  - for RKLB and FRVO: the newest quarterly period end against the period of their balance overrides (30 Sep 2026 for RKLB).

- [ ] **Step 3: Rule.** A finding that breaks spec 12.2 goes to the founder before Task 2: no quarterly answer for these companies; a quarterly answer whose newest period is older than the annual one's; a quarter that fills a debt or cash line with 0 where the filing holds a figure; `minorityInterest` absent from both answers. Any other finding becomes a line in Task 4's or Task 6's dispatch.

---

### Task 2: Policy v14 and method 1.4

**Files:**
- Create: `src/fairband/policy/fairband-policy-v14.toml` (a copy of v13 with the changes below)
- Modify: `src/fairband/policy/__init__.py` (`_POLICY_FILE`, the docstring's version lines), `src/fairband/engine/__init__.py` (`METHOD_VERSION`)
- Modify: `docs/method.md` 4.1 (the override ranges' row, the sentence "loads v13 only"), 11 (the 1.4 row)
- Test: `tests/policy/test_policy.py`, and every test that pins `fairband-policy-v13` or `mechanical/1.3` (grep both; among them `tests/engine/test_route.py`, `tests/engine/test_types.py`, `tests/reports/test_render.py`, `tests/web/test_settings_api.py`, `tests/web/test_company_reads.py`, `tests/policy/test_settings.py`)

**Interfaces:**
- Produces: `load_policy().version == "fairband-policy-v14"`; `Policy.override_ranges["balance.minority"] == (0.0, 1e15)`; `METHOD_VERSION == "fairband-mechanical/1.4"`. No new `Policy` field.

- [ ] **Step 1: Write the failing tests** in `tests/policy/test_policy.py`, beside the v13 pair:

```python
V13_SHA256 = "f2ec6e5841f35a7068a4c733ca52fc9a9daa6dacea3d6d9131a21616803a83d0"


def test_v14_is_the_packaged_policy() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v14"
    assert p.override_ranges["balance.minority"] == (0.0, 1e15)


def test_v14_is_v13_with_the_minority_range() -> None:
    """v14 adds no value: every v13 value loads unchanged but the override ranges, which gain
    ``balance.minority``, and their note names it."""
    v13 = _file_values("fairband-policy-v13.toml")
    v14 = load_policy().raw["values"]
    assert v14.keys() == v13.keys()
    kept = v13.keys() - {"override_ranges"}
    assert {k: v14[k] for k in kept} == {k: v13[k] for k in kept}
    old, new = v13["override_ranges"]["value"], v14["override_ranges"]["value"]
    assert new == old | {"balance.minority": [0.0, 1e15]}
    assert "balance.minority" in v14["override_ranges"]["note"]


def test_v13_is_byte_identical_under_its_hash() -> None:
    """The hash the snapshots valued under ``fairband-policy-v13`` cite."""
    data = resources.files("fairband.policy").joinpath("fairband-policy-v13.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V13_SHA256
```

`_packaged_bytes` reads the v14 file. `test_v13_is_the_packaged_policy` becomes a read of the v13 file's values, and `test_v13_is_v12_with_the_four_values_added_and_two_ranges` reads v13 through `_file_values`, not `load_policy()`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/policy/test_policy.py -k "v14 or v13"`
Expected: FAIL (`fairband-policy-v13`; no range for `balance.minority`).

- [ ] **Step 3: Create the policy file and point the loader at it.** Copy v13 byte for byte, add the header line `# v14: …` in the form of v13's, set the version, add `"balance.minority" = [0.0, 1e15]` to `[values.override_ranges.value]`, and extend that table's `note` with one sentence that names `balance.minority` and "spec 2026-11-13, section 13". Point `_POLICY_FILE` at v14 and bring the docstring's version lines along. Set `METHOD_VERSION`.

- [ ] **Step 4: Update the version pins and the documents.** Every test that pins the old strings moves to the new ones; the packaged policy's full `override_ranges` in `test_the_packaged_policy_keeps_the_earlier_versions_values` gains the new entry. `docs/method.md` 4.1: the override ranges' row names `balance.minority`, and the sentence on the versions reads "v1 to v13 stay … loads v14 only". Section 11: the 1.4 row, written whole now with one sentence for each change (later tasks do not touch it): the quarterly balance sheet and the newest sheet for debt, cash and the Decline floor; the minority interest at book on the revenue-growth, Decline and Start-up routes; the input `balance.minority`; year 1 from the annual consensus on a thin NTM window; `earnings.sbc` lasting at 0.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Name method 1.4 and policy v14, whose override ranges gain the minority interest"
```

---

### Task 3: The quarterly balance sheet in the store (spec 12.1, and "The figure" of 13)

**Files:**
- Modify: `src/fairband/refresh/fetch.py` (`_calls`, `STATEMENT_ENDPOINTS`, the two docstrings that count the calls), `src/fairband/refresh/run.py` (the comment that counts them), `src/fairband/vendors/normalize_fmp_statements.py` (`_BALANCE`, `_STATEMENTS`, the vendor-zero rule)
- Create: `tests/fixtures/fmp/balance-sheet-statement.quarter.ACME.json`, `tests/fixtures/fmp/balance-sheet-statement.quarter.BOLT.json` (synthetic)
- Modify: `tests/refresh/synthetic.py` (`balance_quarter`, `bodies`), `tests/support/payloads.py` (`_STATEMENTS`)
- Modify: `docs/method.md` 2 (the dataset's row; the required endpoints stay four)
- Test: `tests/vendors/test_normalize_fmp.py`, `tests/refresh/test_fetch.py`, `tests/refresh/test_backfill.py`, and every test that counts a company's calls (`tests/refresh/test_run.py`, `tests/refresh/test_run_full.py`, `tests/refresh/test_passthrough.py`)

**Interfaces:**
- Produces: `fetch_company` stores the endpoint and the dataset `balance-quarter` (eight periods, `STATEMENT_QUARTERS`), fetched right after `cashflow-quarter`; it is not in `REQUIRED`. `statement_fields("balance-quarter") == statement_fields("balance-annual")`, and both hold `minorityInterest`. The backfill writes `minorityInterest` onto every stored annual sheet whose payload is on file. A company's fetch is fifteen FMP calls and two GuruFocus calls.
- Produces for tests: `synthetic.balance_quarter(quarters)` and a `balance-quarter` body in `synthetic.bodies()`. Each synthetic quarter that ends with a fiscal year carries that year's annual figures; each later quarter carries figures of its own, so Task 4's tests can tell a quarter from the year.

- [ ] **Step 1: Write the failing tests.**

`tests/vendors/test_normalize_fmp.py`: the `BALANCE` set gains `minorityInterest` and the two counts become `3 * 14` and `2 * 14`. New:

```python
def test_balance_quarter_facts_carry_the_annual_sheet_s_lines() -> None:
    """Spec 2026-11-13 12.1: the quarterly sheet is stored with the annual sheet's lines, the
    minority interest among them, each quarter under its own period end and label; a goodwill of
    0 is not presented there either."""
    rows = statement_facts(_quarterly_sheet(), "ACME", "balance-quarter", 7, NOW, NOW)
    assert {r.field for r in rows} == BALANCE
    assert {r.dataset for r in rows} == {"balance-quarter"}
    assert statement_fields("balance-quarter") == statement_fields("balance-annual")
    assert "minorityInterest" in statement_fields("balance-annual")
    zero = next(r for r in rows if r.field == "goodwill" and r.fiscal_period == "Q2")
    assert (zero.value, zero.missing_reason) == (None, "vendor-zero")
```

`_quarterly_sheet` is a helper of the module: two quarters of the ACME fixture's shape, `period` `Q1` and `Q2`, the second with `goodwill` 0 and a `minorityInterest` above zero.

`tests/refresh/test_fetch.py`: `FMP_ENDPOINTS` gains `"balance-quarter"` after `"cashflow-quarter"` and `DATASETS` gains it; each count of calls rises by one for each company fetched. New: a company whose quarterly balance call answers 404 is fetched with `failed == ("balance-quarter",)`, no error, and is valued by the run (`REQUIRED` is unchanged).

`tests/refresh/test_backfill.py`: a stored `balance-annual` response whose payload holds `minorityInterest` and whose facts were written without it gets the line once, and a second run writes nothing, in the form of `test_backfill_writes_the_six_lines_once`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/vendors/test_normalize_fmp.py tests/refresh/test_backfill.py -k "balance or minority"`
Expected: FAIL (`ValueError` for `balance-quarter`; no `minorityInterest` field).

- [ ] **Step 3: Implement.** `_BALANCE` gains `("minorityInterest", MONEY)`; `_STATEMENTS["balance-quarter"] = _BALANCE`; the vendor-zero rule reads both balance datasets. `_calls` asks `statement("balance", "quarter", STATEMENT_QUARTERS)` after the quarterly cash flow; `STATEMENT_ENDPOINTS` gains `"balance-quarter"`, which brings the dataset to `_rows` and to the backfill. Write the two fixtures and the synthetic body, and add the dataset to `support/payloads._STATEMENTS`.

- [ ] **Step 4: Move the counts.** Every docstring, comment and test that says fourteen FMP calls says fifteen; `test_passthrough.py`'s pace totals follow (sixteen paced calls, slots 0 to 15).

- [ ] **Step 5: Update `docs/method.md` 2**: the row of the quarterly statements names the balance sheet, eight periods, with the annual sheet's lines; the minority interest joins the balance lines' list; the backfill's sentence names the new line.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Fetch the balance sheet by quarter and store the minority interest with the balance lines"
```

---

### Task 4: The newest balance sheet in assembly (spec 12.2)

**Files:**
- Modify: `src/fairband/engine/balance.py` (`NewestSheet`), `src/fairband/engine/route.py` (`CompanyInputs.sheet`; the docstring's list of provenance keys)
- Modify: `src/fairband/refresh/inputs_statements.py` (`SheetRead`, `newest_sheet`, `balance_lines`, `newest_debt_and_cash`), `src/fairband/refresh/inputs.py` (`build_inputs`)
- Modify: `docs/method.md` 4.2 (the rule of the newest sheet, next to the trailing figures), 4.10 (the data date keeps its datasets), 15.3 (the secondary valuation's default)
- Test: `tests/refresh/test_inputs.py` (among them `ROUTE_KEYS`), `tests/web/test_secondary_api.py`

**Interfaces:**
- Consumes: the dataset `balance-quarter` and `synthetic.balance_quarter` (Task 3).
- Produces:

```python
# engine/balance.py
@dataclass(frozen=True)
class NewestSheet:
    """The newest balance sheet on file, a fiscal year's or a quarter's (spec 2026-11-13 12.2):
    its period, the two lines of the liquidation floor and the minority interest as the sheet
    presents them, each ``None`` when it does not."""

    period_end: date
    label: str  # "fiscal 2026 Q3", "fiscal 2025"
    quarterly: bool
    total_current_assets: float | None
    total_liabilities: float | None
    minority_interest: float | None


# refresh/inputs_statements.py
@dataclass(frozen=True)
class SheetRead:
    lines: dict[str, float | None]
    period_end: date
    label: str
    quarterly: bool
    observed_at: datetime
    entered_at: datetime


def newest_sheet(conn: sqlite3.Connection, symbol: str) -> SheetRead | None: ...
```

  - `CompanyInputs.sheet: NewestSheet | None = None`. `CompanyInputs.debt` and `.cash` are the newest sheet's sums (`balance_sums`), as the routes read them today.
  - `CompanyInputs.provenance["balance_sheet"]`: the source "FMP balance-sheet-statement", `as_of` the sheet's period end, the stamps the newest among the sheet's facts. Absent without a sheet.
  - `balance_lines(conn, symbol)` returns `newest_sheet`'s lines (empty without one), so `newest_debt_and_cash` and the secondary valuation's default follow with no change of their own.
  - The routes still cite debt and cash to `statements` after this task; Task 5 moves the citation.

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_inputs.py`, on the module's `store` fixture and `build`, each company's bodies from `synthetic.bodies()` with the quarterly sheet replaced as the case needs:

  - `test_the_newest_sheet_is_the_quarter_s_when_it_ends_later`: the annual sheet ends with fiscal 2025 and the newest quarterly sheet two quarters later. `inputs.sheet.quarterly` is true, its `period_end` and `label` ("fiscal 2026 Q2") are the quarter's, `inputs.debt` and `inputs.cash` are the quarter's sums, and `provenance["balance_sheet"].as_of` is the quarter's end.
  - `test_a_tie_reads_the_annual_sheet`: the newest quarterly sheet ends on the annual sheet's day with other figures. The annual's figures are read, `quarterly` is false and the label is "fiscal 2025".
  - `test_no_quarterly_sheet_reads_the_annual_one`: the quarterly call answered nothing. As today, with `sheet.quarterly` false.
  - `test_a_quarterly_sheet_in_another_currency_is_skipped`: the newest quarterly sheet's `reportedCurrency` differs from the reporting currency (the newest annual income statement's). The next quarterly sheet in the reporting currency is read when it ends after the annual one, else the annual; a sheet with no currency counts as the reporting one.
  - `test_the_newest_sheet_is_read_whole` (Review Focus): the newest quarter lacks `shortTermInvestments` and holds no `longTermDebt`, both of which the annual presents. Cash is the quarter's `cashAndCashEquivalents` alone, debt its `shortTermDebt` alone, and `inputs.notes["debt"]` and `["cash"]` name the missing lines as today.
  - `test_a_half_year_sheet_is_read_as_a_quarter_s` (Review Focus): on `synthetic.bodies(cadence="half-yearly")`, the newest half-year sheet is read, and its label carries the row's own `period` word, whatever Task 1 found it to be.
  - `test_the_quarterly_sheet_moves_no_fiscal_year_figure`: with and without the quarterly sheet, `capital_years`, `balance_years`, `data_date` and `provenance["statements"]` are equal.
  - `ROUTE_KEYS` gains `balance_sheet`.

  In `tests/web/test_secondary_api.py`, beside `test_a_secondary_valuation_reads_the_balance_sheet`: with a later quarterly sheet on file, the default debt and cash are the quarter's.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/refresh/test_inputs.py -k "sheet"`
Expected: FAIL (no attribute `sheet`).

- [ ] **Step 3: Implement `newest_sheet`.** It reads the newest `balance-annual` period and the `balance-quarter` periods from the facts, outside the list `statements_for` builds, so the quarterly sheet enters neither the data date nor the `statements` input's stamps (spec decision of 2026-11-14). It skips a quarterly period in another currency, keeps the latest period end, and on a tie keeps the annual. The label is `fiscal <year> <period>` for a quarter and `fiscal <year>` for a year, from the facts' own labels; without a fiscal year it reads "the period ending 30 Sep 2026".

- [ ] **Step 4: Read it in `build_inputs`**: one read gives the sums, the notes, `sheet` and the provenance key. Existing tests that pinned the annual sheet's debt or cash on a company whose synthetic quarter is newer move to the quarter's figures; say so in the commit's body.

- [ ] **Step 5: Update the documents.** `docs/method.md` 4.2: the newest balance sheet, its tie rule, the skipped currency, what it gives and what stays on fiscal years (spec 12.2's two lists). 4.10: the data date reads the datasets it read before; the newest sheet carries its own date. 15.3: the secondary valuation's default debt and cash are the newest sheet's.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Read debt and cash from the newest balance sheet on file, a year's or a quarter's"
```

---

### Task 5: The routes cite the newest sheet, and the Decline floor reads it (spec 12.2, 12.4)

**Files:**
- Modify: `src/fairband/engine/route_steps.py` (`sheet_note`, `sheet_entry`), `src/fairband/engine/route_revenue_growth.py` (`bridge_flags`, the DATA entries, the rebuild keys), `src/fairband/engine/route_decline.py` (the floor, `_liabilities_flag`, the floor's two DATA entries), `src/fairband/engine/route_start_up.py` (the DATA entries, the intermediates), `src/fairband/engine/distress.py` (`ncav`)
- Modify: `tests/support/engine_companies.py` (`SOURCES`, `sheet=` on the four firm-value builders, `_restated`)
- Modify: `docs/method.md` 5a.9, 5a.14, 6a.5, 6a.6, 6a.10, 6b.2, 6b.4, 6b.6, 8 (the `line-not-presented` rows); the playbook's override table row for the balance tags and its sentence on the secondary valuation's balance sheet (`playbook/fairband-research/SKILL.md`)
- Test: `tests/engine/test_route_revenue_growth.py`, `tests/engine/test_route_decline.py`, `tests/engine/test_route_start_up.py`, `tests/engine/test_distress.py`, `tests/refresh/test_reviews_follow.py`, `tests/engine/test_golden.py` (re-capture)

**Interfaces:**
- Consumes: `CompanyInputs.sheet`, `provenance["balance_sheet"]` (Task 4).
- Produces:
  - `route_steps.sheet_note(i: CompanyInputs, name: str | None = None) -> str | None`: "the balance sheet of fiscal 2026 Q3", followed by "; " and `i.notes[name]` where the notes hold a missing line for `name`. Without a sheet it is that missing-line note alone, and `None` when there is none.
  - `route_steps.sheet_entry(i: CompanyInputs) -> dict[str, Any]`: `{"balance_sheet": {"period_end": "2026-09-30", "label": "fiscal 2026 Q3", "quarterly": True}}`, the value `None` without a sheet. Each of the three routes puts it beside `debt` and `cash`, in the keys a refusal keeps too.
  - The DATA entries `debt` and `cash` of the three routes cite `balance_sheet` with `sheet_note`.
  - Decline: the floor's NCAV and `line-not-presented:totalLiabilities` read `i.sheet`; two new DATA entries, `floor_current_assets` and `floor_total_liabilities`, cite `balance_sheet` with the period note. `_balance_inputs` (Z″ and F) is untouched. `distress.ncav(y: BalanceYear | NewestSheet) -> float | None`.

- [ ] **Step 1: Write the failing tests.**

  - Each route's test module, on its fixture company with `sheet=NewestSheet(date(2026, 9, 30), "fiscal 2026 Q3", True, ...)`: the `debt` and `cash` entries' provenance is the `balance_sheet` key's and their note is "the balance sheet of fiscal 2026 Q3"; `intermediates["balance_sheet"]` equals `sheet_entry`'s value; a result refused in its route for the target margin carries it too.
  - `tests/engine/test_route_revenue_growth.py`: with `debt=None` and `notes={"debt": "shortTermDebt and longTermDebt not presented"}`, `line-not-presented:debt` fires with a sentence that starts "The newest balance sheet (fiscal 2026 Q3) does not present", and the entry's note holds both parts. With every line presented, no `line-not-presented` flag fires: the period note alone never raises one.
  - `tests/engine/test_route_decline.py`: with the fixture's newest fiscal year at current assets $300 m and liabilities $500 m (NCAV −$200 m) and `sheet` holding $900 m and $500 m, `intermediates["ncav"]` is 400e6, Altman's Z″ and Piotroski's F are equal to the fixture's, and the entries `floor_current_assets` and `floor_total_liabilities` hold the sheet's figures while `total_current_assets` and `total_liabilities` hold fiscal 2025's. A sheet without `total_liabilities` applies no floor and raises `line-not-presented:totalLiabilities` naming "fiscal 2026 Q3".
  - `tests/engine/test_distress.py`: `ncav` on a `NewestSheet`.
  - `tests/refresh/test_reviews_follow.py`, on `_hgco_with_a_cash_correction` (spec 16): the next snapshot on the same trailing period with a later sheet and another cash drops the correction with `CHANGED`; the same cash on a later sheet keeps it applied.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_route_revenue_growth.py tests/engine/test_route_decline.py tests/engine/test_route_start_up.py -k "sheet or floor"`
Expected: FAIL (`sheet_note` is not defined; the entries cite `statements`).

- [ ] **Step 3: Implement.** The period never goes into `CompanyInputs.notes`: `bridge_flags` keeps its test (`figure is None or name in i.notes`) and only its sentence changes. The fixtures' builders set `sheet` from their newest fiscal year (label "fiscal <year>", `quarterly` false), `SOURCES` gains the key, and `_restated` scales the sheet's three money fields.

- [ ] **Step 4: Re-capture HGCO, YGCO, DCCO and SUCO** with the README paragraph: the citation, the notes, the `balance_sheet` entry and DCCO's two floor entries. No value moves.

- [ ] **Step 5: Update the documents.** `docs/method.md`: "the newest balance sheet" where 5a.9, 6a.5, 6b.2 and 6b.4 say annual; 6a.6's floor reads the newest sheet and its own two entries; the intermediates and inputs lists of 5a.14, 6a.10 and 6b.6; section 8's three `line-not-presented` sentences. The playbook: the balance tags correct "the newest balance sheet's debt or cash", and the secondary valuation reads the newest sheet.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Cite debt, cash and the liquidation floor's lines to the newest balance sheet and its period"
```

---

### Task 6: The minority interest in the three routes (spec 13)

**Files:**
- Modify: `src/fairband/engine/route_steps.py` (`minority`), `src/fairband/engine/revenue_growth.py` (`Bridge`, `revenue_valuation`), `src/fairband/engine/route_revenue_growth.py` (the rebuild keys, `_rebuilt_bridge`, the DATA entry), `src/fairband/engine/runoff.py` (`runoff_equity`), `src/fairband/engine/route_decline.py` (the rebuild keys, `_equity`, the `equity` entry, the DATA entry), `src/fairband/engine/route_start_up.py` (`_requirement`, the cash floor, `below_net_cash`, `start_up_at_price`, the DATA entry), `src/fairband/engine/route.py` (`reprice`'s `below_net_cash`)
- Modify: `src/fairband/reports/render.py` (`GLOSSARY`: Distress-sale value, NCAV, Requirement, Cash floor)
- Modify: `docs/method.md` 5a.9, 5a.10, 5a.14, 6a.5, 6a.6, 6a.7, 6a.9, 6a.10, 6b.2, 6b.4, 6b.5, 6b.6, 8 (`ncav-floor`, `below-net-cash`), 13 (the four glossary rows); the Methodology page's equity step of the growth, Decline and Start-up entries, with the sentence that the figure is at book; `playbook/fairband-research/reference/citations.md` (the `minority_interest` entry and intermediate, and the `balance_sheet` entry)
- Test: `tests/engine/test_revenue_growth.py`, `tests/engine/test_runoff.py`, `tests/engine/test_route_revenue_growth.py`, `tests/engine/test_route_decline.py`, `tests/engine/test_route_start_up.py`, `tests/engine/test_route.py`, `tests/engine/test_currency.py`, `tests/reports/test_render.py`, `tests/web/test_methodology.py`, `tests/engine/test_golden.py` (re-capture)

**Interfaces:**
- Consumes: `CompanyInputs.sheet.minority_interest`, `sheet_note` (Tasks 4 and 5).
- Produces:
  - `route_steps.minority(c: Context | StartUpContext) -> float`: the minority interest in force, the newest sheet's line, nil when there is no sheet, the line is not presented or it is at or below zero. Task 7 puts the override in front of it.
  - `Bridge(debt, cash, shares, minority=0.0)`; `runoff_equity(firm_value, debt, cash, shares, ncav, pi, fraction, minority=0.0)`; `below_net_cash(market_cap, debt, cash, minority=0.0)`; `_requirement(found, market_cap, debt, cash, policy, minority=0.0)`. Each new parameter is last and has a default, so no existing call changes.
  - `intermediates["minority_interest"]` on every result of the three routes that carries `debt` and `cash`: the figure in force. The price refresh's rebuild reads it with a default of 0.
  - The DATA entry `minority_interest` on the three routes: the sheet's line as presented (`None` when not presented, the figure as it is when at or below zero), in the reporting currency, cited to `balance_sheet` with `sheet_note`.

The formulas (spec 13):

    revenue-growth   equity = firm value − debt − minority interest + cash
    Decline          going concern a share = (firm value − debt − minority interest + cash) ÷ shares
                     floor a share         = (NCAV − minority interest) ÷ shares
                     distress sale a share = max(0, fraction × firm value + cash − debt − minority interest) ÷ shares
    Start-up         EV at the price = market cap + debt + minority interest − cash
                     cash floor a share = (cash − debt − minority interest) ÷ shares

The Decline `equity` entry subtracts it; `distress_proceeds` stays the fraction of the firm value plus cash; the distress rating reads debt and cash alone. `ncav` stays the sheet's own figure and `ncav_per_share` is the floor a share, less the minority interest.

- [ ] **Step 1: Write the failing tests.**

`tests/engine/test_revenue_growth.py`:

```python
def test_the_bridge_subtracts_the_minority_interest() -> None:
    """Spec 2026-11-13 13: a minority interest of 50 on 100 shares takes 0.50 off the value a
    share, and a nil one changes nothing."""
    base = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, BRIDGE)
    less = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, replace(BRIDGE, minority=50.0))
    assert less.value_per_share == pytest.approx(base.value_per_share - 0.5)
    assert revenue_valuation(PATH, MARGIN, 0.21, CHARGE, replace(BRIDGE, minority=0.0)) == base
```

`tests/engine/test_runoff.py`, after the worked row's assertions (firm value 607.4809, debt 200, cash 100, 100 shares, π 5%, fraction 0.6):

```python
def test_the_minority_interest_comes_off_each_claim() -> None:
    """Spec 2026-11-13 13: 50 of minority interest on 100 shares takes 0.50 off the going
    concern (5.0748 to 4.5748) and off the distress sale (2.6449 to 2.1449), so off the value
    (4.9533 to 4.4533); the floor is the NCAV less it, 600 − 50 on 100 shares."""
    v = _valuation()
    e = runoff_equity(
        v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6, minority=50.0
    )
    assert e.gc_per_share == pytest.approx(4.574808958203771, abs=1e-9)
    assert e.distress_per_share == pytest.approx(2.1448853749222626, abs=1e-9)
    assert e.value_per_share == pytest.approx(4.453312779039696, abs=1e-9)
    assert e.ncav_per_share == pytest.approx(-2.5)
    floored = runoff_equity(
        v.firm_value, 200.0, 100.0, 100.0, ncav=600.0, pi=None, fraction=0.6, minority=50.0
    )
    assert floored.floor_bound and floored.value_per_share == pytest.approx(5.5)
    drowned = runoff_equity(
        100.0, 200.0, 100.0, 100.0, ncav=None, pi=1.0, fraction=0.6, minority=50.0
    )
    assert drowned.distress_per_share == 0.0  # 60 + 100 − 200 − 50 is below zero
```

`tests/engine/test_route_start_up.py`, beside `test_net_cash_above_the_market_cap`:

```python
def test_the_minority_interest_counts_against_the_cash() -> None:
    """Spec 2026-11-13 13: a market cap of 250 against cash of 300 and a minority interest of
    40 is still covered, by net cash of 260; at 100 the enterprise value is 50 and it is not."""
    covered = below_net_cash(250.0, 0.0, 300.0, 40.0)
    assert covered is not None and covered.sentence == (
        "The price is covered by net cash: market cap 250 against net cash 260."
    )
    assert below_net_cash(250.0, 0.0, 300.0, 100.0) is None
```

On the fixtures, with `sheet=replace(i.sheet, minority_interest=x)`:

  - High Growth (`tests/engine/test_route_revenue_growth.py`): `x` of $500 m on the fixture's 100 m shares lowers the value a share by exactly $5.00 and `intermediates["equity"]` by $500 m; `intermediates["minority_interest"]` is 500e6 and the DATA entry holds it, cited to `balance_sheet`. With `x` of `None`, 0 and −10e6 the value, the levels and every intermediate equal the result without a minority interest, `intermediates["minority_interest"]` is 0.0, and the DATA entry holds `None`, 0.0 and −10e6. A row refused for its target margin keeps the key.
  - Decline (`tests/engine/test_route_decline.py`): `x` of $50 m on the fixture's 100 m shares lowers `going_concern_per_share`, `distress_per_share` and the value by the same $0.50 a share, and `equity` by $50 m; the distress rating is unchanged.
  - Start-up (`tests/engine/test_route_start_up.py`): on the fixture (cash 300, no debt) at a market cap of 250, `x` of 100 gives `requirement["ev_price"]` 50, no `below-net-cash`, and a `cash_floor` of 2.0, (300 − 100) on the fixture's 100 shares.
  - The price refresh (Review Focus), in each route's reprice test: after `result_from_json(result_to_json(r))` and `reprice`, `intermediates["minority_interest"]` is unchanged, the revenue-growth implied figures and the Decline value are rebuilt with it, and a Start-up row with `x` of 100, repriced so that its market cap falls from 250 to 150, gains `below-net-cash` (150 + 100 − 300 is below zero).
  - `tests/engine/test_route.py`: a Mature Growth and a Mature Stable result are equal with and without a `sheet` that holds a minority interest.
  - `tests/engine/test_currency.py` (Review Focus): the SEK company of `in_sek` holds its minority interest in SEK as its debt and cash, the DATA entry's unit is `SEK`, and the value a share in dollars equals the dollar company's.
  - `tests/reports/test_render.py`: the glossary test passes on the four changed rows.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_revenue_growth.py tests/engine/test_runoff.py tests/engine/test_route_start_up.py -k "minority"`
Expected: FAIL (unexpected keyword `minority`).

- [ ] **Step 3: Implement** the helper, the four signatures and the three routes. Each route computes `minority(c)` once, stores it beside `debt` and `cash`, and passes it down; every rebuild reads `im.get("minority_interest", 0.0)`.

- [ ] **Step 4: Re-capture HGCO, YGCO, DCCO and SUCO** for the entry and the intermediate, with the README paragraph. The fixtures hold no minority interest, so no value moves.

- [ ] **Step 5: Update the documents.** `docs/method.md`: the formulas above in 5a.9, 6a.5, 6a.6, 6a.7, 6b.2 and 6b.4, with the rule for nil; what the price refresh rebuilds in 5a.10, 6a.9 and 6b.5; the lists of 5a.14, 6a.10 and 6b.6; section 8's `ncav-floor` and `below-net-cash`; the four glossary rows of 13, which `reports/render.py` mirrors. The Methodology page: the equity step of the three entries, and one sentence that the minority interest is taken at book, where a market value would be the better figure.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Subtract the minority interest at book on the revenue-growth, Decline and Start-up routes"
```

---

### Task 7: The input `balance.minority` (spec 13, 14)

**Files:**
- Modify: `src/fairband/engine/overrides.py` (`OverrideTag`, `BRIDGE_ORDER`, `TAGS`, `LABELS`, `INPUT_OF`, `current_reading`, the docstring's count), `src/fairband/engine/route_steps.py` (`minority`)
- Modify: `docs/method.md` 14.2 (the table and the count), 14.3 (rule 2's "twenty", rule 4's list), 14.4 (the balance bullet); `src/fairband/web/static/methodology.html` ("twenty inputs"); `playbook/fairband-research/SKILL.md` (the overrides table, the bridge order's sentence, the refused-unit list), `playbook/fairband-research/reference/tools.md` ("the twenty")
- Test: `tests/engine/test_overrides.py`, `tests/engine/test_review.py`, `tests/refresh/test_reviews_follow.py`, `tests/web/test_reviews_api.py`, `tests/test_playbook.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: `Policy.override_ranges["balance.minority"]` (Task 2); `route_steps.minority` and the DATA entry `minority_interest` (Task 6).
- Produces: the tag `balance.minority`: routes revenue-growth, Decline and Start-up; a total in the reporting currency, 0 or more; period-tied only; label "minority interest"; in `BRIDGE_ORDER` right after `balance.cash`; `INPUT_OF["balance.minority"] == "minority_interest"`. `current_reading(result, "balance.minority")` is the value of the DATA entry `minority_interest`, or of the JUDGMENT entry in its place. `minority(c)` is `max(0.0, nil(chosen(c, "balance.minority", line)))`.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_overrides.py`:

```python
def test_the_minority_interest_tag_s_rules(policy: Policy) -> None:
    """Spec 2026-11-13 13: a total of $0 or more on the three firm-value routes, period-tied
    only, bridged right after cash under the label "minority interest"."""
    tied = ("balance.minority", 120e6, "revenue-growth", policy, ["filing"], "period-tied", None)
    assert check_override(*tied) == ("applied", "")
    assert check_override(*tied[:1], 0.0, *tied[2:]) == ("applied", "")
    assert check_override(*tied[:1], -1.0, *tied[2:]) == (
        "refused-unit",
        "balance.minority takes $0 or more",
    )
    assert check_override(*tied[:5], "lasting", None) == (
        "refused-unit",
        "balance.minority is period-tied only",
    )
    for route in ("decline", "start-up"):
        assert check_input("balance.minority", 120e6, route, policy) == ("applied", "")
    for route in ("mature-growth", "mature-stable"):
        assert check_input("balance.minority", 120e6, route, policy)[0] == "refused-route"
    assert BRIDGE_ORDER.index("balance.minority") == BRIDGE_ORDER.index("balance.cash") + 1
    assert LABELS["balance.minority"] == "minority interest"
    assert INPUT_OF["balance.minority"] == "minority_interest"
```

  - `tests/engine/test_overrides.py`: `current_reading` on HGCO reads the sheet's line, `None` when the line is not presented, and the override's figure on a review; `test_a_money_range_is_read_in_the_row_s_currency` covers the tag on the SEK company (Review Focus).
  - `tests/engine/test_review.py`, on the High Growth fixture: `balance.minority` at $500 m applies with a bridge line of −$5.00 a share after the cash line's place, the deltas sum to the reviewed value, and the JUDGMENT entry stands in place of the DATA entry. It replaces a line the sheet does not present.
  - `tests/refresh/test_reviews_follow.py`: a period-tied `balance.minority` stays applied on the same sheet, drops with `CHANGED` when the sheet's line moves, and with `NEWER` when a newer trailing period is on file.
  - `tests/web/test_reviews_api.py`: through the API on HGCO, lasting is refused with 400 "balance.minority is period-tied only", period-tied applies and keeps the value it corrected, and the detail's bridge names it "minority interest" in `USD`.
  - `tests/test_playbook.py`: twenty-one tags and the word "twenty-one"; the bridge sentence reads "… moat, debt, cash, minority interest, diluted shares, outside the business."

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_overrides.py -k minority`
Expected: FAIL (`balance.minority` is not a tag).

- [ ] **Step 3: Implement.** `current_reading` gets its own arm for the tag: the balance arm's `removeprefix` would look for an entry named `minority`. Move the count of the inputs to twenty-one in the five places that hold it.

- [ ] **Step 4: Update the documents and the playbook.** `docs/method.md` 14.2's row (routes, takes, lifetime, label, the entry it replaces), 14.3's two rules, 14.4's balance bullet (what the three routes compute from it, and that it is how an agent sets a market value or a redeemable stake the line leaves out). The playbook's table row names the evidence: the filing's note on non-controlling or redeemable interests.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Let an agent correct the minority interest with balance.minority, period-tied"
```

---

### Task 8: The NTM anchor on a thin window (spec 9a)

This task's commits stand alone (Global Constraints). It follows Task 2 and needs no other task.

**Files:**
- Modify: `src/fairband/engine/anchor.py` (`AnnualShare`, `annual_ntm`, `Anchor`, `ntm_anchor`, `thin_ntm_flag`, the module docstring), `src/fairband/engine/route_mature_growth.py` (`_anchor_and_path`, `_judged`, the `anchor` entry, the two DATA entries), `src/fairband/engine/route_revenue_growth.py` (its call of `ntm_anchor`), `src/fairband/reports/refs.py` (words for the entry's new keys, where the anchor's keys have words)
- Modify: `docs/method.md` 5.2, 5.11, 5.12, 6.4 and 5a.14 where they name the anchor, 8 (`thin-ntm`); the Methodology page's NTM anchor and its `thin-ntm` entry; the playbook's `thin-ntm` entry and its citations reference
- Test: `tests/engine/test_anchor.py`, `tests/engine/test_route.py`, `tests/engine/test_route_revenue_growth.py`, `tests/engine/test_review.py`, `tests/reports/test_refs.py`, `tests/test_playbook.py`, `tests/web/test_methodology.py`, `tests/engine/test_golden.py` (MGCO)

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class AnnualShare:
    """One fiscal year of year 1's annual figure (spec 2026-11-13 9a): its share of the NTM
    window's periods, its annual EPS mean and its EPS analyst count."""

    fiscal_year: int
    weight: float
    eps: float
    analysts: int


def annual_ntm(
    periods: Sequence[QuarterEstimate],
    annual: Sequence[AnnualEstimate],
    cadence: Cadence,
    policy: Policy,
) -> tuple[AnnualShare, ...] | None: ...
```

  - `annual_ntm` returns the years in order when a period of `periods` is thin (its `analysts` is `None` or below `policy.analyst_min`) and every fiscal year the periods carry has an annual row whose `consensus_value(eps, analysts_eps)` is not `None` and whose `analysts_eps` is `policy.analyst_min` or more; else `None`. A year's weight is its count of periods over `PERIODS_PER_YEAR[cadence]`.
  - `ntm_anchor(..., annual: Sequence[AnnualEstimate] = ())`, a keyword. Where `annual_ntm` gives years, `ntm_eps_raw` is the sum of weight × EPS. `Anchor` gains three fields with defaults: `source: Literal["periods", "annual"] = "periods"`, `periods_sum: float = 0.0`, `annual: tuple[AnnualShare, ...] = ()`. The incomplete-consensus refusal, the stock-pay test, the revenue scale, `guided_eps`, `cycle_gap` and the unit-error check read as now.
  - `thin_ntm_flag(periods: Sequence[QuarterEstimate], annual: Sequence[AnnualEstimate], policy: Policy) -> Flag | None`: fires when a period is thin and a fiscal year of the periods fails the annual test.
  - The Mature Growth `anchor` intermediate gains `source`, `periods_sum` and `annual` (a list of `{"fiscal_year", "weight", "eps", "analysts"}`, or `None`). On the annual source the DATA entries `ntm_eps` and `ntm_net_income` cite `estimates_annual`, with the note "fiscal 2026 × 1/4 + fiscal 2027 × 3/4, the annual consensus: a period of the NTM window has fewer than 5 EPS analysts".

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_anchor.py`:

```python
def _thin_window() -> list[QuarterEstimate]:
    """Four NTM quarters after 2026-06-30, the first in fiscal 2026 on 4 analysts and three in
    fiscal 2027, each at an EPS of 2.5 and a revenue of 30."""
    return [
        q("2026-09-30", 2026, "Q4", 2.5, 30.0, n=4),
        q("2026-12-31", 2027, "Q1", 2.5, 30.0),
        q("2027-03-31", 2027, "Q2", 2.5, 30.0),
        q("2027-06-30", 2027, "Q3", 2.5, 30.0),
    ]


def test_a_thin_window_reads_the_annual_consensus_by_its_periods(policy: Policy) -> None:
    """Spec 2026-11-13 9a: one period in fiscal 2026 and three in fiscal 2027 read
    0.25 × 8.00 + 0.75 × 10.00 = 9.50, where the four periods sum to 10.00."""
    years = [a(2026, 8.0), a(2027, 10.0), a(2028, 11.0)]
    got = ntm_anchor(_thin_window(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, annual=years)
    assert got.ntm_eps_raw == pytest.approx(9.5) and got.ntm_eps == pytest.approx(9.5)
    assert got.ntm_net_income == pytest.approx(95.0)
    assert (got.source, got.periods_sum) == ("annual", pytest.approx(10.0))
    assert got.annual == (AnnualShare(2026, 0.25, 8.0, 10), AnnualShare(2027, 0.75, 10.0, 10))
    assert thin_ntm_flag(_thin_window(), years, policy) is None


def test_the_stock_pay_charge_reads_the_annual_figure(policy: Policy) -> None:
    """Street 5.0 against GAAP 4.0: the consensus excludes stock pay, and the 0.948 a share,
    scaled by the window's revenue as before, comes off 9.50."""
    years = [a(2026, 8.0), a(2027, 10.0)]
    got = ntm_anchor(_thin_window(), trailing(), 5.0, 10.0, 0.21, 100.0, policy, annual=years)
    assert got.sbc_adjustment_per_share == pytest.approx(0.948)
    assert got.ntm_eps == pytest.approx(8.552)


def test_a_window_with_no_thin_period_keeps_its_sum(policy: Policy) -> None:
    years = [a(2027, 9.0)]
    got = ntm_anchor(ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, annual=years)
    assert (got.source, got.ntm_eps_raw, got.annual) == ("periods", pytest.approx(10.0), ())
    assert got.periods_sum == pytest.approx(10.0)


def test_a_window_in_one_fiscal_year_reads_that_year(policy: Policy) -> None:
    window = [replace(ntm()[0], analysts=1), *ntm()[1:]]  # all four in fiscal 2027
    got = ntm_anchor(window, trailing(), 4.2, 10.0, 0.21, 100.0, policy, annual=[a(2027, 9.0)])
    assert got.ntm_eps_raw == pytest.approx(9.0)
    assert got.annual == (AnnualShare(2027, 1.0, 9.0, 10),)


def test_two_half_years_read_half_of_each_year(policy: Policy) -> None:
    halves = [
        replace(half(date(2026, 12, 31), 2026, 1.0), analysts=2),
        half(date(2027, 6, 30), 2027, 1.2),
    ]
    got = ntm_anchor(
        halves,
        trailing(),
        4.2,
        10.0,
        0.21,
        100.0,
        policy,
        cadence="half-yearly",
        annual=[a(2026, 2.0), a(2027, 3.0)],
    )
    assert got.ntm_eps_raw == pytest.approx(2.5) and got.periods_sum == pytest.approx(2.2)


def test_a_thin_or_missing_year_keeps_the_sum_and_is_named(policy: Policy) -> None:
    """The annual figure stands in only on `analyst_min` analysts or more in every year it
    reads; else year 1 is the periods' sum and the note names the first year that fails."""
    start = (
        "1 of the 4 periods the NTM EPS sums has fewer than 5 EPS analysts or no count: the "
        "thinnest, ending 30 Sep 2026, has 4 analysts, and "
    )
    end = ", so year 1 rests on thin evidence."
    cases = {
        "the annual consensus of fiscal 2027 has 4 EPS analysts": [
            a(2026, 8.0),
            a(2027, 10.0, n_eps=4),
        ],
        "the annual consensus of fiscal 2026 has no analyst count": [
            a(2026, 8.0, n_eps=None),
            a(2027, 10.0),
        ],
        "fiscal 2026 has no annual EPS estimate": [a(2027, 10.0), a(2028, 11.0)],  # Review Focus
    }
    for clause, years in cases.items():
        got = ntm_anchor(_thin_window(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, annual=years)
        assert (got.source, got.ntm_eps_raw) == ("periods", pytest.approx(10.0)), clause
        flag = thin_ntm_flag(_thin_window(), years, policy)
        assert flag is not None and flag.sentence == start + clause + end, clause
    none = [a(2026, 0.0, n_eps=None), a(2027, 10.0)]  # a zero with no count is no estimate
    flag = thin_ntm_flag(_thin_window(), none, policy)
    assert flag is not None and "fiscal 2026 has no annual EPS estimate" in flag.sentence
```

The two existing `thin_ntm_flag` tests pass an empty annual consensus, and their sentences gain the clause "and fiscal 2027 has no annual EPS estimate".

On the routes:

  - `tests/engine/test_route.py`, on `mature_growth_inputs()` with its first NTM quarter at 3 analysts and the annual rows `annual(2026, 5_700e6, 5.70, 12)` added before fiscal 2027's: the anchor's `ntm_eps_raw` is 0.25 × 5.70 + 0.75 × 6.00 = 5.925 where the periods sum to 5.90; `intermediates["anchor"]["source"]` is "annual" and `["periods_sum"]` 5.90; the value differs from the fixture's; `thin-ntm` is absent; the `ntm_eps` entry cites `estimates_annual` with the note of the weights. Without the fiscal 2026 row the value equals the fixture's and `thin-ntm` shows right after the place of `few-analysts`.
  - The same change on `mature_stable_inputs()` with a consensus moves `growth_cross_check`'s value and no value, level or refusal of the row; on `high_growth_inputs()` it moves the forward EPS of `intermediates["eps"]` and no value.
  - `tests/engine/test_review.py`: under an applied `earnings.ntm` the guided EPS still stands in for the anchor, the bridge sums, and `thin-ntm` is silent.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_anchor.py -k "thin or annual or half_years_read or one_fiscal_year"`
Expected: FAIL (`AnnualShare` is not defined; unexpected keyword `annual`).

- [ ] **Step 3: Implement** `annual_ntm`, the keyword and the three fields; `thin_ntm_flag` names the first fiscal year, in order, that fails, with "has N EPS analysts" (one analyst reads "1 EPS analyst"), "has no analyst count" or "has no annual EPS estimate". Pass `i.annual_estimates` at both calls of `ntm_anchor` and to the flag.

- [ ] **Step 4: Re-capture MGCO** (and any golden that carries the `anchor` entry) for the three new keys, with the README paragraph. Its window has 20 analysts a quarter, so no figure moves.

- [ ] **Step 5: Update the documents.** `docs/method.md` 5.2: the rule, when the annual figure exists, what stays, where it reaches and the error it accepts, as spec 9a states them. 5.11 and 8: `thin-ntm`'s new condition and sentence. 5.12, 6.4 and 5a.14: the entry's keys and the cited estimates. The Methodology page's anchor paragraph and `thin-ntm` entry. The playbook: `thin-ntm` now means that neither the quarters nor the annual consensus has five analysts; an agent reads the anchor's source at `snapshot:<id>/intermediates/anchor/source`.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Read year 1 from the annual consensus, weighted by the NTM window's periods, where a period of the window has fewer than five analysts"
```

---

### Task 9: A lasting nil stock pay (spec 7.3)

**Files:**
- Modify: `src/fairband/engine/overrides.py` (`TagSpec.lasting_value`, `_spec`, `check_override`), `src/fairband/refresh/reviews.py` (`ON_FILE`, `_drop_reason`, `_follow`, the module docstring), `src/fairband/web/reviews_api.py` (the write's check)
- Modify: `docs/method.md` 14.2 (the row's lifetime), 14.3 (rule 4), 14.4 (the `earnings.sbc` bullet), 14.6 (the drop); the Methodology page's paragraph on the two stock-pay inputs and the life of an override; `playbook/fairband-research/SKILL.md` (the `stock-pay-missing` entry, step 2 of the stock-pay steps, the table row, the refused-unit list, the lifetimes), `playbook/fairband-research/reference/report-template.md` (the nil sentence)
- Test: `tests/engine/test_overrides.py`, `tests/refresh/test_reviews_follow.py`, `tests/web/test_reviews_api.py`, `tests/engine/test_review.py`, `tests/test_playbook.py`, `tests/web/test_methodology.py`

**Interfaces:**
- Produces:
  - `TagSpec.lasting_value: float | None = None`: the one value a lasting override of a period-tied-only tag may take; 0.0 on `earnings.sbc`, `None` on every other tag.
  - `check_override` on a lasting `earnings.sbc`: 0 applies; any other figure is `("refused-unit", "a lasting earnings.sbc takes 0 only: a figure is period-tied")`. The other period-tied-only tags keep "<tag> is period-tied only".
  - `reviews.ON_FILE = "the store holds a trailing stock pay above zero"`. `_drop_reason(conn, override, result, base, trailing_end, stored_sbc)`: a lasting `earnings.sbc` drops with `ON_FILE` when `stored_sbc` is above zero; `None` and 0 keep it. `_follow` passes the assembled `inputs.trailing.sbc` (`None` without trailing figures).
  - `reviews_api.lasting_nil_refusal(tag: str, lifetime: Lifetime, reading: float | str | None) -> str | None`: for a lasting `earnings.sbc` whose snapshot's reading is a number above zero, the sentence "a lasting earnings.sbc of 0 is refused: the snapshot's trailing stock pay is above zero"; else `None` (another tag, a period-tied lifetime, a reading of 0 or no reading). `POST /api/companies/{symbol}/overrides` answers 400 with the sentence, after the engine's rules passed.

- [ ] **Step 1: Write the failing tests.** In `tests/engine/test_overrides.py`, `test_the_two_stock_pay_tags_rules` changes its lasting assertion and gains three:

```python
    lasting = ("earnings.sbc", 40e6, "mature-growth", policy, ["filing"], "lasting", None)
    assert check_override(*lasting) == (
        "refused-unit",
        "a lasting earnings.sbc takes 0 only: a figure is period-tied",
    )
    assert check_override(*lasting[:1], 0.0, *lasting[2:]) == ("applied", "")
    assert TAGS["earnings.sbc"].lasting_value == 0.0
    assert TAGS["balance.cash"].lasting_value is None
```

`test_check_refuses_a_lasting_balance_correction` stays as it is.

`tests/refresh/test_reviews_follow.py`, in the form of `test_a_period_tied_stock_pay_follows_the_figure_the_anchor_read`:

```python
def test_a_lasting_nil_stock_pay_holds_until_the_store_holds_one(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-13 7.3: MGCO with a stored trailing stock pay of nil and a lasting
    ``earnings.sbc`` of 0. It stays applied on the same figures, when a newer period is on file
    and when the trailing figure is missing; it drops when the store holds $50 m."""
```

Its body stores MGCO with `trailing.sbc` at 0.0, inserts the override with `insert_override(conn, "MGCO", "earnings.sbc", 0.0, 0.0, "USD", "the 10-K shows no share-based pay", EVIDENCE, "lasting", None, None, made_on, AGENT, HGCO_AT, "applied", "")`, and follows four snapshots with the module's local `follow`: the same inputs (a review is written and holds the override); the trailing period a quarter later with `sbc` still 0.0 (still applied, where a period-tied one would drop with `NEWER`); `sbc=None` (still applied); `sbc=50e6` (`follow` returns `None`, and the override's state and reason are `("dropped", ON_FILE)`). A second case in the same test: a row refused before its route (no `sbc_ttm` in the result) whose assembled trailing stock pay is $50 m drops it too.

`tests/web/test_reviews_api.py`, in `test_the_two_stock_pay_inputs_through_the_api`: the lasting post at $500 m answers 400 with the new sentence, and a lasting post at 0 on AAPL, whose stored stock pay is $400 m, answers 400 with "a lasting earnings.sbc of 0 is refused: the snapshot's trailing stock pay is above zero". Beside it:

```python
def test_a_lasting_nil_needs_a_snapshot_without_stock_pay() -> None:
    refused = "a lasting earnings.sbc of 0 is refused: the snapshot's trailing stock pay is above zero"
    assert lasting_nil_refusal("earnings.sbc", "lasting", 400e6) == refused
    for reading in (0.0, None):  # nil on file, or a row refused before its route read it
        assert lasting_nil_refusal("earnings.sbc", "lasting", reading) is None
    assert lasting_nil_refusal("earnings.sbc", "period-tied", 400e6) is None
    assert lasting_nil_refusal("growth.belief", "lasting", 0.08) is None
```

`tests/engine/test_review.py`, on the fixture of `test_an_agent_s_stock_pay_charges_the_anchor_and_settles_the_notes` (stored stock pay 0.0, a fiscal year above zero): a review under `earnings.sbc` at 0 leaves the value as it is and silences `stock-pay-missing`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_overrides.py tests/refresh/test_reviews_follow.py -k "stock_pay"`
Expected: FAIL (the old sentence; `ON_FILE` is not defined).

- [ ] **Step 3: Implement** the field, the rule in `check_override` after `check_input` passed, the lasting branch of `_drop_reason` before the guided-year test, the argument from `_follow`, and the write's check in the route beside the period check, where the snapshot's reading is in hand.

- [ ] **Step 4: Update the documents and the playbook.** `docs/method.md` 14.2: "period-tied; lasting at 0 only". 14.3 rule 4 and 14.4's bullet: the lasting form and what it says. 14.6: the lasting 0 drops when the store holds a trailing stock pay above zero, tested on the assembled figure. The Methodology page: one sentence in the stock-pay paragraph. The playbook: where the filings show nil too, set a lasting `earnings.sbc` of 0 with the filing as evidence; the table row and the refused-unit list say what a lasting stock pay takes. Update the pins in `tests/test_playbook.py`.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Let earnings.sbc last at 0 for a company that pays no stock, and drop it when the store holds a trailing stock pay"
```

---

### Task 10: A reviewed row's flags (spec 8a)

**Files:**
- Modify: `src/fairband/web/rows.py` (`NO_AGENT_FIELDS`, `agent_fields`, `screen_row`, `placeholder_row`, the docstrings), `src/fairband/web/research_api.py` (`_review`, the module docstring's keys), `src/fairband/web/static/app.js` (`drawerFlags`, `details`, `window.FairbandPage`, the Clean comment)
- Modify: `docs/method.md` 8 (whose flags a reviewed row shows), 14.5 (the last paragraph); the Methodology page's "Where to read them"; `playbook/fairband-research/reference/tools.md` (`screen`, `company`), `playbook/fairband-research/reference/report-template.md` (the sentence on `share-count-gap` that stays)
- Test: `tests/web/test_rows.py`, `tests/web/test_app.py`, `tests/web/test_research_api.py`, a new `tests/web/test_drawer_flags.py`, `tests/web/test_methodology.py`, `tests/test_playbook.py`

**Interfaces:**
- Produces:
  - `agent_fields(...)["flags"]`: the review's `tuple[Flag, ...]` in the review branch (the review has a value and counts on the snapshot), else `None`; `NO_AGENT_FIELDS["flags"] = None`. The secondary branch leaves it `None`.
  - `screen_row`: the row's `flags` (the words) and `flagCount` read `agents["flags"]` when it is not `None`, else the snapshot's. `placeholder_row` leaves the key out, as it leaves `levels` out, so the row's keys are unchanged.
  - The drawer's `review` record gains `flags`: a list of `{"code", "word", "sentence"}` from the review's result when the review has a value, else `None`.
  - `app.js`: `drawerFlags(body)` returns `{flags, reviewed}`: the review's flags and `true` when `body.review` has a value and flags, else `body.result.flags` and `false`. `details` draws them, with the caption "The review's flags." above the list when `reviewed`. The helper is on `window.FairbandPage`. The Clean filter's line is unchanged.

- [ ] **Step 1: Write the failing tests.**

`tests/web/test_rows.py`:

```python
def test_a_counting_review_sets_the_rows_flags(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-13 8a: where a review fills the row, the row's flag words and its count of
    quality warnings are the review's; a row with no agent's record keeps the snapshot's."""
    _review(db_path, policy, results)
    snapshot, review = _newest(db_path, "AAPL"), _current_review(db_path, "AAPL")
    assert flag_count(snapshot.result.flags) == 1
    settled = replace(review, result=replace(review.result, flags=()))
    fields = agent_fields(snapshot, settled, None, None, {}, TODAY, EDGES)
    assert fields["flags"] == ()
    row = screen_row(snapshot, None, TODAY, 0.6667, [], fields)
    assert (row["flags"], row["flagCount"]) == ([], 0)
    kept = screen_row(snapshot, None, TODAY, 0.6667, [], NO_AGENT_FIELDS)
    assert kept["flags"] == [f.word for f in snapshot.result.flags] and kept["flagCount"] == 1
    assert NO_AGENT_FIELDS["flags"] is None
```

`EDGES` is any four edges, as the test before it passes. Also:

  - through `GET /api/screen` after `_review(...)`, AAPL's row holds the stored review's flag words and `flag_count` of its flags;
  - `test_a_refused_review_leaves_the_engines_flags` and `test_a_refused_rows_secondary_leaves_the_engines_flags`, on `_refused_review` and the `secondaries` fixture: `agent_fields(...)["flags"] is None` and the row's flags are the snapshot's.
  - In `tests/web/test_app.py` the placeholder row's keys and the Clean filter's pinned line pass unchanged.

`tests/web/test_research_api.py`: the exact `review` dict of `test_the_detail_carries_the_review_with_its_bridge` gains `"flags"`, equal to the stored review's flags as dicts; a refused review's record holds `"flags": None`.

`tests/web/test_drawer_flags.py`, on the node harness as `tests/web/test_drawer_needs.py` uses it:

```python
SNAPSHOT = [{"code": "share-count-gap", "word": "Share count and market cap disagree", "sentence": "s"}]
REVIEW = [{"code": "thin-ntm", "word": "Thin NTM consensus", "sentence": "t"}]


def test_the_drawer_reads_the_review_s_flags() -> None:
    """Spec 2026-11-13 8a: a review with a value gives the drawer its flags; a refused review,
    a review without flags and no review leave the snapshot's."""
    body = {"result": {"flags": SNAPSHOT}, "review": {"value": 11.0, "flags": REVIEW}}
    assert _call("drawerFlags", body) == {"flags": REVIEW, "reviewed": True}
    settled = {"result": {"flags": SNAPSHOT}, "review": {"value": 11.0, "flags": []}}
    assert _call("drawerFlags", settled) == {"flags": [], "reviewed": True}
    for review in (None, {"value": None, "flags": None}, {"value": 11.0}):
        body = {"result": {"flags": SNAPSHOT}, "review": review}
        assert _call("drawerFlags", body) == {"flags": SNAPSHOT, "reviewed": False}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/web/test_rows.py tests/web/test_drawer_flags.py -k "flags"`
Expected: FAIL (`KeyError: 'flags'`; `drawerFlags` is not a helper).

- [ ] **Step 3: Implement** the four Python changes and the helper; `details` calls it and keeps the section's heading "Flags".

- [ ] **Step 4: Update the documents and the playbook.** `docs/method.md` 14.5: the row's Flags, Warnings and with them the Clean filter and the sort, and the drawer's flag list, follow the review where it fills the row; a row a secondary valuation fills, a refused review and the Clean filter's condition of a value from the engine stay. Section 8 points there. The Methodology page's "Where to read them" gains the flags. `tools.md`: a `screen` row's flags and count follow the review where `reviewed` is a review's, and the `company` tool's `review` record carries `flags`. `report-template.md`: where it says the screen keeps `share-count-gap` after the count is settled, it says the screen follows the review.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Show the review's flags on a row the review fills, on the screen and in the drawer"
```

---

### Task 11: The drawer's figures and the whole-branch review

**Files:**
- Modify: `src/fairband/web/static/app.js` (`revenueRoute`, `floorAndDistress`, `requirement`, `cashFloor`, `belowFloor`, the Mature Growth section's anchor line, `TOTAL`)
- Test: `tests/web/test_drawer_intermediates.py`, `tests/web/test_app.py`

**Interfaces:**
- Consumes: `intermediates["minority_interest"]`, `intermediates["balance_sheet"]` (Tasks 5 and 6); `intermediates["anchor"]["source"]` and `["annual"]` (Task 8, where it merged).

- [ ] **Step 1: Write the failing tests** on the node harness: a revenue-growth result with a minority interest of 500e6 draws "Less minority interest" between "Less debt" and "Plus cash", and one at 0 draws no such row; the bridge's caption reads "Balance sheet of fiscal 2026 Q3." from `balance_sheet.label` and is absent when the entry is `None` or missing (a result from before 1.4); the Decline floor and distress rows and the Start-up enterprise value and cash floor do the same; a Mature Growth result whose anchor's source is "annual" draws "Year 1 from the annual consensus: fiscal 2026 × 1/4 + fiscal 2027 × 3/4." and one on "periods" draws no such line; `minority_interest` prints as a whole total in the intermediates list.

- [ ] **Step 2: Implement**, then check the drawer by eye on the fixture database (`uv run python -m fairband serve` with the data folder set to a temporary one, as the web tests do): one row of each route, and nothing prints a raw tag or a raw key.

- [ ] **Step 3: Request the whole-branch review** (superpowers:requesting-code-review) against the spec's sections 7.3, 8a, 9a, 12 and 13 and this plan's Review Focus; fix what it finds test-first; park what it rules minor in `docs/backlog.md` as one row.

- [ ] **Step 4: Run the four checks, then commit** the drawer in one commit and each review fix in its own.

---

### Task 12: The scratch runs, the founder's reading, the live step and the readout (spec 17)

Nothing in this task runs without the founder's word. Ask once, with this list: about 1,600 FMP calls for the scratch run, the merge and the push, the backup, the server's restart, one full refresh on the live store.

- [ ] **Step 1: The scratch store.** Copy the live database to a scratch folder with SQLite's backup. In the copy's settings set `refresh.reuse_hours` to 720, so that a full refresh reuses every stored answer and fetches only the new dataset. Run the full refresh on the copy with the branch's code (`FAIRBAND_DATA_DIR=<folder> uv run fairband refresh --kind full`). Check the refresh's record: the calls made are close to one a company. If the stored answers are older than thirty days, run the plain full refresh and say so in the readout.

- [ ] **Step 2: The two revalues.** Copy the scratch store to a control folder. Revalue the scratch store with the branch's code (method 1.4) and the control with main's code from the main checkout (method 1.3). Both are revalues on the same stored answers, so the exchange rate they read is the same (B-182) and every difference is the method's.

- [ ] **Step 3: The scratch readout** (spec 17), control against scratch:
  - every Mature Stable row, and every Mature Growth row whose anchor's source is `periods`: identical in value, levels and refusal. A difference here stops the plan.
  - the anchor (9a): the Mature Growth rows by source; the rows where `thin-ntm` still fires, by the clause of its sentence; the moves of the value (the median, the share within 2% and within 5%, the ten largest each way with the anchor before and after); AZN and RELX; the rows that newly refuse or newly value; each review whose value moved.
  - the balance sheet: of the revenue-growth, Decline and Start-up rows, how many read a quarter's sheet; the sheet's median age before and after; the ten largest moves; the rows that newly refuse or newly value.
  - the minority interest: the rows with a figure above zero, their moves, DXC and TDS named.
  - the overrides (12.4): each period-tied override with its state; each drop with its reason, the override's period and the period of the sheet the engine now reads; RKLB's and FRVO's mechanical values beside their reviewed ones; SYM's share count still applied; every lasting override still applied.
  - a reviewed row (8a): SYM's row no longer counts `share-count-gap`; the count of rows whose flags differ from their snapshot's.
  - Task 1's findings.

- [ ] **Step 4: The Methodology page's examples.** Re-read the six examples on the scratch store's rows under 1.4: CrowdStrike, Roku, 3M and Revolution Medicines are on the routes the balance sheet moves, and Microsoft moves if its window is thin. Change each figure that moved, the "Figures as of" paragraph and the sentence that the examples are unchanged since 1.1, with their pins in `tests/web/test_methodology.py`. Run the four checks and commit.

- [ ] **Step 5: The founder's reading.** Give the founder the anchor's part of the readout and ask whether the rule merges. If not: revert Task 8's commits, take its sentence out of the 1.4 row of `docs/method.md` 11, the anchor line out of the drawer and section 9a's status in the spec to "not merged", run the four checks, and repeat Step 2's scratch revalue.

- [ ] **Step 6: The live step.** Merge to main and push; back up the live database as `fairband-before-method-1.4-<date>.db` with SQLite's backup; stop the server by its process ids; run one full refresh by the command line; start the server from main (`setsid nohup uv run python -m fairband serve >> ~/.local/share/fairband/server.log 2>&1 < /dev/null &`). The live refresh fetches every dataset anew, so it is compared with the scratch run by cause: the counts of Step 3 by route, the named rows, and a sample of rows that differ, each traced to a newer vendor answer.

- [ ] **Step 7: The readout**, written into the spec's decision log: the steps in order, Step 3's items from the live refresh, and each place where the live result differs from the scratch run or from the spec.

- [ ] **Step 8: Close the rows.** In `docs/backlog.md`: B-173, B-174, B-175, B-180 and B-181 to Done with their commits; what is left of each, and the review's parked minors, as rows. Commit, remove the worktree and the workspace, and tell the founder that every research session must restart its MCP process.

---

## Self-review notes

- Spec coverage: 12.3 is Task 1; 14 (v14) is Task 2; 12.1 and the stored line of 13 are Task 3; 12.2 is Tasks 4 and 5; 12.4's drop test is in Task 5 and its readout in Task 12; 13 is Tasks 6 and 7; 9a is Task 8; 7.3 is Task 9; 8a is Task 10; 15 is spread over the tasks' document steps and Tasks 11 and 12; 16's plan 2 tests are in the tasks that own the code; 17's plan 2 readout is Task 12.
- The order: Task 3 before Task 4 (the dataset before its reader); Task 5 before Task 6 so that the goldens are re-captured for one cause at a time; Task 7 needs Tasks 2 and 6. Tasks 8, 9 and 10 need Task 2 alone and touch no file of Tasks 3 to 7 but the documents, so each can be reviewed, and Task 8 left out, on its own.
- Settled while planning, each in the spec's decision log or stated here: the quarterly sheet stays out of the data date; the period never enters `CompanyInputs.notes`, so no flag fires on it; a dropped balance correction whose own period is newer than the sheet the engine now reads is listed in the readout for its agent to make again; the drawer shows the minority interest's row only above zero.
