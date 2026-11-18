"""The company page's Investor relations tab (the Investor relations tab's design, 7.1 to 7.8 and
9): the fourth of the five tabs; one block the page's width, at its top the switch of the tab's
two views, Earnings calls and Filings, and at the row's right end the line of the next earnings
report; under it the view the address's word names, the Filings view for ``filings``, else the
Earnings calls view. A view draws its sentence for a company with nothing on file.

The Earnings calls view: at its left the list of calls under their fiscal years' heads, newest
first, five years unless all are asked for, the call shown marked; at its right the reader of
that call, its title, its date, its four figures and its transcript, read once a call through
the call's read with the request header and kept for the page's life, with the find box and the
button to the questions. The Filings view: five filters, each with its count, then the table of
the filings the filter keeps, each row its day, its form, the form's plain words and its links
to the SEC's site, in a box of its own that scrolls sideways; under it the line of the windows
read and Show older filings, which reads one year more through the filings read with the
request header and adds its rows under the table's, the windows kept by company for the page's
life. The data date of the tabs' row is the view's: on Earnings calls the read's alone, on
Filings the oldest of the read's and the days of the filing lists read.

company.js and company_investor.js run in node after the bundle and app.js (``support.page``),
and the tests read the trees their builders return; ``investor.mjs`` drives the view's state, its
reads answered when a step says, its presses and the words typed; how the page loads the tab, its
addresses and a press of the switch, which never reads the tab again, run in
``tests/web/test_company_load.py``. The rules node cannot run are read from the page's CSS.

The company is ``page_answers``' LFOX: five calls on file, the newest Q3 2026's, a filing list of
the year to 1 Nov 2026 stored on 2 Nov 2026, its data date 14 Nov 2026 and its next earnings
report 14 Jan 2027; its call is ``page_payloads``' invented Q3 2026 call. Every company, figure
and word is invented."""

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from support import page_answers as answers
from support import page_payloads as pages
from support.page import BUNDLE, NODE, STATIC, classed, elements, node, text
from support.web import _static_file

from fairband.vendors import page_investor
from fairband.web.filings_api import OWNERSHIP_FORMS

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (STATIC / "company.js", STATIC / "company_investor.js")
DRIVER = Path(__file__).parent / "investor.mjs"
TAB = "investor-relations"
NO_CALL = "No earnings call on file."
NO_FILING = "No filing on file."
NO_WORDS = "No transcript on file for this call."
HEADER = {"X-Fairband-Request": "1"}


def _draw(answer: dict[str, Any], word: str | None = None) -> Any:
    """The tab ``draw['investor-relations']`` draws on ``answer`` and LFOX's detail, at the
    address's word ``word`` (``2026Q4``, ``filings``), none for the tab alone."""
    return node(f"companyPage.draw.{TAB}", [answer, answers.DETAIL, word], *SCRIPTS)


def _switch(tree: Any) -> list[tuple[str, str]]:
    """Each button of the switch: its words and whether it is selected."""
    [switch] = classed(tree, "app-fin__seg")
    return [
        (text(button), button["props"]["aria-selected"])
        for button in classed(switch, "app-ir__view")
    ]


def _line(tree: Any) -> str | None:
    """The line of the next earnings report, none where it is left out."""
    found = classed(tree, "app-ir__next")
    assert len(found) <= 1
    return text(found[0]) if found else None


def _sentences(tree: Any) -> list[str]:
    return [text(e) for e in classed(tree, "app-ir__none")]


# ------------------------------------------------------------------------------------ the row


def test_investor_relations_is_the_fourth_of_five_tabs() -> None:
    """The tabs' row reads Overview, Financials, Estimates, Investor relations, Research (7.1),
    the open one selected, each a button, the data date at the row's right end."""
    tree = node("companyPage.tabs", ["LFOX", TAB, "2026-11-14"], *SCRIPTS)
    tabs = classed(tree, "app-company__tab")
    assert [text(t) for t in tabs] == [
        "Overview",
        "Financials",
        "Estimates",
        "Investor relations",
        "Research",
    ]
    assert [t["props"]["aria-selected"] for t in tabs] == ["false"] * 3 + ["true", "false"]
    assert {t["type"] for t in tabs} == {"button"}
    [asof] = classed(tree, "app-company__asof")
    assert text(asof) == "data 14 Nov 2026"
    script = _static_file("company.js")
    found = re.search(r"\n  var TABS = \[(.*?)\];\n", script, re.DOTALL)
    assert found is not None
    assert "['investor-relations', 'Investor relations']" in found.group(1)
    js = _static_file("controls.js")
    assert (
        "\n  var COMPANY_TABS = "
        "['overview', 'financials', 'estimates', 'investor-relations', 'research'];\n"
    ) in js


# ----------------------------------------------------------------------- the switch and the line


def test_the_block_its_switch_and_the_line() -> None:
    """One block the page's width (7.2), a panel as Financials' is: at its top a row, the switch
    of the two views at its left, drawn as the Financials tab's switch of statements, Earnings
    calls selected on the tab alone; at the row's right end the line of the next earnings
    report, the read's day in the page's words."""
    tree = _draw(answers.investor())
    assert tree["type"] == "section"
    assert tree["props"]["className"] == "app-company__panel app-ir"
    assert tree["props"]["aria-label"] == "Investor relations"
    bar = tree["props"]["children"][0]
    assert bar["type"] == "div" and bar["props"]["className"] == "app-ir__bar"
    [switch] = classed(bar, "app-fin__seg")
    assert switch["props"]["role"] == "tablist"
    assert _switch(tree) == [("Earnings calls", "true"), ("Filings", "false")]
    for button in classed(switch, "app-ir__view"):
        assert button["type"] == "button"
        assert button["props"]["type"] == "button"
        assert button["props"]["role"] == "tab"
        assert button["props"]["className"] == "control app-ir__view"
    assert _line(tree) == "Next earnings report 14 Jan 2027"
    [line] = classed(bar, "app-ir__next")
    assert line["type"] == "p" and line["props"]["className"] == "body app-ir__next"
    [day] = classed(line, "app-ir__day")
    assert text(day) == "14 Jan 2027"
    found = list(elements(bar))
    assert found.index(switch) < found.index(line)


@pytest.mark.parametrize(
    ("day", "line"),
    [
        ("2027-02-04", "Next earnings report 4 Feb 2027"),
        ("2026-11-19", "Next earnings report 19 Nov 2026"),
        (None, None),
    ],
)
def test_the_line_is_left_out_without_a_day(day: str | None, line: str | None) -> None:
    """The line reads the read's ``nextEarnings``, the day the Estimates tab reads from the same
    stored rows; where they hold no coming date the line is left out, on either view."""
    answer = answers.investor() | {"nextEarnings": day}
    for word in (None, "filings"):
        assert _line(_draw(answer, word)) == line


@pytest.mark.parametrize(
    ("word", "view"),
    [
        (None, "Earnings calls"),
        ("2026Q4", "Earnings calls"),
        ("2026Q3", "Earnings calls"),
        ("filings", "Filings"),
    ],
)
def test_the_view_is_the_address_s(word: str | None, view: str) -> None:
    """The view the address's word names: the Filings view for ``filings``, else the Earnings
    calls view, on the tab alone or on a call (``2026Q4``); its button selected."""
    assert [name for name, on in _switch(_draw(answers.investor(), word)) if on == "true"] == [view]
    assert node("investor.view", [word], *SCRIPTS) == ("filings" if view == "Filings" else "calls")


# ----------------------------------------------------------------------------------- the views


def test_a_company_with_a_profile_and_nothing_else_draws_its_two_sentences() -> None:
    """Review Focus 2: the read answers ``calls`` empty and ``filings`` null. The Earnings calls
    view draws "No earnings call on file." and the Filings view "No filing on file.", each alone
    under the row, and neither throws; no line without a next date."""
    empty = answers.profile_only_investor()
    for word in (None, "2026Q4"):
        calls = _draw(empty, word)
        assert _sentences(calls) == [NO_CALL]
        assert _switch(calls) == [("Earnings calls", "true"), ("Filings", "false")]
        assert _line(calls) is None
    filings = _draw(empty, "filings")
    assert _sentences(filings) == [NO_FILING]
    assert _switch(filings) == [("Earnings calls", "false"), ("Filings", "true")]
    [sentence] = classed(filings, "app-ir__none")
    assert sentence["type"] == "p" and sentence["props"]["className"] == "body app-ir__none"
    assert len(filings["props"]["children"]) == 2  # the row and the view's sentence


def test_a_view_with_data_draws_no_sentence() -> None:
    """A company with calls draws its list and its reader on the Earnings calls view, and one
    with a filing list its filters and its table on the Filings view; neither draws a sentence.
    A first window with no filing in it is no filing on file."""
    full = answers.investor()
    for word in (None, "2026Q3"):
        tree = _draw(full, word)
        assert _sentences(tree) == []
        assert tree["props"]["children"][1]["props"]["className"] == "app-ir__calls"
    filings = _draw(full, "filings")
    assert _sentences(filings) == []
    assert filings["props"]["children"][1]["props"]["className"] == "app-ir__filings"
    calls_only = answers.investor() | {"filings": None}
    assert _sentences(_draw(calls_only)) == []
    assert _sentences(_draw(calls_only, "filings")) == [NO_FILING]
    empty_window = answers.investor()
    empty_window["filings"]["rows"] = []
    assert _sentences(_draw(empty_window, "filings")) == [NO_FILING]
    filings_only = answers.investor() | {"calls": []}
    assert _sentences(_draw(filings_only)) == [NO_CALL]
    assert _sentences(_draw(filings_only, "filings")) == []


# ------------------------------------------------------------------------- the pure pieces (7.4)


@pytest.mark.parametrize(
    ("paragraph", "words", "parts", "hits"),
    [
        ("Up $1.5 billion (net).", "$1.5", ["Up ", "$1.5", " billion (net)."], 1),
        ("Up $1.5 billion (net).", "(net)", ["Up $1.5 billion ", "(net)", "."], 1),
        ("a.b axb", "a.b", ["a.b", " axb"], 1),
        ("Why? Because.", "y?", ["Wh", "y?", " Because."], 1),
        ("a (( b", "((", ["a ", "((", " b"], 1),
        ("one \\\\ two", "\\\\", ["one ", "\\\\", " two"], 1),
        ("Sensors and a SENSOR line.", "sensor", ["", "Sensor", "s and a ", "SENSOR", " line."], 2),
        ("aaaa", "aa", ["aa", "aa"], 2),
        ("Up $1.5 billion.", ".*", ["Up $1.5 billion."], 0),
        ("Up $1.5 billion.", "  1.5  ", ["Up $", "1.5", " billion."], 1),
        ("a.b axb", "a", ["a.b axb"], 0),
        ("Why?", "?", ["Why?"], 0),
        ("Up (net)", "(", ["Up (net)"], 0),
        ("one \\ two", "\\", ["one \\ two"], 0),
        ("one two", " o ", ["one two"], 0),
        ("one two", "", ["one two"], 0),
        ("İstanbul and istanbul", "is", ["İstanbul and ", "is", "tanbul"], 1),
    ],
)
def test_the_find_box_marks_plain_words_from_two_characters(
    paragraph: str, words: str, parts: list[str], hits: int
) -> None:
    """Review Focus 5: ``marked`` finds the typed words in a paragraph as plain words, whatever
    the case, never as a pattern: ``$1.5``, ``(``, ``?``, ``a.b`` and a backslash are their own
    characters. The words are taken with their outer spaces off; under two characters they mark
    nothing. Its parts, in order, are the paragraph's text cut at each place found, each part
    found a hit, and they join to the paragraph whole; the hits are counted, none overlapping. A
    letter whose lower case is longer (``İ``) shifts no place found."""
    found = node("investor.marked", [paragraph, words], *SCRIPTS)
    want = [p for p in parts if p]
    assert [p["text"] for p in found["parts"]] == want
    assert "".join(p["text"] for p in found["parts"]) == paragraph
    assert [p["hit"] for p in found["parts"]].count(True) == hits == found["hits"]
    lowered = words.strip().lower()
    assert all(p["text"].lower() == lowered for p in found["parts"] if p["hit"])


def _calls(years: int) -> list[dict[str, Any]]:
    """Calls of ``years`` fiscal years, newest first, four a year from 2026 back and one more,
    Q4 of the year before them: 85 calls over 22 years for 21. No figures on file for any."""
    found = [
        {"fiscalYear": year, "quarter": quarter, "date": f"{year}-{3 * quarter:02d}-20"}
        for year in range(2026, 2026 - years, -1)
        for quarter in (4, 3, 2, 1)
    ]
    found.append({"fiscalYear": 2026 - years, "quarter": 4, "date": f"{2026 - years}-12-20"})
    figures = ("epsReported", "epsEstimate", "revenueReported", "revenueEstimate")
    return [call | dict.fromkeys(figures) for call in found]


def test_the_list_s_years_are_the_newest_five_unless_all_are_asked_for() -> None:
    """``years`` groups the calls under their fiscal years, in the order the calls stand,
    newest first: the newest five years, or every year where all are asked for."""
    calls = _calls(21)
    five = node("investor.years", [calls, False], *SCRIPTS)
    assert [y["year"] for y in five] == [2026, 2025, 2024, 2023, 2022]
    assert [len(y["calls"]) for y in five] == [4] * 5
    assert five[0]["calls"] == calls[:4]
    every = node("investor.years", [calls, True], *SCRIPTS)
    assert [y["year"] for y in every] == list(range(2026, 2004, -1))
    assert sum(len(y["calls"]) for y in every) == 85
    lfox = node("investor.years", [answers.INVESTOR["calls"], False], *SCRIPTS)
    assert [(y["year"], [c["quarter"] for c in y["calls"]]) for y in lfox] == [
        (2026, [3, 2, 1]),
        (2025, [4, 3]),
    ]
    assert node("investor.years", [[], False], *SCRIPTS) == []


def test_a_call_s_title() -> None:
    """The reader's title, ``Q<n> fiscal <year> earnings call``."""
    call = answers.INVESTOR["calls"][0]
    assert node("investor.title", [call], *SCRIPTS) == "Q3 fiscal 2026 earnings call"
    q4 = call | {"fiscalYear": 2025, "quarter": 4}
    assert node("investor.title", [q4], *SCRIPTS) == "Q4 fiscal 2025 earnings call"


# ------------------------------------------------------------------------- the list of calls (7.3)


def _list(tree: Any) -> list[tuple[str, list[tuple[str, str | None]]]]:
    """The list of calls: each fiscal year's head and its rows, each row's words and whether it
    is the call shown (``aria-current``)."""
    [found] = classed(tree, "app-ir__list")
    groups: list[tuple[str, list[tuple[str, str | None]]]] = []
    for e in elements(found):
        names = str(e["props"].get("className") or "").split()
        if "app-ir__year" in names:
            groups.append((text(e), []))
        elif "app-ir__call" in names:
            groups[-1][1].append((text(e), e["props"].get("aria-current")))
    return groups


def _all_button(tree: Any) -> list[str]:
    return [text(e) for e in classed(tree, "app-ir__all")]


LFOX_LIST = [
    ("Fiscal 2026", [("Q315 Oct 2026", "true"), ("Q216 Jul 2026", None), ("Q116 Apr 2026", None)]),
    ("Fiscal 2025", [("Q415 Jan 2026", None), ("Q316 Oct 2025", None)]),
]


def test_the_list_of_calls_by_fiscal_year_the_call_shown_marked() -> None:
    """At the view's left (7.3), the calls on file under one head a fiscal year (``Fiscal
    2026``), newest first, each row the quarter and the call's day, a button; on the tab alone
    the newest is shown and marked, on a call's word that call. Two years: no Show all."""
    tree = _draw(answers.investor())
    assert _list(tree) == LFOX_LIST
    [nav] = classed(tree, "app-ir__list")
    assert nav["type"] == "nav"
    for row in classed(nav, "app-ir__call"):
        assert row["type"] == "button" and row["props"]["type"] == "button"
        assert row["props"]["className"] == "control app-ir__call"
        [quarter] = classed(row, "app-ir__q")
        [day] = classed(row, "app-ir__date")
        assert day["props"]["className"] == "figure-sm app-ir__date"
        assert text(quarter) + text(day) == text(row)
    for head in classed(nav, "app-ir__year"):
        assert head["type"] == "h3" and head["props"]["className"] == "label app-ir__year"
    assert _all_button(tree) == []
    q2 = _list(_draw(answers.investor(), "2026Q2"))
    assert [row for _, rows in q2 for row in rows if row[1] == "true"] == [
        ("Q216 Jul 2026", "true")
    ]
    older = _list(_draw(answers.investor(), "2025Q3"))
    assert [row for _, rows in older for row in rows if row[1]] == [("Q316 Oct 2025", "true")]


def test_the_list_shows_five_fiscal_years_then_show_all() -> None:
    """The newest five fiscal years, and under them **Show all 85 calls**, where there are more;
    none at five years or fewer. A call's word of an older year shows every year, so the call
    shown stands in the list, marked."""
    many = answers.investor() | {"calls": _calls(21)}
    tree = _draw(many)
    found = _list(tree)
    assert [head for head, _ in found] == [f"Fiscal {y}" for y in range(2026, 2021, -1)]
    assert sum(len(rows) for _, rows in found) == 20
    assert _all_button(tree) == ["Show all 85 calls"]
    five = answers.investor() | {"calls": _calls(4)}
    assert len(_list(_draw(five))) == 5 and _all_button(_draw(five)) == []
    old = _draw(many, "2010Q2")
    assert len(_list(old)) == 22 and _all_button(old) == []
    marked = [row for _, rows in _list(old) for row in rows if row[1]]
    assert marked == [("Q220 Jun 2010", "true")]


# ------------------------------------------------------------------------------ the reader (7.4)


def _reader(tree: Any) -> dict[str, Any]:
    [found] = classed(tree, "app-ir__reader")
    return found


def _figures(tree: Any) -> list[tuple[str, str]]:
    """The reader's figures: each name and its figure, in order."""
    return [
        (text(classed(f, "app-ir__name")[0]), text(classed(f, "app-ir__amount")[0]))
        for f in classed(tree, "app-ir__figure")
    ]


def test_the_reader_s_title_date_and_four_figures() -> None:
    """At the list's right (7.4), the call shown: its title, its day under it, then its four
    figures in a row, each its name over its figure, EPS to cents and revenue compact in US
    dollars as the Estimates tab writes them, a missing one the dash. No gap to the estimate."""
    tree = _draw(answers.investor(), "2026Q2")
    reader = _reader(tree)
    assert reader["type"] == "article"
    [title] = classed(reader, "app-ir__title")
    assert title["type"] == "h2" and title["props"]["className"] == "heading app-ir__title"
    assert text(title) == "Q2 fiscal 2026 earnings call"
    assert text(classed(reader, "app-ir__when")[0]) == "16 Jul 2026"
    assert _figures(reader) == [
        ("EPS reported", "$1.97"),
        ("EPS estimate", "$1.90"),
        ("Revenue reported", "$26.71B"),
        ("Revenue estimate", "$26.05B"),
    ]
    for f in classed(reader, "app-ir__figure"):
        assert classed(f, "app-ir__name")[0]["props"]["className"] == "label app-ir__name"
        assert classed(f, "app-ir__amount")[0]["props"]["className"] == "figure app-ir__amount"
    newest = _reader(_draw(answers.investor()))
    assert text(classed(newest, "app-ir__title")[0]) == "Q3 fiscal 2026 earnings call"
    assert _figures(newest) == [
        ("EPS reported", "—"),
        ("EPS estimate", "$2.05"),
        ("Revenue reported", "—"),
        ("Revenue estimate", "$27.30B"),
    ]


def test_a_call_with_no_figure_on_file_has_no_figures_row() -> None:
    """A call no stored earnings row is the call's (its four figures null) has no figures row:
    its title and its day alone."""
    reader = _reader(_draw(answers.investor(), "2025Q3"))
    assert text(classed(reader, "app-ir__title")[0]) == "Q3 fiscal 2025 earnings call"
    assert classed(reader, "app-ir__figures") == [] and _figures(reader) == []


def test_no_gap_to_the_estimate_and_no_colour_of_a_rise_or_a_fall() -> None:
    """The mockup's ``+3.0% against the estimate``, in a colour, is left out (7.4): no element
    holds a percent or those words, and no class names a rise or a fall."""
    for word in (None, "2026Q2", "2026Q1", "2025Q4"):
        tree = _draw(answers.investor(), word)
        words = text(tree)
        assert "%" not in words and "against" not in words and "surprise" not in words
        for e in elements(tree):
            names = str(e["props"].get("className") or "")
            assert not re.search(r"\b(up|down|pos|neg|gain|loss|rise|fall)\b", names), names


# ------------------------------------------------------------------------ the view's state, in node

LFOX = "/api/companies/LFOX"
OTHER = "/api/companies/OTHR"


def _url(year: int, quarter: int, company: str = LFOX) -> str:
    """The call's read of ``company``'s call of ``year`` and ``quarter``."""
    return f"{company}/page/investor-relations/call?year={year}&quarter={quarter}"


Q3 = _url(2026, 3)
Q2 = _url(2026, 2)
Q1 = _url(2026, 1)


def _transcript(year: int = 2026, quarter: int = 3, **changes: Any) -> dict[str, Any]:
    """The call's read's answer for LFOX's call of ``year`` and ``quarter``, as the server gives
    it: ``page_payloads``' invented call read by the server's reader, its five turns, the
    questions from the third; its copy fetched on 16 Oct 2026; with ``changes``."""
    return {
        "symbol": "LFOX",
        "fiscalYear": year,
        "quarter": quarter,
        **page_investor.transcript(pages.TRANSCRIPT),
        "observedDay": "2026-10-16",
    } | changes


def _drive(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The trace of ``steps``: one entry for each, as ``investor.mjs`` gives it."""
    assert NODE is not None
    scripts = (BUNDLE, STATIC / "app.js", *SCRIPTS)
    done = subprocess.run(
        [NODE, str(DRIVER), *(str(script) for script in scripts)],
        input=json.dumps(steps),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr
    trace: list[dict[str, Any]] = json.loads(done.stdout)
    return trace


def _shown(answer: dict[str, Any] | None = None, word: str | None = None) -> dict[str, Any]:
    """The page draws the tab on ``answer``, LFOX's unless given, at ``word``."""
    return {
        "do": "draw",
        "answer": answers.investor() if answer is None else answer,
        "detail": answers.DETAIL,
        "word": word,
    }


def _answer(url: str, body: Any, status: int = 200) -> dict[str, Any]:
    return {"do": "answer", "url": url, "status": status, "body": body}


def _row(words: str) -> dict[str, Any]:
    """The list's row that reads ``words`` (its quarter and its day) is pressed."""
    return {"do": "press", "class": "app-ir__call", "text": words}


def _type(words: str) -> dict[str, Any]:
    return {"do": "type", "words": words}


def _get(*urls: str) -> list[list[str]]:
    return [["GET", url] for url in urls]


def _busy(tree: Any) -> bool:
    """Whether the reader waits on its call's read."""
    return _reader(tree)["props"].get("aria-busy") == "true"


def _turns(tree: Any) -> list[dict[str, Any]]:
    return classed(tree, "app-ir__turn")


def _speakers(tree: Any) -> list[str | None]:
    """Each turn's speaker's name, none for a turn drawn with no name."""
    return [
        text(names[0]) if (names := classed(turn, "app-ir__who")) else None for turn in _turns(tree)
    ]


def _count(tree: Any) -> str:
    [count] = classed(tree, "app-ir__count")
    return text(count)


def _flat(children: Any) -> list[Any]:
    """An element's children as one list: its texts and its elements, in order."""
    if isinstance(children, list):
        return [part for child in children for part in _flat(child)]
    return [] if children is None else [children]


def _marks(tree: Any) -> list[str]:
    """The words marked in the transcript, each a mark element around its text."""
    return [text(e) for e in elements(tree) if e["type"] == "mark"]


def test_the_newest_call_is_read_as_the_tab_opens_and_each_call_once() -> None:
    """Review Focus 4: the view opens on the newest call and reads its transcript once, through
    the call's read with the request header; drawn again, it reads nothing. A press on a row
    replaces the address with that call's (FairbandPage.show, so companyPath writes it) and reads
    that call, once: a call read before is drawn from what the page keeps, at once."""
    trace = _drive(
        [
            _shown(),
            _shown(),
            _answer(Q3, _transcript()),
            _row("Q216 Jul 2026"),
            _row("Q315 Oct 2026"),
            _answer(Q2, _transcript(quarter=2)),
            _row("Q216 Jul 2026"),
            _row("Q116 Apr 2026"),
        ]
    )
    opened, again, landed, q2, q3, late, back, q1 = trace
    assert opened["fetched"] == _get(Q3) and opened["headers"] == [HEADER]
    assert opened["inFlight"] == [Q3] and _busy(opened["tree"])
    assert again["fetched"] == [] and again["inFlight"] == [Q3]
    assert landed["redrawn"] == 1 and not _busy(landed["tree"])
    assert len(_turns(landed["tree"])) == 5
    assert q2["shows"] == [["company", "LFOX", TAB, "2026Q2"]]
    assert q2["fetched"] == _get(Q2) and q2["headers"] == [HEADER]
    assert _busy(q2["tree"])
    assert q3["shows"] == [["company", "LFOX", TAB, "2026Q3"]]
    assert q3["fetched"] == [] and not _busy(q3["tree"])
    assert late["redrawn"] == 0
    assert back["fetched"] == [] and not _busy(back["tree"])
    assert text(classed(back["tree"], "app-ir__title")[0]) == "Q2 fiscal 2026 earnings call"
    assert q1["fetched"] == _get(Q1) and q1["inFlight"] == [Q1]


def test_the_transcript_one_block_a_turn() -> None:
    """The transcript (7.4) at the reading width: one block a turn, the speaker's name over the
    turn's words, in the paragraphs the server gave, each a paragraph of its own; the first turn
    of the questions carries the label Questions and answers over it, a heavier rule and the id
    the button goes to. The find box and Go to the questions stand over it."""
    [*_, landed] = _drive([_shown(), _answer(Q3, _transcript())])
    tree = landed["tree"]
    reader = _reader(tree)
    assert _speakers(tree) == [
        "Operator",
        "Mara Vellini",
        "Operator",
        "Ines Dalgaard",
        "Mara Vellini",
    ]
    turns = _turns(tree)
    [words] = classed(turns[1], "app-ir__words")
    assert words["type"] == "p" and text(words) == (
        "Thank you. Car makers took more of our sensors than we planned. "
        "The fourth line at the sensor plant starts next year."
    )
    assert [t["props"].get("id") for t in turns] == [None, None, "ir-questions", None, None]
    assert [t["props"]["className"] for t in turns] == ["app-ir__turn"] * 2 + [
        "app-ir__turn app-ir__turn--questions"
    ] + ["app-ir__turn"] * 2
    [label] = classed(reader, "app-ir__part")
    assert text(label) == "Questions and answers"
    assert list(elements(turns[2])).index(label) < list(elements(turns[2])).index(
        classed(turns[2], "app-ir__who")[0]
    )
    [box] = classed(tree, "app-ir__find")
    assert box["type"] == "input" and box["props"]["type"] == "search"
    assert box["props"]["placeholder"] == "Find in this call"
    assert box["props"]["aria-label"] == "Find in this call"
    assert box["props"]["value"] == ""
    assert [text(b) for b in classed(tree, "app-ir__go")] == ["Go to the questions"]
    assert classed(reader, "app-ir__who--operator") == classed(turns[0], "app-ir__who") + (
        classed(turns[2], "app-ir__who")
    )
    found = list(elements(reader))
    assert found.index(classed(reader, "app-ir__tools")[0]) < found.index(turns[0])
    assert "dangerouslySetInnerHTML" not in json.dumps(tree)


def test_go_to_the_questions_takes_the_reader_to_their_first_turn() -> None:
    """Go to the questions scrolls the questions' first turn into view, at the top."""
    [*_, pressed] = _drive(
        [
            _shown(),
            _answer(Q3, _transcript()),
            {"do": "press", "class": "app-ir__go", "text": "Go to the questions"},
        ]
    )
    assert pressed["scrolled"] == [["ir-questions", {"behavior": "smooth", "block": "start"}]]
    assert pressed["fetched"] == []


@pytest.mark.parametrize("start", [None, 2])
def test_no_button_and_no_label_where_the_questions_start_is_not_known(start: int | None) -> None:
    """A call whose questions' start the server did not find (``questionsAt`` null), or names
    no turn of it, has no button and no label; a turn with no name (``speaker`` null) is drawn
    with no name."""
    turns = [
        {"speaker": None, "paragraphs": ["Opening words.", "More opening words."]},
        {"speaker": "Ada Park", "paragraphs": ["Good day."]},
    ]
    [*_, landed] = _drive([_shown(), _answer(Q3, _transcript(turns=turns, questionsAt=start))])
    tree = landed["tree"]
    assert classed(tree, "app-ir__go") == [] and classed(tree, "app-ir__part") == []
    assert classed(tree, "app-ir__turn--questions") == []
    assert _speakers(tree) == [None, "Ada Park"]
    first = _turns(tree)[0]
    assert [text(p) for p in classed(first, "app-ir__words")] == [
        "Opening words.",
        "More opening words.",
    ]
    assert len(classed(tree, "app-ir__find")) == 1


def test_a_call_with_no_words_on_file_draws_its_sentence() -> None:
    """A call the vendor holds no words for (``turns`` empty) draws its title, its day and its
    figures, and "No transcript on file for this call.": no find box and no button."""
    [*_, landed] = _drive([_shown(None, "2026Q2"), _answer(Q2, _transcript(quarter=2, turns=[]))])
    reader = _reader(landed["tree"])
    assert text(classed(reader, "app-ir__title")[0]) == "Q2 fiscal 2026 earnings call"
    assert len(_figures(reader)) == 4
    assert _sentences(reader) == [NO_WORDS]
    assert classed(reader, "app-ir__find") == [] and classed(reader, "app-ir__go") == []
    assert _turns(reader) == [] and not _busy(landed["tree"])


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (503, {"detail": "no FMP key"}, "no FMP key"),
        (502, {"detail": "FMP answered 500"}, "FMP answered 500"),
        (
            502,
            {"detail": "FMP answered no transcript for LFOX"},
            "FMP answered no transcript for LFOX",
        ),
        (503, None, "the server answered 503"),
    ],
)
def test_a_transcript_that_cannot_be_read_draws_its_sentence(
    status: int, body: Any, reason: str
) -> None:
    """A call's read the server refuses (7.4, 7.6) draws the title, the day, the figures and
    "The transcript could not be read: <reason>.", the reason the server's sentence; the list
    stays. A press on the call's row reads it again."""
    trace = _drive(
        [
            _shown(None, "2026Q2"),
            _answer(Q2, body, status),
            _row("Q216 Jul 2026"),
            _answer(Q2, _transcript(quarter=2)),
        ]
    )
    _, failed, again, landed = trace
    reader = _reader(failed["tree"])
    assert _sentences(reader) == [f"The transcript could not be read: {reason}."]
    assert text(classed(reader, "app-ir__title")[0]) == "Q2 fiscal 2026 earnings call"
    assert len(_figures(reader)) == 4 and not _busy(failed["tree"])
    assert _list(failed["tree"]) == [
        (head, [(words, "true" if words.startswith("Q216") else None) for words, _ in rows])
        for head, rows in LFOX_LIST
    ]
    assert failed["asOf"] == "2026-11-14"
    assert again["fetched"] == _get(Q2) and again["shows"] == []
    assert _sentences(landed["tree"]) == [] and len(_turns(landed["tree"])) == 5


def test_a_read_that_fails_on_the_network_draws_its_sentence() -> None:
    [_, failed] = _drive([_shown(), {"do": "fail", "url": Q3, "message": "Failed to fetch"}])
    assert _sentences(failed["tree"]) == ["The transcript could not be read: Failed to fetch."]


def test_a_late_answer_of_another_call_or_another_company_draws_nothing() -> None:
    """Review Focus 4: the reader selects a second call while the first's read is out: the first
    lands late and draws nothing, the reader still waiting on the second, the list as it was.
    Another company drawn while a call's read is out: that read lands late and draws nothing.
    What landed late is kept, so coming back to it reads nothing."""
    other = answers.investor() | {"symbol": "OTHR"}
    other_q3 = _url(2026, 3, OTHER)
    trace = _drive(
        [
            _shown(),
            _row("Q216 Jul 2026"),
            _answer(Q3, _transcript()),
            _answer(Q2, _transcript(quarter=2)),
            _row("Q116 Apr 2026"),
            _shown(other),
            _answer(Q1, _transcript(quarter=1)),
            _answer(other_q3, _transcript(symbol="OTHR")),
            _shown(None, "2026Q1"),
        ]
    )
    _, q2, late, landed, q1, opened, late_other, landed_other, back = trace
    assert late["redrawn"] == 0 and late["tree"] == q2["tree"] and _busy(late["tree"])
    assert landed["redrawn"] == 1 and not _busy(landed["tree"])
    assert q1["fetched"] == _get(Q1) and q1["inFlight"] == [Q1]
    assert opened["fetched"] == _get(other_q3) and _busy(opened["tree"])
    assert late_other["redrawn"] == 0 and late_other["tree"] == opened["tree"]
    assert landed_other["redrawn"] == 1 and not _busy(landed_other["tree"])
    assert back["fetched"] == [] and not _busy(back["tree"])
    assert text(classed(back["tree"], "app-ir__title")[0]) == "Q1 fiscal 2026 earnings call"


def test_the_find_box_marks_and_counts() -> None:
    """The find box (7.4) marks every place its words stand in the transcript's paragraphs,
    whatever the case, from two characters on, each a mark element around its text, and writes
    the count beside it: 3 matches, 1 match, 0 matches; none under two characters and none
    emptied, the marks gone. The box shows the words typed."""
    trace = _drive(
        [
            _shown(),
            _answer(Q3, _transcript()),
            _type("sensor"),
            _type("SENSOR"),
            _type("Ines"),
            _type("cobalt"),
            _type("s"),
            _type(""),
        ]
    )
    landed, sensor, upper, ines, none, one, empty = trace[1:]
    assert _count(landed["tree"]) == "" and _marks(landed["tree"]) == []
    assert _count(sensor["tree"]) == "3 matches"
    assert _marks(sensor["tree"]) == ["sensor", "sensor", "sensor"]
    assert classed(sensor["tree"], "app-ir__find")[0]["props"]["value"] == "sensor"
    assert sensor["redrawn"] == 1 and sensor["fetched"] == []
    assert _count(upper["tree"]) == "3 matches" and _marks(upper["tree"]) == ["sensor"] * 3
    assert _count(ines["tree"]) == "1 match" and _marks(ines["tree"]) == ["Ines"]
    assert _count(none["tree"]) == "0 matches" and _marks(none["tree"]) == []
    for step in (one, empty):
        assert _count(step["tree"]) == "" and _marks(step["tree"]) == []
    [words] = classed(_turns(sensor["tree"])[1], "app-ir__words")
    parts = _flat(words["props"]["children"])
    assert [p if isinstance(p, str) else ("mark", p["props"]["children"]) for p in parts] == [
        "Thank you. Car makers took more of our ",
        ("mark", ["sensor"]),
        "s than we planned. The fourth line at the ",
        ("mark", ["sensor"]),
        " plant starts next year.",
    ]


def test_the_find_box_takes_a_pattern_s_characters_as_plain_words() -> None:
    """Review Focus 5: ``$1.5``, ``(``, ``?``, ``a.b`` and a lone backslash typed in the box are
    plain words: the two-character ones find themselves, the one-character ones mark nothing,
    and none throws."""
    turns = [{"speaker": "Ada Park", "paragraphs": ["Up $1.5 billion (net). Why? a.b axb a\\b"]}]
    words = ["$1.5", "(", "?", "a.b", "\\", "(net)", "y?", "a\\b", ".*", "(("]
    trace = _drive(
        [
            _shown(),
            _answer(Q3, _transcript(turns=turns, questionsAt=None)),
            *(_type(w) for w in words),
        ]
    )
    found = {w: (_count(s["tree"]), _marks(s["tree"])) for w, s in zip(words, trace[2:])}
    assert found == {
        "$1.5": ("1 match", ["$1.5"]),
        "(": ("", []),
        "?": ("", []),
        "a.b": ("1 match", ["a.b"]),
        "\\": ("", []),
        "(net)": ("1 match", ["(net)"]),
        "y?": ("1 match", ["y?"]),
        "a\\b": ("1 match", ["a\\b"]),
        ".*": ("0 matches", []),
        "((": ("0 matches", []),
    }


def test_a_change_of_call_takes_the_page_to_its_top_and_empties_the_find_box() -> None:
    """A change of call, by a press or the address, takes the page to its top, as a change of
    report does on the Research tab, and empties the find box; a draw of the same call keeps the
    reader's place and its words, and so does a call's read landing."""
    trace = _drive(
        [
            _shown(),
            _answer(Q3, _transcript()),
            _type("sensor"),
            {"do": "scroll", "top": 600},
            _shown(),
            _row("Q216 Jul 2026"),
            {"do": "scroll", "top": 400},
            _answer(Q2, _transcript(quarter=2)),
            _shown(None, "2026Q1"),
        ]
    )
    same, pressed, scrolled, landed, linked = trace[4:]
    assert same["scrollTop"] == 600 and _count(same["tree"]) == "3 matches"
    assert pressed["scrollTop"] == 0
    assert scrolled["scrollTop"] == 400
    assert landed["scrollTop"] == 400
    assert classed(landed["tree"], "app-ir__find")[0]["props"]["value"] == ""
    assert _marks(landed["tree"]) == [] and _count(landed["tree"]) == ""
    assert linked["scrollTop"] == 0


def test_show_all_draws_every_year() -> None:
    """Show all 85 calls draws every fiscal year, and goes; the list keeps every year while the
    reader moves between calls, and another company's opens on five."""
    many = answers.investor() | {"calls": _calls(21)}
    other = many | {"symbol": "OTHR"}
    trace = _drive(
        [
            _shown(many),
            {"do": "press", "class": "app-ir__all", "text": "Show all 85 calls"},
            _row("Q220 Jun 2026"),
            _shown(other),
        ]
    )
    opened, pressed, moved, another = trace
    assert len(_list(opened["tree"])) == 5
    [button] = classed(opened["tree"], "app-ir__all")
    assert button["type"] == "button" and "fb-btn" in button["props"]["className"]
    [nav] = classed(opened["tree"], "app-ir__list")
    assert list(elements(nav))[-1] == button  # under the rows
    assert pressed["redrawn"] == 1 and pressed["fetched"] == []
    assert len(_list(pressed["tree"])) == 22 and _all_button(pressed["tree"]) == []
    assert len(_list(moved["tree"])) == 22
    assert len(_list(another["tree"])) == 5 and _all_button(another["tree"]) == [
        "Show all 85 calls"
    ]


@pytest.mark.parametrize(
    ("answer", "word"),
    [
        (answers.investor(), "2019Q2"),
        (answers.investor(), "2026Q4"),
        (answers.profile_only_investor(), "2026Q3"),
    ],
)
def test_a_call_the_company_has_none_of_is_put_right(answer: dict[str, Any], word: str) -> None:
    """An address naming a call the company has none of (7.1) shows the newest call, and the
    address is put right to the tab's own (FairbandPage.show with no word), the newest call read
    once and the tab's own read never; a company with no call draws its sentence and is put
    right too."""
    [opened] = _drive([_shown(answer, word)])
    assert opened["shows"] == [["company", "LFOX", TAB, None]]
    if answer["calls"]:
        assert opened["fetched"] == _get(Q3)
        assert _list(opened["tree"]) == LFOX_LIST
    else:
        assert opened["fetched"] == [] and _sentences(opened["tree"]) == [NO_CALL]


@pytest.mark.parametrize("word", [None, "2026Q3", "2025Q3", "filings"])
def test_an_address_the_tab_reads_is_kept(word: str | None) -> None:
    [opened] = _drive([_shown(None, word)])
    assert opened["shows"] == []


@pytest.mark.parametrize(
    ("observed", "status", "body"),
    [
        ("2026-10-16", 200, None),
        ("2026-11-17", 200, None),
        ("2026-10-16", 200, {"turns": [], "questionsAt": None}),
        ("2026-10-16", 503, {"detail": "no FMP key"}),
    ],
)
def test_the_calls_view_s_data_date_is_the_read_s_alone(
    observed: str, status: int, body: Any
) -> None:
    """The whole-branch review's ruling on 7.6: on the Earnings calls view the data date is the
    read's ``dataDate`` alone, the head's quote, the list of calls and the earnings rows. The
    transcript shown does not count, older or newer, with words or without, or failed: a call's
    words do not age, and the reader carries the call's own date. The page still draws again as
    it lands, and the date stays."""
    landed_body = _transcript(observedDay=observed) | (body or {}) if status == 200 else body
    trace = _drive([_shown(), _answer(Q3, landed_body, status), _shown(None, "filings")])
    opened, landed, filings = trace
    assert opened["asOf"] == "2026-11-14"
    assert landed["asOf"] == "2026-11-14" and landed["redrawn"] == 1
    assert filings["asOf"] == answers.FILINGS_DAY


OLDER_DATA = "2026-10-30"  # a data date older than LFOX's filing list's day


@pytest.mark.parametrize(
    ("answer", "word", "day"),
    [
        (answers.INVESTOR, None, "2026-11-14"),
        (answers.INVESTOR, "2026Q3", "2026-11-14"),
        (answers.INVESTOR, "filings", answers.FILINGS_DAY),
        (answers.INVESTOR | {"dataDate": OLDER_DATA}, "filings", OLDER_DATA),
        (answers.INVESTOR | {"filings": None}, "filings", "2026-11-14"),
        (answers.INVESTOR | {"dataDate": None}, None, None),
        (answers.INVESTOR | {"dataDate": None}, "filings", answers.FILINGS_DAY),
        (answers.profile_only_investor(), None, None),
        (answers.profile_only_investor(), "filings", None),
    ],
)
def test_the_data_date_is_the_view_s(answer: dict[str, Any], word: str | None, day: str) -> None:
    """The data date at the row's right end (7.6), the oldest day among the stored answers the
    view draws: on Earnings calls the read's ``dataDate``, its list of calls, its earnings rows
    and the head's quote; on Filings the oldest of that ``dataDate``, which counts the head's
    quote and the earnings rows behind the line of the next earnings report drawn there, and the
    filing list's day: the list's where the ``dataDate`` is newer, the ``dataDate`` where it is
    older, and the ``dataDate`` alone without a list. The page asks the tab's script for it
    (``companyPage.dataDate``), on the answer and the address's word."""
    assert node(f"companyPage.dataDate.{TAB}", [answer, word], *SCRIPTS) == day
    assert node("investor.dataDate", [answer, word], *SCRIPTS) == day


# ------------------------------------------------------------------------ the Filings view (7.5)

FILTERS = ["Without insider forms", "10-K and 10-Q", "8-K", "Insider forms", "All"]
# The mockup's table of the forms' plain words, as written there.
FORMS = {
    "10-K": "Annual report",
    "10-Q": "Quarterly report",
    "8-K": "Current report: an event the company must disclose",
    "DEF 14A": "Proxy statement for the shareholders' meeting",
    "DEFA14A": "Additional proxy material",
    "3": "An insider's first statement of holdings",
    "4": "A change in an insider's holdings",
    "5": "An insider's yearly statement of holdings",
    "144": "Notice of a planned sale of restricted shares",
    "424B2": "Prospectus for securities on offer",
    "FWP": "Free writing prospectus",
    "25-NSE": "Notice that a security leaves an exchange",
    "SD": "Specialized disclosure report",
    "11-K": "Annual report of an employee stock plan",
    "S-8": "Registration of shares for employee plans",
    "S-3ASR": "Shelf registration of securities",
    "20-F": "Annual report of a foreign issuer",
    "6-K": "Report of a foreign issuer",
    "SC 13G": "A large holder's statement of ownership",
    "SC 13G/A": "A change to a large holder's statement",
    "PX14A6G": "A shareholder's notice of exempt solicitation",
    "ARS": "Annual report to shareholders",
}
CUT = "The vendor's list is cut at 1,000 filings a window."


def test_the_five_filters() -> None:
    """The filters (7.5), in order, each a name and a test of a form; the insider forms' test
    takes an amendment (``4/A``), the first's leaves it out. Which forms each keeps:
    test_each_filter_keeps_its_forms_and_a_press_reads_nothing."""
    assert [f["name"] for f in node("investor.FILTERS", [], *SCRIPTS)] == FILTERS
    assert node("investor.FILTERS.3.test", ["4/A"], *SCRIPTS) is True
    assert node("investor.FILTERS.0.test", ["4/A"], *SCRIPTS) is False


@pytest.mark.parametrize(
    ("form", "words"),
    [
        ("10-K", "Annual report"),
        ("8-K/A", "Amendment: Current report: an event the company must disclose"),
        ("4/A", "Amendment: A change in an insider's holdings"),
        ("DEF 14A/A", "Amendment: Proxy statement for the shareholders' meeting"),
        ("SC 13G/A", "A change to a large holder's statement"),
        ("NO-SUCH", ""),
        ("NO-SUCH/A", ""),
        ("toString", ""),
        ("constructor/A", ""),
        ("", ""),
    ],
)
def test_a_form_s_plain_words(form: str, words: str) -> None:
    """What it is (7.5): the form's words from the mockup's table; an amendment (``8-K/A``)
    ``Amendment: `` and the form's words, unless the table holds the amendment's own
    (``SC 13G/A``); nothing for a form the table lacks, whatever an object's own names are."""
    assert node("investor.words", [form], *SCRIPTS) == words


def test_the_forms_words_are_the_mockup_s() -> None:
    """The table of the forms' plain words is the mockup's ``FORMS``, as written there, no form
    added or left out."""
    assert node("investor.FORMS", [], *SCRIPTS) == FORMS


def test_the_insider_forms_are_the_agents_filing_list_s() -> None:
    """The whole-branch review's M-4: the page's insider forms, kept by Insider forms and left out
    by the first filter, are the set the agents' filing list leaves out by default
    (``filings_api.OWNERSHIP_FORMS``, spec 7.5), in its order, so a change to one fails here."""
    assert node("investor.INSIDER", [], *SCRIPTS) == list(OWNERSHIP_FORMS)


@pytest.mark.parametrize(
    ("windows", "rows", "to"),
    [
        ([{"from": "2025-11-18", "to": "2026-11-18", "truncated": False}], [], "2025-11-17"),
        (
            [{"from": "2025-11-18", "to": "2026-11-18", "truncated": True}],
            [{"filed": "2026-09-30"}, {"filed": "2026-08-04"}],
            "2026-08-04",
        ),
        (
            [{"from": "2025-11-18", "to": "2026-11-18", "truncated": True}],
            [{"filed": "2026-09-30"}, {"filed": "2026-08-04"}, {"filed": None}],
            "2026-08-04",
        ),
        (
            [
                {"from": "2025-11-18", "to": "2026-11-18", "truncated": True},
                {"from": "2025-01-01", "to": "2026-01-01", "truncated": False},
            ],
            [{"filed": "2026-09-30"}, {"filed": "2025-03-04"}],
            "2024-12-31",
        ),
        (
            [
                {"from": "2025-11-18", "to": "2026-11-18", "truncated": False},
                {"from": "2024-03-01", "to": "2025-03-01", "truncated": True},
            ],
            [{"filed": "2026-09-30"}, {"filed": None}, {"filed": "2024-07-15"}],
            "2024-07-15",
        ),
        ([{"from": "2024-03-01", "to": "2025-03-01", "truncated": False}], [], "2024-02-29"),
        ([{"from": "2025-11-18", "to": "2026-11-18", "truncated": True}], [], "2025-11-17"),
    ],
)
def test_the_next_window_ends_before_the_oldest_read(
    windows: list[dict[str, Any]], rows: list[dict[str, Any]], to: str
) -> None:
    """The next window (7.5) ends the day before the oldest window's first day; where that
    window is cut, on the filing day of the oldest row shown, a row with no day aside; a cut
    window with no row with a day ends the day before its first day."""
    assert node("investor.olderTo", [windows, rows], *SCRIPTS) == to


def _filing(form: str, filed: str | None, n: int, document: bool = True, files: bool = True) -> Any:
    """A filing row as the reads answer it, its invented links on the SEC's site numbered ``n``."""
    base = f"https://www.sec.gov/Archives/edgar/data/2/{n:018d}"
    return {
        "form": form,
        "filed": filed,
        "document": f"{base}/filing-{n}.htm" if document else None,
        "files": f"{base}/index.htm" if files else None,
    }


def test_a_row_drawn_already_is_not_added_twice() -> None:
    """``merged`` adds the rows of a window read under those drawn, in their order, but a row
    with the same ``files`` link, form and day as one drawn already, two rows with no ``files``
    link among them; a row that differs in any of the three is added."""
    first = [
        _filing("8-K", "2026-05-02", 1),
        _filing("10-Q", "2026-04-28", 2),
        _filing("4", "2026-04-28", 3),
    ]
    first.append(_filing("SC 13G", "2026-04-28", 4, document=False, files=False))
    more = [
        _filing("10-Q", "2026-04-28", 2),
        _filing("10-Q", "2026-04-28", 2, document=False),
        _filing("10-Q/A", "2026-04-28", 2),
        _filing("10-Q", "2026-04-27", 2),
        _filing("10-Q", "2026-04-28", 5),
        _filing("SC 13G", "2026-04-28", 6, document=False, files=False),
        _filing("20-F", "2026-03-01", 7),
    ]
    found = node("investor.merged", [first, more], *SCRIPTS)
    assert found == first + [more[2], more[3], more[4], more[6]]
    assert node("investor.merged", [[], first], *SCRIPTS) == first
    assert node("investor.merged", [first, []], *SCRIPTS) == first


def _filters(tree: Any) -> list[tuple[str, str]]:
    """Each filter's words, its name and its count, and whether it is pressed."""
    return [(text(b), b["props"]["aria-pressed"]) for b in classed(tree, "app-ir__filter")]


def _pressed(tree: Any) -> list[str]:
    return [name for name, on in _filters(tree) if on == "true"]


def _filed(tree: Any) -> list[tuple[str, str, str, list[str]]]:
    """The table's rows: each its day, its form, its plain words and its links' words."""
    [table] = classed(tree, "app-ir__table")
    [body] = [e for e in elements(table) if e["type"] == "tbody"]
    found = []
    for row in (e for e in elements(body) if e["type"] == "tr"):
        cells = [e for e in elements(row) if e["type"] == "td"]
        assert len(cells) == 4
        links = [text(a) for a in elements(cells[3]) if a["type"] == "a"]
        found.append((text(cells[0]), text(cells[1]), text(cells[2]), links))
    return found


def _forms(tree: Any) -> list[str]:
    return [form for _, form, _, _ in _filed(tree)]


def _window_line(tree: Any) -> str | None:
    found = classed(tree, "app-ir__window")
    assert len(found) <= 1
    return text(found[0]) if found else None


def _older_button(tree: Any) -> list[dict[str, Any]]:
    return classed(tree, "app-ir__older")


def _faded(tree: Any) -> bool:
    [block] = classed(tree, "app-ir__filings")
    return block["props"].get("aria-busy") == "true"


LFOX_FILED = [
    ("30 Oct 2026", "6-K", "Report of a foreign issuer", ["Document", "All files"]),
    ("17 Jul 2026", "6-K", "Report of a foreign issuer", ["All files"]),
    ("28 Apr 2026", "20-F", "Annual report of a foreign issuer", ["Document", "All files"]),
    ("11 Feb 2026", "SC 13G", "A large holder's statement of ownership", []),
]
LFOX_FILTERS = [
    ("Without insider forms 4", "true"),
    ("10-K and 10-Q 0", "false"),
    ("8-K 0", "false"),
    ("Insider forms 1", "false"),
    ("All 5", "false"),
]


def test_the_filings_view_its_filters_its_table_and_its_line() -> None:
    """The Filings view (7.5): the five filters, each a button with its count among the rows
    read, the first pressed on opening; then the table, in a box of its own that scrolls
    sideways, four columns, Filed, Form, What it is, On the SEC's site, the rows the filter keeps
    newest first, each its day, its form as given, its plain words and its links, Document and
    All files, a link the row lacks left out; under it the line of the window read and Show older
    filings. The insider's form 4 is under Insider forms and All alone."""
    tree = _draw(answers.investor(), "filings")
    [block] = classed(tree, "app-ir__filings")
    assert _filters(tree) == LFOX_FILTERS
    for button in classed(tree, "app-ir__filter"):
        assert button["type"] == "button" and button["props"]["type"] == "button"
        assert button["props"]["className"] == "control app-ir__filter"
        [count] = classed(button, "app-ir__n")
        assert count["props"]["className"] == "figure-sm app-ir__n"
    [table] = classed(tree, "app-ir__table")
    [box] = [e for e in elements(block) if table in e["props"].get("children", [])]
    assert box["type"] == "div" and box["props"]["className"] == "app-ir__scroll"
    [head] = [e for e in elements(table) if e["type"] == "thead"]
    heads = [e for e in elements(head) if e["type"] == "th"]
    assert [text(th) for th in heads] == ["Filed", "Form", "What it is", "On the SEC's site"]
    assert {th["props"]["className"] for th in heads} == {"label"}
    assert _filed(tree) == LFOX_FILED
    assert _window_line(tree) == "Filed from 1 Nov 2025 to 1 Nov 2026."
    assert [text(b) for b in _older_button(tree)] == ["Show older filings"]
    [button] = _older_button(tree)  # the design system's small button, undrawn here
    assert button["props"]["size"] == "sm" and button["props"]["disabled"] is False
    assert not _faded(tree)
    assert CUT not in text(tree) and _sentences(tree) == []
    found = list(elements(block))
    order = [classed(block, name)[0] for name in ("app-ir__filters", "app-ir__scroll")]
    assert found.index(order[0]) < found.index(order[1]) < found.index(button)


def test_a_row_s_links_open_the_sec_s_site_in_a_new_tab() -> None:
    """A row's links (7.5): Document, the filing's main document, and All files, its index page,
    each opening in a new tab with ``rel="noopener"``; a link the row lacks, or one that does not
    start ``https://``, is left out, the page checking it as the read does. A form the table
    lacks has no plain words; a missing day is the dash."""
    rows = [
        _filing("8-K", "2026-10-02", 1),
        {
            "form": "8-K",
            "filed": "2026-09-02",
            "document": "http://www.sec.gov/a.htm",
            "files": "https://www.sec.gov/Archives/edgar/data/2/b-index.htm",
        },
        {
            "form": "NO-SUCH",
            "filed": "2026-08-02",
            "document": "javascript:alert(1)",
            "files": "ftp://www.sec.gov/c-index.htm",
        },
        {"form": "10-K", "filed": None, "document": "HTTPS://www.sec.gov/d.htm", "files": None},
    ]
    answer = answers.investor()
    answer["filings"]["rows"] = rows
    tree = _draw(answer, "filings")
    assert _filed(tree) == [
        ("2 Oct 2026", "8-K", FORMS["8-K"], ["Document", "All files"]),
        ("2 Sep 2026", "8-K", FORMS["8-K"], ["All files"]),
        ("2 Aug 2026", "NO-SUCH", "", []),
        ("—", "10-K", "Annual report", []),
    ]
    links = [e for e in elements(classed(tree, "app-ir__table")[0]) if e["type"] == "a"]
    assert [a["props"]["href"] for a in links] == [
        rows[0]["document"],
        rows[0]["files"],
        rows[1]["files"],
    ]
    for a in links:
        assert a["props"]["target"] == "_blank" and a["props"]["rel"] == "noopener"
        assert a["props"]["className"] == "app-link app-ir__link"


@pytest.mark.parametrize("truncated", [True, False])
def test_the_cut_line_only_where_a_window_is_cut(truncated: bool) -> None:
    """The line adds "The vendor's list is cut at 1,000 filings a window." where the oldest
    window read, here the only one, holds the vendor's limit of rows, and only there."""
    answer = answers.investor()
    answer["filings"]["truncated"] = truncated
    line = _window_line(_draw(answer, "filings"))
    start = "Filed from 1 Nov 2025 to 1 Nov 2026."
    assert line == (f"{start} {CUT}" if truncated else start)


def test_no_filing_list_draws_its_sentence_and_no_button() -> None:
    """Review Focus 2: a company with no filing list on file draws "No filing on file." and no
    button; one whose first window is empty draws the sentence and the button, and no filter,
    table or line."""
    none = _draw(answers.profile_only_investor(), "filings")
    assert _sentences(none) == [NO_FILING] and _older_button(none) == []
    assert classed(none, "app-ir__filings") == []
    empty = answers.investor()
    empty["filings"]["rows"] = []
    tree = _draw(empty, "filings")
    assert _sentences(tree) == [NO_FILING]
    assert [text(b) for b in _older_button(tree)] == ["Show older filings"]
    for name in ("app-ir__filters", "app-ir__table", "app-ir__window"):
        assert classed(tree, name) == [], name


ROWS_OF_EVERY_KIND = [
    _filing("8-K", "2026-11-10", 1),
    _filing("4/A", "2026-11-05", 2),
    _filing("10-Q", "2026-10-30", 3),
    _filing("4", "2026-10-20", 4),
    _filing("8-K/A", "2026-09-01", 5),
    _filing("144", "2026-08-15", 6),
    _filing("10-K/A", "2026-07-01", 7),
    _filing("20-F", "2026-05-01", 8),
    _filing("6-K", "2026-04-01", 9),
    _filing("NO-SUCH", "2026-03-01", 10),
    _filing("3", "2026-02-01", 11),
    _filing("144/A", "2026-01-20", 12),
    _filing("5", "2026-01-15", 13),
    _filing("40-F", "2026-01-10", 14),
    _filing("10-K", "2025-12-01", 15),
    _filing("10-KT", "2025-11-20", 16),
]


def _filter(name: str, count: int) -> dict[str, Any]:
    """The filter ``name``, with its count ``count``, is pressed."""
    return {"do": "press", "class": "app-ir__filter", "text": f"{name} {count}"}


def _older() -> dict[str, Any]:
    return {"do": "press", "class": "app-ir__older", "text": "Show older filings"}


def _with(rows: list[dict[str, Any]], **changes: Any) -> dict[str, Any]:
    """LFOX's answer, its first window's rows ``rows``, with ``changes`` to that window."""
    answer = answers.investor()
    answer["filings"] |= {"rows": rows, **changes}
    return answer


def test_each_filter_keeps_its_forms_and_a_press_reads_nothing() -> None:
    """Each filter keeps its forms (7.5), with its count among the rows read: ``4/A`` and
    ``144/A`` under Insider forms; ``10-K/A`` and ``10-KT`` under 10-K and 10-Q; ``8-K/A`` under
    8-K; ``20-F``, ``6-K``, ``40-F`` (no insider's form, though it starts with ``4``) and a form
    the table lacks under the first and All alone. A press marks its filter, draws the page again
    and reads nothing."""
    counts = [10, 4, 2, 6, 16]
    order = [1, 2, 3, 4, 0]
    trace = _drive(
        [
            _shown(_with(ROWS_OF_EVERY_KIND), "filings"),
            *(_filter(FILTERS[i], counts[i]) for i in order),
        ]
    )
    opened, tens, eights, insiders, every, first = trace
    named = [f"{name} {n}" for name, n in zip(FILTERS, counts, strict=True)]
    assert [words for words, _ in _filters(opened["tree"])] == named
    assert _pressed(opened["tree"]) == [named[0]] and opened["fetched"] == []
    assert _forms(opened["tree"]) == [
        "8-K",
        "10-Q",
        "8-K/A",
        "10-K/A",
        "20-F",
        "6-K",
        "NO-SUCH",
        "40-F",
        "10-K",
        "10-KT",
    ]
    assert _forms(tens["tree"]) == ["10-Q", "10-K/A", "10-K", "10-KT"]
    assert _forms(eights["tree"]) == ["8-K", "8-K/A"]
    assert _forms(insiders["tree"]) == ["4/A", "4", "144", "3", "144/A", "5"]
    assert _forms(every["tree"]) == [row["form"] for row in ROWS_OF_EVERY_KIND]
    assert _forms(first["tree"]) == _forms(opened["tree"])
    for step, i in zip((tens, eights, insiders, every, first), order, strict=True):
        assert _pressed(step["tree"]) == [named[i]]
        assert step["fetched"] == [] and step["redrawn"] == 1 and step["shows"] == []
    words = {form: what for _, form, what, _ in _filed(every["tree"])}
    assert words["4/A"] == "Amendment: " + FORMS["4"]
    assert words["10-K/A"] == "Amendment: " + FORMS["10-K"]
    assert words["NO-SUCH"] == ""


def _older_url(to: str, company: str = LFOX) -> str:
    """The filings read of ``company``'s window of the 365 days to ``to``."""
    return f"{company}/page/investor-relations/filings?to={to}"


def _window(start: str, to: str, rows: list[dict[str, Any]], **changes: Any) -> dict[str, Any]:
    """The filings read's answer for the window from ``start`` to ``to``, stored on 20 Oct 2026."""
    return {
        "from": start,
        "to": to,
        "rows": rows,
        "truncated": False,
        "observedDay": "2026-10-20",
    } | changes


YEAR_BEFORE = [
    _filing("20-F", "2025-04-29", 21),
    _filing("4", "2025-03-03", 22),
    _filing("6-K", "2025-02-10", 23),
]


def test_show_older_filings_reads_the_year_before_and_adds_its_rows() -> None:
    """A press of Show older filings (7.5, 7.6) reads the window of the 365 days that end the
    day before the first window's first day, through the filings read with the request header,
    while the view waits, faded, a second press reading nothing; as it lands its rows stand under
    the table's, the counts count them, the line's first date moves back and the row's data date
    becomes the older window's day. A window that answers no filing takes the button away; the
    line's first date moves back to it."""
    first = _older_url("2025-10-31")
    second = _older_url("2024-10-30")
    trace = _drive(
        [
            _shown(None, "filings"),
            _older(),
            _older(),
            _answer(first, _window("2024-10-31", "2025-10-31", YEAR_BEFORE)),
            _older(),
            _answer(second, _window("2023-10-31", "2024-10-30", [], observedDay="2026-11-17")),
        ]
    )
    opened, pressed, again, landed, more, ended = trace
    assert opened["fetched"] == [] and opened["asOf"] == answers.FILINGS_DAY
    [button] = _older_button(opened["tree"])
    assert button["type"] == "button" and "fb-btn" in button["props"]["className"].split()
    assert button["props"]["disabled"] is False
    assert pressed["fetched"] == _get(first) and pressed["headers"] == [HEADER]
    assert pressed["inFlight"] == [first] and pressed["redrawn"] == 1
    assert _faded(pressed["tree"]) and _older_button(pressed["tree"])[0]["props"]["disabled"]
    assert _filed(pressed["tree"]) == LFOX_FILED
    assert again["fetched"] == [] and again["inFlight"] == [first]
    assert landed["redrawn"] == 1 and not _faded(landed["tree"])
    assert _filed(landed["tree"]) == LFOX_FILED + [
        ("29 Apr 2025", "20-F", FORMS["20-F"], ["Document", "All files"]),
        ("10 Feb 2025", "6-K", FORMS["6-K"], ["Document", "All files"]),
    ]
    assert _filters(landed["tree"]) == [
        ("Without insider forms 6", "true"),
        ("10-K and 10-Q 0", "false"),
        ("8-K 0", "false"),
        ("Insider forms 2", "false"),
        ("All 8", "false"),
    ]
    assert _window_line(landed["tree"]) == "Filed from 31 Oct 2024 to 1 Nov 2026."
    assert landed["asOf"] == "2026-10-20"
    assert not _older_button(landed["tree"])[0]["props"]["disabled"]
    assert more["fetched"] == _get(second) and more["headers"] == [HEADER]
    assert ended["redrawn"] == 1 and _older_button(ended["tree"]) == []
    assert _filed(ended["tree"]) == _filed(landed["tree"])
    assert _window_line(ended["tree"]) == "Filed from 31 Oct 2023 to 1 Nov 2026."
    assert ended["asOf"] == "2026-10-20"


def test_after_a_cut_window_the_next_ends_on_the_oldest_row_s_day() -> None:
    """Where the oldest window read is cut at the vendor's limit (7.5), the next window ends on
    the filing day of the oldest row shown, and a row of it already in the table (the same
    ``files`` link, form and day) is not drawn twice; the line says the list is cut while the cut
    window is the oldest read, and not once a whole window behind it completes the span."""
    rows = answers.investor()["filings"]["rows"][:4]  # its oldest row the 20-F of 28 Apr 2026
    twenty = rows[3]
    url = _older_url("2026-04-28")
    later = [twenty, _filing("8-K/A", "2026-03-02", 31), twenty | {"form": "20-F/A"}]
    trace = _drive(
        [
            _shown(_with(rows, truncated=True), "filings"),
            _older(),
            _answer(url, _window("2025-04-28", "2026-04-28", later)),
            _filter("All", 6),
        ]
    )
    opened, pressed, landed, every = trace
    assert _window_line(opened["tree"]) == f"Filed from 1 Nov 2025 to 1 Nov 2026. {CUT}"
    assert pressed["fetched"] == _get(url)
    assert _forms(every["tree"]) == ["6-K", "4", "6-K", "20-F", "8-K/A", "20-F/A"]
    assert _window_line(landed["tree"]) == "Filed from 28 Apr 2025 to 1 Nov 2026."


def test_the_cut_line_where_the_oldest_window_read_is_cut() -> None:
    """A whole first window, then an older one cut at the vendor's limit (7.5): the line adds
    that the list is cut, since the oldest window read misses its oldest filings."""
    url = _older_url("2025-10-31")
    trace = _drive(
        [
            _shown(None, "filings"),
            _older(),
            _answer(url, _window("2024-10-31", "2025-10-31", YEAR_BEFORE, truncated=True)),
        ]
    )
    opened, _, landed = trace
    assert _window_line(opened["tree"]) == "Filed from 1 Nov 2025 to 1 Nov 2026."
    assert _window_line(landed["tree"]) == f"Filed from 31 Oct 2024 to 1 Nov 2026. {CUT}"


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (503, {"detail": "no FMP key"}, "no FMP key"),
        (502, {"detail": "FMP answered 500"}, "FMP answered 500"),
        (503, None, "the server answered 503"),
    ],
)
def test_older_filings_that_cannot_be_read_keep_the_table(
    status: int, body: Any, reason: str
) -> None:
    """An older window that cannot be read (7.6): the table stays as it was and one sentence
    stands under it, "The older filings could not be read: <reason>.", the server's sentence;
    the button stays, and a press reads the same window again."""
    url = _older_url("2025-10-31")
    trace = _drive(
        [
            _shown(None, "filings"),
            _older(),
            _answer(url, body, status),
            _older(),
            _answer(url, _window("2024-10-31", "2025-10-31", YEAR_BEFORE)),
        ]
    )
    _, _, failed, again, landed = trace
    assert failed["redrawn"] == 1 and not _faded(failed["tree"])
    assert _filed(failed["tree"]) == LFOX_FILED
    assert _window_line(failed["tree"]) == "Filed from 1 Nov 2025 to 1 Nov 2026."
    assert _sentences(failed["tree"]) == [f"The older filings could not be read: {reason}."]
    [block] = classed(failed["tree"], "app-ir__filings")
    [sentence] = classed(block, "app-ir__none")
    found = list(elements(block))
    assert found.index(classed(block, "app-ir__table")[0]) < found.index(sentence)
    assert not _older_button(failed["tree"])[0]["props"]["disabled"]
    assert failed["asOf"] == answers.FILINGS_DAY
    assert again["fetched"] == _get(url) and _sentences(again["tree"]) == []
    assert _sentences(landed["tree"]) == [] and len(_filed(landed["tree"])) == 6


def test_older_filings_that_fail_on_the_network_keep_the_table() -> None:
    url = _older_url("2025-10-31")
    trace = _drive(
        [
            _shown(None, "filings"),
            _older(),
            {"do": "fail", "url": url, "message": "Failed to fetch"},
        ]
    )
    assert _sentences(trace[-1]["tree"]) == [
        "The older filings could not be read: Failed to fetch."
    ]
    assert _filed(trace[-1]["tree"]) == LFOX_FILED and _older_button(trace[-1]["tree"])


def test_an_empty_first_window_reads_the_year_before() -> None:
    """A first window with no filing draws the sentence and the button (7.5); a press reads the
    year before it, and its rows draw the filters, the table and the line; a window before that
    with no filing takes the button away."""
    trace = _drive(
        [
            _shown(_with([]), "filings"),
            _older(),
            _answer(_older_url("2025-10-31"), _window("2024-10-31", "2025-10-31", YEAR_BEFORE)),
        ]
    )
    opened, pressed, landed = trace
    assert _sentences(opened["tree"]) == [NO_FILING]
    assert pressed["fetched"] == _get(_older_url("2025-10-31"))
    assert _sentences(landed["tree"]) == []
    assert _forms(landed["tree"]) == ["20-F", "6-K"]
    assert _window_line(landed["tree"]) == "Filed from 31 Oct 2024 to 1 Nov 2026."
    [*_, ended] = _drive(
        [
            _shown(_with([]), "filings"),
            _older(),
            _answer(_older_url("2025-10-31"), _window("2024-10-31", "2025-10-31", [])),
        ]
    )
    assert _sentences(ended["tree"]) == [NO_FILING] and _older_button(ended["tree"]) == []


def test_the_windows_read_are_kept_for_the_page_s_life_by_company() -> None:
    """The windows read are kept by company for the page's life: the reader who leaves the view,
    or the company, and comes back sees them, with no read made again. An older window that
    lands while another company is shown draws nothing and is kept under its own company; the
    other company has its own windows, its own button and its first filter."""
    other = answers.investor() | {"symbol": "OTHR"}
    url = _older_url("2025-10-31")
    trace = _drive(
        [
            _shown(None, "filings"),
            _filter("Insider forms", 1),
            _older(),
            _shown(other, "filings"),
            _answer(url, _window("2024-10-31", "2025-10-31", YEAR_BEFORE)),
            _shown(None, "filings"),
            _shown(None, None),
            _shown(None, "filings"),
        ]
    )
    _, insiders, pressed, opened, late, back, calls, again = trace
    assert pressed["fetched"] == _get(url)
    assert _pressed(opened["tree"]) == ["Without insider forms 4"]
    assert not _faded(opened["tree"]) and _filed(opened["tree"]) == LFOX_FILED
    assert late["redrawn"] == 0 and late["tree"] == opened["tree"]
    assert late["asOf"] == answers.FILINGS_DAY
    assert back["fetched"] == [] and _pressed(back["tree"]) == ["Without insider forms 6"]
    assert _window_line(back["tree"]) == "Filed from 31 Oct 2024 to 1 Nov 2026."
    assert back["asOf"] == "2026-10-20"
    assert calls["fetched"] == _get(Q3)
    assert again["fetched"] == [] and again["tree"] == back["tree"]
    assert _pressed(insiders["tree"]) == ["Insider forms 1"]


def test_the_filter_pressed_stays_while_the_view_changes() -> None:
    """The filter pressed stays while the reader moves between the views of one company, and
    another company's filings open on the first."""
    other = answers.investor() | {"symbol": "OTHR"}
    trace = _drive(
        [
            _shown(None, "filings"),
            _filter("All", 5),
            _shown(None, None),
            _shown(None, "filings"),
            _shown(other, "filings"),
        ]
    )
    *_, back, another = trace
    assert _pressed(back["tree"]) == ["All 5"] and len(_filed(back["tree"])) == 5
    assert _pressed(another["tree"]) == ["Without insider forms 4"]


def test_a_new_first_window_starts_the_older_windows_again() -> None:
    """The windows read stand on the first window they followed: where the tab's read answers a
    newer first window (a refresh's), the view draws it alone, with no gap behind it, and the
    next press reads the year before it. Its day, newer than the read's ``dataDate``, leaves the
    data date at the ``dataDate``."""
    newer = _window("2025-11-18", "2026-11-18", [_filing("8-K", "2026-11-17", 41)])
    newer["observedDay"] = "2026-11-18"
    url = _older_url("2025-10-31")
    trace = _drive(
        [
            _shown(None, "filings"),
            _older(),
            _answer(url, _window("2024-10-31", "2025-10-31", YEAR_BEFORE)),
            _shown(answers.investor() | {"filings": newer}, "filings"),
            _older(),
        ]
    )
    *_, refreshed, pressed = trace
    assert _forms(refreshed["tree"]) == ["8-K"]
    assert _window_line(refreshed["tree"]) == "Filed from 18 Nov 2025 to 18 Nov 2026."
    assert refreshed["asOf"] == answers.DATA_DATE and refreshed["fetched"] == []
    assert pressed["fetched"] == _get(_older_url("2025-11-17"))


@pytest.mark.parametrize(
    ("observed", "data", "day"),
    [
        ("2026-10-20", answers.DATA_DATE, "2026-10-20"),
        ("2026-11-17", answers.DATA_DATE, answers.FILINGS_DAY),
        ("2026-11-17", OLDER_DATA, OLDER_DATA),
    ],
)
def test_the_filings_data_date_is_the_oldest_list_read(observed: str, data: str, day: str) -> None:
    """On the Filings view the data date (7.6) is the oldest day among the read's ``dataDate``
    and the filing lists read, the first read's and every older window's; the page draws again
    as a window lands, so the row's date moves. Where the ``dataDate`` is older than every list,
    it is the date."""
    url = _older_url("2025-10-31")
    trace = _drive(
        [
            _shown(answers.investor() | {"dataDate": data}, "filings"),
            _older(),
            _answer(url, _window("2024-10-31", "2025-10-31", YEAR_BEFORE, observedDay=observed)),
        ]
    )
    assert trace[0]["asOf"] == min(data, answers.FILINGS_DAY)
    assert trace[-1]["asOf"] == day and trace[-1]["redrawn"] == 1


def _scripts_but(*names: str) -> str:
    """Every page script but ``names``, one text."""
    return "\n".join(p.read_text() for p in sorted(STATIC.glob("*.js")) if p.name not in names)


# ----------------------------------------------------------------------------- the script's rules


TYPE_STYLES = {"heading", "label", "body", "caption", "figure", "figure-sm", "control"}
# the panel's look, the Financials switch's, the design system's small button's and a link's
SHARED = {
    "app-company__panel",
    "app-fin__seg",
    "fb-btn",
    "fb-btn--secondary",
    "fb-btn--sm",
    "app-link",
}
FRAME = {"app-ir", "app-ir__bar", "app-ir__view", "app-ir__next", "app-ir__day", "app-ir__none"}
CALLS = {  # the Earnings calls view's
    "app-ir__calls",
    "app-ir__list",
    "app-ir__group",
    "app-ir__year",
    "app-ir__call",
    "app-ir__q",
    "app-ir__date",
    "app-ir__all",
    "app-ir__reader",
    "app-ir__title",
    "app-ir__when",
    "app-ir__figures",
    "app-ir__figure",
    "app-ir__name",
    "app-ir__amount",
    "app-ir__tools",
    "app-ir__find",
    "app-ir__count",
    "app-ir__go",
    "app-ir__turns",
    "app-ir__turn",
    "app-ir__turn--questions",
    "app-ir__part",
    "app-ir__who",
    "app-ir__who--operator",
    "app-ir__words",
}
FILINGS = {  # the Filings view's
    "app-ir__filings",
    "app-ir__filters",
    "app-ir__filter",
    "app-ir__n",
    "app-ir__scroll",
    "app-ir__table",
    "app-ir__filed",
    "app-ir__form",
    "app-ir__what",
    "app-ir__links",
    "app-ir__link",
    "app-ir__foot",
    "app-ir__window",
    "app-ir__cut",
    "app-ir__older",
}


def _classes(element: dict[str, Any]) -> list[str]:
    return str(element["props"].get("className") or "").split()


def test_the_tab_s_classes_are_its_own_and_it_draws_no_markup() -> None:
    """Every class the tab draws but the design system's type styles and small button, the
    panel's and the switch's is the tab's own, under ``app-ir``, and in no other script; the
    switch is the Financials tab's (``app-fin__seg``), its rules reused. No vendor is named, no
    chip and no cite; the script builds no markup from words and no pattern from them: a found
    word is a mark element around its text."""
    trees = [
        _draw(answer, word)
        for answer in (answers.investor(), answers.profile_only_investor())
        for word in (None, "filings")
    ]
    trees.append(_draw(answers.investor() | {"calls": _calls(21)}))
    trees.append(_draw(_with(ROWS_OF_EVERY_KIND, truncated=True), "filings"))
    [*_, typed] = _drive([_shown(), _answer(Q3, _transcript()), _type("sensor")])
    trees.append(typed["tree"])
    drawn: set[str] = set()
    for tree in trees:
        drawn |= {n for e in elements(tree) for n in _classes(e)}
        words = text(tree)
        assert "FMP" not in words and "Financial Modeling" not in words
        assert "%" not in words
    own = drawn - TYPE_STYLES - SHARED
    assert FRAME | CALLS | FILINGS <= own
    assert all(name == "app-ir" or name.startswith("app-ir__") for name in own), own
    others = _scripts_but("company_investor.js")
    for name in sorted(own):
        assert re.search(re.escape(name) + r"(?![\w-])", others) is None, name
    assert not [n for n in drawn if "cite" in n or "chip" in n]
    script = _static_file("company_investor.js")
    assert "dangerouslySetInnerHTML" not in script and "innerHTML" not in script
    assert "RegExp" not in script


def _rules(css: str, indent: str = "  ") -> dict[str, str]:
    """Each of the tab's rules of ``css`` by its selector, its declarations on one line: the
    rules at ``indent``, the stylesheet's own by default, an @media block's at four spaces."""
    found = re.findall(r"\n" + indent + r"(\.app-ir(?![a-z])[^{]*)\{([^}]*)\}", css)
    return {selector.strip(): " ".join(body.split()) for selector, body in found}


def _media(css: str, query: str) -> str:
    """The text of the stylesheet's @media block of ``query`` that holds the tab's rules."""
    blocks = []
    for start in [m.end() for m in re.finditer(re.escape(f"@media {query} {{"), css)]:
        depth = 1
        for at in range(start, len(css)):
            depth += {"{": 1, "}": -1}.get(css[at], 0)
            if depth == 0:
                blocks.append(css[start:at])
                break
    [block] = [b for b in blocks if ".app-ir" in b]
    return block


def _painted(css: dict[str, str]) -> None:
    """Every colour a token, none of the tab's own, no red and no green; nothing moves."""
    painted = " ".join(css.values())
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", painted) == []
    for token in re.findall(r"var\(--([a-z0-9-]+)\)", painted):
        assert not re.search(r"pos|neg|red|green|gain|loss|up\b|down\b", token), token
    assert "transition" not in painted and "animation" not in painted


def test_the_tab_s_rules_wear_the_tokens_alone() -> None:
    """The block's top row wraps over a hairline, the switch at its left, the line at its right
    end in ink-muted with its day in ink; a view's sentence in ink-faint. Every colour a token,
    none of the tab's own, no red and no green; nothing moves."""
    css = _rules(_static_file("index.html"))
    assert {".app-ir", ".app-ir__bar", ".app-ir__next", ".app-ir__day", ".app-ir__none"} <= set(css)
    bar = css[".app-ir__bar"]
    assert "display: flex;" in bar and "flex-wrap: wrap;" in bar
    assert "border-bottom: 1px solid var(--hairline);" in bar
    assert "margin: 0 0 0 auto;" in css[".app-ir__next"]  # at the row's right end
    assert "color: var(--ink-muted);" in css[".app-ir__next"]
    assert "color: var(--ink);" in css[".app-ir__day"]
    assert "color: var(--ink-faint);" in css[".app-ir__none"]
    _painted(css)


def test_the_earnings_calls_view_s_rules() -> None:
    """The view as its mockup lays it out (7.3, 7.4): the list 236px wide at the left, staying
    in view while the transcript scrolls; the call shown marked as the Research tab marks its
    section, on surface-selected with a 2px accent edge; the reader faded while its call's read
    is out; the four figures in a row on hairlines, each in the text's own colour; the
    transcript at the reading width, a long word wrapping; the questions' turn under a heavier
    rule; a found word on the accent's quiet tint in the text's own colour. Tokens alone."""
    css = _rules(_static_file("index.html"))
    calls = css[".app-ir__calls"]
    assert "display: grid;" in calls and "grid-template-columns: 236px minmax(0, 1fr);" in calls
    listed = css[".app-ir__list"]
    assert "position: sticky;" in listed and "overflow-y: auto;" in listed
    shown = css['.app-ir__call[aria-current="true"]']
    assert "background: var(--surface-selected);" in shown
    assert "border-left-color: var(--accent);" in shown
    assert "border-left: 2px solid var(--hairline);" in css[".app-ir__call"]
    assert "opacity: 0.5;" in css['.app-ir__reader[aria-busy="true"]']
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in css[".app-ir__figures"]
    assert "color" not in css[".app-ir__amount"]
    assert "max-width: 46rem;" in css[".app-ir__turns"]
    assert "overflow-wrap: anywhere;" in css[".app-ir__words"]
    assert "border-top: 2px solid var(--hairline);" in css[".app-ir__turn--questions"]
    mark = css[".app-ir__words mark"]
    assert "background: var(--accent-quiet);" in mark and "color: inherit;" in mark
    _painted(css)


def test_below_860px_the_list_stands_over_the_reader() -> None:
    """Below 860px (7.8) the list of calls stands over the reader in a box of its own that
    scrolls, and the four figures stand one under the other."""
    css = _rules(_media(_static_file("index.html"), "(width < 860px)"), "    ")
    assert "grid-template-columns: minmax(0, 1fr);" in css[".app-ir__calls"]
    listed = css[".app-ir__list"]
    assert "position: static;" in listed and "max-height: 240px;" in listed
    assert "border: 1px solid var(--hairline);" in listed
    assert "grid-template-columns: minmax(0, 1fr);" in css[".app-ir__figures"]
    assert "border-bottom: 1px solid var(--hairline);" in css[".app-ir__figure"]
    _painted(css)


def test_the_filings_view_s_rules() -> None:
    """The view as its mockup lays it out (7.5, 7.8): the filters wrap, each framed in a pill on
    a hairline, its count in ink-faint, the pressed one on surface-selected with an accent edge;
    the table in a box of its own that scrolls sideways, so a narrow window scrolls the table and
    never the page; the day, the form and the links on one line, the plain words in ink-muted;
    the line and the button under it, wrapping; the view faded while an older window's read is
    out. Tokens alone."""
    css = _rules(_static_file("index.html"))
    filters = css[".app-ir__filters"]
    assert "display: flex;" in filters and "flex-wrap: wrap;" in filters
    one = css[".app-ir__filter"]
    assert "border: 1px solid var(--hairline);" in one
    assert "border-radius: var(--radius-pill);" in one
    pressed = css['.app-ir__filter[aria-pressed="true"]']
    assert "background: var(--surface-selected);" in pressed
    assert "border-color: var(--accent);" in pressed
    assert "color: var(--ink-faint);" in css[".app-ir__n"]
    assert "overflow-x: auto;" in css[".app-ir__scroll"]
    table = css[".app-ir__table"]
    assert "width: 100%;" in table and "min-width: 560px;" in table
    assert "white-space: nowrap;" in css[".app-ir__filed, .app-ir__form, .app-ir__links"]
    assert "color: var(--ink-muted);" in css[".app-ir__what"]
    foot = css[".app-ir__foot"]
    assert "display: flex;" in foot and "flex-wrap: wrap;" in foot
    assert "opacity: 0.5;" in css['.app-ir__filings[aria-busy="true"]']
    _painted(css)


def test_print_shows_the_open_view_alone() -> None:
    """Print (7.8) shows the open view alone, with not the tab's top row, its switch and the line
    of the next earnings report, on either view. On Earnings calls the call shown: its title, its
    figures and its whole transcript at its reading width, as on screen, not the list of calls or
    the tools (the buttons with every button of the page), the reader never faded. On Filings the
    table as filtered, whole, under its line: over it the pressed filter alone, as plain text with
    its count, by the attribute the drawn filter carries (``aria-pressed``), so the paper says
    which filings it holds; never faded, its box not clipping it, a row whole on a page."""
    block = _media(_static_file("index.html"), "print")
    css = _rules(block, "    ")
    assert "display: none !important;" in css[".app-ir__bar"]
    assert "display: none !important;" in css[".app-ir__list, .app-ir__tools"]
    assert "display: block;" in css[".app-ir__calls"]
    assert "opacity: 1;" in css['.app-ir__reader[aria-busy="true"]']
    assert "break-inside: avoid;" in css[".app-ir__words"]
    assert ".app-ir__filters" not in css  # the row stays, for the filter pressed
    assert css['.app-ir__filter:not([aria-pressed="true"])'] == "display: none !important;"
    plain = css['.app-ir__filter[aria-pressed="true"]']
    for declaration in ("padding: 0;", "background: none;", "border: 0;", "border-radius: 0;"):
        assert declaration in plain, declaration
    assert "opacity: 1;" in css['.app-ir__filings[aria-busy="true"]']
    assert "overflow: visible;" in css[".app-ir__scroll"]
    assert "break-inside: avoid;" in css[".app-ir__table tr"]
    assert not [s for s in css if "app-fin__seg" in s]  # the switch goes with the row
    assert not [s for s in css if "app-ir__turns" in s]  # the reading width holds on paper
    tab = block[block.index("/* The Investor relations tab") :]
    comment = " ".join(tab[: tab.index("*/")].split())
    assert "across the page" not in comment and "reading width" in comment
    _painted(css)
    pressed = [
        b
        for b in classed(_draw(answers.investor(), "filings"), "app-ir__filter")
        if b["props"]["aria-pressed"] == "true"
    ]
    assert [text(b) for b in pressed] == ["Without insider forms 4"]


# The Research tab's print rule for the company's head and row, which leaves out its caption too.
RESEARCH_HEAD = (
    ".app-company:has(.app-research) :is(.app-company__quote, .app-company__actions,"
    " .app-company__tabs) { display: none !important; }"
)
# This tab's: the tab list, the head's price and its actions, the row's caption kept.
INVESTOR_HEAD = (
    ".app-company:has(.app-ir) :is(.app-company__quote, .app-company__actions,"
    " .app-company__tablist) { display: none !important; }"
)


def test_print_leaves_out_the_tab_list_the_price_and_the_actions() -> None:
    """The whole-branch review's ruling on 7.8: printed where this tab is drawn, the company's tab
    list, the head's price and its actions are left out, and the row's caption, the data date,
    prints: a printed call or filing list has no other date of its data. The Research tab's rule,
    which leaves out its whole row, the caption with it, is as it was, and no other tab's print
    rule names the company's head or row."""
    block = _media(_static_file("index.html"), "print")
    code = " ".join(re.sub(r"/\*.*?\*/", "", block, flags=re.DOTALL).split())
    assert INVESTOR_HEAD in code and RESEARCH_HEAD in code
    rules = re.findall(r"([^{}]*)\{([^}]*)\}", code)
    heads = [f"{s.strip()} {{ {b.strip()} }}" for s, b in rules if "app-company__" in s]
    assert heads == [RESEARCH_HEAD, INVESTOR_HEAD]
    assert "app-company__asof" not in code
    # the names the rules key on are those the page draws its row and its head with
    script = _static_file("company.js")
    for drawn in (
        "className: 'app-company__tablist'",
        "className: 'caption app-company__asof'",
        "className: 'app-company__quote'",
        "className: 'app-company__actions'",
    ):
        assert drawn in script, drawn


def test_the_script_loads_after_the_estimates_tab_s() -> None:
    """company_investor.js hangs its function on company.js's draw, so it loads after it, and
    after company_estimates.js; the Financials tab's two scripts keep their places, its chart's
    right after its own."""
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    at = scripts.index("company_investor.js")
    assert at > scripts.index("company.js")
    assert at > scripts.index("company_estimates.js")
    assert scripts.index("company_financials.js") == scripts.index("company_estimates.js") + 1
    assert (
        scripts.index("company_financials_chart.js") == scripts.index("company_financials.js") + 1
    )
