"""The secondary valuation and derivation routes (spec 2026-11-06 Tier 2, 11, 13.4 and 16), on the
database of ``conftest.py``: AAPL (the Mature Growth golden: a Wide moat, 1 bn diluted shares, a
price of $150), AAL and HGCO, each with one snapshot. Here AAPL also gets two hand-written annual
balance sheets and income statements; FRGN (refused for its currency's expected inflation), BSIS
(refused for its listed-share basis), ADRX (an ADR in USD in the universe), NOSH (no diluted share
count) and FXCO (spec 2026-11-10 11.2's company in SEK, ``fx_inputs``) get a snapshot each; and
the override routes build each company's inputs as the conftest valued them, as
``test_reviews_api`` does. The drivers form's tests add spec 20.4's company (``_drivers_company``),
and the currency's tests FXCO refused with its trailing revenue on file (``_fxco``).

The secondary valuation is the fallback where neither the route nor the review values the
company, and the route refuses one where either does (plan 3): AAL, refused for its target margin,
takes one as it stands, and none once a margin override values it (``_aal_review``); a test that
makes one on AAPL asks for ``refused_aapl``, AAPL revalued and refused (``_refuse``), and spec
20.4's company is refused the same way."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import (
    SEK_DIFFERENTIAL,
    SEK_RATE,
    fx_inputs,
    high_growth_inputs,
    mature_growth_inputs,
    universe_deciles,
    young_growth_inputs,
)
from support.web import CREATED, HEADER, NOW, TODAY, _company

from fairband.engine.classifier import Deciles
from fairband.engine.designation import designation_for
from fairband.engine.levels import levels_for
from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.roic import terminal_roic
from fairband.engine.route import CompanyInputs, reprice, value_company
from fairband.engine.secondary import SECONDARY_METHOD, Drivers, secondary_value
from fairband.engine.types import ValuationResult
from fairband.policy import Policy, in_currency
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.policy.tax import TaxTable
from fairband.store.companies import insert_companies
from fairband.store.db import connect
from fairband.store.facts import FactRow, insert_facts
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.refreshes import latest_refresh, save_deciles
from fairband.store.reviews import insert_review
from fairband.store.snapshots import insert_snapshot, latest_snapshot
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
# Two refusals an agent cannot fix (spec 2026-11-10 7.6), as the engine words them.
ABOVE_BOUND = "ARS: expected inflation 12.1% above the 10% bound"
BASIS = (
    "share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the ADR"
    " ratio 10)"
)
# The Mature Growth route's refusal that keeps the value-side intermediates (method 5.6).
NOT_POSITIVE = "value not positive under the reinvestment charge"
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
    dataset: str,
    end: date,
    field: str,
    value: float,
    response_id: int,
    symbol: str = "AAPL",
    currency: str = "USD",
) -> FactRow:
    return FactRow(
        symbol=symbol,
        dataset=dataset,
        period_end=end,
        fiscal_year=end.year,
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
    """FRGN refused for its currency's expected inflation and BSIS for its listed-share basis, as
    assembly hands the engine those refusals; ADRX valued while its universe row is an ADR in USD;
    NOSH refused for its share count; FXCO valued in SEK."""
    refresh = latest_refresh(conn)
    assert refresh is not None
    golden = mature_growth_inputs()
    companies = {
        "FRGN": replace(golden, symbol="FRGN", currency="ARS", refusal=ABOVE_BOUND),
        "BSIS": replace(golden, symbol="BSIS", refusal=BASIS),
        "ADRX": replace(golden, symbol="ADRX"),
        "NOSH": replace(golden, symbol="NOSH", shares_diluted=None),
        "FXCO": fx_inputs(),
    }
    adr = replace(_company("ADRX", refresh.id, "An ADR", Decimal(100_000_000_000)), is_adr=True)
    insert_companies(conn, [adr])
    results = {s: value_company(i, universe_deciles(), policy, TODAY) for s, i in companies.items()}
    assert (results["FRGN"].refusal, results["BSIS"].refusal) == (ABOVE_BOUND, BASIS)
    assert results["ADRX"].value is not None and results["FXCO"].value is not None
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


def _refuse(db_path: Path, symbol: str) -> int:
    """A later snapshot of ``symbol`` that the route refused, as the Mature Growth route refuses a
    value at or below zero: the latest's result with no route, value, levels or designation, its
    phase, inputs, intermediates (the moat, the aggregate ROIC) and price kept; its id."""
    with closing(connect(db_path)) as conn:
        latest = latest_snapshot(conn, symbol)
        assert latest is not None and latest.value is not None
        refused = replace(
            latest.result,
            route=None,
            value=None,
            levels=None,
            price_to_value=None,
            designation=None,
            refusal=NOT_POSITIVE,
        )
        return insert_snapshot(conn, refused, latest.refresh_id, clock=lambda: CREATED)


@pytest.fixture
def refused_aapl(db_path: Path) -> int:
    """AAPL revalued and refused (``_refuse``): the golden's Wide moat, aggregate ROIC, 1 bn
    diluted shares and $150 price on a snapshot with no value, which takes the fallback."""
    return _refuse(db_path, "AAPL")


def _drivers_company(
    db_path: Path, policy: Policy, symbol: str = "DRVR", revenue: float | None = 1000.0
) -> None:
    """Spec 20.4's company: the Mature Growth golden with 50 diluted shares, refused as the route
    refuses a value at or below zero (``_refuse``), so it takes the fallback (plan 3); its
    snapshot's aggregate ROIC set to 12%, so its Wide moat's terminal return is 12% (under the cap
    of r plus four points), and one fiscal year on file whose revenue, ``revenue``, is its
    trailing revenue (none on file with ``None``)."""
    golden = replace(mature_growth_inputs(), symbol=symbol, shares_diluted=50.0)
    result = value_company(golden, universe_deciles(), policy, TODAY)
    roic = result.intermediates["roic"] | {"aggregate": 0.12}
    pinned = replace(
        result,
        intermediates=result.intermediates | {"roic": roic},
        route=None,
        value=None,
        levels=None,
        price_to_value=None,
        designation=None,
        refusal=NOT_POSITIVE,
    )
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


# FXCO's trailing revenue, spec 2026-11-10 11.2's 8,000 m in SEK, and spec 20.4's drivers on it
# with a debt of 800 m and a cash of 400 m in SEK, each passed with its evidence item.
SEK_REVENUE = 8_000e6
ON_SEK = ON_DRIVERS | {"debt": 800e6, "cash": 400e6}


def _fxco(db_path: Path) -> None:
    """FXCO refused as the route refuses a value at or below zero (``_refuse``), so it takes the
    fallback, its currency, rate and differential kept on the refused snapshot; and one fiscal year
    on file, its revenue in SEK its trailing revenue."""
    _refuse(db_path, "FXCO")
    with closing(connect(db_path)) as conn:
        response = record_response(
            conn, "fmp", "income-statement", {"symbol": "FXCO"}, "FXCO", 200, "[]", None, CREATED
        )
        revenue = _fact("income-annual", FY25, "revenue", SEK_REVENUE, response, "FXCO", "SEK")
        insert_facts(conn, [revenue])


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


@pytest.mark.parametrize("symbol", ["HGCO", "AAPL", "ADRX"])
def test_a_secondary_valuation_is_refused_where_the_route_values(
    client: TestClient, symbol: str
) -> None:
    """Method 15.4, plan 3: the secondary valuation is the fallback where the route refuses, so a
    valued latest snapshot refuses the call on either form, before the snapshot's other refusals
    (ADRX, an ADR the route values); nothing is stored and no ledger row is written."""
    detail = f"the route values {symbol}: the secondary valuation is the fallback where it refuses"
    for body in (ONE_PART, ON_DRIVERS):
        assert _refused(client, body, symbol) == (400, {"detail": detail})
    assert _stored(client, symbol) == []
    assert client.get(f"/api/companies/{symbol}/ledger").json()["entries"] == []


def test_a_secondary_valuation_is_refused_where_the_review_values(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """Method 15.4, the ruling on plan 3's final review: the secondary valuation is the fallback
    where neither the route nor the review values the company. AAL's route refused for its target
    margin and a margin override values it, so its current review, on the latest snapshot or on one
    the latest reprices, refuses the call on either form, right after the route's refusal; nothing
    is stored and no ledger row is written. A revalue leaves that review on an older snapshot,
    where it no longer counts, and the call is made."""
    _aal_review(db_path, policy, results, 0.2)
    detail = (
        "the review values AAL: the secondary valuation is the fallback where neither the route nor"
        " the review values the company"
    )
    for body in (ONE_PART, ON_DRIVERS):
        assert _refused(client, body, "AAL") == (400, {"detail": detail})
    with closing(connect(db_path)) as conn:
        latest = latest_snapshot(conn, "AAL")
        assert latest is not None
        repriced = reprice(results["AAL"], 160.0, date(2026, 11, 2), policy)
        insert_snapshot(conn, repriced, latest.refresh_id, clock=lambda: CREATED)
    assert _refused(client, ONE_PART, "AAL") == (400, {"detail": detail})  # the reprice keeps it
    assert _stored(client, "AAL") == []
    assert client.get("/api/companies/AAL/ledger").json()["entries"] == []
    with closing(connect(db_path)) as conn:
        revalued = replace(repriced, data_date=repriced.data_date + timedelta(days=1))
        revalue = insert_snapshot(conn, revalued, latest.refresh_id, clock=lambda: CREATED)
    body = _secondary(client, ONE_PART, symbol="AAL")
    assert body["snapshotId"] == revalue


def test_a_review_that_refused_leaves_the_fallback(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    """A current review that refused, as AAL's row does, values nothing: the company takes the
    fallback on its latest snapshot (method 15.4)."""
    _aal_review(db_path, policy, results, None)
    snapshot = client.get("/api/companies/AAL").json()["snapshot"]
    body = _secondary(client, ONE_PART, symbol="AAL")
    assert (body["snapshotId"], body["form"]) == (snapshot["id"], "parts")


def _aal_review(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult], margin: float | None
) -> None:
    """An applied margin.target override of AAL, whose route refused for its target margin, and
    the review on AAL's latest snapshot: valued at ``margin``, else refused as the row is."""
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    with closing(connect(db_path)) as conn:
        latest = latest_snapshot(conn, "AAL")
        assert latest is not None
        override_id = insert_override(
            conn,
            "AAL",
            "margin.target",
            None,
            0.2 if margin is None else margin,
            "ratio",
            "the peers by hand",
            [FILING],
            "lasting",
            None,
            None,
            latest.id,
            writer,
            CREATED,
            "applied",
            "",
        )
        refused = results["AAL"]
        if margin is None:
            review = Review(
                replace(refused, refusal="the reviewed margin is refused"), None, (), (override_id,)
            )
        else:
            target = Override(override_id, "margin.target", margin, "agent", writer.actor, NOW, "")
            inputs = replace(young_growth_inputs(), symbol="AAL", peers=())
            review = review_company(inputs, universe_deciles(), policy, TODAY, [target], refused)
            assert review.result.value is not None
        insert_review(conn, review, "AAL", latest.id, None, clock=lambda: CREATED)


def test_a_secondary_valuation_is_made_where_the_route_refused(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    """AAL, refused for its target margin, takes the fallback on its latest snapshot."""
    assert results["AAL"].value is None and results["AAL"].refusal is not None
    snapshot = client.get("/api/companies/AAL").json()["snapshot"]
    body = _secondary(client, ONE_PART, symbol="AAL")
    assert (body["snapshotId"], body["form"]) == (snapshot["id"], "parts")
    assert _stored(client, "AAL") == [body]


@pytest.mark.usefixtures("refused_aapl")
def test_a_secondary_valuation_reads_the_balance_sheet(
    client: TestClient, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    snapshot = client.get("/api/companies/AAPL").json()["snapshot"]
    body = _secondary(client, ONE_PART, symbol="aapl")
    assert (body["debt"], body["cash"], body["shares"]) == (2e9, 1e9, 1e9)  # FY2025's lines
    assert body["fxRate"] == 1.0  # a USD row's rate
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


def test_the_terminal_return_follows_the_reviewed_moat(
    client: TestClient, db_path: Path, policy: Policy, refused_aapl: int
) -> None:
    """AAPL's aggregate ROIC, near 22%, takes the Wide moat's cap; under a Narrow moat as reviewed
    the terminal return is r. Its trailing revenue is fiscal 2025's: no quarters are on file. The
    review rests on the refused snapshot and refuses as the route does: one that valued it would
    refuse the fallback (method 15.4)."""
    wide = _secondary(client, ON_DRIVERS)
    assert wide["projection"]["terminalReturn"] == policy.wide_terminal_roic_cap
    assert wide["projection"]["trailingRevenue"] == 22e9
    _review_narrow(db_path, policy, refused_aapl)
    body = _secondary(client, ON_DRIVERS)
    assert body["projection"]["terminalReturn"] == policy.required_return
    assert body["buyLevel"] == levels_for(body["valuePerShare"], "Narrow", policy).buy


def _review_narrow(db_path: Path, policy: Policy, snapshot_id: int) -> None:
    """An applied override of AAPL's moat to Narrow on ``snapshot_id`` and the review under it,
    which refuses as the refused snapshot does, its inputs holding the reviewed moat."""
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    reason = "the patents lapse"
    with closing(connect(db_path)) as conn:
        override_id = insert_override(
            conn,
            "AAPL",
            "moat.class",
            "Wide",
            "Narrow",
            "class",
            reason,
            [FILING],
            "lasting",
            None,
            None,
            snapshot_id,
            writer,
            CREATED,
            "applied",
            "",
        )
        inputs = replace(mature_growth_inputs(), symbol="AAPL")
        mechanical = value_company(inputs, universe_deciles(), policy, TODAY)
        narrow = Override(override_id, "moat.class", "Narrow", "agent", writer.actor, NOW, reason)
        reviewed = review_company(inputs, universe_deciles(), policy, TODAY, [narrow], mechanical)
        refused = replace(
            reviewed.result,
            route=None,
            value=None,
            levels=None,
            price_to_value=None,
            designation=None,
            refusal=NOT_POSITIVE,
        )
        review = Review(refused, None, (), (override_id,))
        insert_review(conn, review, "AAPL", snapshot_id, None, clock=lambda: CREATED)


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


@pytest.mark.usefixtures("refused_aapl")
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


@pytest.mark.usefixtures("refused_aapl")
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


@pytest.mark.usefixtures("refused_aapl")
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
    """AAL, refused, has no balance sheet on file: its cash counts as nil, its source none; its
    debt is the override's."""
    debt = {
        "tag": "balance.debt",
        "new": 4e9,
        "reason": "the vendor missed the notes",
        "evidence": [FILING],
        "lifetime": "period-tied",
        "period": "FY2025",
    }
    r = client.post("/api/companies/AAL/overrides", json=debt, headers=AGENT)
    assert r.status_code == 201 and r.json()["override"]["state"] == "applied"
    body = _secondary(client, ONE_PART, symbol="AAL")
    assert (body["debt"], body["debtSource"], body["cash"], body["cashSource"]) == (
        4e9,
        "agent",
        0.0,
        "none",
    )
    assert body["valuePerShare"] == pytest.approx((FIRM - 4e9) / 100e6, abs=1e-3)


def test_the_levels_follow_the_reviewed_moat(client: TestClient, policy: Policy) -> None:
    """AAL's snapshot holds no moat class, so its levels take None's; under a Narrow moat as
    reviewed, Narrow's: the review the override route writes on the refused row."""
    before = _secondary(client, ONE_PART, symbol="AAL")
    assert before["buyLevel"] == levels_for(before["valuePerShare"], "None", policy).buy
    narrow = {
        "tag": "moat.class",
        "new": "Narrow",
        "reason": "the patents lapse",
        "evidence": [FILING],
        "lifetime": "lasting",
    }
    r = client.post("/api/companies/AAL/overrides", json=narrow, headers=AGENT)
    assert r.status_code == 201, r.text
    body = _secondary(client, ONE_PART, symbol="AAL")
    assert body["buyLevel"] == levels_for(body["valuePerShare"], "Narrow", policy).buy
    assert body["buyLevel"] != before["buyLevel"]


@pytest.mark.parametrize(("symbol", "refusal"), [("FRGN", ABOVE_BOUND), ("BSIS", BASIS)])
def test_a_refusal_an_agent_cannot_fix_refuses_the_call(
    client: TestClient, symbol: str, refusal: str
) -> None:
    """A snapshot refused for a reason no call can meet, the currency's expected inflation above
    the bound (FRGN) or the listed-share basis (BSIS), refuses the secondary valuation on either
    form with the refusal's own sentence (spec 2026-11-10 7.6); nothing is stored."""
    for body in (ONE_PART, ON_DRIVERS):
        assert _refused(client, body, symbol) == (400, {"detail": refusal})
    assert _stored(client, symbol) == []


def test_an_adr_in_usd_takes_the_fallback(client: TestClient, db_path: Path) -> None:
    """ADRX, an ADR in the universe that reports in USD, is a domestic row (spec 2026-11-10 7.5):
    once its route refuses it takes the fallback as any USD row does, at the rate 1, no balance
    sheet on file."""
    _refuse(db_path, "ADRX")
    body = _secondary(client, ONE_PART, symbol="ADRX")
    assert (body["fxRate"], body["debtSource"], body["cashSource"]) == (1.0, "none", "none")
    assert body["valuePerShare"] == pytest.approx(FIRM / 1e9, abs=1e-4)


def test_a_secondary_valuation_in_the_reporting_currency(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """Spec 2026-11-10 7.6: FXCO reports in SEK at 8.0 a dollar, its differential 2%. The drivers
    project its trailing revenue in SEK at r restated into SEK, 11.18%, the Wide moat's terminal
    return its aggregate capped at that r plus four points; the totals stay in SEK; the value a
    share, its levels and the grid's cells are ÷ 8.0, US dollars a share as the snapshot's, and
    the designation reads the USD price against that value; the record carries the rate, and the
    ledger names the value in dollars."""
    _fxco(db_path)
    local = in_currency(policy, SEK_DIFFERENTIAL)
    assert local.required_return == pytest.approx(0.1118, abs=1e-12)
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, "FXCO")
    assert snapshot is not None and snapshot.value is None
    body = _secondary(client, ON_SEK, symbol="FXCO")
    assert body["snapshotId"] == snapshot.id
    roic_t = terminal_roic(snapshot.result.intermediates["roic"]["aggregate"], "Wide", local)
    assert roic_t == local.wide_terminal_roic_cap != policy.wide_terminal_roic_cap
    engine = secondary_value(
        drivers=Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02),
        revenue_0=SEK_REVENUE,
        roic_t=roic_t,
        debt=800e6,
        cash=400e6,
        shares=100e6,
        price=50.0 * SEK_RATE,
        moat="Wide",
        policy=local,
    )
    assert engine.grid is not None and engine.value_per_share > 0
    assert body["fxRate"] == SEK_RATE
    # the totals in SEK, as the engine made them
    projection = body["projection"]
    assert (projection["trailingRevenue"], projection["terminalReturn"]) == (SEK_REVENUE, roic_t)
    assert (body["firmValue"], body["equity"]) == (engine.firm_value, engine.equity)
    assert (body["debt"], body["cash"], body["shares"]) == (800e6, 400e6, 100e6)
    # the value a share, the levels and the grid in USD; the designation on the USD price
    value = engine.value_per_share / SEK_RATE
    assert body["valuePerShare"] == value
    levels = levels_for(value, "Wide", policy)
    assert (body["buyLevel"], body["fairLow"], body["fairHigh"], body["trimLevel"]) == (
        levels.buy,
        levels.fair_low,
        levels.fair_high,
        levels.trim,
    )
    ratio, designation = designation_for(50.0, value, policy.designation_edges)
    assert (body["priceToValue"], body["designation"]) == (ratio, designation)
    grid = body["grid"]
    assert (grid["rows"], grid["cols"]) == (list(engine.grid.rows), list(engine.grid.cols))
    assert grid["cols"][1] == local.required_return
    assert grid["cells"] == [[cell / SEK_RATE for cell in row] for row in engine.grid.cells]
    assert grid["cells"][1][1] == body["valuePerShare"]  # the centre is the value
    assert _stored(client, "FXCO") == [body]
    [entry] = client.get("/api/companies/FXCO/ledger").json()["entries"]
    assert entry["summary"].startswith(f"${value:,.2f} a share from drivers over three years")


def test_the_terminal_growth_runs_to_g_t_restated(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """On FXCO the terminal growth's bound is g_T restated into SEK, 5.06% (spec 2026-11-10 7.3):
    5%, above a USD row's 3.0%, is taken; 5.1% is refused, the sentence naming the bound with the
    decimals it needs, so it names a figure below the one refused."""
    _fxco(db_path)
    assert in_currency(policy, SEK_DIFFERENTIAL).terminal_growth == pytest.approx(0.0506)
    above = ON_SEK | {"drivers": DRIVERS | {"terminalGrowth": 0.051}}
    assert _refused(client, above, "FXCO") == (
        400,
        {"detail": "the terminal growth is −100% to g_T, 5.06%"},
    )
    assert _stored(client, "FXCO") == []
    taken = _secondary(client, ON_SEK | {"drivers": DRIVERS | {"terminalGrowth": 0.05}}, "FXCO")
    assert taken["drivers"]["terminalGrowth"] == 0.05


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


@pytest.mark.usefixtures("refused_aapl")
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
@pytest.mark.usefixtures("refused_aapl")
def test_a_rule_refuses_by_name(client: TestClient, change: dict[str, Any], sentence: str) -> None:
    assert _refused(client, ONE_PART | change) == (400, {"detail": sentence})
    assert _stored(client) == []


@pytest.mark.usefixtures("refused_aapl")
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


def test_a_product_takes_the_unit_its_operands_give(client: TestClient) -> None:
    """``product`` is a × b. A figure times a multiple or a percent keeps its unit; a figure a
    share times a count is a total in the currency; any other pair has no unit."""
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    s = f"snapshot:{snapshot_id}"
    r = _derive(
        client,
        {"operation": "product", "a": f"{s}/price", "b": f"{s}/inputs/shares_diluted"},
        {"operation": "product", "a": "policy:required_return", "b": f"{s}/inputs/revenue_ttm"},
        {"operation": "product", "a": "policy:required_return", "b": "policy:terminal_growth"},
        {"operation": "product", "a": f"{s}/price_to_value", "b": f"{s}/value"},
        {"operation": "product", "a": f"{s}/inputs/revenue_ttm", "b": f"{s}/inputs/eps_ttm"},
    )
    assert r.status_code == 201, r.text
    found = r.json()["derivations"]
    assert [(d["value"], d["unit"]) for d in found] == [
        (pytest.approx(150.0 * 1e9), "currency"),  # the price times 1 bn diluted shares
        (pytest.approx(0.09 * 22_800e6), "currency"),  # 9% of the trailing revenue
        (pytest.approx(0.0027), "percent"),  # 9% of 3%
        (pytest.approx(150.0), "per-share"),  # price ÷ value times the value: the price
        (pytest.approx(22_800e6 * 5.30), None),  # dollars times dollars a share: no unit
    ]
    entries = client.get("/api/companies/AAPL/ledger").json()["entries"]
    assert entries[-1]["summary"] == f"product of {s}/price and {s}/inputs/shares_diluted"


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
