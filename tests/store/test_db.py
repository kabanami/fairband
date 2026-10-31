import hashlib
import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import pytest

from fairband.store import db
from fairband.store.db import applied_versions, connect, migrate

_TABLES = {
    "schema_versions",
    "policy_versions",
    "refreshes",
    "refresh_items",
    "deciles",
    "companies",
    "vendor_responses",
    "facts",
    "observations",
    "snapshots",
}


def _packaged_initial() -> bytes:
    return resources.files("fairband.store").joinpath("migrations/001_initial.sql").read_bytes()


def _migrations_dir(tmp_path: Path, extra: dict[str, str]) -> Path:
    """A migrations directory holding the packaged 001 plus ``extra`` files."""
    folder = tmp_path / "migrations"
    folder.mkdir()
    (folder / "001_initial.sql").write_bytes(_packaged_initial())
    for name, text in extra.items():
        (folder / name).write_text(text)
    return folder


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(connect(tmp_path / "f.db")) as conn:
        yield conn


def test_empty_db_migrates(conn: sqlite3.Connection) -> None:
    assert migrate(conn) == ["001_initial.sql"] and applied_versions(conn) == [1]
    assert migrate(conn) == []
    names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert _TABLES <= names


def test_initial_records_the_file_checksum(conn: sqlite3.Connection) -> None:
    migrate(conn, clock=lambda: datetime(2026, 11, 1, 9, 30, tzinfo=UTC))
    row = conn.execute("select * from schema_versions").fetchone()
    assert dict(row) == {
        "version": 1,
        "filename": "001_initial.sql",
        "checksum": hashlib.sha256(_packaged_initial()).hexdigest(),
        "applied_at": "2026-11-01T09:30:00+00:00",
    }


def test_initial_indexes(conn: sqlite3.Connection) -> None:
    migrate(conn)

    def indexed(table: str) -> list[list[str]]:
        rows = conn.execute(f"pragma index_list({table})")
        names = [r["name"] for r in rows if r["origin"] == "c"]
        return [[c["name"] for c in conn.execute(f"pragma index_info({n})")] for n in names]

    assert indexed("vendor_responses") == [["provider", "endpoint", "symbol", "observed_at"]]
    assert indexed("facts") == [["symbol", "dataset", "period_end", "field"]]
    assert indexed("observations") == [["symbol", "dataset", "period", "field"]]
    assert indexed("snapshots") == [["symbol", "id"]]


def test_foreign_keys_enforced(conn: sqlite3.Connection) -> None:
    migrate(conn)
    with pytest.raises(sqlite3.IntegrityError), conn:
        conn.execute(
            "insert into refresh_items (refresh_id, symbol, status, updated_at)"
            " values (?, ?, ?, ?)",
            (99, "AAPL", "pending", "2026-11-01T00:00:00+00:00"),
        )


def test_applied_versions_without_table(conn: sqlite3.Connection) -> None:
    assert applied_versions(conn) == []


def test_checksum_mismatch_refuses(conn: sqlite3.Connection) -> None:
    migrate(conn)
    with conn:
        conn.execute("update schema_versions set checksum = 'tampered' where version = 1")
    with pytest.raises(ValueError, match="001_initial.sql"):
        migrate(conn)


def test_mismatch_refuses_before_applying_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    folder = _migrations_dir(tmp_path, {})
    monkeypatch.setattr(db, "_MIGRATIONS", folder)
    migrate(conn)
    (folder / "001_initial.sql").write_bytes(_packaged_initial() + b"\n-- edited\n")
    (folder / "002_more.sql").write_text("create table more (x integer);\n")
    with pytest.raises(ValueError, match="001_initial.sql"):
        migrate(conn)
    assert applied_versions(conn) == [1]


def test_applied_version_missing_from_package_refuses(conn: sqlite3.Connection) -> None:
    migrate(conn)
    with conn:
        conn.execute(
            "insert into schema_versions values (2, '002_gone.sql', 'abc', '2026-11-01T00:00:00Z')"
        )
    with pytest.raises(ValueError, match="002_gone.sql"):
        migrate(conn)


def test_pending_files_apply_in_filename_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    folder = _migrations_dir(
        tmp_path,
        {
            "010_third.sql": "insert into second (x) values (2);\n",
            "002_second.sql": "create table second (x integer);\ninsert into second values (1);\n",
            "notes.txt": "not a migration\n",
        },
    )
    monkeypatch.setattr(db, "_MIGRATIONS", folder)
    assert migrate(conn) == ["001_initial.sql", "002_second.sql", "010_third.sql"]
    assert applied_versions(conn) == [1, 2, 10]
    assert [r[0] for r in conn.execute("select x from second order by rowid")] == [1, 2]


def test_failed_file_rolls_back_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    folder = _migrations_dir(
        tmp_path, {"002_broken.sql": "create table half (x integer);\nselect * from nowhere;\n"}
    )
    monkeypatch.setattr(db, "_MIGRATIONS", folder)
    with pytest.raises(sqlite3.OperationalError):
        migrate(conn)
    assert not conn.in_transaction
    assert applied_versions(conn) == [1]
    names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert "half" not in names


def test_pragmas(tmp_path: Path) -> None:
    path = tmp_path / "new" / "dir" / "f.db"
    with closing(connect(path)) as conn:
        assert path.parent.is_dir()
        assert conn.execute("pragma journal_mode").fetchone()[0] == "wal"
        assert conn.execute("pragma foreign_keys").fetchone()[0] == 1
        assert conn.execute("pragma synchronous").fetchone()[0] == 2  # FULL
        assert conn.execute("select 1 as one").fetchone()["one"] == 1


def test_cli_migrate(tmp_path: Path) -> None:
    env = {**os.environ, "FAIRBAND_DATA_DIR": str(tmp_path / "data")}

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "fairband", "migrate"],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    first = run()
    assert first.returncode == 0, first.stderr
    assert first.stdout.splitlines() == ["Applied 001_initial.sql"]
    assert (tmp_path / "data" / "fairband.db").is_file()
    second = run()
    assert second.returncode == 0 and second.stdout.splitlines() == ["No migrations to apply."]
