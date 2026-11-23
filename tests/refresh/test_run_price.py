"""The price refresh over the five companies a full refresh of ``fixture_universe`` valued, on a
migrated temporary database: the quotes, in one batch or one call a symbol, the pairs' quotes,
then a new snapshot of each company at its new price; the rows it leaves as they were, and the
command.

The full refresh values ACME and AXLE (Mature Growth, $31.24 a share) and MILD (Mature Stable,
$18.68) at $50: ACME and AXLE ``well-above`` (1.60 × the value), MILD ``well-above`` (2.68 ×). It
values KRON, which reports in SEK, in SEK at USDSEK's 10.52 of 2026-10-30, its value a share in
USD, so a price refresh quotes the pair (spec 2026-11-10 7.1); and it refuses NEWT (Young Growth,
with no mature peer for a target margin).
"""

import json
from collections import Counter
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fixture_universe import ADMITTED, company, serve_universe
from refresh_env import Env, use_cli
from support.engine_companies import decline_inputs, universe_deciles
from support.web import HEADER, HOST
from synthetic import SIX_LINES
from vendor_double import FIXTURES, FMP_KEY

from fairband import __main__ as cli
from fairband.config import DEFAULT_PORT, Settings
from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.route import reprice, value_company
from fairband.engine.types import Provenance
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.refresh import run_price
from fairband.refresh.inputs import build_inputs, latest_price
from fairband.refresh.run import Progress
from fairband.store.companies import insert_companies, latest_companies
from fairband.store.multiples import MultiplesRow, multiples_log_for
from fairband.store.observations import observations_for
from fairband.store.snapshots import SnapshotRow, insert_snapshot
from fairband.web.app import create_app
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER
from fairband.web.reviews_api import built_inputs

PRICE_DATE = date(2026, 10, 31)  # the new quotes' timestamp, a day after the fixtures'
NEW_PRICES = {"ACME": 20.0, "AXLE": 30.0, "KRON": 40.0, "MILD": 10.0, "NEWT": 60.0}
POLICY_CHANGED = "policy changed: run a revalue"
SETTINGS_CHANGED = "settings changed: run a revalue"
METHOD_CHANGED = "method changed: run a revalue"
AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
BELIEF = {
    "tag": "growth.belief",
    "new": 0.05,
    "reason": "guidance raised",
    "evidence": [{"kind": "transcript", "ref": "Q3 call", "note": ""}],
    "lifetime": "lasting",
}


def quote_rows(prices: dict[str, float], days: int = 1) -> list[dict[str, Any]]:
    """ACME's quote fixture for each symbol, at its price, stamped ``days`` later."""
    [row] = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text())
    later = row["timestamp"] + 86_400 * days
    return [row | {"symbol": s, "price": p, "timestamp": later} for s, p in prices.items()]


def serve_pair(env: Env, rate: float, days: int = 1) -> None:
    """USDSEK's quote at ``rate``, stamped as the companies' are: one pair, so one ``quote``
    call."""
    [row] = quote_rows({"USDSEK": rate}, days)
    env.router.symbol_bodies[("quote", "USDSEK")] = json.dumps([row]).encode()


def batch(prices: dict[str, float]) -> bytes:
    return json.dumps(quote_rows(prices)).encode()


def name_currencies(
    env: Env, currencies: dict[str, str], rates: dict[str, float] | None = None
) -> None:
    """Give each symbol a latest snapshot whose intermediates name its ``currency``: with its rate
    from ``rates``, its date and a differential of 0, as the engine names a foreign filer's (spec
    2026-11-10 7.2); without one, the code alone, as it names a row refused for its currency's own
    reason (fix round 1's ruling); a USD row's names none."""
    with closing(env.connect()) as conn:
        for symbol, currency in currencies.items():
            old = env.snapshot(symbol)
            named = {**old.result.intermediates, "currency": currency}
            if rates is not None and symbol in rates:
                named |= {
                    "fx_rate": rates[symbol],
                    "fx_date": "2026-10-30",
                    "inflation_differential": 0.0,
                }
            insert_snapshot(conn, replace(old.result, intermediates=named), 1, clock=env.clock)


def fx_responses(env: Env, after: int) -> list[tuple[str, str | None, str, int, bool]]:
    """The pair quote responses stored after response ``after``, as ``quote_responses`` reads
    the quotes."""
    with closing(env.connect()) as conn:
        rows = conn.execute(
            "SELECT endpoint, symbol, params, http_status, error FROM vendor_responses"
            " WHERE endpoint = 'fx-quote' AND id > ? ORDER BY id",
            (after,),
        ).fetchall()
    return [(r[0], r[1], r[2], r[3], r[4] is not None) for r in rows]


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


def test_price_refresh_keeps_value_updates_designation(env_valued: Env) -> None:
    env = env_valued
    before = snapshots_of(env)
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    serve_pair(env, 10.6)
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
    assert row.calibration == {"total": 5, "repriced": 5, "failed": 0, "skipped": 0}
    assert env.items(refresh_id) == [(symbol, "repriced", None) for symbol in ADMITTED]
    # One batch call for the five, never a call per symbol, and one quote of KRON's pair, USDSEK
    # (spec 2026-11-10 7.1); nothing else is fetched.
    assert env.router.calls == {"batch-quote": 1, "quote": 1}
    assert env.router.requested["batch-quote"] == {"symbols": "ACME,AXLE,KRON,MILD,NEWT"}
    assert quote_responses(env, stored_before) == [
        ("batch-quote", None, '{"symbols": "ACME,AXLE,KRON,MILD,NEWT"}', 200, False)
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
    assert (old.price, old.price_date, old.designation) == (50.0, date(2026, 10, 30), "well-above")
    assert (acme.price, acme.price_date, acme.designation) == (20.0, PRICE_DATE, "well-below")
    assert acme.value is not None and acme.price_to_value == 20.0 / acme.value
    assert acme.result.designation == acme.designation  # the column copies the result
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
    # $20 and $30 on $31.24 (0.64 and 0.96 × the value), $10 on $18.68 (0.54 ×); KRON's value in
    # SEK at the pair's new 10.6, a few dollars a share, far below $40
    assert {s: (r.price, r.designation) for s, r in after.items()} == {
        "ACME": (20.0, "well-below"),
        "AXLE": (30.0, "near"),
        "KRON": (40.0, "well-above"),
        "MILD": (10.0, "well-below"),
        "NEWT": (60.0, None),
    }
    # KRON's USD value moves with the rate: the value in SEK stays, ÷ the pair's quote
    kron, was = after["KRON"].result, before["KRON"].result
    assert kron.intermediates["value_in_currency"] == was.intermediates["value_in_currency"]
    assert (kron.intermediates["fx_rate"], kron.intermediates["fx_date"]) == (10.6, "2026-10-31")
    assert kron.value == pytest.approx(was.intermediates["value_in_currency"] / 10.6)
    assert was.value == pytest.approx(was.intermediates["value_in_currency"] / 10.52)
    [rate] = [i for i in kron.inputs if i.name == "fx_rate"]
    assert (rate.value, rate.unit, rate.provenance.as_of) == (10.6, "SEK per USD", PRICE_DATE)
    assert rate.provenance.observed_at == env.clock.now  # the pair quote's, not the history's
    assert rate.provenance.source == "FMP quote USDSEK"
    rates = {"fx_rate": 10.6, "fx_date": PRICE_DATE, "fx_observed_at": env.clock.now}
    assert kron == reprice(was, 40.0, PRICE_DATE, env.policy, **rates, **stamps)

    assert list(dict.fromkeys(p.stage for p in env.progress)) == [
        "quotes",
        "fx",
        "reprice",
        "done",
    ]
    assert [p for p in env.progress if p.stage in ("quotes", "fx", "done")] == [
        Progress(refresh_id, "quotes", 0, 0, 5, None),
        Progress(refresh_id, "quotes", 5, 0, 0, None),
        Progress(refresh_id, "fx", 0, 0, 1, None),
        Progress(refresh_id, "fx", 1, 0, 0, None),
        Progress(refresh_id, "done", 5, 0, 0, None),
    ]
    assert Progress(refresh_id, "reprice", 5, 0, 0, None) in env.progress


def test_a_reprice_logs_the_multiples_of_the_day(env_valued: Env) -> None:
    """Each repriced snapshot logs its multiples at the quote's price, as of the quote's date, in
    the snapshot's transaction; a second price refresh the same day replaces the day's row. NEWT's
    refusal logs its price and no multiple."""
    env = env_valued
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    first = env.refresh().run("price")
    later = {symbol: price + 1.0 for symbol, price in NEW_PRICES.items()}
    env.router.bodies["batch-quote"] = batch(later)
    env.clock.now += timedelta(hours=1)
    second = env.refresh().run("price")
    assert env.last().status == "done" and second == first + 1
    with closing(env.connect()) as conn:
        logged = {symbol: multiples_log_for(conn, symbol) for symbol in ADMITTED}
        days = conn.execute(
            "SELECT symbol, refresh_id FROM multiples_log WHERE day = ? ORDER BY symbol",
            (PRICE_DATE.isoformat(),),
        ).fetchall()
    assert [tuple(row) for row in days] == [(symbol, second) for symbol in ADMITTED]
    for symbol in ADMITTED:
        snapshot = env.snapshot(symbol)
        multiples = snapshot.result.intermediates.get("multiples", {})
        full, repriced = logged[symbol]  # the full refresh's day, then the quote's
        assert full.day == date(2026, 10, 30) and full.price == 50.0, symbol
        assert repriced == MultiplesRow(
            PRICE_DATE,
            later[symbol],
            multiples.get("pe_reported"),
            multiples.get("pe_clean"),
            multiples.get("pe_forward"),
            snapshot.id,
        ), symbol
    acme = logged["ACME"][1]
    assert acme.pe_forward is not None and acme.pe_forward < logged["ACME"][0].pe_forward
    assert logged["NEWT"][1].pe_reported is None and logged["NEWT"][1].pe_forward is None


def test_a_reprice_with_a_multiple_replaces_the_old_figure(env_valued: Env) -> None:
    """A quote of the full refresh's own day: the reprice's figures replace that day's, one row a
    company; NEWT's refusal has none to give, and its row keeps none."""
    env = env_valued
    with closing(env.connect()) as conn:
        before = {symbol: multiples_log_for(conn, symbol) for symbol in ADMITTED}
    [row] = json.loads((FIXTURES / "fmp" / "quote.ACME.json").read_text())
    same_day = [row | {"symbol": s, "price": p} for s, p in NEW_PRICES.items()]
    env.router.bodies["batch-quote"] = json.dumps(same_day).encode()
    refresh_id = env.refresh().run("price")
    assert env.last().status == "done"
    with closing(env.connect()) as conn:
        after = {symbol: multiples_log_for(conn, symbol) for symbol in ADMITTED}
        refreshes = {r[0] for r in conn.execute("SELECT refresh_id FROM multiples_log")}
    assert refreshes == {refresh_id}
    for symbol in ADMITTED:
        snapshot = env.snapshot(symbol)
        assert snapshot.price_date == date(2026, 10, 30), symbol
        [old], [new] = before[symbol], after[symbol]
        assert (old.day, new.day, new.price, new.snapshot_id) == (
            date(2026, 10, 30),
            date(2026, 10, 30),
            NEW_PRICES[symbol],
            snapshot.id,
        ), symbol
    acme_old, acme_new = before["ACME"][0], after["ACME"][0]
    assert acme_old.pe_forward is not None and acme_new.pe_forward is not None
    assert acme_new.pe_forward == pytest.approx(acme_old.pe_forward * 20.0 / 50.0)
    assert after["NEWT"][0].pe_forward is None and after["NEWT"][0].pe_reported is None


def test_price_refresh_runs_no_backfill(env_valued: Env) -> None:
    """A price refresh values nothing, so it does not backfill: the store as it was before the
    normalizer kept the six lines stays so."""
    env = env_valued
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    lines = ", ".join(f"'{field}'" for field in SIX_LINES)
    with closing(env.connect()) as conn, conn:
        conn.execute(f"DELETE FROM facts WHERE field IN ({lines})")
    env.refresh().run("price")
    assert env.last().status == "done"
    assert "backfill" not in {p.stage for p in env.progress}
    with closing(env.connect()) as conn:
        count = conn.execute(f"SELECT count(*) FROM facts WHERE field IN ({lines})").fetchone()
    assert count[0] == 0


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
        {"total": 6, "repriced": 5, "failed": 0, "skipped": 1},
    )
    assert env.router.requested["batch-quote"] == {"symbols": "ACME,AXLE,KRON,MILD,NEWT"}
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
    assert (newt.value, newt.price_to_value, newt.designation, newt.refusal) == (
        None,
        None,
        None,
        "no target margin: 0 mature peers",
    )
    assert "revenue_path" in newt.result.intermediates
    assert newt.result.intermediates["implied_margin"] is None
    assert [s for s, _, _ in env.snapshots()].count("ZERO") == 0


def test_price_refresh_reprices_a_decline_row(env_valued: Env) -> None:
    """A Decline row (spec 2026-11-06 13.1: $4.9533 a share, valued at $3.00, "below": 0.606 × the
    value, over its None class's buy level at 0.60 ×) reprices from its stored intermediates
    alone: the value and the levels stay; the designation ("near" at $4.60), the implied decline
    rate, the multiples and the expected return move to the quote, as the engine's ``reprice``
    moves them."""
    env = env_valued
    decline = value_company(decline_inputs(), universe_deciles(), env.policy, date(2026, 10, 31))
    assert (decline.route, decline.designation) == ("decline", "below")
    with closing(env.connect()) as conn:
        acme = next(c for c in latest_companies(conn) if c.symbol == "ACME")
        insert_companies(conn, [replace(acme, symbol="DCCO", name="Decline Co")])
        insert_snapshot(conn, decline, 1, clock=env.clock)
    env.router.bodies["batch-quote"] = batch(NEW_PRICES | {"DCCO": 4.6})

    refresh_id = env.refresh().run("price")

    assert env.last().calibration == {"total": 6, "repriced": 6, "failed": 0, "skipped": 0}
    dcco = env.snapshot("DCCO")
    assert (dcco.refresh_id, dcco.route, dcco.price, dcco.designation) == (
        refresh_id,
        "decline",
        4.6,
        "near",
    )
    assert decline.levels is not None
    assert (dcco.value, dcco.buy_level, dcco.trim_level) == (
        decline.value,
        decline.levels.buy,
        decline.levels.trim,
    )
    now = env.clock.now
    assert dcco.result == reprice(
        decline, 4.6, PRICE_DATE, env.policy, observed_at=now, entered_at=now
    )
    moved = dcco.result.intermediates["implied_decline_rate"]
    assert moved is not None and moved != decline.intermediates["implied_decline_rate"]


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
    serve_pair(env, 10.6)
    stored_before = last_response_id(env)

    refresh_id = env.refresh().run("price")

    row = env.last()
    assert (row.status, row.message, row.calibration) == (
        "done",
        None,
        {"total": 5, "repriced": 4, "failed": 1, "skipped": 0},
    )
    assert env.router.calls == {"batch-quote": 1, "quote": 6}  # the five, then USDSEK
    assert quote_responses(env, stored_before) == [
        ("batch-quote", None, '{"symbols": "ACME,AXLE,KRON,MILD,NEWT"}', 402, True),
        ("quote", "ACME", '{"symbol": "ACME"}', 200, False),
        ("quote", "AXLE", '{"symbol": "AXLE"}', 200, False),
        ("quote", "KRON", '{"symbol": "KRON"}', 200, False),
        ("quote", "MILD", '{"symbol": "MILD"}', 200, False),
        ("quote", "NEWT", '{"symbol": "NEWT"}', 402, True),
    ]
    items = env.items(refresh_id)
    repriced = ("ACME", "AXLE", "KRON", "MILD")
    assert items[:4] == [(symbol, "repriced", None) for symbol in repriced]
    symbol, status, reason = items[4]
    assert (symbol, status) == ("NEWT", "failed")
    assert reason is not None and reason.startswith("quote failed: VendorError: GET ")
    assert "402" in reason and FMP_KEY not in reason
    after = snapshots_of(env)
    assert {s: r.price for s, r in after.items()} == {
        "ACME": 20.0,
        "AXLE": 30.0,
        "KRON": 40.0,
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
        {"total": 5, "repriced": 4, "failed": 1, "skipped": 0},
    )
    assert env.items(refresh_id) == [
        ("ACME", "failed", POLICY_CHANGED),
        ("AXLE", "repriced", None),
        ("KRON", "repriced", None),
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
        {"total": 5, "repriced": 4, "failed": 1, "skipped": 0},
    )
    assert env.items(refresh_id) == [
        ("ACME", "repriced", None),
        ("AXLE", "failed", METHOD_CHANGED),
        ("KRON", "repriced", None),
        ("MILD", "repriced", None),
        ("NEWT", "repriced", None),
    ]
    assert env.snapshot("AXLE") == axle
    assert (env.snapshot("MILD").refresh_id, env.snapshot("MILD").price) == (refresh_id, 10.0)


def test_price_refresh_refuses_another_settings_hash_and_reprices_the_empty_one(
    env_valued: Env,
) -> None:
    """ACME's latest snapshot was valued under other settings: its value and levels come from
    them, so it takes a revalue and keeps its snapshot. The others carry the empty overlay's hash,
    as every snapshot valued before the overlay existed does, and the overlay is empty: they
    reprice, under the same hash."""
    env = env_valued
    assert env.policy.settings_hash == EMPTY_SETTINGS_HASH
    with closing(env.connect()) as conn, conn:
        conn.execute(
            "UPDATE snapshots SET settings_hash = 'other',"
            " result = json_set(result, '$.settings_hash', 'other') WHERE id = ?",
            (env.snapshot("ACME").id,),
        )
    acme = env.snapshot("ACME")
    assert acme.settings_hash == acme.result.settings_hash == "other"
    others = ("AXLE", "KRON", "MILD", "NEWT")
    assert {env.snapshot(symbol).settings_hash for symbol in others} == {EMPTY_SETTINGS_HASH}
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)

    refresh_id = env.refresh().run("price")

    assert (env.last().status, env.last().calibration) == (
        "done",
        {"total": 5, "repriced": 4, "failed": 1, "skipped": 0},
    )
    assert env.items(refresh_id) == [
        ("ACME", "failed", SETTINGS_CHANGED),
        ("AXLE", "repriced", None),
        ("KRON", "repriced", None),
        ("MILD", "repriced", None),
        ("NEWT", "repriced", None),
    ]
    assert env.snapshot("ACME") == acme
    for symbol in others:
        row = env.snapshot(symbol)
        assert (row.refresh_id, row.price) == (refresh_id, NEW_PRICES[symbol])
        assert row.settings_hash == row.result.settings_hash == EMPTY_SETTINGS_HASH


def test_a_price_refresh_after_a_changed_threshold_stores_the_levels_in_force(
    env_valued: Env,
) -> None:
    """The margin of safety, the fair band and the trim multiple are in no settings hash (spec
    2026-11-23 thresholds 5.3), so a price refresh reprices a snapshot valued before a change of
    one. The snapshot it writes holds the levels of the policy in force, on which its word is
    read: the stored levels and the stored word agree, and no value moves."""
    env = env_valued
    before = snapshots_of(env)
    env.policy = replace(
        env.policy,
        margin_of_safety={"None": 0.45, "Narrow": 0.35, "Wide": 0.15},
        fair_band=(0.95, 1.05),
        trim_multiple=1.2,
    )
    assert env.policy.settings_hash == EMPTY_SETTINGS_HASH
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    serve_pair(env, 10.6)

    env.refresh().run("price")

    assert env.last().calibration == {"total": 5, "repriced": 5, "failed": 0, "skipped": 0}
    moved = []
    for symbol, row in snapshots_of(env).items():
        old = before[symbol]
        if row.value is None or symbol == "KRON":  # a refusal has no levels; KRON moves at its rate
            continue
        moat = row.result.intermediates["moat"]
        levels = levels_for(row.value, moat, env.policy)
        assert row.value == old.value
        assert (row.buy_level, row.fair_low, row.fair_high, row.trim_level) == (
            levels.buy,
            levels.fair_low,
            levels.fair_high,
            levels.trim,
        )
        assert row.result.levels == levels and row.price is not None
        assert (row.price_to_value, row.designation) == designation_for(
            row.price, row.value, env.policy.edges_for(moat)
        )
        moved.append(row.trim_level != old.trim_level)
    assert moved and all(moved)


def test_price_refresh_checks_the_policy_then_the_settings_then_the_method(
    env_valued: Env,
) -> None:
    """A snapshot unlike the current run on several counts reads the first: the policy version,
    then the settings hash, then the method version."""
    env = env_valued
    stale = {
        "ACME": {"policy_version": "fairband-policy-v0", "settings_hash": "other"},
        "AXLE": {"settings_hash": "other", "method_version": "fairband-mechanical/0.1"},
        "MILD": {"method_version": "fairband-mechanical/0.1"},
    }
    with closing(env.connect()) as conn:
        for symbol, fields in stale.items():
            old = env.snapshot(symbol)
            insert_snapshot(conn, replace(old.result, **fields), old.refresh_id, clock=env.clock)
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)

    refresh_id = env.refresh().run("price")

    assert env.items(refresh_id) == [
        ("ACME", "failed", POLICY_CHANGED),
        ("AXLE", "failed", SETTINGS_CHANGED),
        ("KRON", "repriced", None),
        ("MILD", "failed", METHOD_CHANGED),
        ("NEWT", "repriced", None),
    ]


def test_price_refresh_rate_limited(env_valued: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """One symbol a call, so the 429 lands on MILD: the quotes stop there, the symbols quoted
    before it are repriced, NEWT is never reached and the run fails saying so, quoting no pair."""
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
        "rate limited by FMP: stopped after 4 companies",
        None,
    )
    assert env.items(refresh_id) == [
        ("ACME", "repriced", None),
        ("AXLE", "repriced", None),
        ("KRON", "repriced", None),
        ("MILD", "failed", "quote incomplete: rate limited"),
        ("NEWT", "pending", None),
    ]
    # MILD's three tries (the client retries a 429), then nothing: NEWT is never asked for, nor
    # is any pair (the fx stage does not run after a 429).
    assert env.router.symbol_calls == Counter({"ACME": 1, "AXLE": 1, "KRON": 1, "MILD": 3})
    assert "fx" not in {p.stage for p in env.progress}
    after = snapshots_of(env)
    assert {s: r.refresh_id for s, r in after.items()} == {
        "ACME": refresh_id,
        "AXLE": refresh_id,
        "KRON": refresh_id,
        "MILD": 1,
        "NEWT": 1,
    }
    assert after["MILD"] == before["MILD"] and after["NEWT"] == before["NEWT"]


def test_the_fx_stage_quotes_the_pairs_of_the_snapshots_currencies(env_valued: Env) -> None:
    """Spec 2026-11-10 7.1: between the quotes and the reprice, one ``batch-quote`` call for the
    pairs of the quoted companies' currencies (their latest snapshots' ``currency``, USD left
    out, and a currency named without a rate left out), stored as the quote stage stores a batch:
    under the endpoint ``fx-quote``, no symbol, the pairs as its params, and one ``fx-quote``
    observation a pair, at the quote's price and date. KRON, valued in SEK, reprices at its pair's
    quote, and NEWT, made to carry a TWD rate, at TWD's; MILD, whose snapshot is made to name ARS
    without a rate as a row refused for its currency names it (fix round 1), quotes no pair, reads
    no rate and reprices as before."""
    env = env_valued
    name_currencies(
        env, {"KRON": "SEK", "MILD": "ARS", "NEWT": "TWD", "ACME": "USD"}, rates={"NEWT": 32.0}
    )
    before = snapshots_of(env)
    [stamp] = {row["timestamp"] for row in quote_rows(NEW_PRICES)}
    pairs = [
        {"symbol": "USDSEK", "price": 10.7, "timestamp": stamp},
        {"symbol": "USDTWD", "price": 32.5, "timestamp": stamp},
    ]
    # One body for both calls: each reads the rows it asked for.
    env.router.bodies["batch-quote"] = json.dumps(quote_rows(NEW_PRICES) + pairs).encode()
    stored_before = last_response_id(env)

    refresh_id = env.refresh().run("price")

    row = env.last()
    assert (row.status, row.calibration) == (
        "done",
        {"total": 5, "repriced": 5, "failed": 0, "skipped": 0},
    )
    assert env.router.calls == {"batch-quote": 2}  # the companies', then the pairs'
    assert env.router.requested["batch-quote"] == {"symbols": "USDSEK,USDTWD"}
    assert fx_responses(env, stored_before) == [
        ("fx-quote", None, '{"symbols": "USDSEK,USDTWD"}', 200, False)
    ]
    with closing(env.connect()) as conn:
        stored = {
            pair: [
                (r.symbol, r.period, r.field, r.value, r.unit, r.as_of)
                for r in observations_for(conn, pair, "fx-quote")
            ]
            for pair in ("USDSEK", "USDTWD")
        }
    assert stored == {
        "USDSEK": [("USDSEK", PRICE_DATE, "price", Decimal("10.7"), None, PRICE_DATE)],
        "USDTWD": [("USDTWD", PRICE_DATE, "price", Decimal("32.5"), None, PRICE_DATE)],
    }
    assert [p for p in env.progress if p.stage == "fx"] == [
        Progress(refresh_id, "fx", 0, 0, 2, None),
        Progress(refresh_id, "fx", 2, 0, 0, None),
    ]
    now = env.clock.now
    mild = env.snapshot("MILD")
    assert mild.result == reprice(
        before["MILD"].result, 10.0, PRICE_DATE, env.policy, observed_at=now, entered_at=now
    )
    assert "fx_rate" not in mild.result.intermediates  # named ARS, never read as rated
    kron, was = env.snapshot("KRON").result, before["KRON"].result
    assert kron.value == pytest.approx(was.intermediates["value_in_currency"] / 10.7)
    assert kron.intermediates["fx_rate"] == 10.7
    assert env.snapshot("NEWT").result.intermediates["fx_rate"] == 32.5


def test_a_failed_pair_quote_fails_no_company(env_valued: Env) -> None:
    """One pair, so one ``quote`` call for USDSEK, under the pair as its symbol; it fails, and
    the run still ends done with every company repriced: a pair's failure is its own. KRON
    reprices at the rate its snapshot holds, 10.52 of 2026-10-30, a day before the price date, so
    not stale."""
    env = env_valued
    before = env.snapshot("KRON").result
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    env.router.fail_once[("quote", "USDSEK")] = env.policy.refresh.attempts
    stored_before = last_response_id(env)

    refresh_id = env.refresh().run("price")

    row = env.last()
    assert (row.status, row.message, row.calibration) == (
        "done",
        None,
        {"total": 5, "repriced": 5, "failed": 0, "skipped": 0},
    )
    assert env.router.calls == {"batch-quote": 1, "quote": env.policy.refresh.attempts}
    assert fx_responses(env, stored_before) == [
        ("fx-quote", "USDSEK", '{"symbol": "USDSEK"}', 500, True)
    ]
    assert env.items(refresh_id) == [(symbol, "repriced", None) for symbol in ADMITTED]
    assert [p for p in env.progress if p.stage == "fx"] == [
        Progress(refresh_id, "fx", 0, 0, 1, None),
        Progress(refresh_id, "fx", 0, 1, 0, None),
    ]
    with closing(env.connect()) as conn:
        assert observations_for(conn, "USDSEK", "fx-quote") == []
    kron = env.snapshot("KRON").result
    assert (kron.value, kron.levels, kron.intermediates["fx_rate"]) == (
        before.value,
        before.levels,
        10.52,
    )
    assert "fx-stale" not in [f.code for f in kron.flags]


def test_a_pair_quote_that_is_no_rate_reprices_at_the_stored_rate(env_valued: Env) -> None:
    """USDSEK answers the numeric string "1e400": a finite decimal the store keeps, but no float,
    so no rate (spec 2026-11-10 7.1). KRON reprices at the rate its snapshot holds, as for a
    failed pair, and is not marked "reprice failed"."""
    env = env_valued
    before = env.snapshot("KRON").result
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    [row] = quote_rows({"USDSEK": 1.0})
    huge = json.dumps([row | {"price": "1e400"}]).encode()
    env.router.symbol_bodies[("quote", "USDSEK")] = huge

    refresh_id = env.refresh().run("price")

    assert env.last().calibration == {"total": 5, "repriced": 5, "failed": 0, "skipped": 0}
    assert ("KRON", "repriced", None) in env.items(refresh_id)
    kron = env.snapshot("KRON").result
    assert (kron.price, kron.value, kron.intermediates["fx_rate"]) == (40.0, before.value, 10.52)


def test_a_failed_pair_quote_past_the_bound_notes_a_stale_rate(env_valued: Env) -> None:
    """Quotes nine days after the full refresh's, and USDSEK's quote fails: KRON reprices at the
    rate it holds, 10.52 of 2026-10-30, now more than ``fx_stale_days`` (7) before the price date,
    so its row carries ``fx-stale``, naming both dates (spec 2026-11-10 7.1)."""
    env = env_valued
    before = env.snapshot("KRON").result
    env.router.bodies["batch-quote"] = json.dumps(quote_rows(NEW_PRICES, days=9)).encode()
    env.router.fail_once[("quote", "USDSEK")] = env.policy.refresh.attempts

    env.refresh().run("price")

    kron = env.snapshot("KRON").result
    assert kron.price_date == date(2026, 11, 8) and kron.value == before.value
    [stale] = [f for f in kron.flags if f.code == "fx-stale"]
    assert stale.sentence == (
        "The newest close of USDSEK on file is of 2026-10-30, 9 days before the price date "
        "2026-11-08."
    )


def _override_answer(env: Env, symbol: str) -> tuple[int, Any]:
    """An agent's growth.belief override of ``symbol`` posted to the app over the env's store: its
    status and its answer."""
    settings = Settings(env.db_path.parent, env.db_path.parent, env.db_path, DEFAULT_PORT)
    app = create_app(settings, env.policy, env.connect, clock=env.clock, tax=env.tax)
    with TestClient(app, base_url=HOST) as client:
        r = client.post(f"/api/companies/{symbol}/overrides", json=BELIEF, headers=AGENT)
    return r.status_code, r.json()


def test_a_pair_quote_dated_after_the_price_date_reprices_a_snapshot_that_reproduces(
    env_valued: Env,
) -> None:
    """Between 00:00 UTC and the US open the pair's quote is dated today while the stocks' last
    trade is dated yesterday: here USDSEK's 10.6 is stamped 2026-11-01, a day after the stocks'
    2026-10-31. KRON reprices at the pair's quote (spec 2026-11-10 7.1), while the store's rate
    at its price date is still the history's 10.52 of 2026-10-30. The rate is snapshot data, as
    the price is: the rebuild an override checks reproduction on values at the snapshot's own
    rate and its date, so the snapshot reproduces and the override posts, no 409."""
    env = env_valued
    env.router.bodies["batch-quote"] = batch(NEW_PRICES)
    serve_pair(env, 10.6, days=2)
    env.refresh().run("price")
    snapshot = env.snapshot("KRON")
    im = snapshot.result.intermediates
    assert (snapshot.price_date, im["fx_rate"], im["fx_date"]) == (PRICE_DATE, 10.6, "2026-11-01")
    today = env.clock().date()
    with closing(env.connect()) as conn:
        assert build_inputs(conn, "KRON", env.policy, env.tax, today).fx_rate == 10.52
        inputs, deciles = built_inputs(conn, snapshot, env.policy, env.tax, today)
    assert (inputs.fx_rate, inputs.fx_date, inputs.fx_stale) == (10.6, date(2026, 11, 1), False)
    assert value_company(inputs, deciles, env.policy, today).value == snapshot.value
    status, body = _override_answer(env, "KRON")
    assert status == 201, body
    assert body["override"]["state"] == "applied"
    assert body["review"]["mechanicalValue"] == snapshot.value


def test_a_scoped_refresh_of_a_currency_mate_leaves_a_snapshot_reproducing(
    env_valued: Env,
) -> None:
    """AXLE now reports in SEK, as KRON does, and USDSEK's history has moved its close of
    2026-10-30, the day KRON was valued at, from 10.52 to 10.40. A scoped refresh of AXLE fetches
    the pair's history again; KRON's snapshot still reproduces, at its own rate, and an override
    of KRON posts."""
    env = env_valued
    for endpoint, body in company("KRON").items():
        env.router.symbol_bodies[(endpoint, "AXLE")] = body.replace(b"KRON", b"AXLE")
    history = json.loads((FIXTURES / "fmp" / "historical-price-eod-light.USDSEK.json").read_text())
    moved = [r | {"price": 10.40} if r["date"] == "2026-10-30" else r for r in history]
    env.router.symbol_bodies[("fx-history", "USDSEK")] = json.dumps(moved).encode()
    valued = env.snapshot("KRON")
    assert valued.result.intermediates["fx_rate"] == 10.52

    env.run(["AXLE"])

    assert env.router.calls["fx-history"] == 1
    assert env.snapshot("AXLE").result.intermediates["currency"] == "SEK"
    today = env.clock().date()
    with closing(env.connect()) as conn:
        assert build_inputs(conn, "KRON", env.policy, env.tax, today).fx_rate == 10.40
        inputs, _ = built_inputs(conn, valued, env.policy, env.tax, today)
    assert (inputs.fx_rate, inputs.fx_date) == (10.52, date(2026, 10, 30))
    status, body = _override_answer(env, "KRON")
    assert status == 201, body
    assert body["review"]["mechanicalValue"] == valued.value


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
    serve_pair(env, 10.6)
    assert cli.main(["refresh", "--kind", "price"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "quotes: 0 done, 0 failed, 5 to go",
        "quotes: 5 done, 0 failed, 0 to go",
        "fx: 0 done, 0 failed, 1 to go",
        "fx: 1 done, 0 failed, 0 to go",
        "reprice: 0 done, 0 failed, 5 to go",
        "reprice: 1 done, 0 failed, 4 to go",
        "reprice: 2 done, 0 failed, 3 to go",
        "reprice: 3 done, 0 failed, 2 to go",
        "reprice: 4 done, 0 failed, 1 to go",
        "reprice: 5 done, 0 failed, 0 to go",
        "done: 5 done, 0 failed, 0 to go",
        "refresh 2: done · 5 repriced, 0 failed, 0 skipped",
    ]
    assert env.snapshot("ACME").price == 20.0
