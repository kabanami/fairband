# The Growth Routes and Four Screen Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** High Growth and Young Growth rows get a value from Damodaran's revenue DCF on one route, `revenue-growth`, with the target margin and the sales-to-capital fallback from mature peers, and the page gets its one-line status with a details popover, closing menus, a clear control on FIND and an unclipped focus ring.

**Architecture:** A pure core, `engine/revenue_growth.py`, turns a revenue path, a margin path, a tax rate, a sales-to-capital and the terminal terms into the ten-year tables and the equity value, and solves the two price-implied figures. A route module, `engine/route_revenue_growth.py`, reads a `Context` as the mature routes do, chooses the sales-to-capital, builds the intermediates and the flags, and dispatches from `route.value_company` for both phases. Assembly gains the peers: one new FMP call stored like every other, and a `refresh/peers.py` that classifies each peer from the store with the refresh's deciles and computes its margin, sales-to-capital and ROIC, so the route stays pure. Policy v3 carries the new values; the method version becomes 0.4. The page changes are `controls.js` (the status line and its popover), three marked patches in the bundle (menus, Clear) and one page style (the ring).

**Tech Stack:** Python 3.13, uv, pytest, Ruff, mypy; React 18 through the vendored design-system bundle, no build step. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-02-growth-routes-design.md`. It amends `docs/method.md`, which states the method as built and must be updated in the same commits as the engine (Task 8).

## Global Constraints

- `uv run` for every command; before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- Code holds no valuation constant: every number of spec section 7 comes from `src/fairband/policy/fairband-policy-v3.toml`, each `[values.<name>]` with `value` and `source`. The solve bounds for the implied growth stay the module constants of `mature_growth.py` (−50% to 200%).
- `fairband-policy-v2.toml` stays byte-identical; its sha256 is `f54a31ab4b4a6a0ca549218773191d0936de63ecce50ab5224b3511046a1070b`. `fairband-policy-v1.toml` keeps its hash `cfc46d15585c283322f50a710d3385f4921c186ed94679a542c0571a43b54bde`. The engine loads v3 only.
- Method version `fairband-mechanical/0.4` (`fairband.engine.METHOD_VERSION`).
- r = 0.09 and g_T = 0.03 stay; the two mature routes are unchanged in every figure (their tests pass untouched, except where a test names the policy or method version).
- The same inputs and the same policy give the same intermediates, bit for bit. Intermediates hold JSON values only (no NaN, no infinity); `result_to_json` round-trips.
- Every refusal stays a `ValuationResult` with `value=None`, `route=None` and a reason; a value at or below zero is refused.
- Flags: `Flag(code, word, sentence)`, code in kebab-case, word short enough for the Flags column, sentence one line for the drawer.
- Every change to the exported bundle carries a `// fairband:` comment (JavaScript) or `/* fairband: */` (CSS); `test_bundle_patches_marked` counts them (19 today).
- No JSX, no build step: `React.createElement` against `window.Fairband`. Controls are named by words, never a glyph.
- Tests under `tests/` mirror the package; fixtures synthetic or hand-trimmed; never a vendor call in a test; never a key anywhere.
- `docs/method.md` changes in the same commit as any engine change (Tasks 1, 3, 5 and 8 each carry their part).
- Commit messages: one plain sentence in the imperative; every commit ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Work on a branch, never on `main`.

## Review Focus

Inputs the spec implies but no acceptance number covers. Each has its test in the task named.

1. **A consensus that shrinks revenue** (NTM revenue below trailing, or g_3 below g_T): the fade must rise to g_T, not fall, and a year whose revenue falls must reinvest nothing, never a negative amount. Test in Task 2 (`test_fade_rises_when_g3_is_below_the_terminal_rate`) and Task 3 (`test_reinvestment_never_negative`).
2. **A peer list that names the company itself, a symbol outside the universe, or a company that is not Mature Growth or Mature Stable** must drop those and count only what is left. Test in Task 4 (`test_peers_keep_only_mature_universe_companies`).
3. **A row refused for the target margin, repriced by a price refresh**, must keep its refusal and move its implied margin; a plain refusal must still take only the new price. Test in Task 5 (`test_reprice_moves_the_implied_margin_on_a_refused_row`).
4. **A target margin at or below zero** (loss-making peers) gives a negative NOPAT in every year and a return on new capital at or below zero: the terminal return must fall back to r without dividing by zero, and the row must refuse "value not positive under the reinvestment charge". Test in Task 3 (`test_negative_target_margin_values_below_zero`).
5. **A company whose invested capital is near zero** must give a huge own sales-to-capital only when the usability test passes, and the implied-return flag must then fire. Test in Task 3 (`test_own_sales_to_capital_usability`) and Task 5 (`test_return_above_peers_flag`).

---

## File structure

```
src/fairband/
  engine/__init__.py              METHOD_VERSION → 0.4
  engine/types.py                 Route gains "revenue-growth"
  engine/anchor.py                AnnualEstimate.analysts_revenue
  engine/revenue_growth.py        new: RevenuePath, MarginPath, PeerFigures, TargetMargin, the tables, the value, the solves
  engine/route_revenue_growth.py  new: value_revenue_growth, revenue_at_price, implied_margin_at_price
  engine/route.py                 CompanyInputs.peers/debt/cash; dispatch; reprice for the route and for its refusals
  engine/mature_growth.py         solve_root factored out of implied_growth
  policy/__init__.py              v3 default; five new fields; UniversePolicy.name_exclude_patterns
  policy/fairband-policy-v3.toml  new
  vendors/fmp.py                  Fmp.peers
  vendors/normalize_fmp_observations.py  peer_symbols
  refresh/fetch.py                the "peers" call
  refresh/peers.py                new: peer_figures
  refresh/inputs.py               build_inputs(..., deciles); peers, debt, cash, analysts_revenue
  refresh/universe.py             the name patterns
  refresh/run.py                  the value stage passes the deciles
  web/rows.py                     targetMargin, impliedMargin; growthRouteValue on the new route
  web/static/design-system/components/bundle.js   two columns; menus close; Clear on FIND
  web/static/app.js               ROUTES; the drawer's revenue section
  web/static/controls.js          the one-line status and Details ▾
  web/static/index.html           the ring's room
docs/method.md                    the route's sections; section 10's exception; the version log
tests/
  policy/test_policy.py, engine/test_revenue_growth.py (new), engine/test_route_revenue_growth.py (new),
  engine/test_route.py, support/engine_companies.py, refresh/test_fetch.py, refresh/test_peers.py (new),
  refresh/test_inputs.py, refresh/test_universe.py, refresh/test_run_price.py, vendors/test_normalize_fmp.py,
  web/test_app.py, fixtures/fmp/stock-peers.ACME.json, fixtures/fmp/stock-peers.BOLT.json
```

---

### Task 1: Policy v3, the method version and the name patterns on the universe

**Files:**
- Create: `src/fairband/policy/fairband-policy-v3.toml`
- Modify: `src/fairband/policy/__init__.py`, `src/fairband/engine/__init__.py`, `src/fairband/refresh/universe.py`, `docs/method.md` (sections 1 and 11)
- Test: `tests/policy/test_policy.py`, `tests/refresh/test_universe.py`

**Interfaces:**
- Produces: `Policy.high_growth_years: int` (5), `Policy.margin_convergence_year: int` (10), `Policy.peer_min: int` (3), `Policy.peer_margin_min_years: int` (5), `Policy.implied_margin_bounds: tuple[float, float]` ((−0.5, 1.0)), `UniversePolicy.name_exclude_patterns: tuple[str, ...]`; `load_policy().version == "fairband-policy-v3"`; `METHOD_VERSION == "fairband-mechanical/0.4"`; a universe row excluded for its name carries `exclusion_reason == "name pattern"` and `UniverseResult.excluded["name pattern"]` counts it.

- [ ] **Step 1: Write the failing tests** in `tests/policy/test_policy.py`:

```python
V2_SHA256 = "f54a31ab4b4a6a0ca549218773191d0936de63ecce50ab5224b3511046a1070b"

def test_v3_is_the_default_and_carries_the_growth_route_values() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v3"
    assert p.high_growth_years == 5 and p.margin_convergence_year == 10
    assert p.peer_min == 3 and p.peer_margin_min_years == 5
    assert p.implied_margin_bounds == (-0.5, 1.0)
    assert p.fade_years == 5 and p.marginal_return_span_years == 5  # reused, unchanged
    assert p.universe.name_exclude_patterns[0] == r"\bnotes?\b"

def test_v2_file_is_unchanged() -> None:
    data = resources.files("fairband.policy").joinpath("fairband-policy-v2.toml").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V2_SHA256
```

Change the existing `test_v1_file_is_unchanged` to keep its hash and `_packaged_bytes()` to read v3. In `tests/refresh/test_universe.py`:

```python
def test_name_pattern_excludes_notes_and_preferreds(conn, clients, router, clock, policy) -> None:
    rows = [listing("ABXL", 3e9, companyName="Abacus Global Management, Inc. - 8.875% Fixed Rate Senior Notes due 2028"),
            listing("ACME", 3e9, companyName="Acme Industries Inc.")]
    router.bodies["screener"] = json.dumps(rows).encode()
    result = build_universe(conn, clients.fmp, policy, 1, clock.now, [])
    assert result.admitted == ("ACME",)
    assert result.excluded["name pattern"] == 1
    assert latest_company(conn, "ABXL").exclusion_reason == "name pattern"
```

Add a case per pattern: "5.00% Preferred Stock", "Preference Shares", "Senior Notes", "due 2029" excluded; "Unit Corporation", "Rights Holdings Inc." and "Taiwan Semiconductor American Depositary Shares" admitted (no name pattern covers units, rights or depositary shares; the symbol rule covers the first two). Use the `listing` helper of `tests/refresh/fixture_universe.py` (check its keyword for the name).

- [ ] **Step 2: Run the tests to see them fail**: `uv run pytest tests/policy tests/refresh/test_universe.py -q` — FAIL on the version, the attributes and the reason.

- [ ] **Step 3: Write `fairband-policy-v3.toml`**: copy v2, set `[meta] version = "fairband-policy-v3"`, rewrite the header comment to say v3 and name the spec, and add, with spec section 7's source lines:

```toml
[values.high_growth_years]
value = 5
source = "growth routes spec 5.4; Damodaran's template holds one rate through year 5 (openalice H2) and splits the period half and half (H3); policy value"

[values.margin_convergence_year]
value = 10
source = "growth routes spec 5.5; Damodaran's template default and his Zomato case (openalice H2); policy value"

[values.peer_min]
value = 3
source = "design.md 6.2 and 6.7: minimum mature peers for the target-margin default; no source gives the number"

[values.peer_margin_min_years]
value = 5
source = "growth routes spec 5.5; Damodaran H64, mature margins at averages over the last five or ten years; policy value"

[values.implied_margin_bounds]
value = [-0.5, 1.0]
source = "no source: the bounds of the solve for the margin the price needs (growth routes spec 5.11)"
```

and under `[values.universe.value]`:

```toml
# Regular expressions on the listing's name, matched ignoring case, for notes and preferred
# shares whose symbols carry no suffix (growth routes spec 5.17). ABXL, "... 8.875% Fixed Rate
# Senior Notes due 2028", is the known case. Warrants, units and rights are caught by the
# symbol patterns; "depositary" is not listed because an ADR's name can carry it.
name_exclude_patterns = ['\bnotes?\b', '\bdue 20\d\d\b', '\d(\.\d+)?% ', '\bpreferred\b', '\bpreference\b']
```

- [ ] **Step 4: Change the loader**: `_POLICY_FILE = "fairband-policy-v3.toml"`; add the five fields to `Policy` after `fade_years`, read with `read("high_growth_years", _whole)`, `read("margin_convergence_year", _whole)`, `read("peer_min", _whole)`, `read("peer_margin_min_years", _whole)`, `read("implied_margin_bounds", _pair)`; `UniversePolicy` gains `name_exclude_patterns: tuple[str, ...]`, read in `_universe`. Set `METHOD_VERSION = "fairband-mechanical/0.4"`.

- [ ] **Step 5: Add the name rule to the universe**: in `universe.py`, `_exclusion` checks the name after the industry and before the symbol: `row.name` matched by any of the compiled name patterns with `re.IGNORECASE` gives `"name pattern"`; `_REASONS` gains `"name pattern"`; the module docstring lists the rule as step 5 and renumbers. `build_universe` compiles the name patterns once, as it does the symbol patterns.

- [ ] **Step 6: Update `docs/method.md`**: section 1 gains the name rule as rule 6 and drops "some notes and preferreds pass rule 5" from the known gaps; section 11 gains the row `| 0.4 | 2026-11-… | The High Growth and Young Growth routes (section 5a); the name patterns on the universe. Policy v3 adds five values. |` (the route section is written in Task 8; the row names it now).

- [ ] **Step 7: Run the whole suite**: `uv run pytest -q`. Tests that pin `fairband-policy-v2` or `0.3` by name fail; make them read `policy.version` and `METHOD_VERSION`. Expected after: PASS.

- [ ] **Step 8: Commit**: `git add -A && git commit -m "Add policy v3 with the growth routes' values, move the method version to 0.4 and exclude notes and preferred shares by name"`.

---

### Task 2: The revenue path, the margin path and the tax carry

**Files:**
- Create: `src/fairband/engine/revenue_growth.py`
- Test: `tests/engine/test_revenue_growth.py`

**Interfaces:**
- Produces, in `revenue_growth.py`:
  - `@dataclass(frozen=True) class RevenuePath: revenue0: float; ntm_revenue: float; steps: tuple[float | None, float | None]; hold: float | None; high_growth_years: int; fade_years: int; g_t: float` — `hold` is the rate of the high-growth years after year 3; `None` means g_3 as resolved.
  - `def resolved_steps(path: RevenuePath) -> tuple[tuple[float, float], tuple[bool, bool]]` — (g_2, g_3) with a missing step holding the last known rate (g_2 holds g_1 = ntm_revenue ÷ revenue0 − 1; g_3 holds g_2), and which of the two were held.
  - `def growth_rates(path: RevenuePath) -> tuple[float, ...]` — years 1 to N, N = high_growth_years + fade_years: g_1, g_2, g_3, the hold rate for years 4 to high_growth_years, then the fade `g_t = hold − (hold − g_T) × (t − H) ÷ fade_years` for t = H + 1 … N (H = high_growth_years).
  - `def revenue_by_year(path: RevenuePath) -> tuple[float, ...]` — years 1 to N.
  - `@dataclass(frozen=True) class MarginPath: start: float; target: float; convergence_year: int`
  - `def margins_by_year(margin: MarginPath, years: int) -> tuple[float, ...]` — `start + (target − start) × min(t, convergence_year) ÷ convergence_year` for t = 1 … years.
  - `def tax_and_nopat(ebit: Sequence[float], tax_rate: float) -> tuple[tuple[float, ...], tuple[float, ...]]` — (tax by year, NOPAT by year) with the carried loss starting at zero.

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_revenue_growth.py`, with the spec's section 8 numbers:

```python
PATH = RevenuePath(1_000.0, 1_300.0, (0.25, 0.20), None, 5, 5, 0.03)

def test_growth_rates_hold_then_fade() -> None:
    assert growth_rates(PATH) == pytest.approx(
        (0.30, 0.25, 0.20, 0.20, 0.20, 0.166, 0.132, 0.098, 0.064, 0.03))

def test_revenue_by_year() -> None:
    assert revenue_by_year(PATH) == pytest.approx(
        (1300.0, 1625.0, 1950.0, 2340.0, 2808.0, 3274.13, 3706.31, 4069.53, 4329.98, 4459.88), abs=0.01)

def test_missing_steps_hold_the_last_known_rate() -> None:
    (g2, g3), held = resolved_steps(replace(PATH, steps=(None, None)))
    assert (g2, g3) == pytest.approx((0.30, 0.30)) and held == (True, True)
    (g2, g3), held = resolved_steps(replace(PATH, steps=(0.25, None)))
    assert (g2, g3) == pytest.approx((0.25, 0.25)) and held == (False, True)

def test_hold_overrides_g3() -> None:
    assert growth_rates(replace(PATH, hold=0.10))[3:5] == pytest.approx((0.10, 0.10))
    assert growth_rates(replace(PATH, hold=0.10))[9] == pytest.approx(0.03)

def test_fade_rises_when_g3_is_below_the_terminal_rate() -> None:
    rates = growth_rates(replace(PATH, steps=(0.0, -0.02)))
    assert rates[4] == pytest.approx(-0.02) and rates[5] == pytest.approx(-0.01)
    assert rates[9] == pytest.approx(0.03)

def test_margins_converge_linearly_both_ways() -> None:
    assert margins_by_year(MarginPath(-0.10, 0.20, 10), 10) == pytest.approx(
        (-0.07, -0.04, -0.01, 0.02, 0.05, 0.08, 0.11, 0.14, 0.17, 0.20))
    assert margins_by_year(MarginPath(0.30, 0.20, 10), 10)[9] == pytest.approx(0.20)
    assert margins_by_year(MarginPath(-0.10, 0.20, 5), 10)[4:] == pytest.approx((0.20,) * 6)

def test_tax_carries_the_forecast_losses() -> None:
    ebit = (-91.0, -65.0, -19.5, 46.8, 140.4, 261.93, 407.69, 569.73, 736.1, 891.98)
    tax, nopat = tax_and_nopat(ebit, 0.21)
    assert tax == pytest.approx((0, 0, 0, 0, 2.46, 55.01, 85.62, 119.64, 154.58, 187.32), abs=0.01)
    assert nopat[4] == pytest.approx(137.94, abs=0.01) and nopat[0] == pytest.approx(-91.0)
```

- [ ] **Step 2: Run the tests to see them fail**: `uv run pytest tests/engine/test_revenue_growth.py -q` — FAIL with "No module named fairband.engine.revenue_growth".

- [ ] **Step 3: Write `revenue_growth.py`** with the dataclasses and the five functions of the Interfaces block. The module docstring states the path (spec 5.3, 5.4), the margin line (5.5) and the tax carry (5.7) as the mature modules state theirs. The tax carry: a loss year adds its size to the carried loss and pays no tax; a profit year is taxed on `max(0, ebit − carried)` and reduces the carried loss by `ebit`, never below zero.

- [ ] **Step 4: Run the tests to see them pass**: `uv run pytest tests/engine/test_revenue_growth.py -q` — PASS.

- [ ] **Step 5: Commit**: `git add -A && git commit -m "Build the revenue path, the margin path and the tax carry of the growth routes"`.

---

### Task 3: Reinvestment, the firm value, the equity and the solves

**Files:**
- Modify: `src/fairband/engine/revenue_growth.py`, `src/fairband/engine/mature_growth.py:122-160`, `docs/method.md` (a note under 4.1a for the solve bounds)
- Test: `tests/engine/test_revenue_growth.py`, `tests/engine/test_mature_growth.py`

**Interfaces:**
- Consumes: `terminal_roic(aggregate, moat, policy)` from `roic.py`; `RoicYear` from `roic.py`.
- Produces, in `mature_growth.py`: `def solve_root(gap: Callable[[float], float], lo: float, hi: float, step: float = _SCAN_STEP, tol: float = 1e-7) -> float | None` — the scan-then-bisect of `implied_growth`, which now calls it; its behaviour is unchanged (the existing tests pass).
- Produces, in `revenue_growth.py`:
  - `@dataclass(frozen=True) class RevenueCharge: r: float; g_t: float; terminal_return: float; sales_to_capital: float` (named apart from `mature_growth.Charge`, which the cross-check still uses)
  - `@dataclass(frozen=True) class Bridge: debt: float; cash: float; shares: float`
  - `def reinvestment_by_year(revenue: Sequence[float], nopat: Sequence[float], charge: RevenueCharge) -> tuple[float, ...]` — `max(0, (revenue[t+1] − revenue[t]) ÷ sales_to_capital)` for t = 1 … N−1 and `nopat[N] × g_t ÷ terminal_return` for year N.
  - `@dataclass(frozen=True) class RevenueValuation: revenue, margins, ebit, tax, nopat, reinvestment, fcff: tuple[float, ...]; terminal_value: float; firm_value: float; equity: float; value_per_share: float`
  - `def revenue_valuation(path: RevenuePath, margin: MarginPath, tax_rate: float, charge: RevenueCharge, bridge: Bridge) -> RevenueValuation`
  - `def return_on_new_capital(target_margin: float, tax_rate: float, sales_to_capital: float) -> float` — `target × (1 − tax) × sales_to_capital`.
  - `def implied_hold_growth(target_value: float, path: RevenuePath, margin: MarginPath, tax_rate: float, charge: RevenueCharge, bridge: Bridge, lo: float = -0.5, hi: float = 2.0) -> float | None` — the `hold` at which `value_per_share` equals `target_value`.
  - `def implied_target_margin(target_value: float, path: RevenuePath, margin: MarginPath, tax_rate: float, sales_to_capital: float, moat: Moat, policy: Policy, bridge: Bridge) -> float | None` — the `MarginPath.target` at which `value_per_share` equals `target_value`, the terminal return re-read at each trial margin as `terminal_roic(return_on_new_capital(trial, tax_rate, sales_to_capital), moat, policy)`; bounds `policy.implied_margin_bounds`.
  - `def own_sales_to_capital(kept: Sequence[RoicYear], revenue_by_fiscal_year: Mapping[int, float], span: int, growth_min: float) -> tuple[float | None, bool]` — (revenue_last − revenue_first) ÷ (capital_last − capital_first) over the kept years, first = `span` positions before the newest; `(None, False)` with fewer than `span + 1` kept years, a year without a revenue, or no change in capital; usable when capital grew, by at least `growth_min × |capital_first|`, and revenue grew.
  - `@dataclass(frozen=True) class PeerFigures: symbol: str; market_cap: float | None; margin: float | None; margin_years: int; sales_to_capital: float | None; roic: float | None`
  - `@dataclass(frozen=True) class TargetMargin: value: float; count: int; low: float; high: float; largest_symbol: str | None; largest_margin: float | None; peers: tuple[PeerFigures, ...]`
  - `def target_margin(peers: Sequence[PeerFigures], policy: Policy) -> TargetMargin | None` — over the peers with a margin on at least `policy.peer_margin_min_years` years; `None` below `policy.peer_min` of them; the median, the lowest, the highest, and the largest by market cap.
  - `def peer_sales_to_capital(peers: Sequence[PeerFigures], policy: Policy) -> float | None` — the median over the peers with a positive sales-to-capital; `None` below `policy.peer_min`.
  - `def peer_roic_median(peers: Sequence[PeerFigures]) -> float | None`.

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_revenue_growth.py`:

```python
MARGIN = MarginPath(-0.10, 0.20, 10)
CHARGE = RevenueCharge(0.09, 0.03, 0.09, 2.0)
BRIDGE = Bridge(100.0, 300.0, 100.0)

def test_reinvestment_with_the_lag_and_the_terminal_year() -> None:
    v = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, BRIDGE)
    assert v.reinvestment == pytest.approx(
        (162.5, 162.5, 195.0, 234.0, 233.06, 216.09, 181.61, 130.23, 64.95, 234.89), abs=0.01)

def test_reinvestment_never_negative() -> None:
    v = revenue_valuation(replace(PATH, ntm_revenue=900.0, steps=(-0.1, -0.1)), MARGIN, 0.21, CHARGE, BRIDGE)
    assert min(v.reinvestment[:9]) == 0.0

def test_value_of_the_worked_example() -> None:
    v = revenue_valuation(PATH, MARGIN, 0.21, CHARGE, BRIDGE)
    assert v.fcff[0] == pytest.approx(-253.5, abs=0.01) and v.fcff[9] == pytest.approx(469.77, abs=0.01)
    assert v.terminal_value == pytest.approx(8064.46, abs=0.01)
    assert v.firm_value == pytest.approx(3290.57, abs=0.01)
    assert v.equity == pytest.approx(3490.57, abs=0.01)
    assert v.value_per_share == pytest.approx(34.91, abs=0.01)

def test_value_at_other_inputs() -> None:
    assert revenue_valuation(PATH, replace(MARGIN, target=0.10), 0.21, CHARGE, BRIDGE).value_per_share == pytest.approx(10.09, abs=0.01)
    assert revenue_valuation(PATH, replace(MARGIN, target=0.30), 0.21, CHARGE, BRIDGE).value_per_share == pytest.approx(59.64, abs=0.01)
    assert revenue_valuation(PATH, MARGIN, 0.21, replace(CHARGE, sales_to_capital=3.0), BRIDGE).value_per_share == pytest.approx(38.50, abs=0.01)
    assert revenue_valuation(PATH, MARGIN, 0.21, replace(CHARGE, terminal_return=0.13), BRIDGE).value_per_share == pytest.approx(40.45, abs=0.01)

def test_return_on_new_capital() -> None:
    assert return_on_new_capital(0.20, 0.21, 2.0) == pytest.approx(0.316)

def test_implied_growth_and_margin_at_the_price(policy: Policy) -> None:
    assert implied_hold_growth(25.0, PATH, MARGIN, 0.21, CHARGE, BRIDGE) == pytest.approx(0.086275, abs=1e-5)
    assert implied_target_margin(25.0, PATH, MARGIN, 0.21, 2.0, "None", policy, BRIDGE) == pytest.approx(0.160014, abs=1e-5)
    # round trips
    assert implied_hold_growth(34.9057, PATH, MARGIN, 0.21, CHARGE, BRIDGE) == pytest.approx(0.20, abs=1e-4)
    assert implied_target_margin(34.9057, PATH, MARGIN, 0.21, 2.0, "None", policy, BRIDGE) == pytest.approx(0.20, abs=1e-4)

def test_implied_margin_reads_the_terminal_from_the_trial_margin(policy: Policy) -> None:
    # Wide moat: at a 20% target the return on new capital is 31.6%, so the terminal is the 13% cap
    # and the value is 40.45; the solve at that price returns 20%.
    assert implied_target_margin(40.45, PATH, MARGIN, 0.21, 2.0, "Wide", policy, BRIDGE) == pytest.approx(0.20, abs=1e-3)

def test_negative_target_margin_values_below_zero(policy: Policy) -> None:
    charge = replace(CHARGE, terminal_return=terminal_roic(return_on_new_capital(-0.05, 0.21, 2.0), "Wide", policy))
    assert charge.terminal_return == 0.09
    assert revenue_valuation(PATH, replace(MARGIN, target=-0.05), 0.21, charge, BRIDGE).value_per_share < 0

def test_own_sales_to_capital_usability() -> None:
    def kept(caps): return [RoicYear(2017 + k, 10.0, c, None) for k, c in enumerate(caps)]
    revenue = {2017 + k: 1000.0 + 300.0 * k for k in range(6)}  # 2,500 in 2022
    s2c, usable = own_sales_to_capital(kept([400, 500, 600, 700, 800, 900]), revenue, 5, 0.20)
    assert s2c == pytest.approx(3.0) and usable
    s2c, usable = own_sales_to_capital(kept([400, 404, 408, 412, 416, 420]), revenue, 5, 0.20)
    assert s2c == pytest.approx(75.0) and not usable          # capital grew 5%
    assert own_sales_to_capital(kept([400, 500, 600, 700, 800]), revenue, 5, 0.20) == (None, False)
    falling = {y: 2000.0 - 100.0 * k for k, y in enumerate(revenue)}
    assert own_sales_to_capital(kept([400, 500, 600, 700, 800, 900]), falling, 5, 0.20)[1] is False
    assert own_sales_to_capital(kept([400, 500, 600, 700, 800, 900]), {2022: 2500.0}, 5, 0.20) == (None, False)

def test_target_margin_from_peers(policy: Policy) -> None:
    peers = [PeerFigures("A", 10e9, 0.10, 10, 2.5, 0.12), PeerFigures("B", 50e9, 0.30, 8, 1.5, 0.20),
             PeerFigures("C", 20e9, 0.20, 6, 3.0, 0.15), PeerFigures("D", 5e9, 0.40, 3, None, None)]
    t = target_margin(peers, policy)
    assert t is not None and t.value == pytest.approx(0.20) and t.count == 3
    assert (t.low, t.high) == (0.10, 0.30) and t.largest_symbol == "B" and t.largest_margin == 0.30
    assert target_margin(peers[:2], policy) is None
    assert peer_sales_to_capital(peers, policy) == pytest.approx(2.5)
    assert peer_sales_to_capital(peers[:2], policy) is None
    assert peer_roic_median(peers) == pytest.approx(0.15)
```

In `tests/engine/test_mature_growth.py` add `test_solve_root_finds_the_first_sign_change`: `solve_root(lambda x: x * x - 4, 0.0, 10.0) == pytest.approx(2.0, abs=1e-6)` and `solve_root(lambda x: x + 20, 0.0, 10.0) is None`.

- [ ] **Step 2: Run the tests to see them fail**: `uv run pytest tests/engine/test_revenue_growth.py tests/engine/test_mature_growth.py -q` — FAIL on the missing names.

- [ ] **Step 3: Factor `solve_root` out of `implied_growth`** in `mature_growth.py` (the scan from `lo` to `hi` in `step`s for the first sign change, then `_bisect`); `implied_growth` calls it with its `gap`.

- [ ] **Step 4: Implement the Interfaces block** in `revenue_growth.py`. `revenue_valuation` builds the tables in order: revenue, margins, EBIT, tax and NOPAT, reinvestment, FCFF, the terminal value `nopat[N] × (1 + g_t) × (1 − g_t ÷ terminal_return) ÷ (r − g_t)`, the firm value, equity `firm − debt + cash`, value a share. The two solves call `solve_root` on `value_per_share(trial) − target_value`; `implied_margin` steps the scan by `0.01` from the policy's lower bound. `target_margin` uses `statistics.median`.

- [ ] **Step 5: Run the tests to see them pass**: `uv run pytest tests/engine -q` — PASS, the mature route's tests untouched.

- [ ] **Step 6: Note the bounds in `docs/method.md` 4.1a**: add "the implied-growth scan of the growth routes from −50% to 200%" to the list (the implied-margin bounds are a policy value and belong to the route section of Task 8).

- [ ] **Step 7: Commit**: `git add -A && git commit -m "Value the growth routes' revenue path with sales-to-capital reinvestment and solve the growth and the margin the price needs"`.

---

### Task 4: The peers: the FMP call, its fixture, the normalizer and the peer figures

**Files:**
- Create: `src/fairband/refresh/peers.py`, `tests/refresh/test_peers.py`, `tests/fixtures/fmp/stock-peers.ACME.json`, `tests/fixtures/fmp/stock-peers.BOLT.json`
- Modify: `src/fairband/vendors/fmp.py`, `src/fairband/vendors/normalize_fmp_observations.py`, `src/fairband/refresh/fetch.py`, `src/fairband/refresh/inputs.py`, `src/fairband/refresh/run.py:418-445`, `src/fairband/engine/anchor.py:62-73`, `src/fairband/engine/route.py:88-121`
- Test: `tests/refresh/test_fetch.py`, `tests/vendors/test_normalize_fmp.py`, `tests/refresh/test_inputs.py`, `tests/refresh/test_peers.py`

**Interfaces:**
- Consumes: `PeerFigures` (Task 3); `statements_for`, `series_for` from `inputs_statements.py`; `classify`, `Deciles` from `classifier.py`; `aggregate_roic` from `roic.py`; `latest_company` from `store/companies.py`; `latest_response`, `response_payload` from `store/vendor.py`.
- Produces:
  - `Fmp.peers(self, symbol: str) -> VendorResponse` — `GET stock-peers?symbol=<fmp form>`.
  - `def peer_symbols(payload: Any, own: str) -> list[str]` in `normalize_fmp_observations.py` — the `symbol` of each object of the list, in the exchange form (the dash-to-dot rule `screener_rows` applies), `own` and repeats dropped; empty when the payload is not a list of objects.
  - The fetch's fifteenth call: endpoint `"peers"`, params `{"symbol": symbol}`, no normalized rows, usable when `peer_symbols` gives one symbol or more (an empty list is stored and reused like any usable payload: a company with no peers has no peers). Not in `REQUIRED`.
  - `def peer_figures(conn, symbol: str, deciles: Deciles | None, policy: Policy, tax: TaxTable, today: date) -> tuple[PeerFigures, ...]` in `refresh/peers.py` — from the latest stored `peers` payload: each symbol with an eligible universe row (`latest_company(conn, s)` with `eligible`), classified from `series_for(conn, s)` with `deciles` into Mature Growth or Mature Stable; its `margin` the ten-year aggregate operating margin over its last ten fiscal years with revenue and operating income, `margin_years` their count; its `sales_to_capital` the last fiscal year's revenue ÷ the newest kept ROIC year's average capital (`aggregate_roic(statements_for(...).capital_years).by_year[-1]`), `None` when that capital is not positive or there is no kept year; its `roic` the ten-year aggregate; `market_cap` the universe row's. Empty with no deciles, no stored payload, or no peers.
  - `CompanyInputs` gains `peers: tuple[PeerFigures, ...] = ()`, `debt: float | None = None`, `cash: float | None = None`; `AnnualEstimate` gains `analysts_revenue: int | None = None` (last field, defaulted, so every existing builder still works).
  - `build_inputs(conn, symbol, policy, tax, today, deciles: Deciles | None = None)` fills them: `peers` from `peer_figures`; `debt` = the newest annual balance sheet's `shortTermDebt` + `longTermDebt` (a missing line nil, both missing `None`, and a missing one named in `notes["debt"]`); `cash` = `cashAndCashEquivalents` + `shortTermInvestments` the same way; `analysts_revenue` from the `analysts_revenue` observation.
  - `Refresh._value_stage` and `_revalue` pass `deciles` to `build_inputs`.

- [ ] **Step 1: Write the fixtures**: `stock-peers.ACME.json` as FMP's shape, `[{"symbol": "BOLT", "companyName": "Bolt Corp", "price": 20.0, "mktCap": 3000000000}, {"symbol": "ACME", ...}, {"symbol": "ZZZZ", ...}]` (itself and an unknown symbol among them); `stock-peers.BOLT.json` with `[{"symbol": "ACME", ...}]`.

- [ ] **Step 2: Write the failing tests**:

In `tests/vendors/test_normalize_fmp.py`:

```python
def test_peer_symbols_drop_self_and_repeats_and_use_the_exchange_form() -> None:
    payload = [{"symbol": "BRK-B"}, {"symbol": "ACME"}, {"symbol": "BOLT"}, {"symbol": "BOLT"}, {"x": 1}]
    assert peer_symbols(payload, "ACME") == ["BRK.B", "BOLT"]
    assert peer_symbols({"symbol": "X"}, "ACME") == [] and peer_symbols("no", "ACME") == []
```

In `tests/refresh/test_fetch.py`: add `"peers"` to `FMP_ENDPOINTS` after `"earnings"`, change `calls=14` to `calls=15` and `count(conn, "vendor_responses") == 14` to `15`; add

```python
def test_peers_payload_is_stored_and_not_required(conn, clients, router, clock, policy) -> None:
    router.fail.add("peers")
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == ("peers",) and outcome.error is None
```

In `tests/refresh/test_peers.py`, with a store holding ACME and BOLT fetched (the `env_fixture_universe` or the `conn_with_company` pattern of `test_inputs.py`; BOLT must be a universe row and Mature Growth or Mature Stable on the test deciles):

```python
def test_peers_keep_only_mature_universe_companies(...) -> None:
    figures = peer_figures(conn, "ACME", deciles, policy, tax, today)
    assert [p.symbol for p in figures] == ["BOLT"]          # not ACME itself, not ZZZZ
    bolt = figures[0]
    assert bolt.margin == pytest.approx(<BOLT's Σ operating income ÷ Σ revenue over its years>) and bolt.margin_years == <n>
    assert bolt.sales_to_capital == pytest.approx(<BOLT's last revenue ÷ newest average capital>)
    assert bolt.roic == pytest.approx(<BOLT's aggregate>) and bolt.market_cap == <BOLT's universe cap>

def test_no_peers_without_deciles_or_payload(...) -> None:
    assert peer_figures(conn, "ACME", None, policy, tax, today) == ()
    assert peer_figures(conn, "NOPE", deciles, policy, tax, today) == ()
```

(fill the brackets from the BOLT fixture's figures; compute them in the test from the fixture rows rather than hard-coding, as `test_inputs.py` does for ACME).

In `tests/refresh/test_inputs.py`:

```python
def test_inputs_carry_peers_debt_cash_and_the_revenue_analysts(conn_with_company, deciles, ...) -> None:
    i = build_inputs(conn, "ACME", policy, tax, today, deciles)
    assert i.debt == pytest.approx(<ACME's shortTermDebt + longTermDebt, newest year>)
    assert i.cash == pytest.approx(<cash + shortTermInvestments>)
    assert i.annual_estimates[0].analysts_revenue == <the fixture's numAnalystsRevenue>
    assert build_inputs(conn, "ACME", policy, tax, today).peers == ()   # no deciles: no peers
```

- [ ] **Step 3: Run the tests to see them fail**: `uv run pytest tests/vendors/test_normalize_fmp.py tests/refresh/test_fetch.py tests/refresh/test_peers.py tests/refresh/test_inputs.py -q` — FAIL on the missing names and the call count.

- [ ] **Step 4: Implement**: `Fmp.peers`; `peer_symbols`; the `_Call` in `fetch._calls` after `earnings` (`on_fmp("peers", {}, partial(fmp.peers, symbol))`) and the `_rows` case `"peers": return ([], []) if peer_symbols(payload, symbol) or payload == [] else None` (an empty list is usable; a non-list is not); `refresh/peers.py` with `peer_figures` and a module docstring stating the filter and the three figures; the `CompanyInputs` and `AnnualEstimate` fields; `build_inputs` reading the newest annual balance sheet through `inputs_statements` (add a small `balance_lines(conn, symbol) -> dict[str, float | None]` there if `statements_for` does not expose the newest sheet) and the `analysts_revenue` observation; `run.py` passing `deciles` in `_value_stage` (it already holds `deciles`) and in `_revalue`'s path to the value stage. `vendor_double._FMP_ENDPOINTS` maps `stock-peers` to `peers` if the router needs it (check `_resolve`).

- [ ] **Step 5: Run the whole suite**: `uv run pytest -q` — PASS (the snapshot JSON round-trip tests must still pass with the new `CompanyInputs` fields, which are not stored).

- [ ] **Step 6: Commit**: `git add -A && git commit -m "Fetch each company's FMP peers and build the mature peers' margin, sales-to-capital and ROIC into the engine's inputs"`.

---

### Task 5: The route

**Files:**
- Create: `src/fairband/engine/route_revenue_growth.py`, `tests/engine/test_route_revenue_growth.py`
- Modify: `src/fairband/engine/route.py`, `src/fairband/engine/types.py:21`, `src/fairband/engine/route_steps.py` (if a shared helper is needed), `tests/support/engine_companies.py`, `docs/method.md` (sections 5.1 and 10)
- Test: `tests/engine/test_route_revenue_growth.py`, `tests/engine/test_route.py`, `tests/refresh/test_run_price.py`, `tests/engine/test_types.py` (the route literal)

**Interfaces:**
- Consumes: everything of Tasks 2 to 4; `Context`, `Valued`, `Refused`, `common_inputs`, `common_rules`, `data`, `rule`, `present`, `trailing_flags`, `income`, `expected`, `multiples_at`, `price_facts_for`, `eps`, `nri_gap` from `route_steps.py`; `ntm_quarters`, `base_fiscal_year`, `moat_class` from `anchor.py`; `RoicTerms` for the capital build's flags and the kept years; `growth_cross_check`, `cross_check_at_price` from `route_mature_growth.py`; `value_spread_flag` from `flags.py`.
- Produces:
  - `Route = Literal["mature-growth", "mature-stable", "revenue-growth"]`.
  - `def value_revenue_growth(c: Context, phase: Phase) -> Valued | Refused` — `phase` is `"High Growth"` or `"Young Growth"`; the refusal order of spec 5.2; a refusal for the target margin carries the intermediates of spec 5.11's rebuild keys and `implied_margin`.
  - `def revenue_at_price(im: dict[str, Any], price: float, value: float, policy: Policy) -> dict[str, Any]` — `implied_growth`, `implied_margin`, `multiples`, `growth_share`, `expected_return`, and `growth_route` repriced through `cross_check_at_price` when present.
  - `def implied_margin_at_price(im: dict[str, Any], price: float, policy: Policy) -> dict[str, Any]` — `{"implied_margin": …}` for a refused row, rebuilt from `im["revenue_path"]`, `im["margin_start"]`, `im["tax_rate"]`, `im["sales_to_capital"]["value"]`, `im["moat"]`, `im["debt"]`, `im["cash"]`, `im["shares"]`.
  - `route.value_company` dispatches `"High Growth"` and `"Young Growth"` to `value_revenue_growth`; `reprice` handles `route == "revenue-growth"` with `revenue_at_price`, and a refused result whose intermediates hold `"revenue_path"` with `implied_margin_at_price`.
  - Intermediates and inputs: exactly spec 5.15, with `revenue_path` = `{"revenue0", "ntm_revenue", "steps", "hold": None, "high_growth_years", "fade_years"}`, `margin_start`, `tax_rate`, `moat`, `debt`, `cash`, `shares` as the rebuild keys, and `path_steps` = `[g_2, g_3]` resolved with `path["held"] = [bool, bool]`.
  - Flags, new: `path-held` ("Path held": "The consensus has no revenue for fiscal <year>, so year <t> holds the <rate>% of the year before."), `tax-loss-history-unknown` ("Tax losses unknown": "The forecast carries its own losses forward from zero; losses before it are not stored, so taxes may start too early."), `return-above-peers` ("Return above peers": "The return on new capital at the target margin, <x>%, is above the mature peers' median return of <y>%; the sales-to-capital may be too high (Damodaran's check)."), `failure-not-charged` ("Failure not charged": "No survival table fits a listed company above $2 billion, so the failure probability is unavailable and the value is the going-concern value."). Order: spec 5.14.
  - Test companies in `engine_companies.py`: `high_growth_inputs()` (negative margin improving; the revenue series and estimates giving the spec's worked path is not required, but the quarters carry revenue means and the annual rows revenue with `analysts_revenue`; `peers` three `PeerFigures` with margins 0.10, 0.20, 0.30, sales-to-capital 2.5, 1.5, 3.0 and ROIC 0.12, 0.20, 0.15; `debt`, `cash`), and `young_growth_inputs()` extended the same way.

- [ ] **Step 1: Write the failing tests** in `tests/engine/test_route_revenue_growth.py`:

```python
def test_high_growth_is_valued_on_the_revenue_route(high_growth_inputs, deciles, policy) -> None:
    r = value_company(high_growth_inputs, deciles, policy, TODAY)
    assert r.route == "revenue-growth" and r.value is not None and r.levels is not None
    im = r.intermediates
    assert len(im["revenue_by_year"]) == 10 and len(im["margin_path"]["by_year"]) == 10
    assert im["target_margin"]["value"] == pytest.approx(0.20) and im["target_margin"]["count"] == 3
    assert im["sales_to_capital"]["used"] in ("own", "peers")
    assert im["value_by_margin"].keys() == {"low", "median", "high"}
    assert im["implied_growth"] is not None and im["implied_margin"] is not None
    assert r.phase.phase == "High Growth"
    assert "failure-not-charged" not in [f.code for f in r.flags]

def test_young_growth_values_like_high_growth_and_is_flagged(young_growth_inputs, high_growth_inputs, deciles, policy) -> None:
    same = replace(young_growth_inputs, series=high_growth_inputs.series, capital_years=high_growth_inputs.capital_years)
    # same inputs, the phase apart: identical value
    ...
    r = value_company(young_growth_inputs, deciles, policy, TODAY)
    assert r.route == "revenue-growth"
    assert [f.code for f in r.flags if f.code == "failure-not-charged"] == ["failure-not-charged"]
    assert r.intermediates["failure_probability"] == {"value": None, "reason": "no survival table fits a listed company above $2 billion"}

def test_refusal_order(high_growth_inputs, deciles, policy) -> None:
    assert_refused(value_company(replace(high_growth_inputs, trailing=replace(..., revenue=None)), ...), "no trailing revenue")
    assert_refused(..., tax_rate_latest=None ..., "no statutory tax rate")
    assert_refused(... quarter_estimates=() ..., "incomplete NTM consensus")
    assert_refused(... a quarter with revenue=None ..., "incomplete NTM consensus")
    r = value_company(replace(high_growth_inputs, peers=high_growth_inputs.peers[:2]), deciles, policy, TODAY)
    assert_refused(r, "no target margin: 2 mature peers")
    assert r.intermediates["implied_margin"] is not None and "revenue_path" in r.intermediates
    no_s2c = replace(high_growth_inputs, peers=(), capital_years=high_growth_inputs.capital_years[:3])
    assert_refused(value_company(no_s2c, ...), "no target margin: 0 mature peers")   # the margin refuses first

def test_no_sales_to_capital_refuses(high_growth_inputs, deciles, policy) -> None:
    peers = tuple(replace(p, sales_to_capital=None) for p in high_growth_inputs.peers)
    short = replace(high_growth_inputs, peers=peers, capital_years=high_growth_inputs.capital_years[-4:])
    assert_refused(value_company(short, deciles, policy, TODAY), "no sales-to-capital")

def test_path_held_flag_and_few_analysts(high_growth_inputs, deciles, policy) -> None:
    ...annual estimates with the third year missing → "path-held"; a year with analysts_revenue=3 → "few-analysts"

def test_return_above_peers_flag(high_growth_inputs, deciles, policy) -> None:
    ...peers' ROIC median 0.15 and a return on new capital above it → the flag with both figures in its sentence;
    ...peers' ROIC median raised above it → no flag

def test_tax_loss_flag_and_the_bridge(high_growth_inputs, deciles, policy) -> None:
    ...a forecast with a loss year → "tax-loss-history-unknown"; debt or cash None → "line-not-presented:debt" / "...:cash" and nil

def test_cross_check_present_with_a_positive_anchor(high_growth_inputs, deciles, policy) -> None:
    ...quarter EPS means positive → im["growth_route"]["value_per_share"] is not None; EPS means negative → im["growth_route"] == {"refusal": "no positive forward anchor"}

def test_value_spread_flag_over_the_margins(...)
def test_determinism_and_json_round_trip(...)    # value twice, intermediates equal; result_to_json round-trips

def test_reprice_moves_every_price_side_figure(high_growth_inputs, deciles, policy) -> None:
    r = value_company(...); r2 = reprice(r, r.price * 0.5, date(2026, 11, 2), policy)
    assert r2.value == r.value and r2.intermediates["implied_growth"] != r.intermediates["implied_growth"]
    assert r2.intermediates["implied_margin"] != r.intermediates["implied_margin"]
    assert r2.intermediates["revenue_by_year"] == r.intermediates["revenue_by_year"]

def test_reprice_moves_the_implied_margin_on_a_refused_row(high_growth_inputs, deciles, policy) -> None:
    r = value_company(replace(high_growth_inputs, peers=()), deciles, policy, TODAY)
    r2 = reprice(r, r.price * 0.5, date(2026, 11, 2), policy)
    assert r2.refusal == r.refusal and r2.value is None and r2.route is None
    assert r2.intermediates["implied_margin"] < r.intermediates["implied_margin"]
    plain = value_company(replace(high_growth_inputs, trailing=None), deciles, policy, TODAY)
    assert reprice(plain, 10.0, date(2026, 11, 2), policy).intermediates == plain.intermediates
```

In `tests/engine/test_route.py`: `test_refuses_other_phases` now needs a Decline company (`decline_inputs()`: revenue falling 5% a year, positive margin) and asserts `"Decline route not built yet"`; the young-growth assertions in `test_result_json_round_trip` (line 1140) read the valued result. In `tests/refresh/test_run_price.py`, `test_price_refresh_copies_refused_rows` stays true for a plain refusal; add nothing else unless the fixture universe holds a growth company.

- [ ] **Step 2: Run the tests to see them fail**: `uv run pytest tests/engine/test_route_revenue_growth.py tests/engine/test_route.py -q` — FAIL on the dispatch and the missing module.

- [ ] **Step 3: Write `route_revenue_growth.py`** with the module docstring in the style of `route_mature_growth.py` (what the route reads, the refusal order, the intermediates, the rebuild keys), `value_revenue_growth`, `revenue_at_price`, `implied_margin_at_price` and the private helpers: `_ntm_revenue` (the anchor's quarters, each needing a revenue mean), `_path` (the base year, the steps on revenue, `resolved_steps`, the analysts on `analysts_revenue`), `_sales_to_capital` (own over `RoicTerms.of(...).result.by_year` with the series' revenues by fiscal year, else `peer_sales_to_capital`), the terminal through `terminal_roic(return_on_new_capital(...), moat, policy)`, the charge, the bridge with the nil-and-flag rule, the valuation, `value_by_margin` at `target.low`, `target.value`, `target.high`, the flags in spec 5.14's order, and the refusal for the target margin carrying `implied_margin` and the rebuild keys. The Young Growth difference: `im["failure_probability"]` and the flag when `phase == "Young Growth"`; on a High Growth row the key is absent.

- [ ] **Step 4: Dispatch and reprice in `route.py`**: the phase guard becomes `if phase.phase not in ("Mature Growth", "Mature Stable", "High Growth", "Young Growth")`; the outcome call picks the route by phase; `reprice` gains the two branches; the module docstring's intermediates list gains the route's keys and the refusal exception. `Route` in `types.py`. The test companies in `engine_companies.py`.

- [ ] **Step 5: Run the whole suite**: `uv run pytest -q` — PASS.

- [ ] **Step 6: Update `docs/method.md`**: section 5.1's guard sentence names the two new phases as routed; section 7's table loses High Growth and Young Growth; section 10's price-refresh paragraph gains "a refusal snapshot takes only the new price and date, except a growth-route row refused for its target margin, whose margin the price needs is recomputed"; the route section itself is Task 8.

- [ ] **Step 7: Commit**: `git add -A && git commit -m "Value High Growth and Young Growth rows on the revenue route, with the peers' target margin, the flags and the price-implied figures"`.

---

### Task 6: The screen: columns, the drawer and the route name

**Files:**
- Modify: `src/fairband/web/rows.py`, `src/fairband/web/static/design-system/components/bundle.js` (the column catalog, `// fairband:` marked), `src/fairband/web/static/app.js` (ROUTES, the drawer), `src/fairband/web/static/design-system/components/index.d.ts` (the two keys)
- Test: `tests/web/test_app.py`, `tests/web/test_groups.py` (if it pins the column list)

**Interfaces:**
- Produces: row keys `targetMargin` (the target margin or `None`) and `impliedMargin` (the margin the price needs or `None`), after `growthRouteValue` in `EXTRA_KEYS`; `growthRouteValue` filled on `revenue-growth` rows from `intermediates["growth_route"]["value_per_share"]`; two catalog entries `targetMargin` ("Target margin", percent) and `impliedMargin` ("Implied margin", percent) after `growthRouteValue`; `ROUTES['revenue-growth'] = 'Revenue growth route'`; the drawer shows, for a `revenue-growth` row, the ten-year table (year, revenue, margin, EBIT, tax, NOPAT, reinvestment, free cash flow), the peers (symbol, margin, market cap) with the median and the largest, the sales-to-capital measure, the terminal, the bridge (firm value, debt, cash, equity, shares) and the solves; one caption line on every row of the route, "Discounted at the required return of 9.0% in every year; Damodaran's template starts higher and falls to it by year 10" (spec 5.9); on a Young Growth row the `failure_probability` line with its reason and "The value range is not computed in tier 1" (spec 5.13); a row refused for the target margin shows "Margin the price needs: x%".

- [ ] **Step 1: Write the failing tests** in `tests/web/test_app.py`:

```python
def test_growth_route_columns(client: TestClient) -> None:
    body = client.get("/api/screen").json()
    assert "targetMargin" in body["columns"] and "impliedMargin" in body["columns"]
    row = next(r for r in body["rows"] if r["route"] == "revenue-growth")
    assert row["targetMargin"] == pytest.approx(0.20) and row["impliedMargin"] is not None
    assert row["growthRouteValue"] == row_of_the_cross_check_or_None

def test_bundle_has_the_margin_columns() -> None:
    bundle = _component_file("bundle.js")
    assert "key: 'targetMargin'" in bundle and "key: 'impliedMargin'" in bundle

def test_app_js_names_the_revenue_route_and_draws_its_tables() -> None:
    script = _static_file("app.js")
    assert "'revenue-growth': 'Revenue growth route'" in script
    for key in ("revenue_by_year", "reinvestment_by_year", "fcff_by_year", "target_margin", "sales_to_capital", "failure_probability", "implied_margin"):
        assert key in script, key
    assert "Discounted at the required return of" in script
    assert "The value range is not computed in tier 1" in script
```

The web conftest's `results` fixture must value `high_growth_inputs()` beside the three companies (add it to the fixture that builds the store), so `test_growth_route_columns` finds a row; update `test_bundle_patches_marked`'s count (19 + the new patches) and `test_bundle_has_extra_columns` if it lists the keys.

- [ ] **Step 2: Run the tests to see them fail**: `uv run pytest tests/web -q` — FAIL on the keys and the strings.

- [ ] **Step 3: Implement**: `rows.py` (`EXTRA_KEYS`, `screen_row` reading `_table(intermediates, "target_margin").get("value")` and `intermediates.get("implied_margin")`, `growth_route_value` for the new route); the bundle's two catalog entries with the percent format the other percentage columns use, each marked; `index.d.ts`; `app.js`'s `ROUTES` and the drawer section, laid out with the design system's table and caption classes as the growth route's section is.

- [ ] **Step 4: Run the tests to see them pass**: `uv run pytest tests/web -q` — PASS.

- [ ] **Step 5: Commit**: `git add -A && git commit -m "Show the growth routes' target margin and the margin the price needs on the screen and the drawer"`.

---

### Task 7: The four screen fixes

**Files:**
- Modify: `src/fairband/web/static/controls.js`, `src/fairband/web/static/design-system/components/bundle.js:1036-1250` (marked patches), `src/fairband/web/static/index.html` (the page's `<style>`)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Produces, in `controls.js`: `lastLine(last)` returns one line `[<kind> <status> , <time element>, ' · <valued> of <total> valued', ' · <n> failed' when n > 0, <Details ▾ control>]`; `detailsMenu(c)` renders `div.fb-screen__cols` holding `F.Button` `Details ▾` (`aria-expanded`) and, while `state.detailsOpen`, a `div.fb-menu` with three `fb-menu__sec` sections: `FLAGGED` (one line, `<n> flagged by a classifier check`), `PHASES` (one row per phase in phase order with its count, `unclassified` last, zero counts left out) and `REFUSED` (one row per reason with its count, largest first; `none` when empty); a document `pointerdown` outside the wrapper and a `keydown` Escape set `state.detailsOpen = false`. `calibrationLine` is removed.
- Produces, in the bundle's `ScreenTable`: a `React.useEffect` that, while `open[0] || fopen[0]`, listens for `pointerdown` on `document` and closes both when the event target is outside every `.fb-screen__cols` element of the table, and for `keydown` `Escape`, which closes both; `Filters ▾`'s `onClick` sets `open` false as it toggles `fopen`, and `Columns ▾`'s the reverse; the FIND field gains, when `p.query`, a `button.fb-screen__clear control` with the text `Clear` and `onClick: function () { p.onQueryChange(''); }` inside `.fb-screen__find`, after the input. Each a `// fairband:` patch.
- Produces, in `index.html`: a rule under the page's styles, `/* fairband: the FIND field's focus ring (2px, offset 1px) was clipped by the scroll container's top edge */ .app-main { padding-top: var(--space-1); }`, or the smallest equivalent the implementer confirms in a browser removes the clipping (the `run` skill starts the app; press Tab to the field).

- [ ] **Step 1: Write the failing tests** in `tests/web/test_app.py`:

```python
def test_controls_js_one_line_status_and_details_menu() -> None:
    script = _static_file("controls.js")
    assert "calibrationLine" not in script
    assert "' of '" in script and "' valued'" in script and "' failed'" in script
    assert "'Details ▾'" in script and "state.detailsOpen" in script
    for section in ("'FLAGGED'", "'PHASES'", "'REFUSED'"):
        assert section in script, section
    assert "'pointerdown'" in script and "'Escape'" in script

def test_bundle_menus_close_on_outside_click_and_escape() -> None:
    bundle = _component_file("bundle.js")
    assert "document.addEventListener('pointerdown'" in bundle
    assert "e.key === 'Escape'" in bundle
    assert "fopen[1](!fopen[0]); open[1](false);" in bundle
    assert "open[1](!open[0]); fopen[1](false);" in bundle

def test_bundle_find_has_a_clear_word() -> None:
    bundle = _component_file("bundle.js")
    assert "p.query ? h('button', { type: 'button', className: 'fb-screen__clear control'" in bundle
    assert "onClick: function () { p.onQueryChange(''); }" in bundle

def test_index_gives_the_find_ring_room() -> None:
    page = _static_file("index.html")
    assert "/* fairband:" in page and ".app-main { padding-top: var(--space-1); }" in page
```

Raise `test_bundle_patches_marked`'s floor by the number of new patches (three in the bundle).

- [ ] **Step 2: Run the tests to see them fail**: `uv run pytest tests/web -q` — FAIL on the strings.

- [ ] **Step 3: Implement the status line and the popover** in `controls.js`: `lastLine` as the Interfaces block says, reading `last.calibration.valued`, `.total` and the `failed` count the price refresh's calibration carries; `detailsMenu` with the three sections; the listeners added in `render` once (guard with a flag) and reading `state.detailsOpen`. The time element and `localIso` stay as today.

- [ ] **Step 4: Patch the bundle**: the `useEffect` after the `over` state; the two `onClick` changes; the `Clear` button. Keep each patch's comment to one line naming the spec section.

- [ ] **Step 5: Add the page style** in `index.html` and confirm it in a browser (`run` skill; Tab to FIND; the ring shows on four sides). If the clipping has another cause, fix that cause instead and change the test's string to match; say so in the commit message.

- [ ] **Step 6: Run the tests to see them pass**: `uv run pytest tests/web -q` — PASS.

- [ ] **Step 7: Commit**: `git add -A && git commit -m "Show one status line with a details menu, close the menus on an outside click or Escape, add Clear to FIND and give its focus ring room"`.

---

### Task 8: The method document, the full refresh and the readout

**Files:**
- Modify: `docs/method.md`
- Run: the full refresh on the founder's database, then the readout

**Interfaces:**
- Consumes: the route as built (Task 5), the policy (Task 1).
- Produces: `docs/method.md` section 5a, "The revenue-growth route (High Growth and Young Growth)", between sections 5 and 6, with subsections mirroring section 5's: which rows and the refusal order; year 1 and the path; years 4 to 10; the margin path and the target margin; sales-to-capital and reinvestment; tax and NOPAT; the free cash flow, the terminal and the firm value; the required return; equity and the value a share; what moves with the price; the sensitivities, the cross-check and the implied-return check; Young Growth; the flags; the intermediates and inputs; the worked numbers of spec section 8. Section 8's flag table gains the four new codes; section 9 the three new refusals; section 12 the growth routes' sources; section 13 the glossary terms "sales-to-capital", "margin the price needs", "return on new capital at the target". The 0.4 row of section 11 names the section.

- [ ] **Step 1: Write section 5a and the catalog rows** from the code of Tasks 2 to 5, not from the spec: every sentence must describe what runs. Keep the spec's section numbers out; cite method.md's own.

- [ ] **Step 2: Check the document against the code**: dispatch a fresh subagent with the prompt of the 2026-11-02 review (every formula, order, threshold, flag code and refusal string against `src/fairband/engine/revenue_growth.py`, `route_revenue_growth.py`, `route.py`, `refresh/peers.py`, `refresh/inputs.py`, `refresh/universe.py`, the policy v3 file). Fix what it finds.

- [ ] **Step 3: Commit**: `git add docs/method.md && git commit -m "State the revenue-growth route in the method document"`.

- [ ] **Step 4: Run the checks and merge**: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`; merge the branch to `main` as the founder directs.

- [ ] **Step 5: The full refresh** on the founder's database (`~/.local/share/fairband/fairband.db`, backed up first as `fairband-before-v4-<date>.db`): `uv run python -m fairband refresh --kind full` or the page's `Refresh all`. The peers call is new; every other endpoint is reused within 24 hours of its last fetch, else fetched again.

- [ ] **Step 6: The readout**, written for the founder (spec section 10, item 3): over the High Growth and the Young Growth rows, the counts valued and refused by reason; the median value ÷ price and the share at or above price per phase; the count flagged `return-above-peers`; the peer-count distribution (how many rows had 0, 1, 2, 3 or more mature peers); the universe's `name pattern` count; and five named rows with their value, price and the peers used. No row's figure is changed by hand.
