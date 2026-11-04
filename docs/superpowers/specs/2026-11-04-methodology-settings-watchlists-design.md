# Methodology page, settings and watchlists: design

**Date:** 2026-11-04. **Founder:** Khalid Abanami. **Status:** draft for the builder check.

Three pieces in one plan, chosen by the founder on 2026-11-04 from `docs/backlog.md`: the
Methodology page (B-73), settings (B-2, closing B-24) and watchlists (B-67) with the flag-count
column and the clean filter (B-69). The build is method 0.8 and policy v6. Where this document
and `docs/method.md` disagree after the build, the method describes what runs.

Every `FC-n` below is a feature candidate of the product brief (`docs/backlog.md`, intro).

## 1. What this is

Fairband shows a mechanical value for every company of a useful size, and the investor is asked
to trust it. Today the only statement of the method is `docs/method.md`, written for an
auditor. The founder wants three things next:

1. **A Methodology page** in the app that teaches a reader, in plain words with one real company
   per phase, how a company gets its phase and how each phase's route values it. Every rule
   cites its source, linked where one can be. A life-cycle diagram opens the page.
2. **Settings.** Every valuation judgment, flag threshold, validity rule, universe rule and
   refresh pace that a user may reasonably hold differently becomes a setting on a Settings
   page. The policy file keeps the defaults with their sources. A changed setting says when it
   takes effect, and a changed valuation setting offers a revalue.
3. **Watchlists.** Named lists of companies, filled from the screen or on their own page, with
   a filter on the screen and an API the agents will read later (B-48, B-58). Beside them, a
   flag-count column and a "clean" filter, so the screen can be ranked by cheap and clean.

The three share a header: five views, Screen, Groups, Watchlists, Methodology and Settings.

## 2. Goals

- A reader who has never opened `docs/method.md` can read the Methodology page and say how
  Fairband put a company in its phase and how its value was built, and can follow one worked
  example per phase with today's row one click away.
- Every figure on the Methodology page is one of three things: a live policy value, a live
  count from the latest run, or a figure from a named example as of a named refresh date. No
  number is typed in from memory.
- The 38 settings of section 8.2 can be changed on the Settings page within stated ranges, are
  stored, survive a restart, and are read by the next run, from the page or the CLI alike.
- A snapshot names the settings it was valued under. A price refresh never reprices a snapshot
  valued under other settings; it says "settings changed: run a revalue". The Settings page says
  the same and offers the revalue.
- At the defaults, every value, level, designation and flag is bit for bit what policy v5 and
  method 0.7 give. The derivations of section 8.3 reproduce the v5 numbers.
- A company can be put on one or several named watchlists from its row or on the Watchlists
  page, and removed there; the screen narrows to a watchlist; the lists are readable over the
  web API.
- The screen sorts on a flag count and narrows to rows with no warning flag.

## 3. Non-goals

- The MCP server, the work inbox, notes and overrides (B-48 to B-58). The watchlist and settings
  APIs are what the MCP server will read; nothing agent-facing is built here.
- The expiry rule of the work inbox (a watchlist company whose window expired posts an item).
  That is B-58's, and needs the inbox.
- Editing the tables of the policy file on the page: the base rates, the synthetic ratings, the
  default probabilities, the excluded industries and the symbol and name patterns. They stay in
  the file with their sources. A later piece may open them.
- The method's structural constants (`docs/method.md` 4.1a). They stay in the code.
- A required reason on a settings change. The brand book asks a reason of every write; the
  founder's rule is low ceremony, and the settings' audience is the founder. The reason is one
  optional line per save (8.5).
- A 429 "mode" or a plan-limit probe (B-2 named both). The run already holds, retries and
  stops on a 429 that outlasts its retries, and the status line says so. The hold length is the
  setting; the probe has no FMP endpoint to call. Recorded in the decision log.
- Any new vendor call. The Methodology page's live figures come from the policy and the stored
  snapshots.
- The foreign-filer, history, ownership and multiples items (B-28, B-68, B-70, B-71).

## 4. Anti-goals

- A setting the page accepts and a run that raises on it hours later. Every range is checked at
  the write, and the same check guards the load.
- A snapshot that does not say which settings produced it, or a price refresh that reprices one
  valued under other settings.
- A Methodology page that drifts from what runs: a figure typed in, a sentence that outlives a
  method change, a phase section written from the design rather than from `docs/method.md`.
- A Methodology page that reads like `docs/method.md`: codes, four-decimal figures, sentences
  over 25 words, terms without their meaning.
- A row that becomes a form. The one control a row gains is the watchlist mark.
- A fifth header view that the brand book's header cannot hold at 44px.

## 5. Constraints

- Python 3.13, uv, FastAPI, SQLite; the design system vendored under `web/static/design-system/`
  with `// fairband:` patches re-applied by hand on each export (B-40). New behaviour in the
  bundle is a patch, named and listed in the plan, so a future export can carry it.
- The repository runs no JavaScript tests; page-script tests pin file content in `tests/web/`.
  Behaviour that can be tested in Python is put in Python.
- No key is ever stored, logged or shown; no setting holds a key or a path.
- `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
  passes at every commit.
- `docs/method.md` changes in the same commit as the engine, the classifier, the universe rule
  or a policy value (CLAUDE.md). This piece adds the Methodology page to that rule (7.8).
- The brand book (`docs/design-system/`, `brand-book.md`) governs the look: the tokens, the
  type styles, the words, no icon set, the phase ramp as the only ordered colour ramp.

## 6. The header and the views

`Fairband.AppHeader` takes five views in this order: Screen, Groups, Watchlists, Methodology,
Settings. The view ids are `screen`, `groups`, `watchlists`, `methodology`, `settings`. The
page's panels follow the pattern of `controls.js`: one `<section>` per view, hidden when not
open; the Screen and Groups panels stay as they are.

The URL hash selects the view on load and follows the view when it changes: `#watchlists`,
`#methodology`, `#settings`; `#methodology/<section-id>` opens the Methodology view and scrolls
to that section. No hash means Screen. *My call*: a hash gives the drawer and the README a link
into the page; nothing else is a router.

The AppHeader guideline says "no settings gear" and "the screen's own column chooser handles
the only configuration there is". The founder overrides it on 2026-11-04: settings are a view,
named by the word, not a gear. The `count` of a view is not used in this piece; the inbox will
use it.

At phone width the five views wrap to a second line under the lockup, in the same type style;
the header grows by one line there. *My call.* The 44px budget holds at desktop width: five
words in `control` type fit beside the mark and the engine stamp.

## 7. The Methodology page (B-73)

### 7.1 What it is

A view that teaches. The reader is a value investor who has not read `docs/method.md` and may
not read English first. The sentences follow the rules the output style gives for prose: one
idea each, 25 words or fewer, the plain meaning of every invented term in brackets the first
time, no idiom. Codes stay out of the prose; the flag codes appear once, in the flags section,
beside their words.

Every figure in the page is one of:

- a **live policy value**, filled from `GET /api/policy` (7.4), so a changed setting shows on
  the page;
- a **live count**, the companies in each phase and the universe's size, from `GET
  /api/groups?by=phase`;
- an **example figure**, from a named company's snapshot as of a named refresh date (7.5),
  typed into the page by the builder from the drawer, with the date beside it.

### 7.2 The content, in order

Each section has an `id` for the hash (7.7). The sections and what each must cover:

1. **What Fairband does** (`what`). Three paragraphs: a value for every company of a useful
   size; one engine with one route per phase, because the inputs change with the phase and the
   arithmetic does not; what a value is here (what the business can earn, less what its growth
   costs, discounted at the hurdle rate) and what it is not (a prediction of the price). The
   diagram (7.3) sits under the first paragraph.
2. **The life cycle** (`life-cycle`). The six phases in order, two sentences each in Damodaran's
   words, and what matters most in each (his pricing table: potential market and capital access;
   revenue growth and gross margins; revenue growth and operating margins; earnings growth;
   earnings stability; book value). Under each phase, the live count of companies in it in the
   latest run, and the count of unclassified companies.
3. **How a company gets its phase** (`classifier`). In plain words, in this order: the three-year
   revenue growth, ranked against the whole universe into deciles, gives a growth word (the five
   words, with the live decile edges from the latest run's deciles); the operating margin's
   sign and its five-year trend give a direction; the rules in `docs/method.md` 3.5, each as one
   sentence; the checks of 3.6 as "warnings that do not change the phase"; the Dickinson stage
   (cash-flow signs) shown beside the phase; when a company stays unclassified. One worked
   example: the classifier's evidence for the Mature Growth example company (7.5), as the drawer
   shows it, read aloud.
4. **What a value means here** (`value`). The hurdle rate r and the terminal growth g_T, live;
   the reinvestment charge explained with a four-line numeric example at the live r (earnings
   100, growth 6%, return on new capital 15%: reinvest 40, keep 60); the moat and the runway,
   live by moat class; the margin of safety, the buy level, the fair band and the trim level,
   live; the five designation words and their edges, live, with the sentence that the word is
   about the price, never an action; the validity window (the next earnings date, else the
   fallback days, live) and the three states current, aging, expired; what a refusal is and the
   reasons a row can carry, in words.
5. **Mature Growth** (`mature-growth`). What matters (earnings growth); the steps in plain
   words: the next-twelve-months anchor, the two consensus years, the belief for the years after
   (the base-rate median for the company's sales class plus the inflation addition, live), the
   fade to the terminal growth, the charge at the runway return, the terminal at the terminal
   return, the sum discounted at r, divided by the shares. The implied growth the price needs,
   and what a reader does with it. The flags special to the route. The worked example.
6. **Mature Stable** (`mature-stable`). What matters (earnings stability); normalized earnings;
   the stable-growth value with the charge; the growth-route cross-check. The worked example.
7. **High Growth and Young Growth** (`growth`). What matters (revenue growth and margins); the
   revenue path (the consensus, then the held rate capped at the sales class's 90th percentile,
   live, then the fade), the margin moving to the mature peers' median (the peers, the
   industry fallback), sales-to-capital and reinvestment, tax, the free cash flow and the
   terminal; the margin the price needs. Young Growth's difference: the failure probability,
   unavailable today, with the reason. The worked example (High Growth).
8. **Decline** (`decline`). What matters (book value); the run-off: revenue shrinking, the
   capital released and recovered in part (live fraction), the going-concern value, the
   liquidation floor at the net current asset value, the distress probability from the
   synthetic rating (the table named, not reproduced) and the distress-sale value; the implied
   decline rate; the three distress signals in words. The worked example.
9. **Start-up** (`start-up`). Why there is no value (the inputs that would make one are
   judgments, and the engine holds none); the price-implied requirement: the revenue in year
   ten the price needs at the mature peers' margin, in words; the cash floor and the burn cover.
   The worked example.
10. **The flags** (`flags`). Two lists: the eleven quality warnings that count in the
    flag-count column (9.5), and the notes that do not, each with its short word, its code in a
    code chip and one sentence from `docs/method.md` section 8 rewritten for the reader.
11. **Sources** (`sources`). The list of 7.6 with links.
12. **Your settings** (`settings`). One paragraph: the figures above marked as live come from
    the policy defaults or the reader's settings; a link to the Settings view; the policy
    version and, when settings differ from the defaults, the sentence "n settings differ from
    the defaults".

Each phase section fits in about one screen of prose at desktop width plus one example table.
The whole page is a long read by design; the hash and the section headings are the navigation.
A short table of contents sits under the diagram, one link per section.

### 7.3 The diagram

An inline SVG in the page's fragment, drawn by the builder from the tokens. No image, no
external file, no animation.

- **What it shows.** Damodaran's life-cycle curve: time on the horizontal axis, two curves,
  revenue (`--chart-1`) and earnings (`--ink-muted`), the earnings curve below zero in the two
  early phases and crossing above it in High Growth, revenue rising through the growth phases,
  flat through Mature Stable and falling in Decline. Six vertical bands behind the curves,
  one per phase, filled with `--phase-1` to `--phase-6` at low opacity: the phase ramp is the
  system's one ordered ramp and this is its use. Under each band, the phase name in `caption`
  and the live count of companies in it in `figure-sm` mono, filled by the script (7.4).
- **Size.** A `viewBox` of 960 by 320; the SVG scales to its container and fits 320px wide.
  At phone width the six names stay readable because they are set in the SVG's units; the
  counts sit under the names.
- **Theme.** Every colour is a token (`var(--…)`) or `currentColor`, so the diagram follows
  dark and light mode without a second drawing.
- **Access.** A `<title>` and a `<desc>` inside the SVG; under it, a visually plain list of the
  six phases with their counts, which is also the text a screen reader gets. `role="img"` on
  the SVG with `aria-labelledby` pointing at the title.

### 7.4 Live values and the policy API

`GET /api/policy` returns the effective policy's values the page cites: for each, `name`, the
`value` (a number, a pair, or a map by moat class), the `unit` (`fraction`, `years`, `times`,
`days`, `usd`, `count`), the `source` line from the file, `setting` (true when the value is a
setting), and whether the current value differs from the default. The response also carries
`version` (the policy file's), `settingsHash` (8.4) and `changed` (the count of settings that
differ from the defaults). The route never returns the tables (the base rates, the ratings, the
default probabilities, the patterns, the industries); the page names them and links the file's
sources instead. Nothing in the policy is a key.

The page's script fills every `<span data-policy="<name>">` from the response, formatted by
unit: a fraction as a percentage with one decimal, years and days as a count with the word,
times as `1.5×`, dollars as money. A `data-policy` attribute may name a moat class
(`data-policy="runway_years.Wide"`) or an index (`data-policy="fair_band.1"`). A name the
response lacks renders an em dash and fails the content test (11). The live counts fill
`<span data-count="<phase>">` from `/api/groups?by=phase`, and `data-count="universe"` from
the screen's total. The decile edges fill `<span data-decile="<n>">` from `GET /api/deciles`,
a new route returning the latest run's revenue-growth decile edges (nine numbers) and the growth
words' decile ranges.

### 7.5 The examples

One real company per route, chosen from the run of 2026-11-03 by market cap among the
household names. The builder takes the figures from the company's latest snapshot **after the
revalue under method 0.8**, names that refresh's date once at the head of the examples ("Figures
as of the valuation of <date>"), and writes the walkthrough from the drawer's inputs and
intermediates, rounded as the drawer rounds. The page carries a link under each example,
"Open today's row", which opens the Screen view with the FIND query set to the symbol.

| Route | Symbol | If its phase moved by build time |
|---|---|---|
| Mature Growth (also the classifier example) | MSFT | GOOG |
| Mature Stable | KO | PG |
| High Growth | CRWD | DDOG |
| Young Growth | ROKU | RBRK |
| Decline | MMM | EL |
| Start-up | RVMD | MDGL |

Each example is one table and three to six sentences. The table has the route's key inputs with
their tags (DATA or RULE, as the drawer shows them), the three to five intermediates the section
explained, the value a share, the price and the designation word. The sentences read the table:
what the price needs, what the engine believed, where the two meet. Young Growth's example sits
in the growth section after High Growth's, shorter, with its failure-probability sentence.

The page is not regenerated. When the method changes, the builder of that change re-reads the
examples from the new snapshots and updates the figures and the date (7.8).

### 7.6 Sources

Each rule in the page carries a bracketed source that links to this list. The list, with the
links the builder checks at build time (a dead link is replaced by the work's citation without
a link):

- Damodaran, *The Corporate Life Cycle* (2024), and the slide decks at
  `https://pages.stern.nyu.edu/~adamodar/pdfiles/CLC/slides/` (chapters 2, 3 and 9): the six
  phases, the two deciding variables, the pricing table.
- Damodaran, the valuation template and spreadsheets at `https://pages.stern.nyu.edu/~adamodar/`
  (the ten-year template, the fade, sales-to-capital, the margin convergence).
- Damodaran, "Valuing Distressed and Declining Companies" (2009) and "Valuing Young, Start-up and
  Growth Companies" (2009), both at `https://pages.stern.nyu.edu/~adamodar/pdfiles/papers/`.
- Damodaran, the ratings table at `https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ratings.html`.
- Dickinson, "Cash Flow Patterns as a Proxy for Firm Life Cycle", *The Accounting Review* 86(6),
  2011; the SSRN page.
- Altman, "Predicting Financial Distress of Companies: Revisiting the Z-Score and ZETA Models"
  (2000), the NYU Stern page.
- Piotroski, "Value Investing: The Use of Historical Financial Statement Information to Separate
  Winners from Losers", *Journal of Accounting Research* 38, 2000.
- Mauboussin and Callahan, "Measuring the Moat" (Credit Suisse, 2016): the moat sources.
- Mauboussin, Callahan and Majd, *The Base Rate Book* (Credit Suisse, 2016): the growth belief
  and the held-rate cap. Cited by name, no link: the book is not redistributed (B-46).
- McKinsey, *Valuation* (the value-driver formula behind the reinvestment charge).
- Graham, the net current asset value (*Security Analysis*).
- OECD, Corporate Tax Statistics, the combined statutory rates, at `https://www.oecd.org/`
  (the tax table's source line names the edition).
- Fairband's own method, `docs/method.md`, linked as the full statement.

### 7.7 Where it lives

- `src/fairband/web/static/methodology.html`: the fragment, prose, tables and the SVG, with
  the `data-policy`, `data-count` and `data-decile` spans. The page fetches it into the
  Methodology panel on the view's first open and inserts it as HTML (it is the app's own static
  file; nothing in it comes from a vendor or a user).
- `src/fairband/web/static/methodology.js`: fills the spans from the three routes, wires the
  table of contents and the section hash, and the "Open today's row" links. It draws nothing.
- The CSS for prose in `index.html`'s stylesheet, from the type styles the tokens define
  (`display`, `title`, `body`, `caption`, `figure`), with a measure of about 70 characters.
- The drawer's phase-evidence section gains one link, "How Fairband values a <phase> company",
  to `#methodology/<section-id>` of the row's route.
- `GET /api/policy` and `GET /api/deciles` in `web/app.py`, with their row builders in
  `web/rows.py` or a new `web/policy_rows.py` (the builder's choice).

### 7.8 The same-commit rule

CLAUDE.md's "Read first" entry for `docs/method.md` gains a sentence: the Methodology page
(`web/static/methodology.html`) changes in the same commit as the method, the classifier, the
universe rule or a policy value, and a change of method version re-reads the examples' figures.
`docs/method.md` section 0 says the same in one line.

## 8. Settings (B-2, B-24)

### 8.1 What a setting is

A policy value the user may change on the Settings view. The policy file keeps every value
with its source line and stays the default. The user's values are an **overlay**: a row per
changed setting in the database. The **effective policy** is the file's values with the overlay
applied, built once per run and once per request. `Policy.version` stays the file's version;
the overlay is not a policy version and is never written to `policy_versions`.

A value that is not a setting (3) is read from the file only.

### 8.2 The settings

Thirty-eight settings (forty policy names) in five groups; the inventory of 2026-11-04 held
them in fewer rows. "Effect" is when a change is read: **revalue** (the next
revalue or full refresh; no vendor call needed), **full** (the next full refresh), **run** (the
next refresh of any kind), **at once** (the next request). Ranges are inclusive. A fraction is
entered and shown as a percentage.

**A. Valuation**

| Setting | Policy name | Default | Range | Effect |
|---|---|---|---|---|
| Hurdle rate r | `required_return` | 9% | 4% to 20%, above g_T | revalue |
| Terminal growth g_T | `terminal_growth` | 3% | 0% to 5%, below r | revalue |
| Runway, by moat (None, Narrow, Wide) | `runway_years` | 5, 10, 20 | 4 to 30 years each, non-decreasing None ≤ Narrow ≤ Wide | revalue |
| Margin of safety, by moat | `margin_of_safety` | 45%, 35%, 25% | 5% to 70% each, non-increasing None ≥ Narrow ≥ Wide | revalue |
| Fair band (low, high) | `fair_band` | 0.85, 1.15 | low 0.50 to 0.99, high 1.01 to 1.50 | revalue |
| Trim multiple | `trim_multiple` | 1.5 | above the band's high, up to 3.0 | revalue |
| Wide-moat terminal spread above r | `wide_terminal_roic_spread` (new, 8.3) | 4 points | 0 to 10 points | revalue |
| Inflation addition to the belief | `inflation_addition` | 2 points | 0 to 5 points | revalue |
| Repricing horizon | `repricing_horizon_years` (new, 8.3) | 3 years | 1 to 10 years | revalue |
| Return sensitivities (high, low) | `roic_sensitivity` | 15%, 9% | 1% to 50% each, high above low | revalue |
| Fade years | `fade_years` | 5 | 1 to 9 | revalue |
| High-growth years | `high_growth_years` | 5 | 3 to 9; with the fade years, at most 10 | revalue |
| Margin convergence year | `margin_convergence_year` | 10 | 1 to 10 | revalue |
| Fewest peers for a target margin | `peer_min` | 3 | 1 to 10 | revalue |
| Industry peers on the fallback | `industry_peer_max` | 10 | the fewest peers to 50 | revalue |
| Run-off years | `runoff_years` | 10 | 5 to 20 | revalue |
| Run-off recovery | `runoff_recovery` | 60% | 0% to 100% | revalue |
| Distress-sale fraction | `distress_sale_fraction` | 60% | 0% to 100% | revalue |
| Burn-cover flag years | `burn_cover_flag_years` | 2 | 0.5 to 5 | revalue |

**B. Flags** (none changes a value)

| Setting | Policy name | Default | Range | Effect |
|---|---|---|---|---|
| Fewest analysts behind a path year | `analyst_min` | 5 | 1 to 20 | revalue |
| Non-recurring gap, share of EPS | `nri_flag_share` | 5% | 1% to 50% | revalue |
| Value spread | `value_spread_flag` | 30% | 5% to 100% | revalue |
| Long-runway growth | `long_runway_growth_flag` | 10% | 1% to 30% | revalue |
| Margin flag: ratio to the median, above the high, fewest years | `margin_flag_ratio`, `margin_flag_above_high`, `margin_flag_min_years` | 1.5, 10%, 6 | 1.1 to 3.0; 1% to 50%; 3 to 10 | revalue |
| Heavy capex, share of operating cash flow | `capex_ocf_flag` | 50% | 10% to 100% | revalue |
| Equity raise, share of market cap | `equity_raise_share` | 1% | 0.1% to 10% | revalue |

**C. Validity**

| Setting | Policy name | Default | Range | Effect |
|---|---|---|---|---|
| Validity fallback | `validity_fallback_days` | 91 days | 30 to 365 | revalue |
| Aging after | `aging_fraction` | 2/3 of the window | 10% to 95% | at once |

**D. Universe**

| Setting | Policy name | Default | Range | Effect |
|---|---|---|---|---|
| Exchanges | `universe.exchanges` | NYSE, NASDAQ, AMEX | a non-empty subset of the three | full |
| Size floor | `universe.cap_floor_usd` | $2 bn | $100 m to $50 bn | full |
| Cap bands (Mega, Large, Mid floors) | `universe.cap_bands` | $200 bn, $10 bn, $2 bn | descending; the lowest equals the size floor | full |
| Admitted symbols | `universe.manual_admissions` | V, MA, GPN | a list of symbols | full |
| Excluded symbols | `universe.manual_exclusions` | none | a list of symbols | full |

**E. Refresh**

| Setting | Policy name | Default | Range | Effect |
|---|---|---|---|---|
| FMP workers | `refresh.workers` | 16 | 1 to 64 | run |
| FMP calls a minute | `refresh.fmp_calls_per_minute` | 2,850 | 10 to 10,000 | run |
| Hold after a 429 | `refresh.rate_limit_hold_s` | 60 s | 1 to 3,600, finite | run |
| Reuse window, FMP | `refresh.reuse_hours` | 24 h | 0 to 720 | run |
| Reuse window, GuruFocus | `refresh.gf_reuse_days` | 7 days | 0 to 90 | run |

The server port stays in the environment and the keys file's folder, not on the page (the
page cannot change the port it is served on). Everything else in the inventory of 2026-11-04 is
fixed, by the founder's agreement of that day.

### 8.3 Derived values and policy v6

Two values of policy v5 are derived in v6, so that a changed setting carries them along, and
two new values name what was a constant in code:

- `designation_edges` leaves the file. The edges are derived: e1 = 1 − the Narrow margin of
  safety, e2 = the fair band's low, e3 = the fair band's high, e4 = the trim multiple. At the
  defaults that is 0.65, 0.85, 1.15, 1.50, the v5 edges. `docs/method.md` 4.10 says so, and
  the source stays method v1.7 Step 10, which is where v5's edges came from.
- `wide_terminal_roic_cap` leaves the file; `wide_terminal_roic_spread` = 0.04 enters. The cap
  is r + the spread: 13% at the defaults. `docs/method.md` 4.7 says so.
- `repricing_horizon_years` = 3 enters, with the source "stocks method v1.7 Step 9; design.md 1
  (the 3-year repricing horizon)". It replaces the `horizon` default of `engine/returns.py` and
  every other three-year read of the expected return (`docs/method.md` 5.10, 6.5 and the
  Mature Stable route's `stable_at_price`). The path gives one growth rate a year up to the
  runway, and `engine/returns.py` raises today when the horizon outruns them (a None-moat
  Mature Growth row has four). Past the runway the path grows at g_T, the terminal's own rate,
  so a horizon longer than the path never raises; `docs/method.md` 5.10 states the rule.
  *My call*, from the builder check.
- The load-time checks of B-2 enter `load_policy`: the same ranges as 8.2, so a policy file or
  an overlay outside them fails at load with the setting's name, never inside a run.

The policy file is `fairband-policy-v6.toml`; v5 stays in the package for the snapshots that
name it. The method is 0.8. `docs/method.md` sections 4.1, 4.7, 4.10, 5.10, 8, 10 and 11 change
(10).

### 8.4 The settings hash, the snapshot and the reprice rule

The **settings hash** is the sha256 of the JSON, with sorted keys, of the overlay's entries in
groups A and B and `validity_fallback_days`, as stored (name to value). An empty overlay hashes
`{}`. Groups D and E do not enter it: they change which companies are valued and how they are
fetched, not a snapshot's figures. `aging_fraction` does not enter it either: the code reads it
when a row is rendered (`web/rows.py`), never at valuation, so a change needs no revalue and
must not make the price refresh refuse. *My call*, from the builder check.

`refreshes` and `snapshots` gain `settings_hash TEXT NOT NULL`, the migration filling the
existing rows with the empty overlay's hash. A run records the hash it ran under; a snapshot
carries its run's.

The price refresh reprices a snapshot only when its `policy_version` and its `settings_hash`
both equal the current ones. Otherwise the snapshot keeps its figures and the row's reason
reads "settings changed: run a revalue" or "policy changed: run a revalue". That closes B-24:
the message asked for a full refresh where a revalue does. A revalue runs under the current
file and overlay and writes the current versions and hash. The method's section 10 says so.

### 8.5 The Settings page

One form, five sections in the order of 8.2, each setting one row:

- the label, in `body`; one plain sentence under it in `caption` saying what the value does;
- the field, right-aligned, mono, in the control style, with the unit beside it (%, years,
  ×, days, $), on `surface-sunken`; the two-value settings (the band, the sensitivities) and
  the by-moat settings are two or three fields on the row; the symbol lists are one text field
  of comma-separated symbols; the exchanges are three checkboxes;
- the default in `caption`: "default 9%, from stocks method v1.7", the source line's first
  clause; a changed field shows the word `changed` in `accent` beside it;
- the effect word in `caption`: "takes effect at the next revalue";
- `Reset` (secondary, sm) beside a field that differs from its default.

At the top of the form, one of three notices in `caption`, from the API's `valuedUnder` and
`current`: nothing, when the latest snapshots were valued under the current hash and version;
"Your settings changed since the last valuation." with a **Revalue now** button (primary) that
starts a revalue through `POST /api/refresh`, when the hashes differ; "A universe setting
changed since the last full refresh: run Refresh all." when a group D setting changed after the
latest full refresh (the API compares the overlay's D entries' `changed_at` with the latest full
refresh's start).

At the bottom: one optional `Reason` text field for the save, and **Save** (primary). Save
opens the design system's `ConfirmDialog` with the payload: each changed setting, old to new,
exactly as the server will apply it. Confirm sends `PUT /api/settings`. The server checks every
range (8.2) and the cross-field rules; a 400 names the setting and the rule, and the page shows
the sentence beside that field. On success the form reloads from the API and the notice line
updates.

While Revalue now is in flight, the header shows the run as it does for any refresh; the
Settings page's button is disabled and the form stays readable.

The form uses plain fields in the control style, not `TaggedInput`: that component is for a
company's valuation inputs and requires a reason per field, which is ceremony here. *My call.*

### 8.6 Storage

Migration `004_settings_and_watchlists.sql`:

```sql
CREATE TABLE settings (
    name TEXT PRIMARY KEY,
    value TEXT NOT NULL,          -- JSON
    changed_at TEXT NOT NULL
);
CREATE TABLE settings_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    changed_at TEXT NOT NULL,
    reason TEXT,
    changes TEXT NOT NULL         -- JSON: [{"name", "old", "new"}]
);
ALTER TABLE refreshes ADD COLUMN settings_hash TEXT NOT NULL DEFAULT '<empty hash>';
ALTER TABLE snapshots ADD COLUMN settings_hash TEXT NOT NULL DEFAULT '<empty hash>';
```

`<empty hash>` is the literal sha256 of `{}`. A reset deletes the setting's row and records the
change. A name must be one of the forty policy names; a value must parse as the setting's type and pass its
range; both are checked in `store/settings.py` and again in `load_policy`.

### 8.7 The API

- `GET /api/settings`: `groups` in the order of 8.2, each with its `settings`: `name`,
  `label`, `description`, `unit`, `default`, `value`, `range` (as the page shows it), `effect`,
  `source`, `changed` (differs from the default), `changedAt`; plus `current: {policyVersion,
  settingsHash}` and `valuedUnder: {policyVersion, settingsHash, fullRefreshAt, universeChanged}`
  from the latest snapshots and refreshes.
- `PUT /api/settings` with `{"changes": {"<name>": <value>, …}, "reason": "…"}`: applies all
  or none; 200 with the `GET` body; 400 with `detail` "<name>: <rule>" on the first failing
  setting. The request-header rule of the web API applies, as to every write.
- `POST /api/settings/reset` with `{"names": [...]}` or no names for all: the same body.
- `GET /api/policy` (7.4).

### 8.8 Who reads the overlay

`load_policy` keeps reading the file. A new `effective_policy(conn)` in `fairband.policy`
reads the file, applies the overlay from `settings`, checks the ranges and returns a `Policy`
with `settings_hash` set. The server builds the effective policy per request where it reads
policy values (`rows.py` reads `aging_fraction` and the edges) and per run in the worker; the
CLI `refresh` builds it at the start of the run. So a CLI run sees the page's settings, and a
run in flight keeps the policy it started with.

Two consequences the builder check found. The FMP client and the limiter are built once at
server start today (`refresh/clients.py`); group E's values are read per run, so the worker
builds the clients per run from the effective policy. And the server builds its worker only
with an FMP key today, while a revalue needs none: the worker is built in every case and a
revalue runs keyless, which closes B-45.

### 8.9 Cross-field rules

Checked at the write and at the load: r above g_T; the runways non-decreasing by moat; the
margins of safety non-increasing by moat; the band's low below 1 below the band's high below
the trim multiple; the sensitivities' high above the low; high-growth years plus fade years at
most 10; the industry peer maximum at least the fewest peers; the cap bands descending with
the lowest equal to the size floor; a symbol list of valid exchange-form symbols
(`[A-Z0-9.-]{1,10}`), upper-cased on the write.

## 9. Watchlists (B-67) and the flag count (B-69)

### 9.1 What a watchlist is

A named list of companies the user keeps. A company can be on several. Each entry carries the
date it was added. The lists are the user's, not the engine's: nothing in a valuation reads
them. The work inbox will read them for its expiry rule (B-58), and the MCP server will expose
them (B-48).

### 9.2 Storage

In the same migration (8.6):

```sql
CREATE TABLE watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL
);
CREATE TABLE watchlist_entries (
    watchlist_id INTEGER NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    added_at TEXT NOT NULL,
    PRIMARY KEY (watchlist_id, symbol)
);
```

A name is 1 to 60 characters after trimming. A symbol is kept in the exchange form the store
uses (`BRK.B`); it need not be in the current universe (a company may leave the universe and
stay on a list; its row then shows no snapshot figures).

### 9.3 The API

- `GET /api/watchlists`: `[{id, name, createdAt, count, symbols: [{symbol, addedAt}]}]`, by
  name.
- `POST /api/watchlists` `{name}` → the new list; 409 on a name in use.
- `PATCH /api/watchlists/{id}` `{name}`; `DELETE /api/watchlists/{id}`.
- `PUT /api/watchlists/{id}/symbols/{symbol}` adds (idempotent); `DELETE …/{symbol}` removes.
- `PUT /api/watchlists/memberships/{symbol}` `{ids: [...]}` sets the company's lists in one
  write, for the popup.
- The screen rows (`GET /api/screen`) gain `watchlists: [id, …]` per row.

### 9.4 On the screen

- **The mark.** A bookmark mark at the left edge of the Ticker cell: the glyph `▸` hollow when
  the company is on no list, filled (`▶`) when on one or more, in `ink-faint` and `accent`
  respectively. It is a button (`aria-pressed`, labelled "Watchlists for <ticker>"), 24px
  square, and clicking it does not open the row. The brand book says nothing in a row is a
  control; the founder makes this one exception on 2026-11-04. The mark is a `// fairband:`
  patch to `ScreenTable`: a new prop `onWatch(row)` and a row field `watched: boolean`; without
  `onWatch` the component renders no mark. Fairband has no icon set; the two triangles are
  glyphs the system already draws (the sort indicator).
- **The popup.** Clicking the mark opens a small menu under it, in the bundle's menu style
  (the one the Details ▾ uses): one checkbox row per watchlist, checked where the company is
  on it; a last row with a text field "New watchlist" and an `Add` button (secondary, sm) that
  creates the list and puts the company on it in one step (`POST` then `PUT`). A change writes
  at once (`PUT …/memberships/<symbol>`); the mark fills or empties when the write returns.
  Escape or a click outside closes it. The popup is in `app.js`, not the bundle.
- **The filter.** `ScreenFilters` gains `watchlist: number[]` (list ids, a whitelist like the
  other groups: a row matches when it is on any chosen list) and `cleanOnly: boolean` (9.5).
  The Filters ▾ menu gains a `WATCHLISTS` group listing the lists by name, and a `CLEAN` row
  with one checkbox, "No warning flag". A chosen list shows as a chip with its name; more than
  two become `3 watchlists`; the clean row's chip reads `Clean`. Both are patches to the
  bundle's menu and chip code.
- **The columns.** The chooser gains two columns: `Watchlists` (the names joined by ` · `, em
  dash for none) and `Flags` (the count, right-aligned mono; the existing `flags` column keeps
  the words). The brand book's rule that a filter is also a column holds.

### 9.5 The flag count and the clean filter

Every screen row carries `flagCount`: the number of its **quality warnings**, the eleven flags
that say the value may be wrong because the business or its figures are unusual:

`large-nri`, `value-spread`, `margin-flag`, `z-distress`, `f-score-low`,
`reinvesting-in-decline`, `equity-raise`, `negative-fcf`, `heavy-capex`, `burn-cover-short`,
`consensus-recovery`.

Every other flag is a **note**: the classifier checks, the thin-consensus flags, the unknown
inputs, the engine's mechanics (a floored return, a zeroed charge) and the bookkeeping flags
(the lease and line flags, the carried tax rate). Notes stay in the Flags words column and the
drawer and do not count. The founder chose this on 2026-11-04 from the figures of the
2026-11-03 run: counting every warning left 32 clean rows of 1,305, all Mature Stable, because
`margin-direction-disagrees` sits on 701 valued rows, `few-analysts` on 637, `large-nri` on
630 and `value-spread` on 456; counting the eleven leaves 187 clean rows across the phases.
The list is a constant in `engine/flags.py` (structure, 4.1a), and section 8 of the method
gains a column "Counts" saying which flags do. A refusal row has a count too (its flags are
kept).

`Flags` sorts as a number. `cleanOnly` keeps the rows whose count is zero. "Cheap and clean" is
then the screen sorted by price ÷ value with `Clean` on, and nothing composite is scored.

### 9.6 The Watchlists view

The view lists the watchlists, each as a card-like section: the name in `title`, the count and
the created date in `caption`, `Rename` and `Delete` (danger, sm) beside it; under it the
list's companies as a `ScreenTable` with the screen's current columns (`chooser: false`,
`dense`), the rows from the screen's loaded rows joined by symbol, a symbol with no row shown
as ticker alone with an em dash in every other cell; each row's mark opens the same popup as
on the screen, so removing a company from this list is unchecking it. Opening a row opens the
drawer as on the screen.

Above the lists: a text field "New watchlist" with `Create` (secondary). Within each list: a
text field "Add a company" that matches the screen's rows as FIND does (ticker prefix, name
substring), lists up to eight matches under it, and adds the chosen one; a symbol that matches
no row can be added as typed (upper-cased) when it passes the symbol pattern.

`Delete` opens `ConfirmDialog` with the payload (the list's name and its count) and deletes on
confirm. `Rename` turns the name into a field; Enter saves, Escape cancels.

An empty state: "No watchlists yet. Create one here, or press the mark beside a ticker on the
screen." The view's panel scrolls on its own, like Groups.

## 10. Policy v6 and method 0.8: the document changes

`docs/method.md` in the same commit as the engine change:

- **0.** One line: the Methodology page is written from this document and changes with it.
- **4.1.** The table loses `designation_edges` and `wide_terminal_roic_cap`, gains
  `wide_terminal_roic_spread` and `repricing_horizon_years`, and marks each value that is a
  setting with the word "setting" in a new column; a sentence says what the overlay is and that
  the effective policy is the file plus the overlay.
- **4.7.** The Wide cap is r plus the spread.
- **4.10.** The edges are derived, as 8.3 says.
- **5.10, 6.5.** "Three years" becomes the repricing horizon, named as a policy value.
- **8.** A column "Counts" (yes or no): the eleven quality warnings of 9.5 count, every other
  flag is a note.
- **10.** The reprice rule reads "settings changed: run a revalue" and "policy changed: run a
  revalue"; the settings hash is named; the revalue writes the current versions and hash.
- **11.** The row for 0.8 and policy v6.

`docs/backlog.md`: B-73, B-2, B-67, B-69, B-24 and B-45 move to Done with the commit.

## 11. Tests the builder must write

Python, in the folders that mirror the package:

- `tests/policy/`: v6 loads; the derived edges at the defaults equal v5's `0.65, 0.85, 1.15,
  1.5`; the Wide cap at the defaults is 0.13; every range of 8.2 and every rule of 8.9 raises
  at load with the setting's name; an overlay applies and sets the hash; the empty overlay's
  hash is the literal in the migration.
- `tests/engine/`: a fixture valued under v5 and under v6 at the defaults gives the same
  result dict, bit for bit, for one row per route (the fixtures of the existing route tests).
  Nothing loads a v5 file through the v6 loader, so the plan's first task captures the 0.7
  engine's result dicts for those fixtures as golden files, and the test compares them with the
  version fields masked;
  the repricing horizon read from the policy changes the expected return; `flag_count`
  excludes the bookkeeping flags and counts the rest.
- `tests/store/`: the migration applies to a v3 database and fills the hash; settings write,
  read, reset and the change log; watchlists create, rename (case-insensitive uniqueness),
  delete cascades, add and remove entries, memberships set.
- `tests/web/`: `GET /api/settings` shape and the three notices; `PUT` all-or-none, a 400
  naming the setting; `GET /api/policy` carries every name the fragment's `data-policy` spans
  cite and no table and no key; `GET /api/deciles`; the watchlist routes; the screen rows carry
  `watchlists` and `flagCount`; the price refresh refuses a snapshot with another hash with the
  new message and reprices one with the current hash; the Settings `valuedUnder` after a
  revalue.
- `tests/web/test_app.py` (file-content pins, as the repository does): the five views; the
  hash routing words; the fragment has the twelve section ids, the SVG with a `<title>`,
  the six example symbols and the "Figures as of" line; every `data-policy` name in the
  fragment is a key `GET /api/policy` returns (a Python test reads the fragment and the route);
  the bundle patches are present and named in the patch list.
- `tests/refresh/`: the CLI refresh and the worker build the effective policy from the
  database; a run records the hash; a revalue after a settings change writes snapshots with
  the new hash.

## 12. Left to the builder

- The exact prose of the Methodology page, within 7.1 and 7.2, and the examples' sentences.
- The SVG's drawing: the curves' shapes, the band widths, the label positions.
- The CSS of the prose, the form rows, the popup and the mark, from the tokens.
- The split of `app.js` (1,071 lines today, B-33) into the view scripts; the builder may move
  the drawer and the screen into their own files while adding `watchlists.js`, `settings.js`
  and `methodology.js`.
- The order of the plan's tasks, except that policy v6 and method 0.8 come first, so the
  examples are read from snapshots under 0.8. The revalue that produces them runs on the live
  database after the engine tasks are green, with the database copied first to
  `fairband-before-v6-<date>.db` beside it, as every version before.
- The patch names for the bundle and their entries in the patch list.

## 13. Acceptance

- The header shows Screen, Groups, Watchlists, Methodology and Settings; `#methodology/decline`
  opens the Decline section; the drawer's phase section links to the route's section.
- The Methodology page shows the diagram with six bands and the live counts, the twelve
  sections, one worked example per route with "Figures as of <date>", and a sources list whose
  links resolve. Changing r on the Settings page and reloading changes every r on the page.
- On the Settings page, setting r to 10% and saving opens the confirm with `required_return
  9% → 10%`; after confirm the notice offers Revalue now; the revalue completes; the notice
  clears; every valued row's value differs from before; a price refresh then reprices every row.
  Setting r to 2% is refused with the sentence beside the field. Reset returns 9%.
- At the defaults, after the v6 revalue, the values, levels, designations and flags of the
  2026-11-03 run are unchanged (checked on ten rows across the routes by the builder, and by the
  engine tests bit for bit).
- The CLI `refresh --kind revalue` after a page-side settings change writes snapshots under the
  new hash.
- On the screen, pressing the mark beside MSFT opens the popup; creating "Quality" there puts
  MSFT on it and fills the mark; Filters ▾ → Quality narrows the screen to MSFT; the Watchlists
  view shows Quality with MSFT's row; unchecking there empties the mark on the screen.
- `Flags` sorts by count; `Clean` leaves only rows with a zero count; a row with only
  `leases-not-on-balance-sheet`, `few-analysts` and `margin-direction-disagrees` counts zero,
  and one with `large-nri` counts one.
- The checks command passes; the method and the backlog are updated in the same commits.

## 14. Decision log

| Date | Decision |
|---|---|
| 2026-11-04 | The next plan is the Methodology page, settings and watchlists with the flag count; foreign filers (B-28) is the plan after. Founder. |
| 2026-11-04 | The methodology examples are real companies with figures as of a named refresh date, hand-written; not templated live sentences. Founder agreed the real company; the fixed-date form is Claude's call. |
| 2026-11-04 | The diagram is inline SVG from the tokens, not an image. Claude's advice, founder agreed. |
| 2026-11-04 | Settings live on a page in the app, stored in the database as an overlay over the policy file; the file keeps the defaults and sources. Claude's call, founder agreed. |
| 2026-11-04 | The 38 settings of 8.2 and the fixed set are as the inventory of 2026-11-04 proposed, split where one of its rows held two settings. Founder agreed. |
| 2026-11-04 | The designation edges and the Wide cap are derived from the settings they came from. Claude's call in the inventory, founder agreed. |
| 2026-11-04 | B-2's 429 mode and plan-limit probe are dropped: the run already holds, retries, stops and reports; FMP offers no probe. Claude. |
| 2026-11-04 | A settings change needs no reason; one optional reason per save. Claude, for low ceremony. |
| 2026-11-04 | The watchlist mark is the one control in a row, overriding the brand book's rule; the AppHeader's "no settings gear" rule is overridden by a Settings view. Founder. |
| 2026-11-04 | Both ways into the work inbox exist later: the button and the expiry rule for watchlist companies. Founder. Not built here. |
| 2026-11-04 | The flag count counts the eleven quality warnings of 9.5 and Clean is a zero count; every other flag is a note. Claude's recommendation from the run's figures, founder chose it over a count of every warning with an "at most N" filter. |
| 2026-11-04 | The reviewer's three other questions settled by Claude: `aging_fraction` out of the settings hash; the expected return's path grows at g_T past the runway; 38 settings over 40 names. |
