"""The request button's launch as it runs (spec 2026-11-16 agent launch, 10): the real app.js in
node (``tests/web/following.mjs``), with a fetch that answers only when a step answers it and
timers that run only when a step fires them. Each test reads, after each step, what was fetched,
the timers set, how often ``after`` ran and what the lines under Request research read: a post
with Open Claude Code ticked, the following to the claim, the stops while a post is in flight,
the reads that fail, and a 409."""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support.page import BUNDLE, NODE, STATIC

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

DRIVER = Path(__file__).parent / "following.mjs"
AGENT = "claude-opus-5-5"
ITEM = 12
INBOX_POST = ["POST", "/api/inbox", {"symbol": "AAPL", "mode": "full report", "note": ""}]
LAUNCH_POST = ["POST", "/api/launches", {"itemId": ITEM}]
READ = ["GET", "/api/launches/7", None]
OPENING = "Requested · opening a window…"
STARTING = "Requested · the window opened, Claude Code is starting…"
STARTED = "Requested · Claude Code started, not claimed yet"
CLAIMED = f"Requested · claimed by {AGENT}"
TRYING = "The launch could not be read: Failed to fetch. Trying again."
RELOAD = "The launch could not be read: Failed to fetch. Reload the page."


def _drive(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The trace of ``steps``: one entry for each, as ``following.mjs`` gives it."""
    assert NODE is not None
    done = subprocess.run(
        [NODE, str(DRIVER), str(BUNDLE), str(STATIC / "app.js")],
        input=json.dumps(steps),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


def _launch(state: str, **changes: Any) -> dict[str, Any]:
    """Item 12's launch 7 as ``GET /api/launches/{id}`` answers it, made 5 seconds ago."""
    return {
        "id": 7,
        "itemId": ITEM,
        "test": False,
        "agent": "claude",
        "state": state,
        "stage": None,
        "detail": None,
        "exitCode": None,
        "createdAt": "2026-11-16T10:00:00+00:00",
        "updatedAt": "2026-11-16T10:00:00+00:00",
        "ageSeconds": 5,
        "overdue": False,
        "itemState": "pending",
        "claimedBy": None,
    } | changes


def _item(state: str = "pending", launch: dict[str, Any] | None = None) -> dict[str, Any]:
    """Item 12 as the company detail read gives it, with its newest launch."""
    return {
        "id": ITEM,
        "state": state,
        "mode": "full report",
        "claimedBy": AGENT if state == "claimed" else None,
        "createdAt": "2026-11-16T09:59:00+00:00",
        "launch": launch,
    }


def _answer(status: int, body: Any) -> dict[str, Any]:
    return {"do": "answer", "status": status, "body": body}


POST = {"do": "post"}
TICK = {"do": "tick"}
STOP = {"do": "stop"}
FAIL = {"do": "fail", "message": "Failed to fetch"}
ITEM_TAKEN = _answer(201, {"id": ITEM, "state": "pending"})


def _landed(launch: dict[str, Any] | None, state: str = "pending") -> dict[str, Any]:
    return {"do": "landed", "item": _item(state, launch)}


def _seen(entry: dict[str, Any], *names: str) -> tuple[Any, ...]:
    return tuple(entry[name] for name in names)


def test_a_post_with_the_box_ticked_opens_a_window_and_reads_it_every_2_seconds_to_the_claim() -> (
    None
):
    """The item's post, then the launch's post for its id, then ``after`` once; then one read
    2000 ms after each answer until the answer's item is claimed, then ``after`` once more and no
    further read."""
    claimed = _launch("started", itemState="claimed", claimedBy=AGENT)
    trace = _drive(
        [
            POST,
            ITEM_TAKEN,
            _answer(201, _launch("opened")),
            _landed(_launch("opened")),  # the company read `after` asked for
            TICK,
            _answer(200, _launch("started")),
            TICK,
            _answer(200, claimed),
            _landed(claimed, "claimed"),
        ]
    )
    post, taken, opened, landed, read, started, read_again, ended, last = trace
    assert post["fetched"] == [INBOX_POST]
    assert _seen(post, "afters", "timers", "line") == (0, [], None)
    assert taken["fetched"] == [LAUNCH_POST]
    assert _seen(taken, "afters", "timers", "line", "error") == (0, [], OPENING, None)
    assert _seen(opened, "fetched", "afters", "timers", "inFlight") == ([], 1, [2000], 0)
    assert _seen(landed, "fetched", "afters", "timers", "line") == ([], 1, [2000], STARTING)
    assert _seen(read, "fetched", "timers", "inFlight") == ([READ], [], 1)
    assert _seen(started, "fetched", "afters", "timers", "line") == ([], 1, [2000], STARTED)
    assert read_again["fetched"] == [READ]
    assert _seen(ended, "fetched", "afters", "timers", "inFlight") == ([], 2, [], 0)
    assert _seen(last, "fetched", "afters", "timers", "line", "error") == ([], 2, [], CLAIMED, None)


def test_a_drawer_closed_during_the_launchs_post_follows_nothing() -> None:
    trace = _drive([POST, ITEM_TAKEN, STOP, _answer(201, _launch("opened"))])
    assert trace[1]["fetched"] == [LAUNCH_POST]
    ended = trace[-1]
    assert _seen(ended, "fetched", "afters", "timers", "inFlight") == ([], 1, [], 0)


def test_a_drawer_closed_during_the_items_post_opens_no_window() -> None:
    """D1: a stop while ``POST /api/inbox`` is in flight is not erased by the launch: no launch is
    posted, no timer runs, and ``after`` runs once so the view reads its company again."""
    trace = _drive([POST, STOP, ITEM_TAKEN])
    assert trace[0]["fetched"] == [INBOX_POST]
    ended = trace[-1]
    assert _seen(ended, "fetched", "afters", "timers", "inFlight") == ([], 1, [], 0)
    assert _seen(ended, "line", "error") == (None, None)


def test_a_read_that_fails_tries_again_and_a_read_that_succeeds_clears_its_sentence() -> None:
    trace = _drive(
        [_landed(_launch("opened")), TICK, FAIL, TICK, _answer(200, _launch("started")), TICK]
    )
    landed, read, failed, again, started, third = trace
    assert _seen(landed, "timers", "line", "error") == ([2000], STARTING, None)
    assert read["fetched"] == [READ]
    assert _seen(failed, "afters", "timers", "line", "error") == (0, [2000], STARTING, TRYING)
    assert again["fetched"] == [READ]
    assert _seen(started, "afters", "timers", "line", "error") == (0, [2000], STARTED, None)
    assert third["fetched"] == [READ]


def test_30_failed_reads_in_a_row_stop_the_following_until_the_company_is_read_again() -> None:
    """The 30th failed read in a row stops the following with its second sentence and runs
    ``after`` once; a read of the company that starts a following again clears the sentence."""
    trace = _drive([_landed(_launch("opened")), *[TICK, FAIL] * 30, _landed(_launch("started"))])
    failures = trace[2:-1:2]
    assert len(failures) == 30
    for failed in failures[:29]:
        assert _seen(failed, "afters", "timers", "error") == (0, [2000], TRYING)
    assert _seen(failures[29], "afters", "timers", "inFlight", "error") == (1, [], 0, RELOAD)
    landed = trace[-1]
    assert _seen(landed, "afters", "timers", "line", "error") == (1, [2000], STARTED, None)


def test_a_409_from_the_launchs_post_shows_no_error() -> None:
    """The item is no longer pending or a launch for it is in flight: the company read again draws
    the claim or that launch, so no error shows, and ``after`` runs once."""
    refusal = {"detail": "a window for this request opened 20 seconds ago"}
    trace = _drive([POST, ITEM_TAKEN, _answer(409, refusal)])
    ended = trace[-1]
    assert _seen(ended, "fetched", "afters", "timers", "inFlight") == ([], 1, [], 0)
    assert _seen(ended, "error", "line") == (None, None)


def test_a_launch_post_that_fails_on_the_network_says_the_window_was_not_opened() -> None:
    """A refusal shows the server's sentence; a post that fails on the network says that the
    window was not opened, and why, not the browser's bare message."""
    refused = _drive([POST, ITEM_TAKEN, _answer(400, {"detail": "launching is not set up"})])
    assert _seen(refused[-1], "afters", "error") == (1, "launching is not set up")
    failed = _drive([POST, ITEM_TAKEN, FAIL])[-1]
    assert _seen(failed, "afters", "timers", "error") == (
        1,
        [],
        "The window was not opened: Failed to fetch.",
    )
