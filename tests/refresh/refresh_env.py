"""The refresh tests' environment: a migrated database, the clients over the fixture router and the
helpers that read back what a refresh wrote. ``conftest.py`` builds it; the tests in this directory
import it as ``refresh_env`` (pytest puts the directory on the path)."""

import sqlite3
import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pytest
from vendor_double import FMP_KEY, GF_TOKEN, Clients, Clock, Router

from fairband import __main__ as cli
from fairband.config import Keys
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.refresh.run import Progress, Refresh
from fairband.store.db import connect
from fairband.store.refreshes import RefreshRow, items, latest_refresh
from fairband.store.snapshots import SnapshotRow, latest_snapshot


@dataclass
class Env:
    """A migrated database, and the clients over the router. ``universe_id`` is the refresh whose
    universe the database lists, 0 when it lists none. ``progress`` collects every event of every
    refresh built by ``refresh``."""

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
