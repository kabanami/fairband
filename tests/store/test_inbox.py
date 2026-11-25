"""The work inbox: its items' states (spec 2026-11-06 Tier 2, section 8), and no item Fairband posts
itself (spec 2026-11-25 owner's inbox, 8), on a database where AAPL and MSFT are valued into 2027
and both are on the list Core."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from inspect import signature

import pytest

from fairband.engine.route import refusal_result
from fairband.policy import load_policy
from fairband.store.inbox import (
    ItemOpen,
    WorkItem,
    WrongState,
    claim_item,
    complete_item,
    decline_item,
    oldest_pending,
    open_item,
    post_item,
    work_item,
    work_items,
)
from fairband.store.ledger import OWNER, Writer
from fairband.store.snapshots import insert_snapshot
from fairband.store.watchlists import add_symbol, create_watchlist

NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
VALID = date(2027, 1, 1)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")


@pytest.fixture
def core(conn: sqlite3.Connection, new_refresh: Callable[[], int]) -> int:
    """The list Core, holding AAPL (snapshot 1) and MSFT (snapshot 2), both valid into 2027."""
    refresh_id = new_refresh()
    for symbol in ("AAPL", "MSFT"):
        _value(conn, refresh_id, symbol, VALID)
    core = create_watchlist(conn, "Core", NOW)
    add_symbol(conn, core, "AAPL", NOW)
    add_symbol(conn, core, "MSFT", NOW)
    return core


def _value(conn: sqlite3.Connection, refresh_id: int, symbol: str, valid_until: date) -> int:
    """A newer snapshot of ``symbol``, valid until ``valid_until``; its id."""
    result = refusal_result(symbol, "a test row", load_policy(), date(2026, 9, 1))
    return insert_snapshot(
        conn, replace(result, valid_until=valid_until), refresh_id, clock=lambda: NOW
    )


def test_post_claim_complete(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "AAPL", "full report", "why", 1, "owner", OWNER, NOW)
    assert not conn.in_transaction
    assert work_item(conn, item_id) == WorkItem(
        id=item_id,
        symbol="AAPL",
        mode="full report",
        note="why",
        snapshot_id=1,
        origin="owner",
        posted_by="owner",
        posted_actor=None,
        posted_client=None,
        posted_at=NOW,
        state="pending",
        claimed_by=None,
        claimed_at=None,
        report_id=None,
        reason=None,
        finished_at=None,
        expiry_valid_until=None,
    )
    claimed = claim_item(conn, item_id, "claude-opus-5-5", NOW)
    assert (claimed.state, claimed.claimed_by, claimed.claimed_at) == (
        "claimed",
        "claude-opus-5-5",
        NOW,
    )
    done = complete_item(conn, item_id, 7, LATER)
    assert (done.state, done.report_id, done.finished_at) == ("done", 7, LATER)
    assert done.claimed_by == "claude-opus-5-5"
    with pytest.raises(ValueError, match="^work item 1 is done$"):
        claim_item(conn, item_id, "gpt-5", NOW)
    with pytest.raises(WrongState, match="^work item 1 is done$"):
        complete_item(conn, item_id, 8, NOW)
    assert work_item(conn, item_id) == done


def test_an_agent_post_carries_its_actor_and_client(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "aapl", "valuation review", "", None, "agent", AGENT, NOW)
    item = work_item(conn, item_id)
    assert (item.symbol, item.note, item.snapshot_id, item.origin) == ("AAPL", "", None, "agent")
    assert (item.posted_by, item.posted_actor, item.posted_client) == (
        "agent",
        "claude-opus-5-5",
        "claude-code/2.1",
    )


def test_a_claim_can_be_taken_over_by_name(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    claim_item(conn, item_id, "claude-opus-5-5", NOW)
    taken = claim_item(conn, item_id, "gpt-5", LATER)
    assert (taken.state, taken.claimed_by, taken.claimed_at) == ("claimed", "gpt-5", LATER)


def test_oldest_pending_and_open_item(conn: sqlite3.Connection, core: int) -> None:
    assert oldest_pending(conn) is None and open_item(conn, "AAPL") is None
    first = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    second = post_item(conn, "MSFT", "valuation review", "", 2, "owner", OWNER, LATER)
    assert oldest_pending(conn) == work_item(conn, first)
    claim_item(conn, first, "claude-opus-5-5", LATER)
    assert oldest_pending(conn) == work_item(conn, second)
    assert open_item(conn, "AAPL") == work_item(conn, first)  # claimed is open
    complete_item(conn, first, 7, LATER)
    assert open_item(conn, "AAPL") is None
    assert [i.id for i in work_items(conn)] == [second, first]  # newest first
    assert [i.id for i in work_items(conn, "done")] == [first]
    assert [i.id for i in work_items(conn, "pending")] == [second]


def test_a_symbol_has_one_open_item(conn: sqlite3.Connection, core: int) -> None:
    first = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    with pytest.raises(ItemOpen, match="^an item for AAPL is open$"):
        post_item(conn, "AAPL", "valuation review", "", 1, "agent", AGENT, NOW)
    assert issubclass(ItemOpen, ValueError) and issubclass(WrongState, ValueError)
    assert [i.id for i in work_items(conn)] == [first]
    decline_item(conn, first, "covered last week", NOW)
    second = post_item(conn, "AAPL", "valuation review", "", 1, "agent", AGENT, NOW)
    assert open_item(conn, "AAPL") == work_item(conn, second)


def test_decline_needs_a_reason(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    for reason in ("", "   "):
        with pytest.raises(ValueError, match="^a decline needs a reason$"):
            decline_item(conn, item_id, reason, NOW)
    assert work_item(conn, item_id).state == "pending"
    declined = decline_item(conn, item_id, "no filings since the last report", LATER)
    assert (declined.state, declined.reason, declined.finished_at) == (
        "declined",
        "no filings since the last report",
        LATER,
    )
    with pytest.raises(WrongState, match="^work item 1 is declined$"):
        decline_item(conn, item_id, "again", NOW)
    with pytest.raises(WrongState, match="^work item 1 is declined$"):
        complete_item(conn, item_id, 7, NOW)


def test_a_missing_item_and_a_bad_mode(conn: sqlite3.Connection, core: int) -> None:
    with pytest.raises(KeyError):
        claim_item(conn, 99, "claude-opus-5-5", NOW)
    with pytest.raises(KeyError):
        work_item(conn, 99)
    with pytest.raises(ValueError, match="^a mode is valuation review or full report$"):
        post_item(conn, "AAPL", "memo", "", 1, "owner", OWNER, NOW)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="^'bad symbol' is not a symbol$"):
        post_item(conn, "bad symbol", "full report", "", None, "owner", OWNER, NOW)


def test_fairband_posts_and_drops_no_item_itself() -> None:
    """Spec 2026-11-25 owner's inbox, 8: the expiry rule left, with the drop and the parameters
    by which the system's item named what it stood for."""
    from fairband.store import inbox

    assert not hasattr(inbox, "post_expiry_items")
    assert not hasattr(inbox, "drop_item")
    assert [p for p in signature(inbox.post_item).parameters if p.startswith("expiry")] == []


def test_a_stored_expiry_item_and_a_dropped_one_still_read(conn: sqlite3.Connection) -> None:
    """Spec 2026-11-25 owner's inbox, 8: a row of origin ``expiry`` in the state ``dropped``,
    written before the rule left, reads as it was stored."""
    conn.execute(
        "INSERT INTO work_items (symbol, mode, note, origin, posted_by, posted_at, state,"
        " expiry_valid_until) VALUES ('AAPL', 'valuation review', 'expired 2026-11-01',"
        " 'expiry', 'system', '2026-11-02T00:00:00+00:00', 'dropped', '2026-11-01')"
    )
    [item] = work_items(conn)
    assert (item.origin, item.state) == ("expiry", "dropped")
    assert item.expiry_valid_until == date(2026, 11, 1)
