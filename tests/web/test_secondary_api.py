"""The secondary valuation and derivation routes (spec 2026-11-06 Tier 2, 11, 13.4 and 16), on the
database of ``conftest.py``: AAPL (the Mature Growth golden: a Wide moat, 1 bn diluted shares, a
price of $150), AAL and HGCO, each with one snapshot. Here AAPL also gets two hand-written annual
balance sheets and income statements; FRGN (statements in euros), ADRX (an ADR in the universe)
and NOSH (no diluted share count) get a snapshot each; and the override routes build each
company's inputs as the conftest valued them, as ``test_reviews_api`` does. The drivers form's
tests add spec 20.4's company (``_drivers_company``)."""

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
from fairband.engine.secondary import SECONDARY_METHOD
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
GUIDANCE_REF = "a guidance item cites its record as guidance:<id>"
# Spec 20.4's drivers: three years growing 10%, 8% and 5% at a 20% margin, tax 25%,
# sales-to-capital 2, a terminal growth of 2%.
DRIVERS = {
    "years": 3,
    "revenueGrowth": [0.10, 0.08, 0.05],
    "operatingMargin": [0.20, 0.20, 0.20],
    "taxRate": 0.25,
    "salesToCapital": 2.0,
    "terminalGrowth": 0.02,
}
DEBT_ITEM = FILING | {"figure": "debt"}
CASH_ITEM = {"kind": "url", "ref": "https://example.com/q3", "note": None, "figure": "cash"}
# Spec 20.4's debt and cash, each passed with its evidence item.
ON_DRIVERS = {
    "drivers": DRIVERS,
    "reason": "the cycle turns in fiscal 2027",
    "evidence": [FILING, DEBT_ITEM, CASH_ITEM],
    "debt": 200.0,
    "cash": 100.0,
}
# Spec 20.4's projection, year by year: revenue, EBIT, NOPAT, reinvestment, FCFF and PV.
PROJECTION = [
    (1100.0, 220.0, 165.0, 50.0, 115.0, 105.504587),
    (1188.0, 237.6, 178.2, 44.0, 134.2, 112.953455),
    (1247.4, 249.48, 187.11, 29.7, 157.41, 121.549402),
]


def _fact(
    dataset: str, end: date, field: str, value: float, response_id: int, symbol: str = "AAPL"
) -> FactRow:
    return FactRow(
        symbol=symbol,
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


def _drivers_company(
    db_path: Path, policy: Policy, symbol: str = "DRVR", revenue: float | None = 1000.0
) -> None:
    """Spec 20.4's company: the Mature Growth golden with 50 diluted shares, its snapshot's
    aggregate ROIC set to 12%, so its Wide moat's terminal return is 12% (under the cap of r plus
    four points), and one fiscal year on file whose revenue, ``revenue``, is its trailing revenue
    (none on file with ``None``)."""
    golden = replace(mature_growth_inputs(), symbol=symbol, shares_diluted=50.0)
    result = value_company(golden, universe_deciles(), policy, TODAY)
    roic = result.intermediates["roic"] | {"aggregate": 0.12}
    pinned = replace(result, intermediates=result.intermediates | {"roic": roic})
    with closing(connect(db_path)) as conn:
        refresh = latest_refresh(conn)
        assert refresh is not None
        insert_snapshot(conn, pinned, refresh.id, clock=lambda: CREATED)
        if revenue is not None:
            response = record_response(
                conn,
                "fmp",
                "income-statement",
                {"symbol": symbol},
                symbol,
                200,
                "[]",
                None,
                CREATED,
            )
            insert_facts(conn, [_fact("income-annual", FY25, "revenue", revenue, response, symbol)])


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


def test_the_drivers_form_over_the_api(client: TestClient, db_path: Path, policy: Policy) -> None:
    """Spec 20.4 to 1e-4: r 9%, the terminal return 12%, debt 200, cash 100, 50 shares."""
    _drivers_company(db_path, policy)
    snapshot_id = client.get("/api/companies/DRVR").json()["snapshot"]["id"]
    body = _secondary(client, ON_DRIVERS, symbol="DRVR")
    assert body["valuePerShare"] == pytest.approx(39.888938, abs=1e-4)
    assert body["firmValue"] == pytest.approx(2094.446920, abs=1e-4)
    assert (body["form"], body["parts"], body["secondaryMethod"]) == (
        "drivers",
        [],
        SECONDARY_METHOD,
    )
    assert (body["debt"], body["debtSource"], body["cash"], body["cashSource"]) == (
        200.0,
        "agent",
        100.0,
        "agent",
    )
    assert body["drivers"] == DRIVERS  # the agent's drivers, as sent
    projection = body["projection"]
    assert (projection["trailingRevenue"], projection["terminalReturn"]) == (1000.0, 0.12)
    assert [y["t"] for y in projection["years"]] == [1, 2, 3]
    lines = ("revenue", "ebit", "nopat", "reinvestment", "fcff", "pv")
    for year, worked in zip(projection["years"], PROJECTION, strict=True):
        assert [year[line] for line in lines] == pytest.approx(worked, abs=1e-4)
    assert projection["terminalFcff"] == pytest.approx(159.043500, abs=1e-4)
    assert projection["terminal"] == pytest.approx(2272.05, abs=1e-4)
    assert projection["terminalPv"] == pytest.approx(1754.439476, abs=1e-4)
    grid = body["grid"]
    assert (grid["rowsAre"], grid["rows"], grid["cols"]) == (
        "growths",
        pytest.approx([0.01, 0.02, 0.03]),
        pytest.approx([0.08, 0.09, 0.10]),
    )
    assert [len(row) for row in grid["cells"]] == [3, 3, 3]  # nine cells
    assert grid["cells"][1][1] == body["valuePerShare"]  # the centre is the value
    assert grid["cells"][0][0] == pytest.approx(44.220636, abs=1e-4)  # r 8%, g 1%
    assert _stored(client, "DRVR") == [body]
    [entry] = client.get("/api/companies/DRVR/ledger").json()["entries"]
    assert (entry["kind"], entry["refId"], entry["snapshotId"]) == (
        "secondary",
        body["id"],
        snapshot_id,
    )
    reason = ON_DRIVERS["reason"]
    assert entry["summary"] == f"$39.89 a share from drivers over three years: {reason}"


def test_the_terminal_return_follows_the_reviewed_moat(client: TestClient, policy: Policy) -> None:
    """AAPL's aggregate ROIC, near 22%, takes the Wide moat's cap; under a Narrow moat as reviewed
    the terminal return is r. Its trailing revenue is fiscal 2025's: no quarters are on file."""
    wide = _secondary(client, ON_DRIVERS)
    assert wide["projection"]["terminalReturn"] == policy.wide_terminal_roic_cap
    assert wide["projection"]["trailingRevenue"] == 22e9
    narrow = {
        "tag": "moat.class",
        "new": "Narrow",
        "reason": "the patents lapse",
        "evidence": [FILING],
        "lifetime": "lasting",
    }
    r = client.post("/api/companies/AAPL/overrides", json=narrow, headers=AGENT)
    assert r.status_code == 201, r.text
    body = _secondary(client, ON_DRIVERS)
    assert body["projection"]["terminalReturn"] == policy.required_return
    assert body["buyLevel"] == levels_for(body["valuePerShare"], "Narrow", policy).buy


def test_drivers_or_parts_not_both(client: TestClient) -> None:
    both = ON_DRIVERS | {"parts": ONE_PART["parts"]}
    assert _refused(client, both) == (
        400,
        {"detail": "a secondary valuation takes drivers or parts, not both"},
    )
    assert _stored(client) == []


def test_drivers_or_parts_needed(client: TestClient) -> None:
    neither = {key: value for key, value in ONE_PART.items() if key != "parts"}
    for body in (neither, neither | {"parts": None, "drivers": None}):
        assert _refused(client, body) == (
            400,
            {"detail": "a secondary valuation needs drivers or parts"},
        )
    assert _stored(client) == []


@pytest.mark.parametrize(
    "change,sentence",
    [
        ({"revenueGrowth": [0.10, 3.5, 0.05]}, "revenue_growth is −80% to 300%"),
        ({"operatingMargin": [0.20, 0.20, -0.6]}, "operating_margin is −50% to 60%"),
        ({"taxRate": 0.55}, "tax_rate is 0% to 50%"),
        ({"salesToCapital": 12.0}, "sales_to_capital is 0.1 to 10"),
    ],
)
def test_a_driver_range_refuses_by_name(
    client: TestClient, db_path: Path, policy: Policy, change: dict[str, Any], sentence: str
) -> None:
    _drivers_company(db_path, policy)
    body = ON_DRIVERS | {"drivers": DRIVERS | change}
    assert _refused(client, body, "DRVR") == (400, {"detail": sentence})
    assert _stored(client, "DRVR") == []


@pytest.mark.parametrize("revenue", [None, 0.0, -1000.0])
def test_no_trailing_revenue_is_refused(
    client: TestClient, db_path: Path, policy: Policy, revenue: float | None
) -> None:
    _drivers_company(db_path, policy, revenue=revenue)
    assert _refused(client, ON_DRIVERS, "DRVR") == (
        400,
        {"detail": "no trailing revenue on file"},
    )
    assert _stored(client, "DRVR") == []


def test_the_parts_form_still_answers(client: TestClient) -> None:
    """Spec 20.1's path, valued as the parts form always valued it; its grid's rows are the shift
    in every part's terminal growth, the top one none, since the part is at g_T."""
    body = _secondary(client, ONE_PART)
    assert body["form"] == "parts"
    assert body["valuePerShare"] == pytest.approx((FIRM - 2e9 + 1e9) / 1e9, abs=1e-4)
    assert (body["drivers"], body["projection"]) == (None, None)
    grid = body["grid"]
    assert (grid["rowsAre"], grid["rows"], grid["cols"]) == (
        "shifts",
        pytest.approx([-0.01, 0.0, 0.0]),
        pytest.approx([0.08, 0.09, 0.10]),
    )
    assert grid["cells"][1][1] == body["valuePerShare"]
    assert _stored(client) == [body]


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


def _guided(client: TestClient, symbol: str, call: str) -> int:
    body = {
        "metric": "revenue",
        "period": "2027",
        "low": 24e9,
        "high": 25e9,
        "basis": "gaap",
        "asOf": call,
        "text": "We guide fiscal 2027 revenue.",
        "source": "response:12/0/content",
    }
    r = client.post(f"/api/companies/{symbol}/guidance", json=body, headers=AGENT)
    assert r.status_code == 201, r.text
    guidance_id: int = r.json()["id"]
    return guidance_id


def test_a_guidance_item_is_checked_as_an_override_s_is(client: TestClient) -> None:
    """A secondary valuation's evidence item of kind ``guidance`` names a current guidance record
    of the company: another form of ref 400, another company's record 404, a superseded one 409,
    none stored; a good one is kept with the valuation."""
    earlier = _guided(client, "AAPL", "2026-07-29")
    later = _guided(client, "AAPL", "2026-10-28")
    theirs = _guided(client, "HGCO", "2026-10-28")
    refusals = [
        (_guidance_cite(later) | {"ref": "the Q3 call"}, 400, GUIDANCE_REF),
        (_guidance_cite(theirs), 404, f"no guidance record {theirs} for AAPL"),
        (
            _guidance_cite(earlier),
            409,
            f"guidance record {earlier} is superseded by record {later}",
        ),
    ]
    for cite, status, detail in refusals:
        body = ONE_PART | {"evidence": [FILING, cite]}
        assert _refused(client, body) == (status, {"detail": detail}), detail
    assert _stored(client) == []
    good = _guidance_cite(later)
    stored = _secondary(client, ONE_PART | {"evidence": [FILING, good]})
    assert stored["evidence"][1] == good | {"figure": None}


def _guidance_cite(guidance_id: int) -> dict[str, Any]:
    return {"kind": "guidance", "ref": f"guidance:{guidance_id}", "note": "FY2027 revenue"}


@pytest.mark.parametrize(
    "change,sentence",
    [
        ({"reason": " "}, "a secondary valuation needs a reason"),
        ({"evidence": []}, "a secondary valuation needs evidence"),
        ({"parts": []}, "at least one part"),
        (
            {"parts": [{"name": "too fast", "fcff": PATH, "terminalGrowth": 0.035}]},
            "the terminal growth is −100% to g_T, 3.0%",
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
