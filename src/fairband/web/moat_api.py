"""The moat class's write: the owner's control on the company page and the agent's ``moat_set``
(spec 2026-11-19 8.6; ``method.md`` 4.9).

``PUT /api/companies/{symbol}/moat`` takes ``{class, reason?, evidence?}``, the class Wide, Narrow
or None and the evidence items an override's (``reviews_api.Evidence``). The writer is read as on
every write (``identity``): the owner without the agent's headers, else the agent with its actor.
In this order, each refusing with nothing stored: the body's types, a class outside the three
among them, 400 "class: ..."; an agent's write with a blank reason, 400 "a moat verdict needs a
reason", then with no evidence item, 400 "a moat verdict needs evidence"; a symbol that is not
one, 400; a company with no snapshot, 404 "no snapshot for <symbol>"; while a refresh runs, 409 "a
refresh is running: set the class when it ends"; then an agent's evidence items of kind
``guidance`` as an override's (``reviews_api.require_guidance``): 400 "a guidance item cites its
record as guidance:<id>" for a ref of another form, 404 "no guidance record <id> for <symbol>"
for a record that is not the company's, 409 for one a later call's record superseded. The owner's
write needs neither a reason nor evidence: a blank reason is stored as none, so neither the ledger
nor the snapshot's note carries ": ", and evidence is kept for an agent alone (spec 8.3).

Then, in one transaction that takes the write lock at once, so the check that no refresh runs and
the revalue's own record stand under it: the company's row of the moat table becomes the writer's
(``store.moat.set_moat``), its ``previous`` the class in force before it; the ledger row, kind
``moat``, resting on the company's latest snapshot, "moat Narrow → Wide: <the reason's gist>", or
"moat Wide: ..." with no class before it, and no ": ..." without a reason; then the revalue of the
one company (``refresh.run.revalue_company``) under the effective policy and the moat table the
app was given, which ``serve`` also hands every refresh: a ``revalue`` record naming it, the stage
``moat``, the company valued on the facts the store holds and the latest deciles, a review
following the snapshot, and no vendor call; and the row cites the snapshot it wrote
(``set_snapshot``). The same class as the one in force is a write like any other: the row becomes
the writer's and the company is valued again. Any exception rolls the whole transaction back, the
revalue's record with it, so no record is left running to block a later refresh.

``DELETE`` on the same path is the owner's alone, 403 "returning to Fairband's class is the
owner's" for an agent; 404 "the moat table holds no class for <symbol>" where the table holds no
entry for the company; the snapshot's 404 and the refresh's 409 as above. It writes the table's
entry in place of the row (``file_moat``), the ledger row "moat Wide → Narrow: Fairband's class",
and values the company again the same way; a file row cites no snapshot.

Each answers 200 with ``{moatClass, snapshot}``: the row as ``moat_json`` gives it and the new
snapshot's ``{id, value, refusal}``.

``moat_json`` is the row as the company detail serves it too (``GET /api/companies/{symbol}``,
``moatClass``): ``{class, source, fileVersion, judgedOn, previous, reason, actor, at,
fileClass}``, ``fileClass`` the table's class for the company or ``None``; ``None`` without a row.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fairband.policy import Moat, Policy
from fairband.policy.moat import MoatTable
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.refresh.run import revalue_company
from fairband.store.db import transaction
from fairband.store.ledger import Writer, record
from fairband.store.moat import MoatRow, file_moat, moat_row, set_moat, set_snapshot
from fairband.store.refreshes import current_refresh
from fairband.store.snapshots import SnapshotRow, snapshot_row
from fairband.web.agents_api import WriterOf, gist
from fairband.web.reviews_api import Evidence, require_guidance, snapshot_of
from fairband.web.settings_api import effective

NEEDS_A_REASON = "a moat verdict needs a reason"
NEEDS_EVIDENCE = "a moat verdict needs evidence"
REFRESH_RUNNING = "a refresh is running: set the class when it ends"
OWNERS_RETURN = "returning to Fairband's class is the owner's"
FILES_CLASS = "Fairband's class"  # the ledger's reason for the owner's return


class MoatPut(BaseModel):
    """The write's body; ``class``, a Python word, is the field's alias."""

    moat_class: Moat = Field(alias="class")
    reason: str | None = None
    evidence: list[Evidence] | None = None


def moat_json(row: MoatRow | None, table: MoatTable) -> dict[str, Any] | None:
    """The company's row of the moat table as the API serves it (module docstring), with
    ``table``'s class for the company; ``None`` without a row."""
    if row is None:
        return None
    entry = table.entries.get(row.symbol)
    return {
        "class": row.moat,
        "source": row.source,
        "fileVersion": row.file_version,
        "judgedOn": row.judged_on.isoformat(),
        "previous": row.previous,
        "reason": row.reason,
        "actor": row.actor,
        "at": row.at.isoformat(),
        "fileClass": None if entry is None else entry.moat,
    }


def add_moat_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    moat: MoatTable,
    clock: Callable[[], datetime],
) -> None:
    """Register the moat class's write and its return; ``policy`` is the file's, which the user's
    settings overlay, ``tax`` the table the inputs are built with and ``moat`` the moat table the
    revalue loads and a return reads."""

    def revalued(
        conn: sqlite3.Connection,
        writer: Writer,
        at: datetime,
        symbol: str,
        latest: SnapshotRow,
        summary: str,
    ) -> int:
        """The write's ledger row, ``summary`` resting on ``latest``, the company's snapshot before
        the write; then the company's revalue under the effective policy; the snapshot it wrote."""
        current = effective(conn, policy)
        record(conn, writer, at, "moat", symbol, None, None, snapshot_id=latest.id, summary=summary)
        return revalue_company(conn, symbol, current, tax, moat, clock, made=True)

    def answer(conn: sqlite3.Connection, symbol: str, snapshot_id: int) -> dict[str, Any]:
        written = snapshot_row(conn, snapshot_id)
        assert written is not None  # this transaction's
        return {
            "moatClass": moat_json(moat_row(conn, symbol), moat),
            "snapshot": {"id": written.id, "value": written.value, "refusal": written.refusal},
        }

    @app.put("/api/companies/{symbol}/moat")
    def put_moat(symbol: str, body: MoatPut, writer: WriterOf) -> dict[str, Any]:
        """Set the company's class and value it again (module docstring)."""
        reason = body.reason if body.reason is not None and body.reason.strip() else None
        agent = writer.principal == "agent"
        if agent and reason is None:
            raise HTTPException(400, NEEDS_A_REASON)
        if agent and not body.evidence:
            raise HTTPException(400, NEEDS_EVIDENCE)
        evidence = [e.model_dump() for e in body.evidence or ()] if agent else None
        company = _symbol(symbol)
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            latest = _writable(conn, company)
            if agent:
                require_guidance(conn, company, body.evidence or [])
            row = set_moat(conn, company, body.moat_class, writer, reason, evidence, at)
            why = None if reason is None else gist(reason)
            summary = _summary(row.previous, row.moat, why)
            snapshot_id = revalued(conn, writer, at, company, latest, summary)
            set_snapshot(conn, company, snapshot_id)
            return answer(conn, company, snapshot_id)

    @app.delete("/api/companies/{symbol}/moat")
    def delete_moat(symbol: str, writer: WriterOf) -> dict[str, Any]:
        """Return the company to the table's class and value it again (module docstring)."""
        if writer.principal != "owner":
            raise HTTPException(403, OWNERS_RETURN)
        company = _symbol(symbol)
        if company not in moat.entries:
            raise HTTPException(404, f"the moat table holds no class for {company}")
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            latest = _writable(conn, company)
            held = moat_row(conn, company)
            row = file_moat(conn, company, moat, at)
            summary = _summary(None if held is None else held.moat, row.moat, FILES_CLASS)
            snapshot_id = revalued(conn, writer, at, company, latest, summary)
            return answer(conn, company, snapshot_id)


def _symbol(text: str) -> str:
    """The path's symbol in the store's form; 400 for one that is not a symbol."""
    try:
        return exchange_symbol(text)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


def _writable(conn: sqlite3.Connection, symbol: str) -> SnapshotRow:
    """The company's latest snapshot, which the write's ledger row rests on: 404 without one, and
    409 while a refresh runs, read under the write lock the caller's transaction holds."""
    latest = snapshot_of(conn, symbol)
    if current_refresh(conn) is not None:
        raise HTTPException(409, REFRESH_RUNNING)
    return latest


def _summary(previous: Moat | None, moat: Moat, why: str | None) -> str:
    """The write's ledger summary: "moat Narrow → Wide", "moat Wide" with no class before it, and
    ": <why>" after either where there is a reason."""
    change = moat if previous is None else f"{previous} → {moat}"
    return f"moat {change}" if why is None else f"moat {change}: {why}"
