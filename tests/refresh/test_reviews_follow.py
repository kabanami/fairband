"""A review follows its company's snapshots (spec 2026-11-06 Tier 2, 10.5 and 10.6): every refresh
that writes a snapshot for a company with an applied override writes a review on it, and a log row
for it. A revalue, a scoped or a full refresh recomputes it on the new inputs, after dropping an
override the row's route does not read (spec 2026-11-14 8) and a period-tied override when a newer
period is on file or its input moved (spec 2026-11-13 11a), with each override in dollars a share
or in shares made before a split on the new basis (spec 2026-11-14 7); a price refresh reprices it.

The refresh tests run on the five companies a full refresh of ``fixture_universe`` valued: ACME,
AXLE and KRON (in SEK) Mature Growth, MILD Mature Stable, NEWT refused for its target margin.
"""

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from fixture_universe import serve_universe
from refresh_env import Env
from support.engine_companies import (
    as_live,
    decline_inputs,
    high_growth_inputs,
    mature_growth_inputs,
    mature_stable_inputs,
    on_quarter_sheet,
    quarter,
    universe_deciles,
    with_minority,
)
from support.splits import (
    AFTER,
    BEFORE,
    SPLIT_DAY,
    follow_mgco,
    made_on_mgco,
    mgco_snapshot,
    store_splits,
    under,
)
from vendor_double import FIXTURES

from fairband.engine import METHOD_VERSION
from fairband.engine.levels import levels_for
from fairband.engine.overrides import TAGS, Lifetime, OverrideTag, current_reading
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.types import TaggedInput, ValuationResult
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.refresh import held, reviews
from fairband.refresh.reviews import follow_snapshot
from fairband.store.guidance import insert_guidance
from fairband.store.ledger import SYSTEM, Writer, entries
from fairband.store.overrides import drop_override, insert_override, override_row
from fairband.store.refreshes import create_refresh
from fairband.store.reviews import (
    ReviewRow,
    latest_review,
    review_log,
    review_row,
    reviews_for,
)
from fairband.store.snapshots import insert_snapshot, snapshot_row

AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "transcript", "ref": "Q3 call", "note": ""}]
CHANGED = "the input the override corrected changed"
NEWER = "a newer period is on file than the one the override corrected"
PASSED = "the guided year has passed"
ON_FILE = "the store holds a trailing stock pay above zero"
# The route drop's reason, the route named as the write's route rule names it (spec 2026-11-14 8).
OFF_MATURE_GROWTH = "the Mature Growth route does not read the input"
OFF_MATURE_STABLE = "the Mature Stable route does not read the input"
OFF_DECLINE = "the Decline route does not read the input"
FAILED = "review failed"
HGCO_TODAY = date(2026, 10, 31)  # the day HGCO is valued
HGCO_AT = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)  # the time its snapshots and override are made
Follow = Callable[[CompanyInputs], int | None]


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


def _reading(conn: sqlite3.Connection, symbol: str) -> ReviewRow | None:
    """The company's newest reading: what its review gives on the latest snapshot a refresh
    valued, over the overrides still applied (spec 2026-11-23 held reviewed value, 5.4)."""
    return next((r for r in reviews_for(conn, symbol) if r.kind == "reading"), None)


def _no_reading(conn: sqlite3.Connection, review_id: int | None) -> bool:
    """Whether the follow that answered ``review_id`` dropped the last override: it computed no
    reading, and the review on its snapshot is the held one, carried (spec 2026-11-23 held
    reviewed value, 5.1 and 5.4)."""
    row = None if review_id is None else review_row(conn, review_id)
    if row is None or row.kind != "held":
        return False
    on_it = [r for r in reviews_for(conn, row.symbol) if r.snapshot_id == row.snapshot_id]
    return [r.kind for r in on_it] == ["held"]


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


def test_a_price_refresh_after_a_changed_threshold_stores_the_review_s_levels_in_force(
    env_valued: Env,
) -> None:
    """A threshold is in no settings hash (spec 2026-11-23 thresholds 5.3), so a price refresh
    reprices a review made before a change of one. The review it writes holds the levels of the
    policy in force on its own value, beside the word read on them; its value does not move."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        before = latest_review(conn, "ACME")
    env.policy = replace(env.policy, fair_band=(0.95, 1.05), trim_multiple=1.2)
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    env.refresh().run("price")
    with closing(env.connect()) as conn:
        after = latest_review(conn, "ACME")
    assert before is not None and after is not None and after.id > before.id
    assert after.value is not None and after.value == before.value
    levels = levels_for(after.value, after.result.intermediates["moat"], env.policy)
    assert (after.buy_level, after.fair_low, after.fair_high, after.trim_level) == (
        levels.buy,
        levels.fair_low,
        levels.fair_high,
        levels.trim,
    )
    assert after.result.levels == levels and after.trim_level != before.trim_level
    assert after.designation == after.result.designation


def test_a_price_refresh_at_a_new_rate_moves_the_review_s_bridge_with_it(env_valued: Env) -> None:
    """KRON reports in SEK (spec 2026-11-10 7.2): its review, revalued at USDSEK's 10.52, reprices
    at the pair's new quote, 10.0. The mechanical value is the repriced snapshot's, each bridge
    line's change a share moves by 10.52 ÷ 10.0 (its readings stay, in SEK), so the mechanical
    value plus the changes is still the reviewed value."""
    env = env_valued
    _override(env, "KRON", "growth.belief", 0.08)
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        before = latest_review(conn, "KRON")
    assert before is not None and before.result.intermediates["fx_rate"] == 10.52
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "KRON": 40.0, "MILD": 10.0})
    [pair] = json.loads(_quotes({"USDSEK": 10.0}))
    env.router.symbol_bodies[("quote", "USDSEK")] = json.dumps([pair]).encode()
    env.refresh().run("price")
    snapshot = env.snapshot("KRON")
    with closing(env.connect()) as conn:
        after = latest_review(conn, "KRON")
    assert after is not None and after.snapshot_id == snapshot.id
    assert snapshot.result.intermediates["fx_rate"] == after.result.intermediates["fx_rate"] == 10.0
    assert snapshot.value is not None and after.value is not None
    # the mechanical value of the day the review was made, at the new rate: the repriced
    # snapshot's here, which the same valuation gives
    assert after.mechanical_value == pytest.approx(snapshot.value)
    assert after.mechanical_value != before.mechanical_value
    [was], [line] = before.bridge, after.bridge
    assert (line["old"], line["new"]) == (was["old"], was["new"])  # the readings stay
    assert line["delta"] == pytest.approx(was["delta"] * 10.52 / 10.0)
    assert after.mechanical_value + line["delta"] == pytest.approx(after.value)
    assert after.value == pytest.approx(after.result.intermediates["value_in_currency"] / 10.0)


def test_a_failed_review_at_a_new_rate_keeps_the_mechanical_value_of_its_day(
    env_valued: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KRON holds no review when its review fails at the revalue: the refusal, with no
    intermediates and so no rate, is the review KRON then holds, over the snapshot valued at
    USDSEK's 10.52. The price refresh reprices the snapshot at the pair's 10.0, so its USD value
    moves; the held refusal's copy takes the new price alone and keeps the mechanical value of
    the day it was made (spec 2026-11-23 held reviewed value, 5.2)."""
    env = env_valued
    _override(env, "KRON", "growth.belief", 0.08)

    def falls_over(*args: object) -> None:
        raise RuntimeError("the engine fell over")

    monkeypatch.setattr(reviews, "review_company", falls_over)
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        before = latest_review(conn, "KRON")
    assert before is not None and before.refusal is not None and before.refusal.startswith(FAILED)
    assert "fx_rate" not in before.result.intermediates
    assert before.mechanical_value == env.snapshot("KRON").value
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "KRON": 40.0, "MILD": 10.0})
    [pair] = json.loads(_quotes({"USDSEK": 10.0}))
    env.router.symbol_bodies[("quote", "USDSEK")] = json.dumps([pair]).encode()
    env.refresh().run("price")
    snapshot = env.snapshot("KRON")
    with closing(env.connect()) as conn:
        after = latest_review(conn, "KRON")
    assert after is not None and after.snapshot_id == snapshot.id
    assert snapshot.result.intermediates["fx_rate"] == 10.0
    assert after.refusal == before.refusal and after.bridge == ()
    # a refusing review holds no value: its copy takes the new price alone, and keeps the
    # mechanical value of the day it was made (spec 2026-11-23 held reviewed value, 5.2)
    assert (after.kind, after.mechanical_value) == ("held", before.mechanical_value)
    assert after.result.price == 40.0 and snapshot.value != before.mechanical_value


def test_a_revalue_drops_an_override_the_row_s_route_does_not_read(env_valued: Env) -> None:
    """Spec 2026-11-14 8: AXLE's override corrected a cash figure of $100 on its Mature Growth row,
    whose route reads no cash line. The revalue drops it by the system with the route's reason,
    which runs before the reading test: the engine's reading there, none, is not the value it
    corrected either."""
    env = env_valued
    cash = _override(env, "AXLE", "balance.cash", 120.0, "period-tied", 100.0)
    refresh_id = env.refresh().run("revalue")
    snapshot = env.snapshot("AXLE")
    assert current_reading(snapshot.result, "balance.cash") is None
    with closing(env.connect()) as conn:
        dropped = override_row(conn, cash)
        reviews = reviews_for(conn, "AXLE")
        log = review_log(conn, "AXLE")
        [entry] = entries(conn, "AXLE")
    assert snapshot.refresh_id == refresh_id
    assert dropped is not None
    assert (dropped.state, dropped.drop_reason, dropped.dropped_at) == (
        "dropped",
        OFF_MATURE_GROWTH,
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
    assert entry.summary == f"balance.cash dropped: {OFF_MATURE_GROWTH}"


def test_a_period_tied_override_stays_when_the_same_statements_are_fetched_again(
    env_valued: Env,
) -> None:
    """A full refresh past the reuse window fetches AXLE's statements again and moves its data
    date; the statements hold the same periods and the same diluted count, so the correction of
    the count stays applied, and the review sits on the refetched snapshot."""
    env = env_valued
    made_on = env.snapshot("AXLE")
    count = current_reading(made_on.result, "shares.diluted")
    assert isinstance(count, float)
    shares = _override(env, "AXLE", "shares.diluted", count * 1.1, "period-tied", count)
    env.clock.now += timedelta(days=2)
    env.refresh().run("full")
    refetched = env.snapshot("AXLE")
    assert refetched.data_date > made_on.data_date and refetched.id != made_on.id
    with closing(env.connect()) as conn:
        kept = override_row(conn, shares)
        review = latest_review(conn, "AXLE")
    assert kept is not None and kept.state == "applied"
    assert review is not None and review.override_ids == (shares,)
    assert review.snapshot_id == refetched.id


def _hgco_with_a_cash_correction(
    conn: sqlite3.Connection,
    policy: Policy,
    strip: str | None = None,
    keep_inputs: tuple[str, ...] | None = None,
) -> tuple[int, Follow, CompanyInputs]:
    """``_hgco_with_a_correction`` of the cash line, on HGCO as assembly dates it."""
    inputs = as_live(high_growth_inputs())
    return _hgco_with_a_correction(conn, policy, "balance.cash", inputs, strip, keep_inputs)


def _hgco_with_a_correction(
    conn: sqlite3.Connection,
    policy: Policy,
    tag: OverrideTag,
    inputs: CompanyInputs,
    strip: str | None = None,
    keep_inputs: tuple[str, ...] | None = None,
) -> tuple[int, Follow, CompanyInputs]:
    """HGCO valued on ``inputs``, its snapshot stored (without the intermediate ``strip``, and with
    its inputs cut to ``keep_inputs``, when given, as a snapshot from before 1.3 is stored) and a
    period-tied override of its balance line ``tag`` made on it, $1,000 m above the figure it
    corrected: the override's id, ``follow``, which values the inputs it is given, stores the
    snapshot and follows it, and the inputs."""
    deciles = universe_deciles()
    first = value_company(inputs, deciles, policy, HGCO_TODAY)
    figure = current_reading(first, tag)
    assert isinstance(figure, float)
    stored = first
    if strip is not None:
        stored = replace(
            stored, intermediates={k: v for k, v in first.intermediates.items() if k != strip}
        )
    if keep_inputs is not None:
        stored = replace(stored, inputs=tuple(i for i in first.inputs if i.name in keep_inputs))
    refresh_id = create_refresh(
        conn, "revalue", None, policy.version, METHOD_VERSION, HGCO_AT, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, stored, refresh_id, clock=lambda: HGCO_AT)
    correction = insert_override(
        conn,
        "HGCO",
        tag,
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
        HGCO_AT,
        "applied",
        "",
    )

    def follow(inputs: CompanyInputs) -> int | None:
        result = value_company(inputs, deciles, policy, HGCO_TODAY)
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: HGCO_AT)
        return follow_snapshot(
            conn,
            inputs,
            result,
            snapshot_id,
            deciles,
            policy,
            HGCO_TODAY,
            refresh_id,
            lambda: HGCO_AT,
        )

    return correction, follow, inputs


def _made_on(conn: sqlite3.Connection, override_id: int) -> ValuationResult:
    """The result of the snapshot override ``override_id`` was made on, as stored."""
    override = override_row(conn, override_id)
    assert override is not None
    found = snapshot_row(conn, override.snapshot_id)
    assert found is not None
    return found.result


def _a_quarter_on(inputs: CompanyInputs) -> CompanyInputs:
    """HGCO, or MGCO, a quarter on: the trailing period end moves from 30 Sep to 31 Dec 2026, and
    the consensus quarters with it (Q4 2026 reported, Q4 2027 added at HGCO's figures), so the
    route still values the company on the same base year, and on HGCO reads the same cash line."""
    assert inputs.trailing is not None
    later = inputs.trailing.period_end + timedelta(days=92)
    assert later == date(2026, 12, 31)
    ahead = quarter(date(2027, 12, 31), 2027, "Q4", -0.40, 3_600e6)
    return replace(
        inputs,
        trailing=replace(inputs.trailing, period_end=later),
        quarter_estimates=(*inputs.quarter_estimates[1:], ahead),
    )


def test_a_period_tied_override_follows_its_line(conn: sqlite3.Connection, policy: Policy) -> None:
    """HGCO's revenue-growth result cites its cash line: an override that corrected the figure
    holds while the next snapshot reads it, and drops when the line is gone."""
    cash, follow, inputs = _hgco_with_a_cash_correction(conn, policy)
    review_id = follow(inputs)
    found = latest_review(conn, "HGCO")
    assert found is not None and (found.id, found.override_ids) == (review_id, (cash,))
    assert found.value is not None and found.mechanical_value is not None
    assert found.bridge[0]["delta"] == pytest.approx(found.value - found.mechanical_value)
    assert _no_reading(conn, follow(replace(inputs, cash=None)))
    dropped = override_row(conn, cash)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)
    assert [(e.principal, e.kind) for e in entries(conn, "HGCO")] == [
        (SYSTEM.principal, "override-drop")
    ]


def test_a_period_tied_stock_pay_follows_the_figure_the_anchor_read(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-13 7.2 and 11a: a period-tied ``earnings.sbc`` corrects the trailing stock pay
    the anchor read, MGCO's stored $400 m, its ``sbc_ttm``. The next snapshot on the same figures
    keeps it applied; one whose stored stock pay moved to $450 m drops it, the reading changed."""
    deciles = universe_deciles()
    inputs = as_live(mature_growth_inputs())
    first = value_company(inputs, deciles, policy, HGCO_TODAY)
    figure = current_reading(first, "earnings.sbc")
    assert figure == first.intermediates["sbc_ttm"] == 400e6
    refresh_id = create_refresh(
        conn, "revalue", None, policy.version, METHOD_VERSION, HGCO_AT, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, first, refresh_id, clock=lambda: HGCO_AT)
    pay = insert_override(
        conn,
        "MGCO",
        "earnings.sbc",
        figure,
        500e6,
        "USD",
        "the cash flow statements",
        EVIDENCE,
        "period-tied",
        "Q3 2026",
        figure,
        made_on,
        AGENT,
        HGCO_AT,
        "applied",
        "",
    )

    def follow(inputs: CompanyInputs) -> int | None:
        result = value_company(inputs, deciles, policy, HGCO_TODAY)
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: HGCO_AT)
        return follow_snapshot(
            conn,
            inputs,
            result,
            snapshot_id,
            deciles,
            policy,
            HGCO_TODAY,
            refresh_id,
            lambda: HGCO_AT,
        )

    assert follow(inputs) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (pay,)
    assert review.result.intermediates["sbc_ttm"] == 500e6
    assert inputs.trailing is not None
    assert _no_reading(conn, follow(replace(inputs, trailing=replace(inputs.trailing, sbc=450e6))))
    dropped = override_row(conn, pay)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)


def test_a_lasting_nil_stock_pay_holds_until_the_store_holds_one(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-13 7.3: MGCO with a stored trailing stock pay of nil and a lasting
    ``earnings.sbc`` of 0. It stays applied on the same figures, when a newer period is on file
    and when the trailing figure is missing; it drops when the store holds $50 m."""
    assert reviews.ON_FILE == ON_FILE
    deciles = universe_deciles()
    live = as_live(mature_growth_inputs())
    assert live.trailing is not None
    inputs = replace(live, trailing=replace(live.trailing, sbc=0.0))
    first = value_company(inputs, deciles, policy, HGCO_TODAY)
    assert current_reading(first, "earnings.sbc") == 0.0
    refresh_id = create_refresh(
        conn, "revalue", None, policy.version, METHOD_VERSION, HGCO_AT, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, first, refresh_id, clock=lambda: HGCO_AT)

    def nil() -> int:
        return insert_override(
            conn,
            "MGCO",
            "earnings.sbc",
            0.0,
            0.0,
            "USD",
            "the 10-K shows no share-based pay",
            EVIDENCE,
            "lasting",
            None,
            None,
            made_on,
            AGENT,
            HGCO_AT,
            "applied",
            "",
        )

    def follow(inputs: CompanyInputs) -> int | None:
        result = value_company(inputs, deciles, policy, HGCO_TODAY)
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: HGCO_AT)
        return follow_snapshot(
            conn,
            inputs,
            result,
            snapshot_id,
            deciles,
            policy,
            HGCO_TODAY,
            refresh_id,
            lambda: HGCO_AT,
        )

    def stock_pay(inputs: CompanyInputs, sbc: float | None) -> CompanyInputs:
        assert inputs.trailing is not None
        return replace(inputs, trailing=replace(inputs.trailing, sbc=sbc))

    pay = nil()
    assert follow(inputs) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (pay,)
    later = _a_quarter_on(inputs)
    assert later.trailing is not None and later.trailing.sbc == 0.0
    assert later.trailing.period_end == date(2026, 12, 31)  # a period-tied one drops: NEWER
    assert follow(later) is not None
    assert follow(stock_pay(later, None)) is not None  # a period lacks the line
    kept = override_row(conn, pay)
    assert kept is not None and kept.state == "applied"
    assert _no_reading(conn, follow(stock_pay(later, 50e6)))
    dropped = override_row(conn, pay)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", ON_FILE)

    # a row refused before its route carries no ``sbc_ttm``: the test reads the assembled figure
    again = nil()
    refused = replace(stock_pay(later, 50e6), shares_diluted=None)
    result = value_company(refused, deciles, policy, HGCO_TODAY)
    assert result.refusal == "no diluted share count"
    assert "sbc_ttm" not in result.intermediates
    assert _no_reading(conn, follow(refused))
    dropped = override_row(conn, again)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", ON_FILE)
    assert [(e.principal, e.kind, e.ref_id, e.summary) for e in entries(conn, "MGCO")] == [
        (SYSTEM.principal, "override-drop", again, f"earnings.sbc dropped: {ON_FILE}"),
        (SYSTEM.principal, "override-drop", pay, f"earnings.sbc dropped: {ON_FILE}"),
    ]  # newest first


def test_a_period_tied_override_drops_when_a_newer_period_is_on_file(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """HGCO reports a new quarter: the trailing period end moves from 30 Sep to 31 Dec, and the
    correction of the old period drops, though the cash line reads the same."""
    cash, follow, inputs = _hgco_with_a_cash_correction(conn, policy)
    assert follow(inputs) is not None
    later = _a_quarter_on(inputs)
    reading = current_reading(
        value_company(later, universe_deciles(), policy, HGCO_TODAY), "balance.cash"
    )
    corrected = override_row(conn, cash)
    assert corrected is not None and reading == corrected.corrected_value == 3_000e6
    assert _no_reading(conn, follow(later))
    dropped = override_row(conn, cash)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", NEWER)
    [entry] = entries(conn, "HGCO")
    assert (entry.principal, entry.kind, entry.summary) == (
        SYSTEM.principal,
        "override-drop",
        f"balance.cash dropped: {NEWER}",
    )


def test_a_period_tied_cash_correction_follows_the_newest_sheet(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-13 12.4 and 16: HGCO's cash correction of $3,000 m was made on its fiscal 2025
    sheet. The next snapshot reads a later sheet, the quarter of 30 Sep 2026, on the same trailing
    period: with the same cash the correction stays applied; with a cash of $3,200 m the reading
    changed, and it drops."""
    cash, follow, inputs = _hgco_with_a_cash_correction(conn, policy)
    made_on = _made_on(conn, cash)
    assert made_on.intermediates["balance_sheet"]["label"] == "fiscal 2025"
    later = on_quarter_sheet(inputs)
    assert later.trailing == inputs.trailing
    assert follow(later) is not None
    kept = override_row(conn, cash)
    assert kept is not None and kept.state == "applied"
    review = latest_review(conn, "HGCO")
    assert review is not None and review.override_ids == (cash,)
    assert review.result.intermediates["balance_sheet"]["label"] == "fiscal 2026 Q3"
    assert _no_reading(conn, follow(replace(later, cash=3_200e6)))
    dropped = override_row(conn, cash)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)


def test_a_period_tied_minority_interest_follows_the_sheet_s_line(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-13 13 and 11a: HGCO's newest sheet presents a minority interest of $120 m,
    which an agent corrects to $1,120 m, period-tied. The next snapshot on the same sheet keeps it
    applied, the review subtracting the agent's figure; one whose line moved to $150 m drops it,
    the reading changed."""
    held = with_minority(as_live(high_growth_inputs()), 120e6)
    minority, follow, inputs = _hgco_with_a_correction(conn, policy, "balance.minority", held)
    corrected = override_row(conn, minority)
    assert corrected is not None and corrected.corrected_value == 120e6
    assert follow(inputs) is not None
    kept = override_row(conn, minority)
    assert kept is not None and kept.state == "applied"
    review = latest_review(conn, "HGCO")
    assert review is not None and review.override_ids == (minority,)
    assert review.result.intermediates["minority_interest"] == 1_120e6
    assert _no_reading(conn, follow(with_minority(inputs, 150e6)))
    dropped = override_row(conn, minority)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)
    [entry] = entries(conn, "HGCO")
    assert entry.summary == f"balance.minority dropped: {CHANGED}"


def test_a_period_tied_minority_interest_drops_when_a_newer_period_is_on_file(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-13 11a: HGCO reports a new quarter, its trailing period end moving from 30 Sep
    to 31 Dec, and the correction of the old period's minority interest drops, though the line
    reads the same $120 m."""
    held = with_minority(as_live(high_growth_inputs()), 120e6)
    minority, follow, inputs = _hgco_with_a_correction(conn, policy, "balance.minority", held)
    later = _a_quarter_on(inputs)
    result = value_company(later, universe_deciles(), policy, HGCO_TODAY)
    assert current_reading(result, "balance.minority") == 120e6
    assert follow(later) is None
    dropped = override_row(conn, minority)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", NEWER)
    [entry] = entries(conn, "HGCO")
    assert entry.summary == f"balance.minority dropped: {NEWER}"


def test_period_tied_committed_shares_hold_until_a_newer_period_is_on_file(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-14 4 and 11a: the engine's reading of the committed shares is nil, so a
    period-tied ``shares.committed`` of 60 m made on MGCO, 1,000 m shares, keeps the nil it
    corrected on a snapshot of the same figures, the review dividing the value by 1,060 m; it drops
    when a newer period is on file."""
    deciles = universe_deciles()
    inputs = as_live(mature_growth_inputs())
    first = value_company(inputs, deciles, policy, HGCO_TODAY)
    assert first.value is not None and current_reading(first, "shares.committed") == 0.0
    refresh_id = create_refresh(
        conn, "revalue", None, policy.version, METHOD_VERSION, HGCO_AT, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, first, refresh_id, clock=lambda: HGCO_AT)
    committed = insert_override(
        conn,
        "MGCO",
        "shares.committed",
        0.0,
        60e6,
        "shares",
        "warrants granted to a customer",
        EVIDENCE,
        "period-tied",
        "Q3 2026",
        0.0,
        made_on,
        AGENT,
        HGCO_AT,
        "applied",
        "",
    )

    def follow(inputs: CompanyInputs) -> int | None:
        result = value_company(inputs, deciles, policy, HGCO_TODAY)
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: HGCO_AT)
        return follow_snapshot(
            conn,
            inputs,
            result,
            snapshot_id,
            deciles,
            policy,
            HGCO_TODAY,
            refresh_id,
            lambda: HGCO_AT,
        )

    assert follow(inputs) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (committed,)
    assert review.result.intermediates["shares"] == 1_060e6
    assert review.value == pytest.approx(first.value * 1_000 / 1_060)
    assert _no_reading(conn, follow(_a_quarter_on(inputs)))
    dropped = override_row(conn, committed)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", NEWER)


def test_a_period_tied_one_time_item_holds_until_a_newer_period_is_on_file(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-14 5 and 2026-11-13 11a: the engine's reading of the one-time item is nil, so
    a period-tied ``earnings.ntm_nri`` of $0.59 made on MGCO, an NTM EPS of $5.90, keeps the nil
    it corrected on a snapshot of the same figures, the review valuing year 1 at $5.31 and the
    company at the mechanical value × 5.31 ÷ 5.90; it drops when a newer period is on file, a
    quarter later."""
    deciles = universe_deciles()
    inputs = as_live(mature_growth_inputs())
    first = value_company(inputs, deciles, policy, HGCO_TODAY)
    assert first.value is not None and current_reading(first, "earnings.ntm_nri") == 0.0
    refresh_id = create_refresh(
        conn, "revalue", None, policy.version, METHOD_VERSION, HGCO_AT, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, first, refresh_id, clock=lambda: HGCO_AT)
    one_time = insert_override(
        conn,
        "MGCO",
        "earnings.ntm_nri",
        0.0,
        0.59,
        "USD a share",
        "the consensus carries gains on a stake",
        EVIDENCE,
        "period-tied",
        "Q3 2026",
        0.0,
        made_on,
        AGENT,
        HGCO_AT,
        "applied",
        "",
    )

    def follow(inputs: CompanyInputs) -> int | None:
        result = value_company(inputs, deciles, policy, HGCO_TODAY)
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: HGCO_AT)
        return follow_snapshot(
            conn,
            inputs,
            result,
            snapshot_id,
            deciles,
            policy,
            HGCO_TODAY,
            refresh_id,
            lambda: HGCO_AT,
        )

    assert follow(inputs) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (one_time,)
    assert review.result.intermediates["ntm_nri"] == 0.59
    assert review.result.intermediates["anchor"]["ntm_eps"] == pytest.approx(5.31)
    assert review.value == pytest.approx(first.value * 5.31 / 5.90)
    held = override_row(conn, one_time)
    assert held is not None and held.state == "applied"
    assert _no_reading(conn, follow(_a_quarter_on(inputs)))
    dropped = override_row(conn, one_time)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", NEWER)


def _mgco_with_a_revenue_step(
    conn: sqlite3.Connection,
    policy: Policy,
    inputs: CompanyInputs,
    tag: OverrideTag,
    new: float,
) -> tuple[int, Follow, ValuationResult]:
    """MGCO valued on ``inputs``, its snapshot stored and a period-tied override of the revenue
    step ``tag`` at ``new`` made on it, correcting the engine's reading, the consensus's step as
    found or none: the override's id, ``follow``, which values the inputs it is given, stores the
    snapshot and follows it, and the first result."""
    deciles = universe_deciles()
    first = value_company(inputs, deciles, policy, HGCO_TODAY)
    found = current_reading(first, tag)
    refresh_id = create_refresh(
        conn, "revalue", None, policy.version, METHOD_VERSION, HGCO_AT, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, first, refresh_id, clock=lambda: HGCO_AT)
    step = insert_override(
        conn,
        "MGCO",
        tag,
        found,
        new,
        "ratio",
        "the company guided revenue growth below the consensus",
        EVIDENCE,
        "period-tied",
        "Q3 2026",
        found,
        made_on,
        AGENT,
        HGCO_AT,
        "applied",
        "",
    )

    def follow(inputs: CompanyInputs) -> int | None:
        result = value_company(inputs, deciles, policy, HGCO_TODAY)
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: HGCO_AT)
        return follow_snapshot(
            conn,
            inputs,
            result,
            snapshot_id,
            deciles,
            policy,
            HGCO_TODAY,
            refresh_id,
            lambda: HGCO_AT,
        )

    return step, follow, first


def test_a_period_tied_revenue_step_holds_while_the_consensus_step_stands(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-14 6.1: the engine's reading of a revenue step is the consensus's step as
    found. On MGCO with fiscal 2027 to 2029 revenue of $25,000 m, $27,500 m and $29,700 m, a
    period-tied ``revenue.step_3`` of 5% corrects the 8% found: a snapshot of the same figures
    keeps it applied, its review's charge reading 5%, and one whose fiscal 2029 revenue moved to
    $30,250 m, a step of 10%, drops it, the reading changed."""
    base = mature_growth_inputs()
    revenue = (25_000e6, 27_500e6, 29_700e6)
    rows = tuple(
        replace(a, revenue=x, analysts_revenue=10)
        for a, x in zip(base.annual_estimates, revenue, strict=True)
    )
    inputs = as_live(replace(base, annual_estimates=rows))
    step, follow, first = _mgco_with_a_revenue_step(conn, policy, inputs, "revenue.step_3", 0.05)
    assert current_reading(first, "revenue.step_3") == pytest.approx(0.08)
    held = override_row(conn, step)
    assert held is not None and held.corrected_value == pytest.approx(0.08)
    assert follow(inputs) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (step,)
    charge = review.result.intermediates["charge"]
    assert charge["revenue_steps"] == [pytest.approx(0.10), 0.05]
    assert charge["revenue_steps_found"] == [pytest.approx(0.10), pytest.approx(0.08)]
    held = override_row(conn, step)
    assert held is not None and held.state == "applied"
    moved = (*rows[:2], replace(rows[2], revenue=30_250e6))
    assert _no_reading(conn, follow(replace(inputs, annual_estimates=moved)))
    dropped = override_row(conn, step)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)


def test_a_period_tied_revenue_step_with_no_consensus_step_drops_at_a_newer_period(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-14 6.1 on MGCO as it is, with no revenue consensus: the reading of
    ``revenue.step_2`` is none, so a period-tied override of 4% corrects none and stays applied on
    a snapshot of the same figures, the review's charge paying for 4% in year 2; it drops when a
    newer period is on file, a quarter later."""
    inputs = as_live(mature_growth_inputs())
    step, follow, first = _mgco_with_a_revenue_step(conn, policy, inputs, "revenue.step_2", 0.04)
    assert current_reading(first, "revenue.step_2") is None
    assert follow(inputs) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (step,)
    assert review.result.intermediates["charge"]["growth_by_year"][0] == 0.04
    assert review.result.intermediates["charge"]["revenue_step_source"] == ["agent", "none"]
    held = override_row(conn, step)
    assert held is not None and (held.state, held.corrected_value) == ("applied", None)
    assert _no_reading(conn, follow(_a_quarter_on(inputs)))
    dropped = override_row(conn, step)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", NEWER)


# Overrides at a split (spec 2026-11-14 7, as amended at the build): MGCO's 2-for-1 split of 27 Jan
# 2027, built by ``support.splits``.
EVE = date(2027, 1, 26)  # the quote's date of a refresh on the split's day before the US close
REPRICED = date(2027, 1, 28)  # the day a price refresh reprices at the post-split quote
SCALED = "override-split-scaled"


def _repriced(conn: sqlite3.Connection, policy: Policy, snapshot_id: int, price_date: date) -> int:
    """Snapshot ``snapshot_id`` repriced at the post-split quote of $75.00 on ``price_date``, as a
    price refresh writes it: its figures and its data date stay; its id."""
    found = snapshot_row(conn, snapshot_id)
    assert found is not None
    result = reprice(found.result, 75.0, price_date, policy)
    return insert_snapshot(conn, result, under(conn, policy, "price"), clock=lambda: HGCO_AT)


def _judgment(review: ReviewRow, tag: OverrideTag) -> TaggedInput:
    [entry] = [i for i in review.result.inputs if i.tag == "JUDGMENT" and i.name == tag]
    return entry


def test_an_override_a_share_made_before_a_split_applies_on_the_new_basis(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A lasting ``value.outside`` of $10.00 made on MGCO's snapshot of 10 Jan 2027, then a 2-for-1
    split on 27 Jan 2027: the snapshot of 1 Feb 2027 reviews it at $10.00 ÷ 2 = $5.00, which the
    bridge's new value and the JUDGMENT entry give and the value adds; the entry's note adds the
    figure as entered and the split; the review's result carries the note naming the input, and
    the snapshot none; the stored override keeps $10.00."""
    made_on = mgco_snapshot(conn, policy, BEFORE, BEFORE)
    outside = made_on_mgco(conn, made_on, "value.outside", 10.0, "USD a share")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    review = follow_mgco(conn, policy, AFTER, AFTER)
    [line] = review.bridge
    assert (line["tag"], line["old"], line["new"]) == ("value.outside", 0.0, 5.0)
    assert review.mechanical_value is not None and line["delta"] == pytest.approx(5.0)
    assert review.value == pytest.approx(review.mechanical_value + 5.0)
    entry = _judgment(review, "value.outside")
    assert entry.value == 5.0
    assert (
        entry.note == "a stake; entered as $10.00 a share before the 2-for-1 split of 27 Jan 2027"
    )
    [note] = [f for f in review.result.flags if f.code == SCALED]
    assert note.word == "Override scaled at a split"
    assert note.sentence == (
        "A split took effect after these inputs were entered, so each applies on the new basis: "
        "value.outside."
    )
    snapshot = snapshot_row(conn, review.snapshot_id)
    assert snapshot is not None and SCALED not in snapshot.flags
    stored = override_row(conn, outside)
    assert stored is not None and (stored.state, stored.new) == ("applied", 10.0)


def test_committed_shares_made_before_a_split_apply_on_the_new_basis(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A period-tied ``shares.committed`` of 60 m made before MGCO's 2-for-1 split applies at
    60 m × 2 = 120 m on the next snapshot, of the same period, whose nil reading keeps it: the
    review divides the value among 1,000 m + 120 m shares."""
    made_on = mgco_snapshot(conn, policy, BEFORE, BEFORE)
    committed = made_on_mgco(conn, made_on, "shares.committed", 60e6, "shares", "period-tied")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    review = follow_mgco(conn, policy, AFTER, AFTER)
    assert review.override_ids == (committed,)
    [line] = review.bridge
    assert (line["tag"], line["new"]) == ("shares.committed", 120e6)
    assert review.result.intermediates["shares"] == 1_120e6
    assert review.mechanical_value is not None
    assert review.value == pytest.approx(review.mechanical_value * 1_000 / 1_120)
    entry = _judgment(review, "shares.committed")
    assert entry.value == 120e6
    assert entry.note == "a stake; entered as 60.0M shares before the 2-for-1 split of 27 Jan 2027"
    [note] = [f for f in review.result.flags if f.code == SCALED]
    assert note.sentence.endswith("each applies on the new basis: shares.committed.")
    stored = override_row(conn, committed)
    assert stored is not None and (stored.new, stored.corrected_value) == (60e6, 0.0)


def test_an_override_made_after_a_split_is_not_scaled(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """An override made on MGCO's snapshot of 1 Feb 2027, whose figures the 2-for-1 split of 27
    Jan 2027 had reached, applies as entered on the next snapshot, with no words and no note."""
    store_splits(conn, (SPLIT_DAY, 2, 1))
    made_on_mgco(
        conn, mgco_snapshot(conn, policy, AFTER, AFTER), "value.outside", 10.0, "USD a share"
    )
    review = follow_mgco(conn, policy, AFTER, AFTER)
    [line] = review.bridge
    assert line["new"] == 10.0
    entry = _judgment(review, "value.outside")
    assert (entry.value, entry.note) == (10.0, "a stake")
    assert SCALED not in [f.code for f in review.result.flags]


def _outside_line(review: ReviewRow) -> tuple[float, bool]:
    """The review's outside value in force, and whether its note names a scaling at a split."""
    [line] = [x for x in review.bridge if x["tag"] == "value.outside"]
    return line["new"], SCALED in [f.code for f in review.result.flags]


def test_an_override_made_on_the_split_s_day_before_the_close_is_scaled_on_the_next(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A refresh on the split's day before the US close: its statements fetched on 27 Jan 2027,
    the day of the 2-for-1 split, its quote of 26 Jan, so the split rule did not reach its figures
    and its basis date is 26 Jan. An override made on it is scaled on the next snapshot, quoted
    and fetched on 27 Jan."""
    store_splits(conn, (SPLIT_DAY, 2, 1))
    made_on = mgco_snapshot(conn, policy, EVE, SPLIT_DAY)
    made_on_mgco(conn, made_on, "value.outside", 10.0, "USD a share")
    assert _outside_line(follow_mgco(conn, policy, SPLIT_DAY, SPLIT_DAY)) == (5.0, True)


def test_a_snapshot_of_the_split_s_day_before_the_close_has_not_seen_the_split(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """An override made on a snapshot of 10 Jan 2027 is not scaled on the snapshot of the split's
    day before the close (quoted 26 Jan, fetched 27 Jan), whose figures did not see the split; it
    is scaled on the next."""
    made_on_mgco(
        conn, mgco_snapshot(conn, policy, BEFORE, BEFORE), "value.outside", 10.0, "USD a share"
    )
    store_splits(conn, (SPLIT_DAY, 2, 1))
    early = follow_mgco(conn, policy, EVE, SPLIT_DAY)
    assert _outside_line(early) == (10.0, False)
    assert _judgment(early, "value.outside").note == "a stake"
    assert _outside_line(follow_mgco(conn, policy, AFTER, AFTER)) == (5.0, True)


def test_an_override_on_a_snapshot_repriced_after_a_split_is_scaled(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """The Review Focus case, through the snapshot that assembled the figures: a price refresh of
    28 Jan 2027 reprices the snapshot quoted and fetched on 10 Jan 2027 at the post-split quote,
    fetching no split, so an override made on the repriced snapshot stands on the old basis and is
    scaled."""
    made_on = _repriced(conn, policy, mgco_snapshot(conn, policy, BEFORE, BEFORE), REPRICED)
    found = snapshot_row(conn, made_on)
    assert found is not None and (found.data_date, found.price_date) == (BEFORE, REPRICED)
    made_on_mgco(conn, made_on, "value.outside", 10.0, "USD a share")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    review = follow_mgco(conn, policy, AFTER, AFTER)
    assert _outside_line(review) == (5.0, True)
    assert _judgment(review, "value.outside").note.endswith(
        "entered as $10.00 a share before the 2-for-1 split of 27 Jan 2027"
    )


def test_an_override_on_a_repriced_snapshot_reads_the_figures_it_repriced(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A snapshot a price refresh made on 28 Jan 2027 carries the figures of the snapshot it
    repriced. Where that snapshot was quoted and fetched on 27 Jan, the split's day, its figures
    saw the split, and an override made on the repriced one is not scaled. Where it was the
    refresh before the close (quoted 26 Jan), they did not, and the override is scaled, though the
    repriced snapshot's own two dates (28 and 27 Jan) are both on or after the split's day."""
    store_splits(conn, (SPLIT_DAY, 2, 1))
    seen = _repriced(conn, policy, mgco_snapshot(conn, policy, SPLIT_DAY, SPLIT_DAY), REPRICED)
    outside = made_on_mgco(conn, seen, "value.outside", 10.0, "USD a share")
    assert _outside_line(follow_mgco(conn, policy, AFTER, AFTER)) == (10.0, False)
    drop_override(conn, outside, "made again below", HGCO_AT)
    unseen = _repriced(conn, policy, mgco_snapshot(conn, policy, EVE, SPLIT_DAY), REPRICED)
    found = snapshot_row(conn, unseen)
    assert found is not None and (found.price_date, found.data_date) == (REPRICED, SPLIT_DAY)
    made_on_mgco(conn, unseen, "value.outside", 10.0, "USD a share")
    assert _outside_line(follow_mgco(conn, policy, AFTER, AFTER)) == (5.0, True)


def test_a_repriced_snapshot_with_no_assembling_snapshot_reads_its_own_dates(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A snapshot a price refresh made, with no earlier snapshot of the company that a full or
    scoped refresh or a revalue made, falls back to its own two dates: quoted 28 Jan 2027 with
    statements fetched on 10 Jan, its basis date is 10 Jan, so an override made on it is scaled."""
    made_on = mgco_snapshot(conn, policy, REPRICED, BEFORE, kind="price")
    made_on_mgco(conn, made_on, "value.outside", 10.0, "USD a share")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    assert _outside_line(follow_mgco(conn, policy, AFTER, AFTER)) == (5.0, True)


def test_the_splits_between_the_two_basis_dates_multiply(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A 2-for-1 split on 27 Jan 2027 and a 3-for-1 on 1 Feb 2027, the reviewed snapshot's basis
    date, divide a $12.00 made on 10 Jan 2027 by 2 × 3 = 6, to $2.00, the note naming both in
    order. A 4-for-1 on 10 Jan 2027, which the made-on snapshot's figures had seen, and a 5-for-1
    after the reviewed snapshot's basis date are not counted."""
    made_on = mgco_snapshot(conn, policy, BEFORE, BEFORE)
    made_on_mgco(conn, made_on, "value.outside", 12.0, "USD a share")
    store_splits(conn, (BEFORE, 4, 1), (SPLIT_DAY, 2, 1), (AFTER, 3, 1), (date(2027, 2, 5), 5, 1))
    review = follow_mgco(conn, policy, AFTER, AFTER)
    [line] = review.bridge
    assert line["new"] == 2.0
    assert _judgment(review, "value.outside").note == (
        "a stake; entered as $12.00 a share before the 2-for-1 split of 27 Jan 2027 and the "
        "3-for-1 split of 1 Feb 2027"
    )


def test_a_ratio_or_a_total_is_never_scaled_at_a_split(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Only an input in dollars a share or in shares is scaled: a belief (a ratio) and a cash
    figure (a total) made before MGCO's 2-for-1 split read as entered, beside a value outside the
    business, which the split halves. Through the follow (the cash figure dropped: MGCO's route
    does not read it), the belief's line stands at 8% and the note names the outside value
    alone."""
    made_on = mgco_snapshot(conn, policy, BEFORE, BEFORE)
    belief = made_on_mgco(conn, made_on, "growth.belief", 0.08, "ratio")
    cash = made_on_mgco(conn, made_on, "balance.cash", 3_000e6, "USD", "period-tied")
    outside = made_on_mgco(conn, made_on, "value.outside", 10.0, "USD a share")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    rows = [r for r in (override_row(conn, i) for i in (belief, cash, outside)) if r is not None]
    reviewed = mgco_snapshot(conn, policy, AFTER, AFTER)
    engine = reviews.engine_overrides(conn, "MGCO", rows, reviewed)
    words = "entered as $10.00 a share before the 2-for-1 split of 27 Jan 2027"
    assert [(o.id, o.tag, o.value, o.rescaled) for o in engine] == [
        (belief, "growth.belief", 0.08, None),
        (cash, "balance.cash", 3_000e6, None),
        (outside, "value.outside", 5.0, words),
    ]
    drop_override(conn, cash, "the route does not read it", HGCO_AT)
    review = follow_mgco(conn, policy, AFTER, AFTER)
    assert [(line["tag"], line["new"]) for line in review.bridge] == [
        ("growth.belief", 0.08),
        ("value.outside", 5.0),
    ]
    assert _judgment(review, "growth.belief").note == "a stake"
    [note] = [f for f in review.result.flags if f.code == SCALED]
    assert note.sentence.endswith("each applies on the new basis: value.outside.")


def test_the_words_name_the_currency_and_a_reverse_split(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """The figure as entered is printed as the flags print an amount a share, after the reporting
    currency's code on a row in another, a negative one with the minus sign first; a 1-for-10
    reverse split multiplies a figure a share by 10 and divides a count by 10."""
    made_on = mgco_snapshot(conn, policy, BEFORE, BEFORE)
    gap = made_on_mgco(conn, made_on, "earnings.cycle_gap", -1.5, "SEK a share")
    count = made_on_mgco(conn, made_on, "shares.committed", 60e6, "shares", "period-tied")
    store_splits(conn, (SPLIT_DAY, 1, 10))
    rows = [r for r in (override_row(conn, gap), override_row(conn, count)) if r is not None]
    reviewed = mgco_snapshot(conn, policy, AFTER, AFTER)
    engine = reviews.engine_overrides(conn, "MGCO", rows, reviewed)
    reverse = "the 1-for-10 reverse split of 27 Jan 2027"
    assert [(o.value, o.rescaled) for o in engine] == [
        (pytest.approx(-15.0), f"entered as −SEK 1.50 a share before {reverse}"),
        (pytest.approx(6e6), f"entered as 60.0M shares before {reverse}"),
    ]


def test_an_override_on_a_snapshot_from_before_1_3_is_judged_by_its_share_count_s_date(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A result stored before 1.3 has no ``trailing_end``; its period is the ``as_of`` of its
    diluted share count, 30 Sep 2026, the newest period the statements hold. Its trailing inputs
    cite the newest fiscal year's end, 31 Dec 2025, and are not read: on the same statements the
    correction stays; a quarter later it drops."""
    cash, follow, inputs = _hgco_with_a_cash_correction(conn, policy, strip="trailing_end")
    made_on = _made_on(conn, cash)
    assert "trailing_end" not in made_on.intermediates
    cited = {i.name: i.provenance.as_of for i in made_on.inputs}
    assert cited["revenue_ttm"] == cited["eps_ttm"] == date(2025, 12, 31)
    assert cited["shares_diluted"] == date(2026, 9, 30)
    assert follow(inputs) is not None
    kept = override_row(conn, cash)
    assert kept is not None and kept.state == "applied"
    assert _no_reading(conn, follow(_a_quarter_on(inputs)))
    dropped = override_row(conn, cash)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", NEWER)


def test_an_override_on_a_snapshot_from_before_1_3_with_no_period_follows_its_reading(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A result stored before 1.3 with neither ``trailing_end`` nor a diluted share count gives no
    period to read: the correction stays when the period moves and drops only on a changed
    reading."""
    cash, follow, inputs = _hgco_with_a_cash_correction(
        conn, policy, strip="trailing_end", keep_inputs=("price", "cash")
    )
    made_on = _made_on(conn, cash)
    assert {i.name for i in made_on.inputs} == {"price", "cash"}
    later = _a_quarter_on(inputs)
    assert follow(later) is not None
    kept = override_row(conn, cash)
    assert kept is not None and kept.state == "applied"
    assert _no_reading(conn, follow(replace(later, cash=None)))
    dropped = override_row(conn, cash)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)


@pytest.mark.parametrize("metric", ["eps", "net_income"])
def test_a_lasting_ntm_override_drops_when_its_guided_year_passes(
    conn: sqlite3.Connection, policy: Policy, metric: str
) -> None:
    """MGCO's NTM EPS override cites a gaap record for fiscal 2027, its base year, of EPS or of
    net income (spec 2026-11-14 9), the net income the EPS times the count. A full refresh on the
    same consensus keeps it; one whose consensus has moved a year on, so the base year is 2028,
    drops it, by the system, "the guided year has passed", with its ledger row."""
    today, deciles = date(2026, 10, 31), universe_deciles()
    at = datetime(2026, 11, 6, 9, 30, tzinfo=UTC)
    inputs = mature_growth_inputs()
    first = value_company(inputs, deciles, policy, today)
    assert first.intermediates["path"]["base_year"] == 2027
    ntm = current_reading(first, "earnings.ntm")
    assert isinstance(ntm, float)
    shares = current_reading(first, "shares.diluted")
    assert isinstance(shares, float)
    guided_figure = ntm if metric == "eps" else ntm * shares
    refresh_id = create_refresh(
        conn, "full", None, policy.version, METHOD_VERSION, at, EMPTY_SETTINGS_HASH
    )
    made_on = insert_snapshot(conn, first, refresh_id, clock=lambda: at)
    guided = insert_guidance(
        conn,
        "MGCO",
        metric,
        "2027",
        guided_figure,
        guided_figure * 1.1,
        "gaap",
        today,
        "We guide 2027.",
        "a 10-Q",
        AGENT,
        at,
        None,
    )
    cite = {"kind": "guidance", "ref": f"guidance:{guided}", "note": ""}
    anchor = insert_override(
        conn,
        "MGCO",
        "earnings.ntm",
        ntm,
        ntm * 1.05,
        "USD a share",
        "the guidance",
        [cite, *EVIDENCE],
        "lasting",
        None,
        None,
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
    found = latest_review(conn, "MGCO")
    assert found is not None and (found.id, found.override_ids) == (review_id, (anchor,))
    a_year_on = tuple(
        replace(
            q,
            period_end=q.period_end.replace(year=q.period_end.year + 1),
            fiscal_year=q.fiscal_year + 1,
        )
        for q in inputs.quarter_estimates
    )
    assert _no_reading(conn, follow(replace(inputs, quarter_estimates=a_year_on)))
    dropped = override_row(conn, anchor)
    assert dropped is not None and (dropped.state, dropped.drop_reason) == ("dropped", PASSED)
    [entry] = entries(conn, "MGCO")
    assert (entry.principal, entry.kind, entry.ref_id) == (
        SYSTEM.principal,
        "override-drop",
        anchor,
    )
    assert entry.summary == f"earnings.ntm dropped: {PASSED}"


# An override the route no longer reads (spec 2026-11-14 8): MGCO's overrides are made on its
# Mature Growth snapshot, and its next snapshot is valued on another company's figures where its
# phase moves. The routes each tag is read by are ``TAGS``'.


def _as_mgco(inputs: CompanyInputs) -> CompanyInputs:
    """``inputs`` as MGCO's, dated as assembly dates them."""
    return as_live(replace(inputs, symbol="MGCO"))


def _route_snapshot(conn: sqlite3.Connection, policy: Policy, inputs: CompanyInputs) -> int:
    """MGCO's snapshot valued on ``inputs``, written by a revalue: its id."""
    result = value_company(inputs, universe_deciles(), policy, HGCO_TODAY)
    return insert_snapshot(conn, result, under(conn, policy, "revalue"), clock=lambda: HGCO_AT)


def _follow_inputs(conn: sqlite3.Connection, policy: Policy, inputs: CompanyInputs) -> int | None:
    """MGCO's next snapshot, valued on ``inputs``, written by a revalue and followed: the review's
    id, ``None`` with no override left."""
    deciles = universe_deciles()
    result = value_company(inputs, deciles, policy, HGCO_TODAY)
    refresh_id = under(conn, policy, "revalue")
    snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: HGCO_AT)
    return follow_snapshot(
        conn, inputs, result, snapshot_id, deciles, policy, HGCO_TODAY, refresh_id, lambda: HGCO_AT
    )


def test_an_override_the_new_route_does_not_read_drops_with_the_route_s_reason(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """MGCO, on the Mature Growth route, carries a lasting runway return, a lasting belief and a
    lasting moat class, none of which the Decline route reads, and a lasting value outside the
    business of $1.00, which it reads. Its next snapshot classifies as Decline: the three drop by
    the system, "the Decline route does not read the input", each with its ledger row on the new
    snapshot, and the review there holds the outside value alone, the Decline value of $4.9533 a
    share (spec 13.1's row) plus $1.00."""
    made_on = _route_snapshot(conn, policy, _as_mgco(mature_growth_inputs()))
    stale = {
        tag: made_on_mgco(conn, made_on, tag, new, unit)
        for tag, new, unit in (
            ("return.runway", 0.15, "ratio"),
            ("growth.belief", 0.08, "ratio"),
            ("moat.class", "Narrow", "class"),
        )
    }
    outside = made_on_mgco(conn, made_on, "value.outside", 1.0, "USD a share")
    read = [tag for tag in (*stale, "value.outside") if "decline" in TAGS[tag].routes]
    assert read == ["value.outside"]
    review_id = _follow_inputs(conn, policy, _as_mgco(decline_inputs()))
    review = latest_review(conn, "MGCO")
    assert review is not None and (review.id, review.override_ids) == (review_id, (outside,))
    assert review.result.phase.phase == "Decline"
    assert review.mechanical_value == pytest.approx(4.9533, abs=5e-5)
    assert review.value == pytest.approx(review.mechanical_value + 1.0)
    for override_id in stale.values():
        dropped = override_row(conn, override_id)
        assert dropped is not None
        assert (dropped.state, dropped.drop_reason) == ("dropped", OFF_DECLINE)
    found = [
        (e.principal, e.kind, e.ref_id, e.snapshot_id, e.summary) for e in entries(conn, "MGCO")
    ]
    assert found == [
        (SYSTEM.principal, "override-drop", i, review.snapshot_id, f"{tag} dropped: {OFF_DECLINE}")
        for tag, i in reversed(stale.items())
    ]  # newest first


def test_a_period_tied_override_on_another_route_drops_with_the_route_s_reason(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A period-tied ``earnings.sbc`` corrects MGCO's stored $400 m. Its next snapshot, of the same
    trailing period, classifies as Mature Stable, whose route reads no stock pay: the engine's
    reading there is none, so the reading test would drop it as "the input the override corrected
    changed", but the route's test runs first and gives the true reason."""
    inputs = _as_mgco(mature_growth_inputs())
    made_on = _route_snapshot(conn, policy, inputs)
    pay = made_on_mgco(conn, made_on, "earnings.sbc", 500e6, "USD", "period-tied")
    held = override_row(conn, pay)
    assert held is not None and held.corrected_value == 400e6
    stable = _as_mgco(mature_stable_inputs())
    assert stable.trailing is not None and inputs.trailing is not None
    assert stable.trailing.period_end == inputs.trailing.period_end  # no newer period
    result = value_company(stable, universe_deciles(), policy, HGCO_TODAY)
    assert result.phase.phase == "Mature Stable"
    assert current_reading(result, "earnings.sbc") is None
    assert _follow_inputs(conn, policy, stable) is None
    dropped = override_row(conn, pay)
    assert dropped is not None
    assert (dropped.state, dropped.drop_reason) == ("dropped", OFF_MATURE_STABLE)
    [entry] = entries(conn, "MGCO")
    assert entry.summary == f"earnings.sbc dropped: {OFF_MATURE_STABLE}"


def test_a_phase_override_dropped_at_a_follow_takes_what_only_its_route_read(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """The Review Focus case. MGCO, Mature Growth, carries a period-tied phase override of High
    Growth, a lasting target margin of 25%, which the revenue-growth route reads and the Mature
    Growth route does not, and a lasting value outside the business of $1.00, which both read. On
    a snapshot of the same period the phase override stands, and the other two on its route. A
    quarter on, the phase override drops, "a newer period is on file", the row's route is its
    mechanical phase's again, and the target margin drops at the same follow with that route's
    reason; the review holds the outside value, the Mature Growth value plus $1.00."""
    inputs = _as_mgco(mature_growth_inputs())
    made_on = _route_snapshot(conn, policy, inputs)
    phase = made_on_mgco(conn, made_on, "phase", "High Growth", "phase", "period-tied")
    target = made_on_mgco(conn, made_on, "margin.target", 0.25, "ratio")
    outside = made_on_mgco(conn, made_on, "value.outside", 1.0, "USD a share")
    held = override_row(conn, phase)
    assert held is not None and held.corrected_value == "Mature Growth"
    assert _follow_inputs(conn, policy, inputs) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (phase, target, outside)
    assert review.result.phase.phase == "High Growth"
    assert _follow_inputs(conn, policy, _a_quarter_on(inputs)) is not None
    review = _reading(conn, "MGCO")  # the held review stays; the reading runs over the rest
    assert review is not None and review.override_ids == (outside,)
    assert review.result.phase.phase == "Mature Growth"
    assert review.mechanical_value is not None
    assert review.value == pytest.approx(review.mechanical_value + 1.0)
    rows = [override_row(conn, i) for i in (phase, target)]
    assert [(r.state, r.drop_reason) for r in rows if r is not None] == [
        ("dropped", NEWER),
        ("dropped", OFF_MATURE_GROWTH),
    ]
    assert [(e.ref_id, e.summary) for e in entries(conn, "MGCO")] == [
        (target, f"margin.target dropped: {OFF_MATURE_GROWTH}"),
        (phase, f"phase dropped: {NEWER}"),
    ]  # newest first


def test_an_unclassified_row_has_no_route_and_keeps_every_override(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A row unclassified for one refresh must not lose its review's inputs. MGCO carries a lasting
    belief, which its Mature Growth route reads, a lasting target margin, which it does not, and a
    lasting moat class; its next snapshot holds one fiscal year, too few to classify. No route
    reads anything there, and every override stays applied, with no ledger row: the review is
    the snapshot's refusal over all three."""
    inputs = _as_mgco(mature_growth_inputs())
    made_on = _route_snapshot(conn, policy, inputs)
    belief = made_on_mgco(conn, made_on, "growth.belief", 0.08, "ratio")
    target = made_on_mgco(conn, made_on, "margin.target", 0.25, "ratio")
    moat = made_on_mgco(conn, made_on, "moat.class", "Narrow", "class")
    unclassified = replace(inputs, series=inputs.series[-1:])
    result = value_company(unclassified, universe_deciles(), policy, HGCO_TODAY)
    assert (result.phase.phase, result.refusal) == (None, "fewer than two fiscal years")
    assert _follow_inputs(conn, policy, unclassified) is not None
    review = latest_review(conn, "MGCO")
    assert review is not None and review.override_ids == (belief, target, moat)
    assert (review.value, review.refusal) == (None, "fewer than two fiscal years")
    rows = [override_row(conn, i) for i in (belief, target, moat)]
    assert [r.state for r in rows if r is not None] == ["applied"] * 3
    assert entries(conn, "MGCO") == []


def test_a_failed_company_with_no_held_review_gets_the_refusal_as_its_review(
    env_valued: Env,
) -> None:
    """ACME has an applied override and holds no review, a state no write of the API makes, when
    its fetch fails: its refusal snapshot gets the refusal as its review, which ACME then holds,
    and the price refresh carries that refusal. (A company that holds a review keeps it through a
    failed fetch: ``test_held.py``.)"""
    env = env_valued
    belief = _override(env, "ACME", "growth.belief", 0.08)
    env.clock.now += timedelta(days=2)
    env.router.fail_symbols.add("ACME")
    scoped = env.run(["ACME"])
    failed = env.snapshot("ACME")
    assert failed.refresh_id == scoped and failed.refusal is not None
    assert failed.refusal.startswith("data fetch failed")
    with closing(env.connect()) as conn:
        review = latest_review(conn, "ACME")
    assert review is not None and (review.snapshot_id, review.kind) == (failed.id, "made")
    assert (review.value, review.mechanical_value, review.refusal) == (None, None, failed.refusal)
    assert (review.bridge, review.override_ids, review.refresh_id) == ((), (belief,), scoped)

    env.router.fail_symbols.clear()
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    price = env.refresh().run("price")
    repriced = env.snapshot("ACME")
    assert (repriced.refresh_id, repriced.price, repriced.refusal) == (price, 20.0, failed.refusal)
    with closing(env.connect()) as conn:
        after = latest_review(conn, "ACME")
        log = review_log(conn, "ACME")
    assert after is not None and (after.snapshot_id, after.kind) == (repriced.id, "held")
    assert (after.value, after.refusal, after.result.price) == (None, failed.refusal, 20.0)
    assert after.result.valid_until == review.result.valid_until
    assert [(r.refresh_id, r.mechanical_value, r.reviewed_value, r.price) for r in log] == [
        (price, None, None, 20.0),
        (scoped, None, None, failed.price),
    ]


def test_a_review_on_an_earlier_snapshot_is_carried_onto_the_repriced_one(
    env_valued: Env,
) -> None:
    """A snapshot written after the review, with none of its own: the price refresh reprices the
    snapshot and carries the held review onto it all the same (spec 2026-11-23 held reviewed
    value, 5.2), so the row still shows it."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    revalue = env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        before = latest_review(conn, "ACME")
        insert_snapshot(conn, env.snapshot("ACME").result, revalue, clock=env.clock)
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    env.refresh().run("price")
    snapshot = env.snapshot("ACME")
    assert snapshot.price == 20.0
    with closing(env.connect()) as conn:
        after = latest_review(conn, "ACME")
        assert before is not None and after is not None
        assert (after.kind, after.made_id, after.snapshot_id) == ("held", before.id, snapshot.id)
        assert (after.value, after.bridge) == (before.value, before.bridge)
        assert len(review_log(conn, "ACME")) == 2


def test_a_review_that_raises_leaves_the_snapshot_and_is_a_refusal(
    env_valued: Env, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    env = env_valued
    belief = _override(env, "ACME", "growth.belief", 0.08)

    def falls_over(*args: object) -> None:
        raise RuntimeError("the engine fell over")

    monkeypatch.setattr(reviews, "review_company", falls_over)
    refresh_id = env.refresh().run("revalue")
    snapshot = env.snapshot("ACME")
    assert (snapshot.refresh_id, snapshot.refusal) == (refresh_id, None)
    assert snapshot.value is not None and ("ACME", "valued", None) in env.items(refresh_id)
    refusal = f"{FAILED}: RuntimeError: the engine fell over"
    with closing(env.connect()) as conn:
        review = latest_review(conn, "ACME")
        [row] = review_log(conn, "ACME")
    assert review is not None and review.snapshot_id == snapshot.id
    assert (review.value, review.refusal, review.mechanical_value) == (
        None,
        refusal,
        snapshot.value,
    )
    assert (review.bridge, review.override_ids) == ((), (belief,))
    assert review.result.valid_until == snapshot.valid_until
    assert (row.review_id, row.mechanical_value, row.reviewed_value) == (
        review.id,
        snapshot.value,
        None,
    )
    assert f"ACME: {refusal}" in caplog.messages


def test_a_rebuild_that_raises_leaves_the_snapshot_and_takes_the_plain_move(
    env_valued: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rebuild of the held copy's figures that follow the price raises: the snapshot stands,
    and the copy keeps the held value with every other figure as made, at the new price (spec
    2026-11-23 held reviewed value, 5.2; ``refresh.held``). No refusal takes the review's place."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        made = latest_review(conn, "ACME")
    assert made is not None

    def falls_over(*args: object, **kwargs: object) -> None:
        raise ValueError("no price")

    monkeypatch.setattr(held, "reprice", falls_over)
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    refresh_id = env.refresh().run("price")
    snapshot = env.snapshot("ACME")
    assert (snapshot.refresh_id, snapshot.price) == (refresh_id, 20.0)
    assert ("ACME", "repriced", None) in env.items(refresh_id)
    with closing(env.connect()) as conn:
        review = latest_review(conn, "ACME")
    assert review is not None and review.snapshot_id == snapshot.id
    assert (review.kind, review.refusal, review.value) == ("held", None, made.value)
    assert (review.mechanical_value, review.bridge) == (made.mechanical_value, made.bridge)
    assert review.result.price == 20.0 and made.value is not None
    assert review.price_to_value == pytest.approx(20.0 / made.value)
    assert review.result.intermediates["held_as_made"]["why"] == "failed"
