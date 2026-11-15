"""The agent routes (spec 2026-11-06 Tier 2, sections 7 to 9 and 16): the work inbox, the research
records and the ledger.

``GET /api/inbox`` runs the expiry rule first (``fairband.store.inbox.post_expiry_items``), as the
system's write, then lists the items newest first, or those in ``state``, each with
``reportRevision``, the revision of the report a done item was completed with (``None`` without a
report or its row; 18.5, plan 4). ``POST /api/inbox`` posts an item for the company, its origin
the writer's principal and its snapshot the company's latest. ``POST /api/inbox/claim`` claims
the named item, or the oldest pending one, for the agent; ``PATCH /api/inbox/{id}`` completes it
with a published report of its company, or declines it with a reason. Each company's notes,
findings, kill criteria and news items are read and written under ``/api/companies/{symbol}/``;
a finding may name the currency of its money figure, and answers the one it is in
(``money_json``; spec 2026-11-15 9.1). ``PATCH /api/kill-criteria/{id}`` moves a criterion's
state with a reason. ``/api/ledger`` and ``/api/companies/{symbol}/ledger`` read the ledger newest
first.

Every write names its writer by the identity headers (``fairband.web.identity``) and is a ledger
row, written in the same transaction as the record: the writer, the kind of write, the company,
the record by table and id, the company's latest snapshot (``None`` without one) and, for a work
item's write, the item. A write answers with the record as it now is (a create with 201), its keys
camelCase. The refusals follow ``watchlists_api``: a bad value is a 400, a missing record a 404,
and a second open item for a company or a state the item cannot move from a 409, each with the
sentence the writer can act on.
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import fields
from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from fairband.policy.settings import exchange_symbol
from fairband.store.currency import currency_of, reporting_currency
from fairband.store.db import transaction
from fairband.store.guidance import GuidanceRow
from fairband.store.inbox import (
    ItemOpen,
    Mode,
    Origin,
    State,
    WorkItem,
    WrongState,
    claim_item,
    complete_item,
    decline_item,
    oldest_pending,
    post_expiry_items,
    post_item,
    work_item,
    work_items,
)
from fairband.store.ledger import SYSTEM, Writer, entries, record
from fairband.store.reports import report_row, revisions_by_id
from fairband.store.research import (
    CriterionState,
    FindingRow,
    KillCriterionRow,
    SourceKind,
    Unit,
    add_finding,
    add_kill_criterion,
    add_news_item,
    add_note,
    finding_row,
    findings_for,
    kill_criteria_for,
    kill_criterion_row,
    news_item_row,
    news_items_for,
    note_row,
    notes_for,
    set_kill_criterion,
)
from fairband.store.snapshots import latest_snapshot
from fairband.web.identity import writer_of

_GIST = 80  # the longest summary taken from a record's text

WriterOf = Annotated[Writer, Depends(writer_of)]


class _Body(BaseModel):
    """A request body, its keys camelCase."""

    model_config = ConfigDict(alias_generator=to_camel)


class InboxPost(_Body):
    symbol: str
    mode: Mode
    note: str = ""


class InboxClaim(_Body):
    item_id: int | None = None


class InboxMove(_Body):
    action: Literal["complete", "decline"]
    report_id: int | None = None
    reason: str | None = None


class NotePost(_Body):
    text: str
    override_id: int | None = None


class Source(_Body):
    kind: SourceKind
    ref: str
    note: str | None = None


class FindingPost(_Body):
    as_of: date
    text: str
    source: Source
    value: float | None = None
    unit: Unit | None = None
    period: str | None = None
    currency: str | None = None


class KillCriterionPost(_Body):
    text: str


class KillCriterionMove(_Body):
    state: CriterionState
    reason: str


class NewsItemPost(_Body):
    day: date = Field(alias="date")
    headline: str
    source: str
    text: str
    kill_criterion_id: int | None = None


def record_json(row: Any) -> dict[str, Any]:
    """A store row as the API sends it: each field under its camelCase name, a date or a time as
    ISO text."""
    return {to_camel(f.name): _plain(getattr(row, f.name)) for f in fields(row)}


def money_json(row: FindingRow | GuidanceRow, unit: str | None, reporting: str) -> dict[str, Any]:
    """A finding or a guidance record whose figure is of ``unit`` as the API sends it
    (``record_json``), its ``currency`` the one that figure is in (``store.currency.currency_of``):
    the stored code, else ``reporting``, the company's reporting currency
    (``store.currency.reporting_currency``); ``None`` for a figure that is not money (spec
    2026-11-15 9.1). Every answer of either record reads its currency here."""
    return record_json(row) | {"currency": currency_of(row.currency, unit, reporting)}


def finding_json(finding: FindingRow, reporting: str) -> dict[str, Any]:
    """A finding, its source as one ``{kind, ref, note}``, as it was written, and the currency of
    its money in the company's ``reporting`` currency (``money_json``)."""
    plain = money_json(finding, finding.unit, reporting)
    source = {key: plain.pop(f"source{key.title()}") for key in ("kind", "ref", "note")}
    return plain | {"source": source}


@contextmanager
def _refusals(missing: str, symbol: str | None = None) -> Iterator[None]:
    """The store's refusals as answers: a second open item or a state the record cannot move from
    409, a bad value 400, a missing ``missing`` 404, named as the company's when the record cites
    it for ``symbol``."""
    try:
        yield
    except (ItemOpen, WrongState) as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    except KeyError as exc:
        company = "" if symbol is None else f" for {exchange_symbol(symbol)}"
        raise HTTPException(404, f"no {missing} {exc.args[0]}{company}") from None


def add_agent_routes(
    app: FastAPI, conn_factory: Callable[[], sqlite3.Connection], clock: Callable[[], datetime]
) -> None:
    """Register the agent routes."""

    @app.get("/api/inbox")
    def inbox(state: State | None = None) -> dict[str, Any]:
        """The items, newest first, after the expiry rule has run on the clock's day; the done
        items' report revisions read in one query."""
        at = clock()
        with closing(conn_factory()) as conn:
            with transaction(conn, immediate=True):
                posted, dropped = post_expiry_items(conn, at.date(), at)
                for item_id in posted:
                    _record_post(conn, SYSTEM, at, work_item(conn, item_id))
                for item_id in dropped:
                    item = work_item(conn, item_id)
                    summary = f"dropped: {item.symbol} is on no watchlist"
                    _record_item(conn, SYSTEM, at, "drop", item, summary)
            items = work_items(conn, state)
            found = revisions_by_id(conn, [i.report_id for i in items if i.report_id is not None])
            return {
                "items": [
                    record_json(i)
                    | {"reportRevision": None if i.report_id is None else found.get(i.report_id)}
                    for i in items
                ]
            }

    @app.post("/api/inbox", status_code=201)
    def post(body: InboxPost, writer: WriterOf) -> dict[str, Any]:
        at = clock()
        origin: Origin = "agent" if writer.principal == "agent" else "owner"
        with (
            closing(conn_factory()) as conn,
            _refusals("work item"),
            transaction(conn, immediate=True),
        ):
            symbol = exchange_symbol(body.symbol)
            snapshot = latest_snapshot(conn, symbol)
            snapshot_id = None if snapshot is None else snapshot.id
            item_id = post_item(conn, symbol, body.mode, body.note, snapshot_id, origin, writer, at)
            item = work_item(conn, item_id)
            _record_post(conn, writer, at, item)
            return record_json(item)

    @app.post("/api/inbox/claim")
    def claim(body: InboxClaim, writer: WriterOf) -> dict[str, Any]:
        """Claim the named item, or the oldest pending one, for the agent; naming a claimed item
        takes it over."""
        if writer.actor is None:  # the owner's: only an agent claims
            raise HTTPException(400, "a claim is an agent's write")
        at = clock()
        with (
            closing(conn_factory()) as conn,
            _refusals("work item"),
            transaction(conn, immediate=True),
        ):
            named = body.item_id
            before = oldest_pending(conn) if named is None else work_item(conn, named)
            if before is None:
                raise HTTPException(404, "no pending work item")
            item = claim_item(conn, before.id, writer.actor, at)
            summary = f"claimed by {item.claimed_by}"
            if before.state == "claimed" and before.claimed_by != item.claimed_by:
                summary += f", taken over from {before.claimed_by}"
            _record_item(conn, writer, at, "claim", item, summary)
            return record_json(item)

    @app.patch("/api/inbox/{item_id}")
    def move(item_id: int, body: InboxMove, writer: WriterOf) -> dict[str, Any]:
        """Complete the open item with a published report of its company, or decline it."""
        at = clock()
        with (
            closing(conn_factory()) as conn,
            _refusals("work item"),
            transaction(conn, immediate=True),
        ):
            if body.action == "complete":
                if body.report_id is None:
                    raise ValueError("a complete needs a report id")
                _require_report(conn, body.report_id, work_item(conn, item_id).symbol)
                item = complete_item(conn, item_id, body.report_id, at)
                summary = f"completed with report {body.report_id}"
            else:
                item = decline_item(conn, item_id, body.reason or "", at)
                summary = f"declined: {gist(body.reason or '')}"
            _record_item(conn, writer, at, body.action, item, summary)
            return record_json(item)

    @app.get("/api/companies/{symbol}/notes")
    def notes(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn, _refusals("note"):
            return {"notes": [record_json(n) for n in notes_for(conn, symbol)]}

    @app.post("/api/companies/{symbol}/notes", status_code=201)
    def post_note(symbol: str, body: NotePost, writer: WriterOf) -> dict[str, Any]:
        at = clock()
        with (
            closing(conn_factory()) as conn,
            _refusals("override", symbol),
            transaction(conn, immediate=True),
        ):
            note = note_row(conn, add_note(conn, symbol, body.text, writer, at, body.override_id))
            assert note is not None  # written in this transaction
            _record(conn, writer, at, "note", note.symbol, "notes", note.id, gist(note.text))
            return record_json(note)

    @app.get("/api/companies/{symbol}/findings")
    def findings(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn, _refusals("finding"):
            found = findings_for(conn, symbol)
            reporting = reporting_currency(conn, symbol)
            return {"findings": [finding_json(f, reporting) for f in found]}

    @app.post("/api/companies/{symbol}/findings", status_code=201)
    def post_finding(symbol: str, body: FindingPost, writer: WriterOf) -> dict[str, Any]:
        at = clock()
        source = body.source.model_dump()
        with (
            closing(conn_factory()) as conn,
            _refusals("finding"),
            transaction(conn, immediate=True),
        ):
            finding_id = add_finding(
                conn,
                symbol,
                body.as_of,
                body.text,
                source,
                writer,
                at,
                value=body.value,
                unit=body.unit,
                period=body.period,
                currency=body.currency,
            )
            finding = finding_row(conn, finding_id)
            assert finding is not None  # written in this transaction
            summary = gist(finding.text)
            _record(conn, writer, at, "finding", finding.symbol, "findings", finding.id, summary)
            return finding_json(finding, reporting_currency(conn, finding.symbol))

    @app.get("/api/companies/{symbol}/kill-criteria")
    def kill_criteria(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn, _refusals("kill criterion"):
            return {"killCriteria": [record_json(k) for k in kill_criteria_for(conn, symbol)]}

    @app.post("/api/companies/{symbol}/kill-criteria", status_code=201)
    def post_kill_criterion(
        symbol: str, body: KillCriterionPost, writer: WriterOf
    ) -> dict[str, Any]:
        at = clock()
        with (
            closing(conn_factory()) as conn,
            _refusals("kill criterion"),
            transaction(conn, immediate=True),
        ):
            criterion_id = add_kill_criterion(conn, symbol, body.text, writer, at)
            criterion = kill_criterion_row(conn, criterion_id)
            assert criterion is not None  # written in this transaction
            _record_criterion(conn, writer, at, criterion, gist(criterion.text))
            return record_json(criterion)

    @app.patch("/api/kill-criteria/{criterion_id}")
    def move_kill_criterion(
        criterion_id: int, body: KillCriterionMove, writer: WriterOf
    ) -> dict[str, Any]:
        """Move the criterion to ``state`` for ``reason``."""
        at = clock()
        with (
            closing(conn_factory()) as conn,
            _refusals("kill criterion"),
            transaction(conn, immediate=True),
        ):
            criterion = set_kill_criterion(conn, criterion_id, body.state, body.reason, at)
            summary = f"{criterion.state}: {gist(body.reason)}"
            _record_criterion(conn, writer, at, criterion, summary)
            return record_json(criterion)

    @app.get("/api/companies/{symbol}/news-items")
    def news_items(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn, _refusals("news item"):
            return {"newsItems": [record_json(n) for n in news_items_for(conn, symbol)]}

    @app.post("/api/companies/{symbol}/news-items", status_code=201)
    def post_news_item(symbol: str, body: NewsItemPost, writer: WriterOf) -> dict[str, Any]:
        """Record the news item; a kill criterion it names must be the company's."""
        at = clock()
        with (
            closing(conn_factory()) as conn,
            _refusals("kill criterion", symbol),
            transaction(conn, immediate=True),
        ):
            item_id = add_news_item(
                conn,
                symbol,
                body.day,
                body.headline,
                body.source,
                body.text,
                writer,
                at,
                body.kill_criterion_id,
            )
            item = news_item_row(conn, item_id)
            assert item is not None  # written in this transaction
            summary = gist(item.headline)
            _record(conn, writer, at, "news-item", item.symbol, "news_items", item.id, summary)
            return record_json(item)

    @app.get("/api/ledger")
    def ledger(
        symbol: str | None = None, limit: Annotated[int, Query(ge=1)] = 100
    ) -> dict[str, Any]:
        """The newest ``limit`` ledger rows, newest first: the company's, or every one."""
        with closing(conn_factory()) as conn, _refusals("ledger row"):
            company = None if symbol is None else exchange_symbol(symbol)
            return {"entries": [record_json(e) for e in entries(conn, company, limit)]}

    @app.get("/api/companies/{symbol}/ledger")
    def company_ledger(symbol: str, limit: Annotated[int, Query(ge=1)] = 100) -> dict[str, Any]:
        """The company's newest ``limit`` ledger rows, newest first."""
        return ledger(symbol, limit)


def _require_report(conn: sqlite3.Connection, report_id: int, symbol: str) -> None:
    """A complete names a published report of the item's company: 404 for any other."""
    found = report_row(conn, report_id)
    if found is None or found.symbol != symbol:
        raise HTTPException(404, f"no report {report_id} for {symbol}")


def _record_post(conn: sqlite3.Connection, writer: Writer, at: datetime, item: WorkItem) -> None:
    summary = f"{item.mode} posted" + (f": {gist(item.note)}" if item.note.strip() else "")
    _record_item(conn, writer, at, "work-item", item, summary)


def _record_item(
    conn: sqlite3.Connection,
    writer: Writer,
    at: datetime,
    kind: str,
    item: WorkItem,
    summary: str,
) -> None:
    """The ledger row of a write to the work item, which it also rests on."""
    _record(conn, writer, at, kind, item.symbol, "work_items", item.id, summary, item.id)


def _record_criterion(
    conn: sqlite3.Connection,
    writer: Writer,
    at: datetime,
    criterion: KillCriterionRow,
    summary: str,
) -> None:
    """The ledger row of a write to the kill criterion."""
    table = "kill_criteria"
    _record(conn, writer, at, "kill-criterion", criterion.symbol, table, criterion.id, summary)


def _record(
    conn: sqlite3.Connection,
    writer: Writer,
    at: datetime,
    kind: str,
    symbol: str,
    ref_table: str,
    ref_id: int,
    summary: str,
    work_item_id: int | None = None,
) -> None:
    """The write's ledger row, resting on the company's latest snapshot, in the caller's
    transaction."""
    snapshot = latest_snapshot(conn, symbol)
    record(
        conn,
        writer,
        at,
        kind,
        symbol,
        ref_table,
        ref_id,
        snapshot_id=None if snapshot is None else snapshot.id,
        work_item_id=work_item_id,
        summary=summary,
    )


def gist(text: str) -> str:
    """The text's first line, cut to ``_GIST`` characters, for a ledger summary."""
    lines = text.strip().splitlines()
    line = lines[0] if lines else ""
    return line if len(line) <= _GIST else line[: _GIST - 1] + "…"


def _plain(value: Any) -> Any:
    """A date or a time as ISO text; anything else as it is."""
    return value.isoformat() if isinstance(value, date) else value
