"""The sensitivity reading's routes (spec 2026-11-06 Tier 2, 13.8 and 13.2), on the database of
``conftest.py``: AAPL (the Mature Growth golden), AAL (Young Growth, refused for its target
margin) and HGCO (High Growth), each with one snapshot. The database stores no statements, so
the routes build each company's inputs as the conftest valued them, on the universe deciles stored
under its full refresh, as in ``test_reviews_api``."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import high_growth_inputs, mature_growth_inputs, universe_deciles
from support.web import CREATED, HEADER, NOW

from fairband.engine.classifier import Deciles
from fairband.engine.overrides import Override, OverrideTag
from fairband.engine.route import CompanyInputs, value_company
from fairband.engine.types import Route
from fairband.policy import Policy
from fairband.policy.settings import EMPTY_SETTINGS_HASH
from fairband.policy.tax import TaxTable
from fairband.reports.check import UNRESOLVED, WRONG_SNAPSHOT, headings, required_judgments
from fairband.store.db import connect
from fairband.store.refreshes import latest_deciles, save_deciles
from fairband.store.snapshots import insert_snapshot
from fairband.web import reviews_api
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER

AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
TRANSCRIPT = {"kind": "transcript", "ref": "Q3 call", "note": ""}
# AAPL's grid: the belief at 5% and 8% by the runway return at 10% and 20%.
GRID = {
    "rowTag": "growth.belief",
    "rowValues": [0.05, 0.08],
    "colTag": "return.runway",
    "colValues": [0.10, 0.20],
}
# HGCO's grid: a held rate of −20% at an 8% target margin leaves no positive value.
REFUSED_CELL = {
    "rowTag": "path.hold",
    "rowValues": [-0.20, 0.15],
    "colTag": "margin.target",
    "colValues": [0.08, 0.20],
}
OWNERS_REFUSAL = "a sensitivity reading is an agent's write"


@pytest.fixture(autouse=True)
def stored_inputs(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, CompanyInputs]:
    """The inputs the routes build for each company, by symbol; a test may change one, as a
    store change would."""
    with closing(connect(db_path)) as conn:
        save_deciles(conn, 1, universe_deciles(), CREATED)
    inputs = {"AAPL": replace(mature_growth_inputs(), symbol="AAPL"), "HGCO": high_growth_inputs()}

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
    r = client.post(f"/api/companies/{symbol}/sensitivities", json=body, headers=AGENT)
    assert r.status_code == 201, r.text
    return r.json()


def _engine(
    inputs: CompanyInputs, policy: Policy, values: dict[OverrideTag, float | str]
) -> float | None:
    """The value a share under ``values``, as the route's engine computes it today."""
    applied = {t: Override(1, t, v, "agent", "a", NOW, "r") for t, v in values.items()}
    return value_company(inputs, universe_deciles(), policy, NOW.date(), applied).value


def _snapshot_id(client: TestClient, symbol: str = "AAPL") -> int:
    found: int = client.get(f"/api/companies/{symbol}").json()["snapshot"]["id"]
    return found


def _report(route: Route, *parts: Any) -> dict[str, Any]:
    """A full report whose summary is ``parts`` and whose other sections are plain words, with
    the judgments ``route`` needs."""
    rest = [{"heading": h, "parts": ["Plain words."]} for h in headings("full report")[1:]]
    judgments = [{"judgment": k, "decision": f"keep the {k}"} for k in required_judgments(route)]
    return {
        "mode": "full report",
        "stance": "hold",
        "sections": [{"heading": "Summary", "parts": list(parts)}, *rest],
        "judgments": judgments,
    }


def _sensitivities(client: TestClient, symbol: str = "AAPL") -> list[dict[str, Any]]:
    entries = client.get(f"/api/companies/{symbol}/ledger").json()["entries"]
    return [e for e in entries if e["kind"] == "sensitivity"]


@pytest.mark.usefixtures("secondaries")  # a report needs one on its snapshot
def test_a_sensitivity_is_stored_and_cited(
    client: TestClient, stored_inputs: dict[str, CompanyInputs], policy: Policy
) -> None:
    sid = _snapshot_id(client)
    found = _post(client, GRID)
    cells = [
        [
            _engine(stored_inputs["AAPL"], policy, {"growth.belief": b, "return.runway": c})
            for c in GRID["colValues"]
        ]
        for b in GRID["rowValues"]
    ]
    assert found == {
        "id": found["id"],
        "symbol": "AAPL",
        "snapshotId": sid,
        "reviewId": None,  # no override applied
        "createdAt": NOW.isoformat(),
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "rowTag": "growth.belief",
        "colTag": "return.runway",
        "rowValues": [0.05, 0.08],
        "colValues": [0.10, 0.20],
        "cells": cells,
        "current": None,  # AAPL's belief is 6.3%
        "policyVersion": policy.version,
        "settingsHash": EMPTY_SETTINGS_HASH,
        # the export's title and words for the reading's table (charts.reading_axes), which the
        # report page draws its grid with (spec 18.4)
        "title": f"Sensitivity {found['id']}: the belief by the runway return",
        "rowLabel": "belief",
        "colLabel": "runway return",
        "rowWords": ["5.0%", "8.0%"],
        "colWords": ["10.0%", "20.0%"],
    }
    assert client.get(f"/api/sensitivities/{found['id']}").json() == found
    [entry] = _sensitivities(client)
    assert (entry["refTable"], entry["refId"], entry["snapshotId"], entry["actor"]) == (
        "sensitivities",
        found["id"],
        sid,
        "claude-opus-5-5",
    )
    assert entry["summary"] == "growth.belief by return.runway, a grid of two rows and two columns"
    assert client.get("/api/companies/AAPL/overrides").json() == {"overrides": []}  # a reading
    assert client.get("/api/companies/AAPL/reviews").json() == {"reviews": []}

    cell = cells[0][1]  # row 1, column 2: the belief at 5% and the runway return at 20%
    assert cell is not None
    cite = {"cite": f"${cell:,.0f}", "ref": f"sensitivity:{found['id']}/1/2"}
    r = client.post(
        "/api/companies/AAPL/reports", json=_report("mature-growth", cite), headers=AGENT
    )
    assert r.status_code == 201, r.text
    report = r.json()["report"]
    assert report["snapshotId"] == sid
    [listed] = report["references"]
    assert listed["source"] == f"sensitivity {found['id']}, row 1 column 2"
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    assert f"### Sensitivity {found['id']}: the belief by the runway return" in text


@pytest.mark.usefixtures("secondaries")
def test_a_refused_cell_is_null_and_cannot_be_cited(
    client: TestClient, stored_inputs: dict[str, CompanyInputs], policy: Policy
) -> None:
    found = _post(client, REFUSED_CELL, "HGCO")
    hgco = stored_inputs["HGCO"]
    assert found["cells"][0][0] is None
    assert found["cells"][1] == [
        _engine(hgco, policy, {"path.hold": 0.15, "margin.target": m}) for m in (0.08, 0.20)
    ]
    assert found["current"] == [2, 2]  # HGCO holds 15% at a 20% target margin
    s = f"sensitivity:{found['id']}"
    cites = [{"cite": "$1", "ref": f"{s}/1/1"}, {"cite": "$1", "ref": f"{s}/3/1"}]
    r = client.post(
        "/api/companies/HGCO/reports", json=_report("revenue-growth", *cites), headers=AGENT
    )
    assert r.status_code == 422, r.text
    assert r.json()["findings"] == [
        {"where": "section 1, part 1: $1", "what": UNRESOLVED, "detail": f"{s}/1/1 holds no value"},
        {
            "where": "section 1, part 2: $1",
            "what": UNRESOLVED,
            "detail": f"{s}/3/1 names no stored value",
        },
    ]


@pytest.mark.parametrize(
    "change,sentence",
    [
        ({"rowTag": "terminal_growth"}, "g_T is a locked input: the terminal growth ceiling"),
        ({"rowTag": "beta"}, "beta is not an input"),
        (
            {"colTag": "margin.target", "colValues": [0.25]},
            "the Mature Growth route does not read margin.target",
        ),
        ({"rowValues": [0.05, 0.7]}, "growth.belief takes −20% to 60%"),
        ({"colValues": [0.10, "high"]}, "return.runway takes 0% to 100%"),
        ({"rowValues": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]}, "an axis holds one to five values"),
        ({"colValues": []}, "an axis holds one to five values"),
        ({"colTag": "growth.belief"}, "the two tags differ"),
    ],
)
def test_a_sensitivity_refuses_as_an_override_would(
    client: TestClient, change: dict[str, Any], sentence: str
) -> None:
    r = client.post("/api/companies/AAPL/sensitivities", json=GRID | change, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": sentence})
    assert _sensitivities(client) == []
    assert client.get("/api/sensitivities/1").status_code == 404


def test_the_route_is_the_row_s_with_its_phase(
    client: TestClient, stored_inputs: dict[str, CompanyInputs], policy: Policy
) -> None:
    """An applied phase override sets the route the tags are read on, and the review's id is
    stored; with the phase on an axis, the other input is read on each of its phases' routes.
    AAPL put in Mature Stable is valued, its moat Wide."""
    stable = {
        "tag": "phase",
        "new": "Mature Stable",
        "reason": "growth has stopped",
        "evidence": [TRANSCRIPT],
        "lifetime": "lasting",
    }
    r = client.post("/api/companies/AAPL/overrides", json=stable, headers=AGENT)
    assert r.status_code == 201, r.text
    review_id = r.json()["review"]["id"]
    r = client.post("/api/companies/AAPL/sensitivities", json=GRID, headers=AGENT)
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "the Mature Stable route does not read growth.belief"},
    )
    phases = {
        "rowTag": "phase",
        "rowValues": ["Mature Growth", "Mature Stable"],
        "colTag": "growth.belief",
        "colValues": [0.05],
    }
    r = client.post("/api/companies/AAPL/sensitivities", json=phases, headers=AGENT)
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "the Mature Stable route does not read growth.belief"},
    )
    found = _post(client, phases | {"colTag": "moat.class", "colValues": ["Narrow", "Wide"]})
    assert found["reviewId"] == review_id
    assert found["current"] == [2, 2]  # the applied phase, and the moat it reads, Wide
    aapl = stored_inputs["AAPL"]
    assert found["cells"] == [
        [_engine(aapl, policy, {"phase": phase, "moat.class": moat}) for moat in ("Narrow", "Wide")]
        for phase in ("Mature Growth", "Mature Stable")
    ]
    assert found["cells"][1][1] == client.get("/api/companies/AAPL/reviews/latest").json()["value"]


def test_an_unclassified_row_reads_an_input_only_with_a_phase(
    client: TestClient, db_path: Path, stored_inputs: dict[str, CompanyInputs], policy: Policy
) -> None:
    """A row with one fiscal year has no phase: it reads no input until a phase is set, here by
    the phase axis itself, on whose routes the moat is read."""
    aapl = stored_inputs["AAPL"]
    unclassified = replace(aapl, symbol="UNCL", series=aapl.series[:1])
    result = value_company(unclassified, universe_deciles(), policy, NOW.date())
    assert (result.phase.phase, result.refusal) == (None, "fewer than two fiscal years")
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, result, 1, clock=lambda: CREATED)
    stored_inputs["UNCL"] = unclassified
    r = client.post("/api/companies/UNCL/sensitivities", json=GRID, headers=AGENT)
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "an unclassified row reads no growth.belief: set its phase first"},
    )
    phases = {
        "rowTag": "phase",
        "rowValues": ["Mature Growth", "Mature Stable"],
        "colTag": "moat.class",
        "colValues": ["Narrow", "Wide"],
    }
    found = _post(client, phases, "UNCL")
    assert found["current"] is None  # no phase in force
    assert found["cells"] == [
        [
            _engine(unclassified, policy, {"phase": phase, "moat.class": moat})
            for moat in ("Narrow", "Wide")
        ]
        for phase in ("Mature Growth", "Mature Stable")
    ]


def test_settings_changed_refuses_a_sensitivity(client: TestClient) -> None:
    r = client.put("/api/settings", json={"changes": {"required_return": 0.1}}, headers=HEADER)
    assert r.status_code == 200
    r = client.post("/api/companies/AAPL/sensitivities", json=GRID, headers=AGENT)
    assert (r.status_code, r.json()) == (409, {"detail": "settings changed: run a revalue"})
    assert _sensitivities(client) == []


def test_a_sensitivity_on_a_store_that_moved_is_refused(
    client: TestClient, stored_inputs: dict[str, CompanyInputs]
) -> None:
    sid = _snapshot_id(client, "HGCO")
    hgco = stored_inputs["HGCO"]
    peers = tuple(replace(p, margin=0.25) if p.symbol == "PEER2" else p for p in hgco.peers)
    stored_inputs["HGCO"] = replace(hgco, peers=peers)  # the peers' median margin moves
    r = client.post("/api/companies/HGCO/sensitivities", json=REFUSED_CELL, headers=AGENT)
    assert (r.status_code, r.json()) == (
        409,
        {"detail": f"the store moved since snapshot {sid}: run a revalue"},
    )
    assert _sensitivities(client, "HGCO") == []


def test_the_owner_cannot_post_a_sensitivity(client: TestClient) -> None:
    r = client.post("/api/companies/AAPL/sensitivities", json=GRID, headers=HEADER)
    assert (r.status_code, r.json()) == (403, {"detail": OWNERS_REFUSAL})
    assert _sensitivities(client) == []


def test_a_missing_company_or_record_is_404(client: TestClient) -> None:
    r = client.post("/api/companies/ZZZZ/sensitivities", json=GRID, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no snapshot for ZZZZ"})
    r = client.get("/api/sensitivities/99")
    assert (r.status_code, r.json()) == (404, {"detail": "no sensitivity 99"})


@pytest.mark.usefixtures("secondaries")
def test_a_reading_goes_stale_when_the_review_moves(client: TestClient) -> None:
    """A reading taken under no review, then an override on the same snapshot: the company's
    current review is a new one, so a cite of the reading is wrong snapshot, "the review moved";
    a reading taken under the new review cites, until the next override moves it too."""
    sid = _snapshot_id(client)
    first = _post(client, GRID)
    assert first["reviewId"] is None
    moat = {
        "tag": "moat.class",
        "new": "Narrow",
        "reason": "the patents lapse",
        "evidence": [TRANSCRIPT],
        "lifetime": "lasting",
    }
    r = client.post("/api/companies/AAPL/overrides", json=moat, headers=AGENT)
    assert r.status_code == 201, r.text
    review_id = r.json()["review"]["id"]
    assert r.json()["review"]["snapshotId"] == sid  # the same snapshot

    def submitted(reading: dict[str, Any]) -> Any:
        cell = reading["cells"][0][0]
        cite = {"cite": f"${cell:,.0f}", "ref": f"sensitivity:{reading['id']}/1/1"}
        body = _report("mature-growth", cite)
        return client.post("/api/companies/AAPL/reports", json=body, headers=AGENT)

    r = submitted(first)
    assert r.status_code == 422, r.text
    ref = f"sensitivity:{first['id']}/1/1"
    [finding] = r.json()["findings"]
    assert (finding["what"], finding["detail"]) == (
        WRONG_SNAPSHOT,
        f"{ref} was taken under no review: the review moved, so take the reading again",
    )
    second = _post(client, GRID)
    assert second["reviewId"] == review_id
    belief = moat | {"tag": "growth.belief", "new": 0.08, "reason": "the cycle"}
    r = client.post("/api/companies/AAPL/overrides", json=belief, headers=AGENT)
    assert r.status_code == 201, r.text
    r = submitted(second)
    [finding] = r.json()["findings"]
    moved = f"was taken under review {review_id}: the review moved, so take the reading again"
    assert (finding["what"], finding["detail"]) == (
        WRONG_SNAPSHOT,
        f"sensitivity:{second['id']}/1/1 {moved}",
    )
    third = _post(client, GRID)
    assert submitted(third).status_code == 201
