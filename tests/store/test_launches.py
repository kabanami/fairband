"""The launch record: a window opened from the research button, its states and moves, when it is
overdue, the one launch in flight for an item, and the launches a stopped server left opening
(spec 2026-11-16, section 8)."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fairband.store.db import transaction
from fairband.store.inbox import post_item
from fairband.store.launches import (
    CLAIM_WAIT_S,
    STOPPED,
    InFlight,
    LaunchRow,
    State,
    WrongMove,
    fail_opening,
    insert_launch,
    launch,
    move_launch,
    newest_launch,
    opened,
    overdue,
)
from fairband.store.ledger import OWNER

NOW = datetime(2026, 11, 16, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(seconds=5)
STATES: list[State] = ["opening", "opened", "started", "ended", "failed"]
ALLOWED: list[tuple[State, State]] = [
    ("opening", "opened"),
    ("opening", "started"),
    ("opening", "failed"),
    ("opened", "started"),
    ("opened", "failed"),
    ("started", "ended"),
]
REFUSED = [(a, b) for a in STATES for b in STATES if (a, b) not in ALLOWED]


def _item(conn: sqlite3.Connection, symbol: str = "AAPL") -> int:
    """A pending work item for ``symbol``; its id."""
    return post_item(conn, symbol, "full report", "", None, "owner", OWNER, NOW)


def _launch_in(conn: sqlite3.Connection, state: State, item_id: int | None = None) -> int:
    """A launch made at ``NOW`` and moved at ``NOW`` along the way to ``state``; its id."""
    launch_id = insert_launch(conn, item_id, "claude", NOW).id
    path: dict[State, list[State]] = {
        "opening": [],
        "opened": ["opened"],
        "started": ["started"],
        "ended": ["started", "ended"],
        "failed": ["failed"],
    }
    for to in path[state]:
        stage = "window" if to == "failed" else None
        move_launch(conn, launch_id, to, NOW, stage=stage)
    return launch_id


def _count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM launches").fetchone()[0])


def test_the_constants() -> None:
    assert CLAIM_WAIT_S == 90
    assert STOPPED == "the server stopped while the window command ran"
    assert issubclass(WrongMove, ValueError) and issubclass(InFlight, ValueError)


def test_insert_launch_opens_a_launch_for_an_item(conn: sqlite3.Connection) -> None:
    item_id = _item(conn)

    row = insert_launch(conn, item_id, "claude", NOW)

    assert not conn.in_transaction
    assert row == LaunchRow(
        id=1,
        item_id=item_id,
        agent="claude",
        state="opening",
        stage=None,
        detail=None,
        exit_code=None,
        created_at=NOW,
        updated_at=NOW,
    )
    assert launch(conn, row.id) == row


def test_insert_launch_opens_a_test_with_no_item(conn: sqlite3.Connection) -> None:
    row = insert_launch(conn, None, "claude", NOW)

    assert (row.item_id, row.state) == (None, "opening")
    assert launch(conn, row.id) == row


def test_insert_launch_joins_the_callers_transaction(conn: sqlite3.Connection) -> None:
    """The route checks the item, checks for a launch in flight and inserts in one transaction;
    the insert commits or rolls back with it."""
    item_id = _item(conn)
    with pytest.raises(RuntimeError), transaction(conn, immediate=True):
        insert_launch(conn, item_id, "claude", NOW)
        assert conn.in_transaction
        raise RuntimeError("the caller's check failed")

    assert _count(conn) == 0


def test_no_such_launch_is_a_key_error(conn: sqlite3.Connection) -> None:
    with pytest.raises(KeyError) as read:
        launch(conn, 99)
    with pytest.raises(KeyError) as move:
        move_launch(conn, 99, "started", NOW)
    with pytest.raises(KeyError) as window:
        opened(conn, 99, NOW)

    assert read.value.args == move.value.args == window.value.args == (99,)


@pytest.mark.parametrize(("start", "to"), ALLOWED)
def test_each_allowed_move(conn: sqlite3.Connection, start: State, to: State) -> None:
    launch_id = _launch_in(conn, start, _item(conn))

    stage = "agent" if to == "failed" else None
    row = move_launch(conn, launch_id, to, LATER, stage=stage)

    assert not conn.in_transaction
    assert (row.state, row.created_at, row.updated_at) == (to, NOW, LATER)
    assert launch(conn, launch_id) == row


@pytest.mark.parametrize(("start", "to"), REFUSED)
def test_each_refused_move(conn: sqlite3.Connection, start: State, to: State) -> None:
    launch_id = _launch_in(conn, start, _item(conn))
    before = launch(conn, launch_id)

    stage = "agent" if to == "failed" else None
    with pytest.raises(WrongMove) as refused:
        move_launch(conn, launch_id, to, LATER, stage=stage, detail="a reason", exit_code=1)

    assert str(refused.value) == f"a launch that is {start} does not become {to}"
    assert launch(conn, launch_id) == before
    assert not conn.in_transaction


def test_a_failure_keeps_its_stage_and_sentence(conn: sqlite3.Connection) -> None:
    launch_id = _launch_in(conn, "opened", _item(conn))
    sentence = "`claude` was not found on the path of a login shell"

    row = move_launch(conn, launch_id, "failed", LATER, stage="agent", detail=sentence)

    assert (row.state, row.stage, row.detail, row.exit_code) == ("failed", "agent", sentence, None)


def test_an_end_keeps_its_exit_code(conn: sqlite3.Connection) -> None:
    launch_id = _launch_in(conn, "started", _item(conn))

    row = move_launch(conn, launch_id, "ended", LATER, exit_code=130)

    assert (row.state, row.stage, row.detail, row.exit_code) == ("ended", None, None, 130)


def test_a_failure_without_a_stage_is_refused(conn: sqlite3.Connection) -> None:
    launch_id = _launch_in(conn, "opening", _item(conn))
    before = launch(conn, launch_id)

    with pytest.raises(ValueError, match="^a failed launch names its stage$"):
        move_launch(conn, launch_id, "failed", LATER, detail="a reason")

    assert launch(conn, launch_id) == before


def test_opened_moves_an_opening_launch(conn: sqlite3.Connection) -> None:
    launch_id = _launch_in(conn, "opening", _item(conn))

    row = opened(conn, launch_id, LATER)

    assert not conn.in_transaction
    assert (row.state, row.updated_at) == ("opened", LATER)
    assert launch(conn, launch_id) == row


@pytest.mark.parametrize("state", ["opened", "started", "ended", "failed"])
def test_opened_leaves_a_launch_the_launcher_moved_on(
    conn: sqlite3.Connection, state: State
) -> None:
    """The window command can end with exit 0 after the launcher has reported: the state stays as
    the launcher left it, and the row is answered as it is."""
    launch_id = _launch_in(conn, state, _item(conn))
    before = launch(conn, launch_id)

    assert opened(conn, launch_id, LATER) == before
    assert launch(conn, launch_id) == before


def test_a_started_launch_outlives_a_restart(conn: sqlite3.Connection) -> None:
    """A server that stops while Claude Code runs leaves the launch started; the app's start
    fails only what is opening, and the launcher's end is still taken."""
    launch_id = _launch_in(conn, "started", _item(conn))

    assert fail_opening(conn, LATER) == 0
    assert launch(conn, launch_id).state == "started"

    row = move_launch(conn, launch_id, "ended", LATER, exit_code=0)
    assert (row.state, row.exit_code) == ("ended", 0)


@pytest.mark.parametrize("state", ["opened", "started"])
def test_an_items_launch_is_overdue_at_90_seconds(conn: sqlite3.Connection, state: State) -> None:
    row = launch(conn, _launch_in(conn, state, _item(conn)))

    assert not overdue(row, "pending", NOW + timedelta(seconds=89))
    assert overdue(row, "pending", NOW + timedelta(seconds=90))
    assert overdue(row, "pending", NOW + timedelta(hours=2))


@pytest.mark.parametrize("item_state", ["claimed", "done", "declined", "dropped"])
@pytest.mark.parametrize("state", ["opened", "started"])
def test_a_launch_is_never_overdue_once_its_item_left_pending(
    conn: sqlite3.Connection, state: State, item_state: str
) -> None:
    row = launch(conn, _launch_in(conn, state, _item(conn)))

    assert not overdue(row, item_state, NOW + timedelta(seconds=90))
    assert not overdue(row, item_state, NOW + timedelta(hours=2))


@pytest.mark.parametrize("state", ["opening", "ended", "failed"])
def test_an_opening_ended_or_failed_launch_is_never_overdue(
    conn: sqlite3.Connection, state: State
) -> None:
    row = launch(conn, _launch_in(conn, state, _item(conn)))

    assert not overdue(row, "pending", NOW + timedelta(hours=2))


def test_a_test_is_overdue_while_opened_and_never_once_started(conn: sqlite3.Connection) -> None:
    waiting = launch(conn, _launch_in(conn, "opened"))
    started = launch(conn, _launch_in(conn, "started"))

    assert not overdue(waiting, None, NOW + timedelta(seconds=89))
    assert overdue(waiting, None, NOW + timedelta(seconds=90))
    assert not overdue(started, None, NOW + timedelta(seconds=90))
    assert not overdue(started, None, NOW + timedelta(hours=2))


@pytest.mark.parametrize("state", ["opening", "opened", "started"])
def test_a_second_launch_is_refused_while_one_is_in_flight(
    conn: sqlite3.Connection, state: State
) -> None:
    item_id = _item(conn)
    _launch_in(conn, state, item_id)

    with pytest.raises(InFlight) as refused:
        insert_launch(conn, item_id, "claude", NOW + timedelta(seconds=20, milliseconds=700))

    assert str(refused.value) == "a window for this request opened 20 seconds ago"
    assert _count(conn) == 1
    assert not conn.in_transaction


def test_a_launch_left_opening_blocks_until_the_start_fails_it(conn: sqlite3.Connection) -> None:
    """An opening launch is never overdue, so it holds its item until ``fail_opening`` runs."""
    item_id = _item(conn)
    first = _launch_in(conn, "opening", item_id)

    with pytest.raises(InFlight, match="^a window for this request opened 3600 seconds ago$"):
        insert_launch(conn, item_id, "claude", NOW + timedelta(hours=1))
    fail_opening(conn, NOW + timedelta(hours=1))

    second = insert_launch(conn, item_id, "claude", NOW + timedelta(hours=1))
    assert (launch(conn, first).state, second.state) == ("failed", "opening")


@pytest.mark.parametrize(
    ("state", "after"),
    [
        ("failed", timedelta(seconds=1)),
        ("ended", timedelta(seconds=1)),
        ("opened", timedelta(seconds=90)),
        ("started", timedelta(seconds=90)),
    ],
)
def test_a_second_launch_is_taken_after_a_failure_an_end_or_an_overdue_launch(
    conn: sqlite3.Connection, state: State, after: timedelta
) -> None:
    item_id = _item(conn)
    _launch_in(conn, state, item_id)

    row = insert_launch(conn, item_id, "claude", NOW + after)

    assert (row.id, row.item_id, row.state, row.created_at) == (2, item_id, "opening", NOW + after)
    assert newest_launch(conn, item_id) == row


def test_a_test_never_blocks_nor_is_blocked(conn: sqlite3.Connection) -> None:
    """A test has no item: it is never refused, and it holds no item's launch."""
    item_id = _item(conn)
    first_test = insert_launch(conn, None, "claude", NOW)
    second_test = insert_launch(conn, None, "claude", NOW)
    for_item = insert_launch(conn, item_id, "claude", NOW)
    third_test = insert_launch(conn, None, "claude", NOW)

    assert [first_test.id, second_test.id, for_item.id, third_test.id] == [1, 2, 3, 4]
    assert all(r.state == "opening" for r in (first_test, second_test, for_item, third_test))


def test_one_items_launch_does_not_block_another_item(conn: sqlite3.Connection) -> None:
    first = insert_launch(conn, _item(conn, "AAPL"), "claude", NOW)
    second = insert_launch(conn, _item(conn, "MSFT"), "claude", NOW)

    assert (first.state, second.state) == ("opening", "opening")


def test_newest_launch_is_the_items_highest_id(conn: sqlite3.Connection) -> None:
    aapl, msft = _item(conn, "AAPL"), _item(conn, "MSFT")
    assert newest_launch(conn, aapl) is None

    _launch_in(conn, "failed", aapl)
    newest = launch(conn, _launch_in(conn, "ended", aapl))
    _launch_in(conn, "opening", msft)
    _launch_in(conn, "opening")

    assert newest_launch(conn, aapl) == newest
    assert newest_launch(conn, msft) == launch(conn, 3)


def test_fail_opening_fails_every_opening_launch_and_answers_the_count(
    conn: sqlite3.Connection,
) -> None:
    """A test in each state, and an item's launch left opening."""
    ids = {state: _launch_in(conn, state) for state in STATES}
    for_item = _launch_in(conn, "opening", _item(conn))
    others = {state: launch(conn, ids[state]) for state in STATES if state != "opening"}

    assert fail_opening(conn, LATER) == 2

    assert not conn.in_transaction
    for launch_id in (ids["opening"], for_item):
        row = launch(conn, launch_id)
        assert (row.state, row.stage, row.detail, row.exit_code) == (
            "failed",
            "window",
            STOPPED,
            None,
        )
        assert (row.created_at, row.updated_at) == (NOW, LATER)
    assert {state: launch(conn, ids[state]) for state in others} == others
    assert fail_opening(conn, LATER + timedelta(seconds=1)) == 0
