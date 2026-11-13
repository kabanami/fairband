# The Research Round, plan 1: what the store already holds, read better Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build sections 6 to 11a of the research round spec under method 1.3 and policy v13: the consensus read from one vendor answer, a period-tied correction that follows its period, the two stock-pay notes and the two stock-pay inputs, the share-count warning, the thin-consensus note, the runway range to 500% and the ten-year median margins; then one revalue and its readout. The balance sheet and the minority interest (spec sections 12 and 13) are plan 2.

**Architecture:** Assembly (`refresh/inputs.py`, `refresh/inputs_statements.py`) gains the one-answer read and three new facts for the engine: the trailing tax lines, the stock-pay history and each fiscal year's net income. The engine gains four flag functions in `engine/flags.py`, two keyword inputs on `anchor.ntm_anchor`, two override tags in `engine/overrides.py`, and two entries that every routed result carries (`trailing_end`, `margin_history`), added once in `engine/route.py`. The drop rule changes in one function, `refresh/reviews._drop_reason`. No value-bearing formula changes: a value moves only where the consensus rows read are different rows.

**Tech Stack:** Python 3.13, uv, pytest, mypy, ruff; FastAPI web; the playbook's Markdown.

**Spec:** `docs/superpowers/specs/2026-11-13-research-round-design.md` (sections 5 to 11a, 14 to 19). Read it before any task; where this plan and the spec differ, the spec governs and the difference is a finding to report.

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- `docs/method.md` changes in the same commit as the engine, the classifier, the universe rule or a policy value it describes; the Methodology page (`src/fairband/web/static/methodology.html`) with it. Where documents disagree, `docs/method.md` describes what runs.
- Method version `fairband-mechanical/1.3`; policy `fairband-policy-v13`; `fairband-policy-v12.toml` stays byte-identical; no new setting; no database migration.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic or hand-trimmed.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- Every dispatched subagent, reviewers included, runs on Opus 5.5 at xhigh (the founder's standing instruction of 2026-11-10).
- The goldens (`tests/fixtures/golden/`): no value, level, designation, refusal or existing intermediate of any golden moves in this plan. A golden changes only by gaining the new intermediates and, where a rule fires, a new flag. Each re-capture adds a paragraph to `tests/fixtures/golden/README.md` naming its cause, as the earlier ones did.
- No vendor call and no touch of `~/.local/share/fairband` before Task 9, and none there without the founder's word.
- Work in a git worktree (superpowers:using-git-worktrees), not in the main checkout: research sessions load code from it.

## Review Focus

- A newest estimate answer that holds fewer periods than an older one (FMP dropped a far year): the older answer's row is not revived, and a step with no row is absent as the path already handles a missing step. Test in Task 2.
- A price refresh after the revalue: the four new flags, `trailing_end`, `sbc_ttm` and `margin_history` survive the reprice as the valuation wrote them. Test in Task 6.
- A period-tied override made on a snapshot with no trailing period to read (a refused row, or a result from before 1.3 whose inputs cite none): the first test of spec 11a cannot be read, so only the changed-reading test decides, and nothing raises. Test in Task 3.
- A half-yearly reporter: the NTM window holds two periods, so `thin-ntm` counts two, and the trailing tax sums two half-years. Tests in Tasks 4 and 7.
- A company in another currency: `earnings.sbc` is a total in the reporting currency and its range is read at the rate; `share-count-gap` compares the quote's market cap and price, both in US dollars. Tests in Tasks 5 and 6.

---

### Task 1: Policy v13 and method 1.3

**Files:**
- Create: `src/fairband/policy/fairband-policy-v13.toml` (a copy of v12 with the changes below)
- Modify: `src/fairband/policy/__init__.py` (`_POLICY_FILE`, four fields, four reads), `src/fairband/policy/settings.py` (`check`), `src/fairband/web/policy_rows.py` (the four rows), `src/fairband/engine/__init__.py` (`METHOD_VERSION`)
- Modify: `docs/method.md` 4.1 (four rows), 11 (the 1.3 row), 14.2 (the `return.runway` range); `src/fairband/web/static/methodology.html` where it prints the range or the version
- Test: `tests/policy/test_policy.py`, `tests/policy/test_settings.py`, `tests/engine/test_overrides.py`, `tests/web/test_sensitivity_api.py`, and every test that pins `fairband-policy-v12` or `mechanical/1.2` (grep both)

**Interfaces:**
- Produces: `Policy.sbc_material_share: float` (0.02), `Policy.sbc_basis_tax_share: float` (0.5), `Policy.sbc_basis_gap_multiple: float` (10.0), `Policy.share_count_gap_band: tuple[float, float]` ((0.7, 1.3)); `Policy.override_ranges["return.runway"] == (0.0, 5.0)`, `Policy.override_ranges["earnings.sbc"] == (0.0, 1e15)`; `METHOD_VERSION == "fairband-mechanical/1.3"`.

- [ ] **Step 1: Write the failing tests** in `tests/policy/test_policy.py`, beside `test_v12_is_the_packaged_policy` and `test_v12_is_v11_with_the_cap_added`:

```python
V13_VALUES = {
    "sbc_material_share",
    "sbc_basis_tax_share",
    "sbc_basis_gap_multiple",
    "share_count_gap_band",
}


def test_v13_is_the_packaged_policy() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v13"
    assert (p.sbc_material_share, p.sbc_basis_tax_share, p.sbc_basis_gap_multiple) == (
        0.02,
        0.5,
        10.0,
    )
    assert p.share_count_gap_band == (0.7, 1.3)
    assert p.override_ranges["return.runway"] == (0.0, 5.0)
    assert p.override_ranges["earnings.sbc"] == (0.0, 1e15)


def test_v13_is_v12_with_the_four_values_added_and_two_ranges() -> None:
    """Every v12 value loads unchanged from v13 but the override ranges, which gain
    ``earnings.sbc`` and widen ``return.runway``; each new value's source names the spec."""
    v12 = _file_values("fairband-policy-v12.toml")
    v13 = load_policy().raw["values"]
    assert v13.keys() - v12.keys() == V13_VALUES
    kept = v12.keys() - {"override_ranges"}
    assert {k: v13[k] for k in kept} == {k: v12[k] for k in kept}
    old, new = v12["override_ranges"]["value"], v13["override_ranges"]["value"]
    assert new == old | {"return.runway": [0.0, 5.0], "earnings.sbc": [0.0, 1e15]}
    for name in V13_VALUES:
        assert "spec 2026-11-13" in v13[name]["source"], name
```

In `tests/engine/test_overrides.py`, beside the range tests of `return.runway`:

```python
def test_the_runway_return_takes_up_to_500_percent(policy: Policy) -> None:
    assert check_input("return.runway", 3.326, "mature-growth", policy) == ("applied", "")
    assert check_input("return.runway", 5.0, "mature-growth", policy) == ("applied", "")
    state, sentence = check_input("return.runway", 5.01, "mature-growth", policy)
    assert state == "refused-unit" and "500" in sentence
    assert check_input("return.runway", 0.0, "mature-growth", policy)[0] == "refused-unit"
```

In `tests/web/test_sensitivity_api.py`, beside the test that posts a `return.runway` axis: an axis `[0.2, 3.326]` answers 201 and its second row holds values, not a refusal.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/policy/test_policy.py tests/engine/test_overrides.py -k "v13 or 500"`
Expected: FAIL (`fairband-policy-v12`; no attribute `sbc_material_share`; 3.326 refused).

- [ ] **Step 3: Create the policy file and read it.** Copy v12 to v13, set the version, add the four values under `[values.<name>]` each with `value` and a `source` that reads "spec 2026-11-13, section 7.1" (the three stock-pay values) or "section 8" (the band, `value = [0.7, 1.3]`), and change the two ranges. In `policy/__init__.py` point `_POLICY_FILE` at v13 and add the four fields and reads (the band reads as the other two-number values do). In `settings.check`: each share and the tax share in 0 to 1, the multiple above 0, the band's low below 1 and its high above 1. Add the four rows to `web/policy_rows.py` in the form its neighbours have. Set `METHOD_VERSION`.

- [ ] **Step 4: Update the version pins and the documents.** Every test that pins the old version strings moves to the new ones. `docs/method.md`: four rows in 4.1's table, each marked not a setting; the 1.3 row in 11, one sentence for each change of spec section 1's plan 1 (write the row whole now; later tasks do not touch it); 14.2's `return.runway` row reads "above 0% to 500%". The Methodology page where it prints that range.

- [ ] **Step 5: Run the four checks, then commit**

```bash
git add -A
git commit -m "Name method 1.3 and policy v13, with the stock-pay and share-count thresholds and a runway return that takes up to 500%"
```

---

### Task 2: The consensus from one answer (spec 6)

**Files:**
- Modify: `src/fairband/store/observations.py` (new function), `src/fairband/refresh/inputs.py` (`build_inputs`' `read`, the module docstring)
- Modify: `docs/method.md` 2, 5.2, 5a.2
- Test: `tests/store/test_observations.py`, `tests/refresh/test_inputs.py`, `tests/web/test_company_reads.py`, `tests/reports/test_refs.py`

**Interfaces:**
- Produces: `observations.answer_observations(conn: sqlite3.Connection, symbol: str, dataset: str) -> list[ObservationRow]`: every row of the newest response (the largest `response_id`) that holds a row of `dataset` for `symbol`, ordered by period then field; empty when none. `build_inputs` reads `estimate-annual` and `estimate-quarter` through it and every other dataset through `observations_for`, as now.

- [ ] **Step 1: Write the failing tests.**

`tests/store/test_observations.py`:

```python
def test_answer_observations_reads_one_answer(conn: sqlite3.Connection) -> None:
    """Two answers of one dataset whose periods differ by a day: the newest answer's rows alone
    come back, whatever the older answer holds; another dataset and another company are apart."""
    old = _answer(conn, "AAPL", "estimate-quarter", {"2027-06-27": 2.098, "2027-09-27": 2.21})
    new = _answer(conn, "AAPL", "estimate-quarter", {"2027-06-26": 2.059})
    _answer(conn, "AAPL", "estimate-annual", {"2027-09-27": 9.555})
    _answer(conn, "MSFT", "estimate-quarter", {"2027-06-30": 3.5})
    found = answer_observations(conn, "AAPL", "estimate-quarter")
    assert [(r.period, r.value, r.response_id) for r in found] == [
        (date(2027, 6, 26), Decimal("2.059"), new)
    ]
    assert old < new
    assert answer_observations(conn, "AAPL", "split") == []
```

`_answer` is a helper of the test module: it records a response with `store.vendor.record_response` and inserts one `eps_avg` row for each period with `insert_observations`, returning the response id.

`tests/refresh/test_inputs.py`, after `test_one_consensus_row_per_fiscal_period`, on `_on_a_september_year`:

```python
def test_the_consensus_is_one_answer_s_rows(store: Store, clock: Clock) -> None:
    """FMP moved the period ends by a day between two answers. The older answer's rows have
    more analysts; they are not read, and a far year only the older answer held is not
    revived."""
    _on_a_september_year(
        store,
        quarters=[
            {"date": "2026-12-27", "epsAvg": 2.9, "numAnalystsEps": 13},
            {"date": "2027-03-27", "epsAvg": 2.2, "numAnalystsEps": 10},
        ],
        years=[
            {"date": "2027-09-27", "epsAvg": 9.5, "numAnalystsEps": 30},
            {"date": "2028-09-27", "epsAvg": 10.6, "numAnalystsEps": 22},
        ],
    )
    clock.now += timedelta(days=2)  # past the reuse window: the next fetch asks FMP again
    newer = {
        "estimates-quarter": [
            {"date": "2026-12-26", "epsAvg": 2.8, "numAnalystsEps": 6},
            {"date": "2027-03-26", "epsAvg": 2.1, "numAnalystsEps": 6},
        ],
        "estimates-annual": [{"date": "2027-09-26", "epsAvg": 9.4, "numAnalystsEps": 28}],
    }
    conn = store(company=False, **newer)  # the statements' bodies stay as the first call set them
    inputs = build(conn)
    assert [(q.period_end, q.eps, q.analysts) for q in inputs.quarter_estimates] == [
        (date(2026, 12, 26), 2.8, 6),
        (date(2027, 3, 26), 2.1, 6),
    ]
    assert [(a.period_end, a.eps, a.analysts_eps) for a in inputs.annual_estimates] == [
        (date(2027, 9, 26), 9.4, 28)
    ]
```

Add the same two-answer setup once to `tests/web/test_company_reads.py` (beside the test of HGCO's two rows a day apart: `/estimates` answers the newer rows alone) and once to `tests/reports/test_refs.py` (an `estimate:` ref of the moved fiscal year resolves the newer figure).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/store/test_observations.py tests/refresh/test_inputs.py -k "one_answer"`
Expected: FAIL (no `answer_observations`; the quarters read `2.9` on 13 analysts).

- [ ] **Step 3: Implement `answer_observations`**, and in `build_inputs` make `read` use it for the two estimate datasets (a module constant names them). Keep `_one_per_period` and the skip of a row within `SAME_PERIOD_DAYS` after the trailing period end as they are.

- [ ] **Step 4: Run the tests of Step 1 and the files they live in; all pass.** `test_one_consensus_row_per_fiscal_period` still passes: its two rows a day apart come in one answer, which the guard still merges.

- [ ] **Step 5: Correct the documents.** `docs/method.md` 2, 5.2 and 5a.2: the consensus is read from the newest answer that holds rows; the words "FMP's two fiscal calendars" go, and the seven-day merge is described as a guard for two rows of one period inside one answer. `refresh/inputs.py`'s docstring the same.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Read each estimate dataset from the newest vendor answer that holds rows, so a period FMP moved keeps no old row"
```

---

### Task 3: The life of a period-tied correction (spec 11a)

**Files:**
- Modify: `src/fairband/engine/route.py` (`_valued`, `_refuse`), `src/fairband/refresh/reviews.py` (`_drop_reason`, `_follow`, the constants, the module docstring)
- Modify: `docs/method.md` 14.1, 14.6; `playbook/fairband-research/SKILL.md` where it says when a period-tied override ends; every other place that prints the old sentence (grep "statements moved past")
- Test: `tests/refresh/test_reviews_follow.py`, `tests/engine/test_route.py`, the goldens

**Interfaces:**
- Produces: every result of `value_company` whose inputs have trailing figures carries `intermediates["trailing_end"]`, the trailing period end as an ISO date string. `reviews.NEWER = "a newer period is on file than the one the override corrected"`; `reviews.MOVED` is gone. `reviews._trailing_end(result: ValuationResult) -> date | None`: `intermediates["trailing_end"]` when present, else the `as_of` of the first of the inputs `revenue_ttm`, `eps_ttm`, `operating_income_ttm` that cites one, else `None`.

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_reviews_follow.py`. Replace the module's `MOVED` constant with `NEWER = "a newer period is on file than the one the override corrected"`. Replace `test_a_period_tied_override_drops_when_the_data_date_moves` with the first test below, and add the others beside `test_a_period_tied_override_follows_its_line`, whose `follow` helper and override they reuse (lift the helper to module level).

```python
def test_a_period_tied_override_stays_when_the_same_statements_are_fetched_again(
    env_valued: Env,
) -> None:
    """A full refresh past the reuse window fetches AXLE's statements again and moves its data
    date; the statements hold the same periods, so the correction stays applied."""
    env = env_valued
    cash = _override(env, "AXLE", "balance.cash", 120.0, "period-tied", None)
    made_on = env.snapshot("AXLE")
    env.clock.now += timedelta(days=2)
    env.refresh().run("full")
    assert env.snapshot("AXLE").data_date > made_on.data_date
    with closing(env.connect()) as conn:
        kept = override_row(conn, cash)
        review = latest_review(conn, "AXLE")
    assert kept is not None and kept.state == "applied"
    assert review is not None and review.override_ids == (cash,)


def test_a_period_tied_override_drops_when_a_newer_period_is_on_file(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """HGCO reports a new quarter: the trailing period end moves from 30 Sep to 31 Dec, and the
    correction of the old period drops, though the cash line reads the same."""
    cash, follow, inputs = _hgco_with_a_cash_correction(conn, policy)
    assert follow(inputs) is not None
    later = replace(inputs.trailing, period_end=inputs.trailing.period_end + timedelta(days=92))
    assert follow(replace(inputs, trailing=later)) is None
    dropped = override_row(conn, cash)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", NEWER)


def test_an_override_on_a_snapshot_from_before_1_3_is_judged_by_its_inputs(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A result stored before 1.3 has no ``trailing_end``; the period is the ``as_of`` its
    trailing inputs cite. A result that cites none decides on the reading alone."""
    cash, follow, inputs = _hgco_with_a_cash_correction(conn, policy, strip="trailing_end")
    later = replace(inputs.trailing, period_end=inputs.trailing.period_end + timedelta(days=92))
    assert follow(replace(inputs, trailing=later)) is None
    dropped = override_row(conn, cash)
    assert dropped is not None and dropped.drop_reason == NEWER

    bare, follow, inputs = _hgco_with_a_cash_correction(
        conn, policy, strip="trailing_end", keep_inputs=("price", "shares_diluted", "cash")
    )
    assert follow(replace(inputs, trailing=later)) is not None  # no period to read: it stays
    found = override_row(conn, bare)
    assert found is not None and found.state == "applied"
```

`_hgco_with_a_cash_correction(conn, policy, strip=None, keep_inputs=None)` is the setup of `test_a_period_tied_override_follows_its_line` as a helper: it values `high_growth_inputs()`, stores the snapshot the override is made on (with the named intermediate removed, and its inputs cut to `keep_inputs` when given), inserts the period-tied `balance.cash` override, and returns its id, the `follow` function and the inputs.

In `tests/engine/test_route.py`: a valued result and a result refused in its route each carry `intermediates["trailing_end"] == inputs.trailing.period_end.isoformat()`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/refresh/test_reviews_follow.py tests/engine/test_route.py -k "period_tied or before_1_3 or trailing_end"`
Expected: FAIL (the refetch drops the override with the old sentence; no `NEWER`; no `trailing_end`).

- [ ] **Step 3: Implement.** In `engine/route.py`, `_valued` and `_refuse` add `trailing_end` to the intermediates when `i.trailing` is not `None`. In `refresh/reviews.py`: `_drop_reason(conn, override, result, base, trailing_end: date | None) -> str | None` drops a period-tied override with `NEWER` when both period ends are known and the new one is later, else with `CHANGED` on a changed reading; the data date is not read. `_follow` passes `inputs.trailing.period_end`. Remove `MOVED`.

- [ ] **Step 4: Run the tests; all pass. Re-capture the goldens**, which gain `trailing_end` and nothing else; confirm the diff is that one added key in each file, and add the README paragraph.

- [ ] **Step 5: Correct the documents.** `docs/method.md` 14.6: the two tests of spec 11a in their order with their sentences, and that the day of a fetch drops nothing; 14.1's line on a period-tied lifetime. The playbook: a period-tied override holds until the company reports a new period or the figure it corrected changes.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Drop a period-tied override when a newer period is on file or its reading changed, not when the statements are fetched again"
```

---

### Task 4: The two stock-pay notes (spec 7.1)

**Files:**
- Modify: `src/fairband/engine/anchor.py` (`TrailingFigures`, new `StockPayHistory`), `src/fairband/engine/route.py` (`CompanyInputs`), `src/fairband/refresh/inputs_statements.py` (`_lines`, `Statements`, `statements_for`), `src/fairband/refresh/inputs.py` (`build_inputs`), `src/fairband/engine/flags.py` (two functions), `src/fairband/engine/route_mature_growth.py` (the flags)
- Modify: `docs/method.md` 4.2, 5.11, 8; the Methodology page's flag list
- Test: `tests/engine/test_flags.py`, `tests/engine/test_route.py`, `tests/refresh/test_inputs.py`, `tests/web/test_methodology.py`

**Interfaces:**
- Produces:
  - `TrailingFigures.income_tax: float | None = None` and `.pretax_income: float | None = None`, the trailing periods' `incomeTaxExpense` and `incomeBeforeTax` summed as the other lines are (`None` when a period lacks the line).
  - `anchor.StockPayHistory(zero_periods: int, newest_year: int | None, newest_figure: float | None)`: how many trailing periods hold a stock pay of exactly zero, and the newest fiscal year whose stock pay is above zero with its figure. `CompanyInputs.stock_pay: StockPayHistory | None = None`.
  - `flags.stock_pay_missing_flag(sbc_ttm: float | None, history: StockPayHistory | None, currency: str = "USD") -> Flag | None`, code `stock-pay-missing`, label "Stock pay missing".
  - `flags.sbc_basis_uncertain_flag(basis: SbcBasis, t: TrailingFigures, street_ttm_eps: float | None, shares: float, tax_rate: float, large_nri: bool, policy: Policy) -> Flag | None`, code `sbc-basis-uncertain`, label "Stock-pay basis uncertain", one sentence for each reason that holds, joined by a space.

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_flags.py`, on the module's `trailing()` helper. The figures: 96 million shares, a statutory rate of 25%, a trailing stock pay of $32 million, so the after-tax stock pay a share is 32 × 0.75 ÷ 96 = $0.25.

```python
_T = replace(trailing(), sbc=32e6, eps_diluted=12.5, income_tax=100.0, pretax_income=800.0)


def _uncertain(
    basis: SbcBasis, t: TrailingFigures = _T, street: float = 12.5, nri: bool = False
) -> Flag | None:
    return sbc_basis_uncertain_flag(basis, t, street, 96e6, 0.25, nri, load_policy())


def test_stock_pay_missing_names_the_newest_year_above_zero() -> None:
    history = StockPayHistory(zero_periods=0, newest_year=2024, newest_figure=69.8e6)
    flag = stock_pay_missing_flag(0.0, history)
    assert flag is not None and flag.code == "stock-pay-missing"
    assert "fiscal 2024" in flag.sentence and "$69.8 million" in flag.sentence
    one_quarter = StockPayHistory(zero_periods=1, newest_year=2025, newest_figure=1.33e9)
    assert stock_pay_missing_flag(1.0e9, one_quarter) is not None
    # a history of zeros, a full trailing figure, an unknown figure: silent
    assert stock_pay_missing_flag(0.0, StockPayHistory(4, None, None)) is None
    assert stock_pay_missing_flag(84.1e6, StockPayHistory(0, 2025, 80e6)) is None
    assert stock_pay_missing_flag(None, history) is None
    assert stock_pay_missing_flag(0.0, None) is None


def test_the_basis_is_uncertain_on_a_one_time_item() -> None:
    """Reason 1: the test reads includes-sbc, the stock pay is material (0.25 is 2% of a street
    EPS of 12.5, the edge) and large-nri is on the row."""
    taxed = replace(_T, income_tax=200.0)  # a full tax, so reason 2 is out of the way
    assert _uncertain("includes-sbc", t=taxed, nri=True) is not None
    assert _uncertain("includes-sbc", t=taxed, nri=True, street=12.6) is None  # 0.25 is below 2%
    assert _uncertain("includes-sbc", t=taxed) is None  # no reason holds


def test_the_basis_is_uncertain_on_a_low_tax() -> None:
    """Reason 2: a trailing tax of 100 on a pre-tax income of 800 is 12.5%, half of 25%, the
    edge; 101 is above it; a pre-tax income at or below zero gives no reading."""
    assert _uncertain("includes-sbc") is not None
    assert _uncertain("includes-sbc", t=replace(_T, income_tax=101.0)) is None
    assert _uncertain("includes-sbc", t=replace(_T, pretax_income=0.0)) is None
    assert _uncertain("includes-sbc", t=replace(_T, income_tax=None)) is None


def test_the_basis_is_uncertain_on_a_gap_far_above_stock_pay() -> None:
    """Reason 3: the test reads excludes-sbc and the gap, 12.5 less 10.0, is 10 times 0.25, the
    edge; a GAAP EPS of 10.01 is inside it."""
    wide = replace(_T, eps_diluted=10.0, income_tax=200.0)
    flag = _uncertain("excludes-sbc", t=wide)
    assert flag is not None and flag.code == "sbc-basis-uncertain"
    assert _uncertain("excludes-sbc", t=replace(wide, eps_diluted=10.01)) is None
    assert _uncertain("unknown", t=wide) is None
```

In `tests/refresh/test_inputs.py`: on the synthetic company, `inputs.trailing.income_tax` and `.pretax_income` are the sums of its four quarters' lines (work them from `refresh/synthetic.py`), and `inputs.stock_pay` reads `StockPayHistory(0, 2025, <fiscal 2025's figure>)`; with one quarter's `stockBasedCompensation` set to 0 in the payload, `zero_periods == 1`; on a half-yearly reporter (the module's half-year fixture) the two tax sums are over two periods. In `tests/engine/test_route.py`: on `mature_growth_inputs()` with a trailing stock pay of 0 and a history, the result's flag codes hold `stock-pay-missing` right after the position `sbc-basis-unknown` takes, and `sbc-basis-uncertain` after it when a reason holds.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_flags.py -k "stock_pay or basis_is_uncertain"`
Expected: FAIL (the names are not defined).

- [ ] **Step 3: Implement.** The record and the two fields; assembly fills them (`_lines` for the sums; the history from the trailing periods' cash flows and the fiscal years' cash flows). The two flag functions as the Interfaces block says: reason 1 and 2 need `basis == "includes-sbc"` and a material stock pay (after-tax stock pay a share at or above `policy.sbc_material_share` × a street EPS above zero); reason 2 needs a pre-tax income above zero and `income_tax / pretax_income <= policy.sbc_basis_tax_share * tax_rate`; reason 3 needs `basis == "excludes-sbc"`, a stock pay above zero and `street − GAAP >= policy.sbc_basis_gap_multiple ×` the after-tax stock pay a share. `value_mature_growth` puts both after `anchor.flags`, `large_nri` read from the row's own `nri_flag`.

- [ ] **Step 4: Run the tests; all pass. Re-capture a golden only if one of the notes fires on it**, with its README paragraph.

- [ ] **Step 5: Update the documents.** `docs/method.md` 4.2 (the two trailing sums), 5.11 (the order), 8 (two rows, neither counted). The Methodology page's flag list and `tests/web/test_methodology.py`.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Say when the stored stock pay is missing and when the stock-pay basis test may misread, as two notes on a Mature Growth row"
```

---

### Task 5: The two stock-pay inputs (spec 7.2)

**Files:**
- Modify: `src/fairband/engine/overrides.py` (`OverrideTag`, `BRIDGE_ORDER`, `TAGS`, `LABELS`, `INPUT_OF`, `_reading`, the docstring's count), `src/fairband/engine/anchor.py` (`ntm_anchor`), `src/fairband/engine/route_mature_growth.py` (`_anchor_and_path`, the intermediates, the two notes' silence)
- Modify: every other table that names the tags (grep `value.outside` under `src/` and `playbook/`: the refs' and the page's labels, the web layer's lists)
- Modify: `docs/method.md` 14.2 to 14.5; `methodology.html` ("eighteen"); `playbook/fairband-research/SKILL.md` (the overrides table, the two steps of spec 7.2), `reference/tools.md`, `reference/citations.md`
- Test: `tests/engine/test_anchor.py`, `tests/engine/test_overrides.py`, `tests/engine/test_review.py`, `tests/web/test_reviews_api.py`, `tests/test_playbook.py`

**Interfaces:**
- Consumes: `Policy.override_ranges["earnings.sbc"]` (Task 1); the two notes (Task 4).
- Produces:
  - `ntm_anchor(..., sbc_override: float | None = None, basis_override: Literal["includes", "excludes"] | None = None) -> Anchor`. The trailing stock pay is `sbc_override` when given, in the test and in the adjustment. The basis is `f"{basis_override}-sbc"` when given, and the test is not run.
  - Tags `earnings.sbc` (Mature Growth; unit `USD`; period-tied only; label "stock pay"; its input `sbc_ttm`) and `earnings.sbc_basis` (Mature Growth; unit `basis`; words `("includes", "excludes")`; label "stock-pay basis"). `BRIDGE_ORDER` holds them right after `earnings.nri_gap`, the figure first.
  - Mature Growth intermediates gain `sbc_ttm`, the stock pay the anchor read. `current_reading(result, "earnings.sbc")` is that figure; `current_reading(result, "earnings.sbc_basis")` is `"includes"` or `"excludes"`, `None` on an unknown basis.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_anchor.py`, beside `test_anchor_subtracts_sbc_scaled_by_revenue`, on its figures: the module's `ntm()` (a raw NTM EPS of 10.0, NTM revenue 120) and `trailing()` (GAAP EPS 4.0, stock pay 10, revenue 100), 10 shares and a rate of 21%, so the after-tax stock pay a share is 0.79 and the adjustment 0.79 × 1.2 = 0.948.

```python
def test_an_agent_s_basis_replaces_the_test(policy: Policy) -> None:
    """Street 5.0 against GAAP 4.0: the test reads excludes-sbc, and an agent's ``includes``
    leaves the consensus as it is. Street 4.2: the test reads includes-sbc, and an agent's
    ``excludes`` takes the 0.948 off. An agent's basis needs no street figure."""
    kept = ntm_anchor(ntm(), trailing(), 5.0, 10.0, 0.21, 100.0, policy, basis_override="includes")
    assert (kept.basis, kept.sbc_adjustment_per_share) == ("includes-sbc", 0.0)
    assert kept.ntm_eps == pytest.approx(10.0)
    charged = ntm_anchor(
        ntm(), trailing(), 4.2, 10.0, 0.21, 100.0, policy, basis_override="excludes"
    )
    assert (charged.basis, charged.ntm_eps) == ("excludes-sbc", pytest.approx(9.052))
    blind = ntm_anchor(ntm(), trailing(), None, 10.0, 0.21, 100.0, policy, basis_override="excludes")
    assert blind.ntm_eps == pytest.approx(9.052) and blind.flags == ()


def test_an_agent_s_stock_pay_replaces_the_stored_figure(policy: Policy) -> None:
    """A stock pay of 5 in place of 10 halves the adjustment to 0.474; a figure of zero charges
    nothing; the test reads the agent's figure, not the stored one."""
    half = ntm_anchor(ntm(), trailing(), 5.0, 10.0, 0.21, 100.0, policy, sbc_override=5.0)
    assert half.sbc_adjustment_per_share == pytest.approx(0.474)
    assert half.ntm_eps == pytest.approx(9.526)
    none = ntm_anchor(ntm(), trailing(), 5.0, 10.0, 0.21, 100.0, policy, sbc_override=0.0)
    assert none.ntm_eps == pytest.approx(10.0)
    # stored 0, an agent's 10: a gap of 0.2 is below half of 0.79, so the basis reads includes
    stored_zero = ntm_anchor(
        ntm(), trailing(sbc=0.0), 4.2, 10.0, 0.21, 100.0, policy, sbc_override=10.0
    )
    assert stored_zero.basis == "includes-sbc"
```

`tests/engine/test_overrides.py`: `check_input("earnings.sbc_basis", "excludes", "mature-growth", policy)` applies and `"maybe"` is `refused-unit`; both tags are `refused-route` on `"mature-stable"` and on `"revenue-growth"`; `check_override("earnings.sbc", 40e6, "mature-growth", policy, ["filing"], "lasting", None)` is `("refused-unit", "earnings.sbc is period-tied only")`; a negative `earnings.sbc` is refused; on a row in SEK at a rate of 8 the range has no upper end, so a figure of 8e15 applies, and the refusal of −1 names the range in SEK, as `balance.cash`'s does. `BRIDGE_ORDER.index("earnings.sbc") == BRIDGE_ORDER.index("earnings.nri_gap") + 1` and `earnings.sbc_basis` follows it.

`tests/engine/test_review.py`, on the Mature Growth golden's inputs with a street EPS set so the mechanical basis is `excludes-sbc`: a review under `earnings.sbc_basis` = `"includes"` raises the NTM EPS by exactly the mechanical result's `sbc_adjustment_per_share`; its bridge has one line, labelled by the tag, old `"excludes"`, new `"includes"`, and its delta equals the reviewed value less the mechanical one; `sbc-basis-uncertain` is not among the review's flags though it is among the mechanical result's (arrange a reason that holds); under `earnings.sbc` the review's `stock-pay-missing` is absent; with an applied `earnings.ntm` first, the basis override applies and its bridge line's delta is 0.0.

`tests/web/test_reviews_api.py`: `POST /api/companies/AAPL/overrides` with each tag, a filing as evidence and a period for `earnings.sbc`, answers 201 with a review; `tests/test_playbook.py`: the overrides table names twenty inputs (rename the test and its words).

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_anchor.py tests/engine/test_overrides.py -k "agent_s or sbc"`
Expected: FAIL (`ntm_anchor` takes no `basis_override`; `earnings.sbc is not an input`).

- [ ] **Step 3: Implement the anchor's two keywords and the two tags.** `_anchor_and_path` reads both with `chosen` on the route's own anchor only (`own`), as it reads `earnings.ntm`. `value_mature_growth` leaves out `sbc-basis-uncertain` under an applied `earnings.sbc_basis` and `stock-pay-missing` under an applied `earnings.sbc`.

- [ ] **Step 4: Add the tags to every table that lists them** (the grep of Files), then run the tests; all pass. Re-capture the Mature Growth goldens for `sbc_ttm`, with the README paragraph.

- [ ] **Step 5: Update the documents.** `docs/method.md` 14.2 (two rows: routes, what each takes, lifetime), 14.3 ("twenty"), 14.4 (how the route reads each, and that `earnings.nri_gap` keeps its effect on the test only while no basis override is applied), 14.5 (the order). The Methodology page's count. The playbook: the two rows in the overrides table with the evidence each needs (the release's definition of the adjusted figure; the filing's cash flow statement), and the two steps of spec 7.2 in the Mature Growth part of the valuation step.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Let an agent set the stock-pay basis and the trailing stock pay on a Mature Growth row, each with its bridge line"
```

---

### Task 6: The share-count check (spec 8)

**Files:**
- Modify: `src/fairband/engine/flags.py` (the function, `QUALITY_WARNINGS`, the docstring), `src/fairband/engine/route.py` (`_valued`, `_refuse`), `src/fairband/reports/render.py` ("eleven")
- Modify: `docs/method.md` 8 and each route's flag list (5.11, 5a.13, 6.5, 6a.10, 6b.6); the Methodology page ("eleven", the list)
- Test: `tests/engine/test_flags.py`, `tests/engine/test_route.py`, `tests/engine/test_review.py`, `tests/web/test_methodology.py`, `tests/reports/test_render.py`

**Interfaces:**
- Consumes: `Policy.share_count_gap_band` (Task 1).
- Produces: `flags.share_count_flag(market_cap: float | None, price: float | None, shares: float | None, policy: Policy) -> Flag | None`, code `share-count-gap`, label "Share count and market cap disagree"; `"share-count-gap" in QUALITY_WARNINGS`. `market_cap` and `price` are the quote's, in US dollars on every row.

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_flags.py`:

```python
@pytest.mark.parametrize(
    ("market_cap", "fires"),
    [(70.0, False), (69.9, True), (130.0, False), (130.1, True), (100.0, False)],
)
def test_the_share_count_gap_fires_outside_the_band(market_cap: float, fires: bool) -> None:
    """A price of 1 on 100 shares: the ratio is the market cap over 100. The band's edges, 0.7
    and 1.3, are inside it."""
    flag = share_count_flag(market_cap, 1.0, 100.0, load_policy())
    assert (flag is not None) is fires
    if flag is not None:
        assert flag.code == "share-count-gap" and f"{market_cap / 100:.2f}" in flag.sentence


def test_the_share_count_gap_needs_its_three_figures() -> None:
    policy = load_policy()
    assert share_count_flag(None, 1.0, 100.0, policy) is None
    assert share_count_flag(460.0, None, 100.0, policy) is None
    assert share_count_flag(460.0, 1.0, None, policy) is None
    assert share_count_flag(460.0, 0.0, 100.0, policy) is None
```

Rename `test_flag_count_counts_the_eleven_quality_warnings_only` to twelve and add the new code to its counted set.

`tests/engine/test_route.py`: `mature_growth_inputs()` with its market cap multiplied by 4.6 carries the flag on the valued result; the same on a result refused in its route (the Young Growth company with no peers); `fx_inputs()` (SEK, market cap and price in US dollars) with a consistent market cap carries none, and with the market cap doubled carries it; after `reprice` at another price the flag, `trailing_end` and `margin_history` are as the valuation wrote them (add `margin_history` to this assertion in Task 7). `tests/engine/test_review.py`: on the 4.6x row, a review under a `shares.diluted` of 4.6 times the count carries no `share-count-gap`.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_flags.py -k "share_count or twelve"`
Expected: FAIL (`share_count_flag` is not defined).

- [ ] **Step 3: Implement.** The ratio is `market_cap / (price * shares)`; the flag fires when it is below the band's low or above its high. The sentence gives the ratio to two decimals, the market cap and the count, and the two readings of spec 8. `_valued` and `_refuse` add it after the assembly's flags, on the count in force: an applied `shares.diluted`'s value, else `i.shares_diluted`. `reprice` is not changed: the market cap and the price are one quote's, so the ratio does not move with the price.

- [ ] **Step 4: Run the tests; all pass.** No golden carries the flag (confirm).

- [ ] **Step 5: Update the documents.** `docs/method.md` 8: the row, counted; "twelve" wherever the quality warnings are counted; each route's flag list. `engine/flags.py`'s docstring and `reports/render.py`'s sentence. The Methodology page and its test.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Warn when the market cap and the price times the diluted count disagree by more than 30%, as the twelfth quality warning"
```

---

### Task 7: The thin-consensus note and the ten-year median margins (spec 9, 11)

**Files:**
- Modify: `src/fairband/engine/anchor.py` (`thin_ntm_flag`), `src/fairband/engine/route_mature_growth.py` (its place), `src/fairband/engine/classifier.py` (`FiscalYear.net_income`), `src/fairband/refresh/inputs_statements.py` (`series_for`), `src/fairband/engine/flags.py` (`margin_history`), `src/fairband/engine/route.py` (`_valued`, `_refuse`), `src/fairband/reports/refs.py` (`_SNAPSHOT_PATH_WORDS`)
- Modify: `docs/method.md` 3.1, 5.11, 8, and each route's intermediates list (5.12, 5a.14, 6.5, 6a.10, 6b.6); the Methodology page's flag list; the playbook (`SKILL.md`'s cycle formula, `reference/citations.md`, `reference/report-template.md`)
- Test: `tests/engine/test_anchor.py`, `tests/engine/test_flags.py`, `tests/engine/test_route.py`, `tests/refresh/test_inputs.py`, `tests/reports/test_refs.py`, `tests/test_playbook.py`

**Interfaces:**
- Produces:
  - `anchor.thin_ntm_flag(periods: Sequence[QuarterEstimate], policy: Policy) -> Flag | None`, code `thin-ntm`, label "Thin NTM consensus": fires when a period's `analysts` is `None` or below `policy.analyst_min`.
  - `FiscalYear.net_income: float | None = None`, filled by `series_for` from `netIncome`.
  - `flags.margin_history(series: Series) -> dict[str, dict[str, float | int]]`: `{"operating": {"median": m, "years": n}, "net": {...}}` over the last ten fiscal years that have the line and a revenue above zero; a margin with no such year has no key.
  - Every result of `value_company` with a series carries `intermediates["margin_history"]`.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_anchor.py`:

```python
def _window(*analysts: int | None) -> list[QuarterEstimate]:
    """The first NTM periods after 2026-06-30, each with its EPS analyst count."""
    ends = ("2026-09-30", "2026-12-31", "2027-03-31", "2027-06-30")
    return [q(end, 2027, f"Q{k}", 2.5, n=n) for k, (end, n) in enumerate(zip(ends, analysts), 1)]


def test_thin_ntm_names_the_thin_periods(policy: Policy) -> None:
    assert thin_ntm_flag(_window(5, 5, 5, 5), policy) is None
    flag = thin_ntm_flag(_window(15, 15, 6, 4), policy)
    assert flag is not None and flag.code == "thin-ntm"
    assert "1 of the 4 periods" in flag.sentence and "4 analysts" in flag.sentence
    assert "30 Jun 2027" in flag.sentence
    assert thin_ntm_flag(_window(5, None, 5, 5), policy) is not None  # no count is thin
    two = thin_ntm_flag(_window(3, 2), policy)  # a half-yearly reporter's window
    assert two is not None and "2 of the 2 periods" in two.sentence
```

`tests/engine/test_flags.py`, on the module's `margins()` helper (fiscal years ending in 2025 on a revenue of 100, the operating margin in percent points):

```python
def test_margin_history_is_the_median_of_the_last_ten_years() -> None:
    nets = [1.0, 2.0, 3.0, None]
    four = tuple(
        replace(fy, net_income=n) for fy, n in zip(margins([10, 20, 30, 40]), nets, strict=True)
    )
    assert margin_history(four) == {
        "operating": {"median": pytest.approx(0.25), "years": 4},
        "net": {"median": pytest.approx(0.02), "years": 3},
    }
    # twelve years: the oldest two, 90% and 80%, are outside the window; no net income on file
    twelve = margins([90, 80, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert margin_history(twelve) == {"operating": {"median": pytest.approx(0.055), "years": 10}}
    # a year with no revenue above zero is skipped
    dead = replace(four[0], year=2026, period_end=date(2026, 12, 31), revenue=0.0)
    assert margin_history((*four, dead)) == margin_history(four)
    assert margin_history(()) == {}
```

`tests/engine/test_route.py`: the result of each route's test company carries `margin_history` equal to `margin_history(inputs.series)`, a result refused in its route too; the Mature Growth result's flag codes hold `thin-ntm` right after the place of `few-analysts` when a window period has 4 analysts, and not under an applied `earnings.ntm`. `tests/refresh/test_inputs.py`: the synthetic company's series carries each year's net income (15% of revenue). `tests/reports/test_refs.py`: `snapshot:<id>/intermediates/margin_history/net/median` resolves the figure and describes as "the ten-year median net margin", the operating one as "the ten-year median operating margin", and `/years` as its count.

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest -q tests/engine/test_anchor.py tests/engine/test_flags.py -k "thin_ntm or margin_history"`
Expected: FAIL (the names are not defined).

- [ ] **Step 3: Implement.** `thin_ntm_flag`'s sentence gives the count of thin periods of the window's count, the smallest count (a missing count reads "no count") and that period's end as "30 Sep 2027". `value_mature_growth` places it after `few-analysts` and leaves it out under an applied `earnings.ntm`. `margin_history` reuses `margin-flag`'s window for the operating margin and applies the same rule to net income. `_valued` and `_refuse` add the entry when the series is not empty.

- [ ] **Step 4: Run the tests; all pass. Re-capture every golden for `margin_history`** (and `thin-ntm` where it fires), with the README paragraph; complete Task 6's reprice assertion.

- [ ] **Step 5: Update the documents and the playbook.** `docs/method.md` 3.1 (the series carries net income, read by no rule of the classifier), 5.11 and 8 (`thin-ntm`, not counted), the intermediates lists. The playbook's cycle formula as spec 11 states it: the mid-cycle margin is `snapshot:<id>/intermediates/margin_history/net/median`; a history of fewer than ten years is named with its count; a consensus basis that leaves out the amortization of bought intangibles is said so and is evidence for half the gap; step 7's operating margin reads the operating median. Update `tests/test_playbook.py` where it pins the old term.

- [ ] **Step 6: Run the four checks, then commit**

```bash
git add -A
git commit -m "Note a next-twelve-months EPS that sums a thin period, and carry the ten-year median operating and net margins on every routed result"
```

---

### Task 8: The Methodology page's examples, the drawer and the whole-branch review

**Files:**
- Modify: `src/fairband/web/static/methodology.html` (worked examples), `src/fairband/web/static/app.js` only if a new flag or input needs words there
- Test: `tests/web/test_methodology.py`, `tests/web/test_app.py`

- [ ] **Step 1: Check the drawer.** Run the server on a scratch copy of the fixture database (`uv run python -m fairband serve` with the data folder set to a temporary one, as the web tests do) and open one Mature Growth row: the four new flags show with their sentences where they fire, the two inputs show in the bridge with their labels, and nothing prints a raw tag. Where the page holds its own copy of a label or a count, the tests of `tests/web/test_app.py` pin the change.

- [ ] **Step 2: Re-read the Methodology page's worked examples** on the method version 1.3: each example's figures against the engine on the example's stored inputs. No formula changed, so a figure moves only if its consensus row did; change what moved and the "as of" line of an example that changed.

- [ ] **Step 3: Request the whole-branch review** (superpowers:requesting-code-review) against the spec's sections 6 to 11a and this plan's Review Focus; fix what it finds test-first; park what it rules minor in `docs/backlog.md` as one row.

- [ ] **Step 4: Run the four checks, then commit** what the three steps changed, one commit for the page and one for each review fix.

---

### Task 9: The scratch revalue, the live step and the readout (spec 17)

Nothing in this task runs without the founder's word. Ask once, with this list.

- [ ] **Step 1: The scratch run.** Copy the live database to a scratch folder and run a revalue on the copy with the branch's code (`uv run python -m fairband` with the data folder set to the scratch one; the CLI's revalue needs no key). Collect the readout of Step 4 from the copy.

- [ ] **Step 2: Compare the scratch readout with spec 17's expectations** and report every difference before going on. A difference in a value outside the companies whose kept estimate row was an old one stops the plan.

- [ ] **Step 3: The live step.** Merge to main and push; back up the live database as `fairband-before-method-1.3-<date>.db`; stop the server by its process ids and start it from main (`setsid nohup uv run python -m fairband serve >> ~/.local/share/fairband/server.log 2>&1 < /dev/null &`); run one revalue from the page or the CLI. Check it against the scratch run: the two must be identical.

- [ ] **Step 4: The readout**, written into the spec's decision log:
  - every row whose value, levels or refusal differs from the snapshot before, with its cause; AAPL's NTM EPS and the four quarters it sums;
  - the counts of `stock-pay-missing`, of `sbc-basis-uncertain` by reason, of `share-count-gap` (SYM, ANDG, EROK and EE named; ROAD absent) and of `thin-ntm`, each against spec 5;
  - `margin_history` present on every routed row; ASML's and TTMI's ten-year net margins against 26.0% and 3.1%;
  - on the scratch copy only: NVS under `earnings.sbc_basis` = `includes`, CLS under `excludes`, AAPL's sensitivity at 332.6%;
  - the ten period-tied overrides (SYM 22 and 23, CLS 36 to 38, FRVO 42 and 43, RKLB 54 to 56), each with its state, and every lasting override still applied.

- [ ] **Step 5: Close the rows.** In `docs/backlog.md`: B-172, B-178 and B-164 to Done with their commits; B-115, B-116, B-162 and B-175 rewritten to what is left of each (the test itself, the refetch, the count, the anchor); B-106 to Done as built with the first screen; the review's parked minors as one row. Commit, and tell the founder that every research session must restart its MCP process.

---

## Self-review notes

- Spec coverage: section 6 is Task 2; 7.1 is Task 4; 7.2 is Task 5; 8 is Task 6; 9 and 11 are Task 7; 10 and 14 (v13) are Task 1; 11a is Task 3; 15 is spread over the tasks' document steps and Task 8; 16's plan 1 tests are in the tasks that own the code; 17's plan 1 readout is Task 9. Sections 12, 13 and v14 are plan 2.
- The order: Task 3 comes before the stock-pay tasks so that the goldens are re-captured for one cause at a time; Task 5 needs Tasks 1 and 4; Tasks 6 and 7 need Task 1 alone.
