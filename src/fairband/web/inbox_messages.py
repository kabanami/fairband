"""The owner's read of the messages (spec 2026-11-25 owner's inbox, 7.1 and 7.2).

``GET /api/inbox/messages`` answers ``{"messages": [...]}``: one message for each report an agent
finished and each request an agent declined. A message is not stored: it is read from the work
item, its report and the report's records each time it is asked for, so it cannot disagree with
its report. A work item gives one message, or none, by its state:

- ``done``, whatever its origin, gives a ``done`` message;
- ``declined`` gives a ``declined`` message where an agent wrote the decline, the writer of the
  newest ledger row of kind ``decline`` that names the item (``store.inbox.decliners``); the
  owner's decline, and one with no such row, give none;
- ``pending``, ``claimed`` and ``dropped`` give none.

A message's keys are camelCase. Both kinds carry ``itemId``, ``symbol``, ``kind`` (``done`` or
``declined``), ``mode``, ``at`` (the item's finish time as ISO text) and ``by``, who ended it, as
``{principal, actor}``. A ``done`` message's ``mode`` and ``by`` are its report's, which says what
was made: nothing checks that a report's mode is its item's. It adds ``reportId``,
``reportRevision``, ``stance`` and the report's call as the Research tab answers it
(``research_page.report_call``) for the report's snapshot, review and secondary valuation:
``value``, ``basis``, ``note``, ``price``, ``priceDate``, ``validUntil`` and ``refusal``. The call
is ``report_call``'s and nothing here computes a figure, so a message and the report's own page
show the same value, price and dates. A ``done`` item whose report row or its snapshot row is
missing still gives a message: the item's mode, ``by`` with both parts ``None``, and ``None`` for
``reportRevision``, ``stance`` and the call's seven. A ``declined`` message's ``mode`` is the
item's and its ``by`` the decline's writer; it adds ``reason``, as written.

The messages come newest first: by ``at``, then by ``itemId``, the highest first. The read is
the owner's: a request whose ``X-Fairband-Principal`` header is ``agent`` is refused 403, "the
messages are the owner's"; one with no principal header is the page's.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request

from fairband.store.inbox import Mode, WorkItem, decliners, work_items
from fairband.store.ledger import Principal, Writer
from fairband.store.reports import ReportHead, report_heads
from fairband.store.reviews import review_row
from fairband.store.secondary import secondary_row
from fairband.store.snapshots import snapshot_row
from fairband.web.identity import PRINCIPAL_HEADER
from fairband.web.research_page import report_call

Kind = Literal["done", "declined"]

OWNERS = "the messages are the owner's"
# The figures of a done message, as ``report_call`` answers them.
CALL = ("value", "basis", "note", "price", "priceDate", "validUntil", "refusal")


def add_message_routes(app: FastAPI, conn_factory: Callable[[], sqlite3.Connection]) -> None:
    """Register the owner's read of the messages (the module docstring)."""

    @app.get("/api/inbox/messages")
    def get_messages(request: Request) -> dict[str, Any]:
        if request.headers.get(PRINCIPAL_HEADER) == "agent":
            raise HTTPException(403, OWNERS)
        with closing(conn_factory()) as conn:
            return {"messages": messages(conn)}


def messages(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Every message, newest first (the module docstring): the items, who declined each and the
    done items' report heads in one query each, then each done message's snapshot, review and
    secondary valuation."""
    items = sorted(work_items(conn), key=_order, reverse=True)
    declined = decliners(conn)
    done = [i.report_id for i in items if i.state == "done" and i.report_id is not None]
    heads = report_heads(conn, done)
    found: list[dict[str, Any]] = []
    for item in items:
        if item.state == "done":
            head = None if item.report_id is None else heads.get(item.report_id)
            found.append(_done(conn, item, head))
        elif item.state == "declined":
            writer = declined.get(item.id)
            if writer is not None and writer.principal == "agent":
                found.append(_declined(item, writer))
    return found


def _order(item: WorkItem) -> tuple[float, int]:
    """An item's place among the messages: its finish time, then its id. A closed item always
    has a finish time; one without would come last."""
    finished = float("-inf") if item.finished_at is None else item.finished_at.timestamp()
    return finished, item.id


def _done(conn: sqlite3.Connection, item: WorkItem, head: ReportHead | None) -> dict[str, Any]:
    """The message of a done item completed with the report ``head``, ``None`` where the report's
    row is missing; without the report or its snapshot, the item's mode and no author and no
    figures."""
    snapshot = None if head is None else snapshot_row(conn, head.snapshot_id)
    if head is None or snapshot is None:
        unknown = {"reportId": item.report_id, "reportRevision": None, "stance": None}
        return _message(item, "done", item.mode, None, None) | unknown | dict.fromkeys(CALL)
    review = None if head.review_id is None else review_row(conn, head.review_id)
    secondary = None if head.secondary_id is None else secondary_row(conn, head.secondary_id)
    call = report_call(snapshot, review, secondary)
    return (
        _message(item, "done", head.mode, head.principal, head.actor)
        | {"reportId": item.report_id, "reportRevision": head.revision, "stance": head.stance}
        | {key: call[key] for key in CALL}
    )


def _declined(item: WorkItem, writer: Writer) -> dict[str, Any]:
    """The message of an item declined by ``writer``."""
    message = _message(item, "declined", item.mode, writer.principal, writer.actor)
    return message | {"reason": item.reason}


def _message(
    item: WorkItem, kind: Kind, mode: Mode, principal: Principal | None, actor: str | None
) -> dict[str, Any]:
    """The keys both kinds of message carry."""
    return {
        "itemId": item.id,
        "symbol": item.symbol,
        "kind": kind,
        "mode": mode,
        "at": None if item.finished_at is None else item.finished_at.isoformat(),
        "by": {"principal": principal, "actor": actor},
    }
