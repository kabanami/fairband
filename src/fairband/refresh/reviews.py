"""A review follows its company's snapshots (spec 2026-11-06 Tier 2, 10.5 and 10.6; ``method.md``
14.6 and 14.7).

``follow_snapshot`` runs in the value stage of a full, scoped or revalue refresh, in the
transaction that writes the company's snapshot. A company with no applied override gets nothing.
Otherwise each period-tied override is checked first, and drops, by the system, with a ledger row
resting on the new snapshot:

- "the statements moved past the override's snapshot": the company's data date is after the data
  date of the snapshot the override was made on;
- "the input the override corrected changed": the engine's reading of the input on the new result
  (``overrides.current_reading``) is not the value the override corrected; a reading of none
  against a figure, or a figure against none, is a change.

A lasting override of an NTM anchor (``earnings.ntm``, ``revenue.ntm``) drops the same way, "the
guided year has passed", when the fiscal year its guidance record guides (``guidance.anchor_year``,
the latest such year among the records it cites) is before the new snapshot's base year: the
fiscal year that holds most of the four quarters after the last reported one, as every route
reads it (``anchor.base_year`` on the new inputs). Without a base year, or without such a record,
it stays.

With an override left, ``write_review`` reviews the new result under the rest on the new inputs,
writes the review on the new snapshot, with the snapshot's validity window and its price facts
(the 52-week range and the one-, three- and five-year changes anchor on the date the refresh
valued the snapshot; the engine on another day, as an override written from the web writes a
review, would anchor them on that day's closes, and no override moves them), and its log row;
with none left, no review is written and the company's current review is cleared
(``store.reviews``). A review written at a refresh writes no ledger row: the review log records
it.

``reprice_review`` runs in the reprice stage of a price refresh, in the transaction that writes
the repriced snapshot: the company's current review, when it is on the snapshot repriced, through
``route.reprice`` at the quote, so its value, levels, validity, bridge and override ids stay and
its designation follows the price, written on the new snapshot with its log row; a review in
another currency reprices at the pair's quote the snapshot took, its USD value moving with the
rate, and so its mechanical value is the repriced snapshot's and each bridge line's change a
share is scaled by the old rate ÷ the new one, its readings in the currency staying, so the
mechanical value and the changes still sum to the reviewed value. The snapshot's rate decides
(``types.rated``), not the review's: a refusal review of a failed follow, which carries no
intermediates, on a snapshot in another currency shows the repriced snapshot's value too. A
review on a USD snapshot keeps its mechanical value and bridge as they were. A company with
no current review, or one on another snapshot, gets none.

``review_refusal`` gives the refusal snapshot of a company the refresh could not value (a failed
fetch or valuation) a review that is that refusal, with no mechanical value and an empty bridge,
over the applied overrides, so the current review follows the snapshot.

The follow and the reprice run inside a savepoint of the snapshot's transaction: an exception
undoes their writes alone, the snapshot stands, and the review written on it is a refusal, "review
failed: <class>: <message>", with an empty bridge, over the applied overrides, and a warning is
logged.

A log row takes the mechanical phase, value, price and designation from the snapshot the review
follows, the reviewed phase and value from the review (no value on a refusal), and the latest
secondary value and report stance the store holds.
"""

import logging
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime
from typing import cast

from fairband.engine.anchor import base_year
from fairband.engine.classifier import Deciles
from fairband.engine.overrides import ANCHOR_METRICS, OverrideTag, current_reading
from fairband.engine.review import BridgeLine, Review, review_company
from fairband.engine.route import CompanyInputs, refusal_result, reprice
from fairband.engine.types import ValuationResult, money_of, rated
from fairband.policy import Policy
from fairband.reports.refs import guidance_cited
from fairband.store.db import transaction
from fairband.store.guidance import anchor_year, guidance_row
from fairband.store.ledger import SYSTEM, record
from fairband.store.overrides import OverrideRow, applied_overrides, as_override, drop_override
from fairband.store.reviews import (
    insert_review,
    latest_review,
    latest_secondary_value,
    latest_stance,
    log_review,
)
from fairband.store.snapshots import snapshot_row

logger = logging.getLogger("fairband.refresh")

MOVED = "the statements moved past the override's snapshot"
CHANGED = "the input the override corrected changed"
PASSED = "the guided year has passed"


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
) -> int | None:
    """The review written on snapshot ``snapshot_id``, the company's mechanical ``result`` on
    ``inputs``, after the period-tied check (module docstring); ``None`` with no applied override
    left."""
    with transaction(conn):
        try:
            with _savepoint(conn):
                return _follow(
                    conn, inputs, result, snapshot_id, deciles, policy, today, refresh_id, clock
                )
        except Exception as exc:  # noqa: BLE001 - the snapshot stands; the review is the refusal
            return _review_failed(conn, result, snapshot_id, policy, refresh_id, clock, exc)


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
) -> int | None:
    symbol = result.symbol
    trailing = inputs.trailing
    base = None if trailing is None else base_year(inputs.quarter_estimates, trailing.period_end)
    kept = []
    for override in applied_overrides(conn, symbol):
        reason = _drop_reason(conn, override, result, base)
        if reason is None:
            kept.append(override)
            continue
        at = clock()
        drop_override(conn, override.id, reason, at)
        summary = f"{override.tag} dropped: {reason}"
        record(
            conn,
            SYSTEM,
            at,
            "override-drop",
            symbol,
            "overrides",
            override.id,
            snapshot_id=snapshot_id,
            summary=summary,
        )
    if not kept:
        return None
    return write_review(
        conn, inputs, result, snapshot_id, kept, deciles, policy, today, refresh_id, clock
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
) -> int:
    """Review ``mechanical``, snapshot ``snapshot_id``'s result on ``inputs``, under the applied
    ``overrides``; write the review on the snapshot, valid as long as it and with its price facts
    (module docstring), and its log row; the review's id."""
    engine = [as_override(o) for o in overrides]
    review = review_company(inputs, deciles, policy, today, engine, mechanical)
    result = replace(review.result, valid_until=mechanical.valid_until)
    if "price_facts" in mechanical.intermediates and "price_facts" in result.intermediates:
        facts = {"price_facts": mechanical.intermediates["price_facts"]}
        result = replace(result, intermediates=result.intermediates | facts)
    review = replace(review, result=result)
    review_id = insert_review(conn, review, mechanical.symbol, snapshot_id, refresh_id, clock=clock)
    _log(conn, clock(), refresh_id, snapshot_id, review_id, mechanical, review.result)
    return review_id


def reprice_review(
    conn: sqlite3.Connection,
    symbol: str,
    snapshot_id: int,
    price: float,
    price_date: date,
    policy: Policy,
    refresh_id: int,
    clock: Callable[[], datetime],
    *,
    observed_at: datetime,
    entered_at: datetime,
    repriced: int,
    fx_rate: float | None = None,
    fx_date: date | None = None,
    fx_observed_at: datetime | None = None,
) -> int | None:
    """The company's current review, when it is on snapshot ``repriced``, repriced at ``price``
    (and, in another currency, at the pair's quote ``fx_rate`` of ``fx_date``, observed at
    ``fx_observed_at``, when given) and
    written on ``snapshot_id``, the snapshot ``repriced`` became, with its log row; ``None``
    without such a review."""
    with transaction(conn):
        try:
            with _savepoint(conn):
                return _reprice(
                    conn,
                    symbol,
                    snapshot_id,
                    price,
                    price_date,
                    policy,
                    refresh_id,
                    clock,
                    observed_at,
                    entered_at,
                    repriced,
                    fx_rate,
                    fx_date,
                    fx_observed_at,
                )
        except Exception as exc:  # noqa: BLE001 - the snapshot stands; the review is the refusal
            mechanical = _snapshot_result(conn, snapshot_id)
            return _review_failed(conn, mechanical, snapshot_id, policy, refresh_id, clock, exc)


def _reprice(
    conn: sqlite3.Connection,
    symbol: str,
    snapshot_id: int,
    price: float,
    price_date: date,
    policy: Policy,
    refresh_id: int,
    clock: Callable[[], datetime],
    observed_at: datetime,
    entered_at: datetime,
    repriced: int,
    fx_rate: float | None,
    fx_date: date | None,
    fx_observed_at: datetime | None,
) -> int | None:
    current = latest_review(conn, symbol)
    if current is None or current.snapshot_id != repriced:
        return None
    mechanical = _snapshot_result(conn, snapshot_id)
    result = reprice(
        current.result,
        price,
        price_date,
        policy,
        fx_rate=fx_rate,
        fx_date=fx_date,
        fx_observed_at=fx_observed_at,
        observed_at=observed_at,
        entered_at=entered_at,
    )
    bridge = tuple(BridgeLine(**line) for line in current.bridge)
    mechanical_value = current.mechanical_value
    was = money_of(current.result)[0]
    if rated(mechanical):  # the USD figures move with the snapshot's rate (module docstring)
        k = was / money_of(result)[0]
        mechanical_value = mechanical.value
        bridge = tuple(replace(b, delta=None if b.delta is None else b.delta * k) for b in bridge)
    review = Review(result, mechanical_value, bridge, current.override_ids)
    review_id = insert_review(conn, review, symbol, snapshot_id, refresh_id, clock=clock)
    _log(conn, clock(), refresh_id, snapshot_id, review_id, mechanical, result)
    return review_id


def review_refusal(
    conn: sqlite3.Connection,
    result: ValuationResult,
    snapshot_id: int,
    refresh_id: int,
    clock: Callable[[], datetime],
) -> int | None:
    """The review of ``result``, the refusal snapshot ``snapshot_id`` of a company the refresh
    could not value: the refusal itself, with its log row; ``None`` with no applied override."""
    return _write_refusal(conn, result, result, snapshot_id, refresh_id, clock)


def _snapshot_result(conn: sqlite3.Connection, snapshot_id: int) -> ValuationResult:
    found = snapshot_row(conn, snapshot_id)
    if found is None:
        raise KeyError(snapshot_id)
    return found.result


@contextmanager
def _savepoint(conn: sqlite3.Connection) -> Iterator[None]:
    """A savepoint in the caller's transaction: an exception undoes the block's writes alone."""
    conn.execute("SAVEPOINT review")
    try:
        yield
    except BaseException:
        conn.execute("ROLLBACK TO review")
        conn.execute("RELEASE review")
        raise
    conn.execute("RELEASE review")


def _review_failed(
    conn: sqlite3.Connection,
    mechanical: ValuationResult,
    snapshot_id: int,
    policy: Policy,
    refresh_id: int | None,
    clock: Callable[[], datetime],
    exc: Exception,
) -> int | None:
    """The refusal review of a follow or a reprice that raised ``exc``, on the snapshot it
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
    return _write_refusal(conn, mechanical, refused, snapshot_id, refresh_id, clock)


def _write_refusal(
    conn: sqlite3.Connection,
    mechanical: ValuationResult,
    refused: ValuationResult,
    snapshot_id: int,
    refresh_id: int | None,
    clock: Callable[[], datetime],
) -> int | None:
    """``refused`` as the review of ``mechanical``, snapshot ``snapshot_id``'s result: an empty
    bridge over the applied overrides, with its log row; ``None`` with none applied."""
    applied = applied_overrides(conn, mechanical.symbol)
    if not applied:
        return None
    review = Review(refused, mechanical.value, (), tuple(o.id for o in applied))
    review_id = insert_review(conn, review, mechanical.symbol, snapshot_id, refresh_id, clock=clock)
    _log(conn, clock(), refresh_id, snapshot_id, review_id, mechanical, refused)
    return review_id


def _drop_reason(
    conn: sqlite3.Connection, override: OverrideRow, result: ValuationResult, base: int | None
) -> str | None:
    """Why ``override`` no longer holds on ``result``, whose base year is ``base``, or ``None``
    (module docstring)."""
    if override.lifetime == "lasting":
        return _guided_year_passed(conn, override, base)
    made_on = snapshot_row(conn, override.snapshot_id)
    if made_on is not None and result.data_date > made_on.data_date:
        return MOVED
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


def _log(
    conn: sqlite3.Connection,
    at: datetime,
    refresh_id: int | None,
    snapshot_id: int,
    review_id: int,
    mechanical: ValuationResult,
    reviewed: ValuationResult,
) -> None:
    symbol = mechanical.symbol
    log_review(
        conn,
        at,
        symbol,
        refresh_id,
        snapshot_id,
        review_id,
        mechanical.phase.phase,
        mechanical.value,
        reviewed.phase.phase,
        reviewed.value,
        latest_secondary_value(conn, symbol),
        mechanical.price,
        mechanical.designation,
        latest_stance(conn, symbol),
    )
