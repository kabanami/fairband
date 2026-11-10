# Engine Round 2, plan 2: stock splits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build section 10 of the engine round 2 spec (B-143): the `splits` dataset fetched with every company, and the basis rule that reads every share count and per-share figure on the quote date's share basis when a split falls between the newest statement and the quote, with the `split-pending` note, the documents and the playbook; then the live steps.

**Architecture:** The dataset is one more FMP call in `refresh/fetch.py`, normalized to observations (dataset `split`, two fields per split) by `vendors/normalize_fmp_observations.py`. The rule is a pure module, `refresh/inputs_splits.py`, that `refresh/inputs.build_inputs` runs on the figures it has read, before it builds `CompanyInputs`; the engine is untouched and reads scaled inputs with their notes. The vendor check of spec 10.3, run live on 2026-11-10, fixed the rule's shape (see "The vendor findings" below).

**Tech Stack:** Python 3.13, uv, pytest, mypy, ruff; the playbook's Markdown.

**Spec:** `docs/superpowers/specs/2026-11-09-engine-round-2-design.md`, section 10 (and 13.4's last bullet, 14's splits line, 15's splits line, 16).

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- `docs/method.md` changes in the same commit as the engine or the refresh behaviour it describes; the Methodology page (`src/fairband/web/static/methodology.html`) with it. Where documents disagree, `docs/method.md` describes what runs.
- Method version stays `fairband-mechanical/1.0` and policy `fairband-policy-v10`: the rule changes no figure until a split is on file, and no split is on file until the next full or scoped refresh fetches it. `Policy.split_implied_count_tolerance` (0.15) exists since plan 1; no new policy value, no new setting.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic or hand-trimmed. The splits fixtures below are made up.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Every existing test keeps passing unchanged in meaning: the ACME fixture's one split is dated 2019, before every statement, so no existing row's figures move. The goldens (`tests/fixtures/golden`) stay bit for bit.
- No subagent dispatches another subagent; review arrives from the controller.

## The vendor findings (spec 10.3, live on 2026-11-10, read-only)

Record these in the spec's decision log (Task 3); they fix the rule's branches.

1. **FMP's `splits` endpoint** (`/stable/splits?symbol=`) answers a list of `{symbol, date, numerator, denominator, splitType}`, newest first: NVDA `2024-06-10, 10, 1`; WMT `2024-02-26, 3, 1`; six and ten rows back to 2000 and 1985. **It lists a split only from its effective date**: META's split of late January 2027 is absent (an empty list on 2026-11-10), and `splits-calendar` for 2026-11-01 to 2027-03-31 is empty too.
2. **FMP restates its statement rows** to the post-split basis: NVDA's quarter ending 2024-04-28, before the 10-for-1 split, reads `epsDiluted` 0.60 and `weightedAverageShsOutDil` 24.89 bn (filed: $5.98 and 2.49 bn); AVGO's quarter ending 2024-05-05 reads 0.44 and 4.80 bn (filed: $4.42 and 480 m). Its street actuals (`earnings`) are restated too (NVDA 2024-05-22: 0.61). Its forward consensus rows imply the post-split count (NVDA fiscal 2025 to 2028: 24.6, 24.6, 24.3, 24.0 bn against 24.3 bn diluted); the rows for fiscal years already reported are inconsistent and the engine never reads them. **When** FMP restates after a split is not knowable from 2024's splits; the rows two years on are restated.
3. **FMP's closes** (`historical-price-eod/full`, the `close` field `price_closes` reads) are on the post-split basis before the split: NVDA 2024-06-07 reads 120.89 (traded at $1,208.88). So a refetched price history needs no scaling.
4. **The quote carries the share basis**: `marketCap ÷ price` is the share count on the quote's basis (NVDA 24.10 bn against 24.29 bn diluted; AVGO 4.77 against 4.89; WMT 7.96 against 7.98; META 2.556 bn). The quote has no `sharesOutstanding` field.

**The rulings these give (Claude's calls, written for the founder to overturn):**

- The closes branch of 10.2 is dropped (finding 3). The statement branch is kept but **judged on the data, not assumed**: finding 2 shows FMP restates eventually but not when, so the rule scales the stored count and the statement per-share figures only when the quote's own count (finding 4) shows the stored count on the pre-split basis. In steady state FMP has restated, the test says post-split, nothing is scaled and the sentence says so. The spec's "if FMP restates every statement row, the statement branch above is dropped" is read as: dropped as an assumption, kept as a test; cost if wrong, none in steady state, since nothing is scaled unless the quote and the count disagree by exactly the split.
- The consensus branch stays as the spec wrote it, by the implied count, which is self-correcting against the lag.
- The GuruFocus branch stays by observation date (the spec's rule): GuruFocus's EPS figures are current values reused for 7 days, so a scoped refresh the week after a split may carry a pre-split observation.
- `split-pending` fires whenever a split on file falls after the newest statement period end and at or before the price date, whether or not anything was scaled: the agent wants to know a split just happened (the consensus and the guidance record are on the move). It stops when the newest statement period end passes the split date, which is the spec's "until the stored sources are themselves post-split".
- The normalized shape keeps the numerator and the denominator as two fields of one observation period, so the sentence can say "2-for-1" and "1-for-10 reverse split"; the ratio is numerator ÷ denominator at read time.
- The remedy for a split day stays the scoped refresh (spec 10.3); a price refresh applies no rule. The playbook says so (Task 3).

## Review Focus

- A split dated exactly on the price date: "at or before the price date" includes it; a split dated the day after the quote does not fire. Test in Task 2.
- Two splits in the window (a 2-for-1 then a 3-for-2): one compound ratio of 3, one sentence naming both. Test in Task 2.
- The quote's count missing (no `market_cap` or no `price` observation on the quote): the statement side is left as stored and the sentence says why; the consensus test still runs on the stored count as the post-split count. Test in Task 2.
- A consensus row whose implied count lies within the tolerance of both the pre-split and the post-split count (a 11-for-10 split): left alone and named. Test in Task 2.
- A company whose `splits` call fails (HTTP 500): the response stores its error, the company is valued as before with no `split` rows and no flag, and `splits` never joins the fetch's `failed`-required set. Test in Task 1 and Task 2.

---

### Task 1: The splits dataset

**Files:**
- Modify: `src/fairband/vendors/fmp.py` (a `splits` method and a docstring line, checked live 2026-11-10)
- Modify: `src/fairband/vendors/normalize_fmp_observations.py` (`split_observations`; the module docstring's dataset list), `src/fairband/vendors/normalize_fmp.py` (import and `__all__`)
- Modify: `src/fairband/refresh/fetch.py` (the call list: fourteen FMP calls; `_rows` case `"splits"`; the module docstring: "fourteen FMP calls", the splits' usability), `src/fairband/refresh/run.py` (docstring: "14 FMP and 2 GuruFocus calls")
- Create: `src/fairband/refresh/inputs_splits.py` (`SplitRow`, `splits_for`; Task 2 adds the rule)
- Modify: `src/fairband/refresh/inputs.py` (`_OBSERVATIONS` gains `"split"`)
- Create: `tests/fixtures/fmp/splits.ACME.json`, `tests/fixtures/fmp/splits.BOLT.json`
- Modify: `docs/method.md` sections 2 (the table row) and 10 (the full and scoped bullets)
- Test: `tests/vendors/test_fmp.py`, `tests/vendors/test_normalize_fmp.py`, `tests/refresh/test_fetch.py`, `tests/refresh/test_splits.py` (new)

**Interfaces:**
- Produces: `Fmp.splits(self, symbol: str) -> VendorResponse` calling route `splits` with `{"symbol": to_fmp_symbol(symbol)}`.
- Produces: `split_observations(payload: Any, symbol: str, response_id: int, observed_at: datetime, entered_at: datetime) -> list[ObservationRow]` in `normalize_fmp_observations.py`: two rows per usable split, dataset `"split"`, `period` the split date, fields `"numerator"` and `"denominator"`, unit `"shares"`, `as_of` the split date. A row needs a date that parses and two numbers above zero; others give nothing. Anything but a list gives `[]`. Follow the module's existing `Source`/`source.observation(...)` pattern (see `profile_observations`).
- Produces: in `fetch._rows`, `case "splits": return ([], split_observations(payload, *source)) if isinstance(payload, list) else None` — an empty list is usable (a company with no split has none, reused like any answer), a non-list is unusable. `splits` is not in `REQUIRED`.
- Produces: `SplitRow(date: date, numerator: float, denominator: float)` frozen dataclass with property `ratio -> float` (numerator ÷ denominator) and property `word -> str` (`"2-for-1 split"`, `"3-for-2 split"`, `"1-for-10 reverse split"` when the ratio is below 1; numbers printed as integers when whole, else to two decimals); `splits_for(conn: sqlite3.Connection, symbol: str) -> tuple[SplitRow, ...]`, oldest first, from `observations_for(conn, symbol, "split")`, pairing the two fields by period; a period lacking a field or with a denominator of zero is skipped.

- [ ] **Step 1: Write the failing tests**

In `tests/vendors/test_fmp.py`, one more case in `test_routes_and_params`'s parametrization, beside the peers case:

```python
(lambda f: f.splits("BRK.B"), "splits", {"symbol": "BRK-B"}),
```

In `tests/vendors/test_normalize_fmp.py`:

```python
def test_split_observations() -> None:
    """Two rows per split, dataset ``split``, the split date as the period and as_of; the
    numerator and denominator kept apart so the sentence can read 2-for-1."""
    rows = split_observations(load("splits.ACME"), "ACME", RID, OBSERVED, ENTERED)
    assert [(r.dataset, r.period, r.field, r.value, r.unit, r.as_of) for r in rows] == [
        ("split", date(2019, 5, 20), "numerator", Decimal(2), "shares", date(2019, 5, 20)),
        ("split", date(2019, 5, 20), "denominator", Decimal(1), "shares", date(2019, 5, 20)),
    ]
    assert {r.response_id for r in rows} == {RID}


def test_split_observations_shapes() -> None:
    # a reverse split keeps its numbers; a row without a date, with a zero or missing number, or
    # a non-list payload gives nothing
    reverse = split_observations([{"date": "2025-01-02", "numerator": 1, "denominator": 10}], "X", RID, OBSERVED, ENTERED)
    assert [(r.field, r.value) for r in reverse] == [("numerator", Decimal(1)), ("denominator", Decimal(10))]
    for bad in ([{"numerator": 2, "denominator": 1}], [{"date": "2025-01-02", "numerator": 0, "denominator": 1}], [{"date": "2025-01-02", "numerator": 2}], {"date": "2025-01-02"}, None, "x"):
        assert split_observations(bad, "X", RID, OBSERVED, ENTERED) == []
```

In `tests/refresh/test_fetch.py`: `FMP_ENDPOINTS` gains `"splits"` after `"peers"`; `DATASETS` gains `("split", "splits")`; every `calls=15` and `== 15` becomes 16 (`test_fetches_all_endpoints_and_stores`, `test_reuses_within_24h`, `test_force_fetches_fresh_endpoints`, `test_gf_reused_for_7_days`, `test_endpoint_failure_recorded_and_continues`, `test_only_required_endpoints_set_the_error`, `test_an_empty_quarterly_consensus_is_not_a_fetch_failure`; `router.calls.total()` likewise). Add:

```python
def test_splits_are_stored_and_not_required(
    conn: sqlite3.Connection, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> None:
    """Spec 2026-11-09 10.1: the splits are fetched with the company's datasets and stored as
    observations; an empty list is usable (a company with no split); a failure leaves the
    company valued on what it has."""
    router.bodies["splits"] = b"[]"
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == () and outcome.error is None
    assert responses(conn)["splits"]["error"] is None
    assert observations_for(conn, "ACME", "split") == []
    router.bodies["splits"] = b'{"Error Message": "no"}'
    clock.now += timedelta(days=2)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == ("splits",) and outcome.error is None
    router.bodies.pop("splits")
    router.fail.add("splits")
    clock.now += timedelta(days=2)
    outcome = fetch(conn, clients, policy, clock)
    assert outcome.failed == ("splits",) and outcome.error is None
```

(Adapt the `fetch`/`responses` helpers' signatures to the file's; the stored row for a 500 has `http_status` 500 and an error, as the other endpoints' failures do.)

In `tests/refresh/test_splits.py` (new; the Store fixture and `vendor_double` imports as `test_inputs.py` has them):

```python
def test_splits_for_reads_the_rows_oldest_first(store: Store) -> None:
    conn = store(**bodies(), splits=[
        {"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1},
        {"symbol": "ACME", "date": "2019-05-20", "numerator": 3, "denominator": 2},
        {"symbol": "ACME", "date": "2010-01-04", "numerator": 1, "denominator": 10},
    ])
    rows = splits_for(conn, "ACME")
    assert [(r.date, r.numerator, r.denominator) for r in rows] == [
        (date(2010, 1, 4), 1.0, 10.0), (date(2019, 5, 20), 3.0, 2.0), (date(2026, 10, 15), 2.0, 1.0)
    ]
    assert [r.ratio for r in rows] == [0.1, 1.5, 2.0]
    assert [r.word for r in rows] == ["1-for-10 reverse split", "3-for-2 split", "2-for-1 split"]


def test_splits_for_without_rows(store: Store) -> None:
    assert splits_for(store(**bodies(), splits=[]), "ACME") == ()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest -q tests/vendors/test_fmp.py tests/vendors/test_normalize_fmp.py tests/refresh/test_fetch.py tests/refresh/test_splits.py`
Expected: FAIL on imports (`split_observations`, `splits_for`) and on the counts (15 against 16).

- [ ] **Step 3: Write the fixtures**

`tests/fixtures/fmp/splits.ACME.json`:

```json
[
  {
    "symbol": "ACME",
    "date": "2019-05-20",
    "numerator": 2,
    "denominator": 1,
    "splitType": "forward"
  }
]
```

`tests/fixtures/fmp/splits.BOLT.json`: `[]` (a company with no split). The router finds them as `fmp/splits.<symbol>.json`.

- [ ] **Step 4: Implement**

`Fmp.splits`; the docstring line after `stock-peers`: "``splits``: ``symbol``; each row a ``date``, a ``numerator``, a ``denominator`` and a ``splitType``, newest first; a split appears from its effective date (checked live 2026-11-10 on NVDA, WMT and META)." `split_observations` and the export. In `fetch._calls`, `on_fmp("splits", {}, partial(fmp.splits, symbol))` after the peers; `_rows` case; the docstrings. `inputs_splits.py` with `SplitRow` and `splits_for`; `_OBSERVATIONS` gains `"split"`.

- [ ] **Step 5: The documents**

`docs/method.md` section 2's table, a row after Peers: `| Stock splits | `splits` | every split on file, newest first, stored as two observations per split (the numerator and the denominator on the split date); not required; an empty list is a usable answer (a company with no split). FMP lists a split from its effective date, never before (checked 2026-11-10) |`. Section 10: the Full bullet's "the data of section 2" already covers it; add to the Scoped line (or the paragraph that names it) that a scoped refresh fetches the company's statements, closes and splits again and runs assembly on them.

- [ ] **Step 6: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

```bash
git add -A
git commit -m "Fetch each company's stock splits from FMP with its datasets and store them as observations (spec 2026-11-09 10.1)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: The basis rule and the `split-pending` note

**Files:**
- Modify: `src/fairband/refresh/inputs_splits.py` (the rule), `src/fairband/refresh/inputs.py` (`build_inputs` runs it; the module docstring gains a bullet)
- Modify: `docs/method.md` sections 4.2 (the split basis paragraph), 8 (the flags table row), 10 (the price refresh applies no split rule; the scoped refresh is the remedy), 11 (the 1.0 row's text gains the splits)
- Modify: `src/fairband/web/static/methodology.html` (the notes list gains `split-pending` after `consensus-basis-unknown`)
- Test: `tests/refresh/test_splits.py`, `tests/web/test_methodology.py` (only if it pins the flag list)

**Interfaces:**
- Consumes: `SplitRow`, `splits_for` (Task 1); `Policy.split_implied_count_tolerance`; `TrailingFigures`, `QuarterEstimate`, `AnnualEstimate`, `Flag`.
- Produces, in `inputs_splits.py`:

```python
@dataclass(frozen=True)
class SplitFigures:
    """The figures the rule may scale, as assembly read them."""
    shares_diluted: float | None
    trailing: TrailingFigures | None
    street_ttm_eps: float | None
    gf_eps_ttm: float | None
    gf_eps_ttm_as_of: date | None
    gf_eps_without_nri: float | None
    gf_eps_without_nri_as_of: date | None
    quarter_estimates: tuple[QuarterEstimate, ...]
    annual_estimates: tuple[AnnualEstimate, ...]

@dataclass(frozen=True)
class SplitOutcome:
    figures: SplitFigures            # scaled where the rule scaled
    flag: Flag | None                # split-pending, or None without a pending split
    notes: dict[str, str]            # input name -> note, for each scaled input
    estimate_methods: dict[str, str] # input name -> "split-scaled", the same names

def pending_splits(splits: Sequence[SplitRow], statement_end: date | None, price_date: date | None) -> tuple[SplitRow, ...]
def apply_splits(figures: SplitFigures, splits: Sequence[SplitRow], *, statement_end: date | None, price_date: date | None, quote_market_cap: float | None, quote_price: float | None, tolerance: float) -> SplitOutcome
```

The rule, exactly:

1. `pending_splits`: the splits with `statement_end < date <= price_date`; empty when either date is `None`. `statement_end` is `trailing.period_end` (the newest quarter end, or the fiscal year end on the fallback). The compound ratio ρ is the product of the pending ratios.
2. **The statement side** (the count `shares_diluted`, `trailing.eps_diluted`, `street_ttm_eps`): the quote's count Q = `quote_market_cap ÷ quote_price` (both from the `quote` dataset; `None` when either is missing or the price is zero). With a count D and a Q: pre-split when `within(D × ρ, Q)` and not `within(D, Q)`, where `within(a, b)` is `abs(a − b) ≤ tolerance × b`. Pre-split: the count becomes D × ρ, `trailing.eps_diluted` ÷ ρ (the sum as a whole, `dataclasses.replace`), `street_ttm_eps` ÷ ρ; each present figure gets a note and `"split-scaled"`. Otherwise all three are left as stored. Without Q, left as stored; the sentence says so.
3. **The consensus**: with S the post-split count (D × ρ when the statements were scaled, else D) and P = S ÷ ρ: for each annual and quarterly row with an EPS and a net-income mean, the implied count I = net_income ÷ eps; the row's EPS becomes eps ÷ ρ when `within(I, P)` and not `within(I, S)`; a row with no net-income mean, or within both or neither, is left alone. Notes name the scaled rows (`"EPS ÷ 2 for fiscal 2026 to 2028"` on `estimates_annual`, `"EPS ÷ 2 for the quarters to 30 Sep 2027"` on `estimates_quarter`, the span from the first to the last scaled row). Without a count D, P and S are `None` and the consensus is left alone.
4. **GuruFocus**: `gf_eps_ttm` and `gf_eps_without_nri` each ÷ ρ when its `as_of` is before the earliest pending split's date (the figure predates the split); the pending ratio for a GuruFocus figure is the product of the pending splits dated after its `as_of`.
5. **The flag**: code `split-pending`, word `"Split pending"`. The sentence, built from parts, each present only when it applies, joined by one space:
   - the head: `"A 2-for-1 split of 28 Jan 2027 falls after the newest statement (30 Sep 2026)."` — several splits: `"A 2-for-1 split of 28 Jan 2027 and a 3-for-2 split of 2 Feb 2027 fall after the newest statement (30 Sep 2026)."`; dates as `"%-d %b %Y"`.
   - the statement side: `"The diluted count (×2), the trailing EPS and the street actuals (÷2) are read on the post-split basis."` when scaled; `"FMP's statements and street actuals already read on the post-split basis."` when the test says post-split; `"The quote gives no share count, so the statements are read as stored."` without Q. A non-whole ratio prints to two decimals (`×1.5`).
   - the consensus: `"The consensus EPS for fiscal 2026 to 2028 and for the quarters to 30 Sep 2027 is read ÷2."` for scaled rows (either span alone when only one series scaled); `"The consensus EPS for fiscal 2029 has no net-income mean and is read as stored."` naming the rows left for lack of a mean (annual by fiscal year, quarterly by period end); nothing when no row needed scaling.
   - GuruFocus: `"GuruFocus's EPS observed 25 Jan 2027 is read ÷2."` when scaled.
   - the tail, always: `"The closes and the quote are FMP's, already on it."`
6. `build_inputs` reads the quote's `market_cap` and `price` observations for Q (the `quote` dataset alone, not the profile or the universe row), the two GuruFocus rows' `as_of`, runs `apply_splits` after it has read every figure above and before it builds `CompanyInputs`, and uses `outcome.figures` in place of the read figures; `input_flags` gains the flag after the statements' flags (`flags + (flag,)`); `notes.update(outcome.notes)`; `estimate_methods = {**stated.estimate_methods, **outcome.estimate_methods}`. No split on file, or none pending: every figure as read, no flag, no note.

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_splits.py`

The pure rule, on spec 13.4's numbers (a split of 2 dated 2026-10-15 between a quarter ending 30 Sep and a price of 30 Oct):

```python
SPLIT = SplitRow(date(2026, 10, 15), 2.0, 1.0)
END, PRICE_DATE = date(2026, 9, 30), date(2026, 10, 30)


def _trailing(eps: float) -> TrailingFigures: ...  # period_end END, quarters 4, eps_diluted eps, the rest None


def _figures(count: float = 1000.0, eps: float = 4.0, street: float = 4.2) -> SplitFigures: ...


def _annual(year: int, eps: float, net_income: float | None) -> AnnualEstimate: ...


def _apply(figures: SplitFigures, splits=(SPLIT,), market_cap: float | None = 2000.0 * 50, price: float | None = 50.0) -> SplitOutcome:
    return apply_splits(figures, splits, statement_end=END, price_date=PRICE_DATE, quote_market_cap=market_cap, quote_price=price, tolerance=0.15)


def test_pending_splits_window() -> None:
    """A split after the newest statement and at or before the price date is pending; one on
    the price date is; one the day after is not; one on the statement end is not."""
    assert pending_splits([SPLIT], END, PRICE_DATE) == (SPLIT,)
    assert pending_splits([SplitRow(PRICE_DATE, 2, 1)], END, PRICE_DATE) == (SplitRow(PRICE_DATE, 2, 1),)
    assert pending_splits([SplitRow(date(2026, 10, 31), 2, 1)], END, PRICE_DATE) == ()
    assert pending_splits([SplitRow(END, 2, 1)], END, PRICE_DATE) == ()
    assert pending_splits([SPLIT], None, PRICE_DATE) == () and pending_splits([SPLIT], END, None) == ()


def test_the_statements_are_scaled_when_the_quote_shows_them_pre_split() -> None:
    """Spec 13.4: a count of 1,000 reads 2,000; the trailing EPS of $4 reads $2; the street
    actuals $4.20 read $2.10; each is noted and an estimate under split-scaled."""
    out = _apply(_figures())
    f = out.figures
    assert (f.shares_diluted, f.trailing.eps_diluted, f.street_ttm_eps) == (2000.0, 2.0, 2.1)
    assert set(out.notes) >= {"shares_diluted", "statements", "street_ttm_eps"}
    assert out.estimate_methods == {"shares_diluted": "split-scaled", "statements": "split-scaled", "street_ttm_eps": "split-scaled"}
    assert out.flag is not None and out.flag.code == "split-pending" and out.flag.word == "Split pending"
    assert out.flag.sentence == (
        "A 2-for-1 split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). "
        "The diluted count (×2), the trailing EPS and the street actuals (÷2) are read on the "
        "post-split basis. The closes and the quote are FMP's, already on it."
    )


def test_the_statements_are_left_alone_when_fmp_has_restated_them() -> None:
    """The vendor finding of 2026-11-10: a count of 2,000 against a quote count of 2,000 is
    post-split; nothing is scaled and the sentence says so; the flag still fires."""
    out = _apply(_figures(count=2000.0, eps=2.0, street=2.1))
    assert out.figures == _figures(count=2000.0, eps=2.0, street=2.1)
    assert out.notes == {} and out.estimate_methods == {}
    assert out.flag is not None and "FMP's statements and street actuals already read on the post-split basis." in out.flag.sentence


def test_without_the_quotes_count_the_statements_are_read_as_stored() -> None:
    out = _apply(_figures(), market_cap=None)
    assert out.figures.shares_diluted == 1000.0
    assert "The quote gives no share count, so the statements are read as stored." in out.flag.sentence
    assert _apply(_figures(), price=0.0).figures.shares_diluted == 1000.0


def test_the_consensus_is_scaled_by_its_implied_count() -> None:
    """Spec 13.4: $4.20 on a net-income mean of 4,200 implies 1,000, the pre-split count, so it
    reads $2.10; $2.10 implying 2,000 is left alone; a row without a mean is left alone and
    named."""
    rows = (_annual(2026, 4.2, 4200.0), _annual(2027, 2.1, 4200.0), _annual(2028, 4.4, None))
    out = _apply(replace(_figures(), annual_estimates=rows))
    assert [a.eps for a in out.figures.annual_estimates] == [2.1, 2.1, 4.4]
    assert out.notes["estimates_annual"] == "EPS ÷ 2 for fiscal 2026"
    assert "The consensus EPS for fiscal 2026 is read ÷2." in out.flag.sentence
    assert "The consensus EPS for fiscal 2028 has no net-income mean and is read as stored." in out.flag.sentence


def test_the_consensus_test_reads_the_post_split_count_when_the_statements_were_restated() -> None:
    """With the count already 2,000 (restated), a row implying 1,000 is pre-split and scales;
    one implying 2,000 stands."""
    rows = (_annual(2026, 4.2, 4200.0), _annual(2027, 2.1, 4200.0))
    out = _apply(replace(_figures(count=2000.0, eps=2.0, street=2.1), annual_estimates=rows))
    assert [a.eps for a in out.figures.annual_estimates] == [2.1, 2.1]


def test_quarterly_rows_scale_too_and_the_spans_read_first_to_last() -> None:
    # three annual rows 2026 to 2028 all implying 1,000 and two quarterly rows ending 2026-12-31
    # and 2027-03-31 implying 1,000: the notes read "EPS ÷ 2 for fiscal 2026 to 2028" and
    # "EPS ÷ 2 for the quarters to 31 Mar 2027"; the sentence "The consensus EPS for fiscal
    # 2026 to 2028 and for the quarters to 31 Mar 2027 is read ÷2."
    ...


def test_a_row_within_both_counts_is_left_alone() -> None:
    """An 11-for-10 split: 1,000 and 1,100 lie within 15% of each other, so the implied count
    cannot tell the bases apart and the row stands."""
    small = SplitRow(date(2026, 10, 15), 11.0, 10.0)
    rows = (_annual(2026, 4.2, 4200.0),)
    out = _apply(replace(_figures(count=1000.0), annual_estimates=rows), splits=(small,), market_cap=1100.0 * 50)
    assert out.figures.annual_estimates[0].eps == 4.2
    # the count itself: 1,000 × 1.1 = 1,100 is within 15% of Q, but so is 1,000: left alone
    assert out.figures.shares_diluted == 1000.0


def test_gurufocus_figures_scale_by_observation_date() -> None:
    before, after = date(2026, 10, 10), date(2026, 10, 20)
    out = _apply(replace(_figures(), gf_eps_ttm=6.0, gf_eps_ttm_as_of=before, gf_eps_without_nri=5.8, gf_eps_without_nri_as_of=after))
    assert (out.figures.gf_eps_ttm, out.figures.gf_eps_without_nri) == (3.0, 5.8)
    assert out.notes["gf_eps_ttm"] and "gf_eps_without_nri" not in out.notes
    assert "GuruFocus's EPS observed 10 Oct 2026 is read ÷2." in out.flag.sentence


def test_a_reverse_split_multiplies_the_per_share_figures() -> None:
    reverse = SplitRow(date(2026, 10, 15), 1.0, 10.0)
    out = _apply(_figures(count=1000.0, eps=4.0, street=4.2), splits=(reverse,), market_cap=100.0 * 50)
    f = out.figures
    assert (f.shares_diluted, f.trailing.eps_diluted, f.street_ttm_eps) == (100.0, 40.0, 42.0)
    assert out.flag.sentence.startswith("A 1-for-10 reverse split of 15 Oct 2026 falls after the newest statement (30 Sep 2026). The diluted count (×0.1), the trailing EPS and the street actuals (÷0.1)")


def test_two_pending_splits_compound() -> None:
    two = (SPLIT, SplitRow(date(2026, 10, 20), 3.0, 2.0))
    out = _apply(_figures(), splits=two, market_cap=3000.0 * 50)
    assert out.figures.shares_diluted == 3000.0 and out.figures.trailing.eps_diluted == pytest.approx(4 / 3)
    assert out.flag.sentence.startswith("A 2-for-1 split of 15 Oct 2026 and a 3-for-2 split of 20 Oct 2026 fall after the newest statement (30 Sep 2026). The diluted count (×3),")


def test_no_pending_split_changes_nothing() -> None:
    old = SplitRow(date(2019, 5, 20), 2.0, 1.0)
    out = _apply(_figures(), splits=(old,))
    assert out == SplitOutcome(_figures(), None, {}, {})
    assert _apply(_figures(), splits=()) == SplitOutcome(_figures(), None, {}, {})
```

The wiring, through the Store fixture. ACME's synthetic statements (`synthetic.py`) hold five quarters, 2025-09-30 to 2026-09-30, quarter i with diluted shares 100 m + i m and EPS 0.45 + 0.01 × i, and a street actual of 0.50 + 0.01 × i; so the newest quarter has 104 m shares, the trailing four quarters (i = 1 to 4) sum to an EPS of 1.90 and a street EPS of 2.10. The fixture quote has price 50 and market cap 5,000 m (a count of 100 m); the fixture's annual consensus rows read EPS 2.0, 2.2, 2.4 on net income 200 m, 220 m, 240 m (fiscal 2026 to 2028), the quarterly rows 0.52, 0.54, 0.56 on 52 m, 54 m, 56 m. Redefine `test_inputs.py`'s three-line `build` helper in this file rather than import it from a test module:

```python
def _quote(price: float, count: float) -> list[dict[str, Any]]:
    # the ACME quote fixture with price and marketCap = price × count, the same timestamp
    ...


def test_build_inputs_reads_a_pending_split(store: Store) -> None:
    """ACME split 2-for-1 on 2026-10-15, after its newest quarter (30 Sep 2026) and before its
    quote (30 Oct 2026); the quote shows 208 m shares against 104 m stored, so the statements
    are pre-split and scale; the fixture's consensus rows imply 100 m, within 15% of 104 m,
    and scale; the GuruFocus figures, observed at the fetch (1 Nov 2026), stand."""
    conn = store(**bodies(), splits=[{"symbol": "ACME", "date": "2026-10-15", "numerator": 2, "denominator": 1}], quote=_quote(25.0, 208 * M))
    inputs = build(conn)
    assert inputs.shares_diluted == pytest.approx(208 * M)
    assert inputs.trailing is not None and inputs.trailing.eps_diluted == pytest.approx(0.95)  # 1.90 halved
    assert inputs.street_ttm_eps == pytest.approx(1.05)  # 2.10 halved
    assert [a.eps for a in inputs.annual_estimates] == pytest.approx([1.0, 1.1, 1.2])  # implied 100 m, within 15% of 104 m
    assert [q.eps for q in inputs.quarter_estimates] == pytest.approx([0.26, 0.27, 0.28])
    assert inputs.gf_eps_ttm == 6.11
    assert "split-pending" in [f.code for f in inputs.input_flags]
    assert inputs.estimate_methods["shares_diluted"] == "split-scaled"
    assert inputs.notes["shares_diluted"] == "×2 for the 2-for-1 split of 15 Oct 2026"
    assert inputs.market_cap == pytest.approx(25.0 * 208 * M) and inputs.price == 25.0


def test_build_inputs_without_a_pending_split_is_unchanged(store: Store) -> None:
    """The fixture's 2019 split predates every statement: nothing moves and no flag fires; the
    same when the splits call failed (no rows)."""
    plain = build(store(**bodies()))
    assert "split-pending" not in [f.code for f in plain.input_flags] and "shares_diluted" not in plain.notes
    # a failed splits call: router.fail.add("splits") before the store call
    ...


def test_the_flag_reaches_the_snapshot(store: Store) -> None:
    # value_company on the split inputs with DECILES: "split-pending" among result.flags and the
    # shares_diluted DATA input's note is the split note
    ...
```

The quote helper copies `tests/fixtures/fmp/quote.ACME.json` with `price` and `marketCap` replaced (keep its `timestamp`, 30 Oct 2026, which gives the price date).

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest -q tests/refresh/test_splits.py`
Expected: FAIL on imports (`SplitFigures`, `apply_splits`, `pending_splits`).

- [ ] **Step 3: Implement the rule and wire it**

`inputs_splits.py`'s docstring states the rule as the Interfaces block does, with the vendor findings in two sentences. `build_inputs` as item 6 says; its module docstring gains the bullet "the stock splits: a split dated after the newest statement period end and at or before the price date puts every share count and per-share figure on the quote date's basis (`inputs_splits`), with the `split-pending` note".

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest -q tests/refresh/test_splits.py tests/refresh tests/engine`
Expected: PASS, the goldens included.

- [ ] **Step 5: The documents**

`docs/method.md`:
- 4.2, a new paragraph after the share count's: "**Stock splits.** Every share count and per-share figure is read on the share basis of the quote date. A split on file (section 2) dated after the newest statement period end and at or before the price date is pending, and the row carries the note `split-pending` (section 8). FMP restates its statements, street actuals, consensus and closes to the new basis, but not on a known day, so the rule scales only what the data shows pre-split: the diluted count, the trailing diluted EPS and the street trailing EPS when the count times the split ratio, and not the count itself, lies within `split_implied_count_tolerance` (15%) of the quote's own count (market cap ÷ price); each consensus EPS, annual or quarterly, when its implied count (the net-income mean ÷ the EPS mean) lies within the tolerance of the pre-split count and not of the post-split one, a row without a net-income mean left as stored; GuruFocus's trailing EPS and EPS without non-recurring items when observed before the split. The closes are FMP's, already adjusted. Several pending splits compound. A scaled input is an estimate under the method `split-scaled` and carries a note. A price refresh applies no split rule: on a split day the stored value meets the new quote until the next refresh that runs assembly, and the remedy is a scoped refresh of the company (section 10)."
- 8, the flags table, a row after `consensus-basis-unknown`: `| `split-pending` | no | a split on file falls after the newest statement period end and at or before the price date (4.2); the sentence names the split, its date and ratio, and each figure read on the post-split basis, or that FMP's figures already read on it; fires until the newest statement period end passes the split date |`.
- 10: the Price refresh bullet gains "; it applies no split rule (4.2): a split between the stored statements and the new quote waits for a scoped refresh, which fetches the company's statements, closes and splits again and runs assembly"; the Full/Scoped text names the splits among the data.
- 11: the `1.0, policy v10` row's text gains a final sentence: "Plan 2 (2026-11-10): the `splits` dataset (section 2) and the split basis of 4.2 with the `split-pending` note; no version change, since no figure moves until a split is on file."

`methodology.html`: in the notes list, after the `consensus-basis-unknown` item:

```html
<li><span class="label">Split pending</span> <code class="fb-tag figure-sm">split-pending</code>
<span class="body app-flags__what">A stock split falls between the newest statement and the quote,
so the share count and the per-share figures are read on the new basis.</span></li>
```

Run `uv run pytest -q tests/web/test_methodology.py`: a test may pin every flag code the method names onto the page, and the sentence limit is 25 words.

- [ ] **Step 6: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

```bash
git add -A
git commit -m "Read every share count and per-share figure on the quote date's basis when a split falls after the newest statement, with the split-pending note (spec 2026-11-09 10.2)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: The playbook, the spec's decision log and the backlog

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (step 3; the flags list), `playbook/fairband-research/reference/tools.md` (one line where the `company` result's inputs or flags are described)
- Modify: `docs/superpowers/specs/2026-11-09-engine-round-2-design.md` (the decision log), `docs/backlog.md` (B-143 to Done)
- Test: `tests/test_playbook.py` and `tests/test_method_doc.py` pin the playbook's and the method document's shape; run the suite

- [ ] **Step 1: The playbook**

Step 3, after "A scoped refresh fetches the company's price and statements again and values it. It takes about a minute.", a paragraph: "When a stock split is announced or recent, the scoped refresh is the only remedy: a price refresh reprices the stored pre-split value at a post-split quote, which reads as a fall of half. After the refresh read `split-pending` on the row: it names the split and each figure read on the new basis, or that FMP's figures already read on it. The consensus and the guidance record move to the new basis on their own days, so a step or a guided figure that looks halved may be one not yet restated."

The flags list (after `step-series-disagree`): "- `split-pending`: a split falls between the newest statement and the quote. The sentence names what was read on the post-split basis (the count, the trailing EPS, the consensus EPS by year, GuruFocus's EPS) or that FMP's figures already read on it. Check the consensus steps and any guided figure against the new basis before you read them; a figure the sentence names as read as stored for lack of a net-income mean may be on the old basis."

`reference/tools.md`: where the inputs' notes or estimate methods are described, add that a split-scaled input carries the method `split-scaled` and a note naming the split.

- [ ] **Step 2: The spec's decision log and the backlog**

Append to the spec's decision log one row dated 2026-11-10 with the four vendor findings and the rulings of "The vendor findings" above, in that section's register (one row, `|`-free text). In `docs/backlog.md`, move B-143 from Now to the top of Done with the commits of Tasks 1 and 2 (`git log --oneline -3`), as B-149's row was moved.

- [ ] **Step 3: Run the checks and commit**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

```bash
git add -A
git commit -m "Tell the agent to start a scoped refresh on a split and read split-pending, record the vendor findings in the spec's decision log and close B-143

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: The live steps and the readout (the controller, after the merge)

Not a subagent task. After the final review and the merge to main by fast-forward, pushed:

- [ ] Restart the server on 8470 from main (`setsid nohup uv run python -m fairband serve >> ~/.local/share/fairband/server.log 2>&1 < /dev/null &`; stop the old one by its `python -m fairband serve` PIDs, never by a pattern that matches the shell). No backup: the schema and the method version are unchanged, and the morning's backup stands.
- [ ] One scoped refresh of NVDA, AVGO, WMT and META (`POST /api/refresh` with `{"kind": "scoped", "symbols": [...]}` and the header `X-Fairband-Request: 1`; poll `/api/refresh/current`). Read, read-only: the `split` observations each now holds (NVDA 6, WMT 10, META 0 expected), that no `split-pending` fired (every split predates the newest statement), and that the four rows' values moved only as a fetch of fresh data moves them.
- [ ] Record in the spec's decision log: the refresh id, the splits on file, the flags, and that META's acceptance (10.3) waits for a scoped refresh after late January 2027 and is on the backlog as a dated note.
- [ ] Update the memory file for the engine round 2 (plan 2 done; B-28 next).
