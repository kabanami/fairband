"""The work inbox: requests for an analysis, claimed and completed by an agent (spec 2026-11-06
Tier 2, section 8).

A work item names a company, a mode (``valuation review`` or ``full report``), the requester's
note (it may be empty), the company's snapshot at posting (``None`` for a company without one),
its origin (``owner``, ``agent`` or ``expiry``) and who posted it. Its state moves from
``pending`` to ``claimed`` (the claiming agent's model identifier and the time), and from either
to ``done`` (the report id), ``declined`` (the reason) or, for a pending expiry item only,
``dropped``. A claimed item can be claimed again by name, a takeover. A company has one open item
(pending or claimed) at most: a second post raises ``ItemOpen``. A write the item's state does
not allow raises ``WrongState`` (``"work item 3 is done"``); both are ``ValueError``s. A missing
item raises ``KeyError(id)``. Each write is one transaction; it joins the caller's when there is
one, so the caller's ledger row commits with it.

The expiry rule (``post_expiry_items``) runs when the inbox is read: every company on any
watchlist whose latest snapshot expired (``valid_until`` before today), with no open item and no
expiry item yet posted for that same ``valid_until``, gets a valuation review posted by the
system; then every pending expiry item whose company is on no watchlist drops. The rule writes the
system's ledger row of each post and each drop itself, in its transaction.

An expiry item stands for its window, the ``valid_until`` it was posted for, whatever becomes of
it. Declined, in particular, it holds: no new item is posted for the company on any later read
while its latest snapshot's window is that one, including a newer snapshot in the same window,
as a price refresh or a revalue on unchanged inputs writes (the window is the next earnings date
or the data date's fallback, so only new data moves it). A new window that has also ended may
post again. The window, not the snapshot, is the key, so a daily price refresh does not undo a
decline.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from fairband.policy.settings import exchange_symbol
from fairband.store._codec import dump_date, dump_stamp, inserted_id, load_date, load_stamp
from fairband.store.db import transaction
from fairband.store.ledger import SYSTEM, Principal, Writer, record
from fairband.store.snapshots import latest_snapshot

Mode = Literal["valuation review", "full report"]
State = Literal["pending", "claimed", "done", "declined", "dropped"]
Origin = Literal["owner", "agent", "expiry"]

MODES: tuple[Mode, ...] = get_args(Mode)
STATES: tuple[State, ...] = get_args(State)
_OPEN = ("pending", "claimed")


class ItemOpen(ValueError):
    """The company already has an open item."""


class WrongState(ValueError):
    """The item's state does not allow the write."""


@dataclass(frozen=True)
class WorkItem:
    id: int
    symbol: str
    mode: Mode
    note: str
    snapshot_id: int | None
    origin: Origin
    posted_by: Principal
    posted_actor: str | None
    posted_client: str | None
    posted_at: datetime
    state: State
    claimed_by: str | None
    claimed_at: datetime | None
    report_id: int | None
    reason: str | None
    finished_at: datetime | None
    expiry_valid_until: date | None


def post_item(
    conn: sqlite3.Connection,
    symbol: str,
    mode: Mode,
    note: str,
    snapshot_id: int | None,
    origin: Origin,
    writer: Writer,
    at: datetime,
    *,
    expiry_valid_until: date | None = None,
) -> int:
    """Post a pending item for the company, by ``writer``; return its id."""
    symbol = exchange_symbol(symbol)
    if mode not in MODES:
        raise ValueError("a mode is valuation review or full report")
    with transaction(conn, immediate=True):
        if open_item(conn, symbol) is not None:
            raise ItemOpen(f"an item for {symbol} is open")
        cursor = conn.execute(
            "INSERT INTO work_items (symbol, mode, note, snapshot_id, origin, posted_by,"
            " posted_actor, posted_client, posted_at, state, expiry_valid_until)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (
                symbol,
                mode,
                note,
                snapshot_id,
                origin,
                writer.principal,
                writer.actor,
                writer.client,
                dump_stamp(at),
                dump_date(expiry_valid_until),
            ),
        )
    return inserted_id(cursor)


def claim_item(conn: sqlite3.Connection, item_id: int, actor: str, at: datetime) -> WorkItem:
    """Claim the item for the agent ``actor``: a pending one, or a claimed one taken over."""
    assignments = "state = 'claimed', claimed_by = ?, claimed_at = ?"
    return _move(conn, item_id, _OPEN, assignments, (actor, dump_stamp(at)))


def complete_item(conn: sqlite3.Connection, item_id: int, report_id: int, at: datetime) -> WorkItem:
    """Mark the open item done with report ``report_id``; the caller checks the report."""
    assignments = "state = 'done', report_id = ?, finished_at = ?"
    return _move(conn, item_id, _OPEN, assignments, (report_id, dump_stamp(at)))


def decline_item(conn: sqlite3.Connection, item_id: int, reason: str, at: datetime) -> WorkItem:
    """Decline the open item for ``reason``, kept as written."""
    if not reason.strip():
        raise ValueError("a decline needs a reason")
    assignments = "state = 'declined', reason = ?, finished_at = ?"
    return _move(conn, item_id, _OPEN, assignments, (reason, dump_stamp(at)))


def drop_item(conn: sqlite3.Connection, item_id: int, at: datetime) -> WorkItem:
    """Drop the pending item: the system's write when its company left every watchlist."""
    return _move(
        conn, item_id, ("pending",), "state = 'dropped', finished_at = ?", (dump_stamp(at),)
    )


def work_items(conn: sqlite3.Connection, state: State | None = None) -> list[WorkItem]:
    """Every item, or those in ``state``, newest first."""
    if state is None:
        rows = conn.execute("SELECT * FROM work_items ORDER BY id DESC")
    else:
        rows = conn.execute("SELECT * FROM work_items WHERE state = ? ORDER BY id DESC", (state,))
    return [_item(r) for r in rows]


def work_item(conn: sqlite3.Connection, item_id: int) -> WorkItem:
    """The item; ``KeyError(item_id)`` when there is none."""
    row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise KeyError(item_id)
    return _item(row)


def open_item(conn: sqlite3.Connection, symbol: str) -> WorkItem | None:
    """The company's pending or claimed item, if it has one."""
    row = conn.execute(
        "SELECT * FROM work_items WHERE symbol = ? AND state IN (?, ?) ORDER BY id DESC LIMIT 1",
        (exchange_symbol(symbol), *_OPEN),
    ).fetchone()
    return None if row is None else _item(row)


def oldest_pending(conn: sqlite3.Connection) -> WorkItem | None:
    """The pending item posted first, if there is one."""
    row = conn.execute(
        "SELECT * FROM work_items WHERE state = 'pending' ORDER BY id LIMIT 1"
    ).fetchone()
    return None if row is None else _item(row)


def post_expiry_items(
    conn: sqlite3.Connection, today: date, at: datetime
) -> tuple[list[int], list[int]]:
    """Run the expiry rule (the module docstring) on ``today``, posting and dropping ``at``;
    return the ids posted and the ids dropped, each in ascending order. A company on two lists is
    one company. Each post and each drop is the system's ledger row, written in the same
    transaction (``_record_expiry``)."""
    with transaction(conn, immediate=True):
        expired = conn.execute(
            "SELECT s.symbol, s.id, s.valid_until FROM snapshots s"
            " WHERE s.id IN (SELECT MAX(id) FROM snapshots GROUP BY symbol)"
            " AND s.symbol IN (SELECT symbol FROM watchlist_entries)"
            " AND s.valid_until < ?"
            " AND NOT EXISTS (SELECT 1 FROM work_items w WHERE w.symbol = s.symbol"
            " AND (w.state IN (?, ?) OR (w.origin = 'expiry'"
            " AND w.expiry_valid_until = s.valid_until)))"
            " ORDER BY s.symbol",
            (dump_date(today), *_OPEN),
        ).fetchall()
        posted = [
            post_item(
                conn,
                r["symbol"],
                "valuation review",
                f"expired {r['valid_until']}",
                r["id"],
                "expiry",
                SYSTEM,
                at,
                expiry_valid_until=load_date(r["valid_until"]),
            )
            for r in expired
        ]
        stranded = conn.execute(
            "SELECT id FROM work_items WHERE state = 'pending' AND origin = 'expiry'"
            " AND symbol NOT IN (SELECT symbol FROM watchlist_entries) ORDER BY id"
        ).fetchall()
        dropped = [drop_item(conn, r["id"], at).id for r in stranded]
        for item_id in posted:
            item = work_item(conn, item_id)
            _record_expiry(conn, at, "work-item", item, f"{item.mode} posted: {item.note}")
        for item_id in dropped:
            item = work_item(conn, item_id)
            _record_expiry(conn, at, "drop", item, f"dropped: {item.symbol} is on no watchlist")
    return posted, dropped


def _record_expiry(
    conn: sqlite3.Connection, at: datetime, kind: str, item: WorkItem, summary: str
) -> None:
    """The system's ledger row of the expiry rule's write to ``item``, which it also rests on,
    with the company's latest snapshot, in the caller's transaction. An expiry item's note is one
    short line, ``expired <date>``, so a post's summary carries it whole."""
    snapshot = latest_snapshot(conn, item.symbol)
    record(
        conn,
        SYSTEM,
        at,
        kind,
        item.symbol,
        "work_items",
        item.id,
        snapshot_id=None if snapshot is None else snapshot.id,
        work_item_id=item.id,
        summary=summary,
    )


def _move(
    conn: sqlite3.Connection,
    item_id: int,
    allowed: tuple[str, ...],
    assignments: str,
    values: tuple[str | int, ...],
) -> WorkItem:
    """Set ``assignments``, whose placeholders take ``values``, on an item whose state is in
    ``allowed``; the item as it now is."""
    with transaction(conn, immediate=True):
        current = work_item(conn, item_id)
        if current.state not in allowed:
            raise WrongState(f"work item {item_id} is {current.state}")
        conn.execute(f"UPDATE work_items SET {assignments} WHERE id = ?", (*values, item_id))
        return work_item(conn, item_id)


def _item(row: sqlite3.Row) -> WorkItem:
    return WorkItem(
        id=row["id"],
        symbol=row["symbol"],
        mode=row["mode"],
        note=row["note"],
        snapshot_id=row["snapshot_id"],
        origin=row["origin"],
        posted_by=row["posted_by"],
        posted_actor=row["posted_actor"],
        posted_client=row["posted_client"],
        posted_at=load_stamp(row["posted_at"]),
        state=row["state"],
        claimed_by=row["claimed_by"],
        claimed_at=load_stamp(row["claimed_at"]),
        report_id=row["report_id"],
        reason=row["reason"],
        finished_at=load_stamp(row["finished_at"]),
        expiry_valid_until=load_date(row["expiry_valid_until"]),
    )
