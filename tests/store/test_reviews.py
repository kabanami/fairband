"""The reviews and their log (spec 2026-11-06 Tier 2, 10.4 to 10.6): a review stored as a snapshot
is, its bridge and override ids beside it; the current review while an override is applied; one
log row for each review written."""

import sqlite3
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, timedelta

from support.engine_companies import mature_growth_inputs, universe_deciles

from fairband.engine.overrides import Override
from fairband.engine.review import REVIEW_METHOD, Review, review_company
from fairband.engine.route import value_company
from fairband.policy import load_policy
from fairband.store.db import transaction
from fairband.store.ledger import Writer
from fairband.store.overrides import drop_override, insert_override
from fairband.store.reviews import (
    HeldRow,
    LogRow,
    clear_held,
    held_row,
    held_rows,
    hold_review,
    insert_review,
    latest_review,
    latest_reviews,
    latest_secondary_value,
    latest_stance,
    log_review,
    review_log,
    reviews_for,
    set_held_state,
)

TODAY = date(2026, 10, 31)
NOW = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")


def _applied(conn: sqlite3.Connection, symbol: str) -> int:
    """An applied growth.belief override of ``symbol`` at 8%."""
    return insert_override(
        conn,
        symbol,
        "growth.belief",
        0.1,
        0.08,
        "ratio",
        "guidance raised",
        [{"kind": "transcript", "ref": "Q3 call", "note": ""}],
        "lasting",
        None,
        None,
        1,
        AGENT,
        NOW,
        "applied",
        "",
    )


def _review(symbol: str, override_id: int) -> Review:
    """The Mature Growth golden, renamed, under a belief of 8%."""
    policy, deciles = load_policy(), universe_deciles()
    inputs = replace(mature_growth_inputs(), symbol=symbol)
    mechanical = value_company(inputs, deciles, policy, TODAY)
    belief = Override(override_id, "growth.belief", 0.08, "agent", "a", NOW, "r")
    return review_company(inputs, deciles, policy, TODAY, [belief], mechanical)


def test_a_review_reads_back_exactly(conn: sqlite3.Connection) -> None:
    override_id = _applied(conn, "AAPL")
    review = _review("AAPL", override_id)
    review_id = insert_review(conn, review, "AAPL", 4, 2, clock=lambda: NOW)
    assert not conn.in_transaction
    found = latest_review(conn, "AAPL")
    assert found is not None and found.id == review_id
    result, levels = review.result, review.result.levels
    assert levels is not None and result.value is not None
    assert (found.symbol, found.snapshot_id, found.refresh_id, found.created_at) == (
        "AAPL",
        4,
        2,
        NOW,
    )
    assert (found.value, found.buy_level, found.fair_low, found.fair_high, found.trim_level) == (
        result.value,
        levels.buy,
        levels.fair_low,
        levels.fair_high,
        levels.trim,
    )
    assert (found.price_to_value, found.designation, found.refusal) == (
        result.price_to_value,
        result.designation,
        None,
    )
    assert found.mechanical_value == review.mechanical_value != result.value
    assert found.bridge == tuple(asdict(line) for line in review.bridge)
    assert found.bridge[0]["tag"] == "growth.belief" and found.bridge[0]["new"] == 0.08
    assert found.override_ids == (override_id,)
    assert (found.policy_version, found.method_version, found.settings_hash) == (
        result.policy_version,
        result.method_version,
        result.settings_hash,
    )
    assert (found.review_method, found.deciles_refresh_id) == (REVIEW_METHOD, 1)
    assert found.result == result


def test_the_current_review_is_the_newest_while_an_override_is_applied(
    conn: sqlite3.Connection,
) -> None:
    assert latest_review(conn, "AAPL") is None
    override_id = _applied(conn, "AAPL")
    review = _review("AAPL", override_id)
    first = insert_review(conn, review, "AAPL", 4, None, clock=lambda: NOW)
    second = insert_review(conn, review, "AAPL", 5, 3, clock=lambda: LATER)
    found = latest_review(conn, "AAPL")
    assert found is not None and (found.id, found.snapshot_id) == (second, 5)
    assert [r.id for r in reviews_for(conn, "AAPL")] == [second, first]
    drop_override(conn, override_id, "wrong", LATER)
    assert latest_review(conn, "AAPL") is None  # the drop of the last override clears it
    assert [r.id for r in reviews_for(conn, "AAPL")] == [second, first]  # the history stays


def test_latest_reviews_with_two_companies(conn: sqlite3.Connection) -> None:
    apple, micro, gone = _applied(conn, "AAPL"), _applied(conn, "MSFT"), _applied(conn, "GONE")
    insert_review(conn, _review("AAPL", apple), "AAPL", 1, None, clock=lambda: NOW)
    newest = insert_review(conn, _review("AAPL", apple), "AAPL", 3, 2, clock=lambda: LATER)
    other = insert_review(conn, _review("MSFT", micro), "MSFT", 2, None, clock=lambda: NOW)
    insert_review(conn, _review("GONE", gone), "GONE", 4, None, clock=lambda: NOW)
    drop_override(conn, gone, "wrong", LATER)
    found = latest_reviews(conn)
    assert list(found) == ["AAPL", "MSFT"]
    assert (found["AAPL"].id, found["MSFT"].id) == (newest, other)


def test_a_made_review_is_held_and_a_reading_is_not(conn: sqlite3.Connection) -> None:
    """Spec 2026-11-23 held reviewed value, 5.1: a made review becomes the one the company holds,
    its state empty. A refresh's reading and its copy of the held review name the made review and
    do not take its place; a newer made review does, and starts with an empty state."""
    assert held_row(conn, "AAPL") is None
    override_id = _applied(conn, "AAPL")
    review = _review("AAPL", override_id)
    made = insert_review(conn, review, "AAPL", 4, None, clock=lambda: NOW)
    assert held_row(conn, "AAPL") == HeldRow(
        "AAPL", made, NOW, None, None, (), None, None, None, None
    )
    reading = insert_review(
        conn, review, "AAPL", 5, 3, kind="reading", made_id=made, clock=lambda: LATER
    )
    copy = insert_review(conn, review, "AAPL", 5, 3, kind="held", made_id=made, clock=lambda: LATER)
    held = held_row(conn, "AAPL")
    assert held is not None and (held.review_id, held.made_at) == (made, NOW)
    rows = {r.id: r for r in reviews_for(conn, "AAPL")}
    assert (rows[made].kind, rows[made].made_id, rows[made].held_id) == ("made", None, made)
    assert (rows[reading].kind, rows[reading].made_id, rows[reading].held_id) == (
        "reading",
        made,
        made,
    )
    assert (rows[copy].kind, rows[copy].made_id, rows[copy].held_id) == ("held", made, made)
    set_held_state(conn, replace(held, early_at=date(2026, 11, 14), reading_value=41.5))
    again = insert_review(conn, review, "AAPL", 6, None, clock=lambda: LATER)
    assert held_row(conn, "AAPL") == HeldRow(
        "AAPL", again, LATER, None, None, (), None, None, None, None
    )
    assert not conn.in_transaction


def test_clearing_the_held_review_leaves_no_row(conn: sqlite3.Connection) -> None:
    apple, micro = _applied(conn, "AAPL"), _applied(conn, "MSFT")
    insert_review(conn, _review("AAPL", apple), "AAPL", 1, None, clock=lambda: NOW)
    other = insert_review(conn, _review("MSFT", micro), "MSFT", 2, None, clock=lambda: NOW)
    assert list(held_rows(conn)) == ["AAPL", "MSFT"]
    clear_held(conn, "AAPL")
    clear_held(conn, "NONE")  # a company that holds none: no change
    assert held_row(conn, "AAPL") is None
    assert {s: h.review_id for s, h in held_rows(conn).items()} == {"MSFT": other}
    assert len(reviews_for(conn, "AAPL")) == 1  # the history stays
    hold_review(conn, "AAPL", 1, LATER)  # holding an earlier review again names it
    found = held_row(conn, "AAPL")
    assert found is not None and (found.review_id, found.made_at) == (1, LATER)


def test_the_state_reads_back_exactly(conn: sqlite3.Connection) -> None:
    """The facts a refresh stores for a held review (spec 5.3): the day a refresh first read it
    again, the newer period's end, the overrides the system dropped, the newest good reading or
    its refusal, and the day a refresh first found a reason."""
    override_id = _applied(conn, "AAPL")
    made = insert_review(conn, _review("AAPL", override_id), "AAPL", 4, None, clock=lambda: NOW)
    dropped = {
        "id": 36,
        "tag": "earnings.nri_gap",
        "reason": "the input the override corrected changed",
        "at": LATER.isoformat(),
    }
    state = HeldRow(
        symbol="AAPL",
        review_id=made,
        made_at=NOW,
        read_again_at=LATER,
        newer_period=date(2026, 12, 26),
        dropped=(dropped,),
        reading_value=291.62000000000006,
        reading_refusal=None,
        reading_at=LATER,
        early_at=date(2026, 11, 14),
    )
    set_held_state(conn, state)
    assert held_row(conn, "AAPL") == state
    refused = replace(state, reading_value=None, reading_refusal="no positive trailing earnings")
    set_held_state(conn, refused)
    assert held_row(conn, "AAPL") == refused
    assert not conn.in_transaction


def test_review_log_by_symbol(conn: sqlite3.Connection) -> None:
    # at, symbol, refresh, snapshot, review, the mechanical phase and value, the reviewed phase
    # and value, the secondary value, the price, the designation and the stance
    first = (NOW, "AAPL", 2, 4, 1, "Mature Growth", 33.5, "Mature Growth", 41.25, None, 150.0)
    other = (NOW, "MSFT", None, 5, 2, "Start-up", None, "Young Growth", 12.0, 14.5, 9.0)
    refused = (LATER, "AAPL", 3, 6, 3, "Mature Growth", 33.5, None, None, None, 151.0)
    ids = [
        log_review(conn, *first, "above", None),
        log_review(conn, *other, None, "bullish"),
        log_review(conn, *refused, "above", None),
    ]
    assert not conn.in_transaction
    assert review_log(conn, "AAPL") == [
        LogRow(ids[2], *refused, "above", None),
        LogRow(ids[0], *first, "above", None),
    ]
    assert [row.id for row in review_log(conn)] == ids[::-1]
    assert review_log(conn, "NONE") == []
    assert {row.kind for row in review_log(conn)} == {None}  # a row written with no kind
    read = log_review(conn, *refused, "above", None, kind="reading")
    assert review_log(conn, "AAPL")[0] == LogRow(read, *refused, "above", None, "reading")


def test_the_latest_secondary_value_and_stance(conn: sqlite3.Connection) -> None:
    """Read from rows written straight to the two tables: no store module writes them yet."""
    assert (latest_secondary_value(conn, "AAPL"), latest_stance(conn, "AAPL")) == (None, None)
    with transaction(conn):
        for revision, value, stance in ((1, "40.5", "neutral"), (2, "42.25", "bullish")):
            conn.execute(
                "INSERT INTO secondary_valuations (symbol, snapshot_id, created_at, principal,"
                " parts, firm_value, debt, cash, shares, equity, value_per_share, reason,"
                " evidence, debt_source, cash_source, policy_version, settings_hash,"
                " secondary_method) VALUES ('AAPL', 1, ?, 'agent', '[]', '1', '0', '0', '1',"
                " '1', ?, 'r', '[]', 's', 's', 'v8', 'h', 'm')",
                (NOW.isoformat(), value),
            )
            conn.execute(
                "INSERT INTO reports (symbol, revision, mode, stance, sections, snapshot_id,"
                " principal, created_at) VALUES ('AAPL', ?, 'full report', ?, '[]', 1, 'agent', ?)",
                (revision, stance, NOW.isoformat()),
            )
    assert (latest_secondary_value(conn, "AAPL"), latest_stance(conn, "AAPL")) == (
        42.25,
        "bullish",
    )
    assert (latest_secondary_value(conn, "MSFT"), latest_stance(conn, "MSFT")) == (None, None)
