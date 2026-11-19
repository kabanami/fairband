# The GuruFocus Removal, Plan 2: No Gap, the Warning, the Mark and the Note Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The mechanical routes take no non-recurring gap and read no GuruFocus EPS; Mature Stable
gains the warning `one-time-items`; the screen, the drawer and the company page mark a mechanical
value with three warnings or more and say on hover that it is preliminary (B-258, B-259).

**Architecture:** Policy v17 swaps `nri_flag_share` for `one_time_items_share` and adds
`warning_mark_min`; a stored value of a removed setting is skipped and deleted. The engine drops
`nri_gap`, the two GuruFocus inputs, `large-nri` and `consensus-basis-unknown`, and adds the
warning on Mature Stable (method 1.7). Assembly and the fetch drop the `keyratios` call and the
rules written for it. The web layer turns a snapshot's quality warnings into plain words and a
mark; the bundle draws the mark and the hovers.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite; plain JavaScript with React from the vendored
design-system bundle, no build step; pytest, with node for the page's scripts
(`tests/web/page.mjs`, `tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-19-gurufocus-removal-design.md`, section 7, bound also
by sections 3, 5 (points 4 to 7) and 9 to 14; it stands on `docs/gurufocus-removal.md` 2.5 to
2.7. Read both with your task; where this plan and the spec differ, the spec wins. The look's
sources are in `docs/superpowers/specs/2026-11-19-gurufocus-removal-mockup/` (`dots.mjs`, form A).

**A map of the code as it stands** (plan 1 merged: method 1.6, the ADR ratio from the counts, 54
MCP tools; `summary` and `keyratios` still called). Paths are under `src/fairband/`.

- `apply_overlay` raises `"<name>: not a setting"`, which `effective_policy` turns into a
  refusal of every read; `settings_hash` raises `KeyError` on such a name.
- `common_inputs` cites `gf_eps_ttm` and `gf_eps_without_nri` on every route; Mature Stable's
  refusal "no positive trailing earnings" raises no flag and cites nothing; Mature Growth's
  `_anchor_and_path` corrects GAAP EPS by `gap - nil(nri_gap(i))`; `route.py`'s `_unique` keeps
  one flag a code. MSCO (`tests/support/engine_companies.py`): EPS 3.40, a gap of 0.10, no
  street figure.
- Assembly reads `gf-ratio`, scales it at a split (`_gurufocus_side`, `_observed`) and
  translates it at the mean rate (`_Money.mean`, `FxSeries.mean_at`).
- `covered` is a row field, not a row key. The bundle (`web/static/design-system/components/
  bundle.js`) draws the screen and `BandMeter`; `app.js`'s `meter` and `levelRows` serve the
  drawer and, through `company_overview.js`'s `value(d)` and `company.js`'s `kv`, the company page.

## Global Constraints

- Work in a git worktree, not the main checkout: the live server on port 8470 serves the page
  files of the main checkout as they are on disk.
- Test first: a failing test, then the code, then the passing run, then the commit.
- Before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src &&
  uv run pytest -q`. A commit of documents alone runs the shorter check of `CLAUDE.md`.
- A commit message is one plain sentence in the imperative, then a blank line, then
  `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- No test uses the network. Fixtures are synthetic. Never commit vendor data; never print, log,
  store or commit a key. Nothing under `~/.local/share/fairband/` is committed, and the reference
  database is never written.
- `docs/method.md` and the Methodology page change in the same commit as the engine, classifier
  or policy change they describe.
- Every dispatched subagent runs on Opus 5.5 at xhigh effort.
- GuruFocus's `summary` call keeps working: plan 2 removes `keyratios` only.
- The method becomes `fairband-mechanical/1.7`, the policy `fairband-policy-v17`; the schema
  stays 009 and the MCP server keeps its 54 tools.
- The live steps need the owner's consent, asked once with the list; nothing is pushed without
  his word.
- Every word a person reads on a page is copied from the Words table, which copies the spec.

## Words

| Where | Words |
|---|---|
| The note on the screen (the Mechanical head, a mechanical value, its mark) | `Preliminary estimate only. To ask an agent for a reviewed valuation, open the company and click Request research.` |
| The note in the drawer and on the company page | `Preliminary estimate only. To ask an agent for a reviewed valuation, click Request research.` |
| The hover's three forms | `3 warnings: heavy capital spending; negative free cash flow; new shares issued. ` then the note; `1 warning: one-time items. ` then the note; the note alone for none |
| The mark | `•` (U+2022), `role="img"`, its `aria-label` the hover's first sentence |
| Plain words, by code | `one-time-items` one-time items; `value-spread` value sensitive to its inputs; `margin-flag` by its word: `Margin above history` margin above its history, `Newly profitable` newly profitable, `Possible cycle peak` possible cycle peak; `z-distress` distress signal; `f-score-low` weak financial health; `reinvesting-in-decline` investing while revenue falls; `equity-raise` new shares issued; `negative-fcf` negative free cash flow; `heavy-capex` heavy capital spending; `burn-cover-short` cash covers under two years; `consensus-recovery` analysts expect a recovery; `share-count-gap` share count unclear |
| The warning: word, sentence | `One-time items`; `GAAP trailing EPS is $4.10 and the analysts' is $5.20, apart by 26.8% of GAAP EPS, at or above 20.0%. The trailing earnings may hold one-time items, which the mechanical value keeps; a review takes them out through `earnings.nri_gap`.` |
| `sbc-basis-uncertain`, reason 1's end | `… while GAAP trailing EPS and the analysts' differ by 26.8%, so a one-time item may sit in GAAP EPS and hide the gap.` |
| Glossary, "Non-recurring gap" | `The one-time items in the trailing earnings a share, after tax, which an agent sets in a review; a net charge is negative` |
| Settings page, `one_time_items_share` | label `One-time items, share of EPS`; sentence `A Mature Stable row whose GAAP and street trailing EPS differ by this share of GAAP EPS or more is warned of one-time items.` |
| Methodology, the value section | `A mechanical value is preliminary: fixed rules made it, and no one checked it. It includes one-time items. A review takes them out.` |
| Playbook, step 5 | `Name the one-time items: the mechanical value keeps them, and step 8 takes them out.` |
| Playbook, the clean P/E's gloss | `the clean P/E (the price over the trailing earnings a share less the one-time items you set through `earnings.nri_gap`; it differs from the reported P/E under your gap alone)` |

## Review Focus

Five inputs the spec implies and no task's tests would otherwise meet; each has its test in the
task that owns the code.

1. **A snapshot valued before 1.7.** The live data, a scratch copy and the reference database
   hold results with `large-nri`, `consensus-basis-unknown` and a found `nri_gap`: `warnings`
   leaves both old codes out and counts neither, and nothing raises (Task 5).
2. **A save that names the removed setting.** `PUT /api/settings` with `nri_flag_share` is
   refused 400 "nri_flag_share: not a setting", never ignored; an overlay holding a stale name
   hashes as the overlay without it (Tasks 1, 2).
3. **Signs and zero in the warning's test.** A GAAP loss against a street profit, both negative,
   a GAAP EPS of zero, no street figure: the share reads sizes, a zero GAAP EPS is silent, and
   the sentence prints `−$1.00` (Task 2).
4. **A company in another currency.** The warning and reason 1 print the code, `SEK 4.10`, as the
   other sentences do (Task 2).
5. **Where the mark must not stand.** A refused row, a placeholder, a reviewed row, a row with two
   warnings: no mark; a refused row's em dash has no hover; the watchlists view's table draws the
   screen's mark and hover (Tasks 5, 6).

### Task 1: A stored value of a removed setting is skipped and deleted (spec 5 point 4, 7.4)

**Files:**
- Modify: `src/fairband/policy/settings.py` (`settings_hash`, `apply_overlay`, the docstring),
  `src/fairband/store/settings.py` (`write_settings`, `reset_settings`, the docstring),
  `docs/method.md` (4.1's overlay paragraph), `playbook/fairband-research/SKILL.md` (the settings
  refusal, near line 100), `playbook/fairband-research/reference/tools.md` (near line 420)
- Test: `tests/policy/test_settings.py`, `tests/store/test_settings_overlay.py`,
  `tests/web/test_settings_api.py`, `tests/refresh/test_run_revalue.py`,
  `tests/web/test_refresh_api.py`, `tests/test_playbook.py` (its pin of the sentence, near 576)

**Interfaces:**
- Produces: `apply_overlay(base, overlay)` and `settings_hash(overlay)` read only the names that
  are settings. `write_settings(conn, changes, …)` raises `ValueError("<name>: not a setting")`
  for a name of `changes` that is no setting, before any write. It and `reset_settings` delete,
  in their transaction, each stored row whose name is no setting, logged as `{"name", "old",
  "new": None}` after the call's own entries.

- [ ] **Step 1: Write the failing tests.**

```python
def test_apply_overlay_skips_a_name_that_is_no_setting() -> None:        # test_settings.py
    p = apply_overlay(load_policy(), {"gone_value": 1, "fade_years": 3})
    assert p.fade_years == 3 and p.settings_hash == settings_hash({"fade_years": 3})
    assert settings_hash({"gone_value": 1}) == EMPTY_SETTINGS_HASH
def test_a_stored_row_of_a_removed_setting_is_skipped_then_deleted(conn) -> None:
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),))
    assert effective_policy(conn).settings_hash == EMPTY_SETTINGS_HASH
    write_settings(conn, {"fade_years": 3}, None, AT)
    assert read_overlay(conn) == {"fade_years": 3}
    assert changes(conn)[0].changes == [{"name": "fade_years", "old": None, "new": 3},
                                        {"name": "gone_value", "old": 1, "new": None}]
def test_a_save_that_names_no_setting_writes_nothing(conn) -> None:
    with pytest.raises(ValueError, match="gone_value: not a setting"):
        write_settings(conn, {"gone_value": 1, "fade_years": 3}, None, AT)
    assert read_overlay(conn) == {}
def test_a_stored_row_of_a_removed_setting_is_skipped(client, db_path) -> None:   # 200s
```

The tests that reach the refusal through a stale name (`STALE` in `test_settings_api.py`, the
`'gone'` rows of `test_run_revalue.py` and `test_refresh_api.py`) store `('required_return',
'0.5')` instead, refused "settings: required_return: must be from 4% to 20%; reset it on the
Settings page"; `test_an_unknown_overlay_row_names_itself` gives way to the store test above, and
the `unknown_name` case leaves `test_ranges_and_rules_name_the_setting`.

- [ ] **Step 2: Run the six files.** Expected: the new tests fail on "not a setting".
- [ ] **Step 3: Implement.** Filter by `_BY_NAME` once in `apply_overlay` and in `settings_hash`;
  in the store, refuse an unknown name of `changes` first, then sweep. `method.md` 4.1 gains: "A
  stored value of a name that is no longer a setting is skipped, and deleted at the next save or
  reset (spec 2026-11-19 7.4)." The playbook's two sentences, and `test_playbook.py`'s pin, say
  "a stored setting outside its range" for "a stored setting the policy file no longer accepts".
- [ ] **Step 4: Run `uv run pytest -q`.** Expected: pass. Run the checks, then commit.

### Task 2: Policy v17 and the warning `one-time-items` (spec 7.2 to 7.4; Review Focus 2 to 4)

**Files:**
- Create: `src/fairband/policy/fairband-policy-v17.toml`, a full copy of v16 changed as in Step 3
- Modify: `policy/__init__.py` (`_POLICY_FILE`, `Policy`, `load_policy`, the docstring),
  `policy/settings.py` (the entry, `check`), `web/policy_rows.py` (`READ_ONLY`),
  `engine/__init__.py`, `engine/flags.py`, `engine/route_steps.py`, the four routes;
  `docs/method.md` (head, 4.1, 5.11, 5.12, 6.1, 6.5, 8, 11), `docs/method-overview.md`,
  `web/static/methodology.html` (the flags section's lists), `tests/fixtures/golden/MSCO.json`
  and the goldens' `README.md`
- Test: `tests/engine/` (`test_flags.py`, `test_route.py`, `test_mature_growth.py`,
  `test_review.py`, `test_currency.py`), `tests/policy/`, `tests/refresh/test_run_full.py`
  (`CALIBRATION["flags"]`, `route_flags`), `tests/web/test_methodology.py`,
  `tests/web/test_settings_api.py`, `tests/test_method_doc.py`, each version literal (Step 4)

**Interfaces:**
- Consumes: Task 1 (a stored `nri_flag_share` row is skipped from now on).
- Produces:
  - `Policy.one_time_items_share: float`, 0.20, a setting in `nri_flag_share`'s place (group
    `flags`, unit `fraction`, effect `revalue`, range `1% to 50%`, hashed);
    `Policy.warning_mark_min: int`, 3, not a setting, in `READ_ONLY` as `count`.
  - In `engine/flags.py`, where `nri_flag` and `basis_unknown_flag` were:

```python
def one_time_share(gaap_eps: float | None, street_eps: float | None) -> float | None
    # |GAAP − street| ÷ |GAAP|; None without both figures or with a GAAP EPS of 0
def one_time_items_flag(gaap_eps: float | None, street_eps: float | None, policy: Policy,
                        currency: str = "USD") -> Flag | None
def sbc_basis_uncertain_flag(basis, t, street_ttm_eps, shares, tax_rate,
                             one_time: float | None, policy, currency="USD") -> Flag | None
    # `one_time`, the warning's share where its test holds, replaces `large_nri: bool`
```

  - `QUALITY_WARNINGS` holds `one-time-items` in `large-nri`'s place: still twelve.
  - `trailing_flags(i: CompanyInputs, t: TrailingFigures, policy: Policy, roic: RoicTerms | None =
    None, one_time: Flag | None = None) -> tuple[Flag, ...]`: the margin flag, the gates, then
    `one_time`. Mature Stable alone passes one, and none under an applied `earnings.nri_gap`.
  - Mature Stable cites `street_ttm_eps` (DATA, `per_share(i)`) after `net_income_ttm`. Its
    refusal "no positive trailing earnings" carries the warning where the test holds and cites
    `eps_ttm` and `street_ttm_eps` (`Refused.inputs`).
  - `_stock_pay_notes(c: Context, anchor: Anchor) -> tuple[Flag, ...]`: reason 1 reads
    `one_time_share(t.eps_diluted, i.street_ttm_eps)` at `one_time_items_share` or more, silent
    under an applied `earnings.nri_gap` as the warning is.
  - `METHOD_VERSION = "fairband-mechanical/1.7"`.

- [ ] **Step 1: Write the failing tests.** `SENTENCE` is the Words table's.

```python
def test_the_warning_at_the_threshold(policy) -> None:                    # test_flags.py
    assert one_time_items_flag(5.00, 6.00, policy) is not None           # 20.0% fires
    assert one_time_items_flag(5.00, 5.995, policy) is None              # 19.9% is silent
    assert one_time_items_flag(5.00, None, policy) is None
    assert one_time_items_flag(0.0, 1.00, policy) is None
    assert one_time_share(-1.00, 0.50) == pytest.approx(1.5)             # sizes, either sign
    assert one_time_share(-1.00, -0.70) == pytest.approx(0.3)
def test_the_warning_s_sentence(policy) -> None:
    flag = one_time_items_flag(4.10, 5.20, policy)
    assert (flag.code, flag.word, flag.sentence) == ("one-time-items", "One-time items", SENTENCE)
    assert "−$1.00" in one_time_items_flag(-1.00, 0.50, policy).sentence
    assert "SEK 4.10" in one_time_items_flag(4.10, 5.20, policy, "SEK").sentence
def test_the_basis_is_uncertain_on_one_time_items() -> None:   # one_time=0.268: reason 1's end;
    ...                                                         # None: no reason 1; SEK 0.25
def test_the_warning_follows_the_gates() -> None:   # was ..._consensus_basis_unknown_only_on_...
def test_mature_stable_warns_of_one_time_items() -> None:     # test_route.py; MSCO, street 4.08
def test_the_warning_is_silent_under_an_agents_gap() -> None:
def test_the_refusal_carries_the_warning() -> None:   # net income −100 m, EPS −0.10, street 1.00;
    ...                                               # eps_ttm and street_ttm_eps cited
def test_the_warning_is_on_mature_stable_alone() -> None:     # MGCO, HGCO: a street 50% off
def test_v16_is_byte_identical_under_its_hash() -> None:      # test_policy.py; V16_SHA256
def test_v17_is_v16_with_two_values_in_and_one_out() -> None:
    assert v17.keys() - v16.keys() == {"one_time_items_share", "warning_mark_min"}
    assert v16.keys() - v17.keys() == {"nri_flag_share"}      # the rest equal; 7.4's sources
def test_a_warning_mark_min_below_one_fails_at_load(tmp_path) -> None:
def test_a_put_of_the_removed_setting_is_refused(client) -> None:   # test_settings_api.py, 400
def test_method_1_7_takes_no_gap() -> None:   # test_method_doc.py: rows[-1] "| 1.7, policy v17 |"
```

The two old codes leave every pin (`test_mature_growth.py` near 334, `test_review.py` near 589,
`test_currency.py` near 619, which checks the warning in SEK, `test_run_full.py`); plan 1's test
of `rows[-1]` finds its row by its prefix; `test_methodology.py`'s `QUALITY_WARNINGS` starts with
`one-time-items`, its item citing `<span data-policy="one_time_items_share">—</span>`.

- [ ] **Step 2: Run the listed files.** Expected: fail on the new names and the pins.
- [ ] **Step 3: Write v17.** `[meta] version = "fairband-policy-v17"`; a header line `# v17: v16
  with one_time_items_share in nri_flag_share's place, and warning_mark_min (spec 2026-11-19 7.2,
  7.4)`; `[values.nri_flag_share]` out; in its place `[values.one_time_items_share]`, `value =
  0.20`, `source = "the founder, 2026-11-19: of four thresholds tested on 392 Mature Stable rows,
  20% warns 45% of rows and finds 89% of the large moves"`; then `[values.warning_mark_min]`,
  `value = 3`, `source = "the founder, 2026-11-19: three warnings or more"`. `check` holds
  `one_time_items_share: must be from 1% to 50%`.
- [ ] **Step 4: Implement the engine; then the literals.** `grep -rn
  "fairband-mechanical/1\.[56]\|fairband-policy-v16" tests src docs/method*.md` finds each copy
  (`test_types.py`, `test_route.py`, `test_render.py`, `research_answers.py`, `page_answers.py`,
  `test_company_reads.py`, `test_settings_api.py`, `test_settings.py` among them); each names 1.7
  or v17, but the v16 file itself and the tests that read it as v16.
- [ ] **Step 5: Re-capture MSCO** by the README's command. Its one change is the input
  `street_ttm_eps`, `null`; a README paragraph says so.
- [ ] **Step 6: The documents.** `method.md`: the head; 4.1's rows (the old out; the two new, each
  with its source) and "Policies v1 to v16 stay … loads v17 only."; 5.11 (reason 1 by spec 7.3);
  5.12, 6.1 and 6.5 (the input, the warning, the refusal's warning); 8 (spec 7.2's row word for
  word, the old note out); 11 (the 1.7 row begun). `method-overview.md`: the versions.
  `methodology.html`: the warning's item first, the old note's item out.
- [ ] **Step 7: Run `uv run pytest -q`.** Expected: pass. Run the checks, then commit.

### Task 3: The engine takes no gap (spec 7.1)

**Files:**
- Modify: `engine/route_steps.py` (`nri_gap` out, `common_inputs`, the docstring), the four
  routes, `engine/route.py` (`CompanyInputs`, its docstrings), `engine/overrides.py`
  (`_reading`), `refresh/inputs.py` (stop passing the two fields), `reports/render.py`
  (`GLOSSARY`); `docs/method.md` (5.9, 5.12, 6.1, 6.5, 11, 13, 14.2, 14.4),
  `docs/method-overview.md`, `web/static/methodology.html` (the value section, Mature Stable's
  step 1, KO's "once one-off items are removed"); `tests/support/engine_companies.py`,
  `tests/fixtures/golden/*.json` and the goldens' `README.md`
- Test: `tests/engine/` (`test_route.py`, `test_overrides.py`, `test_review.py`,
  `test_route_decline.py`, `test_mature_stable.py`, `test_golden.py`),
  `tests/reports/test_render.py`, `tests/web/test_methodology.py`

**Interfaces:**
- Consumes: Task 2's `trailing_flags` and `_stock_pay_notes(c, anchor)`.
- Produces: `CompanyInputs` without `gf_eps_ttm` and `gf_eps_without_nri`; no
  `route_steps.nri_gap`. The mature routes read `chosen(c, "earnings.nri_gap", None)` and keep
  the intermediate `nri_gap`, `null` without an override; the other routes call `eps(t, None,
  …)`. Mature Growth's basis correction is the agent's whole figure. `current_reading(result,
  "earnings.nri_gap")` is the stored figure where not `None`, else `0.0` on a Mature Growth or
  Mature Stable result, else `None`.

- [ ] **Step 1: Write the failing tests:**

```python
def test_every_mechanical_route_takes_no_gap(deciles, policy) -> None:     # test_route.py
    # every FIXTURES builder: intermediates.get("nri_gap") is None; eps clean == reported
def test_mature_stable_starts_from_trailing_net_income(ms_inputs, ...) -> None:
    assert r.intermediates["e_trailing"] == 3_400e6 and r.intermediates["eps"]["clean"] == 3.40
def test_the_agents_gap_still_applies_on_both_mature_routes(...) -> None:
    # MSCO under earnings.nri_gap 0.10: e_trailing 3_300e6, clean 3.30, a lower value;
    # MGCO under 0.20: clean 5.10 and epv == pytest.approx(5.10 / 0.09)
def test_the_basis_test_takes_the_agents_whole_figure(...) -> None:       # test_overrides.py
    # MGCO reads 0.0, and an override of 0.0 moves nothing; one of 0.12 takes GAAP 5.30 to
    # 5.18, street 5.35 lies 0.17 above, so the basis reads excludes-sbc
def test_the_engine_reads_a_nil_gap_on_the_mature_routes(...) -> None:
    # 0.0 on MGCO's and MSCO's mechanical results, None on HGCO's
```

Delete `test_mature_stable_without_the_nri_gap`; `test_overrides.py` near 797 reads `0.0`. The
tests that set `gf_eps_without_nri` for a found gap (`test_route.py` near 569 and 618,
`test_review.py` near 667, `test_overrides.py` near 1129) set the agent's gap or the street figure
their subject needs; `test_route_decline.py` near 937 loses the two names.

- [ ] **Step 2: Run the engine tests.** Expected: fail.
- [ ] **Step 3: Implement**, with every docstring that names the gap or GuruFocus's EPS; the
  glossary's entry is the Words table's.
- [ ] **Step 4: Re-capture the seven goldens and read each diff before keeping it.** MSCO's E
  goes from 3,300 m to 3,400 m and its value up; MGCO and FXCO lose a clean EPS that differs;
  every golden loses the two GuruFocus inputs; nothing else moves. A README paragraph gives MSCO's
  old and new value.
- [ ] **Step 5: The documents.** `method.md` 6.1: "E = trailing net income − an agent's
  non-recurring gap × diluted shares; the mechanical route takes no gap"; 5.9: the clean figures
  equal the reported ones except under an agent's gap; 5.12 and 6.5 lose the two inputs; 13; 14.2
  and 14.4 (the whole gap is the agent's; the engine reads 0.0, so a bridge's old value is 0.00);
  11. `methodology.html`: the value section's sentences; step 1 reads "Trailing earnings are the
  starting point."; KO's sentence loses its clause. `method-overview.md`'s Mature Stable row:
  "Trailing earnings grow at terminal growth."
- [ ] **Step 6: Run `uv run pytest -q`.** Expected: pass. Run the checks, then commit.

### Task 4: Assembly and the fetch read no GuruFocus EPS (spec 7.1)

**Files:**
- Modify: `refresh/inputs.py` (`_OBSERVATIONS`, `_KEYRATIOS`, the `gf-ratio` read, `_Money.mean`,
  `ends`), `refresh/inputs_splits.py` (`SplitFigures`, `_split_rule`, `_gurufocus_side`,
  `_observed`, the docstrings), `refresh/rates.py` (`FxSeries.mean_at`), `refresh/fetch.py` (the
  call, `_GF_ENDPOINTS`, `_rows`, the import, the docstring's counts), `vendors/gurufocus.py`
  (`keyratios`), `vendors/normalize_gf.py` (`keyratios_observations`),
  `tests/refresh/fixture_universe.py`; `docs/method.md` (2, 4.2, 7.1, 7.4, 11),
  `docs/method-overview.md` (the data line)
- Delete: `tests/fixtures/gurufocus/keyratios.ACME.json`, `keyratios.BOLT.json`
- Test: `tests/refresh/` (`test_inputs.py`, `test_splits.py`, `test_rates.py`, `test_fetch.py`,
  `test_run.py`, `test_run_full.py`), `tests/vendors/test_gurufocus.py`,
  `tests/web/test_company_page_api.py`

**Interfaces:**
- Consumes: Task 3's `CompanyInputs`.
- Produces: no new name. `SplitFigures` without its GuruFocus fields; `_Money` without `mean`;
  `FxSeries` without `mean_at` (search `src/` first: no caller may remain); `GuruFocus` with
  `summary` alone. Stored `gf-ratio` observations and `keyratios` answers stay, unread.

- [ ] **Step 1: Write the failing tests:**

```python
def test_a_fetch_makes_one_gurufocus_call(...) -> None:              # test_fetch.py
    assert router.calls["summary"] == 1 and router.calls["keyratios"] == 0
def test_assembly_reads_no_gurufocus_eps(...) -> None:               # test_inputs.py
    # a stored gf-ratio observation is not read: no provenance key gf_eps_*, no note
def test_the_split_rule_names_no_gurufocus_figure(...) -> None:      # test_splits.py
    # a pending split: no sentence "GuruFocus's EPS observed", no note under gf_eps_*
```

Then the counts: `GF_ENDPOINTS = ("summary",)`, `DATASETS` without `gf-ratio`, and each count that
held `keyratios` one lower (`test_run.py` 33 to 32, "31 FMP and 1 GuruFocus"; `test_run_full.py`
34 to 33 and 67 to 65; `test_fetch.py` 32 to 31 and 31 to 30); without a GuruFocus client
`outcome.failed == ("summary",)` (`test_fetch.py`, `test_company_page_api.py` near 676). Delete
the `keyratios` tests of `test_gurufocus.py`, `test_rates.py`'s `mean_at` tests and
`test_splits.py`'s GuruFocus case near 402.

- [ ] **Step 2: Run `uv run pytest -q tests/refresh tests/vendors tests/web`.** Expected: fail.
- [ ] **Step 3: Implement the removals.** `method.md` 2 loses the `keyratios` row; 4.2's split
  bullet on GuruFocus's EPS goes; 7.1 drops "GuruFocus states its EPS in USD per ADS"; 7.4 loses
  its row and names the street actuals alone; 11's row names the call. `method-overview.md`:
  "GuruFocus supplies the Moat Score."
- [ ] **Step 4: Run `uv run pytest -q` and `grep -rn "keyratios\|gf-ratio\|gf_eps\|mean_at" src`.**
  Expected: pass; the search finds nothing. Run the checks, then commit.

### Task 5: The row's `warnings` and `marked` (spec 7.5; Review Focus 1, 5)

**Files:**
- Create: `src/fairband/web/warning_words.py`, `tests/web/test_warning_words.py`
- Modify: `web/rows.py` (`screen_row`, `placeholder_row`, the docstring), `web/app.py`
  (`screen_rows`, `company()` and its docstring)
- Test: `tests/web/test_rows.py`, `tests/web/test_app.py` (the whole-row and placeholder pins)

**Interfaces:**
- Consumes: Task 2's `QUALITY_WARNINGS` and `Policy.warning_mark_min`.
- Produces:

```python
WARNING_WORDS: Mapping[str, str]   # the eleven codes but margin-flag, the Words table's
MARGIN_WORDS: Mapping[str, str]    # margin-flag's Flag.word -> its words
def warning_words(flags: Sequence[Flag]) -> list[str]
    # each flag whose code is in QUALITY_WARNINGS, in the flags' order; margin-flag by
    # MARGIN_WORDS, an unknown word reading "margin above its history"
def is_marked(value: float | None, reviewed: float | None, warnings: Sequence[str],
              mark_min: int) -> bool
def screen_row(snapshot, company, today, aging_fraction, watchlists, agents, *,
               mark_min: int) -> dict[str, Any]
```

  - A screen row gains `warnings: list[str]`, from `snapshot.result.flags` and never a review's,
    and `marked: bool`, `is_marked(snapshot.value, agents["reviewed"], …)`; neither is a row key,
    as `covered` is not. A placeholder has `[]` and `false`. `flags` and `flagCount` stay.
  - The detail gains `warnings`, the snapshot's, and `marked`, read against the counting review.

- [ ] **Step 1: Write the failing tests:**

```python
def test_every_quality_warning_has_its_words() -> None:
    assert set(WARNING_WORDS) | {"margin-flag"} == QUALITY_WARNINGS
def test_the_words_follow_the_flags_and_leave_the_notes_out() -> None:
def test_margin_flag_reads_by_its_word() -> None:
def test_a_result_valued_before_1_7_counts_neither_old_code() -> None:
    old = (Flag("large-nri", "", ""), Flag("consensus-basis-unknown", "", ""))
    assert warning_words(old) == []
def test_is_marked() -> None:
    three = ["a", "b", "c"]
    assert is_marked(12.40, None, three, 3) and not is_marked(12.40, None, three[:2], 3)
    assert not is_marked(12.40, 13.0, three, 3) and not is_marked(None, None, three, 3)
def test_the_row_reads_the_snapshots_flags_not_the_reviews(...) -> None:    # test_rows.py
def test_the_screen_rows_carry_warnings_and_marked(client) -> None:         # placeholder too
def test_the_detail_carries_warnings_and_marked(client) -> None:
```

- [ ] **Step 2: Run the three files.** Expected: fail.
- [ ] **Step 3: Implement.** `screen_rows` passes `mark_min=read_under.warning_mark_min`; the
  test calls of `screen_row` pass `mark_min=3`.
- [ ] **Step 4: Run `uv run pytest -q tests/web`.** Expected: pass. Run the checks, then commit.

### Task 6: The screen: the mark and the hovers in, two columns and a filter out (spec 7.5, 9)

**Files:**
- Modify: the bundle (the `mechanical` column and its head's title; `warningsHover`,
  `WarningMark`, the exports; the `flags` and `flagCount` columns; `FILTER_FLAGS`, `FLAG_WORDS`,
  `FLAG_ROWS`, `EMPTY_FILTERS`, `clearAll`), its `bundle.css` (the mark's rule, beside
  `.fb-screen__mech`) and `index.d.ts`; in `web/static/`, `app.js` (`narrow`, the two notes,
  the Screen's props), `watchlists.js`,
  `methodology.html` (the flags section, its two "Flags column" sentences, "Where to read them");
  `docs/method.md` (8), `docs/method-overview.md`
- Create: `tests/web/test_warning_mark.py`
- Test: `tests/web/test_app.py` (`EXTRA_COLUMN_HEADS` and the six tests that pin the two columns,
  `FILTER_FLAGS`, `cleanOnly` and `index.d.ts`), `tests/web/test_methodology.py`

**Interfaces:**
- Consumes: Task 5's `warnings` and `marked`.
- Produces, each a `fairband:` patch documented in `index.d.ts`:
  - `Fairband.warningsHover(words: string[], note: string): string`, the three forms.
  - `Fairband.WarningMark(props: { words: string[] })`: `<span class="fb-warnmark" role="img"
    aria-label={the first sentence}>•</span>`.
  - `ScreenTableProps.mechanicalNote?: string`. Given it, the Mechanical head's `title` is the
    note, and a Mechanical cell with a value has the `title` `warningsHover(r.warnings || [],
    note)`, the mark before the figure where `r.marked`. A cell with no value has neither.
    Without the prop the cell is as before. A column may carry `title(p)` for its head.
  - `ScreenRow` gains `warnings?: string[]` and `marked?: boolean` and loses `flags?` and
    `flagCount?`, which no column reads; `ScreenFilters` loses `cleanOnly`.
  - `FairbandPage.SCREEN_NOTE` and `FairbandPage.OPEN_NOTE`; `app.js` and `watchlists.js` pass
    `mechanicalNote: P.SCREEN_NOTE`.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_warning_mark.py` (node, the bundle):

```python
def test_the_hover_s_three_forms() -> None:          # none, one word, three words
def test_the_mark_is_the_bullet_with_its_label() -> None:
def test_a_marked_row_s_cell() -> None:              # td title; its first child the mark
def test_a_row_under_the_cut_off_keeps_the_hover_alone() -> None:
def test_a_refused_row_s_dash_has_no_hover_and_no_mark() -> None:
def test_the_mechanical_head_carries_the_note() -> None:
def test_without_the_prop_the_cell_is_as_before() -> None:
def test_the_removed_columns_are_no_column_keys() -> None:   # "flags", "flagCount"
```

Text pins in `test_app.py`: two `FILTER_FLAGS`; no `cleanOnly` in the bundle, `app.js` or
`index.d.ts`; `narrow` without the Clean line; no `{ key: 'flags'` or `{ key: 'flagCount'`;
`watchlists.js` passes `mechanicalNote`; `bundle.css` holds `.fb-warnmark { font-family:
var(--font-mono); font-size: 22px; line-height: 0; margin-right: 5px; vertical-align: -3px; }`
(form A, in the value's ink; the drawer and the company page load the same file). `test_methodology.py`: the flags section names the mark, the hover
and `<span data-policy="warning_mark_min">—</span>`; no Flags column, Warnings column or Clean
filter is named.

- [ ] **Step 2: Run the two files.** Expected: fail.
- [ ] **Step 3: Implement.** A saved column list naming `flags` or `flagCount` loses it through
  `normalise`, unchanged. `methodology.html`: the screen draws no flag; a dot marks a mechanical
  value with that many warnings or more and no review, and a hover names them; notes "are read by
  an agent and never count"; "Where to read them" drops the columns and the filter; 25 words or
  fewer a sentence. `method.md` 8: "a short word" for "a short word for the column", and a
  paragraph on the mark, the hover and their rule. `method-overview.md`: "Twelve flags are
  quality warnings; the screen marks a mechanical value with three or more."
- [ ] **Step 4: Run `uv run pytest -q tests/web`.** Expected: pass. Run the checks, then commit.

### Task 7: The drawer and the company page (spec 7.5; Review Focus 5)

**Files:**
- Modify: the bundle (`BandMeter`), `index.d.ts` (`BandMeterProps`), `web/static/app.js` (`meter`,
  `levelRows`, their comments), `tests/support/page_answers.py` (`DETAIL` gains `warnings` and
  `marked`)
- Test: `tests/web/test_drawer_form.py`, `test_company_overview.py`, `test_warning_mark.py`

**Interfaces:**
- Consumes: Task 5's detail fields; Task 6's `warningsHover`, `WarningMark`, `OPEN_NOTE`.
- Produces: `BandMeterProps.fairTitle?: string` (the `title` of `fb-band__fairmark`) and
  `captionTitle?: string` (the `title` of `fb-band__caption`). `meter(body)` passes `fairTitle` on
  a valued row with no counting review and `captionTitle` on a reviewed one, each
  `warningsHover(body.warnings, OPEN_NOTE)`. `levelRows(body)`, on a valued row with no review,
  gives the Fair value row a span with that `title` as its figure, led by the mark where
  `body.marked`. A refused row has neither. `company_overview.js` draws both through `P.meter` and
  `P.levelRows` and does not change; `kv` takes an element as a figure.

- [ ] **Step 1: Write the failing tests:**

```python
def test_an_unreviewed_value_carries_the_hover_and_the_mark() -> None:    # test_drawer_form.py
def test_a_row_under_the_cut_off_has_the_hover_and_no_mark() -> None:
def test_a_reviewed_row_s_caption_carries_the_hover_and_no_mark() -> None:
def test_a_refused_row_carries_no_hover() -> None:
def test_the_value_block_draws_the_same_hover_and_mark() -> None:   # test_company_overview.py
def test_the_meter_takes_the_two_titles() -> None:                  # test_warning_mark.py
```

- [ ] **Step 2: Run the three files.** Expected: fail.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run `uv run pytest -q tests/web`.** Expected: pass. Run the checks, then commit.

### Task 8: The playbook (spec 7.5, its five changes)

**Files:**
- Modify: `playbook/fairband-research/SKILL.md` (step 5, step 8, "Nothing counts twice"),
  `playbook/fairband-research/reference/report-template.md` (the clean P/E's gloss)
- Test: `tests/test_playbook.py`

**Interfaces:**
- Consumes: the warning and the refusal's sentence (Task 2); the agent's whole gap (Task 3).

- [ ] **Step 1: Write the failing tests and move the pins:** `test_the_agent_judges_the_runway_
  return_and_reads_the_notes` loses its `consensus-basis-unknown` entry, `test_the_skill_reads_a_
  foreign_filer` reads "Twelve flags ask for a decision of yours.", and two tests read the new
  words (`test_nothing_counts_twice_route_by_route`, `test_the_template_s_words_state_…`).

```python
def test_step_5_says_the_mechanical_value_keeps_one_time_items() -> None:
def test_step_8_holds_the_one_time_items_step() -> None:
    # every Mature Stable review, no flag needed; the recipe's parts; `earnings.nri_gap`,
    # period-tied, the filing as evidence; section 8 where the filings show none;
    # `one-time-items` and "no positive trailing earnings" named as cues, not as a gate
def test_the_ntm_one_time_item_advice_stays_with_no_flag() -> None:   # `earnings.ntm_nri`
def test_the_asset_rule_reads_the_whole_gap() -> None:     # "your figure is the whole gap"
def test_no_flag_entry_names_the_removed_codes() -> None:
```

- [ ] **Step 2: Run `uv run pytest -q tests/test_playbook.py`.** Expected: fail.
- [ ] **Step 3: Write the changes.** Step 5's sentence and the gloss are the Words table's. Step
  8 gains, after the flags list, the standing step: the mechanical value keeps the one-time items
  of the trailing earnings; sum those of the trailing four quarters; count restructuring,
  impairments, gains and losses on sales, litigation and debt retirement; take them after tax and
  a diluted share; write a net charge as a negative figure; set the sum through
  `earnings.nri_gap`, period-tied, the filing as evidence; where the filings show none, say so in
  section 8 and set nothing. Then the old entry's Mature Growth paragraph, with no flag named.
  "Nothing counts twice": Mature Stable's "the gap found, raised by the gains" becomes "your
  figure is the whole gap, the one-time items of step 8 with the gains"; Mature Growth loses
  "`consensus-basis-unknown` says when that basis is unknown". Lines of 100 or fewer.
- [ ] **Step 4: Run the file.** Expected: pass. Run the checks, then commit.

### Task 9: Acceptance, the look, the examples, the readout and the live steps (spec 10, 11)

**Files:**
- Create, outside the repository:
  `~/.local/share/fairband/research/gurufocus-removal-2026-11-19/accept_plan2.py`
- Modify: `web/static/methodology.html` (KO's table, sentence and caption; the header comment;
  "Figures as of"), `tests/web/test_methodology.py` (`test_the_examples_are_dated_to_method_1_4`),
  `docs/method.md` (11's counts), the spec's decision log, `docs/backlog.md`

- [ ] **Step 1: Write the acceptance script.** It opens
  `file:<folder>/fairband-refresh-68-reference.db?mode=ro&immutable=1` and calls no vendor. As
  `nogap.py` does (`effective_policy`, `load_tax_table`, `latest_deciles`, the top refresh's
  newest snapshot of each symbol, `today` its newest data date), it runs `build_inputs` and
  `value_company` with the worktree's code on every symbol, each row against `nogap.pkl` (`base`
  the stored value, `bare` the value with no gap) within 1e-6 of its size, as `nogap_read.py` does.
- [ ] **Step 2: Run it from the worktree**, `uv run python -I <script>`. It passes when 1,558
  companies are read, none raising; Mature Growth, High Growth, Young Growth and Decline keep
  their 915 valued rows, each value its stored one; and of Mature Stable's 448 valued rows 301 go
  down, 90 up, 38 stay and 19 are refused "no positive trailing earnings", each value and refusal
  `bare`'s. It reports, untested: the rows `one-time-items` is on, valued and refused (against
  177 of 392); the valued rows with `warning_mark_min` warnings or more by `warning_words`, all
  and without a reviewed value (against 151 to 193); the rows holding reason 1 of
  `sbc-basis-uncertain` (against the 50 of refresh 58); each review recomputed in memory with
  `review_company` on its `applied_overrides`, named where it differs from the stored one.
- [ ] **Step 3: The look, by the mockup README's recipe**, from the worktree on port 8499, the
  keys unset, the scratch folder outside the repository: the page's own marks, the cell's and the
  head's hover, the drawer and the company page of a marked row and a reviewed one, both themes.
  The scratch rows predate 1.7, so their `large-nri` no longer counts (Review Focus 1).
  Screenshots go to the research folder's `look/`; stop the server by its process id.
- [ ] **Step 4: The examples.** The five on other routes do not move under 1.7 (step 2) and stand.
  KO is re-read from the reference database under 1.7: its table, sentence and caption, dated
  from its snapshot. The header comment and "Figures as of" say so, and the test pins it.
  `method.md` 11's row gains step 2's counts. Run the checks, then commit.
- [ ] **Step 5: The whole-branch review** by a fresh reviewer with the spec, this plan and the
  Review Focus list; its findings fixed or filed.
- [ ] **Step 6: Ask the owner once, with the list** (spec 11): (1) the acceptance's figures and
  the look; (2) a backup with SQLite's backup to
  `~/.local/share/fairband/fairband-before-method-1.7-<date>.db`; (3) the server on 8470 stopped
  by its process id (`lsof -ti:8470 -sTCP:LISTEN`), main fast-forwarded to the branch and pushed;
  (4) `uv run python -m fairband refresh --kind revalue` from the main checkout; (5) the server
  started from main on 8470, the page looked at on the live data; (6) the readout in the spec's
  decision log (Mature Stable's moves and refusals; the counts of the warning, the mark and reason
  1; the reviews that moved, CLS's override 36 dropped, PLTR's 20 kept), B-258 and B-259 moved to
  Done with their commits and the limits found filed, a documents-only commit, pushed. No tool
  changes, so no research session restarts its MCP process. Then run each approved step in that
  order and report its result.
