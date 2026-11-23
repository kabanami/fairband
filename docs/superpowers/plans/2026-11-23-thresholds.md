# The Thresholds Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New default thresholds (margins of safety 20/30/40%, fair band 0.90 to 1.10, trim multiple 1.35), a word whose first edge is the row's own buy level, and levels and words that follow a changed threshold at the next read with no revalue.

**Architecture:** The three thresholds move no value, so they stop being part of what a row was "valued under". The policy gives the edges of a moat class (`Policy.edges_for`), one engine function gives a record's levels and word from its stored value, its class, a price and the policy in force (`standing_for`), and every reader calls it. The stored levels and word stay in the rows as a record of the day of valuation and are no longer shown.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, pytest, ruff, mypy; plain JavaScript and HTML under `src/fairband/web/static/`.

**Spec:** `docs/superpowers/specs/2026-11-23-thresholds-design.md`. Read it first; this plan argues from it.

## Global Constraints

- Work on a branch `thresholds` in a git worktree: the live server reads page files from the main checkout.
- `uv run` for every command. Before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`. Run each step so a failure shows: no pipe on a lint step.
- A commit message is one plain sentence in the imperative and ends with a `Co-Authored-By: Claude <model> <noreply@anthropic.com>` line naming the model that wrote the change.
- `docs/method.md` and `src/fairband/web/static/methodology.html` change in the same commit as the engine, policy or settings change they describe. A change of method version re-reads the Methodology page's examples.
- The values, exactly: `margin_of_safety` Wide 0.20, Narrow 0.30, None 0.40; `fair_band` [0.90, 1.10]; `trim_multiple` 1.35. The policy is `fairband-policy-v19`; the method is `fairband-mechanical/1.9`.
- No value a share may change on any route. A golden's `value` and its intermediates' value figures stay as they are; only levels, words and RULE inputs of the margin move.
- No schema change: the stored level and word columns stay.
- Never commit a key or vendor data. Test fixtures are synthetic. The README's screenshots stay as they are.
- The merge to main, the restart of the live server, the live revalue and the push wait for the founder's word (Task 7).

## Review Focus

- A stored result with no `moat` in its intermediates (an old snapshot, or a refused row that a secondary valuation fills): the reader shows levels on the moat table's class, and with no class the stored figures; it never raises. Test in Task 3.
- A row with no price or a price of zero: the levels show, price ÷ value and the word are none. Test in Task 2.
- A company in another currency: the levels in force are on the value in US dollars, not on `value_in_currency`. Test in Task 3.
- A snapshot valued under policy v18 that is read under v19 before any revalue: its row shows v19's levels and word. Test in Task 3.
- A stored overlay that the old cross-field rule allowed and the new one refuses (band low 0.75, Wide margin 0.20): the app's error names both settings and says to reset them on the Settings page. Test in Task 5.

---

### Task 1: Policy v19, the three values

**Files:**
- Create: `src/fairband/policy/fairband-policy-v19.toml`
- Modify: `src/fairband/policy/__init__.py` (`_POLICY_FILE`, the module docstring's list of versions)
- Modify: `docs/method.md` (4.1: the rows of `margin_of_safety`, `fair_band`, `trim_multiple` and of the derived edges; 4.10: the figures "at the defaults"; section 11: a row "1.8, policy v19"), `docs/method-overview.md:24,62`
- Modify: `tests/fixtures/golden/*.json` and `tests/fixtures/golden/README.md`
- Test: `tests/policy/test_policy.py`, `tests/engine/test_levels.py`, `tests/engine/test_designation.py`, `tests/policy/test_settings.py`, `tests/test_method_doc.py`, and each test the full suite shows pinned to an old default

**Interfaces:**
- Produces: `load_policy()` returns version `fairband-policy-v19` with the three values. `Policy.designation_edges` still exists and reads `(0.70, 0.90, 1.10, 1.35)`.

- [ ] **Step 1: Write the failing tests**

In `tests/policy/test_policy.py`, beside `test_v17_is_v16_with_two_values_in_and_one_out`:

```python
def test_v19_is_v18_with_the_three_thresholds() -> None:
    v18, v19 = _file_values("fairband-policy-v18.toml"), _file_values("fairband-policy-v19.toml")
    changed = {"margin_of_safety", "fair_band", "trim_multiple"}
    assert v18.keys() == v19.keys()
    assert {k: v19[k] for k in v19.keys() - changed} == {k: v18[k] for k in v18.keys() - changed}
    assert v19["margin_of_safety"]["value"] == {"None": 0.40, "Narrow": 0.30, "Wide": 0.20}
    assert v19["fair_band"]["value"] == [0.90, 1.10]
    assert v19["trim_multiple"]["value"] == 1.35
    for name in changed:
        assert "Morningstar" in v19[name]["source"] and "2026-11-23" in v19[name]["source"]
```

Rename `test_v18_is_the_packaged_policy` to `test_v19_is_the_packaged_policy` with `p.version == "fairband-policy-v19"`, and add a test of v18's own three values read with `_file_values`, in the form of `test_v17_holds_the_moat_thresholds`.

In `tests/engine/test_levels.py`: `levels_for(100.0, "Wide", policy) == Levels(buy=80.0, fair_low=90.0, fair_high=110.0, trim=135.0)` and `levels_for(100.0, "None", policy).buy == 60.0`. In `tests/engine/test_designation.py`: `test_the_policy_holds_the_edges` asserts `(0.70, 0.90, 1.10, 1.35)`; the parametrized test keeps its own literal `EDGES`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/policy/test_policy.py tests/engine/test_levels.py tests/engine/test_designation.py`
Expected: FAIL, the v19 file is missing and the levels are v18's.

- [ ] **Step 3: Add the file and load it**

Copy v18 to `fairband-policy-v19.toml`. Change `[meta] version`, the first comment line to "# Fairband policy v19: …" in v18's form, add a line "# v19: v18 with the margins of safety, the fair band and the trim multiple of the founder's decision of 2026-11-23.", and set the three values. Each `source` reads: `"the founder, 2026-11-23, after Morningstar's Equity Research Methodology (September 2022, Exhibit 4): <which figure>"`, the figure being "the discount for 5 stars at Low, Medium and High uncertainty", "the 3-star range at Medium uncertainty", "the 1-star price at Medium uncertainty". Set `_POLICY_FILE = "fairband-policy-v19.toml"`.

- [ ] **Step 4: Remake the goldens**

Each golden's levels, word and the margin's RULE input change; its `value` must not. Write a one-off script outside the repository that values each fixture as `tests/engine/test_golden.py::test_defaults_match_the_golden` does and writes `golden_dict(result)` in the file's present JSON form. Before writing, assert for each symbol that the new dict's `value` equals the old file's. Add a paragraph to the README: the date, policy v19, the cause, and that no value moved.

- [ ] **Step 5: Change the documents**

`docs/method.md` and `docs/method-overview.md` name the new figures wherever they name the old ones (0.25, 0.35, 0.45, 0.85, 1.15, 1.5, 0.65). `tests/test_method_doc.py` says which sentences it pins.

- [ ] **Step 6: Run the full check and fix each pin of an old default**

Run the full check of Global Constraints. A test that fails only because it holds an old default takes the new figure. A test that fails for another reason stops the task.

- [ ] **Step 7: Commit**

Message: `Set the margins of safety at 20, 30 and 40%, the fair band at 0.90 to 1.10 and the trim multiple at 1.35 under policy v19`

---

### Task 2: The row's own first edge, and one function for levels and word (method 1.9)

**Files:**
- Modify: `src/fairband/policy/__init__.py` (add `Policy.edges_for`)
- Modify: `src/fairband/engine/levels.py` (add `Standing`, `standing_for`)
- Modify: `src/fairband/engine/route.py:589,656`, `src/fairband/engine/secondary.py:232-235`, `src/fairband/web/reviews_api.py:799-802` (the edges of the record's class)
- Modify: `src/fairband/engine/route_steps.py:612-620` (`common_rules`) and `src/fairband/engine/route_decline.py:396`: a result no longer holds the RULE input `margin_of_safety`. A stored copy would show an old margin after a change of the setting; the buy level shows the margin in force (the spec's section 6 left this to the plan)
- Modify: `src/fairband/engine/__init__.py` (`METHOD_VERSION = "fairband-mechanical/1.9"`)
- Modify: `docs/method.md` (4.10: the edges by class and the table of the spec's 5.2; 4.1: the derived-edges row; each route's list of tagged inputs, which loses the margin; section 11: a row "1.9, policy v19"), `src/fairband/web/static/methodology.html` (its examples read again under 1.9; the table of words changes in Task 6)
- Modify: goldens and their README where a word changes
- Test: `tests/engine/test_levels.py`, `tests/engine/test_designation.py`, `tests/engine/test_route.py`, `tests/engine/test_secondary.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: Task 1's policy.
- Produces:

```python
# fairband/policy/__init__.py
class Policy:
    def edges_for(self, moat: Moat) -> tuple[float, float, float, float]:
        """e1 to e4 of a row of class ``moat``: 1 − its margin of safety, the fair band's low and
        high, the trim multiple."""

# fairband/engine/levels.py
@dataclass(frozen=True)
class Standing:
    levels: Levels
    price_to_value: float | None
    designation: Designation | None

def standing_for(value: float, moat: Moat, price: float | None, policy: Policy) -> Standing:
    """A record's levels, price ÷ value and word on ``policy``: ``levels_for(value, moat,
    policy)``; with a price above zero, ``designation_for(price, value, policy.edges_for(moat))``;
    else none for both. ``value`` is above zero: the caller checks."""
```

`Policy.designation_edges` stays until Task 6 for the callers not yet moved.

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_designation.py`:

```python
@pytest.mark.parametrize(
    "moat, edges",
    [
        ("Wide", (0.80, 0.90, 1.10, 1.35)),
        ("Narrow", (0.70, 0.90, 1.10, 1.35)),
        ("None", (0.60, 0.90, 1.10, 1.35)),
    ],
)
def test_the_first_edge_is_the_rows_own_buy_level(moat: Moat, edges: tuple[float, ...]) -> None:
    assert load_policy().edges_for(moat) == pytest.approx(edges)
```

`tests/engine/test_levels.py`:

```python
def test_standing_for_gives_the_rows_own_levels_and_word() -> None:
    goog = standing_for(339.38, "Wide", 264.00, policy)  # the spec's section 7
    assert goog.levels == levels_for(339.38, "Wide", policy)
    assert goog.levels.buy == pytest.approx(271.50, abs=0.005)
    assert goog.levels.trim == pytest.approx(458.16, abs=0.005)
    assert (goog.price_to_value, goog.designation) == (264.00 / 339.38, "well-below")
    assert standing_for(100.0, "Wide", 78.0, policy).designation == "well-below"
    assert standing_for(100.0, "Narrow", 78.0, policy).designation == "below"
    assert standing_for(100.0, "None", 65.0, policy).designation == "below"
    assert standing_for(100.0, "None", 59.0, policy).designation == "well-below"
    for moat in ("Wide", "Narrow", "None"):
        assert standing_for(100.0, moat, 135.0, policy).designation == "well-above"
        assert standing_for(100.0, moat, 134.0, policy).designation == "above"


@pytest.mark.parametrize("price", [None, 0.0, -1.0])
def test_standing_for_without_a_price_gives_the_levels_alone(price: float | None) -> None:
    s = standing_for(100.0, "Wide", price, policy)
    assert s.levels.buy == 80.0 and (s.price_to_value, s.designation) == (None, None)
```

`tests/engine/test_route.py`: for every fixture of `FIXTURES`, `"margin_of_safety" not in {x.name for x in result.inputs}`. And one test that values a fixture of `tests/support/engine_companies.py` twice at a price of 0.78 × its value, once on a Wide row of the moat table and once on a Narrow one, as the file's other tests set a class: the Wide result's `designation` is `"well-below"` and the Narrow one's `"below"`, and both `value`s equal the fixture's value at any price. `tests/engine/test_secondary.py`: the same two words from a secondary valuation at 0.78 × its value a share.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/engine/test_designation.py tests/engine/test_levels.py tests/engine/test_route.py tests/engine/test_secondary.py`
Expected: FAIL, `Policy` has no `edges_for` and `levels` has no `standing_for`.

- [ ] **Step 3: Implement `edges_for` and `standing_for`, and call them**

The three engine call sites and the secondary valuation's way to US dollars (`reviews_api._in_usd`) pass `policy.edges_for(moat)` of the record's class in place of `policy.designation_edges`. `levels_for` and `designation_for` keep their signatures.

- [ ] **Step 4: Move the method to 1.9 and remake what it changes**

Set `METHOD_VERSION`. Remake the goldens, which lose the margin's input and may change a word, by Task 1's script and with its assertion that no `value` moved, and say so in the README. Write `docs/method.md` 4.10, the derived-edges row of 4.1 and the version row. Read the Methodology page's examples again as its tests require (`tests/web/test_methodology.py`).

- [ ] **Step 5: Run the full check, then commit**

Message: `Read Well below from the row's own buy level under method 1.9, and give a record's levels and word by one function`

---

### Task 3: The page reads the levels and the word on the policy in force

**Files:**
- Modify: `src/fairband/web/rows.py` (`screen_row`, `agent_fields`, `_record_levels`, `group_rows`; `standing` goes)
- Modify: `src/fairband/web/app.py:304-376,421-445`, `src/fairband/web/research_api.py:118-135` and its `_review`, `_price_needs`, `_secondary`, `src/fairband/web/company_api.py` (`report_call`)
- Test: `tests/web/test_rows.py`, `tests/web/test_app.py`, `tests/web/test_groups.py`, `tests/web/test_research_api.py`, `tests/web/test_company_page_api.py`

**Interfaces:**
- Consumes: `standing_for`, `Policy.edges_for` (Task 2).
- Produces:

```python
# fairband/web/rows.py
def moat_of(result: ValuationResult) -> Moat | None:
    """The moat class the result was valued on, its intermediates' ``moat``; none without one."""

def screen_row(snapshot, company, today, aging_fraction, watchlists, agents, *, mark_min: int,
               policy: Policy) -> dict[str, Any]: ...

def agent_fields(snapshot, review, secondary, report, cited, today, policy: Policy,
                 table_moat: Moat | None) -> dict[str, Any]: ...

def group_rows(rows, by: str, below_value: float) -> list[dict[str, Any]]: ...
```

`table_moat` is the class of the company's row of the moat table (`store.moat.moat_row`), read by the caller. A record's class is `moat_of` its own result; a secondary valuation's, and a record's with no `moat` in its result, is `table_moat`. With neither, the reader gives the record's stored levels and word.

`screen_row` fills the row's `fairLow`, `fairHigh`, `buyLevel`, `trimLevel`, `priceToValue` and `designation` from `standing_for(snapshot.value, class, snapshot.price, policy)` on a valued row, and `agent_fields` fills its `levels` the same way from the review's or the secondary's value. `group_rows` takes `policy.fair_band[0]`. `GET /api/companies/{symbol}` sends `designationEdges` as `policy.edges_for(class)` of the company's class, none without one; no page file changes. The agents' tools serve the web API's answers (`mcp/server.py`, `FairbandClient`), so they follow with no change of their own, and `tests/mcp/` stays green.

- [ ] **Step 1: Write the failing tests**

In `tests/web/test_rows.py`, on the file's own snapshot and review fixtures:

```python
def test_a_mechanical_row_reads_its_levels_on_the_policy_in_force() -> None:
    changed = apply_overlay(policy, {"trim_multiple": 1.2, "fair_band": [0.95, 1.05]})
    row = screen_row(SNAPSHOT, None, TODAY, 2 / 3, (), NO_AGENT_FIELDS, mark_min=3, policy=changed)
    value = SNAPSHOT.value
    assert row["trimLevel"] == pytest.approx(value * 1.2)
    assert (row["fairLow"], row["fairHigh"]) == pytest.approx((value * 0.95, value * 1.05))
    assert row["fairValue"] == row["mechanical"] == value
    expected = standing_for(value, moat_of(SNAPSHOT.result), SNAPSHOT.price, changed)
    assert (row["priceToValue"], row["designation"]) == (expected.price_to_value, expected.designation)
```

Add, in the same form, with the names the file's fixtures have:

- a snapshot stored under policy v18 (`policy_version="fairband-policy-v18"`, its stored levels v18's) reads v19's levels under `load_policy()`;
- a Wide reviewed row at a price of 0.78 × the review's value has `designation == "well-below"` in `agent_fields(...)["levels"]`, and a Narrow one `"below"`;
- a result with no `moat` in its intermediates reads its levels on `table_moat`, and with `table_moat=None` gives the stored `buy_level`, `fair_low`, `fair_high`, `trim_level`, `price_to_value` and `designation` and does not raise;
- a snapshot in another currency (`fx_rate` in its intermediates, as the file's foreign fixture) has `buyLevel == pytest.approx(snapshot.value * 0.80)` on a Wide row, `snapshot.value` being the US dollar value;
- a row with no price has its four levels and `priceToValue is None`.

In `tests/web/test_app.py`: after `write_settings(conn, {"trim_multiple": 1.2}, None, at)` with no refresh, `GET /api/screen` gives the row a `trimLevel` of 1.2 × its value; and `GET /api/companies/{symbol}` gives `designationEdges == list(policy.edges_for(<the fixture's class>))`. In `tests/web/test_groups.py`: `group_rows(rows, "sector", 0.90)` counts as below value the rows under 0.90.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/web/test_rows.py tests/web/test_app.py tests/web/test_groups.py`
Expected: FAIL, `screen_row` takes no `policy`.

- [ ] **Step 3: Implement the readers**

`rows.standing` and the `edges` parameters go; every level and word on the screen, in the drawer's records and in the report's call comes from `standing_for`. `app.py`'s `screen_rows` reads `moat_row` for the companies in `records` alone.

- [ ] **Step 4: Run the full check, then commit**

Message: `Read every row's levels and word on the policy in force, on the screen, in the drawer and on the company page`

---

### Task 4: The references and the command line read the levels in force

**Files:**
- Modify: `src/fairband/reports/refs.py:790-853` (`_snapshot`, `_review`, `_secondary`: the `levels` case), `src/fairband/__main__.py:292,348-361`
- Test: `tests/reports/test_refs.py`, `tests/reports/test_check.py`, `tests/test_cli_mcp.py` or the file that tests `_snapshot_line`

**Interfaces:**
- Consumes: `standing_for` (Task 2), `rows.moat_of` (Task 3), `store.moat.moat_row`.
- Produces: `snapshot:<id>/levels/<name>`, `review:<id>/levels/<name>` and `secondary:<id>/levels/<name>` resolve to `levels_for(the record's value, its class, the resolver's policy)`, the class found as Task 3 finds it, the stored level where no class is known. `/value` and `/price_to_value` stay the stored figures. `_snapshot_line(symbol, snapshot, policy)` prints the word and the ratio figure on `policy.edges_for(class)`.

- [ ] **Step 1: Write the failing tests**

`tests/reports/test_refs.py`, on the file's stored snapshot, review and secondary valuation:

```python
def test_a_level_ref_reads_the_policy_in_force(conn: sqlite3.Connection) -> None:
    changed = apply_overlay(policy, {"trim_multiple": 1.2})
    for ref, value in (
        (f"snapshot:{SNAPSHOT_ID}/levels/trim", SNAPSHOT_VALUE),
        (f"review:{REVIEW_ID}/levels/trim", REVIEW_VALUE),
        (f"secondary:{SECONDARY_ID}/levels/trim", SECONDARY_VALUE),
    ):
        assert _resolve(conn, ref, changed).value == pytest.approx(value * 1.2)
        assert _resolve(conn, ref, policy).value == pytest.approx(value * 1.35)
```

with the file's own ids and values in place of the capitals. In `tests/reports/test_check.py`: a cite of `review:<id>/levels/buy` written as the figure in force passes, and the same cite written as the stored figure of an older policy fails as a unit mismatch does today. For the command line: `_snapshot_line` of a Wide snapshot at 0.78 × its value ends `well-below (0.78 × value)`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/reports/test_refs.py tests/reports/test_check.py`
Expected: FAIL, the refs give the stored levels.

- [ ] **Step 3: Implement, run the full check, commit**

Message: `Resolve a cited level on the policy in force, and print the command line's word on the row's own edges`

---

### Task 5: The three thresholds take effect at once and leave the settings hash

**Files:**
- Modify: `src/fairband/policy/settings.py:124-153` (the three `Setting` rows), `:637-646` (`check`)
- Modify: `docs/method.md` (4.1: which settings enter the hash and the three rows' effect; section 10: a change of a threshold needs no revalue)
- Test: `tests/policy/test_settings.py`, `tests/store/test_settings_overlay.py`, `tests/web/test_settings_api.py`, `tests/web/test_reviews_api.py`

**Interfaces:**
- Produces: the settings `margin_of_safety`, `fair_band` and `trim_multiple` have `effect="at once"` and `hashed=False`. The margin's description is "The discount to the value that sets the buy level; a price under a row's buy level reads Well below." The cross-field rule reads `low > 1 - p.margin_of_safety["Wide"]`, and its error is "margin_of_safety, fair_band: the band's low must be above 1 − the Wide margin of safety".

- [ ] **Step 1: Write the failing tests**

`tests/policy/test_settings.py`:

```python
THRESHOLDS = {"margin_of_safety", "fair_band", "trim_multiple"}


def test_a_threshold_takes_effect_at_once_and_is_not_hashed() -> None:
    for name in THRESHOLDS:
        assert (setting(name).effect, setting(name).hashed) == ("at once", False)
    assert settings_hash({"trim_multiple": 1.2, "fair_band": [0.95, 1.05]}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"required_return": 0.1, "trim_multiple": 1.2}) == settings_hash(
        {"required_return": 0.1}
    )


def test_the_bands_low_is_above_every_class_buy_level() -> None:
    wide = {"None": 0.40, "Narrow": 0.30, "Wide": 0.20}
    apply_overlay(load_policy(), {"margin_of_safety": wide, "fair_band": [0.81, 1.10]})
    with pytest.raises(ValueError, match="the band's low must be above 1 − the Wide margin"):
        apply_overlay(load_policy(), {"margin_of_safety": wide, "fair_band": [0.75, 1.10]})
```

`test_hash_covers_valuation_flags_and_the_fallback_only` takes `- THRESHOLDS` on its right side. In `tests/store/test_settings_overlay.py`: with a stored overlay of `fair_band` [0.75, 1.10] over the defaults, `effective_policy(conn)` raises a `ValueError` whose text holds "margin_of_safety, fair_band" and "reset it on the Settings page". In `tests/web/test_reviews_api.py`: after `write_settings(conn, {"trim_multiple": 1.2}, None, at)` on a store whose snapshot was valued under the defaults, an override's `POST` answers 201, not the 409 "settings changed: run a revalue". In `tests/web/test_settings_api.py`: after that save, the answer's `valuedUnder` says the screen's figures are current.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/policy/test_settings.py tests/store/test_settings_overlay.py tests/web/test_settings_api.py tests/web/test_reviews_api.py`
Expected: FAIL, the three are hashed with the effect "revalue".

- [ ] **Step 3: Change the three rows and the rule, and the method document**

- [ ] **Step 4: Run the full check, then commit**

Message: `Take the margin of safety, the fair band and the trim multiple out of the settings hash, so a change of one shows at once`

---

### Task 6: One source for the edges, the Methodology page, the documents and the backlog

**Files:**
- Modify: `src/fairband/policy/__init__.py` (remove `designation_edges`; the docstring's line 11), `src/fairband/web/policy_rows.py:50-58` (`DERIVED` loses `designation_edges`), `src/fairband/reports/refs.py` (the module docstring's examples)
- Modify: `src/fairband/web/static/methodology.html:388-399` (the table of the five words, by the spec's 5.2, each figure a `data-policy` span of `fair_band.0`, `fair_band.1` or `trim_multiple`, the first two rows naming the buy level), and the paragraph on the settings where it says a change needs a revalue
- Modify: `docs/method.md` (4.10: "The levels are computed once at valuation…" becomes the rule of the spec's 5.3; 14.5: a reviewed row's levels; every sentence left that names `designation_edges` or one first edge for all), `docs/method-overview.md`
- Modify: `docs/backlog.md` (a Done row B-289, "The thresholds", with the commits of this plan, and each deferred minor of its reviews as a row or a clause)
- Test: `tests/engine/test_designation.py`, `tests/policy/test_settings.py`, `tests/web/test_settings_api.py:354,408,425`, `tests/web/test_methodology.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: every caller moved in Tasks 2 to 5.
- Produces: no `Policy.designation_edges`; `GET /api/settings` and the Methodology page's values hold no `designation_edges`.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_policy_has_one_way_to_the_edges() -> None:
    assert not hasattr(load_policy(), "designation_edges")
```

In `tests/web/test_settings_api.py`: `"designation_edges" not in body["values"]`. In `tests/web/test_methodology.py`: the page holds no `data-policy="designation_edges.` span, and the table's five rows hold the words "buy level", `fair_band.0`, `fair_band.1` and `trim_multiple`. `tests/policy/test_settings.py::test_apply_overlay_changes_the_value_and_the_derived_edges` asserts `p.edges_for("Narrow") == pytest.approx((0.70, 0.8, 1.2, 1.35))` and that the hash is `settings_hash({"required_return": 0.1})`.

- [ ] **Step 2: Run them to see them fail, then remove the property and write the page and the documents**

Run: `uv run pytest -q tests/engine/test_designation.py tests/web/test_settings_api.py tests/web/test_methodology.py tests/policy/test_settings.py`
Expected first: FAIL, the property exists. `uv run mypy src` finds a caller that Tasks 2 to 5 missed.

- [ ] **Step 3: Run the full check, then commit**

Message: `Give the edges by moat class alone, and say on the Methodology page and in the method that the levels and the word follow the settings in force`

---

### Task 7: Acceptance, then going live on the founder's word

Not a task for a subagent. The controller does it.

- [ ] **Step 1: Accept on a scratch database in a headless browser** (a copy of the live store, a spare port, the cached Playwright and Chromium). Check, in both themes: GOOG's reviewed row reads "Well below" with a buy level of $271.50 and a trim level of $458.16; a save of a trim multiple of 1.2 on the Settings page changes the screen's rows with no refresh run and no notice that asks for a revalue; the Methodology page's table of words shows the buy level and the figures in force; the drawer's price ÷ value figure stays inside its word's band at an edge.
- [ ] **Step 2: Run a whole-branch review**, then fix what it finds.
- [ ] **Step 3: Ask the founder** for the merge, the restart, the revalue and the push.
- [ ] **Step 4: Go live.** Merge to main. Restart the live server by the safe way of the filings-access build. On the Settings page, reset `margin_of_safety` and `fair_band`, which equal v19's defaults. Run one revalue, which the new policy version needs. Check that the screen's rows carry policy v19 and method 1.9, and that AMD, GOOG and one None row read the words of the spec's section 7. Push.
