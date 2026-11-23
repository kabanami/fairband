"""The override, review, secondary valuation and derivation routes (spec 2026-11-06 Tier 2, 10.1
to 10.6, 11, 13.4 and 16; ``method.md`` 14 and 15).

``POST /api/companies/{symbol}/overrides`` takes ``{tag, new, reason, evidence: [{kind, ref,
note}], lifetime, period?}`` from an agent; a blank reason, or a period-tied override that names
no period, is a 400 and stores nothing. The company's latest snapshot must have been valued
under the effective policy (``require_current``: the price refresh's sentences, "settings
changed: run a revalue" and the others, answered 409), so the bridge's mechanical term is the
row's own figure. An evidence item of kind ``guidance`` cites a current guidance record of the
company as ``guidance:<id>``: a ref of another form is a 400, "a guidance item cites its record as
guidance:<id>", one naming no record of the company a 404, "no guidance record <id> for
<symbol>", and one naming a record a later call superseded a 409, "guidance record <id> is
superseded by record <id>", so an NTM anchor never rests on a record a later call replaced; none
stores anything. An override of an NTM anchor whose evidence cites guidance must cite, among its
records, a gaap record of one of the anchor's metrics (``eps`` or ``net_income`` for
``earnings.ntm``, ``revenue`` for ``revenue.ntm``) for a fiscal year, else 400 "an NTM anchor
override needs a gaap guidance record of <eps or net_income|revenue> for a fiscal year"
(``overrides.anchor_misfit``), nothing stored; the override's figure is not checked against the
record, since an EPS from a net income record is the agent's cited division; one with no
guidance item at all is left to the evidence rule, which stores it refused. An override applied
before a later record superseded the one it cites stays applied. An override of ``moat.class``
is then refused ``refused-locked``, "moat.class is the moat table's: record the verdict with
moat_set" (``overrides.MOAT_SET``), on any row, an unclassified one too (spec 2026-11-19 8.7).
``check_override`` then judges it on the route the row takes: its phase's, or the phase an applied
``phase`` override sets (the new one included); an unclassified row with no phase override reads
no input but its phase. The evidence rule's cap is the ``sales_p90_5y`` of the sales class of the
snapshot's trailing revenue (its ``revenue_ttm`` input), the class the routes find, so it holds on
a row a phase override moves onto a route that reads the input (a Start-up put in Young Growth);
none when the snapshot cites no trailing revenue. On a row in another currency (spec 2026-11-10
7.3) the class reads that revenue ÷ the snapshot's rate, in USD as the class bounds are, and the
cap is restated by the row's inflation differential, as the routes read it; the money ranges are
read in the currency at the snapshot's rate (``types.money_of``). An NTM anchor's override needs a
``guidance`` item among its evidence. A lasting ``earnings.sbc`` of 0 that the rules apply is
then refused where the snapshot's own trailing stock pay, the engine's reading of the input on
it, is above zero: 400 "a lasting earnings.sbc of 0 is refused: the snapshot's trailing stock pay
is above zero" (``lasting_nil_refusal``), nothing stored; a reading of 0, or none, takes it (spec
2026-11-13 7.3).
Otherwise the override is stored, applied or refused, with the engine's reading of the input on
the snapshot as its old value and, for a period-tied one, as the value it corrected. A refused one
answers 400 with the rule's sentence and ``{override}``. An applied one drops the applied override
on its tag ("replaced by override n") and the company's review is recomputed. The recompute first
drops, by the system, each applied override the row's route does not read (spec 2026-11-14 8,
``reviews.drop_off_route``): the route of the applied ``phase`` override, else of the snapshot's
phase (``reviews.row_route``), so adding, replacing or dropping a ``phase`` override takes with it
the overrides only the old route read, each with the reason "the <route> route does not read the
input"; an unclassified row with no ``phase`` override keeps them all. The new override itself
was judged on the route the row now takes, by the same rule (``judged_route`` reads
``row_route``), so it stays. Then ``build_inputs`` on the latest deciles and today's date, a row
in another currency at the snapshot's own rate and its date, which are snapshot data as the price
is (``built_inputs``); the engine with no override on them must give the snapshot's route and
value a share, else the write is refused 409, "the store moved since snapshot <id>: run a
revalue", and nothing is stored, since a store change after the snapshot (a full refresh's new
deciles before its value stage, a peer's figures from a scoped refresh) would land on the
bridge's first line as the agent's; then ``review_company`` over every override still applied
from the snapshot's result, the review written on the snapshot with its validity window and its
log row; it answers 201 with ``{override, review, bridge, dropped}``, ``dropped`` the overrides
the system dropped, each ``{id, tag, reason}``, empty when none.

``DELETE /api/overrides/{id}`` drops an applied override with ``{reason}`` (the same 409s; 404
for no such override, 409 for one not applied) and recomputes the review over the rest, the
route's drops and the store-moved 409 included, or clears it when none is left; it answers
``{override, review, bridge, dropped}``, the review ``null`` when cleared.
Both writes are an agent's: the owner's answer 403 (spec 10.3, the founder's ruling of
2026-11-06). Each write is a ledger row in its transaction, the agent's (``override``, and
``override-drop`` for a drop or a replacement), resting on the company's latest snapshot; a drop
the recompute makes is the system's ``override-drop``, after them in the same transaction.

The reads: ``GET /api/companies/{symbol}/overrides`` newest first;
``/api/companies/{symbol}/reviews`` newest first, each with its bridge but without its result;
``/api/companies/{symbol}/reviews/latest``, the current review with its result, 404 without one;
``GET /api/review-log`` newest first, the company's with ``symbol``. Keys are camelCase, as the
agent routes send them.

``POST /api/companies/{symbol}/secondary`` takes ``{reason, evidence: [{kind, ref, note,
figure?}], drivers?: {years, revenueGrowth, operatingMargin, taxRate, salesToCapital,
terminalGrowth}, parts?: [{name, fcff, terminalGrowth, note?}], debt?, cash?}`` and answers 201
with the stored secondary valuation (``method.md`` 15). On the body, in this order, each a 400: a
blank reason; no evidence; both forms, "a secondary valuation takes drivers or parts, not both",
or neither, "a secondary valuation needs drivers or parts"; evidence with no item for the drivers
or the path itself, every item naming a ``figure``, "the path needs its own evidence item"; a debt
or a cash passed without its own evidence item, one whose ``figure`` names it. Then, on the
company's latest snapshot: ``require_current``'s 409s; a company with no row in the moat table,
400 "set the moat class first: moat_set", whatever its snapshot's refusal, since the levels need
the class and an agent can set it (spec 2026-11-19 8.7); a snapshot with a value, 400 "the route
values <symbol>: the secondary valuation is the fallback where it refuses", the secondary
valuation being the fallback where the route refuses or no phase fits (spec 11 as amended for plan
3, the founder's ruling of 2026-11-08); a current review that rests on the snapshot or one it
reprices (``same_snapshot``) and has a value, an override having routed the company, 400 "the
review values <symbol>: the secondary valuation is the fallback where neither the route nor the
review values the company"; a ``guidance`` evidence item's 400, 404 and 409, as an override's; a
snapshot refused for a reason no call can meet (``store.secondary.cannot_fix``: the reporting
currency's four refusals, the listed-share basis's, no diluted share count; spec 2026-11-10 7.6),
400 with the refusal's own sentence; no positive diluted share count on the snapshot (its
``shares_diluted`` input, else its intermediates' ``shares``), 400 "no diluted share count"; on
the drivers form, no positive trailing revenue, 400 "no trailing revenue on file". The trailing
revenue is read at the call as ``fact:<symbol>/revenue/ttm`` resolves it, the statements'
trailing figures as the engine reads them; the terminal return is ``terminal_roic`` on the moat the
levels take and the aggregate ROIC of the snapshot's intermediates (``roic/aggregate``, which the
mature routes write; none on the other routes, so r). The debt and the cash are the agent's when
passed, else an applied ``balance.debt`` or ``balance.cash`` override's (both sourced ``agent``),
else the newest balance sheet's as assembly reads them (``statements``), else nil with the source
``none`` when no line is on file; no minority interest is subtracted, an applied
``balance.minority`` included (spec 2026-11-13 3). The levels take the class of the company's row
of the moat table, read at the call, so a company refused for its statements, whose snapshot holds
no class, takes its row's (spec 2026-11-19 8.6); the designation the snapshot's price. A company
in another currency (spec 2026-11-10 7.6) is valued in its reporting currency on the policy
restated by its snapshot's inflation differential (``policy.in_currency``): r, the terminal
growth's bound g_T and the Wide moat's terminal return cap at r plus the spread are the
currency's; the trailing revenue, the agent's path, debt and cash, an override's and the balance
sheet's are in the currency; and the snapshot's USD price comes into it at the snapshot's rate
(``types.money_of``). On the way out the totals stay in the currency; the value a share and the
grid's cells are ÷ the rate, US dollars a share, the levels the policy's on that value and the
designation the USD price against it, as a snapshot's (``_in_usd``); the record stores the rate. A
USD row's rate is 1 and its differential 0, so its valuation is as before. A rule
``secondary_value`` refuses is a 400 with its sentence. The answer's drivers, projection and parts
carry camelCase keys, and its grid ``rowsAre``, ``growths`` or ``shifts`` (``GRID_ROWS``). Anyone
may make one, a tool's output rather than an override; the write is a ``secondary`` ledger row
resting on the snapshot, its summary "<value> a share from drivers over three years: <reason>" or
"... from 2 parts: ...". ``GET`` on the same path lists the company's, newest first.

``POST /api/companies/{symbol}/derivations`` takes ``{derivations: [{operation, a, b, years?}]}``
and answers 201 with ``{derivations: [{id, value, unit}]}``, each stored with a ``derivation``
ledger row resting on the latest snapshot (none without one). The operations: ``ratio`` a ÷ b,
``difference`` a − b, ``sum`` a + b, ``product`` a × b, ``growth`` a ÷ b − 1 and ``cagr``
(a ÷ b)^(1/years) − 1, whose ``years`` (one or more) is required. The unit: ``multiple`` for a
ratio of two values in one unit, else none; ``percent`` for growth and cagr; a difference or a
sum keeps its operands' unit when they share one, else none; a product with a multiple, then
with a percent, keeps the other operand's unit, a figure a share times a count is a ``currency``
total, and any other product has none. A division by zero, a growth or a cagr from a base at or
below zero (spec 2026-11-15 7.4), a cagr over a negative ratio or a result that is not finite has
no value and no unit. The refs resolve as a report's do
(``fairband.reports.refs``, every form of spec 13.2, a ``table:`` cell included, under the
effective policy), their units the reads' (``currency``, ``per-share``, ``percent`` ...); a ref
that names no number, a word or a figure the record does not hold included, is a 400,
"unresolved reference: <ref>", and stores none of the call's derivations; so is a kill
criterion's threshold, ``kill:<id>``, a number the author chose, which enters no arithmetic (spec
2026-11-15 8.2). One operand may be a fixed number (spec 2026-11-15 7.1), ``number:<n>`` of
``refs.NUMBERS``, read before the resolver and stored as written; it has no unit, and the
result's follows the stored figure (7.2): a sum, a difference or a product with it keeps the
figure's unit, as does a ratio of the figure over it, and a ratio of it over the figure has none.
A number off the list or written another way is a
400, "a fixed number is one of 0 to 12, 52, 100, 365 or a power of ten up to
1,000,000,000,000, not <what was written>", and two numbers in one derivation a 400, "a derivation
needs a stored figure"; so is a derivation with a value and a number anywhere in its tree that
depends on no stored figure (``DEPENDS_ON_A_FIGURE``, method 16.4): its tree, read from the stored
rows (``_Trees``), evaluated from its leaves and again with each group of leaves of one value
scaled by 1.5, moves from a value to a value beyond the billionth and the float rounding for no
group (``_no_dependence``); an earlier derivation whose figures changed is a constant there, and
the refusal then says to derive it again (``REDERIVE``). Each stores none of the call's
derivations.
A record in another currency
(spec 2026-11-15 9.3), a finding's or a guidance record's money figure whose ``Resolved.currency``
is not the reporting currency (``Resolver.reporting``), in either direction, is kept out of money
arithmetic until it is converted, and so is a derivation of it (method 16.4): an operand is foreign
in that currency where it is such a record, or a ``derived:`` operand whose tree carries it
(``_carried``), but the ``product`` of an operand in US dollars and the rate
(``snapshot:<id>/inputs/fx_rate``, the reporting currency per US dollar) converted it, a
``growth`` or a ``cagr`` is a percent, and a ``ratio`` of two operands in one currency cancels it;
a ratio over the rate, or the rate's product with another currency, converts nothing. An operand
foreign in a currency, with a ``currency`` or ``per-share`` figure or an operand foreign in another
currency, gives no value and no unit, and where the rules above give it a money unit it has none,
since a stored derivation has no currency. So two records in one currency give a growth, a ratio,
and a sum or a difference with no unit, a quarter or an average of a record is still in its
currency, and a US-dollar record times the rate (which has no unit) is the figure converted, with
no unit. ``GET /api/derivations/{id}`` reads one back, 404 without it.

``sensitivity_api`` shares ``require_current``, ``agents_only``, ``snapshot_of``, ``built_inputs``
(the store-moved 409), ``judged_route`` (the route the rules judge a tag on) and ``counted``.
"""

import json
import math
import sqlite3
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Literal, cast

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, FiniteFloat
from pydantic.alias_generators import to_camel

from fairband.engine import METHOD_VERSION
from fairband.engine.anchor import sales_class
from fairband.engine.classifier import Deciles
from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.overrides import (
    ANCHOR_METRICS,
    MOAT_SET,
    PHASES,
    TAGS,
    Lifetime,
    State,
    anchor_misfit,
    check_override,
    current_reading,
    route_of,
    unit_in,
)
from fairband.engine.roic import terminal_roic
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.secondary import Drivers, Part, SecondaryValuation, secondary_value
from fairband.engine.types import (
    Phase,
    Route,
    ValuationResult,
    money_of,
    rated,
    result_to_json,
)
from fairband.policy import Moat, Policy, in_currency
from fairband.policy.settings import exchange_symbol
from fairband.policy.tax import TaxTable
from fairband.refresh.inputs import build_inputs
from fairband.refresh.inputs_statements import newest_debt_and_cash
from fairband.refresh.reviews import drop_off_route, row_route, write_review
from fairband.refresh.run_price import METHOD_CHANGED, POLICY_CHANGED, SETTINGS_CHANGED
from fairband.reports.refs import (
    KILL_FORM,
    MAX_ID,
    NUMBER_FORM,
    Resolved,
    Resolver,
    fact_ref,
    fixed_number,
    guidance_cited,
    record_id_of,
    same_snapshot,
)
from fairband.store.currency import MONEY_UNITS
from fairband.store.db import transaction
from fairband.store.guidance import anchor_year, guidance_row
from fairband.store.ledger import Writer, record
from fairband.store.moat import moat_row
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
from fairband.store.reviews import (
    ReviewRow,
    clear_held,
    held_row,
    latest_review,
    review_log,
    reviews_for,
)
from fairband.store.secondary import (
    GRID_ROWS,
    BalanceSource,
    DerivationRow,
    Operation,
    SecondaryRow,
    cannot_fix,
    derivation_row,
    diluted_shares,
    insert_derivation,
    insert_secondary,
    latest_secondary,
    secondaries_for,
)
from fairband.store.snapshots import SnapshotRow, latest_snapshot
from fairband.web.agents_api import WriterOf, gist, record_json
from fairband.web.rows import held_block
from fairband.web.settings_api import effective

AGENTS_WRITE = "an override is an agent's write"
SET_THE_MOAT = "set the moat class first: moat_set"
EvidenceKind = Literal["filing", "transcript", "url", "vendor", "base-rate", "finding", "guidance"]
GUIDANCE_REF = "a guidance item cites its record as guidance:<id>"
NIL_ON_FILE = (
    "a lasting earnings.sbc of 0 is refused: the snapshot's trailing stock pay is above zero"
)
FIXED_NUMBERS = (
    "a fixed number is one of 0 to 12, 52, 100, 365 or a power of ten up to 1,000,000,000,000"
)
NEEDS_A_FIGURE = "a derivation needs a stored figure"
DEPENDS_ON_A_FIGURE = (
    "a derivation with a fixed number must depend on a stored figure: this one has the same value"
    " whatever its figures are"
)
# The same refusal where an earlier derivation of the tree was taken as a constant (``_frozen``).
REDERIVE = (
    f"{DEPENDS_ON_A_FIGURE}, or rests on an earlier derivation whose figures changed: derive it"
    " again"
)
# The dependence test of a derivation with a fixed number (method 16.4): each group of its tree's
# leaves is scaled by ``_SCALE``, and a result moves when it moves by more than ``_MOVED`` of the
# larger of 1 and the unscaled result's size, and by more than ``_BOUND`` times the float rounding
# the two evaluations can carry, each value's bound ``_EPS`` of it, carried through each operation.
_SCALE = 1.5
_MOVED = 1e-9
_BOUND = 4.0
_EPS = 2.0**-52
type _Figure = tuple[float, str | None]  # a resolved ref's number and unit
# The overrides the system dropped at a recompute, each with its reason (``drop_off_route``).
type _Dropped = Sequence[tuple[OverrideRow, str]]
# The small counts a sentence writes in words (the register: "three years").
_SMALL_COUNTS = (
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
    "twenty",
)


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


class SecondaryDrivers(_Body):
    years: int
    revenue_growth: list[FiniteFloat]
    operating_margin: list[FiniteFloat]
    tax_rate: FiniteFloat
    sales_to_capital: FiniteFloat
    terminal_growth: FiniteFloat


class SecondaryPost(_Body):
    reason: str
    evidence: list[SecondaryEvidence]
    drivers: SecondaryDrivers | None = None
    parts: list[SecondaryPart] | None = None
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


def _stamp(at: datetime | None) -> str | None:
    return None if at is None else at.isoformat()


def bridge_json(review: ReviewRow) -> list[dict[str, Any]]:
    return [{to_camel(key): value for key, value in line.items()} for line in review.bridge]


def secondary_json(secondary: SecondaryRow) -> dict[str, Any]:
    """A secondary valuation as the API sends it: the keys of its parts, its drivers and its
    projection camelCase, and its grid with ``rowsAre``, what its rows hold (``GRID_ROWS``)."""
    plain = record_json(secondary)
    plain["parts"] = _camel_keys(secondary.parts)
    plain["drivers"] = _camel_keys(secondary.drivers)
    plain["projection"] = _camel_keys(secondary.projection)
    grid = secondary.grid
    plain["grid"] = None if grid is None else grid | {"rowsAre": GRID_ROWS[secondary.form]}
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
    ) -> tuple[int | None, _Dropped]:
        """The company's review over its applied overrides on ``snapshot``, written, once the
        system has dropped those the row's route does not read (``reviews.drop_off_route``): a
        made review, which the company holds from here on (spec 2026-11-23 held reviewed value,
        5.1). ``None`` with none left, and the company then holds no review: a person's act
        left no override applied. With it, the overrides so dropped, each with its reason."""
        applied = applied_overrides(conn, symbol)
        dropped = drop_off_route(conn, applied, snapshot.result.phase.phase, snapshot.id, clock)
        gone = {o.id for o, _ in dropped}
        kept = [o for o in applied if o.id not in gone]
        if not kept:
            clear_held(conn, symbol)
            return None, dropped
        today = clock().date()
        inputs, deciles = built_inputs(conn, snapshot, current, tax, today)
        review_id = write_review(
            conn,
            inputs,
            snapshot.result,
            snapshot.id,
            kept,
            deciles,
            current,
            today,
            None,
            clock,
        )
        return review_id, dropped

    def answer(
        conn: sqlite3.Connection, override_id: int, reviewed: bool, dropped: _Dropped = ()
    ) -> dict[str, Any]:
        override = override_row(conn, override_id)
        assert override is not None  # written in this transaction
        review = latest_review(conn, override.symbol) if reviewed else None
        return {
            "override": record_json(override),
            "review": None if review is None else review_json(review),
            "bridge": [] if review is None else bridge_json(review),
            "dropped": [{"id": o.id, "tag": o.tag, "reason": why} for o, why in dropped],
        }

    @app.post("/api/companies/{symbol}/overrides", status_code=201, response_model=None)
    def post_override(
        symbol: str, body: OverridePost, writer: WriterOf
    ) -> dict[str, Any] | JSONResponse:
        """Judge the override and store it; an applied one replaces the one on its tag and the
        review is recomputed."""
        agents_only(writer)
        if not body.reason.strip():
            raise HTTPException(400, "an override needs a reason")
        if body.lifetime == "period-tied" and not (body.period or "").strip():
            raise HTTPException(400, "a period-tied override names its period")
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            symbol = exchange_symbol(symbol)
            snapshot = snapshot_of(conn, symbol)
            current = effective(conn, policy)
            require_current(current, snapshot)
            require_guidance(conn, symbol, body.evidence)
            _require_anchor_record(conn, body.tag, body.evidence)
            applied = applied_overrides(conn, symbol)
            state, message = _check(body, applied, snapshot, current)
            spec = next((s for s in TAGS.values() if s.tag == body.tag), None)
            old = None if spec is None else current_reading(snapshot.result, spec.tag)
            nil = lasting_nil_refusal(body.tag, body.lifetime, old)
            if state == "applied" and nil is not None:
                raise HTTPException(400, nil)
            override_id = insert_override(
                conn,
                symbol,
                body.tag,
                old,
                body.new,
                "" if spec is None else unit_in(spec.unit, money_of(snapshot.result)[1]),
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
            review_id, dropped = recompute(conn, symbol, snapshot, current)
            # the new override is applied, and stays: it was judged on the route the row takes
            assert review_id is not None
            set_review(conn, override_id, review_id)
            return answer(conn, override_id, reviewed=True, dropped=dropped)

    @app.delete("/api/overrides/{override_id}")
    def delete_override(override_id: int, body: OverrideDrop, writer: WriterOf) -> dict[str, Any]:
        """Drop the applied override; the review is recomputed over the rest, or cleared."""
        agents_only(writer)
        if not body.reason.strip():
            raise HTTPException(400, "a drop needs a reason")
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            found = override_row(conn, override_id)
            if found is None:
                raise HTTPException(404, f"no override {override_id}")
            if found.state != "applied":
                raise HTTPException(409, f"override {override_id} is {found.state}, not applied")
            snapshot = snapshot_of(conn, found.symbol)
            current = effective(conn, policy)
            require_current(current, snapshot)
            drop_override(conn, override_id, body.reason, at)
            summary = f"{found.tag} dropped: {gist(body.reason)}"
            _record(conn, writer, at, "override-drop", found.symbol, override_id, snapshot, summary)
            review_id, dropped = recompute(conn, found.symbol, snapshot, current)
            return answer(conn, override_id, reviewed=review_id is not None, dropped=dropped)

    @app.get("/api/companies/{symbol}/overrides")
    def overrides(symbol: str) -> dict[str, Any]:
        with closing(conn_factory()) as conn:
            found = overrides_for(conn, exchange_symbol(symbol))
        return {"overrides": [record_json(o) for o in found]}

    @app.get("/api/companies/{symbol}/reviews")
    def reviews(symbol: str) -> dict[str, Any]:
        """Every review of the company, newest first, each with its kind, and ``held``: the
        state of the review it holds (``rows.held_block``; spec 2026-11-23 held reviewed value,
        5.8) with the made review's id, when it was made and when a refresh first read it
        again; ``None`` for a company that holds none."""
        company = exchange_symbol(symbol)
        with closing(conn_factory()) as conn:
            found = reviews_for(conn, company)
            facts = held_row(conn, company)
            current = None if facts is None else latest_review(conn, company)
            state = None
            if facts is not None and current is not None:
                state = held_block(current, facts, effective(conn, policy), clock().date()) | {
                    "reviewId": facts.review_id,
                    "madeAt": facts.made_at.isoformat(),
                    "readAgainAt": _stamp(facts.read_again_at),
                }
        return {"held": state, "reviews": [review_json(r, with_result=False) for r in found]}

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
        """Value the company from the agent's drivers or path on its latest snapshot, where
        neither the route nor the current review values it, and store it."""
        _check_secondary(body)
        drivers = None if body.drivers is None else _drivers(body.drivers)
        parts = None if body.parts is None else [_part(p) for p in body.parts]
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            symbol = exchange_symbol(symbol)
            snapshot = snapshot_of(conn, symbol)
            current = effective(conn, policy)
            require_current(current, snapshot)
            moat = _moat(conn, symbol)
            if moat is None:
                raise HTTPException(400, SET_THE_MOAT)
            if snapshot.value is not None:
                raise HTTPException(
                    400,
                    f"the route values {symbol}: the secondary valuation is the fallback where it"
                    " refuses",
                )
            review = latest_review(conn, symbol)
            if (
                review is not None
                and review.value is not None
                and same_snapshot(conn, review.snapshot_id, snapshot.id)
            ):
                raise HTTPException(
                    400,
                    f"the review values {symbol}: the secondary valuation is the fallback where"
                    " neither the route nor the review values the company",
                )
            require_guidance(conn, symbol, body.evidence)
            if snapshot.refusal is not None and cannot_fix(snapshot.refusal):
                raise HTTPException(400, snapshot.refusal)
            shares = diluted_shares(snapshot.result)
            if shares is None:
                raise HTTPException(400, "no diluted share count")
            # valued in the reporting currency, on the policy's rates restated into it
            rate, _ = money_of(snapshot.result)
            local = _in_currency(snapshot.result, current)
            revenue_0 = roic_t = None
            if drivers is not None:
                revenue_0 = _trailing_revenue(Resolver(conn, symbol, current, tax))
                if revenue_0 is None:
                    raise HTTPException(400, "no trailing revenue on file")
                roic_t = terminal_roic(_aggregate_roic(snapshot.result), moat, local)
            (debt, debt_source), (cash, cash_source) = _balance(conn, symbol, body.debt, body.cash)
            try:
                valuation = secondary_value(
                    parts=parts,
                    drivers=drivers,
                    revenue_0=revenue_0,
                    roic_t=roic_t,
                    debt=debt,
                    cash=cash,
                    shares=shares,
                    price=None if snapshot.price is None else snapshot.price * rate,
                    moat=moat,
                    policy=local,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from None
            valuation = _in_usd(valuation, rate, snapshot.price, moat, current)
            secondary_id = insert_secondary(
                conn,
                symbol,
                snapshot.id,
                parts or (),
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
                revenue_0=revenue_0,
                roic_t=roic_t,
                fx_rate=rate,
            )
            summary = f"{_valued_from(valuation)}: {gist(body.reason)}"
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
        """Compute and store each derivation; an unresolved reference, a fixed number off the list,
        two numbers in one derivation, or a fixed number in a derivation that depends on no stored
        figure stores none of them."""
        if not body.derivations:
            raise HTTPException(400, "a derive call needs a derivation")
        if any(d.operation == "cagr" and (d.years or 0) < 1 for d in body.derivations):
            raise HTTPException(400, "a cagr needs its years, one or more")
        at = clock()
        with closing(conn_factory()) as conn, transaction(conn, immediate=True):
            symbol = exchange_symbol(symbol)
            latest = latest_snapshot(conn, symbol)
            resolver = Resolver(conn, symbol, effective(conn, policy), tax)
            trees = _Trees(conn, resolver)
            answers = []
            for d in body.derivations:
                a, b = _operand(resolver, trees, d.a), _operand(resolver, trees, d.b)
                if a.fixed and b.fixed:
                    raise HTTPException(400, NEEDS_A_FIGURE)
                years = d.years if d.operation == "cagr" else None
                value, unit = _derived(d.operation, a, b, years)
                if value is not None:
                    refusal = _no_dependence(_node(d.operation, a.tree, b.tree, years, value))
                    if refusal is not None:
                        raise HTTPException(400, refusal)
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


def _check_secondary(body: SecondaryPost) -> None:
    """A secondary valuation's refusals on its body alone, in order (module docstring)."""
    if not body.reason.strip():
        raise HTTPException(400, "a secondary valuation needs a reason")
    if not body.evidence:
        raise HTTPException(400, "a secondary valuation needs evidence")
    if body.drivers is not None and body.parts is not None:
        raise HTTPException(400, "a secondary valuation takes drivers or parts, not both")
    if body.drivers is None and body.parts is None:
        raise HTTPException(400, "a secondary valuation needs drivers or parts")
    if all(e.figure is not None for e in body.evidence):
        raise HTTPException(400, "the path needs its own evidence item")
    for name, passed in (("debt", body.debt), ("cash", body.cash)):
        if passed is not None and not any(e.figure == name for e in body.evidence):
            raise HTTPException(400, f"an explicit {name} needs its own evidence item")


def _drivers(d: SecondaryDrivers) -> Drivers:
    return Drivers(
        d.years,
        tuple(d.revenue_growth),
        tuple(d.operating_margin),
        d.tax_rate,
        d.sales_to_capital,
        d.terminal_growth,
    )


def _part(p: SecondaryPart) -> Part:
    return Part(p.name, tuple(p.fcff), p.terminal_growth, p.note)


def _trailing_revenue(resolver: Resolver) -> float | None:
    """The trailing revenue as ``fact:<symbol>/revenue/ttm`` reads it, the statements' trailing
    figures as the engine reads them (``financials``' ``ttm``); ``None`` without a positive one."""
    found = resolver.resolve(fact_ref(resolver.symbol, "revenue", "ttm"))
    figure = None if found is None else _number(found.value, None)
    return figure[0] if figure is not None and figure[0] > 0 else None


def _in_usd(
    valuation: SecondaryValuation, rate: float, price: float | None, moat: Moat, policy: Policy
) -> SecondaryValuation:
    """``valuation``, made in the reporting currency, on the way out to US dollars at ``rate``, as
    the route's value goes (spec 2026-11-10 7.6): its value a share and its grid's cells ÷ the
    rate, its levels the policy's on that value and its designation the USD ``price`` against it,
    where it has them; its totals, its projection and its parts stay in the currency. At a USD
    row's rate of 1 every figure is as made."""
    value = valuation.value_per_share / rate
    levels = None if valuation.levels is None else levels_for(value, moat, policy)
    price_to_value, designation = valuation.price_to_value, valuation.designation
    if price_to_value is not None and price is not None:
        price_to_value, designation = designation_for(price, value, policy.edges_for(moat))
    grid = valuation.grid
    if grid is not None:
        grid = replace(grid, cells=tuple(tuple(c / rate for c in row) for row in grid.cells))
    return replace(
        valuation,
        value_per_share=value,
        levels=levels,
        price_to_value=price_to_value,
        designation=designation,
        grid=grid,
    )


def _aggregate_roic(result: ValuationResult) -> float | None:
    """The ten-year aggregate ROIC of the snapshot's intermediates (``roic/aggregate``), which the
    mature routes write; ``None`` on the other routes."""
    roic = result.intermediates.get("roic")
    figure = _number(roic.get("aggregate") if isinstance(roic, Mapping) else None, None)
    return None if figure is None else figure[0]


def _valued_from(valuation: SecondaryValuation) -> str:
    """A secondary valuation's ledger summary before its reason: its value a share and what it
    was valued from, the drivers' years a small count in words."""
    value = _dollars(valuation.value_per_share)
    if valuation.drivers is not None:
        return f"{value} a share from drivers over {counted(valuation.drivers.years, 'year')}"
    return f"{value} a share from {len(valuation.parts)} part{_plural(len(valuation.parts))}"


def counted(n: int, noun: str) -> str:
    """``n`` ``noun``s, the count in words up to twenty: "three years"."""
    word = _SMALL_COUNTS[n] if 0 <= n < len(_SMALL_COUNTS) else str(n)
    return f"{word} {noun}{_plural(n)}"


def _plural(n: int) -> str:
    return "" if n == 1 else "s"


def _camel_keys(value: Any) -> Any:
    """``value`` with the keys of every record in it camelCase; a tuple as a list."""
    if isinstance(value, Mapping):
        return {to_camel(key): _camel_keys(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_camel_keys(item) for item in value]
    return value


def agents_only(writer: Writer, sentence: str = AGENTS_WRITE) -> None:
    """Refuse, 403 with ``sentence``, a write that is not an agent's."""
    if writer.principal != "agent":
        raise HTTPException(403, sentence)


def snapshot_of(conn: sqlite3.Connection, symbol: str) -> SnapshotRow:
    """The company's latest snapshot; 404 without one."""
    found = latest_snapshot(conn, symbol)
    if found is None:
        raise HTTPException(404, f"no snapshot for {symbol}")
    return found


def built_inputs(
    conn: sqlite3.Connection, snapshot: SnapshotRow, policy: Policy, tax: TaxTable, today: date
) -> tuple[CompanyInputs, Deciles | None]:
    """The company's inputs as ``build_inputs`` builds them today on the latest deciles, at
    ``snapshot``'s own rate on a row in another currency (``_at_its_rate``), with those deciles;
    409, "the store moved since snapshot <id>: run a revalue", when the engine on them with no
    override does not give ``snapshot``'s route and value a share."""
    deciles = latest_deciles(conn)
    built = build_inputs(conn, snapshot.symbol, policy, tax, today, deciles)
    inputs = _at_its_rate(built, snapshot.result, policy)
    if not _reproduces(value_company(inputs, deciles, policy, today), snapshot.result):
        raise HTTPException(409, f"the store moved since snapshot {snapshot.id}: run a revalue")
    return inputs, deciles


def _at_its_rate(inputs: CompanyInputs, result: ValuationResult, policy: Policy) -> CompanyInputs:
    """``inputs`` at the rate ``result`` was valued or last repriced at: its ``fx_rate`` and
    ``fx_date`` intermediates, its ``fx_rate`` input's provenance, and stale as a reprice reads
    it, the date more than ``fx_stale_days`` before the price date (spec 2026-11-10 7.1). The rate
    is snapshot data, as the price is: a price refresh reprices at the pair's quote of the quote's
    own date, which may be after the price date, and a scoped refresh of a company in the same
    currency fetches the pair's history again, so the store's rate at the price date need not be
    the snapshot's. ``inputs`` as built on a row that carries no rate (``types.rated``), and on
    inputs in another currency than the snapshot's or with no rate of their own, which the
    reproduction check then reads as the store moving."""
    stored = result.intermediates.get("fx_date")
    rate, currency = money_of(result)
    if not rated(result) or stored is None or inputs.currency != currency or inputs.fx_date is None:
        return inputs
    when = date.fromisoformat(stored)
    cited = next((i.provenance for i in result.inputs if i.name == "fx_rate"), None)
    provenance = inputs.provenance if cited is None else inputs.provenance | {"fx_rate": cited}
    priced = inputs.price_date
    stale = priced is not None and (priced - when).days > policy.fx_stale_days
    return replace(inputs, fx_rate=rate, fx_date=when, fx_stale=stale, provenance=provenance)


def judged_route(
    tag: str, applied: Sequence[OverrideRow], snapshot: SnapshotRow, phase: object = None
) -> Route | tuple[State, str]:
    """The route the rules judge ``tag`` on: the route of ``phase`` when it is one (the new phase
    of an override or of a reading), else the route the row takes (``reviews.row_route``: of an
    applied ``phase`` override, else of the snapshot's phase), the rule the recompute's drop reads,
    so the override a write judges is never the one its recompute drops. An unclassified row with
    no phase override reads no input but its phase: another input's tag answers ``refused-route``
    with "set its phase first"."""
    if phase in PHASES:
        return route_of(cast(Phase, phase))
    route = row_route(applied, snapshot.result.phase.phase)
    if route is not None:
        return route
    if tag in TAGS and tag != "phase":
        return "refused-route", f"an unclassified row reads no {tag}: set its phase first"
    return "start-up"  # read by no rule these tags meet: every route reads a phase


def _check(
    body: OverridePost, applied: Sequence[OverrideRow], snapshot: SnapshotRow, policy: Policy
) -> tuple[State, str]:
    """The rule's answer on the route the row takes (module docstring); the moat class's before
    the route's, an unclassified row's among them (spec 2026-11-19 8.7)."""
    if body.tag == "moat.class":
        return "refused-locked", MOAT_SET
    route = judged_route(body.tag, applied, snapshot, body.new if body.tag == "phase" else None)
    if isinstance(route, tuple):
        return route
    kinds = [e.kind for e in body.evidence]
    cap = _cap(snapshot.result, policy)
    rate, currency = money_of(snapshot.result)
    return check_override(
        body.tag,
        body.new,
        route,
        policy,
        kinds,
        body.lifetime,
        cap,
        fx_rate=rate,
        currency=currency,
    )


def lasting_nil_refusal(tag: str, lifetime: Lifetime, reading: float | str | None) -> str | None:
    """The refusal of a lasting ``earnings.sbc`` of 0, the one figure the rules let it last at,
    on a snapshot whose own trailing stock pay, ``reading``, is a number above zero: the store
    contradicts the nil, and the period-tied form is the one for a period the vendor has wrong
    (spec 2026-11-13 7.3); ``None`` for another tag, a period-tied override, a reading of 0, or
    none, a row refused before its route read one."""
    if tag != "earnings.sbc" or lifetime != "lasting" or isinstance(reading, str | None):
        return None
    return NIL_ON_FILE if reading > 0 else None


def require_guidance(conn: sqlite3.Connection, symbol: str, evidence: Sequence[Evidence]) -> None:
    """Each ``guidance`` item names a current guidance record of the company as ``guidance:<id>``:
    400 for another form of ref, 404 for a record that is not the company's, 409 for one a later
    call's record superseded (module docstring). An override's, a secondary valuation's and an
    agent's moat verdict's evidence meet it (``moat_api``)."""
    for item in evidence:
        if item.kind != "guidance":
            continue
        cited = guidance_cited(item.ref)
        if cited is None:
            raise HTTPException(400, GUIDANCE_REF)
        found = None if cited > MAX_ID else guidance_row(conn, cited)  # no row has such an id
        if found is None or found.symbol != symbol:
            raise HTTPException(404, f"no guidance record {cited} for {symbol}")
        if found.superseded_by is not None:
            detail = f"guidance record {cited} is superseded by record {found.superseded_by}"
            raise HTTPException(409, detail)


def _require_anchor_record(
    conn: sqlite3.Connection, tag: str, evidence: Sequence[Evidence]
) -> None:
    """An override of an NTM anchor whose evidence cites guidance cites, among its records, a gaap
    record of one of the anchor's metrics for a fiscal year: 400 ``anchor_misfit`` otherwise
    (module docstring). Run after ``require_guidance``, so each ref names a record of the
    company."""
    if tag not in ANCHOR_METRICS:
        return
    cited = [guidance_cited(e.ref) for e in evidence if e.kind == "guidance"]
    records = [guidance_row(conn, i) for i in cited if i is not None]
    if records and not any(r is not None and anchor_year(tag, r) is not None for r in records):
        raise HTTPException(400, anchor_misfit(tag))


def _reproduces(fresh: ValuationResult, snapshot: ValuationResult) -> bool:
    """Whether ``fresh``, the engine with no override on the inputs built today, is ``snapshot``'s
    result as the bridge reads it: the same route and the same value a share, or none on both."""
    return fresh.route == snapshot.route and fresh.value == snapshot.value


def _cap(result: ValuationResult, policy: Policy) -> float | None:
    """The 90th-percentile five-year sales growth of the sales class of the result's trailing
    revenue (its ``revenue_ttm`` input), the class every route finds (``anchor.sales_class``): on
    a row in another currency, the revenue ÷ its rate and the cap restated by its differential
    (``policy.in_currency``); ``None`` when the result cites no trailing revenue."""
    cited = next((x.value for x in result.inputs if x.name == "revenue_ttm"), None)
    revenue = _number(cited, None)
    if revenue is None:
        return None
    rate, _ = money_of(result)
    return sales_class(revenue[0] / rate / 1e6, _in_currency(result, policy)).sales_p90_5y


def _in_currency(result: ValuationResult, policy: Policy) -> Policy:
    """``policy`` restated into the reporting currency of ``result`` by its inflation differential
    (``policy.in_currency``); ``policy`` itself for a USD row, whose result carries none."""
    return in_currency(policy, result.intermediates.get("inflation_differential", 0.0))


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


def _balance(
    conn: sqlite3.Connection, symbol: str, debt: float | None, cash: float | None
) -> tuple[tuple[float, BalanceSource], tuple[float, BalanceSource]]:
    """The debt and the cash with their sources: the agent's figure when passed, else an applied
    ``balance.debt`` or ``balance.cash`` override's (both ``agent``), else the newest balance
    sheet's (``statements``), else nil with the source ``none`` when no line is on file."""
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


def _moat(conn: sqlite3.Connection, symbol: str) -> Moat | None:
    """The moat class the levels take: the class of the company's row of the moat table, ``None``
    without a row."""
    row = moat_row(conn, symbol)
    return None if row is None else row.moat


def _dollars(x: float) -> str:
    return f"{'−' if x < 0 else ''}${abs(x):,.2f}"


# A derivation's tree (``_Trees``): a fixed number as its float, a stored figure as a ``_Leaf``, a
# derivation as a ``_Node`` over its two operands' trees.
type _Tree = float | _Leaf | _Node


@dataclass(frozen=True)
class _Leaf:
    """A stored figure in a derivation's tree: its number resolved now, ``None`` where its ref
    names no number now; ``foreign`` the currency it is in where it is a record's money figure in
    another currency than the reporting one (``_foreign``)."""

    value: float | None
    foreign: str | None = None


@dataclass(frozen=True, eq=False)  # one node a derivation however often the tree names it
class _Node:
    """A derivation in a tree (``_node``): its operation, its operands' trees, its years and its
    value, the stored one for a derivation on file; ``whole`` whether every leaf under it has a
    number now, else the tree takes it as one leaf at its value (method 16.4); ``numbered``
    whether a fixed number is anywhere under it; ``foreign`` the currency a stored derivation
    carries where it is an operand (``_carried``)."""

    operation: Operation
    a: _Tree
    b: _Tree
    years: int | None
    value: float | None
    whole: bool
    numbered: bool
    foreign: str | None = None


def _node(
    operation: Operation,
    a: _Tree,
    b: _Tree,
    years: int | None,
    value: float | None,
    foreign: str | None = None,
) -> _Node:
    """The node of a derivation over the trees ``a`` and ``b``: whole where each has a number now,
    a nested derivation that is not whole counting as its value; numbered where either is a fixed
    number or holds one."""
    whole = all(_has_number(x) for x in (a, b))
    numbered = any(isinstance(x, float) or (isinstance(x, _Node) and x.numbered) for x in (a, b))
    return _Node(operation, a, b, years, value, whole, numbered, foreign)


def _has_number(tree: _Tree) -> bool:
    if isinstance(tree, _Leaf):
        return tree.value is not None
    return not isinstance(tree, _Node) or tree.whole or tree.value is not None


def _foreign(resolver: Resolver, found: Resolved | None) -> str | None:
    """The currency of a record's money figure that is not the reporting currency, in either
    direction (spec 2026-11-15 9.3); ``None`` for any other ref, the resolver knowing the currency
    of a record alone."""
    currency = None if found is None else found.currency
    return currency if currency is not None and currency != resolver.reporting() else None


def _carried(operation: str, refs: tuple[str, str], a: _Tree, b: _Tree) -> str | None:
    """The currency a stored derivation carries where it is an operand (method 16.4): that of an
    operand foreign in it, a record in another currency or a derivation that carries one; none for
    the ``product`` of an operand in US dollars and the rate, ``snapshot:<id>/inputs/fx_rate``,
    the reporting currency per US dollar, which converted it, for a ``growth`` or a ``cagr``, a
    percent having no currency, and for a ``ratio`` of two operands in one currency, which cancels
    it. A ratio over the rate, or the rate's product with another currency, converts nothing."""
    fa, fb = (x.foreign if isinstance(x, _Leaf | _Node) else None for x in (a, b))
    if operation in ("growth", "cagr"):
        return None
    if operation == "product" and (
        (_is_rate(refs[1]) and fa == "USD") or (_is_rate(refs[0]) and fb == "USD")
    ):
        return None
    if operation == "ratio" and fa == fb:
        return None
    return fa if fa is not None else fb


def _is_rate(ref: str) -> bool:
    """Whether ``ref`` is a snapshot's rate, ``snapshot:<id>/inputs/fx_rate``."""
    form, _, path = ref.strip().partition(":")
    head, _, rest = path.partition("/")
    return form == "snapshot" and rest == "inputs/fx_rate" and record_id_of(head) is not None


class _Trees:
    """The trees of a call's ``derived:`` operands, read from the stored rows as
    ``refs.snapshots_of`` walks them: each derivation's operation, operands and years, nested ones
    too, each derivation read once; a call's derivations are stored one by one, so a later one of
    the call reads an earlier one. A stored figure is resolved now by the call's resolver, and a
    derivation carries the currency of its tree's records until it is converted (``_carried``)."""

    def __init__(self, conn: sqlite3.Connection, resolver: Resolver) -> None:
        self._conn = conn
        self._resolver = resolver
        self._read: dict[int, _Node | None] = {}

    def derived(self, ref: str) -> _Node | None:
        """The tree of the derivation ``ref`` names, ``derived:<id>``; ``None`` for a ref of
        another form or an id with no derivation."""
        form, _, path = ref.strip().partition(":")
        derivation_id = record_id_of(path) if form == "derived" else None
        if derivation_id is None:
            return None
        if derivation_id not in self._read:  # each an earlier record: no cycle
            row = derivation_row(self._conn, derivation_id)
            self._read[derivation_id] = None if row is None else self._of(row)
        return self._read[derivation_id]

    def _of(self, row: DerivationRow) -> _Node:
        a, b = self._operand(row.a), self._operand(row.b)
        foreign = _carried(row.operation, (row.a, row.b), a, b)
        return _node(cast(Operation, row.operation), a, b, row.years, row.value, foreign)

    def _operand(self, ref: str) -> _Tree:
        number = fixed_number(ref)
        if number is not None:
            return float(number)
        nested = self.derived(ref)
        if nested is not None:
            return nested
        found = self._resolver.resolve(ref)
        value = found.value if found is not None and isinstance(found.value, float) else None
        return _Leaf(value, _foreign(self._resolver, found))


# A value of a tree as ``_evaluated`` gives it: the number, ``None`` where it has none, and a bound
# on its absolute float rounding.
type _Bounded = tuple[float | None, float]


def _no_dependence(node: _Node) -> str | None:
    """The refusal of a derivation that holds a fixed number in its tree and depends on no stored
    figure (method 16.4), ``None`` where it depends or holds no number. Its tree is evaluated from
    its leaves by ``derive``'s arithmetic, then again with each group of leaves of one value scaled
    by ``_SCALE`` in turn; it depends where, for one group at least, both results have a value and
    they differ beyond ``_moved``'s floor. A tree with no value is refused. The refusal says to
    derive again where an earlier derivation of the tree was taken as a constant (``_frozen``)."""
    if not node.numbered:
        return None
    memo: dict[_Node, _Bounded] = {}
    frozen = _frozen(node, node, set(), memo)
    base, rounding = _evaluated(node, None, frozen, memo)
    if base is not None:
        for group in _groups(node, frozen, set()):
            scaled, more = _evaluated(node, group, frozen, {})
            if scaled is not None and _moved(base, scaled, rounding + more):
                return None
    return REDERIVE if frozen else DEPENDS_ON_A_FIGURE


def _frozen(tree: _Tree, top: _Node, frozen: set[_Node], memo: dict[_Node, _Bounded]) -> set[_Node]:
    """``frozen`` with the nested derivations under ``tree`` that are constants at their stored
    value: one whose leaves do not all resolve now (not ``whole``), or whose tree, its own frozen
    derivations constant, no longer gives its stored value within ``_MOVED``. A derivation's
    descendants are judged before it, so ``memo`` (unscaled) holds final values."""
    if not isinstance(tree, _Node) or tree in memo or tree in frozen:
        return frozen
    if tree is not top and not tree.whole:
        frozen.add(tree)
        return frozen
    _frozen(tree.a, top, frozen, memo)
    _frozen(tree.b, top, frozen, memo)
    value, _ = _evaluated(tree, None, frozen, memo)
    stored = tree.value
    if tree is not top and (
        stored is None or value is None or abs(value - stored) > _MOVED * max(1.0, abs(stored))
    ):
        frozen.add(tree)
    return frozen


def _groups(tree: _Tree, frozen: set[_Node], seen: set[_Node]) -> set[float]:
    """The values of a tree's leaves, each the value of one group: its stored figures'. A frozen
    derivation is a constant and gives none."""
    if isinstance(tree, float):
        return set()
    if isinstance(tree, _Leaf):
        return set() if tree.value is None else {tree.value}
    if tree in frozen or tree in seen:
        return set()
    seen.add(tree)
    return _groups(tree.a, frozen, seen) | _groups(tree.b, frozen, seen)


def _evaluated(
    tree: _Tree, group: float | None, frozen: set[_Node], memo: dict[_Node, _Bounded]
) -> _Bounded:
    """A tree's value from its leaves by ``derive``'s arithmetic (``_value``), the leaves of the
    value ``group`` scaled by ``_SCALE``, a frozen derivation a constant at its stored value, with
    a bound on its float rounding (``_rounded``)."""
    if isinstance(tree, float):  # a fixed number is exact and never scaled
        return tree, 0.0
    if isinstance(tree, _Leaf):
        if tree.value is None:
            return None, 0.0
        value = tree.value * (_SCALE if tree.value == group else 1)
        return value, abs(value) * _EPS
    if tree in frozen:
        return tree.value, 0.0
    if tree not in memo:
        (x, ex), (y, ey) = (_evaluated(t, group, frozen, memo) for t in (tree.a, tree.b))
        if x is None or y is None:
            memo[tree] = None, 0.0
        else:
            memo[tree] = _rounded(tree.operation, x, ex, y, ey, tree.years)
    return memo[tree]


def _rounded(
    operation: Operation, x: float, ex: float, y: float, ey: float, years: int | None
) -> _Bounded:
    """The operation over ``x`` and ``y`` (``_value``) and a first-order bound on its absolute
    float rounding, ``ex`` and ``ey`` being the operands': a sum or a difference adds them, a
    product weighs each by the other operand, a ratio, a growth and a cagr carry the quotient's;
    each result rounds by ``_EPS`` of its size."""
    value = _value(operation, x, y, years)
    if value is None:
        return None, 0.0
    if operation in ("sum", "difference"):
        bound = ex + ey
    elif operation == "product":
        bound = abs(x) * ey + abs(y) * ex
    else:  # a ratio, a growth and a cagr divide x by a y that is not zero
        q = x / y
        bound = ex / abs(y) + abs(x) / abs(y) * ey / abs(y) + abs(q) * _EPS
        if operation == "cagr" and years is not None and years > 1:
            root = value + 1  # q to the 1/years
            bound = root / q / years * bound + abs(root) * _EPS if q > 0 else math.inf
    bound += abs(value) * _EPS
    return value, math.inf if math.isnan(bound) else bound


def _moved(base: float, scaled: float, rounding: float) -> bool:
    """Whether a scaled result moved from the base: by more than ``_MOVED`` of the larger of 1 and
    the base's size, and by more than ``_BOUND`` times the rounding the two can carry."""
    return abs(scaled - base) > max(_MOVED * max(1.0, abs(base)), _BOUND * rounding)


@dataclass(frozen=True)
class _Operand:
    """A derivation's operand as read (``_operand``): its number, its unit, whether it is a fixed
    number, which has no unit and leaves the result's to the stored figure, and ``foreign``, the
    currency it is foreign in: a record's money figure in another currency than the reporting one,
    or a derivation that carries one (``_carried``), ``None`` for any other operand; ``tree`` its
    tree (``_Trees``)."""

    value: float
    unit: str | None
    tree: _Tree
    fixed: bool = False
    foreign: str | None = None


def _operand(resolver: Resolver, trees: _Trees, ref: str) -> _Operand:
    """The number and unit ``ref`` names, a fixed number (``refs.fixed_number``) read before the
    resolver, with no unit; 400 when it names no number, is a ``number:`` off the list, or is a
    ``kill:`` threshold, the author's own number (spec 2026-11-15 8.2). A record's money figure
    whose currency (``Resolved.currency``) is not the reporting currency carries it (spec
    2026-11-15 9.3). A ``derived:`` operand's tree is read from the stored rows, and it carries
    the currency its tree gives it (``_carried``)."""
    written = ref.strip()
    if written.startswith(f"{NUMBER_FORM}:"):
        number = fixed_number(written)
        if number is None:
            raise HTTPException(400, f"{FIXED_NUMBERS}, not {written[len(NUMBER_FORM) + 1 :]}")
        return _Operand(float(number), None, float(number), fixed=True)
    if written.startswith(f"{KILL_FORM}:"):  # a number the author chose enters no arithmetic
        raise HTTPException(400, f"unresolved reference: {ref}")
    found = resolver.resolve(ref)
    if found is None or not isinstance(found.value, float):
        raise HTTPException(400, f"unresolved reference: {ref}")
    nested = trees.derived(written)
    if nested is not None:
        return _Operand(found.value, found.unit, nested, foreign=nested.foreign)
    foreign = _foreign(resolver, found)
    return _Operand(found.value, found.unit, _Leaf(found.value, foreign), foreign=foreign)


def _number(x: Any, unit: str | None) -> _Figure | None:
    """``x`` with ``unit`` when ``x`` is a finite number, else ``None``."""
    if isinstance(x, int | float) and not isinstance(x, bool) and math.isfinite(x):
        return float(x), unit
    return None


def _derived(
    operation: Operation, a: _Operand, b: _Operand, years: int | None
) -> tuple[float | None, str | None]:
    """The operation's value and unit (module docstring); ``(None, None)`` where it is undefined:
    a division by zero, growth from a base at or below zero, a cagr over a negative ratio, a
    result that is not finite, and an operand foreign in a currency with a money figure not
    foreign in that currency (method 16.4, rule 1). With such an operand a money unit is none
    (rule 2)."""
    if _unconverted(a, b) or _unconverted(b, a):
        return None, None
    value = _value(operation, a.value, b.value, years)
    if value is None:
        return None, None
    unit = _derived_unit(operation, a, b)
    if unit in MONEY_UNITS and (a.foreign or b.foreign):  # a stored derivation has no currency
        return value, None
    return value, unit


def _value(operation: Operation, x: float, y: float, years: int | None) -> float | None:
    """The operation over ``x`` and ``y`` (module docstring); ``None`` where it is undefined: a
    division by zero, growth from a base at or below zero, a cagr over a negative ratio and a
    result that is not finite."""
    value: float | None
    if operation == "difference":
        value = x - y
    elif operation == "sum":
        value = x + y
    elif operation == "product":
        value = x * y
    elif operation == "ratio":
        value = None if y == 0 else x / y
    elif y <= 0:  # growth from a base at or below zero has no meaning, as the guidance step's
        value = None
    elif operation == "growth":
        value = x / y - 1
    elif x / y < 0 or years is None:  # cagr: a negative ratio has no real root
        value = None
    else:
        value = (x / y) ** (1 / years) - 1
    return value if value is not None and math.isfinite(value) else None


def _unconverted(record: _Operand, other: _Operand) -> bool:
    """Whether ``record`` is foreign in a currency, a record in another currency than the
    reporting one or a derivation that carries one, and ``other`` a money figure not foreign in
    that same currency: a figure in ``currency`` or ``per-share``, or one foreign in another
    currency, money with its unit gone (method 16.4, rule 1). A sum or a ratio of the two would mix
    currencies until the record is converted."""
    return (
        record.foreign is not None
        and other.foreign != record.foreign
        and (other.unit in MONEY_UNITS or other.foreign is not None)
    )


def _derived_unit(operation: Operation, a: _Operand, b: _Operand) -> str | None:
    """A derivation's unit (module docstring). With a fixed number, which has none, the stored
    figure sets it: a sum, a difference or a product, and a ratio of the figure over the number,
    keep the figure's unit; a ratio of the number over the figure has none (spec 2026-11-15
    7.2)."""
    if operation in ("growth", "cagr"):
        return "percent"
    if a.fixed or b.fixed:
        return None if operation == "ratio" and a.fixed else (b if a.fixed else a).unit
    if operation == "product":
        return _product_unit(a.unit, b.unit)
    shared = a.unit if a.unit == b.unit else None
    if operation == "ratio":
        return None if shared is None else "multiple"
    return shared


def _product_unit(a: str | None, b: str | None) -> str | None:
    """A product's unit: a multiple, then a percent, leaves the other operand's unit; a figure a
    share times a count is a total in the currency; any other pair has none."""
    for scalar in ("multiple", "percent"):
        if scalar in (a, b):
            return b if a == scalar else a
    return "currency" if {a, b} == {"per-share", "count"} else None
