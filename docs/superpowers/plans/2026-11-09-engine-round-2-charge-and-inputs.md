# Engine Round 2, plan 1: the charge, the notes, the two inputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build sections 6 to 9, 11 and 12 of the engine round 2 spec: the reinvestment charge without its floor and on revenue growth, the runway return held then faded, the consensus-basis and step-series notes, the `value.outside` and `shares.diluted` inputs, policy v10 and method 1.0, with the documents, the drawer and the playbook; then the live revalue and the readout. Stock splits (spec section 10) are plan 2.

**Architecture:** The charge's arithmetic lives in `engine/mature_growth.py` (`GrowthPath` gains the revenue steps, `Charge` gains the hold); the return measures in `engine/roic.py`; both mature routes wire them through `engine/route_steps.RoicTerms`. The two inputs join `engine/overrides.py` and are read in `engine/route.py` and `route_steps.py`, so every valued route adds the outside value the same way. Documents, drawer and playbook change in the task that changes the behaviour they describe.

**Tech Stack:** Python 3.13, uv, pytest, mypy, ruff; FastAPI web; the playbook's Markdown.

**Spec:** `docs/superpowers/specs/2026-11-09-engine-round-2-design.md`

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- `docs/method.md` changes in the same commit as the engine, the classifier, the universe rule or a policy value it describes; the Methodology page (`src/fairband/web/static/methodology.html`) with it. Where documents disagree, `docs/method.md` describes what runs.
- Method version `fairband-mechanical/1.0`; policy `fairband-policy-v10`; v9 stays byte-identical under its hash; no new setting.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic or hand-trimmed.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- At the defaults, every row on the revenue-growth, Decline and Start-up routes keeps its value, levels, designation, flags and refusal bit for bit (the goldens HGCO, YGCO, DCCO and SUCO assert it).
- The spec's section 5 figures govern within 0.1% on the five companies' stored inputs (Task 5 checks them read-only against the live database); where a figure is off, name the rule that reads differently before changing anything.

## Review Focus

- A `return.runway` override on a row whose measured charge is off (`charge_off`): the override's R starts the fade and charges every runway year, as 14.4 says; the fade must not read `charge_off` from the measured return. Test in Task 5.
- A one-year runway (N = 1): K = 0 and the only year takes T; no division by N − K = 0. Test in Task 2.
- A path with a missing earnings step and a present revenue step (the earnings step takes the belief, the revenue step stands): h uses the revenue step, the earnings path the belief. Test in Task 2.
- `value.outside` negative enough to take the value a share at or below zero: the route refuses "value not positive under the reinvestment charge" today only on the route's own value; with the outside figure the sum decides, and a sum at or below zero is a refusal with the same reason. Test in Task 6.
- `shares.diluted` on a Start-up row: the requirement reads the count; the route raises no bridge line for `value.outside` (not read) but does for the count. Test in Task 6.

---

### Task 1: Policy v10 and method 1.0

**Files:**
- Create: `src/fairband/policy/fairband-policy-v10.toml` (a copy of v9 with the new values)
- Modify: `src/fairband/policy/__init__.py` (`_POLICY_FILE`, two fields, two reads), `src/fairband/policy/settings.py` (`check`), `src/fairband/engine/__init__.py` (`METHOD_VERSION`)
- Modify: `docs/method.md` sections 4.1 (four rows), 11 (the 1.0 row)
- Test: `tests/policy/test_policy.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `Policy.step_series_gap_max: float` (0.05), `Policy.split_implied_count_tolerance: float` (0.15), `Policy.override_ranges["value.outside"] == (-1000.0, 1000.0)`, `Policy.override_ranges["shares.diluted"] == (0.0, 1e12)`; `METHOD_VERSION == "fairband-mechanical/1.0"`.

- [ ] **Step 1: Write the failing tests** in `tests/policy/test_policy.py`, beside `test_v9_is_v8_with_the_values_added`:

```python
def test_v10_is_the_packaged_policy() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v10"
    assert p.step_series_gap_max == 0.05
    assert p.split_implied_count_tolerance == 0.15
    assert p.override_ranges["value.outside"] == (-1000.0, 1000.0)
    assert p.override_ranges["shares.diluted"] == (0.0, 1e12)


def test_v10_is_v9_with_the_four_values_added() -> None:
    v9 = load_policy(_file("fairband-policy-v9.toml"))  # the helper the v9 test uses
    v10 = load_policy()
    assert v10.raw["values"].keys() - v9.raw["values"].keys() == {
        "step_series_gap_max",
        "split_implied_count_tolerance",
    }
    for name in v9.raw["values"]:
        if name != "override_ranges":
            assert v10.raw["values"][name] == v9.raw["values"][name], name
    assert v10.override_ranges.keys() - v9.override_ranges.keys() == {"value.outside", "shares.diluted"}


def test_v9_is_byte_identical_under_its_hash() -> None:
    # the same shape as test_v8_is_byte_identical_under_its_hash, on v9's recorded hash
```

and in `tests/engine/test_golden.py` or `tests/engine/test_types.py`, `assert METHOD_VERSION == "fairband-mechanical/1.0"`. Follow the file's existing helpers for the file path and the hash.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/policy/test_policy.py tests/engine/test_golden.py`
Expected: FAIL on the version and the missing values.

- [ ] **Step 3: Add the policy file and the fields.** Copy v9 to `fairband-policy-v10.toml`; set `[meta] version = "fairband-policy-v10"`; add `[values.step_series_gap_max]` (0.05) and `[values.split_implied_count_tolerance]` (0.15), each with a `source` line from spec section 11; add the two pairs under `[values.override_ranges.value]` and extend its `note`. In `policy/__init__.py`: `_POLICY_FILE = "fairband-policy-v10.toml"`, fields `step_series_gap_max: float` and `split_implied_count_tolerance: float`, read with `_num`. In `settings.py` `check`: both from 0 to 0.5, `ValueError("step_series_gap_max: must be from 0 to 50 points")` and the same for the tolerance. In `engine/__init__.py`: `METHOD_VERSION = "fairband-mechanical/1.0"`.

- [ ] **Step 4: Update `docs/method.md`**: 4.1 gains four rows (the two values and the two ranges, Setting "no", sources from spec 11); 11 gains the 1.0 row summarizing spec section 1 (the charge, the fade, the notes, the two inputs; splits to follow). The 0.9 goldens strip the versions, so the goldens stand.

- [ ] **Step 5: Run the checks**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass (the golden test strips `method_version` and `policy_version`).

- [ ] **Step 6: Commit**

```bash
git add src/fairband/policy src/fairband/engine/__init__.py docs/method.md tests/policy/test_policy.py tests/engine
git commit -m "Add policy v10 with the step-series gap, the split tolerance and the two new override ranges, and name method 1.0"
```

---

### Task 2: The charge's arithmetic

**Files:**
- Modify: `src/fairband/engine/mature_growth.py`
- Test: `tests/engine/test_mature_growth.py`

**Interfaces:**
- Produces: `GrowthPath(year1, steps, belief, runway, fade_years=0, revenue_steps: tuple[float | None, float | None] | None = None)`; `Charge(runway_roic, terminal_roic, r, g_t, charge_off=False, hold: int | None = None)`, where `hold=None` means the shape as built (R for years 1 to N − 1, T in year N) so that every caller not yet passing a hold keeps today's figures, and an integer hold gives spec 6.3's shape; `charge_growth(path) -> tuple[float, ...]` (h for years 2 to N, each revenue step falling back to the earnings step of the same year, faded as the earnings path fades); `hold_years(path) -> int` (the last t in 1 … N − 1 with g_{t+1} > belief, 0 when none); `return_by_year(charge, n) -> tuple[float, ...]` (spec 6.3; with `hold=None`, R for t < n and T at t = n); `cash_to_equity(ni, g_next, roic, charge_off=False) -> float` with no floor; `negative_years(path, charge) -> tuple[int, ...]` and `first_negative_year(path, charge) -> tuple[int, float, float] | None` in place of `floored_years` and `first_floored_year`; `value_at_belief` and `implied_growth` keep their signatures.

- [ ] **Step 1: Write the failing tests.** Replace `test_cash_to_equity`, `test_payout_floor`, `test_first_floored_year` and `test_value_with_the_fade_and_the_floor` with tests on the spec's worked numbers (13.1 to 13.4):

```python
R, GT = 0.09, 0.03
TOY = GrowthPath(100.0, (0.25, 0.20), 0.05, 5, 5, revenue_steps=(0.15, 0.10))
TOY_CHARGE = Charge(0.20, 0.13, R, GT, hold=4)


def test_charge_growth_reads_the_revenue_steps_then_fades_to_the_belief() -> None:
    assert charge_growth(TOY) == pytest.approx((0.15, 0.10, 0.09, 0.08))
    assert growth_rates(TOY) == pytest.approx((0.25, 0.20, 0.17, 0.14))


def test_a_missing_revenue_step_takes_the_earnings_step() -> None:
    path = replace(TOY, revenue_steps=(0.15, None))
    assert charge_growth(path) == pytest.approx((0.15, 0.20, 0.17, 0.14))
    assert charge_growth(replace(TOY, revenue_steps=None)) == growth_rates(TOY)


def test_a_missing_earnings_step_with_a_present_revenue_step() -> None:
    path = replace(TOY, steps=(None, 0.20))  # the earnings step takes the belief
    assert growth_rates(path)[0] == pytest.approx(0.05)
    assert charge_growth(path)[0] == pytest.approx(0.15)


def test_hold_years_is_the_last_year_above_the_belief() -> None:
    assert hold_years(TOY) == 4
    assert hold_years(replace(TOY, runway=10)) == 6
    assert hold_years(GrowthPath(100.0, (0.02, 0.20), 0.05, 10, 5)) == 6  # a flat step inside
    assert hold_years(GrowthPath(100.0, (GT, GT), GT, 10, 5)) == 0
    assert hold_years(GrowthPath(100.0, (0.25, 0.20), 0.05, 1, 5)) == 0


def test_return_by_year_holds_then_fades() -> None:
    assert return_by_year(TOY_CHARGE, 5) == pytest.approx((0.20, 0.20, 0.20, 0.20, 0.13))
    ten = Charge(0.20, 0.13, R, GT, hold=6)
    assert return_by_year(ten, 10) == pytest.approx(
        (0.20, 0.20, 0.20, 0.20, 0.20, 0.20, 0.1825, 0.165, 0.1475, 0.13)
    )
    stable = Charge(0.20, 0.13, R, GT, hold=0)
    assert return_by_year(stable, 10)[0] == pytest.approx(0.193)
    assert return_by_year(stable, 1) == (0.13,)  # a one-year runway: T alone, no division by zero
    as_built = Charge(0.20, 0.13, R, GT)  # hold None: R through year N − 1, T in year N
    assert return_by_year(as_built, 5) == pytest.approx((0.20, 0.20, 0.20, 0.20, 0.13))
    assert return_by_year(as_built, 1) == (0.13,)


def test_cash_to_equity_has_no_floor() -> None:
    assert cash_to_equity(100.0, 0.25, 0.20) == pytest.approx(-25.0)
    assert cash_to_equity(100.0, 0.25, 0.20, charge_off=True) == 100.0
    assert cash_to_equity(100.0, 0.25, math.inf) == 100.0


def test_value_on_the_spec_s_runway_5_path() -> None:
    assert value_at_belief(TOY, TOY_CHARGE) == pytest.approx(2030.9538, abs=1e-3)
    earnings_only = replace(TOY, revenue_steps=None)
    flat = Charge(0.20, 0.13, R, GT, hold=4)
    assert value_at_belief(earnings_only, flat) == pytest.approx(1848.8476, abs=1e-3)


def test_value_on_the_spec_s_runway_10_paths() -> None:
    ten = replace(TOY, runway=10)
    assert value_at_belief(ten, Charge(0.20, 0.13, R, GT, hold=6)) == pytest.approx(2293.8222, abs=1e-3)
    stable = GrowthPath(100.0, (GT, GT), GT, 10, 5)
    assert value_at_belief(stable, Charge(0.20, 0.13, R, GT, hold=0)) == pytest.approx(1315.0993, abs=1e-3)


def test_the_fallback_example() -> None:
    path = replace(TOY, revenue_steps=(0.15, None))
    assert value_at_belief(path, TOY_CHARGE) == pytest.approx(1894.7191, abs=1e-3)


def test_negative_years_name_the_owner_s_money_going_in() -> None:
    path = replace(TOY, revenue_steps=None)
    assert negative_years(path, TOY_CHARGE) == (1,)
    assert first_negative_year(path, TOY_CHARGE) == pytest.approx((1, 0.25, 0.20))
    assert negative_years(TOY, TOY_CHARGE) == ()
    assert negative_years(path, Charge(0.20, 0.13, R, GT, True, 4)) == ()  # the charge off
```

Keep every other existing test; re-pin `test_value_timing_by_hand`, `test_implied_growth_*`, `test_charged_*` and `test_fade_*` where the floor's removal or the fade moves their figures, each with a comment naming the spec section. The hold the existing tests pass is their own: `Charge(..., hold=hold_years(path))`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/engine/test_mature_growth.py`
Expected: FAIL (`revenue_steps`, `hold`, `charge_growth` undefined).

- [ ] **Step 3: Implement in `mature_growth.py`.** `GrowthPath.revenue_steps`; `charge_growth(path)` as `growth_rates(replace(path, steps=resolved))` with `resolved[i] = revenue_steps[i] if not None else steps[i]`; `hold_years(path)`; `Charge.hold` (`int | None`, default `None`); `return_by_year(charge, n)` per spec 6.3, with `hold is None` or `hold >= n - 1` or `n <= 1` giving R for t < n and T in year n only; `_years` yielding `_Year(t, ni, h_next, return_t, charge_off and t < n)` with `h_next` from `charge_growth`; `cash_to_equity` without `max(0, …)`; rename `_floored`/`floored_years`/`first_floored_year` to `_negative`/`negative_years`/`first_negative_year` on `1 - h/roic < 0`. Rewrite the module docstring to spec 6.1 to 6.3. `implied_growth` is unchanged: it varies `path.belief`, and `Charge.hold` is fixed. In `route_mature_growth.py` rename the import and the call of `first_floored_year` to `first_negative_year` (the sentence changes in Task 5), so the suite imports.

- [ ] **Step 4: Run the tests and the goldens**

Run: `uv run pytest -q tests/engine/test_mature_growth.py tests/engine/test_golden.py tests/engine/test_route.py`
Expected: the arithmetic tests PASS. The floor's removal alone moves a golden whose path has a year of growth above its return (MGCO's fixture floors: its steps 25% and 26% against a 14.9% return): re-capture that golden with the README command, with a README line naming spec 6.1 (the floor off) as the cause, and re-pin any route test that pinned the floored value. HGCO, YGCO, DCCO and SUCO must be unchanged. The fade and the revenue charge do not reach the routes until Task 5 (`hold=None`, `revenue_steps=None`).

- [ ] **Step 5: Commit** (after the full checks)

```bash
git add src/fairband/engine/mature_growth.py src/fairband/engine/route_mature_growth.py tests/engine tests/fixtures/golden
git commit -m "Charge the next year's revenue growth with no floor and fade the return from the hold to the terminal in the Mature Growth arithmetic"
```

---

### Task 3: The one-year marginal, the charge with a hold, the two flag sentences

**Files:**
- Modify: `src/fairband/engine/roic.py` (`RunwayReturn.one_year`, `runway_return`), `src/fairband/engine/route_steps.py` (`charge_for`, `RoicTerms.charge`, `RoicTerms.intermediates`, `trailing_flags`), `src/fairband/engine/flags.py` (`basis_unknown_flag`)
- Test: `tests/engine/test_roic.py`, `tests/engine/test_flags.py`

**Interfaces:**
- Produces: `RunwayReturn.one_year: float | None` (a new last field: the change in NOPAT over the change in average capital from the kept year before the newest to the newest, no usability test, `None` with fewer than two kept years or no change in capital); `charge_for(runway_roic, terminal, charge_off, policy, hold: int | None = None) -> Charge`; `RoicTerms.charge(policy, hold: int | None = None) -> Charge` (`None` keeps the shape as built, so the routes' figures do not move in this task); `RoicTerms.intermediates()["runway_return"]["one_year"]`; `flags.basis_unknown_flag(nri: Flag | None, gap: float | None, eps_ttm: float | None) -> Flag | None` (the `consensus-basis-unknown` note, only when `nri` is given); `route_steps.trailing_flags(i, t, gap, policy, rr: RunwayReturn | None = None)` which, only when `rr` is given (the two mature routes pass theirs; any other caller passes none and sees no change), appends `consensus-basis-unknown` after `large-nri` and extends the `heavy-capex` sentence per spec 6.3.

- [ ] **Step 1: Write the failing tests.** In `test_roic.py`, beside `test_marginal_return_spec_example`:

```python
def test_the_one_year_marginal_is_shown_not_used(policy: Policy) -> None:
    rr = runway_return(aggregate_roic(SPEC_YEARS), "Wide", policy)  # the file's spec fixture
    by_year = aggregate_roic(SPEC_YEARS).by_year
    expected = (by_year[-1].nopat - by_year[-2].nopat) / (by_year[-1].average_capital - by_year[-2].average_capital)
    assert rr.one_year == pytest.approx(expected)
    assert rr.value == pytest.approx(rr.marginal)  # the five-year measure still charges


def test_the_one_year_marginal_is_none_without_two_years_or_a_capital_change() -> None:
    # one kept year → None; two kept years with equal average capital → None
```

In `test_flags.py`:

```python
def test_consensus_basis_unknown_follows_large_nri(policy: Policy) -> None:
    nri = nri_flag(0.60, 5.00, policy)
    note = basis_unknown_flag(nri, 0.60, 5.00)
    assert note is not None and note.code == "consensus-basis-unknown"
    assert "$0.60 a share, 12.0% of trailing EPS" in note.sentence
    assert basis_unknown_flag(None, 0.10, 5.00) is None
```

and for the heavy-capex sentence, in `test_flags.py` or `tests/engine/test_route.py` (the one that builds a `CompanyInputs`):

```python
def test_heavy_capex_names_the_start_and_the_newest_year_s_marginal(policy: Policy) -> None:
    flags = trailing_flags(inputs, trailing, None, policy, rr)  # rr with marginal 0.4716 used, one_year 0.2142
    heavy = next(f for f in flags if f.code == "heavy-capex")
    assert "starts at 47.2%, the five-year marginal" in heavy.sentence
    assert "newest year's marginal return is 21.4%" in heavy.sentence
    assert "`return.runway`" in heavy.sentence
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/engine/test_roic.py tests/engine/test_flags.py`
Expected: FAIL (`one_year`, `basis_unknown_flag` missing).

- [ ] **Step 3: Implement.** `roic.py`: add `one_year` to `RunwayReturn` (last), compute it in `runway_return` with `marginal_return(result.by_year, 1, 0.0)[0]` guarded by `len(by_year) >= 2`, on every branch (`unavailable`, `off`, the chosen). `route_steps.py`: `charge_for(..., hold=None)` passes `hold` to `Charge`; `RoicTerms.charge(policy, hold=None)`; `intermediates()` adds `"one_year": rr.one_year`; `trailing_flags(..., rr=None)` appends `basis_unknown_flag(nri, gap, t.eps_diluted)` and, when `rr is not None`, replaces the `heavy-capex` flag's sentence with the spec 6.3 text, naming the measure by `rr.used` ("the five-year marginal" or "the three-year aggregate"; with `used == "floor"` "floored at r"), the fiscal year of the newest kept ROIC year from `RoicTerms.result.by_year[-1].year`, and stopping after R without a one-year figure. `flags.py`: `basis_unknown_flag` with the sentence of spec 7, `Flag("consensus-basis-unknown", "Consensus basis unknown", …)`, a note (not in `QUALITY_WARNINGS`).

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q tests/engine/test_roic.py tests/engine/test_flags.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/engine/roic.py src/fairband/engine/route_steps.py src/fairband/engine/flags.py tests/engine/test_roic.py tests/engine/test_flags.py
git commit -m "Record the newest year's marginal return, give the charge a hold, add the consensus-basis note and name the runway override in the heavy-capex sentence"
```

---

### Task 4: The revenue steps and the step-series note

**Files:**
- Modify: `src/fairband/engine/anchor.py` (`Path`, `path_steps`)
- Test: `tests/engine/test_anchor.py`

**Interfaces:**
- Produces: `Path.revenue_steps: tuple[float | None, float | None]` (the consensus revenue steps on the same rows and base year, `growth_step` on `AnnualEstimate.revenue`); `Path.flags` may hold `step-series-disagree` (spec 9), after `path-on-eps` and `few-analysts`.

- [ ] **Step 1: Write the failing tests**, beside `test_path_on_net_income_then_eps_fallback`:

```python
def test_path_carries_the_revenue_steps(policy: Policy) -> None:
    annual = _annual(2027, revenue=(1000.0, 1150.0, 1265.0), net_income=(100.0, 125.0, 150.0), eps=(1.0, 1.25, 1.5), analysts=20)  # the file's AnnualEstimate builder, or a small one added beside it
    path = path_steps(annual, 2027, policy)
    assert path.revenue_steps == pytest.approx((0.15, 0.10))
    assert path.steps == pytest.approx((0.25, 0.20))


def test_a_missing_or_non_positive_revenue_leaves_the_step_none(policy: Policy) -> None:
    # revenue None in the middle year → both steps None; revenue 0 in the base year → step 2 None


def test_step_series_disagree_names_both_rates(policy: Policy) -> None:
    annual = _annual(2027, net_income=(8.33e9, 10.0e9, 12.0e9), eps=(0.83, 1.10, 1.32), shares=None, analysts=20)
    path = path_steps(annual, 2027, policy)
    note = next(f for f in path.flags if f.code == "step-series-disagree")
    assert "Step 2 reads 20.0% on net income and 32.5% on EPS" in note.sentence
    assert "`path.step_2`" in note.sentence
    assert "Step 3" not in note.sentence  # 20.0% against 20.0%


def test_step_series_within_the_gap_is_silent(policy: Policy) -> None:
    # 20.0% against 24.0%: no note
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/engine/test_anchor.py`
Expected: FAIL (`revenue_steps` missing).

- [ ] **Step 3: Implement in `anchor.py`.** `Path` gains `revenue_steps`; `path_steps` computes `values_rev` from `row.revenue` through `consensus_value(mean, analysts_revenue)` and `growth_step`, and both series' steps (`_point(r, True)` and `_point(r, False)`); for each step i where both series give a rate and `abs(ni - eps) > policy.step_series_gap_max`, collect the sentence part "Step n reads g% on net income and h% on EPS"; one `Flag("step-series-disagree", "Step series disagree", …)` with the parts joined, the implied counts (net-income mean ÷ EPS mean of the landing year, against the diluted count when the caller gives one; `path_steps` has no count, so the sentence names the two implied counts alone: "the two consensus series imply different share counts (A against B)"), "The path is on <net income|EPS>; `path.step_n` decides." Keep `_PATH_ON_EPS` and `few_analysts` as they are.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q tests/engine/test_anchor.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/engine/anchor.py tests/engine/test_anchor.py
git commit -m "Read the consensus revenue steps beside the earnings steps and note a step whose two series disagree by more than the gap"
```

---

### Task 5: The two mature routes on the new charge

**Files:**
- Modify: `src/fairband/engine/route_mature_growth.py`, `src/fairband/engine/route_mature_stable.py`, `src/fairband/engine/mature_stable.py`
- Modify: `docs/method.md` 4.6, 4.8, 5.3, 5.6, 5.7, 5.8, 5.11, 5.13, 6.3, 6.5, 8; `src/fairband/web/static/methodology.html` (the charge passage and the Mature Growth and Mature Stable lists)
- Modify: `tests/fixtures/golden/MGCO.json`, `MSCO.json`, `README.md`
- Test: `tests/engine/test_route.py`, `tests/engine/test_mature_stable.py`, `tests/engine/test_golden.py`, `tests/engine/test_review.py`

**Interfaces:**
- Consumes: Tasks 2 to 4.
- Produces: intermediates `charge: {"growth_by_year": list (years 2 to N + 1, h with g_T last), "return_by_year": list (years 1 to N), "hold_years": int, "revenue_steps": [g2r, g3r]}` on both mature routes and in `growth_cross_check`; `runway_return.one_year`; `_rebuilt(im, policy)` reading `charge.hold_years` and `charge.revenue_steps`; `_roic_charges(own, ten_year, moat, policy, hold)`; `growth-above-return` with spec 6.1's sentence; `consensus-basis-unknown` and the `heavy-capex` sentence through `trailing_flags(i, t, gap, policy, roic)` (Task 3's signature takes the `RoicTerms`, since the sentence names the newest kept year); under a `return.runway` override the `heavy-capex` sentence names the override's value as the charge's start and the measured figure as the measure ("starts at 21.4%, the agent's override; the five-year marginal is 47.2%; the newest year's marginal return is ..."); the `consensus-basis-unknown` sentence ends "through `earnings.nri_gap`, and on Mature Growth `earnings.ntm`" (Mature Stable reads no `earnings.ntm`); `mature_stable_values(e, charge, runway)` unchanged in signature, the charge carrying `hold=0`.

- [ ] **Step 1: Write the failing tests.** In `tests/engine/test_route.py` (on `mature_growth_inputs()` from `support.engine_companies`):

```python
def test_the_mature_growth_charge_intermediates(policy: Policy, deciles: Deciles) -> None:
    r = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    ch = r.intermediates["charge"]
    assert ch["hold_years"] == hold_years(_path_of(r))          # _path_of, _charge_of = route_mature_growth._rebuilt(r.intermediates, policy)
    assert len(ch["return_by_year"]) == r.intermediates["runway"]
    assert ch["return_by_year"][-1] == pytest.approx(r.intermediates["terminal_roic"])
    assert ch["return_by_year"][0] == pytest.approx(r.intermediates["runway_return"]["value"])
    assert len(ch["growth_by_year"]) == r.intermediates["runway"]
    assert ch["growth_by_year"][-1] == pytest.approx(policy.terminal_growth)
    assert ch["revenue_steps"] == list(_path_of(r).revenue_steps)
    assert "one_year" in r.intermediates["runway_return"]


def test_growth_above_return_says_the_owner_funds_the_growth(policy: Policy, deciles: Deciles) -> None:
    # inputs whose year-2 revenue growth outruns the runway return
    flag = next(f for f in r.flags if f.code == "growth-above-return")
    assert "pays out less than nothing: the owner funds the growth" in flag.sentence


def test_a_runway_override_starts_the_fade_even_with_the_charge_off(policy: Policy, deciles: Deciles) -> None:
    # inputs with charge_off (the three-year capital sum at or below zero) plus Override("return.runway", 0.20)
    ch = r.intermediates["charge"]
    assert ch["return_by_year"][0] == pytest.approx(0.20)
    assert r.intermediates["charge_off"] is False


def test_a_reprice_rebuilds_the_same_charge(policy: Policy, deciles: Deciles) -> None:
    # reprice at another price: implied_growth recomputed on the same hold and revenue steps; value unchanged


def test_the_heavy_capex_sentence_names_an_override_as_the_start(policy: Policy, deciles: Deciles) -> None:
    # heavy-capex inputs plus Override("return.runway", 0.214): the sentence reads
    # "starts at 21.4%, the agent's override; the five-year marginal is <R>%" and still names the newest year's marginal
```

In `tests/engine/test_mature_stable.py`: re-pin `test_own_return_through_the_runway_then_the_terminal` and `test_a_longer_runway_at_a_return_above_the_terminal_is_worth_more` on spec 13.3's shape (the return fades from year 1 on a stable path); add `test_a_stable_row_s_value_is_the_spec_s_13_3_figure` asserting `mature_stable_values(100.0, Charge(0.20, 0.13, R, GT, hold=0), 10)[1] == pytest.approx(1315.0993, abs=1e-3)`.

In `tests/engine/test_golden.py`: nothing new; the goldens are re-captured in Step 4.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/engine/test_route.py tests/engine/test_mature_stable.py`
Expected: FAIL (`charge` key missing; stable values on the old shape).

- [ ] **Step 3: Implement.** `route_mature_growth.py`: `_growth_and_charge` builds `GrowthPath(anchor.ntm_net_income, path.steps, belief.rate, runway, policy.fade_years, revenue_steps=path.revenue_steps)` and `roic.charge(policy, hold_years(growth))`; the intermediates gain `"charge": {...}` from `charge_growth`, `return_by_year`, `charge.hold`, `path.revenue_steps`; `_growth_above_return` uses `first_negative_year` and the spec 6.1 sentence (`f"In year {t} the charge pays for {h:.1%} of revenue growth at a return of {ret:.1%}, so the year pays out less than nothing: the owner funds the growth."` plus `f" {k} more such year(s)."` when more); `trailing_flags(i, t, gap, policy, roic)`; `_rebuilt` reads `im["charge"]["revenue_steps"]` and `im["charge"]["hold_years"]`; `_roic_charges(charge, usable, moat, policy)` builds each key's charge with `hold=charge.hold`; `growth_cross_check` carries `"charge"` as the route does. `route_mature_stable.py`: `roic.charge(policy, 0)` (hold 0, the fade from year 1), intermediates gain `"charge"` built on `GrowthPath(e_normalized, (g_t, g_t), g_t, runway)`, `trailing_flags(i, t, gap, policy, roic)`. `mature_stable.py`: `mature_stable_values` builds its `GrowthPath` as today; nothing else.

- [ ] **Step 4: Re-capture the two goldens and check the five companies.** Run the README's capture command for MGCO and MSCO only; add a README paragraph naming spec sections 6.1 to 6.3 as the cause and the new `charge` key; assert in the test that HGCO, YGCO, DCCO and SUCO are unchanged (they are compared bit for bit already). Then the read-only check against the live database: a scratch script (not committed) that opens `~/.local/share/fairband/fairband.db` with `?mode=ro`, builds each of GOOG, QCOM, AMZN, META and RELY through `build_inputs` and `value_company`, applies each company's applied overrides through `review_company`, and prints the mechanical and reviewed values. Expected within 0.1%: GOOG 394.73 / 339.28, QCOM 336.88 / 199.04, AMZN 299.18 / 259.40, META 716.57 / 650.49, RELY 50.07 / 24.04. A figure off by more: stop and name the rule that reads differently (spec section 5's last paragraph).

- [ ] **Step 5: Update the documents.** `docs/method.md`: section 0's list of specs gains `docs/superpowers/specs/2026-11-09-engine-round-2-design.md`; 4.6 (the one-year figure recorded, shown not used), 4.8 rewritten on spec 6.1 to 6.3 (cash_t, h, K, return_t, no floor), 5.3 (the revenue steps and their fallback), 5.6 to 5.8 (the charge, the solve holding K, the return keys on the new shape; 5.8 says that at the `0.09` key the value is the NTM earnings over r whatever the path, so its implied growth is none unless the price sits there), 5.11 (the new note and sentence), 5.13 (re-pinned worked numbers: the spec's 13.1 to 13.4, replacing the calibration spec's figures), 6.3 and 6.5 (the fade from year 1 on a stable row; the stable row's flags), 8 (`growth-above-return`'s new rule words, `consensus-basis-unknown`, `step-series-disagree`, the `heavy-capex` sentence with and without an override). `methodology.html`: the charge passage says the charge pays for revenue growth, that a year can pay out less than nothing when growth outruns the return, and that the return holds through the high-growth years then fades to the terminal return; the two route lists say the same; the examples' figures are re-read at method 1.0 (the page's figures are live from the policy where marked, and the worked example's numbers are updated from the new arithmetic).

- [ ] **Step 6: Run the checks**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/fairband/engine docs/method.md src/fairband/web/static/methodology.html tests/engine tests/fixtures/golden
git commit -m "Run both mature routes on the charge without its floor, on revenue growth and with the held-then-faded return, and say so in the method and on the Methodology page"
```

---

### Task 6: The two inputs, `value.outside` and `shares.diluted`

**Files:**
- Modify: `src/fairband/engine/overrides.py` (`OverrideTag`, `BRIDGE_ORDER`, `TAGS`, `LABELS`, `INPUT_OF`, `_reading`), `src/fairband/engine/route_steps.py` (`outside_value`), `src/fairband/engine/route.py` (`value_company`, `_valued`, `reprice`), the four valued routes' at-price calls, `src/fairband/engine/route_start_up.py` (the count)
- Modify: `docs/method.md` 14.2, 14.3, 14.4, 14.5; `src/fairband/web/static/app.js` (the bridge's units and labels for the two tags)
- Test: `tests/engine/test_overrides.py`, `tests/engine/test_review.py`, `tests/engine/test_route.py`, `tests/web/test_reviews_api.py`

**Interfaces:**
- Produces: tags `"shares.diluted"` (`_spec("shares.diluted", _ALL, "shares", period_tied_only=True, low_open=True)`) and `"value.outside"` (`_spec("value.outside", _ALL - {"start-up"}, "USD a share")`); `BRIDGE_ORDER` ends `(..., "balance.cash", "shares.diluted", "value.outside")`; `LABELS["shares.diluted"] == "diluted shares"`, `LABELS["value.outside"] == "outside the business"`; `INPUT_OF["shares.diluted"] == "shares_diluted"`; `current_reading(result, "shares.diluted")` is the count the result cites (`im["shares"]`, else the DATA input), `current_reading(result, "value.outside")` is `im.get("outside_value_per_share", 0.0)` on a route that reads it, `None` on Start-up; `route_steps.outside_value(c: Context) -> float`; every valued route's `Valued.value` is the route's value a share plus the outside figure, its at-price functions take `price - outside`, and the intermediates carry `outside_value_per_share` under the override only; `value_company` reads `judged["shares.diluted"]` before the "no diluted share count" guard; `reprice` targets `price - im.get("outside_value_per_share", 0.0)`.

- [ ] **Step 1: Write the failing tests.** In `test_overrides.py`:

```python
def test_the_two_new_tags_rules(policy: Policy) -> None:
    assert check_override("value.outside", 12.0, "mature-growth", policy, ["filing"], "lasting", None) == ("applied", "")
    assert check_override("value.outside", 12.0, "start-up", policy, ["filing"], "lasting", None)[0] == "refused-route"
    assert check_override("value.outside", 1200.0, "mature-growth", policy, ["filing"], "lasting", None)[0] == "refused-unit"
    assert check_override("shares.diluted", 1.06e9, "mature-growth", policy, ["filing"], "period-tied", None) == ("applied", "")
    assert check_override("shares.diluted", 1.06e9, "mature-growth", policy, ["filing"], "lasting", None) == ("refused-unit", "shares.diluted is period-tied only")
    assert check_override("shares.diluted", 0.0, "mature-growth", policy, ["filing"], "period-tied", None)[0] == "refused-unit"
    assert BRIDGE_ORDER[-2:] == ("shares.diluted", "value.outside")
    assert LABELS["shares.diluted"] == "diluted shares" and LABELS["value.outside"] == "outside the business"
```

In `test_route.py` (on the fixture companies):

```python
def test_value_outside_adds_to_the_value_and_targets_the_business_price(policy: Policy, deciles: Deciles) -> None:
    plain = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    outside = value_company(mature_growth_inputs(), deciles, policy, TODAY, {"value.outside": _override("value.outside", 12.0)})
    assert outside.value == pytest.approx(plain.value + 12.0)
    assert outside.levels.buy == pytest.approx(levels_for(outside.value, outside.intermediates["moat"], policy).buy)  # the levels helper the file uses
    assert outside.intermediates["outside_value_per_share"] == 12.0
    assert outside.intermediates["implied_growth"] == pytest.approx(
        implied_growth((plain.price - 12.0) * plain.intermediates["shares"], _path_of(outside), _charge_of(outside), hi=2.0)
    )
    assert all(v == pytest.approx(w + 12.0) for v, w in zip(outside.intermediates["value_by_runway"].values(), plain.intermediates["value_by_runway"].values()))


def test_an_outside_value_that_sinks_the_value_refuses(policy: Policy, deciles: Deciles) -> None:
    r = value_company(mature_growth_inputs(), deciles, policy, TODAY, {"value.outside": _override("value.outside", -1000.0)})
    assert r.value is None and r.refusal == "value not positive under the reinvestment charge"


def test_shares_diluted_replaces_the_count_everywhere(policy: Policy, deciles: Deciles) -> None:
    plain = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    more = value_company(mature_growth_inputs(), deciles, policy, TODAY, {"shares.diluted": _override("shares.diluted", plain.intermediates["shares"] * 1.06, lifetime="period-tied")})
    assert more.intermediates["shares"] == pytest.approx(plain.intermediates["shares"] * 1.06)
    assert more.intermediates["ntm_net_income"] == pytest.approx(plain.intermediates["ntm_net_income"] * 1.06)
    assert current_reading(plain, "shares.diluted") == pytest.approx(plain.intermediates["shares"])


def test_the_start_up_requirement_reads_the_count_and_no_outside_value(policy: Policy, deciles: Deciles) -> None:
    # start_up_inputs() with shares.diluted doubled: the requirement's per-share figures halve; value.outside is refused-route
```

In `test_review.py`: `test_the_two_new_lines_close_the_bridge` (a review with `balance.cash`-free overrides `shares.diluted` and `value.outside` on MGCO: the bridge's last two lines in order, the outside line's old value 0.0 and delta 12.0, the count line's old value the engine's count). In `tests/web/test_reviews_api.py`: an API post of each tag (the route and lifetime rules through the API, the bridge labels in the answer).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/engine/test_overrides.py tests/engine/test_route.py tests/engine/test_review.py tests/web/test_reviews_api.py`
Expected: FAIL (`refused-not-input`).

- [ ] **Step 3: Implement.** `overrides.py` per the Interfaces block; `_reading` for the two tags; the LOCKED sentence for `shares_diluted` stays. `route_steps.py`: `outside_value(c) -> float` = `chosen(c, "value.outside", 0.0)`; `judgment_inputs` already renders JUDGMENT entries by tag (the outside one in "USD a share", the count in "shares"). `route.py` `value_company`: `shares = inputs.shares_diluted` replaced by the override's value when `judged` holds `shares.diluted`, before the guard; `reprice`: the at-price rebuilds (`growth_at_price`, `revenue_at_price`, `decline_at_price`, `stable_at_price`) receive `price - im.get("outside_value_per_share", 0.0)`. Each valued route: `outside = outside_value(c)`; `value = route value + outside`; `value_by_runway`/`value_by_roic`/the grid values add `outside`; `*_at_price(im, c.price - outside, value, policy)`; `im["outside_value_per_share"] = outside` only when the override applies; the refusal check `if value <= 0` reads the sum. `route_start_up.py`: the count from `c.shares` is already the override's through `value_company`. `app.js`: the bridge's unit table gains `'shares.diluted': 'shares'` and `'value.outside': 'per-share'` and the label table the two labels (find the tables by the `overrides.TAGS` comment near line 1269); `report.js` the same where it carries its own tag table for section 8's bridge lines. `docs/method.md` 14.2 (two rows, the table's words from spec 8), 14.3 (the sixteen become eighteen; the period-tied rule names the count), 14.4 (two bullets per spec 8), 14.5 (the order and the labels).

- [ ] **Step 4: Run the checks**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass; the goldens unchanged (no override in them).

- [ ] **Step 5: Commit**

```bash
git add src/fairband/engine docs/method.md src/fairband/web/static/app.js tests
git commit -m "Add the value outside the business and the diluted share count as inputs an agent may set, each a bridge line, the outside value added to every route's value a share"
```

---

### Task 7: The drawer's charge rows

**Files:**
- Modify: `src/fairband/web/static/app.js` (the Mature Growth and Mature Stable sections' charge group)
- Test: `tests/web/test_reader_blocks.py` or `tests/web/test_company_reads.py` (whichever renders the drawer through `render.mjs`)

**Interfaces:**
- Consumes: the `charge` intermediates of Task 5.

- [ ] **Step 1: Write the failing test**: the drawer of a Mature Growth row shows a "Return by year" row reading "20.0% through year 6, then to 13.0% in year 10" (or the ends and the hold in that form), a "Growth the charge pays for" row with the revenue steps beside the earnings steps, and the `growth-above-return` sentence when present. Use the existing drawer test's fixture row.

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest -q tests/web/test_reader_blocks.py`
Expected: FAIL (rows absent).

- [ ] **Step 3: Implement** in `app.js`: in the mature route's charge group, from `im.charge`: `['Return by year', <R through year K, then to T in year N>]`, `['Growth the charge pays for', <h2, h3 as percents> + ' on revenue (earnings ' + <g2, g3> + ')']`, `['Newest year's marginal return', F.formatPercent(im.runway_return.one_year)]` when present. Keep the page's register (plain words, no engine names).

- [ ] **Step 4: Run the tests**

Run: `uv run pytest -q tests/web`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/web/static/app.js tests/web
git commit -m "Show the charge's return by year, the growth it pays for and the newest year's marginal return in the drawer"
```

---

### Task 8: The playbook, the refs' words and the backlog

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (the overrides table: two rows; the judgments table's `roic` row; the flags the agent reads), `playbook/fairband-research/reference/report-template.md` (section 8's detail: the outside value, the count, the double-count rule, the NTM net-income effect), `playbook/fairband-research/reference/tools.md` and `reference/citations.md` (the two tags; the new intermediates), `playbook/fairband-research/reference/register.md` (the reader's phrase for the outside value: "assets outside the business, worth $X a share")
- Modify: `src/fairband/reports/refs.py` (`_SNAPSHOT_PATH_WORDS`)
- Modify: `docs/backlog.md` (B-129, B-130, B-133, B-139, B-140 to Done with this plan's commits; B-143 stays)
- Test: `tests/test_playbook.py`, `tests/reports/test_refs.py`

**Interfaces:**
- Produces: `_SNAPSHOT_PATH_WORDS["intermediates/charge/hold_years"] == "the years the runway return holds"`, `["intermediates/runway_return/one_year"] == "the newest year's marginal return"`, `["intermediates/outside_value_per_share"] == "the value outside the business"`.

- [ ] **Step 1: Write the failing tests**: in `test_refs.py`'s describe table, the three new paths' words; in `test_playbook.py`, whatever the file pins about the overrides table (the tag count, the judgments) extended to the two tags and the `roic` row's new sentence ("when `heavy-capex` fires, read the newest year's marginal return and the capex guidance").

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest -q tests/reports/test_refs.py tests/test_playbook.py`
Expected: FAIL.

- [ ] **Step 3: Write the playbook lines** per spec 12: the `roic` judgment row: "the return on invested capital and the runway return; when `heavy-capex` fires, read `intermediates/runway_return/one_year` and the capex guidance, decide the runway return and cite both figures"; the overrides table rows for `value.outside` (−1,000 to 1,000 dollars a share; after tax; the agent strips the asset's gains from earnings through `earnings.nri_gap` so nothing counts twice) and `shares.diluted` (above 0 shares; period-tied only; a raised count raises NTM net income with it, so read the consensus EPS's share basis first); section 8's detail; the three notes in the flags the agent reads; `tools.md`'s `override_add` line naming the eighteen tags; `citations.md`'s `snapshot:<id>/intermediates/<path>` row naming the new paths. `refs.py`: the three words. `docs/backlog.md`: the five rows to Done, each with this plan's commits.

- [ ] **Step 4: Run the checks**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add playbook src/fairband/reports/refs.py docs/backlog.md tests
git commit -m "Tell the agent to judge the runway return under heavy capex, name the two new inputs and the three new notes in the playbook, and close the five backlog rows"
```

---

### Task 9: The live steps and the readout

Runs after the branch is merged to main (the merge is the founder's call through the finishing skill).

- [ ] **Step 1: Back up the live database** with SQLite's backup API to `~/.local/share/fairband/fairband-before-method-1.0-2026-11-XX.db` (the date of the run).
- [ ] **Step 2: Restart the web server on 8470 from main** (`setsid nohup uv run python -m fairband serve >> ~/.local/share/fairband/server.log 2>&1 &` after stopping the running one; confirm `GET /api/policy` answers 200).
- [ ] **Step 3: Run one revalue** (`POST /api/refresh` kind `revalue`, or the MCP `refresh_start("revalue")`) and wait for it.
- [ ] **Step 4: The readout**, written into the spec's decision log: the five companies' mechanical and reviewed values against spec section 5; the Mature Growth and Mature Stable counts, the median move, the rows with a negative cash year, the rows whose return fades, the `consensus-basis-unknown` and `step-series-disagree` counts; the revenue-growth, Decline and Start-up rows bit for bit against the previous refresh; the existing overrides still applied (GOOG's and META's `return.runway`, AMZN's, QCOM's and RELY's steps).
- [ ] **Step 5: Commit the readout** to the spec's decision log and push with the founder's word.
