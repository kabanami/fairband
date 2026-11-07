"""The company reads and the Methodology section read (spec 2026-11-06 Tier 2, 13.5, 15.2 and 16)
on the database of ``conftest.py``: AAPL, AAL and HGCO, each with one snapshot. Here AAPL and
HGCO also get the refresh tests' synthetic statements (``refresh/synthetic.py``: calendar fiscal
years 2014 to 2025, revenue $1,000 m in 2014 up $100 m a year at a 20% operating margin, and
five quarters to 2026-09-30); AAPL gets the synthetic quarterly consensus, two years of annual
consensus, four closes and a peers list naming HGCO and AAL; and the store gets the deciles of
the engine's test universe, under which HGCO's statements classify as Mature Growth."""

from contextlib import closing
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from refresh.synthetic import bodies, estimates_quarter
from support.engine_companies import universe_deciles
from support.payloads import store_payloads
from support.web import CREATED, HEADER

from fairband.engine.anchor import TrailingFigures
from fairband.engine.balance import BalanceYear
from fairband.engine.classifier import FiscalYear
from fairband.policy import Policy
from fairband.reports.refs import Resolver
from fairband.reports.tables import LINES, TABLES
from fairband.store.db import connect
from fairband.store.refreshes import save_deciles

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


def test_the_estimates_read_shows_one_row_per_period(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """FMP's two fiscal calendars give HGCO two rows for 2026 Q4 and two for 2027, a day apart:
    the read serves one row per period, the one with the larger EPS analyst count, and its refs
    resolve to that row."""
    quarters = [
        {"symbol": "HGCO", "date": "2026-12-30", "epsAvg": 0.40, "numAnalystsEps": 4},
        {"symbol": "HGCO", "date": "2026-12-31", "epsAvg": 0.52, "numAnalystsEps": 11},
        {"symbol": "HGCO", "date": "2027-03-31", "epsAvg": 0.54, "numAnalystsEps": 10},
    ]
    annual = [
        {"symbol": "HGCO", "date": "2027-12-30", "epsAvg": 3.63, "numAnalystsEps": 8},
        {"symbol": "HGCO", "date": "2027-12-31", "epsAvg": 3.5, "numAnalystsEps": 3},
    ]
    consensus = {"estimates-quarter": quarters, "estimates-annual": annual}
    with closing(connect(db_path)) as conn:
        store_payloads(conn, "HGCO", consensus, CREATED)
    body = _get(client, "/api/companies/HGCO/estimates")
    assert [(q["period"], q["periodEnd"]) for q in body["quarters"]] == [
        ("2026-Q4", "2026-12-31"),
        ("2027-Q1", "2027-03-31"),
    ]
    assert body["quarters"][0]["eps"] == _figure(0.52, "per-share", "estimate:HGCO/2026-Q4/eps")
    assert [(a["period"], a["periodEnd"]) for a in body["annual"]] == [("2027", "2027-12-30")]
    assert body["annual"][0]["eps"] == _figure(3.63, "per-share", "estimate:HGCO/2027/eps")
    with closing(connect(db_path)) as conn:
        resolver = Resolver(conn, "HGCO", policy)
        for ref, value in (("estimate:HGCO/2026-Q4/eps", 0.52), ("estimate:HGCO/2027/eps", 3.63)):
            found = resolver.resolve(ref)
            assert found is not None and found.value == value, ref


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
        "agents",
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
