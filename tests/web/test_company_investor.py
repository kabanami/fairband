"""The company page's Investor relations tab (the Investor relations tab's design, 7.1 to 7.4, 7.6,
7.8 and 9): the fourth of the five tabs; one block the page's width, at its top the switch of the
tab's two views, Earnings calls and Filings, and at the row's right end the line of the next
earnings report; under it the view the address's word names, the Filings view for ``filings``,
else the Earnings calls view. A view draws its sentence for a company with nothing on file.

The Earnings calls view: at its left the list of calls under their fiscal years' heads, newest
first, five years unless all are asked for, the call shown marked; at its right the reader of
that call, its title, its date, its four figures and its transcript, read once a call through
the call's read with the request header and kept for the page's life, with the find box and the
button to the questions. The Filings view's table comes with that view. The data date of the
tabs' row is the view's: on Earnings calls the older of the read's and the transcript's shown, on
Filings the filing list's day.

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
    with a filing list nothing yet on the Filings view, whose table is that view's own; neither
    draws a sentence. A first window with no filing in it is no filing on file."""
    full = answers.investor()
    for word in (None, "2026Q3"):
        tree = _draw(full, word)
        assert _sentences(tree) == []
        assert tree["props"]["children"][1]["props"]["className"] == "app-ir__calls"
    filings = _draw(full, "filings")
    assert _sentences(filings) == [] and filings["props"]["children"][1] is None
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
    ("observed", "status", "body", "day"),
    [
        ("2026-10-16", 200, None, "2026-10-16"),
        ("2026-11-17", 200, None, "2026-11-14"),
        ("2026-10-16", 200, {"turns": [], "questionsAt": None}, "2026-11-14"),
        ("2026-10-16", 503, {"detail": "no FMP key"}, "2026-11-14"),
    ],
)
def test_the_data_date_counts_the_transcript_shown(
    observed: str, status: int, body: Any, day: str
) -> None:
    """On the Earnings calls view the data date (7.6) is the older of the read's and the day of
    the transcript shown, once it lands with words; while its read is out, where it failed or
    has no words, the read's. The page draws again as it lands, so the row's date moves."""
    landed_body = _transcript(observedDay=observed) | (body or {}) if status == 200 else body
    trace = _drive([_shown(), _answer(Q3, landed_body, status), _shown(None, "filings")])
    opened, landed, filings = trace
    assert opened["asOf"] == "2026-11-14"
    assert landed["asOf"] == day and landed["redrawn"] == 1
    assert filings["asOf"] == answers.FILINGS_DAY


@pytest.mark.parametrize(
    ("answer", "word", "day"),
    [
        (answers.INVESTOR, None, "2026-11-14"),
        (answers.INVESTOR, "2026Q3", "2026-11-14"),
        (answers.INVESTOR, "filings", answers.FILINGS_DAY),
        (answers.INVESTOR | {"filings": None}, "filings", None),
        (answers.INVESTOR | {"dataDate": None}, None, None),
        (answers.profile_only_investor(), None, None),
        (answers.profile_only_investor(), "filings", None),
    ],
)
def test_the_data_date_is_the_view_s(answer: dict[str, Any], word: str | None, day: str) -> None:
    """The data date at the row's right end (7.6), the oldest day among the stored answers the
    view draws: on Earnings calls, before the call's transcript is in, the read's ``dataDate``,
    its list of calls, its earnings rows and the head's quote; on Filings the day of the filing
    list, none without one. The page asks the tab's script for it (``companyPage.dataDate``), on
    the answer and the address's word. The transcript's day joins it as it lands
    (test_the_data_date_counts_the_transcript_shown)."""
    assert node(f"companyPage.dataDate.{TAB}", [answer, word], *SCRIPTS) == day
    assert node("investor.dataDate", [answer, word], *SCRIPTS) == day


def _scripts_but(*names: str) -> str:
    """Every page script but ``names``, one text."""
    return "\n".join(p.read_text() for p in sorted(STATIC.glob("*.js")) if p.name not in names)


# ----------------------------------------------------------------------------- the script's rules


TYPE_STYLES = {"heading", "label", "body", "caption", "figure", "figure-sm", "control"}
# the panel's look, the Financials switch's and the design system's small button's
SHARED = {"app-company__panel", "app-fin__seg", "fb-btn", "fb-btn--secondary", "fb-btn--sm"}
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
    [*_, typed] = _drive([_shown(), _answer(Q3, _transcript()), _type("sensor")])
    trees.append(typed["tree"])
    drawn: set[str] = set()
    for tree in trees:
        drawn |= {n for e in elements(tree) for n in _classes(e)}
        words = text(tree)
        assert "FMP" not in words and "Financial Modeling" not in words
        assert "%" not in words
    own = drawn - TYPE_STYLES - SHARED
    assert FRAME | CALLS <= own
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


def test_print_shows_the_call_alone() -> None:
    """Print (7.8) shows the call shown alone: its title, its figures and its whole transcript;
    the switch, the list of calls and the tools are left out (the buttons with every button of
    the page), the reader across the page and never faded."""
    css = _rules(_media(_static_file("index.html"), "print"), "    ")
    hidden = css[".app-ir .app-fin__seg, .app-ir__list, .app-ir__tools"]
    assert "display: none !important;" in hidden
    assert "display: block;" in css[".app-ir__calls"]
    assert "opacity: 1;" in css['.app-ir__reader[aria-busy="true"]']
    assert "break-inside: avoid;" in css[".app-ir__words"]
    _painted(css)


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
