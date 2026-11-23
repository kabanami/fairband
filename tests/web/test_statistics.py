"""The Statistics view's read, ``GET /api/statistics``, on a temporary migrated database (spec
2026-11-23 refresh experience, 4.5): the screen's rows grouped by sector, industry, phase or cap
band as the Screen shows them, by the row's shown phase and on the row's own value, the reviewed
one where Reviewed is filled. Each group gives its count, the companies with a value, the median
price ÷ value, the share below value (price ÷ value under the fair band's low end, 0.90) and the
filter that opens the Screen on it, ``None`` for the rows ``none`` and ``unclassified``.

The universe of one full refresh admits six companies:

- AAPL: the engine's Mature Growth company (value $127.68) at $150, 1.17 × the value. Its review,
  which counts, values it at $200 as Mature Stable: the Screen shows it at 0.75 × that value,
  below value. Technology, Consumer Electronics, the one Mega cap.
- BBB and CCC: the same company at $80 and $120 (0.63 and 0.94 × the value); Technology,
  Software - Application, Mid.
- STBL: the engine's Mature Stable company (value $45.18) at $40, 0.89 × the value; Industrials,
  Software - Application, Mid.
- AAL: the engine's Young Growth company with no mature peers, refused for its target margin;
  Technology, Software - Application, Mid.
- NEWC: Industrials, no industry and no cap band, not valued yet (no snapshot, so no phase).

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
from support.web import _static_file

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
from fairband.web.rows import GROUP_BY, statistics_rows

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
HOST = "http://127.0.0.1:8470"
EMPTY = {"valued": 0, "medianPriceToValue": None, "shareBelowValue": None}
REVIEWED = 200.0  # AAPL's reviewed value
SOFTWARE = "Software - Application"


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


def company(
    symbol: str, sector: str, industry: str | None, cap_band: str | None, eligible: bool = True
) -> CompanyRow:
    return CompanyRow(
        symbol=symbol,
        refresh_id=1,
        name=f"{symbol} Co",
        exchange="NASDAQ",
        sector=sector,
        industry=industry,
        country="US",
        currency="USD",
        is_adr=False,
        cap_band=cap_band,
        market_cap=Decimal(4_000_000_000),
        eligible=eligible,
        exclusion_reason=None,
        observed_at=NOW,
    )


@pytest.fixture
def client(
    tmp_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> Iterator[TestClient]:
    """One finished full refresh (id 1) whose universe lists the seven companies and holds their
    results, and AAPL's review at $200 as Mature Stable on its snapshot."""
    db_path = tmp_path / "data" / "fairband.db"
    listed = [
        company("AAPL", "Technology", "Consumer Electronics", "Mega"),
        company("BBB", "Technology", SOFTWARE, "Mid"),
        company("CCC", "Technology", SOFTWARE, "Mid"),
        company("STBL", "Industrials", SOFTWARE, "Mid"),
        company("AAL", "Technology", SOFTWARE, "Mid"),
        company("NEWC", "Industrials", None, None),
        company("FIRB", "Financial Services", SOFTWARE, "Mid", eligible=False),
    ]
    aapl = results["AAPL"]
    moved = replace(aapl, value=REVIEWED, phase=replace(aapl.phase, phase="Mature Stable"))
    with closing(connect(db_path)) as conn:
        migrate(conn)
        refresh_id = create_refresh(
            conn, "full", None, policy.version, METHOD_VERSION, NOW, EMPTY_SETTINGS_HASH
        )
        insert_companies(conn, listed)
        for result in results.values():
            insert_snapshot(conn, result, refresh_id, clock=lambda: NOW)
        finish_refresh(conn, refresh_id, "done", NOW)
        snapshot = latest_snapshot(conn, "AAPL")
        assert snapshot is not None
        review = Review(moved, aapl.value, (), ())
        insert_review(conn, review, "AAPL", snapshot.id, None, clock=lambda: NOW)
    settings = Settings(db_path.parent, tmp_path / "config", db_path, DEFAULT_PORT)
    app = create_app(settings, policy, lambda: connect(db_path), clock=lambda: NOW)
    with TestClient(app, base_url=HOST) as c:
        yield c


def read(client: TestClient, route: str, by: str) -> list[dict[str, Any]]:
    response = client.get(f"/api/{route}?by={by}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    assert set(body) == {"by", "groups"} and body["by"] == by
    found: list[dict[str, Any]] = body["groups"]
    return found


def ratio(results: dict[str, ValuationResult], symbol: str) -> float:
    r = results[symbol]
    assert r.price is not None and r.value is not None
    return r.price / r.value


def test_statistics_rows_read_the_row_s_own_value_and_ratio() -> None:
    """A row is valued where it has a ``fairValue``, the value the Screen shows, whatever its
    mechanical value; the median and the share below read its ``priceToValue``. A valued row with
    no ratio (no price) counts in ``valued``, so in the share's base, and in no median."""
    rows = [
        {"sector": "Tech", "mechanical": None, "fairValue": 100.0, "priceToValue": 0.89},
        {"sector": "Tech", "mechanical": 100.0, "fairValue": 100.0, "priceToValue": 0.90},
        {"sector": "Tech", "mechanical": 100.0, "fairValue": 100.0, "priceToValue": None},
        {"sector": "Tech", "mechanical": 100.0, "fairValue": None, "priceToValue": None},
    ]
    assert statistics_rows(rows, "sector", 0.90) == [
        {
            "name": "Tech",
            "count": 4,
            "valued": 3,
            "medianPriceToValue": pytest.approx(0.895),
            "shareBelowValue": pytest.approx(1 / 3),
            "filter": {"sector": ["Tech"]},
        }
    ]


def test_statistics_read_the_value_the_screen_shows(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    """Spec 4.5: AAPL's review moves it to Mature Stable at $200, and Statistics counts it there,
    at 0.75 × the reviewed value, below value; the groups the Methodology page counts keep it in
    Mature Growth at 1.17 × the engine's value."""
    rows = {row["ticker"]: row for row in client.get("/api/screen").json()["rows"]}
    aapl = rows["AAPL"]
    assert (aapl["fairValue"], aapl["phase"], aapl["mechanicalPhase"]) == (REVIEWED, 5, 4)
    assert aapl["priceToValue"] == pytest.approx(150.0 / REVIEWED)
    growth = [ratio(results, symbol) for symbol in ("BBB", "CCC")]
    stable = [150.0 / REVIEWED, ratio(results, "STBL")]
    assert ratio(results, "STBL") < 0.90 < ratio(results, "CCC")
    assert read(client, "statistics", "phase") == [
        {
            "name": "Mature Growth",
            "count": 2,
            "valued": 2,
            "medianPriceToValue": pytest.approx(statistics.median(growth)),
            "shareBelowValue": 0.5,  # BBB at 0.63 × the value
            "filter": {"phase": [4]},
        },
        {
            "name": "Mature Stable",
            "count": 2,
            "valued": 2,
            "medianPriceToValue": pytest.approx(statistics.median(stable)),
            "shareBelowValue": 1.0,  # AAPL at 0.75 × its reviewed value, STBL at 0.89
            "filter": {"phase": [5]},
        },
        {"name": "Young Growth", "count": 1, **EMPTY, "filter": {"phase": [2]}},
        {"name": "unclassified", "count": 1, **EMPTY, "filter": None},
    ]
    technology = [150.0 / REVIEWED, ratio(results, "BBB"), ratio(results, "CCC")]
    [_, tech] = read(client, "statistics", "sector")
    assert tech == {
        "name": "Technology",
        "count": 4,
        "valued": 3,
        "medianPriceToValue": pytest.approx(statistics.median(technology)),  # AAPL's 0.75
        "shareBelowValue": pytest.approx(2 / 3),  # AAPL and BBB
        "filter": {"sector": ["Technology"]},
    }
    # the classifier's phase and the engine's value, for the Methodology page
    by_phase = [(g["name"], g["count"]) for g in read(client, "groups", "phase")]
    assert by_phase == [
        ("Mature Growth", 3),
        ("Mature Stable", 1),
        ("Young Growth", 1),
        ("unclassified", 1),
    ]
    [_, mechanical] = read(client, "groups", "sector")
    assert mechanical["medianPriceToValue"] == pytest.approx(ratio(results, "CCC"))


def test_a_group_s_filter_is_the_screens(client: TestClient) -> None:
    """Spec 4.5: the sector; the industry with the sorted sectors of its rows, which the Screen's
    industry menu needs; the phase as the menu's number; the cap band as the menu's id, lower
    case. The rows ``none`` and ``unclassified`` have no filter: no filter matches a field a row
    lacks."""
    filters = {
        by: [(g["name"], g["filter"]) for g in read(client, "statistics", by)] for by in GROUP_BY
    }
    assert filters == {
        "sector": [
            ("Industrials", {"sector": ["Industrials"]}),
            ("Technology", {"sector": ["Technology"]}),
        ],
        "industry": [
            (
                "Consumer Electronics",
                {"sector": ["Technology"], "industry": ["Consumer Electronics"]},
            ),
            (SOFTWARE, {"sector": ["Industrials", "Technology"], "industry": [SOFTWARE]}),
            ("none", None),
        ],
        "phase": [
            ("Mature Growth", {"phase": [4]}),
            ("Mature Stable", {"phase": [5]}),
            ("Young Growth", {"phase": [2]}),
            ("unclassified", None),
        ],
        "cap": [("Mega", {"cap": ["mega"]}), ("Mid", {"cap": ["mid"]}), ("none", None)],
    }


def test_an_industry_whose_rows_have_no_sector_has_no_filter() -> None:
    """The Screen lists an industry under the chosen sectors alone, so an industry none of whose
    rows has a sector could not be chosen: it is no link, as ``none`` is not."""
    rows = [{"sector": None, "industry": "Shells", "fairValue": None, "priceToValue": None}]
    [group] = statistics_rows(rows, "industry", 0.90)
    assert (group["name"], group["filter"]) == ("Shells", None)


def narrow(rows: list[dict[str, Any]], found: dict[str, list[Any]]) -> list[dict[str, Any]]:
    """The rows the Screen leaves under ``found`` over the empty filters, as app.js's
    ``listedFilters`` and ``narrow`` match them: the chosen industries the chosen sectors' rows
    list, then each chosen group, the cap band lower-cased."""
    listed = {r["industry"] for r in rows if r["sector"] in found.get("sector", [])}
    industries = [name for name in found.get("industry", []) if name in listed]
    assert industries == found.get("industry", [])  # the link's industry stays chosen

    def within(chosen: list[Any], value: Any) -> bool:
        return not chosen or value in chosen

    return [
        r
        for r in rows
        if within(found.get("sector", []), r["sector"])
        and within(industries, r["industry"])
        and within(found.get("phase", []), r["phase"])
        and within(found.get("cap", []), (r["capBand"] or "").lower())
    ]


def test_a_group_s_count_is_the_rows_its_filter_leaves(client: TestClient) -> None:
    """Spec 4.5: a link's count is the Screen's. Every group with a filter counts the rows of
    ``GET /api/screen`` the filter leaves, matched as the Screen matches them, AAPL by its shown
    phase."""
    rows = client.get("/api/screen").json()["rows"]
    checked = 0
    for by in GROUP_BY:
        for group in read(client, "statistics", by):
            if group["filter"] is None:
                continue
            left = narrow(rows, group["filter"])
            assert len(left) == group["count"], (by, group["name"])
            checked += 1
    assert checked == 9


def test_an_unknown_grouping_is_400(client: TestClient) -> None:
    response = client.get("/api/statistics?by=country")
    assert (response.status_code, response.json()) == (
        400,
        {"detail": "by must be sector, industry, phase or cap, not country"},
    )
    response = client.get("/api/statistics")
    assert (response.status_code, response.json()) == (400, {"detail": "by: Field required"})


def test_the_statistics_view_reads_its_route_and_says_its_rule() -> None:
    """The view reads ``/api/statistics``; its failure sentence and the caption under its table
    name the view and the rule of spec 4.5: the value the Screen shows."""
    script = _static_file("controls.js")
    assert "P.getJson('/api/statistics?by=' + encodeURIComponent(state.by))" in script
    assert "'/api/groups" not in script
    assert "state.groupsError = 'The statistics did not load: ' + err.message +" in script
    assert "figure(row.shareBelowValue, F.formatPercent(row.shareBelowValue))" in script
    assert "'Below value'" in script
    assert (
        "'The median and the share read the value the Screen shows, the reviewed one where a ' +\n"
        "        'company has it, over the companies with a value; below value is a price in its ' +\n"
        "        'Below or Well below band.')"
    ) in script
    assert "the mechanical value, the engine" not in script
    assert "shareBelowBuy" not in script and "Below buy" not in script


def test_the_statistics_view_offers_the_industry() -> None:
    script = _static_file("controls.js")
    assert (
        "var BY = { sector: 'Sector', industry: 'Industry', phase: 'Phase', cap: 'Cap band' };"
        in script
    )
