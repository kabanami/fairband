"""Normalized statement values: one row per field per period, citing the response it came from.

``value`` is decimal text; a field that is absent, null or rejected has no value and a
``missing_reason``. A later response restating a period adds rows; ``facts_for`` reads, for each
period and field, the row from the newest response (by response id, then row id).
"""

import sqlite3
from collections.abc import Sequence
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
class FactRow:
    symbol: str
    dataset: str
    period_end: date
    fiscal_year: int | None
    fiscal_period: str | None
    field: str
    value: Decimal | None
    unit: str | None
    currency: str | None
    kind: str
    estimate_method: str | None
    missing_reason: str | None
    as_of: date | None
    observed_at: datetime
    entered_at: datetime
    response_id: int


def insert_facts(conn: sqlite3.Connection, rows: Sequence[FactRow]) -> None:
    """Append the rows in one transaction."""
    stored = [
        (
            r.symbol,
            r.dataset,
            dump_date(r.period_end),
            r.fiscal_year,
            r.fiscal_period,
            r.field,
            dump_decimal(r.value),
            r.unit,
            r.currency,
            r.kind,
            r.estimate_method,
            r.missing_reason,
            dump_date(r.as_of),
            dump_stamp(r.observed_at),
            dump_stamp(r.entered_at),
            r.response_id,
        )
        for r in rows
    ]
    with transaction(conn):
        conn.executemany(
            "INSERT INTO facts (symbol, dataset, period_end, fiscal_year, fiscal_period, field,"
            " value, unit, currency, kind, estimate_method, missing_reason, as_of, observed_at,"
            " entered_at, response_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            stored,
        )


def facts_for(conn: sqlite3.Connection, symbol: str, dataset: str) -> list[FactRow]:
    """The newest row per ``(period_end, field)``, ordered by period end, then field."""
    rows = conn.execute(
        "SELECT * FROM ("
        " SELECT *, ROW_NUMBER() OVER ("
        "  PARTITION BY period_end, field ORDER BY response_id DESC, id DESC"
        " ) AS newest FROM facts WHERE symbol = ? AND dataset = ?"
        ") WHERE newest = 1 ORDER BY period_end, field",
        (symbol, dataset),
    )
    return [
        FactRow(
            symbol=r["symbol"],
            dataset=r["dataset"],
            period_end=load_date(r["period_end"]),
            fiscal_year=r["fiscal_year"],
            fiscal_period=r["fiscal_period"],
            field=r["field"],
            value=load_decimal(r["value"]),
            unit=r["unit"],
            currency=r["currency"],
            kind=r["kind"],
            estimate_method=r["estimate_method"],
            missing_reason=r["missing_reason"],
            as_of=load_date(r["as_of"]),
            observed_at=load_stamp(r["observed_at"]),
            entered_at=load_stamp(r["entered_at"]),
            response_id=r["response_id"],
        )
        for r in rows
    ]
