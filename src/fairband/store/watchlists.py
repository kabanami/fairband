"""The user's watchlists: named lists of symbols, each entry with the time it was added (spec
2026-11-04 9.1 and 9.2).

A name is 1 to 60 characters after trimming, and no two lists share one ignoring case (the
column's ``NOCASE``); a name in use raises ``NameInUse``, a ``ValueError`` naming the list that
holds it. A symbol is kept upper-cased in the exchange form (``BRK.B``,
``fairband.policy.settings.exchange_symbol``), and need not be in the universe: a company may leave
it and stay on a list. A list id that does not exist raises ``KeyError(id)``. Each write is one
transaction, so a refused write changes nothing. Nothing in a valuation reads the lists.
"""

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from fairband.policy.settings import exchange_symbol
from fairband.store._codec import dump_stamp, inserted_id, load_stamp
from fairband.store.db import transaction

NAME_MAX = 60


class NameInUse(ValueError):
    """Another list has the name, ignoring case."""


@dataclass(frozen=True)
class EntryRow:
    symbol: str
    added_at: datetime


@dataclass(frozen=True)
class WatchlistRow:
    """A list with its entries, ordered by symbol."""

    id: int
    name: str
    created_at: datetime
    entries: tuple[EntryRow, ...]


def create_watchlist(conn: sqlite3.Connection, name: str, at: datetime) -> int:
    """Create an empty list named ``name``, trimmed; return its id."""
    name = _name(name)
    with transaction(conn, immediate=True):
        _require_free(conn, name, None)
        cursor = conn.execute(
            "INSERT INTO watchlists (name, created_at) VALUES (?, ?)", (name, dump_stamp(at))
        )
    return inserted_id(cursor)


def rename_watchlist(conn: sqlite3.Connection, watchlist_id: int, name: str) -> None:
    """Name the list ``name``, trimmed; its own name in another case is free."""
    name = _name(name)
    with transaction(conn, immediate=True):
        _require(conn, watchlist_id)
        _require_free(conn, name, watchlist_id)
        conn.execute("UPDATE watchlists SET name = ? WHERE id = ?", (name, watchlist_id))


def delete_watchlist(conn: sqlite3.Connection, watchlist_id: int) -> None:
    """Delete the list and its entries, in one transaction."""
    with transaction(conn, immediate=True):
        _require(conn, watchlist_id)
        conn.execute("DELETE FROM watchlist_entries WHERE watchlist_id = ?", (watchlist_id,))
        conn.execute("DELETE FROM watchlists WHERE id = ?", (watchlist_id,))


def add_symbol(conn: sqlite3.Connection, watchlist_id: int, symbol: str, at: datetime) -> None:
    """Put the symbol on the list, added ``at``; a symbol already on it keeps its first date."""
    symbol = exchange_symbol(symbol)
    with transaction(conn, immediate=True):
        _require(conn, watchlist_id)
        _insert(conn, watchlist_id, symbol, at)


def remove_symbol(conn: sqlite3.Connection, watchlist_id: int, symbol: str) -> None:
    """Take the symbol off the list; a symbol not on it is no change."""
    symbol = exchange_symbol(symbol)
    with transaction(conn, immediate=True):
        _require(conn, watchlist_id)
        conn.execute(
            "DELETE FROM watchlist_entries WHERE watchlist_id = ? AND symbol = ?",
            (watchlist_id, symbol),
        )


def set_memberships(
    conn: sqlite3.Connection, symbol: str, ids: Sequence[int], at: datetime
) -> None:
    """Put the symbol on exactly the lists ``ids``, added ``at`` where it was not on one already:
    a list it stays on keeps its first date. All or none: a missing id changes nothing."""
    symbol = exchange_symbol(symbol)
    wanted = set(ids)
    with transaction(conn, immediate=True):
        for watchlist_id in sorted(wanted):
            _require(conn, watchlist_id)
        rows = conn.execute(
            "SELECT watchlist_id FROM watchlist_entries WHERE symbol = ?", (symbol,)
        )
        held = {int(r["watchlist_id"]) for r in rows}
        for watchlist_id in sorted(held - wanted):
            conn.execute(
                "DELETE FROM watchlist_entries WHERE watchlist_id = ? AND symbol = ?",
                (watchlist_id, symbol),
            )
        for watchlist_id in sorted(wanted - held):
            _insert(conn, watchlist_id, symbol, at)


def get_watchlist(conn: sqlite3.Connection, watchlist_id: int) -> WatchlistRow:
    """The list with its entries."""
    row = conn.execute("SELECT * FROM watchlists WHERE id = ?", (watchlist_id,)).fetchone()
    if row is None:
        raise KeyError(watchlist_id)
    return _watchlist(row, _entries(conn, watchlist_id))


def list_watchlists(conn: sqlite3.Connection) -> list[WatchlistRow]:
    """Every list with its entries, by name ignoring case."""
    entries: dict[int, list[EntryRow]] = {}
    for r in conn.execute("SELECT * FROM watchlist_entries ORDER BY symbol"):
        entries.setdefault(r["watchlist_id"], []).append(_entry(r))
    rows = conn.execute("SELECT * FROM watchlists ORDER BY name COLLATE NOCASE, id")
    return [_watchlist(r, entries.get(r["id"], [])) for r in rows]


def memberships(conn: sqlite3.Connection) -> dict[str, list[int]]:
    """Each symbol on a list, to the ids of its lists in ascending order."""
    found: dict[str, list[int]] = {}
    rows = conn.execute(
        "SELECT symbol, watchlist_id FROM watchlist_entries ORDER BY symbol, watchlist_id"
    )
    for r in rows:
        found.setdefault(r["symbol"], []).append(r["watchlist_id"])
    return found


def _name(name: str) -> str:
    trimmed = name.strip()
    if not 1 <= len(trimmed) <= NAME_MAX:
        raise ValueError(f"a name is 1 to {NAME_MAX} characters")
    return trimmed


def _require(conn: sqlite3.Connection, watchlist_id: int) -> None:
    if conn.execute("SELECT 1 FROM watchlists WHERE id = ?", (watchlist_id,)).fetchone() is None:
        raise KeyError(watchlist_id)


def _require_free(conn: sqlite3.Connection, name: str, own_id: int | None) -> None:
    """``NameInUse`` when a list other than ``own_id`` has the name, ignoring case."""
    row = conn.execute(
        "SELECT name FROM watchlists WHERE name = ? AND id IS NOT ?", (name, own_id)
    ).fetchone()
    if row is not None:
        raise NameInUse(f"a watchlist named '{row['name']}' exists")


def _insert(conn: sqlite3.Connection, watchlist_id: int, symbol: str, at: datetime) -> None:
    conn.execute(
        "INSERT INTO watchlist_entries (watchlist_id, symbol, added_at) VALUES (?, ?, ?)"
        " ON CONFLICT (watchlist_id, symbol) DO NOTHING",
        (watchlist_id, symbol, dump_stamp(at)),
    )


def _entries(conn: sqlite3.Connection, watchlist_id: int) -> list[EntryRow]:
    rows = conn.execute(
        "SELECT * FROM watchlist_entries WHERE watchlist_id = ? ORDER BY symbol", (watchlist_id,)
    )
    return [_entry(r) for r in rows]


def _entry(row: sqlite3.Row) -> EntryRow:
    return EntryRow(symbol=row["symbol"], added_at=load_stamp(row["added_at"]))


def _watchlist(row: sqlite3.Row, entries: list[EntryRow]) -> WatchlistRow:
    return WatchlistRow(
        id=row["id"],
        name=row["name"],
        created_at=load_stamp(row["created_at"]),
        entries=tuple(entries),
    )
