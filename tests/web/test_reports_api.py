"""The report routes (spec 2026-11-06 Tier 2, 12, 13.1, 13.6 and 16) on the database of
``conftest.py``: AAPL (the Mature Growth golden: a price of $150, a value of $127.68), AAL (Young
Growth, refused for its target margin) and HGCO (High Growth), each with one snapshot and a
secondary valuation on it (``secondaries``): on AAL's refused snapshot the fallback a report needs,
on AAPL's and HGCO's valued ones a record made before plan 3 that a report there need not name;
once a margin override values AAL (``_aal_review``), AAL's is such a record too. Every test starts
with an agent's moat verdict on each company's snapshot (``verdicts``), which a report needs there
(spec 2026-11-19 8.7); a test that writes a later snapshot records one on it (``record_verdict``).
A clean submission publishes, completes the work item it names and stores its judgments, kill
criteria and news items; a rejected one stores nothing but its ledger row."""

from contextlib import closing
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from refresh.synthetic import bodies
from support.engine_companies import mature_growth_inputs, universe_deciles, young_growth_inputs
from support.payloads import store_payloads
from support.reports import AGENT, JUDGMENTS
from support.reports import body as _body
from support.reports import published as _published
from support.reports import sections as _sections
from support.reports import snapshot_id as _snapshot_id
from support.reports import submit as _submit
from support.vendor import FIXTURES, Vendor
from support.web import HEADER, NOW, TODAY
from support.web_app import record_verdict

from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import reprice, value_company
from fairband.engine.types import ValuationResult
from fairband.policy import Policy
from fairband.policy.moat import MoatTable
from fairband.reports.check import HEADINGS, NO_REFERENCE, UNRESOLVED
from fairband.reports.refs import day_words
from fairband.store.db import connect
from fairband.store.ledger import Writer
from fairband.store.moat import file_moat, set_moat, set_snapshot
from fairband.store.overrides import insert_override
from fairband.store.refreshes import latest_refresh
from fairband.store.reviews import held_row, hold_review, insert_review, set_held_state
from fairband.store.snapshots import insert_snapshot, snapshot_row

pytestmark = pytest.mark.usefixtures("secondaries", "verdicts")

# AAL's route, the revenue-growth route's, asks for the target margin in place of the ROIC.
REFUSED_JUDGMENTS = [
    {"judgment": kind, "decision": f"keep the {kind}"}
    for kind in ("phase", "moat", "belief", "target_margin")
]
# Appendix A's sentences where the company can have no secondary valuation, in the register's words
# (spec 2026-11-15 7)
ROUTE_VALUES = "No secondary valuation: Fairband's own valuation gives the company a value"
REVIEW_VALUES = "No secondary valuation: the review gives the company a value"
# Refusals an agent cannot fix (spec 2026-11-10 7.6), as the engine words them; and the one the
# engine gave a foreign filer before method 1.1, which a snapshot on file may carry.
ABOVE_BOUND = "ARS: expected inflation 12.1% above the 10% bound"
BASIS = (
    "share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the ADR"
    " ratio 10)"
)
FOREIGN_FILER = "foreign filer: currency and share-unit handling not built yet"


def _refused_body(sid: int) -> dict[str, Any]:
    """A full report on AAL's refused snapshot ``sid``: section 1 cites the price, which a refusal
    keeps; the rest is plain."""
    first = [
        "The price of ",
        {"cite": "$150.00", "ref": f"snapshot:{sid}/price"},
        " stands where the route refuses.",
    ]
    rest = [{"heading": h, "parts": ["Plain words."]} for h in HEADINGS[1:]]
    return _body(
        sid,
        sections=[{"heading": "Summary", "parts": first}, *rest],
        judgments=REFUSED_JUDGMENTS,
    )


def _ledger(client: TestClient, symbol: str = "AAPL") -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = client.get(f"/api/companies/{symbol}/ledger").json()["entries"]
    return found


READ_AGAIN = "the review was made before the latest refresh: make it again"


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
        "secondaryId": None,  # the route values AAPL: the secondary on file is not the report's
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


def test_a_filing_cell_the_search_finds_is_cited_and_named(
    with_passthrough: TestClient, vendor: Vendor
) -> None:
    """The final review's C.12, the filings feature end to end: the search finds the row of the
    leases not yet commenced in AAPL's 10-Q (the synthetic ACME report, which the mock vendor
    serves for AAPL); its ``rowRef`` plus the number's column is cited, the report publishes, and
    its references name the filing, the sheet, the row and the column."""
    stored = (FIXTURES / "financial-reports-json.ACME.json").read_bytes()
    vendor.answer = lambda request: httpx.Response(
        200, content=stored, headers={"Content-Type": "application/json"}
    )
    asked = {"year": "2027", "period": "Q1", "text": "not yet commenced"}
    found = with_passthrough.get("/api/companies/AAPL/filing-report/search", params=asked).json()
    [hit] = [h for h in found["hits"] if h["numbers"]]
    [number] = hit["numbers"]
    assert (number["value"], number["column"]) == (12.5, "3 Months Ended, Sep. 30, 2026")
    ref = f"{hit['rowRef']}/{number['col']}"
    sid = _snapshot_id(with_passthrough)
    cited = [
        " At the quarter's end, leases not yet commenced came to ",
        {"cite": "$12.5", "ref": ref},
        " million.",
    ]
    report = _published(
        with_passthrough, _body(sid, sections=_sections(sid, "full report", *cited))
    )
    [reference] = [r for r in report["references"] if r["ref"] == ref]
    assert reference == {
        "n": 4,
        "ref": f"filing:{found['responseId']}/Leases - Additional Informatio/2/0",
        "source": (
            "FMP filing report of fiscal 2027 Q1, Leases - Additional Informatio: Additional"
            " leases, primarily for warehouses, that have not yet commenced, column 0 (3 Months"
            " Ended, Sep. 30, 2026), observed 1 Nov 2026"
        ),
    }
    # a cite of the wrong value is caught as any figure is
    wrong = [{"cite": "$11.5", "ref": ref}, " million."]
    refused = _submit(with_passthrough, _body(sid, sections=_sections(sid, "full report", *wrong)))
    assert refused.status_code == 422


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
    # the export names the full report it reuses by its date, as the page's line does, and the
    # first, which reuses none, says so (spec 2026-11-15 7)
    reused = datetime.fromisoformat(full["createdAt"]).date()
    text = client.get(f"/api/reports/{second['id']}/markdown").text
    assert text.splitlines()[3] == f"Reuses the full report of {day_words(reused)}."
    text = client.get(f"/api/reports/{first['id']}/markdown").text
    assert text.splitlines()[3] == "No full report to reuse."
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


def test_a_review_whose_reused_report_is_gone_still_exports(
    client: TestClient, db_path: Path
) -> None:
    """A stored report always renders: a valuation review whose reused full report's record is not
    on file exports, its line naming no day (spec 2026-11-15 7)."""
    sid = _snapshot_id(client)
    full = _published(client, _body(sid))
    sections = _sections(sid, "valuation review")
    review = _published(client, _body(sid, mode="valuation review", sections=sections))
    assert review["reusesFullReportOf"] == full["id"]
    with closing(connect(db_path)) as conn:
        conn.execute("DELETE FROM reports WHERE id = ?", (full["id"],))
        conn.commit()
    r = client.get(f"/api/reports/{review['id']}/markdown")
    assert r.status_code == 200
    assert r.text.splitlines()[3] == "Reuses an earlier full report."


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
    assert lines[0] == "AAPL · full report · 1 Nov 2026 · claude-opus-5-5 · revision 1"
    assert lines[2] == (
        "Stance: hold. On the data of 30 Oct 2026, priced that day, valid until 28 Jan 2027."
    )
    assert [line[3:] for line in lines if line.startswith("## ")] == [
        *HEADINGS,
        "Appendix A",
        "Appendix B",
        "References",
    ]
    assert "The price of $150.00[^1] is above the value at belief of $128[^2]" in r.text
    references = r.text.split("\n## References\n", 1)[1]
    assert f"[^1]: snapshot:{report['snapshotId']}/price — snapshot " in references
    assert "### Growth and profitability" in r.text  # section 4's chart tables
    assert "### By quarter" in r.text  # section 5's
    r = client.get("/api/reports/99/markdown")
    assert (r.status_code, r.json()) == (404, {"detail": "no report 99"})
    assert client.get("/api/reports/99").status_code == 404


def test_appendix_a_s_guidance_carries_each_record_s_currency(client: TestClient) -> None:
    """Spec 2026-11-15 9.5: a report's Appendix A gives each guidance record the currency of its
    money, the stored code, else the snapshot's reporting currency, AAPL's USD, none for a percent;
    the export's table names it in a Currency column after the midpoint, its numbers bare, the
    cell empty for the percent."""
    said = {"period": "2027", "basis": "gaap", "asOf": "2026-10-28", "text": "Guided."}
    posted = {}
    for metric, low, high, currency in (
        ("revenue", 24e9, 25e9, None),
        ("capex", 2e9, 2e9, "EUR"),
        ("operating_margin", 0.3, 0.32, None),
    ):
        body = said | {"metric": metric, "low": low, "high": high, "source": "response:1/0/content"}
        r = client.post(
            "/api/companies/AAPL/guidance", json=body | {"currency": currency}, headers=AGENT
        )
        assert r.status_code == 201, r.text
        posted[metric] = r.json()["id"]
    report = _published(client, _body(_snapshot_id(client)))
    guidance = client.get(f"/api/reports/{report['id']}").json()["appendixA"]["guidance"]
    assert {g["id"]: g["currency"] for g in guidance} == {
        posted["revenue"]: "USD",
        posted["capex"]: "EUR",
        posted["operating_margin"]: None,
    }
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    block = text[text.index("### Guidance on file") : text.index("### Bridge")]
    assert "| Low | High | Midpoint | Currency | Basis | Call |" in block
    revenue, capex, margin = (posted[m] for m in ("revenue", "capex", "operating_margin"))
    assert (
        f"| {revenue} | revenue | 2027 | 24000000000.0 | 25000000000.0 | 24500000000.0 | USD |"
    ) in block
    assert f"| {capex} | capex | 2027 | 2000000000.0 | 2000000000.0 | 2000000000.0 | EUR |" in block
    assert f"| {margin} | operating_margin | 2027 | 0.3 | 0.32 | 0.31 |  | gaap |" in block


def test_the_markdown_renders_when_the_consensus_cannot_be_read(
    client: TestClient, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole-branch review's M3: the export's chart tables read the consensus through the
    company's assembly, here on AAPL with the synthetic statements and two consensus years; where
    assembly raises, the report still exports, its growth table without estimate columns."""
    report = _published(client, _body(_snapshot_id(client)))
    statements = {e: p for e, p in bodies().items() if e != "earnings"}
    consensus = [
        {"symbol": "AAPL", "date": f"{year}-12-31", "revenueAvg": 2_200_000_000, "epsAvg": 3.3}
        for year in (2027, 2026)
    ]
    with closing(connect(db_path)) as conn:
        store_payloads(conn, "AAPL", {**statements, "estimates-annual": consensus}, NOW)
    r = client.get(f"/api/reports/{report['id']}/markdown")
    assert r.status_code == 200 and "| 2026 estimate | 2027 estimate |" in r.text

    def raising(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("assembly failed")

    monkeypatch.setattr("fairband.reports.tables.build_inputs", raising)
    r = client.get(f"/api/reports/{report['id']}/markdown")
    assert r.status_code == 200
    assert "| Revenue | " in r.text and " estimate |" not in r.text


def test_a_second_submission_is_revision_two(client: TestClient) -> None:
    sid = _snapshot_id(client)
    first = _published(client, _body(sid))
    second = _published(client, _body(sid, stance="trim"))
    assert (first["revision"], second["revision"], second["stance"]) == (1, 2, "trim")
    listed = client.get("/api/companies/aapl/reports").json()["reports"]
    assert [(r["id"], r["revision"]) for r in listed] == [(second["id"], 2), (first["id"], 1)]
    assert "sections" not in listed[0] and listed[0]["actor"] == "claude-opus-5-5"


def test_the_list_carries_what_the_report_page_reads(client: TestClient) -> None:
    """Spec 18.4 and the Research tab's design, 7.2 and 7.3: the tab's list of the reports on file
    names each revision by its date, revision, mode and stance and links each other one by its id,
    and the bar's line dates the full report a valuation review reuses from that report's entry,
    so the list carries each revision's id, date, writer, revision, mode, stance and the report it
    reuses, newest first, without its sections."""
    sid = _snapshot_id(client)
    full = _published(client, _body(sid))
    review = _body(sid, mode="valuation review", stance="trim")
    second = _published(client, review | {"sections": _sections(sid, "valuation review")})
    listed = client.get("/api/companies/AAPL/reports").json()["reports"]
    keys = ("id", "createdAt", "actor", "revision", "mode", "stance", "reusesFullReportOf")
    assert [{k: r[k] for k in keys} for r in listed] == [
        {
            "id": second["id"],
            "createdAt": NOW.isoformat(),
            "actor": "claude-opus-5-5",
            "revision": 2,
            "mode": "valuation review",
            "stance": "trim",
            "reusesFullReportOf": full["id"],
        },
        {
            "id": full["id"],
            "createdAt": NOW.isoformat(),
            "actor": "claude-opus-5-5",
            "revision": 1,
            "mode": "full report",
            "stance": "hold",
            "reusesFullReportOf": None,
        },
    ]
    assert all("sections" not in r and r["principal"] == "agent" for r in listed)


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


def test_a_kill_threshold_cited_in_risks_and_kill_criteria_publishes(client: TestClient) -> None:
    """Spec 2026-11-15 8.2: a criterion recorded with a threshold is cited as ``kill:<id>`` in
    "Risks and kill criteria"; the report publishes, its references say whose number it is, and
    they keep their words once the criterion is retired. Cited in another section, it refuses the
    report."""
    sid = _snapshot_id(client)
    body = {"text": "revenue growth below 5% for two years", "threshold": 0.05, "unit": "percent"}
    r = client.post("/api/companies/AAPL/kill-criteria", json=body, headers=AGENT)
    assert r.status_code == 201, r.text
    ref = f"kill:{r.json()['id']}"
    risks = [
        "The thesis ends if revenue growth falls below ",
        {"cite": "5%", "ref": ref},
        " for two years running.",
    ]
    sections = _sections(sid)
    at = HEADINGS.index("Risks and kill criteria")
    sections[at] = {"heading": HEADINGS[at], "parts": risks}
    report = _published(client, _body(sid, sections=sections))
    words = {
        "n": 4,
        "ref": ref,
        "source": f"kill criterion {ref[5:]}, a threshold the author chose",
    }
    assert report["references"][-1] == words
    r = client.patch(
        f"/api/kill-criteria/{ref[5:]}",
        json={"state": "retired", "reason": "the thesis changed"},
        headers=AGENT,
    )
    assert r.status_code == 200, r.text
    assert client.get(f"/api/reports/{report['id']}").json()["references"][-1] == words
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    assert f"[^4]: {ref} — kill criterion {ref[5:]}, a threshold the author chose" in text
    # in the Summary it is refused, whatever the criterion's state
    elsewhere = _submit(client, _body(sid, sections=_sections(sid, "full report", risks[1])))
    assert (elsewhere.status_code, elsewhere.json()) == (
        422,
        {
            "findings": [
                {
                    "where": "section 1, part 8: 5%",
                    "what": UNRESOLVED,
                    "detail": f"{ref} is the author's own threshold: cite it in Risks and kill"
                    " criteria",
                }
            ]
        },
    )


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


def test_a_report_needs_the_agent_s_verdict(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    moat_file: MoatTable,
) -> None:
    """Spec 2026-11-19 8.7: a report is refused, with nothing stored, unless the company's row of
    the moat table is an agent's whose snapshot is the latest or one the latest reprices: not with
    no row, the file's row, the owner's row on the snapshot, an agent's row moved by migration 010
    (on no snapshot) or an agent's on an older snapshot. On the latest, or on the one a price
    refresh repriced, it publishes."""
    sid = _snapshot_id(client)
    unrecorded = f"the report needs the moat verdict recorded on snapshot {sid}: call moat_set"
    owner = Writer("owner", None, None)
    agent = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    filing = {"kind": "filing", "ref": "10-K 2025", "note": None}

    def refused(answer: str = unrecorded, snapshot_id: int = sid, **changes: Any) -> None:
        r = _submit(client, _body(snapshot_id, **changes))
        assert (r.status_code, r.json()) == (400, {"detail": answer})

    with closing(connect(db_path)) as conn:
        conn.execute("DELETE FROM moat_classes WHERE symbol = 'AAPL'")
        conn.commit()
    refused()  # no row
    with closing(connect(db_path)) as conn:
        file_moat(conn, "AAPL", moat_file, NOW)
    refused()  # the file's
    with closing(connect(db_path)) as conn:
        set_moat(conn, "AAPL", "Wide", owner, "pricing power", None, NOW)
        set_snapshot(conn, "AAPL", sid)
    refused()  # the owner's, on the snapshot
    with closing(connect(db_path)) as conn:
        set_moat(conn, "AAPL", "Wide", agent, "the class stands", [filing], NOW)
    refused()  # an agent's on no snapshot, as migration 010 moves an applied override
    # the earlier checks answer first
    refused("the report lacks the judgment roic", judgments=JUDGMENTS[:3])
    assert client.get("/api/companies/AAPL/reports").json() == {"reports": []}
    assert _ledger(client) == []  # a refusal before the number check is no ledger row

    with closing(connect(db_path)) as conn:
        set_snapshot(conn, "AAPL", sid)
    assert _published(client, _body(sid))["snapshotId"] == sid  # on the latest
    with closing(connect(db_path)) as conn:
        cited = snapshot_row(conn, sid)
        assert cited is not None and cited.value is not None
        repriced = reprice(results["AAPL"], 160.0, date(2026, 11, 2), policy)
        priced = insert_snapshot(conn, repriced, cited.refresh_id, clock=lambda: NOW)
    assert _snapshot_id(client) == priced
    assert _published(client, _body(sid))["snapshotId"] == sid  # the latest reprices it
    with closing(connect(db_path)) as conn:
        revalued = replace(results["AAPL"], value=cited.value + 1.0)
        latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    plain = [{"heading": h, "parts": ["Plain words."]} for h in HEADINGS]
    older = f"the report needs the moat verdict recorded on snapshot {latest}: call moat_set"
    refused(older, latest, sections=plain)  # an agent's on an older snapshot
    record_verdict(db_path, "AAPL", latest)
    assert _published(client, _body(latest, sections=plain))["snapshotId"] == latest
    assert len(client.get("/api/companies/AAPL/reports").json()["reports"]) == 3


def test_a_secondary_on_an_older_snapshot_does_not_count(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """On a refused row (AAL) a reprice keeps the snapshot's secondary valuation in force; a
    revalue leaves it on an older snapshot, so a submission is refused naming the latest snapshot,
    whatever its cites (method 16.3, plan 3: a refused latest snapshot needs the fallback)."""
    sid = _snapshot_id(client, "AAL")
    with closing(connect(db_path)) as conn:
        cited = snapshot_row(conn, sid)
        assert cited is not None and cited.value is None
        repriced = reprice(results["AAL"], 160.0, date(2026, 11, 2), policy)
        insert_snapshot(conn, repriced, cited.refresh_id, clock=lambda: NOW)
    report = _published(client, _refused_body(sid), "AAL")
    assert (report["snapshotId"], report["secondaryId"]) == (sid, secondaries["AAL"])
    with closing(connect(db_path)) as conn:
        revalued = replace(repriced, data_date=repriced.data_date + timedelta(days=1))
        latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    assert _snapshot_id(client, "AAL") == latest
    record_verdict(db_path, "AAL", latest, "None")
    detail = f"the report needs a secondary valuation on snapshot {latest}"
    for body in (_refused_body(latest), _refused_body(sid)):
        r = _submit(client, body, "AAL")
        assert (r.status_code, r.json()) == (400, {"detail": detail})
    assert len(client.get("/api/companies/AAL/reports").json()["reports"]) == 1


def test_a_valued_row_revalued_needs_no_secondary(
    client: TestClient,
    db_path: Path,
    results: dict[str, ValuationResult],
) -> None:
    """A revalue leaves AAPL's secondary valuation on an older snapshot; the latest is valued, so
    the report publishes without one and Appendix A names why (method 16.3, plan 3)."""
    sid = _snapshot_id(client)
    with closing(connect(db_path)) as conn:
        cited = snapshot_row(conn, sid)
        assert cited is not None and cited.value is not None
        revalued = replace(results["AAPL"], value=cited.value + 1.0)
        latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    record_verdict(db_path, "AAPL", latest)
    sections = [{"heading": h, "parts": ["Plain words."]} for h in HEADINGS]
    report = _published(client, _body(latest, sections=sections))
    assert (report["snapshotId"], report["secondaryId"]) == (latest, None)
    a = report["appendixA"]
    assert (a["secondary"], a["noSecondary"]) == (None, ROUTE_VALUES)


def test_an_older_secondary_on_a_valued_snapshot_is_the_reports_only_when_cited(
    client: TestClient, secondaries: dict[str, int]
) -> None:
    """Review Focus 1, QCOM's case after plan 3: a secondary valuation made before plan 3 rests on
    AAPL's valued snapshot. A report that does not cite it publishes without naming it, Appendix A
    saying the route values the company; one that cites it publishes, the cite resolves and
    Appendix A names it, as a report that cited one before plan 3 still reads."""
    sid = _snapshot_id(client)
    secondary_id = secondaries["AAPL"]
    [found] = client.get("/api/companies/AAPL/secondary").json()["secondaryValuations"]
    assert found["id"] == secondary_id and found["snapshotId"] == sid
    plain = _published(client, _body(sid))
    assert plain["secondaryId"] is None
    a = plain["appendixA"]
    assert (a["secondary"], a["noSecondary"], a["versions"]["secondary"]) == (
        None,
        ROUTE_VALUES,
        None,
    )
    text = client.get(f"/api/reports/{plain['id']}/markdown").text
    assert text.split("### Secondary valuation\n\n", 1)[1].split("\n", 1)[0] == ROUTE_VALUES
    ref = f"secondary:{secondary_id}/value"
    cite = {"cite": f"${found['valuePerShare']:,.2f}", "ref": ref}
    citing = _published(client, _body(sid, sections=_sections(sid, "full report", cite)))
    assert citing["secondaryId"] == secondary_id
    a = citing["appendixA"]
    assert (a["secondary"]["id"], a["noSecondary"]) == (secondary_id, None)
    assert a["versions"]["secondary"] == "fairband-secondary/2"
    assert [r["ref"] for r in citing["references"]][-1] == ref


def test_a_refused_row_the_review_values_needs_no_secondary(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
) -> None:
    """The ruling on plan 3's final review: a margin override values AAL, refused for its target
    margin, so the review is the main method at work and the secondary valuation, the fallback
    where neither the route nor the review values the company, is refused there (method 15.4).
    Revalued, AAL's latest snapshot carries no secondary valuation; the report publishes without one
    and Appendix A says the review values the company, in the JSON and the Markdown (16.3, 16.6)."""
    sid = _snapshot_id(client, "AAL")
    with closing(connect(db_path)) as conn:
        cited = snapshot_row(conn, sid)
        assert cited is not None and cited.value is None
        revalued = replace(results["AAL"], data_date=results["AAL"].data_date + timedelta(days=1))
        latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    record_verdict(db_path, "AAL", latest, "None")
    review_id = _aal_review(db_path, policy, results, latest, 0.2)
    report = _published(client, _refused_body(latest), "AAL")
    assert (report["snapshotId"], report["reviewId"], report["secondaryId"]) == (
        latest,
        review_id,
        None,
    )
    a = report["appendixA"]
    assert (a["secondary"], a["noSecondary"]) == (None, REVIEW_VALUES)
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    assert text.split("### Secondary valuation\n\n", 1)[1].split("\n", 1)[0] == REVIEW_VALUES


def test_a_report_on_a_review_a_refresh_read_again_is_refused_whole(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
) -> None:
    """Spec 2026-11-23 held reviewed value, 5.8, and the whole-branch review of 2026-11-23: a
    report needs a held review that no refresh has read again, whether or not it cites the
    review, since its judgments and its Appendix A rest on that review. Read again, the submit is
    refused whole and nothing is stored; once the review is made again it publishes."""
    sid = _snapshot_id(client, "AAL")
    with closing(connect(db_path)) as conn:
        cited = snapshot_row(conn, sid)
        assert cited is not None
        revalued = replace(results["AAL"], data_date=results["AAL"].data_date + timedelta(days=1))
        latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    record_verdict(db_path, "AAL", latest, "None")
    review_id = _aal_review(db_path, policy, results, latest, 0.2)
    with closing(connect(db_path)) as conn:
        held = held_row(conn, "AAL")
        assert held is not None
        set_held_state(conn, replace(held, read_again_at=NOW))
    refused = _submit(client, _refused_body(latest), "AAL")
    assert (refused.status_code, refused.json()) == (409, {"detail": READ_AGAIN})
    assert client.get("/api/companies/AAL/reports").json()["reports"] == []
    with closing(connect(db_path)) as conn:
        hold_review(conn, "AAL", review_id, NOW)  # made again: the state starts empty
    assert _published(client, _refused_body(latest), "AAL")["reviewId"] == review_id


def test_an_older_secondary_on_a_refused_row_the_review_values_is_the_reports_only_when_cited(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    secondaries: dict[str, int],
) -> None:
    """AAL's secondary valuation was its fallback; a margin override on the same snapshot then
    values it. A report that does not cite the older secondary publishes without naming it,
    Appendix A saying the review values the company; one that cites it publishes, the cite resolves
    and Appendix A names it (method 16.1, as on a valued snapshot)."""
    sid = _snapshot_id(client, "AAL")
    secondary_id = secondaries["AAL"]
    _aal_review(db_path, policy, results, sid, 0.2)
    plain = _published(client, _refused_body(sid), "AAL")
    assert plain["secondaryId"] is None
    a = plain["appendixA"]
    assert (a["secondary"], a["noSecondary"], a["versions"]["secondary"]) == (
        None,
        REVIEW_VALUES,
        None,
    )
    [found] = client.get("/api/companies/AAL/secondary").json()["secondaryValuations"]
    body = _refused_body(sid)
    cite = {"cite": f"${found['valuePerShare']:,.2f}", "ref": f"secondary:{secondary_id}/value"}
    body["sections"][0]["parts"].append(cite)
    citing = _published(client, body, "AAL")
    assert citing["secondaryId"] == secondary_id
    a = citing["appendixA"]
    assert (a["secondary"]["id"], a["noSecondary"]) == (secondary_id, None)


def test_a_refused_row_whose_review_refused_still_needs_a_secondary(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
) -> None:
    """A current review that refused values nothing: revalued, AAL's latest snapshot needs the
    fallback on it, whatever its review (method 16.3)."""
    sid = _snapshot_id(client, "AAL")
    with closing(connect(db_path)) as conn:
        cited = snapshot_row(conn, sid)
        assert cited is not None
        revalued = replace(results["AAL"], data_date=results["AAL"].data_date + timedelta(days=1))
        latest = insert_snapshot(conn, revalued, cited.refresh_id, clock=lambda: NOW)
    record_verdict(db_path, "AAL", latest, "None")
    _aal_review(db_path, policy, results, latest, None)
    r = _submit(client, _refused_body(latest), "AAL")
    detail = f"the report needs a secondary valuation on snapshot {latest}"
    assert (r.status_code, r.json()) == (400, {"detail": detail})


def _aal_review(
    db_path: Path,
    policy: Policy,
    results: dict[str, ValuationResult],
    snapshot_id: int,
    margin: float | None,
) -> int:
    """An applied margin.target override of AAL, whose route refused for its target margin, and
    the review on snapshot ``snapshot_id``: valued at ``margin``, else refused as the row is; the
    review's id."""
    writer = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
    with closing(connect(db_path)) as conn:
        override_id = insert_override(
            conn,
            "AAL",
            "margin.target",
            None,
            0.2 if margin is None else margin,
            "ratio",
            "the peers by hand",
            [{"kind": "filing", "ref": "10-K 2025", "note": ""}],
            "lasting",
            None,
            None,
            snapshot_id,
            writer,
            NOW,
            "applied",
            "",
        )
        refused = results["AAL"]
        if margin is None:
            result = replace(refused, refusal="the reviewed margin is refused")
            review = Review(result, None, (), (override_id,))
        else:
            target = Override(override_id, "margin.target", margin, "agent", writer.actor, NOW, "")
            inputs = replace(young_growth_inputs(), symbol="AAL", peers=())
            review = review_company(inputs, universe_deciles(), policy, TODAY, [target], refused)
            assert review.result.value is not None
        return insert_review(conn, review, "AAL", snapshot_id, None, clock=lambda: NOW)


@pytest.mark.parametrize(
    ("symbol", "changes", "why"),
    [
        ("FRGN", {"currency": "ARS", "refusal": ABOVE_BOUND}, ABOVE_BOUND),
        ("BSIS", {"refusal": BASIS}, BASIS),
        # a snapshot refused as a foreign filer before method 1.1, as one on file may be
        ("OLDF", {"currency": "EUR", "refusal": FOREIGN_FILER}, FOREIGN_FILER),
        ("NOSH", {"shares_diluted": None}, "no diluted share count"),
        # the route's reason in the register's words, without "the route" (spec 2026-11-15 7)
        ("PLAIN", {}, "Fairband's own valuation gives the company a value"),
    ],
)
def test_a_company_that_can_have_no_secondary_publishes_without_one(
    client: TestClient,
    db_path: Path,
    policy: Policy,
    symbol: str,
    changes: dict[str, Any],
    why: str,
) -> None:
    """The secondary route refuses a company the route values (plan 3) and a snapshot refused for a
    reason an agent cannot fix, the currency's, the listed-share basis's or no diluted share count
    (spec 2026-11-10 7.6), so the report needs no secondary valuation there and Appendix A names
    why: the refusal in its own words."""
    inputs = replace(mature_growth_inputs(), symbol=symbol, **changes)
    result = value_company(inputs, universe_deciles(), policy, TODAY)
    with closing(connect(db_path)) as conn:
        refresh = latest_refresh(conn)
        assert refresh is not None
        sid = insert_snapshot(conn, result, refresh.id, clock=lambda: NOW)
    record_verdict(db_path, symbol, sid)
    sections = [{"heading": h, "parts": ["Plain words."]} for h in HEADINGS]
    body = _body(sid, sections=sections)
    report = _published(client, body, symbol)
    assert (report["snapshotId"], report["secondaryId"]) == (sid, None)
    a = report["appendixA"]
    assert (a["secondary"], a["noSecondary"]) == (None, f"No secondary valuation: {why}")
    text = client.get(f"/api/reports/{report['id']}/markdown").text
    block = text.split("### Secondary valuation\n\n", 1)[1].split("\n", 1)[0]
    assert block == f"No secondary valuation: {why}"  # the server's sentence, as the page shows it


def test_appendix_a_says_none_for_a_report_with_no_secondary_that_could_have_one(
    client: TestClient, db_path: Path
) -> None:
    """A report published without a secondary valuation on a company that can have one, a refused
    row (a plan 1 report), names no reason."""
    report = _published(client, _refused_body(_snapshot_id(client, "AAL")), "AAL")
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
    the parts form with no grid. The API reads it with ``grid: null``; a report citing it renders
    its parts, "No grid." in Appendix A, and no grid table in the Markdown."""
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
    sid = _snapshot_id(client)
    cite = {"cite": f"${listed['valuePerShare']:,.2f}", "ref": f"secondary:{secondary_id}/value"}
    report = _published(client, _body(sid, sections=_sections(sid, "full report", cite)))
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
