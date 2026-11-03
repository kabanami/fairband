"""The revalue over the four companies a full refresh of ``fixture_universe`` valued, on a
migrated temporary database: a new snapshot of each company from the facts the store holds, with
no vendor call and no FMP client, and the command.

The full refresh values ACME, AXLE and MILD and refuses NEWT (Young Growth, with no mature peer
for a target margin); the revalue, on the same facts and deciles, gives the same calibration.
"""

import threading
from collections import Counter
from contextlib import closing
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fixture_universe import ADMITTED, serve_universe
from refresh_env import Env
from synthetic import SIX_LINES

from fairband import __main__ as cli
from fairband.engine import METHOD_VERSION
from fairband.refresh.run import Refresh
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.snapshots import SnapshotRow

NO_TARGET = "no target margin: 0 mature peers"
NO_STATEMENTS = "no financial statements"


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
    assert row.calibration["valued"] == 3 and row.calibration["refused"] == {NO_TARGET: 1}
    assert row.calibration["universe"] == {"admitted": len(ADMITTED), "excluded": {}}
    # No universe, fetch or deciles stage: the backfill, then the value stage, its start and
    # each company.
    assert [p.stage for p in env.progress] == (
        ["backfill"] + ["value"] * (1 + len(ADMITTED)) + ["done"]
    )
    last = env.progress[-1]
    assert (last.stage, last.done, last.failed, last.remaining) == ("done", 4, 0, 0)


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
        None,
        env.policy,
        env.tax,
        env.clock,
        threading.Event(),
        env.progress.append,
        (),
    )
    assert refresh.run("revalue") > 1
    assert env.last().status == "done"


def test_revalue_takes_no_symbols(env_valued: Env) -> None:
    with pytest.raises(ValueError, match="takes no symbols"):
        env_valued.refresh().run("revalue", ["ACME"])
    assert env_valued.last().id == 1


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
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)

    def no_clients(*args: Any) -> Any:
        raise AssertionError("a revalue builds no vendor client")

    monkeypatch.setattr(cli, "build_clients", no_clients)
    monkeypatch.setattr(cli, "utcnow", env.clock)
    assert cli.main(["refresh", "--kind", "revalue"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "backfill: 0 done, 0 failed, 0 to go",
        "value: 0 done, 0 failed, 4 to go",
        "value: 1 done, 0 failed, 3 to go",
        "value: 2 done, 0 failed, 2 to go",
        "value: 3 done, 0 failed, 1 to go",
        "value: 4 done, 0 failed, 0 to go",
        "done: 4 done, 0 failed, 0 to go",
        "refresh 2: done",
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
    assert env.last().kind == "revalue"
    assert env.router.calls == Counter()
