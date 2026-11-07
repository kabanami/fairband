"""The guidance records an agent writes on a company (spec 2026-11-06 Tier 2, 9; ``method.md``
14.9): a figure the company itself gave on an earnings call for a future period.

A record: the company, the metric (one of ``METRICS``), the period (a fiscal year, ``2026``, or a
quarter, ``2026Q3``), its low and its high (equal for a point; a percent as a fraction), the
basis (one of ``BASES``), ``as_of`` the call's date, the sentence verbatim, the source (the
transcript's ``response:`` ref, or a filing), and the writer and the time. The store computes the
midpoint, ``(low + high) / 2``, and, for a fiscal-year ``revenue`` or ``eps`` record given the
base year's actual (``base_year``: the fiscal year before the guided one), the step, the midpoint
over that actual less one, so the agent never computes a rate; no step otherwise, nor on a base
at or below zero, from which growth has no meaning.

The call's date orders a company's records of one metric, period and basis, of which one at most
is current (``superseded_by`` empty): a GAAP and an adjusted figure of one call both stay current.
A new record of a call on or after the current record's supersedes it, and the old record keeps
its figures and names its successor in ``superseded_by``; a new record of an earlier call, the
previous call's figure written late, is stored already superseded by the current one. Every
record stays, so a later report can read the track record. ``guidance_for`` lists a
company's newest first; ``guidance_row`` reads one by its id. ``UNITS`` is each metric's unit as
the refs read it.

A refused value raises ``ValueError`` with the sentence the writer can act on. Each write is one
transaction; it joins the caller's when there is one, so the caller's ledger row commits with it.
"""

import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from fairband.policy.settings import exchange_symbol
from fairband.store._codec import (
    dump_date,
    dump_float,
    dump_stamp,
    inserted_id,
    load_date,
    load_float,
    load_stamp,
)
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

METRICS = (
    "revenue",
    "eps",
    "operating_margin",
    "free_cash_flow",
    "capex",
    "revenue_growth",
    "eps_growth",
)
BASES = ("gaap", "adjusted", "constant-currency")
# Each metric's unit as a ``guidance:`` ref reads it; a step is a percent.
UNITS = {
    "revenue": "currency",
    "free_cash_flow": "currency",
    "capex": "currency",
    "eps": "per-share",
    "operating_margin": "percent",
    "revenue_growth": "percent",
    "eps_growth": "percent",
}
# The metrics a fiscal-year record steps from its base year's actual.
STEPPED = frozenset({"revenue", "eps"})
_PERIOD = re.compile(r"(\d{4})(Q[1-4])?")


@dataclass(frozen=True)
class GuidanceRow:
    id: int
    symbol: str
    metric: str
    period: str
    low: float
    high: float
    midpoint: float
    step: float | None
    basis: str
    as_of: date
    text: str
    source: str
    principal: Principal
    actor: str | None
    client: str | None
    created_at: datetime
    superseded_by: int | None


def base_year(metric: str, period: str) -> int | None:
    """The fiscal year a record of ``metric`` for ``period`` steps from, the year before the
    guided one: for a fiscal-year revenue or EPS record only, ``None`` for any other."""
    found = _PERIOD.fullmatch(period)
    if metric not in STEPPED or found is None or found[2] is not None:
        return None
    return int(found[1]) - 1


def insert_guidance(
    conn: sqlite3.Connection,
    symbol: str,
    metric: str,
    period: str,
    low: float,
    high: float,
    basis: str,
    as_of: date,
    text: str,
    source: str,
    writer: Writer,
    at: datetime,
    base_actual: float | None,
) -> int:
    """Record the guidance, its step from ``base_actual`` (the base year's actual on file, or
    ``None``) when it takes one, and order it against the company's current record of the same
    metric, period and basis by the call's date (module docstring); return its id."""
    symbol = exchange_symbol(symbol)
    _check(metric, period, low, high, basis, text, source)
    midpoint = (low + high) / 2
    step = None
    if base_year(metric, period) is not None and base_actual is not None and base_actual > 0:
        step = midpoint / base_actual - 1
    row = (
        symbol,
        metric,
        period,
        dump_float(low),
        dump_float(high),
        dump_float(midpoint),
        dump_float(step),
        basis,
        dump_date(as_of),
        text,
        source,
        writer.principal,
        writer.actor,
        writer.client,
        dump_stamp(at),
    )
    with transaction(conn, immediate=True):
        current = conn.execute(
            "SELECT id, as_of FROM guidance WHERE symbol = ? AND metric = ? AND period = ?"
            " AND basis = ? AND superseded_by IS NULL",
            (symbol, metric, period, basis),
        ).fetchone()
        # a record of an earlier call than the current one's is stored superseded by it
        later = current is not None and load_date(current["as_of"]) > as_of
        cursor = conn.execute(
            "INSERT INTO guidance (symbol, metric, period, low, high, midpoint, step, basis, as_of,"
            " text, source, principal, actor, client, created_at, superseded_by)"
            f" VALUES ({', '.join('?' * (len(row) + 1))})",
            (*row, current["id"] if later else None),
        )
        guidance_id = inserted_id(cursor)
        if current is not None and not later:
            conn.execute(
                "UPDATE guidance SET superseded_by = ? WHERE id = ?", (guidance_id, current["id"])
            )
    return guidance_id


def guidance_row(conn: sqlite3.Connection, guidance_id: int) -> GuidanceRow | None:
    row = conn.execute("SELECT * FROM guidance WHERE id = ?", (guidance_id,)).fetchone()
    return None if row is None else _guidance(row)


def guidance_for(conn: sqlite3.Connection, symbol: str) -> list[GuidanceRow]:
    """The company's records, newest first."""
    rows = conn.execute(
        "SELECT * FROM guidance WHERE symbol = ? ORDER BY id DESC", (exchange_symbol(symbol),)
    ).fetchall()
    return [_guidance(r) for r in rows]


def _check(
    metric: str, period: str, low: float, high: float, basis: str, text: str, source: str
) -> None:
    """Refuse a value the record cannot take, with its sentence, in the order of the fields."""
    if metric not in METRICS:
        raise ValueError(f"metric is one of {', '.join(METRICS[:-1])} or {METRICS[-1]}")
    if _PERIOD.fullmatch(period) is None:
        raise ValueError("period is a fiscal year or a quarter (2026, 2026Q3)")
    if not (math.isfinite(low) and math.isfinite(high)):
        raise ValueError("low and high are finite numbers")
    if low > high:
        raise ValueError("low is above high")
    if basis not in BASES:
        raise ValueError(f"basis is one of {', '.join(BASES[:-1])} or {BASES[-1]}")
    if not text.strip():
        raise ValueError("a guidance record needs its text")
    if not source.strip():
        raise ValueError("a guidance record needs its source")


def _guidance(row: sqlite3.Row) -> GuidanceRow:
    low, high, midpoint = (load_float(row[k]) for k in ("low", "high", "midpoint"))
    assert low is not None and high is not None and midpoint is not None  # NOT NULL columns
    return GuidanceRow(
        id=row["id"],
        symbol=row["symbol"],
        metric=row["metric"],
        period=row["period"],
        low=low,
        high=high,
        midpoint=midpoint,
        step=load_float(row["step"]),
        basis=row["basis"],
        as_of=load_date(row["as_of"]),
        text=row["text"],
        source=row["source"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        created_at=load_stamp(row["created_at"]),
        superseded_by=row["superseded_by"],
    )
