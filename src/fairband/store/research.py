"""The research records an owner or an agent writes on a company: notes, findings, kill criteria and
news items (spec 2026-11-06 Tier 2, section 9).

Each names its writer (the principal, and an agent's model identifier and client) and the time it
was written, and each list reads newest first. A symbol is kept upper-cased in the exchange form,
and need not have a snapshot. Text is kept as written; a blank one is refused.

- A note: text, and the override whose provenance it carries, if any.
- A finding: a dated, sourced fact. ``as_of`` is the date the fact describes; the source is
  ``{kind, ref, note}`` with kind one of ``SOURCE_KINDS`` and a ref; a value comes with its unit
  (one of ``UNITS``), and a period (a fiscal year, a quarter, ``ttm``) may name what it covers.
- A kill criterion: a measurable event that would prove the view wrong, the report that set it,
  and a state, ``open`` until ``set_kill_criterion`` moves it with a reason.
- A news item: a date, a headline, a source (a URL or a vendor response id), text, and the
  company's kill criterion it touches, if any.

A refused value raises ``ValueError`` with the sentence the writer can act on; a cited record
that is not the company's, a note's override or a news item's kill criterion, ``KeyError(id)``. Each write is
one transaction; it joins the caller's when there is one, so the caller's ledger row commits with
it.
"""

import math
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, get_args

from fairband.policy.settings import exchange_symbol
from fairband.store._codec import (
    dump_date,
    dump_float,
    dump_stamp,
    inserted_id,
    load_date,
    load_float,
    load_stamp,
)
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

SourceKind = Literal["filing", "transcript", "url", "vendor", "base-rate"]
Unit = Literal["currency", "percent", "multiple", "count", "per-share", "score", "years"]
CriterionState = Literal["open", "triggered", "retired"]

SOURCE_KINDS: tuple[SourceKind, ...] = get_args(SourceKind)
UNITS: tuple[Unit, ...] = get_args(Unit)
CRITERION_STATES: tuple[CriterionState, ...] = get_args(CriterionState)


@dataclass(frozen=True)
class NoteRow:
    id: int
    symbol: str
    text: str
    principal: Principal
    actor: str | None
    client: str | None
    at: datetime
    override_id: int | None


@dataclass(frozen=True)
class FindingRow:
    id: int
    symbol: str
    as_of: date
    text: str
    source_kind: SourceKind
    source_ref: str
    source_note: str | None
    value: float | None
    unit: Unit | None
    period: str | None
    principal: Principal
    actor: str | None
    client: str | None
    at: datetime


@dataclass(frozen=True)
class KillCriterionRow:
    id: int
    symbol: str
    text: str
    state: CriterionState
    report_id: int | None
    principal: Principal
    actor: str | None
    client: str | None
    at: datetime
    state_reason: str | None
    state_at: datetime | None


@dataclass(frozen=True)
class NewsItemRow:
    id: int
    symbol: str
    date: date
    headline: str
    source: str
    text: str
    kill_criterion_id: int | None
    principal: Principal
    actor: str | None
    client: str | None
    at: datetime


def add_note(
    conn: sqlite3.Connection,
    symbol: str,
    text: str,
    writer: Writer,
    at: datetime,
    override_id: int | None = None,
) -> int:
    """Write the note, carrying the company's override ``override_id`` if one; return its id."""
    symbol = exchange_symbol(symbol)
    _require_text(text, "a note needs text")
    fields = {"symbol": symbol, "text": text, "override_id": override_id}
    with transaction(conn, immediate=True):
        if override_id is not None and not _has_override(conn, override_id, symbol):
            raise KeyError(override_id)
        return _insert(conn, "notes", fields, writer, at)


def note_row(conn: sqlite3.Connection, note_id: int) -> NoteRow | None:
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    return None if row is None else _note(row)


def notes_for(conn: sqlite3.Connection, symbol: str) -> list[NoteRow]:
    return [_note(r) for r in _rows(conn, "notes", symbol)]


def add_finding(
    conn: sqlite3.Connection,
    symbol: str,
    as_of: date,
    text: str,
    source: Mapping[str, str | None],
    writer: Writer,
    at: datetime,
    *,
    value: float | None = None,
    unit: Unit | None = None,
    period: str | None = None,
) -> int:
    """Record the finding, sourced by ``source`` (``{kind, ref, note}``); return its id."""
    symbol = exchange_symbol(symbol)
    _require_text(text, "a finding needs text")
    kind, ref = source.get("kind"), source.get("ref")
    if kind not in SOURCE_KINDS:
        raise ValueError(f"a source kind is one of {', '.join(SOURCE_KINDS)}, not {kind!r}")
    if ref is None or not ref.strip():
        raise ValueError("a finding's source needs a ref")
    if (value is None) != (unit is None):
        raise ValueError("a finding's value and unit come together")
    if unit is not None and unit not in UNITS:
        raise ValueError(f"a unit is one of {', '.join(UNITS)}, not {unit!r}")
    if value is not None and not math.isfinite(value):
        raise ValueError("a finding's value is a finite number")
    fields = {
        "symbol": symbol,
        "as_of": dump_date(as_of),
        "text": text,
        "source_kind": kind,
        "source_ref": ref,
        "source_note": source.get("note"),
        "value": dump_float(value),
        "unit": unit,
        "period": period,
    }
    return _insert(conn, "findings", fields, writer, at)


def finding_row(conn: sqlite3.Connection, finding_id: int) -> FindingRow | None:
    row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    return None if row is None else _finding(row)


def findings_for(conn: sqlite3.Connection, symbol: str) -> list[FindingRow]:
    return [_finding(r) for r in _rows(conn, "findings", symbol)]


def add_kill_criterion(
    conn: sqlite3.Connection,
    symbol: str,
    text: str,
    writer: Writer,
    at: datetime,
    report_id: int | None = None,
) -> int:
    """Set an open kill criterion, by the report ``report_id`` if one set it; return its id."""
    symbol = exchange_symbol(symbol)
    _require_text(text, "a kill criterion needs text")
    fields = {"symbol": symbol, "text": text, "state": "open", "report_id": report_id}
    return _insert(conn, "kill_criteria", fields, writer, at)


def set_kill_criterion(
    conn: sqlite3.Connection,
    criterion_id: int,
    state: CriterionState,
    reason: str,
    at: datetime,
) -> KillCriterionRow:
    """Move the criterion to ``state`` for ``reason``, kept as written; the criterion as it now
    is."""
    if state not in CRITERION_STATES:
        raise ValueError(f"a kill criterion's state is open, triggered or retired, not {state!r}")
    _require_text(reason, "a state change needs a reason")
    with transaction(conn, immediate=True):
        if _require_criterion(conn, criterion_id).state == state:
            raise ValueError(f"kill criterion {criterion_id} is already {state}")
        conn.execute(
            "UPDATE kill_criteria SET state = ?, state_reason = ?, state_at = ? WHERE id = ?",
            (state, reason, dump_stamp(at), criterion_id),
        )
        return _require_criterion(conn, criterion_id)


def kill_criterion_row(conn: sqlite3.Connection, criterion_id: int) -> KillCriterionRow | None:
    row = conn.execute("SELECT * FROM kill_criteria WHERE id = ?", (criterion_id,)).fetchone()
    return None if row is None else _kill_criterion(row)


def kill_criteria_for(conn: sqlite3.Connection, symbol: str) -> list[KillCriterionRow]:
    return [_kill_criterion(r) for r in _rows(conn, "kill_criteria", symbol)]


def add_news_item(
    conn: sqlite3.Connection,
    symbol: str,
    day: date,
    headline: str,
    source: str,
    text: str,
    writer: Writer,
    at: datetime,
    kill_criterion_id: int | None = None,
) -> int:
    """Record the news item, dated ``day``, touching the company's kill criterion
    ``kill_criterion_id`` if one; return its id."""
    symbol = exchange_symbol(symbol)
    for field, given in (("headline", headline), ("source", source), ("text", text)):
        _require_text(given, f"a news item needs its {field}")
    fields = {
        "symbol": symbol,
        "date": dump_date(day),
        "headline": headline,
        "source": source,
        "text": text,
        "kill_criterion_id": kill_criterion_id,
    }
    with transaction(conn, immediate=True):
        cited = None if kill_criterion_id is None else _require_criterion(conn, kill_criterion_id)
        if cited is not None and cited.symbol != symbol:
            raise KeyError(kill_criterion_id)
        return _insert(conn, "news_items", fields, writer, at)


def news_item_row(conn: sqlite3.Connection, item_id: int) -> NewsItemRow | None:
    row = conn.execute("SELECT * FROM news_items WHERE id = ?", (item_id,)).fetchone()
    return None if row is None else _news_item(row)


def news_items_for(conn: sqlite3.Connection, symbol: str) -> list[NewsItemRow]:
    return [_news_item(r) for r in _rows(conn, "news_items", symbol)]


def _require_text(text: str, refusal: str) -> None:
    if not text.strip():
        raise ValueError(refusal)


def _has_override(conn: sqlite3.Connection, override_id: int, symbol: str) -> bool:
    found = conn.execute(
        "SELECT 1 FROM overrides WHERE id = ? AND symbol = ?", (override_id, symbol)
    ).fetchone()
    return found is not None


def _require_criterion(conn: sqlite3.Connection, criterion_id: int) -> KillCriterionRow:
    found = kill_criterion_row(conn, criterion_id)
    if found is None:
        raise KeyError(criterion_id)
    return found


def _insert(
    conn: sqlite3.Connection,
    table: str,
    fields: Mapping[str, str | int | None],
    writer: Writer,
    at: datetime,
) -> int:
    """Insert the record's ``fields`` with its writer and time; its id."""
    row = {
        **fields,
        "principal": writer.principal,
        "actor": writer.actor,
        "client": writer.client,
        "at": dump_stamp(at),
    }
    columns = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with transaction(conn, immediate=True):
        cursor = conn.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({marks})", tuple(row.values())
        )
    return inserted_id(cursor)


def _rows(conn: sqlite3.Connection, table: str, symbol: str) -> list[sqlite3.Row]:
    """The company's rows of ``table``, newest first."""
    return conn.execute(
        f"SELECT * FROM {table} WHERE symbol = ? ORDER BY id DESC", (exchange_symbol(symbol),)
    ).fetchall()


def _note(row: sqlite3.Row) -> NoteRow:
    return NoteRow(
        id=row["id"],
        symbol=row["symbol"],
        text=row["text"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        at=load_stamp(row["at"]),
        override_id=row["override_id"],
    )


def _finding(row: sqlite3.Row) -> FindingRow:
    return FindingRow(
        id=row["id"],
        symbol=row["symbol"],
        as_of=load_date(row["as_of"]),
        text=row["text"],
        source_kind=row["source_kind"],
        source_ref=row["source_ref"],
        source_note=row["source_note"],
        value=load_float(row["value"]),
        unit=row["unit"],
        period=row["period"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        at=load_stamp(row["at"]),
    )


def _kill_criterion(row: sqlite3.Row) -> KillCriterionRow:
    return KillCriterionRow(
        id=row["id"],
        symbol=row["symbol"],
        text=row["text"],
        state=row["state"],
        report_id=row["report_id"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        at=load_stamp(row["at"]),
        state_reason=row["state_reason"],
        state_at=load_stamp(row["state_at"]),
    )


def _news_item(row: sqlite3.Row) -> NewsItemRow:
    return NewsItemRow(
        id=row["id"],
        symbol=row["symbol"],
        date=load_date(row["date"]),
        headline=row["headline"],
        source=row["source"],
        text=row["text"],
        kill_criterion_id=row["kill_criterion_id"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        at=load_stamp(row["at"]),
    )
