import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fairband.engine.classifier import Deciles
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.store.refreshes import (
    ItemRow,
    RefreshRow,
    RefreshRunning,
    create_refresh,
    current_refresh,
    finish_refresh,
    items,
    latest_deciles,
    latest_refresh,
    mark_interrupted,
    save_deciles,
    set_stage,
    upsert_item,
)

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
T1 = T0 + timedelta(minutes=5)
POLICY, METHOD = "fairband-policy-v1", "fairband-mechanical/0.1"


def _start(conn: sqlite3.Connection, kind: str = "full", symbols: list[str] | None = None) -> int:
    return create_refresh(conn, kind, symbols, POLICY, METHOD, T0, EMPTY_SETTINGS_HASH)


def test_create_refresh_and_latest_refresh(conn: sqlite3.Connection) -> None:
    assert latest_refresh(conn) is None
    full = _start(conn)
    finish_refresh(conn, full, "done", T1)
    scoped = _start(conn, "scoped", ["MSFT", "BRK.B"])
    assert not conn.in_transaction
    assert latest_refresh(conn) == RefreshRow(
        id=scoped,
        kind="scoped",
        symbols=("MSFT", "BRK.B"),
        status="running",
        stage=None,
        started_at=T0,
        finished_at=None,
        policy_version=POLICY,
        method_version=METHOD,
        settings_hash=EMPTY_SETTINGS_HASH,
        calibration=None,
        message=None,
    )
    stored = conn.execute("select symbols from refreshes order by id").fetchall()
    assert [r[0] for r in stored] == [None, '["MSFT", "BRK.B"]']


def test_create_refresh_records_the_settings_hash(conn: sqlite3.Connection) -> None:
    refresh_id = create_refresh(conn, "revalue", None, POLICY, METHOD, T0, "abc")
    row = latest_refresh(conn)
    assert row is not None and (row.id, row.settings_hash) == (refresh_id, "abc")
    assert conn.execute("select settings_hash from refreshes").fetchone()[0] == "abc"


def test_create_refresh_refuses_while_one_runs(conn: sqlite3.Connection) -> None:
    running = _start(conn)
    with pytest.raises(RefreshRunning) as refused:
        _start(conn, "scoped", ["AAPL"])
    assert refused.value.refresh_id == running
    assert not conn.in_transaction
    assert conn.execute("select count(*) from refreshes").fetchone()[0] == 1
    finish_refresh(conn, running, "cancelled", T1)
    assert _start(conn) == running + 1


def test_set_stage_and_current_refresh(conn: sqlite3.Connection) -> None:
    assert current_refresh(conn) is None
    refresh_id = _start(conn)
    set_stage(conn, refresh_id, "fetch")
    current = current_refresh(conn)
    assert current is not None and (current.id, current.stage) == (refresh_id, "fetch")
    finish_refresh(conn, refresh_id, "failed", T1, message="universe call failed")
    assert current_refresh(conn) is None


def test_finish_refresh_records_the_outcome(conn: sqlite3.Connection) -> None:
    refresh_id = _start(conn)
    calibration = {"phases": {"Mature Growth": 2}, "valued": 2, "total": 3, "share": 0.1 + 0.2}
    finish_refresh(conn, refresh_id, "done", T1, message="3 companies", calibration=calibration)
    row = latest_refresh(conn)
    assert row is not None
    assert (row.status, row.finished_at, row.message) == ("done", T1, "3 companies")
    assert row.calibration == calibration
    stored = conn.execute("select finished_at, calibration from refreshes").fetchone()
    assert stored[0] == "2026-11-01T09:35:00+00:00" and stored[1].startswith('{"phases"')


def test_set_stage_and_finish_refuse_an_unknown_refresh(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="no refresh 7"):
        set_stage(conn, 7, "fetch")
    with pytest.raises(ValueError, match="no refresh 7"):
        finish_refresh(conn, 7, "done", T1)
    assert not conn.in_transaction


def test_upsert_item_and_items(conn: sqlite3.Connection) -> None:
    first = _start(conn)
    upsert_item(conn, first, "MSFT", "pending", None, T0)
    upsert_item(conn, first, "AAPL", "pending", None, T0)
    upsert_item(conn, first, "AAPL", "failed", "data fetch failed: quote", T1)
    finish_refresh(conn, first, "done", T1)
    other = _start(conn)
    upsert_item(conn, other, "AAPL", "valued", None, T1)
    assert not conn.in_transaction
    assert items(conn, first) == [
        ItemRow(first, "AAPL", "failed", "data fetch failed: quote", T1),
        ItemRow(first, "MSFT", "pending", None, T0),
    ]
    assert items(conn, other) == [ItemRow(other, "AAPL", "valued", None, T1)]
    assert items(conn, other + 1) == []


def test_mark_interrupted_flips_running(conn: sqlite3.Connection) -> None:
    done = _start(conn)
    finish_refresh(conn, done, "done", T1)
    stale = _start(conn)
    set_stage(conn, stale, "fetch")
    at = T0 + timedelta(hours=2)
    assert mark_interrupted(conn, at) == 1
    assert not conn.in_transaction
    row = latest_refresh(conn)
    assert row is not None and (row.id, row.status, row.finished_at) == (stale, "interrupted", at)
    assert row.stage == "fetch"
    finished = conn.execute("select status, finished_at from refreshes where id = ?", (done,))
    assert tuple(finished.fetchone()) == ("done", "2026-11-01T09:35:00+00:00")
    assert current_refresh(conn) is None
    assert mark_interrupted(conn, at) == 0


def test_save_deciles_and_latest_deciles(conn: sqlite3.Connection) -> None:
    assert latest_deciles(conn) is None
    first = _start(conn)
    save_deciles(conn, first, Deciles((0.01, 0.05), (), 2, 0, None), T0)
    finish_refresh(conn, first, "done", T1)
    second = _start(conn)
    edges = tuple(0.1 * k for k in range(1, 10))
    margin_edges = (-0.02, 0.1 + 0.2, 0.0)
    save_deciles(conn, second, Deciles(edges, margin_edges, 1200, 980, None), T1)
    assert not conn.in_transaction
    assert latest_deciles(conn) == Deciles(edges, margin_edges, 1200, 980, second)
    computed = conn.execute("select computed_at from deciles where refresh_id = ?", (second,))
    assert computed.fetchone()[0] == "2026-11-01T09:35:00+00:00"
