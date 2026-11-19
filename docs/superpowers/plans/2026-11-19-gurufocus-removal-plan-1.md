# GuruFocus Removal, Plan 1: Altman's Z″, the ADR Ratio, the P/E Series

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fairband stops storing GuruFocus's Z″, finds an ADR's ratio from FMP's two share counts, and builds the daily trailing P/E series from FMP's closes and EPS; no value moves.

**Architecture:** The listed-share basis rule keeps its factor logic and gains a step before it that finds the ratio from the counts of a flagged ADR. The P/E history keeps its read, its refs and its statistics; only its source changes, from one GuruFocus answer to three FMP answers stored under names of their own and turned into a series by a pure function. The GuruFocus `summary` and `keyratios` calls keep running: plans 2 and 3 remove them.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, httpx; plain JavaScript pages with no build step; pytest, with node for the pages' scripts (`tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-19-gurufocus-removal-design.md`, sections 3, 5, 6, 10, 11, 12, 13 and 14. Read it with your task: this plan argues from it, and where the two differ the spec wins. The decisions behind it are in `docs/gurufocus-removal.md`, sections 3, 4 and 5; do not reopen one. Where the spec and the code disagree in a way that changes a task, stop and report.

**A map of the code as it stands:**

- `src/fairband/vendors/normalize_gf.py`: `_SUMMARY` names the three fields of the `gf-score` dataset (`moat_score`, `z2score`, `depositary_receipt_ratio`); `summary_observations`; `pe_ttm_rows(payload)`, the P/E rows.
- `src/fairband/vendors/gurufocus.py`: `GuruFocus.summary`, `.keyratios`, `.pe_ttm`; `PROVIDER = "gf"`, `PE_TTM = "pettm"`.
- `src/fairband/refresh/inputs_splits.py`: `apply_splits(figures, splits, *, statement_end, price_date, quote_market_cap, quote_price, tolerance, adr_ratio=None) -> SplitOutcome`. Its gate runs `_basis_side` only when `adr_ratio` is neither `None`, 0 nor 1. `_basis_side` finds the diluted count's factor (`_factor`: 1, ρ, 1 ÷ ρ), reads each period (`_read_periods`), writes the notes (`_relation`, `_adr`, `_basis_note`, `_basis_scaled`) and the refusal. `_within(a, b, tolerance)`, `_after(splits, day)`, `_ratio(splits)`, `pending_splits` are its helpers. `SplitOutcome` holds `figures`, `flag`, `notes`, `estimate_methods`, `basis_flag`, `refusal`.
- `src/fairband/refresh/inputs.py`: `build_inputs` reads `is_adr = _adr_flag(profile, company) is True`, then `adr_ratio = cite("adr_ratio", _adr_ratio(scores))` from the `gf-score` observations, and passes the ratio to `apply_splits`. `is_adr` is not passed today.
- `src/fairband/engine/route.py`: `_base_inputs` writes the DATA input `adr_ratio` when `i.is_adr or i.adr_ratio is not None`.
- `src/fairband/refresh/passthrough.py`: `KINDS` (seven, `pe-history` last), `_Call(part, endpoint, params, send, provider, reuse, ages, usable)`, `Passthrough(fmp, conn_factory, policy, clock, secrets, gurufocus=None)`, `.fetch(kind, symbol, params) -> dict[str, Fetched]`, `PassthroughNoKey`, `NO_GF_KEY`, `PE_HISTORY_REUSE_HOURS`, `_reads_as_series`.
- `src/fairband/reports/multiples.py`: `Series(points, stats, since)`, `trailing_series(payload)`, `forward_series(rows)`, `stored_trailing(conn, symbol)`, `stored_series(conn, symbol, name)`, `_series(rows)` (the ten-year window and the four statistics), `years_before`.
- `src/fairband/web/multiples_api.py`: `GET /api/companies/{symbol}/multiples-history`, `_trailing`. `src/fairband/web/vendor_api.py`: `GET /api/vendor/{kind}/{symbol}` for a kind in `KINDS`.
- `src/fairband/mcp/server.py`: `TOOL_NAMES` (55), `pe_history`, `multiples_history`.
- `src/fairband/vendors/fmp.py`: `Fmp.price_history(symbol, start)`, `.statement(symbol, kind, period, limit)`, `.fx_history(pair, start)`. `src/fairband/vendors/normalize_fmp_observations.py`: `price_closes(payload)`, `fx_closes(payload)`.
- `src/fairband/refresh/inputs_statements.py`: `cadence_of(ends) -> Cadence | None`. `src/fairband/engine/anchor.py`: `consecutive_periods(ends, cadence)`, `PERIODS_PER_YEAR`. `src/fairband/store/currency.py`: `reporting_currency(conn, symbol) -> str`.
- `src/fairband/web/static/app.js`: `currencyLine(body, perAds)` and `adsWords(ratio)`.
- `src/fairband/engine/__init__.py`: `METHOD_VERSION = "fairband-mechanical/1.5"`. Its literal copies: `tests/engine/test_types.py`, `tests/engine/test_route.py` (two), `tests/support/research_answers.py` (two), `tests/reports/test_render.py`, the goldens of `tests/fixtures/golden/` (`tests/engine/test_golden.py`), `docs/method.md` (the head and section 11), `docs/method-overview.md`. `tests/test_method_doc.py` pins the last row of section 11 (`rows[-1]`), and `tests/web/test_methodology.py` the examples' caption.

## Global Constraints

- No value, level, designation or settings hash moves. The policy stays `fairband-policy-v16` and the schema 009. Task 7 proves the first on the reference database.
- The method becomes `fairband-mechanical/1.6` in Task 2 and nowhere else.
- GuruFocus's `summary` and `keyratios` calls, the Moat Score and the two GuruFocus EPS figures keep working. This plan removes the `pettm` call, the read of the ratio and the stored Z″ only.
- `docs/method.md` and the Methodology page change in the same commit as the engine change they describe.
- Work in a git worktree, not the main checkout: the live server on port 8470 serves the page files of the main checkout as they are on disk.
- Test first: a failing test, then the code, then the passing run, then the commit.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`. A commit of documents alone runs the shorter check of `CLAUDE.md`.
- A commit message is one plain sentence in the imperative, then a blank line, then `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- No test uses the network. Fixtures are synthetic. Never commit vendor data; never print, log, store or commit a key. Nothing under `~/.local/share/fairband/` is committed, and the reference database is never written.
- Every dispatched subagent runs on Opus 5.5 at xhigh effort.
- The live steps of Task 7 need the founder's consent, asked once with the list. Nothing is pushed without his word.

## Words

| Where | Words |
|---|---|
| The refusal | `share basis unclear: the newest period's count 259.5 m against the quote's 194.9 m` |
| A count's note | `×10 to the quote's share basis: the stored count, 145.8 m, is a tenth of the quote's, 1,450.8 m (the ratio 10)` |
| An EPS's note | `÷10 to the quote's share basis (the ratio 10)`, with `on 1 of 4 quarters` as today |
| The `adr_ratio` input's note | `the whole number that brings the stored count, 145.8 m, to the quote's, 1,450.8 m` |
| The line under the drawer's head, an ADR | `Reports in TWD; an ADR: every per-share figure is per ADS; valued at TWD 32.96 per USD` |
| The ref's words, `inputs/adr_ratio` | `the ratio between FMP's stored share count and the quote's` |
| `peNote` | `no FMP key`; the busy sentence (`BUSY`); the vendor's error; `the series could not be read` |
| The Methodology page's caption | `… under method 1.4 on 14 Nov 2026 and are unchanged under methods 1.5 and 1.6.` |

## Review Focus

1. A flagged ADR whose quote holds no market cap: the rule finds no ratio and refuses nothing; the row reads as the split rule alone reads it (Task 2).
2. A trailing period with no share count among periods whose counts differ: it is passed over, and the ratio comes from the next period (Task 2).
3. FMP answers a deep call with an empty list, a company listed last month: the read answers a series with no point and a `since` of `null`, not an error (Tasks 4 and 5).
4. A quarter row whose `epsDiluted` is missing or is text: the days that need it have no point, and no exception is raised (Task 4).
5. A database that holds an old GuruFocus `pettm` answer and no `pe-closes`: `stored_trailing` answers `None`, so a ref on the old series is unresolved and the read's `pe` is `null` with its reason (Tasks 4 and 5).

---

### Task 1: Stop storing Altman's Z″ (B-255)

**Files:**
- Modify: `src/fairband/vendors/normalize_gf.py` (`_SUMMARY`, the module's docstring)
- Test: `tests/vendors/test_gurufocus.py`; `tests/store/test_observations.py` if it builds its row through the normalizer

**Interfaces:**
- Produces: `summary_observations` yields `moat_score` and `depositary_receipt_ratio` only.

- [ ] **Step 1: Write the failing test** in `tests/vendors/test_gurufocus.py`

```python
def test_summary_observations_leave_out_the_z_score() -> None:
    rows = summary_observations(_payload("summary.ACME.json"), "ACME", RESPONSE_ID, OBSERVED)
    assert {row.field for row in rows} == {"moat_score", "depositary_receipt_ratio"}
```

Use the file's own helper for loading a fixture and its own call form. The fixture keeps its `z2score` line: it is the vendor's shape.

- [ ] **Step 2: Run it.** `uv run pytest tests/vendors/test_gurufocus.py -q`. Expected: FAIL, the set holds `z2score`.
- [ ] **Step 3: Remove the `z2score` entry** from `_SUMMARY` and from the docstring. Change the assertions of the existing summary tests that name it.
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Stop storing GuruFocus's Altman Z″, which nothing reads (B-255)".

### Task 2: The ADR ratio from the two counts, under method 1.6 (B-256)

**Files:**
- Modify: `src/fairband/refresh/inputs_splits.py`, `src/fairband/refresh/inputs.py`, `src/fairband/engine/route.py` (`_base_inputs`, the `CompanyInputs` docstring), `src/fairband/engine/__init__.py`
- Modify: `docs/method.md` (2, 4.2, 5.12, 7.1, 8, 9, 11, the head), `docs/method-overview.md` (the version), `src/fairband/web/static/methodology.html` (the caption, the share basis' words)
- Test: `tests/refresh/test_splits.py`, `tests/refresh/test_inputs.py`, `tests/engine/test_route.py`, `tests/test_method_doc.py`, `tests/web/test_methodology.py`, and every file that holds the version's literal (the map)

**Interfaces:**
- Produces:
  - `found_ratio(figures: SplitFigures, pending: Sequence[SplitRow], statement_end: date | None, quote_count: float, tolerance: float) -> float | Literal["none"] | None` in `inputs_splits.py`: ρ as a float of a whole number, 2.0 or more; `"none"` when the diluted count differs and fits no whole number; `None` when no count that differs fits one.
  - `apply_splits(figures, splits, *, statement_end, price_date, quote_market_cap, quote_price, tolerance, is_adr: bool = False) -> SplitOutcome`. The parameter `adr_ratio` goes.
  - `SplitOutcome.adr_ratio: float | None = None`, the ratio found; `notes["adr_ratio"]` and `estimate_methods["adr_ratio"] == "counts-ratio"` beside it.
  - `CompanyInputs.adr_ratio` is the ratio found, else `None`; the DATA input `adr_ratio` is on a result only when it is not `None`.
  - `METHOD_VERSION == "fairband-mechanical/1.6"`.

The rule is the spec's 6.2, as `adr.py` of the research folder ran it (`plain`, `cand`, `infer`): the first multiple tried is the count against the count it is judged against, the second that with the pending splits' ratio; Python's `round`; the diluted count first, then the periods oldest first, the newest against the quote's count and each older one against the diluted count as stored.

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_splits.py`, with the file's own builders for figures and periods. The existing listed-basis tests pass `adr_ratio=`; each becomes a test of `is_adr=True` on counts that give the same ratio, or goes where no counts can give its case.

```python
def test_ratio_found_on_the_diluted_count() -> None:
    out = apply_splits(_figures(shares=145.8e6), (), **_quote(count=1_450.8e6), is_adr=True)
    assert out.adr_ratio == 10.0
    assert out.figures.shares_diluted == pytest.approx(1_458.0e6)
    assert out.notes["shares_diluted"] == (
        "×10 to the quote's share basis: the stored count, 145.8 m, is a tenth of the quote's, "
        "1,450.8 m (the ratio 10)"
    )
    assert out.notes["adr_ratio"] == (
        "the whole number that brings the stored count, 145.8 m, to the quote's, 1,450.8 m"
    )
    assert out.estimate_methods["adr_ratio"] == "counts-ratio"

def test_ratio_found_on_a_period_when_the_diluted_count_agrees() -> None:
    # the oldest quarter's count is a quarter of the diluted count; the others agree
    out = apply_splits(_figures(shares=400e6, period_shares=(100e6, 400e6, 400e6, 400e6),
                                period_eps=(4.0, 1.0, 1.0, 1.0)), (), **_quote(count=400e6),
                       is_adr=True)
    assert out.adr_ratio == 4.0
    assert out.figures.periods[0].eps_diluted == pytest.approx(1.0)

def test_inverse_ratio_reads_as_the_whole_number() -> None:
    out = apply_splits(_figures(shares=300e6), (), **_quote(count=100e6), is_adr=True)
    assert out.adr_ratio == 3.0
    assert out.figures.shares_diluted == pytest.approx(100e6)

def test_count_that_fits_no_whole_number_refuses() -> None:
    out = apply_splits(_figures(shares=259.5e6), (), **_quote(count=194.9e6), is_adr=True)
    assert out.refusal == (
        "share basis unclear: the newest period's count 259.5 m against the quote's 194.9 m"
    )
    assert out.adr_ratio is None

def test_row_without_the_flag_is_never_scaled() -> None:
    out = apply_splits(_figures(shares=145.8e6), (), **_quote(count=1_450.8e6))
    assert (out.figures.shares_diluted, out.basis_flag, out.refusal) == (145.8e6, None, None)

def test_period_that_fits_no_whole_number_is_passed_over() -> None:
    # 1.4 times: between 1 / 1.5 and 1.5, so no candidate, and no other period differs
    out = apply_splits(_figures(shares=400e6, period_shares=(286e6, 400e6, 400e6, 400e6)), (),
                       **_quote(count=400e6), is_adr=True)
    assert (out.adr_ratio, out.refusal, out.basis_flag) == (None, None, None)

def test_ratio_with_a_pending_split_reads_the_count_on_the_quotes_basis() -> None:
    # a 2-for-1 after the newest period, and a count a tenth of the pre-split ADS count
    out = apply_splits(_figures(shares=100e6), (_split(2, 1, after_newest=True),),
                       **_quote(count=2_000e6), is_adr=True)
    assert out.figures.shares_diluted == pytest.approx(2_000e6)
    assert out.adr_ratio == 20.0  # the first multiple that fits holds the split's ratio too

def test_flagged_row_without_a_quote_count_reads_as_the_split_rule_does() -> None:
    out = apply_splits(_figures(shares=145.8e6), (), **_quote(count=None), is_adr=True)
    assert (out.adr_ratio, out.refusal) == (None, None)

def test_period_without_a_count_is_passed_over() -> None:
    out = apply_splits(_figures(shares=400e6, period_shares=(None, 100e6, 400e6, 400e6)), (),
                       **_quote(count=400e6), is_adr=True)
    assert out.adr_ratio == 4.0
```

- [ ] **Step 2: Run them.** `uv run pytest tests/refresh/test_splits.py -q`. Expected: FAIL, `apply_splits` takes no `is_adr`.
- [ ] **Step 3: Write `found_ratio`** and the gate of `apply_splits`: without the flag, a quote count or a diluted count, `_split_rule` alone; `"none"` gives the refusal; `None` gives `_split_rule` alone; a ratio runs `_basis_side` with it, as today, and the outcome carries it. `_basis_side`'s own refusal and `_adr` print no `ADR`: `_adr(ratio)` returns `" (the ratio 10)"`, and the words on ADSs to a share go.
- [ ] **Step 4: Run them.** Expected: PASS. The readers of the refusal match its lead, "share basis unclear" (`store.secondary.cannot_fix`, the playbook's refusals), so the new sentence and a stored old one both pass. The tests that hold the old sentence as a stored snapshot's refusal keep it; add the new sentence beside it in `tests/store/test_secondary_store.py`.
- [ ] **Step 5: Write the failing tests of assembly and the input** in `tests/refresh/test_inputs.py` and `tests/engine/test_route.py`:

```python
def test_assembly_finds_the_ratio_of_a_flagged_adr(...) -> None:
    # the profile's is_adr 1, statements at 145.8 m shares, a quote whose count is 1,450.8 m,
    # and a stored gf-score depositary_receipt_ratio of 5, which must not be read
    inputs = build_inputs(conn, "CXCO", policy, tax, TODAY, deciles)
    assert inputs.adr_ratio == 10.0
    assert inputs.estimate_methods["adr_ratio"] == "counts-ratio"
    assert inputs.provenance["adr_ratio"].source == inputs.provenance["price"].source

def test_assembly_reads_no_ratio_where_the_counts_agree(...) -> None:
    assert build_inputs(conn, "ADRCO", policy, tax, TODAY, deciles).adr_ratio is None

def test_an_adr_whose_counts_agree_carries_no_adr_ratio_input() -> None:
    result = value_company(replace(_inputs(), is_adr=True, adr_ratio=None), DECILES, POLICY, TODAY)
    assert "adr_ratio" not in {i.name for i in result.inputs}
```

- [ ] **Step 6: Run them, then change assembly and `_base_inputs`.** `_adr_ratio` goes from `inputs.py`; `apply_splits` gets `is_adr=is_adr`; `adr_ratio` is `split.adr_ratio`, cited to the quote's provenance. `_base_inputs` writes the input when `i.adr_ratio is not None`. Run: PASS.
- [ ] **Step 7: Set `METHOD_VERSION` to `fairband-mechanical/1.6`**, change each literal copy (`grep -rn "fairband-mechanical/1\.5" src tests docs/method*.md` finds them: the map's list and `tests/support/page_answers.py` among them), and make the goldens again as `tests/fixtures/golden/README.md` says. Read the goldens' diff: the version line alone changes.
- [ ] **Step 8: Change `docs/method.md`.** 4.2's listed-share basis takes the spec's text of 6.2 with its limits; 5.12 and 7.1 the input as the spec has it; section 2's GuruFocus row loses the ratio; section 8's `basis-scaled` row and section 9's refusal row as the spec has them, the refusal row naming the old ending on a snapshot valued before 1.6; the head's version; a row in section 11: "1.6, policy v16 | 2026-11-<day> | The ADR ratio from FMP's two share counts (spec 2026-11-19 6.2) …", saying that no vendor's ratio is read, that the flag guards the rule, and that no value moved on refresh 68. Move the pin of `tests/test_method_doc.py` from the 1.5 row to the 1.6 row, keeping the 1.5 row's assertions on `rows[-2]`.
- [ ] **Step 9: Change the Methodology page**: the caption by the Words table, and the share basis' words where they say a vendor states the ratio. Change the caption's test in `tests/web/test_methodology.py`.
- [ ] **Step 10: Run the full check.** Expected: PASS.
- [ ] **Step 11: Commit.** "Find an ADR's ratio from FMP's two share counts under method 1.6, with FMP's ADR flag as the rule's guard, in place of GuruFocus's ratio (B-256)".

### Task 3: The ratio's words on the pages, in the refs and in the playbook

**Files:**
- Modify: `src/fairband/web/static/app.js` (`currencyLine`, `adsWords`), `src/fairband/web/app.py` (the docstring of the company read), `src/fairband/reports/refs.py` (the words of `inputs/adr_ratio`, the docstring), `src/fairband/mcp/server.py` (`company`'s description)
- Modify: `playbook/fairband-research/SKILL.md`, `playbook/fairband-research/reference/tools.md`, `playbook/fairband-research/reference/citations.md`
- Test: `tests/web/test_drawer_currency.py`, `tests/reports/test_refs.py`, `tests/test_playbook.py`

**Interfaces:**
- Consumes: Task 2's `adrRatio` (the ratio found, or `null`) and its refusal text.
- Produces: `currencyLine(body, perAds)` names no ratio; `adsWords` is gone.

- [ ] **Step 1: Write the failing page test** in `tests/web/test_drawer_currency.py`, in the file's own form:

```python
def test_an_adr_line_names_no_ratio() -> None:
    assert _line({"currency": "TWD", "isAdr": True, "adrRatio": None, "fxRate": 32.96}) == (
        "Reports in TWD; an ADR: every per-share figure is per ADS; valued at TWD 32.96 per USD"
    )
    assert "ratio" not in _line({"currency": "USD", "isAdr": True, "adrRatio": 10})
```

- [ ] **Step 2: Run it** (FAIL: "the ADR ratio is not on file"), **then change `currencyLine`** and remove `adsWords` with `NUMBER_WORDS` if nothing else reads it. The Research tab's `perAds` form says the same sentence once, not twice.
- [ ] **Step 3: Change the ref's words** in `refs.py` by the Words table, with its test.
- [ ] **Step 4: Change the playbook's nine places** (the spec's section 5, "Smaller differences"): `adrRatio` is "the whole number Fairband found between FMP's stored share count and the quote's, `null` where the counts agree"; the `basis-scaled` entry says the ratio comes from the two counts; the refusal sentence loses its ending. `tests/test_playbook.py` pins `adrRatio`, the entry and the refusal (`BASIS_UNCLEAR`): move each pin to the new words. Lines stay at 100 characters or fewer.
- [ ] **Step 5: Run the full check, then commit.** "Say on the pages, in the refs and in the playbook that an ADR's ratio comes from the two share counts".

### Task 4: The P/E series as a pure function

**Files:**
- Modify: `src/fairband/reports/multiples.py`
- Test: `tests/reports/test_multiples.py` (create)

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class PeriodEps:
    end: date
    eps: float | None        # epsDiluted; None when the line is missing or no number
    currency: str | None     # reportedCurrency

def period_eps(payload: Any) -> list[PeriodEps] | None      # oldest first; None for no list
def built_rows(
    closes: Sequence[tuple[date, float]],
    periods: Sequence[PeriodEps],
    currency: str,                                  # the reporting currency
    rates: Sequence[tuple[date, float]] | None,     # units of the currency per USD; None for USD
) -> list[tuple[date, float | None]]                # a loss day is (day, None)
def built_series(closes, periods, currency, rates) -> Series    # _series(built_rows(...))
```

The rule is the spec's text for `method.md` 16.7. The cadence is `cadence_of` on the periods' ends, quarterly when the rows give none. A day is a row when it has a trailing EPS, a loss among them; a day without one (too few periods, periods not consecutive by `consecutive_periods`, a period without its EPS, a period in another currency than `currency`, no rate at or before the day) is no row.

- [ ] **Step 1: Write the failing tests** in `tests/reports/test_multiples.py`:

```python
Q = [date(2025, 3, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31),
     date(2026, 3, 31)]

def _periods(eps, currency="USD", ends=Q):
    return [PeriodEps(end, e, currency) for end, e in zip(ends, eps)]

def test_the_eps_steps_at_a_period_end() -> None:
    closes = [(date(2026, 3, 30), 100.0), (date(2026, 3, 31), 100.0)]
    rows = built_rows(closes, _periods([1.0, 1.0, 1.0, 1.0, 2.0]), "USD", None)
    assert rows == [(date(2026, 3, 30), 25.0), (date(2026, 3, 31), 20.0)]

def test_a_loss_day_is_a_row_with_no_point() -> None:
    series = built_series([(date(2026, 1, 5), 50.0)], _periods([1.0, -1.0, -1.0, -1.0]),
                          "USD", None)
    assert (series.points, series.since) == ((), date(2026, 1, 5))
    assert series.stats == dict.fromkeys(STATS)

def test_a_half_yearly_reporter_sums_two_periods() -> None:
    ends = [date(2024, 12, 31), date(2025, 6, 30), date(2025, 12, 31)]
    rows = built_rows([(date(2026, 1, 5), 60.0)], _periods([9.0, 1.0, 2.0], ends=ends),
                      "USD", None)
    assert rows == [(date(2026, 1, 5), 20.0)]

def test_another_currency_reads_the_close_at_the_days_rate() -> None:
    closes = [(date(2026, 1, 2), 10.0), (date(2026, 1, 5), 10.0)]
    rates = [(date(2026, 1, 5), 30.0)]
    rows = built_rows(closes, _periods([3.0, 4.0, 4.0, 4.0], "TWD"), "TWD", rates)
    assert rows == [(date(2026, 1, 5), 20.0)]      # 10 × 30 ÷ 15; no rate on 2 January

def test_periods_that_are_not_consecutive_give_no_row() -> None:
    ends = [date(2024, 12, 31), date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31)]
    assert built_rows([(date(2026, 1, 5), 50.0)], _periods([1.0] * 4, ends=ends),
                      "USD", None) == []

def test_a_period_in_another_currency_gives_no_row() -> None:
    periods = [*_periods([1.0] * 3), PeriodEps(Q[3], 1.0, "CAD")]
    assert built_rows([(date(2026, 1, 5), 50.0)], periods, "USD", None) == []

def test_a_period_without_its_eps_gives_no_row() -> None:
    assert built_rows([(date(2026, 1, 5), 50.0)], _periods([1.0, None, 1.0, 1.0]),
                      "USD", None) == []

def test_period_eps_reads_text_and_missing_lines_as_none() -> None:
    payload = [{"date": "2025-12-31", "epsDiluted": "n/a", "reportedCurrency": "USD"},
               {"date": "2025-09-30", "reportedCurrency": "USD"}]
    assert [p.eps for p in period_eps(payload)] == [None, None]
    assert period_eps({"error": "x"}) is None

def test_no_close_and_no_period_give_an_empty_series() -> None:
    series = built_series([], [], "USD", None)
    assert (series.points, series.since) == ((), None)
```

- [ ] **Step 2: Run them.** `uv run pytest tests/reports/test_multiples.py -q`. Expected: FAIL, the names are not defined.
- [ ] **Step 3: Write `PeriodEps`, `period_eps`, `built_rows` and `built_series`.** For each day, find the newest period at or before it with a binary search over the period ends; the trailing sums are computed once a period, not once a day.
- [ ] **Step 4: Run them.** Expected: PASS.
- [ ] **Step 5: Commit.** "Build the daily trailing P/E series from closes and quarterly EPS as a pure function (B-257)".

### Task 5: The three FMP answers through the pass-through, and the stored series

**Files:**
- Modify: `src/fairband/refresh/passthrough.py`, `src/fairband/reports/multiples.py` (`trailing_series`, `stored_trailing`), `src/fairband/__main__.py` (`_serve` passes no GuruFocus client to `Passthrough`; `_NO_GF_KEY` loses its words on the pass-through)
- Test: `tests/refresh/test_passthrough.py`, `tests/reports/test_multiples.py`, `tests/reports/test_refs.py`, `tests/reports/test_charts.py`, `tests/reports/test_render.py` (the three seed the series with a `gf` / `pettm` response today)

**Interfaces:**
- Consumes: Task 4's `period_eps`, `built_series`.
- Produces:
  - `passthrough.SERIES_KIND = "pe-history"`, not in `KINDS` (six kinds, all FMP's); `PE_CLOSES = "pe-closes"`, `PE_QUARTERS = "pe-quarters"`, `PE_RATES = "pe-rates"`; `PE_YEARS = 10`, `PE_QUARTERS_LIMIT = 44`.
  - `Passthrough(fmp, conn_factory, policy, clock, secrets)`: no `gurufocus`. `PassthroughNoKey`, `NO_GF_KEY`, `PE_HISTORY_REUSE_HOURS` and `_reads_as_series` go.
  - `Passthrough.fetch("pe-history", symbol, {}) -> dict[str, Fetched]` with the parts `closes`, `quarters` and, where `reporting_currency(conn, symbol)` is not `USD`, `rates`. Logical params: `{"symbol": symbol, "years": "10"}`; `{"symbol": symbol, "period": "quarter", "limit": "44"}`; the pair's `{"symbol": "USD<code>", "years": "10"}`, stored under the pair as `fx-history` stores it. Each is reused for `reuse_hours` and usable when it is a list.
  - `trailing_series(parts: Mapping[str, Any], currency: str) -> Series | None`: the payloads by part; `None` when the closes or the quarters cannot be read.
  - `stored_trailing(conn, symbol) -> tuple[int, Series | None] | None`: the newest usable `pe-closes` and `pe-quarters` answers, and `pe-rates` for a company in another currency, whatever their age; the id is the closes answer's; `None` when the closes or the quarters are not stored. `stored_series` keeps its signature.

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_passthrough.py`, with the file's fake FMP client, replacing the tests of the GuruFocus kind:

```python
def test_pe_history_stores_closes_and_quarters_under_their_own_names(...) -> None:
    parts = passthrough.fetch("pe-history", "ACME", {})
    assert set(parts) == {"closes", "quarters"}
    assert (parts["closes"].row.provider, parts["closes"].row.endpoint) == ("fmp", "pe-closes")
    assert parts["quarters"].row.endpoint == "pe-quarters"
    assert fmp.calls == [("price_history", "ACME", years_before(TODAY, 10)),
                         ("statement", "ACME", "income", "quarter", 44)]

def test_pe_history_adds_the_pair_for_a_company_in_another_currency(...) -> None:
    assert set(passthrough.fetch("pe-history", "TWCO", {})) == {"closes", "quarters", "rates"}

def test_pe_history_is_reused_within_reuse_hours(...) -> None:
    passthrough.fetch("pe-history", "ACME", {})
    assert all(f.reused for f in passthrough.fetch("pe-history", "ACME", {}).values())

def test_the_five_year_closes_stay_the_newest_price_history(...) -> None:
    before = latest_response(conn, "fmp", "price-history", "ACME", {"symbol": "ACME"})
    passthrough.fetch("pe-history", "ACME", {})
    after = latest_response(conn, "fmp", "price-history", "ACME", {"symbol": "ACME"})
    assert after.id == before.id

def test_the_backfill_writes_no_fact_from_the_deep_quarters(...) -> None:
    passthrough.fetch("pe-history", "ACME", {})
    facts = conn.execute("SELECT count(*) FROM facts").fetchone()[0]
    backfill_statement_facts(conn, NOW)
    assert conn.execute("SELECT count(*) FROM facts").fetchone()[0] == facts
    assert conn.execute("SELECT count(*) FROM observations").fetchone()[0] == 0

def test_pe_history_is_not_a_kind_of_the_vendor_route() -> None:
    assert "pe-history" not in KINDS and len(KINDS) == 6

def test_an_empty_answer_is_stored_and_usable(...) -> None:      # Review Focus 3
    parts = passthrough.fetch("pe-history", "NEWCO", {})         # FMP answers [] to both
    assert trailing_series({k: f.payload for k, f in parts.items()}, "USD").points == ()
```

and in `tests/reports/test_multiples.py`:

```python
def test_stored_trailing_reads_the_three_answers(conn) -> None:
    closes_id = _seed(conn, "TWCO")               # pe-closes, pe-quarters and pe-rates
    stored = stored_trailing(conn, "TWCO")
    assert stored[0] == closes_id and stored[1].points

def test_stored_trailing_does_not_read_an_old_gurufocus_answer(conn) -> None:   # Review Focus 5
    record_response(conn, "gf", "pettm", {"symbol": "ACME"}, "ACME", 200, OLD_PAYLOAD, None, NOW)
    assert stored_trailing(conn, "ACME") is None
```

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Change the pass-through and the two readers.** The kind's calls are built where the connection is open, since the pair needs the reporting currency. Move the series' seeds in `test_refs.py`, `test_charts.py` and `test_render.py` to the three answers; their assertions on points and statistics change to the built figures.
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Fetch the P/E history's closes, quarters and rates from FMP under names of their own, and read the stored series from them".

### Task 6: The read, the tool that goes, and the documents

**Files:**
- Modify: `src/fairband/web/multiples_api.py` (`_trailing`, the docstring), `src/fairband/web/vendor_api.py`, `src/fairband/web/app.py` (the docstring), `src/fairband/mcp/server.py` (`pe_history` and its name in `TOOL_NAMES` go; `multiples_history`'s description)
- Modify: `src/fairband/vendors/gurufocus.py` (`pe_ttm`, `PE_TTM`), `src/fairband/vendors/normalize_gf.py` (`pe_ttm_rows`); delete `tests/fixtures/gurufocus/pettm.ACME.json`
- Modify: `docs/method.md` (16.7), `docs/agents.md`, `README.md` (the tool counts), `playbook/fairband-research/reference/tools.md`, `playbook/fairband-research/SKILL.md` where it names the series' source
- Test: `tests/web/test_multiples_api.py`, `tests/web/test_vendor_api.py`, `tests/mcp/test_server.py`, `tests/vendors/test_gurufocus.py`, `tests/test_playbook.py`

**Interfaces:**
- Consumes: Task 5's `Passthrough.fetch("pe-history", …)`, `trailing_series`, `stored_trailing`.
- Produces: `GET /api/companies/{symbol}/multiples-history` with its shape unchanged (`symbol`, `pe`, `peNote`, `peForward`; `pe.responseId` the closes answer's id); 54 tools; `GET /api/vendor/pe-history/{symbol}` answers 400 with `unknown_kind`.

- [ ] **Step 1: Write the failing tests.** In `tests/web/test_multiples_api.py`: the read builds `pe` from FMP's three answers, with the statistics of the built series; with no pass-through it serves the stored answers and `peNote == "no FMP key"`; with neither, `pe is None`; a fetched answer that cannot be read serves the stored series with `the series could not be read`. In `tests/web/test_vendor_api.py`: `client.get("/api/vendor/pe-history/ACME", headers=HEADER).status_code == 400`. In `tests/mcp/test_server.py`: `"pe_history" not in TOOL_NAMES` and `len(TOOL_NAMES) == 54`, with `SPEC_TOOLS` and `READS` changed to match.
- [ ] **Step 2: Run them, then change the read, the route and the server.** Remove `pe_ttm`, `PE_TTM`, `pe_ttm_rows` and their tests and fixture.
- [ ] **Step 3: Change the documents.** `method.md` 16.7 takes the spec's text of 6.3, with the paragraph on the fetch, the limits, and `since`. `docs/agents.md` and `README.md`: 54 tools, nine vendor reads, none from GuruFocus. `tools.md`: `multiples_history`'s entry says Fairband builds the trailing series from FMP's closes and EPS; the entry of `pe_history` and the refusal "no GuruFocus key: the pe-history pass-through is off" go; "six pass-throughs, all from FMP". `tests/test_playbook.py` loses `NO_GF_KEY` from its imports and `REFUSALS`.
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Serve the trailing P/E history from the series built on FMP's data, and remove the pe_history tool with GuruFocus's pettm call (B-257)".

### Task 7: Acceptance, the readout and the live steps

**Files:**
- Create, outside the repository: `~/.local/share/fairband/research/gurufocus-removal-2026-11-19/accept_plan1_values.py`, `accept_plan1_pe.py`
- Modify: `docs/superpowers/specs/2026-11-19-gurufocus-removal-design.md` (the decision log), `docs/backlog.md`

**Interfaces:**
- Consumes: the branch as Tasks 1 to 6 left it; the reference database `fairband-refresh-68-reference.db` in the research folder, opened with `mode=ro`.

- [ ] **Step 1: The values.** `accept_plan1_values.py` values every company of refresh 68 in memory with the branch's code, as `adr.py` there does (`effective_policy`, `load_tax_table`, `latest_deciles`, `today` the newest `data_date` of refresh 68's snapshots, then `build_inputs` and `value_company`), and compares each with the company's newest snapshot of refresh 68. Run it with `uv run python -I`. Pass, all of:
  - 1,558 rows, 1,363 of them valued; every value equals the stored one to 1e-9 of its size;
  - every refusal equals the stored one, but GDS's, which is `share basis unclear: the newest period's count 259.5 m against the quote's 194.9 m`;
  - CX is 7.49 and SIMO 95.71 to the cent;
  - the ratio found is 10 on CX, 4 on SIMO, 2 on XPEV and 3 on TAL, and `None` on every other row.

  A row that differs is a defect of Task 2: stop and fix it there.
- [ ] **Step 2: Ask the founder once**, with the list: about 90 FMP calls for Step 3; the merge and the push; the backup; the server's restart; one revalue.
- [ ] **Step 3: The P/E series.** `accept_plan1_pe.py` holds its own copy of the GuruFocus row parser, since Task 6 removed the package's. For each company with a usable `gf` / `pettm` answer in the reference database (29), it fetches the three answers with the branch's `Fmp` client into `pe/` of the research folder, builds the series with `built_series`, and compares each day that both series hold over the ten years: the absolute difference as a share of GuruFocus's value. Pass: over the companies that report in USD, 96% of days or more within 5%. Report ASML, NVO, TSM and RELX each with its median difference and its share of days within 5%. Where one of the four is under 90%, test the quarter's EPS translated at its period end's rate in the place of the day's rate, offline on the fetched answers, and bring both figures to the founder before the merge (the spec's 6.3).
- [ ] **Step 4: The page.** By the recipe of `docs/superpowers/specs/2026-11-19-gurufocus-removal-mockup/README.md`, on a scratch database with an ADR among its companies: the line under the drawer's head and the Research tab's bar, and the P/E chart under "Price and multiples" on a company with a report, in both themes.
- [ ] **Step 5: The live steps**, in the spec's order (section 11): the backup `fairband-before-method-1.6-<date>.db` with SQLite's backup; the server stopped by its process id; main fast-forwarded and pushed; `uv run python -m fairband refresh --kind revalue`; the server started from main (`setsid nohup uv run python -m fairband serve >> ~/.local/share/fairband/server.log 2>&1 < /dev/null &`), and `GET /api/policy` answers 200.
- [ ] **Step 6: The live readout.** After the revalue: the count of rows whose value differs from its snapshot before the revalue, in the reporting currency (expected: none); the rows that carry `basis-scaled` and those refused "share basis unclear"; the P/E history opened on three companies, one of them in another currency.
- [ ] **Step 7: Write the readout** in the spec's decision log: the figures of Steps 1, 3 and 6, the backup's name, the refresh's number, the commits. Move B-255, B-256 and B-257 to Done in `docs/backlog.md` with their commits. File as new rows the limits met: a pending split in the P/E series (with B-199), a ratio with no upper bound, and any company of Step 3 that the rule misses. Run the documents-only check and commit: "Write plan 1's readout of the GuruFocus removal in its design's decision log and close B-255, B-256 and B-257". Push with the founder's word.
- [ ] **Step 8: Tell the founder** that every research session must restart its MCP process: `pe_history` is gone.
