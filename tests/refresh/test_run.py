"""``Refresh`` and ``python -m fairband refresh`` over the fixture router and a migrated temporary
database: the stages, the per-symbol failures, the stops, the progress and the printed rows.

ACME and BOLT are in the universe (the fixtures' companies; CRUX has no fixtures and is never
reached). The default policy fetches on sixteen workers; a test that pins the order of events runs on
one.
"""

import json
import logging
import re
import signal
import sqlite3
import threading
import time
from collections import Counter
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from refresh_env import Env, use_cli
from synthetic import bodies, estimates_quarter
from vendor_double import FMP_KEY, GF_TOKEN

from fairband import __main__ as cli
from fairband.config import MissingKey
from fairband.engine import METHOD_VERSION
from fairband.engine.classifier import Deciles
from fairband.refresh import run as run_module
from fairband.refresh.run import Progress, Refresh
from fairband.store.multiples import MultiplesRow, multiples_log_for
from fairband.store.refreshes import RefreshRunning, current_refresh, save_deciles
from fairband.store.vendor import record_response

GROWTH_EDGES = (-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3)
BOLT_FAILED = "data fetch failed: income-annual, balance-annual, cashflow-annual, quote"
QUOTE_DATE = date(2026, 10, 30)  # both fixture quotes'
RATE_LIMITED = "data fetch incomplete: rate limited"


@pytest.fixture
def env_with_deciles(env: Env) -> Env:
    """Deciles stored under the universe's refresh, and ACME's twelve synthetic years with a full
    NTM consensus, so ACME is Mature Growth and gets a value."""
    payloads = {**bodies(), "estimates-quarter": estimates_quarter()}
    env.router.bodies.update({name: json.dumps(body).encode() for name, body in payloads.items()})
    deciles = Deciles(GROWTH_EDGES, (0.0,) * 9, 100, 100, None)
    with closing(env.connect()) as conn:
        save_deciles(conn, env.universe_id, deciles, env.clock())
    return env


@pytest.fixture
def env_with_500_for_B(env: Env) -> Env:
    env.router.fail_symbols.add("BOLT")
    return env


def test_scoped_refresh_without_deciles_writes_refusal_snapshots(env: Env) -> None:
    refresh_id = env.run(["ACME", "BOLT"], workers=1)
    assert refresh_id == env.universe_id + 1
    row = env.last()
    assert (row.id, row.kind, row.symbols, row.status, row.stage, row.message) == (
        refresh_id,
        "scoped",
        ("ACME", "BOLT"),
        "done",
        "done",
        None,
    )
    assert (row.policy_version, row.method_version) == (env.policy.version, METHOD_VERSION)
    assert (row.started_at, row.finished_at) == (env.clock.now, env.clock.now)
    assert env.items(refresh_id) == [("ACME", "valued", None), ("BOLT", "valued", None)]
    assert env.snapshots() == [
        ("ACME", refresh_id, "no universe deciles yet"),
        ("BOLT", refresh_id, "no universe deciles yet"),
    ]
    acme = env.snapshot("ACME")
    assert (acme.value, acme.price, acme.price_date, acme.deciles_refresh_id) == (
        None,
        50.0,
        QUOTE_DATE,
        None,
    )
    assert env.router.symbol_calls == Counter({"ACME": 15, "BOLT": 15})
    with closing(env.connect()) as conn:
        versions = [r[0] for r in conn.execute("SELECT version FROM policy_versions")]
    assert versions == [env.policy.version]
    assert env.progress == [
        Progress(refresh_id, "fetch", 0, 0, 2, None),
        Progress(refresh_id, "fetch", 1, 0, 1, None),
        Progress(refresh_id, "fetch", 2, 0, 0, None),
        Progress(refresh_id, "backfill", 0, 0, 0, None),
        Progress(refresh_id, "value", 0, 0, 2, None),
        Progress(refresh_id, "value", 1, 0, 1, None),
        Progress(refresh_id, "value", 2, 0, 0, None),
        Progress(refresh_id, "done", 2, 0, 0, None),
    ]


def test_first_refresh_before_any_universe_says_no_deciles(env_without_universe: Env) -> None:
    """Before any universe there are no deciles: that is the reason a first scoped refresh
    gives, whatever else assembly finds."""
    env = env_without_universe
    refresh_id = env.run(["ACME"])
    assert refresh_id == 1 and env.last().status == "done"
    assert env.snapshots() == [("ACME", refresh_id, "no universe deciles yet")]


def test_scoped_refresh_with_stored_deciles_values(env_with_deciles: Env) -> None:
    env = env_with_deciles
    refresh_id = env.run(["ACME"])
    acme = env.snapshot("ACME")
    assert (acme.refresh_id, acme.refusal, acme.deciles_refresh_id) == (
        refresh_id,
        None,
        env.universe_id,
    )
    assert (acme.phase, acme.route) == ("Mature Growth", "mature-growth")
    assert acme.value is not None and acme.value > 0 and acme.designation is not None
    assert (acme.price, acme.price_date, acme.data_date) == (50.0, QUOTE_DATE, env.clock.now.date())
    assert env.items(refresh_id) == [("ACME", "valued", None)]
    # The synthetic company's invested capital takes the issuer's as-reported intangibles.
    [roic] = [i for i in acme.result.inputs if i.name == "aggregate_roic"]
    assert (roic.kind, roic.estimate_method) == ("estimate", "bs10-intangibles-total-v1")
    # The drawer names the tax country, the FMP profile's.
    [tax] = [i for i in acme.result.inputs if i.name == "tax_rate_latest"]
    assert tax.note is not None and tax.note.startswith("US, the headquarters country in the FMP")


def test_stop_after_first_then_continue(env: Env) -> None:
    """The cancel lands in the fetch stage: ACME keeps its stored responses, BOLT is never
    started, and no snapshot is written, because a cancel ends the run after the current symbol
    and no later stage runs (a full refresh could not compute deciles from part of the
    universe either). Nothing is lost: the next run reuses ACME's responses (no call), fetches
    BOLT and values both."""
    cancel = threading.Event()

    def stop_after_first(progress: Progress) -> None:
        if progress.stage == "fetch" and progress.done + progress.failed == 1:
            cancel.set()

    first = env.run(["ACME", "BOLT"], workers=1, cancel=cancel, then=stop_after_first)
    row = env.last()
    assert (row.id, row.status, row.stage, row.message) == (first, "cancelled", "fetch", None)
    assert env.items(first) == [("ACME", "fetched", None), ("BOLT", "pending", None)]
    assert env.snapshots() == []
    assert env.router.symbol_calls == Counter({"ACME": 15})

    env.router.symbol_calls.clear()
    env.clock.now += timedelta(hours=1)
    second = env.run(["ACME", "BOLT"])
    assert (env.last().id, env.last().status) == (second, "done")
    assert env.router.symbol_calls == Counter({"BOLT": 15})  # ACME: no call
    assert env.items(second) == [("ACME", "valued", None), ("BOLT", "valued", None)]
    assert [(symbol, refresh) for symbol, refresh, _ in env.snapshots()] == [
        ("ACME", second),
        ("BOLT", second),
    ]


def test_fresh_company_not_fetched_again(env: Env) -> None:
    first = env.run(["ACME"])
    env.router.calls.clear()
    env.clock.now += timedelta(hours=23)
    second = env.run(["ACME"])
    assert env.router.calls == Counter()
    assert env.last().status == "done"
    assert env.items(second) == [("ACME", "valued", None)]
    assert [refresh for _, refresh, _ in env.snapshots()] == [first, second]

    env.clock.now += timedelta(hours=2)  # 25 hours after the first fetch
    env.run(["ACME"])
    assert sum(env.router.calls.values()) == 13  # FMP again; GuruFocus is reused for 7 days


def test_failing_company_gets_refusal_row(
    env_with_500_for_B: Env, caplog: pytest.LogCaptureFixture
) -> None:
    env = env_with_500_for_B
    refresh_id = env.run(["ACME", "BOLT"])
    assert (env.last().status, env.last().message) == ("done", None)
    assert env.items(refresh_id) == [("ACME", "valued", None), ("BOLT", "failed", BOLT_FAILED)]
    bolt = env.snapshot("BOLT")
    assert (bolt.refresh_id, bolt.refusal, bolt.value, bolt.phase) == (
        refresh_id,
        BOLT_FAILED,
        None,
        None,
    )
    assert (bolt.price, bolt.price_date) == (None, None)  # the store holds no quote for BOLT
    assert env.snapshot("ACME").refusal == "no universe deciles yet"
    assert f"BOLT: {BOLT_FAILED}" in caplog.text
    assert Progress(refresh_id, "fetch", 1, 1, 0, None) in env.progress
    assert env.progress[-1] == Progress(refresh_id, "done", 1, 1, 0, None)


def test_failed_fetch_keeps_the_stored_price(env: Env) -> None:
    env.run(["BOLT"])
    env.router.fail_symbols.add("BOLT")
    env.clock.now += timedelta(hours=25)
    refresh_id = env.run(["BOLT"])
    bolt = env.snapshot("BOLT")
    assert (bolt.refresh_id, bolt.refusal) == (refresh_id, BOLT_FAILED)
    assert (bolt.price, bolt.price_date) == (100.0, QUOTE_DATE)


def test_a_refusal_with_a_price_logs_the_price_alone(env: Env) -> None:
    """A refusal with a price logs the price of its day and no multiple; a failed fetch's refusal
    that carries the stored price replaces the row of the same day."""
    first = env.run(["BOLT"])  # no deciles yet: refused, at the quote's price
    first_snapshot = env.snapshot("BOLT").id
    with closing(env.connect()) as conn:
        assert multiples_log_for(conn, "BOLT") == [
            MultiplesRow(QUOTE_DATE, 100.0, None, None, None, first_snapshot)
        ]
    env.router.fail_symbols.add("BOLT")
    env.clock.now += timedelta(hours=25)
    second = env.run(["BOLT"])
    bolt = env.snapshot("BOLT")
    assert bolt.refusal == BOLT_FAILED and bolt.id > first_snapshot
    with closing(env.connect()) as conn:
        assert multiples_log_for(conn, "BOLT") == [
            MultiplesRow(QUOTE_DATE, 100.0, None, None, None, bolt.id)
        ]
        [(refresh_id,)] = conn.execute("SELECT refresh_id FROM multiples_log").fetchall()
    assert (first, refresh_id) == (second - 1, second)


@pytest.mark.parametrize(
    ("target", "prefix", "price"),
    [("fetch_company", "data fetch failed", None), ("build_inputs", "valuation failed", 100.0)],
)
def test_exception_in_a_symbol_gives_it_a_refusal_row(
    env: Env,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    target: str,
    prefix: str,
    price: float | None,
) -> None:
    real = getattr(run_module, target)

    def boom(*args: Any) -> Any:
        if "BOLT" in args:
            raise ValueError(f"bad answer near {FMP_KEY}")
        return real(*args)

    monkeypatch.setattr(run_module, target, boom)
    refresh_id = env.run(["ACME", "BOLT"])
    reason = f"{prefix}: ValueError: bad answer near <key>"
    assert env.last().status == "done"
    assert env.items(refresh_id) == [("ACME", "valued", None), ("BOLT", "failed", reason)]
    bolt = env.snapshot("BOLT")
    assert (bolt.refusal, bolt.price) == (reason, price)
    assert f"BOLT: {reason}" in caplog.text and FMP_KEY not in caplog.text


def test_rate_limit_stops_the_fetch_and_values_what_was_fetched(env: Env) -> None:
    """BOLT's fetch hits the 429: it gets a refusal row; CRUX is never reached and gets none."""
    env.router.fail_status = 429
    env.router.fail_symbols.add("BOLT")
    refresh_id = env.run(["ACME", "BOLT", "CRUX"], workers=1)
    row = env.last()
    assert (row.status, row.stage, row.message) == (
        "failed",
        "value",
        "rate limited by FMP: stopped after 2 companies",
    )
    assert env.items(refresh_id) == [
        ("ACME", "valued", None),
        ("BOLT", "failed", RATE_LIMITED),
        ("CRUX", "pending", None),
    ]
    assert env.snapshots() == [
        ("BOLT", refresh_id, RATE_LIMITED),
        ("ACME", refresh_id, "no universe deciles yet"),
    ]
    assert env.router.symbol_calls == Counter({"ACME": 15, "BOLT": 3})  # three tries, then stop


def test_the_fetch_stage_logs_the_fmp_pace(env: Env, caplog: pytest.LogCaptureFixture) -> None:
    """One INFO line at the fetch stage's end gives the FMP limiter's share of the stage: the
    fixtures' FMP client is not paced, so 13 calls a company with no wait and no hold. A second
    run within the reuse window fetches nothing, and its line counts its own stage only."""
    with caplog.at_level(logging.INFO, logger="fairband.refresh"):
        env.run(["ACME", "BOLT"])
        env.run(["ACME", "BOLT"])
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("FMP pace")]
    assert lines == [
        "FMP pace: waited 0.0 s over 26 calls, 0 holds",
        "FMP pace: waited 0.0 s over 0 calls, 0 holds",
    ]


def test_rate_limit_names_the_provider(env: Env) -> None:
    """ACME's GuruFocus call hits the 429 after its quote is stored: its refusal row has the
    price."""
    env.router.fail_status = 429
    env.router.fail.add("summary")
    refresh_id = env.run(["ACME", "BOLT"], workers=1)
    assert env.last().message == "rate limited by GuruFocus: stopped after 1 company"
    assert env.items(refresh_id) == [("ACME", "failed", RATE_LIMITED), ("BOLT", "pending", None)]
    assert env.snapshots() == [("ACME", refresh_id, RATE_LIMITED)]
    assert env.snapshot("ACME").price == 50.0


def test_second_refresh_refused_while_running(env: Env) -> None:
    refused: list[int] = []

    def start_another(progress: Progress) -> None:
        if progress.stage == "fetch" and not refused:
            with pytest.raises(RefreshRunning) as running:
                env.run(["BOLT"])
            refused.append(running.value.refresh_id)

    first = env.run(["ACME"], then=start_another)
    assert refused == [first]
    assert env.last().id == first and env.last().status == "done"
    assert env.router.symbol_calls == Counter({"ACME": 15})


def test_run_refuses_before_any_work(env: Env) -> None:
    no_fmp = Refresh(
        env.connect,
        None,
        env.clients.gf,
        env.policy,
        env.tax,
        env.clock,
        threading.Event(),
    )
    with pytest.raises(ValueError, match="no fmp key"):
        no_fmp.run("scoped", ["ACME"])
    refresh = env.refresh()
    for symbols in ([], None):
        with pytest.raises(ValueError, match="a scoped refresh needs symbols"):
            refresh.run("scoped", symbols)
    with pytest.raises(ValueError, match="a full refresh takes no symbols"):
        refresh.run("full", ["ACME"])
    with pytest.raises(ValueError, match="a price refresh takes no symbols"):
        refresh.run("price", ["ACME"])
    assert env.last().id == env.universe_id
    assert env.router.calls == Counter() and env.progress == []


def test_refresh_without_fmp_refuses_every_kind_but_revalue(env: Env) -> None:
    """Without an FMP client (the server's worker without a key), a kind that fetches is a
    ``ValueError`` naming the keys file, before its record exists; a revalue runs."""
    refresh = Refresh(
        env.connect, None, None, env.policy, env.tax, env.clock, threading.Event(), None, ()
    )
    for kind, symbols in (("full", None), ("price", None), ("scoped", ["ACME"])):
        with pytest.raises(ValueError, match=re.escape(str(MissingKey("fmp")))):
            refresh.run(kind, symbols)
    assert env.last().id == env.universe_id
    refresh_id = refresh.run("revalue")
    row = env.last()
    assert (row.id, row.kind, row.status) == (env.universe_id + 1, "revalue", "done")
    assert refresh_id == row.id and env.router.calls == Counter()


def test_an_exception_outside_a_symbol_fails_the_run(env: Env) -> None:
    def fail_in_value(progress: Progress) -> None:
        if progress.stage == "value":
            raise RuntimeError("the progress sink is gone")

    with pytest.raises(RuntimeError, match="the progress sink is gone"):
        env.run(["ACME"], then=fail_in_value)
    row = env.last()
    assert (row.status, row.message) == ("failed", "RuntimeError: the progress sink is gone")
    assert row.finished_at == env.clock.now
    with closing(env.connect()) as conn:
        assert current_refresh(conn) is None


# --- python -m fairband refresh --------------------------------------------------------------


def test_cli_refresh_prints_rows(
    env: Env, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_cli(env, monkeypatch, tmp_path)
    assert cli.main(["refresh", "ACME,BOLT"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "fetch: 0 done, 0 failed, 2 to go",
        "fetch: 1 done, 0 failed, 1 to go",
        "fetch: 2 done, 0 failed, 0 to go",
        "backfill: 0 done, 0 failed, 0 to go",
        "value: 0 done, 0 failed, 2 to go",
        "value: 1 done, 0 failed, 1 to go",
        "value: 2 done, 0 failed, 0 to go",
        "done: 2 done, 0 failed, 0 to go",
        f"refresh {env.universe_id + 1}: done",
        "ACME  —  no universe deciles yet",
        "BOLT  —  no universe deciles yet",
    ]


def test_cli_prints_the_value_line(
    env_with_deciles: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env = env_with_deciles
    use_cli(env, monkeypatch, tmp_path)
    assert cli.main(["refresh", "ACME"]) == 0
    acme = env.snapshot("ACME")
    assert acme.value is not None and acme.price_to_value is not None
    assert acme.designation == "above"
    line = capsys.readouterr().out.splitlines()[-1]
    # ACME's price is about 1.496 × its value: to two decimals 1.50, the edge where well-above
    # starts, so the line gives the third decimal that keeps the figure in its band.
    assert f"{acme.price_to_value:.2f}" == "1.50" and f"{acme.price_to_value:.3f}" == "1.496"
    assert line == f"ACME  Mature Growth  value {acme.value:.2f}  above (1.496 × value)"


def test_cli_line_keeps_the_ratio_inside_its_band(env_with_deciles: Env) -> None:
    """Two decimals that would land on a designation edge the ratio is not on would print the
    next band's figure beside the word (0.8499 as 0.85, where near starts): the line gives a
    third decimal, kept a thousandth off the edge. A ratio on an edge, or whose two decimals land
    on no edge, prints as before; a snapshot without a designation ends at its value."""
    env = env_with_deciles
    env.run(["ACME"])
    acme = env.snapshot("ACME")
    assert acme.value is not None
    edges = env.policy.designation_edges
    assert edges == (0.65, 0.85, 1.15, 1.50)
    value = f"{acme.value:.2f}"

    def line(ratio: float | None, designation: str | None) -> str:
        row = replace(acme, price_to_value=ratio, designation=designation)
        return cli._snapshot_line("ACME", row, edges)

    assert line(0.8499, "below") == f"ACME  Mature Growth  value {value}  below (0.849 × value)"
    assert line(1.1501, "above") == f"ACME  Mature Growth  value {value}  above (1.151 × value)"
    assert line(0.6499, "well-below").endswith("well-below (0.649 × value)")
    assert line(1.4999, "above").endswith("above (1.499 × value)")
    # A third decimal that rounds onto the edge too is kept a thousandth off it.
    assert line(0.84996, "below").endswith("below (0.849 × value)")
    assert line(1.15002, "above").endswith("above (1.151 × value)")
    # On an edge, and off every edge, two decimals as before.
    assert line(85 / 100, "near").endswith("near (0.85 × value)")
    assert line(150 / 100, "well-above").endswith("well-above (1.50 × value)")
    assert line(0.7512, "below").endswith("below (0.75 × value)")
    assert line(1.0468, "near").endswith("near (1.05 × value)")
    # A snapshot valued before the designation (method 0.5) has a value and no word.
    assert line(None, None) == f"ACME  Mature Growth  value {value}"


def test_cli_exits_1_when_the_refresh_is_not_done(
    env: Env, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_cli(env, monkeypatch, tmp_path)
    env.router.fail_status = 429
    env.router.fail.add("income-annual")
    assert cli.main(["refresh", "ACME"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == [
        f"refresh {env.universe_id + 1}: failed: rate limited by FMP: stopped after 1 company",
        f"ACME  —  {RATE_LIMITED}",
    ]


def press_ctrl_c(times: int) -> Callable[[Progress], None]:
    """A progress printer that, at the start of the fetch stage, calls the SIGINT handler in
    place ``times`` times, as Ctrl-C would; ``pressed`` records each handler called."""
    pressed: list[object] = []
    print_progress = cli._print_progress

    def on_progress(progress: Progress) -> None:
        if progress.stage == "fetch" and not pressed:
            for _ in range(times):
                handler = signal.getsignal(signal.SIGINT)
                assert callable(handler)
                if not pressed and handler is signal.default_int_handler:
                    pytest.fail("the command installed no SIGINT handler")
                pressed.append(handler)
                handler(signal.SIGINT, None)
        print_progress(progress)

    on_progress.pressed = pressed  # type: ignore[attr-defined]
    return on_progress


def test_cli_ctrl_c_cancels_after_the_current_symbol(
    env: Env, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_cli(env, monkeypatch, tmp_path)
    before = signal.getsignal(signal.SIGINT)
    on_progress = press_ctrl_c(1)
    monkeypatch.setattr(cli, "_print_progress", on_progress)
    assert cli.main(["refresh", "ACME,BOLT"]) == 1
    row = env.last()
    assert (row.status, row.stage) == ("cancelled", "fetch")
    assert env.items(row.id) == [("ACME", "pending", None), ("BOLT", "pending", None)]
    assert env.router.calls == Counter()
    assert f"refresh {row.id}: cancelled" in capsys.readouterr().out.splitlines()
    [handler] = on_progress.pressed  # type: ignore[attr-defined]
    assert handler is not before  # the command's own handler ran
    assert signal.getsignal(signal.SIGINT) is before  # and is gone once the command ends


def test_cli_second_ctrl_c_interrupts(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_cli(env, monkeypatch, tmp_path)
    before = signal.getsignal(signal.SIGINT)
    on_progress = press_ctrl_c(2)
    monkeypatch.setattr(cli, "_print_progress", on_progress)
    with pytest.raises(KeyboardInterrupt):
        cli.main(["refresh", "ACME"])
    assert on_progress.pressed[1] is signal.default_int_handler  # type: ignore[attr-defined]
    assert (env.last().status, env.last().message) == ("failed", "KeyboardInterrupt")
    assert signal.getsignal(signal.SIGINT) is before


def ctrl_c_twice() -> float:
    """Press Ctrl-C twice from a fetch thread, the way a terminal does, by sending SIGINT to the
    main thread, the second after the first is handled; return the time of the second."""

    def ctrl_c() -> None:
        signal.pthread_kill(threading.main_thread().ident or 0, signal.SIGINT)

    ctrl_c()
    deadline = time.monotonic() + 5
    while signal.getsignal(signal.SIGINT) is not signal.default_int_handler:
        assert time.monotonic() < deadline, "the first Ctrl-C was not handled"
        time.sleep(0.01)
    second = time.monotonic()
    ctrl_c()
    return second


def release_fetches(release: threading.Event) -> None:
    """Let the given-up fetch doubles end, and wait for their threads."""
    release.set()
    for thread in threading.enumerate():
        if thread.name.startswith("fairband-fetch"):
            thread.join(5)


def test_cli_second_ctrl_c_does_not_wait_for_a_blocked_fetch(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Both fetches block, as on a stalled vendor, and ACME's presses Ctrl-C twice. The
    interrupt must not wait for them."""
    use_cli(env, monkeypatch, tmp_path)
    release = threading.Event()
    second_press: list[float] = []

    def blocked_fetch(*args: Any) -> Any:
        if "ACME" in args:
            second_press.append(ctrl_c_twice())
        release.wait(3)
        raise RuntimeError("released")

    monkeypatch.setattr(run_module, "fetch_company", blocked_fetch)
    try:
        with pytest.raises(KeyboardInterrupt):
            cli.main(["refresh", "ACME,BOLT"])
        surfaced_after = time.monotonic() - second_press[0]
    finally:
        release_fetches(release)
    assert surfaced_after < 1
    row = env.last()
    assert (row.status, row.message) == ("failed", "KeyboardInterrupt")
    assert all(status == "pending" for _, status, _ in env.items(row.id))


def test_cli_second_ctrl_c_while_the_fetches_keep_writing(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The given-up fetches go on storing responses on their own connections while the run puts
    their items back to ``pending``: that write must wait for its turn, not fail with "database
    is locked". Five symbols on four workers, five rounds, to catch the race."""
    use_cli(env, monkeypatch, tmp_path)
    for _ in range(5):
        release = threading.Event()

        def writing_fetch(
            conn: sqlite3.Connection, *args: Any, release: threading.Event = release
        ) -> Any:
            symbol, now = args[2], args[4]
            if symbol == "ACME":
                ctrl_c_twice()
            while not release.is_set():
                record_response(conn, "fmp", "quote", {}, symbol, 200, "[]", None, now)
                release.wait(0.005)
            raise RuntimeError("released")

        monkeypatch.setattr(run_module, "fetch_company", writing_fetch)
        try:
            with pytest.raises(KeyboardInterrupt):
                cli.main(["refresh", "ACME,BOLT,CRUX,DUNE,ECHO"])
        finally:
            release_fetches(release)
        row = env.last()
        assert (row.status, row.message) == ("failed", "KeyboardInterrupt")
        assert {status for _, status, _ in env.items(row.id)} == {"pending"}


def test_cli_off_the_main_thread_leaves_sigint_alone(
    env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Python delivers signals to the main thread only; installing a handler elsewhere raises."""
    use_cli(env, monkeypatch, tmp_path)
    before = signal.getsignal(signal.SIGINT)
    exits: list[int] = []
    thread = threading.Thread(target=lambda: exits.append(cli.main(["refresh", "ACME"])))
    thread.start()
    thread.join()
    assert exits == [0] and env.last().status == "done"
    assert signal.getsignal(signal.SIGINT) is before


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["refresh", ","], "no symbols given"),
        (["refresh", "ACME", "--kind", "full"], "a full refresh takes no symbols"),
        (["refresh", "ACME", "--kind", "price"], "a price refresh takes no symbols"),
        (["refresh", "AAPL", "--kind", "revalue"], "a revalue takes no symbols"),
        (["refresh", "--kind", "scoped"], "a scoped refresh needs symbols"),
    ],
)
def test_cli_refuses_before_building_anything(
    argv: list[str],
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    assert cli.main(argv) == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize(("mode", "warned"), [(0o644, True), (0o600, False)])
def test_cli_warns_on_a_keys_file_others_can_read(
    mode: int,
    warned: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The file holds no FMP key, so the command stops after the warning."""
    keys_file = tmp_path / "config" / "fairband" / "keys.toml"
    keys_file.parent.mkdir(parents=True)
    keys_file.write_text(f'[keys]\ngurufocus = "{GF_TOKEN}"\n')
    keys_file.chmod(mode)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    with caplog.at_level(logging.WARNING):
        assert cli.main(["refresh", "ACME"]) == 2
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    expected = [f"{keys_file} has mode {mode:04o}: other users can read it; chmod 600 it"]
    assert warnings == (expected if warned else [])
    assert "no fmp key" in capsys.readouterr().err
    assert GF_TOKEN not in caplog.text
