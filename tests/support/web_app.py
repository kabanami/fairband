"""The web tests' fixtures, which the MCP tests share: the packaged policy, the engine's three test
companies valued under it, a migrated database that lists them in the universe of one finished full
refresh, and clients of an app over that database. The plain names they use are in
``support.web``; a directory's ``conftest.py`` imports the fixtures it uses from here.

AAPL is valued on the Mature Growth route; AAL, a Young Growth company with no mature peers, is
refused for its target margin; HGCO, the High Growth company, is valued on the revenue growth
route."""

from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fairband.engine import METHOD_VERSION
from fairband.engine.route import value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy, load_policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.store.companies import insert_companies
from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh, set_stage
from fairband.store.snapshots import insert_snapshot
from fairband.web.app import create_app
from support.engine_companies import (
    high_growth_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.web import (
    CALIBRATION,
    CREATED,
    FINISHED,
    HOST,
    NOW,
    STARTED,
    TODAY,
    _company,
    _settings,
)


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def results(policy: Policy) -> dict[str, ValuationResult]:
    deciles = universe_deciles()
    valued = value_company(replace(mature_growth_inputs(), symbol="AAPL"), deciles, policy, TODAY)
    no_peers = replace(young_growth_inputs(), symbol="AAL", peers=())
    refused = value_company(no_peers, deciles, policy, TODAY)
    growth = value_company(high_growth_inputs(), deciles, policy, TODAY)
    assert valued.value is not None and refused.value is None
    assert growth.symbol == "HGCO" and growth.route == "revenue-growth"
    return {"AAPL": valued, "AAL": refused, "HGCO": growth}


@pytest.fixture
def db_path(tmp_path: Path, policy: Policy, results: dict[str, ValuationResult]) -> Path:
    path = tmp_path / "data" / "fairband.db"
    with closing(connect(path)) as conn:
        migrate(conn)
        refresh_id = create_refresh(
            conn, "full", None, policy.version, METHOD_VERSION, STARTED, EMPTY_SETTINGS_HASH
        )
        insert_companies(
            conn,
            [
                _company("AAPL", refresh_id, "Mature Growth Co", Decimal(150_000_000_000)),
                _company("AAL", refresh_id, "Young Growth Co", Decimal(4_000_000_000)),
                _company("HGCO", refresh_id, "High Growth Co", Decimal(15_000_000_000)),
            ],
        )
        for result in results.values():
            insert_snapshot(conn, result, refresh_id, clock=lambda: CREATED)
        set_stage(conn, refresh_id, "done")
        finish_refresh(conn, refresh_id, "done", FINISHED, "3 valued or refused", CALIBRATION)
    return path


@pytest.fixture
def client_with_clock(
    tmp_path: Path, db_path: Path, policy: Policy
) -> Iterator[Callable[[datetime], TestClient]]:
    """Makes a client of an app whose clock reads ``now``."""
    clients: list[TestClient] = []

    def make(now: datetime) -> TestClient:
        app = create_app(
            _settings(tmp_path, db_path), policy, lambda: connect(db_path), clock=lambda: now
        )
        clients.append(TestClient(app, base_url=HOST))
        return clients[-1]

    yield make
    for c in clients:
        c.close()


@pytest.fixture
def client(client_with_clock: Callable[[datetime], TestClient]) -> TestClient:
    return client_with_clock(NOW)
