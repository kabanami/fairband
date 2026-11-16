# The Company Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One page per company at `#company/<symbol>`, with an Overview tab and an Estimates tab drawn from FMP data that the refresh stores; a drawer cut down to the company, its value band and two buttons; a moat stamp, a Notes control and a ticker link that opens the page.

**Architecture:** The refresh's per-company fetch gains ten optional FMP calls, stored whole as vendor responses. Pure readers shape the newest stored answers into two page reads, which call no vendor and carry no refs. A new view of the one page the app is draws them with the design system's tokens and components; the chart is the page's own SVG.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, httpx; plain JavaScript with React from the design-system bundle, no build step; pytest, with node for the page's own scripts (`tests/web/page.mjs`, `tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-16-company-page-design.md`. Read it with your task: this plan argues from it, and where the two differ the spec wins. The look is the mockup's: `docs/superpowers/specs/2026-11-16-company-page-mockup/` (`overview.js`, `overview.css`, `drawer.js`, `drawer.css`). Translate from it; import nothing from it.

**A map of the code as it stands:**

- `src/fairband/vendors/fmp.py`: `Fmp`, one method a route, each `return self._get(route, params)` with `to_fmp_symbol(symbol)`; `news(symbol, limit)` exists.
- `src/fairband/refresh/fetch.py`: `fetch_company`, `_calls` (fifteen FMP calls, then two GuruFocus), `_rows` (the payload's rows, or `None` for an unusable one), `REQUIRED`, `provider_of`.
- `src/fairband/refresh/passthrough.py`: the `news` kind stores endpoint `news` with params `{"symbol", "limit"}`; `NEWS_LIMIT = 20`, `NEWS_LIMIT_MAX = 100`.
- `src/fairband/store/vendor.py`: `latest_response(conn, provider, endpoint, symbol, params) -> ResponseRow | None`, `response_payload(conn, response_id) -> str | None`, `record_response(...)`. `src/fairband/store/observations.py`: `observations_for(conn, symbol, dataset)`, each row with `response_id`. `src/fairband/store/currency.py`: `reporting_currency(conn, symbol) -> str`. `src/fairband/store/research.py`: `notes_for(conn, symbol)`.
- `src/fairband/web/app.py`: `create_app(...)`; `company()` is the detail read (`GET /api/companies/{symbol}`); routes are added by `add_*_routes(app, ...)` functions of the `web/*_api.py` modules. `src/fairband/web/research_api.py`: `agent_records` builds the detail's `review`, `secondary`, `report`, `item`, `priceNeeds`; its `counted` is the review that counts. `src/fairband/web/reports_api.py`: `_symbol(text)` (400 for a bad symbol).
- `src/fairband/web/static/app.js`: the screen and the drawer; `sections(body)` draws the drawer; `window.FairbandPage` (`P`) shares `meter`, `logo`, `pairs`, `currencyLine`, `asking`, `requestResearch`, `watch`, `api`, `getJson`, `localIso`, `PHASE_NUMBER`, `show` and more with the other scripts. `controls.js`: `VIEWS`, `show(tab, section, id)`, `fromHash`, `keepReport`. `report.js`: the report page, the model for a view's script. `charts.js`: the report's charts. `index.html`: the page's CSS (`.app-*`) and its `<script>` list.
- `src/fairband/web/static/design-system/components/bundle.js`: the vendored components with `fairband:` patches; the Ticker cell is at the column `{ key: 'ticker', ... }`; `index.d.ts` documents each patch.
- Tests: `tests/support/web_app.py` (`client`, `db_path`, `policy`), `tests/support/web.py` (`HEADER`, `NOW`), `tests/support/page.py` (`node(helper, args, *scripts)`, `classed`, `elements`, `text`); `tests/refresh/vendor_double.py` (`Router`, fixtures under `tests/fixtures/fmp/<route>[.<period>][.<symbol>].json`).

## Global Constraints

- No file under `src/fairband/engine/` or `src/fairband/policy/` changes. The method stays `fairband-mechanical/1.5` and the policy v16. No migration: the schema stays at 009. No value, level, flag or settings hash moves.
- The two page reads call no vendor. No block's first draw waits on a vendor.
- No figure and no block of vendor data names a vendor, carries a chip, a cite or a ref, or draws three dates. The one exception is the Fairband value block, which is Fairband's own: it keeps the basis chip.
- A change carries `+` or `−` and the text's own colour. No red, no green, no class that colours by sign.
- A missing figure is an em dash, `—`. So is a multiple or the interest cover at exactly 0.
- Every word a person reads is copied from this plan's Words table, which copies the spec's. A changed word is a spec change.
- A link is made only of an address whose scheme is `http` or `https`; every such link has `target="_blank"` and `rel="noopener noreferrer"`.
- No test uses the network. Fixtures and payloads are synthetic: never commit vendor data. Never print, log, store or commit a key.
- Work in a worktree, not in the main checkout: the live server on port 8470 serves the page files of the main checkout as they are on disk.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, then a blank line, then `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.

## Words

| Where | Words |
|---|---|
| Tabs | `Overview`, `Estimates`, `Research` |
| Tabs' row, right end | `data 14 Nov 2026` |
| Head | `close 13 Nov 2026`; the stamp `WIDE MOAT`, `NARROW MOAT`, `NO MOAT`; `Notes`, `Notes 3`; `Watchlists ▾`; `Request research`; the link `Back to the screen` |
| Blocks | `Company`, `Fairband value`, `Key statistics`, `Price`, `Price facts`, `News`, `Earnings`, `Consensus estimates`, `Analysts` |
| Company | `Show more`, `Show less`; `CEO`, `Website`, `Employees`, `Listed`, `Sector`, `Industry`, `Country`, `Exchange` |
| Fairband value | `Fair value`, `Buy level`, `Fair band`, `Trim level`; `Open the report` |
| Key statistics | caption `trailing twelve months, unless the row says`; groups `Size`, `Margins`, `Returns`, `Valuation`, `Financial health`, `Growth, fiscal 2026`, `Growth a year, per share`, `Dividends` |
| Rows | `Market cap`, `Enterprise value`, `Shares`, `Free float`, `Revenue`, `Employees`, `Beta`; `Gross`, `EBITDA`, `Operating`, `Pretax`, `Net`; `ROE`, `ROA`, `ROIC`, `ROCE`; `P/E`, `PEG`, `P/B`, `P/S`, `P/FCF`, `EV/Sales`, `EV/EBITDA`, `EV/FCF`, `Earnings yield`, `FCF yield`; `Debt to equity`, `Net debt to EBITDA`, `Current ratio`, `Quick ratio`, `Interest cover`, `Altman Z`, `Piotroski` (`9 of 9`); `Revenue`, `EBITDA`, `EPS`, `Free cash flow`; `Revenue`, `Net income`, `Cash flow`, `Dividend` under `3Y`, `5Y`, `10Y`; `Yield`, `Payout`, `Dividend a share`, `Paid`, `Last payment` |
| Price | ranges `1M`, `3M`, `6M`, `YTD`, `1Y`, `3Y`, `5Y`; `past month`, `past 3 months`, `past 6 months`, `year to date`, `past year`, `past 3 years`, `past 5 years`; plot names `Close, USD`, `Volume`; the box's `Close`, `Volume`; `No prices on file.` |
| Price facts | groups `Trading`, `Price change`, `Price change, years`; `Open`, `Previous close`, `Day range`, `52 weeks`, `50-day average`, `200-day average`, `Volume`, `Average volume`, `Next earnings`; `1 day`, `5 days`, `1 month`, `3 months`, `6 months`, `Year to date`; `1 year`, `3 years`, `5 years`, `10 years` |
| News | `60 stories`, `1 story`; `newer news did not load: <the server's sentence>` |
| Earnings | head `next 4 Feb 2027, after the close, not confirmed` (`before the open` for `bmo`; nothing for another time; `, not confirmed` only where FMP says false); columns `Reported`, `EPS`, `Estimate`, `Revenue`, `Estimate` |
| Consensus estimates | `Fiscal year`, `Revenue`, `EPS`, `EPS low`, `EPS high`, `Analysts` |
| Analysts | head `consensus Buy`; `Price target`: `Consensus`, `Median`, `Low`, `High`; `Ratings`: `Strong buy`, `Buy`, `Hold`, `Sell`, `Strong sell` |
| Notes box | `No notes yet.`; the field's placeholder and the button `Add a note`, as today |
| Drawer | `Company page`, `Request research`, `Close` |
| Failures | 404 `no page data for <symbol>`; a tab whose read fails: `The company's data did not load: <message>. Open the page again to retry.` |

## Review Focus

Five conditions the spec implies and a hurried build would miss. Each has its test in the task that owns the code.

1. **A vendor answer of the wrong shape.** FMP answers HTTP 200 with `{"Error Message": ...}`, a number as text (`"167000"`), `null`, or `NaN`. The fetch stores an object as unusable and does not reuse it; a reader gives `null` for the field and never raises; the page draws a dash (Tasks 3, 4).
2. **A company with a profile and nothing else.** A company fetched before this build, or whose ten calls all failed, opens its page: both reads answer 200 with every figure `null`, an empty `prices` and no stories, and each block draws dashes or its empty line (Tasks 5, 7, 8, 9, 10).
3. **A short, flat or empty price series.** A company listed two months ago has fewer rows than the range; a halted one has the same close every day; one has no history. Every range draws what there is, the flat one divides by nothing, and the empty one draws `No prices on file.` (Task 8).
4. **An address that is not a web address.** A story's `url` or the profile's `website` is `javascript:alert(1)`, `data:text/html,...`, empty or missing. It is drawn as text, never as a link (Task 9, and the website in Task 7).
5. **A symbol with a dot.** `BRK.B` in the hash, in the ticker's link, in the Company page button and in the reads' paths: encoded where a link is made, decoded and upper-cased where the hash is read, as the report page does (Tasks 6, 11, 13).

And one the reviewer reads the code for: a read that lands after the reader has moved to another company or tab is dropped, as `report.js` drops one (`++latest`).

---

### Task 1: The sentences of what the price needs leave the page (spec 4, 11, 13, 15)

**Files:**
- Modify: `src/fairband/web/static/app.js` (the call in `sections`, the function `priceNeeds`, its entry in `window.FairbandPage`, the comments that name it), `src/fairband/web/static/report.js` (`band`), `src/fairband/web/static/index.html` (the rule `.app-needs`), `docs/method.md` (4.11), `src/fairband/web/static/methodology.html` (the value section's paragraph on a price well above the value)
- Test: `tests/web/test_drawer_needs.py` (rewritten), `tests/web/test_company_reads.py` (`test_the_value_section_says_what_a_price_well_above_the_value_shows`)

**Interfaces:**
- Produces: nothing a later task uses. The detail's `priceNeeds` field stays; `engine/price_needs.py`, `research_api.py` and the playbook do not change.

- [ ] **Step 1: Rewrite `tests/web/test_drawer_needs.py`** to three tests and no node call:

```python
def test_the_drawer_does_not_draw_it() -> None:
    assert "priceNeeds" not in APP.read_text(encoding="utf-8")

def test_the_report_page_does_not_draw_it() -> None:
    assert "priceNeeds" not in REPORT.read_text(encoding="utf-8")

def test_the_page_has_no_style_for_it() -> None:
    assert ".app-needs" not in INDEX.read_text(encoding="utf-8")
```

- [ ] **Step 2: Change the Methodology pin** in `tests/web/test_company_reads.py` to the new paragraph:

```python
assert (
    "When the word is Well above, the value alone says only that the method cannot reach "
    "the price. An agent's report then leads its valuation with what the price needs."
) in value
assert "When no rate in the route's range reaches the price, the report says so." in value
assert (
    "Where growth is charged at the hurdle rate, it adds no value, and the report says that "
    "instead."
) in value
```

- [ ] **Step 3: Run both files.** Expected: the five tests fail.
- [ ] **Step 4: Remove the sentences from the two scripts and the rule from `index.html`.** `tests/web/test_price_needs_api.py` and `tests/web/test_app.py` keep passing: the detail still carries `priceNeeds`.
- [ ] **Step 5: Change the two documents.** `methodology.html`: the paragraph reads "When the word is Well above, the value alone says only that the method cannot reach the price. An agent's report then leads its valuation with what the price needs. That is the growth, the margin or the decline rate at which the value would equal the price. The figure the route holds stands beside it. When no rate in the route's range reaches the price, the report says so. Where growth is charged at the hurdle rate, it adds no value, and the report says that instead." `docs/method.md` 4.11: replace "The drawer and the report page lead the band with them, above the meter." with "No page draws them (the founder, 2026-11-16): they are written for an agent's research, whose report leads its valuation with what the price needs."
- [ ] **Step 6: Run the checks, then commit.**

### Task 2: The Fmp client's nine routes (spec 10.1)

**Files:**
- Modify: `src/fairband/vendors/fmp.py`
- Test: `tests/vendors/test_fmp.py` (`ROUTES`)

**Interfaces:**
- Produces, on `Fmp`, each returning `VendorResponse`:

| Method | Route | Params beside `symbol` |
|---|---|---|
| `ratios_ttm(symbol)` | `ratios-ttm` | none |
| `key_metrics_ttm(symbol)` | `key-metrics-ttm` | none |
| `financial_growth(symbol, limit)` | `financial-growth` | `limit` |
| `financial_scores(symbol)` | `financial-scores` | none |
| `price_change(symbol)` | `stock-price-change` | none |
| `price_target(symbol)` | `price-target-consensus` | none |
| `grades(symbol)` | `grades-consensus` | none |
| `dividends(symbol, limit)` | `dividends` | `limit` |
| `shares_float(symbol)` | `shares-float` | none |

- [ ] **Step 1: Add nine rows to `ROUTES`**, each with the symbol `BRK.B` and the expected `{"symbol": "BRK-B"}`, with `"limit": "1"` for `financial_growth("BRK.B", 1)` and `"limit": "4"` for `dividends("BRK.B", 4)`.
- [ ] **Step 2: Run `uv run pytest -q tests/vendors/test_fmp.py`.** Expected: nine failures, `AttributeError`.
- [ ] **Step 3: Add the nine methods**, each with a one-line docstring saying what the route answers.
- [ ] **Step 4: Run the file again.** Expected: pass. Run the checks, then commit.

### Task 3: The fetch's ten page calls (spec 10.1, 10.2; Review Focus 1)

**Files:**
- Modify: `src/fairband/refresh/fetch.py` (`_calls`, `_rows`, the constants, the module docstring's count and its paragraph on what is usable and required), `tests/refresh/vendor_double.py` (`_FMP_ENDPOINTS`, the fixture fallback)
- Create: `tests/fixtures/fmp/ratios-ttm.json`, `key-metrics-ttm.json`, `financial-growth.json`, `financial-scores.json`, `stock-price-change.json`, `price-target-consensus.json`, `grades-consensus.json`, `dividends.json`, `shares-float.json`, `news-stock.json` (synthetic, one or two rows each, no company's real figures)
- Test: `tests/refresh/test_fetch.py`, and the call counts in `tests/refresh/test_run.py` and `tests/refresh/test_run_full.py`

**Interfaces:**
- Consumes: Task 2's nine methods, `Fmp.news(symbol, limit)`.
- Produces, in `fetch.py`:
  - `GROWTH_YEARS = 1`, `DIVIDEND_ROWS = 4`, `NEWS_STORIES = 60`.
  - `PAGE_ENDPOINTS: tuple[str, ...] = ("ratios-ttm", "key-metrics-ttm", "financial-growth", "financial-scores", "price-change", "price-target", "grades", "dividends", "shares-float", "news")`, the stored endpoint names, in fetch order, after the two GuruFocus calls.
  - Stored params: `{"symbol": s}` for each, plus `"limit": "1"` (`financial-growth`), `"limit": "4"` (`dividends`), `"limit": "60"` (`news`).

- [ ] **Step 1: Teach the double the routes.** In `vendor_double.py` add to `_FMP_ENDPOINTS`: `"stock-price-change": "price-change"`, `"price-target-consensus": "price-target"`, `"grades-consensus": "grades"`. In `_resolve`, when the fixture with the symbol in its name is not a file and the same name without the symbol is, use that one: the ten new fixtures serve every test company.
- [ ] **Step 2: Write the failing tests** in `tests/refresh/test_fetch.py`:

```python
PAGE_ENDPOINTS = ("ratios-ttm", "key-metrics-ttm", "financial-growth", "financial-scores",
                  "price-change", "price-target", "grades", "dividends", "shares-float", "news")

def test_the_page_calls_come_last_in_this_order(...):   # router.requested / call order
    # the ten follow "keyratios"; fetch.PAGE_ENDPOINTS == PAGE_ENDPOINTS
def test_the_page_calls_store_their_params(...):
    # financial-growth {"symbol": "ACME", "limit": "1"}; dividends limit "4"; news limit "60"
def test_a_failed_page_call_is_named_and_costs_nothing(...):
    # router.fail = set(PAGE_ENDPOINTS): outcome.failed == PAGE_ENDPOINTS, outcome.error is None
def test_a_page_payload_is_usable_when_it_is_a_list(...):
    # b"[]" stored with no error and reused on the next fetch (calls unchanged);
    # b'{"Error Message": "x"}' stored with "unusable payload: ..." and called again
def test_a_page_call_gives_no_fact_and_no_observation(...):
def test_a_429_on_a_page_call_stops_the_fetch(...):
    # fail={"grades"}, fail_status=429: rate_limited is True, "dividends" was not called
def test_the_news_is_stored_under_the_pass_through_s_key(...):
    # after the fetch, Passthrough.fetch("news", "ACME", {"limit": "60"}) is reused: no new call
```

Extend `FMP_ENDPOINTS` in that file with the ten, and change the per-company counts in `test_run.py` and `test_run_full.py` from 17 to 27 (25 FMP and 2 GuruFocus) and from 34 to 54, with their comments.

- [ ] **Step 3: Run the three files.** Expected: the new tests fail; the count tests fail at 17.
- [ ] **Step 4: Add the constants, the ten calls and the `_rows` case** (`case _ if endpoint in PAGE_ENDPOINTS: return ([], []) if isinstance(payload, list) else None`). They are not in `REQUIRED`. Update the module docstring: twenty-five FMP calls, the ten's rule in the paragraph on usable payloads, and that a 429 on one is the run's stop as on any call (`run.py` does not change).
- [ ] **Step 5: Run `uv run pytest -q tests/refresh`.** Expected: pass. Run the checks, then commit.

### Task 4: The payload readers (spec 8.3, 8.5, 9, 10.3, 10.4, 14.2, 14.3; Review Focus 1)

**Files:**
- Create: `src/fairband/vendors/page_fmp.py`, `tests/support/page_payloads.py` (synthetic payloads for one made-up company, one constant an endpoint), `tests/vendors/test_page_fmp.py`

**Interfaces:**
- Produces, in `page_fmp.py`, pure functions, payload in and plain data out; none raises on any JSON value:

```python
type Money = dict[str, Any]   # {"value": float, "currency": "USD"}; None where the value is

def number(value: Any) -> float | None           # a finite int or float, never a bool; else None
def money(value: Any, currency: str) -> Money | None
def yearly(total: float | None, years: int) -> float | None   # (1+total)**(1/years)-1; None when 1+total <= 0
def quote_row(payload: Any, symbol: str) -> dict[str, Any] | None  # the row whose "symbol" is the FMP form of symbol
def company(profile: Any) -> dict[str, Any]
def statistics(answers: Mapping[str, Any], profile: Any, quote: Mapping[str, Any] | None,
               reporting: str) -> dict[str, Any]
def trading(quote: Mapping[str, Any] | None, profile: Any, next_day: str | None) -> dict[str, Any]
def price_change(payload: Any) -> dict[str, float | None]
def prices(history: Any, quote: Mapping[str, Any] | None) -> list[list[Any]]
def stories(payload: Any) -> list[dict[str, Any]]
def next_earnings(payload: Any, today: date) -> dict[str, Any] | None
def earnings(payload: Any, today: date) -> dict[str, Any]
def consensus(payload: Any, after: date | None, reporting: str) -> list[dict[str, Any]]
def target(payload: Any) -> dict[str, Any]
def ratings(payload: Any) -> dict[str, Any]
```

`answers` maps an endpoint of `fetch.PAGE_ENDPOINTS` to its parsed payload (absent or `None` when not stored). The shapes they return are the two answers of Task 5, part by part:

```
company     {"brief","ceo","website","employees","listed","sector","industry","country","exchange"}
statistics  {"size": {"marketCap": Money, "enterpriseValue": Money, "shares", "freeFloat", "revenue": Money, "employees", "beta"},
             "margins": {"gross","ebitda","operating","pretax","net"},
             "returns": {"roe","roa","roic","roce"},
             "valuation": {"pe","peg","pb","ps","pfcf","evSales","evEbitda","evFcf","earningsYield","fcfYield"},
             "health": {"debtToEquity","netDebtToEbitda","currentRatio","quickRatio","interestCover","altmanZ","piotroski"},
             "growth": {"fiscalYear","revenue","ebitda","eps","freeCashFlow"},
             "perShare": {"revenue": {"y3","y5","y10"}, "netIncome": {...}, "cashFlow": {...}, "dividend": {...}},
             "dividends": {"yield","payout","perShare": Money, "frequency","lastPayment"}}
trading     {"open","previousClose","dayLow","dayHigh","yearLow","yearHigh","average50","average200": Money each,
             "volume","averageVolume","nextEarnings","price","change","changePercent","day"}
price_change {"d1","d5","m1","m3","m6","ytd","y1","y3","y5","y10"}     # percents as FMP gives them
prices      [["2021-11-15", 150.0, 60000000], ...]                       # oldest first
stories     [{"day","title","publisher","url"}]                          # newest first, as stored
next_earnings {"day","time","confirmed"}
earnings    {"next": next_earnings | None,
             "rows": [{"day","eps": Money,"epsEstimate": Money,"revenue": Money,"revenueEstimate": Money}]}
consensus   [{"fiscalYear","revenue": Money,"eps": Money,"epsLow": Money,"epsHigh": Money,"analysts"}]
target      {"consensus","median","low","high": Money each}
ratings     {"consensus","strongBuy","buy","hold","sell","strongSell"}
```

The FMP field of each figure is spec 8.3's table, 8.5 and 9. The currency of each `Money` is spec 14.2's table: `reporting` for `enterpriseValue`, `revenue`, `dividends.perShare` and the four of `consensus`; `"USD"` for every other. `quote` is one quote row (`quote_row`'s). `trading.nextEarnings` is `next_day`, the `day` of `next_earnings`. `trading.day` is the UTC date of the row's `timestamp`. `earnings.rows` starts with the next date, its two actuals `None`, when there is one; then every row with an actual EPS, newest first. `next_earnings` is the earliest row on or after `today` with no actual EPS, the rule of `normalize_fmp_observations.earnings_observations`. `consensus` keeps the rows whose `date` is after `after`, oldest first. `prices` adds `[trading day, price, volume]` when that day is later than the history's newest day.

- [ ] **Step 1: Write `tests/support/page_payloads.py`**: `PROFILE`, `QUOTE`, `BATCH_QUOTE` (two rows, the company's second), `HISTORY` (ten rows, newest first as FMP gives them), `EARNINGS` (two future rows, one past row with no actual, three reported), `ESTIMATES`, `NEWS` (three stories, one with the address `javascript:alert(1)`), `RATIOS`, `KEY_METRICS`, `GROWTH`, `SCORES` (`reportedCurrency` `"TWD"`), `PRICE_CHANGE`, `TARGET`, `GRADES`, `DIVIDENDS`, `FLOAT`. Invent every figure.
- [ ] **Step 2: Write the failing tests** in `tests/vendors/test_page_fmp.py`. One test a function on its payload, asserting every key's value; and:

```python
@pytest.mark.parametrize("value", [None, "12", True, float("nan"), float("inf"), [], {}])
def test_number_refuses_what_is_not_a_finite_number(value): assert number(value) is None

def test_yearly():
    assert yearly(2.314, 10) == pytest.approx(0.1273, abs=1e-4)
    assert yearly(-1.0, 3) is None and yearly(-1.5, 3) is None and yearly(None, 3) is None

@pytest.mark.parametrize("payload", [None, {}, [], {"Error Message": "x"}, "text", [None], [[]]])
def test_every_reader_answers_on_a_payload_of_the_wrong_shape(payload):
    # each reader returns its shape with None figures or an empty list, and raises nothing

def test_the_reporting_currency_is_on_four_figures_and_usd_on_the_rest():
def test_the_next_earnings_date_is_the_soonest():      # of two future rows; a past row without an actual is not it
def test_the_quote_s_day_is_added_when_it_is_the_later_and_only_then():
def test_the_quote_row_is_found_in_a_batch():          # by symbol, BRK.B against "BRK-B"
def test_interest_cover_is_kept_as_given():            # 0 stays 0: the page draws the dash
```

- [ ] **Step 3: Run the file.** Expected: `ModuleNotFoundError`.
- [ ] **Step 4: Write `page_fmp.py`** with a module docstring that states the rule: every figure is the answer's own field, shaped and never recomputed, but for `yearly`.
- [ ] **Step 5: Run the file.** Expected: pass. Run the checks, then commit.

### Task 5: The two reads, the moat and the note count (spec 7.2, 7.4, 10.3, 10.4, 10.5, 11.1; Review Focus 2)

**Files:**
- Create: `src/fairband/web/company_api.py`, `tests/web/test_company_page_api.py`
- Modify: `src/fairband/web/app.py` (register the routes; `company()` adds `moat` and `noteCount`), `src/fairband/web/research_api.py` (`agent_records` gives `moat`)

**Interfaces:**
- Consumes: Task 4's readers; `latest_response`, `response_payload`, `observations_for`, `reporting_currency`, `notes_for`; `fetch.NEWS_STORIES`, `fetch.PAGE_ENDPOINTS`.
- Produces:
  - `add_company_page_routes(app, conn_factory, policy, clock) -> None` in `company_api.py`.
  - `GET /api/companies/{symbol}/page/overview` → `{"symbol", "dataDate", "company", "statistics", "trading", "priceChange", "prices", "news": {"stories", "observedAt", "stale", "limit": 60}}`.
  - `GET /api/companies/{symbol}/page/estimates` → `{"symbol", "dataDate", "earnings", "consensus", "target", "ratings"}`.
  - The detail (`GET /api/companies/{symbol}`) gains `"moat"`: `"Wide"`, `"Narrow"`, `"None"` or `null`; and `"noteCount"`: a whole number.

Rules:
- Each endpoint's payload is the newest HTTP 200 answer with no error, whatever its age (`latest_response` with the fetch's params for that endpoint), parsed; absent when none.
- The quote row: the newest observation of dataset `quote` for the symbol names a `response_id`; the row is `quote_row(payload of that response, symbol)`.
- `dataDate`: the oldest `observed_at` day among the answers the read drew from, the news left out; `null` when it drew from none.
- `news.stale`: no stored answer, or one observed at or before `clock()` less the refresh's reuse window (the effective policy's `refresh.reuse_hours`).
- `consensus`'s `after`: the newest fiscal year end on file, found as `reports/tables.py` finds its estimate columns.
- A symbol that is not one: 400, as `reports_api._symbol`. No stored profile: 404, `no page data for <symbol>`.
- `moat`: where the review counts and has a value, its result's `intermediates["moat"]`; else the snapshot's where the snapshot has a value; else `null`.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_company_page_api.py`, storing `page_payloads` with `record_response` in the test database:

```python
def test_the_overview_whole(client, db_path):          # every key of the answer, against the payloads
def test_the_estimates_whole(client, db_path):
def test_a_company_with_a_profile_and_nothing_else(client, db_path):
    # both 200; every figure None; prices == []; stories == []; stale is True; dataDate is the profile's day
def test_a_bad_symbol_is_a_400_and_no_profile_a_404(client):
    # 404 detail == "no page data for ZZZZ"
def test_the_data_date_is_the_oldest_answer_s_day(client, db_path):
def test_the_news_is_stale_on_the_far_side_of_the_window(client_with_clock, db_path):
def test_the_newest_answer_wins_and_an_errored_one_is_passed_over(client, db_path):
def test_the_quote_row_comes_through_the_observation(client, db_path):   # a single quote, then a later batch
def test_the_reads_call_no_vendor(client, db_path):    # an app built with a pass-through whose every call fails
def test_the_detail_carries_the_moat_in_force_and_the_note_count(client, db_path, ...):
    # snapshot's moat; a counting review's moat over it; None on a refused row; noteCount 0 then 2
```

- [ ] **Step 2: Run the file.** Expected: 404s from the missing routes and `KeyError`s on the detail.
- [ ] **Step 3: Write `company_api.py`, register it in `create_app`, and add the two fields to the detail.** Update `app.py`'s `company()` docstring and `research_api.py`'s module docstring for the two fields.
- [ ] **Step 4: Run `uv run pytest -q tests/web`.** Expected: pass. Run the checks, then commit.

### Task 6: The company view: its address, head, tabs and data date (spec 7; Review Focus 5)

**Files:**
- Create: `src/fairband/web/static/company.js`, `tests/support/page_answers.py` (one synthetic overview answer, one estimates answer and one detail, in Task 5's shapes), `tests/web/test_company_page.py`
- Modify: `src/fairband/web/static/controls.js` (`VIEWS`, `show`, `fromHash`, a `keepCompany`), `src/fairband/web/static/index.html` (`<section id="company" hidden>`, the script after `charts.js`, the CSS), `src/fairband/web/static/app.js` (`moatStamp`, shared through `FairbandPage`)

**Interfaces:**
- Consumes: Task 5's detail fields and reads.
- Produces:
  - `P.company = { symbol, tab }`, `tab` one of `'overview'`, `'estimates'`; the hash `#company/<encoded symbol>` and `#company/<encoded symbol>/estimates`; `P.show('company', symbol, tab)`.
  - `P.moatStamp(body) -> element | null`: `<span class="label app-moat">WIDE MOAT</span>` from `body.moat`; `null` without one.
  - `P.companyPage`, the object the page's other scripts hang their parts on, with: `head(detail)`, `tabs(symbol, tab, dataDate)`, `panel(title, right, children)`, `kv(rows)` (rows of `[name, value, isText]`; classes `app-kv`, `app-kv__row`, `app-kv__k`, `app-kv__v`), `group(title, rows)`, `table(head, rows)`, and the formatters `money(m)` (`$356.27`, `TWD 120.00`, `—`), `big(m)` (`$5.18T`, `TWD 4.94T`, `14.53B` for a bare count), `percent(x, digits)` for a fraction, `points(x, digits)` for a percent as given, `signed(text, x)`, `multiple(x)` (`39.3x`; `—` at 0), `day(iso)`, `count(n)`.
  - `P.companyPage.draw`, an object later tasks fill: `draw.overview(answer, detail) -> element` (Task 7) and `draw.estimates(answer, detail) -> element` (Task 10). `company.js` reads `/page/overview` or `/page/estimates` for the open tab and draws nothing under the tabs while a tab's function is missing. `Research` is a plain link to `#report/<symbol>`.
  - The head's right side ends with two controls that exist: the watchlists control, a button `Watchlists ▾` that opens the screen's watchlists popup for this company (`P.watch` reads the mark a click landed on: give the button the mark's class, or give `watch` its anchor), and Request research as `report.js` draws it (`P.asking`, `P.requestResearch`, the open item's line, the following of a launch stopped when the page reads another company). Task 12 puts the Notes control before them.
  - CSS classes: `app-company`, `app-company__head`, `app-company__tabs`, `app-company__tab` (`aria-selected`), `app-company__asof`, `app-company__grid`, `app-company__col`, `app-company__panel`.

Behaviour: `load()` reads the detail, then the open tab's read once for that company; a tab change replaces the hash and reads only what the tab has not read; the page shown stays, faded (`is-loading`), until the new one lands; the latest read wins; a failed tab read draws the Words table's sentence; a detail's 404 draws its sentence and `Back to the screen`. The head's change is drawn only where `trading.price` equals the snapshot's price.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_company_page.py` (node, `company.js` as the script):

```python
def test_the_head_s_parts():        # logo, name, ticker, phase badge, "NASDAQ · Technology · ...", price, "close 13 Nov 2026"
def test_the_moat_stamp_s_three_words_and_none():   # "Wide" -> "WIDE MOAT", "None" -> "NO MOAT", null -> no element
def test_the_change_carries_its_sign_and_no_colour_class():
def test_no_change_where_the_quote_is_not_the_snapshot_s_price():
def test_the_tabs_and_the_data_date():   # three, in order; Research's href "#report/BRK.B" encoded; "data 14 Nov 2026"
def test_the_head_s_controls():     # "Watchlists ▾" then Request research, as the report page draws it
def test_the_formatters():          # money USD and TWD, big, percent, points, multiple at 0, the dash for None
```

and text pins on `controls.js` and `index.html`: `'company'` is in `VIEWS`; `fromHash` hands `show` the tab; the panel and the script tag exist; `encodeURIComponent` and `decodeURIComponent` both appear in `keepCompany`'s neighbourhood as in `keepReport`'s.

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Write the view.** `controls.js` follows `keepReport` and `reportPath` for the symbol's coding and upper-casing; an unknown tab is `overview`.
- [ ] **Step 4: Run the file.** Expected: pass. Run the checks, then commit.

### Task 7: The Overview's left column (spec 8.1, 8.2, 8.3; Review Focus 2, 4)

**Files:**
- Create: `src/fairband/web/static/company_overview.js`, `tests/web/test_company_overview.py`
- Modify: `src/fairband/web/static/index.html` (the script, the CSS)

**Interfaces:**
- Consumes: Task 6's `P.companyPage` helpers; `P.meter`, `P.localIso`; the overview answer.
- Produces on `P.companyPage`: `safeHref(address) -> string | null` (the address when its scheme is `http` or `https`, else `null`), `Company(props)` (a component: its brief opens and closes), `value(detail)`, `statistics(overview)`; and `draw.overview(answer, detail)`: two columns, the left one these three blocks, the right one what Tasks 8 and 9 add to it in this file.

- [ ] **Step 1: Write the failing tests**:

```python
def test_the_company_block():       # the brief, eight facts in two lists of four, "167,000", "12 Dec 1980"
def test_the_website_is_a_link_only_when_it_is_a_web_address():
    # "https://www.acme.example" -> href, text "acme.example", target "_blank", rel "noopener noreferrer";
    # "javascript:alert(1)", "", None -> text or dash, no <a>
def test_the_value_block_valued():   # basis chip "mechanical"; four levels with the Words; no stance line without a report
def test_the_value_block_reviewed_and_with_a_report():   # chip "reviewed"; stance chip, "full report, 11 Nov 2026", "Open the report" -> "#report/ACME"
def test_the_value_block_of_a_refused_row():             # the refusal's sentence; no levels
def test_the_statistics_groups_rows_and_figures():       # seven titles, the fiscal year in "Growth, fiscal 2026", every row's text
def test_a_reporting_currency_figure_carries_its_code(): # "TWD 4.94T"
def test_every_figure_missing_draws_the_dash():          # the answer of a company with nothing: no exception, "—" in every row
def test_interest_cover_at_zero_is_the_dash():
```

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Write the three blocks**, the brief clamped to three lines with `Show more` and `Show less`.
- [ ] **Step 4: Run the file.** Expected: pass. Run the checks, then commit.

### Task 8: The price chart (spec 8.4; Review Focus 3)

**Files:**
- Create: `src/fairband/web/static/company_chart.js`, `tests/web/test_company_chart.py`
- Modify: `src/fairband/web/static/company_overview.js` (`draw.overview`'s right column starts with the chart), `src/fairband/web/static/index.html` (the script, the CSS)

**Interfaces:**
- Consumes: `overview.prices`; `P.companyPage.panel`, `money`, `big`, `day`.
- Produces `P.companyChart`:
  - `RANGES`: `[['1M', 'past month'], ['3M', 'past 3 months'], ['6M', 'past 6 months'], ['YTD', 'year to date'], ['1Y', 'past year'], ['3Y', 'past 3 years'], ['5Y', 'past 5 years']]`.
  - `inRange(prices, id) -> rows`: from the day that many months before the newest row's day; `YTD` from the last day of the year before.
  - `change(rows) -> { amount, ratio } | null`: the newest close less the first, and that over the first; `null` for fewer than two rows or a first close of 0.
  - `niceStep(span, count)`, `xTicks(rows, long)` (the first trading day of a month, or of a year when `long`, at most seven; the first shown and each January carry the year).
  - `geometry(rows, width) -> { path, yTicks, lastX, lastY, bars, volumeMax, ... }` or `null` for no rows.
  - `lead(rows, id) -> string | null`: the change's words, `+$83.32 (+30.5%) past year`.
  - `Chart(props)` with `props.prices`: the block, with the range's state (`1Y` at first), the hover and the measured width.

- [ ] **Step 1: Write the failing tests** on a known series of ten rows (two months) and one of 600 (generated in the test):

```python
def test_each_range_keeps_the_rows_from_its_first_day():
def test_a_range_longer_than_the_series_keeps_every_row():
def test_the_change_over_a_range():            # amount and ratio; None for one row and for none
def test_the_path_starts_at_the_first_close_and_ends_at_the_last():   # "M4.0 ..." and lastX == left + plot width
def test_a_flat_series_has_a_finite_geometry():   # every close equal: no NaN, no Infinity in path or ticks
def test_an_empty_series_draws_its_sentence():    # "No prices on file."; no svg
def test_the_ticks_name_the_year_on_the_first_and_on_each_january():
def test_a_range_over_two_years_ticks_by_year():
def test_the_y_tick_under_the_tag_is_left_out():
def test_the_lead_carries_the_sign_the_percent_and_the_range_s_words():   # "+$83.32 (+30.5%) past year"
```

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Write the chart.** Two plots on one time axis: the close as a 2px line in `var(--chart-1)` with an end marker ringed in `var(--surface-raised)` and the newest close in a tag in `var(--accent)` with `var(--on-accent)` text; the volume as bars in `var(--chart-context)`. Grid lines solid in `var(--chart-grid)`. Text ticks in `var(--ink-faint)`, monospaced. A hover draws a crosshair and a box with the day, `Close` and `Volume`; keyboard focus on the plot with the arrow keys moves the same crosshair. No table, no Table button, no animation. The mockup's `PriceChart` is the reference for the geometry.
- [ ] **Step 4: Run the file.** Expected: pass. Run the checks, then commit.

### Task 9: Price facts, the news and the columns' rule (spec 8.5, 8.6, 8.7, 10.5, 10.6; Review Focus 2, 4)

**Files:**
- Modify: `src/fairband/web/static/company_overview.js`, `src/fairband/web/static/company.js` (the stale news' second read), `src/fairband/web/static/index.html` (CSS)
- Test: `tests/web/test_company_overview.py`

**Interfaces:**
- Consumes: Task 7's `safeHref` and `draw.overview`; the pass-through `GET /api/vendor/news/{symbol}?limit=<news.limit>`, read with the header a write carries (`X-Fairband-Request: 1`), as `report.js` reads the series of its charts.
- Produces on `P.companyPage`: `priceFacts(overview)`, `news(newsState)` where `newsState` is `{ stories, note }`, both added to `draw.overview`'s right column after the chart; `freshNews(symbol, limit) -> Promise<stories>` (the pass-through's payload shaped as the read's stories: `day` the first ten characters of `publishedDate`, `title`, `publisher` (else `site`), `url`).
- CSS, as the mockup's rule: `.app-company__grid { align-items: stretch; }`, `.app-company__col--match { height: 0; min-height: 100%; }`, the news block `flex: 1 1 0; min-height: 260px` with its list `overflow-y: auto`, and `.app-company__col > .app-company__panel:last-child` growing on every other tab; one column under 1180px with the list under 520px; inside a block three columns become two under 700px of block width and one under 460px (container queries).

- [ ] **Step 1: Write the failing tests**:

```python
def test_the_three_groups_of_price_facts():    # titles, rows, "$355.75 – $360.83", "+1.2%", "−0.7%", "4 Feb 2027"
def test_the_news_list_and_its_count():        # "3 stories"; day, title, publisher; "1 story" for one
def test_a_story_is_a_link_only_when_its_address_is_a_web_address():   # javascript: and data: drawn as text
def test_the_news_note_is_drawn_when_given():  # "newer news did not load: no FMP key"
def test_no_news_draws_an_empty_list_and_its_count():   # "0 stories"
def test_the_columns_rule_is_in_the_page_s_css():       # the three rules above, as text pins on index.html
```

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Write the two blocks, the CSS and the second read.** Where `news.stale` is true the page draws the stored stories, then asks the pass-through once for that opening of the page; on an answer it draws those stories; on a refusal it keeps the stored ones and sets the note from the server's `detail`. A read for a company the page has left is dropped.
- [ ] **Step 4: Run the file.** Expected: pass. Run the checks, then commit.

### Task 10: The Estimates tab (spec 9, 14.2; Review Focus 2)

**Files:**
- Create: `src/fairband/web/static/company_estimates.js`, `tests/web/test_company_estimates.py`
- Modify: `src/fairband/web/static/index.html` (the script, the CSS)

**Interfaces:**
- Consumes: the estimates answer; Task 6's helpers.
- Produces on `P.companyPage`: `earnings(estimates)`, `consensus(estimates)`, `analysts(estimates)`; the `estimates` tab's `draw`: Earnings in the left column, Analysts then Consensus estimates in the right.

- [ ] **Step 1: Write the failing tests**:

```python
def test_the_earnings_head_and_table():   # "next 4 Feb 2027, after the close, not confirmed"; the next row with two dashes; then the reported rows
def test_the_head_without_a_next_date_and_with_a_confirmed_one():
def test_the_consensus_rows_carry_the_reporting_currency():   # "TWD 11.54T", "TWD 949.56"
def test_the_analysts_block():            # "consensus Buy"; four target rows; five counts in order; no track element
def test_an_answer_with_nothing_draws_dashes_and_empty_tables():
```

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Write the three blocks.**
- [ ] **Step 4: Run the file.** Expected: pass. Run the checks, then commit.

### Task 11: The drawer's form A (spec 11; Review Focus 5)

**Files:**
- Modify: `src/fairband/web/static/app.js` (`sections`, `drawer`, and the functions nothing calls after it), `src/fairband/web/static/index.html` (CSS)
- Test: `tests/web/test_drawer_form.py` (new), and the drawer tests whose subject left (`tests/web/test_drawer_*.py`, `tests/web/test_logo_page.py`, `tests/web/test_launch_page.py`: keep, change or delete each by what it tests)

**Interfaces:**
- Consumes: `P.moatStamp` (Task 6), `body.moat`.
- Produces: `sections(body)` returns, in order: the head (logo, ticker, phase badge, moat stamp, name, the currency line of a company not in US dollars); one caption, the sector and the industry; the brief in body text, six lines (class `app-drawer__brief`, clamped in CSS); the value band (`meter(body)` as today for a valued row, a reviewed one, a refused row's review or secondary band) with four levels named `Fair value`, `Buy level`, `Fair band`, `Trim level`; a refused row's refusal sentence where there is no band; and the buttons: `Company page`, primary, `href` `#company/<encoded symbol>`, then Request research with its menu and the open item's line as today.

- [ ] **Step 1: Write the failing tests** in `tests/web/test_drawer_form.py` (node, a synthetic detail):

```python
def test_the_parts_in_order():                   # head, sector line, brief, band, buttons
def test_the_levels_use_the_screen_s_words():    # no "Margin of safety", no "× value", no moat caption
def test_the_company_page_button_s_address():    # "#company/BRK.B" encoded
def test_what_left_the_drawer_is_not_drawn():    # no route name line, no cross-check, no stance, no Summary,
                                                 # no "Open the report", no "Details", no Young Growth or Start-up line
def test_a_refused_row_draws_its_refusal():
def test_a_reviewed_row_draws_the_review_s_band():
def test_the_moat_stamp_follows_the_phase_badge():
```

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Rewrite `sections`.** Then remove what nothing calls: for each function of `app.js`, keep it when `app.js`, another script under `static/` or a kept test still uses it; `report.js` reads `inputsTable`, `figuresTable`, `inputFigure`, `secondaryRows`, `secondaryPath`, `guidanceTable`, `phaseEvidence`, `pairs`, `when`, `whole`, `money`, `rate`, `plain`, `footnotes`, `currencyLine` and more through `FairbandPage`, so check each name with a search before deleting. `readResearch`, `state.detailsOpen`, `toggleDetails` and `details` go; `drafted` and `postNote` stay for Task 12. The read `GET /api/companies/{symbol}/research` and its tests stay.
- [ ] **Step 4: Settle the old drawer tests.** A test of a function that stays (the report page uses it) stays; a test of a drawer part that left is deleted with it; say in the commit which files went.
- [ ] **Step 5: Run `uv run pytest -q tests/web`.** Expected: pass. Run the checks, then commit.

### Task 12: The Notes control and its box (spec 11.1)

**Files:**
- Modify: `src/fairband/web/static/app.js` (the control, the box, `drafted`, `postNote`), `src/fairband/web/static/company.js` (the control in the head), `src/fairband/web/static/index.html` (CSS)
- Test: `tests/web/test_notes_control.py`

**Interfaces:**
- Consumes: the detail's `noteCount` (Task 5); `GET /api/companies/{symbol}/notes` → `{"notes": [{id, text, principal, actor, at, overrideId}]}`; `POST /api/companies/{symbol}/notes` `{text}`; the watchlists popup's frame and its closing on Escape and on a click outside.
- Produces through `FairbandPage`: `notesControl(symbol, count) -> element` (a quiet button, class `app-notes-open`, text `Notes` or `Notes 3`) and `notesBox(box) -> element` where `box` is `{ symbol, notes, loading, error, draft }` (class `app-notes-box`).

Behaviour: the control stands at the left of the drawer's top bar (`Close` at the right) and in the company page's head before the watchlists control. A click opens the box under the control and reads the notes; the list is newest first, each with its day, its principal chip and its text, scrolling under 240px; `No notes yet.` without one. Under it the field and `Add a note`, as Details had them. A note taken is first in the list, and the detail is read again so the count follows (`reloadDetail` for the drawer, the page's own load for the page). A refusal draws the server's sentence under the field and keeps the text. The draft is kept until the drawer or the page shows another company.

- [ ] **Step 1: Write the failing tests**:

```python
def test_the_control_without_a_count_and_with_one():   # "Notes", "Notes 3"
def test_the_box_lists_the_notes_newest_first():       # day, PrincipalChip props, text
def test_the_box_without_a_note():                     # "No notes yet."
def test_the_box_s_field_and_button():                 # placeholder "A note on ACME"; "Add a note" disabled for an empty draft
def test_a_refusal_s_sentence_is_under_the_field():
def test_the_drawer_s_bar_holds_the_control_left_of_close():
def test_the_page_s_head_holds_it_before_the_watchlists_control():
```

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Write the control and the box.**
- [ ] **Step 4: Run the file.** Expected: pass. Run the checks, then commit.

### Task 13: The ticker's link and the report page (spec 12, 13; Review Focus 5)

**Files:**
- Modify: `src/fairband/web/static/design-system/components/bundle.js` (the Ticker cell), `src/fairband/web/static/design-system/components/index.d.ts` (`ScreenTableProps`), `src/fairband/web/static/app.js` and `src/fairband/web/static/watchlists.js` (the prop), `src/fairband/web/static/report.js` (the link, the Tables button), `src/fairband/web/static/charts.js` (`tableView`), `src/fairband/web/static/index.html` (CSS)
- Test: `tests/web/test_ticker_link.py` (new), `tests/web/test_report_charts.py` and the report page's tests that name `Tables` or `tableView`

**Interfaces:**
- Produces:
  - `ScreenTableProps.companyHref?: (row: ScreenRow) => string`, a `fairband:` patch. Given it, the ticker's text is `<a class="fb-screen__company" href={companyHref(r)}>`, whose click and whose Enter stop at the link (`stopPropagation`), so the row's `onOpen` does not run. Without it the cell is as it was.
  - `app.js` and `watchlists.js` pass `companyHref: function (r) { return '#company/' + encodeURIComponent(r.ticker); }`.
  - `report.js`: a `Company page` link in the head to `#company/<encoded symbol>`; no `Tables` button, no `state.tables`, no `toggleTables`; `P.reportCharts.draw(report, series)` takes two arguments; `charts.js` hands no chart `tableView`.

- [ ] **Step 1: Write the failing tests**:

```python
def test_the_ticker_is_a_link_given_the_prop():        # node, "Fairband.ScreenTable": href "#company/BRK.B" encoded
def test_the_cell_without_the_prop_is_as_before():     # no <a>
def test_the_link_stops_its_click_and_its_enter():     # text pins on the patch: stopPropagation in onClick and onKeyDown
def test_the_screen_and_the_watchlists_pass_the_prop():
def test_the_report_page_links_to_the_company_page():
def test_the_report_page_has_no_tables_button():       # "Tables", "toggleTables", "tableView" not in report.js or charts.js
```

- [ ] **Step 2: Run the file.** Expected: fail.
- [ ] **Step 3: Make the patch and the report page's changes.** Mark the patch `// fairband:` with the spec's date, as the watchlist mark's is, and document the prop in `index.d.ts`. The link reads as the ticker does, takes an underline on hover and the focus ring on focus.
- [ ] **Step 4: Run `uv run pytest -q tests/web`.** Expected: pass. Run the checks, then commit.

### Task 14: The documents, the whole-branch review and the live steps (spec 15, 17)

**Files:**
- Modify: `docs/backlog.md`, the spec's decision log, the docstrings and comments the build made untrue

- [ ] **Step 1: Search for what the build made untrue**: the drawer's Details, the report's Summary in the drawer, `Open the report` in the drawer, the fetch's count of calls, the report page's Tables toggle, in `docs/method.md`, `methodology.html`, the playbook, `README.md` and the module docstrings. Correct each. `uv run pytest -q tests/test_method_doc.py tests/test_playbook.py tests/web/test_methodology.py` passes.
- [ ] **Step 2: The backlog.** B-215 keeps its row for the later tabs and gains a line that plan 1 is built; B-197 moves to Done with the commit that took the sentences off the pages; the reviews' deferred minors are filed, one row a file or theme.
- [ ] **Step 3: The whole-branch review** by a fresh reviewer, with the spec, this plan and the Review Focus list. Its findings are fixed or filed.
- [ ] **Step 4: The page in a headless browser**, by the controller, on a scratch database with a few companies and synthetic page answers: the Overview and the Estimates tab at 1,250, 1,600 and 2,400 pixels, both themes, against the mockup; the two columns end on one line; the drawer's form A; the ticker's link; Back from the report page.
- [ ] **Step 5: The live steps, with the founder's consent for each** (spec 17): back the database up, start the server from main after the merge, run a full refresh, open the pages the spec names. The readout goes in the spec's decision log: the refresh's minutes against 13, the failed page calls by endpoint, the database's growth, what the five foreign filers showed.
