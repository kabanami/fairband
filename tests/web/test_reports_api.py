"""The report routes (spec 2026-11-06 Tier 2, 12, 13.1, 13.6 and 16) on the database of
``conftest.py``: AAPL (the Mature Growth golden: a price of $150, a value of $133.37), AAL (Young
Growth, refused for its target margin) and HGCO (High Growth), each with one snapshot and a
secondary valuation on it (``secondaries``). A clean submission publishes, completes the work item
it names and stores its judgments, kill criteria and news items; a rejected one stores nothing but
its ledger row."""

from contextlib import closing
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from support.engine_companies import mature_growth_inputs, universe_deciles
from support.web import HEADER, NOW, TODAY

from fairband.engine.route import reprice, value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.reports.check import HEADINGS, NO_REFERENCE, UNRESOLVED, headings
from fairband.store.db import connect
from fairband.store.refreshes import latest_refresh
from fairband.store.snapshots import insert_snapshot, snapshot_row
from fairband.web.identity import ACTOR_HEADER, CLIENT_HEADER, PRINCIPAL_HEADER

pytestmark = pytest.mark.usefixtures("secondaries")

AGENT = HEADER | {
    PRINCIPAL_HEADER: "agent",
    ACTOR_HEADER: "claude-opus-5-5",
    CLIENT_HEADER: "claude-code/2.1",
}
JUDGMENTS = [
    {"judgment": kind, "decision": f"keep the {kind}"}
    for kind in ("phase", "moat", "belief", "roic")
]


def _snapshot_id(client: TestClient, symbol: str = "AAPL") -> int:
    found: int = client.get(f"/api/companies/{symbol}").json()["snapshot"]["id"]
    return found


def _sections(sid: int, mode: str = "full report", *extra: Any) -> list[dict[str, Any]]:
    """The sections of ``mode``: section 1 cites the price, the value and r, then ``extra``."""
    s = f"snapshot:{sid}"
    first = [
        "The price of ",
        {"cite": "$150.00", "ref": f"{s}/price"},
        " is above the value at belief of ",
        {"cite": "$133", "ref": f"{s}/value"},
        ", discounted at ",
        {"cite": "9.0%", "ref": "policy:required_return"},
        ". Three reasons stand out in FY2025.",
        *extra,
    ]
    rest = [{"heading": h, "parts": ["Plain words."]} for h in headings(mode)[1:]]
    return [{"heading": "Summary", "parts": first}, *rest]


def _body(sid: int, **changes: Any) -> dict[str, Any]:
    body = {
        "mode": "full report",
        "stance": "hold",
        "sections": _sections(sid),
        "judgments": JUDGMENTS,
    }
    return body | changes


def _submit(client: TestClient, body: dict[str, Any], symbol: str = "AAPL") -> Any:
    return client.post(f"/api/companies/{symbol}/reports", json=body, headers=AGENT)


def _published(client: TestClient, body: dict[str, Any], symbol: str = "AAPL") -> Any:
    r = _submit(client, body, symbol)
    assert r.status_code == 201, r.text
    return r.json()["report"]


def _ledger(client: TestClient, symbol: str = "AAPL") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = client.get(f"/api/companies/{symbol}/ledger").json()["entries"]
    return found


def test_a_clean_submission_publishes_and_completes_the_item(
    client: TestClient, secondaries: dict[str, int]
) -> None:
    sid = _snapshot_id(client)
    item = client.post("/api/inbox", json={"symbol": "AAPL", "mode": "full report"}, headers=HEADER)
    item_id = item.json()["id"]
    client.post("/api/inbox/claim", json={"itemId": item_id}, headers=AGENT)
    report = _published(client, _body(sid, workItemId=item_id))
    generated = ("judgments", "appendixA", "appendixB", "references")
    assert {k: v for k, v in report.items() if k not in generated} == {
        "id": report["id"],
        "symbol": "AAPL",
        "revision": 1,
        "mode": "full report",
        "stance": "hold",
        "sections": _sections(sid),
        "reusesFullReportOf": None,
        "snapshotId": sid,
        "reviewId": None,
        "secondaryId": secondaries["AAPL"],  # the newest on the snapshot, as the check asks
        "workItemId": item_id,
        "principal": "agent",
        "actor": "claude-opus-5-5",
        "client": "claude-code/2.1",
        "createdAt": NOW.isoformat(),
    }
    assert [
        {k: v for k, v in j.items() if k not in ("id", "reportId")} for j in report["judgments"]
    ] == [{"symbol": "AAPL", **j, "overrideId": None} for j in JUDGMENTS]
    assert report["appendixA"]["snapshot"]["id"] == sid
    assert [t["term"] for t in report["appendixB"]] == ["Value at belief", "Belief"]
    version = report["appendixA"]["versions"]["policy"]
    assert report["references"] == [
        {
            "n": 1,
            "ref": f"snapshot:{sid}/price",
            "source": f"snapshot {sid}, the price, priced 30 Oct 2026",
        },
        {
            "n": 2,
            "ref": f"snapshot:{sid}/value",
            "source": f"snapshot {sid}, the value a share, priced 30 Oct 2026",
        },
        {"n": 3, "ref": "policy:required_return", "source": f"policy required_return, {version}"},
    ]
    assert client.get(f"/api/reports/{report['id']}").json() == report
    done = client.get("/api/inbox").json()["items"][0]
    assert (done["state"], done["reportId"]) == ("done", report["id"])
    entries = _ledger(client)
    kinds = [(e["kind"], e["refTable"], e["workItemId"]) for e in entries[:6]]
    assert kinds == [
        ("complete", "work_items", item_id),
        *[("judgment", "judgments", None)] * 4,
        ("report", "reports", item_id),
    ]
    assert entries[5]["refId"] == report["id"] and entries[5]["snapshotId"] == sid
    assert entries[5]["summary"] == "full report revision 1: hold"
    assert entries[0]["summary"] == f"completed with report {report['id']}"


def test_a_rejection_stores_nothing_but_the_ledger_row(client: TestClient) -> None:
    sid = _snapshot_id(client)
    bad = [
        " Revenue grew 11.2%.",
        {"cite": "$2,100,000,000", "ref": "fact:AAPL/revenue/2031"},
    ]
    r = _submit(client, _body(sid, sections=_sections(sid, "full report", *bad)))
    assert r.status_code == 422
    assert r.json() == {
        "findings": [
            {
                "where": "section 1, part 8: 11.2%",
                "what": NO_REFERENCE,
                "detail": "cite it with its reference, or write a small count in words",
            },
            {
                "where": "section 1, part 9: $2,100,000,000",
                "what": UNRESOLVED,
                "detail": "fact:AAPL/revenue/2031 names no stored value",
            },
        ]
    }
    assert client.get("/api/companies/AAPL/reports").json() == {"reports": []}
    assert client.get("/api/companies/AAPL/kill-criteria").json() == {"killCriteria": []}
    [entry] = _ledger(client)
    assert (entry["kind"], entry["refTable"], entry["refId"], entry["snapshotId"]) == (
        "report",
        None,
        None,
        sid,
    )
    assert (entry["summary"], entry["actor"]) == ("rejected: 2 findings", "claude-opus-5-5")
    one = _submit(client, _body(sid, sections=_sections(sid, "full report", bad[0])))
    assert one.status_code == 422 and _ledger(client)[0]["summary"] == "rejected: 1 finding"


def test_a_review_mode_has_ten_sections(client: TestClient) -> None:
    sid = _snapshot_id(client)
    review = _body(sid, mode="valuation review", sections=_sections(sid, "valuation review"))
    first = _published(client, review)
    assert (first["mode"], first["reusesFullReportOf"], len(first["sections"])) == (
        "valuation review",
        None,
        10,
    )
    full = _published(client, _body(sid))
    second = _published(client, review)
    assert second["reusesFullReportOf"] == full["id"]
    r = _submit(client, _body(sid, mode="valuation review"))
    assert (r.status_code, r.json()) == (
        400,
        {"detail": "a valuation review has 10 sections, not 12"},
    )
    sections = _sections(sid)
    sections[1], sections[2] = sections[2], sections[1]
    r = _submit(client, _body(sid, sections=sections))
    detail = "section 2 is headed 'The business', not 'Industry and competition'"
    assert (r.status_code, r.json()) == (400, {"detail": detail})


def test_an_unknown_stance_is_refused(client: TestClient) -> None:
    r = _submit(client, _body(_snapshot_id(client), stance="accumulate"))
    detail = "a stance is one of buy, hold, trim or avoid, not 'accumulate'"
    assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert _ledger(client) == []  # a refusal before the number check is no ledger row


def test_the_required_judgments(client: TestClient) -> None:
    sid = _snapshot_id(client)
    r = _submit(client, _body(sid, judgments=JUDGMENTS[:3]))
    assert (r.status_code, r.json()) == (400, {"detail": "the report lacks the judgment roic"})
    for symbol in ("HGCO", "AAL"):  # the revenue-growth route, valued or refused
        r = _submit(client, _body(_snapshot_id(client, symbol), judgments=JUDGMENTS), symbol)
        assert (r.status_code, r.json()) == (
            400,
            {"detail": "the report lacks the judgment target_margin"},
        )
    margin = {"judgment": "target_margin", "decision": "d"}
    hgco = _snapshot_id(client, "HGCO")
    sections = _sections(hgco)
    sections[0]["parts"] = ["Plain words."]
    assert _published(
        client, _body(hgco, sections=sections, judgments=[*JUDGMENTS, margin]), "HGCO"
    )
    r = _submit(client, _body(sid, judgments=[*JUDGMENTS, {**margin, "judgment": "luck"}]))
    assert r.status_code == 400 and r.json()["detail"].startswith("judgments.4.judgment: ")
    with_override = [*JUDGMENTS[:3], {**JUDGMENTS[3], "overrideId": 99}]
    r = _submit(client, _body(sid, judgments=with_override))
    assert (r.status_code, r.json()) == (404, {"detail": "no override 99 for AAPL"})
    assert client.get("/api/companies/AAPL/reports").json() == {"reports": []}


def test_markdown_download(client: TestClient) -> None:
    report = _published(client, _body(_snapshot_id(client)))
    r = client.get(f"/api/reports/{report['id']}/markdown")
    assert r.status_code == 200
    assert r.headers["content-type"] == "text/markdown; charset=utf-8"
    lines = r.text.splitlines()
    assert lines[0] == "AAPL · full report · 2026-11-01 · claude-opus-5-5 · revision 1"
    assert [line[3:] for line in lines if line.startswith("## ")] == [
        *HEADINGS,
        "References",
        "Appendix A",
        "Appendix B",
    ]
    assert "The price of $150.00[^1] is above the value at belief of $133[^2]" in r.text
    assert f"[^1]: snapshot:{report['snapshotId']}/price — snapshot " in r.text
    assert "### Growth and profitability" in r.text  # section 4's chart tables
    r = client.get("/api/reports/99/markdown")
    assert (r.status_code, r.json()) == (404, {"detail": "no report 99"})
    assert client.get("/api/reports/99").status_code == 404


def test_a_second_submission_is_revision_two(client: TestClient) -> None:
    sid = _snapshot_id(client)
    first = _published(client, _body(sid))
    second = _published(client, _body(sid, stance="trim"))
    assert (first["revision"], second["revision"], second["stance"]) == (1, 2, "trim")
    listed = client.get("/api/companies/aapl/reports").json()["reports"]
    assert [(r["id"], r["revision"]) for r in listed] == [(second["id"], 2), (first["id"], 1)]
    assert "sections" not in listed[0] and listed[0]["actor"] == "claude-opus-5-5"


def test_kill_criteria_and_news_items_are_stored_with_the_report(client: TestClient) -> None:
    sid = _snapshot_id(client)
    news = {
        "date": "2026-10-28",
        "headline": "Guidance raised",
        "source": "https://example.com/news",
        "text": "The company raised its guidance.",
    }
    report = _published(
        client,
        _body(sid, killCriteria=[{"text": "revenue falls two quarters running"}], newsItems=[news]),
    )
    [criterion] = client.get("/api/companies/AAPL/kill-criteria").json()["killCriteria"]
    assert (criterion["text"], criterion["state"], criterion["reportId"]) == (
        "revenue falls two quarters running",
        "open",
        report["id"],
    )
    assert criterion["actor"] == "claude-opus-5-5"
    [item] = client.get("/api/companies/AAPL/news-items").json()["newsItems"]
    assert (item["headline"], item["date"], item["killCriterionId"], item["reportId"]) == (
        "Guidance raised",
        "2026-10-28",
        None,
        report["id"],
    )
    kinds = [e["kind"] for e in _ledger(client)]
    assert kinds[:2] == ["news-item", "kill-criterion"] and kinds[-1] == "report"
    r = _submit(client, _body(sid, killCriteria=[{"text": " "}]))
    assert (r.status_code, r.json()) == (400, {"detail": "a kill criterion needs text"})
    assert len(client.get("/api/companies/AAPL/reports").json()["reports"]) == 1


def test_a_named_work_item_must_be_the_company_s_and_open(client: TestClient) -> None:
    sid = _snapshot_id(client)
    r = _submit(client, _body(sid, workItemId=99))
    assert (r.status_code, r.json()) == (404, {"detail": "no work item 99"})
    other = client.post("/api/inbox", json={"symbol": "AAL", "mode": "full report"}, headers=HEADER)
    r = _submit(client, _body(sid, workItemId=other.json()["id"]))
    assert (r.status_code, r.json()) == (
        404,
        {"detail": f"no work item {other.json()['id']} for AAPL"},
    )
    item = client.post("/api/inbox", json={"symbol": "AAPL", "mode": "full report"}, headers=HEADER)
    item_id = item.json()["id"]
    client.patch(f"/api/inbox/{item_id}", json={"action": "decline", "reason": "no"}, headers=AGENT)
    r = _submit(client, _body(sid, workItemId=item_id))
    assert (r.status_code, r.json()) == (409, {"detail": f"work item {item_id} is declined"})
    assert client.get("/api/companies/AAPL/reports").json() == {"reports": []}


def test_complete_takes_a_published_report_of_the_item_s_company(client: TestClient) -> None:
    report = _published(client, _body(_snapshot_id(client)))
    other = client.post("/api/inbox", json={"symbol": "AAL", "mode": "full report"}, headers=HEADER)
    url = f"/api/inbox/{other.json()['id']}"
    r = client.patch(url, json={"action": "complete", "reportId": report["id"]}, headers=AGENT)
    assert (r.status_code, r.json()) == (404, {"detail": f"no report {report['id']} for AAL"})
    item = client.post("/api/inbox", json={"symbol": "AAPL", "mode": "full report"}, headers=HEADER)
    url = f"/api/inbox/{item.json()['id']}"
    r = client.patch(url, json={"action": "complete", "reportId": report["id"]}, headers=AGENT)
    assert r.status_code == 200 and r.json()["reportId"] == report["id"]


def test_a_company_without_a_snapshot_has_no_report(client: TestClient) -> None:
    r = _submit(client, _body(1), "MSFT")
    assert (r.status_code, r.json()) == (404, {"detail": "no snapshot for MSFT"})


def test_a_judgment_with_bull_or_bear_is_an_unknown_field(client: TestClient) -> None:
    """A judgment is a record of the decision and its override: the debate is the report's own
    section, so a judgment carrying a bull or a bear case is refused by the body's validation,
    as every request the routes' types refuse is, naming the field."""
    sid = _snapshot_id(client)
    phase = {**JUDGMENTS[0], "bull": "Revenue still grows."}
    moat = {**JUDGMENTS[1], "bear": "Rivals sell substitutes."}
    r = _submit(client, _body(sid, judgments=[phase, moat, *JUDGMENTS[2:]]))
    detail = (
        "judgments.0.bull: Extra inputs are not permitted;"
        " judgments.1.bear: Extra inputs are not permitted"
    )
    assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert _ledger(client) == []  # refused before the number check: no ledger row
    assert client.get("/api/companies/AAPL/reports").json() == {"reports": []}


def test_a_judgment_s_text_holds_no_figure(client: TestClient) -> None:
    sid = _snapshot_id(client)
    moat = {**JUDGMENTS[1], "decision": "Keep Wide: share rose 11.2% on patents."}
    r = _submit(client, _body(sid, judgments=[JUDGMENTS[0], moat, *JUDGMENTS[2:]]))
    assert (r.status_code, r.json()) == (
        422,
        {
            "findings": [
                {
                    "where": "judgment moat, decision: 11.2%",
                    "what": NO_REFERENCE,
                    "detail": "a judgment's text holds no figure: cite it in a section",
                }
            ]
        },
    )
    assert _ledger(client)[0]["summary"] == "rejected: 1 finding"
    assert client.get("/api/companies/AAPL/reports").json() == {"reports": []}


def test_a_secondary_on_an_older_snapshot_does_not_count(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """A reprice keeps the snapshot's secondary valuation in force; a revalue leaves it on an
    older snapshot, so a submission is refused naming the latest snapshot, whatever its cites."""
    sid = _snapshot_id(client)
    with closing(connect(db_path)) as conn:
        cited = snapshot_row(conn, sid)
        assert cited is not None and cited.value is not None
        repriced = reprice(results["AAPL"], 160.0, date(2026, 11, 2), policy)
        insert_snapshot(conn, repriced, cited.refresh_id, clock=lambda: NOW)
    report = _published(client, _body(sid))
    assert (report["snapshotId"], report["secondaryId"]) == (sid, secondaries["AAPL"])
    with closing(connect(db_path)) as conn:
        revalued = replace(repriced, value=cited.value + 1.0)
        latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    assert _snapshot_id(client) == latest
    detail = f"the report needs a secondary valuation on snapshot {latest}"
    for body in (_body(latest), _body(sid)):
        r = _submit(client, body)
        assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert len(client.get("/api/companies/AAPL/reports").json()["reports"]) == 1


@pytest.mark.parametrize(
    ("symbol", "changes", "why"),
    [
        ("FRGN", {"currency": "EUR"}, "foreign filer"),
        ("NOSH", {"shares_diluted": None}, "no diluted share count"),
        ("PLAIN", {}, None),
    ],
)
def test_a_company_that_can_have_no_secondary_publishes_without_one(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    symbol: str,
    changes: dict[str, Any],
    why: str | None,
) -> None:
    """The secondary route refuses a foreign filer and a snapshot with no diluted share count, so
    the report needs no secondary valuation there and Appendix A names why; a company the route
    values still needs one."""
    inputs = replace(mature_growth_inputs(), symbol=symbol, **changes)
    result = value_company(inputs, universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        refresh = latest_refresh(conn)
        assert refresh is not None
        sid = insert_snapshot(conn, result, refresh.id, clock=lambda: NOW)
    sections = [{"heading": h, "parts": ["Plain words."]} for h in HEADINGS]
    body = _body(sid, sections=sections)
    if why is None:
        r = _submit(client, body, symbol)
        detail = f"the report needs a secondary valuation on snapshot {sid}"
        assert (r.status_code, r.json()) == (400, {"detail": detail})
        return
    report = _published(client, body, symbol)
    assert (report["snapshotId"], report["secondaryId"]) == (sid, None)
    a = report["appendixA"]
    assert (a["secondary"], a["noSecondary"]) == (None, f"no secondary valuation: {why}")
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    block = text.split("### Secondary valuation\n\n", 1)[1].split("\n", 1)[0]
    assert block == f"No secondary valuation: {why}."


def test_appendix_a_says_none_for_a_report_with_no_secondary_that_could_have_one(
    client: TestClient, db_path: Path
) -> None:
    """A report published without a secondary valuation on a company that can have one (a plan 1
    report) names no reason."""
    report = _published(client, _body(_snapshot_id(client)))
    with closing(connect(db_path)) as conn:
        conn.execute("UPDATE reports SET secondary_id = NULL WHERE id = ?", (report["id"],))
        conn.commit()
    a = client.get(f"/api/reports/{report['id']}").json()["appendixA"]
    assert (a["secondary"], a["noSecondary"]) == (None, None)
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    assert "### Secondary valuation\n\nNone.\n" in text


def test_a_plan_1_parts_record_reads_and_renders(
    client: TestClient, db_path: Path, secondaries: dict[str, int]
) -> None:
    """A secondary valuation written under ``fairband-secondary/1``, as migration 006 leaves one:
    the parts form with no grid. The API reads it with ``grid: null``; a report resting on it
    renders its parts, "No grid." in Appendix A, and no grid table in the Markdown."""
    secondary_id = secondaries["AAPL"]
    with closing(connect(db_path)) as conn:
        conn.execute(
            "UPDATE secondary_valuations SET grid = NULL, secondary_method = ? WHERE id = ?",
            ("fairband-secondary/1", secondary_id),
        )
        conn.commit()
    [listed] = client.get("/api/companies/AAPL/secondary").json()["secondaryValuations"]
    assert (listed["id"], listed["form"], listed["grid"]) == (secondary_id, "parts", None)
    assert listed["secondaryMethod"] == "fairband-secondary/1"
    assert (listed["drivers"], listed["projection"]) == (None, None)
    assert [p["name"] for p in listed["parts"]] == ["the business"]
    report = _published(client, _body(_snapshot_id(client)))
    a = report["appendixA"]
    assert (a["secondary"]["id"], a["secondary"]["form"], a["secondary"]["grid"]) == (
        secondary_id,
        "parts",
        None,
    )
    assert a["versions"]["secondary"] == "fairband-secondary/1"
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    block = text.split("### Secondary valuation\n\n", 1)[1].split("\n### ", 1)[0]
    assert block.startswith(f"Secondary valuation {secondary_id}, from parts: firm value ")
    assert "| the business |" in block
    assert block.rstrip().endswith("No grid.")
    assert "The grid of secondary valuation" not in text
