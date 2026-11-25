"""The work inbox: requests for an analysis, claimed and completed by an agent (spec 2026-11-06
Tier 2, section 8).

A work item names a company, a mode (``valuation review`` or ``full report``), the requester's
note (it may be empty), the company's snapshot at posting (``None`` for a company without one),
its origin (``owner`` or ``agent``) and who posted it. Its state moves from ``pending`` to
``claimed`` (the claiming agent's model identifier and the time), and from either to ``done``
(the report id) or ``declined`` (the reason). A claimed item can be claimed again by name, a
takeover. A company has one open item (pending or claimed) at most: a second post raises
``ItemOpen``. A write the item's state does not allow raises ``WrongState`` (``"work item 3 is
done"``); both are ``ValueError``s. A missing item raises ``KeyError(id)``. Each write is one
transaction; it joins the caller's when there is one, so the caller's ledger row commits with
it. Who declined an item is the ledger's (``decliners``; spec 2026-11-25 owner's inbox, 7.1): the
writer of the newest row of kind ``decline`` that names it.

Fairband posts no item by itself and drops none (spec 2026-11-25 owner's inbox, 8), so a read of
the inbox writes nothing. A row the expiry rule wrote before it left still reads as stored: its
origin ``expiry``, the system as its poster, the record it stood for in ``expiry_valid_until``,
``expiry_review_id`` or ``expiry_secondary_id``, and, for one that dropped, the state
``dropped``. A pending one is claimed, completed or declined as any item is.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from fairband.policy.settings import exchange_symbol
from fairband.store._codec import dump_stamp, inserted_id, load_date, load_stamp
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

Mode = Literal["valuation review", "full report"]
State = Literal["pending", "claimed", "done", "declined", "dropped"]
Origin = Literal["owner", "agent", "expiry"]

MODES: tuple[Mode, ...] = get_args(Mode)
STATES: tuple[State, ...] = get_args(State)
OPEN_STATES = ("pending", "claimed")  # the states of an open item


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
    expiry_review_id: int | None = None
    expiry_secondary_id: int | None = None


def post_item(
    conn: sqlite3.Connection,
    symbol: str,
    mode: Mode,
    note: str,
    snapshot_id: int | None,
    origin: Origin,
    writer: Writer,
    at: datetime,
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
            " posted_actor, posted_client, posted_at, state)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')",
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
            ),
        )
    return inserted_id(cursor)


def claim_item(conn: sqlite3.Connection, item_id: int, actor: str, at: datetime) -> WorkItem:
    """Claim the item for the agent ``actor``: a pending one, or a claimed one taken over."""
    assignments = "state = 'claimed', claimed_by = ?, claimed_at = ?"
    return _move(conn, item_id, OPEN_STATES, assignments, (actor, dump_stamp(at)))


def complete_item(conn: sqlite3.Connection, item_id: int, report_id: int, at: datetime) -> WorkItem:
    """Mark the open item done with report ``report_id``; the caller checks the report."""
    assignments = "state = 'done', report_id = ?, finished_at = ?"
    return _move(conn, item_id, OPEN_STATES, assignments, (report_id, dump_stamp(at)))


def decline_item(conn: sqlite3.Connection, item_id: int, reason: str, at: datetime) -> WorkItem:
    """Decline the open item for ``reason``, kept as written."""
    if not reason.strip():
        raise ValueError("a decline needs a reason")
    assignments = "state = 'declined', reason = ?, finished_at = ?"
    return _move(conn, item_id, OPEN_STATES, assignments, (reason, dump_stamp(at)))


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
        (exchange_symbol(symbol), *OPEN_STATES),
    ).fetchone()
    return None if row is None else _item(row)


def oldest_pending(conn: sqlite3.Connection) -> WorkItem | None:
    """The pending item posted first, if there is one."""
    row = conn.execute(
        "SELECT * FROM work_items WHERE state = 'pending' ORDER BY id LIMIT 1"
    ).fetchone()
    return None if row is None else _item(row)


def decliners(conn: sqlite3.Connection) -> dict[int, Writer]:
    """The writer of each item's decline, by item id, in one query: the newest ledger row of kind
    ``decline`` that names the item. An item no such row names is left out."""
    rows = conn.execute(
        "SELECT work_item_id, principal, actor, client FROM ledger WHERE id IN"
        " (SELECT MAX(id) FROM ledger WHERE kind = 'decline' AND work_item_id IS NOT NULL"
        " GROUP BY work_item_id)"
    )
    return {r["work_item_id"]: Writer(r["principal"], r["actor"], r["client"]) for r in rows}


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
        expiry_review_id=row["expiry_review_id"],
        expiry_secondary_id=row["expiry_secondary_id"],
    )
