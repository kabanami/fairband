"""Refresh fixtures: a migrated temporary database, the policy, the vendor clients over the
fixture router of ``vendor_double`` with a settable clock and a sleep that records the seconds in
``sleeps`` and does not sleep, and the ``refresh_env.Env`` over them. The GuruFocus client is not
paced, nor the FMP client unless a test parametrizes ``fmp_calls_per_minute``."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from refresh_env import Env
from synthetic import add_company
from vendor_double import FMP_KEY, GF_TOKEN, Clients, Clock, Router

from fairband.policy import Policy, load_policy
from fairband.policy.tax import load_tax_table
from fairband.store.db import connect, migrate
from fairband.vendors import fmp, gurufocus
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorHttp

NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    with closing(connect(tmp_path / "f.db")) as conn:
        migrate(conn)
        yield conn


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def router() -> Router:
    return Router()


@pytest.fixture
def clock() -> Clock:
    return Clock(NOW)


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def fmp_calls_per_minute() -> float:
    """The FMP client's pace: 0, none, unless a test parametrizes it."""
    return 0.0


@pytest.fixture
def clients(
    router: Router, clock: Clock, policy: Policy, sleeps: list[float], fmp_calls_per_minute: float
) -> Iterator[Clients]:
    def http(base_url: str, secret: str, pace: float = 0.0) -> VendorHttp:
        return VendorHttp(
            base_url,
            [secret],
            policy.refresh,
            transport=router.transport,
            sleep=sleeps.append,
            clock=clock,
            calls_per_minute=pace,
        )

    with (
        http(fmp.BASE_URL, FMP_KEY, fmp_calls_per_minute) as fmp_http,
        http(gurufocus.BASE_URL, GF_TOKEN) as gf_http,
    ):
        yield Clients(Fmp(fmp_http, FMP_KEY), GuruFocus(gf_http, GF_TOKEN), (FMP_KEY, GF_TOKEN))


@pytest.fixture
def clients_with_500_on_quote(clients: Clients, router: Router) -> Clients:
    router.fail.add("quote")
    return clients


@pytest.fixture
def clients_no_gf(clients: Clients) -> Clients:
    return replace(clients, gf=None, secrets=(FMP_KEY,))


@pytest.fixture
def env(
    tmp_path: Path, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> Iterator[Env]:
    """A universe that lists ACME and BOLT, the fixtures' companies."""
    db_path = tmp_path / "data" / "fairband.db"
    with closing(connect(db_path)) as conn:
        migrate(conn)
        universe_id = add_company(conn, symbols=("ACME", "BOLT"))
    yield Env(db_path, universe_id, clients, router, clock, policy, load_tax_table())


@pytest.fixture
def env_without_universe(
    tmp_path: Path, clients: Clients, router: Router, clock: Clock, policy: Policy
) -> Iterator[Env]:
    """No refresh has run: no universe rows, no deciles (``universe_id`` 0, so the first
    refresh is 1)."""
    db_path = tmp_path / "data" / "fairband.db"
    with closing(connect(db_path)) as conn:
        migrate(conn)
    yield Env(db_path, 0, clients, router, clock, policy, load_tax_table())
