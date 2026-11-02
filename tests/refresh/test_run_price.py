"""The price refresh over the four companies a full refresh of ``fixture_universe`` valued, on a
migrated temporary database: the quotes, in one batch or one call a symbol, then a new snapshot
of each company at its new price; the rows it leaves as they were, and the command.

The full refresh values ACME and AXLE (Mature Growth, buy $21.25, trim $49.03) and MILD (Mature
Stable, buy $11.46) at $50, all three ``trim``, and refuses NEWT (Young Growth, with no mature
peer for a target margin).
"""

import json
from collections import Counter
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fixture_universe import ADMITTED, serve_universe
from refresh_env import Env, use_cli
from vendor_double import FIXTURES, FMP_KEY

from fairband import __main__ as cli
from fairband.engine.route import reprice
from fairband.engine.types import Provenance
from fairband.refresh import run_price
from fairband.refresh.inputs import latest_price
from fairband.refresh.run import Progress
from fairband.store.companies import insert_companies, latest_companies
from fairband.store.snapshots import SnapshotRow, insert_snapshot

PRICE_DATE = date(2026, 10, 31)  # the new quotes' timestamp, a day after the fixtures'
NEW_PRICES = {"ACME": 20.0, "AXLE": 30.0, "MILD": 10.0, "NEWT": 60.0}
POLICY_CHANGED = "policy changed: run a full refresh"
METHOD_CHANGED = "method changed: run a revalue"


def quote_rows(prices: dict[str, float]) -> list[dict[str, Any]]:
    """ACME's quote fixture for each symbol, at its price, stamped a day later."""
    [row] = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text())
    later = row["timestamp"] + 86_400
    return [row | {"symbol": s, "price": p, "timestamp": later} for s, p in prices.items()]


def batch(prices: dict[str, float]) -> bytes:
    return json.dumps(quote_rows(prices)).encode()


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


def snapshots_of(env: Env) -> dict[str, SnapshotRow]:
    return {symbol: env.snapshot(symbol) for symbol in ADMITTED}


def quote_responses(env: Env, after: int = 0) -> list[tuple[str, str | None, str, int, bool]]:
    """The quote responses stored after response ``after``: endpoint, symbol, params, status and
    whether an error came with it."""
    with closing(env.connect()) as conn:
        rows = conn.execute(
            "SELECT endpoint, symbol, params, http_status, error FROM vendor_responses"
            " WHERE endpoint IN ('quote', 'batch-quote') AND id > ? ORDER BY id",
            (after,),
        ).fetchall()
    return [(r[0], r[1], r[2], r[3], r[4] is not None) for r in rows]


def last_response_id(env: Env) -> int:
    with closing(env.connect()) as conn:
        return int(conn.execute("SELECT MAX(id) FROM vendor_responses").fetchone()[0])


def test_price_refresh_keeps_value_updates_stance(env_valued: Env) -> None:
    env = env_valued
    before = snapshots_of(env)
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    stored_before = last_response_id(env)

    refresh_id = env.refresh().run("price")

    row = env.last()
    assert (row.id, row.kind, row.symbols, row.status, row.stage, row.message) == (
        refresh_id,
        "price",
        None,
        "done",
        "done",
        None,
    )
    assert row.calibration == {"total": 4, "repriced": 4, "failed": 0, "skipped": 0}
    assert env.items(refresh_id) == [(symbol, "repriced", None) for symbol in ADMITTED]
    # One batch call for the four, never a call per symbol; nothing else is fetched.
    assert env.router.calls == {"batch-quote": 1}
    assert env.router.requested["batch-quote"] == {"symbols": "ACME,AXLE,MILD,NEWT"}
    assert quote_responses(env, stored_before) == [
        ("batch-quote", None, '{"symbols": "ACME,AXLE,MILD,NEWT"}', 200, False)
    ]
    with closing(env.connect()) as conn:  # the quote observations are stored
        assert latest_price(conn, "ACME") == (20.0, PRICE_DATE)
        payloads = [r[0] for r in conn.execute("SELECT payload FROM vendor_responses")]
    assert all(FMP_KEY not in (payload or "") for payload in payloads)

    after = snapshots_of(env)
    acme, old = after["ACME"], before["ACME"]
    assert acme.refresh_id == refresh_id and acme.id > old.id
    unchanged = ("value", "buy_level", "fair_low", "fair_high", "trim_level", "phase", "route")
    unchanged += ("data_date", "valid_until", "deciles_refresh_id", "policy_version", "refusal")
    for name in unchanged:
        assert getattr(acme, name) == getattr(old, name), name
    assert (old.price, old.price_date, old.stance3) == (50.0, date(2026, 10, 30), "hold")
    assert (acme.price, acme.price_date, acme.stance3) == (20.0, PRICE_DATE, "buy")
    assert acme.stance5 != old.stance5
    implied = acme.result.intermediates["implied_growth"]
    assert implied != old.result.intermediates["implied_growth"]
    # The same inputs, cited as they were, but the price: the fresh quote, as of its date.
    [price] = [i for i in acme.result.inputs if i.name == "price"]
    quoted = Provenance("FMP quote", PRICE_DATE, env.clock.now, env.clock.now)
    assert (price.value, price.provenance) == (20.0, quoted)
    others = [i for i in acme.result.inputs if i.name != "price"]
    assert others == [i for i in old.result.inputs if i.name != "price"]
    stamps = {"observed_at": env.clock.now, "entered_at": env.clock.now}
    assert acme.result == reprice(old.result, 20.0, PRICE_DATE, env.policy, **stamps)
    assert {s: (r.price, r.stance3) for s, r in after.items()} == {
        "ACME": (20.0, "buy"),
        "AXLE": (30.0, "hold"),
        "MILD": (10.0, "buy"),
        "NEWT": (60.0, None),
    }

    assert list(dict.fromkeys(p.stage for p in env.progress)) == ["quotes", "reprice", "done"]
    assert [p for p in env.progress if p.stage in ("quotes", "done")] == [
        Progress(refresh_id, "quotes", 0, 0, 4, None),
        Progress(refresh_id, "quotes", 4, 0, 0, None),
        Progress(refresh_id, "done", 4, 0, 0, None),
    ]
    assert Progress(refresh_id, "reprice", 4, 0, 0, None) in env.progress


def test_price_refresh_copies_refused_rows(env_valued: Env) -> None:
    """NEWT's refusal is copied with the new price, its date and the price input only: refused
    for its target margin, it would move the margin the price needs too, but it has no
    sales-to-capital (its own measure is not usable and it has no peers), so that margin stays
    ``None``. ZERO, admitted with no snapshot yet, is skipped and never quoted."""
    env = env_valued
    with closing(env.connect()) as conn:
        acme = next(c for c in latest_companies(conn) if c.symbol == "ACME")
        insert_companies(conn, [replace(acme, symbol="ZERO", name="Zero Corp")])
    before = snapshots_of(env)
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)

    refresh_id = env.refresh().run("price")

    row = env.last()
    assert (row.status, row.calibration) == (
        "done",
        {"total": 5, "repriced": 4, "failed": 0, "skipped": 1},
    )
    assert env.router.requested["batch-quote"] == {"symbols": "ACME,AXLE,MILD,NEWT"}
    assert env.items(refresh_id) == [
        *[(symbol, "repriced", None) for symbol in ADMITTED],
        ("ZERO", "skipped", "no snapshot to reprice"),
    ]
    newt, old = env.snapshot("NEWT"), before["NEWT"]
    assert (newt.refresh_id, newt.price, newt.price_date) == (refresh_id, 60.0, PRICE_DATE)
    quoted = Provenance("FMP quote", PRICE_DATE, env.clock.now, env.clock.now)
    inputs = tuple(
        replace(i, value=60.0, provenance=quoted) if i.name == "price" else i
        for i in old.result.inputs
    )
    assert any(i.name == "price" for i in inputs)
    assert newt.result == replace(old.result, price=60.0, price_date=PRICE_DATE, inputs=inputs)
    assert (newt.value, newt.stance3, newt.refusal) == (
        None,
        None,
        "no target margin: 0 mature peers",
    )
    assert "revenue_path" in newt.result.intermediates
    assert newt.result.intermediates["implied_margin"] is None
    assert [s for s, _, _ in env.snapshots()].count("ZERO") == 0


def test_price_refresh_batch_fallback_per_symbol(env_valued: Env) -> None:
    """The account does not serve ``batch-quote`` (HTTP 402): the batch falls back to one
    ``quote`` call a symbol. NEWT's own call fails; it keeps its snapshot and the run goes on."""
    env = env_valued
    before = snapshots_of(env)
    env.router.fail.add("batch-quote")
    env.router.fail_symbols.add("NEWT")
    env.router.fail_status = 402
    for row in quote_rows(NEW_PRICES):
        env.router.symbol_bodies[("quote", row["symbol"])] = json.dumps([row]).encode()
    stored_before = last_response_id(env)

    refresh_id = env.refresh().run("price")

    row = env.last()
    assert (row.status, row.message, row.calibration) == (
        "done",
        None,
        {"total": 4, "repriced": 3, "failed": 1, "skipped": 0},
    )
    assert env.router.calls == {"batch-quote": 1, "quote": 4}
    assert quote_responses(env, stored_before) == [
        ("batch-quote", None, '{"symbols": "ACME,AXLE,MILD,NEWT"}', 402, True),
        ("quote", "ACME", '{"symbol": "ACME"}', 200, False),
        ("quote", "AXLE", '{"symbol": "AXLE"}', 200, False),
        ("quote", "MILD", '{"symbol": "MILD"}', 200, False),
        ("quote", "NEWT", '{"symbol": "NEWT"}', 402, True),
    ]
    items = env.items(refresh_id)
    assert items[:3] == [(symbol, "repriced", None) for symbol in ("ACME", "AXLE", "MILD")]
    symbol, status, reason = items[3]
    assert (symbol, status) == ("NEWT", "failed")
    assert reason is not None and reason.startswith("quote failed: VendorError: GET ")
    assert "402" in reason and FMP_KEY not in reason
    after = snapshots_of(env)
    assert {s: r.price for s, r in after.items()} == {
        "ACME": 20.0,
        "AXLE": 30.0,
        "MILD": 10.0,
        "NEWT": 50.0,
    }
    assert after["NEWT"] == before["NEWT"]  # no new row


def test_price_refresh_policy_version_mismatch_fails_symbol(env_valued: Env) -> None:
    """ACME's latest snapshot was valued under another policy version: its levels come from that
    policy, so a new price cannot be put against them. It keeps its snapshot."""
    env = env_valued
    with closing(env.connect()) as conn:
        old = env.snapshot("ACME")
        stale = replace(old.result, policy_version="fairband-policy-v0")
        insert_snapshot(conn, stale, old.refresh_id, clock=env.clock)
    acme = env.snapshot("ACME")
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)

    refresh_id = env.refresh().run("price")

    assert (env.last().status, env.last().calibration) == (
        "done",
        {"total": 4, "repriced": 3, "failed": 1, "skipped": 0},
    )
    assert env.items(refresh_id) == [
        ("ACME", "failed", POLICY_CHANGED),
        ("AXLE", "repriced", None),
        ("MILD", "repriced", None),
        ("NEWT", "repriced", None),
    ]
    assert env.snapshot("ACME") == acme
    assert (env.snapshot("AXLE").refresh_id, env.snapshot("AXLE").price) == (refresh_id, 30.0)


def test_price_refresh_method_version_mismatch_fails_symbol(env_valued: Env) -> None:
    """AXLE's latest snapshot was valued under method 0.1: its value is that method's, and a
    rebuild at the price would carry it, so AXLE takes a revalue, not a reprice. It keeps its
    snapshot, and the run goes on."""
    env = env_valued
    with closing(env.connect()) as conn:
        old = env.snapshot("AXLE")
        stale = replace(old.result, method_version="fairband-mechanical/0.1")
        insert_snapshot(conn, stale, old.refresh_id, clock=env.clock)
    axle = env.snapshot("AXLE")
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)

    refresh_id = env.refresh().run("price")

    assert (env.last().status, env.last().calibration) == (
        "done",
        {"total": 4, "repriced": 3, "failed": 1, "skipped": 0},
    )
    assert env.items(refresh_id) == [
        ("ACME", "repriced", None),
        ("AXLE", "failed", METHOD_CHANGED),
        ("MILD", "repriced", None),
        ("NEWT", "repriced", None),
    ]
    assert env.snapshot("AXLE") == axle
    assert (env.snapshot("MILD").refresh_id, env.snapshot("MILD").price) == (refresh_id, 10.0)


def test_price_refresh_rate_limited(env_valued: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """One symbol a call, so the 429 lands on MILD: the quotes stop there, the symbols quoted
    before it are repriced, NEWT is never reached and the run fails saying so."""
    env = env_valued
    monkeypatch.setattr(run_price, "QUOTE_BATCH", 1)
    env.router.fail_symbols.add("MILD")
    env.router.fail_status = 429
    for row in quote_rows(NEW_PRICES):
        env.router.symbol_bodies[("quote", row["symbol"])] = json.dumps([row]).encode()
    before = snapshots_of(env)

    refresh_id = env.refresh().run("price")

    row = env.last()
    assert (row.status, row.stage, row.message, row.calibration) == (
        "failed",
        "reprice",
        "rate limited by FMP: stopped after 3 companies",
        None,
    )
    assert env.items(refresh_id) == [
        ("ACME", "repriced", None),
        ("AXLE", "repriced", None),
        ("MILD", "failed", "quote incomplete: rate limited"),
        ("NEWT", "pending", None),
    ]
    # MILD's three tries (the client retries a 429), then nothing: NEWT is never asked for.
    assert env.router.symbol_calls == Counter({"ACME": 1, "AXLE": 1, "MILD": 3})
    after = snapshots_of(env)
    assert {s: r.refresh_id for s, r in after.items()} == {
        "ACME": refresh_id,
        "AXLE": refresh_id,
        "MILD": 1,
        "NEWT": 1,
    }
    assert after["MILD"] == before["MILD"] and after["NEWT"] == before["NEWT"]


def test_price_refresh_without_a_universe_reprices_every_snapshot(
    env_without_universe: Env,
) -> None:
    """Before any full refresh, the companies a scoped refresh valued are the symbols."""
    env = env_without_universe
    env.run(["ACME", "BOLT"])  # no deciles yet: two refusals, each with its price
    env.router.bodies["batch-quote"] = batch({"ACME": 52.0, "BOLT": 53.0})
    refresh_id = env.refresh().run("price")
    assert env.last().calibration == {"total": 2, "repriced": 2, "failed": 0, "skipped": 0}
    assert env.router.requested["batch-quote"] == {"symbols": "ACME,BOLT"}
    for symbol, price in (("ACME", 52.0), ("BOLT", 53.0)):
        snapshot = env.snapshot(symbol)
        assert (snapshot.refresh_id, snapshot.price, snapshot.refusal) == (
            refresh_id,
            price,
            "no universe deciles yet",
        )


def test_cli_price_refresh(
    env_valued: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env = env_valued
    use_cli(env, monkeypatch, tmp_path)
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    assert cli.main(["refresh", "--kind", "price"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "quotes: 0 done, 0 failed, 4 to go",
        "quotes: 4 done, 0 failed, 0 to go",
        "reprice: 0 done, 0 failed, 4 to go",
        "reprice: 1 done, 0 failed, 3 to go",
        "reprice: 2 done, 0 failed, 2 to go",
        "reprice: 3 done, 0 failed, 1 to go",
        "reprice: 4 done, 0 failed, 0 to go",
        "done: 4 done, 0 failed, 0 to go",
        "refresh 2: done · 4 repriced, 0 failed, 0 skipped",
    ]
    assert env.snapshot("ACME").price == 20.0
