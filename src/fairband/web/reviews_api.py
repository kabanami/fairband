"""The override and review routes (spec 2026-11-06 Tier 2, 10.1 to 10.6 and 16; ``method.md`` 14).

``POST /api/companies/{symbol}/overrides`` takes ``{tag, new, reason, evidence: [{kind, ref,
note}], lifetime, period?}`` from an agent. The company's latest snapshot must have been valued
under the effective policy (``require_current``: the price refresh's sentences, "settings
changed: run a revalue" and the others, answered 409), so the bridge's mechanical term is the
row's own figure. ``check_override`` then judges it on the route the row takes: its phase's, or
the phase an applied ``phase`` override sets (the new one included); an unclassified row with no
phase override reads no input but its phase. The evidence rule's cap is the ``sales_p90_5y`` of
the snapshot's sales class (``belief.sales_class`` or ``path.sales_class``), none without one.
The override is stored either way, with the engine's reading of the input on the snapshot as its
old value and, for a period-tied one, as the value it corrected. A refused one answers 400 with
the rule's sentence and ``{override}``. An applied one drops the applied override on its tag
("replaced by override n") and the company's review is recomputed: ``build_inputs`` on the latest
deciles, ``review_company`` over every applied override from the snapshot's result, the review
written on the snapshot with its log row; it answers 201 with ``{override, review, bridge}``.

``DELETE /api/overrides/{id}`` drops an applied override with ``{reason}`` (the same 409s; 404
for no such override, 409 for one not applied) and recomputes the review over the rest, or clears
it when none is left; it answers ``{override, review, bridge}``, the review ``null`` when cleared.
Both writes are an agent's: the owner's answer 403 (spec 10.3, the founder's ruling of
2026-11-06). Each write is a ledger row in its transaction, the agent's (``override``, and
``override-drop`` for a drop or a replacement), resting on the company's latest snapshot.

The reads: ``GET /api/companies/{symbol}/overrides`` newest first;
``/api/companies/{symbol}/reviews`` newest first, each with its bridge but without its result;
``/api/companies/{symbol}/reviews/latest``, the current review with its result, 404 without one;
``GET /api/review-log`` newest first, the company's with ``symbol``. Keys are camelCase, as the
agent routes send them.
"""

import json
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
from fairband.engine.overrides import (
    TAGS,
    Lifetime,
    State,
    check_override,
    current_reading,
    route_of,
)
from fairband.engine.types import Phase, ValuationResult, result_to_json
from fairband.policy import Policy
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs import build_inputs
from fairband.refresh.reviews import write_review
from fairband.refresh.run_price import METHOD_CHANGED, POLICY_CHANGED, SETTINGS_CHANGED
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
from fairband.store.snapshots import SnapshotRow, latest_snapshot
from fairband.web.agents_api import WriterOf, gist, record_json
from fairband.web.settings_api import effective

AGENTS_WRITE = "an override is an agent's write"
EvidenceKind = Literal["filing", "transcript", "url", "vendor", "base-rate", "finding"]
_PHASES: tuple[str, ...] = get_args(Phase)


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


def _cap(result: ValuationResult, policy: Policy) -> float | None:
    """The 90th-percentile five-year sales growth of the result's sales class; ``None`` without
    one."""
    for key in ("belief", "path"):
        found = result.intermediates.get(key)
        if isinstance(found, dict) and "sales_class" in found:
            label = found["sales_class"]
            return next((c.sales_p90_5y for c in policy.base_rates if c.label == label), None)
    return None


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
