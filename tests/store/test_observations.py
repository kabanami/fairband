import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from fairband.store.observations import ObservationRow, insert_observations, observations_for

T0 = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
Q1, Q2 = date(2026, 12, 27), date(2027, 3, 27)


def _obs(response_id: int, period: date | None, field: str, value: str | None) -> ObservationRow:
    return ObservationRow(
        symbol="AAPL",
        dataset="estimate-quarter",
        period=period,
        field=field,
        value=None if value is None else Decimal(value),
        unit="USD",
        as_of=date(2026, 10, 31),
        observed_at=T0,
        entered_at=T0,
        response_id=response_id,
    )


def test_insert_observations_and_observations_for(
    conn: sqlite3.Connection, new_response: Callable[[], int]
) -> None:
    response_id = new_response()
    eps = _obs(response_id, Q2, "eps_avg", "1.70")
    analysts = replace(_obs(response_id, Q1, "analysts_eps", "28"), unit=None, as_of=None)
    moat = replace(_obs(response_id, None, "moat_score", "9"), dataset="gf-score")
    no_value = _obs(response_id, Q1, "net_income_avg", None)
    insert_observations(conn, [eps, analysts, moat, no_value])
    assert not conn.in_transaction
    assert observations_for(conn, "AAPL", "estimate-quarter") == [analysts, no_value, eps]
    assert observations_for(conn, "AAPL", "gf-score") == [moat]
    assert observations_for(conn, "MSFT", "gf-score") == []
    rows = conn.execute("select period, value from observations order by id")
    assert [tuple(r) for r in rows] == [
        ("2027-03-27", "1.70"),
        ("2026-12-27", "28"),
        (None, "9"),
        ("2026-12-27", None),
    ]


def test_observations_for_returns_newest_response_per_period_field(
    conn: sqlite3.Connection, new_response: Callable[[], int]
) -> None:
    older, newer = new_response(), new_response()
    fresh_moat = replace(_obs(newer, None, "moat_score", "8"), dataset="gf-score")
    insert_observations(conn, [fresh_moat])
    kept = replace(_obs(older, None, "z2score", "7.1"), dataset="gf-score")
    stale_moat = replace(_obs(older, None, "moat_score", "9"), dataset="gf-score")
    insert_observations(conn, [stale_moat, kept])
    estimate = _obs(older, Q1, "eps_avg", "1.60")
    revised = _obs(older, Q1, "eps_avg", "1.65")
    insert_observations(conn, [estimate, revised])
    assert observations_for(conn, "AAPL", "gf-score") == [fresh_moat, kept]
    assert observations_for(conn, "AAPL", "estimate-quarter") == [revised]


def test_insert_observations_is_one_transaction(
    conn: sqlite3.Connection, new_response: Callable[[], int]
) -> None:
    response_id = new_response()
    with pytest.raises(sqlite3.IntegrityError):
        insert_observations(
            conn,
            [_obs(response_id, Q1, "eps_avg", "1"), _obs(response_id + 99, Q2, "eps_avg", "1")],
        )
    assert not conn.in_transaction
    assert observations_for(conn, "AAPL", "estimate-quarter") == []
