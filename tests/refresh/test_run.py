"""``Refresh`` and ``python -m fairband refresh`` over the fixture router and a migrated temporary
database: the stages, the per-symbol failures, the stops, the progress and the printed rows.

ACME and BOLT are in the universe (the fixtures' companies; CRUX has no fixtures and is never
reached). The default policy fetches on four workers; a test that pins the order of events runs on
one.
"""

import json
import logging
import sqlite3
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from synthetic import add_company, bodies, estimates_quarter
from vendor_double import FMP_KEY, GF_TOKEN, Clients, Clock, Router

from fairband import __main__ as cli
from fairband.config import Keys, MissingKey
from fairband.engine import METHOD_VERSION
from fairband.engine.classifier import Deciles
from fairband.policy import Policy
from fairband.policy.tax import TaxTable, load_tax_table
from fairband.refresh import run as run_module
from fairband.refresh.run import Progress, Refresh
from fairband.store.db import connect, migrate
from fairband.store.refreshes import (
    RefreshRow,
    RefreshRunning,
    current_refresh,
    items,
    latest_refresh,
    save_deciles,
)
from fairband.store.snapshots import SnapshotRow, latest_snapshot

GROWTH_EDGES = (-0.1, -0.05, 0.0, 0.03, 0.06, 0.09, 0.12, 0.18, 0.3)
BOLT_FAILED = (
    "data fetch failed: income-annual, balance-annual, cashflow-annual, quote, estimates-quarter"
)
QUOTE_DATE = date(2026, 10, 30)  # both fixture quotes'


@dataclass
class Env:
    """A migrated database whose universe lists ACME and BOLT, and the clients over the router.
    ``progress`` collects every event of every refresh built by ``refresh``."""

    db_path: Path
    universe_id: int
    clients: Clients
    router: Router
    clock: Clock
    policy: Policy
    tax: TaxTable
    progress: list[Progress] = field(default_factory=list)

    def connect(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def refresh(
        self,
        workers: int | None = None,
        cancel: threading.Event | None = None,
        then: Callable[[Progress], None] | None = None,
    ) -> Refresh:
        policy = self.policy
        if workers is not None:
            policy = replace(policy, refresh=replace(policy.refresh, workers=workers))

        def record(progress: Progress) -> None:
            self.progress.append(progress)
            if then is not None:
                then(progress)

        return Refresh(
            self.connect,
            self.clients.fmp,
            self.clients.gf,
            policy,
            self.tax,
            self.clock,
            cancel or threading.Event(),
            record,
            self.clients.secrets,
        )

    def run(self, symbols: list[str], **refresh: Any) -> int:
        return self.refresh(**refresh).run("scoped", symbols)

    def last(self) -> RefreshRow:
        with closing(self.connect()) as conn:
            row = latest_refresh(conn)
        assert row is not None
        return row

    def items(self, refresh_id: int) -> list[tuple[str, str, str | None]]:
        with closing(self.connect()) as conn:
            return [(i.symbol, i.status, i.error) for i in items(conn, refresh_id)]

    def snapshot(self, symbol: str) -> SnapshotRow:
        with closing(self.connect()) as conn:
            row = latest_snapshot(conn, symbol)
        assert row is not None
        return row

    def snapshots(self) -> list[tuple[str, int, str | None]]:
        """Every snapshot, oldest first: symbol, refresh id and refusal."""
        with closing(self.connect()) as conn:
            rows = conn.execute("SELECT symbol, refresh_id, refusal FROM snapshots ORDER BY id")
            return [(r["symbol"], r["refresh_id"], r["refusal"]) for r in rows]


@pytest.fixture
def env(
    tmp_path: Path, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> Iterator[Env]:
    db_path = tmp_path / "data" / "fairband.db"
    with closing(connect(db_path)) as conn:
        migrate(conn)
        universe_id = add_company(conn, symbols=("ACME", "BOLT"))
    yield Env(db_path, universe_id, clients, router, clock, policy, load_tax_table())


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
    assert env.router.symbol_calls == Counter({"ACME": 14, "BOLT": 14})
    with closing(env.connect()) as conn:
        versions = [r[0] for r in conn.execute("SELECT version FROM policy_versions")]
    assert versions == [env.policy.version]
    assert env.progress == [
        Progress(refresh_id, "fetch", 0, 0, 2, None),
        Progress(refresh_id, "fetch", 1, 0, 1, None),
        Progress(refresh_id, "fetch", 2, 0, 0, None),
        Progress(refresh_id, "value", 0, 0, 2, None),
        Progress(refresh_id, "value", 1, 0, 1, None),
        Progress(refresh_id, "value", 2, 0, 0, None),
        Progress(refresh_id, "done", 2, 0, 0, None),
    ]


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
    assert acme.value is not None and acme.value > 0 and acme.stance5 is not None
    assert (acme.price, acme.price_date, acme.data_date) == (50.0, QUOTE_DATE, env.clock.now.date())
    assert env.items(refresh_id) == [("ACME", "valued", None)]


def test_stop_after_first_then_continue(env: Env) -> None:
    """The cancel lands in the fetch stage: ACME keeps its stored responses, BOLT is never
    started and nothing is valued; the next run reuses ACME's responses and fetches BOLT."""
    cancel = threading.Event()

    def stop_after_first(progress: Progress) -> None:
        if progress.stage == "fetch" and progress.done + progress.failed == 1:
            cancel.set()

    first = env.run(["ACME", "BOLT"], workers=1, cancel=cancel, then=stop_after_first)
    row = env.last()
    assert (row.id, row.status, row.stage, row.message) == (first, "cancelled", "fetch", None)
    assert env.items(first) == [("ACME", "fetched", None), ("BOLT", "pending", None)]
    assert env.snapshots() == []
    assert env.router.symbol_calls == Counter({"ACME": 14})

    env.router.symbol_calls.clear()
    env.clock.now += timedelta(hours=1)
    second = env.run(["ACME", "BOLT"])
    assert (env.last().id, env.last().status) == (second, "done")
    assert env.router.symbol_calls == Counter({"BOLT": 14})  # ACME: no call
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
    assert sum(env.router.calls.values()) == 12  # FMP again; GuruFocus is reused for 7 days


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
    env.router.fail_status = 429
    env.router.fail_symbols.add("BOLT")
    refresh_id = env.run(["ACME", "BOLT", "CRUX"], workers=1)
    row = env.last()
    assert (row.status, row.stage, row.message) == (
        "failed",
        "value",
        "rate limited by FMP: stopped after 1 company",
    )
    assert env.items(refresh_id) == [
        ("ACME", "valued", None),
        ("BOLT", "pending", "rate limited by FMP"),
        ("CRUX", "pending", None),
    ]
    assert env.snapshots() == [("ACME", refresh_id, "no universe deciles yet")]
    assert env.router.symbol_calls == Counter({"ACME": 14, "BOLT": 3})  # three tries, then stop


def test_rate_limit_names_the_provider(env: Env) -> None:
    env.router.fail_status = 429
    env.router.fail.add("summary")
    refresh_id = env.run(["ACME", "BOLT"], workers=1)
    assert env.last().message == "rate limited by GuruFocus: stopped after 0 companies"
    assert env.items(refresh_id) == [
        ("ACME", "pending", "rate limited by GuruFocus"),
        ("BOLT", "pending", None),
    ]
    assert env.snapshots() == []


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
    assert env.router.symbol_calls == Counter({"ACME": 14})


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
    with pytest.raises(MissingKey, match="no fmp key"):
        no_fmp.run("scoped", ["ACME"])
    refresh = env.refresh()
    for symbols in ([], None):
        with pytest.raises(ValueError, match="a scoped refresh needs symbols"):
            refresh.run("scoped", symbols)
    for kind in ("full", "price"):
        with pytest.raises(NotImplementedError, match="built in a later task"):
            refresh.run(kind)  # type: ignore[arg-type]
    assert env.last().id == env.universe_id
    assert env.router.calls == Counter() and env.progress == []


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


def use_cli(env: Env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the command at the env's database and clients; the keys come from the environment."""
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(env.db_path.parent))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FAIRBAND_FMP_KEY", FMP_KEY)
    monkeypatch.setenv("FAIRBAND_GURUFOCUS_KEY", GF_TOKEN)

    def clients(keys: Keys, policy: Policy) -> tuple[Any, Any, tuple[str, ...]]:
        assert (keys.fmp, keys.gurufocus, policy.version) == (FMP_KEY, GF_TOKEN, env.policy.version)
        return env.clients.fmp, env.clients.gf, env.clients.secrets

    monkeypatch.setattr(cli, "build_clients", clients)
    monkeypatch.setattr(cli, "utcnow", env.clock)


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
    assert acme.value is not None and acme.stance5 is not None
    line = capsys.readouterr().out.splitlines()[-1]
    assert line == f"ACME  Mature Growth  value {acme.value:.2f}  stance {acme.stance5}"


def test_cli_exits_1_when_the_refresh_is_not_done(
    env: Env, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    use_cli(env, monkeypatch, tmp_path)
    env.router.fail_status = 429
    env.router.fail.add("income-annual")
    assert cli.main(["refresh", "ACME"]) == 1
    out = capsys.readouterr().out.splitlines()
    assert out[-2:] == [
        f"refresh {env.universe_id + 1}: failed: rate limited by FMP: stopped after 0 companies",
        "ACME  —  no snapshot yet",
    ]


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["refresh", ","], "no symbols given"),
        (["refresh"], "a full refresh is not built yet"),
        (["refresh", "ACME", "--kind", "price"], "a price refresh is not built yet"),
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
