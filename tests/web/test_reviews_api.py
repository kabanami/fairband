"""The override and review routes (spec 2026-11-06 Tier 2, 10.1 to 10.6 and 16), on the database of
``conftest.py``: AAPL (the Mature Growth golden), AAL (Young Growth, refused for its target margin)
and HGCO, each with one snapshot. The database stores no statements, so the routes build each
company's inputs as the conftest valued them, on the universe deciles stored under its full
refresh."""

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import (
    fx_inputs,
    high_growth_inputs,
    mature_growth_inputs,
    start_up_inputs,
    universe_deciles,
    with_minority,
    young_growth_inputs,
)
from support.web import CREATED, HEADER, NOW, TODAY

from fairband.engine import METHOD_VERSION
from fairband.engine.anchor import sales_class
from fairband.engine.classifier import Deciles
from fairband.engine.overrides import Override, current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import ValuationResult, result_from_json
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.policy.tax import TaxTable
from fairband.store.db import connect
from fairband.store.refreshes import create_refresh, latest_deciles, save_deciles
from fairband.store.snapshots import insert_snapshot
from fairband.web import reviews_api
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER

AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
TRANSCRIPT = {"kind": "transcript", "ref": "Q3 call", "note": ""}
BELIEF_8 = {
    "tag": "growth.belief",
    "new": 0.08,
    "reason": "guidance raised",
    "evidence": [TRANSCRIPT],
    "lifetime": "lasting",
}
MOAT_NARROW = BELIEF_8 | {"tag": "moat.class", "new": "Narrow", "reason": "the patents lapse"}
LOCKED_G = BELIEF_8 | {"tag": "terminal_growth", "new": 0.03}
G_T_LOCKED = "g_T is a locked input: the terminal growth ceiling"
OWNERS_REFUSAL = "an override is an agent's write"
NO_PERIOD = "a period-tied override names its period"


@pytest.fixture(autouse=True)
def stored_inputs(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, CompanyInputs]:
    """The inputs the routes build for each company, by symbol; a test may change one, as a
    store change would."""
    with closing(connect(db_path)) as conn:
        save_deciles(conn, 1, universe_deciles(), CREATED)
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
        assert deciles is not None and deciles == latest_deciles(conn)  # the stored deciles
        return inputs[symbol]

    monkeypatch.setattr(reviews_api, "build_inputs", build)
    return inputs


def _post(client: TestClient, body: dict[str, Any], symbol: str = "AAPL") -> Any:
    r = client.post(f"/api/companies/{symbol}/overrides", json=body, headers=AGENT)
    assert r.status_code == 201, r.text
    return r.json()


def _drop(client: TestClient, override_id: int, headers: dict[str, str] = AGENT) -> Any:
    body = {"reason": "guidance withdrawn"}
    return client.request("DELETE", f"/api/overrides/{override_id}", json=body, headers=headers)


def _overrides(client: TestClient, symbol: str = "AAPL") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = client.get(f"/api/companies/{symbol}/overrides").json()[
        "overrides"
    ]
    return found


def test_an_applied_override_returns_the_review_and_the_bridge(
    client: TestClient, results: dict[str, ValuationResult], policy: Policy
) -> None:
    mgco_belief = results["AAPL"].intermediates["belief"]["rate"]
    mechanical = results["AAPL"].value
    snapshot = client.get("/api/companies/AAPL").json()["snapshot"]
    r = client.post("/api/companies/AAPL/overrides", json=BELIEF_8, headers=AGENT)
    assert r.status_code == 201
    body = r.json()
    assert (
        body["override"]["state"] == "applied"
        and body["review"]["value"] != body["review"]["mechanicalValue"]
    )
    assert body["bridge"][0]["tag"] == "growth.belief" and body["bridge"][0]["old"] == (
        pytest.approx(mgco_belief)
    )
    latest = client.get("/api/companies/AAPL/reviews/latest").json()
    assert latest["overrideIds"] == [body["override"]["id"]]

    override, review = body["override"], body["review"]
    assert override == {
        "id": override["id"],
        "symbol": "AAPL",
        "tag": "growth.belief",
        "old": mgco_belief,
        "new": 0.08,
        "unit": "ratio",
        "reason": "guidance raised",
        "evidence": [TRANSCRIPT],
        "lifetime": "lasting",
        "period": None,
        "correctedValue": None,
        "snapshotId": snapshot["id"],
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "at": NOW.isoformat(),
        "state": "applied",
        "message": "",
        "reviewId": review["id"],
        "dropReason": None,
        "droppedAt": None,
    }
    belief = Override(override["id"], "growth.belief", 0.08, "agent", "a", NOW, "r")
    inputs = replace(mature_growth_inputs(), symbol="AAPL")
    direct = value_company(inputs, universe_deciles(), policy, NOW.date(), {belief.tag: belief})
    assert review["value"] == pytest.approx(direct.value, abs=1e-9)
    assert (review["snapshotId"], review["refreshId"], review["mechanicalValue"]) == (
        snapshot["id"],
        None,
        mechanical,
    )
    assert (
        review["reviewMethod"] == "fairband-review/1"
        and review["result"]["value"] == (review["value"])
    )
    assert body["bridge"] == review["bridge"] == latest["bridge"]
    assert body["bridge"][0]["delta"] == pytest.approx(review["value"] - mechanical)
    assert body["bridge"][0]["overrideId"] == override["id"]
    [row] = client.get("/api/review-log", params={"symbol": "aapl"}).json()["reviewLog"]
    assert (row["reviewId"], row["refreshId"], row["snapshotId"]) == (
        review["id"],
        None,
        snapshot["id"],
    )
    assert (row["mechanicalValue"], row["reviewedValue"]) == (mechanical, review["value"])
    assert client.get("/api/review-log", params={"symbol": "HGCO"}).json() == {"reviewLog": []}


def test_a_refused_override_is_stored_with_its_state(client: TestClient) -> None:
    r = client.post("/api/companies/AAPL/overrides", json=LOCKED_G, headers=AGENT)
    assert r.status_code == 400
    body = r.json()
    assert body["detail"] == G_T_LOCKED
    assert (body["override"]["state"], body["override"]["message"]) == (
        "refused-locked",
        G_T_LOCKED,
    )
    assert (body["override"]["old"], body["override"]["reviewId"]) == (None, None)
    assert [(o["id"], o["state"]) for o in _overrides(client)] == [
        (body["override"]["id"], "refused-locked")
    ]
    r = client.get("/api/companies/AAPL/reviews/latest")
    assert (r.status_code, r.json()) == (404, {"detail": "no review for AAPL"})
    assert client.get("/api/companies/AAPL/reviews").json() == {"reviews": []}


@pytest.mark.parametrize(
    "body,state,message",
    [
        (BELIEF_8 | {"tag": "beta"}, "refused-not-input", "beta is not an input"),
        (
            BELIEF_8 | {"tag": "margin.target", "new": 0.25},
            "refused-route",
            "the Mature Growth route does not read margin.target",
        ),
        (BELIEF_8 | {"new": 0.7}, "refused-unit", "growth.belief takes −20% to 60%"),
        (BELIEF_8 | {"evidence": []}, "refused-evidence", "an override needs evidence"),
        (
            BELIEF_8 | {"new": 0.5, "evidence": [{"kind": "url", "ref": "a blog", "note": ""}]},
            "refused-evidence",
            "a belief above the base rate's 90th percentile needs a filing or a transcript",
        ),
    ],
)
def test_each_rule_refuses_by_name(
    client: TestClient, body: dict[str, Any], state: str, message: str
) -> None:
    r = client.post("/api/companies/AAPL/overrides", json=body, headers=AGENT)
    assert r.status_code == 400, r.text
    assert (r.json()["override"]["state"], r.json()["detail"]) == (state, message)


def test_the_check_reads_the_route_after_a_phase_override(client: TestClient) -> None:
    """A Mature Growth row put in High Growth takes a target margin; a Young Growth row refused
    for its target margin takes its phase's route."""
    target = BELIEF_8 | {"tag": "margin.target", "new": 0.25}
    phase = _post(client, BELIEF_8 | {"tag": "phase", "new": "High Growth"})
    assert phase["override"]["state"] == "applied"
    assert _post(client, target)["override"]["state"] == "applied"
    young = _post(client, target, "AAL")
    assert young["override"]["state"] == "applied" and young["review"]["value"] is not None
    assert young["review"]["mechanicalValue"] is None  # refused for its target margin
    assert young["bridge"][0]["delta"] == young["review"]["value"]


def test_a_second_override_on_a_tag_replaces_the_first(client: TestClient) -> None:
    first = _post(client, BELIEF_8)["override"]
    second = _post(client, BELIEF_8 | {"new": 0.09})["override"]
    listed = _overrides(client)
    assert [(o["id"], o["state"], o["dropReason"]) for o in listed] == [
        (second["id"], "applied", None),
        (first["id"], "dropped", f"replaced by override {second['id']}"),
    ]
    assert listed[1]["droppedAt"] == NOW.isoformat()
    latest = client.get("/api/companies/AAPL/reviews/latest").json()
    assert latest["overrideIds"] == [second["id"]] and latest["bridge"][0]["new"] == 0.09


def test_a_drop_recomputes_or_clears_the_review(client: TestClient) -> None:
    belief = _post(client, BELIEF_8)["override"]["id"]
    moat = _post(client, MOAT_NARROW)["override"]["id"]
    both = client.get("/api/companies/AAPL/reviews/latest").json()
    assert both["overrideIds"] == [belief, moat]
    assert [line["tag"] for line in both["bridge"]] == ["growth.belief", "moat.class"]

    r = _drop(client, belief)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["override"]["state"], body["override"]["dropReason"]) == (
        "dropped",
        "guidance withdrawn",
    )
    assert body["review"]["overrideIds"] == [moat]
    assert [line["tag"] for line in body["bridge"]] == ["moat.class"]
    latest = client.get("/api/companies/AAPL/reviews/latest").json()
    assert latest["id"] == body["review"]["id"] and latest["value"] != both["value"]

    r = _drop(client, belief)
    assert (r.status_code, r.json()["detail"]) == (
        409,
        f"override {belief} is dropped, not applied",
    )
    r = _drop(client, 99)
    assert (r.status_code, r.json()["detail"]) == (404, "no override 99")

    body = _drop(client, moat).json()
    assert (body["override"]["state"], body["review"], body["bridge"]) == ("dropped", None, [])
    assert client.get("/api/companies/AAPL/reviews/latest").status_code == 404
    reviews = client.get("/api/companies/AAPL/reviews").json()["reviews"]
    assert [r["overrideIds"] for r in reviews] == [[moat], [belief, moat], [belief]]
    assert all("result" not in r and r["bridge"] for r in reviews)


def test_settings_changed_refuses_an_override(client: TestClient) -> None:
    applied = _post(client, BELIEF_8)["override"]["id"]
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1}}, headers=HEADER)
    assert r.status_code == 200
    r = client.post("/api/companies/AAPL/overrides", json=MOAT_NARROW, headers=AGENT)
    assert (r.status_code, r.json()) == (409, {"detail": "settings changed: run a revalue"})
    r = _drop(client, applied)
    assert (r.status_code, r.json()) == (409, {"detail": "settings changed: run a revalue"})
    assert [(o["id"], o["state"]) for o in _overrides(client)] == [(applied, "applied")]


def test_the_owner_neither_adds_nor_drops_an_override(client: TestClient) -> None:
    r = client.post("/api/companies/AAPL/overrides", json=BELIEF_8, headers=HEADER)
    assert (r.status_code, r.json()) == (403, {"detail": OWNERS_REFUSAL})
    applied = _post(client, BELIEF_8)["override"]["id"]
    r = _drop(client, applied, HEADER)
    assert (r.status_code, r.json()) == (403, {"detail": OWNERS_REFUSAL})
    assert [(o["id"], o["state"]) for o in _overrides(client)] == [(applied, "applied")]


def test_every_override_write_is_a_ledger_row(client: TestClient) -> None:
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    first = _post(client, BELIEF_8)["override"]["id"]
    refused = client.post("/api/companies/AAPL/overrides", json=LOCKED_G, headers=AGENT)
    refused_id = refused.json()["override"]["id"]
    second = _post(client, BELIEF_8 | {"new": 0.09})["override"]["id"]
    assert _drop(client, second).status_code == 200
    entries = client.get("/api/companies/AAPL/ledger").json()["entries"]
    assert [(e["kind"], e["refTable"], e["refId"], e["summary"]) for e in entries] == [
        ("override-drop", "overrides", second, "growth.belief dropped: guidance withdrawn"),
        ("override-drop", "overrides", first, f"growth.belief replaced by override {second}"),
        ("override", "overrides", second, "growth.belief applied: guidance raised"),
        ("override", "overrides", refused_id, f"terminal_growth refused-locked: {G_T_LOCKED}"),
        ("override", "overrides", first, "growth.belief applied: guidance raised"),
    ]
    assert {(e["principal"], e["actor"], e["client"], e["snapshotId"]) for e in entries} == {
        ("agent", "claude-opus-5-5", "claude-code/2.1", snapshot_id)
    }


def test_an_override_needs_a_company_with_a_snapshot(client: TestClient) -> None:
    r = client.post("/api/companies/NONE/overrides", json=BELIEF_8, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no snapshot for NONE"})
    r = client.post("/api/companies/AAPL/overrides", json=BELIEF_8 | {"reason": " "}, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": "an override needs a reason"})


def test_a_period_tied_override_keeps_the_value_it_corrected(client: TestClient) -> None:
    hgco = client.get("/api/companies/HGCO").json()
    cash = BELIEF_8 | {"tag": "balance.cash", "new": 5e8, "lifetime": "period-tied"}
    body = _post(client, cash | {"period": "FY2025"}, "HGCO")["override"]
    from_result = current_reading(result_from_json(json.dumps(hgco["result"])), "balance.cash")
    assert (body["lifetime"], body["period"], body["unit"]) == ("period-tied", "FY2025", "USD")
    assert body["old"] == body["correctedValue"] == from_result is not None
    lasting = cash | {"lifetime": "lasting"}
    r = client.post("/api/companies/HGCO/overrides", json=lasting, headers=AGENT)
    assert r.json()["detail"] == "balance.cash is period-tied only"
    for unnamed in (cash, cash | {"period": " "}):
        r = client.post("/api/companies/HGCO/overrides", json=unnamed, headers=AGENT)
        assert (r.status_code, r.json()) == (400, {"detail": NO_PERIOD})
    assert len(_overrides(client, "HGCO")) == 2  # neither stored


def test_the_two_new_inputs_through_the_api(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    stored_inputs: dict[str, CompanyInputs],
) -> None:
    """The value outside the business applies on AAPL with a filing and adds its figure; the
    count refuses a lasting override and applies a period-tied one, which keeps the count it
    corrected; the detail's bridge closes on the two lines under their labels. A Start-up row
    reads the count and not the outside value (spec 2026-11-09 8)."""
    filing = {"kind": "filing", "ref": "10-Q, note 7: equity investments", "note": ""}
    outside = {
        "tag": "value.outside",
        "new": 12.0,
        "reason": "a listed stake, after tax",
        "evidence": [filing],
        "lifetime": "lasting",
    }
    body = _post(client, outside)
    mechanical = results["AAPL"].value
    assert mechanical is not None
    assert (body["override"]["state"], body["override"]["old"], body["override"]["unit"]) == (
        "applied",
        0.0,
        "USD a share",
    )
    assert body["review"]["value"] == pytest.approx(mechanical + 12.0)
    count = results["AAPL"].intermediates["shares"]
    shares = outside | {"tag": "shares.diluted", "new": count * 1.06, "reason": "a forward sale"}
    r = client.post("/api/companies/AAPL/overrides", json=shares, headers=AGENT)
    assert (r.status_code, r.json()["detail"]) == (400, "shares.diluted is period-tied only")
    tied = _post(client, shares | {"lifetime": "period-tied", "period": "Q3 2026"})["override"]
    assert (tied["state"], tied["unit"], tied["old"], tied["correctedValue"]) == (
        "applied",
        "shares",
        count,
        count,
    )
    bridge = client.get("/api/companies/AAPL").json()["review"]["bridge"]
    assert [(line["tag"], line["label"], line["unit"], line["old"]) for line in bridge] == [
        ("shares.diluted", "diluted shares", "shares", count),
        ("value.outside", "outside the business", "USD a share", 0.0),
    ]
    assert bridge[1]["delta"] == pytest.approx(12.0)

    start_up = value_company(start_up_inputs(), universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, start_up, 1, clock=lambda: CREATED)
    stored_inputs["SUCO"] = start_up_inputs()
    r = client.post("/api/companies/SUCO/overrides", json=outside, headers=AGENT)
    assert (r.status_code, r.json()["override"]["state"], r.json()["detail"]) == (
        400,
        "refused-route",
        "the Start-up route does not read value.outside",
    )
    su_count = start_up.intermediates["shares"]
    su_shares = shares | {"new": 2 * su_count, "lifetime": "period-tied", "period": "FY2025"}
    assert _post(client, su_shares, "SUCO")["override"]["state"] == "applied"


def test_the_two_stock_pay_inputs_through_the_api(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    """Spec 2026-11-13 7.2 on AAPL, the Mature Growth golden, whose test reads includes-sbc: the
    basis applies lasting with a filing, and the consensus taken as excluding stock pay lowers the
    value; the stock pay is refused lasting and without a period, and applies period-tied with
    one, keeping the figure it corrected, the stored $400 m; the detail's bridge names both under
    their labels and units, the figure first."""
    filing = {"kind": "filing", "ref": "Q3 2026 release: the adjusted EPS", "note": ""}
    basis = {
        "tag": "earnings.sbc_basis",
        "new": "excludes",
        "reason": "the release's adjusted EPS leaves out stock pay",
        "evidence": [filing],
        "lifetime": "lasting",
    }
    body = _post(client, basis)
    mechanical = results["AAPL"].value
    assert mechanical is not None
    assert (body["override"]["state"], body["override"]["old"], body["override"]["unit"]) == (
        "applied",
        "includes",
        "basis",
    )
    assert body["review"]["value"] < mechanical
    pay = basis | {
        "tag": "earnings.sbc",
        "new": 500e6,
        "reason": "the cash flow statement's stock pay",
        "lifetime": "period-tied",
    }
    r = client.post("/api/companies/AAPL/overrides", json=pay, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": NO_PERIOD})
    r = client.post(
        "/api/companies/AAPL/overrides", json=pay | {"lifetime": "lasting"}, headers=AGENT
    )
    assert (r.status_code, r.json()["detail"]) == (400, "earnings.sbc is period-tied only")
    tied = _post(client, pay | {"period": "Q3 2026"})["override"]
    assert (tied["state"], tied["unit"], tied["old"], tied["correctedValue"]) == (
        "applied",
        "USD",
        400e6,
        400e6,
    )
    bridge = client.get("/api/companies/AAPL").json()["review"]["bridge"]
    assert [(x["tag"], x["label"], x["unit"], x["old"], x["new"]) for x in bridge] == [
        ("earnings.sbc", "stock pay", "USD", 400e6, 500e6),
        ("earnings.sbc_basis", "stock-pay basis", "basis", "includes", "excludes"),
    ]


def test_the_minority_interest_through_the_api(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    stored_inputs: dict[str, CompanyInputs],
) -> None:
    """Spec 2026-11-13 13 on HGCO, its newest sheet now presenting a minority interest of $120 m:
    a lasting ``balance.minority`` is refused; a period-tied one at $500 m applies and keeps the
    $120 m it corrected; the detail's bridge names the line "minority interest" in USD, its delta
    the $380 m more over 100 m shares, −$3.80 a share."""
    held = with_minority(high_growth_inputs(), 120e6)
    valued = value_company(held, universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, valued, 1, clock=lambda: CREATED)
    stored_inputs["HGCO"] = held
    note = {
        "kind": "filing",
        "ref": "10-K, note 14: redeemable noncontrolling interests",
        "note": "",
    }
    minority = {
        "tag": "balance.minority",
        "new": 500e6,
        "reason": "the partners' stake at its redemption value",
        "evidence": [note],
        "lifetime": "lasting",
    }
    r = client.post("/api/companies/HGCO/overrides", json=minority, headers=AGENT)
    assert (r.status_code, r.json()["detail"]) == (400, "balance.minority is period-tied only")
    tied = minority | {"lifetime": "period-tied", "period": "FY2025"}
    body = _post(client, tied, "HGCO")["override"]
    assert (body["state"], body["unit"], body["old"], body["correctedValue"]) == (
        "applied",
        "USD",
        120e6,
        120e6,
    )
    bridge = client.get("/api/companies/HGCO").json()["review"]["bridge"]
    assert [(x["tag"], x["label"], x["unit"], x["old"], x["new"]) for x in bridge] == [
        ("balance.minority", "minority interest", "USD", 120e6, 500e6)
    ]
    assert bridge[0]["delta"] == pytest.approx(-3.80)


def test_a_start_up_put_in_young_growth_meets_the_evidence_rule(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    stored_inputs: dict[str, CompanyInputs],
) -> None:
    """A Start-up row carries no belief and no path, so the cap is its trailing revenue's sales
    class, as the revenue-growth route finds it: a held rate above that class's 90th percentile
    needs a filing or a transcript once the row is put in Young Growth."""
    start_up = start_up_inputs()
    assert start_up.trailing is not None
    inputs = replace(start_up, trailing=replace(start_up.trailing, revenue=50e6))
    result = value_company(inputs, universe_deciles(), policy, TODAY)
    assert (result.phase.phase, result.route, result.value) == ("Start-up", "start-up", None)
    assert "belief" not in result.intermediates and "path" not in result.intermediates
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, result, 1, clock=lambda: CREATED)
    stored_inputs["SUCO"] = inputs
    cap = sales_class(50.0, policy).sales_p90_5y
    young = BELIEF_8 | {"tag": "phase", "new": "Young Growth", "reason": "it sells now"}
    assert _post(client, young, "SUCO")["override"]["state"] == "applied"
    hold = BELIEF_8 | {"tag": "path.hold", "new": cap + 0.5, "reason": "the order book"}
    blog = {"kind": "url", "ref": "https://example.com/orders", "note": ""}
    r = client.post(
        "/api/companies/SUCO/overrides", json=hold | {"evidence": [blog]}, headers=AGENT
    )
    assert r.status_code == 400
    assert (r.json()["override"]["state"], r.json()["detail"]) == (
        "refused-evidence",
        "a held rate above the base rate's 90th percentile needs a filing or a transcript",
    )
    assert _post(client, hold, "SUCO")["override"]["state"] == "applied"  # a transcript


def test_a_company_in_another_currency_reads_its_ranges_and_cap_in_it(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    stored_inputs: dict[str, CompanyInputs],
) -> None:
    """FXCO reports in SEK at 8.0 SEK per USD with an inflation differential of 2% (spec
    2026-11-10 7.3): earnings.ntm takes above 0 to 8,000 SEK a share, the override's unit is in
    SEK, and the evidence rule's cap is the 90th percentile of the class of its trailing revenue
    in USD, 18,240 m SEK ÷ 8.0 = USD 2,280 m (20%), restated to 22.4%: a belief of 21% needs no
    filing (the class of 18,240 m read as USD would cap it at 15%), one of 23% does."""
    inputs = fx_inputs()
    result = value_company(inputs, universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, result, 1, clock=lambda: CREATED)
    stored_inputs["FXCO"] = inputs
    eps = BELIEF_8 | {"tag": "earnings.ntm", "new": 9_000.0, "reason": "guided"}
    r = client.post("/api/companies/FXCO/overrides", json=eps, headers=AGENT)
    assert r.status_code == 400
    assert (r.json()["override"]["state"], r.json()["detail"]) == (
        "refused-unit",
        "earnings.ntm takes above 0 to 8,000 SEK a share",
    )
    assert r.json()["override"]["unit"] == "SEK a share"
    blog = {"kind": "url", "ref": "https://example.com/orders", "note": ""}
    above = BELIEF_8 | {"new": 0.23, "evidence": [blog]}
    r = client.post("/api/companies/FXCO/overrides", json=above, headers=AGENT)
    assert (r.status_code, r.json()["override"]["state"]) == (400, "refused-evidence")
    within = _post(client, BELIEF_8 | {"new": 0.21, "evidence": [blog]}, "FXCO")
    assert within["override"]["state"] == "applied" and within["review"]["value"] is not None


def _moved(snapshot_id: int) -> dict[str, str]:
    return {"detail": f"the store moved since snapshot {snapshot_id}: run a revalue"}


def test_an_override_on_a_store_that_moved_is_refused(
    client: TestClient, stored_inputs: dict[str, CompanyInputs]
) -> None:
    """A peer's figures changed after HGCO's snapshot (a scoped refresh of the peer, say): the
    engine on today's store no longer gives the snapshot's value, so the recompute would put the
    store's move on the override's line. It is refused and nothing is stored."""
    snapshot_id = client.get("/api/companies/HGCO").json()["snapshot"]["id"]
    ledger = client.get("/api/companies/HGCO/ledger").json()["entries"]
    hgco = stored_inputs["HGCO"]
    peers = tuple(replace(p, margin=0.25) if p.symbol == "PEER2" else p for p in hgco.peers)
    stored_inputs["HGCO"] = replace(hgco, peers=peers)  # the peers' median margin moves
    target = BELIEF_8 | {"tag": "margin.target", "new": 0.25}
    r = client.post("/api/companies/HGCO/overrides", json=target, headers=AGENT)
    assert (r.status_code, r.json()) == (409, _moved(snapshot_id))
    assert _overrides(client, "HGCO") == []
    assert client.get("/api/companies/HGCO/reviews").json() == {"reviews": []}
    assert client.get("/api/companies/HGCO/ledger").json()["entries"] == ledger


def test_new_deciles_refuse_an_override_and_a_drop(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """A full refresh stored its deciles after AAPL's snapshot and has not valued AAPL yet: on
    them the classifier puts AAPL in Mature Stable, so no review is recomputed from the old
    snapshot until a revalue."""
    belief = _post(client, BELIEF_8)["override"]["id"]
    moat = _post(client, MOAT_NARROW)["override"]["id"]
    snapshot_id = client.get("/api/companies/AAPL").json()["snapshot"]["id"]
    reviews = client.get("/api/companies/AAPL/reviews").json()
    deciles = universe_deciles()
    higher = replace(deciles, growth_edges=tuple(e + 0.1 for e in deciles.growth_edges))
    with closing(connect(db_path)) as conn:
        refresh_id = create_refresh(
            conn, "full", None, policy.version, METHOD_VERSION, NOW, EMPTY_SETTINGS_HASH
        )
        save_deciles(conn, refresh_id, higher, NOW)
    r = client.post("/api/companies/AAPL/overrides", json=BELIEF_8 | {"new": 0.09}, headers=AGENT)
    assert (r.status_code, r.json()) == (409, _moved(snapshot_id))
    r = _drop(client, belief)
    assert (r.status_code, r.json()) == (409, _moved(snapshot_id))
    assert [(o["id"], o["state"]) for o in _overrides(client)] == [
        (moat, "applied"),
        (belief, "applied"),
    ]
    assert client.get("/api/companies/AAPL/reviews").json() == reviews


def test_a_review_after_the_next_earnings_date_keeps_its_snapshot_s_window(
    client_with_clock: Callable[[datetime], TestClient],
    stored_inputs: dict[str, CompanyInputs],
) -> None:
    """Past AAPL's next earnings date the store gives no next earnings date, so the engine on
    today's inputs would end the window at the fallback; a review carries its snapshot's window."""
    aapl = stored_inputs["AAPL"]
    assert aapl.next_earnings is not None
    stored_inputs["AAPL"] = replace(aapl, next_earnings=None)  # as build_inputs reads it then
    later = client_with_clock(
        datetime.combine(aapl.next_earnings + timedelta(days=1), NOW.timetz())
    )
    window = later.get("/api/companies/AAPL").json()["result"]["valid_until"]
    assert window == aapl.next_earnings.isoformat()
    review = _post(later, BELIEF_8)["review"]
    assert review["result"]["valid_until"] == window
    latest = later.get("/api/companies/AAPL/reviews/latest").json()
    assert latest["result"]["valid_until"] == window


def test_a_review_written_days_later_carries_its_snapshot_s_price_facts(
    client_with_clock: Callable[[datetime], TestClient],
) -> None:
    """An override written days after the snapshot: the engine on that day would anchor the
    one-year change on a later reference close, but the review shows the snapshot's price facts,
    which the refresh computed on its own date (B-132)."""
    later = client_with_clock(NOW + timedelta(days=8))
    snapshot = later.get("/api/companies/AAPL").json()["result"]["intermediates"]["price_facts"]
    review = _post(later, BELIEF_8)["review"]["result"]["intermediates"]["price_facts"]
    assert review == snapshot
    latest = later.get("/api/companies/AAPL/reviews/latest").json()
    assert latest["result"]["intermediates"]["price_facts"] == snapshot


def _guidance(
    client: TestClient,
    symbol: str,
    metric: str,
    low: float,
    high: float,
    call: str = "2026-10-28",
    period: str = "2027",
    basis: str = "gaap",
) -> int:
    body = {
        "metric": metric,
        "period": period,
        "low": low,
        "high": high,
        "basis": basis,
        "asOf": call,
        "text": "We guide fiscal 2027.",
        "source": "response:12/0/content",
    }
    r = client.post(f"/api/companies/{symbol}/guidance", json=body, headers=AGENT)
    assert r.status_code == 201, r.text
    guidance_id: int = r.json()["id"]
    return guidance_id


def test_an_ntm_override_cites_a_guidance_record(
    client: TestClient, results: dict[str, ValuationResult]
) -> None:
    """An NTM anchor override needs a guidance record of the company among its evidence: one of
    another company's is a 404, a ref that names none a 400, neither storing the override; with
    no guidance item it is refused and stored; a good one applies, and its bridge line comes
    right after the phase's."""
    ours = _guidance(client, "AAPL", "eps", 6.30, 6.60)
    theirs = _guidance(client, "HGCO", "revenue", 12.5e9, 12.7e9)
    ntm = BELIEF_8 | {"tag": "earnings.ntm", "new": 6.45, "reason": "guided 6.30 to 6.60"}
    cite = {"kind": "guidance", "ref": f"guidance:{theirs}", "note": "FY2027 EPS"}
    r = client.post("/api/companies/AAPL/overrides", json=ntm | {"evidence": [cite]}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": f"no guidance record {theirs} for AAPL"})
    # an id past the store's integers names no record either: a 404, not a server error
    huge = cite | {"ref": "guidance:99999999999999999999"}
    r = client.post("/api/companies/AAPL/overrides", json=ntm | {"evidence": [huge]}, headers=AGENT)
    assert (r.status_code, r.json()) == (
        404,
        {"detail": "no guidance record 99999999999999999999 for AAPL"},
    )
    bad = cite | {"ref": "the Q3 call"}
    r = client.post("/api/companies/AAPL/overrides", json=ntm | {"evidence": [bad]}, headers=AGENT)
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "a guidance item cites its record as guidance:<id>"},
    )
    assert _overrides(client) == []
    r = client.post("/api/companies/AAPL/overrides", json=ntm, headers=AGENT)  # a transcript only
    refused = "an NTM anchor override needs a guidance record among its evidence"
    assert (r.status_code, r.json()["detail"]) == (400, refused)
    assert r.json()["override"]["state"] == "refused-evidence"
    _post(client, BELIEF_8 | {"tag": "phase", "new": "Mature Growth"})
    _post(client, BELIEF_8)
    good = ntm | {"evidence": [cite | {"ref": f"guidance:{ours}"}, TRANSCRIPT]}
    body = _post(client, good)
    assert body["override"]["state"] == "applied"
    assert body["override"]["unit"] == "USD a share"
    assert [line["tag"] for line in body["bridge"]] == ["phase", "earnings.ntm", "growth.belief"]
    line = body["bridge"][1]
    found = results["AAPL"].intermediates["anchor"]["ntm_eps"]
    assert (line["old"], line["new"]) == (pytest.approx(found), 6.45)
    assert line["delta"] > 0
    revenue = BELIEF_8 | {"tag": "revenue.ntm", "new": 12.6e9, "reason": "guided"}
    on_hgco = _post(client, revenue | {"evidence": [cite]}, "HGCO")
    assert [line["tag"] for line in on_hgco["bridge"]] == ["revenue.ntm"]


NTM_EPS = BELIEF_8 | {"tag": "earnings.ntm", "new": 6.45, "reason": "guided 6.30 to 6.60"}
MISFIT_EPS = "an NTM anchor override needs a gaap guidance record of eps for a fiscal year"


@pytest.mark.parametrize(
    ("metric", "period", "basis"),
    [("eps", "2027", "adjusted"), ("revenue", "2027", "gaap"), ("eps", "2027Q1", "gaap")],
)
def test_an_ntm_override_needs_a_record_that_fits_its_anchor(
    client: TestClient, metric: str, period: str, basis: str
) -> None:
    """The NTM EPS takes a gaap EPS record for a fiscal year: an adjusted record, a revenue record
    and a quarter's are each refused 400 with nothing stored; the gaap fiscal-year EPS record
    beside one of them applies."""
    _post(client, BELIEF_8 | {"tag": "phase", "new": "Mature Growth"})
    misfit = _guidance(client, "AAPL", metric, 6.30, 6.60, period=period, basis=basis)
    before = _overrides(client)
    r = client.post("/api/companies/AAPL/overrides", json=_citing(misfit), headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": MISFIT_EPS})
    assert _overrides(client) == before
    fits = _guidance(client, "AAPL", "eps", 6.30, 6.60)
    both = _citing(fits)
    both["evidence"].insert(0, _citing(misfit)["evidence"][0])
    assert _post(client, both)["override"]["state"] == "applied"


def test_an_ntm_revenue_override_needs_a_gaap_fiscal_year_revenue_record(
    client: TestClient,
) -> None:
    eps = _guidance(client, "HGCO", "eps", 1.0, 1.2)
    cite = {"kind": "guidance", "ref": f"guidance:{eps}", "note": "FY2027 EPS"}
    revenue = BELIEF_8 | {"tag": "revenue.ntm", "new": 12.6e9, "reason": "guided"}
    r = client.post(
        "/api/companies/HGCO/overrides", json=revenue | {"evidence": [cite]}, headers=AGENT
    )
    detail = "an NTM anchor override needs a gaap guidance record of revenue for a fiscal year"
    assert (r.status_code, r.json()) == (400, {"detail": detail})


def _citing(guidance_id: int) -> dict[str, Any]:
    """The NTM EPS override with the guidance record ``guidance_id`` among its evidence."""
    cite = {"kind": "guidance", "ref": f"guidance:{guidance_id}", "note": "FY2027 EPS"}
    return NTM_EPS | {"evidence": [cite, TRANSCRIPT]}


def test_an_override_citing_a_superseded_record_is_refused(client: TestClient) -> None:
    """A later call's figure supersedes the earlier one, so an NTM anchor never rests on a record
    a later call replaced: 409, nothing stored."""
    earlier = _guidance(client, "AAPL", "eps", 6.00, 6.40, call="2026-07-29")
    later = _guidance(client, "AAPL", "eps", 6.30, 6.60)
    r = client.post("/api/companies/AAPL/overrides", json=_citing(earlier), headers=AGENT)
    detail = f"guidance record {earlier} is superseded by record {later}"
    assert (r.status_code, r.json()) == (409, {"detail": detail})
    assert _overrides(client) == []
    assert _post(client, _citing(later))["override"]["state"] == "applied"


def test_an_applied_override_stands_when_a_later_call_supersedes_its_record(
    client: TestClient,
) -> None:
    """The accepted case: an override applied on the current record stays applied, its review as
    it was, when a later call's record supersedes the one it cites; Appendix A shows the record's
    state. A new override citing the superseded record is refused."""
    cited = _guidance(client, "AAPL", "eps", 6.30, 6.60)
    applied = _post(client, _citing(cited))
    review = client.get("/api/companies/AAPL/reviews/latest").json()
    newer = _guidance(client, "AAPL", "eps", 6.50, 6.70, call="2027-01-27")
    [override] = _overrides(client)
    assert (override["id"], override["state"]) == (applied["override"]["id"], "applied")
    assert client.get("/api/companies/AAPL/reviews/latest").json() == review
    listed = client.get("/api/companies/AAPL/guidance").json()["guidance"]
    assert [(g["id"], g["supersededBy"]) for g in listed] == [(newer, None), (cited, newer)]
    r = client.post("/api/companies/AAPL/overrides", json=_citing(cited), headers=AGENT)
    assert r.status_code == 409
