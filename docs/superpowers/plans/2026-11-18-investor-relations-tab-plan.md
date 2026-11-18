# The Investor Relations Tab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An Investor relations tab on the company page at `#company/<symbol>/investor-relations`: a company's earnings calls, each read in the page beside the quarter's reported figures and their estimates, and its filings as links to the SEC's site, opened from the store with no vendor call.

**Architecture:** The refresh's per-company fetch gains two optional page calls (the list of calls, the filings of the last 365 days) and, where the store has none with words, the newest call's transcript, each stored under its pass-through's key so the agents' tools share the copy. Pure readers shape the stored answers. One read answers the tab from the store alone; two more reads fetch an older call's transcript or an older year of filings on a reader's press, through the pass-throughs. One page script draws the tab.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLite, httpx; plain JavaScript with React from the design-system bundle, no build step; pytest, with node for the page's own scripts (`tests/web/page.mjs`, `tests/support/page.py`).

**Spec:** `docs/superpowers/specs/2026-11-18-investor-relations-tab-design.md` ("the spec"). Read it with your task: this plan argues from it, and where the two differ the spec wins. It stands on `docs/superpowers/specs/2026-11-16-company-page-design.md` ("the page's design"), which is built. The look is the mockup's: `docs/superpowers/specs/2026-11-18-investor-relations-tab-mockup/template.html`, with the differences of the spec's section 13.

**A map of the code as it stands:**

- `src/fairband/vendors/fmp.py`: `Fmp.transcript(symbol, year, quarter)`, `Fmp.transcript_dates(symbol)`, `Fmp.filings(symbol, start, end)`, `Fmp.earnings(symbol, limit)`.
- `src/fairband/refresh/fetch.py`: `PAGE_ENDPOINTS` (the page's fourteen, fetched last), `page_params(endpoint, symbol)`, `_calls(fmp, gf, symbol, today)` with its `page_sends` map, `_Call(provider, endpoint, params, send)`, `_rows` (a page endpoint's payload is usable when it is a list), `_store`, `fetch_company(conn, fmp, gf, symbol, policy, now, secrets, force=False) -> FetchOutcome`.
- `src/fairband/refresh/passthrough.py`: `Passthrough.fetch(kind, symbol, params) -> dict[str, Fetched]` (`Fetched.row`, `.payload`, `.reused`); the kinds `transcript` (logical params `{"symbol", "year", "quarter"}`, no usability test), `transcript-dates` (`{"symbol"}`, no usability test) and `filings` (endpoint `sec-filings`, `{"symbol", "from", "to", "limit": str(FILINGS_LIMIT)}`, `usable=_is_list`); `PassthroughBusy`, `PassthroughNoKey`.
- `src/fairband/store/vendor.py`: `latest_response(conn, provider, endpoint, symbol, params)` (the newest HTTP 200 answer stored with no error under exactly those params), `response_payload(conn, id)`, `ResponseRow` (`id`, `params`, `observed_at`, ...).
- `src/fairband/vendors/page_fmp.py`: the page's pure readers; `next_earnings(payload, today) -> {"day", "time", "confirmed"} | None`, `money(value, currency) -> Money | None`. `src/fairband/vendors/_fmp_parse.py`: `objects`, `dated`, `whole`, `text`, `parse_date`.
- `src/fairband/web/company_api.py`: `add_company_page_routes(app, conn_factory, policy, tax, clock)`, the four reads; `_profile` (a 404 without one), `_stored`, `_quote`, `_payload`, `_parsed`, `_data_date`, `_Answer(payload, observed_at)`.
- `src/fairband/web/vendor_api.py` and `filings_api.py`: how a route maps the pass-through's failures (a `ValueError` 400; no pass-through 503 `NO_FMP_KEY`; `PassthroughBusy` and `PassthroughNoKey` 503; `VendorError` 502); `filings_api.WINDOW_DAYS = 365`, `OWNERSHIP_FORMS`.
- `src/fairband/web/app.py`: `_VENDOR_READS`, the paths that need `X-Fairband-Request: 1`; `add_company_page_routes(app, conn_factory, policy, taxed, clock)` beside `add_vendor_routes(app, passthrough)`.
- `src/fairband/web/static/controls.js`: `COMPANY_TABS`, `keepCompany(symbol, tab, id)` (keeps an `id` on the Research tab only, a whole number), `companyPath()`, `fromHash()`.
- `src/fairband/web/static/company.js`: `TABS`, `keyOf`, `load()` (reads `/page/<tab>`, with `?report=<id>` where an id is kept), `read(url)` (a plain GET, no header), and `P.companyPage`: `panel`, `table`, `day`, `money`, `big` and `draw`, on which a tab's script hangs `draw.<tab>(answer, detail)`.
- `src/fairband/web/static/company_estimates.js`: the Earnings table, the model for the figures' words (`C.money`, `C.big`). `company_financials.js`: the switch of statements (`app-fin__seg`).
- `src/fairband/web/static/index.html`: the page's CSS (classes `app-…`) and the scripts in load order.
- Tests: `tests/vendors/test_page_fmp.py` (readers), `tests/refresh/test_fetch.py`, `test_passthrough.py` and `vendor_double.py` (`Router`, fixtures under `tests/fixtures/fmp/`, which hold `earning-call-transcript-dates.ACME.json`, `earning-call-transcript.ACME.json` and `sec-filings-search-symbol.ACME.json`), `tests/web/test_company_page_api.py` (reads), `tests/web/test_company_load.py` with `company_load.mjs` (addresses and loading), `tests/web/test_company_estimates.py` (a tab drawn in node), `tests/support/page.py` (`node(helper, args, *scripts)`, `classed`, `elements`, `text`), `tests/support/page_payloads.py` and `page_answers.py`.

## Global Constraints

- No file under `src/fairband/engine/` or `src/fairband/policy/` changes. The method stays `fairband-mechanical/1.5` and the policy v16. No migration: the schema stays at 009. No value, level, flag or settings hash moves, and a failure of a new call costs no valuation.
- The tab's first read calls no vendor. Only the two later reads may, and each needs the header `X-Fairband-Request: 1`.
- No figure Fairband computes: no gap to an estimate, no percent, no sum. No red and green: a figure wears the text's own colour.
- No figure and no block names a vendor, carries a chip, a cite or a ref.
- A vendor's words are drawn as text, never as markup. A link is drawn only where it starts `https://`.
- Every word a person reads is copied from this plan's Words table, which copies the spec's 7.7. A changed word is a spec change.
- No test uses the network. Fixtures and payloads are synthetic, an invented company's invented call among them: never commit vendor data, and a real transcript is vendor data. Never print, log, store or commit a key.
- The repository is public. Commit on the branch only; nothing is pushed or merged without the founder's word.
- Work in a worktree, not in the main checkout: the live server on port 8470 serves the page files of the main checkout as they are on disk.
- Run before every commit: `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
- A commit message is one plain sentence in the imperative, then a blank line, then `Co-Authored-By: Claude <model> <noreply@anthropic.com>` naming the model that wrote the change.
- Every dispatched subagent, reviewers included, runs on Opus 5.5 at xhigh (the founder's standing rule).

## Words

| Where | Words |
|---|---|
| Tabs | `Overview`, `Financials`, `Estimates`, `Investor relations`, `Research` |
| The switch | `Earnings calls`, `Filings` |
| The line | `Next earnings report <date>` |
| The list | `Fiscal <year>`; a row `Q<n>` and the date; `Show all <n> calls`; `No earnings call on file.` |
| The reader | `Q<n> fiscal <year> earnings call`; `EPS reported`, `EPS estimate`, `Revenue reported`, `Revenue estimate`; `Find in this call`; `<n> matches`, `1 match`; `Go to the questions`; `Questions and answers`; `No transcript on file for this call.`; `The transcript could not be read: <reason>.` |
| The filters | `Without insider forms`, `10-K and 10-Q`, `8-K`, `Insider forms`, `All`, each with its count |
| The table | `Filed`, `Form`, `What it is`, `On the SEC's site`; `Document`, `All files`; `Amendment: <the form's words>` |
| The forms' words | the mockup's `FORMS` table, as written there |
| Under the table | `Filed from <date> to <date>.`; `The vendor's list is cut at 1,000 filings a window.`; `Show older filings`; `No filing on file.`; `The older filings could not be read: <reason>.` |
| Failures | 404 `no page data for <symbol>`; a tab whose read fails, as the other tabs |

Dates read as the page's (`2 Nov 2026`, `C.day`). A missing figure is the dash, `—`.

## Review Focus

Five conditions the spec implies and a hurried build would miss. Each has its test in the task that owns the code.

1. **A vendor answer of the wrong shape.** FMP answers HTTP 200 with `{"Error Message": ...}` for a list or a transcript; a call's row with no date, a quarter of 5 or a fiscal year as text; a transcript row with no `content` or a blank one; a filing row with no link, a link that is not `https://`, or no form. The fetch stores an object as unusable; a reader drops the row or gives null; nothing throws (Tasks 1, 2, 3).
2. **A company with a profile and nothing else.** The read answers 200 with `calls` empty and `filings` null; the tab draws its two sentences, no reader and no button, and does not throw (Tasks 3, 4, 5, 6).
3. **A transcript that is not a tidy script.** No speaker's line at all; one turn of 60,000 characters; a sentence longer than 520 characters; a line such as `Note: see the slides` that reads as a speaker's; text before the first speaker's line; `OPERATOR` in capitals. Every word of the content is in the turns, in order (Task 1).
4. **A late answer.** A reader selects a second call, or another company, while a transcript's read is out: the answer that lands late draws nothing, and the list stays. A change of call or of view never reads the tab's first read again (Tasks 4, 5).
5. **What a reader types in the find box.** `$1.5`, `(`, `?`, `a.b` and a lone backslash are plain words, never a pattern; one character marks nothing; the marks are text nodes inside `mark` elements, never markup built from the words (Task 5).

---

### Task 1: The readers (spec 5, 7.4, 7.5, 8.2; Review Focus 1, 3)

**Files:**
- Create: `src/fairband/vendors/page_investor.py`
- Test: `tests/vendors/test_page_investor.py`

**Interfaces:**
- Consumes: `page_fmp.money`, `_fmp_parse.parse_date`, `whole`, `text`.
- Produces, all pure, payload in and fields out:
  - `PARAGRAPH_CHARS = 520`, `JOIN_DAYS = 45`, `SPEAKER_WORDS = 6`
  - `speaker_turns(content: str) -> list[tuple[str | None, str]]`: the turns by the spec's speaker's line (a name of 2 to 60 characters with no colon and at most six words, then `: `); another non-blank line joins the turn before it after one space, or starts a turn with no name.
  - `paragraphs(words: str) -> list[str]`: broken after a `.`, `!` or `?` and its space; no paragraph over `PARAGRAPH_CHARS` but a single longer sentence.
  - `questions_at(turns: Sequence[tuple[str | None, str]]) -> int | None`: the spec's 7.4 rule.
  - `has_words(payload: Any) -> bool`: a list whose first row is an object with a non-blank text `content`.
  - `transcript(payload: Any) -> dict[str, Any]`: `{"date": <ISO or None>, "turns": [{"speaker", "paragraphs"}], "questionsAt": int | None}`; `turns` empty without words.
  - `newest_call(dates: Any) -> tuple[int, int] | None`: the fiscal year and quarter of the usable row with the latest date.
  - `calls(dates: Any, earnings: Any) -> list[dict[str, Any]]`: every usable row (a whole `fiscalYear`, a `quarter` of 1 to 4, an ISO `date`), newest first, each `{"fiscalYear", "quarter", "date", "epsReported", "epsEstimate", "revenueReported", "revenueEstimate"}`; the four from the earnings row whose `fiscalYear` and `fiscalPeriod` (`Q<n>`) are the call's and whose `date` is within `JOIN_DAYS` of the call's, each `page_fmp.money(<field>, "USD")`; null without such a row.
  - `filing_rows(payload: Any) -> list[dict[str, Any]]`: each object row with a text `formType` as `{"form", "filed", "document", "files"}`: `filed` the date part of `filingDate`, `document` its `finalLink` and `files` its `link`, each null unless a text that starts `https://`; in the payload's order.

- [ ] **Step 1: Write the failing tests** in `tests/vendors/test_page_investor.py`, among them:

```python
def test_a_speaker_s_line_starts_a_turn_and_another_line_joins_it() -> None:
    content = "Opening music\nAda Park: Good day.\nMore words.\nOperator: First question.\n"
    assert speaker_turns(content) == [
        (None, "Opening music"),
        ("Ada Park", "Good day. More words."),
        ("Operator", "First question."),
    ]


def test_seven_words_or_a_colon_in_the_name_is_no_speaker_s_line() -> None:
    assert speaker_turns("one two three four five six seven: words") == [
        (None, "one two three four five six seven: words")
    ]
    assert speaker_turns("https://example.com/a: b") == [(None, "https://example.com/a: b")]


def test_paragraphs_end_at_sentences_and_stay_under_the_limit() -> None:
    sentence = "Word " * 59 + "end. "  # 300 characters
    parts = paragraphs((sentence * 4).strip())
    assert [len(p) <= PARAGRAPH_CHARS for p in parts] == [True] * 4
    assert " ".join(parts) == (sentence * 4).strip()
    long = "x" * 600 + "."
    assert paragraphs(long + " Short one.") == [long, "Short one."]


def test_the_questions_start_at_the_operator_s_turn_that_says_question() -> None:
    opened = [("Operator", "Welcome."), ("Ada Park", "Thanks."), ("OPERATOR", "Our first Question.")]
    assert questions_at(opened) == 2
    assert questions_at([("Operator", "Welcome to the question session."), ("Ada", "Hi.")]) is None
    assert questions_at([("Ada", "Hi."), ("Operator", "Please go ahead.")]) is None
    assert questions_at([("Ada", "Any question?"), ("Bo", "No.")]) is None


def test_a_call_takes_the_earnings_row_of_its_label_within_45_days() -> None:
    dates = [{"quarter": 1, "fiscalYear": 2025, "date": "2025-04-17"}]
    row = {"fiscalYear": 2025, "fiscalPeriod": "Q1", "epsActual": 2.0, "epsEstimated": 1.9,
           "revenueActual": 5e9, "revenueEstimated": 4.9e9}
    near = calls(dates, [{**row, "date": "2025-05-15"}])[0]
    assert near["epsReported"] == money(2.0, "USD") and near["revenueEstimate"] == money(4.9e9, "USD")
    far = calls(dates, [{**row, "date": "2026-04-17"}])[0]
    assert far["epsReported"] is None and far["date"] == "2025-04-17"
```

Also: `has_words` and `transcript` on `[]`, on `{"Error Message": "x"}`, on a row with `content` `"  "`; every word of a content with no speaker's line in one turn with a null speaker; `newest_call` and `calls` dropping a row with quarter 5, a fiscal year `"2025"` as text, or no date; `calls` newest first; `filing_rows` with a link missing, a link `javascript:alert(1)` (null), a row that is no object, and a payload that is no list (`[]`).

- [ ] **Step 2: Run them**: `uv run pytest tests/vendors/test_page_investor.py -q`. Expected: FAIL, no module `page_investor`.
- [ ] **Step 3: Write `page_investor.py`** with the functions above. `paragraphs` splits with one regular expression over sentence ends and packs sentences greedily.
- [ ] **Step 4: Run the tests again.** Expected: PASS.
- [ ] **Step 5: Commit**: `git add src/fairband/vendors/page_investor.py tests/vendors/test_page_investor.py`, message "Add the Investor relations tab's readers, ...".

### Task 2: The refresh's calls (spec 8.1, 8.3, 10; Review Focus 1)

**Files:**
- Modify: `src/fairband/refresh/fetch.py`, `src/fairband/refresh/passthrough.py`, `docs/method.md` (section 10's sentence), the docstrings that count the fetch's calls (`fetch.py`, `run.py`, `passthrough.py`)
- Test: `tests/refresh/test_fetch.py`, `tests/refresh/test_passthrough.py`, `tests/refresh/vendor_double.py`, `tests/test_method_doc.py` where it pins that sentence

**Interfaces:**
- Consumes: `page_investor.newest_call`, `page_investor.has_words`; `Fmp.transcript_dates`, `Fmp.filings`, `Fmp.transcript`.
- Produces:
  - `PAGE_ENDPOINTS` ends `..., "segments-geographic", "transcript-dates", "sec-filings")`.
  - `FILINGS_WINDOW_DAYS = 365` and `filings_window(today: date) -> tuple[date, date]`, `(today - 365 days, today)`, in `fetch.py`.
  - `page_params(endpoint: str, symbol: str, today: date | None = None) -> dict[str, str]`: for `transcript-dates` the symbol alone; for `sec-filings` `{"symbol", "from", "to", "limit": str(FILINGS_LIMIT)}` of `filings_window(today)`, a `ValueError` without `today`. `FILINGS_LIMIT` moves to where both modules import it without a cycle.
  - In `fetch_company`, after the listed calls: where the `transcript-dates` answer in the store is usable and `newest_call` names a call, and no usable stored `transcript` answer of that company, year and quarter `has_words`, one more call, endpoint `transcript`, params `{"symbol", "year": str(y), "quarter": str(q)}`, stored and judged as a page call is (usable when a list; not required; a 429 stopping the fetch).
  - `passthrough.py`: the `transcript-dates` call gains `usable=_is_list`.

- [ ] **Step 1: Write the failing tests**, among them:

```python
def test_the_fetch_asks_the_page_s_sixteen_with_the_filings_of_the_last_year(env) -> None:
    outcome = fetch(env, "ACME", today=date(2026, 11, 18))
    asked = env.router.asked("ACME")
    assert asked["sec-filings"] == {"symbol": "ACME", "from": "2025-11-18", "to": "2026-11-18", "limit": "1000"}
    assert asked["transcript-dates"] == {"symbol": "ACME"}
    assert outcome.error is None


def test_the_newest_call_s_transcript_is_fetched_once(env) -> None:
    fetch(env, "ACME", today=date(2026, 11, 18))
    first = env.router.count("transcript")
    fetch(env, "ACME", today=date(2026, 11, 19), force=True)
    assert (first, env.router.count("transcript")) == (1, 1)
```

Write them in the file's own style and helpers (`vendor_double.Router`, the conftest's fixtures); the names above stand for what the file has. Also: no transcript call where the dates answer is an error object, an empty list, or holds no usable row; a second call where the stored transcript has no words; the pass-through's `transcript-dates`, `filings` (a year to the same day) and `transcript` reusing the refresh's copies, and the refresh reusing the pass-through's; `transcript-dates`' error object stored with `unusable payload: ...` by both and reused by neither; a failed or unusable new call leaving `FetchOutcome.error` as it was without it; a 429 on a new call stopping the fetch as on any page call; `page_params("sec-filings", "ACME")` raising.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Write the code**, then `docs/method.md` section 10: the sentence that counts the FMP answers only the company page shows counts sixteen and names the two, and says the newest call's transcript is fetched where the store has none with words. Bring `tests/test_method_doc.py` and the docstrings up to it.
- [ ] **Step 4: Run the task's tests, then the whole suite.** Expected: PASS.
- [ ] **Step 5: Commit**, message "Fetch each company's list of earnings calls and its filings of the last 365 days at a refresh, ...".

### Task 3: The three reads (spec 7.5, 8.2; Review Focus 1, 2)

**Files:**
- Modify: `src/fairband/store/vendor.py`, `src/fairband/web/company_api.py`, `src/fairband/web/app.py`
- Test: `tests/store/test_vendor.py` (or the file that tests `latest_response`), `tests/web/test_investor_page_api.py` (new), `tests/support/page_payloads.py`

**Interfaces:**
- Consumes: Task 1's readers; `Passthrough.fetch`; `page_fmp.next_earnings`, `head_quote`; `fetch.FILINGS_WINDOW_DAYS`.
- Produces:
  - `store.vendor.usable_responses(conn, provider: str, endpoint: str, symbol: str) -> list[ResponseRow]`: every HTTP 200 answer stored with no error, newest first.
  - `add_company_page_routes(app, conn_factory, policy, tax, clock, passthrough: Passthrough | None)`; `app.py` passes its `passthrough`; `_VENDOR_READS` gains `/api/companies/[^/]+/page/investor-relations/call` and `/api/companies/[^/]+/page/investor-relations/filings`.
  - `GET /api/companies/{symbol}/page/investor-relations` -> `{"symbol", "dataDate", "quote", "nextEarnings", "calls", "filings"}`: `nextEarnings` the `day` of `next_earnings` or null; `calls` of the newest usable `transcript-dates` answer and the stored `earnings`; `filings` null or `{"from", "to", "rows", "truncated"}` of the usable `sec-filings` answer whose `to` param is the latest, the newest id among equals; `truncated` true where the payload holds `FILINGS_LIMIT` rows; `dataDate` over the answers drawn.
  - `GET .../page/investor-relations/call?year=&quarter=` -> `{"symbol", "fiscalYear", "quarter", "date", "turns", "questionsAt", "observedDay"}`: the newest usable stored `transcript` answer of those params that `has_words`, whatever its age; else `passthrough.fetch("transcript", symbol, {"year", "quarter"})["transcript"]`.
  - `GET .../page/investor-relations/filings?to=<ISO date>` -> `{"from", "to", "rows", "truncated", "observedDay"}` for `(to - 365 days, to)`: the stored usable answer of exactly that window where `to` is before the clock's day, whatever its age; else `passthrough.fetch("filings", symbol, {"from", "to"})["filings"]`.
  - Failures of the last two, in this order: 403 without the header (the app's own); 400 for a bad symbol, a `year` or `quarter` that is no whole number, a quarter outside 1 to 4, a `to` that is no ISO date, each with its sentence; 404 `no page data for <symbol>`; then, only where the vendor must be asked, 503 `no FMP key` without a pass-through, 503 for `PassthroughBusy`, 502 for `VendorError`.

- [ ] **Step 1: Write the failing tests** on a store seeded with synthetic answers, among them:

```python
def test_the_tab_s_read_calls_no_vendor_and_needs_no_header(client, seeded) -> None:
    answer = client.get("/api/companies/ACME/page/investor-relations")
    assert answer.status_code == 200
    body = answer.json()
    assert body["calls"][0] == {
        "fiscalYear": 2026, "quarter": 4, "date": "2026-11-02",
        "epsReported": {"amount": 2.05, "currency": "USD"}, "epsEstimate": {"amount": 1.99, "currency": "USD"},
        "revenueReported": {"amount": 114.0e9, "currency": "USD"}, "revenueEstimate": {"amount": 113.0e9, "currency": "USD"},
    }
    assert body["filings"]["to"] == "2026-11-17" and body["nextEarnings"] == "2027-02-04"
    assert seeded.vendor_calls == 0


def test_the_latest_window_wins_over_a_newer_copy_of_an_older_one(client, seeded) -> None:
    seeded.filings("ACME", to="2024-12-31", observed="2026-11-18")   # an agent's, fetched later
    assert client.get("/api/companies/ACME/page/investor-relations").json()["filings"]["to"] == "2026-11-17"


def test_a_transcript_with_words_is_never_fetched_again(client, seeded) -> None:
    get = lambda: client.get("/api/companies/ACME/page/investor-relations/call?year=2026&quarter=3",
                             headers={"X-Fairband-Request": "1"})
    first, second = get(), get()
    assert first.json()["turns"][0]["speaker"] == "Operator" and second.json() == first.json()
    assert seeded.vendor_calls == 1
```

Shape the money fields as `page_fmp.money` gives them; the fixture names stand for the file's own. Also: a company with a profile only (`calls` `[]`, `filings` null, `nextEarnings` null, 200); `truncated`; `dataDate` as the oldest day; the two reads' 403; each 400 and the 404; a stored transcript without words asked again past the window and answered `turns` `[]` inside it; a past window used from the store whatever its age and a window that ends today going through the pass-through; `no FMP key` 503 only where the store cannot answer; the busy 503 and the vendor's 502.

- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Write `usable_responses`, the three routes and the app's two lines.** The page reads take the symbol as the other page reads do and hand the pass-through the store's form, as `filings_api` does.
- [ ] **Step 4: Run the task's tests, then the whole suite.** Expected: PASS.
- [ ] **Step 5: Commit**, message "Add the Investor relations tab's three reads, ...".

### Task 4: The tab's frame (spec 7.1, 7.2, 7.6, 9; Review Focus 2, 4)

**Files:**
- Modify: `src/fairband/web/static/controls.js`, `company.js`, `index.html`
- Create: `src/fairband/web/static/company_investor.js`
- Test: `tests/web/test_company_load.py` with `company_load.mjs`, `tests/web/test_company_investor.py` (new), `tests/support/page_answers.py`

**Interfaces:**
- Consumes: Task 3's first read's answer.
- Produces:
  - `COMPANY_TABS` and `TABS` hold `investor-relations` between `estimates` and `research`, named `Investor relations`.
  - `keepCompany` keeps this tab's `id` where it is `filings` or matches `/^\d{4}Q[1-4]$/`, else null; `companyPath` writes it as it does the Research tab's.
  - `load()` reads `/page/investor-relations` with no query, and a change of this tab's `id` alone reads nothing: the answer held for the company's tab is drawn again.
  - `C.readVendor(url)`: `read` with the header `X-Fairband-Request: 1`.
  - `C.draw['investor-relations'](answer, detail)`: the panel, the switch (`app-fin__seg`'s look) and the line; the view by `P.company.id` (`filings`, else the calls); a press of the switch sets the hash by `companyPath`. This task draws the two views' empty sentences only; Tasks 5 and 6 fill them.
  - `P.investor` for the tests: the pure functions the later tasks add.

- [ ] **Step 1: Write the failing tests**: the row's five tabs in order; `#company/ACME/investor-relations`, `/2026Q4` and `/filings` kept and written back; `/2026Q5`, `/nonsense` and `/12` put right to the tab alone; a change from `/2026Q4` to `/2026Q3` and to `/filings` making no read (count the reads in `company_load.mjs`); the line `Next earnings report 4 Feb 2027` and no line without a day; a company with `calls` `[]` and `filings` null drawing `No earnings call on file.` under Earnings calls and `No filing on file.` under Filings, with no throw; the data date in the row.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Write the code and the stylesheet's rules** (tokens only, no colour of their own; the script after `company_estimates.js`).
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**, message "Make Investor relations the company page's fourth tab, ...".

### Task 5: The Earnings calls view (spec 7.3, 7.4, 7.6, 7.8; Review Focus 3, 4, 5)

**Files:**
- Modify: `src/fairband/web/static/company_investor.js`, `index.html`
- Test: `tests/web/test_company_investor.py`, `tests/web/investor.mjs` (new, if the tab's state needs a driver as `research.mjs` is one)

**Interfaces:**
- Consumes: the first read's `calls`; Task 3's call read through `C.readVendor`.
- Produces on `P.investor`: `years(calls, shown) -> [{year, calls}]` (five fiscal years unless all are asked for); `marked(paragraph, words) -> {parts: [{text, hit}], hits}` (plain, case-blind, from two characters); `title(call)`.

- [ ] **Step 1: Write the failing tests**, among them `marked("Up $1.5 billion (net).", "$1.5")` giving one hit and the parts `["Up ", "$1.5", " billion (net)."]`; `marked(p, "a")` giving no hit; `marked("a.b axb", "a.b")` one hit. Also: the list under `Fiscal <year>` heads, newest first, five years and `Show all 85 calls`, no button at five years or fewer; the selected row marked; the title and date; the figures row with four figures, with a dash for a null one, and no row where all four are null; no element that holds a percent or the words `against the estimate`; the find box's count `1 match` and `3 matches` and none when empty; the button and the label only where `questionsAt` is a number; a turn with a null speaker drawn with no name; `No transcript on file for this call.` for `turns` `[]`; `The transcript could not be read: no FMP key.` for a 503 with that sentence, the list still drawn; a late answer of another call, and of another company, drawing nothing; the newest call read on the tab's opening and a selected call once.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Write the view**: the list, the reader, its tools; the call's read keyed by company, year and quarter and kept for the page's life; the address set by `companyPath` on a selection; the rules below 860px and for print (spec 7.8).
- [ ] **Step 4: Run the tests.** Expected: PASS.
- [ ] **Step 5: Commit**, message "Draw the Investor relations tab's earnings calls, ...".

### Task 6: The Filings view (spec 7.5, 7.6, 7.8; Review Focus 1, 2)

**Files:**
- Modify: `src/fairband/web/static/company_investor.js`, `index.html`
- Test: `tests/web/test_company_investor.py`

**Interfaces:**
- Consumes: the first read's `filings`; Task 3's filings read through `C.readVendor`.
- Produces on `P.investor`: `FILTERS` (the five, each a name and a test of a form); `words(form) -> string` (the mockup's table; `Amendment: ` and the words for `<form>/A`; `''` for a form it lacks); `olderTo(windows, rows) -> ISO date` (the day before the oldest window's `from`, or, where that window is truncated, the filing day of the oldest row shown); `merged(rows, more)` (a row with the same `files`, `form` and `filed` not added twice).

- [ ] **Step 1: Write the failing tests**, among them:

```javascript
// investor filters and windows, run through tests/support/page.py's node()
assert.deepEqual(I.FILTERS.map((f) => f.name), ['Without insider forms', '10-K and 10-Q', '8-K', 'Insider forms', 'All']);
assert.equal(I.words('8-K/A'), 'Amendment: ' + I.words('8-K'));
assert.equal(I.words('NO-SUCH'), '');
assert.equal(I.olderTo([{ from: '2025-11-18', to: '2026-11-18', truncated: false }], rows), '2025-11-17');
assert.equal(I.olderTo([{ from: '2025-11-18', to: '2026-11-18', truncated: true }], [{ filed: '2026-09-30' }, { filed: '2026-08-04' }]), '2026-08-04');
```

Also: each filter's rows and its count (`4/A` under Insider forms, `10-K/A` under 10-K and 10-Q, `20-F` under the first and All only); the first filter pressed on opening; a row's two links, one link, and none; the line `Filed from 18 Nov 2025 to 18 Nov 2026.`; the cut line only where a window is truncated; a press of **Show older filings** reading `?to=` by `olderTo`, adding rows, moving the line's first date, dropping a row drawn already; an empty window taking the button away; a failed read keeping the table and drawing `The older filings could not be read: <reason>.`; `No filing on file.` with no button for `filings` null, and the sentence with the button for an empty first window; the table inside its own scrolling box.
- [ ] **Step 2: Run them.** Expected: FAIL.
- [ ] **Step 3: Write the view** and its narrow and print rules.
- [ ] **Step 4: Run the tests, then the whole suite.** Expected: PASS.
- [ ] **Step 5: Commit**, message "Draw the Investor relations tab's filings, ...".

### Task 7: The documents, the look, the whole-branch review and the live steps (spec 10, 12)

Not an implementer task for its last two parts: the controller runs the look, the review and the live steps, and every live step waits for the founder's word.

- [ ] **Step 1: The documents**, in one commit: `docs/backlog.md` (B-217 to Done with the build's commits; a row for what the tasks' reviews deferred); the page's design (a line in its decision log, 7.3's row); `README.md` (the Pages line names the tab; the tools' line says `transcript_dates` and `filings` may answer from a refresh's copy), `docs/agents.md` and `playbook/fairband-research/reference/tools.md` where they describe those two tools' reuse; the module docstrings that list the page's reads and tabs (`company_api.py`, `company.js`, `controls.js`); the spec's status line and its decision log (what the build overturned).
- [ ] **Step 2: The look in a browser**, before the review of the whole branch: a scratch database with AAPL, ASML, NVS, TSM, FRVO and one company with no call, the branch's server on a spare port, headless Chromium at 400, 1,000, 1,200, 1,440 and 2,000px in both themes. Nothing wider than the window, no error in the console, no first-draw vendor call. Faults go to one fixer before the review.
- [ ] **Step 3: The whole-branch review**, its one fix wave and its scoped check (superpowers:subagent-driven-development, references/final-review.md).
- [ ] **Step 4: On the founder's word, the live steps**, in order: back the database up; merge; start the server from main (by its process ids, no refresh running); one full refresh; the acceptance of the spec's section 12, its readout written in the spec's decision log; delete this plan's workspace.
