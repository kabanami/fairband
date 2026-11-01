"""The web app through its routes, on a temporary migrated database with two snapshots from the
engine's test companies: AAPL, valued on the Mature Growth route, and AAL, a Young Growth company
the engine refuses. Both are listed in the universe of one finished full refresh."""

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
CALIBRATION = {"refused": 1, "valued": 1}
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
]


@pytest.fixture
def policy() -> Policy:
    return load_policy()


@pytest.fixture
def results(policy: Policy) -> dict[str, ValuationResult]:
    deciles = universe_deciles()
    valued = value_company(replace(mature_growth_inputs(), symbol="AAPL"), deciles, policy, TODAY)
    refused = value_company(replace(young_growth_inputs(), symbol="AAL"), deciles, policy, TODAY)
    assert valued.value is not None and refused.value is None
    return {"AAPL": valued, "AAL": refused}


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
            ],
        )
        for result in results.values():
            insert_snapshot(conn, result, refresh_id, clock=lambda: CREATED)
        set_stage(conn, refresh_id, "done")
        finish_refresh(conn, refresh_id, "done", FINISHED, "2 valued or refused", CALIBRATION)
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
    assert [row["ticker"] for row in rows] == ["AAL", "AAPL"]
    aal, aapl = rows

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
    }

    refused = results["AAL"]
    assert set(aal) == set(aapl)
    assert aal["phase"] == 2 and aal["name"] == "Young Growth Co"
    assert aal["refusal"] == refused.refusal == "Young Growth route not built yet"
    for key in ("fairLow", "fairHigh", "fairValue", "buyLevel", "trimLevel", "mechanical"):
        assert aal[key] is None, key
    for key in ("moat", "impliedGrowth", "expectedReturn", "epv", "peClean", "stance3", "route"):
        assert aal[key] is None, key
    assert aal["reviewed"] is None and aal["overrides"] == 0
    assert aal["price"] == 150.0
    assert aal["high52w"] == refused.intermediates["price_facts"]["high_52w"]
    assert aal["flags"] == [f.word for f in refused.flags]


def test_screen_sort_nulls_last(client: TestClient) -> None:
    assert _tickers(client, "?sort=fairValue&dir=desc") == ["AAPL", "AAL"]
    assert _tickers(client, "?sort=fairValue&dir=asc") == ["AAPL", "AAL"]
    assert _tickers(client, "?sort=phase&dir=asc") == ["AAL", "AAPL"]
    assert _tickers(client, "?sort=phase&dir=desc") == ["AAPL", "AAL"]
    assert _tickers(client, "?sort=marketCap&dir=desc") == ["AAPL", "AAL"]
    assert _tickers(client, "?sort=ticker&dir=desc") == ["AAPL", "AAL"]
    assert _tickers(client, "?sort=marketCap") == ["AAL", "AAPL"]  # ascending by default
    for key in _screen(client)["rows"][0]:
        for direction in ("asc", "desc"):
            assert len(_tickers(client, f"?sort={key}&dir={direction}")) == 2, key


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
        "message": "2 valued or refused",
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
    assert [row["freshness"] for row in body["rows"]] == [state, state]


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


def test_screen_keeps_the_universe_when_a_refresh_admits_none(
    db_path: Path, policy: Policy, client: TestClient
) -> None:
    """A later full refresh whose screener admitted nobody recorded only an excluded listing: the
    screen keeps the last universe that admitted companies."""
    _universe(db_path, policy, ("FIRB", "First Bank", 4_000_000_000, False))
    assert _tickers(client, "") == ["AAL", "AAPL"]


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
        ("AAL", None, "Young Growth route not built yet"),
        ("AAPL", None, None),
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
    fonts = re.findall(r'url\("\./([^"]+)"\)', client.get(references.urls[0]).text)
    assert len(fonts) == 6
    for font in fonts:
        assert client.get(f"/static/design-system/fonts/{font}").status_code == 200, font


def _component_file(name: str) -> str:
    """A file of the repository's design-system copy, as text."""
    components = resources.files("fairband.web").joinpath("static", "design-system", "components")
    return components.joinpath(name).read_text(encoding="utf-8")


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


def test_bundle_patches_marked() -> None:
    """The repository's patches to the exported bundle each carry a ``// fairband:`` comment, so
    a later export can be diffed against them."""
    bundle = _component_file("bundle.js")
    assert bundle.count("// fairband:") >= 5
    # A null phase has no badge: an em dash, never phase 1 "Start-up".
    assert "Number(p.phase) || 1" not in bundle
    assert "if (p.phase == null) return h('span', { className: 'fb-screen__none' }, '—');" in bundle
    # A row without levels has no stance: an em dash, never "Hold".
    assert "if (r.price == null || r.buyLevel == null || r.trimLevel == null) {" in bundle
    # A timestamp reads as its date; the full ISO stays in the datetime attribute.
    assert "if (rest.charAt(0) === 'T') rest = '';" in bundle
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
