import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from fairband.engine import METHOD_VERSION
from fairband.engine.route import refusal_result
from fairband.engine.types import (
    Flag,
    Levels,
    PhaseEvidence,
    ValuationResult,
    result_to_json,
)
from fairband.policy import load_policy
from fairband.store.snapshots import (
    SnapshotRow,
    insert_snapshot,
    latest_snapshot,
    latest_snapshots,
)

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


def _at(when: datetime = T0) -> Callable[[], datetime]:
    return lambda: when


def _result(symbol: str, value: float = 100.0) -> ValuationResult:
    return ValuationResult(
        symbol=symbol,
        route="mature-growth",
        value=value,
        levels=Levels(buy=0.65 * value, fair_low=0.85 * value, fair_high=1.15 * value, trim=150.0),
        stance5="HOLD",
        stance3="hold",
        price=120.5,
        price_date=date(2026, 10, 30),
        data_date=date(2026, 10, 29),
        valid_until=date(2027, 1, 28),
        phase=PhaseEvidence(
            phase="Mature Growth",
            reason=None,
            years_used=10,
            growth_3y=0.08,
            growth_word="moderate",
            growth_decile=6,
            revenue_slope=1.2,
            margin=0.3,
            margin_slope=0.01,
            margin_direction="rising",
            fcf_sign="positive",
            dickinson="mature",
            checks=(),
        ),
        inputs=(),
        intermediates={"aggregate_roic": 0.3},
        flags=(
            Flag(code="few-analysts", word="few analysts", sentence="Year 3 has 4 analysts."),
            Flag(code="value-spread", word="spread", sentence="The value moves 40%."),
        ),
        refusal=None,
        policy_version="fairband-policy-v1",
        method_version=METHOD_VERSION,
        deciles_refresh_id=None,
    )


def test_insert_snapshot_and_latest_snapshot(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    refresh_id, deciles_id = new_refresh(), new_refresh()
    result = replace(_result("MSFT"), deciles_refresh_id=deciles_id)
    snapshot_id = insert_snapshot(conn, result, refresh_id, clock=_at())
    assert not conn.in_transaction
    assert latest_snapshot(conn, "MSFT") == SnapshotRow(
        id=snapshot_id,
        symbol="MSFT",
        refresh_id=refresh_id,
        deciles_refresh_id=deciles_id,
        created_at=T0,
        phase="Mature Growth",
        route="mature-growth",
        value=100.0,
        buy_level=65.0,
        fair_low=85.0,
        fair_high=1.15 * 100.0,
        trim_level=150.0,
        price=120.5,
        stance5="HOLD",
        stance3="hold",
        price_date=date(2026, 10, 30),
        data_date=date(2026, 10, 29),
        valid_until=date(2027, 1, 28),
        flags=("few-analysts", "value-spread"),
        refusal=None,
        policy_version="fairband-policy-v1",
        method_version=METHOD_VERSION,
        result=result,
    )
    assert latest_snapshot(conn, "AAPL") is None


def test_snapshot_columns_keep_exact_floats(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    result = _result("MSFT", value=0.1 + 0.2)
    insert_snapshot(conn, result, new_refresh(), clock=_at())
    row = conn.execute("select * from snapshots").fetchone()
    expected: dict[str, Any] = {
        "value": "0.30000000000000004",
        "fair_high": repr(1.15 * (0.1 + 0.2)),
        "price": "120.5",
        "phase": "Mature Growth",
        "flags": '["few-analysts", "value-spread"]',
        "created_at": "2026-11-01T09:30:00+00:00",
        "price_date": "2026-10-30",
        "valid_until": "2027-01-28",
        "deciles_refresh_id": None,
        "result": result_to_json(result),
    }
    assert {k: row[k] for k in expected} == expected
    stored = latest_snapshot(conn, "MSFT")
    assert stored is not None and stored.value == 0.1 + 0.2


def test_refusal_snapshot_keeps_nulls(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    refusal = refusal_result(
        "BANK",
        "no positive forward anchor",
        load_policy(),
        date(2026, 10, 29),
        price=41.0,
        price_date=date(2026, 10, 30),
    )
    insert_snapshot(conn, refusal, new_refresh(), clock=_at())
    row = latest_snapshot(conn, "BANK")
    assert row is not None and row.result == refusal
    assert (row.value, row.buy_level, row.fair_low, row.fair_high, row.trim_level) == (None,) * 5
    assert (row.phase, row.route, row.stance5, row.stance3) == (None,) * 4
    assert (row.refusal, row.price, row.flags) == ("no positive forward anchor", 41.0, ())


def test_priceless_refusal_snapshot_round_trips(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    refusal = refusal_result("NEW", "data fetch failed: quote", load_policy(), date(2026, 10, 31))
    assert (refusal.price, refusal.price_date) == (None, None)
    snapshot_id = insert_snapshot(conn, refusal, new_refresh(), clock=_at())
    row = latest_snapshot(conn, "NEW")
    assert row is not None and row.id == snapshot_id and row.result == refusal
    assert (row.price, row.price_date, row.refusal) == (None, None, "data fetch failed: quote")
    stored = conn.execute("select price, price_date from snapshots").fetchone()
    assert tuple(stored) == (None, None)


def test_insert_snapshot_refuses_a_nan_before_writing(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    refresh_id = new_refresh()
    with pytest.raises(ValueError, match="not JSON compliant"):
        insert_snapshot(conn, _result("MSFT", value=float("nan")), refresh_id, clock=_at())
    assert not conn.in_transaction
    assert latest_snapshots(conn) == []


def test_latest_snapshots_one_per_symbol(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    first, second = new_refresh(), new_refresh()
    later = _at(datetime(2026, 11, 2, tzinfo=UTC))
    insert_snapshot(conn, _result("MSFT", 100.0), first, clock=_at())
    insert_snapshot(conn, _result("AAPL", 200.0), first, clock=_at())
    insert_snapshot(conn, _result("MSFT", 110.0), second, clock=later)
    rows = latest_snapshots(conn)
    assert [(r.symbol, r.refresh_id, r.value) for r in rows] == [
        ("AAPL", first, 200.0),
        ("MSFT", second, 110.0),
    ]
    assert rows[1] == latest_snapshot(conn, "MSFT")
    assert rows[1].created_at == datetime(2026, 11, 2, tzinfo=UTC)
