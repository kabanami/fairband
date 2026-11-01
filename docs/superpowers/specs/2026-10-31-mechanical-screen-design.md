# Fairband mechanical screen — design (first cut)

**Date:** 2026-10-31
**Status:** draft, awaiting the founder's approval
**Decisions by:** the founder (Khalid Abanami). Items marked *my call* were made by Claude while writing this document and can be overturned.

## 1. What this is

Fairband values every U.S.-listed company of a useful size by its life-cycle phase, and later lets the founder's own agents re-value the few worth a closer look. This document covers the first piece only: **the mechanical screen**. It is the page the founder opens most days. One row per company, with the engine's value, the levels around it, the price and the stance. No agent writes yet, no company report page, no portfolio.

The method is not restated here. It lives in the legacy documents, which stay the source for everything this document does not change:

- `docs/legacy/design.md` — the product design. Sections 2 (scope), 4 (the screen), 5 (the phase classifier), 6.2 to 6.6 and 6.11 to 6.13 (the engine), 8 (the validity window), 12 (storage) and 13 (keys and private material) apply to this piece.
- `docs/legacy/research.md` — founder decisions D2, D3, D3a, D3b, D6, D7, D9 and D17 apply to this piece. The rest belong to later pieces or to the earlier build's process.
- `docs/legacy/input-source-map.md` and `docs/legacy/source-evidence.md` — which vendor endpoint supplies which input, with the known limits.
- `docs/legacy/product-brief.md` — the audience, the wedge and the non-goals.
- The design system, exported from the founder's design artifact on 2026-10-29: the screen table, its thirteen columns, the stance rule, the three dates and the validity marks. The archive is at `docs/design-system/`. It is a starting point, not a contract; it may change.

Where this document and a legacy document disagree, this document is newer and wins. Where this document is silent, the legacy document applies. A "Decided" label in `design.md` stays decided. A "Proposed" or "Open" item that this piece needs is settled below and marked *my call*.

The stocks repo (`/mnt/c/users/kaban/documents/workspace/stocks`) holds the method v1.7 (`docs/valuation-method.md`), the mechanical rules `mech/1.2` (`docs/mechanical-valuation.md`) and working vendor clients. It is reference material on this machine only. Nothing is ported from it. A builder may read it to check a rule, and may copy a small piece (the URL scrub, a parser trap) with a comment that names its origin.

## 2. Why this piece first

The founder's words: "I need to have a value for any ticker, and use it as a starting point for exploring value pockets." The screen is that starting point. The earlier build spent its first release on the data acquisition layer and had no value for any company after 64 commits. This cut inverts the order: a defensible value for real companies first, infrastructure only as far as that needs.

Success for this cut: the founder opens the page, runs a refresh, and sees a value, the levels and a stance for most Mature Growth and Mature Stable companies above $2 bn, with every other row saying why it has no value. The numbers for the test companies match the arithmetic in `design.md` section 6.5.

## 3. Goals

1. One page at `localhost` with one row per eligible company. Columns: ticker, company, phase, fair band, fair value, buy level, trim level, mechanical value, reviewed value (always an em dash in this cut), price, stance, entered date, and the extra columns in section 6.3. A column chooser, a default set, sort by any column.
2. A refresh that runs only on request, fetches what it needs from FMP and GuruFocus, stores it locally, classifies every company, values it, and writes one snapshot per company. It can be stopped and continued.
3. The Mature Growth route with the reinvestment charge and the ROIC rules, and the Mature Stable route. The other four phases get a row with their phase and the reason they have no value.
4. Every row explains itself: the classifier evidence, the tagged inputs, the flags, or the refusal reason, visible from the row.
5. Every input carries its tag (DATA or RULE), its source, its as-of date, its observed date and its entered date. Every rule number comes from a versioned policy file with a source or an explicit "no source" note.
6. The founder's keys stay in a private file outside the repository. No key appears in a URL, a log, the database, a test fixture or an error message.
7. A calibration count after the first universe run: how many companies per phase, how many flagged by a classifier check, how many refused and why (`design.md` 5.8).

## 4. Non-goals for this cut

- The Start-up, Young Growth, High Growth and Decline routes. Each comes as its own later piece.
- Agent access (the MCP server), overrides, reviews, the value bridge. The reviewed column exists and shows an em dash.
- The company report page. A read-only detail drawer on the screen stands in for it (section 6.4).
- The portfolio ledger. The founder deferred it on 2026-10-31; it is not on the near-term list.
- GuruFocus security-class check for eligibility. FMP data alone decides eligibility in this cut.
- Values for foreign filers and ADRs. They get a row and a refusal reason (section 11). Their valuation is the next piece.
- Owner sign-in and sessions. The server binds to `127.0.0.1` only. Agent writes in a later piece will revisit this.
- Point-in-time reruns as of a past date.
- Two share classes for one company. FMP lists one class per company; the screen shows that one.
- The guidance ceiling, the FY1 pollution test, the dividend-to-FCFE test, the control layer, Altman Z and distance-to-default flags, the "price fell but estimates did not" flag. Each belongs to a later piece or a later route.
- A scheduled refresh. Nothing runs unless asked.
- An LLM inside Fairband, a brokerage connection, a hosted service, technical analysis.

## 5. Anti-goals

These would make the cut a failure even if the page renders:

- An invented number. A missing input is a refusal with a reason, never a zero or a default the literature does not give.
- A silent methodology change. Every departure from `design.md` or the method v1.7 is written down here or in a policy file.
- A missing row. A company in the universe with no row cannot be told apart from "not cheap".
- A leaked key, or vendor data committed to the repository.
- A page that needs the network to render. Fonts and scripts are served from the package.
- A refresh that cannot be stopped and continued.
- Codes in the reader-facing text. The screen shows words; the codes live in the detail drawer's audit section.

## 6. The shape

### 6.1 The universe

Source: one FMP `company-screener` call per refresh (my call: one call, cached for the day). Admit a listing when all hold:

- exchange is NYSE, NASDAQ or AMEX (no OTC);
- market cap in USD is $2 bn or more;
- not an ETF, not a fund, actively trading;
- the sector or industry is not banks, insurance or REITs (the exact FMP industry strings go in the policy file);
- the symbol does not match the preferred, warrant, unit or rights patterns in the policy file, and is not on the policy file's manual exclusion list.

Cap bands (`design.md` 2, Proposed → adopted, *my call*): Mega from $200 bn, Large from $10 bn, Mid from $2 bn. Market cap comes from the screener in USD.

The universe of 2026-10-20 held 74 Mega, 888 Large and 1,118 Mid listings before the sector exclusions. Expect about 1,700 to 2,000 companies after them.

Every admitted company gets a `companies` row and a screen row. Every excluded listing that only fails the sector or symbol rule is recorded with its reason, so the exclusion list can be audited; it gets no screen row.

### 6.2 The refresh

Two kinds, both started from the page (`design.md` 4.3, Proposed → adopted, *my call*):

- **Full refresh.** Universe, then per company the data in 6.5, then deciles, classification, valuation, snapshots.
- **Price refresh.** Quotes only, then the price-dependent fields of each current snapshot: price, price ÷ value, stance, the implied growth and the expected return. It writes a new snapshot that cites the same inputs, with the price input and the price date replaced by the fresh quote. The price facts (the 52-week range, the price changes, the drawdown) need the price history, so they follow the full refresh (amended 2026-11-01).

Rules:

- A refresh is a database record with per-company progress. Stopping the server or the refresh keeps every company already done. Starting again continues with the companies not done. A company's vendor data observed within the last 24 hours is reused, not fetched again (D13). The GuruFocus scores are reused within 7 days (*my call*, to protect the 40,000-call monthly quota).
- One refresh at a time. A second request while one runs is refused with the running one's id.
- Vendor calls run outside database write transactions. Four companies fetch at a time (*my call*, from `mech/1.2` experience; a policy value). An HTTP 429 from a vendor stops the refresh with a message that says so; the work done stays.
- A company whose fetch fails gets a snapshot with the refusal reason "data fetch failed: <endpoint>", not a missing row.
- The refresh reports progress: companies done, failed, remaining, and the current stage. The page shows it. While a refresh runs, the page keeps showing the previous snapshots.
- A development command, `python -m fairband refresh AAPL,MSFT`, runs the same code for named tickers without the page (*my call*; it is a builder and test convenience, not a user surface).

### 6.3 The screen page

One HTML page served by FastAPI. The design system's `ScreenTable` renders the rows. The column chooser is the design system's; the chosen columns persist in the browser's local storage. Sorting is a request to the server (`sort`, `dir`); the server orders rows with a defined rule for rows with no value (they sort last). No pagination; all rows in one response.

Columns beyond the design system's thirteen (*my call*, from `design.md` 4.2 and 9.5; the founder asked for price-based and valuation-based columns to choose from). Each is a plain figure; the design system's table definitions are extended in the repository's copy:

| Column | Source |
|---|---|
| Sector, cap band, market cap | FMP screener |
| Moat class | GuruFocus moat score by the `mech/1.2` table |
| Implied growth, years 4 to N | the engine, Step 4c |
| Expected return, 3 years | the engine, Step 9 |
| EPV (no-growth value) | the engine, Step 3 |
| Trailing P/E, reported and clean; forward P/E | the engine, Step 7 |
| 52-week high and low; 1-, 3-, 5-year change; drop from the last peak | FMP price history |
| Flags | the engine (section 6.7); shown as short words, with the explanation in the drawer |
| Refusal reason | the engine; filled only when there is no value |
| Price date, data date, valid until | the snapshot |

Group view (`design.md` 4.2, Proposed → adopted, *my call*): a second tab on the page groups the rows by sector, by phase or by cap band and shows per group the count, the median price ÷ value, and the share of companies below the buy level. It is one table with no chart.

Stance words follow the design system: `buy`, `hold`, `trim`, derived from the price against the buy and trim levels. The five-step stance of `design.md` 6.3 is kept in the snapshot and shown in the drawer; the screen column shows the three-word form the design system defines. (*My call*; the design system was written after the design and collapsed the middle three steps into `hold`.)

### 6.4 The detail drawer

Clicking a row opens a drawer beside the table. It is read-only and stands in for the company report page until that piece exists. It shows:

1. The headline: value, price, the three levels, the stance, the validity window with its state.
2. The phase with the classifier evidence: the growth word and its decile, the margin sign and direction, the check flags, the Dickinson stage.
3. Every tagged input with its tag, value, unit, source, as-of, observed and entered dates.
4. The engine's intermediate results: NOPAT and invested capital by year, the aggregate ROIC, the terminal ROIC, the growth path, the implied growth at the three runways and at the three ROIC values, EPV, the expected-return parts.
5. The flags with one plain sentence each.
6. The refusal reason, when there is no value.
7. The policy version and the method version.

Numbers in the drawer are rounded as `design.md` 9.2 says; the stored values keep full precision.

### 6.5 Data per company

All from FMP unless named. Endpoint names are the FMP stable API's; the builder checks them against the current documentation. Each stored response records a logical endpoint name (for example `income-annual`) and the logical parameters that identify the call; the adapter's route table maps the name to the vendor route (amended 2026-11-01).

| Need | Endpoint | Depth |
|---|---|---|
| Income statement, balance sheet, cash flow, annual | `income-statement`, `balance-sheet-statement`, `cash-flow-statement` | 11 fiscal years: ten for the ROIC aggregate plus the opening balance (D2) |
| Income statement and cash flow, quarterly | the same endpoints with `period=quarter` | the last 8 quarters, for the trailing-twelve-month figures (section 6.6, "Trailing figures") |
| Acquired intangibles, net | `balance-sheet-statement-as-reported` | same years; the issuer's total intangibles excluding goodwill (D17, method `bs10-intangibles-total-v1`) |
| Profile: name, sector, industry, country, currency, exchange | `profile` or the screener row | current |
| Quote: price, 52-week range, market cap, diluted shares | `quote` (batch where the API allows) | current |
| Price history | `historical-price-eod` | 5 years of daily closes, for the 1-, 3-, 5-year change and the peak drawdown |
| Consensus EPS, revenue and net income, annual, with analyst counts | `analyst-estimates` (period annual) | the next four fiscal years |
| Consensus EPS, quarterly | `analyst-estimates` (period quarter) | the next four quarters for the NTM anchor |
| Street actual EPS by quarter | `earnings` | the last eight quarters, for the SBC basis test |
| Next earnings date | `earnings` or `earnings-calendar` | the next confirmed or estimated date, for the validity window |
| Moat score; Altman Z″; EPS without NRI | GuruFocus `stock/{symbol}/summary` and `stock/{symbol}/keyratios` | current; two calls per company |

Share-class symbols differ between vendors (`BRK.B` at GuruFocus, `BRK-B` at FMP). The store keeps the exchange form (`BRK.B`) and the adapters convert.

Every response is stored as received, minus any secret, with the provider, endpoint, parameters, HTTP status and observed time. Normalized facts are stored in their own rows and cite the response they came from. A field that is absent, null or rejected is stored as absent with a reason; a normalized balance-sheet zero counts as not presented unless the as-reported statement presents the line (D17).

Numbers from vendors are parsed as decimals and stored as decimal text with their unit and currency. The engine computes in 64-bit floats with a pinned tolerance in its tests (*my call*; the reverse DCF is a numerical solve and financial-grade decimals buy nothing there). Display rounds; storage does not.

### 6.6 The engine

**Policy values** (`design.md` 6.2): r 9%, terminal growth 3%, runway 5/10/20 years by moat class, margin of safety 45/35/25% by moat class, fair band 0.85 to 1.15, trim 1.5, Wide-moat terminal ROIC cap 13%, minimum 3 mature peers (unused in this cut). Plus the `mech/1.2` rules: moat class from the GuruFocus score (8 to 10 Wide, 4 to 7 Narrow, 0 to 3 None, no score None); growth belief for years 4 to N = the Base Rate Book median ten-year net-income growth for the company's sales class plus 2 points for inflation. All of these live in one versioned policy file with a source line per value. The eleven base-rate medians and their sales-class boundaries go into that file in Fairband's own format with attribution (D6). The sales class reads trailing revenue in current dollars against the book's 2015-dollar boundaries, and the policy file says so (*my call*; D6 forbids inventing an inflation index).

**Trailing figures** (*my call*, from the builder review). "Trailing" in the engine means the trailing twelve months: the sum of the last four reported quarters for revenue, operating income, net income, GAAP EPS, stock compensation and free cash flow. Trailing EPS, EPV, the SBC basis test, the non-recurring gap, the trailing P/E, Mature Stable's E and the `mech/1.2` margin flag all read these. The classifier series, the ROIC aggregate and every history read fiscal years. A company with fewer than four quarters on file falls back to the last fiscal year for its trailing figures and is flagged "trailing on fiscal year".

**Deciles across refreshes** (*my call*, from the builder review). The growth and margin-slope deciles are a universe-level result. A full refresh computes them after it has every company's income statements and stores them with the refresh record. A scoped refresh (named tickers, or the development command) reuses the latest stored deciles, and the snapshot cites the refresh they came from. With no deciles stored yet, a scoped refresh classifies nothing: the snapshot says "no universe deciles yet" and carries no value. So the first value on the screen appears after the first full refresh.

**The classifier** (`design.md` 5, Decided). Build details from 5.7, settled (*my calls*):

- Each series ends at the last fiscal year on file. No trailing-twelve-month point in this cut.
- The free cash flow for the sign check is the last fiscal year's operating cash flow less capital expenditure.
- Growth needs at least two fiscal years (the CAGR runs over the span available); a slope needs at least three. A company with fewer than five fiscal years (the trend window, `design.md` 5.7) is classified from what exists and flagged "short history" (amended 2026-11-01; the first draft said four). A company with fewer than two years is unclassified: no phase badge, refusal reason "fewer than two fiscal years".
- A revenue of zero now or three years ago is Start-up, as 5.3 says. A revenue three years ago that is unknown is not zero; it falls under the short-history rule.
- For a negative margin, a trend slope of exactly zero means not improving: Young Growth. A margin of exactly zero counts as positive and is flagged.
- The deciles are computed over the companies the engine values: the admitted universe minus the unclassified. The excluded sectors never enter.
- A series whose reported currency changes between years is flagged; the growth ratio is still computed.

**Mature Growth** (`design.md` 6.5 and 6.6, method v1.7 Steps 1 to 10, `mech/1.2` rules). The engine computes:

1. **Year 1, the NTM anchor.** The sum of the next four quarterly consensus EPS from FMP, converted to net income with the current diluted share count. The SBC basis test of `mech/1.2` applies with FMP street actuals in place of GuruFocus actuals (*my call*; the design prefers FMP): when street trailing EPS exceeds GAAP trailing EPS by at least half the after-tax SBC per share, the consensus excludes SBC, and the engine subtracts after-tax SBC held at its trailing share of revenue. The tax rate for that conversion is the statutory rate of section 6.6 below. An anchor at or below zero is a refusal: "no positive forward anchor". A forward P/E below 2 is a unit error and a refusal.
2. **Years 2 and 3.** The first two fiscal-year steps of the FMP annual consensus net income, from the base year that holds most of the NTM window (a tie takes the later year). Where net income consensus is absent, the EPS steps are used and the row is flagged "path on EPS". A step the consensus does not reach takes the belief. A path year with fewer than 5 analysts is flagged "few analysts".
3. **Years 4 to N.** The growth belief from the policy rule. N from the moat class.
4. **The reinvestment charge.** Cash to equity in year t = net income in year t × (1 − g in year t+1 ÷ ROIC). ROIC in the runway years is the ten-year aggregate; in the terminal year it is the terminal ROIC. The timing convention is `design.md` 6.5's proposal, adopted (*my call*).
5. **Terminal value** = net income in year N × (1 + 3%) × (1 − 3% ÷ terminal ROIC) ÷ (9% − 3%), discounted N years.
6. **Value at belief** = the present value of the cash to equity for years 1 to N plus the terminal value, divided by the current diluted share count. One share count for every year (`design.md` 6.5 change 2).
7. **Implied growth** (Step 4c): the uniform growth for years 4 to N at which the value equals the price, solved numerically. Also at each of the three runways, and at each of three ROIC values: the company's aggregate ROIC, 15% and 9% (*my call* for the three values; a policy value with no source).
8. **EPV** = normalized trailing EPS ÷ r, where normalized trailing EPS is GAAP trailing EPS less the GuruFocus non-recurring gap (`mech/1.2`). Growth share of price = 1 − EPV ÷ price. EPV never sets a level.
9. **Levels and stance** (`design.md` 6.3) on the value at belief.
10. **Expected return** (Step 9) over 3 years: income from dividends and net buybacks, growth from the path and the belief, repricing from the value against the price.
11. **Clean and reported trailing P/E, forward P/E** (Step 7). The own-history zones wait for a later piece.

**ROIC** (`design.md` 6.6 with D2, D3, D3a, D3b, D9, D17):

- Invested capital per year = operating working capital (current assets less cash and investments, less current liabilities excluding short-term debt and the current part of leases) + net property and equipment + lease right-of-use assets where the balance sheet reports them + goodwill + acquired intangibles (D17 method). Cash and marketable securities are excluded (D3b). Lease assets enter only where reported; years before lease capitalization are flagged "leases not on balance sheet", with no reconstruction (D3a's limitation stated, not fixed, in this cut; *my call*).
- A balance-sheet line the issuer does not present, on a balance sheet whose totals are present, contributes nothing to its component. The value is stored as an estimate with method `not-presented-as-nil-v1` and the row is flagged "line not presented: <field>". The year stays in the aggregate. Apple presents neither goodwill nor intangibles for FY2018 to FY2025, so this rule is what keeps ten years of Apple in the aggregate (*my call*, under D17's estimation principle; the issuer's own choice not to present the line is the evidence that it is small). A year drops out only when a required total is absent: total current assets, total current liabilities, net property and equipment, or operating income.
- NOPAT per year = operating income × (1 − statutory marginal rate). The rate is the OECD combined central-plus-subcentral statutory corporate rate for the company's country and the fiscal year, from a policy table with the OECD source and version (D3, D9). The company's country is the FMP profile's country (the headquarters), and the drawer says so (*my call*). The builder populates the table for the countries in the universe. A fiscal year later than the newest year in the OECD table takes the newest year's rate, stored as an estimate with method `tax-rate-latest-oecd-year-v1` and flagged "tax rate carried forward to <year>" (*my call*, from the builder review: the table lacked 2026 on 2026-10-29, and every June and calendar 2026 filer would otherwise be refused). An earlier missing country-year is a refusal for that company: "no statutory tax rate for <country> <year>". No other carry-forward.
- Average capital per year = (opening + closing) ÷ 2 (D2). Ten years of NOPAT need eleven balance sheets.
- Aggregate ROIC = sum of ten NOPATs ÷ sum of ten average capitals. With fewer than ten years, use at least five and flag "ROIC on N years"; below five, the charge uses the terminal ROIC in every year and the row is flagged "ROIC unavailable".
- A sum of average capital at or below zero sets the charge to zero and flags the row.
- Terminal ROIC: 9% for Narrow and None; for Wide, the lower of the aggregate and 13%, never below 9%.

**Mature Stable** (`design.md` 6.11; details *my calls*):

- Normalized earnings E = trailing GAAP net income less the non-recurring gap. When the margin flag of section 6.7 fires, E is scaled by the ten-year median operating margin ÷ the trailing operating margin, and the row says so. This is the "margins at their 5- to 10-year norm" rule read as a proportional scaling; it is an approximation, written in the policy file as such.
- EPV = E ÷ r. Stable-growth value = E × (1 − 3% ÷ terminal ROIC) ÷ (9% − 3%), with the ROIC rules above.
- The value at belief for the levels is the stable-growth value. EPV is shown as the no-growth value. For Narrow and None the two are equal, since the terminal ROIC is 9%; for Wide the stable-growth value is at most 15% above EPV. This settles `design.md` 15.8 for the mechanical screen only; an agent may override later.
- The dividend-to-FCFE test and the control layer are out of this cut.

**The other four phases.** The snapshot carries the phase, the classifier evidence and the refusal reason "<phase> route not built yet". Start-up rows say "Start-up: no value by design; the price-implied requirement comes with the Start-up route".

**Result shape.** Every route returns the same object: the value or `null`, the levels or `null`, the stance or `null`, the phase and its evidence, the tagged inputs, the intermediate results, the flags, the refusal reason or `null`, the policy version, the method version. A refusal has `null` values and a reason; it is never an exception that drops the row.

**Determinism.** The same inputs and the same policy version give the same result bit for bit. No randomness in these two routes.

### 6.7 Flags

A flag warns and never changes a value or a stance. Each has a short word for the column and one sentence for the drawer.

| Flag | Rule |
|---|---|
| Classifier check | any of the three checks in `design.md` 5.5 |
| Margin above history / Possible cycle peak / Newly profitable | the `mech/1.2` margin flag, verbatim |
| Few analysts | a path year with fewer than 5 analysts |
| Large non-recurring item | the non-recurring gap is 5% or more of trailing EPS, in either direction |
| Equity raise / Negative free cash flow / Heavy capex | the three `mech/1.2` gate tests, kept as flags; the gate itself is retired because the classifier now answers the phase question (`design.md` 15.7, *my call*) |
| Charge zeroed | invested capital at or below zero |
| Long runway, high growth | runway 20 with a belief or an implied growth of 10% or more |
| Value spread | the value at belief moves 30% or more across the three ROIC values or the three runways (policy value, no source) |
| Short history / ROIC on N years / ROIC unavailable / Leases not on balance sheet / Path on EPS / Currency change | as defined in 6.6 |

### 6.8 The validity window

`design.md` 8. The window ends at the next earnings date from FMP; when none is known, three months after the data date. The states follow the design system: current until two thirds of the window, then aging, then expired. An expired row keeps its figures and shows the mark.

### 6.9 Storage

One SQLite database in the XDG data directory (`~/.local/share/fairband/fairband.db` by default; D10). Keys in `~/.config/fairband/keys.toml`, mode 0600, read once at startup; the `FAIRBAND_FMP_KEY` and `FAIRBAND_GURUFOCUS_KEY` environment variables override for development. The repository never holds either.

Tables, as the logical shape (*my call*; the builder pins columns and indexes):

- `companies` — one row per admitted or sector-excluded listing: symbol, name, exchange, sector, industry, country, currency, cap band, market cap, eligibility, exclusion reason, observed date.
- `vendor_responses` — one row per vendor call: provider, endpoint, parameters, symbol, HTTP status, observed time, payload. Secrets scrubbed before storage.
- `facts` — normalized values: company, dataset, fiscal year or period end, field, decimal text, unit, currency, as-of, observed, entered, response id, missing reason. One row per field per period.
- `estimates`, `quotes`, `price_facts`, `earnings_dates`, `vendor_scores` — dated observations, each citing its response.
- `policy_versions` — version, content, hash, created.
- `refreshes` and `refresh_items` — the refresh record and per-company progress.
- `snapshots` — one per company per refresh: the full result object of 6.6 as JSON, plus indexed columns for the screen (phase, value, levels, price, stance, dates, flags, refusal reason, policy version, method version).

Rows are appended, not updated, except the refresh progress rows. A later refresh never deletes an earlier snapshot or the responses it cites. The screen reads the latest snapshot per company.

Schema migrations are numbered SQL files applied in order and recorded in a `schema_versions` table.

### 6.10 The web server

FastAPI and Uvicorn, one process, bound to `127.0.0.1` on a configurable port (default 8470, *my call*). Started by `python -m fairband serve`, which also runs pending migrations. Routes:

| Route | Does |
|---|---|
| `GET /` | the page |
| `GET /static/...` | the design system copy, the vendored React files, the app script |
| `GET /api/screen?sort=&dir=` | all rows for the table |
| `GET /api/groups?by=sector\|phase\|cap` | the group view |
| `GET /api/companies/{symbol}` | the drawer's content: the latest snapshot in full |
| `POST /api/refresh` with `{kind: full\|price, symbols?: [...]}` | starts a refresh; refuses if one runs |
| `GET /api/refresh/current` | progress |
| `POST /api/refresh/cancel` | stops after the current company |

The refresh runs in one worker thread owned by the server process. The HTTP handlers never call a vendor.

The page is one HTML file and one app script written against the design system's React bundle with `React.createElement`. No build step, no Node toolchain. The design system archive is unpacked into the package's static directory; that copy is the one the repository owns and may extend (the extra columns). The archive under `docs/design-system/` records where it came from.

### 6.11 Toolchain

uv with `pyproject.toml` and `uv.lock`; CPython 3.13; Ruff (lint and format); mypy strict at the adapter boundaries; pytest. httpx for vendor calls with redirects refused, TLS verified, `trust_env` off, bounded timeouts and at most three attempts on transport errors, 408, 429 and selected 5xx; never on 401, 402, 403 or a shape failure. GitHub Actions runs lint, type check and tests on every push. `.gitignore` excludes the data directory and any local key file.

Not in this cut (*my call*, to keep the ceremony small): Playwright and axe, Bandit, pip-audit, pre-commit hooks, Gitleaks. The key-scrub test in section 7 covers the one hygiene rule that matters most.

## 7. Tests the builder must write

Test-driven, per the superpowers workflow. The named numbers are acceptance numbers.

1. **Terminal multiple** (`design.md` 6.5 table): with r 9% and terminal growth 3%, the terminal multiple of final-year earnings is 17.2× at infinite ROIC, 15.5× at 30%, 13.7× at 15%, 13.2× at 13%, 11.4× at 9%.
2. **The worked example** (`design.md` 6.5): Wide moat, N 20, consensus path 12% then 10%, belief 8%: the value is 25.5× NTM earnings at a 30% ROIC, 22.4× at 20%, 19.3× at 15%; at a 20% ROIC the price needs 11.8% growth, not 8%. These figures hold when the terminal ROIC equals the runway ROIC. With the Wide-moat cap of 13% applied, the builder review computed 23.6×, 21.2×, 18.9× and 12.6%. So the test calls the engine core with the terminal ROIC passed explicitly: once equal to the runway ROIC, to reproduce the design's figures, and once at the capped value, to pin the production rule. The builder reports any difference from the design's rounded figures.
3. **Aggregate ROIC** (`design.md` 6.6 example): seven years of 20 on 100, year 8 −10 on 100, year 9 20 on 20, year 10 22 on 110 gives 18.5%, not the 25.0% average or the 20.0% median. (The example uses year-end capital; the test states its capital series explicitly.)
4. **Classifier**: hand-built series for each of the six phases, each check flag, the short-history and unclassified cases, the zero-slope and zero-margin cases, and the decile boundaries.
5. **Levels and stance**: each of the five bands of `design.md` 6.3 and the three-word form.
6. **Refusals**: every refusal reason in section 6.6 produced by a crafted input, with the row still present.
7. **Adapters**: each endpoint parsed from a stored fixture. Fixtures are synthetic or hand-trimmed, carry no key and no bulk vendor data. A live smoke test runs only when keys are present and is skipped in CI.
8. **Key scrub**: a test that builds every request URL and every log line the adapters can emit with a fake key and asserts the key never appears in a URL path or query string that is logged or stored, nor in any stored response.
9. **Refresh**: a refresh over three fake companies stopped after the first continues with the second; a 24-hour-fresh company is not fetched again; a failing company gets a refusal row.
10. **Migrations**: an empty database migrates to the current schema; a database at the previous schema migrates forward.

## 8. Acceptance

The founder accepts this cut when:

1. `python -m fairband serve` starts, and the page renders with the network cable out (fonts and scripts local).
2. A full refresh completes over the universe, or continues after being stopped once, and every admitted company has a row with a value or a refusal reason.
3. After that refresh, `AAPL` and `MSFT` each show a Mature Growth or Mature Stable value, the drawer shows every tagged input with its dates and source, and the arithmetic reproduces from the drawer's intermediate results.
4. The calibration count (goal 7) is written to the refresh record and shown on the page.
5. The key-scrub test passes and a grep of the database and the logs for the key finds nothing.
6. All tests pass in CI.

## 9. Left to the builder

- Package and module layout; the exact SQL; indexes; the normalized field catalog (derive it from what 6.6 reads, nothing more).
- The exact FMP routes and parameters for the current API version, recorded per stored response.
- Decile ties; the numerical solver and its tolerance; how the engine handles a consensus year in another currency (the growth ratio is currency-free; the anchor is not).
- Worker count, timeouts, retry delays, as policy values.
- The port, the page layout within the design system's rules, the drawer's exact arrangement.
- The CI workflow file.
- A `CLAUDE.md` for the repository that points agents to `docs/legacy/design.md`, this document and the design system's brand book, and states the key and vendor-data rules from `design.md` 13.

## 10. Order of work

A plan should reach a visible result early:

1. Toolchain, package skeleton, policy file, migrations, key loading, the scrub test.
2. The engine: Mature Growth and Mature Stable, with the acceptance numbers, on hand-built inputs.
3. The classifier, on hand-built series.
4. The FMP and GuruFocus adapters and the store, for one ticker; `python -m fairband refresh AAPL`. Until the first full refresh, its snapshot has no phase and no value ("no universe deciles yet"); the data path and the drawer are what this step proves.
5. The page with one row and the drawer.
6. The universe, the full refresh with progress and continuation, the price refresh, the group view, the calibration count. The first value appears here.

## 11. Foreign filers and ADRs (founder decision, 2026-10-31)

`design.md` section 2 puts foreign filers and ADRs in the universe (Decided). They stay in the universe and get a row. In this cut they get no value: the snapshot carries the phase where the classifier can assign one and the refusal reason "foreign filer: currency and share-unit handling not built yet". A company is a foreign filer when its statements' reported currency is not USD, or when the FMP profile marks it as an ADR.

Valuing them is the piece right after the screen. It needs three things this cut does not include: the statement currency converted to USD at a dated rate (FMP forex history), the ADR ratio (GuruFocus `depositary_receipt_ratio`, already in the summary response this cut stores), and the annual consensus route for the NTM anchor, since most foreign filers report twice a year (`mech/1.2`, I388). The known traps are in the stocks issue log: mixed currencies between years (I290) and the annual route's window (I388).

The founder chose this over including them now, to keep the first cut small and the screen correct for U.S. filers on day one. Roughly one listing in six above $2 bn is affected, including TSM, ASML, SAP, NVO, TM and SHEL.
