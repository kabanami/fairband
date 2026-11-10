# Foreign filers, plan 2: the half-year window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build section 8 of the foreign filers spec (B-28, plan 2): a company whose statement periods are half-years takes its trailing figures from the last two and its NTM consensus from the next two, so the 26 half-year reporters among the 192 get a route.

**Architecture:** The reporting cadence is read once from the spacing of the quarterly statement rows (`refresh/inputs_statements.py`) and carried on the trailing figures; the trailing sum, the street actuals and the split rule's periods follow it with no change of shape. The NTM window (`engine/anchor.py`) takes the cadence and asks for four quarters or two half-years; the three routes that call it pass the trailing figures' cadence.

**Tech Stack:** Python 3.13, uv, pytest, mypy, ruff.

**Spec:** `docs/superpowers/specs/2026-11-10-foreign-filers-design.md`, section 8, 11.4, 12 (the plan 2 line), 13 (the last bullet), 15 (plan 2).

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- `docs/method.md` changes in the same commit as the engine or the refresh behaviour it describes; the Methodology page with it where it speaks of four quarters.
- Method version stays `fairband-mechanical/1.1` and policy v11 (plan 1): no quarterly company's figure moves; the six goldens and FXCO are unchanged bit for bit.
- Never print, log, store or commit a key; never commit vendor data; fixtures are synthetic.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- No subagent dispatches another subagent; review arrives from the controller.

## Review Focus

1. A company with quarterly rows 89 to 92 days apart: bit for bit as today (the cadence is `quarterly`, the window four).
2. A company whose consensus rows are quarterly while its statements are half-years (ABVX): the window the consensus gives, the trailing figures the statements give, the street actuals matched at the two trailing ends or absent.
3. A company with neither four consecutive quarters nor two consecutive half-years: the fiscal-year fallback as today, flagged, the window read on four quarters as today (the fallback carries no cadence of its own; *the plan's call*: `quarterly`).
4. The base fiscal year of a two-period window: the later year on a tie, where a quarterly reporter's window lands.
5. The split rule on two periods: the per-period judgment unchanged in shape.

---

### Task 1: The cadence, the two-period trailing figures and the two-period window

**Files:**
- Modify: `src/fairband/refresh/inputs_statements.py` (`Cadence`, `cadence_of`, `_trailing`, `TrailingFigures.cadence`, the flag's sentence), `src/fairband/engine/anchor.py` (`consecutive_periods`, `ntm_periods`, `ntm_anchor`'s count check, `base_year`, `_revenue_scale` unchanged), `src/fairband/engine/route_mature_growth.py`, `route_revenue_growth.py`, `route_decline.py` (the window call), `src/fairband/web/reviews_api.py` and `src/fairband/engine/overrides.py` where `ntm_quarters` or "four quarters" is read for the guidance override (`earnings.ntm`, `revenue.ntm`: "the four quarters still required" becomes the window's periods), `src/fairband/refresh/inputs.py` (`_street_actuals` reads `trailing_quarter_ends` as today; its docstring), `src/fairband/refresh/inputs_splits.py` (docstrings: "the four quarters, or the two half-years")
- Modify: `docs/method.md` 4.2 (the cadence and the two half-years), 5.2 (the window), 5a.1 and 6a.1 (the same window), 8 (`trailing-on-fiscal-year`'s sentence), 13 (cadence), the Methodology page where it says "four quarters" in the Mature Growth steps
- Test: `tests/refresh/test_inputs.py`, `tests/engine/test_anchor.py`, `tests/engine/test_mature_growth.py`, `tests/engine/test_route_decline.py`, `tests/engine/test_route_revenue_growth.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `Cadence = Literal["quarterly", "half-yearly"]` in `engine/anchor.py` (the engine never imports from `refresh`), with the bounds `HALF_DAYS_MIN, HALF_DAYS_MAX = 170, 195` beside the quarter bounds, both pairs public; `cadence_of(ends: Sequence[date]) -> Cadence | None` in `inputs_statements.py`, reading those bounds: `quarterly` when the two newest ends are 80 to 100 days apart, `half-yearly` when 170 to 195, else `None`.
- Produces: `TrailingFigures.cadence: Cadence = "quarterly"` (the fallback's value too); `_trailing` sums the last four when the cadence is quarterly and each end is 80 to 100 days after the one before, the last two when half-yearly and 170 to 195 apart, else the fiscal year; `trailing_quarter_ends` the two ends on the half-yearly reading; `Statements.trailing_periods` the two.
- Produces: in `anchor.py`, `PERIODS_PER_YEAR = {"quarterly": 4, "half-yearly": 2}`, `consecutive_periods(ends, cadence) -> bool` (the cadence's bounds), `ntm_periods(estimates, last_reported, cadence) -> tuple[QuarterEstimate, ...] | None` (the first `PERIODS_PER_YEAR[cadence]` rows ending more than `SAME_PERIOD_DAYS` after `last_reported`, consecutive under the cadence); `ntm_quarters(estimates, last_reported)` stays as `ntm_periods(..., "quarterly")`; `ntm_anchor(quarters, ...)` requires `len(quarters) == PERIODS_PER_YEAR[cadence]` with the cadence passed (`cadence: Cadence = "quarterly"`); `base_year(estimates, last_reported, cadence="quarterly")`; `base_fiscal_year` unchanged (most periods, a tie the later).
- Produces: the three routes call `ntm_periods(i.quarter_estimates, t.period_end, t.cadence)` and pass `t.cadence` to `ntm_anchor` and `base_year`.

- [ ] **Step 1: Write the failing tests**

`tests/refresh/test_inputs.py` (over the synthetic company with its quarters replaced by half-years: `synthetic.bodies` gains a `cadence` parameter writing `income-quarter` and `cashflow-quarter` rows at 2024-12-31, 2025-06-30, 2025-12-31 and 2026-06-30, the EPS and shares as the quarterly ones; the street actuals at the same ends):

```python
def test_half_year_rows_give_a_two_period_trailing_sum(store) -> None:
    """Spec 11.4: rows ending 2025-06-30, 2025-12-31 and 2026-06-30 (184 and 181 days)."""
    inputs = build(store(**bodies(cadence="half-yearly")))
    t = inputs.trailing
    assert t.cadence == "half-yearly" and t.quarters == 2 and not t.on_fiscal_year
    assert t.period_end == date(2026, 6, 30)
    assert t.revenue == pytest.approx(<the sum of the two half-years' revenue>)
    assert [p.end for p in stated.trailing_periods] == [date(2025, 12, 31), date(2026, 6, 30)]
    assert inputs.street_ttm_eps == pytest.approx(<the two actuals' sum>)


def test_quarterly_rows_read_as_today(store) -> None:
    inputs = build(store(**bodies()))
    assert inputs.trailing.cadence == "quarterly" and inputs.trailing.quarters == 4


def test_two_half_years_not_consecutive_fall_back(store) -> None:
    # ends 2025-06-30 and 2026-06-30 only: on_fiscal_year, the flag's sentence, cadence "quarterly"
```

`tests/engine/test_anchor.py`:

```python
def test_ntm_periods_half_yearly() -> None:
    """Spec 11.4: consensus rows ending 2026-12-31 and 2027-06-30 after a last reported 2026-06-30."""
    rows = [half(date(2026, 6, 30), 2026), half(date(2026, 12, 31), 2026), half(date(2027, 6, 30), 2027), half(date(2027, 12, 31), 2027)]
    window = ntm_periods(rows, date(2026, 6, 30), "half-yearly")
    assert [q.period_end for q in window] == [date(2026, 12, 31), date(2027, 6, 30)]
    assert base_fiscal_year(window) == 2027
    assert ntm_periods(rows, date(2026, 6, 30), "quarterly") is None
    assert ntm_periods(rows[:2], date(2026, 6, 30), "half-yearly") is None   # one row after


def test_ntm_anchor_sums_two_half_years(...) -> None:
    # two rows at EPS 1.0 and 1.2: ntm_eps_raw 2.2 with cadence "half-yearly"; with "quarterly" the refusal "incomplete NTM consensus"
```

The routes: `mature_growth_inputs()` with half-yearly trailing figures and half-year consensus rows values with the two-row window (a hand figure for the anchor); the Decline and revenue-growth routes the same window; `test_golden.py` unchanged.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/engine/test_anchor.py tests/refresh/test_inputs.py -q`
Expected: FAIL (`ntm_periods`, `cadence` unknown).

- [ ] **Step 3: Build it**

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS; the goldens unchanged.

- [ ] **Step 5: The method document and the Methodology page**

4.2: "The trailing figures are the sums of the last four quarterly income statements when the company reports quarterly (the two newest rows 80 to 100 days apart) and each ends 80 to 100 days after the one before, or of the last two when it reports half-yearly (170 to 195 days apart) and each ends 170 to 195 days after the one before; ... Otherwise the last fiscal year's, flagged." 5.2: "the sum of the periods after the last reported one that cover the next twelve months: four consecutive quarters, or two consecutive half-years for a half-yearly reporter; the base fiscal year holds most of them, a tie taking the later". 5a.1 and 6a.1 refer to 5.2. The Methodology page's Mature Growth steps say "the next four quarters (two half-years for a company that reports twice a year)".

- [ ] **Step 6: Commit**

```bash
git add src tests docs/method.md
git commit -m "Read a half-yearly reporter's trailing figures from its last two half-years and its NTM consensus from the next two"
```

---

### Task 2: The live steps and the readout (the controller, after the merge)

Not a subagent task. After the merge: the server restarted from main, a scoped refresh of the 26 half-year reporters (SSL, NGG, ABVX, RELX, SBSW, WPP, DEO, CCEP, MAAS, WDS, HLN, ZGN, VOD, GFI, TLX, IHG, DRD, BHP, UL, RIO, BTI, SNN, RTO, WSE, PSO, HMY), the readout of spec 13's last bullet into the spec's decision log, and the backlog's B-28 row closed with plan 2's commits.
