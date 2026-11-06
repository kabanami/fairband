"""A review follows its company's snapshots (spec 2026-11-06 Tier 2, 10.5 and 10.6): every refresh
that writes a snapshot for a company with an applied override writes a review on it, and a log row
for it. A revalue, a scoped or a full refresh recomputes it on the new inputs, after dropping a
period-tied override whose input moved; a price refresh reprices it.

The refresh tests run on the four companies a full refresh of ``fixture_universe`` valued: ACME and
AXLE Mature Growth, MILD Mature Stable, NEWT refused for its target margin.
"""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from fixture_universe import serve_universe
from refresh_env import Env
from support.engine_companies import high_growth_inputs, universe_deciles
from vendor_double import FIXTURES

from fairband.engine import METHOD_VERSION
from fairband.engine.overrides import Lifetime, OverrideTag, current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.refresh.reviews import follow_snapshot
from fairband.store.ledger import SYSTEM, Writer, entries
from fairband.store.overrides import insert_override, override_row
from fairband.store.refreshes import create_refresh
from fairband.store.reviews import latest_review, review_log, reviews_for
from fairband.store.snapshots import insert_snapshot

AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "transcript", "ref": "Q3 call", "note": ""}]
CHANGED = "the input the override corrected changed"
MOVED = "the statements moved past the override's snapshot"


@pytest.fixture
def env_valued(env_without_universe: Env) -> Env:
    """The fixture universe after its full refresh (refresh 1), an hour later."""
    env = env_without_universe
    serve_universe(env.router)
    assert env.refresh().run("full") == 1
    env.router.calls.clear()
    env.router.symbol_calls.clear()
    env.progress.clear()
    env.clock.now += timedelta(hours=1)
    return env


def _override(
    env: Env,
    symbol: str,
    tag: OverrideTag,
    new: float | str,
    lifetime: Lifetime = "lasting",
    corrected: float | str | None = None,
) -> int:
    """An applied override of ``symbol`` made on its latest snapshot, stored as the route stores
    one."""
    snapshot = env.snapshot(symbol)
    old = current_reading(snapshot.result, tag)
    period = "FY2025" if lifetime == "period-tied" else None
    with closing(env.connect()) as conn:
        return insert_override(
            conn,
            symbol,
            tag,
            old,
            new,
            "ratio",
            "because",
            EVIDENCE,
            lifetime,
            period,
            corrected,
            snapshot.id,
            AGENT,
            env.clock(),
            "applied",
            "",
        )


def _quotes(prices: dict[str, float]) -> bytes:
    """ACME's quote fixture for each symbol at its price, stamped a day later."""
    [row] = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text())
    later = row["timestamp"] + 86_400
    rows = [row | {"symbol": s, "price": p, "timestamp": later} for s, p in prices.items()]
    return json.dumps(rows).encode()


def test_a_revalue_writes_a_review_for_a_company_with_an_applied_override(env_valued: Env) -> None:
    env = env_valued
    belief = _override(env, "ACME", "growth.belief", 0.08)
    refresh_id = env.refresh().run("revalue")
    snapshot = env.snapshot("ACME")
    assert snapshot.refresh_id == refresh_id
    with closing(env.connect()) as conn:
        review = latest_review(conn, "ACME")
        log = review_log(conn)
        others = [reviews_for(conn, s) for s in ("AXLE", "MILD", "NEWT")]
    assert review is not None
    assert (review.snapshot_id, review.refresh_id, review.override_ids) == (
        snapshot.id,
        refresh_id,
        (belief,),
    )
    assert review.mechanical_value == snapshot.value is not None
    assert review.value is not None and review.value != snapshot.value
    [line] = review.bridge
    assert (line["tag"], line["override_id"], line["new"]) == ("growth.belief", belief, 0.08)
    assert line["old"] == current_reading(snapshot.result, "growth.belief")
    assert line["delta"] == pytest.approx(review.value - snapshot.value, abs=1e-9)
    assert others == [[], [], []]  # no override, no review
    [row] = log
    assert (row.symbol, row.refresh_id, row.snapshot_id, row.review_id) == (
        "ACME",
        refresh_id,
        snapshot.id,
        review.id,
    )
    assert (row.mechanical_phase, row.mechanical_value) == ("Mature Growth", snapshot.value)
    assert (row.reviewed_phase, row.reviewed_value) == ("Mature Growth", review.value)
    assert (row.price, row.designation) == (snapshot.price, snapshot.designation)
    assert (row.secondary_value, row.stance) == (None, None)  # none written yet


def test_a_price_refresh_reprices_the_review(env_valued: Env) -> None:
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        before = latest_review(conn, "ACME")
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    refresh_id = env.refresh().run("price")
    snapshot = env.snapshot("ACME")
    assert (snapshot.refresh_id, snapshot.price) == (refresh_id, 20.0)
    with closing(env.connect()) as conn:
        after = latest_review(conn, "ACME")
        log = review_log(conn, "ACME")
    assert before is not None and after is not None and after.id > before.id
    assert (after.snapshot_id, after.refresh_id) == (snapshot.id, refresh_id)
    unchanged = ("value", "buy_level", "fair_low", "fair_high", "trim_level", "mechanical_value")
    assert [getattr(after, f) for f in unchanged] == [getattr(before, f) for f in unchanged]
    assert (after.bridge, after.override_ids) == (before.bridge, before.override_ids)
    assert after.value is not None and after.price_to_value == pytest.approx(20.0 / after.value)
    assert after.price_to_value != before.price_to_value
    assert after.result.price == 20.0 and after.result.valid_until == before.result.valid_until
    assert [(row.refresh_id, row.review_id, row.price) for row in log] == [
        (refresh_id, after.id, 20.0),
        (before.refresh_id, before.id, before.result.price),
    ]


def test_a_period_tied_override_drops_when_its_line_vanishes(env_valued: Env) -> None:
    """AXLE's override corrected a cash figure of $100; the revalue's result reads no cash line (a
    Mature Growth row cites none, as a sheet served without the line does on a route that reads
    one), so the engine's reading, none, is not the value the override corrected."""
    env = env_valued
    cash = _override(env, "AXLE", "balance.cash", 120.0, "period-tied", 100.0)
    refresh_id = env.refresh().run("revalue")
    snapshot = env.snapshot("AXLE")
    with closing(env.connect()) as conn:
        dropped = override_row(conn, cash)
        reviews = reviews_for(conn, "AXLE")
        log = review_log(conn, "AXLE")
        [entry] = entries(conn, "AXLE")
    assert snapshot.refresh_id == refresh_id
    assert dropped is not None
    assert (dropped.state, dropped.drop_reason, dropped.dropped_at) == (
        "dropped",
        CHANGED,
        env.clock(),
    )
    assert (reviews, log) == ([], [])  # no applied override is left
    assert (entry.principal, entry.actor, entry.kind, entry.symbol) == (
        "system",
        None,
        "override-drop",
        "AXLE",
    )
    assert (entry.ref_table, entry.ref_id, entry.snapshot_id) == ("overrides", cash, snapshot.id)
    assert entry.summary == f"balance.cash dropped: {CHANGED}"


def test_a_period_tied_override_drops_when_the_data_date_moves(env_valued: Env) -> None:
    """The override corrected AXLE's reading, none, so a revalue on the same statements keeps it;
    a full refresh past the reuse window fetches the statements again and moves the data date."""
    env = env_valued
    cash = _override(env, "AXLE", "balance.cash", 120.0, "period-tied", None)
    made_on = env.snapshot("AXLE")
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        kept = override_row(conn, cash)
        review = latest_review(conn, "AXLE")
    assert kept is not None and kept.state == "applied"
    assert review is not None and review.override_ids == (cash,)
    assert env.snapshot("AXLE").data_date == made_on.data_date

    env.clock.now += timedelta(days=2)
    refresh_id = env.refresh().run("full")
    snapshot = env.snapshot("AXLE")
    assert snapshot.refresh_id == refresh_id and snapshot.data_date > made_on.data_date
    with closing(env.connect()) as conn:
        dropped = override_row(conn, cash)
        current = latest_review(conn, "AXLE")
        [entry, *_] = entries(conn, "AXLE")
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", MOVED)
    assert current is None
    assert (entry.principal, entry.kind, entry.ref_id, entry.snapshot_id) == (
        "system",
        "override-drop",
        cash,
        snapshot.id,
    )


def test_a_period_tied_override_follows_its_line(conn: sqlite3.Connection, policy: Policy) -> None:
    """HGCO's revenue-growth result cites its cash line: an override that corrected the figure
    holds while the next snapshot reads it, and drops when the line is gone."""
    today, deciles = date(2026, 10, 31), universe_deciles()
    at = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
    inputs = high_growth_inputs()
    first = value_company(inputs, deciles, policy, today)
    figure = current_reading(first, "balance.cash")
    assert isinstance(figure, float)
    refresh_id = create_refresh(
        conn, "revalue", None, policy.version, METHOD_VERSION, at, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, first, refresh_id, clock=lambda: at)
    cash = insert_override(
        conn,
        "HGCO",
        "balance.cash",
        figure,
        figure + 1e9,
        "USD",
        "a vendor error",
        EVIDENCE,
        "period-tied",
        "FY2025",
        figure,
        made_on,
        AGENT,
        at,
        "applied",
        "",
    )

    def follow(inputs: CompanyInputs) -> int | None:
        result = value_company(inputs, deciles, policy, today)
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: at)
        return follow_snapshot(
            conn, inputs, result, snapshot_id, deciles, policy, today, refresh_id, lambda: at
        )

    review_id = follow(inputs)
    found = latest_review(conn, "HGCO")
    assert found is not None and (found.id, found.override_ids) == (review_id, (cash,))
    assert found.value is not None and found.mechanical_value is not None
    assert found.bridge[0]["delta"] == pytest.approx(found.value - found.mechanical_value)
    assert follow(replace(inputs, cash=None)) is None
    dropped = override_row(conn, cash)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)
    assert [(e.principal, e.kind) for e in entries(conn, "HGCO")] == [
        (SYSTEM.principal, "override-drop")
    ]
