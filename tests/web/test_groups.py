"""The groups, ``GET /api/groups``, which the Methodology page counts by phase, on a temporary
migrated database: the screen's rows grouped by sector, phase or cap band, with each group's count,
the companies with a value, the median price ÷ value and the share below value (price ÷ value
under the second designation edge, 0.85). The phase is the classifier's, whatever phase a review
shows on the row (spec 2026-11-23 refresh experience, 4.4). The Statistics view reads its own
route, on the figures the Screen shows (``test_statistics.py``).

The universe of one full refresh admits six companies:

- AAPL, BBB and CCC: the engine's Mature Growth company (value $127.68) at $150, $80 and $120
  (1.17, 0.63 and 0.94 × the value); Technology, the first mega cap, the others mid.
- STBL: the engine's Mature Stable company (value $43.85) at $40, 0.91 × the value; Industrials,
  mid.
- AAL: the engine's Young Growth company with no mature peers, refused for its target margin;
  Technology, mid.
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
from fairband.engine.review import Review
from fairband.engine.route import reprice, value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy, load_policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.db import connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh
from fairband.store.reviews import insert_review
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.web.app import create_app
from fairband.web.rows import group_rows

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
HOST = "http://127.0.0.1:8470"
EMPTY = {"valued": 0, "medianPriceToValue": None, "shareBelowValue": None}


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
        "CCC": reprice(value(mature_growth_inputs(), "CCC"), 120.0, TODAY, policy),
        "STBL": value(mature_stable_inputs(), "STBL"),
        "AAL": value(replace(young_growth_inputs(), peers=()), "AAL"),
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
        refresh_id = create_refresh(
            conn, "full", None, policy.version, METHOD_VERSION, NOW, EMPTY_SETTINGS_HASH
        )
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


def test_group_rows_counts_below_value_under_the_figure_it_is_given() -> None:
    """Spec 2026-11-23 thresholds, 5.3: the first edge is each row's own, so the groups take the
    one edge every class shares, the fair band's low end: at 0.90 a row at 0.89 × its value is
    below value and one at 0.90 × is not; a row with no value counts in neither."""
    rows = [
        {"sector": "Tech", "mechanical": 100.0, "price": 89.0},
        {"sector": "Tech", "mechanical": 100.0, "price": 90.0},
        {"sector": "Tech", "mechanical": None, "price": 50.0},
    ]
    assert group_rows(rows, "sector", 0.90) == [
        {
            "name": "Tech",
            "count": 3,
            "valued": 2,
            "medianPriceToValue": pytest.approx(0.895),
            "shareBelowValue": 0.5,
        }
    ]


def test_groups_by_phase_median_and_share(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    growth = [ratio(results, symbol) for symbol in ("AAPL", "BBB", "CCC")]
    assert statistics.median(growth) == ratio(results, "CCC")  # $120 against the same value
    assert groups(client, "phase") == [
        {
            "name": "Mature Growth",
            "count": 3,
            "valued": 3,
            "medianPriceToValue": pytest.approx(statistics.median(growth)),
            "shareBelowValue": pytest.approx(1 / 3),  # BBB alone, at 0.60 × the value
        },
        {
            "name": "Mature Stable",
            "count": 1,
            "valued": 1,
            "medianPriceToValue": pytest.approx(ratio(results, "STBL")),
            "shareBelowValue": 1.0,  # STBL at 0.89 × the value, under the band's 0.90
        },
        {"name": "Young Growth", "count": 1, **EMPTY},
        {"name": "unclassified", "count": 1, **EMPTY},  # NEWC, with no snapshot yet
    ]


def test_the_groups_count_the_classifiers_phase(
    tmp_path: Path, client: TestClient, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-23 refresh experience, 4.4: a review that moves AAPL to Mature Stable moves
    its row's phase, and the groups by phase, which the Methodology page counts, stay the
    classifier's: AAPL is still counted in Mature Growth, and NEWC, with no snapshot, in
    unclassified."""
    before = groups(client, "phase")
    aapl = results["AAPL"]
    moved = replace(aapl, phase=replace(aapl.phase, phase="Mature Stable"))
    with closing(connect(tmp_path / "data" / "fairband.db")) as conn:
        snapshot = latest_snapshot(conn, "AAPL")
        assert snapshot is not None
        review = Review(moved, aapl.value, (), ())
        insert_review(conn, review, "AAPL", snapshot.id, None, clock=lambda: NOW)
    rows = {row["ticker"]: row for row in client.get("/api/screen").json()["rows"]}
    assert (rows["AAPL"]["reviewed"], rows["AAPL"]["phase"]) == (aapl.value, 5)
    assert rows["AAPL"]["mechanicalPhase"] == 4
    assert (rows["NEWC"]["phase"], rows["NEWC"]["mechanicalPhase"]) == (None, None)
    assert groups(client, "phase") == before
    assert [(g["name"], g["count"]) for g in before] == [
        ("Mature Growth", 3),
        ("Mature Stable", 1),
        ("Young Growth", 1),
        ("unclassified", 1),
    ]


def test_groups_by_sector_and_cap(client: TestClient, results: dict[str, ValuationResult]) -> None:
    growth = statistics.median(ratio(results, symbol) for symbol in ("AAPL", "BBB", "CCC"))
    assert groups(client, "sector") == [
        {
            "name": "Industrials",
            "count": 2,
            "valued": 1,
            "medianPriceToValue": pytest.approx(ratio(results, "STBL")),
            "shareBelowValue": 1.0,
        },
        {
            "name": "Technology",
            "count": 4,
            "valued": 3,
            "medianPriceToValue": pytest.approx(growth),
            "shareBelowValue": pytest.approx(1 / 3),
        },
    ]
    mid = statistics.median(ratio(results, symbol) for symbol in ("BBB", "CCC", "STBL"))
    assert groups(client, "cap") == [
        {
            "name": "mega",
            "count": 1,
            "valued": 1,
            "medianPriceToValue": pytest.approx(ratio(results, "AAPL")),
            "shareBelowValue": 0.0,
        },
        {
            "name": "mid",
            "count": 4,
            "valued": 3,
            "medianPriceToValue": pytest.approx(mid),
            "shareBelowValue": pytest.approx(2 / 3),  # BBB at 0.60 and STBL at 0.89, under 0.90
        },
        {"name": "none", "count": 1, **EMPTY},
    ]


def test_share_below_value_reads_the_second_edge(tmp_path: Path, policy: Policy) -> None:
    """LOW at 0.85 × the value is below value though above its Wide moat's buy level (0.80 ×);
    HIGH at 0.95 × is not: the group's share is one half."""
    deciles = universe_deciles()
    valued = value_company(mature_growth_inputs(), deciles, policy, TODAY)
    assert valued.value is not None and valued.levels is not None
    assert valued.levels.buy == pytest.approx(0.80 * valued.value)
    low = reprice(replace(valued, symbol="LOW"), 0.85 * valued.value, TODAY, policy)
    high = reprice(replace(valued, symbol="HIGH"), 0.95 * valued.value, TODAY, policy)
    assert (low.designation, high.designation) == ("below", "near")
    assert policy.fair_band[0] == 0.90
    db_path = tmp_path / "data" / "fairband.db"
    listed = [company("LOW", 1, "Technology", "mid"), company("HIGH", 1, "Technology", "mid")]
    seed(db_path, policy, listed, [low, high])
    with make_client(tmp_path, db_path, policy) as c:
        [group] = groups(c, "sector")
    assert group == {
        "name": "Technology",
        "count": 2,
        "valued": 2,
        "medianPriceToValue": pytest.approx(0.90),
        "shareBelowValue": 0.5,
    }


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


def test_groups_by_industry(
    tmp_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """The industry, the level under the sector, groups as the sector does (B-32): by its name,
    ``none`` for a row the universe gives no industry."""
    db_path = tmp_path / "data" / "fairband.db"
    listed = [
        replace(company("AAPL", 1, "Technology", "mega"), industry="Consumer Electronics"),
        company("BBB", 1, "Technology", "mid"),
        company("CCC", 1, "Technology", "mid"),
        replace(company("NEWC", 1, "Industrials", None), industry=None),
    ]
    seed(db_path, policy, listed, [results[symbol] for symbol in ("AAPL", "BBB", "CCC")])
    software = statistics.median(ratio(results, symbol) for symbol in ("BBB", "CCC"))
    with make_client(tmp_path, db_path, policy) as c:
        assert groups(c, "industry") == [
            {
                "name": "Consumer Electronics",
                "count": 1,
                "valued": 1,
                "medianPriceToValue": pytest.approx(ratio(results, "AAPL")),
                "shareBelowValue": 0.0,
            },
            {
                "name": "Software - Application",
                "count": 2,
                "valued": 2,
                "medianPriceToValue": pytest.approx(software),
                "shareBelowValue": 0.5,
            },
            {"name": "none", "count": 1, **EMPTY},
        ]


def test_groups_unknown_by_400(client: TestClient) -> None:
    response = client.get("/api/groups?by=country")
    assert (response.status_code, response.json()) == (
        400,
        {"detail": "by must be sector, industry, phase or cap, not country"},
    )
    response = client.get("/api/groups")
    assert (response.status_code, response.json()) == (400, {"detail": "by: Field required"})
