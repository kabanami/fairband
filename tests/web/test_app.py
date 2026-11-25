"""The web app through its routes, on a temporary migrated database with three snapshots from the
engine's test companies: AAPL, valued on the Mature Growth route; AAL, a Young Growth company with
no mature peers, which the engine refuses for its target margin; and HGCO, the High Growth company,
valued on the revenue growth route. All three are listed in the universe of one finished full
refresh. The fixtures are in ``conftest.py``, the names they share in ``support.web``."""

import json
import re
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from typing import Any, get_args

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from support.engine_companies import (
    annual,
    decline_inputs,
    fiscal_years,
    fx_inputs,
    high_growth_inputs,
    in_sek,
    mature_growth_inputs,
    mature_stable_inputs,
    start_up_inputs,
    universe_deciles,
)
from support.web import (
    CALIBRATION,
    CREATED,
    FINISHED,
    HEADER,
    HOST,
    NOW,
    STARTED,
    TODAY,
    _company,
    _component_file,
    _settings,
    _static_file,
)

from fairband import __main__ as cli
from fairband.config import DEFAULT_PORT
from fairband.engine import METHOD_VERSION
from fairband.engine.review import Review
from fairband.engine.route import value_company
from fairband.engine.types import Designation, Flag, ValuationResult, result_to_json
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.reports.charts import (
    BAND_TITLE,
    GRID_TITLE,
    QUARTERS_TITLE,
    SERIES_TITLES,
    TITLES,
    row_name,
)
from fairband.reports.tables import financial_tables, quarters_table
from fairband.store.companies import insert_companies
from fairband.store.db import applied_versions, connect, migrate
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.refreshes import create_refresh, finish_refresh
from fairband.store.reviews import insert_review
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.web.app import create_app
from fairband.web.rows import COLUMNS, EXTRA_KEYS, ROW_KEYS

# The design system's ScreenRow keys.
DESIGN_ROW_KEYS = [
    "ticker",
    "name",
    "phase",
    "fairLow",
    "fairHigh",
    "fairValue",
    "buyLevel",
    "trimLevel",
    "price",
    "mechanical",
    "reviewed",
    "overrides",
    "enteredAt",
    "freshness",
]
DESIGN_COLUMNS = [
    "ticker",
    "name",
    "phase",
    "band",
    "fairValue",
    "buyLevel",
    "trimLevel",
    "mechanical",
    "reviewed",
    "price",
    "designation",
    "overrides",
    "entered",
]
EXTRA_COLUMNS = [
    "sector",
    "industry",
    "capBand",
    "marketCap",
    "moat",
    "impliedGrowth",
    "expectedReturn",
    "epv",
    "peReported",
    "peForward",
    "high52w",
    "low52w",
    "change1y",
    "change3y",
    "change5y",
    "drawdown",
    "flags",
    "flagCount",
    "watchlists",
    "refusal",
    "priceToValue",
    "designation",
    "agentStance",
    "priceDate",
    "dataDate",
    "validUntil",
    "route",
    "growthRouteValue",
    "targetMargin",
    "impliedMargin",
    "requiredRevenue",
    "burnCover",
    "rating",
    "distressProbability",
    "altmanZ",
    "piotroskiF",
    "impliedDeclineRate",
]
# The Start-up and Decline rows' figures, the last extra columns.
START_UP_KEYS = ("requiredRevenue", "burnCover")
DECLINE_KEYS = ("rating", "distressProbability", "altmanZ", "piotroskiF", "impliedDeclineRate")


def _screen(client: TestClient, query: str = "") -> dict[str, Any]:
    response = client.get(f"/api/screen{query}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _tickers(client: TestClient, query: str) -> list[str]:
    return [row["ticker"] for row in _screen(client, query)["rows"]]


def test_index_and_static_served(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    for path in (
        "/static/design-system/tokens/tokens.css",
        "/static/design-system/fonts/ibm-plex-mono-latin-400-normal.woff2",
        "/static/vendor/react.production.min.js",
        "/static/design-system/components/bundle.js",
    ):
        assert client.get(path).status_code == 200, path
    assert client.get("/static/no-such-file.js").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/static/app.js",
        "/static/settings.js",
        "/static/design-system/components/bundle.js",
        "/static/design-system/tokens/tokens.css",
        "/static/vendor/react.production.min.js",
    ],
)
def test_the_page_and_its_files_are_checked_again_at_each_load(
    client: TestClient, path: str
) -> None:
    """No-cache: the browser keeps its copy and asks at each load whether the file changed, so a
    page file of an older build is not used after the server changed (the founder, 2026-11-16:
    the Agents section was missing behind an old settings.js)."""
    assert client.get(path).headers["cache-control"] == "no-cache", path


def test_a_static_file_that_did_not_change_is_a_304_that_says_no_cache_too(
    client: TestClient,
) -> None:
    first = client.get("/static/app.js")
    again = client.get("/static/app.js", headers={"If-None-Match": first.headers["etag"]})
    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["cache-control"] == "no-cache"


def test_screen_rows_and_default_sort(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    rows = _screen(client)["rows"]
    assert [row["ticker"] for row in rows] == ["AAL", "AAPL", "HGCO"]
    aal, aapl, _ = rows

    valued = results["AAPL"]
    assert valued.value is not None and valued.levels is not None
    im = valued.intermediates
    facts = im["price_facts"]
    assert aapl == {
        "ticker": "AAPL",
        "name": "Mature Growth Co",
        "phase": 4,
        "fairLow": valued.levels.fair_low,
        "fairHigh": valued.levels.fair_high,
        "fairValue": valued.value,
        "buyLevel": valued.levels.buy,
        "trimLevel": valued.levels.trim,
        "price": 150.0,
        "mechanical": valued.value,
        "reviewed": None,
        "overrides": 0,
        "enteredAt": "2026-10-31T22:15:00+00:00",
        "freshness": "current",
        "sector": "Technology",
        "industry": "Software - Application",
        "capBand": "mega",
        "marketCap": 150_000_000_000.0,
        "moat": "Wide",
        "impliedGrowth": im["implied_growth"],
        "expectedReturn": im["expected_return"]["total"],
        "epv": im["epv"],
        "peReported": im["multiples"]["pe_reported"],
        "peForward": im["multiples"]["pe_forward"],
        "high52w": facts["high_52w"],
        "low52w": facts["low_52w"],
        "change1y": facts["change_1y"],
        "change3y": None,
        "change5y": None,
        "drawdown": facts["drawdown_from_peak"],
        "flags": [f.word for f in valued.flags],
        "refusal": None,
        "priceToValue": 150.0 / valued.value,  # $150 on the value $127.68: 1.175
        "designation": "above",  # above 1.15 × the value, below 1.50
        "agentStance": None,
        "priceDate": "2026-10-30",
        "dataDate": "2026-10-30",
        "validUntil": "2027-01-28",
        "route": "mature-growth",
        "growthRouteValue": valued.value,
        "targetMargin": None,
        "impliedMargin": None,
        "requiredRevenue": None,
        "burnCover": None,
        "rating": None,
        "distressProbability": None,
        "altmanZ": None,
        "piotroskiF": None,
        "impliedDeclineRate": None,
        "watchlists": [],
        "flagCount": 1,  # value-spread; its other flags are notes
        "covered": None,
        "warnings": ["value sensitive to its inputs"],
        "marked": False,  # one warning, under three
        "expiredEarly": False,  # no review fills the row (spec 2026-11-23 held reviewed value)
        # the classifier's phase, which ``phase`` shows where no review fills the row (spec
        # 2026-11-23 refresh experience, 4.4): tests/web/test_rows.py
        "mechanicalPhase": 4,
    }

    refused = results["AAL"]
    assert set(aal) == set(aapl)
    assert aal["phase"] == 2 and aal["name"] == "Young Growth Co"
    assert aal["refusal"] == refused.refusal == "no target margin: 0 mature peers"
    for key in ("fairLow", "fairHigh", "fairValue", "buyLevel", "trimLevel", "mechanical"):
        assert aal[key] is None, key
    for key in ("impliedGrowth", "expectedReturn", "epv", "route"):
        assert aal[key] is None, key
    assert (aal["priceToValue"], aal["designation"]) == (None, None)
    # refused for its target margin, it keeps the moat class the margin the price needs reads,
    # which the column shows only on a row with a value, as on the mature routes' refusals
    assert refused.intermediates["moat"] == "None" and aal["moat"] is None
    assert aal["reviewed"] is None and aal["overrides"] == 0
    assert aal["price"] == 150.0
    assert aal["high52w"] == refused.intermediates["price_facts"]["high_52w"]
    assert aal["flags"] == [f.word for f in refused.flags]


def test_screen_sort_nulls_last(client: TestClient) -> None:
    assert _tickers(client, "?sort=fairValue&dir=desc") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=fairValue&dir=asc") == ["AAPL", "HGCO", "AAL"]
    assert _tickers(client, "?sort=phase&dir=asc") == ["AAL", "HGCO", "AAPL"]
    assert _tickers(client, "?sort=phase&dir=desc") == ["AAPL", "HGCO", "AAL"]
    assert _tickers(client, "?sort=marketCap&dir=desc") == ["AAPL", "HGCO", "AAL"]
    assert _tickers(client, "?sort=ticker&dir=desc") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=marketCap") == ["AAL", "HGCO", "AAPL"]  # ascending by default
    # every row key sorts but the coverage mark's record, the warning mark's two fields, the
    # held review's early expiry and the classifier's phase, which no column draws
    fields = {"covered", "warnings", "marked", "expiredEarly", "mechanicalPhase"}
    assert set(_screen(client)["rows"][0]) == {*ROW_KEYS, *fields}
    for key in ROW_KEYS:
        for direction in ("asc", "desc"):
            assert len(_tickers(client, f"?sort={key}&dir={direction}")) == 3, key


def test_screen_sorts_by_flag_count(client: TestClient) -> None:
    """AAL has no quality warning, AAPL one and HGCO three; the notes do not count."""
    assert [r["flagCount"] for r in _screen(client, "?sort=flagCount")["rows"]] == [0, 1, 3]
    assert _tickers(client, "?sort=flagCount&dir=asc") == ["AAL", "AAPL", "HGCO"]
    assert _tickers(client, "?sort=flagCount&dir=desc") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=watchlists") == ["AAL", "AAPL", "HGCO"]  # a row key too


def test_screen_sorts_by_price_to_value(client: TestClient) -> None:
    """HGCO at 0.63 × its value, AAPL at 1.175, AAL refused with none: last either way."""
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}
    assert rows["HGCO"]["priceToValue"] == pytest.approx(0.632, abs=5e-4)
    assert rows["HGCO"]["designation"] == "below"  # over its None class's buy level, 0.60 ×
    assert _tickers(client, "?sort=priceToValue&dir=asc") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=priceToValue&dir=desc") == ["AAPL", "HGCO", "AAL"]


def test_sort_unknown_key_400(client: TestClient) -> None:
    response = client.get("/api/screen?sort=fair_value")
    assert response.status_code == 400
    assert response.json() == {"detail": "unknown sort column: fair_value"}
    assert client.get("/api/screen?sort=band").status_code == 400  # a column, not a row key
    for gone in ("stance", "stance3", "stance5", "peClean"):
        assert client.get(f"/api/screen?sort={gone}").status_code == 400, gone
    assert client.get("/api/screen?sort=covered").status_code == 400  # the mark's, not a column
    response = client.get("/api/screen?sort=ticker&dir=down")
    assert response.status_code == 400
    assert response.json() == {"detail": "dir must be asc or desc, not down"}


def test_screen_envelope_columns_and_today(client: TestClient) -> None:
    body = _screen(client)
    assert set(body) == {"rows", "columns", "today", "refresh"}
    # the designation is a design column and a row key: listed once, in its design place
    extra = [key for key in EXTRA_COLUMNS if key not in DESIGN_COLUMNS]
    assert extra == [key for key in EXTRA_COLUMNS if key != "designation"]
    assert body["columns"] == DESIGN_COLUMNS + extra
    assert body["today"] == "2026-11-01"
    assert body["refresh"] == {
        "id": 1,
        "kind": "full",
        "symbols": None,
        "status": "done",
        "stage": "done",
        "startedAt": "2026-10-31T22:00:00+00:00",
        "finishedAt": "2026-10-31T22:20:00+00:00",
        "message": "3 valued or refused",
        "calibration": CALIBRATION,
    }


def test_screen_envelope_has_today(client: TestClient) -> None:
    """The screen names the engine's day, on which a validity window is judged, never the
    browser's."""
    assert _screen(client)["today"] == NOW.date().isoformat() == "2026-11-01"


@pytest.mark.parametrize(
    ("now", "state"),
    [
        # The window runs 2026-10-30 to 2027-01-28, 90 days; aging from 0.6667 of it, day 61.
        (datetime(2026, 12, 29, 23, 59, tzinfo=UTC), "current"),
        (datetime(2026, 12, 30, 0, 0, tzinfo=UTC), "aging"),
        (datetime(2027, 1, 28, 23, 59, tzinfo=UTC), "aging"),
        (datetime(2027, 1, 29, 0, 0, tzinfo=UTC), "expired"),
    ],
)
def test_freshness_states(
    client_with_clock: Callable[[datetime], TestClient], now: datetime, state: str
) -> None:
    body = _screen(client_with_clock(now))
    assert body["today"] == now.date().isoformat()
    assert [row["freshness"] for row in body["rows"]] == [state, state, state]


def test_aging_fraction_from_the_overlay_changes_freshness(
    client_with_clock: Callable[[datetime], TestClient],
) -> None:
    """The setting is read at once, at the next request: on day 21 of the 90-day window a row is
    current at the default 2/3 and aging from 10%."""
    client = client_with_clock(datetime(2026, 11, 20, 12, 0, tzinfo=UTC))
    assert [row["freshness"] for row in _screen(client)["rows"]] == ["current"] * 3
    r = client.put("/api/settings", json={"changes": {"aging_fraction": 0.1}}, headers=HEADER)
    assert r.status_code == 200, r.text
    assert [row["freshness"] for row in _screen(client)["rows"]] == ["aging"] * 3


def test_groups_and_the_drawer_read_the_edges_of_the_settings(client: TestClient) -> None:
    """HGCO sits at 0.63 × its value and AAPL at 1.175. Under a fair band from 0.6, with every
    margin of safety at 45% so each class's edges still ascend, HGCO is no longer below the band,
    in the groups the Methodology page reads and in the Statistics view's, which the page now
    shows (spec 2026-11-23 refresh experience, 4.5)."""
    for route in ("/api/groups?by=sector", "/api/statistics?by=sector"):
        [before] = client.get(route).json()["groups"]
        assert before["shareBelowValue"] == 0.5, route  # HGCO below 0.90, AAPL not
    safety = {"None": 0.45, "Narrow": 0.45, "Wide": 0.45}
    changes = {"fair_band": [0.6, 1.15], "margin_of_safety": safety}
    assert client.put("/api/settings", json={"changes": changes}, headers=HEADER).status_code == 200
    edges = client.get("/api/companies/AAPL").json()["designationEdges"]
    assert edges == [1 - 0.45, 0.6, 1.15, 1.35]
    for route in ("/api/groups?by=sector", "/api/statistics?by=sector"):
        [after] = client.get(route).json()["groups"]
        assert after["shareBelowValue"] == 0.0, route


def test_a_changed_threshold_shows_on_the_screen_and_in_the_detail_with_no_revalue(
    client: TestClient,
) -> None:
    """Spec 2026-11-23 thresholds, 5.3 and 7: a saved trim multiple of 1.2 is on the screen's row
    and in the company detail's result, which the drawer's meter and the agents' ``company`` tool
    read, at the next read, with no refresh run; the value does not move. AAPL at 1.175 × its
    value read above under the default trim multiple; the detail's word follows the row's."""
    before = {row["ticker"]: row for row in _screen(client)["rows"]}["AAPL"]
    value = before["mechanical"]
    assert before["trimLevel"] == pytest.approx(value * 1.35) and before["designation"] == "above"
    saved = client.put("/api/settings", json={"changes": {"trim_multiple": 1.16}}, headers=HEADER)
    assert saved.status_code == 200
    after = {row["ticker"]: row for row in _screen(client)["rows"]}["AAPL"]
    assert (after["mechanical"], after["fairValue"]) == (value, value)
    assert after["trimLevel"] == pytest.approx(value * 1.16)
    assert after["designation"] == "well-above"  # 1.175 is at or above the new 1.16
    result = client.get("/api/companies/AAPL").json()["result"]
    assert result["value"] == value and result["levels"]["trim"] == after["trimLevel"]
    assert (result["designation"], result["price_to_value"]) == (
        after["designation"],
        after["priceToValue"],
    )


def test_the_detail_reads_the_aging_fraction_of_the_settings(client: TestClient) -> None:
    """The company detail serves the effective ``aging_fraction``, from which a validity window
    turns aging where the screen's Freshness column does, a setting that takes effect at once
    (spec 2026-11-04 8.2)."""
    assert client.get("/api/companies/AAPL").json()["agingFraction"] == 0.6667
    r = client.put("/api/settings", json={"changes": {"aging_fraction": 0.1}}, headers=HEADER)
    assert r.status_code == 200, r.text
    assert client.get("/api/companies/AAPL").json()["agingFraction"] == 0.1


def _universe(db_path: Path, policy: Policy, *companies: tuple[str, str, int, bool]) -> None:
    """A later full refresh whose universe lists ``companies``: symbol, name, market cap and
    whether it is admitted."""
    with closing(connect(db_path)) as conn:
        refresh_id = create_refresh(
            conn, "full", None, policy.version, METHOD_VERSION, NOW, EMPTY_SETTINGS_HASH
        )
        rows = [
            _company(symbol, refresh_id, name, Decimal(cap))
            if admitted
            else replace(
                _company(symbol, refresh_id, name, Decimal(cap)),
                cap_band=None,
                eligible=False,
                exclusion_reason="manual exclusion",
            )
            for symbol, name, cap, admitted in companies
        ]
        insert_companies(conn, rows)
        finish_refresh(conn, refresh_id, "done", NOW)


def test_screen_rows_follow_the_universe(db_path: Path, policy: Policy, client: TestClient) -> None:
    """The rows are the latest universe's admitted companies, each with its latest snapshot: AAL,
    no longer admitted, drops off, and NEWC, not valued yet, shows."""
    _universe(
        db_path,
        policy,
        ("AAPL", "Mature Growth Co", 150_000_000_000, True),
        ("AAL", "Young Growth Co", 4_000_000_000, False),
        ("NEWC", "New Co", 3_000_000_000, True),
    )
    rows = _screen(client)["rows"]
    assert [(row["ticker"], row["refusal"]) for row in rows] == [
        ("AAPL", None),
        ("NEWC", "not yet valued"),
    ]
    assert rows[0]["fairValue"] is not None
    assert rows[0]["enteredAt"] == "2026-10-31T22:15:00+00:00"  # the snapshot of the first refresh
    assert _tickers(client, "?sort=fairValue&dir=desc") == ["AAPL", "NEWC"]
    assert client.get("/api/companies/NEWC").status_code == 404  # no snapshot to show yet


def test_screen_placeholder_row_not_yet_valued(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    _universe(db_path, policy, ("NEWC", "New Co", 3_000_000_000, True))
    [row] = _screen(client)["rows"]
    fields = {"covered", "warnings", "marked", "expiredEarly", "mechanicalPhase"}
    assert set(row) == {*DESIGN_ROW_KEYS, *EXTRA_COLUMNS, *fields}
    assert {key: value for key, value in row.items() if value is not None} == {
        "ticker": "NEWC",
        "name": "New Co",
        "overrides": 0,
        "freshness": "current",
        "sector": "Technology",
        "industry": "Software - Application",
        "capBand": "mid",
        "marketCap": 3_000_000_000.0,
        "refusal": "not yet valued",
        "watchlists": [],
        "flagCount": 0,
        "warnings": [],
        "marked": False,
        "expiredEarly": False,
    }


def test_growth_route_value_column(client: TestClient) -> None:
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}
    assert rows["AAPL"]["growthRouteValue"] == rows["AAPL"]["mechanical"]
    assert rows["AAL"]["growthRouteValue"] is None


def test_growth_route_value_on_mature_stable_rows(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    """A Mature Stable row shows its growth-route cross-check in the column, while its value
    stays the stable-growth value; one whose cross-check refused shows nothing."""
    growth = mature_growth_inputs()
    with_path = replace(
        mature_stable_inputs(),
        quarter_estimates=growth.quarter_estimates,
        annual_estimates=growth.annual_estimates,
    )
    stable = {
        "MSCO": value_company(with_path, universe_deciles(), policy, TODAY),
        "MSNC": value_company(
            replace(mature_stable_inputs(), symbol="MSNC"), universe_deciles(), policy, TODAY
        ),
    }
    with closing(connect(db_path)) as conn:
        companies = [_company(s, 1, "Mature Stable Co", Decimal(40_000_000_000)) for s in stable]
        insert_companies(conn, companies)
        for result in stable.values():
            insert_snapshot(conn, result, 1, clock=lambda: CREATED)
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}
    msco, msnc = rows["MSCO"], rows["MSNC"]
    cross_check = stable["MSCO"].intermediates["growth_route"]["value_per_share"]
    assert msco["growthRouteValue"] == cross_check != msco["mechanical"]
    assert msco["mechanical"] == stable["MSCO"].intermediates["stable_growth"]
    assert msnc["growthRouteValue"] is None and msnc["mechanical"] is not None


def test_growth_route_columns(client: TestClient, results: dict[str, ValuationResult]) -> None:
    """A row valued on the revenue growth route shows the peers' target margin and the margin the
    price needs; a row refused for its target margin shows the margin the price needs alone, its
    one figure; a mature row shows neither."""
    body = _screen(client)
    assert "targetMargin" in body["columns"] and "impliedMargin" in body["columns"]
    rows = {row["ticker"]: row for row in body["rows"]}
    row = rows["HGCO"]
    im = results["HGCO"].intermediates
    assert row["route"] == "revenue-growth"
    assert row["targetMargin"] == pytest.approx(0.20) == im["target_margin"]["value"]
    assert row["impliedMargin"] == im["implied_margin"] is not None
    # no positive forward anchor, so no cross-check value
    assert row["growthRouteValue"] == im["growth_route"].get("value_per_share") is None
    assert row["moat"] == "None"  # a valued row shows its moat class

    refused = rows["AAL"]
    assert refused["targetMargin"] is None
    assert refused["impliedMargin"] == results["AAL"].intermediates["implied_margin"] is not None
    assert rows["AAPL"]["targetMargin"] is None and rows["AAPL"]["impliedMargin"] is None


def test_growth_route_value_on_revenue_growth_rows(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    """A growth row whose forward EPS anchor is positive shows the growth route's cross-check in
    the column, while its value stays the revenue route's."""
    hg = high_growth_inputs()
    positive = replace(
        hg,
        symbol="HGPA",
        quarter_estimates=tuple(replace(q, eps=0.60) for q in hg.quarter_estimates),
        annual_estimates=(
            annual(2027, 250e6, 2.50, 3, 13_000e6, 20),
            annual(2028, 320e6, 3.20, 3, 16_000e6, 15),
            annual(2029, 400e6, 4.00, 3, 19_200e6, 12),
        ),
    )
    result = value_company(positive, universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        insert_companies(conn, [_company("HGPA", 1, "High Growth Co", Decimal(15_000_000_000))])
        insert_snapshot(conn, result, 1, clock=lambda: CREATED)
    row = {row["ticker"]: row for row in _screen(client)["rows"]}["HGPA"]
    cross_check = result.intermediates["growth_route"]["value_per_share"]
    assert row["route"] == "revenue-growth" and cross_check is not None
    assert row["growthRouteValue"] == cross_check != row["mechanical"]
    assert row["mechanical"] == result.intermediates["value_per_share"]


def _add_snapshots(db_path: Path, *found: ValuationResult) -> None:
    """Each result's company admitted in the first refresh's universe, with its snapshot."""
    with closing(connect(db_path)) as conn:
        companies = [_company(r.symbol, 1, f"{r.symbol} Co", Decimal(3_000_000_000)) for r in found]
        insert_companies(conn, companies)
        for result in found:
            insert_snapshot(conn, result, 1, clock=lambda: CREATED)


def test_screen_row_carries_the_decline_figures(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    """Spec 13.1's Decline row: the rating, its ten-year π, Altman Z″ (3.07) and Piotroski F, and
    the decline rate a price of $4.00 implies (−21.8%). A row refused for a value at or below
    zero keeps them, though it has no route: a chronic loss-maker with net debt rated D, π 100%.
    With net cash there is no rating ("—") and π is 0. No other row carries them, nor a Decline row
    the Start-up figures."""
    deciles = universe_deciles()
    valued = value_company(replace(decline_inputs(), price=4.0), deciles, policy, TODAY)
    margins = [-0.02, -0.03, -0.03, -0.03, -0.03]
    revenue = [fy.revenue for fy in decline_inputs().series if fy.revenue is not None]
    chronic = replace(decline_inputs(), symbol="DCLM", series=fiscal_years(revenue, margins))
    refused = value_company(chronic, deciles, policy, TODAY)
    net_cash = value_company(
        replace(decline_inputs(), symbol="DCNC", cash=250e6), deciles, policy, TODAY
    )
    assert (valued.route, refused.route, refused.refusal) == (
        "decline",
        None,
        "value not positive in the run-off",
    )
    _add_snapshots(db_path, valued, refused, net_cash)
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}

    row, im = rows["DCCO"], valued.intermediates
    assert row["rating"] == "A-"
    assert row["distressProbability"] == 0.05
    assert row["altmanZ"] == pytest.approx(3.07, abs=5e-3) == im["altman_z"]["score"]
    assert row["piotroskiF"] == "6 of 9"
    assert row["impliedDeclineRate"] == pytest.approx(-0.218, abs=5e-4)
    assert row["impliedDeclineRate"] == im["implied_decline_rate"]
    assert all(row[key] is None for key in START_UP_KEYS)

    row = rows["DCLM"]
    assert (row["refusal"], row["rating"], row["distressProbability"]) == (
        "value not positive in the run-off",
        "D",
        1.0,
    )
    assert row["altmanZ"] is not None and row["piotroskiF"] is not None
    assert row["impliedDeclineRate"] is None  # a refusal has nothing at the price
    assert (rows["DCNC"]["rating"], rows["DCNC"]["distressProbability"]) == ("—", 0.0)
    for ticker in ("AAPL", "AAL", "HGCO"):
        assert all(rows[ticker][key] is None for key in START_UP_KEYS + DECLINE_KEYS), ticker


def test_screen_row_carries_the_start_up_requirement(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    """Spec 13.2's Start-up row, a refusal with its figures: the year-10 revenue its price needs
    (1,725.73) and the years its cash covers the burn (4.0). A row not burning has no cover, and
    a row whose requirement has a reason no revenue; neither carries the Decline figures."""
    deciles, inputs = universe_deciles(), start_up_inputs()
    t = inputs.trailing
    assert t is not None
    found = value_company(inputs, deciles, policy, TODAY)
    not_burning = replace(inputs, symbol="SUNB", trailing=replace(t, cfo=15.0))
    no_peers = replace(inputs, symbol="SUNP", peers=())
    others = [value_company(i, deciles, policy, TODAY) for i in (not_burning, no_peers)]
    _add_snapshots(db_path, found, *others)
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}

    row, req = rows["SUCO"], found.intermediates["requirement"]
    assert (row["route"], row["refusal"]) == ("start-up", "Start-up: no value by design")
    assert row["requiredRevenue"] == pytest.approx(1_725.73, abs=5e-3) == req["revenue_y10"]
    assert row["burnCover"] == 4.0
    assert all(row[key] is None for key in DECLINE_KEYS)
    assert others[0].intermediates["burn_cover_years"] == "not burning"
    assert rows["SUNB"]["burnCover"] is None and rows["SUNB"]["requiredRevenue"] is not None
    assert others[1].intermediates["requirement"]["reason"] == "no target margin: 0 mature peers"
    assert rows["SUNP"]["requiredRevenue"] is None and rows["SUNP"]["burnCover"] == 4.0


def test_a_row_in_another_currency_shows_its_money_columns_in_us_dollars(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    """Spec 2026-11-10 7.4 (spec 2: the screen compares like with like): every money column is in
    US dollars, as the value and the price are. FXCO, in SEK at 8.0 a dollar, shows its EPV as
    the route's ÷ 8.0. A Mature Stable company with a cross-check and the Start-up company, each
    in SEK at 8.0 with no inflation differential, show their USD twins' EPV, cross-check value and
    year-10 revenue: the route's figures in SEK ÷ 8.0. The USD twins show the route's figures as
    they are."""
    growth = mature_growth_inputs()
    stable = replace(
        mature_stable_inputs(),
        quarter_estimates=growth.quarter_estimates,
        annual_estimates=growth.annual_estimates,
    )
    inputs = {
        "FXCO": fx_inputs(),
        "MSCO": stable,
        "MSEK": in_sek(stable, differential=0.0),
        "SUCO": start_up_inputs(),
        "SUEK": in_sek(start_up_inputs(), differential=0.0),
    }
    found = {
        symbol: value_company(replace(i, symbol=symbol), universe_deciles(), policy, TODAY)
        for symbol, i in inputs.items()
    }
    _add_snapshots(db_path, *found.values())
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}

    def im(symbol: str) -> dict[str, Any]:
        return found[symbol].intermediates

    assert rows["FXCO"]["epv"] == im("FXCO")["epv"] / 8.0
    assert rows["FXCO"]["growthRouteValue"] == rows["FXCO"]["mechanical"]  # its own, in USD
    cross_check = im("MSEK")["growth_route"]["value_per_share"]
    assert (rows["MSEK"]["epv"], rows["MSEK"]["growthRouteValue"]) == (
        im("MSEK")["epv"] / 8.0,
        cross_check / 8.0,
    )
    assert rows["SUEK"]["requiredRevenue"] == im("SUEK")["requirement"]["revenue_y10"] / 8.0
    for key in ("epv", "growthRouteValue", "mechanical"):
        assert rows["MSEK"][key] == pytest.approx(rows["MSCO"][key]), key
    assert rows["SUEK"]["requiredRevenue"] == pytest.approx(rows["SUCO"]["requiredRevenue"])
    # a USD row's figures are the route's, unchanged
    assert (rows["MSCO"]["epv"], rows["MSCO"]["growthRouteValue"]) == (
        im("MSCO")["epv"],
        im("MSCO")["growth_route"]["value_per_share"],
    )
    assert rows["SUCO"]["requiredRevenue"] == im("SUCO")["requirement"]["revenue_y10"]


def test_screen_keeps_the_universe_when_a_refresh_admits_none(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    """A later full refresh whose screener admitted nobody recorded only an excluded listing: the
    screen keeps the last universe that admitted companies."""
    _universe(db_path, policy, ("FIRB", "First Bank", 4_000_000_000, False))
    assert _tickers(client, "") == ["AAL", "AAPL", "HGCO"]


def test_screen_without_a_universe_shows_every_snapshot(
    tmp_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Before any full refresh, the companies a scoped refresh valued are the rows."""
    path = tmp_path / "bare.db"
    with closing(connect(path)) as conn:
        migrate(conn)
        symbols = list(results)
        refresh_id = create_refresh(
            conn, "scoped", symbols, policy.version, METHOD_VERSION, STARTED, EMPTY_SETTINGS_HASH
        )
        for result in results.values():
            insert_snapshot(conn, result, refresh_id, clock=lambda: CREATED)
        finish_refresh(conn, refresh_id, "done", FINISHED)
    app = create_app(_settings(tmp_path, path), policy, lambda: connect(path), clock=lambda: NOW)
    with TestClient(app, base_url=HOST) as c:
        rows = _screen(c)["rows"]
    assert [(row["ticker"], row["name"], row["refusal"]) for row in rows] == [
        ("AAL", None, "no target margin: 0 mature peers"),
        ("AAPL", None, None),
        ("HGCO", None, None),
    ]


def test_company_detail(client: TestClient, results: dict[str, ValuationResult]) -> None:
    response = client.get("/api/companies/AAPL")
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "company",
        "snapshot",
        "result",
        "today",
        "designationEdges",
        "agingFraction",
        "review",
        "secondary",
        "report",
        "item",
        "brief",
        "logo",
        # what the price needs when it is well above the value (method 4.11): none here, the
        # price being above the value only; tests/web/test_price_needs_api.py
        "priceNeeds",
        # what the figures are in (spec 2026-11-10 7.4): tests/web/test_company_reads.py
        "currency",
        "isAdr",
        "adrRatio",
        "fxRate",
        "fxDate",
        # whether launching is set up (spec 2026-11-16 agent launch, 9): no launch file here;
        # tests/web/test_launch_settings_api.py
        "launchReady",
        # the moat class in force and the count of the company's notes (the company page's
        # design, 7.2 and 11.1): tests/web/test_company_page_api.py
        "moat",
        "noteCount",
        # the company's row of the moat table (spec 2026-11-19 8.6): tests/web/test_moat_api.py
        "moatClass",
        # the plain words of the snapshot's quality warnings and the mark (spec 2026-11-19 7.5):
        # test_the_detail_carries_warnings_and_marked
        "warnings",
        "marked",
        # the phase the screen's row shows (spec 2026-11-23 refresh experience, 4.4), the
        # snapshot's here: tests/web/test_research_api.py
        "phase",
    }
    assert body["phase"] == "Mature Growth"
    assert (body["warnings"], body["marked"]) == (["value sensitive to its inputs"], False)
    assert body["launchReady"] is False
    # The company brief (B-149) is the stored profile's description; none is stored here.
    assert body["brief"] is None
    # The logo's address (B-203) is the stored profile's too: tests/web/test_logo_api.py.
    assert body["logo"] is None
    # The agents' records (spec 2026-11-06 Tier 2, 18.2): none here;
    # tests/web/test_research_api.py writes each and reads its shape.
    assert (body["review"], body["secondary"], body["report"], body["item"]) == (None,) * 4
    assert body["priceNeeds"] is None and body["result"]["designation"] == "above"
    # The policy's edges, by which the drawer keeps its price ÷ value figure inside the band.
    # AAPL's own edges, a Wide row's: the first is its buy level over its value
    assert body["result"]["intermediates"]["moat"] == "Wide"
    assert body["designationEdges"] == pytest.approx([0.80, 0.90, 1.10, 1.35])
    # The fraction of the window from which a validity window reads aging, as the Freshness
    # column does.
    assert body["agingFraction"] == 0.6667
    result = body["result"]
    assert result == json.loads(result_to_json(results["AAPL"]))
    assert result["route"] == "mature-growth"
    assert isinstance(result["inputs"], list) and result["inputs"]
    assert {"price", "statements", "shares_diluted"} <= {i["name"] for i in result["inputs"]}
    assert {"moat", "implied_growth", "expected_return", "epv", "multiples", "price_facts"} <= set(
        result["intermediates"]
    )
    assert body["company"] == {
        "symbol": "AAPL",
        "refreshId": 1,
        "name": "Mature Growth Co",
        "exchange": "NASDAQ",
        "sector": "Technology",
        "industry": "Software - Application",
        "country": "US",
        "currency": "USD",
        "isAdr": False,
        "capBand": "mega",
        "marketCap": 150_000_000_000.0,
        "eligible": True,
        "exclusionReason": None,
        "observedAt": "2026-10-31T22:00:00+00:00",
    }
    assert body["snapshot"] == {
        "id": 1,
        "refreshId": 1,
        "decilesRefreshId": 1,
        "createdAt": "2026-10-31T22:15:00+00:00",
    }
    assert body["today"] == "2026-11-01"


def test_unknown_company_404(client: TestClient) -> None:
    response = client.get("/api/companies/NOPE")
    assert response.status_code == 404
    assert response.json() == {"detail": "no snapshot for NOPE"}


# HGCO's three quality warnings in the order of its flags, in their plain words.
HGCO_WARNINGS = ["new shares issued", "negative free cash flow", "value sensitive to its inputs"]


def _valued_before_1_7(result: ValuationResult) -> ValuationResult:
    """OLDC: AAPL's Mature Growth result as a snapshot valued before method 1.7 holds it, with a
    found non-recurring gap and the two codes 1.7 removed among its flags, beside two warnings:
    its own ``value-spread`` and an ``equity-raise``."""
    old = (
        Flag("large-nri", "Large non-recurring item", "The non-recurring gap is large."),
        Flag("consensus-basis-unknown", "Consensus basis unknown", "The basis is unknown."),
        Flag("equity-raise", "Equity raise", "The share count rose."),
    )
    return replace(
        result,
        symbol="OLDC",
        flags=(*old, *result.flags),
        intermediates=result.intermediates | {"nri_gap": 0.10},
    )


def _review_hgco(db_path: Path, result: ValuationResult, mechanical: float | None) -> None:
    """HGCO's newest review on its latest snapshot, with ``result`` over the ``mechanical`` value,
    and an applied override inside it, which keeps the review current."""
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "HGCO")
        assert snapshot is not None
        override_id = insert_override(
            conn,
            "HGCO",
            "growth.belief",
            None,
            0.08,
            "ratio",
            "guidance raised",
            [{"kind": "transcript", "ref": "Q3 call", "note": ""}],
            "lasting",
            None,
            None,
            snapshot.id,
            Writer("agent", "claude-opus-5-5", "claude-code/2.1"),
            NOW,
            "applied",
            "",
        )
        review = Review(result, mechanical, (), (override_id,))
        insert_review(conn, review, "HGCO", snapshot.id, None, clock=lambda: NOW)


def test_the_screen_rows_carry_warnings_and_marked(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    client: TestClient,
) -> None:
    """Spec 2026-11-19 7.5: a row's ``warnings`` are the plain words of its snapshot's quality
    warnings in the order of its flags, and ``marked`` holds on a mechanical value with the
    effective policy's ``warning_mark_min`` (3) of them or more and no reviewed value: HGCO's
    three mark it, AAPL's one does not, AAL's refusal has none; at a cut-off of one AAPL's is
    marked too. Neither field is a row key, so neither sorts. A snapshot valued before method 1.7
    counts neither code it removed, and nothing raises: OLDC's two warnings leave it unmarked. A
    placeholder has no warning and no mark."""
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}
    assert {t: (r["warnings"], r["marked"]) for t, r in rows.items()} == {
        "AAL": ([], False),
        "AAPL": (["value sensitive to its inputs"], False),
        "HGCO": (HGCO_WARNINGS, True),
    }
    for key in ("warnings", "marked"):
        response = client.get(f"/api/screen?sort={key}")
        assert (response.status_code, response.json()) == (
            400,
            {"detail": f"unknown sort column: {key}"},
        )

    under_one = replace(policy, warning_mark_min=1)
    app = create_app(
        _settings(tmp_path, db_path), under_one, lambda: connect(db_path), clock=lambda: NOW
    )
    with TestClient(app, base_url=HOST) as c:
        marked = {row["ticker"]: row["marked"] for row in _screen(c)["rows"]}
    assert marked == {"AAL": False, "AAPL": True, "HGCO": True}

    _add_snapshots(db_path, _valued_before_1_7(results["AAPL"]))
    oldc = {row["ticker"]: row for row in _screen(client)["rows"]}["OLDC"]
    assert (oldc["warnings"], oldc["marked"], oldc["flagCount"]) == (
        ["new shares issued", "value sensitive to its inputs"],
        False,
        2,
    )

    _universe(db_path, policy, ("NEWC", "New Co", 3_000_000_000, True))
    [placeholder] = _screen(client)["rows"]
    assert (placeholder["warnings"], placeholder["marked"]) == ([], False)


def test_the_detail_carries_warnings_and_marked(
    tmp_path: Path,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    client: TestClient,
) -> None:
    """Spec 2026-11-19 7.5: the detail's ``warnings`` are the plain words of the snapshot's
    quality warnings, never a review's, and ``marked`` reads them against the counting review, as
    the screen's row does: HGCO's three mark its mechanical value until a review values it,
    whatever flags the review holds, and a newer review that refused leaves the mark; AAPL's one
    warning and AAL's refusal have none, and at a cut-off of one AAPL's is marked. A snapshot
    valued before method 1.7 counts neither code it removed."""

    def detail(symbol: str, read: TestClient = client) -> tuple[list[str], bool]:
        body = read.get(f"/api/companies/{symbol}").json()
        return body["warnings"], body["marked"]

    def row(symbol: str) -> tuple[list[str], bool]:
        found = {r["ticker"]: r for r in _screen(client)["rows"]}[symbol]
        return found["warnings"], found["marked"]

    assert detail("HGCO") == (HGCO_WARNINGS, True)
    assert detail("AAPL") == (["value sensitive to its inputs"], False)
    assert detail("AAL") == ([], False)
    app = create_app(
        _settings(tmp_path, db_path),
        replace(policy, warning_mark_min=1),
        lambda: connect(db_path),
        clock=lambda: NOW,
    )
    with TestClient(app, base_url=HOST) as c:
        assert detail("AAPL", c) == (["value sensitive to its inputs"], True)

    mechanical = results["HGCO"]
    _review_hgco(db_path, replace(mechanical, flags=()), mechanical.value)
    reviewed = client.get("/api/companies/HGCO").json()["review"]
    assert (reviewed["value"], reviewed["flags"]) == (mechanical.value, [])
    assert detail("HGCO") == row("HGCO") == (HGCO_WARNINGS, False)
    refused = replace(
        mechanical,
        value=None,
        levels=None,
        price_to_value=None,
        designation=None,
        refusal="the reviewed belief is refused",
    )
    _review_hgco(db_path, refused, mechanical.value)
    assert client.get("/api/companies/HGCO").json()["review"]["value"] is None
    assert detail("HGCO") == row("HGCO") == (HGCO_WARNINGS, True)

    _add_snapshots(db_path, _valued_before_1_7(results["AAPL"]))
    assert detail("OLDC") == (["new shares issued", "value sensitive to its inputs"], False)


class _References(HTMLParser):
    """The ``href`` and ``src`` attribute values of a page, in document order."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.urls += [value for name, value in attrs if name in ("href", "src") and value]


def test_static_design_system_served_offline(client: TestClient) -> None:
    page = client.get("/").text
    assert "https://" not in page and "http://" not in page
    references = _References()
    references.feed(page)
    assert references.urls == [
        "/static/design-system/assets/Logos/mark-on-dark.svg",
        "/static/design-system/fonts/fonts.css",
        "/static/design-system/tokens/tokens.css",
        "/static/design-system/components/bundle.css",
        "/static/vendor/react.production.min.js",
        "/static/vendor/react-dom.production.min.js",
        "/static/design-system/components/bundle.js",
        "/static/app.js",
        "/static/finder.js",
        "/static/messages.js",
        "/static/controls.js",
        "/static/watchlists.js",
        "/static/inbox_messages.js",
        "/static/inbox.js",
        "/static/agents.js",
        "/static/settings.js",
        "/static/methodology.js",
        "/static/report_parts.js",
        "/static/charts.js",
        "/static/company.js",
        "/static/company_overview.js",
        "/static/company_chart.js",
        "/static/company_estimates.js",
        "/static/company_financials.js",
        "/static/company_financials_chart.js",
        "/static/company_investor.js",
        "/static/company_research_text.js",
        "/static/company_research.js",
        "/static/company_research_records.js",
    ]
    for url in references.urls:
        assert client.get(url).status_code == 200, url
    fonts = re.findall(r'url\("\./([^"]+)"\)', client.get(references.urls[1]).text)
    assert len(fonts) == 6
    for font in fonts:
        assert client.get(f"/static/design-system/fonts/{font}").status_code == 200, font


def test_index_mounts_the_header_and_the_favicon(client: TestClient) -> None:
    page = client.get("/").text
    assert "<h1" not in page and 'role="tab"' not in page
    assert 'id="header"' in page
    assert '<link rel="icon" href="/static/design-system/assets/Logos/mark-on-dark.svg"' in page


def test_controls_js_mounts_app_header() -> None:
    script = _static_file("controls.js")
    assert "h(F.AppHeader, {" in script
    assert "engineRanAt:" in script and "onViewChange: show" in script


def test_header_has_the_six_views() -> None:
    """Spec 2026-11-06 Tier 2, 18.5: a sixth header view, Inbox, after Settings, its count the
    unread messages (spec 2026-11-25 owner's inbox, 7.5); the company page stays a panel no header
    view names. The views stand in the founder's order, Groups under its name Statistics (spec
    2026-11-23 refresh experience, 4.6)."""
    js = _static_file("controls.js")
    assert (
        "views: [{ id: 'screen', label: 'Screen' }, { id: 'watchlists', label: 'Watchlists' },\n"
        "        { id: 'statistics', label: 'Statistics' }, "
        "{ id: 'methodology', label: 'Methodology' },\n"
        "        { id: 'settings', label: 'Settings' },\n"
        "        { id: 'inbox', label: 'Inbox', count: state.unread }],"
    ) in js
    assert "view: state.tab === 'company' ? '' : state.tab," in js
    assert "location.hash" in js and "history.replaceState" in js
    html = _static_file("index.html")
    for panel in ("watchlists", "statistics", "methodology", "settings", "inbox"):
        assert f'<section id="{panel}" hidden' in html
    _in_order(html, '<section id="settings" hidden>', '<section id="inbox" hidden>')


def test_the_count_follows_the_poll() -> None:
    """Spec 2026-11-25 owner's inbox, 7.5 and 7.7: the header's Inbox count is the unread
    messages, as FairbandPage.messages (messages.js) counts them on each read of the work items
    and the list of those the owner saw. The page reads /api/inbox as it loads and every thirty
    seconds after, whether a refresh runs or not, on a cycle of its own, hidden or shown: the read
    writes nothing on the server, and shown again the page reads at once. The header draws again
    only when the count moves, at a read and when messages.js says it may have moved (listen); a
    failed read keeps the count and the next read comes all the same; the Inbox view hands its own
    reads over, so the count follows the table it shows, and while it shows, its table takes each
    of the header's reads (onInbox). At 0 the bundle draws no count. The behaviour is
    tests/web/test_messages.py's."""
    js = _static_file("controls.js")
    assert "var INBOX_MS = 30000;" in js
    assert "unread: 0, /* the unread messages: the Inbox entry's count (messages.js) */" in js
    read = _function(js, "pollInbox")
    _in_order(
        read,
        "clearTimeout(inboxTimer);",
        "var request = ++latestInbox;",
        "P.getJson('/api/inbox')",
        "if (request !== latestInbox) return;",
        "countInbox(body.items);",
        "if (P.onInbox) P.onInbox(body.items);",
        ".catch(function () { /* the count stays as it was */ })",
        "if (request === latestInbox) inboxTimer = setTimeout(pollInbox, INBOX_MS);",
    )
    assert (
        "document.addEventListener('visibilitychange', function () {\n"
        "    if (!document.hidden) pollInbox();\n"
        "  });"
    ) in js
    assert "setUnread(P.messages.landed(items));" in _function(js, "countInbox")
    _in_order(
        _function(js, "setUnread"),
        "if (n === state.unread) return;",
        "state.unread = n;",
        "render();",
    )
    assert "P.messages.listen(function () { setUnread(P.messages.unread()); });" in js
    # the view's read after its write wins over a poll still in flight, and the cycle goes on
    _in_order(
        _function(js, "inboxRead"),
        "++latestInbox;",
        "clearTimeout(inboxTimer);",
        "countInbox(items);",
        "inboxTimer = setTimeout(pollInbox, INBOX_MS);",
    )
    assert "P.countInbox = inboxRead;" in js
    assert js.rstrip().endswith("render();\n  poll(true);\n  pollInbox();\n})();")
    view = _static_file("inbox.js")
    assert "P.countInbox(body.items);" in _function(view, "load")
    # the header's reads redraw the view's table while it shows, unless its own read is in flight
    _in_order(
        _function(view, "fromHeader"),
        "if (panel.hidden || state.loading) return;",
        "state.items = items;",
        "render();",
    )
    assert "P.onInbox = fromHeader;" in view
    bundle = _component_file("bundle.js")
    assert "v.count ? h('span', { className: 'fb-hdr__count figure-sm' }, v.count) : null" in bundle


def test_one_copy_of_the_open_states_and_the_refusal() -> None:
    """A work item's open states and a refused write's sentence and its reason are app.js's, on
    FairbandPage, and the Inbox view, the Watchlists view and the Agents section read them there;
    the header, which counts the unread messages and no longer the open items, keeps no copy. The
    reason is the server's string detail as it arrived, or the status when the server sent none;
    the sentence is the reason led by the write's head."""
    app = _static_file("app.js")
    assert "var OPEN_STATES = ['pending', 'claimed'];" in app
    assert "refusal: refusal" in app and "OPEN_STATES: OPEN_STATES" in app
    assert "refusalDetail: refusalDetail" in app
    _in_order(
        _function(app, "refusal"),
        "if (r.ok) return null;",
        "return head + ': ' + refusalDetail(r) + '.';",
    )
    _in_order(
        _function(app, "refusalDetail"),
        "return r.body && typeof r.body.detail === 'string' ? r.body.detail",
        ": 'the server answered ' + r.status;",
    )
    for name, uses in (
        ("controls.js", ()),
        ("inbox.js", ("var OPEN = P.OPEN_STATES;", "var refusal = P.refusal;")),
        ("watchlists.js", ("var refusal = P.refusal;",)),
        ("agents.js", ("P.refusal('Not saved', r)", "P.refusalDetail(r)")),
    ):
        js = _static_file(name)
        assert "function refusal(" not in js and "['pending', 'claimed']" not in js, name
        assert "function detailOf(" not in js, name
        for text in uses:
            assert text in js, (name, text)


def test_controls_js_names_a_missing_worker() -> None:
    """The server answers 503 only from an app built without a refresh worker; serve always
    builds one, so the page names the state and sends the reader nowhere."""
    script = _static_file("controls.js")
    assert "notify('No refresh worker.', false);" in script
    assert "vendor keys" not in script


def test_page_opens_the_view_the_hash_names() -> None:
    """Spec 2026-11-04 6: the hash follows the view, none for the Screen, and names the view on
    load and when a link changes it; #methodology/<section-id> opens the Methodology view and
    keeps the section for its script to scroll to; a hash naming no view is the Screen. Each view
    loads through FairbandPage.onShow as it opens, every panel but the Methodology view's fades
    while a refresh runs, and FairbandPage.find puts a symbol in FIND with the filters cleared and
    opens the Screen. The company page's hash is tests/web/test_company_page.py's, the report
    page's old addresses test_a_report_s_old_address_opens_the_research_tab's, and the watchlist
    page's list, #watchlists/<id>, under whose head the Screen's panel shows,
    tests/web/test_watchlist_page.py's."""
    js = _static_file("controls.js")
    assert (
        "var VIEWS = ['screen', 'watchlists', 'statistics', 'methodology', 'settings', 'inbox',"
        " 'company'];"
    ) in js
    show = js[js.index("function show(tab, section, id, report) {") :]
    show = show[: show.index("\n  }\n")]
    assert "if (VIEWS.indexOf(tab) === -1 || (tab === 'company' && !section)) tab = 'screen';" in (
        show
    )
    assert "P.section = tab === 'methodology' && section ? section : null;" in show
    assert "history.replaceState(null, '', tab === 'screen' ? location.pathname" in show
    assert (
        ": '#' + tab + (P.section ? '/' + P.section : '') + (tab === 'company' ? companyPath() : '') +"
    ) in show
    assert "(tab === 'watchlists' && P.listId != null ? '/' + P.listId : ''));" in show
    assert "panels[id].hidden = id !== tab && !(id === 'screen' && tab === 'watchlists');" in show
    assert "if (P.onShow[tab]) P.onShow[tab]();" in show
    assert "var parts = location.hash.slice(1).split('/');" in js
    assert "else show(parts[0], parts[1], parts[2], parts[3]);" in js
    assert "window.addEventListener('hashchange', fromHash);" in js
    # the first view opens once the later scripts have registered their loaders
    assert "document.addEventListener('DOMContentLoaded', fromHash);" in js
    assert "P.show = show;" in js and "P.onShow = {};" in js and "P.section = null;" in js
    assert "P.running = function () { return state.running !== null; };" in js
    # every panel but the Methodology view's, whose examples are figures as of a named date, and
    # only under a run of the whole screen (spec 2026-11-23 refresh experience, 4.1)
    assert "VIEWS.forEach(function (id) {\n" in js
    assert "var faded = alive && whole(state.running);" in js
    assert "if (id !== 'methodology') panels[id].classList.toggle(RECOMPUTING, faded);" in js
    # a faded panel's tables keep their old figures at ink-faint, a phase number its colour on its
    # fill; the Research tab's, a report's appendixes on the report's own snapshot, which no
    # refresh changes, are not faded
    page = _static_file("index.html")
    assert (
        "  .is-recomputing .fb-table:not(.app-research .fb-table) tbody td,\n"
        "  .is-recomputing .fb-table:not(.app-research .fb-table) tbody td *:not(.fb-phase__n) {\n"
        "    color: var(--ink-faint);\n"
        "  }\n"
    ) in page
    assert page.count(".is-recomputing") == 2  # the fade's two lines, no other rule
    app = _static_file("app.js")
    assert "find: find" in app  # on window.FairbandPage
    find = app[app.index("function find(symbol) {") :]
    find = find[: find.index("\n  }\n")]
    assert "state.query = symbol;" in find and "state.filters = F.EMPTY_FILTERS;" in find
    assert "window.FairbandPage.show('screen');" in find


def test_index_scrolls_the_new_panels_and_the_header_wraps_at_phone_width() -> None:
    """The new panels scroll as the statistics' does; under 980px, where the one-line header with
    the six views and the Inbox count no longer fits (measured in a browser: about 970px with a
    two-figure count before the refresh buttons' words wrap), the views take a line of their own
    under the lockup and the header grows by it, so the page never scrolls sideways (spec
    2026-11-04 6; 2026-11-06 Tier 2, 18.5)."""
    page = _static_file("index.html")
    assert "#screen, #statistics, #methodology, #settings, #inbox {" in page
    assert "#statistics, #methodology, #settings, #inbox { overflow: auto; }" in page
    # the watchlist page's head, its own height, over the Screen's panel (spec 2026-11-22)
    assert "#watchlists { flex: none; padding: var(--space-2) var(--space-6); }" in page
    css = _component_file("bundle.css")
    patch = css[css.index("/* fairband: below 980px, where the one-line header") :]
    comment = patch[: patch.index("*/")]
    assert "(spec 2026-11-04 6)" in comment and "spec 2026-11-06 Tier 2, 18.5" in comment
    patch = patch[: patch.index("\n}\n")]
    assert "@media (width < 980px) {" in patch
    assert ".fb-hdr { flex-wrap: wrap; height: auto; row-gap: 0; }" in patch
    assert ".fb-hdr__nav { order: 1; flex-basis: 100%;" in patch
    # B-82: the refresh controls stay beside the lockup at phone width (the stamp gives way below
    # 560px, the buttons shorten below 400px), and the six views wrap below 450px, where they and
    # the count no longer fit inside the page's margins.
    for text in (
        ".app-actions__short { display: none; }",
        "@media (width < 560px) {\n    .fb-hdr__ran { display: none; }",
        (
            "@media (width < 400px) {\n    .app-actions__long { display: none; }\n"
            "    .app-actions__short { display: inline; }"
        ),
        (
            "@media (width < 450px) {\n    .fb-hdr__nav { flex-wrap: wrap; height: auto;"
            " min-height: var(--header-height); row-gap: 0; }"
        ),
    ):
        assert text in page, text
    controls = _static_file("controls.js")
    for text in (
        "'aria-label': 'Refresh prices'",
        "label('Refresh prices', 'Prices')",
        "'aria-label': 'Refresh all'",
        "label('Refresh all', 'Full')",
        "className: 'app-actions__long' }, full)",
        "className: 'app-actions__short' }, short)",
    ):
        assert text in controls, text


def test_the_diagram_keeps_its_labels_legible_at_phone_width() -> None:
    """B-82: the diagram scales to its panel down to 800px and no further, scrolling sideways in a
    narrower one, so its captions stay above 9px where the whole drawing at 327px set them at 4."""
    page = _static_file("index.html")
    assert "overflow-x: auto;" in _rule(page, ".app-life {")
    svg = _rule(page, ".app-life__svg {")
    assert "width: 100%;" in svg and "min-width: 800px;" in svg


def test_controls_js_run_bar() -> None:
    script = _static_file("controls.js")
    assert "h(F.RunProgress, runProps(state.running))" in script
    for stage, word in (
        ("universe", "reading the universe"),
        ("deciles", "ranking"),
        ("backfill", "reading stored statements"),
        ("fetch", "fetching"),
        ("value", "valuing"),
        ("quotes", "fetching prices"),
        ("reprice", "repricing"),
        ("done", "finishing"),
        # the exchange rates of a full or scoped refresh and the pairs' quotes of a price refresh
        # (spec 2026-11-10 7.1)
        ("rates", "fetching exchange rates"),
        ("fx", "quoting exchange rates"),
        # the moat table read into the database, and a moat write's revalue (spec 2026-11-19 8.4,
        # 8.6)
        ("moat", "reading the moat table"),
    ):
        assert f"{stage}: '{word}'" in script, stage
    assert "progressLine" not in script
    # the header gets no run prop
    assert "run:" not in script.split("h(F.AppHeader, {")[1].split("})")[0]


def test_controls_js_handles_a_zero_total() -> None:
    script = _static_file("controls.js")
    assert "total > 0 ? h(F.RunProgress" in script or "props.total > 0 ? h(F.RunProgress" in script
    assert "done: 0" in script  # the universe and deciles stages show nothing done


def test_controls_js_one_line_status_and_details_menu() -> None:
    """Growth-routes spec 6.1: the last refresh is one line, the kind, the status, the finish and
    the valued count, with the failed count when there is one; its breakdown is in Details ▾."""
    script = _static_file("controls.js")
    assert "calibrationLine" not in script
    assert "' of '" in script and "' valued'" in script and "' failed'" in script
    assert "'Details ▾'" in script and "state.detailsOpen" in script
    for section in ("'FLAGGED'", "'PHASES'", "'REFUSED'"):
        assert section in script, section
    assert "'pointerdown'" in script and "'Escape'" in script
    # focus moving outside closes it too, so a keyboard user opening another menu closes it
    assert "document.addEventListener('focusin', closeDetailsOutside);" in script
    # the popover follows the bundle's menu markup, and a run closes it
    assert "className: 'fb-screen__cols app-details'" in script
    assert "'aria-expanded': state.detailsOpen ? 'true' : 'false'" in script
    assert (
        "if (body.refresh !== null) {\n"
        "          /* the rows as the run began, which its end's marks are set against (4.2) */\n"
        "          if (!alive) P.baseline();\n"
        "          state.detailsOpen = false;"
    ) in script
    # the line starts at the kind, as spec 6.1 writes it
    assert "Last refresh: " not in script
    assert "var line = [last.kind + ' ' + last.status + (when ? ' ' : ''), when];" in script
    # a full refresh's or a revalue's failed companies are its refusals of the three reasons the
    # refresh writes; a price refresh's calibration counts them
    assert (
        "var FAILED_REASONS = ['data fetch failed', 'data fetch incomplete', 'valuation failed'];"
        in (script)
    )
    assert "if (c.failed != null) return c.failed;" in script


def test_page_hands_the_design_system_local_time() -> None:
    """The server writes UTC (+00:00) and the design system prints a string's own hour and
    minute, so every timestamp the page hands it is first put in the browser's offset; a plain
    date passes through."""
    app = _static_file("app.js")
    assert "function localIso(iso) {" in app
    assert "String(iso).indexOf('T') < 0" in app  # a plain date is a day, not an instant
    assert "getTimezoneOffset()" in app
    assert "localIso: localIso" in app  # on window.FairbandPage, for controls.js
    assert "var local = localIso(iso);" in app  # when(): the inputs table's observed and entered
    assert "state.rows = body.rows.map(localRow);" in app  # the table's Entered cell
    assert "{ enteredAt: localIso(r.enteredAt) }" in app
    controls = _static_file("controls.js")
    assert "engineRanAt: ran ? P.localIso(ran) : null" in controls
    assert "P.localIso(last.finishedAt)" in controls  # the last-refresh line


def test_app_js_find_and_filters() -> None:
    script = _static_file("app.js")
    for prop in (
        "query: view.query",
        "onQueryChange:",
        "filters: view.filters",
        "onFiltersChange:",
        "sectors: sectorsOf(all)",
        "total: all.length",
    ):
        assert prop in script, prop
    # the view that shows, the Screen's FIND and filters on the Screen's loaded rows, or the
    # watchlist page's on its list's (tests/web/test_watchlist_page.py)
    assert "var all = state.onList ? listed() : state.rows;" in script
    assert "var rows = narrow(all, view.query, view.filters);" in script
    # the screen's script draws no footnote of its own: ReportReader numbers a cite from the
    # footnotes its caller hands it (spec 2026-11-06 Tier 2, 13.1)
    assert "'sup'" not in script and "[^" not in script


def test_app_js_query_is_trimmed_and_lower_cased() -> None:
    script = _static_file("app.js")
    assert "(query || '').trim().toLowerCase()" in script
    assert "r.ticker.toLowerCase().indexOf(needle) === 0" in script
    assert "(r.name || '').toLowerCase().indexOf(needle) !== -1" in script


def test_app_js_sorts_designation_by_the_ratio() -> None:
    """Spec 7.3: the designation column asks the server for the price-to-value order."""
    script = _static_file("app.js")
    assert (
        "var SORT_KEYS = { band: 'fairLow', designation: 'priceToValue', entered: 'enteredAt',"
        in script
    )


def test_app_js_narrows_on_the_designation() -> None:
    """The word is the row's, never derived on the page: a row without one (a refusal, a
    placeholder) matches no designation filter, as a row without a cap band matches no cap."""
    script = _static_file("app.js")
    assert "within(filters.designation, r.designation) &&" in script
    assert "(r.capBand || '').toLowerCase()" in script


def test_app_js_narrows_on_the_stance() -> None:
    """Spec 2026-11-06 Tier 2, 18.1: a non-empty STANCE group keeps the rows whose published word
    it names, so a row without a report matches none; the column asks the server for its own key,
    which the server orders by the words."""
    script = _static_file("app.js")
    assert "within(filters.stance, r.agentStance) &&" in script
    assert "agentStance: 'agentStance' };" in script
    narrowing = script[script.index("function narrow(") : script.index("function sectorsOf(")]
    assert narrowing.index("filters.designation") < narrowing.index("filters.stance")
    assert "filters.stance" not in script.replace("within(filters.stance, r.agentStance)", "")
    # the report's time in the reader's offset, as the Entered date is, for the mark's title
    assert "row.covered = Object.assign({}, r.covered, { at: localIso(r.covered.at) });" in script


def test_app_js_narrows_on_watchlist() -> None:
    js = _static_file("app.js")
    # the Clean filter is gone (spec 2026-11-19 7.5): the narrowing ends at Hide expired, and no
    # line reads a flag count
    narrowing = js[js.index("function narrow(") : js.index("function sectorsOf(")]
    assert "(!filters.hideExpired || r.freshness !== 'expired');\n" in narrowing
    assert "cleanOnly" not in js and "flagCount" not in narrowing and "Clean" not in narrowing
    assert "r.fairValue != null" not in js
    assert "'/api/watchlists/memberships/' + encodeURIComponent(symbol)" in js


def test_app_js_opens_the_watchlist_popup() -> None:
    """Spec 2026-11-04 9.4: the screen passes onWatch and the lists' names; a row is watched when
    it is on a list; the popup creates a list and puts the company on it in one step, writes a
    change at once and closes on Escape or a press or focus outside it. The lists load on page
    load and after every write, and the later views read them."""
    js = _static_file("app.js")
    for text in (
        "within(filters.watchlist, r.watchlists || [])",
        "watched: (r.watchlists || []).length > 0",
        "onWatch: watch,",
        "watchlists: state.watchlists || [],",
        "put: function (url, body) { return send('PUT', url, body); }",
        "api.post('/api/watchlists', { name: name })",
        "placeholder: 'New watchlist'",
        "h(F.Button, { type: 'submit', size: 'sm', disabled: !w.name.trim() }, 'Add')",
        "document.addEventListener('pointerdown', closeWatchOutside);",
        "document.addEventListener('focusin', closeWatchOutside);",
        "if (event.key !== 'Escape' || !state.watch) return;",
        "watchlists: function () { return state.watchlists; },",
        "reloadWatchlists: reloadWatchlists,",
    ):
        assert text in js, text


def test_watchlists_view_creates_renames_deletes_and_adds() -> None:
    js = _static_file("watchlists.js")
    assert (
        "'No watchlists yet. Create one here, or press the mark beside a ticker on the screen.'"
        in js
    )
    assert "P.api.post('/api/watchlists', { name: name })" in js
    assert "method: 'PATCH'" in js and "method: 'DELETE'" in js
    assert "h(F.ConfirmDialog, {" in js  # Delete confirms with the name and the count
    assert "placeholder: 'Add a company'" in js and ".slice(0, 8)" in js
    html = _static_file("index.html")
    assert '<script src="/static/watchlists.js"></script>' in html


def test_watchlists_view_draws_the_screen_rows_and_a_symbol_without_one() -> None:
    """Spec 2026-11-04 9.6, as the watchlist page keeps it (spec 2026-11-22 7.1): a list's rows are
    the screen's loaded rows, each watched, and a symbol with no row (it left the universe, or has
    no snapshot) stays, its ticker alone with an em dash in every other cell; the Screen's own
    table draws them (app.js, listRows; tests/web/test_watchlist_page.py). The head follows each
    draw of the screen, so it follows the rows and the lists as they load. Its writes go through
    FairbandPage.api, which gains PATCH and DELETE beside POST and PUT."""
    js = _static_file("watchlists.js")
    assert (
        "{ ticker: symbol, name: null, price: null, mechanical: null, reviewed: null, "
        "phase: null, fairLow: null, fairHigh: null, watched: true }"
    ) in " ".join(_static_file("app.js").split())
    for text in (
        "P.onShow.watchlists = function () {\n    state.selected = null;\n    follow();\n  };",
        "P.onRender = follow;",
        "title: 'Delete ' + d.name,",
        "payload: { name: d.name, companies: d.count },",
        "/^[A-Za-z0-9.-]{1,10}$/",
        "P.api.patch('/api/watchlists/' + id, { name: name })",
        "P.api.del('/api/watchlists/' + d.id)",
        "P.reload();",
        "return P.reloadWatchlists();",
    ):
        assert text in js, text
    app = _static_file("app.js")
    for text in (
        "patch: function (url, body) { return send('PATCH', url, body); },",
        "del: function (url) { return send('DELETE', url); }",
        "rows: function () { return state.rows; },",
        "if (page.onRender) page.onRender();",
    ):
        assert text in app, text
    page = _static_file("index.html")
    assert "#screen .fb-screen__name:empty::before { content: '—'; color: var(--ink-faint); }" in (
        page
    )


def test_watchlists_view_enter_adds_only_a_chosen_company() -> None:
    """Spec 2026-11-04 9.6: the field adds the chosen company. Enter adds the row whose ticker the
    text spells, ignoring case, or the one match shown; a ticker already on the list adds nothing
    and the line under the field says so; a text no row matches is added as typed when it is a
    symbol. Any other choice is a match's button: Enter never adds the first of several."""
    js = _static_file("watchlists.js")
    for text in (
        "var typed = text.trim().toUpperCase();",
        "if (r.ticker.toUpperCase() === typed) exact = r;",
        "if (exact) onEnter = on[exact.ticker] ? null : exact.ticker;",
        "else if (shown.length === 1) onEnter = shown[0].ticker;",
        "else if (asTyped) onEnter = asTyped;",
        "hint = exact.ticker + ' is on this list.';",
        "if (onEnter) add(list.id, onEnter);",
        "onClick: function () { add(list.id, r.ticker); }",
    ):
        assert text in js, text
    assert "add(list.id, shown[0].ticker)" not in js


def test_the_inbox_view_columns_are_pinned(client: TestClient) -> None:
    """Spec 2026-11-06 Tier 2, 18.5: the Inbox view, its own script after watchlists.js, is one
    table of the work items as the server lists them, newest first, under the heads Symbol, Mode,
    State, Posted, By, Claimed by, Note and Report: the symbol a link to the company page (spec
    2026-11-22, 11); the state word, with a declined item's reason under it as written; the posted
    date and time in the reader's time; who posted it, a compact PrincipalChip (the owner, an agent
    by its model identifier, or the system for an expiry item), and the agent that claimed it
    likewise; the note as written; the report a done item was completed with, as a link to its page
    named by its revision (plan 4). A pending or claimed item has Decline, which opens the reason
    line under the row (spec 18.5's "reason line"): the field, Decline, which sends the owner's
    decline, and Cancel; a refused decline's sentence, the server's, stands on a line under the
    row. The read runs as the view opens and after every write, and the drawer, if it shows the
    company, reads it again. "No work items." when there are none. Every field of an item the view
    reads is one the server sends."""
    js = _static_file("inbox.js")
    assert (
        "var HEADS = ['Symbol', 'Mode', 'State', 'Posted', 'By', 'Claimed by', 'Note', 'Report'];"
        in js
    )
    assert "var OPEN = P.OPEN_STATES;" in js
    row = _function(js, "row")
    _in_order(
        row,
        "var open = OPEN.indexOf(item.state) !== -1;",
        "var declining = open && state.declining === item.id;",
        "href: P.companyHref({ ticker: item.symbol })",
        "h('td', { className: 'body' }, item.mode),",
        "h('td', { className: 'body app-inbox__wrap' }, item.state,",
        "item.state === 'declined' && item.reason",
        "posted(item.postedAt)",
        "h(F.PrincipalChip, { principal: item.postedBy, actor: item.postedActor, compact: true })",
        "h(F.PrincipalChip, { principal: 'agent', actor: item.claimedBy, compact: true })",
        "h('td', { className: 'body app-inbox__wrap' }, item.note || none()),",
        # a done item's report on the Research tab (tests/web/test_inbox_launch.py draws it)
        "className: 'app-link', href: P.researchHref(item.symbol, item.reportId),",
        # the launch's button stands before Decline (B-210; tests/web/test_inbox_launch.py)
        "h('td', null, parts.button, open && !declining ? h(F.Button, {",
        "state.declining = item.id;",
        "}, 'Decline') : null)),",
        "declining ? reasonLine(item) : null,",
        "state.errors[item.id] ? refused(state.errors[item.id]) : null,",
    )
    assert "colSpan: HEADS.length + 1" in _function(js, "refused")
    line = _function(js, "reasonLine")
    _in_order(
        line,
        "state.declining = null;",
        "colSpan: HEADS.length + 1",
        "onSubmit: function (event) { event.preventDefault(); decline(item); }",
        "autoFocus: true,",
        "placeholder: 'Reason', 'aria-label': 'Reason for declining ' + item.symbol,",
        "if (event.key === 'Escape') close();",
        "type: 'submit', size: 'sm', disabled: !reason.trim() || state.pending !== null",
        "}, 'Decline'),",
        "h(F.Button, { variant: 'quiet', size: 'sm', onClick: close }, 'Cancel')",
    )
    decline = _function(js, "decline")
    _in_order(
        decline,
        "if (!reason || state.pending !== null) return;",
        "state.errors = {};",
        "P.api.patch('/api/inbox/' + item.id, { action: 'decline', reason: reason })",
        "return refusal('Not declined', r);",
        "if (error) state.errors[item.id] = error;",
        # a taken decline closes its own reason line, not another row's the owner opened meanwhile
        "if (state.declining === item.id) state.declining = null;",
        "P.reloadDetail(item.symbol);",
        "return load();",
    )
    view = _function(js, "View")
    assert (
        "items && items.length === 0 ? h('p', { className: 'body app-note' }, 'No work items.')"
    ) in view
    # focus waits for the read after a decline: the field when the item is still open, else the
    # row's symbol, since a refused decline's item may have closed elsewhere
    assert "if (!state.focus || state.loading) return;" in view
    _in_order(
        decline,
        "state.focus = (error ? [inRow(item.id, '.app-inbox__reason')] : [])",
        ".concat([inRow(item.id, '.app-inbox__symbol')]);",
    )
    assert "P.onShow.inbox = load;" in js
    assert "reloadDetail: reloadDetail" in _static_file("app.js")
    html = _static_file("index.html")
    _in_order(
        html,
        '<script src="/static/watchlists.js"></script>',
        '<script src="/static/inbox.js"></script>',
    )
    assert ".app-inbox.is-loading .fb-table tbody td { color: var(--ink-faint); }" in html
    # the note and the state wrap, and the refusal line too: the table's own nowrap yields
    assert "white-space: normal;" in _rule(html, ".app-inbox .fb-table td.app-inbox__wrap {")
    assert "white-space: normal;" in _rule(html, ".app-inbox .fb-table td.app-inbox__error {")
    # every field of an item the view reads is one the server sends
    client.post("/api/inbox", json={"symbol": "AAPL", "mode": "full report"}, headers=HEADER)
    [item] = client.get("/api/inbox").json()["items"]
    read = set(re.findall(r"\bitem\.(\w+)", js))
    assert read and read <= set(item), read - set(item)


def test_items_are_named_by_number_and_time() -> None:
    """Spec 18.5 (plan 4): two items on one day read the same by date alone. An item's Posted
    cell is ``P.when``'s element in the reader's local time; a done item's report link names its
    revision, in its text and its accessible name, and reads Open when the server sends none. The
    Research tab's reports on file are named by date and revision
    (``tests/web/test_company_research.py``)."""
    inbox = _code(_static_file("inbox.js"))
    assert "return P.when(iso);" in _function(inbox, "posted")
    row = _function(inbox, "row")
    assert "item.reportRevision != null ? 'revision ' + item.reportRevision : 'Open'" in row
    _in_order(
        row,
        "'aria-label': item.reportRevision != null",
        "? 'Open revision ' + item.reportRevision + ' of the report for ' + item.symbol",
        ": 'Open the report for ' + item.symbol",
    )


def test_the_drawer_s_head_and_appendix_a_say_what_the_figures_are_in() -> None:
    """Spec 2026-11-10 7.4 and 10: the line that names the reporting currency, the ADS and the rate
    (``currencyLine``, its words in ``tests/web/test_drawer_currency.py``) is in the drawer under
    the value band, before the buttons (the founder, 2026-11-24: it stood in the head, where its
    one line or two moved the meter), and under the Research tab's bar, the same line, which
    names no ratio (spec 2026-11-19 6.2; ``tests/web/test_company_research.py``); none on a
    domestic row. Appendix A's secondary valuation reads its totals and its parts in the currency
    and names the rate."""
    script = _static_file("app.js")
    main = _function(script, "sections")
    _in_order(
        main,
        "className: 'body app-drawer__name'",
        "className: 'caption app-muted app-drawer__sector'",
        "className: 'app-drawer__band'",
        "currency ? h('p', { key: 'currency', className: 'caption app-muted app-drawer__currency' },",
        "className: 'app-drawer__actions'",
    )
    assert "var currency = currencyLine(body);" in main
    assert "currency: props.detail ? P.currencyLine(props.detail) : ''," in (
        _function(_static_file("company_research.js"), "Research")
    )
    appendix = _function(_code(_static_file("report_parts.js")), "secondary")
    for text in (
        "var code = s.currency;",
        "code !== 'USD' ? [['Rate', code + ' ' + P.rate(s.fxRate) + ' per USD', true]] : [],",
        "['Firm value', P.whole(s.firmValue, code), true],",
        "P.secondaryPath(s, code),",
    ):
        assert text in appendix, text


def test_bundle_confirm_dialog_takes_a_danger_confirm() -> None:
    """Spec 2026-11-04 9.6: a delete's one affirmative button is the danger one. ConfirmDialog
    shows no revision without targetRevision and no Reject without onReject, and confirmVariant
    styles Confirm; the Watchlists view's Delete passes neither and the danger variant."""
    bundle = _component_file("bundle.js")
    dialog = bundle[bundle.index("  function ConfirmDialog(props) {") :]
    dialog = dialog[: dialog.index("\n  }\n")]
    assert "// fairband:" in dialog and "(spec 2026-11-04 9.6)" in dialog
    assert ": p.targetRevision == null ? null : h('p', { className: 'fb-rec__gloss caption' }," in (
        dialog
    )
    assert "variant: p.confirmVariant === 'danger' ? 'danger' : 'primary', size: 'sm'," in dialog
    assert (
        ": p.onReject ? h(Button, { variant: 'danger', size: 'sm', onClick: p.onReject }, 'Reject')"
        in dialog
    )
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ConfirmDialogProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    assert "confirmVariant?: 'primary' | 'danger';" in props.group(1)
    js = _static_file("watchlists.js")
    view = js[js.index("h(F.ConfirmDialog, {") :]
    view = view[: view.index("}));")]
    assert "confirmVariant: 'danger'," in view
    assert "targetRevision" not in view and "onReject" not in view


def test_the_validity_window_judges_aging_as_the_screen_does() -> None:
    """ValidityWindow takes ``agingFraction``, 0.6667 by default, and judges its state by the
    server's rule (``validity_state``): on whole days, aging from that fraction of the window,
    expired after its last day, so a caller that passes the route's figure reads as the Freshness
    column does after a change of ``aging_fraction`` (spec 2026-11-04 8.2). A `// fairband:`
    patch the bundle keeps, though no page draws the window since it left the drawer."""
    bundle = _component_file("bundle.js")
    window = bundle[bundle.index("  function ValidityWindow(props) {") :]
    window = window[: window.index("\n  }\n")]
    assert (
        "// fairband: the state as the screen's Freshness column judges it (spec 2026-11-04 8.2)"
        in (window)
    )
    for text in (
        "var fraction = p.agingFraction == null ? 0.6667 : p.agingFraction;",
        "var day = function (iso) { return Date.parse(String(iso).slice(0, 10)) / 864e5; };",
        "var elapsed = day(p.today || p.enteredAt || p.validFrom) - day(p.validFrom);",
        "var length = day(p.validUntil) - day(p.validFrom);",
        "var state = elapsed > length ? 'expired' : elapsed >= fraction * length ? 'aging'",
    ):
        assert text in window, text
    assert "0.6667 ?" not in window and "ratio > 1" not in window
    declarations = _component_file("index.d.ts")
    props = re.search(
        r"export interface ValidityWindowProps \{\n(.*?)\n\}", declarations, re.DOTALL
    )
    assert props is not None
    assert "agingFraction?: number;" in props.group(1)
    assert "(spec 2026-11-04 8.2)" in props.group(1)
    assert "ValidityWindow" not in _code(_static_file("app.js"))


def test_settings_view_form_and_notices() -> None:
    js = _static_file("settings.js")
    # the notice names what changed: the user's settings (the hash), else the policy's version
    assert "var sentence = v.settingsHash !== c.settingsHash" in js
    assert "? 'Your settings changed since the last valuation.'" in js
    assert ": 'The policy changed since the last valuation.';" in js
    assert "h('p', { className: 'caption' }, sentence)," in js
    assert "'Revalue now'" in js and "P.api.post('/api/refresh', { kind: 'revalue' }" in js
    assert "'A universe setting changed since the last full refresh: run Refresh all.'" in js
    assert "'takes effect at the next revalue'" in js and "'takes effect at once'" in js
    assert "h(F.ConfirmDialog, {" in js and "payload: payload" in js
    assert "'Reset'" in js and "'Save'" in js and "placeholder: 'Reason (optional)'" in js
    assert (
        "UNITS = { fraction: '%', points: ' points', years: ' years', times: '×', days: ' days', seconds: ' s', hours: ' h', count: '', usd: '$' }"
        in js
    )


def test_settings_view_saves_through_the_dialog_and_follows_the_run() -> None:
    """Spec 2026-11-04 8.5: the view loads from GET /api/settings as it opens; Save confirms the
    changes, old to new, and sends them with the reason in one PUT; a 400's "<name>[, <name>]:
    <rule>" stands beside the field of the named setting the user changed (B-75), and the dialog
    shows the cap bands a changed size floor carries (8.9). A stored setting the policy refuses makes GET answer 409: the view
    shows the sentence and Reset all settings, a reset with no names. Revalue now posts a revalue
    the header then follows, handed the id the answer gave, so the revalue is the page's own and
    locks it, and none after a 409 (spec 2026-11-23 refresh experience, 4.1); the view asks
    FairbandPage.running() while it is open, so the button turns off for a run and the notice is
    read again when the run ends."""
    js = _static_file("settings.js")
    for text in (
        "P.onShow.settings = function () {",
        "fetch('/api/settings')",
        "title: 'Change ' + n + ' setting' + (n === 1 ? '' : 's'),",
        "state: state.saving ? 'confirming' : 'open',",
        "P.api.put('/api/settings', { changes: changes, reason: reason })",
        "var names = detail.slice(0, detail.indexOf(':')).split(', ');",
        "var name = names.filter(function (n) { return n in changes; })[0] || names[0];",
        "state.error[name] = detail;",
        "payload.push(['universe.cap_bands',",
        "shown(bands, bands.value) + ' → ' + shown(bands, carried) + ', with the size floor']",
        "'Reset all settings'",
        "P.api.post('/api/settings/reset', {})",
        "disabled: state.starting || P.running(),",
        "if (r.status === 409) state.started = 'A refresh is already running.';",
        "if (r.ok) P.followRefresh(r.body ? r.body.refreshId : null);",
        "else if (r.status === 409) P.followRefresh();",
        "if (panel.hidden) {",
        "P.running()",
        "'takes effect at the next full refresh'",
        "'takes effect at the next refresh'",
        "['NYSE', 'NASDAQ', 'AMEX']",
        "['Mega', 'Large', 'Mid']",
    ):
        assert text in js, text
    # the notice: a version or a hash unlike the current one, and only once a snapshot exists
    assert "v.settingsHash != null && (v.settingsHash !== c.settingsHash ||" in js
    assert "v.policyVersion !== c.policyVersion)" in js
    controls = _static_file("controls.js")
    assert (
        "P.followRefresh = function (id) {\n    started = true;\n    if (id != null) keepMine(id);\n"
        "    poll();\n  };"
    ) in controls
    page = _static_file("index.html")
    assert '<script src="/static/settings.js"></script>' in page
    assert page.index("/static/watchlists.js") < page.index("/static/settings.js")
    for text in (
        ".app-set__changed { color: var(--accent); }",
        ".app-set__error { margin: var(--space-1) 0 0; color: var(--caution); }",
        ".app-set__notice {",
    ):
        assert text in page, text
    num = page[page.index(".app-set__num {") :]
    num = num[: num.index("}")]
    assert "font-family: var(--font-mono);" in num and "text-align: right;" in num


def test_settings_view_shows_each_figure_at_its_own_precision() -> None:
    """A field and the confirm show a figure as the server holds it, never rounded: the decimal
    point moves in the number's own text, both ways, so 8.25% reads 8.25 and is 0.0825, and 8.3%
    can be typed after it."""
    js = _static_file("settings.js")
    for text in (
        "return Number(parts[0] + 'e' + (Number(parts[1] || 0) + places));",
        "if (unit === 'fraction' || unit === 'points') return String(shift(n, 2));",
        "if (unit === 'usd') return String(shift(n, -9));",
        "return grouped(unit === 'fraction' || unit === 'points' ? shift(n, 2) : n);",
        "if (unit === 'fraction' || unit === 'points') return Number(t + 'e-2');",
        "if (unit === 'usd') return Number(t + 'e9');",
    ):
        assert text in js, text
    assert "toFixed" not in js and "toLocaleString" not in js  # nothing rounds a figure


def test_settings_view_labels_each_single_field() -> None:
    """Only a table by moat has three fields: a symbol list, an array, is one field, which the
    row's label names through htmlFor."""
    js = _static_file("settings.js")
    assert "return !!s.value && typeof s.value === 'object' && !Array.isArray(s.value);" in js
    assert "if (byMoat(s)) return { names: MOATS, unit: s.unit };" in js
    assert "h('label', { className: 'body app-set__label', htmlFor: 'set-' + s.name }" in js


def test_settings_view_keeps_one_primary_and_a_true_note() -> None:
    """One primary at a time: Revalue now is primary until the form holds a change, then Save is
    the one. The confirm says what is true of a setting, that Reset undoes it, through the
    dialog's note (spec 2026-11-04 8.5)."""
    js = _static_file("settings.js")
    assert "variant: n ? 'secondary' : 'primary', size: 'sm'," in js
    assert "notice(state.body, n)" in js
    assert "note: 'Reset returns any setting to its default.'," in js
    bundle = _component_file("bundle.js")
    dialog = bundle[bundle.index("  function ConfirmDialog(props) {") :]
    dialog = dialog[: dialog.index("\n  }\n")]
    assert "(spec 2026-11-04 8.5)" in dialog
    assert (
        "h('p', { className: 'fb-dlg__warn-note caption' }, "
        "p.note == null ? 'This cannot be undone.' : p.note),"
    ) in dialog
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ConfirmDialogProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    assert "note?: string;" in props.group(1)


def test_app_js_meter_states_the_ratio_and_has_no_scale() -> None:
    """Spec 7.3 and spec 2026-11-06 Tier 2, 18.2 item 2 (plan 4): the band meter's head says the
    word and price ÷ value over the value's name, "the mechanical value"; the meter's own scale,
    whose words would collide in the rail, is off. The four levels under it are in the screen's
    words (``levelRows``; ``tests/web/test_drawer_form.py``), with no caption of the margin and
    no multiple of the value, and no route's name under them (the company page's design, 11)."""
    script = _static_file("app.js")
    assert "buyLevel: r.levels.buy, trimLevel: r.levels.trim, designation: r.designation," in script
    assert (
        "designation: r.designation,\n        showScale: false,\n"
        "        gap: gapText(r.price_to_value, body.designationEdges, 'the mechanical value'),"
    ) in _function(script, "meter")
    for gone in ("Margin of safety', h(", "' × value'", "value less the", "ROUTES"):
        assert gone not in script, gone


def test_app_js_keeps_the_ratio_figure_inside_the_band() -> None:
    """The caption's two decimals would contradict the word at an edge the ratio is not on
    (0.8499 reads 0.85, where Near starts, beside Below): then a third decimal, kept a thousandth
    off the edge, on the policy's edges from the drawer's body. The CLI's line does the same;
    tests/refresh/test_run.py runs it at the edges."""
    script = _static_file("app.js")
    helper = script[script.index("function ratioFigure(ratio, edges) {") :]
    helper = helper[: helper.index("\n  }\n")]
    assert "var two = ratio.toFixed(2);" in helper
    assert "var edge = Number(two);" in helper
    assert "if (ratio === edge || (edges || []).indexOf(edge) === -1) return two;" in helper
    assert "var three = Number(ratio.toFixed(3));" in helper
    assert (
        "three = ratio < edge ? Math.min(three, edge - 0.001) : Math.max(three, edge + 0.001);"
        in helper
    )
    assert "return three.toFixed(3);" in helper
    assert "r.price_to_value.toFixed(2)" not in script


def test_app_js_normalises_a_saved_column_list() -> None:
    """A saved list keeps its order; a list saved under method 0.5 names the Stance column,
    and Price vs value takes its place, where `stance` stood."""
    script = _static_file("app.js")
    assert "function normalise(columns)" in script
    assert "F.COLUMN_KEYS" in script
    assert (
        "var named = columns.map(function (key) { return key === 'stance' ? 'designation' : key; });"
        in script
    )
    assert "return F.COLUMN_KEYS.indexOf(key) !== -1 && named.indexOf(key) === i;" in script
    assert "if (kept.indexOf('ticker') === -1) kept.unshift('ticker');" in script
    assert "if (kept.indexOf('price') === -1) kept.push('price');" in script
    assert "if (Array.isArray(saved)) return normalise(saved);" in script


def test_figure_tables_scroll_by_keyboard_with_the_year_in_view() -> None:
    """The table of figures by year Appendix A draws (``figuresTable``, report_parts.js), each
    column's head its name: no caller hands a column a note for its head."""
    script = _static_file("app.js")
    assert script.count("h('div', { className: 'app-scroll', tabIndex: 0 },") == 1
    table = _function(script, "figuresTable")
    assert "return h('th', { key: c[0], className: 'label fb-num' }, c[0]);" in table
    assert "c[3]" not in table and "function noted(" not in script
    parts = _static_file("report_parts.js")
    calls = re.findall(r"P\.figuresTable\(\[(.*?)\]\)", parts, re.DOTALL)
    assert len(calls) == 2
    for call in calls:
        # each column three elements: its name, its figures by year and their format
        three = re.findall(r"\['[^']+', column\(p\.years, '\w+'\), \w+\]", call)
        assert len(three) == call.count("['"), call
    page = _static_file("index.html")
    assert (
        ".app-scroll:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }"
        in (page)
    )
    assert ".app-figures th:first-child, .app-figures td:first-child {" in page
    assert "position: sticky; left: 0; background: var(--surface-raised);" in page


def test_app_js_escape_closes_an_open_menu_before_the_drawer() -> None:
    """Escape closes an open menu before the drawer, and closes the drawer only while the Screen
    shows it: in another view the drawer is hidden, and Escape belongs to that view's field. An
    Escape a control has acted on, which says so by preventDefault, is that control's alone: the
    drawer stays (the final review of 2026-11-22; tests/web/test_watchlist_page.py)."""
    script = _static_file("app.js")
    assert "var mount = document.getElementById('screen');" in script
    assert (
        "  document.addEventListener('keydown', function (event) {\n"
        "    if (event.defaultPrevented) return;\n"
        "    if (event.key === 'Escape' && state.drawer && !mount.hidden &&\n"
        "        !document.querySelector('.fb-menu')) close();\n"
        "  });"
    ) in script


def _function(script: str, name: str) -> str:
    """The text of the script's ``function <name>(``, to its closing brace."""
    start = script.index(f"  function {name}(")
    return script[start : script.index("\n  }\n", start)]


def _in_order(text: str, *parts: str) -> None:
    """Each part is in ``text``, each after the one before it."""
    at = [text.index(part) for part in parts]
    assert at == sorted(at), [parts[i] for i in range(len(parts) - 1) if at[i] > at[i + 1]]


def test_the_drawers_order_is_pinned() -> None:
    """The company page's design, 11: the drawer's form A, in this order and nothing else: the
    head, the moat stamp after the phase badge; the caption of the sector and the industry; the
    brief; the value band, the meter and its levels, or a refused row's sentence in its place;
    the line on what the figures are in; then Company page and Request research with its menu
    and the open item's line (``tests/web/test_drawer_form.py`` reads what it draws). The stance,
    the report's Summary, Open the report and Details left it. Request research is the drawer's
    own part, which the company page draws too."""
    script = _static_file("app.js")
    main = _function(script, "sections")
    _in_order(
        main,
        "className: 'app-drawer__head'",
        "h('div', { className: 'app-drawer__id' },",
        "phase ? h(F.PhaseBadge, { phase: phase, size: 'sm' }) : null),",
        "h('div', { className: 'app-drawer__moat' }, moatStamp(body), moatChip(body)),",
        "className: 'body app-drawer__name'",
        "className: 'caption app-muted app-drawer__sector'",
        "className: 'body app-drawer__brief'",
        "rows ? h('section', { key: 'band', className: 'app-drawer__band' }, meter(body),",
        ": r.refusal ? h('section', { key: 'band', className: 'app-drawer__band' },",
        "className: 'caption app-muted app-drawer__currency'",
        "href: '#company/' + encodeURIComponent(r.symbol)",
        "'Company page'",
        "requestResearch(ask, body.item, render, reread(r.symbol), body.launchReady)",
    )
    for gone in ("'Details ▾')", "detailsOpen", "app-stance", "F.ReportReader", "Open the report"):
        assert gone not in script, gone
    ask = _function(script, "requestResearch")
    assert "disabled: !!item || ask.opening," in ask
    assert "'aria-expanded': ask.open ? 'true' : 'false'" in ask
    assert (
        "ask.open ? h(RequestMenu, { ask: ask, redraw: redraw, after: after, ready: ready }) : null"
        in ask
    )
    _in_order(
        ask,
        "'Request research')",
        "ask.error ? h('p', { className: 'caption app-request__error' }, ask.error) : null",
        "requested(ask, item, redraw, after, ready)",
    )
    asked = _function(script, "asked")
    assert (
        "if (!state.request || state.request.symbol !== symbol) state.request = asking(symbol);"
        in (asked)
    )
    assert "mode: 'full report'" in _function(script, "asking")
    # the open item's line (launchLine, spec 2026-11-16 agent launch, 10): none without an item,
    # the claim whatever the launch, pending without one
    assert "if (!line) return null;" in _function(script, "requested")
    # its words (launchWords) after the word Requested, which the Inbox view's row leaves out
    assert "return { text: 'Requested · ' + words.text, failed: false, action: words.action };" in (
        _function(script, "launchLine")
    )
    _in_order(
        _function(script, "launchWords"),
        "if (!item) return null;",
        "if (item.state === 'claimed') return said('claimed by ' + item.claimedBy);",
        "text: 'pending'",
    )
    page = _static_file("index.html")
    assert ".app-stance" not in page and ".app-disclosure" not in page
    assert ".app-request .fb-menu { left: auto; right: 0; }" in page
    assert ".app-company__actions .app-request .fb-menu" not in page
    assert ".app-request__error { margin: var(--space-2) 0 0; color: var(--caution); }" in page


def test_the_guidance_table_reads_each_record_s_call_state_and_currency() -> None:
    """The guidance table the Research tab's Appendix A draws (18.4): each record's call, its state
    and the overrides citing it as the record brings them, its range and midpoint in its own
    currency, the company's where it names none (spec 2026-11-15 9.5)."""
    script = _static_file("app.js")
    table = _function(script, "guidanceTable")
    for text in (
        "'call ', when(g.asOf), ' · ', g.state",
        # each record's money in its own currency, the company's where it names none (spec
        # 2026-11-15 9.5)
        "guidedRange(g, g.currency || code)",
        "'midpoint ' + guided(g.midpoint, g.metric, g.currency || code)",
        "g.citedBy.length ? h('span', { className: 'caption app-line' },",
        "'cited by override ' + g.citedBy.join(', ')",
    ):
        assert text in table, text


def test_details_and_its_research_read_left_the_drawer() -> None:
    """Details and its research read left the drawer (the company page's design, 11); Add a note
    moved to the Notes control (11.1), which ``test_notes_control.py`` tests. The server's research
    read stays (B-218 reads it); the address of a report on the Research tab (researchHref) is no
    read."""
    script = _static_file("app.js")
    for gone in ("detailsOpen", "readResearch", "toggleDetails", "'/research')"):
        assert gone not in script, gone


def test_the_secondary_path_lists_its_parts_or_drivers() -> None:
    """Spec 18.3, the secondary valuation "with its parts, value and date", as the Research tab's
    Appendix A draws it: on the parts form each part's name, its value and its note; on the
    drivers form the drivers in words, the years, the growth and margin lists as percentages, the
    tax rate, sales-to-capital and the terminal growth."""
    script = _static_file("app.js")
    path = _function(script, "secondaryPath")
    _in_order(
        path,
        "if (s.form === 'parts') {",
        "s.parts.map(function (p, i) {",
        "h('span', { className: 'body' }, p.name)",
        "h('span', { className: 'figure-sm' }, whole(p.value, code))",
        "p.note ? h('p', { className: 'caption app-muted' }, p.note) : null",
        "var d = s.drivers;",
        "['Years', plain(d.years), true],",
        "['Revenue growth', percents(d.revenueGrowth), true],",
        "['Operating margin', percents(d.operatingMargin), true],",
        "['Tax rate', F.formatPercent(d.taxRate), true],",
        "['Sales to capital', times(d.salesToCapital), true],",
        "['Terminal growth', F.formatPercent(d.terminalGrowth), true]",
    )
    percents = _function(script, "percents")
    assert "return list.map(function (v) { return F.formatPercent(v); }).join(', ');" in percents


def test_a_refused_row_draws_its_secondarys_band() -> None:
    """The ruling of 2026-11-07 on spec 18.1 and 18.2: a refused row whose secondary valuation
    counts on the latest snapshot, and whose review has no value there, shows the secondary's
    value in the screen's Reviewed column, so its drawer draws the secondary's band against the
    price, its head the word and price ÷ value over the secondary valuation at today's price
    (plan 4), and its levels under it in the refusal's place (the company page's design, 11). A
    refused row with a valued review draws the review's band instead (the ruling of 2026-11-08);
    a refused row with neither has its refusal alone; the valued row's meter is the review's where
    its review counts and has a value, else the mechanical one (plan 3). The meter is the drawer's
    own part, which the company page's Overview draws too; ``tests/web/test_drawer_form.py`` reads
    the drawer's band."""
    script = _static_file("app.js")
    banded = _function(script, "isBanded")
    assert "var s = body.secondary;" in banded
    assert "var v = body.review;" in banded
    # a review with a value leads; the secondary valuation needs its levels and a price; one
    # that holds the row (spec 2026-11-23 held reviewed value, 5.9) bands a valued row too
    assert (
        "if ((v && v.value != null) || !s || !s.levels || r.price == null) return false;"
        " return s.held ? true : !isValued(r) && !!r.refusal;"
    ) in " ".join(banded.split())
    meter = _function(script, "meter")
    _in_order(
        meter,
        "if (isValued(r)) {",
        "if (isBanded(body)) {",  # a held secondary valuation on a row the route values
        "if (isReviewBanded(body)) {",
        "if (!isBanded(body)) return null;",
    )
    band = meter[meter.index("if (!isBanded(body)) return null;") :]
    _in_order(
        band,
        "low: secondary.levels.fairLow, high: secondary.levels.fairHigh, price: r.price,",
        "fairValue: secondary.valuePerShare, buyLevel: secondary.levels.buy,",
        "trimLevel: secondary.levels.trim, designation: secondary.designation, showScale: false,",
        "gap: gapText(secondary.priceToValue, body.designationEdges, 'the secondary valuation'),",
    )
    assert "reviewedValue" not in band
    assert "caption:" not in band


def test_a_refused_row_with_a_valued_review_draws_the_reviews_band() -> None:
    """The ruling of 2026-11-08 on spec 18.1 and 18.2: where the route refused and the review on
    the latest snapshot has a value and its levels, the row's Reviewed cell shows that value, so
    the drawer's meter draws the review's band against the price:
    its levels and value, the reviewed marker on the value itself, the meter's head the word and
    price ÷ value over the reviewed value at today's price, which the detail carries, and its
    caption "reviewed" and the value (plan 4). Its levels stand under it, in the refusal's place
    (the company page's design, 11)."""
    script = _static_file("app.js")
    reviewed = _function(script, "isReviewBanded")
    assert "var v = body.review;" in reviewed
    assert (
        "return !isValued(r) && !!r.refusal && !!v && v.value != null && !!v.levels &&"
        " r.price != null;"
    ) in " ".join(reviewed.split())
    meter = _function(script, "meter")
    band = meter[meter.index("if (isReviewBanded(body)) {") : meter.index("if (!isBanded(body))")]
    _in_order(
        band,
        "low: review.levels.fairLow, high: review.levels.fairHigh, price: r.price,",
        "fairValue: review.value, buyLevel: review.levels.buy, trimLevel: review.levels.trim,",
        "designation: review.designation, reviewedValue: review.value, showScale: false,",
        "gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value'),",
        "hero: hero",
    )
    assert "caption:" not in band
    bundle = _function(_component_file("bundle.js"), "BandMeter")
    assert "reviewed == null ? null : 'reviewed ' + money(reviewed)" in bundle


def test_a_valued_row_with_a_counting_review_draws_the_reviews_band() -> None:
    """Spec 2026-11-06 Tier 2, 18.1 and 18.2, plan 3 (the founder, 2026-11-08: the levels should
    follow the agent's valuation): where the route values the row and the review on the latest
    snapshot has a value and its levels, the meter draws the review's band, value and word at
    today's price, its head the word and price ÷ value over the reviewed value, its caption the
    mechanical value in words ("mechanical $342", plan 4); the reviewed second marker is no longer
    drawn on a valued row. Without such a review the meter is the mechanical band as before. The
    levels named under the meter are the ones it draws (``levelRows``, read in
    ``tests/web/test_company_overview.py``). The company page's Overview draws the same meter."""
    script = _static_file("app.js")
    reviewed = _function(script, "isReviewed")
    assert "var v = body.review;" in reviewed
    assert "return isValued(body.result) && !!v && v.value != null && !!v.levels;" in " ".join(
        reviewed.split()
    )
    meter = _function(script, "meter")
    valued = meter[meter.index("if (isValued(r)) {") : meter.index("if (isReviewBanded(body)) {")]
    _in_order(
        valued,
        "if (isReviewed(body)) {",
        "low: review.levels.fairLow, high: review.levels.fairHigh, price: r.price,",
        "fairValue: review.value, buyLevel: review.levels.buy, trimLevel: review.levels.trim,",
        "designation: review.designation, showScale: false,",
        "gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value'),",
        "caption: 'mechanical ' + F.formatMoney(r.value), hero: hero",
        "low: r.levels.fair_low, high: r.levels.fair_high, price: r.price, fairValue: r.value,",
        "buyLevel: r.levels.buy, trimLevel: r.levels.trim, designation: r.designation,",
        "gap: gapText(r.price_to_value, body.designationEdges, 'the mechanical value'), hero: hero",
    )
    assert "reviewedValue" not in valued
    # the Overview draws the drawer's meter, so its band is the review's too
    assert "P.meter(d, false)" in _function(_static_file("company_overview.js"), "value")


def test_the_meter_says_the_ratio_and_the_values_name_once() -> None:
    """Spec 18.2 item 2 (plan 4): the head says price ÷ value and the value's name in one form;
    the caption says only what the head does not."""
    script = _code(_static_file("app.js"))
    meter = _function(script, "meter")
    assert "gap: gapText(review.priceToValue, body.designationEdges, 'the reviewed value')" in meter
    assert "gap: gapText(r.price_to_value, body.designationEdges, 'the mechanical value')" in meter
    assert (
        "gap: gapText(secondary.priceToValue, body.designationEdges, 'the secondary valuation')"
        in meter
    )
    assert "caption: 'mechanical ' + F.formatMoney(r.value)" in meter
    # the reviewed band's, and the held secondary valuation's on a row the route values (spec
    # 2026-11-23 held reviewed value, 5.9); the other three branches pass none
    assert meter.count("caption:") == 2
    gap = _function(script, "gapText")
    assert "ratioFigure(ratio, edges) + ' × ' + of" in gap
    assert "mechanicalCaption" not in script and "secondaryCaption" not in script


def test_the_drawer_is_read_again_when_a_run_ends() -> None:
    """A run may follow the drawer's company's review or drop an override (method 14.6): when a
    run ends, the drawer's company is read again in place, as the report page is (controls.js's
    followRuns)."""
    _in_order(
        _function(_static_file("controls.js"), "followRuns"), "P.reload(true);", "P.reloadDrawer();"
    )
    script = _static_file("app.js")
    assert "reloadDetail: reloadDetail, reloadDrawer: reloadDrawer," in script
    drawer = _function(script, "reloadDrawer")
    _in_order(
        drawer,
        "var d = state.drawer;",
        "if (!d) return;",
        "reloadDetail(d.symbol);",
    )


def test_an_applied_override_outside_a_valued_review_says_so() -> None:
    """Spec 18.3: an applied override with no effect to show (a review that refused) reads a
    caption in its Result row, never an empty figure: a `// fairband:` patch,
    ``OverrideRecord.resultNote``, which the Research tab's Appendix A passes
    (``test_the_appendixes_are_drawn_from_the_records``)."""
    bundle = _component_file("bundle.js")
    override = _function(bundle, "OverrideRecord")
    assert "// fairband: an applied override with no effect to show" in override
    assert "(spec 2026-11-06 Tier 2, 18.3)" in override
    _in_order(
        override,
        "h('dt', { className: 'label' }, 'Result'),",
        "p.effect == null && p.resultNote",
        "? h('dd', { className: 'caption fb-rec__gloss' }, p.resultNote)",
        "h('b', { className: 'fb-rec__effect' }, signedMoney(p.effect)), ' per share',",
    )
    declarations = _component_file("index.d.ts")
    props = re.search(
        r"export interface OverrideRecordProps \{\n(.*?)\n\}", declarations, re.DOTALL
    )
    assert props is not None and "resultNote?: string;" in props.group(1)


def test_the_request_menu_shows_the_open_item_refusal(client: TestClient) -> None:
    """Request research on a company whose item is already open posts nothing new: the server
    refuses the second post 409, its sentence shows under the button as it arrives, and the
    detail is read again so the open item's line follows. The menu: the two modes, a radio each,
    the note line of at most 200 characters, and Post, sent as the owner with the request header
    every page write carries. The drawer and the company page each keep their own request, so the
    drawer on one company never resets the company page's on another."""
    script = _static_file("app.js")
    assert "var REQUEST_MODES = ['valuation review', 'full report'];" in script
    menu = _function(script, "RequestMenu")
    for text in (
        "className: 'fb-menu fb-menu--filters app-request__menu'",
        "REQUEST_MODES.map(function (mode) {",
        "type: 'radio'",
        "maxLength: 200",
        "'Post')",
        (
            "onSubmit: function (event) {"
            " event.preventDefault(); postRequest(ask, redraw, after, ready); }"
        ),
    ):
        assert text in menu, text
    post = _function(script, "postRequest")
    assert (
        "api.post('/api/inbox', { symbol: ask.symbol, mode: ask.mode, note: ask.note.trim() })"
        in post
    )
    _in_order(
        post,
        "if (!r.ok) throw new Error(r.body && r.body.detail ? String(r.body.detail)",
        ".catch(function (err) { ask.error = err.message; })",
        "ask.open = false;",
        "after();",
    )
    # the menu closes on a press or focus outside its control and on Escape, which hands focus
    # back to the button, after the drawer's own Escape has seen a menu open and waited; its
    # listeners last as long as the menu
    _in_order(
        menu,
        "if (!(event.target instanceof Element) || control.contains(event.target)) return;",
        "if (event.key !== 'Escape') return;",
        "control.querySelector(':scope > .fb-btn').focus();",
        "document.addEventListener('pointerdown', outside);",
        "document.addEventListener('focusin', outside);",
        "document.addEventListener('keydown', escape);",
        "return function () {",
        "document.removeEventListener('pointerdown', outside);",
        "document.removeEventListener('focusin', outside);",
        "document.removeEventListener('keydown', escape);",
    )
    assert "closeRequestOutside" not in script
    # the server's side: one open item for a company, the second post refused
    body = {"symbol": "AAPL", "mode": "full report", "note": "the first look"}
    first = client.post("/api/inbox", json=body, headers=HEADER)
    assert first.status_code == 201, first.text
    second = client.post("/api/inbox", json=body | {"mode": "valuation review"}, headers=HEADER)
    assert (second.status_code, second.json()) == (409, {"detail": "an item for AAPL is open"})
    assert [i["id"] for i in client.get("/api/inbox").json()["items"]] == [first.json()["id"]]
    assert client.get("/api/companies/AAPL").json()["item"]["id"] == first.json()["id"]


def test_the_request_menu_asks_for_the_request_in_the_owners_words() -> None:
    """Spec 2026-11-06 Tier 2, 8 (plan 4): the note is the request in the requester's own words,
    one line, and the menu's note line asks for it so."""
    menu = _function(_code(_static_file("app.js")), "RequestMenu")
    assert "placeholder: 'The request in your words, one line'" in menu


def test_the_meter_takes_a_reviewed_value() -> None:
    """Spec 2026-11-06 Tier 2, 18.2, a `// fairband:` patch: BandMeter's ``reviewedValue`` is a
    second marker on the track, in ink with the price marker's surface ring and no cap, placed as
    the price is, pinned at an end beyond the scale (spec 2026-11-23 refresh experience, 4.7);
    the caption keeps the caller's sentence and adds "reviewed $283.00". No word is derived from
    it: the head's word stays the caller's designation. Plan 3: the patch stays in the bundle for
    the caller that passes it, the refused row's band from its review; a valued row's meter draws
    the review's band itself and passes none."""
    meter = _function(_static_file("app.js"), "meter")
    assert meter.count("reviewedValue") == 1
    refused = meter[meter.index("if (isReviewBanded(body)) {") : meter.index("if (!isBanded(")]
    assert "designation: review.designation, reviewedValue: review.value," in refused
    bundle = _component_file("bundle.js")
    meter = _function(bundle, "BandMeter")
    assert "// fairband: the reviewed value, a second marker" in meter
    assert "(spec 2026-11-06 Tier 2, 18.2)" in meter
    _in_order(
        meter,
        "var reviewed = p.reviewedValue == null ? null : Number(p.reviewedValue);",
        "var caption = [p.caption, reviewed == null ? null : 'reviewed ' + money(reviewed)]",
        "className: cx('fb-band__price-mark', pinned && 'fb-band__price-mark--pinned'),",
        "reviewed == null ? null : h('div', {",
        "className: 'fb-band__reviewed-mark',",
        "style: { left: place(reviewed) },",
        "title: 'Reviewed value ' + money(reviewed)",
        # the caption's title is spec 2026-11-19 7.5's (tests/web/test_warning_mark.py)
        "caption ? h('div', {",
        "className: 'fb-band__caption caption', title: p.captionTitle || null",
        "}, caption) : null",
    )
    assert ".filter(Boolean).join(' · ');" in meter
    assert "var word = DESIGNATION[p.designation];" in meter  # the caller's word, as before
    css = _component_file("bundle.css")
    patch = css[css.index("/* fairband: the reviewed value's marker") :]
    assert "(spec 2026-11-06 Tier 2, 18.2)" in patch[: patch.index("*/")]
    rule = _rule(css, ".fb-band__reviewed-mark {")
    for text in (
        "background: var(--ink);",
        "box-shadow: 0 0 0 2px var(--surface-raised);",
        "top: -4px;",
        "bottom: -4px;",
    ):
        assert text in rule, text
    assert "radius-pill" not in rule  # the pill cap is the price's
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface BandMeterProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    assert "reviewedValue?: number | null;" in props.group(1)
    assert "(spec 2026-11-06 Tier 2, 18.2)" in props.group(1)


def test_the_bundle_links_a_button_and_reads_every_override_state() -> None:
    """Spec 2026-11-06 Tier 2, 18.2 and 18.3, `// fairband:` patches: a Button given ``href`` is a
    link in the button's look (Company page goes to the company page, and Button.md keeps a link
    a link); ReportReader draws its cites line only when the caller passes cites; OverrideRecord
    knows the store's two other states, an input off the row's route, refused, and a dropped
    override, in a neutral tone of its own, never drawn as applied."""
    bundle = _component_file("bundle.js")
    button = _function(bundle, "Button")
    assert "// fairband: given href, the button is a link" in button
    assert "if (p.href) {" in button
    assert (
        "return h('a', { className: className, href: p.href, 'aria-label': p['aria-label'] },"
        in (button)
    )
    reader = _function(bundle, "ReportReader")
    assert "// fairband: the cites line only when the caller passes cites" in reader
    assert "p.cites ? h('p', { className: 'fb-report__cites caption' }," in reader
    states = bundle[bundle.index("var OVERRIDE_STATES = {") :]
    states = states[: states.index("};")]
    assert "// fairband: the store's two other states (spec 2026-11-06 Tier 2, 18.3)" in states
    assert "'refused-route': { word: 'refused · not on the route', tone: 'refused' }," in states
    assert "'dropped': { word: 'dropped', tone: 'dropped' }" in states
    css = _component_file("bundle.css")
    assert "a.fb-btn { text-decoration: none; }" in css
    assert ".fb-rec--dropped .fb-rec__head { background: var(--surface-sunken); }" in css
    assert ".fb-rec__state--dropped { color: var(--ink-faint); }" in css
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ButtonProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None and "href?: string;" in props.group(1)
    union = re.search(r"export type OverrideState =(.*?);", declarations, re.DOTALL)
    assert union is not None
    assert "| 'refused-route'" in union.group(1) and "| 'dropped'" in union.group(1)


def test_a_report_s_old_address_opens_the_research_tab() -> None:
    """The Research tab's design, 7.1 and 9: the report page left, its panel, its script and its
    view; its addresses, #report/<symbol> and #report/<symbol>/<id>, which a link or a bookmark
    may still name, open the company page's Research tab on the same report, the hash replaced
    by the tab's; without a symbol it is the Screen (``tests/web/test_company_load.py`` runs
    them). fromHash alone sends them there: no script opens a report by another way. No view,
    panel, rule or script names the report page."""
    js = _static_file("controls.js")
    views = re.search(r"\n  var VIEWS = \[(.*?)\];", js, re.DOTALL)
    assert views is not None and "report" not in re.findall(r"'(\w+)'", views.group(1))
    _in_order(
        _function(js, "fromHash"),
        "var parts = location.hash.slice(1).split('/');",
        "if (parts[0] === 'report') show('company', parts[1], 'research', parts[2]);",
        "else show(parts[0], parts[1], parts[2], parts[3]);",
    )
    for gone in ("keepReport", "reportPath", "P.report ", "P.report.", "onShow.report"):
        assert gone not in js, gone
    for script in resources.files("fairband.web").joinpath("static").iterdir():
        if script.name.endswith(".js"):
            assert "openReport" not in script.read_text(encoding="utf-8"), script.name
    assert "state.tab === 'report'" not in js and "show('report'" not in js
    html = _static_file("index.html")
    assert 'id="report"' not in html and "#report" not in html
    assert "report.js" not in html
    assert not resources.files("fairband.web").joinpath("static", "report.js").is_file()
    assert re.search(r"\.app-report[ ,.{:]", html) is None  # the page's root class left too


def test_the_report_s_parts_after_its_sections_are_pinned() -> None:
    """Spec 13.1 and 18.4: what the Research tab draws in its closed parts (report_parts.js), in
    this order: the references, each cited number's source by its number with the ref in its
    title; Appendix A with the bridge; Appendix B. Download .md fetches the report's Markdown and
    saves it as a file named for the company and the revision, a refusal its sentence."""
    parts = _code(_static_file("report_parts.js"))
    _in_order(parts, "'References')", "'Appendix A')", "h(F.ValueBridge, {", "'Appendix B')")
    refs = _function(parts, "references")
    for text in ("h('ol', {", "title: e.ref", "'[' + e.n + ']'", "e.source", "'No references.'"):
        assert text in refs, text
    download = _function(parts, "download")
    _in_order(
        download,
        "fetch('/api/reports/' + report.id + '/markdown')",
        "URL.createObjectURL(blob)",
        "link.download = report.symbol + '-revision-' + report.revision + '.md';",
        "link.click();",
        "failed('The Markdown did not download: ' + err.message + '.');",
    )


def test_the_appendixes_are_drawn_from_the_records() -> None:
    """Spec 13.1 and 18.4: Appendix A as the server generates it, drawn with app.js's parts
    (window.FairbandPage) rather than copies of them: the snapshot line; the inputs table; the
    bridge, each line under its input's label, when the review has a value,
    else its refusal; the overrides inside the review, each a record, read-only; the secondary
    valuation's figures, its drivers or parts and its projection; the guidance on file; the checks
    that ran; the versions; the classifier's evidence. Appendix B, a definition list. The owner
    neither adds nor drops an override on the page (spec 3). The Research tab draws them in its
    closed parts (report_parts.js)."""
    script = _code(_static_file("report_parts.js"))
    a = _function(script, "appendixA")
    _in_order(
        a,
        "part('Snapshot',",
        "P.inputsTable(a.inputs.map(input))",
        "part('Bridge', bridge(a))",
        "part('Overrides',",
        "part('Secondary valuation', secondary(a))",
        "part('Guidance on file',",
        "P.guidanceTable(a.guidance, a.snapshot.currency)",
        "part('Checks that ran',",
        "part('Versions', versions(a.versions))",
        "part('Classifier evidence', P.phaseEvidence(classifier(a.classifier)))",
    )
    adapted = _function(script, "input")
    for text in (
        "estimate_method: i.estimateMethod,",
        "source: i.source, as_of: i.asOf, observed_at: i.observedAt, entered_at: i.enteredAt",
        # a date input's note, the next earnings date as an ISO day, in words, as the export
        # writes it (spec 2026-11-15 7); the inputs table keeps a note as it is
        r"var day = i.unit === 'date' && /^\d{4}-\d{2}-\d{2}$/.test(String(i.note));",
        "note: day ? F.formatDate(i.note) : i.note,",
    ):
        assert text in adapted, text
    assert "formatDate" not in _function(_code(_static_file("app.js")), "inputsTable")
    bridge = _function(script, "bridge")
    # without a review: the mechanical value is the value, unless the snapshot refused and has none
    _in_order(
        bridge,
        "if (!b) {",
        "return none(a.snapshot.value == null ? 'No review.'",
        ": 'No review: the value is the mechanical one.');",
        "if (b.reviewedValue == null)",
        "h(F.ValueBridge, {",
        "mechanical: b.mechanicalValue, reviewed: b.reviewedValue, hero: false,",
        "tag: line.label,",
        "from: P.inputFigure(line.old, o.unit), to: P.inputFigure(line.new, o.unit),",
        "principal: o.principal, actor: o.actor, reason: o.reason",
    )
    records = _function(script, "overrides")
    for text in (
        "h(F.OverrideRecord, {",
        "state: 'applied',",
        (
            "var effect = line && line.delta != null && b.reviewedValue != null ? line.delta"
            " : undefined;"
        ),
        "resultNote: effect === undefined ? (line && line.refusal) || NO_EFFECT : undefined",
    ):
        assert text in records, text
    for gone in ("Drop", "onClick", "Button"):
        assert gone not in records, gone
    # the page's code sends no override and no drop, the Research tab's nor the screen's; the
    # screen's one DELETE is the moat box's return to the file's class (spec 2026-11-19 8.8)
    for name in ("company_research.js", "company_research_records.js", "report_parts.js", "app.js"):
        page = _static_file(name)
        if name == "app.js":
            page = page.replace("api.del(moatPath(box.symbol))", "", 1)
        assert "/overrides" not in page and "api.del" not in page and ".del(" not in page, name
    secondary = _function(script, "secondary")
    _in_order(
        secondary,
        # the server's sentence as it arrives, never rewritten
        "if (!s) return none(a.noSecondary || 'None.');",
        "P.pairs(P.secondaryRows(s).concat(",
        "P.secondaryPath(s, code)",
        "s.form === 'drivers' ? projection(s, code) : partsYears(s, code)",
    )
    assert "sentence(" not in script and "toUpperCase()" not in script
    assert "P.figuresTable([" in _function(script, "projection")
    assert "P.figuresTable([" in _function(script, "partsYears")
    b = _function(script, "appendixB")
    assert "h('dl', { className: 'app-report__glossary' }" in b and "'No terms used.'" in b
    app = _static_file("app.js")
    exposed = app[app.index("window.FairbandPage = {") :]
    exposed = exposed[: exposed.index("};")]
    for name in (
        "meter: meter",
        "inputsTable: inputsTable",
        "figuresTable: figuresTable",
        "inputFigure: inputFigure",
        "secondaryRows: secondaryRows",
        "secondaryPath: secondaryPath",
        "guidanceTable: guidanceTable",
        "phaseEvidence: phaseEvidence",
        "pairs: pairs",
        "when: when",
        "whole: whole",
        "plain: plain",
        "footnotes: footnotes",
        "asking: asking",
        "requestResearch: requestResearch",
    ):
        assert name in exposed, name


def test_request_research_shows_with_a_report_too() -> None:
    """Spec 18.2 item 4 (plan 4): Request research with its menu and the open item's line on a
    company with a report, after Company page in the drawer (the company page's design, 11), as on
    a company without one; the company page has it in its head on every tab
    (``tests/web/test_company_page.py``)."""
    sections = _function(_code(_static_file("app.js")), "sections")
    assert "requestResearch(ask, body.item, render, reread(r.symbol), body.launchReady)" in (
        sections
    )
    assert "report" not in sections  # drawn whether the company has a report or not


def test_the_meter_and_the_bridge_take_figure_under_a_headline_figure() -> None:
    """The brand book and CompanyReport.md: a page's one figure-lg is its headline. The meter's
    price and the bridge's reviewed sum take figure under one, by a `// fairband:` prop,
    ``hero: false``; elsewhere they keep figure-lg."""
    bundle = _component_file("bundle.js")
    meter = _function(bundle, "BandMeter")
    assert "// fairband: under a page's one headline figure, `hero: false`" in meter
    assert (
        "h('span', { className: 'fb-band__price ' + (p.hero === false ? 'figure' : 'figure-lg') },"
        in meter
    )
    bridge = _function(bundle, "ValueBridge")
    assert "// fairband: under a page's one headline figure, `hero: false`" in bridge
    assert "className: 'fb-num ' + (p.hero === false ? 'figure' : 'figure-lg')" in bridge
    declarations = _component_file("index.d.ts")
    for name in ("BandMeterProps", "ValueBridgeProps"):
        props = re.search(rf"export interface {name} \{{\n(.*?)\n\}}", declarations, re.DOTALL)
        assert props is not None and "hero?: boolean;" in props.group(1), name
    meter = _function(_static_file("app.js"), "meter")
    # each of the four bands, the review's on a valued row, the mechanical, the review's on a
    # refused row and the secondary's; the drawer passes none: its meter keeps figure-lg
    assert meter.count("hero: hero") == 5  # one for each of the meter's five branches


def test_the_reader_numbers_its_footnotes() -> None:
    """Spec 13.1: a cite shows as its text followed by its footnote number; ReportReader keeps the
    dotted underline and the ref in the title and adds the number as a superscript, from the
    caller's ``footnotes`` (ref → n), a `// fairband:` patch. The Research tab numbers its cites
    by the report's references (``footnotes``)."""
    bundle = _component_file("bundle.js")
    reader = _function(bundle, "ReportReader")
    assert "// fairband: a cited number keeps its dotted underline" in reader
    assert "(spec 2026-11-06 Tier 2, 13.1 and 18.4)" in reader
    _in_order(reader, "var footnotes = p.footnotes || {};", "blocks(s.parts, footnotes)")
    _in_order(
        _function(bundle, "cited"),
        "var n = own(footnotes, String(part.ref).trim());",
        "h(Cite, { source: part.ref }, part.cite),",
        "n == null ? null : h('sup', { className: 'fb-cite__n' }, '[' + n + ']'));",
    )
    assert "return Object.prototype.hasOwnProperty.call(map, key) ? map[key] : null;" in (
        _function(bundle, "own")
    )
    helper = bundle[: bundle.index("  function own(")]
    helper = helper[helper.rindex("// fairband:") :]
    assert "(spec 2026-11-06 Tier 2, 13.1)" in helper
    css = _component_file("bundle.css")
    patch = css[css.index("/* fairband: a cited number's footnote number") :]
    assert "(spec 2026-11-06 Tier 2, 13.1 and 18.4)" in patch[: patch.index("*/")]
    rule = _rule(css, ".fb-cite__n {")
    assert "color: var(--ink-faint);" in rule and "line-height: 0;" in rule
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ReportReaderProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None and "footnotes?: Record<string, number>;" in props.group(1)
    app = _static_file("app.js")
    marks = _function(app, "footnotes")
    assert "(references || []).forEach(function (e) { marks[e.ref] = e.n; });" in marks
    assert "var footnotes = P.footnotes(report.references);" in (
        _function(_static_file("company_research.js"), "section")
    )


def test_the_line_under_the_title_is_in_the_reader_s_words() -> None:
    """Spec 2026-11-15 7, a `// fairband:` patch: ReportReader's line under the title says what the
    report rests on, the data's date, the price's ("priced that day" where it is the same day,
    none without one), the end of the validity window and the full report a valuation review
    reuses, each date the bundle's ``DateText``, joined by `·`, and names no record's id;
    ``index.d.ts`` declares the four dates with a `fairband:` note. A caller that passes no cites
    draws no line. ``tests/web/test_report_reader.py`` draws the line."""
    bundle = _component_file("bundle.js")
    reader = _function(bundle, "ReportReader")
    patch = reader[reader.index("// fairband: the line under the title says what the report") :]
    patch = patch[: patch.index("'On the data of '")]
    assert "(spec 2026-11-15 7)" in patch
    _in_order(
        reader,
        "p.cites ? h('p', { className: 'fb-report__cites caption' },",
        "'On the data of ', h(DateText, { value: cites.dataDate }),",
        "cites.priceDate == null ? null",
        ": cites.priceDate === cites.dataDate ? ' · priced that day'",
        ": h(React.Fragment, null, ' · priced ', h(DateText, { value: cites.priceDate })),",
        "cites.validUntil == null ? null : h(React.Fragment, null, ' · valid until ',",
        "h(DateText, { value: cites.validUntil })),",
        "cites.reusesFullReportOf ? h(React.Fragment, null, ' · reuses the full report of ',",
        "h(DateText, { value: cites.reusesFullReportOf })) : null) : null,",
    )
    code = _code(reader)
    for gone in ("'cites snapshot '", "cites.snapshot", "cites.review", "cites.thesis"):
        assert gone not in code, gone
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ReportReaderProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    cites = props.group(1)[props.group(1).index("  cites?: {") :]
    cites = cites[: cites.index("\n  };")]
    for field in (
        "dataDate?: string;",
        "priceDate?: string | null;",
        "validUntil?: string | null;",
        "reusesFullReportOf?: string;",
    ):
        assert f"    {field}" in cites, field
    for gone in ("snapshot?:", "review?:", "thesis?:"):
        assert gone not in cites, gone
    note = props.group(1)[: props.group(1).index("  cites?: {")]
    note = note[note.rindex("/**") :]
    assert "fairband:" in note and "(spec 2026-11-15 7)" in note


def test_the_reader_renders_the_text_as_blocks() -> None:
    """Spec 13.1 "The text's shape" and 18.4: ReportReader renders each section's parts as the
    agent wrote them, through ``blocks``, a `// fairband:` patch naming 13.1: paragraphs, bullet
    and numbered lists, a table with a header row in a scroller, bold in ink; the cites inline in
    any of them. ``index.d.ts`` notes the shape on the part; ``tests/web/test_reader_blocks.py``
    renders it. ``blocks`` reads the parts with ``readBlocks`` and draws each block with
    ``drawBlock``, the two steps the bundle exports as ``reportText`` (spec 2026-11-17 research
    tab, 9), a `// fairband:` patch that ``index.d.ts`` declares."""
    bundle = _component_file("bundle.js")
    reader = _function(bundle, "ReportReader")
    assert "blocks(s.parts, footnotes)" in reader
    assert "fb-report__prose" not in reader
    assert (
        "return readBlocks(parts).map(function (b, k) { return drawBlock(b, footnotes, k); });"
    ) in _function(bundle, "blocks")
    draw = _function(bundle, "drawBlock")
    patch = bundle[: bundle.index("  function readBlocks(")]
    patch = patch[patch.rindex("  // fairband: the section's text as blocks") :]
    assert "(spec 2026-11-06 Tier 2, 13.1 and 18.4)" in patch
    assert "(spec 2026-11-17 research tab, 9)" in patch
    for text in (
        "h('p', { className: 'fb-report__prose body', key: key }",
        "className: 'fb-report__list body'",
        "h('div', { className: 'fb-report__scroll', key: key },",
        "h('table', { className: 'fb-report__table' },",
    ):
        assert text in draw, text
    exported = bundle[bundle.index("global.Fairband = {") :]
    mark = exported[: exported.index("reportText: { read: readBlocks, draw: drawBlock },")]
    assert "(spec 2026-11-17 research tab, 9)" in mark[mark.rindex("// fairband:") :]
    declarations = _component_file("index.d.ts")
    doc = declarations[: declarations.index("export declare const reportText: {")]
    doc = doc[doc.rindex("/**") :]
    assert "fairband:" in doc and "(spec 2026-11-17 research tab, 9)" in doc
    css = _component_file("bundle.css")
    comment = css[css.index("/* fairband: the text's") :]
    assert "(spec 2026-11-06 Tier 2, 13.1 and 18.4)" in comment[: comment.index("*/")]
    assert "max-width: 72ch;" in _rule(css, ".fb-report__list {")
    assert "max-width: 72ch;" in _rule(css, ".fb-report__prose {")
    # the table's scroller spans the reader's width, not the prose measure (ruling 2026-11-08)
    scroll = _rule(css, ".fb-report__scroll {")
    assert "overflow-x: auto;" in scroll and "max-width" not in scroll
    assert "border-collapse: collapse;" in _rule(css, ".fb-report__table {")
    assert "color: var(--ink);" in _rule(css, ".fb-report strong {")
    declarations = _component_file("index.d.ts")
    part = declarations[declarations.index(" * A plain string, or a number that traces") :]
    part = part[: part.index("export interface ReportSection")]
    assert "(spec 2026-11-06 Tier 2, 13.1 and 18.4)" in part
    assert "a blank line" in part and "period?: string" in part
    page = _static_file("index.html")
    block = page[page.index("@media print {") :]
    block = block[: block.index("\n  }\n")]
    assert ".fb-report__table, .fb-report__list li { break-inside: avoid; }" in block


def test_the_reader_is_set_at_sixteen_pixels() -> None:
    """Spec 18.4 (plan 4): the reader's text at 16px on a 24px line, the column 72ch at that size.
    Two classes win over the ``body`` token's 14px on 20px, which the paragraphs, the lists and
    the table's body cells each carry; the table's header row keeps its label. A cite in that
    text is the ``figure`` token's 14px over its ``figure-sm``, on the text's line; a section's
    heading 18px on a 24px line."""
    css = _component_file("bundle.css")
    assert (
        ".fb-report .fb-report__prose, .fb-report .fb-report__list,"
        " .fb-report .fb-report__table td {\n  font-size: 16px;\n  line-height: 24px;\n}"
    ) in css
    assert (
        ".fb-report .fb-report__prose .fb-cite, .fb-report .fb-report__list .fb-cite,\n"
        ".fb-report .fb-report__table td .fb-cite {\n  font-size: 14px;\n  line-height: inherit;\n}"
    ) in css
    assert ".fb-report .fb-report__section h4 {\n  font-size: 18px;\n  line-height: 24px;\n}" in css
    assert ".fb-report__prose { margin: 0; max-width: 72ch; color: var(--ink); }" in css
    comment = css[css.index("/* fairband: the reader's text at 16px") :]
    assert "(spec 2026-11-06 Tier 2, 18.4, plan 4" in comment[: comment.index("*/")]


def test_a_cite_s_number_stays_with_its_figure_in_a_table() -> None:
    """Spec 2026-11-15 9 (B-119), a `// fairband:` patch: in a report's table a cited figure and
    its number ``[n]`` do not part at a line break. ``cited`` holds the two in one span,
    ``fb-cite__pair``, where ``inlineNodes`` draws a table's cell, header or body, and the cite
    has a number; the span does not wrap. A cite outside a table, or one with no number, is drawn
    as before, the cite and its number side by side, so outside a table a cite wraps as text
    does. ``tests/web/test_report_reader.py`` draws both."""
    bundle = _component_file("bundle.js")
    cited = _function(bundle, "cited")
    patch = cited[cited.index("// fairband: in a table's cell") :]
    assert "(spec 2026-11-15 9)" in patch[: patch.index("var pair")]
    _in_order(
        cited,
        "function cited(part, footnotes, key, inCell) {",
        "var n = own(footnotes, String(part.ref).trim());",
        "var pair = inCell && n != null;",
        "return h(pair ? 'span' : React.Fragment,",
        "pair ? { className: 'fb-cite__pair', key: key } : { key: key },",
        "h(Cite, { source: part.ref }, part.cite),",
        "n == null ? null : h('sup', { className: 'fb-cite__n' }, '[' + n + ']'));",
    )
    inline = _function(bundle, "inlineNodes")
    assert "function inlineNodes(pieces, footnotes, inCell) {" in inline
    assert "put(cited(piece, footnotes, 'c' + key++, inCell));" in inline
    draw = _function(bundle, "drawBlock")
    # a table's row, its header's and its body's, draws its cells as cells, under its mark; a
    # paragraph and a list item do not
    assert (
        "// fairband: a table's cell keeps a cite with its number (spec 2026-11-15 9)\n"
        "          inlineNodes(pieces, footnotes, true));"
    ) in draw
    assert (
        "h('p', { className: 'fb-report__prose body', key: key },\n"
        "        inlineNodes(pieces, footnotes));"
    ) in draw
    assert "inlineNodes(trimPieces(item), footnotes));" in draw
    css = _component_file("bundle.css")
    comment = css[css.index("/* fairband: a cite's number stays with its figure") :]
    assert "(spec 2026-11-15 9)" in comment[: comment.index("*/")]
    assert "white-space: nowrap;" in _rule(css, ".fb-report__table .fb-cite__pair {")
    assert "white-space: nowrap;" in _rule(css, ".fb-report__table .fb-cite {")
    # no rule holds the pair outside a table
    assert _code(css).count("fb-cite__pair") == 1


def test_a_tier_label_keeps_its_near_edge_off_the_price_marker() -> None:
    """Spec 18.2 item 2 (plan 4), with spec 2026-11-23 refresh experience 4.7: the band's low
    label ends 5px before its tick and the high one starts 5px after its, so they cannot overlap,
    unless that brings a near edge within 8px of the price marker's centre line, where it stops,
    at any width, and the other label moves on with 8px between the two. The tier says where the
    price lies against the band; the span gives its tick, the price, its length and the other
    label's in ch (tests/web/test_band_meter.py reads them)."""
    css = _component_file("bundle.css")
    for rule in (
        (
            ".fb-band__tier > span.fb-band__tier-label--low,\n"
            ".fb-band__tier > span.fb-band__tier-label--high { transform: none; }"
        ),
        (
            ".fb-band__tier--under > .fb-band__tier-label--low  { left: max(calc(var(--tick) - 5px"
            " - var(--len)), calc(var(--price) + 8px)); }"
        ),
        (
            ".fb-band__tier--under > .fb-band__tier-label--high { left: max(calc(var(--tick) +"
            " 5px), calc(var(--price) + 16px + var(--other))); }"
        ),
        (
            ".fb-band__tier--in > .fb-band__tier-label--low     { left: min(calc(var(--tick) - 5px"
            " - var(--len)), calc(var(--price) - 8px - var(--len))); }"
        ),
        (
            ".fb-band__tier--in > .fb-band__tier-label--high    { left: max(calc(var(--tick) +"
            " 5px), calc(var(--price) + 8px)); }"
        ),
        (
            ".fb-band__tier--over > .fb-band__tier-label--low   { left: min(calc(var(--tick) - 5px"
            " - var(--len)), calc(var(--price) - 16px - var(--other) - var(--len))); }"
        ),
        (
            ".fb-band__tier--over > .fb-band__tier-label--high  { left: min(calc(var(--tick) +"
            " 5px), calc(var(--price) - 8px - var(--len))); }"
        ),
    ):
        assert rule in css, rule
    comment = css[css.index("/* fairband: the band's two labels") :]
    comment = " ".join(comment[: comment.index("*/")].split())
    assert "its near edge 8px off the price marker" in comment
    assert "(spec 2026-11-23 refresh experience, 4.7)" in comment
    bundle = _function(_component_file("bundle.js"), "BandMeter")
    for gone in (
        "tier-label--after",
        "tier-label--before",
        "var near",
        "tier-label--left",
        "tier-label--right",
    ):
        assert gone not in bundle and gone not in css, gone


def test_a_pinned_price_s_break_mark_is_two_strokes_of_the_ground() -> None:
    """Spec 2026-11-23 refresh experience 4.7, as the approved mockup draws it: before a price
    pinned at an end, two slanted strokes of the card's ground, 3px each and 3px apart, cross the
    track 20px in from that end, so the marker's place does not read as true. The mark stands in
    the track's clip (``fb-band__clip``), which cuts off anything past the track, so it fills the
    track's height and no more."""
    css = _component_file("bundle.css")
    comment = css[css.index("/* fairband: the break mark") :]
    assert "(spec 2026-11-23 refresh experience, 4.7)" in comment[: comment.index("*/")]
    rule = _rule(css, ".fb-band__break {")
    assert "-3px" not in rule
    for text in (
        "top: 0;",
        "bottom: 0;",
        "box-sizing: border-box;",
        "width: 9px;",
        "border-left: 3px solid var(--surface-raised);",
        "border-right: 3px solid var(--surface-raised);",
        "transform: skewX(-18deg);",
    ):
        assert text in rule, text
    assert "right: 20px;" in _rule(css, ".fb-band__break--high {")
    assert "left: 20px;" in _rule(css, ".fb-band__break--low {")
    bundle = _function(_component_file("bundle.js"), "BandMeter")
    assert "// fairband: the scale comes from the value, never from the price" in bundle
    _in_order(
        bundle,
        "className: 'fb-band__clip'",
        "pinned ? h('div', { className: 'fb-band__break fb-band__break--' + pinned }) : null",
        "className: cx('fb-band__price-mark', pinned && 'fb-band__price-mark--pinned'),",
    )


def test_the_print_stylesheet() -> None:
    """Spec 13.6: printed, the page has no header chrome, no status line, no button or menu and no
    Request research or its lines (plan 4); the page runs its full length. A panel another view
    would show is hidden already."""
    page = _static_file("index.html")
    block = page[page.index("@media print {") :]
    block = block[: block.index("\n  }\n")]
    hidden = block[: block.index("{ display: none !important; }")]
    for selector in (
        "#header",
        "#controls",
        ".fb-btn",
        ".fb-menu",
        ".app-request,",
        ".app-requested,",
        ".app-request__error",
    ):
        assert selector in hidden, selector
    for text in ("html, body, .app-page { height: auto; }", ".app-page { display: block; }"):
        assert text in block, text


def test_a_wide_table_prints_whole() -> None:
    """Spec 2026-11-15 9 (B-119), held on the Research tab (its design, 7.11): printed, an agent's
    table is not clipped at the screen's scroll box. The scroller sets no width and the table
    none, so an auto-width table takes the smaller of its content and the paper. Since a cite and
    its number never wrap, in a table dense with figures those pairs set its width, so the table
    takes the floor of the type scale and nothing below it (the controller's ruling): the cells'
    words at the ``label`` token's 12px on a 16px line, a cite at ``figure-sm``'s 12px, its own
    class's size, and its number at the ``caption``'s 11px, its screen size, with no print rule
    that sizes it (the one print rule that names it shows the tab's marks); the tab's selector
    beats the cell's type class. Nothing in print stops the cells wrapping, and a cite stays
    whole with its number by the bundle's rule, which holds in print. The table still stays on
    one page, and the screen keeps its scroller."""
    page = _static_file("index.html")
    block = page[page.index("@media print {") :]
    block = block[: block.index("\n  }\n")]
    comment = block[block.index("/* the agent's table prints whole") :]
    comment = " ".join(comment[: comment.index("*/")].split())
    assert "(spec 2026-11-15 9)" in comment
    for words in ("the floor of the type scale", "label", "figure-sm", "caption", "set its width"):
        assert words in comment, words
    for text in (
        ".fb-report__scroll { overflow: visible; }",
        ".app-research .fb-report__table td { font-size: 12px; line-height: 16px; }",
        ".app-research .fb-report__table td .fb-cite { font-size: 12px; }",
        ".fb-report__table, .fb-report__list li { break-inside: avoid; }",
    ):
        assert text in block, text
    # the reader's card (``fb-report``), which hid its overflow, is no page's now
    code = _code(block)
    assert [line.strip() for line in code.splitlines() if "fb-report__scroll" in line] == [
        ".fb-report__scroll { overflow: visible; }"
    ]
    # no width for the table
    assert [line.strip() for line in code.splitlines() if "fb-report__table" in line] == [
        ".fb-report__table, .fb-report__list li { break-inside: avoid; }",
        ".app-research .fb-report__table td { font-size: 12px; line-height: 16px; }",
        ".app-research .fb-report__table td .fb-cite { font-size: 12px; }",
    ]
    assert re.search(r"\.fb-report[ {,]", code) is None
    # no print rule sizes the cite's number: the one print rule that names it shows the Research
    # tab's marks whatever Footnote marks says (the Research tab's design, 7.11)
    assert [line.strip() for line in code.splitlines() if "fb-cite__n" in line] == [
        ".app-research:not(.app-research--marks) .fb-cite__n { display: inline; }"
    ]
    sizes = [int(px) for px in re.findall(r"font-size:\s*(\d+)px", code)]
    assert sizes and min(sizes) >= 11, sizes
    assert "white-space" not in code
    assert page.index("/static/design-system/components/bundle.css") < page.index("<style>")
    css = _component_file("bundle.css")
    assert "overflow-x: auto;" in _rule(css, ".fb-report__scroll {")
    assert "font-size: 11px;" in _rule(css, ".fb-cite__n {")
    assert "@media print" not in css
    tokens = _static_file("design-system/tokens/tokens.css")
    for token in (
        ".label { font-family: var(--font-sans); font-size: 12px; line-height: 16px;",
        ".figure-sm { font-family: var(--font-mono); font-size: 12px; line-height: 16px;",
        ".caption { font-family: var(--font-sans); font-size: 11px; line-height: 15px;",
    ):
        assert token in tokens, token


# The charts of Financial performance and health by their table and row, each titled by its row's
# name in the export (charts.row_name); buybacks and dividends, one measure, is the page's sum of
# two rows.
FINANCIAL_CHARTS = {
    "growth": ["revenue", "operating_margin", "eps"],
    "cash_flow": ["free_cash_flow", "stock_compensation_to_revenue"],
    "solvency": ["net_debt_to_ebitda", "interest_coverage"],
    "returns": ["roic"],
    "capital_allocation": ["share_count_change"],
    "quality": ["altman_z", "piotroski_f"],
}


def test_the_report_s_charts_are_titled_as_the_export_s(db_path: Path, policy: Policy) -> None:
    """Spec 18.4's table, drawn by charts.js on the Research tab. Financial performance and
    health: a group per table under its title in the export, in its order (charts.TITLES; the
    Research tab's design, 7.9), HistoryBars titled by their rows' names there (charts.row_name):
    revenue, the operating margin as a percentage, the EPS; free cash flow, stock compensation to
    revenue; net debt to EBITDA, interest coverage; buybacks and dividends, one measure, and the
    share count's change; Altman's Z″ and Piotroski's F; and ROIC against the hurdle rate the
    returns table carries (SpreadChart). The last earnings call (spec 2026-11-15 6.5): the
    quarters table's revenue, operating margin and EPS by quarter (HistoryBars three times),
    under its title in the export (charts.QUARTERS_TITLE), each titled by its row's name there.
    Valuation: the readings the sections cite and the secondary valuation's grid
    (SensitivityGrid twice), titled as their tables are. Price and multiples: the price against
    the band (BandHistory) and the trailing and forward P/E (MultipleHistory twice), titled as
    their table and the year-end table's columns. So the page and its Markdown export never
    differ."""
    script = _code(_static_file("charts.js"))
    parts = re.findall(r"\{ table: '(\w+)', title: '([^']+)', charts: \[", script)
    assert parts == list(TITLES.items())
    with closing(connect(db_path)) as conn:
        rows = {t.name: [r.name for r in t.rows] for t in financial_tables(conn, "AAPL", policy)}
        quarters = quarters_table(conn, "AAPL")
    assert f"var QUARTERS_TITLE = '{QUARTERS_TITLE}';" in script
    quarterly = re.search(
        r"var QUARTERLY = \{ table: '(\w+)', title: QUARTERS_TITLE, by: 'quarter', charts: \[(.*?)\]"
        r" \};",
        script,
        re.DOTALL,
    )
    assert quarterly is not None and quarterly.group(1) == quarters.name
    assert re.findall(r"\{ row: '(\w+)'", quarterly.group(2)) == [r.name for r in quarters.rows]
    part = r"\{ table: '(\w+)', title: '[^']+', charts: \[(.*?)\] \}"
    blocks = re.findall(part, script, re.DOTALL)
    charted = {table: re.findall(r"\{ row: '(\w+)'", block) for table, block in blocks}
    assert charted == FINANCIAL_CHARTS
    for table, names in charted.items():
        assert set(names) <= set(rows[table]), table
    for row, _, title in re.findall(r"\{ row: '(\w+)', title: (['\"])(.+?)\2", script):
        assert title == row_name(row), row
    assert "{ rows: ['buybacks', 'dividends'], title: 'Buybacks and dividends' }" in script
    assert {"buybacks", "dividends"} <= set(rows["capital_allocation"])
    bars = _function(script, "bars")
    assert "h(F.HistoryBars, {" in bars and "format: unit === 'percent' ? F.formatPercent" in bars
    assert "h(F.SpreadChart, {" in _function(script, "spread")
    assert script.count("h(F.SensitivityGrid, {") == 2
    assert "h(F.SensitivityGrid, {" in _function(script, "reading")
    assert "title: r.title, rows: r.rowWords, cols: r.colWords," in _function(script, "reading")
    grid = _function(script, "secondaryGrid")
    assert "h(F.SensitivityGrid, {" in grid and "rows: g.rowWords," in grid
    assert f"var GRID_TITLE = '{GRID_TITLE.format('')}';" in script
    assert "h(F.BandHistory, {" in _function(script, "band")
    assert f"var BAND_TITLE = '{BAND_TITLE}';" in script
    assert "title: BAND_TITLE, subtitle: pastYear(list)" in _function(script, "band")
    assert "h(F.MultipleHistory, {" in _function(script, "multiple")
    multiples = _function(script, "multiples")
    _in_order(
        multiples,
        f"multiple('{SERIES_TITLES['pe']}', m.pe,",
        "'the last P/E of each month against its ten-year average'",
        "(m.peNote ? ' · ' + m.peNote : '')",  # the server's sentence, as it arrives
        f"multiple('{SERIES_TITLES['pe_forward']}', forward,",
        "'since ' + F.formatDate(forward.since)",
    )
    assert (
        "P.reportCharts = { groupCharts: groupCharts, quarterCharts: quarterCharts,"
        " gridCharts: gridCharts, priceCharts: priceCharts, roicPoints: roicPoints,"
        " points: points, kindsLine: kindsLine };"
    ) in " ".join(script.split())
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("company_research.js") > scripts.index("charts.js")


def test_a_missing_cell_is_a_gap() -> None:
    """Review focus 4: a cell with no value is left out of its chart's series, a gap, never a zero
    column; the cash returned is none where either line is; a year missing ROIC or the hurdle
    rate is left out; a month of the trailing P/E with no point is null, which MultipleHistory
    draws as a break in its line; a quarter with no band in force draws the price alone; a chart
    left with no point shows its title and "No data on file.", not an empty plot."""
    script = _code(_static_file("charts.js"))
    assert "filter(function (p) { return p.value != null; })" in _function(script, "points")
    assert "var series = row ? points(row, columns) : [];" in _function(script, "bars")
    assert (
        "var value = cell.value == null || paid == null ? null : -(cell.value + paid);"
        in _function(script, "returned")
    )
    # and so is a ROIC year whose cell carries a note, capital at or below zero (B-8), which
    # tests/web/test_report_charts.py runs
    assert "return p.roic != null && p.wacc != null && !p.note;" in (
        _function(script, "roicPoints")
    )
    assert "var drawn = roicPoints(rows[c.row], rows[c.hurdle]);" in _function(script, "spread")
    # with every year left out, the panel shows that sentence, not "No data on file."
    assert "if (!drawn.series.length) return look.wrap(c.title, noData(c.title, drawn.left));" in (
        _function(script, "spread")
    )
    month = _function(script, "byMonth")
    assert "value: Object.prototype.hasOwnProperty.call(last, key) ? last[key] : null" in month
    band = _function(script, "band")
    assert "fairLow: p ? p.fairLow : null, fairHigh: p ? p.fairHigh : null" in band
    for text in ("|| 0", "?? 0", ": 0)", "value || "):
        assert text not in script, text
    empty = _function(script, "noData")
    assert "h('span', { className: 'fb-c__title heading' }, title)" in empty
    assert "h(F.BasisChip, { basis: 'mechanical', compact: true })" in empty
    assert "var NO_DATA = 'No data on file.';" in script
    for name in ("bars", "spread", "band", "multiple"):
        assert "noData(" in _function(script, name), name
    bundle = _component_file("bundle.js")
    assert "if (d.value == null) { run = null; return; }" in _function(bundle, "MultipleHistory")
    history = _function(bundle, "BandHistory")
    assert "var banded = function (d) { return d.fairLow != null && d.fairHigh != null; };" in (
        history
    )
    assert "if (!banded(d)) { run = null; return; }" in history
    assert "if (banded(d)) vals.push(d.fairLow, d.fairHigh);" in history
    assert "if (value == null) return 'none';" in _function(bundle, "sensStep")


def test_the_bundle_exports_multiple_history() -> None:
    """Spec 18.4: MultipleHistory, a `// fairband:` block in BandHistory's marks and tokens: a
    line in chart-1, 2px, round joins and caps (fb-c__line), null values gaps; the average a 1px
    solid chart-context reference line labelled at its right end in ink-faint; the last value
    labelled at the line's end in ink beside the end marker and its surface-raised ring, the
    average's words and figure outside the plot at the reference line's right end, as SpreadChart
    labels its hurdle, moved clear of the last value's label so the series never crosses them;
    chart-grid solid and bare ticks, as many period labels as fit the width; the BasisChip in its
    header; the table twin behind tableView. Exported as Fairband.MultipleHistory and declared in
    index.d.ts. Nothing animates and no phase token colours it."""
    bundle = _component_file("bundle.js")
    chart = _function(bundle, "MultipleHistory")
    lead = bundle.index("// fairband: a multiple's history against its own average")
    assert "(spec 2026-11-06 Tier 2, 18.4 and 13.7)" in bundle[lead : bundle.index(chart)]
    for text in (
        "h(BasisChip, { basis: p.basis || 'mechanical', compact: true })",
        "h(Grid, { ticks: ticks, scale: Y, left: L, right: R, format: compact }),",
        "h('line', { className: 'fb-c__ref', x1: L, x2: R, y1: avg, y2: avg }),",
        "h('text', { className: 'fb-c__endlabel fb-c__endlabel--context' },",
        "h('tspan', { x: R + 12, y: named - 2 }, p.averageLabel || 'average'),",
        "h('tspan', { x: R + 12, y: named + 11 }, label(p.average))),",
        "if (avg != null && last && Math.abs(Y(last.value) - avg) < 30) {",
        "var most = Math.max(1, Math.floor((R - L) / (widest * 6.6 * 1.5 + 12)));",
        "h(XAxis, { series: series, x: X, y: B, left: L, right: R, most: most })",
        "key: k, className: 'fb-c__line fb-c__line--1',",
        "points: (r.length === 1 ? r.concat(r) : r).join(' ')",
        "h('circle', { className: 'fb-c__dot fb-c__dot--1', cx: X(end), cy: Y(last.value), r: 4.5 })",
        "h('text', { className: 'fb-c__endlabel', x: X(end) + 12, y: Y(last.value) + 4 },",
        "show: p.tableView,",
        "head: ['Period', p.title || 'Value'],",
        "rows: series.map(function (d) { return [d.period, label(d.value)]; })",
    ):
        assert text in chart, text
    for banned in ("phase-", "animat", "transition"):
        assert banned not in chart, banned
    # the shared axis takes `most`, seven absent, so the other charts' axes are as they were
    # the average's two lines stay inside the figure, its figure's baseline at most H - 2
    assert "if (named != null) named = Math.min(named, H - 13);" in chart
    assert "function labelEvery(n, most) { return Math.max(1, Math.ceil(n / (most || 7))); }" in (
        bundle
    )
    assert "var text = periodLabel(d, i, p.series.length, p.most, kept);" in bundle
    exported = bundle[bundle.index("global.Fairband = {") :]
    assert "MultipleHistory: MultipleHistory," in exported
    css = _component_file("bundle.css")
    assert ".fb-c__ref { stroke: var(--chart-context); stroke-width: 1; }" in css
    patch = css[css.index("/* fairband: MultipleHistory's average") :]
    assert "(spec 2026-11-06 Tier 2, 18.4)" in patch[: patch.index("*/")]
    assert ".fb-c__line { fill: none; stroke-width: 2; stroke-linejoin: round;" in css
    assert ".fb-c__dot { stroke: var(--surface-raised); stroke-width: 2; }" in css
    assert ".fb-c__endlabel--context { fill: var(--ink-faint); }" in css
    declarations = _component_file("index.d.ts")
    assert "export declare function MultipleHistory(props: MultipleHistoryProps): unknown;" in (
        declarations
    )
    props = re.search(
        r"export interface MultipleHistoryProps \{\n(.*?)\n\}", declarations, re.DOTALL
    )
    assert props is not None
    for field in (
        "series: MultiplePoint[];",
        "average: number;",
        "averageLabel?: string;",
        "title: string;",
        "subtitle?: string;",
        "unit?: string;",
        "basis?: Basis;",
        "tableView?: boolean;",
    ):
        assert field in props.group(1), field
    assert "value: number | null;" in declarations


def test_the_bundle_draws_what_the_report_charts_need() -> None:
    """The bundle's patches for the page's charts, each a `// fairband:` naming 18.4: BandHistory
    draws a period with no band in force with the price alone, a lone period's band half a period
    each side; HistoryBars' `inverse` swaps the diverging pair for a measure whose lower values
    are the better ones; a SensitivityGrid cell the engine valued none at has no fill;
    ReportReader takes the charts by section (above). index.d.ts says each."""
    bundle = _component_file("bundle.js")
    history = _function(bundle, "BandHistory")
    assert "// fairband: a period with no band in force" in history
    for text in (
        "var half = n < 2 ? (R - L) / 2 : (R - L) / (n - 1) / 2;",
        "if (pts.length > 1) return pts;",
        "var top = edge(r, 'fairHigh'), bottom = edge(r, 'fairLow');",
        "? 'band ' + money(cur.fairLow) + ' – ' + money(cur.fairHigh) : 'no band') : null",
    ):
        assert text in history, text
    bars = _function(bundle, "HistoryBars")
    assert "// fairband: `inverse`, a measure whose lower values are the better ones" in bars
    assert "var good = p.inverse ? d.value < 0 : d.value >= 0;" in bars
    assert "(good ? 'fb-c__bar fb-c__bar--pos' : 'fb-c__bar fb-c__bar--neg');" in bars
    assert "// fairband: a pair the engine valued none at" in _function(bundle, "sensStep")
    css = _component_file("bundle.css")
    assert ".fb-sens__cell--none { color: var(--ink-faint); }" in css
    declarations = _component_file("index.d.ts")
    for name, field in (
        ("HistoryBarsProps", "inverse?: boolean;"),
        ("BandPoint", "fairLow: number | null;"),
        ("BandPoint", "fairHigh: number | null;"),
        ("SensitivityGridProps", "cells: (number | null)[][];"),
        ("ReportReaderProps", "charts?: Record<string, unknown>;"),
    ):
        props = re.search(rf"export interface {name} \{{\n(.*?)\n\}}", declarations, re.DOTALL)
        assert props is not None and field in props.group(1), (name, field)
    script = _code(_static_file("charts.js"))
    inverse = re.findall(r"\{ row: '(\w+)', title: '[^']+', inverse: true \}", script)
    assert inverse == ["net_debt_to_ebitda", "share_count_change"]


def test_the_bundle_draws_a_bar_that_is_not_a_fiscal_year() -> None:
    """Spec 2026-11-15 6.6, a patch as `inverse` is one: a HistoryBars point's `kind` gives its
    bar a class, the trailing twelve months filled in chart-context whatever their sign, an
    estimate an outline in the colour its fill would have had, and both keep their look hovered
    (spec 4); the value stands on the last bar that is not an estimate, with a halo in the panel's
    surface where an estimate's outline runs under it; the accessible name reads `by`; the tooltip
    and the table twin read a point's `label`. Each change is marked, and index.d.ts says each
    field. What the bars draw is read in node (tests/web/test_report_charts.py)."""
    bars = _function(_component_file("bundle.js"), "HistoryBars")
    _in_order(
        bars,
        "// fairband: the value stands on the last bar that is not an estimate",
        "series.forEach(function (d, i) { if (d.kind !== 'estimate') capped = i; });",
        "// fairband: `by`, what the bars run by",
        "'aria-label': p.title + ' by ' + (p.by || 'fiscal year')",
        "// fairband: a bar that is not a fiscal year",
        "className: cx(cls, d.kind && 'fb-c__bar--' + d.kind, at === i && 'is-hovered'),",
        "// fairband: the value on `capped`, the last bar that is not an estimate",
        "capped < 0 ? null : h('text', {",
        "x: X(capped) + bw / 2,",
        "y: Y(series[capped].value) + (series[capped].value < 0 ? 14 : -7)",
        "}, fmt(series[capped].value)),",
        "// fairband: the tooltip names a point by its `label`",
        "h('span', { className: 'label' }, cur ? cur.label || cur.period : ''),",
        "// fairband: the table twin names a point by its `label`",
        "return [(d.label || d.period) + markFor(d.freshness), fmt(d.value)];",
    )
    assert "series[n - 1]" not in bars
    css = _component_file("bundle.css")
    _in_order(
        css,
        ".fb-c__bar--neg { fill: var(--chart-neg-3); }",
        "/* fairband: the trailing twelve months",
        ".fb-c__bar--trailing { fill: var(--chart-context); }",
        "/* fairband: an analysts' estimate",
        ".fb-c__bar--estimate { fill: none; stroke: var(--chart-1); stroke-width: 1.5;"
        " pointer-events: visible; }",
        ".fb-c__bar--estimate.fb-c__bar--pos { stroke: var(--chart-pos-3); }",
        ".fb-c__bar--estimate.fb-c__bar--neg { stroke: var(--chart-neg-3); }",
        ".fb-c__bar.is-hovered { fill: var(--accent-hover); }",
        ".fb-c__bar--neg.is-hovered { fill: var(--chart-neg-2); }",
        "/* fairband: hovered, an estimate stays an outline",
        ".fb-c__bar--estimate.is-hovered { fill: none; stroke-width: 2.5; }",
        ".fb-c__bar--trailing.is-hovered { fill: var(--ink-muted); }",
    )
    _in_order(
        css,
        ".fb-c__capvalue { text-anchor: middle; }",
        "/* fairband: the value above a bar has a halo in the chart panel's surface",
        ".fb-c__capvalue { paint-order: stroke; stroke: var(--surface-raised); stroke-width: 3px;"
        " stroke-linejoin: round; }",
    )
    for mark, spec in (
        ("/* fairband: the trailing twelve months", "(spec 2026-11-15 6.6)"),
        ("/* fairband: an analysts' estimate", "(spec 2026-11-15 6.6)"),
        ("/* fairband: hovered, an estimate stays an outline", "(spec 2026-11-15 4, 6.6)"),
        ("/* fairband: the value above a bar has a halo", "(spec 2026-11-15 6.6)"),
    ):
        patch = css[css.index(mark) :]
        assert spec in patch[: patch.index("*/")], mark
    declarations = _component_file("index.d.ts")
    for name, doc, field in (
        (
            "BarPoint",
            "a bar that is not a fiscal year: the trailing twelve months, or an estimate.",
            "kind?: 'trailing' | 'estimate';",
        ),
        (
            "BarPoint",
            "the period in words, for the table twin and the tooltip; the period when absent.",
            "label?: string;",
        ),
        (
            "HistoryBarsProps",
            "what the bars run by, for the accessible name; 'fiscal year' when absent.",
            "by?: string;",
        ),
    ):
        props = re.search(rf"export interface {name} \{{\n(.*?)\n\}}", declarations, re.DOTALL)
        said = f"  /** fairband: {doc} */\n  {field}"
        assert props is not None and said in props.group(1), (name, field)


def test_the_axis_always_prints_the_trailing_twelve_months_tick() -> None:
    """Spec 2026-11-15 6.5, 6.6, a patch to the shared axis: the tick of a point whose `kind` is
    `trailing`, "to date", prints as the two ends' do, and a tick within `every` slots of it is
    dropped, so no two printed ticks stand fewer bars apart than before; a series with no such
    point, every chart but a HistoryBars of a table with a trailing column, labels as before. What
    the axis prints is read in node (tests/web/test_report_charts.py)."""
    bundle = _component_file("bundle.js")
    axis = _function(bundle, "XAxis")
    _in_order(
        axis,
        '// fairband: the trailing twelve months\' tick, "to date", is always printed',
        "var kept = -1;",
        "p.series.forEach(function (d, i) { if (d.kind === 'trailing') kept = i; });",
        "var text = periodLabel(d, i, p.series.length, p.most, kept);",
    )
    label = _function(bundle, "periodLabel")
    lead = bundle.index("// fairband: `kept`, the index of the trailing twelve months' point")
    assert "(spec 2026-11-15 6.5, 6.6)" in bundle[lead : bundle.index(label)]
    _in_order(
        label,
        "function periodLabel(d, i, n, most, kept) {",
        "if (i === 0 || i === n - 1 || i === kept) return d.period;",
        "if (i % every !== 0) return '';",
        "if (n - 1 - i < every) return '';",
        "if (kept >= 0 && Math.abs(i - kept) < every) return '';\n    return d.period;",
    )
    assert _code(bundle).count("periodLabel(") == 2  # its definition and XAxis, its one caller


def test_the_charts_axes_hold_as_many_ticks_as_their_width() -> None:
    """The Research tab's design, 7.9, one patch: `ticksHeld(width, per)`, the ticks a plot's
    width holds, one to `per` px, seven at most and two at least, gives the axis its `most` in
    HistoryBars (70px a tick: the last year's and "to date", anchored at its end, side by side),
    BandHistory (64px: "Q4 2021") and SpreadChart (56px: a year), each call marked; so a chart as
    narrow as the tab's thins its ticks and one as wide as the report page drew it prints as
    before. MultipleHistory keeps its own `most`. What the axes print is read in node
    (tests/web/test_report_charts.py)."""
    bundle = _component_file("bundle.js")
    held = _function(bundle, "ticksHeld")
    lead = bundle.index("// fairband: the ticks a plot `width` px wide holds")
    assert "(spec 2026-11-17 research tab, 7.9)" in bundle[lead : bundle.index(held)]
    assert "return Math.min(7, Math.max(2, Math.floor(width / per)));" in held
    for chart, per in (("HistoryBars", 70), ("BandHistory", 64), ("SpreadChart", 56)):
        _in_order(
            _function(bundle, chart),
            "// fairband: the axis carries as many ticks as the plot's width holds",
            "(spec 2026-11-17 research tab, 7.9)",
            f"most: ticksHeld(R - L, {per})",
        )
    code = _code(bundle)
    assert code.count("ticksHeld(") == 4  # its definition and the three axes
    assert code.count("most: ticksHeld(") == 3
    assert "h(XAxis, { series: series, x: X, y: B, left: L, right: R, most: most })" in (
        _function(bundle, "MultipleHistory")
    )


def test_the_research_tab_s_reads_carry_the_request_header() -> None:
    """D11 and B-109: the server refuses the multiples history read, which may call FMP,
    without ``X-Fairband-Request: 1``, as it refuses a write; the Research tab's one read helper
    for the series sends it on every read, as the page's writes do, and its refusal stays the
    server's sentence."""
    research = _code(_static_file("company_research.js"))
    read = _function(research, "read")
    assert "return fetch(url, { headers: { 'X-Fairband-Request': '1' } }).then(" in read
    assert "return response.ok ? response.json() : refused(response);" in read
    assert research.count("fetch(") == 1  # the read; the Markdown download is report_parts.js's
    assert _code(_static_file("report_parts.js")).count("fetch(") == 1
    assert "headers: { 'Content-Type': 'application/json', 'X-Fairband-Request': '1' }," in (
        _function(_static_file("app.js"), "send")
    )


def test_each_series_lands_as_its_read_settles() -> None:
    """The multiples history may wait on FMP (13.7): each series lands in what the Research
    tab holds of its report as its own read settles and the page draws again, so the charts of
    the local reads never wait for it; a chart draws once the series it reads are in. The latest
    read wins (``tests/web/test_company_research_cards.py`` runs them)."""
    research = _code(_static_file("company_research.js"))
    reads = _function(research, "readSeries")
    assert "Promise.all([" not in reads
    for url, key in (
        ("'/financial-tables'", "tables"),
        ("'/multiples-history'", "multiples"),
        ("'/price-history?years=5'", "closes"),
        ("'/band-history'", "band"),
    ):
        assert f"settle(read(company + {url})).then(land('{key}'));" in reads, key
    _in_order(
        reads,
        "Promise.all(cited(report.references).map(function (n) {",
        "land('readings')(got.filter(function (r) {",
    )
    _in_order(
        reads,
        "if (!kept || kept.of !== report) return;",
        "next[key] = got;",
        "kept.got = next;",
        "C.redraw();",
    )
    script = _code(_static_file("charts.js"))
    price = _function(script, "priceCharts")
    _in_order(
        price,
        "var drawn = series.closes && series.band ? [band(series.closes, series.band, look)] : [];",
        "return series.multiples ? drawn.concat(multiples(series.multiples, look)) : drawn;",
    )


def test_a_refused_or_empty_series_says_why() -> None:
    """The server's sentences as they arrive: when the band's history alone did not load, the price
    is drawn alone with that read's own sentence under it, and the price history's refusal is its
    own; a trailing P/E with no point says why in the server's words when it sends them (the
    series' note, "the series could not be read", or the read's), else "No data on file."."""
    script = _code(_static_file("charts.js"))
    band = _function(script, "band")
    _in_order(
        band,
        "return look.wrap(BAND_TITLE, refused('The price history', closes.error));",
        "var marks = history.error ? [] : history.body.points;",
        "h(F.BandHistory, {",
        "history.error ? refused('The band\\'s history', history.error, 'refused') : null",
    )
    assert "history.error)" not in band.split("var marks")[0]
    multiples = _function(script, "multiples")
    assert "(m.peNote ? ' · ' + m.peNote : ''), (m.pe && m.pe.note) || m.peNote, look)," in (
        multiples
    )
    assert "}) : noData(title, why));" in _function(script, "multiple")
    assert "h('p', { className: 'caption app-muted' }, why || NO_DATA));" in (
        _function(script, "noData")
    )
    page = _static_file("index.html")
    assert ".app-charts__chart .fb-c + .app-report__error { margin-top: var(--space-2); }" in page


def test_a_short_forward_log_is_a_figure_not_a_chart() -> None:
    """Spec 13.7 and 18.4 (plan 4): fewer than five readings show the newest as a figure with the
    sentence, no line and no average; five draw the line. A log with no reading keeps "No data on
    file.", and the figure's title is the export's."""
    script = _code(_static_file("charts.js"))
    assert "var SHORT_LOG = 5;" in script
    multiples = _function(script, "multiples")
    assert "logged.length < SHORT_LOG ? look.wrap('forward', shortLog(forward)) :" in multiples
    assert "0 < logged.length && logged.length < SHORT_LOG ? look.wrap(" in multiples
    short = _function(script, "shortLog")
    assert (
        "'logged since ' + F.formatDate(forward.since) + '; a reading is added at each price refresh'"
        in short
    )
    assert "F.BasisChip" in short and "average" not in short
    title = SERIES_TITLES["pe_forward"]
    assert f"h('span', {{ className: 'fb-c__title heading' }}, '{title}')," in short
    assert "newest.value.toFixed(1) + 'x on ' + F.formatDate(newest.day)" in short


def test_the_spread_names_the_hurdle_as_the_export_does() -> None:
    """The page's SpreadChart draws ROIC against the policy's required return, which the export's
    returns table names "Hurdle rate": SpreadChart's `hurdleLabel`, a `// fairband:` patch naming
    18.4, names it in the legend, the tooltip and the table twin, "WACC" for other callers."""
    bundle = _component_file("bundle.js")
    spread = _function(bundle, "SpreadChart")
    lead = spread.index("// fairband: `hurdleLabel`")
    assert "(spec 2026-11-06 Tier 2, 18.4)" in spread[lead : spread.index("var hurdle =")]
    assert "var hurdle = p.hurdleLabel || 'WACC';" in spread
    for text in (
        "h('span', { className: 'label' }, hurdle)),",
        "hurdle + ' ' + pct(cur.wacc)",
        "head: ['Period', 'ROIC', hurdle, 'Spread'],",
    ):
        assert text in spread, text
    assert _code(spread).count("'WACC'") == 1  # the default alone
    props = re.search(
        r"export interface SpreadChartProps \{\n(.*?)\n\}", _component_file("index.d.ts"), re.DOTALL
    )
    assert props is not None and "hurdleLabel?: string;" in props.group(1)
    script = _code(_static_file("charts.js"))
    assert f"hurdleLabel: '{row_name('hurdle_rate')}'\n" in _function(script, "spread")
    assert "{ row: 'roic', title: 'ROIC', hurdle: 'hurdle_rate' }" in script


# The columns the repository's bundle adds to ScreenTable, each a row key, with its head.
EXTRA_COLUMN_HEADS = {
    "sector": "Sector",
    "industry": "Industry",
    "capBand": "Cap",
    "marketCap": "Market cap",
    "moat": "Moat",
    "impliedGrowth": "Implied growth",
    "expectedReturn": "Expected return",
    "epv": "EPV",
    "peReported": "P/E",
    "peForward": "Forward P/E",
    "high52w": "52w high",
    "low52w": "52w low",
    "change1y": "1y",
    "change3y": "3y",
    "change5y": "5y",
    "drawdown": "Drawdown",
    "refusal": "Refusal",
    "priceDate": "Price date",
    "dataDate": "Data date",
    "validUntil": "Valid until",
    "agentStance": "Stance",
    "growthRouteValue": "Growth-route value",
    "targetMargin": "Target margin",
    "impliedMargin": "Implied margin",
}


def test_bundle_has_extra_columns() -> None:
    bundle = _component_file("bundle.js")
    assert set(EXTRA_COLUMN_HEADS) <= set(EXTRA_KEYS)  # the API sends each one
    for key, head in EXTRA_COLUMN_HEADS.items():
        assert f"{{ key: '{key}', head: '{head}'," in bundle, key


def test_the_screen_has_no_clean_pe_column(client: TestClient) -> None:
    """The founder, 2026-11-22: the screen's Clean P/E column goes. Since method 1.7 the engine
    finds no one-time items, so the column held the P/E again on every row (B-268, point 1). The
    row sends no `peClean`, the table has no such column and no saved list can name one. The
    engine's own `pe_clean` stays, which a report cites from a review that set the one-time
    items."""
    row = client.get("/api/screen").json()["rows"][0]
    assert "peReported" in row and "peForward" in row
    assert "peClean" not in row
    assert "peClean" not in ROW_KEYS and "peClean" not in COLUMNS
    bundle = _component_file("bundle.js")
    assert "key: 'peClean'" not in bundle and "'Clean P/E'" not in bundle
    assert "{ key: 'peReported', head: 'P/E', num: true," in bundle
    assert "{ key: 'peForward', head: 'Forward P/E', num: true," in bundle
    assert "peClean" not in _component_file("index.d.ts")


def test_bundle_default_columns_end_with_designation() -> None:
    """Spec 7.3's default columns. A list saved before carries `stance`, which the bundle no
    longer has; the page's normalise puts `designation` in its place."""
    bundle = _component_file("bundle.js")
    default = re.search(r"var DEFAULT_COLUMNS = \[(.*?)\];", bundle, re.DOTALL)
    assert default is not None
    assert re.findall(r"'(\w+)'", default.group(1)) == [
        "ticker",
        "name",
        "phase",
        "band",
        "mechanical",
        "reviewed",
        "price",
        "designation",
    ]


def test_bundle_has_the_five_designation_words() -> None:
    """The five words in band order, keyed by the engine's codes, and exported for the drawer."""
    bundle = _component_file("bundle.js")
    words = re.search(r"var DESIGNATION = \{(.*?)\};", bundle, re.DOTALL)
    assert words is not None
    assert re.findall(r"'([\w-]+)': '([^']+)'", words.group(1)) == [
        ("well-below", "Well below"),
        ("below", "Below"),
        ("near", "Near"),
        ("above", "Above"),
        ("well-above", "Well above"),
    ]
    assert [code for code, _ in re.findall(r"'([\w-]+)': '([^']+)'", words.group(1))] == list(
        get_args(Designation)
    )
    assert "DESIGNATION: DESIGNATION," in bundle


def test_bundle_filter_menu_has_a_price_vs_value_section() -> None:
    """Spec 7.3: PRICE VS VALUE stands where STANCE stood, its five words in band order, each a
    checkbox as PHASE's are; the chip names the chosen words in band order."""
    bundle = _component_file("bundle.js")
    groups = "['designation', 'stance', 'phase', 'cap', 'sector', 'industry', 'watchlist']"
    assert f"var FILTER_GROUPS = {groups};" in bundle
    assert "var EMPTY_FILTERS = { designation: [], stance: [], phase: [], cap: []," in bundle
    assert "p.onFiltersChange({ designation: [], stance: [], phase: [], cap: []," in bundle
    assert bundle.count("sector: [], industry: [],") == 2  # the group follows the sector's
    assert "h('span', { className: 'fb-menu__h label' }, 'PRICE VS VALUE')," in bundle
    assert "Object.keys(DESIGNATION).map(function (k) {" in bundle
    assert "return checkRow(k, listOf(filters, 'designation').indexOf(k) !== -1," in bundle
    assert "function () { toggleIn('designation', k); }," in bundle
    assert "h('span', null, DESIGNATION[k]));" in bundle
    assert bundle.index("'PRICE VS VALUE'") < bundle.index("'PHASE'")
    # the chip: "Price vs value: Below + Near", whatever order the boxes were ticked in
    assert "out.push({ key: 'designation', word: 'Price vs value: ' + Object.keys(DESIGNATION)" in (
        bundle
    )
    assert ".filter(function (k) { return f.designation.indexOf(k) !== -1; })" in bundle


def test_bundle_has_the_watch_mark_and_the_two_filters() -> None:
    bundle = _component_file("bundle.js")
    assert "// fairband: the watchlist mark (spec 2026-11-04 9.4)" in bundle
    assert "onClick: function (e) { e.stopPropagation(); p.onWatch(r); }" in bundle
    assert "'aria-pressed': r.watched ? 'true' : 'false'" in bundle
    assert "watchlist: [], reviewedOnly: false, hideExpired: false };" in bundle
    assert "'WATCHLISTS'" in bundle and "'No warning flag'" not in bundle
    assert "{ key: 'watchlists', head: 'Watchlists'" in bundle
    dts = _component_file("index.d.ts")
    assert "onWatch?: (row: ScreenRow) => void;" in dts
    # the Clean filter is gone (spec 2026-11-19 7.5)
    for name, text in (("bundle.js", bundle), ("index.d.ts", dts)):
        assert "cleanOnly" not in text, name


def test_bundle_draws_the_mark_only_given_onWatch() -> None:
    """Spec 2026-11-04 9.4: the mark is a button at the left of the Ticker cell, named for its
    ticker, filled when the company is on a list; Enter and Space on it never open the row; a
    table without onWatch draws none. The cells see the props, for the mark and the list names,
    and a cell whose figure a run changed takes its tint (spec 2026-11-23 refresh experience,
    4.2; tests/web/test_end_signal.py)."""
    bundle = _component_file("bundle.js")
    assert "p.onWatch ? h('button', {" in bundle
    assert "className: cx('fb-watch control', r.watched && 'fb-watch--on')," in bundle
    assert "'aria-label': 'Watchlists for ' + r.ticker," in bundle
    assert "if (e.key === 'Enter' || e.key === ' ') e.stopPropagation();" in bundle
    assert "}, r.watched ? '▶' : '▸') : null," in bundle
    assert "return h(React.Fragment, { key: c.key }, tinted(c.cell(r, p), r, c.key));" in bundle
    css = _component_file("bundle.css")
    assert ".fb-watch--on { color: var(--accent); }" in css
    ring = "outline: 2px solid var(--focus-ring); outline-offset: 2px;"
    assert f".fb-watch:focus-visible {{ {ring} }}" in css


def test_bundle_filters_on_watchlists() -> None:
    """Spec 2026-11-04 9.4: WATCHLISTS follows SECTOR in the menu, one row per list by name; a
    chosen list's chip is its name, more than two their count; Clear all empties it. VALUE holds
    the two flags left once the Clean filter has gone (spec 2026-11-19 7.5)."""
    bundle = _component_file("bundle.js")
    assert "var FILTER_FLAGS = ['reviewedOnly', 'hideExpired'];" in bundle
    assert "var FLAG_WORDS = { reviewedOnly: 'Reviewed only', hideExpired: 'Hide expired' };" in (
        bundle
    )
    assert bundle.index("'SECTOR'") < bundle.index("'WATCHLISTS'") < bundle.index("'VALUE'")
    assert "function () { toggleIn('watchlist', w.id); }," in bundle
    assert "h('span', null, FLAG_ROWS[k] || FLAG_WORDS[k])" in bundle
    assert "var chips = summarise(p.filters, lists);" in bundle
    assert "word: n <= 2 && names.length === n" in bundle
    assert "n + (n === 1 ? ' watchlist' : ' watchlists')" in bundle
    clear = bundle[bundle.index("function clearAll() {") : bundle.index("function checkRow")]
    assert "watchlist: [], reviewedOnly: false, hideExpired: false });" in clear


def test_bundle_draws_the_watchlist_column() -> None:
    """Spec 2026-11-04 9.4: the list names joined by ` · `, an em dash for none. The Flags and
    the Warnings columns are gone (spec 2026-11-19 7.5): no column draws a row's flags or their
    count."""
    bundle = _component_file("bundle.js")
    assert "return wordCell(names.length ? names.join(' · ') : null);" in bundle
    assert "{ key: 'flags'" not in bundle and "{ key: 'flagCount'" not in bundle
    assert "r.flags" not in bundle and "r.flagCount" not in bundle
    # every column has a head of its own, so the chooser never offers two boxes with one name
    heads = re.findall(r"\{ key: '\w+', head: '([^']+)'", bundle)
    assert len(heads) == len(set(heads))


def test_the_screen_and_the_watchlists_hand_the_table_the_note() -> None:
    """Spec 2026-11-19 7.5 and 9: the screen's table, which draws the watchlist page's list too
    (spec 2026-11-22 7.1), hands ScreenTable the screen's note, which the page holds beside the
    open company's. The mark's rule stands beside the Mechanical cell's: form A of the look, the
    bullet of the mono face enlarged, in the value's ink, so it sets no colour; the drawer and the
    company page load the same file. The hover, the mark and the note's prop are `// fairband:`
    patches that index.d.ts declares (``tests/web/test_warning_mark.py`` draws them)."""
    app = _static_file("app.js")
    assert "mechanicalNote: SCREEN_NOTE," in _function(app, "render")
    shared = app[app.index("window.FairbandPage = {") :]
    assert "SCREEN_NOTE: SCREEN_NOTE, OPEN_NOTE: OPEN_NOTE," in shared[: shared.index("};")]
    assert "F.ScreenTable" not in _static_file("watchlists.js")  # the list's table is the screen's
    css = _component_file("bundle.css")
    rule = (
        ".fb-warnmark { font-family: var(--font-mono); font-size: 22px; line-height: 0;"
        " margin-right: 5px; vertical-align: -3px; }"
    )
    assert rule in css and "color" not in _rule(css, ".fb-warnmark {")
    beside = css[css.index(".fb-screen__mech {") : css.index(rule)]
    assert beside.count("\n.") == 0  # nothing but the patch's comment between the two rules
    assert "/* fairband: the warnings mark before a mechanical value (spec 2026-11-19 7.5" in beside
    bundle = _component_file("bundle.js")
    for patch in (
        "// fairband: the hover of a mechanical value (spec 2026-11-19 7.5)",
        "// fairband: the warnings mark (spec 2026-11-19 7.5 and 9)",
        "// fairband: given mechanicalNote (spec 2026-11-19 7.5)",
    ):
        assert patch in bundle, patch
    assert "warningsHover: warningsHover," in bundle and "WarningMark: WarningMark," in bundle


def test_the_drawer_hangs_the_mark_in_the_column_gap() -> None:
    """The look's defect D1 and the final review of plan 2, Minor 4: in the drawer's list of
    levels, left-aligned, the mark before the Fair value figure pushed it 18.2px right of the
    other three (the bullet's 13.2px advance at 22px of the mono face, and the mark's 5px right
    margin). The drawer's own rule hangs it in the 12px column gap: a negative left margin of the
    advance plus a 1px right margin, so the figure keeps the levels' left edge and the dot's ink,
    about 4.9 to 10.4px left of it, stays clear of the label. The mark's own rule, which the
    right-aligned screen, watchlists and company page read, does not change."""
    page = _static_file("index.html")
    rule = ".app-drawer__band .app-pairs .fb-warnmark { margin-left: -14.2px; margin-right: 1px; }"
    assert rule in page
    assert "gap: var(--space-1) var(--space-3);" in _rule(page, ".app-pairs {")
    assert "--space-3: 12px;" in _static_file("design-system/tokens/tokens.css")
    advance = 0.6 * 22  # IBM Plex Mono's advance, 600 of 1,000 units, at the mark's 22px
    assert -14.2 + advance + 1 == pytest.approx(0)  # the figure stays on the levels' left edge
    css = _component_file("bundle.css")
    assert (
        ".fb-warnmark { font-family: var(--font-mono); font-size: 22px; line-height: 0;"
        " margin-right: 5px; vertical-align: -3px; }"
    ) in css
    dts = _component_file("index.d.ts")
    assert "export declare function warningsHover(words: string[], note: string): string;" in dts
    assert "export declare function WarningMark(props: WarningMarkProps): unknown;" in dts
    assert "export interface WarningMarkProps {\n  words: string[];\n}" in dts


def test_bundle_designation_column_head_and_chip() -> None:
    """Spec 7.3: the column shows the row's word as a chip in its band's colour; a row without one
    (a refusal, a placeholder, a snapshot valued before the designation) shows an em dash, never a
    word derived from the levels."""
    bundle = _component_file("bundle.js")
    assert "{ key: 'designation', head: 'Price vs value'," in bundle
    assert "var word = DESIGNATION[r.designation];" in bundle
    assert "if (!word) return h('td', null, h('span', { className: 'fb-screen__none' }, '—'));" in (
        bundle
    )
    # the column's cell and the band meter's head: the same chip, in its band's colour
    assert bundle.count(".designation + ' label' }, word)") == 2
    assert "var word = DESIGNATION[p.designation];" in bundle  # the meter takes the row's word
    assert "Hold'" not in bundle  # never "Hold": the agent's stance has a column of its own
    css = _component_file("bundle.css")
    rule = re.search(r"\.fb-designation \{(.*?)\}", css, re.DOTALL)
    assert rule is not None
    assert "text-transform: uppercase;" in rule.group(1)
    assert "border: 1px solid currentColor;" in rule.group(1)
    assert "color:" not in rule.group(1)  # the band's modifier sets the colour
    # the stance tokens stay for the delta and the recommendation's effect; the spread chart's
    # label takes the delta's classes in place of the stance chip's
    assert ".fb-delta--up { color: var(--stance-buy); }" in css
    assert ".fb-rec__effect { font-weight: 500; color: var(--stance-buy); }" in css
    assert "cur.roic >= cur.wacc ? 'fb-delta--up' : 'fb-delta--down'" in bundle


def _code(script: str) -> str:
    """A script or a declaration file without its comments."""
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", script, flags=re.DOTALL)


def test_no_derived_stance_remains() -> None:
    """Spec 7.2: the engine gives no stance, and the page derives none. The one stance the page
    names is the agent's, the word of the company's latest published report (spec 2026-11-06 Tier
    2, 18.1): the row's ``agentStance``, its column, the STANCE filter group and the chip's
    classes, and no other name in the code. The drawer's stance line left it (the company page's
    design, 11)."""
    files = {
        "app.js": _static_file("app.js"),
        "controls.js": _static_file("controls.js"),
        "bundle.js": _component_file("bundle.js"),
        "index.d.ts": _component_file("index.d.ts"),
    }
    for name, text in files.items():
        for gone in ("stanceOf", "STANCE[", "Five-step", "stance5", "stance3"):
            assert gone not in text, (name, gone)
    assert re.search(r"\bstance", files["controls.js"], re.IGNORECASE) is None
    # A column list saved under method 0.5 carries the old key, which normalise maps to the
    # designation's: app.js's one bare 'stance' outside the filter.
    assert files["app.js"].count("key === 'stance' ? 'designation' : key") == 1
    # the names holding the word: `stance` starting a word, `Stance` or `STANCE` anywhere in one
    # (`agentStance`, `AGENT_STANCES`); never the `stance` inside another word (`instanceof`)
    word = re.compile(r"[\w.-]*(?:\bstance|Stance|STANCE)[\w-]*")
    named = {
        name: set(word.findall(_code(files[name])))
        for name in ("app.js", "bundle.js", "index.d.ts")
    }
    assert named["app.js"] == {"stance", "agentStance", "filters.stance", "r.agentStance"}
    assert named["bundle.js"] == {
        "AGENT_STANCES",
        "stance",
        "Stance",
        "STANCE",
        "f.stance",
        "agentStance",
        "r.agentStance",
        "fb-stance",
        "fb-stance--",
        "fb-stance--expired",
    }
    assert named["index.d.ts"] == {"AgentStance", "agentStance", "stance"}
    # the Research tab's stance (18.4): the report's own word in the column's chip classes
    tab = set(word.findall(_code(_static_file("company_research.js"))))
    assert tab == {"report.stance", "r.stance", "fb-stance", "fb-stance--", "fb-stance--expired"}


def test_the_bundle_stance_words_are_the_policys(policy: Policy) -> None:
    """The menu's STANCE rows, the chip's order and the declared union are the policy's
    ``stance_words`` in its order, the order the server sorts the column by."""
    bundle = _component_file("bundle.js")
    words = re.search(r"var AGENT_STANCES = \[(.*?)\];", bundle)
    assert words is not None
    assert tuple(re.findall(r"'(\w+)'", words.group(1))) == policy.stance_words
    declarations = _component_file("index.d.ts")
    union = re.search(r"export type AgentStance = (.*?);", declarations)
    assert union is not None
    assert tuple(re.findall(r"'(\w+)'", union.group(1))) == policy.stance_words


def test_the_bundle_draws_the_stance_column_and_the_mark() -> None:
    """Spec 2026-11-06 Tier 2, 18.1, each a `// fairband:` patch naming the section: the Stance
    column after Price vs value draws the report's word as a chip in the stance tokens, avoid in
    ink, and an em dash without a report; the Filters menu's STANCE group after PRICE VS VALUE
    holds the four words, its chip "Stance: buy + hold" in the words' order; the reviewedOnly row
    reads "Has a review"; the Ticker cell draws ◆ after the ticker for a covered company, in
    prov-input, ink-faint once the report's window has expired, the report's date and actor in its
    title, never a control; a stance whose report's window has expired fades to ink-faint as the
    mark does, its title saying so. The chooser and COLUMN_KEYS list every column; the default
    eight stay."""
    bundle = _component_file("bundle.js")
    # the column
    column = bundle.index("{ key: 'agentStance', head: 'Stance',")
    assert (
        bundle.index("{ key: 'designation', head: 'Price vs value',")
        < bundle.index("// fairband: the agent's stance (spec 2026-11-06 Tier 2, 18.1)")
        < column
        < bundle.index("{ key: 'overrides', head: 'Overrides',")
    )
    none = "h('td', null, h('span', { className: 'fb-screen__none' }, '—'));"
    assert f"if (r.agentStance == null) return {none}" in bundle
    cell = bundle[column : bundle.index("{ key: 'overrides', head: 'Overrides',")]
    assert "var stale = !!(r.covered && r.covered.expired);" in cell
    classes = "'fb-stance', 'fb-stance--' + r.agentStance, stale && 'fb-stance--expired', 'label'"
    assert f"className: cx({classes})," in cell
    assert "title: stale ? coverage(r.covered) : null" in cell
    assert "}, r.agentStance));" in cell
    assert "// fairband: once the window of the snapshot the report rests on has expired" in bundle
    assert "COLUMN_KEYS: COLUMNS.map(function (c) { return c.key; })," in bundle
    assert (
        "shown.concat(COLUMNS.filter(function (c) { return shown.indexOf(c) === -1; }))" in bundle
    )
    # the filter
    assert "// fairband: STANCE, the agent's four words (spec 2026-11-06 Tier 2, 18.1)" in bundle
    assert bundle.index("'PRICE VS VALUE'") < bundle.index("'STANCE'") < bundle.index("'PHASE'")
    assert "AGENT_STANCES.map(function (k) {" in bundle
    assert "return checkRow(k, listOf(filters, 'stance').indexOf(k) !== -1," in bundle
    assert "function () { toggleIn('stance', k); }," in bundle
    assert "out.push({ key: 'stance', word: 'Stance: ' + AGENT_STANCES" in bundle
    assert ".filter(function (k) { return f.stance.indexOf(k) !== -1; }).join(' + ') });" in bundle
    assert "var FLAG_ROWS = { reviewedOnly: 'Has a review' };" in bundle
    # the mark
    ticker = bundle[
        bundle.index("{ key: 'ticker', head: 'Ticker'") : bundle.index("{ key: 'name', head:")
    ]
    assert "// fairband: the coverage mark (spec 2026-11-06 Tier 2, 18.1)" in ticker
    mark = ticker[ticker.index("r.covered ? h('span', {") :]
    assert ticker.index("r.ticker,") < ticker.index("r.covered ? h('span', {")
    assert "className: cx('fb-covered', r.covered.expired && 'fb-covered--expired')," in mark
    assert "title: coverage(r.covered), role: 'img', 'aria-label': coverage(r.covered)" in mark
    assert "}, GLYPH_INPUT) : null" in mark
    for control in ("tabIndex", "onClick", "onKeyDown", "button"):
        assert control not in mark, control
    assert "return 'Report ' + readable(String(c.at).slice(0, 10)) + ' by ' + c.actor +" in bundle
    assert "(c.expired ? '; its snapshot window has expired' : '');" in bundle
    css = _component_file("bundle.css")
    assert "/* fairband: the agent's stance word (spec 2026-11-06 Tier 2, 18.1)" in css
    assert "/* fairband: the coverage mark after the ticker (spec 2026-11-06 Tier 2, 18.1)" in css
    for rule in (
        ".fb-stance--buy { color: var(--stance-buy); }",
        ".fb-stance--hold { color: var(--stance-hold); }",
        ".fb-stance--trim { color: var(--stance-trim); }",
        ".fb-stance--avoid { color: var(--ink); }",
        ".fb-stance--expired { color: var(--ink-faint); }",
        ".fb-covered--expired { color: var(--ink-faint); }",
    ):
        assert rule in css, rule
    # the faded word follows the words' colours, so it wins over each
    assert css.index(".fb-stance--avoid {") < css.index(".fb-stance--expired {")
    stance = re.search(r"\.fb-stance \{(.*?)\}", css, re.DOTALL)
    assert stance is not None and "color:" not in stance.group(1)  # the word's modifier sets it
    covered = re.search(r"\.fb-covered \{(.*?)\}", css, re.DOTALL)
    assert covered is not None and "color: var(--prov-input);" in covered.group(1)
    assert "cursor" not in covered.group(1)
    declarations = _component_file("index.d.ts")
    row = re.search(r"export interface ScreenRow \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert row is not None
    assert "agentStance?: AgentStance | null;" in row.group(1)
    assert "when `covered.expired`" in row.group(1)
    assert "covered?: { at: string; actor: string; expired: boolean } | null;" in row.group(1)
    filters = re.search(r"export interface ScreenFilters \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert filters is not None and "stance: AgentStance[];" in filters.group(1)


def test_bundle_has_the_margin_columns() -> None:
    """The two margins of the growth routes, percentages as the other fractions are, after the
    growth-route value in the catalog."""
    bundle = _component_file("bundle.js")
    assert "key: 'targetMargin'" in bundle and "key: 'impliedMargin'" in bundle
    assert "figureCell(percent(r.targetMargin))" in bundle
    assert "figureCell(percent(r.impliedMargin))" in bundle
    margins = ("growthRouteValue", "targetMargin", "impliedMargin")
    start = EXTRA_KEYS.index(margins[0])
    assert EXTRA_KEYS[start : start + 3] == margins
    order = [bundle.index(f"key: '{key}'") for key in margins]
    assert order == sorted(order)


# The Start-up and Decline rows' columns, after the margins, with their heads.
ROUTE_COLUMN_HEADS = {
    "requiredRevenue": "Needs by yr 10",
    "burnCover": "Cash cover",
    "rating": "Rating",
    "distressProbability": "π",
    "altmanZ": "Altman Z″",
    "piotroskiF": "Piotroski F",
    "impliedDeclineRate": "Implied decline",
}


def test_bundle_catalog_has_the_route_columns() -> None:
    """The figures of the Start-up and Decline rows as columns, each a row key the API sends,
    after the margins in the catalog and off by default: the year-10 revenue in billions as the
    market cap is, the cash cover in years to one decimal, π and the implied decline rate as
    percentages, Z″ to two decimals, the rating and F as the row gives them."""
    bundle = _component_file("bundle.js")
    assert tuple(ROUTE_COLUMN_HEADS) == START_UP_KEYS + DECLINE_KEYS == EXTRA_KEYS[-7:]
    for key, head in ROUTE_COLUMN_HEADS.items():
        assert f"{{ key: '{key}', head: '{head}'," in bundle, key
    order = [bundle.index(f"key: '{key}'") for key in ("impliedMargin", *ROUTE_COLUMN_HEADS)]
    assert order == sorted(order)
    default = re.search(r"var DEFAULT_COLUMNS = \[(.*?)\];", bundle, re.DOTALL)
    assert default is not None
    assert not set(ROUTE_COLUMN_HEADS) & set(re.findall(r"'(\w+)'", default.group(1)))
    for cell in (
        "figureCell(billions(r.requiredRevenue))",
        "figureCell(years(r.burnCover))",
        "wordCell(r.rating)",
        "figureCell(percent(r.distressProbability))",
        "figureCell(fixed(r.altmanZ, 2))",
        "figureCell(r.piotroskiF == null ? '—' : r.piotroskiF)",
        "figureCell(percent(r.impliedDeclineRate))",
    ):
        assert cell in bundle, cell
    years = "return v == null || isNaN(Number(v)) ? '—' : signed(Number(v).toFixed(1)) + ' years';"
    assert years in bundle
    # π keeps its case in the header, where the label's upper case would make it Π
    css = _component_file("bundle.css")
    assert '.fb-table thead th[data-key="distressProbability"] { text-transform: none; }' in css
    declarations = _component_file("index.d.ts")
    row = re.search(r"export interface ScreenRow \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert row is not None
    for declared in (
        "requiredRevenue?: number | null;",
        "burnCover?: number | null;",
        "rating?: string | null;",
        "distressProbability?: number | null;",
        "altmanZ?: number | null;",
        "piotroskiF?: string | null;",
        "impliedDeclineRate?: number | null;",
    ):
        assert declared in row.group(1), declared


def test_bundle_css_colours_the_five_designations() -> None:
    """Spec 7.3 as amended (founder 2026-11-03): the chip's word takes one gradient from the
    design system's scales, teal below the value through the muted ink to terracotta above it,
    through tokens both themes define. The chip names its band's code, in the column's cell and
    the band meter's head alike."""
    colours = {
        "well-below": "--chart-pos-3",
        "below": "--chart-pos-2",
        "near": "--ink-muted",
        "above": "--chart-neg-2",
        "well-above": "--chart-neg-3",
    }
    assert tuple(colours) == get_args(Designation)
    css = _component_file("bundle.css")
    marker = css.index("/* fairband: the five designations")
    for code, token in colours.items():
        rule = f".fb-designation--{code} {{ color: var({token}); }}"
        assert rule in css, code
        assert marker < css.index(rule) and css.index(".fb-designation {") < css.index(rule)
    tokens = (
        resources.files("fairband.web")
        .joinpath("static/design-system/tokens/tokens.css")
        .read_text(encoding="utf-8")
    )
    for token in colours.values():
        # the dark root, the light theme and the light preference
        assert len(re.findall(rf"^\s*{token}: #", tokens, re.MULTILINE)) == 3, token
    bundle = _component_file("bundle.js")
    for name in ("r", "p"):
        chip = f"h('span', {{ className: 'fb-designation fb-designation--' + {name}.designation"
        assert chip + " + ' label' }, word)" in bundle, name
    assert "className: 'fb-designation label'" not in bundle  # no chip without its band


def test_bundle_patches_marked() -> None:
    """The repository's patches to the exported bundle each carry a ``// fairband:`` comment, so
    a later export can be diffed against them."""
    bundle = _component_file("bundle.js")
    assert bundle.count("// fairband:") >= 56
    # A menu's toggle says whether its menu is open: Button passes aria-expanded through.
    assert "'aria-expanded': p['aria-expanded']," in bundle
    # A null phase has no badge: an em dash, never phase 1 "Start-up".
    assert "Number(p.phase) || 1" not in bundle
    assert "if (p.phase == null) return h('span', { className: 'fb-screen__none' }, '—');" in bundle
    # A timestamp in the Entered cell reads as its date; the full ISO stays in the datetime
    # attribute. formatDate itself keeps the time, which the header's engine stamp shows.
    assert "iso ? h('time', { dateTime: iso, title: iso }, readable(iso.slice(0, 10)))" in bundle
    assert "return t ? day + ', ' + t[1] : day;" in bundle
    # A header cell names its column and sorts through onSort, by click, Enter or Space.
    assert "'data-key': c.key" in bundle
    assert "tabIndex: p.onSort ? 0 : null" in bundle
    assert "p.onSort(c.key)" in bundle
    # Given onOpen, a row is focusable and opens on a click, Enter or Space. It stays a row: no
    # role="button", whose cells would turn presentational; the open row is aria-current.
    assert "tabIndex: p.onOpen ? 0 : null" in bundle
    assert "p.onOpen(r)" in bundle
    assert "role: p.onOpen" not in bundle
    assert "'aria-current': r.selected ? 'true' : null" in bundle
    assert "'aria-selected'" not in bundle
    # The columns render in the list's order; a locked column the list lacks still shows, Ticker
    # first and Price last. A drop's click does not sort; a press clears the flag first. The
    # chooser lists the table's order, then the rest in catalog order.
    assert "if (shown.indexOf(columnOf('ticker')) === -1) shown.unshift(columnOf('ticker'));" in (
        bundle
    )
    assert "if (shown.indexOf(columnOf('price')) === -1) shown.push(columnOf('price'));" in bundle
    assert "if (drag.current.dropped) { drag.current.dropped = false; return; }" in bundle
    assert "onPointerDown: function () { drag.current.dropped = false; }" in bundle
    assert "shown.concat(COLUMNS.filter(function (c) { return shown.indexOf(c) === -1; }))" in (
        bundle
    )


def test_bundle_orders_columns_by_the_list() -> None:
    bundle = _component_file("bundle.js")
    assert "var shown = visible.map(function (key) {" in bundle
    assert "draggable: p.onColumnsChange ? true : null" in bundle
    assert "p.onColumnsChange(moved(visible, " in bundle
    assert "COLUMN_KEYS: COLUMNS.map(function (c) { return c.key; })" in bundle
    assert bundle.count("// fairband:") >= 10
    css = _component_file("bundle.css")
    assert "th.is-drop-before { box-shadow: inset 2px 0 0 var(--accent); }" in css
    assert "th.is-drop-after { box-shadow: inset -2px 0 0 var(--accent); }" in css
    # The edge is on the side where the column will land: after the target when it comes from
    # the left.
    assert "var after = visible.indexOf(from) < visible.indexOf(c.key);" in bundle
    # A drag carries a type of its own, which no text field accepts: a header dropped on FIND
    # types nothing into it.
    assert "e.dataTransfer.setData('application/x-fairband-column', c.key);" in bundle
    assert "'text/plain'" not in bundle


def test_bundle_is_the_november_build() -> None:
    bundle = _component_file("bundle.js")
    for name in ("AppHeader", "RunProgress", "Mark", "CAPS", "SECTORS", "EMPTY_FILTERS"):
        assert f"{name}: {name}" in bundle, name  # exported on window.Fairband
    assert "'fb-logo" in bundle and "'fb-screen__find'" in bundle
    tokens = (
        resources.files("fairband.web")
        .joinpath("static/design-system/tokens/tokens.css")
        .read_text(encoding="utf-8")
    )
    assert "--header-height: 44px;" in tokens


def test_bundle_keeps_the_freshness_glyph_class() -> None:
    bundle = _component_file("bundle.js")
    assert "className: 'fb-mark fb-mark--' + f" in bundle
    css = _component_file("bundle.css")
    assert ".fb-mark--aging" in css and ".fb-logo" in css


def test_bundle_menus_close_on_outside_click_and_escape() -> None:
    """Growth-routes spec 6.3: a press or focus outside the table's menus or Escape closes them,
    and opening one closes the other."""
    bundle = _component_file("bundle.js")
    assert "document.addEventListener('pointerdown'" in bundle
    assert "e.key === 'Escape'" in bundle
    assert "fopen[1](!fopen[0]); open[1](false);" in bundle
    assert "open[1](!open[0]); fopen[1](false);" in bundle
    # focus moving outside closes them too: Enter or Space on another menu's toggle sends a click
    # with no pointerdown
    assert "document.addEventListener('focusin', onOutside);" in bundle
    assert "document.removeEventListener('focusin', onOutside);" in bundle
    # the listeners live only while a menu is open, and a press inside one of the bar's menus
    # keeps them open
    assert "if (!open[0] && !fopen[0]) return undefined;" in bundle
    assert "document.removeEventListener('pointerdown', onOutside);" in bundle
    assert "document.removeEventListener('keydown', onKeyDown);" in bundle
    assert "}, [open[0], fopen[0]]);" in bundle
    assert "barRef.current.querySelectorAll('.fb-screen__cols')" in bundle
    assert "h('div', { className: 'fb-screen__bar', ref: barRef }," in bundle


def test_bundle_find_has_a_clear_word() -> None:
    bundle = _component_file("bundle.js")
    assert "p.query ? h('button', { type: 'button', className: 'fb-screen__clear control'" in bundle
    # Clear unmounts with the text: it hands focus back to the field, not to the page body
    clear = bundle.index("p.query ? h('button', { type: 'button', className: 'fb-screen__clear")
    handler = bundle[clear : bundle.index("'Clear')", clear)]
    assert "p.onQueryChange('');" in handler
    assert "var q = document.getElementById('fb-q');" in handler
    assert "if (q) q.focus();" in handler
    assert handler.index("p.onQueryChange('');") < handler.index("q.focus()")
    css = _component_file("bundle.css")
    assert (
        ".fb-screen__clear:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }"
        in (css)
    )


def _rule(css: str, selector: str) -> str:
    """The declarations of the one rule whose line opens with ``selector``."""
    starts = [m.start() for m in re.finditer(r"(?m)^[ \t]*" + re.escape(selector), css)]
    assert len(starts) == 1, selector
    return css[starts[0] : css.index("}", starts[0])]


def test_the_bar_gives_the_find_ring_room() -> None:
    """FIND's focus ring (2px, offset 1px) needs room at the scroller's top edge. That room was
    the scroller's padding; with the bar sticky it is the bar's own padding, since a sticky child
    stops at the scroller's padding edge and rows would show above the bar."""
    css = _component_file("bundle.css")
    assert "padding: var(--space-1) 0 var(--space-2);" in _rule(css, ".fb-screen__bar {")
    assert "the room FIND's focus ring (2px, offset 1px) needs" in css
    page = _static_file("index.html")
    assert "padding" not in _rule(page, ".app-main {")


def test_the_columns_menu_scrolls_inside_the_window() -> None:
    """Columns ▾ lists all 45 columns, taller than a 900px window: a menu of the screen's bar
    stops 12rem short of the window's height and scrolls, so the last rows can be reached (spec
    2026-11-04 9.4)."""
    css = _component_file("bundle.css")
    menu = _rule(css, ".fb-screen__cols > .fb-menu {")
    assert "max-height: calc(100vh - 12rem);" in menu and "overflow-y: auto;" in menu
    patch = css[: css.index(".fb-screen__cols > .fb-menu {")]
    patch = patch[patch.rindex("/* fairband:") :]
    assert "(spec 2026-11-04 9.4)" in patch


def test_bundle_css_bar_is_sticky_and_the_header_sits_under_it() -> None:
    """Classifier-designation spec 8.2: the FIND, filter and columns bar sticks at the top of the
    table's scroller, on the raised surface above the header cells, and the screen's header cells
    stick under it at its measured height, the bar's one-line height until it is measured. Its
    space below is padding, so no row shows between the bar and the header. The groups' table
    keeps its header at the top."""
    css = _component_file("bundle.css")
    bar = _rule(css, ".fb-screen__bar {")
    assert "position: sticky;" in bar and "top: 0;" in bar
    assert "z-index: 5;" in bar and "background: var(--surface-raised);" in bar
    assert "margin" not in bar
    assert css.index("/* fairband: the bar sticks") < css.index(".fb-screen__bar {")
    # 38px: the bar's one line, a 26px control in space-1 above and space-2 below.
    assert ".fb-screen .fb-table thead th { top: var(--bar-height, 38px); }" in css
    head = _rule(css, ".fb-table thead th {")
    assert "position: sticky;" in head and "top: 0;" in head


def test_app_js_measures_the_bar() -> None:
    """The header cells' top follows the bar's height as its chips wrap, and the bar's width the
    scroller's less its scrollbar: an observer on the bar and the scroller sets --bar-height and
    --scroller-width on the scroller, and goes when the table does."""
    script = _static_file("app.js")
    assert "if (!bar || typeof ResizeObserver === 'undefined') return undefined;" in script
    assert "var bar = document.querySelector('.fb-screen__bar');" in script
    assert "main.style.setProperty('--bar-height', bar.offsetHeight + 'px');" in script
    assert "main.style.setProperty('--scroller-width', main.clientWidth + 'px');" in script
    assert "observer.observe(bar);" in script and "observer.observe(main);" in script
    assert "return function () { observer.disconnect(); };" in script
    assert "main = h(Screen, {" in script


def test_app_js_keeps_the_measures_while_the_screen_is_hidden() -> None:
    """The Groups view hides the screen, whose scroller then measures 0 wide: the observer
    writes neither 0px measure nor asks after Top until the screen shows again."""
    script = _static_file("app.js")
    observer = script[script.index("new ResizeObserver(function () {") :]
    observer = observer[: observer.index("});")]
    guard = "if (main.clientWidth === 0) return;"
    assert guard in observer
    assert observer.index(guard) < observer.index("--bar-height")
    assert observer.index(guard) < observer.index("--scroller-width")
    assert observer.index(guard) < observer.index("pastFirstScreen(main);")


def test_index_keeps_the_bar_in_view_sideways() -> None:
    """A table wider than the scroller scrolls sideways under the bar, which stays in view at no
    more than the scroller's width, so no row shows beside it; a table that fits keeps the
    scroller's width. The width is a cap: a width the scroller has just outgrown would widen the
    screen for a frame, and the scrollbar that brings and takes away is a ResizeObserver loop."""
    page = _static_file("index.html")
    assert ".app-main .fb-screen { width: fit-content; min-width: 100%; }" in page
    assert ".app-main .fb-screen__bar { left: 0; max-width: var(--scroller-width, none); }" in page
    assert " width: var(--scroller-width" not in page


def test_app_js_back_to_top() -> None:
    """Spec 8.3: past one screen of the table's scroller, a quiet small Top control; it returns
    the scroller to its start at once and hands focus to FIND, since the control goes at the
    top."""
    script = _static_file("app.js")
    assert "h('div', { className: 'app-main', onScroll: scrolled }, main)" in script
    assert "function scrolled(event) { pastFirstScreen(event.currentTarget); }" in script
    assert "var past = main.scrollTop > main.clientHeight;" in script
    # A scroller made taller can leave the threshold behind without a scroll: the observer asks
    # again, so Top goes then too.
    observer = script[script.index("new ResizeObserver(function () {") :]
    assert "pastFirstScreen(main);" in observer[: observer.index("});")]
    assert "state.pastFirstScreen ? h(F.Button, {" in script
    assert (
        "variant: 'quiet', size: 'sm', 'aria-label': 'Back to top', className: 'app-top'," in script
    )
    assert "}, 'Top ↑') : null" in script
    # Top after the table and before the drawer, so Shift+Tab from the drawer reaches it.
    render = script[script.index("function render() {") :]
    render = render[: render.index("\n  }\n")]
    assert (
        render.index("className: 'app-main'")
        < render.index("state.pastFirstScreen ?")
        < render.index("d ? drawer(d)")
    )
    handler = script[script.index("function toTop() {") :]
    handler = handler[: handler.index("\n  }\n")]
    assert "main.scrollTop = 0;" in handler
    assert "document.getElementById('fb-q').focus();" in handler
    assert handler.index("main.scrollTop = 0;") < handler.index("focus()")
    assert "behavior" not in script and "scrollTo(" not in script  # no smooth scrolling
    # The design system's Button passes the name through to the button element.
    bundle = _component_file("bundle.js")
    assert "'aria-label': p['aria-label']," in bundle
    declarations = _component_file("index.d.ts")
    assert "'aria-label'?: string;" in declarations


def test_index_positions_the_top_control() -> None:
    """The Top control sits at the bottom right of the table's column, over the table, so the
    drawer rail never covers it."""
    page = _static_file("index.html")
    assert "position: relative;" in _rule(page, ".app-layout {")
    top = _rule(page, ".app-top {")
    # Both lines named: an absolute grid child's auto end line is the grid's edge, past the rail.
    assert "position: absolute;" in top and "grid-area: 1 / 1 / 2 / 2;" in top
    assert "right: var(--space-4);" in top and "bottom: var(--space-4);" in top
    # Above the table, below the bar (z-index 5) and so below its Filters and Columns menus.
    assert "z-index: 4;" in top and "background: var(--surface-raised);" in top
    assert "z-index: 5;" in _rule(_component_file("bundle.css"), ".fb-screen__bar {")
    assert "transition" not in top


def test_logos_served(client: TestClient) -> None:
    for name in (
        "mark-on-dark.svg",
        "mark-on-light.svg",
        "mark-one-ink-on-dark.svg",
        "mark-one-ink-on-light.svg",
    ):
        response = client.get(f"/static/design-system/assets/Logos/{name}")
        assert response.status_code == 200 and response.headers["content-type"].startswith(
            "image/svg"
        ), name


def test_index_d_ts_declares_onSort() -> None:
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ScreenTableProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    assert "onSort?: (column: string) => void;" in props.group(1)


def test_index_d_ts_declares_onOpen() -> None:
    declarations = _component_file("index.d.ts")
    props = re.search(r"export interface ScreenTableProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    assert "onOpen?: (row: ScreenRow) => void;" in props.group(1)


def test_index_d_ts_says_columns_are_ordered() -> None:
    declarations = _component_file("index.d.ts")
    assert "fairband: ordered" in declarations


def test_index_d_ts_declares_the_designation() -> None:
    """The row's word and ratio, the filter group and the meter's word, typed by the engine's
    codes; no stance type is left."""
    declarations = _component_file("index.d.ts")
    codes = " | ".join(f"'{code}'" for code in get_args(Designation))
    assert f"export type Designation = {codes};" in declarations
    row = re.search(r"export interface ScreenRow \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert row is not None
    assert "priceToValue?: number | null;" in row.group(1)
    assert "designation?: Designation | null;" in row.group(1)
    filters = re.search(r"export interface ScreenFilters \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert filters is not None
    assert "designation: Designation[];" in filters.group(1)
    meter = re.search(r"export interface BandMeterProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert meter is not None
    assert "designation?: Designation | null;" in meter.group(1)
    # The price's comment, edited when the word left it, carries the marker as every patch does.
    assert (
        "/** The market price, per share. fairband: no word is derived from it; see `designation`."
        in meter.group(1)
    )
    assert "export declare const DESIGNATION: Record<Designation, string>;" in declarations


def test_index_d_ts_declares_the_margin_keys() -> None:
    declarations = _component_file("index.d.ts")
    row = re.search(r"export interface ScreenRow \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert row is not None
    assert "targetMargin?: number | null;" in row.group(1)
    assert "impliedMargin?: number | null;" in row.group(1)


def test_index_d_ts_declares_the_watchlist_keys() -> None:
    declarations = _component_file("index.d.ts")
    row = re.search(r"export interface ScreenRow \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert row is not None
    for key in ("watched?: boolean;", "watchlists?: number[];"):
        assert key in row.group(1), key
    # the warnings' words and the mark (spec 2026-11-19 7.5); no column reads the flags or their
    # count, which the row still carries for the agents' screen tool
    for key in ("warnings?: string[];", "marked?: boolean;"):
        assert key in row.group(1), key
    assert "flags?:" not in row.group(1) and "flagCount?:" not in row.group(1)
    filters = re.search(r"export interface ScreenFilters \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert filters is not None
    assert "watchlist: number[];" in filters.group(1)
    assert "cleanOnly" not in filters.group(1)
    props = re.search(r"export interface ScreenTableProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    assert "onWatch?: (row: ScreenRow) => void;" in props.group(1)
    assert "watchlists?: { id: number; name: string }[];" in props.group(1)
    assert "mechanicalNote?: string;" in props.group(1)


def test_each_request_closes_its_connection(tmp_path: Path, db_path: Path, policy: Policy) -> None:
    opened: list[sqlite3.Connection] = []

    def conn_factory() -> sqlite3.Connection:
        opened.append(connect(db_path))
        return opened[-1]

    app = create_app(_settings(tmp_path, db_path), policy, conn_factory, clock=lambda: NOW)
    paths = (
        "/api/screen",
        "/api/companies/AAPL",
        "/api/companies/NOPE",
        "/api/groups?by=phase",
        "/api/settings",
        "/api/policy",
        "/api/deciles",
        "/api/watchlists",
        "/",
    )
    with TestClient(app, base_url=HOST) as c:
        for path in paths:
            c.get(path)
        c.put("/api/settings", json={"changes": {"fade_years": 3}}, headers=HEADER)
        c.post("/api/settings/reset", json={}, headers=HEADER)
        c.post("/api/watchlists", json={"name": "Core"}, headers=HEADER)
        c.put("/api/watchlists/1/symbols/AAPL", headers=HEADER)
        c.put("/api/watchlists/memberships/AAPL", json={"ids": []}, headers=HEADER)
    # the startup's, which marks the refreshes left running, and one for each request to the API
    assert len(opened) == 1 + len(paths) - 1 + 5

    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


def test_serve_cli_parses_port(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FAIRBAND_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.delenv("FAIRBAND_FMP_KEY", raising=False)  # no worker: test_refresh_api has it
    monkeypatch.delenv("FAIRBAND_GURUFOCUS_KEY", raising=False)
    calls: list[tuple[Any, dict[str, Any]]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: calls.append((app, kwargs)))

    assert cli.parse_args(["serve"]).port == DEFAULT_PORT == 8470
    assert cli.main(["serve", "--port", "9123"]) == 0

    [(app, kwargs)] = calls
    assert isinstance(app, FastAPI)
    assert kwargs == {"host": "127.0.0.1", "port": 9123, "log_level": "info"}
    with closing(connect(tmp_path / "data" / "fairband.db")) as conn:
        assert applied_versions(conn) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    with TestClient(app, base_url=HOST) as c:
        body = c.get("/api/screen").json()
    assert body["rows"] == [] and body["refresh"] is None
