# Backlog

One list of work not started. Specs, plans and `docs/method.md` hold the detail; an item here is a
pointer with the origin and the figure that justify it. **Now** is ordered: the next spec starts at
the top. **Later** is not ordered; its items are grouped by the files that change. **Questions**
need the founder's call before anyone builds. An item moves to **Done** with the commit that closed
it. IDs are never reused. An origin `FC-n` is a feature candidate of the product brief
(`docs/legacy/product-brief.md`), listed in Section 11 of the earlier build's
`discovery/synthesis.md`, which is outside the repo.

Types: feature (new behaviour), fix (wrong behaviour), debt (code, test or document cleanup),
question (the founder decides).

At the end of each plan, the ledger's deferred minors and parked findings move here, one row per
file or theme, before the workspace is deleted.

## Now

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|

## Questions

| ID | Question | Raised | Options |
|---|---|---|---|
| B-3 | Keep the Retry-After cap? A numeric Retry-After holds at most `rate_limit_hold_s` (60 s). | plan A, Task 2 ruling; spec 5.2 amended | keep the cap (as built) or honour any length (a 3600 holds every worker an hour) |
| B-4 | Chip colours for Below and Above fail the brand book's 4.5:1 contrast: below 2.99 dark and 3.51 light; above 2.90 and 3.62; well above 4.10 in dark. | plan B, Task 6 | change the step-2 and step-3 chart tokens in the design system, or accept the contrast |
| B-5 | The band meter's zones carry no word; the page turns the scale off and lists the levels under the meter. The brand book says every zone carries a word. | plan A, Task 6 | add zone words to the component, or keep the list |
| B-6 | A consensus check flag on every phase: next-3-year consensus revenue growth ranked on the phase deciles maps to a different phase, with at least 5 analysts; the phase stays. And the thin-step rule: "a thin step takes the belief" would give QCOM $157.71 and move the Mature Growth median value ÷ price 0.824 → 0.708 (421 of 716 rows have a thin year-3 step). | founder, 2026-11-02 (QCOM) | adopt the flag only; adopt both; leave as built |
| B-8 | AAPL's three-year aggregate return reads 9236% (invested capital near zero), so its runway charge is nil. | readout, 2026-11-02 | floor the capital, cap the return, or accept |
| B-46 | The Base Rate Book's medians and 90th percentiles ship in policy v5 under an attribution line; the brief lists the book as a source that cannot ship. | brief, uncertainties; design.md 6.13 | keep the attribution; replace the figures with a public source; ask the authors, before the repo goes public |

## Later

### Engine and routes

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-9 | Tier 2: the agent's research and stance per company; the stance column is empty until then | feature | founder, 2026-11-03 | the engine's value is a best effort; the stance is the agent's call after research; the parts are B-48 to B-59 |
| B-10 | Young Growth's failure probability is "unavailable" (`failure-not-charged`, 25 rows); the Decline route's rating-to-default table could serve it | feature | growth routes readout, 2026-11-03 | one table can serve three routes |
| B-11 | `route_decline.py` (730 lines): `_decline_rate` raises ValueError when evidence is None (unreachable; a guard refusal keeps the contract); six helpers imported from `route_revenue_growth` belong in a shared module, `_row` in `distress.py`, `_margin` in the core; the DATA input `equity` (book) and the intermediate `equity` (going concern) share a name; test gaps: path-held with decline-rate-floored, the order of four flags, the π = 1 floor edge | debt | plan B, Task 4 review | |
| B-12 | `runoff.py`: `runoff_rates` with fewer than 3 years silently returns three rates; `RunoffValuation` built positionally (14 fields); no test of a negative firm value through `runoff_equity` alone | debt | plan B, Task 3 review | |
| B-13 | `distress.py` and the loader: no check that every `synthetic_rating` row has a `default_probability_10y` entry (KeyError in the Decline route); `_ratio` rejects only a zero denominator while `altman_z` rejects at or below zero; D found by position; `rate()` assumes a positive interest size | debt | plan B, Task 2 review | |
| B-14 | `route_start_up.py`: the repriced market cap is the stored one moved with the price (misleads after an equity raise until the next full refresh; the drawer should say so); "the least revenue in [0, 1e13]" overclaims when the enterprise value falls with year-10 revenue; `tax-loss-history-unknown` can go stale on a reprice; `operating_income_fy` cited with value None; the exhausted-floats guard, a Wide reprice and a Narrow case untested; a Wide row with an input reason still lists `terminal_roic` | debt | plan B, Task 5 review | |
| B-15 | Growth routes: the tax-loss flag sentence says "unknown in both directions" (both unknowns lower the value); the "years 4 and 5" sentence assumes H = 5; `tax-loss-history-unknown` fires only on a forecast loss year; `g_T` lives on both `RevenuePath` and `RevenueCharge`; `own_sales_to_capital` repeats `roic.marginal_return`'s span logic; the industry fallback can leave fewer countable peers than FMP's list | debt | growth routes, final review 2026-11-03 | |
| B-16 | `roic.py`: "five-year" and "three-year" are fixed words while the windows are policy values; the unavailable note reads `_MIN_YEARS`, not the argument; tests missing for capital shrinking with NOPAT rising, growth at the 20% boundary, policy-replaced windows | debt | calibration, 2026-11-02 | |
| B-17 | `route_mature_growth.py`: the value-spread slice assumes two `roic_sensitivity` values; the implied growth is solved twice for the `runway` key. `route_mature_stable.py`: `im["growth_route"]` indexed unguarded; the `runway_return` input is tagged DATA even when its value is a policy number | debt | calibration, 2026-11-02 | |
| B-18 | `classifier.py`: `_checks` takes 12 positional arguments with same-typed neighbours; a no-margin company with a bottom growth word and fewer than three falls is unclassified with no `revenue-falling` flag; `steps` computed and unused; no test for a 4b company carrying both `growth-word-disagrees` and `revenue-falling` | debt | plan A, Task 4 review | |
| B-19 | Designation: the groups' share recomputes price ÷ value against the edge instead of reading the row's `priceToValue`; the drawer's in-band figure reads the current policy's edges, not the snapshot's; the meter's own "% below fair value" figure (bundle.js, about line 433) rounds across a band edge | debt | plan A, final review | one figure reads 15.0% at a ratio of 0.8499 |
| B-20 | Peers: computed for every company, not only the growth phases (about 28 s a value stage); a per-stage memo symbol → PeerFigures; the drawer does not list the peers behind the sales-to-capital and ROIC medians; `path.cap` and `revenue_path.hold` show as 0.15, not 15%, in the drawer's generic list | debt | growth routes, Task 4 and final review | |
| B-47 | A flag for a large price fall with no change in the consensus, read against the consensus stored at the previous refresh; no new endpoint | feature | design.md 4.2 | the top of a screen collects errors; a fall with a revision is a different row from a fall without one |
| B-76 | `policy/settings.py`: only 4 of the 40 catalogue rows are pinned against spec 8.2 (a table-driven test would lock the rest); `check()`'s docstring misstates a cross-field rule's order; a 401-digit integer in `PUT /api/settings` raises `OverflowError` (a 500) in `_num`; `universe.exchanges` is compared with its default in order | debt | final review, 2026-11-04 | |
| B-77 | `returns.py` keeps `horizon: int = 3` though spec 8.3 says the policy value replaces it; `docs/method.md` uses H for both the repricing horizon and `high_growth_years` | debt | final review, 2026-11-04 | |

### Tier 2 and agent access (new files; B-9 is the umbrella)

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-48 | MCP server: an agent connects from Claude Code, Codex or Claude Desktop over stdio, started by the host; finds the tools; reads everything the page shows (the screen, snapshots, financials, peers, price facts, reports, notes, watchlists, the inbox, the ledger); starts a refresh for a scope and follows it. No token: the request-header rule and the 127.0.0.1 binding stay; a token comes only with a network transport | feature | FC-36, FC-37, FC-37a, FC-46; founder 2026-11-04 | the agents are the second surface; every write below arrives through it |
| B-49 | Provenance ledger: every agent write records the agent, the playbook role, the time and what it rests on | feature | FC-39; concerns A and G | |
| B-50 | Overrides: one input per override with the old value, the new value, the reason, the evidence, a tag (lasting, or tied to a period) and the snapshot it was made on; locked inputs (r, g_T, reported data) refused; a belief above the sales class's base-rate 90th percentile needs extra evidence; a period-tied override drops at the next full refresh or when the data it corrected changes, so the corrected value is stored | feature | FC-27, FC-28, FC-29; design.md 7.3 | inputs, never numbers |
| B-51 | Value bridge: the engine recomputes with the overrides and shows one line per override in the method's step order, from the mechanical value to the reviewed value | feature | FC-18; design.md 7.4 | |
| B-52 | Key judgments: phase, moat, belief, ROIC and target margin, each with the bull view, the bear view and the decision | feature | FC-30; design.md 9.3 | |
| B-53 | Reports: the valuation review and the full report; the ten-section reader layout with Appendix A (the audit) and B (the glossary); stored as Markdown; the number check rejects a report with a number no tool output gave. Needs segment data, 10-K text from EDGAR and the Beneish M score, which the engine does not fetch | feature | FC-31, FC-32, FC-02; design.md 9 | readability is a hard requirement |
| B-54 | Notes: dated notes on a company by the user or an agent, with an override's provenance | feature | FC-33; founder 2026-10-27 | |
| B-55 | Kill criteria and dated news items, recorded by an agent; no automatic trigger check, the agent checks them on the next review | feature | FC-34; founder 2026-11-04 | |
| B-56 | The mechanical-versus-reviewed log: both values at every update, with the phase and the method | feature | FC-20; design.md 7.3 | the measure of whether the agents help |
| B-57 | The playbook: the Tier 2 roles as skills the user installs in the agent host; its first step is "check the inbox" | feature | FC-41 | |
| B-58 | Work inbox, two ways in. A button on a row posts an item: the symbol, the mode (valuation review or full report), a note and the snapshot at posting. A company on a watchlist (B-67) whose validity window expired is posted once per expiry as a valuation review, when the inbox is read on the page or over MCP, never while an item for it is open; it drops while pending if the company leaves every watchlist. States: pending, claimed (agent, time), done (linked to the report or notes), declined with a reason. MCP tools: list, claim, complete. Later: ledger proposals in the reverse direction (B-60) | feature | FC-40; founder 2026-11-04 | the user hands the agent its work through Fairband, not through chat |
| B-59 | Report export: a Markdown download of the stored report, and a print stylesheet for the browser's save-as-PDF; a server-side PDF only if the print result falls short | feature | FC-35; founder 2026-11-04 | the stored copy is the one that passed the number check, a week later too |

### Portfolio (new files)

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-60 | Transaction ledger: append-only rows the user records; a fix is a reversing row; an agent may propose a row the user confirms | feature | FC-42; design.md 10 | |
| B-61 | Positions, cash and market value from the ledger, updated at each price refresh | feature | FC-43; design.md 10 | |
| B-62 | Portfolio review by an agent over MCP, on request only, reading the ledger and the values; no strategy, no rules | feature | FC-44; design.md 10 | |

### Refresh and vendors

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-21 | Limiter: the 16-thread test cannot detect a missing lock (a yielding fake clock would); no run-level test with a paced client; the wall clock stalls acquires on a backward clock step; `run.py`'s docstring says only an FMP call runs past `deadline_s` (a GuruFocus 429 does too); GuruFocus is unpaced by design | debt | plan A, Task 2 review | |
| B-22 | Backfill: branches untested (unparseable payload, partial fields, no symbol); every valuing refresh scans all statement responses, one `fields_stored` query each; the stage cannot be cancelled and reports no progress; it also runs on the 429-stopped path | debt | plan B, Task 1 review | |
| B-23 | `run.py`: a revalue on a store with no universe reports `universe.admitted` as the count of companies with snapshots; no revalue-specific cancel or failing-company tests; `inputs_statements.py` (491 lines) holds `country_for` and `stored_payload` to avoid an import cycle | debt | calibration and growth routes reviews | |
| B-25 | A `--force` flag to refetch inside the 24-hour reuse window | feature | offered 2026-11-03, not requested | |
| B-26 | Ultimate-only FMP content (earnings call transcripts, for one) is unused; the legacy design assumed the Premium plan | feature | 2026-11-01 | |
| B-63 | Refresh scope by cap band (all Mega, or Mega and Large) as a CLI option and an MCP argument, not a page control | feature | FC-06; founder 2026-10-27 and 2026-11-04 | the page has full, price and revalue; a symbol list covers the rest |
| B-64 | Point-in-time: as-of reads over the stored observations, which are dated and appended, so a revalue can run as of a past date; a backtest command only once B-56 has data | feature | FC-04; design.md 11.5 | |
| B-85 | Refresh tests read `Refresh`'s private `_fmp`, `_gf` and `_secrets`; nothing tests a reset of a name with no row or a write over a stale row | debt | final review, 2026-11-04 | |

### Universe and data

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-28 | Foreign filers are refused: currency and share-unit handling not built (196 rows on 2026-11-01; 13 of the 112 Decline rows) | feature | first live run | |
| B-29 | Notes and preferreds: DUKU and SOJC stay admitted; 9 fetch failures were all preferreds and notes without statements; test gaps: `\bpreferred\b` alone, the industry rule beating the name rule, a listed admission skipping the name and symbol patterns, a manual exclusion beating a symbol pattern | debt | growth routes and plan A reviews | |
| B-30 | Test fixtures label refreshes "fairband-policy-v1" while building results under v2; `env_valued` and `snapshots_of` copied into `test_run_revalue.py`; `load_policy` on the v1 path raises on the missing v2 values and nothing calls it | debt | calibration, 2026-11-02 | |
| B-65 | A free data path for basic users: SEC EDGAR statements and a free price source, with the fields the routes need | feature | FC-51; founder 2026-10-27, deferred not refused | adoption stays small while the data is paid-only |
| B-66 | Banks, insurers and REITs, each with its own route per phase | feature | design.md 2 | excluded "for now"; six financial industries are out of the universe today |

### Page

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-31 | FIND re-renders and re-lays out the whole table on every keystroke: 0.1 to 0.3 s on 1,759 rows, measured headless. Debounce the narrowing or virtualise the body | fix | screen controls, 2026-11-02 | |
| B-32 | Industry filter (121 names) and the failed-count button; the page counts a full refresh's failures from refusal prefixes | feature | first live run, 2026-11-01 | |
| B-33 | Drawer: the "π" head needs a case override (the glyph is outside the font subset) and the "Needs by yr 10" wording; the Rating column's "—" for no net debt looks null and sorts alphabetically; Z″'s "No score" reason is wrong without balance years; the Decline sales-to-capital note always says "mature peers' median" (the industry fallback too); `app.js` is 1,352 lines; tests do not pin the drawer's `im.*` keys to the routes' intermediates nor `SIGNALS` to `piotroski_f`'s names; no row test for an unavailable rating | debt | plan B, Task 6 review | |
| B-34 | Meter head: the chip, the "% below fair value" figure and the caption state one fact up to four times; dead CSS `.fb-zone > span`; the bundle's default scale still prints Buy and Trim (unused); the margin % is recomputed from the levels, not read from the rule input | debt | plan A, Task 6 review | |
| B-35 | Sticky bar: a browser without ResizeObserver loses the sideways behaviour; while `#screen` is hidden (Groups view) the observer writes `--scroller-width: 0px` and the first frame back can raise the loop error (skip the writes when `main.clientWidth === 0`) | debt | plan A, Task 7 review | |
| B-36 | Chooser: reorders its rows while open (the spec asks for table order first); the drop flag lasts until the next press; Clear on FIND drops focus to body | fix | screen controls and growth routes reviews | |
| B-37 | Pre-existing: the drawer scrolls sideways 17px (the Inputs table is too wide); dark-mode scrollbars and checkboxes stay light; the status line wraps to six lines; the header sits inside `main` (no banner landmark) | fix | screen controls hand check, 2026-11-02 | |
| B-38 | Page-script tests pin source lines and run no logic; thin pins on Cancel's disabled state, the unknown-stage fallback and the narrowing clauses; two tests pin incidental line wrapping; exact float equality in the repriced-cap check | debt | screen controls and plan B reviews | |
| B-68 | History: a per-company view of value, phase and designation across snapshots; a "what changed" list after a refresh; the price change since the valuation on the row | feature | FC-24, FC-25, FC-06; journey J2 | snapshots are appended, but the page reads only the latest |
| B-70 | The phase multiples the stored data gives: EV/Sales, EV/forward sales, PEG, EV/EBITDA, P/B; not EV/TAM, EV/users, EV/subscribers or EV/liquidation value | feature | FC-19; design.md 9.5; founder 2026-11-04 | the three P/E, EPV and the growth share exist; the NCAV figure stands in for liquidation |
| B-71 | Ownership evidence in the drawer: institutional ownership, guru holdings and their quarterly moves, insider transactions, each with its as-of date; evidence only, never a value or a designation | feature | FC-49; founder 2026-10-27 | |
| B-72 | Recent picks across the universe: guru buys and sells and insider buys from FMP's or GuruFocus's endpoints, joined to the row's value and designation; no filing parsing | feature | FC-50; founder 2026-11-04 | |
| B-78 | `watchlists_api.py`'s `_refusals` maps any `KeyError` to a 404 (a `NoWatchlist` error would be safer); `app.js`'s `getJson` drops a 409's sentence, so a refused stored setting reads "the server answered 409. Reload the page" on the screen, groups and drawer | debt | final review, 2026-11-04 | |
| B-79 | The watchlist popup in `app.js`: the boxes can disagree with the server after a failed write followed by a quick change; focus is lost after Add creates a list; it copies `menuSection`'s markup and finds its mark through a global capture listener because `onWatch` passes no element | debt | final review, 2026-11-04 | |
| B-80 | The Watchlists view: Delete's dialog does not hold focus; a failed load of the lists or the rows leaves the view silent; the old name flashes after a rename; focus falls to body after a popup removal or after Create when its target is not drawn yet; `refusal()` and `found()` copy `app.js` | debt | final review, 2026-11-04 | |
| B-81 | The Settings view: a revalue shorter than the first poll leaves the notice up; Revalue now re-enables for a moment after a 200; errors have no `aria-describedby`; focus can fall to body after a save; a server detail ending in a period doubles it; the 409 and 503 sentences are copied from `controls.js`; a stale `typeIn` comment; a duplicated CSS rule; the disabled primary Save keeps a teal border; the drawer clamps price ÷ value with the current edges while the word was set under the snapshot's settings | debt | final review, 2026-11-04 | |
| B-83 | "Open today's row" matches the symbol inside company names, so KO lands among 16 rows; `find()` clears the filters and leaves an open drawer on another symbol; the Watchlists column sorts by list ids, not names | fix | final review, 2026-11-04 | |
| B-84 | The Methodology page: the High Growth entry's "once the margin is positive" sentence leaves out rule 2 and rule 4a; the 3M table's layout differs from MSFT's; no test checks that each cited unit has a formatter; the page test copies `QUALITY_WARNINGS` and the panel ids instead of importing them; the deciles 404 is read from the error text | debt | final review, 2026-11-04 | |

### Design system (the external artifact; patched copies live in `web/static/design-system/`)

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-39 | The header renders 45px (`.fb-hdr` sets 44px plus a 1px border without `box-sizing`); the FIND focus ring is clipped by the scroll container; `F.Button` drops `aria-expanded` | fix | screen controls and growth routes | |
| B-40 | A new export needs the `fairband:` patches re-applied by hand, 56 in `bundle.js`, 10 in `bundle.css` and 30 in `index.d.ts`; a patch script would remove the hand work | debt | since 2026-11-01 | |

### Documents

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-41 | `docs/method.md`: the 0.6 row says the manual exclusion is "checked before every other rule" (it runs after rules 1–3); section 2's table says the six lines serve "the Decline and Start-up routes" (Start-up reads none) and omits `grossProfit` on the quarterly row; the 6a intro says "the five-year trend's rate" (imprecise on a floored row) | debt | plan A and plan B re-reviews | |
| B-42 | Spec 2026-11-03: one unwrapped line in 10.3; 9.5's intermediates list omits `cash_known`; ASCII and U+2212 minus signs mixed on one drawer row | debt | plan B, final re-review | |

### Operational

| ID | Item | Type | Origin | Why |
|---|---|---|---|---|
| B-44 | Starting the server marks a running CLI refresh interrupted, and a server on an older method fails on newer JSON: stop the server before a CLI refresh. A guard (the server refuses to start while a refresh runs) would remove the rule | debt | growth routes, 2026-11-03 | |

## Done

| ID | Item | Closed by |
|---|---|---|
| B-73 | Methodology page: the life-cycle diagram with the live phase counts, the classifier and each route in plain words with the live policy values, one worked example per route as of a named refresh date, and the sources | 60c8335, 1a02c35 |
| B-2 | Settings and parametization: the 40 policy names of spec 2026-11-04 8.2 on a Settings view, stored as an overlay over the policy file, checked at the write and at the load, with the settings hash on every snapshot | 5cbe67f, a135f31, 66bf1c3, 1512156, c557110, cfc20bd |
| B-67 | Watchlists: named lists, a company on several, the mark and its popup on the screen's rows, the watchlist filter, the Watchlists view and the web API | 8d25b4c, 4e08aca, 9a1bc05 |
| B-69 | A Warnings column counting the eleven quality warnings, sortable, and the Clean filter over valued rows; no composite score | a135f31, 4e08aca |
| B-24 | The price refresh says "policy changed: run a revalue" or "settings changed: run a revalue", not a full refresh | 1512156 |
| B-45 | A revalue from the web API runs without the FMP key; the server builds its worker in every case | 1512156 |
| B-75 | A rule between two settings names both, the Settings page stands the sentence beside the field the user changed, and the save dialog shows the cap bands a changed size floor carries | 088e9a9 |
| B-82 | Phone width: the engine stamp gives way below 560px, the refresh buttons read Prices and Full below 400px, the views wrap below 360px, and the Methodology diagram keeps at least 800px and scrolls sideways | 088e9a9 |
| B-43 | The limiter's proof at full load: a full refresh after the 24-hour reuse window finishes in one run | refresh 15, 2026-11-05: the whole universe fetched 35 hours after refresh 13, 1,602 companies in one run of 11 min 40 s, done |
| B-1 | Gentler Decline route: the run-off reads the consensus past year 3 while a year has a revenue mean above zero and at least `analyst_min` revenue analysts, then the decline rate fades in a straight line to zero by year 10, and the terminal is flat. The revalue of refresh 15 (2026-11-06): median value ÷ EPV 0.66 → 0.73, well above 67 → 63 of 76 valued; BBY 53 → 64, TTE 61 → 71 | 6615025, 3cbfb91, 0ef9b31 |
| B-7 | Are the growth routes too harsh on true growers? 50 of the 63 refused growth rows were a reinvestment that outran the terminal, from an absurd own sales-to-capital or a loss larger than revenue on the margin path; the bound and the dollar ramp value 26 of them; the rest need a margin far above the mature peers' median, which the drawer shows. The own measure counts at half the mature peers' median or more, and a loss larger than revenue moves in dollars (policy v7); 37 growth rows remain refused for the charge, 36 of the 63 and LLYVK | f5c0767, 16e6a07, 0ef9b31 |
| B-86 | The classifier's established test: five profitable fiscal years of the 11 on file count beside three of the last five, an established company is never a Start-up (`revenue-gap`), and a Mature Stable row refused for its trailing earnings keeps the growth cross-check. The seven rows moved: TTWO, AVAV, NBIS and KYIV to Mature Growth; SLAB, SYNA and AXTI to Mature Stable | edba8d7, a0c9b31, 0ef9b31 |
| B-74 | `margin-direction-disagrees` reads deciles 9 and 2, and Stable points to no phase: 744 → 272 of 1,602 rows on the revalue of refresh 15 | edba8d7, 0ef9b31 |
| B-27 | The tax table regenerated from the OECD series for every jurisdiction it covers, Taiwan and Cyprus by hand (`tax-rates-oecd-v2.toml`, 148 jurisdictions): the tax refusals fall from 22 to 1 (TCPA, whose fiscal 2009 precedes the series) | 3de1a30 |
