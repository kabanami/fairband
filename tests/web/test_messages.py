"""The owner's messages in the page (spec 2026-11-25 owner's inbox, 7.1, 7.3, 7.5, 7.6 and 7.7):
which work items give a message; the two lists the browser keeps, of the messages the owner saw
and of those a notification was handled for, each of work item ids; the header's count of the
unread messages; the inbox read while the page is hidden; and the browser's system notification
of a new message, its words, its tag and where a click on it leads. ``messages.js`` keeps them
on the page (``FairbandPage.messages``). Its helpers run in node (``support.page``), and the
header with it (``tests/web/header.mjs``) on steps the test gives, the tests reading the trace.
No first read and no later grant brings a mark or a notification for a message already on file,
and no message is notified twice."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support.page import BUNDLE, NODE, STATIC, node

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

DRIVER = Path(__file__).parent / "header.mjs"
MESSAGES = STATIC / "messages.js"
INBOX, FULL = "/api/inbox", "/api/inbox/messages"
SEEN, NOTIFIED = "fairband.inbox.seen", "fairband.inbox.notified"
AGENT = "claude-opus-5-5"
REASON = "The company files no annual report in English."
# The call of a done message, as the Research tab's value card answers it: a reviewed value.
CALL: dict[str, Any] = {
    "stance": "hold",
    "value": 210.87,
    "basis": "reviewed",
    "note": None,
    "price": 173.19,
    "priceDate": "2026-11-07",
    "validUntil": "2027-02-03",
    "refusal": None,
}
BODY = "Hold. Value $210.87 against a price of $173.19 on 7 Nov 2026. Valid until 3 Feb 2027."


def _item(item_id: int, symbol: str, state: str, at: str | None, **fields: Any) -> dict[str, Any]:
    """A work item as the inbox's cheap read answers it (``GET /api/inbox``)."""
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
        "claimedBy": None if state == "pending" else AGENT,
        "reportId": None,
        "reportRevision": None,
        "reason": None,
        "finishedAt": at,
        "declinedBy": None,
        "launch": None,
    } | fields


def _done(item_id: int, symbol: str, at: str) -> dict[str, Any]:
    """A done item of the cheap read, completed with the report ``item_id + 100``."""
    return _item(item_id, symbol, "done", at, reportId=item_id + 100, reportRevision=1)


def _declined(item_id: int, symbol: str, at: str, by: str) -> dict[str, Any]:
    """An item of the cheap read declined by ``by``, the owner or an agent."""
    return _item(
        item_id, symbol, "declined", at, mode="valuation review", reason=REASON, declinedBy=by
    )


def _open(item_id: int, symbol: str) -> dict[str, Any]:
    """A pending item of the cheap read."""
    return _item(item_id, symbol, "pending", None)


def _full(item: dict[str, Any], **figures: Any) -> dict[str, Any]:
    """The message of ``item`` as the full read answers it (``GET /api/inbox/messages``): a done
    one with its report and ``CALL``'s figures, ``figures`` over them; a declined one with its
    reason."""
    head = {
        "itemId": item["id"],
        "symbol": item["symbol"],
        "kind": item["state"],
        "mode": item["mode"],
        "at": item["finishedAt"],
        "by": {"principal": "agent", "actor": AGENT},
    }
    if item["state"] == "declined":
        return head | {"reason": item["reason"]} | figures
    report = {"reportId": item["reportId"], "reportRevision": item["reportRevision"]}
    return head | report | CALL | figures


def _read(items: list[dict[str, Any]]) -> dict[str, Any]:
    """The oldest cheap read in flight answers ``items``."""
    body = {"launchReady": False, "items": items}
    return {"do": "answer", "url": INBOX, "status": 200, "body": body}


def _answer(url: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
    """The oldest full read in flight answers ``messages``."""
    return {"do": "answer", "url": url, "status": 200, "body": {"messages": messages}}


def _run(steps: list[dict[str, Any]], **given: Any) -> list[dict[str, Any]]:
    """The trace of ``steps`` on the page loaded with ``given``: its ``local`` storage, the
    ``notification`` permission, ``secure`` (``tests/web/header.mjs``)."""
    assert NODE is not None
    scripts = ("app.js", "finder.js", "messages.js", "controls.js")
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


QCOM = _done(1, "QCOM", "2026-11-08T17:56:00+00:00")
MSFT = _done(2, "MSFT", "2026-11-11T14:03:00+00:00")
TICK = {"do": "tick"}


def _watch(on: bool) -> dict[str, Any]:
    return {"do": "watch", "on": on}


def _visible(shown: bool) -> dict[str, Any]:
    return {"do": "visibility", "hidden": not shown}


# ----------------------------------------------------------------------- what gives a message


def test_which_items_give_a_message() -> None:
    """7.1: a done item, and an item an agent declined; not one the owner declined, nor an open
    one. The newest finish first."""
    items = [
        QCOM,
        _declined(3, "AMD", "2026-11-09T09:12:00+00:00", "agent"),
        _declined(4, "AAL", "2026-11-09T10:00:00+00:00", "owner"),
        _open(5, "V"),
    ]
    assert [i["id"] for i in node("messages.of", [items], MESSAGES)] == [3, 1]


# ------------------------------------------------------------------------------ the two lists


def test_a_first_read_marks_nothing_and_notifies_nothing() -> None:
    """7.3: the first read after the build, in a new browser or after its data was cleared,
    writes both lists with every message's id: nothing is unread and nothing notified."""
    last = _run([_read([QCOM, MSFT])], notification="granted")[-1]
    assert (last["count"], last["notices"]) == (0, [])
    assert last["local"] == {"seen": [1, 2], "notified": [1, 2]}
    assert FULL not in last["reads"]


def test_a_store_with_no_message_marks_its_first() -> None:
    trace = _run(
        [_read([]), TICK, _read([QCOM]), _answer(FULL, [_full(QCOM)])], notification="granted"
    )
    assert trace[0]["local"] == {"seen": [], "notified": []}
    assert trace[-1]["count"] == 1
    assert [n["tag"] for n in trace[-1]["notices"]] == ["fairband-message-1"]


def test_a_new_message_counts_and_notifies_once() -> None:
    """7.6: the new id goes into ``notified`` before the full read is asked for, so the next read
    asks for none and notifies nothing; the message stays unread until the owner sees it."""
    steps = [
        _read([QCOM]),
        TICK,
        _read([QCOM, MSFT]),
        _answer(FULL, [_full(MSFT), _full(QCOM)]),
        TICK,
        _read([QCOM, MSFT]),
    ]
    trace = _run(steps, notification="granted")
    assert trace[2]["local"] == {"seen": [1], "notified": [1, 2]}
    assert trace[2]["reads"] == [FULL]
    assert trace[3]["notices"] == [
        {"title": "MSFT: full report done", "body": BODY, "tag": "fairband-message-2"}
    ]
    assert trace[-1]["notices"] == [] and trace[-1]["count"] == 1
    assert FULL not in trace[-1]["reads"]


def test_a_message_saved_late_is_still_new() -> None:
    """7.3: the lists hold ids, not a newest time, so an item that finished first but was saved
    after another is still notified and counted."""
    late = _done(7, "V", "2026-11-12T10:00:01+00:00")
    soon = _done(8, "MA", "2026-11-12T10:00:02+00:00")
    trace = _run(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, soon]),
            _answer(FULL, [_full(soon), _full(QCOM)]),
            TICK,
            _read([QCOM, soon, late]),
            _answer(FULL, [_full(soon), _full(late), _full(QCOM)]),
        ],
        notification="granted",
    )
    assert [n["tag"] for n in trace[-1]["notices"]] == ["fairband-message-7"]
    assert trace[-1]["count"] == 2


def test_a_reload_notifies_nothing_again_and_keeps_the_count() -> None:
    """A page loaded again finds the lists as the browser kept them."""
    kept = {SEEN: "[1]", NOTIFIED: "[1, 2]"}
    last = _run([_read([QCOM, MSFT])], local=kept, notification="granted")[-1]
    assert (last["notices"], last["count"]) == ([], 1)
    assert FULL not in last["reads"]


def test_a_message_another_tab_notified_is_not_notified_again() -> None:
    """Spec 4 and 7.6: another open tab that read the message first wrote ``notified``; this tab's
    read finds it there."""
    elsewhere = {"do": "elsewhere", "set": {NOTIFIED: "[1, 2]"}}
    last = _run([_read([QCOM]), TICK, elsewhere, _read([QCOM, MSFT])], notification="granted")[-1]
    assert (last["notices"], last["count"]) == ([], 1)
    assert FULL not in last["reads"]


@pytest.mark.parametrize("permission", ["default", "denied", None])
def test_no_permission_no_notification_and_the_list_still_moves(permission: str | None) -> None:
    """7.6: without the permission, or in a browser with no Notification, no notification and no
    full read; ``notified`` takes the id all the same, so a later grant brings nothing old."""
    last = _run([_read([QCOM]), TICK, _read([QCOM, MSFT])], notification=permission)[-1]
    assert (last["notices"], last["local"]["notified"], last["count"]) == ([], [1, 2], 1)
    assert FULL not in last["reads"]


def test_an_address_that_is_no_secure_context_notifies_nothing() -> None:
    """Spec 5: the Notification API needs a secure context."""
    last = _run([_read([QCOM]), TICK, _read([QCOM, MSFT])], notification="granted", secure=False)[
        -1
    ]
    assert (last["notices"], last["local"]["notified"], last["count"]) == ([], [1, 2], 1)
    assert FULL not in last["reads"]


def test_a_later_grant_brings_nothing_old() -> None:
    """Spec 4: a grant brings no burst of notifications for what arrived before it."""
    trace = _run(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, MSFT]),
            {"do": "ask", "grant": "granted"},
            TICK,
            _read([QCOM, MSFT]),
        ],
        notification="default",
    )
    assert [n["tag"] for n in trace[3]["notices"]] == ["fairband-test"]
    assert trace[-1]["notices"] == [] and FULL not in trace[-1]["reads"]


def test_more_than_three_give_one() -> None:
    """7.6: four new at one read give one notification in their place, which opens the Messages
    tab; it needs no figure, so the full read is not asked for."""
    new = [
        _done(item_id, f"N{item_id}", f"2026-11-12T10:0{item_id}:00+00:00") for item_id in (3, 4)
    ]
    new += [
        _declined(item_id, f"D{item_id}", "2026-11-12T11:00:00+00:00", "agent")
        for item_id in (5, 6)
    ]
    trace = _run(
        [_read([QCOM]), TICK, _read([QCOM, *new]), {"do": "click", "index": 0}],
        notification="granted",
    )
    assert trace[2]["notices"] == [
        {"title": "Fairband", "body": "4 new messages", "tag": "fairband-messages"}
    ]
    assert FULL not in trace[2]["reads"] and trace[2]["local"]["notified"] == [1, 3, 4, 5, 6]
    assert (trace[-1]["hash"], trace[-1]["windowFocused"]) == ("#inbox", True)


def test_three_new_give_three() -> None:
    new = [
        _done(item_id, f"N{item_id}", f"2026-11-12T10:0{item_id}:00+00:00") for item_id in (3, 4, 5)
    ]
    trace = _run(
        [_read([QCOM]), TICK, _read([QCOM, *new]), _answer(FULL, [_full(i) for i in new])],
        notification="granted",
    )
    assert sorted(n["tag"] for n in trace[-1]["notices"]) == [
        "fairband-message-3",
        "fairband-message-4",
        "fairband-message-5",
    ]


def test_a_failed_full_read_still_notifies_by_the_title() -> None:
    trace = _run(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, MSFT]),
            {"do": "answer", "url": FULL, "status": 503, "body": {}},
            {"do": "click", "index": 0},
        ],
        notification="granted",
    )
    assert trace[3]["notices"] == [
        {"title": "MSFT: full report done", "body": "", "tag": "fairband-message-2"}
    ]
    assert trace[-1]["hash"] == "#inbox"


def test_a_notification_that_throws_stops_nothing() -> None:
    trace = _run(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, MSFT]),
            _answer(FULL, [_full(MSFT), _full(QCOM)]),
            TICK,
            _read([QCOM, MSFT]),
        ],
        notification="throws",
    )
    assert trace[3]["notices"] == []
    assert trace[-1]["count"] == 1 and INBOX in trace[-2]["reads"]


@pytest.mark.parametrize("stored", ["null", '"3"', "{}", "not json", '[1, "2"]'])
def test_a_stored_value_that_is_no_list_reads_as_missing(stored: str) -> None:
    kept = {SEEN: stored, NOTIFIED: stored}
    last = _run([_read([QCOM])], local=kept, notification="granted")[-1]
    assert last["local"] == {"seen": [1], "notified": [1]} and last["count"] == 0
    assert last["notices"] == []


def test_storage_that_throws_keeps_the_lists_for_the_page_s_life() -> None:
    """7.3: where the browser refuses its storage, the lists live in memory by the same rules."""
    trace = _run(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, MSFT]),
            _answer(FULL, [_full(MSFT), _full(QCOM)]),
            TICK,
            _read([QCOM, MSFT]),
        ],
        local="throws",
        notification="granted",
    )
    assert trace[3]["count"] == 1 and len(trace[3]["notices"]) == 1
    assert trace[-1]["notices"] == [] and FULL not in trace[-1]["reads"]


# ------------------------------------------------------------------------ seen, and the marks


def test_the_owner_sees_the_messages_only_while_the_tab_shows() -> None:
    """7.3: a hidden browser tab left on Messages adds nothing to ``seen``; shown again, the read
    that lands adds every message's id."""
    hidden = [_read([QCOM]), _watch(True), _visible(False), TICK, _read([QCOM, MSFT])]
    trace = _run(hidden)
    assert trace[-1]["count"] == 1 and trace[-1]["local"]["seen"] == [1]
    back = _run(hidden + [_visible(True), _read([QCOM, MSFT])])[-1]
    assert back["count"] == 0 and back["local"]["seen"] == [1, 2]


def test_the_tab_shown_again_sees_the_messages_at_once() -> None:
    """7.3: the browser's tab coming back to the front over a read that already landed adds its
    ids to ``seen`` at once, before the read it asks for lands."""
    hidden = [_read([QCOM]), _watch(True), _visible(False), TICK, _read([QCOM, MSFT])]
    shown = _run(hidden + [_visible(True)])[-1]
    assert INBOX in shown["reads"]
    assert (shown["count"], shown["local"]["seen"], shown["unreadMarks"]) == (0, [1, 2], [2])


def test_a_tab_restored_hidden_sees_nothing() -> None:
    """7.3: a browser restores a tab at #inbox in the background, so the Messages tab shows
    (``watch(true)``) while the document is hidden: the owner has seen nothing, and ``seen`` and
    the count stay; shown again, the read that lands adds the message to ``seen``."""
    hidden = [_read([QCOM]), TICK, _read([QCOM, MSFT]), _watch(True)]
    trace = _run(hidden, hidden=True)
    assert (trace[2]["local"]["seen"], trace[2]["count"]) == ([1], 1)
    assert (trace[-1]["local"]["seen"], trace[-1]["count"]) == ([1], 1)
    assert trace[-1]["unreadMarks"] == []
    shown = _run(hidden + [_visible(True), _read([QCOM, MSFT])], hidden=True)[-1]
    assert (shown["local"]["seen"], shown["count"]) == ([1, 2], 0)
    assert shown["unreadMarks"] == [2]


def test_the_marks_stay_until_the_tab_changes() -> None:
    """7.3: the Messages tab shown over a read with an unread message: the count goes to none at
    once, and the row keeps its mark until the tab no longer shows."""
    trace = _run([_read([QCOM]), TICK, _read([QCOM, MSFT]), _watch(True), _watch(False)])
    assert (trace[2]["count"], trace[2]["unreadMarks"]) == (1, [])
    assert (trace[3]["count"], trace[3]["unreadMarks"]) == (0, [2])
    assert trace[3]["local"]["seen"] == [1, 2]
    assert (trace[4]["count"], trace[4]["unreadMarks"]) == (0, [])


def test_a_read_that_lands_while_the_tab_shows_marks_its_new_message() -> None:
    trace = _run([_read([QCOM]), _watch(True), TICK, _read([QCOM, MSFT])])
    assert (trace[-1]["count"], trace[-1]["unreadMarks"]) == (0, [2])
    assert trace[-1]["local"]["seen"] == [1, 2]


def test_another_tab_s_write_moves_the_count() -> None:
    trace = _run(
        [_read([QCOM]), TICK, _read([QCOM, MSFT]), {"do": "elsewhere", "set": {SEEN: "[1, 2]"}}]
    )
    assert (trace[2]["count"], trace[3]["count"]) == (1, 0)


# ----------------------------------------------------------------------- the read while hidden


def test_the_read_runs_while_the_page_is_hidden() -> None:
    """7.7: the 30-second cycle runs on while the page is hidden."""
    trace = _run([_read([QCOM]), _visible(False), TICK])
    assert INBOX in trace[-1]["reads"] and trace[-1]["waits"] == []


def test_a_page_loaded_hidden_reads_the_inbox() -> None:
    trace = _run([_read([QCOM]), TICK], hidden=True)
    assert trace[0]["local"] == {"seen": [1], "notified": [1]}
    assert trace[-1]["reads"] == [INBOX]


# ------------------------------------------------------------------- the permission and a click


def test_only_the_press_asks_and_a_grant_shows_the_test_notification() -> None:
    trace = _run(
        [_read([QCOM]), TICK, _read([QCOM]), {"do": "ask", "grant": "granted"}],
        notification="default",
    )
    assert [t["asks"] for t in trace] == [0, 0, 0, 1]
    assert trace[-1]["notices"] == [
        {"title": "Fairband", "body": "Notifications are on.", "tag": "fairband-test"}
    ]
    assert trace[-1]["askAnswer"] == "granted"


@pytest.mark.parametrize(("grant", "answer"), [("denied", "denied"), ("default", "default")])
def test_a_refused_ask_shows_nothing(grant: str, answer: str) -> None:
    last = _run([{"do": "ask", "grant": grant}], notification="default")[-1]
    assert (last["asks"], last["notices"], last["askAnswer"]) == (1, [], answer)


def test_an_ask_in_a_browser_with_no_notification_answers_none() -> None:
    last = _run([{"do": "ask", "grant": "granted"}])[-1]
    assert (last["asks"], last["notices"], last["askAnswer"]) == (0, [], "none")


def test_a_click_opens_the_report() -> None:
    """7.6: a click brings the Fairband tab to the front, opens the report on the Research tab
    and closes the notification."""
    trace = _run(
        [
            _read([QCOM]),
            TICK,
            _read([QCOM, MSFT]),
            _answer(FULL, [_full(MSFT, reportId=9), _full(QCOM)]),
            {"do": "click", "index": 0},
        ],
        notification="granted",
    )
    assert trace[-2]["closedNotices"] == []
    assert trace[-1]["hash"] == node("researchHref", ["MSFT", 9]) and trace[-1]["windowFocused"]
    assert trace[-1]["closedNotices"] == [0]


def test_the_permission_of_a_browser_with_no_notification() -> None:
    assert node("messages.permission", [], MESSAGES) == "none"


# ------------------------------------------------------------------------------ a notice's words


@pytest.mark.parametrize(
    ("message", "body"),
    [
        pytest.param(_full(QCOM), BODY, id="reviewed"),
        pytest.param(
            _full(QCOM, note="secondary valuation"),
            "Hold. Value $210.87 (reviewed, secondary valuation) against a price of $173.19 on "
            "7 Nov 2026. Valid until 3 Feb 2027.",
            id="secondary",
        ),
        pytest.param(
            _full(QCOM, stance="trim", value=95.1, basis="mechanical"),
            "Trim. Value $95.10 (mechanical) against a price of $173.19 on 7 Nov 2026. Valid "
            "until 3 Feb 2027.",
            id="mechanical",
        ),
        pytest.param(
            _full(
                QCOM, stance="trim", value=None, basis=None, refusal="no positive trailing earnings"
            ),
            "Trim. No value: no positive trailing earnings.",
            id="refused",
        ),
        pytest.param(_full(QCOM, reportRevision=None, **dict.fromkeys(CALL)), "", id="report-gone"),
        pytest.param(
            _full(_declined(3, "AMD", "2026-11-09T09:12:00+00:00", "agent")), REASON, id="declined"
        ),
    ],
)
def test_a_notice_s_words(message: dict[str, Any], body: str) -> None:
    assert node("messages.notice", [message], MESSAGES)["body"] == body


def test_a_notice_s_title_tag_and_link() -> None:
    """7.6: the title names the symbol and what ended; the tag is the message's own; the link is
    the report on the Research tab, or the Messages tab for a decline and for a done item with no
    report on file: none named, or one the full read finds no longer there (no revision)."""
    done = node("messages.notice", [_full(QCOM)], MESSAGES)
    assert done == {
        "title": "QCOM: full report done",
        "body": BODY,
        "tag": "fairband-message-1",
        "href": node("researchHref", ["QCOM", 101]),
    }
    declined = node(
        "messages.notice",
        [_full(_declined(3, "AMD", "2026-11-09T09:12:00+00:00", "agent"))],
        MESSAGES,
    )
    assert (declined["title"], declined["tag"], declined["href"]) == (
        "AMD: valuation review declined",
        "fairband-message-3",
        "#inbox",
    )
    unnamed = node("messages.notice", [_full(QCOM, reportId=None)], MESSAGES)
    gone = node("messages.notice", [_full(QCOM, reportRevision=None)], MESSAGES)
    assert (unnamed["href"], gone["href"]) == ("#inbox", "#inbox")
