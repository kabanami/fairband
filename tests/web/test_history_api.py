"""The band's history read (spec 2026-11-06 Tier 2, 18.4) on the database of ``conftest.py``: AAPL,
AAL and HGCO, each with one snapshot, AAPL's valued and priced 30 Oct 2026 at $150, AAL's refused.
Each test adds AAPL snapshots of its own."""

from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from support.web import CREATED

from fairband.engine.types import Levels, ValuationResult
from fairband.store.db import connect
from fairband.store.snapshots import insert_snapshot, latest_snapshot


def _add(db_path: Path, result: ValuationResult) -> int:
    """``result`` as a snapshot under the fixture's refresh; its id."""
    with closing(connect(db_path)) as conn:
        first = latest_snapshot(conn, "AAL")
        assert first is not None
        return insert_snapshot(conn, result, first.refresh_id, clock=lambda: CREATED)


def _point(snapshot_id: int, day: str, price: float, levels: Levels | None) -> dict[str, object]:
    return {
        "day": day,
        "price": price,
        "fairLow": None if levels is None else levels.fair_low,
        "fairHigh": None if levels is None else levels.fair_high,
        "buyLevel": None if levels is None else levels.buy,
        "trimLevel": None if levels is None else levels.trim,
        "snapshotId": snapshot_id,
    }


def test_the_band_history_is_one_point_per_snapshot(
    client: TestClient, db_path: Path, results: dict[str, ValuationResult]
) -> None:
    """One point a snapshot with a price date, oldest day first, each with its levels; of two
    snapshots priced on one day the later one; a refused snapshot's point carries its price and no
    band."""
    aapl = results["AAPL"]
    with closing(connect(db_path)) as conn:
        first = latest_snapshot(conn, "AAPL")
    assert first is not None and first.price_date == date(2026, 10, 30)
    earlier = Levels(buy=100.0, fair_low=120.0, fair_high=140.0, trim=160.0)
    later = Levels(buy=110.0, fair_low=130.0, fair_high=150.0, trim=170.0)
    september = _add(  # an earlier day, written after the fixture's
        db_path, replace(aapl, levels=earlier, price=125.0, price_date=date(2026, 9, 30))
    )
    same_day = _add(db_path, replace(aapl, levels=later))  # 30 Oct again: it replaces the first
    refused = _add(
        db_path,
        replace(
            aapl,
            value=None,
            levels=None,
            price_to_value=None,
            designation=None,
            refusal="no target margin: 0 mature peers",
            price=140.0,
            price_date=date(2026, 11, 2),
        ),
    )
    found = client.get("/api/companies/AAPL/band-history").json()
    assert found == {
        "symbol": "AAPL",
        "points": [
            _point(september, "2026-09-30", 125.0, earlier),
            _point(same_day, "2026-10-30", 150.0, later),
            _point(refused, "2026-11-02", 140.0, None),
        ],
    }
    [aal] = client.get("/api/companies/AAL/band-history").json()["points"]
    assert (aal["fairLow"], aal["fairHigh"]) == (None, None)  # the fixture's refusal
    assert aal["price"] == results["AAL"].price


def test_a_company_before_its_first_snapshot_has_no_points(
    client: TestClient, db_path: Path
) -> None:
    with closing(connect(db_path)) as conn:
        conn.execute("DELETE FROM snapshots WHERE symbol = 'HGCO'")
        conn.commit()
    assert client.get("/api/companies/HGCO/band-history").json() == {
        "symbol": "HGCO",
        "points": [],
    }


def test_an_unknown_symbol_is_404(client: TestClient) -> None:
    r = client.get("/api/companies/NOPE/band-history")
    assert r.status_code == 404
    assert r.json() == {"detail": "no company NOPE"}
    assert client.get("/api/companies/a%20b/band-history").status_code == 400
