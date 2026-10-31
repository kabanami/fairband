"""Record calls compose: inside a caller's transaction they join it and leave the commit to it."""

import sqlite3
from contextlib import closing
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from fairband.store.db import connect, transaction
from fairband.store.facts import FactRow, facts_for, insert_facts
from fairband.store.vendor import record_response

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


def _response_and_facts(conn: sqlite3.Connection) -> None:
    response_id = record_response(
        conn, "fmp", "income-statement", {"symbol": "AAPL"}, "AAPL", 200, "[]", None, T0
    )
    fact = FactRow(
        symbol="AAPL",
        dataset="income-annual",
        period_end=date(2025, 9, 27),
        fiscal_year=2025,
        fiscal_period="FY",
        field="revenue",
        value=Decimal(416),
        unit="USD",
        currency="USD",
        kind="observed",
        estimate_method=None,
        missing_reason=None,
        as_of=date(2025, 9, 27),
        observed_at=T0,
        entered_at=T0,
        response_id=response_id,
    )
    insert_facts(conn, [fact])


def _counts(conn: sqlite3.Connection) -> tuple[int, int]:
    responses = conn.execute("select count(*) from vendor_responses").fetchone()[0]
    return responses, len(facts_for(conn, "AAPL", "income-annual"))


def test_a_raise_rolls_back_the_response_and_its_facts(conn: sqlite3.Connection) -> None:
    with pytest.raises(RuntimeError, match="normalizer failed"), transaction(conn):
        _response_and_facts(conn)
        assert conn.in_transaction and _counts(conn) == (1, 1)
        raise RuntimeError("normalizer failed")
    assert not conn.in_transaction
    assert _counts(conn) == (0, 0)


def test_the_response_and_its_facts_commit_together(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    with closing(connect(tmp_path / "f.db")) as other:
        with transaction(conn):
            _response_and_facts(conn)
            assert _counts(other) == (0, 0)  # not committed by the record calls
        assert not conn.in_transaction
        assert _counts(other) == (1, 1)


def test_record_calls_join_a_transaction_the_caller_began(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN")
    _response_and_facts(conn)
    assert conn.in_transaction
    conn.rollback()
    assert _counts(conn) == (0, 0)


def test_a_record_call_alone_commits(conn: sqlite3.Connection, tmp_path: Path) -> None:
    _response_and_facts(conn)
    assert not conn.in_transaction
    with closing(connect(tmp_path / "f.db")) as other:
        assert _counts(other) == (1, 1)
