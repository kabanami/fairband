"""The company reads and the Methodology section read (spec 2026-11-06 Tier 2, 13.5, 15.2 and 16)
on the database of ``conftest.py``: AAPL, AAL and HGCO, each with one snapshot. Here AAPL and
HGCO also get the refresh tests' synthetic statements (``refresh/synthetic.py``: calendar fiscal
years 2014 to 2025, revenue $1,000 m in 2014 up $100 m a year at a 20% operating margin, and
five quarters to 2026-09-30); AAPL gets the synthetic quarterly consensus, two years of annual
consensus, four closes and a peers list naming HGCO and AAL; and the store gets the deciles of
the engine's test universe, under which HGCO's statements classify as Mature Growth. The
multiples history's tests give AAPL a synthetic GuruFocus P/E series and multiples log rows of
their own."""

from collections.abc import Callable, Iterator
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from refresh.synthetic import bodies, estimates_quarter
from support.engine_companies import universe_deciles
from support.payloads import store_payloads
from support.web import CREATED, HEADER, HOST, NOW, _settings

from fairband.engine.anchor import TrailingFigures
from fairband.engine.balance import BalanceYear
from fairband.engine.classifier import FiscalYear
from fairband.policy import Policy
from fairband.refresh.passthrough import Passthrough
from fairband.reports.refs import Resolver
from fairband.reports.tables import LINES, TABLES
from fairband.store.db import connect
from fairband.store.multiples import log_multiples
from fairband.store.refreshes import save_deciles
from fairband.store.vendor import latest_response
from fairband.vendors import fmp as fmp_api
from fairband.vendors import gurufocus as gurufocus_api
from fairband.vendors.fmp import Fmp
from fairband.vendors.gurufocus import GuruFocus
from fairband.vendors.http import VendorHttp
from fairband.web.app import create_app

M = 1_000_000
ANNUAL = [  # FMP's order: the furthest year first
    {
        "symbol": "AAPL",
        "date": "2027-12-31",
        "revenueAvg": 2_420_000_000,
        "netIncomeAvg": 363_000_000,
        "epsAvg": 3.63,
        "numAnalystsEps": 8,
        "numAnalystsRevenue": 10,
    },
    {
        "symbol": "AAPL",
        "date": "2026-12-31",
        "revenueAvg": 2_200_000_000,
        "netIncomeAvg": 330_000_000,
        "epsAvg": 3.3,
        "numAnalystsEps": 9,
        "numAnalystsRevenue": 12,
    },
]
CLOSES = [  # newest first, as FMP sends them
    {"symbol": "AAPL", "date": "2026-10-30", "close": 150.0},
    {"symbol": "AAPL", "date": "2025-11-03", "close": 190.0},
    {"symbol": "AAPL", "date": "2024-06-28", "close": 180.0},
    {"symbol": "AAPL", "date": "2021-11-01", "close": 140.0},
]
PEERS = [{"symbol": "HGCO"}, {"symbol": "AAL"}, {"symbol": "AAPL"}]


@pytest.fixture(autouse=True)
def stored(db_path: Path) -> None:
    statements = {e: p for e, p in bodies().items() if e != "earnings"}
    reads = {
        "estimates-quarter": estimates_quarter(),
        "estimates-annual": ANNUAL,
        "price-history": CLOSES,
        "peers": PEERS,
    }
    with closing(connect(db_path)) as conn:
        store_payloads(conn, "AAPL", statements | reads, CREATED)
        store_payloads(conn, "HGCO", statements, CREATED)
        save_deciles(conn, 1, universe_deciles(), CREATED)


def _get(client: TestClient, url: str) -> Any:
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()


def _figure(value: float | None, unit: str, ref: str) -> dict[str, Any]:
    return {"value": value, "unit": unit, "ref": ref}


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def test_financials(client: TestClient) -> None:
    body = _get(client, "/api/companies/aapl/financials")
    assert (body["symbol"], body["currency"]) == ("AAPL", "USD")
    series, balance = body["series"], body["balanceYears"]
    assert [y["year"] for y in series] == list(range(2015, 2026))
    assert [y["year"] for y in balance] == list(range(2015, 2026))
    newest = series[-1]
    assert (newest["periodEnd"], newest["currency"]) == ("2025-12-31", "USD")
    assert newest["revenue"] == _figure(2100 * M, "currency", "fact:AAPL/revenue/2025")
    assert balance[-1]["totalAssets"] == _figure(
        1610 * M, "currency", "fact:AAPL/total_assets/2025"
    )
    trailing = body["trailing"]
    assert (trailing["periodEnd"], trailing["quarters"], trailing["onFiscalYear"]) == (
        "2026-09-30",
        4,
        False,
    )
    # the last four quarters: revenue $310 m to $340 m; EPS 0.46 to 0.49 a share
    assert trailing["revenue"] == _figure(1300 * M, "currency", "fact:AAPL/revenue/ttm")
    assert trailing["epsDiluted"]["unit"] == "per-share"
    assert trailing["epsDiluted"]["value"] == pytest.approx(1.90)
    # every figure, by the engine's field names, with its ref; a fiscal year's line is one of
    # the tables' lines, so one reading resolves both
    for fields, rows, period in (
        (FiscalYear, series, None),
        (BalanceYear, balance, None),
        (TrailingFigures, [trailing], "ttm"),
    ):
        plain = {"year", "period_end", "currency", "quarters", "on_fiscal_year"}
        names = [f for f in fields.__dataclass_fields__ if f not in plain]
        for row in rows:
            for name in names:
                at = period or str(row["year"])
                assert row[_camel(name)]["ref"] == f"fact:AAPL/{name}/{at}"
                assert period == "ttm" or name in LINES


def test_financials_without_statements(client: TestClient) -> None:
    r = client.get("/api/companies/AAL/financials")
    assert r.status_code == 404 and r.json()["detail"] == "no financial statements for AAL"
    r = client.get("/api/companies/not%20one/financials")
    assert r.status_code == 400 and r.json()["detail"] == "'not one' is not a symbol"


def test_financial_tables(client: TestClient) -> None:
    body = _get(client, "/api/companies/AAPL/financial-tables")
    assert (body["symbol"], body["currency"]) == ("AAPL", "USD")
    assert [t["name"] for t in body["tables"]] == list(TABLES)
    growth = body["tables"][0]["rows"]
    assert [r["name"] for r in growth][:2] == ["revenue", "revenue_growth"]
    cell = growth[1]["cells"][-1]
    assert cell == {
        "period": "2025",
        "value": pytest.approx(0.05),
        "unit": "percent",
        "ref": "table:AAPL/growth/revenue_growth/2025",
        "note": None,
    }
    assert client.get("/api/companies/AAL/financial-tables").status_code == 404


def test_estimates(client: TestClient) -> None:
    body = _get(client, "/api/companies/AAPL/estimates")
    quarters, annual = body["quarters"], body["annual"]
    # the synthetic consensus: quarter i ends 2026-12-31 onwards, EPS 0.52 + 0.02 × i
    assert [q["period"] for q in quarters] == ["2026-Q4", "2027-Q1", "2027-Q2", "2027-Q3"]
    first = quarters[0]
    assert (first["periodEnd"], first["fiscalYear"], first["fiscalPeriod"]) == (
        "2026-12-31",
        2026,
        "Q4",
    )
    assert first["eps"] == _figure(0.52, "per-share", "estimate:AAPL/2026-Q4/eps")
    assert first["netIncome"] == _figure(52 * M, "currency", "estimate:AAPL/2026-Q4/net_income")
    assert first["analysts"] == _figure(11, "count", "estimate:AAPL/2026-Q4/analysts")
    assert [a["period"] for a in annual] == ["2026", "2027"]
    assert annual[0]["eps"] == _figure(3.3, "per-share", "estimate:AAPL/2026/eps")
    assert annual[0]["analystsRevenue"] == _figure(
        12, "count", "estimate:AAPL/2026/analysts_revenue"
    )
    assert _get(client, "/api/companies/AAL/estimates") == {
        "symbol": "AAL",
        "quarters": [],
        "annual": [],
    }


def test_price_history(client: TestClient) -> None:
    body = _get(client, "/api/companies/AAPL/price-history")
    closes = body["closes"]
    assert [c["date"] for c in closes] == ["2021-11-01", "2024-06-28", "2025-11-03", "2026-10-30"]
    assert closes[-1]["close"] == _figure(150.0, "per-share", "close:AAPL/2026-10-30")
    # a year back from the newest close
    year = _get(client, "/api/companies/AAPL/price-history?years=1")["closes"]
    assert [c["date"] for c in year] == ["2025-11-03", "2026-10-30"]
    assert client.get("/api/companies/AAPL/price-history?years=0").status_code == 400
    assert _get(client, "/api/companies/AAL/price-history")["closes"] == []


def test_peers(client: TestClient) -> None:
    body = _get(client, "/api/companies/AAPL/peers")
    # FMP's list keeps HGCO alone (AAL has no statements), fewer than the three a target margin
    # needs, so the peers are the industry's: HGCO again
    assert body["source"] == {
        "kind": "industry",
        "industry": "Software - Application",
        "fmpCounted": 1,
    }
    [hgco] = body["peers"]
    assert hgco["symbol"] == "HGCO"
    assert hgco["marketCap"] == _figure(15e9, "currency", "peer:AAPL/HGCO/market_cap")
    assert hgco["margin"]["value"] == pytest.approx(0.20)
    assert hgco["margin"]["ref"] == "peer:AAPL/HGCO/margin"
    assert hgco["marginYears"] == _figure(10, "count", "peer:AAPL/HGCO/margin_years")
    assert hgco["salesToCapital"]["unit"] == "multiple"
    assert hgco["roic"]["unit"] == "percent" and hgco["roic"]["value"] is not None


def test_peers_without_deciles(client: TestClient, db_path: Path) -> None:
    with closing(connect(db_path)) as conn:
        conn.execute("DELETE FROM deciles")
        conn.commit()
    assert _get(client, "/api/companies/AAPL/peers") == {
        "symbol": "AAPL",
        "source": None,
        "peers": [],
    }


def test_a_methodology_section_reads_with_its_live_values(client: TestClient) -> None:
    body = _get(client, "/api/methodology/mature-growth")
    assert (body["id"], body["title"]) == ("mature-growth", "Mature Growth")
    text = body["text"]
    assert text.startswith("In Mature Growth, the market prices earnings growth")
    assert "Hurdle rate RULE 9.0%" in text  # the worked example's table, cell by cell
    # the live values, as the page's script formats them: spans of years, points, fractions
    assert "growth fades in equal steps over 5 years to the belief" in text
    assert "It adds 2 points for inflation." in text
    assert "runways of 5 years, 10 years and 20 years" in text
    assert "returns of 15.0% and 9.0% too" in text
    assert "—" not in text and "  " not in text
    value = _get(client, "/api/methodology/value")["text"]
    assert "Every route discounts at the hurdle rate, 9.0%." in value
    r = client.get("/api/methodology/nope")
    assert r.status_code == 404 and r.json()["detail"] == "no methodology section nope"


def test_the_methodology_sections_are_listed(client: TestClient) -> None:
    sections = _get(client, "/api/methodology")["sections"]
    assert [s["id"] for s in sections] == [
        "what",
        "life-cycle",
        "classifier",
        "value",
        "mature-growth",
        "mature-stable",
        "growth",
        "decline",
        "start-up",
        "flags",
        "sources",
        "your-settings",
    ]
    assert sections[0] == {"id": "what", "title": "What Fairband does"}
    assert sections[6] == {"id": "growth", "title": "High Growth and Young Growth"}


def test_a_methodology_section_reads_the_user_s_settings(client: TestClient) -> None:
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1}}, headers=HEADER)
    assert r.status_code == 200, r.text
    value = _get(client, "/api/methodology/value")["text"]
    assert "Every route discounts at the hurdle rate, 10.0%." in value
    settings = _get(client, "/api/methodology/your-settings")["text"]
    assert "The policy file is fairband-policy-v9." in settings
    assert settings.endswith("1 setting differs from the defaults.")


def test_the_classifier_section_reads_the_decile_edges(client: TestClient) -> None:
    text = _get(client, "/api/methodology/classifier")["text"]
    # the engine's test universe: edges at -10%, -5%, 0%, 3%, 6%, 9%, 12%, 18% and 30%, read
    # from 100 companies
    assert "Very High 9 and 10 18.0% or more" in text
    assert "Close to zero or negative 1 and 2 below −5.0%" in text
    assert "100 companies" in text


def test_every_ref_the_reads_hand_out_resolves_to_its_figure(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """A cite of any figure the reads serve passes the number check's resolver: the same value
    and unit (spec 13.2, 13.5)."""
    served: list[dict[str, Any]] = []

    def collect(x: Any) -> None:
        if isinstance(x, dict) and set(x) >= {"value", "unit", "ref"}:
            served.append(x)
        for child in x.values() if isinstance(x, dict) else x if isinstance(x, list) else ():
            collect(child)

    for read in ("financials", "financial-tables", "estimates", "price-history", "peers"):
        collect(_get(client, f"/api/companies/AAPL/{read}"))
    forms = {figure["ref"].partition(":")[0] for figure in served}
    assert forms == {"fact", "table", "estimate", "close", "peer"}
    with closing(connect(db_path)) as conn:
        resolver = Resolver(conn, "AAPL", policy)
        for figure in served:
            found = resolver.resolve(figure["ref"])
            assert found is not None, figure["ref"]
            assert (found.value, found.unit) == (figure["value"], figure["unit"]), figure["ref"]


# --- the multiples history (13.7) ------------------------------------------------------------

# Fourteen years of GuruFocus's pettm series, a row on 30 October each year, three of them loss
# rows. The ten years to the newest day run from 30 October 2016, so 2013 and 2015 fall outside.
PETTM_YEARS: dict[int, float | None] = {
    2013: 30.0,
    2014: None,
    2015: 25.0,
    2016: 20.0,
    2017: 22.0,
    2018: None,
    2019: 18.0,
    2020: 24.0,
    2021: None,
    2022: 16.0,
    2023: 35.0,
    2024: 21.0,
    2025: 19.0,
    2026: 23.0,
}
FMP_KEY = "fake-fmp-key-0005"  # not a real key
GF_TOKEN = "fakegfhalf5:fakegfhalf6"  # not a real token
NO_GF_KEY = "no GuruFocus key: the pe-history pass-through is off"
STATS = ("avg_10y", "median_10y", "high_10y", "low_10y")


def _pettm(years: dict[int, float | None]) -> list[list[Any]]:
    """A row a year, ``[date, open, high, low, close]``; a loss row as GuruFocus writes one."""
    return [
        [f"{year}-10-30", "At Loss", 0, 0, 0]
        if close is None
        else [f"{year}-10-30", close - 0.5, close + 0.5, close - 1.0, close]
        for year, close in years.items()
    ]


class GuruFocusDouble:
    """GuruFocus on a mock transport: every request answers ``body`` with ``status``; ``calls``
    counts them."""

    def __init__(self) -> None:
        self.body: Any = _pettm(PETTM_YEARS)
        self.status = 200
        self.calls = 0
        self.transport = httpx.MockTransport(self._answer)

    def _answer(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        assert request.url.path == f"/public/user/{GF_TOKEN}/stock/AAPL/pettm"
        return httpx.Response(self.status, json=self.body)


@pytest.fixture
def gf() -> GuruFocusDouble:
    return GuruFocusDouble()


@pytest.fixture
def with_history(
    tmp_path: Path, db_path: Path, policy: Policy, gf: GuruFocusDouble
) -> Iterator[Callable[[bool], TestClient]]:
    """Makes a client of an app whose pass-through has a GuruFocus client over ``gf``, or none."""
    opened: list[Any] = []

    def make(with_gurufocus: bool) -> TestClient:
        def http(base_url: str, secret: str, transport: httpx.BaseTransport) -> VendorHttp:
            made = VendorHttp(
                base_url, [secret], policy.refresh, transport=transport, sleep=lambda _: None
            )
            opened.append(made)
            return made

        nowhere = httpx.MockTransport(lambda request: httpx.Response(404))
        fmp = Fmp(http(fmp_api.BASE_URL, FMP_KEY, nowhere), FMP_KEY)
        gurufocus = GuruFocus(http(gurufocus_api.BASE_URL, GF_TOKEN, gf.transport), GF_TOKEN)
        passthrough = Passthrough(
            fmp,
            lambda: connect(db_path),
            policy,
            lambda: NOW,
            (FMP_KEY, GF_TOKEN),
            gurufocus if with_gurufocus else None,
        )
        app = create_app(
            _settings(tmp_path, db_path),
            policy,
            lambda: connect(db_path),
            clock=lambda: NOW,
            passthrough=passthrough,
        )
        opened.append(TestClient(app, base_url=HOST))
        client: TestClient = opened[-1]
        return client

    yield make
    for made in opened:
        made.close()


def _log(db_path: Path, rows: list[tuple[str, float | None]]) -> None:
    """AAPL's multiples log: a row a day at $150 with the forward P/E given."""
    with closing(connect(db_path)) as conn:
        for day, pe_forward in rows:
            log_multiples(
                conn, "AAPL", date.fromisoformat(day), 150.0, 25.0, 24.0, pe_forward, 1, 1, CREATED
            )


def _series(
    name: str,
    points: list[tuple[str, float]],
    stats: tuple[float | None, ...],
    since: str | None,
    response_id: int | None,
    note: str | None = None,
    symbol: str = "AAPL",
) -> dict[str, Any]:
    """The series as the read answers it, the company's refs beside each point and statistic."""
    ref = f"multiple:{symbol}/{name}"
    return {
        "points": [{"day": day, "value": value, "ref": f"{ref}/{day}"} for day, value in points],
        "stats": {
            stat.replace("_", ""): _figure(value, "multiple", f"{ref}/{stat}")
            for stat, value in zip(STATS, stats, strict=True)
        },
        "since": since,
        "responseId": response_id,
        "note": note,
    }


def _response_id(db_path: Path) -> int:
    with closing(connect(db_path)) as conn:
        row = latest_response(conn, "gurufocus", "pettm", "AAPL", {"symbol": "AAPL"})
    assert row is not None
    return row.id


def test_the_multiples_history_read(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble, db_path: Path, policy: Policy
) -> None:
    """The trailing series over the ten years to its newest day, the loss rows dropped and the
    statistics over the points left; the forward series from the log, ``since`` its first day.
    Every ref resolves to its figure, and a second read reuses the stored series."""
    _log(db_path, [("2026-10-28", 20.0), ("2026-10-29", 25.0), ("2026-10-30", 21.0)])
    client = with_history(True)
    body = _get(client, "/api/companies/aapl/multiples-history")
    trailing = [
        (f"{year}-10-30", close)
        for year, close in PETTM_YEARS.items()
        if year >= 2016 and close is not None
    ]
    # 20, 22, 18, 24, 16, 35, 21, 19 and 23: the average 22, the median 21, 35 and 16
    assert body == {
        "symbol": "AAPL",
        "pe": _series(
            "pe", trailing, (22.0, 21.0, 35.0, 16.0), "2013-10-30", _response_id(db_path)
        ),
        "peNote": None,
        "peForward": _series(
            "pe_forward",
            [("2026-10-28", 20.0), ("2026-10-29", 25.0), ("2026-10-30", 21.0)],
            (22.0, 21.0, 25.0, 20.0),
            "2026-10-28",
            None,
        ),
    }
    assert _get(client, "/api/companies/AAPL/multiples-history") == body
    assert gf.calls == 1  # stored inside its seven days: no second call
    figures = [
        *(p for series in ("pe", "peForward") for p in body[series]["points"]),
        *(s for series in ("pe", "peForward") for s in body[series]["stats"].values()),
    ]
    with closing(connect(db_path)) as conn:
        resolver = Resolver(conn, "AAPL", policy)
        for figure in figures:
            found = resolver.resolve(figure["ref"])
            assert found is not None, figure["ref"]
            assert (found.value, found.unit) == (figure["value"], "multiple"), figure["ref"]


def test_loss_rows_are_dropped_from_the_series(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble, db_path: Path
) -> None:
    """A loss leaves a gap: an "At Loss" row, a negative or a zero multiple has no point and
    nothing fills its days; a log row with no forward P/E has none either, yet the log began on
    its day."""
    gf.body = [
        ["2026-10-26", 18.0, 18.0, 18.0, 18.0],
        ["2026-10-27", "At Loss", 0, 0, 0],
        ["2026-10-28", -3.0],
        ["2026-10-29", 0],
        ["2026-10-30", 20.0, 20.0, 20.0, 20.0],
    ]
    _log(db_path, [("2026-10-29", None), ("2026-10-30", 21.0)])
    body = _get(with_history(True), "/api/companies/AAPL/multiples-history")
    assert body["pe"] == _series(
        "pe",
        [("2026-10-26", 18.0), ("2026-10-30", 20.0)],
        (19.0, 19.0, 20.0, 18.0),
        "2026-10-26",
        _response_id(db_path),
    )
    assert body["peForward"] == _series(
        "pe_forward", [("2026-10-30", 21.0)], (21.0, 21.0, 21.0, 21.0), "2026-10-29", None
    )


def test_without_a_gurufocus_client_the_trailing_series_is_null(
    with_history: Callable[[bool], TestClient],
    client: TestClient,
    gf: GuruFocusDouble,
    db_path: Path,
) -> None:
    """The forward series still answers; the trailing one is ``null`` with the reason in
    ``peNote``: no GuruFocus key, or, on a server with no pass-through at all, no FMP key."""
    _log(db_path, [("2026-10-30", 21.0)])
    forward = _series(
        "pe_forward", [("2026-10-30", 21.0)], (21.0, 21.0, 21.0, 21.0), "2026-10-30", None
    )
    without = _get(with_history(False), "/api/companies/AAPL/multiples-history")
    assert without == {"symbol": "AAPL", "pe": None, "peNote": NO_GF_KEY, "peForward": forward}
    no_passthrough = _get(client, "/api/companies/AAPL/multiples-history")
    assert no_passthrough == {**without, "peNote": "no FMP key"}
    assert gf.calls == 0
    empty = _get(client, "/api/companies/HGCO/multiples-history")["peForward"]
    nothing_logged = _series("pe_forward", [], (None,) * 4, None, None, symbol="HGCO")
    assert empty == nothing_logged


def test_a_series_that_cannot_be_read_has_no_points(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble, db_path: Path
) -> None:
    gf.body = {"error": "Stock not found"}  # GuruFocus answers some failures with HTTP 200
    body = _get(with_history(True), "/api/companies/AAPL/multiples-history")
    unread = _series("pe", [], (None,) * 4, None, _response_id(db_path))
    assert body["pe"] == {**unread, "note": "the series could not be read"}
    assert body["peNote"] is None


def test_a_failed_fetch_leaves_the_trailing_series_null_without_the_token(
    with_history: Callable[[bool], TestClient], gf: GuruFocusDouble
) -> None:
    gf.status, gf.body = 403, {"error": f"token {GF_TOKEN} is not valid"}
    response = with_history(True).get("/api/companies/AAPL/multiples-history")
    assert response.status_code == 200 and GF_TOKEN not in response.text
    body = response.json()
    assert body["pe"] is None and body["peForward"]["points"] == []
    assert body["peNote"].startswith(
        "GET https://api.gurufocus.com/public/user/<key>/stock/AAPL/pettm -> 403"
    )


def test_a_symbol_that_is_not_one_is_400(client: TestClient) -> None:
    response = client.get("/api/companies/A$B/multiples-history")
    assert response.status_code == 400 and response.json()["detail"].startswith("'A$B'")
