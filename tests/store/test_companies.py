import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from fairband.store.companies import (
    CompanyRow,
    insert_companies,
    latest_companies,
    latest_company,
)

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


def _company(symbol: str, refresh_id: int, eligible: bool = True) -> CompanyRow:
    return CompanyRow(
        symbol=symbol,
        refresh_id=refresh_id,
        name=f"{symbol} Inc.",
        exchange="NASDAQ",
        sector="Technology",
        industry="Consumer Electronics",
        country="US",
        currency="USD",
        is_adr=False,
        cap_band="mega",
        market_cap=Decimal("3500000000000.50"),
        eligible=eligible,
        exclusion_reason=None if eligible else "excluded industry: Banks",
        observed_at=T0,
    )


def test_insert_companies_and_latest_companies(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    assert latest_companies(conn) == []
    first, second = new_refresh(), new_refresh()
    old = [_company("AAPL", first), _company("XOM", first)]
    aapl, msft = _company("AAPL", second), replace(_company("MSFT", second), is_adr=True)
    bank = replace(_company("BANK", second, eligible=False), market_cap=None)
    insert_companies(conn, old)
    insert_companies(conn, [msft, bank, aapl])
    assert not conn.in_transaction
    assert latest_companies(conn) == [aapl, msft]
    assert latest_companies(conn, eligible_only=False) == [aapl, bank, msft]


def test_latest_company_reads_the_newest_refresh_for_the_symbol(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    first, second = new_refresh(), new_refresh()
    xom = _company("XOM", first)
    insert_companies(conn, [_company("AAPL", first), xom])
    newer = replace(_company("AAPL", second), market_cap=Decimal(3600000000000))
    insert_companies(conn, [newer])
    assert latest_company(conn, "AAPL") == newer
    assert latest_company(conn, "XOM") == xom
    assert latest_company(conn, "NONE") is None


def test_company_columns_hold_decimal_text_and_utc_time(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    refresh_id = new_refresh()
    insert_companies(conn, [_company("AAPL", refresh_id)])
    row = conn.execute("select market_cap, is_adr, eligible, observed_at from companies").fetchone()
    assert tuple(row) == ("3500000000000.50", 0, 1, "2026-11-01T09:30:00+00:00")


def test_insert_companies_is_one_transaction(
    conn: sqlite3.Connection, new_refresh: Callable[[], int]
) -> None:
    refresh_id = new_refresh()
    with pytest.raises(sqlite3.IntegrityError):
        insert_companies(conn, [_company("AAPL", refresh_id), _company("MSFT", refresh_id + 99)])
    assert not conn.in_transaction
    assert latest_companies(conn, eligible_only=False) == []
