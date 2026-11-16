import hashlib
import os
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, date, datetime
from importlib import resources
from pathlib import Path

import pytest

from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.store import db
from fairband.store.db import applied_versions, connect, migrate
from fairband.store.guidance import GuidanceRow, guidance_row
from fairband.store.inbox import WorkItem, work_item
from fairband.store.reports import JudgmentRow, judgments_for
from fairband.store.research import FindingRow, KillCriterionRow, finding_row, kill_criterion_row

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
    "006_report.sql",
    "007_secondary_fx.sql",
    "008_record_currency.sql",
    "009_launches.sql",
]
# The agents' records (spec 2026-11-06 Tier 2, section 17), each table's columns the record's
# fields in order, as 005 made them and 006, 007 and 008 changed them: a judgment without its
# debate text, a secondary valuation with its form, drivers, projection and grid, and its
# snapshot's rate (spec 2026-11-10 7.6); a finding's and a kill criterion's currency, and the kill
# criterion's threshold and its unit (spec 2026-11-15 8.1, 9.1); a work item's poster carries its
# client as every other writer does.
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
        *("unit", "period", "principal", "actor", "client", "at", "currency"),
    ],
    "kill_criteria": [
        *("id", "symbol", "text", "state", "report_id", "principal", "actor", "client", "at"),
        *("state_reason", "state_at", "threshold", "unit", "currency"),
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
        *("deciles_refresh_id", "secondary_method", "form", "drivers", "projection", "grid"),
        "fx_rate",
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
    "judgments": ["id", "report_id", "symbol", "judgment", "decision", "override_id"],
}
# The report's records 006 adds (spec 2026-11-06 Tier 2, 9, 13.7 and 13.8): the multiples log,
# the sensitivity readings and the guidance records, a record's currency 008's (spec 2026-11-15
# 9.1).
_REPORT_COLUMNS = {
    "multiples_log": [
        *("id", "symbol", "day", "price", "pe_reported", "pe_clean", "pe_forward"),
        *("snapshot_id", "refresh_id", "created_at"),
    ],
    "sensitivities": [
        *("id", "symbol", "snapshot_id", "review_id", "created_at", "principal", "actor"),
        *("client", "row_tag", "col_tag", "row_values", "col_values", "cells", "current_row"),
        *("current_col", "policy_version", "settings_hash"),
    ],
    "guidance": [
        *("id", "symbol", "metric", "period", "low", "high", "midpoint", "step", "basis"),
        *("as_of", "text", "source", "principal", "actor", "client", "created_at"),
        *("superseded_by", "currency"),
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
    assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
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
    assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
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
    assert migrate(conn) == _ALL[3:]
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
    for table, columns in (_AGENT_COLUMNS | _REPORT_COLUMNS).items():
        assert [r["name"] for r in conn.execute(f"pragma table_info({table})")] == columns, table
    for table in ("reviews", "secondary_valuations"):
        types = {r["name"]: r["type"] for r in conn.execute(f"pragma table_info({table})")}
        assert types["price_to_value"] == "REAL", table


def test_migration_006_on_a_005_database_keeps_the_judgments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    """A database at 005 holds a report, its two judgments with their bull and bear text and a
    secondary valuation. 006 drops the debate text and keeps each judgment's decision and
    override; the secondary valuation reads as the parts form; the multiples log, the
    sensitivities and the guidance records join with their indexes."""
    assert sqlite3.sqlite_version_info >= (3, 35, 0), (
        "migration 006 drops two columns, which needs SQLite 3.35 or later;"
        f" this Python links SQLite {sqlite3.sqlite_version}"
    )
    folder = _migrations_dir(tmp_path, {})
    for filename in _ALL[1:5]:
        (folder / filename).write_bytes(_packaged(filename))
    with monkeypatch.context() as patched:
        patched.setattr(db, "_MIGRATIONS", folder)
        assert migrate(conn) == _ALL[:5]
    stamp = "2026-11-06T09:30:00+00:00"
    conn.execute(
        "insert into reports (symbol, revision, mode, stance, sections, snapshot_id, principal,"
        " created_at) values ('AAPL', 1, 'full report', 'hold', '[]', 4, 'agent', ?)",
        (stamp,),
    )
    conn.executemany(
        "insert into judgments (report_id, symbol, judgment, bull, bear, decision, override_id)"
        " values (1, 'AAPL', ?, ?, ?, ?, ?)",
        [("phase", "growing", "slowing", "as is", None), ("moat", "patents", "lapse", "Wide", 7)],
    )
    conn.execute(
        "insert into secondary_valuations (symbol, snapshot_id, created_at, principal, parts,"
        " firm_value, debt, cash, shares, equity, value_per_share, reason, evidence, debt_source,"
        " cash_source, policy_version, settings_hash, secondary_method) values ('AAPL', 4, ?,"
        " 'agent', '[]', '100.0', '10.0', '5.0', '2.0', '95.0', '47.5', 'a second view', '[]',"
        " 'balance', 'balance', 'fairband-policy-v8', 'h', 'fairband-secondary/1')",
        (stamp,),
    )
    conn.commit()

    assert migrate(conn) == _ALL[5:]

    assert judgments_for(conn, 1) == [
        JudgmentRow(1, 1, "AAPL", "phase", "as is", None),
        JudgmentRow(2, 1, "AAPL", "moat", "Wide", 7),
    ]
    judgment_columns = [r["name"] for r in conn.execute("pragma table_info(judgments)")]
    assert "bull" not in judgment_columns and "bear" not in judgment_columns
    form = {r["name"]: r for r in conn.execute("pragma table_info(secondary_valuations)")}["form"]
    assert (form["type"], form["notnull"], form["dflt_value"]) == ("TEXT", 1, "'parts'")
    stored = conn.execute("select form, drivers, projection, grid from secondary_valuations")
    assert tuple(stored.fetchone()) == ("parts", None, None, None)
    for table, columns in _REPORT_COLUMNS.items():
        assert [r["name"] for r in conn.execute(f"pragma table_info({table})")] == columns, table

    def indexed(table: str) -> list[tuple[str, list[str]]]:
        """Each index on ``table``, its origin (``u`` a UNIQUE constraint's, ``c`` a CREATE
        INDEX's) with its columns."""
        names = [(r["origin"], r["name"]) for r in conn.execute(f"pragma index_list({table})")]
        return [
            (origin, [c["name"] for c in conn.execute(f"pragma index_info({name})")])
            for origin, name in names
        ]

    assert indexed("multiples_log") == [("u", ["symbol", "day"])]  # one row a company a day
    assert indexed("sensitivities") == [("c", ["symbol", "snapshot_id"])]
    assert indexed("guidance") == [("c", ["symbol"])]


def test_migration_007_gives_a_secondary_valuation_its_rate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    """A database at 006 holds a secondary valuation, made in USD as every one before method 1.1
    was. 007 gives the record its snapshot's rate, a REAL that is 1.0 for a USD row (spec 2026-11-10
    7.6), so the record made before reads at the rate 1."""
    folder = _migrations_dir(tmp_path, {})
    for filename in _ALL[1:6]:
        (folder / filename).write_bytes(_packaged(filename))
    with monkeypatch.context() as patched:
        patched.setattr(db, "_MIGRATIONS", folder)
        assert migrate(conn) == _ALL[:6]
    conn.execute(
        "insert into secondary_valuations (symbol, snapshot_id, created_at, principal, parts,"
        " firm_value, debt, cash, shares, equity, value_per_share, reason, evidence, debt_source,"
        " cash_source, policy_version, settings_hash, secondary_method) values ('AAPL', 4,"
        " '2026-11-06T09:30:00+00:00', 'agent', '[]', '100.0', '10.0', '5.0', '2.0', '95.0',"
        " '47.5', 'a second view', '[]', 'none', 'none', 'fairband-policy-v10', 'h',"
        " 'fairband-secondary/2')"
    )
    conn.commit()

    assert migrate(conn) == _ALL[6:]

    columns = {r["name"]: r for r in conn.execute("pragma table_info(secondary_valuations)")}
    rate = columns["fx_rate"]
    assert (rate["type"], rate["notnull"], rate["dflt_value"]) == ("REAL", 1, "1.0")
    assert conn.execute("select fx_rate from secondary_valuations").fetchone()[0] == 1.0


def test_migration_008_gives_a_record_its_currency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    """A database at 007 holds a finding, a guidance record and a kill criterion, each written
    before a record named its currency. 008 adds a currency to all three and a threshold with its
    unit to the kill criterion (spec 2026-11-15 8.1, 9.1), each column empty, so every record
    reads with its fields as before and no currency: the company's reporting currency."""
    folder = _migrations_dir(tmp_path, {})
    for filename in _ALL[1:7]:
        (folder / filename).write_bytes(_packaged(filename))
    with monkeypatch.context() as patched:
        patched.setattr(db, "_MIGRATIONS", folder)
        assert migrate(conn) == _ALL[:7]
    stamp = "2026-11-11T09:30:00+00:00"
    conn.execute(
        "insert into findings (symbol, as_of, text, source_kind, source_ref, source_note, value,"
        " unit, period, principal, actor, client, at) values ('TSM', '2026-10-16', 'capex guided',"
        " 'transcript', 'response:7', null, '42000000000.0', 'currency', '2026', 'agent',"
        " 'claude-opus-5-5', 'claude-code/2.1', ?)",
        (stamp,),
    )
    conn.execute(
        "insert into guidance (symbol, metric, period, low, high, midpoint, step, basis, as_of,"
        " text, source, principal, actor, client, created_at) values ('TSM', 'revenue', '2026',"
        " '3.0e12', '3.2e12', '3.1e12', '0.2', 'gaap', '2026-10-16', 'We expect revenue to grow.',"
        " 'response:7', 'agent', 'claude-opus-5-5', 'claude-code/2.1', ?)",
        (stamp,),
    )
    conn.execute(
        "insert into kill_criteria (symbol, text, state, report_id, principal, actor, client, at)"
        " values ('TSM', 'gross margin below 50%', 'open', null, 'agent', 'claude-opus-5-5',"
        " 'claude-code/2.1', ?)",
        (stamp,),
    )
    conn.commit()

    assert migrate(conn) == _ALL[7:]

    assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    at = datetime(2026, 11, 11, 9, 30, tzinfo=UTC)
    by_agent = {"principal": "agent", "actor": "claude-opus-5-5", "client": "claude-code/2.1"}
    assert finding_row(conn, 1) == FindingRow(
        id=1,
        symbol="TSM",
        as_of=date(2026, 10, 16),
        text="capex guided",
        source_kind="transcript",
        source_ref="response:7",
        source_note=None,
        value=42e9,
        unit="currency",
        period="2026",
        **by_agent,
        at=at,
        currency=None,
    )
    assert guidance_row(conn, 1) == GuidanceRow(
        id=1,
        symbol="TSM",
        metric="revenue",
        period="2026",
        low=3.0e12,
        high=3.2e12,
        midpoint=3.1e12,
        step=0.2,
        basis="gaap",
        as_of=date(2026, 10, 16),
        text="We expect revenue to grow.",
        source="response:7",
        **by_agent,
        created_at=at,
        superseded_by=None,
        currency=None,
    )
    assert kill_criterion_row(conn, 1) == KillCriterionRow(
        id=1,
        symbol="TSM",
        text="gross margin below 50%",
        state="open",
        report_id=None,
        **by_agent,
        at=at,
        state_reason=None,
        state_at=None,
    )
    for table, added in (
        ("findings", ["currency"]),
        ("guidance", ["currency"]),
        ("kill_criteria", ["threshold", "unit", "currency"]),
    ):
        columns = {r["name"]: r for r in conn.execute(f"pragma table_info({table})")}
        for name in added:
            column = columns[name]
            assert (column["type"], column["notnull"], column["dflt_value"]) == ("TEXT", 0, None)
        stored = conn.execute(f"select {', '.join(added)} from {table}").fetchone()
        assert tuple(stored) == (None,) * len(added), table


def test_migration_009_adds_the_launch_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, conn: sqlite3.Connection
) -> None:
    """A database at 008 holds a pending work item. 009 adds the launch record (spec 2026-11-16,
    section 8), empty, with its index on an item's launches in order; the item reads as before."""
    folder = _migrations_dir(tmp_path, {})
    for filename in _ALL[1:8]:
        (folder / filename).write_bytes(_packaged(filename))
    with monkeypatch.context() as patched:
        patched.setattr(db, "_MIGRATIONS", folder)
        assert migrate(conn) == _ALL[:8]
    conn.execute(
        "insert into work_items (symbol, mode, note, snapshot_id, origin, posted_by, posted_actor,"
        " posted_client, posted_at, state) values ('AAPL', 'full report', 'why', null, 'owner',"
        " 'owner', null, null, '2026-11-16T09:30:00+00:00', 'pending')"
    )
    conn.commit()

    assert migrate(conn) == ["009_launches.sql"]

    assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    recorded = conn.execute("select filename, checksum from schema_versions where version = 9")
    assert tuple(recorded.fetchone()) == (
        "009_launches.sql",
        hashlib.sha256(_packaged("009_launches.sql")).hexdigest(),
    )
    assert work_item(conn, 1) == WorkItem(
        id=1,
        symbol="AAPL",
        mode="full report",
        note="why",
        snapshot_id=None,
        origin="owner",
        posted_by="owner",
        posted_actor=None,
        posted_client=None,
        posted_at=datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
        state="pending",
        claimed_by=None,
        claimed_at=None,
        report_id=None,
        reason=None,
        finished_at=None,
        expiry_valid_until=None,
    )
    assert conn.execute("select count(*) from launches").fetchone()[0] == 0
    columns = [
        (r["name"], r["type"], r["notnull"]) for r in conn.execute("pragma table_info(launches)")
    ]
    assert columns == [
        ("id", "INTEGER", 0),
        ("item_id", "INTEGER", 0),
        ("agent", "TEXT", 1),
        ("state", "TEXT", 1),
        ("stage", "TEXT", 0),
        ("detail", "TEXT", 0),
        ("exit_code", "INTEGER", 0),
        ("created_at", "TEXT", 1),
        ("updated_at", "TEXT", 1),
    ]
    keys = [
        (r["from"], r["table"], r["to"]) for r in conn.execute("pragma foreign_key_list(launches)")
    ]
    assert keys == [("item_id", "work_items", "id")]
    [index] = [r["name"] for r in conn.execute("pragma index_list(launches)")]
    assert [c["name"] for c in conn.execute(f"pragma index_info({index})")] == ["item_id", "id"]


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
        "Applied 006_report.sql",
        "Applied 007_secondary_fx.sql",
        "Applied 008_record_currency.sql",
        "Applied 009_launches.sql",
    ]
    assert (tmp_path / "data" / "fairband.db").is_file()
    second = run()
    assert second.returncode == 0 and second.stdout.splitlines() == ["No migrations to apply."]
