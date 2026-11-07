# Tier 2, plan 1b, the report: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The report an agent publishes reads as a human analyst's: eleven sections that argue the business and settle on a thesis, the valuation detail in one section, every cite a footnote, a standard DCF beside the route's value on every report, a cyclical business valued at mid-cycle, the price and the multiples read against their history, and the data the page's charts will draw.

**Architecture:** The engine gains one override tag (`earnings.cycle_gap`), a drivers form of the secondary valuation with a sensitivity grid, and a sensitivity reading of the route. The store gains migration 006 (the judgments without their debate text, the secondary's drivers and projection, a multiples log, the sensitivities). The server gains two pass-throughs (FMP's DCF, GuruFocus's trailing P/E series), a multiples-history read, the sensitivity route, the eleven-section check, and a references list in the report's JSON and Markdown. The playbook is rewritten around the debate, the thesis and the cycle. The page (plan 2) draws the charts from the series this plan serves.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite; the `mcp` package; httpx.

**Spec:** `docs/superpowers/specs/2026-11-06-tier-2-agents-design.md`, as amended 2026-11-07: sections 10.2 (the cycle gap), 11 (the secondary valuation), 12 (key judgments), 13.1 to 13.8 (the report, the refs, the check, the export, the multiples history, the sensitivity grid), 14 (the playbook), 15.3 and 15.4 (the tools), 19 (policy v9), 20.4 (the worked numbers), 21 (the tests), 24 (plan 1b). The method as built is `docs/method.md`; the spec cites its sections.

## Global Constraints

- The constraints of every earlier plan: never print, log or commit a key; never commit vendor data; `docs/method.md` changes in the same commit as the engine; the same inputs give the same result bit for bit; every valuation constant lives in the policy file with a source line; one imperative sentence per commit with the `Co-Authored-By` line; `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q` before every commit.
- The mechanical method stays `fairband-mechanical/0.9`; this plan ends at `fairband-policy-v9`, `fairband-review/1` and `fairband-secondary/2`. v8 stays in the package byte-identical under its hash. At the defaults every mechanical figure on every golden and every row is bit for bit what 0.9 gives (spec 2); the goldens' JSON does not move.
- Policy v9 adds two values, neither a setting: `override_ranges["earnings.cycle_gap"]` = (−100.0, 100.0) and `secondary_driver_ranges` = revenue_growth (−0.80, 3.00), operating_margin (−0.50, 0.60), tax_rate (0.0, 0.50), sales_to_capital (0.1, 10.0) (spec 19). Every v8 value is unchanged.
- The secondary valuation discounts at the policy's required return, locked (the founder, 2026-11-07); the grid at other rates is a display, never a value (spec 11).
- A write names its principal as plan 1 built it; every write is a ledger row, the reference both or neither (spec 7). The server's refusal words are the design system's (spec 10.1, 13.3); the new structural refusal is `the report needs a secondary valuation on snapshot <id>`.
- The brand book's words in every sentence the server emits: override, review, snapshot, finding, judgment, note, news item, report, work item, secondary valuation; the model identifier as it arrived.
- Tolerances: 1e-4 on the secondary's worked numbers (spec 20.4), 1e-9 a share on the bridge.

## Review Focus

1. A drivers form with a year whose revenue falls: the reinvestment of that year is zero, not negative, so a decline does not create cash (Task 3's `test_a_falling_year_reinvests_nothing`).
2. A report submitted after a revalue moved the company's snapshot: the secondary valuation on the old snapshot does not count, and the refusal names the latest snapshot's id (Task 7's `test_a_secondary_on_an_older_snapshot_does_not_count`).
3. One ref cited twice, once with a period and once without: one footnote number, one references entry (Task 7's `test_one_number_per_distinct_ref`).
4. A GuruFocus `pettm` payload with zero-filled loss rows: the zeros are dropped, the statistics run over the rest, and the series keeps the gap (Task 6's `test_loss_rows_are_dropped_from_the_series`).
5. A sensitivity cell whose valuation refuses: the cell is `null`, the grid is stored, and a cite of that cell is `unresolved reference` (Task 5's `test_a_refused_cell_is_null_and_cannot_be_cited`).

---

### Task 1: Policy v9 and the cycle gap

**Files:**
- Create: `src/fairband/policy/fairband-policy-v9.toml` (a copy of v8 with the header line for v9, the `earnings.cycle_gap` pair under `[values.override_ranges.value]`, and a new `[values.secondary_driver_ranges]` with `value`, `source` and `note`)
- Modify: `src/fairband/policy/__init__.py` (`_POLICY_FILE`; `Policy.secondary_driver_ranges: dict[str, tuple[float, float]]`; its read; the module docstring's count of the agents' values)
- Modify: `src/fairband/engine/overrides.py` (`OverrideTag`, `BRIDGE_ORDER` after `earnings.nri_gap`, `TAGS` with `_spec("earnings.cycle_gap", _MATURE, "USD a share")`, `current_reading`'s case, a new `LABELS`)
- Modify: `src/fairband/engine/route_mature_growth.py:114,138,230-240` and `src/fairband/engine/route_mature_stable.py:61-62`
- Modify: `docs/method.md` 4.1 (the two rows, Setting "no"), 11 (the versions row for policy v9), 14.2 (the table row), 14.4 (how the mature routes read it), 14.5 (the bridge's order and the line's label)
- Test: `tests/policy/test_policy.py`, `tests/engine/test_overrides.py`, `tests/engine/test_mature_growth.py`, `tests/engine/test_mature_stable.py`, `tests/engine/test_review.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Consumes: `chosen(c, tag, default)` of `route_steps`, `nil`, `nri_gap(i)`; `Policy.override_ranges`.
- Produces: `policy.version == "fairband-policy-v9"`; `Policy.secondary_driver_ranges` with the four keys `revenue_growth`, `operating_margin`, `tax_rate`, `sales_to_capital`.
- Produces: `OverrideTag` with `"earnings.cycle_gap"`; `LABELS: dict[OverrideTag, str]`, the reader's label of each tag's bridge line (`"phase"`: "phase", `"growth.belief"`: "belief", `"path.hold"`: "held rate", `"path.step_2"`: "consensus step 2", `"path.step_3"`: "consensus step 3", `"moat.class"`: "moat", `"margin.target"`: "target margin", `"capital.sales_to_capital"`: "sales to capital", `"return.runway"`: "runway return", `"earnings.nri_gap"`: "non-recurring gap", `"earnings.cycle_gap"`: "mid-cycle earnings", `"decline.rate"`: "decline rate", `"balance.debt"`: "debt", `"balance.cash"`: "cash"); the mature routes write `"cycle_gap": <float>` in their intermediates (0.0 with no override) and read `e = net_income − (nil(gap) + cycle) × shares`; the Mature Growth anchor's correction is the sum of the non-recurring correction and the cycle gap, `None` when neither override applies.

- [ ] **Step 1: Write the failing tests**

In `tests/policy/test_policy.py`: `test_v9_is_the_packaged_policy` (version `fairband-policy-v9`; `override_ranges["earnings.cycle_gap"] == (-100.0, 100.0)`; `secondary_driver_ranges == {"revenue_growth": (-0.80, 3.00), "operating_margin": (-0.50, 0.60), "tax_rate": (0.0, 0.50), "sales_to_capital": (0.1, 10.0)}`; each with a non-empty source); `test_v8_is_byte_identical_under_its_hash` on the pattern of the v7 test; `test_v9_is_v8_with_the_two_values_added`. In `tests/engine/test_overrides.py`: `test_the_cycle_gap_is_a_mature_tag` (`TAGS["earnings.cycle_gap"].routes == TAGS["earnings.nri_gap"].routes`, unit `USD a share`; `BRIDGE_ORDER.index("earnings.cycle_gap") == BRIDGE_ORDER.index("earnings.nri_gap") + 1`; `LABELS["earnings.cycle_gap"] == "mid-cycle earnings"`; every tag has a label); `test_a_cycle_gap_is_refused_on_a_growth_route` (`check_override("earnings.cycle_gap", 2.0, "revenue-growth", ...)` is `refused-route`). In `tests/engine/test_mature_stable.py` and `tests/engine/test_mature_growth.py`, on the fixtures the override tests use:

```python
def test_a_cycle_gap_lowers_the_anchor_earnings(context):
    plain = value_mature_stable(context)
    lowered = value_mature_stable(with_overrides(context, {"earnings.cycle_gap": 1.0}))
    assert lowered.intermediates["cycle_gap"] == 1.0
    assert lowered.intermediates["e_trailing"] == pytest.approx(
        plain.intermediates["e_trailing"] - 1.0 * context.shares
    )
    assert plain.intermediates["cycle_gap"] == 0.0


def test_a_cycle_gap_of_nothing_moves_nothing(context):
    assert value_mature_stable(with_overrides(context, {"earnings.cycle_gap": 0.0})) == value_mature_stable(context)
```

and for Mature Growth the same two plus `test_the_two_gaps_add_on_the_anchor` (an nri gap of 0.5 and a cycle gap of 1.0 shift the anchor's basis by 1.5 a share). In `tests/engine/test_review.py`: `test_the_cycle_gap_line_follows_the_non_recurring_gap` (both overrides applied: the bridge's lines are in `BRIDGE_ORDER`, the cycle line's `old == 0.0`, `new == 1.0`, the deltas sum). `tests/engine/test_golden.py` is unchanged and must stay green.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/policy tests/engine/test_overrides.py tests/engine/test_mature_stable.py tests/engine/test_mature_growth.py tests/engine/test_review.py -q`
Expected: FAIL on the v9 file, the tag and the intermediates key.

- [ ] **Step 3: Write the v9 file and the loader**

Copy v8 to v9; change the header line's version; add `"earnings.cycle_gap" = [-100.0, 100.0]` after the nri gap pair; add `[values.secondary_driver_ranges]` with `source = "spec 2026-11-06 Tier 2 (amended 2026-11-07), section 11: the range of each driver of the secondary valuation's standard form; no source gives the numbers; policy value"` and a `note` naming the unit of each (a fraction for a growth rate, a margin and a tax rate; a multiple for sales-to-capital). Read it in `load_policy` as `override_ranges` is read, into `secondary_driver_ranges`. Keep v8 in the package unchanged.

- [ ] **Step 4: Add the tag to the engine and the routes**

`overrides.py`: the literal, the bridge order, the spec, `LABELS`, the `current_reading` case `im.get("cycle_gap")`. The mature routes: `cycle = chosen(c, "earnings.cycle_gap", 0.0)` beside the gap; the anchor earnings subtract both; the intermediates carry `"cycle_gap": cycle`; `route_mature_growth.py:230` adds the cycle correction into the anchor's correction (the sum, `None` when neither applies). Where a result is valued under the override, the JUDGMENT entry is written as the non-recurring gap's is (`INPUT_OF` needs no entry: the gap tags stand for no DATA entry).

- [ ] **Step 5: Change `docs/method.md`**

4.1: the two v9 rows. 11: a row "0.9, `fairband-review/1`, `fairband-secondary/1`, policy v9 | <date> | the cycle gap and the secondary's driver ranges; every v8 value unchanged". 14.2: the row for `earnings.cycle_gap`, "the correction that takes the anchor's earnings to mid-cycle for a cyclical business; the same arithmetic as the non-recurring gap". 14.4: the mature routes subtract both gaps. 14.5: the bridge's order and the line labels of `LABELS`.

- [ ] **Step 6: Run the whole check and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all green; the goldens unchanged.

```bash
git add src/fairband/policy src/fairband/engine docs/method.md tests
git commit -m "Add policy v9 with the mid-cycle earnings override that the mature routes subtract from the anchor, labelled on the bridge after the non-recurring gap"
```

---

### Task 2: Migration 006 and the judgments as a record

**Files:**
- Create: `src/fairband/store/migrations/006_report.sql`
- Modify: `src/fairband/store/reports.py` (`JudgmentRow`, `insert_judgments`, `_judgment`)
- Modify: `src/fairband/web/reports_api.py` (`JudgmentPost`)
- Modify: `src/fairband/reports/check.py` (`check_judgments` on `decision` only)
- Modify: `playbook/fairband-research/reference/tools.md` only where `report_submit`'s judgment shape is named (the rest of the playbook is Task 8)
- Test: `tests/store/test_db.py`, `tests/store/test_reports.py`, `tests/web/test_reports_api.py`, `tests/reports/test_check.py`

**Interfaces:**
- Produces, migration 006: `ALTER TABLE judgments DROP COLUMN bull` and `DROP COLUMN bear`; `ALTER TABLE secondary_valuations ADD COLUMN form TEXT NOT NULL DEFAULT 'parts'`, `ADD COLUMN drivers TEXT` (JSON or NULL), `ADD COLUMN projection TEXT` (JSON or NULL), `ADD COLUMN grid TEXT` (JSON or NULL); `CREATE TABLE multiples_log (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, day TEXT NOT NULL, price TEXT NOT NULL, pe_reported TEXT, pe_clean TEXT, pe_forward TEXT, snapshot_id INTEGER, refresh_id INTEGER, created_at TEXT NOT NULL, UNIQUE (symbol, day))`; `CREATE TABLE sensitivities (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, snapshot_id INTEGER NOT NULL, review_id INTEGER, created_at TEXT NOT NULL, principal TEXT NOT NULL, actor TEXT, client TEXT, row_tag TEXT NOT NULL, col_tag TEXT NOT NULL, row_values TEXT NOT NULL, col_values TEXT NOT NULL, cells TEXT NOT NULL, current_row INTEGER, current_col INTEGER, policy_version TEXT NOT NULL, settings_hash TEXT NOT NULL)`; indexes on `(symbol, day)` and `(symbol, snapshot_id)`.
- Produces: `JudgmentRow(id, report_id, symbol, judgment, decision, override_id)`; `insert_judgments(conn, report_id, symbol, judgments: Sequence[Mapping])` reading `judgment`, `decision`, `override_id` only; `JudgmentPost(judgment, decision, override_id=None)` with `model_config = ConfigDict(alias_generator=to_camel, extra="forbid")` so `bull` is refused as an unknown field (422 from the body validation).
- Produces: `check_judgments` finds a quantity in `decision` only.

- [ ] **Step 1: Write the failing tests**

`tests/store/test_db.py`: `test_migration_006_on_a_005_database_keeps_the_judgments` (build a database at 005 with the fixture's path; insert a report and two judgments with `bull` and `bear`; `migrate`; the judgments' `decision` and `override_id` are intact, `PRAGMA table_info(judgments)` has no `bull`; `secondary_valuations` has `form` defaulting to `parts`; `multiples_log` and `sensitivities` exist with the columns above). `tests/web/test_reports_api.py`: `test_a_judgment_with_bull_or_bear_is_an_unknown_field` (a submission whose judgment carries `bull` answers 422 naming the field); the existing submissions drop `bull` and `bear`. `tests/reports/test_check.py`: `test_a_figure_in_a_decision_is_a_finding` keeps its assertion on `decision`; the `bull` and `bear` cases go.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/store/test_db.py tests/web/test_reports_api.py tests/reports/test_check.py -q`
Expected: FAIL on the missing migration and the accepted field.

- [ ] **Step 3: Write the migration, the store and the models**

The DDL above. `DROP COLUMN` needs SQLite 3.35; assert `sqlite3.sqlite_version_info >= (3, 35, 0)` in the migration test with a clear message. `tests/support/payloads.py` and every test submission lose `bull` and `bear`.

- [ ] **Step 4: Run the whole check and commit**

```bash
git add src/fairband/store src/fairband/web/reports_api.py src/fairband/reports/check.py playbook tests
git commit -m "Add migration 006: the judgments as a record without their debate text, the secondary's drivers and grid columns, the multiples log and the sensitivities"
```

---

### Task 3: The drivers form in the engine

**Files:**
- Modify: `src/fairband/engine/secondary.py`
- Modify: `docs/method.md` 15.1 (the two forms), 15.2 (the drivers' arithmetic), 15.4 (the refusals), 15.6 (the worked numbers of spec 20.4), 11 (the versions row for `fairband-secondary/2`), 13 (the glossary row's text)
- Test: `tests/engine/test_secondary.py`

**Interfaces:**
- Consumes: `terminal_roic(aggregate, moat, policy)` of `engine/roic.py` (the caller computes ROIC_T; the engine function takes it as a number); `Policy.required_return`, `Policy.terminal_growth`, `Policy.secondary_driver_ranges`, `secondary_years_min`, `secondary_years_max`.
- Produces: `SECONDARY_METHOD = "fairband-secondary/2"`; `Drivers(years: int, revenue_growth: tuple[float, ...], operating_margin: tuple[float, ...], tax_rate: float, sales_to_capital: float, terminal_growth: float)` (frozen); `Year(t: int, revenue: float, ebit: float, nopat: float, reinvestment: float, fcff: float, pv: float)`; `Projection(years: tuple[Year, ...], terminal_fcff: float, terminal: float, terminal_pv: float, value: float)`; `project(drivers: Drivers, revenue_0: float, r: float, roic_t: float) -> Projection` (spec 11's arithmetic: `reinvestment_t = max(0, revenue_t − revenue_{t−1}) ÷ s`; terminal FCFF `= NOPAT_N × (1 + g) × (1 − g ÷ roic_t)`; terminal `= terminal FCFF ÷ (r − g)`); `secondary_value(*, parts: Sequence[Part] | None = None, drivers: Drivers | None = None, revenue_0: float | None = None, roic_t: float | None = None, debt, cash, shares, price, moat, policy) -> SecondaryValuation` with exactly one form; `SecondaryValuation` gains `form: Literal["parts", "drivers"]`, `drivers: Drivers | None`, `projection: Projection | None`, `grid: SecondaryGrid | None` where `SecondaryGrid(rows: tuple[float, float, float], cols: tuple[float, float, float], cells: tuple[tuple[float, ...], ...])`, rows the terminal growth at g − 0.01, g, min(g + 0.01, g_T), cols the rate at r − 0.01, r, r + 0.01, each cell the value a share by the same arithmetic (the parts form gets a grid too, its rows moving every part's terminal growth together). `_check_drivers` refuses, in this order and each with its sentence: "a secondary valuation runs 3 to 15 years" (the years), "revenue_growth has <n> entries for <N> years" (each list), "<driver> is <low> to <high>" for a driver outside `secondary_driver_ranges` (each entry of a list checked), "the terminal growth is at most <g_T>".

- [ ] **Step 1: Write the failing tests**

```python
def test_the_drivers_worked_numbers(policy):  # spec 20.4
    drivers = Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02)
    p = project(drivers, 1000.0, 0.09, 0.12)
    assert [y.revenue for y in p.years] == pytest.approx([1100.0, 1188.0, 1247.4])
    assert [y.reinvestment for y in p.years] == pytest.approx([50.0, 44.0, 29.7])
    assert [y.fcff for y in p.years] == pytest.approx([115.0, 134.2, 157.41])
    assert sum(y.pv for y in p.years) == pytest.approx(340.007444, abs=1e-4)
    assert p.terminal_fcff == pytest.approx(159.0435, abs=1e-4)
    assert p.terminal_pv == pytest.approx(1754.439476, abs=1e-4)
    v = secondary_value(drivers=drivers, revenue_0=1000.0, roic_t=0.12, debt=200.0, cash=100.0,
                        shares=50.0, price=30.0, moat="Narrow", policy=at_r(policy, 0.09))
    assert v.form == "drivers"
    assert v.firm_value == pytest.approx(2094.44692, abs=1e-4)
    assert v.value_per_share == pytest.approx(39.888938, abs=1e-4)
    assert v.grid.cells[1][1] == pytest.approx(v.value_per_share)
    assert v.grid.rows == pytest.approx((0.01, 0.02, 0.03)) and v.grid.cols == pytest.approx((0.08, 0.09, 0.10))


def test_a_falling_year_reinvests_nothing(policy):
    drivers = Drivers(3, (0.10, 0.08, -0.05), (0.20,) * 3, 0.25, 2.0, 0.02)
    assert project(drivers, 1000.0, 0.09, 0.12).years[2].reinvestment == 0.0


def test_the_grid_caps_the_terminal_growth_at_g_t(policy):  # g = g_T: the third row repeats the second
def test_one_form_only(policy):  # both or neither raise "a secondary valuation takes drivers or parts, not both" / "needs drivers or parts"
def test_each_driver_range_refuses_by_name(policy):  # parametrized over the four drivers and the years
def test_a_list_of_the_wrong_length_is_refused(policy):
def test_the_parts_form_is_unchanged(policy):  # test_one_part's numbers still hold under the new signature, form == "parts", a grid present
```

`at_r` is a test helper returning the policy with `required_return` replaced (`dataclasses.replace`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/engine/test_secondary.py -q`
Expected: FAIL with `Drivers` undefined.

- [ ] **Step 3: Implement the drivers form, the grid and the method's version**

`project` as the Interfaces state; `secondary_value` dispatches on the form; the grid by re-running the same arithmetic nine times. Keep the parts form's arithmetic byte for byte.

- [ ] **Step 4: Change `docs/method.md` 15 and 11**

15.1: two forms; 15.2: the drivers' arithmetic in the spec's lines; 15.4: the new refusals in order; 15.6: the worked numbers of spec 20.4 as a table; 15.5: the grid is a display at other rates, the rate in force stays r; 11: the versions row for `fairband-secondary/2` (a plan 1 record stays `/1` and reads as it was); 13: the glossary's "Secondary valuation" names the standard form and the parts form.

- [ ] **Step 5: Run the whole check and commit**

```bash
git add src/fairband/engine/secondary.py docs/method.md tests/engine/test_secondary.py
git commit -m "Add the drivers form of the secondary valuation, the standard FCFF projection at the policy's rate with a three-by-three grid, as fairband-secondary/2"
```

---

### Task 4: The drivers form on the API, in the store, in the refs and in Appendix A

**Files:**
- Modify: `src/fairband/web/reviews_api.py` (`SecondaryDrivers`, `SecondaryPost`, `post_secondary`, `secondary_json`)
- Modify: `src/fairband/store/secondary.py` (`SecondaryRow`, `insert_secondary`, `_secondary`)
- Modify: `src/fairband/reports/refs.py` (`_secondary`, `_SECONDARY_FIELDS`, the module docstring's list)
- Modify: `src/fairband/reports/render.py` (`_secondary`, `_appendix_a_tables`)
- Modify: `src/fairband/mcp/server.py` (`secondary_valuation`'s signature and description), `src/fairband/web/methodology_text.py` only if it names the form
- Test: `tests/web/test_secondary_api.py`, `tests/store/test_secondary.py`, `tests/reports/test_refs.py`, `tests/reports/test_render.py`, `tests/mcp/test_server.py`

**Interfaces:**
- Consumes: Task 3's `Drivers`, `project`, `secondary_value`; Task 2's columns; `terminal_roic(aggregate, moat, policy)` with the aggregate ROIC from the snapshot's intermediates where the route stores one (`roic` → `aggregate`, as the mature routes write it), else `None`; the trailing revenue as `financials` serves `revenue` for `ttm` (the engine's reading, `TrailingFigures.revenue` of the snapshot's inputs), refused 400 "no trailing revenue on file" when `None`.
- Produces: `SecondaryDrivers(years: int, revenue_growth: list[float], operating_margin: list[float], tax_rate: float, sales_to_capital: float, terminal_growth: float)`; `SecondaryPost(reason, evidence, drivers: SecondaryDrivers | None = None, parts: list[SecondaryPart] | None = None, debt=None, cash=None)`; the refusals 400 "a secondary valuation takes drivers or parts, not both" and "a secondary valuation needs drivers or parts"; `insert_secondary(..., valuation)` stores `form`, `drivers` (the dataclass as JSON), `projection` (the years as a list of `{t, revenue, ebit, nopat, reinvestment, fcff, pv}` plus `terminal_fcff`, `terminal`, `terminal_pv`), `grid` (`{rows, cols, cells}`), `secondary_method` from the engine's constant; `SecondaryRow` gains `form`, `drivers`, `projection`, `grid`; `secondary_json` carries them camelCase.
- Produces, refs: `secondary:<id>/years/<t>/<line>` with `line` in `revenue`, `ebit`, `nopat`, `reinvestment`, `fcff`, `pv` (currency), `/drivers/years` (count), `/drivers/<name>` for `tax_rate`, `terminal_growth` (ratio) and `sales_to_capital` (multiple), `/drivers/<name>/<t>` for the two lists (ratio), `/grid/<i>/<j>` (per-share), `/terminal_fcff`, `/terminal`, `/terminal_pv` (currency); on a parts record the `years` and `drivers` paths resolve to nothing.
- Produces, Appendix A: the secondary's block carries `form`, the drivers, the projection table and the grid; the Markdown prints the projection as a table (t, revenue, EBIT, NOPAT, reinvestment, FCFF, PV) and the grid as a three-by-three table with its row and column headers.
- Produces, MCP: `secondary_valuation(symbol, reason, evidence, drivers=None, parts=None, debt=None, cash=None)`, description "Value the company a second way: the standard DCF from drivers {years, revenue_growth[], operating_margin[], tax_rate, sales_to_capital, terminal_growth}, or a sum of parts [{name, fcff, terminal_growth, note}]; with a reason and evidence."

- [ ] **Step 1: Write the failing tests**

`tests/web/test_secondary_api.py`: `test_the_drivers_form_over_the_api` (on the fixture company whose trailing revenue the test sets to 1,000 and whose policy the test sets to r 0.09, with a `Narrow` moat whose terminal return the test pins to 0.12 by the fixture's aggregate ROIC: the answer's `valuePerShare` is 39.888938 within 1e-4, `form == "drivers"`, nine grid cells, the projection's three years; the ledger summary reads "$39.89 a share from drivers over three years: <gist>"); `test_drivers_or_parts_not_both`; `test_drivers_or_parts_needed`; `test_a_driver_range_refuses_by_name` (parametrized over the four drivers; the sentence names the driver and its ends); `test_no_trailing_revenue_is_refused`; `test_the_parts_form_still_answers` (the existing parts test's numbers, `form == "parts"`). `tests/reports/test_refs.py`: `test_the_secondary_projection_and_grid_refs_resolve` (each path above with its unit; `/years/9/fcff` on a three-year record is unresolved; a `$` cite of `/drivers/tax_rate` is `wrong unit`). `tests/reports/test_render.py`: `test_appendix_a_carries_the_drivers_and_the_grid`. `tests/mcp/test_server.py`: the tool's arguments.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/web/test_secondary_api.py tests/reports/test_refs.py tests/reports/test_render.py tests/mcp/test_server.py -q`
Expected: FAIL on the body model and the refs.

- [ ] **Step 3: Implement the route, the store, the refs, the appendix and the tool**

- [ ] **Step 4: Run the whole check and commit**

```bash
git add src/fairband/web src/fairband/store/secondary.py src/fairband/reports src/fairband/mcp tests
git commit -m "Serve the secondary valuation's drivers form over the API and MCP, store its projection and grid, and resolve their refs in reports and Appendix A"
```

---

### Task 5: The sensitivity grid of the route

**Files:**
- Create: `src/fairband/engine/sensitivity.py`
- Create: `src/fairband/store/sensitivities.py`
- Modify: `src/fairband/web/reviews_api.py` (two routes), `src/fairband/reports/refs.py` (`sensitivity:`), `src/fairband/reports/render.py` (Appendix A's checks list is unchanged; the record is cited, not listed), `src/fairband/mcp/server.py` (the tool), `src/fairband/store/ledger.py` only if kinds are enumerated
- Modify: `docs/method.md` 16.2 (the ref) and a new 14.8 "A sensitivity reading"
- Test: `tests/engine/test_sensitivity.py`, `tests/store/test_sensitivities.py`, `tests/web/test_reviews_api.py`, `tests/reports/test_refs.py`, `tests/mcp/test_server.py`

**Interfaces:**
- Consumes: `value_company(inputs, deciles, policy, today, overrides=...)`; `build_inputs`, `latest_deciles` as `post_override` uses them; `check_override` and `TAGS` for the two tags; `current_reading`; the current review's applied overrides as a mapping by tag (`applied_overrides(conn, symbol)` of `store/overrides.py`, or the review's own list).
- Produces: `sensitivity_grid(inputs, deciles, policy, today, applied: Mapping[str, Any], row_tag: OverrideTag, row_values: Sequence[float | str], col_tag: OverrideTag, col_values: Sequence[float | str]) -> SensitivityGrid` where `SensitivityGrid(rows, cols, cells: tuple[tuple[float | None, ...], ...], current: tuple[int, int] | None)`: each cell the value a share of `value_company` under `applied | {row_tag: r, col_tag: c}`, `None` where the result has no value; `current` the pair whose values equal, within 1e-12, the readings in force (the applied override's value, else `current_reading` of the snapshot's result), `None` when no pair matches.
- Produces: `POST /api/companies/{symbol}/sensitivities` for agents (body `{rowTag, rowValues, colTag, colValues}`), refused 400 with the override rule's sentence for a tag that is not an input, that the route does not read, or a value outside its range (as `check_override` would say, by `_check`'s route), "an axis holds one to five values" past five, "the two tags differ" when equal, and 409 by `require_current`; stored as a `sensitivities` row with the snapshot, the current review's id, the writer and the versions; the answer `{id, symbol, snapshotId, reviewId, rowTag, colTag, rowValues, colValues, cells, current}`; a ledger row of kind `sensitivity` whose summary names the two tags and the grid's size. `GET /api/sensitivities/{id}`. The ref `sensitivity:<id>/<i>/<j>` resolves to the cell's value a share, `unresolved reference` on a `null` cell or an index off the grid; its snapshot for `wrong snapshot` is the record's.
- Produces, MCP: `sensitivity(symbol, row_tag, row_values, col_tag, col_values)`, description "The route's value a share across two inputs' values, at most five by five, stored to cite as sensitivity:<id>/<i>/<j>; nothing is overridden."

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_sensitivity.py`: `test_the_grid_is_the_engine_under_each_pair` (on the Mature Growth golden: a 2×2 over `growth.belief` (0.05, 0.08) and `return.runway` (0.10, 0.20); each cell equals `value_company` with those two overrides; `current` is `None` when no pair matches, and `(0, 1)` when the fixture's readings are those values); `test_a_refused_cell_is_null` (a `path.hold` that drives the value below zero on the revenue-growth golden: that cell `None`, the others present). `tests/web/test_reviews_api.py`: `test_a_sensitivity_is_stored_and_cited` (post, read, cite `sensitivity:<id>/0/1` in a report that passes); `test_a_refused_cell_is_null_and_cannot_be_cited` (the cite answers `unresolved reference`); `test_a_sensitivity_refuses_as_an_override_would` (parametrized: a locked tag, a tag the route does not read, a value outside its range, six values, the same tag twice); `test_settings_changed_refuses_a_sensitivity`; `test_the_owner_cannot_post_a_sensitivity` (403, as `derive`).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/engine/test_sensitivity.py tests/web/test_reviews_api.py tests/reports/test_refs.py -q`
Expected: FAIL with the module missing.

- [ ] **Step 3: Implement the engine function, the store, the routes, the ref and the tool**

- [ ] **Step 4: Write `docs/method.md` 14.8 and the 16.2 row, run the whole check and commit**

```bash
git add src/fairband/engine/sensitivity.py src/fairband/store/sensitivities.py src/fairband/web src/fairband/reports src/fairband/mcp docs/method.md tests
git commit -m "Add the sensitivity reading: the route's value across two inputs' values, stored and cited, with nothing overridden"
```

---

### Task 6: The multiples history: the log, the two pass-throughs and the read

**Files:**
- Create: `src/fairband/store/multiples.py`
- Create: `src/fairband/web/multiples_api.py`
- Modify: `src/fairband/refresh/run.py:488-500,520-525` and `src/fairband/refresh/run_price.py:280-296` (log after each `insert_snapshot`)
- Modify: `src/fairband/vendors/fmp.py` (`dcf`, `dcf_levered`), `src/fairband/vendors/gurufocus.py` (`pe_ttm`)
- Modify: `src/fairband/refresh/passthrough.py` (`KINDS`, the GuruFocus client, the provider per call, the seven-day reuse), `src/fairband/__main__.py:159-166` (build the GuruFocus client for the pass-through when its key is present), `src/fairband/web/app.py` (`add_multiples_routes`), `src/fairband/web/vendor_api.py` (the 503 "no GuruFocus key" sentence)
- Modify: `src/fairband/reports/refs.py` (`multiple:`), `src/fairband/mcp/server.py` (three tools)
- Modify: `docs/method.md` 16.2 (the `multiple:` row) and a new 16.7 "The multiples history"
- Test: `tests/store/test_multiples.py`, `tests/refresh/test_run.py`, `tests/refresh/test_run_price.py`, `tests/refresh/test_passthrough.py`, `tests/web/test_company_reads.py`, `tests/web/test_vendor_api.py`, `tests/reports/test_refs.py`, `tests/mcp/test_server.py`, `tests/vendors/test_fmp.py`, `tests/vendors/test_gurufocus.py`

**Interfaces:**
- Consumes: `result.intermediates["multiples"]` (`pe_reported`, `pe_clean`, `pe_forward`, each a float or `None`) and `result.price_date`, `result.price` of a `ValuationResult`; `build_clients` of `refresh/clients.py` for the GuruFocus client; `record_response`, `latest_response`, `response_payload` of `store/vendor.py`.
- Produces, store: `log_multiples(conn, symbol, day: date, price: float, pe_reported, pe_clean, pe_forward, snapshot_id: int | None, refresh_id: int | None, at: datetime) -> None` (an upsert on `(symbol, day)`, the newest write wins); `multiples_log_for(conn, symbol) -> list[MultiplesRow]` oldest first, `MultiplesRow(day, price, pe_reported, pe_clean, pe_forward, snapshot_id)`; `since(conn, symbol) -> date | None`.
- Produces, refresh: after every `insert_snapshot` in `run.py` and `run_price.py`, a log row when the result carries a price and a price date (a refusal with no price logs nothing); the multiples `None` where the result has none; inside the same transaction.
- Produces, vendors: `Fmp.dcf(symbol)` → `stable/discounted-cash-flow`, `Fmp.dcf_levered(symbol)` → `stable/levered-discounted-cash-flow`; `GuruFocus.pe_ttm(symbol)` → `stock/{symbol}/pettm`. The exact routes are checked against each vendor's documentation at build time (spec 15.3); the FMP docs pages are `developer/docs/stable/dcf` and `developer/docs/stable/dcf-levered`; the GuruFocus route is the one the stocks repo's notes record as working.
- Produces, pass-through: `KINDS = ("transcript", "news", "segments", "insider-trades", "dcf", "pe-history")`; `Passthrough(fmp, conn_factory, policy, clock, secrets, gurufocus: GuruFocus | None = None)`; `dcf` is two FMP calls answered as the parts `dcf` and `levered`; `pe-history` is one GuruFocus call, provider `gurufocus`, endpoint `pettm`, reused inside `PE_HISTORY_REUSE_HOURS = 168` whatever `reuse_hours` is; without a GuruFocus client it raises `PassthroughNoKey` (new), answered 503 "no GuruFocus key: the pe-history pass-through is off"; the GuruFocus client's calls take a slot as the FMP calls do.
- Produces, read: `GET /api/companies/{symbol}/multiples-history` → `{"pe": Series | null, "peForward": Series}` with `Series = {"points": [{"day", "value", "ref"}], "stats": {"avg10y": Figure, "median10y": Figure, "high10y": Figure, "low10y": Figure}, "since": "<date>", "responseId": int | null, "note": str | null}`, `Figure = {"value", "unit": "multiple", "ref"}`. The trailing series is the stored `pe-history` response's rows parsed (a row's date and its P/E; a row at or below zero is a loss and is dropped, the gap kept), fetched through the pass-through when none is stored inside the window; `null` with `note` "no GuruFocus key" when there is no client. The ten years run from ten years before the newest point. The forward series is the log's `pe_forward` by day, the statistics over the rows on file, `since` the first row's day. The refs: `multiple:<symbol>/pe/<date>`, `multiple:<symbol>/pe/avg_10y` (and `median_10y`, `high_10y`, `low_10y`), `multiple:<symbol>/pe_forward/<date>` and the same four statistics; each resolves to a `multiple`.
- Produces, MCP: `multiples_history(symbol)` (a read), `dcf(symbol)` and `pe_history(symbol)` (pass-throughs), each with a one-sentence description.

- [ ] **Step 1: Write the failing tests**

`tests/store/test_multiples.py`: `test_log_and_read` (two days, an upsert on the second, `since`). `tests/refresh/test_run.py`: `test_a_snapshot_logs_its_multiples` (after a full run on the fixture universe, one row per valued company with a price, `pe_forward` present where the result has one, none for a refusal without a price); `tests/refresh/test_run_price.py`: `test_a_reprice_logs_the_multiples_of_the_day` (the row's price is the quote's; the same day's row is replaced). `tests/refresh/test_passthrough.py`: `test_kinds` gains the two; `test_dcf_fetches_two_endpoints`; `test_pe_history_is_reused_for_seven_days` (a second call at six days reuses; at eight days fetches); `test_pe_history_without_a_gurufocus_client_is_no_key`; `test_each_kind_stores_its_call` gains the rows (provider `gurufocus` for `pe-history`). `tests/web/test_company_reads.py`: `test_the_multiples_history_read` (a synthetic `pettm` payload of fourteen years with three zero rows: the points exclude the zeros, `avg10y` over the last ten years' points, `high10y` and `low10y` right, the refs as above; the forward series from three log rows with `since`); `test_loss_rows_are_dropped_from_the_series`; `test_without_a_gurufocus_client_the_trailing_series_is_null`. `tests/reports/test_refs.py`: `test_multiple_refs_resolve` (a point, a statistic, `wrong unit` on a `$` cite, an unknown date unresolved). `tests/vendors/test_fmp.py` and `test_gurufocus.py`: the routes.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/store/test_multiples.py tests/refresh tests/web/test_company_reads.py tests/reports/test_refs.py tests/vendors -q`
Expected: FAIL on the missing store module and kinds.

- [ ] **Step 3: Implement the store, the log hooks, the vendors, the pass-through, the read, the refs and the tools**

The `pettm` payload's shape is judged by content as `normalize_gf` does: the notes say the series rows are OHLC-shaped with a date; parse a row's date and its closing value; a payload without that shape gives no points and a `note` "the series could not be read". `__main__` builds the GuruFocus client with `build_clients`' pieces when `keys.gurufocus` is set and hands it to the `Passthrough`; the server's `close` closes it.

- [ ] **Step 4: Write `docs/method.md` 16.7 and the 16.2 row, run the whole check and commit**

```bash
git add src/fairband/store/multiples.py src/fairband/web src/fairband/refresh src/fairband/vendors src/fairband/reports/refs.py src/fairband/mcp src/fairband/__main__.py docs/method.md tests
git commit -m "Log the multiples at every snapshot and reprice, fetch FMP's DCF and GuruFocus's trailing P/E series as pass-throughs, and serve the multiples history with its refs"
```

---

### Task 7: The report's eleven sections, the references list and the export

**Files:**
- Modify: `src/fairband/reports/check.py` (`HEADINGS`, `STRUCTURE`, `structure_refusal`)
- Modify: `src/fairband/reports/render.py` (`references`, `markdown`, `_appendix_a_tables`'s bridge label column, the chart tables)
- Modify: `src/fairband/reports/refs.py` (`Resolver.describe`)
- Modify: `src/fairband/reports/tables.py` only for a Markdown rendering helper if `render` needs one
- Modify: `src/fairband/web/reports_api.py` (`submit`'s secondary rule, `_report_json`'s `references`, the Markdown route)
- Modify: `docs/method.md` 16.1 (the eleven sections), 16.3 (the structural checks with the secondary rule), 16.6 (the references list and the chart tables)
- Modify: `tests/support/payloads.py` and the report fixtures
- Test: `tests/reports/test_check.py`, `tests/reports/test_render.py`, `tests/reports/test_refs.py`, `tests/web/test_reports_api.py`

**Interfaces:**
- Consumes: Task 4's and Task 6's series and records; `latest_secondary`, `same_snapshot`.
- Produces: `HEADINGS = ("Summary", "The business", "Industry and competition", "Financial performance and health", "The bull case and the bear case", "The thesis", "Valuation", "Price and multiples", "Recent news", "Risks and kill criteria", "Key judgments")`; `FULL_ONLY` unchanged; `STRUCTURE = ("the mode's section count", "the stance word", "the required judgments", "the headings in the spec's order", "a secondary valuation on the snapshot")`; `structure_refusal(mode, stance, section_headings, judgments, route, policy, secondary_on_snapshot: bool, snapshot_id: int)` returning, after the headings, `the report needs a secondary valuation on snapshot <id>` when `secondary_on_snapshot` is false. `submit` computes the flag from `latest_secondary` and `same_snapshot` against the latest snapshot before calling it.
- Produces: `references(conn, report: ReportRow, policy: Policy, tax) -> list[dict]`: `[{"n": 1, "ref": "snapshot:412/price", "source": "snapshot 412, the price, priced 3 Nov 2026"}, ...]` numbered in the order the refs are first cited across the sections, one entry per distinct `ref` (the period is not part of the key); `Resolver.describe(ref) -> str`, one sentence per form: `snapshot:` "snapshot <id>, <path in words>, priced <date>"; `review:` "review <id>, <path in words>"; `secondary:` "secondary valuation <id>, <path in words>"; `sensitivity:` "sensitivity <id>, row <i> column <j>"; `fact:` "the <line> line of <period> on file"; `table:` "the <table> table, <row>, <year>"; `estimate:` "the consensus for <period>, <field>"; `close:` "the close of <date>"; `peer:` "<peer>, <field>"; `finding:` "finding <id>: <source>"; `derived:` "derivation <id>: the <operation> of <a> and <b>"; `response:` "<provider> <endpoint>, observed <date>"; `policy:` "policy <name>, <version>"; `multiple:` "the <trailing|forward> P/E, <date or statistic>". `markdown(report, a, b, refs, tables)`: each cite as `<text>[^n]`; after the last section `## References` with `[^n]: <ref> — <source>` lines; then the appendixes. `_report_json` gains `"references"`. The chart tables in the Markdown, each under its section before the prose, as Markdown tables with the cite rounding of method 16.3: in section 4 the six tables of `financial_tables` (one per part, titled by the table); in section 7 the route's sensitivity grid the report cites and the secondary's grid; in section 8 the trailing and forward P/E statistics and the year-end points of the two series. The JSON does not carry the tables; the page reads the series itself (plan 2).
- Produces, Appendix A: the bridge table gains a `label` column from `LABELS`.

- [ ] **Step 1: Write the failing tests**

`tests/reports/test_check.py`: `test_the_eleven_and_nine_headings`; `test_an_old_heading_names_the_new_one` ("section 5 is headed 'The bull case and the bear case', not 'Life-cycle phase'"); `test_a_report_needs_a_secondary_valuation_on_the_snapshot`. `tests/web/test_reports_api.py`: `test_a_secondary_on_an_older_snapshot_does_not_count` (a secondary, then a revalue, then a submission: 400 with the latest snapshot's id); every submission fixture becomes eleven sections with a secondary on the snapshot. `tests/reports/test_render.py`: `test_the_references_list` (three distinct refs cited five times: three entries, numbered in first-cite order, each `source` as the sentence above); `test_one_number_per_distinct_ref` (the same ref with and without a period: one entry); `test_the_markdown_has_footnote_marks_and_no_ref_in_the_text` (`[^1]` after the first cite's text; no `snapshot:` or `fact:` string before `## References`); `test_the_markdown_carries_the_chart_tables` (section 4's six tables, section 8's statistics table); `test_the_bridge_table_has_labels`. `tests/reports/test_refs.py`: `test_describe` parametrized over every form.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/reports tests/web/test_reports_api.py -q`
Expected: FAIL on the headings and the missing functions.

- [ ] **Step 3: Implement the check, the references, the Markdown and the route**

- [ ] **Step 4: Change `docs/method.md` 16.1, 16.3, 16.6; run the whole check and commit**

```bash
git add src/fairband/reports src/fairband/web/reports_api.py docs/method.md tests
git commit -m "Check the report's eleven sections and its secondary valuation, number every cite as a footnote with a references list, and carry the chart tables in the Markdown"
```

---

### Task 8: The playbook

**Files:**
- Modify: `playbook/fairband-research/SKILL.md`, `reference/tools.md`, `reference/report-template.md`, `reference/citations.md`, `reference/register.md`
- Modify: `README.md` ("Agents over MCP": the tools added and the count)
- Test: `tests/test_playbook.py`

**Interfaces:**
- Consumes: Tasks 1 to 7's tools, refs, headings and refusals.
- Produces: `SKILL.md` with the twelve steps of spec 14, each headed `### <n>. <title>`: 1 Identify yourself; 2 Take the work item; 3 Read the company (`multiples_history` among the reads; an `expiry` item refreshed first); 4 The fundamentals; 5 The news; 6 The cycle (spec 14 step 6: the signs, the position, the findings; the engine does not flag a cyclical); 7 The valuation (the engine's result in words, the candidate judgments); 8 The debate and the thesis (the bull case and the bear case about the business and its outlook, never about inputs; the thesis for every stance, with the four forms of spec 13.1 section 6); 9 The decisions, the overrides and the two values (the overrides from the thesis; for a cyclical the mid-cycle levers of spec 14 step 9; `secondary_valuation` with `drivers` on every report, `parts` where a sum of parts fits; `dcf` as a cross-check; `sensitivity` for the route's grid; `derive`); 10 The stance; 11 The report (the eleven sections; the judgments as the record, `{judgment, decision, override_id?}`); 12 Complete the work item. The rules list gains: the valuation and its detail are in section 7 only, the rest argues the business; the thesis is written for every stance. The overrides table gains the `earnings.cycle_gap` row ("the correction that takes the anchor's earnings to mid-cycle; a positive figure lowers them"). "The secondary valuation" is rewritten for the drivers form first (each driver in words, the ranges from `policy()`, the reinvestment floor, the terminal through the policy's terminal return, the grid, the refusals) with the parts form after it. "The judgments" drops the bull and bear text.
- Produces: `reference/tools.md` in the server's order with `multiples_history`, `dcf`, `pe_history`, `sensitivity` and the new `secondary_valuation` signature; `reference/report-template.md` with the eleven-section table of spec 13.1, the summary page's shape with the thesis after the stance, the section 4 and section 8 guidance (the multiples against their history by the `multiple:` refs; "where the price sits in its year's range" by two `derive` calls), a note that the page draws the charts and the export carries their tables, and a full example submission of eleven sections for an invented company that cites a `secondary:` value, a `multiple:` statistic and a `sensitivity:` cell, with judgments of `{judgment, decision, override_id?}`; `reference/citations.md` with the `multiple:` and `sensitivity:` forms and the secondary's new paths, and a line that the server numbers the footnotes; `reference/register.md` with thesis, cyclical and mid-cycle.
- Produces: `tests/test_playbook.py`'s `STEPS` of twelve with the tools each names (6 names `financial_tables` and `finding_add`; 8 names none; 9 names `override_add`, `override_drop`, `secondary_valuation`, `dcf`, `sensitivity`, `derive`); `TOOL_NAMES` in the server's order; `REF_FORMS` with `multiple` and `sensitivity`; the example passing `structure_refusal` with `secondary_on_snapshot=True` and the token rule; `test_the_skill_has_the_frontmatter_and_the_twelve_steps`.

- [ ] **Step 1: Change the tests**

The names and lists above; `test_the_template_example_passes_the_structural_checks_and_the_token_rule` asserts eleven headings and a judgment without `bull`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_playbook.py -q`
Expected: FAIL on the steps and the tools.

- [ ] **Step 3: Rewrite the playbook files**

In the register of `reference/register.md`: the answer first, short sentences, every term explained the first time; no first person.

- [ ] **Step 4: Run the whole check and commit**

```bash
git add playbook README.md tests/test_playbook.py
git commit -m "Rewrite the playbook around the debate, the thesis and the cycle, with the standard DCF on every report and the eleven-section template"
```

---

### Task 9: Merge and the live steps up to the registration

Not an implementer task: the controller runs it, and every live step waits for the founder's consent (spec 22, as amended).

- [ ] **Step 1: Finish the branch** with superpowers:finishing-a-development-branch: merge to main, push.
- [ ] **Step 2: Back up** `~/.local/share/fairband/fairband.db` as `fairband-before-v9-<date>.db`.
- [ ] **Step 3: Stop the server on 8470 and migrate**: `uv run fairband migrate` applies 005 and 006.
- [ ] **Step 4: Revalue under v9**: `uv run fairband refresh revalue`; the readout checks every mechanical figure against refresh 16 (spec 22).
- [ ] **Step 5: Restart the server** from main on 8470.
- [ ] **Step 6: Register and link**: `claude mcp add --scope user fairband -- uv run --directory <repo> fairband mcp`; link `playbook/fairband-research` under `~/.claude/skills/fairband-research`.
- [ ] **Step 7: Close the backlog**: B-97's row names the drivers form; B-102's citations-table item is closed by the references list; the spec's status line says plan 1b merged. The first live session waits for plan 2.
