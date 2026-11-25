"""The published reports and their judgments (spec 2026-11-06 Tier 2, 12 and 13.1; ``method.md``
16).

A report is stored whole once the number check passes, never changed: the company, its revision
(one more than the company's last, from 1), the mode (``valuation review`` or ``full report``),
the stance, the sections as JSON (``[{heading, parts}]``, a part a plain string or ``{cite, ref,
period}``), the full report a valuation review reuses (``None`` for a full report, and for a
review of a company with none), the snapshot, review and secondary valuation it rests on (the
last two ``None`` without one), the work item it completes, the writer and the time. The
appendixes are not stored: ``fairband.reports.render`` generates them from the records at read
time. The company's report is its latest; the earlier revisions stay, read newest first. A read
that needs no text takes a report's head (``report_heads``): what it is, the records it rests on
and its writer, read without its sections.

A judgment is the record of one of a report's input decisions (spec 12): its kind (``phase``,
``moat``, ``belief``, ``roic``, ``target_margin``), the decision in words, and the company's
override it produced, if one. The debate about the business is the report's own section, not the
judgment's. Each write is one transaction; it joins the caller's when there is one, so the
caller's ledger rows commit with it. A judgment's override that is not the company's raises
``KeyError(id)``.
"""

import json
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, get_args

from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction
from fairband.store.inbox import Mode
from fairband.store.ledger import Principal, Writer

JudgmentKind = Literal["phase", "moat", "belief", "roic", "target_margin"]
JUDGMENT_KINDS: tuple[JudgmentKind, ...] = get_args(JudgmentKind)


@dataclass(frozen=True)
class ReportRow:
    id: int
    symbol: str
    revision: int
    mode: Mode
    stance: str
    sections: tuple[dict[str, Any], ...]
    reuses_full_report_of: int | None
    snapshot_id: int
    review_id: int | None
    secondary_id: int | None
    work_item_id: int | None
    principal: Principal
    actor: str | None
    client: str | None
    created_at: datetime


@dataclass(frozen=True)
class ReportHead:
    """A report without its text: what it is, the records it rests on and its writer."""

    id: int
    symbol: str
    revision: int
    mode: Mode
    stance: str
    snapshot_id: int
    review_id: int | None
    secondary_id: int | None
    principal: Principal
    actor: str | None


@dataclass(frozen=True)
class JudgmentRow:
    id: int
    report_id: int
    symbol: str
    judgment: JudgmentKind
    decision: str
    override_id: int | None


def insert_report(
    conn: sqlite3.Connection,
    symbol: str,
    mode: Mode,
    stance: str,
    sections: Sequence[Mapping[str, Any]],
    reuses_full_report_of: int | None,
    snapshot_id: int,
    review_id: int | None,
    secondary_id: int | None,
    work_item_id: int | None,
    writer: Writer,
    at: datetime,
) -> int:
    """Store the report as the company's next revision; return its id."""
    with transaction(conn, immediate=True):
        last = conn.execute(
            "SELECT MAX(revision) FROM reports WHERE symbol = ?", (symbol,)
        ).fetchone()[0]
        cursor = conn.execute(
            "INSERT INTO reports (symbol, revision, mode, stance, sections, reuses_full_report_of,"
            " snapshot_id, review_id, secondary_id, work_item_id, principal, actor, client,"
            " created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                symbol,
                1 if last is None else last + 1,
                mode,
                stance,
                json.dumps([dict(s) for s in sections], allow_nan=False),
                reuses_full_report_of,
                snapshot_id,
                review_id,
                secondary_id,
                work_item_id,
                writer.principal,
                writer.actor,
                writer.client,
                dump_stamp(at),
            ),
        )
        return inserted_id(cursor)


def report_row(conn: sqlite3.Connection, report_id: int) -> ReportRow | None:
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    return None if row is None else _report(row)


def latest_report(conn: sqlite3.Connection, symbol: str) -> ReportRow | None:
    """The company's report: its latest revision, if it has one."""
    row = conn.execute(
        "SELECT * FROM reports WHERE symbol = ? ORDER BY revision DESC LIMIT 1", (symbol,)
    ).fetchone()
    return None if row is None else _report(row)


def reports_for(conn: sqlite3.Connection, symbol: str) -> list[ReportRow]:
    """Every revision of the company's report, newest first."""
    rows = conn.execute("SELECT * FROM reports WHERE symbol = ? ORDER BY revision DESC", (symbol,))
    return [_report(r) for r in rows]


def latest_reports(conn: sqlite3.Connection) -> dict[str, ReportRow]:
    """The report of every company that has one, by symbol."""
    rows = conn.execute(
        "SELECT * FROM reports WHERE id IN (SELECT MAX(id) FROM reports GROUP BY symbol)"
        " ORDER BY symbol"
    )
    return {r["symbol"]: _report(r) for r in rows}


def revisions_by_id(conn: sqlite3.Connection, ids: Iterable[int]) -> dict[int, int]:
    """The revision of each of the reports ``ids``, by id, in one query; an id with no report is
    left out, and no ids read nothing."""
    wanted = tuple(ids)
    if not wanted:
        return {}
    marks = ", ".join("?" * len(wanted))
    rows = conn.execute(f"SELECT id, revision FROM reports WHERE id IN ({marks})", wanted)
    return {r["id"]: r["revision"] for r in rows}


def report_heads(conn: sqlite3.Connection, ids: Iterable[int]) -> dict[int, ReportHead]:
    """The head of each of the reports ``ids``, by id, in one query that does not read their
    sections; an id with no report is left out, and no ids read nothing."""
    wanted = tuple(ids)
    if not wanted:
        return {}
    marks = ", ".join("?" * len(wanted))
    rows = conn.execute(
        "SELECT id, symbol, revision, mode, stance, snapshot_id, review_id, secondary_id,"
        f" principal, actor FROM reports WHERE id IN ({marks})",
        wanted,
    )
    return {r["id"]: _head(r) for r in rows}


def insert_judgments(
    conn: sqlite3.Connection,
    report_id: int,
    symbol: str,
    judgments: Sequence[Mapping[str, Any]],
) -> list[int]:
    """Store the report's judgments, each ``{judgment, decision, override_id}``, in order; return
    their ids."""
    ids = []
    with transaction(conn, immediate=True):
        for j in judgments:
            override_id = j.get("override_id")
            if override_id is not None and not _has_override(conn, override_id, symbol):
                raise KeyError(override_id)
            cursor = conn.execute(
                "INSERT INTO judgments (report_id, symbol, judgment, decision, override_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (report_id, symbol, j["judgment"], j["decision"], override_id),
            )
            ids.append(inserted_id(cursor))
    return ids


def judgments_for(conn: sqlite3.Connection, report_id: int) -> list[JudgmentRow]:
    """The report's judgments, in the order they were given."""
    rows = conn.execute("SELECT * FROM judgments WHERE report_id = ? ORDER BY id", (report_id,))
    return [_judgment(r) for r in rows]


def latest_judgments(conn: sqlite3.Connection, symbol: str) -> list[JudgmentRow]:
    """The judgments of the company's report; none without one."""
    report = latest_report(conn, symbol)
    return [] if report is None else judgments_for(conn, report.id)


def _has_override(conn: sqlite3.Connection, override_id: int, symbol: str) -> bool:
    found = conn.execute(
        "SELECT 1 FROM overrides WHERE id = ? AND symbol = ?", (override_id, symbol)
    ).fetchone()
    return found is not None


def _report(row: sqlite3.Row) -> ReportRow:
    return ReportRow(
        id=row["id"],
        symbol=row["symbol"],
        revision=row["revision"],
        mode=row["mode"],
        stance=row["stance"],
        sections=tuple(json.loads(row["sections"])),
        reuses_full_report_of=row["reuses_full_report_of"],
        snapshot_id=row["snapshot_id"],
        review_id=row["review_id"],
        secondary_id=row["secondary_id"],
        work_item_id=row["work_item_id"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        created_at=load_stamp(row["created_at"]),
    )


def _head(row: sqlite3.Row) -> ReportHead:
    return ReportHead(
        id=row["id"],
        symbol=row["symbol"],
        revision=row["revision"],
        mode=row["mode"],
        stance=row["stance"],
        snapshot_id=row["snapshot_id"],
        review_id=row["review_id"],
        secondary_id=row["secondary_id"],
        principal=row["principal"],
        actor=row["actor"],
    )


def _judgment(row: sqlite3.Row) -> JudgmentRow:
    return JudgmentRow(
        id=row["id"],
        report_id=row["report_id"],
        symbol=row["symbol"],
        judgment=row["judgment"],
        decision=row["decision"],
        override_id=row["override_id"],
    )
