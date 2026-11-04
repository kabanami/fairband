"""The watchlists: named lists of symbols, each entry with the time it was added (spec 2026-11-04
9.2)."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fairband.store.watchlists import (
    EntryRow,
    NameInUse,
    WatchlistRow,
    add_symbol,
    create_watchlist,
    delete_watchlist,
    get_watchlist,
    list_watchlists,
    memberships,
    remove_symbol,
    rename_watchlist,
    set_memberships,
)

AT = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)
LATER = AT + timedelta(hours=1)


def test_create_and_list_by_name_ignoring_case(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "  Core  ", AT)
    banks = create_watchlist(conn, "banks", LATER)
    assert not conn.in_transaction
    assert list_watchlists(conn) == [
        WatchlistRow(id=banks, name="banks", created_at=LATER, entries=()),
        WatchlistRow(id=core, name="Core", created_at=AT, entries=()),  # the name trimmed
    ]
    assert get_watchlist(conn, core).name == "Core"


def test_a_name_in_use_ignoring_case_raises(conn: sqlite3.Connection) -> None:
    create_watchlist(conn, "Core", AT)
    with pytest.raises(NameInUse, match="^a watchlist named 'Core' exists$"):
        create_watchlist(conn, "CORE", AT)
    assert issubclass(NameInUse, ValueError)
    assert [w.name for w in list_watchlists(conn)] == ["Core"]


@pytest.mark.parametrize("name", ["", "   ", "x" * 61])
def test_a_name_is_1_to_60_characters(conn: sqlite3.Connection, name: str) -> None:
    with pytest.raises(ValueError, match="^a name is 1 to 60 characters$"):
        create_watchlist(conn, name, AT)
    assert list_watchlists(conn) == []
    create_watchlist(conn, "x" * 60, AT)


def test_rename(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    other = create_watchlist(conn, "Other", AT)
    rename_watchlist(conn, core, "CORE")  # its own name in another case
    assert get_watchlist(conn, core).name == "CORE"
    with pytest.raises(NameInUse, match="^a watchlist named 'CORE' exists$"):
        rename_watchlist(conn, other, "core")
    with pytest.raises(ValueError, match="^a name is 1 to 60 characters$"):
        rename_watchlist(conn, other, " ")
    rename_watchlist(conn, other, " Income ")
    assert [w.name for w in list_watchlists(conn)] == ["CORE", "Income"]


def test_add_is_idempotent_and_upper_cases(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    add_symbol(conn, core, "brk.b", AT)
    add_symbol(conn, core, "BRK.B", LATER)  # already on: keeps its first date
    add_symbol(conn, core, "aapl", LATER)
    assert get_watchlist(conn, core).entries == (
        EntryRow("AAPL", LATER),
        EntryRow("BRK.B", AT),
    )


def test_a_bad_symbol_raises(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    with pytest.raises(ValueError, match="^'bad symbol' is not a symbol$"):
        add_symbol(conn, core, "bad symbol", AT)
    with pytest.raises(ValueError, match="^'TOOLONGSYMBOL' is not a symbol$"):
        set_memberships(conn, "TOOLONGSYMBOL", [core], AT)
    assert get_watchlist(conn, core).entries == ()


def test_remove(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    add_symbol(conn, core, "AAPL", AT)
    add_symbol(conn, core, "MSFT", AT)
    remove_symbol(conn, core, "aapl")
    remove_symbol(conn, core, "KO")  # not on the list: nothing to do
    assert get_watchlist(conn, core).entries == (EntryRow("MSFT", AT),)


def test_delete_removes_the_entries(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    other = create_watchlist(conn, "Other", AT)
    add_symbol(conn, core, "AAPL", AT)
    add_symbol(conn, other, "AAPL", AT)
    delete_watchlist(conn, core)
    assert [w.id for w in list_watchlists(conn)] == [other]
    assert memberships(conn) == {"AAPL": [other]}
    count = conn.execute("SELECT COUNT(*) FROM watchlist_entries WHERE watchlist_id = ?", (core,))
    assert count.fetchone()[0] == 0


def test_the_foreign_key_cascades_a_delete(conn: sqlite3.Connection) -> None:
    """The schema's own rule, should a list row go without ``delete_watchlist``."""
    core = create_watchlist(conn, "Core", AT)
    add_symbol(conn, core, "AAPL", AT)
    with conn:
        conn.execute("DELETE FROM watchlists WHERE id = ?", (core,))
    assert conn.execute("SELECT COUNT(*) FROM watchlist_entries").fetchone()[0] == 0


def test_a_duplicate_entry_is_refused_by_the_schema(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    add_symbol(conn, core, "AAPL", AT)
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute(
            "INSERT INTO watchlist_entries (watchlist_id, symbol, added_at) VALUES (?, ?, ?)",
            (core, "AAPL", LATER.isoformat()),
        )


def test_set_memberships_adds_and_removes_in_one_call(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    income = create_watchlist(conn, "Income", AT)
    watch = create_watchlist(conn, "Watch", AT)
    add_symbol(conn, core, "KO", AT)
    add_symbol(conn, income, "KO", AT)
    set_memberships(conn, "ko", [watch, core, watch], LATER)
    assert memberships(conn) == {"KO": [core, watch]}
    assert get_watchlist(conn, core).entries == (EntryRow("KO", AT),)  # kept: its first date
    assert get_watchlist(conn, watch).entries == (EntryRow("KO", LATER),)
    set_memberships(conn, "KO", [], LATER)
    assert memberships(conn) == {}


def test_set_memberships_is_all_or_none(conn: sqlite3.Connection) -> None:
    core = create_watchlist(conn, "Core", AT)
    with pytest.raises(KeyError):
        set_memberships(conn, "KO", [core, 99], AT)
    assert not conn.in_transaction
    assert memberships(conn) == {}


def test_memberships_map_symbols_to_sorted_ids(conn: sqlite3.Connection) -> None:
    first = create_watchlist(conn, "Zeta", AT)
    second = create_watchlist(conn, "Alpha", AT)
    add_symbol(conn, second, "AAPL", AT)
    add_symbol(conn, first, "AAPL", AT)
    add_symbol(conn, second, "MSFT", AT)
    assert memberships(conn) == {"AAPL": [first, second], "MSFT": [second]}


def test_a_missing_id_raises_key_error(conn: sqlite3.Connection) -> None:
    calls = [
        lambda: get_watchlist(conn, 99),
        lambda: rename_watchlist(conn, 99, "Core"),
        lambda: delete_watchlist(conn, 99),
        lambda: add_symbol(conn, 99, "AAPL", AT),
        lambda: remove_symbol(conn, 99, "AAPL"),
    ]
    for call in calls:
        with pytest.raises(KeyError) as raised:
            call()
        assert raised.value.args == (99,)
    assert not conn.in_transaction
