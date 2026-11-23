"""The work inbox: its items' states and the expiry rule (spec 2026-11-06 Tier 2, section 8), on a
database where AAPL and MSFT are valued into 2027 and both are on the list Core."""

import sqlite3
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from support.engine_companies import mature_growth_inputs, universe_deciles

from fairband.engine.review import Review
from fairband.engine.route import refusal_result, value_company
from fairband.engine.secondary import Part, secondary_value
from fairband.policy import load_policy
from fairband.store.inbox import (
    ItemOpen,
    WorkItem,
    WrongState,
    claim_item,
    complete_item,
    decline_item,
    drop_item,
    oldest_pending,
    open_item,
    post_expiry_items,
    post_item,
    work_item,
    work_items,
)
from fairband.store.ledger import OWNER, LedgerRow, Writer, entries
from fairband.store.reviews import held_row, insert_review, set_held_state
from fairband.store.secondary import insert_secondary
from fairband.store.snapshots import insert_snapshot
from fairband.store.watchlists import add_symbol, create_watchlist, remove_symbol

NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
LATER = NOW + timedelta(hours=1)
TODAY = date(2026, 11, 1)
VALID = date(2027, 1, 1)
EXPIRED = date(2026, 10, 1)
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")


@pytest.fixture
def core(conn: sqlite3.Connection, new_refresh: Callable[[], int]) -> int:
    """The list Core, holding AAPL (snapshot 1) and MSFT (snapshot 2), both valid into 2027."""
    refresh_id = new_refresh()
    for symbol in ("AAPL", "MSFT"):
        _value(conn, refresh_id, symbol, VALID)
    core = create_watchlist(conn, "Core", NOW)
    add_symbol(conn, core, "AAPL", NOW)
    add_symbol(conn, core, "MSFT", NOW)
    return core


def _value(conn: sqlite3.Connection, refresh_id: int, symbol: str, valid_until: date) -> int:
    """A newer snapshot of ``symbol``, valid until ``valid_until``; its id."""
    result = refusal_result(symbol, "a test row", load_policy(), date(2026, 9, 1))
    return insert_snapshot(
        conn, replace(result, valid_until=valid_until), refresh_id, clock=lambda: NOW
    )


def _expire(conn: sqlite3.Connection, symbol: str, valid_until: date = EXPIRED) -> int:
    """A newer snapshot of ``symbol`` whose window closed on ``valid_until``; its id."""
    refresh_id = conn.execute("SELECT MAX(id) FROM refreshes").fetchone()[0]
    return _value(conn, refresh_id, symbol, valid_until)


def test_post_claim_complete(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "AAPL", "full report", "why", 1, "owner", OWNER, NOW)
    assert not conn.in_transaction
    assert work_item(conn, item_id) == WorkItem(
        id=item_id,
        symbol="AAPL",
        mode="full report",
        note="why",
        snapshot_id=1,
        origin="owner",
        posted_by="owner",
        posted_actor=None,
        posted_client=None,
        posted_at=NOW,
        state="pending",
        claimed_by=None,
        claimed_at=None,
        report_id=None,
        reason=None,
        finished_at=None,
        expiry_valid_until=None,
    )
    claimed = claim_item(conn, item_id, "claude-opus-5-5", NOW)
    assert (claimed.state, claimed.claimed_by, claimed.claimed_at) == (
        "claimed",
        "claude-opus-5-5",
        NOW,
    )
    done = complete_item(conn, item_id, 7, LATER)
    assert (done.state, done.report_id, done.finished_at) == ("done", 7, LATER)
    assert done.claimed_by == "claude-opus-5-5"
    with pytest.raises(ValueError, match="^work item 1 is done$"):
        claim_item(conn, item_id, "gpt-5", NOW)
    with pytest.raises(WrongState, match="^work item 1 is done$"):
        complete_item(conn, item_id, 8, NOW)
    assert work_item(conn, item_id) == done


def test_an_agent_post_carries_its_actor_and_client(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "aapl", "valuation review", "", None, "agent", AGENT, NOW)
    item = work_item(conn, item_id)
    assert (item.symbol, item.note, item.snapshot_id, item.origin) == ("AAPL", "", None, "agent")
    assert (item.posted_by, item.posted_actor, item.posted_client) == (
        "agent",
        "claude-opus-5-5",
        "claude-code/2.1",
    )


def test_a_claim_can_be_taken_over_by_name(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    claim_item(conn, item_id, "claude-opus-5-5", NOW)
    taken = claim_item(conn, item_id, "gpt-5", LATER)
    assert (taken.state, taken.claimed_by, taken.claimed_at) == ("claimed", "gpt-5", LATER)


def test_oldest_pending_and_open_item(conn: sqlite3.Connection, core: int) -> None:
    assert oldest_pending(conn) is None and open_item(conn, "AAPL") is None
    first = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    second = post_item(conn, "MSFT", "valuation review", "", 2, "owner", OWNER, LATER)
    assert oldest_pending(conn) == work_item(conn, first)
    claim_item(conn, first, "claude-opus-5-5", LATER)
    assert oldest_pending(conn) == work_item(conn, second)
    assert open_item(conn, "AAPL") == work_item(conn, first)  # claimed is open
    complete_item(conn, first, 7, LATER)
    assert open_item(conn, "AAPL") is None
    assert [i.id for i in work_items(conn)] == [second, first]  # newest first
    assert [i.id for i in work_items(conn, "done")] == [first]
    assert [i.id for i in work_items(conn, "pending")] == [second]


def test_a_symbol_has_one_open_item(conn: sqlite3.Connection, core: int) -> None:
    first = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    with pytest.raises(ItemOpen, match="^an item for AAPL is open$"):
        post_item(conn, "AAPL", "valuation review", "", 1, "agent", AGENT, NOW)
    assert issubclass(ItemOpen, ValueError) and issubclass(WrongState, ValueError)
    assert [i.id for i in work_items(conn)] == [first]
    decline_item(conn, first, "covered last week", NOW)
    second = post_item(conn, "AAPL", "valuation review", "", 1, "agent", AGENT, NOW)
    assert open_item(conn, "AAPL") == work_item(conn, second)


def test_decline_needs_a_reason(conn: sqlite3.Connection, core: int) -> None:
    item_id = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    for reason in ("", "   "):
        with pytest.raises(ValueError, match="^a decline needs a reason$"):
            decline_item(conn, item_id, reason, NOW)
    assert work_item(conn, item_id).state == "pending"
    declined = decline_item(conn, item_id, "no filings since the last report", LATER)
    assert (declined.state, declined.reason, declined.finished_at) == (
        "declined",
        "no filings since the last report",
        LATER,
    )
    with pytest.raises(WrongState, match="^work item 1 is declined$"):
        decline_item(conn, item_id, "again", NOW)
    with pytest.raises(WrongState, match="^work item 1 is declined$"):
        complete_item(conn, item_id, 7, NOW)


def test_a_missing_item_a_bad_mode_and_a_drop_of_an_open_claim(
    conn: sqlite3.Connection, core: int
) -> None:
    with pytest.raises(KeyError):
        claim_item(conn, 99, "claude-opus-5-5", NOW)
    with pytest.raises(KeyError):
        work_item(conn, 99)
    with pytest.raises(ValueError, match="^a mode is valuation review or full report$"):
        post_item(conn, "AAPL", "memo", "", 1, "owner", OWNER, NOW)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="^'bad symbol' is not a symbol$"):
        post_item(conn, "bad symbol", "full report", "", None, "owner", OWNER, NOW)
    item_id = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    claim_item(conn, item_id, "claude-opus-5-5", NOW)
    with pytest.raises(WrongState, match="^work item 1 is claimed$"):
        drop_item(conn, item_id, NOW)


def test_an_expired_watchlist_company_posts_one_valuation_review(
    conn: sqlite3.Connection, core: int
) -> None:
    snapshot_id = _expire(conn, "AAPL")
    _expire(conn, "IBM")  # expired, but on no list
    assert post_expiry_items(conn, EXPIRED, NOW) == ([], [])  # its last valid day
    posted, dropped = post_expiry_items(conn, TODAY, NOW)
    assert not conn.in_transaction
    assert dropped == []
    [item] = [work_item(conn, item_id) for item_id in posted]
    assert item == WorkItem(
        id=item.id,
        symbol="AAPL",
        mode="valuation review",
        note="expired 2026-10-01",
        snapshot_id=snapshot_id,
        origin="expiry",
        posted_by="system",
        posted_actor=None,
        posted_client=None,
        posted_at=NOW,
        state="pending",
        claimed_by=None,
        claimed_at=None,
        report_id=None,
        reason=None,
        finished_at=None,
        expiry_valid_until=EXPIRED,
    )
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])  # once per valid_until


def test_an_expired_company_on_two_lists_posts_one_item(
    conn: sqlite3.Connection, core: int
) -> None:
    banks = create_watchlist(conn, "Banks", NOW)
    add_symbol(conn, banks, "AAPL", NOW)
    _expire(conn, "AAPL")
    [item_id], [] = post_expiry_items(conn, TODAY, NOW)
    remove_symbol(conn, core, "AAPL")
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])
    assert work_item(conn, item_id).state == "pending"  # still on Banks
    remove_symbol(conn, banks, "AAPL")
    assert post_expiry_items(conn, TODAY, LATER) == ([], [item_id])
    dropped = work_item(conn, item_id)
    assert (dropped.state, dropped.finished_at) == ("dropped", LATER)
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])


def test_only_a_pending_expiry_item_drops(conn: sqlite3.Connection, core: int) -> None:
    """An owner's item and a claimed expiry item stay when the company leaves every list."""
    _expire(conn, "AAPL")
    [expiry_id], [] = post_expiry_items(conn, TODAY, NOW)
    claim_item(conn, expiry_id, "claude-opus-5-5", NOW)
    owners = post_item(conn, "MSFT", "full report", "", 2, "owner", OWNER, NOW)
    remove_symbol(conn, core, "AAPL")
    remove_symbol(conn, core, "MSFT")
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])
    assert work_item(conn, expiry_id).state == "claimed"
    assert work_item(conn, owners).state == "pending"


def test_an_open_item_blocks_the_expiry_post(conn: sqlite3.Connection, core: int) -> None:
    owners = post_item(conn, "AAPL", "full report", "", 1, "owner", OWNER, NOW)
    _expire(conn, "AAPL")
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])  # pending
    claim_item(conn, owners, "claude-opus-5-5", NOW)
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])  # claimed
    complete_item(conn, owners, 7, NOW)
    [expiry_id], [] = post_expiry_items(conn, TODAY, LATER)
    assert work_item(conn, expiry_id).origin == "expiry"


def test_a_new_valid_until_posts_again_after_the_first_is_done(
    conn: sqlite3.Connection, core: int
) -> None:
    _expire(conn, "AAPL")
    [first], [] = post_expiry_items(conn, TODAY, NOW)
    claim_item(conn, first, "claude-opus-5-5", NOW)
    complete_item(conn, first, 7, NOW)
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])  # the same valid_until
    _expire(conn, "AAPL", date(2026, 10, 15))
    [second], [] = post_expiry_items(conn, TODAY, LATER)
    assert work_item(conn, second).expiry_valid_until == date(2026, 10, 15)
    assert [i.id for i in work_items(conn, "pending")] == [second]


def test_a_declined_expiry_item_holds_for_its_window(conn: sqlite3.Connection, core: int) -> None:
    """Declining an expiry item means something: no new item on any later read while the
    company's latest snapshot carries the window it was posted for, a newer snapshot in that same
    window (a price refresh's) included; a new window that has also ended posts again."""
    _expire(conn, "AAPL")
    [first], [] = post_expiry_items(conn, TODAY, NOW)
    decline_item(conn, first, "nothing new to read", NOW)
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])  # read again the same day
    assert post_expiry_items(conn, TODAY + timedelta(days=30), LATER) == ([], [])  # a month on
    _expire(conn, "AAPL")  # a newer snapshot in the same window
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])
    assert open_item(conn, "AAPL") is None
    _expire(conn, "AAPL", date(2026, 10, 15))  # a new window, ended too
    [second], [] = post_expiry_items(conn, TODAY, LATER)
    assert (work_item(conn, second).state, work_item(conn, second).expiry_valid_until) == (
        "pending",
        date(2026, 10, 15),
    )
    assert work_item(conn, first).state == "declined"


CHANGED = "the input the override corrected changed"


def _held(conn: sqlite3.Connection, symbol: str, snapshot_id: int, valid_until: date) -> int:
    """A made review of ``symbol`` on ``snapshot_id``, valued, its window ending on
    ``valid_until``, which the company holds; the review's id."""
    policy = load_policy()
    inputs = replace(mature_growth_inputs(), symbol=symbol)
    result = value_company(inputs, universe_deciles(), policy, date(2026, 10, 31))
    result = replace(result, valid_until=valid_until)
    review = Review(result, result.value, (), (36,))
    return insert_review(conn, review, symbol, snapshot_id, None, clock=lambda: NOW)


def _drops(conn: sqlite3.Connection, symbol: str, **facts: object) -> None:
    held = held_row(conn, symbol)
    assert held is not None
    set_held_state(conn, replace(held, **facts))  # type: ignore[arg-type]


DROPPED = {"id": 36, "tag": "earnings.nri_gap", "reason": CHANGED, "at": NOW.isoformat()}


def test_a_watched_company_expired_early_gets_one_item_for_its_held_review(
    conn: sqlite3.Connection, core: int
) -> None:
    """Spec 2026-11-23 held reviewed value, 5.10 and 7: a watched company whose held review
    expired early gets one valuation review, whose note gives the first reason. The item stands
    for that held review whatever becomes of it: declined, it is not posted again, and a second
    reason on the same review posts nothing. A review made again, when it expires, posts one."""
    snapshot_id = _expire(conn, "AAPL", VALID)  # the latest snapshot's window is open
    made = _held(conn, "AAPL", snapshot_id, VALID)
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])  # current: nothing to post
    _drops(conn, "AAPL", dropped=(DROPPED,), early_at=TODAY)
    [item_id], [] = post_expiry_items(conn, TODAY, NOW)
    item = work_item(conn, item_id)
    assert (item.symbol, item.mode, item.origin, item.snapshot_id) == (
        "AAPL",
        "valuation review",
        "expiry",
        snapshot_id,
    )
    assert item.note == "expired early: override 36 no longer applies"
    assert (item.expiry_review_id, item.expiry_secondary_id, item.expiry_valid_until) == (
        made,
        None,
        None,
    )
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])  # open
    decline_item(conn, item_id, "not now", LATER)
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])  # declined: it holds
    _drops(conn, "AAPL", dropped=(DROPPED,), newer_period=date(2026, 12, 26), early_at=TODAY)
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])  # a second reason, the same review
    again = _held(conn, "AAPL", snapshot_id, VALID)
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])  # made again: current
    _drops(conn, "AAPL", newer_period=date(2026, 12, 26), early_at=TODAY)
    [second], [] = post_expiry_items(conn, TODAY, LATER)
    newer = work_item(conn, second)
    assert (newer.note, newer.expiry_review_id) == (
        "expired early: a newer period is on file",
        again,
    )


def test_the_held_review_s_window_decides_in_place_of_the_snapshot_s(
    conn: sqlite3.Connection, core: int
) -> None:
    """Spec 5.10: for a watched company that holds a review, the rule reads that review's state
    in place of the latest snapshot's window. A held review whose window is open posts nothing
    though the latest snapshot's ended; one whose window ended posts "expired <date>" though the
    latest snapshot's is open; and a reading outside the fair band is an early expiry."""
    open_window = _expire(conn, "AAPL", VALID)
    _held(conn, "AAPL", open_window, VALID)
    _expire(conn, "AAPL")  # the latest snapshot's window ended; the held review's did not
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])
    latest = _expire(conn, "MSFT", VALID)
    made = _held(conn, "MSFT", latest, EXPIRED)
    [item_id], [] = post_expiry_items(conn, TODAY, NOW)
    item = work_item(conn, item_id)
    assert (item.symbol, item.note, item.expiry_review_id) == ("MSFT", "expired 2026-10-01", made)
    held = held_row(conn, "AAPL")
    assert held is not None
    _drops(conn, "AAPL", reading_value=1.0, early_at=TODAY)
    [early], [] = post_expiry_items(conn, TODAY, LATER)
    assert work_item(conn, early).note == "expired early: computed again, the review gives $1.00"


def test_an_unwatched_company_expired_early_gets_no_item(
    conn: sqlite3.Connection, core: int
) -> None:
    """The founder's rule (spec 2, anti-goals): no item for a company on no watchlist. A pending
    item of a held review drops when its company leaves every list, as an expiry item does."""
    snapshot_id = _expire(conn, "IBM", VALID)
    _held(conn, "IBM", snapshot_id, VALID)
    _drops(conn, "IBM", dropped=(DROPPED,), early_at=TODAY)
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])
    watched = _expire(conn, "AAPL", VALID)
    _held(conn, "AAPL", watched, VALID)
    _drops(conn, "AAPL", dropped=(DROPPED,), early_at=TODAY)
    [item_id], [] = post_expiry_items(conn, TODAY, NOW)
    remove_symbol(conn, core, "AAPL")
    assert post_expiry_items(conn, TODAY, LATER) == ([], [item_id])


def test_a_watched_company_s_held_secondary_valuation_posts_by_its_state(
    conn: sqlite3.Connection, core: int
) -> None:
    """Spec 5.9 and 5.10: a watched company with no held review and a held secondary valuation
    is read by that record's state: nothing while its window is open, one item, keyed to the
    secondary valuation, when a newer period is on file."""
    policy = load_policy()
    made_on = _expire(conn, "MSFT", VALID)  # a refused row, as the fixture's rows are
    parts = (Part("the business", (100.0,) * 5, 0.03, None),)
    valuation = secondary_value(
        parts=parts, debt=200.0, cash=100.0, shares=100.0, price=15.0, moat="Wide", policy=policy
    )
    evidence = [{"kind": "filing", "ref": "10-K 2025", "note": None, "figure": "debt"}]
    secondary_id = insert_secondary(
        conn,
        "MSFT",
        made_on,
        parts,
        valuation,
        *("the segments diverge", evidence, "agent", "statements", policy.version, "{}", 1),
        AGENT,
        NOW,
    )
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])
    conn.execute(
        "UPDATE snapshots SET result = json_set(result, '$.intermediates.trailing_end',"
        " '2026-09-30') WHERE id = ?",
        (made_on,),
    )
    conn.commit()
    result = refusal_result("MSFT", "a test row", policy, date(2026, 9, 1))
    later = replace(
        result,
        valid_until=VALID,
        intermediates=result.intermediates | {"trailing_end": "2026-12-31"},
    )
    refresh_id = conn.execute("SELECT MAX(id) FROM refreshes").fetchone()[0]
    latest = insert_snapshot(conn, later, refresh_id, clock=lambda: NOW)
    [item_id], [] = post_expiry_items(conn, TODAY, NOW)
    item = work_item(conn, item_id)
    assert (item.symbol, item.note, item.snapshot_id) == (
        "MSFT",
        "expired early: a newer period is on file",
        latest,
    )
    assert (item.expiry_secondary_id, item.expiry_review_id) == (secondary_id, None)
    decline_item(conn, item_id, "not now", LATER)
    assert post_expiry_items(conn, TODAY, LATER) == ([], [])  # one item for one held record


def test_the_expiry_rule_writes_its_own_ledger_rows(conn: sqlite3.Connection, core: int) -> None:
    """B-103 (spec 2026-11-15 12.1, clause 2): the expiry rule writes the system's ledger row of
    each item it posts and each it drops, in its own transaction, each resting on the company's
    latest snapshot and naming the item; a run that posts and drops nothing writes none."""
    snapshot_id = _expire(conn, "AAPL")
    [item_id], [] = post_expiry_items(conn, TODAY, NOW)
    assert post_expiry_items(conn, TODAY, NOW) == ([], [])
    remove_symbol(conn, core, "AAPL")
    assert post_expiry_items(conn, TODAY, LATER) == ([], [item_id])
    assert not conn.in_transaction

    def row(n: int, at: datetime, kind: str, summary: str) -> LedgerRow:
        refs = ("work_items", item_id, snapshot_id, item_id)
        return LedgerRow(n, at, "system", None, None, kind, "AAPL", *refs, summary)

    assert entries(conn) == [
        row(2, LATER, "drop", "dropped: AAPL is on no watchlist"),
        row(1, NOW, "work-item", "valuation review posted: expired 2026-10-01"),
    ]
