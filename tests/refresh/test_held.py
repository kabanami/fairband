"""A refresh reads a review again and carries the held one (spec 2026-11-23 held reviewed value,
5.1 to 5.5 and 7; ``refresh/held.py``, ``refresh/reviews.py``)."""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta

import pytest
from fixture_universe import serve_universe
from refresh_env import Env
from support.engine_companies import universe_deciles
from support.splits import (
    AFTER,
    AT,
    BEFORE,
    SPLIT_DAY,
    TODAY,
    made_on_mgco,
    mgco_on,
    mgco_snapshot,
    store_splits,
    under,
)
from vendor_double import FIXTURES

from fairband.engine import METHOD_VERSION
from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.overrides import Lifetime, OverrideTag, current_reading
from fairband.engine.route import value_company
from fairband.policy import Policy
from fairband.refresh import reviews
from fairband.refresh.reviews import follow_snapshot
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override, override_row
from fairband.store.reviews import (
    ReviewRow,
    held_row,
    latest_review,
    review_log,
    review_row,
    reviews_for,
)
from fairband.store.snapshots import insert_snapshot, snapshot_row

AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "transcript", "ref": "Q3 call", "note": ""}]
CHANGED = "the input the override corrected changed"


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
) -> int:
    """An applied override of ``symbol`` made on its latest snapshot; a period-tied one corrects
    the engine's reading there."""
    snapshot = env.snapshot(symbol)
    old = current_reading(snapshot.result, tag)
    tied = lifetime == "period-tied"
    with closing(env.connect()) as conn:
        return insert_override(
            conn,
            symbol,
            tag,
            *(old, new, "ratio", "because", EVIDENCE, lifetime),
            "FY2025" if tied else None,
            old if tied else None,
            snapshot.id,
            AGENT,
            env.clock(),
            "applied",
            "",
        )


def _shares(env: Env, symbol: str) -> int:
    """A period-tied override of the company's diluted share count, 10% above the engine's
    reading, which it corrects."""
    count = current_reading(env.snapshot(symbol).result, "shares.diluted")
    assert isinstance(count, float)
    return _override(env, symbol, "shares.diluted", count * 1.1, "period-tied")


def _made(env: Env, symbol: str) -> ReviewRow:
    """The review the company holds after a revalue over its applied overrides, made when it held
    none (the plan's decision 4)."""
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        made = latest_review(conn, symbol)
    assert made is not None and made.kind == "made" and made.value is not None
    env.clock.now += timedelta(hours=1)
    return made


def _quotes(prices: dict[str, float]) -> bytes:
    """ACME's quote fixture for each symbol at its price, stamped a day later."""
    [row] = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text(encoding="utf-8"))
    later = row["timestamp"] + 86_400
    rows = [row | {"symbol": s, "price": p, "timestamp": later} for s, p in prices.items()]
    return json.dumps(rows).encode()


def test_a_refresh_with_overrides_and_no_held_review_holds_its_review(env_valued: Env) -> None:
    """A state no write of the API makes: an applied override and no review. The refresh's review
    is then the one the company holds, so no override is hidden; the log names it made."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    with closing(env.connect()) as conn:
        held = held_row(conn, "ACME")
        [row] = review_log(conn, "ACME")
    assert held is not None and (held.review_id, held.read_again_at, held.early_at) == (
        made.id,
        None,
        None,
    )
    assert (row.review_id, row.kind) == (made.id, "made")


def test_a_revalue_that_moves_the_reading_leaves_the_held_value(env_valued: Env) -> None:
    """The spec's 7: a revalue under which the review gives another value. The held value stays,
    carried onto the new snapshot as a held copy; the reading is a row of its own, and the store
    keeps its value as the newest good reading with the time a refresh first read the review
    again. A second revalue changes neither the held value nor that time."""
    env = env_valued
    belief = _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    env.policy = replace(env.policy, required_return=env.policy.required_return + 0.01)
    refresh_id = env.refresh().run("revalue")
    at = env.clock()
    snapshot = env.snapshot("ACME")
    with closing(env.connect()) as conn:
        current = latest_review(conn, "ACME")
        rows = reviews_for(conn, "ACME")
        held = held_row(conn, "ACME")
        log = review_log(conn, "ACME")
    assert current is not None and held is not None
    assert (current.kind, current.made_id, current.snapshot_id, current.refresh_id) == (
        "held",
        made.id,
        snapshot.id,
        refresh_id,
    )
    assert (current.value, current.bridge, current.override_ids) == (
        made.value,
        made.bridge,
        (belief,),
    )
    assert current.mechanical_value == made.mechanical_value != snapshot.value
    assert current.result.valid_until == made.result.valid_until
    [reading] = [r for r in rows if r.kind == "reading"]
    assert (reading.made_id, reading.snapshot_id, reading.override_ids) == (
        made.id,
        snapshot.id,
        (belief,),
    )
    assert reading.value is not None and reading.value != made.value
    assert reading.mechanical_value == snapshot.value
    assert (held.review_id, held.read_again_at, held.reading_value, held.reading_at) == (
        made.id,
        at,
        reading.value,
        at,
    )
    assert (held.newer_period, held.dropped, held.reading_refusal) == (None, (), None)
    low, high = env.policy.fair_band
    outside = not low <= reading.value / made.value <= high
    assert held.early_at == (at.date() if outside else None)
    assert [(r.review_id, r.kind) for r in log[:2]] == [
        (current.id, "held"),
        (reading.id, "reading"),
    ]
    env.clock.now += timedelta(days=1)
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        again, later = latest_review(conn, "ACME"), held_row(conn, "ACME")
    assert again is not None and later is not None and again.id > current.id
    assert (again.kind, again.made_id, again.value) == ("held", made.id, made.value)
    assert (later.read_again_at, later.early_at) == (at, held.early_at)


def test_a_refresh_that_drops_a_period_tied_override_holds_the_review(env_valued: Env) -> None:
    """The spec's 7: a refresh drops a period-tied override whose input changed. The held value
    stays; the store names the override among those the system dropped, with the drop's reason
    and time; the reading runs over the override still applied; and the day of the refresh is the
    day the value expired early."""
    env = env_valued
    belief = _override(env, "AXLE", "growth.belief", 0.08)
    cash = _shares(env, "AXLE")
    made = _made(env, "AXLE")
    assert made.override_ids == (belief, cash)
    with closing(env.connect()) as conn, conn:
        conn.execute("UPDATE overrides SET corrected_value = '1.0' WHERE id = ?", (cash,))
    env.run(["AXLE"])
    at = env.clock()
    snapshot = env.snapshot("AXLE")
    with closing(env.connect()) as conn:
        current, held = latest_review(conn, "AXLE"), held_row(conn, "AXLE")
        dropped = override_row(conn, cash)
        readings = [r for r in reviews_for(conn, "AXLE") if r.kind == "reading"]
    assert current is not None and held is not None and dropped is not None
    assert (dropped.state, dropped.drop_reason) == ("dropped", CHANGED)
    assert (current.kind, current.snapshot_id, current.value) == ("held", snapshot.id, made.value)
    assert current.override_ids == (belief, cash)  # the held review still counts it
    [reading] = readings
    assert reading.override_ids == (belief,)
    assert held.dropped == (
        {"id": cash, "tag": "shares.diluted", "reason": CHANGED, "at": at.isoformat()},
    )
    assert (held.reading_value, held.early_at) == (reading.value, at.date())


def test_a_refresh_that_drops_the_last_override_holds_the_review(env_valued: Env) -> None:
    """Spec 5.1 and 5.4: when a refresh drops the last override the held review stays, and with
    no override left the refresh computes no reading: the reading is the mechanical value."""
    env = env_valued
    cash = _shares(env, "AXLE")
    made = _made(env, "AXLE")
    with closing(env.connect()) as conn, conn:
        conn.execute("UPDATE overrides SET corrected_value = '1.0' WHERE id = ?", (cash,))
    env.refresh().run("revalue")
    snapshot = env.snapshot("AXLE")
    with closing(env.connect()) as conn:
        current, held = latest_review(conn, "AXLE"), held_row(conn, "AXLE")
        kinds = [r.kind for r in reviews_for(conn, "AXLE")]
    assert current is not None and held is not None
    assert (current.kind, current.snapshot_id, current.value) == ("held", snapshot.id, made.value)
    assert kinds == ["held", "made"]  # no reading
    assert (held.reading_value, held.reading_refusal) == (snapshot.value, None)
    assert [d["id"] for d in held.dropped] == [cash]
    env.clock.now += timedelta(days=1)
    env.refresh().run("revalue")  # with no override applied the held review is still carried
    with closing(env.connect()) as conn:
        again = latest_review(conn, "AXLE")
    assert again is not None and (again.kind, again.value) == ("held", made.value)
    assert again.snapshot_id == env.snapshot("AXLE").id


def test_a_refresh_after_the_company_reports_stores_the_newer_period(env_valued: Env) -> None:
    """Spec 5.3, reason 1: the latest snapshot's trailing period ends after the one the held
    review was made on. The review here was made on a snapshot whose period the test moves back
    a year."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    on_file = env.snapshot("ACME").result.intermediates["trailing_end"]
    earlier = date.fromisoformat(on_file).replace(year=date.fromisoformat(on_file).year - 1)
    with closing(env.connect()) as conn, conn:
        conn.execute(
            "UPDATE snapshots SET result = json_set(result, '$.intermediates.trailing_end', ?)"
            " WHERE id = ?",
            (earlier.isoformat(), made.snapshot_id),
        )
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        current, held = latest_review(conn, "ACME"), held_row(conn, "ACME")
    assert current is not None and held is not None and current.value == made.value
    assert held.newer_period == date.fromisoformat(on_file)
    assert held.early_at == env.clock().date()


def test_a_failed_company_keeps_its_held_review_and_its_state(env_valued: Env) -> None:
    """The spec's 7: a refresh whose fetch fails changes neither the held value nor its state.
    The held review is carried onto the refusal snapshot, so the row still shows it, and a price
    refresh carries it on."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    with closing(env.connect()) as conn:
        before = held_row(conn, "ACME")
    env.clock.now += timedelta(days=2)
    env.router.fail_symbols.add("ACME")
    scoped = env.run(["ACME"])
    failed = env.snapshot("ACME")
    assert failed.refresh_id == scoped and failed.refusal is not None
    with closing(env.connect()) as conn:
        current, held = latest_review(conn, "ACME"), held_row(conn, "ACME")
        kinds = [r.kind for r in reviews_for(conn, "ACME")]
    assert current is not None and held == before
    assert (current.kind, current.snapshot_id, current.value) == ("held", failed.id, made.value)
    assert (current.bridge, current.refusal) == (made.bridge, None)
    assert kinds == ["held", "made"]  # no reading
    env.router.fail_symbols.clear()
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    env.refresh().run("price")
    with closing(env.connect()) as conn:
        after = latest_review(conn, "ACME")
    assert after is not None and (after.kind, after.value) == ("held", made.value)
    assert after.snapshot_id == env.snapshot("ACME").id and after.result.price == 20.0
    assert after.price_to_value == pytest.approx(20.0 / made.value)


def test_a_failure_while_storing_the_state_leaves_the_snapshot_and_the_held_review(
    env_valued: Env, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The whole-branch review of 2026-11-23: an error while the facts of the state are stored
    must not undo the company's snapshot. The refresh values the company, carries the held
    review, logs a warning, and leaves the stored state as it was."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    with closing(env.connect()) as conn:
        before = held_row(conn, "ACME")

    def falls_over(*args: object, **kwargs: object) -> None:
        raise RuntimeError("the facts fell over")

    monkeypatch.setattr(reviews, "read_again", falls_over)
    refresh_id = env.refresh().run("revalue")
    snapshot = env.snapshot("ACME")
    assert (snapshot.refresh_id, snapshot.refusal) == (refresh_id, None)
    assert ("ACME", "valued", None) in env.items(refresh_id)
    with closing(env.connect()) as conn:
        current, held = latest_review(conn, "ACME"), held_row(conn, "ACME")
    assert current is not None and held == before
    assert (current.kind, current.snapshot_id, current.value) == ("held", snapshot.id, made.value)
    assert any("ACME" in m and "the facts fell over" in m for m in caplog.messages)


def test_a_failed_reading_still_marks_the_review_read_again(
    env_valued: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole-branch review of 2026-11-23: a reading the engine cannot compute is no reason
    and no reading, and the last good one stands; but the refresh did value the company on new
    figures. It still stores that it read the review again, so a report is not taken on it, and
    the newer period it found."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    on_file = env.snapshot("ACME").result.intermediates["trailing_end"]
    earlier = date.fromisoformat(on_file).replace(year=date.fromisoformat(on_file).year - 1)
    with closing(env.connect()) as conn, conn:
        conn.execute(
            "UPDATE snapshots SET result = json_set(result, '$.intermediates.trailing_end', ?)"
            " WHERE id = ?",
            (earlier.isoformat(), made.snapshot_id),
        )

    def falls_over(*args: object, **kwargs: object) -> None:
        raise RuntimeError("the engine fell over")

    monkeypatch.setattr(reviews, "review_company", falls_over)
    env.refresh().run("revalue")
    at = env.clock()
    with closing(env.connect()) as conn:
        current, held = latest_review(conn, "ACME"), held_row(conn, "ACME")
        [reading] = [r for r in reviews_for(conn, "ACME") if r.kind == "reading"]
    assert current is not None and held is not None
    assert (current.kind, current.value) == ("held", made.value)
    assert reading.refusal is not None and reading.refusal.startswith("review failed")
    assert (held.read_again_at, held.newer_period) == (at, date.fromisoformat(on_file))
    assert (held.reading_value, held.reading_refusal) == (None, None)  # no good reading yet
    assert held.early_at == at.date()  # by the newer period


def test_a_price_refresh_carries_the_held_review_and_rebuilds_what_follows_the_price(
    env_valued: Env,
) -> None:
    """Spec 5.2: under the versions the review was made under, a price refresh moves on the held
    copy everything it moved on a review before: price ÷ value, the word and the implied growth.
    The value, the bridge and the window stay, and the store's state does not change."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    with closing(env.connect()) as conn:
        before = held_row(conn, "ACME")
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    refresh_id = env.refresh().run("price")
    snapshot = env.snapshot("ACME")
    with closing(env.connect()) as conn:
        current, held = latest_review(conn, "ACME"), held_row(conn, "ACME")
        [newest, *_] = review_log(conn, "ACME")
    assert current is not None and held == before
    assert (current.kind, current.made_id, current.snapshot_id, current.refresh_id) == (
        "held",
        made.id,
        snapshot.id,
        refresh_id,
    )
    assert (current.value, current.bridge, current.mechanical_value) == (
        made.value,
        made.bridge,
        made.mechanical_value,
    )
    assert current.result.valid_until == made.result.valid_until
    assert current.result.price == 20.0 and current.price_to_value == pytest.approx(
        20.0 / made.value
    )
    implied = current.result.intermediates["implied_growth"]
    assert implied != made.result.intermediates["implied_growth"]
    assert "held_as_made" not in current.result.intermediates
    assert (newest.review_id, newest.kind, newest.price) == (current.id, "held", 20.0)


def test_a_held_review_of_another_method_version_takes_the_plain_move(env_valued: Env) -> None:
    """Review Focus 1: a held review made under another method version is not rebuilt with
    today's formulas. Its copy keeps the value, the bridge and every figure as made, takes the
    new price, price ÷ value and the word on the policy in force and the levels of that policy,
    and says so in ``held_as_made``. A revalue carries it the same way."""
    env = env_valued
    _override(env, "ACME", "growth.belief", 0.08)
    made = _made(env, "ACME")
    old = "fairband-mechanical/1.1"
    with closing(env.connect()) as conn, conn:
        conn.execute(
            "UPDATE reviews SET method_version = ?,"
            " result = json_set(result, '$.method_version', ?) WHERE id = ?",
            (old, old, made.id),
        )
    env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0})
    env.refresh().run("price")
    with closing(env.connect()) as conn:
        current = latest_review(conn, "ACME")
    assert current is not None and made.value is not None
    moat = made.result.intermediates["moat"]
    assert (current.kind, current.method_version, current.value) == ("held", old, made.value)
    assert (current.bridge, current.mechanical_value) == (made.bridge, made.mechanical_value)
    assert current.result.levels == levels_for(made.value, moat, env.policy)
    assert (current.price_to_value, current.designation) == designation_for(
        20.0, made.value, env.policy.edges_for(moat)
    )
    im = current.result.intermediates
    assert im["implied_growth"] == made.result.intermediates["implied_growth"]
    assert im["held_as_made"] == {"why": "method", "since": made.result.price_date.isoformat()}
    env.clock.now += timedelta(days=1)
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        again = latest_review(conn, "ACME")
    assert again is not None and (again.kind, again.value) == ("held", made.value)
    assert again.result.intermediates["held_as_made"] == im["held_as_made"]
    assert again.method_version == old and METHOD_VERSION != old


def test_a_foreign_held_review_moves_with_the_rate(env_valued: Env) -> None:
    """Review Focus 3, spec 5.2: KRON reports in SEK. Its held value in the currency stays; its
    value in US dollars is that value at the latest snapshot's rate, at a price refresh that
    rebuilds and at one that takes the plain move alike, and the mechanical value and the
    bridge's changes move with it, so they still sum to the held value."""
    env = env_valued
    _override(env, "KRON", "growth.belief", 0.08)
    made = _made(env, "KRON")
    in_sek = made.result.intermediates["value_in_currency"]
    assert made.result.intermediates["fx_rate"] == 10.52 and made.value is not None

    def reprice_at(rate: float) -> ReviewRow:
        env.router.bodies["batch-quote"] = _quotes({"ACME": 20.0, "KRON": 40.0, "MILD": 10.0})
        [pair] = json.loads(_quotes({"USDSEK": rate}))
        env.router.symbol_bodies[("quote", "USDSEK")] = json.dumps([pair]).encode()
        env.refresh().run("price")
        with closing(env.connect()) as conn:
            found = latest_review(conn, "KRON")
        assert found is not None and found.snapshot_id == env.snapshot("KRON").id
        return found

    def sums(review: ReviewRow) -> None:
        [line] = review.bridge
        assert review.mechanical_value is not None and review.value is not None
        assert review.mechanical_value + line["delta"] == pytest.approx(review.value)

    rebuilt = reprice_at(10.0)
    assert rebuilt.result.intermediates["value_in_currency"] == in_sek
    assert rebuilt.value == pytest.approx(in_sek / 10.0)
    assert "held_as_made" not in rebuilt.result.intermediates
    sums(rebuilt)
    old = "fairband-mechanical/1.1"
    with closing(env.connect()) as conn, conn:
        conn.execute(
            "UPDATE reviews SET method_version = ?,"
            " result = json_set(result, '$.method_version', ?) WHERE id = ?",
            (old, old, rebuilt.id),
        )
    env.clock.now += timedelta(days=1)
    plain = reprice_at(9.5)
    assert plain.result.intermediates["value_in_currency"] == in_sek
    assert plain.result.intermediates["fx_rate"] == 9.5
    assert plain.value == pytest.approx(in_sek / 9.5)
    assert plain.result.intermediates["held_as_made"]["why"] == "method"
    [was], [line] = made.bridge, plain.bridge
    assert (line["old"], line["new"]) == (was["old"], was["new"])  # the readings stay
    assert line["delta"] == pytest.approx(was["delta"] * 10.52 / 9.5)
    sums(plain)
    # at a refresh that values, the copy stands at the new snapshot's own rate too
    env.clock.now += timedelta(days=1)
    env.refresh().run("revalue")
    snapshot = env.snapshot("KRON")
    with closing(env.connect()) as conn:
        revalued = latest_review(conn, "KRON")
    assert revalued is not None and revalued.snapshot_id == snapshot.id
    rate = snapshot.result.intermediates["fx_rate"]
    assert revalued.result.intermediates["value_in_currency"] == in_sek
    assert revalued.result.intermediates["fx_rate"] == rate
    assert revalued.value == pytest.approx(in_sek / rate)
    sums(revalued)


def test_a_two_for_one_split_halves_the_held_value_and_changes_no_word(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """The spec's 7: MGCO's review is made on figures of 10 Jan 2027; a 2-for-1 split follows on
    27 Jan, and the snapshot of 1 Feb sees it, at half the price. The held value a share and its
    levels halve, the mechanical value and the bridge with them, and price ÷ value and the word
    stay; the copy says it is as made since the split."""
    deciles = universe_deciles()

    def follow(when: date, halved: bool) -> ReviewRow:
        inputs = mgco_on(when, when)
        result = value_company(inputs, deciles, policy, TODAY)
        if halved:
            assert result.price is not None
            result = replace(result, price=result.price / 2)
        refresh_id = under(conn, policy, "revalue")
        snapshot_id = insert_snapshot(conn, result, refresh_id, clock=lambda: AT)
        review_id = follow_snapshot(
            conn, inputs, result, snapshot_id, deciles, policy, TODAY, refresh_id, lambda: AT
        )
        review = latest_review(conn, "MGCO")
        assert review is not None and review.id == review_id and review.snapshot_id == snapshot_id
        return review

    first = mgco_snapshot(conn, policy, BEFORE, BEFORE)
    made_on_mgco(conn, first, "growth.belief", 0.08, "ratio")
    made = follow(BEFORE, halved=False)
    assert made.kind == "made" and made.value is not None and made.mechanical_value is not None
    store_splits(conn, (SPLIT_DAY, 2, 1))
    after = follow(AFTER, halved=True)
    assert (after.kind, after.made_id) == ("held", made.id)
    assert after.value == made.value / 2
    assert after.result.levels == levels_for(made.value / 2, "Wide", policy)
    assert after.mechanical_value == pytest.approx(made.mechanical_value / 2)
    [was], [line] = made.bridge, after.bridge
    assert line["delta"] == pytest.approx(was["delta"] / 2)
    assert after.price_to_value == pytest.approx(made.price_to_value)
    assert after.designation == made.designation
    assert after.result.intermediates["held_as_made"]["why"] == "split"
    held = held_row(conn, "MGCO")
    assert held is not None and (held.dropped, held.newer_period) == ((), None)
    assert review_row(conn, made.id) == made and snapshot_row(conn, first) is not None
