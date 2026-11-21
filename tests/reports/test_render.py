"""A report's appendixes, its references and its Markdown (spec 2026-11-06 Tier 2, 13.1 and 13.6),
on the ``snapshots`` fixture of ``conftest.py``: AAPL's report generated from its records, a review
under an applied belief override and a secondary valuation beside it."""

import re
import sqlite3
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from refresh.synthetic import NOW
from support.engine_companies import (
    ABOVE_BOUND,
    ars_refused_inputs,
    fx_inputs,
    mature_growth_inputs,
    universe_deciles,
)
from support.payloads import store_payloads
from support.pe_history import closes_payload, store_pe_history, unit_quarters
from support.splits import (
    AFTER,
    BEFORE,
    SPLIT_DAY,
    follow_mgco,
    made_on_mgco,
    mgco_on,
    store_splits,
    under,
)
from support.web import TODAY

from fairband.engine.flags import QUALITY_WARNINGS
from fairband.engine.overrides import Override
from fairband.engine.review import Review, review_company
from fairband.engine.route import value_company
from fairband.engine.secondary import Drivers, Part, secondary_value
from fairband.policy import Policy
from fairband.reports.charts import chart_tables
from fairband.reports.check import CHECKS, HEADINGS, headings
from fairband.reports.render import (
    GLOSSARY,
    appendix_a,
    appendix_b,
    markdown,
    references,
    resting_words,
)
from fairband.store.currency import reporting_currency
from fairband.store.db import transaction
from fairband.store.guidance import insert_guidance
from fairband.store.ledger import Writer
from fairband.store.overrides import insert_override
from fairband.store.reports import ReportRow, insert_report, report_row
from fairband.store.reviews import insert_review
from fairband.store.secondary import insert_secondary
from fairband.store.snapshots import insert_snapshot, snapshot_row

METHOD = Path(__file__).parent.parent.parent / "docs" / "method.md"
AGENT = Writer("agent", "claude-opus-5-5", "claude-code/2.1")
EVIDENCE = [{"kind": "transcript", "ref": "Q3 call", "note": "guidance"}]
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Appendix A's sentences where the company can have no secondary valuation (spec 2026-11-15 7).
ROUTE_VALUES = "No secondary valuation: Fairband's own valuation gives the company a value"


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
    sections: list[dict[str, Any]] | None = None,
    symbol: str = "AAPL",
) -> ReportRow:
    """``symbol``'s report on snapshot ``sid``, of ``sections`` or ``_sections``' plain ones."""
    report_id = insert_report(
        conn,
        symbol,
        "full report" if mode == "full report" else "valuation review",
        "buy",
        _sections(sid, mode) if sections is None else sections,
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
    # the rows in words as the export's grid writes them, which the Research tab reads (18.4)
    assert grid["rowWords"] == ["1.0%", "2.0%", "3.0%"]
    text = markdown(report, a, [], [], {})
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
    assert secondary["grid"]["rowWords"] == ["−1 pp", "0 pp", "+0 pp, capped at g_T"]
    block = markdown(report, a, [], [], {}).split("### Secondary valuation")[1]
    assert f"Secondary valuation {secondary['id']}, from parts: firm value " in block
    assert "| Every part's terminal growth | r 8.0% | r 9.0% | r 10.0% |" in block
    for shift in ("−1 pp", "0 pp", "+0 pp, capped at g_T"):  # the part is at g_T
        assert f"| {shift} | " in block, shift


def test_appendix_a_names_the_currency_of_a_row_refused_for_it(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Fix round 1 of task 6: a report on ARSX, refused for ARS's expected inflation, names ARS
    as the currency of its figures, never USD; it has no secondary valuation, a refusal no agent
    can fix, so no rate row either, and Appendix A names the refusal."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    refused = value_company(ars_refused_inputs(), universe_deciles(), policy, TODAY)
    sid = insert_snapshot(conn, refused, aapl.refresh_id, clock=lambda: NOW)
    report = _stored(conn, sid, symbol="ARSX")
    a = appendix_a(conn, report, policy)
    assert a["snapshot"]["currency"] == "ARS"
    assert a["secondary"] is None
    assert a["noSecondary"] == "No secondary valuation: " + ABOVE_BOUND


def test_appendix_a_names_the_currency_and_the_rate_of_a_secondary_valuation(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-10 7.6: a secondary valuation of a company in another currency runs in it, its
    totals in the currency and its value a share in USD, and the record carries the rate; Appendix
    A names the currency and the rate where it states the valuation, the page's and the export's
    alike. FXCO is in SEK at 8.0 a dollar; AAPL's, in USD, reads as before."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    fx = value_company(fx_inputs(), universe_deciles(), policy, TODAY)
    sid = insert_snapshot(conn, fx, aapl.refresh_id, clock=lambda: NOW)
    part = Part("the business", (800.0, 840.0, 882.0), 0.03, None)
    valuation = secondary_value(
        parts=[part], debt=0.0, cash=0.0, shares=100.0, price=400.0, moat="Wide", policy=policy
    )
    secondary_id = insert_secondary(
        conn,
        "FXCO",
        sid,
        [part],
        valuation,
        "the business in SEK",
        EVIDENCE,
        "none",
        "none",
        policy.version,
        policy.settings_hash,
        None,
        AGENT,
        NOW,
        fx_rate=8.0,
    )
    report = _stored(conn, sid, secondary_id=secondary_id, symbol="FXCO")
    a = appendix_a(conn, report, policy)
    assert a["snapshot"]["currency"] == "SEK"  # the guidance's and the records' money figures
    assert (a["secondary"]["currency"], a["secondary"]["fxRate"]) == ("SEK", 8.0)
    block = markdown(report, a, [], [], {}).split("### Secondary valuation")[1]
    lead = f"Secondary valuation {secondary_id}, from parts, in SEK at 8.0 SEK per USD, its value"
    assert f"{lead} a share in USD: firm value " in block
    usd = _stored(conn, snapshots["AAPL"], secondary_id=_secondary(conn, policy, snapshots["AAPL"]))
    plain = appendix_a(conn, usd, policy)
    assert plain["snapshot"]["currency"] == "USD"
    assert (plain["secondary"]["currency"], plain["secondary"]["fxRate"]) == ("USD", 1.0)


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
        "method": "fairband-mechanical/1.7",
        "policy": policy.version,
        "settingsHash": policy.settings_hash,
        "review": "fairband-review/1",
        "secondary": "fairband-secondary/2",
    }
    assert a["classifier"]["phase"] == "Mature Growth" and a["classifier"]["checks"] == []


def test_appendix_a_gives_each_input_its_provenance(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 13.1, "every input with its tag, source and dates": each input carries its source and
    its three dates, the day the figure is as of, when it was observed and when it was entered,
    which the Research tab draws with each of Appendix A's inputs (18.4)."""
    sid = snapshots["AAPL"]
    a = appendix_a(conn, _stored(conn, sid), policy)
    snapshot = snapshot_row(conn, sid)
    assert snapshot is not None
    for entry, i in zip(a["inputs"], snapshot.result.inputs, strict=True):
        p = i.provenance
        assert entry["name"] == i.name and entry["source"] == p.source
        assert entry["asOf"] == (None if p.as_of is None else p.as_of.isoformat())
        assert entry["observedAt"] == (None if p.observed_at is None else p.observed_at.isoformat())
        assert entry["enteredAt"] == (None if p.entered_at is None else p.entered_at.isoformat())
    assert any(e["observedAt"] is not None for e in a["inputs"])


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
            "currency": "USD",  # a US company's: none stored is the snapshot's reporting currency
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
            "currency": "USD",
            "basis": "gaap",
            "asOf": "2026-07-28",
            "state": "superseded",
            "citedBy": [],
        },
    ]
    assert later not in [g["id"] for g in a["guidance"]]
    text = markdown(report, a, [], [], {})
    block = text[text.index("### Guidance on file") : text.index("### Bridge")]
    header = (
        "| Guidance | Metric | Period | Low | High | Midpoint | Currency | Basis | Call | State"
        " | Cited by |"
    )
    assert header in block
    # the call's date in words, as the references write a day (spec 2026-11-15 7)
    assert f"| {new} | eps | 2027 | 6.25 | 6.75 | 6.5 | USD | gaap | 28 Oct 2026 | current |" in (
        block
    )
    assert (
        f"| {old} | eps | 2027 | 6.0 | 6.5 | 6.25 | USD | gaap | 28 Jul 2026 | superseded |"
        in block
    )
    assert ISO_DATE.search(block) is None
    assert f"| current | {override_id} |" in block and "| superseded | — |" in block


def test_appendix_a_gives_each_guidance_record_its_currency(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-15 9.1 and 9.5: on FXCO, whose report rests on a snapshot in SEK, a guidance
    record with no stored currency is in SEK, one recorded in USD in USD, and a percent metric's
    has none; the export's table keeps its bare numbers and names each in a Currency column after
    the midpoint, empty for the percent. The SEK is the report's own snapshot's, so a newer
    snapshot in another currency changes nothing in the report."""
    aapl = snapshot_row(conn, snapshots["AAPL"])
    assert aapl is not None
    fx = value_company(fx_inputs(), universe_deciles(), policy, TODAY)
    sid = insert_snapshot(conn, fx, aapl.refresh_id, clock=lambda: NOW)

    def guided(metric: str, low: float, high: float, currency: str | None) -> int:
        said = f"We guide fiscal 2027 {metric}."
        return insert_guidance(
            conn,
            "FXCO",
            metric,
            "2027",
            low,
            high,
            "gaap",
            date(2026, 10, 28),
            said,
            "response:3/0/content",
            AGENT,
            NOW,
            None,
            currency=currency,
        )

    eps = guided("eps", 40.0, 44.0, None)
    revenue = guided("revenue", 2.0e9, 2.2e9, "USD")
    margin = guided("operating_margin", 0.30, 0.32, None)
    report = _stored(conn, sid, symbol="FXCO")
    usd = replace(mature_growth_inputs(), symbol="FXCO")  # a newer snapshot, in USD
    insert_snapshot(conn, value_company(usd, universe_deciles(), policy, TODAY), aapl.refresh_id)
    assert reporting_currency(conn, "FXCO") == "USD"  # the latest snapshot's, not the report's
    a = appendix_a(conn, report, policy)
    assert a["snapshot"]["currency"] == "SEK"
    by_id = {g["id"]: g["currency"] for g in a["guidance"]}
    assert by_id == {eps: "SEK", revenue: "USD", margin: None}
    text = markdown(report, a, [], [], {})
    block = text[text.index("### Guidance on file") : text.index("### Bridge")]
    assert (
        "| Guidance | Metric | Period | Low | High | Midpoint | Currency | Basis | Call | State"
        " | Cited by |"
    ) in block
    # the numbers stay bare, as before; the code is in its own cell, empty for a percent
    assert f"| {eps} | eps | 2027 | 40.0 | 44.0 | 42.0 | SEK | gaap | 28 Oct 2026 |" in block
    assert (
        f"| {revenue} | revenue | 2027 | 2000000000.0 | 2200000000.0 | 2100000000.0 | USD | gaap |"
    ) in block
    assert f"| {margin} | operating_margin | 2027 | 0.3 | 0.32 | 0.31 |  | gaap |" in block


def test_appendix_a_without_a_review_or_a_secondary(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """AAPL's snapshot is valued, so a report with no secondary valuation says Fairband's own
    valuation gives the company a value, in the register's words, without "the route" (method
    16.6, plan 3, spec 2026-11-15 7); AAL's is refused and could have one, so its report names no
    reason."""
    a = appendix_a(conn, _stored(conn, snapshots["AAPL"]), policy)
    assert a["overrides"] == [] and a["bridge"] is None and a["secondary"] is None
    assert a["noSecondary"] == ROUTE_VALUES
    assert a["guidance"] == []
    text = markdown(_stored(conn, snapshots["AAPL"]), a, [], [], {})
    assert "### Guidance on file\n\nNone." in text
    assert f"### Secondary valuation\n\n{ROUTE_VALUES}\n" in text
    assert "the route" not in text.split("### Secondary valuation\n\n", 1)[1].split("\n", 1)[0]
    assert {i["tag"] for i in a["inputs"]} == {"DATA", "RULE"}
    assert a["versions"]["review"] is None and a["versions"]["secondary"] is None
    refused = _stored(conn, snapshots["AAL"], symbol="AAL")
    a = appendix_a(conn, refused, policy)
    assert (a["secondary"], a["noSecondary"]) == (None, None)
    assert "### Secondary valuation\n\nNone.\n" in markdown(refused, a, [], [], {})
    rule = next(c["rule"] for c in a["checks"] if c["check"] == CHECKS[4])
    assert rule == (
        "on a refused latest snapshot, the company's newest secondary valuation rests on it or on"
        " one it reprices; none where the route or the review values the company, or where the"
        " snapshot's refusal is one an agent cannot fix: no diluted share count, the reporting"
        " currency's or the share basis's"
    )


def test_appendix_a_names_a_refusal_an_agent_cannot_fix(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """A report with no secondary valuation on a snapshot refused for a reason an agent cannot
    fix: Appendix A's reason is the refusal in its own words (spec 2026-11-10 7.6), on the page and
    in the export."""
    basis = (
        "share basis unclear: the newest period's count 1,680.7 m against the quote's 210.1 m (the"
        " ADR ratio 10)"
    )
    aal = snapshot_row(conn, snapshots["AAL"])
    assert aal is not None
    sid = insert_snapshot(
        conn, replace(aal.result, refusal=basis), aal.refresh_id, clock=lambda: NOW
    )
    report = _stored(conn, sid, symbol="AAL")
    a = appendix_a(conn, report, policy)
    assert (a["secondary"], a["noSecondary"]) == (None, f"No secondary valuation: {basis}")
    text = markdown(report, a, [], [], {})
    assert f"### Secondary valuation\n\nNo secondary valuation: {basis}\n" in text


def test_the_bridge_without_a_review_names_the_value_that_stands(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Without a review the mechanical value is the value, unless the snapshot refused and has
    none: then the export says only that there is no review, as the Research tab does."""
    for symbol, line in (
        ("AAPL", "No review: the value is the mechanical one."),
        ("AAL", "No review."),
    ):
        report = _stored(conn, snapshots[symbol], symbol=symbol)
        a = appendix_a(conn, report, policy)
        assert a["bridge"] is None and (a["snapshot"]["value"] is None) == (symbol == "AAL")
        text = markdown(report, a, [], [], {})
        assert text.split("### Bridge\n\n", 1)[1].split("\n", 1)[0] == line, symbol


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


def test_the_glossary_takes_the_minority_interest_off() -> None:
    """Spec 2026-11-13 13: the four terms whose formulas take the minority interest name it, as
    method 13 does; the test above holds them to the method's words."""
    assert GLOSSARY["Distress-sale value"].startswith(
        "What equity gets in a distress sale: 60% of the firm value plus cash, less debt and the "
        "minority interest, not below zero, a share"
    )
    assert GLOSSARY["NCAV"].startswith(
        "Graham's net current asset value: total current assets less total liabilities; less the "
        "minority interest and over the count in force, the diluted shares plus any committed "
        "shares, the run-off's floor when above zero"
    )
    assert "market cap plus debt and the minority interest, less cash" in GLOSSARY["Requirement"]
    assert GLOSSARY["Cash floor"].startswith(
        "A Start-up row's net cash a share, (cash − debt − minority interest) ÷ the count in "
        "force, the diluted shares plus any committed shares"
    )


def test_the_glossary_counts_the_engine_s_quality_warnings() -> None:
    """Spec 2026-11-13 8: ``share-count-gap`` is the twelfth quality warning, and the glossary's
    count is the engine's."""
    assert len(QUALITY_WARNINGS) == 12 and "share-count-gap" in QUALITY_WARNINGS
    assert GLOSSARY["Quality warning"].startswith("One of the twelve flags that say the value")


def test_the_markdown(conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]) -> None:
    sid = snapshots["AAPL"]
    override_id, review_id = _review(conn, policy, sid)
    report = _stored(conn, sid, review_id, _secondary(conn, policy, sid))
    a, b = appendix_a(conn, report, policy), appendix_b(report.sections)
    refs = references(conn, report, policy)
    text = markdown(report, a, b, refs, chart_tables(conn, report, policy))
    lines = text.splitlines()
    # the lines above the sections name no part of Fairband and write each date in words, as the
    # references do (spec 2026-11-15 7); the actor and the revision stay
    assert lines[0] == "AAPL · full report · 1 Nov 2026 · claude-opus-5-5 · revision 1"
    assert lines[2] == (
        "Stance: buy. On the data of 30 Oct 2026, priced that day, valid until 28 Jan 2027."
    )
    assert lines[2].startswith("Stance: ")
    assert "snapshot" not in lines[2].lower() and ISO_DATE.search(lines[2]) is None
    assert ISO_DATE.search(lines[0]) is None
    # Appendix A's inputs, each as of a day in words, and the next earnings date, a date input's
    # note, in words too
    inputs = text[text.index("### Inputs") : text.index("### Overrides")]
    assert "| price | 150.0 | USD | DATA | observed | FMP quote | 30 Oct 2026 | — |" in inputs
    assert "| next_earnings | — | date | DATA | " in inputs and " | 28 Jan 2027 |" in inputs
    assert ISO_DATE.search(inputs) is None
    # the references last, where GitHub-flavoured Markdown renders footnote definitions (B-108)
    assert [line[3:] for line in lines if line.startswith("## ")] == [
        *HEADINGS,
        "Appendix A",
        "Appendix B",
        "References",
    ]
    listed = lines.index("## References")
    footnotes = [n for n, line in enumerate(lines) if line.startswith("[^")]
    assert footnotes and all(n > listed for n in footnotes)
    # the cite as its text and its footnote mark
    assert "The price of $150.00[^1] is above the value at belief;" in text
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
    text = markdown(report, appendix_a(conn, report, policy), [], [], {})
    assert text.splitlines()[0].startswith("AAPL · valuation review · ")
    assert "No full report to reuse." in text and "## The business" not in text
    assert "## Appendix B\n\nNo terms used.\n\n## References\n\nNo references.\n" in text
    reusing = replace(report, reuses_full_report_of=3)
    a = appendix_a(conn, reusing, policy)
    text = markdown(reusing, a, [], [], {}, reused=date(2026, 11, 3))
    # the full report by its date, not its id (spec 2026-11-15 7)
    assert text.splitlines()[3] == "Reuses the full report of 3 Nov 2026."
    assert "Reuses full report" not in text
    # where the reused report's record is not on file the report still renders, naming no day
    text = markdown(reusing, a, [], [], {})
    assert text.splitlines()[3] == "Reuses an earlier full report."


@pytest.mark.parametrize(
    ("data", "price", "valid", "words"),
    [
        (
            date(2026, 11, 4),
            date(2026, 11, 4),
            date(2027, 1, 27),
            "On the data of 4 Nov 2026, priced that day, valid until 27 Jan 2027.",
        ),
        (
            date(2026, 11, 4),
            date(2026, 11, 3),
            date(2027, 1, 27),
            "On the data of 4 Nov 2026, priced 3 Nov 2026, valid until 27 Jan 2027.",
        ),
        (
            date(2026, 11, 4),
            None,
            date(2027, 1, 27),
            "On the data of 4 Nov 2026, valid until 27 Jan 2027.",
        ),
        (
            date(2026, 11, 4),
            date(2026, 11, 4),
            None,
            "On the data of 4 Nov 2026, priced that day.",
        ),
    ],
)
def test_the_export_says_what_the_report_rests_on_in_the_reader_s_words(
    data: date, price: date | None, valid: date | None, words: str
) -> None:
    assert resting_words(data, price, valid) == words


def test_the_export_s_second_line_follows_the_snapshot_s_dates(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The second line reads the snapshot's dates from Appendix A: a snapshot priced on another day
    than its data's names the price's day, and one with no price date says nothing of a price."""
    report = _stored(conn, snapshots["AAPL"])
    a = appendix_a(conn, report, policy)
    other = {**a, "snapshot": {**a["snapshot"], "priceDate": "2026-10-29"}}
    assert markdown(report, other, [], [], {}).splitlines()[2] == (
        "Stance: buy. On the data of 30 Oct 2026, priced 29 Oct 2026, valid until 28 Jan 2027."
    )
    unpriced = {**a, "snapshot": {**a["snapshot"], "priceDate": None}}
    assert markdown(report, unpriced, [], [], {}).splitlines()[2] == (
        "Stance: buy. On the data of 30 Oct 2026, valid until 28 Jan 2027."
    )


def _snapshot_part(text: str) -> str:
    """The export's Appendix A from its first part to its Inputs part."""
    appendix = text.split("\n## Appendix A\n\n", 1)[1]
    return appendix[: appendix.index("### Inputs")]


def test_the_export_s_appendix_a_opens_with_the_snapshot(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The whole-branch review's I1: the export's second line names no record (spec 2026-11-15 7),
    so its Appendix A opens with the Snapshot part, one line in the order of the Research tab's
    Appendix A: the snapshot's id, its data date, its price date and the end of its window in
    words, its price and its value a share, both US dollars, as the export writes a figure a share
    elsewhere, with its thousands separator ("$1,507.85", where the page's line writes
    "$1507.85"), and the reporting currency on a company in another currency; a refused
    snapshot's refusal after the line, as the page shows it under the line (method 16.6)."""
    sid = snapshots["AAPL"]
    aapl = snapshot_row(conn, sid)
    assert aapl is not None and aapl.value is not None
    report = _stored(conn, sid)
    a = appendix_a(conn, report, policy)
    text = markdown(report, a, [], [], {})
    line = (
        f"Snapshot {sid} · data 30 Oct 2026 · priced 30 Oct 2026 · valid until 28 Jan 2027"
        f" · price $150.00 · value ${aapl.value:.2f}"
    )
    assert _snapshot_part(text) == f"### Snapshot\n\n{line}\n\n"
    # a figure of four digits takes the separator; a figure below zero its minus first
    large = {**a, "snapshot": {**a["snapshot"], "price": 1507.85, "value": -1234.5}}
    part = _snapshot_part(markdown(report, large, [], [], {}))
    assert part.endswith(" · price $1,507.85 · value −$1,234.50\n\n")
    # a refused snapshot: no value, and its refusal after the line
    aal = snapshot_row(conn, snapshots["AAL"])
    assert aal is not None and aal.value is None and aal.refusal
    refused = _stored(conn, aal.id, symbol="AAL")
    text = markdown(refused, appendix_a(conn, refused, policy), [], [], {})
    part = _snapshot_part(text)
    assert part.startswith(f"### Snapshot\n\nSnapshot {aal.id} · data ")
    assert part.endswith(f" · value —\n\n{aal.refusal}\n\n")
    # a company in another currency names it last; the price and the value are US dollars
    fx = value_company(fx_inputs(), universe_deciles(), policy, TODAY)
    fxid = insert_snapshot(conn, fx, aapl.refresh_id, clock=lambda: NOW)
    sek = _stored(conn, fxid, symbol="FXCO")
    part = _snapshot_part(markdown(sek, appendix_a(conn, sek, policy), [], [], {}))
    assert part.startswith(f"### Snapshot\n\nSnapshot {fxid} · data ")
    assert " · price $50.00 · value $" in part and part.endswith(" · in SEK\n\n")
    assert ISO_DATE.search(part) is None


def test_the_export_writes_no_data_under_a_chart_table_without_rows(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The whole-branch review's M8: under a chart table with no rows the export writes "No data
    on file.", as the page does under a chart with no point; Appendix A's empty parts, which are
    no chart's table, keep "None."."""
    sid = snapshots["AAPL"]
    with transaction(conn):
        conn.execute(
            "DELETE FROM facts WHERE symbol = 'AAPL'"
            " AND dataset IN ('income-quarter', 'cashflow-quarter', 'balance-quarter')"
        )
    report = _stored(conn, sid)
    a = appendix_a(conn, report, policy)
    text = markdown(report, a, [], [], chart_tables(conn, report, policy))
    assert _part(text, HEADINGS[4]) == "\n### By quarter\n\nNo data on file.\n\nPlain words.\n"
    assert "### Guidance on file\n\nNone." in text
    refused = _stored(conn, snapshots["AAL"], symbol="AAL")
    text = markdown(
        refused, appendix_a(conn, refused, policy), [], [], chart_tables(conn, refused, policy)
    )
    financial = _part(text, HEADINGS[3])
    assert financial.count("\n\nNo data on file.\n") == 6 and "None." not in financial


def test_a_review_mode_leads_its_earnings_call_with_the_quarters(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Spec 2026-11-15 6.5: a valuation review has the last earnings call too, its third section,
    and it gains the quarters' table before its text, as a full report's section 5 does."""
    report = _stored(conn, snapshots["AAPL"], mode="valuation review")
    tables = chart_tables(conn, report, policy)
    text = markdown(report, appendix_a(conn, report, policy), [], [], tables)
    call = _part(text, HEADINGS[4])
    assert call.startswith("\n### By quarter\n\n| Period | Q3 2025 | Q4 2025 | Q1 2026 | Q2 2026 |")
    assert "| Revenue | $300,000,000 | " in call and "| Operating margin | " in call
    assert call.rstrip().endswith("|\n\nPlain words.")


def _cited(sid: int) -> list[dict[str, Any]]:
    """A full report citing three refs five times: the price twice, the fiscal 2025 revenue twice,
    once with its period, and r once."""
    price = {"cite": "$150.00", "ref": f"snapshot:{sid}/price"}
    revenue = "fact:AAPL/revenue/2025"
    sections = _sections(sid)
    sections[0] = {
        "heading": HEADINGS[0],
        "parts": [
            "The price of ",
            price,
            " against revenue of ",
            {"cite": "$2,100,000,000", "ref": revenue, "period": "FY2025"},
            ".",
        ],
    }
    sections[3] = {
        "heading": HEADINGS[3],
        "parts": [
            "Revenue of ",
            {"cite": "$2.1 billion", "ref": revenue},
            " clears the hurdle of ",
            {"cite": "9.0%", "ref": "policy:required_return"},
            " at the price of ",
            price,
            ".",
        ],
    }
    return sections


def test_the_references_list(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Three distinct refs cited five times: three entries, numbered in the order each is first
    cited across the sections, each with its source in words."""
    sid = snapshots["AAPL"]
    report = _stored(conn, sid, sections=_cited(sid))
    assert references(conn, report, policy) == [
        {
            "n": 1,
            "ref": f"snapshot:{sid}/price",
            "source": f"snapshot {sid}, the price, priced 30 Oct 2026",
        },
        {
            "n": 2,
            "ref": "fact:AAPL/revenue/2025",
            "source": "the revenue line of fiscal 2025 on file",
        },
        {
            "n": 3,
            "ref": "policy:required_return",
            "source": f"policy required_return, {policy.version}",
        },
    ]
    plain = [{"heading": HEADINGS[0], "parts": ["Plain words."]}]
    assert references(conn, _stored(conn, sid, sections=plain), policy) == []
    # a policy: ref names the version the report's snapshot was valued under, not the newest
    later = replace(policy, version="fairband-policy-v99")
    *_, cited = references(conn, report, later)
    assert cited["source"] == f"policy required_return, {policy.version}"


def test_the_references_one_section_cites(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """The company detail's report summary (spec 2026-11-06 Tier 2, 18.2): the refs section 1
    cites, each with the number the whole list gives it, so a number there matches the report
    page; r, cited in section 4 alone, is left out. A section past the last cites nothing."""
    sid = snapshots["AAPL"]
    report = _stored(conn, sid, sections=_cited(sid))
    whole = references(conn, report, policy)
    assert references(conn, report, policy, section=1) == whole[:2]
    assert [r["n"] for r in references(conn, report, policy, section=4)] == [1, 2, 3]
    assert references(conn, report, policy, section=99) == []


def test_one_number_per_distinct_ref(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """One ref cited with its period and without, and once with space around it: one entry, and
    the one footnote number on every cite of it."""
    sid = snapshots["AAPL"]
    revenue = "fact:AAPL/revenue/2025"
    sections = _sections(sid)
    sections[3] = {
        "heading": HEADINGS[3],
        "parts": [
            "Revenue was ",
            {"cite": "$2,100,000,000", "ref": revenue, "period": "FY2025"},
            ", or ",
            {"cite": "$2.1 billion", "ref": revenue},
            ", or ",
            {"cite": "$2,100,000,000", "ref": f" {revenue} ", "period": "2025"},
            ".",
        ],
    }
    report = _stored(conn, sid, sections=sections)
    refs = references(conn, report, policy)
    assert [(r["n"], r["ref"]) for r in refs] == [(1, f"snapshot:{sid}/price"), (2, revenue)]
    text = markdown(report, appendix_a(conn, report, policy), [], refs, {})
    assert "Revenue was $2,100,000,000[^2], or $2.1 billion[^2], or $2,100,000,000[^2]." in text
    assert text.count("[^2]: ") == 1


def test_the_markdown_has_footnote_marks_and_no_ref_in_the_text(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """A cite reads as its text and its footnote mark; the refs and their sources are listed once,
    last, after Appendix B (spec 2026-11-15 9, B-108): GitHub-flavoured Markdown renders the
    footnote definitions at the end of the document, so the heading stands over its list."""
    sid = snapshots["AAPL"]
    report = _stored(conn, sid, sections=_cited(sid))
    refs = references(conn, report, policy)
    text = markdown(report, appendix_a(conn, report, policy), [], refs, {})
    body, _, appendixes = text.partition("\n## Appendix A\n")
    assert "The price of $150.00[^1] against revenue of $2,100,000,000[^2]." in body
    second = (
        "Revenue of $2.1 billion[^2] clears the hurdle of 9.0%[^3] at the price of $150.00[^1]."
    )
    assert second in body
    for form in ("snapshot:", "fact:", "policy:"):
        assert form not in body, form
    assert body.rstrip().endswith(f"## {HEADINGS[-1]}\n\nPlain words.")  # after the last section
    audit, _, rest = appendixes.partition("\n## Appendix B\n")
    terms, _, listed = rest.partition("\n## References\n")
    assert "[^" not in audit and "[^" not in terms
    assert listed.strip().splitlines() == [
        f"[^1]: snapshot:{sid}/price — snapshot {sid}, the price, priced 30 Oct 2026",
        "[^2]: fact:AAPL/revenue/2025 — the revenue line of fiscal 2025 on file",
        f"[^3]: policy:required_return — policy required_return, {policy.version}",
    ]
    assert text.endswith(f"policy required_return, {policy.version}\n")  # nothing after them
    plain = _stored(conn, sid, sections=[{"heading": HEADINGS[0], "parts": ["Plain words."]}])
    text = markdown(plain, appendix_a(conn, plain, policy), [], [], {})
    assert text.endswith("\n## References\n\nNo references.\n")


def _part(text: str, heading: str) -> str:
    """The Markdown under ``## <heading>``, to the next ``##`` heading."""
    start = text.index(f"\n## {heading}\n") + len(heading) + 5
    return text[start : text.index("\n## ", start)]


def test_the_markdown_carries_the_chart_tables(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Each chart's table twin under its section's heading, before the prose: section 4's six
    tables, their columns under their labels; section 5's quarters; section 8's grid of the
    secondary valuation; section 9's statistics and year-end points; no section else carries
    one."""
    sid = snapshots["AAPL"]
    closes = closes_payload("AAPL", {"2025-12-31": 22.0, "2026-10-30": 24.0})  # EPS 1.00 a year
    store_pe_history(conn, "AAPL", {"closes": closes, "quarters": unit_quarters("AAPL")}, NOW)
    secondary_id = _drivers_secondary(conn, policy, sid)
    report = _stored(conn, sid, secondary_id=secondary_id)
    text = markdown(
        report, appendix_a(conn, report, policy), [], [], chart_tables(conn, report, policy)
    )
    financial = _part(text, HEADINGS[3])
    assert re.findall(r"^### (.+)$", financial, re.MULTILINE) == [
        "Growth and profitability",
        "Cash flow",
        "Balance sheet and solvency",
        "Returns on capital",
        "Capital allocation",
        "Quality scores",
    ]
    growth = (
        "| Period | 2021 | 2022 | 2023 | 2024 | 2025 | 12 months to 30 Sep 2026 | 2026 estimate"
        " | 2027 estimate |"
    )
    assert f"### Growth and profitability\n\n{growth}\n" in financial
    # one plain line under the growth table's rows, its EPS estimates' basis (the whole-branch
    # review's I2), and under no other table
    basis = (
        "EPS estimates are on the analysts' own basis, which can leave out items the reported EPS"
        " includes."
    )
    assert financial.split("### Cash flow", 1)[0].endswith(f" |\n\n{basis}\n\n")
    assert text.count(basis) == 1
    assert "| Revenue | " in financial and " | $1,300,000,000 | $2,200,000,000 | " in financial
    returns = "### Returns on capital\n\n| Fiscal year | 2021 | 2022 | 2023 | 2024 | 2025 |\n"
    assert returns in financial
    assert "| $2,000,000,000 | $2,100,000,000 |" in financial  # at the cite's rounding
    assert financial.rstrip().endswith("|\n\nPlain words.")  # the prose after the tables
    call = _part(text, HEADINGS[4])
    assert re.findall(r"^### (.+)$", call, re.MULTILINE) == ["By quarter"]
    assert "| Period | Q3 2025 | Q4 2025 | Q1 2026 | Q2 2026 | Q3 2026 |" in call
    assert "| Operating margin | 20.0% | " in call and call.rstrip().endswith("|\n\nPlain words.")
    valuation = _part(text, "Valuation")
    assert f"### The grid of secondary valuation {secondary_id}" in valuation
    assert "| Terminal growth | r 8.0% | r 9.0% | r 10.0% |" in valuation
    assert valuation.rstrip().endswith("|\n\nPlain words.")
    price = _part(text, "Price and multiples")
    assert "| Series | Ten-year average | Median | High | Low | Since |" in price
    assert "| Trailing P/E | 23.00x | 23.00x | 24.00x | 22.00x | 31 Dec 2025 |" in price
    assert "| Year | Trailing P/E | Forward P/E |" in price and "| 2026 | 24.00x |  |" in price
    assert price.rstrip().endswith("|\n\nPlain words.")
    charted = {HEADINGS[3], HEADINGS[4], "Valuation", "Price and multiples"}
    for heading in set(HEADINGS) - charted:
        assert "### " not in _part(text, heading), heading
    # without an EPS estimate on file, no line
    revenue_only = [{"symbol": "AAPL", "date": "2026-12-31", "revenueAvg": 2_200_000_000}]
    store_payloads(conn, "AAPL", {"estimates-annual": revenue_only}, NOW)
    text = markdown(
        report, appendix_a(conn, report, policy), [], [], chart_tables(conn, report, policy)
    )
    assert "| 2026 estimate |" in text and basis not in text


def test_a_report_on_file_renders_with_the_columns_and_the_quarters(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Review Focus 4: a report stored as reports were before the change, its record its sections
    alone, renders through ``markdown`` with no error and no migration, since the chart tables and
    the references are read from the store when it is exported: section 4 carries its six tables
    with the columns past the last fiscal year, section 5 the quarters, and the references come
    last. A cite of an estimate cell outlives the cell: once the consensus no longer holds fiscal
    2026, its column is gone and the cite still reads its words."""
    sid = snapshots["AAPL"]
    estimate = "table:AAPL/growth/revenue_growth/2026E"
    sections = _cited(sid)
    sections[4] = {
        "heading": HEADINGS[4],
        "parts": ["Revenue growth of ", {"cite": "4.8%", "ref": estimate}, " is expected."],
    }
    report = _stored(conn, sid, sections=sections)

    def exported() -> str:
        return markdown(
            report,
            appendix_a(conn, report, policy),
            appendix_b(report.sections),
            references(conn, report, policy),
            chart_tables(conn, report, policy),
        )

    text = exported()
    financial = _part(text, HEADINGS[3])
    assert re.findall(r"^### (.+)$", financial, re.MULTILINE) == [
        "Growth and profitability",
        "Cash flow",
        "Balance sheet and solvency",
        "Returns on capital",
        "Capital allocation",
        "Quality scores",
    ]
    assert "| 12 months to 30 Sep 2026 | 2026 estimate | 2027 estimate |" in financial
    assert "### By quarter\n\n| Period | Q3 2025 |" in _part(text, HEADINGS[4])
    # Appendix A names the snapshot the report rests on (the whole-branch review's I1)
    assert f"\n## Appendix A\n\n### Snapshot\n\nSnapshot {sid} · data 30 Oct 2026 · " in text
    words = "the growth table, revenue growth, fiscal 2026, the analysts' estimate"
    assert text.endswith(f"[^4]: {estimate} — {words}\n")
    moved = [{"symbol": "AAPL", "date": "2027-12-31", "revenueAvg": 2_420_000_000, "epsAvg": 3.63}]
    store_payloads(conn, "AAPL", {"estimates-annual": moved}, NOW)
    text = exported()
    growth = _part(text, HEADINGS[3]).split("\n### ", 2)[1]
    assert "| 12 months to 30 Sep 2026 | 2027 estimate |" in growth
    assert "2026 estimate" not in growth
    assert text.endswith(f"[^4]: {estimate} — {words}\n")


def test_the_bridge_table_has_labels(
    conn: sqlite3.Connection, policy: Policy, snapshots: dict[str, int]
) -> None:
    """Each bridge line carries its input's label in a reader's words (``overrides.LABELS``), in
    Appendix A's record and in its table."""
    sid = snapshots["AAPL"]
    override_id, review_id = _review(conn, policy, sid)
    report = _stored(conn, sid, review_id)
    a = appendix_a(conn, report, policy)
    assert [(x["tag"], x["label"]) for x in a["bridge"]["lines"]] == [("growth.belief", "belief")]
    text = markdown(report, a, [], [], {})
    block = text[text.index("### Bridge") : text.index("### Secondary valuation")]
    assert "| Input | Label | Override | Old | New | Delta | Refusal |" in block
    assert f"| growth.belief | belief | {override_id} | 0.063 | 0.08 | " in block


def _made_before_the_split(conn: sqlite3.Connection, policy: Policy) -> int:
    """MGCO's snapshot of 10 Jan 2027 on the share basis before its 2-for-1 split of 27 Jan 2027,
    its NTM consensus each quarter twice the one after (``support.splits``); its id."""
    pre = mgco_on(BEFORE, BEFORE)
    doubled = tuple(
        replace(q, eps=None if q.eps is None else 2 * q.eps) for q in pre.quarter_estimates
    )
    result = value_company(
        replace(pre, quarter_estimates=doubled), universe_deciles(), policy, TODAY
    )
    return insert_snapshot(conn, result, under(conn, policy, "revalue"), clock=lambda: NOW)


SCALED_WORDS = "entered as $30.00 a share before the 2-for-1 split of 27 Jan 2027"


def test_appendix_a_shows_an_override_scaled_at_a_split_with_both_figures(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """Spec 2026-11-15 8 (method 14.6, 16.6): MGCO's lasting NTM EPS override, a reading of
    $11.80 set to $30.00 on its snapshot before its 2-for-1 split, and a belief of 8%, reviewed as
    the refresh reviews them on its snapshot after the split, where the engine reads $5.90.
    Appendix A's entry of the NTM override carries the pair in force, its bridge line's old and
    new, $5.90 and $15.00, both on the new basis, and the words of the scaling from its JUDGMENT
    entry's note, beside the stored pair as entered; the belief, applied as entered, carries
    neither. The export's row prints the pair in force and the words after the new figure in
    brackets, never the stored old figure beside the new one in force; the belief's row prints as
    before."""
    made_on = _made_before_the_split(conn, policy)
    ntm = made_on_mgco(conn, made_on, "earnings.ntm", 30.0, "USD a share")
    belief = made_on_mgco(conn, made_on, "growth.belief", 0.08, "ratio")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    review = follow_mgco(conn, policy, AFTER, AFTER)
    assert review.value is not None and review.override_ids == (ntm, belief)
    [line] = [x for x in review.bridge if x["override_id"] == ntm]
    assert (line["old"], line["new"]) == (5.9, 15.0)
    report = _stored(conn, review.snapshot_id, review.id, symbol="MGCO")
    a = appendix_a(conn, report, policy)
    by = {o["id"]: o for o in a["overrides"]}
    scaled, plain = by[ntm], by[belief]
    assert scaled["inForce"] == {"old": 5.9, "new": 15.0}
    assert scaled["rescaled"] == SCALED_WORDS
    assert (scaled["old"], scaled["new"]) == (pytest.approx(11.8), 30.0)  # the stored pair
    assert (plain["inForce"], plain["rescaled"]) == (None, None)
    assert (plain["old"], plain["new"]) == (0.063, 0.08)
    text = markdown(report, a, [], [], {})
    block = text[text.index("### Overrides") : text.index("### Guidance on file")]
    assert f"| {ntm} | earnings.ntm | 5.9 | 15.0 ({SCALED_WORDS}) | a stake |" in block
    row = next(r for r in block.splitlines() if r.startswith(f"| {ntm} |"))
    assert repr(scaled["old"]) not in row and "| 30.0 |" not in row
    assert f"| {belief} | growth.belief | 0.063 | 0.08 | a stake |" in block


def test_an_override_whose_step_refused_at_a_split_shows_the_figures_in_force(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A step that refused was applied at the figure in force and met its refusal there, so its
    override shows the pair in force and the words, as the bridge and the JUDGMENT entry read it
    (spec 2026-11-15 8, the controller's ruling of the Task 7 review): MGCO's NTM EPS set to
    −$2.00 before its 2-for-1 split, scaled to −$1.00 after it, where the step refuses ("no
    positive forward anchor"). The same override with no bridge line, as in the empty bridge of a
    failed review, which the review did not apply, shows its stored pair, the words on file or
    not."""
    made_on = _made_before_the_split(conn, policy)
    ntm = made_on_mgco(conn, made_on, "earnings.ntm", -2.0, "USD a share")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    review = follow_mgco(conn, policy, AFTER, AFTER)
    [line] = review.bridge
    assert (line["old"], line["new"], line["refusal"]) == (5.9, -1.0, "no positive forward anchor")
    words = "entered as −$2.00 a share before the 2-for-1 split of 27 Jan 2027"
    [entry] = [i for i in review.result.inputs if i.tag == "JUDGMENT"]
    assert (entry.value, entry.note) == (-1.0, f"a stake; {words}")
    report = _stored(conn, review.snapshot_id, review.id, symbol="MGCO")
    a = appendix_a(conn, report, policy)
    [o] = a["overrides"]
    assert (o["inForce"], o["rescaled"]) == ({"old": 5.9, "new": -1.0}, words)
    assert (o["old"], o["new"]) == (pytest.approx(11.8), -2.0)  # the stored pair
    text = markdown(report, a, [], [], {})
    assert f"| {ntm} | earnings.ntm | 5.9 | -1.0 ({words}) | a stake |" in text
    unbridged = Review(review.result, review.mechanical_value, (), review.override_ids)
    failed = insert_review(conn, unbridged, "MGCO", review.snapshot_id, None, clock=lambda: NOW)
    a = appendix_a(conn, _stored(conn, review.snapshot_id, failed, symbol="MGCO"), policy)
    [o] = a["overrides"]
    assert (o["inForce"], o["rescaled"], o["new"]) == (None, None, -2.0)


def test_appendix_a_shows_two_overrides_scaled_at_once_each_with_its_own_figures(
    conn: sqlite3.Connection, policy: Policy
) -> None:
    """A review with two overrides scaled at the one 2-for-1 split, a figure a share and a count:
    MGCO's NTM EPS of $30.00 divided to $15.00 and its committed shares of 60 m multiplied to
    120 m, each with its own pair in force and its own words, in Appendix A and in the export's
    rows (spec 2026-11-15 8)."""
    made_on = _made_before_the_split(conn, policy)
    ntm = made_on_mgco(conn, made_on, "earnings.ntm", 30.0, "USD a share")
    committed = made_on_mgco(conn, made_on, "shares.committed", 60e6, "shares", "period-tied")
    store_splits(conn, (SPLIT_DAY, 2, 1))
    review = follow_mgco(conn, policy, AFTER, AFTER)
    assert review.value is not None and review.override_ids == (ntm, committed)
    report = _stored(conn, review.snapshot_id, review.id, symbol="MGCO")
    a = appendix_a(conn, report, policy)
    by = {o["id"]: o for o in a["overrides"]}
    count = "entered as 60.0M shares before the 2-for-1 split of 27 Jan 2027"
    assert (by[ntm]["inForce"], by[ntm]["rescaled"]) == ({"old": 5.9, "new": 15.0}, SCALED_WORDS)
    assert (by[committed]["inForce"], by[committed]["rescaled"]) == (
        {"old": 0.0, "new": 120e6},
        count,
    )
    assert (by[ntm]["new"], by[committed]["new"]) == (30.0, 60e6)  # the stored figures
    block = markdown(report, a, [], [], {}).split("### Overrides", 1)[1]
    assert f"| {ntm} | earnings.ntm | 5.9 | 15.0 ({SCALED_WORDS}) | a stake |" in block
    assert f"| {committed} | shares.committed | 0.0 | 120000000.0 ({count}) | a stake |" in block
