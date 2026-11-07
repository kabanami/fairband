"""A report's appendixes and its Markdown (spec 2026-11-06 Tier 2, 13.1 and 13.6), on the
``snapshots`` fixture of ``conftest.py``: AAPL's report generated from its records, a review under
an applied belief override and a secondary valuation beside it."""

import re
import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from refresh.synthetic import NOW
from support.engine_companies import mature_growth_inputs, universe_deciles
from support.web import TODAY

from fairband.engine.overrides import Override
from fairband.engine.review import review_company
from fairband.engine.route import value_company
from fairband.engine.secondary import Drivers, Part, secondary_value
from fairband.policy import Policy
from fairband.reports.check import CHECKS, HEADINGS, headings
from fairband.reports.render import GLOSSARY, appendix_a, appendix_b, markdown
from fairband.store.guidance import insert_guidance
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.reports import ReportRow, insert_report, report_row
from fairband.store.reviews import insert_review
from fairband.store.secondary import insert_secondary

METHOD = Path(__file__).parent.parent.parent / "docs" / "method.md"
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "transcript", "ref": "Q3 call", "note": "guidance"}]


def _sections(sid: int, mode: str = "full report") -> list[dict[str, Any]]:
    first = [
        "The price of ",
        {"cite": "$150.00", "ref": f"snapshot:{sid}/price"},
        " is above the value at belief; the belief and the moat decide it.",
    ]
    rest = [{"heading": h, "parts": ["Plain words."]} for h in headings(mode)[1:]]
    return [{"heading": "Summary", "parts": first}, *rest]


def _stored(
    conn: sqlite3.Connection,
    sid: int,
    review_id: int | None = None,
    secondary_id: int | None = None,
    mode: str = "full report",
) -> ReportRow:
    report_id = insert_report(
        conn,
        "AAPL",
        "full report" if mode == "full report" else "valuation review",
        "buy",
        _sections(sid, mode),
        None,
        sid,
        review_id,
        secondary_id,
        None,
        AGENT,
        NOW,
    )
    found = report_row(conn, report_id)
    assert found is not None
    return found


def _review(conn: sqlite3.Connection, policy: Policy, sid: int) -> tuple[int, int]:
    """An applied belief override of 8% and the review under it, on snapshot ``sid``."""
    override_id = insert_override(
        conn,
        "AAPL",
        "growth.belief",
        0.063,
        0.08,
        "ratio",
        "guidance raised",
        EVIDENCE,
        "lasting",
        None,
        None,
        sid,
        AGENT,
        NOW,
        "applied",
        "",
    )
    inputs = replace(mature_growth_inputs(), symbol="AAPL")
    deciles = universe_deciles()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    belief = Override(override_id, "growth.belief", 0.08, "agent", "claude-opus-5-5", NOW, "why")
    review = review_company(inputs, deciles, policy, TODAY, [belief], mechanical)
    return override_id, insert_review(conn, review, "AAPL", sid, None, clock=lambda: NOW)


def _secondary(conn: sqlite3.Connection, policy: Policy, sid: int) -> int:
    part = Part("the business", (100.0, 105.0, 110.25, 115.7625, 121.550625), 0.03, None)
    valuation = secondary_value(
        parts=[part], debt=200.0, cash=100.0, shares=100.0, price=150.0, moat="Wide", policy=policy
    )
    return insert_secondary(
        conn,
        "AAPL",
        sid,
        [part],
        valuation,
        "the services segment",
        EVIDENCE,
        "agent",
        "statements",
        policy.version,
        policy.settings_hash,
        None,
        AGENT,
        NOW,
    )


def _drivers_secondary(conn: sqlite3.Connection, policy: Policy, sid: int) -> int:
    """Spec 20.4's drivers: a trailing revenue of 1,000, the terminal return 12%, debt 200, cash
    100, 50 shares."""
    drivers = Drivers(3, (0.10, 0.08, 0.05), (0.20, 0.20, 0.20), 0.25, 2.0, 0.02)
    valuation = secondary_value(
        drivers=drivers,
        revenue_0=1000.0,
        roic_t=0.12,
        debt=200.0,
        cash=100.0,
        shares=50.0,
        price=150.0,
        moat="Wide",
        policy=policy,
    )
    return insert_secondary(
        conn,
        "AAPL",
        sid,
        (),
        valuation,
        "the cycle turns",
        EVIDENCE,
        "agent",
        "agent",
        policy.version,
        policy.settings_hash,
        None,
        AGENT,
        NOW,
        revenue_0=1000.0,
        roic_t=0.12,
    )


def test_appendix_a_carries_the_drivers_and_the_grid(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    report = _stored(conn, sid, secondary_id=_drivers_secondary(conn, policy, sid))
    a = appendix_a(conn, report, policy)
    secondary = a["secondary"]
    assert (secondary["form"], secondary["parts"]) == ("drivers", [])
    assert round(secondary["valuePerShare"], 4) == 39.8889
    assert secondary["drivers"] == {
        "years": 3,
        "revenueGrowth": [0.10, 0.08, 0.05],
        "operatingMargin": [0.20, 0.20, 0.20],
        "taxRate": 0.25,
        "salesToCapital": 2.0,
        "terminalGrowth": 0.02,
    }
    projection = secondary["projection"]
    assert (projection["trailingRevenue"], projection["terminalReturn"]) == (1000.0, 0.12)
    assert [y["t"] for y in projection["years"]] == [1, 2, 3]
    assert round(projection["years"][2]["pv"], 6) == 121.549402
    assert round(projection["terminalPv"], 6) == 1754.439476
    grid = secondary["grid"]
    assert grid["rowsAre"] == "growths" and len(grid["cells"]) == 3
    assert grid["cells"][1][1] == secondary["valuePerShare"]
    text = markdown(report, a, [])
    block = text[text.index("### Secondary valuation") : text.index("### Checks that ran")]
    assert f"Secondary valuation {secondary['id']}, from drivers: firm value " in block
    assert "| tax rate | 0.25 |" in block and "| revenue growth | 0.1, 0.08, 0.05 |" in block
    assert "| trailing revenue | 1000.0 |" in block and "| terminal return | 0.12 |" in block
    assert "| t | Revenue | EBIT | NOPAT | Reinvestment | FCFF | PV |" in block
    assert f"| 3 | {projection['years'][2]['revenue']!r} | " in block
    terminal_row = f"| terminal | — | — | — | — | {projection['terminalFcff']!r} | "
    assert terminal_row + f"{projection['terminalPv']!r} |" in block
    assert f"Terminal value {projection['terminal']!r} at year 3." in block
    assert "| Terminal growth | r 8.0% | r 9.0% | r 10.0% |" in block
    assert f"| 1.0% | {grid['cells'][0][0]!r} | " in block
    assert "| 3.0% | " in block


def test_appendix_a_labels_a_parts_grid_by_its_shift(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """On the parts form a grid's row moves every part's terminal growth: its header is the
    shift, not a growth no part has."""
    sid = snapshots["AAPL"]
    report = _stored(conn, sid, secondary_id=_secondary(conn, policy, sid))
    a = appendix_a(conn, report, policy)
    secondary = a["secondary"]
    assert (secondary["form"], secondary["drivers"], secondary["projection"]) == (
        "parts",
        None,
        None,
    )
    assert secondary["grid"]["rowsAre"] == "shifts"
    block = markdown(report, a, []).split("### Secondary valuation")[1]
    assert f"Secondary valuation {secondary['id']}, from parts: firm value " in block
    assert "| Every part's terminal growth | r 8.0% | r 9.0% | r 10.0% |" in block
    for shift in ("−1 pp", "0 pp", "+1 pp"):
        assert f"| {shift} | " in block, shift


def test_appendix_a_is_generated_from_the_records(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    override_id, review_id = _review(conn, policy, sid)
    secondary_id = _secondary(conn, policy, sid)
    a = appendix_a(conn, _stored(conn, sid, review_id, secondary_id), policy)
    assert a["snapshot"]["id"] == sid and a["snapshot"]["price"] == 150.0
    inputs = {i["name"]: i for i in a["inputs"]}
    assert inputs["price"]["tag"] == "DATA" and inputs["price"]["source"] == "FMP quote"
    judged = inputs["growth.belief"]  # the review's JUDGMENT entry, beside the snapshot's own
    assert (judged["tag"], judged["value"]) == ("JUDGMENT", 0.08)
    assert judged["source"] == f"override {override_id}, agent claude-opus-5-5"
    assert [(o["id"], o["tag"], o["reason"], o["evidence"]) for o in a["overrides"]] == [
        (override_id, "growth.belief", "guidance raised", EVIDENCE)
    ]
    bridge = a["bridge"]
    assert bridge["reviewId"] == review_id and len(bridge["lines"]) == 1
    assert bridge["lines"][0]["tag"] == "growth.belief"
    assert bridge["lines"][0]["delta"] == bridge["reviewedValue"] - bridge["mechanicalValue"]
    secondary = a["secondary"]
    assert secondary["id"] == secondary_id and len(secondary["parts"][0]["years"]) == 5
    assert round(secondary["valuePerShare"], 4) == 16.8242
    assert [c["check"] for c in a["checks"]] == list(CHECKS)
    stance = next(c for c in a["checks"] if c["check"] == "the stance word")
    assert stance["rule"] == "one of buy, hold, trim, avoid"
    assert a["versions"] == {
        "method": "fairband-mechanical/0.9",
        "policy": policy.version,
        "settingsHash": policy.settings_hash,
        "review": "fairband-review/1",
        "secondary": "fairband-secondary/2",
    }
    assert a["classifier"]["phase"] == "Mature Growth" and a["classifier"]["checks"] == []


def _guided(conn: sqlite3.Connection, symbol: str, low: float, high: float, call: date) -> int:
    said = "We guide fiscal 2027 EPS."
    return insert_guidance(
        conn,
        symbol,
        "eps",
        "2027",
        low,
        high,
        "gaap",
        call,
        said,
        "response:3/0/content",
        AGENT,
        NOW,
        None,
    )


def test_appendix_a_lists_the_guidance_on_file(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The company's guidance records on file when the report was published, newest first, each
    current or superseded, with the overrides inside the review that cite it."""
    sid = snapshots["AAPL"]
    old = _guided(conn, "AAPL", 6.0, 6.5, date(2026, 7, 28))
    new = _guided(conn, "AAPL", 6.25, 6.75, date(2026, 10, 28))
    _guided(conn, "AAL", 1.0, 1.5, date(2026, 10, 28))
    cites = [{"kind": "guidance", "ref": f"guidance:{new}", "note": "FY2027 EPS"}]
    override_id = insert_override(
        conn,
        "AAPL",
        "earnings.ntm",
        5.9,
        6.5,
        "USD a share",
        "guided",
        cites,
        "lasting",
        None,
        None,
        sid,
        AGENT,
        NOW,
        "applied",
        "",
    )
    inputs = replace(mature_growth_inputs(), symbol="AAPL")
    deciles = universe_deciles()
    mechanical = value_company(inputs, deciles, policy, TODAY)
    ntm = Override(override_id, "earnings.ntm", 6.5, "agent", "claude-opus-5-5", NOW, "guided")
    review = review_company(inputs, deciles, policy, TODAY, [ntm], mechanical)
    review_id = insert_review(conn, review, "AAPL", sid, None, clock=lambda: NOW)
    report = _stored(conn, sid, review_id)
    later = insert_guidance(
        conn,
        "AAPL",
        "eps",
        "2027",
        6.4,
        6.6,
        "gaap",
        date(2026, 11, 2),
        "Raised.",
        "response:4/0/content",
        AGENT,
        NOW + timedelta(days=1),
        None,
    )
    a = appendix_a(conn, report, policy)
    assert a["guidance"] == [
        {
            "id": new,
            "metric": "eps",
            "period": "2027",
            "low": 6.25,
            "high": 6.75,
            "midpoint": 6.5,
            "basis": "gaap",
            "asOf": "2026-10-28",
            "state": "current",  # as of the report: the later record came after it
            "citedBy": [override_id],
        },
        {
            "id": old,
            "metric": "eps",
            "period": "2027",
            "low": 6.0,
            "high": 6.5,
            "midpoint": 6.25,
            "basis": "gaap",
            "asOf": "2026-07-28",
            "state": "superseded",
            "citedBy": [],
        },
    ]
    assert later not in [g["id"] for g in a["guidance"]]
    text = markdown(report, a, [])
    block = text[text.index("### Guidance on file") : text.index("### Bridge")]
    header = (
        "| Guidance | Metric | Period | Low | High | Midpoint | Basis | Call | State | Cited by |"
    )
    assert header in block
    assert f"| {new} | eps | 2027 | 6.25 | 6.75 | 6.5 | gaap | 2026-10-28 | current |" in block
    assert f"| current | {override_id} |" in block and "| superseded | — |" in block


def test_appendix_a_without_a_review_or_a_secondary(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    a = appendix_a(conn, _stored(conn, snapshots["AAPL"]), policy)
    assert a["overrides"] == [] and a["bridge"] is None and a["secondary"] is None
    assert a["guidance"] == []
    assert "### Guidance on file\n\nNone." in markdown(_stored(conn, snapshots["AAPL"]), a, [])
    assert {i["tag"] for i in a["inputs"]} == {"DATA", "RULE"}
    assert a["versions"]["review"] is None and a["versions"]["secondary"] is None


def test_appendix_b_lists_only_the_terms_used() -> None:
    sections = [
        {
            "heading": "Summary",
            "parts": [
                "The belief sets the runway; snapshots follow the growth word. ",
                {"cite": "$150.00", "ref": "snapshot:1/price"},
                " EPV is low.",
            ],
        },
        {"heading": "Key judgments", "parts": ["Nothing on the fade here: fades aside."]},
    ]
    terms = [entry["term"] for entry in appendix_b(sections)]
    assert terms == [
        "Belief",
        "Runway N",
        "Fade",
        "EPV",
        "Growth word, margin direction",
        "Snapshot",
    ]
    assert appendix_b([{"heading": "Key judgments", "parts": ["Plain words."]}]) == []
    assert appendix_b(sections)[0] == {"term": "Belief", "meaning": GLOSSARY["Belief"]}


def test_the_glossary_matches_the_method_document() -> None:
    text = METHOD.read_text(encoding="utf-8")
    start = text.index("\n## 13. ")
    section = text[start : text.index("\n## ", start + 1)]
    rows = re.findall(r"^\| (.+?) \| (.+?) \|$", section, re.MULTILINE)
    table = {term: meaning for term, meaning in rows if term not in ("Term", "---")}
    assert len(table) >= 40 and set(table) == set(GLOSSARY)
    for term, meaning in table.items():
        assert GLOSSARY[term].startswith(meaning), term
    assert "an agent writes" in GLOSSARY["Note"]  # the brand book's note beside the flag


def test_the_markdown(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    sid = snapshots["AAPL"]
    override_id, review_id = _review(conn, policy, sid)
    report = _stored(conn, sid, review_id, _secondary(conn, policy, sid))
    text = markdown(report, appendix_a(conn, report, policy), appendix_b(report.sections))
    lines = text.splitlines()
    assert lines[0] == "AAPL · full report · 2026-11-01 · claude-opus-5-5 · revision 1"
    assert lines[2] == f"Stance: buy. On snapshot {sid}, priced 2026-10-30, valid until 2027-01-28."
    assert [line[3:] for line in lines if line.startswith("## ")] == [
        *HEADINGS,
        "Appendix A",
        "Appendix B",
    ]
    assert "The price of $150.00 is above the value at belief;" in text  # the cite as its text
    assert "| Input | Value | Unit | Tag | Kind | Source | As of | Note |" in text
    assert f"| {override_id} | growth.belief | 0.063 | 0.08 | guidance raised |" in text
    assert "| the business | 1 | 100.0 | " in text
    assert "| wrong snapshot | every cite rests on" in text
    assert "- **Belief**: " + GLOSSARY["Belief"] in text
    assert text.endswith("\n")


def test_a_review_mode_names_the_full_report_it_reuses_or_that_there_is_none(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    sid = snapshots["AAPL"]
    report = _stored(conn, sid, mode="valuation review")
    text = markdown(report, appendix_a(conn, report, policy), [])
    assert text.splitlines()[0].startswith("AAPL · valuation review · ")
    assert "No full report to reuse." in text and "## The business" not in text
    assert text.rstrip().endswith("No terms used.")
    reusing = replace(report, reuses_full_report_of=3)
    assert "Reuses full report 3." in markdown(reusing, appendix_a(conn, reusing, policy), [])
