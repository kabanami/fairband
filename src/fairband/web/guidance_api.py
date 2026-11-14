"""The guidance routes (spec 2026-11-06 Tier 2, 9, 15.4 and 16; ``method.md`` 14.9).

``POST /api/companies/{symbol}/guidance`` takes ``{metric, period, low, high, basis, asOf, text,
source}`` from an agent and answers 201 with the stored guidance record, its midpoint and its step
the server's (``fairband.store.guidance``). The owner's post answers 403, "a guidance record is an
agent's write". A value the record cannot take is a 400 with the store's sentence, in the order of
the fields: "metric is one of revenue, eps, ...", "period is a fiscal year or a quarter (2026,
2026Q3)", "low is above high", "basis is one of gaap, adjusted or constant-currency", "a guidance
record needs its text", "a guidance record needs its source"; a low or a high that is not a
finite number is refused by the body's types, a 400 too. For a fiscal-year revenue, EPS or net
income record the server reads the actual of the fiscal year before the guided one from the
statements as ``fact:<symbol>/revenue/<year>``, ``fact:<symbol>/eps_diluted/<year>`` or
``fact:<symbol>/net_income/<year>`` resolves it (spec 2026-11-14 9); with no actual on file the
record takes no step, and neither does a record on a basis other than ``gaap``, whatever the
actual (``store.guidance``). The company needs no snapshot. The call's
date orders the records of one metric, period and basis (``store.guidance``): a record of a call
on or after the current one's supersedes it, whose ``supersededBy`` then names it, and a record of
an earlier call is stored already superseded.
The write is a ``guidance`` ledger row resting on the company's latest snapshot (none without
one), its summary "<metric> <period>: <the text's first line>".

``GET`` on the same path lists the company's records newest first, each as the post answers it,
under ``guidance``. A record's keys are camelCase.
"""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, FiniteFloat
from pydantic.alias_generators import to_camel

from fairband.policy import Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.reports.refs import Resolver, fact_ref
from fairband.store.db import transaction
from fairband.store.guidance import guidance_for, guidance_row, insert_guidance, year_before
from fairband.store.ledger import record
from fairband.store.snapshots import latest_snapshot
from fairband.web.agents_api import WriterOf, gist, record_json
from fairband.web.reviews_api import agents_only
from fairband.web.settings_api import effective

GUIDANCE_WRITE = "a guidance record is an agent's write"
# The statement line a stepped metric's year before reads, by the engine's name (``fact:``).
_BASE_LINES = {"revenue": "revenue", "eps": "eps_diluted", "net_income": "net_income"}


class GuidancePost(BaseModel):
    """A guidance record as the agent gives it; the keys camelCase."""

    model_config = ConfigDict(alias_generator=to_camel)

    metric: str
    period: str
    low: FiniteFloat
    high: FiniteFloat
    basis: str
    as_of: date
    text: str
    source: str


def add_guidance_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    clock: Callable[[], datetime],
) -> None:
    """Register the guidance routes; ``policy`` is the file's, which the user's settings overlay,
    and ``tax`` the table the statements are read with."""

    @app.post("/api/companies/{symbol}/guidance", status_code=201)
    def post_guidance(symbol: str, body: GuidancePost, writer: WriterOf) -> dict[str, Any]:
        """Store the guidance record with its midpoint and step."""
        agents_only(writer, GUIDANCE_WRITE)
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            try:
                symbol = exchange_symbol(symbol)
                resolver = Resolver(conn, symbol, effective(conn, policy), tax)
                guidance_id = insert_guidance(
                    conn,
                    symbol,
                    body.metric,
                    body.period,
                    body.low,
                    body.high,
                    body.basis,
                    body.as_of,
                    body.text,
                    body.source,
                    writer,
                    at,
                    _base_actual(resolver, body.metric, body.period),
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None
            found = guidance_row(conn, guidance_id)
            assert found is not None  # written in this transaction
            latest = latest_snapshot(conn, symbol)
            record(
                conn,
                writer,
                at,
                "guidance",
                symbol,
                "guidance",
                guidance_id,
                snapshot_id=None if latest is None else latest.id,
                summary=f"{found.metric} {found.period}: {gist(found.text)}",
            )
            return record_json(found)

    @app.get("/api/companies/{symbol}/guidance")
    def guidance(symbol: str) -> dict[str, Any]:
        try:
            company = exchange_symbol(symbol)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        with closing(conn_factory()) as conn:
            return {"guidance": [record_json(g) for g in guidance_for(conn, company)]}


def _base_actual(resolver: Resolver, metric: str, period: str) -> float | None:
    """The actual a fiscal-year revenue, EPS or net income record steps from, the statement line
    of the year before as a ``fact:`` ref resolves it; ``None`` for any other record or with no
    figure on file."""
    year = year_before(metric, period)
    if year is None:
        return None
    found = resolver.resolve(fact_ref(resolver.symbol, _BASE_LINES[metric], str(year)))
    value = None if found is None else found.value
    return value if isinstance(value, float) else None
