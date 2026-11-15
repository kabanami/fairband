"""The guidance records an agent writes on a company (spec 2026-11-06 Tier 2, 9; ``method.md``
14.9): a figure the company itself gave on an earnings call for a future period.

A record: the company, the metric (one of ``METRICS``), the period (a fiscal year, ``2026``, or a
quarter, ``2026Q3``), its low and its high (equal for a point; a percent as a fraction), the
basis (one of ``BASES``), ``as_of`` the call's date, the sentence verbatim, the source (the
transcript's ``response:`` ref, or a filing), and the writer and the time. ``net_income`` is a
total in the reporting currency, the net income that belongs to the company's shareholders, as
its EPS does (spec 2026-11-14 9). The store computes the midpoint, ``(low + high) / 2``, and, for
a fiscal-year ``revenue``, ``eps`` or ``net_income`` record on the ``gaap`` basis given the actual
of the year before the guided one (``year_before``), the step, the midpoint over that actual less
one, so the agent never computes a rate; no step otherwise, nor on a base at or below zero, from
which growth has no meaning. The actual is the statement's line, a GAAP figure, so a record on
another basis takes no step: an adjusted figure over a GAAP actual is a rate across two bases, no
growth, and a constant-currency figure over it is growth at constant currency, a rate the agent
derives and names as such. A step such a record holds from before this rule is not read. A record
of a money metric may name the currency the company guides in (``store.currency``; spec
2026-11-15 9.1), the code stored as given; none is the company's reporting currency. A record
whose currency is named and is not the actual's (``base_currency``, the currency of the statement
the actual is read from) takes no step either: its midpoint over an actual in another currency is
no growth (spec 2026-11-15 9.2).

The call's date orders a company's records of one metric, period and basis, of which one at most
is current (``superseded_by`` empty), whatever the currency of either: a GAAP and an adjusted
figure of one call both stay current.
A new record of a call on or after the current record's supersedes it, and the old record keeps
its figures and names its successor in ``superseded_by``; a new record of an earlier call, the
previous call's figure written late, is stored already superseded by the current one. Every
record stays, so a later report can read the track record. ``guidance_for`` lists a
company's newest first; ``guidance_row`` reads one by its id. ``UNITS`` is each metric's unit as
the refs read it. ``anchor_year`` is the fiscal year a record guides when it may back an NTM
anchor override: a gaap record of one of the anchor's metrics for a fiscal year, ``eps`` or
``net_income`` for the NTM EPS and ``revenue`` for the NTM revenue (``method.md`` 14.3).

A refused value raises ``ValueError`` with the sentence the writer can act on. Each write is one
transaction; it joins the caller's when there is one, so the caller's ledger row commits with it.
"""

import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from fairband.engine.overrides import ANCHOR_METRICS
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
from fairband.store.currency import check_currency
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

METRICS = (
    "revenue",
    "eps",
    "net_income",
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
    "net_income": "currency",
    "free_cash_flow": "currency",
    "capex": "currency",
    "eps": "per-share",
    "operating_margin": "percent",
    "revenue_growth": "percent",
    "eps_growth": "percent",
}
# The metrics a fiscal-year record steps from the actual of the year before the guided one.
STEPPED = frozenset({"revenue", "eps", "net_income"})
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
    currency: str | None = None  # as stored: none is the reporting currency


def year_before(metric: str, period: str) -> int | None:
    """The fiscal year a record of ``metric`` for ``period`` steps from, the year before the
    guided one: for a fiscal-year revenue, EPS or net income record only, ``None`` for any
    other."""
    found = _PERIOD.fullmatch(period)
    if metric not in STEPPED or found is None or found[2] is not None:
        return None
    return int(found[1]) - 1


def fiscal_year(period: str) -> int | None:
    """The fiscal year ``period`` names; ``None`` for a quarter or a period that is not one."""
    found = _PERIOD.fullmatch(period)
    return None if found is None or found[2] is not None else int(found[1])


def anchor_year(tag: str, row: GuidanceRow) -> int | None:
    """The fiscal year ``row`` guides when it may back an override of the NTM anchor ``tag``: a
    gaap record of one of the anchor's metrics (``overrides.ANCHOR_METRICS``) for a fiscal year;
    ``None`` for any other record or tag."""
    if row.metric not in ANCHOR_METRICS.get(tag, frozenset()) or row.basis != "gaap":
        return None
    return fiscal_year(row.period)


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
    *,
    currency: str | None = None,
    base_currency: str | None = None,
) -> int:
    """Record the guidance, in ``currency`` when one is named, its step from ``base_actual`` (the
    actual on file of the year before the guided one, or ``None``, in ``base_currency``) when it
    takes one, a ``gaap`` record alone and none in a named currency that is not the actual's, and
    order it against the company's current record of the same metric, period and basis by the
    call's date (module docstring); return its id."""
    symbol = exchange_symbol(symbol)
    _check(metric, period, low, high, basis, text, source)
    check_currency(currency, UNITS[metric])
    midpoint = (low + high) / 2
    step = None
    stepped = basis == "gaap" and year_before(metric, period) is not None
    same = currency is None or currency == base_currency
    if stepped and same and base_actual is not None and base_actual > 0:
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
            " text, source, principal, actor, client, created_at, superseded_by, currency)"
            f" VALUES ({', '.join('?' * (len(row) + 2))})",
            (*row, current["id"] if later else None, currency),
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
        # a record written before the step was kept to the gaap basis may hold one: not read
        step=load_float(row["step"]) if row["basis"] == "gaap" else None,
        basis=row["basis"],
        as_of=load_date(row["as_of"]),
        text=row["text"],
        source=row["source"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        created_at=load_stamp(row["created_at"]),
        superseded_by=row["superseded_by"],
        currency=row["currency"],
    )
