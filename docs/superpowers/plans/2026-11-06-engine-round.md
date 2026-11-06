# The engine round: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Method `fairband-mechanical/0.9` on policy v7: the Decline run-off fades to zero with the consensus read past year 3, the growth routes bound the own sales-to-capital and ramp a loss larger than revenue in dollars, the classifier reads five profitable years on file and never makes an established company a Start-up, the margin-direction check reads deciles 9 and 2 with Stable pointing nowhere, a Mature Stable refusal keeps the growth cross-check, and the tax table covers every jurisdiction in the OECD series.

**Architecture:** Each change lands in the module that owns the rule: `runoff.py` and `route_decline.py` for the fade and the consensus; `revenue_growth.py` and `route_revenue_growth.py` for the bound and the ramp; `classifier.py` for the established test, the Start-up rule and the direction; `route_mature_stable.py` and `route.py` for the refusal's cross-check; `policy/tax.py` with a generated `tax-rates-oecd-v2.toml`. Policy v7 adds two constants. The drawer and the Methodology page change last, then one revalue and its readout. Every engine task updates `docs/method.md` in the same commit.

**Tech Stack:** Python 3.13, uv, SQLite; plain JS for the drawer; `pycountry` as a dev dependency for the tax script only.

**Spec:** `docs/superpowers/specs/2026-11-06-engine-round-design.md` (sections 6 to 15). The method as built is `docs/method.md`; the spec cites its sections.

## Global Constraints

- The constraints of every earlier plan: never print, log or commit a key; never commit vendor data; `docs/method.md` and the Methodology page change in the same commit as the engine; the same inputs give the same result bit for bit; every valuation constant lives in the policy file with a source line; one imperative sentence per commit with the `Co-Authored-By` line; `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q` before every commit.
- This plan ends at `fairband-mechanical/0.9` and `fairband-policy-v7`; v6 stays in the package byte-identical under its hash; `tax-rates-oecd-v1.toml` stays for provenance.
- The two new policy values are not settings: `own_sales_to_capital_min_share` 0.5 and `loss_ramp_margin_bound` −1.0 (spec 11). The structural constants in code change: the direction deciles 9 and 2, the established company's five profitable years on file (spec 8, 11).
- A refusal is a result with no value and a reason, never an exception.
- At the defaults, every row the changes do not touch, directly or through its mature peers, keeps every figure bit for bit (spec 2, 15).
- Tolerances: 1e-9 a share unless the spec names one (spec 13).

## Review Focus

1. A Decline row whose consensus reaches year 10 (K = N): no fade year exists, year 10 grows at the consensus's own rate, and the terminal is still flat on year 10's revenue (Task 5's `test_a_consensus_to_year_ten_leaves_no_fade`).
2. A Decline row whose base + 2 step was held (no consensus for base + 2): the chain past year 3 has no earlier value to step from, so K is 3 even when base + 3 has a consensus on many analysts (Task 5's `test_a_held_year_3_ends_the_consensus_at_year_3`).
3. A growth row on the dollar ramp with a convergence year before the explicit period (C = 5): years 6 to 10 earn the target margin on each year's revenue, not year 5's dollars (Task 4's `test_the_ramp_holds_the_target_margin_after_the_convergence_year`).
4. An established company with zero revenue three years back whose last three revenues fell three steps on a falling trend: rule 2 takes it (Decline), and `revenue-gap` is still raised (Task 2's `test_an_established_company_past_the_start_up_rule_can_be_decline`).
5. A Mature Stable refusal whose cross-check is itself a refusal (no positive anchor): the row carries `growth_route.refusal` only and a reprice leaves it as it is (Task 3's `test_a_refused_cross_check_on_a_refused_row_survives_a_reprice`).

---

### Task 1: Policy v7 and method 0.9

**Files:**
- Create: `src/fairband/policy/fairband-policy-v7.toml` (a copy of v6 with the two values and a header line for v7)
- Modify: `src/fairband/policy/__init__.py:28` (`_POLICY_FILE`), `:80-130` (`Policy` fields), `:145-230` (`load_policy` reads), the docstring's v6 mentions
- Modify: `src/fairband/engine/__init__.py` (`METHOD_VERSION = "fairband-mechanical/0.9"`)
- Modify: `docs/method.md` sections 4.1 (the two rows, Setting "no"), 4.1a (the deciles 9 and 2; the five profitable years on file), 11 (the 0.9 row), the header table's versions
- Modify: `tests/fixtures/golden/README.md` (the baseline sentence: captured from 0.7 and v5, still the baseline at the start of 0.9)
- Test: `tests/policy/test_policy.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `Policy.own_sales_to_capital_min_share: float` (0.5), `Policy.loss_ramp_margin_bound: float` (−1.0); `policy.version == "fairband-policy-v7"`; `METHOD_VERSION == "fairband-mechanical/0.9"`.

- [ ] **Step 1: Write the failing tests**

In `tests/policy/test_policy.py`: `test_v7_is_the_packaged_policy` (version `fairband-policy-v7`, `own_sales_to_capital_min_share == 0.5`, `loss_ramp_margin_bound == -1.0`, each with a non-empty source); `test_v6_is_byte_identical_under_its_hash` on the pattern of the v5 test at line 190 (the v6 file's sha256 is the one `fairband-policy-v6` snapshots cite: read it from the file once and pin it); `test_v7_is_v6_with_the_two_values_added` (every v6 value loads unchanged from v7). Rename the golden test to `test_defaults_match_the_golden` and keep its assertion; `golden_dict` already strips the versions.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/policy/test_policy.py tests/engine/test_golden.py -q`
Expected: FAIL on the v7 tests; the golden test passes.

- [ ] **Step 3: Implement**

The v7 file: v6's text with `version = "fairband-policy-v7"`, a header line "v7: v6 with the growth routes' own sales-to-capital bound and the loss ramp bound (spec 2026-11-06 section 11)", and two tables, `[values.own_sales_to_capital_min_share]` (value 0.5) and `[values.loss_ramp_margin_bound]` (value −1.0), each with spec 11's source line. The loader: two `read(..., _num)` calls and two `Policy` fields. `METHOD_VERSION` to 0.9.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS (the goldens still match: `golden_dict` drops the versions).

- [ ] **Step 5: Update `docs/method.md`**

The header table's two version rows; 4.1's two rows with Setting "no" and spec 11's sources; 4.1a's deciles 9 and 2 and the five profitable years on file; section 11's 0.9 row listing the five changes and the refusal's cross-check, "At the defaults every row the changes do not touch keeps its figures".

- [ ] **Step 6: Commit**

```bash
git add src/fairband/policy src/fairband/engine/__init__.py docs/method.md tests
git commit -m "Add policy v7 with the own sales-to-capital bound and the loss ramp bound, and record method 0.9"
```

### Task 2: The classifier: the established test, the Start-up rule and the margin direction

**Files:**
- Modify: `src/fairband/engine/classifier.py:1-60` (docstring, constants), `:134-145` (`established`), `:216-300` (`classify`: rule 1, the evidence), `:345-420` (`_checks`: the loss-year sentence, the revenue-gap flag, the direction check), `:499-508` (`_margin_direction`)
- Modify: `src/fairband/engine/types.py:78-95` (`PhaseEvidence`: a second count)
- Modify: `tests/support/engine_companies.py:118-127` (`universe_deciles`: the margin-slope edges)
- Modify: `docs/method.md` sections 3.4, 3.5, 3.6, 8 (the `revenue-gap` row; the direction row), 9
- Test: `tests/engine/test_classifier.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `ESTABLISHED_YEARS_ON_FILE = 5` beside `ESTABLISHED_YEARS = 3`; `established(series: Series) -> tuple[bool, int, int]` (established, positive years of the last five, positive years on file); `PhaseEvidence.positive_years_on_file: int | None`; `_DIRECTION_PHASE` without "Stable"; the flag `revenue-gap` (word "Revenue gap"); the `loss-year` sentence naming both counts.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests**

In `tests/engine/test_classifier.py`, with the module's `series(revenue, income, ...)` builder (the margins are income ÷ revenue):

```python
def test_five_profitable_years_on_file_make_an_established_company(deciles):  # spec 13.4
    # eleven years: margins +,+,+,+,+,+,-,-,-,-,- → 6 on file, 0 of the last 5
    assert e.phase in ("Mature Growth", "Mature Stable")
    assert "loss-year" in codes(e)
    assert "0 of the last five fiscal years and in 6 of the 11 on file" in sentence(e, "loss-year")

def test_four_profitable_years_on_file_are_not_established(deciles):
    # +,+,+,+,-,-,-,-,-,-,- → rule 4b: Young Growth (or High Growth by the slope)

def test_an_established_company_is_never_a_start_up(deciles):
    # revenue 0, 100, 120, 150 with margins none, +, +, + → not "Start-up"; "revenue-gap" raised; "short-history" raised

def test_a_non_established_company_with_zero_revenue_now_is_a_start_up(deciles):
    # revenue 100, 80, 50, 0 with margins -,-,-,none → "Start-up" (a reported zero), no "revenue-gap"

def test_an_established_company_with_zero_revenue_now_is_unclassified(deciles):
    # revenue 100, 110, 120, 130, 0 with margins +,+,+,+,none → phase None, reason "no measurable revenue growth", no "revenue-gap"

def test_an_established_company_past_the_start_up_rule_can_be_decline(deciles):
    # revenue 0, 200, 150, 120, 100 with margins none, +, +, +, + (word "Close to zero or negative", three falls) → "Decline", "revenue-gap" raised

def test_margin_direction_reads_deciles_nine_and_two(deciles):
    # slopes at decile 9 and above zero → "Rising"; decile 8 → "Stable"; decile 2 below zero → "Declining"; decile 3 → "Stable"

def test_stable_points_nowhere(deciles):
    # a Mature Growth company with a Stable direction carries no "margin-direction-disagrees"; a Rising one on Mature Stable does
```

Update `test_margin_direction_and_its_check` and `test_margin_direction_needs_the_slope_sign` to the new deciles, and `test_exactly_three_positive_years_is_established` to the three-value return. In `universe_deciles`, set `margin_slope_edges=(-0.03, -0.012, -0.01, -0.005, 0.0, 0.005, 0.01, 0.012, 0.03)` so a slope of 1.5 points a year is decile 9 (Rising), −1.5 points decile 2 (Declining) and a flat margin decile 6 (Stable); update its docstring.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_classifier.py tests/engine/test_golden.py -q`
Expected: FAIL on the new tests; the goldens pass once the edges move (MGCO stays Rising) and fail before.

- [ ] **Step 3: Implement**

`established` counts the positive margins over the whole series as well; the company is established when either count reaches its constant. `classify`: `if is_startup(series) and not is_established:` for rule 1; the evidence carries both counts. `_checks`: the `loss-year` sentence "The operating margin is negative in fiscal {year} after a positive margin in {n5} of the last five fiscal years and in {nf} of the {years_used} on file; the phase follows the growth word."; a `revenue-gap` flag when `is_startup(series) and is_established and phase is not None`: "Revenue was zero in fiscal {year} (or three years ago), but the margin was above zero in {n5} of the last 5 fiscal years and in {nf} of the {years_used} on file, so the company is not a Start-up."; the direction check skips "Stable". `_margin_direction`: `d >= 9` and `d <= 2`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS, the six goldens unchanged.

- [ ] **Step 5: Update `docs/method.md`**

3.4: the deciles 9 and 2 for Rising and Declining. 3.5: rule 1 "that is not established"; the established definition with the second count. 3.6: the direction row (Rising → Mature Growth, Declining → Decline; Stable points nowhere), the loss-year sentence, a `revenue-gap` row. 8: the `revenue-gap` note.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine tests docs/method.md
git commit -m "Count five profitable years on file as established, keep an established company out of Start-up with a revenue-gap note, and read the margin direction at deciles 9 and 2 with Stable pointing nowhere"
```

### Task 3: The Mature Stable refusal keeps the growth cross-check

**Files:**
- Modify: `src/fairband/engine/route_mature_stable.py:48-55` (the refusal), docstring
- Modify: `src/fairband/engine/route.py:291-335` (`reprice`: a refusal whose intermediates hold `growth_route` and `e_trailing`)
- Modify: `docs/method.md` sections 6.1, 6.4, 10
- Test: `tests/engine/test_route.py` (where the stable route's refusal is tested today; else `tests/engine/test_route_mature_stable.py`, new)

**Interfaces:**
- Produces: on "no positive trailing earnings", `Refused(reason, (), im, ())` with `im` = `e_trailing`, `nri_gap`, `eps`, `shares`, `moat`, `growth_route` (as `growth_cross_check` gives it), `price_facts`, and at the price `growth_route` through `cross_check_at_price`; `reprice` moves that cross-check on the refusal.
- Consumes: `growth_cross_check(c, moat, roic)` and `cross_check_at_price(g, price, shares, policy)` as today.

- [ ] **Step 1: Write the failing tests**

With `support.engine_companies.mature_stable_inputs()` and `replace`d trailing figures (`net_income` negative) and the fixture's positive anchor:

```python
def test_no_positive_trailing_earnings_keeps_the_cross_check(...):  # spec 13.5
    r = value_company(inputs, deciles, policy, TODAY)
    assert r.value is None and r.refusal == "no positive trailing earnings"
    assert r.intermediates["growth_route"]["value_per_share"] > 0
    assert r.intermediates["growth_route"]["implied_growth"] is not None

def test_the_cross_check_moves_with_the_price_on_the_refusal(...):
    moved = reprice(r, 2 * r.price, REPRICED, policy)
    assert moved.intermediates["growth_route"]["implied_growth"] != r.intermediates["growth_route"]["implied_growth"]
    assert moved.value is None and moved.refusal == r.refusal

def test_a_refused_cross_check_on_a_refused_row_survives_a_reprice(...):
    # the anchor refused too (no quarterly estimates): growth_route == {"refusal": "..."} and reprice leaves it
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_route.py -q -k cross_check`
Expected: FAIL (`intermediates` empty on the refusal).

- [ ] **Step 3: Implement**

Build `moat` and `roic` before the earnings test; return the refusal with the intermediates above and `growth_route` at the price. In `reprice`, after the `revenue_path` branch: `if "growth_route" in im and "e_trailing" in im: return replace(moved, intermediates=im | {"growth_route": cross_check_at_price(im["growth_route"], price, im["shares"], policy)})`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md`**

6.1: the refusal keeps the cross-check and the named intermediates; 6.4: "on a valued row and on the refusal of 6.1"; section 10: the price refresh moves the cross-check's implied growth on that refusal.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine tests docs/method.md
git commit -m "Keep the growth-route cross-check on a Mature Stable row refused for its trailing earnings and move it with the price"
```

### Task 4: The growth routes: the sales-to-capital bound and the dollar ramp

**Files:**
- Modify: `src/fairband/engine/revenue_growth.py:83-90` (`MarginPath`), `:122-128` (`margins_by_year`), `:206-237` (`revenue_valuation`), docstring
- Modify: `src/fairband/engine/route_revenue_growth.py:160-170` (`_SalesToCapital`), `:173-316` (`value_revenue_growth`: the ramp, `margin_path.ramp`, the flag, the two RULE inputs), `:318-361` (`revenue_at_price`, `implied_margin_at_price`: the ramp rebuilt), `:454-472` (`_sales_to_capital`: the bound), `:638-648` (`_sales_to_capital_input`: the note), `:473-492` (`_at_margin`), docstring
- Modify: `docs/method.md` sections 5a.4, 5a.5, 5a.10, 5a.13, 5a.14, 8
- Test: `tests/engine/test_revenue_growth.py`, `tests/engine/test_route_revenue_growth.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `MarginPath(start, target, convergence_year, in_dollars: bool = False)`; `ebit_by_year(revenue: Sequence[float], margin: MarginPath, revenue0: float) -> tuple[float, ...]` (the margin path's EBITs, or the ramp: E_0 = start × revenue0, E* = target × revenue[min(C, N) − 1], E_t = E_0 + (E* − E_0) × t ÷ C for t ≤ C, target × revenue_t after); `RevenueValuation.margins` = EBIT ÷ revenue on either path; `_SalesToCapital.own_below_bound: bool` (the record gains the key; additive, *my call*); the flag `margin-ramp-in-dollars`; `margin_path["ramp"]` "margin" or "dollars"; the RULE inputs `own_sales_to_capital_min_share` and `loss_ramp_margin_bound` where spec 7.3 says.
- Consumes: `Policy.own_sales_to_capital_min_share`, `Policy.loss_ramp_margin_bound` (Task 1).

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_revenue_growth.py`, on the module's `PATH` and `MARGIN` constants (spec 13.2):

```python
def test_the_dollar_ramp_from_a_loss_larger_than_revenue():
    ramp = MarginPath(-1.5, 0.20, 10, in_dollars=True)
    ebit = ebit_by_year(revenue_by_year(PATH), ramp, 1000.0)
    assert ebit[0] == pytest.approx(-1260.80, abs=0.01) and ebit[6] == pytest.approx(174.38, abs=0.01) and ebit[9] == pytest.approx(891.98, abs=0.01)
    v = revenue_valuation(PATH, ramp, 0.21, CHARGE, BRIDGE)
    assert v.margins[0] == pytest.approx(-0.9698, abs=1e-4) and v.margins[9] == pytest.approx(0.20)
    assert v.nopat[9] == pytest.approx(891.98, abs=0.01) and v.terminal_nopat == pytest.approx(704.66, abs=0.01)
    assert v.fcff[0] == pytest.approx(-1423.30, abs=0.01) and v.terminal_value == pytest.approx(8064.46, abs=0.01)
    assert v.firm_value == pytest.approx(-31.33, abs=0.01) and v.value_per_share == pytest.approx(1.6867, abs=1e-4)

def test_the_margin_path_from_the_same_loss_gives_minus_61_94(): ...  # MarginPath(-1.5, 0.20, 10) → −61.94

def test_the_ramp_holds_the_target_margin_after_the_convergence_year():
    # MarginPath(-1.5, 0.20, 5, in_dollars=True): margins[5:] == 0.20 each; margins[4] == 0.20

def test_the_ramp_past_the_explicit_period_ends_at_year_ten_revenue():
    # convergence_year 12: E* = 0.20 × revenue[9]; margins[9] < 0.20

def test_the_margin_the_price_needs_on_the_ramp(policy):
    # implied_target_margin(25.0, PATH, MarginPath(-1.5, -1.5, 10, in_dollars=True), 0.21, 2.0, "None", policy, BRIDGE) ≈ 0.277164 within 1e-5
```

`tests/engine/test_route_revenue_growth.py`, on `high_growth_inputs()`:

```python
def test_a_trailing_margin_below_the_bound_takes_the_dollar_ramp(...):
    # operating_income −15 bn on 10 bn revenue → margin_path.ramp == "dollars", "margin-ramp-in-dollars" in codes after "tax-loss-history-unknown", the RULE input loss_ramp_margin_bound present, value_per_share > the margin path's (compute both through value_company by replacing the trailing figure)
def test_a_trailing_margin_at_the_bound_keeps_the_margin_path(...):  # −100% exactly → ramp "margin"
def test_the_own_sales_to_capital_must_reach_half_the_peers_median(...):  # spec 13.3: own 0.5 with peers 2.5 → used "peers", own_usable False, own_below_bound True, the note names 0.5 and 2.5, the RULE input own_sales_to_capital_min_share present; own 1.3 → "own"; own 0.5 with no peers' median → "own"
def test_reprice_rebuilds_the_ramp(...):  # a ramp row repriced: implied_margin and implied_growth move; the refusal "no target margin" on a ramp row reprices its implied margin
def test_young_growth_equals_high_growth_on_the_ramp(...)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_revenue_growth.py tests/engine/test_route_revenue_growth.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`ebit_by_year` as the interface says; `revenue_valuation` calls it and sets `margins` from the EBITs. The route: `in_dollars = start < policy.loss_ramp_margin_bound` wherever a `MarginPath` is built (`_at_margin`, `revenue_at_price`, `implied_margin_at_price`); `margin_path["ramp"]`; the flag after `TAX_LOSS` in the flag order, its sentence spec 7.2's with the two figures in millions and the margin as a percent; the RULE input when on the ramp. `_sales_to_capital`: after `own_sales_to_capital`, `usable = usable and (peers is None or own >= policy.own_sales_to_capital_min_share * peers)`, `own_below_bound` true when the bound alone rejected it; the input note "the mature peers' median; the own measure, {own:.2f}, is below half the peers' median, {peers:.2f}" on that case, today's note otherwise; the RULE input when rejected.

- [ ] **Step 4: Run the suite, then the goldens**

Run: `uv run pytest -q`
Expected: PASS. If HGCO or YGCO moved (their own measure under the bound, or a margin below −100%: neither should, the fixtures' margins are −9% and their own measure is the fixture's), stop and check the fixture before re-capturing; the goldens are expected unchanged in this task.

- [ ] **Step 5: Update `docs/method.md`**

5a.4: the ramp paragraph with the formula and the bound; 5a.5 step 1: the third condition; 5a.10: the solves rebuild the ramp; 5a.13: the flag in order; 5a.14: `margin_path.ramp`, `sales_to_capital.own_below_bound`, the two RULE inputs and the note; 8: `margin-ramp-in-dollars` as a note.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine tests docs/method.md
git commit -m "Use the mature peers' sales-to-capital when the own measure is below half their median, and move a loss larger than revenue in dollars to the target margin, as the Start-up ramp does"
```

### Task 5: The Decline route: the fade and the consensus past year 3

**Files:**
- Modify: `src/fairband/engine/runoff.py:1-60` (docstring, `runoff_rates`), `:89-131` (`runoff_valuation`: the flat terminal)
- Modify: `src/fairband/engine/route_decline.py:1-60` (docstring), `:166-177` (`_Consensus`), `:179-325` (`value_decline`: `runoff_path`, the inputs), `:327-345` (`decline_at_price`: the expected return), `:359-391` (`_consensus`, `_rates`), `:510-535` (`_on_trend`, `_recovery`), `:625-640` (`_path_inputs`)
- Modify: `src/fairband/engine/route_revenue_growth.py` (a reader for the years past base + 2, beside `revenue_path_for` at 372)
- Modify: `docs/method.md` sections 6a.2, 6a.5, 6a.9, 6a.10, 8 (`path-on-trend`, `consensus-recovery`, `few-analysts` rows), 13 (the glossary's Run-off and Decline rate rows)
- Modify: `tests/fixtures/golden/DCCO.json`, `tests/fixtures/golden/README.md`
- Test: `tests/engine/test_runoff.py`, `tests/engine/test_route_decline.py`, `tests/engine/test_route_revenue_growth.py` (the reader), `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `consensus_beyond(annual: Sequence[AnnualEstimate], base_year: int, policy: Policy) -> tuple[float, ...]` in `route_revenue_growth.py`: the steps for base + 3 onward, each from the year before's consensus value, while the year has a `consensus_value` above zero and `analysts_revenue >= policy.analyst_min`; empty when base + 2 has no consensus value; `runoff_rates(g1: float | None, g2: float | None, g3: float | None, beyond: Sequence[float], d: float, years: int) -> tuple[float, ...]` (years 1 to 3 as today, then `beyond`, then the fade `d × (N − t) ÷ (N − K)`; `ValueError` when `len(beyond) > years − 3`); `runoff_valuation(revenue0, rates, margin, tax_rate, sales_to_capital, recovery, r)` with the flat terminal (`revenue_n1 = revenue[-1]`, `fcff_n1 = nopat_n1`, `terminal = fcff_n1 / r`); `runoff_path` gains `consensus_years` (K) and its `steps` hold years 2 to K; the DATA inputs `path_step_4` to `path_step_K`; the sentences of spec 6.1.
- Consumes: `consensus_value`, `growth_step`, `base_fiscal_year` from `anchor.py`; `revenue_path_for` for years 1 to 3.

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_runoff.py` (the module's figures are spec 13.1's; update its constants):

```python
def test_rates_fade_from_d_to_zero_after_the_consensus():
    assert runoff_rates(-0.03, -0.03, -0.03, (), -0.04, 10) == pytest.approx((-0.03, -0.03, -0.03, -0.034285714, -0.028571429, -0.022857143, -0.017142857, -0.011428571, -0.005714286, 0.0))
    assert runoff_rates(-0.03, -0.03, -0.03, (0.01, 0.02), -0.04, 10)[3:] == pytest.approx((0.01, 0.02, -0.032, -0.024, -0.016, -0.008, 0.0))
def test_no_consensus_takes_d_then_the_fade(): ...  # (−0.04,)*3 then the fade
def test_a_consensus_to_year_ten_leaves_no_fade(): ...  # beyond of 7 rates: years 4 to 10 are the consensus's; 8 rates raise ValueError
def test_the_worked_decline_row():  # spec 13.1: revenue 970.00 and 808.24, fcff 67.20 and 48.49, fcff_n1 48.49, terminal 538.83, firm 607.48, value 4.9533 (1e-4 a share on the spec's rounding, the core's own figure pinned to 1e-9 once computed)
def test_the_terminal_is_flat(): ...  # revenue_n1 == revenue[-1]; no release in fcff_n1
def test_the_implied_decline_rate_recovers_d(): ...  # at 4.9533 → −0.04 within 1e-4; at 3.00 → None; value at 0 → 5.2247, at −0.5 → 3.1251
```

`tests/engine/test_route_decline.py`, on `decline_inputs()`: update `VALUE`, `GOING_CONCERN`, `DISTRESS`, `FIRM`, `RUNOFF_REVENUE`, `FCFF` to spec 13.1; add

```python
def test_the_consensus_is_read_past_year_three_on_enough_analysts(...):  # base + 3 at +1% on 6, base + 4 at +2% on 6, base + 5 absent → consensus_years 5, value 5.0974, "consensus-recovery" names years 4 and 5, inputs path_step_4 and path_step_5, no "few-analysts" for year 4
def test_a_thin_year_past_three_ends_the_consensus(...):  # base + 3 on 4 analysts → consensus_years 3, value 4.9533, no "few-analysts"
def test_a_held_year_3_ends_the_consensus_at_year_3(...):  # base + 2 missing, base + 3 present on 6 → consensus_years 3, "path-held"
def test_a_consensus_to_year_ten_leaves_no_fade(...):  # seven years past base + 2 on 6 analysts
def test_a_far_year_at_minus_100_refuses(...):  # base + 3 at 0 with analysts → "consensus revenue falls to zero or below within the path"
def test_no_consensus_takes_the_trend_then_the_fade(...):  # value 4.8626, the new "path-on-trend" sentence
def test_the_expected_return_grows_at_the_path_then_zero(...):  # growth term from growth_rates[1:4]
def test_reprice_rebuilds_the_same_path(...)  # growth_rates and value unchanged; implied_decline_rate moves
```

Re-pin `test_the_distress_variants`, `test_the_floor_has_no_weight_at_a_pi_of_one`, `test_a_chronic_loss_is_refused_with_its_figures`, `test_a_steep_trend_is_floored_at_minus_half` and the rest on the new path (compute each with the core once; the rules are unchanged).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_runoff.py tests/engine/test_route_decline.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`consensus_beyond` as the interface says. `_Consensus` gains `beyond`; `_consensus` reads it only on a usable path (`()` on trend); `runoff_path["steps"] = [s2, s3, *beyond]`, `["consensus_years"] = 3 + len(beyond)`; `_rates` passes `p["steps"][2:]`; `_recovery` reads years 1 to K; `_on_trend(d, n)`'s sentence "No usable consensus: years 1 to 3 shrink at the decline rate, {d}, which fades to zero by year {n}."; `decline_at_price` calls `expected(price, value, im, im["growth_rates"][1:], policy.repricing_horizon_years, 0.0)`; `_path_inputs` adds one `step_input` per year past 3; `_valuation` drops `d` for the terminal. The refusal for a far-year step at or below −100% uses the existing reason.

- [ ] **Step 4: Run the suite and re-capture DCCO**

Run: `uv run pytest -q`
Expected: every test but `test_defaults_match_the_golden[DCCO]` passes. Re-capture DCCO with the README's command restricted to DCCO, then run again: PASS. Add to the README: "DCCO re-captured under 0.9 on <date>: the fade and the flat terminal (spec 2026-11-06 section 6)."

- [ ] **Step 5: Update `docs/method.md`**

6a.2: the consensus past year 3, K, the fade formula, `path-on-trend`'s path; 6a.5: the flat terminal; 6a.9: the implied decline rate on the fade, the expected return's rates; 6a.10: `runoff_path.consensus_years`, the steps, the inputs; 8: the three rows; the glossary's two rows; the 6a intro sentence.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine tests docs/method.md
git commit -m "Fade the Decline route's rate to zero by year 10 with a flat terminal and read the revenue consensus past year 3 where five analysts give it"
```

### Task 6: The tax table for every jurisdiction

**Files:**
- Create: `scripts/build_tax_table.py`, `src/fairband/policy/tax-rates-oecd-v2.toml`
- Modify: `pyproject.toml` (`pycountry` in the dev group; `uv lock`), `src/fairband/policy/tax.py:19` (`_TAX_FILE`), its docstring
- Modify: `docs/method.md` sections 2 (the tax row), 4.3 (the table's name and coverage)
- Test: `tests/policy/test_tax.py`

**Interfaces:**
- Produces: `tax-rates-oecd-v2.toml` with `[meta]` (source, url, retrieved), `[country_aliases]` for every jurisdiction (alpha-2 → the OECD name), `[[rates]]` rows for every jurisdiction and year the series gives with `CIT_C`, `S13`, `ST`, plus Taiwan (17% 2014 to 2017, 20% from 2018) and Cyprus (12.5% 2014 to 2025) with a `source` line each in the script's `HAND_ROWS`; `uv run python scripts/build_tax_table.py <csv> <toml>` regenerates it.
- Consumes: the OECD CSV export of spec 5 (the SDMX URL in v1's `[meta]`, requested with `Accept: application/vnd.sdmx.data+csv;version=1.0.0`), not committed.

- [ ] **Step 1: Write the failing tests**

In `tests/policy/test_tax.py` (spec 13.6): `test_v2_keeps_every_v1_rate` (every (country, year, rate) of v1 is in v2); `test_the_new_countries` parametrized over GR 2024 0.22, SE 0.206, IT 0.2781, IN 0.2517, HK 0.165, BE 0.20, BS 0.0, GG 0.0, AE 0.09, CN 0.25, TW 2018 0.20, TW 2017 0.17, CY 0.125, each through `rate_for(code, year)`; `test_every_jurisdiction_has_an_alias_and_a_rate_from_2024` (every country in the table has a code and a 2024 rate); keep `test_each_jurisdiction_covered_from_2014` for v1's sixteen on v2; the US 2025 rate 0.25569714.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/policy/test_tax.py -q`
Expected: FAIL (v2 absent).

- [ ] **Step 3: Implement**

`uv add --group dev pycountry`. The script: read the CSV with `csv.DictReader` (columns are labelled, `REF_AREA: Reference area` with values `GRC: Greece`), keep rows whose measure starts with `CIT_C`, sector with `S13:` and targeting with `ST:`, map alpha-3 to alpha-2 with `pycountry.countries.get(alpha_3=...)`, take the name from the CSV label, rates as `OBS_VALUE / 100` rounded to 6 decimals as v1's are, append `HAND_ROWS`, write the TOML with v1's layout and header comments naming the dataflow and the retrieval date. Fetch the CSV to the scratchpad (never the repo), run the script, point `_TAX_FILE` at v2.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q && uv run ruff check scripts`
Expected: PASS; the goldens unchanged (the fixtures are US).

- [ ] **Step 5: Update `docs/method.md`**

Section 2's tax row names v2 and "146 jurisdictions, plus Taiwan and Cyprus by hand"; 4.3 names the file and that v1 stays for the snapshots that cite it.

- [ ] **Step 6: Commit**

```bash
git add scripts src/fairband/policy pyproject.toml uv.lock tests docs/method.md
git commit -m "Regenerate the tax table from the OECD series for every jurisdiction, with Taiwan and Cyprus by hand"
```

### Task 7: The drawer and the Methodology page

**Files:**
- Modify: `src/fairband/web/static/app.js:617-640` (the refusal section: the cross-check), `:851` (the growth route's margin row), `:955-975` (`runoffSummary`: the path sentence)
- Modify: `src/fairband/web/static/methodology.html:176-212` (the classifier: deciles, the rules, the notes), `:477-596` (the growth section: the two rules), `:597-640` (the Decline run-off list), `:731-880` (the flags list: two notes)
- Test: `tests/web/test_methodology.py`, `tests/web/test_app.py` (the page-script pins)

**Interfaces:**
- Consumes: `im.growth_route` on a refused stable row (Task 3); `im.margin_path.ramp` (Task 4); `im.runoff_path.consensus_years` (Task 5); the flag codes `margin-ramp-in-dollars` and `revenue-gap` (Tasks 2 and 4).

- [ ] **Step 1: Write the failing tests**

`test_methodology.py`: the page names "deciles 9 and 2" wording ("the top two deciles", "the bottom two"), "five of the fiscal years on file", "fades to zero", "flat", "past year 3", "half the mature peers' median", "in dollars", and lists `margin-ramp-in-dollars` and `revenue-gap` among the notes (add both to the test's code loop). `test_app.py`: the drawer source carries `consensus_years` and `ramp` and shows `crossCheck` in the refusal section.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/web -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`runoffSummary`: the decline-rate row's note "years 1 to K from the consensus; fades to zero by year N" (on trend: "years 1 to 3 at the decline rate; fades to zero by year N"), the terminal row's note "flat". The refusal section: `crossCheck(im.growth_route)` under the refusal sentence when present. The growth margin row: the note "in dollars" when `ramp === 'dollars'`. The Methodology page: the classifier's direction paragraph (top two, bottom two, "A stable margin points to no phase"), rule 1's exception and rule 4's second count, the notes list; the growth section's two sentences (the bound; the ramp); the Decline list's items 2 and 5 and the "What the price needs" sentence; the flags list's two notes. The examples' figures stay until Task 8.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/web tests
git commit -m "Say in the drawer and on the Methodology page how the run-off fades, when a loss ramps in dollars, and which margin directions point to a phase"
```

### Task 8: The revalue, the readout and the close

**Files:**
- Modify: `src/fairband/web/static/methodology.html` (the six examples' figures and the "Figures as of" line)
- Modify: `docs/backlog.md` (B-1, B-7, B-74, B-27, B-86 to Done with their commits; B-7 leaves Questions)
- Create (scratchpad, not the repo): the peer-spillover probe and the readout script

- [ ] **Step 1: The probe before the revalue**

On a read-only connection to the live database: the rows whose counted peers (the `target_margin.peers` of the latest snapshot, or the industry fallback's) include TTWO, SLAB, SYNA, AXTI, AVAV, NBIS or KYIV, and the rows whose peers include a company whose country is in v2 and not v1. Keep the list for Step 4.

- [ ] **Step 2: Merge and back up**

After the whole-branch review: merge to main, push, stop the server, copy `~/.local/share/fairband/fairband.db` to `fairband-before-v7-<date>.db` with SQLite's backup API.

- [ ] **Step 3: Revalue**

Run: `uv run python -m fairband refresh --kind revalue`
Expected: `refresh <id>: done` with the calibration lines; then start the server on 8470 from main.

- [ ] **Step 4: The readout**

Over refresh 15 and the revalue, spec 15's lines: Decline (valued, designations, median price ÷ value and value ÷ EPV, the K > 3 rows, BBY, TTE, AAP); growth (the "value not positive" count, the rows now valued, the ramp rows, the bound rows); the seven classifier moves and the rows that moved through their peers against Step 1's list; the `margin-direction-disagrees`, `loss-year` and `revenue-gap` counts; no tax refusal for a v2 country; every other row bit for bit. Any row that moved and is on neither list is a defect: stop and report it.

- [ ] **Step 5: The examples' figures**

Re-read the six Methodology examples from the revalue (the MMM example's path and figures move; the others as the revalue says) and the "Figures as of" line; run `uv run pytest tests/web -q`.

- [ ] **Step 6: Close the backlog and commit**

Move B-1, B-74, B-27 and B-86 to Done with the task commits, B-7 to Done with its answer ("50 of 63 were the two faults; 26 valued under the rules; the rest need a margin far above the peers'"); commit and push.

```bash
git add src/fairband/web/static/methodology.html docs/backlog.md
git commit -m "Re-read the Methodology examples under method 0.9 and close the engine round in the backlog"
```
