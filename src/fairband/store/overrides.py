"""The overrides: an agent's change to one tagged input, stored with the rule's answer (spec
2026-11-06 Tier 2, 10.1 to 10.3; ``method.md`` 14).

A row keeps the input (its tag, kept as written: a refused tag need not be an input), the engine's
reading of it on the snapshot the override was made on (``old``), the new value and its unit, the
reason, the evidence (``{kind, ref, note}`` items), the lifetime (``lasting``, or ``period-tied``
with its period and the value it corrected), the snapshot, the writer, the time, and the state
``check_override`` gave with its sentence (empty when applied). ``old``, ``new`` and
``corrected_value`` are a number or a word, stored as JSON text so either reads back exactly.
An applied override cites the review its write produced (``set_review``) and is dropped with a
reason and a time (``drop_override``); a row is never deleted. ``applied_overrides`` lists the
company's applied ones by id, the set the engine reads (``as_override``); ``overrides_for`` every
one, newest first.

Each write is one transaction; it joins the caller's when there is one, so the caller's ledger row
and review commit with it.
"""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from fairband.engine.overrides import Lifetime, Override, OverrideTag, State
from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

type Value = float | str


@dataclass(frozen=True)
class OverrideRow:
    id: int
    symbol: str
    tag: str
    old: Value | None
    new: Value
    unit: str
    reason: str
    evidence: tuple[dict[str, Any], ...]
    lifetime: Lifetime
    period: str | None
    corrected_value: Value | None
    snapshot_id: int
    principal: Principal
    actor: str | None
    client: str | None
    at: datetime
    state: State
    message: str
    review_id: int | None
    drop_reason: str | None
    dropped_at: datetime | None


def insert_override(
    conn: sqlite3.Connection,
    symbol: str,
    tag: str,
    old: Value | None,
    new: Value,
    unit: str,
    reason: str,
    evidence: Sequence[Mapping[str, Any]],
    lifetime: Lifetime,
    period: str | None,
    corrected_value: Value | None,
    snapshot_id: int,
    writer: Writer,
    at: datetime,
    state: State,
    message: str,
) -> int:
    """Store the override as ``check_override`` answered it; return its id."""
    row = (
        symbol,
        tag,
        _dump(old),
        json.dumps(new, allow_nan=False),
        unit,
        reason,
        json.dumps([dict(item) for item in evidence]),
        lifetime,
        period,
        _dump(corrected_value),
        snapshot_id,
        writer.principal,
        writer.actor,
        writer.client,
        dump_stamp(at),
        state,
        message,
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO overrides (symbol, tag, old, new, unit, reason, evidence, lifetime,"
            " period, corrected_value, snapshot_id, principal, actor, client, at, state, message)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    return inserted_id(cursor)


def set_review(conn: sqlite3.Connection, override_id: int, review_id: int) -> None:
    """Cite ``review_id`` as the review the override's write produced."""
    with transaction(conn):
        cursor = conn.execute(
            "UPDATE overrides SET review_id = ? WHERE id = ?", (review_id, override_id)
        )
    if cursor.rowcount != 1:
        raise KeyError(override_id)


def drop_override(conn: sqlite3.Connection, override_id: int, reason: str, at: datetime) -> None:
    """Drop the applied override for ``reason`` at ``at``; ``KeyError`` for no such override and
    ``ValueError`` for one that is not applied."""
    with transaction(conn, immediate=True):
        found = override_row(conn, override_id)
        if found is None:
            raise KeyError(override_id)
        if found.state != "applied":
            raise ValueError(f"override {override_id} is {found.state}, not applied")
        conn.execute(
            "UPDATE overrides SET state = 'dropped', drop_reason = ?, dropped_at = ? WHERE id = ?",
            (reason, dump_stamp(at), override_id),
        )


def applied_overrides(conn: sqlite3.Connection, symbol: str) -> list[OverrideRow]:
    """The company's applied overrides, by id."""
    rows = conn.execute(
        "SELECT * FROM overrides WHERE symbol = ? AND state = 'applied' ORDER BY id", (symbol,)
    )
    return [_override(r) for r in rows]


def overrides_for(conn: sqlite3.Connection, symbol: str) -> list[OverrideRow]:
    """Every override of the company, newest first."""
    rows = conn.execute("SELECT * FROM overrides WHERE symbol = ? ORDER BY id DESC", (symbol,))
    return [_override(r) for r in rows]


def override_row(conn: sqlite3.Connection, override_id: int) -> OverrideRow | None:
    row = conn.execute("SELECT * FROM overrides WHERE id = ?", (override_id,)).fetchone()
    return None if row is None else _override(row)


def as_override(row: OverrideRow) -> Override:
    """The applied override as the engine reads it."""
    return Override(
        row.id, cast(OverrideTag, row.tag), row.new, row.principal, row.actor, row.at, row.reason
    )


def _dump(value: Value | None) -> str | None:
    return None if value is None else json.dumps(value, allow_nan=False)


def _load(text: str | None) -> Any:
    return None if text is None else json.loads(text)


def _override(row: sqlite3.Row) -> OverrideRow:
    return OverrideRow(
        id=row["id"],
        symbol=row["symbol"],
        tag=row["tag"],
        old=_load(row["old"]),
        new=json.loads(row["new"]),
        unit=row["unit"],
        reason=row["reason"],
        evidence=tuple(json.loads(row["evidence"])),
        lifetime=row["lifetime"],
        period=row["period"],
        corrected_value=_load(row["corrected_value"]),
        snapshot_id=row["snapshot_id"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        at=load_stamp(row["at"]),
        state=row["state"],
        message=row["message"],
        review_id=row["review_id"],
        drop_reason=row["drop_reason"],
        dropped_at=load_stamp(row["dropped_at"]),
    )
