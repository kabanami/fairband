"""The launch record: a window opened from the research button, and what its launcher reported
(spec 2026-11-16, section 8).

A launch names its work item (``None`` for a test from Settings) and its agent (``claude``). It is
made ``opening``, before the window command runs. When the command ends with exit 0 the server
moves it to ``opened`` through the function ``opened``, and when it does not, to ``failed`` at the
``window`` stage; the launcher moves it to ``started``, then ``ended`` with the agent's exit code,
or to ``failed`` at the ``agent`` stage. A failure keeps its sentence. The moves are ``opening`` to
``opened``, ``started`` or ``failed``; ``opened`` to ``started`` or ``failed``; ``started`` to
``ended``. Any other raises ``WrongMove`` (``"a launch that is ended does not become started"``).
A missing launch raises ``KeyError(id)``.

A launch is overdue (``overdue``) when it is ``opened`` or ``started``, its item is still pending,
and ``CLAIM_WAIT_S`` seconds have passed since it was made. A test is overdue while it is
``opened`` after those seconds, and never once it has started. The caller works this out when it
reads a launch, on its own clock.

An item has one launch in flight: ``insert_launch`` raises ``InFlight`` (``"a window for this
request opened 20 seconds ago"``) while the item's newest launch is ``opening``, ``opened`` or
``started`` and not overdue. A launch left ``opening`` is never overdue, so it holds its item
until ``fail_opening``, which the app runs when it starts, marks it failed. A test neither blocks
nor is blocked. Each write is one transaction; it joins the caller's when there is one, so the
route's check of the item and the insert commit together. Both errors are ``ValueError``s.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction

CLAIM_WAIT_S = 90
State = Literal["opening", "opened", "started", "ended", "failed"]
Stage = Literal["window", "agent"]
STOPPED = "the server stopped while the window command ran"

_MOVES: dict[State, tuple[State, ...]] = {
    "opening": ("opened", "started", "failed"),
    "opened": ("started", "failed"),
    "started": ("ended",),
}
_IN_FLIGHT: tuple[State, ...] = ("opening", "opened", "started")


class WrongMove(ValueError):
    """The launch's state does not allow the move."""


class InFlight(ValueError):
    """The item's newest launch is in flight."""


@dataclass(frozen=True)
class LaunchRow:
    id: int
    item_id: int | None
    agent: str
    state: State
    stage: Stage | None
    detail: str | None
    exit_code: int | None
    created_at: datetime
    updated_at: datetime


def overdue(row: LaunchRow, item_state: str | None, now: datetime) -> bool:
    """Whether the launch is overdue at ``now``, its item in ``item_state`` (``None`` for a test):
    an item's launch while ``opened`` or ``started`` with the item pending, a test while
    ``opened``, each once ``CLAIM_WAIT_S`` seconds have passed since it was made."""
    if now - row.created_at < timedelta(seconds=CLAIM_WAIT_S):
        return False
    if row.item_id is None:
        return row.state == "opened"
    return row.state in ("opened", "started") and item_state == "pending"


def insert_launch(
    conn: sqlite3.Connection, item_id: int | None, agent: str, at: datetime
) -> LaunchRow:
    """Make a launch ``opening`` for the item ``item_id`` (``None`` for a test) and ``agent``, at
    ``at``; the launch. The item is read as pending: the caller holds the write lock and has
    checked it. ``InFlight`` when the item's newest launch is in flight and not overdue, with the
    whole seconds since that launch was made, never below 0 where the clock stepped back."""
    with transaction(conn, immediate=True):
        if item_id is not None:
            newest = newest_launch(conn, item_id)
            if (
                newest is not None
                and newest.state in _IN_FLIGHT
                and not overdue(newest, "pending", at)
            ):
                seconds = max(0, int((at - newest.created_at).total_seconds()))
                raise InFlight(f"a window for this request opened {seconds} seconds ago")
        cursor = conn.execute(
            "INSERT INTO launches (item_id, agent, state, created_at, updated_at)"
            " VALUES (?, ?, 'opening', ?, ?)",
            (item_id, agent, dump_stamp(at), dump_stamp(at)),
        )
        return launch(conn, inserted_id(cursor))


def launch(conn: sqlite3.Connection, launch_id: int) -> LaunchRow:
    """The launch; ``KeyError(launch_id)`` when there is none."""
    row = conn.execute("SELECT * FROM launches WHERE id = ?", (launch_id,)).fetchone()
    if row is None:
        raise KeyError(launch_id)
    return _launch(row)


def newest_launch(conn: sqlite3.Connection, item_id: int) -> LaunchRow | None:
    """The item's launch with the highest id, if it has one."""
    row = conn.execute(
        "SELECT * FROM launches WHERE item_id = ? ORDER BY id DESC LIMIT 1", (item_id,)
    ).fetchone()
    return None if row is None else _launch(row)


def move_launch(
    conn: sqlite3.Connection,
    launch_id: int,
    to: State,
    at: datetime,
    *,
    stage: Stage | None = None,
    detail: str | None = None,
    exit_code: int | None = None,
) -> LaunchRow:
    """Move the launch to ``to`` at ``at``, keeping ``stage`` and ``detail`` (a failure's) and
    ``exit_code`` (an end's); the launch as it now is. ``WrongMove`` for a move the launch's state
    does not allow; ``ValueError`` for a failure that names no stage."""
    if to == "failed" and stage is None:
        raise ValueError("a failed launch names its stage")
    with transaction(conn, immediate=True):
        current = launch(conn, launch_id)
        if to not in _MOVES.get(current.state, ()):
            raise WrongMove(f"a launch that is {current.state} does not become {to}")
        conn.execute(
            "UPDATE launches SET state = ?, stage = ?, detail = ?, exit_code = ?, updated_at = ?"
            " WHERE id = ?",
            (to, stage, detail, exit_code, dump_stamp(at), launch_id),
        )
        return launch(conn, launch_id)


def opened(conn: sqlite3.Connection, launch_id: int, at: datetime) -> LaunchRow:
    """Move an ``opening`` launch to ``opened`` at ``at``: the window command ended with exit 0.
    A launch the launcher has already moved on stays as it is, and is answered as it is."""
    with transaction(conn, immediate=True):
        current = launch(conn, launch_id)
        if current.state != "opening":
            return current
        return move_launch(conn, launch_id, "opened", at)


def fail_opening(conn: sqlite3.Connection, at: datetime) -> int:
    """Set every ``opening`` launch to ``failed`` at the ``window`` stage with ``STOPPED``, at
    ``at``: the server stopped while its window command ran. Return how many."""
    with transaction(conn):
        cursor = conn.execute(
            "UPDATE launches SET state = 'failed', stage = 'window', detail = ?, updated_at = ?"
            " WHERE state = 'opening'",
            (STOPPED, dump_stamp(at)),
        )
    return cursor.rowcount


def _launch(row: sqlite3.Row) -> LaunchRow:
    return LaunchRow(
        id=row["id"],
        item_id=row["item_id"],
        agent=row["agent"],
        state=row["state"],
        stage=row["stage"],
        detail=row["detail"],
        exit_code=row["exit_code"],
        created_at=load_stamp(row["created_at"]),
        updated_at=load_stamp(row["updated_at"]),
    )
