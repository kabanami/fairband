"""The company page's Research tab, its frame (the Research tab's design, 7.2, 7.3, 7.4, 7.7 and
7.8; Review Focus 3 and 5): the bar and its line, the section list, a section's panel drawn by its
layout with the design system's reader, a cite's source, the footnote marks kept in the browser,
the three closed parts, a company with no report, the two views and the Markdown's refusal.
company.js, report_parts.js, company_research_text.js and company_research.js run in node after
the bundle and app.js (``support.page``), and the tests read the trees the tab's builders return;
``research.mjs`` drives the tab's state, with a store and answers of its own; the rules node
cannot run are read from the page's CSS.

The answer is ``support.research_answers``' LFOX: report 31, revision 2 of a full report, a hold,
on the data of 10 Nov 2026, valid until 12 Feb 2027, and report 19 before it, revision 1, a trim
of 2 Oct 2026. Every company, figure and sentence is invented."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support import page_answers
from support import research_answers as answers
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (
    STATIC / "charts.js",
    STATIC / "company.js",
    STATIC / "report_parts.js",
    STATIC / "company_research_text.js",
    STATIC / "company_research.js",
    STATIC / "company_research_records.js",
)
DRIVER = Path(__file__).parent / "research.mjs"
KEY = "fairband.research.marks"
TODAY = page_answers.TODAY.isoformat()
HEADINGS = [s["heading"] for s in answers.SECTIONS]
RECORDS = "The company's records on file, from any report."
# Records in the bar with the count of the rows its panels draw of the synthetic records, after a
# space, as a Records panel's head has its count (company_research_records.js;
# tests/web/test_company_research_records.py).
RECORDS_VIEW = "Records 23"
EXPIRED = "The value of this report is past the date it was valid until"
MARKS = ("app-research__marks", "Footnote marks")
DOWNLOAD = ("app-research__download", "Download .md")
MARKDOWN = "/api/reports/31/markdown"


def _research(helper: str, *args: Any) -> Any:
    """What ``research.<helper>`` returns on ``args``, the tab's scripts loaded after app.js."""
    return node("research." + helper, list(args), *SCRIPTS)


def _drive(
    store: Any, steps: list[dict[str, Any]], replies: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """The trace of ``steps`` with the store ``store`` and the fetch's ``replies``
    (``research.mjs``)."""
    assert NODE is not None
    scripts = (BUNDLE, STATIC / "app.js", *SCRIPTS)
    done = subprocess.run(
        [NODE, str(DRIVER), *(str(script) for script in scripts)],
        input=json.dumps({"store": store, "answers": replies or {}, "steps": steps}),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


def _mount(answer: dict[str, Any] | None = None, do: str = "mount") -> dict[str, Any]:
    """The tab opened on ``answer``, the synthetic one where none is given, with LFOX's detail."""
    return {
        "do": do,
        "answer": answer if answer is not None else answers.answer(),
        "detail": page_answers.detail(),
    }


def _press(name: str, words: str) -> dict[str, Any]:
    return {"do": "press", "class": name, "text": words}


def _classes(e: dict[str, Any]) -> list[str]:
    return str(e["props"].get("className") or "").split()


def _one(tree: Any, name: str) -> dict[str, Any]:
    [found] = classed(tree, name)
    return found


def _texts(tree: Any) -> list[str]:
    return [text(e) for e in elements(tree)]


def _references(count: int) -> list[dict[str, Any]]:
    """``count`` references, the report's own first, then synthetic ones after them."""
    own: list[dict[str, Any]] = answers.answer()["report"]["references"]
    more = [
        {"n": n, "ref": f"derived:{n}", "source": f"derivation {n}"}
        for n in range(len(own) + 1, count + 1)
    ]
    return own + more


def _rule(selector: str, indent: str = r"[ \t]*") -> str:
    """The declarations of the page's one rule whose line opens with ``selector``, on one line;
    with ``indent`` "  ", the one outside any ``@media`` block."""
    css = _static_file("index.html")
    ends = [m.end() for m in re.finditer(r"(?m)^" + indent + re.escape(selector), css)]
    assert len(ends) == 1, selector
    return " ".join(css[ends[0] : css.index("}", ends[0])].split())


# ------------------------------------------------------------------------------------- the bar


def test_the_bar_s_line() -> None:
    """In the Report view, the report's line: its stance in the Stance column's chip, faded with
    a title that says so once its validity ended before the detail's day; its mode; its
    revision; its date and time as the page writes them; who wrote it; valid until and the
    date."""
    answer = answers.answer()
    answer["report"]["appendixA"]["snapshot"]["validUntil"] = "2027-02-04"
    tree = _research("bar", answer, "report", False, {"today": TODAY})
    line = _one(tree, "app-research__line")
    stance = _one(line, "fb-stance")
    assert stance["props"]["className"] == "fb-stance fb-stance--hold label"
    assert stance["props"].get("title") is None
    assert text(stance) == "hold"
    found = _texts(line)
    at = [found.index(w) for w in ("hold", "full report", "revision 2", "valid until 4 Feb 2027")]
    assert at == sorted(at)
    drawn = list(elements(line))
    when = node("when", [answers.CREATED])
    [chip] = [e for e in drawn if "principal" in e["props"]]
    assert (chip["props"]["principal"], chip["props"]["actor"]) == ("agent", "claude-opus-5-5")
    # the date and time, then the writer, between the revision and the end of the window
    order = [drawn.index(e) for e in drawn if e == when or e is chip]
    assert len(order) == 2 and order == sorted(order)
    assert found.index("revision 2") < order[0] and order[1] < found.index("valid until 4 Feb 2027")

    for today in ("2027-02-05", "2027-03-01"):
        late = _one(_research("bar", answer, "report", False, {"today": today}), "fb-stance")
        assert late["props"]["className"] == "fb-stance fb-stance--hold fb-stance--expired label"
        assert late["props"]["title"] == EXPIRED
    on_the_day = _research("bar", answer, "report", False, {"today": "2027-02-04"})
    assert "fb-stance--expired" not in _one(on_the_day, "fb-stance")["props"]["className"]


# LFOX's detail reports in TWD and is an ADR, five ordinary shares an ADS, at TWD 32.40 a dollar.
PER_ADS = (
    "Reports in TWD; one ADS is five ordinary shares; every per-share figure here is per ADS;"
    " valued at TWD 32.40 per USD"
)


def test_the_report_view_says_what_the_figures_are_in() -> None:
    """The foreign filers' design (spec 2026-11-10, 6.2 and 7.4), the report page's head's line
    carried to the tab: in the Report view, under the bar, for a company in another currency or
    an ADR, what its figures are in, every figure a share per ADS on an ADR
    (``FairbandPage.currencyLine`` of the detail the tab is handed, with ``perAds``), in caption
    and ink-faint, before the bar's other lines; none for a company in US dollars that is no ADR,
    none in the Records view and none for a company with no report."""
    adr, records = _drive({}, [_mount(), _press("app-research__view", RECORDS_VIEW)])
    line = _one(adr["tree"], "app-research__currency")
    assert line["type"] == "p"
    assert _classes(line) == ["caption", "app-muted", "app-research__currency"]
    assert text(line) == PER_ADS == node("currencyLine", [page_answers.detail(), True])
    top = _one(adr["tree"], "app-research__top")["props"]["children"]
    assert top.index(line) == 1  # under the bar, the first of its lines
    assert classed(records["tree"], "app-research__currency") == []

    domestic = page_answers.detail(currency="USD", isAdr=False, adrRatio=None, fxRate=None)
    [usd] = _drive({}, [{"do": "mount", "answer": answers.answer(), "detail": domestic}])
    assert classed(usd["tree"], "app-research__currency") == []
    assert classed(usd["tree"], "app-research__line") != []  # the bar's line still stands

    sek = page_answers.detail(currency="SEK", isAdr=False, adrRatio=None, fxRate=8.0)
    [foreign] = _drive({}, [{"do": "mount", "answer": answers.answer(), "detail": sek}])
    assert text(_one(foreign["tree"], "app-research__currency")) == (
        "Reports in SEK; valued at SEK 8.00 per USD"
    )

    none = answers.answer() | {"report": None, "call": None, "reports": []}
    [empty] = _drive({}, [_mount(none)])
    assert classed(empty["tree"], "app-research__currency") == []
    assert _rule(".app-research__currency {") == "margin: 0;"


def test_a_valuation_review_names_the_report_it_reuses_or_that_it_has_none() -> None:
    """A valuation review that reuses a full report says so in the line with that report's date;
    one that reuses none says so under the bar; a full report says neither."""
    answer = answers.answer()
    answer["report"] |= {"mode": "valuation review", "reusesFullReportOf": 19}
    reuses = _research("bar", answer, "report", False, {"today": TODAY})
    assert "reuses the full report of 2 Oct 2026" in _texts(_one(reuses, "app-research__line"))
    assert classed(reuses, "app-research__note") == []

    answer["report"]["reusesFullReportOf"] = None
    none = _research("bar", answer, "report", False, {"today": TODAY})
    assert text(_one(none, "app-research__note")) == "No full report to reuse."
    assert not [w for w in _texts(none) if w.startswith("reuses the full report of")]

    full = _research("bar", answers.answer(), "report", False, {"today": TODAY})
    assert classed(full, "app-research__note") == []
    assert not [w for w in _texts(full) if w.startswith("reuses the full report of")]


# ------------------------------------------------------------------------------------ the list


def test_the_list() -> None:
    """The report's twelve headings in their order, then the three kept closed, References with
    their count after a space, as Records has its count, so its text and its name read "References
    185", not one word; ten headings for a valuation review. The reports on file with their count,
    each with its date and revision over its mode and stance: the one shown marked and no link,
    the other a link to its address on the tab. The name ``shown`` names is marked."""
    answer = answers.answer()
    answer["report"]["references"] = _references(185)
    tree = _research("list", answer, "research-s1")
    assert tree["type"] == "nav"
    heads = [text(e) for e in classed(tree, "app-research__grouphead")]
    assert heads == ["The report", "Kept closed", "Reports on file · 2"]
    # the reports on file's group named, so the narrow width can set it in a line of its own
    assert [_classes(g) for g in classed(tree, "app-research__group")] == [
        ["app-research__group"],
        ["app-research__group"],
        ["app-research__group", "app-research__group--files"],
    ]
    links = classed(tree, "app-research__link")
    assert [text(e) for e in links] == [
        *HEADINGS,
        "References 185",
        "Appendix A",
        "Appendix B",
    ]
    assert [e["type"] for e in links] == ["button"] * 15
    assert [("is-on" in _classes(e)) for e in links] == [True] + [False] * 14
    assert text(_one(links[12], "app-research__n")) == "185"

    shown, other = classed(tree, "app-research__file")
    assert "is-on" in _classes(shown) and shown["type"] != "a" and "href" not in shown["props"]
    assert text(shown) == "11 Nov 2026, revision 2Full report, hold"
    assert other["type"] == "a" and "is-on" not in _classes(other)
    assert other["props"]["href"] == node("researchHref", ["LFOX", 19])
    assert other["props"]["href"] == "#company/LFOX/research/19"
    assert text(other) == "2 Oct 2026, revision 1Full report, trim"

    marked = _research("list", answer, "research-b")
    assert [text(e) for e in classed(marked, "app-research__link") if "is-on" in _classes(e)] == [
        "Appendix B"
    ]

    review = answers.answer()
    review["report"] |= {
        "mode": "valuation review",
        "sections": [s for s in answers.SECTIONS if s["heading"] not in HEADINGS[1:3]],
    }
    listed = _research("list", review, "research-s1")
    names = [text(e) for e in classed(listed, "app-research__link")]
    count = len(review["report"]["references"])
    assert names == [
        *(h for h in HEADINGS if h not in HEADINGS[1:3]),
        f"References {count}",
        "Appendix A",
        "Appendix B",
    ]


# ------------------------------------------------------------------------------- the sections


def _section(index: int, cards: dict[str, Any] | None = None) -> Any:
    report = answers.answer()["report"]
    return _research("section", report["sections"][index], index, report, cards or {})


def _rows(tree: Any) -> list[dict[str, Any]]:
    """The rows of a section's panel, in order."""
    rows: list[dict[str, Any]] = _one(tree, "app-research__body")["props"]["children"][0]
    return rows


def _laid(index: int) -> dict[str, Any]:
    section = answers.SECTIONS[index]
    laid: dict[str, Any] = node(
        "researchText.lay",
        [section["heading"], section["parts"], answers.STANCE],
        STATIC / "company_research_text.js",
    )
    return laid


def _block_count(laid: dict[str, Any]) -> int:
    """The blocks ``lay`` gives a section, its rows' and its cards', a named block one: a run's
    and a columns row's blocks, a wide row's and a pair's one, a sides row's one a side, and none
    in a row of charts alone."""
    count = len(laid["cards"])
    for row in laid["rows"]:
        if row["kind"] in ("run", "columns"):
            count += len(row["blocks"])
        elif row["kind"] == "sides":
            count += len(row["sides"])
        elif row["kind"] in ("wide", "pair"):
            count += 1
    return count


def _drawn_blocks(tree: Any) -> list[dict[str, Any]]:
    """The elements the reader drew for a section's blocks, a named block's body among them but
    not its name."""
    names = {id(e) for name in classed(tree, "app-research__name") for e in elements(name)}
    kinds = ("fb-report__prose", "fb-report__list", "fb-report__scroll")
    return [
        e for e in elements(tree) if id(e) not in names and any(k in _classes(e) for k in kinds)
    ]


def test_a_section_is_drawn_by_its_layout() -> None:
    """A section is a panel with its heading, id research-s<n> from 1. A run of text at the
    reading width; a wide table across the panel, the whole width where a cell is long; named
    lists side by side; the two sides each under its label; the cards of rule 2, each under its
    name, in a column beside the first run; a paragraph beside its charts, in a pair, drawn at
    the reading width as a run is. No block drawn twice, none left out."""
    business = _section(1)
    assert business["type"] == "section" and business["props"]["id"] == "research-s2"
    [title] = [e for e in elements(business) if e.get("type") == "h2"]
    assert text(title) == "The business"
    [split] = _rows(business)
    assert "app-research__split" in _classes(split)
    run, cards = split["props"]["children"]
    assert "app-research__run" in _classes(run) and "app-research__cards" in _classes(cards)
    assert [text(_one(c, "app-research__name")) for c in classed(cards, "app-research__card")] == [
        "Revenue by product",
        "What drives revenue",
    ]

    earnings = _section(4)
    assert [" ".join(_classes(r)) for r in _rows(earnings)] == [
        "app-research__run",
        "app-research__wide",
        "app-research__run",
        "app-research__wide app-research__wide--full",
        "app-research__run",
    ]
    assert classed(earnings, "app-research__cards") == []

    summary = _section(0)
    [columns] = classed(summary, "app-research__columns")
    assert [
        text(_one(n, "app-research__name")) for n in classed(columns, "app-research__named")
    ] == [
        "Reasons for",
        "Main risks",
        "What would change the view",
    ]
    assert "Stance: hold." not in text(summary)

    debate = _section(5)
    [sides] = classed(debate, "app-research__sides")
    assert [text(_one(s, "app-research__name")) for s in classed(sides, "app-research__side")] == [
        "The bull case",
        "The bear case",
    ]

    financial = _section(3)
    pairs = _rows(financial)
    assert [" ".join(_classes(r)) for r in pairs] == ["app-research__pair"] * 6
    assert all("app-research__run" in _classes(p["props"]["children"][0]) for p in pairs)

    for index in range(len(answers.SECTIONS)):
        drawn = _drawn_blocks(_section(index))
        assert len(drawn) == _block_count(_laid(index)), index
        texts = [json.dumps(e) for e in drawn]
        assert len(set(texts)) == len(texts), index


def test_the_blocks_are_the_bundle_s() -> None:
    """Each block of a run is the element the design system's reader draws for it,
    ``Fairband.reportText.draw``, its cites numbered by the report's references."""
    [mounted] = _drive({}, [_mount()])
    [summary] = [e for e in elements(mounted["tree"]) if e["props"].get("id") == "research-s1"]
    run = classed(summary, "app-research__run")[0]
    laid = _laid(0)
    blocks = laid["rows"][0]["blocks"]
    report = answers.answer()["report"]
    footnotes = {e["ref"]: e["n"] for e in report["references"]}
    drawn = run["props"]["children"][0]
    assert len(drawn) == len(blocks) >= 3
    for key, (element, block) in enumerate(zip(drawn, blocks, strict=True)):
        assert element == node("Fairband.reportText.draw", [block, footnotes, key])
    assert classed(run, "fb-cite__n")  # the cites carry their numbers, which the CSS hides


def test_a_section_with_no_card_draws_no_cards_column() -> None:
    """A section whose layout gives no card, and none from the records, draws no cards column;
    the records' cards for its heading stand in one beside its first run."""
    thesis = _section(6)
    assert classed(thesis, "app-research__cards") == []
    assert classed(thesis, "app-research__split") == []
    card = {"type": "div", "props": {"className": "probe", "children": ["a record's card"]}}
    held = _section(6, {"The thesis": [card]})
    [split] = _rows(held)
    run, cards = split["props"]["children"]
    assert "app-research__run" in _classes(run)
    assert cards["props"]["children"] == [[card]]


# ------------------------------------------------------------------------------- a cited number


def test_a_cite_s_source() -> None:
    """A cite's box gives its reference's number and its source; none for a ref the references
    lack."""
    references = [
        {"n": 1, "ref": "snapshot:38/price", "source": "snapshot 38, the price"},
        {
            "n": 3,
            "ref": "fact:AAPL/revenue/2026",
            "source": "FMP income statement, revenue, fiscal 2026",
        },
    ]
    words = "[3] FMP income statement, revenue, fiscal 2026"
    assert _research("source", "fact:AAPL/revenue/2026", references) == words
    assert _research("source", " fact:AAPL/revenue/2026 ", references) == words
    assert _research("source", "fact:AAPL/revenue/2027", references) is None
    assert _research("source", "constructor", references) is None


def test_footnote_marks() -> None:
    """Footnote marks is off at first; a press turns the tab's class on and keeps 1 in the
    browser, a second press 0; a reload with the item reads on. A store that throws reads off,
    and the press does not throw: the marks last while the tab is open."""
    mounted, pressed, again = _drive({}, [_mount(), _press(*MARKS), _press(*MARKS)])
    assert "app-research--marks" not in _classes(mounted["tree"])
    assert _one(mounted["tree"], "app-research__marks")["props"]["aria-pressed"] == "false"
    assert "app-research--marks" in _classes(pressed["tree"])
    assert _one(pressed["tree"], "app-research__marks")["props"]["aria-pressed"] == "true"
    assert pressed["store"] == {KEY: "1"}
    assert "app-research--marks" not in _classes(again["tree"]) and again["store"] == {KEY: "0"}

    [reloaded] = _drive({KEY: "1"}, [_mount()])
    assert "app-research--marks" in _classes(reloaded["tree"])

    mounted, pressed = _drive("throws", [_mount(), _press(*MARKS)])
    assert "app-research--marks" not in _classes(mounted["tree"])
    assert pressed["threw"] is False
    assert "app-research--marks" in _classes(pressed["tree"])

    kept = _drive(
        {},
        [
            {"do": "keep", "on": True},
            {"do": "stored"},
            {"do": "keep", "on": False},
            {"do": "stored"},
        ],
    )
    assert [(s["result"], s["store"]) for s in kept] == [
        (None, {KEY: "1"}),
        (True, {KEY: "1"}),
        (None, {KEY: "0"}),
        (False, {KEY: "0"}),
    ]
    stored, keep = _drive("throws", [{"do": "stored"}, {"do": "keep", "on": True}])
    assert (stored["result"], stored["threw"], keep["threw"]) == (False, False, False)


def test_the_marks_are_hidden_until_asked_for_and_a_cite_reads_as_the_text() -> None:
    """A cite takes the text's colour, accent on hover and focus; its [n] is hidden until
    Footnote marks is on; in an agent's table it carries no dotted line; in a card a table's
    cells after the first are set right. The section in view is marked as the app marks a
    selection."""
    assert _rule(".app-research .fb-cite__n {") == "display: none;"
    assert _rule(".app-research--marks .fb-cite__n {") == "display: inline;"
    assert "color: inherit;" in _rule(".app-research .fb-cite {")
    hover = _rule(".app-research .fb-cite:hover, .app-research .fb-cite:focus-visible {")
    assert "color: var(--accent);" in hover and "border-bottom-color: var(--accent);" in hover
    assert _rule(".app-research .fb-report__table .fb-cite {") == "border-bottom: 0;"
    right = _rule(".app-research__card .fb-report__table :is(th, td):not(:first-child) {")
    assert right == "text-align: right;"
    on = _rule(".app-research__link.is-on {")
    assert "background: var(--surface-selected);" in on
    assert "border-left-color: var(--accent);" in on
    assert "border-left: 2px solid" in _rule(".app-research__link {")
    # the tab's rules name no colour of their own: each is a token of the design system
    css = _static_file("index.html")
    tab = css[css.index("  /* The company page's Research tab") :]
    tab = tab[: tab.index("\n  /*", 10)]
    assert ".app-research" in tab
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", tab)


# ------------------------------------------------------------------------------- the closed parts


def test_the_closed_parts() -> None:
    """After the sections, three details, closed: References with their count, Appendix A and
    Appendix B with the glossary's count, each opened drawing the report's part (the references,
    Appendix A's nine parts and the glossary, P.reportParts)."""
    report = answers.answer()["report"]
    report["references"] = _references(185)
    parts = _research("closed", report)
    assert [p["type"] for p in parts] == ["details"] * 3
    assert [p["props"]["id"] for p in parts] == ["research-refs", "research-a", "research-b"]
    assert all("open" not in p["props"] for p in parts)
    heads = [
        [text(e) for e in _one(p, "app-research__summary")["props"]["children"]] for p in parts
    ]
    assert heads == [
        ["References", "185 sources, one for each cited number"],
        ["Appendix A", "the audit of the records the report rests on"],
        ["Appendix B", f"the glossary, {len(report['appendixB'])} terms"],
    ]
    for part, helper in zip(parts, ("references", "appendixA", "appendixB"), strict=True):
        fold = _one(part, "app-research__fold")
        assert fold["props"]["children"] == [node("reportParts." + helper, [report], *SCRIPTS)]
    appendix = node("reportParts.appendixA", [report], *SCRIPTS)
    assert [text(e) for e in elements(appendix) if e.get("type") == "h4"] == [
        "Snapshot",
        "Inputs",
        "Bridge",
        "Overrides",
        "Secondary valuation",
        "Guidance on file",
        "Checks that ran",
        "Versions",
        "Classifier evidence",
    ]


def test_a_press_on_a_closed_part_s_name_opens_it() -> None:
    """A press on a name in the list scrolls to its panel, and opens it where it is one of the
    closed three."""
    _, closed, section = _drive(
        {},
        [
            _mount(),
            _press("app-research__link", "Appendix A"),
            _press("app-research__link", "Summary"),
        ],
    )
    assert closed["touched"] == {"research-a": {"open": True, "scrolled": True}}
    assert section["touched"] == {"research-s1": {"open": False, "scrolled": True}}


# --------------------------------------------------------------------- the views and the states


def test_the_count_after_records_is_set_off_by_its_space_alone() -> None:
    """The count follows Records after a space, as a Records panel's head has it; no margin of
    its own adds to the space."""
    assert ".app-research__view .app-research__n" not in _static_file("index.html")
    assert _rule(".app-research__n {") == "color: var(--ink-faint);"


def test_the_view_is_report_first_and_a_press_shows_records() -> None:
    """The tab opens on Report: the bar's line, its two controls, the list and the panels. A
    press on Records puts its sentence in the line's place; Footnote marks, Download .md, the
    list and the panels leave. Another report of the company keeps the view; another company's
    tab opens on Report."""
    other = answers.answer()
    other["symbol"] = "BRK.B"
    mounted, records, revision, company = _drive(
        {},
        [
            _mount(),
            _press("app-research__view", RECORDS_VIEW),
            _mount(_report_19(), "land"),
            _mount(other, "land"),
        ],
    )
    views = classed(mounted["tree"], "app-research__view")
    assert [(text(v), v["props"]["aria-selected"]) for v in views] == [
        ("Report", "true"),
        (RECORDS_VIEW, "false"),
    ]
    assert [v["props"]["role"] for v in views] == ["tab", "tab"]
    assert classed(mounted["tree"], "fb-stance")
    assert classed(mounted["tree"], "app-research__marks")
    assert classed(mounted["tree"], "app-research__download")
    assert classed(mounted["tree"], "app-research__list")
    assert len(classed(mounted["tree"], "app-research__sec")) == 15

    for shows in (records, revision):
        tree = shows["tree"]
        assert [v["props"]["aria-selected"] for v in classed(tree, "app-research__view")] == [
            "false",
            "true",
        ]
        assert text(_one(tree, "app-research__line")) == RECORDS
        for gone in (
            "fb-stance",
            "app-research__marks",
            "app-research__download",
            "app-research__list",
            "app-research__sec",
        ):
            assert classed(tree, gone) == [], gone
    assert classed(company["tree"], "app-research__list")


def _report_19() -> dict[str, Any]:
    """The answer of the tab on report 19, the company's first revision."""
    answer = answers.answer()
    answer["report"] |= {"id": 19, "revision": 1, "stance": "trim"}
    return answer


def test_a_company_with_no_report() -> None:
    """With no report, the Report view draws No report yet. and nothing else: no line, no list,
    no controls and no Request research of the tab's own, which the head has. Records is still
    a view."""
    answer = answers.answer() | {"report": None, "call": None, "reports": []}
    mounted, records = _drive({}, [_mount(answer), _press("app-research__view", RECORDS_VIEW)])
    tree = mounted["tree"]
    assert text(_one(tree, "app-research__none")) == "No report yet."
    for gone in ("app-research__line", "app-research__list", "app-research__marks"):
        assert classed(tree, gone) == [], gone
    assert "Request research" not in text(tree)
    assert "Download .md" not in text(tree)
    assert [text(v) for v in classed(tree, "app-research__view")] == ["Report", RECORDS_VIEW]
    assert text(_one(records["tree"], "app-research__line")) == RECORDS
    assert classed(records["tree"], "app-research__none") == []


def test_download_s_refusal() -> None:
    """Download .md fetches the report's Markdown; a refusal draws one sentence under the bar,
    the server's words in it, and another report of the company draws none."""
    pressed, revision = _drive(
        {},
        [_mount(), _press(*DOWNLOAD), _mount(_report_19(), "land")],
        {MARKDOWN: {"status": 500, "body": {"detail": "the export failed"}}},
    )[1:]
    assert pressed["fetched"] == [["GET", MARKDOWN]]
    error = _one(pressed["tree"], "app-research__error")
    assert text(error) == "The Markdown did not download: the export failed."
    bar = _one(pressed["tree"], "app-research__top")
    assert error in bar["props"]["children"]
    assert classed(revision["tree"], "app-research__error") == []


# --------------------------------------------------------------------------------- the page


def test_the_tab_hangs_on_the_page_s_draw_keyed_on_the_company() -> None:
    """draw.research(answer, detail) is the tab keyed on the company of its answer, so another
    company's answer opens a new one; its scripts load in the page's order."""
    drawn = node("companyPage.draw.research", [answers.ANSWER, page_answers.DETAIL], *SCRIPTS)
    assert drawn["props"]["key"] == "LFOX"
    assert drawn["props"]["answer"] == answers.ANSWER
    assert drawn["props"]["detail"] == page_answers.DETAIL
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("report_parts.js") == scripts.index("charts.js") - 1
    assert scripts.index("company_research.js") == scripts.index("company_research_text.js") + 1


# ------------------------------------------------------------------------- print and the width


def _media(query: str) -> str:
    """The page's one block of rules under ``@media <query>``, on one line."""
    css = _static_file("index.html")
    starts = [m.end() for m in re.finditer(r"(?m)^  @media " + re.escape(query) + r" \{\n", css)]
    assert len(starts) == 1, query
    return " ".join(css[starts[0] : css.index("\n  }\n", starts[0])].split())


def test_print_opens_the_closed_parts_and_closes_those_it_opened() -> None:
    """Print draws the three closed parts open (7.11). A stylesheet cannot open a closed details
    in every browser, so the tab's script does: before the page prints, each of the three that is
    closed opens; after it, those it opened close again, and one the reader had opened stays
    open. The tab listens while it is drawn, its effect adding the two listeners and its cleanup
    taking them away."""
    trace = _drive(
        {},
        [
            _mount(),
            {"do": "listen"},
            _press("app-research__link", "Appendix A"),
            {"do": "event", "name": "beforeprint"},
            {"do": "event", "name": "afterprint"},
            {"do": "event", "name": "beforeprint"},
            {"do": "event", "name": "afterprint"},
            {"do": "unlisten"},
            {"do": "event", "name": "beforeprint"},
        ],
    )
    assert not [step for step in trace if step["threw"]]
    listened, opened, before, after, again, closed, gone, unheard = trace[1:]

    def printing(step: dict[str, Any]) -> list[int]:
        """The count of the window's print listeners at ``step``."""
        return [step["listening"].get(event, 0) for event in ("beforeprint", "afterprint")]

    assert printing(trace[0]) == [0, 0] and printing(listened) == [1, 1]
    assert opened["open"] == {"research-a": True}
    assert before["open"] == {"research-refs": True, "research-a": True, "research-b": True}
    assert after["open"] == {"research-refs": False, "research-a": True, "research-b": False}
    assert again["open"] == before["open"] and closed["open"] == after["open"]
    assert printing(gone) == [0, 0]
    assert unheard["open"] == after["open"]
    research = _static_file("company_research.js")
    assert "React.useEffect(function () { return openForPrint(); }, []);" in research


def test_below_980_px_the_tab_is_one_column() -> None:
    """The Research tab's design, 7.3, 7.4 and 7.11: below 980 px the tab is one column. The
    section list is a row above the report, each of its lists a line that scrolls sideways, the
    reports on file first, in a line under the bar; a name marked by its lower edge. A pair's
    charts stand under its paragraph, as many to a row as fit; Records one column; the panels'
    padding the mockup's. A section's cards and the charts' tracks take no rule of their own
    here: the panel's own width sets the cards beside the text or under it, at every width
    (test_the_cards_stand_beside_the_text_where_the_panel_holds_both), and the one rule of the
    tracks, at least 300px and never wider than the column, and a group's block never wider
    than its row, keep them inside a 400px window (7.9)."""
    block = _media("(width < 980px)")
    for rule in (
        ".app-research__records { grid-template-columns: minmax(0, 1fr); }",
        ".app-research__layout { grid-template-columns: minmax(0, 1fr); gap: var(--space-3); }",
        ".app-research__list { position: static; max-height: none; gap: var(--space-2); }",
        ".app-research__group--files { order: -1; }",
        ".app-research__links, .app-research__files { flex-direction: row; overflow-x: auto; }",
        (
            ".app-research__link, .app-research__file { width: auto; white-space: nowrap;"
            " border-left: 0; border-bottom: 2px solid var(--hairline); }"
        ),
        (
            ".app-research__link.is-on, .app-research__file.is-on {"
            " border-bottom-color: var(--accent); }"
        ),
        ".app-research__pair { display: grid; grid-template-columns: minmax(0, 1fr); }",
        ".app-research__sec, .app-research__panel { padding: var(--space-4); }",
    ):
        assert rule in block, rule
    for name in (
        "app-research__split",
        "app-research__cards",
        "app-research__minis",
        "app-research__groups",
        "app-research__block",
    ):
        assert name not in block, name


def test_the_cards_stand_beside_the_text_where_the_panel_holds_both() -> None:
    """The Research tab's design, 7.4 (the look at a 1,200px window): a section's cards column is
    never under 300px. The first run of text and the cards stand in a row that wraps: the text
    at least 28rem and at most the reading width (43rem), growing to it first, the cards at
    least 300px, taking what is left; where the panel holds both side by side they stand side by
    side, the cards' column staying in view while the panel scrolls, and where it cannot the
    cards wrap under the text across the panel. The panel's own width decides it, not the
    window's: no media rule names the row or the cards (test_below_980_px_the_tab_is_one_column),
    and print stands the cards under the text (test_print_draws_the_report_view_alone)."""
    row = _rule(".app-research__split {", "  ")
    for declaration in ("display: flex;", "flex-wrap: wrap;", "align-items: flex-start;"):
        assert declaration in row, declaration
    assert "grid-template-columns" not in row
    assert _rule(".app-research__split > .app-research__run {") == "flex: 10 1 28rem;"
    assert "max-width: 43rem;" in _rule(".app-research__run {")
    assert _rule(".app-research__split > .app-research__cards {") == "flex: 1 1 300px;"
    cards = _rule(".app-research__cards {", "  ")
    assert "position: sticky;" in cards and "min-width: 0;" in cards


def test_a_pair_s_charts_stand_beside_its_paragraph_where_the_panel_holds_both() -> None:
    """The Research tab's design, 7.4 rule 3 (the scoped check of the look): a pair's charts
    column is never under 300px. Its paragraph keeps its width, 27rem at most, and its charts take
    the rest, at least 300px, in a row that wraps: where the panel holds both side by side they
    stand side by side, and where it cannot the charts stand under the paragraph across the
    panel; the panel's own width decides. Below 980px the pair stacks as before, one column
    (test_below_980_px_the_tab_is_one_column)."""
    pair = _rule(".app-research__pair {", "  ")
    for declaration in ("display: flex;", "flex-wrap: wrap;", "align-items: flex-start;"):
        assert declaration in pair, declaration
    assert "grid-template-columns" not in pair
    assert "border-top: 1px solid var(--hairline);" in pair  # a pair still opens with its rule
    assert _rule(".app-research__pair > .app-research__run {") == "flex: 0 1 27rem;"
    assert _rule(".app-research__pair > .app-research__minis {") == "flex: 1 1 300px;"


def test_print_draws_the_report_view_alone() -> None:
    """The Research tab's design, 7.11: printed where the Research tab is drawn, the head's price,
    its controls and the tabs' row are not, nor the bar's controls or the section list; the
    company's name and ticker and the bar's line are. The report is one column, a section's cards
    under its text, a card and a chart whole on a page, a heading kept with what follows it; an
    agent's table prints whole at the floor of the type scale, as the report page's did
    (``tests/web/test_app.py``, ``test_a_wide_table_prints_whole``). The footnote marks print
    whatever Footnote marks says, since on paper no box shows a cite's source: with the switch
    off, the default, the screen's rule hides them and the print rule shows them, so each number
    in the text points to its reference. The other tabs print as they did: the rule for the head
    names the tab, apart from the tab's own, so a browser that cannot read it still hides the
    tab's controls."""
    block = _media("print")
    # a browser does not break a scroll container across pages: the company panel is no scroll
    # container in print, and runs to its end with no side padding
    assert "section#company { overflow: visible; padding: 0; }" in block
    tab = block[block.index("/* The Research tab") :]
    for rule in (
        (
            ".app-research__views, .app-research__actions, .app-research__list"
            " { display: none !important; }"
        ),
        (
            ".app-company:has(.app-research) :is(.app-company__quote, .app-company__actions,"
            " .app-company__tabs) { display: none !important; }"
        ),
        ".app-research__layout { display: block; }",
        ".app-research__split { display: grid; grid-template-columns: minmax(0, 1fr); }",
        ".app-research__cards { position: static; }",
        ".app-research__card, .app-charts__chart { break-inside: avoid; }",
        (
            ".app-research h2, .app-research h3, .app-research h4,"
            " .app-research__summary { break-after: avoid; }"
        ),
        ".app-research:not(.app-research--marks) .fb-cite__n { display: inline; }",
    ):
        assert rule in tab, rule
    code = re.sub(r"/\*.*?\*/", "", block)
    hidden = "".join(re.findall(r"([^{}]*)\{ display: none !important; \}", code))
    for name in (
        "app-research__line",
        "app-research__currency",
        "app-company__id",
        "app-company__name",
        "ticker",
    ):
        assert name not in hidden, name
