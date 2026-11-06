"""The override, review, secondary valuation and derivation routes (spec 2026-11-06 Tier 2, 10.1
to 10.6, 11, 13.4 and 16; ``method.md`` 14 and 15).

``POST /api/companies/{symbol}/overrides`` takes ``{tag, new, reason, evidence: [{kind, ref,
note}], lifetime, period?}`` from an agent; a blank reason, or a period-tied override that names
no period, is a 400 and stores nothing. The company's latest snapshot must have been valued
under the effective policy (``require_current``: the price refresh's sentences, "settings
changed: run a revalue" and the others, answered 409), so the bridge's mechanical term is the
row's own figure. ``check_override`` then judges it on the route the row takes: its phase's, or
the phase an applied ``phase`` override sets (the new one included); an unclassified row with no
phase override reads no input but its phase. The evidence rule's cap is the ``sales_p90_5y`` of
the sales class of the snapshot's trailing revenue (its ``revenue_ttm`` input), the class the
routes find, so it holds on a row a phase override moves onto a route that reads the input (a
Start-up put in Young Growth); none when the snapshot cites no trailing revenue.
The override is stored either way, with the engine's reading of the input on the snapshot as its
old value and, for a period-tied one, as the value it corrected. A refused one answers 400 with
the rule's sentence and ``{override}``. An applied one drops the applied override on its tag
("replaced by override n") and the company's review is recomputed: ``build_inputs`` on the latest
deciles and today's date; the engine with no override on them must give the snapshot's route and
value a share, else the write is refused 409, "the store moved since snapshot <id>: run a
revalue", and nothing is stored, since a store change after the snapshot (a full refresh's new
deciles before its value stage, a peer's figures from a scoped refresh) would land on the bridge's
first line as the agent's; then ``review_company`` over every applied override from the
snapshot's result, the review written on the snapshot with its validity window and its log row;
it answers 201 with ``{override, review, bridge}``.

``DELETE /api/overrides/{id}`` drops an applied override with ``{reason}`` (the same 409s; 404
for no such override, 409 for one not applied) and recomputes the review over the rest, the
store-moved 409 included, or clears it when none is left; it answers ``{override, review,
bridge}``, the review ``null`` when cleared.
Both writes are an agent's: the owner's answer 403 (spec 10.3, the founder's ruling of
2026-11-06). Each write is a ledger row in its transaction, the agent's (``override``, and
``override-drop`` for a drop or a replacement), resting on the company's latest snapshot.

The reads: ``GET /api/companies/{symbol}/overrides`` newest first;
``/api/companies/{symbol}/reviews`` newest first, each with its bridge but without its result;
``/api/companies/{symbol}/reviews/latest``, the current review with its result, 404 without one;
``GET /api/review-log`` newest first, the company's with ``symbol``. Keys are camelCase, as the
agent routes send them.

``POST /api/companies/{symbol}/secondary`` takes ``{parts: [{name, fcff, terminalGrowth, note?}],
reason, evidence: [{kind, ref, note, figure?}], debt?, cash?}`` and answers 201 with the stored
secondary valuation (``method.md`` 15). A blank reason or no evidence is a 400; so is evidence
with no item for the path itself, every item naming a ``figure``, "the path needs its own evidence
item"; and a debt or a cash passed without its own evidence item, one whose ``figure`` names it.
Then, on the company's latest snapshot: ``require_current``'s 409s; a foreign filer, the snapshot
refused as one or its universe row an ADR or in a currency other than USD (a row naming none
leaves it to the snapshot), 400 with section 7's sentence; no positive diluted share count on the
snapshot (its ``shares_diluted`` input, else its intermediates' ``shares``), 400 "no diluted share
count". The debt and the cash are the agent's when passed, else an applied ``balance.*``
override's (both sourced ``agent``), else the newest annual balance sheet's as assembly reads them
(``statements``), else nil with the source ``none`` when no line is on file. The levels take the
current review's moat, else the snapshot's, else None; the designation the snapshot's price. A
rule ``secondary_value`` refuses is a 400 with its sentence. Anyone may make one, a tool's output
rather than an override; the write is a ``secondary`` ledger row resting on the snapshot. ``GET``
on the same path lists the company's, newest first.

``POST /api/companies/{symbol}/derivations`` takes ``{derivations: [{operation, a, b, years?}]}``
and answers 201 with ``{derivations: [{id, value, unit}]}``, each stored with a ``derivation``
ledger row resting on the latest snapshot (none without one). The operations: ``ratio`` a ÷ b,
``difference`` a − b, ``sum`` a + b, ``growth`` a ÷ b − 1 and ``cagr`` (a ÷ b)^(1/years) − 1,
whose ``years`` (one or more) is required. The unit: ``multiple`` for a ratio of two values in
one unit, else none; ``percent`` for growth and cagr; a difference or a sum keeps its operands'
unit when they share one, else none. A division by zero, a cagr over a negative ratio or a result
that is not finite has no value and no unit. The refs resolve as a report's do
(``fairband.reports.refs``, every form of spec 13.2, a ``table:`` cell included, under the
effective policy), their units the reads' (``currency``, ``per-share``, ``percent`` ...); a ref
that names no number, a word or a figure the record does not hold included, is a 400,
"unresolved reference: <ref>", and stores none of the call's derivations.
``GET /api/derivations/{id}`` reads one back, 404 without it.
"""

import json
import math
import sqlite3
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import datetime
from typing import Any, Literal, cast, get_args

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, FiniteFloat
from pydantic.alias_generators import to_camel

from fairband.engine import METHOD_VERSION
from fairband.engine.anchor import sales_class
from fairband.engine.overrides import (
    TAGS,
    Lifetime,
    State,
    check_override,
    current_reading,
    route_of,
)
from fairband.engine.route import FOREIGN_FILER, value_company
from fairband.engine.secondary import Part, secondary_value
from fairband.engine.types import Phase, ValuationResult, result_to_json
from fairband.policy import Moat, Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs import build_inputs
from fairband.refresh.inputs_statements import newest_debt_and_cash
from fairband.refresh.reviews import write_review
from fairband.refresh.run_price import METHOD_CHANGED, POLICY_CHANGED, SETTINGS_CHANGED
from fairband.reports.refs import Resolver
from fairband.store.companies import latest_company
from fairband.store.db import transaction
from fairband.store.ledger import Writer, record
from fairband.store.overrides import (
    OverrideRow,
    applied_overrides,
    drop_override,
    insert_override,
    override_row,
    overrides_for,
    set_review,
)
from fairband.store.refreshes import latest_deciles
from fairband.store.reviews import ReviewRow, latest_review, review_log, reviews_for
from fairband.store.secondary import (
    BalanceSource,
    Operation,
    SecondaryRow,
    derivation_row,
    insert_derivation,
    insert_secondary,
    latest_secondary,
    secondaries_for,
)
from fairband.store.snapshots import SnapshotRow, latest_snapshot
from fairband.web.agents_api import WriterOf, gist, record_json
from fairband.web.settings_api import effective

AGENTS_WRITE = "an override is an agent's write"
EvidenceKind = Literal["filing", "transcript", "url", "vendor", "base-rate", "finding"]
_PHASES: tuple[str, ...] = get_args(Phase)
_MOATS: tuple[str, ...] = get_args(Moat)
type _Figure = tuple[float, str | None]  # a resolved ref's number and unit


class _Body(BaseModel):
    """A request body, its keys camelCase."""

    model_config = ConfigDict(alias_generator=to_camel)


class Evidence(_Body):
    kind: EvidenceKind
    ref: str
    note: str | None = None


class OverridePost(_Body):
    tag: str
    new: FiniteFloat | str
    reason: str
    evidence: list[Evidence]
    lifetime: Lifetime
    period: str | None = None


class OverrideDrop(_Body):
    reason: str


class SecondaryEvidence(Evidence):
    """An evidence item; ``figure`` marks the one that backs a debt or a cash the agent passes."""

    figure: Literal["debt", "cash"] | None = None


class SecondaryPart(_Body):
    name: str
    fcff: list[FiniteFloat]
    terminal_growth: FiniteFloat
    note: str | None = None


class SecondaryPost(_Body):
    parts: list[SecondaryPart]
    reason: str
    evidence: list[SecondaryEvidence]
    debt: FiniteFloat | None = None
    cash: FiniteFloat | None = None


class DerivationPost(_Body):
    operation: Operation
    a: str
    b: str
    years: int | None = None


class DerivationsPost(_Body):
    derivations: list[DerivationPost]


def require_current(effective: Policy, snapshot: SnapshotRow) -> None:
    """Refuse, 409 with the price refresh's sentence, a write on a snapshot valued under another
    policy version, other settings or another method version, checked in that order."""
    if snapshot.policy_version != effective.version:
        raise HTTPException(409, POLICY_CHANGED)
    if snapshot.settings_hash != effective.settings_hash:
        raise HTTPException(409, SETTINGS_CHANGED)
    if snapshot.method_version != METHOD_VERSION:
        raise HTTPException(409, METHOD_CHANGED)


def review_json(review: ReviewRow, *, with_result: bool = True) -> dict[str, Any]:
    """A review as the API sends it: its bridge's lines camelCase, its result as the snapshot
    route sends one, or left out."""
    plain = record_json(review)
    plain["bridge"] = bridge_json(review)
    plain["overrideIds"] = list(review.override_ids)
    if with_result:
        plain["result"] = json.loads(result_to_json(review.result))
    else:
        del plain["result"]
    return plain


def bridge_json(review: ReviewRow) -> list[dict[str, Any]]:
    return [{to_camel(key): value for key, value in line.items()} for line in review.bridge]


def secondary_json(secondary: SecondaryRow) -> dict[str, Any]:
    """A secondary valuation as the API sends it, its parts' keys camelCase."""
    plain = record_json(secondary)
    plain["parts"] = [{to_camel(key): value for key, value in p.items()} for p in secondary.parts]
    return plain


def add_review_routes(
    app: FastAPI,
    conn_factory: Callable[[], sqlite3.Connection],
    policy: Policy,
    tax: TaxTable,
    clock: Callable[[], datetime],
) -> None:
    """Register the override and review routes; ``policy`` is the file's, which the user's
    settings overlay, and ``tax`` the table the inputs are built with."""

    def recompute(
        conn: sqlite3.Connection, symbol: str, snapshot: SnapshotRow, current: Policy
    ) -> int | None:
        """The company's review over its applied overrides on ``snapshot``, written; ``None``
        with none applied."""
        applied = applied_overrides(conn, symbol)
        if not applied:
            return None
        today = clock().date()
        deciles = latest_deciles(conn)
        inputs = build_inputs(conn, symbol, current, tax, today, deciles)
        if not _reproduces(value_company(inputs, deciles, current, today), snapshot.result):
            raise HTTPException(409, f"the store moved since snapshot {snapshot.id}: run a revalue")
        return write_review(
            conn,
            inputs,
            snapshot.result,
            snapshot.id,
            applied,
            deciles,
            current,
            today,
            None,
            clock,
        )

    def answer(conn: sqlite3.Connection, override_id: int, reviewed: bool) -> dict[str, Any]:
        override = override_row(conn, override_id)
        assert override is not None  # written in this transaction
        review = latest_review(conn, override.symbol) if reviewed else None
        return {
            "override": record_json(override),
            "review": None if review is None else review_json(review),
            "bridge": [] if review is None else bridge_json(review),
        }

    @app.post("/api/companies/{symbol}/overrides", status_code=201, response_model=None)
    def post_override(
        symbol: str, body: OverridePost, writer: WriterOf
    ) -> dict[str, Any] | JSONResponse:
        """Judge the override and store it; an applied one replaces the one on its tag and the
        review is recomputed."""
        _agents_only(writer)
        if not body.reason.strip():
            raise HTTPException(400, "an override needs a reason")
        if body.lifetime == "period-tied" and not (body.period or "").strip():
            raise HTTPException(400, "a period-tied override names its period")
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            symbol = exchange_symbol(symbol)
            snapshot = _snapshot(conn, symbol)
            current = effective(conn, policy)
            require_current(current, snapshot)
            applied = applied_overrides(conn, symbol)
            state, message = _check(body, applied, snapshot, current)
            spec = next((s for s in TAGS.values() if s.tag == body.tag), None)
            old = None if spec is None else current_reading(snapshot.result, spec.tag)
            override_id = insert_override(
                conn,
                symbol,
                body.tag,
                old,
                body.new,
                "" if spec is None else spec.unit,
                body.reason,
                [e.model_dump() for e in body.evidence],
                body.lifetime,
                body.period,
                old if body.lifetime == "period-tied" else None,
                snapshot.id,
                writer,
                at,
                state,
                message,
            )
            summary = f"{body.tag} {state}: {message or gist(body.reason)}"
            _record(conn, writer, at, "override", symbol, override_id, snapshot, summary)
            if state != "applied":
                stored = answer(conn, override_id, reviewed=False)["override"]
                return JSONResponse({"detail": message, "override": stored}, status_code=400)
            for replaced in (o for o in applied if o.tag == body.tag):
                why = f"replaced by override {override_id}"
                drop_override(conn, replaced.id, why, at)
                summary = f"{body.tag} {why}"
                _record(conn, writer, at, "override-drop", symbol, replaced.id, snapshot, summary)
            review_id = recompute(conn, symbol, snapshot, current)
            assert review_id is not None  # the new override is applied
            set_review(conn, override_id, review_id)
            return answer(conn, override_id, reviewed=True)

    @app.delete("/api/overrides/{override_id}")
    def delete_override(override_id: int, body: OverrideDrop, writer: WriterOf) -> dict[str, Any]:
        """Drop the applied override; the review is recomputed over the rest, or cleared."""
        _agents_only(writer)
        if not body.reason.strip():
            raise HTTPException(400, "a drop needs a reason")
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            found = override_row(conn, override_id)
            if found is None:
                raise HTTPException(404, f"no override {override_id}")
            if found.state != "applied":
                raise HTTPException(409, f"override {override_id} is {found.state}, not applied")
            snapshot = _snapshot(conn, found.symbol)
            current = effective(conn, policy)
            require_current(current, snapshot)
            drop_override(conn, override_id, body.reason, at)
            summary = f"{found.tag} dropped: {gist(body.reason)}"
            _record(conn, writer, at, "override-drop", found.symbol, override_id, snapshot, summary)
            review_id = recompute(conn, found.symbol, snapshot, current)
            return answer(conn, override_id, reviewed=review_id is not None)

    @app.get("/api/companies/{symbol}/overrides")
    def overrides(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            found = overrides_for(conn, exchange_symbol(symbol))
        return {"overrides": [record_json(o) for o in found]}

    @app.get("/api/companies/{symbol}/reviews")
    def reviews(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            found = reviews_for(conn, exchange_symbol(symbol))
        return {"reviews": [review_json(r, with_result=False) for r in found]}

    @app.get("/api/companies/{symbol}/reviews/latest")
    def latest(symbol: str) -> dict[str, Any]:
        symbol = exchange_symbol(symbol)
        with closing(conn_factory()) as conn:
            found = latest_review(conn, symbol)
        if found is None:
            raise HTTPException(404, f"no review for {symbol}")
        return review_json(found)

    @app.get("/api/review-log")
    def log(symbol: str | None = None) -> dict[str, Any]:
        company = None if symbol is None else exchange_symbol(symbol)
        with closing(conn_factory()) as conn:
            rows = review_log(conn, company)
        return {"reviewLog": [record_json(r) for r in rows]}

    @app.post("/api/companies/{symbol}/secondary", status_code=201)
    def post_secondary(symbol: str, body: SecondaryPost, writer: WriterOf) -> dict[str, Any]:
        """Value the company from the agent's path on its latest snapshot and store it."""
        if not body.reason.strip():
            raise HTTPException(400, "a secondary valuation needs a reason")
        if not body.evidence:
            raise HTTPException(400, "a secondary valuation needs evidence")
        if all(e.figure is not None for e in body.evidence):
            raise HTTPException(400, "the path needs its own evidence item")
        for name, passed in (("debt", body.debt), ("cash", body.cash)):
            if passed is not None and not any(e.figure == name for e in body.evidence):
                raise HTTPException(400, f"an explicit {name} needs its own evidence item")
        parts = [Part(p.name, tuple(p.fcff), p.terminal_growth, p.note) for p in body.parts]
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            symbol = exchange_symbol(symbol)
            snapshot = _snapshot(conn, symbol)
            current = effective(conn, policy)
            require_current(current, snapshot)
            if _foreign(conn, snapshot):
                raise HTTPException(400, FOREIGN_FILER)
            shares = _shares(snapshot.result)
            if shares is None:
                raise HTTPException(400, "no diluted share count")
            (debt, debt_source), (cash, cash_source) = _balance(conn, symbol, body.debt, body.cash)
            moat = _moat(conn, snapshot)
            try:
                valuation = secondary_value(
                    parts, debt, cash, shares, snapshot.price, moat, current
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None
            secondary_id = insert_secondary(
                conn,
                symbol,
                snapshot.id,
                parts,
                valuation,
                body.reason,
                [e.model_dump() for e in body.evidence],
                debt_source,
                cash_source,
                current.version,
                current.settings_hash,
                snapshot.deciles_refresh_id,
                writer,
                at,
            )
            count = f"{len(parts)} part{'' if len(parts) == 1 else 's'}"
            value = _dollars(valuation.value_per_share)
            summary = f"{value} a share from {count}: {gist(body.reason)}"
            record(
                conn,
                writer,
                at,
                "secondary",
                symbol,
                "secondary_valuations",
                secondary_id,
                snapshot_id=snapshot.id,
                summary=summary,
            )
            stored = latest_secondary(conn, symbol)
            assert stored is not None and stored.id == secondary_id  # this transaction's
            return secondary_json(stored)

    @app.get("/api/companies/{symbol}/secondary")
    def secondaries(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            found = secondaries_for(conn, exchange_symbol(symbol))
        return {"secondaryValuations": [secondary_json(s) for s in found]}

    @app.post("/api/companies/{symbol}/derivations", status_code=201)
    def post_derivations(symbol: str, body: DerivationsPost, writer: WriterOf) -> dict[str, Any]:
        """Compute and store each derivation; an unresolved reference stores none of them."""
        if not body.derivations:
            raise HTTPException(400, "a derive call needs a derivation")
        if any(d.operation == "cagr" and (d.years or 0) < 1 for d in body.derivations):
            raise HTTPException(400, "a cagr needs its years, one or more")
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            symbol = exchange_symbol(symbol)
            latest = latest_snapshot(conn, symbol)
            resolver = Resolver(conn, symbol, effective(conn, policy), tax)
            answers = []
            for d in body.derivations:
                a, b = _operand(resolver, d.a), _operand(resolver, d.b)
                years = d.years if d.operation == "cagr" else None
                value, unit = _derived(d.operation, a, b, years)
                derivation_id = insert_derivation(
                    conn, symbol, d.operation, d.a, d.b, years, value, unit, writer, at
                )
                record(
                    conn,
                    writer,
                    at,
                    "derivation",
                    symbol,
                    "derivations",
                    derivation_id,
                    snapshot_id=None if latest is None else latest.id,
                    summary=f"{d.operation} of {d.a} and {d.b}",
                )
                answers.append({"id": derivation_id, "value": value, "unit": unit})
            return {"derivations": answers}

    @app.get("/api/derivations/{derivation_id}")
    def derivation(derivation_id: int) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            found = derivation_row(conn, derivation_id)
        if found is None:
            raise HTTPException(404, f"no derivation {derivation_id}")
        return record_json(found)


def _agents_only(writer: Writer) -> None:
    if writer.principal != "agent":
        raise HTTPException(403, AGENTS_WRITE)


def _snapshot(conn: sqlite3.Connection, symbol: str) -> SnapshotRow:
    found = latest_snapshot(conn, symbol)
    if found is None:
        raise HTTPException(404, f"no snapshot for {symbol}")
    return found


def _check(
    body: OverridePost, applied: Sequence[OverrideRow], snapshot: SnapshotRow, policy: Policy
) -> tuple[State, str]:
    """The rule's answer on the route the row takes (module docstring)."""
    phases: list[float | str | None] = [body.new] if body.tag == "phase" else []
    phases += [o.new for o in applied if o.tag == "phase"]
    phases.append(snapshot.phase)
    route = next((route_of(cast(Phase, p)) for p in phases if p in _PHASES), None)
    if route is None:  # unclassified, with no phase override
        if body.tag in TAGS and body.tag != "phase":
            return "refused-route", f"an unclassified row reads no {body.tag}: set its phase first"
        route = "start-up"  # read by no rule these tags meet: every route reads a phase
    kinds = [e.kind for e in body.evidence]
    cap = _cap(snapshot.result, policy)
    return check_override(body.tag, body.new, route, policy, kinds, body.lifetime, cap)


def _reproduces(fresh: ValuationResult, snapshot: ValuationResult) -> bool:
    """Whether ``fresh``, the engine with no override on the inputs built today, is ``snapshot``'s
    result as the bridge reads it: the same route and the same value a share, or none on both."""
    return fresh.route == snapshot.route and fresh.value == snapshot.value


def _cap(result: ValuationResult, policy: Policy) -> float | None:
    """The 90th-percentile five-year sales growth of the sales class of the result's trailing
    revenue (its ``revenue_ttm`` input), the class every route finds (``anchor.sales_class``);
    ``None`` when the result cites no trailing revenue."""
    cited = next((x.value for x in result.inputs if x.name == "revenue_ttm"), None)
    revenue = _number(cited, None)
    return None if revenue is None else sales_class(revenue[0] / 1e6, policy).sales_p90_5y


def _record(
    conn: sqlite3.Connection,
    writer: Writer,
    at: datetime,
    kind: str,
    symbol: str,
    override_id: int,
    snapshot: SnapshotRow,
    summary: str,
) -> None:
    """The override write's ledger row, resting on ``snapshot``."""
    record(
        conn,
        writer,
        at,
        kind,
        symbol,
        "overrides",
        override_id,
        snapshot_id=snapshot.id,
        summary=summary,
    )


def _foreign(conn: sqlite3.Connection, snapshot: SnapshotRow) -> bool:
    """A foreign filer: the snapshot refused as one, or the universe row an ADR or in a currency
    other than USD; a row naming no currency leaves it to the snapshot."""
    if snapshot.refusal == FOREIGN_FILER:
        return True
    company = latest_company(conn, snapshot.symbol)
    return company is not None and (company.is_adr or company.currency not in (None, "USD"))


def _shares(result: ValuationResult) -> float | None:
    """The snapshot's diluted share count: its ``shares_diluted`` input, else its intermediates'
    ``shares``; ``None`` without a positive one."""
    cited = next((x.value for x in result.inputs if x.name == "shares_diluted"), None)
    for found in (cited, result.intermediates.get("shares")):
        figure = _number(found, None)
        if figure is not None and figure[0] > 0:
            return figure[0]
    return None


def _balance(
    conn: sqlite3.Connection, symbol: str, debt: float | None, cash: float | None
) -> tuple[tuple[float, BalanceSource], tuple[float, BalanceSource]]:
    """The debt and the cash with their sources: the agent's figure when passed, else an applied
    ``balance.*`` override's (both ``agent``), else the newest balance sheet's (``statements``),
    else nil with the source ``none`` when no line is on file."""
    corrected = {o.tag: o.new for o in applied_overrides(conn, symbol)}
    lines = newest_debt_and_cash(conn, symbol)
    figures: list[tuple[float, BalanceSource]] = []
    for name, passed, line in zip(("debt", "cash"), (debt, cash), lines, strict=True):
        override = _number(corrected.get(f"balance.{name}"), None)
        if passed is not None:
            figures.append((passed, "agent"))
        elif override is not None:
            figures.append((override[0], "agent"))
        elif line is not None:
            figures.append((line, "statements"))
        else:
            figures.append((0.0, "none"))
    return figures[0], figures[1]


def _moat(conn: sqlite3.Connection, snapshot: SnapshotRow) -> Moat:
    """The moat class the levels take: the current review's, else the snapshot's, else None."""
    review = latest_review(conn, snapshot.symbol)
    for result in ([] if review is None else [review.result]) + [snapshot.result]:
        found = current_reading(result, "moat.class")
        if found in _MOATS:
            return cast(Moat, found)
    return "None"


def _dollars(x: float) -> str:
    return f"{'−' if x < 0 else ''}${abs(x):,.2f}"


def _operand(resolver: Resolver, ref: str) -> _Figure:
    """The number and unit ``ref`` names; 400 when it names no number."""
    found = resolver.resolve(ref)
    if found is None or not isinstance(found.value, float):
        raise HTTPException(400, f"unresolved reference: {ref}")
    return found.value, found.unit


def _number(x: Any, unit: str | None) -> _Figure | None:
    """``x`` with ``unit`` when ``x`` is a finite number, else ``None``."""
    if isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x):
        return float(x), unit
    return None


def _derived(
    operation: Operation, a: _Figure, b: _Figure, years: int | None
) -> tuple[float | None, str | None]:
    """The operation's value and unit (module docstring); ``(None, None)`` where it is undefined."""
    (x, x_unit), (y, y_unit) = a, b
    shared = x_unit if x_unit == y_unit else None
    value: float | None
    if operation == "difference":
        value, unit = x - y, shared
    elif operation == "sum":
        value, unit = x + y, shared
    elif y == 0:
        value, unit = None, None
    elif operation == "ratio":
        value, unit = x / y, None if shared is None else "multiple"
    elif operation == "growth":
        value, unit = x / y - 1, "percent"
    elif x / y < 0 or years is None:  # cagr: a negative ratio has no real root
        value, unit = None, None
    else:
        value, unit = (x / y) ** (1 / years) - 1, "percent"
    if value is None or not math.isfinite(value):
        return None, None
    return value, unit
