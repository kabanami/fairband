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
    high_growth_inputs,
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
from fairband.engine.route import value_company
from fairband.engine.types import Designation, ValuationResult, result_to_json
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.store.companies import insert_companies
from fairband.store.db import applied_versions, connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh
from fairband.store.snapshots import insert_snapshot
from fairband.web.app import create_app
from fairband.web.rows import EXTRA_KEYS

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
    "capBand",
    "marketCap",
    "moat",
    "impliedGrowth",
    "expectedReturn",
    "epv",
    "peReported",
    "peClean",
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
        "capBand": "mega",
        "marketCap": 150_000_000_000.0,
        "moat": "Wide",
        "impliedGrowth": im["implied_growth"],
        "expectedReturn": im["expected_return"]["total"],
        "epv": im["epv"],
        "peReported": im["multiples"]["pe_reported"],
        "peClean": im["multiples"]["pe_clean"],
        "peForward": im["multiples"]["pe_forward"],
        "high52w": facts["high_52w"],
        "low52w": facts["low_52w"],
        "change1y": facts["change_1y"],
        "change3y": None,
        "change5y": None,
        "drawdown": facts["drawdown_from_peak"],
        "flags": [f.word for f in valued.flags],
        "refusal": None,
        "priceToValue": 150.0 / valued.value,  # $150 on the value $133.37: 1.125
        "designation": "near",  # from 0.85 to 1.15 × the value
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
    }

    refused = results["AAL"]
    assert set(aal) == set(aapl)
    assert aal["phase"] == 2 and aal["name"] == "Young Growth Co"
    assert aal["refusal"] == refused.refusal == "no target margin: 0 mature peers"
    for key in ("fairLow", "fairHigh", "fairValue", "buyLevel", "trimLevel", "mechanical"):
        assert aal[key] is None, key
    for key in ("impliedGrowth", "expectedReturn", "epv", "peClean", "route"):
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
    for key in _screen(client)["rows"][0]:
        for direction in ("asc", "desc"):
            assert len(_tickers(client, f"?sort={key}&dir={direction}")) == 3, key


def test_screen_sorts_by_flag_count(client: TestClient) -> None:
    """AAL has no quality warning, AAPL one and HGCO three; the notes do not count."""
    assert [r["flagCount"] for r in _screen(client, "?sort=flagCount")["rows"]] == [0, 1, 3]
    assert _tickers(client, "?sort=flagCount&dir=asc") == ["AAL", "AAPL", "HGCO"]
    assert _tickers(client, "?sort=flagCount&dir=desc") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=watchlists") == ["AAL", "AAPL", "HGCO"]  # a row key too


def test_screen_sorts_by_price_to_value(client: TestClient) -> None:
    """HGCO at 0.63 × its value, AAPL at 1.125, AAL refused with none: last either way."""
    rows = {row["ticker"]: row for row in _screen(client)["rows"]}
    assert rows["HGCO"]["priceToValue"] == pytest.approx(0.632, abs=5e-4)
    assert rows["HGCO"]["designation"] == "well-below"
    assert _tickers(client, "?sort=priceToValue&dir=asc") == ["HGCO", "AAPL", "AAL"]
    assert _tickers(client, "?sort=priceToValue&dir=desc") == ["AAPL", "HGCO", "AAL"]


def test_sort_unknown_key_400(client: TestClient) -> None:
    response = client.get("/api/screen?sort=fair_value")
    assert response.status_code == 400
    assert response.json() == {"detail": "unknown sort column: fair_value"}
    assert client.get("/api/screen?sort=band").status_code == 400  # a column, not a row key
    for gone in ("stance", "stance3", "stance5"):
        assert client.get(f"/api/screen?sort={gone}").status_code == 400, gone
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
        "status": "done",
        "stage": "done",
        "startedAt": "2026-10-31T22:00:00+00:00",
        "finishedAt": "2026-10-31T22:20:00+00:00",
        "message": "3 valued or refused",
        "calibration": CALIBRATION,
    }


def test_screen_envelope_has_today(client: TestClient) -> None:
    """The drawer judges the validity window on the engine's day, never the browser's."""
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
    """HGCO sits at 0.63 × its value and AAPL at 1.125. Under a fair band from 0.6, with the Narrow
    margin of safety at 45% so the edges still ascend, HGCO is no longer below the band."""
    [before] = client.get("/api/groups?by=sector").json()["groups"]
    assert before["shareBelowValue"] == 0.5  # HGCO below 0.85, AAPL not
    safety = {"None": 0.45, "Narrow": 0.45, "Wide": 0.25}
    changes = {"fair_band": [0.6, 1.15], "margin_of_safety": safety}
    assert client.put("/api/settings", json={"changes": changes}, headers=HEADER).status_code == 200
    edges = client.get("/api/companies/AAPL").json()["designationEdges"]
    assert edges == [1 - 0.45, 0.6, 1.15, 1.5]
    [after] = client.get("/api/groups?by=sector").json()["groups"]
    assert after["shareBelowValue"] == 0.0


def test_the_drawer_reads_the_aging_fraction_of_the_settings(client: TestClient) -> None:
    """The drawer's validity window turns aging where the screen's Freshness column does: the
    route serves the effective ``aging_fraction``, a setting that takes effect at once (spec
    2026-11-04 8.2)."""
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
    assert set(row) == set(DESIGN_ROW_KEYS + EXTRA_COLUMNS)
    assert {key: value for key, value in row.items() if value is not None} == {
        "ticker": "NEWC",
        "name": "New Co",
        "overrides": 0,
        "freshness": "current",
        "sector": "Technology",
        "capBand": "mid",
        "marketCap": 3_000_000_000.0,
        "refusal": "not yet valued",
        "watchlists": [],
        "flagCount": 0,
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
    }
    # The policy's edges, by which the drawer keeps its price ÷ value figure inside the band.
    assert body["designationEdges"] == [0.65, 0.85, 1.15, 1.5]
    # The fraction of the window from which the drawer's validity window reads aging.
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
        "/static/controls.js",
        "/static/watchlists.js",
        "/static/settings.js",
        "/static/methodology.js",
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


def test_header_has_the_five_views() -> None:
    js = _static_file("controls.js")
    assert (
        "views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' },\n"
        "        { id: 'watchlists', label: 'Watchlists' }, "
        "{ id: 'methodology', label: 'Methodology' },\n"
        "        { id: 'settings', label: 'Settings' }]"
    ) in js
    assert "location.hash" in js and "history.replaceState" in js
    html = _static_file("index.html")
    for panel in ("watchlists", "methodology", "settings"):
        assert f'<section id="{panel}" hidden' in html


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
    opens the Screen."""
    js = _static_file("controls.js")
    assert "var VIEWS = ['screen', 'groups', 'watchlists', 'methodology', 'settings'];" in js
    show = js[js.index("function show(tab, section) {") :]
    show = show[: show.index("\n  }\n")]
    assert "if (VIEWS.indexOf(tab) === -1) tab = 'screen';" in show
    assert "P.section = tab === 'methodology' && section ? section : null;" in show
    assert "history.replaceState(null, '', tab === 'screen' ? location.pathname" in show
    assert ": '#' + tab + (P.section ? '/' + P.section : ''));" in show
    assert "VIEWS.forEach(function (id) { panels[id].hidden = id !== tab; });" in show
    assert "if (P.onShow[tab]) P.onShow[tab]();" in show
    assert "var parts = location.hash.slice(1).split('/');" in js
    assert "show(parts[0], parts[1]);" in js
    assert "window.addEventListener('hashchange', fromHash);" in js
    # the first view opens once the later scripts have registered their loaders
    assert "document.addEventListener('DOMContentLoaded', fromHash);" in js
    assert "P.show = show;" in js and "P.onShow = {};" in js and "P.section = null;" in js
    assert "P.running = function () { return state.running !== null; };" in js
    # every panel but the Methodology view's, whose examples are figures as of a named date
    assert "VIEWS.forEach(function (id) {\n" in js
    assert "if (id !== 'methodology') panels[id].classList.toggle(RECOMPUTING, alive);" in js
    app = _static_file("app.js")
    assert "find: find" in app  # on window.FairbandPage
    find = app[app.index("function find(symbol) {") :]
    find = find[: find.index("\n  }\n")]
    assert "state.query = symbol;" in find and "state.filters = F.EMPTY_FILTERS;" in find
    assert "window.FairbandPage.show('screen');" in find


def test_index_scrolls_the_new_panels_and_the_header_wraps_at_phone_width() -> None:
    """The three new panels scroll as the groups' does; under 840px, where the one-line header no
    longer fits, the views take a line of their own under the lockup and the header grows by it,
    so the page never scrolls sideways (spec 2026-11-04 6)."""
    page = _static_file("index.html")
    assert "#screen, #groups, #watchlists, #methodology, #settings {" in page
    assert "#groups, #watchlists, #methodology, #settings { overflow: auto; }" in page
    css = _component_file("bundle.css")
    patch = css[css.index("/* fairband: below 840px, where the one-line header") :]
    assert "(spec 2026-11-04 6)" in patch[: patch.index("*/")]
    patch = patch[: patch.index("\n}\n")]
    assert "@media (width < 840px) {" in patch
    assert ".fb-hdr { flex-wrap: wrap; height: auto; row-gap: 0; }" in patch
    assert ".fb-hdr__nav { order: 1; flex-basis: 100%;" in patch
    # B-82: the refresh controls stay beside the lockup at phone width (the stamp gives way below
    # 560px, the buttons shorten below 400px), and the five views wrap below 360px.
    for text in (
        ".app-actions__short { display: none; }",
        "@media (width < 560px) {\n    .fb-hdr__ran { display: none; }",
        (
            "@media (width < 400px) {\n    .app-actions__long { display: none; }\n"
            "    .app-actions__short { display: inline; }"
        ),
        (
            "@media (width < 360px) {\n    .fb-hdr__nav { flex-wrap: wrap; height: auto;"
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
    assert "if (body.refresh !== null) state.detailsOpen = false;" in script
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
    assert "var local = localIso(iso);" in app  # when(): the drawer's observed and entered
    assert "enteredAt: localIso(body.snapshot.createdAt)" in app  # the ValidityWindow
    assert "state.rows = body.rows.map(localRow);" in app  # the table's Entered cell
    assert "{ enteredAt: localIso(r.enteredAt) }" in app
    controls = _static_file("controls.js")
    assert "engineRanAt: ran ? P.localIso(ran) : null" in controls
    assert "P.localIso(last.finishedAt)" in controls  # the last-refresh line


def test_app_js_find_and_filters() -> None:
    script = _static_file("app.js")
    for prop in (
        "query: state.query",
        "onQueryChange:",
        "filters: state.filters",
        "onFiltersChange:",
        "sectors: sectorsOf(state.rows)",
        "total: state.rows.length",
    ):
        assert prop in script, prop
    assert "var rows = narrow(state.rows, state.query, state.filters);" in script
    assert "footnote" not in script


def test_app_js_query_is_trimmed_and_lower_cased() -> None:
    script = _static_file("app.js")
    assert "(query || '').trim().toLowerCase()" in script
    assert "r.ticker.toLowerCase().indexOf(needle) === 0" in script
    assert "(r.name || '').toLowerCase().indexOf(needle) !== -1" in script


def test_app_js_sorts_designation_by_the_ratio() -> None:
    """Spec 7.3: the designation column asks the server for the price-to-value order."""
    script = _static_file("app.js")
    assert (
        "var SORT_KEYS = { band: 'fairLow', designation: 'priceToValue', entered: 'enteredAt' };"
        in script
    )


def test_app_js_narrows_on_the_designation() -> None:
    """The word is the row's, never derived on the page: a row without one (a refusal, a
    placeholder) matches no designation filter, as a row without a cap band matches no cap."""
    script = _static_file("app.js")
    assert "within(filters.designation, r.designation) &&" in script
    assert "(r.capBand || '').toLowerCase()" in script


def test_app_js_narrows_on_watchlist_and_clean() -> None:
    js = _static_file("app.js")
    # Clean keeps the valued rows with no quality warning: a refusal or a placeholder has no
    # value to be cheap on, so it is never clean.
    assert "(!filters.cleanOnly || (r.flagCount === 0 && r.fairValue != null))" in js
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
    assert "chooser: false, dense: true" in js  # each list is a ScreenTable of the screen's rows
    assert "placeholder: 'Add a company'" in js and ".slice(0, 8)" in js
    html = _static_file("index.html")
    assert '<script src="/static/watchlists.js"></script>' in html


def test_watchlists_view_draws_the_screen_rows_and_a_symbol_without_one() -> None:
    """Spec 2026-11-04 9.6: a list's rows are the screen's loaded rows joined by symbol, in the
    list's order, each watched, under the screen's columns; a symbol with no row (it left the
    universe, or has no snapshot) stays, its ticker alone with an em dash in every other cell. A
    row opens the drawer and its mark the screen's popup. The view draws as it opens and again
    whenever the screen draws, so it follows the rows and the lists as they load. Its writes go
    through FairbandPage.api, which gains PATCH and DELETE beside POST and PUT."""
    js = _static_file("watchlists.js")
    assert (
        "{ ticker: symbol, name: null, price: null, mechanical: null, reviewed: null, "
        "phase: null, fairLow: null, fairHigh: null, watched: true }"
    ) in " ".join(js.split())
    for text in (
        "Object.assign({}, row, { watched: true })",
        "columns: P.columns(),",
        "onOpen: function (row) { P.openRow(row.ticker); },",
        "onWatch: P.watch,",
        "P.onShow.watchlists = render;",
        "P.onRender = function () { if (!panel.hidden) render(); };",
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
        "columns: function () { return state.columns; },",
        "openRow: openRow",
        "if (page.onRender) page.onRender();",
    ):
        assert text in app, text
    open_row = app[app.index("function openRow(symbol) {") :]
    open_row = open_row[: open_row.index("\n  }\n")]
    assert "open({ ticker: symbol });" in open_row
    assert "window.FairbandPage.show('screen');" in open_row
    # the lists' tables keep their header cells at the top: no bar stands above them
    page = _static_file("index.html")
    assert "#watchlists .fb-screen { --bar-height: 0px; }" in page


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


def test_the_drawer_window_judges_aging_as_the_screen_does() -> None:
    """ValidityWindow takes ``agingFraction``, 0.6667 by default, and judges its state by the
    server's rule (``validity_state``): on whole days, aging from that fraction of the window,
    expired after its last day. The drawer passes the route's figure, so after a change of
    ``aging_fraction`` a row reads the same in the drawer as in the Freshness column (spec
    2026-11-04 8.2)."""
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
    script = _static_file("app.js")
    assert "validFrom: r.data_date, validUntil: r.valid_until, today: body.today," in script
    assert "agingFraction: body.agingFraction" in script


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
    the header then follows; the view asks FairbandPage.running() while it is open, so the button
    turns off for a run and the notice is read again when the run ends."""
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
        "P.followRefresh();",
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
    assert "P.followRefresh = function () { started = true; poll(); };" in controls
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


def test_app_js_drawer_states_the_ratio_and_the_level_labels() -> None:
    """Spec 7.3: the band meter's caption says the word and the price ÷ value; the levels below
    it read Margin of safety (the value less the moat's margin), Fair band and the trim multiple
    × value, the multiple read from the levels as the margin is, so 1.75 under a setting of 1.75
    and 1.5 at the default; and the meter's own scale, whose words would collide in the rail, is
    off."""
    script = _static_file("app.js")
    assert "buyLevel: r.levels.buy, trimLevel: r.levels.trim, designation: r.designation," in script
    assert "showScale: false, caption: standing(r, body.designationEdges)" in script
    assert "var word = F.DESIGNATION[r.designation];" in script
    assert "if (!word || r.price_to_value == null) return null;" in script
    assert (
        "return word + ': the price is ' + ratioFigure(r.price_to_value, edges) + ' × the value';"
        in script
    )
    assert "var margin = Math.round((1 - r.levels.buy / r.value) * 100);" in script
    assert "['Margin of safety', h(React.Fragment, null, F.formatMoney(r.levels.buy)," in script
    assert "'value less the ' + moat + ' moat\\'s ' + margin + '%'" in script
    assert "['Fair band', F.formatMoney(r.levels.fair_low) + ' – ' +" in script
    assert "var multiple = Number((r.levels.trim / r.value).toFixed(2));" in script
    assert "[multiple + ' × value', F.formatMoney(r.levels.trim), true]" in script
    assert "'1.5 × value'" not in script
    # the route's name, the meter's caption before, keeps a line of its own under the levels
    assert "h('p', { className: 'caption app-muted' }, ROUTES[r.route] || r.route)," in script


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


def test_app_js_words_the_margin_for_no_moat() -> None:
    """The moat class "None" is no moat: its margin reads "value less the 45% margin for no
    moat", not "the None moat's 45%"; a Wide or Narrow moat keeps the moat's own wording."""
    script = _static_file("app.js")
    assert (
        "var basis = moat === 'None' ? 'value less the ' + margin + '% margin for no moat'"
        in script
    )
    assert "moat ? h('span', { className: 'caption app-muted app-line' }, basis) : null" in script
    assert "None moat" not in script


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


def test_app_js_names_the_revenue_route_and_draws_its_tables() -> None:
    script = _static_file("app.js")
    assert "'revenue-growth': 'Revenue growth route'" in script
    for key in (
        "revenue_by_year",
        "margin_path",
        "ebit_by_year",
        "tax_by_year",
        "nopat_by_year",
        "reinvestment_by_year",
        "fcff_by_year",
        "target_margin",
        "largest_margin",
        "sales_to_capital",
        "terminal_roic",
        "terminal_nopat",
        "terminal_value",
        "firm_value",
        "failure_probability",
        "implied_growth",
        "implied_margin",
    ):
        assert key in script, key
    # the terminal value is the fully taxed year-10 NOPAT times the multiple: both lines show
    assert "['Year-10 NOPAT, fully taxed', whole(im.terminal_nopat), true]," in script
    # spec 5.9: the flat required return, read from the row's RULE input, on every row of the
    # route; spec 5.13: a Young Growth row has no range in tier 1
    assert "'Discounted at the required return of ' +" in script
    assert "' in every year; Damodaran\\'s template starts higher and falls to it ' +" in script
    assert "ruleValue(inputs, 'required_return')" in script
    assert "growth ? discountedAt(r.inputs) : null" in script
    assert "The value range is not computed in tier 1" in script
    assert "youngGrowth(im.failure_probability)" in script
    # the solves, and the one figure of a row refused for its target margin
    assert "held ? 'Implied growth held in ' + held : 'Implied growth held after year 3'," in script
    assert "if (last == null) return null;" in script  # no high_growth_years RULE input
    assert "['Margin the price needs', F.formatPercent(im.implied_margin), true]" in script
    assert "'implied_margin' in im ? pairs([" in script
    # a loss makes EPV negative and the growth share above 100%: the EPV line says why
    assert "key === 'epv' && v < 0" in script
    assert "'negative: trailing earnings are a loss'" in script


def test_drawer_figure_tables_scroll_by_keyboard_with_the_year_in_view() -> None:
    script = _static_file("app.js")
    assert script.count("h('div', { className: 'app-scroll', tabIndex: 0 },") == 2
    page = _static_file("index.html")
    assert (
        ".app-scroll:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }"
        in (page)
    )
    assert ".app-figures th:first-child, .app-figures td:first-child {" in page
    assert "position: sticky; left: 0; background: var(--surface-raised);" in page


def test_app_js_escape_closes_an_open_menu_before_the_drawer() -> None:
    """Escape closes an open menu before the drawer, and closes the drawer only while the Screen
    shows it: in another view the drawer is hidden, and Escape belongs to that view's field."""
    script = _static_file("app.js")
    assert "var mount = document.getElementById('screen');" in script
    assert (
        "if (event.key === 'Escape' && state.drawer && !mount.hidden &&\n"
        "        !document.querySelector('.fb-menu')) close();"
    ) in script


def test_app_js_drawer_draws_the_run_off_table() -> None:
    """Spec 10.10: a Decline row's drawer draws the run-off's ten years, a fall in revenue
    releasing capital and a rise reinvesting it, then the terminal; the margin it holds; the
    rating and π; the floor, the distress-sale value and the weighting; Z″ and F. A row refused
    for a value at or below zero keeps its figures without a route, so the drawer reads its
    intermediates."""
    script = _static_file("app.js")
    assert "'decline': 'Decline route'" in script
    assert "'runoff_path' in im ? declineRoute(r) : null," in script
    for text in (
        "'Run-off'",
        "['Release', im.release_by_year, whole],",
        "['Reinvestment', im.reinvestment_by_year, whole],",
        "['Free cash flow', im.fcff_by_year, whole]",
        "['Terminal value', noted(whole(im.terminal_value), 'flat'), true],",
        "rows.push(['Implied decline rate', im.implied_decline_rate == null",
        "'Normalized margin'",
        "'Rating'",
        "'no net debt'",
        # no rating says why: no debt line on file, or no interest expense on file
        "['Rating', 'unavailable: ' + (g.note || 'no interest expense on file'), false],",
        "'π, ten-year default probability'",
        "'Floor and distress'",
        "'Going concern a share'",
        "'NCAV a share'",
        "var floor = ncav == null || ncav <= 0 ? 'no floor'",
        ": im.floored_per_share > im.going_concern_per_share ? 'the floor binds'",
        ": 'the floor does not bind';",
        "'Distress-sale value a share'",
        "'value = floored × (1 − π) + distress × π'",
        "'Altman Z″'",
        "'Piotroski F'",
        "var mark = s.value === true ? 'met' : s.value === false ? 'not met' : 'not read';",
        "h('span', { className: 'caption app-mark' }, mark),",
    ):
        assert text in script, text
    # each signal's outcome in words, in a box so the signals line up: no dingbat the vendored
    # Plex subset lacks, and nothing like the × that means expired (the brand book's glyph rules)
    assert "✓" not in script and "✗" not in script
    page = _static_file("index.html")
    assert ".app-signals li { display: flex; align-items: baseline; }" in page
    assert ".app-mark { flex: none; min-width: 8ch; }" in page
    for key in (
        "going_concern_per_share",
        "ncav_per_share",
        "floored_per_share",
        "distress_per_share",
        "altman_z",
        "piotroski_f",
        "implied_decline_rate",
    ):
        assert key in script, key


def test_app_js_drawer_says_the_fade_the_ramp_and_the_stable_cross_check() -> None:
    """Spec 2026-11-06 12: the run-off's decline rate names the years the consensus gives, K, or the
    three years on trend, and the fade to zero by year N, or, when the consensus reaches year N - 1
    or N and no year reads the rate, where the consensus ends, and at N - 1 that year N is flat; its
    terminal is flat (6.4); a growth row on the dollar ramp says so over its margins (7.2); a Mature
    Stable row refused for its trailing earnings shows the growth-route cross-check under the
    refusal, as a valued row shows it under the band (9). A revenue-growth refusal's cross-check
    does not move with the price, so it shows only among the intermediates."""
    script = _static_file("app.js")
    summary = script[script.index("function runoffSummary(") :]
    summary = summary[: summary.index("\n  }\n")]
    for text in (
        "var years = path.ntm_revenue == null ? 'years 1 to 3 at the decline rate'",
        ": 'years 1 to ' + path.consensus_years + ' from the consensus';",
        "var fade = path.consensus_years < path.runoff_years - 1",
        "? years + '; fades to zero by year ' + path.runoff_years",
        # at K = N - 1 the one fade year, N, is at zero: no year reads the rate (final review)
        ": path.consensus_years < path.runoff_years",
        "? 'the consensus runs to year ' + path.consensus_years + '; year ' + path.runoff_years",
        "+ ' is flat'",
        # no year reads the rate when the consensus reaches year N (review of task 7)
        ": 'the consensus runs to year ' + path.runoff_years;",
        "['Decline rate', noted(F.formatPercent(path.d), fade), true],",
        "['Terminal value', noted(whole(im.terminal_value), 'flat'), true],",
    ):
        assert text in summary, text
    assert "from year 4" not in summary and "every year: no usable consensus" not in summary
    years = script[script.index("function yearsTable(") :]
    years = years[: years.index("\n  }\n")]
    assert "var ramp = im.margin_path.ramp === 'dollars' ? 'ramp in dollars' : null;" in years
    assert "['Margin', im.margin_path.by_year, F.formatPercent, ramp]," in years
    assert "c[3] ? noted(c[0], c[3]) : c[0]" in script
    refusal = script[script.index("r.refusal ? section('refusal', 'Refusal',") :]
    refusal = refusal[: refusal.index("section('window'")]
    assert "'e_trailing' in im ? crossCheck(im.growth_route) : null" in refusal
    assert script.count("crossCheck(im.growth_route)") == 2


def test_app_js_drawer_draws_the_requirement() -> None:
    """Spec 9.2 and 9.4: a Start-up row's drawer, under its refusal, states the revenue its price
    needs in year 10 (a multiple of the trailing revenue when there is one), the target margin
    and the ramp behind it, the cash floor and the burn cover. A repriced row's market cap moved
    with the price from the one its input read: both show. The caption under the cash floor reads
    the row's ``below-net-cash`` flag, the one test (method 6b.4), never the price against the
    cash floor; a burn without a cash figure has no cover."""
    script = _static_file("app.js")
    assert "'start-up': 'Start-up route'" in script
    assert "'requirement' in im ? startUpRoute(r) : null," in script
    for text in (
        "'Revenue the price needs'",
        "if (!req.reason && req.revenue_0 > 0) {",
        "' × the trailing revenue'",
        "'Cash floor'",
        "'Net cash a share'",
        "'Burn cover'",
        "if (cover === 'not burning')",
        "var read = dataValue(inputs, 'market_cap');",
        "'The market cap moved with the price: '",
        "var below = r.flags.some(function (f) { return f.code === 'below-net-cash'; });",
        "'The price is covered by net cash: the market cap is at or below the cash less the debt'",
        "if (cover == null && im.burn != null && im.cash_known === false) {",
        "['Cash covers', 'unknown: no cash line on file', false],",
    ):
        assert text in script, text
    assert "r.price >= floor" not in script and "is below the net cash a share" not in script


# The columns the repository's bundle adds to ScreenTable, each a row key, with its head.
EXTRA_COLUMN_HEADS = {
    "sector": "Sector",
    "capBand": "Cap",
    "marketCap": "Market cap",
    "moat": "Moat",
    "impliedGrowth": "Implied growth",
    "expectedReturn": "Expected return",
    "epv": "EPV",
    "peReported": "P/E",
    "peClean": "Clean P/E",
    "peForward": "Forward P/E",
    "high52w": "52w high",
    "low52w": "52w low",
    "change1y": "1y",
    "change3y": "3y",
    "change5y": "5y",
    "drawdown": "Drawdown",
    "flags": "Flags",
    "refusal": "Refusal",
    "priceDate": "Price date",
    "dataDate": "Data date",
    "validUntil": "Valid until",
    "growthRouteValue": "Growth-route value",
    "targetMargin": "Target margin",
    "impliedMargin": "Implied margin",
}


def test_bundle_has_extra_columns() -> None:
    bundle = _component_file("bundle.js")
    assert set(EXTRA_COLUMN_HEADS) <= set(EXTRA_KEYS)  # the API sends each one
    for key, head in EXTRA_COLUMN_HEADS.items():
        assert f"{{ key: '{key}', head: '{head}'," in bundle, key


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
    assert "var FILTER_GROUPS = ['designation', 'phase', 'cap', 'sector', 'watchlist'];" in bundle
    assert "var EMPTY_FILTERS = { designation: [], phase: [], cap: [], sector: []," in bundle
    assert "p.onFiltersChange({ designation: [], phase: [], cap: [], sector: []," in bundle
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
    assert "watchlist: [], reviewedOnly: false, hideExpired: false, cleanOnly: false" in bundle
    assert "'WATCHLISTS'" in bundle and "'No warning flag'" in bundle
    assert "{ key: 'flagCount', head: 'Warnings', num: true" in bundle
    assert "{ key: 'watchlists', head: 'Watchlists'" in bundle
    dts = _component_file("index.d.ts")
    assert "onWatch?: (row: ScreenRow) => void;" in dts and "cleanOnly: boolean;" in dts


def test_bundle_draws_the_mark_only_given_onWatch() -> None:
    """Spec 2026-11-04 9.4: the mark is a button at the left of the Ticker cell, named for its
    ticker, filled when the company is on a list; Enter and Space on it never open the row; a
    table without onWatch draws none. The cells see the props, for the mark and the list names."""
    bundle = _component_file("bundle.js")
    assert "p.onWatch ? h('button', {" in bundle
    assert "className: cx('fb-watch control', r.watched && 'fb-watch--on')," in bundle
    assert "'aria-label': 'Watchlists for ' + r.ticker," in bundle
    assert "if (e.key === 'Enter' || e.key === ' ') e.stopPropagation();" in bundle
    assert "}, r.watched ? '▶' : '▸') : null," in bundle
    assert "return h(React.Fragment, { key: c.key }, c.cell(r, p));" in bundle
    css = _component_file("bundle.css")
    assert ".fb-watch--on { color: var(--accent); }" in css
    ring = "outline: 2px solid var(--focus-ring); outline-offset: 2px;"
    assert f".fb-watch:focus-visible {{ {ring} }}" in css


def test_bundle_filters_on_watchlists_and_clean() -> None:
    """Spec 2026-11-04 9.4 and 9.5: WATCHLISTS follows SECTOR in the menu, one row per list by
    name; the clean row stands in VALUE as "No warning flag" and its chip reads Clean; a chosen
    list's chip is its name, more than two their count; Clear all empties both."""
    bundle = _component_file("bundle.js")
    assert "var FILTER_FLAGS = ['reviewedOnly', 'hideExpired', 'cleanOnly'];" in bundle
    assert "cleanOnly: 'Clean'" in bundle
    assert bundle.index("'SECTOR'") < bundle.index("'WATCHLISTS'") < bundle.index("'VALUE'")
    assert "function () { toggleIn('watchlist', w.id); }," in bundle
    assert "h('span', null, FLAG_ROWS[k] || FLAG_WORDS[k])" in bundle
    assert "var chips = summarise(p.filters, lists);" in bundle
    assert "word: n <= 2 && names.length === n" in bundle
    assert "n + (n === 1 ? ' watchlist' : ' watchlists')" in bundle
    clear = bundle[bundle.index("function clearAll() {") : bundle.index("function checkRow")]
    assert "watchlist: [], reviewedOnly: false, hideExpired: false, cleanOnly: false });" in clear


def test_bundle_draws_the_watchlist_and_count_columns() -> None:
    """Spec 2026-11-04 9.4: the list names joined by ` · `, an em dash for none; the count of
    the quality warnings after the flags' words, a figure headed Warnings (the controller's
    ruling), so no two columns share a name."""
    bundle = _component_file("bundle.js")
    assert "return wordCell(names.length ? names.join(' · ') : null);" in bundle
    assert bundle.index("{ key: 'flags', head: 'Flags'") < bundle.index("{ key: 'flagCount'")
    # every column has a head of its own, so the chooser never offers two boxes with one name
    heads = re.findall(r"\{ key: '\w+', head: '([^']+)'", bundle)
    assert len(heads) == len(set(heads))
    assert "return figureCell(r.flagCount == null ? '—' : r.flagCount);" in bundle


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
    assert "Hold'" not in bundle and "STANCE" not in bundle  # never "Hold"
    css = _component_file("bundle.css")
    rule = re.search(r"\.fb-designation \{(.*?)\}", css, re.DOTALL)
    assert rule is not None
    assert "text-transform: uppercase;" in rule.group(1)
    assert "border: 1px solid currentColor;" in rule.group(1)
    assert "color:" not in rule.group(1)  # the band's modifier sets the colour
    assert ".fb-stance" not in css
    # the stance tokens stay for the delta and the recommendation's effect; the spread chart's
    # label takes the delta's classes in place of the stance chip's
    assert ".fb-delta--up { color: var(--stance-buy); }" in css
    assert ".fb-rec__effect { font-weight: 500; color: var(--stance-buy); }" in css
    assert "cur.roic >= cur.wacc ? 'fb-delta--up' : 'fb-delta--down'" in bundle


def test_no_stance_word_remains() -> None:
    """Spec 7.2: the engine gives no stance, and the page derives none, names none and declares
    none. Only the CSS keeps the --stance-* tokens, for the delta's colours."""
    for name, text in (
        ("app.js", _static_file("app.js")),
        ("controls.js", _static_file("controls.js")),
        ("bundle.js", _component_file("bundle.js")),
        ("index.d.ts", _component_file("index.d.ts")),
    ):
        for gone in ("stanceOf", "STANCE[", "Five-step", "stance5", "stance3"):
            assert gone not in text, (name, gone)
        if name == "app.js":
            # The one mention: a column list saved under method 0.5 carries the old key, which
            # normalise maps to the designation's.
            legacy = "key === 'stance' ? 'designation' : key"
            assert text.count(legacy) == 1
            text = text.replace(legacy, "")
        assert re.search(r"\bstance", text, re.IGNORECASE) is None, name


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
        .read_text()
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
        .read_text()
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
    """Columns ▾ lists all 46 columns, taller than a 900px window: a menu of the screen's bar
    stops 12rem short of the window's height and scrolls, so the last rows, the Warnings column
    among them, can be reached (spec 2026-11-04 9.4)."""
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
    space below is padding, so no row shows between the bar and the header. The groups' and the
    drawer's tables keep their header at the top."""
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
    for key in ("watched?: boolean;", "watchlists?: number[];", "flagCount?: number;"):
        assert key in row.group(1), key
    filters = re.search(r"export interface ScreenFilters \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert filters is not None
    assert "watchlist: number[];" in filters.group(1)
    assert "cleanOnly: boolean;" in filters.group(1)
    props = re.search(r"export interface ScreenTableProps \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert props is not None
    assert "onWatch?: (row: ScreenRow) => void;" in props.group(1)
    assert "watchlists?: { id: number; name: string }[];" in props.group(1)


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
        assert applied_versions(conn) == [1, 2, 3, 4, 5, 6]
    with TestClient(app, base_url=HOST) as c:
        body = c.get("/api/screen").json()
    assert body["rows"] == [] and body["refresh"] is None
