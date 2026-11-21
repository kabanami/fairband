"""The moat table in the database: one row a company, the class in force (spec 2026-11-19 8.3,
8.4; ``method.md`` 4.9).

A row is the file's, the owner's or an agent's (``source``). A file row holds the packaged moat
table's entry: its class, its version and the day it was judged, written by the system with no
reason, evidence or class before it. The owner's or an agent's row is a local change: the class in
force before it (``previous``, ``None`` without one), the reason (an agent's required, the
owner's optional), an agent's evidence as ``{kind, ref, note}`` items, the writer, the day of the
write as ``judged_on``, and the snapshot the company's revalue then wrote (``set_snapshot``). The
history of changes is the ledger's: the caller writes the ledger row.

``load_moat_file`` reads the file into the table. It writes a file row for a company the table
lacks, replaces a file row whose class, date or version differs from the file's entry, deletes a
file row whose company the file no longer holds, and never touches the owner's or an agent's row,
whatever the file holds. It reads every row once and writes only the differences, so a load on an
unchanged file writes nothing and every ``at`` stays as it was. ``set_moat`` writes the owner's or
an agent's class; ``file_moat`` returns one company to the file's entry.

Each write is one transaction; it joins the caller's when there is one, so the caller's ledger row
and revalue commit with it.
"""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal, cast

from fairband.policy import Moat
from fairband.policy.moat import MoatEntry, MoatTable
from fairband.store._codec import dump_date, dump_stamp, load_date, load_stamp
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

type MoatSource = Literal["file", "owner", "agent"]

_COLUMNS = (
    "symbol, class, source, file_version, judged_on, previous, reason, evidence, principal,"
    " actor, client, at, snapshot_id"
)
_PUT = f"INSERT OR REPLACE INTO moat_classes ({_COLUMNS}) VALUES ({', '.join('?' * 13)})"


@dataclass(frozen=True)
class MoatRow:
    symbol: str
    moat: Moat
    source: MoatSource
    file_version: str | None
    judged_on: date
    previous: Moat | None
    reason: str | None
    evidence: tuple[dict[str, str], ...] | None
    principal: Principal
    actor: str | None
    client: str | None
    at: datetime
    snapshot_id: int | None


@dataclass(frozen=True)
class Loaded:
    """The file rows a load wrote, replaced and deleted."""

    written: int
    replaced: int
    deleted: int


def moat_row(conn: sqlite3.Connection, symbol: str) -> MoatRow | None:
    """The company's row, or ``None`` when the table holds none."""
    row = conn.execute("SELECT * FROM moat_classes WHERE symbol = ?", (symbol,)).fetchone()
    return None if row is None else _moat_row(row)


def set_moat(
    conn: sqlite3.Connection,
    symbol: str,
    moat: Moat,
    writer: Writer,
    reason: str | None,
    evidence: Sequence[Mapping[str, str]] | None,
    at: datetime,
) -> MoatRow:
    """Write the owner's or an agent's class in place of the company's row, judged on ``at``'s UTC
    day, the class in force before it as ``previous`` and no snapshot; ``ValueError`` for the
    system, whose rows are the file's."""
    if writer.principal == "system":
        raise ValueError("a moat class is the owner's or an agent's: the system writes the file's")
    with transaction(conn, immediate=True):
        held = moat_row(conn, symbol)
        row = MoatRow(
            symbol=symbol,
            moat=moat,
            source=cast(MoatSource, writer.principal),
            file_version=None,
            judged_on=at.astimezone(UTC).date(),
            previous=None if held is None else held.moat,
            reason=reason,
            evidence=None if evidence is None else tuple(dict(item) for item in evidence),
            principal=writer.principal,
            actor=writer.actor,
            client=writer.client,
            at=at,
            snapshot_id=None,
        )
        conn.execute(_PUT, _values(row))
    return row


def file_moat(conn: sqlite3.Connection, symbol: str, table: MoatTable, at: datetime) -> MoatRow:
    """Write the file's row for the company in place of its row; ``KeyError`` where the file holds
    no entry for it."""
    row = _file_row(table.entries[symbol], table.version, at)
    with transaction(conn):
        conn.execute(_PUT, _values(row))
    return row


def set_snapshot(conn: sqlite3.Connection, symbol: str, snapshot_id: int) -> None:
    """Cite the snapshot the company's revalue wrote on its row; ``KeyError`` for no row."""
    with transaction(conn):
        cursor = conn.execute(
            "UPDATE moat_classes SET snapshot_id = ? WHERE symbol = ?", (snapshot_id, symbol)
        )
    if cursor.rowcount != 1:
        raise KeyError(symbol)


def load_moat_file(conn: sqlite3.Connection, table: MoatTable, at: datetime) -> Loaded:
    """Read the file into the table, writing only the file rows that differ from it."""
    with transaction(conn, immediate=True):
        rows = conn.execute(
            "SELECT symbol, source, class, judged_on, file_version FROM moat_classes"
        )
        held = {r[0]: (r[1], (r[2], r[3], r[4])) for r in rows}  # source, the file's three fields
        written: list[MoatRow] = []
        replaced: list[MoatRow] = []
        for symbol, entry in table.entries.items():
            if symbol not in held:
                written.append(_file_row(entry, table.version, at))
                continue
            source, kept = held[symbol]
            if source == "file" and kept != (entry.moat, dump_date(entry.judged), table.version):
                replaced.append(_file_row(entry, table.version, at))
        deleted = [
            s for s, (source, _) in held.items() if source == "file" and s not in table.entries
        ]
        if written or replaced:
            conn.executemany(_PUT, [_values(row) for row in written + replaced])
        if deleted:
            conn.executemany(
                "DELETE FROM moat_classes WHERE symbol = ?", [(symbol,) for symbol in deleted]
            )
    return Loaded(len(written), len(replaced), len(deleted))


def _file_row(entry: MoatEntry, version: str, at: datetime) -> MoatRow:
    return MoatRow(
        symbol=entry.symbol,
        moat=entry.moat,
        source="file",
        file_version=version,
        judged_on=entry.judged,
        previous=None,
        reason=None,
        evidence=None,
        principal="system",
        actor=None,
        client=None,
        at=at,
        snapshot_id=None,
    )


def _values(row: MoatRow) -> tuple[object, ...]:
    return (
        row.symbol,
        row.moat,
        row.source,
        row.file_version,
        dump_date(row.judged_on),
        row.previous,
        row.reason,
        None if row.evidence is None else json.dumps(list(row.evidence)),
        row.principal,
        row.actor,
        row.client,
        dump_stamp(row.at),
        row.snapshot_id,
    )


def _moat_row(row: sqlite3.Row) -> MoatRow:
    evidence = row["evidence"]
    return MoatRow(
        symbol=row["symbol"],
        moat=row["class"],
        source=row["source"],
        file_version=row["file_version"],
        judged_on=load_date(row["judged_on"]),
        previous=row["previous"],
        reason=row["reason"],
        evidence=None if evidence is None else tuple(json.loads(evidence)),
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        at=load_stamp(row["at"]),
        snapshot_id=row["snapshot_id"],
    )
