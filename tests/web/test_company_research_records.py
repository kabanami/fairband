"""The company page's Research tab, its Records view (the Research tab's design, 7.2 and 7.10;
Review Focus 5): the nine panels in the design's order, each a table of the company's records,
newest first, with its count, "None on file." where it holds none; the ledger's head with the count
on file where more are on file than it draws; the count beside Records in the bar, the rows the
panels draw; and a review's bridge, drawn under its row on a press and closed by a second.
company.js and company_research_records.js run in node after the bundle and app.js
(``support.page``), and the tests read the plain panels ``panels`` gives and the tree ``draw``
returns; ``research.mjs`` drives the tab, the tab's other scripts loaded before them.

The answer is ``support.research_answers``' LFOX and its records on file, a record of each kind,
in TWD where it is money the company reports. Every company, figure and sentence is invented."""

import copy
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from support import page_answers
from support import research_answers as answers
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

RECORDS_JS = STATIC / "company_research_records.js"
SCRIPTS = (
    STATIC / "charts.js",
    STATIC / "company.js",
    STATIC / "report_parts.js",
    STATIC / "company_research_text.js",
    STATIC / "company_research.js",
    RECORDS_JS,
)
DRIVER = Path(__file__).parent / "research.mjs"
TODAY = page_answers.TODAY.isoformat()
NAMES = [
    "Kill criteria",
    "Guidance",
    "Overrides",
    "Notes",
    "Reviews",
    "Secondary valuations",
    "News items",
    "Findings",
    "Ledger",
]
HEADS = [
    ["State", "The thesis is wrong if", "Set", "Moved, and why"],
    ["Metric", "Period", "Range", "Midpoint", "Basis", "Call of", "State"],
    ["Input", "From", "To", "State", "The reason"],
    ["When", "The note"],
    ["When", "Value", "Mechanical value", "Overrides inside", "Price vs value, or the refusal"],
    ["When", "Form", "Value a share", "The reason"],
    ["Date", "Headline", "What happened"],
    ["As of", "Period", "Figure", "The words", "Source"],
    ["When", "Kind", "What was written", "By"],
]
NONE = "None on file."
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
REVIEWS = NAMES.index("Reviews")
COUNT = 23  # the rows the panels of the synthetic records draw
RECORDS_VIEW = ("app-research__view", f"Records {COUNT}")


def _records() -> dict[str, Any]:
    records: dict[str, Any] = copy.deepcopy(answers.RECORDS)
    return records


def _panels(records: dict[str, Any]) -> list[dict[str, Any]]:
    """What ``researchRecords.panels`` gives on ``records``."""
    found: list[dict[str, Any]] = node("researchRecords.panels", [records], *SCRIPTS)
    return found


def _drawn(records: dict[str, Any]) -> Any:
    return node("researchRecords.draw", [records], *SCRIPTS)


def _texts(panel: dict[str, Any]) -> list[list[str]]:
    """Each row's cells' texts."""
    return [[c["text"] for c in row["cells"]] for row in panel["rows"]]


def _local(iso: str) -> datetime:
    """A stored time in the reader's local time, as the page reads it (``localIso``): node and
    this process share the machine's zone."""
    return datetime.fromisoformat(iso).astimezone()


def _day(iso: str) -> str:
    """A day as the page writes it, of a stored time in the reader's local time: 11 Nov 2026."""
    at = _local(iso)
    return f"{at.day} {MONTHS[at.month - 1]} {at.year}"


def _when(iso: str) -> str:
    """A time as the page writes it (``FairbandPage.when``): 11 Nov 2026, 14:05 at UTC."""
    at = _local(iso)
    return f"{_day(iso)}, {at.hour:02d}:{at.minute:02d}"


def _drive(steps: list[dict[str, Any]]) -> Any:
    """The trace of ``steps`` (``research.mjs``), no fetch answered and no store."""
    assert NODE is not None
    scripts = (BUNDLE, STATIC / "app.js", *SCRIPTS)
    done = subprocess.run(
        [NODE, str(DRIVER), *(str(script) for script in scripts)],
        input=json.dumps({"store": {}, "answers": {}, "steps": steps}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    assert done.stderr == "", done.stderr
    return json.loads(done.stdout)


def _mount(answer: dict[str, Any]) -> dict[str, Any]:
    return {"do": "mount", "answer": answer, "detail": page_answers.detail()}


def _press(name: str, words: str) -> dict[str, Any]:
    return {"do": "press", "class": name, "text": words}


def _one(tree: Any, name: str) -> dict[str, Any]:
    [found] = classed(tree, name)
    return found


def _clean(tree: Any) -> None:
    """No text the tree holds is a figure that failed."""
    for word in ("NaN", "null", "undefined", "Infinity"):
        assert word not in text(tree), word


# ---------------------------------------------------------------------------------- the panels


def test_the_nine_panels_in_order() -> None:
    """The nine kinds in the design's order, each with its count of the rows it draws and its
    columns' heads; the judgments have none. Drawn, each is a panel with its name and its count
    over a table of its records, a panel with records across the view's two columns."""
    records = _records()
    panels = _panels(records)
    assert [p["name"] for p in panels] == NAMES
    assert [p["count"] for p in panels] == [3, 3, 2, 1, 3, 1, 3, 3, 4]
    assert [p["count"] for p in panels] == [len(p["rows"]) for p in panels]
    assert [p["heads"] for p in panels] == HEADS
    assert [p["note"] for p in panels] == [None] * 9
    assert "judgments" in records and not [p for p in panels if p["name"] == "Judgments"]

    view = _drawn(records)
    assert "app-research__records" in view["props"]["className"].split()
    drawn = classed(view, "app-research__panel")
    assert [text(_one(p, "app-research__title")) for p in drawn] == [
        f"{name} {p['count']}" for name, p in zip(NAMES, panels, strict=True)
    ]
    for panel, shown in zip(panels, drawn, strict=True):
        assert "app-research__panel--full" in shown["props"]["className"].split()
        [table] = [e for e in elements(shown) if e.get("type") == "table"]
        heads = [e for e in elements(table) if e.get("type") == "th"]
        assert [text(e) for e in heads] == panel["heads"]
        body = [e for e in elements(table) if e.get("type") == "tbody"]
        rows = [e for e in elements(body) if e.get("type") == "tr"]
        assert [[text(td) for td in row["props"]["children"][0]] for row in rows] == _texts(panel)
        assert classed(shown, "app-research__empty") == []
    _clean(view)


def test_each_panel_s_rows() -> None:
    """Each record's cells, newest first as the read serves them, the news items by their date: a
    kill criterion's state, text, day set, and the day it moved with its reason; a guidance
    record's metric in words, a range in percent and one in its own currency, its midpoint, its
    basis, its call's day and current or superseded by ``supersededBy``; an override's figures
    by ``FairbandPage.inputFigure``, a dash for none; a note's time; a review's value, its
    mechanical value, its count of overrides, and its designation or its refusal; a secondary
    valuation's form and value a share; a news item's headline a link where its source is a web
    address; a finding's figure in its unit and currency, a dash for none; a ledger row's writer."""
    panels = {p["name"]: p for p in _panels(_records())}
    rival = "A rival launched a lens of the same grade on 28 Oct 2026."
    assert _texts(panels["Kill criteria"]) == [
        ["open", "Sensor revenue falls two quarters in a row.", _day(answers.CREATED), "—"],
        ["open", "The gross margin falls below the threshold.", "2 Oct 2026", "—"],
        [
            "triggered",
            "A rival matches the newest lens grade.",
            "2 Oct 2026",
            f"{_day('2026-11-11T13:30:00+00:00')}: {rival}",
        ],
    ]
    assert [r["cells"][0]["kind"] for r in panels["Kill criteria"]["rows"]] == ["stamp"] * 3

    guidance = panels["Guidance"]
    assert _texts(guidance) == [
        ["operating margin", "2026", "7.0% to 10.0%", "8.5%", "gaap", "22 Oct 2026", "current"],
        [
            "revenue",
            "2026",
            "TWD 440,000,000,000 to TWD 455,000,000,000",
            "TWD 447,500,000,000",
            "gaap",
            "22 Oct 2026",
            "current",
        ],
        [
            "revenue",
            "2026",
            "TWD 430,000,000,000 to TWD 450,000,000,000",
            "TWD 440,000,000,000",
            "gaap",
            "24 Jul 2026",
            "superseded",
        ],
    ]
    assert [c["kind"] for c in guidance["rows"][0]["cells"]][2:4] == ["figure", "figure"]
    usd = _records()
    point = {"currency": "USD", "low": 4.4e9, "high": 4.4e9, "midpoint": 4.4e9}
    usd["guidance"] = [usd["guidance"][1] | point]
    assert _texts(_panels(usd)[1])[0][2:4] == ["$4,400,000,000", "$4,400,000,000"]
    assert guidance["rows"][2]["cells"][6]["kind"] == "stamp"

    assert _texts(panels["Overrides"]) == [
        ["moat.class", "—", "Narrow", "applied", answers.OVERRIDE["reason"]],
        [
            "return.runway",
            "47.2%",
            "21.4%",
            "dropped",
            "The return on new plants falls as the newest grade's premium fades.",
        ],
    ]
    runway = answers.RECORDS["overrides"][1]
    assert _texts(panels["Overrides"])[1][1:3] == [
        node("inputFigure", [runway["old"], runway["unit"]]),
        node("inputFigure", [runway["new"], runway["unit"]]),
    ]
    assert _texts(panels["Notes"]) == [
        [_when("2026-11-12T08:15:00+00:00"), "Ask about the car contracts at the next call."]
    ]
    assert panels["Notes"]["rows"][0]["cells"][0]["at"] == "2026-11-12T08:15:00+00:00"

    reviews = panels["Reviews"]
    assert _texts(reviews) == [
        [_when("2026-11-14T06:25:00+00:00"), "$182.00", "$196.50", "1", "Near"],
        [_when("2026-11-11T13:50:00+00:00"), "$182.00", "$196.50", "1", "Near"],
        [
            _when("2026-10-02T10:10:00+00:00"),
            "—",
            "$171.20",
            "1",
            "The runway return leaves no value above zero.",
        ],
    ]
    assert [r["cells"][4]["kind"] for r in reviews["rows"]] == [
        "designation",
        "designation",
        "refusal",
    ]
    assert reviews["rows"][0]["cells"][4]["designation"] == "near"

    assert _texts(panels["Secondary valuations"]) == [
        [
            _when("2026-10-02T10:20:00+00:00"),
            "parts",
            "$114.65",
            "A second view while the newest grade ramps.",
        ]
    ]

    news = panels["News items"]
    assert _texts(news) == [
        [
            "3 Nov 2026",
            "A new supply contract with a car supplier",
            "A new supply contract with a car supplier.",
        ],
        [
            "28 Oct 2026",
            "A rival launched a lens of the same grade",
            "A rival launched a lens of the same grade.",
        ],
        [
            "18 Sep 2026",
            "The newest lens grade went into production",
            "The newest lens grade went into production.",
        ],
    ]
    assert [r["cells"][1].get("href") for r in news["rows"]] == [
        "https://lanternfield.example/contract",
        None,
        "https://lanternfield.example/grade",
    ]
    stored = _records()
    stored["newsItems"] = list(reversed(stored["newsItems"]))  # by the date, not by the store
    assert _texts(_panels(stored)[6]) == _texts(news)
    links = [e for e in elements(_drawn(_records())) if e.get("type") == "a"]
    assert [(text(a), a["props"]["href"]) for a in links] == [
        ("A new supply contract with a car supplier", "https://lanternfield.example/contract"),
        ("The newest lens grade went into production", "https://lanternfield.example/grade"),
    ]
    assert all(a["props"]["target"] == "_blank" and a["props"]["rel"] == "noopener" for a in links)

    assert _texts(panels["Findings"]) == [
        [
            "31 Dec 2025",
            "2025",
            "TWD 98,300,000,000",
            "Free cash flow in fiscal 2025 funded the new plants in full.",
            "filing",
        ],
        [
            "22 Oct 2026",
            "2026-Q3",
            "6",
            "Sensor sales to car suppliers rose for six quarters running.",
            "transcript",
        ],
        ["21 Oct 2026", "—", "—", "The company named a new head of its car business.", "url"],
    ]
    finding = _records()["findings"][1]
    for unit, value, currency, shown in (
        ("percent", -0.031, None, "−3.1%"),
        ("per-share", 12.5, "TWD", "TWD 12.50"),
        ("per-share", 4.2, "USD", "$4.20"),
        ("currency", -2.0e9, None, "−$2,000,000,000"),
        ("multiple", 1.375, None, "1.38x"),
        ("years", 6.25, None, "6.3 years"),
        ("score", 6.2, None, "6.20"),
        ("count", 1200.0, None, "1,200"),
    ):
        one = _records()
        one["findings"] = [finding | {"unit": unit, "value": value, "currency": currency}]
        assert _texts(_panels(one)[7])[0][2] == shown, unit

    ledger = panels["Ledger"]
    assert [row[1:] for row in _texts(ledger)] == [
        ["report", "full report revision 2: hold", "claude-opus-5-5"],
        ["override", "moat.class: Narrow", "claude-opus-5-5"],
        [
            "finding",
            "Sensor sales to car suppliers rose for six quarters running.",
            "claude-opus-5-5",
        ],
        ["guidance", "revenue 2026", "claude-opus-5-5"],
    ]
    assert _texts(ledger)[0][0] == _when(answers.CREATED)
    owner = _records()
    owner["ledger"] = [owner["ledger"][0] | {"principal": "owner", "actor": None, "kind": "note"}]
    owner["ledgerCount"] = 1
    assert _texts(_panels(owner)[8])[0][1:] == ["note", "full report revision 2: hold", "owner"]
    _clean(_drawn(_records()))


def test_none_on_file() -> None:
    """A company with no record of a kind: its panel's count is 0 and it draws "None on file." in
    its table's place, at half the view's width; a kind with records keeps its table."""
    records = _records()
    for key in records:
        records[key] = 0 if key == "ledgerCount" else []
    panels = _panels(records)
    assert [(p["count"], p["rows"], p["note"]) for p in panels] == [(0, [], None)] * 9
    drawn = classed(_drawn(records), "app-research__panel")
    assert [text(_one(p, "app-research__empty")) for p in drawn] == [NONE] * 9
    assert [e for e in elements(drawn) if e.get("type") == "table"] == []
    assert all("app-research__panel--full" not in p["props"]["className"] for p in drawn)

    some = _records()
    some["notes"] = []
    notes = classed(_drawn(some), "app-research__panel")[NAMES.index("Notes")]
    assert text(_one(notes, "app-research__empty")) == NONE
    others = [p for i, p in enumerate(classed(_drawn(some), "app-research__panel")) if i != 3]
    assert all(classed(p, "app-research__empty") == [] for p in others)


def test_the_ledger_says_the_newest_20_only_when_more_are_on_file() -> None:
    """Twenty rows of 192 on file: the ledger's count is the 20 it draws, and its head says
    "the newest 20 of 192"; three rows of three say nothing more."""
    records = _records()
    row = records["ledger"][0]
    records["ledger"] = [row | {"id": 1000 - n} for n in range(20)]
    records["ledgerCount"] = 192
    ledger = _panels(records)[8]
    assert (ledger["count"], ledger["note"]) == (20, "the newest 20 of 192")
    head = classed(_drawn(records), "app-research__panel")[8]
    assert text(_one(head, "app-research__title")) == "Ledger 20"
    assert text(_one(head, "app-research__headnote")) == "the newest 20 of 192"
    assert len([e for e in elements(head) if e.get("type") == "tr"]) == 21

    records["ledger"] = records["ledger"][:3]
    records["ledgerCount"] = 3
    ledger = _panels(records)[8]
    assert (ledger["count"], ledger["note"]) == (3, None)
    head = classed(_drawn(records), "app-research__panel")[8]
    assert classed(head, "app-research__headnote") == []
    assert "newest" not in text(head)


def test_the_bar_s_count_is_the_rows_drawn() -> None:
    """Records in the bar carries the count of the rows its panels draw, after a space as a
    panel's head has its count, the judgments left out and the ledger's twenty counted, not the
    count on file; in either view."""
    records = _records()
    assert node("researchRecords.count", [records], *SCRIPTS) == COUNT
    answer = answers.answer()
    for view in ("report", "records"):
        bar = node("research.bar", [answer, view, False, {"today": TODAY}], *SCRIPTS)
        report, shown = classed(bar, "app-research__view")
        assert text(report) == "Report"
        assert text(shown) == f"Records {COUNT}"
        assert text(_one(shown, "app-research__n")) == str(COUNT)

    row = records["ledger"][0]
    records["ledger"] = [row | {"id": 1000 - n} for n in range(20)]
    records["ledgerCount"] = 192
    assert node("researchRecords.count", [records], *SCRIPTS) == COUNT - 4 + 20
    empty = {key: 0 if key == "ledgerCount" else [] for key in records}
    answer["records"] = empty
    bar = node("research.bar", [answer, "records", False, {"today": TODAY}], *SCRIPTS)
    assert text(classed(bar, "app-research__view")[1]) == "Records 0"


# ---------------------------------------------------------------------------------- the view


def test_records_draws_the_panels_under_the_bar() -> None:
    """A press on Records draws the panels under the bar in the line's place, as ``draw`` gives
    them; a company with no report draws them too; Report draws none."""
    answer = answers.answer()
    mounted, records = _drive([_mount(answer), _press(*RECORDS_VIEW)])
    assert classed(mounted["tree"], "app-research__records") == []
    view = _one(records["tree"], "app-research__records")
    assert view == _drawn(answer["records"])
    top = _one(records["tree"], "app-research__top")
    assert records["tree"]["props"]["children"] == [top, view]

    none = answers.answer() | {"report": None, "call": None, "reports": []}
    _, shown = _drive([_mount(none), _press(*RECORDS_VIEW)])
    assert _one(shown["tree"], "app-research__records") == _drawn(none["records"])


def _row_text(review: int) -> str:
    """The text of the drawn row of the review at ``review`` in the Reviews panel."""
    row = _panels(_records())[REVIEWS]["rows"][review]
    return "".join(c["text"] for c in row["cells"])


def _expanded(step: dict[str, Any]) -> list[str]:
    """Whether each review's bridge is open, as its row's button says."""
    rows = classed(step["tree"], "app-research__review")
    return [_one(r, "app-research__open")["props"]["aria-expanded"] for r in rows]


def test_a_press_on_a_review_draws_its_bridge() -> None:
    """A press on a review's row draws its bridge under it, the design system's ValueBridge from
    its mechanical value to its value, each line under its label, from and to by
    ``FairbandPage.inputFigure`` in its unit, with its effect and its override's writer and
    reason; a second press closes it. Its time is a button that says whether the bridge is open,
    so the keyboard opens it too. A review with no value draws its refusal in the bridge's place;
    a press on another row opens that one alone."""
    answer = answers.answer()
    steps = [_mount(answer), _press(*RECORDS_VIEW)]
    steps += [_press("app-research__review", _row_text(0))] * 2
    steps += [_press("app-research__review", _row_text(2))]
    steps += [_press("app-research__review", _row_text(1))]
    _, shut, opened, closed, refused, other = _drive(steps)

    assert classed(shut["tree"], "fb-bridge") == []
    rows = classed(opened["tree"], "app-research__review")
    assert _expanded(opened) == ["true", "false", "false"]
    assert ["is-open" in r["props"]["className"].split() for r in rows] == [True, False, False]
    [bridge] = classed(opened["tree"], "fb-bridge")
    line = answers.REVIEWS[0]["bridge"][0]
    expected = {
        "mechanical": 196.5,
        "reviewed": 182.0,
        "hero": False,
        # the day of the mechanical value: the day the review was made (spec 2026-11-23 held
        # reviewed value, 5.7), here its own
        "mechanicalDay": node("localIso", [answers.REVIEWS[0]["createdAt"]])[:10],
        "overrides": [
            {
                "tag": "moat",
                "from": node("inputFigure", [line["old"], line["unit"]]),
                "to": node("inputFigure", [line["new"], line["unit"]]),
                "delta": -14.5,
                "principal": "agent",
                "actor": "claude-opus-5-5",
                "reason": answers.OVERRIDE["reason"],
            }
        ],
    }
    assert bridge == node("Fairband.ValueBridge", [expected])
    assert "Override — moat Wide → Narrow" in text(bridge)
    assert f"Mechanical value of {_day(answers.REVIEWS[0]['createdAt'])}" in text(bridge)
    under = _one(opened["tree"], "app-research__bridge")
    body = [e for e in elements(_one(opened["tree"], "app-research__records")) if e["type"] == "tr"]
    assert body.index(under) == body.index(rows[0]) + 1
    assert under["props"]["children"][0]["props"]["colSpan"] == 5

    assert classed(closed["tree"], "fb-bridge") == []
    assert classed(closed["tree"], "app-research__bridge") == []

    assert classed(refused["tree"], "fb-bridge") == []
    sentence = _one(_one(refused["tree"], "app-research__bridge"), "app-refusal")
    assert text(sentence) == "The runway return leaves no value above zero."
    assert _expanded(refused) == ["false", "false", "true"]
    assert _expanded(other) == ["false", "true", "false"]
    assert len(classed(other["tree"], "fb-bridge")) == 1


def test_a_held_copy_s_bridge_says_the_day_the_review_was_made() -> None:
    """Spec 2026-11-23 held reviewed value, 5.2 and 5.7: a copy a refresh carried keeps the bridge
    with the mechanical value of the day the review was made, and its bridge's first line says
    that day, not the copy's own. A bridge given no day says "Mechanical value" alone."""
    made = answers.REVIEWS[1] | {"kind": "made", "madeId": None}
    copy = answers.REVIEWS[0] | {"kind": "held", "madeId": made["id"]}
    records = answers.answer()["records"] | {"reviews": [copy, made]}
    rows = node("researchRecords.panels", [records], *SCRIPTS)[REVIEWS]["rows"]
    day = node("localIso", [made["createdAt"]])[:10]
    assert [row["bridge"]["mechanicalDay"] for row in rows] == [day, day]
    assert copy["createdAt"][:10] != made["createdAt"][:10]
    plain = node(
        "Fairband.ValueBridge", [{"mechanical": 196.5, "reviewed": 182.0, "overrides": []}]
    )
    assert "Mechanical value196.5" not in text(plain) and "Mechanical value of" not in text(plain)


def test_the_view_writes_nothing() -> None:
    """Records is read-only: opening it and a review's bridge fetches nothing and offers no
    control to write."""
    steps = [_mount(answers.answer()), _press(*RECORDS_VIEW)]
    steps += [_press("app-research__review", _row_text(0))]
    _, shown, opened = _drive(steps)
    assert shown["fetched"] == [] and opened["fetched"] == []
    view = _one(opened["tree"], "app-research__records")
    assert [e for e in elements(view) if e["type"] in ("input", "textarea", "select", "form")] == []
    buttons = [e for e in elements(view) if e["type"] == "button"]
    assert [b["props"]["className"] for b in buttons] == ["app-research__open"] * 3
