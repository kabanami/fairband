"""The drawer's reads (spec 2026-11-06 Tier 2, 16, 18.2 and 18.3), on the database of
``conftest.py``: AAPL valued on the Mature Growth route, AAL refused for its target margin and HGCO
valued on the revenue growth route, each with one snapshot.

The company detail carries the agents' records its main view leads with: the current review and
the newest secondary valuation when they rest on the latest snapshot or one it reprices (the
screen's rule), the latest published report with its Summary, and the open work item.
``GET /api/companies/{symbol}/research`` serves what Details lists, each record as its own read
serves it."""

from collections.abc import Callable
from contextlib import closing
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from support.engine_companies import mature_growth_inputs, universe_deciles
from support.web import HEADER, NOW, TODAY

from fairband.engine.designation import designation_for
from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import reprice
from fairband.engine.secondary import Drivers, Part, secondary_value
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.store.db import connect
from fairband.store.ledger import OWNER, Writer
from fairband.store.overrides import insert_override
from fairband.store.reports import insert_judgments, insert_report
from fairband.store.reviews import insert_review
from fairband.store.secondary import insert_secondary, secondary_row
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER

AT = NOW.isoformat()
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
AGENT_HEADERS = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
PUBLISHED = datetime(2026, 11, 1, 8, 0, tzinfo=UTC)
KINDS = ("overrides", "guidance", "judgments", "killCriteria", "newsItems", "notes", "findings")


def _latest(db_path: Path, symbol: str) -> int:
    with closing(connect(db_path)) as conn:
        snapshot = latest_snapshot(conn, symbol)
    assert snapshot is not None
    return snapshot.id


def _override(db_path: Path, results: dict[str, ValuationResult]) -> int:
    """An applied growth.belief override of AAPL at 8%; its id."""
    with closing(connect(db_path)) as conn:
        return insert_override(
            conn,
            "AAPL",
            "growth.belief",
            results["AAPL"].intermediates["belief"]["rate"],
            0.08,
            "ratio",
            "guidance raised",
            [{"kind": "guidance", "ref": "guidance:1", "note": "the Q3 call"}],
            "lasting",
            None,
            None,
            _latest(db_path, "AAPL"),
            AGENT,
            NOW,
            "applied",
            "",
        )


def _review(
    db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> tuple[int, Review]:
    """The override and the review it produced on AAPL's snapshot."""
    override_id = _override(db_path, results)
    belief = Override(override_id, "growth.belief", 0.08, "agent", AGENT.actor, NOW, "raised")
    inputs = replace(mature_growth_inputs(), symbol="AAPL")
    review = review_company(inputs, universe_deciles(), policy, TODAY, [belief], results["AAPL"])
    with closing(connect(db_path)) as conn:
        insert_review(conn, review, "AAPL", _latest(db_path, "AAPL"), None, clock=lambda: NOW)
    assert review.result.value is not None
    return override_id, review


def _report(
    db_path: Path,
    symbol: str,
    stance: str,
    sections: list[dict[str, Any]],
    writer: Writer = AGENT,
) -> int:
    with closing(connect(db_path)) as conn:
        return insert_report(
            conn,
            symbol,
            "full report",
            stance,
            sections,
            None,
            _latest(db_path, symbol),
            None,
            None,
            None,
            writer,
            PUBLISHED,
        )


def _cited_sections(sid: int) -> list[dict[str, Any]]:
    """A Summary citing the price, and a second section citing r and the price again."""
    price = {"cite": "$150.00", "ref": f"snapshot:{sid}/price"}
    return [
        {"heading": "Summary", "parts": ["The price of ", price, " is below the value."]},
        {
            "heading": "The business",
            "parts": [
                "It clears ",
                {"cite": "9.0%", "ref": "policy:required_return"},
                " at ",
                price,
            ],
        },
    ]


def _detail(client: TestClient, symbol: str) -> dict[str, Any]:
    response = client.get(f"/api/companies/{symbol}")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _research(client: TestClient, symbol: str) -> dict[str, Any]:
    response = client.get(f"/api/companies/{symbol}/research")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _post(client: TestClient, url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
    response = client.post(url, json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


# ------------------------------------------------------------------ the detail's records


def test_the_detail_carries_the_review_with_its_bridge(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    override_id, review = _review(db_path, policy, results)
    value, levels = review.result.value, review.result.levels
    assert value is not None and levels is not None
    mechanical = results["AAPL"].value
    assert mechanical is not None
    (line,) = review.bridge
    found = _detail(client, "AAPL")["review"]
    assert found == {
        "id": found["id"],
        "value": value,
        "levels": {
            "buy": levels.buy,
            "fairLow": levels.fair_low,
            "fairHigh": levels.fair_high,
            "trim": levels.trim,
        },
        "refusal": None,
        "bridge": [
            {
                "overrideId": override_id,
                "tag": "growth.belief",
                "label": "belief",  # the reader's word for the input (overrides.LABELS)
                "old": results["AAPL"].intermediates["belief"]["rate"],
                "new": 0.08,
                "unit": "ratio",
                "delta": line.delta,
                "refusal": None,
                # the override's own record: its reason as stored, its writer
                "reason": "guidance raised",
                "principal": "agent",
                "actor": "claude-opus-5-5",
            }
        ],
        "overrideCount": 1,
        "mechanical": mechanical,
    }
    assert line.delta is not None and abs(mechanical + line.delta - value) < 1e-6
    # no record of the others
    for symbol in ("AAL", "HGCO"):
        body = _detail(client, symbol)
        assert (body["review"], body["secondary"], body["report"], body["item"]) == (
            None,
            None,
            None,
            None,
        )


def test_a_refused_review_carries_its_refusal(
    client: TestClient, db_path: Path, policy: Policy, results: dict[str, ValuationResult]
) -> None:
    override_id = _override(db_path, results)
    mechanical = results["AAPL"]
    refused = replace(
        mechanical,
        value=None,
        levels=None,
        price_to_value=None,
        designation=None,
        refusal="the reviewed belief is refused",
    )
    with closing(connect(db_path)) as conn:
        review = Review(refused, mechanical.value, (), (override_id,))
        insert_review(conn, review, "AAPL", _latest(db_path, "AAPL"), None, clock=lambda: NOW)
    found = _detail(client, "AAPL")["review"]
    assert (found["value"], found["levels"], found["refusal"]) == (
        None,
        None,
        "the reviewed belief is refused",
    )
    assert (found["bridge"], found["overrideCount"]) == ([], 1)


def test_a_refused_row_carries_its_counting_secondary(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """AAL's route refused; its secondary valuation counts on its snapshot, so the drawer draws
    the secondary's band (spec 18.2, the ruling of 2026-11-07): the levels, price ÷ value and its
    word at the latest snapshot's price on the policy's edges, and the parts with their values
    as the secondary read serves them (18.3)."""
    refused = results["AAL"]
    assert refused.value is None and refused.price is not None
    with closing(connect(db_path)) as conn:
        secondary = secondary_row(conn, secondaries["AAL"])
    assert secondary is not None and secondary.buy_level is not None
    value = secondary.value_per_share
    ratio, word = designation_for(refused.price, value, policy.designation_edges)
    served = client.get("/api/companies/AAL/secondary").json()["secondaryValuations"][0]
    found = _detail(client, "AAL")["secondary"]
    assert found == {
        "id": secondaries["AAL"],
        "form": "parts",
        "valuePerShare": value,
        "levels": {
            "buy": secondary.buy_level,
            "fairLow": secondary.fair_low,
            "fairHigh": secondary.fair_high,
            "trim": secondary.trim_level,
        },
        "priceToValue": ratio,
        "designation": word,
        "parts": served["parts"],
        "drivers": None,
        "createdAt": "2026-10-31T22:15:00+00:00",
        "principal": "agent",
        "actor": "claude-opus-5-5",
    }
    (part,) = found["parts"]
    assert (part["name"], part["note"], part["value"]) == (
        "the business",
        None,
        secondary.parts[0]["value"],
    )
    # a reprice: the secondary still counts, its word read at the new price
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, replace(refused, price=100.0), 1, clock=lambda: NOW)
    repriced = _detail(client, "AAL")["secondary"]
    assert (repriced["priceToValue"], repriced["designation"]) == designation_for(
        100.0, value, policy.designation_edges
    )
    assert repriced["priceToValue"] == 100.0 / value


def test_a_secondary_without_levels_has_no_word(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """A value a share at or below zero has no levels, so no band and no word."""
    path = (-5e9,) * 3
    part = Part("the business", path, 0.0, None)
    loss = secondary_value(
        parts=[part], debt=0.0, cash=0.0, shares=1e9, price=150.0, moat="None", policy=policy
    )
    with closing(connect(db_path)) as conn:
        insert_secondary(
            conn, "AAL", _latest(db_path, "AAL"), [part], loss, "a loss", [], "none", "none",
            policy.version, policy.settings_hash, None, AGENT, NOW,
        )  # fmt: skip
    found = _detail(client, "AAL")["secondary"]
    assert found["valuePerShare"] < 0
    assert (found["levels"], found["priceToValue"], found["designation"]) == (None, None, None)


def test_the_detail_carries_the_drivers_of_a_drivers_form(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """Spec 20.4's drivers, as the secondary read serves them, and no parts."""
    drivers = Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02)
    valuation = secondary_value(
        drivers=drivers,
        revenue_0=1e9,
        roic_t=0.12,
        debt=0.0,
        cash=0.0,
        shares=1e8,
        price=150.0,
        moat="None",
        policy=policy,
    )
    with closing(connect(db_path)) as conn:
        insert_secondary(
            conn, "HGCO", _latest(db_path, "HGCO"), [], valuation, "the drivers", [], "none",
            "none", policy.version, policy.settings_hash, None, AGENT, NOW,
            revenue_0=1e9, roic_t=0.12,
        )  # fmt: skip
    found = _detail(client, "HGCO")["secondary"]
    assert (found["form"], found["parts"]) == ("drivers", [])
    assert found["drivers"] == {
        "years": 3,
        "revenueGrowth": [0.10, 0.08, 0.05],
        "operatingMargin": [0.20, 0.20, 0.20],
        "taxRate": 0.25,
        "salesToCapital": 2.0,
        "terminalGrowth": 0.02,
    }


def test_records_on_an_older_snapshot_leave_the_detail(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """The screen's rule (``rows.counts_on``): a reprice keeps the review and the secondary, a
    revalue leaves both on the snapshot they were made on; the report stays the company's."""
    _review(db_path, policy, results)
    _report(db_path, "AAPL", "hold", _cited_sections(_latest(db_path, "AAPL")))
    cited = results["AAPL"]
    assert cited.value is not None
    repriced = reprice(cited, 160.0, date(2026, 11, 2), policy)
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, repriced, 1, clock=lambda: NOW)
    body = _detail(client, "AAPL")
    assert body["review"] is not None
    assert body["secondary"] is not None and body["secondary"]["id"] == secondaries["AAPL"]
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, replace(repriced, value=cited.value + 1.0), 1, clock=lambda: NOW)
    body = _detail(client, "AAPL")
    assert (body["review"], body["secondary"]) == (None, None)
    assert body["report"] is not None and body["report"]["stance"] == "hold"


def test_the_detail_carries_the_report_and_its_summary(client: TestClient, db_path: Path) -> None:
    """Section 1 as submitted, cites included, and the references it cites with the numbers the
    report page's list gives them, so a number in the drawer matches the page."""
    sections = _cited_sections(_latest(db_path, "AAPL"))
    report_id = _report(db_path, "AAPL", "buy", sections)
    whole = client.get(f"/api/reports/{report_id}").json()["references"]
    assert [r["n"] for r in whole] == [1, 2]
    assert _detail(client, "AAPL")["report"] == {
        "id": report_id,
        "mode": "full report",
        "stance": "buy",
        "revision": 1,
        "createdAt": "2026-11-01T08:00:00+00:00",
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "expired": False,
        "summary": sections[0],
        "references": [whole[0]],  # the price; r is cited in the second section only
    }


def test_an_owners_report_names_the_owner(client: TestClient, db_path: Path) -> None:
    sections = [{"heading": "Summary", "parts": ["Plain words."]}]
    _report(db_path, "HGCO", "avoid", sections, writer=OWNER)
    report = _detail(client, "HGCO")["report"]
    assert (report["principal"], report["actor"], report["references"]) == ("owner", None, [])


def test_the_reports_stance_expires_with_its_window(
    client_with_clock: Callable[[datetime], TestClient],
    db_path: Path,
    results: dict[str, ValuationResult],
) -> None:
    _report(db_path, "AAPL", "trim", [{"heading": "Summary", "parts": ["Plain."]}])
    assert results["AAPL"].valid_until == date(2027, 1, 28)
    last_day = client_with_clock(datetime(2027, 1, 28, 23, 59, tzinfo=UTC))
    after = client_with_clock(datetime(2027, 1, 29, 0, 0, tzinfo=UTC))
    assert _detail(last_day, "AAPL")["report"]["expired"] is False
    assert _detail(after, "AAPL")["report"]["expired"] is True


def test_the_detail_carries_the_open_item(client: TestClient) -> None:
    body = {"symbol": "AAPL", "mode": "full report", "note": "the first look"}
    item = _post(client, "/api/inbox", body, HEADER)
    assert _detail(client, "AAPL")["item"] == {
        "id": item["id"],
        "state": "pending",
        "mode": "full report",
        "claimedBy": None,
        "createdAt": AT,
    }
    response = client.post("/api/inbox/claim", json={}, headers=AGENT_HEADERS)
    assert response.status_code == 200, response.text
    found = _detail(client, "AAPL")["item"]
    assert (found["state"], found["claimedBy"]) == ("claimed", "claude-opus-5-5")
    move = {"action": "decline", "reason": "no consensus on file"}
    response = client.patch(f"/api/inbox/{item['id']}", json=move, headers=AGENT_HEADERS)
    assert response.status_code == 200, response.text
    assert _detail(client, "AAPL")["item"] is None  # a finished item is not open


# ------------------------------------------------------------------ the research read


def test_the_research_read_serves_each_record_as_its_own_read(
    client: TestClient, db_path: Path, results: dict[str, ValuationResult]
) -> None:
    empty = _research(client, "AAPL")
    assert empty == {key: [] for key in (*KINDS, "ledger")}
    base = "/api/companies/AAPL"
    guidance = {
        "metric": "revenue",
        "period": "2026",
        "low": 24e9,
        "high": 25e9,
        "basis": "gaap",
        "asOf": "2026-10-28",
        "text": "We expect revenue of $24.0 billion to $25.0 billion for fiscal 2026.",
        "source": "response:12/0/content",
    }
    _post(client, f"{base}/guidance", guidance, AGENT_HEADERS)
    _override(db_path, results)
    finding = {
        "asOf": "2025-09-27",
        "text": "services grew 11.2%",
        "source": {"kind": "filing", "ref": "10-K 2025, p. 41", "note": None},
    }
    _post(client, f"{base}/findings", finding, AGENT_HEADERS)
    criterion = _post(client, f"{base}/kill-criteria", {"text": "margin below 40%"}, AGENT_HEADERS)
    news = {
        "date": "2026-10-30",
        "headline": "Q3 results",
        "source": "https://example.com/q3",
        "text": "gross margin held",
        "killCriterionId": criterion["id"],
    }
    _post(client, f"{base}/news-items", news, AGENT_HEADERS)
    first = _post(client, f"{base}/notes", {"text": "the first note"}, HEADER)
    second = _post(client, f"{base}/notes", {"text": "the second note"}, AGENT_HEADERS)
    report_id = _report(db_path, "AAPL", "hold", [{"heading": "Summary", "parts": ["Plain."]}])
    with closing(connect(db_path)) as conn:
        insert_judgments(
            conn,
            report_id,
            "AAPL",
            [
                {"judgment": "phase", "decision": "Mature Growth holds"},
                {"judgment": "moat", "decision": "Wide"},
            ],
        )
    found = _research(client, "AAPL")
    assert list(found) == [*KINDS, "ledger"]
    assert found["overrides"] == client.get(f"{base}/overrides").json()["overrides"]
    assert found["guidance"] == client.get(f"{base}/guidance").json()["guidance"]
    assert found["judgments"] == client.get(f"/api/reports/{report_id}").json()["judgments"]
    assert found["killCriteria"] == client.get(f"{base}/kill-criteria").json()["killCriteria"]
    assert found["newsItems"] == client.get(f"{base}/news-items").json()["newsItems"]
    assert found["notes"] == client.get(f"{base}/notes").json()["notes"]
    assert found["findings"] == client.get(f"{base}/findings").json()["findings"]
    assert found["ledger"] == client.get(f"{base}/ledger").json()["entries"]
    for kind in KINDS:
        assert len(found[kind]) >= 1, kind
    # newest first; the latest report's judgments in the order the agent gave them
    assert [n["id"] for n in found["notes"]] == [second["id"], first["id"]]
    assert [j["judgment"] for j in found["judgments"]] == ["phase", "moat"]
    ledger = [e["id"] for e in found["ledger"]]
    assert ledger == sorted(ledger, reverse=True) and found["ledger"][0]["kind"] == "note"
    # another company's records are not this one's
    assert _research(client, "HGCO") == empty


def test_the_research_reads_the_twenty_newest_ledger_rows(client: TestClient) -> None:
    for n in range(25):
        _post(client, "/api/companies/AAPL/notes", {"text": f"note {n}"}, HEADER)
    every = client.get("/api/companies/AAPL/ledger").json()["entries"]
    assert len(every) == 25
    found = _research(client, "AAPL")
    assert found["ledger"] == every[:20]
    assert len(found["notes"]) == 25  # every note; the ledger alone is cut


def test_the_research_read_of_an_unknown_company(client: TestClient) -> None:
    response = client.get("/api/companies/NOPE/research")
    assert (response.status_code, response.json()) == (404, {"detail": "no snapshot for NOPE"})
    response = client.get("/api/companies/a$b/research")
    assert response.status_code == 400
