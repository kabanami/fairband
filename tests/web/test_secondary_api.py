"""The secondary valuation and derivation routes (spec 2026-11-06 Tier 2, 11, 13.4 and 16), on the
database of ``conftest.py``: AAPL (the Mature Growth golden: a Wide moat, 1 bn diluted shares, a
price of $150), AAL and HGCO, each with one snapshot. Here AAPL also gets two hand-written annual
balance sheets and income statements; FRGN (statements in euros), ADRX (an ADR in the universe)
and NOSH (no diluted share count) get a snapshot each; and the override routes build each
company's inputs as the conftest valued them, as ``test_reviews_api`` does."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import (
    high_growth_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.web import CREATED, HEADER, NOW, TODAY, _company

from fairband.engine.classifier import Deciles
from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.policy.tax import TaxTable
from fairband.store.companies import insert_companies
from fairband.store.db import connect
from fairband.store.facts import FactRow, insert_facts
from fairband.store.refreshes import latest_refresh, save_deciles
from fairband.store.snapshots import insert_snapshot
from fairband.store.vendor import record_response
from fairband.web import reviews_api
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER

AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
FILING = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None}
SCALE = 1e8  # spec 20.1's path in hundreds of millions of dollars, over AAPL's 1 bn shares
PATH = [x * SCALE for x in (100.0, 105.0, 110.25, 115.7625, 121.550625)]
FIRM = 1782.4206 * SCALE  # spec 20.1's firm value at this scale
ONE_PART = {
    "parts": [{"name": "the business", "fcff": PATH, "terminalGrowth": 0.03}],
    "reason": "the services segment carries the company",
    "evidence": [FILING],
}
FY24, FY25 = date(2024, 9, 28), date(2025, 9, 27)
# AAPL's balance sheets: in fiscal 2025 debt 0.5 + 1.5 = $2 bn and cash 0.6 + 0.4 = $1 bn
SHEETS = {
    FY24: {
        "shortTermDebt": 9e9,
        "longTermDebt": 9e9,
        "cashAndCashEquivalents": 9e9,
        "shortTermInvestments": 9e9,
    },
    FY25: {
        "shortTermDebt": 0.5e9,
        "longTermDebt": 1.5e9,
        "cashAndCashEquivalents": 0.6e9,
        "shortTermInvestments": 0.4e9,
    },
}
REVENUE = {FY24: 20e9, FY25: 22e9}
FOREIGN = "foreign filer: currency and share-unit handling not built yet"


def _fact(dataset: str, end: date, field: str, value: float, response_id: int) -> FactRow:
    return FactRow(
        symbol="AAPL",
        dataset=dataset,
        period_end=end,
        fiscal_year=end.year,
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
        response_id=response_id,
    )


def _store_statements(conn: sqlite3.Connection) -> None:
    response = record_response(
        conn, "fmp", "balance-sheet-statement", {"symbol": "AAPL"}, "AAPL", 200, "[]", None, CREATED
    )
    rows = [
        _fact("balance-annual", end, field, value, response)
        for end, lines in SHEETS.items()
        for field, value in lines.items()
    ]
    rows += [
        _fact("income-annual", end, "revenue", value, response) for end, value in REVENUE.items()
    ]
    insert_facts(conn, rows)


def _store_more_companies(conn: sqlite3.Connection, policy: Policy) -> None:
    """FRGN refused as a foreign filer, ADRX valued while its universe row is an ADR, NOSH
    refused for its share count."""
    refresh = latest_refresh(conn)
    assert refresh is not None
    golden = mature_growth_inputs()
    companies = {
        "FRGN": replace(golden, symbol="FRGN", currency="EUR"),
        "ADRX": replace(golden, symbol="ADRX"),
        "NOSH": replace(golden, symbol="NOSH", shares_diluted=None),
    }
    adr = replace(_company("ADRX", refresh.id, "An ADR", Decimal(100_000_000_000)), is_adr=True)
    insert_companies(conn, [adr])
    results = {s: value_company(i, universe_deciles(), policy, TODAY) for s, i in companies.items()}
    assert results["FRGN"].refusal == FOREIGN and results["ADRX"].value is not None
    assert results["NOSH"].refusal == "no diluted share count"
    for result in results.values():
        insert_snapshot(conn, result, refresh.id, clock=lambda: CREATED)


@pytest.fixture(autouse=True)
def stored(db_path: Path, policy: Policy, monkeypatch: pytest.MonkeyPatch) -> None:
    with closing(connect(db_path)) as conn:
        save_deciles(conn, 1, universe_deciles(), CREATED)
        _store_statements(conn)
        _store_more_companies(conn, policy)
    inputs = {
        "AAPL": replace(mature_growth_inputs(), symbol="AAPL"),
        "AAL": replace(young_growth_inputs(), symbol="AAL", peers=()),
        "HGCO": high_growth_inputs(),
    }

    def build(
        conn: sqlite3.Connection,
        symbol: str,
        policy: Policy,
        tax: TaxTable,
        today: date,
        deciles: Deciles | None = None,
    ) -> CompanyInputs:
        return inputs[symbol]

    monkeypatch.setattr(reviews_api, "build_inputs", build)


def _secondary(
    client: TestClient, body: dict[str, Any], symbol: str = "AAPL", headers: Any = AGENT
) -> Any:
    r = client.post(f"/api/companies/{symbol}/secondary", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _refused(client: TestClient, body: dict[str, Any], symbol: str = "AAPL") -> tuple[int, Any]:
    r = client.post(f"/api/companies/{symbol}/secondary", json=body, headers=AGENT)
    return r.status_code, r.json()


def _stored(client: TestClient, symbol: str = "AAPL") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = client.get(f"/api/companies/{symbol}/secondary").json()[
        "secondaryValuations"
    ]
    return found


def _derive(client: TestClient, *derivations: dict[str, Any]) -> Any:
    body = {"derivations": list(derivations)}
    return client.post("/api/companies/AAPL/derivations", json=body, headers=AGENT)


def test_a_secondary_valuation_reads_the_balance_sheet(
    client: TestClient, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    snapshot = client.get("/api/companies/AAPL").json()["snapshot"]
    body = _secondary(client, ONE_PART, symbol="aapl")
    assert (body["debt"], body["cash"], body["shares"]) == (2e9, 1e9, 1e9)  # FY2025's lines
    assert (body["debtSource"], body["cashSource"]) == ("statements", "statements")
    value = (FIRM - 2e9 + 1e9) / 1e9
    assert body["firmValue"] == pytest.approx(FIRM, abs=1e-4 * SCALE)
    assert body["equity"] == pytest.approx(body["firmValue"] - 1e9)
    assert body["valuePerShare"] == pytest.approx(value, abs=1e-4)
    levels = levels_for(body["valuePerShare"], "Wide", policy)  # the snapshot's moat
    assert (body["buyLevel"], body["fairLow"], body["fairHigh"], body["trimLevel"]) == (
        levels.buy,
        levels.fair_low,
        levels.fair_high,
        levels.trim,
    )
    ratio, designation = designation_for(150.0, body["valuePerShare"], policy.designation_edges)
    assert (body["priceToValue"], body["designation"]) == (ratio, designation)
    [part] = body["parts"]
    worked = [x * SCALE for x in (91.7431, 88.3764, 85.1332, 82.0091, 78.9996)]
    assert part["pv"] == pytest.approx(worked, abs=1e-4 * SCALE)
    assert part["terminalPv"] == pytest.approx(1356.1592 * SCALE, abs=1e-4 * SCALE)
    assert (part["name"], part["fcff"], part["terminalGrowth"], part["note"]) == (
        "the business",
        PATH,
        0.03,
        None,
    )
    assert {key: body[key] for key in ("symbol", "snapshotId", "principal", "actor", "client")} == {
        "symbol": "AAPL",
        "snapshotId": snapshot["id"],
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
    }
    assert (body["reason"], body["evidence"], body["createdAt"]) == (
        ONE_PART["reason"],
        [FILING | {"figure": None}],
        NOW.isoformat(),
    )
    assert (body["policyVersion"], body["settingsHash"], body["decilesRefreshId"]) == (
        policy.version,
        EMPTY_SETTINGS_HASH,
        results["AAPL"].deciles_refresh_id,
    )
    assert body["secondaryMethod"] == "fairband-secondary/2"
    assert _stored(client) == [body]
    assert _stored(client, "HGCO") == []


def test_explicit_debt_and_cash_need_evidence(client: TestClient) -> None:
    passed = ONE_PART | {"debt": 5e9, "cash": 2e9}
    assert _refused(client, passed) == (
        400,
        {"detail": "an explicit debt needs its own evidence item"},
    )
    debt_item = FILING | {"figure": "debt"}
    with_debt = passed | {"evidence": [FILING, debt_item]}
    assert _refused(client, with_debt) == (
        400,
        {"detail": "an explicit cash needs its own evidence item"},
    )
    assert _stored(client) == []
    cash_item = {"kind": "url", "ref": "https://example.com/q3", "note": None, "figure": "cash"}
    body = _secondary(client, passed | {"evidence": [FILING, debt_item, cash_item]})
    assert (body["debt"], body["debtSource"], body["cash"], body["cashSource"]) == (
        5e9,
        "agent",
        2e9,
        "agent",
    )
    assert body["valuePerShare"] == pytest.approx((FIRM - 5e9 + 2e9) / 1e9, abs=1e-4)
    no_cash = _secondary(client, ONE_PART | {"cash": 0.0, "evidence": [cash_item, FILING]})
    assert (no_cash["debt"], no_cash["debtSource"], no_cash["cash"], no_cash["cashSource"]) == (
        2e9,
        "statements",
        0.0,
        "agent",
    )
    assert [s["id"] for s in _stored(client)] == [no_cash["id"], body["id"]]


def test_the_path_needs_its_own_evidence_item(client: TestClient) -> None:
    """The items that back a debt or a cash do not back the cash-flow path."""
    debt_item = FILING | {"figure": "debt"}
    cash_item = FILING | {"figure": "cash"}
    for evidence in ([debt_item], [debt_item, cash_item]):
        passed = ONE_PART | {"debt": 5e9, "cash": 2e9, "evidence": evidence}
        assert _refused(client, passed) == (
            400,
            {"detail": "the path needs its own evidence item"},
        )
    assert _stored(client) == []
    explicit_none = FILING | {"figure": None}  # a figure of none backs the path
    body = _secondary(client, ONE_PART | {"debt": 5e9, "evidence": [debt_item, explicit_none]})
    assert body["debtSource"] == "agent"


def test_an_applied_balance_override_counts(client: TestClient) -> None:
    """HGCO has no balance sheet on file: its cash counts as nil, its source none; its debt is
    the override's."""
    debt = {
        "tag": "balance.debt",
        "new": 4e9,
        "reason": "the vendor missed the notes",
        "evidence": [FILING],
        "lifetime": "period-tied",
        "period": "FY2025",
    }
    r = client.post("/api/companies/HGCO/overrides", json=debt, headers=AGENT)
    assert r.status_code == 201 and r.json()["override"]["state"] == "applied"
    body = _secondary(client, ONE_PART, symbol="HGCO")
    assert (body["debt"], body["debtSource"], body["cash"], body["cashSource"]) == (
        4e9,
        "agent",
        0.0,
        "none",
    )
    assert body["valuePerShare"] == pytest.approx((FIRM - 4e9) / 100e6, abs=1e-3)


def test_the_levels_follow_the_reviewed_moat(client: TestClient, policy: Policy) -> None:
    narrow = {
        "tag": "moat.class",
        "new": "Narrow",
        "reason": "the patents lapse",
        "evidence": [FILING],
        "lifetime": "lasting",
    }
    r = client.post("/api/companies/AAPL/overrides", json=narrow, headers=AGENT)
    assert r.status_code == 201
    body = _secondary(client, ONE_PART)
    assert body["buyLevel"] == levels_for(body["valuePerShare"], "Narrow", policy).buy


@pytest.mark.parametrize("symbol", ["FRGN", "ADRX"])
def test_a_foreign_filer_is_refused(client: TestClient, symbol: str) -> None:
    assert _refused(client, ONE_PART, symbol) == (400, {"detail": FOREIGN})
    assert _stored(client, symbol) == []


def test_a_row_with_no_diluted_share_count_is_refused(client: TestClient) -> None:
    assert _refused(client, ONE_PART, "NOSH") == (400, {"detail": "no diluted share count"})
    assert _refused(client, ONE_PART, "ZZZZ") == (404, {"detail": "no snapshot for ZZZZ"})


def test_settings_changed_refuses_a_secondary(client: TestClient) -> None:
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1}}, headers=HEADER)
    assert r.status_code == 200
    assert _refused(client, ONE_PART) == (409, {"detail": "settings changed: run a revalue"})
    assert _stored(client) == []


@pytest.mark.parametrize(
    "change,sentence",
    [
        ({"reason": " "}, "a secondary valuation needs a reason"),
        ({"evidence": []}, "a secondary valuation needs evidence"),
        ({"parts": []}, "at least one part"),
        (
            {"parts": [{"name": "too fast", "fcff": PATH, "terminalGrowth": 0.035}]},
            "the terminal growth is at most g_T, 3.0%",
        ),
        (
            {"parts": [{"name": "too short", "fcff": PATH[:2], "terminalGrowth": 0.0}]},
            "a part has 3 to 15 years",
        ),
        (
            {
                "parts": [
                    {"name": f"unit {n}", "fcff": PATH, "terminalGrowth": 0.0} for n in range(11)
                ]
            },
            "at most 10 parts",
        ),
    ],
)
def test_a_rule_refuses_by_name(client: TestClient, change: dict[str, Any], sentence: str) -> None:
    assert _refused(client, ONE_PART | change) == (400, {"detail": sentence})
    assert _stored(client) == []


def test_a_secondary_is_a_ledger_row(client: TestClient) -> None:
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    by_agent = _secondary(client, ONE_PART)
    by_owner = _secondary(client, ONE_PART, headers=HEADER)  # a tool, not an override
    assert (by_owner["principal"], by_owner["actor"]) == ("owner", None)
    entries = client.get("/api/companies/AAPL/ledger").json()["entries"]
    assert [
        (e["kind"], e["refTable"], e["refId"], e["snapshotId"], e["principal"], e["actor"])
        for e in entries
    ] == [
        ("secondary", "secondary_valuations", by_owner["id"], snapshot_id, "owner", None),
        (
            "secondary",
            "secondary_valuations",
            by_agent["id"],
            snapshot_id,
            "agent",
            "claude-opus-5-5",
        ),
    ]
    value = by_agent["valuePerShare"]
    assert entries[1]["summary"] == f"${value:,.2f} a share from 1 part: {ONE_PART['reason']}"


def test_derivations_in_one_call(client: TestClient, results: dict[str, ValuationResult]) -> None:
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    s = f"snapshot:{snapshot_id}"
    r = _derive(
        client,
        {
            "operation": "ratio",
            "a": f"{s}/inputs/operating_income_ttm",
            "b": f"{s}/inputs/revenue_ttm",
        },
        {"operation": "growth", "a": f"{s}/inputs/ntm_eps", "b": f"{s}/inputs/eps_ttm"},
        {"operation": "cagr", "a": f"{s}/value", "b": f"{s}/price", "years": 3},
        {"operation": "difference", "a": f"{s}/value", "b": f"{s}/levels/buy"},
        {"operation": "sum", "a": f"{s}/inputs/revenue_ttm", "b": f"{s}/inputs/eps_ttm"},
    )
    assert r.status_code == 201, r.text
    found = r.json()["derivations"]
    value = results["AAPL"].value
    levels = results["AAPL"].levels
    assert value is not None and levels is not None
    assert [(d["value"], d["unit"]) for d in found] == [
        (pytest.approx(7_000e6 / 22_800e6), "multiple"),  # operating income ÷ revenue, trailing
        (pytest.approx(5.90 / 5.30 - 1), "percent"),  # NTM EPS over trailing EPS
        (pytest.approx((value / 150.0) ** (1 / 3) - 1), "percent"),
        (pytest.approx(value - levels.buy), "per-share"),  # the reads' units, not a currency code
        (pytest.approx(22_800e6 + 5.30), None),  # dollars and dollars a share: no unit
    ]
    stored = client.get(f"/api/derivations/{found[2]['id']}").json()
    assert stored == {
        "id": found[2]["id"],
        "symbol": "AAPL",
        "operation": "cagr",
        "a": f"{s}/value",
        "b": f"{s}/price",
        "years": 3,
        "value": found[2]["value"],
        "unit": "percent",
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "at": NOW.isoformat(),
    }
    entries = client.get("/api/companies/AAPL/ledger").json()["entries"]
    assert [(e["kind"], e["refId"], e["snapshotId"]) for e in entries] == [
        ("derivation", d["id"], snapshot_id) for d in reversed(found)
    ]
    assert (
        entries[-1]["summary"]
        == f"ratio of {s}/inputs/operating_income_ttm and {s}/inputs/revenue_ttm"
    )


def test_a_division_by_zero_has_no_value(client: TestClient) -> None:
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    zero = f"snapshot:{snapshot_id}/intermediates/price_facts/drawdown_from_peak"  # 0.0
    price = f"snapshot:{snapshot_id}/price"
    r = _derive(
        client,
        {"operation": "ratio", "a": price, "b": zero},
        {"operation": "growth", "a": price, "b": zero},
        {"operation": "cagr", "a": price, "b": zero, "years": 2},
        {"operation": "sum", "a": price, "b": zero},
    )
    assert r.status_code == 201, r.text
    found = r.json()["derivations"]
    assert [(d["value"], d["unit"]) for d in found] == [
        (None, None),
        (None, None),
        (None, None),
        (150.0, None),  # an intermediate's unit is not known
    ]
    assert client.get(f"/api/derivations/{found[0]['id']}").json()["value"] is None


def test_fact_refs_read_the_statements(client: TestClient) -> None:
    r = _derive(
        client,
        {"operation": "growth", "a": "fact:AAPL/revenue/2025", "b": "fact:aapl/revenue/2024"},
        {"operation": "ratio", "a": "fact:AAPL/revenue/ttm", "b": "fact:AAPL/revenue/2025"},
    )
    assert r.status_code == 201, r.text
    assert [(d["value"], d["unit"]) for d in r.json()["derivations"]] == [
        (pytest.approx(0.1), "percent"),
        (1.0, "multiple"),  # no quarters on file: the trailing figures are fiscal 2025's
    ]


def test_table_cells_and_policy_values_are_operands(client: TestClient) -> None:
    r = _derive(
        client,
        {"operation": "ratio", "a": "table:AAPL/solvency/debt/2025", "b": "fact:AAPL/revenue/2025"},
        {"operation": "difference", "a": "policy:required_return", "b": "policy:terminal_growth"},
    )
    assert r.status_code == 201, r.text
    assert [(d["value"], d["unit"]) for d in r.json()["derivations"]] == [
        (pytest.approx(2e9 / 22e9), "multiple"),  # fiscal 2025's debt over its revenue
        (pytest.approx(0.06), "percent"),  # r less g_T
    ]


@pytest.mark.parametrize(
    "ref",
    [
        "fact:AAPL/revenue/2023",
        "fact:AAPL/goodwill/2025",
        "fact:AAPL/revenue",
        "snapshot:{AAPL}/inputs/no_such_input",
        "snapshot:{AAPL}/phase/phase",
        "snapshot:{HGCO}/value",
        "snapshot:999/value",
        "snapshot:x/value",
        "review:1/value",
        "table:AAPL/solvency/cash_runway_years/2025",  # a cell with no figure
        "snapshot:{AAPL}/inputs/moat_class",  # a word
    ],
)
def test_an_unresolved_reference_stores_nothing(client: TestClient, ref: str) -> None:
    ids = {s: client.get(f"/api/companies/{s}").json()["snapshot"]["id"] for s in ("AAPL", "HGCO")}
    ref = ref.format(**ids)
    good = f"snapshot:{ids['AAPL']}/price"
    r = _derive(
        client,
        {"operation": "sum", "a": good, "b": good},
        {"operation": "ratio", "a": good, "b": ref},
    )
    assert (r.status_code, r.json()) == (400, {"detail": f"unresolved reference: {ref}"})
    assert client.get("/api/companies/AAPL/ledger").json()["entries"] == []
    assert client.get("/api/derivations/1").status_code == 404


def test_a_cagr_needs_its_years(client: TestClient) -> None:
    good = "fact:AAPL/revenue/2025"
    for years in ({}, {"years": 0}):
        r = _derive(client, {"operation": "cagr", "a": good, "b": good} | years)
        assert (r.status_code, r.json()) == (400, {"detail": "a cagr needs its years, one or more"})
    r = _derive(client)
    assert (r.status_code, r.json()) == (400, {"detail": "a derive call needs a derivation"})
    r = client.get("/api/derivations/1")
    assert (r.status_code, r.json()) == (404, {"detail": "no derivation 1"})
