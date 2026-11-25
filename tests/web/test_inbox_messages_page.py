"""The Inbox view's two tabs and its Messages tab (spec 2026-11-25 owner's inbox, 7.3, 7.4 and
7.6): Messages, the owner's, first, at #inbox, and Work queue, the work items as built, at
#inbox/queue; a message's row, for a report an agent finished and for a request an agent
declined; and the one line about the browser's notification, by its permission. The row, the
line and the tabs run in node (``support.page``); the view with the header
(``tests/web/header.mjs``, inbox_messages.js and inbox.js loaded after controls.js) on steps the
test gives, the tests reading the trace."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

MESSAGES, VIEW, INBOX = STATIC / "messages.js", STATIC / "inbox_messages.js", STATIC / "inbox.js"
DRIVER = Path(__file__).parent / "header.mjs"
CHEAP, FULL = "/api/inbox", "/api/inbox/messages"
AGENT = "claude-opus-5-5"
DONE: dict[str, Any] = {
    "itemId": 12,
    "symbol": "QCOM",
    "kind": "done",
    "mode": "full report",
    "at": "2026-11-08T17:56:00+00:00",
    "by": {"principal": "agent", "actor": AGENT},
    "reportId": 9,
    "reportRevision": 2,
    "stance": "hold",
    "value": 210.87,
    "basis": "reviewed",
    "note": None,
    "price": 173.19,
    "priceDate": "2026-11-07",
    "validUntil": "2027-02-03",
    "refusal": None,
}
NONE_YET = "No messages. One arrives when an agent finishes a report or declines a request."
CANNOT = "This browser cannot show notifications at this address."
OFF = "Notifications are off."
BLOCKED = (
    "The browser blocks notifications for this address. Allow them in the browser's site settings."
)


def _rule(selector: str) -> str:
    """The declarations of the page's rule for ``selector``."""
    pattern = rf"\n  {re.escape(selector)} \{{(.*?)\}}"
    found = re.search(pattern, _static_file("index.html"), re.DOTALL)
    assert found is not None, selector
    return " ".join(found.group(1).split())


def _row(message: dict[str, Any], marked: bool = False) -> Any:
    return node("inboxMessages.row", [message, marked], MESSAGES, VIEW)


# ------------------------------------------------------------------------------- a message's row


def test_a_done_row() -> None:
    tree = _row(DONE, True)
    words = text(tree)
    for part in ("QCOM", "Full report done", "Value $210.87", "price $173.19", "valid until"):
        assert part in words
    [mark] = [e for e in elements(tree) if e["props"].get("aria-label") == "unread"]
    assert mark["props"]["className"] == "app-inbox__new"
    [chip] = classed(tree, "fb-stance")
    assert chip["props"]["className"] == "fb-stance fb-stance--hold label"
    [link] = [
        e
        for e in elements(tree)
        if e["props"].get("aria-label") == "Open revision 2 of the report for QCOM"
    ]
    assert link["props"]["href"] == node("researchHref", ["QCOM", 9])


def test_a_done_row_s_summary_in_full() -> None:
    """7.4: the value with its price, the price's date and the end of the validity window, in the
    page's money and date forms; a secondary valuation's note or a mechanical basis stands with
    the value, as in the notification's words (messages.js) and on the value card."""
    [summary] = [e for e in elements(_row(DONE)) if e.get("type") == "td"][2:3]
    assert text(summary) == (
        "hold Value $210.87 · price $173.19 on 7 Nov 2026 · valid until 3 Feb 2027"
    )
    secondary = text(_row(DONE | {"note": "secondary valuation"}))
    assert "Value $210.87 (reviewed, secondary valuation) · price" in secondary
    mechanical = text(_row(DONE | {"basis": "mechanical"}))
    assert "Value $210.87 (mechanical) · price" in mechanical


def test_a_read_row_has_no_mark() -> None:
    assert [e for e in elements(_row(DONE)) if e["props"].get("aria-label") == "unread"] == []


def test_a_row_without_a_value() -> None:
    refused = DONE | {"value": None, "basis": None, "refusal": "no positive trailing earnings"}
    gone = (
        DONE
        | dict.fromkeys(
            ("reportRevision", "stance", "value", "basis", "price", "priceDate", "validUntil")
        )
        | {"by": {"principal": None, "actor": None}}
    )
    assert "no positive trailing earnings" in text(_row(refused))
    assert "$" not in text(_row(refused))
    for bad in ("undefined", "null", "NaN", "$"):
        assert bad not in text(_row(gone))


def test_a_declined_row() -> None:
    reason = "No filing for the new quarter is on file yet. " * 12
    tree = _row(
        {
            "itemId": 13,
            "symbol": "AMD",
            "kind": "declined",
            "mode": "valuation review",
            "at": "2026-11-09T09:12:00+00:00",
            "by": {"principal": "agent", "actor": AGENT},
            "reason": reason,
        }
    )
    assert "Valuation review declined" in text(tree) and reason in text(tree)
    assert [
        e
        for e in elements(tree)
        if e.get("type") == "a" and "report" in str(e["props"].get("aria-label"))
    ] == []
    # the reason wraps in its cell, as a declined item's does in the work queue
    [cell] = [e for e in elements(tree) if e.get("type") == "td" and reason in text(e)]
    assert "app-inbox__wrap" in cell["props"]["className"].split()


# ------------------------------------------------------------------------- the notification's line


@pytest.mark.parametrize(
    ("permission", "words", "button"),
    [
        ("none", CANNOT, False),
        ("default", OFF, True),
        ("denied", BLOCKED, False),
    ],
)
def test_the_notification_s_line(permission: str, words: str, button: bool) -> None:
    tree = node("inboxMessages.line", [permission, None], MESSAGES, VIEW)
    assert words in text(tree)
    assert ("Turn on notifications" in text(tree)) is button


def test_a_granted_permission_draws_no_line() -> None:
    assert node("inboxMessages.line", ["granted", None], MESSAGES, VIEW) is None


# ----------------------------------------------------------------------------------- the tabs


def test_the_tabs() -> None:
    tree = node("inbox.tabs", ["messages", 2, 1], MESSAGES, VIEW, INBOX)
    assert tree["props"]["role"] == "tablist" and tree["props"]["aria-label"] == "Inbox"
    first, second = [e for e in elements(tree) if e["props"].get("role") == "tab"]
    assert (text(first), text(second)) == ("Messages 2", "Work queue 1")
    assert (first["props"]["aria-selected"], second["props"]["aria-selected"]) == ("true", "false")
    assert first["props"]["aria-controls"] == second["props"]["aria-controls"] == "inbox-panel"
    assert (first["props"]["id"], second["props"]["id"]) == (
        "inbox-tab-messages",
        "inbox-tab-queue",
    )
    quiet = node("inbox.tabs", ["queue", 0, 0], MESSAGES, VIEW, INBOX)
    assert [text(e) for e in elements(quiet) if e["props"].get("role") == "tab"] == [
        "Messages",
        "Work queue",
    ]


def test_the_new_rules_hold_no_motion_and_no_pill() -> None:
    for selector in (
        ".app-inbox__tabs",
        ".app-inbox__tab",
        ".app-inbox__new",
        ".app-inbox__notify",
    ):
        rule = _rule(selector)
        assert "transition" not in rule and "animation" not in rule and "radius-pill" not in rule
    assert "border-radius: var(--radius-sm)" in _rule(".app-inbox__new")


def test_the_script_loads_before_the_view_s() -> None:
    html = _static_file("index.html")
    at = [
        html.index(f'<script src="/static/{name}"></script>')
        for name in ("messages.js", "inbox_messages.js", "inbox.js")
    ]
    assert at == sorted(at)


# ------------------------------------------------------------------------------- the view, driven


def _view(steps: list[dict[str, Any]], **given: Any) -> list[dict[str, Any]]:
    """The trace of ``steps`` on the page loaded with ``given`` (``tests/web/header.mjs``), the
    Inbox view's scripts loaded after controls.js as index.html loads them."""
    assert NODE is not None
    scripts = ("app.js", "finder.js", "messages.js", "controls.js", "inbox_messages.js", "inbox.js")
    done = subprocess.run(
        [NODE, str(DRIVER), str(BUNDLE)] + [str(STATIC / name) for name in scripts],
        input=json.dumps({"steps": steps} | given),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


def _item(item_id: int, symbol: str, state: str, at: str | None) -> dict[str, Any]:
    """A work item as the inbox's cheap read answers it, a done one with its report."""
    return {
        "id": item_id,
        "symbol": symbol,
        "mode": "full report",
        "note": "",
        "origin": "owner",
        "postedBy": "owner",
        "postedActor": None,
        "postedAt": "2026-11-01T09:00:00+00:00",
        "state": state,
        "claimedBy": AGENT,
        "reportId": item_id + 100 if state == "done" else None,
        "reportRevision": 1 if state == "done" else None,
        "reason": None,
        "finishedAt": at,
        "declinedBy": None,
        "launch": None,
    }


def _message(item: dict[str, Any]) -> dict[str, Any]:
    """The message of a done ``item`` as the full read answers it."""
    return DONE | {
        "itemId": item["id"],
        "symbol": item["symbol"],
        "at": item["finishedAt"],
        "reportId": item["reportId"],
        "reportRevision": item["reportRevision"],
    }


QCOM = _item(1, "QCOM", "done", "2026-11-08T17:56:00+00:00")
MSFT = _item(2, "MSFT", "done", "2026-11-11T14:03:00+00:00")
CLAIMED = _item(3, "AMD", "claimed", None)
TICK = {"do": "tick"}


def _read(items: list[dict[str, Any]]) -> dict[str, Any]:
    """The oldest cheap read in flight answers ``items``."""
    return {
        "do": "answer",
        "url": CHEAP,
        "status": 200,
        "body": {"launchReady": False, "items": items},
    }


def _full(items: list[dict[str, Any]]) -> dict[str, Any]:
    """The oldest full read in flight answers the messages of ``items``."""
    body = {"messages": [_message(item) for item in items]}
    return {"do": "answer", "url": FULL, "status": 200, "body": body}


def _show(section: str | None = None) -> dict[str, Any]:
    return {"do": "show", "view": "inbox", "section": section}


def _press(name: str, **more: Any) -> dict[str, Any]:
    return {"do": "inbox", "name": name} | more


def test_the_messages_tab_opens_first_and_reads_the_messages() -> None:
    """7.4: #inbox opens Messages, the first tab, and the view reads the queue as before and the
    messages (7.2); the panel is labelled by the tab it shows."""
    opened, _, _, drawn = _view([_show(), _read([QCOM]), _read([QCOM, CLAIMED]), _full([QCOM])])
    assert opened["hash"] == "#inbox"
    assert sorted(opened["reads"]) == [CHEAP, FULL]
    assert drawn["inbox"]["tabs"] == [["Messages", "true"], ["Work queue 1", "false"]]
    assert drawn["inbox"]["panel"] == "inbox-tab-messages"
    assert drawn["inbox"]["messages"] == [["QCOM", False]]
    assert drawn["inbox"]["queue"] == []


def test_the_work_queue_tab_at_its_address_reads_no_message() -> None:
    """7.4: #inbox/queue opens the Work queue, today's table, and the full read is not asked for;
    a reload there keeps it."""
    trace = _view([{"do": "hash", "hash": "#inbox/queue"}, _read([QCOM]), _read([QCOM])])
    opened, drawn = trace[0], trace[-1]
    assert opened["hash"] == "#inbox/queue" and opened["reads"] == [CHEAP]
    assert drawn["inbox"]["tabs"] == [["Messages", "false"], ["Work queue", "true"]]
    assert drawn["inbox"]["panel"] == "inbox-tab-queue"
    assert drawn["inbox"]["queue"] == ["QCOM"] and drawn["inbox"]["messages"] == []
    assert FULL not in [url for step in trace for url in step["reads"]]


def test_no_message_and_no_work_item_say_so() -> None:
    trace = _view([_show(), _read([]), _read([]), _full([]), _press("Work queue")])
    assert trace[3]["inbox"]["sentences"] == [NONE_YET]
    assert trace[-1]["inbox"]["sentences"] == ["No work items."]


def test_a_failed_full_read_says_so() -> None:
    failed = {"do": "answer", "url": FULL, "status": 503, "body": {}}
    last = _view([_show(), failed])[-1]
    assert last["inbox"]["sentences"] == [
        "The messages did not load: the server answered 503. Reload the page to try again."
    ]


def test_a_change_of_tab_clears_the_marks_and_back_marks_nothing() -> None:
    """7.3: the rows unread as the tab shows keep their mark until the tab changes; back on
    Messages with nothing new, no row is marked."""
    trace = _view(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, MSFT]),
            _show(),
            _read([QCOM, MSFT]),
            _full([MSFT, QCOM]),
            _press("Work queue"),
            _press("Messages"),
            _read([QCOM, MSFT]),
            _full([MSFT, QCOM]),
        ]
    )
    assert trace[2]["count"] == 1
    marked = trace[5]
    assert marked["count"] == 0 and marked["inbox"]["messages"] == [["MSFT", True], ["QCOM", False]]
    assert marked["inbox"]["tabs"][0] == ["Messages", "true"]
    queue = trace[6]
    assert queue["hash"] == "#inbox/queue" and queue["unreadMarks"] == []
    assert FULL not in queue["reads"]
    back = trace[-1]
    assert back["hash"] == "#inbox" and back["unreadMarks"] == []
    assert back["inbox"]["messages"] == [["MSFT", False], ["QCOM", False]]


def test_leaving_the_inbox_clears_the_marks() -> None:
    trace = _view(
        [_read([QCOM]), TICK, _read([QCOM, MSFT]), _show(), {"do": "show", "view": "screen"}]
    )
    assert trace[3]["unreadMarks"] == [2]
    assert trace[-1]["unreadMarks"] == []


def test_a_decline_that_lands_after_the_view_is_left_sees_nothing() -> None:
    """7.3: the owner declines an item on the Work queue, turns to Messages and leaves the Inbox
    before the decline lands; the view's read after it, made while the view is hidden, neither
    watches nor reads the messages, so a later message is counted, not seen."""
    declined = CLAIMED | {"state": "declined", "reason": "no", "declinedBy": "owner"}
    trace = _view(
        [
            _read([QCOM]),
            _show("queue"),
            _read([QCOM, CLAIMED]),
            _press("Decline"),
            {"do": "inboxField", "name": "Reason for declining AMD", "value": "no"},
            {"do": "inboxSubmit"},
            _press("Messages"),
            {"do": "show", "view": "screen"},
            {"do": "answer", "url": "/api/inbox/3", "status": 200, "body": declined},
            _read([QCOM, declined]),
            _read([QCOM, declined]),
            TICK,
            _read([QCOM, declined, MSFT]),
        ]
    )
    assert trace[5]["reads"] == ["/api/inbox/3"]
    assert trace[6]["hash"] == "#inbox" and trace[7]["hash"] == ""
    assert [url for step in trace[7:] for url in step["reads"]].count(FULL) == 0
    assert trace[-1]["local"]["seen"] == [1]
    assert trace[-1]["count"] == 1 and trace[-1]["unreadMarks"] == []


def test_a_message_that_arrives_while_the_tab_shows_is_read_and_marked() -> None:
    """7.2: the cheap read shows a message the tab does not show: the full read is asked for again,
    and the row is drawn marked."""
    trace = _view(
        [_show(), _read([QCOM]), _read([QCOM]), _full([QCOM]), TICK, _read([QCOM, MSFT])]
        + [_full([MSFT, QCOM])]
    )
    assert FULL not in trace[4]["reads"]
    assert trace[5]["reads"] == [FULL]
    assert trace[-1]["inbox"]["messages"] == [["MSFT", True], ["QCOM", False]]
    assert trace[-1]["count"] == 0


def test_a_read_with_nothing_new_asks_for_no_full_read() -> None:
    trace = _view([_show(), _read([QCOM]), _read([QCOM]), _full([QCOM]), TICK, _read([QCOM])])
    assert FULL not in trace[-1]["reads"]


def test_back_and_forward_between_the_tabs() -> None:
    trace = _view(
        [
            {"do": "hash", "hash": "#inbox/queue"},
            {"do": "hash", "hash": "#inbox"},
            {"do": "hash", "hash": "#inbox/queue"},
        ]
    )
    assert [t["hash"] for t in trace] == ["#inbox/queue", "#inbox", "#inbox/queue"]
    assert [t["inbox"]["panel"] for t in trace] == [
        "inbox-tab-queue",
        "inbox-tab-messages",
        "inbox-tab-queue",
    ]
    assert [FULL in t["reads"] for t in trace] == [False, True, False]


@pytest.mark.parametrize(
    ("permission", "secure", "line"),
    [
        (None, True, CANNOT),
        ("granted", False, CANNOT),
        ("default", True, OFF + " Turn on notifications"),
        ("denied", True, BLOCKED),
        ("granted", True, None),
    ],
)
def test_the_line_by_the_browser_s_permission(
    permission: str | None, secure: bool, line: str | None
) -> None:
    last = _view([_show()], notification=permission, secure=secure)[-1]
    assert last["inbox"]["line"] == line
    assert last["asks"] == 0


@pytest.mark.parametrize(
    ("grant", "line"),
    [("granted", None), ("denied", BLOCKED), ("default", OFF + " Turn on notifications")],
)
def test_turn_on_notifications_asks_and_the_line_follows(grant: str, line: str | None) -> None:
    """7.6: the press, and nothing else, asks the browser; a grant shows the test notification
    and the line goes; a refusal draws its own line."""
    trace = _view(
        [_show(), _read([QCOM]), _press("Turn on notifications", grant=grant)],
        notification="default",
    )
    assert [t["asks"] for t in trace] == [0, 0, 1]
    assert trace[-1]["inbox"]["line"] == line
    assert [n["tag"] for n in trace[-1]["notices"]] == (
        ["fairband-test"] if grant == "granted" else []
    )


def test_the_tab_counts_follow_the_reads() -> None:
    """7.4: Messages carries the unread messages, Work queue the open items, pending and claimed;
    neither a number at none."""
    trace = _view(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, MSFT, CLAIMED]),
            _show("queue"),
            _read([QCOM, MSFT, CLAIMED]),
        ]
    )
    assert trace[-1]["inbox"]["tabs"] == [["Messages 1", "false"], ["Work queue 1", "true"]]
