# The Start-up and Decline routes: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Value Decline rows on Damodaran's run-off DCF with a distress weighting, a net-current-asset floor and the distress signals, and give Start-up rows the revenue the price needs, the cash floor and the burn cover. Method 0.7 on policy v5.

**Architecture:** Six statement lines join the facts, backfilled from the stored payloads before every valuing refresh. A `distress.py` (rating, π, Altman Z″, Piotroski F, NCAV) and a `runoff.py` core (the shrinking path, the capital release, the terminal, the floor and the weighting) feed `route_decline.py`; a `requirement.py` core (the straight ramp and the bisection) feeds `route_start_up.py`. Both routes hang off `route.py`'s dispatch and `reprice`. Every task updates `docs/method.md` in the same commit.

**Tech Stack:** Python 3.13, uv, SQLite; plain JS for the drawer.

**Spec:** `docs/superpowers/specs/2026-11-03-classifier-designation-ends-design.md` (sections 9, 10, 11, 13.1, 13.2, 14, 15, 16). Builds on `2026-11-03-limiter-classifier-designation.md` (policy v5 with the routes' values, method 0.6, the designation).

## Global Constraints

- The constraints of the first plan (keys, vendor data, the method document in the same commit, determinism, policy values with sources, the commit style, the checks before every commit).
- This plan ends at `fairband-mechanical/0.7`; policy stays v5 (every value the routes read is there).
- A refusal is a result with no value and a reason, never an exception; a Start-up row's refusal keeps its figures.
- The distress weighting never raises a value; the floor and the weighting are applied in the order of spec 10.6 and 10.7.
- The peers, the target margin and the industry fallback are 5a.4's; sales-to-capital's peer median is 5a.5's; tax and NOPAT are 5a.6's; debt and cash are 5a.9's.
- Structural constants in code (method 4.1a): the Z″ coefficients, the nine Piotroski signals, the requirement's bisection bounds (0 to 1e13) and tolerance (1e-9 relative), the implied-decline scan (−50% to 0 in steps of 0.1% to 1e-7).

## Review Focus

1. FMP signs `interestExpense` either way across companies: the trailing interest is summed as its size (`abs`) per quarter, never netted (Task 1's `test_interest_expense_is_summed_as_its_size`).
2. A Decline row whose trailing figures fall back to the fiscal year (fewer than four consecutive quarters): the coverage and the burn read the annual lines, and the route still runs (Task 4's `test_a_fiscal_year_fallback_still_rates_the_company`).
3. A collapsed last fiscal revenue makes d very negative (−80%): the terminal denominator `r − d` is large, the path shrinks to near zero, and no division by zero or overflow occurs (Task 3's `test_a_steep_decline_rate_still_values`).
4. A Decline row with `totalLiabilities` missing: no floor is applied and the flag `line-not-presented:totalLiabilities` is raised, never a floor on a nil liability (Task 4's `test_a_missing_total_liabilities_line_applies_no_floor`).
5. A Start-up row whose market cap is missing from the quote and the profile: the requirement's reason is "no market cap" and the cash floor still shows (Task 5's `test_no_market_cap_gives_the_reason_and_keeps_the_floor`).

---

### Task 1: The six statement lines, the trailing figures, the balance years and the backfill

**Files:**
- Modify: `src/fairband/vendors/normalize_fmp_statements.py:38-81` (`_INCOME`, `_BALANCE`, `_CASHFLOW`)
- Create: `src/fairband/refresh/backfill.py`
- Modify: `src/fairband/store/vendor.py` (a query over stored statement responses), `src/fairband/store/facts.py` (the fields already stored for a response)
- Modify: `src/fairband/refresh/run.py` (`_full` at line 237, `_scoped` at 278, `_revalue` at 292: a `backfill` stage before `_value_stage`)
- Modify: `src/fairband/engine/anchor.py:78-94` (`TrailingFigures`), `src/fairband/refresh/inputs_statements.py` (`_trailing` at 349, `Statements` at 106, a `_balance_years` beside `_capital_years` at 309), `src/fairband/engine/route.py:114-165` (`CompanyInputs.balance_years`), `src/fairband/refresh/inputs.py` (pass it)
- Modify: `docs/method.md` sections 2, 4.2, 10
- Test: `tests/vendors/test_normalize_fmp.py`, `tests/refresh/test_backfill.py` (new), `tests/refresh/test_run_revalue.py`, `tests/refresh/test_run_full.py`, `tests/refresh/test_run_price.py`, `tests/refresh/test_inputs.py`

**Interfaces:**
- Produces: the facts `grossProfit`, `interestExpense` (income, annual and quarter), `totalAssets`, `totalLiabilities`, `retainedEarnings` (balance), `depreciationAndAmortization` (cash flow, annual and quarter); `backfill_statement_facts(conn: sqlite3.Connection, now: datetime) -> int` (the facts written; idempotent); `Refresh._backfill(conn, refresh_id)` reporting a stage `"backfill"`; `TrailingFigures.interest_expense: float | None` (the sum of the sizes) and `TrailingFigures.depreciation: float | None`; `BalanceYear(year: int, period_end: date, total_current_assets, total_current_liabilities, total_assets, total_liabilities, retained_earnings, equity, long_term_debt, revenue, gross_profit, operating_income, net_income, cfo, stock_issued: float | None ...)` frozen, one per fiscal year of the series that has an annual balance sheet, oldest first; `Statements.balance_years` and `CompanyInputs.balance_years: tuple[BalanceYear, ...] = ()`.

- [ ] **Step 1: Write the failing tests**

`test_normalize_fmp.py`: a hand-trimmed income, balance and cash-flow payload each gain the new facts. `test_backfill.py`: a stored response of each statement kind (inserted through `record_response` with a synthetic payload, its facts inserted without the new fields) gains exactly the six facts on the first run and nothing on the second; a response with an error or no payload is skipped; the facts cite the response id. `test_run_revalue.py`, `test_run_full.py`: the stage `backfill` is reported before `value`, and a full refresh that reuses a response from before the change values the company with `interest_expense` set; `test_run_price.py`: no backfill stage. `test_inputs.py`: `trailing.interest_expense` sums four quarters as sizes (`test_interest_expense_is_summed_as_its_size`: quarters of −5, 5, −5, 5 give 20); `balance_years` has one row per fiscal year with a balance sheet and the lines by name.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/vendors/test_normalize_fmp.py tests/refresh -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

The backfill: `responses_with_payload(conn, endpoints: Sequence[str]) -> Iterator[tuple[int, str, str, datetime, str]]` (id, endpoint, symbol, observed_at, payload) over `http_status = 200 AND error IS NULL AND payload IS NOT NULL`; `fields_stored(conn, response_id) -> set[str]`; for each response, `statement_facts(payload, symbol, endpoint, response_id, observed, now)` filtered to the new fields not yet stored, inserted in one transaction per response. Log the total at INFO. `run.py`: `self._stage(conn, refresh_id, "backfill", 0)` then the call, in `_full` (after the deciles, before the value stage), `_scoped` and `_revalue`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md`**

Section 2's table: the six lines in the statement rows; 4.2: the two trailing figures; section 10: "Every refresh that values (full, scoped, revalue) first backfills the facts of lines added since the payloads were stored, reading the stored responses; a price refresh does not."

- [ ] **Step 6: Commit**

```bash
git add src/fairband tests docs/method.md
git commit -m "Keep six more statement lines as facts, backfill them from the stored payloads before valuing, and carry them to the inputs"
```

### Task 2: The distress module: the rating, π, Altman Z″, Piotroski F and NCAV

**Files:**
- Create: `src/fairband/engine/distress.py`
- Test: `tests/engine/test_distress.py`

**Interfaces:**
- Consumes: `Policy.synthetic_rating`, `Policy.default_probability_10y`, `Policy.z_distress`, `Policy.z_safe`; `BalanceYear` (Task 1).
- Produces:
  - `Rating(rating: str, coverage: float | None, pi: float, note: str | None)` and `rate(ebit: float, interest: float | None, debt: float, cash: float, policy: Policy) -> Rating | None`: `None` when the company has net debt and `interest` is `None` or 0 (π unavailable); `Rating("—", None, 0.0, "no net debt")` when `cash >= debt`; else coverage `ebit / interest`, the lowest row (`D`) when `ebit <= 0`, else the last `synthetic_rating` row whose `coverage_min <= coverage`; `pi = default_probability_10y[rating]`.
  - `ZScore(x1, x2, x3, x4: float, score: float, zone: Literal["distress", "grey", "safe"])` and `altman_z(y: BalanceYear, policy: Policy) -> ZScore | None` (`None` when any of total assets, total liabilities, current assets, current liabilities, retained earnings, equity or operating income is missing, or total assets or total liabilities is at or below zero); `6.56·x1 + 3.26·x2 + 6.72·x3 + 1.05·x4`; zone by `z_distress` and `z_safe` (below the first "distress", above the second "safe", else "grey").
  - `FScore(signals: tuple[tuple[str, bool | None], ...], score: int, read: int)` and `piotroski_f(this: BalanceYear, last: BalanceYear) -> FScore`: the nine signals of spec 10.8 in that order, each `True`, `False` or `None` (a line missing); `score` the count of `True`, `read` the count not `None`.
  - `ncav(y: BalanceYear) -> float | None`: `total_current_assets − total_liabilities`, `None` when either is missing.

- [ ] **Step 1: Write the failing tests**

```python
def test_coverage_4_is_a_minus_with_five_percent() -> None:   # ebit 80, interest 20, debt 200, cash 100 → ("A-", 4.0, 0.05)
def test_net_cash_is_no_default_risk() -> None:                # cash 250 ≥ debt 200 → pi 0.0, note "no net debt"
def test_net_debt_without_interest_is_unavailable() -> None:   # interest None or 0 with debt 200, cash 100 → None
def test_a_loss_is_rated_d_whatever_the_interest() -> None:    # ebit -10, interest 20 → ("D", -0.5, 1.0)
def test_the_table_edges() -> None:                            # coverage 0.2 → C; 0.199999 → D; 8.5 → AAA; 2.25 → BB+ (pi 0.1963)
def test_altman_z_on_the_worked_lines() -> None:
    # a BalanceYear with WC 100, RE 200, EBIT 60, equity 400, TL 500, TA 1000 → x = (0.1, 0.2, 0.06, 0.8), score 6.56·0.1+3.26·0.2+6.72·0.06+1.05·0.8 = 2.5512, zone "grey"
def test_altman_z_zones_and_missing_lines() -> None:
def test_piotroski_f_counts_true_signals_and_reads_missing_as_none() -> None:
    # two hand-built years giving signals T,T,F,T,T,F,T,F,T → score 6, read 9; with gross profit missing → read 8
def test_ncav() -> None:
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_distress.py -q`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `distress.py`**

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/engine/test_distress.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/engine/distress.py tests/engine/test_distress.py
git commit -m "Add the synthetic rating, the ten-year distress probability, Altman Z double prime, Piotroski F and NCAV"
```

### Task 3: The run-off core

**Files:**
- Create: `src/fairband/engine/runoff.py`
- Test: `tests/engine/test_runoff.py`

**Interfaces:**
- Consumes: `RevenuePath`, `resolved_steps`, `growth_rates`, `tax_and_nopat` from `engine/revenue_growth.py` (read them; reuse what fits, and say in the report what did not).
- Produces:
  - `runoff_rates(g1: float | None, g2: float | None, g3: float | None, d: float, years: int) -> tuple[float, ...]`: the consensus rates for years 1 to 3 where given (a `None` g1 means every year takes `d`, spec 10.2's `path-on-trend`), then `d` to `years`.
  - `RunoffValuation(revenue, ebit, tax, nopat, reinvestment, release, fcff: tuple[float, ...], revenue_n1, nopat_n1, fcff_n1, terminal_value, pv_flows, pv_terminal, firm_value: float)` and `runoff_valuation(revenue0: float, rates: Sequence[float], margin: float, tax_rate: float, sales_to_capital: float, recovery: float, r: float, d: float) -> RunoffValuation` by spec 10.2 to 10.5 (same-year release and reinvestment; the carried-loss tax of 5a.6; the terminal at `d`).
  - `Equity(gc_per_share, ncav_per_share: float | None, floored_per_share, floor_bound: bool, distress_per_share, value_per_share: float)` and `runoff_equity(firm_value, debt, cash, shares, ncav: float | None, pi: float | None, fraction: float) -> Equity`: `gc = (firm − debt + cash) / shares`; the floor when `ncav > 0` and `ncav / shares > gc`; `distress = max(0, fraction · firm + cash − debt) / shares`; `value = floored · (1 − π) + distress · π`, and `value = floored` when `pi is None`.
  - `implied_decline_rate(value_at: Callable[[float], float], price: float) -> float | None`: the `d` in [−0.5, 0] at which `value_at(d) == price` to 1e-7, scanned in steps of 0.001 then bisected; `None` outside the range.

- [ ] **Step 1: Write the failing tests from spec 13.1**

```python
BASE = dict(revenue0=1000.0, rates=runoff_rates(-0.03, -0.03, -0.03, -0.04, 10), margin=0.08, tax_rate=0.25,
            sales_to_capital=2.0, recovery=0.6, r=0.09, d=-0.04)

def test_the_worked_decline_row() -> None:
    v = runoff_valuation(**BASE)
    assert v.revenue[0] == pytest.approx(970.0) and v.revenue[9] == pytest.approx(685.83, abs=0.01)
    assert v.fcff[0] == pytest.approx(67.2) and v.fcff[9] == pytest.approx(49.72, abs=0.01)
    assert v.fcff_n1 == pytest.approx(47.7335, abs=1e-3) and v.terminal_value == pytest.approx(367.18, abs=0.01)
    assert v.firm_value == pytest.approx(542.65, abs=0.01)
    e = runoff_equity(v.firm_value, 200.0, 100.0, 100.0, ncav=-200.0, pi=0.05, fraction=0.6)
    assert (e.gc_per_share, e.distress_per_share, e.value_per_share) == (pytest.approx(4.4265, abs=1e-3), pytest.approx(2.2559, abs=1e-3), pytest.approx(4.3180, abs=1e-3))
    assert not e.floor_bound

def test_net_cash_takes_no_distress() -> None:       # cash 250, pi 0.0 → 5.9265
def test_no_pi_is_the_floored_value() -> None:       # pi None → 4.4265
def test_the_ncav_floor_binds() -> None:             # ncav 600 → floored 6.00, floor_bound, value 5.8128
def test_a_chronic_loss_with_net_debt() -> None:     # margin -0.01, pi 1.0 → firm below zero, distress 0, value 0
def test_a_rising_consensus_step_reinvests_in_full() -> None:   # g2 = +0.02 → reinvestment (R2 − R1) / 2.0, release 0
def test_no_consensus_takes_d_in_every_year() -> None:          # runoff_rates(None, None, None, -0.04, 10) == (-0.04,) * 10
def test_a_steep_decline_rate_still_values() -> None:           # d = -0.8: finite, positive terminal, no exception
def test_the_implied_decline_rate_recovers_d() -> None:         # value_at built from BASE; price 4.3180 → -0.04 within 1e-4; a price above value_at(0) → None
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_runoff.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement `runoff.py`**

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/engine/test_runoff.py -q`
Expected: PASS to the spec's decimals; then tighten the worked assertions to the exact figures the arithmetic gives (1e-9) after checking them against the spec's.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/engine/runoff.py tests/engine/test_runoff.py
git commit -m "Add the run-off core: the shrinking path, the capital release, the terminal at the decline rate, the floor and the distress weighting"
```

### Task 4: The Decline route

**Files:**
- Create: `src/fairband/engine/route_decline.py`
- Modify: `src/fairband/engine/route_revenue_growth.py` (make the path pieces public: rename `_ntm_revenue` to `ntm_revenue` and `_path` to `revenue_path_for`, keeping their behaviour, with `_path_held` and the `few-analysts` flag reachable), `src/fairband/engine/route.py` (`_ROUTED`, `_route`, the refusal order at 193 to 196, `reprice` at 280), `src/fairband/engine/types.py` (`Route` gains `"decline"`), `src/fairband/engine/__init__.py` (`METHOD_VERSION = "fairband-mechanical/0.7"`)
- Modify: `docs/method.md` (a new section 6a "The Decline route" after 6; section 7 loses the Decline row; 8 the new flags; 9 the new refusals; 11 the 0.7 row; 12 sources; 13 glossary)
- Test: `tests/engine/test_route_decline.py` (new), `tests/engine/test_route.py`, `tests/engine/test_types.py`, `tests/refresh/test_run_price.py`

**Interfaces:**
- Consumes: Tasks 1 to 3; `Context`, `Valued`, `Refused`, `common_inputs`, `trailing_flags`, `price_facts_for`, `multiples_at`, `expected` from `route_steps.py`; the peers of `CompanyInputs.peers` with `target_margin`, `peer_sales_to_capital` from `revenue_growth.py`; `own_sales_to_capital`'s neighbours for the own-latest measure (`CapitalYear` of 4.5: revenue of the newest kept year over its average capital, as 5a.4 computes a peer's).
- Produces: `value_decline(c: Context) -> Valued | Refused` with route `"decline"`; `decline_at_price(im: dict[str, Any], price: float, value: float, policy: Policy) -> dict[str, Any]` (the designation is `route.py`'s; this returns `implied_decline_rate`, `multiples`, `expected_return`); the refusals, flags, intermediates and inputs of spec 10.1, 10.9 and 10.10 with the exact sentences of 10.2, 10.6, 10.7 and 10.8; the rebuild keys of 10.9.

- [ ] **Step 1: Write the failing tests**

Build a `CompanyInputs` fixture from spec 13.1 (trailing revenue 1,000 and operating income 80 over four quarters, five fiscal years with margins 7, 8, 8, 9, 8%, revenues falling so the classifier gives Decline on the test deciles, a kept ROIC year with revenue 1,000 and average capital 500, the quarterly and annual consensus for −3% steps, interest 5 a quarter, debt 200, cash 100, 100 shares, a balance year with current assets 300 and total liabilities 500, price 3.00):

```python
def test_the_worked_decline_row_values_at_4_318() -> None:          # value_per_share ≈ 4.3180; route "decline"; rating A-, pi 0.05
def test_the_refusal_order() -> None:                                # no trailing revenue → "no trailing revenue"; ...; value ≤ 0 → "value not positive in the run-off" with intermediates
def test_no_consensus_takes_the_trend_and_flags_path_on_trend() -> None:
def test_a_held_step_flags_path_held() -> None:
def test_a_rising_step_flags_consensus_recovery() -> None:           # sentence "The consensus has revenue growing 2.0% in year 2 while the five-year trend falls 4.0%."
def test_sales_to_capital_falls_back_to_the_peers() -> None:         # no kept year → peers' median, record "peers"; none → "no sales-to-capital"
def test_the_margin_is_the_five_year_median() -> None:               # trailing −1% with the same fiscal margins → the same value; intermediates["margin"] has median, trailing, used
def test_a_fiscal_year_fallback_still_rates_the_company() -> None:   # two quarters on file → trailing on the fiscal year, interest from the annual line, rating given
def test_a_missing_total_liabilities_line_applies_no_floor() -> None:
def test_the_flag_order() -> None:                                   # codes in spec 10.10's order on a row that raises path-held, line-not-presented:cash, ncav-floor, z-distress, f-score-low, reinvesting-in-decline, margin-flag
def test_the_inputs() -> None:                                       # DATA/RULE tags and the notes of spec 10.10; runoff_recovery, distress_sale_fraction, the rating row and figure cited
def test_the_json_round_trip_and_the_price_refresh() -> None:        # reprice at 6.00 moves the designation to "well-above" and recomputes implied_decline_rate, multiples, expected_return; the value and levels stay
```

`tests/engine/test_route.py`: a Decline phase no longer refuses "route not built yet"; `test_types.py`: `"decline"` is a `Route`.

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine -q`
Expected: FAIL.

- [ ] **Step 3: Implement `route_decline.py` and wire it**

Guards in spec 10.1's order after the shared ones. `d = min(0, c.inputs' revenue_slope ÷ last fiscal revenue)` from the `PhaseEvidence` (pass the evidence into the route or recompute `_trend`; prefer passing). Margin by 10.3 from `c.inputs.series`. The path from `revenue_path_for` (an incomplete NTM gives `g1 = None`, no refusal). Sales-to-capital: own-latest first, else `peer_sales_to_capital`, else refuse. Rating by `rate(ebit_n, trailing.interest_expense, debt, cash, policy)`. Z″ and F from the newest two `balance_years`. Flags in 10.10's order with 10.8's sentences; `reinvesting-in-decline` when `abs(trailing.capex) > trailing.depreciation` and the path's year-10 revenue is below revenue0. Intermediates and inputs as 10.10. `decline_at_price` via `implied_decline_rate` on a closure rebuilding the value from the rebuild keys. `route.py`: `_ROUTED` gains Decline, `_route` dispatches, `reprice` branches on `"decline"`. `METHOD_VERSION` to 0.7.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md`**

New section 6a with subsections mirroring spec 10.1 to 10.11 in the method's register (what runs, no reasons); section 7's table loses Decline; section 8 the flag rows (`path-on-trend`, `consensus-recovery`, `ncav-floor`, `distress-not-charged`, `z-distress`, `f-score-low`, `reinvesting-in-decline`, `line-not-presented:totalLiabilities`); section 9 the refusals ("value not positive in the run-off"); section 11 the 0.7 row; section 12 the sources (Damodaran 2009 distress paper, ratings.html, Altman 2000, Piotroski 2000, Graham); section 13 the terms (run-off, normalized margin, synthetic rating, distress-sale value, NCAV).

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine tests/engine tests/refresh docs/method.md
git commit -m "Value Decline rows on the run-off DCF with the distress weighting, the NCAV floor and the distress signals, as method 0.7"
```

### Task 5: The Start-up route

**Files:**
- Create: `src/fairband/engine/requirement.py`, `src/fairband/engine/route_start_up.py`
- Modify: `src/fairband/engine/route.py` (the Start-up branch at line 193 runs the route before the "no trailing figures" guard; `reprice` on a Start-up refusal; `Route` gains `"start-up"`)
- Modify: `docs/method.md` (section 6b "The Start-up route"; section 7 keeps the foreign filer only; 8, 9, 11, 12, 13)
- Test: `tests/engine/test_requirement.py`, `tests/engine/test_route_start_up.py` (new), `tests/engine/test_route.py`

**Interfaces:**
- Consumes: `target_margin`, `peer_sales_to_capital` (5a.4, 5a.5 via `revenue_growth.py`), `tax_and_nopat`, the terminal return of 4.7 (`route_steps.RoicTerms` or the moat-only path: a Start-up without kept ROIC years takes `r`), `price_facts_for`.
- Produces:
  - `ramp_ev(revenue_y10: float, revenue0: float, ebit0: float, target_margin: float, tax_rate: float, sales_to_capital: float, r: float, g_t: float, terminal_return: float) -> RampValuation` (the ten-year table and the firm value of spec 9.2) and `required_revenue(ev_price: float, **ramp) -> float | None` (bisection on [0, 1e13] to 1e-9 relative; `None` when `ramp_ev(1e13) < ev_price`).
  - `value_start_up(c: StartUpContext) -> Refused` always: reason `"Start-up: no value by design"`, intermediates `requirement` (9.2's keys or `reason`), `cash_floor`, `burn_cover_years`, `burn`, `price_facts`, `debt`, `cash`, `shares`, `market_cap`; flags in 9.5's order; inputs as 9.5. `StartUpContext` is `Context` with `trailing: TrailingFigures | None`.
  - `start_up_at_price(im, price, policy, market_cap) -> dict[str, Any]`: `requirement.revenue_y10` and `ev_price` rebuilt from the rebuild keys; the `below-net-cash` flag re-evaluated.

- [ ] **Step 1: Write the failing tests from spec 13.2**

```python
def test_the_worked_start_up_requirement() -> None:
    # revenue0 0, ebit0 -50, margin 0.25, tax 0.25, s2c 1.5, r 0.09, g 0.03, terminal return 0.09:
    # ramp_ev(0) ≈ -166.93; ramp_ev(1000) ≈ 931.91; required_revenue(1700) ≈ 1725.73 (abs 0.01); ramp_ev(that) ≈ 1700 (abs 1e-4)
def test_no_revenue_reaches_the_price() -> None:          # ev_price 1e15 → None
def test_the_route_is_always_the_refusal_with_figures() -> None:   # reason "Start-up: no value by design"; requirement.revenue_y10 ≈ 1725.73; value None; designation None
def test_each_requirement_reason() -> None:               # no target margin: n mature peers; no sales-to-capital; no statutory tax rate; no market cap; no revenue reaches the price
def test_no_market_cap_gives_the_reason_and_keeps_the_floor() -> None:
def test_net_cash_above_the_market_cap() -> None:         # market cap 250, cash 300 → requirement 0, flag below-net-cash with "The price is covered by net cash: market cap 250 against net cash 300"
def test_the_burn_cover() -> None:                        # cfo -60, capex -15, cash 300 → 4.0, no flag; cash 120 → 1.6 and burn-cover-short "Cash covers 1.6 years of the trailing burn of 75 a year."; cfo +10 → "not burning"
def test_a_start_up_without_trailing_figures_still_runs() -> None:
def test_the_flag_order_and_inputs() -> None:
def test_the_price_refresh_rebuilds_the_requirement() -> None:     # market cap doubles → revenue_y10 rises; the same from the rebuild keys alone
```

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/engine/test_requirement.py tests/engine/test_route_start_up.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

`route.py`: the Start-up branch builds a `StartUpContext` after the price and share guards and before the trailing guard, and returns `refusal_result` with the route's intermediates, flags and inputs; `reprice` on a refusal whose intermediates carry `requirement` calls `start_up_at_price`.

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Update `docs/method.md`**

Section 6b from spec 9; section 7 keeps the foreign-filer row only, with the Start-up refusal text now "Start-up: no value by design"; 8 (`below-net-cash`, `burn-cover-short`); 9; 11's 0.7 row gains the Start-up route; 12; 13.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/engine tests/engine docs/method.md
git commit -m "Give a Start-up row the revenue the price needs by year 10, the cash floor and the burn cover"
```

### Task 6: The drawer and the columns for both routes

**Files:**
- Modify: `src/fairband/web/rows.py` (`EXTRA_KEYS`, the row dict)
- Modify: `src/fairband/web/static/app.js` (the drawer's `sections()`), `src/fairband/web/static/design-system/components/bundle.js` (the column catalog) and `index.d.ts`
- Test: `tests/web/test_app.py`

**Interfaces:**
- Produces: row keys `requiredRevenue` (a Start-up row's `requirement.revenue_y10`), `burnCover`, `rating` (the rating letter), `distressProbability`, `altmanZ`, `piotroskiF` (as "6 of 9"); catalog columns for each, off by default; drawer sections: on a Decline row the run-off table (year, revenue, EBIT, NOPAT, release or reinvestment, FCFF), the margin line (median, trailing), the rating with coverage and π, the floor, the distress-sale value and the weighting, Z″ with its zone and F with its signals; on a Start-up row the requirement (the revenue, the multiple of trailing revenue when positive, the target margin and its peers, the ramp table), the cash floor and the burn cover; the designation chip's colours (founder 2026-11-03): `.fb-designation--well-below { color: var(--chart-pos-3) }`, `--below` `var(--chart-pos-2)`, `--near` `var(--ink-muted)`, `--above` `var(--chart-neg-2)`, `--well-above` `var(--chart-neg-3)` in `bundle.css` under a marker, the chip's class gaining `fb-designation--<code>` in `bundle.js`.

- [ ] **Step 1: Write the failing tests**

`tests/web/test_app.py`: `test_bundle_css_colours_the_five_designations` (the five rules with those tokens; the chip class carries the code), `test_screen_row_carries_the_decline_figures` (a Decline fixture snapshot gives `rating == "A-"`, `distressProbability == 0.05`, `altmanZ`, `piotroskiF == "6 of 9"`), `test_screen_row_carries_the_start_up_requirement` (`requiredRevenue`, `burnCover`), `test_bundle_catalog_has_the_route_columns` (the six keys with their heads, off by default), `test_app_js_drawer_draws_the_run_off_table` (`'Release'`, `'Normalized margin'`, `'Distress-sale value'`, `'Altman Z″'`, `'Piotroski F'`), `test_app_js_drawer_draws_the_requirement` (`'Revenue the price needs'`, `'× the trailing revenue'`, `'Cash floor'`, `'Burn cover'`).

- [ ] **Step 2: Run them to see them fail**

Run: `uv run pytest tests/web -q`
Expected: FAIL.

- [ ] **Step 3: Implement** within the design system, each bundle edit under a `// fairband:` marker

- [ ] **Step 4: Run the suite and look at the page**

Run: `uv run pytest -q`; serve against a database copy with a Decline and a Start-up row.
Expected: PASS; the drawer shows the sections named above.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/web tests/web
git commit -m "Show the run-off, the rating and the distress signals on a Decline row and the price-implied requirement on a Start-up row"
```

### After the merge (the controller, not a task)

A revalue under 0.7/v5, then the readout of spec 15.6 for the routes: the Decline rows valued and refused by reason, the median price ÷ value, the ratings' distribution, the floor and distress-charged counts, the flags; the Start-up requirements' distribution.
