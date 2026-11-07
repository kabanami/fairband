"""The multiples log (spec 2026-11-06 Tier 2, 13.7): a row a company a day, the newest write of a
day replacing the older, read back oldest first, and the day the company's log began."""

import sqlite3
from datetime import UTC, date, datetime

from fairband.store.multiples import MultiplesRow, log_multiples, multiples_log_for, since

AT = datetime(2026, 10, 31, 22, 15, tzinfo=UTC)
LATER = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


def test_log_and_read(conn: sqlite3.Connection) -> None:
    assert multiples_log_for(conn, "AAPL") == [] and since(conn, "AAPL") is None
    log_multiples(conn, "AAPL", date(2026, 10, 31), 151.0, None, None, None, 8, 4, AT)
    log_multiples(conn, "AAPL", date(2026, 10, 30), 150.0, 28.3, 26.1, 22.5, 7, 3, AT)
    log_multiples(conn, "AAL", date(2026, 10, 29), 12.0, None, None, None, None, None, AT)
    # The same day again: the newest write wins.
    log_multiples(conn, "AAPL", date(2026, 10, 31), 152.5, 28.8, 0.1 + 0.2, 22.9, 9, 5, LATER)
    assert multiples_log_for(conn, "AAPL") == [
        MultiplesRow(date(2026, 10, 30), 150.0, 28.3, 26.1, 22.5, 7),
        MultiplesRow(date(2026, 10, 31), 152.5, 28.8, 0.1 + 0.2, 22.9, 9),
    ]
    assert multiples_log_for(conn, "AAL") == [
        MultiplesRow(date(2026, 10, 29), 12.0, None, None, None, None)
    ]
    assert (since(conn, "AAPL"), since(conn, "AAL"), since(conn, "HGCO")) == (
        date(2026, 10, 30),
        date(2026, 10, 29),
        None,
    )
    stored = conn.execute(
        "SELECT refresh_id, created_at FROM multiples_log WHERE symbol = 'AAPL' AND day = ?",
        ("2026-10-31",),
    ).fetchone()
    assert tuple(stored) == (5, LATER.isoformat())
    assert conn.execute("SELECT COUNT(*) FROM multiples_log").fetchone()[0] == 3


def test_a_null_never_replaces_a_figure(conn: sqlite3.Connection) -> None:
    """A later write of the day without a multiple keeps the row's figure; one with a figure
    replaces it. The price, the snapshot and the refresh are always the later write's."""
    day = date(2026, 10, 30)
    log_multiples(conn, "AAPL", day, 150.0, 28.3, 26.1, 22.5, 7, 3, AT)
    log_multiples(conn, "AAPL", day, 150.0, None, None, None, 8, 4, LATER)  # a refusal
    assert multiples_log_for(conn, "AAPL") == [MultiplesRow(day, 150.0, 28.3, 26.1, 22.5, 8)]
    log_multiples(conn, "AAPL", day, 120.0, 22.6, None, 18.0, 9, 5, LATER)  # a reprice
    assert multiples_log_for(conn, "AAPL") == [MultiplesRow(day, 120.0, 22.6, 26.1, 18.0, 9)]
