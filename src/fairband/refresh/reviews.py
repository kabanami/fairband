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

With an override left, ``write_review`` reviews the new result under the rest on the new inputs,
writes the review on the new snapshot and its log row; with none left, no review is written and
the company's current review is cleared (``store.reviews``).

``reprice_review`` runs in the reprice stage of a price refresh, in the transaction that writes
the repriced snapshot: the company's current review through ``route.reprice`` at the quote, so its
value, levels, validity, bridge and override ids stay and its designation follows the price,
written on the new snapshot with its log row. A company with no current review gets none.

A log row takes the mechanical phase, value, price and designation from the snapshot the review
follows, the reviewed phase and value from the review (no value on a refusal), and the latest
secondary value and report stance the store holds.
"""

import sqlite3
from collections.abc import Callable, Sequence
from datetime import date, datetime
from typing import cast

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import OverrideTag, current_reading
from fairband.engine.review import BridgeLine, Review, review_company
from fairband.engine.route import CompanyInputs, reprice
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
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

MOVED = "the statements moved past the override's snapshot"
CHANGED = "the input the override corrected changed"


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
    symbol = result.symbol
    kept = []
    for override in applied_overrides(conn, symbol):
        reason = None if override.lifetime == "lasting" else _drop_reason(conn, override, result)
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
    ``overrides``; write the review on the snapshot and its log row; the review's id."""
    engine = [as_override(o) for o in overrides]
    review = review_company(inputs, deciles, policy, today, engine, mechanical)
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
) -> int | None:
    """The company's current review repriced at ``price`` and written on the repriced snapshot
    ``snapshot_id``, with its log row; ``None`` without a current review."""
    current = latest_review(conn, symbol)
    if current is None:
        return None
    result = reprice(
        current.result, price, price_date, policy, observed_at=observed_at, entered_at=entered_at
    )
    bridge = tuple(BridgeLine(**line) for line in current.bridge)
    review = Review(result, current.mechanical_value, bridge, current.override_ids)
    review_id = insert_review(conn, review, symbol, snapshot_id, refresh_id, clock=clock)
    snapshot = snapshot_row(conn, snapshot_id)
    if snapshot is None:
        raise KeyError(snapshot_id)
    _log(conn, clock(), refresh_id, snapshot_id, review_id, snapshot.result, result)
    return review_id


def _drop_reason(
    conn: sqlite3.Connection, override: OverrideRow, result: ValuationResult
) -> str | None:
    """Why the period-tied ``override`` no longer holds on ``result``, or ``None``."""
    made_on = snapshot_row(conn, override.snapshot_id)
    if made_on is not None and result.data_date > made_on.data_date:
        return MOVED
    if current_reading(result, cast(OverrideTag, override.tag)) != override.corrected_value:
        return CHANGED
    return None


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
