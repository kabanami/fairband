"""The held review at a refresh (spec 2026-11-23 held reviewed value, 5.2 to 5.4; ``method.md``
14.6).

A company holds the review it last made (``store.reviews``). A refresh never changes it. It
carries it: ``carry_held`` writes the held review on the refresh's new snapshot as a ``held``
copy, so every reader finds it on the latest snapshot. A price refresh, a full or scoped refresh
and a revalue carry alike, and so does the refusal snapshot of a company whose fetch or
valuation failed.

What a copy keeps: the value in the company's currency, the bridge with the mechanical value of
the day the review was made, the overrides inside, the flags and the validity window. What moves,
none of it a change of opinion:

- the price and its date, the new snapshot's, and with them price ÷ value and the word;
- at a split, the value a share ÷ ρ, the product of the ratios of the splits the new snapshot's
  figures saw and the copy's snapshot did not (``basis_date``, the rule that scales an override);
- for a company in another currency, the value in US dollars, its value in the currency ÷ the
  new snapshot's rate;
- the mechanical value and each bridge line's change a share by the same factor, so they still
  sum to the value.

The figures that follow the price (the implied growth and its sensitivities, the expected return,
the multiples, the long-runway flag) are rebuilt by ``route.reprice`` only under the price
refresh's own three tests: the held result cites the current method version, the policy's
version and its settings hash. With one of them changed, after a split, or when the rebuild
raises, the copy takes the plain move: the figures above on the policy in force, every other
figure as made, and the intermediates' ``held_as_made``, ``{why, since}``: ``method``, ``policy``,
``settings``, ``split`` or ``failed``, and the price date of the figures it keeps. A copy of a
plain copy stays plain. Today's formulas are never run on a result of another method version.

``read_again`` stores, after a refresh that values, the facts of the held review's state
(``engine.held``; spec 5.3): when a refresh first read it again; the newer trailing period's end,
when the new snapshot's is after the one of the snapshot the review was made on; the overrides
inside it that the system dropped since, each with its tag, its reason and the drop's time; the
newest good reading, the refresh's review over the overrides still applied, or the mechanical
value with none left (a reading that failed is none, and the last good one stands); and the day
of the first refresh that found a reason, cleared when none holds. A price refresh and a failed
company store nothing.
"""

import logging
import math
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime

from fairband.engine import METHOD_VERSION
from fairband.engine.designation import designation_for
from fairband.engine.held import READING_FAILED, reading_outside
from fairband.engine.levels import levels_for, moat_of
from fairband.engine.review import BridgeLine, Review
from fairband.engine.route import reprice
from fairband.engine.types import Levels, ValuationResult, money_of, rated
from fairband.policy import Policy
from fairband.refresh.inputs_splits import splits_for
from fairband.store.db import transaction
from fairband.store.overrides import override_row
from fairband.store.reviews import (
    ReviewKind,
    ReviewRow,
    held_row,
    insert_review,
    latest_review,
    latest_secondary_value,
    latest_stance,
    log_review,
    review_row,
    set_held_state,
)
from fairband.store.snapshots import SnapshotRow, assembling_snapshot, snapshot_row

logger = logging.getLogger("fairband.refresh")


def carry_held(
    conn: sqlite3.Connection,
    symbol: str,
    snapshot_id: int,
    policy: Policy,
    refresh_id: int | None,
    clock: Callable[[], datetime],
) -> int | None:
    """Write the review ``symbol`` holds on snapshot ``snapshot_id`` as a ``held`` copy (module
    docstring), with its log row; the copy's id, the id of the review already on that snapshot,
    or ``None`` for a company that holds none. It runs in a savepoint of the caller's
    transaction: a copy that cannot be written leaves the snapshot as it is, logs a warning and
    gives ``None``, and the held review stays on its earlier snapshot."""
    held = held_row(conn, symbol)
    previous = None if held is None else latest_review(conn, symbol)
    if held is None or previous is None:
        return None
    if previous.snapshot_id == snapshot_id:
        return previous.id
    with transaction(conn):
        try:
            with savepoint(conn):
                snapshot = snapshot_row(conn, snapshot_id)
                if snapshot is None:
                    raise KeyError(snapshot_id)
                rho = _split_ratio(conn, symbol, previous.snapshot_id, snapshot_id)
                review = _moved(previous, snapshot, rho, policy)
                review_id = insert_review(
                    conn,
                    review,
                    symbol,
                    snapshot_id,
                    refresh_id,
                    kind="held",
                    made_id=held.review_id,
                    clock=clock,
                )
                log_row(
                    conn,
                    clock(),
                    refresh_id,
                    snapshot_id,
                    review_id,
                    snapshot.result,
                    review.result,
                )
                return review_id
        except Exception as exc:  # noqa: BLE001 - the snapshot stands; the held review stays
            logger.warning("%s: the held review was not carried: %r", symbol, exc)
            return None


def read_again(
    conn: sqlite3.Connection,
    symbol: str,
    reading: ReviewRow | None,
    mechanical: ValuationResult,
    trailing_end: date | None,
    policy: Policy,
    at: datetime,
) -> None:
    """Store the facts of the state of the review ``symbol`` holds after a refresh that values
    wrote ``mechanical``, the new snapshot's result, whose trailing period ends on
    ``trailing_end`` (module docstring). ``reading`` is the refresh's review over the overrides
    still applied, ``None`` with none left. Nothing for a company that holds none."""
    held = held_row(conn, symbol)
    made = None if held is None else review_row(conn, held.review_id)
    if held is None or made is None:
        return
    made_on = snapshot_row(conn, made.snapshot_id)
    made_end = None if made_on is None else trailing_end_of(made_on.result)
    newer = held.newer_period
    if trailing_end is not None and made_end is not None and trailing_end > made_end:
        newer = trailing_end
    dropped = _system_drops(conn, made.override_ids)
    value, refusal, when = held.reading_value, held.reading_refusal, held.reading_at
    if reading is None:
        value, refusal, when = mechanical.value, mechanical.refusal, at
    elif not (reading.refusal or "").startswith(READING_FAILED):
        value, refusal, when = reading.value, reading.refusal, at
    current = latest_review(conn, symbol)
    stands = None if current is None else current.value
    reason = (
        newer is not None
        or bool(dropped)
        or reading_outside(stands, value, refusal, policy.fair_band)
    )
    early = None
    if reason:
        days = [datetime.fromisoformat(str(d["at"])).date() for d in dropped if d["at"]]
        early = held.early_at or min([at.date(), *days])
    set_held_state(
        conn,
        replace(
            held,
            read_again_at=held.read_again_at or at,
            newer_period=newer,
            dropped=dropped,
            reading_value=value,
            reading_refusal=refusal,
            reading_at=when,
            early_at=early,
        ),
    )


def log_row(
    conn: sqlite3.Connection,
    at: datetime,
    refresh_id: int | None,
    snapshot_id: int,
    review_id: int,
    mechanical: ValuationResult,
    reviewed: ValuationResult,
    kind: ReviewKind = "held",
) -> None:
    """The log row of the review ``review_id`` of ``kind``, written on snapshot ``snapshot_id``:
    the mechanical phase, value, price and designation from ``mechanical``, the snapshot's
    result, the reviewed phase and value from ``reviewed``, and the latest secondary value and
    report stance the store holds."""
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
        kind,
    )


def basis_date(conn: sqlite3.Connection, snapshot_id: int) -> date | None:
    """The day up to which snapshot ``snapshot_id``'s figures saw the splits: the earlier of the
    price date and the data date of the snapshot that assembled them
    (``snapshots.assembling_snapshot``), else of its own; ``None`` without the snapshot."""
    found = assembling_snapshot(conn, snapshot_id) or snapshot_row(conn, snapshot_id)
    if found is None:
        return None
    return found.data_date if found.price_date is None else min(found.price_date, found.data_date)


def trailing_end_of(result: ValuationResult) -> date | None:
    """The trailing period end of the snapshot ``result``: its ``trailing_end``; without one (a
    result stored before method 1.3), the ``as_of`` of its ``shares_diluted`` input, the newest
    quarterly row's period end, the fiscal year's when that row holds no count; else ``None``."""
    stored = result.intermediates.get("trailing_end")
    if stored is not None:
        return date.fromisoformat(stored)
    shares = next((i for i in result.inputs if i.name == "shares_diluted"), None)
    return None if shares is None else shares.provenance.as_of


@contextmanager
def savepoint(conn: sqlite3.Connection, name: str = "held") -> Iterator[None]:
    """A savepoint in the caller's transaction: an exception undoes the block's writes alone."""
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        conn.execute(f"ROLLBACK TO {name}")
        conn.execute(f"RELEASE {name}")
        raise
    conn.execute(f"RELEASE {name}")


def _split_ratio(conn: sqlite3.Connection, symbol: str, was_on: int, now_on: int) -> float:
    """ρ between two snapshots of ``symbol``: the product of the ratios of its splits on file
    dated after the basis date of ``was_on`` and at or before that of ``now_on``; 1 with no
    split between them or without both dates."""
    splits = splits_for(conn, symbol)
    if not splits:
        return 1.0
    was, now = basis_date(conn, was_on), basis_date(conn, now_on)
    if was is None or now is None:
        return 1.0
    return math.prod(s.ratio for s in splits if was < s.date <= now)


def _moved(previous: ReviewRow, snapshot: SnapshotRow, rho: float, policy: Policy) -> Review:
    """``previous``, the held review on its newest snapshot, as it reads on ``snapshot``, a newer
    one, after splits of ratio ``rho`` (module docstring)."""
    held = previous.result
    bridge = tuple(BridgeLine(**line) for line in previous.bridge)
    price, price_date = snapshot.price, snapshot.price_date
    if price is None or price_date is None or not (math.isfinite(price) and price > 0):
        return Review(held, previous.mechanical_value, bridge, previous.override_ids)
    if held.value is None:  # a made review that refuses holds no value: the price alone moves
        moved = replace(held, price=price, price_date=price_date)
        return Review(moved, previous.mechanical_value, bridge, previous.override_ids)
    rate = money_of(snapshot.result)[0] if rated(held) and rated(snapshot.result) else None
    why = _plain_reason(held, rho, policy)
    result = None
    if why is None:
        try:
            result = _rebuilt(held, snapshot, policy, rate)
        except Exception as exc:  # noqa: BLE001 - the plain move needs no rebuild
            logger.warning("%s: the held review was not rebuilt: %r", held.symbol, exc)
            why = "failed"
    if result is None:
        result = _plain(held, snapshot, rho, policy, rate, why or "failed")
    assert result.value is not None
    k = 1.0 if result.value == held.value else result.value / held.value
    mechanical_value = previous.mechanical_value
    if k != 1.0:
        mechanical_value = None if mechanical_value is None else mechanical_value * k
        bridge = tuple(replace(b, delta=None if b.delta is None else b.delta * k) for b in bridge)
    return Review(result, mechanical_value, bridge, previous.override_ids)


def _plain_reason(held: ValuationResult, rho: float, policy: Policy) -> str | None:
    """Why the copy of ``held`` takes the plain move, or ``None`` when its figures that follow
    the price are rebuilt: the price refresh's own three tests, and no split."""
    kept = held.intermediates.get("held_as_made")
    if isinstance(kept, dict):
        return str(kept.get("why"))
    if rho != 1:
        return "split"
    if held.method_version != METHOD_VERSION:
        return "method"
    if held.policy_version != policy.version:
        return "policy"
    if held.settings_hash != policy.settings_hash:
        return "settings"
    return None


def _rebuilt(
    held: ValuationResult, snapshot: SnapshotRow, policy: Policy, rate: float | None
) -> ValuationResult:
    """``held`` at ``snapshot``'s price and, in another currency, at its ``rate``, through
    ``route.reprice``, with the snapshot's own price and rate inputs."""
    assert snapshot.price is not None and snapshot.price_date is not None
    stored = snapshot.result.intermediates.get("fx_date")
    result = reprice(
        held,
        snapshot.price,
        snapshot.price_date,
        policy,
        fx_rate=rate,
        fx_date=None if rate is None or stored is None else date.fromisoformat(stored),
    )
    own = {i.name: i for i in snapshot.result.inputs if i.name in ("price", "fx_rate")}
    if rate is None:
        own.pop("fx_rate", None)
    return replace(result, inputs=tuple(own.get(i.name, i) for i in result.inputs))


def _plain(
    held: ValuationResult,
    snapshot: SnapshotRow,
    rho: float,
    policy: Policy,
    rate: float | None,
    why: str,
) -> ValuationResult:
    """The plain move of ``held`` onto ``snapshot`` (module docstring): the value ÷ ``rho`` and,
    in another currency, at ``rate``; the levels, price ÷ value and the word on ``policy``; and
    every other figure as made, with ``held_as_made``."""
    assert held.value is not None and snapshot.price is not None
    im = dict(held.intermediates)
    value = held.value / rho
    if rated(held):
        in_currency = im["value_in_currency"] / rho
        at_rate = money_of(held)[0] if rate is None else rate
        value = in_currency / at_rate
        im |= {"value_in_currency": in_currency, "fx_rate": at_rate}
        if rate is not None:
            im["fx_date"] = snapshot.result.intermediates.get("fx_date")
    moat = moat_of(held)
    levels = held.levels
    if moat is not None:
        levels = levels_for(value, moat, policy)
        price_to_value, word = designation_for(snapshot.price, value, policy.edges_for(moat))
    elif levels is not None:  # no class on file: the stored levels keep their place on the value
        k = value / held.value
        levels = Levels(
            buy=levels.buy * k,
            fair_low=levels.fair_low * k,
            fair_high=levels.fair_high * k,
            trim=levels.trim * k,
        )
        edges = (levels.buy / value, levels.fair_low / value, levels.fair_high / value)
        price_to_value, word = designation_for(snapshot.price, value, (*edges, levels.trim / value))
    else:
        price_to_value, word = snapshot.price / value, None
    since = None if held.price_date is None else held.price_date.isoformat()
    im["held_as_made"] = im.get("held_as_made") or {"why": why, "since": since}
    return replace(
        held,
        value=value,
        levels=levels,
        price=snapshot.price,
        price_date=snapshot.price_date,
        price_to_value=price_to_value,
        designation=word,
        intermediates=im,
    )


def _system_drops(
    conn: sqlite3.Connection, override_ids: tuple[int, ...]
) -> tuple[dict[str, object], ...]:
    """Those of ``override_ids``, the overrides inside a made review, that the system dropped:
    each dropped override with a ledger row ``override-drop`` of the system's, as ``{id, tag,
    reason, at}``, in id order. An override an agent dropped or replaced is none of them, nor is
    a ``moat.class`` override that method 1.8 moved to the moat table."""
    if not override_ids:
        return ()
    marks = ",".join("?" * len(override_ids))
    by_system = {
        row["ref_id"]
        for row in conn.execute(
            "SELECT ref_id FROM ledger WHERE kind = 'override-drop' AND principal = 'system'"
            f" AND ref_table = 'overrides' AND ref_id IN ({marks})",
            override_ids,
        )
    }
    out: list[dict[str, object]] = []
    for override_id in sorted(by_system):
        row = override_row(conn, override_id)
        if row is None or row.state != "dropped" or row.tag == "moat.class":
            continue
        at = None if row.dropped_at is None else row.dropped_at.isoformat()
        out.append({"id": row.id, "tag": row.tag, "reason": row.drop_reason, "at": at})
    return tuple(out)
