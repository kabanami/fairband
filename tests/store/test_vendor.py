import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from fairband.store.vendor import (
    ResponseRow,
    latest_response,
    record_response,
    response_payload,
)

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
ANNUAL = {"symbol": "AAPL", "period": "annual", "limit": "11"}


def _ok(conn: sqlite3.Connection, at: datetime, params: dict[str, str] = ANNUAL) -> int:
    return record_response(
        conn, "fmp", "income-statement", params, "AAPL", 200, '[{"revenue": 1}]', None, at
    )


def test_record_response_and_latest_response(conn: sqlite3.Connection) -> None:
    assert latest_response(conn, "fmp", "income-statement", "AAPL", ANNUAL) is None
    newest = _ok(conn, T0 + timedelta(hours=1))
    _ok(conn, T0)  # recorded later, observed earlier
    later = [T0 + timedelta(days=d) for d in range(1, 6)]
    record_response(conn, "fmp", "income-statement", ANNUAL, "AAPL", 500, "oops", None, later[0])
    record_response(
        conn, "fmp", "income-statement", ANNUAL, "AAPL", None, None, "timeout", later[1]
    )
    _ok(conn, later[2], {**ANNUAL, "limit": "5"})
    record_response(conn, "fmp", "balance", ANNUAL, "AAPL", 200, "[]", None, later[3])
    record_response(conn, "fmp", "income-statement", ANNUAL, "MSFT", 200, "[]", None, later[4])
    assert not conn.in_transaction
    assert latest_response(conn, "fmp", "income-statement", "AAPL", ANNUAL) == ResponseRow(
        id=newest,
        provider="fmp",
        endpoint="income-statement",
        params=ANNUAL,
        symbol="AAPL",
        http_status=200,
        observed_at=T0 + timedelta(hours=1),
        error=None,
    )


def test_latest_response_skips_a_200_with_an_error(conn: sqlite3.Connection) -> None:
    clean = _ok(conn, T0)
    unusable = "unusable payload: []"
    later = T0 + timedelta(hours=1)
    record_response(conn, "fmp", "income-statement", ANNUAL, "AAPL", 200, "[]", unusable, later)
    found = latest_response(conn, "fmp", "income-statement", "AAPL", ANNUAL)
    assert found is not None and (found.id, found.error) == (clean, None)


def test_latest_response_matches_params_in_any_order(conn: sqlite3.Connection) -> None:
    response_id = _ok(conn, T0)
    reordered = {"limit": "11", "period": "annual", "symbol": "AAPL"}
    found = latest_response(conn, "fmp", "income-statement", "AAPL", reordered)
    assert found is not None and found.id == response_id
    stored = conn.execute("select params from vendor_responses").fetchone()[0]
    assert stored == '{"limit": "11", "period": "annual", "symbol": "AAPL"}'
    assert latest_response(conn, "fmp", "income-statement", "AAPL", {"symbol": "AAPL"}) is None


def test_latest_response_without_symbol(conn: sqlite3.Connection) -> None:
    params = {"exchange": "NYSE,NASDAQ,AMEX"}
    response_id = record_response(
        conn, "fmp", "company-screener", params, None, 200, "[]", None, T0
    )
    found = latest_response(conn, "fmp", "company-screener", None, params)
    assert found is not None and found.id == response_id and found.symbol is None


def test_response_payload(conn: sqlite3.Connection) -> None:
    ok = _ok(conn, T0)
    failed = record_response(
        conn, "gurufocus", "summary", {}, "AAPL", None, None, "no GuruFocus key", T0
    )
    assert response_payload(conn, ok) == '[{"revenue": 1}]'
    assert response_payload(conn, failed) is None
    assert response_payload(conn, failed + 1) is None


def test_observed_at_is_stored_in_utc(conn: sqlite3.Connection) -> None:
    new_york = datetime(2026, 11, 1, 5, 30, tzinfo=timezone(timedelta(hours=-4)))
    response_id = _ok(conn, new_york)
    stored = conn.execute("select observed_at from vendor_responses").fetchone()[0]
    assert stored == "2026-11-01T09:30:00+00:00"
    found = latest_response(conn, "fmp", "income-statement", "AAPL", ANNUAL)
    assert found is not None and found.id == response_id and found.observed_at == T0


def test_naive_observed_at_is_refused(conn: sqlite3.Connection) -> None:
    with pytest.raises(ValueError, match="time zone"):
        _ok(conn, datetime(2026, 11, 1, 9, 30))
    assert conn.execute("select count(*) from vendor_responses").fetchone()[0] == 0
