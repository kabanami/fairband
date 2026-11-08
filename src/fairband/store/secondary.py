"""The secondary valuations and the derivations (spec 2026-11-06 Tier 2, 11 and 13.4; ``method.md``
15).

A secondary valuation is stored as of the snapshot it was made on, and never changed: its form,
``parts`` or ``drivers``; on the parts form its parts as JSON, each with its path, its terminal
growth, its note, its present values, its terminal, the terminal's present value and its value
(an empty list on the drivers form); on the drivers form its drivers as JSON (``years``,
``revenue_growth``, ``operating_margin``, ``tax_rate``, ``sales_to_capital``,
``terminal_growth``) and its projection as JSON, ``{trailing_revenue, terminal_return, years:
[{t, revenue, ebit, nopat, reinvestment, fcff, pv}], terminal_fcff, terminal, terminal_pv}``, the
trailing revenue and the terminal return it was projected from beside the table, so the value
rebuilds (both NULL on the parts form); its grid as JSON, ``{rows, cols, cells}``, the rows the
terminal growths, or the shifts on the parts form (``GRID_ROWS``), NULL where the valuation has
none and on a ``fairband-secondary/1`` record; the firm value, the debt, the cash, the diluted
shares, the equity, the value a share and the levels as ``repr`` text, so each float reads back
exactly (JSON writes a float as its ``repr`` too); price ÷ value as a REAL and the designation's
word, none of the four levels or the two on a value a share at or below zero; the reason and the
evidence (JSON ``{kind, ref, note, figure}`` items); where the debt and the cash came from
(``BalanceSource``), ``statements``, ``agent`` or ``none`` (no line on file, the figure 0.0); the
writer and the time; the policy version, the settings hash and the deciles refresh it ran under;
and the engine's ``SECONDARY_METHOD`` (a record written under ``fairband-secondary/1`` keeps it).
``latest_secondary`` reads the company's newest, ``latest_secondaries`` every company's newest in
one read (the screen's rows), ``secondaries_for`` every one, newest first, and ``secondary_row``
one by its id.

``no_secondary`` says why a company can have none on a snapshot, the four refusals of the secondary
route that no call can meet (``method.md`` 15.4), in the route's order: the route values the
company (the snapshot has a value), the review values the company (the company's current review
counts on the snapshot and has a value: an override routed it), the secondary valuation being the
fallback where neither does (plan 3); a foreign filer (``foreign_filer``: the snapshot refused as
one, or the universe row an ADR or in a currency other than USD, a row naming none leaving it to
the snapshot); and no positive diluted share count (``diluted_shares``: the snapshot's
``shares_diluted`` input, else its intermediates' ``shares``). The caller passes the review:
whether one counts on a snapshot is the reports' rule (``reports.refs.same_snapshot``), which reads
this module.

A derivation is one operation of an agent's arithmetic over two references: its operation, its
refs, its years (a cagr's, else none), its value as ``repr`` text (none where the operation is
undefined) and its unit, the writer and the time.

Each write is one transaction; it joins the caller's when there is one, so the caller's ledger row
commits with it.
"""

import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from fairband.engine.route import FOREIGN_FILER
from fairband.engine.secondary import (
    SECONDARY_METHOD,
    Form,
    Part,
    Projection,
    SecondaryGrid,
    SecondaryValuation,
)
from fairband.engine.types import ValuationResult
from fairband.store._codec import dump_float, dump_stamp, inserted_id, load_float, load_stamp
from fairband.store.companies import latest_company
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer
from fairband.store.reviews import ReviewRow
from fairband.store.snapshots import SnapshotRow

Operation = Literal["ratio", "difference", "sum", "growth", "cagr"]
# Where a secondary valuation's debt or cash came from: the newest balance sheet; the agent's
# figure or an applied balance override; or no line on file, counted as nil.
BalanceSource = Literal["statements", "agent", "none"]
# What a grid's rows hold, by form: the terminal growths; on the parts form the shift applied to
# every part's terminal growth, since the parts' growths differ.
GRID_ROWS: dict[Form, Literal["growths", "shifts"]] = {"drivers": "growths", "parts": "shifts"}


@dataclass(frozen=True)
class SecondaryRow:
    id: int
    symbol: str
    snapshot_id: int
    created_at: datetime
    principal: Principal
    actor: str | None
    client: str | None
    parts: tuple[dict[str, Any], ...]
    firm_value: float
    debt: float
    cash: float
    shares: float
    equity: float
    value_per_share: float
    buy_level: float | None
    fair_low: float | None
    fair_high: float | None
    trim_level: float | None
    price_to_value: float | None
    designation: str | None
    reason: str
    evidence: tuple[dict[str, Any], ...]
    debt_source: BalanceSource
    cash_source: BalanceSource
    policy_version: str
    settings_hash: str
    deciles_refresh_id: int | None
    secondary_method: str
    form: Form
    drivers: dict[str, Any] | None
    projection: dict[str, Any] | None
    grid: dict[str, Any] | None


@dataclass(frozen=True)
class DerivationRow:
    id: int
    symbol: str
    operation: str
    a: str
    b: str
    years: int | None
    value: float | None
    unit: str | None
    principal: Principal
    actor: str | None
    client: str | None
    at: datetime


def insert_secondary(
    conn: sqlite3.Connection,
    symbol: str,
    snapshot_id: int,
    parts: Sequence[Part],
    valuation: SecondaryValuation,
    reason: str,
    evidence: Sequence[Mapping[str, Any]],
    debt_source: BalanceSource,
    cash_source: BalanceSource,
    policy_version: str,
    settings_hash: str,
    deciles_refresh_id: int | None,
    writer: Writer,
    at: datetime,
    *,
    revenue_0: float | None = None,
    roic_t: float | None = None,
) -> int:
    """Store ``valuation`` on snapshot ``snapshot_id``; return its id. ``parts`` are the parts
    it valued, none on the drivers form; ``revenue_0`` and ``roic_t``, the trailing revenue and
    the terminal return the drivers were projected from, which the drivers form requires."""
    projection: dict[str, Any] | None = None
    if valuation.projection is not None:
        if revenue_0 is None or roic_t is None:
            raise TypeError("the drivers form stores revenue_0 and roic_t")
        projection = _projection_json(valuation.projection, revenue_0, roic_t)
    drivers = None if valuation.drivers is None else asdict(valuation.drivers)
    levels = valuation.levels
    stored_parts = [
        {
            "name": part.name,
            "fcff": list(part.fcff),
            "terminal_growth": part.terminal_growth,
            "note": part.note,
            "pv": list(value.pv),
            "terminal": value.terminal,
            "terminal_pv": value.terminal_pv,
            "value": value.value,
        }
        for part, value in zip(parts, valuation.parts, strict=True)
    ]
    row = (
        symbol,
        snapshot_id,
        dump_stamp(at),
        writer.principal,
        writer.actor,
        writer.client,
        json.dumps(stored_parts, allow_nan=False),
        dump_float(valuation.firm_value),
        dump_float(valuation.debt),
        dump_float(valuation.cash),
        dump_float(valuation.shares),
        dump_float(valuation.equity),
        dump_float(valuation.value_per_share),
        dump_float(None if levels is None else levels.buy),
        dump_float(None if levels is None else levels.fair_low),
        dump_float(None if levels is None else levels.fair_high),
        dump_float(None if levels is None else levels.trim),
        valuation.price_to_value,
        valuation.designation,
        reason,
        json.dumps([dict(item) for item in evidence]),
        debt_source,
        cash_source,
        policy_version,
        settings_hash,
        deciles_refresh_id,
        SECONDARY_METHOD,
        valuation.form,
        _dumped(drivers),
        _dumped(projection),
        _dumped(_grid_json(valuation.grid)),
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO secondary_valuations (symbol, snapshot_id, created_at, principal, actor,"
            " client, parts, firm_value, debt, cash, shares, equity, value_per_share, buy_level,"
            " fair_low, fair_high, trim_level, price_to_value, designation, reason, evidence,"
            " debt_source, cash_source, policy_version, settings_hash, deciles_refresh_id,"
            " secondary_method, form, drivers, projection, grid)"
            f" VALUES ({', '.join('?' * len(row))})",
            row,
        )
    return inserted_id(cursor)


def latest_secondary(conn: sqlite3.Connection, symbol: str) -> SecondaryRow | None:
    """The company's newest secondary valuation, if it has one."""
    row = conn.execute(
        "SELECT * FROM secondary_valuations WHERE symbol = ? ORDER BY id DESC LIMIT 1", (symbol,)
    ).fetchone()
    return None if row is None else _secondary(row)


def latest_secondaries(conn: sqlite3.Connection) -> dict[str, SecondaryRow]:
    """The newest secondary valuation of every company that has one, by symbol."""
    rows = conn.execute(
        "SELECT * FROM secondary_valuations WHERE id IN"
        " (SELECT MAX(id) FROM secondary_valuations GROUP BY symbol) ORDER BY symbol"
    )
    return {r["symbol"]: _secondary(r) for r in rows}


def secondary_row(conn: sqlite3.Connection, secondary_id: int) -> SecondaryRow | None:
    """The secondary valuation ``secondary_id``, if there is one."""
    row = conn.execute(
        "SELECT * FROM secondary_valuations WHERE id = ?", (secondary_id,)
    ).fetchone()
    return None if row is None else _secondary(row)


def secondaries_for(conn: sqlite3.Connection, symbol: str) -> list[SecondaryRow]:
    """Every secondary valuation of the company, newest first."""
    rows = conn.execute(
        "SELECT * FROM secondary_valuations WHERE symbol = ? ORDER BY id DESC", (symbol,)
    )
    return [_secondary(r) for r in rows]


def no_secondary(
    conn: sqlite3.Connection, snapshot: SnapshotRow, review: ReviewRow | None
) -> str | None:
    """Why the company can have no secondary valuation on ``snapshot``, "the route values the
    company", "the review values the company", "foreign filer" or "no diluted share count", in
    the order the secondary route refuses them; ``None`` when it can have one. ``review`` is the
    company's current review where it counts on ``snapshot`` (rests on it or on one it reprices),
    else ``None``: the caller reads it, as the module docstring says."""
    if snapshot.value is not None:
        return "the route values the company"
    if review is not None and review.value is not None:
        return "the review values the company"
    if foreign_filer(conn, snapshot):
        return "foreign filer"
    if diluted_shares(snapshot.result) is None:
        return "no diluted share count"
    return None


def foreign_filer(conn: sqlite3.Connection, snapshot: SnapshotRow) -> bool:
    """A foreign filer: the snapshot refused as one, or the universe row an ADR or in a currency
    other than USD; a row naming no currency leaves it to the snapshot."""
    if snapshot.refusal == FOREIGN_FILER:
        return True
    company = latest_company(conn, snapshot.symbol)
    return company is not None and (company.is_adr or company.currency not in (None, "USD"))


def diluted_shares(result: ValuationResult) -> float | None:
    """The snapshot's diluted share count: its ``shares_diluted`` input, else its intermediates'
    ``shares``; ``None`` without a positive one."""
    cited = next((x.value for x in result.inputs if x.name == "shares_diluted"), None)
    for found in (cited, result.intermediates.get("shares")):
        if isinstance(found, bool) or not isinstance(found, int | float):
            continue
        if math.isfinite(found) and found > 0:
            return float(found)
    return None


def insert_derivation(
    conn: sqlite3.Connection,
    symbol: str,
    operation: Operation,
    a: str,
    b: str,
    years: int | None,
    value: float | None,
    unit: str | None,
    writer: Writer,
    at: datetime,
) -> int:
    """Store the derivation; return its id."""
    row = (
        symbol,
        operation,
        a,
        b,
        years,
        dump_float(value),
        unit,
        writer.principal,
        writer.actor,
        writer.client,
        dump_stamp(at),
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO derivations (symbol, operation, a, b, years, value, unit, principal,"
            " actor, client, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            row,
        )
    return inserted_id(cursor)


def derivation_row(conn: sqlite3.Connection, derivation_id: int) -> DerivationRow | None:
    row = conn.execute("SELECT * FROM derivations WHERE id = ?", (derivation_id,)).fetchone()
    if row is None:
        return None
    return DerivationRow(
        id=row["id"],
        symbol=row["symbol"],
        operation=row["operation"],
        a=row["a"],
        b=row["b"],
        years=row["years"],
        value=load_float(row["value"]),
        unit=row["unit"],
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        at=load_stamp(row["at"]),
    )


def _secondary(row: sqlite3.Row) -> SecondaryRow:
    return SecondaryRow(
        id=row["id"],
        symbol=row["symbol"],
        snapshot_id=row["snapshot_id"],
        created_at=load_stamp(row["created_at"]),
        principal=row["principal"],
        actor=row["actor"],
        client=row["client"],
        parts=tuple(json.loads(row["parts"])),
        firm_value=float(row["firm_value"]),
        debt=float(row["debt"]),
        cash=float(row["cash"]),
        shares=float(row["shares"]),
        equity=float(row["equity"]),
        value_per_share=float(row["value_per_share"]),
        buy_level=load_float(row["buy_level"]),
        fair_low=load_float(row["fair_low"]),
        fair_high=load_float(row["fair_high"]),
        trim_level=load_float(row["trim_level"]),
        price_to_value=row["price_to_value"],
        designation=row["designation"],
        reason=row["reason"],
        evidence=tuple(json.loads(row["evidence"])),
        debt_source=row["debt_source"],
        cash_source=row["cash_source"],
        policy_version=row["policy_version"],
        settings_hash=row["settings_hash"],
        deciles_refresh_id=row["deciles_refresh_id"],
        secondary_method=row["secondary_method"],
        form=row["form"],
        drivers=_loaded(row["drivers"]),
        projection=_loaded(row["projection"]),
        grid=_loaded(row["grid"]),
    )


def _projection_json(projection: Projection, revenue_0: float, roic_t: float) -> dict[str, Any]:
    """The projection table as stored (module docstring), from the trailing revenue and at the
    terminal return it was projected with."""
    return {
        "trailing_revenue": revenue_0,
        "terminal_return": roic_t,
        "years": [asdict(year) for year in projection.years],
        "terminal_fcff": projection.terminal_fcff,
        "terminal": projection.terminal,
        "terminal_pv": projection.terminal_pv,
    }


def _grid_json(grid: SecondaryGrid | None) -> dict[str, Any] | None:
    return None if grid is None else asdict(grid)


def _dumped(record: Mapping[str, Any] | None) -> str | None:
    """A record as JSON text, its floats as ``repr`` text; NULL for none."""
    return None if record is None else json.dumps(record, allow_nan=False)


def _loaded(text: str | None) -> dict[str, Any] | None:
    return None if text is None else dict(json.loads(text))
