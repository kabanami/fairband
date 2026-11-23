"""A refresh reads a company's review again (spec 2026-11-06 Tier 2, 10.5 and 10.6; spec
2026-11-23 held reviewed value, 5.1 to 5.5; ``method.md`` 14.6 and 14.7).

A company holds the review it last made, by an override's write or drop, a moat class's write or
Review again (``store.reviews``). A refresh never changes it. ``follow_snapshot`` runs in the
value stage of a full, scoped or revalue refresh, in the transaction that writes the company's
snapshot: it runs the drop tests below, computes the review over the overrides still applied as
a ``reading``, carries the held review onto the new snapshot (``held.carry_held``) and stores the
facts of the held review's state (``held.read_again``). With no override left it computes no
reading, and the reading is then the snapshot's mechanical value; the held review stays, and
only a person's act ends it. A company that holds no review and has no applied override gets
nothing. A company with an applied override and no held review, a state no write of the API
makes, holds the review the refresh writes, so no override is hidden.

The moat class's write values the company through the same follow with ``made`` set (spec 5.1):
the review it writes is a made one, which the company holds from there, and with no override
left the company holds none.

The drop tests: the applied ``phase`` override's own tests (below) run first, then the route's,
then the other overrides' own tests on those left.

The route's test (spec 2026-11-14 8): the row's route is the route of the ``phase`` override still
applied, else of the new result's phase, the mechanical one, and each other override whose tag
that route does not read (``off_route``, by ``TAGS``) drops, by the system, with a ledger row
resting on the new snapshot, "the <route> route does not read the input" (``OFF_ROUTE``), the
route named as the write's route rule names it (``overrides.ROUTE_NAMES``), "the Decline route does
not read the input". Since it runs before the other overrides' tests, a period-tied override on a
route that no longer reads it drops with that reason, not as a changed reading. An unclassified
row, with no ``phase`` override left and no mechanical phase, has no route and keeps every
override: a row unclassified for one refresh does not lose its review's inputs. The web's
recompute drops the same overrides the same way (``drop_off_route``), on its snapshot's phase.

The own tests: a period-tied override drops, by the system, with a ledger row resting on the new
snapshot, on the first of these that holds (spec 2026-11-13 11a):

- "a newer period is on file than the one the override corrected": the new inputs' trailing
  period end is after the trailing period end of the snapshot the override was made on
  (``_trailing_end``); without both period ends this test is not read;
- "the input the override corrected changed": the engine's reading of the input on the new result
  (``overrides.current_reading``) is not the value the override corrected; a reading of none
  against a figure, or a figure against none, is a change.

The day the statements were fetched, the data date, drops nothing: a refetch of the same statements
leaves the correction applied. A snapshot's trailing period end is its result's ``trailing_end``; a
result stored before method 1.3 carries none, and its period end is the ``as_of`` of its
``shares_diluted`` input, which assembly dates at the newest quarterly row's period end, the fiscal
year's when that row holds no count (``method.md`` 4.2), so such a snapshot may read as an older
period, and its correction then drops as "a newer period is on file". Its trailing inputs
(``revenue_ttm``, ``eps_ttm``, ``operating_income_ttm``) cite the newest fiscal year's end and are
not read.

A lasting override of an NTM anchor (``earnings.ntm``, ``revenue.ntm``) drops the same way, "the
guided year has passed", when the fiscal year its guidance record guides (``guidance.anchor_year``,
the latest such year among the records it cites) is before the new snapshot's base year: the
fiscal year that holds most of the NTM window after the last reported period (four quarters, or
two half-years for a half-yearly reporter), as every route reads it (``anchor.base_year`` on the
new inputs and their trailing cadence). Without a base year, or without such a record, it stays.

A lasting ``earnings.sbc``, which takes 0 alone (``overrides.TagSpec.lasting_value``), drops the
same way, "the store holds a trailing stock pay above zero", when the new inputs' assembled
trailing stock pay (``inputs.trailing.sbc``) is above zero (spec 2026-11-13 7.3). A nil, or none
(no trailing figures, or a period that lacks the line), keeps it. The test reads the assembled
figure, not the result's ``sbc_ttm``, which a row refused before its route does not carry.

The overrides at a split (spec 2026-11-14 7, as amended at the build): ``engine_overrides`` makes
each applied row the engine's override, for the follow, the web's recompute (both through
``write_review``) and a sensitivity reading, on the share basis of the snapshot they value. A row
whose input is in dollars a share (``TAGS``' unit ``USD a share``: the NTM EPS, the two gaps, the
one-time item, the value outside the business) is divided by ρ, and one in shares (the diluted
count, the committed shares) multiplied by it, where ρ is the product of the ratios of the
company's splits on file (``inputs_splits.splits_for``) that the reviewed snapshot's figures saw
and the figures of the snapshot the override was made on did not. A snapshot's figures saw a split
dated at or before its basis date: the earlier of the price date and the data date of the snapshot
that assembled them, itself, or for a snapshot a price refresh made, which re-assembles nothing
and fetches no split, the company's latest earlier snapshot a full or scoped refresh or a revalue
made (``snapshots.assembling_snapshot``), else its own two dates. The split rule applies a split
only from the price date on, and the data date is the day the figures were fetched, so a refresh
on a split's day before the US close, its quote of the day before, has not seen the split. A ρ of
1, a row whose made-on snapshot is not on file, and a ratio or a total keep the figure entered.
A scaled override carries the words of its scaling (``Override.rescaled``): the figure as entered,
in the reporting currency its unit names as the flags print an amount a share ("$30.00 a share",
"SEK 30.00 a share") or in millions of shares ("60.0M shares"), and the splits in order, "entered
as $30.00 a share before the 2-for-1 split of 27 Jan 2027". The stored row keeps the figure
entered, and the drop tests read it as stored: the value a period-tied override corrected is
never scaled.

With an override left, ``write_review`` reviews the new result under the rest on the new inputs,
writes the review on the new snapshot, with the snapshot's validity window and its price facts
(the 52-week range and the one-, three- and five-year changes anchor on the date the refresh
valued the snapshot; the engine on another day, as an override written from the web writes a
review, would anchor them on that day's closes, and no override moves them), and its log row. A
review written at a refresh writes no ledger row: the review log records it, with its kind.

A price refresh computes no reading: its reprice stage carries the held review onto the
repriced snapshot (``held.carry_held``), and the facts of its state stay as they are.

``review_refusal`` runs for the refusal snapshot of a company the refresh could not value (a
failed fetch or valuation). A held review is carried onto it, and its state stays as it was: a
failed refresh is no reading and no reason. A company with an applied override and no held
review gets the refusal as its review, with no mechanical value and an empty bridge.

The drop tests and the reading run inside a savepoint of the snapshot's transaction: an
exception undoes their writes alone, the snapshot stands, and the reading written on it is a
refusal, "review failed: <class>: <message>", with an empty bridge, over the applied overrides,
and a warning is logged. Such a reading is no reason: the last good reading stands. The held
review is carried all the same.

A log row takes the mechanical phase, value, price and designation from the snapshot the review
is written on, the reviewed phase and value from the review (no value on a refusal), the
review's kind, and the latest secondary value and report stance the store holds
(``held.log_row``).
"""

import logging
import math
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date, datetime
from typing import cast

from fairband.engine.anchor import base_year
from fairband.engine.classifier import Deciles
from fairband.engine.held import trailing_end_of
from fairband.engine.overrides import (
    ANCHOR_METRICS,
    PHASES,
    ROUTE_NAMES,
    TAGS,
    Override,
    OverrideTag,
    current_reading,
    route_of,
)
from fairband.engine.review import Review, review_company
from fairband.engine.route import CompanyInputs, refusal_result
from fairband.engine.types import Phase, Route, ValuationResult
from fairband.policy import Policy
from fairband.refresh.held import basis_date, carry_held, log_row, read_again, savepoint
from fairband.refresh.inputs_splits import SplitRow, named_splits, splits_for
from fairband.reports.refs import guidance_cited
from fairband.store.db import transaction
from fairband.store.guidance import anchor_year, guidance_row
from fairband.store.ledger import SYSTEM, record
from fairband.store.overrides import OverrideRow, applied_overrides, as_override, drop_override
from fairband.store.reviews import (
    ReviewKind,
    clear_held,
    held_row,
    insert_review,
    latest_review_on,
    review_row,
)
from fairband.store.snapshots import snapshot_row

logger = logging.getLogger("fairband.refresh")

NEWER = "a newer period is on file than the one the override corrected"
CHANGED = "the input the override corrected changed"
PASSED = "the guided year has passed"
ON_FILE = "the store holds a trailing stock pay above zero"
# The route drop's reason, the route named by ``overrides.ROUTE_NAMES`` (spec 2026-11-14 8).
OFF_ROUTE = "the {route} route does not read the input"
# The units a split scales (``TAGS``): a figure a share is divided by the ratio, a count multiplied.
_A_SHARE, _SHARES = "USD a share", "shares"
_SCALED = frozenset({_A_SHARE, _SHARES})


def follow_snapshot(
    conn: sqlite3.Connection,
    inputs: CompanyInputs,
    result: ValuationResult,
    snapshot_id: int,
    deciles: Deciles | None,
    policy: Policy,
    today: date,
    refresh_id: int | None,
    clock: Callable[[], datetime],
    *,
    made: bool = False,
) -> int | None:
    """Follow snapshot ``snapshot_id``, the company's mechanical ``result`` on ``inputs`` (module
    docstring): the drop tests, the route's among them, then the review over the overrides left.
    For a company that holds a review it is a reading, and the held review is carried onto the
    snapshot with the facts of its state stored. With ``made``, a moat class's write, and for a
    company that holds none, it is a made review, which the company holds; with no override left
    a ``made`` follow leaves the company with no review. The id of the company's current review
    on the snapshot, the held copy or the made review; ``None`` when it holds none."""
    symbol = result.symbol
    with transaction(conn):
        held = None if made else held_row(conn, symbol)
        kind: ReviewKind = "made" if held is None else "reading"
        made_id = None if held is None else held.review_id
        failed = False
        try:
            with savepoint(conn, "review"):
                written = _follow(
                    conn,
                    inputs,
                    result,
                    snapshot_id,
                    deciles,
                    policy,
                    today,
                    refresh_id,
                    clock,
                    kind,
                    made_id,
                )
        except Exception as exc:  # noqa: BLE001 - the snapshot stands; the review is the refusal
            failed = True
            written = _review_failed(
                conn, result, snapshot_id, policy, refresh_id, clock, exc, kind, made_id
            )
        if held is None:
            if made and written is None:
                clear_held(conn, symbol)
            return written
        carry_held(conn, symbol, snapshot_id, policy, refresh_id, clock)
        if not failed:
            reading = None if written is None else review_row(conn, written)
            trailing = inputs.trailing
            trailing_end = None if trailing is None else trailing.period_end
            read_again(conn, symbol, reading, result, trailing_end, policy, clock())
        current = latest_review_on(conn, snapshot_id)
        return None if current is None else current.id


def _follow(
    conn: sqlite3.Connection,
    inputs: CompanyInputs,
    result: ValuationResult,
    snapshot_id: int,
    deciles: Deciles | None,
    policy: Policy,
    today: date,
    refresh_id: int | None,
    clock: Callable[[], datetime],
    kind: ReviewKind,
    made_id: int | None,
) -> int | None:
    """The drop tests, then the review over the overrides left, written as ``kind``; ``None``
    with none left."""
    symbol = result.symbol
    trailing = inputs.trailing
    base = (
        None
        if trailing is None
        else base_year(inputs.quarter_estimates, trailing.period_end, trailing.cadence)
    )
    trailing_end = None if trailing is None else trailing.period_end
    stored_sbc = None if trailing is None else trailing.sbc

    def holds(override: OverrideRow) -> bool:
        """Whether ``override`` holds on ``result``; one that does not is dropped."""
        reason = _drop_reason(conn, override, result, base, trailing_end, stored_sbc)
        if reason is not None:
            _system_drop(conn, override, reason, snapshot_id, clock())
        return reason is None

    applied = applied_overrides(conn, symbol)
    # the phase override's own tests first: the route is the one the row then takes
    phases = [o for o in applied if o.tag == "phase" and holds(o)]
    others = [o for o in applied if o.tag != "phase"]
    stale = drop_off_route(conn, [*phases, *others], result.phase.phase, snapshot_id, clock)
    gone = {o.id for o, _ in stale}
    kept = [*phases, *(o for o in others if o.id not in gone and holds(o))]
    if not kept:
        return None
    return write_review(
        conn,
        inputs,
        result,
        snapshot_id,
        kept,
        deciles,
        policy,
        today,
        refresh_id,
        clock,
        kind=kind,
        made_id=made_id,
    )


def off_route(route: Route | None, rows: Sequence[OverrideRow]) -> list[OverrideRow]:
    """The ``rows`` the row's ``route`` does not read: each whose tag is not ``phase``, which
    every route reads, and whose ``TAGS`` entry does not hold ``route``; none when ``route`` is
    ``None``, an unclassified row's (module docstring)."""
    if route is None:
        return []
    others = (o for o in rows if o.tag != "phase")
    return [o for o in others if route not in TAGS[cast(OverrideTag, o.tag)].routes]


def row_route(rows: Sequence[OverrideRow], phase: Phase | None) -> Route | None:
    """The route the row takes: the route of its applied ``phase`` override among ``rows``, else
    of ``phase``, its mechanical phase; ``None`` for neither, an unclassified row."""
    phases = [*(o.new for o in rows if o.tag == "phase"), phase]
    return next((route_of(cast(Phase, p)) for p in phases if p in PHASES), None)


def drop_off_route(
    conn: sqlite3.Connection,
    rows: Sequence[OverrideRow],
    phase: Phase | None,
    snapshot_id: int,
    clock: Callable[[], datetime],
) -> list[tuple[OverrideRow, str]]:
    """Drop, by the system, each of the applied ``rows`` that the row's route (``row_route``, on
    the mechanical ``phase``) does not read (``off_route``), each with its ledger row resting on
    snapshot ``snapshot_id``: the rows dropped, each with the reason, ``OFF_ROUTE`` naming the
    route as the write's route rule names it. The follow and the web's recompute share it."""
    route = row_route(rows, phase)
    if route is None:
        return []
    reason = OFF_ROUTE.format(route=ROUTE_NAMES[route])
    stale = off_route(route, rows)
    for override in stale:
        _system_drop(conn, override, reason, snapshot_id, clock())
    return [(o, reason) for o in stale]


def _system_drop(
    conn: sqlite3.Connection, override: OverrideRow, reason: str, snapshot_id: int, at: datetime
) -> None:
    """Drop ``override`` by the system for ``reason`` at ``at``, with its ledger row resting on
    snapshot ``snapshot_id``."""
    drop_override(conn, override.id, reason, at)
    record(
        conn,
        SYSTEM,
        at,
        "override-drop",
        override.symbol,
        "overrides",
        override.id,
        snapshot_id=snapshot_id,
        summary=f"{override.tag} dropped: {reason}",
    )


def write_review(
    conn: sqlite3.Connection,
    inputs: CompanyInputs,
    mechanical: ValuationResult,
    snapshot_id: int,
    overrides: Sequence[OverrideRow],
    deciles: Deciles | None,
    policy: Policy,
    today: date,
    refresh_id: int | None,
    clock: Callable[[], datetime],
    *,
    kind: ReviewKind = "made",
    made_id: int | None = None,
) -> int:
    """Review ``mechanical``, snapshot ``snapshot_id``'s result on ``inputs``, under the applied
    ``overrides`` on its share basis (``engine_overrides``); write the review on the snapshot,
    valid as long as it and with its price facts (module docstring), and its log row; the
    review's id. A ``made`` review, a person's act's, becomes the one the company holds
    (``store.reviews.insert_review``); a refresh's ``reading`` names the made review it reads
    again in ``made_id``."""
    engine = engine_overrides(conn, mechanical.symbol, overrides, snapshot_id)
    review = review_company(inputs, deciles, policy, today, engine, mechanical)
    result = replace(review.result, valid_until=mechanical.valid_until)
    if "price_facts" in mechanical.intermediates and "price_facts" in result.intermediates:
        facts = {"price_facts": mechanical.intermediates["price_facts"]}
        result = replace(result, intermediates=result.intermediates | facts)
    review = replace(review, result=result)
    review_id = insert_review(
        conn,
        review,
        mechanical.symbol,
        snapshot_id,
        refresh_id,
        kind=kind,
        made_id=made_id,
        clock=clock,
    )
    log_row(conn, clock(), refresh_id, snapshot_id, review_id, mechanical, review.result, kind)
    return review_id


def engine_overrides(
    conn: sqlite3.Connection, symbol: str, rows: Sequence[OverrideRow], snapshot_id: int
) -> list[Override]:
    """Each of ``rows``, applied overrides of ``symbol``, as the engine reads it on the share basis
    of snapshot ``snapshot_id``, the snapshot reviewed: a figure a share ÷ ρ and a count × ρ, with
    the words of the scaling, where ρ is the product of the ratios of the splits that snapshot's
    figures saw and those of the snapshot the row was made on did not, each dated after the made-on
    snapshot's basis date and at or before the reviewed one's (``held.basis_date``, module
    docstring)."""
    splits = splits_for(conn, symbol)
    if not splits:
        return [as_override(o) for o in rows]
    reviewed = basis_date(conn, snapshot_id)
    made_on = {i: basis_date(conn, i) for i in {o.snapshot_id for o in rows}}
    out = []
    for row in rows:
        made = made_on[row.snapshot_id]
        seen: tuple[SplitRow, ...] = ()
        if made is not None and reviewed is not None:
            seen = tuple(s for s in splits if made < s.date <= reviewed)
        out.append(_on_basis(row, seen))
    return out


def _on_basis(row: OverrideRow, splits: Sequence[SplitRow]) -> Override:
    """``row`` as the engine's override after ``splits``, the splits since it was made, oldest
    first: in dollars a share ÷ their ratio's product ρ, in shares × ρ, with the words of the
    scaling; as entered for a ρ of 1 and for an input in any other unit."""
    engine = as_override(row)
    unit = TAGS[engine.tag].unit
    rho = math.prod(s.ratio for s in splits)
    if rho == 1 or unit not in _SCALED or not isinstance(row.new, int | float):
        return engine
    value = row.new / rho if unit == _A_SHARE else row.new * rho
    words = f"entered as {_entered(row.new, row.unit)} before {named_splits(splits)}"
    return replace(engine, value=value, rescaled=words)


def _entered(figure: float, unit: str) -> str:
    """The figure as the agent entered it in the row's ``unit``: an amount a share to two
    decimals after ``$``, or after the reporting currency's code its unit names ("SEK a share"),
    a negative one with the minus sign first, as the flags print one; a count in millions to one
    decimal, "60.0M shares"."""
    if unit == _SHARES:
        return f"{figure / 1e6:,.1f}M shares"
    code = unit.removesuffix(" a share") if unit.endswith(" a share") else "USD"
    sign = "$" if code == "USD" else f"{code} "
    return f"{'−' if figure < 0 else ''}{sign}{abs(figure):,.2f} a share"


def review_refusal(
    conn: sqlite3.Connection,
    result: ValuationResult,
    snapshot_id: int,
    policy: Policy,
    refresh_id: int,
    clock: Callable[[], datetime],
) -> int | None:
    """For ``result``, the refusal snapshot ``snapshot_id`` of a company the refresh could not
    value (module docstring): the held review carried onto it, its state as it was; for a company
    that holds none, the refusal itself as its review over the applied overrides, with its log
    row. The id of the review on the snapshot; ``None`` with neither."""
    if held_row(conn, result.symbol) is not None:
        return carry_held(conn, result.symbol, snapshot_id, policy, refresh_id, clock)
    return _write_refusal(conn, result, result, snapshot_id, refresh_id, clock, "made", None)


def _review_failed(
    conn: sqlite3.Connection,
    mechanical: ValuationResult,
    snapshot_id: int,
    policy: Policy,
    refresh_id: int | None,
    clock: Callable[[], datetime],
    exc: Exception,
    kind: ReviewKind,
    made_id: int | None,
) -> int | None:
    """The refusal review of a follow that raised ``exc``, of ``kind``, on the snapshot it
    followed and valid as long as it; a warning names the company and the refusal."""
    detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
    reason = f"review failed: {detail}"
    logger.warning("%s: %s", mechanical.symbol, reason)
    refused = refusal_result(
        mechanical.symbol,
        reason,
        policy,
        mechanical.data_date,
        price=mechanical.price,
        price_date=mechanical.price_date,
        deciles_refresh_id=mechanical.deciles_refresh_id,
    )
    refused = replace(refused, valid_until=mechanical.valid_until)
    return _write_refusal(conn, mechanical, refused, snapshot_id, refresh_id, clock, kind, made_id)


def _write_refusal(
    conn: sqlite3.Connection,
    mechanical: ValuationResult,
    refused: ValuationResult,
    snapshot_id: int,
    refresh_id: int | None,
    clock: Callable[[], datetime],
    kind: ReviewKind,
    made_id: int | None,
) -> int | None:
    """``refused`` as the review of ``mechanical``, snapshot ``snapshot_id``'s result, of
    ``kind``: an empty bridge over the applied overrides, with its log row; ``None`` with none
    applied."""
    applied = applied_overrides(conn, mechanical.symbol)
    if not applied:
        return None
    review = Review(refused, mechanical.value, (), tuple(o.id for o in applied))
    review_id = insert_review(
        conn,
        review,
        mechanical.symbol,
        snapshot_id,
        refresh_id,
        kind=kind,
        made_id=made_id,
        clock=clock,
    )
    log_row(conn, clock(), refresh_id, snapshot_id, review_id, mechanical, refused, kind)
    return review_id


def _drop_reason(
    conn: sqlite3.Connection,
    override: OverrideRow,
    result: ValuationResult,
    base: int | None,
    trailing_end: date | None,
    stored_sbc: float | None,
) -> str | None:
    """Why ``override`` no longer holds on ``result``, whose base year is ``base``, whose
    trailing period end is ``trailing_end`` and whose inputs' trailing stock pay is
    ``stored_sbc``, or ``None`` (module docstring)."""
    if override.lifetime == "lasting":
        if override.tag == "earnings.sbc" and stored_sbc is not None and stored_sbc > 0:
            return ON_FILE
        return _guided_year_passed(conn, override, base)
    made_on = snapshot_row(conn, override.snapshot_id)
    corrected = None if made_on is None else trailing_end_of(made_on.result)
    if trailing_end is not None and corrected is not None and trailing_end > corrected:
        return NEWER
    if current_reading(result, cast(OverrideTag, override.tag)) != override.corrected_value:
        return CHANGED
    return None


def _guided_year_passed(
    conn: sqlite3.Connection, override: OverrideRow, base: int | None
) -> str | None:
    """``PASSED`` when the lasting NTM anchor ``override`` guides a fiscal year before ``base``."""
    if override.tag not in ANCHOR_METRICS or base is None:
        return None
    guided = (e for e in override.evidence if e.get("kind") == "guidance")
    cited = (guidance_cited(str(e.get("ref", ""))) for e in guided)
    rows = (guidance_row(conn, i) for i in cited if i is not None)
    years = [y for r in rows if r is not None and (y := anchor_year(override.tag, r)) is not None]
    return PASSED if years and max(years) < base else None
