"""The full refresh over the six listings of ``fixture_universe`` and a migrated temporary database
that holds no universe yet: the universe, the fetch, the deciles, the values and the calibration;
the stops and the rerun that continues; the server's worker and the marking of a refresh a stop
left running.
"""

import json
import logging
import threading
import time
from collections import Counter
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fixture_universe import ADMITTED, SCREENER, serve_universe
from refresh_env import Env, use_cli
from vendor_double import FMP_KEY

from fairband import __main__ as cli
from fairband.config import DEFAULT_PORT, Settings
from fairband.engine import METHOD_VERSION
from fairband.engine.classifier import Deciles
from fairband.refresh import run as run_module
from fairband.refresh.deciles import deciles_for_universe
from fairband.refresh.run import Progress, Refresh
from fairband.refresh.worker import RefreshWorker
from fairband.store.companies import latest_companies
from fairband.store.policy import record_policy
from fairband.store.refreshes import (
    RefreshRunning,
    create_refresh,
    current_refresh,
    latest_deciles,
)
from fairband.vendors.http import VendorError
from fairband.web.app import create_app

RATE_LIMITED = "data fetch incomplete: rate limited"
# NEWT is Young Growth: its peers list (ACME's, the symbol changed) names no mature company of the
# fixture universe, so the revenue-growth route has no target margin.
NO_TARGET = "no target margin: 0 mature peers"
FOREIGN = "foreign filer: currency and share-unit handling not built yet"
# The fixture universe's calibration: ACME, AXLE and MILD valued, NEWT refused. Every company
# carries a flag (the synthetic company has no leases on its balance sheet, among others), but
# only ACME, AXLE (margin direction) and NEWT (growth word, free cash flow) are flagged by a
# classifier check. NEWT's refusal for its target margin keeps the flags of its revenue path (the
# annual consensus has no revenue for a path year, so the path holds) and of its capital build.
CALIBRATION = {
    "total": 4,
    "valued": 3,
    "refused": {NO_TARGET: 1},
    "phases": {
        "Start-up": 0,
        "Young Growth": 1,
        "High Growth": 0,
        "Mature Growth": 2,
        "Mature Stable": 1,
        "Decline": 0,
        "unclassified": 0,
    },
    "flagged": 3,
    "flags": {
        "fcf-sign": 1,
        "growth-word-disagrees": 1,
        "large-nri": 3,
        "leases-not-on-balance-sheet": 4,
        "line-not-presented:current_lease_liability": 4,
        "line-not-presented:goodwill": 4,
        "line-not-presented:lease_rou_asset": 4,
        "margin-direction-disagrees": 2,
        "path-held": 1,
        "path-on-eps": 2,
        "sbc-basis-unknown": 2,
        "value-spread": 2,
    },
    "universe": {
        "admitted": 4,
        "excluded": {
            "industry": 1,
            "name pattern": 0,
            "symbol pattern": 0,
            "manual exclusion": 0,
            "skipped": 1,
        },
    },
}


@pytest.fixture
def env_fixture_universe(env_without_universe: Env) -> Env:
    serve_universe(env_without_universe.router)
    return env_without_universe


def deciles(env: Env) -> Deciles | None:
    with closing(env.connect()) as conn:
        return latest_deciles(conn)


def universe(env: Env) -> dict[str, tuple[int, bool]]:
    """The latest universe: each listing recorded, with its refresh and whether it is admitted."""
    with closing(env.connect()) as conn:
        rows = latest_companies(conn, eligible_only=False)
    return {c.symbol: (c.refresh_id, c.eligible) for c in rows}


def test_full_refresh_builds_universe_deciles_and_values(env_fixture_universe: Env) -> None:
    env = env_fixture_universe
    refresh_id = env.refresh().run("full")
    row = env.last()
    assert (row.id, row.kind, row.symbols, row.status, row.stage, row.message) == (
        refresh_id,
        "full",
        None,
        "done",
        "done",
        None,
    )
    assert universe(env) == {
        "ACME": (refresh_id, True),
        "AXLE": (refresh_id, True),
        "FIRB": (refresh_id, False),
        "MILD": (refresh_id, True),
        "NEWT": (refresh_id, True),
    }
    saved = deciles(env)
    assert saved is not None
    # Every admitted company ranks on growth; NEWT's negative margin keeps it off the margin slope.
    assert (saved.refresh_id, saved.n_growth, saved.n_margin) == (refresh_id, 4, 3)

    assert env.items(refresh_id) == [(symbol, "valued", None) for symbol in ADMITTED]
    snapshots = {symbol: env.snapshot(symbol) for symbol in ADMITTED}
    assert {
        s: (row.refresh_id, row.deciles_refresh_id) for s, row in snapshots.items()
    } == dict.fromkeys(ADMITTED, (refresh_id, refresh_id))
    assert {s: row.phase for s, row in snapshots.items()} == {
        "ACME": "Mature Growth",
        "AXLE": "Mature Growth",
        "MILD": "Mature Stable",
        "NEWT": "Young Growth",
    }
    for symbol, route in (
        ("ACME", "mature-growth"),
        ("AXLE", "mature-growth"),
        ("MILD", "mature-stable"),
    ):
        valued = snapshots[symbol]
        assert valued.route == route and valued.refusal is None
        assert valued.value is not None and valued.value > 0
    assert snapshots["NEWT"].refusal == NO_TARGET and snapshots["NEWT"].value is None

    calibration = row.calibration
    assert calibration == CALIBRATION
    assert sum(calibration["phases"].values()) == calibration["total"]
    assert calibration["valued"] + sum(calibration["refused"].values()) == calibration["total"]

    assert list(dict.fromkeys(p.stage for p in env.progress)) == [
        "universe",
        "fetch",
        "deciles",
        "value",
        "done",
    ]
    assert [p for p in env.progress if p.stage in ("universe", "deciles", "done")] == [
        Progress(refresh_id, "universe", 0, 0, 0, None),
        Progress(refresh_id, "universe", 4, 0, 0, None),
        Progress(refresh_id, "deciles", 0, 0, 4, None),
        Progress(refresh_id, "deciles", 4, 0, 0, None),
        Progress(refresh_id, "done", 4, 0, 0, None),
    ]
    assert env.router.calls["screener"] == 1
    assert set(env.router.symbol_calls) == {"", *ADMITTED}  # FIRB and TINY are never fetched


def test_rerun_after_cancel_continues(env_fixture_universe: Env) -> None:
    """The cancel lands after two companies are fetched: no deciles and no values, since the
    deciles need the whole universe. The rerun is a new refresh: it rebuilds the universe from the
    screener response of the hour before, reuses the two fetched companies and fetches the rest."""
    env = env_fixture_universe
    cancel = threading.Event()

    def stop_after_two(progress: Progress) -> None:
        if progress.stage == "fetch" and progress.done + progress.failed == 2:
            cancel.set()

    first = env.refresh(workers=1, cancel=cancel, then=stop_after_two).run("full")
    row = env.last()
    assert (row.id, row.status, row.stage, row.calibration) == (first, "cancelled", "fetch", None)
    assert env.items(first) == [
        ("ACME", "fetched", None),
        ("AXLE", "fetched", None),
        ("MILD", "pending", None),
        ("NEWT", "pending", None),
    ]
    assert deciles(env) is None and env.snapshots() == []
    assert env.router.symbol_calls == Counter({"": 1, "ACME": 15, "AXLE": 15})

    env.router.symbol_calls.clear()
    env.progress.clear()
    env.clock.now += timedelta(hours=1)
    second = env.refresh().run("full")
    row = env.last()
    assert (row.id, row.status) == (second, "done") and second == first + 1
    assert env.router.symbol_calls == Counter({"MILD": 15, "NEWT": 15})  # no screener call
    assert Progress(second, "fetch", 4, 0, 0, None) in env.progress
    assert env.items(second) == [(symbol, "valued", None) for symbol in ADMITTED]
    assert {refresh for refresh, _ in universe(env).values()} == {second}
    saved = deciles(env)
    assert saved is not None and saved.refresh_id == second
    assert sorted(env.snapshots()) == sorted(
        (symbol, second, env.snapshot(symbol).refusal) for symbol in ADMITTED
    )
    assert row.calibration is not None and row.calibration["total"] == 4


@pytest.mark.parametrize(
    ("status", "body", "error", "message"),
    [
        (403, None, VendorError, "VendorError: "),
        (200, b"[]", ValueError, "ValueError: screener returned no rows"),
    ],
)
def test_full_refresh_screener_failure_finishes_failed(
    env_fixture_universe: Env,
    status: int,
    body: bytes | None,
    error: type[Exception],
    message: str,
) -> None:
    env = env_fixture_universe
    if body is None:
        env.router.fail.add("screener")
        env.router.fail_status = status
    else:
        env.router.bodies["screener"] = body
    with pytest.raises(error):
        env.refresh().run("full")
    row = env.last()
    assert (row.status, row.stage, row.finished_at, row.calibration) == (
        "failed",
        "universe",
        env.clock.now,
        None,
    )
    assert row.message is not None and row.message.startswith(message)
    assert FMP_KEY not in row.message
    assert universe(env) == {} and deciles(env) is None and env.snapshots() == []
    assert set(env.router.symbol_calls) == {""}  # no company is fetched
    with closing(env.connect()) as conn:
        assert current_refresh(conn) is None


def test_full_refresh_rate_limited_saves_no_deciles(env_fixture_universe: Env) -> None:
    """As in a scoped refresh, a 429 stops the fetch and what was fetched is valued, here with no
    deciles stored: the run saves none from part of the universe."""
    env = env_fixture_universe
    env.router.fail_status = 429
    env.router.fail_symbols.add("MILD")
    refresh_id = env.refresh(workers=1).run("full")
    row = env.last()
    assert (row.status, row.message, row.calibration) == (
        "failed",
        "rate limited by FMP: stopped after 3 companies",
        None,
    )
    assert deciles(env) is None
    assert env.items(refresh_id) == [
        ("ACME", "valued", None),
        ("AXLE", "valued", None),
        ("MILD", "failed", RATE_LIMITED),
        ("NEWT", "pending", None),
    ]
    assert sorted(env.snapshots()) == [
        ("ACME", refresh_id, "no universe deciles yet"),
        ("AXLE", refresh_id, "no universe deciles yet"),
        ("MILD", refresh_id, RATE_LIMITED),
    ]


def test_full_refresh_admitting_no_company_fails(env_fixture_universe: Env) -> None:
    """A screener that admits no company ends the refresh failed before any fetch, with no
    deciles saved: the last good universe's deciles stay the ones a scoped refresh uses."""
    env = env_fixture_universe
    first = env.refresh().run("full")
    env.clock.now += timedelta(hours=25)  # past the screener's reuse
    env.router.bodies["screener"] = json.dumps([SCREENER[1], SCREENER[3]]).encode()  # FIRB, TINY
    env.router.symbol_calls.clear()
    second = env.refresh().run("full")
    row = env.last()
    assert (row.id, row.status, row.stage, row.message, row.calibration) == (
        second,
        "failed",
        "universe",
        "universe admitted no company",
        None,
    )
    assert set(env.router.symbol_calls) == {""} and env.items(second) == []
    saved = deciles(env)
    assert saved is not None and saved.refresh_id == first

    env.run(["ACME"])
    acme = env.snapshot("ACME")
    assert (acme.phase, acme.deciles_refresh_id) == ("Mature Growth", first)
    assert acme.value is not None


def test_full_refresh_whose_deciles_rank_no_company_fails(env_fixture_universe: Env) -> None:
    """Every admitted company fails its income-statement fetch, so no series ranks: the refresh
    fails in its deciles stage and saves none."""
    env = env_fixture_universe
    env.router.fail.add("income-annual")
    refresh_id = env.refresh().run("full")
    row = env.last()
    assert (row.status, row.stage, row.message, row.calibration) == (
        "failed",
        "deciles",
        "deciles rank no company",
        None,
    )
    assert deciles(env) is None
    reason = "data fetch failed: income-annual"
    assert env.items(refresh_id) == [(symbol, "failed", reason) for symbol in ADMITTED]
    assert sorted(env.snapshots()) == [(symbol, refresh_id, reason) for symbol in ADMITTED]


def test_deciles_leave_out_symbols_without_statements(env_fixture_universe: Env) -> None:
    env = env_fixture_universe
    refresh_id = env.refresh().run("full")
    saved = deciles(env)
    assert saved is not None and saved.refresh_id == refresh_id
    with closing(env.connect()) as conn:
        assert deciles_for_universe(conn, [*ADMITTED, "NONE"], refresh_id) == saved
        assert deciles_for_universe(conn, ["NONE"], 99) == Deciles((), (), 0, 0, 99)


def test_a_growth_company_is_valued_on_its_mature_peers(env_fixture_universe: Env) -> None:
    """The value stage hands the refresh's deciles to assembly, which classifies the peers on
    them: NEWT's peers name the fixture universe's three mature companies (and NEWT itself, which
    is dropped), so its revenue route has a target margin on three peers and a value. Without the
    deciles NEWT would have no peers and be refused for its target margin."""
    env = env_fixture_universe
    peers = [{"symbol": symbol} for symbol in ("ACME", "NEWT", "AXLE", "MILD")]
    env.router.symbol_bodies[("peers", "NEWT")] = json.dumps(peers).encode()
    refresh_id = env.refresh().run("full")
    assert env.items(refresh_id) == [(symbol, "valued", None) for symbol in ADMITTED]
    newt = env.snapshot("NEWT")
    assert (newt.phase, newt.route, newt.refusal) == ("Young Growth", "revenue-growth", None)
    assert newt.deciles_refresh_id == refresh_id
    assert newt.value is not None and newt.value > 0
    target = newt.result.intermediates["target_margin"]
    assert target["count"] == 3
    assert [p["symbol"] for p in target["peers"]] == ["ACME", "AXLE", "MILD"]


def test_an_empty_quarterly_consensus_is_not_a_fetch_failure(env_fixture_universe: Env) -> None:
    """FMP answers ``[]`` for a company without quarterly coverage. AXLE reports in euros (a
    foreign filer, which reports twice a year) and gets the foreign-filer refusal with its phase;
    MILD is Mature Stable, whose route never reads the consensus, and gets its value."""
    env = env_fixture_universe
    for symbol in ("AXLE", "MILD"):
        env.router.symbol_bodies[("estimates-quarter", symbol)] = b"[]"
    annual = json.loads(env.router.symbol_bodies[("income-annual", "AXLE")])
    euros = [{**row, "reportedCurrency": "EUR"} for row in annual]
    env.router.symbol_bodies[("income-annual", "AXLE")] = json.dumps(euros).encode()
    refresh_id = env.refresh().run("full")
    assert env.last().status == "done"
    assert env.items(refresh_id) == [(symbol, "valued", None) for symbol in ADMITTED]
    axle, mild = env.snapshot("AXLE"), env.snapshot("MILD")
    assert (axle.phase, axle.refusal, axle.value) == ("Mature Growth", FOREIGN, None)
    assert (mild.phase, mild.route, mild.refusal) == ("Mature Stable", "mature-stable", None)
    assert mild.value is not None and mild.value > 0


# --- the server's worker and its startup -----------------------------------------------------


def join_threads(prefix: str) -> None:
    """Wait for the threads whose name starts with ``prefix``: no test leaves one running."""
    for thread in threading.enumerate():
        if thread.name.startswith(prefix):
            thread.join(5)
            assert not thread.is_alive(), thread.name


def test_worker_waits_for_abandoned_fetches(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """While a run's thread is alive, a start is refused at once. A run that ends on an exception
    in its fetch stage gives up the fetches in flight; they may still write. The worker starts no
    run until they end, waiting up to its limit, and keeps the run's error."""
    hold_acme, release = threading.Event(), threading.Event()
    fetch_company = run_module.fetch_company

    def blocked(*args: Any) -> Any:
        if "BOLT" in args:  # given up: what it returns is never read
            release.wait(5)
            raise RuntimeError("released")
        hold_acme.wait(5)
        return fetch_company(*args)

    monkeypatch.setattr(run_module, "fetch_company", blocked)

    raised: list[int] = []

    def make_refresh(cancel: threading.Event, on_progress: Callable[[Progress], None]) -> Refresh:
        def stop_after_acme(progress: Progress) -> None:  # the first run only
            on_progress(progress)
            if progress.stage == "fetch" and progress.done == 1 and not raised:
                raised.append(progress.refresh_id)
                raise RuntimeError(f"the sink is gone near {FMP_KEY}")

        return env.refresh(cancel=cancel, then=stop_after_acme)

    worker = RefreshWorker(make_refresh, wait_s=1.0)
    first = worker.start("scoped", ["ACME", "BOLT"])
    try:
        began = time.monotonic()
        with pytest.raises(RefreshRunning) as running:
            worker.start("scoped", ["ACME"])  # the run's thread is alive: no wait
        assert running.value.refresh_id == first and time.monotonic() - began < 0.2

        hold_acme.set()  # ACME is fetched and the run stops on its progress
        join_threads("fairband-refresh")
        assert (env.last().id, env.last().status) == (first, "failed")
        assert worker.last_error == "RuntimeError: the sink is gone near <key>"
        assert worker.status() is None
        with pytest.raises(RefreshRunning) as running:
            worker.start("scoped", ["ACME"])  # BOLT's given-up fetch is still in flight
        assert running.value.refresh_id == first and env.last().id == first

        releaser = threading.Timer(0.05, release.set)
        releaser.start()
        second = worker.start("scoped", ["ACME"])  # waits for BOLT's fetch to end
        releaser.join()
        join_threads("fairband-refresh")
        assert (env.last().id, env.last().status) == (second, "done") and second == first + 1
        assert worker.last_error is None
    finally:
        hold_acme.set()
        release.set()
        join_threads("fairband-")


def test_startup_marks_interrupted(env: Env, caplog: pytest.LogCaptureFixture) -> None:
    """A refresh a stopped server or command left running is marked when the server starts."""
    with closing(env.connect()) as conn:
        left = create_refresh(conn, "full", None, env.policy.version, METHOD_VERSION, env.clock())
    env.clock.now += timedelta(hours=2)
    settings = Settings(env.db_path.parent, env.db_path.parent, env.db_path, DEFAULT_PORT)
    app = create_app(settings, env.policy, env.connect, clock=env.clock)
    with caplog.at_level(logging.INFO), TestClient(app, base_url="http://127.0.0.1:8470"):
        row = env.last()
        assert (row.id, row.status, row.finished_at) == (left, "interrupted", env.clock.now)
    assert "1 running refresh marked interrupted" in caplog.messages


# --- python -m fairband refresh | migrate ----------------------------------------------------


def test_cli_full_refresh_prints_calibration(
    env_fixture_universe: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env = env_fixture_universe
    use_cli(env, monkeypatch, tmp_path)
    assert cli.main(["refresh"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:3] == [
        "universe: 0 done, 0 failed, 0 to go",
        "universe: 4 done, 0 failed, 0 to go",
        "fetch: 0 done, 0 failed, 4 to go",
    ]
    assert "deciles: 4 done, 0 failed, 0 to go" in out
    assert out[out.index("done: 4 done, 0 failed, 0 to go") :] == [
        "done: 4 done, 0 failed, 0 to go",
        "refresh 1: done",
        "4 companies · 3 valued · 3 flagged by a classifier check",
        "Start-up: 0",
        "Young Growth: 1",
        "High Growth: 0",
        "Mature Growth: 2",
        "Mature Stable: 1",
        "Decline: 0",
        "unclassified: 0",
        f"1 refused: {NO_TARGET}",
    ]
    assert env.last().calibration == CALIBRATION


def test_migrate_marks_an_interrupted_refresh(
    env: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A refresh a killed command left running blocks the next one; the message names the way
    out, and ``migrate`` takes it without the server."""
    use_cli(env, monkeypatch, tmp_path)
    with closing(env.connect()) as conn:
        left = create_refresh(conn, "scoped", ["ACME"], env.policy.version, "m", env.clock())
    assert cli.main(["refresh", "ACME"]) == 1
    assert capsys.readouterr().err.splitlines()[-1] == (
        f"refresh {left} is running; try again when it has finished."
        " Start the server, or run migrate, to mark an interrupted refresh."
    )
    assert cli.main(["migrate"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "No migrations to apply.",
        "Marked 1 running refresh interrupted.",
    ]
    assert (env.last().id, env.last().status) == (left, "interrupted")
    assert cli.main(["refresh", "ACME"]) == 0
    assert cli.main(["migrate"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == "No migrations to apply."


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [(403, None, "VendorError: "), (200, b"[]", "ValueError: screener returned no rows")],
)
def test_cli_full_refresh_failure_prints_no_traceback(
    env_fixture_universe: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    status: int,
    body: bytes | None,
    message: str,
) -> None:
    env = env_fixture_universe
    use_cli(env, monkeypatch, tmp_path)
    if body is None:
        env.router.fail.add("screener")
        env.router.fail_status = status
    else:
        env.router.bodies["screener"] = body
    assert cli.main(["refresh"]) == 1
    out, err = capsys.readouterr()
    last = out.splitlines()[-1]
    assert last == f"refresh 1: failed: {env.last().message}"
    assert last.startswith(f"refresh 1: failed: {message}")
    assert "Traceback" not in out + err and FMP_KEY not in out + err


def test_cli_refresh_that_cannot_start_prints_no_traceback(
    env: Env, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The policy version is on record with another hash, so the run refuses before its record
    exists: there is no refresh id to name."""
    use_cli(env, monkeypatch, tmp_path)
    with closing(env.connect()) as conn:
        record_policy(conn, replace(env.policy, hash="0" * 64), env.clock())
    assert cli.main(["refresh"]) == 1
    out, err = capsys.readouterr()
    refused = f"policy {env.policy.version} is recorded with hash {'0' * 64}, not {env.policy.hash}"
    assert out.splitlines() == [f"refresh failed: ValueError: {refused}"]
    assert "Traceback" not in out + err and env.last().id == env.universe_id
