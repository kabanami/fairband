"""The web app through its routes, on a temporary migrated database with three snapshots from the
engine's test companies: AAPL, valued on the Mature Growth route; AAL, a Young Growth company with
no mature peers, which the engine refuses for its target margin; and HGCO, the High Growth company,
valued on the revenue growth route. All three are listed in the universe of one finished full
refresh."""

import json
import re
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient
from support.engine_companies import (
    annual,
    high_growth_inputs,
    mature_growth_inputs,
    mature_stable_inputs,
    universe_deciles,
    young_growth_inputs,
)

from fairband import __main__ as cli
from fairband.config import DEFAULT_PORT, Settings
from fairband.engine import METHOD_VERSION
from fairband.engine.route import value_company
from fairband.engine.types import ValuationResult, result_to_json
from fairband.policy import Policy, load_policy
from fairband.store.companies import CompanyRow, insert_companies
from fairband.store.db import applied_versions, connect, migrate
from fairband.store.refreshes import create_refresh, finish_refresh, set_stage
from fairband.store.snapshots import insert_snapshot
from fairband.web.app import create_app
from fairband.web.rows import EXTRA_KEYS

TODAY = date(2026, 10, 31)  # the day the engine's test companies are valued
STARTED = datetime(2026, 10, 31, 22, 0, tzinfo=UTC)
CREATED = datetime(2026, 10, 31, 22, 15, tzinfo=UTC)
FINISHED = datetime(2026, 10, 31, 22, 20, tzinfo=UTC)
NOW = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
CALIBRATION = {"refused": 1, "valued": 2}
HOST = "http://127.0.0.1:8470"  # a host the app trusts (D11)

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
    "stance",
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
    "refusal",
    "stance3",
    "stance5",
    "priceDate",
    "dataDate",
    "validUntil",
    "route",
    "growthRouteValue",
    "targetMargin",
    "impliedMargin",
]


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


def _company(symbol: str, refresh_id: int, name: str, market_cap: Decimal) -> CompanyRow:
    return CompanyRow(
        symbol=symbol,
        refresh_id=refresh_id,
        name=name,
        exchange="NASDAQ",
        sector="Technology",
        industry="Software - Application",
        country="US",
        currency="USD",
        is_adr=False,
        cap_band="mega" if market_cap >= 100_000_000_000 else "mid",
        market_cap=market_cap,
        eligible=True,
        exclusion_reason=None,
        observed_at=STARTED,
    )


@pytest.fixture
def db_path(tmp_path: Path, policy: Policy, results: dict[str, ValuationResult]) -> Path:
    path = tmp_path / "data" / "fairband.db"
    with closing(connect(path)) as conn:
        migrate(conn)
        refresh_id = create_refresh(conn, "full", None, policy.version, METHOD_VERSION, STARTED)
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


def _settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings(
        data_dir=db_path.parent, config_dir=tmp_path / "config", db_path=db_path, port=DEFAULT_PORT
    )


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
        "stance3": "hold",
        "stance5": "HOLD",  # $150 within the $113.36 to $153.37 fair band
        "priceDate": "2026-10-30",
        "dataDate": "2026-10-30",
        "validUntil": "2027-01-28",
        "route": "mature-growth",
        "growthRouteValue": valued.value,
        "targetMargin": None,
        "impliedMargin": None,
    }

    refused = results["AAL"]
    assert set(aal) == set(aapl)
    assert aal["phase"] == 2 and aal["name"] == "Young Growth Co"
    assert aal["refusal"] == refused.refusal == "no target margin: 0 mature peers"
    for key in ("fairLow", "fairHigh", "fairValue", "buyLevel", "trimLevel", "mechanical"):
        assert aal[key] is None, key
    for key in ("impliedGrowth", "expectedReturn", "epv", "peClean", "stance3", "route"):
        assert aal[key] is None, key
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


def test_sort_unknown_key_400(client: TestClient) -> None:
    response = client.get("/api/screen?sort=fair_value")
    assert response.status_code == 400
    assert response.json() == {"detail": "unknown sort column: fair_value"}
    assert client.get("/api/screen?sort=band").status_code == 400  # a column, not a row key
    response = client.get("/api/screen?sort=ticker&dir=down")
    assert response.status_code == 400
    assert response.json() == {"detail": "dir must be asc or desc, not down"}


def test_screen_envelope_columns_and_today(client: TestClient) -> None:
    body = _screen(client)
    assert set(body) == {"rows", "columns", "today", "refresh"}
    assert body["columns"] == DESIGN_COLUMNS + EXTRA_COLUMNS
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


def _universe(db_path: Path, policy: Policy, *companies: tuple[str, str, int, bool]) -> None:
    """A later full refresh whose universe lists ``companies``: symbol, name, market cap and
    whether it is admitted."""
    with closing(connect(db_path)) as conn:
        refresh_id = create_refresh(conn, "full", None, policy.version, METHOD_VERSION, NOW)
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
            conn, "scoped", symbols, policy.version, METHOD_VERSION, STARTED
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
    assert set(body) == {"company", "snapshot", "result", "today"}
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
    ]
    for url in references.urls:
        assert client.get(url).status_code == 200, url
    fonts = re.findall(r'url\("\./([^"]+)"\)', client.get(references.urls[1]).text)
    assert len(fonts) == 6
    for font in fonts:
        assert client.get(f"/static/design-system/fonts/{font}").status_code == 200, font


def _component_file(name: str) -> str:
    """A file of the repository's design-system copy, as text."""
    components = resources.files("fairband.web").joinpath("static", "design-system", "components")
    return components.joinpath(name).read_text(encoding="utf-8")


def _static_file(name: str) -> str:
    """A file of the page's own static directory, as text."""
    return resources.files("fairband.web").joinpath("static", name).read_text(encoding="utf-8")


def test_index_mounts_the_header_and_the_favicon(client: TestClient) -> None:
    page = client.get("/").text
    assert "<h1" not in page and 'role="tab"' not in page
    assert 'id="header"' in page
    assert '<link rel="icon" href="/static/design-system/assets/Logos/mark-on-dark.svg"' in page


def test_controls_js_mounts_app_header() -> None:
    script = _static_file("controls.js")
    assert "h(F.AppHeader, {" in script
    assert "views: [{ id: 'screen', label: 'Screen' }, { id: 'groups', label: 'Groups' }]" in script
    assert "engineRanAt:" in script and "onViewChange: show" in script


def test_controls_js_run_bar() -> None:
    script = _static_file("controls.js")
    assert "h(F.RunProgress, runProps(state.running))" in script
    for stage, word in (
        ("universe", "reading the universe"),
        ("deciles", "ranking"),
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


def test_app_js_filter_rule_handles_missing_fields() -> None:
    script = _static_file("app.js")
    assert "(r.capBand || '').toLowerCase()" in script
    assert (
        "if (r.price == null || r.buyLevel == null || r.trimLevel == null) return null;" in script
    )


def test_app_js_normalises_a_saved_column_list() -> None:
    script = _static_file("app.js")
    assert "function normalise(columns)" in script
    assert "F.COLUMN_KEYS" in script
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
    script = _static_file("app.js")
    assert "event.key === 'Escape' && state.drawer && !document.querySelector('.fb-menu')" in script


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
        "stance",
    ]


def test_bundle_has_the_margin_columns() -> None:
    """The two margins of the growth routes, percentages as the other fractions are, after the
    growth-route value in the catalog."""
    bundle = _component_file("bundle.js")
    assert "key: 'targetMargin'" in bundle and "key: 'impliedMargin'" in bundle
    assert "figureCell(percent(r.targetMargin))" in bundle
    assert "figureCell(percent(r.impliedMargin))" in bundle
    order = [bundle.index(f"key: '{key}'") for key in EXTRA_KEYS[-3:]]
    assert EXTRA_KEYS[-3:] == ("growthRouteValue", "targetMargin", "impliedMargin")
    assert order == sorted(order)


def test_bundle_patches_marked() -> None:
    """The repository's patches to the exported bundle each carry a ``// fairband:`` comment, so
    a later export can be diffed against them."""
    bundle = _component_file("bundle.js")
    assert bundle.count("// fairband:") >= 27
    # A menu's toggle says whether its menu is open: Button passes aria-expanded through.
    assert "'aria-expanded': p['aria-expanded']," in bundle
    # A null phase has no badge: an em dash, never phase 1 "Start-up".
    assert "Number(p.phase) || 1" not in bundle
    assert "if (p.phase == null) return h('span', { className: 'fb-screen__none' }, '—');" in bundle
    # A row without levels has no stance: an em dash, never "Hold".
    assert "if (r.price == null || r.buyLevel == null || r.trimLevel == null) {" in bundle
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
    assert "onClick: function () { p.onQueryChange(''); }" in bundle
    css = _component_file("bundle.css")
    assert (
        ".fb-screen__clear:focus-visible { outline: 2px solid var(--focus-ring); outline-offset: 2px; }"
        in (css)
    )


def test_index_gives_the_find_ring_room() -> None:
    page = _static_file("index.html")
    assert "/* fairband:" in page and ".app-main { padding-top: var(--space-1); }" in page


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


def test_index_d_ts_declares_the_margin_keys() -> None:
    declarations = _component_file("index.d.ts")
    row = re.search(r"export interface ScreenRow \{\n(.*?)\n\}", declarations, re.DOTALL)
    assert row is not None
    assert "targetMargin?: number | null;" in row.group(1)
    assert "impliedMargin?: number | null;" in row.group(1)


def test_each_request_closes_its_connection(tmp_path: Path, db_path: Path, policy: Policy) -> None:
    opened: list[sqlite3.Connection] = []

    def conn_factory() -> sqlite3.Connection:
        opened.append(connect(db_path))
        return opened[-1]

    app = create_app(_settings(tmp_path, db_path), policy, conn_factory, clock=lambda: NOW)
    with TestClient(app, base_url=HOST) as c:
        for path in ("/api/screen", "/api/companies/AAPL", "/api/companies/NOPE", "/"):
            c.get(path)
    assert len(opened) == 4  # the startup's, which marks the refreshes left running, and three

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
        assert applied_versions(conn) == [1]
    with TestClient(app, base_url=HOST) as c:
        body = c.get("/api/screen").json()
    assert body["rows"] == [] and body["refresh"] is None
