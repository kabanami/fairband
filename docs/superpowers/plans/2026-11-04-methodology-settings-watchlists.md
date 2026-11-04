# Methodology page, settings and watchlists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Methodology view that teaches the method with live values and real examples, a Settings view over a database overlay of the policy with a settings hash on every snapshot, and watchlists with a flag-count column and a clean filter, as method 0.8 and policy v6.

**Architecture:** The policy file stays the defaults; `fairband.policy.settings` names the 40 settable values and checks their ranges, `fairband.store.settings` keeps the overlay and builds the effective `Policy`, and every run and request reads the effective policy. The engine cites `policy.settings_hash` on each result, the store writes it on snapshots and refreshes, and the price refresh reprices only under the same version and hash. The page gains three views over new JSON routes; the bundle takes named `// fairband:` patches for the mark, the two filters and the two columns.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, pytest, mypy, ruff; React 18 and the vendored design system (`web/static/design-system/`, patched by hand); no JavaScript test runner.

**Spec:** `docs/superpowers/specs/2026-11-04-methodology-settings-watchlists-design.md`

## Global Constraints

- Checks before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, ending with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and `Claude-Session: https://claude.ai/code/session_01K4pNFGMWqnrPuvG88Nf31f`.
- Never print, log, store or commit a key; no setting holds a key or a path. Never commit vendor data; fixtures are synthetic.
- `docs/method.md` changes in the same commit as the engine, the classifier, the universe rule or a policy value; from Task 8 on, `web/static/methodology.html` too.
- Policy files, once versioned, are never edited: `fairband-policy-v5.toml` stays byte for byte; v6 is a new file. `METHOD_VERSION` becomes `"fairband-mechanical/0.8"` in Task 2.
- At the defaults, every value, level, designation and flag is bit for bit what policy v5 and method 0.7 give (spec 2).
- New bundle behaviour is a `// fairband:` patch with a comment naming the spec section; `tests/web/test_app.py::test_bundle_patches_marked` counts them.
- Prose on the page follows the output style's rules: sentences of 25 words or fewer, one idea each, no idiom, an invented term's plain meaning in brackets the first time.
- Dates in markup ride in `datetime` as ISO; readers see `3 Dec 2026` (design system).
- Text the page shows comes from the design system's words: `Settings`, `Watchlists`, `Methodology`, never a gear or an icon.

## Review Focus

1. A settings overlay row whose name a later policy version no longer knows (the file renames a value): `effective_policy` must raise naming the row, not crash a run; Task 3 tests it.
2. A watchlist symbol that leaves the universe or has no snapshot: the Watchlists view and `GET /api/watchlists` must still list it; Task 5 tests the route and Task 8 pins the view's row with no snapshot.
3. A price refresh over snapshots valued before the migration (hash column filled with the empty hash) while the overlay is empty: every row must reprice; Task 4 tests it.
4. A `PUT /api/settings` that fails on the second of two changes must leave the first unwritten; Task 6 tests all-or-none.
5. A `repricing_horizon_years` longer than a Mature Growth row's path on a None-moat runway of 4: the expected return must compute, padded at g_T; Task 2 tests it.

---

### Task 0: Golden results from the 0.7 engine

The six fixtures' result dicts under policy v5 and method 0.7, captured before anything changes, so Task 2 can prove the defaults unchanged.

**Files:**
- Create: `tests/fixtures/golden/README.md`, `tests/fixtures/golden/<SYMBOL>.json` (six files)
- Create: `tests/engine/test_golden.py`
- Test: `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `tests/engine/test_golden.py::golden_dict(result: ValuationResult) -> dict` (the result as `json.loads(result_to_json(result))` with the keys `policy_version`, `method_version` and `settings_hash` removed) and the six golden files, compared by `test_defaults_match_the_0_7_golden`.

- [ ] **Step 1: Write the capture script and the test**

`tests/engine/test_golden.py`:

```python
"""The six engine fixtures under the packaged policy at its defaults, against the result dicts
captured from method 0.7 and policy v5 before the settings build (spec 2026-11-04, 2 and 11).
The version fields are masked: the dict's figures are what must not move."""

GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden"
MASKED = ("policy_version", "method_version", "settings_hash")
FIXTURES = {
    "MGCO": mature_growth_inputs, "MSCO": mature_stable_inputs, "HGCO": high_growth_inputs,
    "YGCO": young_growth_inputs, "DCCO": decline_inputs, "SUCO": start_up_inputs,
}  # the fixtures' own symbols (tests/support/engine_companies.py)


def golden_dict(result: ValuationResult) -> dict[str, Any]:
    d = json.loads(result_to_json(result))
    for key in MASKED:
        d.pop(key, None)
    return d


@pytest.mark.parametrize("symbol", sorted(FIXTURES))
def test_defaults_match_the_0_7_golden(symbol: str) -> None:
    result = value_company(FIXTURES[symbol](), universe_deciles(), load_policy(), TODAY)
    assert golden_dict(result) == json.loads((GOLDEN / f"{symbol}.json").read_text())
```

`TODAY = date(2026, 10, 31)`, as `tests/engine/test_route.py` has it.

- [ ] **Step 2: Capture the goldens with the current engine**

Run, once, from the repository root: a four-line script that loops over `FIXTURES`, values each with `load_policy()` and writes `json.dumps(golden_dict(result), indent=1, sort_keys=True)` to `tests/fixtures/golden/<symbol>.json`. Put the script's text in `tests/fixtures/golden/README.md` with the sentence "Captured from method 0.7, policy v5, on 2026-11-04; regenerate only when the method changes on purpose."

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/engine/test_golden.py -v`
Expected: 6 PASS

- [ ] **Step 4: Commit**

```bash
git add tests/engine/test_golden.py tests/fixtures/golden
git commit -m "Capture the six engine fixtures' results under method 0.7 as golden files"
```

---

### Task 1: Policy v6, the settings catalogue and the range checks

**Files:**
- Create: `src/fairband/policy/fairband-policy-v6.toml`
- Create: `src/fairband/policy/settings.py`
- Modify: `src/fairband/policy/__init__.py` (the `Policy` dataclass, `load_policy`, `_POLICY_FILE`)
- Test: `tests/policy/test_policy.py`, `tests/policy/test_settings.py`

**Interfaces:**
- Produces: `Policy` gains `wide_terminal_roic_spread: float`, `repricing_horizon_years: int`, `settings_hash: str`; loses the fields `wide_terminal_roic_cap` and `designation_edges` and gains them back as read-only properties (`policy.designation_edges -> tuple[float, float, float, float]`, `policy.wide_terminal_roic_cap -> float`), so no engine read site changes.
- Produces: `fairband.policy.settings`:
  - `Setting` (frozen dataclass): `name: str` (the policy name, dotted for `universe.*` and `refresh.*`), `group: Literal["valuation", "flags", "validity", "universe", "refresh"]`, `label: str`, `description: str`, `unit: Literal["fraction", "points", "years", "times", "days", "seconds", "hours", "count", "usd", "symbols", "exchanges", "cap_bands"]`, `effect: Literal["revalue", "full", "run", "at once"]`, `range_text: str` (the Range column of spec 8.2, as the API serves it), `hashed: bool`.
  - `SETTINGS: tuple[Setting, ...]` — the 40 names of spec 8.2 in its order; `hashed` is true for groups valuation and flags and for `validity_fallback_days`, false otherwise.
  - `EMPTY_SETTINGS_HASH: str` — `hashlib.sha256(b"{}").hexdigest()`.
  - `settings_hash(overlay: Mapping[str, Any]) -> str` — sha256 of `json.dumps({k: v for k, v in overlay.items() if setting(k).hashed}, sort_keys=True)`.
  - `setting(name: str) -> Setting` — `KeyError` for an unknown name.
  - `apply_overlay(base: Policy, overlay: Mapping[str, Any]) -> Policy` — `dataclasses.replace` with each value converted by the same converters `load_policy` uses, nested names replacing inside `universe` and `refresh`; sets `settings_hash`; then `check(policy)`.
  - `check(policy: Policy) -> None` — every range of spec 8.2 and every rule of 8.9; raises `ValueError("<name>: <rule>")`, the rule a plain sentence (`"required_return: must be above terminal_growth"`).
  - `default_of(name: str, base: Policy) -> Any` — the file's value for the name, in the JSON form the API serves.
- Consumes: nothing new.

- [ ] **Step 1: Write the v6 file**

Copy v5 to `fairband-policy-v6.toml`; set `[meta] version = "fairband-policy-v6"`; remove `[values.designation_edges]` and `[values.wide_terminal_roic_cap]`; add:

```toml
[values.wide_terminal_roic_spread]
source = "design.md 6.6: the Wide moat's terminal return is at most r + 4 points; spec 2026-11-04 8.3 derives the cap from r so a changed r carries it"
value = 0.04

[values.repricing_horizon_years]
source = "stocks method v1.7 Step 9; design.md 1 (the 3-year repricing horizon); spec 2026-11-04 8.3"
value = 3
```

Add to the header comment one line: "v6: the edges and the Wide cap are derived (spec 2026-11-04 8.3); the user's settings overlay these defaults."

- [ ] **Step 2: Write the failing policy tests**

In `tests/policy/test_policy.py`, change `_packaged_bytes` and `test_v5_is_the_packaged_policy` into `test_v6_is_the_packaged_policy`, add `V5_SHA256` as the v5 file's hash today (compute it once with `sha256sum`) and `test_v5_file_is_unchanged`, and add:

```python
def test_v6_derives_the_edges_and_the_wide_cap() -> None:
    p = load_policy()
    assert p.version == "fairband-policy-v6"
    assert p.designation_edges == (0.65, 0.85, 1.15, 1.5)
    assert p.wide_terminal_roic_cap == 0.13
    assert p.wide_terminal_roic_spread == 0.04 and p.repricing_horizon_years == 3
    assert p.settings_hash == EMPTY_SETTINGS_HASH
    assert "designation_edges" not in p.raw["values"]


def test_v6_is_v5_with_the_two_values_swapped() -> None:
    # as test_v5_is_v4_with_the_new_values does: the same values but the two removed and the two added
```

In `tests/policy/test_settings.py`:

```python
def test_forty_settings_in_the_spec_order() -> None:
    assert len(SETTINGS) == 40
    assert [s.name for s in SETTINGS[:3]] == ["required_return", "terminal_growth", "runway_years"]
    assert SETTINGS[-1].name == "refresh.gf_reuse_days"
    assert {s.group for s in SETTINGS} == {"valuation", "flags", "validity", "universe", "refresh"}


def test_hash_covers_valuation_flags_and_the_fallback_only() -> None:
    assert settings_hash({}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"aging_fraction": 0.5}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"refresh.workers": 4}) == EMPTY_SETTINGS_HASH
    assert settings_hash({"validity_fallback_days": 60}) != EMPTY_SETTINGS_HASH
    assert settings_hash({"required_return": 0.1}) == settings_hash({"required_return": 0.1, "refresh.workers": 4})


def test_apply_overlay_changes_the_value_and_the_derived_edges() -> None:
    p = apply_overlay(load_policy(), {"required_return": 0.1, "fair_band": [0.8, 1.2], "universe.cap_floor_usd": 5e9})
    assert p.required_return == 0.1 and p.wide_terminal_roic_cap == pytest.approx(0.14)
    assert p.designation_edges == (0.65, 0.8, 1.2, 1.5) and p.universe.cap_floor_usd == 5e9
    assert p.version == "fairband-policy-v6" and p.settings_hash == settings_hash({"required_return": 0.1, "fair_band": [0.8, 1.2]})


@pytest.mark.parametrize(("overlay", "rule"), [
    ({"required_return": 0.02}, "required_return: must be from 4% to 20%"),
    ({"terminal_growth": 0.1}, "terminal_growth: must be below required_return"),
    ({"runway_years": {"None": 3, "Narrow": 10, "Wide": 20}}, "runway_years: each must be from 4 to 30 years"),
    ({"runway_years": {"None": 12, "Narrow": 10, "Wide": 20}}, "runway_years: None, Narrow, Wide must not decrease"),
    ({"fair_band": [0.9, 1.6]}, "fair_band: the high must be from 1.01 to 1.50"),
    ({"trim_multiple": 1.1}, "trim_multiple: must be above the fair band's high, up to 3.0"),
    ({"high_growth_years": 7, "fade_years": 5}, "high_growth_years: with fade_years, at most 10"),
    ({"industry_peer_max": 2}, "industry_peer_max: must be from peer_min to 50"),
    ({"refresh.rate_limit_hold_s": float("inf")}, "refresh.rate_limit_hold_s: must be from 1 to 3600"),
    ({"universe.cap_bands": [[2e11, "Mega"], [1e10, "Large"], [3e9, "Mid"]]}, "universe.cap_bands: the lowest must equal the size floor"),
    ({"universe.manual_admissions": ["v", "bad symbol"]}, "universe.manual_admissions: 'bad symbol' is not a symbol"),
    ({"unknown_name": 1}, "unknown_name: not a setting"),
])
def test_ranges_and_rules_name_the_setting(overlay: dict[str, Any], rule: str) -> None:
    with pytest.raises(ValueError, match=re.escape(rule)):
        apply_overlay(load_policy(), overlay)


def test_symbols_are_upper_cased_on_apply() -> None:
    p = apply_overlay(load_policy(), {"universe.manual_admissions": ["v", "ma"]})
    assert p.universe.manual_admissions == ("V", "MA")


def test_load_policy_checks_the_file_too(tmp_path: Path) -> None:
    # a copy of v6 with required_return = 0.02 raises "required_return: must be from 4% to 20%"
```

Write the rule sentences exactly as the parametrize gives them; the sentences are the API's `detail` (Task 6).

- [ ] **Step 3: Run the tests to see them fail**

Run: `uv run pytest tests/policy -q`
Expected: FAIL, `ImportError` on `fairband.policy.settings` and `AttributeError` on the v6 fields.

- [ ] **Step 4: Implement**

In `policy/__init__.py`: `_POLICY_FILE = "fairband-policy-v6.toml"`; the three new fields on `Policy` (`settings_hash` last, default `EMPTY_SETTINGS_HASH` is not possible on a frozen dataclass before non-defaults, so set it in `load_policy`); the two properties:

```python
@property
def designation_edges(self) -> tuple[float, float, float, float]:
    return (1 - self.margin_of_safety["Narrow"], self.fair_band[0], self.fair_band[1], self.trim_multiple)

@property
def wide_terminal_roic_cap(self) -> float:
    return self.required_return + self.wide_terminal_roic_spread
```

`load_policy` reads the two new names, sets `settings_hash=EMPTY_SETTINGS_HASH` and ends with `check(policy)` (import inside the function; `settings.py` imports `Policy` from the package, so the package imports `settings` lazily). Export the converters `settings.py` needs (`_num`, `_whole`, `_pair`, `_texts`, `_universe`, `_refresh`) or move them to a `policy/_convert.py` both import.

In `settings.py`: `SETTINGS` as a literal tuple of 40 `Setting(...)` rows, the labels and descriptions as spec 8.2 and 8.5 word them; `check` as one function of plain `if` tests, each raising the exact sentence; `apply_overlay` converts each value by the setting's unit (`fraction`, `points` → `_num`; `years`, `days`, `count`, `hours` → `_whole` except `burn_cover_flag_years` → `_num`; `seconds` → `_num`; `symbols` → upper-cased `_texts` checked by `re.fullmatch(r"[A-Z0-9.-]{1,10}", s)`; `exchanges` → `_texts`; `cap_bands` → the tuple of `(float, str)` pairs; `runway_years`, `margin_of_safety` → dicts by moat; `fair_band`, `roic_sensitivity` → `_pair`), then `replace`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/policy tests/engine -q`
Expected: the policy tests PASS; `tests/engine` PASS unchanged (the properties keep every read site working); `test_golden` PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/policy tests/policy
git commit -m "Add policy v6 with the derived edges and Wide cap, the repricing horizon, and the settings catalogue with its range checks"
```

---

### Task 2: Method 0.8: the horizon, the settings hash on a result, the flag count, and the method document

**Files:**
- Modify: `src/fairband/engine/__init__.py` (`METHOD_VERSION`)
- Modify: `src/fairband/engine/types.py` (`ValuationResult.settings_hash`, `result_from_json`)
- Modify: `src/fairband/engine/route.py` (`_valued`, `refusal_result`, `reprice` set `settings_hash`)
- Modify: `src/fairband/engine/route_steps.py:203-213` (`expected`)
- Modify: `src/fairband/engine/route_mature_growth.py:254`, `route_mature_stable.py:114`, `route_revenue_growth.py:334`, `route_decline.py:342`
- Modify: `src/fairband/engine/flags.py` (`QUALITY_WARNINGS`, `flag_count`)
- Modify: `docs/method.md` sections 0, 4.1, 4.7, 4.10, 5.10, 6.5, 8, 11
- Test: `tests/engine/test_returns.py`, `tests/engine/test_route.py`, `tests/engine/test_flags.py`, `tests/engine/test_types.py`, `tests/engine/test_golden.py`

**Interfaces:**
- Produces: `ValuationResult.settings_hash: str` (after `method_version`; `result_from_json` defaults a missing one to `EMPTY_SETTINGS_HASH`).
- Produces: `route_steps.expected(price: float, value: float, im: dict[str, Any], rates: Sequence[float], horizon: int, terminal: float) -> dict[str, float] | None` — pads `rates` with `terminal` up to `horizon` entries, then `expected_return(..., horizon=horizon)`.
- Produces: `flags.QUALITY_WARNINGS: frozenset[str]` (the eleven codes of spec 9.5) and `flags.flag_count(flags: Sequence[Flag]) -> int`.
- Consumes: `Policy.repricing_horizon_years`, `Policy.settings_hash` (Task 1).

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_returns.py`:

```python
def test_horizon_beyond_the_rates_is_padded_by_the_caller() -> None:
    # expected_return itself still raises; route_steps.expected pads (next test)
    with pytest.raises(ValueError, match="2 growth rates for a 3-year horizon"):
        expected_return(100, 120, 0.0, 0.0, (0.1, 0.1), horizon=3)
```

`tests/engine/test_route.py` (the fixtures `mg_inputs`, `ms_inputs`, `deciles`, `policy` exist in `tests/engine/conftest.py`; `TODAY` is the module's):

```python
def test_result_cites_the_settings_hash(mg_inputs, deciles, policy) -> None:
    r = value_company(mg_inputs, deciles, policy, TODAY)
    assert r.settings_hash == EMPTY_SETTINGS_HASH and r.method_version == "fairband-mechanical/0.8"
    custom = apply_overlay(policy, {"required_return": 0.1})
    assert value_company(mg_inputs, deciles, custom, TODAY).settings_hash == custom.settings_hash


def test_expected_pads_the_rates_at_the_terminal_rate() -> None:
    # route_steps.expected: two rates, a horizon of 4, padded with the terminal 3%
    im = {"dividend_yield": 0.01, "net_buyback_yield": 0.0}
    er = expected(100.0, 120.0, im, (0.1, 0.05), 4, 0.03)
    assert er is not None
    assert er["growth"] == pytest.approx((1.1 * 1.05 * 1.03 * 1.03) ** (1 / 4) - 1)
    assert er["repricing"] == pytest.approx(math.log(1.2) / 4)
    assert er["income"] == 0.01


def test_long_horizon_never_raises_on_a_short_runway(mg_inputs, deciles, policy) -> None:
    # every runway 4 gives the Mature Growth path three rates; a horizon of 6 is padded, not refused
    custom = apply_overlay(policy, {"repricing_horizon_years": 6, "runway_years": {"None": 4, "Narrow": 4, "Wide": 4}})
    r = value_company(mg_inputs, deciles, custom, TODAY)
    assert r.value is not None and r.refusal is None
    er = r.intermediates["expected_return"]
    assert er["repricing"] == pytest.approx(math.log(r.value / r.price) / 6)


def test_repricing_horizon_moves_the_expected_return(ms_inputs, deciles, policy) -> None:
    base = value_company(ms_inputs, deciles, policy, TODAY).intermediates["expected_return"]
    five = value_company(ms_inputs, deciles, apply_overlay(policy, {"repricing_horizon_years": 5}), TODAY).intermediates["expected_return"]
    assert five["repricing"] == pytest.approx(base["repricing"] * 3 / 5)
```

`tests/engine/test_flags.py`:

```python
def test_flag_count_counts_the_eleven_quality_warnings_only() -> None:
    flags = (Flag("leases-not-on-balance-sheet", "", ""), Flag("few-analysts", "", ""),
             Flag("margin-direction-disagrees", "", ""), Flag("line-not-presented:cash", "", ""))
    assert flag_count(flags) == 0
    assert flag_count(flags + (Flag("large-nri", "", ""), Flag("value-spread", "", ""))) == 2
    assert QUALITY_WARNINGS == frozenset({"large-nri", "value-spread", "margin-flag", "z-distress", "f-score-low",
        "reinvesting-in-decline", "equity-raise", "negative-fcf", "heavy-capex", "burn-cover-short", "consensus-recovery"})
```

`tests/engine/test_types.py`: a 0.7 result JSON without `settings_hash` loads with `EMPTY_SETTINGS_HASH`; a round trip keeps a custom hash.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/engine -q`
Expected: FAIL on `settings_hash`, `flag_count`, the version string, and `expected()`'s new arity.

- [ ] **Step 3: Implement**

- `METHOD_VERSION = "fairband-mechanical/0.8"`.
- `ValuationResult.settings_hash: str` after `method_version`; `result_from_json`: `d.setdefault("settings_hash", EMPTY_SETTINGS_HASH)`.
- `route.py`: `settings_hash=policy.settings_hash` beside `policy_version` in `_valued` and `refusal_result`; `reprice` keeps the result's own (it does not revalue).
- `expected(...)`: `padded = tuple(rates[:horizon]) + (terminal,) * max(horizon - len(rates), 0)`; callers pass `policy.repricing_horizon_years` and the terminal rate: `policy.terminal_growth` on Mature Growth, Mature Stable (rates `()`) and the revenue-growth route; `d` on Decline (rates `()`).
- `flags.py`: the frozenset and `flag_count` = the number of flags whose `code` is in it.
- `docs/method.md`: 0 gains the Methodology page line (spec 10); 4.1's table: the `designation_edges` row becomes "Designation edges, derived: 1 − the Narrow margin of safety, the fair band, the trim multiple" with no policy name, `wide_terminal_roic_cap` becomes `wide_terminal_roic_spread` 4 points, add `repricing_horizon_years` 3; a new column "Setting" marked yes on the 40; one paragraph after the table: the overlay and the effective policy, the settings hash and what it covers (spec 8.4). 4.7: "capped at r plus the spread (13% at the defaults)". 4.10: the edges derived. 5.10: H years, the geometric mean over years 2 to H + 1, the path padded at the terminal rate past the runway, repricing ÷ H; 6.5 says "H rates of g_T". 8: the column "Counts" and, before the table, the sentence of spec 9.5 with the eleven codes and the word "note" for the rest. 11: the 0.8 row.

- [ ] **Step 4: Run the tests, the golden test included**

Run: `uv run pytest tests/engine tests/policy -q`
Expected: PASS, `test_golden` included (the defaults reproduce 0.7 with the versions masked).

- [ ] **Step 5: Commit**

```bash
git add src/fairband/engine docs/method.md tests/engine
git commit -m "Cite the settings hash on every result, read the repricing horizon from the policy padded at the terminal rate, count the eleven quality warnings, and record method 0.8"
```

---

### Task 3: The store: migration 004, the settings overlay and the effective policy

**Files:**
- Create: `src/fairband/store/migrations/004_settings_and_watchlists.sql`
- Create: `src/fairband/store/settings.py`
- Modify: `src/fairband/store/snapshots.py` (`SnapshotRow.settings_hash`, `insert_snapshot`, `_snapshot`)
- Modify: `src/fairband/store/refreshes.py` (`create_refresh(..., settings_hash)`, `RefreshRow.settings_hash`, `_refresh`)
- Modify: `src/fairband/store/__init__.py` docstring (the two new record modules)
- Test: `tests/store/test_db.py`, `tests/store/test_settings.py`, `tests/store/test_snapshots.py`, `tests/store/test_refreshes.py`

**Interfaces:**
- Produces: the migration of spec 8.6 and 9.2, the literal default being `EMPTY_SETTINGS_HASH`'s value (`sha256("{}")`, write the 64 hex characters in the SQL).
- Produces: `fairband.store.settings`:
  - `read_overlay(conn) -> dict[str, Any]` — name to `json.loads(value)`.
  - `effective_policy(conn, base: Policy | None = None) -> Policy` — `apply_overlay(base or load_policy(), read_overlay(conn))`; a `ValueError` from the overlay (an unknown or out-of-range row) is re-raised as `ValueError("settings: <name>: <rule>; reset it on the Settings page")`.
  - `write_settings(conn, changes: Mapping[str, Any], reason: str | None, at: datetime, base: Policy | None = None) -> Policy` — builds the effective policy over `read_overlay | changes` first (which checks every range), then in one transaction upserts each row (`changed_at = at`) and inserts one `settings_changes` row with `[{"name", "old", "new"}]` (old is the previous overlay value or `None`); returns the new effective policy. Nothing is written when the check raises.
  - `reset_settings(conn, names: Sequence[str] | None, at: datetime) -> None` — deletes the rows (all when `names` is `None`) and logs the change with `new: None`.
  - `changes(conn) -> list[ChangeRow]` (`ChangeRow(id, changed_at, reason, changes)`), newest first.
  - `overlay_changed_at(conn) -> dict[str, datetime]` — name to `changed_at`.
- Produces: `create_refresh(conn, kind, symbols, policy_version, method_version, started_at, settings_hash: str)`; `RefreshRow.settings_hash`; `SnapshotRow.settings_hash` read from the column, written from `result.settings_hash`.
- Consumes: `apply_overlay`, `EMPTY_SETTINGS_HASH` (Task 1); `ValuationResult.settings_hash` (Task 2).

- [ ] **Step 1: Write the failing tests**

`tests/store/test_db.py`: `test_migration_004_fills_the_hash` — a connection migrated through 003 with one refresh and one snapshot inserted by raw SQL, then `migrate`, reads `settings_hash == EMPTY_SETTINGS_HASH` on both rows and the four new tables exist.

`tests/store/test_settings.py` (the `conn` fixture of `tests/store/conftest.py`):

```python
def test_write_read_and_hash(conn) -> None:
    p = write_settings(conn, {"required_return": 0.1, "refresh.workers": 4}, "try 10%", AT)
    assert read_overlay(conn) == {"required_return": 0.1, "refresh.workers": 4}
    assert p.required_return == 0.1 and p.refresh.workers == 4
    assert p.settings_hash == settings_hash({"required_return": 0.1})
    assert effective_policy(conn).settings_hash == p.settings_hash
    log = changes(conn)
    assert log[0].reason == "try 10%" and log[0].changes == [
        {"name": "required_return", "old": None, "new": 0.1}, {"name": "refresh.workers", "old": None, "new": 4}]


def test_write_is_all_or_none(conn) -> None:
    with pytest.raises(ValueError, match="terminal_growth: must be below required_return"):
        write_settings(conn, {"refresh.workers": 4, "terminal_growth": 0.5}, None, AT)
    assert read_overlay(conn) == {} and changes(conn) == []


def test_reset_names_or_all(conn) -> None:
    write_settings(conn, {"required_return": 0.1, "fade_years": 3}, None, AT)
    reset_settings(conn, ["fade_years"], AT)
    assert read_overlay(conn) == {"required_return": 0.1}
    reset_settings(conn, None, AT)
    assert read_overlay(conn) == {} and changes(conn)[0].changes == [{"name": "required_return", "old": 0.1, "new": None}]


def test_an_unknown_overlay_row_names_itself(conn) -> None:
    conn.execute("INSERT INTO settings VALUES ('gone_value', '1', ?)", (AT.isoformat(),)); conn.commit()
    with pytest.raises(ValueError, match="settings: gone_value: not a setting; reset it on the Settings page"):
        effective_policy(conn)
```

`tests/store/test_snapshots.py` and `test_refreshes.py`: a snapshot inserted from a result with `settings_hash="abc"` reads back `"abc"`; `create_refresh(..., settings_hash="abc")` reads back on `RefreshRow`.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/store -q`
Expected: FAIL: no table `settings`, no module `fairband.store.settings`, `create_refresh` arity.

- [ ] **Step 3: Implement**

The migration as spec 8.6 and 9.2 (both pairs of tables, the two `ALTER TABLE`s with the literal). `store/settings.py` as the interfaces say; `write_settings` opens one `transaction(conn)` after the check passes. `snapshots.py` and `refreshes.py` add the column to the `INSERT`, the row types and the readers. Update every caller of `create_refresh` in `src/` and `tests/` to pass `settings_hash` (`EMPTY_SETTINGS_HASH` in the tests that do not care; `grep -rn "create_refresh(" src tests`).

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/store tests/store tests
git commit -m "Add the settings overlay, the watchlist tables and the settings hash on snapshots and refreshes"
```

---

### Task 4: The refresh reads the effective policy and the price refresh honours the hash

**Files:**
- Modify: `src/fairband/refresh/run.py:196-225` (`run`: the record carries the hash; `run_price.py` gets the policy)
- Modify: `src/fairband/refresh/run_price.py:76-77, 252-260` (`POLICY_CHANGED`, new `SETTINGS_CHANGED`, the three-way check)
- Modify: `src/fairband/refresh/worker.py` (`start` closes the previous run's clients: `Refresh.close()`)
- Modify: `src/fairband/refresh/run.py` (`Refresh.__init__(..., close: Callable[[], None] | None = None)`, `Refresh.close()`; `run` with `fmp is None` and a kind other than `revalue` raises `ValueError("no FMP key: set fmp under [keys] in ~/.config/fairband/keys.toml ($XDG_CONFIG_HOME/fairband/keys.toml when set)")` before the record exists — reuse `MissingKey("fmp")`'s text)
- Modify: `src/fairband/__main__.py:90-125, 143-170` (`_serve`: the worker is always built; `make_refresh` reads the effective policy and builds the clients per run; `_refresh`: the effective policy at the start of the run)
- Modify: `docs/method.md` section 10 (the reprice sentence: spec 10)
- Test: `tests/refresh/test_run_price.py`, `tests/refresh/test_run_revalue.py`, `tests/refresh/test_run.py`, `tests/web/test_refresh_api.py`

**Interfaces:**
- Produces: `run_price.SETTINGS_CHANGED = "settings changed: run a revalue"`, `POLICY_CHANGED = "policy changed: run a revalue"`; the check order: policy version, then settings hash, then method version.
- Produces: `fairband.__main__.make_refresh(conn_factory, keys: Keys | None, tax: TaxTable, cancel, on_progress) -> Refresh` — module-level, used by `_serve`'s worker and testable: opens a connection, `policy = effective_policy(conn)`, builds the clients when `keys is not None and keys.fmp is not None` else `(None, None, ())`, returns `Refresh(..., close=<closes the clients>)`.
- Produces: `Refresh.close()`; `RefreshWorker.start` calls `self._run.refresh.close()` after `_wait_for` on the previous run.
- Consumes: `effective_policy`, `RefreshRow.settings_hash`, `create_refresh(..., settings_hash)` (Task 3).

- [ ] **Step 1: Write the failing tests**

`tests/refresh/test_run_price.py`: change the `POLICY_CHANGED` constant to the new text; add

```python
def test_price_refresh_refuses_another_settings_hash_and_reprices_the_empty_one(env_valued) -> None:
    # one snapshot rewritten with settings_hash "other" by raw UPDATE; a price refresh: that row's
    # refusal reads SETTINGS_CHANGED, every other row (hash = EMPTY_SETTINGS_HASH) reprices
```

`tests/refresh/test_run_revalue.py`: `test_revalue_runs_under_the_overlay` — `write_settings(conn, {"required_return": 0.1}, None, AT)`; a `Refresh` built with `effective_policy(conn)`; after `run("revalue")` every new snapshot's `settings_hash` equals the overlay's and the refresh row's; a Mature Growth value differs from before.

`tests/refresh/test_run.py`: `test_refresh_without_fmp_refuses_every_kind_but_revalue` — `Refresh(..., fmp=None, gf=None)`: `run("full")` raises `ValueError` matching `"no FMP key"` and creates no record; `run("revalue")` works.

`tests/web/test_refresh_api.py`: `test_make_refresh_reads_the_overlay_per_run` — `cli.make_refresh(conn_factory, None, tax, Event(), lambda p: None)` twice around a `write_settings`; the second `Refresh`'s policy (`refresh._policy.settings_hash`) differs from the first's. And `test_start_full_without_a_key_is_400_not_503`: the client built with a worker whose `make_refresh` gives `fmp=None`: `POST /api/refresh {"kind": "full"}` → 400 with `detail` starting `no FMP key`; `{"kind": "revalue"}` → 200.

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/refresh tests/web/test_refresh_api.py -q`
Expected: FAIL on the constants, `make_refresh`, and the 503.

- [ ] **Step 3: Implement**

`run.py`: `create_refresh(..., self._policy.settings_hash)`; the `fmp is None` guard at the top of `run`; `close`. `run_price.py`: the constants and the check. `worker.py`: after `self._wait_for(self._run)` in `start`, `self._run.refresh.close()`. `__main__.py`: `make_refresh` as the interface says; `_serve` builds `RefreshWorker(lambda cancel, on_progress: make_refresh(conn_factory, keys, tax, cancel, on_progress))` whether or not `keys.fmp` is set, logging the warning only; `create_app(settings, policy, conn_factory, worker)` keeps the file policy as the base; `_refresh` (the CLI) replaces `load_policy()` by `effective_policy(conn, load_policy())` read inside the `with closing(connect(...))` block after `migrate`. `app.py`: unchanged; `create_app(worker=None)` keeps its 503 for the tests that build no worker, and `_serve` now always passes one; a `ValueError` from `worker.start` is 400 as today.

`docs/method.md` 10: the last sentence of the price refresh bullet becomes: "A snapshot valued under another policy version is not repriced, "policy changed: run a revalue"; under other settings (its settings hash), "settings changed: run a revalue"; under another method version, "method changed: run a revalue". A revalue writes the current versions and hash."

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/refresh src/fairband/__main__.py src/fairband/web/app.py docs/method.md tests
git commit -m "Run every refresh under the effective policy, record its settings hash, reprice only under the same hash and version, and build the worker without an FMP key"
```

---

### Task 5: The web API: settings, policy, deciles, watchlists, and the two row keys

**Files:**
- Create: `src/fairband/store/watchlists.py`
- Create: `src/fairband/web/settings_api.py`, `src/fairband/web/watchlists_api.py`, `src/fairband/web/policy_rows.py`
- Modify: `src/fairband/web/app.py` (`create_app` reads the effective policy per request; registers the two route sets; `/api/policy`, `/api/deciles`; `screen_rows` passes the memberships)
- Modify: `src/fairband/web/rows.py` (`screen_row(..., watchlists: Sequence[int])`, `placeholder_row(..., watchlists)`, keys `watchlists` and `flagCount`, `EXTRA_KEYS`)
- Create: `tests/web/conftest.py` (the fixtures `policy`, `results`, `db_path`, `client_with_clock`, `client` and the helpers `_static_file`, `_component_file`, `HOST`, `NOW`, `HEADER = {"X-Fairband-Request": "1"}` moved out of `test_app.py`)
- Test: `tests/store/test_watchlists.py`, `tests/web/test_settings_api.py`, `tests/web/test_watchlists_api.py`, `tests/web/test_app.py`

**Interfaces:**
- Produces: `fairband.store.watchlists`: `EntryRow(symbol: str, added_at: datetime)`, `WatchlistRow(id: int, name: str, created_at: datetime, entries: tuple[EntryRow, ...])`; `create_watchlist(conn, name, at) -> int` (`ValueError("a watchlist named '<name>' exists")` on a case-insensitive clash; `ValueError("a name is 1 to 60 characters")`); `rename_watchlist(conn, id, name) -> None`; `delete_watchlist(conn, id) -> None` (deletes the entries in the same transaction); `add_symbol(conn, id, symbol, at) -> None` (idempotent; the symbol upper-cased and checked by `[A-Z0-9.-]{1,10}`); `remove_symbol(conn, id, symbol) -> None`; `set_memberships(conn, symbol, ids: Sequence[int], at) -> None`; `list_watchlists(conn) -> list[WatchlistRow]` by name, case-insensitive; `memberships(conn) -> dict[str, list[int]]`. A missing id raises `KeyError(id)`.
- Produces: `policy_rows.policy_json(policy: Policy, base: Policy, overlay: Mapping[str, Any]) -> dict` — `{"version", "settingsHash", "changed": <count>, "values": {name: {"value", "unit", "source", "setting", "changed"}}}` for every `Setting` plus the read-only values the page cites (`moat_wide_min`, `moat_narrow_min`, `peer_margin_min_years`, `z_distress`, `z_safe`, `f_score_low`, `implied_margin_bounds`) and the derived `designation_edges` and `wide_terminal_roic_cap` with `setting: false`; never the tables. `settings_json(policy, base, overlay, changed_at, valued_under) -> dict` as spec 8.7. `deciles_json(deciles: Deciles) -> dict` — `{"edges": [9 floats], "words": {"Very High": [9, 10], "High": [7, 8], "Moderate": [5, 6], "Low": [3, 4], "Close to zero or negative": [1, 2]}, "n": n_growth}`.
- Produces: the routes of spec 8.7 and 9.3, plus `GET /api/policy` and `GET /api/deciles` (404 `"no deciles yet"` before a full refresh). `valuedUnder` reads the latest snapshots' most common `(policy_version, settings_hash)` and the latest `full` refresh's `started_at`; `universeChanged` is true when any `universe.*` overlay row's `changed_at` is after that start.
- Produces: screen rows carry `watchlists: list[int]` and `flagCount: int` (`flag_count(result.flags)`; a placeholder has `0`); both in `EXTRA_KEYS` so they sort.
- Consumes: Tasks 1 to 4.

- [ ] **Step 1: Write the failing tests**

`tests/store/test_watchlists.py`: create, duplicate name ignoring case raises, rename, delete removes entries, add is idempotent and upper-cases, remove, `set_memberships` adds and removes in one call, `memberships()` maps symbols to sorted ids, a bad symbol raises `ValueError("'bad symbol' is not a symbol")`.

`tests/web/test_settings_api.py` (the `client` fixture of `test_app.py`, moved to `tests/web/conftest.py` with `db_path`, `policy`, `results`, `HOST`, `NOW`):

```python
def test_get_settings_shape(client) -> None:
    body = client.get("/api/settings").json()
    assert [g["name"] for g in body["groups"]] == ["valuation", "flags", "validity", "universe", "refresh"]
    r = next(s for s in body["groups"][0]["settings"] if s["name"] == "required_return")
    assert r == {"name": "required_return", "label": "Hurdle rate r", "description": r["description"], "unit": "fraction",
                 "default": 0.09, "value": 0.09, "range": "4% to 20%, above g_T", "effect": "revalue",
                 "source": "design.md 6.2 (stocks method v1.7 section 3): required return r = 9%", "changed": False, "changedAt": None}
    assert body["current"] == {"policyVersion": "fairband-policy-v6", "settingsHash": EMPTY_SETTINGS_HASH}
    assert body["valuedUnder"]["settingsHash"] == EMPTY_SETTINGS_HASH


def test_put_settings_all_or_none_and_the_notice(client) -> None:
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1, "terminal_growth": 0.5}}, headers=HEADER)
    assert r.status_code == 400 and r.json()["detail"] == "terminal_growth: must be below required_return"
    assert client.get("/api/settings").json()["current"]["settingsHash"] == EMPTY_SETTINGS_HASH
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1}, "reason": "try"}, headers=HEADER)
    assert r.status_code == 200 and r.json()["current"]["settingsHash"] != EMPTY_SETTINGS_HASH
    assert r.json()["valuedUnder"]["settingsHash"] == EMPTY_SETTINGS_HASH  # the snapshots are older


def test_reset(client) -> None: ...
def test_put_needs_the_request_header(client) -> None: ...  # 403
def test_policy_route_has_the_cited_values_and_no_table(client) -> None:
    body = client.get("/api/policy").json()
    assert body["values"]["required_return"] == {"value": 0.09, "unit": "fraction", "source": ..., "setting": True, "changed": False}
    assert body["values"]["designation_edges"]["value"] == [0.65, 0.85, 1.15, 1.5] and body["values"]["designation_edges"]["setting"] is False
    assert "base_rates" not in body["values"] and "synthetic_rating" not in body["values"]
    assert "key" not in json.dumps(body).lower()


def test_deciles_route(client) -> None: ...  # 404 before deciles; the nine edges after save_deciles
```

`tests/web/test_watchlists_api.py`: the six routes; `GET /api/screen` rows carry `watchlists` and `flagCount`; a symbol not in the universe stays in the list's `symbols`.

`tests/web/test_app.py`: `test_screen_sorts_by_flag_count` and `test_aging_fraction_from_the_overlay_changes_freshness` (write `aging_fraction` 0.1 into the overlay; a row that was `current` reads `aging`).

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/web tests/store -q`
Expected: FAIL: 404 on the new routes, `KeyError` on the new row keys.

- [ ] **Step 3: Implement**

`app.py`: a helper `def current(conn) -> Policy: return effective_policy(conn, policy)` used by `screen_rows` (`aging_fraction`), `groups` (`designation_edges`) and `company` (`designationEdges`); `add_settings_routes(app, conn_factory, policy, clock)` and `add_watchlist_routes(app, conn_factory, clock)` registered before `return app`. `settings_api.py` holds `SettingsPut(BaseModel)` with `changes: dict[str, Any]` and `reason: str | None`; a `ValueError` from `write_settings` is `HTTPException(400, str(exc))`. `watchlists_api.py`: `409` for a name clash, `404` for a missing id, `400` for a bad symbol. `rows.py`: the two keys.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fairband/store/watchlists.py src/fairband/web tests
git commit -m "Serve the settings, policy, deciles and watchlist routes, read the effective policy per request, and put the watchlists and the flag count on every screen row"
```

---

### Task 6: The header's five views and the hash routing

**Files:**
- Modify: `src/fairband/web/static/index.html` (three new `<section>` panels: `#watchlists`, `#methodology`, `#settings`, each `hidden`; the CSS for a scrolling panel as `#groups` has)
- Modify: `src/fairband/web/static/controls.js:267-280` (`views`), `show(tab)` (the three panels; the hash), the initial tab from `location.hash`
- Modify: `src/fairband/web/static/app.js:132-134` (`FairbandPage.show`, `FairbandPage.find(symbol)` sets the query and opens the Screen view)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Produces: `FairbandPage.show(tab: string)`, `FairbandPage.find(symbol: string)`, `FairbandPage.onShow` (an object the later views fill: `onShow[tab]` is called each time the tab opens), `FairbandPage.running()` (true while a refresh runs, set by `controls.js`); the panels' ids; the hash words `#watchlists`, `#methodology`, `#settings`, `#methodology/<section>`.
- Consumes: nothing new from the API.

- [ ] **Step 1: Write the failing pins**

```python
def test_header_has_the_five_views() -> None:
    js = _static_file("controls.js")
    assert ("views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' },\n"
            "        { id: 'watchlists', label: 'Watchlists' }, { id: 'methodology', label: 'Methodology' },\n"
            "        { id: 'settings', label: 'Settings' }]") in js
    assert "location.hash" in js and "history.replaceState" in js
    html = _static_file("index.html")
    for panel in ("watchlists", "methodology", "settings"):
        assert f'<section id="{panel}" hidden' in html
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/web/test_app.py -k five_views -v` — FAIL.

- [ ] **Step 3: Implement**

`show(tab)` hides and shows the five panels, writes `history.replaceState(null, '', tab === 'screen' ? location.pathname : '#' + tab)` (keep a methodology section suffix when given), and calls the view's loader (Task 7, 8, 9 register loaders through `FairbandPage.onShow[tab]`). On load, `show` the hash's view; `#methodology/<id>` scrolls to `document.getElementById(id)` after the fragment loads. At phone width the header's view row wraps: one CSS rule on `.fb-hdr` allowing `flex-wrap: wrap` under 600px, as a `// fairband:` patch in `bundle.css` with its comment.

- [ ] **Step 4: Run and commit**

Run: `uv run pytest tests/web -q` — PASS.

```bash
git add src/fairband/web/static tests/web/test_app.py
git commit -m "Give the header five views and open the view the URL hash names"
```

---

### Task 7: The screen: the watchlist mark, its popup, the two filters and the two columns

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (patches: `onWatch` and the mark cell; `watchlist` and `cleanOnly` in `EMPTY_FILTERS`, `summarise`, `clearAll`, the Filters menu; the `watchlists` and `flagCount` catalog columns; `watchlists` prop for the menu's names)
- Modify: `src/fairband/web/static/design-system/components/index.d.ts` (`ScreenRow.watched`, `ScreenRow.watchlists`, `ScreenRow.flagCount`, `ScreenFilters.watchlist`, `ScreenFilters.cleanOnly`, `ScreenTableProps.onWatch`, `ScreenTableProps.watchlists`)
- Modify: `src/fairband/web/static/design-system/components/bundle.css` (`.fb-watch`, `.fb-watch--on`)
- Modify: `src/fairband/web/static/app.js` (`narrow`, the `watched` row field, the popup state and render, `state.watchlists` loaded from `/api/watchlists`, `FairbandPage.watchlists` for Task 8)
- Modify: `src/fairband/web/rows.py` nothing (Task 5 gave the keys)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Produces: bundle: `ScreenTable` takes `onWatch(row)` and `watchlists: [{id, name}]`; a row's `watched: boolean` fills the mark; `EMPTY_FILTERS = { designation: [], phase: [], cap: [], sector: [], watchlist: [], reviewedOnly: false, hideExpired: false, cleanOnly: false }`; the chip words `<name>` or `<n> watchlists` and `Clean`; the menu sections `WATCHLISTS` (after SECTOR) and the `CLEAN` row (`No warning flag`, in the VALUE section); the catalog columns `{ key: 'watchlists', head: 'Watchlists' }` (names joined by ` · `, em dash for none) and `{ key: 'flagCount', head: 'Flags', num: true }` after `flags`.
- Produces: `app.js`: `FairbandPage.watchlists()` returns the loaded `[{id, name, symbols}]`; `FairbandPage.reloadWatchlists()`; `narrow` applies `within(filters.watchlist, …any of r.watchlists…)` and `cleanOnly → r.flagCount === 0`.
- Consumes: Task 5's routes and keys; Task 6's `FairbandPage.show`.

- [ ] **Step 1: Write the failing pins**

```python
def test_bundle_has_the_watch_mark_and_the_two_filters() -> None:
    bundle = _component_file("bundle.js")
    assert "// fairband: the watchlist mark (spec 2026-11-04 9.4)" in bundle
    assert "onClick: function (e) { e.stopPropagation(); p.onWatch(r); }" in bundle
    assert "'aria-pressed': r.watched ? 'true' : 'false'" in bundle
    assert "watchlist: [], reviewedOnly: false, hideExpired: false, cleanOnly: false" in bundle
    assert "'WATCHLISTS'" in bundle and "'No warning flag'" in bundle
    assert "{ key: 'flagCount', head: 'Flags', num: true" in bundle
    assert "{ key: 'watchlists', head: 'Watchlists'" in bundle
    dts = _component_file("index.d.ts")
    assert "onWatch?: (row: ScreenRow) => void;" in dts and "cleanOnly: boolean;" in dts


def test_app_js_narrows_on_watchlist_and_clean() -> None:
    js = _static_file("app.js")
    assert "(!filters.cleanOnly || r.flagCount === 0)" in js
    assert "'/api/watchlists/memberships/' + encodeURIComponent(symbol)" in js
```

Raise the `>= 43` in `test_bundle_patches_marked` to the new count.

- [ ] **Step 2: Run to see them fail** — `uv run pytest tests/web/test_app.py -k "watch or clean" -v`: FAIL.

- [ ] **Step 3: Implement**

The mark: a `<button type="button" class="fb-watch control">` as the first child of the Ticker cell, text `▶` when `r.watched` else `▸`, `aria-label: 'Watchlists for ' + r.ticker`, `aria-pressed`, and `onKeyDown` that stops Enter and Space from opening the row; rendered only when `p.onWatch` is given. CSS: 24px square, `color: var(--ink-faint)`; `.fb-watch--on { color: var(--accent); }`; the focus ring as the buttons have.

The popup in `app.js`: `state.watch = { symbol, anchor }` while open; rendered under the mark in the bundle's `fb-menu` style (as controls.js's Details ▾ draws it with `menuSection`), one `checkRow`-style label per watchlist (checked when the row's `watchlists` holds the id), then a text field with placeholder `New watchlist` and an `Add` button (`F.Button`, secondary, sm) that `POST /api/watchlists` then `PUT /api/watchlists/memberships/<symbol>` with the ids plus the new one; a checkbox change writes the memberships at once and reloads the rows (`P.reload()`) and the lists; Escape or an outside pointerdown or focusin closes it (the same three listeners controls.js uses for Details ▾). Chips: `summarise` adds the watchlist group (names from `p.watchlists`) and `cleanOnly`.

- [ ] **Step 4: Run and commit** — `uv run pytest tests/web -q`: PASS.

```bash
git add src/fairband/web/static tests/web/test_app.py
git commit -m "Put the watchlist mark and its popup on the screen's rows, with the watchlist and clean filters and the two columns"
```

---

### Task 8: The Watchlists view

**Files:**
- Create: `src/fairband/web/static/watchlists.js` (loaded after `controls.js`)
- Modify: `src/fairband/web/static/index.html` (the script tag; the CSS of the lists' sections, the name field, the add field's match list)
- Modify: `src/fairband/web/static/app.js` (`FairbandPage.rows()` returns the loaded screen rows; `FairbandPage.openRow(symbol)` opens the drawer; `FairbandPage.columns()` returns the chooser's current columns)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: Task 7's `FairbandPage.watchlists()`, `reloadWatchlists()`, the popup through `onWatch`; Task 5's routes.
- Produces: the view of spec 9.6, registered as `FairbandPage.onShow.watchlists`.

- [ ] **Step 1: Write the failing pins**

```python
def test_watchlists_view_creates_renames_deletes_and_adds() -> None:
    js = _static_file("watchlists.js")
    assert "'No watchlists yet. Create one here, or press the mark beside a ticker on the screen.'" in js
    assert "P.api.post('/api/watchlists', { name: name })" in js
    assert "method: 'PATCH'" in js and "method: 'DELETE'" in js
    assert "h(F.ConfirmDialog, {" in js  # Delete confirms with the name and the count
    assert "chooser: false, dense: true" in js  # each list is a ScreenTable of the screen's rows
    assert "placeholder: 'Add a company'" in js and ".slice(0, 8)" in js
    html = _static_file("index.html")
    assert '<script src="/static/watchlists.js"></script>' in html
```

`FairbandPage.api` gains `patch` and `del` (same shape as `post`), pinned.

- [ ] **Step 2: Run to see it fail.** `uv run pytest tests/web/test_app.py -k watchlists_view -v`: FAIL.

- [ ] **Step 3: Implement**

As spec 9.6. The rows of a list: `P.rows()` filtered to the list's symbols, in the list's order, each with `watched: true`; a symbol with no row becomes `{ ticker: symbol, name: null, price: null, mechanical: null, reviewed: null, phase: null, fairLow: null, fairHigh: null, watched: true }`. The match list under "Add a company": the first eight rows whose ticker starts with the text or whose name contains it, drawn as buttons; Enter on a text that matches no row adds it as typed when `/^[A-Za-z0-9.-]{1,10}$/` passes. `Rename` swaps the title for a text field (Enter saves through `PATCH`, Escape cancels). `Delete` opens `F.ConfirmDialog` with `title: 'Delete ' + name`, `payload: { name: name, companies: count }`, `targetRevision: id`, `state: 'open'`, and deletes on `onConfirm`. After every write: `P.reloadWatchlists()` then re-render; the screen's marks follow through `P.reload()`.

- [ ] **Step 4: Run and commit** — `uv run pytest tests/web -q`: PASS.

```bash
git add src/fairband/web/static tests/web/test_app.py
git commit -m "Add the Watchlists view: create, rename and delete a list, and add and remove its companies"
```

---

### Task 9: The Settings view

**Files:**
- Create: `src/fairband/web/static/settings.js`
- Modify: `src/fairband/web/static/index.html` (the script tag; the CSS of the form rows, the fields in the control style on `surface-sunken`, the `changed` word in `accent`, the notice line)
- Test: `tests/web/test_app.py`

**Interfaces:**
- Consumes: `GET/PUT /api/settings`, `POST /api/settings/reset`, `POST /api/refresh` (Task 5, Task 4); `FairbandPage.api`, `FairbandPage.onShow`.
- Produces: the view of spec 8.5, registered as `FairbandPage.onShow.settings`.

- [ ] **Step 1: Write the failing pins**

```python
def test_settings_view_form_and_notices() -> None:
    js = _static_file("settings.js")
    assert "'Your settings changed since the last valuation.'" in js
    assert "'Revalue now'" in js and "P.api.post('/api/refresh', { kind: 'revalue' }" in js
    assert "'A universe setting changed since the last full refresh: run Refresh all.'" in js
    assert "'takes effect at the next revalue'" in js and "'takes effect at once'" in js
    assert "h(F.ConfirmDialog, {" in js and "payload: payload" in js
    assert "'Reset'" in js and "'Save'" in js and "placeholder: 'Reason (optional)'" in js
    assert "UNITS = { fraction: '%', points: ' points', years: ' years', times: '×', days: ' days', seconds: ' s', hours: ' h', count: '', usd: '$' }" in js
```

- [ ] **Step 2: Run to see it fail.** FAIL.

- [ ] **Step 3: Implement**

As spec 8.5. State: `{ body, draft: {name: value}, error: {name: sentence}, confirm: payload | null, saving }`. A field shows `draft[name]` when present else `value`; a fraction field shows the percentage with one decimal and parses back to a fraction; `points` shows `4` for `0.04`; the by-moat and pair settings are two or three fields on one row; the symbol lists one comma-separated field; the exchanges three checkboxes; the cap bands three dollar fields in billions. `Reset` beside a changed field puts the default in the draft. `Save` builds `payload = [{ name, from, to }]` for every draft value that differs from `value`, and opens `F.ConfirmDialog` (`title: 'Change ' + n + ' setting' + (n === 1 ? '' : 's')`, `payload`, `state: saving ? 'confirming' : 'open'`). `onConfirm` sends `PUT` with `{ changes, reason }`; a 400's `detail` `"<name>: <rule>"` lands in `error[name]` and the dialog closes; a 200 replaces `body` and clears the draft. The three notices from `body.current` and `body.valuedUnder`: hashes differ → the sentence and the `Revalue now` button (primary; disabled while `state.running` in controls.js is set, read through `P.running()`); `valuedUnder.universeChanged` → the second sentence; else nothing.

- [ ] **Step 4: Run and commit** — `uv run pytest tests/web -q`: PASS.

```bash
git add src/fairband/web/static tests/web/test_app.py
git commit -m "Add the Settings view over the overlay, with the confirm, the ranges' sentences and the revalue notice"
```

---

### Task 10: The Methodology view: the fragment, the diagram, the live values and the examples

This task runs the live revalue under 0.8 first, so the examples' figures come from it.

**Files:**
- Create: `src/fairband/web/static/methodology.html`, `src/fairband/web/static/methodology.js`
- Modify: `src/fairband/web/static/index.html` (the script tag; the prose CSS: `.app-prose` with a 70-character measure, headings in `title`, body in `body`, tables in `fb-table`)
- Modify: `src/fairband/web/static/app.js` (the drawer's phase section gains the link `How Fairband values a <phase> company` to `#methodology/<section-id>`)
- Modify: `CLAUDE.md` ("Read first", the method entry gains the page's sentence), `README.md` (one line naming the five views)
- Test: `tests/web/test_methodology.py`

**Interfaces:**
- Consumes: `GET /api/policy`, `GET /api/deciles`, `GET /api/groups?by=phase`, `GET /api/screen` (the total) (Task 5); `FairbandPage.show`, `FairbandPage.find` (Task 6).
- Produces: the twelve sections with ids `what`, `life-cycle`, `classifier`, `value`, `mature-growth`, `mature-stable`, `growth`, `decline`, `start-up`, `flags`, `sources`, `settings`; the route-to-section map `{ 'mature-growth': 'mature-growth', 'mature-stable': 'mature-stable', 'revenue-growth': 'growth', 'decline': 'decline', 'start-up': 'start-up' }` in `methodology.js` as `FairbandPage.methodologySection(route)`.

- [ ] **Step 1: The live revalue**

Run, in order:

```bash
cp ~/.local/share/fairband/fairband.db ~/.local/share/fairband/fairband-before-v6-$(date +%F).db
uv run python -m fairband refresh --kind revalue
```

Expected: `refresh <n>: done` and the calibration lines; the six example symbols (MSFT, KO, CRWD, ROKU, MMM, RVMD) keep the phases of spec 7.5 (check with `uv run python -m fairband serve` and the screen, or a query on `snapshots`); if one moved, take its alternate. Note the refresh's finish date for the "Figures as of" line.

- [ ] **Step 2: Write the failing content tests**

`tests/web/test_methodology.py`:

```python
SECTIONS = ["what", "life-cycle", "classifier", "value", "mature-growth", "mature-stable", "growth",
            "decline", "start-up", "flags", "sources", "settings"]


def test_fragment_sections_diagram_and_examples() -> None:
    html = _static_file("methodology.html")
    for section in SECTIONS:
        assert f'<section id="{section}"' in html
    assert "<svg" in html and 'role="img"' in html and "<title" in html and "<desc" in html
    assert html.count("var(--phase-") >= 6 and "url(" not in html and "<img" not in html
    assert "Figures as of" in html
    for symbol in ("MSFT", "KO", "CRWD", "ROKU", "MMM", "RVMD"):
        assert f"data-find=\"{symbol}\"" in html


def test_every_data_policy_name_is_served(client) -> None:
    html = _static_file("methodology.html")
    names = set(re.findall(r'data-policy="([a-z_]+)', html))
    served = client.get("/api/policy").json()["values"]
    assert names and names <= set(served)
    counts = set(re.findall(r'data-count="([^"]+)"', html))
    assert counts == {"Start-up", "Young Growth", "High Growth", "Mature Growth", "Mature Stable", "Decline", "unclassified", "universe"}


def test_sources_have_links() -> None:
    html = _static_file("methodology.html")
    sources = html.split('<section id="sources"')[1].split("</section>")[0]
    assert sources.count('href="https://') >= 8 and "Base Rate Book" in sources and "pages.stern.nyu.edu" in sources


def test_prose_sentences_are_short() -> None:
    # strip tags from the fragment's <p> text; every sentence (split on ". ") has at most 25 words
    # except inside <table> and <code>; the test lists any that fail


def test_drawer_links_to_the_route_section() -> None:
    js = _static_file("app.js")
    assert "'How Fairband values a ' + " in js and "'#methodology/' + P.methodologySection(" in js
```

- [ ] **Step 3: Run to see them fail.** FAIL: no fragment.

- [ ] **Step 4: Write the fragment**

Spec 7.2 to 7.6, every section, in the output style's prose rules. The diagram as spec 7.3: `viewBox="0 0 960 320"`, six `<rect>` bands at `fill="var(--phase-n)" fill-opacity="0.18"`, the revenue `<path>` in `var(--chart-1)` and the earnings `<path>` in `var(--ink-muted)`, a zero line in `var(--chart-grid)`, the names in `class="caption"` at `y="300"`, the counts as `<text data-count="<phase>" class="figure-sm">` at `y="316"`. The examples: one `<table class="fb-table">` per route with the figures from the drawer of the revalued snapshot, then the sentences; under each, `<a href="#" data-find="MSFT">Open today's row</a>`. Every live number is a `<span data-policy="…">—</span>` with the unit handled by the script; the decile edges `<span data-decile="n">`.

- [ ] **Step 5: Write the script**

`methodology.js`: on the view's first show, `fetch('/static/methodology.html')` then `panel.innerHTML = text`; then the three `getJson`s fill the spans by unit (`fraction` → one-decimal percentage; `points` → `n points`; `years`, `days` → `n years`; `times` → `n×`; `usd` → `F.formatMoney`; `count` → `toLocaleString`); the counts from `/api/groups?by=phase` (the `count` of each group; `unclassified` from the group named `none`, else 0) and `universe` from the screen's `rows.length`; the deciles from `/api/deciles`; each `data-find` link calls `P.find(symbol)`; the table of contents links call `show('methodology')` and scroll. `FairbandPage.methodologySection(route)`.

- [ ] **Step 6: Documents**

`CLAUDE.md`, the method entry: add "The Methodology page (`src/fairband/web/static/methodology.html`) changes in the same commit, and a change of method version re-reads its examples' figures." `README.md`: one sentence after Run: "The page has five views: Screen, Groups, Watchlists, Methodology and Settings."

- [ ] **Step 7: Run and commit** — `uv run pytest tests/web -q`: PASS.

```bash
git add src/fairband/web/static tests/web/test_methodology.py CLAUDE.md README.md
git commit -m "Add the Methodology view with the life-cycle diagram, the live policy values and one worked example per route"
```

---

### Task 11: The backlog, the final checks and the hand check

**Files:**
- Modify: `docs/backlog.md` (B-73, B-2, B-67, B-69, B-24, B-45 to Done with the commits; B-1 stays at the top of Now)
- Modify: `docs/superpowers/specs/2026-11-04-methodology-settings-watchlists-design.md` (status: built; the decision log's build rulings)

- [ ] **Step 1: The checks**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
Expected: all pass.

- [ ] **Step 2: The hand check against spec 13**

Start `uv run python -m fairband serve`; walk the acceptance list of spec 13 in the browser: the five views and `#methodology/decline`; the diagram's counts; a change of r to 10% through the confirm, the notice, `Revalue now`, the price refresh after it; r at 2% refused beside the field; the mark on MSFT, a `Quality` list, the filter, the Watchlists view, unchecking there; `Flags` sorting and `Clean`. Record each line's outcome in the spec's decision log, with any ruling made on the way.

- [ ] **Step 3: Move the items and commit**

```bash
git add docs/backlog.md docs/superpowers/specs/2026-11-04-methodology-settings-watchlists-design.md
git commit -m "Close the Methodology page, settings, watchlists and flag-count items in the backlog and record the build's rulings"
```
