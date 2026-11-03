# The rate limiter, the classifier fixes, the price-to-value designation and the sticky controls: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pace FMP calls so a full refresh completes in one run; classify an established company with a loss year by its growth word and a Decline only on a string of falling years; replace the engine's stance with a price-to-value word; keep the table's controls in view and add a way back to the top. Method 0.6, policy v5.

**Architecture:** A `RateLimiter` under `VendorHttp.get`, one per vendor client. Two rule changes and two flags in the classifier. A `designation.py` beside `levels.py` whose word rides on the result, the snapshot and the API row in place of the stance. Page work in the vendored bundle under `// fairband:` markers and in the page scripts. Every task updates `docs/method.md` in the same commit (CLAUDE.md).

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, httpx; plain JS with React 18 UMD, no build step; pytest with string tests on the static files.

**Spec:** `docs/superpowers/specs/2026-11-03-classifier-designation-ends-design.md` (sections 5 to 8, 12, 13.3 to 13.5, 14, 15). The second plan, `2026-11-03-start-up-and-decline-routes.md`, builds sections 9 to 11 on top of this one.

## Global Constraints

- Never print, log, store or commit a key; never commit vendor data; fixtures are synthetic or hand-trimmed (CLAUDE.md).
- `docs/method.md` changes in the same commit as any change to the engine, the classifier, the universe rule or a policy value; the method version bumps when the value of any row can move. This plan ends at `fairband-mechanical/0.6` and `fairband-policy-v5`.
- Policies v1 to v4 stay in the package byte for byte; the engine loads v5 only; v4's hash is pinned in `tests/policy/test_policy.py` as v3's is.
- Determinism: the same inputs under the same policy and method version give the same result, bit for bit.
- Every valuation constant lives in the policy file with a source line; structural constants live in code (method 4.1a): the established test (three of the last five fiscal years), the Decline duration test (three of the last four steps).
- No motion on the page (the brand book); the design system's components and classes; edits to `bundle.js`, `bundle.css` and `index.d.ts` carry a `// fairband:` (or `/* fairband: */`) marker.
- A flag warns and never changes a value, a level or a designation.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- Before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.

## Review Focus

1. A 429 whose `Retry-After` is an HTTP date, not a number: the hold is `rate_limit_hold_s`, never a parse error (Task 2's `test_a_429_with_an_http_date_retry_after_holds_the_default`).
2. Sixteen real threads on one limiter: slots never collide and the order of admission is the order of arrival under the lock (Task 2's `test_sixteen_threads_take_distinct_slots`).
3. A snapshot valued under 0.5 read by the screen before the revalue: its JSON carries `stance5` and `stance3` and lacks the new keys; the reader must not fail (Task 5's `test_a_0_5_snapshot_reads_without_the_stance_keys`).
4. A fiscal year without a margin inside the five-year window (no revenue, or revenue at zero): the established count reads the years that have one and never counts a missing year as positive (Task 4's `test_a_year_without_a_margin_counts_for_nothing`).
5. The admission list's symbol form: the universe compares the exchange form (`BRK.B`), exactly and case-sensitively, as `manual_exclusions` does (Task 3's `test_the_admission_list_matches_the_exchange_form_exactly`).

---

### Task 1: Policy v5 and method 0.6

**Files:**
- Create: `src/fairband/policy/fairband-policy-v5.toml`
- Modify: `src/fairband/policy/__init__.py` (the dataclasses at lines 38 to 100, `load_policy`, `_universe`, `_refresh`, `_POLICY_FILE`)
- Modify: `src/fairband/engine/__init__.py:7` (`METHOD_VERSION`)
- Modify: `docs/method.md` (header table, 4.1, 11)
- Test: `tests/policy/test_policy.py`

**Interfaces:**
- Produces: `UniversePolicy.manual_admissions: tuple[str, ...]`; `RefreshPolicy.fmp_calls_per_minute: int`, `RefreshPolicy.rate_limit_hold_s: float`; `Policy.designation_edges: tuple[float, float, float, float]`; `Policy.runoff_years: int`, `Policy.runoff_recovery: float`, `Policy.distress_sale_fraction: float`, `Policy.synthetic_rating: tuple[RatingRow, ...]` with `RatingRow(coverage_min: float, rating: str)` (frozen dataclass, rows ascending by `coverage_min`, the first row's `coverage_min` is `-inf`), `Policy.default_probability_10y: dict[str, float]` (rating → fraction), `Policy.z_distress: float`, `Policy.z_safe: float`, `Policy.f_score_low: int`, `Policy.burn_cover_flag_years: float`; `METHOD_VERSION == "fairband-mechanical/0.6"`; `_POLICY_FILE == "fairband-policy-v5.toml"`.

- [ ] **Step 1: Write the failing tests**

In `tests/policy/test_policy.py`, beside the v4 tests (keep the v3 hash pin; add the v4 one):

```python
V4_SHA256 = "<sha256 of src/fairband/policy/fairband-policy-v4.toml as shipped; compute with sha256sum>"

def test_v5_is_the_packaged_policy() -> None:
    policy = load_policy()
    assert policy.version == "fairband-policy-v5"
    assert policy.universe.manual_admissions == ("V", "MA", "GPN")
    assert set(policy.universe.excluded_industries) >= {
        "Asset Management", "Financial - Capital Markets", "Financial - Credit Services",
        "Financial - Mortgages", "Financial - Conglomerates",
        "Investment - Banking & Investment Services",
    }
    assert policy.refresh.fmp_calls_per_minute == 2850
    assert policy.refresh.rate_limit_hold_s == 60
    assert policy.designation_edges == (0.65, 0.85, 1.15, 1.50)
    assert (policy.runoff_years, policy.runoff_recovery, policy.distress_sale_fraction) == (10, 0.6, 0.6)
    assert (policy.z_distress, policy.z_safe, policy.f_score_low, policy.burn_cover_flag_years) == (1.1, 2.6, 1, 2)

def test_the_synthetic_rating_table_is_damodarans_fifteen_rows() -> None:
    rows = load_policy().synthetic_rating
    assert [r.rating for r in rows] == ["D", "C", "CC", "CCC", "B-", "B", "B+", "BB", "BB+", "BBB", "A-", "A", "A+", "AA", "AAA"]
    assert rows[0].coverage_min == float("-inf")
    assert [r.coverage_min for r in rows[1:]] == [0.2, 0.65, 0.8, 1.25, 1.5, 1.75, 2, 2.25, 2.5, 3, 4.25, 5.5, 6.5, 8.5]

def test_the_default_probabilities_are_table_5s_ten_year_column() -> None:
    p = load_policy().default_probability_10y
    assert p == {"AAA": 0.0007, "AA": 0.0051, "A+": 0.0057, "A": 0.0066, "A-": 0.05, "BBB": 0.0754,
                 "BB+": 0.1963, "BB": 0.1963, "B+": 0.2825, "B": 0.368, "B-": 0.4212,
                 "CCC": 0.5902, "CC": 0.666, "C": 0.8103, "D": 1.0}

def test_v4_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v4.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V4_SHA256
```

Update every existing assertion that names `fairband-policy-v4` as the loaded version or `fairband-mechanical/0.5` (grep `tests/` for both strings) to v5 and 0.6.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/policy/test_policy.py -q`
Expected: FAIL (v4 loaded; the new fields missing).

- [ ] **Step 3: Write `fairband-policy-v5.toml`**

Copy v4 byte for byte, then: `[meta] version = "fairband-policy-v5"`; in `[values.universe.value]` append the six industries to `excluded_industries` and add `manual_admissions = ["V", "MA", "GPN"]`, with the comment "payment companies that do not lend; founder 2026-11-03 (spec 2026-11-03 section 6.4)"; in `[values.refresh.value]` add `fmp_calls_per_minute = 2850` and `rate_limit_hold_s = 60`, and correct the worker comment to "13 FMP calls per company"; add these `[values.<name>]` tables, each with `value` and a `source` line copied from spec section 12:

- `designation_edges`: `[0.65, 0.85, 1.15, 1.50]`
- `runoff_years`: `10`; `runoff_recovery`: `0.6`; `distress_sale_fraction`: `0.6`
- `synthetic_rating`: an array of `{ coverage_min = <number or "-inf">, rating = "<rating>" }` in the fifteen rows of spec section 12 (the first row `coverage_min = "-inf"` as the string, parsed to `float("-inf")`); `attribution` naming Damodaran's ratings page, January 2026, large non-financial firms
- `default_probability_10y`: an inline table of the fifteen ratings to fractions (spec section 12, percent ÷ 100; `D = 1.0`; `"BB+"` equal to `BB`); `attribution` naming Damodaran 2009, "Valuing Distressed and Declining Companies", Table 5, Altman 1971 to 2007, and the note on BB+ and the C+/C− rows left out
- `z_distress`: `1.1`; `z_safe`: `2.6`; `f_score_low`: `1`; `burn_cover_flag_years`: `2`

- [ ] **Step 4: Extend the dataclasses and the loader**

In `policy/__init__.py`: add the fields named in Interfaces; `RatingRow` as a frozen dataclass; `_synthetic_rating(rows) -> tuple[RatingRow, ...]` (accepts the string `"-inf"`; raises `ValueError` unless `coverage_min` ascends strictly and the first is `-inf`); `_probabilities(t) -> dict[str, float]` (each in [0, 1]; `D` must be 1.0); `_universe` reads `manual_admissions`; `_refresh` reads the two values; `_POLICY_FILE = "fairband-policy-v5.toml"`. In `engine/__init__.py`: `METHOD_VERSION = "fairband-mechanical/0.6"`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/policy -q && uv run pytest -q`
Expected: PASS (fix the tests that pinned 0.5 or v4 along the way).

- [ ] **Step 6: Update `docs/method.md`**

The header table (0.6, v5); 4.1: the new rows (one per policy value above, source as the spec's table) and "Policies v1 to v4 stay in the package unchanged ... The engine loads v5 only"; section 11: a row `0.6 | 2026-11-0x | Policy v5 adds the values of the limiter, the universe's admission list and six excluded industries, the designation edges and the Decline and Start-up routes' values (the routes come with 0.7)`. The row's text grows in Tasks 2 to 5.

- [ ] **Step 7: Commit**

```bash
git add src/fairband/policy src/fairband/engine/__init__.py tests/policy docs/method.md
git commit -m "Cut policy v5 with the limiter, universe, designation and distress values and open method 0.6"
```

### Task 2: The FMP rate limiter

**Files:**
- Create: `src/fairband/vendors/limiter.py`
- Modify: `src/fairband/vendors/http.py` (`VendorHttp.__init__` at line 136, `get` at line 182)
- Modify: `src/fairband/refresh/clients.py:18-30`
- Modify: `src/fairband/refresh/fetch.py:1` and `:227` (the stale call counts), `src/fairband/policy/fairband-policy-v5.toml` (the worker comment, if Task 1 left it)
- Modify: `tests/refresh/vendor_double.py` (`Router` gains `fail_once`)
- Modify: `docs/method.md` section 2
- Test: `tests/vendors/test_limiter.py`, `tests/vendors/test_http.py`, `tests/refresh/test_clients.py`, `tests/refresh/test_run_full.py`

**Interfaces:**
- Produces: `RateLimiter(calls_per_minute: float, clock: Callable[[], datetime], sleep: Callable[[float], None])` with `acquire() -> float` (the seconds waited) and `hold(seconds: float) -> None`; `VendorHttp(..., calls_per_minute: float = 0.0)` building its own `RateLimiter` from its clock and sleep, exposed as `VendorHttp.limiter`; `Router.fail_once: dict[tuple[str, str], int]` (an `(endpoint, symbol)` answers `fail_status` that many times, then normally).

- [ ] **Step 1: Write the failing limiter tests**

`tests/vendors/test_limiter.py`, with a settable clock (`tests/refresh/vendor_double.py`'s `Clock`) and a recording sleep that advances the clock:

```python
def test_sixty_a_minute_spaces_calls_one_second_apart() -> None:
    # three acquires at t=0 return waits 0, 1, 2 and the clock reads 2 after the sleeps

def test_zero_a_minute_never_waits() -> None:
    # RateLimiter(0, ...).acquire() == 0.0 ten times with no sleep recorded

def test_a_hold_moves_every_next_slot() -> None:
    # at t=5 hold(60): an acquire at t=10 waits 55; a hold shorter than the next slot changes nothing

def test_sixteen_threads_take_distinct_slots() -> None:
    # 16 threads each acquire once at 600 a minute: the waits are {0, 0.1, ..., 1.5} with no repeat

def test_a_late_arrival_starts_from_now_not_from_the_last_slot() -> None:
    # one acquire at t=0, the next at t=100 waits 0 (slots never accumulate in the past)
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/vendors/test_limiter.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `limiter.py`**

`RateLimiter.acquire`: under a `threading.Lock`, `slot = max(now, self._next)`, `self._next = slot + interval`; outside the lock sleep `(slot - now)` when positive and return it; `interval = timedelta(seconds=60 / calls_per_minute)`, and with `calls_per_minute <= 0` return 0.0 at once. `hold`: under the lock, `self._next = max(self._next, now + seconds)`.

- [ ] **Step 4: Run the limiter tests**

Run: `uv run pytest tests/vendors/test_limiter.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing client tests**

In `tests/vendors/test_http.py`, with its `Script` helper:

```python
def test_every_try_takes_a_slot() -> None:
    # at 60 a minute, a call whose first try answers 500 makes its second try one slot later and after the backoff

def test_a_429_holds_the_limiter_for_the_policy_hold() -> None:
    # 429 without Retry-After: the retry comes rate_limit_hold_s later, and a second client call made meanwhile waits for the hold

def test_a_429_with_a_numeric_retry_after_holds_that_long() -> None:
    # Retry-After: 7 → the retry 7 s later

def test_a_429_with_an_http_date_retry_after_holds_the_default() -> None:
    # Retry-After: Wed, 21 Oct 2026 07:28:00 GMT → the policy hold, no error

def test_limiter_waits_do_not_count_against_the_deadline() -> None:
    # a call admitted after a 55 s hold still has deadline_s from its first try; a 429 then a success at hold+1 s completes

def test_three_429s_still_fail_the_call() -> None:
    # attempts exhausted: VendorError with status 429, as before
```

In `tests/refresh/test_clients.py`: `test_fmp_is_paced_and_gurufocus_is_not` (`fmp.http.limiter` interval from `policy.refresh.fmp_calls_per_minute`; the GuruFocus client's limiter at 0).

In `tests/refresh/test_run_full.py`: `test_a_single_429_does_not_end_the_run` (`router.fail_status = 429`, `router.fail_once[("quote", "ACME")] = 1`, 16 workers: the run ends `done`, every company fetched, the Router saw the quote twice, and the recording sleep saw one hold of `rate_limit_hold_s`). Keep the existing 429 tests (a 429 on every try still ends the run).

- [ ] **Step 6: Run them to see them fail**

Run: `uv run pytest tests/vendors/test_http.py tests/refresh/test_clients.py tests/refresh/test_run_full.py -q`
Expected: FAIL.

- [ ] **Step 7: Wire the limiter into `VendorHttp.get` and `build_clients`**

In `get`: `waited = self.limiter.acquire()` before every `_attempt`; add `waited` to `deadline`; on a failure with `status == 429`, `hold = retry_after if numeric else self._policy.rate_limit_hold_s`, `self.limiter.hold(hold)`, `delay = hold` and the deadline extended by `hold` (the retry's sleep is the hold; the `_MIN_WINDOW_S` check still applies after it). `build_clients`: `calls_per_minute=policy.refresh.fmp_calls_per_minute` for FMP, 0 for GuruFocus. `Router.fail_once` in `vendor_double.py`. Correct the docstrings in `fetch.py` ("thirteen FMP calls and two GuruFocus calls") and the TOML comment.

- [ ] **Step 8: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 9: Update `docs/method.md` section 2**

After "A company's vendor data observed within the last 24 hours is reused": "FMP calls are paced to `fmp_calls_per_minute`, one pace shared by every worker; a 429 answer holds every worker for the vendor's numeric `Retry-After` or `rate_limit_hold_s`, and the call retries after the hold. The retry counts and the run's 429 path are unchanged." Section 11's 0.6 row gains "the FMP pace".

- [ ] **Step 10: Commit**

```bash
git add src/fairband/vendors src/fairband/refresh/clients.py src/fairband/refresh/fetch.py src/fairband/policy tests docs/method.md
git commit -m "Pace FMP calls to the plan's rate with one limiter shared by the workers and hold them on a 429"
```

### Task 3: The universe: six industries out, the admission list in

**Files:**
- Modify: `src/fairband/refresh/universe.py:189-201` (`_exclusion`) and the module docstring at lines 15 to 20
- Modify: `docs/method.md` section 1 (rule 4)
- Test: `tests/refresh/test_universe.py`

**Interfaces:**
- Consumes: `UniversePolicy.manual_admissions` (Task 1).
- Produces: `_exclusion` returns `None` for a symbol on the admission list whatever its industry, after the manual exclusion check and before the industry check; `build_universe` logs one INFO line `manual admission: <symbols admitted, comma separated>` when any.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("industry", ["Asset Management", "Financial - Capital Markets", "Financial - Credit Services",
                                      "Financial - Mortgages", "Financial - Conglomerates", "Investment - Banking & Investment Services"])
def test_the_six_financial_industries_are_excluded(industry: str, ...) -> None:
    # a screener row in the industry is recorded with exclusion_reason f"industry: {industry}"

def test_data_and_stock_exchanges_stay_admitted(...) -> None:

def test_the_admission_list_admits_a_symbol_from_an_excluded_industry(...) -> None:
    # V under "Financial - Credit Services" is admitted; the log has "manual admission: V"

def test_the_admission_list_matches_the_exchange_form_exactly(...) -> None:
    # "v" and "V.X" are not admitted; "BRK.B" on the list is

def test_a_symbol_on_both_lists_is_excluded(...) -> None:
    # manual_exclusions wins: reason "manual exclusion"
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/refresh/test_universe.py -q`
Expected: the six-industry test passes already (v5 lists them); the admission tests FAIL.

- [ ] **Step 3: Implement the admission check in `_exclusion` and the log line**

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/refresh -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md` section 1**

Rule 4 names the six industries added and says `Financial - Data & Stock Exchanges` stays; a new sentence: "A symbol on the manual admission list (`manual_admissions`: V, MA, GPN, payment companies that do not lend) passes rule 4 whatever its industry; a symbol on both lists is excluded." Replace the "Known gap" paragraph with the admission rule. Note that a universe is built by a full refresh only, so the rule applies at the next full refresh.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/refresh/universe.py tests/refresh/test_universe.py docs/method.md
git commit -m "Exclude six financial industries from the universe and admit the payment networks by name"
```

### Task 4: The classifier: the established company and the Decline duration test

**Files:**
- Modify: `src/fairband/engine/classifier.py` (`classify` at line 180, `_checks` at line 285, the module docstring)
- Modify: `docs/method.md` 3.5, 3.6, 8, 11
- Test: `tests/engine/test_classifier.py`

**Interfaces:**
- Produces: `established(series: Series) -> tuple[bool, int]` (whether at least `ESTABLISHED_YEARS = 3` of the last `TREND_YEARS` (5) fiscal years have an operating margin above zero, and that count); `falling_steps(series: Series) -> tuple[int, int]` (falls, steps among the last `DECLINE_STEPS = 4` year-over-year steps; a step counts only when both years have a revenue; a fall is a later revenue below the earlier); `DECLINE_FALLS = 3`; the flags `loss-year` ("Loss year") and `revenue-falling` ("Revenue falling") with the spec's sentences (6.2, 6.3).

- [ ] **Step 1: Write the failing tests**

Using the file's series builder (`tests/engine/test_classifier.py` has one; use the same `Deciles` fixture as the growth-word tests):

```python
def test_an_established_company_with_a_loss_year_follows_its_growth_word() -> None:
    # margins 4%, 4%, 3%, 2%, -1%, growth word Moderate → "Mature Growth"; flag codes include "loss-year"
    # with the sentence "The operating margin is negative in fiscal 2025 after a positive margin in 4 of the last five fiscal years; the phase follows the growth word."

def test_an_established_company_with_a_low_growth_word_is_mature_stable() -> None:
    # margins 4%, 4%, 3%, 2%, -1%, growth word Low → "Mature Stable", "loss-year"

def test_a_pre_profit_company_keeps_the_margin_trend_rule() -> None:
    # margins -5%, -4%, -3%, 1%, -1%: one positive year → High Growth (rising) / Young Growth (falling); no "loss-year"; "growth-word-disagrees" fires as before

def test_exactly_three_positive_years_is_established() -> None:

def test_a_year_without_a_margin_counts_for_nothing() -> None:
    # five years, margins 5%, None, 5%, 5%, -1% → established (3 positive among the four with one)

def test_growth_word_disagrees_is_silent_under_the_established_rule() -> None:

def test_decline_needs_three_falling_steps() -> None:
    # revenues 100, 95, 90, 86, 83, bottom growth word, falling slope → "Decline"

def test_one_falling_step_is_not_decline_and_is_flagged() -> None:
    # revenues 100, 120, 80, 82, 84, positive margin → "Mature Stable"; "revenue-falling" with
    # "Revenue fell in 1 of the last four fiscal years with a falling five-year trend; the Decline rule needs three."

def test_three_steps_all_falling_is_decline() -> None:
    # four years on file: 100, 95, 90, 86

def test_two_steps_on_file_cannot_make_decline() -> None:

def test_decline_comes_before_the_established_rule() -> None:
    # an established company with a loss year and four falling steps → "Decline", no "loss-year"
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_classifier.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement the two rules and the two checks**

In `classify`: compute `est, positive_years = established(series)` and `falls, steps = falling_steps(series)`; rule 2 adds `and falls >= DECLINE_FALLS`; rule 4: `if margin < 0 and est:` fall through to the growth-word rules (5), appending `loss-year` in `_checks`; else the margin-trend rule. In `_checks`: `growth-word-disagrees` only when the margin is below zero and the company is not established; `loss-year` when the margin is below zero and established (needs the last fiscal year with a margin and `positive_years`); `revenue-falling` when `g_word == GROWTH_WORDS[0]`, the slope is below zero and `falls < DECLINE_FALLS` (needs `falls`). Pass what `_checks` needs as arguments.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/engine -q`
Expected: PASS (adjust any existing classifier test whose series now reads differently; say which in the report).

- [ ] **Step 5: Update `docs/method.md`**

3.5: the rules as spec 6.2 and 6.3 state them (rule 2 with the duration test; rule 4a and 4b). 3.6: two rows, `loss-year` and `revenue-falling`, with when they fire; `growth-word-disagrees` "Negative margin of a company that is not established". 4.1a: the two structural constants. Section 8's classifier row names the two new codes. Section 11's 0.6 row gains "the established company with a loss year (3.5 rule 4a) and the Decline duration test (rule 2)".

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine/classifier.py tests/engine/test_classifier.py docs/method.md
git commit -m "Classify an established company with a loss year by its growth word and require three falling years for Decline"
```

### Task 5: The designation in the engine, the snapshot, the JSON and the API row

**Files:**
- Create: `src/fairband/engine/designation.py`
- Create: `src/fairband/store/migrations/002_designation.sql`
- Modify: `src/fairband/engine/types.py` (`ValuationResult`, `Stance5`/`Stance3`, `result_from_json`), `src/fairband/engine/levels.py` (drop `stance5`, `stance3`), `src/fairband/engine/route.py` (`_valued` at line 322, `reprice` at line 280, `refusal_result`), `src/fairband/store/snapshots.py` (`SnapshotRow`, `insert_snapshot`, the row reader), `src/fairband/refresh/run_price.py` (docstring lines 20 to 26)
- Modify: `src/fairband/web/rows.py` (`SCREEN_ROW_KEYS` lines 30 to 45, `EXTRA_KEYS` 47 to 75, `COLUMNS` 80 to 95, the row dict at 115 to 160, `_group` at 218 to 229), `src/fairband/web/app.py:144-160` (the sort key validation if it names keys), the groups page script that reads `shareBelowBuy` (grep `src/fairband/web/static` for it)
- Modify: `docs/method.md` 4.10, 8, 10, 11
- Test: `tests/engine/test_designation.py` (new), `tests/engine/test_levels.py`, `tests/engine/test_types.py`, `tests/engine/test_route.py`, `tests/store/test_snapshots.py`, `tests/refresh/test_run_price.py`, `tests/web/test_app.py` (the key lists at lines 70 to 110, the row assertions at 229 to 290), `tests/web/test_groups.py`

The engine and the API row change together so the suite is green at the commit: `rows.py` reads the snapshot's columns and the web tests pin the row's keys.

**Interfaces:**
- Consumes: `Policy.designation_edges` (Task 1).
- Produces: `Designation = Literal["well-below", "below", "near", "above", "well-above"]` in `types.py`; `designation_for(price: float, value: float, edges: tuple[float, float, float, float]) -> tuple[float, Designation]` in `designation.py` (price ÷ value as a plain float division; the word by spec 7.1's table, comparing the ratio with the edges as floats, so `85 / 100` reads `near` and `150 / 100` reads `well-above`); `ValuationResult.price_to_value: float | None` and `ValuationResult.designation: Designation | None` in place of `stance5` and `stance3`; `SnapshotRow.price_to_value`, `SnapshotRow.designation`; the `snapshots` table gains the columns `price_to_value REAL` and `designation TEXT` (the old `stance5`, `stance3` columns stay and are no longer written); `result_from_json` drops the keys `stance5` and `stance3` if present and defaults the two new keys to `None` if absent; the API row carries `priceToValue: float | None` and `designation: str | None` and no `stance3`/`stance5`; `COLUMNS` lists `designation` where `stance` was; `sort=priceToValue` sorts by the ratio with `None` last; the group dict carries `shareBelowValue` (the share of valued, priced rows with `priceToValue < edges[1]`) in place of `shareBelowBuy`.

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_designation.py`:

```python
@pytest.mark.parametrize("price, word", [(64.99, "well-below"), (65, "below"), (84.99, "below"), (85, "near"),
                                         (115, "near"), (115.01, "above"), (149.99, "above"), (150, "well-above")])
def test_the_five_bands_on_a_value_of_100(price: float, word: str) -> None:
    ratio, got = designation_for(price, 100.0, (0.65, 0.85, 1.15, 1.50))
    assert got == word and ratio == pytest.approx(price / 100)
```

`tests/engine/test_levels.py`: delete `test_stances`. `tests/engine/test_route.py`: the valued Mature Growth result carries `price_to_value` and `designation` and has no `stance5`/`stance3` attribute; `reprice` from a price of 70 to 120 on a value of 100 moves `below` to `above` and leaves `levels`; a refusal has `None` for both. `tests/engine/test_types.py`: the JSON round trip with the two fields; `test_a_0_5_snapshot_reads_without_the_stance_keys` (a JSON string with `"stance5": "HOLD", "stance3": "hold"` and no `designation` key reads, with `None` for the new fields). `tests/store/test_snapshots.py`: the inserted row has the two columns and `stance5`/`stance3` NULL. `tests/refresh/test_run_price.py`: the repriced snapshot's `designation` follows the new price. `tests/web/test_app.py`: the key lists updated; the fixture row's `priceToValue` and `designation` asserted from its price and value (state the figures); `GET /api/screen?sort=priceToValue&dir=asc` orders by the ratio with `None` last. `tests/web/test_groups.py`: `shareBelowValue` on a group with one row below 0.85 and one above.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine tests/store tests/refresh/test_run_price.py tests/web -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`designation.py` as in Interfaces. `types.py`: the Literal, the two fields, the tolerant reader. `levels.py`: remove the two functions and the `Stance` imports. `route.py`: `_valued` sets `price_to_value, designation = designation_for(price, v.value, policy.designation_edges)`; `reprice` the same from `result.value` and the new price; `refusal_result` passes `None`. `002_designation.sql`: the two `ALTER TABLE snapshots ADD COLUMN` statements (check how `store/db.py` applies numbered migrations and follow it). `snapshots.py`: read and write the two columns; leave `stance5`/`stance3` out of the INSERT. `run_price.py`'s docstring: "the designation" for "the stance". `rows.py` and the groups script as in Interfaces.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md`**

4.10 becomes "Levels, designation and validity": the levels unchanged; spec 7.1's table in place of the stance table; "The designation is a fact about the price: a price refresh recomputes it; a refusal and a Start-up row have none." Section 8's first sentence: "never changes a value, a level or a designation". Section 10's price-refresh bullet: "the designation" for "the stance". Section 11's 0.6 row gains "the stance leaves the engine; the designation on price ÷ value (4.10)".

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine src/fairband/store src/fairband/web src/fairband/refresh/run_price.py tests docs/method.md
git commit -m "Replace the engine's stance with a price-to-value designation on the result, the snapshot and the screen row"
```

### Task 6: The page: the designation column, chip, filter and drawer

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (`STANCE` at line 43, `stanceOf` at 94, `BandMeter` 417 to 471, `FILTER_GROUPS`/`EMPTY_FILTERS` 842 to 846, the chips at 871, the `stance` column at 947, `DEFAULT_COLUMNS` at 1030, the filter menu's STANCE section near 1234)
- Modify: `src/fairband/web/static/design-system/components/bundle.css` (`.fb-stance` at 40 to 50) and `index.d.ts`
- Modify: `src/fairband/web/static/app.js` (`SORT_KEYS` at 16, `stanceOf` at 203 to 211, `narrow` at 223, the drawer caption at 316 and the level labels in `sections()`)
- Test: `tests/web/test_app.py` (the string tests at 737, 843 to 915 and the `index.d.ts` tests at 1011 to 1030)

**Interfaces:**
- Consumes: the row's `designation` and `priceToValue` (Task 5).
- Produces: `DESIGNATION = { 'well-below': 'Well below', 'below': 'Below', 'near': 'Near', 'above': 'Above', 'well-above': 'Well above' }` in the bundle; a `designation` column (head "Price vs value") whose cell is `<span class="fb-designation label">` with the word, an em dash without one; `FILTER_GROUPS` and `EMPTY_FILTERS` use `designation`; the filter menu section "PRICE VS VALUE" listing the five words in band order, each a checkbox as the PHASE section's are, and the chip "Price vs value: Below + Near" when chosen; `DEFAULT_COLUMNS` ends `'price', 'designation'`; `SORT_KEYS.designation = 'priceToValue'`; `narrow` filters on `r.designation`; the band meter's caption "<Word>: the price is <ratio> × the value" (ratio to two decimals) and the level labels "Margin of safety" (with "value less the <moat> moat's <n>%"), "Fair band", "1.5 × value"; no `stanceOf`, no `STANCE`, no "Five-step stance".

- [ ] **Step 1: Write the failing string tests**

Replace `test_app_js_filter_rule_handles_missing_fields` and the bundle's null-stance tests with: `test_bundle_has_the_five_designation_words` (the `DESIGNATION` object, in band order), `test_bundle_filter_menu_has_a_price_vs_value_section` (`'PRICE VS VALUE'`, the five words, the group key `designation` in `FILTER_GROUPS` and `EMPTY_FILTERS`), `test_bundle_designation_column_head_and_chip` (`head: 'Price vs value'`, `fb-designation`, the em dash for a missing word, "never Hold"), `test_bundle_default_columns_end_with_designation`, `test_app_js_sorts_designation_by_the_ratio` (`designation: 'priceToValue'`), `test_app_js_narrows_on_the_designation` (`within(filters.designation, r.designation)`), `test_app_js_drawer_states_the_ratio_and_the_level_labels` (`'× the value'`, `'Margin of safety'`, `'1.5 × value'`), `test_no_stance_word_remains` (neither `stanceOf` nor `STANCE[` nor `Five-step` in `app.js`, `controls.js`, `bundle.js`, `index.d.ts`), and the `index.d.ts` pins updated.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/web/test_app.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement in the bundle and the page script, each edit under a `// fairband:` marker**

`.fb-designation` in `bundle.css`: the chip's shape from `.fb-stance` (uppercase label, outline) with the default text colour, no per-band colour; delete `.fb-stance--*`; keep `--stance-*` tokens for `.fb-delta` and `.fb-rec__effect`.

- [ ] **Step 4: Run the suite and look at the page**

Run: `uv run pytest -q`; then `uv run python -m fairband serve` against a copy of the database (never the founder's live file while a refresh runs) and check the column, the filter section, the drawer caption.
Expected: PASS; the page shows the word and the ratio, and the filter narrows by band.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/web/static tests/web/test_app.py
git commit -m "Show the price-to-value word in the table, the filter and the drawer in place of the stance"
```

### Task 7: The sticky controls bar and the back-to-top control

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.css` (`.fb-screen__bar` at 638, `.fb-table thead th` at 750)
- Modify: `src/fairband/web/static/index.html` (the `.app-layout` and `.app-main` rules at 58 to 62)
- Modify: `src/fairband/web/static/app.js` (the screen's render; a `ResizeObserver` on the bar; the scroll listener; the Top button)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Produces: `.fb-screen__bar { position: sticky; top: 0; z-index: 5; background: var(--surface-raised); }`; `.fb-table thead th { top: var(--bar-height, 40px); }`; `app.js` sets `--bar-height` on `.app-main` from a `ResizeObserver` on `.fb-screen__bar`; a button `F.Button({variant: 'quiet', size: 'sm', 'aria-label': 'Back to top', className: 'app-top'}, 'Top ↑')` rendered inside `.app-layout` (which gains `position: relative`; `.app-top { position: absolute; right: var(--space-4); bottom: var(--space-4); z-index: 6 }`) only while `main.scrollTop > main.clientHeight`; on click `main.scrollTop = 0` and `document.getElementById('fb-q').focus()`.

- [ ] **Step 1: Write the failing string tests**

`test_bundle_css_bar_is_sticky_and_the_header_sits_under_it` (`position: sticky` in `.fb-screen__bar`; `top: var(--bar-height` in the thead rule), `test_app_js_measures_the_bar` (`ResizeObserver`, `'--bar-height'`), `test_app_js_back_to_top` (`'Back to top'`, `scrollTop > main.clientHeight` or the equivalent expression, `scrollTop = 0`, `getElementById('fb-q').focus()`), `test_index_positions_the_top_control` (`.app-top`, `position: absolute`), and `test_index_gives_the_find_ring_room` still passes.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/web/test_app.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

No smooth scrolling, no transition. Guard `ResizeObserver` with `typeof ResizeObserver !== 'undefined'`.

- [ ] **Step 4: Run the suite and look at the page**

Run: `uv run pytest -q`; serve against a database copy; scroll: the bar and the header stay, the Top control appears past one screen and returns to the top with focus on FIND.
Expected: PASS and the behaviour as described.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/web/static tests/web/test_app.py
git commit -m "Keep the table's controls bar in view with the header and add a back-to-top control"
```

### After the merge (the controller, not a task)

A revalue of the founder's database under 0.6/v5, then a full refresh in one run (the limiter's proof; it also applies the universe exclusions and the admission list), then the readout of spec 15.6 for this plan's parts: the phase counts before and after, the rows the classifier moved and their outcomes, the designation counts by band, the companies the exclusion removed and the three admitted.
