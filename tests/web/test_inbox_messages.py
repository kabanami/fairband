"""The owner's read of the messages (spec 2026-11-25 owner's inbox, 7.1 and 7.2), on the database of
``conftest.py``: AAPL valued on the Mature Growth route, AAL refused for its target margin and HGCO
valued on the revenue growth route, each with one snapshot, and a secondary valuation on each where
a test asks for them (``secondaries``). Items are posted and moved through the inbox routes; a
report is stored on the company's latest snapshot by the store, an agent its writer."""

from contextlib import closing
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.reports import AGENT
from support.web import HEADER, NOW

from fairband.engine.review import Review
from fairband.engine.types import ValuationResult
from fairband.store.db import connect
from fairband.store.inbox import Mode
from fairband.store.ledger import Writer
from fairband.store.reports import insert_report
from fairband.store.reviews import insert_review, review_row
from fairband.store.secondary import secondary_row
from fairband.store.snapshots import latest_snapshot, snapshot_row
from fairband.web.research_page import report_call

# The figures of a done message, as ``report_call`` answers them.
CALL = ("value", "basis", "note", "price", "priceDate", "validUntil", "refusal")
WRITER = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
SECTIONS = [{"heading": "Summary", "parts": ["Plain words."]}]


def _item(client: TestClient, symbol: str, mode: Mode = "full report") -> int:
    """The id of an item of ``symbol`` the owner posts."""
    r = client.post("/api/inbox", json={"symbol": symbol, "mode": mode}, headers=HEADER)
    assert r.status_code == 201, r.text
    item_id: int = r.json()["id"]
    return item_id


def _report(
    db_path: Path,
    symbol: str,
    mode: Mode = "full report",
    review_id: int | None = None,
    secondary_id: int | None = None,
) -> int:
    """The id of a hold of ``symbol`` stored on its latest snapshot by an agent."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, symbol)
        assert snapshot is not None
        return insert_report(
            conn,
            symbol,
            mode,
            "hold",
            SECTIONS,
            None,
            snapshot.id,
            review_id,
            secondary_id,
            None,
            WRITER,
            NOW,
        )


def _move(client: TestClient, item_id: int, body: dict[str, Any], headers: dict[str, str]) -> None:
    r = client.patch(f"/api/inbox/{item_id}", json=body, headers=headers)
    assert r.status_code == 200, r.text


def _complete(client: TestClient, item_id: int, report_id: int) -> None:
    """The agent completes the item with the report."""
    _move(client, item_id, {"action": "complete", "reportId": report_id}, AGENT)


def _decline(client: TestClient, item_id: int, reason: str, headers: dict[str, str]) -> None:
    _move(client, item_id, {"action": "decline", "reason": reason}, headers)


def _messages(client: TestClient) -> list[dict[str, Any]]:
    r = client.get("/api/inbox/messages")
    assert r.status_code == 200, r.text
    found: list[dict[str, Any]] = r.json()["messages"]
    return found


def _finished(db_path: Path, item_id: int, at: str) -> None:
    """Set the item's finish time to ``at`` by SQL."""
    with closing(connect(db_path)) as conn, conn:
        conn.execute("UPDATE work_items SET finished_at = ? WHERE id = ?", (at, item_id))


@pytest.mark.parametrize("case", ["review", "secondary", "refused"])
def test_a_done_message_holds_the_report_s_call(
    client: TestClient,
    db_path: Path,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
    case: str,
) -> None:
    """A done message's figures are ``report_call``'s for its report's snapshot, review and
    secondary valuation, read here from the store: a report on AAPL's snapshot with a review; one
    on AAL's refused snapshot with its secondary valuation and no review; and one on AAL's with
    neither, whose call is the snapshot's refusal."""
    symbol = "AAPL" if case == "review" else "AAL"
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, symbol)
        assert snapshot is not None
        review = None
        if case == "review":
            mechanical = results["AAPL"]
            reviewed = Review(mechanical, mechanical.value, (), ())
            review_id = insert_review(conn, reviewed, "AAPL", snapshot.id, None, clock=lambda: NOW)
            review = review_row(conn, review_id)
            assert review is not None
        secondary = secondary_row(conn, secondaries["AAL"]) if case == "secondary" else None
    report_id = _report(
        db_path,
        symbol,
        review_id=None if review is None else review.id,
        secondary_id=None if secondary is None else secondary.id,
    )
    item_id = _item(client, symbol)
    _complete(client, item_id, report_id)

    [message] = client.get("/api/inbox/messages").json()["messages"]
    expected = report_call(snapshot, review, secondary)
    assert (expected["basis"], expected["refusal"] is None) == {
        "review": ("reviewed", True),
        "secondary": ("reviewed", True),
        "refused": (None, False),
    }[case]
    assert {k: message[k] for k in CALL} == {k: expected[k] for k in CALL}
    assert (message["kind"], message["stance"], message["reportRevision"]) == ("done", "hold", 1)
    assert message["by"] == {"principal": "agent", "actor": "claude-opus-5-5"}
    assert {k: message[k] for k in ("itemId", "symbol", "mode", "at", "reportId")} == {
        "itemId": item_id,
        "symbol": symbol,
        "mode": "full report",
        "at": NOW.isoformat(),
        "reportId": report_id,
    }
    assert len(message) == 16  # the six of both kinds, a done one's three and its call's seven


def test_the_report_s_mode_names_a_done_message(client: TestClient, db_path: Path) -> None:
    """Nothing checks that a report's mode is its item's: the message says what was made."""
    item_id = _item(client, "AAPL", "full report")
    _complete(client, item_id, _report(db_path, "AAPL", "valuation review"))
    assert client.get("/api/inbox/messages").json()["messages"][0]["mode"] == "valuation review"


def test_an_agent_s_decline_gives_a_message_and_the_owner_s_none(client: TestClient) -> None:
    """An agent's decline gives a message, its reason as written and the item's mode; the owner
    declined the other himself."""
    _decline(client, _item(client, "AAPL"), "covered last week", HEADER)
    aal = _item(client, "AAL", "valuation review")
    _decline(client, aal, "no filing yet", AGENT)
    [message] = client.get("/api/inbox/messages").json()["messages"]
    assert (message["symbol"], message["kind"], message["reason"]) == (
        "AAL",
        "declined",
        "no filing yet",
    )
    assert message["by"] == {"principal": "agent", "actor": "claude-opus-5-5"}
    assert message == {
        "itemId": aal,
        "symbol": "AAL",
        "kind": "declined",
        "mode": "valuation review",
        "at": NOW.isoformat(),
        "by": message["by"],
        "reason": "no filing yet",
    }


def test_the_messages_come_newest_first(client: TestClient, db_path: Path) -> None:
    """By the item's finish time, the newest first, then by its id, the highest first: item 2
    ended last, and items 3 and 1 at one moment before it."""
    aapl = _item(client, "AAPL")
    _complete(client, aapl, _report(db_path, "AAPL"))
    aal = _item(client, "AAL")
    _decline(client, aal, "no filing yet", AGENT)
    hgco = _item(client, "HGCO")
    _decline(client, hgco, "no filing yet", AGENT)
    assert (aapl, aal, hgco) == (1, 2, 3)
    earlier = (NOW - timedelta(hours=2)).isoformat()
    _finished(db_path, aapl, earlier)
    _finished(db_path, hgco, earlier)
    messages = _messages(client)
    assert [m["itemId"] for m in messages] == [2, 3, 1]
    assert [m["at"] for m in messages] == [NOW.isoformat(), earlier, earlier]


def test_the_messages_are_the_owner_s(client: TestClient) -> None:
    """A request with an agent's identity headers is refused, as the launch routes refuse one."""
    answer = client.get("/api/inbox/messages", headers=AGENT)
    assert (answer.status_code, answer.json()["detail"]) == (403, "the messages are the owner's")
    assert _messages(client) == []  # a request with no principal header is the page's


@pytest.mark.parametrize("missing", ["report", "snapshot"])
def test_a_done_item_without_its_report_still_reads(
    client: TestClient, db_path: Path, missing: str
) -> None:
    """A done item whose report row is missing, or whose report's snapshot row is, still gives a
    message: the item's mode, no author and no figures. Here the item's report id, or the report's
    snapshot id, is set by SQL to name no row."""
    item_id = _item(client, "AAPL", "valuation review")
    report_id = _report(db_path, "AAPL", "full report")
    _complete(client, item_id, report_id)
    with closing(connect(db_path)) as conn, conn:
        if missing == "report":
            conn.execute("UPDATE work_items SET report_id = 999 WHERE id = ?", (item_id,))
        else:
            conn.execute("UPDATE reports SET snapshot_id = 999 WHERE id = ?", (report_id,))
        assert snapshot_row(conn, 999) is None
    [message] = client.get("/api/inbox/messages").json()["messages"]
    assert message["by"] == {"principal": None, "actor": None}
    assert all(message[k] is None for k in (*CALL, "stance", "reportRevision"))
    assert (message["kind"], message["mode"], message["reportId"]) == (
        "done",
        "valuation review",
        999 if missing == "report" else report_id,
    )
