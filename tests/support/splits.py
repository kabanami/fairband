"""MGCO across a split, as the refresh reviews it (spec 2026-11-14 7, as amended at the build): its
2-for-1 split of 27 Jan 2027 falls between the basis date of the snapshot an override is made on
and that of the next snapshot, a snapshot's basis date the earlier of the price date and the data
date of the snapshot that assembled its figures. The fixture's figures stand on both: the split
rule's own scaling is ``tests/refresh/test_splits.py``'. ``tests/refresh/test_reviews_follow.py``
and ``tests/reports/test_render.py`` (Appendix A's two figures, spec 2026-11-15 8) use them."""

import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime

from fairband.engine import METHOD_VERSION
from fairband.engine.overrides import Lifetime, OverrideTag, current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.refresh.reviews import follow_snapshot
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.refreshes import create_refresh, current_refresh, finish_refresh
from fairband.store.reviews import ReviewRow, reviews_for
from fairband.store.snapshots import insert_snapshot, snapshot_row
from support.engine_companies import as_live, mature_growth_inputs, universe_deciles
from support.payloads import split_rows, store_payloads

SPLIT_DAY = date(2027, 1, 27)
BEFORE, AFTER = date(2027, 1, 10), date(2027, 2, 1)
TODAY = date(2026, 10, 31)  # the day MGCO is valued
AT = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)  # the time its snapshots and overrides are made
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "transcript", "ref": "Q3 call", "note": ""}]


def store_splits(conn: sqlite3.Connection, *splits: tuple[date, float, float]) -> None:
    """MGCO's ``splits`` answer, each split its day, numerator and denominator, stored as the
    fetch stores one."""
    store_payloads(conn, "MGCO", {"splits": split_rows("MGCO", *splits)}, AT)


def under(conn: sqlite3.Connection, policy: Policy, kind: str) -> int:
    """The running refresh of ``kind`` the test's snapshots are written under; a running one of
    another kind is finished first, since one refresh runs at a time."""
    running = current_refresh(conn)
    if running is not None and running.kind == kind:
        return running.id
    if running is not None:
        finish_refresh(conn, running.id, "done", AT)
    return create_refresh(conn, kind, None, policy.version, METHOD_VERSION, AT, EMPTY_SETTINGS_HASH)


def mgco_on(price_date: date, data_date: date) -> CompanyInputs:
    """MGCO as assembly dates it, quoted on ``price_date``, its statements fetched on
    ``data_date``."""
    return replace(as_live(mature_growth_inputs()), price_date=price_date, data_date=data_date)


def mgco_snapshot(
    conn: sqlite3.Connection,
    policy: Policy,
    price_date: date,
    data_date: date,
    kind: str = "revalue",
) -> int:
    """MGCO's snapshot quoted on ``price_date``, its statements fetched on ``data_date``, written
    under a refresh of ``kind``; its id."""
    result = value_company(mgco_on(price_date, data_date), universe_deciles(), policy, TODAY)
    return insert_snapshot(conn, result, under(conn, policy, kind), clock=lambda: AT)


def made_on_mgco(
    conn: sqlite3.Connection,
    snapshot_id: int,
    tag: OverrideTag,
    new: float | str,
    unit: str,
    lifetime: Lifetime = "lasting",
) -> int:
    """An applied override of MGCO's ``tag`` at ``new`` in ``unit``, made on snapshot
    ``snapshot_id``; a period-tied one corrects the engine's reading there."""
    made_on = snapshot_row(conn, snapshot_id)
    assert made_on is not None
    old = current_reading(made_on.result, tag)
    tied = lifetime == "period-tied"
    return insert_override(
        conn,
        "MGCO",
        tag,
        old,
        new,
        unit,
        "a stake",
        EVIDENCE,
        lifetime,
        "Q3 2026" if tied else None,
        old if tied else None,
        snapshot_id,
        AGENT,
        AT,
        "applied",
        "",
    )


def follow_mgco(
    conn: sqlite3.Connection, policy: Policy, price_date: date, data_date: date
) -> ReviewRow:
    """MGCO's next snapshot, quoted on ``price_date``, its statements fetched on ``data_date``,
    written by a revalue and followed: the review the follow computed on it over the applied
    overrides, a made review where MGCO held none and a reading where it holds one (spec
    2026-11-23 held reviewed value, 5.4)."""
    deciles = universe_deciles()
    inputs = mgco_on(price_date, data_date)
    result = value_company(inputs, deciles, policy, TODAY)
    refresh_id = under(conn, policy, "revalue")
    snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: AT)
    follow_snapshot(
        conn, inputs, result, snapshot_id, deciles, policy, TODAY, refresh_id, lambda: AT
    )
    [review] = [
        r for r in reviews_for(conn, "MGCO") if r.snapshot_id == snapshot_id and r.kind != "held"
    ]
    return review
