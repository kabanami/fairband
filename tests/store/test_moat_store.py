"""The moat table in the database (spec 2026-11-19 8.3, 8.4): one row a company, the file's, the
owner's or an agent's. The file read into the table writes, replaces and deletes file rows only
where they differ from it, and never touches a local row."""

import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from fairband.policy import Moat
from fairband.policy.moat import MoatEntry, MoatTable
from fairband.store.db import transaction
from fairband.store.ledger import OWNER, SYSTEM, Writer
from fairband.store.moat import (
    Loaded,
    MoatRow,
    file_moat,
    load_moat_file,
    moat_row,
    set_moat,
    set_snapshot,
)

AT = datetime(2026, 11, 21, 9, 30, tzinfo=UTC)
LATER = AT + timedelta(hours=1)
JUDGED = date(2026, 11, 19)
V1 = "fairband-moat-v1"
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
FILING = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": "share lost to rivals"}


def _table(
    classes: dict[str, Moat], *, version: str = V1, judged: dict[str, date] | None = None
) -> MoatTable:
    """A table of rule entries, each judged ``JUDGED`` unless ``judged`` names another day."""
    days = judged or {}
    entries = {s: MoatEntry(s, m, days.get(s, JUDGED), "rule") for s, m in classes.items()}
    return MoatTable(version, date(2026, 11, 21), "a test universe", "docs/method.md 4.9a", entries)


def _file_row(
    symbol: str, moat: Moat, at: datetime, *, version: str = V1, judged: date = JUDGED
) -> MoatRow:
    return MoatRow(
        symbol=symbol,
        moat=moat,
        source="file",
        file_version=version,
        judged_on=judged,
        previous=None,
        reason=None,
        evidence=None,
        principal="system",
        actor=None,
        client=None,
        at=at,
        snapshot_id=None,
    )


def _rows(conn: sqlite3.Connection) -> dict[str, MoatRow | None]:
    symbols = [r[0] for r in conn.execute("SELECT symbol FROM moat_classes ORDER BY symbol")]
    return {s: moat_row(conn, s) for s in symbols}


def test_the_load_writes_replaces_and_deletes_file_rows(conn: sqlite3.Connection) -> None:
    """A company the file holds and the table does not gets its file row; a file row whose class,
    date or version differs from the file's entry is replaced; a file row whose company the file
    no longer holds is deleted. A row the file still holds as it is keeps its ``at``."""
    first = _table({"AAA": "Wide", "BBB": "Narrow", "CCC": "None", "DDD": "Narrow"})
    assert load_moat_file(conn, first, AT) == Loaded(written=4, replaced=0, deleted=0)
    assert not conn.in_transaction
    assert _rows(conn) == {
        "AAA": _file_row("AAA", "Wide", AT),
        "BBB": _file_row("BBB", "Narrow", AT),
        "CCC": _file_row("CCC", "None", AT),
        "DDD": _file_row("DDD", "Narrow", AT),
    }

    redated = {"DDD": date(2026, 11, 25)}
    second = _table({"AAA": "Wide", "BBB": "Wide", "DDD": "Narrow", "EEE": "None"}, judged=redated)
    assert load_moat_file(conn, second, LATER) == Loaded(written=1, replaced=2, deleted=1)
    assert _rows(conn) == {
        "AAA": _file_row("AAA", "Wide", AT),  # as the file holds it
        "BBB": _file_row("BBB", "Wide", LATER),  # its class
        "DDD": _file_row("DDD", "Narrow", LATER, judged=date(2026, 11, 25)),  # its date
        "EEE": _file_row("EEE", "None", LATER),  # the file holds it, the table did not
    }  # CCC: the file no longer holds it

    latest = LATER + timedelta(hours=1)
    v2 = "fairband-moat-v2"
    third = replace(second, version=v2)
    assert load_moat_file(conn, third, latest) == Loaded(written=0, replaced=4, deleted=0)
    assert _rows(conn) == {
        "AAA": _file_row("AAA", "Wide", latest, version=v2),  # its version
        "BBB": _file_row("BBB", "Wide", latest, version=v2),
        "DDD": _file_row("DDD", "Narrow", latest, version=v2, judged=date(2026, 11, 25)),
        "EEE": _file_row("EEE", "None", latest, version=v2),
    }


def test_the_load_never_touches_a_local_row(conn: sqlite3.Connection) -> None:
    """The owner's and an agent's rows stay as they were whatever a new version of the file holds,
    a company the file does not hold among them."""
    load_moat_file(conn, _table({"AAA": "Wide", "BBB": "Narrow"}), AT)
    owners = set_moat(conn, "AAA", "Narrow", OWNER, None, None, LATER)
    agents = set_moat(conn, "BBB", "None", AGENT, "margins fell for a decade", [FILING], LATER)
    entrant = set_moat(conn, "ZZZ", "Wide", AGENT, "a network no rival matches", [FILING], LATER)
    new = _table(
        {"AAA": "None", "BBB": "Wide"},
        version="fairband-moat-v2",
        judged={"AAA": date(2026, 12, 1), "BBB": date(2026, 12, 1)},
    )

    assert load_moat_file(conn, new, LATER + timedelta(hours=1)) == Loaded(0, 0, 0)

    assert _rows(conn) == {"AAA": owners, "BBB": agents, "ZZZ": entrant}


def test_a_load_that_changes_nothing_writes_nothing(conn: sqlite3.Connection) -> None:
    """A load on an unchanged file writes no row: every ``at`` stays as it was."""
    table = _table({"AAA": "Wide", "BBB": "Narrow", "CCC": "None"})
    load_moat_file(conn, table, AT)
    set_moat(conn, "BBB", "Wide", OWNER, None, None, AT)
    held = _rows(conn)
    changes = conn.total_changes

    assert load_moat_file(conn, table, LATER) == Loaded(written=0, replaced=0, deleted=0)

    assert conn.total_changes == changes
    assert _rows(conn) == held


def test_set_moat_and_file_moat(conn: sqlite3.Connection) -> None:
    """The owner's or an agent's write keeps the class in force before it, none without a row, and
    is judged on its time's UTC day; the system writes no such row. The file's class returns a
    company to its entry, and a company the file does not hold has none."""
    assert moat_row(conn, "AAA") is None
    tokyo = datetime(2026, 11, 20, 8, 0, tzinfo=timezone(timedelta(hours=9)))  # 19 Nov in UTC
    agents = set_moat(conn, "AAA", "Wide", AGENT, "pricing power", [FILING], tokyo)
    assert agents == MoatRow(
        symbol="AAA",
        moat="Wide",
        source="agent",
        file_version=None,
        judged_on=date(2026, 11, 19),
        previous=None,
        reason="pricing power",
        evidence=(FILING,),
        principal="agent",
        actor="claude-opus-5-5",
        client="claude-code/2.1",
        at=tokyo,
        snapshot_id=None,
    )
    assert moat_row(conn, "AAA") == agents

    owners = set_moat(conn, "AAA", "Narrow", OWNER, None, None, LATER)
    assert owners == MoatRow(
        symbol="AAA",
        moat="Narrow",
        source="owner",
        file_version=None,
        judged_on=date(2026, 11, 21),
        previous="Wide",
        reason=None,
        evidence=None,
        principal="owner",
        actor=None,
        client=None,
        at=LATER,
        snapshot_id=None,
    )
    stands = set_moat(conn, "AAA", "Narrow", AGENT, "the class stands", [FILING], LATER)
    assert (stands.source, stands.moat, stands.previous) == ("agent", "Narrow", "Narrow")
    with pytest.raises(ValueError, match="^a moat class is the owner's or an agent's"):
        set_moat(conn, "AAA", "Wide", SYSTEM, None, None, LATER)
    assert moat_row(conn, "AAA") == stands

    set_snapshot(conn, "AAA", 42)
    assert moat_row(conn, "AAA") == replace(stands, snapshot_id=42)
    with pytest.raises(KeyError):
        set_snapshot(conn, "ZZZ", 42)

    table = _table({"AAA": "None"})
    returned = file_moat(conn, "AAA", table, LATER)
    assert returned == _file_row("AAA", "None", LATER)
    assert moat_row(conn, "AAA") == returned
    with pytest.raises(KeyError):
        file_moat(conn, "ZZZ", table, LATER)
    assert moat_row(conn, "ZZZ") is None


def test_the_writes_join_the_callers_transaction(conn: sqlite3.Connection) -> None:
    """Inside the caller's transaction each write leaves the commit to it: a revalue that fails
    after the write takes the row back with it."""
    load_moat_file(conn, _table({"AAA": "Wide"}), AT)
    with pytest.raises(RuntimeError, match="the revalue failed"), transaction(conn):
        set_moat(conn, "AAA", "Narrow", OWNER, None, None, LATER)
        set_snapshot(conn, "AAA", 42)
        load_moat_file(conn, _table({"BBB": "None"}), LATER)
        file_moat(conn, "CCC", _table({"CCC": "Wide"}), LATER)
        assert conn.in_transaction
        raise RuntimeError("the revalue failed")
    assert _rows(conn) == {"AAA": _file_row("AAA", "Wide", AT)}
