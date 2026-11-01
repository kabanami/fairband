# Calibration of the Mature Growth Charge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Mature Growth value charges growth at the return on new capital, floors the payout at zero and fades the consensus growth to the belief over five years; the terminal reads the same return; Mature Stable rows carry a growth-route cross-check; and a revalue mode re-runs the engine on stored facts so the first run's data can be read under the new rules.

**Architecture:** The ROIC module gains the runway-return build (marginal, three-year fallback, floor, charge-off) beside the ten-year aggregate; `RoicTerms` carries it to both routes. The growth model gains a fade length and the payout floor. The growth route writes the new intermediates and sensitivity keys and raises the new flag; the stable route runs the growth route's anchor and path as a cross-check. Policy v2 holds the new values; the method version becomes 0.2. A `revalue` refresh kind values every company of the latest universe from the store with no vendor call.

**Tech Stack:** Python 3.13, uv, pytest, Ruff, mypy. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-01-calibration-design.md`. It amends `docs/superpowers/specs/2026-10-31-mechanical-screen-design.md` section 6.6 and `docs/legacy/design.md` 6.5 and 6.6 for the two mature routes.

## Global Constraints

- `uv run` for every command; before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- Code holds no valuation constant: every number of spec section 6 comes from `src/fairband/policy/fairband-policy-v2.toml`, each `[values.<name>]` with `value` and `source`.
- `fairband-policy-v1.toml` stays byte-identical; its sha256 is `cfc46d15585c283322f50a710d3385f4921c186ed94679a542c0571a43b54bde`, the hash the first run's 1,759 snapshots cite. The engine loads v2 and has no code path for the v1 rules.
- Method version `fairband-mechanical/0.2` (`fairband.engine.METHOD_VERSION`).
- r = 0.09 and g_T = 0.03 stay; the runway, the margin of safety, the belief, the 13% cap and the classifier are unchanged.
- The same inputs and the same policy give the same intermediates, bit for bit.
- Every refusal stays a `ValuationResult` with `value=None` and a reason; a value at or below zero is still refused.
- Intermediates hold JSON values only (no NaN, no infinity); `result_to_json` round-trips.
- Flags: `Flag(code, word, sentence)`, code in kebab-case, word short enough for the Flags column, sentence one line for the drawer.
- Tests under `tests/` mirror the package; fixtures synthetic. Never a vendor call in a test; never a key anywhere.
- Commit messages: one plain sentence in the imperative; every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Work on a branch, never on `main`.

## Review Focus

Inputs the spec implies but no acceptance number covers. Each has its test in the task named.

1. **A company whose kept ROIC years are exactly six** must use the marginal return over five positions (first = oldest kept year), not fall back; at five kept years it must use the three-year aggregate; at four, "ROIC unavailable". Test in Task 2 (`test_marginal_needs_six_kept_years`).
2. **A fade where the runway cuts inside the fade** (runway 5 with g_3 above the belief) must take the faded rates for years 4 and 5 and nothing after. Test in Task 3 (`test_fade_cut_by_the_runway`).
3. **A consensus step that is `None`** (missing) takes the belief for g_3, so there is no fade and no flag. Test in Task 3 (`test_no_fade_when_g3_is_the_belief`).
4. **The implied-growth solve with the fade** must move the fade target with each trial, so a round trip from the value at belief returns the belief. Test in Task 4 (`test_implied_growth_round_trip_with_fade`).
5. **A revalue on a database whose latest universe lists a company with no stored statements** must give that company a refusal snapshot and go on; the run never raises on one company. Test in Task 6 (`test_revalue_refuses_a_company_without_facts`).

---

## File structure

```
src/fairband/
  engine/__init__.py           METHOD_VERSION → 0.2
  engine/roic.py               + RunwayReturn, marginal_return, window_aggregate, runway_return, terminal_return
  engine/mature_growth.py      GrowthPath.fade_years; growth_rates fades; cash_to_equity floors; value_at_belief charges the terminal under charge-off; floored_years
  engine/returns.py            expected_return takes the resolved rates
  engine/route_steps.py        RoicTerms carries the runway return; expected() takes rates; common_inputs adds the runway_return input
  engine/route_mature_growth.py  fade, flag, new sensitivity keys, growth_at_price rebuild; growth_cross_check for the stable route
  engine/route_mature_stable.py  shared terminal, cross-check intermediates
  policy/__init__.py           v2 default; four new fields
  policy/fairband-policy-v2.toml  new
  refresh/run.py               Kind "revalue"; _revalue; calibration(admitted, excluded, snapshots)
  __main__.py                  --kind revalue without keys
  web/rows.py                  growthRouteValue column
  web/static/design-system/components/bundle.js  the column definition
  web/static/app.js            the drawer's cross-check line
tests/
  policy/test_policy.py, engine/test_roic.py, engine/test_mature_growth.py, engine/test_returns.py,
  engine/test_route.py, refresh/test_run_revalue.py (new), web/test_app.py
```

---

### Task 1: Policy v2 and the method version

**Files:**
- Create: `src/fairband/policy/fairband-policy-v2.toml`
- Modify: `src/fairband/policy/__init__.py`, `src/fairband/engine/__init__.py`
- Test: `tests/policy/test_policy.py`, `tests/engine/test_route.py`

**Interfaces:**
- Produces: `Policy.marginal_return_span_years: int` (5), `Policy.marginal_capital_growth_min: float` (0.20), `Policy.fallback_return_years: int` (3), `Policy.fade_years: int` (5); `load_policy()` returns version `fairband-policy-v2`; `METHOD_VERSION == "fairband-mechanical/0.2"`.

- [ ] **Step 1: Write the failing tests** in `tests/policy/test_policy.py`:

```python
V1_SHA256 = "cfc46d15585c283322f50a710d3385f4921c186ed94679a542c0571a43b54bde"

def test_v2_is_the_default_and_carries_the_calibration_values() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v2"
    assert p.marginal_return_span_years == 5 and p.marginal_capital_growth_min == 0.20
    assert p.fallback_return_years == 3 and p.fade_years == 5
    assert p.roic_sensitivity == (0.15, 0.09) and p.wide_terminal_roic_cap == 0.13
    assert p.required_return == 0.09 and p.terminal_growth == 0.03  # unchanged

def test_v1_file_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v1.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V1_SHA256

def test_return_measure_note_is_recorded() -> None:
    raw = load_policy().raw
    note = raw["values"]["return_measure"]
    assert "value" not in note and "Return on invested capital" in note["note"]
    assert "source" in note
```

Change `_packaged_bytes()` and `test_values_match_design` to read v2 (`version == "fairband-policy-v2"`); the other assertions of that test stay true. In `tests/engine/test_route.py` the method-version assertion reads `METHOD_VERSION` already; add `assert METHOD_VERSION == "fairband-mechanical/0.2"` to `test_mature_growth_end_to_end`.

- [ ] **Step 2: Run the tests to see them fail**: `uv run pytest tests/policy -q` — FAIL on the version and the missing attributes.

- [ ] **Step 3: Write `fairband-policy-v2.toml`**: copy v1, set `[meta] version = "fairband-policy-v2"`, rewrite the header comment to say v2 and name the spec (`docs/superpowers/specs/2026-11-01-calibration-design.md`), then add, with the exact source lines of spec section 6:

```toml
[values.marginal_return_span_years]
value = 5
source = "calibration spec 5.1; Damodaran, Investment Valuation ch. 11 (openalice H21) gives the measure, not the window; policy value"

[values.marginal_capital_growth_min]
value = 0.20
source = "calibration spec 5.1: capital must have grown by a fifth of its opening level for the marginal return to be usable; policy value"

[values.fallback_return_years]
value = 3
source = "calibration spec 5.1; Damodaran H29, keep the company's return on capital; the window is a policy value"

[values.fade_years]
value = 5
source = "calibration spec 5.4; Damodaran's template fades growth in five equal steps (openalice H2)"

[values.return_measure]
source = "calibration spec 6; founder decision 2026-11-01"
note = "Return on invested capital, not return on equity. Damodaran prescribes return on equity for an equity model (H11) and adds back recent buybacks to book equity when buybacks distort it (IV 2e ch. 13). Fairband uses invested capital because it is the base that growth draws on and it holds where book equity is shrunk, zero or negative. Founder decision 2026-11-01."
```

Change the `roic_sensitivity` note to "The first ROIC of the sensitivity is the runway return of spec 5.1; a fourth value shows the old ten-year basis." and the `wide_terminal_roic_cap` source to add "; the input is the runway return (calibration spec 5.3)".

- [ ] **Step 4: Change the loader**: `_POLICY_FILE = "fairband-policy-v2.toml"`; add the four fields to `Policy` after `inflation_addition`, read with `read("marginal_return_span_years", _whole)`, `read("marginal_capital_growth_min", _num)`, `read("fallback_return_years", _whole)`, `read("fade_years", _whole)`. `test_every_value_has_a_source_line` still passes: `return_measure` has a source. Set `METHOD_VERSION = "fairband-mechanical/0.2"` in `src/fairband/engine/__init__.py`.

- [ ] **Step 5: Run the whole suite**: `uv run pytest -q`. Expected: the policy tests pass; tests elsewhere that pin `fairband-policy-v1` by name fail. Fix them to read `policy.version` rather than the literal (grep `policy-v1` under `tests/`). Expected after: PASS.

- [ ] **Step 6: Commit**: `git add -A && git commit -m "Add policy v2 with the calibration values and move the method version to 0.2"`.

---

### Task 2: The runway return and the terminal return

**Files:**
- Modify: `src/fairband/engine/roic.py`, `src/fairband/engine/route_steps.py:74-116`
- Test: `tests/engine/test_roic.py`, `tests/engine/test_route.py`

**Interfaces:**
- Produces, in `roic.py`:
  - `Used = Literal["marginal", "three-year", "floor", "off", "unavailable"]`
  - `@dataclass(frozen=True) class RunwayReturn: used: Used; marginal: float | None; marginal_usable: bool; three_year: float | None; ten_year: float | None; chosen: float | None; value: float; charge_off: bool; flags: tuple[Flag, ...]` — `chosen` is the measure before the floor (`None` for off and unavailable); `value` is what the charge uses: the chosen measure floored at r, or the terminal return for off and unavailable.
  - `marginal_return(by_year: Sequence[RoicYear], span: int, growth_min: float) -> tuple[float | None, bool]` — `(marginal, usable)`; `(None, False)` with fewer than `span + 1` kept years or a zero capital change.
  - `window_aggregate(by_year: Sequence[RoicYear], n: int) -> tuple[float | None, float]` — `(aggregate, capital_sum)` over the last `n` kept years; aggregate `None` when the capital sum is at or below zero.
  - `runway_return(result: RoicResult, moat: Moat, policy: Policy, min_years: int = 5) -> RunwayReturn`.
  - `terminal_return(rr: RunwayReturn, moat: Moat, policy: Policy) -> float` — Wide: `max(r, min(rr.chosen, cap))` when `chosen` is a number; Wide and `used == "off"`: `cap`; Wide and `used == "unavailable"`: r; Narrow and None: r. `terminal_roic(aggregate, moat, policy)` stays for the sensitivity keys.
  - `aggregate_roic` no longer flags `charge-zeroed`; a ten-year capital sum at or below zero leaves `aggregate=None` and flags `ten-year-roic-unavailable` / "Ten-year ROIC unavailable" / "Average invested capital sums to zero or below over the {n} ROIC years, so the ten-year ROIC is unavailable."
- Produces, in `route_steps.py`: `RoicTerms(result, runway_return: RunwayReturn, usable: float | None, runway: float, terminal: float, charge_off: bool, flags)`; `RoicTerms.of(years, moat, policy)`; `RoicTerms.intermediates()` returns `{"roic": {...as today}, "runway_return": {"used", "marginal", "marginal_usable", "three_year", "ten_year", "value"}, "terminal_roic": terminal}`; `common_inputs` adds `data(i, "runway_return", roic.runway, "ratio", "statements", note)` after `_aggregate_roic`, the note from `runway_note(rr)` below.

The flags `runway_return` raises, in this order, after the ones `aggregate_roic` raised:
- `used == "off"`: `charge-zeroed` / "Charge zeroed" / "The marginal return is not usable and average invested capital sums to zero or below over the last {n} ROIC years, so the runway charge is zero; the terminal still charges at {terminal:.1%}." (the terminal is the moat's: `cap` for Wide, r otherwise).
- `used == "floor"`: `return-floored` / "Return floored" / "The {measure} return of {chosen:.1%} is below the required return, so the charge uses {r:.1%}." where measure is "five-year marginal" or "three-year".
- `used == "unavailable"`: no new flag; `aggregate_roic`'s `roic-unavailable` already fired.

`runway_note(rr: RunwayReturn) -> str`, the input tag's note: `"five-year marginal return on new capital"`, `"three-year aggregate ROIC (marginal not usable)"`, `"floored at the required return; the {measure} was {chosen:.1%}"`, `"charge off: capital at or below zero"`, `"unavailable: fewer than 5 ROIC years"`.

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_roic.py`, with a helper that builds kept years from `(nopat, average_capital)` pairs:

```python
def kept(pairs: list[tuple[float, float]], first_year: int = 2017) -> RoicResult:
    rows = tuple(RoicYear(first_year + k, n, c, n / c if c else None) for k, (n, c) in enumerate(pairs))
    return RoicResult(aggregate=window_aggregate(rows, 10)[0], years_used=len(rows), by_year=rows, flags=())

SPEC = [(100, 1000), (110, 1050), (125, 1100), (140, 1200), (150, 1300),
        (180, 1500), (220, 1700), (260, 1900), (300, 2100), (350, 2300)]

def test_marginal_return_spec_example(policy: Policy) -> None:
    rr = runway_return(kept(SPEC), "Wide", policy)
    assert rr.marginal == pytest.approx(0.2000) and rr.marginal_usable
    assert rr.three_year == pytest.approx(0.1444, abs=5e-5)
    assert rr.ten_year == pytest.approx(0.1277, abs=5e-5)
    assert rr.used == "marginal" and rr.chosen == rr.value == pytest.approx(0.2000)
    assert rr.charge_off is False and rr.flags == ()

def test_fallback_when_capital_barely_grows(policy: Policy) -> None:
    flat = [(n, 2000 + 10 * k) for k, (n, _) in enumerate(SPEC)]
    rr = runway_return(kept(flat), "Wide", policy)
    assert rr.marginal_usable is False and rr.used == "three-year"
    assert rr.value == pytest.approx(0.1458, abs=5e-5)

def test_fallback_when_nopat_falls(policy: Policy) -> None:
    falling = SPEC[:5] + [(90, 1500), (80, 1700), (70, 1900), (60, 2100), (50, 2300)]
    rr = runway_return(kept(falling), "Wide", policy)
    assert rr.marginal == pytest.approx(-0.10) and rr.marginal_usable is False
    assert rr.three_year == pytest.approx(180 / 6300)  # below r, so the floor applies
    assert rr.used == "floor" and rr.chosen == rr.three_year and rr.value == 0.09

def test_floor_at_the_required_return(policy: Policy) -> None:
    low = [(n * 0.3, c) for n, c in SPEC]  # marginal (105 − 30) ÷ 1000 = 0.075, usable, under r
    rr = runway_return(kept(low), "Wide", policy)
    assert rr.used == "floor" and rr.value == 0.09 and rr.chosen == pytest.approx(0.075)
    assert [f.code for f in rr.flags] == ["return-floored"]

def test_marginal_needs_six_kept_years(policy: Policy) -> None:
    six = runway_return(kept(SPEC[-6:]), "Wide", policy)
    assert six.used == "marginal" and six.marginal == pytest.approx(200 / 1000)
    five = runway_return(kept(SPEC[-5:]), "Wide", policy)
    assert five.marginal is None and five.used == "three-year"
    four = runway_return(kept(SPEC[-4:]), "Wide", policy)
    assert four.used == "unavailable" and four.value == 0.09 and four.chosen is None

def test_charge_off_on_a_non_positive_three_year_sum(policy: Policy) -> None:
    negative = [(20.0, -50.0)] * 10
    wide = runway_return(kept(negative), "Wide", policy)
    assert wide.used == "off" and wide.charge_off and wide.value == 0.13
    assert [f.code for f in wide.flags] == ["charge-zeroed"]
    narrow = runway_return(kept(negative), "Narrow", policy)
    assert narrow.value == 0.09

@pytest.mark.parametrize(("moat", "used", "chosen", "expected"), [
    ("Wide", "marginal", 0.28, 0.13), ("Wide", "three-year", 0.098, 0.098),
    ("Wide", "floor", 0.06, 0.09), ("Narrow", "marginal", 0.28, 0.09),
    ("Wide", "off", None, 0.13), ("None", "off", None, 0.09), ("Wide", "unavailable", None, 0.09),
])
def test_terminal_return(policy, moat, used, chosen, expected) -> None:
    rr = RunwayReturn(used, None, False, None, None, chosen, 0.0, used == "off", ())
    assert terminal_return(rr, moat, policy) == pytest.approx(expected)

def test_ten_year_capital_at_or_below_zero_is_unavailable_not_zeroed() -> None:
    r = aggregate_roic(history(11, ppe=-50.0))
    assert r.aggregate is None and codes(r) == ("ten-year-roic-unavailable",)
```

Rename `test_negative_capital_zeroes_charge` and `test_zero_capital_does_not_divide_by_zero` to assert the new flag code. In `tests/engine/test_route.py`, add to `MATURE_GROWTH_KEYS` and `MATURE_STABLE_KEYS` the key `runway_return` and remove `runway_roic` from the growth set (Task 4 writes the route); add a test that the route's input list carries `runway_return` with a note (`test_runway_return_input_carries_its_note`). Keep `test_capital_at_or_below_zero_zeroes_the_charge` but assert the terminal charge stays (Task 4 pins the value).

- [ ] **Step 2: Run** `uv run pytest tests/engine/test_roic.py -q`. Expected: FAIL, names not defined.

- [ ] **Step 3: Implement** the functions in `roic.py` with the signatures above. `marginal_return`: first = `by_year[-1 - span]`, last = `by_year[-1]`; `delta_capital = last.average_capital - first.average_capital`; marginal is `None` when `delta_capital == 0`; usable when `delta_capital > 0 and delta_capital >= growth_min * abs(first.average_capital) and last.nopat - first.nopat > 0`. `runway_return`: if `result.years_used < min_years` → unavailable (value = r for every moat, since the terminal is r when unavailable); else marginal; if usable → chosen = marginal; else `three, capital = window_aggregate(by_year, policy.fallback_return_years)`; if `capital <= 0` → off; else chosen = three; `value = max(r, chosen)`; `used = "floor"` when `chosen < r`. `ten_year = result.aggregate`. Rewrite the module docstring: the ten-year aggregate is shown and feeds the sensitivity; the runway return feeds the charge.

- [ ] **Step 4: Rebuild `RoicTerms.of`** in `route_steps.py`: `result = aggregate_roic(years)`; `rr = runway_return(result, moat, policy)`; `terminal = terminal_return(rr, moat, policy)`; `usable` = the positive ten-year aggregate (for the "ten-year" sensitivity key); `runway = rr.value`; `charge_off = rr.charge_off`; `flags = result.flags + rr.flags` (drop the old "aggregate not positive" flag: a non-positive ten-year aggregate no longer touches the charge). Update the class and module docstrings.

- [ ] **Step 5: Run** `uv run pytest tests/engine -q`. Expected: `test_roic.py` passes; `test_route.py` fails on the intermediates and the terminal (Task 4 fixes the route). Run `uv run mypy src` — PASS.

- [ ] **Step 6: Commit**: `git commit -am "Build the runway return from the marginal and three-year returns and read the terminal from it"`.

---

### Task 3: The fade and the payout floor in the growth model

**Files:**
- Modify: `src/fairband/engine/mature_growth.py`
- Test: `tests/engine/test_mature_growth.py`

**Interfaces:**
- Produces: `GrowthPath(year1, steps, belief, runway, fade_years: int = 0)`; `growth_rates(path)` fades when `g_3 > belief` and `fade_years > 0`; `cash_to_equity(ni, g_next, roic, charge_off=False) -> float` returns `ni * max(0.0, 1 - g_next / roic)` (or `ni` when off or `roic` is infinite); `value_at_belief(path, charge)` applies `charge_off` to years 1 to N−1 only and always charges year N and the terminal at `charge.terminal_roic`; `floored_years(path, charge) -> tuple[int, ...]` the years whose payout the floor raised to zero, in order; `implied_growth` unchanged in signature.

- [ ] **Step 1: Write the failing tests** (spec section 7, tolerance 0.01 on values, 1e-4 on rates):

```python
FADE = GrowthPath(1000.0, (0.25, 0.26), 0.053, 20, fade_years=5)
CHARGE = Charge(0.149, 0.13, R, GT)

def test_fade_path_rates_and_earnings() -> None:
    assert growth_rates(FADE)[:8] == pytest.approx(
        (0.25, 0.26, 0.2186, 0.1772, 0.1358, 0.0944, 0.053, 0.053), abs=1e-4)
    assert earnings_by_year(FADE)[:9] == pytest.approx(
        (1000.00, 1250.00, 1575.00, 1919.29, 2259.39, 2566.22, 2808.47, 2957.32, 3114.06), abs=0.01)

def test_value_with_the_fade_and_the_floor() -> None:
    assert value_at_belief(FADE, CHARGE) == pytest.approx(24941.95, abs=0.01)
    assert value_at_belief(replace(FADE, fade_years=0), CHARGE) == pytest.approx(19699.10, abs=0.01)

def test_fade_cut_by_the_runway() -> None:
    five = replace(FADE, runway=5)
    assert growth_rates(five) == pytest.approx((0.25, 0.26, 0.2186, 0.1772), abs=1e-4)
    assert value_at_belief(five, CHARGE) == pytest.approx(20520.66, abs=0.01)

def test_no_fade_when_g3_is_at_or_below_the_belief() -> None:
    path = GrowthPath(1000.0, (0.04, 0.05), 0.053, 20, fade_years=5)
    assert growth_rates(path)[:4] == pytest.approx((0.04, 0.05, 0.053, 0.053))
    assert value_at_belief(path, CHARGE) == pytest.approx(14910.79, abs=0.01)

def test_no_fade_when_g3_is_the_belief() -> None:
    path = GrowthPath(1000.0, (0.25, None), 0.053, 20, fade_years=5)
    assert growth_rates(path)[1:4] == pytest.approx((0.053, 0.053, 0.053))
    assert floored_years(path, CHARGE) == (1,)  # year 1 pays for the 25% step and floors

def test_payout_floor() -> None:
    assert cash_to_equity(100.0, 0.25, 0.149) == 0.0  # −67.79 before the floor
    assert cash_to_equity(100.0, 0.053, 0.149) == pytest.approx(64.43, abs=0.01)
    assert floored_years(FADE, CHARGE) == (1, 2, 3, 4)  # growth above 14.9% in years 2 to 5

def test_charge_off_keeps_the_terminal_charge() -> None:
    off = Charge(0.20, 0.13, R, GT, charge_off=True)
    assert value_at_belief(worked_example(), off) == pytest.approx(28.2647, abs=0.001)
    assert value_at_belief(FADE, replace(CHARGE, charge_off=True)) == pytest.approx(37618.17, abs=0.01)
```

Replace `test_charge_off_equals_uncharged` with `test_charge_off_keeps_the_terminal_charge`. The existing tests keep passing: `fade_years` defaults to 0 and the worked example's payouts never floor.

- [ ] **Step 2: Run** `uv run pytest tests/engine/test_mature_growth.py -q`. Expected: FAIL on `fade_years`, `floored_years`, the charge-off value.

- [ ] **Step 3: Implement.** `growth_rates`: after resolving the two steps, if `fade_years > 0 and g3 > belief`, the rate for year t in 4..3+fade_years is `g3 - (g3 - belief) * (t - 3) / fade_years`; then the belief to the runway; cut to `runway - 1` entries. `value_at_belief`: `off = charge.charge_off and t < n`; the terminal multiple always at `charge.terminal_roic`. `floored_years`: the years t (1-based) where `1 - g_next / roic < 0` and the charge applies. Rewrite the module docstring for the fade, the floor and the charge-off rule (spec 5.1 rule 4, 5.2, 5.4).

- [ ] **Step 4: Run** `uv run pytest tests/engine/test_mature_growth.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**: `git commit -am "Fade the consensus growth to the belief over the policy's years and floor the payout at zero"`.

---

### Task 4: The growth route: intermediates, sensitivity keys, flag, expected return, implied growth

**Files:**
- Modify: `src/fairband/engine/route_mature_growth.py`, `src/fairband/engine/returns.py`, `src/fairband/engine/route_steps.py:162-174`, `src/fairband/engine/route_mature_stable.py:95-103`, `src/fairband/engine/route.py` (docstring list of intermediates)
- Test: `tests/engine/test_route.py`, `tests/engine/test_returns.py`

**Interfaces:**
- Consumes: Task 2's `RoicTerms` and `terminal_roic`; Task 3's `GrowthPath.fade_years`, `floored_years`.
- Produces:
  - `expected_return(price, value, dividend_yield, net_buyback_yield, rates: Sequence[float], horizon: int = 3) -> ExpectedReturn` — `rates` are the growth rates for years 2 to H+1, already resolved; fewer than `horizon` raise `ValueError`.
  - `route_steps.expected(price, value, im, rates: Sequence[float]) -> dict | None`.
  - Growth-route intermediates: as today minus `runway_roic`, plus `runway_return` (Task 2), `fade_years` (int), `growth_rates` (the list for years 2 to N, from `growth_rates(path)`), and `value_by_roic` / `implied_by_roic` keyed `"runway"`, `"0.15"`, `"0.09"`, `"ten-year"`.
  - `growth_at_price(im, price, value, policy)` rebuilds `GrowthPath(im["ntm_net_income"], steps, belief, im["runway"], im["fade_years"])` and the charge from `im["runway_return"]["value"]`, `im["terminal_roic"]`, `im["charge_off"]`; the expected return reads `growth_rates(path)[:3]`.
  - Flag `growth-above-return` / "Growth above return" / `f"Year {t + 1} growth of {g:.1%} exceeds the {ret:.1%} return on new capital; year {t}'s payout is floored at zero and the growth above the return is treated as efficiency growth, which costs nothing."` for the first floored year t (g is year t + 1's growth, which year t's reinvestment pays for; ret the return of year t; amended after the final review), raised after the ROIC flags and before the trailing flags.
  - `value_spread_flag` reads the first three keys of `value_by_roic` only.

- [ ] **Step 1: Write the failing tests.** In `tests/engine/test_returns.py` change the calls to pass resolved rates (`(0.12, 0.10, 0.08)`), keep the assertions, and add:

```python
def test_growth_term_with_and_without_the_fade() -> None:
    faded = expected_return(100.0, 120.0, 0.0, 0.0, (0.25, 0.26, 0.2186))
    assert faded.growth == pytest.approx(0.247, abs=5e-4)
    plain = expected_return(100.0, 120.0, 0.0, 0.0, (0.04, 0.05, 0.053))
    assert plain.growth == pytest.approx(0.048, abs=5e-4)
    with pytest.raises(ValueError):
        expected_return(100.0, 120.0, 0.0, 0.0, (0.04, 0.05))
```

In `tests/engine/test_route.py`: update `MATURE_GROWTH_KEYS` (− `runway_roic`, + `runway_return`, `fade_years`, `growth_rates`); in `test_mature_growth_result` replace the `runway_roic` assertions with:

```python
    rr = im["runway_return"]
    expected = runway_return(aggregate_roic(capital), "Wide", policy)
    assert rr == {"used": expected.used, "marginal": expected.marginal,
                  "marginal_usable": expected.marginal_usable, "three_year": expected.three_year,
                  "ten_year": expected.ten_year, "value": expected.value}
    assert im["fade_years"] == 5 and im["terminal_roic"] == terminal_return(expected, "Wide", policy)
    growth = GrowthPath(5_900e6, (0.12, 0.10), 0.063, 20, fade_years=5)
    charge = Charge(rr["value"], im["terminal_roic"], 0.09, 0.03)
    assert im["growth_rates"] == pytest.approx(growth_rates(growth))
    assert set(im["value_by_roic"]) == {"runway", "0.15", "0.09", "ten-year"}
    assert im["value_by_roic"]["runway"] == r.value
    assert im["value_by_roic"]["ten-year"] == pytest.approx(
        value_at_belief(growth, Charge(expected.ten_year, terminal_roic(expected.ten_year, "Wide", policy), 0.09, 0.03)) / 1_000e6)
    assert er["growth"] == pytest.approx((1.12 * 1.10 * (1 + growth_rates(growth)[2])) ** (1 / 3) - 1)
```

and keep every other line of that test with `"aggregate"` renamed `"runway"`. Add:

```python
def test_growth_above_return_flag(mg_inputs, deciles, policy) -> None:
    steep = replace(mg_inputs, annual_estimates=<the fixture's annual estimates with net income 1.40× then 1.40× the base year>)
    r = value_company(steep, deciles, policy, TODAY)
    flag = next(f for f in r.flags if f.code == "growth-above-return")
    assert flag.word == "Growth above return" and flag.sentence.startswith("Year 1 growth of 40.0%")
    assert r.value is not None and r.value > 0

def test_implied_growth_round_trip_with_fade(mg_inputs, deciles, policy) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    im = r.intermediates
    at_value = growth_at_price(im, r.value, r.value, policy)["implied_growth"]
    assert at_value == pytest.approx(im["belief"]["rate"], abs=1e-6)

def test_charge_off_row_keeps_the_terminal_charge(mg_inputs, deciles, policy) -> None:
    # the existing test_capital_at_or_below_zero_zeroes_the_charge's inputs
    r = value_company(<negative-capital inputs>, deciles, policy, TODAY)
    im = r.intermediates
    assert im["charge_off"] is True and im["runway_return"]["used"] == "off"
    assert im["terminal_roic"] == 0.13  # Wide; the terminal multiple is 13.2, not 17.2
    growth = GrowthPath(im["ntm_net_income"], tuple(im["path_steps"]), im["belief"]["rate"], 20, 5)
    assert im["value_total"] == pytest.approx(value_at_belief(growth, Charge(0.13, 0.13, 0.09, 0.03, charge_off=True)))
```

(`steep` and the negative-capital inputs: build them the way the existing tests in that file build variants of `mg_inputs`; the fixture's annual estimates are in `tests/support/engine_companies.py`.)

- [ ] **Step 2: Run** `uv run pytest tests/engine/test_route.py tests/engine/test_returns.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement.** `returns.py`: `rates` resolved by the caller; `level = prod(1 + g for g in rates[:horizon])`; raise when `len(rates) < horizon`. `route_steps.expected(price, value, im, rates)`. `route_mature_growth.value_mature_growth`: `GrowthPath(..., policy.fade_years)`; `_charge(roic.runway, roic.terminal, roic.charge_off, policy)`; `_roic_charges(roic, moat, policy)` returns `{"runway": the row's own charge, "0.15": ..., "0.09": ..., "ten-year": None if roic.usable is None else _charge(roic.usable, terminal_roic(roic.usable, moat, policy), False, policy)}`; the spread flag over `list(by_roic.values())[:3]`; the flag from `floored_years(growth, charge)`; intermediates add `fade_years`, `growth_rates`, drop `runway_roic`; `growth_at_price` as in Interfaces, with `_roic_charges_at_price(im, policy)` rebuilding the four charges from `im["runway_return"]["value"]`, `im["terminal_roic"]`, `im["charge_off"]`, `im["roic"]["aggregate"]`, `im["moat"]`. `route_mature_stable.stable_at_price`: `expected(price, value, im, (g_T, g_T, g_T))`. Update `route.py`'s docstring list of intermediates and the sensitivity key names.

- [ ] **Step 4: Run** `uv run pytest -q && uv run mypy src`. Expected: PASS. (`tests/web` reads `impliedGrowth`, which keeps its key.)

- [ ] **Step 5: Commit**: `git commit -am "Charge the growth route at the runway return with the fade, the payout floor and the new sensitivity keys"`.

---

### Task 5: The Mature Stable cross-check and the growth-route column

**Files:**
- Modify: `src/fairband/engine/route_mature_growth.py` (factor the anchor-and-path step; add `growth_cross_check`), `src/fairband/engine/route_mature_stable.py`, `src/fairband/web/rows.py`, `src/fairband/web/static/design-system/components/bundle.js` (one column definition, `// fairband:` marked), `src/fairband/web/static/app.js` (one drawer line), `src/fairband/web/static/design-system/components/index.d.ts` (nothing: extra columns are not declared)
- Test: `tests/engine/test_route.py`, `tests/web/test_app.py`

**Interfaces:**
- Produces: `growth_cross_check(c: Context, moat: Moat, roic: RoicTerms) -> dict[str, Any]` in `route_mature_growth.py`: `{"value_per_share": x, "runway_return": {...}, "path_steps": [g2, g3], "belief": {...}, "implied_growth": x | None, "refusal": None}` or `{"refusal": "<reason>"}` where the reason is the one `value_mature_growth` would give (no trailing revenue, no statutory tax rate, the anchor's refusal, consensus earnings turning negative, value not positive). The stable route stores it as `im["growth_route"]`.
- `rows.py`: `EXTRA_KEYS` gains `"growthRouteValue"` after `"route"`; `screen_row` fills it with `snapshot.value` on a `mature-growth` row, with `im["growth_route"]["value_per_share"]` on a `mature-stable` row that has it, else `None`; `placeholder_row` leaves it `None`.
- `bundle.js`: `{ key: 'growthRouteValue', head: 'Growth-route value', num: true, cell: figureCell(money(r.growthRouteValue)) }` after `validUntil`.
- `app.js`: under the band meter, for a result with `intermediates.growth_route.value_per_share`, a `caption` line `Growth-route cross-check: $x (implied growth y%)`; `y%` is `—` when `implied_growth` is null.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_route.py`:

```python
def test_mature_stable_cross_check_present_with_a_path(ms_inputs, deciles, policy) -> None:
    r = value_company(ms_inputs, deciles, policy, TODAY)
    gr = r.intermediates["growth_route"]
    assert gr["refusal"] is None and gr["value_per_share"] > 0
    assert set(gr) == {"value_per_share", "runway_return", "path_steps", "belief", "implied_growth", "refusal"}
    assert r.value == r.intermediates["stable_growth"]  # the headline stays the stable value

def test_mature_stable_cross_check_absent_with_a_refusal(ms_inputs, deciles, policy) -> None:
    r = value_company(replace(ms_inputs, quarter_estimates=()), deciles, policy, TODAY)
    assert r.intermediates["growth_route"] == {"refusal": "incomplete NTM consensus"}

def test_mature_stable_reads_the_shared_terminal(ms_inputs, deciles, policy) -> None:
    # a Wide stable row whose marginal return is above 13% and ten-year aggregate 10% values at 13%
    r = value_company(<ms_inputs made Wide with capital years whose marginal return is 0.28 and ten-year aggregate 0.10>, deciles, policy, TODAY)
    assert r.intermediates["terminal_roic"] == 0.13
```

(If `ms_inputs` lacks a usable consensus, give it `mg_inputs`'s quarter and annual estimates in the first test.) `tests/web/test_app.py`: add `"growthRouteValue": "Growth-route value"` to `EXTRA_COLUMN_HEADS` and `"growthRouteValue"` to `EXTRA_COLUMNS`; add `test_growth_route_value_column` asserting AAPL's row has `growthRouteValue == row["mechanical"]` and AAL's is `None`. Add `MATURE_STABLE_KEYS |= {"growth_route"}`.

- [ ] **Step 2: Run** `uv run pytest tests/engine/test_route.py tests/web -q`. Expected: FAIL.

- [ ] **Step 3: Implement.** Factor `value_mature_growth`'s lines 55–70 into `_anchor_and_path(c) -> tuple[Anchor, Path, int, Belief] | Refused`; `growth_cross_check` calls it, then builds the path and charge exactly as the route does and returns the dict (its `implied_growth` from `implied_growth(c.price * c.shares, growth, charge, hi=_IMPLIED_HI)`). `value_mature_stable` adds `"growth_route": growth_cross_check(c, moat, roic)` to `im`. `_roic_flags`'s sentence: "Operating capital summed to zero or below over the last three ROIC years and the marginal return is not usable, so the stable-growth value uses the moat's terminal return." Then the rows, the column and the drawer line.

- [ ] **Step 4: Run** `uv run pytest -q && uv run mypy src`. Expected: PASS.

- [ ] **Step 5: Commit**: `git commit -am "Show the growth-route value as a cross-check on Mature Stable rows and as a column"`.

---

### Task 6: The revalue mode

**Files:**
- Modify: `src/fairband/refresh/run.py`, `src/fairband/__main__.py`, `src/fairband/web/app.py` (nothing beyond `KINDS`, which it imports)
- Test: `tests/refresh/test_run_revalue.py` (new), `tests/refresh/test_run.py` (the CLI usage checks)

**Interfaces:**
- Consumes: `latest_companies(conn)` (`fairband.store.companies`), `latest_deciles`, `build_inputs`, `value_company`, `insert_snapshot`, `upsert_item`.
- Produces: `Kind = Literal["full", "price", "scoped", "revalue"]`, `KINDS` in that order; `Refresh.run("revalue")` needs no FMP client (the `MissingKey` check moves to the kinds that fetch; `fmp` may be `None` for revalue); `Refresh._revalue(conn, refresh_id) -> _Finish`: symbols = the latest universe's eligible companies in symbol order; each listed `pending`; `_value_stage(conn, refresh_id, symbols)` (stage `value`, the latest stored deciles, today = the clock's date); `_done`; status `done` with `calibration(symbols, {}, snapshots)`; `cancelled` when the stage returns `None`. `calibration(admitted: Sequence[str], excluded: Mapping[str, int], snapshots)` replaces the `UniverseResult` parameter; the full path passes `universe.admitted, universe.excluded`.
- CLI: `fairband refresh --kind revalue` takes no symbols, needs no keys (`_refresh` skips `require(keys, "fmp")` and `build_clients` for it and passes `fmp=None, gf=None, secrets=()`), prints the calibration lines like a full refresh. `--kind revalue` with symbols is the usage error "a revalue takes no symbols".
- The web API accepts `{"kind": "revalue"}` through `KINDS` with no further change.

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_run_revalue.py`, on the `env_valued` fixture pattern of `test_run_price.py` (the fixture universe after its full refresh):

```python
def test_revalue_writes_new_snapshots_without_a_vendor_call(env_valued: Env) -> None:
    env = env_valued
    before = snapshots_of(env)
    env.router.refuse_all()  # or the router's equivalent: any call fails the test
    refresh_id = env.refresh().run("revalue")
    row = env.last()
    assert (row.id, row.kind, row.status, row.stage) == (refresh_id, "revalue", "done", "done")
    assert env.router.calls == []
    after = snapshots_of(env)
    for symbol in ADMITTED:
        assert after[symbol].refresh_id == refresh_id and after[symbol].id > before[symbol].id
        assert after[symbol].method_version == METHOD_VERSION
        assert after[symbol].policy_version == env.policy.version
    assert row.calibration is not None and row.calibration["total"] == len(ADMITTED)
    assert [p.stage for p in env.progress][0] == "value"

def test_revalue_refuses_a_company_without_facts(env_valued: Env) -> None:
    # add a company to the latest universe with no stored statements, then revalue
    ...
    assert env.snapshot("NOFACTS").value is None and env.snapshot("NOFACTS").refusal

def test_revalue_without_an_fmp_client(env_valued: Env) -> None:
    refresh = Refresh(env.connect, None, None, env.policy, env.tax, env.clock, threading.Event(), env.progress.append, ())
    assert refresh.run("revalue") > 1

def test_revalue_takes_no_symbols(env_valued: Env) -> None:
    with pytest.raises(ValueError, match="takes no symbols"):
        env_valued.refresh().run("revalue", ["ACME"])

def test_cli_revalue_prints_calibration(env_valued, capsys, monkeypatch) -> None:
    # as test_cli_full_refresh_prints_calibration, with ["refresh", "--kind", "revalue"] and no keys file
    ...
```

In `tests/refresh/test_run.py`'s CLI usage parametrisation add `(["refresh", "AAPL", "--kind", "revalue"], "a revalue takes no symbols")`.

- [ ] **Step 2: Run** `uv run pytest tests/refresh/test_run_revalue.py -q`. Expected: FAIL.

- [ ] **Step 3: Implement** as in Interfaces. In `run()`: `if kind != "revalue" and fmp is None: raise MissingKey("fmp")`; dispatch `kind == "revalue"` to `_revalue`. Add the kind to the module docstring. In `__main__._refresh`: the usage check, the keys skip, the calibration lines for `revalue` as for `full`; `_build_parser`'s `--kind` help gains "revalue: value every company again from the stored facts, with no vendor call".

- [ ] **Step 4: Run** `uv run pytest -q && uv run mypy src`. Expected: PASS.

- [ ] **Step 5: Commit**: `git commit -am "Add the revalue refresh kind that runs the engine on the stored facts with no vendor call"`.

---

### Task 7: Revalue the first run's database and check the acceptance figures

**Files:**
- None in the repository. Writes to `~/.local/share/fairband/fairband.db` (a new refresh and 1,759 snapshots); a backup beside it.
- Scratch: a read-only script in the session's scratchpad directory.

**Interfaces:**
- Consumes: Task 6's `fairband refresh --kind revalue`; the snapshots of refresh 1 (policy v1, method 0.1) and of the new refresh (v2, 0.2).

- [ ] **Step 1: Back up the database** (1.2 GB; 859 GB free): `cp ~/.local/share/fairband/fairband.db ~/.local/share/fairband/fairband-before-v2-2026-11-01.db`. Confirm the copy's size equals the original's.

- [ ] **Step 2: Run the revalue**: `uv run python -m fairband refresh --kind revalue`. Expected: exit 0, `refresh 2: done`, the calibration lines; no vendor call (no keys are needed; the run makes none).

- [ ] **Step 3: Compute the acceptance table** with a script that opens the database read-only (`file:...?mode=ro`), reads the latest snapshot of each symbol from refresh 1 and from refresh 2, and prints: the values of CRM, AMZN, MSFT, GOOG, META, NVDA, TSLA before and after; over the 619 Mature Growth rows valued in refresh 1 without `charge_off`, the median of value ÷ price (the stored 2026-10-30 prices) and the share with value ≥ price, before and after. Expected within tolerance: CRM 244.96, AMZN 250.49, MSFT 515.58, GOOG 399.55, META 749.28, NVDA 457.66, TSLA 56.19 (1%); median 0.826 (±0.02); share 33.3% (±2 points). Also print QCOM's `growth_route` cross-check value.

- [ ] **Step 4: Report** the table to the founder with the refresh id. A company value more than 1% off is a defect: stop and use `superpowers:systematic-debugging` before anything else. Nothing is committed in this task.

---

## Self-review notes

- Spec coverage: 5.1 → Task 2; 5.2 → Tasks 3, 4 (flag); 5.3 → Task 2 (both routes through `RoicTerms`); 5.4 → Task 3; 5.4a → Task 4; 5.5 → Task 3 (`implied_growth` re-fades per trial through `replace(path, belief=g)`) and Task 4's round-trip test; 5.6 → Task 4; 5.7 → Task 5; 5.8 → Task 1; 5.9 → Task 6; 6 → Task 1; 7 → Tasks 2, 3, 4; 8 → every bullet has a test above (determinism: the existing `test_mature_growth_is_deterministic` stays); 9 → Task 7; 11 → the task order.
- Spec 8's "v1 still loads and records under its own hash" is met by keeping the v1 file byte-identical (Task 1 pins its sha256, the hash the stored `policy_versions` row and the 1,759 snapshots cite); `load_policy` on the v1 path raises on the missing v2 values, and nothing calls it. The founder sees this ruling in the handoff.
- Names used across tasks: `RunwayReturn`, `runway_return`, `terminal_return`, `window_aggregate` (Task 2) in Tasks 4 and 5; `GrowthPath.fade_years`, `floored_years`, `growth_rates` (Task 3) in Task 4; `expected_return(..., rates)` (Task 4) in the stable route; `growth_cross_check` (Task 5); `calibration(admitted, excluded, snapshots)` (Task 6).
- The "ten-year" sensitivity key is `None` when the ten-year aggregate is unavailable or not positive (a non-positive runway return would divide by zero in the charge); the spec says `null` when unavailable, and a non-positive aggregate is unavailable as a return.
- Review Focus: each line names its test and task.
