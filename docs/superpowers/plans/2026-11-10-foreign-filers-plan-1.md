# Foreign filers, plan 1: the reporting currency and the listed-share basis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build sections 6, 7 and 9 of the foreign filers spec (B-28, plan 1): value the 192 rows the screen refuses as foreign filers, in their reporting currency with the policy's nominal rates restated by the inflation differential, on FMP's listed-share basis, the value and the levels translated to USD per ADS at FMP's exchange rate.

**Architecture:** A new packaged table of expected inflation by currency (`policy/inflation.py`, built by a script from the IMF datamapper) and policy v11. A new dataset, the pair's daily rate history, fetched in a `rates` stage of a full or scoped refresh and read by `refresh/rates.py`; a price refresh quotes the pairs. The split rule (`refresh/inputs_splits.py`) gains the ADR ratio as a candidate factor, period by period. Assembly (`refresh/inputs.py`) brings the street actuals and GuruFocus's EPS into the currency and hands the engine the rate and the differential; `engine/route.py` wraps the routes: the price and the market cap into the currency, the policy restated, the value and the levels back to USD. The words follow: units, the company read, the drawer, the report page, the Methodology page, the playbook.

**Tech Stack:** Python 3.13, uv, pytest, mypy, ruff; TOML tables; the playbook's Markdown.

**Spec:** `docs/superpowers/specs/2026-11-10-foreign-filers-design.md`, sections 1 to 7, 9 to 16 (section 8 is plan 2).

## Global Constraints

- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- `docs/method.md` changes in the same commit as the engine or the refresh behaviour it describes; the Methodology page (`src/fairband/web/static/methodology.html`) with it. Where documents disagree, `docs/method.md` describes what runs.
- Method version `fairband-mechanical/1.1` (`fairband.engine.METHOD_VERSION`) and policy `fairband-policy-v11` from Task 1 on; v10 stays in the package byte for byte.
- Never print, log, store or commit a key; never commit vendor data; test fixtures are synthetic or hand-trimmed. The exchange-rate fixtures below are made up; the inflation table is derived from public IMF projections and is committed, the datamapper JSON it is built from is not.
- Commit messages: one plain sentence in the imperative, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` (the implementer's model).
- Every domestic row keeps its figures bit for bit: the six goldens (`tests/fixtures/golden`) are unchanged, which `tests/engine/test_golden.py` asserts; every rule below is conditioned on the currency, the ADR ratio or a period in another currency. The one deliberate move on a domestic row is BVC's, on the live data (spec 13), not in any fixture.
- No subagent dispatches another subagent; review arrives from the controller.
- The spec's section 5 table is the unit of every vendor field. Do not apply the ADR ratio to FMP's figures; they are per ADS on file.

## Review Focus

1. A company reporting in USD with the ADR flag (48 rows): no rate input, no differential, no restated policy, valued exactly as a domestic row; pinned in Task 4.
2. A currency with no pair response on file (a vendor failure on the `rates` stage): the company is refused "no exchange rate for <code>" and every other company is valued; pinned in Task 2.
3. A price refresh whose pair quote fails: the reprice at the snapshot's stored rate with `fx-stale` once the rate is older than the bound; pinned in Task 2.
4. A row with both a pending split and a basis factor: each sentence names its own scaling and the counts agree; pinned in Task 3.
5. An override on a foreign filer at a figure inside the USD range but outside the currency's, and the other way round; pinned in Task 4.

---

### Task 1: Policy v11, the inflation table and its script

**Files:**
- Create: `src/fairband/policy/fairband-policy-v11.toml` (a copy of v10 with the changes below), `src/fairband/policy/inflation.py`, `src/fairband/policy/inflation-imf-weo-v1.toml`, `scripts/build_inflation_table.py`
- Modify: `src/fairband/policy/__init__.py` (`_POLICY_FILE`, the `Policy` fields, `load_policy`), `src/fairband/policy/settings.py` (`check`), `src/fairband/engine/__init__.py` (`METHOD_VERSION`), `pyproject.toml` only if the package data glob does not already include every `*.toml` of the policy package (check `tool.hatch` or the equivalent; it does for the tax tables)
- Modify: `docs/method.md` 4.1 (the table rows for `inflation_max`, `fx_stale_days`, `refresh.fx_history_years` and the inflation table, in the policy-values table and its text), 4.1a if a constant is added, 11 (the 1.1 row: the sentence below), 12 (the IMF row), the version lines at the top (1.1, v11)
- Test: `tests/policy/test_policy.py`, `tests/policy/test_inflation.py` (new), `tests/test_method_doc.py` if it pins the version lines

**Interfaces:**
- Produces: `Policy.inflation_max: float`, `Policy.fx_stale_days: int`, `RefreshValues.fx_history_years: int` (the nested refresh values' dataclass, whatever its name in `policy/__init__.py`), read from `[values.inflation_max]`, `[values.fx_stale_days]` and `[values.refresh.value].fx_history_years`; `check` refuses `inflation_max` outside (0, 1), `fx_stale_days` below 1, `fx_history_years` below 1, each with the setting-style sentence ("inflation_max: must be above 0 and below 1").
- Produces: in `policy/inflation.py`:

```python
INFLATION_FILE = "inflation-imf-weo-v1.toml"

@dataclass(frozen=True)
class Inflation:
    currency: str          # ISO 4217, "TWD"
    economy: str           # the WEO's code, "TWN"
    years: tuple[int, ...] # the projection years, (2027, 2028, 2029, 2030, 2031)
    rates: tuple[float, ...]  # fractions, one per year
    @property
    def mean(self) -> float: ...

class InflationTable:
    source: str; vintage: str; retrieved: str
    def rate_for(self, currency: str) -> Inflation | None: ...
    def differential(self, currency: str) -> float | None:
        """(1 + π_currency) ÷ (1 + π_USD) − 1 on the means; 0.0 for USD; None for a currency
        the table lacks."""

def load_inflation_table(path: Path | None = None) -> InflationTable: ...
```

- Produces: the TOML shape, which the script writes and the loader checks (a currency twice, a rate count that is not the years' count, a rate outside [−0.5, 5], a missing `[meta]` field each raise `ValueError` naming the currency or the field):

```toml
# Expected inflation by currency: the IMF World Economic Outlook's projections of consumer price
# inflation for the five years after the retrieval's year, as fractions (spec 2026-11-10 7.3).
# Generated by scripts/build_inflation_table.py from the datamapper's JSON; edit the script.
[meta]
source = "IMF World Economic Outlook, October 2026: inflation, average consumer prices (PCPIPCH), annual percent change"
url = "https://www.imf.org/external/datamapper/api/v1/PCPIPCH"
vintage = "October 2026"
retrieved = "2026-11-10"
years = [2027, 2028, 2029, 2030, 2031]

[[currencies]]
code = "USD"
economy = "USA"
rates = [0.028, 0.021, 0.019, 0.019, 0.019]
```

- Produces: `scripts/build_inflation_table.py <json> <toml> [--years 2027-2031] [--retrieved YYYY-MM-DD]`, modelled on `scripts/build_tax_table.py`: reads the datamapper JSON saved outside the repository (the `PCPIPCH` response, `{"values": {"PCPIPCH": {"USA": {"2027": 2.8, ...}}}}`), takes the vintage from the `indicators` endpoint's `source` field when a second JSON is given with `--indicators`, else from `--vintage`; the currency-to-economy map is a constant in the script, these pairs at least: USD USA, EUR EURO, GBP GBR, JPY JPN, CAD CAN, CNY CHN, HKD HKG, TWD TWN, KRW KOR, INR IND, SGD SGP, AUD AUS, NZD NZL, CHF CHE, SEK SWE, NOK NOR, DKK DNK, PLN POL, CZK CZE, HUF HUN, ILS ISR, AED ARE, SAR SAU, QAR QAT, KWD KWT, ZAR ZAF, BRL BRA, MXN MEX, ARS ARG, CLP CHL, COP COL, PEN PER, TRY TUR, IDR IDN, PHP PHL, THB THA, MYR MYS, VND VNM, KZT KAZ, EGP EGY, NGN NGA, RUB RUS; a currency whose economy lacks a year is left out with a line on stderr naming it; the written file is loaded back through `load_inflation_table` before the script reports.
- Produces: `METHOD_VERSION = "fairband-mechanical/1.1"`.

- [ ] **Step 1: Write the failing tests**

In `tests/policy/test_inflation.py`:

```python
def test_the_table_loads_every_currency_of_the_universe() -> None:
    t = load_inflation_table()
    for code in ("USD", "CAD", "EUR", "CNY", "BRL", "GBP", "MXN", "KRW", "ZAR", "JPY", "TWD", "ARS", "INR", "VND", "TRY", "PHP", "SEK", "COP", "CLP", "DKK", "KZT", "CHF", "IDR"):
        found = t.rate_for(code)
        assert found is not None and found.years == (2027, 2028, 2029, 2030, 2031) and len(found.rates) == 5
    assert t.vintage == "October 2026" and "PCPIPCH" in t.source


def test_the_means_and_the_differentials() -> None:
    """Spec 11.1 on the packaged table, to three decimals of a percent."""
    t = load_inflation_table()
    assert t.rate_for("USD").mean == pytest.approx(0.02120, abs=5e-6)
    assert t.rate_for("TWD").mean == pytest.approx(0.01600, abs=5e-6)
    assert t.differential("USD") == 0.0
    assert t.differential("TWD") == pytest.approx(-0.00509, abs=5e-6)
    assert t.differential("JPY") == pytest.approx(0.0, abs=5e-6)
    assert t.differential("BRL") == pytest.approx(0.01097, abs=5e-6)
    assert t.differential("CHF") == pytest.approx(-0.01351, abs=5e-6)
    assert t.differential("KZT") == pytest.approx(0.04034, abs=5e-6)
    assert t.rate_for("ARS").mean == pytest.approx(0.12120, abs=5e-6)
    assert t.rate_for("TRY").mean == pytest.approx(0.18480, abs=5e-6)
    assert t.differential("XXX") is None and t.rate_for("XXX") is None


def test_a_bad_table_is_refused(tmp_path: Path) -> None:
    # a currency twice; four rates for five years; a rate of 6.0; no vintage: each raises
    # ValueError naming the currency or the field
```

And a round-trip test of the script: write a small datamapper JSON (three economies, the five years) to `tmp_path`, run `build_inflation_table.main([...])` (expose a `main(argv)`), load the written file, assert the rates are the JSON's ÷ 100 and a currency whose economy lacks 2031 is absent.

In `tests/policy/test_policy.py`: v11 loads with `version == "fairband-policy-v11"`, `inflation_max == 0.10`, `fx_stale_days == 7`, `refresh.fx_history_years == 3`; v10's file is byte-identical under its recorded hash (extend the existing hash-pinning test as the v10 round did); `check` refuses each of the three out of range.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/policy -q`
Expected: FAIL (no `fairband.policy.inflation`, v10 still loaded).

- [ ] **Step 3: Build the table and the script, then the policy**

Save the datamapper JSON outside the repository (for example `~/.local/share/fairband/sources/imf-pcpipch-2026-11-10.json`, fetched from the `url` above with `curl`; the `indicators` endpoint beside it) and run the script to write `inflation-imf-weo-v1.toml`. Write `inflation.py` on the shape of `tax.py`. Copy v10 to v11, set `[meta] version`, add the two values with source lines quoting spec 2026-11-10 section 9 and the `fx_history_years` line in the refresh table; point `_POLICY_FILE` at v11; add the fields and the checks; bump `METHOD_VERSION`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/policy tests/engine/test_golden.py -q`
Expected: PASS; the goldens still pass, since their version fields are masked.

- [ ] **Step 5: The method document**

`docs/method.md`: the two version lines at the top; 4.1's table gains four rows (the three values, no setting, each with its source; the table's row naming the file, its vintage and the rule of 7.3 in one sentence); 11 gains the 1.1 row: "1.1, policy v11 | 2026-11-10 | Foreign filers (spec 2026-11-10). A company reporting in another currency is valued in that currency ... [one paragraph summarising sections 6 and 7 of the spec; write it in full here, the later tasks only amend their sections]"; 12 gains the IMF row and the FMP forex row. Run `uv run pytest tests/test_method_doc.py -q`.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/policy scripts/build_inflation_table.py src/fairband/engine/__init__.py docs/method.md tests/policy
git commit -m "Add policy v11 with the inflation bound, the stale-rate bound and the rate history depth, the IMF inflation table and its build script, and step the method to 1.1"
```

---

### Task 2: The exchange rates: the dataset, the `rates` stage and the price refresh's pairs

**Files:**
- Create: `src/fairband/refresh/rates.py`, `tests/refresh/test_rates.py`, `tests/fixtures/fmp/historical-price-eod-light.USDSEK.json` (made up: about forty rows from 2026-09-01 to 2026-11-05, weekdays, `{"symbol": "USDSEK", "date": "...", "price": 10.5 ± small moves, "volume": 0}`, newest first, with 2026-11-01 at 10.5 and 2026-11-05 at 10.6 exactly, and the four period ends of `synthetic.QUARTERS` at 7.8, 7.9, 8.1 and 8.2 if the fixture is extended back to 2025-09-30, which it should be: spec 11.2's rates), `tests/fixtures/fmp/historical-price-eod-light.USDTWD.json` (a handful of rows)
- Modify: `src/fairband/vendors/fmp.py` (`fx_history`), `src/fairband/vendors/normalize_fmp.py` (`fx_closes`), `src/fairband/refresh/fetch.py` (`_rows` case `"fx-history"`; `provider_of`; the reuse rule for `fx-history` as for the price history), `src/fairband/refresh/run.py` (the `rates` stage in `_full` and `_scoped`; `Progress` unchanged), `src/fairband/refresh/run_price.py` (the `fx` stage and the reprice's rate), `src/fairband/vendors/normalize_fmp_observations.py` (`fx_quote_observations`), `tests/refresh/vendor_double.py` (`historical-price-eod/light` → `fx-history` in `_FMP_ENDPOINTS`; the symbol read from the pair), `tests/refresh/fixture_universe.py` (a SEK company, see below)
- Modify: `docs/method.md` 2 (the rates row and the pairs' quotes row, after the splits row) and 10 (each kind's bullet)
- Test: `tests/vendors/test_fmp.py`, `tests/vendors/test_normalize_fmp.py`, `tests/refresh/test_fetch.py`, `tests/refresh/test_rates.py`, `tests/refresh/test_run_full.py`, `tests/refresh/test_run_price.py`

**Interfaces:**
- Consumes: `policy.refresh.reuse_hours`, `policy.refresh.fx_history_years`, `policy.fx_stale_days` (Task 1).
- Produces: `Fmp.fx_history(self, pair: str, start: date) -> VendorResponse` calling route `historical-price-eod/light` with `{"symbol": pair, "from": start.isoformat()}`; the pairs' quotes go through the existing `Fmp.quote(pairs)` (`quote` for one, `batch-quote` for several; a pair has no dot, so `to_fmp_symbol` leaves it).
- Produces: `fx_closes(payload: Any) -> list[tuple[date, float]]` in `normalize_fmp.py`, oldest first, from rows with a parseable `date` and a positive numeric `price`; the shape of `price_closes`.
- Produces: `fx_quote_observations(payload, pair, response_id, observed_at, entered_at) -> list[ObservationRow]`: dataset `fx-quote`, symbol the pair, field `price`, unit `None`, period and `as_of` the quote's date (its `timestamp`, else the observation day), one row per pair in a batch; none when no row matches the pair.
- Produces: in `refresh/rates.py`:

```python
FX_HISTORY = "fx-history"   # the endpoint name the fetch stores the pair's history under
FX_QUOTE = "fx-quote"       # the price refresh's pair quotes
NO_RATE = "no exchange rate for {code}"

def pair_of(currency: str) -> str: ...   # "USD" + the code; ValueError for "USD" or a code that is not three upper-case letters

@dataclass(frozen=True)
class Rate:
    rate: float      # units of the currency per USD
    date: date       # the close's date
    observed_at: datetime
    stale: bool      # the close is more than fx_stale_days before the date asked for

@dataclass(frozen=True)
class FxSeries:
    currency: str
    closes: tuple[tuple[date, float], ...]   # oldest first; the history's closes and the stored pair quotes, a quote winning on its date
    observed_at: datetime
    def at(self, day: date, stale_days: int) -> Rate | None:
        """The last close at or before ``day``; None without one. ``stale`` when that close is more than ``stale_days`` before ``day``."""
    def mean_at(self, days: Sequence[date], stale_days: int) -> Rate | None:
        """The mean of ``at`` over ``days``; None when any day has none; stale when any is; the date the latest close read."""

def rates_for(conn: sqlite3.Connection, currency: str) -> FxSeries | None:
    """The latest usable fx-history response of the pair, its closes merged with every stored fx-quote observation of the pair; None without a usable history. USD gives a series whose ``at`` is always 1.0 on the day asked, never stale."""

def currencies_of(conn: sqlite3.Connection, symbols: Sequence[str]) -> tuple[str, ...]:
    """The distinct reporting currencies of ``symbols``' newest annual income statements (the newest ``income-annual`` fact's ``currency`` per symbol), USD and None left out, sorted."""

@dataclass(frozen=True)
class RatesOutcome:
    fetched: tuple[str, ...]   # the currencies whose pair was fetched or reused
    calls: int
    reused: int
    failed: tuple[str, ...]    # the currencies whose call failed or gave no close
    rate_limited: bool

def fetch_rates(conn, fmp, currencies, policy, now, secrets, force=False) -> RatesOutcome:
    """One fx-history call per currency, from ``now - fx_history_years`` years; reused within ``reuse_hours`` by provider, endpoint and the pair alone (the ``from`` parameter changes daily, as the price history's does); stored whole as the fetch stores a response (``fetch._store`` with a call whose symbol is the pair), no rows, usable when it gives a close. A 429 stops the loop and sets ``rate_limited``. Never raises for a vendor error."""
```

- Produces: in `run.py`, after `_fetch_pending` in `_full` and `_scoped` and before `_stopped` is consulted: `self._stage(conn, refresh_id, "rates", len(currencies))`, `fetch_rates(...)` with `force` the scoped refresh's, one progress report per currency as `_report(refresh_id, "rates", done, failed, left)`; a 429 here ends the run as a fetch-stage 429 does (`_stopped`'s rule, the message naming FMP). The revalue and the price refresh run no `rates` stage.
- Produces: in `run_price.py`, a stage `fx` between `quotes` and `reprice`: the pairs of the currencies of the quoted symbols' latest snapshots (`result.intermediates.get("currency")`, USD and None left out; before Task 4 no snapshot carries one, so the stage quotes nothing and reports zero), one `Fmp.quote(pairs)` call per `QUOTE_BATCH`, stored as the quote stage stores a batch (endpoint `fx-quote`, symbol `None` for a batch, else the pair; `fx_quote_observations` per pair); a failed call marks no symbol failed. The stage leaves the pairs' quotes in a `dict[str, _Quote]` by currency that the reprice stage will hand to `reprice` in Task 4 (`fx_rate=`, `fx_date=`); in this task the reprice stage calls `reprice` as today.
- Produces: `tests/refresh/fixture_universe.py` gains `KRON`, a copy of ACME's synthetic company whose statements carry `reportedCurrency` `SEK` (a `currency` parameter on `synthetic.bodies`), admitted; its quote ACME's. The full-refresh tests then expect five admitted companies; adjust every count that names four (`test_run_full.py`, `test_run_price.py`, `test_run.py` where they count) and note it in the report.

- [ ] **Step 1: Write the failing tests**

`tests/vendors/test_fmp.py`: `(lambda f: f.fx_history("USDTWD", date(2023, 11, 10)), "historical-price-eod/light", {"symbol": "USDTWD", "from": "2023-11-10"})` in the route parametrization.

`tests/vendors/test_normalize_fmp.py`:

```python
def test_fx_closes_oldest_first_skipping_bad_rows() -> None:
    rows = [{"symbol": "USDSEK", "date": "2026-11-05", "price": 10.6}, {"date": "2026-11-04", "price": "x"}, {"date": "2026-11-01", "price": 10.5}, {"price": 10.0}]
    assert fx_closes(rows) == [(date(2026, 11, 1), 10.5), (date(2026, 11, 5), 10.6)]
    assert fx_closes({}) == [] and fx_closes(None) == []
```

`tests/refresh/test_rates.py` (over the refresh fixtures; the router answers `fx-history` with the USDSEK fixture for the pair `USDSEK`):

```python
def test_at_reads_the_last_close_at_or_before_the_day() -> None:
    s = FxSeries("SEK", ((date(2026, 11, 1), 10.5), (date(2026, 11, 5), 10.6)), NOW)
    assert s.at(date(2026, 11, 5), 7) == Rate(10.6, date(2026, 11, 5), NOW, False)
    assert s.at(date(2026, 11, 4), 7) == Rate(10.5, date(2026, 11, 1), NOW, False)
    assert s.at(date(2026, 11, 10), 7) == Rate(10.6, date(2026, 11, 5), NOW, False)   # 5 days
    assert s.at(date(2026, 11, 13), 7).stale is True                                    # 8 days
    assert s.at(date(2026, 10, 31), 7) is None
    assert s.mean_at([date(2026, 11, 1), date(2026, 11, 5)], 7).rate == pytest.approx(10.55)


def test_rates_for_merges_the_history_and_the_pair_quotes(conn, clients, router, clock, policy) -> None:
    # fetch_rates stores USDSEK; an fx-quote observation on 2026-11-06 at 10.7 is inserted; rates_for("SEK").at(2026-11-06) is 10.7; at(2026-11-05) is the history's 10.6; rates_for("USD").at(any) is 1.0; rates_for("TWD") is None before any fetch


def test_fetch_rates_reuses_within_the_window_and_forces(conn, clients, router, clock, policy) -> None:
    # two calls to fetch_rates(["SEK"]) within 24 h: calls 1 then 0, reused 1; with force=True: 1 again; the stored response's symbol is "USDSEK", its params {"symbol": "USDSEK", "from": "2023-11-01"} (clock 2026-11-01 less three years)


def test_fetch_rates_failure_names_the_currency(conn, clients, router, clock, policy) -> None:
    # router.fail = {"fx-history"}: failed == ("SEK",), rates_for("SEK") is None, nothing raised; a body of "[]" is unusable and failed too
```

`tests/refresh/test_run_full.py`: a full refresh over the five-company universe runs the stages `universe, fetch, rates, deciles, backfill, value, done` in that order (the `progress` events' stages, deduplicated), the `rates` stage with `remaining == 1` at its start (SEK); `router.calls["fx-history"] == 1`; the scoped refresh of KRON fetches the pair again (`force`); a revalue makes no `fx-history` call; `router.fail = {"fx-history"}` leaves KRON refused "no exchange rate for SEK" (Task 4 makes the refusal; here assert the run finishes `done` and the other four are valued).

`tests/refresh/test_run_price.py`: after the full refresh, a price refresh runs `quotes, fx, reprice, done`. Until Task 4 no snapshot names a currency (KRON is still refused as a foreign filer), so pin the stage order and that the `fx` stage reports zero pairs; the pairs' quote, its stored `fx-quote` observation and the failing call are pinned in Task 4 on a KRON snapshot that names SEK. Test the `fx` stage's call and storing directly here on a hand-made snapshot whose intermediates name `"currency": "SEK"` (insert one with `insert_snapshot` on a result whose intermediates are set by `replace`): `router.calls["batch-quote"] == 1` for the pairs (the router serves it from `router.bodies`), the `fx-quote` observation for `USDSEK` with the quote's price and date; with the call failing (`router.fail_once`), the run still ends `done`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/refresh/test_rates.py tests/vendors -q`
Expected: FAIL (no `fx_history`, no `rates` module).

- [ ] **Step 3: Build the adapter route, the normalizer, the rates module, the two stages**

Follow `_calls`/`_store` in `fetch.py` for the storing (a `_Call("fmp", FX_HISTORY, {"symbol": pair, "from": ...}, send)` stored under the pair as the symbol; `_rows` case `"fx-history"`: `([], []) if fx_closes(payload) else None`). `latest_response` for the reuse is called with `{"symbol": pair}` alone, as `_closes` does for the price history: record the `from` in the params but match on the pair (mirror how the price history's reuse works today; if it records `{"symbol": ...}` only, do the same). The `rates` stage reads `currencies_of(conn, fetched.symbols)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/refresh tests/vendors -q`
Expected: PASS.

- [ ] **Step 5: The method document**

`docs/method.md` section 2: two rows after the splits row: "Exchange rates | `historical-price-eod/light` on the pair `USD<code>` | three years (`refresh.fx_history_years`) of daily closes in units of the currency per USD, one call a currency in the `rates` stage, reused for 24 hours, stored whole as the price history is; not required: a company whose currency has no usable history is refused (section 7)" and "Pair quotes | `batch-quote` on the pairs | a price refresh, one call per hundred pairs, stored as `fx-quote` observations". Section 10: the full bullet gains "then the exchange rates of the fetched companies' currencies, one call a currency"; the scoped bullet "its currency's rates again"; the price bullet "the pairs' quotes for the repriced companies' currencies, so the price and the USD value sit on the same day's rate; a pair whose quote fails reprices at the rate the snapshot holds"; the revalue bullet "the rates on file".

- [ ] **Step 6: Commit**

```bash
git add src/fairband/vendors src/fairband/refresh docs/method.md tests
git commit -m "Fetch each reporting currency's daily rate history in a rates stage, quote the pairs in a price refresh, and read a rate at a date"
```

---

### Task 3: The ADR ratio in the split rule's per-period judgment

**Files:**
- Modify: `src/fairband/refresh/inputs_splits.py` (`apply_splits` gains `adr_ratio`; `_basis` and `_judge_periods` the candidate factors; `SplitOutcome` gains `basis_flag` and `refusal`; the notes), `src/fairband/refresh/inputs.py` (`adr_ratio` from the `gf-score` observations; the refusal; `CompanyInputs.adr_ratio`), `src/fairband/engine/route.py` (`CompanyInputs.adr_ratio: float | None = None`; `_base_inputs` gains `data(i, "adr_ratio", i.adr_ratio, "ratio", "adr_ratio")` with the provenance of the GuruFocus summary, value `None` for a direct listing), `docs/method.md` 4.2 (one paragraph after the split basis: the rule of spec 6.1), 8 (the row `basis-scaled`), 9 (the refusal row), 5.12 (`adr_ratio` among every result's inputs)
- Test: `tests/refresh/test_splits.py`, `tests/refresh/test_inputs.py`, `tests/engine/test_route.py` (the base input)

**Interfaces:**
- Consumes: `SplitFigures`, `TrailingPeriod`, `_within`, the period judgment of the split rule as built.
- Produces: `apply_splits(figures, splits, *, statement_end, price_date, quote_market_cap, quote_price, tolerance, adr_ratio: float | None = None) -> SplitOutcome`; `SplitOutcome` gains `basis_flag: Flag | None` (code `basis-scaled`, word "Share basis scaled") and `refusal: str | None` ("share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the ADR ratio 10)"); `estimate_methods` carries `basis-scaled` on `shares_diluted` and `eps_ttm` where the factor applied (a period scaled by both a split and the factor carries `basis-scaled`, the note naming both); the notes' sentences as spec 6.1 gives them. The rule applies only when `adr_ratio` is a number other than 0 and 1 and `quote_market_cap` and `quote_price` are known; otherwise the outcome is the split rule's as built.
- Produces: in `inputs.py`, `adr_ratio` read from the newest `gf-score` observation `depositary_receipt_ratio` (`None` when absent or 0); `CompanyInputs.refusal` takes, in order, the statements' refusal, the split outcome's refusal, then the tax refusal (Task 4 reorders the currency ones in).

- [ ] **Step 1: Write the failing tests**

In `tests/refresh/test_splits.py`, on `_figures()`-style synthetic figures (four quarters, the newest count and EPS per period), with `_apply(..., adr_ratio=...)`:

```python
def test_every_period_a_tenth_of_the_quote_reads_times_ten() -> None:
    """Spec 11.3, CX: counts 145.8 m on every quarter, Q 1,450.8 m, ρ 10."""
    # D reads 1,458.0 m; each period's EPS ÷ 10; the trailing EPS ÷ 10; methods basis-scaled on shares_diluted and eps_ttm; the count's note "×10 to the quote's share basis: the stored count, 145.8 m, is a tenth of the quote's, 1,450.8 m (the ADR ratio 10)"; the EPS note starts "÷10"; basis_flag.sentence names the factor, "every trailing quarter" and the two counts; refusal None; flag (split) None


def test_only_the_newest_period_off_reads_on_one_of_four() -> None:
    """Spec 11.3, UMC: the newest 496.9 m, the older three 2,508.3 m, Q 2,494.4 m, ρ 5."""
    # D 2,484.5 m; the newest EPS ÷ 5, the older as stored; the trailing EPS note ends "on 1 of 4 quarters"; the sentence names the one quarter


def test_the_inverse_ratio_reads_times_three() -> None:
    """TAL: 184.0 m against 608.5 m, ρ 0.3333: f = 1 ÷ ρ."""
    # D == pytest.approx(184.0 * M / 0.3333); the note says "×3" and "three ADSs to one share (the ADR ratio 0.3333)"


def test_a_newest_period_fitting_nothing_is_refused() -> None:
    """KOF: 1,680.7 m against 210.1 m, ρ 10."""
    # refusal == "share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the ADR ratio 10)"; figures unchanged


def test_an_older_period_fitting_nothing_reads_as_stored_and_is_named() -> None:
    # the newest fits f = 1, an older period off by 3: as stored, the sentence names it with its reason


def test_a_ratio_of_one_or_none_leaves_the_split_rule_as_built() -> None:
    # GRFS (ρ 1, 680.6 m against 846.0 m) and WSE (ρ None, 778.9 m against 1,000.3 m): the outcome equals apply_splits without adr_ratio; no basis_flag, no refusal


def test_two_factors_fitting_reads_as_stored() -> None:
    # a synthetic ρ of 1.2 with a count 10% under Q: f = 1 and f = ρ both fit; the newest period: refused ("two factors" is not possible for the newest? — no: spec 6.1 says the newest fitting two is the refusal); an older period: as stored and named


def test_a_pending_split_and_a_factor_each_name_their_own_scaling() -> None:
    # the 2-for-1 SPLIT after END with every count a tenth of Q ÷ 2: the period reads × 2 × 10; both sentences present; the notes name both
```

In `tests/refresh/test_inputs.py`: `build_inputs` on the ACME store with a GuruFocus summary whose `depositary_receipt_ratio` is 10 and a quote at a tenth of ACME's count: `inputs.refusal is None`, `inputs.shares_diluted` scaled, `inputs.adr_ratio == 10.0`; with the ratio 0 or absent, `adr_ratio is None` and nothing scales. In `tests/engine/test_route.py`: every result carries the `adr_ratio` DATA input, `None` with unit `ratio` on the fixtures.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/refresh/test_splits.py -q`
Expected: FAIL (`adr_ratio` unknown).

- [ ] **Step 3: Build it**

Extend `_basis` to try the factors in the order 1, ρ, 1 ÷ ρ for each period, each with the period's split ratio; keep the verdicts as today when `adr_ratio` is None, 0 or 1. The newest period's verdict sets D, S, the refusal; the older periods' verdicts scale or name. The sentences follow the split rule's helpers (`_times`, `_divided`, `_count`, `_spans`).

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/refresh tests/engine -q`
Expected: PASS; `test_golden.py` unchanged (the fixtures have no ratio).

- [ ] **Step 5: The method document**

4.2 gains the paragraph "**The listed-share basis.**" after the split basis: the rule of spec 6.1 in the method's register; 8 the row `basis-scaled`; 9 the row "share basis unclear: ... | 4.2"; 5.12 the `adr_ratio` input.

- [ ] **Step 6: Commit**

```bash
git add src/fairband/refresh src/fairband/engine/route.py docs/method.md tests
git commit -m "Read an ADR's statement periods on the quote's share basis by the depositary receipt ratio or its inverse, each period judged on its own, and refuse a newest period that fits no basis"
```

---

### Task 4: The engine in the reporting currency

**Files:**
- Modify: `src/fairband/refresh/inputs_statements.py` (a trailing period in another currency: the fiscal-year fallback with the sentence), `src/fairband/refresh/inputs.py` (the currency refusals in order; the rate; the street actuals and GuruFocus's EPS into the currency; the new fields; the `_UNKNOWN_CURRENCY` flag removed), `src/fairband/engine/route.py` (`CompanyInputs` fields; `value_company`'s wrap; `_valued`; `reprice`; `FOREIGN_FILER` removed), `src/fairband/engine/route_steps.py` (`money(i)` and `per_share(i)` unit helpers; `common_inputs` on them; the `inflation_differential` RULE input and the `fx_rate` DATA input), every `engine/route_*.py` and `engine/overrides.py` where `"USD"` or `"USD a share"` is written (45 sites: replace with the helpers or the row's currency), `src/fairband/engine/route_mature_growth.py` and `route_revenue_growth.py` (the sales class on `t.revenue / i.fx_rate / 1e6`), `src/fairband/web/reviews_api.py` (the p90 read at line ~780 on the same figure, and the restated cap), `src/fairband/policy/__init__.py` (`in_currency`), `src/fairband/engine/overrides.py` (`check_input` and `range_text` in the currency), `src/fairband/refresh/run_price.py` (passes the rate), `src/fairband/store/secondary.py` (`foreign_filer` reads the new refusals: Task 5 finishes this; here only keep the import compiling)
- Modify: `docs/method.md` 4.2 (the trailing period in another currency), 4.3 (the withholding sentence removed), 4.10 (the translation), 5.1, 5a.1, 6.1, 6a.1, 6b.1 (the guard order of spec 7.5), 5.12 and the inputs sections (the units' words; `fx_rate`, `inflation_differential`), 7 (rewritten: spec 6 and 7 in the method's register, with the table of spec 7.2 and the formula of 7.3), 8 (`fx-stale`; `currency-unknown` removed), 9 (the refusals), 13 (ADS, reporting currency, inflation differential, pair), 14.2 and 14.3 (the ranges in the currency), 3.6 (the `currency-change` row's sentence)
- Create: `tests/engine/test_currency.py`; `tests/fixtures/golden/FXCO.json` with the README note; `tests/support/engine_companies.py` gains `fx_inputs()`: `mature_growth_inputs()` restated in a currency `SEK` at the rate 8.0 on the price date and the differential 0.02 (spec 11.2: price USD 50 → 400; the street actuals and GuruFocus EPS already in SEK, as assembly hands them)
- Test: `tests/engine/test_currency.py`, `tests/engine/test_route.py`, `tests/engine/test_overrides.py`, `tests/engine/test_golden.py`, `tests/refresh/test_inputs.py`, `tests/refresh/test_run_full.py`, `tests/refresh/test_run_price.py`

**Interfaces:**
- Consumes: `InflationTable` (Task 1), `rates_for`, `FxSeries.at`, `FxSeries.mean_at`, `NO_RATE` (Task 2), `apply_splits` (Task 3).
- Produces: `CompanyInputs.fx_rate: float = 1.0` (units of the currency per USD on the price date), `fx_date: date | None = None`, `inflation_differential: float = 0.0`, `fx_stale: bool = False`; the `provenance` keys `fx_rate` (source `FMP historical-price-eod/light USD<code>`, `as_of` the close's date) and `inflation_differential` (the table's source, `as_of` the retrieval date); `notes["inflation_differential"]` = "TWD 1.600% against USD 2.120%, the IMF World Economic Outlook October 2026 means of 2027 to 2031".
- Produces: `in_currency(policy: Policy, differential: float) -> Policy` in `policy/__init__.py`: `replace` of `required_return`, `terminal_growth`, `inflation_addition` and each `base_rates` class's `sales_p90_5y` by `(1 + rate) × (1 + d) − 1`; the version and the hash unchanged; a differential of 0 returns the policy itself.
- Produces: in `value_company`, after the deciles check and the assembly refusal and before the classifier: nothing new (assembly makes the currency and basis refusals, so `inputs.refusal` carries them in the order of spec 7.5: statements, currency unknown, no rate, no projection, above the bound, basis, tax); then `local = in_currency(policy, i.inflation_differential)`, `price_local = price × i.fx_rate`, `market_cap_local = market_cap × i.fx_rate`; the `Context` and the Start-up context built on `price_local`, `market_cap_local` and `local`; `_valued` translates: `value = v.value / i.fx_rate`, `levels = levels_for(value, v.moat, policy)` (on the USD value: the fractions are currency-free), the designation on the USD price and value; `intermediates |= {"currency": i.currency, "fx_rate": i.fx_rate, "fx_date": i.fx_date.isoformat(), "value_in_currency": v.value, "inflation_differential": i.inflation_differential}` on a USD row too (`fx_rate` 1.0, `fx_date` the price date, differential 0.0, `value_in_currency` the value), so a reprice reads one shape. The flag `fx-stale` (word "Rate stale", sentence "The newest close of USDTWD on file is of 2026-11-01, 9 days before the price date 2026-11-10.") when `i.fx_stale`.
- Produces: `reprice(result, price, price_date, policy, *, fx_rate: float | None = None, fx_date: date | None = None, observed_at=None, entered_at=None)`: `fx = fx_rate or im["fx_rate"]`; the local price `price × fx`; the at-price functions on the local price, `im["value_in_currency"]` and `in_currency(policy, im["inflation_differential"])`; the new USD value `im["value_in_currency"] / fx`, the levels scaled by the new value over the old (`Levels(buy × k, ...)`), the designation on the USD pair; `fx_rate` and `fx_date` in the intermediates replaced when given; `fx-stale` swapped in when `fx_date` (given or stored) is more than `policy.fx_stale_days` before `price_date`, out otherwise. The `fx_rate` DATA input moves with it as the price input moves.
- Produces: the DATA inputs `price` (unit `USD`, the quote), `market_cap` (unit the currency, the local figure), `fx_rate` (unit `<code> per USD`; carried on every result, 1.0 with unit `USD per USD` on a USD row? No: left off a USD row, *the plan's call*: a USD row carries neither `fx_rate` nor `inflation_differential`, spec 7.3); the RULE input `inflation_differential` (unit `ratio`, the note above, cited to the table); every other money input's unit the currency's code or `<code> a share` (`money(i)`, `per_share(i)`).
- Produces: `check_input(tag, value, route, policy, *, fx_rate: float = 1.0, currency: str = "USD")`: a money range's ends × `fx_rate`; `range_text(low, high, unit, currency=...)` printing `$` for USD and the code before the figure otherwise ("above 0 to 32,956 TWD a share"); every caller passes the snapshot's rate and currency (`reviews_api.py` from the result's intermediates).
- Produces: assembly's refusals, in `inputs.py` after the statements' refusal: `"reporting currency unknown"` (no currency from the statements or the universe row); `NO_RATE.format(code=...)` when `rates_for` is None or `at(price_date)` is None; `"no inflation projection for <code>"`; `f"{code}: expected inflation {π:.1%} above the {bound:.0%} bound"` (`"ARS: expected inflation 12.1% above the 10% bound"`); the basis refusal; then the tax refusal for every row (the `foreign` withholding removed). The street actuals: each period's actual × `series.at(period_end).rate`; GuruFocus's two EPS × `series.mean_at(period_ends).rate`; a missing rate on any period end leaves the figure `None` (the basis test unknown), never a refusal. `fx_stale` is the price date's rate's `stale`.
- Produces: `inputs_statements._trailing` takes the newest annual currency and leaves the four (or two) quarters for the fiscal year when any names another currency, the flag's sentence "The quarter to 2026-09-30 is in USD while the fiscal years are in CAD, so the trailing figures are fiscal 2025's."; `trailing_quarter_ends` empty on that fallback as on the other.

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_currency.py` (spec 11.1 and 11.2):

```python
def test_in_currency_restates_the_four_rates(policy: Policy) -> None:
    local = in_currency(policy, 0.02)
    assert local.required_return == pytest.approx(0.11180) and local.terminal_growth == pytest.approx(0.05060)
    assert local.inflation_addition == pytest.approx(0.04040)
    assert local.base_rates[0].sales_p90_5y == pytest.approx((1 + policy.base_rates[0].sales_p90_5y) * 1.02 - 1)
    assert local.version == policy.version and local.hash == policy.hash and local.settings_hash == policy.settings_hash
    assert local.wide_terminal_roic_cap == pytest.approx(0.11180 + policy.wide_terminal_roic_spread)
    assert in_currency(policy, 0.0) is policy


def test_a_currency_row_values_in_the_currency_and_translates(policy, deciles) -> None:
    """fx_inputs: SEK at 8.0, price USD 50, market cap USD 5,000 m, d 0.02."""
    r = value_company(fx_inputs(), deciles, policy, TODAY)
    usd = value_company(mature_growth_inputs(), deciles, policy, TODAY)   # the same company in USD
    assert r.price == 50.0 and r.intermediates["fx_rate"] == 8.0 and r.intermediates["currency"] == "SEK"
    assert r.intermediates["value_in_currency"] == pytest.approx(r.value * 8.0)
    assert r.levels.buy == pytest.approx(r.value * (1 - policy.margin_of_safety[moat]))
    assert r.price_to_value == pytest.approx(50.0 / r.value)
    # the route ran on a price of 400 and the restated policy: the implied growth differs from the USD row's
    assert {i.name: i.unit for i in r.inputs}["eps_ttm"] == "SEK a share"
    assert {i.name: i.value for i in r.inputs}["market_cap"] == pytest.approx(40_000e6)
    assert {i.name: i.unit for i in r.inputs}["fx_rate"] == "SEK per USD"
    assert next(i for i in r.inputs if i.name == "inflation_differential").tag == "RULE"
    assert "fx_rate" not in {i.name for i in usd.inputs}


def test_the_sales_class_reads_revenue_in_usd(...) -> None:
    # fx_inputs with trailing revenue 8,000 m SEK: the belief's sales class is the one for USD 1,000 m (compare with mature_growth_inputs at 1,000 m)


def test_reprice_moves_the_usd_value_with_the_rate(policy, deciles) -> None:
    r = value_company(fx_inputs(), deciles, policy, TODAY)
    moved = reprice(r, 55.0, date(2026, 11, 2), policy, fx_rate=8.5, fx_date=date(2026, 11, 2))
    assert moved.intermediates["value_in_currency"] == r.intermediates["value_in_currency"]
    assert moved.value == pytest.approx(r.intermediates["value_in_currency"] / 8.5)
    assert moved.levels.trim == pytest.approx(r.levels.trim * moved.value / r.value)
    assert moved.price_to_value == pytest.approx(55.0 / moved.value)
    kept = reprice(r, 55.0, date(2026, 11, 12), policy)          # no fresh pair quote
    assert kept.value == r.value and "fx-stale" in [f.code for f in kept.flags]   # 12 days past the stored 2026-10-31
    assert "fx-stale" not in [f.code for f in reprice(r, 55.0, date(2026, 11, 5), policy).flags]


def test_a_usd_adr_reads_as_a_domestic_row(policy, deciles) -> None:
    # mature_growth_inputs with is_adr=True and currency "USD": the result equals the domestic one but for the adr_ratio input


def test_override_ranges_read_in_the_currency(policy) -> None:
    assert check_input("earnings.ntm", 32_000.0, "mature-growth", policy, fx_rate=32.956, currency="TWD")[0] == "applied"
    state, sentence = check_input("earnings.ntm", 33_000.0, "mature-growth", policy, fx_rate=32.956, currency="TWD")
    assert state != "applied" and sentence == "earnings.ntm is above 0 to 32,956 TWD a share"
    assert check_input("earnings.ntm", 1_500.0, "mature-growth", policy)[0] != "applied"
```

Also, every route: `value_company` on each of the five other fixtures restated as `fx_inputs` is (a helper `in_sek(inputs)` in `engine_companies`): the result's `value` × 8.0 equals the value the route gives on the local inputs directly with the restated policy (compute by calling the route function with a `Context` built by hand, or assert `value_in_currency` against a hand figure for the Mature Growth row only and the shape for the rest); a Start-up row's requirement in SEK; a Decline row's levels in USD.

`tests/engine/test_golden.py`: the six unchanged; `FXCO` captured from `fx_inputs()` with the README note.

`tests/refresh/test_inputs.py`: on the KRON-style store (ACME's statements in SEK, the USDSEK fixture fetched by `fetch_rates`): `inputs.currency == "SEK"`, `inputs.fx_rate == 10.6` (the close of 2026-11-05 for the price date 2026-10-30? — pick the fixture's close at ACME's quote date, 2026-10-30, and pin it), `inputs.street_ttm_eps` the sum of the four actuals × the four period-end rates (the fixture's 7.8, 7.9, 8.1, 8.2 against `synthetic.QUARTERS`' last four ends; 2.10 USD summed becomes 20.174 only if the actuals are 0.60 to 0.66: the synthetic street actuals are 0.50 + 0.01 × i; compute and pin), `inputs.gf_eps_ttm == 6.11 × 8.0`, `inputs.inflation_differential == pytest.approx(t.differential("SEK"))`, `inputs.refusal is None`; with no `fx-history` on file: `inputs.refusal == "no exchange rate for SEK"`; with the statements' currency `ARS`: `"ARS: expected inflation 12.1% above the 10% bound"`; with `XXX`: `"no inflation projection for XXX"` (the rate first: give it a USDXXX fixture or expect the rate refusal first, per the spec's order rate then projection); with no currency anywhere: `"reporting currency unknown"` and no `currency-unknown` flag; a quarter in another currency: `trailing.on_fiscal_year` with the sentence.

`tests/refresh/test_run_full.py` and `test_run_price.py`: KRON valued with a value in USD; its `fx_rate` input; the price refresh moving its USD value with the pair's quote (`router.bodies["batch-quote"]` for the pairs' call); the failing pair quote leaving the value and setting `fx-stale` only past the bound.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/engine/test_currency.py -q`
Expected: FAIL (`fx_inputs`, `in_currency` unknown).

- [ ] **Step 3: Build it**

Order: `in_currency`; the `CompanyInputs` fields and `fx_inputs`; the wrap in `value_company` and `_valued`; the unit helpers and the 45 sites; the ranges; `reprice`; then assembly (the refusals, the rates, the conversions, the trailing fallback); then the run modules' calls. Keep `price` the USD quote in the inputs and the `price_facts` on the USD closes.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS; the six goldens bit for bit.

- [ ] **Step 5: The method document**

The sections listed under Files, section 7 rewritten in full. 4.10 gains one paragraph: the value and the levels of a company in another currency are its route's figures ÷ the price date's rate. 5.1's guard sentence becomes spec 7.5's. The 1.1 row of 11 (Task 1) is checked against what runs and amended where it differs.

- [ ] **Step 6: Commit**

```bash
git add src tests docs/method.md
git commit -m "Value a company in its reporting currency on the policy's rates restated by the inflation differential, translate the value and the levels to USD at the rate, and refuse a currency the method cannot price"
```

---

### Task 5: The secondary valuation and the report rule

**Files:**
- Modify: `src/fairband/store/secondary.py` (`foreign_filer` removed; `no_secondary` and a new `cannot_fix(refusal: str | None) -> bool`: `"no diluted share count"`, `"reporting currency unknown"`, a refusal starting `"no exchange rate for "`, `"no inflation projection for "`, containing `": expected inflation "` or starting `"share basis unclear"`), `src/fairband/web/reviews_api.py` (the secondary route: the price into the currency at the snapshot's `fx_rate`, `in_currency` on the differential, the value a share and the levels ÷ the rate, the record's rate; the refusal list), `src/fairband/engine/secondary.py` only if its signature needs the restated policy passed (it takes `policy`: pass the restated one), `src/fairband/reports/check.py`, `src/fairband/reports/render.py` and `src/fairband/web/reports_api.py` (the spared list and Appendix A's reason: "no secondary valuation: <the refusal>"), the secondary record's `fx_rate` (a column by a migration `007_secondary_fx.sql` with the row's `fx_rate REAL NOT NULL DEFAULT 1.0`, read into `SecondaryRow.fx_rate`), `playbook/fairband-research/SKILL.md` and `reference/tools.md` (the refusal lists: the foreign-filer line replaced by the new refusals' words)
- Modify: `docs/method.md` 15.3 (the figures in the currency; the per-share value in USD), 15.4 (the refusals), 16.3 and 16.6
- Test: `tests/store/test_secondary_store.py`, `tests/web/test_agents_api.py`, `tests/reports/test_check.py`, `tests/reports/test_render.py`, `tests/test_playbook.py`

**Interfaces:**
- Consumes: `in_currency` and the intermediates' `fx_rate`, `currency`, `inflation_differential` (Task 4).
- Produces: `cannot_fix`; `no_secondary` returns the refusal's own sentence for a cannot-fix refusal (`"no secondary valuation: share basis unclear: ..."` is Appendix A's line, the reason the refusal text); the secondary record's `fx_rate`; the `secondary:` refs' `value` in USD, `firm_value`, `equity`, `debt`, `cash` in the currency (the refs' units unchanged).

- [ ] **Step 1: Write the failing tests**

`tests/store/test_secondary_store.py`: `cannot_fix` on each sentence and on `None`/"no trailing revenue" (False); `no_secondary` on a snapshot refused "ARS: expected inflation 12.1% above the 10% bound" returns that sentence; a snapshot refused "foreign filer: ..." (an old one on file) also counts as cannot-fix (keep the old sentence in the list, since old snapshots carry it). `tests/web/test_agents_api.py`: a secondary valuation on a SEK snapshot (the web conftest values the fixtures; add `fx_inputs`): `value_per_share` in USD = the engine's per-share ÷ 8.0, `firm_value` in SEK, `fx_rate == 8.0`, the drivers' `terminal_growth` bound read against the restated g_T; the refusal for a cannot-fix snapshot. `tests/reports/test_check.py`: the structural check spares a cannot-fix refusal and no longer knows "foreign filer" as a word of its own. `tests/reports/test_render.py`: Appendix A's reason line.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/store/test_secondary_store.py tests/web/test_agents_api.py -q`
Expected: FAIL.

- [ ] **Step 3: Build it**

- [ ] **Step 4: Run the suite**

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 5: The method document and the playbook's refusal lists**

- [ ] **Step 6: Commit**

```bash
git add src tests docs/method.md playbook
git commit -m "Run the secondary valuation in the reporting currency with its value a share in USD, and spare a report the secondary valuation for the refusals an agent cannot fix"
```

---

### Task 6: The words: units, the company read, the drawer, the report page, the Methodology page, the refs and the playbook

**Files:**
- Modify: `src/fairband/web/app.py` (`company`: `currency`, `is_adr`, `adr_ratio`, `fx_rate`, `fx_date` from the snapshot's result; `company_json` if the universe row's `is_adr` is the source), `src/fairband/mcp/server.py` (the `company` tool's description names them), `src/fairband/web/static/app.js` (`inputValue`: a unit that is a three-letter code other than USD prints the code and the figure, `TWD 12,807.36` for a per-share unit `<code> a share` to two decimals and `TWD 3,809,054,300,000` for a total; the head and Details show "Reports in TWD; one ADS is five ordinary shares; valued at TWD 32.96 per USD"), `src/fairband/web/static/report.js` (the same line in the report's head; the inputs' units), `src/fairband/web/static/methodology.html` and `methodology_text.py` (a section `foreign-filers` after `value`, in the page's register: the currency, the rate, the differential with one example, the basis, the bound, the refusals' words; the refusals list's foreign-filer line replaced), `src/fairband/reports/refs.py` (the words of `value_in_currency`, `fx_rate`, `fx_date`, `inflation_differential`, `currency`), `playbook/fairband-research/SKILL.md` (step 3 "Read the company": a foreign filer paragraph; step 10's ranges "in the reporting currency a share"; the flags list gains `basis-scaled` and `fx-stale`; the guidance figures in the reporting currency), `playbook/fairband-research/reference/citations.md` (the format rows: `$` for a USD figure; the code before a figure in another currency, or its sign for €, £, ¥), `playbook/fairband-research/reference/tools.md` (the company read's fields; the secondary valuation's currency; the `fx_rate` ref for `derive`)
- Test: `tests/web/test_company_reads.py`, `tests/web/test_methodology.py` (SECTIONS gains `foreign-filers`), `tests/web/test_app.py`, `tests/reports/test_refs.py`, `tests/test_playbook.py`, `tests/mcp`

**Interfaces:**
- Consumes: the result's intermediates and inputs of Task 4.
- Produces: `GET /api/companies/{symbol}` gains `"currency"`, `"isAdr"`, `"adrRatio"`, `"fxRate"`, `"fxDate"` (camelCase as the API writes keys); the Methodology section id `foreign-filers`; the refs' words: `value_in_currency` "the value a share in the reporting currency", `fx_rate` "the exchange rate, units of the reporting currency per US dollar", `inflation_differential` "the inflation differential against the US dollar".

- [ ] **Step 1: Write the failing tests** (the company read's fields on a SEK fixture and on a USD one; the Methodology section present, its prose under 25 words a sentence; the drawer's unit words pinned through the content check the web tests use; the playbook's new lines, the citations' rows, the tools' fields; `tests/test_playbook.py::test_the_skill_quotes_the_refusals_as_the_server_words_them` on the new refusals)

- [ ] **Step 2: Run them to verify they fail**

- [ ] **Step 3: Build it**

- [ ] **Step 4: Run the suite**: `uv run pytest -q`, PASS.

- [ ] **Step 5: Commit**

```bash
git add src playbook tests
git commit -m "Name the reporting currency on every figure, show the rate, the ratio and the differential in the drawer and the report page, add the foreign filers section to the Methodology page and the playbook, and expose them in the company read"
```

---

### Task 7: The live steps and the readout (the controller, after the merge)

Not a subagent task. After the final review and the merge to main: back up `~/.local/share/fairband/fairband.db` beside the earlier backups, run the migration (Task 5's), restart the server on 8470 from main, run one full refresh (the first with the `rates` stage), then the readout of spec 13 into the spec's decision log, and the backlog: B-28 to Done with the commits, the ledger's parked findings as rows. The full refresh is about 26,000 FMP calls at 3,000 a minute; expect ten to fifteen minutes.
