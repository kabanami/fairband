import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from fairband.store.facts import FactRow, facts_for, fields_stored, insert_facts

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
T1 = datetime(2026, 11, 1, 9, 31, tzinfo=UTC)


def _fact(response_id: int, period_end: date, field: str, value: str | None) -> FactRow:
    return FactRow(
        symbol="AAPL",
        dataset="income-annual",
        period_end=period_end,
        fiscal_year=period_end.year,
        fiscal_period="FY",
        field=field,
        value=None if value is None else Decimal(value),
        unit="USD",
        currency="USD",
        kind="observed",
        estimate_method=None,
        missing_reason="null" if value is None else None,
        as_of=period_end,
        observed_at=T0,
        entered_at=T1,
        response_id=response_id,
    )


FY24, FY25 = date(2024, 9, 28), date(2025, 9, 27)


def test_insert_facts_and_facts_for(
    conn: sqlite3.Connection, new_response: Callable[[], int]
) -> None:
    response_id = new_response()
    revenue = _fact(response_id, FY25, "revenue", "416161000000.00")
    eps = _fact(response_id, FY25, "eps", "-0.10")
    missing = _fact(response_id, FY24, "revenue", None)
    estimate = replace(
        _fact(response_id, FY24, "intangibles_ex_goodwill", "1E+9"),
        kind="estimate",
        estimate_method="bs10-intangibles-total-v1",
        as_of=None,
        fiscal_year=None,
        fiscal_period=None,
        unit=None,
        currency=None,
    )
    insert_facts(conn, [revenue, eps, missing, estimate])
    assert not conn.in_transaction
    assert facts_for(conn, "AAPL", "income-annual") == [estimate, missing, eps, revenue]
    assert facts_for(conn, "AAPL", "balance-annual") == []
    assert facts_for(conn, "MSFT", "income-annual") == []


def test_facts_for_returns_newest_response_per_period_field(
    conn: sqlite3.Connection, new_response: Callable[[], int]
) -> None:
    older, newer = new_response(), new_response()
    # The newer response's rows go in first: the newest response wins, not the newest row.
    restated = _fact(newer, FY25, "revenue", "111")
    insert_facts(conn, [restated])
    kept_fy24 = _fact(older, FY24, "revenue", "100")
    kept_income = _fact(older, FY25, "netIncome", "10")
    insert_facts(conn, [kept_fy24, _fact(older, FY25, "revenue", "110"), kept_income])
    # Within one response the later row wins.
    corrected = _fact(newer, FY25, "eps", "2.5")
    insert_facts(conn, [_fact(newer, FY25, "eps", "2.4"), corrected])
    assert facts_for(conn, "AAPL", "income-annual") == [kept_fy24, corrected, kept_income, restated]


def test_fact_columns_hold_decimal_text(
    conn: sqlite3.Connection, new_response: Callable[[], int]
) -> None:
    response_id = new_response()
    insert_facts(conn, [_fact(response_id, FY25, "revenue", "416161000000.00")])
    insert_facts(conn, [_fact(response_id, FY24, "revenue", None)])
    rows = conn.execute("select period_end, value, as_of, entered_at from facts order by id")
    assert [tuple(r) for r in rows] == [
        ("2025-09-27", "416161000000.00", "2025-09-27", "2026-11-01T09:31:00+00:00"),
        ("2024-09-28", None, "2024-09-28", "2026-11-01T09:31:00+00:00"),
    ]


def test_insert_facts_is_one_transaction(
    conn: sqlite3.Connection, new_response: Callable[[], int]
) -> None:
    response_id = new_response()
    with pytest.raises(sqlite3.IntegrityError):
        insert_facts(
            conn,
            [_fact(response_id, FY25, "revenue", "1"), _fact(response_id + 99, FY24, "eps", "1")],
        )
    assert not conn.in_transaction
    assert facts_for(conn, "AAPL", "income-annual") == []


def test_fields_stored(conn: sqlite3.Connection, new_response: Callable[[], int]) -> None:
    first, second = new_response(), new_response()
    insert_facts(
        conn,
        [
            _fact(first, FY24, "revenue", "1"),
            _fact(first, FY25, "revenue", "2"),
            _fact(first, FY25, "eps", None),  # a field without a value is stored too
            _fact(second, FY25, "netIncome", "3"),
        ],
    )
    assert fields_stored(conn, first) == {"revenue", "eps"}
    assert fields_stored(conn, second) == {"netIncome"}
    assert fields_stored(conn, second + 1) == set()
