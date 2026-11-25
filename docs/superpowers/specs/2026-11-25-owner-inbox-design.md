# The owner's inbox: design

Status: written 2026-11-25 from a brainstorm with the founder that day, quoted in the decision
log. The founder decided that the owner gets an inbox of his own, apart from the agents' work
queue; that a finished report gives a short message with a link to the research page; that a
notification with a sound tells him, as an email's does; that the watchlist expiry rule stops and
he asks for new research himself; that the page keeps asking the server and the server pushes
nothing; and that the Inbox view has two tabs. He agreed to four of Claude's proposals: the server
writes the message from the stored report, the notification is the browser's system notification,
the header counts unread messages, and an agent's decline gives a message. Every other choice
below is Claude's, marked *my call* where it is more than a reading of those decisions, and can
be overturned as any other. Backlog item B-322.

No valuation moves. Nothing here touches the engine, the classifier, the universe rule or a
policy value, so the method version stays `fairband-mechanical/1.10` and the policy
`fairband-policy-v19`. `docs/method.md` changes all the same, because it states the expiry rule
that leaves (section 9). The schema stays at 012. No MCP tool is added, removed or changed, and
no agent's write changes.

On the points it covers, this design replaces the Tier 2 spec of 2026-11-06 (section 8's expiry
rule, 18.5's header count) and the held reviewed value spec of 2026-11-23 (5.10).

## 1. What this is

Today the Inbox view is one table of work items, the requests for an agent's research: pending,
claimed, done, declined or dropped. It is the agents' queue. The header's Inbox count is the open
items, pending and claimed, which is work for an agent and not news for the owner. A done row
links to its report, but nothing tells the owner that the research ended: he looks, or he does
not know. The page reads the inbox every 30 seconds and stops while its tab is hidden
(`controls.js`, `pollInbox`), because each read also runs the expiry rule inside a write
transaction: Fairband posts a valuation review by itself for a watched company whose value
expired (`store/inbox.py`, `post_expiry_items`).

After this work the Inbox view has two tabs. Messages is the owner's: one line for each piece of
research that ended, the newest first, unread ones marked. Work queue is the present table. The
header counts the unread messages. When a message arrives, the browser shows a system
notification, which Windows draws at the bottom right with its own sound, whether the Fairband
tab is shown or hidden. Fairband posts no work item by itself.

```
Screen  Watchlists  Statistics  Methodology  Settings  Inbox 2

  [ Messages 2 ]  [ Work queue 1 ]
  Notifications are off.  [Turn on notifications]
  ──────────────────────────────────────────────────────────────────────────────────────────────
  ● QCOM  Full report done           HOLD  Value $211 · price $173.19 on 8 Nov 2026 ·   revision 2
                                           valid until 3 Feb 2027
          claude-opus-5-5 · 8 Nov 2026, 17:56
  ● AMD   Valuation review declined  No filing for the new quarter is on file yet.
          claude-opus-5-5 · 9 Nov 2026, 09:12
    MSFT  Valuation review done      HOLD  Value $518 · price $533.16 on 11 Nov 2026 ·  revision 1
                                           valid until 28 Jan 2027
          claude-opus-5-5 · 11 Nov 2026, 14:03
```

The sketch shows what a row holds, not its layout, which is the builder's (section 13).

## 2. Goals

1. The owner learns that research ended without looking for it: a message in the Inbox and a
   system notification with the system's sound, also while the Fairband tab is hidden.
2. A message says in one line what ended and how, and links to the report.
3. The header's Inbox count is the owner's unread messages.
4. The work queue stays as built, on a tab of its own.
5. Fairband posts no work item by itself. The expiry rule leaves.
6. A read of the inbox writes nothing and takes no write lock, so it can run while the tab is
   hidden.

## 3. Non-goals

- A push from the server (Server-Sent Events, a WebSocket). Section 6 says why.
- A notification while no Fairband tab is open, or with the browser closed. That needs a service
  worker and an outside push service.
- A sound the page plays itself, and a popup drawn inside the page.
- A message an agent writes. No new MCP tool, no change to `inbox_complete`, `inbox_decline` or
  `report_submit`, no new step in the playbook.
- A message for any other event: a refresh that ended, a value that expired, a launch that
  failed.
- A read mark for one message, a way to mark a message unread, to delete one or to filter them.
- A switch in Settings for the notification. The browser's permission is the switch.
- Any change to how a value's expiry is shown: the row's `expired`, the drawer's reasons and the
  company page stay as they are (`engine.held`, method 14.6).
- Any change to the Work queue's table, its Decline or its Open Claude Code.
- Dropping the `expiry_*` columns of `work_items`, the origin `expiry` or the state `dropped`.
  Stored rows carry them.

## 4. Anti-goals

Each of these would make the work a failure even if it ran.

- A notification that repeats: twice for one message, again at a reload, or once from each open
  Fairband tab with a sound each time.
- A burst of notifications or unread marks for old research: at the first load after this build
  (the live store holds 56 done items), or when the owner grants the permission later.
- A figure in a message that differs from the figure the report's own page shows.
- A motion in the page beyond the three `CLAUDE.md` allows.
- A request for the notification permission that the owner did not press for.
- A 30-second read whose number of queries grows with the reports on file, or that parses a
  stored result or a report's text. Its rows grow with the work items, as they do today; a limit
  on them is not part of this build, and the acceptance measures the read (section 11).
- A message that is never marked and never notified, because another ended at nearly the same
  moment.

## 5. Constraints

- `CLAUDE.md` allows motion in three places and no other. The system notification is the
  operating system's surface, not the page's, so the rule stands unchanged. The unread mark, the
  count and a new row appear with no transition.
- The brand book: "A value without its dates is not a value." A message that shows a value shows
  the price's date and the end of the validity window with it. A work item is a "work item",
  never a task or a ticket. Vendor data rules do not apply: a message shows Fairband's own
  figures.
- The Notification API needs a secure context. The server listens on `127.0.0.1` alone
  (`__main__.py`, `_HOST`), and a browser treats `http://127.0.0.1:<port>` and
  `http://localhost:<port>` as secure. At another address the page says that it cannot notify
  (7.6).
- A browser slows the timers of a hidden tab, to about one a minute after some minutes. So a
  notification can arrive about a minute after the research ended. The founder accepted this.
  A browser can also put a long-hidden tab to sleep (Chrome's Memory Saver); such a tab shows
  nothing until it wakes. The README says how to exclude the address (section 9).
- A notification's text stays on the machine: the API hands it to the operating system, and
  no outside service takes part. No key and no vendor payload is in it.
- The owner alone has messages. An agent's `inbox_list` answers what it answers today.
- The repository is public. Test fixtures are synthetic.

## 6. Approaches

Four choices, each with the ways considered and the one picked.

**How the page learns of a message.** (a) The page asks the server every 30 seconds, as it does
today, and also while hidden. (b) The server pushes over one open connection (Server-Sent
Events). Picked: (a). Push brings the notification within a second, not within a minute, which
is worth little for research that takes many minutes. Its costs here: the server's first
connection that stays open, where every route today answers and closes, with a restart that can
wait on it and a worker thread held for each tab; a browser's limit of six connections to one
address under HTTP/1.1, which uvicorn serves, so six open Fairband tabs would stop every page
from loading; and the plain read is needed anyway at opening and after each reconnect. With the
expiry rule gone the read is a few plain queries, so asking is cheap. The founder confirmed (a)
on 2026-11-25. Push can replace it later with no rework of the rest.

**Who writes the message.** (a) The server builds it at each read from the work item, its report
and the report's records. (b) The agent writes a summary through a new or a wider tool. Picked:
(a), agreed by the founder. It needs no tool and no playbook change, it covers every report
already on file, and no free text with figures passes outside the report's cite check.

**The notification.** (a) The browser's system notification. (b) A popup inside the page with a
sound the page plays. Picked: (a), agreed by the founder. The owner is most likely in another
window when the research ends, and a popup inside a hidden page is not seen. The system draws
(a) over any window, at the bottom right on Windows, with its own sound, and keeps it in its
notification centre. (b) would also be a fourth motion in the page, and a browser blocks a
page's sound until the owner has clicked in that page.

**The layout.** (a) Two tabs inside the Inbox view. (b) Two blocks on one scrolling page, the
messages over the queue. (c) A seventh entry in the menu. Picked: (a), by the founder. In (b)
the messages grow with every report and move the queue down the page. (c) adds to the header,
which already wraps under 450px. With (a) the present table and its tests stay as built.

## 7. The design

### 7.1 What gives a message

A work item gives one message, or none, by its state:

| The item | The message |
|---|---|
| `done`, whatever its origin | "done": the research ended with a report |
| `declined`, and an agent wrote the decline | "declined": the agent's reason |
| `declined` by the owner | none: he did it himself |
| `pending`, `claimed`, `dropped` | none |

Who wrote a decline is in the ledger: the row of kind `decline` that names the work item, its
`principal` (`agents_api.py`, `move`, `_record_item`). A declined item with no such row gives no
message.

A message is not a stored record. The server reads it from the item, the report and the report's
records each time it is asked (*my call*: nothing is stored twice, so a message cannot disagree
with its report). An item's closed state is final, so its id names its message for good. A
message's time is the item's `finished_at`, and the list is drawn by it, the newest first; the
time orders the rows and decides nothing else (7.3).

### 7.2 The two reads

**The cheap read**, `GET /api/inbox`, every 30 seconds from each open tab. It loses the expiry
rule (section 8), so it opens no write transaction. Its answer keeps today's shape, and each
item gains one field, `declinedBy`: the principal that wrote the item's decline, `owner` or
`agent`, and `null` for an item that is not declined or has no such ledger row. The page tells
from the items alone which of them are messages (7.1), which is the newest, and how many are
unread (7.3). The read runs a fixed number of queries whatever the number of items, beside the
one query for each open item's launch that it runs today, and it parses no stored result and no
report's sections. `inbox_list` passes the answer on as it does today; the new field is the only
change an agent sees.

**The full read**, a new route, `GET /api/inbox/messages` (*my call*: its name and shape). It
answers every message, the newest first, each with what a row draws:

- for both kinds: `itemId`, `symbol`, `kind` (`done` or `declined`), `mode`, `at`, and who ended
  it, as the principal and the agent's model identifier;
- for `done`: `reportId`, `reportRevision`, `stance`, and the report's call as the Research tab
  answers it for that report (`web/research_page.py`, `report_call`): `value`, `basis`, `note`,
  `price`, `priceDate`, `validUntil` and `refusal`;
- for `declined`: `reason`, as written.

The `mode` of a `done` message is the report's, which says what was made: nothing checks that a
report's mode is its item's, so a full report's item can end with a valuation review. The `mode`
of a `declined` message is the item's. The read carries no currency: the call's figures are in
US dollars and the value card writes them with `F.formatMoney`, as a message's row does. The
Research tab's line on a foreign filer's reporting currency is about the report's text and has
no place in a message.

The author of a `done` message is the report's (`reports.actor`, `reports.principal`); of a
`declined` one, the decline's ledger row.

The page asks for the full read in three cases only: the Messages tab opens; the cheap read
shows a new message while the Messages tab is shown; a notification is to be drawn (7.6). It is
the owner's read: a request that carries an agent's identity headers gets a 403, as the launch
routes answer (*my call*).

The figures are `report_call`'s and nothing else computes one. So a message for QCOM's revision
2 and the value card on `#company/QCOM/research/<id>` show the same value, price and dates,
today and after any later refresh.

### 7.3 Unread, and what the browser keeps

The browser keeps two lists in `localStorage`, each of work item ids, a message being named by
its item (*my call*, after the watchlist page's default, which the browser keeps too; the cost
is that another browser has lists of its own):

- `fairband.inbox.seen`: the messages the owner saw in the Messages tab.
- `fairband.inbox.notified`: the messages a notification was handled for.

The lists hold ids and not a newest time. An item's `finished_at` is read from the clock before
its write waits for the store's lock (`agents_api.py`, `move`; `reports_api.py`), so two items
that end at nearly the same moment can be saved in the other order than their times. A "newest
time seen" would then pass over the one saved later, for good. Ids have no such order to trust.

A message is unread while its item is not in `seen`. The header's count is the number of unread
messages.

The owner sees the messages while three things hold together: the Inbox view is shown, its tab
is Messages, and the document is not hidden. When a read lands while they hold, and when they
come to hold over a read that already landed (the tab is opened, the browser's tab comes back
to the front), the page adds every message's id to `seen`. The header's count goes to none at
once. The rows that were unread at that moment keep their mark until the owner leaves the Inbox
view or changes the tab, so he sees which are new (*my call*: a list the owner saw is read;
there is no read mark for one row and no button). A hidden browser tab that was left on Messages
adds nothing to `seen`, so its count and every other tab's still show the message.

A list that is missing is written at the first read that lands, with the id of every message in
that read, and as an empty list where there is none. Nothing is unread and nothing is notified
by that read. This is the first load after the build, a new browser and cleared site data. So
the 56 done items of the live store give no mark and no notification, and a store with no
message yet marks and notifies its first one. Each later write of a list keeps only the ids the
read holds, so a list does not outgrow the messages on file.

Where the browser refuses `localStorage`, the page keeps both lists in memory for the page's
life, by the same rules.

A change of a list in one tab reaches the other open tabs through the browser's `storage` event,
and each draws its count again.

### 7.4 The Inbox view

Two tabs at the top of the Inbox view's panel, which today holds the table alone (`inbox.js`,
`View`). They are built as the company page's tabs are (`company.js`, the tab list and its
buttons), with the names and the panel that B-222 says those lack (`aria-controls`, a tab panel,
a name on the list).

- **Messages** is the first tab, and `#inbox` opens it. Its label carries the unread count, and
  no number when there is none.
- **Work queue** is the second, at `#inbox/queue`. Its label carries the open items, pending and
  claimed, which is the number the header carries today, and no number when there is none.

The address holds the tab, so a reload and the browser's Back keep it. This is new routing:
today `show` writes any `#inbox/<x>` back to `#inbox` (`controls.js`), and a view keeps a second
part for Methodology, the company page and Watchlists alone. The Inbox joins them. An unknown
second part opens Messages and the address reads `#inbox`.

A message's row holds:

1. the unread mark, with an accessible name ("unread");
2. the symbol, a plain link to the company page, as in the Work queue;
3. what ended, as words: the mode and "done" or "declined" ("Full report done", "Valuation
   review declined");
4. for `done`: the stance in the Stance column's chip, then the value, the price with its date
   and the end of the validity window, in the page's own money and date forms; where the call
   holds a secondary valuation's note or a mechanical basis, that word stands with the value, as
   on the value card; where the call has no value, the chip and the refusal's sentence, and no
   figure;
5. for `declined`: the reason as written;
6. who ended it, the compact `PrincipalChip`, and when, in the reader's time (`P.when`);
7. for `done`: a link to the report on the Research tab, named by its revision, with the Work
   queue's accessible name ("Open revision 2 of the report for QCOM").

With no message the tab shows one sentence: "No messages. One arrives when an agent finishes a
report or declines a request." A failed full read shows the server's sentence, as the Work queue
does.

The Work queue tab is today's table and behaviour: its columns, its reads, Decline, Open Claude
Code and the launch's line. Nothing in it changes but where it stands.

### 7.5 The header

The Inbox entry's count is the unread messages (7.3), from the cheap read and the `seen` list.
It no longer counts the open items. A post from the drawer or the company page changes no number
in the header, so the gap found in the brainstorm (the count waiting up to 30 seconds after
Request research) has nothing left to correct.

### 7.6 The notification

**The permission.** The Messages tab's head holds one line about the notification, by the
browser's state:

| The state | The line |
|---|---|
| no `Notification` in the browser, or the page is not a secure context | "This browser cannot show notifications at this address." |
| `default` | "Notifications are off." and a button, Turn on notifications |
| `denied` | "The browser blocks notifications for this address. Allow them in the browser's site settings." |
| `granted` | no line |

Turn on notifications asks the browser for the permission, and nothing else in the page ever
does. When the owner grants it, the page shows one notification at once, titled "Fairband" with
the body "Notifications are on.", so he sees where it appears and hears its sound.

**When.** After each cheap read that lands, in every open tab, hidden or shown: where a
message's id is not in `notified`, the page adds those ids to `notified` first, and then, if the
permission is granted, asks for the full read and shows a notification for each of those
messages. More than three at once give one notification in their place, "4 new messages", which
opens the Messages tab. The list takes the ids whether or not the permission is granted, so a
later grant brings nothing old.

**One, not many.** Each notification carries a tag of its own, `fairband-message-<itemId>`. Two
tabs that read at the same moment can each show it; the second replaces the first under the same
tag, and without `renotify` the system gives no second sound. The list, written before the full
read is asked for, stops every later read.

**The text.** Title: the symbol and what ended, "QCOM: full report done", "AMD: valuation review
declined". Body, for `done`: "Hold. Value $211 against a price of $173.19 on 8 Nov 2026. Valid
until 3 Feb 2027."; with no value, the stance and the refusal's sentence. For `declined`: the
reason. The figures are the row's own.

**A click** on it brings the Fairband tab to the front and opens the report on the Research tab,
or the Messages tab for a decline, and closes the notification.

**The sound** is the operating system's, which it plays with a notification unless the owner
muted it there (Focus assist on Windows). The page sets no `silent` and plays nothing itself.
Whether Windows gives the sound on the founder's machine is checked by ear at the acceptance
(section 11); if it gives none, a sound of the page's own is a new backlog item and not part of
this build.

### 7.7 The read while the tab is hidden

`pollInbox` no longer stops while the document is hidden. The 30-second cycle runs on, as slowly
as the browser lets a hidden tab's timers run, and the read at once on becoming visible stays.
The comment that explains the pause by the write lock goes with the pause.

## 8. The expiry rule leaves

Fairband posts no work item by itself and drops none. From `store/inbox.py` go
`post_expiry_items` and what only it calls (`_due`, `_note`, `_posted_for`, `_record_expiry`),
`drop_item`, and the `expiry_*` parameters of `post_item`; from `GET /api/inbox`, the call. A
function of `engine.held` or of another module that loses its last caller goes too; one that the
rows or the drawer still call stays.

What stays: the columns `expiry_valid_until`, `expiry_review_id` and `expiry_secondary_id`, and
their fields in an item's answer; the origin `expiry` and the state `dropped` as values a stored
row can hold; the system's chip in the Work queue for such a row. A pending item of origin
`expiry` in a store stays pending, and the owner opens Claude Code on it or declines it, as on
any item (*my call*: no migration moves them; the live store has none, section 12).

A value's expiry is shown as before: the row reads `expired`, the drawer and the company page
give the reasons. The owner sees it there and asks for the research.

## 9. The documents

In the same commit as the code they describe:

- `docs/method.md`: the glossary's Work item row loses "or the expiry rule" and "or dropped"
  stays, since a stored row can hold it; the paragraph on a held value's state (section 14.6)
  loses its sentences on the inbox's expiry rule, from "The inbox's expiry rule, run when the
  inbox is read" to the paragraph's end, and says in their place that Fairband posts no work
  item for an expired value. These are the document's only two statements on the inbox. The
  method version and the policy stay.
- The report's glossary (`reports/render.py`), which carries the same Work item sentence.
- The Methodology page: the sentence on the Inbox names its two tabs and what a message is. The
  method version does not change, so no example's figures are read again.
- The playbook (`playbook/fairband-research/SKILL.md`): the sentence on an item of origin
  `expiry` says what is true after the build, that such an item is one Fairband posted under a
  rule that no longer runs and is worked as a valuation review.
- `README.md`: the research steps say that the Inbox shows a message and the browser a
  notification when the report is published, with the one press that turns the notification on
  and how to exclude the address from Chrome's Memory Saver. The screenshots stay as they are.
- `docs/backlog.md`: this build's row; B-114's inbox clauses, B-295's items 6 and 7 and the
  first clause of B-202's item 4 close, as the rule they describe left; what the build leaves is
  filed.

## 10. Tests the builder must write

- The cheap read: opens no write transaction and writes no row (a store whose watched company's
  value expired gets no item); `declinedBy` for an owner's decline, an agent's, and an item not
  declined; the number of queries does not grow with the done items.
- The full read: a `done` message's figures equal `report_call`'s for that report, for a
  reviewed value, a secondary valuation and a call with no value; a `declined` message for an
  agent's decline and none for the owner's; the order; the 403 for an agent's request.
- The store: `post_item` without its expiry parameters; no `drop_item`; a stored row of origin
  `expiry` or state `dropped` still reads.
- The page, run in node as the launch tests are: the count from the items and the `seen` list;
  a missing list written at the first read with nothing unread and nothing notified, as an empty
  list on a store with no message, whose first message is then marked and notified; two messages
  saved in the other order than their times, both marked and both notified; `seen` written as
  the Messages tab shows, not while the document is hidden, and again as it comes back; the
  marks kept until the tab changes; the lists kept in memory where `localStorage` throws; the
  `storage` event; the two tabs and their addresses, an unknown second part among them; the four
  permission lines; the ask on the press alone; the notification once for a new message, its
  tag, its text for each kind, one in place of more than three, none without the permission
  while the list still takes the ids; the click's address; the read that runs while
  `document.hidden`.
- The documents' own tests (`tests/test_method_doc.py`, `tests/test_playbook.py`,
  `tests/reports/test_render.py`) on the changed sentences.

## 11. Acceptance

On a scratch database and a spare port, in a headless browser, both themes, with the
notification permission granted through the browser's own test controls and each notification
the page makes recorded:

1. At the first load, with done items on file: no unread mark, a count of none, no notification.
2. An agent's `report_submit` and `inbox_complete` on a claimed item, the browser's tab hidden,
   once left on the Screen and once left on the Inbox's Messages tab: within one read the header
   counts 1 and one notification is recorded, with the title, the body and the tag of 7.6; a
   reload records none; a second open tab adds none under another tag.
3. The Messages tab: the row's figures equal the Research tab's value card for that report; the
   mark shows, the count goes to none, and the mark is gone after a change of tab.
4. An agent's decline gives a message and a notification; the owner's decline gives neither.
5. The Work queue tab at `#inbox/queue`: today's table, Decline and Open Claude Code working.
6. A watched company whose value expired: no work item appears, and its row still reads
   `expired`.
7. The permission lines for `default`, `denied` and no `Notification`.
8. The time of the cheap read and of the full read on a copy of the live store, as figures.

Then the founder's own look on the live server: Turn on notifications, the test notification's
place and its sound, and one real report's message.

## 12. Facts read on 2026-11-25

- The live store holds 56 work items, all `done`: 51 posted by the owner and 5 by an agent. It
  holds no item of origin `expiry`, none pending and none declined, and 56 reports.
- The ledger's kinds for a work item's writes in the live store are `work-item`, `claim`,
  `report` and `complete`; a decline writes `decline` (`agents_api.py`, `move`).
- `tests/web/test_header.py` holds the header's tests, the 30-second cycle's among them.

## 13. Left to the builder

- The row's layout, its classes and its words where 7.4 gives none, within the brand book.
- Whether the tabs share the company page's classes or take their own.
- The full read's field names and how it reads who wrote a decline.
- The notification's icon.
- How the page tests stand in for `Notification`, `localStorage` and `document.hidden`.
- The order of the work, and whether the rule's removal is a commit of its own before the page's.

## Decision log

- 2026-11-25, the founder: "I am thinking about our inbox, and whether its a true inbox. Its
  more of a work queue for agents. I thinking maybe we have a different inbox for the user, once
  an agent is done with generating the report, the agent publishes a message to the user's inbox
  notifying that the research is done, gives a very short summary of the reserach, and a link to
  the research page. Also, I am thinking of a popup notification in the bottom right (like an
  email notification) that pops and go'es away with a sound."
- 2026-11-25, the founder, on the expiry rule: "assume we will stop the wathclist expiry rule and
  instead will depend on the user to request updated reserach rather than posting an automatic
  request." Taken as a requirement of this build, and confirmed by him with the playback.
- 2026-11-25, the founder, on push against asking: "if we implement one pipe, we should use it
  for both no?" One way serves the count and the notification. Claude first recommended push for
  the notification, then withdrew it for the costs in section 6; the founder confirmed asking.
- 2026-11-25, the founder, on the playback (the server writes the message; the system
  notification; one Inbox view whose header counts unread messages; an agent's decline gives a
  message): "I agree with everything".
- 2026-11-25, the founder, on the layout: "tabs make sense."
- 2026-11-25, Claude, after the playback: the unread state is kept in the browser and not in
  the store, so the schema does not change. In the brainstorm Claude had named a schema change
  (012 to 013) for a read mark; the two lists of 7.3 replace it.
- 2026-11-25, Claude, on a reviewer's reading of the document as its builder: the browser keeps
  ids and not a newest time, since two items can be saved in the other order than their times;
  the owner sees the messages only while the document is not hidden; a missing list is written
  empty on a store with no message; the 30-second read's limit is its queries, not its rows; the
  full read carries no currency; a done message is named by its report's mode; the Inbox's
  second address part is new routing.
- 2026-11-25, Claude: the figures come from a second read, asked for only when a row or a
  notification is drawn, so the 30-second read stays a few plain queries.
- 2026-11-25, Claude, where the build differs from 7.3: `seen` is written as the union of the
  stored list and the read's ids, where 7.3 says each later write keeps only the ids the read
  holds: a second tab's older read would otherwise un-see what the owner saw in the first.
  `notified` is written as 7.3 says.
- 2026-11-25, Claude: the unread mark is 8px, where the plan said 6px: a 6px square with the 3px
  corner is a round dot. Question B-324.
- 2026-11-25, Claude, where the build differs from 7.2: the page asks for the full read in more
  cases than its three. A launch's reread and a decline that lands on the Messages tab each ask
  once more, and a message that lands while the Messages tab shows with the permission granted
  asks twice. Filed as B-326.
- 2026-11-25, Claude, where the build differs from 7.6: more than three new messages at once ask
  for no full read, since the one notification in their place needs no figure.
- 2026-11-25, Claude, where the build differs from 7.6: a done message's notification opens the
  Messages tab, not the report, where the report has no revision on file.
- 2026-11-25, Claude: `docs/agents.md` also stated the expiry rule and is corrected with the
  build; section 9 did not name it.
- 2026-11-25, the founder, on the look's screenshot, whose test reports had no review and so
  read "Value $187.39 (mechanical)": "the agent did a research and also would provide a reviewed
  value. That is the value that should be in the message and it should be called the fair
  value." Told that the Screen and the report's page call that number the reviewed value, he
  ruled: "fine, call it revewied value for consistency". A message names its value "Reviewed
  value", in the row and in the notification, where 7.4 and 7.6 write "Value". The figure is
  still `report_call`'s: the reviewed value of a report with a review. On the live store that
  day, 51 of 56 messages hold a reviewed value, 3 rest on the mechanical value (their reports
  name no review, the research having changed no input), 1 on a secondary valuation, and 1 has
  no value. Claude's call for the other two cases: "Reviewed value $210.87 (secondary
  valuation)", and "Mechanical value $95.10 (unchanged)" for a report with no review, the
  Screen's own name for that number.
