# The Owner's Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Inbox view has a Messages tab for the owner beside the work queue, the header counts
the unread messages, the browser's system notification tells of a new one also while the tab is
hidden, and Fairband posts no work item by itself.

**Architecture:** The server stores nothing new. `GET /api/inbox` loses the expiry rule, so it
writes nothing, and each item gains `declinedBy`; a new owner's read, `GET /api/inbox/messages`,
builds each message from the work item, its report and `report_call`. On the page a new script,
`messages.js`, keeps two lists of item ids in `localStorage` (seen, notified), counts the unread
and makes the notifications from every 30-second read; `controls.js` hands it each read and draws
its count; `inbox.js` gets two tabs and `inbox_messages.js` draws the Messages tab.

**Tech Stack:** Python 3.13, FastAPI, SQLite; plain ES5 scripts with the vendored React
(`h = React.createElement`), no build step; pytest tests that read the scripts as text, run
their helpers in node through `tests/web/page.mjs`, and drive the header through
`tests/web/header.mjs`.

**Spec:** `docs/superpowers/specs/2026-11-25-owner-inbox-design.md`. Read it first; section
numbers below are its.

## Global Constraints

- Work only in the worktree `.claude/worktrees/owner-inbox`, on the branch
  `worktree-owner-inbox`. Never edit the main checkout: the live server serves its page files.
- Never start a server on the live data folder (`~/.local/share/fairband`) and never send a
  write to the live server. A scratch server takes a scratch data folder and a spare port.
- No schema change (it stays at 012), no MCP tool added, removed or changed, no change to an
  agent's write, no change to `fairband.engine.METHOD_VERSION` or to the policy.
- No motion: no `transition` and no `animation` in any rule this plan adds (`CLAUDE.md`).
- The unread mark is a small square (`border-radius: var(--radius-sm)`), never a round dot: the
  brand book keeps the pill for a point on a scale.
- Scripts stay in the files' own manner: `var`, `function`, no arrow functions, a block comment
  on each function that says what it does and why. Storage and `Notification` are touched inside
  a `try`, never as a script loads.
- Every test is written first and seen to fail. Test fixtures are synthetic.
- Exact words and values, copied from the spec:
  - the addresses `#inbox` (Messages) and `#inbox/queue` (Work queue);
  - the storage keys `fairband.inbox.seen` and `fairband.inbox.notified`, each a JSON list of
    work item ids;
  - the tab labels `Messages` and `Work queue`;
  - "No messages. One arrives when an agent finishes a report or declines a request.";
  - "This browser cannot show notifications at this address."; "Notifications are off." with the
    button `Turn on notifications`; "The browser blocks notifications for this address. Allow
    them in the browser's site settings.";
  - the test notification: title `Fairband`, body `Notifications are on.`;
  - a notification's tag `fairband-message-<itemId>`; more than three at once give one, title
    `Fairband`, body `<n> new messages`, tag `fairband-messages`;
  - the refusal `the messages are the owner's` (403).
- Every dispatched subagent, reviewers included, runs on Opus 5.5 at xhigh (the founder,
  2026-11-10).
- Before every commit, from the worktree, with no pipe after a step:
  `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`.
  A commit of documents alone runs the short check of `CLAUDE.md`.
- A commit message is one plain sentence in the imperative and ends with
  `Co-Authored-By: Claude <model> <noreply@anthropic.com>`, naming the model that wrote the
  change. A test that is removed or rewritten is named in the message of the commit that does it.

## Review Focus

1. **Two messages saved in the other order than their times.** Item 7 ends at 10:00:01 and is
   saved after item 8, which ends at 10:00:02; a read lands between the two saves. Both are
   marked unread and both are notified (Task 3, `test_a_message_saved_late_is_still_new`).
2. **A stored list that is not a list**: `null`, `"3"`, `{}`, text that is not JSON, an older
   build's value. It reads as missing, is written again from the read, and nothing throws
   (Task 3, `test_a_stored_value_that_is_no_list_reads_as_missing`).
3. **The full read fails when a notification is due**, as while the server restarts. The ids are
   already in `notified`, so no later read would try again. The page still shows the
   notification, with its title from the cheap read's item and no body (Task 3,
   `test_a_failed_full_read_still_notifies_by_the_title`).
4. **A message with no figure**: a report whose call has no value, and a done item whose report
   row is gone. The row and the notification draw with no figure, and the text holds no
   `undefined`, `null`, `NaN` or `$—` (Task 2, `test_a_done_item_without_its_report_still_reads`;
   Task 4, `test_a_row_without_a_value`).
5. **A browser whose `Notification` throws or changes its mind**: the constructor throws, as on
   Chrome for Android, or the permission is taken back after the grant. The count, the 30-second
   read and the Messages tab go on, and the line follows the permission at the next draw
   (Task 3, `test_a_notification_that_throws_stops_nothing`).

---

### Task 1: The expiry rule leaves

**Files:**
- Modify: `src/fairband/store/inbox.py` (the module docstring; remove `post_expiry_items`,
  `_due`, `_note`, `_posted_for`, `_record_expiry`, `drop_item`; `post_item` loses
  `expiry_valid_until`, `expiry_review_id` and `expiry_secondary_id`)
- Modify: `src/fairband/web/agents_api.py` (the docstring's first paragraph; the `inbox` route)
- Modify: `src/fairband/web/app.py:66`, `src/fairband/engine/held.py:45` (the docstrings that
  name the rule; a function there that loses its last caller goes, checked by a search)
- Modify: `src/fairband/reports/render.py:291`, `docs/method.md:1366` and `:1475`,
  `playbook/fairband-research/SKILL.md:82`
- Test: `tests/store/test_inbox.py`, `tests/web/test_agents_api.py`, `tests/test_method_doc.py`,
  `tests/test_playbook.py`, `tests/reports/test_render.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `GET /api/inbox` opens no write transaction. `post_item(conn, symbol, mode, note,
  snapshot_id, origin, writer, at) -> int`. `WorkItem` keeps its three `expiry_*` fields,
  `Origin` keeps `"expiry"` and `State` keeps `"dropped"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_agents_api.py
def test_the_inbox_read_posts_nothing_for_an_expired_watched_company(
    client: TestClient, db_path: Path
) -> None:
    # AAPL on a watchlist, its latest snapshot's valid_until before TODAY (the file's
    # _snapshot_until and the watchlist routes, as the removed tests set it up)
    assert client.get("/api/inbox").json()["items"] == []
    assert [e for e in _ledger(client, "AAPL") if e["principal"] == "system"] == []


def test_the_inbox_read_takes_no_write_lock(client: TestClient, db_path: Path) -> None:
    with closing(connect(db_path)) as other:
        other.execute("BEGIN IMMEDIATE")
        try:
            answer = client.get("/api/inbox")
        finally:
            other.rollback()
    assert answer.status_code == 200


# tests/store/test_inbox.py
def test_fairband_posts_and_drops_no_item_itself() -> None:
    import fairband.store.inbox as inbox

    assert not hasattr(inbox, "post_expiry_items")
    assert not hasattr(inbox, "drop_item")


def test_a_stored_expiry_item_and_a_dropped_one_still_read(conn: sqlite3.Connection) -> None:
    conn.execute(
        "INSERT INTO work_items (symbol, mode, note, origin, posted_by, posted_at, state,"
        " expiry_valid_until) VALUES ('AAPL', 'valuation review', 'expired 2026-11-01',"
        " 'expiry', 'system', '2026-11-02T00:00:00+00:00', 'dropped', '2026-11-01')"
    )
    [item] = work_items(conn)
    assert (item.origin, item.state) == ("expiry", "dropped")
    assert item.expiry_valid_until == date(2026, 11, 1)


# tests/test_method_doc.py, on the file's own read of docs/method.md
def test_the_method_states_no_expiry_rule() -> None:
    assert "expiry rule" not in METHOD_TEXT
    assert "Fairband posts no work item for an expired value" in METHOD_TEXT
    assert "posted by the owner or an agent; pending, claimed, done, declined or dropped" in METHOD_TEXT
```

- [ ] **Step 2: Run them and see each fail**

Run: `uv run pytest -q tests/web/test_agents_api.py tests/store/test_inbox.py tests/test_method_doc.py -k "posts_nothing or no_write_lock or no_item_itself or still_read or no_expiry_rule"`
Expected: FAIL. The lock test waits for SQLite's busy timeout and then fails.

- [ ] **Step 3: Remove the rule from the code**

Remove the functions named under Files, their imports and the rule's call in the `inbox` route.
Keep the `expiry_*` columns in `post_item`'s `INSERT` out (they default to NULL) and in `_item`
in. Search `src/` for each helper of `fairband.engine.held` and of `fairband.store` that the
rule imported; one with no caller left goes with its tests, one that `web/rows.py` or another
module still calls stays.

- [ ] **Step 4: Remove the rule's tests**

From `tests/store/test_inbox.py`, the eleven tests from
`test_an_expired_watchlist_company_posts_one_valuation_review` to
`test_the_expiry_rule_writes_its_own_ledger_rows` and their helpers that nothing else uses;
`test_a_missing_item_a_bad_mode_and_a_drop_of_an_open_claim` loses its drop and becomes
`test_a_missing_item_and_a_bad_mode`. From `tests/web/test_agents_api.py`,
`test_the_inbox_read_runs_the_expiry_rule`, `test_the_expiry_rule_s_ledger_rows_on_an_inbox_read`
and `test_a_declined_expiry_item_holds_for_its_window`; a test of the owner's decline keeps what
is about the decline. Any other test that calls a removed function is rewritten or removed the
same way.

- [ ] **Step 5: Change the documents' sentences**

- `docs/method.md`, the glossary's row: `| Work item | A request in the inbox for an agent's
  research on one company, a valuation review or a full report, posted by the owner or an
  agent; pending, claimed, done, declined or dropped |`.
- `docs/method.md`, section 14.6: the text from "The inbox's expiry rule, run when the inbox is
  read" to the paragraph's end becomes "Fairband posts no work item for an expired value (spec
  2026-11-25, the owner's inbox, 8): the owner sees the state on the row and asks for the
  research."
- `src/fairband/reports/render.py`: the glossary's Work item sentence, as the method's row.
- `playbook/fairband-research/SKILL.md`: "An item of origin `expiry` is one Fairband posted
  itself under a rule that no longer runs. Work it as a valuation review: step 3's refresh
  renews the company, as it renews every company's."
- The module docstrings named under Files say what runs now.

- [ ] **Step 6: Run the full check** (Global Constraints). Expected: all pass.

- [ ] **Step 7: Commit**

"Remove the watchlist expiry rule, so Fairband posts and drops no work item itself and a read of
the inbox writes nothing, and say so in the method, the report's glossary and the playbook",
with the removed and renamed tests named after it.

---

### Task 2: The server's side of the messages

**Files:**
- Modify: `src/fairband/store/inbox.py` (add `decliners`)
- Modify: `src/fairband/store/reports.py` (add `ReportHead`, `report_heads`)
- Modify: `src/fairband/web/agents_api.py` (add `inbox_items_json`; the route calls it)
- Create: `src/fairband/web/inbox_messages.py`
- Modify: `src/fairband/web/app.py` (register the route after `add_agent_routes`)
- Test: `tests/store/test_inbox.py`, `tests/store/test_reports.py`,
  `tests/web/test_agents_api.py`; create `tests/web/test_inbox_messages.py`

**Interfaces:**
- Consumes: Task 1's `GET /api/inbox`.
- Produces:
  - `decliners(conn: sqlite3.Connection) -> dict[int, Writer]`: the writer of each item's
    decline, by item id, the newest ledger row of kind `decline` that names the item, in one
    query.
  - `ReportHead(id, symbol, revision, mode, stance, snapshot_id, review_id, secondary_id,
    principal, actor)`, frozen, and `report_heads(conn, ids: Iterable[int]) -> dict[int,
    ReportHead]`, one query, which does not read `sections`.
  - `inbox_items_json(conn: sqlite3.Connection, state: State | None, at: datetime) ->
    list[dict[str, Any]]`: the cheap read's items. Each item gains `"declinedBy"`: `"owner"`,
    `"agent"`, or `None` for an item that is not declined or whose decline has no ledger row.
  - `messages(conn: sqlite3.Connection) -> list[dict[str, Any]]` and
    `add_message_routes(app: FastAPI, conn_factory: Callable[[], sqlite3.Connection]) -> None`
    in `web/inbox_messages.py`; the route `GET /api/inbox/messages` answers
    `{"messages": [...]}`, and 403 `the messages are the owner's` to a request whose
    `X-Fairband-Principal` header is `agent`.
  - A message, the keys camelCase. Both kinds: `itemId`, `symbol`, `kind` (`"done"` or
    `"declined"`), `mode`, `at` (the item's `finished_at` as ISO text), `by`
    (`{"principal", "actor"}`). `done` adds `reportId`, `reportRevision`, `stance`, `value`,
    `basis`, `note`, `price`, `priceDate`, `validUntil`, `refusal`, the last seven as
    `report_call` answers them for the report's snapshot, review and secondary valuation
    (`company_api._report_parts` shows how the three are read). `declined` adds `reason`.
  - The rules of 7.1 and 7.2: a `done` item gives a message whatever its origin; a `declined`
    one only where `decliners` names an agent; `mode` and `by` of a `done` message are the
    report's, of a `declined` one the item's mode and the decline's writer; the order is `at`
    descending, then `itemId` descending. A `done` item whose report or snapshot row is missing
    still gives a message: the item's mode, `by` with both parts `None`, and `None` for
    `reportRevision`, `stance` and the seven figures.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_agents_api.py
def test_the_inbox_names_who_declined(client: TestClient, db_path: Path) -> None:
    # three items: one declined by the owner (HEADER), one by an agent (AGENT), one pending;
    # a fourth set to 'declined' by SQL, with no ledger row
    by = {i["symbol"]: i["declinedBy"] for i in client.get("/api/inbox").json()["items"]}
    assert by == {"AAPL": "owner", "AAL": "agent", "HGCO": None, "MSFT": None}


def test_the_inbox_read_s_queries_do_not_grow_with_its_items(db_path: Path) -> None:
    # one done item with its report, counted; then four more, counted again
    def statements(conn: sqlite3.Connection) -> int:
        seen: list[str] = []
        conn.set_trace_callback(seen.append)
        inbox_items_json(conn, None, NOW)
        conn.set_trace_callback(None)
        return len(seen)

    assert after == before


# tests/web/test_inbox_messages.py
CALL = ("value", "basis", "note", "price", "priceDate", "validUntil", "refusal")


@pytest.mark.parametrize("case", ["review", "secondary", "refused"])
def test_a_done_message_holds_the_report_s_call(client, db_path, case) -> None:
    # a report on a snapshot with a review; with a secondary valuation and no review; on a
    # refused snapshot with neither. The item is completed with it.
    [message] = client.get("/api/inbox/messages").json()["messages"]
    expected = report_call(snapshot, review, secondary)  # read from the store in the test
    assert {k: message[k] for k in CALL} == {k: expected[k] for k in CALL}
    assert (message["kind"], message["stance"], message["reportRevision"]) == ("done", "hold", 1)
    assert message["by"] == {"principal": "agent", "actor": "claude-opus-5-5"}


def test_the_report_s_mode_names_a_done_message(client, db_path) -> None:
    # a "full report" item completed with a report whose mode is "valuation review"
    assert client.get("/api/inbox/messages").json()["messages"][0]["mode"] == "valuation review"


def test_an_agent_s_decline_gives_a_message_and_the_owner_s_none(client) -> None:
    [message] = client.get("/api/inbox/messages").json()["messages"]
    assert (message["symbol"], message["kind"], message["reason"]) == ("AAL", "declined", "no filing yet")
    assert message["by"] == {"principal": "agent", "actor": "claude-opus-5-5"}


def test_the_messages_come_newest_first(client, db_path) -> None:
    # three messages whose finished_at, set by SQL, is not in the order of their ids
    assert [m["itemId"] for m in messages] == [2, 3, 1]


def test_the_messages_are_the_owner_s(client) -> None:
    answer = client.get("/api/inbox/messages", headers=AGENT)
    assert (answer.status_code, answer.json()["detail"]) == (403, "the messages are the owner's")


def test_a_done_item_without_its_report_still_reads(client, db_path) -> None:
    # a done item whose report_id, set by SQL, names no report
    [message] = client.get("/api/inbox/messages").json()["messages"]
    assert message["by"] == {"principal": None, "actor": None}
    assert all(message[k] is None for k in (*CALL, "stance", "reportRevision"))
```

Also `test_decliners_reads_the_newest_decline_of_each_item` in `tests/store/test_inbox.py` and
`test_report_heads_reads_no_sections` in `tests/store/test_reports.py` (the heads of two ids and
of an id with no report, which is left out).

- [ ] **Step 2: Run them and see each fail.** Run: `uv run pytest -q tests/web/test_inbox_messages.py tests/web/test_agents_api.py tests/store/test_inbox.py tests/store/test_reports.py`. Expected: FAIL, the new names not defined and the route 404.

- [ ] **Step 3: Write `decliners` and `report_heads`**, each one query.

- [ ] **Step 4: Write `inbox_items_json` and use it in the route.** It runs the items' query,
  `revisions_by_id`, `decliners`, and the one launch query for each open item that runs today.
  Tests that compare a whole item gain `"declinedBy": None`.

- [ ] **Step 5: Write `web/inbox_messages.py` and register it.** The route reads the principal
  header itself (`fairband.web.identity.PRINCIPAL_HEADER`); a request with none is the page's.

- [ ] **Step 6: Run the full check.** Expected: all pass.

- [ ] **Step 7: Commit**

"Name who declined each work item in the inbox read and add the owner's read of the messages, one
for each report an agent finished and each request an agent declined, with the figures the
report's own page shows".

---

### Task 3: The page keeps the messages: the lists, the count, the read while hidden, the notification

**Files:**
- Create: `src/fairband/web/static/messages.js`
- Modify: `src/fairband/web/static/index.html` (the script, after `finder.js` and before
  `controls.js`)
- Modify: `src/fairband/web/static/controls.js` (`countInbox`, `state.open` becomes
  `state.unread`, `pollInbox`, the header's count, the comments on the pause)
- Modify: `tests/web/header.mjs`; `tests/web/page.mjs` (its head comment names the new helpers
  the tests read, here and in Task 4)
- Test: create `tests/web/test_messages.py`; modify `tests/web/test_app.py`
  (`test_the_count_follows_the_poll`) and `tests/web/test_header.py` where they pin the count

**Interfaces:**
- Consumes: Task 2's `declinedBy` and `GET /api/inbox/messages`.
- Produces: `FairbandPage.messages`:
  - `of(items)`: the items that give a message (7.1: `state === 'done'`, or `'declined'` with
    `declinedBy === 'agent'`), the newest `finishedAt` first.
  - `landed(items)`: a cheap read landed; returns the unread count. In this order: (1) `ids` are
    the ids of `of(items)`; (2) a list that is missing, or that is not a JSON list of numbers,
    is written as `ids`; (3) the ids not in `notified` are the new ones: where there is one,
    `notified` is written as `ids` first, then the notifications are made; (4) while watched and
    `document.hidden` is false, the ids not in `seen` join the marks and `seen` is written as
    `ids`; (5) the count is the ids not in `seen`. A write keeps only ids of this read.
  - `unread()`: the count on the last read's items and the stored `seen`.
  - `watch(on)`: the Messages tab shows (`true`) or no longer shows (`false`). `true` over a
    read that landed runs step 4 at once and calls `onChange`; `false` clears the marks.
  - `marked(id)`: whether the row keeps its unread mark in this viewing.
  - `notice(message)`: `{ title, body, tag, href }` of a full message (the texts below).
  - `permission()`: `'none'` (no `Notification`, or `window.isSecureContext` false),
    `'default'`, `'denied'` or `'granted'`.
  - `ask()`: `Notification.requestPermission()`; on `'granted'` the test notification, tag
    `fairband-test`; then `onChange`. Nothing else in the page asks.
  - `onChange`: a function `controls.js` sets; `messages.js` calls it when the count or the
    permission may have moved, a `storage` event on either key among the cases.
- The texts. Title: `<symbol>: <mode> <kind>`, "QCOM: full report done". Body of `done` with a
  value: `<Stance>. Value <money> against a price of <money> on <date>. Valid until <date>.`,
  the money `Fairband.formatMoney`'s, the dates `Fairband.formatDate`'s, the stance with a
  capital; after the value's money, ` (<basis>, <note>)` where the call has a note and
  ` (mechanical)` where the basis is mechanical. With no value and a refusal:
  `<Stance>. No value: <refusal>.`. With neither: no body. Body of `declined`: the reason. The
  link (`href`): `FairbandPage.researchHref(symbol, reportId)` for `done` with a report, else
  `#inbox`.
- The notifications of step 3: with the permission not `'granted'`, none. Else the page reads
  `/api/inbox/messages` and shows `notice(message)` for each new id, or the one of Global
  Constraints for more than three, whose link is `#inbox`. Where that read fails, each new id is shown by its title
  alone, from the cheap read's item, with the link `#inbox`. Every `new Notification` is inside
  a `try`. A click on one calls `window.focus()`, sets `location.hash` to its link and closes
  it.
- `controls.js`: `countInbox(items)` sets `state.unread` to `P.messages.landed(items)`;
  `P.messages.onChange` sets it to `P.messages.unread()`; each draws the header where the count
  moved. The Inbox entry's `count` is `state.unread`. `pollInbox` loses
  `if (document.hidden) return;`; the read at once on becoming visible stays.

- [ ] **Step 1: Give the driver what the tests need** (`tests/web/header.mjs`), and say so in its
  head comment:
  - it loads `messages.js` in the page's order;
  - the input takes `local` (the `localStorage` entries as the scripts load, or `"throws"`) and
    `notification` (`"granted"`, `"default"`, `"denied"`, `"throws"` for a constructor that
    throws under a granted permission, or `null` for a browser with none);
  - new steps: `{"do": "local", "set", "clear"}`; `{"do": "elsewhere", "set"}`, another tab's
    write, which sets the entries and runs the window's `storage` listeners with the key;
    `{"do": "watch", "on"}`, `FairbandPage.messages.watch(on)`; `{"do": "ask", "grant"}`,
    `FairbandPage.messages.ask()` answered with `grant`; `{"do": "click", "index"}`, a click on
    the notification made at `index`;
  - the trace gains `count` (the Inbox entry's count), `notices` (each notification made since
    the step before, `{title, body, tag}`), `local` (`{"seen", "notified"}`, each the parsed
    entry or `null`), `asks` (the permission requests so far) and `focused` (whether a click
    called `window.focus`).

- [ ] **Step 2: Write the failing tests** (`tests/web/test_messages.py`)

```python
INBOX, FULL = "/api/inbox", "/api/inbox/messages"


MESSAGES = STATIC / "messages.js"


def _done(item_id: int, symbol: str, at: str) -> dict[str, Any]: ...      # a done item of the cheap read
def _declined(item_id: int, symbol: str, at: str, by: str) -> dict[str, Any]: ...
def _open(item_id: int, symbol: str) -> dict[str, Any]: ...               # a pending item
def _full(item: dict[str, Any], **figures: Any) -> dict[str, Any]: ...    # its full message
def _read(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"do": "answer", "url": INBOX, "status": 200, "body": {"launchReady": False, "items": items}}
def _answer(url: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {"do": "answer", "url": url, "status": 200, "body": {"messages": messages}}
def _run(steps: list[dict[str, Any]], **given: Any) -> list[dict[str, Any]]: ...  # the trace

QCOM = _done(1, "QCOM", "2026-11-08T17:56:00+00:00")
MSFT = _done(2, "MSFT", "2026-11-11T14:03:00+00:00")
TICK = {"do": "tick"}


def test_which_items_give_a_message() -> None:
    items = [QCOM, _declined(3, "AMD", "2026-11-09T09:12:00+00:00", "agent"),
             _declined(4, "AAL", "2026-11-09T10:00:00+00:00", "owner"), _open(5, "V")]
    assert [i["id"] for i in node("messages.of", [items], MESSAGES)] == [3, 1]


def test_a_first_read_marks_nothing_and_notifies_nothing() -> None:
    last = _run([_read([QCOM, MSFT])], notification="granted")[-1]
    assert (last["count"], last["notices"]) == (0, [])
    assert last["local"] == {"seen": [1, 2], "notified": [1, 2]}


def test_a_store_with_no_message_marks_its_first() -> None:
    trace = _run([_read([]), TICK, _read([QCOM]), _answer(FULL, [_full(QCOM)])], notification="granted")
    assert trace[0]["local"] == {"seen": [], "notified": []}
    assert trace[-1]["count"] == 1
    assert [n["tag"] for n in trace[-1]["notices"]] == ["fairband-message-1"]


def test_a_new_message_counts_and_notifies_once() -> None:
    steps = [_read([QCOM]), TICK, _read([QCOM, MSFT]), _answer(FULL, [_full(MSFT), _full(QCOM)]),
             TICK, _read([QCOM, MSFT])]
    trace = _run(steps, notification="granted")
    assert trace[3]["notices"] == [{"title": "MSFT: full report done", "body": BODY, "tag": "fairband-message-2"}]
    assert trace[-1]["notices"] == [] and trace[-1]["count"] == 1
    assert FULL not in trace[-1]["reads"]


def test_a_message_saved_late_is_still_new() -> None:
    late = _done(7, "V", "2026-11-12T10:00:01+00:00")
    soon = _done(8, "MA", "2026-11-12T10:00:02+00:00")
    trace = _run([_read([QCOM]), TICK, _read([QCOM, soon]), _answer(FULL, ...), TICK,
                  _read([QCOM, soon, late]), _answer(FULL, ...)], notification="granted")
    assert [n["tag"] for n in trace[-1]["notices"]] == ["fairband-message-7"]
    assert trace[-1]["count"] == 2


def test_no_permission_no_notification_and_the_list_still_moves() -> None:
    last = _run([_read([QCOM]), TICK, _read([QCOM, MSFT])], notification="default")[-1]
    assert (last["notices"], last["local"]["notified"], last["count"]) == ([], [1, 2], 1)
    assert FULL not in last["reads"]


def test_more_than_three_give_one() -> None:
    # four new at one read
    assert trace[-1]["notices"] == [{"title": "Fairband", "body": "4 new messages", "tag": "fairband-messages"}]


def test_a_failed_full_read_still_notifies_by_the_title() -> None:
    trace = _run([_read([QCOM]), TICK, _read([QCOM, MSFT]), {"do": "answer", "url": FULL, "status": 503, "body": {}}],
                 notification="granted")
    assert trace[-1]["notices"] == [{"title": "MSFT: full report done", "body": "", "tag": "fairband-message-2"}]


def test_a_notification_that_throws_stops_nothing() -> None:
    trace = _run([_read([QCOM]), TICK, _read([QCOM, MSFT]), _answer(FULL, ...), TICK, _read([QCOM, MSFT])],
                 notification="throws")
    assert trace[-1]["count"] == 1 and INBOX in trace[-2]["reads"]


def test_a_stored_value_that_is_no_list_reads_as_missing() -> None:
    for stored in ("null", '"3"', "{}", "not json"):
        last = _run([_read([QCOM])], local={"fairband.inbox.seen": stored, "fairband.inbox.notified": stored})[-1]
        assert last["local"] == {"seen": [1], "notified": [1]} and last["count"] == 0


def test_storage_that_throws_keeps_the_lists_for_the_page_s_life() -> None:
    trace = _run([_read([QCOM]), TICK, _read([QCOM, MSFT]), _answer(FULL, ...)], local="throws", notification="granted")
    assert trace[-1]["count"] == 1 and len(trace[-1]["notices"]) == 1


def test_the_owner_sees_the_messages_only_while_the_tab_shows() -> None:
    hidden = [_read([QCOM]), {"do": "watch", "on": True}, {"do": "visibility", "hidden": True},
              TICK, _read([QCOM, MSFT])]
    trace = _run(hidden)
    assert trace[-1]["count"] == 1 and trace[-1]["local"]["seen"] == [1]
    back = _run(hidden + [{"do": "visibility", "hidden": False}, _read([QCOM, MSFT])])[-1]
    assert back["count"] == 0 and back["local"]["seen"] == [1, 2]


def test_the_marks_stay_until_the_tab_changes() -> None:
    # read [QCOM], tick, read [QCOM, MSFT], watch(true): marked(2) is true and the count 0;
    # watch(false): marked(2) is false


def test_another_tab_s_write_moves_the_count() -> None:
    trace = _run([_read([QCOM]), TICK, _read([QCOM, MSFT]),
                  {"do": "elsewhere", "set": {"fairband.inbox.seen": "[1, 2]"}}])
    assert (trace[2]["count"], trace[3]["count"]) == (1, 0)


def test_the_read_runs_while_the_page_is_hidden() -> None:
    trace = _run([_read([QCOM]), {"do": "visibility", "hidden": True}, TICK])
    assert INBOX in trace[-1]["reads"]


def test_only_the_press_asks_and_a_grant_shows_the_test_notification() -> None:
    trace = _run([_read([QCOM]), TICK, _read([QCOM]), {"do": "ask", "grant": "granted"}], notification="default")
    assert [t["asks"] for t in trace] == [0, 0, 0, 1]
    assert trace[-1]["notices"] == [{"title": "Fairband", "body": "Notifications are on.", "tag": "fairband-test"}]


def test_a_click_opens_the_report() -> None:
    # after a notification for MSFT's report 9: {"do": "click", "index": 0}
    assert trace[-1]["hash"] == node("researchHref", ["MSFT", 9]) and trace[-1]["focused"] is True


@pytest.mark.parametrize(("message", "body"), [
    (_full(QCOM, stance="hold", value=210.87, basis="reviewed", price=173.19, priceDate="2026-11-07", validUntil="2027-02-03"),
     "Hold. Value $210.87 against a price of $173.19 on 7 Nov 2026. Valid until 3 Feb 2027."),
    (... note="secondary valuation" ..., "Hold. Value $210.87 (reviewed, secondary valuation) against a price of ..."),
    (... basis="mechanical" ..., "Trim. Value $95.10 (mechanical) against a price of ..."),
    (... value=None, refusal="no positive trailing earnings" ..., "Trim. No value: no positive trailing earnings."),
    (... every figure None, stance None ..., ""),
])
def test_a_notice_s_words(message, body) -> None:
    assert node("messages.notice", [message], MESSAGES)["body"] == body
```

`BODY` is the first parametrized body. The date's exact form is `Fairband.formatDate`'s; where
it is not "7 Nov 2026", the expected strings take its form. Rewrite
`test_the_count_follows_the_poll` in `tests/web/test_app.py` without its two pins of the pause.

- [ ] **Step 3: Run them and see each fail.** Run: `uv run pytest -q tests/web/test_messages.py tests/web/test_app.py -k "messages or count_follows"`. Expected: FAIL, `messages.js` missing.

- [ ] **Step 4: Write `messages.js`** to the Interfaces block, and add its script tag.

- [ ] **Step 5: Change `controls.js`** to the Interfaces block. The comment over `pollInbox`
  says that the read writes nothing and so runs while the page is hidden, as slowly as the
  browser lets a hidden tab's timers run.

- [ ] **Step 6: Run the full check.** Expected: all pass, the header's other tests among them.

- [ ] **Step 7: Commit**

"Count the owner's unread messages in the header, keep what he saw and what was notified in the
browser, read the inbox while the page is hidden and show the browser's notification for a new
message", with the rewritten test named after it.

---

### Task 4: The Inbox view's two tabs and the Messages tab

**Files:**
- Create: `src/fairband/web/static/inbox_messages.js`
- Modify: `src/fairband/web/static/inbox.js` (the tabs; the view draws the tab's panel)
- Modify: `src/fairband/web/static/controls.js` (`show` keeps the Inbox's second part)
- Modify: `src/fairband/web/static/index.html` (the script, before `inbox.js`; the rules)
- Modify: `src/fairband/web/static/methodology.html:1260`
- Test: create `tests/web/test_inbox_messages_page.py`; modify `tests/web/test_header.py`,
  `tests/web/test_methodology.py` where it pins the sentence

**Interfaces:**
- Consumes: Task 3's `FairbandPage.messages` (`watch`, `marked`, `unread`, `permission`, `ask`)
  and Task 2's full read.
- Produces:
  - `FairbandPage.inboxTab`: `'messages'` or `'queue'`, set by `show`. `show('inbox', 'queue')`
    writes `#inbox/queue`; any other second part gives `'messages'` and writes `#inbox`. A
    change of the tab with the view already shown is not the early return: the panels draw and
    `onShow.inbox` runs. `show` calls `FairbandPage.messages.watch(false)` when it shows another
    view.
  - `FairbandPage.inbox.tabs(tab, unread, open)`: a `div` with `role="tablist"` and
    `aria-label="Inbox"` holding two `button`s with `role="tab"`, ids `inbox-tab-messages` and
    `inbox-tab-queue`, `aria-selected`, `aria-controls="inbox-panel"`, each opening through
    `FairbandPage.show('inbox', ...)`; a label's count stands in a `span` after the name and is
    absent at 0. The panel under them is `role="tabpanel"`, id `inbox-panel`, labelled by the
    shown tab.
  - `FairbandPage.inboxMessages`: `load()`, which reads `/api/inbox/messages`; `view()`, the
    tab's panel; `row(message, marked)`; `line(permission, onAsk)`, the notification's line, or
    `null` for `'granted'`.
  - `inbox.js`'s `onShow.inbox` reads the queue as today, calls
    `FairbandPage.messages.watch(FairbandPage.inboxTab === 'messages')` and, on the Messages
    tab, `FairbandPage.inboxMessages.load()`. `fromHeader` reads the full list again where the
    cheap read holds a message the tab does not show.
- A message's row, in a table whose heads are `Symbol`, `Message`, `Summary`, `By`, `Ended`,
  `Report`:
  1. where `marked`, a `span` with `role="img"`, `aria-label="unread"` and the class
     `app-inbox__new`, before the symbol; the symbol a link, as the queue's;
  2. `Message`: the mode with a capital and the kind, "Full report done";
  3. `Summary` of `done`: the stance in the Research tab's chip
     (`fb-stance fb-stance--<stance> label`), then `Value <money>`, with ` (<basis>, <note>)`
     or ` (mechanical)` as in Task 3's body, ` · price <money> on <date> · valid until <date>`;
     with no value and a refusal, the chip and the refusal's sentence; with neither, a dash, as
     the queue's `none()`. Of `declined`: the reason as written, in a cell that wraps;
  4. `By`: `Fairband.PrincipalChip`, compact, or the dash where `by.principal` is null;
  5. `Ended`: `FairbandPage.when(message.at)`;
  6. `Report`: for `done` with a `reportId`, the queue's link and its accessible name, "Open
     revision 2 of the report for QCOM"; else the dash.
- The view: the line, then the sentence of Global Constraints where there is no message, a
  failed read's sentence as the queue words its own, or the table. The Work queue tab draws
  today's `table(items)` and "No work items." unchanged.
- The Methodology page's sentence: "The <a href="#inbox">Inbox</a> has two tabs. Messages tells
  the owner that an agent finished a report or declined a request. Work queue lists the work
  items (requests for an agent's research on one company). Request research in the drawer posts
  one."

- [ ] **Step 1: Write the failing tests** (`tests/web/test_inbox_messages_page.py`)

```python
MESSAGES, VIEW, INBOX = STATIC / "messages.js", STATIC / "inbox_messages.js", STATIC / "inbox.js"
DONE = {"itemId": 12, "symbol": "QCOM", "kind": "done", "mode": "full report",
        "at": "2026-11-08T17:56:00+00:00", "by": {"principal": "agent", "actor": "claude-opus-5-5"},
        "reportId": 9, "reportRevision": 2, "stance": "hold", "value": 210.87, "basis": "reviewed",
        "note": None, "price": 173.19, "priceDate": "2026-11-07", "validUntil": "2027-02-03", "refusal": None}


def _row(message: dict[str, Any], marked: bool = False) -> Any:
    return node("inboxMessages.row", [message, marked], MESSAGES, VIEW)


def test_a_done_row() -> None:
    tree = _row(DONE, True)
    words = text(tree)
    for part in ("QCOM", "Full report done", "Value $210.87", "price $173.19", "valid until"):
        assert part in words
    [mark] = [e for e in elements(tree) if e["props"].get("aria-label") == "unread"]
    assert mark["props"]["className"] == "app-inbox__new"
    [chip] = classed(tree, "fb-stance")
    assert chip["props"]["className"] == "fb-stance fb-stance--hold label"
    [link] = [e for e in elements(tree) if e["props"].get("aria-label") == "Open revision 2 of the report for QCOM"]
    assert link["props"]["href"] == node("researchHref", ["QCOM", 9])


def test_a_read_row_has_no_mark() -> None:
    assert [e for e in elements(_row(DONE)) if e["props"].get("aria-label") == "unread"] == []


def test_a_row_without_a_value() -> None:
    refused = DONE | {"value": None, "basis": None, "refusal": "no positive trailing earnings"}
    gone = DONE | {k: None for k in ("reportRevision", "stance", "value", "basis", "price", "priceDate", "validUntil")} \
        | {"by": {"principal": None, "actor": None}}
    assert "no positive trailing earnings" in text(_row(refused)) and "$" not in text(_row(refused))
    for bad in ("undefined", "null", "NaN", "$"):
        assert bad not in text(_row(gone))


def test_a_declined_row() -> None:
    reason = "No filing for the new quarter is on file yet. " * 12
    tree = _row({"itemId": 13, "symbol": "AMD", "kind": "declined", "mode": "valuation review",
                 "at": "2026-11-09T09:12:00+00:00", "by": {"principal": "agent", "actor": "claude-opus-5-5"},
                 "reason": reason})
    assert "Valuation review declined" in text(tree) and reason in text(tree)
    assert [e for e in elements(tree) if e["type"] == "a" and "report" in str(e["props"].get("aria-label"))] == []


@pytest.mark.parametrize(("permission", "words", "button"), [
    ("none", "This browser cannot show notifications at this address.", False),
    ("default", "Notifications are off.", True),
    ("denied", "The browser blocks notifications for this address. Allow them in the browser's site settings.", False),
])
def test_the_notification_s_line(permission, words, button) -> None:
    tree = node("inboxMessages.line", [permission, None], MESSAGES, VIEW)
    assert words in text(tree)
    assert ("Turn on notifications" in text(tree)) is button


def test_a_granted_permission_draws_no_line() -> None:
    assert node("inboxMessages.line", ["granted", None], MESSAGES, VIEW) is None


def test_the_tabs() -> None:
    tree = node("inbox.tabs", ["messages", 2, 1], MESSAGES, VIEW, INBOX)
    assert tree["props"]["role"] == "tablist" and tree["props"]["aria-label"] == "Inbox"
    first, second = [e for e in elements(tree) if e["props"].get("role") == "tab"]
    assert (text(first), text(second)) == ("Messages 2", "Work queue 1")
    assert (first["props"]["aria-selected"], second["props"]["aria-selected"]) == ("true", "false")
    assert first["props"]["aria-controls"] == second["props"]["aria-controls"] == "inbox-panel"
    quiet = node("inbox.tabs", ["queue", 0, 0], MESSAGES, VIEW, INBOX)
    assert [text(e) for e in elements(quiet) if e["props"].get("role") == "tab"] == ["Messages", "Work queue"]


def test_the_new_rules_hold_no_motion_and_no_pill() -> None:
    for selector in (".app-inbox__tabs", ".app-inbox__tab", ".app-inbox__new", ".app-inbox__notify"):
        rule = _rule(selector)
        assert "transition" not in rule and "animation" not in rule and "radius-pill" not in rule
    assert "border-radius: var(--radius-sm)" in _rule(".app-inbox__new")
```

In `tests/web/test_header.py`, on the driver:

```python
def test_the_inbox_s_address_holds_its_tab() -> None:
    trace = _trace([{"do": "hash", "hash": "#inbox/queue"}, {"do": "hash", "hash": "#inbox/zzz"},
                    {"do": "show", "view": "inbox"}, {"do": "show", "view": "inbox", "section": "queue"}])
    assert [t["hash"] for t in trace] == ["#inbox/queue", "#inbox", "#inbox", "#inbox/queue"]
```

- [ ] **Step 2: Run them and see each fail.** Run: `uv run pytest -q tests/web/test_inbox_messages_page.py tests/web/test_header.py -k "inbox or row or tabs or line or rules"`. Expected: FAIL.

- [ ] **Step 3: `controls.js`'s `show`** keeps the Inbox's second part, as it keeps a
  watchlist's (`keepList`), to the Interfaces block.

- [ ] **Step 4: Write `inbox_messages.js`** and its rules in `index.html`: the tabs' row, the
  mark (a 6px square of `--ink`), the notification's line. Reuse the queue's classes for the
  table, its wrapping cell and its error line.

- [ ] **Step 5: Change `inbox.js`**: the tabs, the panel, `onShow.inbox` and `fromHeader` to the
  Interfaces block. Its head comment says what the view is now.

- [ ] **Step 6: Change the Methodology page's sentence.**

- [ ] **Step 7: Run the full check.** Expected: all pass.

- [ ] **Step 8: Commit**

"Give the Inbox view two tabs, Messages for the owner and the work queue as built, draw a message
for each report an agent finished and each request an agent declined, and say so on the
Methodology page".

---

### Task 5: The README, the acceptance look, and the backlog

**Files:**
- Modify: `README.md`, `docs/backlog.md`
- Scratch only, never committed: a data folder, a script and screenshots in the session's
  scratchpad

- [ ] **Step 1: The README.** Line 35's "the agent inbox" becomes "the inbox". The research
  steps say, after the report is published: the Inbox's Messages tab shows a message and the
  browser a notification; the notification is turned on once with Turn on notifications on that
  tab; it needs an open Fairband tab; and Chrome's Memory Saver can put a long-hidden tab to
  sleep, which the reader prevents by adding the address under Settings, Performance, "Always
  keep these sites active". The screenshots stay as they are.

- [ ] **Step 2: A scratch server.** Make a scratch database (`connect` and `migrate` from
  `fairband.store.db`), attach the live file read-only and copy `policy_versions`, `refreshes`,
  `deciles`, `settings` and, for about twelve symbols, the newest universe rows of `companies`
  and the newest `snapshots` row; put one of them on a watchlist with its snapshot's
  `valid_until` in the past. Start the branch's server on it with `FAIRBAND_FMP_KEY` unset:
  `FAIRBAND_DATA_DIR=<scratch>/data XDG_CONFIG_HOME=<scratch>/config uv run python -m fairband serve --port 8499`.
  Post work items and publish reports through the scratch server's own routes with an agent's
  identity headers, as an agent's tools do.

- [ ] **Step 3: The checks** of the spec's section 11, items 1 to 7, with `playwright-core` and
  the cached Chromium, in both themes, the notification permission granted with the context's
  `grantPermissions(['notifications'])` and each `new Notification` recorded by a script added
  before the page's own. A second page of the same context stands for the second tab. Shown
  scrollbars: launch with `ignoreDefaultArgs: ['--hide-scrollbars']`.

- [ ] **Step 4: The two reads' times** (section 11, item 8): on a read-only copy of the live
  store, the median of twenty `GET /api/inbox` and of twenty `GET /api/inbox/messages`, in
  milliseconds, with the number of items and of messages. Report the four figures.

- [ ] **Step 5: Fix what a check finds**, test first, each fix a commit of its own. Stop the
  scratch server: `lsof -ti:8499 -sTCP:LISTEN | xargs -r kill`.

- [ ] **Step 6: The backlog.** B-322 moves from Now to Done in the table's own form: what was
  built in two or three sentences, the spec and this plan, the commits, the checks' count and
  the two reads' times. B-114's inbox clauses, B-295's items 6 and 7 and the first clause of
  B-202's item 4 close there, as the rule they describe left; the rows keep their other
  clauses. File what the build left as new rows, among them: a sound of the page's own, if
  Windows gives none at the founder's look; a limit on the items the 30-second read answers, if
  step 4's time calls for one. This commit is of documents alone and runs the short check.

- [ ] **Step 7: Show the founder.** Screenshots of both tabs in both themes, the results of the
  checks and the four figures of step 4. His own look on the live server comes after the merge:
  Turn on notifications, the test notification's place and its sound, and one real report's
  message. The merge, the restart of the live server (this build changes Python), and the push
  wait for the founder's word.
