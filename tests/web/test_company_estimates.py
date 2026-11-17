"""The company page's Estimates tab (the company page's design, 9): at the left Earnings, the next
date in its head over the table of the next date and the reported quarters; at the right Analysts,
the consensus word in its head over the price target and the five ratings' counts, then Consensus
estimates, one row a fiscal year. company.js and company_estimates.js run in node after the bundle
and app.js (``support.page``), and the tests read the trees their builders return.

The company is ``page_answers``' LFOX, which reports in New Taiwan dollars: its earnings and its
price target are in US dollars, its consensus in TWD (14.2). Its next date is 14 Jan 2027, after
the close and not confirmed, and three quarters are reported."""

import re
from typing import Any

import pytest
from support import page_answers as answers
from support.page import NODE, STATIC, classed, elements, node, text
from support.web import _static_file

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

SCRIPTS = (STATIC / "company.js", STATIC / "company_estimates.js")
EARNINGS = answers.ESTIMATES["earnings"]
RATINGS = answers.ESTIMATES["ratings"]
NEXT = {"day": "2027-02-04", "time": "amc", "confirmed": False}
EARNINGS_HEAD = ["Reported", "EPS", "Estimate", "Revenue", "Estimate"]
CONSENSUS_HEAD = ["Fiscal year", "Revenue", "EPS", "EPS low", "EPS high", "Analysts"]
REPORTED = [
    ["16 Jul 2026", "$1.97", "$1.90", "$26.71B", "$26.05B"],
    ["16 Apr 2026", "$1.72", "$1.75", "$24.88B", "$25.10B"],
    ["15 Jan 2026", "$1.64", "$1.58", "$23.94B", "$23.50B"],
]


def _page(helper: str, *args: Any) -> Any:
    """What ``companyPage.<helper>`` returns on ``args``, company.js and company_estimates.js
    loaded after app.js, as the page loads them."""
    return node("companyPage." + helper, list(args), *SCRIPTS)


def _title(tree: Any) -> str:
    """The text of the block's title, its head's ``h2``."""
    [title] = [e for e in elements(tree) if e.get("type") == "h2"]
    return text(title)


def _head_texts(tree: Any) -> list[str]:
    """The text of each paragraph in the block's head."""
    [head] = [e for e in elements(tree) if e.get("type") == "header"]
    return [text(e) for e in elements(head) if e.get("type") == "p"]


def _table(tree: Any) -> list[list[str]]:
    """The texts of the one small table of ``tree``: its head's cells, then each row's."""
    [table] = [e for e in elements(tree) if e.get("type") == "table"]
    head = [text(e) for e in elements(table) if e.get("type") == "th"]
    rows = [e for e in elements(table) if e.get("type") == "tr"][1:]
    return [head] + [[text(e) for e in elements(row) if e.get("type") == "td"] for row in rows]


def _lists(tree: Any) -> list[list[tuple[str, str]]]:
    """Each list of names and figures in ``tree``, as its rows' (name, figure) texts."""
    return [
        [
            (text(classed(row, "app-kv__k")[0]), text(classed(row, "app-kv__v")[0]))
            for row in classed(kv, "app-kv__row")
        ]
        for kv in classed(tree, "app-kv")
    ]


def _counts(tree: Any) -> list[tuple[str, str]]:
    """Each ratings box of ``tree``: its count and its name."""
    return [
        (text(classed(box, "figure-lg")[0]), text(classed(box, "app-company__gradename")[0]))
        for box in classed(tree, "app-company__grade")
    ]


def _with_earnings(next_date: dict[str, Any] | None) -> dict[str, Any]:
    """The estimates answer whose next date is ``next_date``, its row first in the table dated
    as it is, or, for none, the reported quarters alone."""
    reported = EARNINGS["rows"][1:]
    if next_date is None:
        return answers.ESTIMATES | {"earnings": {"next": None, "rows": reported}}
    first = EARNINGS["rows"][0] | {"day": next_date["day"]}
    return answers.ESTIMATES | {"earnings": {"next": next_date, "rows": [first, *reported]}}


# --------------------------------------------------------------------------------- Earnings


def test_the_earnings_head_and_table() -> None:
    """The head says the next date, after the close for FMP's amc and not confirmed where FMP
    says false; the table's first row is the next date with its two estimates and the dash for
    its two actuals, then every reported quarter, newest first: EPS to cents, revenue compact,
    in US dollars; the day leads its row, monospaced as a date is (14.1). No surprise column, no
    chip, no cite."""
    tree = _page("earnings", _with_earnings(NEXT))
    assert tree.get("type") == "section"
    assert _title(tree) == "Earnings"
    assert _head_texts(tree) == ["next 4 Feb 2027, after the close, not confirmed"]
    [caption] = classed(tree, "caption")
    assert caption["props"]["className"] == "caption app-company__note"
    assert _table(tree) == [
        EARNINGS_HEAD,
        ["4 Feb 2027", "—", "$2.18", "—", "$28.42B"],
        *REPORTED,
    ]
    cells = [e for e in elements(tree) if e.get("type") == "td"]
    assert {e["props"]["className"] for e in cells[0::5]} == {"body app-company__rowname"}
    for day in cells[0::5]:
        [span] = day["props"]["children"]
        assert (span["type"], span["props"]["className"]) == ("span", "figure")
    assert {e["props"]["className"] for e in cells if e not in cells[0::5]} == {"figure"}
    assert [e for e in elements(tree) if "basis" in e["props"] or "principal" in e["props"]] == []
    # the stored answer: LFOX's next date
    stored = _page("earnings", answers.ESTIMATES)
    assert _head_texts(stored) == ["next 14 Jan 2027, after the close, not confirmed"]
    assert _table(stored)[1] == ["14 Jan 2027", "—", "$2.18", "—", "$28.42B"]


def test_the_head_without_a_next_date_and_with_a_confirmed_one() -> None:
    """With no next date the head has no caption and the table only the reported quarters.
    Before the open for FMP's bmo; no time's words for any other time; not confirmed only where
    FMP says false, not where it says true or nothing."""
    tree = _page("earnings", _with_earnings(None))
    assert _head_texts(tree) == []
    assert classed(tree, "caption") == []
    assert _table(tree) == [EARNINGS_HEAD, *REPORTED]
    for next_date, words in (
        (NEXT | {"time": "bmo", "confirmed": True}, "next 4 Feb 2027, before the open"),
        (
            NEXT | {"time": "bmo", "confirmed": False},
            "next 4 Feb 2027, before the open, not confirmed",
        ),
        (NEXT | {"confirmed": None}, "next 4 Feb 2027, after the close"),
        (NEXT | {"time": "dmh"}, "next 4 Feb 2027, not confirmed"),
        (NEXT | {"time": None, "confirmed": True}, "next 4 Feb 2027"),
        (NEXT | {"time": "constructor", "confirmed": None}, "next 4 Feb 2027"),
    ):
        assert _head_texts(_page("earnings", _with_earnings(next_date))) == [words], next_date


# ------------------------------------------------------------------------- Consensus estimates


def test_the_consensus_rows_carry_the_reporting_currency() -> None:
    """One row a fiscal year, oldest first: the year as plain text, revenue compact, the three
    EPS figures to cents and the analysts as a count. A figure in the reporting currency carries
    its code in the dollar sign's place, one in US dollars the dollar sign."""
    tree = _page("consensus", answers.ESTIMATES)
    assert tree.get("type") == "section"
    assert _title(tree) == "Consensus estimates"
    assert _head_texts(tree) == []
    assert _table(tree) == [
        CONSENSUS_HEAD,
        ["2026", "TWD 3.99T", "TWD 61.20", "TWD 58.70", "TWD 63.90", "18"],
        ["2027", "TWD 4.62T", "TWD 71.90", "TWD 64.00", "TWD 80.30", "16"],
        ["2028", "TWD 5.31T", "TWD 84.10", "TWD 72.50", "TWD 96.80", "10"],
        ["2029", "TWD 6.12T", "TWD 98.40", "TWD 81.20", "TWD 117.60", "5"],
    ]
    [year] = [e for e in elements(tree) if e.get("type") == "td"][:1]
    assert year["props"]["className"] == "body app-company__rowname"

    def twd(value: float) -> dict[str, Any]:
        return {"value": value, "currency": "TWD"}

    def usd(value: float) -> dict[str, Any]:
        return {"value": value, "currency": "USD"}

    rows = [
        {
            "fiscalYear": 2027,
            "revenue": twd(11.54e12),
            "eps": twd(949.56),
            "epsLow": twd(901.2),
            "epsHigh": twd(1012.4),
            "analysts": 1240,
        },
        {
            "fiscalYear": 2028,
            "revenue": usd(478.8e9),
            "eps": usd(7.42),
            "epsLow": usd(-0.35),
            "epsHigh": usd(8.1),
            "analysts": None,
        },
    ]
    assert _table(_page("consensus", answers.ESTIMATES | {"consensus": rows}))[1:] == [
        ["2027", "TWD 11.54T", "TWD 949.56", "TWD 901.20", "TWD 1012.40", "1,240"],
        ["2028", "$478.8B", "$7.42", "−$0.35", "$8.10", "—"],
    ]


# --------------------------------------------------------------------------------- Analysts


def test_the_analysts_block() -> None:
    """The consensus word in the head; under Price target four rows in two columns, Consensus and
    Median, then Low and High, to cents in US dollars; under Ratings five boxes in a row, each a
    count in figure-lg over its name, in the Words table's order. No track and no marks."""
    tree = _page("analysts", answers.ESTIMATES)
    assert tree.get("type") == "section"
    assert _title(tree) == "Analysts"
    assert _head_texts(tree) == ["consensus Buy"]
    [caption] = [e for e in classed(tree, "caption") if text(e) == "consensus Buy"]
    assert caption["props"]["className"] == "caption app-company__note"
    titles = classed(tree, "app-company__subtitle")
    assert [(e["type"], e["props"]["className"], text(e)) for e in titles] == [
        ("h3", "label app-company__subtitle", "Price target"),
        ("h3", "label app-company__subtitle", "Ratings"),
    ]
    [target] = classed(tree, "app-company__two")
    assert _lists(target) == [
        [("Consensus", "$205.60"), ("Median", "$210.00")],
        [("Low", "$150.00"), ("High", "$240.00")],
    ]
    [grades] = classed(tree, "app-company__grades")
    assert _counts(grades) == [
        ("3", "Strong buy"),
        ("14", "Buy"),
        ("4", "Hold"),
        ("1", "Sell"),
        ("0", "Strong sell"),
    ]
    box = classed(grades, "app-company__grade")[0]
    [count, name] = [e for e in elements(box) if e.get("type") == "p"]
    assert count["props"]["className"] == "figure-lg"
    assert name["props"]["className"] == "caption app-company__gradename"
    found = list(elements(tree))
    assert found.index(titles[0]) < found.index(target) < found.index(titles[1])
    assert found.index(titles[1]) < found.index(grades)
    # no track and no marks on it: the founder had them removed
    names = {n for e in found for n in str(e["props"].get("className") or "").split()}
    assert [n for n in names if "track" in n or "mark" in n or "target" in n] == []
    assert [e for e in found if e.get("type") in ("svg", "progress", "meter")] == []
    [rule] = re.findall(r"\n  \.app-company__grades \{([^}]*)\}", _static_file("index.html"))
    assert "grid-template-columns: repeat(5, minmax(0, 1fr));" in " ".join(rule.split())


def test_the_analysts_block_without_a_word_or_a_count() -> None:
    """No consensus word: no caption in the head. A missing count is the dash; a target missing
    the dash."""
    ratings = RATINGS | {"consensus": None, "buy": None}
    target = answers.ESTIMATES["target"] | {"median": None}
    tree = _page("analysts", answers.ESTIMATES | {"ratings": ratings, "target": target})
    assert _head_texts(tree) == []
    assert [count for count, _ in _counts(tree)] == ["3", "—", "4", "1", "0"]
    assert _lists(tree)[0] == [("Consensus", "$205.60"), ("Median", "—")]


# ------------------------------------------------------------------------- an empty answer


def test_an_answer_with_nothing_draws_dashes_and_empty_tables() -> None:
    """Review Focus 2: a company with nothing stored but its profile, which this read does not
    draw. No caption in either head; the two tables have their heads and no row; the four targets
    and the five counts are the dash. A row that holds nothing but its day or its year draws the
    dash in every figure."""
    empty = answers.profile_only_estimates()
    earnings = _page("earnings", empty)
    assert _head_texts(earnings) == []
    assert _table(earnings) == [EARNINGS_HEAD]
    [body] = [e for e in elements(earnings) if e.get("type") == "tbody"]
    assert body["props"]["children"] == [[]]
    consensus = _page("consensus", empty)
    assert _table(consensus) == [CONSENSUS_HEAD]
    analysts = _page("analysts", empty)
    assert _head_texts(analysts) == []
    assert [figure for rows in _lists(analysts) for _, figure in rows] == ["—"] * 4
    assert [count for count, _ in _counts(analysts)] == ["—"] * 5
    drawn = _page("draw.estimates", empty, answers.DETAIL)
    assert [_title(e) for e in elements(drawn) if e.get("type") == "section"] == [
        "Earnings",
        "Analysts",
        "Consensus estimates",
    ]
    bare = {"day": "2026-07-16", "eps": None, "epsEstimate": None}
    bare |= {"revenue": None, "revenueEstimate": None}
    rows = _table(_page("earnings", empty | {"earnings": {"next": None, "rows": [bare]}}))
    assert rows[1:] == [["16 Jul 2026", "—", "—", "—", "—"]]
    year = {"fiscalYear": 2027, "revenue": None, "eps": None, "epsLow": None, "epsHigh": None}
    year |= {"analysts": None}
    rows = _table(_page("consensus", empty | {"consensus": [year]}))
    assert rows[1:] == [["2027", "—", "—", "—", "—", "—"]]


# --------------------------------------------------------------------------------- the tab


def test_the_tab_draws_earnings_at_the_left_and_analysts_then_consensus_at_the_right() -> None:
    """``draw.estimates``: the grid of two columns, the founder's layout: Earnings alone at the
    left; Analysts, then Consensus estimates, at the right. Neither column is the Overview's that
    adds no height of its own, and no block fills: the page's rule grows the last block of the
    shorter column (9). The script loads after company.js."""
    tree = _page("draw.estimates", answers.ESTIMATES, answers.DETAIL)
    assert tree["props"]["className"] == "app-company__grid"
    left, right = tree["props"]["children"]
    assert left["props"]["className"] == "app-company__col"
    assert right["props"]["className"] == "app-company__col"
    assert left["props"]["children"] == [_page("earnings", answers.ESTIMATES)]
    assert right["props"]["children"] == [
        _page("analysts", answers.ESTIMATES),
        _page("consensus", answers.ESTIMATES),
    ]
    assert classed(tree, "app-company__panel--fill") == []
    assert [e["props"]["className"] for e in elements(tree) if e.get("type") == "section"] == [
        "app-company__panel"
    ] * 3
    html = _static_file("index.html")
    scripts = re.findall(r'<script src="/static/([\w.]+)"></script>', html)
    assert scripts.index("company_estimates.js") > scripts.index("company.js")


TYPE_STYLES = {"heading", "label", "body", "caption", "figure", "figure-lg"}  # the design system's
KV = {"app-kv", "app-kv__row", "app-kv__k", "app-kv__v"}  # company.js's list of names and figures


def test_the_estimates_classes_are_the_company_page_s_alone() -> None:
    """Every class the tab's blocks draw but the design system's type styles is the company
    page's own: under its prefix, or company.js's list of names and figures, and in no script but
    the company page's, so none of the tab's rules can style an element another view draws."""
    tree = _page("draw.estimates", answers.ESTIMATES, answers.DETAIL)
    drawn = {
        name for e in elements(tree) for name in str(e["props"].get("className") or "").split()
    }
    own = drawn - TYPE_STYLES
    tab = {"__subtitle", "__grades", "__grade", "__gradename"}
    assert {"app-company" + part for part in tab} <= own
    assert KV <= own
    page = {
        "company.js",
        "company_overview.js",
        "company_chart.js",
        "company_estimates.js",
        "company_financials.js",
        "company_financials_chart.js",
    }
    scripts = {p.name: p.read_text() for p in STATIC.rglob("*.js") if p.name not in page}
    assert {"app.js", "report.js", "inbox.js", "charts.js", "bundle.js"} <= set(scripts)
    for name in sorted(own):
        assert name.startswith("app-company__") or name in KV, name
        assert [script for script, body in scripts.items() if name in body] == [], name
