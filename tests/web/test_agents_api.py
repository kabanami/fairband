"""The agent routes (spec 2026-11-06 Tier 2, sections 7 to 9 and 16): the work inbox, the research
records and the ledger, on the database of ``conftest.py``: AAPL, AAL and HGCO, each with one
snapshot."""

import sqlite3
from contextlib import closing
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from support.engine_companies import fx_inputs, universe_deciles
from support.web import HEADER, NOW, TODAY

from fairband.engine.route import refusal_result, value_company
from fairband.policy import Policy, load_policy
from fairband.store.db import connect
from fairband.store.inbox import complete_item, post_item
from fairband.store.ledger import OWNER, Writer
from fairband.store.reports import insert_report
from fairband.store.snapshots import insert_snapshot, latest_snapshot
from fairband.web.agents_api import inbox_items_json
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, IDENTIFY_FIRST, PRINCIPAL_HEADER

AT = NOW.isoformat()
AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
OTHER_AGENT = HEADER | {PRINCIPAL_HEADER: "agent", ACTOR_HEADER: "gpt-5"}


def _snapshot_id(client: TestClient, symbol: str) -> int:
    snapshot_id: int = client.get(f"/api/companies/{symbol}").json()["snapshot"]["id"]
    return snapshot_id


def _post(client: TestClient, url: str, body: dict[str, Any], headers: dict[str, str]) -> Any:
    r = client.post(url, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _ledger(client: TestClient, symbol: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = client.get(f"/api/companies/{symbol}/ledger").json()["entries"]
    return entries


def test_post_and_list_inbox(client: TestClient) -> None:
    assert client.get("/api/inbox").json() == {"launchReady": False, "items": []}
    item = _post(
        client, "/api/inbox", {"symbol": "aapl", "mode": "full report", "note": "why"}, HEADER
    )
    assert item == {
        "id": item["id"],
        "symbol": "AAPL",
        "mode": "full report",
        "note": "why",
        "snapshotId": _snapshot_id(client, "AAPL"),
        "origin": "owner",
        "postedBy": "owner",
        "postedActor": None,
        "postedClient": None,
        "postedAt": AT,
        "state": "pending",
        "claimedBy": None,
        "claimedAt": None,
        "reportId": None,
        "reason": None,
        "finishedAt": None,
        "expiryValidUntil": None,
        "expiryReviewId": None,  # the held record an expiry item stands for (spec 2026-11-23
        "expirySecondaryId": None,  # held reviewed value, 5.10); none on an owner's item
    }
    # the list's own fields: the report's revision (18.5, plan 4), who declined the item (spec
    # 2026-11-25 owner's inbox, 7.2) and the open item's newest launch, with whether launching is
    # set up beside the items (B-210)
    listed = item | {"reportRevision": None, "declinedBy": None, "launch": None}
    assert client.get("/api/inbox").json() == {"launchReady": False, "items": [listed]}
    assert client.get("/api/inbox", params={"state": "pending"}).json()["items"] == [listed]
    assert client.get("/api/inbox", params={"state": "done"}).json()["items"] == []
    r = client.get("/api/inbox", params={"state": "open"})
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "state: Input should be 'pending', 'claimed', 'done', 'declined' or 'dropped'"},
    )


def test_the_inbox_names_a_done_items_report_revision(client: TestClient, db_path: Path) -> None:
    """Spec 18.5 (plan 4): a done item carries its report's revision; a pending one null, and a
    done one whose report row is missing null too, so its link reads Open."""
    aapl = _post(client, "/api/inbox", {"symbol": "AAPL", "mode": "full report"}, HEADER)
    _post(client, "/api/inbox", {"symbol": "AAL", "mode": "full report"}, HEADER)
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    sections = [{"heading": "Summary", "parts": ["Phones."]}]
    with closing(connect(db_path)) as conn:
        for symbol in ("AAL", "AAPL"):  # AAL's first, so AAPL's report id is not its revision
            snapshot_id = _snapshot_id(client, symbol)
            report_id = insert_report(
                conn,
                symbol,
                "full report",
                "hold",
                sections,
                None,
                snapshot_id,
                None,
                None,
                None,
                writer,
                NOW,
            )
    url = f"/api/inbox/{aapl['id']}"
    r = client.patch(url, json={"action": "complete", "reportId": report_id}, headers=AGENT)
    assert r.status_code == 200, r.text
    items = client.get("/api/inbox").json()["items"]
    done = next(i for i in items if i["state"] == "done")
    assert done["reportRevision"] == 1
    pending = next(i for i in items if i["state"] == "pending")
    assert pending["reportRevision"] is None
    with closing(connect(db_path)) as conn, conn:
        conn.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    [done] = client.get("/api/inbox", params={"state": "done"}).json()["items"]
    assert (done["reportId"], done["reportRevision"]) == (report_id, None)


def test_the_inbox_names_who_declined(client: TestClient, db_path: Path) -> None:
    """Spec 2026-11-25 owner's inbox, 7.2: a declined item names the principal that wrote its
    decline, read from the ledger; an item not declined names none, and so does a declined one
    with no ledger row of its decline (MSFT's, declined by SQL)."""
    for symbol, headers in (("AAPL", HEADER), ("AAL", AGENT)):
        item = _post(client, "/api/inbox", {"symbol": symbol, "mode": "full report"}, HEADER)
        move = {"action": "decline", "reason": "not now"}
        r = client.patch(f"/api/inbox/{item['id']}", json=move, headers=headers)
        assert r.status_code == 200, r.text
    _post(client, "/api/inbox", {"symbol": "HGCO", "mode": "full report"}, HEADER)
    msft = _post(client, "/api/inbox", {"symbol": "MSFT", "mode": "full report"}, HEADER)
    with closing(connect(db_path)) as conn, conn:
        conn.execute(
            "UPDATE work_items SET state = 'declined', reason = 'gone', finished_at = ?"
            " WHERE id = ?",
            (AT, msft["id"]),
        )
    by = {i["symbol"]: i["declinedBy"] for i in client.get("/api/inbox").json()["items"]}
    assert by == {"AAPL": "owner", "AAL": "agent", "HGCO": None, "MSFT": None}


def _done_item(conn: sqlite3.Connection, symbol: str) -> None:
    """A done item of ``symbol``, completed with a report on the company's latest snapshot."""
    snapshot = latest_snapshot(conn, symbol)
    assert snapshot is not None
    item_id = post_item(conn, symbol, "full report", "", snapshot.id, "owner", OWNER, NOW)
    sections = [{"heading": "Summary", "parts": ["Plain words."]}]
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    report_id = insert_report(
        conn,
        symbol,
        "full report",
        "hold",
        sections,
        None,
        snapshot.id,
        None,
        None,
        item_id,
        writer,
        NOW,
    )
    complete_item(conn, item_id, report_id, NOW)


def test_the_inbox_read_s_queries_do_not_grow_with_its_items(db_path: Path) -> None:
    """Spec 2026-11-25 owner's inbox, 4 and 7.2: the read every open tab makes each 30 seconds
    runs a fixed number of queries whatever the number of done items: the items, their reports'
    revisions and who declined each, with one done item and with five."""

    def statements(conn: sqlite3.Connection) -> int:
        seen: list[str] = []
        conn.set_trace_callback(seen.append)
        inbox_items_json(conn, None, NOW)
        conn.set_trace_callback(None)
        return len(seen)

    with closing(connect(db_path)) as conn:
        _done_item(conn, "AAPL")
        before = statements(conn)
        for symbol in ("AAL", "HGCO", "AAPL", "AAL"):
            _done_item(conn, symbol)
        after = statements(conn)
        assert len(inbox_items_json(conn, None, NOW)) == 5
    assert after == before == 3


def test_an_agent_post_carries_its_actor(client: TestClient) -> None:
    item = _post(client, "/api/inbox", {"symbol": "HGCO", "mode": "valuation review"}, AGENT)
    assert (item["origin"], item["postedBy"], item["note"]) == ("agent", "agent", "")
    assert (item["postedActor"], item["postedClient"]) == ("claude-opus-5-5", "claude-code/2.1")
    [entry] = client.get("/api/ledger").json()["entries"]
    assert entry == {
        "id": entry["id"],
        "at": AT,
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "kind": "work-item",
        "symbol": "HGCO",
        "refTable": "work_items",
        "refId": item["id"],
        "snapshotId": _snapshot_id(client, "HGCO"),
        "workItemId": item["id"],
        "summary": "valuation review posted",
    }


def test_a_blank_client_header_is_stored_as_none(client: TestClient) -> None:
    """B-103 (spec 2026-11-15 12.1, clause 4): a client header that is blank or whitespace names no
    client: the record and its ledger row store none."""
    for blank in ("", "   "):
        headers = AGENT | {CLIENT_HEADER: blank}
        note = _post(client, "/api/companies/AAPL/notes", {"text": "margins look peaked"}, headers)
        assert (note["actor"], note["client"]) == ("claude-opus-5-5", None)
        entry = _ledger(client, "AAPL")[0]
        assert (entry["refId"], entry["actor"], entry["client"]) == (
            note["id"],
            note["actor"],
            None,
        )


def test_a_write_names_its_writer_or_is_refused(client: TestClient) -> None:
    body = {"symbol": "AAPL", "mode": "full report"}
    r = client.post("/api/inbox", json=body, headers=HEADER | {PRINCIPAL_HEADER: "agent"})
    assert (r.status_code, r.json()) == (400, {"detail": IDENTIFY_FIRST})
    r = client.post("/api/inbox", json=body, headers=HEADER | {PRINCIPAL_HEADER: "system"})
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "a principal is owner or agent, not 'system'"},
    )
    assert client.post("/api/inbox", json=body).status_code == 403  # no request header
    assert client.get("/api/inbox").json()["items"] == []
    assert client.get("/api/ledger").json() == {"entries": []}


def test_a_second_open_item_is_409(client: TestClient) -> None:
    _post(client, "/api/inbox", {"symbol": "AAPL", "mode": "full report"}, HEADER)
    r = client.post(
        "/api/inbox", json={"symbol": "aapl", "mode": "valuation review"}, headers=AGENT
    )
    assert (r.status_code, r.json()) == (409, {"detail": "an item for AAPL is open"})
    r = client.post("/api/inbox", json={"symbol": "AAL", "mode": "memo"}, headers=HEADER)
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "mode: Input should be 'valuation review' or 'full report'"},
    )
    r = client.post("/api/inbox", json={"symbol": "a b", "mode": "full report"}, headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "'a b' is not a symbol"})
    assert len(client.get("/api/inbox").json()["items"]) == 1
    assert len(client.get("/api/ledger").json()["entries"]) == 1


def test_claim_and_decline_over_the_api(client: TestClient) -> None:
    r = client.post("/api/inbox/claim", json={}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no pending work item"})
    first = _post(client, "/api/inbox", {"symbol": "AAPL", "mode": "full report"}, HEADER)
    second = _post(client, "/api/inbox", {"symbol": "AAL", "mode": "full report"}, HEADER)
    r = client.post("/api/inbox/claim", json={}, headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "a claim is an agent's write"})

    claimed = client.post("/api/inbox/claim", json={}, headers=AGENT).json()  # the oldest
    assert (claimed["id"], claimed["state"], claimed["claimedBy"], claimed["claimedAt"]) == (
        first["id"],
        "claimed",
        "claude-opus-5-5",
        AT,
    )
    taken = client.post("/api/inbox/claim", json={"itemId": first["id"]}, headers=OTHER_AGENT)
    assert taken.json()["claimedBy"] == "gpt-5"
    r = client.post("/api/inbox/claim", json={"itemId": 99}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no work item 99"})

    url = f"/api/inbox/{second['id']}"
    r = client.patch(url, json={"action": "decline"}, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": "a decline needs a reason"})
    r = client.patch(url, json={"action": "decline", "reason": "no new filing"}, headers=AGENT)
    assert r.status_code == 200
    assert (r.json()["state"], r.json()["reason"], r.json()["finishedAt"]) == (
        "declined",
        "no new filing",
        AT,
    )
    r = client.patch(url, json={"action": "decline", "reason": "again"}, headers=AGENT)
    assert (r.status_code, r.json()) == (409, {"detail": f"work item {second['id']} is declined"})
    r = client.post("/api/inbox/claim", json={"itemId": second["id"]}, headers=AGENT)
    assert (r.status_code, r.json()) == (409, {"detail": f"work item {second['id']} is declined"})
    r = client.patch("/api/inbox/99", json={"action": "decline", "reason": "x"}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no work item 99"})
    r = client.patch(url, json={"action": "drop"}, headers=AGENT)
    assert r.status_code == 400 and r.json()["detail"].startswith("action: ")


def test_a_claim_without_a_body_claims_the_oldest_pending_item(client: TestClient) -> None:
    """B-103 (spec 2026-11-15 12.1, clause 3): a claim with no body claims the oldest pending item,
    as an empty body does, and answers as one does with none pending."""
    r = client.post("/api/inbox/claim", headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no pending work item"})
    first = _post(client, "/api/inbox", {"symbol": "AAPL", "mode": "full report"}, HEADER)
    _post(client, "/api/inbox", {"symbol": "AAL", "mode": "full report"}, HEADER)
    r = client.post("/api/inbox/claim", headers=AGENT)
    assert r.status_code == 200, r.text
    assert (r.json()["id"], r.json()["state"], r.json()["claimedBy"]) == (
        first["id"],
        "claimed",
        "claude-opus-5-5",
    )
    r = client.post("/api/inbox/claim", headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "a claim is an agent's write"})


def test_complete_needs_a_published_report(client: TestClient) -> None:
    item = _post(client, "/api/inbox", {"symbol": "AAPL", "mode": "full report"}, HEADER)
    url = f"/api/inbox/{item['id']}"
    r = client.patch(url, json={"action": "complete"}, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": "a complete needs a report id"})
    r = client.patch(url, json={"action": "complete", "reportId": 7}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no report 7 for AAPL"})
    assert client.get("/api/inbox").json()["items"][0]["state"] == "pending"


def test_notes_findings_kill_criteria_and_news_items_round_trip(client: TestClient) -> None:
    base = "/api/companies/aapl"
    note = _post(client, f"{base}/notes", {"text": "margins look peaked"}, HEADER)
    assert note == {
        "id": note["id"],
        "symbol": "AAPL",
        "text": "margins look peaked",
        "principal": "owner",
        "actor": None,
        "client": None,
        "at": AT,
        "overrideId": None,
    }
    assert client.get(f"{base}/notes").json() == {"notes": [note]}
    r = client.post(f"{base}/notes", json={"text": "its source", "overrideId": 99}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no override 99 for AAPL"})
    assert client.get(f"{base}/notes").json() == {"notes": [note]}

    source = {"kind": "filing", "ref": "10-K 2025, p. 41", "note": "the segment table"}
    body = {
        "asOf": "2025-09-27",
        "text": "services grew 11.2%",
        "source": source,
        "value": 0.112,
        "unit": "percent",
        "period": "2025",
    }
    finding = _post(client, f"{base}/findings", body, AGENT)
    assert finding == {
        "id": finding["id"],
        "symbol": "AAPL",
        "asOf": "2025-09-27",
        "text": "services grew 11.2%",
        "source": source,
        "value": 0.112,
        "unit": "percent",
        "period": "2025",
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "at": AT,
        "currency": None,  # a percent is no money figure
    }
    assert client.get(f"{base}/findings").json() == {"findings": [finding]}
    r = client.post(
        f"{base}/findings", json=body | {"source": {"kind": "blog", "ref": "x"}}, headers=AGENT
    )
    assert r.status_code == 400 and r.json()["detail"].startswith(
        "source.kind: Input should be 'filing'"
    )
    r = client.post(f"{base}/findings", json=body | {"source": {"kind": "url"}}, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": "source.ref: Field required"})

    criterion = _post(client, f"{base}/kill-criteria", {"text": "gross margin below 40%"}, AGENT)
    assert (criterion["state"], criterion["reportId"], criterion["stateReason"]) == (
        "open",
        None,
        None,
    )
    r = client.patch(
        f"/api/kill-criteria/{criterion['id']}",
        json={"state": "triggered", "reason": "Q3 gross margin 39.8%"},
        headers=AGENT,
    )
    assert r.status_code == 200
    moved = r.json()
    assert (moved["state"], moved["stateReason"], moved["stateAt"]) == (
        "triggered",
        "Q3 gross margin 39.8%",
        AT,
    )
    assert client.get(f"{base}/kill-criteria").json() == {"killCriteria": [moved]}
    r = client.patch(
        "/api/kill-criteria/99", json={"state": "retired", "reason": "x"}, headers=AGENT
    )
    assert (r.status_code, r.json()) == (404, {"detail": "no kill criterion 99"})

    news = {
        "date": "2026-10-30",
        "headline": "Q4 results",
        "source": "https://example.com/q4",
        "text": "gross margin 39.8%",
        "killCriterionId": criterion["id"],
    }
    item = _post(client, f"{base}/news-items", news, AGENT)
    assert item == news | {
        "id": item["id"],
        "symbol": "AAPL",
        "reportId": None,
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "at": AT,
    }
    assert client.get(f"{base}/news-items").json() == {"newsItems": [item]}
    r = client.post(f"{base}/news-items", json=news | {"killCriterionId": 99}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": "no kill criterion 99 for AAPL"})
    r = client.post(
        f"{base}/news-items", json={k: v for k, v in news.items() if k != "text"}, headers=AGENT
    )
    assert (r.status_code, r.json()) == (400, {"detail": "text: Field required"})

    for kind in ("notes", "findings", "kill-criteria", "news-items"):
        assert client.get(f"/api/companies/AAL/{kind}").status_code == 200
        r = client.get(f"/api/companies/a b/{kind}")
        assert (r.status_code, r.json()) == (400, {"detail": "'a b' is not a symbol"})


def test_a_finding_names_the_currency_of_its_money(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """Spec 2026-11-15 9.1: a money finding answers the currency it names, else the company's
    reporting currency, its latest snapshot's (SEK for FXCO, USD for AAPL and for a company with
    no snapshot); a figure that is not money answers none. A currency on a figure that is not
    money, or out of form, is refused 400 and stores nothing."""
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, value_company(fx_inputs(), universe_deciles(), policy, TODAY), 1)
    source = {"kind": "transcript", "ref": "response:7", "note": None}
    fact = {"asOf": "2026-10-16", "text": "capex", "source": source}
    total = fact | {"value": 4e9, "unit": "currency"}
    url = "/api/companies/FXCO/findings"
    usd = _post(client, url, total | {"currency": "USD"}, AGENT)
    bare = _post(client, url.lower(), total | {"value": 12.5, "unit": "per-share"}, AGENT)
    rate = total | {"value": 0.11, "unit": "percent"}
    percent = _post(client, url, rate, AGENT)
    assert [f["currency"] for f in (usd, bare, percent)] == ["USD", "SEK", None]
    assert client.get(url.lower()).json() == {"findings": [percent, bare, usd]}
    for symbol in ("AAPL", "ZZZZ"):  # USD, and no snapshot
        found = _post(client, f"/api/companies/{symbol}/findings", total, AGENT)
        assert found["currency"] == "USD", symbol
        assert client.get(f"/api/companies/{symbol}/findings").json() == {"findings": [found]}
    for given, detail in (
        (rate | {"currency": "USD"}, "a currency goes with a money figure"),
        (total | {"currency": "usd"}, "a currency is three capital letters, not 'usd'"),
    ):
        r = client.post(url, json=given, headers=AGENT)
        assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert len(client.get(url).json()["findings"]) == 3


def test_a_kill_criterion_holds_a_threshold_and_answers_its_currency(
    client: TestClient, db_path: Path, policy: Policy
) -> None:
    """Spec 2026-11-15 8.1: the post takes a threshold, its unit and a currency, each optional, and
    answers them; a money threshold answers the currency it names, else the company's reporting
    currency (SEK for FXCO, USD for a company with no snapshot), and any other none. The list and a
    state move answer the same. A threshold without its unit, or a currency on a figure that is not
    money, is refused 400 and stores nothing."""
    with closing(connect(db_path)) as conn:
        insert_snapshot(conn, value_company(fx_inputs(), universe_deciles(), policy, TODAY), 1)
    url = "/api/companies/FXCO/kill-criteria"
    growth = _post(
        client, url, {"text": "growth below 5%", "threshold": 0.05, "unit": "percent"}, AGENT
    )
    capex = _post(client, url, {"text": "capex above", "threshold": 4e9, "unit": "currency"}, AGENT)
    eps = _post(
        client,
        url.lower(),
        {"text": "EPS below", "threshold": 1.5, "unit": "per-share", "currency": "USD"},
        AGENT,
    )
    words = _post(client, url, {"text": "the founder leaves"}, AGENT)
    assert [(k["threshold"], k["unit"], k["currency"]) for k in (growth, capex, eps, words)] == [
        (0.05, "percent", None),
        (4e9, "currency", "SEK"),
        (1.5, "per-share", "USD"),
        (None, None, None),
    ]
    assert growth == {
        "id": growth["id"],
        "symbol": "FXCO",
        "text": "growth below 5%",
        "state": "open",
        "reportId": None,
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "at": AT,
        "stateReason": None,
        "stateAt": None,
        "threshold": 0.05,
        "unit": "percent",
        "currency": None,
    }
    assert client.get(url).json() == {"killCriteria": [words, eps, capex, growth]}
    r = client.patch(
        f"/api/kill-criteria/{capex['id']}",
        json={"state": "retired", "reason": "the plan changed"},
        headers=AGENT,
    )
    assert r.status_code == 200, r.text
    assert (r.json()["state"], r.json()["threshold"], r.json()["currency"]) == (
        "retired",
        4e9,
        "SEK",
    )
    total = {"text": "capex above", "threshold": 4e9, "unit": "currency"}
    found = _post(client, "/api/companies/ZZZZ/kill-criteria", total, AGENT)
    assert found["currency"] == "USD"  # no snapshot
    assert client.get("/api/companies/ZZZZ/kill-criteria").json() == {"killCriteria": [found]}
    for given, detail in (
        ({"text": "x", "threshold": 0.05}, "a kill criterion's threshold and unit come together"),
        ({"text": "x", "unit": "percent"}, "a kill criterion's threshold and unit come together"),
        (
            {"text": "x", "threshold": 0.05, "unit": "percent", "currency": "USD"},
            "a currency goes with a money figure",
        ),
        (total | {"currency": "usd"}, "a currency is three capital letters, not 'usd'"),
    ):
        r = client.post(url, json=given, headers=AGENT)
        assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert len(client.get(url).json()["killCriteria"]) == 4


def test_a_kill_criterion_moved_to_the_state_it_is_in_is_409(client: TestClient) -> None:
    """B-103 (spec 2026-11-15 12.1, clause 1): a move to the state the criterion is in already is
    a state the record cannot move from, 409, in the words it had as a 400, and writes nothing; a
    move without a reason is still a bad value, 400."""
    criterion = _post(
        client, "/api/companies/AAPL/kill-criteria", {"text": "gross margin below 40%"}, AGENT
    )
    url = f"/api/kill-criteria/{criterion['id']}"
    r = client.patch(url, json={"state": "open", "reason": "it still holds"}, headers=AGENT)
    assert (r.status_code, r.json()) == (
        409,
        {"detail": f"kill criterion {criterion['id']} is already open"},
    )
    body = {"state": "retired", "reason": "the thesis changed"}
    assert client.patch(url, json=body, headers=AGENT).status_code == 200
    r = client.patch(url, json=body | {"reason": "again"}, headers=AGENT)
    assert (r.status_code, r.json()) == (
        409,
        {"detail": f"kill criterion {criterion['id']} is already retired"},
    )
    r = client.patch(url, json={"state": "open", "reason": " "}, headers=AGENT)
    assert (r.status_code, r.json()) == (400, {"detail": "a state change needs a reason"})
    [found] = client.get("/api/companies/AAPL/kill-criteria").json()["killCriteria"]
    assert (found["state"], found["stateReason"]) == ("retired", "the thesis changed")
    assert [e["summary"] for e in _ledger(client, "AAPL")] == [
        "retired: the thesis changed",
        "gross margin below 40%",
    ]


def test_every_write_is_a_ledger_row(client: TestClient) -> None:
    item = _post(client, "/api/inbox", {"symbol": "AAPL", "mode": "full report"}, HEADER)
    client.post("/api/inbox/claim", json={"itemId": item["id"]}, headers=AGENT)
    client.post("/api/inbox/claim", json={"itemId": item["id"]}, headers=OTHER_AGENT)
    client.patch(
        f"/api/inbox/{item['id']}",
        json={"action": "decline", "reason": "no new filing"},
        headers=OTHER_AGENT,
    )
    note = _post(client, "/api/companies/AAPL/notes", {"text": "margins look peaked"}, AGENT)
    source = {"kind": "url", "ref": "https://example.com/q3"}
    finding = _post(
        client,
        "/api/companies/AAPL/findings",
        {"asOf": "2026-07-31", "text": "a new plant", "source": source},
        AGENT,
    )
    criterion = _post(
        client, "/api/companies/AAPL/kill-criteria", {"text": "gross margin below 40%"}, AGENT
    )
    client.patch(
        f"/api/kill-criteria/{criterion['id']}",
        json={"state": "retired", "reason": "the thesis changed"},
        headers=AGENT,
    )
    news = {"date": "2026-10-30", "headline": "Q4 results", "source": "response:12", "text": "t"}
    news_item = _post(client, "/api/companies/AAPL/news-items", news, AGENT)
    _post(client, "/api/companies/AAL/notes", {"text": "another company"}, HEADER)

    entries = _ledger(client, "AAPL")
    snapshot_id = _snapshot_id(client, "AAPL")
    work_items = ("work_items", item["id"])
    assert [
        (e["kind"], e["principal"], e["actor"], (e["refTable"], e["refId"]), e["summary"])
        for e in entries
    ] == [
        ("news-item", "agent", "claude-opus-5-5", ("news_items", news_item["id"]), "Q4 results"),
        (
            "kill-criterion",
            "agent",
            "claude-opus-5-5",
            ("kill_criteria", criterion["id"]),
            "retired: the thesis changed",
        ),
        (
            "kill-criterion",
            "agent",
            "claude-opus-5-5",
            ("kill_criteria", criterion["id"]),
            "gross margin below 40%",
        ),
        ("finding", "agent", "claude-opus-5-5", ("findings", finding["id"]), "a new plant"),
        ("note", "agent", "claude-opus-5-5", ("notes", note["id"]), "margins look peaked"),
        ("decline", "agent", "gpt-5", work_items, "declined: no new filing"),
        (
            "claim",
            "agent",
            "gpt-5",
            work_items,
            "claimed by gpt-5, taken over from claude-opus-5-5",
        ),
        ("claim", "agent", "claude-opus-5-5", work_items, "claimed by claude-opus-5-5"),
        ("work-item", "owner", None, work_items, "full report posted"),
    ]
    assert all(e["snapshotId"] == snapshot_id for e in entries)
    assert [e["workItemId"] for e in entries[-4:]] == [item["id"]] * 4
    assert [e["workItemId"] for e in entries[:-4]] == [None] * 5
    assert [e["id"] for e in entries] == sorted((e["id"] for e in entries), reverse=True)

    everything = client.get("/api/ledger").json()["entries"]
    assert everything[0]["symbol"] == "AAL" and len(everything) == 10
    assert client.get("/api/ledger", params={"symbol": "aapl", "limit": 2}).json() == {
        "entries": entries[:2]
    }
    assert client.get("/api/companies/AAPL/ledger", params={"limit": 1}).json() == {
        "entries": entries[:1]
    }
    assert client.get("/api/ledger", params={"limit": 0}).status_code == 400


def _snapshot_until(db_path: Path, symbol: str, valid_until: date) -> int:
    """A newer snapshot of ``symbol`` under the latest refresh, its window ending ``valid_until``,
    as a price refresh writes one in the same window or a full refresh a new window; its id."""
    result = refusal_result(symbol, "a test row", load_policy(), date(2026, 9, 1))
    with closing(connect(db_path)) as conn:
        refresh_id = conn.execute("SELECT MAX(id) FROM refreshes").fetchone()[0]
        return insert_snapshot(
            conn, replace(result, valid_until=valid_until), refresh_id, clock=lambda: NOW
        )


def test_the_inbox_read_posts_nothing_for_an_expired_watched_company(
    client: TestClient, db_path: Path
) -> None:
    """Spec 2026-11-25 owner's inbox, 8: Fairband posts no work item by itself. AAPL is on a
    watchlist and its latest snapshot's window ended before the clock's day, and a read of the
    inbox posts no item and writes no ledger row of the system's."""
    _snapshot_until(db_path, "AAPL", TODAY - timedelta(days=1))
    core = _post(client, "/api/watchlists", {"name": "Core"}, HEADER)
    client.put(f"/api/watchlists/{core['id']}/symbols/AAPL", headers=HEADER)
    assert client.get("/api/inbox").json()["items"] == []
    assert [e for e in _ledger(client, "AAPL") if e["principal"] == "system"] == []


def test_the_inbox_read_takes_no_write_lock(client: TestClient, db_path: Path) -> None:
    """Spec 2026-11-25 owner's inbox, 7: the read writes nothing, so it answers while another
    connection holds the write lock, as a refresh does all the while it writes."""
    with closing(connect(db_path)) as other:
        other.execute("BEGIN IMMEDIATE")
        try:
            answer = client.get("/api/inbox")
        finally:
            other.rollback()
    assert answer.status_code == 200


def test_a_declined_item_over_the_api_from_the_owner(client: TestClient) -> None:
    """The Inbox view's Decline (spec 18.5): the owner declines an open item, pending or claimed,
    with a reason kept as written. The item leaves the open items the header counts and the
    ledger names the owner. A blank reason is refused 400 and a closed item 409, each with the
    sentence the page shows."""
    pending = _post(client, "/api/inbox", {"symbol": "AAPL", "mode": "valuation review"}, HEADER)
    claimed = _post(client, "/api/inbox", {"symbol": "AAL", "mode": "full report"}, HEADER)
    client.post("/api/inbox/claim", json={"itemId": claimed["id"]}, headers=AGENT)

    def open_items() -> list[int]:
        items = client.get("/api/inbox").json()["items"]
        return [i["id"] for i in items if i["state"] in ("pending", "claimed")]

    assert open_items() == [claimed["id"], pending["id"]]
    url = f"/api/inbox/{pending['id']}"
    r = client.patch(url, json={"action": "decline", "reason": "  "}, headers=HEADER)
    assert (r.status_code, r.json()) == (400, {"detail": "a decline needs a reason"})
    reason = "Held: no new filing since the window"
    r = client.patch(url, json={"action": "decline", "reason": reason}, headers=HEADER)
    assert r.status_code == 200, r.text
    assert (r.json()["state"], r.json()["reason"], r.json()["finishedAt"]) == (
        "declined",
        reason,
        AT,
    )
    r = client.patch(
        f"/api/inbox/{claimed['id']}",
        json={"action": "decline", "reason": "not now"},
        headers=HEADER,
    )
    assert (r.status_code, r.json()["state"], r.json()["claimedBy"]) == (
        200,
        "declined",
        "claude-opus-5-5",
    )
    assert open_items() == []
    r = client.patch(url, json={"action": "decline", "reason": "again"}, headers=HEADER)
    assert (r.status_code, r.json()) == (409, {"detail": f"work item {pending['id']} is declined"})
    [declined] = [e for e in _ledger(client, "AAPL") if e["kind"] == "decline"]
    assert (declined["principal"], declined["actor"], declined["workItemId"]) == (
        "owner",
        None,
        pending["id"],
    )
    assert declined["summary"] == f"declined: {reason}"
