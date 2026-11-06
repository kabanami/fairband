"""The override and review routes (spec 2026-11-06 Tier 2, 10.1 to 10.6 and 16), on the database of
``conftest.py``: AAPL (the Mature Growth golden), AAL (Young Growth, refused for its target margin)
and HGCO, each with one snapshot. The database stores no statements, so the routes build each
company's inputs as the conftest valued them, on the universe deciles stored under its full
refresh."""

import json
import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date
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
from support.web import CREATED, HEADER, NOW

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import Override, current_reading
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import ValuationResult, result_from_json
from fairband.policy import Policy
from fairband.policy.tax import TaxTable
from fairband.store.db import connect
from fairband.store.refreshes import save_deciles
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
def stored_inputs(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        assert deciles == universe_deciles()  # the stored deciles
        return inputs[symbol]

    monkeypatch.setattr(reviews_api, "build_inputs", build)


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
