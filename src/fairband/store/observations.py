"""Dated vendor observations: estimates, quotes, street actuals, earnings dates and vendor scores.

One row per field per period (``period`` is ``None`` for a value with no period, such as a moat
score), citing the response it came from; ``value`` is decimal text. ``observations_for`` reads,
for each period and field, the row from the newest response (by response id, then row id).
``answer_observations`` reads one response whole: the newest that holds a row of the dataset for
the symbol, so a period the vendor dropped or moved in a newer answer leaves no row behind.
"""

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from fairband.store._codec import (
    dump_date,
    dump_decimal,
    dump_stamp,
    load_date,
    load_decimal,
    load_stamp,
)
from fairband.store.db import transaction


@dataclass(frozen=True)
class ObservationRow:
    symbol: str
    dataset: str
    period: date | None
    field: str
    value: Decimal | None
    unit: str | None
    as_of: date | None
    observed_at: datetime
    entered_at: datetime
    response_id: int


def insert_observations(conn: sqlite3.Connection, rows: Sequence[ObservationRow]) -> None:
    """Append the rows in one transaction."""
    stored = [
        (
            r.symbol,
            r.dataset,
            dump_date(r.period),
            r.field,
            dump_decimal(r.value),
            r.unit,
            dump_date(r.as_of),
            dump_stamp(r.observed_at),
            dump_stamp(r.entered_at),
            r.response_id,
        )
        for r in rows
    ]
    with transaction(conn):
        conn.executemany(
            "INSERT INTO observations (symbol, dataset, period, field, value, unit, as_of,"
            " observed_at, entered_at, response_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            stored,
        )


def observations_for(conn: sqlite3.Connection, symbol: str, dataset: str) -> list[ObservationRow]:
    """The newest row per ``(period, field)``, ordered by period (``None`` first), then field."""
    rows = conn.execute(
        "SELECT * FROM ("
        " SELECT *, ROW_NUMBER() OVER ("
        "  PARTITION BY period, field ORDER BY response_id DESC, id DESC"
        " ) AS newest FROM observations WHERE symbol = ? AND dataset = ?"
        ") WHERE newest = 1 ORDER BY period, field",
        (symbol, dataset),
    )
    return _loaded(rows)


def answer_observations(
    conn: sqlite3.Connection, symbol: str, dataset: str
) -> list[ObservationRow]:
    """Every row of the newest response (the largest response id) that holds a row of ``dataset``
    for ``symbol``, ordered by period (``None`` first), then field, then row id; empty when no
    response holds one. Rows of an older response are not read, whatever periods they hold."""
    rows = conn.execute(
        "SELECT * FROM observations WHERE symbol = ? AND dataset = ? AND response_id = ("
        " SELECT MAX(response_id) FROM observations WHERE symbol = ? AND dataset = ?"
        ") ORDER BY period, field, id",
        (symbol, dataset, symbol, dataset),
    )
    return _loaded(rows)


def _loaded(rows: Iterable[sqlite3.Row]) -> list[ObservationRow]:
    return [
        ObservationRow(
            symbol=r["symbol"],
            dataset=r["dataset"],
            period=load_date(r["period"]),
            field=r["field"],
            value=load_decimal(r["value"]),
            unit=r["unit"],
            as_of=load_date(r["as_of"]),
            observed_at=load_stamp(r["observed_at"]),
            entered_at=load_stamp(r["entered_at"]),
            response_id=r["response_id"],
        )
        for r in rows
    ]
