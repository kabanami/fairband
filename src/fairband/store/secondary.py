"""The secondary valuations and the derivations (spec 2026-11-06 Tier 2, 11 and 13.4; ``method.md``
15).

A secondary valuation is stored as of the snapshot it was made on, and never changed: its parts as
JSON, each with its path, its terminal growth, its note, its present values, its terminal, the
terminal's present value and its value; the firm value, the debt, the cash, the diluted shares,
the equity, the value a share and the levels as ``repr`` text, so each float reads back exactly;
price ÷ value as a REAL and the designation's word, none of the four levels or the two on a value
a share at or below zero; the reason and the evidence (JSON ``{kind, ref, note, figure}`` items);
where the debt and the cash came from (``BalanceSource``), ``statements``, ``agent`` or ``none``
(no line on file, the figure 0.0); the writer and the time; the
policy version, the settings hash and the deciles refresh it ran under; and
``fairband-secondary/1``. ``latest_secondary`` reads the company's newest, ``secondaries_for``
every one, newest first, and ``secondary_row`` one by its id.

A derivation is one operation of an agent's arithmetic over two references: its operation, its
refs, its years (a cagr's, else none), its value as ``repr`` text (none where the operation is
undefined) and its unit, the writer and the time.

Each write is one transaction; it joins the caller's when there is one, so the caller's ledger row
commits with it.
"""

import json
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from fairband.engine.secondary import SECONDARY_METHOD, Part, SecondaryValuation
from fairband.store._codec import dump_float, dump_stamp, inserted_id, load_float, load_stamp
from fairband.store.db import transaction
from fairband.store.ledger import Principal, Writer

Operation = Literal["ratio", "difference", "sum", "growth", "cagr"]
# Where a secondary valuation's debt or cash came from: the newest balance sheet; the agent's
# figure or an applied balance override; or no line on file, counted as nil.
BalanceSource = Literal["statements", "agent", "none"]


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
) -> int:
    """Store the valuation of ``parts`` on snapshot ``snapshot_id``; return its id."""
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
    )
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO secondary_valuations (symbol, snapshot_id, created_at, principal, actor,"
            " client, parts, firm_value, debt, cash, shares, equity, value_per_share, buy_level,"
            " fair_low, fair_high, trim_level, price_to_value, designation, reason, evidence,"
            " debt_source, cash_source, policy_version, settings_hash, deciles_refresh_id,"
            " secondary_method)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,"
            " ?)",
            row,
        )
    return inserted_id(cursor)


def latest_secondary(conn: sqlite3.Connection, symbol: str) -> SecondaryRow | None:
    """The company's newest secondary valuation, if it has one."""
    row = conn.execute(
        "SELECT * FROM secondary_valuations WHERE symbol = ? ORDER BY id DESC LIMIT 1", (symbol,)
    ).fetchone()
    return None if row is None else _secondary(row)


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
    )
