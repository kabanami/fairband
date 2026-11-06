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

from fairband.policy.settings import EMPTY_SETTINGS_HASH
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
    "settings",
    "settings_changes",
    "watchlists",
    "watchlist_entries",
}
_ALL = [
    "001_initial.sql",
    "002_designation.sql",
    "003_facts_by_response.sql",
    "004_settings_and_watchlists.sql",
    "005_agents.sql",
]
# The agents' records (spec 2026-11-06 Tier 2, section 17), each table's columns the record's
# fields in order; a work item's poster carries its client as every other writer does.
_AGENT_COLUMNS = {
    "ledger": [
        *("id", "at", "principal", "actor", "client", "kind", "symbol", "ref_table", "ref_id"),
        *("snapshot_id", "work_item_id", "summary"),
    ],
    "work_items": [
        *("id", "symbol", "mode", "note", "snapshot_id", "origin", "posted_by", "posted_actor"),
        *("posted_client", "posted_at", "state", "claimed_by", "claimed_at", "report_id"),
        *("reason", "finished_at", "expiry_valid_until"),
    ],
    "notes": ["id", "symbol", "text", "principal", "actor", "client", "at", "override_id"],
    "findings": [
        *("id", "symbol", "as_of", "text", "source_kind", "source_ref", "source_note", "value"),
        *("unit", "period", "principal", "actor", "client", "at"),
    ],
    "kill_criteria": [
        *("id", "symbol", "text", "state", "report_id", "principal", "actor", "client", "at"),
        *("state_reason", "state_at"),
    ],
    "news_items": [
        *("id", "symbol", "date", "headline", "source", "text", "kill_criterion_id"),
        "report_id",
        *("principal", "actor", "client", "at"),
    ],
    "overrides": [
        *("id", "symbol", "tag", "old", "new", "unit", "reason", "evidence", "lifetime"),
        *("period", "corrected_value", "snapshot_id", "principal", "actor", "client", "at"),
        *("state", "message", "review_id", "drop_reason", "dropped_at"),
    ],
    "reviews": [
        *("id", "symbol", "snapshot_id", "refresh_id", "created_at", "value", "buy_level"),
        *("fair_low", "fair_high", "trim_level", "price_to_value", "designation", "refusal"),
        *("mechanical_value", "bridge", "override_ids", "policy_version", "method_version"),
        *("review_method", "settings_hash", "deciles_refresh_id", "result"),
    ],
    "review_log": [
        *("id", "at", "symbol", "refresh_id", "snapshot_id", "review_id", "mechanical_phase"),
        *("mechanical_value", "reviewed_phase", "reviewed_value", "secondary_value", "price"),
        *("designation", "stance"),
    ],
    "secondary_valuations": [
        *("id", "symbol", "snapshot_id", "created_at", "principal", "actor", "client", "parts"),
        *("firm_value", "debt", "cash", "shares", "equity", "value_per_share", "buy_level"),
        *("fair_low", "fair_high", "trim_level", "price_to_value", "designation", "reason"),
        *("evidence", "debt_source", "cash_source", "policy_version", "settings_hash"),
        *("deciles_refresh_id", "secondary_method"),
    ],
    "derivations": [
        *("id", "symbol", "operation", "a", "b", "years", "value", "unit", "principal"),
        *("actor", "client", "at"),
    ],
    "reports": [
        *("id", "symbol", "revision", "mode", "stance", "sections", "reuses_full_report_of"),
        *("snapshot_id", "review_id", "secondary_id", "work_item_id", "principal", "actor"),
        *("client", "created_at"),
    ],
    "judgments": [
        *("id", "report_id", "symbol", "judgment", "bull", "bear", "decision", "override_id"),
    ],
}


def _packaged_initial() -> bytes:
    return _packaged("001_initial.sql")


def _packaged(filename: str) -> bytes:
    return resources.files("fairband.store").joinpath(f"migrations/{filename}").read_bytes()


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
    assert migrate(conn) == _ALL
    assert applied_versions(conn) == [1, 2, 3, 4, 5]
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
    assert indexed("facts") == [
        ["response_id", "field"],  # 003: the fields a response's facts hold
        ["symbol", "dataset", "period_end", "field"],
    ]
    assert indexed("observations") == [["symbol", "dataset", "period", "field"]]
    assert indexed("snapshots") == [["symbol", "id"]]


def test_designation_columns_join_a_database_at_001(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    """A database at 001 gains price ÷ value and the designation on the snapshots; the stance
    columns stay, no longer written."""
    with monkeypatch.context() as patched:
        patched.setattr(db, "_MIGRATIONS", _migrations_dir(tmp_path, {}))
        assert migrate(conn) == ["001_initial.sql"]
    assert migrate(conn) == _ALL[1:]
    assert applied_versions(conn) == [1, 2, 3, 4, 5]
    columns = {r["name"]: r["type"] for r in conn.execute("pragma table_info(snapshots)")}
    assert (columns["price_to_value"], columns["designation"]) == ("REAL", "TEXT")
    assert (columns["stance5"], columns["stance3"]) == ("TEXT", "TEXT")


def test_migration_004_fills_the_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    """A database at 003 gains the settings and watchlist tables, and its refreshes and snapshots
    read the empty overlay's settings hash: they ran under the policy file alone."""
    folder = _migrations_dir(tmp_path, {})
    for filename in _ALL[1:3]:
        (folder / filename).write_bytes(_packaged(filename))
    with monkeypatch.context() as patched:
        patched.setattr(db, "_MIGRATIONS", folder)
        assert migrate(conn) == _ALL[:3]
    stamp = "2026-11-01T09:30:00+00:00"
    conn.execute(
        "insert into refreshes (kind, status, started_at, policy_version, method_version)"
        " values ('full', 'done', ?, 'fairband-policy-v5', 'fairband-mechanical/0.7')",
        (stamp,),
    )
    conn.execute(
        "insert into snapshots (symbol, refresh_id, created_at, data_date, valid_until, flags,"
        " policy_version, method_version, result) values ('MSFT', 1, ?, '2026-10-29',"
        " '2027-01-28', '[]', 'fairband-policy-v5', 'fairband-mechanical/0.7', '{}')",
        (stamp,),
    )
    conn.commit()
    assert migrate(conn) == ["004_settings_and_watchlists.sql", "005_agents.sql"]
    assert conn.execute("select settings_hash from refreshes").fetchone()[0] == EMPTY_SETTINGS_HASH
    assert conn.execute("select settings_hash from snapshots").fetchone()[0] == EMPTY_SETTINGS_HASH
    names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert {"settings", "settings_changes", "watchlists", "watchlist_entries"} <= names


def test_migration_005_creates_the_agent_tables(conn: sqlite3.Connection) -> None:
    """One table for each record of the agents' side: the ledger, the work items, the research
    records, the overrides, the reviews and their log, the secondary valuations, the
    derivations, the reports and their judgments."""
    migrate(conn)
    names = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    assert len(_AGENT_COLUMNS) == 13 and set(_AGENT_COLUMNS) <= names


def test_the_agent_tables_hold_the_records_fields(conn: sqlite3.Connection) -> None:
    """Each table's columns are its record's fields; price ÷ value is a REAL, as on the
    snapshots, so it reads back as the double the engine computed."""
    migrate(conn)
    for table, columns in _AGENT_COLUMNS.items():
        assert [r["name"] for r in conn.execute(f"pragma table_info({table})")] == columns, table
    for table in ("reviews", "secondary_valuations"):
        types = {r["name"]: r["type"] for r in conn.execute(f"pragma table_info({table})")}
        assert types["price_to_value"] == "REAL", table


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
            "insert into schema_versions values (99, '099_gone.sql', 'abc', '2026-11-01T00:00:00Z')"
        )
    with pytest.raises(ValueError, match="099_gone.sql"):
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
    assert first.stdout.splitlines() == [
        "Applied 001_initial.sql",
        "Applied 002_designation.sql",
        "Applied 003_facts_by_response.sql",
        "Applied 004_settings_and_watchlists.sql",
        "Applied 005_agents.sql",
    ]
    assert (tmp_path / "data" / "fairband.db").is_file()
    second = run()
    assert second.returncode == 0 and second.stdout.splitlines() == ["No migrations to apply."]
