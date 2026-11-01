"""The group view, ``GET /api/groups``, on a temporary migrated database: the screen's rows grouped
by sector, phase or cap band, with each group's count, the companies with a value, the median
price ÷ value and the share below the buy level.

The universe of one full refresh admits six companies:

- AAPL, BBB and CCC: the engine's Mature Growth company (value $113.70, buy $85.28) at $150, $80
  and $100; Technology, the first mega cap, the others mid.
- STBL: the engine's Mature Stable company at $40, above its $31.73 buy level; Industrials, mid.
- AAL: the engine's Young Growth company, refused; Technology, mid.
- NEWC: Industrials, no cap band, not valued yet (no snapshot, so no phase).

FIRB, valued like AAPL, is listed but not admitted: it has no row on the screen, so in no group.
"""

import statistics
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import (
    mature_growth_inputs,
    mature_stable_inputs,
    universe_deciles,
    young_growth_inputs,
)

from fairband.config import DEFAULT_PORT, Settings
from fairband.engine import METHOD_VERSION
from fairband.engine.route import reprice, value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy, load_policy
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh
from fairband.store.snapshots import insert_snapshot
from fairband.web.app import create_app

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
HOST = "http://127.0.0.1:8470"
EMPTY = {"valued": 0, "medianPriceToValue": None, "shareBelowBuy": None}


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def results(policy: Policy) -> dict[str, ValuationResult]:
    deciles = universe_deciles()

    def value(inputs: Any, symbol: str) -> ValuationResult:
        return value_company(replace(inputs, symbol=symbol), deciles, policy, TODAY)

    aapl = value(mature_growth_inputs(), "AAPL")
    assert aapl.price == 150.0 and aapl.value is not None
    return {
        "AAPL": aapl,
        "BBB": reprice(value(mature_growth_inputs(), "BBB"), 80.0, TODAY, policy),
        "CCC": reprice(value(mature_growth_inputs(), "CCC"), 100.0, TODAY, policy),
        "STBL": value(mature_stable_inputs(), "STBL"),
        "AAL": value(young_growth_inputs(), "AAL"),
        "FIRB": value(mature_growth_inputs(), "FIRB"),
    }


def company(symbol: str, refresh_id: int, sector: str, cap_band: str | None) -> CompanyRow:
    return CompanyRow(
        symbol=symbol,
        refresh_id=refresh_id,
        name=f"{symbol} Co",
        exchange="NASDAQ",
        sector=sector,
        industry="Software - Application",
        country="US",
        currency="USD",
        is_adr=False,
        cap_band=cap_band,
        market_cap=Decimal(4_000_000_000),
        eligible=True,
        exclusion_reason=None,
        observed_at=NOW,
    )


def make_client(tmp_path: Path, db_path: Path, policy: Policy) -> TestClient:
    settings = Settings(db_path.parent, tmp_path / "config", db_path, DEFAULT_PORT)
    app = create_app(settings, policy, lambda: connect(db_path), clock=lambda: NOW)
    return TestClient(app, base_url=HOST)


def seed(
    db_path: Path,
    policy: Policy,
    listed: list[CompanyRow],
    results: list[ValuationResult],
) -> None:
    """One finished full refresh (id 1) whose universe lists ``listed`` and holds ``results``."""
    with closing(connect(db_path)) as conn:
        migrate(conn)
        refresh_id = create_refresh(conn, "full", None, policy.version, METHOD_VERSION, NOW)
        assert refresh_id == 1
        insert_companies(conn, listed)
        for result in results:
            insert_snapshot(conn, result, refresh_id, clock=lambda: NOW)
        finish_refresh(conn, refresh_id, "done", NOW)


@pytest.fixture
def client(
    tmp_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> Iterator[TestClient]:
    db_path = tmp_path / "data" / "fairband.db"
    listed = [
        company("AAPL", 1, "Technology", "mega"),
        company("BBB", 1, "Technology", "mid"),
        company("CCC", 1, "Technology", "mid"),
        company("STBL", 1, "Industrials", "mid"),
        company("AAL", 1, "Technology", "mid"),
        company("NEWC", 1, "Industrials", None),
        replace(company("FIRB", 1, "Financial Services", "mid"), eligible=False),
    ]
    seed(db_path, policy, listed, list(results.values()))
    with make_client(tmp_path, db_path, policy) as c:
        yield c


def groups(client: TestClient, by: str) -> list[dict[str, Any]]:
    response = client.get(f"/api/groups?by={by}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == {"by", "groups"} and body["by"] == by
    found: list[dict[str, Any]] = body["groups"]
    return found


def ratio(results: dict[str, ValuationResult], symbol: str) -> float:
    r = results[symbol]
    assert r.price is not None and r.value is not None
    return r.price / r.value


def test_groups_by_phase_median_and_share(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    growth = [ratio(results, symbol) for symbol in ("AAPL", "BBB", "CCC")]
    assert statistics.median(growth) == ratio(results, "CCC")  # $100 against the same value
    assert groups(client, "phase") == [
        {
            "name": "Mature Growth",
            "count": 3,
            "valued": 3,
            "medianPriceToValue": pytest.approx(statistics.median(growth)),
            "shareBelowBuy": pytest.approx(1 / 3),  # BBB alone, $80 under the $85.28 buy level
        },
        {
            "name": "Mature Stable",
            "count": 1,
            "valued": 1,
            "medianPriceToValue": pytest.approx(ratio(results, "STBL")),
            "shareBelowBuy": 0.0,
        },
        {"name": "Young Growth", "count": 1, **EMPTY},
        {"name": "unclassified", "count": 1, **EMPTY},  # NEWC, with no snapshot yet
    ]


def test_groups_by_sector_and_cap(client: TestClient, results: dict[str, ValuationResult]) -> None:
    growth = statistics.median(ratio(results, symbol) for symbol in ("AAPL", "BBB", "CCC"))
    assert groups(client, "sector") == [
        {
            "name": "Industrials",
            "count": 2,
            "valued": 1,
            "medianPriceToValue": pytest.approx(ratio(results, "STBL")),
            "shareBelowBuy": 0.0,
        },
        {
            "name": "Technology",
            "count": 4,
            "valued": 3,
            "medianPriceToValue": pytest.approx(growth),
            "shareBelowBuy": pytest.approx(1 / 3),
        },
    ]
    mid = statistics.median(ratio(results, symbol) for symbol in ("BBB", "CCC", "STBL"))
    assert groups(client, "cap") == [
        {
            "name": "mega",
            "count": 1,
            "valued": 1,
            "medianPriceToValue": pytest.approx(ratio(results, "AAPL")),
            "shareBelowBuy": 0.0,
        },
        {
            "name": "mid",
            "count": 4,
            "valued": 3,
            "medianPriceToValue": pytest.approx(mid),
            "shareBelowBuy": pytest.approx(1 / 3),
        },
        {"name": "none", "count": 1, **EMPTY},
    ]


def test_groups_null_when_no_values(
    tmp_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Only a refusal and a company not valued yet: every group counts its rows and has no
    median and no share."""
    db_path = tmp_path / "data" / "fairband.db"
    listed = [company("AAL", 1, "Technology", "mid"), company("NEWC", 1, "Industrials", None)]
    seed(db_path, policy, listed, [results["AAL"]])
    with make_client(tmp_path, db_path, policy) as c:
        assert groups(c, "sector") == [
            {"name": "Industrials", "count": 1, **EMPTY},
            {"name": "Technology", "count": 1, **EMPTY},
        ]
        assert groups(c, "phase") == [
            {"name": "Young Growth", "count": 1, **EMPTY},
            {"name": "unclassified", "count": 1, **EMPTY},
        ]
        assert groups(c, "cap") == [
            {"name": "mid", "count": 1, **EMPTY},
            {"name": "none", "count": 1, **EMPTY},
        ]

    empty = tmp_path / "empty" / "fairband.db"
    with closing(connect(empty)) as conn:
        migrate(conn)
    with make_client(tmp_path, empty, policy) as c:
        assert groups(c, "phase") == []


def test_groups_unknown_by_400(client: TestClient) -> None:
    response = client.get("/api/groups?by=industry")
    assert (response.status_code, response.json()) == (
        400,
        {"detail": "by must be sector, phase or cap, not industry"},
    )
    response = client.get("/api/groups")
    assert (response.status_code, response.json()) == (400, {"detail": "by: Field required"})
