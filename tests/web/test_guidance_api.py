"""The guidance routes (spec 2026-11-06 Tier 2, 9, 15.4 and 16; ``method.md`` 14.9), on the database
of ``conftest.py``: AAPL, AAL and HGCO, each with one snapshot. AAPL's fiscal 2025 revenue is
stored where a test needs the year before's actual on file."""

from contextlib import closing
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import fx_inputs, universe_deciles
from support.web import CREATED, HEADER, NOW, TODAY

from fairband.engine.route import value_company
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.store.facts import FactRow, insert_facts
from fairband.store.snapshots import insert_snapshot
from fairband.store.vendor import record_response
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER

AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
SAID = "We expect revenue of $24.0 billion to $25.0 billion for fiscal 2026."
REVENUE_2026 = {
    "metric": "revenue",
    "period": "2026",
    "low": 24e9,
    "high": 25e9,
    "basis": "gaap",
    "asOf": "2026-10-28",
    "text": SAID,
    "source": "response:12/0/content",
}


def _store_line(
    db_path: Path,
    field: str,
    year: int,
    value: float,
    symbol: str = "AAPL",
    currency: str = "USD",
) -> None:
    """One line of the company's fiscal-year income statement, as the refresh stores it, in
    ``currency``: AAPL's in USD unless named."""
    with closing(connect(db_path)) as conn:
        response = record_response(
            conn, "fmp", "income-statement", {"symbol": symbol}, symbol, 200, "[]", None, CREATED
        )
        end = date(year, 9, 27)
        fact = FactRow(
            symbol=symbol,
            dataset="income-annual",
            period_end=end,
            fiscal_year=year,
            fiscal_period="FY",
            field=field,
            value=Decimal(repr(value)),
            unit=currency,
            currency=currency,
            kind="observed",
            estimate_method=None,
            missing_reason=None,
            as_of=end,
            observed_at=CREATED,
            entered_at=CREATED,
            response_id=response,
        )
        insert_facts(conn, [fact])


def _post(client: TestClient, body: dict[str, Any], symbol: str = "AAPL") -> Any:
    r = client.post(f"/api/companies/{symbol}/guidance", json=body, headers=AGENT)
    assert r.status_code == 201, r.text
    return r.json()


def test_guidance_round_trip(client: TestClient, db_path: Path) -> None:
    """Posted, read back newest first, recorded in the ledger; the server reads the year before's
    actual from the statements and computes the midpoint and the step; a newer record for the
    same metric and period supersedes the older."""
    _store_line(db_path, "revenue", 2025, 20e9)
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    first = _post(client, REVENUE_2026)
    assert first == {
        "id": first["id"],
        "symbol": "AAPL",
        "metric": "revenue",
        "period": "2026",
        "low": 24e9,
        "high": 25e9,
        "midpoint": 24.5e9,
        "step": pytest.approx(0.225),
        "basis": "gaap",
        "asOf": "2026-10-28",
        "text": SAID,
        "source": "response:12/0/content",
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "createdAt": NOW.isoformat(),
        "supersededBy": None,
        "currency": "USD",  # none stored: the reporting currency, AAPL's snapshot's
    }
    point = _post(client, REVENUE_2026 | {"low": 24.6e9, "high": 24.6e9, "text": "About $24.6bn."})
    assert (point["midpoint"], point["step"]) == (24.6e9, pytest.approx(0.23))
    listed = client.get("/api/companies/aapl/guidance").json()["guidance"]
    assert [g["id"] for g in listed] == [point["id"], first["id"]]
    assert listed[1]["supersededBy"] == point["id"] and listed[0]["supersededBy"] is None
    entries = client.get("/api/companies/AAPL/ledger").json()["entries"]
    assert [(e["kind"], e["refTable"], e["refId"]) for e in entries] == [
        ("guidance", "guidance", point["id"]),
        ("guidance", "guidance", first["id"]),
    ]
    assert entries[1]["summary"] == f"revenue 2026: {SAID}"
    assert entries[1]["snapshotId"] == snapshot_id
    assert (entries[1]["principal"], entries[1]["actor"]) == ("agent", "claude-opus-5-5")
    assert client.get("/api/companies/HGCO/guidance").json() == {"guidance": []}


def test_the_step_reads_the_eps_line_and_needs_a_base_on_file(
    client: TestClient, db_path: Path
) -> None:
    """A fiscal-year EPS record steps from the year before's diluted EPS; a year with no actual on
    file, a quarter and a margin take no step."""
    _store_line(db_path, "epsDiluted", 2025, 6.0)
    eps = REVENUE_2026 | {"metric": "eps", "low": 6.3, "high": 6.6}
    assert _post(client, eps)["step"] == pytest.approx(0.075)
    assert _post(client, eps | {"period": "2027"})["step"] is None  # no 2026 actual on file
    assert _post(client, eps | {"period": "2026Q3"})["step"] is None
    margin = REVENUE_2026 | {"metric": "operating_margin", "low": 0.30, "high": 0.32}
    found = _post(client, margin)
    assert found["step"] is None and found["midpoint"] == pytest.approx(0.31)


def test_a_net_income_record_steps_from_the_net_income_line(
    client: TestClient, db_path: Path
) -> None:
    """Spec 2026-11-14 9: a fiscal-year net income record steps from the year before's net income
    as `fact:AAPL/net_income/2025` reads it: $1.1 bn to $1.3 bn over $1.0 bn, a midpoint of
    $1.2 bn and a step of 20%; with no actual of the year before on file, no step."""
    _store_line(db_path, "netIncome", 2025, 1.0e9)
    net_income = REVENUE_2026 | {"metric": "net_income", "low": 1.1e9, "high": 1.3e9}
    found = _post(client, net_income)
    assert (found["metric"], found["midpoint"]) == ("net_income", pytest.approx(1.2e9))
    assert found["step"] == pytest.approx(0.2)
    assert _post(client, net_income | {"period": "2027"})["step"] is None
    entries = client.get("/api/companies/AAPL/ledger").json()["entries"]
    assert entries[-1]["summary"] == f"net_income 2026: {SAID}"


def test_only_a_gaap_record_takes_a_step(client: TestClient, db_path: Path) -> None:
    """The actual of the year before is the statement's, a GAAP figure: an adjusted or a
    constant-currency record takes no step from it, since a rate across two bases is no growth
    (an adjusted EPS guidance of $11.50 on a GAAP actual of $6.00 would read 91.7%)."""
    _store_line(db_path, "epsDiluted", 2025, 6.0)
    _store_line(db_path, "revenue", 2025, 20e9)
    eps = REVENUE_2026 | {"metric": "eps", "low": 11.5, "high": 11.5}
    assert _post(client, eps | {"basis": "adjusted"})["step"] is None
    assert _post(client, eps)["step"] == pytest.approx(11.5 / 6.0 - 1)
    assert _post(client, REVENUE_2026 | {"basis": "constant-currency"})["step"] is None
    assert _post(client, REVENUE_2026 | {"basis": "adjusted"})["step"] is None


@pytest.mark.parametrize(
    ("changes", "detail"),
    [
        ({"low": 26e9}, "low is above high"),
        (
            {"metric": "ebitda"},
            (
                "metric is one of revenue, eps, net_income, operating_margin, free_cash_flow,"
                " capex, revenue_growth or eps_growth"
            ),
        ),
        ({"basis": "non-gaap"}, "basis is one of gaap, adjusted or constant-currency"),
        ({"period": "FY2026"}, "period is a fiscal year or a quarter (2026, 2026Q3)"),
        ({"text": "  "}, "a guidance record needs its text"),
        ({"source": ""}, "a guidance record needs its source"),
        (
            {"metric": "operating_margin", "low": 0.30, "high": 0.32, "currency": "USD"},
            "a currency goes with a money figure",
        ),
        ({"currency": "usd"}, "a currency is three capital letters, not 'usd'"),
        ({"currency": "DOLLAR"}, "a currency is three capital letters, not 'DOLLAR'"),
    ],
)
def test_guidance_refusals(client: TestClient, changes: dict[str, Any], detail: str) -> None:
    r = client.post("/api/companies/AAPL/guidance", json=REVENUE_2026 | changes, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert client.get("/api/companies/AAPL/guidance").json() == {"guidance": []}
    assert client.get("/api/companies/AAPL/ledger").json() == {"entries": []}


def test_a_record_names_its_currency_and_steps_in_the_statements(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """Spec 2026-11-15 9.1, 9.2: FXCO reports in SEK, its snapshot's currency and its statements'.
    A record that names no currency is in SEK and steps from the SEK actual of the year before; one
    that names SEK steps too; one in US dollars takes no step, its midpoint over a SEK actual being
    no growth; a margin has no currency. Each answer, and the read, names the currency."""
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, value_company(fx_inputs(), universe_deciles(), policy, TODAY), 1)
    _store_line(db_path, "revenue", 2025, 20e9, symbol="FXCO", currency="SEK")
    bare = _post(client, REVENUE_2026, "FXCO")
    assert (bare["currency"], bare["step"]) == ("SEK", pytest.approx(0.225))
    sek = _post(client, REVENUE_2026 | {"currency": "SEK"}, "FXCO")
    assert (sek["currency"], sek["step"]) == ("SEK", pytest.approx(0.225))
    usd = _post(client, REVENUE_2026 | {"low": 2.4e9, "high": 2.5e9, "currency": "USD"}, "fxco")
    assert (usd["currency"], usd["step"], usd["midpoint"]) == ("USD", None, 2.45e9)
    margin = REVENUE_2026 | {"metric": "operating_margin", "low": 0.30, "high": 0.32}
    assert _post(client, margin, "FXCO")["currency"] is None
    listed = client.get("/api/companies/fxco/guidance").json()["guidance"]
    assert [(g["metric"], g["currency"]) for g in listed] == [
        ("operating_margin", None),
        ("revenue", "USD"),
        ("revenue", "SEK"),
        ("revenue", "SEK"),
    ]
    assert listed[1:] == [
        usd,
        sek | {"supersededBy": usd["id"]},
        bare | {"supersededBy": sek["id"]},
    ]


def test_a_company_with_no_snapshot_reads_in_us_dollars(client: TestClient) -> None:
    """Spec 2026-11-15 9.1: with no snapshot, the reporting currency is USD; a record's own
    currency stands."""
    bare = _post(client, REVENUE_2026, "ZZZZ")
    eps = REVENUE_2026 | {"metric": "eps", "low": 6.3, "high": 6.6, "currency": "TWD"}
    assert (bare["currency"], bare["step"]) == ("USD", None)
    assert _post(client, eps, "ZZZZ")["currency"] == "TWD"
    listed = client.get("/api/companies/zzzz/guidance").json()["guidance"]
    assert [(g["metric"], g["currency"]) for g in listed] == [("eps", "TWD"), ("revenue", "USD")]


def test_a_guidance_record_is_an_agents_write(client: TestClient) -> None:
    r = client.post("/api/companies/AAPL/guidance", json=REVENUE_2026, headers=HEADER)
    assert (r.status_code, r.json()) == (403, {"detail": "a guidance record is an agent's write"})
    assert client.get("/api/companies/AAPL/guidance").json() == {"guidance": []}
