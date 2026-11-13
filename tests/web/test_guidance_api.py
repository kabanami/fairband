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
from support.web import CREATED, HEADER, NOW

from fairband.store.db import connect
from fairband.store.facts import FactRow, insert_facts
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


def _store_line(db_path: Path, field: str, year: int, value: float) -> None:
    """One line of AAPL's fiscal-year income statement, as the refresh stores it."""
    with closing(connect(db_path)) as conn:
        response = record_response(
            conn, "fmp", "income-statement", {"symbol": "AAPL"}, "AAPL", 200, "[]", None, CREATED
        )
        end = date(year, 9, 27)
        fact = FactRow(
            symbol="AAPL",
            dataset="income-annual",
            period_end=end,
            fiscal_year=year,
            fiscal_period="FY",
            field=field,
            value=Decimal(repr(value)),
            unit="USD",
            currency="USD",
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
                "metric is one of revenue, eps, operating_margin, free_cash_flow, capex,"
                " revenue_growth or eps_growth"
            ),
        ),
        ({"basis": "non-gaap"}, "basis is one of gaap, adjusted or constant-currency"),
        ({"period": "FY2026"}, "period is a fiscal year or a quarter (2026, 2026Q3)"),
        ({"text": "  "}, "a guidance record needs its text"),
        ({"source": ""}, "a guidance record needs its source"),
    ],
)
def test_guidance_refusals(client: TestClient, changes: dict[str, Any], detail: str) -> None:
    r = client.post("/api/companies/AAPL/guidance", json=REVENUE_2026 | changes, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert client.get("/api/companies/AAPL/guidance").json() == {"guidance": []}
    assert client.get("/api/companies/AAPL/ledger").json() == {"entries": []}


def test_a_guidance_record_is_an_agents_write(client: TestClient) -> None:
    r = client.post("/api/companies/AAPL/guidance", json=REVENUE_2026, headers=HEADER)
    assert (r.status_code, r.json()) == (403, {"detail": "a guidance record is an agent's write"})
    assert client.get("/api/companies/AAPL/guidance").json() == {"guidance": []}
