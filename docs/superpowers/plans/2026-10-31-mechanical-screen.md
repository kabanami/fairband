# Mechanical Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One local page with one row per U.S.-listed company above $2 bn, each row carrying the engine's value, levels, price and stance from the Mature Growth and Mature Stable routes, with a refresh that runs on request and continues after a stop.

**Architecture:** A pure-Python engine (`fairband.engine`) that turns a `CompanyInputs` record into a `ValuationResult`, with no I/O. A SQLite store (`fairband.store`) that keeps every vendor response, the normalized facts, and one snapshot per company per refresh. Vendor adapters (`fairband.vendors`) behind one HTTP client that scrubs keys. A refresh orchestrator (`fairband.refresh`) that fetches, assembles inputs, classifies and values. A FastAPI server (`fairband.web`) that serves the design system's React bundle and a JSON API.

**Tech Stack:** Python 3.13, uv, FastAPI, Uvicorn, httpx, sqlite3 (stdlib), tomllib (stdlib), pytest, Ruff, mypy. No Node toolchain. React 18 and the design-system bundle are vendored static files.

**Spec:** `docs/superpowers/specs/2026-10-31-mechanical-screen-design.md`. Method sources: `docs/legacy/design.md` (sections 5, 6.2–6.6, 6.11, 6.13, 8), `docs/legacy/research.md` (D2, D3, D3a, D3b, D6, D9, D17). Reference only: `/mnt/c/users/kaban/documents/workspace/stocks/docs/valuation-method.md` and `docs/mechanical-valuation.md`.

## Global Constraints

- Python `>=3.13`; dependencies locked in `uv.lock`; `uv run` for every command.
- Package root `src/fairband/`; tests under `tests/` mirroring the package; fixtures under `tests/fixtures/` are synthetic or hand-trimmed, never bulk vendor data, never a real key.
- No key in a URL that is logged or stored, in a log line, in the database, in an error message or in a fixture. FMP sends `apikey` as a query parameter; GuruFocus puts the token in the URL path. Both are scrubbed to `<key>` before any string leaves `fairband.vendors.http`.
- Vendor numbers are parsed to `Decimal` and stored as decimal text with unit and currency. The engine computes in `float`. Display rounds; storage does not.
- Every refusal is a `ValuationResult` with `value=None` and a `refusal` string; never an exception that drops a row.
- Policy numbers come from `src/fairband/policy/fairband-policy-v1.toml`; code holds no valuation constant.
- Method version string: `fairband-mechanical/0.1` (`fairband.engine.METHOD_VERSION`).
- Server binds `127.0.0.1` only; default port 8470.
- Data directory: `$XDG_DATA_HOME/fairband` else `~/.local/share/fairband`; config: `$XDG_CONFIG_HOME/fairband` else `~/.config/fairband`; keys file `keys.toml` with `[keys] fmp = "..." gurufocus = "..."`; env vars `FAIRBAND_FMP_KEY`, `FAIRBAND_GURUFOCUS_KEY` override; `FAIRBAND_DATA_DIR` overrides the data directory.
- Dates: ISO `YYYY-MM-DD` strings in JSON; timestamps UTC RFC 3339.
- Commit messages: a plain sentence in the imperative, like the first commit; every commit ends with the line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Ruff and mypy pass before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src`.

## Review Focus

Inputs the spec implies but no acceptance number covers. Each has its test in the task named.

1. **Quarterly estimates arrive out of order and far into the future** (MSFT needs `limit=40`); the NTM window must be picked by period after the last reported quarter, never the first four rows. Test in Task 9 (`test_ntm_quarters_picks_by_period_not_order`).
2. **A fiscal-year change leaves a gap in the last four quarters**; the trailing sum must fall back to the fiscal year and flag it, not sum across the gap. Test in Task 18 (`test_trailing_falls_back_when_quarters_not_consecutive`).
3. **GuruFocus returns numbers as strings, `"-"` and nulls**; the parser must return `None`, not crash or read `"-"` as zero. Test in Task 16 (`test_summary_string_numbers_and_dashes`).
4. **A missing or zero diluted share count** must refuse the company ("no diluted share count"), never divide by zero. Test in Task 11 (`test_refuses_without_shares`).
5. **A price history shorter than five years or with holiday gaps** must give `None` for the changes it cannot compute and still produce the 52-week range. Test in Task 10 (`test_price_facts_short_history`).

---

## File structure

```
pyproject.toml, uv.lock, .python-version, .gitignore, CLAUDE.md, README.md
.github/workflows/ci.yml
src/fairband/
  __init__.py            version string
  __main__.py            argparse: serve | refresh | migrate
  config.py              Settings, load_keys
  policy/
    __init__.py          load_policy, Policy dataclasses
    tax.py               TaxTable, TaxRate
    fairband-policy-v1.toml
    tax-rates-oecd-v1.toml
  engine/
    __init__.py          METHOD_VERSION
    types.py             TaggedInput, Flag, Levels, PhaseEvidence, ValuationResult, JSON round trip
    levels.py            levels_for, stance5, stance3, validity_state
    classifier.py        FiscalYear, Series, Deciles, slope, decile, compute_deciles, classify, dickinson
    roic.py              CapitalYear, invested_capital, nopat, aggregate_roic, terminal_roic
    mature_growth.py     GrowthPath, Charge, terminal_multiple, value_at_belief, implied_growth
    mature_stable.py     mature_stable_values
    anchor.py            estimates types, ntm_quarters, sbc_basis, ntm_anchor, base_fiscal_year, path_steps, belief_from_sales, moat_class
    flags.py             margin_flag, gate_flags, nri_flag, long_runway_flag, value_spread_flag
    returns.py           expected_return
    multiples.py         multiples, epv, growth_share
    price_facts.py       price_facts
    route.py             CompanyInputs, value_company, reprice
  store/
    db.py                connect, migrate
    migrations/001_initial.sql
    companies.py, vendor.py, facts.py, observations.py, snapshots.py, refreshes.py, policy.py
  vendors/
    scrub.py, http.py, fmp.py, normalize_fmp.py, gurufocus.py, normalize_gf.py
  refresh/
    fetch.py, inputs.py, universe.py, deciles.py, run.py, worker.py
  web/
    app.py
    static/index.html, static/app.js
    static/design-system/{tokens,fonts,components}/   unpacked from docs/design-system archive
    static/vendor/react.production.min.js, react-dom.production.min.js
tests/  (mirrors src; tests/fixtures/*.json)
```

---

### Task 1: Project skeleton, toolchain, CI, CLAUDE.md

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore` (modify), `src/fairband/__init__.py`, `src/fairband/__main__.py`, `.github/workflows/ci.yml`, `CLAUDE.md`, `README.md`, `tests/test_package.py`

**Interfaces:**
- Produces: `fairband.__version__ == "0.1.0"`; `python -m fairband --version` prints it; `python -m fairband serve|refresh|migrate` subcommands registered (bodies raise `NotImplementedError` until Tasks 12, 19, 20).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_package.py
import subprocess, sys
import fairband

def test_version():
    assert fairband.__version__ == "0.1.0"

def test_cli_version():
    out = subprocess.run([sys.executable, "-m", "fairband", "--version"], capture_output=True, text=True)
    assert out.returncode == 0 and "0.1.0" in out.stdout
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_package.py -v`
Expected: FAIL (no package / no pyproject).

- [ ] **Step 3: Create the toolchain**

`pyproject.toml`: project `fairband`, version `0.1.0`, `requires-python = ">=3.13"`, dependencies `fastapi`, `uvicorn[standard]`, `httpx`; dev group `pytest`, `ruff`, `mypy`; build backend `hatchling` with `packages = ["src/fairband"]`; `[tool.ruff] line-length = 100`, `[tool.mypy] strict = true, python_version = "3.13"`, `[tool.pytest.ini_options] testpaths = ["tests"]`. `.python-version`: `3.13`. Run `uv lock`. Add to `.gitignore`: `.venv/`, `__pycache__/`, `*.db`, `data/`, `keys.toml`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`.

`src/fairband/__main__.py`: `main(argv: list[str] | None = None) -> int` with argparse; `--version`; subparsers `serve` (`--port`, default 8470), `refresh` (`symbols`, comma-separated; `--kind` in `full|price|scoped`, default `scoped` when symbols given, `full` otherwise), `migrate`.

`.github/workflows/ci.yml`: on push and pull request; `astral-sh/setup-uv`; `uv sync`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run mypy src`; `uv run pytest -q`.

`CLAUDE.md`: under 60 lines. Points to `docs/legacy/design.md` as the method source, the spec and this plan, and the design system's `docs/brand-book.md` inside the archive. States: never print, log, store or commit a key; never commit vendor data; keys live in `~/.config/fairband/keys.toml`; data in `~/.local/share/fairband`; run checks with `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`; commit style as in Global Constraints.

`README.md`: ten lines: what Fairband is, how to install (`uv sync`), where keys go, `uv run python -m fairband serve`.

- [ ] **Step 4: Run tests, lint and types**

Run: `uv run pytest -q && uv run ruff check . && uv run mypy src`
Expected: 2 passed; no lint or type errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock .python-version .gitignore src tests .github CLAUDE.md README.md
git commit -m "Add the package skeleton, the toolchain and the CI workflow"
```

---

### Task 2: Settings and key loading

**Files:**
- Create: `src/fairband/config.py`, `tests/test_config.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Settings: data_dir: Path; config_dir: Path; db_path: Path; port: int`
  - `def load_settings(env: Mapping[str, str] | None = None, home: Path | None = None) -> Settings`
  - `@dataclass(frozen=True) class Keys: fmp: str | None; gurufocus: str | None`
  - `def load_keys(settings: Settings, env: Mapping[str, str] | None = None) -> Keys` — reads `config_dir / "keys.toml"` if present, env vars override; a key is `None` when absent, never `""`.
  - `class MissingKey(Exception)` with `.vendor: str`; `def require(keys: Keys, vendor: Literal["fmp", "gurufocus"]) -> str` raises it.
  - `def utcnow() -> datetime` — timezone-aware UTC now; every module takes a `clock` that defaults to it.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
def test_xdg_defaults(tmp_path):
    s = load_settings(env={}, home=tmp_path)
    assert s.data_dir == tmp_path / ".local/share/fairband"
    assert s.config_dir == tmp_path / ".config/fairband"
    assert s.db_path == s.data_dir / "fairband.db" and s.port == 8470

def test_env_overrides(tmp_path):
    s = load_settings(env={"XDG_DATA_HOME": str(tmp_path / "d"), "FAIRBAND_DATA_DIR": str(tmp_path / "x")}, home=tmp_path)
    assert s.data_dir == tmp_path / "x"

def test_keys_file_then_env(tmp_path):
    (tmp_path / ".config/fairband").mkdir(parents=True)
    (tmp_path / ".config/fairband/keys.toml").write_text('[keys]\nfmp = "file-fmp"\n')
    s = load_settings(env={}, home=tmp_path)
    assert load_keys(s, env={}) == Keys(fmp="file-fmp", gurufocus=None)
    assert load_keys(s, env={"FAIRBAND_FMP_KEY": "env-fmp"}).fmp == "env-fmp"

def test_require_raises():
    with pytest.raises(MissingKey) as e:
        require(Keys(fmp=None, gurufocus=None), "gurufocus")
    assert e.value.vendor == "gurufocus"
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_config.py -v` → ImportError.
- [ ] **Step 3: Implement `config.py`** with the signatures above. `tomllib` for the file. The `MissingKey` message names the file path and the env var, never a value.
- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/test_config.py -v` → 4 passed.
- [ ] **Step 5: Commit** — `git add src/fairband/config.py tests/test_config.py && git commit -m "Add settings and key loading"`

---

### Task 3: The policy file and its loader

**Files:**
- Create: `src/fairband/policy/__init__.py`, `src/fairband/policy/fairband-policy-v1.toml`, `src/fairband/policy/tax.py`, `src/fairband/policy/tax-rates-oecd-v1.toml`, `tests/policy/test_policy.py`, `tests/policy/test_tax.py`

**Interfaces:**
- Produces (`fairband.policy`):
  - `Moat = Literal["Wide", "Narrow", "None"]`
  - `@dataclass(frozen=True) class BaseRateClass: upper_musd: float; median: float; label: str`
  - `@dataclass(frozen=True) class Policy:` fields `version: str; hash: str; required_return: float; terminal_growth: float; runway_years: dict[Moat, int]; margin_of_safety: dict[Moat, float]; fair_band: tuple[float, float]; trim_multiple: float; wide_terminal_roic_cap: float; moat_wide_min: float; moat_narrow_min: float; base_rates: tuple[BaseRateClass, ...]; inflation_addition: float; roic_sensitivity: tuple[float, float]; analyst_min: int; nri_flag_share: float; value_spread_flag: float; long_runway_growth_flag: float; margin_flag_ratio: float; margin_flag_above_high: float; margin_flag_min_years: int; capex_ocf_flag: float; equity_raise_share: float; sbc_detect: float; forward_pe_unit_error: float; validity_fallback_days: int; aging_fraction: float; universe: UniversePolicy; refresh: RefreshPolicy; raw: dict[str, Any]`
  - `@dataclass(frozen=True) class UniversePolicy: exchanges: tuple[str, ...]; cap_floor_usd: float; cap_bands: tuple[tuple[float, str], ...]; excluded_industries: tuple[str, ...]; symbol_exclude_patterns: tuple[str, ...]; manual_exclusions: tuple[str, ...]`
  - `@dataclass(frozen=True) class RefreshPolicy: reuse_hours: int; gf_reuse_days: int; workers: int; connect_timeout_s: float; read_timeout_s: float; deadline_s: float; attempts: int; backoff_s: tuple[float, ...]`
  - `def load_policy(path: Path | None = None) -> Policy` (default: the packaged v1 file via `importlib.resources`); `hash` = sha256 hex of the file bytes.
- Produces (`fairband.policy.tax`):
  - `@dataclass(frozen=True) class TaxRate: rate: float; year_used: int; estimate: bool; method: str | None; source: str`
  - `class TaxTable` with `def rate_for(self, country: str, year: int) -> TaxRate | None` — exact year → `estimate=False`; year later than the newest year for that country → newest year's rate with `estimate=True, method="tax-rate-latest-oecd-year-v1"`; earlier missing year or unknown country → `None`.
  - `def load_tax_table(path: Path | None = None) -> TaxTable`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/policy/test_policy.py
def test_values_match_design():
    p = load_policy()
    assert p.version == "fairband-policy-v1" and len(p.hash) == 64
    assert p.required_return == 0.09 and p.terminal_growth == 0.03
    assert p.runway_years == {"None": 5, "Narrow": 10, "Wide": 20}
    assert p.margin_of_safety == {"None": 0.45, "Narrow": 0.35, "Wide": 0.25}
    assert p.fair_band == (0.85, 1.15) and p.trim_multiple == 1.5
    assert p.wide_terminal_roic_cap == 0.13
    assert p.moat_wide_min == 8 and p.moat_narrow_min == 4
    assert len(p.base_rates) == 11
    assert p.base_rates[0] == BaseRateClass(325, 0.085, "$0-325 Mn")
    assert p.base_rates[-1].median == 0.033 and p.inflation_addition == 0.02
    assert p.analyst_min == 5 and p.universe.cap_floor_usd == 2_000_000_000
    assert p.refresh.reuse_hours == 24 and p.refresh.gf_reuse_days == 7 and p.refresh.workers == 4

def test_every_value_has_a_source_line():
    raw = load_policy().raw
    for section, values in raw["values"].items():
        assert "source" in values, section

# tests/policy/test_tax.py
def test_exact_year():
    t = load_tax_table()
    r = t.rate_for("United States", 2022)
    assert r is not None and r.estimate is False and r.year_used == 2022 and 0.2 < r.rate < 0.3

def test_later_year_carried_forward():
    t = load_tax_table()
    newest = max(y for (c, y) in t.years() if c == "United States")
    r = t.rate_for("United States", newest + 1)
    assert r is not None and r.estimate is True and r.year_used == newest and r.method == "tax-rate-latest-oecd-year-v1"

def test_missing_earlier_year_and_unknown_country():
    t = load_tax_table()
    assert t.rate_for("United States", 1990) is None
    assert t.rate_for("Atlantis", 2022) is None
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/policy -v` → ImportError.

- [ ] **Step 3: Write the policy file and the loader**

`fairband-policy-v1.toml`: a `[meta]` table with `version = "fairband-policy-v1"`; a `[values.<name>]` table per value with `value` and `source` keys (the source line is the `design.md` section, the `mech/1.2` rule, the founder decision, or the words `no source: policy value`). Values and sources, from the spec:

| name | value | source |
|---|---|---|
| required_return | 0.09 | design 6.2 |
| terminal_growth | 0.03 | design 6.2 |
| runway_years | None 5, Narrow 10, Wide 20 | design 6.2 |
| margin_of_safety | None 0.45, Narrow 0.35, Wide 0.25 | design 6.2 |
| fair_band | 0.85, 1.15 | design 6.2 |
| trim_multiple | 1.5 | design 6.2 |
| wide_terminal_roic_cap | 0.13 | design 6.6 |
| moat_wide_min, moat_narrow_min | 8, 4 | mech/1.2 |
| base_rates | the eleven rows of `BASE_RATES` in stocks `gfclient/mechanical.py` lines 81–93 (upper bound USD millions, median, label); attribution: Mauboussin, Callahan, Majd, *The Base Rate Book*, 2016, Earnings Growth Exhibit 4, pp. 72–73; note that the classes are in 2015 dollars and Fairband reads current-dollar trailing revenue (D6) | D6; mech/1.2 |
| inflation_addition | 0.02 | mech/1.2 |
| roic_sensitivity | 0.15, 0.09 (the third value is the company's aggregate) | no source: policy value |
| analyst_min | 5 | method v1.7 section 3 |
| nri_flag_share | 0.05 | spec 6.7 |
| value_spread_flag | 0.30 | no source: policy value |
| long_runway_growth_flag | 0.10 | design 6.5 change 3 |
| margin_flag_ratio, margin_flag_above_high, margin_flag_min_years | 1.5, 0.10, 6 | mech/1.2 |
| capex_ocf_flag, equity_raise_share | 0.5, 0.01 | method v1.7 Step 0 |
| sbc_detect | 0.5 | mech/1.2 |
| forward_pe_unit_error | 2.0 | mech/1.2 (I290) |
| validity_fallback_days | 91 | design 8 ("3 months") |
| aging_fraction | 0.6667 | design system, values-and-provenance |
| universe | exchanges NYSE, NASDAQ, AMEX; cap_floor_usd 2e9; cap_bands [[2e11,"Mega"],[1e10,"Large"],[2e9,"Mid"]]; excluded_industries: the FMP industry strings beginning `Banks`, `Insurance`, `REIT` (list them in full after checking the screener's industry vocabulary; start with `Banks - Diversified`, `Banks - Regional`, `Insurance - Diversified`, `Insurance - Life`, `Insurance - Property & Casualty`, `Insurance - Reinsurance`, `Insurance - Specialty`, `Insurance Brokers`, `REIT - Diversified`, `REIT - Healthcare Facilities`, `REIT - Hotel & Motel`, `REIT - Industrial`, `REIT - Mortgage`, `REIT - Office`, `REIT - Residential`, `REIT - Retail`, `REIT - Specialty`); symbol_exclude_patterns (regex): `-P[A-Z]?$`, `-W[ST]?$`, `-U$`, `-R$`, `\.W[ST]$`; manual_exclusions: empty | design 2; spec 6.1 |
| refresh | reuse_hours 24, gf_reuse_days 7, workers 4, connect_timeout_s 5, read_timeout_s 15, deadline_s 30, attempts 3, backoff_s [2, 4] | D13; spec 6.2 |

`tax-rates-oecd-v1.toml`: `[meta]` with `source = "OECD Corporate Tax Statistics, Table II.1 statutory corporate income tax rates, combined central and sub-central"`, `url`, `retrieved`; then `[[rates]]` rows `country`, `year`, `rate` (decimal fraction). Populate 2014 to the newest published year for: United States, Canada, United Kingdom, Ireland, Netherlands, Switzerland, Germany, France, Luxembourg, Israel, Singapore, Japan, Australia, Bermuda (0.0), Cayman Islands (0.0), Jersey (0.0), Puerto Rico (use the OECD value if listed, else omit). Read the values from the OECD data explorer; if the explorer cannot be reached during the build, populate the United States only and record in `[meta]` which countries are pending, so that other countries refuse with a visible reason rather than a wrong rate. `TaxTable.years()` returns the set of `(country, year)` pairs.

`policy/__init__.py`: `load_policy` parses the TOML, builds the dataclasses, and raises `ValueError` naming the section when a value is missing.

- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/policy -v` → 5 passed.
- [ ] **Step 5: Commit** — `git add src/fairband/policy tests/policy && git commit -m "Add the versioned policy file and the statutory tax table"`

---

### Task 4: Engine types, levels and stance

**Files:**
- Create: `src/fairband/engine/__init__.py`, `src/fairband/engine/types.py`, `src/fairband/engine/levels.py`, `tests/engine/test_types.py`, `tests/engine/test_levels.py`

**Interfaces:**
- Produces (`fairband.engine`): `METHOD_VERSION = "fairband-mechanical/0.1"`.
- Produces (`fairband.engine.types`):
  - `Tag = Literal["DATA", "RULE"]`; `Kind = Literal["observed", "estimate", "rule"]`; `Phase = Literal["Start-up", "Young Growth", "High Growth", "Mature Growth", "Mature Stable", "Decline"]`; `PHASE_NUMBER: dict[Phase, int]` 1..6 in that order; `Stance5 = Literal["BUY", "ACCUMULATE / HOLD", "HOLD", "HOLD — above fair band", "TRIM"]`; `Stance3 = Literal["buy", "hold", "trim"]`; `Route = Literal["mature-growth", "mature-stable"]`.
  - `@dataclass(frozen=True) class Provenance: source: str; as_of: date | None; observed_at: datetime | None; entered_at: datetime | None`
  - `@dataclass(frozen=True) class TaggedInput: name: str; value: float | None; unit: str; tag: Tag; kind: Kind; provenance: Provenance; estimate_method: str | None = None; note: str | None = None`
  - `@dataclass(frozen=True) class Flag: code: str; word: str; sentence: str`
  - `@dataclass(frozen=True) class Levels: buy: float; fair_low: float; fair_high: float; trim: float`
  - `@dataclass(frozen=True) class PhaseEvidence: phase: Phase | None; reason: str | None; years_used: int; growth_3y: float | None; growth_word: str | None; growth_decile: int | None; revenue_slope: float | None; margin: float | None; margin_slope: float | None; margin_direction: str | None; fcf_sign: str | None; dickinson: str | None; checks: tuple[Flag, ...]`
  - `@dataclass(frozen=True) class ValuationResult: symbol: str; route: Route | None; value: float | None; levels: Levels | None; stance5: Stance5 | None; stance3: Stance3 | None; price: float | None; price_date: date | None; data_date: date; valid_until: date; phase: PhaseEvidence; inputs: tuple[TaggedInput, ...]; intermediates: dict[str, Any]; flags: tuple[Flag, ...]; refusal: str | None; policy_version: str; method_version: str; deciles_refresh_id: int | None`
  - `def result_to_json(r: ValuationResult) -> str`; `def result_from_json(s: str) -> ValuationResult` (dates as ISO strings; `intermediates` must be JSON-serializable; tuples restored as tuples).
- Produces (`fairband.engine.levels`):
  - `def levels_for(value: float, moat: Moat, policy: Policy) -> Levels`
  - `def stance5(price: float, levels: Levels) -> Stance5`; `def stance3(price: float, levels: Levels) -> Stance3`
  - `def validity_state(valid_from: date, valid_until: date, today: date, aging_fraction: float) -> Literal["current", "aging", "expired"]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/engine/test_levels.py  (policy = load_policy())
def test_levels_wide():
    lv = levels_for(100.0, "Wide", policy)
    assert lv == Levels(buy=75.0, fair_low=85.0, fair_high=115.0, trim=150.0)

def test_levels_none_moat():
    assert levels_for(100.0, "None", policy).buy == 55.0

@pytest.mark.parametrize("price,s5,s3", [
    (74.99, "BUY", "buy"), (75.0, "ACCUMULATE / HOLD", "hold"), (84.99, "ACCUMULATE / HOLD", "hold"),
    (85.0, "HOLD", "hold"), (115.0, "HOLD", "hold"), (115.01, "HOLD — above fair band", "hold"),
    (149.99, "HOLD — above fair band", "hold"), (150.0, "TRIM", "trim")])
def test_stances(price, s5, s3):
    lv = levels_for(100.0, "Wide", policy)
    assert stance5(price, lv) == s5 and stance3(price, lv) == s3

def test_validity_states():
    f, u = date(2026, 1, 1), date(2026, 4, 1)   # 90 days
    assert validity_state(f, u, date(2026, 2, 1), 2/3) == "current"
    assert validity_state(f, u, date(2026, 3, 5), 2/3) == "aging"
    assert validity_state(f, u, date(2026, 4, 2), 2/3) == "expired"

# tests/engine/test_types.py
def test_result_json_round_trip(sample_result):   # fixture builds a full ValuationResult with one flag, two inputs, intermediates {"a": [1, 2]}
    assert result_from_json(result_to_json(sample_result)) == sample_result
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/engine -v` → ImportError.
- [ ] **Step 3: Implement `types.py` and `levels.py`** with the signatures above. Stance boundaries: `price < buy` → BUY; `buy <= price < fair_low` → ACCUMULATE / HOLD; `fair_low <= price <= fair_high` → HOLD; `fair_high < price < trim` → HOLD — above fair band; `price >= trim` → TRIM. `stance3`: BUY→buy, TRIM→trim, else hold. `validity_state`: expired when `today > valid_until`; aging when `today >= valid_from + aging_fraction × (valid_until − valid_from)`.
- [ ] **Step 4: Run to verify they pass** — `uv run pytest tests/engine -v` → all passed.
- [ ] **Step 5: Commit** — `git add src/fairband/engine tests/engine && git commit -m "Add the engine types, the levels and the stance"`

---

### Task 5: The phase classifier

**Files:**
- Create: `src/fairband/engine/classifier.py`, `tests/engine/test_classifier.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class FiscalYear: year: int; period_end: date; currency: str; revenue: float | None; operating_income: float | None; cfo: float | None; cfi: float | None; cff: float | None; capex: float | None`
  - `Series = tuple[FiscalYear, ...]` oldest first.
  - `@dataclass(frozen=True) class Deciles: growth_edges: tuple[float, ...]; margin_slope_edges: tuple[float, ...]; n_growth: int; n_margin: int; refresh_id: int | None` — nine cut points each (`statistics.quantiles(values, n=10, method="inclusive")`).
  - `def slope(values: Sequence[float]) -> float` least-squares slope against index 0..n−1.
  - `def decile(value: float, edges: Sequence[float]) -> int` 1..10: `1 + number of edges <= value`, capped at 10.
  - `def growth_3y(series: Series) -> float | None` — `(rev[-1] / rev[-4]) ** (1/3) − 1`; with 2 or 3 years, the CAGR over the available span; `None` with fewer than 2 years or when either endpoint is `None`.
  - `def is_startup(series: Series) -> bool` — revenue zero now or zero three years ago (when that year exists).
  - `GROWTH_WORDS = ("Close to zero or negative", "Low", "Moderate", "High", "Very High")` mapped from decile pairs 1-2, 3-4, 5-6, 7-8, 9-10.
  - `def compute_deciles(series_by_symbol: Mapping[str, Series], refresh_id: int | None = None) -> Deciles` — growth over symbols with a measurable `growth_3y`; margin-slope over symbols whose last margin is positive and whose slope exists.
  - `def dickinson(fy: FiscalYear) -> str | None` — Introduction, Growth, Mature, Decline, Shake-out per `design.md` 5.2; `None` when a sign is missing.
  - `def classify(series: Series, deciles: Deciles) -> PhaseEvidence`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/engine/test_classifier.py
def fy(year, rev, oi, cfo=10, cfi=-5, cff=-2, capex=-5, cur="USD"): ...  # helper

def test_slope_and_decile():
    assert slope([1, 2, 3, 4, 5]) == pytest.approx(1.0)
    edges = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert decile(0.5, edges) == 1 and decile(5, edges) == 6 and decile(100, edges) == 10

def test_startup_when_revenue_zero_three_years_ago(deciles):
    s = (fy(2022, 0, -5), fy(2023, 10, -8), fy(2024, 40, -9), fy(2025, 120, -9))
    assert classify(s, deciles).phase == "Start-up"

def test_decline_needs_low_growth_and_falling_trend(deciles):   # growth in decile 1, revenue slope < 0
def test_young_vs_high_growth_by_margin_slope(deciles):         # negative margin worsening → Young Growth; improving → High Growth
def test_mature_growth_vs_stable_by_growth_word(deciles):       # positive margin; "High" → Mature Growth; "Low" → Mature Stable
def test_zero_margin_slope_negative_margin_is_young_growth(deciles)
def test_zero_margin_counts_positive_and_flags(deciles)         # check code "margin-zero" in evidence.checks
def test_checks_never_change_phase(deciles)                     # High Growth with "Low" growth word → phase High Growth, check "growth-word-disagrees"
def test_fcf_sign_check(deciles)                                # negative FCF in Mature Growth → check "fcf-sign"
def test_short_history_flagged_and_two_years_unclassified(deciles):
    three = (fy(2023, 100, 10), fy(2024, 110, 12), fy(2025, 121, 14))
    ev = classify(three, deciles)
    assert ev.phase is not None and any(c.code == "short-history" for c in ev.checks)
    one = (fy(2025, 121, 14),)
    assert classify(one, deciles).phase is None and classify(one, deciles).reason == "fewer than two fiscal years"

def test_currency_change_flagged(deciles)                       # check "currency-change"

def test_compute_deciles_excludes_unmeasurable():
    d = compute_deciles({"A": series_a, "B": series_b, "C": one_year_series})
    assert d.n_growth == 2

def test_dickinson():
    assert dickinson(fy(2025, 1, 1, cfo=-1, cfi=-1, cff=1)) == "Introduction"
    assert dickinson(fy(2025, 1, 1, cfo=1, cfi=-1, cff=-1)) == "Mature"
    assert dickinson(fy(2025, 1, 1, cfo=1, cfi=1, cff=1)) == "Shake-out"
```

The `deciles` fixture: `Deciles(growth_edges=(-0.10, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.30), margin_slope_edges=(-0.03, -0.02, -0.01, -0.005, 0.0, 0.005, 0.01, 0.02, 0.03), n_growth=100, n_margin=80, refresh_id=1)`.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/engine/test_classifier.py -v`.
- [ ] **Step 3: Implement `classifier.py`** following `design.md` 5.3–5.6 exactly: rules in order (Start-up; Decline when growth word is "Close to zero or negative" and `slope(revenue[-5:]) < 0`; negative margin → Young/High by `slope(margin[-5:])` with `<= 0` → Young Growth; positive margin → Mature Growth for Very High/High/Moderate else Mature Stable). Margin direction for positive margins: decile of the margin slope 8–10 and slope > 0 → Rising; 1–3 and slope < 0 → Declining; else Stable. Checks as `Flag`s with codes `growth-word-disagrees`, `margin-direction-disagrees`, `fcf-sign`, `short-history`, `margin-zero`, `currency-change`. Use the last up-to-five years for slopes, at least three.
- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "Add the life-cycle phase classifier"`

---

### Task 6: ROIC

**Files:**
- Create: `src/fairband/engine/roic.py`, `tests/engine/test_roic.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class CapitalYear: year: int; operating_income: float | None; tax_rate: float | None; total_current_assets: float | None; cash_and_investments: float | None; total_current_liabilities: float | None; short_term_debt: float | None; current_lease_liability: float | None; net_ppe: float | None; lease_rou_asset: float | None; goodwill: float | None; intangibles: float | None`
  - `@dataclass(frozen=True) class RoicYear: year: int; nopat: float; average_capital: float; roic: float`
  - `@dataclass(frozen=True) class RoicResult: aggregate: float | None; years_used: int; by_year: tuple[RoicYear, ...]; flags: tuple[Flag, ...]`
  - `def invested_capital(y: CapitalYear) -> float | None` — `(tca − cash) − (tcl − std − current_lease) + net_ppe + rou + goodwill + intangibles`; `None` when `total_current_assets`, `total_current_liabilities` or `net_ppe` is `None`; the optional components (`cash_and_investments`, `short_term_debt`, `current_lease_liability`, `lease_rou_asset`, `goodwill`, `intangibles`) count as 0 when `None`.
  - `def not_presented(y: CapitalYear) -> tuple[str, ...]` — the optional component names that are `None`.
  - `def nopat(y: CapitalYear) -> float | None` — `operating_income × (1 − tax_rate)`; `None` if either is `None`.
  - `def aggregate_roic(years: Sequence[CapitalYear], min_years: int = 5) -> RoicResult` — years oldest first; year i (i ≥ 1) uses `nopat(years[i])` and `(ic(years[i-1]) + ic(years[i])) / 2`; a year whose NOPAT or either capital is `None` is dropped; aggregate = Σ nopat ÷ Σ average capital over the kept years, at most the last ten; flags: `roic-on-n-years` when fewer than ten kept and at least `min_years`; `roic-unavailable` and `aggregate=None` when fewer than `min_years`; `charge-zeroed` and `aggregate=None` when Σ average capital ≤ 0; one `line-not-presented:<field>` flag per optional field that is `None` in any kept year.
  - `def terminal_roic(aggregate: float | None, moat: Moat, policy: Policy) -> float` — Wide: `max(r, min(aggregate, cap))` (with `aggregate=None` → `r`); else `r`.

- [ ] **Step 1: Write the failing tests**

```python
def test_design_example_aggregate():
    # design 6.6: 7 years of 20 on 100, year 8 -10 on 100, year 9 20 on 20, year 10 22 on 110 → 18.5%
    # build 11 CapitalYears whose invested capital equals the stated opening/closing so each average equals the design's capital
    ...
    r = aggregate_roic(years)
    assert r.aggregate == pytest.approx(172 / 930, abs=1e-6) and r.years_used == 10 and r.flags == ()

def test_not_presented_counts_nil_and_flags():
    y = CapitalYear(2025, 100, 0.21, 500, 200, 300, 50, None, 400, None, None, None)
    assert invested_capital(y) == pytest.approx(500 - 200 - (300 - 50) + 400)
    assert not_presented(y) == ("current_lease_liability", "lease_rou_asset", "goodwill", "intangibles")

def test_required_total_missing_drops_year():      # net_ppe None → that year dropped; years_used 9; flag roic-on-n-years
def test_fewer_than_five_years_unavailable():      # 4 kept years → aggregate None, flag roic-unavailable
def test_negative_capital_zeroes_charge():         # Σ average capital ≤ 0 → aggregate None, flag charge-zeroed
def test_terminal_roic_rules():
    assert terminal_roic(0.25, "Wide", policy) == 0.13
    assert terminal_roic(0.11, "Wide", policy) == 0.11
    assert terminal_roic(0.05, "Wide", policy) == 0.09
    assert terminal_roic(0.25, "Narrow", policy) == 0.09 and terminal_roic(None, "Wide", policy) == 0.09
```

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement `roic.py`.**
- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "Add the ten-year aggregate ROIC"`

---

### Task 7: Mature Growth valuation core

**Files:**
- Create: `src/fairband/engine/mature_growth.py`, `tests/engine/test_mature_growth.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class GrowthPath: year1: float; steps: tuple[float | None, float | None]; belief: float; runway: int` — `year1` is year-1 net income (a total, not per share); `steps` are the growth rates for years 2 and 3, `None` meaning the belief; `belief` applies to years 4..runway.
  - `@dataclass(frozen=True) class Charge: runway_roic: float; terminal_roic: float; r: float; g_t: float; charge_off: bool = False` — `math.inf` ROIC means no charge; `charge_off=True` means no charge in any year (capital ≤ 0).
  - `def growth_rates(path: GrowthPath) -> tuple[float, ...]` — g for years 2..runway (length runway−1).
  - `def earnings_by_year(path: GrowthPath) -> tuple[float, ...]` — net income for years 1..runway.
  - `def cash_to_equity(ni: float, g_next: float, roic: float, charge_off: bool = False) -> float` — `ni × (1 − g_next / roic)`; `ni` when `roic` is inf or `charge_off`.
  - `def terminal_multiple(roic: float, r: float, g_t: float) -> float` — `(1 + g_t) × (1 − g_t / roic) / (r − g_t)`.
  - `def value_at_belief(path: GrowthPath, charge: Charge) -> float` — Σ_{t=1..N} cash_t / (1+r)^t + NI_N × terminal_multiple / (1+r)^N, where cash_t uses g_{t+1} (year N uses g_t with `terminal_roic`; years before N use `runway_roic`).
  - `def implied_growth(target: float, path: GrowthPath, charge: Charge, lo: float = -0.5, hi: float = 0.5, tol: float = 1e-7) -> float | None` — the belief at which `value_at_belief` equals `target`; bisection after scanning `[lo, hi]` in steps of 0.01 for the first sign change; `None` when no sign change.

- [ ] **Step 1: Write the failing tests**

```python
R, GT = 0.09, 0.03

@pytest.mark.parametrize("roic,expected", [(math.inf, 17.2), (0.30, 15.5), (0.15, 13.7), (0.13, 13.2), (0.09, 11.4)])
def test_terminal_multiples_design_table(roic, expected):
    assert terminal_multiple(roic, R, GT) == pytest.approx(expected, abs=0.05)

def worked_example(): return GrowthPath(year1=1.0, steps=(0.12, 0.10), belief=0.08, runway=20)

def test_uncharged_matches_design():
    v = value_at_belief(worked_example(), Charge(math.inf, math.inf, R, GT))
    assert v == pytest.approx(31.7, abs=0.1)

@pytest.mark.parametrize("roic,expected", [(0.30, 25.5), (0.20, 22.4), (0.15, 19.3)])
def test_charged_terminal_equals_runway(roic, expected):
    assert value_at_belief(worked_example(), Charge(roic, roic, R, GT)) == pytest.approx(expected, abs=0.1)

def test_implied_growth_at_20pct_roic():
    # the design's price proxy is the uncharged value at 8%; at a 20% ROIC that price needs 11.8%
    g = implied_growth(value_at_belief(worked_example(), Charge(math.inf, math.inf, R, GT)), worked_example(), Charge(0.20, 0.20, R, GT))
    assert g == pytest.approx(0.118, abs=0.002)

@pytest.mark.parametrize("roic,expected", [(0.30, 23.6), (0.20, 21.2), (0.15, 18.9)])
def test_charged_with_wide_cap(roic, expected):   # production rule: terminal ROIC capped at 13%
    assert value_at_belief(worked_example(), Charge(roic, 0.13, R, GT)) == pytest.approx(expected, abs=0.1)

def test_implied_growth_round_trip():
    p = worked_example(); c = Charge(0.20, 0.13, R, GT)
    assert implied_growth(value_at_belief(p, c), p, c) == pytest.approx(0.08, abs=1e-5)

def test_implied_growth_none_when_out_of_range():
    assert implied_growth(1e9, worked_example(), Charge(0.20, 0.13, R, GT)) is None

def test_charge_off_equals_uncharged():
    assert value_at_belief(worked_example(), Charge(0.2, 0.13, R, GT, charge_off=True)) == pytest.approx(value_at_belief(worked_example(), Charge(math.inf, math.inf, R, GT)))
```

If a design figure differs from the computed value by more than the tolerance, keep the test at the computed value and record the difference in the commit message and in a note at the top of the test file; do not change the formula.

- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement `mature_growth.py`.**
- [ ] **Step 4: Run to verify they pass.**
- [ ] **Step 5: Commit** — `git commit -m "Add the Mature Growth valuation core with the reinvestment charge"`

---

### Task 8: Mature Stable values and EPV

**Files:**
- Create: `src/fairband/engine/mature_stable.py`, `src/fairband/engine/multiples.py`, `tests/engine/test_mature_stable.py`, `tests/engine/test_multiples.py`

**Interfaces:**
- Produces (`mature_stable`): `def mature_stable_values(e: float, terminal_roic: float, r: float, g_t: float) -> tuple[float, float]` → `(epv, stable_growth)` with `epv = e / r`, `stable_growth = e × (1 − g_t / terminal_roic) / (r − g_t)`; `def normalize_for_margin(e: float, ttm_margin: float, median_margin: float, flagged: bool) -> float` → `e × median / ttm` when `flagged` and both margins > 0, else `e`.
- Produces (`multiples`): `@dataclass(frozen=True) class Multiples: pe_reported: float | None; pe_clean: float | None; pe_forward: float | None`; `def multiples(price: float, eps_reported: float | None, eps_clean: float | None, eps_forward: float | None) -> Multiples` (`None` when the EPS is `None` or ≤ 0); `def epv(eps_clean: float, r: float) -> float`; `def growth_share(epv_value: float, price: float) -> float` → `1 − epv/price`.

- [ ] **Step 1: Write the failing tests**

```python
def test_equal_when_terminal_roic_is_r():
    epv_v, sg = mature_stable_values(9.0, 0.09, 0.09, 0.03)
    assert epv_v == pytest.approx(100.0) and sg == pytest.approx(100.0)

def test_wide_cap_at_most_15pct_above_epv():
    epv_v, sg = mature_stable_values(9.0, 0.13, 0.09, 0.03)
    assert sg / epv_v == pytest.approx(1.1538, abs=1e-3)

def test_margin_scaling_only_when_flagged():
    assert normalize_for_margin(100.0, 0.30, 0.20, True) == pytest.approx(66.667, abs=1e-2)
    assert normalize_for_margin(100.0, 0.30, 0.20, False) == 100.0

def test_multiples_and_epv():
    m = multiples(100.0, 5.0, 4.0, 0.0)
    assert m.pe_reported == 20.0 and m.pe_clean == 25.0 and m.pe_forward is None
    assert epv(9.0, 0.09) == 100.0 and growth_share(100.0, 400.0) == 0.75
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the Mature Stable values, EPV and the multiples"`.

---

### Task 9: The anchor, the path and the belief

**Files:**
- Create: `src/fairband/engine/anchor.py`, `tests/engine/test_anchor.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class QuarterEstimate: period_end: date; fiscal_year: int; fiscal_period: str; eps: float | None; revenue: float | None; net_income: float | None; analysts: int | None`
  - `@dataclass(frozen=True) class AnnualEstimate: fiscal_year: int; period_end: date; eps: float | None; revenue: float | None; net_income: float | None; analysts_eps: int | None; analysts_net_income: int | None`
  - `@dataclass(frozen=True) class TrailingFigures: period_end: date; quarters: int; on_fiscal_year: bool; revenue: float | None; operating_income: float | None; net_income: float | None; eps_diluted: float | None; sbc: float | None; cfo: float | None; capex: float | None; dividends: float | None; buybacks: float | None; equity_issued: float | None`
  - `def ntm_quarters(estimates: Sequence[QuarterEstimate], last_reported: date) -> tuple[QuarterEstimate, ...] | None` — the four with `period_end > last_reported`, sorted by period end, consecutive quarters (each about three months after the previous); `None` if fewer than four.
  - `SbcBasis = Literal["excludes-sbc", "includes-sbc", "unknown"]`
  - `def sbc_basis(street_ttm_eps: float | None, gaap_ttm_eps: float | None, sbc_after_tax_per_share: float | None, detect: float) -> SbcBasis`
  - `@dataclass(frozen=True) class Anchor: ntm_eps_raw: float; sbc_adjustment_per_share: float; ntm_eps: float; ntm_net_income: float; basis: SbcBasis; flags: tuple[Flag, ...]; refusal: str | None`
  - `def ntm_anchor(quarters: Sequence[QuarterEstimate], trailing: TrailingFigures, street_ttm_eps: float | None, shares: float, tax_rate: float, price: float, policy: Policy) -> Anchor` — raw = Σ eps; SBC after tax per share TTM = `sbc × (1 − tax) / shares`; when basis is `excludes-sbc`, adjustment = that amount scaled by `Σ ntm revenue / trailing revenue` when both exist, else unscaled; `ntm_eps = raw − adjustment`; `ntm_net_income = ntm_eps × shares`; refusals: `"no positive forward anchor"` when `ntm_eps <= 0`; `"forward P/E below 2: unit error"` when `price / ntm_eps < policy.forward_pe_unit_error`; flag `sbc-basis-unknown` when basis is unknown.
  - `def base_fiscal_year(quarters: Sequence[QuarterEstimate]) -> int` — the fiscal year holding most of the four; tie → the later year.
  - `@dataclass(frozen=True) class Path: steps: tuple[float | None, float | None]; on_eps: bool; analysts: tuple[int | None, int | None]; flags: tuple[Flag, ...]`
  - `def path_steps(annual: Sequence[AnnualEstimate], base_year: int, policy: Policy) -> Path` — steps `base→base+1` and `base+1→base+2` on net income when all three are present and > 0, else on EPS with `on_eps=True` and flag `path-on-eps`; a step whose later year is absent or whose mean is 0 with no analysts is `None`; flag `few-analysts` when a used year has analysts `< policy.analyst_min` or `None`.
  - `@dataclass(frozen=True) class Belief: rate: float; sales_class: str; median: float`
  - `def belief_from_sales(revenue_ttm_usd: float, policy: Policy) -> Belief` — revenue in USD millions against `base_rates` upper bounds; `rate = median + inflation_addition`.
  - `def moat_class(score: float | None, policy: Policy) -> Moat`.

- [ ] **Step 1: Write the failing tests**

```python
def q(pe, fy, fp, eps, rev=None, ni=None, n=10): return QuarterEstimate(date.fromisoformat(pe), fy, fp, eps, rev, ni, n)

def test_ntm_quarters_picks_by_period_not_order():
    far = [q("2029-03-31", 2029, "Q3", 9), q("2026-12-31", 2027, "Q2", 1), q("2026-09-30", 2027, "Q1", 1),
           q("2027-06-30", 2027, "Q4", 1), q("2027-03-31", 2027, "Q3", 1), q("2028-09-30", 2029, "Q1", 5)]
    got = ntm_quarters(far, date(2026, 6, 30))
    assert [x.period_end.isoformat() for x in got] == ["2026-09-30", "2026-12-31", "2027-03-31", "2027-06-30"]

def test_ntm_quarters_none_when_gap():      # 2026-09-30, 2026-12-31, 2027-06-30, 2027-09-30 → None

def test_sbc_basis():
    assert sbc_basis(5.0, 4.0, 1.5, 0.5) == "excludes-sbc"    # gap 1.0 ≥ 0.75
    assert sbc_basis(4.2, 4.0, 1.5, 0.5) == "includes-sbc"
    assert sbc_basis(None, 4.0, 1.5, 0.5) == "unknown"

def test_anchor_subtracts_sbc_scaled_by_revenue(policy):   # trailing revenue 100, NTM revenue 120, sbc 10, tax 0.21, shares 10 → adj = 0.79 × 1.2 = 0.948
def test_anchor_refusals(policy):                           # ntm_eps ≤ 0 → "no positive forward anchor"; price 1 / eps 1 → "forward P/E below 2: unit error"

def test_base_fiscal_year_tie_takes_later():
    qs = [q("2026-09-30", 2026, "Q4", 1), q("2026-12-31", 2027, "Q1", 1), q("2027-03-31", 2027, "Q2", 1), q("2027-06-30", 2027, "Q3", 1)]
    assert base_fiscal_year(qs) == 2027
    tie = [q("2026-06-30", 2026, "Q3", 1), q("2026-09-30", 2026, "Q4", 1), q("2026-12-31", 2027, "Q1", 1), q("2027-03-31", 2027, "Q2", 1)]
    assert base_fiscal_year(tie) == 2027

def test_path_on_net_income_then_eps_fallback(policy):      # NI present → steps from NI, on_eps False; NI missing → EPS, flag path-on-eps
def test_path_few_analysts_flag(policy)                      # analysts 3 on year base+2 → flag few-analysts
def test_belief_from_sales(policy):
    assert belief_from_sales(400_000, policy) == Belief(0.053, ">$50,000 Mn", 0.033)
    assert belief_from_sales(100, policy).sales_class == "$0-325 Mn"

def test_moat_class(policy):
    assert moat_class(8, policy) == "Wide" and moat_class(7.9, policy) == "Narrow" and moat_class(3, policy) == "None" and moat_class(None, policy) == "None"
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the NTM anchor, the consensus path and the belief rule"`.

---

### Task 10: Flags, expected return and price facts

**Files:**
- Create: `src/fairband/engine/flags.py`, `src/fairband/engine/returns.py`, `src/fairband/engine/price_facts.py`, tests for each under `tests/engine/`

**Interfaces:**
- Produces (`flags`):
  - `def margin_flag(series: Series, ttm_margin: float | None, policy: Policy) -> Flag | None` — needs ≥ `margin_flag_min_years` fiscal years with margins; fires when `ttm_margin >= ratio × median` (median > 0) or `ttm_margin >= high × (1 + above_high)`; word by `mech/1.2`: `Possible cycle peak` when a window year has operating income < 0 and median > 0; `Newly profitable` when median ≤ 0; else `Margin above history`; code `margin-flag`.
  - `def gate_flags(trailing: TrailingFigures, market_cap: float | None, policy: Policy) -> tuple[Flag, ...]` — `equity-raise` when `equity_issued >= equity_raise_share × market_cap`; `negative-fcf` when `cfo + capex < 0`; `heavy-capex` when `-capex > capex_ocf_flag × cfo` and `cfo > 0`.
  - `def nri_flag(nri_gap_per_share: float | None, eps_ttm: float | None, policy: Policy) -> Flag | None` — `large-nri` when `|gap| >= share × |eps|`.
  - `def long_runway_flag(runway: int, belief: float, implied: float | None, policy: Policy) -> Flag | None` — `long-runway-high-growth` when runway 20 and either rate ≥ threshold.
  - `def value_spread_flag(values: Sequence[float], policy: Policy) -> Flag | None` — `value-spread` when `(max − min) / min >= value_spread_flag`.
- Produces (`returns`): `@dataclass(frozen=True) class ExpectedReturn: income: float; growth: float; repricing: float; total: float`; `def expected_return(price: float, value: float, dividend_yield: float, net_buyback_yield: float, steps: tuple[float | None, float | None], belief: float, horizon: int = 3) -> ExpectedReturn` — growth = `((1+g2)(1+g3)(1+belief))^(1/3) − 1` with `None` steps replaced by the belief; repricing = `ln(value/price) / horizon`.
- Produces (`price_facts`): `@dataclass(frozen=True) class PriceFacts: high_52w: float | None; low_52w: float | None; change_1y: float | None; change_3y: float | None; change_5y: float | None; drawdown_from_peak: float | None`; `def price_facts(closes: Sequence[tuple[date, float]], today: date) -> PriceFacts` — a change uses the last close on or before `today − n years` (within 7 days) else `None`; peak = max close in the series.

- [ ] **Step 1: Write the failing tests**

```python
def test_margin_flag_labels(policy):     # three series: loss year + median>0 → "Possible cycle peak"; median ≤ 0 → "Newly profitable"; else "Margin above history"; fewer than 6 years → None
def test_margin_flag_above_high(policy)  # ttm 0.33 vs high 0.30 → fires; ttm 0.32 → None
def test_gate_flags(policy)
def test_nri_flag(policy)
def test_long_runway_flag(policy)
def test_value_spread_flag(policy):      # [100, 131] → flag; [100, 129] → None
def test_expected_return_design_example():   # method v1.7 Step 9: price 338.46, value 473, div 0.0025, buyback -0.01, steps (0.199, 0.169), belief 0.08 → growth ≈ 0.148, repricing ≈ 0.112, total ≈ 0.253
def test_price_facts_full_history()
def test_price_facts_short_history():    # 18 months of closes → change_3y None, change_5y None, high_52w present
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the flags, the expected return and the price facts"`.

---

### Task 11: Route dispatch and the result

**Files:**
- Create: `src/fairband/engine/route.py`, `tests/engine/test_route.py`, `tests/engine/conftest.py` (builders for a complete Mature Growth `CompanyInputs` and a Mature Stable one)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class CompanyInputs: symbol: str; name: str; country: str; currency: str; is_adr: bool; market_cap: float | None; price: float | None; price_date: date | None; shares_diluted: float | None; series: Series; capital_years: tuple[CapitalYear, ...]; tax_rate_latest: float | None; trailing: TrailingFigures | None; quarter_estimates: tuple[QuarterEstimate, ...]; annual_estimates: tuple[AnnualEstimate, ...]; street_ttm_eps: float | None; moat_score: float | None; gf_eps_ttm: float | None; gf_eps_without_nri: float | None; next_earnings: date | None; closes: tuple[tuple[date, float], ...]; data_date: date; provenance: dict[str, Provenance]; input_flags: tuple[Flag, ...]; refusal: str | None`
  - `def value_company(inputs: CompanyInputs, deciles: Deciles | None, policy: Policy, today: date) -> ValuationResult`
  - `def reprice(result: ValuationResult, price: float, price_date: date, policy: Policy) -> ValuationResult` — same value and levels; new price, stance, price-dependent intermediates (`implied_growth`, `multiples`, `expected_return` recomputed), `valid_until` unchanged. A result with `value=None` only gets the new price and date.
  - `def refusal_result(symbol: str, reason: str, policy: Policy, data_date: date, price: float | None = None, price_date: date | None = None, phase: PhaseEvidence | None = None, inputs: tuple[TaggedInput, ...] = (), flags: tuple[Flag, ...] = (), deciles_refresh_id: int | None = None) -> ValuationResult` — `valid_until = data_date + validity_fallback_days`; `phase` defaults to an empty `PhaseEvidence` with `phase=None, reason=reason`.
- Order inside `value_company`: (1) `inputs.refusal` → `refusal_result` with phase evidence if computable; (2) `deciles is None` → phase `None`, reason and refusal `"no universe deciles yet"`; (3) classify; (4) `is_adr or currency != "USD"` → refusal `"foreign filer: currency and share-unit handling not built yet"`; (5) phase not in the two mature phases → refusal `"<phase> route not built yet"` (Start-up: `"Start-up: no value by design; the price-implied requirement comes with the Start-up route"`); (6) `price is None` → `"no price"`; (7) `shares_diluted` missing or ≤ 0 → `"no diluted share count"`; (8) the route. Every result carries `inputs` built from `provenance` (DATA, kind observed/estimate) plus the RULE inputs from the policy (`required_return`, `terminal_growth`, `runway_years`, `margin_of_safety`, `belief`, `moat_class`), `valid_until` = `next_earnings` else `data_date + validity_fallback_days`, `flags` = input flags + classifier checks + route flags.
- Mature Growth intermediates (keys, all JSON-able): `anchor`, `path`, `belief`, `moat`, `runway`, `roic` (aggregate, years, by_year), `terminal_roic`, `value_total`, `value_per_share`, `implied_growth`, `implied_growth_by_runway` {5, 10, 20}, `value_by_roic` {aggregate, 0.15, 0.09} and `implied_by_roic`, `epv`, `growth_share`, `multiples`, `expected_return`, `price_facts`, `sbc_basis`.
- Mature Stable intermediates: `e_trailing`, `e_normalized`, `margin_scaled`, `epv`, `stable_growth`, `terminal_roic`, `moat`, `value_per_share`, `multiples`, `price_facts`, `expected_return` (steps `(None, None)`, belief `g_t`).

- [ ] **Step 1: Write the failing tests**

```python
def test_mature_growth_end_to_end(mg_inputs, deciles, policy):
    r = value_company(mg_inputs, deciles, policy, date(2026, 10, 31))
    assert r.route == "mature-growth" and r.refusal is None and r.value is not None
    assert r.levels == levels_for(r.value, r.intermediates["moat"], policy)
    assert r.stance5 == stance5(r.price, r.levels)
    assert {i.name for i in r.inputs} >= {"ntm_net_income", "required_return", "belief", "moat_class", "aggregate_roic"}
    assert all(i.tag in ("DATA", "RULE") for i in r.inputs)
    assert r.valid_until == mg_inputs.next_earnings
    assert result_from_json(result_to_json(r)) == r

def test_mature_stable_end_to_end(ms_inputs, deciles, policy):   # route mature-stable; value == stable_growth / shares

def test_refuses_without_deciles(mg_inputs, policy):
    r = value_company(mg_inputs, None, policy, date(2026, 10, 31))
    assert r.phase.phase is None and r.refusal == "no universe deciles yet"

def test_refuses_foreign_filer(mg_inputs, deciles, policy):      # currency EUR → the foreign-filer refusal, phase still assigned
def test_refuses_other_phases(young_growth_inputs, deciles, policy)   # "Young Growth route not built yet"
def test_refuses_without_shares(mg_inputs, deciles, policy):
    r = value_company(replace(mg_inputs, shares_diluted=0.0), deciles, policy, date(2026, 10, 31))
    assert r.refusal == "no diluted share count" and r.value is None
def test_refuses_without_price(mg_inputs, deciles, policy):
    r = value_company(replace(mg_inputs, price=None, price_date=None), deciles, policy, date(2026, 10, 31))
    assert r.refusal == "no price" and r.phase.phase == "Mature Growth"
def test_refusal_result_shape(policy):
    r = refusal_result("X", "data fetch failed: quote", policy, date(2026, 10, 31))
    assert r.value is None and r.price is None and r.valid_until == date(2026, 10, 31) + timedelta(days=91)
def test_fallback_validity(mg_inputs, deciles, policy):          # next_earnings None → data_date + 91 days
def test_reprice_keeps_value_changes_stance(mg_inputs, deciles, policy)
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the route dispatch and the valuation result"`.

---

### Task 12: The store: connection and migrations

**Files:**
- Create: `src/fairband/store/__init__.py`, `src/fairband/store/db.py`, `src/fairband/store/migrations/001_initial.sql`, `tests/store/test_db.py`; modify `src/fairband/__main__.py` (`migrate` subcommand)

**Interfaces:**
- Produces: `def connect(path: Path) -> sqlite3.Connection` (creates parent dirs; `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `synchronous=FULL`; `row_factory = sqlite3.Row`; the record modules use `with conn:` for one transaction per write call); `def migrate(conn: sqlite3.Connection) -> list[str]` (applies unapplied `NNN_*.sql` files from the package in order inside one transaction each, records `schema_versions(version, filename, checksum, applied_at)`, refuses with `ValueError` on a checksum mismatch); `def applied_versions(conn) -> list[int]`.
- `001_initial.sql` creates: `schema_versions`, `policy_versions(version TEXT PRIMARY KEY, hash TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL)`, `refreshes(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, symbols TEXT, status TEXT NOT NULL, stage TEXT, started_at TEXT NOT NULL, finished_at TEXT, policy_version TEXT NOT NULL, method_version TEXT NOT NULL, calibration TEXT, message TEXT)`, `refresh_items(refresh_id INTEGER NOT NULL REFERENCES refreshes(id), symbol TEXT NOT NULL, status TEXT NOT NULL, error TEXT, updated_at TEXT NOT NULL, PRIMARY KEY (refresh_id, symbol))`, `deciles(refresh_id INTEGER PRIMARY KEY REFERENCES refreshes(id), growth_edges TEXT NOT NULL, margin_slope_edges TEXT NOT NULL, n_growth INTEGER NOT NULL, n_margin INTEGER NOT NULL, computed_at TEXT NOT NULL)`, `companies(symbol TEXT NOT NULL, refresh_id INTEGER NOT NULL REFERENCES refreshes(id), name TEXT, exchange TEXT, sector TEXT, industry TEXT, country TEXT, currency TEXT, is_adr INTEGER NOT NULL, cap_band TEXT, market_cap TEXT, eligible INTEGER NOT NULL, exclusion_reason TEXT, observed_at TEXT NOT NULL, PRIMARY KEY (symbol, refresh_id))`, `vendor_responses(id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, endpoint TEXT NOT NULL, params TEXT NOT NULL, symbol TEXT, http_status INTEGER, observed_at TEXT NOT NULL, payload TEXT, error TEXT)` with index `(provider, endpoint, symbol, observed_at)`, `facts(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, dataset TEXT NOT NULL, period_end TEXT NOT NULL, fiscal_year INTEGER, fiscal_period TEXT, field TEXT NOT NULL, value TEXT, unit TEXT, currency TEXT, kind TEXT NOT NULL, estimate_method TEXT, missing_reason TEXT, as_of TEXT, observed_at TEXT NOT NULL, entered_at TEXT NOT NULL, response_id INTEGER NOT NULL REFERENCES vendor_responses(id))` with index `(symbol, dataset, period_end, field)`, `observations(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, dataset TEXT NOT NULL, period TEXT, field TEXT NOT NULL, value TEXT, unit TEXT, as_of TEXT, observed_at TEXT NOT NULL, entered_at TEXT NOT NULL, response_id INTEGER NOT NULL REFERENCES vendor_responses(id))` with index `(symbol, dataset, period, field)`, `snapshots(id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT NOT NULL, refresh_id INTEGER NOT NULL REFERENCES refreshes(id), deciles_refresh_id INTEGER, created_at TEXT NOT NULL, phase TEXT, route TEXT, value TEXT, buy_level TEXT, fair_low TEXT, fair_high TEXT, trim_level TEXT, price TEXT, stance5 TEXT, stance3 TEXT, price_date TEXT, data_date TEXT NOT NULL, valid_until TEXT NOT NULL, flags TEXT NOT NULL, refusal TEXT, policy_version TEXT NOT NULL, method_version TEXT NOT NULL, result TEXT NOT NULL)` with index `(symbol, id)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_empty_db_migrates(tmp_path):
    conn = connect(tmp_path / "f.db")
    assert migrate(conn) == ["001_initial.sql"] and applied_versions(conn) == [1]
    assert migrate(conn) == []           # idempotent
    names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert {"schema_versions", "companies", "vendor_responses", "facts", "observations", "snapshots", "refreshes", "refresh_items", "deciles", "policy_versions"} <= names

def test_checksum_mismatch_refuses(tmp_path):   # tamper schema_versions.checksum → migrate raises ValueError
def test_pragmas(tmp_path):                     # journal_mode wal, foreign_keys 1
def test_cli_migrate(tmp_path):                 # python -m fairband migrate with FAIRBAND_DATA_DIR → db exists
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the SQLite store with ordered migrations"`.

---

### Task 13: Store record modules

**Files:**
- Create: `src/fairband/store/companies.py`, `vendor.py`, `facts.py`, `observations.py`, `snapshots.py`, `refreshes.py`, `policy.py`; `tests/store/test_records.py`

**Interfaces:**
- `companies`: `@dataclass(frozen=True) class CompanyRow` (the table's columns; `market_cap: Decimal | None`); `insert_companies(conn, rows: Sequence[CompanyRow]) -> None`; `latest_companies(conn, eligible_only: bool = True) -> list[CompanyRow]` (rows of the newest `refresh_id` that has companies); `latest_company(conn, symbol) -> CompanyRow | None`.
- `vendor`: `record_response(conn, provider, endpoint, params: Mapping[str, str], symbol: str | None, http_status: int | None, payload: str | None, error: str | None, observed_at: datetime) -> int`; `@dataclass(frozen=True) class ResponseRow`; `latest_response(conn, provider, endpoint, symbol, params) -> ResponseRow | None` (newest with `http_status == 200`); `response_payload(conn, response_id) -> str | None`.
- `facts`: `@dataclass(frozen=True) class FactRow` (columns; `value: Decimal | None`); `insert_facts(conn, rows) -> None`; `facts_for(conn, symbol, dataset) -> list[FactRow]` — for each `(period_end, field)` the row from the newest `response_id`.
- `observations`: `ObservationRow`, `insert_observations`, `observations_for(conn, symbol, dataset) -> list[ObservationRow]` (newest per `(period, field)`).
- `snapshots`: `insert_snapshot(conn, result: ValuationResult, refresh_id: int) -> int`; `@dataclass(frozen=True) class SnapshotRow` (indexed columns + `result: ValuationResult`); `latest_snapshots(conn) -> list[SnapshotRow]` (newest per symbol); `latest_snapshot(conn, symbol) -> SnapshotRow | None`.
- `refreshes`: `create_refresh(conn, kind, symbols: Sequence[str] | None, policy_version, method_version, started_at) -> int`; `set_stage(conn, refresh_id, stage)`; `finish_refresh(conn, refresh_id, status, finished_at, message=None, calibration: dict | None = None)`; `upsert_item(conn, refresh_id, symbol, status, error, updated_at)`; `items(conn, refresh_id) -> list[ItemRow]`; `current_refresh(conn) -> RefreshRow | None` (status `running`); `mark_interrupted(conn, at) -> int`; `save_deciles(conn, refresh_id, deciles: Deciles, at)`; `latest_deciles(conn) -> Deciles | None`; `latest_refresh(conn) -> RefreshRow | None`.
- `policy`: `record_policy(conn, policy: Policy, at) -> None` (insert or ignore by version; raise `ValueError` if the same version has a different hash).
- Every write function runs inside `with conn:` (one transaction per call).

- [ ] **Step 1: Write the failing tests** — one test per function pair above, plus: `test_facts_for_returns_newest_response_per_period_field`, `test_latest_snapshots_one_per_symbol`, `test_record_policy_rejects_changed_hash`, `test_mark_interrupted_flips_running`.
- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the store record modules"`.

---

### Task 14: The vendor HTTP client and the key scrub

**Files:**
- Create: `src/fairband/vendors/__init__.py`, `src/fairband/vendors/scrub.py`, `src/fairband/vendors/http.py`, `tests/vendors/test_scrub.py`, `tests/vendors/test_http.py`

**Interfaces:**
- `scrub`: `def scrub(text: str, secrets: Iterable[str]) -> str` — replaces every occurrence of each non-empty secret (and its URL-encoded form) with `<key>`.
- `http`: `class VendorError(Exception)` with `status: int | None`, `retryable: bool`, message already scrubbed; `@dataclass(frozen=True) class VendorResponse: status: int; json: Any; text: str; url: str; observed_at: datetime; attempts: int` (`url` scrubbed); `class VendorHttp` with `__init__(self, base_url: str, secrets: Sequence[str], policy: RefreshPolicy, transport: httpx.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep, clock: Callable[[], datetime] = utcnow)` and `def get(self, path: str, params: Mapping[str, str]) -> VendorResponse`. Client settings: `follow_redirects=False`, `trust_env=False`, `verify=True`, `timeout=httpx.Timeout(connect=..., read=..., write=..., pool=...)` from policy; a wall-clock deadline per call; retries on transport errors, 408, 429 and 5xx up to `attempts` with `backoff_s`; `Retry-After` honored within the deadline; no retry on 401, 402, 403, 404 or on a redirect (3xx is a `VendorError(retryable=False)`); every log line goes through `scrub`; the logger is `fairband.vendors`.

- [ ] **Step 1: Write the failing tests**

```python
def test_scrub_plain_and_encoded():
    assert scrub("https://x/?apikey=SECRET123&sym=AAPL", ["SECRET123"]) == "https://x/?apikey=<key>&sym=AAPL"
    assert scrub("/public/user/T0K3N/stock", ["T0K3N"]) == "/public/user/<key>/stock"

def test_key_never_in_response_url_or_logs(caplog):   # MockTransport returns 200; assert "SECRET" not in resp.url and not in any caplog record; with a 500 the VendorError message has "<key>"
def test_retries_then_succeeds():     # transport: 429, 503, 200 → attempts == 3; sleep called with 2 then 4
def test_no_retry_on_402():           # VendorError status 402, retryable False, one call
def test_redirect_refused():          # 302 → VendorError, no second request
def test_deadline_bounds_retries():   # clock advances past deadline_s → stops after the first retry
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the vendor HTTP client with the key scrub"`.

---

### Task 15: The FMP adapter and its normalizer

**Files:**
- Create: `src/fairband/vendors/fmp.py`, `src/fairband/vendors/normalize_fmp.py`, `tests/vendors/test_fmp.py`, `tests/vendors/test_normalize_fmp.py`, `tests/fixtures/fmp/*.json` (synthetic: two companies, two to three periods each, realistic field names, round numbers)

**Interfaces:**
- `fmp`: `class Fmp` with `__init__(self, http: VendorHttp, api_key: str)`; base URL `https://financialmodelingprep.com/stable`; each method returns `VendorResponse` and passes `apikey` as a query parameter: `screener(self) -> VendorResponse` (`company-screener` with `exchange=NYSE,NASDAQ,AMEX`, `marketCapMoreThan=2000000000`, `isEtf=false`, `isFund=false`, `isActivelyTrading=true`, `limit=10000`), `profile(symbol)`, `quote(symbols: Sequence[str])` (`batch-quote` or `quote` per symbol; the builder checks which the account serves and records it), `statement(symbol, kind: Literal["income", "balance", "cashflow"], period: Literal["annual", "quarter"], limit: int)`, `balance_as_reported(symbol, limit)`, `estimates(symbol, period: Literal["annual", "quarter"], limit: int)` (quarter uses `limit=40`), `earnings(symbol, limit: int)`, `price_history(symbol, start: date)`. Symbols are converted exchange-form → FMP form (`BRK.B` → `BRK-B`) in this class only.
- `normalize_fmp`: `def statement_facts(payload: Any, symbol: str, dataset: str, response_id: int, observed_at: datetime, entered_at: datetime) -> list[FactRow]` — datasets `income-annual`, `income-quarter`, `balance-annual`, `cashflow-annual`, `cashflow-quarter`; fields read, verbatim from the FMP schema (`docs/legacy/source-evidence.md`, "R1 statement field binding"): income `revenue, operatingIncome, netIncome, eps, epsDiluted, weightedAverageShsOutDil, incomeTaxExpense, incomeBeforeTax`; balance `cashAndCashEquivalents, shortTermInvestments, totalCurrentAssets, totalCurrentLiabilities, shortTermDebt, propertyPlantEquipmentNet, goodwill, intangibleAssets, longTermDebt, totalStockholdersEquity`; cash flow `netCashProvidedByOperatingActivities, netCashProvidedByInvestingActivities, netCashProvidedByFinancingActivities, capitalExpenditure, stockBasedCompensation, netDividendsPaid, commonStockRepurchased, commonStockIssuance`; plus `reportedCurrency`, `fiscalYear`, `period`, `date` as the period end; `as_of` = the period end; a null field → a row with `value=None, missing_reason="null"`; a normalized balance-sheet zero for `goodwill` or `intangibleAssets` → `value=None, missing_reason="vendor-zero"` (D17; the as-reported row decides). `def as_reported_balance_facts(payload, symbol, response_id, observed_at, entered_at) -> list[FactRow]` — dataset `balance-asreported-annual`, fields `intangibles_ex_goodwill` from the first present of the tags `intangibleassetsnetexcludinggoodwill`, `finitelivedintangibleassetsnet`, `otherintangibleassetsnet` (kind `estimate`, method `bs10-intangibles-total-v1`), `lease_rou_asset` from `operatingleaserightofuseasset`, `current_lease_liability` from `operatingleaseliabilitycurrent`; absent tag → `value=None, missing_reason="not-presented"`. `def estimate_observations(payload, symbol, period: Literal["annual", "quarter"], ...) -> list[ObservationRow]` — dataset `estimate-annual`/`estimate-quarter`, period = the row's `date`, fields `eps_avg, revenue_avg, net_income_avg, analysts_eps, analysts_revenue, analysts_net_income, fiscal_year, fiscal_period` (FMP: `epsAvg, revenueAvg, netIncomeAvg, numAnalystsEps, numAnalystsRevenue`; the builder confirms the net-income count field name and records the mapping in the module docstring). `def earnings_observations(payload, ...) -> list[ObservationRow]` — dataset `street-actual` (`eps_actual` per past `date`) and `earnings-date` (the next `date` with `epsActual` null; field `next_date`). `def quote_observations(payload, ...)`: dataset `quote`, fields `price, market_cap, shares_outstanding, year_high, year_low`. `def price_closes(payload) -> list[tuple[date, float]]`. `def screener_rows(payload) -> list[ScreenerRow]` with `symbol, name, exchange, sector, industry, country, currency, market_cap, is_etf, is_fund, is_actively_trading, is_adr` (FMP `isAdr` where present, else `False`).

- [ ] **Step 1: Write the failing tests** — for each normalizer, from the fixtures: field count and one value per dataset; `test_vendor_zero_goodwill_becomes_not_presented`; `test_as_reported_tag_search_order`; `test_screener_rows_symbol_forms` (`BRK-B` in payload → `BRK.B` in the row); for `Fmp`: `test_requests_carry_apikey_and_converted_symbol` with `MockTransport` asserting the request URL has `symbol=BRK-B` and `apikey=`; `test_quarter_estimates_use_limit_40`.
- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the FMP adapter and its normalizer"`.

---

### Task 16: The GuruFocus adapter and its normalizer

**Files:**
- Create: `src/fairband/vendors/gurufocus.py`, `src/fairband/vendors/normalize_gf.py`, `tests/vendors/test_gurufocus.py`, `tests/fixtures/gurufocus/*.json`

**Interfaces:**
- `gurufocus`: `class GuruFocus` with `__init__(self, http: VendorHttp, token: str)`; base URL `https://api.gurufocus.com/public/user/{token}`; `summary(symbol) -> VendorResponse`, `keyratios(symbol) -> VendorResponse`. Symbols stay in exchange form (`BRK.B`).
- `normalize_gf`: `def num(value: Any) -> Decimal | None` — accepts numbers and numeric strings; returns `None` for `None`, `""`, `"-"`, `"N/A"` and anything that does not parse. `def summary_observations(payload, symbol, response_id, observed_at, entered_at) -> list[ObservationRow]` — dataset `gf-score`, fields `moat_score`, `z2score`, `depositary_receipt_ratio` from `summary.company_data`. `def keyratios_observations(...)` — dataset `gf-ratio`, fields `eps_ttm` from `"EPS (TTM)"` and `eps_without_nri` from `"EPS without NRI"`, searched across the response's categories (the key sits under a category dict; search every category).

- [ ] **Step 1: Write the failing tests**

```python
def test_summary_string_numbers_and_dashes():
    rows = summary_observations({"summary": {"company_data": {"moat_score": "7", "z2score": "-", "depositary_receipt_ratio": None}}}, "X", 1, now, now)
    by = {r.field: r.value for r in rows}
    assert by["moat_score"] == Decimal("7") and by["z2score"] is None and by["depositary_receipt_ratio"] is None

def test_keyratios_search_across_categories()
def test_token_only_in_path_and_scrubbed()   # MockTransport sees /public/user/T0K3N/stock/AAPL/summary; VendorResponse.url has <key>
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the GuruFocus adapter and its normalizer"`.

---

### Task 17: Fetch one company with freshness reuse

**Files:**
- Create: `src/fairband/refresh/__init__.py`, `src/fairband/refresh/fetch.py`, `tests/refresh/test_fetch.py`, `tests/refresh/conftest.py` (a `MockTransport` router that serves the Task 15/16 fixtures by path, counting calls per endpoint)

**Interfaces:**
- `@dataclass(frozen=True) class FetchOutcome: symbol: str; calls: int; reused: int; failed: tuple[str, ...]; error: str | None`
- `def fetch_company(conn, fmp: Fmp, gf: GuruFocus | None, symbol: str, policy: Policy, now: datetime, force: bool = False) -> FetchOutcome` — the endpoint set per company: `income annual 11`, `balance annual 11`, `cashflow annual 11`, `income quarter 8`, `cashflow quarter 8`, `balance_as_reported 11`, `profile`, `quote`, `price_history 5y`, `estimates annual 6`, `estimates quarter 40`, `earnings 12`, `gf summary`, `gf keyratios`. For each: skip when `latest_response` for the same `(provider, endpoint, symbol, params)` is newer than `reuse_hours` (`gf_reuse_days` for GuruFocus) unless `force`; else call, `record_response` (payload scrubbed), normalize and insert the facts/observations in the same transaction as the response row. A `VendorError` on one endpoint records the response row with `error` and continues with the others; `failed` lists the endpoints; `error` is set when any required endpoint failed (the three annual statements, quote, estimates quarter). When `gf` is `None` (no GuruFocus key) the two GuruFocus endpoints are recorded as failed with error `"no GuruFocus key"` and the fetch continues.

- [ ] **Step 1: Write the failing tests**

```python
def test_fetches_all_endpoints_and_stores(conn, clients, policy):   # 14 calls; facts_for income-annual has rows; observations gf-score has moat_score
def test_reuses_within_24h(conn, clients, policy):                  # second fetch_company: calls == 0, reused == 14
def test_gf_reused_for_7_days(conn, clients, policy):               # now + 2 days: FMP refetched (12 calls), GF reused (2)
def test_endpoint_failure_recorded_and_continues(conn, clients_with_500_on_quote, policy):   # failed == ("quote",), error set, other datasets stored
def test_missing_gf_key_marks_gf_failed(conn, clients_no_gf, policy)
def test_no_key_in_stored_params_or_payload(conn, clients, policy)  # grep every vendor_responses row for the fake key
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the per-company fetch with freshness reuse"`.

---

### Task 18: Assemble the engine inputs from the store

**Files:**
- Create: `src/fairband/refresh/inputs.py`, `tests/refresh/test_inputs.py`

**Interfaces:**
- `def series_for(conn, symbol: str) -> Series` — the fiscal-year series below, on its own so Task 23 can build deciles without the rest.
- `def build_inputs(conn, symbol: str, policy: Policy, tax: TaxTable, today: date) -> CompanyInputs` — reads `latest_company`, the facts and observations, and builds every field of `CompanyInputs`:
  - `series`: one `FiscalYear` per `income-annual` period joined to `cashflow-annual` by `period_end`, oldest first, at most the last 11.
  - `capital_years`: one `CapitalYear` per annual balance period (at most 11), joined to `income-annual` for `operating_income` and to `balance-asreported-annual` for `intangibles` (the as-reported estimate when present; else the normalized `intangibleAssets` when it is not `vendor-zero`; else `None`), `lease_rou_asset`, `current_lease_liability`; `cash_and_investments = cashAndCashEquivalents + shortTermInvestments`; `goodwill` likewise from normalized unless `vendor-zero`; `tax_rate` from `tax.rate_for(country, fiscal_year)`; an estimate rate adds flag `tax-carried-forward`; a `None` rate for any needed year sets `refusal = f"no statutory tax rate for {country} {year}"`.
  - `trailing`: the last four `income-quarter` and `cashflow-quarter` periods when they are consecutive (each period end 80–100 days after the previous) → sums, `on_fiscal_year=False`; else the last fiscal year's values with `on_fiscal_year=True` and flag `trailing-on-fiscal-year`.
  - `shares_diluted`: the latest quarter's `weightedAverageShsOutDil`, else the latest annual.
  - `quarter_estimates`, `annual_estimates`, `street_ttm_eps` (sum of the last four `street-actual` values whose periods match the trailing quarters; else `None`), `moat_score`, `gf_eps_ttm`, `gf_eps_without_nri`, `next_earnings`, `closes`, `price` and `price_date` from `quote`, `market_cap`, `is_adr`, `currency` = the latest annual income statement's `reportedCurrency`.
  - `provenance`: one `Provenance` per input name (source `"FMP <endpoint>"` or `"GuruFocus <endpoint>"`, `as_of`, `observed_at`, `entered_at` from the rows).
  - `data_date`: the newest `observed_at` across the statements, as a date.

- [ ] **Step 1: Write the failing tests** (from rows inserted by the Task 17 fixtures)

```python
def test_builds_series_and_capital_years(conn_with_company)        # 11 years, oldest first; intangibles from the as-reported estimate; vendor-zero goodwill → None
def test_trailing_from_four_consecutive_quarters(conn_with_company)
def test_trailing_falls_back_when_quarters_not_consecutive(conn_with_gap)   # on_fiscal_year True, flag present
def test_tax_rate_estimate_flag_and_refusal(conn_with_company, tax_table_without_2025)   # flag tax-carried-forward; a country absent → refusal text
def test_provenance_dates(conn_with_company)                          # provenance["ntm_eps"].source == "FMP analyst-estimates"
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Assemble the engine inputs from the store"`.

---

### Task 19: The refresh runner and the one-ticker command

**Files:**
- Create: `src/fairband/refresh/run.py`, `tests/refresh/test_run.py`; modify `src/fairband/__main__.py` (`refresh` subcommand)

**Interfaces:**
- `@dataclass(frozen=True) class Progress: refresh_id: int; stage: str; done: int; failed: int; remaining: int; current: str | None`
- `class Refresh` with `__init__(self, conn_factory: Callable[[], sqlite3.Connection], fmp: Fmp | None, gf: GuruFocus | None, policy: Policy, tax: TaxTable, clock: Callable[[], datetime], cancel: threading.Event, on_progress: Callable[[Progress], None] | None = None)` and `def run(self, kind: Literal["full", "price", "scoped"], symbols: Sequence[str] | None = None) -> int`. `run` raises `MissingKey("fmp")` before any work when `fmp` is `None`. This task implements `scoped` only: stages `fetch` → `value` → `done`; for each symbol, `fetch_company` (4 workers, each with its own connection from `conn_factory`), then `build_inputs`, `value_company(inputs, latest_deciles(conn), policy, today)`, `insert_snapshot`; a symbol whose fetch `error` is set or whose assembly raises gets `refusal_result(symbol, "data fetch failed: <endpoints>", ...)` with whatever price the store holds; `upsert_item` per symbol; the cancel event is checked before each symbol; `finish_refresh` with `done`, `cancelled` or `failed` (an exception outside per-symbol work). `record_policy` at start. One `running` refresh at a time: `create_refresh` raises `RefreshRunning` when `current_refresh` exists.
- `python -m fairband refresh AAPL,MSFT`: loads settings, keys, policy and tax, migrates, builds clients, runs a scoped refresh, prints one line per symbol (`AAPL  Mature Growth  value 189.40  stance HOLD` or `AAPL  —  no universe deciles yet`).

- [ ] **Step 1: Write the failing tests**

```python
def test_scoped_refresh_without_deciles_writes_refusal_snapshots(env)   # two fake symbols → two snapshots, refusal "no universe deciles yet", items valued
def test_scoped_refresh_with_stored_deciles_values(env_with_deciles)    # value present for the Mature Growth fixture company
def test_stop_after_first_then_continue(env):                           # cancel set by on_progress after symbol 1 → status cancelled, 1 snapshot; second run: symbol 1 reused (0 calls), symbol 2 fetched
def test_fresh_company_not_fetched_again(env)
def test_failing_company_gets_refusal_row(env_with_500_for_B)           # "data fetch failed: ..." snapshot; refresh done
def test_second_refresh_refused_while_running(env)
def test_cli_refresh_prints_rows(env, capsys)
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the refresh runner and the one-ticker command"`.

---

### Task 20: The web server, the screen API and the page

**Files:**
- Create: `src/fairband/web/__init__.py`, `src/fairband/web/app.py`, `src/fairband/web/static/index.html`, `src/fairband/web/static/app.js`, `src/fairband/web/static/design-system/` (unpack `tokens/`, `fonts/`, `components/` from `docs/design-system/fairband-design-system_2.tar.gz`; keep the two font licence files), `src/fairband/web/static/vendor/react.production.min.js`, `react-dom.production.min.js` (from the archive's `previews/vendor/`), `tests/web/test_app.py`; modify `pyproject.toml` (Hatch includes `src/fairband/web/static/**`), `src/fairband/__main__.py` (`serve`)

**Interfaces:**
- `def create_app(settings: Settings, policy: Policy, conn_factory, worker: "RefreshWorker | None" = None, clock=utcnow) -> FastAPI`.
- `GET /` → `index.html`. `GET /static/{path}` → files via `importlib.resources`.
- `GET /api/screen?sort=<column>&dir=asc|desc` → `{"rows": [...], "columns": [...], "refresh": {...}}`; a row: `symbol, name, sector, cap_band, market_cap, phase (1–6 or null), phase_name, fair_low, fair_high, fair_value, buy_level, trim_level, mechanical, reviewed (null), overrides (0), price, stance3, stance5, moat, implied_growth, expected_return, epv, pe_reported, pe_clean, pe_forward, high_52w, low_52w, change_1y, change_3y, change_5y, drawdown, flags (list of words), refusal, price_date, data_date, valid_until, entered_at, freshness`; numbers as JSON numbers (floats from the stored decimal text); default sort `symbol asc`; rows with a null sort key last; `freshness` from `validity_state` with the server clock.
- `GET /api/companies/{symbol}` → the latest snapshot's full `ValuationResult` as JSON plus the company row.
- `index.html`: the three stylesheets, the two React scripts, `design-system/components/bundle.js`, then `app.js`. `app.js` (no JSX): fetches `/api/screen`, renders `Fairband.ScreenTable` with `columns` from `localStorage["fairband.columns"]` (fallback `Fairband.DEFAULT_COLUMNS`) and `onColumnsChange` persisting it; header click re-fetches with `sort`/`dir`; row click opens a drawer (Task 21); a footnote with the row count and `"$2 bn and up"`.
- `python -m fairband serve --port` runs migrations, builds the app and starts Uvicorn on `127.0.0.1`.

- [ ] **Step 1: Write the failing tests** (FastAPI `TestClient`, a temp database with two snapshots inserted through the store)

```python
def test_index_and_static_served(client):          # 200 for /, /static/design-system/tokens/tokens.css, /static/design-system/fonts/ibm-plex-mono-latin-400-normal.woff2, /static/vendor/react.production.min.js, /static/design-system/components/bundle.js
def test_screen_rows_and_default_sort(client)      # two rows, sorted by symbol; mechanical == value; reviewed is None
def test_screen_sort_nulls_last(client)            # sort=fair_value desc → the refused row last
def test_freshness_states(client_with_clock)
def test_company_detail(client)                    # /api/companies/AAPL → result.route, inputs list, intermediates keys
def test_unknown_company_404(client)
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the web server, the screen API and the page"`. Check by hand: `uv run python -m fairband serve`, open `http://127.0.0.1:8470/`, the table renders with the vendored fonts (disconnect the network to confirm).

---

### Task 21: The detail drawer and the extra columns

**Files:**
- Modify: `src/fairband/web/static/app.js`, `src/fairband/web/static/design-system/components/bundle.js` (the repository's copy; add column definitions), `src/fairband/web/static/index.html`; `tests/web/test_app.py`

**Interfaces:**
- Columns added to the bundle's `ScreenTable` definitions, keys matching the API row fields: `sector, cap_band, market_cap, moat, implied_growth, expected_return, epv, pe_reported, pe_clean, pe_forward, high_52w, low_52w, change_1y, change_3y, change_5y, drawdown, flags, refusal, price_date, data_date, valid_until`. Numeric columns use `figure` and right-align; percentages one decimal with `%`; money through `Fairband.formatMoney`; dates through `Fairband.formatDate`; `flags` as the words joined by `·`.
- The drawer (`app.js`): a `detail-rail`-wide panel composed of design-system components: header (ticker, name, `PhaseBadge`), `BandMeter` (when a value exists), `ValidityWindow` (`asOf=data_date`, `observedAt`, `enteredAt`, `validFrom=data_date`, `validUntil`, `today` from the API), the classifier evidence as a two-column list, the inputs table (name, tag, value, unit, source, as of, observed, entered), the intermediates as grouped key/value lists, the flags with their sentences, the refusal reason in `caution` when present, and the policy and method versions in `caption`.
- `GET /api/screen` gains `"today"` (ISO) in the envelope for the drawer.

- [ ] **Step 1: Write the failing test** — `test_screen_envelope_has_today(client)`; `test_bundle_has_extra_columns()` reads `bundle.js` and asserts each new key appears in a `key: '<name>'` column definition.
- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the detail drawer and the extra screen columns"`. Check by hand: click a row, the drawer shows the inputs with three dates each.

---

### Task 22: The universe

**Files:**
- Create: `src/fairband/refresh/universe.py`, `tests/refresh/test_universe.py`, `tests/fixtures/fmp/screener.json` (synthetic: an eligible common stock on each exchange, an OTC listing, a bank, a REIT, a preferred `-PA`, a warrant `-WS`, a market cap below the floor, an ETF, an ADR with `isAdr: true`, a duplicate symbol)

**Interfaces:**
- `@dataclass(frozen=True) class UniverseResult: refresh_id: int; admitted: tuple[str, ...]; excluded: dict[str, int]` (exclusion reason → count).
- `def build_universe(conn, fmp: Fmp, policy: Policy, refresh_id: int, now: datetime) -> UniverseResult` — one screener call (reused within `reuse_hours`), `screener_rows`, then per row in order: exchange not in `policy.universe.exchanges` → skip silently; `is_etf` or `is_fund` or not actively trading → skip silently; `market_cap < cap_floor` → skip silently; industry in `excluded_industries` → insert with `eligible=0, exclusion_reason="industry: <industry>"`; symbol matches an exclude pattern or is in `manual_exclusions` → insert with `eligible=0, exclusion_reason="symbol pattern"`; else insert with `eligible=1`, `cap_band` from `cap_bands`; duplicates keep the first. `is_adr` and `country` and `currency` from the row.

- [ ] **Step 1: Write the failing tests** — `test_admits_and_excludes_each_fixture_case`, `test_cap_bands`, `test_duplicate_symbol_kept_once`, `test_screener_reused_within_24h`.
- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the universe build"`.

---

### Task 23: The full refresh with deciles, workers, continuation and the API

**Files:**
- Create: `src/fairband/refresh/deciles.py`, `src/fairband/refresh/worker.py`; modify `src/fairband/refresh/run.py`, `src/fairband/web/app.py`, `src/fairband/__main__.py`; tests `tests/refresh/test_run_full.py`, `tests/web/test_refresh_api.py`

**Interfaces:**
- `deciles.py`: `def deciles_for_universe(conn, symbols: Sequence[str], refresh_id: int) -> Deciles` — builds each symbol's `Series` through the Task 18 series builder (factor `series_for(conn, symbol) -> Series` out of `inputs.py`) and calls `compute_deciles`.
- `run.py`: `kind="full"` stages `universe` → `fetch` (all admitted, 4 workers) → `deciles` (`save_deciles`) → `value` (every admitted symbol) → `done`; the calibration dict `{"phases": {name: count}, "flagged": n, "refused": {reason: count}, "valued": n, "total": n}` saved with `finish_refresh`. A symbol fetched within `reuse_hours` is not fetched again, so a rerun after a stop continues with the rest. Startup hook: `mark_interrupted`.
- `worker.py`: `class RefreshWorker` with `__init__(self, make_refresh: Callable[[threading.Event, Callable[[Progress], None]], Refresh])`, `start(self, kind, symbols) -> int` (raises `RefreshRunning`), `cancel(self) -> None`, `status(self) -> Progress | None`; one daemon thread; progress held in memory and mirrored to `refreshes.stage` and `refresh_items`.
- API: `POST /api/refresh` body `{"kind": "full"|"price"|"scoped", "symbols": [...]?}` → `{"refresh_id": n}` or 409 `{"running": n}`; `GET /api/refresh/current` → the `Progress` or `{"refresh": null, "last": {...}}` with the last refresh's status, finish time and calibration; `POST /api/refresh/cancel` → 200. The app's startup event calls `mark_interrupted`.
- `python -m fairband refresh` with no symbols runs a full refresh in the foreground and prints progress lines and the calibration.

- [ ] **Step 1: Write the failing tests**

```python
def test_full_refresh_builds_universe_deciles_and_values(env_fixture_universe)   # 6 fixture companies: deciles row saved; every admitted symbol has a snapshot; the Mature Growth company has a value; calibration counts sum to total
def test_rerun_after_cancel_continues(env_fixture_universe)                      # cancel after 2 fetched → cancelled; rerun → 4 fetched (2 reused), done
def test_startup_marks_interrupted(env)
def test_api_start_status_cancel(client_with_worker)
def test_api_refuses_second_refresh(client_with_worker)   # 409
def test_cli_full_refresh_prints_calibration(env_fixture_universe, capsys)
```

- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the full refresh with deciles, workers and continuation"`.

---

### Task 24: The price refresh, the group view and the calibration on the page

**Files:**
- Modify: `src/fairband/refresh/run.py` (`kind="price"`), `src/fairband/web/app.py` (`GET /api/groups`), `src/fairband/web/static/app.js`, `index.html`; create `tests/refresh/test_run_price.py`, `tests/web/test_groups.py`

**Interfaces:**
- Price refresh: stage `quotes` (one batch quote call per 100 symbols, or per symbol where the account serves no batch; `quote_observations` stored) → `reprice` each latest snapshot with the new price and `price_date`, `insert_snapshot` with the new `refresh_id` → `done`. Snapshots with `value=None` are copied with the new price only.
- `GET /api/groups?by=sector|phase|cap` → `{"by": ..., "groups": [{"name", "count", "valued", "median_price_to_value", "share_below_buy"}]}` — medians and shares over rows with a value; `null` when none.
- Page: a tab bar `Screen | Groups`; the Groups tab is one plain table with a `by` selector; the refresh controls (buttons `Refresh prices`, `Refresh all`, `Cancel`; progress line; the last calibration as one `caption` line: `"1,812 companies · 1,540 valued · phases: …"`) in the page's top bar; during a refresh the old rows stay at `ink-faint`.

- [ ] **Step 1: Write the failing tests** — `test_price_refresh_keeps_value_updates_stance`, `test_price_refresh_copies_refused_rows`, `test_groups_by_phase_median_and_share`, `test_groups_null_when_no_values`.
- [ ] **Step 2–5:** fail, implement, pass, commit `"Add the price refresh, the group view and the calibration line"`. Check by hand: run `Refresh all` against the live vendors with real keys, let it finish or stop it once and start it again, confirm the calibration line, open AAPL and MSFT, confirm the drawer's arithmetic reproduces the value.

---

## Self-review notes

- Spec coverage: 6.1 → Task 22; 6.2 → Tasks 17, 19, 23, 24; 6.3 → Tasks 20, 21, 24; 6.4 → Task 21; 6.5 → Tasks 15, 16, 17, 18; 6.6 → Tasks 5–11, 18; 6.7 → Task 10; 6.8 → Tasks 4, 11; 6.9 → Tasks 12, 13; 6.10 → Tasks 20, 23; 6.11 → Task 1; 7.1–7.3 → Tasks 6, 7; 7.4 → Task 5; 7.5 → Task 4; 7.6 → Task 11; 7.7 → Tasks 15, 16; 7.8 → Tasks 14, 17; 7.9 → Tasks 19, 23; 7.10 → Task 12; section 11 → Task 11; goal 7 → Tasks 23, 24.
- The live smoke test the spec names (7.7) is the hand check at the end of Tasks 20 and 24; it is not automated.
- `series_for` is introduced in Task 18 and reused in Task 23; `levels_for`, `stance5`, `validity_state` from Task 4 are used in Tasks 11 and 20; `Deciles` from Task 5 is stored by Task 13 and read by Tasks 19 and 23.
