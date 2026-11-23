# The Held Reviewed Value Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reviewed value stays the figure of the company's last made review until someone reviews the company again, and a held figure that no longer fits the data reads "Expired early" with its reasons.

**Architecture:** The store marks each review as made, held or reading, and one row a company (`held_reviews`) names its held review and keeps the facts of its state. A refresh that values still drops overrides and computes its review, now a reading, and carries the held review onto the new snapshot; a price refresh carries it too. Every reader keeps calling `latest_review`, which now gives the held review on the latest snapshot, and one pure function turns the stored facts into the state and its sentences on the settings in force.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite (a migration, `011_held_reviews.sql`), plain JavaScript pages, pytest.

**Spec:** `docs/superpowers/specs/2026-11-23-held-reviewed-value-design.md`. It follows `docs/superpowers/specs/2026-11-23-thresholds-design.md`, built at main `7e17f8e` (policy v19, method 1.9).

## Global Constraints

- No mechanical value moves and no policy value is added. The mechanical method stays `fairband-mechanical/1.9` and the policy `fairband-policy-v19`.
- The review method becomes `fairband-review/2` (`engine/review.py`, `REVIEW_METHOD`).
- A review a refresh writes is a reading and never the held review. Only an agent adds or drops an override (method 14.1).
- The sentences, word for word: "The company has reported a newer period (to 26 Dec 2026)." "Override 36 (non-recurring gap) no longer applies: the input the override corrected changed." "Computed again on today's data, the review gives $229.25 (+204%)." "Computed again, the review gives no value: <the refusal>." "The route now values the company, at $X." "the review was made before the latest refresh: make it again".
- "Expired early" takes the glyph and the colour of Expired (`×`, `critical`). No new colour and no new column. The filter that hides expired rows hides it too.
- The drawer and the company page add nothing for a value that is current, aging or expired by its date. For one expired early they add one line, and the detail opens on a click. No mockup.
- No inbox item for a company on no watchlist. One item stands for one held record.
- `docs/method.md` changes in the same commit as the rule it describes, and the Methodology page with it where its words change (`CLAUDE.md`). No cite, chip or vendor's name on vendor data.
- Every commit runs `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`, is one plain imperative sentence, and ends with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Keys and vendor data are never committed; fixtures are synthetic.

## Decisions the spec left to the builder

Each is Claude's and can be overturned.

1. **The store.** `reviews.kind` is `made`, `held` or `reading`; `reviews.made_id` names the made review of a held copy and of a reading. The table `held_reviews` has one row for a company that holds a review: its made review and the facts of its state. A company with no row has no review. `latest_review` gives the newest `made` or `held` row of that made review.
2. **The carry.** A refresh writes the held review on each new snapshot as a `held` copy. The copy's price-dependent figures (implied growth, sensitivities, expected return, multiples, the long-runway flag) are rebuilt by `route.reprice` only when the held result cites the current method version, policy version and settings hash and no split came since it was made: the price refresh's own three tests. Otherwise the copy takes **the plain move**: the value (÷ ρ at a split, at the new rate for a foreign company), the levels on the policy in force, the price, price ÷ value and the word; every other figure stays as made, the copy's intermediates gain `held_as_made`, and "what the price needs" is not served for it. Today's formulas are not run on a result of another method version.
3. **The state is read, not stored.** A refresh stores facts: the newer period's end, the overrides the system dropped, the newest good reading, and the day a refresh first found a reason. `held.held_state` reads them on the fair band in force, so reason 3 follows a changed band at once, as the levels do.
4. **A refresh that finds applied overrides and no held review** (a state the API cannot make) holds the review it writes, so no override is hidden.
5. **A made act that leaves no override applied clears the held review.** That includes a moat write whose follow drops the last one.
6. **At the migration** a company with an applied override gets its held review by the spec's 5.12; a company with none stays mechanical. The copies on the latest snapshots, the reasons and the readings come from the revalue run at go-live.
7. **A secondary valuation after a split** keeps its figure: the spec names no rule, and "a newer period is on file" will mark it.

## Review Focus

- A held review made under an older method or policy version (21 of the 32 at go-live): the carry must not raise, must not run today's formulas on it, and must keep its value and bridge. Test in Task 3.
- A company whose fetch or valuation fails at a refresh: the held value and its state stay, on the refusal snapshot too. Test in Task 3.
- A foreign held review at a valuing refresh with a new rate: the value in the currency stays and the value in US dollars moves. Test in Task 3.
- The last override dropped by an agent clears the review; dropped by a refresh, the review holds, expired early, and Review again then clears it. Tests in Tasks 2, 3 and 5.
- A reading at 0.92 × the held value is no reason at the default band and is one after the band's low is saved at 0.95, with no refresh between. Test in Task 4.

---

### Task 1: The store marks a made review and names the held one

**Files:**
- Create: `src/fairband/store/migrations/011_held_reviews.sql`
- Modify: `src/fairband/store/reviews.py`
- Test: `tests/store/test_reviews.py`, `tests/store/test_db.py`

**Interfaces:**
- Produces, in `store/reviews.py`:
  - `ReviewKind = Literal["made", "held", "reading"]`; `ReviewRow.kind: ReviewKind`, `ReviewRow.made_id: int | None`, and the property `ReviewRow.held_id -> int` (`made_id`, else `id`).
  - `insert_review(conn, review, symbol, snapshot_id, refresh_id, *, kind: ReviewKind, made_id: int | None = None, clock=utcnow) -> int`.
  - `@dataclass(frozen=True) HeldRow`: `symbol: str`, `review_id: int`, `made_at: datetime`, `read_again_at: datetime | None`, `newer_period: date | None`, `dropped: tuple[dict[str, Any], ...]` (each `{id, tag, reason, at}`), `reading_value: float | None`, `reading_refusal: str | None`, `reading_at: datetime | None`, `early_at: date | None`.
  - `hold_review(conn, symbol: str, review_id: int, at: datetime) -> None` (the made review becomes the held one, its state empty), `clear_held(conn, symbol: str) -> None`, `held_row(conn, symbol: str) -> HeldRow | None`, `held_rows(conn) -> dict[str, HeldRow]`, `set_held_state(conn, row: HeldRow) -> None`.
  - `log_review(..., kind: ReviewKind | None = None)`; `LogRow.kind: str | None`.
- The migration: `reviews.kind TEXT NOT NULL DEFAULT 'reading'`, `reviews.made_id INTEGER`, `review_log.kind TEXT`, the table `held_reviews` (the columns of `HeldRow`, `symbol` the key, `dropped` JSON, the value as `repr` text), `work_items.expiry_review_id INTEGER`, `work_items.expiry_secondary_id INTEGER`. It marks as `made` each review with no refresh id (an override's write or drop), each review a report cites (`reports.review_id`), and each review written by the revalue of a moat write (a `revalue` naming one company, started within a minute after a `moat` ledger row of that company). For each company with an applied override it inserts the `held_reviews` row of its newest made review, and where it has none marks its newest review made.

- [ ] **Step 1: Write the failing tests.** `tests/store/test_reviews.py`: `test_a_made_review_is_held_and_a_reading_is_not` (insert a made review, `hold_review`, insert a reading on a newer snapshot: `held_row(...).review_id` is the made id, and the reading's `kind` and `made_id` read back); `test_clearing_the_held_review_leaves_no_row`; `test_the_state_reads_back_exactly` (a `HeldRow` with a newer period of 2026-12-26, one dropped override, a reading of 291.62 and an early day reads back equal after `set_held_state`). `tests/store/test_db.py`: `test_migration_011_marks_the_made_reviews_and_seeds_the_held_ones` on a database migrated to 010 and filled by SQL: a review with no refresh id, one a report cites, one of a moat write's revalue and one of a full refresh, with an applied override; expect kinds `made, made, made, reading` and one `held_reviews` row naming the newest made one.
- [ ] **Step 2: Run them.** `uv run pytest -q tests/store/test_reviews.py tests/store/test_db.py`. Expected: FAIL (no column `kind`, no `hold_review`).
- [ ] **Step 3: Write the migration and the store functions.** `insert_review`'s callers pass `kind="made"` for now (`refresh/reviews.py`), so nothing else changes.
- [ ] **Step 4: Run the tests, then the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Mark each review as made, held or a reading, and keep one row for the review a company holds".

### Task 2: Every writer holds its review, and every reader reads the held one

No behaviour changes here: a refresh's review is still held, so the suite stays green before the rule flips in Task 3.

**Files:**
- Modify: `src/fairband/store/reviews.py` (`latest_review`, `latest_reviews`, `latest_review_on`), `src/fairband/refresh/reviews.py` (`write_review`, `_write_refusal`, `_follow`, `_reprice`), `src/fairband/web/reviews_api.py` (`recompute`)
- Test: `tests/store/test_reviews.py`, `tests/web/test_reviews_api.py`, `tests/refresh/test_reviews_follow.py`

**Interfaces:**
- Consumes: Task 1's `hold_review`, `clear_held`, `held_row`.
- Produces: `latest_review(conn, symbol)` is the newest `made` or `held` row whose `held_id` is the company's `held_reviews.review_id`, `None` with no row there (the test "an override is applied" is gone); `latest_reviews` likewise; `latest_review_on(conn, snapshot_id)` skips readings. `write_review(..., kind: ReviewKind = "made") -> int` writes the row and, for a made one, calls `hold_review`. A write that leaves no override applied calls `clear_held`.

- [ ] **Step 1: Write the failing tests.** `test_the_current_review_is_the_held_one_whatever_overrides_are_applied` (store: a held review stays `latest_review` after its override's state is set to dropped; `clear_held` ends it); `test_an_agent_s_drop_of_the_last_override_clears_the_review` (web: `latest_review` is `None` and `held_row` is `None` after the DELETE).
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Change the three readers and the writers.** The follow's "none left" path and `_write_refusal`'s "none applied" keep clearing for now.
- [ ] **Step 4: Run the suite.** Expected: PASS, with test set-ups that insert a review directly now calling `hold_review`.
- [ ] **Step 5: Commit.** "Read a company's review from the one it holds, which every write of a review now names".

### Task 3: A refresh reads the review again and carries the held one

**Files:**
- Create: `src/fairband/refresh/held.py` (the carry and the facts)
- Modify: `src/fairband/refresh/reviews.py`, `src/fairband/refresh/run.py` (`_value_symbol`, `revalue_company`, `_fail`), `src/fairband/refresh/run_price.py`, `src/fairband/web/moat_api.py`, `src/fairband/engine/review.py` (`REVIEW_METHOD = "fairband-review/2"`), `docs/method.md` (10, 14.5 to 14.7, the versions table), `docs/method-overview.md`
- Test: `tests/refresh/test_held.py` (new), `tests/refresh/test_reviews_follow.py`, `tests/refresh/test_run_price.py`, `tests/web/test_moat_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Produces, in `refresh/held.py`:
  - `carry_held(conn, symbol: str, snapshot_id: int, policy: Policy, refresh_id: int | None, clock) -> int | None`: the held review written on `snapshot_id` as a `held` copy by decision 2, with its log row; `None` for a company that holds none. It reads the price, its date and the rate from the new snapshot. It runs in a savepoint, and a failure of the rebuild falls back to the plain move.
  - `read_again(conn, symbol: str, snapshot_id: int, reading: ReviewRow | None, mechanical: ValuationResult, trailing_end: date | None, policy: Policy, at: datetime) -> None`: stores `read_again_at` (once), `newer_period` (the new trailing end when it is after the held review's made-on snapshot's, read by `reviews._trailing_end`), `dropped` (each override inside the held review that is dropped with a ledger row `override-drop` by the system, `moat.class` left out), the newest good reading (the reading's value or refusal; the mechanical value or refusal with no override left; unchanged when the reading is "review failed: …"), and `early_at`, the day of this refresh when a reason holds and none was stored, cleared when none holds.
- `follow_snapshot(..., made: bool = False)`. With `made`, the moat write's: the drop tests, then the review as a made one, held, or the held review cleared with none left. Without: the drop tests, the review as a `reading` with `made_id`, then `carry_held`, then `read_again`. With applied overrides and no held review: decision 4.
- `revalue_company(..., made: bool = False)`; `moat_api` passes `True`.
- A price refresh calls `carry_held` in place of `reprice_review`; a failed company's refusal snapshot calls `carry_held` in place of `review_refusal`'s write, and stores no reading.

- [ ] **Step 1: Write the failing tests** in `tests/refresh/test_held.py`, each on `env_valued` with a review made through the API's recompute:
  - `test_a_revalue_that_moves_the_reading_leaves_the_held_value` (the spec's 7, second bullet: a method version bump that moves the reading by 12%: `latest_review(...).value` is the made value, on the new snapshot, `kind == "held"`; the reading row holds the new value).
  - `test_a_scoped_refresh_that_drops_a_period_tied_override_holds_the_review` (the held value stays; `held_row(...).dropped` names the override and "the input the override corrected changed").
  - `test_a_refresh_that_drops_the_last_override_holds_the_review` (no reading row; the stored reading is the mechanical value).
  - `test_a_refresh_after_the_company_reports_stores_the_newer_period`.
  - `test_a_failed_company_keeps_its_held_review_and_its_state` (Review Focus 2).
  - `test_a_held_review_of_another_method_version_takes_the_plain_move` (Review Focus 1: the made row's `method_version` set to `fairband-mechanical/1.1`; the copy's value, bridge and implied growth are the made ones, its price ÷ value is the new price ÷ the value, its levels are `levels_for` on the policy, and `held_as_made` is set).
  - `test_a_foreign_held_review_moves_with_the_rate_at_a_revalue` (Review Focus 3, KRON: `value_in_currency` as made, the USD value ÷ the new rate, the bridge still summing).
  - `test_a_two_for_one_split_halves_the_held_value_and_changes_no_word` (the spec's 7).
  - `test_a_moat_write_makes_the_review` (web: the review of the write's revalue is `made` and held, and the state is empty).
  - `test_a_refresh_with_overrides_and_no_held_review_holds_its_review` (decision 4).
  - In `test_run_price.py`: `test_a_price_refresh_carries_the_held_review` (value as made, price ÷ value and the word moved, implied growth rebuilt, `kind == "held"`).
  - In `test_method_doc.py`: `test_a_review_is_made_held_and_read_again` pins the new sentences of 10 and 14.5 to 14.7 and `fairband-review/2`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement** `refresh/held.py`, the two paths of `follow_snapshot`, the price refresh's and the failed company's carry, and `REVIEW_METHOD`. Rewrite `docs/method.md` 10 and 14.5 to 14.7: a review is made by an act, held, and read again by a refresh; what the carry moves; the plain move; the log's `kind`.
- [ ] **Step 4: Move the old tests.** Each test of `test_reviews_follow.py` that expects a review to follow new data now expects the reading to move and the held value to stay; a test of the drop tests keeps its drops and reads the reading.
- [ ] **Step 5: Run the full check.** Expected: PASS.
- [ ] **Step 6: Commit.** "Hold a reviewed value through every refresh, which now reads the review again beside it, under review method 2".

### Task 4: The state, its sentences and its readers

**Files:**
- Create: `src/fairband/engine/held.py`
- Modify: `src/fairband/web/rows.py`, `src/fairband/web/app.py`, `src/fairband/web/research_api.py`, `src/fairband/web/reviews_api.py` (the `reviews` list), `src/fairband/web/static/app.js` (the Freshness cell's words and the filter), `docs/method.md` (4.10, 14.5, the glossary)
- Test: `tests/engine/test_held.py` (new), `tests/web/test_rows.py`, `tests/web/test_app.py`, `tests/web/test_research_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Produces, in `engine/held.py`:
  - `@dataclass(frozen=True) HeldState`: `state: Literal["current", "aging", "expired", "expired-early"]`, `early_at: date | None`, `reasons: tuple[str, ...]`, `reading: float | None`, `reading_refusal: str | None`.
  - `held_state(*, value: float | None, valid_from: date, valid_until: date, newer_period: date | None, dropped: Sequence[Mapping[str, Any]], reading_value: float | None, reading_refusal: str | None, early_at: date | None, band: tuple[float, float], today: date, aging_fraction: float) -> HeldState`. Reasons in the order 1, 2, 3. Reason 3: `reading_value ÷ value` under `band[0]` or over `band[1]`, or a reading that refuses. An expired-early state wins over the date's state. The percent has one decimal under 100 and none from 100 ("+7.0%", "+204%"); money is `$1,234.56`; a day is "26 Dec 2026". An override's words are `overrides.LABELS[tag]`.
- `rows.agent_fields(..., held: HeldRow | None)` adds `"held"`: `None`, or `{state, earlyAt, reasons, reading, readingRefusal, validUntil}`. `screen_row`: on a row a review fills, `freshness` is `expired` for both expired states, else the held state; the new key `expiredEarly: bool`; `validUntil` is the held review's. The detail's `review` gains the same `held` block, and `priceNeeds` is `None` for a review whose result holds `held_as_made`.
- `GET /api/companies/{symbol}/reviews` answers `{"held": {...} | None, "reviews": [...]}`, each review with its `kind`.
- The page: the Freshness cell reads "Expired early" where `expiredEarly`, with Expired's glyph and colour; `hideExpired` hides it.

- [ ] **Step 1: Write the failing tests.** `tests/engine/test_held.py`: `test_the_three_reasons_read_as_their_sentences` (the four sentences of the Global Constraints, from 2026-12-26, override 36 `earnings.nri_gap`, a held $75.29 against $229.25, and a refusal); `test_a_reading_inside_the_band_is_no_reason` (8% is none and 12% is one, the spec's 7); `test_reason_3_follows_the_band_in_force` (Review Focus 5); `test_a_value_with_no_reason_reads_by_its_date` (current, aging, expired). `tests/web/test_rows.py`: `test_a_held_row_reads_expired_early_and_keeps_its_number`; `test_a_mechanical_row_reads_as_before`. `tests/web/test_research_api.py`: `test_the_detail_gives_the_held_state_and_the_reading`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Read a held value's state and its reasons, and show Expired early on the row".

### Task 5: Review again

**Files:**
- Modify: `src/fairband/web/reviews_api.py`, `src/fairband/mcp/server.py`, `playbook/fairband-research/reference/tools.md`, `docs/method.md` (14.5, 16)
- Test: `tests/web/test_reviews_api.py`, `tests/mcp/test_server.py`, `tests/test_method_doc.py`, `tests/test_playbook.py`

**Interfaces:**
- Produces: `POST /api/companies/{symbol}/review`, an agent's or the owner's, with no body. It runs `require_current`, then the recompute of an override's write on the latest snapshot. With an override applied: a made review, its log row, the ledger row `review` ("review made again on snapshot <id>"), and the answer `{"review", "bridge", "dropped"}` of an override's write. With none applied: the held review cleared, the ledger row ("review cleared: no override applies") and `{"review": null, "bridge": [], "dropped": []}`. 404 "no review for <symbol>" for a company that holds none.
- The MCP tool `review_again(symbol: str)`, described "Make the company's review again on its latest snapshot, over the overrides still applied."

- [ ] **Step 1: Write the failing tests.** `test_review_again_makes_the_reading_the_held_value` (after a revalue that moved the reading: the new held value is the reading's, the state is empty, the row's window is the new snapshot's; by an agent and by the owner); `test_review_again_with_no_override_clears_the_review` (Review Focus 4, after a refresh dropped the last one); `test_review_again_is_refused_without_a_review`; `test_review_again_is_refused_under_changed_settings`; the MCP tool's call and its place in the tool list.
- [ ] **Step 2: Run them.** Expected: FAIL (404 on the route).
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Let an agent or the owner make a review again with no change of an input".

### Task 6: A report and a sensitivity reading need a review no refresh has read again

**Files:**
- Modify: `src/fairband/reports/check.py` (`_stale_review`, `_stale_reading`), `src/fairband/web/sensitivity_api.py`, `docs/method.md` (16.3)
- Test: `tests/reports/test_check.py`, `tests/web/test_sensitivity_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Consumes: `held_row(...).read_again_at`, `ReviewRow.held_id`.
- Produces: a `review:<id>` cite is accepted when `<id>` is the held review or a copy of it, the newest made or held row on its snapshot, on the latest snapshot or one it reprices, and `read_again_at` is `None`. With `read_again_at` set the failure reads "review:<id>: the review was made before the latest refresh: make it again". The sensitivity POST answers 409 with "the review was made before the latest refresh: make it again" in the same state.

- [ ] **Step 1: Write the failing tests.** `test_a_report_on_a_review_read_again_is_refused_and_accepted_after_review_again` (the spec's 7); `test_a_report_on_a_review_a_price_refresh_carried_is_accepted` (a foreign company too); `test_a_reading_is_refused_on_a_review_read_again`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Refuse a report or a reading on a review that a refresh read again since it was made".

### Task 7: A secondary valuation holds

**Files:**
- Modify: `src/fairband/engine/held.py`, `src/fairband/web/rows.py`, `src/fairband/web/app.py`, `src/fairband/web/research_api.py`, `docs/method.md` (15)
- Test: `tests/engine/test_held.py`, `tests/web/test_rows.py`, `tests/web/test_secondary_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Produces: `held.secondary_state(*, valid_from: date, valid_until: date, made_period: date | None, latest_period: date | None, route_value: float | None, today: date, aging_fraction: float) -> HeldState`, with the reasons "The company has reported a newer period (to …)." and "The route now values the company, at $X.". `rows.agent_fields` fills `reviewed` from the newest secondary valuation above zero wherever no held review values the company, whatever snapshot it rests on, with its `held` block; the made-on snapshots' windows and period ends are read once for the screen.

- [ ] **Step 1: Write the failing tests.** `test_a_secondary_valuation_stays_through_a_refresh_that_replaces_its_snapshot`; `test_a_secondary_valuation_expires_early_when_the_route_values_the_company` (the row shows the secondary's value, `expiredEarly`, and the sentence with the route's value); `test_a_made_review_with_a_value_fills_the_row_before_a_secondary`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Hold a secondary valuation on its row until a newer one or a made review replaces it".

### Task 8: The inbox reads the held record's state

**Files:**
- Modify: `src/fairband/store/inbox.py`, `src/fairband/web/agents_api.py`, `docs/method.md` (the inbox's rule)
- Test: `tests/store/test_inbox.py`, `tests/web/test_agents_api.py`, `tests/test_method_doc.py`

**Interfaces:**
- Produces: `post_expiry_items(conn, today: date, at: datetime, band: tuple[float, float], aging_fraction: float) -> tuple[list[int], list[int]]`. For a watched company with no open item: with a held review, its `held_state`; else with a held secondary valuation, its `secondary_state`; else today's rule. Expired by its date it posts "expired <date>"; expired early, "expired early: override 36 no longer applies", "expired early: a newer period is on file" or "expired early: computed again, the review gives $229.25", the first reason's. The item keeps `expiry_review_id` (the made review) or `expiry_secondary_id`, and a company with an expiry item for that record gets no second. `WorkItem` gains the two ids.

- [ ] **Step 1: Write the failing tests.** `test_a_watched_company_expired_early_gets_one_item` (the note names the first reason); `test_a_declined_item_is_not_posted_again_for_the_same_held_review` (a second reason later posts nothing; a review made again and expired again posts one); `test_an_unwatched_company_expired_early_gets_none`; `test_a_watched_company_with_no_review_keeps_the_window_s_rule`.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the full check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Post an expiry item for a watched company on its held record's state, one for each record".

### Task 9: The page's one line, its detail and the button

**Files:**
- Modify: `src/fairband/web/static/app.js` (the drawer), `src/fairband/web/static/company_overview.js` or the Overview's file as it is named, `src/fairband/web/static/index.html` (styles, tokens only), `src/fairband/web/static/methodology.html`
- Test: `tests/web/page.mjs` and its Python runner, `tests/web/test_company_overview.py`, `tests/web/test_methodology.py`, `tests/web/test_design_tokens.py`

**Interfaces:**
- Consumes: the detail's `review.held` and `secondary.held` (Task 4, Task 7), `POST /api/companies/{symbol}/review` (Task 5).
- Produces: under the reviewed value, only for `state == "expired-early"`, the line "× Expired early 14 Nov 2026 · 3 reasons ▸" (a button, `aria-expanded`), and on a click the reasons, one a line, then a Review again button for a review (none for a secondary valuation). The button posts, then reloads the row and the detail; a refusal's sentence shows in the detail. The bridge's first line says the day of its mechanical value. The Methodology page says in plain words that a reviewed value holds until the next review and what "Expired early" means.

- [ ] **Step 1: Write the failing page tests**: the line is absent for a current, an aging and an expired value; present and closed for an expired-early one, with the count; the click shows the reasons in the order given; Review again posts to the route; a secondary valuation's detail has no button.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Implement**, with the design system's tokens only.
- [ ] **Step 4: Run the full check, and look at the drawer in a headless browser in both themes**, with the scrollbars shown and a short window.
- [ ] **Step 5: Commit.** "Show one line for a value expired early, its reasons on a click, and a Review again button".

### Task 10: The playbook, the remaining documents and the backlog

**Files:**
- Modify: `playbook/fairband-research/SKILL.md`, `playbook/fairband-research/reference/tools.md`, `docs/method.md` (the glossary and any sentence that still says a review follows its snapshot), `docs/method-overview.md`, `docs/backlog.md` (B-290 to Done, with the minors), `README.md` only if it states the old rule
- Test: `tests/test_playbook.py`, `tests/test_method_doc.py`

- [ ] **Step 1: Write the failing pins**: the playbook's valuation step starts by reading the held state and its reasons, decides again from the filing for each override that no longer applies, and ends with a made review on the latest snapshot; no document says "a review follows its snapshot" as the rule in force.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Write the words.**
- [ ] **Step 4: Run the short check.** Expected: PASS.
- [ ] **Step 5: Commit.** "Have the playbook start a valuation from the held review's state, and say in every document that a reviewed value holds".

### Task 11: Acceptance, then going live on the founder's word

Not a task for a subagent. The controller does it.

- [ ] **Step 1: Accept on a scratch copy of the live store** (every table but the vendor's stored responses; a spare port; no key). Migrate it, run one revalue, and compare with the spec's 5.12: 32 held reviews; the six that expire early (AMD, AVGO and TTMI by reason 3; CLS, RKLB and SYM by reason 2); no inbox item. Record each company whose figure differs from the spec's and why. In a headless browser, both themes: AMD reads $75.29 and "Expired early", its detail shows $229.25, and Review again puts the reading in its place.
- [ ] **Step 2: Run a whole-branch review** by a fresh reviewer on Opus 5.5 at xhigh, then one fix pass.
- [ ] **Step 3: Ask the founder** for the word to leave the worktree and for the merge, the restart, the revalue and the push.
- [ ] **Step 4: Go live.** Merge to main. Restart the live server by its process ids. Run one revalue at once: until it ends, a reviewed row shows its mechanical value alone. Check the screen against Step 1's list. Push. Tell the founder that each research session must reconnect `fairband` for the new tool.
