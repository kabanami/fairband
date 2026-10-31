"""The conversions between Python values and the store's text columns.

A ``Decimal`` is stored as its canonical string and a ``float`` as its ``repr``, so either reads
back exactly. Dates are ISO ``YYYY-MM-DD``; timestamps are RFC 3339 in UTC, and a timestamp
without a time zone is refused. ``None`` is NULL throughout.
"""

import sqlite3
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import overload


def dump_decimal(x: Decimal | None) -> str | None:
    return None if x is None else str(x)


def load_decimal(s: str | None) -> Decimal | None:
    return None if s is None else Decimal(s)


def dump_float(x: float | None) -> str | None:
    return None if x is None else repr(x)


def load_float(s: str | None) -> float | None:
    return None if s is None else float(s)


@overload
def dump_date(d: date) -> str: ...
@overload
def dump_date(d: None) -> None: ...
def dump_date(d: date | None) -> str | None:
    return None if d is None else d.isoformat()


@overload
def load_date(s: str) -> date: ...
@overload
def load_date(s: None) -> None: ...
def load_date(s: str | None) -> date | None:
    return None if s is None else date.fromisoformat(s)


@overload
def dump_stamp(dt: datetime) -> str: ...
@overload
def dump_stamp(dt: None) -> None: ...
def dump_stamp(dt: datetime | None) -> str | None:
    """The UTC RFC 3339 text of an aware timestamp; ``ValueError`` for a naive one."""
    if dt is None:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"timestamp {dt.isoformat()} has no time zone")
    return dt.astimezone(UTC).isoformat()


@overload
def load_stamp(s: str) -> datetime: ...
@overload
def load_stamp(s: None) -> None: ...
def load_stamp(s: str | None) -> datetime | None:
    return None if s is None else datetime.fromisoformat(s)


def inserted_id(cursor: sqlite3.Cursor) -> int:
    """The row id an ``INSERT`` just assigned."""
    if cursor.lastrowid is None:
        raise RuntimeError("the insert assigned no row id")
    return cursor.lastrowid
