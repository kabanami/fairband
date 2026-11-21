"""The revalue over the five companies a full refresh of ``fixture_universe`` valued, on a
migrated temporary database: a new snapshot of each company from the facts the store holds, with
no vendor call and no FMP client, and the command; a revalue that names companies, the revalue of
one company inside its caller's transaction, and the moat table each refresh that values loads
first (spec 2026-11-19 8.4, 8.6).

The full refresh values ACME, AXLE, MILD and KRON (in SEK, at the rate on file) and refuses NEWT
(Young Growth, with no mature peer for a target margin); the revalue, on the same facts, rates and
deciles, gives the same calibration.
"""

import threading
from collections import Counter
from contextlib import closing
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fixture_universe import ADMITTED, serve_universe
from refresh_env import MOAT_CLASSES, Env
from support.moat import moat_table
from synthetic import SIX_LINES

from fairband import __main__ as cli
from fairband.engine import METHOD_VERSION
from fairband.engine.overrides import current_reading
from fairband.policy.moat import MoatTable
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.refresh import run as run_module
from fairband.refresh.run import Kind, Progress, Refresh, revalue_company
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.db import transaction
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.refreshes import RefreshRunning, create_refresh
from fairband.store.reviews import latest_review
from fairband.store.settings import effective_policy, write_settings
from fairband.store.snapshots import SnapshotRow

NO_TARGET = "no target margin: 0 mature peers"
NO_STATEMENTS = "no financial statements"
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "transcript", "ref": "Q3 call", "note": ""}]


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


def moat_rows(env: Env) -> dict[str, tuple[str, str, str | None, str]]:
    """Each row of the moat table: its class, source, file version and the day it was judged."""
    with closing(env.connect()) as conn:
        rows = conn.execute(
            "SELECT symbol, class, source, file_version, judged_on FROM moat_classes"
        ).fetchall()
    return {r["symbol"]: (r["class"], r["source"], r["file_version"], r["judged_on"]) for r in rows}


def file_rows(table: MoatTable) -> dict[str, tuple[str, str, str | None, str]]:
    """The file rows ``table`` loads, as ``moat_rows`` reads them."""
    return {
        symbol: (entry.moat, "file", table.version, entry.judged.isoformat())
        for symbol, entry in table.entries.items()
    }


def override_acme(env: Env) -> int:
    """An applied override of ACME's belief, made on its latest snapshot, so a review follows each
    of its later snapshots."""
    snapshot = env.snapshot("ACME")
    old = current_reading(snapshot.result, "growth.belief")
    with closing(env.connect()) as conn:
        return insert_override(
            conn,
            "ACME",
            "growth.belief",
            old,
            0.08,
            "ratio",
            "because",
            EVIDENCE,
            "lasting",
            None,
            None,
            snapshot.id,
            AGENT,
            env.clock(),
            "applied",
            "",
        )


def test_revalue_writes_new_snapshots_without_a_vendor_call(env_valued: Env) -> None:
    env = env_valued
    before = snapshots_of(env)
    refresh_id = env.refresh().run("revalue")
    row = env.last()
    assert (row.id, row.kind, row.status, row.stage) == (refresh_id, "revalue", "done", "done")
    assert (row.symbols, row.message) == (None, None)
    assert env.router.calls == Counter()
    assert env.items(refresh_id) == [(symbol, "valued", None) for symbol in ADMITTED]
    after = snapshots_of(env)
    for symbol in ADMITTED:
        assert after[symbol].refresh_id == refresh_id and after[symbol].id > before[symbol].id
        assert after[symbol].method_version == METHOD_VERSION
        assert after[symbol].policy_version == env.policy.version
        # The latest stored deciles, the full refresh's: a revalue computes none.
        assert after[symbol].deciles_refresh_id == before[symbol].deciles_refresh_id == 1
        assert (after[symbol].value, after[symbol].phase) == (
            before[symbol].value,
            before[symbol].phase,
        )
    assert row.calibration is not None and row.calibration["total"] == len(ADMITTED)
    assert row.calibration["valued"] == 4
    assert row.calibration["refused"] == {NO_TARGET: 1}
    assert row.calibration["universe"] == {"admitted": len(ADMITTED), "excluded": {}}
    # No universe, fetch, rates or deciles stage: the backfill, the moat table, then the value
    # stage, its start and each company.
    assert [p.stage for p in env.progress] == (
        ["backfill", "moat"] + ["value"] * (1 + len(ADMITTED)) + ["done"]
    )
    last = env.progress[-1]
    assert (last.stage, last.done, last.failed, last.remaining) == ("done", 5, 0, 0)


def test_revalue_backfills_the_six_lines_before_valuing(env_valued: Env) -> None:
    """The store as it was before the normalizer kept the six lines: the revalue writes them
    again from the stored payloads, each citing its payload's response, with no vendor call."""
    env = env_valued
    lines = ", ".join(f"'{field}'" for field in SIX_LINES)
    with closing(env.connect()) as conn:
        kept = conn.execute(
            f"SELECT symbol, dataset, period_end, field, response_id FROM facts"
            f" WHERE field IN ({lines}) ORDER BY 1, 2, 3, 4, 5"
        ).fetchall()
        assert kept
        with conn:
            conn.execute(f"DELETE FROM facts WHERE field IN ({lines})")
    env.refresh().run("revalue")
    with closing(env.connect()) as conn:
        written = conn.execute(
            f"SELECT symbol, dataset, period_end, field, response_id FROM facts"
            f" WHERE field IN ({lines}) ORDER BY 1, 2, 3, 4, 5"
        ).fetchall()
    assert [tuple(row) for row in written] == [tuple(row) for row in kept]
    assert env.router.calls == Counter()


def test_revalue_refuses_a_company_without_facts(env_valued: Env) -> None:
    env = env_valued
    nofacts = CompanyRow(
        symbol="NOFACTS",
        refresh_id=1,  # the latest universe, the full refresh's
        name="Nofacts Corp",
        exchange="NASDAQ",
        sector="Industrials",
        industry="Specialty Industrial Machinery",
        country="US",
        currency="USD",
        is_adr=False,
        cap_band="mid",
        market_cap=Decimal(3_000_000_000),
        eligible=True,
        exclusion_reason=None,
        observed_at=env.clock(),
    )
    with closing(env.connect()) as conn:
        insert_companies(conn, [nofacts])
    refresh_id = env.refresh().run("revalue")
    row = env.last()
    assert (row.id, row.status) == (refresh_id, "done")
    assert [symbol for symbol, _, _ in env.items(refresh_id)] == sorted([*ADMITTED, "NOFACTS"])
    assert env.snapshot("NOFACTS").refresh_id == refresh_id
    assert env.snapshot("NOFACTS").value is None and env.snapshot("NOFACTS").refusal
    assert env.snapshot("ACME").refresh_id == refresh_id and env.snapshot("ACME").value is not None
    assert row.calibration is not None and row.calibration["total"] == len(ADMITTED) + 1
    assert row.calibration["refused"] == {NO_TARGET: 1, NO_STATEMENTS: 1}
    assert env.router.calls == Counter()


def test_revalue_without_a_universe_values_every_snapshot(env_without_universe: Env) -> None:
    """Before any full refresh, the companies a scoped refresh valued are the symbols, as the
    price refresh takes them; with no deciles stored, each is the same refusal again."""
    env = env_without_universe
    scoped = env.run(["ACME", "BOLT"])  # no deciles yet: two refusals
    env.router.calls.clear()
    refresh_id = env.refresh().run("revalue")
    row = env.last()
    assert (row.id, row.kind, row.status) == (refresh_id, "revalue", "done")
    assert refresh_id > scoped and env.router.calls == Counter()
    assert env.items(refresh_id) == [("ACME", "valued", None), ("BOLT", "valued", None)]
    for symbol in ("ACME", "BOLT"):
        snapshot = env.snapshot(symbol)
        assert (snapshot.refresh_id, snapshot.refusal) == (refresh_id, "no universe deciles yet")
    assert row.calibration is not None and row.calibration["total"] == 2
    assert row.calibration["refused"] == {"no universe deciles yet": 2}


def test_revalue_without_an_fmp_client(env_valued: Env) -> None:
    env = env_valued
    refresh = Refresh(
        env.connect,
        None,
        env.policy,
        env.tax,
        env.clock,
        threading.Event(),
        env.progress.append,
        (),
        moat=env.moat,
    )
    assert refresh.run("revalue") > 1
    assert env.last().status == "done"


def test_revalue_runs_under_the_overlay(env_valued: Env) -> None:
    """A hurdle rate of 10% saved over the file's 9%: the revalue runs under the effective policy,
    so the record and every new snapshot carry the overlay's hash, and a Mature Growth value
    moves."""
    env = env_valued
    before = snapshots_of(env)
    with closing(env.connect()) as conn:
        write_settings(conn, {"required_return": 0.1}, None, env.clock())
        policy = effective_policy(conn)
    assert policy.required_return == 0.1
    assert policy.settings_hash != EMPTY_SETTINGS_HASH == before["ACME"].settings_hash
    refresh = Refresh(
        env.connect,
        None,
        policy,
        env.tax,
        env.clock,
        threading.Event(),
        env.progress.append,
        (),
        moat=env.moat,
    )
    refresh_id = refresh.run("revalue")
    row = env.last()
    assert (row.id, row.status, row.settings_hash) == (refresh_id, "done", policy.settings_hash)
    after = snapshots_of(env)
    for symbol in ADMITTED:
        assert after[symbol].refresh_id == refresh_id
        assert after[symbol].settings_hash == policy.settings_hash
        assert after[symbol].result.settings_hash == policy.settings_hash
    assert before["ACME"].phase == after["ACME"].phase == "Mature Growth"
    assert before["ACME"].value is not None and after["ACME"].value is not None
    assert after["ACME"].value < before["ACME"].value  # a higher hurdle, a lower value


def test_every_refresh_that_values_loads_the_moat_file_first(env_valued: Env) -> None:
    """A full refresh, a scoped refresh and a revalue each read their moat table into the database
    after the backfill, before the value stage (spec 2026-11-19 8.4): a file row for each company
    of the table, an earlier table's rows replaced where they differ. A price refresh values
    nothing and loads none."""
    env = env_valued
    assert moat_rows(env) == file_rows(env.moat)  # the fixture's full refresh loaded it
    runs: tuple[tuple[Kind, list[str] | None, list[str]], ...] = (
        ("full", None, ["universe", "fetch", "rates", "deciles"]),
        ("scoped", ["ACME"], ["fetch", "rates"]),
        ("revalue", None, []),
    )
    for day, (kind, symbols, first) in enumerate(runs, start=20):
        table = moat_table(MOAT_CLASSES, judged=date(2026, 11, day))
        env.progress.clear()
        refresh_id = env.refresh(moat=table).run(kind, symbols)
        assert env.last().status == "done", kind
        stages = list(dict.fromkeys(p.stage for p in env.progress))
        assert stages == [*first, "backfill", "moat", "value", "done"], kind
        moat = [p for p in env.progress if p.stage == "moat"]
        assert moat == [Progress(refresh_id, "moat", 0, 0, 0, None)], kind
        assert moat_rows(env) == file_rows(table), kind
    env.progress.clear()
    env.refresh(moat=moat_table({"ACME": "Wide"})).run("price")
    assert "moat" not in {p.stage for p in env.progress}
    assert moat_rows(env) == file_rows(table)


def test_a_revalue_that_names_companies_values_those_alone(env_valued: Env) -> None:
    """In the order named, on the facts the store holds, with no vendor call; the record names
    them and, as a scoped refresh's, saves no calibration (spec 2026-11-19 8.6). The record's
    items read in symbol order (``refreshes.items``)."""
    env = env_valued
    before = snapshots_of(env)
    refresh_id = env.refresh().run("revalue", ["KRON", "ACME"])
    assert env.items(refresh_id) == [("ACME", "valued", None), ("KRON", "valued", None)]
    row = env.last()
    assert (row.id, row.kind, row.status, row.stage) == (refresh_id, "revalue", "done", "done")
    assert row.symbols == ("KRON", "ACME") and row.calibration is None and row.message is None
    assert env.router.calls == Counter()
    after = snapshots_of(env)
    assert {s for s in ADMITTED if after[s].id != before[s].id} == {"ACME", "KRON"}
    assert after["KRON"].refresh_id == after["ACME"].refresh_id == refresh_id
    assert after["KRON"].id < after["ACME"].id  # valued in the order named
    for symbol in ("ACME", "KRON"):
        assert (after[symbol].value, after[symbol].phase) == (
            before[symbol].value,
            before[symbol].phase,
        )
    assert [p.stage for p in env.progress] == ["backfill", "moat"] + ["value"] * 3 + ["done"]
    last = env.progress[-1]
    assert (last.stage, last.done, last.failed, last.remaining) == ("done", 2, 0, 0)


def test_revalue_company(env_valued: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """The revalue of one company inside its caller's transaction (spec 2026-11-19 8.6): a revalue
    record naming it, the stage moat, then its value stage, the record done; its one snapshot, the
    others' standing, with no vendor call; a review follows the snapshot."""
    env = env_valued
    belief = override_acme(env)
    before = snapshots_of(env)
    stages: list[str] = []
    set_stage = run_module.set_stage

    def record_stage(conn: Any, refresh_id: int, stage: str) -> None:
        stages.append(stage)
        set_stage(conn, refresh_id, stage)

    monkeypatch.setattr(run_module, "set_stage", record_stage)
    table = moat_table({**MOAT_CLASSES, "NEWCO": "Wide"}, judged=date(2026, 11, 21))
    with closing(env.connect()) as conn:
        with transaction(conn, immediate=True):
            snapshot_id = revalue_company(conn, "ACME", env.policy, env.tax, table, env.clock)
        review = latest_review(conn, "ACME")
    row = env.last()
    assert (row.id, row.kind, row.symbols, row.status, row.stage) == (
        2,
        "revalue",
        ("ACME",),
        "done",
        "done",
    )
    assert (row.message, row.calibration, row.policy_version) == (None, None, env.policy.version)
    assert (row.method_version, row.settings_hash) == (METHOD_VERSION, env.policy.settings_hash)
    assert stages == ["moat", "value", "done"]
    assert env.items(2) == [("ACME", "valued", None)]
    assert moat_rows(env) == file_rows(table)
    after = snapshots_of(env)
    assert (after["ACME"].id, after["ACME"].refresh_id) == (snapshot_id, 2)
    assert (after["ACME"].value, after["ACME"].phase) == (before["ACME"].value, "Mature Growth")
    assert {s: after[s].id for s in ADMITTED if s != "ACME"} == {
        s: before[s].id for s in ADMITTED if s != "ACME"
    }
    assert review is not None
    assert (review.snapshot_id, review.refresh_id, review.override_ids) == (
        snapshot_id,
        2,
        (belief,),
    )
    assert env.router.calls == Counter() and env.progress == []


def test_revalue_company_while_a_refresh_runs(env_valued: Env) -> None:
    """``RefreshRunning`` with the running refresh's id; the caller's transaction rolls back and
    the store holds what it held."""
    env = env_valued
    before = snapshots_of(env)
    with closing(env.connect()) as conn:
        running = create_refresh(
            conn,
            "scoped",
            ["AXLE"],
            env.policy.version,
            METHOD_VERSION,
            env.clock(),
            env.policy.settings_hash,
        )
        with pytest.raises(RefreshRunning) as raised, transaction(conn, immediate=True):
            revalue_company(conn, "ACME", env.policy, env.tax, env.moat, env.clock)
    assert raised.value.refresh_id == running
    assert env.last().id == running and snapshots_of(env) == before


def test_revalue_company_raises_what_it_meets(
    env_valued: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Where the value stage gives a company a refusal for an exception, the revalue of one company
    lets it rise: the caller's transaction rolls back, its record with it, and the company keeps
    its snapshot."""
    env = env_valued
    before = snapshots_of(env)

    def broken(*args: Any) -> Any:
        raise RuntimeError("assembly broke")

    monkeypatch.setattr(run_module, "build_inputs", broken)
    with (
        closing(env.connect()) as conn,
        pytest.raises(RuntimeError, match="assembly broke"),
        transaction(conn, immediate=True),
    ):
        revalue_company(conn, "ACME", env.policy, env.tax, env.moat, env.clock)
    assert env.last().id == 1 and snapshots_of(env) == before


def test_cli_revalue_prints_calibration(
    env_valued: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """No keys file and no key in the environment: the revalue reads none and builds no client."""
    env = env_valued
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(env.db_path.parent))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)

    def no_clients(*args: Any) -> Any:
        raise AssertionError("a revalue builds no vendor client")

    monkeypatch.setattr(cli, "build_clients", no_clients)
    monkeypatch.setattr(cli, "utcnow", env.clock)
    monkeypatch.setattr(cli, "load_moat_table", lambda: env.moat)
    assert cli.main(["refresh", "--kind", "revalue"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "backfill: 0 done, 0 failed, 0 to go",
        "moat: 0 done, 0 failed, 0 to go",
        "value: 0 done, 0 failed, 5 to go",
        "value: 1 done, 0 failed, 4 to go",
        "value: 2 done, 0 failed, 3 to go",
        "value: 3 done, 0 failed, 2 to go",
        "value: 4 done, 0 failed, 1 to go",
        "value: 5 done, 0 failed, 0 to go",
        "done: 5 done, 0 failed, 0 to go",
        "refresh 2: done",
        "5 companies · 4 valued · 1 flagged by a classifier check",
        "Start-up: 0",
        "Young Growth: 1",
        "High Growth: 0",
        "Mature Growth: 3",
        "Mature Stable: 1",
        "Decline: 0",
        "unclassified: 0",
        f"1 refused: {NO_TARGET}",
    ]
    assert env.last().kind == "revalue"
    assert env.router.calls == Counter()


def test_cli_revalue_with_symbols(
    env_valued: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """``refresh ACME --kind revalue`` values ACME alone, reading no key and building no client,
    and prints its snapshot's line, as a scoped refresh does, with no calibration."""
    env = env_valued
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(env.db_path.parent))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)

    def no_clients(*args: Any) -> Any:
        raise AssertionError("a revalue builds no vendor client")

    monkeypatch.setattr(cli, "build_clients", no_clients)
    monkeypatch.setattr(cli, "utcnow", env.clock)
    monkeypatch.setattr(cli, "load_moat_table", lambda: env.moat)
    assert cli.main(["refresh", "ACME", "--kind", "revalue"]) == 0
    *lines, acme = capsys.readouterr().out.splitlines()
    assert lines == [
        "backfill: 0 done, 0 failed, 0 to go",
        "moat: 0 done, 0 failed, 0 to go",
        "value: 0 done, 0 failed, 1 to go",
        "value: 1 done, 0 failed, 0 to go",
        "done: 1 done, 0 failed, 0 to go",
        "refresh 2: done",
    ]
    assert acme.startswith("ACME  Mature Growth  value ")
    row = env.last()
    assert (row.id, row.kind, row.symbols, row.calibration) == (2, "revalue", ("ACME",), None)
    assert env.items(2) == [("ACME", "valued", None)]
    assert env.router.calls == Counter()


def test_cli_revalue_runs_under_the_overlay(
    env_valued: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The command reads the effective policy from the database when it starts: the settings the
    page saved are the run's."""
    env = env_valued
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(env.db_path.parent))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(cli, "utcnow", env.clock)
    monkeypatch.setattr(cli, "load_moat_table", lambda: env.moat)
    with closing(env.connect()) as conn:
        saved = write_settings(conn, {"required_return": 0.1}, None, env.clock())
    assert saved.settings_hash != EMPTY_SETTINGS_HASH
    assert cli.main(["refresh", "--kind", "revalue"]) == 0
    assert "refresh 2: done" in capsys.readouterr().out.splitlines()
    assert (env.last().id, env.last().settings_hash) == (2, saved.settings_hash)
    assert {env.snapshot(symbol).settings_hash for symbol in ADMITTED} == {saved.settings_hash}


def test_cli_refuses_a_stored_setting_outside_its_range(
    env_valued: Env,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A stored setting outside its range is one line naming it, before any record, never a
    traceback."""
    env = env_valued
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(env.db_path.parent))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with closing(env.connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (name, value, changed_at) VALUES ('required_return', '0.5', ?)",
            (env.clock().isoformat(),),
        )
    assert cli.main(["refresh", "--kind", "revalue"]) == 2
    err = capsys.readouterr().err
    assert err.startswith(
        "settings: required_return: must be from 4% to 20%; reset it on the Settings page"
    )
    assert env.last().id == 1
