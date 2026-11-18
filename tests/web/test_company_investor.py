"""The company page's Investor relations tab, its frame (the Investor relations tab's design, 7.1,
7.2, 7.6 and 9): the fourth of the five tabs; one block the page's width, at its top the switch of
the tab's two views, Earnings calls and Filings, and at the row's right end the line of the next
earnings report; under it the view the address's word names, the Filings view for ``filings``,
else the Earnings calls view. This task's views draw their sentences for a company with nothing
on file, and nothing where the read holds calls or filings: the list, the reader and the table
come with the views of their own. The data date of the tabs' row is the view's: on Earnings calls
the read's, on Filings the filing list's day.

company.js and company_investor.js run in node after the bundle and app.js (``support.page``),
and the tests read the trees their builders return; how the page loads the tab, its addresses
and a press of the switch, which reads nothing, run in ``tests/web/test_company_load.py``.

The company is ``page_answers``' LFOX: five calls on file, the newest Q3 2026's, a filing list of
the year to 1 Nov 2026 stored on 2 Nov 2026, its data date 14 Nov 2026 and its next earnings
report 14 Jan 2027."""

import re
from typing import Any

import pytest
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (STATIC / "company.js", STATIC / "company_investor.js")
TAB = "investor-relations"
NO_CALL = "No earnings call on file."
NO_FILING = "No filing on file."


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


def test_a_view_with_data_draws_its_frame_alone() -> None:
    """A company with calls draws nothing under the row on the Earnings calls view yet, and one
    with a filing list nothing on the Filings view: the list, the reader and the table are the
    views' own. A first window with no filing in it is no filing on file."""
    full = answers.investor()
    for word in (None, "2026Q3", "filings"):
        tree = _draw(full, word)
        assert _sentences(tree) == []
        assert tree["props"]["children"][1] is None
    calls_only = answers.investor() | {"filings": None}
    assert _sentences(_draw(calls_only)) == []
    assert _sentences(_draw(calls_only, "filings")) == [NO_FILING]
    empty_window = answers.investor()
    empty_window["filings"]["rows"] = []
    assert _sentences(_draw(empty_window, "filings")) == [NO_FILING]
    filings_only = answers.investor() | {"calls": []}
    assert _sentences(_draw(filings_only)) == [NO_CALL]
    assert _sentences(_draw(filings_only, "filings")) == []


# ------------------------------------------------------------------------------- the data date


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
    view draws: on Earnings calls the read's ``dataDate``, its list of calls, its earnings rows
    and the head's quote; on Filings the day of the filing list, none without one. The page asks
    the tab's script for it (``companyPage.dataDate``), on the answer and the address's word."""
    assert node(f"companyPage.dataDate.{TAB}", [answer, word], *SCRIPTS) == day
    assert node("investor.dataDate", [answer, word], *SCRIPTS) == day


def _scripts_but(*names: str) -> str:
    """Every page script but ``names``, one text."""
    return "\n".join(p.read_text() for p in sorted(STATIC.glob("*.js")) if p.name not in names)


# ----------------------------------------------------------------------------- the script's rules


TYPE_STYLES = {"heading", "label", "body", "caption", "figure", "control"}  # the design system's
SHARED = {"app-company__panel", "app-fin__seg"}  # the panel's look, and the Financials switch's
FRAME = {"app-ir", "app-ir__bar", "app-ir__view", "app-ir__next", "app-ir__day", "app-ir__none"}


def _classes(element: dict[str, Any]) -> list[str]:
    return str(element["props"].get("className") or "").split()


def test_the_tab_s_classes_are_its_own_and_it_draws_no_markup() -> None:
    """Every class the frame draws but the design system's type styles, the panel's and the
    switch's is the tab's own, under ``app-ir``, and in no other script; the switch is the
    Financials tab's (``app-fin__seg``), its rules reused. No vendor is named, no chip and no
    cite; the script builds no markup from words."""
    drawn: set[str] = set()
    for answer in (answers.investor(), answers.profile_only_investor()):
        for word in (None, "filings"):
            tree = _draw(answer, word)
            drawn |= {n for e in elements(tree) for n in _classes(e)}
            words = text(tree)
            assert "FMP" not in words and "Financial Modeling" not in words
            assert "%" not in words
    own = drawn - TYPE_STYLES - SHARED
    assert FRAME <= own
    assert all(name == "app-ir" or name.startswith("app-ir__") for name in own), own
    others = _scripts_but("company_investor.js")
    for name in sorted(own):
        assert re.search(re.escape(name) + r"(?![\w-])", others) is None, name
    assert not [n for n in drawn if "cite" in n or "chip" in n]
    script = _static_file("company_investor.js")
    assert "dangerouslySetInnerHTML" not in script and "innerHTML" not in script


def _rules(css: str) -> dict[str, str]:
    """Each of the tab's rules of ``css`` by its selector, its declarations on one line."""
    found = re.findall(r"\n  (\.app-ir(?![a-z])[^{]*)\{([^}]*)\}", css)
    return {selector.strip(): " ".join(body.split()) for selector, body in found}


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
    painted = " ".join(css.values())
    assert re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", painted) == []
    for token in re.findall(r"var\(--([a-z0-9-]+)\)", painted):
        assert not re.search(r"pos|neg|red|green|gain|loss|up\b|down\b", token), token
    assert "transition" not in painted and "animation" not in painted


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
